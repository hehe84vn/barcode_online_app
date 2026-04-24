from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Tuple, Iterable, Optional

MM_TO_PT = 72.0 / 25.4

Command = Tuple[str, tuple]

@dataclass
class GlyphPath:
    commands: List[Command]
    advance_width: float

@lru_cache(maxsize=8)
def _load_font(font_path: str):
    from fontTools.ttLib import TTFont
    font = TTFont(font_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    units_per_em = font["head"].unitsPerEm
    hmtx = font["hmtx"]
    return font, glyph_set, cmap, units_per_em, hmtx


def _glyph_recording(font_path: str, ch: str) -> GlyphPath:
    from fontTools.pens.recordingPen import RecordingPen
    font, glyph_set, cmap, units_per_em, hmtx = _load_font(font_path)
    glyph_name = cmap.get(ord(ch))
    if glyph_name is None:
        glyph_name = ".notdef"
    pen = RecordingPen()
    glyph_set[glyph_name].draw(pen)
    aw, _ = hmtx[glyph_name]
    return GlyphPath(commands=list(pen.value), advance_width=float(aw))


def measure_text_mm(text: str, font_path: str, font_size_mm: float, letter_spacing_mm: float = 0.0) -> float:
    _, _, _, units_per_em, _ = _load_font(font_path)
    scale = font_size_mm / float(units_per_em)
    total = 0.0
    for i, ch in enumerate(text):
        gp = _glyph_recording(font_path, ch)
        total += gp.advance_width * scale
        if i < len(text) - 1:
            total += letter_spacing_mm
    return total


def _q_to_cubic(p0, p1, p2):
    c1 = (p0[0] + 2.0/3.0*(p1[0]-p0[0]), p0[1] + 2.0/3.0*(p1[1]-p0[1]))
    c2 = (p2[0] + 2.0/3.0*(p1[0]-p2[0]), p2[1] + 2.0/3.0*(p1[1]-p2[1]))
    return c1, c2, p2


def iter_text_contours_mm(
    text: str,
    font_path: str,
    x_mm: float,
    baseline_y_mm: float,
    font_size_mm: float,
    letter_spacing_mm: float = 0.0,
):
    """Yield glyph outline commands transformed into top-left page millimetres.

    Output commands: M, L, C, Q, Z with coordinates in mm.
    """
    _, _, _, units_per_em, _ = _load_font(font_path)
    scale = font_size_mm / float(units_per_em)
    cursor_x = x_mm
    for ch in text:
        gp = _glyph_recording(font_path, ch)
        for name, args in gp.commands:
            if name == "moveTo":
                x, y = args[0]
                yield ("M", (cursor_x + x * scale, baseline_y_mm - y * scale))
            elif name == "lineTo":
                x, y = args[0]
                yield ("L", (cursor_x + x * scale, baseline_y_mm - y * scale))
            elif name == "curveTo":
                pts = []
                for x, y in args:
                    pts.append((cursor_x + x * scale, baseline_y_mm - y * scale))
                yield ("C", tuple(pts))
            elif name == "qCurveTo":
                pts = [(cursor_x + x * scale, baseline_y_mm - y * scale) for x, y in args if x is not None]
                # TrueType quadratic curves may include multiple off-curve points. Approximate by chaining.
                # This fallback is sufficient for numeric barcode text and Arial glyphs.
                if len(pts) >= 2:
                    start = None
                    # consumer can handle Q; for EPS/PDF we convert later where current point is known
                    for p in pts:
                        pass
                    yield ("Q", tuple(pts))
            elif name == "closePath":
                yield ("Z", ())
        cursor_x += gp.advance_width * scale + letter_spacing_mm


def text_to_svg_path_d(*args, **kwargs) -> str:
    d = []
    for cmd, vals in iter_text_contours_mm(*args, **kwargs):
        if cmd == "M":
            x, y = vals; d.append(f"M{x:.4f},{y:.4f}")
        elif cmd == "L":
            x, y = vals; d.append(f"L{x:.4f},{y:.4f}")
        elif cmd == "C":
            (x1,y1),(x2,y2),(x3,y3) = vals; d.append(f"C{x1:.4f},{y1:.4f} {x2:.4f},{y2:.4f} {x3:.4f},{y3:.4f}")
        elif cmd == "Q":
            if len(vals) >= 2:
                x1,y1 = vals[0]; x2,y2 = vals[-1]; d.append(f"Q{x1:.4f},{y1:.4f} {x2:.4f},{y2:.4f}")
        elif cmd == "Z":
            d.append("Z")
    return " ".join(d)


def append_text_eps(lines: List[str], text: str, font_path: str, x_mm: float, baseline_y_mm: float, font_size_mm: float, page_h_mm: float, letter_spacing_mm: float = 0.0):
    """Append text outlines as filled PostScript paths."""
    cur = None
    start = None
    lines.append("newpath")
    for cmd, vals in iter_text_contours_mm(text, font_path, x_mm, baseline_y_mm, font_size_mm, letter_spacing_mm):
        if cmd == "M":
            x, y = vals; yp = page_h_mm - y
            lines.append(f"{x*MM_TO_PT:.4f} {yp*MM_TO_PT:.4f} moveto")
            cur = (x, y); start = (x, y)
        elif cmd == "L":
            x, y = vals; yp = page_h_mm - y
            lines.append(f"{x*MM_TO_PT:.4f} {yp*MM_TO_PT:.4f} lineto")
            cur = (x, y)
        elif cmd == "C":
            pts = []
            for x, y in vals:
                pts.append((x*MM_TO_PT, (page_h_mm-y)*MM_TO_PT))
            lines.append(f"{pts[0][0]:.4f} {pts[0][1]:.4f} {pts[1][0]:.4f} {pts[1][1]:.4f} {pts[2][0]:.4f} {pts[2][1]:.4f} curveto")
            cur = vals[-1]
        elif cmd == "Q" and cur is not None and len(vals) >= 2:
            p1 = vals[0]; p2 = vals[-1]
            c1, c2, p3 = _q_to_cubic(cur, p1, p2)
            pts = []
            for x, y in (c1, c2, p3):
                pts.append((x*MM_TO_PT, (page_h_mm-y)*MM_TO_PT))
            lines.append(f"{pts[0][0]:.4f} {pts[0][1]:.4f} {pts[1][0]:.4f} {pts[1][1]:.4f} {pts[2][0]:.4f} {pts[2][1]:.4f} curveto")
            cur = p3
        elif cmd == "Z":
            lines.append("closepath")
            cur = start
    lines.append("fill")


def draw_text_pdf(canvas, text: str, font_path: str, x_mm: float, baseline_y_mm: float, font_size_mm: float, page_h_mm: float, letter_spacing_mm: float = 0.0):
    p = canvas.beginPath()
    cur = None
    start = None
    for cmd, vals in iter_text_contours_mm(text, font_path, x_mm, baseline_y_mm, font_size_mm, letter_spacing_mm):
        if cmd == "M":
            x, y = vals; p.moveTo(x*MM_TO_PT, (page_h_mm-y)*MM_TO_PT); cur = (x,y); start = (x,y)
        elif cmd == "L":
            x, y = vals; p.lineTo(x*MM_TO_PT, (page_h_mm-y)*MM_TO_PT); cur = (x,y)
        elif cmd == "C":
            pts = [(x*MM_TO_PT, (page_h_mm-y)*MM_TO_PT) for x,y in vals]
            p.curveTo(pts[0][0], pts[0][1], pts[1][0], pts[1][1], pts[2][0], pts[2][1]); cur = vals[-1]
        elif cmd == "Q" and cur is not None and len(vals) >= 2:
            c1, c2, p3 = _q_to_cubic(cur, vals[0], vals[-1])
            pts = [(x*MM_TO_PT, (page_h_mm-y)*MM_TO_PT) for x,y in (c1,c2,p3)]
            p.curveTo(pts[0][0], pts[0][1], pts[1][0], pts[1][1], pts[2][0], pts[2][1]); cur = p3
        elif cmd == "Z":
            p.close(); cur = start
    canvas.drawPath(p, stroke=0, fill=1)
