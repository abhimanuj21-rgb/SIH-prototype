"""
A4 "Land Profile" PDF — the shareable version of the Land Intelligence page.

Page 1 answers "how good is this land?" (verdict, access score, facility
comparison chart vs the city core). Page 2 answers "what else could it be
used for, and how sure are we?" (use-fit chart, site character, climate,
verified vs open checks, method). Rendered with reportlab using the built-in
Helvetica family so it has no font-file dependency.
"""
from __future__ import annotations

import io

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String, Wedge
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

# palette — mirrors the web app's tokens
INK = colors.HexColor("#1C1A17")
DIM = colors.HexColor("#6B655C")
FAINT = colors.HexColor("#948C80")
BORDER = colors.HexColor("#E3DED3")
PANEL = colors.HexColor("#F7F5F0")
ACCENT = colors.HexColor("#B4543A")
SITE = colors.HexColor("#2A78D6")       # "this site" series
TYPICAL = colors.HexColor("#B9B3A7")    # "city typical" comparison, recessive
SECOND = colors.HexColor("#EB6834")     # second series (S->N profile)
DARK = colors.HexColor("#171A21")
STATUS = {  # reserved status colours, always paired with a text label
    "Excellent": colors.HexColor("#2F7D4A"), "Strong fit": colors.HexColor("#2F7D4A"),
    "Good": colors.HexColor("#5E9C3F"), "Possible fit": colors.HexColor("#A6790A"),
    "Fair": colors.HexColor("#A6790A"), "Weak fit": colors.HexColor("#B0392F"),
    "Poor": colors.HexColor("#B0392F"), "Not scored": FAINT,
}

_W, _H = A4
_M = 16 * mm
CONTENT_W = _W - 2 * _M


def _clean(s) -> str:
    """Helvetica is WinAnsi; map the few symbols the data uses outside it."""
    s = "" if s is None else str(s)
    for a, b in (("→", "->"), ("≤", "<="), ("≥", ">="), ("−", "-"), ("’", "'"),
                 ("µ", "u"), ("³", "3"), ("²", "2"), ("₂", "2"), ("₃", "3"), ("–", "-")):
        s = s.replace(a, b)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _hex(c) -> str:
    return "#" + c.hexval()[2:]


def _km(d) -> str:
    if d is None:
        return "not mapped"
    return f"{d / 1000:.1f} km" if d >= 1000 else f"{round(d)} m"


# --- styles --------------------------------------------------------------
def _styles():
    base = dict(fontName="Helvetica", textColor=INK, leading=13, fontSize=9.2)
    return {
        "h1": ParagraphStyle("h1", **{**base, "fontName": "Helvetica-Bold",
                                       "fontSize": 17, "leading": 21}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": "Helvetica-Bold",
                                       "fontSize": 11.5, "leading": 15,
                                       "spaceBefore": 10, "spaceAfter": 5}),
        "body": ParagraphStyle("body", **base),
        "dim": ParagraphStyle("dim", **{**base, "textColor": DIM}),
        "small": ParagraphStyle("small", **{**base, "fontSize": 7.8, "leading": 10.5,
                                             "textColor": DIM}),
        "tiny": ParagraphStyle("tiny", **{**base, "fontSize": 7, "leading": 9,
                                           "textColor": FAINT}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8.4, "leading": 11}),
        "cellb": ParagraphStyle("cellb", **{**base, "fontSize": 8.4, "leading": 11,
                                             "fontName": "Helvetica-Bold"}),
        "tile_v": ParagraphStyle("tv", **{**base, "fontName": "Helvetica-Bold",
                                           "fontSize": 15, "leading": 18}),
        "tile_l": ParagraphStyle("tl", **{**base, "fontSize": 7, "leading": 9,
                                           "textColor": DIM, "alignment": TA_LEFT}),
    }


# --- drawings ------------------------------------------------------------
def _gauge(score, label: str, size: float = 34 * mm) -> Drawing:
    d = Drawing(size, size)
    cx = cy = size / 2
    r = size / 2 - 3
    d.add(Circle(cx, cy, r, fillColor=PANEL, strokeColor=BORDER, strokeWidth=1))
    if score is not None:
        col = STATUS.get(label, ACCENT)
        d.add(Wedge(cx, cy, r, 90 - 360 * score / 100, 90, fillColor=col,
                    strokeColor=None))
    d.add(Circle(cx, cy, r - 7, fillColor=colors.white, strokeColor=None))
    d.add(String(cx, cy + 1, "—" if score is None else str(score),
                 fontName="Helvetica-Bold", fontSize=22, fillColor=INK,
                 textAnchor="middle"))
    d.add(String(cx, cy - 12, "out of 100", fontName="Helvetica", fontSize=6.5,
                 fillColor=DIM, textAnchor="middle"))
    return d


