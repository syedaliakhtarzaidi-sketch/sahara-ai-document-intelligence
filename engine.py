import os, re, io, json, sqlite3, hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime

DB_PATH = os.getenv("SAHARA_DB_PATH","sahara_shipments.db")

FIELDS = [
    "container_number","seal_number","bl_number","invoice_number","lot_numbers",
    "supplier_exporter","consignee_importer","notify_party","product_description",
    "hs_code","country_of_origin","port_of_loading","port_of_discharge",
    "vessel","voyage","shipment_date","invoice_date","incoterms","currency",
    "cartons_packages","pallet_count","net_weight","gross_weight","container_size",
    "container_type","temperature","loading_method","production_date","expiry_date",
    "certificate_number","certificate_issue_date","certificate_valid_until"
]

SYSTEM_PROMPT = """You are Sahara UK Foods' import-document review analyst. Read the supplied document text and, if provided, page images. Identify document type and extract only facts explicitly visible. Never guess. Return valid JSON only with this schema:
{
 "document_type":"Bill of Lading|Commercial Invoice|Packing List|Certificate of Origin|EUR.1|Phytosanitary Certificate|Fumigation Certificate|Allergen Certificate|Organic COI|Other|Unknown",
 "classification_confidence":"high|medium|low",
 "page_count": integer,
 "data": {
  "container_number":null,"seal_number":null,"bl_number":null,"invoice_number":null,
  "lot_numbers":[],"supplier_exporter":null,"consignee_importer":null,"notify_party":null,
  "product_description":null,"hs_code":null,"country_of_origin":null,
  "port_of_loading":null,"port_of_discharge":null,"vessel":null,"voyage":null,
  "shipment_date":null,"invoice_date":null,"incoterms":null,"currency":null,
  "cartons_packages":null,"pallet_count":null,"net_weight":null,"gross_weight":null,
  "container_size":null,"container_type":null,"temperature":null,"loading_method":null,
  "production_date":null,"expiry_date":null,"certificate_number":null,
  "certificate_issue_date":null,"certificate_valid_until":null
 },
 "evidence":[{"field":"field_name","value":"exact visible value","page":1,"quote":"short verbatim excerpt"}],
 "warnings":["uncertain, illegible, absent or conflicting interpretation notes"]
}
Use null for absent values, [] for absent lists. Treat form instructions, printed guidance, checkboxes, labels, section headings and boilerplate as NOT data. Never use words such as ATTACHED, FINAL, WEIGHT, VOY., NAME & ADDRESS, GOODS, or generic form prompts as extracted values. For every non-null field, provide evidence quote that contains the value or clearly identifies the labelled field. Do not infer palletization from the fact that a container is dry. Container type: dry/reefer only when explicit evidence. Loading method: palletized only when pallets explicitly shown; handball only when explicitly stated; otherwise null. Keep units in weight strings. Preserve source language if necessary. If a value is uncertain, use null and explain in warnings."""

def _pdf_text_and_images(data, use_vision=True):
    pages=[]
    try:
        import fitz
        pdf=fitz.open(stream=data,filetype="pdf")
        for i,p in enumerate(pdf):
            txt=p.get_text("text").strip()
            img=None
            if use_vision and len(txt)<80:
                pix=p.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                img=pix.tobytes("png")
            pages.append({"page":i+1,"text":txt,"image":img})
        return pages
    except Exception as e:
        return [{"page":1,"text":"","image":None,"error":str(e)}]

def _call_openai(prompt, api_key, model, image_bytes=None):
    from openai import OpenAI
    client=OpenAI(api_key=api_key)
    content=[{"type":"text","text":prompt}]
    if image_bytes:
        import base64
        content.append({"type":"image_url","image_url":{"url":"data:image/png;base64,"+base64.b64encode(image_bytes).decode()}})
    response=client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type":"json_object"},
        messages=[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":content}]
    )
    return json.loads(response.choices[0].message.content)

