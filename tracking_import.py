"""Cập nhật bảng Theo dõi ticket (ticket_tracking) từ file Excel. Tự nhận 2 loại file:

1. Log cập nhật hệ thống Gree App ("[Gree-IT] GreeApp System Update Log", sheet "Logs"):
   lấy các dòng có cột "Trạng thái cập nhật" KHÁC trống / "Đã cập nhật" / "Không cập nhật"
   (việc còn đang theo dõi). Đổi trạng thái theo file.
2. Báo cáo của AEGONA ("Gree VN x AGN_Maintenance Ticket Report", mỗi tháng 1 sheet July/Aug/Sep/Oct...):
   lấy mọi ticket (STT = ID AEGONA) kèm giờ ETA/thực tế, tháng tính giờ (= sheet), ngày bắt đầu/kết thúc,
   trạng thái AEGONA... → dùng để tính MD theo tháng. Tiêu đề/nội dung/ưu tiên/người thực hiện chỉ điền khi
   đang trống; Trạng thái của mục đã có chỉ đổi theo file khi bật --status (mục mới thì lấy theo file).

Khớp với bảng theo ID AEGONA (dòng không có ID thì khớp theo Tiêu đề):
  - đã có → cập nhật (đổi trạng thái thì tự ghi log cho báo cáo tuần)
  - chưa có → thêm mới (nhóm Gree App)
Mục đang có trong bảng mà file không còn thì giữ nguyên.

Chạy từ máy (cần .streamlit/secrets.toml để ghi vào DB thật):
    python tracking_import.py <file.xlsx> --dry-run    (chỉ xem thay đổi, không ghi DB)
    python tracking_import.py <file.xlsx> [--status]
Trang "Báo cáo tuần" cũng có ô tải file lên dùng chung các hàm này.
"""
import datetime
import os
import re
import sys

# app.py so với thời gian sửa file để tự nạp lại module sau khi sửa (CLAUDE.md, lỗi 8)
LOADED_MTIME = os.path.getmtime(__file__)

SHEET_NAME = "logs"
SKIP_STATUSES = {"", "đã cập nhật", "không cập nhật"}
# Tên cột trong file (so khớp phần đầu, không phân biệt hoa thường) → trường trong ticket_tracking
COLUMN_MAP = {
    "trạng thái cập nhật": "status",
    "ưu tiên": "priority",
    "ngày cập nhật lên server": "prod_date",
    "id aegona": "ext_id",
    "tiêu đề": "title",
    "nội dung cập nhật": "content",
    "source code": "source_code",
    "người thực hiện": "assignee",
}

# --- Báo cáo AEGONA (Gree VN x AGN_Maintenance Ticket Report) ---
AGN_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
AGN_COLUMN_MAP = {
    "stt": "ext_id",
    "date report": "requested_at",
    "system": "system_name",
    "module": "module",
    "title": "title",
    "description": "content",
    "eta": "eta_hours",
    "actual": "actual_hours",
    "assignee": "assignee",
    "start date": "start_date",
    "end date": "end_date",
    "priority": "priority",
    "status": "agn_status",
    "gree approve": "agn_approve",
    "comment": "agn_comment",
}
AGN_PRIORITIES = {"high": "Cao", "urgent": "Cao", "normal": "Trung bình", "medium": "Trung bình", "low": "Thấp"}
AGN_DATE_FIELDS = ("requested_at", "start_date", "end_date")
AGN_HOUR_FIELDS = ("eta_hours", "actual_hours")
# Trường chỉ điền khi trên bảng đang trống (không ghi đè nội dung đã sửa tay / lấy từ log Gree App)
AGN_FILL_ONLY = {"title", "content", "priority", "assignee"}


def map_agn_status(value):
    """Trạng thái AEGONA (New / Closed / Complete (Ready to deploy)...) → trạng thái trên bảng theo dõi."""
    text = str(value or "").strip().lower()
    rules = [
        (("cancel", "reject", "hủy"), "Hủy"),
        (("closed", "close", "done"), "Đóng"),
        (("ready to deploy", "complete"), "Chờ deploy"),
        (("deployed", "production"), "Đã lên Production"),
        (("test", "uat"), "Đang testing"),
        (("progress", "doing", "processing"), "Đang thực hiện"),
        (("pending", "waiting", "estimate"), "Chờ đề xuất"),
    ]
    for keys, status in rules:
        if any(k in text for k in keys):
            return status
    return "Mới"