def _facility_chart(rows: list[dict], city_label: str) -> Drawing:
    """Grouped horizontal bars: this site vs a typical city-core spot (km)."""
    label_w, right_pad, row_h, bar_h = 34 * mm, 18 * mm, 9.6 * mm, 3.3 * mm
    w = CONTENT_W
    top_pad, bottom_pad = 9 * mm, 7 * mm
    h = top_pad + bottom_pad + row_h * len(rows)
    d = Drawing(w, h)
    vals = [v for r in rows for v in (r["distance_m"], r["city_typical_m"]) if v is not None]
    vmax = max(vals + [1000]) * 1.08
    plot_w = w - label_w - right_pad
    x0 = label_w

    # legend
    d.add(Rect(x0, h - 6 * mm, 8, 8, fillColor=SITE, strokeColor=None))
    d.add(String(x0 + 12, h - 6 * mm + 1.5, "This site", fontName="Helvetica",
                 fontSize=7.5, fillColor=INK))
    d.add(Rect(x0 + 55, h - 6 * mm, 8, 8, fillColor=TYPICAL, strokeColor=None))
    d.add(String(x0 + 67, h - 6 * mm + 1.5,
                 f"Typical spot in {city_label} city core (median)",
                 fontName="Helvetica", fontSize=7.5, fillColor=INK))

    # grid + axis ticks (km)
    step = next(s for s in (250, 500, 1000, 2000, 2500, 5000, 10000, 20000)
                if vmax / s <= 6)
    t = 0
    while t <= vmax:
        x = x0 + plot_w * t / vmax
        d.add(Line(x, bottom_pad, x, h - top_pad, strokeColor=BORDER, strokeWidth=.5))
        d.add(String(x, bottom_pad - 9, _km(t) if t else "0", fontName="Helvetica",
                     fontSize=6.5, fillColor=FAINT, textAnchor="middle"))
        t += step

    for i, r in enumerate(rows):
        y = h - top_pad - (i + 1) * row_h + (row_h - 2 * bar_h - 2) / 2
        d.add(String(0, y + bar_h + 1, r["label"], fontName="Helvetica-Bold",
                     fontSize=8, fillColor=INK))
        for j, (v, col) in enumerate(((r["distance_m"], SITE),
                                      (r["city_typical_m"], TYPICAL))):
            yy = y + (bar_h + 2) * (1 - j)
            if v is None:
                d.add(String(x0 + 2, yy + 1, "not mapped", fontName="Helvetica-Oblique",
                             fontSize=6.5, fillColor=FAINT))
                continue
            bw = max(1.5, plot_w * v / vmax)
            d.add(Rect(x0, yy, bw, bar_h, fillColor=col, strokeColor=None))
            if j == 0:
                d.add(String(x0 + bw + 3, yy + 1, _km(v), fontName="Helvetica-Bold",
                             fontSize=7, fillColor=INK))
        d.add(String(0, y - 2, r["rating"], fontName="Helvetica", fontSize=7,
                     fillColor=STATUS.get(r["rating"], DIM)))
    return d


def _use_chart(uses: list[dict]) -> Drawing:
    label_w, right_pad, row_h, bar_h = 58 * mm, 26 * mm, 8 * mm, 4.4 * mm
    w, pad = CONTENT_W, 7 * mm
    h = pad * 2 + row_h * len(uses)
    d = Drawing(w, h)
    plot_w = w - label_w - right_pad
    for t in (0, 25, 50, 75, 100):
        x = label_w + plot_w * t / 100
        d.add(Line(x, pad, x, h - pad + 2, strokeColor=BORDER, strokeWidth=.5))
        d.add(String(x, pad - 8, str(t), fontName="Helvetica", fontSize=6.5,
                     fillColor=FAINT, textAnchor="middle"))
    for i, u in enumerate(uses):
        y = h - pad - (i + 1) * row_h + (row_h - bar_h) / 2
        d.add(String(0, y + 1.2, u["label"], fontName="Helvetica-Bold", fontSize=8,
                     fillColor=INK))
        d.add(Rect(label_w, y, plot_w, bar_h, fillColor=PANEL, strokeColor=None))
        if u["score"] is not None:
            d.add(Rect(label_w, y, plot_w * u["score"] / 100, bar_h,
                       fillColor=STATUS.get(u["fit"], SITE), strokeColor=None))
        d.add(String(label_w + plot_w + 4, y + 1.2,
                     f"{'—' if u['score'] is None else u['score']}  {u['fit']}",
                     fontName="Helvetica", fontSize=7.5, fillColor=INK))
    return d


def _coverage_bar(pct: int, w: float = 60 * mm) -> Drawing:
    d = Drawing(w, 9)
    d.add(Rect(0, 1, w, 6, fillColor=PANEL, strokeColor=BORDER, strokeWidth=.4))
    d.add(Rect(0, 1, w * pct / 100, 6, fillColor=SITE, strokeColor=None))
    return d


