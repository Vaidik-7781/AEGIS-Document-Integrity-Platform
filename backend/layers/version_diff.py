import hashlib
import difflib
import re
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from models import Flag, FlagLocation, Severity, LayerName
from database import save_fingerprint, get_fingerprint_history, get_hash_history

logger = logging.getLogger(__name__)

FINANCIAL_LINE_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr|salary|income|balance|amount|total|emi|loan|tax|gross|net).*[\d,]+|[\d,]+\s*(?:₹|rs\.?|inr)",
    re.IGNORECASE
)


def run(parsed_doc: Dict[str, Any], applicant_id: Optional[str] = None,
        submission_id: Optional[str] = None) -> Dict[str, Any]:
    t0 = time.time()
    filename = parsed_doc.get("filename", "unknown")
    raw_hash = parsed_doc.get("raw_hash", "")
    text = parsed_doc.get("text", "")
    content_fp = parsed_doc.get("content_fingerprint", "")

    if not raw_hash:
        return _error_result("Cannot compute document fingerprint.", t0)

    # ── CHECK 1: EXACT HASH MATCH (unmodified resubmission) ──────────────────
    exact_history = get_hash_history(raw_hash)
    if exact_history:
        first = exact_history[-1]
        return {
            "layer": LayerName.VERSION_DIFF, "passed": True, "flags": [],
            "score_contribution": 0.0,
            "summary": (f"Document matches previously submitted version from "
                        f"{first.get('uploaded_at','unknown')}. No modifications."),
            "processing_time_ms": int((time.time() - t0) * 1000),
            "is_resubmission": True,
            "submission_count": len(exact_history),
            "first_seen": first.get("uploaded_at"),
            "diff_summary": None,
            "financial_changes": 0,
            "metadata": {"match_type": "exact_hash"}
        }

    # ── CHECK 2: CONTENT FINGERPRINT (modified resubmission) ─────────────────
    similar_history = get_fingerprint_history(content_fp)

    # Save current
    save_fingerprint(
        fingerprint=content_fp,
        filename=filename,
        file_hash=raw_hash,
        applicant_id=applicant_id,
        submission_id=submission_id,
    )

    if similar_history:
        previous = similar_history[0]
        prev_text = previous.get("text_sample", "")

        flags, diff_result = _analyze_diff(filename, text, prev_text, previous)
        final_score = min(sum(_severity_score(f.severity) for f in flags), 40.0)

        return {
            "layer": LayerName.VERSION_DIFF,
            "passed": len(flags) == 0,
            "flags": [f.model_dump() for f in flags],
            "score_contribution": final_score,
            "summary": _build_summary(flags, similar_history),
            "processing_time_ms": int((time.time() - t0) * 1000),
            "is_resubmission": True,
            "submission_count": len(similar_history) + 1,
            "first_seen": similar_history[-1].get("uploaded_at"),
            "diff_summary": diff_result.get("summary") if diff_result else None,
            "financial_changes": diff_result.get("financial_changes", 0) if diff_result else 0,
            "metadata": {
                "match_type": "content_fingerprint",
                "diff": diff_result,
            }
        }

    # ── FIRST SUBMISSION ──────────────────────────────────────────────────────
    return {
        "layer": LayerName.VERSION_DIFF, "passed": True, "flags": [],
        "score_contribution": 0.0,
        "summary": f"First submission of '{filename}'. Document fingerprint recorded in database.",
        "processing_time_ms": int((time.time() - t0) * 1000),
        "is_resubmission": False,
        "submission_count": 1,
        "first_seen": None,
        "diff_summary": None,
        "financial_changes": 0,
        "metadata": {"match_type": "new_document"}
    }


def _analyze_diff(filename: str, new_text: str, old_text: str,
                  previous: Dict) -> Tuple[List[Flag], Optional[Dict]]:
    if not old_text or not new_text:
        return [], None

    diff_result = _compute_diff(old_text, new_text)
    if not diff_result["changed_lines"]:
        return [], diff_result

    flags = []
    financial_changes = diff_result["financial_change_count"]
    total_changes = diff_result["changed_line_count"]
    prev_date = previous.get("uploaded_at", "unknown")

    if financial_changes >= 3:
        sev, conf = Severity.CRITICAL, 0.95
    elif financial_changes >= 1:
        sev, conf = Severity.HIGH, 0.85
    elif total_changes >= 5:
        sev, conf = Severity.MEDIUM, 0.70
    else:
        sev, conf = Severity.LOW, 0.55

    changed_samples = diff_result.get("financial_samples", [])[:3]

    flags.append(Flag(
        flag_type="document_modification_detected",
        severity=sev,
        description=(
            f"Document '{filename}' was previously submitted on {prev_date} "
            f"and has since been modified. {total_changes} line(s) changed, "
            f"of which {financial_changes} contain financial figures. "
            f"Modified financial lines: {'; '.join(changed_samples[:2]) or 'see diff'}."
        ),
        confidence=conf,
        metadata={
            "previous_submission": prev_date,
            "total_changed_lines": total_changes,
            "financial_changed_lines": financial_changes,
            "changed_samples": changed_samples,
            "diff_summary": diff_result.get("summary", ""),
        },
        source_layer=LayerName.VERSION_DIFF,
    ))

    return flags, diff_result


def _compute_diff(old_text: str, new_text: str) -> Dict:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=1))
    changed = [l for l in diff if l.startswith(("+","-")) and not l.startswith(("---","+++"))]
    financial = [l for l in changed if FINANCIAL_LINE_PATTERN.search(l)]

    # Extract readable samples
    financial_samples = []
    for line in financial[:5]:
        prefix = "ADDED: " if line.startswith("+") else "REMOVED: "
        financial_samples.append(prefix + line[1:].strip()[:60])

    parts = []
    if financial:
        parts.append(f"{len(financial)} financial figure(s) changed")
    non_fin = len(changed) - len(financial)
    if non_fin > 0:
        parts.append(f"{non_fin} other line(s) changed")

    return {
        "changed_lines": changed[:20],
        "changed_line_count": len(changed),
        "financial_changes": financial,
        "financial_change_count": len(financial),
        "financial_samples": financial_samples,
        "summary": ". ".join(parts) if parts else "Minor whitespace/formatting changes only.",
        "raw_diff": "\n".join(diff[:40]),
    }


def _severity_score(sev: Severity) -> float:
    return {Severity.CRITICAL: 40.0, Severity.HIGH: 25.0, Severity.MEDIUM: 12.0, Severity.LOW: 5.0}.get(sev, 8.0)


def _error_result(msg: str, t0: float) -> Dict:
    return {
        "layer": LayerName.VERSION_DIFF, "passed": True, "flags": [],
        "score_contribution": 0.0, "summary": msg,
        "processing_time_ms": int((time.time() - t0) * 1000),
        "is_resubmission": False, "submission_count": 1,
        "first_seen": None, "diff_summary": None, "financial_changes": 0, "metadata": {}
    }


def _build_summary(flags: List[Flag], history: List) -> str:
    if not flags:
        return "No suspicious modifications between document submissions."
    crit = [f for f in flags if f.severity == Severity.CRITICAL]
    count = len(history) + 1
    if crit:
        return (f"CRITICAL: Document modified across {count} submissions. "
                f"Financial figures altered between submissions — strong evidence of deliberate fraud.")
    return (f"HIGH RISK: Document was modified between submissions. "
            f"Financial content changed — cross-submission comparison required.")
