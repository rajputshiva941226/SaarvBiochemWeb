from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
import httpx
from datetime import datetime
import os

from database import create_tables, get_db, Enquiry, NewsletterSubscriber
from molecules import MOLECULES, CATEGORIES

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
    return templates.TemplateResponse("partials/enquiry_success.html", {
        "request": request,
        "name": first_name,
        "ref_id": f"SB{enquiry.id:05d}",
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