def _profile_chart(we: list[dict], sn: list[dict], w: float = CONTENT_W,
                   h: float = 44 * mm) -> Drawing:
    """Ground elevation along W->E and S->N lines through the site (+-1 km)."""
    d = Drawing(w, h)
    L, R, T, B = 16 * mm, 4 * mm, 8 * mm, 7 * mm
    zs = [p["elevation_m"] for p in we + sn]
    pad = max(2, (max(zs) - min(zs)) * .15)
    zmin, zmax = min(zs) - pad, max(zs) + pad
    x = lambda o: L + (o + 1000) / 2000 * (w - L - R)  # noqa: E731
    y = lambda z: B + (z - zmin) / (zmax - zmin) * (h - T - B)  # noqa: E731
    for z in (zmin, (zmin + zmax) / 2, zmax):
        d.add(Line(L, y(z), w - R, y(z), strokeColor=BORDER, strokeWidth=.5))
        d.add(String(L - 3, y(z) - 2, f"{z:.0f} m", fontName="Helvetica", fontSize=6.5,
                     fillColor=FAINT, textAnchor="end"))
    for o in (-1000, -500, 0, 500, 1000):
        d.add(String(x(o), 1, "site" if o == 0 else f"{'+' if o > 0 else '-'}{abs(o) / 1000:g} km",
                     fontName="Helvetica", fontSize=6.5, fillColor=FAINT, textAnchor="middle"))
    d.add(Line(x(0), B, x(0), h - T, strokeColor=INK, strokeWidth=.7))
    for series, col in ((we, SITE), (sn, SECOND)):
        pts = []
        for p in series:
            pts += [x(p["offset_m"]), y(p["elevation_m"])]
        d.add(PolyLine(pts, strokeColor=col, strokeWidth=1.6))
    d.add(Rect(L, h - 5, 8, 3, fillColor=SITE, strokeColor=None))
    d.add(String(L + 11, h - 6, "West -> East", fontName="Helvetica", fontSize=7, fillColor=INK))
    d.add(Rect(L + 65, h - 5, 8, 3, fillColor=SECOND, strokeColor=None))
    d.add(String(L + 76, h - 6, "South -> North", fontName="Helvetica", fontSize=7, fillColor=INK))
    return d


def _columns(data: list[dict], key: str, label_key: str, title: str, w: float,
             h: float = 40 * mm, color=SITE, ref: tuple | None = None) -> Drawing:
    """Small column chart with an optional labelled reference line."""
    d = Drawing(w, h)
    L, R, T, B = 10 * mm, 2 * mm, 8 * mm, 7 * mm
    vals = [r[key] for r in data if r[key] is not None]
    vmax = max(vals + ([ref[0]] if ref else []) + [1]) * 1.12
    bw = (w - L - R) / max(1, len(data))
    y = lambda v: B + v / vmax * (h - T - B)  # noqa: E731
    d.add(String(0, h - 6, title, fontName="Helvetica-Bold", fontSize=7.5, fillColor=INK))
    for t in (0, vmax / 2, vmax / 1.12):
        d.add(Line(L, y(t), w - R, y(t), strokeColor=BORDER, strokeWidth=.4))
        d.add(String(L - 2, y(t) - 2, f"{t:.0f}", fontName="Helvetica", fontSize=6,
                     fillColor=FAINT, textAnchor="end"))
    for i, r in enumerate(data):
        v = r[key]
        if v is not None:
            d.add(Rect(L + i * bw + bw * .15, B, bw * .7, y(v) - B, fillColor=color, strokeColor=None))
        d.add(String(L + i * bw + bw / 2, 1, str(r[label_key])[:4], fontName="Helvetica",
                     fontSize=5.8, fillColor=FAINT, textAnchor="middle"))
    if ref:
        d.add(Line(L, y(ref[0]), w - R, y(ref[0]), strokeColor=INK, strokeWidth=.8))
        d.add(String(w - R, y(ref[0]) + 2, ref[1], fontName="Helvetica-Bold", fontSize=6,
                     fillColor=INK, textAnchor="end"))
    return d


def _share_chart(series: list[dict], w: float = CONTENT_W, h: float = 40 * mm) -> Drawing:
    """Built / crops / trees / water share (%) around the point, by year."""
    d = Drawing(w, h)
    L, R, T, B = 10 * mm, 30 * mm, 4 * mm, 7 * mm
    n = max(1, len(series) - 1)
    x = lambda i: L + i / n * (w - L - R)  # noqa: E731
    y = lambda v: B + v / 100 * (h - T - B)  # noqa: E731
    for t in (0, 50, 100):
        d.add(Line(L, y(t), w - R, y(t), strokeColor=BORDER, strokeWidth=.4))
        d.add(String(L - 2, y(t) - 2, f"{t}%", fontName="Helvetica", fontSize=6,
                     fillColor=FAINT, textAnchor="end"))
    for i, row in enumerate(series):
        d.add(String(x(i), 1, str(row["year"]), fontName="Helvetica", fontSize=6,
                     fillColor=FAINT, textAnchor="middle"))
    used = []
    for key, label, col in (("built_pct", "Built-up", "#B4543A"), ("crops_pct", "Cropland", "#C98500"),
                            ("trees_pct", "Trees", "#2F7D4A"), ("water_pct", "Water", "#2A78D6")):
        pts = []
        for i, row in enumerate(series):
            pts += [x(i), y(row[key])]
        d.add(PolyLine(pts, strokeColor=colors.HexColor(col), strokeWidth=1.6))
        ly = y(series[-1][key]) - 2
        while any(abs(ly - u) < 8 for u in used):  # keep end labels from overlapping
            ly += 8
        used.append(ly)
        d.add(String(w - R + 4, ly, f"{label} {series[-1][key]}%", fontName="Helvetica-Bold",
                     fontSize=6.8, fillColor=colors.HexColor(col)))
    return d


