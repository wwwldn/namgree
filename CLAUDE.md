# NamLeGree — AI đọc trước khi xử lý

Đọc thêm `CONTEXT.md` (mục tiêu dự án, quy tắc code, chi tiết DB/deploy) và `.cursorrules`.

## Môi trường
- Production: Streamlit Cloud `https://namgree.streamlit.app/` — push lên `main` là tự deploy.
- DB: TiDB Cloud Serverless (MySQL-compatible, v8.5), port 4000, bắt buộc SSL. Thông tin đăng nhập trong Streamlit Secrets / `.streamlit/secrets.toml` (local, gitignore).
- Không có `.streamlit/secrets.toml` thì `db.py` tự dùng MySQL localhost.
- Kết nối thử từ máy: `"/e/MariaDB 11.3/bin/mysql" -h <host> -P 4000 -u <user> --ssl <db>` (đặt mật khẩu qua biến `MYSQL_PWD`).

## Lỗi đã gặp — kiểm tra trước khi sửa
1. **Lỗi trên web bị ẩn ("error message is redacted").** Đừng đoán. `app.py` đã bọc `db.init_db()` để hiện lỗi thật qua `st.error`; lỗi chỗ khác thì xem log "Manage app" hoặc tái hiện ở local với `secrets.toml` thật.
2. **`3780 ... foreign key constraint 'ticket_messages_ibfk_1' are incompatible` (09/10/2026).** DB `namgree` mặc định `utf8mb4_unicode_ci`, bảng import từ dump là `utf8mb4_0900_ai_ci`; TiDB vẫn kiểm tra khóa ngoại khi `CREATE TABLE IF NOT EXISTS` bảng đã có. → `init_db()` chỉ CREATE bảng chưa có (`SHOW TABLES`). Không bỏ cơ chế này; bảng/cột mới có khóa ngoại phải cùng collation với cột được tham chiếu.
3. **Import dump vào TiDB làm mất bảng `ticket_messages`.** Dump xếp bảng theo ABC nên `ticket_messages` được tạo trước `tickets`. Luôn thêm `SET FOREIGN_KEY_CHECKS=0;` ở đầu file (dòng `/*!40014 ... */` trong dump có thể không chạy). Sau import kiểm tra `SELECT COUNT(*)` từng bảng.
4. **Lần đầu chẩn đoán sai (09/10/2026):** đã kết luận "thiếu bảng" khi chưa xem DB thật. → Có thông tin đăng nhập thì kiểm tra DB thật (bảng, collation, số dòng) trước khi sửa code.
5. **Railway (DB cũ) đã ngừng,** kết nối báo `2013 Lost connection ... reading initial communication packet`. Không dùng lại các host `*.proxy.rlwy.net` trong `cmd_run.txt`.

## Quy tắc an toàn
- Repo là **public**: không commit mật khẩu, `secrets.toml`, file backup `.sql` có dữ liệu thật. `cmd_run.txt` hiện còn mật khẩu Railway — không commit file này.
- Code mới gọi DB: dùng `get_connection()` trong `db.py`, xử lý trường hợp trả về `None`; sau khi ghi dữ liệu gọi `.clear()` cache tương ứng (`get_all_tickets`, `get_settings`).
- Khi gặp lỗi mới: thêm vào mục "Lỗi đã gặp" ở trên (ngày, thông báo lỗi, nguyên nhân, cách sửa).
