from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timedelta
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

# Working temp folder: only used while generating. The current job folder is deleted
# immediately after the ZIP is copied into HISTORY_DIR.
JOBS_DIR = APP_DIR / ".tmp_jobs"

# Download history: keep only the 3 newest ZIP files, each no older than 48 hours.
HISTORY_DIR = APP_DIR / ".history"
HISTORY_MAX_FILES = 3
HISTORY_MAX_HOURS = 48

REQUIRED_COLUMNS = ["Communication number", "EAN/UPC", "Product Version no."]
COMPANY_LOGO_URL = "https://spring-cc.com/_assets/v11/a04d764c1c5ecfe5a14652f59cc5c020ef497847.svg"


def inject_css():
    st.markdown(
        """
        <style>
            :root {
                --spring-red: #ff4f57;
                --spring-red-dark: #e83944;
                --spring-ink: #2e3142;
                --spring-muted: #777b8f;
                --spring-soft: #fff3f4;
                --spring-border: #ececf2;
                --spring-card: #ffffff;
                --spring-bg: #fafafa;
            }

            .stApp {
                background:
                    radial-gradient(circle at 0% 0%, rgba(255, 79, 87, 0.08), transparent 28%),
                    linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
            }

            section[data-testid="stSidebar"] {
                background: #f4f5f8;
                border-right: 1px solid var(--spring-border);
            }

            .block-container {
                max-width: 1280px;
                padding-top: 2.2rem;
                padding-bottom: 3rem;
            }

            h1, h2, h3 {
                color: var(--spring-ink);
                letter-spacing: -0.03em;
            }

            div[data-testid="stMetric"] {
                background: var(--spring-card);
                border: 1px solid var(--spring-border);
                border-radius: 18px;
                padding: 18px 18px 12px;
                box-shadow: 0 10px 30px rgba(30, 32, 50, 0.04);
            }

            div[data-testid="stMetricLabel"] {
                color: var(--spring-muted);
            }

            .spring-hero {
                background: rgba(255,255,255,0.76);
                border: 1px solid var(--spring-border);
                border-radius: 28px;
                padding: 28px 30px;
                box-shadow: 0 18px 50px rgba(30,32,50,0.06);
                margin-bottom: 22px;
            }

            .spring-logo-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 20px;
                margin-bottom: 10px;
            }

            .spring-logo {
                width: 330px;
                height: 45px;
                object-fit: contain;
            }

            .spring-title {
                margin: 0;
                font-size: 42px;
                line-height: 1.05;
                letter-spacing: -0.045em;
                font-weight: 800;
                color: var(--spring-ink);
            }

            .spring-subtitle {
                margin-top: 12px;
                color: var(--spring-muted);
                font-size: 15px;
            }

            .spring-badge {
                display: inline-flex;
                align-items: center;
                border: 1px solid rgba(255, 79, 87, 0.22);
                background: var(--spring-soft);
                color: var(--spring-red-dark);
                border-radius: 999px;
                padding: 7px 12px;
                font-size: 13px;
                font-weight: 700;
                white-space: nowrap;
            }

            .spring-section-card {
                background: rgba(255,255,255,0.86);
                border: 1px solid var(--spring-border);
                border-radius: 22px;
                padding: 22px;
                box-shadow: 0 12px 34px rgba(30,32,50,0.05);
                margin-bottom: 18px;
            }

            .history-item {
                background: #fff;
                border: 1px solid var(--spring-border);
                border-radius: 18px;
                padding: 16px 18px;
                margin-bottom: 12px;
                box-shadow: 0 10px 24px rgba(30,32,50,0.04);
            }

            .history-name {
                font-weight: 800;
                color: var(--spring-ink);
                margin-bottom: 4px;
            }

            .history-meta {
                color: var(--spring-muted);
                font-size: 13px;
            }

            div.stButton > button[kind="primary"],
            div.stDownloadButton > button[kind="primary"] {
                background: var(--spring-red);
                border-color: var(--spring-red);
                color: white;
                border-radius: 13px;
                font-weight: 800;
                padding: 0.68rem 1.15rem;
            }

            div.stButton > button[kind="primary"]:hover,
            div.stDownloadButton > button[kind="primary"]:hover {
                background: var(--spring-red-dark);
                border-color: var(--spring-red-dark);
            }

            div.stButton > button,
            div.stDownloadButton > button {
                border-radius: 13px;
                border-color: #dfe1e8;
                color: var(--spring-ink);
                font-weight: 700;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                background: #f2f3f7;
                padding: 6px;
                border-radius: 16px;
                width: fit-content;
            }

            .stTabs [data-baseweb="tab"] {
                border-radius: 12px;
                padding: 8px 18px;
                color: var(--spring-muted);
                font-weight: 800;
            }

            .stTabs [aria-selected="true"] {
                background: #fff;
                color: var(--spring-red-dark);
                box-shadow: 0 6px 16px rgba(30,32,50,0.08);
            }

            div[data-testid="stFileUploader"] section {
                border-radius: 18px;
                border: 1px dashed #d7d9e2;
                background: #f7f8fb;
            }

            div[data-testid="stDataFrame"] {
                border-radius: 16px;
                overflow: hidden;
            }

            .sidebar-logo {
                margin: 8px 0 22px;
            }

            .sidebar-logo img {
                width: 220px;
                max-width: 100%;
                height: 30px;
                object-fit: contain;
            }

            @media (max-width: 900px) {
                .spring-logo-row {
                    align-items: flex-start;
                    flex-direction: column;
                }
                .spring-title {
                    font-size: 34px;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_app_password() -> str:
    """Read password from Streamlit Secrets, fallback to the default internal password."""
    try:
        return str(st.secrets.get("APP_PASSWORD", "Springcc2026"))
    except Exception:
        return "Springcc2026"


def require_login():
    """Simple shared-password login for light internal protection."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return

    st.set_page_config(page_title="Barcode / DataMatrix Generator", layout="centered")
    inject_css()

    st.markdown(
        f"""
        <div class="spring-section-card" style="max-width: 520px; margin: 60px auto 20px; text-align: center;">
            <img src="{COMPANY_LOGO_URL}" alt="Spring CC" style="width:330px; height:45px; object-fit:contain; margin-bottom: 18px;">
            <h1 style="font-size: 32px; margin-bottom: 6px;">Barcode / DataMatrix Generator</h1>
            <p style="color:#777b8f; margin-top: 0;">Internal tool. Please login to continue.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

    if submitted:
        if password == get_app_password():
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    st.stop()


def cleanup_history():
    """Keep history lightweight: max 3 ZIP files, max age 48 hours."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    zip_files = [p for p in HISTORY_DIR.glob("*.zip") if p.is_file()]

    for zip_file in zip_files:
        try:
            mtime = datetime.fromtimestamp(zip_file.stat().st_mtime)
            if now - mtime > timedelta(hours=HISTORY_MAX_HOURS):
                zip_file.unlink(missing_ok=True)
        except Exception:
            pass

    zip_files = [p for p in HISTORY_DIR.glob("*.zip") if p.is_file()]
    zip_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for old_file in zip_files[HISTORY_MAX_FILES:]:
        try:
            old_file.unlink(missing_ok=True)
        except Exception:
            pass


def save_zip_to_history(zip_path: Path) -> Path:
    """Copy finished ZIP into history and clean history limits."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_path = HISTORY_DIR / zip_path.name

    if history_path.exists():
        history_path = HISTORY_DIR / f"{zip_path.stem}_{uuid.uuid4().hex[:4]}{zip_path.suffix}"

    shutil.copy2(zip_path, history_path)
    cleanup_history()
    return history_path


def render_history():
    """Show the latest downloadable ZIP files."""
    cleanup_history()

    zip_files = [p for p in HISTORY_DIR.glob("*.zip") if p.is_file()]
    zip_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    st.markdown(
        """
        <div class="spring-section-card">
            <h2 style="margin-top:0;">History</h2>
            <p style="color:#777b8f; margin-bottom:0;">
                Lưu tối đa 3 file ZIP gần nhất trong 48 giờ. Có thể mất sớm hơn nếu app reboot/redeploy.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not zip_files:
        st.info("Chưa có file history.")
        return

    for idx, zip_file in enumerate(zip_files, start=1):
        stat = zip_file.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_mb = stat.st_size / (1024 * 1024)

        col1, col2 = st.columns([5, 1.3])
        with col1:
            st.markdown(
                f"""
                <div class="history-item">
                    <div class="history-name">{zip_file.name}</div>
                    <div class="history-meta">{created_at} · {size_mb:.2f} MB</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col2:
            st.write("")
            with zip_file.open("rb") as f:
                st.download_button(
                    "Download",
                    data=f.read(),
                    file_name=zip_file.name,
                    mime="application/zip",
                    key=f"history_download_{idx}_{zip_file.name}",
                    use_container_width=True,
                )


def reset_current_session_data():
    """Reset current upload UI and remove the current temp job only."""
    current_job_dir = st.session_state.get("current_job_dir")

    if current_job_dir:
        try:
            shutil.rmtree(current_job_dir, ignore_errors=True)
        except Exception:
            pass

    st.session_state.current_job_dir = None
    st.session_state.uploader_key = f"uploader_{uuid.uuid4().hex[:8]}"


require_login()

st.set_page_config(page_title="Barcode / DataMatrix Generator", layout="wide")
inject_css()

cleanup_old_jobs(JOBS_DIR, max_age_hours=8)
cleanup_history()

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = "uploader_0"

if "current_job_dir" not in st.session_state:
    st.session_state.current_job_dir = None

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-logo">
            <img src="{COMPANY_LOGO_URL}" alt="Spring CC">
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.header("Cấu hình")
    make_svg = st.checkbox("Xuất SVG", value=True)
    make_eps = st.checkbox("Xuất EPS", value=True)
    make_pdf = st.checkbox("Xuất PDF", value=True)
    max_rows = st.number_input("Giới hạn dòng/lần", min_value=10, max_value=1000, value=300, step=50)

    st.divider()
    st.write("Font:")
    if FONT_PATH.exists():
        st.success("Đã thấy fonts/Arial.ttf")
    else:
        st.error("Thiếu fonts/Arial.ttf")

    st.divider()
    st.write("Storage:")
    st.caption(f"History: tối đa {HISTORY_MAX_FILES} ZIP / {HISTORY_MAX_HOURS} giờ")
    st.caption("Job tạm: xoá ngay sau khi tạo ZIP xong")

    st.divider()
    if st.button("Logout", use_container_width=True):
        reset_current_session_data()
        st.session_state.authenticated = False
        st.rerun()

st.markdown(
    f"""
    <div class="spring-hero">
        <div class="spring-logo-row">
            <img class="spring-logo" src="{COMPANY_LOGO_URL}" alt="Spring CC">
            <span class="spring-badge">Internal tool</span>
        </div>
        <h1 class="spring-title">Barcode / DataMatrix Generator</h1>
        <div class="spring-subtitle">
            Excel → SVG / EPS / PDF / ZIP · History lưu tối đa 3 file gần nhất trong 48 giờ
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_generate, tab_history = st.tabs(["Generate", "History"])


with tab_generate:
    action_col1, action_col2 = st.columns([1, 5])
    with action_col1:
        if st.button("Clear data", help="Xoá dữ liệu upload hiện tại và job tạm của phiên này. Không xoá History.", use_container_width=True):
            reset_current_session_data()
            st.rerun()

    uploaded = st.file_uploader(
        "Upload Excel",
        type=["xlsx", "xls"],
        key=st.session_state.uploader_key,
    )

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

        st.session_state.current_job_dir = str(job_dir)

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

        data = zip_path.read_bytes()
        history_path = save_zip_to_history(zip_path)

        try:
            shutil.rmtree(job_dir, ignore_errors=True)
        except Exception:
            pass
        st.session_state.current_job_dir = None

        if errors:
            st.error("Một số dòng generate lỗi:")
            st.code("\n".join(errors[:50]))
        else:
            st.success("Generate xong.")

        st.download_button(
            "Download ZIP",
            data=data,
            file_name=f"{batch_name}.zip",
            mime="application/zip",
            type="primary",
        )

        st.info(f"Đã lưu vào History: {history_path.name}. Job tạm đã được xoá.")
        st.caption("History chỉ giữ tối đa 3 ZIP gần nhất trong 48 giờ.")


with tab_history:
    render_history()