def _soil_bar(sand: float, silt: float, clay: float, w: float = CONTENT_W) -> Drawing:
    d = Drawing(w, 16)
    total = (sand or 0) + (silt or 0) + (clay or 0) or 100
    x = 0
    for name, v, col in (("Sand", sand, "#D9B26F"), ("Silt", silt, "#A89A85"), ("Clay", clay, "#8A5A3C")):
        bw = w * (v or 0) / total
        d.add(Rect(x, 2, max(0, bw - 1.5), 12, fillColor=colors.HexColor(col), strokeColor=None))
        if bw > 40:
            d.add(String(x + bw / 2, 5.5, f"{name} {v:.0f}%", fontName="Helvetica-Bold",
                         fontSize=7, fillColor=colors.white, textAnchor="middle"))
        x += bw
    return d


def _aq_bullet(pm: float, refs: dict, w: float = CONTENT_W) -> Drawing:
    d = Drawing(w, 22)
    top = max(60, pm * 1.3)
    d.add(Rect(0, 3, w, 8, fillColor=PANEL, strokeColor=None))
    d.add(Rect(0, 3, w * min(1, pm / top), 8, fillColor=colors.HexColor("#7A6F62"), strokeColor=None))
    for v, lbl in ((refs["who_annual"], f"WHO {refs['who_annual']}"),
                   (refs["naaqs_annual"], f"India limit {refs['naaqs_annual']}")):
        xx = w * v / top
        d.add(Line(xx, 0, xx, 14, strokeColor=INK, strokeWidth=1))
        d.add(String(xx, 15, lbl, fontName="Helvetica", fontSize=6.5, fillColor=DIM,
                     textAnchor="middle"))
    return d


# --- page chrome -----------------------------------------------------------
def _on_page(profile: dict):
    loc = profile["location"]

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK)
        canvas.rect(0, _H - 22 * mm, _W, 22 * mm, fill=1, stroke=0)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, _H - 22 * mm, 4 * mm, 22 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(_M, _H - 11 * mm, "Land Profile Report")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#C6C9D2"))
        canvas.drawString(_M, _H - 16.5 * mm,
                          "National Digital Platform  ·  evidence-first land intelligence")
        canvas.setFont("Helvetica-Bold", 9)
        canvas.setFillColor(colors.white)
        canvas.drawRightString(_W - _M, _H - 11 * mm,
                               f"{loc['city_label']}, {loc['state']}")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#C6C9D2"))
        canvas.drawRightString(_W - _M, _H - 16.5 * mm,
                               f"{loc['latitude']}, {loc['longitude']}  ·  {profile['generated']}")
        # footer
        canvas.setStrokeColor(BORDER)
        canvas.line(_M, 13 * mm, _W - _M, 13 * mm)
        canvas.setFont("Helvetica", 6.8)
        canvas.setFillColor(FAINT)
        canvas.drawString(_M, 9 * mm, _clean(profile["disclaimer"]).replace("&amp;", "&"))
        canvas.drawRightString(_W - _M, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def _tile(value, label, st) -> list:
    style = st["tile_v"]
    if len(str(value)) > 12:  # long text (a use name) — step down so it fits
        style = ParagraphStyle("tvs", parent=style, fontSize=11, leading=13.5)
    return [Paragraph(_clean(value), style), Paragraph(_clean(label).upper(), st["tile_l"])]


def _box(flowables, bg=PANEL, pad=8) -> Table:
    t = Table([[flowables]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), .6, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), pad), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
        ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
    ]))
    return t


def _grid_table(data, widths, header=True) -> Table:
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), .4, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), PANEL),
                  ("LINEBELOW", (0, 0), (-1, 0), .8, DIM)]
    t.setStyle(TableStyle(style))
    return t


