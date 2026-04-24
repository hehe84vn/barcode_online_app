from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from barcode_core import (
    InputRow,
    classify_code,
    clean_code,
    validate_code,
    ensure_dirs,
    generate_row,
    zip_folder,
    cleanup_old_jobs,
)

APP_DIR = Path(__file__).resolve().parent
FONT_PATH = APP_DIR / "fonts" / "Arial.ttf"
JOBS_DIR = APP_DIR / ".tmp_jobs"
REQUIRED_COLUMNS = ["Communication number", "EAN/UPC", "Product Version no."]

st.set_page_config(page_title="Barcode / DataMatrix Generator", layout="wide")

st.title("Barcode / DataMatrix Generator")
st.caption("MVP nội bộ: Excel → SVG / EPS / PDF / ZIP. File tạm tự xoá sau 8 giờ.")

cleanup_old_jobs(JOBS_DIR, max_age_hours=8)

with st.sidebar:
    st.header("Cấu hình")
    make_svg = st.checkbox("Xuất SVG", value=True)
    make_eps = st.checkbox("Xuất EPS", value=True)
    make_pdf = st.checkbox("Xuất PDF", value=True)
    max_rows = st.number_input("Giới hạn dòng/lần", min_value=10, max_value=5000, value=1000, step=100)
    st.divider()
    st.write("Font:")
    if FONT_PATH.exists():
        st.success("Đã thấy fonts/Arial.ttf")
    else:
        st.error("Thiếu fonts/Arial.ttf")

uploaded = st.file_uploader("Upload Excel", type=["xlsx", "xls"])

if uploaded is None:
    st.info("Upload file Excel để bắt đầu.")
    st.stop()

if not FONT_PATH.exists():
    st.warning("Vui lòng copy Arial.ttf vào thư mục `fonts/Arial.ttf` trước khi generate.")

try:
    df = pd.read_excel(uploaded, dtype=str)
except Exception as e:
    st.error(f"Không đọc được Excel: {e}")
    st.stop()

missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    st.error("Thiếu cột bắt buộc: " + ", ".join(missing))
    st.stop()

work = df[REQUIRED_COLUMNS].copy()
work["Communication number"] = work["Communication number"].fillna("").astype(str).str.strip()
work["Product Version no."] = work["Product Version no."].fillna("").astype(str).str.strip()
work["Clean code"] = work["EAN/UPC"].apply(clean_code)
work["Type"] = work["Clean code"].apply(classify_code)

statuses = []
for _, r in work.iterrows():
    ok, msg = validate_code(r["Clean code"], r["Type"])
    if not str(r["Communication number"]).strip():
        ok, msg = False, "Thiếu Communication number"
    if not str(r["Product Version no."]).strip():
        ok, msg = False, "Thiếu Product Version no."
    statuses.append("OK" if ok else msg)
work["Status"] = statuses

valid = work[work["Status"] == "OK"].copy()
invalid = work[work["Status"] != "OK"].copy()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Tổng dòng", len(work))
c2.metric("Hợp lệ", len(valid))
c3.metric("EAN", int((valid["Type"] == "EAN").sum()))
c4.metric("UPC", int((valid["Type"] == "UPC").sum()))

if len(work) > max_rows:
    st.error(f"File có {len(work)} dòng, vượt giới hạn {max_rows} dòng/lần. Hãy tách batch hoặc tăng giới hạn nếu server đủ mạnh.")
    st.stop()

with st.expander("Preview dữ liệu", expanded=True):
    st.dataframe(work, use_container_width=True)

if len(invalid):
    st.warning(f"Có {len(invalid)} dòng lỗi. App chỉ generate các dòng OK.")

if len(valid) == 0:
    st.stop()

if st.button("Generate ZIP", type="primary", disabled=not FONT_PATH.exists()):
    batch_name = "BARCODE_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    job_id = uuid.uuid4().hex[:8]
    job_dir = JOBS_DIR / f"job_{batch_name}_{job_id}"
    batch_root = job_dir / batch_name
    ensure_dirs(batch_root)

    progress = st.progress(0)
    log = st.empty()
    errors = []

    rows = []
    for _, r in valid.iterrows():
        rows.append(InputRow(
            communication=str(r["Communication number"]).strip(),
            code=str(r["Clean code"]).strip(),
            version=str(r["Product Version no."]).strip(),
            kind=str(r["Type"]).strip(),
        ))

    for i, row in enumerate(rows, start=1):
        try:
            log.write(f"Đang xử lý {i}/{len(rows)}: {row.communication}_{row.version}_{row.kind}")
            generate_row(row, batch_root, str(FONT_PATH), make_svg=make_svg, make_eps=make_eps, make_pdf=make_pdf)
        except Exception as e:
            errors.append(f"{row.communication}_{row.version}_{row.kind}: {e}")
        progress.progress(i / len(rows))

    zip_path = job_dir / f"{batch_name}.zip"
    zip_folder(batch_root, zip_path)

    if errors:
        st.error("Một số dòng generate lỗi:")
        st.code("\n".join(errors[:50]))
    else:
        st.success("Generate xong.")

    data = zip_path.read_bytes()
    st.download_button(
        "Download ZIP",
        data=data,
        file_name=f"{batch_name}.zip",
        mime="application/zip",
    )
    st.caption("File tạm sẽ được xoá tự động sau tối đa 8 giờ.")
