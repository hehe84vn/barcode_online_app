from __future__ import annotations

import io
import math
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional

from vector_font import MM_TO_PT, measure_text_mm, text_to_svg_path_d, append_text_eps, draw_text_pdf

PAGE_MM = 50.0
DM_SIZE_MM = 16.0
DM_X_MM = 17.0
DM_Y_MM = 17.0
BARCODE_SCALE = 0.80

EAN_L = {
    "0": "0001101", "1": "0011001", "2": "0010011", "3": "0111101", "4": "0100011",
    "5": "0110001", "6": "0101111", "7": "0111011", "8": "0110111", "9": "0001011",
}
EAN_G = {
    "0": "0100111", "1": "0110011", "2": "0011011", "3": "0100001", "4": "0011101",
    "5": "0111001", "6": "0000101", "7": "0010001", "8": "0001001", "9": "0010111",
}
EAN_R = {
    "0": "1110010", "1": "1100110", "2": "1101100", "3": "1000010", "4": "1011100",
    "5": "1001110", "6": "1010000", "7": "1000100", "8": "1001000", "9": "1110100",
}
EAN_PARITY = {
    "0": "LLLLLL", "1": "LLGLGG", "2": "LLGGLG", "3": "LLGGGL", "4": "LGLLGG",
    "5": "LGGLLG", "6": "LGGGLL", "7": "LGLGLG", "8": "LGLGGL", "9": "LGGLGL",
}
UPC_L = EAN_L
UPC_R = EAN_R

@dataclass
class InputRow:
    communication: str
    code: str
    version: str
    kind: str  # EAN / UPC

@dataclass
class ShapeSet:
    rects: List[Tuple[float, float, float, float]]  # x,y,w,h in mm top-left coordinates
    text_parts: List[Tuple[str, float, float, float, float]]  # text,x,baseline_y,size,letter_spacing
    page_w: float = PAGE_MM
    page_h: float = PAGE_MM


