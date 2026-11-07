import streamlit as st
import pandas as pd
import altair as alt
import json
import os
import datetime
import secrets
import hmac
import calendar
import io
import re
import html
import copy
from config import Config
import db
import mailer
import importlib
import time
import mysql.connector

# Streamlit Cloud tự deploy chỉ chạy lại app.py, module db cũ vẫn nằm trong bộ nhớ
# → db.py trên đĩa mới hơn bản đang chạy thì nạp lại (xem CLAUDE.md, lỗi 8)
if getattr(db, "LOADED_MTIME", None) != os.path.getmtime(db.__file__):
    db = importlib.reload(db)
from ai_notes import parse_notes_json
import tracking_import
import agn_report_pdf
if getattr(agn_report_pdf, "LOADED_MTIME", None) != os.path.getmtime(agn_report_pdf.__file__):
    importlib.reload(agn_report_pdf)
if getattr(tracking_import, "LOADED_MTIME", None) != os.path.getmtime(tracking_import.__file__):
    importlib.reload(tracking_import)
from tracking_import import (parse_tracking_xlsx, match_tracking, describe_change, normalize_ext_id, _same as same_value,
                             MONTH_TOTALS_KEY, merge_month_totals)

try:
    from docx import Document
    from docx.table import _Row, _Cell
    from docx.oxml.ns import qn
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# -----------------
# CHUYỂN HƯỚNG BẢN CŨ (Streamlit Cloud + TiDB) → gree.leducnam.com (từ 16/10/2026)
# -----------------
# Streamlit Cloud không cấu hình redirect phía máy chủ được → app tự chuyển trang, chạy TRƯỚC init_db
# để bản cũ không ghi gì thêm vào TiDB. Giữ nguyên query (?ticket=...) để link ticket cũ vẫn mở đúng.
NEW_APP_URL = "https://gree.leducnam.com"

def _is_old_deployment():
    host = (st.context.headers.get("Host") or "").lower()
    return host.endswith(".streamlit.app") or "tidbcloud.com" in str(db.DB_CONFIG.get("host", ""))

if _is_old_deployment():
    from urllib.parse import urlencode
    query = urlencode(st.query_params.to_dict())
    target = NEW_APP_URL + (f"/?{query}" if query else "/")
    st.markdown(
        f"""
        <div style="max-width:640px;margin:10vh auto;text-align:center">
          <h2>🔀 Hệ thống đã chuyển sang địa chỉ mới</h2>
          <p>Vui lòng dùng <b>{NEW_APP_URL}</b> và lưu lại link mới (đang tự chuyển trang...).</p>
          <p><a href="{html.escape(target)}" target="_blank" rel="noopener" style="display:inline-block;padding:10px 22px;
             background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">
             Mở {NEW_APP_URL.removeprefix('https://')}</a></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Streamlit Cloud nhúng app trong iframe sandbox KHÔNG cho chuyển trang cấp trên (target=_top, window.top
    # đều bị chặn) → nút ở trên mở tab mới (sandbox cho phép popup). Tự chuyển: component (cùng origin với
    # khung app) chèn script vào khung app để khung đó tự tải trang mới — khung được tự chuyển chính nó.
    redirect_js = f"""<script>
        try {{
            const d = window.parent.document, s = d.createElement("script");
            s.textContent = "window.location.replace(" + JSON.stringify({json.dumps(target)}) + ")";
            d.body.appendChild(s);
        }} catch (e) {{ console.warn("Không tự chuyển trang được:", e); }}
        </script>"""
    # components.html: iframe có allow-same-origin (truy cập được khung app); bản Streamlit mới đã bỏ thì dùng st.iframe
    try:
        import streamlit.components.v1 as components
        components.html(redirect_js, height=0)
    except (ImportError, AttributeError):
        st.iframe(redirect_js, height=1)
    st.stop()

# Khởi tạo database và bảng
# Tự hiện lỗi vì Streamlit Cloud ẩn nội dung exception không bắt ("error message is redacted")
try:
    db.init_db()
except Exception as e:
    st.error(f"❌ Lỗi khởi tạo DB `{db.DB_CONFIG.get('host')}`: {type(e).__name__} — {e}")
    st.stop()

# -----------------
# ADMIN AUTH CONFIG
# -----------------
ADMIN_USERNAME = "NamIT"
# Tên hiển thị trên log xử lý của Admin
ADMIN_DISPLAY_NAME = "Admin Nam"

def _read_admin_password():
    """Mật khẩu Admin đặt trong Streamlit Secrets (ADMIN_PASSWORD) — repo public nên không ghi trong code."""
    try:
        password = st.secrets.get("ADMIN_PASSWORD")
    except Exception:
        password = None
    return str(password or os.environ.get("ADMIN_PASSWORD", ""))

ADMIN_PASSWORD = _read_admin_password()

def check_admin_password(password):
    if not ADMIN_PASSWORD:
        st.error("Chưa cấu hình `ADMIN_PASSWORD` trong Secrets (web: Manage app → Settings → Secrets; máy local: `.streamlit/secrets.toml`).")
        return False
    return hmac.compare_digest(password.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))

def is_admin() -> bool:
    return st.session_state.get("is_admin", False)

# -----------------
# GHI NHỚ ĐĂNG NHẬP ADMIN (COOKIE)
# -----------------
# Streamlit tạo session mới cho mỗi tab/lần tải trang nên session_state không giữ được
# đăng nhập khi mở link ticket ở tab khác. Lưu 1 token ngẫu nhiên vào cookie, đối chiếu
# với token lưu trong CSDL. Không bao giờ lưu mật khẩu vào cookie.
ADMIN_COOKIE_NAME = "namgree_admin"
ADMIN_SESSION_DAYS = 30
ADMIN_TOKENS_KEY = "admin_session_tokens"

def _load_admin_tokens():
    """Đọc danh sách token còn hạn từ CSDL: {token: hạn dùng ISO}."""
    raw = db.get_settings().get(ADMIN_TOKENS_KEY) or "{}"
    try:
        tokens = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    now = datetime.datetime.now(datetime.timezone.utc)
    valid = {}
    for token, expires in tokens.items():
        try:
            if datetime.datetime.fromisoformat(expires) > now:
                valid[token] = expires
        except (ValueError, TypeError):
            continue
    return valid

def create_admin_session():
    """Sinh token mới, lưu vào CSDL và trả về để ghi xuống cookie."""
    tokens = _load_admin_tokens()
    token = secrets.token_urlsafe(32)
    expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=ADMIN_SESSION_DAYS)
    tokens[token] = expires.isoformat()
    db.save_settings({ADMIN_TOKENS_KEY: json.dumps(tokens)})
    return token

def revoke_admin_session(token):
    """Xóa token khỏi CSDL khi đăng xuất (thiết bị khác vẫn giữ phiên riêng)."""
    tokens = _load_admin_tokens()
    if token and token in tokens:
        tokens.pop(token)
        db.save_settings({ADMIN_TOKENS_KEY: json.dumps(tokens)})

def write_admin_cookie(token):
    """Ghi cookie bằng JS. Streamlit không có API ghi cookie phía server."""
    max_age = ADMIN_SESSION_DAYS * 24 * 3600
    js = (
        "<script>"
        f"var v='{ADMIN_COOKIE_NAME}={token}; path=/; max-age={max_age}; SameSite=Lax'"
        "+(location.protocol==='https:'?'; Secure':'');"
        "try{window.parent.document.cookie=v;}catch(e){document.cookie=v;}"
        "</script>"
    )
    st.components.v1.html(js, height=0)

def clear_admin_cookie():
    js = (
        "<script>"
        f"var v='{ADMIN_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax';"
        "try{window.parent.document.cookie=v;}catch(e){document.cookie=v;}"
        "</script>"
    )
    st.components.v1.html(js, height=0)

def login_admin():
    """Đánh dấu đã đăng nhập trong phiên hiện tại và ghi nhớ sang các tab/lần sau."""
    st.session_state["is_admin"] = True
    token = create_admin_session()
    st.session_state["admin_token"] = token
    st.session_state["pending_admin_cookie"] = token

def logout_admin():
    revoke_admin_session(st.session_state.get("admin_token"))
    st.session_state["is_admin"] = False
    st.session_state.pop("admin_token", None)
    st.session_state["pending_admin_cookie_clear"] = True

def restore_admin_session():
    """Khôi phục đăng nhập từ cookie khi mở tab mới hoặc tải lại trang."""
    if st.session_state.get("is_admin"):
        return
    try:
        token = st.context.cookies.get(ADMIN_COOKIE_NAME)
    except Exception:
        return
    if token and token in _load_admin_tokens():
        st.session_state["is_admin"] = True
        st.session_state["admin_token"] = token

def apply_pending_admin_cookie():
    """Ghi/xóa cookie sau khi rerun (phải gọi ở nhánh giao diện đang hiển thị)."""
    token = st.session_state.pop("pending_admin_cookie", None)
    if token:
        write_admin_cookie(token)
    if st.session_state.pop("pending_admin_cookie_clear", False):
        clear_admin_cookie()

# -----------------
# Đường dẫn logo (đặt file logo.png vào thư mục static/ cạnh app.py)
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")
# Favicon: logo chữ G chung với HUB (đen) / GreeFastAPI (đỏ), NamGree dùng màu tím để dễ phân biệt tab
FAVICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "favicon.png")

# Thiết lập cấu hình trang
st.set_page_config(
    page_title=Config.APP_NAME,
    page_icon=FAVICON_PATH if os.path.exists(FAVICON_PATH) else "🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS để giao diện chuyên nghiệp hơn theo brand leducnam.com
# Danh sách trạng thái chuẩn
STATUS_LIST = ["Mới tạo", "Đã tiếp nhận", "Đang xử lý", "Chờ xử lý", "Hoàn thành", "Từ chối"]
STATUS_COLORS = {
    "Mới tạo": "#3B82F6",       # Xanh dương
    "Đã tiếp nhận": "#8B5CF6",  # Tím
    "Đang xử lý": "#F59E0B",    # Vàng cam
    "Chờ xử lý": "#EF4444",     # Đỏ
    "Hoàn thành": "#10B981",     # Xanh lá
    "Từ chối": "#6B7280",       # Xám
}

# Nhóm ghi chú công việc = 4 dòng trong bảng báo cáo tuần của file mẫu công ty
# key: mã nhóm (trùng "domain" của FORM_CONFIGS) → (tên hiển thị, chữ để tìm dòng trong file mẫu)
WORK_NOTE_CATEGORIES = {
    "erp": ("ERP", "ERP"),
    "warranty": ("Hệ thống Bảo hành", "HỆ THỐNG BẢO HÀNH"),
    "gree_app": ("Gree App", "GREE APP"),
    "it": ("IT cơ bản", "CÔNG VIỆC IT CƠ BẢN"),
}
WORK_NOTE_LABELS = {key: label for key, (label, _) in WORK_NOTE_CATEGORIES.items()}

# Theo dõi ticket bên ngoài (AEGONA...) theo trạng thái — thứ tự dùng để sắp xếp bảng
TRACKING_STATUSES = ["Mới", "Chờ đề xuất", "Đang thực hiện", "Đang testing", "Chờ deploy", "Chờ cập nhật", "Đã lên Production", "Đóng", "Hủy"]
# Mục đã đóng chỉ vào báo cáo tuần nếu đổi trạng thái trong tuần đó
TRACKING_CLOSED = {"Đóng", "Hủy"}
TRACKING_PRIORITIES = ["Cao", "Trung bình", "Thấp"]
# Hợp đồng bảo trì AEGONA: hạn mức giờ/tháng (sheet Overview của file báo cáo) và quy đổi MD (man-day)
# Gói bảo trì 1 năm: 288 giờ, ký 14/07/2026 (hết hạn 13/07/2027), chia đều 12 tháng T7/2026 → T6/2027 = 24 giờ/tháng
AGN_PACKAGE_HOURS = 288
AGN_CONTRACT_SIGNED = datetime.date(2026, 7, 14)
AGN_CONTRACT_MONTHS = 12
AGN_MONTHLY_QUOTA_HOURS = AGN_PACKAGE_HOURS // AGN_CONTRACT_MONTHS
HOURS_PER_MD = 8

# Trạng thái coi như đã đóng — dùng để đẩy ticket chưa xong lên đầu danh sách
CLOSED_STATUSES = {"Hoàn thành", "Từ chối"}

def status_badge(status_text):
    color = STATUS_COLORS.get(status_text, "#6B7280")
    return f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.85em;font-weight:600;">{status_text}</span>'

def sort_tickets_for_display(tickets):
    """Sắp xếp danh sách ticket để hiển thị: ticket chưa hoàn thành lên trên,
    trong mỗi nhóm thì mới nhất trước."""
    def sort_key(t):
        created = t.get("created_at")
        timestamp = created.timestamp() if isinstance(created, datetime.datetime) else 0
        return (t.get("status") in CLOSED_STATUSES, -timestamp)
    return sorted(tickets, key=sort_key)

def days_open(ticket):
    """Số ngày ticket đã mở (tính tới lúc đóng nếu đã đóng). created_at/closed_at lưu theo giờ UTC của DB."""
    created = ticket.get("created_at")
    if not isinstance(created, datetime.datetime):
        return None
    end = ticket.get("closed_at") or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    return max((end - created).days, 0)

# Ticket chưa đóng mở quá số ngày này thì đánh dấu đỏ
AGING_WARN_DAYS = 3

def aging_label(ticket):
    d = days_open(ticket)
    if d is None:
        return "—"
    if ticket.get("status") not in CLOSED_STATUSES and d >= AGING_WARN_DAYS:
        return f"🔴 {d} ngày"
    return f"{d} ngày"

# Bảng dữ liệu không tô màu được như badge → dùng chấm màu tương ứng STATUS_COLORS
STATUS_ICONS = {
    "Mới tạo": "🔵", "Đã tiếp nhận": "🟣", "Đang xử lý": "🟠",
    "Chờ xử lý": "🔴", "Hoàn thành": "🟢", "Từ chối": "⚪",
}

def ticket_table_rows(tickets):
    return [
        {
            "Mã Ticket": t["id"],
            "Trạng thái": f"{STATUS_ICONS.get(t['status'], '⚪')} {t['status']}",
            "Người y/c": t.get("requester") or "—",
            "Tiêu đề": t.get("subject") or "—",
            "Ngày tạo": format_ticket_date(t.get("created_at")),
            "Đã mở": aging_label(t),
        }
        for t in tickets
    ]

def render_ticket_messages(msgs, show_internal):
    """Vẽ chat-log của ticket. Dòng đổi trạng thái (type='status') hiện gọn 1 dòng."""
    for m in msgs:
        if m['type'] == "internal" and not show_internal:
            continue
        when = f"{m.get('date', '')} • {m.get('time', '')}"
        if m['type'] == "status":
            st.caption(f"🔄 {m['msg']} — {m['user']} • {when}")
            continue
        is_admin_msg = m['user'].startswith("Admin")
        with st.chat_message("assistant" if is_admin_msg else "user"):
            label = "🔒 Nội bộ" if m['type'] == "internal" else "🌐 Công khai"
            st.write(f"**{m['user']}** ({label})")
            st.write(m['msg'])
            st.caption(when)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .stAppHeader .stToolbarActions {display:none;}
</style>
""", unsafe_allow_html=True)

# Lấy dữ liệu từ database
db_tickets = db.get_all_tickets()
db_tasks = db.get_tasks()

# Khôi phục đăng nhập Admin từ cookie (mở tab mới / tải lại trang không phải đăng nhập lại)
restore_admin_session()
# Ghi/xóa cookie sau khi vừa đăng nhập hoặc đăng xuất (đặt ở đây để áp dụng cho
# cả giao diện đầy đủ lẫn giao diện xem qua link chia sẻ)
apply_pending_admin_cookie()

# -----------------
# XỬ LÝ DEEP LINKING (URL Query Parameters)
# -----------------
url_ticket_id = st.query_params.get("ticket")
if url_ticket_id and st.session_state.get("view_mode") != "full":
    st.session_state["view_mode"] = "only"
    st.session_state["active_ticket_id"] = url_ticket_id

