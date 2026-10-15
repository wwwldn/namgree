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
6. **Mã ticket trùng & task trùng (13/10/2026).** Mã cũ `GREE-IT_YYYYMM_<random 100-999>` dễ trùng (tháng 6 có 61 ticket) → nay `db.create_ticket()` tự sinh mã tăng dần theo tháng và tự thử lại khi trùng. `complete_ticket()` trước đây INSERT `tasks` mỗi lần bấm → 2 ticket bị đếm đôi trong báo cáo tuần; nay mỗi ticket chỉ giữ 1 dòng `tasks`.
7. **Mật khẩu Admin từng nằm trong code public** (`gree@2025`, vẫn còn trong lịch sử git — không dùng lại mật khẩu này). Nay đọc từ Secrets `ADMIN_PASSWORD`; thiếu key này thì không đăng nhập Admin được.
8. **`AttributeError` khi gọi hàm mới trong `db.py` (15/10/2026, `db.get_work_note_drafts`).** Streamlit Cloud tự deploy chạy lại `app.py` mới nhưng vẫn giữ module `db` cũ trong bộ nhớ. → `app.py` so `db.LOADED_MTIME` với thời gian sửa file `db.py` để tự `importlib.reload(db)`. Module khác (`mailer.py`, `ai_notes.py`…) chưa có cơ chế này → sửa chúng thì **Manage app → Reboot app**.

## Quy tắc an toàn
- Repo là **public**: không commit mật khẩu, `secrets.toml`, file backup `.sql` có dữ liệu thật. `cmd_run.txt` hiện còn mật khẩu Railway — không commit file này.
- Secrets cần có: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`, `ADMIN_PASSWORD`.
- Đổi trạng thái ticket chỉ qua `db.update_ticket_status()` / `db.complete_ticket()` — hai hàm này ghi `closed_at` và dòng log `type='status'`. Không UPDATE `tickets.status` trực tiếp.
- Báo cáo tuần = ticket (theo Form/domain) + bảng `work_notes` (ghi chú việc ngoài ticket, nhóm `erp`/`warranty`/`gree_app`/`it` ↔ 4 dòng file mẫu, xem `WORK_NOTE_CATEGORIES` trong `app.py`). Ticket chỉ dùng thống kê yêu cầu online — không tạo ticket cho việc tự follow.
- Code mới gọi DB: dùng `get_connection()` trong `db.py`, xử lý trường hợp trả về `None`; sau khi ghi dữ liệu gọi `.clear()` cache tương ứng (`get_all_tickets`, `get_tasks`, `get_settings`). `get_connection()` lấy từ pool → luôn `conn.close()` để trả kết nối.
- **AI nạp nội dung báo cáo tuần (ngoài ticket):** không INSERT thẳng `work_notes`. Soạn JSON `{"week_start": "YYYY-MM-DD", "notes": [{"date", "category": erp|warranty|gree_app|it, "content"}]}` rồi chạy `python ai_notes.py <file.json>` (thử trước với `--dry-run`) → vào bảng `work_note_drafts` chờ duyệt. Người dùng duyệt ở trang "Báo cáo tuần" thì mới chuyển sang `work_notes`. Nội dung nên viết ngắn gọn kiểu gạch đầu dòng, mỗi dòng 1 việc.
- Khi gặp lỗi mới: thêm vào mục "Lỗi đã gặp" ở trên (ngày, thông báo lỗi, nguyên nhân, cách sửa).
