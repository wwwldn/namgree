"""Gửi email qua SMTP. Cấu hình lấy từ bảng app_settings (nhập trong trang Cài đặt),
không hardcode trong code vì repo là public."""

import smtplib
import ssl
from email.message import EmailMessage

DOCX_MIME = ("application", "vnd.openxmlformats-officedocument.wordprocessingml.document")


def parse_recipients(raw):
    """Tách danh sách email từ chuỗi nhập tay (phân cách bằng dấu phẩy, chấm phẩy hoặc xuống dòng)."""
    if not raw:
        return []
    separators = [",", ";", "\n"]
    parts = [raw]
    for sep in separators:
        parts = [piece for chunk in parts for piece in chunk.split(sep)]
    return [p.strip() for p in parts if p.strip()]


def validate_smtp_config(cfg):
    """Trả về danh sách trường còn thiếu để UI báo rõ, thay vì để smtplib ném lỗi khó hiểu.
    Tài khoản/mật khẩu không bắt buộc: relay nội bộ công ty có thể không cần xác thực."""
    missing = []
    if not cfg.get("host"):
        missing.append("SMTP Host")
    if not cfg.get("port"):
        missing.append("Port")
    if not cfg.get("sender"):
        missing.append("Email người gửi")
    return missing


def send_email(cfg, to_list, cc_list, subject, body, attachment=None, attachment_name=None):
    """Gửi 1 email. cfg: dict host/port/user/password/sender/sender_name/security.
    attachment: bytes nội dung file (tùy chọn). Ném exception nếu gửi thất bại."""
    missing = validate_smtp_config(cfg)
    if missing:
        raise ValueError("Thiếu cấu hình SMTP: " + ", ".join(missing))

    to_list = [t for t in (to_list or []) if t]
    cc_list = [c for c in (cc_list or []) if c]
    if not to_list:
        raise ValueError("Chưa có người nhận (To).")

    msg = EmailMessage()
    sender_name = (cfg.get("sender_name") or "").strip()
    msg["From"] = f"{sender_name} <{cfg['sender']}>" if sender_name else cfg["sender"]
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = subject
    msg.set_content(body)

    if attachment:
        msg.add_attachment(
            attachment,
            maintype=DOCX_MIME[0],
            subtype=DOCX_MIME[1],
            filename=attachment_name or "BaoCao.docx",
        )

    port = int(cfg["port"])
    security = (cfg.get("security") or "STARTTLS").upper()
    context = ssl.create_default_context()

    # Chỉ đăng nhập khi có khai báo tài khoản (relay nội bộ thường không cần)
    needs_login = bool(cfg.get("user") and cfg.get("password"))

    if security == "SSL":
        with smtplib.SMTP_SSL(cfg["host"], port, context=context, timeout=30) as server:
            if needs_login:
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg, to_addrs=to_list + cc_list)
    else:
        with smtplib.SMTP(cfg["host"], port, timeout=30) as server:
            if security == "STARTTLS":
                server.starttls(context=context)
            if needs_login:
                server.login(cfg["user"], cfg["password"])
            server.send_message(msg, to_addrs=to_list + cc_list)

    return True
