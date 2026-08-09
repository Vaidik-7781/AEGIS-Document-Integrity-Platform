import math
import logging
from datetime import datetime
from typing import List, Dict, Any
from models import (
    ScoreData, LayerBreakdown, Verdict, RiskLevel, Severity, LayerName,
    Flag, AnalysisResult
)
from config import settings

logger = logging.getLogger(__name__)

LAYER_WEIGHTS = {
    LayerName.ELA:            settings.WEIGHT_ELA,
    LayerName.BLOCKCHAIN:     settings.WEIGHT_BLOCKCHAIN,
    LayerName.CONTRADICTION:  settings.WEIGHT_CONTRADICTION,
    LayerName.FONT_FORENSICS: settings.WEIGHT_FONT,
    LayerName.VERSION_DIFF:   settings.WEIGHT_VERSION,
}

LAYER_MAX_CONTRIBUTIONS = {
    LayerName.ELA: 40.0,
    LayerName.BLOCKCHAIN: 45.0,
    LayerName.CONTRADICTION: 50.0,
    LayerName.FONT_FORENSICS: 40.0,
    LayerName.VERSION_DIFF: 40.0,
}

SEVERITY_BOOST = {
    Severity.CRITICAL: 1.35,
    Severity.HIGH: 1.15,
    Severity.MEDIUM: 1.0,
    Severity.LOW: 0.85,
}


def compute_score(layer_results: List[Dict[str, Any]]) -> ScoreData:
    """
    Bayesian-weighted risk score aggregation.
    Each layer contributes proportionally to its weight.
    Critical flags get a confidence-weighted boost.
    """
    total_score = 0.0
    breakdown: List[LayerBreakdown] = []

    for result in layer_results:
        layer_name_str = result.get("layer", "")
        try:
            layer_name = LayerName(layer_name_str)
        except ValueError:
            continue

        weight = LAYER_WEIGHTS.get(layer_name, 0)
        max_contribution = LAYER_MAX_CONTRIBUTIONS.get(layer_name, 40.0)
        raw_contribution = float(result.get("score_contribution", 0))

        # Apply confidence-weighted flag boost
        flags = result.get("flags", [])
        confidence_boost = _compute_confidence_boost(flags)
        boosted = raw_contribution * confidence_boost

        # Normalize to layer weight
        normalized = min(boosted, max_contribution)
        layer_score = (normalized / max_contribution) * weight
        layer_score = min(layer_score, weight)
        total_score += layer_score

        breakdown.append(LayerBreakdown(
            layer=layer_name,
            score=round(layer_score, 2),
            max_score=weight,
            passed=result.get("passed", True),
            flag_count=len(flags),
            summary=result.get("summary", "")[:200],
            weight_pct=weight,
        ))

    # Apply global severity penalty if multiple critical layers flagged
    critical_layers = sum(1 for b in breakdown if not b.passed and b.flag_count > 0)
    if critical_layers >= 3:
        total_score = min(total_score * 1.1, 100.0)

    final_score = round(min(total_score, 100.0), 1)
    verdict = _get_verdict(final_score)
    risk_level = _get_risk_level(final_score)

    return ScoreData(
        risk_score=final_score,
        verdict=verdict,
        risk_level=risk_level,
        layer_breakdown=breakdown,
        computed_at=datetime.utcnow(),
    )


def _compute_confidence_boost(flags: List[Dict]) -> float:
    if not flags:
        return 1.0
    total_weight = 0.0
    weighted_boost = 0.0
    for flag in flags:
        sev_str = flag.get("severity", "medium")
        try:
            sev = Severity(sev_str)
        except ValueError:
            sev = Severity.MEDIUM
        confidence = float(flag.get("confidence", 0.5))
        boost = SEVERITY_BOOST.get(sev, 1.0)
        weight = confidence
        weighted_boost += boost * weight
        total_weight += weight
    return weighted_boost / max(total_weight, 1.0)


def _get_verdict(score: float) -> Verdict:
    if score <= settings.APPROVE_THRESHOLD:
        return Verdict.APPROVE
    elif score <= settings.REVIEW_THRESHOLD:
        return Verdict.REVIEW
    return Verdict.REJECT


def _get_risk_level(score: float) -> RiskLevel:
    if score <= 20:  return RiskLevel.LOW
    elif score <= 40: return RiskLevel.MODERATE
    elif score <= 55: return RiskLevel.HIGH
    return RiskLevel.CRITICAL


