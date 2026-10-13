import mysql.connector
from mysql.connector import Error, pooling
import datetime
import json

import streamlit as st

try:
    DB_CONFIG = {
        'host': st.secrets["DB_HOST"],
        'database': st.secrets["DB_NAME"],
        'user': st.secrets["DB_USER"],
        'password': st.secrets["DB_PASS"],
        'port': int(st.secrets["DB_PORT"])
    }

except Exception as e:
    print(f"Không đọc được st.secrets ({e!r}) → dùng DB localhost")
    DB_CONFIG = {
        'host': 'localhost',
        'database': 'namlegree',
        'user': 'root',
        'password': '123456',
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_general_ci'
    }


# Trạng thái coi như đã đóng (ghi closed_at)
CLOSED_STATUSES = ("Hoàn thành", "Từ chối")
# Mã ticket tạo theo giờ Việt Nam (đổi tháng đúng lúc 0h VN)
VN_TZ = datetime.timezone(datetime.timedelta(hours=7))


@st.cache_resource
def _get_pool():
    # Giữ sẵn kết nối: mỗi lần mở kết nối SSL mới tới TiDB (Singapore) mất vài trăm ms
    return pooling.MySQLConnectionPool(pool_name="namgree", pool_size=5, **DB_CONFIG)


def get_connection():
    try:
        try:
            conn = _get_pool().get_connection()
            # TiDB Serverless tự cắt kết nối rảnh lâu → ping để nối lại trước khi dùng
            conn.ping(reconnect=True, attempts=2, delay=0)
            return conn
        except pooling.PoolError:
            # Hết kết nối rảnh trong pool → mở kết nối riêng như trước
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        # Hiện lỗi lên web — trước đây chỉ print nên trang trống mà không ai biết vì sao
        st.error(f"❌ Không kết nối được DB `{DB_CONFIG.get('host')}:{DB_CONFIG.get('port', 3306)}` — {e}")
    return None

@st.cache_resource
def init_db():
    conn = get_connection()
    if not conn:
        return
    cursor = conn.cursor()

    # Chỉ CREATE bảng chưa có. TiDB vẫn kiểm tra khóa ngoại khi chạy CREATE TABLE IF NOT EXISTS
    # với bảng đã tồn tại → lỗi 3780 vì DB mặc định utf8mb4_unicode_ci còn bảng import là utf8mb4_0900_ai_ci.
    cursor.execute("SHOW TABLES")
    existing_tables = {row[0] for row in cursor.fetchall()}

    # Create tickets table
    if 'tickets' not in existing_tables:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id VARCHAR(50) PRIMARY KEY,
            subject VARCHAR(255) NOT NULL,
            requester VARCHAR(100) NOT NULL,
            status VARCHAR(50) DEFAULT 'Mới tạo',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
    
    # Attempt to add form_type and form_data columns (will fail silently if they already exist)
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN form_type VARCHAR(255)")
    except Error:
        pass
        
    try:
        cursor.execute("ALTER TABLE tickets ADD COLUMN form_data JSON")
    except Error:
        pass

    # closed_at: thời điểm Hoàn thành/Từ chối → tính thời gian xử lý
    cursor.execute("SHOW COLUMNS FROM tickets LIKE 'closed_at'")
    if not cursor.fetchall():
        cursor.execute("ALTER TABLE tickets ADD COLUMN closed_at DATETIME NULL")
        # Ticket đã đóng từ trước: lấy mốc ghi nhận task, không có thì lấy tin nhắn cuối
        cursor.execute("""
            UPDATE tickets t SET closed_at = COALESCE(
                (SELECT MAX(k.created_at) FROM tasks k WHERE k.ticket_id = t.id),
                (SELECT MAX(m.created_at) FROM ticket_messages m WHERE m.ticket_id = t.id),
                t.created_at)
            WHERE t.status IN ('Hoàn thành', 'Từ chối')
        """)
    
    # Create ticket_messages table
    # ticket_id phải cùng charset/collation với tickets.id, nếu không khóa ngoại lỗi 3780.
    # (tickets import từ MySQL dump là utf8mb4_0900_ai_ci, còn TiDB mặc định utf8mb4_bin)
    cursor.execute("""
        SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tickets' AND COLUMN_NAME = 'id'
    """)
    row = cursor.fetchone()
    id_collate = f"CHARACTER SET {row[0]} COLLATE {row[1]}" if row and row[0] else ""
    if 'ticket_messages' not in existing_tables:
        cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS ticket_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id VARCHAR(50) {id_collate} NOT NULL,
            user VARCHAR(100) NOT NULL,
            msg TEXT NOT NULL,
            type VARCHAR(50) DEFAULT 'public',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
        """)
    
    # Create tasks table (for Báo cáo tuần)
    if 'tasks' not in existing_tables:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id VARCHAR(50),
            content VARCHAR(255) NOT NULL,
            action TEXT NOT NULL,
            status VARCHAR(50) DEFAULT 'Done',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

    # Bổ sung ticket_id cho DB đã tồn tại từ trước (sẽ lỗi âm thầm nếu cột đã có)
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN ticket_id VARCHAR(50)")
    except Error:
        pass

    # Bảng cấu hình chung (SMTP, lịch gửi báo cáo...) dạng key-value.
    # Lưu ở DB thay vì trong code vì repo là public.
    if 'app_settings' not in existing_tables:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """)

    # Ghi chú công việc ngoài ticket (việc tự follow/xử lý) → đổ vào báo cáo tuần theo nhóm
    if 'work_notes' not in existing_tables:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_notes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            note_date DATE NOT NULL,
            category VARCHAR(30) NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

    conn.commit()
    cursor.close()
    conn.close()

