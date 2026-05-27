import streamlit as st
import pandas as pd
import json
import os
from config import Config

# Thiết lập cấu hình trang
st.set_page_config(
    page_title=Config.APP_NAME,
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS để giao diện chuyên nghiệp hơn theo brand leducnam.com
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
</style>
""", unsafe_allow_html=True)

# -----------------
# THIẾT KẾ SIDEBAR
# -----------------
with st.sidebar:
    st.title(Config.APP_NAME)
    st.markdown(f"**Owner:** {Config.OWNER}")
    st.markdown(f"**Domain:** [{Config.BASE_DOMAIN}{Config.SUB_PATH}](https://{Config.BASE_DOMAIN}{Config.SUB_PATH})")
    st.divider()
    
    menu = ["🏠 Dashboard", "📚 Tài liệu & Form", "📊 Báo cáo tuần"]
    choice = st.radio("Điều hướng", menu)

# -----------------
# GIAO DIỆN CHÍNH
# -----------------
if choice == "🏠 Dashboard":
    st.markdown(f'<div class="main-header">Welcome to {Config.APP_NAME}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Tổng quan công việc và hệ thống quản lý tại Gree Vietnam</div>', unsafe_allow_html=True)
    
    st.info("Bảng điều khiển chính. Hãy chọn các tính năng ở thanh điều hướng bên trái để bắt đầu làm việc.")
    
    # Hiển thị các thông số tổng quan
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Tài liệu & Form", value="Sẵn sàng")
    with col2:
        st.metric(label="Báo cáo tuần", value="Giai đoạn 2")
    with col3:
        st.metric(label="Database", value="Giai đoạn 3")

elif choice == "📚 Tài liệu & Form":
    st.markdown('<div class="main-header">Tài liệu & Form</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Quản lý danh mục hướng dẫn nghiệp vụ và biểu mẫu</div>', unsafe_allow_html=True)
    
    links_file = os.path.join(Config.DATA_DIR, "links.json")
    
    try:
        # Load danh sách links từ file json
        with open(links_file, "r", encoding="utf-8") as f:
            links_data = json.load(f)
            
        for category, items in links_data.items():
            st.subheader(category)
            for item in items:
                st.markdown(f"- [{item['title']}]({item['url']}) - *{item['description']}*")
                
    except FileNotFoundError:
        st.warning(f"Không tìm thấy file dữ liệu tại `{links_file}`. Hãy đảm bảo file `data/links.json` tồn tại.")
    except Exception as e:
        st.error(f"Lỗi khi đọc file: {e}")

elif choice == "📊 Báo cáo tuần":
    st.markdown('<div class="main-header">Báo cáo tuần</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Tự động hóa xuất báo cáo công việc</div>', unsafe_allow_html=True)
    
    st.info("Tính năng này đang trong Giai đoạn 2. Giao diện dưới đây là bản dựng khung (mockup).")
    
    # Khung UI nhập liệu
    with st.form("weekly_report_form"):
        st.subheader("Nhập dữ liệu báo cáo")
        col1, col2 = st.columns([1, 3])
        with col1:
            week_number = st.number_input("Tuần số", min_value=1, max_value=53, value=1)
        with col2:
            reporter_name = st.text_input("Người báo cáo", value=Config.OWNER)
            
        tasks_completed = st.text_area("Công việc đã hoàn thành", placeholder="Nhập danh sách công việc...")
        issues = st.text_area("Vấn đề gặp phải", placeholder="Nhập các vấn đề nếu có...")
        
        st.divider()
        st.subheader("Upload file dữ liệu đính kèm (Excel)")
        uploaded_file = st.file_uploader("Chọn file Excel báo cáo", type=["xlsx", "xls"])
        
        submitted = st.form_submit_button("Xuất Báo Cáo", type="primary")
        if submitted:
            st.success("Tính năng xuất báo cáo sẽ được xử lý ở Giai đoạn 2 (đọc và ghi file bằng openpyxl/pandas).")