def _clean_value(field, value):
    """Reject obvious form boilerplate and heading fragments."""
    if value is None:
        return None
    if isinstance(value, list):
        cleaned=[_clean_value(field,x) for x in value]
        return [x for x in cleaned if x] or []
    value=re.sub(r"\s+"," ",str(value)).strip(" \t\r\n:;,-")
    if not value:
        return None
    upper=value.upper().strip(" .:")
    junk={
      "ATTACHED","FINAL","WEIGHT","VOY.","VOY","GOODS","OF GOODS",
      "NAME & ADDRESS","NAME AND ADDRESS","S' DANGEROUS GOODS / HAZMAT OR OTHER",
      "DANGEROUS GOODS / HAZMAT OR OTHER","NOT APPLICABLE","N/A","NIL",
      "DESCRIPTION","SHIPPER","CONSIGNEE","EXPORTER","IMPORTER","SUPPLIER",
      "PORT OF LOADING","PORT OF DISCHARGE","COUNTRY OF ORIGIN",
      "COMMERCIAL INVOICE","PACKING LIST","BILL OF LADING"
    }
    if upper in junk or len(upper)<2:
        return None
    if field in ("bl_number","invoice_number","certificate_number") and upper in {"ATTACHED","ENCLOSED","AS ATTACHED","SEE ATTACHED"}:
        return None
    if field in ("supplier_exporter","consignee_importer","notify_party","product_description","port_of_loading","port_of_discharge","vessel","voyage"):
        if upper in {"VOY","VOY.","FINAL","WEIGHT","GOODS","OF GOODS","NAME & ADDRESS"}:
            return None
    return value

def _basic_extract(filename, pages):
    text="\n".join(x.get("text","") for x in pages)
    data={k:None for k in FIELDS}; evidence=[]
    # Patterns require a clear label/value relationship; avoid generic table headings.
    patterns={
      "container_number":r"\b[A-Z]{4}\s?\d{7}\b",
      "seal_number":r"(?im)^\s*(?:CONTAINER\s+)?SEAL(?:\s*(?:NO|NUMBER))?\s*[:#-]\s*([A-Z0-9/-]{5,})\s*$",
      "bl_number":r"(?im)^\s*(?:B\s*/\s*L|BILL\s+OF\s+LADING)\s*(?:NO\.?|NUMBER|#)\s*[:#-]\s*([A-Z0-9/-]{5,})\s*$",
      "invoice_number":r"(?im)^\s*(?:COMMERCIAL\s+)?INVOICE\s*(?:NO\.?|NUMBER|#)\s*[:#-]\s*([A-Z0-9/-]{3,})\s*$",
      "hs_code":r"(?im)^\s*(?:HS(?:\s*CODE)?|HARMONI[ZS]ED\s+CODE|COMMODITY\s+CODE)\s*[:#-]\s*([0-9.]{6,12})\s*$",
      "country_of_origin":r"(?im)^\s*(?:COUNTRY\s+OF\s+ORIGIN|ORIGIN\s+OF\s+GOODS)\s*[:#-]\s*([A-Z][A-Z ,()-]{2,45})\s*$",
      "port_of_loading":r"(?im)^\s*PORT\s+OF\s+LOADING\s*[:#-]\s*([A-Z][A-Z ,()-]{2,55})\s*$",
      "port_of_discharge":r"(?im)^\s*PORT\s+OF\s+DISCHARGE\s*[:#-]\s*([A-Z][A-Z ,()-]{2,55})\s*$",
      "vessel":r"(?im)^\s*(?:VESSEL(?:\s+NAME)?|SHIP\s+NAME)\s*[:#-]\s*([A-Z0-9][A-Z0-9 .'-]{2,50})\s*$",
      "voyage":r"(?im)^\s*VOYAGE(?:\s+NO\.?)?\s*[:#-]\s*([A-Z0-9/-]{2,20})\s*$",
      "cartons_packages":r"(?im)^\s*(?:TOTAL\s+)?(?:NO\.?\s+OF\s+)?(?:CARTONS|PACKAGES|PKGS|CASES)\s*[:#-]\s*([0-9,]+(?:\s*(?:CARTONS|PACKAGES|PKGS|CASES))?)\s*$",
      "net_weight":r"(?im)^\s*(?:NET\s+WEIGHT|N\.?\s*W\.?)\s*[:#-]\s*([0-9,.]+\s*(?:KG|KGS|MT|TONS?)?)\s*$",
      "gross_weight":r"(?im)^\s*(?:GROSS\s+WEIGHT|G\.?\s*W\.?)\s*[:#-]\s*([0-9,.]+\s*(?:KG|KGS|MT|TONS?)?)\s*$",
      "product_description":r"(?im)^\s*(?:DESCRIPTION\s+OF\s+GOODS|PRODUCT\s+DESCRIPTION|GOODS\s+DESCRIPTION)\s*[:#-]\s*([^\n]{4,120})$",
      "supplier_exporter":r"(?im)^\s*(?:EXPORTER|SHIPPER|SELLER|SUPPLIER)\s*[:#-]\s*([^\n]{4,120})$",
      "consignee_importer":r"(?im)^\s*(?:CONSIGNEE|IMPORTER|BUYER)\s*[:#-]\s*([^\n]{4,120})$",
      "lot_numbers":r"(?im)^\s*(?:LOT|BATCH)\s*(?:NO\.?|NUMBER|#)\s*[:#-]\s*([A-Z0-9, /-]{3,60})\s*$"
    }
    for field,pat in patterns.items():
        m=re.search(pat,text,re.I|re.M)
        if m:
            val=_clean_value(field,m.group(1) if m.lastindex else m.group(0))
            if val:
                data[field]=val
                evidence.append({"field":field,"value":val,"page":1,"quote":m.group(0)[:160]})

    # Container IDs are distinctive, but do not accept a value embedded in an unrelated example.
    m=re.search(r"(?i)(?:container(?:\s*(?:no|number))?\s*[:#-]?\s*)([A-Z]{4}\s?\d{7})",text)
    if m:
        val=m.group(1).replace(" ","").upper()
        data["container_number"]=val
        evidence.append({"field":"container_number","value":val,"page":1,"quote":m.group(0)[:160]})

    name=Path(filename).stem.lower().replace("_"," ").replace("-"," ")
    if "invoice" in name: dtype="Commercial Invoice"
    elif "packing" in name or re.search(r"\b(pkl|pack list)\b",name): dtype="Packing List"
    elif "bill of lading" in name or re.search(r"\b(bl|bol)\b",name): dtype="Bill of Lading"
    elif "origin" in name or "coo" in name: dtype="Certificate of Origin"
    elif "health" in name: dtype="Health Certificate"
    elif "phyto" in name: dtype="Phytosanitary Certificate"
    elif "fumigation" in name: dtype="Fumigation Certificate"
    elif "eur1" in name or "eur 1" in name: dtype="EUR.1"
    else:
        head=text[:8000].lower()
        if "bill of lading" in head or ("shipper" in head and "notify party" in head): dtype="Bill of Lading"
        elif "packing list" in head: dtype="Packing List"
        elif "commercial invoice" in head or re.search(r"\binvoice\b",head): dtype="Commercial Invoice"
        elif "certificate of origin" in head: dtype="Certificate of Origin"
        elif "health certificate" in head: dtype="Health Certificate"
        else: dtype="Unknown"

    chars=len(text.strip())
    warnings=[]
    if chars < 80:
        warnings.append("No selectable PDF text was found. This is likely a scanned PDF. Enable Vision and configure a valid OpenAI API key for image reading.")
    else:
        warnings.append(f"Fallback text extraction used ({chars} characters). Full AI extraction was unavailable; check the OpenAI key, model access and API error below.")
    return {"document_type":dtype,"classification_confidence":"medium" if dtype!="Unknown" else "low",
            "page_count":len(pages),"data":data,"evidence":evidence,"warnings":warnings,
            "text_characters":chars}