FORM_CONFIGS = [
    {
        "label": "Form 1: Khai báo Model phân loại chi phí bảo hành",
        "type": "Khai_Bao_Model_Bao_Hanh",
        "title": "Danh sách Model đã cập nhật hệ thống",
        "report_fields": ["model_name"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Tên model", "model_name"),
            ("Loại chi phí", "cost_type"),
            ("Công suất", "capacity_range"),
            ("Loại sản phẩm", "product_type"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
            ("Ghi chú", "note"),
        ],
    },
    {
        "label": "Form 2: Khai báo mã linh kiện mới",
        "type": "Khai_Bao_Ma_Linh_Kien",
        "title": "Danh sách mã linh kiện đã cập nhật hệ thống",
        "report_fields": ["part_code", "part_name_vi"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Mã linh kiện", "part_code"),
            ("Tên linh kiện (EN)", "part_name_en"),
            ("Tên linh kiện (VI)", "part_name_vi"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
            ("Mô tả", "description"),
        ],
    },
    {
        "label": "Form 3: Yêu cầu điều chỉnh tồn kho hệ thống",
        "type": "Yeu_Cau_Dieu_Chinh_Ton_Kho",
        "title": "Danh sách yêu cầu điều chỉnh tồn kho",
        "report_fields": ["note", "warehouse"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Kho/Trạm", "warehouse"),
            ("Mã linh kiện", "part_code"),
            ("Tính chất LK", "part_nature"),
            ("Phiếu xuất", "export_voucher"),
            ("SL điều chỉnh", "adjusted_quantity"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
            ("Ghi chú", "note"),
        ],
    },
    {
        "label": "Form 4: Đăng ký thông tin trạm bảo hành mới",
        "type": "Dang_Ky_Tram_Bao_Hanh_Moi",
        "title": "Danh sách trạm bảo hành đăng ký mới",
        "report_fields": ["company_info.name"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Tên công ty", "company_info.name"),
            ("Mã số thuế", "company_info.tax_code"),
            ("Email", "company_info.email"),
            ("Điện thoại", "company_info.phone"),
            ("User hệ thống", "company_info.system_username"),
            ("Số KTV", "technicians"),
            ("Số kho", "associated_warehouses"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "Form 5: Đăng ký tài khoản user nội bộ Gree",
        "type": "Dang_Ky_Tai_Khoan_User_Noi_Bo",
        "title": "Danh sách tài khoản user nội bộ đăng ký mới",
        "report_fields": ["full_name", "user_group"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Họ tên", "full_name"),
            ("Điện thoại", "phone"),
            ("Email Gree", "company_email"),
            ("Nhóm user", "user_group"),
            ("Line Call Center", "call_center_line"),
            ("Link chính", "main_link"),
            ("Username test", "test_account.username"),
            ("Password test", "test_account.password"),
            ("Link test", "test_account.test_link"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "Form 6: Khai báo Model cho Import Hồ sơ máy",
        "type": "Khai_Bao_Model_Ho_So_May",
        "title": "Danh sách Model hồ sơ máy đã cập nhật hệ thống",
        "report_fields": ["model_name"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Tên model", "model_name"),
            ("Loại máy", "machine_type"),
            ("BH Máy (tháng)", "warranty_months_machine"),
            ("BH Block (tháng)", "warranty_months_compressor"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "Form 7: Admin ghi nhận nội dung hỗ trợ (Admin Logs)",
        "type": "Admin_Web_Noted_Log_Ho_Tro",
        "title": "Danh sách log hỗ trợ Admin Web",
        "report_fields": ["request_detail"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Mã ca", "case_code"),
            ("Người xử lý IT", "it_assignee"),
            ("Ngày hoàn thành", "completion_date"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
            ("Nội dung yêu cầu", "request_detail"),
            ("Log xử lý nội bộ", "internal_action_log"),
        ],
    },
    {
        "label": "Form 8: Import bảng giá linh kiện",
        "type": "Import_Bang_Gia_Linh_Kien",
        "title": "Danh sách giá linh kiện đã cập nhật hệ thống",
        "report_fields": ["part_code", "part_name_vi"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Mã linh kiện", "part_code"),
            ("Tên linh kiện (VI)", "part_name_vi"),
            ("Nhóm Model", "model_group"),
            ("Loại sản phẩm", "product_type"),
            ("Giá có VAT", "price_vat"),
            ("Giá chưa VAT", "price_no_vat"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "Form 9: Khai báo danh mục chi phí",
        "type": "Khai_Bao_Danh_Muc_Chi_Phi",
        "title": "Danh sách danh mục chi phí đã cập nhật hệ thống",
        "report_fields": ["content"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Mã chi phí", "cost_code"),
            ("Nội dung", "content"),
            ("Đơn giá", "unit_price"),
            ("Công suất", "capacity"),
            ("Loại chi phí", "cost_type"),
            ("Nhóm sản phẩm", "product_group"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "Form 10: Yêu cầu tổng hợp (Khác)",
        "type": "Yeu_Cau_Tong_Hop_Khac",
        "title": "Danh sách yêu cầu tổng hợp / không thuộc 9 Form trên",
        "report_fields": ["request_detail"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Tiêu đề yêu cầu", "subject"),
            ("Liên quan Form", "related_form"),
            ("Nội dung yêu cầu", "request_detail"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "ERP-1: Yêu cầu hỗ trợ ERP (Tổng hợp)",
        "type": "ERP_Yeu_Cau_Tong_Hop",
        "title": "Danh sách yêu cầu hỗ trợ ERP",
        "domain": "erp",
        "report_fields": ["request_detail"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Tiêu đề yêu cầu", "subject"),
            ("Loại yêu cầu", "request_category"),
            ("Nội dung yêu cầu", "request_detail"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
    {
        "label": "GreeApp-1: Yêu cầu hỗ trợ Gree App (Tổng hợp)",
        "type": "GreeApp_Yeu_Cau_Tong_Hop",
        "title": "Danh sách yêu cầu hỗ trợ Gree App",
        "domain": "gree_app",
        "report_fields": ["original_ref", "request_detail"],
        "columns": [
            ("Mã Ticket", "id"),
            ("Tiêu đề yêu cầu", "subject"),
            ("Loại yêu cầu", "request_category"),
            ("Mã/Tham chiếu gốc (email)", "original_ref"),
            ("Nội dung yêu cầu", "request_detail"),
            ("Ngày y/c", "created_at"),
            ("Người y/c", "requester"),
            ("Trạng thái", "status"),
        ],
    },
]

# Các form từ Bảo hành (Form 1-10) chưa có "domain" khai báo riêng -> gán mặc định "warranty"
for _f in FORM_CONFIGS:
    _f.setdefault("domain", "warranty")

# Form nào dùng cấu trúc "tổng hợp" (tiêu đề + loại liên quan + nội dung yêu cầu)
GENERAL_FORM_TYPES = {"Yeu_Cau_Tong_Hop_Khac", "ERP_Yeu_Cau_Tong_Hop", "GreeApp_Yeu_Cau_Tong_Hop"}

FORM_LABEL_TO_TYPE = {f["label"]: f["type"] for f in FORM_CONFIGS}
FORM_TYPE_TO_CONFIG = {f["type"]: f for f in FORM_CONFIGS}

# domain -> (tên trang trong sidebar, state_key dùng để cô lập session_state/widget key)
DOMAIN_TO_PAGE = {
    "warranty": ("🛡️ Hệ thống Bảo hành", "bh"),
    "erp": ("🏭 Quản trị ERP", "erp"),
    "gree_app": ("📱 Gree App Support", "greeapp"),
}
LEGACY_FORM_TYPES = {
    f["label"]: f["type"] for f in FORM_CONFIGS
}

def normalize_form_type(form_type):
    return LEGACY_FORM_TYPES.get(form_type, form_type)

def goto_ticket_detail(ticket):
    """Điều hướng sang trang domain tương ứng và mở sẵn chi tiết ticket.
    Các key active_ticket_id/ticket_form_scope được cô lập theo state_key của từng trang."""
    disp_config = FORM_TYPE_TO_CONFIG.get(normalize_form_type(ticket.get("form_type")))
    domain = disp_config.get("domain", "warranty") if disp_config else "warranty"
    target_page, target_state_key = DOMAIN_TO_PAGE.get(domain, DOMAIN_TO_PAGE["warranty"])

    st.session_state["view_mode"] = "full"
    # Không gán thẳng "selected_page" (key của st.radio): Streamlit cấm sửa session_state
    # của widget sau khi widget đã render trong cùng 1 lần chạy. Hoãn lại và áp dụng ở
    # lần chạy kế tiếp, trước khi radio được tạo.
    st.session_state["_pending_page"] = target_page
    st.session_state[f"active_ticket_id_{target_state_key}"] = ticket["id"]
    if disp_config:
        st.session_state[f"ticket_form_scope_{target_state_key}"] = disp_config["label"]
    # Bỏ lọc trạng thái để ticket chắc chắn nằm trong danh sách hiển thị
    st.session_state[f"ticket_filter_{target_state_key}"] = "Tất cả"

# Nhãn tiếng Việt cho các field không nằm trong "columns" của Form (hoặc field lồng nhau)
FIELD_LABELS = {
    "request_title": "Tiêu đề yêu cầu",
    "request_detail": "Nội dung yêu cầu",
    "request_category": "Loại yêu cầu",
    "related_form": "Liên quan Form",
    "original_ref": "Tham chiếu gốc",
    "internal_action_log": "Log xử lý nội bộ",
    "note": "Ghi chú",
    "description": "Mô tả",
    "model_name": "Tên Model",
    "model_group": "Nhóm Model",
    "machine_type": "Loại máy",
    "cost_type": "Loại chi phí",
    "cost_code": "Mã chi phí",
    "product_type": "Loại sản phẩm",
    "product_group": "Nhóm sản phẩm",
    "capacity": "Công suất",
    "capacity_range": "Công suất",
    "unit_type": "Loại Unit",
    "unit_price": "Đơn giá",
    "price_vat": "Giá có VAT",
    "price_no_vat": "Giá chưa VAT",
    "classification": "Phân loại",
    "discount_rate": "Tỷ lệ chiết khấu (%)",
    "sla_bonus_rate": "Thưởng SLA (%)",
    "part_code": "Mã linh kiện",
    "part_name_vi": "Tên linh kiện (VI)",
    "part_name_en": "Tên linh kiện (EN)",
    "part_nature": "Tính chất linh kiện",
    "warehouse": "Kho/Trạm",
    "export_voucher": "Phiếu xuất",
    "adjusted_quantity": "Số lượng điều chỉnh",
    "evidence_image_url": "Link ảnh bằng chứng",
    "evidence_link": "Link bằng chứng",
    "case_code": "Mã ca / Mã chứng từ",
    "it_assignee": "Người xử lý IT",
    "completion_date": "Ngày hoàn thành",
    "warranty_months_machine": "T/g BH Máy (Tháng)",
    "warranty_months_compressor": "T/g BH Block (Tháng)",
    "full_name": "Họ tên",
    "phone": "Điện thoại",
    "company_email": "Email Gree",
    "user_group": "Nhóm user",
    "call_center_line": "Line Call Center",
    "main_link": "Link chính",
    "test_account": "Tài khoản test",
    "username": "Username",
    "password": "Password",
    "test_link": "Link test",
    "company_info": "Thông tin công ty",
    "technicians": "Danh sách KTV",
    "associated_warehouses": "Danh sách kho liên kết",
    "name": "Tên",
    "type": "Loại",
    "email": "Email",
    "tax_code": "Mã số thuế",
    "tax_address": "Địa chỉ thuế",
    "postal_address": "Địa chỉ nhận thư",
    "system_username": "User hệ thống",
    "bank_account": "Số tài khoản",
    "bank_account_name": "Tên tài khoản ngân hàng",
    "bank_name": "Ngân hàng",
    "content": "Nội dung",
    "subject": "Tiêu đề",
}

def build_field_label_map(config):
    """Gộp nhãn từ cấu hình 'columns' của Form với bảng nhãn mặc định."""
    labels = dict(FIELD_LABELS)
    if config:
        for label, key in config.get("columns", []):
            labels[key] = label
    return labels

def field_label(key, labels):
    return labels.get(key) or key.replace("_", " ").capitalize()

def is_empty_value(value):
    return value is None or (isinstance(value, str) and not value.strip()) or value == []

def render_form_data_view(form_data, labels, level=0):
    """Hiển thị form_data dạng dễ đọc: nhãn tiếng Việt + nội dung giữ nguyên xuống dòng.
    Thay cho st.json() vốn hiển thị JSON thô, key tiếng Anh và \\n khó đọc."""
    for key, value in form_data.items():
        if is_empty_value(value):
            continue  # bỏ qua field trống cho gọn khi dữ liệu nhiều
        label = field_label(key, labels)

        if isinstance(value, dict):
            st.markdown(f"{'#' * min(level + 5, 6)} {label}")
            render_form_data_view(value, labels, level + 1)
        elif isinstance(value, list):
            # Nhãn trong "columns" mô tả cột tổng hợp (vd "Số KTV" = đếm số dòng),
            # không hợp để đặt trên bảng liệt kê -> ưu tiên nhãn mặc định.
            st.markdown(f"**{FIELD_LABELS.get(key, label)}**")
            if all(isinstance(x, dict) for x in value):
                # Danh sách bản ghi (KTV, kho...) -> bảng, đổi key sang nhãn tiếng Việt
                rows = [{field_label(k, labels): v for k, v in item.items()} for item in value]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                for item in value:
                    st.markdown(f"- {item}")
        elif isinstance(value, bool):
            st.markdown(f"**{label}:** {'✅ Có' if value else '❌ Không'}")
        elif isinstance(value, str) and ("\n" in value or len(value) > 80):
            # Nội dung dài/nhiều dòng -> khối riêng, giữ nguyên ngắt dòng
            st.markdown(f"**{label}**")
            with st.container(border=True):
                st.markdown(value.replace("\n", "  \n"))
        else:
            st.markdown(f"**{label}:** {value}")

def render_form_data_editor(form_data, key_prefix):
    """Hiển thị từng field của form_data bằng input riêng (thay vì 1 ô JSON thô)
    để tránh việc xuống dòng trong nội dung bị hiển thị dưới dạng ký tự \\n khi sửa."""
    updated = {}
    for key, value in form_data.items():
        widget_key = f"{key_prefix}_{key}"
        if isinstance(value, dict):
            st.caption(f"**{key}**")
            updated[key] = render_form_data_editor(value, widget_key)
        elif isinstance(value, bool):
            updated[key] = st.checkbox(key, value=value, key=widget_key)
        elif isinstance(value, (int, float)):
            updated[key] = st.number_input(key, value=value, key=widget_key)
        elif isinstance(value, str) and ("\n" in value or len(value) > 60):
            updated[key] = st.text_area(key, value=value, key=widget_key, height=100)
        else:
            updated[key] = st.text_input(key, value="" if value is None else str(value), key=widget_key)
    return updated


def parse_form_data(ticket):
    f_json = ticket.get("form_data", {})
    if isinstance(f_json, str):
        try:
            return json.loads(f_json)
        except Exception:
            return {}
    return f_json or {}

def tickets_for_form(tickets, form_type):
    return [t for t in tickets if normalize_form_type(t.get("form_type")) == form_type]

def format_ticket_date(value):
    if isinstance(value, datetime.datetime):
        return value.strftime("%d/%m/%Y")
    return value or ""

def to_date(value):
    """Chuẩn hóa 1 giá trị (datetime/date/string) về kiểu date để so sánh theo tuần."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value.strip():
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None

def month_first_monday(year, month):
    """Thứ 2 của tuần làm việc chứa ngày 1 của tháng (có thể rơi vào cuối tháng trước)."""
    first_of_month = datetime.date(year, month, 1)
    return first_of_month - datetime.timedelta(days=first_of_month.weekday())

def week_of_month(d):
    """Số thứ tự tuần làm việc (Thứ 2 → Thứ 7) chứa ngày d, đánh số theo tháng của d.
    Tuần 1 = tuần chứa ngày 1 của tháng."""
    monday0 = month_first_monday(d.year, d.month)
    return (d - monday0).days // 7 + 1

def max_weeks_in_month(year, month):
    last_day = calendar.monthrange(year, month)[1]
    return week_of_month(datetime.date(year, month, last_day))

def week_date_range(year, month, week_no):
    """Trả về (Thứ 2, Thứ 7) của tuần làm việc thứ week_no trong tháng được chọn."""
    monday0 = month_first_monday(year, month)
    monday = monday0 + datetime.timedelta(days=7 * (week_no - 1))
    saturday = monday + datetime.timedelta(days=5)
    return monday, saturday

def build_report_context(year, month, week, reporter, tickets, tasks, notes=(), issues="", tracking=(), tracking_logs=()):
    """Dựng toàn bộ dữ liệu báo cáo tuần. Tách riêng khỏi UI để cả trang Báo cáo lẫn
    chức năng gửi email tự động đều dùng chung một nguồn số liệu."""
    start_date, end_date = week_date_range(year, month, week)

    # Ticket được TẠO trong tuần
    week_new_tickets = [
        t for t in tickets
        if to_date(t.get('created_at')) and start_date <= to_date(t.get('created_at')) <= end_date
    ]
    # Công việc HOÀN THÀNH trong tuần (theo tasks.created_at = thời điểm đánh dấu Hoàn thành)
    week_completed_tasks = [
        task for task in tasks
        if to_date(task.get('created_at')) and start_date <= to_date(task.get('created_at')) <= end_date
    ]
    tickets_by_id = {t['id']: t for t in tickets}
    # Ghi chú công việc ngoài ticket, theo ngày ghi chú
    week_notes = [
        n for n in notes
        if to_date(n.get('note_date')) and start_date <= to_date(n.get('note_date')) <= end_date
    ]
    week_tracking = build_week_tracking(tracking, tracking_logs, start_date, end_date)

    summary_rows = []
    for cfg in FORM_CONFIGS:
        cnt = len([t for t in week_new_tickets if normalize_form_type(t.get('form_type')) == cfg['type']])
        if cnt:
            summary_rows.append({"Form": cfg['label'], "Số lượng": cnt})

    completed_rows = []
    for task in week_completed_tasks:
        ref_ticket = tickets_by_id.get(task.get('ticket_id'))
        if ref_ticket:
            f_type = normalize_form_type(ref_ticket.get('form_type'))
            f_label = FORM_TYPE_TO_CONFIG.get(f_type, {}).get('label', f_type or '—')
            completed_rows.append({
                "id": ref_ticket.get("id", ""),
                "form_label": f_label,
                "requester": ref_ticket.get("requester", ""),
                "subject": ref_ticket.get("subject", task.get("content", "")),
            })
        else:
            # Log cũ chưa có ticket_id (ghi trước khi nâng cấp), hoặc ticket gốc đã bị xóa
            completed_rows.append({
                "id": "—", "form_label": "—", "requester": "—",
                "subject": task.get("content", task.get("action", "")),
            })

    # Ticket "liên quan tuần này" = tạo mới trong tuần ∪ hoàn thành trong tuần (dù tạo trước đó)
    week_relevant_ticket_ids = set(t['id'] for t in week_new_tickets)
    for task in week_completed_tasks:
        if task.get('ticket_id'):
            week_relevant_ticket_ids.add(task['ticket_id'])
    week_relevant_tickets = [t for t in tickets if t['id'] in week_relevant_ticket_ids]

    return {
        "year": year, "month": month, "week": week,
        "reporter": reporter, "start_date": start_date, "end_date": end_date,
        "metrics": [
            ("Ticket mới trong tuần", len(week_new_tickets)),
            ("Hoàn thành trong tuần", len(week_completed_tasks)),
            ("Đang xử lý/Chờ xử lý", len([t for t in week_new_tickets if t['status'] in ['Đang xử lý', 'Chờ xử lý']])),
            ("Từ chối", len([t for t in week_new_tickets if t['status'] == 'Từ chối'])),
        ],
        "summary_rows": summary_rows,
        "completed_rows": completed_rows,
        "week_notes": week_notes,
        "week_tracking": week_tracking,
        "tracking": list(tracking),
        "issues": issues,
        "week_relevant_tickets": week_relevant_tickets,
        "week_new_tickets": week_new_tickets,
        "week_completed_tasks": week_completed_tasks,
    }

def build_week_tracking(tracking, tracking_logs, start_date, end_date):
    """Mục theo dõi ticket đưa vào báo cáo tuần: còn mở (tạo trước cuối tuần) hoặc đổi trạng thái trong tuần.
    Mỗi mục kèm 'week_logs' (các lần đổi trạng thái trong tuần) và 'report_date' (ngày ghi ở đầu dòng)."""
    logs_by_item = {}
    for log in tracking_logs:
        if to_date(log.get('created_at')) and start_date <= to_date(log['created_at']) <= end_date:
            logs_by_item.setdefault(log['tracking_id'], []).append(log)
    result = []
    for item in tracking:
        week_logs = logs_by_item.get(item['id'], [])
        created = to_date(item.get('created_at'))
        if not week_logs and (item.get('status') in TRACKING_CLOSED or (created and created > end_date)):
            continue
        report_date = to_date(week_logs[-1]['created_at']) if week_logs else to_date(item.get('status_changed_at'))
        result.append(dict(item, week_logs=week_logs, report_date=report_date))
    status_rank = {s: i for i, s in enumerate(TRACKING_STATUSES)}
    result.sort(key=lambda x: (status_rank.get(x.get('status'), 99), x.get('report_date') or datetime.date.min))
    return result

# -----------------
# GỬI EMAIL BÁO CÁO TUẦN
# -----------------
# Streamlit Cloud chạy theo giờ UTC, còn giờ người dùng nhập là giờ Việt Nam (UTC+7)
# -> luôn quy đổi về VN trước khi so sánh lịch, nếu không sẽ lệch 7 tiếng.
VN_TZ = datetime.timezone(datetime.timedelta(hours=7))
WEEKDAY_LABELS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]

def now_vn():
    return datetime.datetime.now(VN_TZ)

def week_tag(d):
    """Định danh tuần (ISO) dùng để chống gửi trùng trong cùng một tuần."""
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

def smtp_config_from_settings(settings):
    return {
        "host": settings.get("smtp_host", ""),
        "port": settings.get("smtp_port", "587"),
        "user": settings.get("smtp_user", ""),
        "password": settings.get("smtp_password", ""),
        "sender": settings.get("smtp_sender", ""),
        "sender_name": settings.get("smtp_sender_name", ""),
        "security": settings.get("smtp_security", "STARTTLS"),
    }

# Khoảng chờ tối thiểu giữa 2 lần thử gửi khi lần trước thất bại. Nếu không có, cấu hình SMTP
# sai sẽ khiến MỌI lần tải trang đều treo chờ timeout SMTP.
EMAIL_RETRY_COOLDOWN = datetime.timedelta(minutes=30)

def weekly_email_due(settings, now=None):
    """Đã tới giờ gửi báo cáo tuần và tuần này chưa gửi?"""
    if settings.get("report_email_enabled") != "1":
        return False
    now = now or now_vn()
    if settings.get("report_email_last_week") == week_tag(now.date()):
        return False  # tuần này đã gửi rồi

    # Vừa thử gửi và thất bại -> chờ hết cooldown mới thử lại
    last_attempt = settings.get("report_email_last_attempt_at")
    if last_attempt:
        try:
            attempted_at = datetime.datetime.fromisoformat(last_attempt)
            if now - attempted_at < EMAIL_RETRY_COOLDOWN:
                return False
        except ValueError:
            pass

    try:
        target_weekday = int(settings.get("report_email_weekday", "5"))
        hh, mm = (settings.get("report_email_time") or "17:00").split(":")
        target_time = datetime.time(int(hh), int(mm))
    except (ValueError, TypeError):
        return False

    # Mốc gửi của tuần hiện tại (theo giờ VN)
    monday = now.date() - datetime.timedelta(days=now.weekday())
    scheduled = datetime.datetime.combine(
        monday + datetime.timedelta(days=target_weekday), target_time, tzinfo=VN_TZ
    )
    return now >= scheduled

def send_weekly_report_email(settings, tickets, tasks, target_date=None, mark_sent=True):
    """Gửi báo cáo tuần và ghi nhật ký (report_email_logs) dù thành công hay lỗi. Trả về (thành công, thông báo)."""
    target_date = target_date or now_vn().date()
    ok, msg = _send_weekly_report_email(settings, tickets, tasks, target_date, mark_sent)
    recipients = ", ".join(mailer.parse_recipients(settings.get("report_email_to")))
    cc = ", ".join(mailer.parse_recipients(settings.get("report_email_cc")))
    db.add_report_email_log(
        target_date, "auto" if mark_sent else "manual", "sent" if ok else "failed",
        recipients + (f" (CC: {cc})" if cc else ""), msg,
    )
    return ok, msg

def report_email_status(settings, logs, start_date, end_date, now=None):
    """Tình trạng gửi email của tuần [start_date, end_date] → (kiểu hiển thị, nội dung).
    kiểu: success | error | warning | info (tên hàm st.* tương ứng)."""
    week_logs = [l for l in logs if start_date <= to_date(l["target_date"]) <= end_date]
    sent = [l for l in week_logs if l["status"] == "sent"]
    if sent:
        last = sent[0]
        kind = "tự động" if last["trigger_type"] == "auto" else "gửi tay"
        to = f" tới {last['recipients']}" if last.get("recipients") else ""
        more = f" (đã gửi {len(sent)} lần)" if len(sent) > 1 else ""
        return "success", f"✅ **Đã gửi** ({kind}) lúc {last['created_at'].strftime('%H:%M %d/%m/%Y')}{to}{more}"
    if week_logs:
        last = week_logs[0]
        return "error", (f"❌ **Gửi lỗi** lúc {last['created_at'].strftime('%H:%M %d/%m/%Y')} "
                         f"({len(week_logs)} lần thử): {last.get('message') or ''}")
    now = now or now_vn()
    if settings.get("report_email_enabled") != "1":
        return "info", "⏸️ **Chưa gửi** — đang tắt gửi tự động (bật ở ⚙️ Cài đặt → Lịch gửi báo cáo tuần)."
    try:
        weekday = int(settings.get("report_email_weekday", "5"))
        schedule = f"{WEEKDAY_LABELS[weekday]} {settings.get('report_email_time') or '17:00'}"
    except (ValueError, IndexError):
        schedule = "(lịch chưa hợp lệ)"
    if end_date < now.date():
        return "warning", f"⚠️ **Chưa gửi** — tuần đã qua mà không có lần gửi nào (lịch: {schedule})."
    if weekly_email_due(settings, now):
        return "warning", f"⏳ **Chưa gửi** — đã quá giờ hẹn ({schedule}), sẽ gửi ở lần mở app kế tiếp."
    return "info", f"🕒 **Chưa gửi** — lịch gửi tự động: {schedule}."

def _send_weekly_report_email(settings, tickets, tasks, target_date, mark_sent):
    """Dựng báo cáo tuần theo mẫu công ty và gửi kèm email. Trả về (thành công, thông báo)."""
    if not DOCX_AVAILABLE:
        return False, "Chưa cài thư viện python-docx nên không tạo được file báo cáo."
    if not os.path.exists(TEMPLATE_PATH):
        return False, f"Không tìm thấy file mẫu công ty tại {TEMPLATE_PATH}."

    to_list = mailer.parse_recipients(settings.get("report_email_to"))
    cc_list = mailer.parse_recipients(settings.get("report_email_cc"))
    if not to_list:
        return False, "Chưa cấu hình người nhận (To)."

    year, month = target_date.year, target_date.month
    week = min(week_of_month(target_date), max_weeks_in_month(year, month))

    ctx = build_report_context(
        year, month, week,
        settings.get("report_email_reporter") or Config.OWNER,
        tickets, tasks, db.get_work_notes(),
        tracking=db.get_ticket_tracking(), tracking_logs=db.get_ticket_tracking_logs(),
    )

    try:
        buffer = generate_weekly_report_from_template(TEMPLATE_PATH, ctx)
    except Exception as e:
        return False, f"Lỗi khi tạo file báo cáo từ mẫu: {e}"

    filename = f"NAMLE - BC-TUAN {week:02d} THANG {month:02d}.docx"
    attachments = []
    pdf_note = ""
    try:
        pdf_bytes = build_agn_pdf_bytes(ctx["tracking"])
        if pdf_bytes:
            attachments.append((pdf_bytes, f"NAMLE - BAO CAO AEGONA - TUAN {week:02d} THANG {month:02d}.pdf", mailer.PDF_MIME))
    except Exception as e:  # PDF lỗi vẫn gửi file Word, ghi chú lại trong email
        pdf_note = f"\n(Không tạo được file PDF AEGONA: {e})\n"
    period = f"{ctx['start_date'].strftime('%d/%m/%Y')} - {ctx['end_date'].strftime('%d/%m/%Y')}"
    subject = f"[Gree IT] Báo cáo tuần {week:02d}/tháng {month:02d}/{year} - {ctx['reporter']}"
    body = (
        f"Kính gửi Anh/Chị,\n\n"
        f"Báo cáo công việc tuần {week} tháng {month}/{year} ({period}) được đính kèm trong email này:\n"
        f"- {filename}: báo cáo công việc tuần theo mẫu công ty\n"
        + (f"- {attachments[0][1]}: báo cáo gói bảo trì AEGONA (ticket chưa triển khai, đã triển khai, giờ theo tháng)\n"
           if attachments else "")
        + pdf_note + "\n"
        f"Người báo cáo: {ctx['reporter']}\n\n"
        f"(Email được gửi tự động từ hệ thống {Config.APP_NAME}.)"
    )

    try:
        mailer.send_email(
            smtp_config_from_settings(settings), to_list, cc_list,
            subject, body, buffer.getvalue(), filename, attachments=attachments,
        )
    except Exception as e:
        db.save_settings({
            "report_email_last_error": f"{now_vn().strftime('%d/%m/%Y %H:%M')} - {e}",
        })
        return False, f"Gửi email thất bại: {e}"

    if mark_sent:
        db.save_settings({
            "report_email_last_week": week_tag(target_date),
            "report_email_last_sent_at": now_vn().strftime("%d/%m/%Y %H:%M"),
            "report_email_last_error": "",
        })
    return True, f"Đã gửi báo cáo tuần {week}/tháng {month} tới: {', '.join(to_list)}"

def get_form_value(data, key):
    value = data
    for part in key.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(part)
    if isinstance(value, list):
        return len(value)
    return value if value is not None else ""

def parse_pipe_rows(raw_text, fields):
    rows = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        row = {field: parts[idx] if idx < len(parts) else "" for idx, field in enumerate(fields)}
        rows.append(row)
    return rows

def missing_form5_required_fields(form_data):
    required_fields = {
        "Họ tên": form_data.get("full_name"),
        "Điện thoại": form_data.get("phone"),
        "Email Gree": form_data.get("company_email"),
        "Nhóm user": form_data.get("user_group"),
        "Link chính": form_data.get("main_link"),
        "Username test": form_data.get("test_account", {}).get("username"),
        "Password test": form_data.get("test_account", {}).get("password"),
        "Link test": form_data.get("test_account", {}).get("test_link"),
    }
    return [label for label, value in required_fields.items() if not str(value or "").strip()]

def build_form_rows(tickets, config):
    rows = []
    for t in tickets:
        f_json = parse_form_data(t)
        row = {}
        for label, key in config["columns"]:
            if key == "id":
                row[label] = t.get("id", "")
            elif key == "created_at":
                row[label] = format_ticket_date(t.get("created_at"))
            elif key == "requester":
                row[label] = t.get("requester", "")
            elif key == "status":
                row[label] = t.get("status", "Mới tạo")
            elif key == "subject":
                row[label] = t.get("subject", "")
            else:
                row[label] = get_form_value(f_json, key)
        rows.append(row)
    return rows

def generate_weekly_report_docx(ctx):
    """Tạo file Word (.docx) báo cáo tuần từ dữ liệu đã tổng hợp. Trả về buffer BytesIO."""
    doc = Document()
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(11)

    heading = doc.add_heading(
        f"BÁO CÁO CÔNG VIỆC TUẦN {ctx['week']} - THÁNG {ctx['month']}/{ctx['year']}",
        level=1
    )
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    p1 = doc.add_paragraph()
    p1.add_run("Người báo cáo: ").bold = True
    p1.add_run(ctx['reporter'])

    p2 = doc.add_paragraph()
    p2.add_run("Khoảng thời gian: ").bold = True
    p2.add_run(f"{ctx['start_date'].strftime('%d/%m/%Y')} - {ctx['end_date'].strftime('%d/%m/%Y')}")

    doc.add_heading("1. Tổng quan số liệu trong tuần", level=2)
    t1 = doc.add_table(rows=1, cols=2)
    t1.style = 'Light Grid Accent 1'
    t1.rows[0].cells[0].text = "Chỉ số"
    t1.rows[0].cells[1].text = "Số lượng"
    for label, value in ctx['metrics']:
        row = t1.add_row().cells
        row[0].text = label
        row[1].text = str(value)

    if ctx['summary_rows']:
        doc.add_heading("2. Ticket mới theo Form", level=2)
        t2 = doc.add_table(rows=1, cols=2)
        t2.style = 'Light Grid Accent 1'
        t2.rows[0].cells[0].text = "Form"
        t2.rows[0].cells[1].text = "Số lượng"
        for row_data in ctx['summary_rows']:
            r = t2.add_row().cells
            r[0].text = row_data["Form"]
            r[1].text = str(row_data["Số lượng"])

    doc.add_heading("3. Công việc đã hoàn thành trong tuần", level=2)
    if ctx['completed_rows']:
        t3 = doc.add_table(rows=1, cols=4)
        t3.style = 'Light Grid Accent 1'
        for i, label in enumerate(["Mã Ticket", "Loại Form", "Người y/c", "Nội dung"]):
            t3.rows[0].cells[i].text = label
        for row_data in ctx['completed_rows']:
            r = t3.add_row().cells
            r[0].text = row_data['id']
            r[1].text = row_data['form_label']
            r[2].text = row_data['requester']
            r[3].text = row_data['subject']
    else:
        doc.add_paragraph("Không có ticket nào hoàn thành trong tuần này.")

    doc.add_heading("4. Công việc khác (ghi chú công việc)", level=2)
    if not ctx['week_notes']:
        doc.add_paragraph("(Không có)")
    for category, label in WORK_NOTE_LABELS.items():
        note_lines = build_note_lines([n for n in ctx['week_notes'] if n.get('category') == category])
        if note_lines:
            doc.add_paragraph().add_run(f"{label}:").bold = True
            for text, bold in note_lines:
                add_report_runs(doc.add_paragraph(), text, bold)

    doc.add_heading("5. Theo dõi ticket (trạng thái)", level=2)
    tracking_lines = build_tracking_lines(ctx.get('week_tracking', []))
    if not tracking_lines:
        doc.add_paragraph("(Không có)")
    for text, bold in tracking_lines:
        add_report_runs(doc.add_paragraph(), text, bold)

    doc.add_heading("6. Vấn đề gặp phải / Lưu ý", level=2)
    doc.add_paragraph(ctx['issues'].strip() if ctx['issues'] else "(Không có)")

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# --- Xuất báo cáo theo ĐÚNG MẪU CÔNG TY (tìm & thay nội dung trong file .docx thật) ---

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "BaoCaoTuan_Template.docx")

def build_ticket_report_line(t, cfg):
    """Sinh 1 dòng mô tả ticket trong báo cáo: 'Mã – Nội dung (Người y/c) – Trạng thái.'"""
    f_json = parse_form_data(t)
    detail_parts = []
    for key in cfg.get("report_fields", []):
        val = get_form_value(f_json, key)
        if val not in (None, "", "None"):
            detail_parts.append(str(val))
    detail = " - ".join(detail_parts) if detail_parts else t.get("subject", "")
    requester = t.get("requester", "")
    status = t.get("status", "")
    return f"- {day_prefix(t.get('created_at'))}{t.get('id', '')} – {detail} ({requester}) – {status}."

def day_prefix(value):
    """'dd/mm: ' đặt ở đầu mỗi dòng báo cáo (rỗng nếu không có ngày)."""
    d = to_date(value)
    return f"{d.strftime('%d/%m')}: " if d else ""

def build_domain_section_lines(tickets, domain):
    """Sinh nội dung cột 'Các công việc thực hiện' cho 1 domain (warranty/erp/...), phân theo từng Form
    thuộc domain đó. Trả về list (text, bold) — mỗi tuple là 1 đoạn (paragraph) riêng."""
    lines = []
    section_no = 0
    for cfg in FORM_CONFIGS:
        if cfg.get("domain", "warranty") != domain:
            continue
        form_tickets = [t for t in tickets if normalize_form_type(t.get('form_type')) == cfg['type']]
        if not form_tickets:
            continue
        section_no += 1
        short_label = cfg['label'].split(": ", 1)[-1] if ": " in cfg['label'] else cfg['label']
        lines.append((f"{section_no}. {short_label}:", True))
        for t in sorted(form_tickets, key=lambda x: x.get('id') or ''):
            lines.append((build_ticket_report_line(t, cfg), False))
    return lines

def build_note_lines(notes):
    """Mỗi ghi chú → 1 hoặc nhiều dòng '- nội dung' (ghi chú nhiều dòng thì giữ nguyên xuống dòng)."""
    lines = []
    for note in sorted(notes, key=lambda n: (to_date(n.get("note_date")) or datetime.date.min, n.get("id") or 0)):
        prefix = day_prefix(note.get("note_date"))
        for text in str(note.get("content") or "").splitlines():
            text = text.strip().lstrip("-+•").strip()
            if text:
                lines.append((f"- {prefix}{text}", False))
    return lines

def build_tracking_lines(items):
    """Mỗi mục theo dõi → '- dd/mm: #ID – Tiêu đề – Trạng thái'. Chỉ 4 trường này (theo yêu cầu);
    ngày = lần đổi trạng thái gần nhất trong tuần, không có thì ngày đổi sang trạng thái hiện tại."""
    lines = []
    for item in items:
        title = "; ".join(part.strip() for part in str(item.get("title") or "").splitlines() if part.strip() not in ("", "--"))
        ext_id = str(item.get("ext_id") or "").strip()
        if ext_id and not ext_id.startswith("#"):
            ext_id = f"#{ext_id}"
        text = f"- {day_prefix(item.get('report_date'))}{ext_id + ' – ' if ext_id else ''}{title} – {item.get('status') or ''}"
        lines.append((text, False))
    return lines

def build_report_row_lines(ctx, category, tracking=None):
    """Nội dung việc đã làm của 1 nhóm (ERP / Bảo hành / Gree App / IT): ticket theo Form
    + mục 'Theo dõi ticket' (tracking, mặc định ctx['week_tracking']) + 'Công việc khác' từ ghi chú công việc."""
    lines = build_domain_section_lines(ctx['week_relevant_tickets'], category)
    tracking = ctx.get('week_tracking', []) if tracking is None else tracking
    tracking_lines = build_tracking_lines([i for i in tracking if i.get('category') == category])
    category_notes = [n for n in ctx.get('week_notes', []) if n.get('category') == category]
    note_lines = build_note_lines(category_notes)
    extra_sections = [(title, extra) for title, extra in (("Theo dõi ticket", tracking_lines), ("Công việc khác", note_lines)) if extra]
    for title, extra in extra_sections:
        # Chỉ có đúng 1 loại nội dung thì không cần tiêu đề mục (giữ như trước)
        if lines or len(extra_sections) > 1:
            section_no = sum(1 for _, bold in lines if bold) + 1
            lines.append((f"{section_no}. {title}:", True))
        lines.extend(extra)
    return lines

# Dòng báo cáo dạng '- dd/mm: nội dung' → tách phần ngày để in đậm
DATED_LINE_RE = re.compile(r"^(- )(\d{2}/\d{2})(:.*)$", re.DOTALL)

def add_report_runs(paragraph, text, bold):
    """Ghi 1 dòng báo cáo vào paragraph; dòng '- dd/mm: ...' thì in đậm phần ngày."""
    m = None if bold else DATED_LINE_RE.match(text)
    if not m:
        paragraph.add_run(text).bold = bold
        return
    paragraph.add_run(m.group(1))
    paragraph.add_run(m.group(2)).bold = True
    paragraph.add_run(m.group(3))

def report_lines_markdown(lines):
    """Xem trước nội dung báo cáo trên web: tiêu đề mục in đậm, ngày đầu dòng in đậm."""
    out = []
    for text, bold in lines:
        safe = html.escape(text).replace("*", "\\*").replace("_", "\\_")
        if bold:
            # Dòng trống trước/sau để tiêu đề mục không dính vào danh sách phía trên
            out.extend(["", f"**{safe}**", ""])
            continue
        m = DATED_LINE_RE.match(safe)
        out.append(f"- **{m.group(2)}**{m.group(3)}" if m else safe)
    return "\n".join(out)

def set_cell_lines(cell, lines):
    """Ghi nội dung mới vào 1 cell (list (text, bold)), mỗi tuple thành 1 paragraph riêng.
    Giữ định dạng (font) gốc của cell bằng cách tái sử dụng đoạn/run đầu tiên."""
    paragraphs = list(cell.paragraphs)
    for p in paragraphs[1:]:
        p._element.getparent().remove(p._element)
    base_p = cell.paragraphs[0]
    for r in list(base_p.runs):
        r._element.getparent().remove(r._element)
    # Bỏ gạch đầu dòng tự động của file mẫu (mẫu mới để sẵn list) — nội dung đã tự có "- " ở đầu dòng
    p_pr = base_p._p.pPr
    if p_pr is not None and p_pr.numPr is not None:
        p_pr.remove(p_pr.numPr)
        for tag in ("w:ind", "w:pStyle"):  # thụt lề / kiểu "List Paragraph" đi kèm gạch đầu dòng
            for el in p_pr.findall(qn(tag)):
                p_pr.remove(el)
    if not lines:
        return
    first_text, first_bold = lines[0]
    add_report_runs(base_p, first_text, first_bold)
    for text, bold in lines[1:]:
        add_report_runs(cell.add_paragraph(), text, bold)

def replace_paragraph_text(paragraph, new_text):
    """Thay toàn bộ nội dung 1 paragraph, giữ định dạng (font/bold/size) của run đầu tiên."""
    if not paragraph.runs:
        paragraph.add_run(new_text)
        return
    paragraph.runs[0].text = new_text
    for r in paragraph.runs[1:]:
        r._element.getparent().remove(r._element)

def update_title_paragraphs(doc, week, month, year, reporter):
    """Tìm và thay '(Tuần X tháng Y năm Z)' + 'Tên nhân viên báo cáo: ...' ở đầu file,
    bất kể nội dung cũ trong file mẫu là gì (tìm theo mẫu chữ, không theo vị trí cố định)."""
    week_pattern = re.compile(r"\(Tuần\s*\d+\s*tháng\s*\d+\s*năm\s*\d+\)")
    reporter_pattern = re.compile(r"^Tên nhân viên báo cáo\s*:")
    for p in doc.paragraphs:
        if week_pattern.search(p.text):
            replace_paragraph_text(p, f"(Tuần {week} tháng {month} năm {year})")
        elif reporter_pattern.match(p.text.strip()):
            replace_paragraph_text(p, f"Tên nhân viên báo cáo: {reporter}")

# Ticket AEGONA chưa triển khai trong báo cáo tuần: nguyên nhân chưa xong / bước tiếp theo, theo trạng thái theo dõi
AGN_PENDING_REASON = {
    "Mới": "Chưa bắt đầu thực hiện",
    "Chờ đề xuất": "Đang chờ chốt đề xuất / phê duyệt",
    "Đang thực hiện": "AEGONA đang thực hiện, chưa bàn giao",
    "Đang testing": "Đang kiểm thử, chưa đủ điều kiện triển khai",
    "Chờ deploy": "Chờ lịch triển khai lên Production",
    "Chờ cập nhật": "Chờ cập nhật lên hệ thống",
}
AGN_NEXT_STEP = {
    "Mới": "Gửi yêu cầu, AEGONA đánh giá ETA",
    "Chờ đề xuất": "Chốt đề xuất & phê duyệt để AEGONA triển khai",
    "Đang thực hiện": "AEGONA hoàn thành, bàn giao kiểm thử",
    "Đang testing": "Hoàn tất kiểm thử, chuyển triển khai",
    "Chờ deploy": "Triển khai lên Production",
    "Chờ cập nhật": "Cập nhật lên hệ thống",
}
PLAN_WEEKDAY_COLS = 6  # cột T2 → T7 của bảng Kế hoạch tuần sau

def agn_requested_date(item):
    """Ngày ticket AEGONA được nêu ra (ngày yêu cầu; thiếu thì ngày bắt đầu / ngày tạo)."""
    return to_date(item.get("requested_at")) or to_date(item.get("start_date")) or to_date(item.get("created_at"))

def agn_item_label(item):
    ext = str(item.get("ext_id") or "").strip()
    if ext and not ext.startswith("#"):
        ext = f"#{ext}"
    title = "; ".join(part.strip() for part in str(item.get("title") or "").splitlines() if part.strip() not in ("", "--"))
    return f"{ext} – {title}" if ext else title

def build_weekly_sections(ctx):
    """Nội dung báo cáo tuần theo mẫu 'BÁO CÁO CÔNG VIỆC HÀNG TUẦN QUẢN TRỊ HỆ THỐNG IT'.
    I.1 Tóm tắt chung · I.2 Công việc đã thực hiện · I.3 Đang tiến hành/dở dang · II Tuần trước chưa giải quyết · III Kế hoạch.
    Ticket AEGONA chưa triển khai (có giờ, chưa Đóng/lên Production): nêu TRONG tuần → I.3, nêu TRƯỚC tuần → II,
    tất cả → III."""
    start, end = ctx["start_date"], ctx["end_date"]
    next_monday = start + datetime.timedelta(days=7)
    next_saturday = next_monday + datetime.timedelta(days=5)
    next_week_text = f"{next_monday:%d/%m}-{next_saturday:%d/%m/%Y}"
    time_text = f"{start:%d/%m}-{end:%d/%m/%Y}"

    stats = agn_package_stats(ctx.get("tracking") or [])
    pending = [i for i in (stats["pending_items"] if stats else []) if (agn_requested_date(i) or start) <= end]
    pending_ids = {i["id"] for i in pending}
    carried = [i for i in pending if agn_requested_date(i) and agn_requested_date(i) < start]
    carried_ids = {i["id"] for i in carried}
    new_pending = [i for i in pending if i["id"] not in carried_ids]

    week_tracking = ctx.get("week_tracking", [])
    finished = TRACKING_CLOSED | set(AGN_DEPLOYED_STATUSES)
    done_tracking = [i for i in week_tracking if i.get("status") in finished and i.get("week_logs")]
    moving = [i for i in week_tracking if i.get("status") not in finished and i.get("week_logs") and i["id"] not in pending_ids]

    # I.2 — việc đã làm, nhóm theo hệ thống
    done = []
    for category, (_, heading) in WORK_NOTE_CATEGORIES.items():
        lines = build_report_row_lines(ctx, category, tracking=done_tracking)
        if lines:
            done.append((f"{heading}:", True))
            done.extend(lines)

    # I.3 — đang tiến hành / dở dang
    doing = []
    open_tickets = [t for t in ctx.get("week_relevant_tickets", []) if t.get("status") not in CLOSED_STATUSES]
    if open_tickets:
        doing.append(("Ticket hỗ trợ đang xử lý:", True))
        doing += [(f"- {day_prefix(t.get('created_at'))}{t.get('id')} – {t.get('subject') or ''} ({t.get('requester') or ''})"
                   f" – {t.get('status')}", False) for t in sort_tickets_for_display(open_tickets)]
    if new_pending:
        doing.append(("AEGONA – chưa triển khai (yêu cầu trong tuần):", True))
        doing += [(f"- {day_prefix(agn_requested_date(i))}{agn_item_label(i)} – {i.get('status')} ({agn_item_hours(i):.2f} giờ)", False)
                  for i in new_pending]
    if moving:
        doing.append(("AEGONA – ticket đang mở có cập nhật trong tuần:", True))
        doing += build_tracking_lines(moving)

    # I.1 — tóm tắt chung (số liệu)
    week_tickets = ctx.get("week_relevant_tickets", [])
    by_domain = " · ".join(f"{label} {n}" for label, n in (
        (WORK_NOTE_LABELS[c], len([t for t in week_tickets if ticket_domain(t) == c])) for c in ("erp", "warranty", "gree_app")) if n)
    summary = [(f"- Ticket hỗ trợ: {len(ctx.get('week_new_tickets', []))} tiếp nhận mới, "
                f"{len(ctx.get('week_completed_tasks', []))} hoàn thành, {len(open_tickets)} đang xử lý"
                + (f" ({by_domain})." if by_domain else "."), False)]
    if stats:
        summary.append((f"- Gói bảo trì AEGONA (tới {stats['today']:%d/%m}): đã dùng {stats['used']:.2f}/{stats['quota']:g} giờ "
                        f"({stats['used_pct']:.1f}%) — đã triển khai {stats['deployed']:.2f} giờ, chưa triển khai "
                        f"{stats['pending']:.2f} giờ ({len(stats['pending_items'])} ticket). Chi tiết: file PDF đính kèm.", False))
        summary.append((f"- Ticket AEGONA: {len(done_tracking)} đóng/triển khai trong tuần, {len(stats['open_items'])} đang mở.", False))
    issues = str(ctx.get("issues") or "").strip()
    if issues:
        summary.append(("Sự cố / vấn đề:", True))
        summary += [(f"- {line.strip().lstrip('-+•').strip()}", False) for line in issues.splitlines() if line.strip()]

    def due_text(item):
        d = to_date(item.get("end_date"))
        return f"{d:%d/%m/%Y}" if d and d > end else f"tuần sau ({next_week_text})"

    carried_rows = [{
        "content": agn_item_label(i) + (f" ({i['system_name']})" if i.get("system_name") else ""),
        "status": f"{i.get('status')} – {agn_item_hours(i):.2f} giờ" + (f" (AEGONA: {i['agn_status']})" if i.get("agn_status") else ""),
        "reason": AGN_PENDING_REASON.get(i.get("status"), "Chưa hoàn tất"),
        "next": f"{AGN_NEXT_STEP.get(i.get('status'), 'Tiếp tục theo dõi')} – dự kiến: {due_text(i)}",
    } for i in carried]
    plan_rows = [{
        "content": agn_item_label(i),
        "goal": AGN_NEXT_STEP.get(i.get("status"), "Tiếp tục theo dõi"),
        "require": "Triển khai lên hệ thống, đóng ticket",
    } for i in pending]
    return {"summary": summary, "done": done, "doing": doing, "carried": carried_rows, "plan": plan_rows,
            "time_text": time_text, "next_week_text": next_week_text}

def find_table_with_header(doc, header_text, header_rows=1):
    """Tìm bảng (kể cả lồng trong cell khác) có ô tiêu đề (trong header_rows dòng đầu) chứa header_text."""
    def search(tables):
        for tbl in tables:
            for row in tbl.rows[:header_rows]:
                if any(header_text in c.text for c in row.cells):
                    return tbl
            for row in tbl.rows:
                for cell in row.cells:
                    found = search(cell.tables)
                    if found is not None:
                        return found
        return None
    return search(doc.tables)

def own_cells(row, table):
    """Các ô THẬT của 1 dòng (mỗi <w:tc> 1 ô, ô gộp ngang chỉ tính 1 lần). Bỏ gộp dọc (vMerge) của dòng này:
    file mẫu mới để ô dòng dữ liệu gộp dọc với ô tiêu đề, row.cells sẽ trả về ô tiêu đề → ghi đè tiêu đề."""
    cells = []
    for tc in row._tr.tc_lst:
        tc_pr = tc.tcPr
        if tc_pr is not None:
            for v_merge in tc_pr.findall(qn("w:vMerge")):
                tc_pr.remove(v_merge)
        cells.append(_Cell(tc, table))
    return cells

def find_row_by_content(table, keyword, content_col_label="Nội dung"):
    """Tìm dòng trong bảng mà cột 'Nội dung' chứa keyword (vd: 'Tóm tắt chung')."""
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    col_idx = header_cells.index(content_col_label) if content_col_label in header_cells else 1
    for row in table.rows[1:]:
        if keyword in row.cells[col_idx].text:
            return row
    return None

def update_all_rows_time(table, time_text):
    """Điền khoảng thời gian của tuần vào cột 'T/g giải quyết' cho tất cả các dòng nội dung."""
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    if "T/g giải quyết" not in header_cells:
        return False
    time_idx = header_cells.index("T/g giải quyết")
    for row in table.rows[1:]:
        set_cell_lines(row.cells[time_idx], [(time_text, False)])
    return True

def fill_rows_from_template(table, template_row, values_list):
    """Nhân bản template_row cho từng phần tử values_list (list giá trị theo thứ tự ô) rồi bỏ dòng mẫu."""
    tpl = template_row._tr
    for values in values_list:
        tr = copy.deepcopy(tpl)
        tpl.addprevious(tr)
        for cell, value in zip(own_cells(_Row(tr, table), table), values):
            set_cell_lines(cell, [(value, False)] if value else [])
    tpl.getparent().remove(tpl)

def fill_carried_table(doc, carried_rows):
    """Bảng 'CÁC CÔNG VIỆC ĐÃ NÊU TUẦN TRƯỚC NHƯNG CHƯA ĐƯỢC GIẢI QUYẾT' (TT · Nội dung · Tình trạng · Nguyên nhân · Hướng xử lý)."""
    table = find_table_with_header(doc, "Tình trạng hiện tại")
    if table is None or len(table.rows) < 2:
        return False
    values = [[str(n), r["content"], r["status"], r["reason"], r["next"]] for n, r in enumerate(carried_rows, 1)]
    fill_rows_from_template(table, table.rows[1], values or [["", "Không có công việc tồn đọng từ tuần trước.", "", "", ""]])
    return True

def fill_plan_table(doc, plan_rows, next_week_text):
    """Bảng 'KẾ HOẠCH CÔNG VIỆC TUẦN SAU': TT · Nội dung · Mục tiêu · Yêu cầu kết quả · T2..T7 · Ghi chú.
    Mỗi ticket AEGONA chưa triển khai 1 dòng; dòng trống còn dư của file mẫu được bỏ đi."""
    table = find_table_with_header(doc, "Mục tiêu / Kết quả kỳ vọng", header_rows=2)
    if table is None or len(table.rows) < 3 or not plan_rows:
        return False
    data_rows = list(table.rows[2:])
    values = [[str(n), r["content"], r["goal"], r["require"]] + ["x"] * PLAN_WEEKDAY_COLS + [next_week_text]
              for n, r in enumerate(plan_rows, 1)]
    template = data_rows[-1]
    for row in data_rows[:-1]:
        row._tr.getparent().remove(row._tr)
    fill_rows_from_template(table, template, values)
    return True

def generate_weekly_report_from_template(template_path, ctx):
    """Đổ dữ liệu vào ĐÚNG file mẫu công ty (giữ logo/layout/khung tự đánh giá...): tiêu đề tuần, người báo cáo,
    cột 'Chi tiết thực hiện' + 'T/g giải quyết' của mục I, bảng II (tuần trước chưa giải quyết), bảng III (kế hoạch)."""
    doc = Document(template_path)
    update_title_paragraphs(doc, ctx['week'], ctx['month'], ctx['year'], ctx['reporter'])
    sections = build_weekly_sections(ctx)

    table = find_table_with_header(doc, "Chi tiết thực hiện")
    if table is None:
        raise ValueError("Không tìm thấy bảng có cột 'Chi tiết thực hiện' (mục Công việc đã thực hiện trong tuần) trong file mẫu.")
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    detail_idx = header_cells.index("Chi tiết thực hiện")
    for keyword, key in (("Tóm tắt chung", "summary"), ("Công việc đã thực hiện", "done"), ("Công việc đang tiến hành", "doing")):
        row = find_row_by_content(table, keyword)
        if row is not None:
            set_cell_lines(row.cells[detail_idx], sections[key] or [("Không có.", False)])
    update_all_rows_time(table, sections["time_text"])
    fill_carried_table(doc, sections["carried"])
    fill_plan_table(doc, sections["plan"], sections["next_week_text"])

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# -----------------
# GIAO DIỆN VIEW-ONLY TINH GỌN (GUEST VIEW)
# -----------------
if st.session_state.get("view_mode") == "only":
    # Ẩn Sidebar hoàn toàn bằng CSS
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        [data-testid="stSidebarCollapseButton"] {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Tìm kiếm Ticket trong db_tickets
    target_t = None
    for t in db_tickets:
        if t["id"] == url_ticket_id:
            target_t = t
            break
            
    if target_t:
        st.markdown(f'<div class="main-header">🔍 Tra cứu Ticket Chi tiết</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sub-header">Giao diện xem nhanh thông tin yêu cầu bảo hành Gree IT</div>', unsafe_allow_html=True)
        
        # Thẻ thông tin tổng quan dạng card đẹp mắt
        with st.container(border=True):
            c_g1, c_g2, c_g3, c_g4 = st.columns([0.25, 0.25, 0.25, 0.25])
            with c_g1:
                st.markdown(f"**Mã Ticket:**\n`{target_t['id']}`")
            with c_g2:
                badge_html = status_badge(target_t['status'])
                st.markdown(f"**Trạng thái:**\n{badge_html}", unsafe_allow_html=True)
            with c_g3:
                st.markdown(f"**Người yêu cầu:**\n`{target_t['requester']}`")
            with c_g4:
                st.markdown(f"**Ngày khởi tạo:**\n`{format_ticket_date(target_t['created_at'])}`")
                
            st.markdown("---")
            st.markdown(f"**Tiêu đề yêu cầu:**\n### {target_t['subject']}")

        # Hàng chứa nút chuyển về hệ thống chính
        col_back_space, col_back_btn = st.columns([0.65, 0.35])
        with col_back_btn:
            if st.button("🏠 Mở trong hệ thống đầy đủ", type="primary", use_container_width=True):
                goto_ticket_detail(target_t)
                # Xóa tham số URL
                st.query_params.clear()
                st.rerun()

        # Dữ liệu đính kèm (nếu có)
        if target_t.get('form_data') and target_t.get('form_type'):
            display_form_type = normalize_form_type(target_t.get("form_type"))
            display_form_name = FORM_TYPE_TO_CONFIG.get(display_form_type, {}).get("label", display_form_type)
            st.markdown("---")
            st.markdown(f"#### 📋 Dữ liệu đính kèm: **{display_form_name}**")
            
            # Nhãn tiếng Việt + khối nội dung, thay cho bảng 1 dòng bị cắt chữ khi nội dung dài
            display_config = FORM_TYPE_TO_CONFIG.get(display_form_type)
            try:
                f_data = parse_form_data(target_t)
                render_form_data_view(f_data, build_field_label_map(display_config))
            except Exception as e:
                st.error(f"Lỗi hiển thị dữ liệu Form: {e}")

        # Lịch sử hội thoại (Chat-log)
        st.markdown("---")
        st.markdown("#### 💬 Lịch sử trao đổi & Xử lý (Chat-log)")
        
        # Trong chế độ guest, ẩn log nội bộ để bảo mật!
        render_ticket_messages(target_t['msgs'], show_internal=False)

        # Gửi log mới (chỉ cho phép Công khai trong chế độ Guest)
        st.divider()
        st.markdown("##### 📩 Gửi phản hồi mới")
        guest_name = st.text_input("Tên của bạn", value=target_t['requester'], key="guest_msg_name")
        guest_msg = st.text_area("Nội dung phản hồi...", height=80, key="guest_msg_val")

        if st.button("📩 Gửi phản hồi", use_container_width=True, key="btn_guest_send"):
            if guest_name.strip().startswith("Admin") and not is_admin():
                # Tên bắt đầu bằng "Admin" sẽ hiện như phản hồi của Admin
                st.warning("Tên người gửi không được bắt đầu bằng 'Admin'.")
            elif guest_msg and guest_name:
                db.add_ticket_message(target_t['id'], guest_name, guest_msg, "public")
                st.success("Đã gửi phản hồi thành công!")
                st.rerun()
            else:
                st.warning("Vui lòng nhập đầy đủ tên và nội dung phản hồi.")

        # Cập nhật trạng thái ngay trong màn hình chi tiết — chỉ Admin.
        # Sidebar bị ẩn ở chế độ này nên cần ô đăng nhập riêng tại đây.
        st.divider()
        if is_admin():
            st.markdown("##### 🔄 Cập nhật trạng thái Ticket")
            share_status = st.selectbox(
                "Chọn trạng thái mới",
                STATUS_LIST,
                index=STATUS_LIST.index(target_t['status']) if target_t['status'] in STATUS_LIST else 0,
                key="share_status_change",
            )
            share_log = st.text_area(
                "Nội dung xử lý (ghi kèm vào log khi chuyển sang Hoàn thành)",
                height=80,
                key="share_status_log",
            )
            col_up, col_out = st.columns(2)
            if col_up.button("🔄 Cập nhật trạng thái", type="primary", use_container_width=True, key="btn_share_update_status"):
                if share_status == target_t['status']:
                    st.info("Trạng thái không thay đổi.")
                elif share_status == "Hoàn thành":
                    # Dùng complete_ticket để ghi nhận vào bảng tasks cho báo cáo tuần
                    db.complete_ticket(
                        target_t['id'],
                        target_t['subject'],
                        share_log.strip() or "Admin đã đánh dấu hoàn thành",
                        changed_by=ADMIN_DISPLAY_NAME,
                    )
                    st.rerun()
                else:
                    db.update_ticket_status(target_t['id'], share_status, changed_by=ADMIN_DISPLAY_NAME)
                    st.rerun()
            if col_out.button("🚪 Thoát Admin", use_container_width=True, key="btn_share_logout"):
                logout_admin()
                st.rerun()
        else:
            with st.expander("🔐 Đăng nhập Admin để cập nhật trạng thái"):
                st.caption(f"Đăng nhập một lần, ghi nhớ {ADMIN_SESSION_DAYS} ngày trên trình duyệt này.")
                share_pw = st.text_input("Mật khẩu", type="password", key="share_admin_pw")
                if st.button("Đăng nhập", use_container_width=True, key="btn_share_login"):
                    if check_admin_password(share_pw):
                        login_admin()
                        st.rerun()
                    elif ADMIN_PASSWORD:
                        st.error("Sai mật khẩu.")
    else:
        st.error(f"❌ Không tìm thấy Ticket với mã yêu cầu `{url_ticket_id}` hoặc yêu cầu đã bị xóa vĩnh viễn khỏi hệ thống.")
        if st.button("🏠 Quay lại trang chủ hệ thống", type="primary"):
            st.session_state["view_mode"] = "full"
            st.query_params.clear()
            st.rerun()
            
    # Dừng chạy code phía dưới để giữ giao diện tinh gọn
    st.stop()

# -----------------
# GHI CHÚ CÔNG VIỆC NGOÀI TICKET
# -----------------
def _save_quick_note():
    """Callback chạy trước lần chạy lại → được phép xóa ô nội dung sau khi lưu."""
    content = st.session_state.get("quick_note_content", "").strip()
    if not content:
        st.session_state["_quick_note_msg"] = ("warning", "Chưa nhập nội dung.")
        return
    category = st.session_state["quick_note_category"]
    db.add_work_note(st.session_state["quick_note_date"], category, content)
    st.session_state["quick_note_content"] = ""
    st.session_state["_quick_note_msg"] = ("toast", f"Đã lưu ghi chú ({WORK_NOTE_LABELS[category]})")

def render_quick_note_form():
    """Ô ghi chú nhanh ở sidebar: chọn nhóm + 1 đoạn nội dung tổng quan. Nhóm giữ nguyên lựa chọn trước."""
    with st.form("quick_note_form", border=False):
        st.selectbox("Nhóm", list(WORK_NOTE_LABELS), format_func=WORK_NOTE_LABELS.get, key="quick_note_category")
        st.date_input("Ngày", value=now_vn().date(), format="DD/MM/YYYY", key="quick_note_date")
        st.text_area("Nội dung", height=90, placeholder="VD: Họp ASoft chốt quy trình nhập kho", key="quick_note_content")
        st.form_submit_button("💾 Lưu ghi chú", width="stretch", on_click=_save_quick_note)
    msg = st.session_state.pop("_quick_note_msg", None)
    if msg and msg[0] == "toast":
        st.toast(msg[1])
    elif msg:
        st.warning(msg[1])

def wrapped_text_html(text):
    """Nội dung giữ nguyên xuống dòng của người nhập và tự ngắt dòng theo độ rộng cột."""
    return f'<div style="white-space: pre-wrap; word-break: break-word;">{html.escape(str(text or ""))}</div>'

def render_work_notes_list(week_notes):
    """Danh sách ghi chú của tuần: nội dung tự xuống dòng, mỗi dòng có nút Sửa / Xóa."""
    if not week_notes:
        st.info("Chưa có ghi chú nào trong tuần này.")
        return
    label_to_key = {label: key for key, label in WORK_NOTE_LABELS.items()}
    notes = sorted(week_notes, key=lambda n: (to_date(n["note_date"]), n["id"]))
    for n in notes:
        c_date, c_cat, c_content, c_edit, c_del = st.columns([1, 1.2, 7, 0.6, 0.6], vertical_alignment="top")
        c_date.markdown(f"**{to_date(n['note_date']).strftime('%d/%m')}**")
        c_cat.caption(WORK_NOTE_LABELS.get(n["category"], n["category"]))
        c_content.markdown(wrapped_text_html(n["content"]), unsafe_allow_html=True)
        with c_edit.popover("✏️", help="Sửa ghi chú"):
            with st.form(f"edit_note_{n['id']}", border=False):
                new_date = st.date_input("Ngày", value=to_date(n["note_date"]), format="DD/MM/YYYY", key=f"edit_note_date_{n['id']}")
                cat_labels = list(label_to_key)
                cur_label = WORK_NOTE_LABELS.get(n["category"], cat_labels[0])
                new_label = st.selectbox("Nhóm", cat_labels, index=cat_labels.index(cur_label) if cur_label in cat_labels else 0, key=f"edit_note_cat_{n['id']}")
                new_content = st.text_area("Nội dung", value=n["content"], height=150, key=f"edit_note_content_{n['id']}")
                if st.form_submit_button("💾 Lưu", type="primary"):
                    if new_content.strip():
                        db.save_work_note_changes(
                            [{"id": n["id"], "note_date": new_date, "category": label_to_key[new_label], "content": new_content.strip()}], []
                        )
                        st.session_state["_notes_editor_version"] = st.session_state.get("_notes_editor_version", 0) + 1
                        st.rerun()
                    else:
                        st.warning("Nội dung không được để trống.")
        with c_del.popover("🗑️", help="Xóa ghi chú"):
            st.write("Xóa ghi chú này?")
            if st.button("Xóa", type="primary", key=f"del_note_{n['id']}"):
                db.delete_work_note(n["id"])
                st.session_state["_notes_editor_version"] = st.session_state.get("_notes_editor_version", 0) + 1
                st.toast("Đã xóa ghi chú")
                st.rerun()

def render_work_notes_editor(week_notes, start_date, end_date):
    """Bảng sửa/xóa/thêm ghi chú của tuần đang xem trên trang Báo cáo."""
    label_to_key = {label: key for key, label in WORK_NOTE_LABELS.items()}
    original = pd.DataFrame(
        [
            {"id": n["id"], "Ngày": to_date(n["note_date"]),
             "Nhóm": WORK_NOTE_LABELS.get(n["category"], n["category"]), "Nội dung": n["content"]}
            for n in week_notes
        ],
        columns=["id", "Ngày", "Nhóm", "Nội dung"],
    )
    # Đổi key sau mỗi lần Lưu để bảng nạp lại dữ liệu mới thay vì giữ chỉnh sửa cũ
    version = st.session_state.get("_notes_editor_version", 0)
    edited = st.data_editor(
        original,
        key=f"notes_editor_{start_date}_{version}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        row_height=60,
        column_order=["Ngày", "Nhóm", "Nội dung"],
        column_config={
            "Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY", default=min(max(now_vn().date(), start_date), end_date), required=True),
            "Nhóm": st.column_config.SelectboxColumn("Nhóm", options=list(label_to_key), required=True),
            "Nội dung": st.column_config.TextColumn("Nội dung", width="large", required=True),
        },
    )
    if st.button("💾 Lưu thay đổi ghi chú", key="btn_save_notes"):
        original_by_id = {int(r["id"]): r for r in original.to_dict("records")}
        kept_ids, updated = set(), []
        for row in edited.to_dict("records"):
            content = str(row.get("Nội dung") or "").strip()
            if not content or not row.get("Nhóm"):
                continue
            # Ô ngày trả về có thể là date / Timestamp / chuỗi tùy thao tác → chuẩn hóa về date
            note_date = to_date(row.get("Ngày")) or now_vn().date()
            note = {"note_date": note_date, "category": label_to_key[row["Nhóm"]], "content": content}
            if pd.isna(row.get("id")):
                db.add_work_note(note["note_date"], note["category"], note["content"])
                continue
            note["id"] = int(row["id"])
            kept_ids.add(note["id"])
            old = original_by_id[note["id"]]
            if (old["Ngày"], old["Nhóm"], old["Nội dung"]) != (note_date, row["Nhóm"], content):
                updated.append(note)
        deleted_ids = [note_id for note_id in original_by_id if note_id not in kept_ids]
        db.save_work_note_changes(updated, deleted_ids)
        st.session_state["_notes_editor_version"] = version + 1
        st.rerun()

def generate_tracking_excel(ctx):
    """File Excel theo dõi ticket của tuần (cùng bố cục bảng theo dõi AEGONA): các mục còn mở
    + mục đổi trạng thái trong tuần, thêm cột 'Thay đổi trong tuần'. Trả về bytes .xlsx."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = f"Tuan {ctx['week']}-T{ctx['month']}"
    period = f"{ctx['start_date'].strftime('%d/%m/%Y')} - {ctx['end_date'].strftime('%d/%m/%Y')}"
    ws.append([f"THEO DÕI TICKET - TUẦN {ctx['week']} THÁNG {ctx['month']}/{ctx['year']} ({period})"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([])

    headers = ["Trạng thái cập nhật", "Ưu tiên", "Ngày cập nhật lên server Production", "ID AEGONA",
               "Tiêu đề", "Thay đổi trong tuần", "Ghi chú", "Nội dung cập nhật", "Source code", "Người thực hiện"]
    widths = [18, 11, 16, 11, 50, 30, 30, 70, 18, 18]
    ws.append(headers)
    thin = Side(style="thin", color="BFBFBF")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for i, (cell, width) in enumerate(zip(ws[3], widths)):
        # Giống file gốc: 2 cột đầu nền xanh, các cột còn lại nền cam
        cell.fill = PatternFill("solid", fgColor="1F4E79" if i < 2 else "F79646")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        ws.column_dimensions[cell.column_letter].width = width

    new_fill = PatternFill("solid", fgColor="FFFF00")
    for item in ctx.get("week_tracking", []):
        changes = "\n".join(
            f"{to_date(l['created_at']).strftime('%d/%m')}: "
            + (f"{l['old_status']} → {l['new_status']}" if l.get("old_status") else f"Thêm mới ({l['new_status']})")
            for l in item.get("week_logs", [])
        )
        ws.append([
            item.get("status") or "", item.get("priority") or "", to_date(item.get("prod_date")),
            item.get("ext_id") or "", item.get("title") or "", changes, item.get("note") or "",
            item.get("content") or "", item.get("source_code") or "", item.get("assignee") or "",
        ])
        for cell in ws[ws.max_row]:
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            cell.border = border
            if item.get("status") == "Mới":
                cell.fill = new_fill
        ws.cell(ws.max_row, 3).number_format = "DD/MM/YYYY"
        ws.cell(ws.max_row, 4).alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:J{max(ws.max_row, 3)}"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

def render_tracking_import_box(items):
    """Tải file Excel (log cập nhật Gree App hoặc báo cáo tháng của AEGONA) → xem trước → cập nhật bảng theo dõi
    (xem tracking_import.py)."""
    with st.expander("📥 Đồng bộ từ file Excel (báo cáo AEGONA / log cập nhật Gree App)"):
        st.caption(
            "• **Gree VN x AGN_Maintenance Ticket Report** (sheet July/Aug/Sep/Oct...): lấy mọi ticket kèm giờ ETA/thực tế "
            "và tháng tính giờ → MD theo tháng. Tiêu đề/nội dung đã có thì giữ nguyên.  \n"
            "• **GreeApp System Update Log** (sheet Logs): lấy các dòng còn theo dõi, đổi trạng thái theo file.  \n"
            "Khớp theo ID AEGONA (không có ID thì theo Tiêu đề). Mục không còn trong file được giữ nguyên."
        )
        upload = st.file_uploader("File .xlsx", type=["xlsx"], key="tracking_xlsx", label_visibility="collapsed")
        if upload is None:
            return
        file_items, errors, source, month_totals = parse_tracking_xlsx(io.BytesIO(upload.getvalue()))
        if errors:
            st.error("\n".join(errors))
            return
        update_status = None
        if source == "agn":
            update_status = st.checkbox(
                "Đổi cả Trạng thái của mục đã có theo trạng thái AEGONA (Closed → Đóng, Ready to deploy → Chờ deploy...)",
                value=False, key="tracking_import_status",
                help="Bỏ chọn: giữ trạng thái bạn đang theo dõi, chỉ cập nhật giờ/tháng/trạng thái AEGONA. Mục mới luôn lấy theo file.",
            )
        added, updated = match_tracking(file_items, items, source, update_status=update_status)
        kind = "báo cáo AEGONA" if source == "agn" else "log cập nhật Gree App"
        st.write(f"File **{kind}** có **{len(file_items)}** mục → thêm **{len(added)}**, cập nhật **{len(updated)}**.")
        by_id = {i["id"]: i for i in items}
        preview = [
            {"Thao tác": "Thêm", "ID": a.get("ext_id") or "", "Tiêu đề": a["title"], "Thay đổi": a["status"]} for a in added
        ] + [
            {"Thao tác": "Cập nhật", "ID": by_id[u["id"]].get("ext_id") or "", "Tiêu đề": by_id[u["id"]]["title"],
             "Thay đổi": describe_change(by_id[u["id"]], u)}
            for u in updated
        ]
        if preview:
            st.dataframe(pd.DataFrame(preview), hide_index=True, width="stretch")
        saved_totals = db.get_settings().get(MONTH_TOTALS_KEY)
        new_totals = merge_month_totals(saved_totals, month_totals) if month_totals else saved_totals
        if month_totals:
            st.caption("Tổng giờ theo tháng (ô 'Tổng số giờ đã triển khai'): " + " · ".join(
                f"{month_label(m)}: ETA {t['eta']:g}h, Actual {t['actual']:g}h" for m, t in month_totals.items()))
        if st.button("✅ Cập nhật bảng theo dõi", type="primary", disabled=not preview and new_totals == saved_totals,
                     key="btn_tracking_import"):
            if new_totals != saved_totals:
                db.save_settings({MONTH_TOTALS_KEY: new_totals})
            if db.save_ticket_tracking_changes(added, updated, []):
                st.session_state["_tracking_msg"] = f"Đã cập nhật từ file: thêm {len(added)}, sửa {len(updated)}"
                st.session_state["_tracking_editor_version"] = st.session_state.get("_tracking_editor_version", 0) + 1
                st.rerun()

def _cell(value):
    """Giá trị ô bảng → None nếu trống (None / NaN / NaT / chuỗi rỗng)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return value

def tracking_sort_key(item):
    """Mục đang mở trước, Đóng/Hủy xuống cuối; trong mỗi nhóm ID AEGONA lớn ở trên (#40, #37, #35...).
    Mục chưa có ID (việc mới, chưa lên ticket AEGONA) đứng đầu nhóm."""
    ext = str(item.get("ext_id") or "").strip().lstrip("#")
    num = int(ext) if ext.isdigit() else float("inf")
    return (item.get("status") in TRACKING_CLOSED, -num, -(item.get("id") or 0))

def month_label(work_month):
    """'2026-10' → 'T10/2026'."""
    try:
        year, month = str(work_month).split("-")
        return f"T{int(month)}/{year}"
    except ValueError:
        return str(work_month or "")

def hours_to_md(hours):
    return round(float(hours or 0) / HOURS_PER_MD, 2)

def saved_month_totals():
    """Tổng giờ từng tháng đúng như ô 'Tổng số giờ đã triển khai' của file báo cáo AEGONA (lưu khi đồng bộ file)."""
    try:
        return json.loads(db.get_settings().get(MONTH_TOTALS_KEY) or "{}")
    except ValueError:
        return {}

def tracking_month_summary(items):
    """Giờ/MD theo tháng tính giờ (work_month) so với hạn mức hợp đồng AEGONA. Tháng nào có tổng lấy từ file
    thì dùng đúng số của file (công thức trong file có thể chừa dòng chuyển từ tháng trước), không thì tự cộng."""
    months = {}
    for i in items:
        m = i.get("work_month")
        if not m:
            continue
        s = months.setdefault(m, {"count": 0, "eta": 0.0, "actual": 0.0})
        s["count"] += 1
        s["eta"] += float(i.get("eta_hours") or 0)
        s["actual"] += float(i.get("actual_hours") or 0)
    for m, t in saved_month_totals().items():
        s = months.setdefault(m, {"count": 0, "eta": 0.0, "actual": 0.0})
        s["eta"], s["actual"] = float(t.get("eta") or 0), float(t.get("actual") or 0)
    return dict(sorted(months.items()))

def render_tracking_kpis(items):
    summary = tracking_month_summary(items)
    total_hours = sum(s["actual"] for s in summary.values())
    this_month = now_vn().strftime("%Y-%m")
    month_hours = summary.get(this_month, {}).get("actual", 0.0)
    open_items = [i for i in items if i.get("status") not in TRACKING_CLOSED]
    waiting = [i for i in open_items if i.get("status") in ("Đang testing", "Chờ deploy", "Chờ cập nhật")]
    quota_md = hours_to_md(AGN_MONTHLY_QUOTA_HOURS)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng MD đã dùng", f"{hours_to_md(total_hours):g} MD", help=f"{total_hours:g} giờ thực tế · 1 MD = {HOURS_PER_MD} giờ",
              border=True)
    k2.metric(f"MD {month_label(this_month)}", f"{hours_to_md(month_hours):g} / {quota_md:g} MD",
              help=f"{month_hours:g} / {AGN_MONTHLY_QUOTA_HOURS} giờ hạn mức tháng", border=True)
    k3.metric("Ticket đang mở", len(open_items), border=True)
    k4.metric("Đang testing / chờ deploy", len(waiting), border=True)

def render_tracking_month_table(items):
    """Bảng tổng theo tháng: số ticket, giờ ETA/thực tế, MD, hạn mức, vượt hạn mức + dòng tổng."""
    summary = tracking_month_summary(items)
    if not summary:
        st.info("Chưa có dữ liệu giờ theo tháng — tải file báo cáo AEGONA ở mục 📥 bên dưới.")
        return
    rows = []
    for m, s in summary.items():
        rows.append({
            "Tháng": month_label(m), "Số ticket": s["count"], "ETA (giờ)": s["eta"], "Thực tế (giờ)": s["actual"],
            "MD": hours_to_md(s["actual"]), "Hạn mức (giờ)": AGN_MONTHLY_QUOTA_HOURS,
            "Vượt hạn mức (giờ)": max(s["actual"] - AGN_MONTHLY_QUOTA_HOURS, 0),
            "% hạn mức": round(s["actual"] / AGN_MONTHLY_QUOTA_HOURS * 100),
        })
    total_actual = sum(s["actual"] for s in summary.values())
    rows.append({
        "Tháng": "TỔNG", "Số ticket": sum(s["count"] for s in summary.values()),
        "ETA (giờ)": sum(s["eta"] for s in summary.values()), "Thực tế (giờ)": total_actual,
        "MD": hours_to_md(total_actual), "Hạn mức (giờ)": AGN_MONTHLY_QUOTA_HOURS * len(summary),
        "Vượt hạn mức (giờ)": sum(r["Vượt hạn mức (giờ)"] for r in rows),
        "% hạn mức": round(total_actual / (AGN_MONTHLY_QUOTA_HOURS * len(summary)) * 100),
    })
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, width="stretch",
        column_config={
            "ETA (giờ)": st.column_config.NumberColumn(format="%.2f"),
            "Thực tế (giờ)": st.column_config.NumberColumn(format="%.2f"),
            "MD": st.column_config.NumberColumn("MD (8 giờ)", format="%.2f"),
            "Vượt hạn mức (giờ)": st.column_config.NumberColumn(format="%.2f"),
            "% hạn mức": st.column_config.ProgressColumn("% hạn mức", format="%d%%", min_value=0, max_value=100),
        },
    )

def render_tracking_md_pivot(shown):
    """Mỗi ticket 1 dòng, mỗi tháng 1 cột MD (giờ thực tế / 8) + cột Tổng MD + dòng TỔNG cuối bảng."""
    months = sorted({i["work_month"] for i in shown if i.get("work_month")})
    if not months:
        st.info("Các ticket đang lọc chưa có giờ theo tháng.")
        return
    rows = []
    for i in shown:
        # Không làm tròn từng ticket (0.25h = 0.03125 MD) để dòng TỔNG khớp tổng giờ / 8; bảng tự hiện 2 số lẻ
        md = float(i["actual_hours"]) / HOURS_PER_MD if i.get("actual_hours") is not None else None
        rows.append({
            "ID": i.get("ext_id") or "", "Tiêu đề": (i.get("title") or "").splitlines()[0],
            "Trạng thái": i.get("status") or "", "TT AEGONA": i.get("agn_status") or "",
            "Hệ thống": i.get("system_name") or "",
            "ETA (giờ)": float(i["eta_hours"]) if i.get("eta_hours") is not None else None,
            "Thực tế (giờ)": float(i["actual_hours"]) if i.get("actual_hours") is not None else None,
            **{month_label(m): (md if i.get("work_month") == m else None) for m in months},
            "Tổng MD": md,
        })
    df = pd.DataFrame(rows)
    total = {"ID": "", "Tiêu đề": "TỔNG", "Trạng thái": "", "TT AEGONA": "", "Hệ thống": ""}
    for col in ["ETA (giờ)", "Thực tế (giờ)", *[month_label(m) for m in months], "Tổng MD"]:
        total[col] = df[col].sum() if df[col].notna().any() else None
    df = pd.concat([df, pd.DataFrame([total])], ignore_index=True)
    number_cols = {col: st.column_config.NumberColumn(col, format="%.2f", width="small")
                   for col in ["ETA (giờ)", "Thực tế (giờ)", *[month_label(m) for m in months], "Tổng MD"]}
    st.dataframe(
        df, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 640),
        column_config={
            "ID": st.column_config.TextColumn("ID", width="small"),
            "Tiêu đề": st.column_config.TextColumn("Tiêu đề", width="large"),
            **number_cols,
        },
    )

def render_ticket_tracking_editor(items, logs, start_date, end_date):
    """Theo dõi ticket bên ngoài (AEGONA...): số liệu MD theo tháng, bộ lọc, bảng cập nhật trạng thái bằng dropdown.
    Đổi trạng thái được ghi log → báo cáo tuần ghi 'trạng thái cũ → mới' kèm ngày."""
    msg = st.session_state.pop("_tracking_msg", None)
    if msg:
        st.toast(msg)
    render_tracking_kpis(items)

    # --- Bộ lọc (dùng chung cho bảng cập nhật và bảng MD theo tháng) ---
    all_months = sorted({i["work_month"] for i in items if i.get("work_month")}, reverse=True)
    systems = sorted({i["system_name"] for i in items if i.get("system_name")})
    with st.container(border=True):
        f1, f2, f3, f4, f5 = st.columns([2.2, 2, 1.4, 1.4, 1.3], vertical_alignment="bottom")
        search = f1.text_input("🔎 Tìm ID / tiêu đề / module", key="trk_search", placeholder="VD: 37, UrBox, An Gia...")
        statuses = f2.multiselect("Trạng thái", TRACKING_STATUSES, key="trk_status", placeholder="Tất cả")
        months = f3.multiselect("Tháng tính giờ", all_months, format_func=month_label, key="trk_month", placeholder="Tất cả")
        sys_filter = f4.multiselect("Hệ thống", systems, key="trk_system", placeholder="Tất cả")
        show_closed = f5.toggle("Hiện Đóng/Hủy", value=False, key="tracking_show_closed",
                                help="Bật để xem cả mục đã Đóng/Hủy (xếp cuối bảng)")

    def match(i, include_closed=False):
        if statuses:
            if i.get("status") not in statuses:
                return False
        elif not (show_closed or include_closed) and i.get("status") in TRACKING_CLOSED:
            return False
        if months and i.get("work_month") not in months:
            return False
        if sys_filter and i.get("system_name") not in sys_filter:
            return False
        if search.strip():
            q = search.strip().lower().lstrip("#")
            hay = " ".join(str(i.get(f) or "") for f in ("ext_id", "title", "module", "note", "assignee")).lower()
            return q in hay
        return True

    shown = sorted((i for i in items if match(i)), key=tracking_sort_key)
    # Bảng MD luôn tính cả mục Đóng/Hủy (phần lớn giờ nằm ở ticket đã đóng), vẫn theo các bộ lọc khác
    shown_md = sorted((i for i in items if match(i, include_closed=True)), key=tracking_sort_key)
    st.caption(f"Đang hiện **{len(shown)}**/{len(items)} mục · mở trước, Đóng/Hủy cuối · ID AEGONA lớn ở trên.")

    tab_edit, tab_md, tab_month, tab_log = st.tabs(
        ["✏️ Cập nhật trạng thái", "📊 MD theo ticket & tháng", "🗓️ Tổng theo tháng", "🕑 Đổi trạng thái trong tuần"]
    )
    with tab_edit:
        render_tracking_edit_table(shown, all_months)
    with tab_md:
        render_tracking_md_pivot(shown_md)
        st.caption("Bảng này luôn tính cả mục Đóng/Hủy. Ô trống = ticket không tính giờ vào tháng đó.")
    with tab_month:
        render_tracking_month_table(items)
        st.caption(f"Hạn mức hợp đồng AEGONA: {AGN_MONTHLY_QUOTA_HOURS} giờ/tháng · MD = giờ thực tế / {HOURS_PER_MD}.")
    with tab_log:
        # Các lần đổi trạng thái trong tuần đang xem — đúng nội dung sẽ vào báo cáo
        items_by_id = {i["id"]: i for i in items}
        week_logs = [l for l in logs if to_date(l.get("created_at")) and start_date <= to_date(l["created_at"]) <= end_date]
        if not week_logs:
            st.info("Không có lần đổi trạng thái nào trong tuần đang xem.")
        for l in reversed(week_logs):
            item = items_by_id.get(l["tracking_id"], {})
            change = f"{l['old_status']} → {l['new_status']}" if l.get("old_status") else f"Thêm mới: {l['new_status']}"
            title = str(item.get("title") or "").splitlines()[0] if item.get("title") else ""
            st.markdown(
                f"- **{to_date(l['created_at']).strftime('%d/%m')}** · {html.escape(str(item.get('ext_id') or ''))} "
                f"{html.escape(title)} — {change}"
            )

# Cột trên bảng cập nhật → trường trong ticket_tracking
TRACKING_EDIT_COLUMNS = {
    "Trạng thái": "status", "ID": "ext_id", "Tiêu đề": "title", "Ưu tiên": "priority", "Tháng tính giờ": "work_month",
    "ETA (giờ)": "eta_hours", "Thực tế (giờ)": "actual_hours", "Lên Production": "prod_date",
    "Người thực hiện": "assignee", "Ghi chú": "note", "Hệ thống": "system_name", "Module": "module",
    "Nhóm": "category", "Nội dung cập nhật": "content", "Source code": "source_code",
}
TRACKING_DETAIL_COLUMNS = ["Hệ thống", "Module", "Nhóm", "Nội dung cập nhật", "Source code"]

def render_tracking_edit_table(shown, all_months):
    """Bảng sửa trực tiếp (dropdown Trạng thái/Ưu tiên/Tháng...) → bấm Lưu. Không dùng cột khóa (disabled)
    vì lưới hiển thị chữ cột khóa màu nhạt, khó đọc."""
    label_to_key = {label: key for key, label in WORK_NOTE_LABELS.items()}
    show_detail = st.toggle("Hiện cột chi tiết (Hệ thống, Module, Nhóm, Nội dung cập nhật, Source code)",
                            value=False, key="trk_show_detail")
    this_month = now_vn().date().replace(day=1)
    month_options = sorted(set(all_months) | {
        (this_month - datetime.timedelta(days=31 * k)).strftime("%Y-%m") for k in range(-1, 6)
    }, reverse=True)

    def to_row(i):
        row = {"id": i["id"]}
        for col, field in TRACKING_EDIT_COLUMNS.items():
            value = i.get(field)
            if field in ("eta_hours", "actual_hours"):
                value = float(value) if value is not None else None
            elif field == "prod_date":
                value = to_date(value)
            elif field == "category":
                value = WORK_NOTE_LABELS.get(value, value)
            elif field not in ("status", "priority", "work_month"):
                value = value or ""
            row[col] = value
        return row

    columns = ["id", *TRACKING_EDIT_COLUMNS]
    original = pd.DataFrame([to_row(i) for i in shown], columns=columns)
    order = ["Trạng thái", "ID", "Tiêu đề", "Ưu tiên", "Tháng tính giờ", "ETA (giờ)", "Thực tế (giờ)",
             "Lên Production", "Người thực hiện", "Ghi chú"]
    if show_detail:
        order += TRACKING_DETAIL_COLUMNS
    version = st.session_state.get("_tracking_editor_version", 0)
    edited = st.data_editor(
        original,
        key=f"tracking_editor_{hash(tuple(original['id']))}_{show_detail}_{version}",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        height=min(42 + 56 * (len(original) + 1), 720),
        row_height=56,
        column_order=order,
        column_config={
            "Trạng thái": st.column_config.SelectboxColumn("Trạng thái", options=TRACKING_STATUSES, default="Mới", required=True, width="small"),
            "ID": st.column_config.TextColumn("ID", width=60, help="ID AEGONA, VD: #40"),
            "Tiêu đề": st.column_config.TextColumn("Tiêu đề", width="large", required=True),
            "Ưu tiên": st.column_config.SelectboxColumn("Ưu tiên", options=TRACKING_PRIORITIES, width="small"),
            "Tháng tính giờ": st.column_config.SelectboxColumn("Tháng", options=month_options, width="small",
                                                               help="Tháng AEGONA tính giờ (dạng YYYY-MM)"),
            "ETA (giờ)": st.column_config.NumberColumn("ETA (h)", min_value=0, step=0.25, format="%.2f", width="small"),
            "Thực tế (giờ)": st.column_config.NumberColumn("Thực tế (h)", min_value=0, step=0.25, format="%.2f", width="small",
                                                          help=f"Giờ thực tế; MD = giờ / {HOURS_PER_MD}"),
            "Lên Production": st.column_config.DateColumn("Lên Prod", format="DD/MM/YYYY", width="small"),
            "Người thực hiện": st.column_config.TextColumn("Người TH", width="small"),
            "Ghi chú": st.column_config.TextColumn("Ghi chú", width="medium"),
            "Hệ thống": st.column_config.TextColumn("Hệ thống", width="small"),
            "Module": st.column_config.TextColumn("Module", width="medium"),
            "Nhóm": st.column_config.SelectboxColumn("Nhóm", options=list(label_to_key), default=WORK_NOTE_LABELS["gree_app"], required=True, width="small"),
            "Nội dung cập nhật": st.column_config.TextColumn("Nội dung cập nhật", width="large"),
            "Source code": st.column_config.TextColumn("Source code", width="small"),
        },
    )
    if not st.button("💾 Lưu bảng theo dõi ticket", type="primary", key="btn_save_tracking"):
        return
    original_by_id = {int(r["id"]): r for r in original.to_dict("records")}
    kept_ids, added, updated = set(), [], []
    for row in edited.to_dict("records"):
        title = str(_cell(row.get("Tiêu đề")) or "").strip()
        if not title:
            continue
        item = {}
        for col, field in TRACKING_EDIT_COLUMNS.items():
            value = _cell(row.get(col))
            if field == "ext_id":
                value = normalize_ext_id(value)
            elif field == "category":
                value = label_to_key.get(value, "gree_app")
            elif field == "prod_date":
                value = to_date(value) if value is not None else None
            elif field in ("eta_hours", "actual_hours"):
                value = float(value) if value is not None else None
            elif isinstance(value, str):
                value = value.strip() or None
            item[field] = value
        item["title"] = title
        item["status"] = item["status"] or "Mới"
        if _cell(row.get("id")) is None:
            added.append(item)
            continue
        item_id = int(row["id"])
        kept_ids.add(item_id)
        old = original_by_id[item_id]
        changes = {field: item[field] for col, field in TRACKING_EDIT_COLUMNS.items()
                   if not same_value(_cell(old.get(col)), _cell(row.get(col)))}
        if changes:
            # Gửi đủ các trường đã đổi (đã chuẩn hóa); db chỉ UPDATE các trường có trong dict
            updated.append(dict(changes, id=item_id))
    deleted_ids = [i for i in original_by_id if i not in kept_ids]
    if db.save_ticket_tracking_changes(added, updated, deleted_ids):
        st.session_state["_tracking_msg"] = f"Đã lưu: thêm {len(added)}, sửa {len(updated)}, xóa {len(deleted_ids)}"
        st.session_state["_tracking_editor_version"] = st.session_state.get("_tracking_editor_version", 0) + 1
        st.rerun()

def render_ai_notes_paste_box():
    """Dán JSON do AI tổng hợp (ChatGPT/Claude trên web...) → đưa vào hàng chờ duyệt."""
    with st.expander("📥 Dán JSON từ AI vào hàng chờ"):
        st.caption(
            'Định dạng: `{"notes": [{"date": "2026-10-13", "category": "erp", "content": "..."}]}` — '
            "category: erp / warranty / gree_app / it. Chi tiết xem `ai_notes.py`."
        )
        raw = st.text_area("JSON", height=160, key="ai_notes_raw", label_visibility="collapsed")
        if st.button("➕ Đưa vào hàng chờ duyệt", key="btn_ai_notes_import"):
            notes, errors = parse_notes_json(raw)
            if errors:
                st.error("Chưa thêm gì vì có lỗi:\n\n" + "\n".join(f"- {e}" for e in errors))
            elif not notes:
                st.warning("Không có ghi chú nào.")
            elif db.add_work_note_drafts(notes, source="AI (dán)"):
                st.session_state["_drafts_msg"] = f"Đã thêm {len(notes)} ghi chú vào hàng chờ duyệt."
                st.rerun()

def render_note_drafts_review(start_date, end_date):
    """Ghi chú AI đưa vào của tuần đang xem: sửa nếu cần, tick chọn rồi Duyệt (→ work_notes) hoặc Bỏ."""
    msg = st.session_state.pop("_drafts_msg", None)
    if msg:
        st.success(msg)
    drafts = db.get_work_note_drafts()
    week_drafts = [d for d in drafts if start_date <= to_date(d["note_date"]) <= end_date]
    other_weeks = sorted({to_date(d["note_date"]) for d in drafts} - {to_date(d["note_date"]) for d in week_drafts})
    if other_weeks:
        st.caption(
            f"ℹ️ Còn {len(drafts) - len(week_drafts)} ghi chú chờ duyệt ở tuần khác "
            f"(ngày: {', '.join(d.strftime('%d/%m') for d in other_weeks)}) — chọn tuần đó ở trên để duyệt."
        )
    if not week_drafts:
        st.info("Không có ghi chú nào đang chờ duyệt trong tuần này.")
        return

    label_to_key = {label: key for key, label in WORK_NOTE_LABELS.items()}
    original = pd.DataFrame(
        [
            {"id": d["id"], "Chọn": True, "Ngày": to_date(d["note_date"]),
             "Nhóm": WORK_NOTE_LABELS.get(d["category"], d["category"]), "Nội dung": d["content"],
             "Nguồn": d.get("source") or ""}
            for d in week_drafts
        ],
        columns=["id", "Chọn", "Ngày", "Nhóm", "Nội dung", "Nguồn"],
    )
    version = st.session_state.get("_drafts_editor_version", 0)
    # row_height > 64px thì Streamlit tự xuống dòng trong ô → đọc hết nội dung dài khi review.
    # Ước ~70 ký tự/dòng, ~21px/dòng; giới hạn 8 dòng (dài hơn thì bấm đúp vào ô để xem/sửa).
    max_lines = max((len(str(d["content"] or "")) // 70 + 1 + str(d["content"] or "").count("\n") for d in week_drafts), default=1)
    row_height = max(70, min(max_lines, 8) * 21 + 14)
    edited = st.data_editor(
        original,
        key=f"drafts_editor_{start_date}_{version}",
        hide_index=True,
        width="stretch",
        row_height=row_height,
        column_order=["Chọn", "Ngày", "Nhóm", "Nội dung", "Nguồn"],
        disabled=["Nguồn"],
        column_config={
            "Chọn": st.column_config.CheckboxColumn("Chọn", width="small"),
            "Ngày": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY", required=True),
            "Nhóm": st.column_config.SelectboxColumn("Nhóm", options=list(label_to_key), required=True),
            "Nội dung": st.column_config.TextColumn("Nội dung", width="large", required=True),
            "Nguồn": st.column_config.TextColumn("Nguồn", width="small"),
        },
    )
    selected = [r for r in edited.to_dict("records") if r.get("Chọn")]
    b1, b2, _ = st.columns([1, 1, 2])
    if b1.button(f"✅ Duyệt {len(selected)} mục đã chọn", type="primary", disabled=not selected, key="btn_approve_drafts"):
        approved = []
        for r in selected:
            content = str(r.get("Nội dung") or "").strip()
            if content and r.get("Nhóm"):
                approved.append({
                    "id": int(r["id"]), "content": content, "category": label_to_key[r["Nhóm"]],
                    "note_date": to_date(r.get("Ngày")) or to_date(original.loc[original["id"] == r["id"], "Ngày"].iloc[0]),
                })
        if db.approve_work_note_drafts(approved):
            st.session_state["_drafts_msg"] = f"Đã duyệt {len(approved)} ghi chú — đã vào báo cáo tuần."
            st.session_state["_drafts_editor_version"] = version + 1
            st.session_state["_notes_editor_version"] = st.session_state.get("_notes_editor_version", 0) + 1
            st.rerun()
    if b2.button(f"🗑️ Bỏ {len(selected)} mục đã chọn", disabled=not selected, key="btn_reject_drafts"):
        if db.delete_work_note_drafts([int(r["id"]) for r in selected]):
            st.session_state["_drafts_msg"] = f"Đã bỏ {len(selected)} ghi chú."
            st.session_state["_drafts_editor_version"] = version + 1
            st.rerun()

# -----------------
# THANH ĐIỀU HƯỚNG (SIDEBAR)
# -----------------

# Khởi tạo trạng thái sitemap page mặc định
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "🏠 Trang chủ"

# Áp dụng điều hướng đang chờ (do goto_ticket_detail đặt) trước khi radio được tạo
if "_pending_page" in st.session_state:
    st.session_state["selected_page"] = st.session_state.pop("_pending_page")

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    st.title(Config.APP_NAME)
    st.markdown(f"**Owner:** {Config.OWNER}")
    #st.markdown(f"**Domain:** [{Config.BASE_DOMAIN}{Config.SUB_PATH}](https://{Config.BASE_DOMAIN}{Config.SUB_PATH})")
    st.markdown("---")
    
    # Menu: guest thấy 5 trang, admin thấy thêm Cài đặt
    base_menu = [
        "🏠 Trang chủ",
        "🛡️ Hệ thống Bảo hành",
        "🏭 Quản trị ERP",
        "📱 Gree App Support",
        "📈 Báo cáo tuần của Nam",
    ]
    # Báo cáo Ticket (cho Sếp) và Cài đặt chỉ hiện khi đã đăng nhập Admin
    menu = base_menu + ["📊 Báo cáo Ticket", "⚙️ Cài đặt"] if is_admin() else base_menu

    # Nếu guest đang ở trang bị ẩn → reset về trang chủ
    if st.session_state.get("selected_page") not in menu:
        st.session_state["selected_page"] = "🏠 Trang chủ"

    page = st.radio("SITEMAP HỆ THỐNG", menu, key="selected_page")

    st.markdown("---")

    # --- ADMIN LOGIN / LOGOUT ---
    if is_admin():
        st.success(f"🔐 {ADMIN_USERNAME}")
        st.caption(f"Ghi nhớ đăng nhập {ADMIN_SESSION_DAYS} ngày trên trình duyệt này.")
        if st.button("🚪 Đăng xuất", use_container_width=True, key="btn_logout"):
            logout_admin()
            st.rerun()
        with st.expander("📝 Ghi chú công việc nhanh"):
            render_quick_note_form()
    else:
        with st.expander("🔐 Admin Login"):
            pw_input = st.text_input("Mật khẩu", type="password", key="admin_pw_input")
            if st.button("Đăng nhập", use_container_width=True, key="btn_admin_login"):
                if check_admin_password(pw_input):
                    login_admin()
                    st.rerun()
                elif ADMIN_PASSWORD:
                    st.error("Sai mật khẩu!")

    st.markdown("---")
    st.caption(f"📅 {datetime.date.today()}")

# -----------------
# RENDER TRANG QUẢN LÝ TICKET (DÙNG CHUNG CHO NHIỀU DOMAIN: BẢO HÀNH / ERP / ...)
# -----------------
def render_field_inputs_for_form(form_choice_type):
    """Render các input field theo từng loại Form, trả về dict form_data.
    Dùng chung cho mọi domain ticket (Bảo hành, ERP, ...)."""
    form_data = {}
    if form_choice_type == "Khai_Bao_Model_Bao_Hanh":
        left_col, right_col = st.columns(2)
        with left_col:
            form_data['model_name'] = st.text_input("Tên Model", placeholder="Ví dụ: GWC12PB-K3D0P4")
            form_data['cost_type'] = st.selectbox("Loại chi phí", ["CAC", "GD - RAC", "ĐH - RAC", "RAC - CT"])
            form_data['product_type'] = st.selectbox("Loại sản phẩm", [
                "BĐT - Bếp điện từ", 
                "Điều hòa dân dụng, treo tường tú đứng dưới 10Hp (RAC)", 
                "MHA - Máy hút ẩm", 
                "MLKK - Máy lọc không khí", 
                "MLM - Máy làm mát bằng hơi nước", 
                "Multi, máy âm trần, âm trần nối ống gió, áp trần (CAC)", 
                "NAS - Nồi áp suất", 
                "NCĐ - nồi cơm điện", 
                "Ống gió lớn, Tú đứng lớn, máy lạnh chính xác", 
                "QĐ - Quạt điện", 
                "VRV/VRF(CAC)", 
                "Water cooled packge Chiller"
            ])
        with right_col:
            form_data['capacity_range'] = st.selectbox("Công suất", [
                "9.000 - 18.000 Btu", "9.000 - 36.000 Btu", "24.000 - 36.000 Btu", 
                "36.000 - 42.000 Btu", "42.000 - 60.000 Btu", "100.000 - 200.000 Btu", 
                "10Hp - 24Hp", "10Hp - 60Hp"
            ])
            form_data['note'] = st.text_area("Ghi chú", height=96, placeholder="Thông tin bổ sung nếu có")
    elif form_choice_type == "Khai_Bao_Ma_Linh_Kien":
        form_data['part_code'] = st.text_input("Mã linh kiện")
        form_data['part_name_en'] = st.text_input("Tên linh kiện (EN)")
        form_data['part_name_vi'] = st.text_input("Tên linh kiện (VI)")
        form_data['description'] = st.text_area("Mô tả")
    elif form_choice_type == "Yeu_Cau_Dieu_Chinh_Ton_Kho":
        left_col, right_col = st.columns(2)
        with left_col:
            form_data['warehouse'] = st.text_input("Kho/Trạm", placeholder="Ví dụ: Hưng Yên - RAC")
            form_data['part_code'] = st.text_input("Mã linh kiện", placeholder="Ví dụ: GMC42S6I1")
            form_data['part_nature'] = st.selectbox("Tính chất linh kiện", ["", "Linh kiện mượn", "Linh kiện mua"])
            form_data['evidence_image_url'] = st.text_input("Link ảnh bằng chứng", placeholder="https://prnt.sc/...")
        with right_col:
            form_data['export_voucher'] = st.text_input("Phiếu xuất", placeholder="Để trống nếu chưa có")
            form_data['adjusted_quantity'] = st.number_input("Số lượng điều chỉnh", min_value=0, value=1)
            form_data['note'] = st.text_area(
                "Ghi chú xử lý",
                height=140,
                placeholder="Mô tả lệch tồn, hướng xử lý, lưu ý cho kho/trạm",
            )
    elif form_choice_type == "Dang_Ky_Tram_Bao_Hanh_Moi":
        left_col, right_col = st.columns(2)
        with left_col:
            st.markdown("**Thông tin công ty**")
            company_name = st.text_input("Tên công ty / Trạm", placeholder="Ví dụ: CÔNG TY TNHH TM DV A.T.P")
            tax_code = st.text_input("Mã số thuế", placeholder="Ví dụ: 0301841221")
            tax_address = st.text_area("Địa chỉ thuế", height=90)
            postal_address = st.text_area("Địa chỉ nhận thư", height=90)
            email = st.text_input("Email", placeholder="email@domain.com")
            phone = st.text_input("Điện thoại", placeholder="Ví dụ: 0916318948")
            system_username = st.text_input("User hệ thống", placeholder="Ví dụ: a.t.p-hochiminh")
        with right_col:
            st.markdown("**Tài khoản & cấu trúc liên quan**")
            bank_account = st.text_input("Số tài khoản")
            bank_account_name = st.text_input("Tên tài khoản ngân hàng")
            bank_name = st.text_input("Ngân hàng")
            technicians_raw = st.text_area(
                "Danh sách KTV",
                height=120,
                placeholder="Mỗi dòng: Tên KTV | SĐT | Username",
            )
            warehouses_raw = st.text_area(
                "Danh sách kho liên kết",
                height=120,
                placeholder="Mỗi dòng: Loại kho | Tên kho | Email",
            )
        form_data = {
            "company_info": {
                "name": company_name,
                "tax_code": tax_code,
                "tax_address": tax_address,
                "postal_address": postal_address,
                "email": email,
                "phone": phone,
                "bank_account": bank_account,
                "bank_account_name": bank_account_name,
                "bank_name": bank_name,
                "system_username": system_username,
            },
            "technicians": parse_pipe_rows(technicians_raw, ["name", "phone", "username"]),
            "associated_warehouses": parse_pipe_rows(warehouses_raw, ["type", "name", "email"]),
        }
    elif form_choice_type == "Dang_Ky_Tai_Khoan_User_Noi_Bo":
        left_col, right_col = st.columns(2)
        with left_col:
            form_data['full_name'] = st.text_input("Họ tên", placeholder="Ví dụ: Võ Thanh Tùng")
            form_data['phone'] = st.text_input("Điện thoại", placeholder="Ví dụ: 0797 704 205")
            form_data['company_email'] = st.text_input("Email Gree", placeholder="name@gree.com.vn")
            form_data['user_group'] = st.selectbox(
                "Nhóm user",
                [
                    "Giám đốc BH",
                    "Trưởng phòng BH",
                    "KTV Gree",
                    "Trưởng phòng XNK",
                    "Chuyên viên XNK",
                    "Phòng Thương Mại CAC",
                    "Phòng Quản Trị",
                    "Chuyên viên Kế Hoạch",
                    "Trưởng phòng Kế hoạch",
                    "Trưởng Phòng Call Center",
                    "Chuyên Viên Call Center",
                ],
            )
        with right_col:
            form_data['call_center_line'] = st.text_input("Line Call Center", placeholder="Để trống nếu không áp dụng")
            form_data['main_link'] = st.text_input("Link chính", value="https://warranty.gree.com.vn/")
            test_username = st.text_input("Username test", value="test")
            test_password = st.text_input("Password test", value="123456")
            test_link = st.text_input("Link test", value="http://gree.baohanhso.net/")
            form_data['test_account'] = {
                "username": test_username,
                "password": test_password,
                "test_link": test_link,
            }
    elif form_choice_type == "Khai_Bao_Model_Ho_So_May":
        form_data['model_name'] = st.text_input("Tên Model")
        form_data['machine_type'] = st.selectbox("Loại máy", ["Dàn nóng", "Dàn lạnh"])
        form_data['warranty_months_machine'] = st.number_input("T/g BH Máy (Tháng)", min_value=0, value=24)
        form_data['warranty_months_compressor'] = st.number_input("T/g BH Block (Tháng)", min_value=0, value=36)
    elif form_choice_type == "Admin_Web_Noted_Log_Ho_Tro":
        left_col, right_col = st.columns(2)
        with left_col:
            form_data['case_code'] = st.text_input("Mã ca / Mã chứng từ", placeholder="Ví dụ: MBTH2025080234")
            form_data['it_assignee'] = st.text_input("Người xử lý IT", value="IT - Nam Lê")
            form_data['completion_date'] = st.date_input("Ngày hoàn thành", value=datetime.date.today()).isoformat()
            form_data['evidence_link'] = st.text_input("Link bằng chứng", placeholder="https://prnt.sc/...")
        with right_col:
            form_data['request_detail'] = st.text_area(
                "Nội dung yêu cầu",
                height=120,
                placeholder="Nhập nội dung cần hỗ trợ/can thiệp dữ liệu",
            )
            form_data['internal_action_log'] = st.text_area(
                "Log xử lý nội bộ",
                height=120,
                placeholder="Nhập thao tác đã xử lý, kết quả, lưu ý nội bộ",
            )
    elif form_choice_type == "Import_Bang_Gia_Linh_Kien":
        form_data['part_code'] = st.text_input("Mã linh kiện")
        form_data['part_name_vi'] = st.text_input("Tên linh kiện (VI)")
        form_data['part_name_en'] = st.text_input("Tên linh kiện (EN)")
        form_data['model_group'] = st.text_input("Nhóm Model")
        form_data['product_type'] = st.text_input("Loại sản phẩm")
        form_data['unit_type'] = st.text_input("Loại Unit (Indoor/Outdoor)")
        form_data['price_vat'] = st.number_input("Giá có VAT", min_value=0, value=0)
        form_data['price_no_vat'] = st.number_input("Giá chưa VAT", min_value=0, value=0)
        form_data['classification'] = st.text_input("Phân loại (Vd: CAC)")
        form_data['discount_rate'] = st.text_input("Tỷ lệ chiết khấu (%)")
        form_data['sla_bonus_rate'] = st.text_input("Thưởng SLA (%)")
    elif form_choice_type == "Khai_Bao_Danh_Muc_Chi_Phi":
        form_data['cost_code'] = st.text_input("Mã chi phí")
        form_data['content'] = st.text_input("Nội dung")
        form_data['unit_price'] = st.number_input("Đơn giá", min_value=0, value=0)
        form_data['capacity'] = st.text_input("Công suất (Tùy chọn)")
        form_data['cost_type'] = st.text_input("Loại chi phí")
        form_data['product_group'] = st.text_input("Nhóm sản phẩm")
    elif form_choice_type == "Yeu_Cau_Tong_Hop_Khac":
        form_data['request_title'] = st.text_input(
            "Tiêu đề yêu cầu",
            placeholder="Ví dụ: Hỗ trợ kiểm tra số liệu tồn kho khu vực Hà Nội",
        )
        related_form_options = [
            f["label"] for f in FORM_CONFIGS
            if f["type"] != "Yeu_Cau_Tong_Hop_Khac" and f.get("domain") == "warranty"
        ] + ["Khác (Không thuộc 9 Form trên)"]
        form_data['related_form'] = st.selectbox(
            "Yêu cầu này liên quan đến Form nào?",
            related_form_options,
        )
        form_data['request_detail'] = st.text_area(
            "Nội dung yêu cầu",
            height=160,
            placeholder="Mô tả chi tiết yêu cầu cần hỗ trợ/xử lý...",
        )
    elif form_choice_type == "ERP_Yeu_Cau_Tong_Hop":
        form_data['request_title'] = st.text_input(
            "Tiêu đề yêu cầu",
            placeholder="Ví dụ: Hỗ trợ kiểm tra dữ liệu kho ERP chi nhánh HN",
        )
        form_data['request_category'] = st.selectbox(
            "Loại yêu cầu ERP",
            [
                "Khởi tạo đối tượng (KH/NCC/NV)",
                "Khởi tạo sản phẩm/hàng hóa",
                "Bảng giá mua/bán",
                "Chương trình khuyến mãi",
                "Phê duyệt / phân quyền",
                "Lỗi hệ thống / Issue kỹ thuật",
                "Khác",
            ],
        )
        form_data['request_detail'] = st.text_area(
            "Nội dung yêu cầu",
            height=160,
            placeholder="Mô tả chi tiết yêu cầu cần hỗ trợ/xử lý...",
        )
    elif form_choice_type == "GreeApp_Yeu_Cau_Tong_Hop":
        form_data['request_title'] = st.text_input(
            "Tiêu đề yêu cầu",
            placeholder="Ví dụ: KH không đăng nhập được App phiên bản iOS",
        )
        form_data['request_category'] = st.selectbox(
            "Loại yêu cầu Gree App",
            [
                "Lỗi đăng nhập / Tài khoản",
                "Lỗi hiển thị / Dữ liệu sai",
                "App bị lỗi / Crash",
                "Yêu cầu tính năng mới",
                "Hỗ trợ khách hàng (CSKH)",
                "Khác",
            ],
        )
        form_data['original_ref'] = st.text_input(
            "Mã/Tham chiếu ticket gốc (email)",
            placeholder="Ví dụ: Subject email hoặc mã ticket bên hệ thống Gree App, để truy lại khi cần",
        )
        form_data['request_detail'] = st.text_area(
            "Nội dung yêu cầu",
            height=160,
            placeholder="Mô tả chi tiết yêu cầu cần hỗ trợ/xử lý (tóm tắt nội dung email)...",
        )

    return form_data
def render_ticket_domain_page(state_key, main_title, subtitle, domain_forms, show_master_table=True):
    """Render đầy đủ 1 trang quản lý ticket cho 1 domain (Bảo hành / ERP / ...).
    state_key: tiền tố để cô lập session_state/widget key giữa các trang (vd: 'bh', 'erp').
    domain_forms: subset của FORM_CONFIGS chỉ thuộc domain đang render."""
    st.markdown(f'<div class="main-header">{main_title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">{subtitle}</div>', unsafe_allow_html=True)

    domain_types = set(f["type"] for f in domain_forms)
    domain_tickets = [t for t in db_tickets if normalize_form_type(t.get("form_type")) in domain_types]

    form_scope_options = ["Tất cả Ticket"] + [f["label"] for f in domain_forms]
    selected_scope = st.selectbox(
        "Form đang xem",
        form_scope_options,
        key=f"ticket_form_scope_{state_key}",
    )
    selected_form_type = FORM_LABEL_TO_TYPE.get(selected_scope)
    selected_config = FORM_TYPE_TO_CONFIG.get(selected_form_type)
    scoped_tickets = tickets_for_form(domain_tickets, selected_form_type) if selected_form_type else domain_tickets

    show_key = f"show_create_ticket_{state_key}"
    btn_col, hint_col = st.columns([0.28, 0.72])
    with btn_col:
        if st.button("➕ Tạo Ticket mới", use_container_width=True, disabled=selected_config is None, key=f"btn_toggle_create_{state_key}"):
            st.session_state[show_key] = not st.session_state.get(show_key, False)
    with hint_col:
        if selected_config:
            st.caption(f"Ticket mới sẽ được tạo cho: {selected_scope}")
        else:
            st.caption("Chọn một Form cụ thể để tạo ticket mới.")

    if selected_config and st.session_state.get(show_key, False):
        form_choice = selected_scope
        form_choice_type = selected_form_type
        with st.container(border=True):
            st.subheader(f"➕ Tạo Ticket mới - {selected_scope}")

            t_user = st.text_input("Người yêu cầu", placeholder="Ví dụ: Phượng BH RAC", key=f"t_user_{state_key}")

            form_data = render_field_inputs_for_form(form_choice_type)

            create_col, close_col = st.columns(2)
            if create_col.button("Khởi tạo mã Ticket", use_container_width=True, key=f"create_btn_{state_key}"):
                form5_missing = missing_form5_required_fields(form_data) if form_choice_type == "Dang_Ky_Tai_Khoan_User_Noi_Bo" else []
                general_missing = []
                if form_choice_type in GENERAL_FORM_TYPES and not str(form_data.get('request_detail') or "").strip():
                    general_missing.append("Nội dung yêu cầu")

                if form5_missing:
                    st.warning("Vui lòng nhập đủ thông tin Form 5: " + ", ".join(form5_missing))
                elif general_missing:
                    st.warning("Vui lòng nhập đủ thông tin: " + ", ".join(general_missing))
                elif t_user:
                    form_type = form_choice_type
                    status = "Hoàn thành" if form_choice_type == "Admin_Web_Noted_Log_Ho_Tro" else "Mới tạo"
                    subject = form_choice
                    if form_choice_type in GENERAL_FORM_TYPES and str(form_data.get('request_title') or "").strip():
                        subject = form_data['request_title']

                    new_id = db.create_ticket(subject, t_user, form_type, form_data, status)
                    if new_id:
                        st.success(f"Đã tạo Ticket: {new_id}")
                        st.session_state[show_key] = False
                        st.rerun()
                    else:
                        st.error("Lỗi khi kết nối CSDL")
                else:
                    st.warning("Vui lòng nhập Người yêu cầu")
            if close_col.button("Đóng form", use_container_width=True, key=f"close_btn_{state_key}"):
                st.session_state[show_key] = False
                st.rerun()

    st.markdown("---")

    if show_master_table:
        st.subheader("📊 Dữ liệu danh mục đã cập nhật hệ thống")

        # Xác định loại Form cần hiển thị dựa trên selected_scope ở đầu trang
        master_form_options = [f["label"] for f in domain_forms]

        if selected_scope in master_form_options:
            # Nếu đang chọn một Form cụ thể trên đầu trang
            target_form_label = selected_scope
        else:
            # Nếu đang chọn "Tất cả Ticket", mặc định hiển thị Form đầu tiên của domain
            target_form_label = master_form_options[0]
            st.caption(f"ℹ️ *Đang hiển thị mặc định danh sách '{target_form_label}'. Chọn một Form cụ thể ở ô 'Form đang xem' trên đầu trang để đồng bộ bảng dữ liệu này.*")

        master_form_type = FORM_LABEL_TO_TYPE.get(target_form_label)
        master_config = FORM_TYPE_TO_CONFIG.get(master_form_type)

        if master_config:
            # Lấy tickets của form đó
            form_tickets = tickets_for_form(domain_tickets, master_form_type)
            master_status_filter = st.selectbox(
                "🔍 Lọc trạng thái bản ghi",
                ["Tất cả"] + STATUS_LIST,
                key=f"master_filter_{state_key}_{master_form_type}",
            )
            master_tickets = form_tickets if master_status_filter == "Tất cả" else [
                t for t in form_tickets if t["status"] == master_status_filter
            ]
            master_rows = build_form_rows(sort_tickets_for_display(master_tickets), master_config)
            if master_rows:
                st.dataframe(pd.DataFrame(master_rows), use_container_width=True)
            else:
                st.info(f"Chưa có dữ liệu hoặc không có bản ghi nào ở trạng thái '{master_status_filter}' cho form này.")
        else:
            st.info("Không tìm thấy cấu hình hiển thị dữ liệu cho Form này.")

        st.divider()

    col_list, col_detail = st.columns([0.45, 0.55])
    active_key = f"active_ticket_id_{state_key}"

    with col_list:
        st.subheader("📋 Danh sách Ticket")
        ticket_filter = st.selectbox("🔍 Lọc trạng thái", ["Tất cả"] + STATUS_LIST, key=f"ticket_filter_{state_key}")
        search_query = st.text_input(
            "🔎 Tìm kiếm",
            key=f"ticket_search_{state_key}",
            placeholder="Nhập mã ticket, tiêu đề hoặc người yêu cầu...",
        )
        filtered_tickets = scoped_tickets if ticket_filter == "Tất cả" else [
            t for t in scoped_tickets if t["status"] == ticket_filter
        ]
        if search_query.strip():
            q = search_query.strip().lower()
            filtered_tickets = [
                t for t in filtered_tickets
                if q in t['id'].lower() or q in t['subject'].lower() or q in t['requester'].lower()
            ]
        filtered_tickets = sort_tickets_for_display(filtered_tickets)

        if not filtered_tickets:
            st.info("Không có ticket nào trong phạm vi đang chọn.")
        else:
            # 1 bảng thay cho mỗi ticket 1 khung + 1 nút (trước đây ~100 widget/trang nên rất chậm)
            st.caption("Bấm vào ô đầu dòng để xem chi tiết ticket.")
            table_ids = [t["id"] for t in filtered_tickets]
            event = st.dataframe(
                pd.DataFrame(ticket_table_rows(filtered_tickets)),
                # Key đổi khi danh sách/thứ tự đổi → bỏ dòng đang chọn cũ, tránh chỉ số dòng trỏ nhầm ticket khác
                key=f"ticket_table_{state_key}_{hash(tuple(table_ids))}",
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True,
                width="stretch",
                height=min(38 + 35 * len(table_ids), 600),
            )
            selected_rows = event.selection.rows
            selected_id = table_ids[selected_rows[0]] if selected_rows else None
            # Chỉ áp dụng khi người dùng vừa chọn dòng khác, để không ghi đè ticket mở từ trang chủ
            last_key = f"_last_table_selection_{state_key}"
            if selected_id != st.session_state.get(last_key):
                st.session_state[last_key] = selected_id
                if selected_id:
                    st.session_state[active_key] = selected_id

    with col_detail:
        st.subheader("💬 Luồng xử lý (Chat-log)")
        active_ticket_id = st.session_state.get(active_key)
        active_candidates = [t for t in scoped_tickets if t["id"] == active_ticket_id]
        if active_ticket_id and not active_candidates:
            st.info("Ticket đang chọn không thuộc Form/phạm vi hiện tại. Hãy chọn ticket bên trái.")
        elif active_candidates:
            current_t = active_candidates[0]
            st.markdown(
                f"**{current_t['id']}** &nbsp; {status_badge(current_t['status'])} &nbsp; "
                f"<span style='color:#6B7280;font-size:0.9em;'>Đã mở {aging_label(current_t)}</span>",
                unsafe_allow_html=True,
            )
            # Đường dẫn chia sẻ ticket nhanh dành cho BA/Admin
            st.markdown("🔗 **Liên kết chia sẻ ticket nhanh (BA-Share):**")

            ticket_json = json.dumps(current_t['id'])

            share_html = (
                "<div style='font-family: Inter, sans-serif; font-size: 0.95rem; color: #111;'>"
                "  <div style='margin-bottom: 0.5rem;'>"
                "    <span style='font-weight: 600;'>Link hiện tại:</span>"
                "  </div>"
                "  <div style='display: flex; align-items: center; gap: 0.75rem;'>"
                "    <code id='share_url_text' style='display: inline-block; padding: 0.6rem 0.8rem; background: #f7f7f8; border-radius: 0.75rem; color: #0f172a; overflow-x: auto; white-space: nowrap; max-width: 100%;'>Đang tạo...</code>"
                "    <button id='copy_button' style='border: none; padding: 0.6rem 1rem; border-radius: 0.75rem; background: #2563eb; color: white; cursor: pointer;'>Copy</button>"
                "  </div>"
                "  <div style='margin-top: 0.5rem;'>"
                "    <a id='share_url_link' href='#' target='_blank' rel='noreferrer' style='color: #2563eb; text-decoration: none; font-weight: 600;'></a>"
                "  </div>"
                "</div>"
                "<script>"
                "const ticketId = " + ticket_json + ";"
                "try {"
                "  const origin = window.parent.location.origin;"
                "  const shareUrl = origin + '/?ticket=' + ticketId;"
                "  const textEl = document.getElementById('share_url_text');"
                "  const linkEl = document.getElementById('share_url_link');"
                "  const copyButton = document.getElementById('copy_button');"
                "  if (textEl) { textEl.textContent = shareUrl; }"
                "  if (linkEl) { linkEl.href = shareUrl; linkEl.textContent = 'Mở liên kết'; }"
                "  if (copyButton) { copyButton.addEventListener('click', () => { navigator.clipboard.writeText(shareUrl).then(() => { copyButton.textContent = 'Copied'; setTimeout(() => { copyButton.textContent = 'Copy'; }, 1500); }); }); }"
                "} catch(e) {"
                "  console.error('Share URL error:', e);"
                "}"
                "</script>"
            )
            st.components.v1.html(share_html, height=140)

            # Dữ liệu form hiển thị dạng nhãn tiếng Việt + khối nội dung giữ nguyên xuống dòng
            if current_t.get('form_data') and current_t.get('form_type'):
                display_form_type = normalize_form_type(current_t.get("form_type"))
                display_config = FORM_TYPE_TO_CONFIG.get(display_form_type)
                display_form_name = (display_config or {}).get("label", display_form_type)
                st.info(f"📋 Dữ liệu đính kèm: **{display_form_name}**")
                try:
                    f_data = parse_form_data(current_t)
                    render_form_data_view(f_data, build_field_label_map(display_config))
                except Exception as e:
                    st.error(f"Lỗi hiển thị dữ liệu Form: {e}")

            # Hiển thị hội thoại
            render_ticket_messages(current_t['msgs'], show_internal=True)

            # Nhập Log + đổi trạng thái trong 1 lần Lưu — Admin only
            st.divider()
            if is_admin():
                current_status = current_t['status']
                with st.form(key=f"admin_update_{state_key}_{current_t['id']}", clear_on_submit=True):
                    log_msg = st.text_area("Nội dung xử lý (Log)", height=120, placeholder="Có thể để trống nếu chỉ đổi trạng thái...")
                    c_type, c_status = st.columns(2)
                    log_type = c_type.radio("Loại log:", ["Công khai", "Nội bộ (Chỉ Admin)"], horizontal=True)
                    new_status = c_status.selectbox(
                        "Trạng thái",
                        STATUS_LIST,
                        index=STATUS_LIST.index(current_status) if current_status in STATUS_LIST else 0,
                    )
                    submitted = st.form_submit_button("💾 Lưu cập nhật", type="primary", width="stretch")
                if submitted:
                    log_msg = log_msg.strip()
                    status_changed = new_status != current_status
                    if not log_msg and not status_changed:
                        st.warning("Hãy nhập nội dung log hoặc chọn trạng thái mới.")
                    else:
                        if log_msg:
                            mtype = "internal" if "Nội bộ" in log_type else "public"
                            # Đang đổi trạng thái thì không tự chuyển 'Mới tạo → Đã tiếp nhận' (tránh 2 dòng log trạng thái)
                            db.add_ticket_message(current_t['id'], ADMIN_DISPLAY_NAME, log_msg, mtype, from_admin=not status_changed)
                        if status_changed:
                            if new_status == "Hoàn thành":
                                # Dùng complete_ticket để ghi nhận vào bảng tasks cho báo cáo tuần
                                db.complete_ticket(current_t['id'], current_t['subject'], log_msg or "Admin đã đánh dấu hoàn thành", changed_by=ADMIN_DISPLAY_NAME)
                                st.balloons()
                            else:
                                db.update_ticket_status(current_t['id'], new_status, changed_by=ADMIN_DISPLAY_NAME)
                        st.rerun()
                # Khu vực Quản trị Admin - Sửa và Xóa Ticket
                st.divider()
                with st.expander("🛠️ Quản trị Admin - Chỉnh sửa / Xóa Ticket"):
                    st.markdown("##### ✏️ Chỉnh sửa thông tin Ticket")
                    edit_subject = st.text_input("Tiêu đề Ticket", value=current_t['subject'], key=f"edit_subj_{current_t['id']}")
                    edit_requester = st.text_input("Người yêu cầu", value=current_t['requester'], key=f"edit_req_{current_t['id']}")

                    # Chỉnh sửa form_data theo từng field
                    has_form = False
                    updated_form_data = None
                    if current_t.get('form_data') and current_t.get('form_type'):
                        has_form = True
                        current_form_data = parse_form_data(current_t)
                        st.markdown("**Dữ liệu đính kèm**")
                        updated_form_data = render_form_data_editor(current_form_data, f"edit_field_{current_t['id']}")

                    c_edit1, c_edit2 = st.columns(2)
                    if c_edit1.button("💾 Lưu Thay Đổi", type="primary", use_container_width=True, key=f"btn_save_{current_t['id']}"):
                        parsed_form_data = updated_form_data if has_form else None
                        if db.update_ticket_data(current_t['id'], edit_subject, edit_requester, parsed_form_data):
                            st.success("Đã cập nhật thông tin ticket thành công!")
                            st.rerun()
                        else:
                            st.error("Lỗi khi cập nhật CSDL")

                    st.markdown("---")
                    st.markdown("##### 🗑️ Xóa Ticket vĩnh viễn")
                    confirm_delete = st.checkbox("Tôi xác nhận muốn xóa vĩnh viễn ticket này khỏi hệ thống.", key=f"conf_del_{current_t['id']}")
                    if st.button("🗑️ Thực hiện Xóa Ticket", type="primary", disabled=not confirm_delete, use_container_width=True, key=f"btn_del_{current_t['id']}"):
                        if db.delete_ticket(current_t['id']):
                            st.success("Đã xóa ticket thành công!")
                            if active_key in st.session_state:
                                del st.session_state[active_key]
                            st.rerun()
                        else:
                            st.error("Lỗi khi xóa ticket khỏi CSDL")
            else:
                st.divider()
                st.info("🔐 Đăng nhập Admin (sidebar) để thêm log, cập nhật trạng thái hoặc chỉnh sửa ticket.")
        else:
            st.info("Chọn một ticket bên trái để xem chi tiết.")

# -----------------
# GIAO DIỆN CHÍNH
# -----------------

# -----------------
# BÁO CÁO TICKET (trang cho Sếp xem — chỉ hiện khi đã đăng nhập Admin)
# -----------------
# Gói bảo trì AEGONA: AGN_PACKAGE_HOURS giờ / AGN_CONTRACT_MONTHS tháng từ AGN_CONTRACT_SIGNED (khai báo ở đầu file).

# Màu đậm hơn STATUS_COLORS để chữ trắng trên thẻ dễ đọc (sáng lẫn tối)
RPT_COLORS = {
    "navy": "#1E3A8A", "blue": "#2563EB", "purple": "#7C3AED", "amber": "#D97706",
    "red": "#DC2626", "green": "#059669", "gray": "#475569", "teal": "#0F766E",
}
RPT_STATUS_COLORS = {
    "Mới tạo": "#2563EB", "Đã tiếp nhận": "#7C3AED", "Đang xử lý": "#D97706",
    "Chờ xử lý": "#DC2626", "Hoàn thành": "#059669", "Từ chối": "#64748B",
}

REPORT_CSS = """
<style>
.rpt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px;margin:4px 0 16px}
.rpt-card{border-radius:14px;padding:14px 16px;color:#fff;box-shadow:0 2px 10px rgba(15,23,42,.15);position:relative;overflow:hidden}
.rpt-card:after{content:"";position:absolute;right:-28px;top:-28px;width:90px;height:90px;border-radius:50%;background:rgba(255,255,255,.12)}
.rpt-card .lbl{font-size:.78rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;opacity:.95}
.rpt-card .val{font-size:2.05rem;font-weight:800;line-height:1.15;margin-top:6px}
.rpt-card .sub{font-size:.8rem;opacity:.92;margin-top:2px}
.rpt-chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.rpt-chip{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;border-radius:999px;font-weight:600;font-size:.88rem;
  border:1.5px solid var(--c);color:var(--c);background:color-mix(in srgb,var(--c) 10%,transparent)}
.rpt-chip b{background:var(--c);color:#fff;border-radius:999px;padding:0 9px;font-size:.85rem}
.rpt-meter{margin:6px 0 4px}
.rpt-meter .row{display:flex;justify-content:space-between;font-size:.85rem;font-weight:600;margin-bottom:4px}
.rpt-meter .track{height:16px;border-radius:8px;background:rgba(148,163,184,.28);overflow:hidden;position:relative}
.rpt-meter .fill{height:100%;border-radius:8px}
.rpt-section{font-size:1.25rem;font-weight:800;margin:18px 0 8px;padding-left:10px;border-left:5px solid #2563EB}
</style>
"""

def rpt_cards_html(cards):
    """cards: list (nhãn, giá trị, dòng phụ, mã màu) → lưới thẻ số liệu màu."""
    items = "".join(
        f'<div class="rpt-card" style="background:linear-gradient(135deg,{color},{color}D9)">'
        f'<div class="lbl">{html.escape(str(label))}</div><div class="val">{html.escape(str(value))}</div>'
        f'<div class="sub">{html.escape(str(sub or ""))}</div></div>'
        for label, value, sub, color in cards
    )
    return f'<div class="rpt-grid">{items}</div>'

def rpt_meter_html(label, percent, color, right_text):
    width = max(0, min(percent, 100))
    return (f'<div class="rpt-meter"><div class="row"><span>{html.escape(label)}</span><span>{html.escape(right_text)}</span></div>'
            f'<div class="track"><div class="fill" style="width:{width:.1f}%;background:{color}"></div></div></div>')

def rpt_section(title):
    st.markdown(f'<div class="rpt-section">{html.escape(title)}</div>', unsafe_allow_html=True)

def ticket_domain(ticket):
    cfg = FORM_TYPE_TO_CONFIG.get(normalize_form_type(ticket.get("form_type")), {})
    return cfg.get("domain", "warranty")

def ticket_form_short_label(ticket):
    f_type = normalize_form_type(ticket.get("form_type"))
    label = FORM_TYPE_TO_CONFIG.get(f_type, {}).get("label", f_type or "—")
    return re.sub(r"^(Form \d+|ERP-\d+|GreeApp-\d+):\s*", "", label)

def report_period_range(preset, today):
    """Khoảng ngày (from, to) theo lựa chọn nhanh; None = không giới hạn."""
    if preset == "Tháng này":
        return today.replace(day=1), today
    if preset == "Tháng trước":
        last = today.replace(day=1) - datetime.timedelta(days=1)
        return last.replace(day=1), last
    if preset == "Quý này":
        q_month = (today.month - 1) // 3 * 3 + 1
        return today.replace(month=q_month, day=1), today
    if preset == "Năm nay":
        return today.replace(month=1, day=1), today
    return None

def style_status_cells(value):
    status = re.sub(r"^\W+\s*", "", str(value))
    color = RPT_STATUS_COLORS.get(status)
    return f"background-color:{color};color:#fff;font-weight:600" if color else ""

def style_aging_cells(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return ""
    if days >= 7:
        return "background-color:#FEE2E2;color:#B91C1C;font-weight:700"
    if days >= AGING_WARN_DAYS:
        return "background-color:#FEF3C7;color:#B45309;font-weight:700"
    return "color:#047857;font-weight:600"

def report_ticket_df(tickets):
    rows = []
    for t in tickets:
        d = days_open(t)
        rows.append({
            "Mã Ticket": t["id"],
            "Tiêu đề": t.get("subject") or "—",
            "Lĩnh vực": WORK_NOTE_LABELS.get(ticket_domain(t), "—"),
            "Loại yêu cầu": ticket_form_short_label(t),
            "Người y/c": t.get("requester") or "—",
            "Ngày tạo": format_ticket_date(t.get("created_at")),
            "Ngày đóng": format_ticket_date(t.get("closed_at")) if t.get("closed_at") else "",
            "Số ngày": d if d is not None else None,
            "Trạng thái": t.get("status") or "",
        })
    return pd.DataFrame(rows)

def render_styled_ticket_table(tickets, key, aging=True):
    """Bảng ticket tô màu theo trạng thái (+ số ngày mở). Bấm 1 dòng để mở ticket ở trang xử lý."""
    df = report_ticket_df(tickets)
    styler = df.style.map(style_status_cells, subset=["Trạng thái"])
    if aging:
        styler = styler.map(style_aging_cells, subset=["Số ngày"])
    event = st.dataframe(
        styler, key=key, on_select="rerun", selection_mode="single-row", hide_index=True, width="stretch",
        height=min(38 + 35 * len(df), 520),
        column_config={
            "Tiêu đề": st.column_config.TextColumn(width="large"),
            "Số ngày": st.column_config.NumberColumn("Số ngày", help="Số ngày từ lúc tạo tới lúc đóng (hoặc tới hôm nay nếu chưa đóng)"),
        },
    )
    if event.selection.rows:
        goto_ticket_detail(tickets[event.selection.rows[0]])
        st.rerun()
    return df

def month_range(start_month, count):
    """'2026-07', 3 → ['2026-07', '2026-08', '2026-09']."""
    year, month = map(int, start_month.split("-"))
    months = []
    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months

def render_ticket_report_tickets(tickets):
    today = now_vn().date()
    f1, f2, f3 = st.columns([1.2, 1.6, 1.6])
    preset = f1.selectbox("Khoảng thời gian (ngày tạo)", ["Tất cả", "Tháng này", "Tháng trước", "Quý này", "Năm nay", "Tùy chọn"],
                          key="rpt_period")
    if preset == "Tùy chọn":
        picked = f1.date_input("Từ ngày – đến ngày", (today.replace(day=1), today), format="DD/MM/YYYY", key="rpt_range")
        period = picked if isinstance(picked, (tuple, list)) and len(picked) == 2 else None
    else:
        period = report_period_range(preset, today)
    domains = f2.multiselect("Lĩnh vực", list(WORK_NOTE_LABELS)[:3], format_func=WORK_NOTE_LABELS.get,
                             key="rpt_domains", placeholder="Tất cả lĩnh vực")
    statuses = f3.multiselect("Trạng thái", STATUS_LIST, key="rpt_statuses", placeholder="Tất cả trạng thái")

    scope = [t for t in tickets if not domains or ticket_domain(t) in domains]
    in_period = [t for t in scope if not period or (to_date(t.get("created_at")) and period[0] <= to_date(t["created_at"]) <= period[1])]
    if statuses:
        in_period = [t for t in in_period if t.get("status") in statuses]
    # Việc chưa xong luôn tính tới hôm nay (không phụ thuộc ngày tạo) — tồn đọng thì phải hiện
    open_now = sort_tickets_for_display([t for t in scope if t.get("status") not in CLOSED_STATUSES
                                         and (not statuses or t.get("status") in statuses)])
    overdue = [t for t in open_now if (days_open(t) or 0) >= AGING_WARN_DAYS]
    done = [t for t in in_period if t.get("status") == "Hoàn thành"]
    rejected = [t for t in in_period if t.get("status") == "Từ chối"]
    durations = [days_open(t) for t in done if t.get("closed_at") and days_open(t) is not None]
    avg_days = sum(durations) / len(durations) if durations else None
    rate = len(done) / len(in_period) * 100 if in_period else 0

    period_text = "toàn bộ thời gian" if not period else f"{period[0]:%d/%m/%Y} – {period[1]:%d/%m/%Y}"
    st.caption(f"Số liệu theo ngày tạo ticket: **{period_text}**. Ô *Chưa hoàn thành* / *Quá {AGING_WARN_DAYS} ngày* tính tất cả ticket còn mở tới hôm nay.")
    st.markdown(rpt_cards_html([
        ("Tổng ticket", len(in_period), period_text, RPT_COLORS["navy"]),
        ("Chưa hoàn thành", len(open_now), "đang mở tới hôm nay", RPT_COLORS["amber"]),
        (f"Quá {AGING_WARN_DAYS} ngày", len(overdue), "cần ưu tiên xử lý", RPT_COLORS["red"]),
        ("Hoàn thành", len(done), f"tỷ lệ {rate:.0f}%", RPT_COLORS["green"]),
        ("Từ chối", len(rejected), "không thực hiện", RPT_COLORS["gray"]),
        ("TG xử lý TB", f"{avg_days:.1f} ngày" if avg_days is not None else "—", "từ lúc tạo tới lúc đóng", RPT_COLORS["purple"]),
    ]), unsafe_allow_html=True)

    counts = {s: len([t for t in in_period if t.get("status") == s]) for s in STATUS_LIST}
    chips = "".join(f'<span class="rpt-chip" style="--c:{RPT_STATUS_COLORS[s]}">{STATUS_ICONS.get(s, "")} {s} <b>{n}</b></span>'
                    for s, n in counts.items())
    st.markdown(f'<div class="rpt-chips">{chips}</div>', unsafe_allow_html=True)

    rpt_section(f"⚠️ Việc chưa hoàn thành ({len(open_now)})")
    if open_now:
        st.caption(f"Ô *Số ngày*: xanh < {AGING_WARN_DAYS} ngày · vàng ≥ {AGING_WARN_DAYS} ngày · đỏ ≥ 7 ngày. Bấm vào một dòng để mở ticket.")
        render_styled_ticket_table(open_now, "rpt_open_table")
    else:
        st.success("✅ Không còn ticket nào chưa hoàn thành.")

    if in_period:
        rpt_section("📈 Thống kê")
        c1, c2 = st.columns([3, 2])
        chart_df = pd.DataFrame([{
            "Tháng": t["created_at"].strftime("%Y-%m"),
            "Trạng thái": t.get("status"),
            "Lĩnh vực": WORK_NOTE_LABELS.get(ticket_domain(t), "—"),
        } for t in in_period if isinstance(t.get("created_at"), datetime.datetime)])
        status_scale = alt.Scale(domain=STATUS_LIST, range=[RPT_STATUS_COLORS[s] for s in STATUS_LIST])
        with c1:
            st.markdown("**Số ticket theo tháng (theo trạng thái)**")
            st.altair_chart(
                alt.Chart(chart_df).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                    x=alt.X("Tháng:O", title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("count():Q", title="Số ticket"),
                    color=alt.Color("Trạng thái:N", scale=status_scale, legend=alt.Legend(orient="bottom", title=None)),
                    tooltip=["Tháng", "Trạng thái", alt.Tooltip("count():Q", title="Số ticket")],
                ).properties(height=300),
                width="stretch",
            )
        with c2:
            st.markdown("**Theo lĩnh vực**")
            st.altair_chart(
                alt.Chart(chart_df).mark_bar(cornerRadiusEnd=3).encode(
                    y=alt.Y("Lĩnh vực:N", title=None, sort="-x"),
                    x=alt.X("count():Q", title="Số ticket"),
                    color=alt.Color("Trạng thái:N", scale=status_scale, legend=None),
                    tooltip=["Lĩnh vực", "Trạng thái", alt.Tooltip("count():Q", title="Số ticket")],
                ).properties(height=300),
                width="stretch",
            )

    rpt_section(f"📋 Danh sách ticket trong kỳ ({len(in_period)})")
    kw = st.text_input("Tìm theo mã / tiêu đề / người yêu cầu", key="rpt_kw", placeholder="Nhập từ khóa...")
    shown = sort_tickets_for_display(in_period)
    if kw.strip():
        k = kw.strip().lower()
        shown = [t for t in shown if k in str(t.get("id", "")).lower() or k in str(t.get("subject", "")).lower()
                 or k in str(t.get("requester", "")).lower()]
    if shown:
        df = render_styled_ticket_table(shown, "rpt_all_table", aging=False)
        st.download_button("⬇️ Tải danh sách (CSV/Excel)", df.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"BaoCaoTicket_{today:%Y%m%d}.csv", mime="text/csv")
    else:
        st.info("Không có ticket nào khớp bộ lọc.")

# Nhóm trạng thái ticket AEGONA đang mở → 4 ô chi tiết (+ ô tổng "Ticket đang mở")
AGN_OPEN_GROUPS = [
    ("Mới (chưa thực hiện)", ("Mới",), "#2563EB"),
    ("Chờ đề xuất", ("Chờ đề xuất",), "#7C3AED"),
    ("Đang thực hiện", ("Đang thực hiện",), "#D97706"),
    ("Testing / chờ deploy", ("Đang testing", "Chờ deploy", "Chờ cập nhật", "Đã lên Production"), "#0F766E"),
]
TRACKING_STATUS_COLORS = {
    "Mới": "#2563EB", "Chờ đề xuất": "#7C3AED", "Đang thực hiện": "#D97706", "Đang testing": "#0891B2",
    "Chờ deploy": "#0F766E", "Chờ cập nhật": "#0D9488", "Đã lên Production": "#059669", "Đóng": "#64748B", "Hủy": "#94A3B8",
}

# Giờ của ticket ở các trạng thái này = đã triển khai thật trên hệ thống; còn lại = đã làm nhưng chưa triển khai
AGN_DEPLOYED_STATUSES = ("Đóng", "Đã lên Production")

def agn_item_hours(item):
    return float(item.get("actual_hours") or 0)

def agn_package_stats(items):
    """Số liệu gói bảo trì AEGONA (dùng chung cho trang Báo cáo Ticket và file PDF). None nếu chưa có giờ."""
    summary = tracking_month_summary(items)
    if not summary:
        return None
    signed = AGN_CONTRACT_SIGNED
    contract_end = signed.replace(year=signed.year + 1) - datetime.timedelta(days=1)
    total_days = (contract_end - signed).days + 1
    today = now_vn().date()
    elapsed_days = min(max((today - signed).days + 1, 0), total_days)
    contract_months = month_range(signed.strftime("%Y-%m"), AGN_CONTRACT_MONTHS)
    this_month = today.strftime("%Y-%m")
    elapsed = len([m for m in contract_months if m <= this_month])  # số tháng tính giờ đã tới (kể cả tháng này)
    quota = AGN_PACKAGE_HOURS
    in_contract = {m: summary.get(m, {"count": 0, "eta": 0.0, "actual": 0.0}) for m in contract_months}
    used = sum(s["actual"] for s in in_contract.values())
    elapsed_months = elapsed_days / total_days * AGN_CONTRACT_MONTHS
    remaining = quota - used
    remaining_months = AGN_CONTRACT_MONTHS - max(elapsed - 1, 0)

    # Tách giờ đã thực hiện: đã triển khai / chưa triển khai (theo trạng thái ticket). Phần chưa triển khai cộng từ
    # từng ticket; phần đã triển khai = tổng tháng (theo file AEGONA) − chưa triển khai → 2 phần luôn cộng đúng tổng.
    worked = sorted([i for i in items if i.get("work_month") in in_contract and agn_item_hours(i) > 0],
                    key=lambda i: (i["work_month"], -tracking_sort_key(i)[1]))
    deployed_items = [i for i in worked if i.get("status") in AGN_DEPLOYED_STATUSES]
    pending_items = [i for i in worked if i.get("status") not in AGN_DEPLOYED_STATUSES]
    month_pending = {m: sum(agn_item_hours(i) for i in pending_items if i["work_month"] == m) for m in contract_months}
    pending = sum(month_pending.values())
    pending_by_status = {}
    for i in pending_items:
        pending_by_status[i["status"]] = pending_by_status.get(i["status"], 0.0) + agn_item_hours(i)

    month_rows, cumulative = [], 0.0
    for m in contract_months:
        s = in_contract[m]
        has_data = m <= this_month or bool(s["actual"])
        cumulative += s["actual"]
        month_rows.append({
            "month": m, "label": month_label(m), "has_data": has_data, "count": s["count"], "eta": s["eta"],
            "actual": s["actual"], "pending": month_pending[m], "deployed": s["actual"] - month_pending[m],
            "quota": AGN_MONTHLY_QUOTA_HOURS, "diff": s["actual"] - AGN_MONTHLY_QUOTA_HOURS,
            "cum": cumulative, "cum_pct": cumulative / quota * 100,
        })

    open_items = sorted([i for i in items if i.get("status") not in TRACKING_CLOSED], key=tracking_sort_key)
    open_groups = [(label, len([i for i in open_items if i.get("status") in statuses]), color, statuses)
                   for label, statuses, color in AGN_OPEN_GROUPS]
    return {
        "signed": signed, "contract_end": contract_end, "total_days": total_days, "elapsed_days": elapsed_days,
        "today": today, "this_month": this_month, "contract_months": contract_months, "elapsed": elapsed,
        "quota": quota, "monthly_quota": AGN_MONTHLY_QUOTA_HOURS, "hours_per_md": HOURS_PER_MD,
        "used": used, "used_pct": used / quota * 100 if quota else 0,
        "time_pct": elapsed_days / total_days * 100, "remaining": remaining,
        "month_used": in_contract[this_month]["actual"] if this_month in in_contract else 0.0,
        "avg_month": used / elapsed_months if elapsed_months else 0,
        "remaining_months": remaining_months,
        "per_month_left": remaining / remaining_months if remaining_months > 0 else None,
        "month_rows": month_rows,
        "total_count": sum(s["count"] for s in in_contract.values()),
        "total_eta": sum(s["eta"] for s in in_contract.values()),
        "total_diff": used - AGN_MONTHLY_QUOTA_HOURS * elapsed,
        "outside": {m: summary[m] for m in sorted(summary) if m not in in_contract},
        "file_totals": saved_month_totals(),
        "open_items": open_items, "open_groups": open_groups,
        "closed_count": len([i for i in items if i.get("status") in TRACKING_CLOSED]),
        "status_counts": {s: len([i for i in items if i.get("status") == s]) for s in TRACKING_STATUSES},
        "deployed": used - pending, "pending": pending, "deployed_items": deployed_items, "pending_items": pending_items,
        "pending_by_status": dict(sorted(pending_by_status.items(), key=lambda kv: -kv[1])),
        "deployed_statuses": AGN_DEPLOYED_STATUSES,
    }

def tracking_status_style(v):
    color = TRACKING_STATUS_COLORS.get(v)
    return f"background-color:{color};color:#fff;font-weight:600" if color else ""

def render_agn_hours_list(hours_items, empty_text):
    """Danh sách ticket kèm giờ thực tế (+ dòng TỔNG), tô màu cột trạng thái."""
    if not hours_items:
        st.info(empty_text)
        return
    rows = [{
        "ID": i.get("ext_id") or "—", "Tiêu đề": (i.get("title") or "").strip().splitlines()[0] if (i.get("title") or "").strip() else "",
        "Trạng thái": i.get("status") or "", "TT AEGONA": i.get("agn_status") or "", "Hệ thống": i.get("system_name") or "",
        "Tháng tính giờ": month_label(i["work_month"]),
        "Kết thúc": f"{to_date(i.get('end_date')):%d/%m/%Y}" if to_date(i.get("end_date")) else "",
        "Giờ thực tế": agn_item_hours(i), "MD": agn_item_hours(i) / HOURS_PER_MD,
    } for i in hours_items]
    total = sum(r["Giờ thực tế"] for r in rows)
    rows.append({"ID": "", "Tiêu đề": f"TỔNG ({len(hours_items)} ticket)", "Trạng thái": "", "TT AEGONA": "", "Hệ thống": "",
                 "Tháng tính giờ": "", "Kết thúc": "", "Giờ thực tế": total, "MD": total / HOURS_PER_MD})
    df = pd.DataFrame(rows)
    styler = (df.style.map(tracking_status_style, subset=["Trạng thái"])
              .apply(lambda r: ["font-weight:800;background-color:#E0E7FF;color:#1E3A8A"] * len(r)
                     if str(r["Tiêu đề"]).startswith("TỔNG (") else [""] * len(r), axis=1)
              .format({"Giờ thực tế": "{:.2f}", "MD": "{:.2f}"}))
    st.dataframe(styler, hide_index=True, width="stretch", height=min(38 + 35 * len(df), 520),
                 column_config={"Tiêu đề": st.column_config.TextColumn(width="large")})

def render_agn_hours_split(st_):
    """Giờ đã thực hiện = đã triển khai trên hệ thống + chưa triển khai (chờ đề xuất, đang làm, testing...)."""
    used, deployed, pending = st_["used"], st_["deployed"], st_["pending"]
    dep_pct = deployed / used * 100 if used else 0
    pend_pct = 100 - dep_pct if used else 0
    rpt_section(f"🚀 Phân tách {used:.2f} giờ đã thực hiện")
    pend_detail = " · ".join(f"{s} {h:.2f}" for s, h in st_["pending_by_status"].items())
    st.markdown(rpt_cards_html([
        ("⏳ Chưa triển khai", f"{pending:.2f} giờ",
         f"{pend_pct:.1f}% · {len(st_['pending_items'])} ticket · {pend_detail or 'không có'}", RPT_COLORS["amber"]),
        ("✅ Đã triển khai trên hệ thống", f"{deployed:.2f} giờ",
         f"{dep_pct:.1f}% · {len(st_['deployed_items'])} ticket · trạng thái {' / '.join(st_['deployed_statuses'])}", RPT_COLORS["green"]),
    ]), unsafe_allow_html=True)
    st.markdown(
        f'<div class="rpt-meter"><div class="row"><span>✅ Đã triển khai {deployed:.2f} giờ ({dep_pct:.1f}%)</span>'
        f'<span>⏳ Chưa triển khai {pending:.2f} giờ ({pend_pct:.1f}%)</span></div>'
        f'<div class="track" style="display:flex"><div class="fill" style="width:{dep_pct:.1f}%;background:{RPT_COLORS["green"]};border-radius:8px 0 0 8px"></div>'
        f'<div class="fill" style="width:{pend_pct:.1f}%;background:{RPT_COLORS["amber"]};border-radius:0 8px 8px 0"></div></div></div>',
        unsafe_allow_html=True)
    t_pending, t_deployed = st.tabs([f"⏳ Chưa triển khai — {pending:.2f} giờ ({len(st_['pending_items'])} ticket)",
                                     f"✅ Đã triển khai — {deployed:.2f} giờ ({len(st_['deployed_items'])} ticket)"])
    with t_pending:
        render_agn_hours_list(st_["pending_items"], "Không có giờ nào chưa triển khai.")
    with t_deployed:
        render_agn_hours_list(st_["deployed_items"], "Chưa có ticket nào đã triển khai.")
        gap = deployed - sum(agn_item_hours(i) for i in st_["deployed_items"])
        if abs(gap) >= 0.005:
            st.caption(f"Tổng tháng theo file AEGONA lệch {gap:+.2f} giờ so với cộng các dòng — phần lệch tính vào Đã triển khai.")

def build_agn_pdf_bytes(tracking_items):
    """File PDF báo cáo gói bảo trì AEGONA (nút tải ở trang Báo cáo Ticket / Báo cáo tuần + đính kèm email). None nếu chưa có giờ."""
    stats = agn_package_stats(tracking_items)
    if not stats:
        return None
    return agn_report_pdf.build_pdf(stats, tracking_items, LOGO_PATH, now_vn(), TRACKING_STATUS_COLORS)

def render_ticket_report_agn():
    """Gói bảo trì AEGONA: tổng giờ theo tháng, tổng giờ đã thực hiện, % đã dùng gói, ticket đang mở + xuất PDF."""
    items = db.get_ticket_tracking()
    st_ = agn_package_stats(items)
    if not st_:
        st.info("Chưa có dữ liệu giờ AEGONA — tải file báo cáo AEGONA ở trang 📈 Báo cáo tuần.")
        return
    quota, mq = st_["quota"], st_["monthly_quota"]
    used, used_pct, time_pct, remaining = st_["used"], st_["used_pct"], st_["time_pct"], st_["remaining"]

    h1, h2 = st.columns([4, 1.3])
    h1.markdown(
        f"Hợp đồng ký <b>{st_['signed']:%d/%m/%Y}</b> → hết hạn <b>{st_['contract_end']:%d/%m/%Y}</b> · tổng gói <b>{quota:g} giờ</b> "
        f"({hours_to_md(quota):g} MD) · chia đều <b>{mq} giờ/tháng</b> "
        f"({month_label(st_['contract_months'][0])} → {month_label(st_['contract_months'][-1])})", unsafe_allow_html=True)
    with h2:
        try:
            pdf_bytes = build_agn_pdf_bytes(items)
            st.download_button("📄 Xuất báo cáo PDF", pdf_bytes, file_name=f"BaoCao_AEGONA_{st_['today']:%Y%m%d}.pdf",
                               mime="application/pdf", type="primary", width="stretch")
        except Exception as e:  # PDF lỗi không được làm hỏng cả trang
            st.error(f"Không tạo được PDF: {e}")

    pct_color = RPT_COLORS["green"] if used_pct <= time_pct else (RPT_COLORS["amber"] if used_pct <= 100 else RPT_COLORS["red"])
    per_left = st_["per_month_left"]
    st.markdown(rpt_cards_html([
        ("Tổng giờ đã thực hiện", f"{used:.2f} giờ", f"= {hours_to_md(used):g} MD trong gói", RPT_COLORS["navy"]),
        ("% đã dùng gói", f"{used_pct:.1f}%", f"trên {quota:g} giờ · thời gian đã qua {time_pct:.0f}%", pct_color),
        ("Giờ còn lại", f"{remaining:.2f} giờ" if remaining >= 0 else f"Vượt {-remaining:.2f} giờ",
         f"≈ {per_left:.2f} giờ/tháng cho {st_['remaining_months']} tháng còn lại (kể cả tháng này)"
         if per_left is not None and remaining >= 0 else f"{hours_to_md(max(remaining, 0)):g} MD",
         RPT_COLORS["teal"] if remaining >= 0 else RPT_COLORS["red"]),
        (f"Giờ {month_label(st_['this_month'])}", f"{st_['month_used']:.2f} / {mq}",
         f"{st_['month_used'] / mq * 100:.0f}% hạn mức tháng", RPT_COLORS["red"] if st_["month_used"] > mq else RPT_COLORS["blue"]),
        ("Bình quân / tháng", f"{st_['avg_month']:.2f} giờ", f"hạn mức {mq} giờ/tháng",
         RPT_COLORS["red"] if st_["avg_month"] > mq else RPT_COLORS["purple"]),
    ]), unsafe_allow_html=True)
    st.markdown(
        rpt_meter_html("Đã dùng gói bảo trì", used_pct, pct_color, f"{used:.2f} / {quota:g} giờ ({used_pct:.1f}%)")
        + rpt_meter_html("Thời gian hợp đồng đã qua", time_pct, "#64748B",
                         f"{st_['elapsed_days']} / {st_['total_days']} ngày ({time_pct:.0f}%)"),
        unsafe_allow_html=True)
    if used_pct > time_pct:
        st.warning(f"Giờ sử dụng ({used_pct:.1f}%) đang nhanh hơn tiến độ thời gian hợp đồng ({time_pct:.0f}%) — "
                   f"bình quân {st_['avg_month']:.2f} giờ/tháng, hạn mức {mq} giờ/tháng.")
    if st_["outside"]:
        st.caption("Có giờ ngoài thời hạn hợp đồng (không tính vào %): " + ", ".join(
            f"{month_label(m)} {s['actual']:.2f} giờ" for m, s in st_["outside"].items()))

    render_agn_hours_split(st_)

    open_items = st_["open_items"]
    rpt_section(f"🎫 Ticket AEGONA đang mở ({len(open_items)})")
    st.markdown(rpt_cards_html(
        [("Ticket đang mở", len(open_items), f"{st_['closed_count']} ticket đã Đóng / Hủy", RPT_COLORS["navy"])]
        + [(label, n, " · ".join(statuses) if len(statuses) > 1 else "", color) for label, n, color, statuses in st_["open_groups"]]
    ), unsafe_allow_html=True)
    chips = "".join(f'<span class="rpt-chip" style="--c:{TRACKING_STATUS_COLORS.get(s, "#64748B")}">{s} <b>{n}</b></span>'
                    for s, n in st_["status_counts"].items())
    st.markdown(f'<div class="rpt-chips">{chips}</div>', unsafe_allow_html=True)
    if open_items:
        open_df = pd.DataFrame([{
            "ID": i.get("ext_id") or "", "Tiêu đề": (i.get("title") or "").splitlines()[0] if i.get("title") else "",
            "Trạng thái": i.get("status") or "", "Ưu tiên": i.get("priority") or "",
            "Hệ thống": i.get("system_name") or "", "Ngày yêu cầu": f"{to_date(i.get('requested_at')):%d/%m/%Y}" if to_date(i.get("requested_at")) else "",
            "Tháng tính giờ": month_label(i["work_month"]) if i.get("work_month") else "",
            "ETA (giờ)": float(i["eta_hours"]) if i.get("eta_hours") is not None else None,
        } for i in open_items])

        st.dataframe(open_df.style.map(tracking_status_style, subset=["Trạng thái"]).format({"ETA (giờ)": "{:.2f}"}, na_rep=""),
                     hide_index=True, width="stretch", height=min(38 + 35 * len(open_df), 460),
                     column_config={"Tiêu đề": st.column_config.TextColumn(width="large")})

    rpt_section("⏱️ Tổng giờ theo tháng")
    rows = [{
        "Tháng": r["label"], "Số ticket": r["count"] if r["has_data"] else None,
        "ETA (giờ)": r["eta"] if r["has_data"] else None, "Thực hiện (giờ)": r["actual"] if r["has_data"] else None,
        "Đã triển khai (giờ)": r["deployed"] if r["has_data"] else None,
        "Chưa triển khai (giờ)": r["pending"] if r["has_data"] else None,
        "Hạn mức (giờ)": r["quota"], "Chênh lệch (giờ)": r["diff"] if r["has_data"] else None,
        "Lũy kế (giờ)": r["cum"] if r["has_data"] else None, "% gói (lũy kế)": r["cum_pct"] if r["has_data"] else None,
    } for r in st_["month_rows"]]
    rows.append({
        "Tháng": "TỔNG", "Số ticket": st_["total_count"], "ETA (giờ)": st_["total_eta"], "Thực hiện (giờ)": used,
        "Đã triển khai (giờ)": st_["deployed"], "Chưa triển khai (giờ)": st_["pending"], "Hạn mức (giờ)": quota, "Chênh lệch (giờ)": st_["total_diff"], "Lũy kế (giờ)": used, "% gói (lũy kế)": used_pct,
    })
    df = pd.DataFrame(rows)

    def diff_style(v):
        if v is None or pd.isna(v):
            return ""
        return "color:#B91C1C;font-weight:700;background-color:#FEE2E2" if v > 0 else "color:#047857;font-weight:700"

    styler = (df.style.map(diff_style, subset=["Chênh lệch (giờ)"])
              .map(lambda v: "color:#047857;font-weight:600", subset=["Đã triển khai (giờ)"])
              .map(lambda v: "color:#B45309;font-weight:600" if v else "", subset=["Chưa triển khai (giờ)"])
              .apply(lambda r: ["font-weight:800;background-color:#E0E7FF;color:#1E3A8A"] * len(r) if r["Tháng"] == "TỔNG" else [""] * len(r), axis=1)
              .format({"Số ticket": "{:.0f}"}, na_rep="")
              .format({c: "{:.2f}" for c in ["ETA (giờ)", "Thực hiện (giờ)", "Đã triển khai (giờ)", "Chưa triển khai (giờ)", "Hạn mức (giờ)", "Lũy kế (giờ)"]}, na_rep="")
              .format({"Chênh lệch (giờ)": "{:+.2f}", "% gói (lũy kế)": "{:.1f}%"}, na_rep=""))
    c1, c2 = st.columns([3, 2])
    with c1:
        st.caption("Chênh lệch = Thực hiện − hạn mức tháng (đỏ: vượt, xanh: trong hạn mức). Dòng TỔNG so với hạn mức các tháng đã qua.")
        st.dataframe(styler, hide_index=True, width="stretch", height=38 + 35 * len(df))
    with c2:
        parts = [("Đã triển khai", "deployed"), ("Chưa triển khai", "pending")]
        chart_df = pd.DataFrame([{"Tháng": r["label"], "Thứ tự": n, "Phần": label, "Thứ tự phần": k, "Giờ": round(r[key], 2)}
                                 for n, r in enumerate(st_["month_rows"]) for k, (label, key) in enumerate(parts)])
        totals_df = pd.DataFrame([{"Tháng": r["label"], "Thứ tự": n, "Tổng": round(r["actual"], 2), "Vượt": r["actual"] > mq}
                                  for n, r in enumerate(st_["month_rows"]) if r["actual"]])
        x_enc = alt.X("Tháng:N", sort=alt.SortField("Thứ tự"), title=None, axis=alt.Axis(labelAngle=-45))
        bars = alt.Chart(chart_df).mark_bar().encode(
            x=x_enc, y=alt.Y("sum(Giờ):Q", title="Giờ"),
            color=alt.Color("Phần:N", scale=alt.Scale(domain=["Đã triển khai", "Chưa triển khai"], range=["#059669", "#D97706"]),
                            legend=alt.Legend(orient="bottom", title=None)),
            order=alt.Order("Thứ tự phần:Q"),
            tooltip=["Tháng", "Phần", alt.Tooltip("Giờ:Q", format=".2f")],
        )
        layers = bars
        if not totals_df.empty:
            layers += alt.Chart(totals_df).mark_text(dy=-8, fontWeight="bold").encode(
                x=x_enc, y="Tổng:Q", text=alt.Text("Tổng:Q", format="g"),
                color=alt.condition("datum['Vượt']", alt.value("#DC2626"), alt.value("#475569")))
        layers += alt.Chart(pd.DataFrame({"y": [mq]})).mark_rule(strokeDash=[6, 4], color="#DC2626", size=2).encode(y="y:Q")
        st.altair_chart(layers.properties(height=360), width="stretch")
        st.caption(f"Đường nét đứt đỏ = hạn mức {mq} giờ/tháng; số trên cột = tổng giờ tháng (đỏ: vượt hạn mức).")

def render_ticket_report_page():
    st.markdown(REPORT_CSS, unsafe_allow_html=True)
    st.markdown('<div class="main-header">📊 Báo cáo Ticket</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">Tổng hợp yêu cầu hỗ trợ & gói bảo trì AEGONA · cập nhật {now_vn():%H:%M %d/%m/%Y}</div>',
                unsafe_allow_html=True)
    tab_ticket, tab_agn = st.tabs(["🎫 Ticket hỗ trợ", "🔧 Gói bảo trì AEGONA"])
    with tab_ticket:
        render_ticket_report_tickets(db_tickets)
    with tab_agn:
        render_ticket_report_agn()

# -----------------
# TỰ ĐỘNG GỬI BÁO CÁO TUẦN
# -----------------
# Streamlit Cloud cho app ngủ khi không ai truy cập nên không thể chạy scheduler nền.
# Thay vào đó kiểm tra mỗi lần có người mở app: quá giờ hẹn và tuần này chưa gửi thì gửi.
# Đặt sau phần định nghĩa hàm vì email đính kèm PDF AEGONA (agn_package_stats... định nghĩa ở dưới).
app_settings = db.get_settings()
if weekly_email_due(app_settings):
    # Ghi mốc thử TRƯỚC khi gửi để nếu thất bại thì cooldown có hiệu lực ngay,
    # tránh mọi lượt truy cập sau đó đều phải chờ timeout SMTP.
    db.save_settings({"report_email_last_attempt_at": now_vn().isoformat()})
    ok, msg = send_weekly_report_email(app_settings, db_tickets, db_tasks)
    if ok:
        st.toast(f"📧 {msg}")
    else:
        print(f"[Gửi báo cáo tuần tự động] Thất bại: {msg}")

if page == "🏠 Trang chủ":
    st.markdown(f'<div class="main-header">Welcome to {Config.APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Dashboard Tổng quát</div>', unsafe_allow_html=True)
    
    open_tickets = sort_tickets_for_display(
        [t for t in db_tickets if t['status'] not in CLOSED_STATUSES]
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Ticket", str(len(db_tickets)), "")
    c2.metric("Đang xử lý", len(open_tickets))
    c3.metric("Hoàn thành (Tasks)", len(db_tasks))
    c4.metric("Chờ xử lý", len([t for t in open_tickets if t['status'] == 'Chờ xử lý']))

    st.divider()
    # --- DANH SÁCH ĐANG XỬ LÝ ---
    in_progress_statuses = [s for s in STATUS_LIST if s not in CLOSED_STATUSES]

    st.subheader(f"🔄 Danh sách đang xử lý ({len(open_tickets)} ticket)")

    if open_tickets:
        filter_col1, filter_col2 = st.columns([2, 3])
        with filter_col1:
            filter_status = st.selectbox(
                "Lọc theo trạng thái",
                ["Tất cả"] + in_progress_statuses,
                key="home_filter_status"
            )
        with filter_col2:
            filter_keyword = st.text_input(
                "Tìm theo mã ticket / tiêu đề / người y/c",
                placeholder="Nhập từ khóa...",
                key="home_filter_kw"
            )

        filtered = open_tickets
        if filter_status != "Tất cả":
            filtered = [t for t in filtered if t.get("status") == filter_status]
        if filter_keyword.strip():
            kw = filter_keyword.strip().lower()
            filtered = [
                t for t in filtered
                if kw in str(t.get("id", "")).lower()
                or kw in str(t.get("subject", "")).lower()
                or kw in str(t.get("requester", "")).lower()
            ]

        if filtered:
            rows = ticket_table_rows(filtered)
            for row, t in zip(rows, filtered):
                f_type = normalize_form_type(t.get("form_type"))
                f_label = FORM_TYPE_TO_CONFIG.get(f_type, {}).get("label", f_type or "—")
                row["Loại Form"] = re.sub(r"^(Form \d+|ERP-\d+|GreeApp-\d+):\s*", "", f_label)
                # Link xem nhanh ở tab mới (dùng để gửi cho người khác)
                row["Link chia sẻ"] = f"/?ticket={t['id']}"
            st.caption("Bấm vào ô đầu dòng để mở ticket trong trang xử lý.")
            event = st.dataframe(
                pd.DataFrame(rows),
                key="home_ticket_table",
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True,
                width="stretch",
                column_order=["Mã Ticket", "Tiêu đề", "Loại Form", "Người y/c", "Ngày tạo", "Đã mở", "Trạng thái", "Link chia sẻ"],
                column_config={"Link chia sẻ": st.column_config.LinkColumn("Link chia sẻ", display_text="Mở ↗")},
            )
            if event.selection.rows:
                goto_ticket_detail(filtered[event.selection.rows[0]])
                st.rerun()
        else:
            st.info("Không có ticket nào khớp với bộ lọc.")
    else:
        st.success("✅ Hiện không có ticket nào đang chờ xử lý!")

    st.divider()
    cl, cr = st.columns(2)
    with cl:
        st.subheader("📅 Lịch trình & Ghi chú")
        st.write("- [ ] Họp ERP chiều thứ 2 (05/05)")
        st.text_area("Ghi chú nhanh", placeholder="Nhập mã lỗi hoặc ID cần lưu ý...")
    with cr:
        st.subheader("🔗 Truy cập nhanh")
        st.button("Hệ thống ERP", use_container_width=True)
        st.button("Gree App Admin", use_container_width=True)

elif page == "🛡️ Hệ thống Bảo hành":
    render_ticket_domain_page(
        "bh",
        "🛡️ Hệ thống Warranty - Bảo Hành",
        "Quản lý và hỗ trợ xử lý lỗi hệ thống",
        [f for f in FORM_CONFIGS if f.get("domain") == "warranty"],
    )

elif page == "🏭 Quản trị ERP":
    render_ticket_domain_page(
        "erp",
        "🏭 Quản trị ERP",
        "Quản lý yêu cầu hỗ trợ nghiệp vụ ERP",
        [f for f in FORM_CONFIGS if f.get("domain") == "erp"],
    )

elif page == "📱 Gree App Support":
    render_ticket_domain_page(
        "greeapp",
        "📱 Gree App Support",
        "Ghi nhận lại các yêu cầu hỗ trợ Gree App nhận qua email (hệ thống xử lý ticket gốc nằm ngoài tool này)",
        [f for f in FORM_CONFIGS if f.get("domain") == "gree_app"],
    )

elif page == "📈 Báo cáo tuần của Nam":
    if not is_admin():
        st.warning("🔐 Chức năng này chỉ dành cho Admin. Vui lòng đăng nhập ở sidebar.")
        st.stop()
    st.markdown('<div class="main-header">📊 Báo cáo công việc theo tuần</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Tuần tính theo tháng (Tuần 1 → Tuần 5 mỗi tháng, reset khi sang tháng mới)</div>', unsafe_allow_html=True)

    today = datetime.date.today()
    wc1, wc2, wc3, wc4 = st.columns([1, 1, 1, 2])
    with wc1:
        report_year = st.selectbox("Năm", list(range(today.year - 1, today.year + 2)), index=1)
    with wc2:
        report_month = st.selectbox("Tháng", list(range(1, 13)), index=today.month - 1, format_func=lambda m: f"Tháng {m}")
    with wc3:
        max_w = max_weeks_in_month(report_year, report_month)
        default_week = week_of_month(today) if (report_year == today.year and report_month == today.month) else 1
        default_week = min(default_week, max_w)
        report_week = st.selectbox("Tuần", list(range(1, max_w + 1)), index=default_week - 1, format_func=lambda w: f"Tuần {w}")
    with wc4:
        reporter_name = st.text_input("Người báo cáo", value=Config.OWNER)

    start_date, end_date = week_date_range(report_year, report_month, report_week)
    st.caption(
        f"📅 Khoảng thời gian: **{start_date.strftime('%d/%m/%Y')} → {end_date.strftime('%d/%m/%Y')}** "
        f"(Tuần {report_week} tháng {report_month}/{report_year})"
    )

    status_kind, status_text = report_email_status(app_settings, db.get_report_email_logs(), start_date, end_date)
    getattr(st, status_kind)(f"📧 Email báo cáo tuần này: {status_text}")

    # Số liệu báo cáo dựng bằng hàm dùng chung với chức năng gửi email tự động
    tracking_items, tracking_logs = db.get_ticket_tracking(), db.get_ticket_tracking_logs()
    base_ctx = build_report_context(
        report_year, report_month, report_week, reporter_name, db_tickets, db_tasks, db.get_work_notes(),
        tracking=tracking_items, tracking_logs=tracking_logs,
    )
    week_new_tickets = base_ctx["week_new_tickets"]
    week_completed_tasks = base_ctx["week_completed_tasks"]
    summary_rows = base_ctx["summary_rows"]
    completed_rows = base_ctx["completed_rows"]

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    for col, (label, value) in zip((m1, m2, m3, m4), base_ctx["metrics"]):
        col.metric(label, value)

    if summary_rows:
        st.subheader("📊 Ticket mới theo Form")
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    st.subheader("✅ Danh sách công việc đã hoàn thành trong tuần")
    if completed_rows:
        st.dataframe(
            pd.DataFrame(completed_rows).rename(columns={
                "id": "Mã Ticket", "form_label": "Loại Form", "requester": "Người y/c", "subject": "Nội dung"
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Chưa có công việc nào hoàn thành trong tuần này.")

    st.caption(
        "ℹ️ *Số liệu 'Hoàn thành trong tuần' lấy theo thời điểm thực tế đánh dấu Hoàn thành (bảng tasks), không phải "
        "ngày tạo ticket. Các dòng hiển thị 'Mã Ticket: —' là log được ghi trước khi cập nhật cột `ticket_id` (17/6/2026), "
        "nên chưa liên kết lại được với ticket gốc.*"
    )

    st.divider()
    st.subheader("🤖 Ghi chú AI tổng hợp — chờ duyệt")
    st.caption(
        "Nội dung ngoài ticket do AI tổng hợp đưa vào (chạy `python ai_notes.py file.json` hoặc dán JSON bên dưới). "
        "Xem/sửa lại, tick chọn rồi bấm **Duyệt** → chuyển xuống bảng ghi chú bên dưới và được đưa vào file mẫu."
    )
    render_note_drafts_review(start_date, end_date)
    render_ai_notes_paste_box()

    st.divider()
    st.subheader("📝 Ghi chú công việc ngoài ticket")
    st.caption(
        "Ghi tổng quan việc đã làm/đang follow — mỗi dòng sẽ thành '- nội dung' trong mục 'Công việc khác' "
        "của nhóm ERP / Bảo hành / Gree App / IT cơ bản ở dòng 'Công việc đã thực hiện' của file mẫu. Ghi nhanh hằng ngày ở sidebar, "
        "hoặc thêm/sửa/xóa trực tiếp trong bảng dưới rồi bấm Lưu."
    )
    render_work_notes_list(base_ctx["week_notes"])
    with st.expander("✏️ Thêm / sửa hàng loạt dạng bảng"):
        st.caption("Thêm dòng ở cuối bảng; xóa: tick ô đầu dòng rồi bấm biểu tượng thùng rác trên bảng → bấm Lưu.")
        render_work_notes_editor(base_ctx["week_notes"], start_date, end_date)

    st.divider()
    st.subheader("🎯 Theo dõi ticket (AEGONA...)")
    st.caption(
        "Ticket AEGONA cần follow + giờ/MD đã dùng theo tháng. Đổi trạng thái bằng dropdown trong bảng rồi bấm **Lưu**; "
        "giờ theo tháng lấy từ file báo cáo AEGONA (mục 📥 bên dưới). Báo cáo tuần ghi mục **Theo dõi ticket**: các mục "
        "còn mở + mục đổi trạng thái trong tuần, dạng `dd/mm: #ID – Tiêu đề – Trạng thái`."
    )
    render_ticket_tracking_editor(tracking_items, tracking_logs, start_date, end_date)
    st.download_button(
        f"📊 Xuất Excel theo dõi ticket tuần {report_week}/tháng {report_month} ({len(base_ctx['week_tracking'])} mục)",
        data=generate_tracking_excel(base_ctx),
        file_name=f"NAMLE - THEO DOI TICKET - TUAN {report_week:02d} THANG {report_month:02d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="btn_export_tracking_xlsx",
    )
    render_tracking_import_box(tracking_items)
    issues = st.text_area("Vấn đề gặp phải / Rủi ro cần lưu ý", placeholder="Nhập các vấn đề nếu có...")

    with st.expander("👀 Xem trước nội dung báo cáo theo mẫu"):
        preview = build_weekly_sections(dict(base_ctx, issues=issues))
        for title, key in (("I.1. Tóm tắt chung", "summary"), ("I.2. Công việc đã thực hiện trong tuần", "done"),
                           ("I.3. Công việc đang tiến hành / dở dang", "doing")):
            st.markdown(f"##### {title}")
            st.markdown(report_lines_markdown(preview[key]) if preview[key] else "_(Không có)_")
        st.markdown("##### II. Các công việc đã nêu tuần trước nhưng chưa được giải quyết")
        if preview["carried"]:
            st.dataframe(pd.DataFrame(preview["carried"]).rename(columns={
                "content": "Nội dung", "status": "Tình trạng hiện tại", "reason": "Nguyên nhân chưa giải quyết",
                "next": "Hướng xử lý tiếp theo & dự kiến hoàn thành"}), hide_index=True, width="stretch")
        else:
            st.markdown("_(Không có)_")
        st.markdown(f"##### III. Kế hoạch công việc tuần sau ({preview['next_week_text']})")
        if preview["plan"]:
            st.dataframe(pd.DataFrame(preview["plan"]).rename(columns={
                "content": "Nội dung công việc", "goal": "Mục tiêu / Kết quả kỳ vọng", "require": "Yêu cầu kết quả đạt được"}),
                hide_index=True, width="stretch")
        else:
            st.markdown("_(Giữ nguyên bảng trống của file mẫu)_")

    st.divider()
    if not DOCX_AVAILABLE:
        st.error("Chưa cài thư viện `python-docx`. Vui lòng chạy `pip install python-docx` rồi khởi động lại app để dùng tính năng xuất Word.")
    else:
        # Bổ sung phần nhập tay vào ngữ cảnh đã dựng ở trên
        report_ctx = dict(base_ctx, issues=issues)

        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            st.caption("Dùng đúng file mẫu công ty (logo, khung tự đánh giá...) — điền mục I (tóm tắt / đã làm / dở dang), "
                       "II (tuần trước chưa giải quyết) và III (kế hoạch tuần sau).")
            if st.button("📄 Xuất theo Mẫu Công ty (.docx)", type="primary", use_container_width=True):
                if not os.path.exists(TEMPLATE_PATH):
                    st.error(
                        f"Không tìm thấy file mẫu tại `{TEMPLATE_PATH}`. "
                        "Vui lòng tạo thư mục `templates/` cạnh app.py và đặt file mẫu công ty vào đó "
                        "với tên `BaoCaoTuan_Template.docx`."
                    )
                else:
                    try:
                        docx_buffer = generate_weekly_report_from_template(TEMPLATE_PATH, report_ctx)
                        st.session_state["weekly_report_buffer"] = docx_buffer.getvalue()
                        st.session_state["weekly_report_filename"] = f"NAMLE - BC-TUAN {report_week:02d} THANG {report_month:02d}.docx"
                        st.success("Đã tạo file theo mẫu công ty. Bấm nút bên dưới để tải về.")
                    except ValueError as e:
                        st.error(f"Không khớp được cấu trúc file mẫu: {e}")

        with exp_col2:
            st.caption("Bản tổng quát đơn giản do hệ thống tự dựng (không theo layout công ty) — dùng khi chưa có file mẫu.")
            if st.button("📋 Xuất bản tổng quát (.docx)", use_container_width=True):
                docx_buffer = generate_weekly_report_docx(report_ctx)
                st.session_state["weekly_report_buffer"] = docx_buffer.getvalue()
                st.session_state["weekly_report_filename"] = f"BaoCao_Tuan{report_week}_Thang{report_month}_{report_year}_TongQuat.docx"
                st.success("Đã tạo file báo cáo. Bấm nút bên dưới để tải về.")

        try:
            agn_pdf = build_agn_pdf_bytes(tracking_items)
        except Exception as e:
            agn_pdf = None
            st.error(f"Không tạo được PDF AEGONA: {e}")
        if agn_pdf:
            st.download_button(
                "📄 Tải PDF báo cáo AEGONA (gửi kèm email)", data=agn_pdf,
                file_name=f"NAMLE - BAO CAO AEGONA - TUAN {report_week:02d} THANG {report_month:02d}.pdf",
                mime="application/pdf", use_container_width=True, key="btn_weekly_agn_pdf",
            )
        if st.session_state.get("weekly_report_buffer"):
            st.download_button(
                "⬇️ Tải file báo cáo Word",
                data=st.session_state["weekly_report_buffer"],
                file_name=st.session_state.get("weekly_report_filename", "BaoCao.docx"),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

elif page == "📊 Báo cáo Ticket":
    if not is_admin():
        st.warning("🔐 Chức năng này chỉ dành cho Admin. Vui lòng đăng nhập ở sidebar.")
        st.stop()
    render_ticket_report_page()

elif page == "⚙️ Cài đặt":
    if not is_admin():
        st.warning("🔐 Chức năng này chỉ dành cho Admin. Vui lòng đăng nhập ở sidebar.")
        st.stop()

    st.markdown('<div class="main-header">⚙️ Cài đặt hệ thống</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Cấu hình email và lịch gửi báo cáo tuần</div>', unsafe_allow_html=True)

    cfg = db.get_settings()

    tab_smtp, tab_schedule, tab_speed = st.tabs(["📮 Cấu hình SMTP", "🗓️ Lịch gửi báo cáo tuần", "⏱️ Kiểm tra tốc độ"])

    with tab_smtp:
        st.caption(
            "Thông tin này lưu trong CSDL, không nằm trong mã nguồn. "
            "Với Gmail phải dùng **App Password** (16 ký tự) chứ không dùng mật khẩu đăng nhập thường."
        )
        sc1, sc2 = st.columns(2)
        with sc1:
            smtp_host = st.text_input("SMTP Host", value=cfg.get("smtp_host", ""), placeholder="smtp.gmail.com")
            smtp_user = st.text_input("Tài khoản đăng nhập", value=cfg.get("smtp_user", ""), placeholder="ten@gmail.com")
            smtp_sender = st.text_input("Email người gửi (From)", value=cfg.get("smtp_sender", ""), placeholder="ten@gmail.com")
        with sc2:
            smtp_port = st.text_input("Port", value=cfg.get("smtp_port", "587"), placeholder="587")
            smtp_password = st.text_input(
                "Mật khẩu / App Password", value=cfg.get("smtp_password", ""), type="password",
            )
            smtp_sender_name = st.text_input(
                "Tên hiển thị người gửi", value=cfg.get("smtp_sender_name", Config.OWNER),
            )
        security_options = ["STARTTLS", "SSL", "NONE"]
        current_security = cfg.get("smtp_security", "STARTTLS")
        smtp_security = st.radio(
            "Bảo mật kết nối",
            security_options,
            index=security_options.index(current_security) if current_security in security_options else 0,
            horizontal=True,
            help="Gmail/Outlook port 587 dùng STARTTLS, port 465 dùng SSL.",
        )

        if st.button("💾 Lưu cấu hình SMTP", type="primary", use_container_width=True):
            db.save_settings({
                "smtp_host": smtp_host.strip(),
                "smtp_port": smtp_port.strip(),
                "smtp_user": smtp_user.strip(),
                "smtp_password": smtp_password,
                "smtp_sender": smtp_sender.strip(),
                "smtp_sender_name": smtp_sender_name.strip(),
                "smtp_security": smtp_security,
            })
            st.success("Đã lưu cấu hình SMTP.")
            st.rerun()

        st.divider()
        st.markdown("##### 🧪 Gửi email thử")
        test_to = st.text_input("Gửi thử tới", value=cfg.get("smtp_sender", ""), key="smtp_test_to")
        if st.button("📨 Gửi email thử", use_container_width=True, key="btn_smtp_test"):
            missing = mailer.validate_smtp_config(smtp_config_from_settings(cfg))
            if missing:
                st.error("Chưa lưu đủ cấu hình: " + ", ".join(missing) + ". Hãy bấm Lưu cấu hình SMTP trước.")
            elif not test_to.strip():
                st.warning("Vui lòng nhập email nhận thử.")
            else:
                try:
                    mailer.send_email(
                        smtp_config_from_settings(cfg),
                        mailer.parse_recipients(test_to), [],
                        f"[{Config.APP_NAME}] Email thử cấu hình SMTP",
                        "Nếu bạn nhận được email này, cấu hình SMTP đã hoạt động.",
                    )
                    st.success(f"Đã gửi email thử tới {test_to}. Kiểm tra hộp thư (kể cả mục Spam).")
                except Exception as e:
                    st.error(f"Gửi thất bại: {e}")

    with tab_schedule:
        st.caption(
            "Hệ thống gửi **file .docx theo mẫu công ty** của tuần hiện tại. "
            "Giờ nhập ở đây là **giờ Việt Nam**."
        )

        enabled = st.toggle("Bật gửi báo cáo tuần tự động", value=cfg.get("report_email_enabled") == "1")

        rc1, rc2 = st.columns(2)
        with rc1:
            weekday_index = int(cfg.get("report_email_weekday", "5") or 5)
            report_weekday = st.selectbox(
                "Gửi vào",
                list(range(7)),
                index=weekday_index if 0 <= weekday_index <= 6 else 5,
                format_func=lambda i: WEEKDAY_LABELS[i],
            )
        with rc2:
            try:
                hh, mm = (cfg.get("report_email_time") or "17:00").split(":")
                default_time = datetime.time(int(hh), int(mm))
            except (ValueError, TypeError):
                default_time = datetime.time(17, 0)
            report_time = st.time_input("Lúc (giờ VN)", value=default_time)

        email_to = st.text_area(
            "Người nhận (To)",
            value=cfg.get("report_email_to", ""),
            height=80,
            placeholder="Nhiều email cách nhau bằng dấu phẩy hoặc xuống dòng",
        )
        email_cc = st.text_area(
            "CC (tùy chọn)", value=cfg.get("report_email_cc", ""), height=68,
        )
        email_reporter = st.text_input(
            "Tên người báo cáo trong file", value=cfg.get("report_email_reporter", Config.OWNER),
        )

        if st.button("💾 Lưu lịch gửi", type="primary", use_container_width=True):
            db.save_settings({
                "report_email_enabled": "1" if enabled else "0",
                "report_email_weekday": str(report_weekday),
                "report_email_time": report_time.strftime("%H:%M"),
                "report_email_to": email_to.strip(),
                "report_email_cc": email_cc.strip(),
                "report_email_reporter": email_reporter.strip(),
            })
            st.success("Đã lưu lịch gửi báo cáo tuần.")
            st.rerun()

        st.divider()
        st.markdown("##### 📤 Gửi ngay (không chờ lịch)")
        st.caption("Gửi báo cáo tuần hiện tại ngay lập tức. Không tính là lần gửi tự động của tuần.")
        if st.button("📤 Gửi báo cáo tuần ngay", use_container_width=True, key="btn_send_report_now"):
            with st.spinner("Đang tạo báo cáo và gửi email..."):
                ok, msg = send_weekly_report_email(cfg, db_tickets, db_tasks, mark_sent=False)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

        st.divider()
        st.markdown("##### 📋 Tình trạng")
        now_local = now_vn()
        st.write(f"- Giờ hệ thống (VN): **{now_local.strftime('%d/%m/%Y %H:%M')}**")
        st.write(f"- Lần gửi tự động gần nhất: **{cfg.get('report_email_last_sent_at') or 'Chưa gửi lần nào'}**")
        if cfg.get("report_email_last_week"):
            st.write(f"- Tuần đã gửi: **{cfg.get('report_email_last_week')}**")
        if cfg.get("report_email_last_error"):
            st.error(f"Lỗi lần gửi gần nhất: {cfg.get('report_email_last_error')}")

        st.markdown("##### 🗂️ Lịch sử gửi theo tuần")
        email_logs = db.get_report_email_logs()
        if email_logs:
            history = []
            for l in email_logs:
                d = to_date(l["target_date"])
                history.append({
                    "Tuần": f"Tuần {week_of_month(d)} - T{d.month:02d}/{d.year}",
                    "Thời điểm": l["created_at"].strftime("%d/%m/%Y %H:%M"),
                    "Kết quả": "✅ Đã gửi" if l["status"] == "sent" else "❌ Lỗi",
                    "Cách gửi": "Tự động" if l["trigger_type"] == "auto" else "Gửi ngay",
                    "Người nhận": l.get("recipients") or "",
                    "Chi tiết": l.get("message") or "",
                })
            st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
        else:
            st.caption("Chưa có lần gửi nào được ghi nhận.")

        st.info(
            "⚠️ **Lưu ý về độ chính xác của giờ gửi:** Streamlit Cloud cho app ngủ khi không có ai truy cập, "
            "nên hệ thống kiểm tra lịch mỗi lần có người mở app. Nếu qua giờ hẹn mà cả ngày không ai vào app, "
            "email sẽ được gửi ở lần truy cập kế tiếp (vẫn trong tuần đó, không bị gửi trùng). "
            "Muốn gửi đúng giờ tuyệt đối cần thêm bộ hẹn giờ chạy bên ngoài (ví dụ GitHub Actions)."
        )

    with tab_speed:
        st.caption(
            "Đo ngay trên server đang chạy app (Streamlit Cloud), không phải từ máy bạn. "
            "Dùng để biết trang chậm do DB (khoảng cách server ↔ TiDB Singapore) hay do Streamlit."
        )
        if st.button("⏱️ Đo tốc độ DB", key="btn_speed_test"):
            def timed(fn):
                started = time.perf_counter()
                result = fn()
                return (time.perf_counter() - started) * 1000, result

            def select_one():
                conn = db.get_connection()
                cursor = conn.cursor()
                rtts = []
                for _ in range(3):
                    started = time.perf_counter()
                    cursor.execute("SELECT 1")
                    cursor.fetchall()
                    rtts.append((time.perf_counter() - started) * 1000)
                cursor.close()
                conn.close()
                return min(rtts)

            rows = []
            rtt = select_one()
            rows.append({"Bước": "1 lượt đi-về server ↔ DB (SELECT 1)", "Thời gian (ms)": round(rtt)})
            ms, _ = timed(lambda: mysql.connector.connect(**db.DB_CONFIG).close())
            rows.append({"Bước": "Mở kết nối SSL mới (không qua pool)", "Thời gian (ms)": round(ms)})
            total_db = 0
            for name in ["get_all_tickets", "get_tasks", "get_settings", "get_work_notes", "get_work_note_drafts", "get_ticket_tracking", "get_ticket_tracking_logs", "get_report_email_logs"]:
                fn = getattr(db, name)
                fn.clear()
                ms, data = timed(fn)
                total_db += ms
                rows.append({"Bước": f"{name}() — không cache ({len(data)} dòng)", "Thời gian (ms)": round(ms)})
            ms, _ = timed(db.get_all_tickets)
            rows.append({"Bước": "get_all_tickets() — có cache", "Thời gian (ms)": round(ms)})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

            if rtt > 100:
                st.warning(
                    f"Mỗi lượt đi-về tới DB mất ~{rtt:.0f}ms → server Streamlit ở xa TiDB (Singapore). "
                    f"Lần tải trang khi hết cache tốn ~{total_db / 1000:.1f}s chỉ riêng cho DB. "
                    "Cách khắc phục triệt để: tạo cluster TiDB ở region gần server Streamlit rồi chuyển dữ liệu."
                )
            else:
                st.success(
                    f"DB phản hồi nhanh (~{rtt:.0f}ms/lượt, ~{total_db / 1000:.1f}s cho toàn bộ truy vấn khi hết cache). "
                    "Nếu trang vẫn chậm thì nguyên nhân nằm ở Streamlit (app ngủ/khởi động lại, dựng giao diện)."
                )

else:
    st.markdown(f'<div class="main-header">{page}</div>', unsafe_allow_html=True)
    st.info("🚧 Phân hệ này đang được thiết kế giao diện.")
