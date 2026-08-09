import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional
from models import Flag, FlagLocation, Severity, LayerName
from config import settings

logger = logging.getLogger(__name__)

try:
    from google import genai as google_genai
    _client = google_genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None
except Exception:
    _client = None


# ── EXTRACTION SCHEMA ──────────────────────────────────────────────────────────
EXTRACTION_PROMPT = """
You are a forensic financial document analyzer for an Indian bank.
Analyze this document and extract structured financial data.

Document filename: {filename}
Document text (first 4000 chars):
{text}

Return ONLY valid JSON, no markdown, no explanation:
{{
  "document_type": "salary_slip|itr|bank_statement|land_record|loan_form|identity|other",
  "applicant_name": null,
  "applicant_pan": null,
  "applicant_dob": null,
  "monthly_income": null,
  "annual_income": null,
  "employer_name": null,
  "account_number": null,
  "bank_name": null,
  "account_balance": null,
  "existing_loans": null,
  "existing_emi_monthly": null,
  "property_value": null,
  "property_owner": null,
  "ownership_date": null,
  "document_date": null,
  "document_period": null,
  "tax_paid": null,
  "net_worth": null,
  "deductions": null,
  "pf_contribution": null,
  "extraction_confidence": 0.0
}}

Rules:
- All amounts in INR as plain numbers (no symbols)
- Dates as YYYY-MM-DD strings
- null for missing fields
- extraction_confidence: 0.0-1.0 based on text quality
"""


