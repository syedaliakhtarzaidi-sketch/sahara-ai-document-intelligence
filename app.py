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
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;}
.stApp {background:#F4F6F5;}
.block-container {padding-top:1.6rem; max-width:1500px;}
.hero {background:linear-gradient(115deg,#102A43,#1E4B4B);padding:28px 32px;border-radius:18px;color:white;margin-bottom:22px;}
.hero h1 {font-family:'Playfair Display',serif;font-size:34px;margin:0;color:white;}
.hero p {color:#D9E5E1;margin:8px 0 0 0;}
.kpi {background:white;border:1px solid #E3E9E6;border-radius:14px;padding:16px 18px;}
.kpi .v {font-size:26px;font-weight:700;color:#102A43;}
.kpi .l {font-size:12px;color:#687985;text-transform:uppercase;letter-spacing:.08em;}
.section {font-size:19px;font-weight:700;color:#102A43;margin:18px 0 10px 0;}
div[data-testid="stFileUploader"] {background:white;border:1px dashed #B7C8C0;border-radius:14px;padding:14px;}
.stButton>button {border-radius:9px;font-weight:600;}
.small-muted {color:#718096;font-size:12px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🌿 SAHARA")
    st.caption("UK FOODS · INTELLIGENCE SUITE")
    page = st.radio("WORKSPACE", ["Shipment Analysis", "Shipment History", "System Guide"])
    st.divider()
    st.caption("DOCUMENT INTELLIGENCE")
    st.markdown("**Recognition · Extraction · Verification**")
    st.caption("Human approval remains mandatory for customs and supplier actions.")

if page == "Shipment Analysis":
    st.markdown("""
    <div class="hero">
      <h1>Document Intelligence</h1>
      <p>AI-powered shipment document review · Cross-document verification · Supplier discrepancy drafting</p>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown('<div class="kpi"><div class="l">Review workflow</div><div class="v">01 — 06</div><div class="small-muted">Upload to final report</div></div>',unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="kpi"><div class="l">Supported input</div><div class="v">PDF / TXT</div><div class="small-muted">Multiple files per shipment</div></div>',unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="kpi"><div class="l">Decision control</div><div class="v">Human-led</div><div class="small-muted">No automatic email or customs filing</div></div>',unsafe_allow_html=True)

    st.markdown('<div class="section">01 · Shipment reference</div>',unsafe_allow_html=True)
    a,b = st.columns([2,1])
    with a:
        shipment_ref = st.text_input("Shipment / container / BL reference", placeholder="e.g. TGHU1234567 or BL number")
    with b:
        supplier = st.text_input("Supplier", placeholder="Supplier name")
    uploaded = st.file_uploader("02 · Upload all shipment documents", type=["pdf","txt"], accept_multiple_files=True,
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
        st.markdown('<div class="section">03 · Verification overview</div>',unsafe_allow_html=True)
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

        st.markdown('<div class="section">04 · Cross-document findings</div>',unsafe_allow_html=True)
        if findings:
            df=pd.DataFrame(findings)
            preferred=["field","status","normalised_values","evidence","comment"]
            df=df[[x for x in preferred if x in df.columns]]
            st.dataframe(df,use_container_width=True,hide_index=True)
        else:
            st.info("No comparable fields were extracted. Check the document extraction section and API/OCR configuration.")

        st.markdown('<div class="section">05 · Document intelligence</div>',unsafe_allow_html=True)
        for doc in result.get("documents",[]):
            with st.expander(f"{doc.get('document_type','Unknown')} · {doc.get('filename','')}", expanded=False):
                st.write("**Classification confidence:**",doc.get("classification_confidence","Not provided"))
                st.write("**Pages / text evidence:**",doc.get("page_count",0))
                st.json(doc.get("data",{}))
                if doc.get("warnings"):
                    st.warning(" · ".join(doc["warnings"]))

        st.markdown('<div class="section">06 · Supplier discrepancy email</div>',unsafe_allow_html=True)
        email=build_supplier_email(result)
        st.text_area("Draft only — review before sending",value=email,height=260)
        st.download_button("Download supplier email (.txt)",email.encode("utf-8"),file_name="sahara_supplier_discrepancy_email.txt")
        st.markdown('<div class="section">07 · Export reports</div>',unsafe_allow_html=True)
        ex1,ex2=st.columns(2)
        with ex1:
            xlsx=make_excel_report(result)
            st.download_button("Download Excel verification report",xlsx,file_name="sahara_shipment_verification.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
        with ex2:
            pdf=make_pdf_report(result)
            st.download_button("Download PDF verification report",pdf,file_name="sahara_shipment_verification.pdf",mime="application/pdf",use_container_width=True)

elif page == "Shipment History":
    st.markdown('<div class="hero"><h1>Shipment History</h1><p>Previously analysed shipment records stored in this app environment</p></div>',unsafe_allow_html=True)
    from engine import list_shipments
    history=list_shipments()
    if history:
        st.dataframe(pd.DataFrame(history),use_container_width=True,hide_index=True)
    else:
        st.info("No saved shipment reviews yet. Records are stored locally in the app database.")

else:
    st.markdown('<div class="hero"><h1>System Guide</h1><p>How Sahara AI Document Intelligence reviews import documents</p></div>',unsafe_allow_html=True)
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
