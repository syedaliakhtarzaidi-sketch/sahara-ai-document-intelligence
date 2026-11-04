import streamlit as st
import pandas as pd
import json, os, re, sqlite3, hashlib, io, zipfile
from datetime import datetime
from pathlib import Path

from engine import (
    extract_document, verify_shipment, build_supplier_email,
    make_excel_report, make_pdf_report, save_shipment
)

st.set_page_config(
    page_title="Sahara AI | Document Intelligence",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

NAVY = "#102A43"
GOLD = "#C8A45D"
GREEN = "#39745B"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');
:root { --ink:#172D28; --forest:#173B32; --forest2:#245344; --gold:#B99A62; --muted:#718078; --paper:#F5F4EF; --line:#E5E4DC; }
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:var(--paper); color:var(--ink);}
.block-container {padding-top:1.35rem; padding-bottom:3rem; max-width:1480px;}
[data-testid="stSidebar"] {background:#142F29; border-right:1px solid #29473E;}
[data-testid="stSidebar"] * {color:#F4F2E9;}
[data-testid="stSidebar"] [data-testid="stRadio"] label {padding:9px 12px; border-radius:9px;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {background:#23483D;}
[data-testid="stSidebar"] hr {border-color:#35564B;}
.brand-mark {font-family:'Playfair Display',serif; font-size:27px; letter-spacing:2px; color:#F5F0E4; font-weight:700;}
.brand-sub {font-size:9px; letter-spacing:2.2px; color:#C6B58D; text-transform:uppercase; margin-top:-5px;}
.sidebar-note {background:#1E4036; border:1px solid #34584B; border-radius:12px; padding:13px; color:#D8E3DC; font-size:12px; line-height:1.6;}
.hero {background:linear-gradient(112deg,#142F29 0%,#1F4B3D 62%,#315B49 100%); padding:31px 34px; border-radius:19px; color:#fff; margin:0 0 22px 0; box-shadow:0 12px 30px rgba(20,47,41,.12); position:relative; overflow:hidden;}
.hero:after {content:""; position:absolute; width:250px; height:250px; right:-70px; top:-120px; border:1px solid rgba(205,181,130,.28); border-radius:50%; box-shadow:0 0 0 24px rgba(205,181,130,.04),0 0 0 48px rgba(205,181,130,.035);}
.hero-kicker {font-size:10px; letter-spacing:2.6px; text-transform:uppercase; color:#D7C49A; margin-bottom:10px;}
.hero h1 {font-family:'Playfair Display',serif; font-size:36px; line-height:1.12; margin:0; color:#FFFDF7; font-weight:600;}
.hero p {color:#D6E2DB; margin:10px 0 0 0; font-size:13px; max-width:760px;}
.hero-tag {display:inline-block; margin-top:19px; border:1px solid rgba(220,202,159,.45); color:#E6D8B8; border-radius:30px; padding:6px 11px; font-size:10px; letter-spacing:1px; text-transform:uppercase;}
.section-head {display:flex; align-items:center; gap:10px; color:#1C3A31; font-size:15px; font-weight:700; letter-spacing:.2px; margin:24px 0 12px;}
.section-no {font-size:10px; color:#A1844D; letter-spacing:1.5px; font-weight:700;}
.kpi {background:#FFFEFA; border:1px solid var(--line); border-radius:15px; padding:17px 18px; min-height:105px; box-shadow:0 3px 12px rgba(27,48,39,.025);}
.kpi .v {font-family:'Playfair Display',serif; font-size:25px; font-weight:600; color:#1A3B31; margin-top:5px;}
.kpi .l {font-size:9px; color:#8A918A; text-transform:uppercase; letter-spacing:1.5px; font-weight:700;}
.small-muted {color:#7C887F; font-size:11px; margin-top:3px;}
div[data-testid="stFileUploader"] {background:#FFFEFA; border:1px dashed #B9B49F; border-radius:15px; padding:13px;}
div[data-testid="stFileUploader"] section {background:transparent;}
.stButton>button, .stDownloadButton>button {border-radius:10px; font-weight:600; min-height:42px; border:1px solid #D8D8CE;}
.stButton>button[kind="primary"] {background:#1D493B; border:1px solid #1D493B; color:#fff;}
.stButton>button[kind="primary"]:hover {background:#2B5B49; border-color:#2B5B49;}
.stTextInput input, .stSelectbox div[data-baseweb="select"], .stTextArea textarea {border-radius:9px!important; background:#FFFEFA!important;}
div[data-testid="stExpander"] {background:#FFFEFA; border:1px solid var(--line); border-radius:12px;}
div[data-testid="stDataFrame"] {border:1px solid var(--line); border-radius:12px; overflow:hidden;}
hr {border-color:#E2E1D8;}
.caption-line {font-size:11px; color:#7C887F; line-height:1.6;}
.result-banner {padding:13px 16px; border-radius:12px; background:#F0EEE5; border:1px solid #E4DFD0; color:#49584F; font-size:12px;}
.footer-note {border-top:1px solid #E2E1D8; margin-top:28px; padding-top:13px; color:#89928A; font-size:10px; letter-spacing:.3px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand-mark">SAHARA</div><div class="brand-sub">UK FOODS · INTELLIGENCE</div>', unsafe_allow_html=True)
    st.write("")
    st.markdown("<div style='font-size:9px;letter-spacing:2px;color:#BBA778;font-weight:700;'>WORKSPACE</div>", unsafe_allow_html=True)
    page = st.radio(" ", ["Shipment Analysis", "Shipment History", "System Guide"], label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="sidebar-note"><b style="color:#E2C995;">DOCUMENT INTELLIGENCE</b><br>Recognition<br>Extraction<br>Cross-document verification<br><br><span style="color:#AFC2B7;">Human approval remains essential before customs or supplier action.</span></div>', unsafe_allow_html=True)
    st.write("")
    st.caption("SAHARA · PRIVATE WORKSPACE")

if page == "Shipment Analysis":
    st.markdown("""
    <div class="hero">
      <div class="hero-kicker">SAHARA UK FOODS · IMPORT OPERATIONS</div>
      <h1>Document Intelligence</h1>
      <p>A considered review of your shipment paperwork — from document extraction to cross-document consistency and supplier follow-up.</p>
      <span class="hero-tag">Import document review suite</span>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown('<div class="kpi"><div class="l">Review workflow</div><div class="v">01 — 06</div><div class="small-muted">Upload to final report</div></div>',unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="kpi"><div class="l">Supported input</div><div class="v">PDF / TXT</div><div class="small-muted">Multiple files per shipment</div></div>',unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="kpi"><div class="l">Decision control</div><div class="v">Human-led</div><div class="small-muted">No automatic email or customs filing</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="section-head"><span class="section-no">01</span> Shipment reference</div>',unsafe_allow_html=True)
    a,b = st.columns([2,1])
    with a:
        shipment_ref = st.text_input("Shipment / container / BL reference", placeholder="e.g. TGHU1234567 or BL number")
    with b:
        supplier = st.text_input("Supplier", placeholder="Supplier name")
    st.markdown('<div class="section-head"><span class="section-no">02</span> Document intake</div>',unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload shipment documents", type=["pdf","txt"], accept_multiple_files=True,
                                help="Upload one merged PDF or several individual documents. Scanned PDFs are processed through OCR when configured.")
    st.caption("Accepted: Bill of Lading, invoice, packing list, COO, EUR.1, phytosanitary, fumigation, allergen, organic COI and supporting documents.")

    with st.expander("AI connection and processing settings", expanded=not bool(os.getenv("OPENAI_API_KEY"))):
        try:
            configured_api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        except Exception:
            configured_api_key = os.getenv("OPENAI_API_KEY", "")
        api_key = st.text_input("OpenAI API key", type="password", value=configured_api_key, help="Loaded from Streamlit Secrets or environment variables.")
        model = st.selectbox("Analysis model", ["gpt-4.1","gpt-4.1-mini"], index=1)
        st.caption("Without an API key, the app can still extract selectable PDF text and produce a basic evidence inventory, but AI classification and reasoning will be disabled.")
        include_page_images = st.checkbox("Use vision analysis for scanned / image-based PDF pages", value=True)

    run = st.button("Analyse shipment documents", type="primary", disabled=not uploaded, use_container_width=True)

    if run:
        st.session_state.pop("analysis_result",None)
        all_docs=[]
        progress=st.progress(0, text="Preparing documents…")
        status=st.empty()
        for i,f in enumerate(uploaded):
            status.write(f"Reading {f.name}…")
            result = extract_document(f.name, f.getvalue(), api_key=api_key, model=model, use_vision=include_page_images)
            all_docs.append(result)
            progress.progress((i+1)/max(1,len(uploaded)), text=f"Processed {i+1} of {len(uploaded)}")
        status.write("Comparing extracted shipment data…")
        verification = verify_shipment(all_docs)
        verification["shipment_reference"] = shipment_ref.strip()
        verification["supplier"] = supplier.strip()
        verification["created_at"] = datetime.utcnow().isoformat(timespec="seconds")+"Z"
        verification["documents"] = all_docs
        st.session_state.analysis_result=verification
        save_shipment(verification)
        progress.empty()
        status.success("Document review completed. Check every finding against the original documents before acting.")

    result=st.session_state.get("analysis_result")
    if result:
        st.divider()
        findings=result.get("findings",[])
        summary=result.get("summary",{})
        total=len(findings)
        mismatch=sum(1 for x in findings if x.get("status")=="MISMATCH")
        missing=sum(1 for x in findings if x.get("status")=="MISSING")
        review=sum(1 for x in findings if x.get("status")=="REVIEW")
        matched=sum(1 for x in findings if x.get("status")=="MATCH")
        st.markdown('<div class="section-head"><span class="section-no">03</span> Verification overview</div>',unsafe_allow_html=True)
        x1,x2,x3,x4=st.columns(4)
        for col,label,value in [(x1,"MISMATCH",mismatch),(x2,"MISSING",missing),(x3,"REVIEW",review),(x4,"MATCH",matched)]:
            with col:
                st.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div></div>',unsafe_allow_html=True)
        if mismatch or missing:
            st.error("Discrepancies or missing information found. Do not approve shipment documents until reviewed.")
        elif review:
            st.warning("Some items require human review. No clean approval should be inferred.")
        else:
            st.success("No material discrepancy was detected in the fields that could be compared. This is not a customs clearance approval.")

        st.markdown('<div class="section-head"><span class="section-no">04</span> Cross-document findings</div>',unsafe_allow_html=True)
        if findings:
            df=pd.DataFrame(findings)
            preferred=["field","status","normalised_values","evidence","comment"]
            df=df[[x for x in preferred if x in df.columns]]
            st.dataframe(df,use_container_width=True,hide_index=True)
        else:
            st.info("No comparable fields were extracted. Check the document extraction section and API/OCR configuration.")

        st.markdown('<div class="section-head"><span class="section-no">05</span> Extracted document details</div>',unsafe_allow_html=True)
        for doc in result.get("documents",[]):
            with st.expander(f"{doc.get('document_type','Unknown')} · {doc.get('filename','')}", expanded=False):
                st.write("**Classification confidence:**",doc.get("classification_confidence","Not provided"))
                st.write("**Pages / text evidence:**",doc.get("page_count",0))
                st.json(doc.get("data",{}))
                if doc.get("warnings"):
                    st.warning(" · ".join(doc["warnings"]))

        st.markdown('<div class="section-head"><span class="section-no">06</span> Supplier follow-up draft</div>',unsafe_allow_html=True)
        email=build_supplier_email(result)
        st.text_area("Draft only — review before sending",value=email,height=260)
        st.download_button("Download supplier email (.txt)",email.encode("utf-8"),file_name="sahara_supplier_discrepancy_email.txt")
        st.markdown('<div class="section-head"><span class="section-no">07</span> Export review reports</div>',unsafe_allow_html=True)
        ex1,ex2=st.columns(2)
        with ex1:
            xlsx=make_excel_report(result)
            st.download_button("Download Excel verification report",xlsx,file_name="sahara_shipment_verification.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
        with ex2:
            pdf=make_pdf_report(result)
            st.download_button("Download PDF verification report",pdf,file_name="sahara_shipment_verification.pdf",mime="application/pdf",use_container_width=True)

elif page == "Shipment History":
    st.markdown('<div class="hero"><div class="hero-kicker">SAHARA UK FOODS · RECORDS</div><h1>Shipment History</h1><p>Previously analysed shipment reviews stored in this app environment.</p><span class="hero-tag">Review archive</span></div>',unsafe_allow_html=True)
    from engine import list_shipments
    history=list_shipments()
    if history:
        st.dataframe(pd.DataFrame(history),use_container_width=True,hide_index=True)
    else:
        st.info("No saved shipment reviews yet. Records are stored locally in the app database.")

else:
    st.markdown('<div class="hero"><div class="hero-kicker">SAHARA UK FOODS · REFERENCE</div><h1>System Guide</h1><p>A clear guide to the document review workflow, decision statuses and operational safeguards.</p><span class="hero-tag">How the system works</span></div>',unsafe_allow_html=True)
    st.markdown("""
### Review sequence
1. Upload one merged PDF or multiple individual PDF/TXT documents.
2. The system attempts to identify document types and extract key shipment fields.
3. Extracted values are compared across documents using normalised values and conservative matching.
4. Findings are marked **MATCH**, **MISMATCH**, **MISSING**, or **REVIEW**.
5. A supplier email draft and downloadable Excel/PDF reports are generated.

### Important controls
- A missing document is not automatically a legal breach. Certificate requirements depend on product, origin, commodity code, route and current UK rules.
- The app does not authenticate a certificate with the issuing authority.
- AI extraction may misread scans, stamps, handwriting, tables or poor-quality copies.
- Always open the cited original page before deciding.
- Never use this report as a customs clearance decision or legal/regulatory sign-off.
- Supplier emails are drafts only. Nothing is sent automatically.

### Deployment configuration
Set `OPENAI_API_KEY` as a server secret. For scanned PDFs, vision analysis is used when enabled and an API key is configured. Persistent records use SQLite in the app's writable data directory; for multi-user production deployment, replace this with managed PostgreSQL and private object storage.
""")


st.markdown('<div class="footer-note">SAHARA UK FOODS &nbsp;·&nbsp; DOCUMENT INTELLIGENCE &nbsp;·&nbsp; INTERNAL REVIEW TOOL</div>', unsafe_allow_html=True)