# --- the document ----------------------------------------------------------
def render(profile: dict) -> bytes:
    st = _styles()
    v = profile["verdict"]
    loc = profile["location"]
    fac = profile["facilities"]
    story: list = []

    # 1. verdict
    verdict_right = [
        Paragraph(_clean(v["title"]), st["h1"]),
        Spacer(1, 3),
        Paragraph(_clean(v["summary"]), st["body"]),
        Spacer(1, 5),
        Paragraph(f"<b>Access rating:</b> <font color='{_hex(STATUS.get(v['access_rating'], DIM))}'>"
                  f"{_clean(v['access_rating'])}</font> &nbsp;·&nbsp; "
                  f"<b>Confidence:</b> {_clean(v['confidence'])}", st["dim"]),
        Paragraph(_clean(v["confidence_note"]), st["small"]),
    ]
    top = Table([[_gauge(v["access_score"], v["access_rating"]), verdict_right]],
                colWidths=[40 * mm, CONTENT_W - 40 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [top, Spacer(1, 6)]

    cov = profile["evidence_coverage"]
    tiles = Table([[
        _tile(f"{v['access_score'] if v['access_score'] is not None else '—'}/100",
              "Access score (this site)", st),
        _tile(f"{v['city_typical_access_score'] if v['city_typical_access_score'] is not None else '—'}/100",
              f"Typical {loc['city_label']} core spot", st),
        _tile(v["best_use"] or "—", "Best indicative fit", st),
        _tile(f"{cov['pct']}%", f"Evidence coverage ({len(cov['known'])} of "
                                f"{len(cov['known']) + len(cov['unknown'])})", st),
    ]], colWidths=[CONTENT_W / 4] * 4)
    tiles.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), .6, BORDER), ("INNERGRID", (0, 0), (-1, -1), .6, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [tiles]
    if v.get("facts"):
        cells = [Paragraph(f"<font color='#948C80' size='6.8'>{_clean(f['label']).upper()}</font>"
                           f"<br/><b>{_clean(f['value'])}</b>", st["cell"]) for f in v["facts"]]
        while len(cells) % 3:
            cells.append("")
        ft = Table([cells[i:i + 3] for i in range(0, len(cells), 3)], colWidths=[CONTENT_W / 3] * 3)
        ft.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                ("LINEBELOW", (0, -1), (-1, -1), .6, BORDER)]))
        story += [Spacer(1, 4), ft]

    # 2. facility comparison
    story += [Paragraph("How close are the essentials? — this site vs the rest of the city",
                        st["h2"]),
              Paragraph(f"Distance to the nearest mapped facility of each kind. Grey bars "
                        f"show the typical (median) distance across "
                        f"{profile['benchmark'].get('sample_points', 0)} sample points in the "
                        f"{_clean(loc['city_label'])} city core — shorter is better.",
                        st["small"]),
              Spacer(1, 4),
              _facility_chart(fac, loc["city_label"]),
              Spacer(1, 6)]

    rows = [[Paragraph(h, st["cellb"]) for h in
             ("Facility", "Nearest mapped", "Distance", "Score", "Rating",
              "vs city core")]]
    for r in fac:
        pct = r["closer_than_pct_of_city"]
        cmp = ("—" if pct is None else
               "farther than all spots" if pct == 0 else
               f"closer than {pct}% of spots")
        rows.append([
            Paragraph(_clean(r["label"]), st["cellb"]),
            Paragraph(_clean(r["nearest_name"] or "unnamed in OSM"), st["cell"]),
            Paragraph(_km(r["distance_m"]), st["cell"]),
            Paragraph("—" if r["score"] is None else str(r["score"]), st["cell"]),
            Paragraph(f"<font color='{_hex(STATUS.get(r['rating'], DIM))}'>"
                      f"<b>{r['rating']}</b></font>", st["cell"]),
            Paragraph(cmp, st["cell"]),
        ])
    story += [_grid_table(rows, [30 * mm, 52 * mm, 20 * mm, 14 * mm, 20 * mm,
                                 CONTENT_W - 136 * mm]),
              Spacer(1, 4),
              Paragraph(_clean(profile["method"]["access"]), st["tiny"])]

    # 4. site character + climate
    site = profile.get("site") or {}
    char_rows = []
    if site:
        dev = site.get("development") or {}
        land = site.get("land_use") or {}
        water = site.get("water") or {}
        char_rows += [
            ["Development", dev.get("level"), dev.get("summary")],
            ["Land use", land.get("effective_category"), land.get("summary")],
            ["Water", "Surface water", water.get("summary") or water.get("reason")],
        ]
    if char_rows:
        rows = [[Paragraph(f"<b>{_clean(a)}</b>", st["cell"]),
                 Paragraph(f"<b>{_clean(b)}</b>", st["cell"]),
                 Paragraph(_clean(c), st["cell"])] for a, b, c in char_rows]
        story += [KeepTogether([Paragraph("Site character", st["h2"]),
                                _grid_table(rows, [26 * mm, 46 * mm, CONTENT_W - 72 * mm],
                                            header=False)])]


    story += _land_details({**(profile.get("details") or {}),
                            "_live": profile.get("live_weather"),
                            "_air": profile.get("live_air")}, st)

    # 3. use fit
    uses = profile["use_fit"]
    use_block = [Paragraph("What could this land be good for?", st["h2"]),
              Paragraph("Indicative fit for common land uses, scored only from the verified "
                        "access and site-character factors above. It is a screening aid, "
                        "not a zoning or legal determination.", st["small"]),
              Spacer(1, 4), _use_chart(uses), Spacer(1, 6)]
    story += [KeepTogether(use_block)]
    rows = [[Paragraph(h, st["cellb"]) for h in ("Use", "Why this score", "Check before deciding")]]
    for u in uses:
        why = "; ".join(f"{f['factor'].lower()} {'—' if f['points'] is None else f['points']}"
                        for f in u["factors"])
        needs = ", ".join(_label(n) for n in u["verify_before_deciding"]) or "—"
        rows.append([Paragraph(f"<b>{_clean(u['label'])}</b><br/>"
                               f"<font color='{_hex(STATUS.get(u['fit'], DIM))}'>"
                               f"{u['fit']}</font>", st["cell"]),
                     Paragraph(_clean(u["why"]) + f"<br/><font color='#948C80'>{_clean(why)}</font>",
                               st["cell"]),
                     Paragraph(_clean(needs), st["cell"])])
    story += [_grid_table(rows, [42 * mm, CONTENT_W - 92 * mm, 50 * mm])]

    # 5. what we know / don't
    known = "<br/>".join(f"<font color='#2F7D4A'>+</font> {_clean(k['label'])} "
                         f"<font color='#948C80' size='7'>({_clean(k.get('kind', '')).lower()})</font>"
                         for k in cov["known"])
    unknown = "<br/>".join(f"<font color='#B0392F'>-</font> {_clean(u['label'])} "
                           f"<font color='#948C80' size='7'>({_clean(u['status'].replace('_', ' ').lower())})</font>"
                           for u in cov["unknown"])
    kt = Table([[Paragraph("<b>Verified from real data</b>", st["cell"]),
                 Paragraph("<b>Still open — needed before any decision</b>", st["cell"])],
                [Paragraph(known or "—", st["cell"]), Paragraph(unknown or "—", st["cell"])]],
               colWidths=[CONTENT_W * .4, CONTENT_W * .6])
    kt.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("BACKGROUND", (0, 0), (-1, 0), PANEL),
                            ("BOX", (0, 0), (-1, -1), .6, BORDER),
                            ("INNERGRID", (0, 0), (-1, -1), .4, BORDER),
                            ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [KeepTogether([
        Paragraph(f"How sure are we? — {cov['pct']}% evidence coverage", st["h2"]),
        _coverage_bar(cov["pct"]), Spacer(1, 5), kt]
        + [Paragraph(f"<b>Cross-check — {_clean(c['check'])}:</b> "
                     f"{'agree' if c['result'] == 'agree' else 'gap filled by satellite' if c['result'] == 'filled' else 'DISAGREE'}. "
                     + _clean(c["note"]), st["small"]) for c in cov.get("cross_checks", [])])]

    # 6. method
    story += [Paragraph("Method &amp; sources", st["h2"]),
              Paragraph(" ".join((
                  _clean(profile["method"]["benchmark"]),
                  _clean(profile["method"]["use_fit"]),
                  _clean(profile["method"].get("details", "")),
                  "Sources: OpenStreetMap via Overpass (cached city layers), Open-Meteo "
                  "Archive (ERA5 reanalysis). Full provenance for every dataset is in the "
                  "platform's provenance manifest export.")), st["small"])]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=_M, rightMargin=_M,
                            topMargin=28 * mm, bottomMargin=18 * mm,
                            title=f"Land Profile — {loc['city_label']} "
                                  f"{loc['latitude']}, {loc['longitude']}",
                            author="National Digital Platform")
    page = _on_page(profile)
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buf.getvalue()


