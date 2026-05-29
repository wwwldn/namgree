# -*- coding: utf-8 -*-
import db
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = db.get_connection()
if conn:
    cur = conn.cursor()
    cur.execute("UPDATE tickets SET status = 'Hoàn thành' WHERE status = 'Done'")
    print(f"Done -> Hoàn thành: {cur.rowcount}")
    cur.execute("UPDATE tickets SET status = 'Mới tạo' WHERE status = 'New'")
    print(f"New -> Mới tạo: {cur.rowcount}")
    cur.execute("UPDATE tickets SET status = 'Đã tiếp nhận' WHERE status = 'In Progress'")
    print(f"In Progress -> Đã tiếp nhận: {cur.rowcount}")
    conn.commit()
    cur.close()
    conn.close()
    print("Migration complete!")
else:
    print("Cannot connect to DB")