def extract_document(filename, raw, api_key="", model="gpt-4.1-mini", use_vision=True):
    ext=Path(filename).suffix.lower()
    if ext==".txt":
        text=raw.decode("utf-8",errors="replace")
        pages=[{"page":1,"text":text,"image":None}]
    elif ext==".pdf":
        pages=_pdf_text_and_images(raw,use_vision)
    else:
        return {"filename":filename,"document_type":"Unknown","data":{},"warnings":["Unsupported file type."]}
    if not api_key:
        result=_basic_extract(filename,pages)
    else:
        try:
            combined=[]
            image_candidates=[]
            for p in pages:
                if p["text"]:
                    combined.append(f"\n[PAGE {p['page']}]\n"+p["text"][:12000])
                if p.get("image") is not None:
                    image_candidates.append(p)
            prompt=f"Filename: {filename}\nDocument pages and selectable text:\n{''.join(combined)[:50000]}\nExtract this single document. Page numbering starts at 1."
            # Send at most 6 scanned pages per request to bound cost.
            if image_candidates:
                results=[]
                for p in image_candidates[:6]:
                    part=_call_openai(prompt+f"\nAlso inspect image of page {p['page']}.",api_key,model,p["image"])
                    results.append(part)
                result=results[0]
                for extra in results[1:]:
                    for ev in extra.get("evidence",[]):
                        if ev not in result.setdefault("evidence",[]): result["evidence"].append(ev)
                    for k,v in extra.get("data",{}).items():
                        if not result.get("data",{}).get(k) and v: result["data"][k]=v
                    result.setdefault("warnings",[]).extend(extra.get("warnings",[]))
            else:
                result=_call_openai(prompt,api_key,model)
        except Exception as e:
            result=_basic_extract(filename,pages)
            result["warnings"].append("AI processing error: "+str(e)[:300])
    result["filename"]=filename
    result["page_count"]=len(pages)
    result.setdefault("warnings",[])
    result.setdefault("data",{})
    result.setdefault("evidence",[])
    # Reject common hallucinated/form-heading values before verification.
    for key, value in list(result.get("data", {}).items()):
        cleaned=_clean_value(key,value)
        if cleaned in (None, []):
            result["data"][key]=None if key!="lot_numbers" else []
        else:
            result["data"][key]=cleaned
    if api_key and any("AI processing error:" in str(w) for w in result["warnings"]):
        result["ai_status"]="fallback_after_error"
    elif api_key:
        result["ai_status"]="ai_extraction"
    else:
        result["ai_status"]="no_api_key"
    return result

