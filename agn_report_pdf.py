"""Xuất PDF báo cáo gói bảo trì AEGONA (nút "📄 Xuất báo cáo PDF" ở trang 📊 Báo cáo Ticket).

Số liệu tính sẵn ở app.agn_package_stats() — module này chỉ dàn trang, không đọc DB.
Font: Arial của Windows (có dấu tiếng Việt); máy không có Arial thì dùng Helvetica (mất dấu).
"""
import io
import os
import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                KeepTogether, Image, CondPageBreak)
from reportlab.graphics.shapes import Drawing, Rect, String, Line

# app.py so giá trị này với thời gian sửa file để tự nạp lại module khi file đổi
LOADED_MTIME = os.path.getmtime(__file__)

PAGE = landscape(A4)
MARGIN = 12 * mm
CONTENT_W = PAGE[0] - 2 * MARGIN

NAVY = colors.HexColor("#1E3A8A")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
ZEBRA = colors.HexColor("#F1F5F9")
HEAD_BG = colors.HexColor("#E0E7FF")
GREEN = colors.HexColor("#059669")
RED = colors.HexColor("#DC2626")
AMBER = colors.HexColor("#D97706")
TEAL = colors.HexColor("#0F766E")
BLUE = colors.HexColor("#2563EB")
PURPLE = colors.HexColor("#7C3AED")


def _register_fonts():
    font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    files = {"VN": "arial.ttf", "VN-B": "arialbd.ttf", "VN-I": "ariali.ttf", "VN-BI": "arialbi.ttf"}
    try:
        for name, file in files.items():
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, os.path.join(font_dir, file)))
        pdfmetrics.registerFontFamily("VN", normal="VN", bold="VN-B", italic="VN-I", boldItalic="VN-BI")
        return "VN", "VN-B"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


FONT, FONT_B = _register_fonts()


def _style(name, size=8.5, bold=False, color=INK, align=None, leading=None):
    s = ParagraphStyle(name, fontName=FONT_B if bold else FONT, fontSize=size, textColor=color,
                       leading=leading or size * 1.25)
    if align is not None:
        s.alignment = align
    return s


S_BODY = _style("body")
S_SMALL = _style("small", 7.5, color=MUTED)
S_CELL = _style("cell", 8)
S_CELL_B = _style("cellb", 8, bold=True)
S_HEAD = _style("head", 8, bold=True, color=NAVY)
S_HEAD_R = _style("headr", 8, bold=True, color=NAVY, align=TA_RIGHT)
S_H2 = _style("h2", 12.5, bold=True, color=NAVY, leading=16)
S_H3 = _style("h3", 10, bold=True, color=INK, leading=13)
S_TILE_LBL = _style("tl", 7.5, bold=True, color=colors.white)
S_TILE_VAL = _style("tv", 17, bold=True, color=colors.white, leading=21)
S_TILE_SUB = _style("ts", 7, color=colors.white, leading=9)
S_CHIP = _style("chip", 8, color=colors.white)


def month_label(work_month):
    try:
        year, month = str(work_month).split("-")
        return f"T{int(month)}/{year}"
    except ValueError:
        return str(work_month or "")


def _h(value):
    return "" if value is None else f"{float(value):.2f}"


def _d(value):
    if isinstance(value, datetime.datetime):
        value = value.date()
    return value.strftime("%d/%m/%Y") if isinstance(value, datetime.date) else (str(value) if value else "")


def _p(text, style=S_CELL):
    return Paragraph(escape(str(text or "")).replace("\n", "<br/>"), style)


def _first_line(text):
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


def _ext_num(item):
    ext = str(item.get("ext_id") or "").strip().lstrip("#")
    return int(ext) if ext.isdigit() else 10 ** 6