def _air_now_rows(m: dict, st: dict) -> list:
    """Live Indian AQI + per-pollutant table at the moment the PDF was made."""
    idx = m.get("india_aqi") or {}
    if not (m.get("available") and idx.get("available")):
        return []
    col = colors.HexColor(idx["category"]["colour"])
    head = Paragraph(
        f"<b>Right now ({_clean(m['time_local'][11:])} local):</b> Indian AQI "
        f"<font color='{_hex(col)}'><b>{idx['aqi']} — {_clean(idx['category']['name'])}</b></font>, "
        f"main pollutant {_clean(idx['prominent_pollutant'])}. {_clean(idx['category']['health'])}"
        + (f" PM2.5 {_clean(m['trend_next_24h'])} over the next 24 h." if m.get("trend_next_24h") else ""),
        st["small"])
    rows = [[Paragraph(h, st["cellb"]) for h in ("Pollutant", "Now", "Average", "Sub-index")]]
    for p in m["pollutants"]:
        rows.append([Paragraph(_clean(p["name"]), st["cell"]),
                     Paragraph(_clean(f"{p['now']} {p['unit']}"), st["cell"]),
                     Paragraph(_clean(f"{p['average']} ({p['average_window']})"), st["cell"]),
                     Paragraph(_clean(f"{p['sub_index']} — {p['category']}"), st["cell"])])
    return [Spacer(1, 4), head, Spacer(1, 2),
            _grid_table(rows, [30 * mm, 38 * mm, 38 * mm, CONTENT_W - 106 * mm]),
            Paragraph("Indian AQI computed with CPCB National AQI breakpoints from the CAMS "
                      "model's 24-h (8-h for O3, CO) averages.", st["tiny"])]