def _norm(field,val):
    if val is None: return None
    if isinstance(val,list):
        return sorted({_norm(field,x) for x in val if x is not None})
    s=str(val).strip().upper()
    s=re.sub(r"\s+"," ",s)
    if field in ("container_number","seal_number","bl_number","invoice_number","hs_code"):
        s=re.sub(r"[\s\-./]","",s)
    if field in ("net_weight","gross_weight"):
        s=s.replace(",","")
    return s or None

def verify_shipment(docs):
    collected=defaultdict(list)
    for doc_index, doc in enumerate(docs):
        for field,val in doc.get("data",{}).items():
            if val not in (None,"",[]):
                collected[field].append({"value":val,"normalised":_norm(field,val),"document":doc.get("filename",""),"document_index":doc_index,"type":doc.get("document_type","Unknown")})
    findings=[]
    important=[("container_number","Container number"),("seal_number","Seal number"),("bl_number","Bill of Lading number"),("invoice_number","Invoice number"),("supplier_exporter","Supplier / exporter"),("consignee_importer","Consignee / importer"),("product_description","Product description"),("hs_code","HS / commodity code"),("country_of_origin","Country of origin"),("port_of_loading","Port of loading"),("port_of_discharge","Port of discharge"),("vessel","Vessel"),("voyage","Voyage"),("cartons_packages","Cartons / packages"),("net_weight","Net weight"),("gross_weight","Gross weight"),("container_size","Container size"),("container_type","Container type"),("temperature","Temperature"),("loading_method","Loading method"),("lot_numbers","Lot / batch numbers")]
    for field,label in important:
        vals=collected.get(field,[])
        distinct={json.dumps(x["normalised"],sort_keys=True) for x in vals}
        if len(distinct)>1:
            status="MISMATCH"; comment="Different values found between uploaded documents. Check the source documents."
        elif len(vals)==len(docs) and len(docs)>1:
            status="MATCH"; comment="Same value found in every uploaded document."
        elif vals:
            status="REVIEW"; comment="This field is not shown in every uploaded document; comparison is incomplete."
        else:
            status="MISSING"; comment="This field was not extracted from any uploaded document."
        evidence="; ".join(str(x["document"])+" ("+str(x["type"])+"): "+str(x["value"]) for x in vals)
        document_values=[]
        for i,d in enumerate(docs):
            value=next((str(x["value"]) for x in vals if x["document_index"]==i),"NOT SHOWN")
            document_values.append({"document_index":i,"filename":d.get("filename",""),"document_type":d.get("document_type",""),"value":value})
        findings.append({"field":label,"status":status,"normalised_values":" | ".join(str(x["value"]) for x in vals),"document_values":document_values,"evidence":evidence,"comment":comment})
    return {"findings":findings,"summary":{"documents_received":len(docs)},"document_warnings":[{"filename":d.get("filename"),"warnings":d.get("warnings",[])} for d in docs if d.get("warnings")]}

