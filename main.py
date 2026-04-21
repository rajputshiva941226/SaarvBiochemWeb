from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
import httpx
from datetime import datetime
import os
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import create_tables, get_db, Enquiry, NewsletterSubscriber
from molecules import MOLECULES, CATEGORIES

# ── Email Config (set these in .env) ───────────────────────────────────────
# GoDaddy cPanel webmail:  HOST=smtpout.secureserver.net  PORT=465
# GoDaddy Microsoft 365:  HOST=smtp.office365.com         PORT=587
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtpout.secureserver.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USER = os.getenv("EMAIL_USER", "")           # enquiry@saarvbiochem.com
EMAIL_PASS = os.getenv("EMAIL_PASS", "")           # your email password
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USER)
EMAIL_TO   = os.getenv("EMAIL_TO",   "saarv.biochem1241@gmail.com")


def _send(msg: MIMEMultipart) -> bool:
    """Send email. Silently skips if credentials not set."""
    if not EMAIL_USER or not EMAIL_PASS:
        print("[EMAIL] Skipped — credentials not configured in .env")
        return False
    try:
        if EMAIL_PORT == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(EMAIL_HOST, EMAIL_PORT, context=ctx, timeout=15) as s:
                s.login(EMAIL_USER, EMAIL_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT, timeout=15) as s:
                s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo()
                s.login(EMAIL_USER, EMAIL_PASS)
                s.send_message(msg)
        print(f"[EMAIL] Sent to {msg['To']}")
        return True
    except Exception as e:
        print(f"[EMAIL] Failed: {e}")
        return False


def email_admin(enquiry, ref_id: str):
    """Notify admin of new enquiry."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Saarv Biochem] New Enquiry {ref_id} — {enquiry.subject}"
    msg["From"]    = f"Saarv Biochem Website <{EMAIL_FROM}>"
    msg["To"]      = EMAIL_TO

    rows = ""
    fields = [
        ("Name", f"{enquiry.first_name} {enquiry.last_name}"),
        ("Email", enquiry.email),
        ("Phone", enquiry.phone),
        ("Company", enquiry.company),
        ("Designation", enquiry.designation),
        ("Country", enquiry.country),
        ("Enquiry Type", enquiry.enquiry_type.replace("_", " ").title()),
        ("Service Interest", enquiry.service_interest),
        ("Molecule / CAS", f"{enquiry.molecule_name} {'(CAS: '+enquiry.cas_number+')' if enquiry.cas_number else ''}" if enquiry.molecule_name else ""),
        ("Quantity", enquiry.required_quantity),
        ("Grade", enquiry.required_grade),
        ("Purity", enquiry.purity_requirement),
        ("Subject", enquiry.subject),
        ("Source Page", enquiry.source_page),
        ("Submitted", enquiry.created_at.strftime("%d %b %Y, %H:%M UTC")),
    ]
    for label, val in fields:
        if val and val.strip():
            rows += f"<tr><td style='padding:8px 12px;color:#6a9ab5;font-weight:600;width:36%;border-bottom:1px solid #1a3050;white-space:nowrap;font-size:0.85rem;'>{label}</td><td style='padding:8px 12px;color:#ddeeff;border-bottom:1px solid #1a3050;font-size:0.85rem;'>{val}</td></tr>"

    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0a1628;font-family:Arial,sans-serif;">
<div style="max-width:620px;margin:28px auto;background:#0d1f30;border:1px solid #1a3050;border-radius:10px;overflow:hidden;">
  <div style="background:#04101e;padding:24px 28px;border-bottom:2px solid #00b4ff;">
    <h2 style="color:#00b4ff;margin:0 0 4px;font-size:1.2rem;">🧬 New Enquiry — {ref_id}</h2>
    <p style="color:#6a9ab5;margin:0;font-size:0.8rem;">Submitted via saarvbiochem.com</p>
  </div>
  <table style="width:100%;border-collapse:collapse;">{rows}</table>
  <div style="padding:16px 28px;background:#060f1c;">
    <p style="color:#6a9ab5;font-size:0.75rem;margin:0 0 6px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;">Message</p>
    <div style="background:#0a1628;border-left:3px solid #00b4ff;padding:12px 16px;border-radius:0 6px 6px 0;color:#ddeeff;font-size:0.87rem;line-height:1.6;">{enquiry.message}</div>
  </div>
  <div style="padding:14px 28px;background:#04101e;border-top:1px solid #1a3050;text-align:center;">
    <a href="http://saarvbiochem.com/admin/enquiries" style="color:#00b4ff;font-size:0.78rem;">View Admin Dashboard →</a>
  </div>
</div></body></html>"""

    msg.attach(MIMEText(html, "html"))
    _send(msg)