def run(parsed_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    t0 = time.time()
    readable = [d for d in parsed_docs if d.get("text", "").strip() and not d.get("error")]

    if len(readable) < 1:
        return _no_docs_result(t0)

    # Extract structured data from each document
    extracted: Dict[str, Dict] = {}
    for doc in readable:
        data = _extract_financial_data(doc)
        extracted[doc["filename"]] = data

    if len(extracted) < 2:
        # Single document — run internal consistency check
        contradictions = _check_internal_consistency(extracted)
    else:
        contradictions = _cross_check_all(extracted)

    flags: List[Flag] = []
    total_score = 0.0

    for c in contradictions:
        sev_map = {"critical": (Severity.CRITICAL, 35.0), "high": (Severity.HIGH, 20.0), "medium": (Severity.MEDIUM, 10.0)}
        sev, pts = sev_map.get(c["severity"], (Severity.MEDIUM, 10.0))
        total_score += pts
        flags.append(Flag(
            flag_type=f"contradiction_{c['field']}",
            severity=sev,
            description=c["description"],
            confidence=c.get("confidence", 0.7),
            metadata={
                "field": c["field"],
                "doc_a": c.get("doc_a", ""),
                "doc_b": c.get("doc_b", ""),
                "value_a": str(c.get("value_a", "")),
                "value_b": str(c.get("value_b", "")),
                "discrepancy_pct": c.get("discrepancy_pct", 0),
            },
            source_layer=LayerName.CONTRADICTION,
        ))

    return {
        "layer": LayerName.CONTRADICTION,
        "passed": len(flags) == 0,
        "flags": [f.model_dump() for f in flags],
        "score_contribution": min(total_score, 50.0),
        "summary": _build_summary(flags, extracted),
        "processing_time_ms": int((time.time() - t0) * 1000),
        "extracted_data": {k: _sanitize(v) for k, v in extracted.items()},
        "contradictions_found": len(flags),
        "metadata": {"docs_analyzed": len(extracted), "extraction_method": "gemini" if _client else "regex"}
    }


def _extract_financial_data(doc: Dict) -> Dict:
    text = doc.get("text", "")
    filename = doc.get("filename", "")
    if _client and text.strip():
        return _extract_with_gemini(text, filename)
    return _extract_with_regex(text, filename)


def _extract_with_gemini(text: str, filename: str) -> Dict:
    try:
        prompt = EXTRACTION_PROMPT.format(filename=filename, text=text[:4000])
        response = _client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        raw = response.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        data["filename"] = filename
        data["extraction_method"] = "gemini"
        return data
    except Exception as e:
        logger.warning("Gemini extraction failed for %s: %s", filename, e)
        result = _extract_with_regex(text, filename)
        result["gemini_error"] = str(e)
        return result


def _extract_with_regex(text: str, filename: str) -> Dict:
    data: Dict[str, Any] = {
        "filename": filename,
        "extraction_method": "regex",
        "document_type": _detect_doc_type(filename, text),
        "applicant_name": None, "applicant_pan": None,
        "monthly_income": None, "annual_income": None,
        "account_balance": None, "existing_loans": None,
        "existing_emi_monthly": None, "document_date": None,
        "extraction_confidence": 0.3,
    }

    # Income extraction
    income_patterns = [
        (r"(?:gross\s+salary|net\s+salary|basic\s+pay|monthly\s+salary|take.?home)[^\d₹Rs\.INR]*(?:₹|Rs\.?|INR)?\s*([\d,]+)", "monthly"),
        (r"(?:₹|Rs\.?|INR)\s*([\d,]+)\s*(?:per\s+month|p\.m\.|/month|pm\b)", "monthly"),
        (r"(?:annual|yearly|total)\s+(?:income|salary|ctc)[^\d]*(?:₹|Rs\.?|INR)?\s*([\d,]+)", "annual"),
        (r"(?:total\s+income|gross\s+total)[^\d]*(?:₹|Rs\.?|INR)?\s*([\d,]+)", "annual"),
    ]
    for pattern, period in income_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                amount = float(match.group(1).replace(",", ""))
                if period == "monthly" and amount > 500:
                    data["monthly_income"] = amount
                    data["annual_income"] = amount * 12
                elif period == "annual" and amount > 6000:
                    data["annual_income"] = amount
                    data["monthly_income"] = amount / 12
                data["extraction_confidence"] = 0.6
                break
            except ValueError:
                pass

    # Name extraction
    name_patterns = [
        r"(?:employee\s+name|name\s+of\s+employee|applicant\s+name|name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})",
        r"(?:mr\.?|mrs\.?|ms\.?|dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
    ]
    for p in name_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if 3 < len(name) < 60:
                data["applicant_name"] = name
                break

    # PAN
    pan_m = re.search(r"\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b", text)
    if pan_m:
        data["applicant_pan"] = pan_m.group(1)

    # Account balance
    bal_m = re.search(r"(?:balance|closing\s+balance|available\s+balance)[^\d]*(?:₹|Rs\.?|INR)?\s*([\d,]+)", text, re.IGNORECASE)
    if bal_m:
        try:
            data["account_balance"] = float(bal_m.group(1).replace(",", ""))
        except ValueError:
            pass

    # Date
    date_m = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b", text)
    if date_m:
        data["document_date"] = date_m.group(1)

    return data


def _cross_check_all(extracted: Dict[str, Dict]) -> List[Dict]:
    contradictions = []
    docs = list(extracted.items())
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            fa, da = docs[i]
            fb, db = docs[j]
            for checker in [_check_income, _check_name, _check_pan, _check_emi_vs_declaration]:
                result = checker(fa, da, fb, db)
                if result:
                    contradictions.append(result)
    return contradictions


def _check_internal_consistency(extracted: Dict[str, Dict]) -> List[Dict]:
    contradictions = []
    for fname, data in extracted.items():
        monthly = data.get("monthly_income")
        annual = data.get("annual_income")
        if monthly and annual:
            expected_annual = monthly * 12
            if abs(expected_annual - annual) / max(annual, 1) > 0.15:
                contradictions.append({
                    "field": "income_internal_consistency",
                    "severity": "high",
                    "doc_a": fname,
                    "doc_b": fname,
                    "value_a": f"Monthly ₹{monthly:,.0f} × 12 = ₹{expected_annual:,.0f}",
                    "value_b": f"Annual stated as ₹{annual:,.0f}",
                    "discrepancy_pct": round(abs(expected_annual - annual) / max(annual, 1) * 100, 1),
                    "confidence": 0.9,
                    "description": (
                        f"Internal income inconsistency in {fname}: monthly ₹{monthly:,.0f} × 12 = ₹{expected_annual:,.0f} "
                        f"but annual income is stated as ₹{annual:,.0f} "
                        f"({abs(expected_annual-annual)/max(annual,1)*100:.1f}% discrepancy)."
                    )
                })
    return contradictions


def _check_income(fa: str, da: Dict, fb: str, db: Dict) -> Optional[Dict]:
    def get_annual(d):
        if d.get("annual_income") and d["annual_income"] > 0:
            return float(d["annual_income"])
        if d.get("monthly_income") and d["monthly_income"] > 0:
            return float(d["monthly_income"]) * 12
        return None

    ia = get_annual(da)
    ib = get_annual(db)
    if not ia or not ib:
        return None

    ratio = max(ia, ib) / min(ia, ib)
    if ratio <= (1 + settings.INCOME_MISMATCH_THRESHOLD):
        return None

    discrepancy_pct = round((ratio - 1) * 100, 1)
    if ratio > 2.5:
        severity, confidence = "critical", 0.95
    elif ratio > 1.5:
        severity, confidence = "high", 0.85
    else:
        severity, confidence = "medium", 0.7

    return {
        "field": "annual_income",
        "severity": severity,
        "doc_a": fa, "doc_b": fb,
        "value_a": f"₹{ia:,.0f}/year",
        "value_b": f"₹{ib:,.0f}/year",
        "discrepancy_pct": discrepancy_pct,
        "confidence": confidence,
        "description": (
            f"Income mismatch between {fa} and {fb}. "
            f"{fa} shows ₹{ia:,.0f}/year but {fb} shows ₹{ib:,.0f}/year. "
            f"Discrepancy of {discrepancy_pct}% significantly exceeds the 25% acceptable threshold. "
            f"Ratio: {ratio:.1f}x. Indicates deliberate income inflation in one document."
        ),
    }


def _check_name(fa: str, da: Dict, fb: str, db: Dict) -> Optional[Dict]:
    na = (da.get("applicant_name") or "").strip().lower()
    nb = (db.get("applicant_name") or "").strip().lower()
    if not na or not nb or na == nb:
        return None
    words_a = set(na.split())
    words_b = set(nb.split())
    overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
    if overlap >= 0.5:
        return None
    return {
        "field": "applicant_name",
        "severity": "high",
        "doc_a": fa, "doc_b": fb,
        "value_a": da.get("applicant_name", ""),
        "value_b": db.get("applicant_name", ""),
        "discrepancy_pct": round((1 - overlap) * 100, 1),
        "confidence": 0.8,
        "description": (
            f"Applicant name mismatch: '{da.get('applicant_name')}' in {fa} "
            f"vs '{db.get('applicant_name')}' in {fb}. "
            f"Name overlap {overlap*100:.0f}% — different people or deliberate substitution."
        ),
    }


def _check_pan(fa: str, da: Dict, fb: str, db: Dict) -> Optional[Dict]:
    pa = da.get("applicant_pan", "")
    pb = db.get("applicant_pan", "")
    if not pa or not pb or pa == pb:
        return None
    return {
        "field": "applicant_pan",
        "severity": "critical",
        "doc_a": fa, "doc_b": fb,
        "value_a": pa, "value_b": pb,
        "discrepancy_pct": 100,
        "confidence": 0.99,
        "description": (
            f"PAN number mismatch: {fa} contains PAN {pa} but {fb} contains {pb}. "
            f"Documents belong to different individuals or PAN was forged."
        ),
    }


def _check_emi_vs_declaration(fa: str, da: Dict, fb: str, db: Dict) -> Optional[Dict]:
    for (doc_form, data_form), (doc_bank, data_bank) in [
        ((fa, da), (fb, db)), ((fb, db), (fa, da))
    ]:
        if data_form.get("document_type") == "loan_form":
            declared_no_loans = data_form.get("existing_loans") is False
            bank_emi = data_bank.get("existing_emi_monthly")
            if declared_no_loans and bank_emi and float(bank_emi) > 0:
                return {
                    "field": "existing_loan_declaration",
                    "severity": "critical",
                    "doc_a": doc_form, "doc_b": doc_bank,
                    "value_a": "No existing loans declared",
                    "value_b": f"Active EMI ₹{float(bank_emi):,.0f}/month in bank statement",
                    "discrepancy_pct": 100,
                    "confidence": 0.95,
                    "description": (
                        f"Loan declaration fraud: {doc_form} declares no existing loans, "
                        f"but {doc_bank} shows active EMI payments of ₹{float(bank_emi):,.0f}/month. "
                        f"Applicant has concealed existing debt obligations from the bank."
                    ),
                }
    return None


def _detect_doc_type(filename: str, text: str) -> str:
    import re
    fn = filename.lower()
    tx = text.lower()
    patterns = {
        "salary_slip": r"salary|payslip|pay slip|gross pay|basic pay",
        "itr": r"income tax|itr|form 16|assessment year|taxable income",
        "bank_statement": r"bank statement|account statement|debit|credit|transaction",
        "land_record": r"land record|property|survey|khata|registry",
        "loan_form": r"loan application|borrower|emi|repayment",
        "identity": r"passport|aadhaar|voter id|driving licence|pan card",
    }
    for doc_type, pattern in patterns.items():
        if re.search(pattern, fn) or re.search(pattern, tx):
            return doc_type
    return "other"


def _sanitize(data: Dict) -> Dict:
    return {k: v for k, v in data.items()
            if isinstance(v, (str, int, float, bool, dict, list, type(None)))}


def _no_docs_result(t0: float) -> Dict:
    return {
        "layer": LayerName.CONTRADICTION, "passed": True, "flags": [],
        "score_contribution": 0.0, "summary": "No readable documents for cross-analysis.",
        "processing_time_ms": int((time.time() - t0) * 1000),
        "extracted_data": {}, "contradictions_found": 0,
        "metadata": {"docs_analyzed": 0}
    }


def _build_summary(flags: List[Flag], extracted: Dict) -> str:
    if not flags:
        return (f"Cross-document AI analysis of {len(extracted)} document(s) complete. "
                f"All financial figures are internally consistent — no contradictions detected.")
    crit = sum(1 for f in flags if f.severity == Severity.CRITICAL)
    return (f"{'CRITICAL' if crit else 'HIGH RISK'}: {len(flags)} contradiction(s) detected across {len(extracted)} documents. "
            f"{crit} critical flag(s). Financial figures are irreconcilable — strong indicator of fraud.")