def _clean(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    return text or None


def _hours(value):
    """'8' / 8 / 0.25 → float; '-' / trống → None."""
    if value is None or isinstance(value, (datetime.date, datetime.datetime)):
        return None
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def normalize_ext_id(value):
    text = str(value or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if not text:
        return None
    return text if text.startswith("#") else f"#{text}"


def parse_tracking_xlsx(file):
    """file: đường dẫn hoặc file-like. Trả về (items, errors, source, month_totals) — source: 'logs' | 'agn';
    items: list dict theo các trường của ticket_tracking; month_totals (chỉ file AEGONA):
    {'2026-10': {'eta': 20.0, 'actual': 16.5}} lấy từ ô 'Tổng số giờ đã triển khai' của từng sheet."""
    from openpyxl import load_workbook

    wb = load_workbook(file, data_only=True, read_only=True)
    try:
        sheet = next((wb[n] for n in wb.sheetnames if n.strip().lower() == SHEET_NAME), None)
        if sheet is not None:
            items, errors = _parse_logs_sheet(sheet)
            return items, errors, "logs", {}
        items, errors, month_totals = _parse_agn_workbook(wb)
        return items, errors, "agn", month_totals
    finally:
        wb.close()


def _parse_logs_sheet(sheet):
    rows = sheet.iter_rows(values_only=True)
    header = [str(h or "").strip().lower() for h in next(rows, [])]
    col_idx = {}
    for i, h in enumerate(header):
        for prefix, field in COLUMN_MAP.items():
            if field not in col_idx and h.startswith(prefix):
                col_idx[field] = i
    missing = [p for p, f in COLUMN_MAP.items() if f not in col_idx and f in ("status", "title")]
    if missing:
        return [], [f"Thiếu cột: {', '.join(missing)}"]

    items = []
    for row in rows:
        status = _clean(row[col_idx["status"]]) if col_idx["status"] < len(row) else None
        if str(status or "").lower() in SKIP_STATUSES:
            continue
        item = {f: _clean(row[i]) if i < len(row) else None for f, i in col_idx.items()}
        if not item.get("title"):
            continue
        item["ext_id"] = normalize_ext_id(item.get("ext_id"))
        if item.get("prod_date") is not None and not isinstance(item["prod_date"], datetime.date):
            item["prod_date"] = None
        items.append(item)
    return items, []


def _parse_agn_workbook(wb):
    """Mỗi sheet tên tháng (July/Aug/Sep/Oct...) = giờ tính cho tháng đó; năm lấy từ dòng tiêu đề
    'GREE X AGN MONTHLY REPORT - JULY 2026'. Trả về (items, errors, month_totals) — month_totals lấy đúng ô
    'Tổng số giờ đã triển khai' (ETA, Actual) của sheet: công thức SUM trong file có thể chừa các dòng chuyển
    từ tháng trước (VD sheet Oct cộng H8:H27, bỏ #37/#40) nên không tự cộng lại từ các dòng."""
    items, months, month_totals = [], [], {}
    for ws in wb.worksheets:
        month = AGN_MONTHS.get(ws.title.strip().lower()[:3])
        if not month:
            continue
        rows = list(ws.iter_rows(values_only=True))
        header_idx, year, totals = None, None, None
        for i, row in enumerate(rows[:15]):
            cells = [str(c or "").strip().lower() for c in row]
            for c in cells:
                found = re.search(r"\b(20\d\d)\b", c)
                if found and "report" in c:
                    year = int(found.group(1))
            label_idx = next((j for j, c in enumerate(cells) if c.startswith("tổng số giờ")), None)
            if label_idx is not None:
                numbers = [h for h in (_hours(v) for v in row[label_idx + 1:]) if h is not None]
                if numbers:
                    totals = {"eta": numbers[0], "actual": numbers[1] if len(numbers) > 1 else numbers[0]}
            if "stt" in cells and any(c.startswith("actual") for c in cells):
                header_idx = i
                break
        if header_idx is None:
            continue
        year = year or datetime.date.today().year
        col_idx = {}
        for i, h in enumerate(str(c or "").strip().lower() for c in rows[header_idx]):
            for prefix, field in AGN_COLUMN_MAP.items():
                if field not in col_idx and h.startswith(prefix):
                    col_idx[field] = i
        work_month = f"{year}-{month:02d}"
        months.append(work_month)
        if totals:
            month_totals[work_month] = totals
        for row in rows[header_idx + 1:]:
            raw = {f: row[i] if i < len(row) else None for f, i in col_idx.items()}
            ext_id = normalize_ext_id(raw.get("ext_id"))
            title = _clean(raw.get("title"))
            if not ext_id or not title or not ext_id[1:].isdigit():
                continue
            item = {f: _clean(v) for f, v in raw.items() if f not in AGN_HOUR_FIELDS}
            item.update(ext_id=ext_id, title=str(title), work_month=work_month, category="gree_app")
            for f in AGN_DATE_FIELDS:
                if not isinstance(item.get(f), datetime.date):
                    item[f] = None
            for f in AGN_HOUR_FIELDS:
                item[f] = _hours(raw.get(f))
            item["priority"] = AGN_PRIORITIES.get(str(item.get("priority") or "").strip().lower())
            item["status"] = map_agn_status(item.get("agn_status"))
            items.append(item)
    if not months:
        return [], ["Không nhận ra file: cần sheet 'Logs' (log cập nhật Gree App) hoặc các sheet tháng "
                    "(July/Aug/...) có cột STT + Actual hours (báo cáo AEGONA)."], {}
    return items, [], month_totals


def _same(a, b):
    """So giá trị trong file với DB: trống = None, số so theo float (Decimal 8.00 == 8), chuỗi bỏ khoảng trắng."""
    a = None if a is None or (isinstance(a, str) and not a.strip()) else a
    b = None if b is None or (isinstance(b, str) and not b.strip()) else b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, datetime.datetime):
        a = a.date()
    if isinstance(b, datetime.datetime):
        b = b.date()
    if not isinstance(a, (str, datetime.date)) and not isinstance(b, (str, datetime.date)):
        return abs(float(a) - float(b)) < 1e-9
    return str(a).strip() == str(b).strip()


def match_tracking(items, existing, source="logs", update_status=None):
    """So file với bảng hiện có → (added, updated). updated chỉ chứa id + các trường thay đổi.
    source='agn': trường AGN_FILL_ONLY chỉ điền khi đang trống; Trạng thái chỉ đổi khi update_status=True."""
    if update_status is None:
        update_status = source != "agn"
    by_ext = {normalize_ext_id(e.get("ext_id")): e for e in existing if e.get("ext_id")}
    by_title = {str(e.get("title") or "").strip().casefold(): e for e in existing if not e.get("ext_id")}
    added, updated = [], []
    for item in items:
        if item.get("ext_id"):
            current = by_ext.get(item["ext_id"])
        else:
            current = by_title.get(item["title"].strip().casefold())
        if current is None:
            new = dict(item, category=item.get("category") or "gree_app")
            if source == "agn":
                # Ngày thật của mục (đóng ngày nào / báo ngày nào) → không dồn hết vào báo cáo tuần hiện tại
                new["changed_at"] = (item.get("end_date") if item["status"] == "Đóng" else None) or item.get("requested_at")
            added.append(new)
            continue
        changes = {}
        for f, v in item.items():
            if f == "category" or (f == "status" and not update_status):
                continue
            if source == "agn" and f in AGN_FILL_ONLY and not _same(current.get(f), None):
                continue
            if not _same(current.get(f), v):
                changes[f] = v
        if changes:
            if changes.get("status") == "Đóng" and item.get("end_date"):
                changes["changed_at"] = item["end_date"]
            updated.append(dict(changes, id=current["id"]))
    return added, updated


MONTH_TOTALS_KEY = "agn_month_totals"


def merge_month_totals(saved_json, month_totals):
    """Gộp tổng giờ theo tháng của file mới vào bản đã lưu (app_settings, JSON) — tháng nào có trong file thì
    lấy theo file, tháng cũ không còn trong file thì giữ."""
    import json
    try:
        saved = json.loads(saved_json) if saved_json else {}
    except ValueError:
        saved = {}
    saved.update(month_totals)
    return json.dumps(dict(sorted(saved.items())))


def describe_change(current, change):
    """1 dòng tóm tắt thay đổi để xem trước: trường chính ghi 'cũ → mới', còn lại chỉ ghi tên trường."""
    parts = []
    for f, v in change.items():
        if f in ("id", "changed_at"):
            continue
        if f in ("status", "actual_hours", "eta_hours", "work_month", "agn_status"):
            parts.append(f"{f}: {current.get(f)} → {v}")
        else:
            parts.append(f)
    return ", ".join(parts)


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    items, errors, source, month_totals = parse_tracking_xlsx(args[0])
    if errors:
        print("Lỗi:", *errors, sep="\n- ")
        return 1

    import db
    existing = db.get_ticket_tracking()
    added, updated = match_tracking(items, existing, source, update_status=True if "--status" in argv else None)
    by_id = {e["id"]: e for e in existing}
    kind = "báo cáo AEGONA" if source == "agn" else "log cập nhật Gree App"
    print(f"File {kind}: {len(items)} mục → thêm {len(added)}, cập nhật {len(updated)}")
    for item in added:
        print(f"  + {item.get('ext_id') or '(không ID)'} [{item['status']}] {item['title'].splitlines()[0][:70]}")
    for item in updated:
        cur = by_id[item["id"]]
        print(f"  ~ {cur.get('ext_id') or cur['title'][:40]}: {describe_change(cur, item)}")
    for month, t in month_totals.items():
        print(f"  Tổng giờ {month}: ETA {t['eta']:g} · Actual {t['actual']:g}")
    if "--dry-run" in argv:
        print("(--dry-run: chưa ghi DB)")
        return 0
    if (added or updated) and not db.save_ticket_tracking_changes(added, updated, []):
        print("Không kết nối được DB.")
        return 1
    if month_totals:
        db.save_settings({MONTH_TOTALS_KEY: merge_month_totals(db.get_settings().get(MONTH_TOTALS_KEY), month_totals)})
    print("Đã cập nhật DB.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
