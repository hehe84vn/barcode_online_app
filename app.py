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

JOBS_DIR = APP_DIR / ".tmp_jobs"
HISTORY_DIR = APP_DIR / ".history"
HISTORY_MAX_FILES = 3
HISTORY_MAX_HOURS = 48

REQUIRED_COLUMNS = ["Communication number", "EAN/UPC", "Product Version no."]
COMPANY_LOGO_URL = "https://spring-cc.com/_assets/v11/a04d764c1c5ecfe5a14652f59cc5c020ef497847.svg"
TEMPLATE_PATH = APP_DIR / "templates" / "barcode_template.xlsx"


TEXT = {
    "EN": {
        "app_title": "Barcode / DataMatrix Generator",
        "internal_tool": "Internal tool",
        "hero_subtitle": "Excel → SVG / EPS / PDF / ZIP · History keeps the latest 3 ZIP files for 48 hours",
        "login_caption": "Internal tool. Please login to continue.",
        "password": "Password",
        "login": "Login",
        "incorrect_password": "Incorrect password.",
        "settings": "Settings",
        "export_svg": "Export SVG",
        "export_eps": "Export EPS",
        "export_pdf": "Export PDF",
        "row_limit": "Rows per batch limit",
        "font": "Font:",
        "font_ok": "Found fonts/Arial.ttf",
        "font_missing": "Missing fonts/Arial.ttf",
        "storage": "Storage:",
        "history_storage": "History: max 3 ZIP / 48 hours",
        "temp_storage": "Temp jobs: deleted immediately after ZIP is created",
        "logout": "Logout",
        "language": "Language",
        "generate": "Generate",
        "history": "History",
        "clear_data": "Clear data",
        "clear_help": "Clear current upload and temp job for this session. History is not deleted.",
        "upload_excel": "Upload Excel",
        "upload_start": "Upload an Excel file to start.",
        "font_warning": "Please copy Arial.ttf into `fonts/Arial.ttf` before generating.",
        "excel_read_error": "Cannot read Excel",
        "missing_cols": "Missing required columns: ",
        "total_rows": "Total rows",
        "valid": "Valid",
        "preview": "Data preview",
        "invalid_warning": "There are {n} error rows. The app will generate only OK rows.",
        "too_many_rows": "The file has {n} rows, exceeding the {max_rows} rows/batch limit. Please split the batch or increase the limit if the server is strong enough.",
        "generate_zip": "Generate ZIP",
        "processing": "Processing {i}/{total}: {item}",
        "some_errors": "Some rows failed to generate:",
        "done": "Generation completed.",
        "download_zip": "Download ZIP",
        "history_saved": "Saved to History: {name}. Temp job has been deleted.",
        "history_caption": "History keeps the latest 3 ZIP files for 48 hours.",
        "history_desc": "Keeps up to 3 latest ZIP files for 48 hours. Files may be removed sooner if the app reboots/redeploys.",
        "history_empty": "No history files yet.",
        "download": "Download",
        "download_template": "Download Excel template",
        "template_missing": "Template file is missing: templates/barcode_template.xlsx",
        "no_comm": "Missing Communication number",
        "no_version": "Missing Product Version no.",
    },
    "VN": {
        "app_title": "Barcode / DataMatrix Generator",
        "internal_tool": "Công cụ nội bộ",
        "hero_subtitle": "Excel → SVG / EPS / PDF / ZIP · History lưu tối đa 3 file ZIP gần nhất trong 48 giờ",
        "login_caption": "Công cụ nội bộ. Vui lòng đăng nhập để tiếp tục.",
        "password": "Mật khẩu",
        "login": "Đăng nhập",
        "incorrect_password": "Sai mật khẩu.",
        "settings": "Cấu hình",
        "export_svg": "Xuất SVG",
        "export_eps": "Xuất EPS",
        "export_pdf": "Xuất PDF",
        "row_limit": "Giới hạn dòng/lần",
        "font": "Font:",
        "font_ok": "Đã thấy fonts/Arial.ttf",
        "font_missing": "Thiếu fonts/Arial.ttf",
        "storage": "Storage:",
        "history_storage": "History: tối đa 3 ZIP / 48 giờ",
        "temp_storage": "Job tạm: xoá ngay sau khi tạo ZIP xong",
        "logout": "Đăng xuất",
        "language": "Ngôn ngữ",
        "generate": "Generate",
        "history": "History",
        "clear_data": "Clear data",
        "clear_help": "Xoá dữ liệu upload hiện tại và job tạm của phiên này. Không xoá History.",
        "upload_excel": "Upload Excel",
        "upload_start": "Upload file Excel để bắt đầu.",
        "font_warning": "Vui lòng copy Arial.ttf vào thư mục `fonts/Arial.ttf` trước khi generate.",
        "excel_read_error": "Không đọc được Excel",
        "missing_cols": "Thiếu cột bắt buộc: ",
        "total_rows": "Tổng dòng",
        "valid": "Hợp lệ",
        "preview": "Preview dữ liệu",
        "invalid_warning": "Có {n} dòng lỗi. App chỉ generate các dòng OK.",
        "too_many_rows": "File có {n} dòng, vượt giới hạn {max_rows} dòng/lần. Hãy tách batch hoặc tăng giới hạn nếu server đủ mạnh.",
        "generate_zip": "Generate ZIP",
        "processing": "Đang xử lý {i}/{total}: {item}",
        "some_errors": "Một số dòng generate lỗi:",
        "done": "Generate xong.",
        "download_zip": "Download ZIP",
        "history_saved": "Đã lưu vào History: {name}. Job tạm đã được xoá.",
        "history_caption": "History chỉ giữ tối đa 3 ZIP gần nhất trong 48 giờ.",
        "history_desc": "Lưu tối đa 3 file ZIP gần nhất trong 48 giờ. Có thể mất sớm hơn nếu app reboot/redeploy.",
        "history_empty": "Chưa có file history.",
        "download": "Download",
        "download_template": "Tải file Excel mẫu",
        "template_missing": "Thiếu file mẫu: templates/barcode_template.xlsx",
        "no_comm": "Thiếu Communication number",
        "no_version": "Thiếu Product Version no.",
    },
}


