"""Sao lưu DB local (MariaDB) mỗi ngày — Task Scheduler "NamLeGree Backup DB" gọi file này.

Đọc thông tin đăng nhập từ .streamlit/secrets.toml (không ghi mật khẩu vào repo public).
File .sql.gz lưu ở BACKUP_DIR (ngoài repo), giữ KEEP_DAYS ngày gần nhất.
Nên đồng bộ BACKUP_DIR lên Google Drive/OneDrive để có bản sao ngoài máy.

    python deploy/backup_db.py
"""
import datetime
import gzip
import os
import subprocess
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = r"D:\NAMLE\backup_namlegree\daily"
MYSQLDUMP = r"E:\MariaDB 11.3\bin\mysqldump.exe"
KEEP_DAYS = 30


def main():
    with open(os.path.join(ROOT, ".streamlit", "secrets.toml"), "rb") as f:
        s = tomllib.load(f)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = os.path.join(BACKUP_DIR, f"{s['DB_NAME']}_{datetime.datetime.now():%Y%m%d_%H%M}.sql.gz")
    cmd = [MYSQLDUMP, "-h", s["DB_HOST"], "-P", str(s["DB_PORT"]), "-u", s["DB_USER"],
           "--single-transaction", "--routines", "--default-character-set=utf8mb4", s["DB_NAME"]]
    result = subprocess.run(cmd, capture_output=True, env=dict(os.environ, MYSQL_PWD=s["DB_PASS"]))
    if result.returncode != 0:
        print(f"[{datetime.datetime.now():%d/%m/%Y %H:%M}] LỖI backup: {result.stderr.decode(errors='replace')}")
        return 1
    # Khi import: thêm SET FOREIGN_KEY_CHECKS=0 ở đầu (CLAUDE.md, lỗi 3)
    with gzip.open(out, "wb") as f:
        f.write(b"SET FOREIGN_KEY_CHECKS=0;\n" + result.stdout + b"\nSET FOREIGN_KEY_CHECKS=1;\n")

    cutoff = datetime.datetime.now() - datetime.timedelta(days=KEEP_DAYS)
    for name in os.listdir(BACKUP_DIR):
        path = os.path.join(BACKUP_DIR, name)
        if name.endswith(".sql.gz") and datetime.datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
            os.remove(path)
    print(f"[{datetime.datetime.now():%d/%m/%Y %H:%M}] OK {out} ({os.path.getsize(out) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