def build_supplier_email(result):
    issues=[x for x in result.get("findings",[]) if x.get("status") in ("MISMATCH","MISSING","REVIEW")]
    supplier=result.get("supplier") or "[Supplier]"
    ref=result.get("shipment_reference") or "[Shipment / container reference]"
    lines=[]
    for x in issues:
        lines.append(f"- {x['field']}: {x['status']}. Extracted evidence: {x['evidence'] or 'No value found'}. {x['comment']}")
    if not lines: lines=["- No material cross-document mismatch was detected in the fields extracted. Please confirm the attached documents are final and complete."]
    return f"""Subject: Document clarification required – {ref}

Dear {supplier} Team,

We are reviewing the shipping documents for the above shipment and have identified the following points that require your clarification and/or corrected documents:

{chr(10).join(lines)}

Please review the original documents and confirm the correct information. Where a document contains an error, kindly issue and share a corrected copy. Please do not amend or overwrite an issued certificate; arrange an amended/reissued document through the relevant issuing authority where required.

We would appreciate your prompt response so that we can progress the import documentation.

Kind regards,
Ali
Sahara UK Foods Ltd
"""

def _db():
    con=sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS shipments (
      id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_reference TEXT, supplier TEXT,
      created_at TEXT, status TEXT, payload TEXT)""")
    con.commit()
    return con

def save_shipment(result):
    try:
        con=_db()
        statuses=[x["status"] for x in result.get("findings",[])]
        status="ACTION REQUIRED" if any(x in statuses for x in ("MISMATCH","MISSING")) else ("REVIEW" if "REVIEW" in statuses else "NO DISCREPANCY DETECTED")
        con.execute("INSERT INTO shipments(shipment_reference,supplier,created_at,status,payload) VALUES(?,?,?,?,?)",
          (result.get("shipment_reference"),result.get("supplier"),result.get("created_at"),status,json.dumps(result,default=str)))
        con.commit(); con.close()
    except Exception:
        pass

def list_shipments():
    try:
        con=_db()
        rows=con.execute("SELECT shipment_reference,supplier,created_at,status FROM shipments ORDER BY id DESC LIMIT 200").fetchall()
        con.close()
        return [{"Shipment":r[0],"Supplier":r[1],"Reviewed":r[2],"Outcome":r[3]} for r in rows]
    except Exception:
        return []

def make_excel_report(result):
    import pandas as pd
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    out=io.BytesIO()
    with pd.ExcelWriter(out,engine="openpyxl") as writer:
        pd.DataFrame(result.get("findings",[])).to_excel(writer,index=False,sheet_name="Verification")
        docs=[]
        for d in result.get("documents",[]):
            for k,v in d.get("data",{}).items():
                if v not in (None,"",[]): docs.append({"Document":d.get("filename"),"Type":d.get("document_type"),"Field":k,"Extracted value":str(v)})
        pd.DataFrame(docs).to_excel(writer,index=False,sheet_name="Extracted Data")
        pd.DataFrame([{"Shipment":result.get("shipment_reference"),"Supplier":result.get("supplier"),"Reviewed":result.get("created_at")}]).to_excel(writer,index=False,sheet_name="Cover")
        for ws in writer.book.worksheets:
            ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
            for cell in ws[1]:
                cell.font=Font(bold=True,color="FFFFFF")
                cell.fill=PatternFill("solid",fgColor="102A43")
            for col in ws.columns:
                width=min(55,max(14,max(len(str(c.value or "")) for c in col)+2))
                ws.column_dimensions[get_column_letter(col[0].column)].width=width
    return out.getvalue()

def make_pdf_report(result):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.units import mm
    out=io.BytesIO(); doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=16*mm,leftMargin=16*mm,topMargin=16*mm,bottomMargin=16*mm)
    styles=getSampleStyleSheet()
    story=[Paragraph("SAHARA UK FOODS",styles["Title"]),Paragraph("Shipment Document Verification Report",styles["Heading2"]),
      Paragraph(f"Shipment: {result.get('shipment_reference') or 'Not supplied'} | Supplier: {result.get('supplier') or 'Not supplied'}",styles["Normal"]),
      Paragraph(f"Review date: {result.get('created_at','')}",styles["Normal"]),Spacer(1,8)]
    rows=[["Field","Status","Evidence / extracted values","Comment"]]
    for x in result.get("findings",[]):
        rows.append([x.get("field",""),x.get("status",""),(x.get("evidence","") or "")[:500],x.get("comment","")])
    t=Table(rows,repeatRows=1,colWidths=[31*mm,22*mm,75*mm,48*mm])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#102A43")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
      ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#CBD5D1")),
      ("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F2F6F4")])]))
    story.append(t)
    story += [Spacer(1,10),Paragraph("Important limitation",styles["Heading3"]),
      Paragraph("This report is an AI-assisted document review, not customs clearance approval, legal advice, certificate authentication or confirmation that all regulatory requirements have been met. Verify cited source pages and current UK import requirements before action.",styles["BodyText"])]
    doc.build(story); return out.getvalue()
