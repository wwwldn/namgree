# AI PROGRAMMING CONTEXT: NAMLEGREE

## 1. Môi trường & Định danh
- **Project Name:** namlegree (Antigravity Project)
- **Local Path:** `D:\NAMLE\GIT\Antigravity\namlegree`
- **Personal Domain:** `https://leducnam.com/greevietnam`
- **Tech Stack:** Python (Streamlit), Pandas, Openpyxl.

## 2. Mục tiêu dự án
Xây dựng công cụ cá nhân hóa để quản lý công việc tại **Gree Vietnam**.
- Tổng hợp link hướng dẫn nghiệp vụ IT/Database.
- Quản lý các biểu mẫu (Forms) từ các phòng ban công ty Gree.
- Tự động hóa xuất báo cáo tuần (Weekly Report) dựa trên file mẫu Excel.

## 3. Lộ trình phát triển (Phân kỳ)
- **Giai đoạn 1:** Dựng Portal điều hướng, quản lý danh mục Link và Form. Giao diện tối giản, chuyên nghiệp theo brand leducnam.com.
- **Giai đoạn 2:** Phát triển Engine xử lý Excel (Export báo cáo tuần).
- **Giai đoạn 3:** Tích hợp Database lưu trữ lịch sử task và bảo mật đăng nhập.

## 4. Quy tắc Code
- Biến và hàm đặt tên rõ nghĩa (English), Comment giải thích bằng tiếng Việt.
- Sử dụng file `config.py` để quản lý các hằng số (URL, Path).
- Luôn ưu tiên Clean Code và xử lý ngoại lệ (Try-Except) khi đọc file.

## 5. Database & Deploy
- **Production:** Streamlit Cloud — `https://namgree.streamlit.app/`, tự deploy khi push lên nhánh `main`.
- **Database (từ 08/10/2026):** TiDB Cloud Serverless — host `gateway01.ap-southeast-1.prod.aws.tidbcloud.com`, port `4000`, bắt buộc SSL, user dạng `xxxxxxxx.root`.
  - Trước đó dùng MySQL trên Railway (đã ngừng, không kết nối được nữa).
- **Thông tin đăng nhập DB:** chỉ để trong Streamlit Cloud > Settings > Secrets (`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`).
  - Ở máy local: `.streamlit/secrets.toml` (đã có trong `.gitignore`). Không có file này thì `db.py` dùng MySQL localhost.
  - Repo là public → **không** ghi mật khẩu vào code, `cmd_run.txt` hay file `.md`.
- **Lỗi DB trên web:** Streamlit Cloud ẩn nội dung exception ("error message is redacted"), nên `app.py` bọc `db.init_db()` trong try/except để hiện lỗi thật bằng `st.error`. Xem thêm log tại "Manage app".

### Lưu ý khi import file dump (.sql) vào TiDB
- File dump xếp bảng theo ABC → `ticket_messages` được tạo **trước** `tickets`. Nếu khóa ngoại chưa tắt, bảng `ticket_messages` lỗi và bị bỏ qua.
- Dòng `/*!40014 SET ... FOREIGN_KEY_CHECKS=0 */` có sẵn trong dump có thể không được thực thi → luôn thêm `SET FOREIGN_KEY_CHECKS=0;` ở **đầu** file trước khi import.
- Database `namgree` trên TiDB có collation mặc định `utf8mb4_unicode_ci`, còn các bảng import từ MySQL dump dùng `utf8mb4_0900_ai_ci`. TiDB vẫn kiểm tra khóa ngoại khi chạy `CREATE TABLE IF NOT EXISTS` với bảng **đã tồn tại** → lỗi `3780 ... are incompatible`. Vì vậy `db.init_db()` chỉ CREATE những bảng chưa có (kiểm tra bằng `SHOW TABLES`).
- Sau khi import, kiểm tra: `SELECT COUNT(*) FROM tickets;` và `SELECT COUNT(*) FROM ticket_messages;`
- Lệnh import mẫu: xem `cmd_run.txt` (mục TiDB Cloud).

### Sự cố 09/10/2026
- App lỗi `3780` khi khởi động (tại `CREATE TABLE IF NOT EXISTS tickets`), dù dữ liệu trên TiDB đầy đủ (159 tickets, 182 tin nhắn, khớp backup 24/09).
- Nguyên nhân: lệch collation giữa DB mặc định và bảng import (xem mục trên). Đã sửa `db.init_db()` để bỏ qua CREATE với bảng đã có.
