"""Nạp ghi chú báo cáo tuần do AI tổng hợp vào hàng chờ duyệt (bảng work_note_drafts).

Ghi chú vào hàng chờ chưa xuất hiện trong báo cáo; vào trang "Báo cáo tuần" bấm Duyệt thì mới
chuyển sang work_notes và được đổ vào file mẫu (mục "Công việc khác" của dòng tương ứng).

Định dạng JSON (dùng chung cho script này và ô "Dán JSON từ AI" trên trang Báo cáo):
    {
      "notes": [
        {"date": "2026-10-13", "category": "erp", "content": "Họp ASoft chốt quy trình nhập kho"},
        {"date": "2026-10-14", "category": "it",  "content": "- Cài máy in tầng 2\\n- Cấp lại mật khẩu VPN"}
      ]
    }
  - Có thể đưa thẳng danh sách [...] thay vì {"notes": [...]}.
  - category: erp | warranty | gree_app | it (chấp nhận cả tên tiếng Việt: "Bảo hành", "Gree App", "IT cơ bản"...).
  - date: YYYY-MM-DD hoặc DD/MM/YYYY; bỏ trống thì lấy "week_start" ở gốc JSON, không có nữa thì lấy hôm nay.
  - content: nhiều dòng thì mỗi dòng thành 1 gạch đầu dòng trong báo cáo.

Chạy từ máy (cần .streamlit/secrets.toml để ghi vào DB thật):
    python ai_notes.py notes.json
    python ai_notes.py - < notes.json          (đọc từ stdin)
    python ai_notes.py notes.json --dry-run    (chỉ kiểm tra, không ghi DB)
"""
import datetime
import json
import sys
import unicodedata

# Mã nhóm trùng WORK_NOTE_CATEGORIES trong app.py
CATEGORY_ALIASES = {
    "erp": "erp",
    "warranty": "warranty", "bao hanh": "warranty", "he thong bao hanh": "warranty",
    "gree_app": "gree_app", "gree app": "gree_app", "greeapp": "gree_app", "app": "gree_app",
    "it": "it", "it co ban": "it", "cong viec it co ban": "it",
}

VN_TZ = datetime.timezone(datetime.timedelta(hours=7))


def _normalize(text):
    """Bỏ dấu tiếng Việt + chữ thường để so khớp tên nhóm ('Bảo hành' → 'bao hanh')."""
    text = unicodedata.normalize("NFD", str(text).replace("đ", "d").replace("Đ", "D"))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().replace("-", " ").split())


def _parse_date(value):
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"ngày không hợp lệ: {value!r}")


def parse_notes_json(raw_text):
    """Trả về (danh sách ghi chú hợp lệ, danh sách lỗi). Mỗi ghi chú: dict note_date/category/content."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return [], [f"JSON không hợp lệ: {e}"]

    default_date = datetime.datetime.now(VN_TZ).date()
    if isinstance(data, dict):
        if data.get("week_start"):
            try:
                default_date = _parse_date(data["week_start"])
            except ValueError as e:
                return [], [f"week_start: {e}"]
        items = data.get("notes")
    else:
        items = data
    if not isinstance(items, list):
        return [], ['Không tìm thấy danh sách ghi chú (cần dạng [...] hoặc {"notes": [...]})']

    notes, errors = [], []
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            errors.append(f"Mục {i}: phải là object {{date, category, content}}")
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "\n".join(str(x) for x in content)
        content = str(content or "").strip()
        category = CATEGORY_ALIASES.get(_normalize(item.get("category", "")))
        if not content:
            errors.append(f"Mục {i}: thiếu content")
            continue
        if not category:
            errors.append(f"Mục {i}: nhóm không hợp lệ {item.get('category')!r} (erp / warranty / gree_app / it)")
            continue
        try:
            note_date = _parse_date(item["date"]) if item.get("date") else default_date
        except ValueError as e:
            errors.append(f"Mục {i}: {e}")
            continue
        notes.append({"note_date": note_date, "category": category, "content": content})
    return notes, errors


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    dry_run = "--dry-run" in argv
    if not args:
        print(__doc__)
        return 1
    raw = sys.stdin.read() if args[0] == "-" else open(args[0], encoding="utf-8").read()
    notes, errors = parse_notes_json(raw)
    for err in errors:
        print(f"⚠️  {err}")
    if errors:
        print("Có lỗi → không ghi gì. Sửa JSON rồi chạy lại.")
        return 1
    if not notes:
        print("Không có ghi chú nào.")
        return 1
    for n in notes:
        print(f"  {n['note_date']}  [{n['category']}]  {n['content'][:80]!r}")
    if dry_run:
        print(f"(dry-run) {len(notes)} ghi chú hợp lệ, chưa ghi DB.")
        return 0

    import db  # import muộn: --dry-run không cần kết nối DB
    db.init_db()
    count = db.add_work_note_drafts(notes, source="AI")
    if count is None:
        print("❌ Không kết nối được DB.")
        return 1
    print(f"✅ Đã thêm {count} ghi chú vào hàng chờ duyệt (host {db.DB_CONFIG.get('host')}).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
