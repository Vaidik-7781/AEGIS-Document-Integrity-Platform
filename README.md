# ⚔ AEGIS v3.0 — Intelligent Document Integrity Platform

> Real-time, 5-layer document fraud detection engine for banking underwriting.
> Built for **SuRaksha Hackathon** by Canara Bank · Theme: Real-time Anomaly Detection

---

## Architecture

```
AEGIS/
├── backend/          FastAPI + Python
│   ├── main.py       API routes + WebSocket real-time
│   ├── config.py     Pydantic settings
│   ├── models.py     Full Pydantic v2 data models
│   ├── database.py   SQLite with WAL + indices
│   ├── ingestor.py   Advanced PDF/image parser (PyMuPDF)
│   ├── aggregator.py Bayesian weighted risk scoring
│   └── layers/
│       ├── ela.py              L1: Multi-quality ELA + noise analysis
│       ├── blockchain.py       L2: SHA-256 + chain notarization
│       ├── contradiction.py    L3: Gemini AI cross-doc extraction
│       ├── font_forensics.py   L4: 5-algorithm typography fingerprinting
│       └── version_diff.py     L5: Semantic diff + resubmission detection
│
└── frontend/         React 19 + Vite + Framer Motion
    └── src/
        ├── services/api.js     Full Axios client + WebSocket helper
        ├── store/AppContext.jsx Global state (useReducer)
        ├── hooks/useAnalysis.js Analysis orchestration
        ├── components/
        │   ├── Layout.jsx      Collapsible sidebar + topbar
        │   └── ui/index.jsx    Card, StatCard, AnimCounter, VerdictBadge,
        │                       LayerRow, AnimBar, RiskGauge, Spinner, Toast
        └── pages/
            ├── Dashboard.jsx   Stats + Heatmap + Chart + Upload + Layers + Gauge
            ├── Report.jsx      Score + Accordion + Terminal typewriter + Flags
            ├── History.jsx     Table + Search + Filter + Real API
            └── Verify.jsx      SHA-256 + Blockchain check + 4 result states
```

---

## 5 Detection Layers

| Layer | File | Algorithm | Detects |
|-------|------|-----------|---------|
| L1 | `ela.py` | Multi-quality ELA + noise variance + blocking artifacts | Pixel-level forgery in scanned images |
| L2 | `blockchain.py` | SHA-256 + HMAC constant-time compare | Tampering after notarization |
| L3 | `contradiction.py` | Gemini AI structured extraction + cross-validation | Income/name/PAN/loan mismatches |
| L4 | `font_forensics.py` | Z-score, family consistency, color, intra-line mixing, kerning | Character-level text replacement |
| L5 | `version_diff.py` | Content fingerprint + semantic diff | Resubmission fraud |

---

## Run Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # Add GEMINI_API_KEY
python main.py                # → http://localhost:8000
```

### API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/analyze` | Upload docs → runs all 5 layers → returns risk score |
| WS | `/ws/analyze` | WebSocket real-time analysis with layer progress |
| GET | `/report/{id}` | Get full analysis report |
| GET | `/history` | Paginated submission history |
| GET | `/stats` | Aggregate statistics |
| GET | `/hash/{hash}` | Check blockchain notarization |
| GET | `/health` | System health check |

---

## Run Frontend

```bash
cd frontend
npm install
npm run dev       # → http://localhost:5173
npm run build     # Production build → dist/
```

---

## One-Line Pitch

> *"AEGIS is a 5-layer real-time document fraud detection engine combining visual forensics, blockchain proof, AI contradiction analysis, typography fingerprinting, and version history — giving bank underwriters a single trust score before any loan is approved."*
