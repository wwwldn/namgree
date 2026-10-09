import streamlit as st
import pandas as pd
import json
import os
import datetime
import random
import secrets
import calendar
import io
import re
from config import Config
import db
import mailer

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

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
ADMIN_PASSWORD = "gree@2025"  # Đổi password tại đây

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

# Thiết lập cấu hình trang
st.set_page_config(
    page_title=Config.APP_NAME,
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🏠",
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

# Hàm sinh mã Ticket tự động
def gen_ticket_id():
    now = datetime.datetime.now()
    return f"GREE-IT_{now.strftime('%Y%m')}_{random.randint(100, 999)}"

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

def build_report_context(year, month, week, reporter, tickets, tasks, manual_tasks="", issues=""):
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
        "manual_tasks": manual_tasks,
        "issues": issues,
        "week_relevant_tickets": week_relevant_tickets,
        "week_new_tickets": week_new_tickets,
        "week_completed_tasks": week_completed_tasks,
    }

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
    """Dựng báo cáo tuần theo mẫu công ty và gửi kèm email. Trả về (thành công, thông báo)."""
    if not DOCX_AVAILABLE:
        return False, "Chưa cài thư viện python-docx nên không tạo được file báo cáo."
    if not os.path.exists(TEMPLATE_PATH):
        return False, f"Không tìm thấy file mẫu công ty tại {TEMPLATE_PATH}."

    to_list = mailer.parse_recipients(settings.get("report_email_to"))
    cc_list = mailer.parse_recipients(settings.get("report_email_cc"))
    if not to_list:
        return False, "Chưa cấu hình người nhận (To)."

    target_date = target_date or now_vn().date()
    year, month = target_date.year, target_date.month
    week = min(week_of_month(target_date), max_weeks_in_month(year, month))

    ctx = build_report_context(
        year, month, week,
        settings.get("report_email_reporter") or Config.OWNER,
        tickets, tasks,
    )

    try:
        buffer = generate_weekly_report_from_template(TEMPLATE_PATH, ctx)
    except Exception as e:
        return False, f"Lỗi khi tạo file báo cáo từ mẫu: {e}"

    filename = f"NAMLE - BC-TUAN {week:02d} THANG {month:02d}.docx"
    period = f"{ctx['start_date'].strftime('%d/%m/%Y')} - {ctx['end_date'].strftime('%d/%m/%Y')}"
    subject = f"[Gree IT] Báo cáo tuần {week:02d}/tháng {month:02d}/{year} - {ctx['reporter']}"
    body = (
        f"Kính gửi Anh/Chị,\n\n"
        f"Báo cáo công việc tuần {week} tháng {month}/{year} ({period}) được đính kèm trong email này.\n\n"
        f"Người báo cáo: {ctx['reporter']}\n\n"
        f"(Email được gửi tự động từ hệ thống {Config.APP_NAME}.)"
    )

    try:
        mailer.send_email(
            smtp_config_from_settings(settings), to_list, cc_list,
            subject, body, buffer.getvalue(), filename,
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

    doc.add_heading("4. Công việc bổ sung (nhập tay)", level=2)
    doc.add_paragraph(ctx['manual_tasks'].strip() if ctx['manual_tasks'] else "(Không có)")

    doc.add_heading("5. Vấn đề gặp phải / Lưu ý", level=2)
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
    return f"{t.get('id', '')} – {detail} ({requester}) – {status}."

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
    if not lines:
        lines = [("Không có công việc nào trong tuần này.", False)]
    return lines

def set_cell_lines(cell, lines):
    """Ghi nội dung mới vào 1 cell (list (text, bold)), mỗi tuple thành 1 paragraph riêng.
    Giữ định dạng (font) gốc của cell bằng cách tái sử dụng đoạn/run đầu tiên."""
    paragraphs = list(cell.paragraphs)
    for p in paragraphs[1:]:
        p._element.getparent().remove(p._element)
    base_p = cell.paragraphs[0]
    for r in list(base_p.runs):
        r._element.getparent().remove(r._element)
    if not lines:
        return
    first_text, first_bold = lines[0]
    run = base_p.add_run(first_text)
    run.bold = first_bold
    for text, bold in lines[1:]:
        p = cell.add_paragraph()
        r = p.add_run(text)
        r.bold = bold

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

def find_main_content_table(doc):
    """Tìm bảng (kể cả lồng trong cell khác) có cột tiêu đề 'Các công việc thực hiện'."""
    def search(tables):
        for tbl in tables:
            if tbl.rows:
                header_texts = [c.text.strip() for c in tbl.rows[0].cells]
                if "Các công việc thực hiện" in header_texts:
                    return tbl
            for row in tbl.rows:
                for cell in row.cells:
                    found = search(cell.tables)
                    if found is not None:
                        return found
        return None
    return search(doc.tables)

def find_row_by_content(table, keyword, content_col_label="Nội dung"):
    """Tìm dòng trong bảng mà cột 'Nội dung' chứa keyword (vd: 'HỆ THỐNG BẢO HÀNH')."""
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    col_idx = header_cells.index(content_col_label) if content_col_label in header_cells else 1
    for row in table.rows[1:]:
        if keyword in row.cells[col_idx].text:
            return row
    return None

def find_next_week_plan_table(doc):
    """Tìm bảng 'KẾ HOẠCH CÔNG VIỆC TUẦN SAU' — nhận diện qua cặp cột đặc trưng
    'Người thực hiện' + 'Ghi chú' (khác với bảng 'Tuần trước chưa giải quyết' dùng
    'Người giải quyết trực tiếp')."""
    def search(tables):
        for tbl in tables:
            if tbl.rows:
                header_texts = set()
                for r in tbl.rows[:2]:
                    for c in r.cells:
                        header_texts.add(c.text.strip())
                if "Người thực hiện" in header_texts and "Ghi chú" in header_texts:
                    return tbl
            for row in tbl.rows:
                for cell in row.cells:
                    found = search(cell.tables)
                    if found is not None:
                        return found
        return None
    return search(doc.tables)

def update_next_week_plan_notes(doc, note_text):
    """Điền khoảng ngày của TUẦN KẾ TIẾP vào cột 'Ghi chú' cho mọi dòng nội dung
    (1. ERP, 2. Hệ thống Bảo hành...) của bảng Kế hoạch công việc tuần sau."""
    table = find_next_week_plan_table(doc)
    if table is None:
        return False
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    if "Ghi chú" not in header_cells:
        return False
    ghi_chu_idx = header_cells.index("Ghi chú")
    content_start = None
    for ri, row in enumerate(table.rows):
        if row.cells[0].text.strip().isdigit():
            content_start = ri
            break
    if content_start is None:
        return False
    for row in table.rows[content_start:]:
        set_cell_lines(row.cells[ghi_chu_idx], [(note_text, False)])
    return True

def update_all_rows_time(table, time_text):
    """Điền cùng 1 khoảng thời gian vào cột 'T/g giải quyết' cho TẤT CẢ các dòng nội dung
    (1. ERP, 2. Hệ thống Bảo hành, 3. Gree App, 4. CV IT cơ bản) — chỉ cột thời gian,
    không đụng tới nội dung công việc của các dòng ngoài Hệ thống Bảo hành."""
    header_cells = [c.text.strip() for c in table.rows[0].cells]
    if "T/g giải quyết" not in header_cells:
        return False
    time_idx = header_cells.index("T/g giải quyết")
    for row in table.rows[1:]:
        set_cell_lines(row.cells[time_idx], [(time_text, False)])
    return True

def generate_weekly_report_from_template(template_path, ctx):
    """Đổ dữ liệu vào ĐÚNG file mẫu công ty (giữ logo/layout/song ngữ/khung tự đánh giá...),
    chỉ thay: tiêu đề tuần, tên người báo cáo, nội dung dòng HỆ THỐNG BẢO HÀNH + ERP, cột T/g giải quyết
    của cả 4 dòng, và cột Ghi chú (thời gian) của bảng Kế hoạch công việc tuần sau."""
    doc = Document(template_path)

    update_title_paragraphs(doc, ctx['week'], ctx['month'], ctx['year'], ctx['reporter'])

    table = find_main_content_table(doc)
    if table is None:
        raise ValueError("Không tìm thấy bảng có cột 'Các công việc thực hiện' trong file mẫu.")

    row = find_row_by_content(table, "HỆ THỐNG BẢO HÀNH")
    if row is None:
        raise ValueError("Không tìm thấy dòng 'HỆ THỐNG BẢO HÀNH' trong file mẫu.")

    header_cells = [c.text.strip() for c in table.rows[0].cells]
    content_idx = header_cells.index("Các công việc thực hiện")
    set_cell_lines(row.cells[content_idx], build_domain_section_lines(ctx['week_relevant_tickets'], "warranty"))

    # Mục "1. ERP" — best-effort: nếu file mẫu không có dòng này thì bỏ qua, không raise lỗi
    erp_row = find_row_by_content(table, "ERP")
    if erp_row is not None:
        set_cell_lines(erp_row.cells[content_idx], build_domain_section_lines(ctx['week_relevant_tickets'], "erp"))

    # Mục "3. GREE APP" — best-effort tương tự
    gree_app_row = find_row_by_content(table, "GREE APP")
    if gree_app_row is not None:
        set_cell_lines(gree_app_row.cells[content_idx], build_domain_section_lines(ctx['week_relevant_tickets'], "gree_app"))

    time_text = f"{ctx['start_date'].strftime('%d/%m')}-{ctx['end_date'].strftime('%d/%m')}/{ctx['end_date'].year}"
    update_all_rows_time(table, time_text)

    next_monday = ctx['start_date'] + datetime.timedelta(days=7)
    next_saturday = next_monday + datetime.timedelta(days=5)
    next_week_text = f"{next_monday.strftime('%d/%m')}-{next_saturday.strftime('%d/%m')}/{next_saturday.year}"
    update_next_week_plan_notes(doc, next_week_text)

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
        
        # Vẽ các tin nhắn
        for m in target_t['msgs']:
            is_admin_msg = m['user'].startswith("Admin")
            # Trong chế độ guest, ẩn log nội bộ để bảo mật!
            if m['type'] == "internal":
                continue
            with st.chat_message("assistant" if is_admin_msg else "user"):
                label = "🔒 Nội bộ" if m['type'] == "internal" else "🌐 Công khai"
                st.write(f"**{m['user']}** ({label})")
                st.write(m['msg'])
                # Hiển thị ngày và giờ cùng nhau
                st.caption(f"{m.get('date', '')} • {m.get('time', '')}")

        # Gửi log mới (chỉ cho phép Công khai trong chế độ Guest)
        st.divider()
        st.markdown("##### 📩 Gửi phản hồi mới")
        guest_name = st.text_input("Tên của bạn", value=target_t['requester'], key="guest_msg_name")
        guest_msg = st.text_area("Nội dung phản hồi...", height=80, key="guest_msg_val")

        if st.button("📩 Gửi phản hồi", use_container_width=True, key="btn_guest_send"):
            if guest_msg and guest_name:
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
                    )
                    st.rerun()
                else:
                    db.update_ticket_status(target_t['id'], share_status)
                    st.rerun()
            if col_out.button("🚪 Thoát Admin", use_container_width=True, key="btn_share_logout"):
                logout_admin()
                st.rerun()
        else:
            with st.expander("🔐 Đăng nhập Admin để cập nhật trạng thái"):
                st.caption(f"Đăng nhập một lần, ghi nhớ {ADMIN_SESSION_DAYS} ngày trên trình duyệt này.")
                share_pw = st.text_input("Mật khẩu", type="password", key="share_admin_pw")
                if st.button("Đăng nhập", use_container_width=True, key="btn_share_login"):
                    if share_pw == ADMIN_PASSWORD:
                        login_admin()
                        st.rerun()
                    else:
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
# THANH ĐIỀU HƯỚNG (SIDEBAR)
# -----------------
# -----------------
# TỰ ĐỘNG GỬI BÁO CÁO TUẦN
# -----------------
# Streamlit Cloud cho app ngủ khi không ai truy cập nên không thể chạy scheduler nền.
# Thay vào đó kiểm tra mỗi lần có người mở app: quá giờ hẹn và tuần này chưa gửi thì gửi.
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
    menu = base_menu + ["⚙️ Cài đặt"] if is_admin() else base_menu

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
    else:
        with st.expander("🔐 Admin Login"):
            pw_input = st.text_input("Mật khẩu", type="password", key="admin_pw_input")
            if st.button("Đăng nhập", use_container_width=True, key="btn_admin_login"):
                if pw_input == ADMIN_PASSWORD:
                    login_admin()
                    st.rerun()
                else:
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
                    new_id = gen_ticket_id()
                    form_type = form_choice_type
                    status = "Hoàn thành" if form_choice_type == "Admin_Web_Noted_Log_Ho_Tro" else "Mới tạo"
                    subject = form_choice
                    if form_choice_type in GENERAL_FORM_TYPES and str(form_data.get('request_title') or "").strip():
                        subject = form_data['request_title']

                    if db.create_ticket(new_id, subject, t_user, form_type, form_data, status):
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

    col_list, col_detail = st.columns([0.4, 0.6])
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

        for t in filtered_tickets:
            with st.container(border=True):
                badge_html = status_badge(t['status'])
                st.markdown(f"**{t['id']}** &nbsp; {badge_html}", unsafe_allow_html=True)
                st.caption(f"Từ: {t['requester']} - {t['subject']}")
                if st.button("Xem chi tiết", key=f"btn_{state_key}_{t['id']}"):
                    st.session_state[active_key] = t["id"]

    with col_detail:
        st.subheader("💬 Luồng xử lý (Chat-log)")
        active_ticket_id = st.session_state.get(active_key)
        active_candidates = [t for t in scoped_tickets if t["id"] == active_ticket_id]
        if active_ticket_id and not active_candidates:
            st.info("Ticket đang chọn không thuộc Form/phạm vi hiện tại. Hãy chọn ticket bên trái.")
        elif active_candidates:
            current_t = active_candidates[0]

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
            for m in current_t['msgs']:
                is_admin_msg = m['user'].startswith("Admin")
                with st.chat_message("assistant" if is_admin_msg else "user"):
                    label = "🔒 Nội bộ" if m['type'] == "internal" else "🌐 Công khai"
                    st.write(f"**{m['user']}** ({label})")
                    st.write(m['msg'])
                    # Hiển thị ngày và giờ cùng nhau
                    st.caption(f"{m.get('date', '')} • {m.get('time', '')}")

            # Nhập Log mới — Admin only
            st.divider()
            if is_admin():
                log_msg = st.text_area("Nhập nội dung xử lý (Log)...", height=120, placeholder="Bạn có thể nhập nhiều dòng nội dung log xử lý tại đây...", key=f"log_msg_{state_key}")
                log_type = st.radio("Loại log:", ["Công khai", "Nội bộ (Chỉ Admin)"], horizontal=True, key=f"log_type_{state_key}")

                c_btn1, c_btn2 = st.columns(2)
                if c_btn1.button("📩 Gửi Log", use_container_width=True, key=f"send_log_{state_key}"):
                    if log_msg:
                        mtype = "internal" if "Nội bộ" in log_type else "public"
                        db.add_ticket_message(current_t['id'], "Admin Nam", log_msg, mtype)
                        st.rerun()
                    else:
                        st.warning("Vui lòng nhập nội dung")

                # Dropdown chuyển trạng thái
                st.divider()
                st.markdown("**🔄 Chuyển trạng thái Ticket:**")
                current_status = current_t['status']
                new_status = st.selectbox(
                    "Chọn trạng thái mới",
                    STATUS_LIST,
                    index=STATUS_LIST.index(current_status) if current_status in STATUS_LIST else 0,
                    key=f"status_change_{state_key}"
                )
                col_s1, col_s2 = st.columns(2)
                if col_s1.button("🔄 Cập nhật trạng thái", use_container_width=True, key=f"update_status_{state_key}"):
                    if new_status != current_status:
                        if new_status == "Hoàn thành":
                            action_log = log_msg if log_msg else "Admin đã đánh dấu hoàn thành"
                            db.complete_ticket(current_t['id'], current_t['subject'], action_log)
                            st.balloons()
                        else:
                            db.update_ticket_status(current_t['id'], new_status)
                        st.rerun()
                    else:
                        st.info("Trạng thái không thay đổi.")
                if col_s2.button("❌ Từ chối Ticket", use_container_width=True, key=f"reject_{state_key}"):
                    if current_status != "Từ chối":
                        db.update_ticket_status(current_t['id'], "Từ chối")
                        st.rerun()
                    else:
                        st.info("Ticket này đã bị từ chối rồi.")

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
            col_widths = [1.4, 2.5, 2.2, 1.5, 1.2, 1.5, 1.2]
            header_cols = st.columns(col_widths)
            headers = ["Mã Ticket", "Tiêu đề", "Loại Form", "Người y/c", "Ngày tạo", "Trạng thái", ""]
            for col, h in zip(header_cols, headers):
                col.markdown(f"**{h}**")
            st.markdown("<hr style='margin:4px 0 8px 0;border-color:#e5e7eb;'>", unsafe_allow_html=True)

            for t in filtered:
                f_type = normalize_form_type(t.get("form_type"))
                f_label = FORM_TYPE_TO_CONFIG.get(f_type, {}).get("label", f_type or "—")
                short_label = re.sub(r"^(Form \d+|ERP-\d+|GreeApp-\d+):\s*", "", f_label)
                tid = t.get("id", "")

                r_cols = st.columns(col_widths)
                # Bấm mã ticket: mở màn xem nhanh ở tab mới (dùng để gửi link cho người khác)
                r_cols[0].markdown(
                    f"<a href='/?ticket={tid}' target='_blank' rel='noreferrer' "
                    f"style='font-family:monospace;font-size:0.85em;color:#2563eb;"
                    f"text-decoration:none;font-weight:600;'>{tid}</a>",
                    unsafe_allow_html=True
                )
                r_cols[1].markdown(t.get("subject") or "—")
                r_cols[2].markdown(f"<span style='font-size:0.85em;color:#6B7280;'>{short_label}</span>", unsafe_allow_html=True)
                r_cols[3].markdown(t.get("requester") or "—")
                r_cols[4].markdown(f"<span style='font-size:0.85em;'>{format_ticket_date(t.get('created_at'))}</span>", unsafe_allow_html=True)
                r_cols[5].markdown(status_badge(t.get("status", "")), unsafe_allow_html=True)
                # Nút: mở thẳng trong app (có quyền Admin để xử lý ticket)
                if r_cols[6].button("Chi tiết", key=f"home_goto_{tid}", use_container_width=True):
                    goto_ticket_detail(t)
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

    # Số liệu báo cáo dựng bằng hàm dùng chung với chức năng gửi email tự động
    base_ctx = build_report_context(report_year, report_month, report_week, reporter_name, db_tickets, db_tasks)
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
    st.subheader("📝 Bổ sung nội dung báo cáo (nhập tay)")
    manual_tasks = st.text_area("Công việc khác ngoài hệ thống ticket", placeholder="Những việc đã làm nhưng chưa tạo ticket...")
    issues = st.text_area("Vấn đề gặp phải / Rủi ro cần lưu ý", placeholder="Nhập các vấn đề nếu có...")

    st.divider()
    if not DOCX_AVAILABLE:
        st.error("Chưa cài thư viện `python-docx`. Vui lòng chạy `pip install python-docx` rồi khởi động lại app để dùng tính năng xuất Word.")
    else:
        # Bổ sung phần nhập tay vào ngữ cảnh đã dựng ở trên
        report_ctx = dict(base_ctx, manual_tasks=manual_tasks, issues=issues)

        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            st.caption("Dùng đúng file mẫu công ty (logo, song ngữ, khung tự đánh giá...) — chỉ đổ dữ liệu vào mục Hệ thống Bảo hành.")
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

        if st.session_state.get("weekly_report_buffer"):
            st.download_button(
                "⬇️ Tải file báo cáo Word",
                data=st.session_state["weekly_report_buffer"],
                file_name=st.session_state.get("weekly_report_filename", "BaoCao.docx"),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )

elif page == "⚙️ Cài đặt":
    if not is_admin():
        st.warning("🔐 Chức năng này chỉ dành cho Admin. Vui lòng đăng nhập ở sidebar.")
        st.stop()

    st.markdown('<div class="main-header">⚙️ Cài đặt hệ thống</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Cấu hình email và lịch gửi báo cáo tuần</div>', unsafe_allow_html=True)

    cfg = db.get_settings()

    tab_smtp, tab_schedule = st.tabs(["📮 Cấu hình SMTP", "🗓️ Lịch gửi báo cáo tuần"])

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

        st.info(
            "⚠️ **Lưu ý về độ chính xác của giờ gửi:** Streamlit Cloud cho app ngủ khi không có ai truy cập, "
            "nên hệ thống kiểm tra lịch mỗi lần có người mở app. Nếu qua giờ hẹn mà cả ngày không ai vào app, "
            "email sẽ được gửi ở lần truy cập kế tiếp (vẫn trong tuần đó, không bị gửi trùng). "
            "Muốn gửi đúng giờ tuyệt đối cần thêm bộ hẹn giờ chạy bên ngoài (ví dụ GitHub Actions)."
        )

else:
    st.markdown(f'<div class="main-header">{page}</div>', unsafe_allow_html=True)
    st.info("🚧 Phân hệ này đang được thiết kế giao diện.")