def email_user(enquiry, ref_id: str):
    """Confirmation email to the enquirer."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Enquiry Received — {ref_id} | Saarv Biochem"
    msg["From"]    = f"Saarv Biochem <{EMAIL_FROM}>"
    msg["To"]      = enquiry.email

    detail = ""
    if enquiry.molecule_name:
        detail = f"<div style='background:#0a1628;border-radius:6px;padding:12px 16px;margin:16px 0;font-size:0.87rem;color:#ddeeff;'><b>Molecule:</b> {enquiry.molecule_name}" + (f" &nbsp;·&nbsp; CAS: {enquiry.cas_number}" if enquiry.cas_number else "") + "</div>"
    elif enquiry.service_interest:
        detail = f"<div style='background:#0a1628;border-radius:6px;padding:12px 16px;margin:16px 0;font-size:0.87rem;color:#ddeeff;'><b>Service:</b> {enquiry.service_interest}</div>"

    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0a1628;font-family:Arial,sans-serif;">
<div style="max-width:560px;margin:28px auto;background:#0d1f30;border:1px solid #1a3050;border-radius:10px;overflow:hidden;">
  <div style="background:#04101e;padding:32px;text-align:center;border-bottom:1px solid #1a3050;">
    <div style="font-size:3rem;margin-bottom:10px;">✅</div>
    <h1 style="color:#00b4ff;margin:0 0 6px;font-size:1.4rem;">Enquiry Received!</h1>
    <p style="color:#6a9ab5;margin:0;font-size:0.85rem;">Thank you for contacting Saarv Biochem</p>
  </div>
  <div style="padding:28px 32px;">
    <p style="color:#ddeeff;font-size:0.92rem;line-height:1.7;margin:0 0 12px;">Dear <b>{enquiry.first_name} {enquiry.last_name}</b>,</p>
    <p style="color:#aac4d8;font-size:0.9rem;line-height:1.7;margin:0 0 20px;">We have received your enquiry. Our team will review your requirements and respond within <b style='color:#ddeeff;'>24 business hours</b>.</p>
    <div style="background:#0a1628;border:2px solid #00b4ff;border-radius:8px;padding:16px;text-align:center;margin:0 0 20px;">
      <div style="color:#6a9ab5;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">Reference Number</div>
      <div style="color:#00b4ff;font-size:2rem;font-weight:700;font-family:monospace;">{ref_id}</div>
      <div style="color:#6a9ab5;font-size:0.72rem;margin-top:4px;">Keep this for any follow-up</div>
    </div>
    {detail}
    <p style="color:#aac4d8;font-size:0.88rem;margin:0 0 8px;">For urgent queries, reach us at:</p>
    <div style="background:#0a1628;border-radius:6px;padding:12px 16px;font-size:0.87rem;color:#ddeeff;">
      📧 <a href="mailto:enquiry@saarvbiochem.com" style="color:#00b4ff;">enquiry@saarvbiochem.com</a><br>
      📞 <a href="tel:+916351171509" style="color:#00b4ff;">+91 6351171509</a>
    </div>
    <div style="margin-top:24px;text-align:center;">
      <a href="https://saarvbiochem.com/catalog" style="display:inline-block;background:#00b4ff;color:#04101e;font-weight:700;padding:11px 28px;border-radius:8px;text-decoration:none;font-size:0.9rem;">Browse API Catalog →</a>
    </div>
  </div>
  <div style="padding:16px 32px;background:#04101e;border-top:1px solid #1a3050;text-align:center;">
    <p style="color:#6a9ab5;font-size:0.72rem;margin:0;">Saarv Biochem · Nadiad, Gujarat 387330 · <a href="https://saarvbiochem.com" style="color:#00b4ff;">saarvbiochem.com</a></p>
  </div>
</div></body></html>"""

    msg.attach(MIMEText(html, "html"))
    _send(msg)

app = FastAPI(title="Saarv Biochem", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

create_tables()


# ── Helpers ────────────────────────────────────────────────────────────────
def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0] if forwarded else request.client.host