def _land_details(det: dict, st: dict) -> list:
    """Terrain, climate, soil, air, amenities, locality — or each one's gap."""
    out: list = [Paragraph("Land details", st["h2"])]

    def gap(what, d):
        reason = _clean((d or {}).get("reason") or "source returned no data")
        return Paragraph(f"<b>{what}:</b> <font color='#948C80'>not available here — {reason}</font>",
                         st["cell"])

    def sub(t):
        return Paragraph(f"<b>{t}</b>", st["cell"])

    # locality
    loc = (det.get("locality") or {}).get("value")
    if loc and loc.get("address"):
        out += [Paragraph(f"<b>Address (OSM):</b> {_clean(loc['address'])}", st["cell"]), Spacer(1, 4)]

    # terrain
    t = det.get("terrain") or {}
    tv = t.get("value")
    if tv:
        blk = [sub("Ground &amp; terrain"),
               Paragraph(_clean(f"{tv['elevation_m']} m above sea level; {tv['slope_class'].lower()} "
                                f"slope of {tv['slope_deg']} deg ({tv['slope_pct']}%)"
                                f"{', facing ' + tv['aspect'] if tv.get('aspect') else ''}. "
                                f"{tv['relative_position']} ({tv['relative_to_1km_m']:+} m vs the "
                                f"land within 1 km): {tv['relative_position_note']}"), st["small"])]
        if t.get("detail"):
            blk += [Spacer(1, 2), _profile_chart(t["detail"]["profile_west_east"],
                                                 t["detail"]["profile_south_north"])]
        out += [KeepTogether(blk), Spacer(1, 6)]
    else:
        out += [gap("Terrain", t), Spacer(1, 4)]

    fl = det.get("flood_screening") or {}
    if fl.get("available"):
        col = {"Elevated": "#B0392F", "Moderate": "#A6790A"}.get(fl["level"], "#2F7D4A")
        out += [Paragraph(f"<b>Flood screening:</b> <font color='{col}'><b>{fl['level']}</b></font> "
                          f"({fl['points']} of {fl['max_points']} risk signs) — "
                          + _clean("; ".join(fl["reasons"])) + ". "
                          + f"<font color='#948C80'>{_clean(fl['note'])}</font>", st["small"]),
                Spacer(1, 6)]

    lc = det.get("land_cover") or {}
    lv = lc.get("value")
    if lv and lc.get("detail"):
        out += [KeepTogether([
            sub(f"Satellite land cover {lv['first_year']}–{lv['year']} — {lv['trend'].lower()}"),
            Paragraph(_clean(lv["summary"]), st["small"]), Spacer(1, 2),
            _share_chart(lc["detail"]["series"]),
            Paragraph("Esri / Impact Observatory Sentinel-2 10 m land cover, 49 samples ~100 m "
                      "apart around the point; ~85% overall classification accuracy.", st["tiny"])]),
            Spacer(1, 6)]
    else:
        out += [gap("Satellite land cover", lc), Spacer(1, 4)]

    # weather at the time this report was generated
    lw = det.get("_live") or {}
    m = lw.get("model") or {}
    if m.get("available"):
        cur, obs, ag = m["current"], lw.get("observed") or {}, lw.get("agreement")
        feels = f" (feels like {cur['feels_like_c']} °C)" if cur.get("feels_like_c") is not None else ""
        line = (f"{cur['sky']['label']}, {cur['temperature_c']} °C{feels}, "
                f"humidity {cur['humidity_pct']}%, wind {cur['wind_kmh']} km/h {cur['wind_from'] or ''}, "
                f"rain now {cur['precipitation_mm']} mm — model value at {cur['time_local'][11:]} local time.")
        if obs.get("available"):
            line += (f" Measured at {obs['station']} ({obs['distance_km']} km away) at "
                     f"{obs['observed_local']}: {obs['temperature_c']} °C"
                     + (f", {obs['humidity_pct']}% humidity" if obs.get("humidity_pct") is not None else "")
                     + (f" ({ag['level']}, {ag['difference_c']:+} °C)." if ag else "."))
        norm = lw.get("vs_normal") or {}
        if norm.get("available"):
            line += " " + norm["summary"]
        rows = [[Paragraph(f"<b>{_clean(d['weekday'])}</b>", st["cell"]),
                 Paragraph(_clean(d["sky"]["label"]), st["cell"]),
                 Paragraph(f"{d['max_c']:.0f}° / {d['min_c']:.0f}°", st["cell"]),
                 Paragraph((f"{d['rain_chance_pct']}% · " if d.get("rain_chance_pct") is not None else "")
                           + f"{d['rain_mm']} mm", st["cell"])]
                for d in m.get("forecast_7d", [])]
        out += [KeepTogether([
            sub(f"Weather when this report was made ({_clean(lw.get('fetched_at', ''))})"),
            Paragraph(_clean(line), st["small"]), Spacer(1, 3),
            _grid_table([[Paragraph(h, st["cellb"]) for h in ("Day", "Sky", "High / low", "Rain chance · amount")]]
                        + rows, [22 * mm, 50 * mm, 30 * mm, CONTENT_W - 102 * mm]),
            Paragraph(_clean(f"Model: {(m.get('provenance') or {}).get('source', 'Open-Meteo')}. "
                             "Measured: NOAA Aviation Weather Center METAR (airport station)."),
                      st["tiny"])]), Spacer(1, 6)]

    # climate
    c = det.get("climate") or {}
    if c.get("detail"):
        cv, cd = c["value"], c["detail"]
        avg = (round(sum(y["rain_mm"] for y in cd["yearly_rain"]) / len(cd["yearly_rain"]))
               if cd["yearly_rain"] else None)
        half = (CONTENT_W - 6 * mm) / 2
        charts = Table([[
            _columns(cd["monthly"], "rain_mm", "month", "Average rain by month (mm)", half),
            _columns(cd["yearly_rain"], "rain_mm", "year", "Rain by year (mm)", half,
                     ref=(avg, f"avg {avg}") if avg else None),
        ]], colWidths=[half + 3 * mm, half + 3 * mm])
        charts.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        line = (f"Wettest month {cd['wettest_month']}, hottest {cd['hottest_month']}; "
                f"{cd['dry_months']} dry month(s) under 30 mm; "
                f"{cv.get('days_above_40c_per_year', '—')} days a year reach 40 °C; "
                f"sunshine {cv.get('solar_kwh_m2_day', '—')} kWh/m2 per day "
                f"(ERA5, {cv['period']}).")
        out += [KeepTogether([sub("Climate (10-year normals)"), Paragraph(_clean(line), st["small"]),
                              Spacer(1, 2), charts]), Spacer(1, 6)]

    # soil
    so = det.get("soil") or {}
    sv = so.get("value")
    if sv:
        rows = [[Paragraph(_clean(k), st["cell"]), Paragraph(f"<b>{_clean(val)}</b>", st["cell"])]
                for k, val in (("Texture", f"{sv['texture_class']}. {sv['texture_note']}"),
                               ("pH (acidity)", f"{sv['ph']} — {sv['ph_note']}"),
                               ("Organic carbon", f"{sv['organic_carbon_g_per_kg']} g/kg ({sv['organic_carbon_note']})"),
                               ("Nitrogen", f"{sv['nitrogen_g_per_kg']} g/kg"),
                               ("CEC (nutrient holding)", f"{sv['cec_cmol_per_kg']} cmol/kg"),
                               ("Bulk density", f"{sv['bulk_density_kg_per_dm3']} kg/dm3"))]
        where = sv.get("sampled_at") or "at the site"
        out += [KeepTogether([sub("Soil (modelled — ISRIC SoilGrids 250 m, topsoil 0-5 cm, "
                                  + _clean(where) + ")"),
                              Spacer(1, 2),
                              _soil_bar(sv["sand_pct"], sv["silt_pct"], sv["clay_pct"]),
                              Spacer(1, 3),
                              _grid_table(rows, [42 * mm, CONTENT_W - 42 * mm], header=False)]),
                Spacer(1, 6)]
    else:
        out += [gap("Soil", so), Spacer(1, 4)]

    # air quality
    a = det.get("air_quality") or {}
    av = a.get("value")
    if av:
        refs = ((a.get("detail") or {}).get("references") or {}).get("pm2_5")
        blk = [sub(f"Air quality — PM2.5 {av['pm2_5_annual_mean']} ug/m3 (12-month average)"),
               Paragraph(_clean(f"{av['summary']} PM10 {av['pm10_annual_mean']} ug/m3 (limit 60); "
                                f"{av['days_pm2_5_above_naaqs_24h']} day(s) above the 24-hour "
                                f"PM2.5 limit of 60. CAMS regional model, ~45 km."), st["small"])]
        if refs:
            blk += [Spacer(1, 3), _aq_bullet(av["pm2_5_annual_mean"], refs)]
        blk += _air_now_rows((det.get("_air") or {}).get("model") or {}, st)
        out += [KeepTogether(blk), Spacer(1, 6)]
    else:
        out += [gap("Air quality", a), Spacer(1, 4)]

    # amenities
    am = det.get("amenities") or {}
    if am.get("available") and am.get("groups"):
        rows = [[Paragraph(h, st["cellb"]) for h in
                 ("Amenity", "Within 500 m", "Within 1 km", "Nearest")]]
        for g in am["groups"]:
            near = _km(g["nearest_m"]) + (f" — {g['nearest_name']}" if g.get("nearest_name") else "")
            rows.append([Paragraph(_clean(g["group"]), st["cell"]),
                         Paragraph(str(g["within_500m"]), st["cell"]),
                         Paragraph(str(g["within_1km"]), st["cell"]),
                         Paragraph(_clean(near), st["cell"])])
        out += [KeepTogether([
            sub(f"Everyday amenities — {am['total_within_1km']} mapped within 1 km "
                f"({am['groups_within_1km']} kinds)"),
            Spacer(1, 2),
            _grid_table(rows, [42 * mm, 22 * mm, 22 * mm, CONTENT_W - 86 * mm]),
            Paragraph(_clean(am.get("note", "")), st["tiny"])])]
    elif am.get("available"):
        out += [Paragraph("<b>Everyday amenities:</b> nothing of these kinds is mapped "
                          "within 5 km in OpenStreetMap.", st["cell"])]
    else:
        out += [gap("Everyday amenities", am)]
    return out


def _label(topic: str) -> str:
    from services.land_profile import topic_label
    return topic_label(topic).lower()