class _NumberedCanvas(rl_canvas.Canvas):
    """Vẽ "Trang x / y" sau khi biết tổng số trang."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.setFont(FONT, 7.5)
            self.setFillColor(MUTED)
            self.drawRightString(PAGE[0] - MARGIN, 7 * mm, f"Trang {self._pageNumber} / {total}")
            super().showPage()
        super().save()


def _page_decor(generated_at):
    def draw(canv, doc):
        canv.saveState()
        band_h = 13 * mm
        canv.setFillColor(NAVY)
        canv.rect(0, PAGE[1] - band_h, PAGE[0], band_h, stroke=0, fill=1)
        canv.setFillColor(AMBER)
        canv.rect(0, PAGE[1] - band_h - 1.2 * mm, PAGE[0], 1.2 * mm, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont(FONT_B, 13)
        canv.drawString(MARGIN, PAGE[1] - 8.5 * mm, "BÁO CÁO GÓI BẢO TRÌ AEGONA")
        canv.setFont(FONT, 8.5)
        canv.drawRightString(PAGE[0] - MARGIN, PAGE[1] - 8.3 * mm,
                             f"Gree Việt Nam × AEGONA  ·  Lập lúc {generated_at:%H:%M %d/%m/%Y}")
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.6)
        canv.line(MARGIN, 10.5 * mm, PAGE[0] - MARGIN, 10.5 * mm)
        canv.setFont(FONT, 7.5)
        canv.setFillColor(MUTED)
        canv.drawString(MARGIN, 7 * mm, "NamLeGree · gree.leducnam.com · Gree VN x AGN Maintenance Ticket Report")
        canv.restoreState()
    return draw


def _tiles(cards):
    """cards: (nhãn, giá trị, dòng phụ, màu) → 1 hàng thẻ màu."""
    n = len(cards)
    row = [[_p(lbl.upper(), S_TILE_LBL), _p(val, S_TILE_VAL), _p(sub, S_TILE_SUB)] for lbl, val, sub, _ in cards]
    t = Table([row], colWidths=[CONTENT_W / n] * n)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
             ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("LINEAFTER", (0, 0), (-2, -1), 5, colors.white)]
    style += [("BACKGROUND", (i, 0), (i, 0), colors.HexColor(c) if isinstance(c, str) else c)
              for i, (_, _, _, c) in enumerate(cards)]
    t.setStyle(TableStyle(style))
    return t


def _meters(bars, width):
    """bars: (nhãn, %, màu, chữ bên phải) → các thanh tiến độ."""
    row_h, bar_h = 17, 8
    d = Drawing(width, row_h * len(bars))
    for n, (label, pct, color, right) in enumerate(bars):
        y = row_h * (len(bars) - n - 1)
        d.add(String(0, y + bar_h + 2.5, label, fontName=FONT_B, fontSize=8, fillColor=INK))
        d.add(String(width, y + bar_h + 2.5, right, fontName=FONT_B, fontSize=8, fillColor=INK, textAnchor="end"))
        d.add(Rect(0, y, width, bar_h, rx=4, ry=4, fillColor=colors.HexColor("#E2E8F0"), strokeColor=None))
        fill_w = width * max(0.0, min(pct, 100.0)) / 100
        if fill_w > 0:
            d.add(Rect(0, y, fill_w, bar_h, rx=4, ry=4, fillColor=color, strokeColor=None))
    return d


def _month_chart(month_rows, quota, width, height):
    """Cột giờ thực hiện từng tháng (xanh: trong hạn mức, đỏ: vượt) + đường hạn mức."""
    d = Drawing(width, height)
    left, bottom, top_pad = 24, 26, 14
    plot_w, plot_h = width - left - 4, height - bottom - top_pad
    peak = max([r["actual"] for r in month_rows] + [quota]) * 1.15 or 1
    step = 10 if peak <= 60 else 20 if peak <= 120 else 50
    v = 0
    while v <= peak:
        y = bottom + plot_h * v / peak
        d.add(Line(left, y, left + plot_w, y, strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.5))
        d.add(String(left - 3, y - 2.5, f"{v:g}", fontName=FONT, fontSize=6.5, fillColor=MUTED, textAnchor="end"))
        v += step
    slot = plot_w / len(month_rows)
    bar_w = slot * 0.62
    for n, r in enumerate(month_rows):
        x = left + slot * n + (slot - bar_w) / 2
        h_dep = plot_h * max(r["deployed"], 0) / peak
        h_pend = plot_h * r["pending"] / peak
        if h_dep > 0:
            d.add(Rect(x, bottom, bar_w, h_dep, fillColor=GREEN, strokeColor=None))
        if h_pend > 0:
            d.add(Rect(x, bottom + h_dep, bar_w, h_pend, fillColor=AMBER, strokeColor=None))
        if r["actual"] > 0:
            d.add(String(x + bar_w / 2, bottom + h_dep + h_pend + 2, f"{r['actual']:g}", fontName=FONT_B, fontSize=6.8,
                         fillColor=RED if r["actual"] > quota else INK, textAnchor="middle"))
        short = r["label"][:-4] + r["label"][-2:]  # T7/2026 → T7/26 cho khỏi chồng chữ
        d.add(String(x + bar_w / 2, bottom - 9, short, fontName=FONT, fontSize=6.5, fillColor=MUTED, textAnchor="middle"))
    qy = bottom + plot_h * quota / peak
    d.add(Line(left, qy, left + plot_w, qy, strokeColor=RED, strokeWidth=1.3, strokeDashArray=[4, 3]))
    d.add(String(left + plot_w, qy + 3, f"Hạn mức {quota:g} giờ/tháng", fontName=FONT_B, fontSize=6.8,
                 fillColor=RED, textAnchor="end"))
    d.add(Rect(left, 3, 7, 7, fillColor=GREEN, strokeColor=None))
    d.add(String(left + 10, 4, "Đã triển khai", fontName=FONT, fontSize=6.8, fillColor=INK))
    d.add(Rect(left + 70, 3, 7, 7, fillColor=AMBER, strokeColor=None))
    d.add(String(left + 80, 4, "Chưa triển khai", fontName=FONT, fontSize=6.8, fillColor=INK))
    d.add(String(left + 150, 4, "Số trên cột = tổng giờ tháng (đỏ: vượt hạn mức)", fontName=FONT, fontSize=6.8, fillColor=MUTED))
    return d


def _grid_style(n_rows, header_rows=1, zebra=True):
    style = [
        ("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), HEAD_BG), ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), NAVY),
        ("FONTNAME", (0, 0), (-1, header_rows - 1), FONT_B),
        ("LINEBELOW", (0, 0), (-1, header_rows - 1), 1, NAVY),
        ("LINEBELOW", (0, header_rows), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    if zebra:
        style += [("BACKGROUND", (0, r), (-1, r), ZEBRA) for r in range(header_rows + 1, n_rows, 2)]
    return style


def _status_cell_styles(rows_status, col, status_colors, first_row=1):
    style = []
    for n, status in enumerate(rows_status):
        color = status_colors.get(status)
        if color:
            r = first_row + n
            style += [("BACKGROUND", (col, r), (col, r), colors.HexColor(color)),
                      ("TEXTCOLOR", (col, r), (col, r), colors.white), ("FONTNAME", (col, r), (col, r), FONT_B)]
    return style


def _month_table(stats, width):
    head = ["Tháng", "Số ticket", "ETA (giờ)", "Thực hiện (giờ)", "Đã triển khai (giờ)", "Chưa triển khai (giờ)",
            "Hạn mức (giờ)", "Chênh lệch (giờ)", "Lũy kế (giờ)", "% gói (lũy kế)"]
    data = [[_p(head[0], S_HEAD)] + [_p(h, S_HEAD_R) for h in head[1:]]]
    diff_colors = []
    for r in stats["month_rows"]:
        if r["has_data"]:
            data.append([r["label"], f"{r['count']:d}", _h(r["eta"]), _h(r["actual"]), _h(r["deployed"]),
                         _h(r["pending"]) if r["pending"] else "", _h(r["quota"]),
                         f"{r['diff']:+.2f}", _h(r["cum"]), f"{r['cum_pct']:.1f}%"])
            diff_colors.append(RED if r["diff"] > 0 else GREEN)
        else:
            data.append([r["label"], "", "", "", "", "", _h(r["quota"]), "", "", ""])
            diff_colors.append(None)
    data.append(["TỔNG", f"{stats['total_count']:d}", _h(stats["total_eta"]), _h(stats["used"]), _h(stats["deployed"]),
                 _h(stats["pending"]), _h(stats["quota"]),
                 f"{stats['total_diff']:+.2f}", _h(stats["used"]), f"{stats['used_pct']:.1f}%"])
    ratios = [0.1, 0.08, 0.09, 0.1, 0.11, 0.11, 0.1, 0.11, 0.1, 0.1]
    t = Table(data, colWidths=[width * x for x in ratios], repeatRows=1)
    style = _grid_style(len(data)) + [
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), NAVY), ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("FONTNAME", (0, -1), (-1, -1), FONT_B),
    ]
    for n, color in enumerate(diff_colors):
        if color is not None:
            style += [("TEXTCOLOR", (7, n + 1), (7, n + 1), color), ("FONTNAME", (7, n + 1), (7, n + 1), FONT_B),
                      ("TEXTCOLOR", (4, n + 1), (4, n + 1), GREEN), ("TEXTCOLOR", (5, n + 1), (5, n + 1), AMBER)]
        else:
            style += [("TEXTCOLOR", (0, n + 1), (-1, n + 1), MUTED)]
    t.setStyle(TableStyle(style))
    return t


def _open_table(open_items, status_colors):
    head = ["#", "ID", "Tiêu đề", "Trạng thái", "Ưu tiên", "Hệ thống / Module", "Phụ trách", "Ngày y/c", "Tháng giờ", "ETA", "Thực tế"]
    ratios = [0.03, 0.045, 0.30, 0.09, 0.065, 0.17, 0.08, 0.07, 0.06, 0.045, 0.045]
    data = [head]
    for n, i in enumerate(open_items, 1):
        sys_mod = " / ".join(x for x in [i.get("system_name"), i.get("module")] if x)
        data.append([str(n), i.get("ext_id") or "—", _p(_first_line(i.get("title"))), i.get("status") or "",
                     i.get("priority") or "", _p(sys_mod), _p(i.get("assignee") or ""), _d(i.get("requested_at")),
                     month_label(i["work_month"]) if i.get("work_month") else "", _h(i.get("eta_hours")),
                     _h(i.get("actual_hours"))])
    t = Table(data, colWidths=[CONTENT_W * x for x in ratios], repeatRows=1)
    style = _grid_style(len(data)) + [("ALIGN", (-2, 0), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (0, -1), "CENTER")]
    style += _status_cell_styles([i.get("status") for i in open_items], 3, status_colors)
    style += [("TEXTCOLOR", (4, n), (4, n), RED) for n, i in enumerate(open_items, 1) if i.get("priority") == "Cao"]
    t.setStyle(TableStyle(style))
    return t


def _month_detail_table(month_items, status_colors, hours_per_md):
    head = ["ID", "Tiêu đề", "Hệ thống", "Trạng thái", "TT AEGONA", "Phê duyệt", "Bắt đầu", "Kết thúc", "ETA", "Thực tế", "MD"]
    ratios = [0.045, 0.33, 0.065, 0.095, 0.11, 0.07, 0.065, 0.065, 0.05, 0.055, 0.05]
    data = [head]
    eta_sum = actual_sum = 0.0
    for i in month_items:
        eta, actual = i.get("eta_hours"), i.get("actual_hours")
        eta_sum += float(eta or 0)
        actual_sum += float(actual or 0)
        data.append([i.get("ext_id") or "—", _p(_first_line(i.get("title"))), i.get("system_name") or "",
                     i.get("status") or "", _p(i.get("agn_status") or ""), i.get("agn_approve") or "",
                     _d(i.get("start_date")), _d(i.get("end_date")), _h(eta), _h(actual),
                     f"{float(actual) / hours_per_md:.2f}" if actual is not None else ""])
    data.append(["", _p(f"Cộng {len(month_items)} ticket", S_CELL_B), "", "", "", "", "", "",
                 _h(eta_sum), _h(actual_sum), f"{actual_sum / hours_per_md:.2f}"])
    t = Table(data, colWidths=[CONTENT_W * x for x in ratios], repeatRows=1)
    style = _grid_style(len(data)) + [
        ("ALIGN", (-3, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, -1), (-1, -1), HEAD_BG), ("FONTNAME", (0, -1), (-1, -1), FONT_B),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, NAVY),
    ]
    style += _status_cell_styles([i.get("status") for i in month_items], 3, status_colors)
    t.setStyle(TableStyle(style))
    return t, actual_sum


def _status_chips(counts, status_colors):
    """Dãy ô nhỏ: số ticket theo từng trạng thái (kể cả Đóng / Hủy)."""
    names = list(counts)
    t = Table([[Paragraph(f"{escape(s)}&nbsp;&nbsp;<b>{counts[s]}</b>", S_CHIP) for s in names]],
              colWidths=[CONTENT_W / len(names)] * len(names))
    style = [("LINEAFTER", (0, 0), (-2, -1), 3, colors.white), ("TOPPADDING", (0, 0), (-1, -1), 3),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 6)]
    style += [("BACKGROUND", (n, 0), (n, 0), colors.HexColor(status_colors.get(s, "#64748B"))) for n, s in enumerate(names)]
    t.setStyle(TableStyle(style))
    return t


def _hours_table(hours_items, status_colors, hours_per_md):
    """Danh sách ticket kèm giờ thực tế + dòng TỔNG (dùng cho phần Đã / Chưa triển khai)."""
    head = ["#", "ID", "Tiêu đề", "Trạng thái", "TT AEGONA", "Hệ thống", "Tháng giờ", "Kết thúc", "Giờ thực tế", "MD"]
    ratios = [0.03, 0.045, 0.40, 0.095, 0.12, 0.065, 0.065, 0.075, 0.06, 0.045]
    data = [head]
    total = 0.0
    for n, i in enumerate(hours_items, 1):
        hours = float(i.get("actual_hours") or 0)
        total += hours
        data.append([str(n), i.get("ext_id") or "—", _p(_first_line(i.get("title"))), i.get("status") or "",
                     _p(i.get("agn_status") or ""), i.get("system_name") or "", month_label(i.get("work_month")),
                     _d(i.get("end_date")), _h(hours), f"{hours / hours_per_md:.2f}"])
    data.append(["", "", _p(f"TỔNG ({len(hours_items)} ticket)", S_CELL_B), "", "", "", "", "", _h(total),
                 f"{total / hours_per_md:.2f}"])
    t = Table(data, colWidths=[CONTENT_W * x for x in ratios], repeatRows=1)
    style = _grid_style(len(data)) + [
        ("ALIGN", (-2, 0), (-1, -1), "RIGHT"), ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("BACKGROUND", (0, -1), (-1, -1), HEAD_BG), ("FONTNAME", (0, -1), (-1, -1), FONT_B),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, NAVY),
    ]
    style += _status_cell_styles([i.get("status") for i in hours_items], 3, status_colors)
    t.setStyle(TableStyle(style))
    return t


def _split_bar(deployed, pending, width):
    """1 thanh ngang 2 màu: đã triển khai (xanh) | chưa triển khai (cam)."""
    total = deployed + pending
    d = Drawing(width, 26)
    dep_w = width * deployed / total if total else 0
    d.add(String(0, 16, f"Đã triển khai {deployed:.2f} giờ ({deployed / total * 100 if total else 0:.1f}%)",
                 fontName=FONT_B, fontSize=8, fillColor=GREEN))
    d.add(String(width, 16, f"Chưa triển khai {pending:.2f} giờ ({pending / total * 100 if total else 0:.1f}%)",
                 fontName=FONT_B, fontSize=8, fillColor=AMBER, textAnchor="end"))
    d.add(Rect(0, 0, width, 11, fillColor=colors.HexColor("#E2E8F0"), strokeColor=None))
    if dep_w > 0:
        d.add(Rect(0, 0, dep_w, 11, fillColor=GREEN, strokeColor=None))
    if width - dep_w > 0 and pending > 0:
        d.add(Rect(dep_w, 0, width - dep_w, 11, fillColor=AMBER, strokeColor=None))
    return d


def _logo(logo_path, height):
    if not logo_path or not os.path.exists(logo_path):
        return None
    try:
        w, h = ImageReader(logo_path).getSize()
        return Image(logo_path, width=height * w / h, height=height)
    except Exception:
        return None


def build_pdf(stats, items, logo_path, generated_at, status_colors):
    """Trả về bytes của file PDF báo cáo gói bảo trì AEGONA."""
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=PAGE, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=20 * mm,
                          bottomMargin=15 * mm, title="Báo cáo gói bảo trì AEGONA", author="NamLeGree")
    frame = Frame(MARGIN, 15 * mm, CONTENT_W, PAGE[1] - 35 * mm, id="body", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=_page_decor(generated_at))])

    quota, mq, hpm = stats["quota"], stats["monthly_quota"], stats["hours_per_md"]
    used, used_pct, time_pct, remaining = stats["used"], stats["used_pct"], stats["time_pct"], stats["remaining"]
    story = []

    # --- Thông tin hợp đồng ---
    info = (f"<b>Hợp đồng bảo trì:</b> ký <b>{stats['signed']:%d/%m/%Y}</b> → hết hạn <b>{stats['contract_end']:%d/%m/%Y}</b>"
            f"   ·   <b>Tổng gói:</b> {quota:g} giờ ({quota / hpm:g} MD)"
            f"   ·   <b>Chia đều:</b> {mq} giờ/tháng ({month_label(stats['contract_months'][0])} → "
            f"{month_label(stats['contract_months'][-1])})   ·   <b>Số liệu tới ngày:</b> {stats['today']:%d/%m/%Y}")
    logo = _logo(logo_path, 11 * mm)
    info_p = Paragraph(info, _style("info", 9, leading=13))
    if logo:
        head = Table([[logo, info_p]], colWidths=[logo.drawWidth + 6 * mm, CONTENT_W - logo.drawWidth - 6 * mm])
    else:
        head = Table([[info_p]], colWidths=[CONTENT_W])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                              ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                              ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story += [head, Spacer(1, 6)]

    # --- Thẻ số liệu giờ ---
    pct_color = GREEN if used_pct <= time_pct else (AMBER if used_pct <= 100 else RED)
    per_left = stats["per_month_left"]
    story.append(Paragraph("1. Sử dụng gói bảo trì", S_H2))
    story.append(Spacer(1, 3))
    story.append(_tiles([
        ("Tổng gói", f"{quota:g} giờ", f"{quota / hpm:g} MD · {mq} giờ/tháng", NAVY),
        ("Đã thực hiện", f"{used:.2f} giờ", f"= {used / hpm:.2f} MD", BLUE),
        ("% đã dùng gói", f"{used_pct:.1f}%", f"thời gian HĐ đã qua {time_pct:.0f}%", pct_color),
        ("Giờ còn lại", f"{remaining:.2f} giờ" if remaining >= 0 else f"Vượt {-remaining:.2f} giờ",
         f"≈ {per_left:.2f} giờ/tháng cho {stats['remaining_months']} tháng còn lại" if per_left is not None and remaining >= 0 else "",
         TEAL if remaining >= 0 else RED),
        ("Bình quân / tháng", f"{stats['avg_month']:.2f} giờ", f"hạn mức {mq} giờ/tháng",
         RED if stats["avg_month"] > mq else PURPLE),
    ]))
    story.append(Spacer(1, 6))
    story.append(_meters([
        ("Đã dùng gói bảo trì", used_pct, pct_color, f"{used:.2f} / {quota:g} giờ ({used_pct:.1f}%)"),
        ("Thời gian hợp đồng đã qua", time_pct, MUTED,
         f"{stats['elapsed_days']} / {stats['total_days']} ngày ({time_pct:.0f}%)"),
    ], CONTENT_W))
    if used_pct > time_pct:
        story.append(Spacer(1, 3))
        warn = Table([[Paragraph(
            f"<b>Lưu ý:</b> giờ sử dụng ({used_pct:.1f}%) đang nhanh hơn tiến độ thời gian hợp đồng ({time_pct:.0f}%) — "
            f"bình quân {stats['avg_month']:.2f} giờ/tháng so với hạn mức {mq} giờ/tháng.",
            _style("warn", 8.5, color=colors.HexColor("#92400E")))]], colWidths=[CONTENT_W])
        warn.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                                  ("LINEBEFORE", (0, 0), (0, -1), 3, AMBER), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
        story.append(warn)

    # --- Tách giờ đã thực hiện: đã triển khai / chưa triển khai ---
    deployed, pending = stats["deployed"], stats["pending"]
    pend_detail = " · ".join(f"{s} {h:.2f}" for s, h in stats["pending_by_status"].items())
    story.append(CondPageBreak(60 * mm))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"2. Phân tách {used:.2f} giờ đã thực hiện", S_H2))
    story.append(Spacer(1, 3))
    story.append(_tiles([
        ("Chưa triển khai", f"{pending:.2f} giờ",
         f"{len(stats['pending_items'])} ticket · {pend_detail or 'không có'}", AMBER),
        ("Đã triển khai trên hệ thống", f"{deployed:.2f} giờ",
         f"{len(stats['deployed_items'])} ticket · trạng thái {' / '.join(stats['deployed_statuses'])}", GREEN),
    ]))
    story.append(Spacer(1, 5))
    story.append(_split_bar(deployed, pending, CONTENT_W))
    # Chưa triển khai đưa lên trước: đây là phần cần theo dõi / xử lý tiếp
    for title, key, color in [(f"2.1. Chưa triển khai — {pending:.2f} giờ", "pending_items", AMBER),
                              (f"2.2. Đã triển khai trên hệ thống — {deployed:.2f} giờ", "deployed_items", GREEN)]:
        story.append(CondPageBreak(35 * mm))
        story.append(Spacer(1, 7))
        story.append(Paragraph(title, _style(key, 10.5, bold=True, color=color, leading=14)))
        story.append(Spacer(1, 2))
        if stats[key]:
            story.append(_hours_table(stats[key], status_colors, hpm))
        else:
            story.append(Paragraph("Không có ticket nào.", S_SMALL))
    gap = deployed - sum(float(i.get("actual_hours") or 0) for i in stats["deployed_items"])
    if abs(gap) >= 0.005:
        story.append(Paragraph(f"Tổng tháng theo file AEGONA lệch {gap:+.2f} giờ so với cộng các dòng — phần lệch tính vào "
                               "Đã triển khai.", S_SMALL))

    # --- Ticket đang mở theo trạng thái ---
    open_items = stats["open_items"]
    story.append(CondPageBreak(45 * mm))
    story.append(Spacer(1, 8))
    story.append(Paragraph("3. Ticket AEGONA đang mở", S_H2))
    story.append(Spacer(1, 3))
    story.append(_tiles([("Ticket đang mở", str(len(open_items)), f"{stats['closed_count']} ticket đã Đóng / Hủy", NAVY)]
                        + [(label, str(n), " · ".join(st) if len(st) > 1 else "", color)
                           for label, n, color, st in stats["open_groups"]]))
    story.append(Spacer(1, 4))
    story.append(_status_chips(stats["status_counts"], status_colors))

    # --- Giờ theo tháng: bảng + biểu đồ ---
    story.append(CondPageBreak(95 * mm))
    story.append(Spacer(1, 8))
    story.append(Paragraph("4. Tổng giờ theo tháng", S_H2))
    story.append(Paragraph("Chênh lệch = giờ thực hiện − hạn mức tháng (đỏ: vượt, xanh: trong hạn mức). "
                           "Dòng TỔNG so với hạn mức các tháng đã tới.", S_SMALL))
    story.append(Spacer(1, 3))
    story.append(_month_table(stats, CONTENT_W))
    story.append(Spacer(1, 6))
    story.append(KeepTogether([
        Paragraph("Biểu đồ giờ thực hiện theo tháng (đã triển khai / chưa triển khai)", S_H3), Spacer(1, 3),
        _month_chart(stats["month_rows"], mq, CONTENT_W, 50 * mm)]))
    if stats["outside"]:
        story.append(Paragraph("Giờ ngoài thời hạn hợp đồng (không tính vào %): " + ", ".join(
            f"{month_label(m)} {s['actual']:.2f} giờ" for m, s in stats["outside"].items()), S_SMALL))

    # --- Danh sách ticket đang mở ---
    if open_items:
        story.append(CondPageBreak(40 * mm))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"5. Danh sách ticket đang mở ({len(open_items)})", S_H2))
        story.append(Spacer(1, 3))
        story.append(_open_table(open_items, status_colors))

    # --- Chi tiết theo tháng tính giờ ---
    story.append(CondPageBreak(40 * mm))
    story.append(Spacer(1, 8))
    story.append(Paragraph("6. Chi tiết ticket theo tháng tính giờ", S_H2))
    file_totals = stats.get("file_totals") or {}
    by_month = {}
    for i in items:
        by_month.setdefault(i.get("work_month") or "", []).append(i)
    for m in sorted(k for k in by_month if k):
        month_items = sorted(by_month[m], key=_ext_num)
        table, actual_sum = _month_detail_table(month_items, status_colors, hpm)
        month_total = float((file_totals.get(m) or {}).get("actual") or actual_sum)
        over = month_total - mq
        title = (f"{month_label(m)}  —  {len(month_items)} ticket  ·  {month_total:.2f} giờ "
                 f"({'vượt' if over > 0 else 'còn'} {abs(over):.2f} giờ so với hạn mức {mq})")
        block = [Spacer(1, 5), Paragraph(title, _style(f"m{m}", 10, bold=True, color=RED if over > 0 else NAVY)), Spacer(1, 2), table]
        if abs(month_total - actual_sum) >= 0.005:
            block.append(Paragraph(
                f"Tổng giờ tháng lấy theo ô \"Tổng số giờ đã triển khai\" của file AEGONA: {month_total:.2f} giờ "
                f"(cộng các dòng: {actual_sum:.2f} giờ — file không tính dòng chuyển từ tháng trước).", S_SMALL))
        # Tháng ít ticket thì giữ tiêu đề + bảng trên cùng 1 trang; bảng dài thì cho tách trang (lặp dòng tiêu đề)
        # nhưng phải còn chỗ cho tiêu đề + vài dòng đầu, không để tiêu đề nằm trơ cuối trang
        story += [KeepTogether(block)] if len(month_items) <= 12 else [CondPageBreak(60 * mm)] + block
    if by_month.get(""):
        no_month = sorted(by_month[""], key=_ext_num)
        table, _ = _month_detail_table(no_month, status_colors, hpm)
        story += [Spacer(1, 5), Paragraph(f"Chưa có tháng tính giờ — {len(no_month)} ticket", S_H3), Spacer(1, 2), table]

    # --- Ghi chú ---
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<b>Ghi chú:</b> 1 MD = {hpm} giờ. Hạn mức tháng = tổng gói {quota:g} giờ chia đều {len(stats['contract_months'])} tháng. "
        "Giờ mỗi tháng lấy theo báo cáo tháng của AEGONA (\"Gree VN x AGN_Maintenance Ticket Report\"). "
        "Trạng thái là trạng thái theo dõi nội bộ; cột TT AEGONA / Phê duyệt là trạng thái trên file AEGONA.", S_SMALL))

    doc.build(story, canvasmaker=_NumberedCanvas)
    return buf.getvalue()