def clean_code(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return re.sub(r"\D", "", s)


def ean13_check_digit(first12: str) -> str:
    total = 0
    for i, ch in enumerate(first12):
        total += int(ch) * (1 if i % 2 == 0 else 3)
    return str((10 - (total % 10)) % 10)


def upca_check_digit(first11: str) -> str:
    total = 0
    for i, ch in enumerate(first11):
        total += int(ch) * (3 if i % 2 == 0 else 1)
    return str((10 - (total % 10)) % 10)


def classify_code(code: str) -> str:
    if len(code) == 13:
        return "EAN"
    if len(code) == 12:
        return "UPC"
    return "INVALID"


def validate_code(code: str, kind: str) -> Tuple[bool, str]:
    if kind == "EAN":
        if len(code) != 13:
            return False, "EAN-13 phải có 13 số"
        if ean13_check_digit(code[:12]) != code[-1]:
            return False, "Sai check digit EAN-13"
    elif kind == "UPC":
        if len(code) != 12:
            return False, "UPC-A phải có 12 số"
        if upca_check_digit(code[:11]) != code[-1]:
            return False, "Sai check digit UPC-A"
    else:
        return False, "Không xác định EAN/UPC"
    return True, "OK"


def ean13_bits(code: str) -> str:
    first = code[0]
    left = code[1:7]
    right = code[7:]
    parity = EAN_PARITY[first]
    bits = "101"
    for digit, p in zip(left, parity):
        bits += EAN_L[digit] if p == "L" else EAN_G[digit]
    bits += "01010"
    for digit in right:
        bits += EAN_R[digit]
    bits += "101"
    return bits


def upca_bits(code: str) -> str:
    left = code[:6]
    right = code[6:]
    bits = "101"
    for digit in left:
        bits += UPC_L[digit]
    bits += "01010"
    for digit in right:
        bits += UPC_R[digit]
    bits += "101"
    return bits


def _runs(bits: str) -> Iterable[Tuple[int, int, str]]:
    i = 0
    while i < len(bits):
        j = i + 1
        while j < len(bits) and bits[j] == bits[i]:
            j += 1
        yield i, j - i, bits[i]
        i = j


def barcode_shapes(code: str, kind: str) -> ShapeSet:
    """Return shapes matching the old flow closely enough for first validation.

    Coordinates are in mm on a 50mm page. EPS export later crops to artwork bbox.
    """
    if kind == "EAN":
        bits = ean13_bits(code)
        module = 0.352  # unscaled mm; action scales 80%, old EPS width ~26.75mm
        bar_h = 21.85
        guard_h = 23.85
        x0 = (PAGE_MM - len(bits) * module * BARCODE_SCALE) / 2.0 / BARCODE_SCALE
        y0 = 12.9 / BARCODE_SCALE
        text_base = (12.9 + 19.05) / BARCODE_SCALE
        font_size = 3.05 / BARCODE_SCALE
        letter = 0.36 / BARCODE_SCALE
    else:
        bits = upca_bits(code)
        module = 0.374  # unscaled mm; action scales 80%, old EPS width ~28.4mm
        bar_h = 21.85
        guard_h = 23.85
        x0 = (PAGE_MM - len(bits) * module * BARCODE_SCALE) / 2.0 / BARCODE_SCALE
        y0 = 12.9 / BARCODE_SCALE
        text_base = (12.9 + 19.05) / BARCODE_SCALE
        font_size = 3.05 / BARCODE_SCALE
        letter = 0.36 / BARCODE_SCALE

    guard_indices = set(list(range(0,3)) + list(range(45,50)) + list(range(92,95)))
    rects = []
    for start, length, bit in _runs(bits):
        if bit != "1":
            continue
        is_guard = any(i in guard_indices for i in range(start, start + length))
        h = guard_h if is_guard else bar_h
        rects.append((x0 + start * module, y0, length * module, h))

    # Fine-tuned text layout so the outlined Arial digits sit lower and do not
    # collide with the barcode bars after the legacy 80% scale is applied.
    # The values below are calibrated against the approved sample EPS.
    text_parts = []
    if kind == "EAN":
        tuned_base = text_base + 2.70
        tuned_size = font_size * 0.94
        tuned_letter = 0.28
        text_parts.append((code[0], x0 + 0.10, tuned_base + 0.10, tuned_size * 0.875, 0.0))
        text_parts.append((code[1:7], x0 + 6.0 * module, tuned_base, tuned_size, tuned_letter))
        text_parts.append((code[7:], x0 + 51.0 * module, tuned_base, tuned_size, tuned_letter))
    else:
        tuned_base = text_base + 2.70
        tuned_size = font_size * 0.94
        tuned_letter = 0.28
        text_parts.append((code[0], x0 + 0.10, tuned_base + 0.10, tuned_size * 0.875, 0.0))
        text_parts.append((code[1:6], x0 + 8.0 * module, tuned_base, tuned_size, tuned_letter))
        text_parts.append((code[6:11], x0 + 53.0 * module, tuned_base, tuned_size, tuned_letter))
        text_parts.append((code[-1], x0 + 92.0 * module, tuned_base + 0.10, tuned_size * 0.875, 0.0))

    # Apply old Illustrator scale 80% around origin, then recentre visual group by returning transformed shapes.
    # We scale around page centre for stable page placement; EPS will crop actual artwork.
    return scale_shapes(ShapeSet(rects, text_parts), BARCODE_SCALE, PAGE_MM/2.0, PAGE_MM/2.0)


def scale_shapes(shapes: ShapeSet, factor: float, cx: float, cy: float) -> ShapeSet:
    def sx(x): return cx + (x - cx) * factor
    def sy(y): return cy + (y - cy) * factor
    rects = [(sx(x), sy(y), w*factor, h*factor) for x,y,w,h in shapes.rects]
    texts = [(txt, sx(x), sy(base), size*factor, letter*factor) for txt,x,base,size,letter in shapes.text_parts]
    return ShapeSet(rects, texts, shapes.page_w, shapes.page_h)


def datamatrix_modules(data: str) -> List[List[int]]:
    """Generate a DataMatrix module matrix without native libdmtx.

    Preferred backend: pyStrich (pure Python + Pillow/Numpy), suitable for
    Streamlit Cloud because it does not need apt/system package libdmtx.
    Fallback: pylibdmtx if available.
    Returns a 0/1 matrix including the rendered DataMatrix symbol area.
    """
    # Backend 1: pyStrich. This avoids libdmtx native dependency on Streamlit Cloud.
    try:
        from pystrich.datamatrix import DataMatrixEncoder
        encoder = DataMatrixEncoder(data)
        ascii_matrix = encoder.get_ascii()
        rows = [line.rstrip() for line in ascii_matrix.splitlines() if line.strip()]
        if not rows:
            raise RuntimeError("pyStrich returned empty DataMatrix")

        # pyStrich ASCII uses two characters for one visual module in examples,
        # typically 'XX' for black and spaces for white. Group by 2 chars.
        max_len = max(len(r) for r in rows)
        rows = [r.ljust(max_len) for r in rows]
        matrix = []
        for line in rows:
            row = []
            for i in range(0, len(line), 2):
                cell = line[i:i+2]
                row.append(1 if 'X' in cell else 0)
            matrix.append(row)

        # Trim fully white quiet-zone rows/cols so the artwork matches old EPS
        # crop behavior: real DataMatrix artwork is placed at 16mm x 16mm.
        non_empty_rows = [i for i, row in enumerate(matrix) if any(row)]
        non_empty_cols = [j for j in range(max(len(r) for r in matrix)) if any(j < len(r) and r[j] for r in matrix)]
        if not non_empty_rows or not non_empty_cols:
            raise RuntimeError("pyStrich DataMatrix has no black modules")
        r1, r2 = min(non_empty_rows), max(non_empty_rows)
        c1, c2 = min(non_empty_cols), max(non_empty_cols)
        trimmed = [row[c1:c2+1] for row in matrix[r1:r2+1]]
        return trimmed
    except Exception:
        pass

    # Backend 2: pylibdmtx fallback. This requires native libdmtx and is kept
    # only for local/VPS environments where libdmtx is installed.
    try:
        from pylibdmtx.pylibdmtx import encode
        from PIL import Image
    except Exception as e:
        raise RuntimeError("DataMatrix cần pyStrich hoặc pylibdmtx + pillow + libdmtx trên server") from e

    enc = encode(data.encode("utf-8"))
    img = Image.frombytes("RGB", (enc.width, enc.height), enc.pixels)
    gray = img.convert("L")
    pix = gray.load()
    xs, ys = [], []
    for y in range(gray.height):
        for x in range(gray.width):
            if pix[x, y] < 128:
                xs.append(x); ys.append(y)
    if not xs:
        raise RuntimeError("Không tạo được DataMatrix")
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    side_px = max(maxx-minx+1, maxy-miny+1)
    candidates = [10,12,14,16,18,20,22,24,26,32,36,40,44,48,52,64,72,80,88,96,104,120,132,144]
    modules = min(candidates, key=lambda n: abs(side_px / n - round(side_px / n)))
    pitch = side_px / modules
    matrix = []
    for r in range(modules):
        row = []
        for c in range(modules):
            x = int(minx + (c + 0.5) * pitch)
            y = int(miny + (r + 0.5) * pitch)
            row.append(1 if pix[min(max(x,0),gray.width-1), min(max(y,0),gray.height-1)] < 128 else 0)
        matrix.append(row)
    return matrix

def datamatrix_shapes(data: str) -> ShapeSet:
    matrix = datamatrix_modules(data)
    n = len(matrix)
    cell = DM_SIZE_MM / n
    rects = []
    for r, row in enumerate(matrix):
        for c, v in enumerate(row):
            if v:
                rects.append((DM_X_MM + c * cell, DM_Y_MM + r * cell, cell, cell))
    return ShapeSet(rects, [])


def artwork_bbox(shapes: ShapeSet, font_path: Optional[str] = None, pad_mm: float = 0.0) -> Tuple[float,float,float,float]:
    xs = []
    ys = []
    for x,y,w,h in shapes.rects:
        xs += [x, x+w]; ys += [y, y+h]
    # Text bbox estimate; EPS crop may be refined by Illustrator but this is stable.
    if font_path:
        for txt,x,base,size,letter in shapes.text_parts:
            width = measure_text_mm(txt, font_path, size, letter)
            xs += [x, x+width]
            ys += [base-size*0.95, base+size*0.25]
    if not xs:
        return (0,0,0,0)
    return (min(xs)-pad_mm, min(ys)-pad_mm, max(xs)+pad_mm, max(ys)+pad_mm)


def write_svg(path: Path, shapes: ShapeSet, font_path: str):
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" x="0mm" y="0mm" width="{shapes.page_w:g}mm" height="{shapes.page_h:g}mm" viewBox="0 0 {shapes.page_w:g} {shapes.page_h:g}">',
        '<style>.fill{fill:#000000;}</style>',
        '<g>'
    ]
    for x,y,w,h in shapes.rects:
        parts.append(f'<rect class="fill" x="{x:.4f}" y="{y:.4f}" width="{w:.4f}" height="{h:.4f}"/>')
    for txt,x,base,size,letter in shapes.text_parts:
        d = text_to_svg_path_d(txt, font_path, x, base, size, letter)
        parts.append(f'<path class="fill" d="{d}"/>')
    parts += ['</g>', '</svg>']
    path.write_text("\n".join(parts), encoding="utf-8")


