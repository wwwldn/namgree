import mysql.connector
from mysql.connector import Error
import datetime
import json

DB_CONFIG = {
    'host': 'localhost',
    'database': 'namlegree',
    'user': 'root',
    'password': '',
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
    return None

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticket_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id VARCHAR(50) NOT NULL,
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
            content VARCHAR(255) NOT NULL,
            action TEXT NOT NULL,
            status VARCHAR(50) DEFAULT 'Done',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    cursor.close()
    conn.close()

def get_all_tickets():
    conn = get_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
    tickets = cursor.fetchall()
    
    # Fetch messages for each ticket
    for ticket in tickets:
        cursor.execute("SELECT * FROM ticket_messages WHERE ticket_id = %s ORDER BY created_at ASC", (ticket['id'],))
        # Format time for UI
        msgs = cursor.fetchall()
        for m in msgs:
            m['time'] = m['created_at'].strftime("%H:%M")
        ticket['msgs'] = msgs
        
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
    conn.commit()
    cursor.close()
    conn.close()
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
    return True

def complete_ticket(ticket_id, subject, log_msg):
    conn = get_connection()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET status = 'Hoàn thành' WHERE id = %s", (ticket_id,))
    cursor.execute(
        "INSERT INTO tasks (content, action, status) VALUES (%s, %s, 'Done')",
        (subject, log_msg)
    )
    conn.commit()
    cursor.close()
    conn.close()
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
    return True