def build_report(layer_results: List[Dict], score_data: ScoreData,
                 filenames: List[str], applicant_id: str = None) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    score = score_data.risk_score
    verdict = score_data.verdict.value
    risk = score_data.risk_level.value
    sep = "=" * 62
    thin = "-" * 62

    lines = [
        sep,
        "  AEGIS — FORENSIC DOCUMENT INTEGRITY REPORT",
        "  Intelligent Document Analysis Platform v3.0",
        sep,
        f"  Generated   : {now}",
        f"  Documents   : {', '.join(filenames)}",
        f"  Applicant   : {applicant_id or 'Not specified'}",
        f"  Risk Score  : {score}/100",
        f"  Risk Level  : {risk}",
        f"  Verdict     : {verdict}",
        sep, "",
    ]

    # Layer-by-layer breakdown
    lines += ["LAYER ANALYSIS", thin]
    layer_labels = {
        "ela":            "L1 · Visual ELA Scanner",
        "blockchain":     "L2 · Blockchain Verification",
        "contradiction":  "L3 · AI Contradiction Engine",
        "font_forensics": "L4 · Typography Forensics",
        "version_diff":   "L5 · Version History Diff",
    }
    for result in layer_results:
        layer = result.get("layer", "")
        label = layer_labels.get(layer, layer.upper())
        status = "✓ PASSED" if result.get("passed") else "✗ FLAGGED"
        contrib = result.get("score_contribution", 0)
        flags = result.get("flags", [])
        processing_ms = result.get("processing_time_ms", 0)

        lines.append(f"\n{label}  [{status}]  (+{contrib:.0f} risk points)  [{processing_ms}ms]")
        lines.append(f"  {result.get('summary','No summary.')}")

        if flags:
            lines.append(f"  Flags ({len(flags)}):")
            for flag in flags:
                sev = flag.get("severity","").upper()
                desc = flag.get("description","")
                conf = flag.get("confidence", 0)
                lines.append(f"  [{sev}] [{conf*100:.0f}%] {desc}")

    # All flags summary
    all_flags = []
    for result in layer_results:
        for flag in result.get("flags", []):
            flag["_source"] = result.get("layer", "")
            all_flags.append(flag)

    lines += ["", sep, "FLAGS SUMMARY", thin]
    if not all_flags:
        lines.append("No flags raised. Document bundle appears authentic.")
    else:
        for sev_filter in ["critical", "high", "medium", "low"]:
            batch = [f for f in all_flags if f.get("severity") == sev_filter]
            if batch:
                lines.append(f"\n{sev_filter.upper()} ({len(batch)}):")
                for f in batch:
                    src = f.get("_source","").upper()
                    conf = f.get("confidence", 0)
                    lines.append(f"  • [{src}] [{conf*100:.0f}%] {f.get('description','')}")

    # Recommendation
    lines += ["", sep, "RECOMMENDATION", thin, _get_recommendation(score, all_flags), "", sep,
              f"  AEGIS v3.0 · NODE-FORENSIC · Report auto-generated",
              f"  Retain this report for audit purposes.",
              sep]

    return "\n".join(lines)


def _get_recommendation(score: float, flags: List[Dict]) -> str:
    critical = [f for f in flags if f.get("severity") == "critical"]
    flag_types = list(set(f.get("flag_type","") for f in critical[:3]))

    if score <= settings.APPROVE_THRESHOLD:
        return (
            "Document bundle passes all integrity checks. Risk score is within acceptable threshold.\n"
            "Proceed with standard underwriting process. No additional verification required."
        )
    elif score <= settings.REVIEW_THRESHOLD:
        return (
            f"Risk score {score}/100 requires senior officer review before proceeding.\n"
            f"Key concerns: {', '.join(flag_types) if flag_types else 'see flags above'}.\n"
            "Request additional verified documentation from applicant. Do not approve without investigation."
        )
    else:
        return (
            f"HIGH RISK: Score {score}/100 exceeds rejection threshold ({settings.REVIEW_THRESHOLD}).\n"
            f"Evidence of document manipulation: {', '.join(flag_types) if flag_types else 'multiple anomalies'}.\n"
            "REJECT application. Flag applicant for fraud review.\n"
            "Retain ALL documents as evidence. Consider referral to fraud investigation unit.\n"
            "Do not return documents to applicant until legal review is complete."
        )
