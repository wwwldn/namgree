@echo off
REM Mo nhanh NamLeGree (shortcut "NamLeGree" ngoai Desktop). Chu khong dau: cmd doc sai UTF-8.
REM Streamlit chua chay thi bat task "NamLeGree Streamlit" (deploy\run_local.bat), roi mo trinh duyet.
REM Apache XAMPP dang chay (cong 443) thi mo https://gree.leducnam.com, khong thi mo 127.0.0.1:8501.
title NamLeGree

netstat -ano | findstr /c:":8501 " | findstr LISTENING >nul
if errorlevel 1 (
    echo Dang khoi dong NamLeGree...
    schtasks /run /tn "NamLeGree Streamlit" >nul 2>&1
    if errorlevel 1 start "NamLeGree Streamlit" /min cmd /c "%~dp0run_local.bat"
    for /l %%i in (1,1,30) do (
        "%SystemRoot%\System32\timeout.exe" /t 1 /nobreak >nul
        netstat -ano | findstr /c:":8501 " | findstr LISTENING >nul && goto :ready
    )
    echo Khong khoi dong duoc - xem logs\streamlit.log
    pause
    exit /b 1
)

:ready
netstat -ano | findstr /c:":443 " | findstr LISTENING >nul
if errorlevel 1 (
    start "" http://127.0.0.1:8501
) else (
    start "" https://gree.leducnam.com
)
