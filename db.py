import mysql.connector
from mysql.connector import Error
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


def get_connection():
    try:
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
    
    # Create tickets table
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
    
    # Create ticket_messages table
    # ticket_id phải cùng charset/collation với tickets.id, nếu không khóa ngoại lỗi 3780.
    # (tickets import từ MySQL dump là utf8mb4_0900_ai_ci, còn TiDB mặc định utf8mb4_bin)
    cursor.execute("""
        SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'tickets' AND COLUMN_NAME = 'id'
    """)
    row = cursor.fetchone()
    id_collate = f"CHARACTER SET {row[0]} COLLATE {row[1]}" if row and row[0] else ""
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
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

def create_ticket(ticket_id, subject, requester, form_type=None, form_data=None, status='Mới tạo'):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    form_data_str = json.dumps(form_data, ensure_ascii=False) if form_data else None
    cursor.execute(
        "INSERT INTO tickets (id, subject, requester, status, form_type, form_data) VALUES (%s, %s, %s, %s, %s, %s)",
        (ticket_id, subject, requester, status, form_type, form_data_str)
    )
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
    return True

def add_ticket_message(ticket_id, user, msg, msg_type):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ticket_messages (ticket_id, user, msg, type) VALUES (%s, %s, %s, %s)",
        (ticket_id, user, msg, msg_type)
    )
    
    # Nếu đang 'Mới tạo' thì đổi thành 'Đã tiếp nhận' khi Admin phản hồi
    if user.startswith('Admin'):
        cursor.execute("UPDATE tickets SET status = 'Đã tiếp nhận' WHERE id = %s AND status = 'Mới tạo'", (ticket_id,))

    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    return True

def complete_ticket(ticket_id, subject, log_msg):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = 'Hoàn thành' WHERE id = %s", (ticket_id,))
    cursor.execute(
        "INSERT INTO tasks (ticket_id, content, action, status) VALUES (%s, %s, %s, 'Done')",
        (ticket_id, subject, log_msg)
    )
    conn.commit()
    cursor.close()
    conn.close()
    get_all_tickets.clear()
    return True

def get_tasks():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    tasks = cursor.fetchall()
    cursor.close()
    conn.close()
    return tasks

def update_ticket_status(ticket_id, new_status):
    """Cập nhật trạng thái ticket theo luồng chuẩn."""
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = %s WHERE id = %s", (new_status, ticket_id))
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

