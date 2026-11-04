# Sahara AI – Document Intelligence

A separate Streamlit application for AI-assisted import shipment document review.

## Current capabilities
- Multiple PDF/TXT uploads per shipment.
- PDF page text extraction; scanned pages can be sent as page images to the vision-capable model.
- Document classification and structured field extraction.
- Cross-document comparison for container, seal, BL, invoice, supplier, consignee, product, HS code, origin, ports, vessel/voyage, packages, weights, container type/size, temperature, loading method and lots.
- Findings with status: MATCH / MISMATCH / MISSING / REVIEW.
- Supplier discrepancy email draft (not sent automatically).
- Excel and PDF reports.
- Local SQLite shipment history.

## Run locally
Python 3.10+ recommended.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Set `OPENAI_API_KEY` in the environment or enter it in the app. The key is not saved by the application.

## Deployment
Deploy as a separate Streamlit Community Cloud app from a private GitHub repository. Add `OPENAI_API_KEY` in Streamlit app Secrets. Do not put API keys in source code.

## Important production work still required
- OCR/vision fallback has been implemented for scanned PDF pages when AI is configured; test against real supplier scans before operational use.
- Streamlit local SQLite storage is not durable/reliable for multi-replica production deployments. Replace with managed PostgreSQL and private object storage.
- Add user authentication, role-based access, audit logs, encryption-at-rest, retention/deletion policy and backup.
- Regulatory certificate applicability must be checked against current official UK rules by commodity/origin and cannot be inferred from a generic document checklist.
- Validate extraction and mismatch thresholds on representative Sahara shipments.
- This is a review assistant, not a customs filing or clearance system. Human review is mandatory.

## Data handling
Uploaded documents and extracted data are processed by the configured AI provider when an API key is supplied. Obtain internal approval for data processing and review provider terms before uploading commercially sensitive documents.