def write_eps(path: Path, shapes: ShapeSet, font_path: str, crop: bool = True):
    if crop:
        x1,y1,x2,y2 = artwork_bbox(shapes, font_path, pad_mm=0.0)
    else:
        x1,y1,x2,y2 = 0,0,shapes.page_w,shapes.page_h
    w = max(0.01, x2-x1); h = max(0.01, y2-y1)
    # EPS coordinate system after translation: crop top-left becomes page top-left of h.
    shifted = ShapeSet(
        rects=[(x-x1, y-y1, rw, rh) for x,y,rw,rh in shapes.rects],
        text_parts=[(t, x-x1, base-y1, size, letter) for t,x,base,size,letter in shapes.text_parts],
        page_w=w, page_h=h,
    )
    lines = []
    lines.append("%!PS-Adobe-3.0 EPSF-3.0")
    lines.append(f"%%BoundingBox: 0 0 {math.ceil(w*MM_TO_PT)} {math.ceil(h*MM_TO_PT)}")
    lines.append(f"%%HiResBoundingBox: 0 0 {w*MM_TO_PT:.4f} {h*MM_TO_PT:.4f}")
    lines.append("%%DocumentProcessColors: Black")
    lines.append("%%EndComments")
    lines.append("/rectfill { 4 dict begin /hh exch def /ww exch def /yy exch def /xx exch def newpath xx yy moveto ww 0 rlineto 0 hh rlineto ww neg 0 rlineto closepath fill end } bind def")
    lines.append("true setoverprint")
    lines.append("0 0 0 1 setcmykcolor")
    for x,y,rw,rh in shifted.rects:
        xp = x * MM_TO_PT
        yp = (shifted.page_h - y - rh) * MM_TO_PT
        lines.append(f"{xp:.4f} {yp:.4f} {rw*MM_TO_PT:.4f} {rh*MM_TO_PT:.4f} rectfill")
    for txt,x,base,size,letter in shifted.text_parts:
        append_text_eps(lines, txt, font_path, x, base, size, shifted.page_h, letter)
    lines.append("showpage")
    lines.append("%%EOF")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_pdf(path: Path, shapes: ShapeSet, font_path: str):
    try:
        from reportlab.pdfgen import canvas
    except Exception as e:
        raise RuntimeError("PDF export cần cài reportlab") from e
    c = canvas.Canvas(str(path), pagesize=(shapes.page_w*MM_TO_PT, shapes.page_h*MM_TO_PT))
    # CMYK K100
    try:
        c.setFillColorCMYK(0, 0, 0, 1)
    except Exception:
        c.setFillGray(0)
    # Overprint where supported by ReportLab canvas.
    if hasattr(c, "setFillOverprint"):
        try: c.setFillOverprint(True)
        except Exception: pass
    if hasattr(c, "setOverprintMask"):
        try: c.setOverprintMask(True)
        except Exception: pass
    for x,y,w,h in shapes.rects:
        c.rect(x*MM_TO_PT, (shapes.page_h-y-h)*MM_TO_PT, w*MM_TO_PT, h*MM_TO_PT, stroke=0, fill=1)
    for txt,x,base,size,letter in shapes.text_parts:
        draw_text_pdf(c, txt, font_path, x, base, size, shapes.page_h, letter)
    c.showPage(); c.save()


