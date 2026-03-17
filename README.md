# Saarv Biochem — Full Web Application

## Project Structure

```
saarv_biochem/
├── main.py                   # FastAPI app — all routes
├── database.py               # SQLAlchemy models (SQLite)
├── molecules.py              # API catalog data (100+ molecules)
├── requirements.txt
├── static/
│   └── css/main.css          # Full custom CSS (dark molecular theme)
└── templates/
    ├── base.html             # Navigation, footer
    ├── index.html            # Landing page
    ├── catalog.html          # API catalog with search/filter
    ├── molecule_detail.html  # Per-molecule page (PubChem data)
    ├── enquiry.html          # General enquiry/contact form
    ├── partials/
    │   └── enquiry_success.html
    ├── services/
    │   ├── computational_chemistry.html
    │   ├── computational_biology.html
    │   ├── pharmacovigilance.html
    │   ├── custom_synthesis.html
    │   ├── adme_tox.html
    │   └── consulting.html
    └── admin/
        └── enquiries.html    # Admin dashboard
```

## Setup & Run

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open: http://localhost:8000

## Pages / Routes

| URL | Page |
|-----|------|
| `/` | Landing page |
| `/catalog` | API catalog (search, filter by grade/category) |
| `/catalog/{cas}` | Molecule detail + PubChem 2D structure + enquiry form |
| `/enquiry` | General enquiry form |
| `/contact` | Same as /enquiry |
| `/services/computational-chemistry` | Service page |
| `/services/computational-biology` | Service page |
| `/services/pharmacovigilance` | Service page |
| `/services/custom-synthesis` | Service page |
| `/services/adme-tox` | Service page |
| `/services/consulting` | Service page |
| `/admin/enquiries` | Admin dashboard (all submissions) |
| `/api/docs` | FastAPI auto-docs |

## Database

SQLite (`saarv_biochem.db`) is created automatically on first run.

Tables:
- `enquiries` — all form submissions with full metadata, status, priority
- `newsletter_subscribers` — opt-in subscribers

Each enquiry stores: contact info, company/designation/country, enquiry type, molecule/service details, quantity/grade/purity, IP address, timestamps, and admin notes.

Admin can update status (new → in_progress → quoted → closed) from `/admin/enquiries`.

## PubChem Integration

Molecule detail pages fetch live from PubChem REST API:
- 2D structure image (400×400 PNG)
- Molecular formula, weight, XLogP, H-bond donors/acceptors
- IUPAC name
- Description text

Results are cached in-memory per process to avoid redundant API calls.

## Design

**Dark Molecular Lab** aesthetic:
- Background: Deep obsidian `#05100e` with hexagonal grid pattern
- Primary accent: Electric lime `#00ff94`
- Secondary: Warm amber `#ffab00`
- Fonts: Syne (display) + DM Sans (body) + JetBrains Mono (data)
- Grid-based layouts with no generic purple gradients
