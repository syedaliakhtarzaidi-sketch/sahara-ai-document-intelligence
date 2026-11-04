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
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
:root {--bg:#080F18;--panel:#101C29;--panel2:#142333;--line:#233849;--text:#E8F0F4;--muted:#91A4B3;--cyan:#65D9D0;--blue:#6AA8FF;--amber:#D8B875;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{background:radial-gradient(ellipse at 80% 0%,#14283A 0%,#080F18 48%);color:var(--text);}
.block-container{padding-top:1.25rem;padding-bottom:3rem;max-width:1500px;}
[data-testid="stSidebar"]{background:#0B1520;border-right:1px solid #1D3142;}
[data-testid="stSidebar"] *{color:#E6EFF3;}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:10px 12px;border-radius:9px;}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#172A3A;}
[data-testid="stSidebar"] hr{border-color:#263C4D;}
.brand-mark{font-family:'Space Grotesk',sans-serif;font-size:26px;font-weight:700;letter-spacing:3px;color:#F1F7F8;}
.brand-sub{font-size:9px;letter-spacing:2.1px;color:#6EDBD1;text-transform:uppercase;margin-top:-5px;}
.sidebar-note{background:linear-gradient(145deg,#132638,#101C29);border:1px solid #294355;border-radius:13px;padding:14px;color:#B8C9D2;font-size:11px;line-height:1.8;}
.hero{background:linear-gradient(112deg,#101E2C 0%,#142A3B 55%,#173D4B 100%);padding:29px 32px;border:1px solid #2A4657;border-radius:18px;color:#fff;margin:0 0 21px;box-shadow:0 18px 45px rgba(0,0,0,.2);position:relative;overflow:hidden;min-height:208px;}
.hero:before{content:"";position:absolute;width:230px;height:230px;right:55px;top:-12px;border-radius:50%;background:radial-gradient(circle at 45% 45%,rgba(101,217,208,.22),rgba(101,168,255,.08) 38%,transparent 68%);filter:blur(2px);}
.hero:after{content:"";position:absolute;width:170px;height:170px;right:85px;top:8px;border:1px solid rgba(101,217,208,.27);border-radius:50%;box-shadow:0 0 0 16px rgba(101,217,208,.035),0 0 0 34px rgba(101,217,208,.025),inset 0 0 25px rgba(101,217,208,.07);}
.hero-kicker{font-size:9px;letter-spacing:2.8px;text-transform:uppercase;color:#6EDBD1;margin-bottom:12px;position:relative;z-index:1;}
.hero h1{font-family:'Space Grotesk',sans-serif;font-size:35px;line-height:1.1;margin:0;color:#F2F7F9;font-weight:600;position:relative;z-index:1;}
.hero p{color:#AFC2CE;margin:11px 0 0;font-size:13px;max-width:690px;position:relative;z-index:1;}
.hero-tag{display:inline-flex;margin-top:18px;border:1px solid #3B6671;color:#A4E9E1;border-radius:6px;padding:6px 10px;font-size:9px;letter-spacing:1.4px;text-transform:uppercase;position:relative;z-index:1;}
.agent-chip{display:inline-flex;align-items:center;gap:7px;border:1px solid #315A61;background:#102B35;color:#9CE8DF;padding:6px 10px;border-radius:30px;font-size:9px;letter-spacing:1.2px;text-transform:uppercase;margin-bottom:16px;position:relative;z-index:1;}
.agent-dot{width:6px;height:6px;background:#65D9D0;border-radius:50%;box-shadow:0 0 9px #65D9D0;}
.section-head{display:flex;align-items:center;gap:10px;color:#DDE9EF;font-size:14px;font-weight:700;letter-spacing:.3px;margin:24px 0 12px;}
.section-no{font-family:'Space Grotesk',sans-serif;font-size:10px;color:#65D9D0;letter-spacing:1.4px;font-weight:700;}
.kpi{background:linear-gradient(145deg,#132333,#101B27);border:1px solid #263D4F;border-radius:13px;padding:16px 17px;min-height:104px;box-shadow:0 5px 20px rgba(0,0,0,.12);}
.kpi .v{font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:600;color:#EAF5F6;margin-top:7px;}
.kpi .l{font-size:9px;color:#7F9AAA;text-transform:uppercase;letter-spacing:1.6px;font-weight:700;}
.small-muted{color:#8FA4B1;font-size:10px;margin-top:4px;}
div[data-testid="stFileUploader"]{background:#101D2A;border:1px dashed #41616F;border-radius:14px;padding:13px;}
div[data-testid="stFileUploader"] section{background:transparent;}
.stButton>button,.stDownloadButton>button{border-radius:8px;font-weight:600;min-height:42px;border:1px solid #355166;background:#142638;color:#E8F0F4;}
.stButton>button[kind="primary"]{background:linear-gradient(100deg,#1C8D8B,#256E91);border:1px solid #3BAEAA;color:white;box-shadow:0 5px 18px rgba(38,156,157,.16);}
.stButton>button[kind="primary"]:hover{background:linear-gradient(100deg,#24A6A1,#2D83A9);border-color:#65D9D0;}
.stTextInput input,.stSelectbox div[data-baseweb="select"],.stTextArea textarea{border-radius:8px!important;background:#101D2A!important;color:#EAF2F5!important;border-color:#2B4355!important;}
.stTextInput label,.stSelectbox label,.stTextArea label,.stCheckbox label{color:#C2D0D8!important;}
div[data-testid="stExpander"]{background:#101D2A;border:1px solid #293F50;border-radius:11px;}
div[data-testid="stDataFrame"]{border:1px solid #294153;border-radius:11px;overflow:hidden;}
.stMarkdown,.stCaption{color:#C1CFD8;}
hr{border-color:#263B4D;}
[data-testid="stAlert"]{border-radius:10px;}
.footer-note{border-top:1px solid #24394A;margin-top:28px;padding-top:13px;color:#6F8796;font-size:9px;letter-spacing:1px;}

/* GLOBAL TEXT CONTRAST FIX */
.stApp,
.stApp p,
.stApp li,
.stApp span,
.stApp label,
.stApp small,
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] strong,
.stApp [data-testid="stCaptionContainer"],
.stApp .stCaption,
.stApp [data-testid="stExpander"] summary,
.stApp [data-testid="stExpander"] details,
.stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stFileUploader"] section,
.stApp [data-testid="stFileUploader"] small,
.stApp [data-testid="stRadio"] label,
.stApp [data-testid="stCheckbox"] label,
.stApp [data-testid="stSelectbox"] label,
.stApp [data-testid="stTextInput"] label,
.stApp [data-testid="stTextArea"] label,
.stApp [data-testid="stNumberInput"] label,
.stApp [data-testid="stDateInput"] label,
.stApp [data-testid="stMultiSelect"] label,
.stApp [data-testid="stDataFrame"],
.stApp [data-testid="stTable"] {
  color: #F1F5F8 !important;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
  color: #FFFFFF !important;
}
.stApp input, .stApp textarea,
.stApp [data-baseweb="select"] *,
.stApp [data-baseweb="input"] *,
.stApp [data-baseweb="textarea"] * {
  color: #FFFFFF !important;
  -webkit-text-fill-color: #FFFFFF !important;
}
.stApp input::placeholder, .stApp textarea::placeholder {
  color: #AFC0CC !important;
  -webkit-text-fill-color: #AFC0CC !important;
  opacity: 1 !important;
}
.stApp [data-testid="stDataFrame"] *,
.stApp [data-testid="stTable"] * {
  color: #F1F5F8 !important;
}
.stApp [data-baseweb="popover"] *,
.stApp [role="listbox"] *,
.stApp [role="option"] {
  color: #F1F5F8 !important;
}


/* DARKEN UPLOAD AND AI SETTINGS CONTROLS */
div[data-testid="stFileUploader"] button,
div[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"] {
  background: #142638 !important;
  color: #FFFFFF !important;
  border: 1px solid #3A586D !important;
  border-radius: 8px !important;
}
div[data-testid="stFileUploader"] button:hover,
div[data-testid="stFileUploader"] [data-testid="stBaseButton-secondary"]:hover {
  background: #1B3449 !important;
  border-color: #65D9D0 !important;
}
div[data-testid="stExpander"] > details > summary,
div[data-testid="stExpander"] > details > summary:hover {
  background: #142638 !important;
  color: #FFFFFF !important;
  border-radius: 9px !important;
}
div[data-testid="stExpander"] > details > summary * {
  color: #FFFFFF !important;
}

</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="brand-mark">SAHARA<span style="color:#65D9D0;">/</span>AI</div><div class="brand-sub">UK FOODS · AGENT CONSOLE</div>', unsafe_allow_html=True)
    st.write("")
    st.markdown("<div style='font-size:9px;letter-spacing:2px;color:#65D9D0;font-weight:700;'>NAVIGATION</div>", unsafe_allow_html=True)
    page = st.radio(" ", ["Shipment Analysis", "Shipment History", "System Guide"], label_visibility="collapsed")
    st.divider()
    st.markdown('<div class="sidebar-note"><b style="color:#65D9D0;letter-spacing:1px;">AGENT CAPABILITIES</b><br>01 &nbsp; Document recognition<br>02 &nbsp; Data extraction<br>03 &nbsp; Cross-file reasoning<br>04 &nbsp; Discrepancy reporting<br><br><span style="color:#91A4B3;">AI-assisted analysis. Final decisions remain with your team.</span></div>', unsafe_allow_html=True)
    st.write("")
    st.caption("CONTROLLED REVIEW ENVIRONMENT")

if page == "Shipment Analysis":
    st.markdown("""
    <div class="hero">
      <div class="agent-chip"><span class="agent-dot"></span> SAHARA AI AGENT &nbsp;·&nbsp; CONTROLLED MODE</div>
      <div class="hero-kicker">IMPORT OPERATIONS / INTELLIGENCE SYSTEM</div>
      <h1>Your shipment review agent.</h1>
      <p>Upload the paperwork. The agent reads each document, extracts shipment data, checks consistency across files and prepares a structured review for your approval.</p>
      <span class="hero-tag">Perception &nbsp; / &nbsp; Extraction &nbsp; / &nbsp; Verification</span>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown('<div class="kpi"><div class="l">Agent workflow</div><div class="v">03 stages</div><div class="small-muted">Read · compare · report</div></div>',unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="kpi"><div class="l">Input channel</div><div class="v">Multi-file</div><div class="small-muted">PDF and text documents</div></div>',unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="kpi"><div class="l">Decision authority</div><div class="v">Human</div><div class="small-muted">Review required before action</div></div>',unsafe_allow_html=True)

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
            import html
            status_filter = st.selectbox(
                "Filter findings by status",
                ["All findings", "MISMATCH", "MISSING", "REVIEW", "MATCH"],
                key="finding_status_filter"
            )
            visible_findings = findings if status_filter == "All findings" else [x for x in findings if x.get("status") == status_filter]
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'background:#101D2A;border:1px solid #294153;border-radius:10px;padding:11px 15px;'
                f'margin:5px 0 15px;color:#B9C9D3;font-size:12px;">'
                f'<span>SHOWING <b style="color:#FFFFFF;">{len(visible_findings)}</b> OF {len(findings)} CHECKS</span>'
                f'<span style="color:#65D9D0;">EVIDENCE-LED REVIEW</span></div>',
                unsafe_allow_html=True
            )
            status_styles = {
                "MATCH": ("#153B32", "#72D6A6", "✓"),
                "MISMATCH": ("#48252B", "#FF8992", "!"),
                "MISSING": ("#49391F", "#F2C36D", "—"),
                "REVIEW": ("#243A53", "#8FC4FF", "?")
            }
            for row_start in range(0, len(visible_findings), 2):
                card_cols = st.columns(2, gap="medium")
                for offset, col in enumerate(card_cols):
                    idx = row_start + offset
                    if idx >= len(visible_findings):
                        continue
                    item = visible_findings[idx]
                    status = item.get("status", "REVIEW")
                    bg, fg, symbol = status_styles.get(status, status_styles["REVIEW"])
                    field_name = html.escape(str(item.get("field", "Unlabelled field")))
                    values = html.escape(str(item.get("normalised_values") or "No value extracted"))
                    comment = html.escape(str(item.get("comment") or "No additional comment"))
                    with col:
                        st.markdown(
                            f'<div style="background:linear-gradient(145deg,#142536,#101B28);'
                            f'border:1px solid #2A4355;border-radius:13px;padding:16px 17px 14px;'
                            f'min-height:150px;margin-bottom:8px;">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">'
                            f'<div style="font-size:13px;font-weight:700;color:#F4F8FA;">{field_name}</div>'
                            f'<span style="white-space:nowrap;background:{bg};color:{fg};border:1px solid {fg}55;'
                            f'border-radius:20px;padding:4px 9px;font-size:9px;font-weight:800;letter-spacing:1px;">'
                            f'{symbol} &nbsp;{status}</span></div>'
                            f'<div style="font-size:9px;color:#8EA5B5;letter-spacing:1.3px;margin-top:15px;">'
                            f'EXTRACTED VALUE(S)</div>'
                            f'<div style="font-size:12px;line-height:1.6;color:#EAF2F5;margin-top:5px;'
                            f'overflow-wrap:anywhere;">{values}</div>'
                            f'<div style="border-top:1px solid #2A4051;margin-top:12px;padding-top:9px;'
                            f'font-size:11px;line-height:1.5;color:#B5C5CF;">{comment}</div></div>',
                            unsafe_allow_html=True
                        )
                        with st.expander("View document evidence", expanded=False):
                            st.write(item.get("evidence") or "No supporting document evidence was extracted.")
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
    st.markdown('<div class="hero"><div class="agent-chip"><span class="agent-dot"></span> AGENT MEMORY / LOCAL ARCHIVE</div><div class="hero-kicker">SAHARA AI · RECORDS</div><h1>Shipment history.</h1><p>Review previously processed shipments and revisit the records saved in this app environment.</p><span class="hero-tag">Review archive</span></div>',unsafe_allow_html=True)
    from engine import list_shipments
    history=list_shipments()
    if history:
        st.dataframe(pd.DataFrame(history),use_container_width=True,hide_index=True)
    else:
        st.info("No saved shipment reviews yet. Records are stored locally in the app database.")

else:
    st.markdown('<div class="hero"><div class="agent-chip"><span class="agent-dot"></span> SYSTEM KNOWLEDGE / REFERENCE</div><div class="hero-kicker">SAHARA AI · OPERATING PROTOCOL</div><h1>Agent operating guide.</h1><p>Understand how the agent reads, compares and reports shipment information — and where human review is required.</p><span class="hero-tag">Operating protocol</span></div>',unsafe_allow_html=True)
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
