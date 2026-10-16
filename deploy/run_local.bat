@echo off
REM Chạy NamLeGree cho gree.leducnam.com (Apache XAMPP proxy https -> 127.0.0.1:8501).
REM Task Scheduler "NamLeGree Streamlit" gọi file này khi đăng nhập Windows.
REM Chỉ nghe 127.0.0.1: bên ngoài phải đi qua Apache/HTTPS, không vào thẳng cổng 8501.
cd /d "%~dp0.."
if not exist logs mkdir logs
"C:\Users\greev\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run app.py ^
    --server.address 127.0.0.1 --server.port 8501 --server.headless true ^
    --browser.gatherUsageStats false >> logs\streamlit.log 2>&1