def ensure_dirs(root: Path):
    dirs = [
        "svg/EAN", "svg/UPC", "svg/DATAMATRIX_EAN", "svg/DATAMATRIX_UPC",
        "dist/EAN/EAN_EPS", "dist/EAN/EAN_PDF",
        "dist/UPC/UPC_EPS", "dist/UPC/UPC_PDF",
        "dist/DATAMATRIX_EAN/EAN_DATAMATRIX_EPS", "dist/DATAMATRIX_EAN/EAN_DATAMATRIX_PDF",
        "dist/DATAMATRIX_UPC/UPC_DATAMATRIX_EPS", "dist/DATAMATRIX_UPC/UPC_DATAMATRIX_PDF",
    ]
    for d in dirs:
        (root/d).mkdir(parents=True, exist_ok=True)


def output_names(row: InputRow) -> Dict[str, str]:
    prefix = f"{row.communication}_{row.version}_{row.kind}"
    return {
        "barcode": prefix,
        "dm": prefix + "_DATAMATRIX",
    }


def generate_row(row: InputRow, batch_root: Path, font_path: str, make_svg=True, make_eps=True, make_pdf=True):
    names = output_names(row)
    shapes = barcode_shapes(row.code, row.kind)
    if make_svg:
        write_svg(batch_root / "svg" / row.kind / f"{names['barcode']}.svg", shapes, font_path)
    if make_eps:
        write_eps(batch_root / "dist" / row.kind / f"{row.kind}_EPS" / f"{names['barcode']}.eps", shapes, font_path, crop=True)
    if make_pdf:
        write_pdf(batch_root / "dist" / row.kind / f"{row.kind}_PDF" / f"{names['barcode']}.pdf", shapes, font_path)

    dm_shapes = datamatrix_shapes(row.code)
    dm_dir = f"DATAMATRIX_{row.kind}"
    dm_prefix = f"{row.kind}_DATAMATRIX"
    if make_svg:
        write_svg(batch_root / "svg" / dm_dir / f"{names['dm']}.svg", dm_shapes, font_path)
    if make_eps:
        write_eps(batch_root / "dist" / dm_dir / f"{dm_prefix}_EPS" / f"{names['dm']}.eps", dm_shapes, font_path, crop=True)
    if make_pdf:
        write_pdf(batch_root / "dist" / dm_dir / f"{dm_prefix}_PDF" / f"{names['dm']}.pdf", dm_shapes, font_path)


def zip_folder(src: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(src.parent))


def cleanup_old_jobs(base_dir: Path, max_age_hours: int = 8):
    if not base_dir.exists():
        return
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    for p in base_dir.iterdir():
        if not p.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            if mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass
