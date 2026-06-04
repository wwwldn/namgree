import streamlit as st
import pandas as pd
import json
import os
import datetime
import random
from config import Config
import db

# Khởi tạo database và bảng
db.init_db()

# Thiết lập cấu hình trang
st.set_page_config(
    page_title=Config.APP_NAME,
    page_icon="🏠",
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

def status_badge(status_text):
    color = STATUS_COLORS.get(status_text, "#6B7280")
    return f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;font-size:0.85em;font-weight:600;">{status_text}</span>'

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
]

FORM_LABEL_TO_TYPE = {f["label"]: f["type"] for f in FORM_CONFIGS}
FORM_TYPE_TO_CONFIG = {f["type"]: f for f in FORM_CONFIGS}
LEGACY_FORM_TYPES = {
    f["label"]: f["type"] for f in FORM_CONFIGS
}

def normalize_form_type(form_type):
    return LEGACY_FORM_TYPES.get(form_type, form_type)

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
            else:
                row[label] = get_form_value(f_json, key)
        rows.append(row)
    return rows

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
                # Lưu trạng thái để chuyển về Full View
                st.session_state["view_mode"] = "full"
                st.session_state["active_ticket_id"] = target_t["id"]
                st.session_state["selected_page"] = "🛡️ Hệ thống Bảo hành"
                
                # Đồng bộ form_scope
                if target_t.get("form_type"):
                    disp_type = normalize_form_type(target_t.get("form_type"))
                    disp_config = FORM_TYPE_TO_CONFIG.get(disp_type)
                    if disp_config:
                        st.session_state["ticket_form_scope"] = disp_config["label"]
                        
                # Xóa tham số URL
                st.query_params.clear()
                st.rerun()

        # Dữ liệu đính kèm (nếu có)
        if target_t.get('form_data') and target_t.get('form_type'):
            display_form_type = normalize_form_type(target_t.get("form_type"))
            display_form_name = FORM_TYPE_TO_CONFIG.get(display_form_type, {}).get("label", display_form_type)
            st.markdown("---")
            st.markdown(f"#### 📋 Dữ liệu đính kèm: **{display_form_name}**")
            
            # Hiển thị dạng bảng (nếu thuộc cấu hình Form) hoặc JSON
            display_config = FORM_TYPE_TO_CONFIG.get(display_form_type)
            if display_config:
                # Dựng 1 DataFrame gồm 1 hàng duy nhất cho ticket này
                rows_data = build_form_rows([target_t], display_config)
                if rows_data:
                    st.dataframe(pd.DataFrame(rows_data), use_container_width=True)
            else:
                try:
                    f_data = parse_form_data(target_t)
                    st.json(f_data)
                except Exception as e:
                    st.error(f"Lỗi hiển thị dữ liệu Form: {e}")

        # Lịch sử hội thoại (Chat-log)
        st.markdown("---")
        st.markdown("#### 💬 Lịch sử trao đổi & Xử lý (Chat-log)")
        
        # Vẽ các tin nhắn
        for m in target_t['msgs']:
            is_admin = m['user'].startswith("Admin")
            # Trong chế độ guest, ẩn log nội bộ để bảo mật!
            if m['type'] == "internal":
                continue
            with st.chat_message("assistant" if is_admin else "user"):
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
# Khởi tạo trạng thái sitemap page mặc định
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "🏠 Trang chủ"

with st.sidebar:
    st.title(Config.APP_NAME)
    st.markdown(f"**Owner:** {Config.OWNER}")
    st.markdown(f"**Domain:** [{Config.BASE_DOMAIN}{Config.SUB_PATH}](https://{Config.BASE_DOMAIN}{Config.SUB_PATH})")
    st.markdown("---")
    
    menu = [
        "🏠 Trang chủ", 
        "🛡️ Hệ thống Bảo hành", 
        "🏭 Quản trị ERP", 
        "📱 Gree App Support", 
        #"🔍 Tra cứu An Gia", 
        #"📦 Quản lý XNK", 
        #"🔐 Security Audit", 
        #"🌐 Website", 
        "📈 Báo cáo tuần của Nam", 
        "⚙️ Cài đặt"
    ]
    
    # Tìm chỉ số trang hiện tại trong menu để làm default index
    default_page_idx = 0
    if st.session_state["selected_page"] in menu:
        default_page_idx = menu.index(st.session_state["selected_page"])
        
    page = st.radio("SITEMAP HỆ THỐNG", menu, index=default_page_idx)
    st.session_state["selected_page"] = page
    
    st.markdown("---")
    st.caption(f"Admin: {Config.OWNER} | 📅 {datetime.date.today()}")

# -----------------
# GIAO DIỆN CHÍNH
# -----------------

if page == "🏠 Trang chủ":
    st.markdown(f'<div class="main-header">Welcome to {Config.APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Dashboard Tổng quát</div>', unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tổng số Ticket", str(len(db_tickets)), "")
    c2.metric("Đang xử lý", len([t for t in db_tickets if t['status'] not in ['Hoàn thành', 'Từ chối']]))
    c3.metric("Hoàn thành (Tasks)", len(db_tasks))
    c4.metric("NCC Issue", "1", "Gấp")

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
    st.markdown('<div class="main-header">🛡️ Hệ thống Warranty - Bảo Hành</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Quản lý và hỗ trợ xử lý lỗi hệ thống</div>', unsafe_allow_html=True)

    form_scope_options = ["Tất cả Ticket"] + [f["label"] for f in FORM_CONFIGS]
    selected_scope = st.selectbox(
        "Form đang xem",
        form_scope_options,
        key="ticket_form_scope",
    )
    selected_form_type = FORM_LABEL_TO_TYPE.get(selected_scope)
    selected_config = FORM_TYPE_TO_CONFIG.get(selected_form_type)
    scoped_tickets = tickets_for_form(db_tickets, selected_form_type) if selected_form_type else db_tickets
    
    btn_col, hint_col = st.columns([0.28, 0.72])
    with btn_col:
        if st.button("➕ Tạo Ticket mới", use_container_width=True, disabled=selected_config is None):
            st.session_state["show_create_ticket"] = not st.session_state.get("show_create_ticket", False)
    with hint_col:
        if selected_config:
            st.caption(f"Ticket mới sẽ được tạo cho: {selected_scope}")
        else:
            st.caption("Chọn một Form cụ thể để tạo ticket mới.")

    if selected_config and st.session_state.get("show_create_ticket", False):
        form_choice = selected_scope
        form_choice_type = selected_form_type
        with st.container(border=True):
            st.subheader(f"➕ Tạo Ticket mới - {selected_scope}")
        
            t_user = st.text_input("Người yêu cầu", placeholder="Ví dụ: Phượng BH RAC")
        
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

            create_col, close_col = st.columns(2)
            if create_col.button("Khởi tạo mã Ticket", use_container_width=True):
                form5_missing = missing_form5_required_fields(form_data) if form_choice_type == "Dang_Ky_Tai_Khoan_User_Noi_Bo" else []
                if form5_missing:
                    st.warning("Vui lòng nhập đủ thông tin Form 5: " + ", ".join(form5_missing))
                elif t_user:
                    new_id = gen_ticket_id()
                    form_type = form_choice_type
                    status = "Hoàn thành" if form_choice_type == "Admin_Web_Noted_Log_Ho_Tro" else "Mới tạo"
                    subject = form_choice
                    
                    if db.create_ticket(new_id, subject, t_user, form_type, form_data, status):
                        st.success(f"Đã tạo Ticket: {new_id}")
                        st.session_state["show_create_ticket"] = False
                        st.rerun()
                    else:
                        st.error("Lỗi khi kết nối CSDL")
                else:
                    st.warning("Vui lòng nhập Người yêu cầu")
            if close_col.button("Đóng form", use_container_width=True):
                st.session_state["show_create_ticket"] = False
                st.rerun()

    st.markdown("---")

    st.subheader("📊 Dữ liệu danh mục đã cập nhật hệ thống")
    
    # Xác định loại Form cần hiển thị dựa trên selected_scope ở đầu trang
    master_form_options = [f["label"] for f in FORM_CONFIGS]
    
    if selected_scope in master_form_options:
        # Nếu đang chọn một Form cụ thể trên đầu trang
        target_form_label = selected_scope
        is_default_view = False
    else:
        # Nếu đang chọn "Tất cả Ticket", mặc định hiển thị Form 1
        target_form_label = master_form_options[0]  # Form 1
        is_default_view = True
        st.caption("ℹ️ *Đang hiển thị mặc định danh sách Form 1 (Model phân loại chi phí). Chọn một Form cụ thể ở ô 'Form đang xem' trên đầu trang để đồng bộ bảng dữ liệu này.*")
    
    master_form_type = FORM_LABEL_TO_TYPE.get(target_form_label)
    master_config = FORM_TYPE_TO_CONFIG.get(master_form_type)
    
    if master_config:
        # Lấy tickets của form đó
        form_tickets = tickets_for_form(db_tickets, master_form_type)
        master_status_filter = st.selectbox(
            "🔍 Lọc trạng thái bản ghi",
            ["Tất cả"] + STATUS_LIST,
            key=f"master_filter_{master_form_type}",
        )
        master_tickets = form_tickets if master_status_filter == "Tất cả" else [
            t for t in form_tickets if t["status"] == master_status_filter
        ]
        master_rows = build_form_rows(master_tickets, master_config)
        if master_rows:
            st.dataframe(pd.DataFrame(master_rows), use_container_width=True)
        else:
            st.info(f"Chưa có dữ liệu hoặc không có bản ghi nào ở trạng thái '{master_status_filter}' cho form này.")
    else:
        st.info("Không tìm thấy cấu hình hiển thị dữ liệu cho Form này.")

    st.divider()
    
    col_list, col_detail = st.columns([0.4, 0.6])
    
    with col_list:
        st.subheader("📋 Danh sách Ticket")
        ticket_filter = st.selectbox("🔍 Lọc trạng thái", ["Tất cả"] + STATUS_LIST, key="ticket_filter")
        filtered_tickets = scoped_tickets if ticket_filter == "Tất cả" else [
            t for t in scoped_tickets if t["status"] == ticket_filter
        ]
        
        if not filtered_tickets:
            st.info("Không có ticket nào trong phạm vi đang chọn.")

        for t in filtered_tickets:
            with st.container(border=True):
                badge_html = status_badge(t['status'])
                st.markdown(f"**{t['id']}** &nbsp; {badge_html}", unsafe_allow_html=True)
                st.caption(f"Từ: {t['requester']} - {t['subject']}")
                if st.button("Xem chi tiết", key=f"btn_{t['id']}"):
                    st.session_state['active_ticket_id'] = t["id"]

    with col_detail:
        st.subheader("💬 Luồng xử lý (Chat-log)")
        active_ticket_id = st.session_state.get("active_ticket_id")
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
            
            # Nếu có dữ liệu form thì in ra JSON format đẹp mắt
            if current_t.get('form_data') and current_t.get('form_type'):
                display_form_type = normalize_form_type(current_t.get("form_type"))
                display_form_name = FORM_TYPE_TO_CONFIG.get(display_form_type, {}).get("label", display_form_type)
                st.info(f"📋 Dữ liệu đính kèm: **{display_form_name}**")
                try:
                    f_data = parse_form_data(current_t)
                    st.json(f_data)
                except Exception as e:
                    st.error(f"Lỗi hiển thị dữ liệu Form: {e}")
                    
            # Hiển thị hội thoại
            for m in current_t['msgs']:
                is_admin = m['user'].startswith("Admin")
                with st.chat_message("assistant" if is_admin else "user"):
                    label = "🔒 Nội bộ" if m['type'] == "internal" else "🌐 Công khai"
                    st.write(f"**{m['user']}** ({label})")
                    st.write(m['msg'])
                    # Hiển thị ngày và giờ cùng nhau
                    st.caption(f"{m.get('date', '')} • {m.get('time', '')}")

            # Nhập Log mới
            st.divider()
            log_msg = st.text_area("Nhập nội dung xử lý (Log)...", height=120, placeholder="Bạn có thể nhập nhiều dòng nội dung log xử lý tại đây...")
            log_type = st.radio("Loại log:", ["Công khai", "Nội bộ (Chỉ Admin)"], horizontal=True)
            
            c_btn1, c_btn2 = st.columns(2)
            if c_btn1.button("📩 Gửi Log", use_container_width=True):
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
                key="status_change"
            )
            col_s1, col_s2 = st.columns(2)
            if col_s1.button("🔄 Cập nhật trạng thái", use_container_width=True):
                if new_status != current_status:
                    db.update_ticket_status(current_t['id'], new_status)
                    if new_status == "Hoàn thành":
                        action_log = log_msg if log_msg else "Admin đã đánh dấu hoàn thành"
                        conn_tmp = db.get_connection()
                        if conn_tmp:
                            cur_tmp = conn_tmp.cursor()
                            cur_tmp.execute("INSERT INTO tasks (content, action, status) VALUES (%s, %s, 'Done')", (current_t['subject'], action_log))
                            conn_tmp.commit()
                            cur_tmp.close()
                            conn_tmp.close()
                        st.balloons()
                    st.rerun()
                else:
                    st.info("Trạng thái không thay đổi.")
            if col_s2.button("❌ Từ chối Ticket", use_container_width=True):
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
                
                # Chỉnh sửa form_data JSON
                edit_form_json = ""
                has_form = False
                if current_t.get('form_data') and current_t.get('form_type'):
                    has_form = True
                    current_form_data = parse_form_data(current_t)
                    edit_form_json = st.text_area(
                        "Dữ liệu đính kèm (JSON)", 
                        value=json.dumps(current_form_data, indent=4, ensure_ascii=False),
                        height=200,
                        key=f"edit_json_{current_t['id']}"
                    )
                
                c_edit1, c_edit2 = st.columns(2)
                if c_edit1.button("💾 Lưu Thay Đổi", type="primary", use_container_width=True, key=f"btn_save_{current_t['id']}"):
                    parsed_form_data = None
                    json_ok = True
                    if has_form:
                        try:
                            parsed_form_data = json.loads(edit_form_json)
                        except Exception as e:
                            st.error(f"Dữ liệu JSON không hợp lệ: {e}")
                            json_ok = False
                    
                    if json_ok:
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
                        if 'active_ticket_id' in st.session_state:
                            del st.session_state['active_ticket_id']
                        st.rerun()
                    else:
                        st.error("Lỗi khi xóa ticket khỏi CSDL")
        else:
            st.info("Chọn một ticket bên trái để xem chi tiết.")

elif page == "📈 Báo cáo tuần của Nam":
    st.markdown('<div class="main-header">📊 Tổng hợp Báo cáo</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Tự động hóa xuất báo cáo công việc</div>', unsafe_allow_html=True)
    
    if not db_tasks:
        st.warning("Chưa có task nào được hoàn thành để làm báo cáo.")
    else:
        st.write(f"Đã có **{len(db_tasks)}** task hoàn thành trong CSDL.")
        for t in db_tasks:
            st.write(f"- ✅ {t['content']} (Action: {t['action']})")
        
        st.button("🚀 Khởi tạo file Word (.docx)")
        
    st.divider()
    st.info("Tính năng này đang trong Giai đoạn 2. Dưới đây là khung nhập liệu mở rộng:")
    with st.form("weekly_report_form"):
        col1, col2 = st.columns([1, 3])
        with col1:
            week_number = st.number_input("Tuần số", min_value=1, max_value=53, value=1)
        with col2:
            reporter_name = st.text_input("Người báo cáo", value=Config.OWNER)
            
        tasks_completed = st.text_area("Công việc đã hoàn thành (Thêm tay)", placeholder="Nhập danh sách công việc...")
        issues = st.text_area("Vấn đề gặp phải", placeholder="Nhập các vấn đề nếu có...")
        
        st.divider()
        st.subheader("Upload file dữ liệu đính kèm (Excel)")
        uploaded_file = st.file_uploader("Chọn file Excel báo cáo", type=["xlsx", "xls"])
        
        submitted = st.form_submit_button("Lưu Nháp Báo Cáo", type="primary")

else:
    st.markdown(f'<div class="main-header">{page}</div>', unsafe_allow_html=True)
    st.info("🚧 Phân hệ này đang được thiết kế giao diện.")