def tr(key: str) -> str:
    lang = st.session_state.get("lang", "EN")
    return TEXT.get(lang, TEXT["EN"]).get(key, key)


def inject_css():
    st.markdown(
        """
        <style>
            :root {
                --spring-red: #ff3218;
                --spring-red-soft: #fff1ef;
                --spring-ink: #2e3142;
                --spring-muted: #777b8f;
                --spring-border: #ececf2;
                --spring-card: #ffffff;
            }

            .stApp {
                background:
                    radial-gradient(circle at 0% 0%, rgba(255, 50, 24, 0.08), transparent 28%),
                    linear-gradient(180deg, #ffffff 0%, #fbfbfd 100%);
            }

            section[data-testid="stSidebar"] {
                background: #f4f5f8;
                border-right: 1px solid var(--spring-border);
            }

            .block-container {
                max-width: 1240px;
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
                background: rgba(255,255,255,0.82);
                border: 1px solid var(--spring-border);
                border-radius: 26px;
                padding: 30px 34px;
                box-shadow: 0 18px 50px rgba(30,32,50,0.06);
                margin-bottom: 22px;
            }

            .spring-title {
                margin: 0;
                font-size: 44px;
                line-height: 1.06;
                letter-spacing: -0.045em;
                font-weight: 850;
                color: var(--spring-ink);
            }

            .spring-subtitle {
                margin-top: 14px;
                color: var(--spring-muted);
                font-size: 15px;
            }

            .spring-badge {
                display: inline-flex;
                align-items: center;
                border: 1px solid rgba(255, 50, 24, 0.22);
                background: var(--spring-red-soft);
                color: var(--spring-red);
                border-radius: 999px;
                padding: 7px 12px;
                font-size: 13px;
                font-weight: 800;
                white-space: nowrap;
                margin-bottom: 14px;
            }

            .spring-section-card {
                background: rgba(255,255,255,0.86);
                border: 1px solid var(--spring-border);
                border-radius: 22px;
                padding: 22px;
                box-shadow: 0 12px 34px rgba(30,32,50,0.05);
                margin-bottom: 18px;
            }

            div[data-testid="stForm"] {
                max-width: 520px;
                margin: 0 auto;
                padding: 20px 22px 18px;
                border-radius: 20px;
                border: 1px solid var(--spring-border);
                background: rgba(255,255,255,0.92);
                box-shadow: 0 12px 34px rgba(30,32,50,0.05);
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
                filter: brightness(0.92);
                border-color: var(--spring-red);
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
                color: var(--spring-red);
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
                margin: 6px 0 12px;
            }

            .sidebar-logo img {
                width: 260px;
                max-width: 100%;
                height: 36px;
                object-fit: contain;
            }

            .sidebar-divider {
                height: 1px;
                background: #dfe1e8;
                margin: 18px 0;
            }

            @media (max-width: 900px) {
                .spring-title {
                    font-size: 34px;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_app_password() -> str:
    """Read password from Streamlit Secrets only.

    Configure in Streamlit Cloud → App settings → Secrets:
    APP_PASSWORD = "your-password"
    """
    try:
        return str(st.secrets["APP_PASSWORD"])
    except Exception:
        return ""


def require_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "lang" not in st.session_state:
        st.session_state.lang = "EN"

    if st.session_state.authenticated:
        return

    st.set_page_config(page_title="Barcode / DataMatrix Generator", layout="centered")
    inject_css()

    st.markdown(
        f"""
        <div class="spring-section-card" style="max-width: 520px; margin: 48px auto 18px; text-align: center;">
            <img src="{COMPANY_LOGO_URL}" alt="Spring CC" style="width:330px; height:45px; object-fit:contain; margin-bottom: 18px;">
            <h1 style="font-size: 32px; margin-bottom: 6px;">Barcode / DataMatrix Generator</h1>
            <p style="color:#777b8f; margin-top: 0;">{tr("login_caption")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        password = st.text_input(tr("password"), type="password")
        submitted = st.form_submit_button(tr("login"), type="primary", use_container_width=True)

    if submitted:
        if password == get_app_password():
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error(tr("incorrect_password"))

    st.stop()


def cleanup_history():
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
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_path = HISTORY_DIR / zip_path.name

    if history_path.exists():
        history_path = HISTORY_DIR / f"{zip_path.stem}_{uuid.uuid4().hex[:4]}{zip_path.suffix}"

    shutil.copy2(zip_path, history_path)
    cleanup_history()
    return history_path


def render_history():
    cleanup_history()

    zip_files = [p for p in HISTORY_DIR.glob("*.zip") if p.is_file()]
    zip_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    st.markdown(
        f"""
        <div class="spring-section-card">
            <h2 style="margin-top:0;">{tr("history")}</h2>
            <p style="color:#777b8f; margin-bottom:0;">{tr("history_desc")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not zip_files:
        st.info(tr("history_empty"))
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
                    tr("download"),
                    data=f.read(),
                    file_name=zip_file.name,
                    mime="application/zip",
                    key=f"history_download_{idx}_{zip_file.name}",
                    use_container_width=True,
                )


def reset_current_session_data():
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

if "lang" not in st.session_state:
    st.session_state.lang = "EN"

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-logo">
            <img src="{COMPANY_LOGO_URL}" alt="Spring CC">
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(tr("logout"), use_container_width=True):
        reset_current_session_data()
        st.session_state.authenticated = False
        st.rerun()

    st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    st.radio(
        tr("language"),
        options=["EN", "VN"],
        index=0 if st.session_state.lang == "EN" else 1,
        key="lang",
        horizontal=True,
    )

    st.header(tr("settings"))
    make_svg = st.checkbox(tr("export_svg"), value=True)
    make_eps = st.checkbox(tr("export_eps"), value=True)
    make_pdf = st.checkbox(tr("export_pdf"), value=True)
    max_rows = st.number_input(tr("row_limit"), min_value=10, max_value=1000, value=300, step=50)

    st.divider()
    st.write(tr("font"))
    if FONT_PATH.exists():
        st.success(tr("font_ok"))
    else:
        st.error(tr("font_missing"))


st.markdown(
    f"""
    <div class="spring-hero">
        <span class="spring-badge">{tr("internal_tool")}</span>
        <h1 class="spring-title">{tr("app_title")}</h1>
        <div class="spring-subtitle">{tr("hero_subtitle")}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_generate, tab_history = st.tabs([tr("generate"), tr("history")])

with tab_generate:
    action_col1, action_col2 = st.columns([1, 5])
    with action_col1:
        if st.button(tr("clear_data"), help=tr("clear_help"), use_container_width=True):
            reset_current_session_data()
            st.rerun()

    st.markdown("#### " + tr("upload_excel"))

    template_col, upload_col = st.columns([1.4, 4])
    with template_col:
        if TEMPLATE_PATH.exists():
            with TEMPLATE_PATH.open("rb") as f:
                st.download_button(
                    tr("download_template"),
                    data=f.read(),
                    file_name="barcode_template.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        else:
            st.warning(tr("template_missing"))

    uploaded = st.file_uploader(
        tr("upload_excel"),
        type=["xlsx", "xls"],
        key=st.session_state.uploader_key,
        label_visibility="collapsed",
    )

    if uploaded is None:
        st.info(tr("upload_start"))
    else:
        if not FONT_PATH.exists():
            st.warning(tr("font_warning"))

        try:
            df = pd.read_excel(uploaded, dtype=str)
        except Exception as e:
            st.error(f"{tr('excel_read_error')}: {e}")
            st.stop()

        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            st.error(tr("missing_cols") + ", ".join(missing))
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
                ok, msg = False, tr("no_comm")
            if not str(r["Product Version no."]).strip():
                ok, msg = False, tr("no_version")
            statuses.append("OK" if ok else msg)
        work["Status"] = statuses

        valid = work[work["Status"] == "OK"].copy()
        invalid = work[work["Status"] != "OK"].copy()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(tr("total_rows"), len(work))
        c2.metric(tr("valid"), len(valid))
        c3.metric("EAN", int((valid["Type"] == "EAN").sum()))
        c4.metric("UPC", int((valid["Type"] == "UPC").sum()))

        if len(work) > max_rows:
            st.error(tr("too_many_rows").format(n=len(work), max_rows=max_rows))
            st.stop()

        with st.expander(tr("preview"), expanded=True):
            st.dataframe(work, use_container_width=True)

        if len(invalid):
            st.warning(tr("invalid_warning").format(n=len(invalid)))

        if len(valid) > 0:
            if st.button(tr("generate_zip"), type="primary", disabled=not FONT_PATH.exists()):
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
                    item = f"{row.communication}_{row.version}_{row.kind}"
                    try:
                        log.write(tr("processing").format(i=i, total=len(rows), item=item))
                        generate_row(row, batch_root, str(FONT_PATH), make_svg=make_svg, make_eps=make_eps, make_pdf=make_pdf)
                    except Exception as e:
                        errors.append(f"{item}: {e}")
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
                    st.error(tr("some_errors"))
                    st.code("\n".join(errors[:50]))
                else:
                    st.success(tr("done"))

                st.download_button(
                    tr("download_zip"),
                    data=data,
                    file_name=f"{batch_name}.zip",
                    mime="application/zip",
                    type="primary",
                )

                st.info(tr("history_saved").format(name=history_path.name))
                st.caption(tr("history_caption"))

with tab_history:
    render_history()