@st.cache_data(ttl=30)
def get_all_tickets():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    tickets = cursor.fetchall()

    # Lấy toàn bộ message của mọi ticket trong 1 query thay vì query lặp lại theo từng ticket
    if tickets:
        ticket_ids = [t['id'] for t in tickets]
        placeholders = ",".join(["%s"] * len(ticket_ids))
        cursor.execute(
            f"SELECT * FROM ticket_messages WHERE ticket_id IN ({placeholders}) ORDER BY created_at ASC",
            ticket_ids
        )
        msgs_by_ticket = {}
        for m in cursor.fetchall():
            m['time'] = m['created_at'].strftime("%H:%M")
            m['date'] = m['created_at'].strftime("%d/%m/%Y")
            msgs_by_ticket.setdefault(m['ticket_id'], []).append(m)
        for ticket in tickets:
            ticket['msgs'] = msgs_by_ticket.get(ticket['id'], [])

    cursor.close()
    conn.close()
    return tickets

def _next_ticket_id(cursor):
    """Mã ticket tăng dần theo tháng: GREE-IT_YYYYMM_001, _002...
    Trước đây dùng số ngẫu nhiên 100-999 nên dễ trùng khi một tháng có vài chục ticket."""
    prefix = f"GREE-IT_{datetime.datetime.now(VN_TZ):%Y%m}_"
    cursor.execute("SELECT id FROM tickets WHERE id LIKE %s", (prefix.replace("_", r"\_") + "%",))
    numbers = [int(row[0][len(prefix):]) for row in cursor.fetchall() if row[0][len(prefix):].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1:03d}"

def _set_status(cursor, ticket_id, new_status, changed_by):
    """Đổi trạng thái và ghi 1 dòng log 'cũ → mới' (type='status') để biết ai đổi, lúc nào.
    Trả về False nếu trạng thái không đổi."""
    cursor.execute("SELECT status FROM tickets WHERE id = %s", (ticket_id,))
    row = cursor.fetchone()
    if not row or row[0] == new_status:
        return False
    if new_status in CLOSED_STATUSES:
        cursor.execute("UPDATE tickets SET status = %s, closed_at = NOW() WHERE id = %s", (new_status, ticket_id))
    else:
        cursor.execute("UPDATE tickets SET status = %s, closed_at = NULL WHERE id = %s", (new_status, ticket_id))
    cursor.execute(
        "INSERT INTO ticket_messages (ticket_id, user, msg, type) VALUES (%s, %s, %s, 'status')",
        (ticket_id, changed_by, f"Trạng thái: {row[0]} → {new_status}")
    )
    return True

def create_ticket(subject, requester, form_type=None, form_data=None, status='Mới tạo'):
    """Tạo ticket mới, trả về mã ticket (None nếu lỗi kết nối)."""
    conn = get_connection()
    if not conn: return None
    cursor = conn.cursor()
    form_data_str = json.dumps(form_data, ensure_ascii=False) if form_data else None
    ticket_id = None
    # Thử lại nếu 2 người tạo ticket cùng lúc và lấy trùng số
    for attempt in range(3):
        ticket_id = _next_ticket_id(cursor)
        try:
            cursor.execute(
                "INSERT INTO tickets (id, subject, requester, status, form_type, form_data, closed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, IF(%s, NOW(), NULL))",
                (ticket_id, subject, requester, status, form_type, form_data_str, status in CLOSED_STATUSES)
            )
            break
        except mysql.connector.IntegrityError:
            conn.rollback()
            if attempt == 2:
                raise
    # Thêm message đầu tiên
    cursor.execute(
        "INSERT INTO ticket_messages (ticket_id, user, msg, type) VALUES (%s, %s, %s, 'public')",
        (ticket_id, requester, f"Hệ thống: Ticket tự động được tạo từ form '{form_type}'." if form_type else subject)
    )
    # Một số form (vd: Form 7 - Admin Log) tạo ticket với trạng thái Hoàn thành ngay từ đầu.
    # Ghi nhận luôn vào tasks để không bị bỏ sót khỏi báo cáo tuần.
    if status == 'Hoàn thành':
        cursor.execute(
            "INSERT INTO tasks (ticket_id, content, action, status) VALUES (%s, %s, %s, 'Done')",
            (ticket_id, subject, "Ticket được tạo và hoàn thành ngay khi khởi tạo.")
        )
    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    get_tasks.clear()
    return ticket_id

def add_ticket_message(ticket_id, user, msg, msg_type, from_admin=False):
    """from_admin: do code truyền vào (đã kiểm tra đăng nhập), không suy ra từ tên người gửi
    — khách có thể tự đặt tên bắt đầu bằng 'Admin'."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ticket_messages (ticket_id, user, msg, type) VALUES (%s, %s, %s, %s)",
        (ticket_id, user, msg, msg_type)
    )

    # Nếu đang 'Mới tạo' thì đổi thành 'Đã tiếp nhận' khi Admin phản hồi
    if from_admin:
        cursor.execute("SELECT status FROM tickets WHERE id = %s", (ticket_id,))
        row = cursor.fetchone()
        if row and row[0] == 'Mới tạo':
            _set_status(cursor, ticket_id, 'Đã tiếp nhận', user)

    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    return True

def complete_ticket(ticket_id, subject, log_msg, changed_by="Admin"):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    _set_status(cursor, ticket_id, 'Hoàn thành', changed_by)
    # Mỗi ticket chỉ giữ 1 dòng trong tasks: hoàn thành lại (sau khi mở lại) hoặc bấm 2 lần
    # trước đây tạo dòng trùng → báo cáo tuần đếm 2 lần.
    cursor.execute("DELETE FROM tasks WHERE ticket_id = %s", (ticket_id,))
    cursor.execute(
        "INSERT INTO tasks (ticket_id, content, action, status) VALUES (%s, %s, %s, 'Done')",
        (ticket_id, subject, log_msg)
    )
    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    get_tasks.clear()
    return True

@st.cache_data(ttl=30)
def get_tasks():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    tasks = cursor.fetchall()
    cursor.close()
    conn.close()
    return tasks

def update_ticket_status(ticket_id, new_status, changed_by="Admin"):
    """Cập nhật trạng thái ticket theo luồng chuẩn (có ghi log thay đổi)."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    _set_status(cursor, ticket_id, new_status, changed_by)
    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    return True

def delete_ticket(ticket_id):
    """Xóa ticket khỏi CSDL (các message liên quan sẽ tự động xóa nhờ CASCADE)."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets WHERE id = %s", (ticket_id,))
    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    return True

@st.cache_data(ttl=30)
def get_settings():
    """Đọc toàn bộ cấu hình dạng key-value. Trả về dict rỗng nếu chưa cấu hình gì."""
    conn = get_connection()
    if not conn: return {}
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT setting_key, setting_value FROM app_settings")
    settings = {row['setting_key']: row['setting_value'] for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return settings

def save_settings(values):
    """Ghi (upsert) nhiều cấu hình cùng lúc. values: dict {key: value}."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    for key, value in values.items():
        cursor.execute(
            "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)",
            (key, "" if value is None else str(value))
        )
    conn.commit()
    cursor.close()
    conn.close()
    get_settings.clear()
    return True

def update_ticket_data(ticket_id, subject, requester, form_data):
    """Cập nhật tiêu đề, người yêu cầu và dữ liệu form đính kèm."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    form_data_str = json.dumps(form_data, ensure_ascii=False) if form_data else None
    cursor.execute(
        "UPDATE tickets SET subject = %s, requester = %s, form_data = %s WHERE id = %s",
        (subject, requester, form_data_str, ticket_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    return True


@st.cache_data(ttl=30)
def get_work_notes():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM work_notes ORDER BY note_date, id")
    notes = cursor.fetchall()
    cursor.close()
    conn.close()
    return notes

def add_work_note(note_date, category, content):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO work_notes (note_date, category, content) VALUES (%s, %s, %s)",
        (note_date, category, content)
    )
    conn.commit()
    cursor.close()
    conn.close()
    get_work_notes.clear()
    return True

def save_work_note_changes(updated, deleted_ids):
    """Lưu chỉnh sửa từ bảng trên trang Báo cáo. updated: list dict (id, note_date, category, content)."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    for note in updated:
        cursor.execute(
            "UPDATE work_notes SET note_date = %s, category = %s, content = %s WHERE id = %s",
            (note['note_date'], note['category'], note['content'], note['id'])
        )
    for note_id in deleted_ids:
        cursor.execute("DELETE FROM work_notes WHERE id = %s", (note_id,))
    conn.commit()
    cursor.close()
    conn.close()
    get_work_notes.clear()
    return True