async def fetch_pubchem(name: str, cas: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        cid = None
        for query in [cas, name]:
            try:
                r = await client.get(
                    f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{query}/cids/JSON"
                )
                if r.status_code == 200:
                    data = r.json()
                    cid = data.get("IdentifierList", {}).get("CID", [None])[0]
                    if cid:
                        break
            except Exception:
                continue

        if not cid:
            return {}

        result = {
            "cid": cid,
            "structure_url": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG?image_size=400x400",
            "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            "description": "",
            "iupac_name": "",
            "molecular_formula": "",
            "molecular_weight": "",
            "xlogp": "",
            "hbd": "",
            "hba": "",
        }

        # Fetch properties
        try:
            props_r = await client.get(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/"
                f"IUPACName,MolecularFormula,MolecularWeight,XLogP,HBondDonorCount,HBondAcceptorCount/JSON"
            )
            if props_r.status_code == 200:
                props = props_r.json().get("PropertyTable", {}).get("Properties", [{}])[0]
                result["iupac_name"] = props.get("IUPACName", "")
                result["molecular_formula"] = props.get("MolecularFormula", "")
                result["molecular_weight"] = props.get("MolecularWeight", "")
                result["xlogp"] = props.get("XLogP", "")
                result["hbd"] = props.get("HBondDonorCount", "")
                result["hba"] = props.get("HBondAcceptorCount", "")
        except Exception:
            pass

        # Fetch description
        try:
            desc_r = await client.get(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON?heading=Description"
            )
            if desc_r.status_code == 200:
                desc_data = desc_r.json()
                sections = desc_data.get("Record", {}).get("Section", [])
                for sec in sections:
                    for subsec in sec.get("Section", []):
                        for info in subsec.get("Information", []):
                            text = info.get("Value", {}).get("StringWithMarkup", [{}])[0].get("String", "")
                            if text and len(text) > 40:
                                result["description"] = text[:500]
                                break
                        if result["description"]:
                            break
                    if result["description"]:
                        break
        except Exception:
            pass

        return result


# ── Pages ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    stats = {"molecules": len(MOLECULES), "partners": "50+", "projects": "1000+", "satisfaction": "99%"}
    return templates.TemplateResponse("index.html", {"request": request, "stats": stats})


@app.get("/catalog", response_class=HTMLResponse)
async def catalog(
    request: Request,
    q: str = "",
    grade: str = "",
    category: str = "",
    page: int = 1
):
    per_page = 24
    filtered = MOLECULES
    if q:
        ql = q.lower()
        filtered = [m for m in filtered if ql in m["name"].lower() or ql in m["cas"]]
    if grade:
        filtered = [m for m in filtered if grade in m["grades"]]
    if category:
        filtered = [m for m in filtered if m["category"] == category]

    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    paginated = filtered[start:start + per_page]

    return templates.TemplateResponse("catalog.html", {
        "request": request,
        "molecules": paginated,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "q": q,
        "grade": grade,
        "category": category,
        "categories": CATEGORIES,
        "grades": ["USP", "EP", "BP", "IP", "JP"],
    })


@app.get("/catalog/{cas_slug}", response_class=HTMLResponse)
async def molecule_detail(request: Request, cas_slug: str):
    mol = next((m for m in MOLECULES if m["cas"].replace("-", "") == cas_slug.replace("-", "")), None)
    if not mol:
        raise HTTPException(status_code=404, detail="Molecule not found")
    pubchem_data = await fetch_pubchem(mol["name"], mol["cas"])
    return templates.TemplateResponse("molecule_detail.html", {
        "request": request,
        "mol": mol,
        "pubchem": pubchem_data,
    })


@app.get("/api/pubchem/{cas}", response_class=JSONResponse)
async def pubchem_api(cas: str):
    mol = next((m for m in MOLECULES if m["cas"] == cas), None)
    if not mol:
        return JSONResponse({"error": "not found"}, status_code=404)
    data = await fetch_pubchem(mol["name"], mol["cas"])
    return data


# ── Service Pages ──────────────────────────────────────────────────────────
@app.get("/services/computational-chemistry", response_class=HTMLResponse)
async def service_comp_chem(request: Request):
    return templates.TemplateResponse("services/computational_chemistry.html", {"request": request})

@app.get("/services/computational-biology", response_class=HTMLResponse)
async def service_comp_bio(request: Request):
    return templates.TemplateResponse("services/computational_biology.html", {"request": request})

@app.get("/services/pharmacovigilance", response_class=HTMLResponse)
async def service_pv(request: Request):
    return templates.TemplateResponse("services/pharmacovigilance.html", {"request": request})

@app.get("/services/custom-synthesis", response_class=HTMLResponse)
async def service_synthesis(request: Request):
    return templates.TemplateResponse("services/custom_synthesis.html", {"request": request})

@app.get("/services/adme-tox", response_class=HTMLResponse)
async def service_adme(request: Request):
    return templates.TemplateResponse("services/adme_tox.html", {"request": request})

@app.get("/services/consulting", response_class=HTMLResponse)
async def service_consulting(request: Request):
    return templates.TemplateResponse("services/consulting.html", {"request": request})

@app.get("/enquiry", response_class=HTMLResponse)
async def enquiry_page(request: Request):
    return templates.TemplateResponse("enquiry.html", {"request": request})

@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("enquiry.html", {"request": request})


# ── Enquiry Submission ─────────────────────────────────────────────────────
@app.post("/enquiry/submit")
async def submit_enquiry(
    request: Request,
    db: Session = Depends(get_db),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    company: str = Form(""),
    designation: str = Form(""),
    country: str = Form(""),
    enquiry_type: str = Form("service"),
    service_interest: str = Form(""),
    subject: str = Form(""),
    message: str = Form(...),
    molecule_name: str = Form(""),
    cas_number: str = Form(""),
    required_quantity: str = Form(""),
    required_grade: str = Form(""),
    purity_requirement: str = Form(""),
    source_page: str = Form(""),
    consent: bool = Form(False),
    newsletter: bool = Form(False),
):
    enquiry = Enquiry(
        first_name=first_name, last_name=last_name,
        email=email, phone=phone, company=company,
        designation=designation, country=country,
        enquiry_type=enquiry_type, service_interest=service_interest,
        subject=subject or f"Enquiry: {service_interest or molecule_name or 'General'}",
        message=message,
        molecule_name=molecule_name, cas_number=cas_number,
        required_quantity=required_quantity, required_grade=required_grade,
        purity_requirement=purity_requirement,
        source_page=source_page, ip_address=get_client_ip(request),
        consent_given=consent, newsletter_opt_in=newsletter,
    )
    db.add(enquiry)

    if newsletter and email:
        existing = db.query(NewsletterSubscriber).filter_by(email=email).first()
        if not existing:
            db.add(NewsletterSubscriber(email=email, name=f"{first_name} {last_name}"))

    db.commit()

    ref_id = f"SB{enquiry.id:05d}"

    # ── Send emails (non-blocking) ──────────────────────────────────────
    try:
        email_admin(enquiry, ref_id)
        email_user(enquiry, ref_id)
    except Exception as e:
        print(f"[EMAIL] Unexpected error: {e}")

    return templates.TemplateResponse("partials/enquiry_success.html", {
        "request": request,
        "name": first_name,
        "ref_id": ref_id,
    })


# ── Admin ──────────────────────────────────────────────────────────────────
@app.get("/admin/enquiries", response_class=HTMLResponse)
async def admin_enquiries(
    request: Request,
    db: Session = Depends(get_db),
    status: str = "",
    enquiry_type: str = "",
    page: int = 1,
):
    per_page = 25
    query = db.query(Enquiry)
    if status:
        query = query.filter(Enquiry.status == status)
    if enquiry_type:
        query = query.filter(Enquiry.enquiry_type == enquiry_type)
    total = query.count()
    enquiries = query.order_by(Enquiry.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    stats = {
        "total": db.query(Enquiry).count(),
        "new": db.query(Enquiry).filter_by(status="new").count(),
        "in_progress": db.query(Enquiry).filter_by(status="in_progress").count(),
    }
    return templates.TemplateResponse("admin/enquiries.html", {
        "request": request,
        "enquiries": enquiries,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "status": status,
        "enquiry_type": enquiry_type,
        "stats": stats,
    })


@app.post("/admin/enquiries/{id}/status")
async def update_status(id: int, status: str = Form(...), db: Session = Depends(get_db)):
    enquiry = db.query(Enquiry).filter_by(id=id).first()
    if not enquiry:
        raise HTTPException(status_code=404)
    enquiry.status = status
    db.commit()
    return RedirectResponse("/admin/enquiries", status_code=303)