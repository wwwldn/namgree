import os

class Config:
    APP_NAME = "Ticket Management"
    BASE_DOMAIN = "leducnam.com"
    SUB_PATH = "/greevietnam"
    OWNER = "Lê Đức Nam"
    
    # Path cấu hình
    BASE_DIR = r"D:\NAMLE\GIT\Antigravity\namlegree"
    DATA_DIR = os.path.join(BASE_DIR, "data")
    ASSETS_DIR = os.path.join(BASE_DIR, "assets")
    
    # File mẫu báo cáo tuần
    REPORT_TEMPLATE = os.path.join(ASSETS_DIR, "bao_cao_tuan_mau.xlsx")