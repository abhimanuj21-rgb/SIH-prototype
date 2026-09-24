import io
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from services import evidence_engine as ee
from services import land_profile as lp
from services import site_context as sc

router = APIRouter()


class Coord(BaseModel):
    latitude: float
    longitude: float


@router.post("/location")
def location_evidence(c: Coord):
    return ee.get_location_evidence(c.latitude, c.longitude)


@router.post("/site-context")
def site_context(c: Coord):
    """Water / land-use / development context for a point, from live OSM."""
    chk = ee.validate_coordinate(c.latitude, c.longitude)
    if not chk["valid"]:
        return {"available": False, "reason": chk["reason"]}
    return {"location": {"latitude": round(c.latitude, 6),
                         "longitude": round(c.longitude, 6),
                         "city": chk["city"],
                         "in_city_core": chk.get("in_city_core", False)},
            **sc.build_site_context(c.latitude, c.longitude, chk["city"])}


@router.post("/report")
def evidence_report(c: Coord):
    return ee.build_report(c.latitude, c.longitude)


@router.post("/land-profile")
def land_profile(c: Coord):
    """Plain-language outcome: access scores, city comparison, use fit."""
    return lp.build_profile(c.latitude, c.longitude)


@router.get("/live-weather")
def live_weather(latitude: float, longitude: float):
    """Current conditions, 24 h + 7-day forecast, live air, nearest airport
    observation and today-vs-normal for a point (cached ~10 min)."""
    from services import live_weather as lw
    return lw.get_live_weather(latitude, longitude)


@router.get("/live-air")
def live_air(latitude: float, longitude: float):
    """Current pollutants, Indian AQI (CPCB method), 24 h past + next trend,
    and measured station readings when an OpenAQ key is configured."""
    from services import live_air as la
    return la.get_live_air(latitude, longitude)


@router.get("/export/json")
def export_json(latitude: float, longitude: float):
    report = ee.build_report(latitude, longitude)
    payload = json.dumps(report, indent=2).encode()
    return Response(payload, media_type="application/json",
                    headers={"Content-Disposition":
                             'attachment; filename="evidence_report.json"'})


@router.get("/export/manifest")
def export_manifest():
    payload = json.dumps(ee.provenance_manifest(), indent=2).encode()
    return Response(payload, media_type="application/json",
                    headers={"Content-Disposition":
                             'attachment; filename="provenance_manifest.json"'})


@router.get("/export/pdf")
def export_pdf(latitude: float, longitude: float):
    """
    A4 Land Profile PDF (verdict, charts, use fit, open checks). Falls back
    to the plain-text evidence PDF if reportlab is not installed or the
    point is outside every prototype area.
    """
    profile = lp.build_profile(latitude, longitude)
    if "error" not in profile:
        from services import live_air as la
        from services import live_weather as lw
        profile["live_weather"] = lw.get_live_weather(latitude, longitude)
        profile["live_air"] = la.get_live_air(latitude, longitude)
        try:
            from services import pdf_report
        except ImportError:
            pdf_report = None
        if pdf_report is not None:
            name = (f"land_profile_{profile['location']['city']}_"
                    f"{latitude:.4f}_{longitude:.4f}.pdf")
            return Response(pdf_report.render(profile), media_type="application/pdf",
                            headers={"Content-Disposition": f'attachment; filename="{name}"'})

    report = ee.build_report(latitude, longitude)
    lines: list[str] = []
    loc = report.get("location", {})
    lines.append("NATIONAL DIGITAL PLATFORM - LOCATION EVIDENCE REPORT")
    lines.append(f"Location: {loc.get('latitude')}, {loc.get('longitude')}")
    lines.append(f"Generated: {report.get('generated')}")
    lines.append("")
    lines.append("VERIFIED EVIDENCE")
    for v in report.get("verified_evidence", []):
        lines.append(f"  [{v['topic']}] source: {v['provenance']['source']}")
        for k, val in v["value"].items():
            lines.append(f"      {k}: {val}")
    lines.append("")
    lines.append("DATA GAPS")
    for g in report.get("data_gaps", []):
        lines.append(f"  [{g['topic']}] {g.get('dataset_status', '')}")
        lines.append(f"      {g['reason']}")
    lines.append("")
    lines.append("CONCLUSION")
    for chunk in _wrap(report.get("conclusion", ""), 90):
        lines.append(f"  {chunk}")
    lines.append("")
    lines.append(report.get("disclaimer", ""))

    pdf = _text_pdf(lines)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition":
                             'attachment; filename="evidence_report.pdf"'})


def _wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out or [""]


def _text_pdf(lines: list[str]) -> bytes:
    """Hand-rolled single-stream PDF (Helvetica 10pt, A4). No dependencies."""
    def esc(s: str) -> str:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    content = ["BT", "/F1 10 Tf", "12 TL", "50 800 Td"]
    for ln in lines:
        content.append(f"({esc(ln[:110])}) Tj")
        content.append("T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF"
            % (len(objs) + 1, xref_pos))
    return out
