import numpy as np
import time
import logging
import re
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple
from models import Flag, FlagLocation, Severity, LayerName
from config import settings

logger = logging.getLogger(__name__)

FINANCIAL_KEYWORDS = re.compile(r"[₹$€£]|(?:rs\.?|inr|amount|total|salary|income|balance|emi|loan|tax)\s*:?\s*[\d,]", re.IGNORECASE)
NUMERIC_PATTERN = re.compile(r"^\s*[₹$€£\-]?\s*[\d,]+\.?\d*\s*$")


def run(parsed_doc: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    fonts = parsed_doc.get("fonts", [])

    if len(fonts) < 10:
        return _no_fonts_result(t0, len(fonts))

    flags: List[Flag] = []
    total_score = 0.0

    # ── L4-A: FONT SIZE Z-SCORE ANALYSIS ─────────────────────────────────────
    size_flags = _check_size_anomalies(fonts)
    flags.extend(size_flags)
    total_score += sum(_severity_score(f.severity) for f in size_flags)

    # ── L4-B: FONT FAMILY CONSISTENCY ────────────────────────────────────────
    family_flags = _check_font_family_consistency(fonts)
    flags.extend(family_flags)
    total_score += sum(_severity_score(f.severity) for f in family_flags)

    # ── L4-C: TEXT COLOR ANOMALY ──────────────────────────────────────────────
    color_flags = _check_color_anomalies(fonts)
    flags.extend(color_flags)
    total_score += sum(_severity_score(f.severity) for f in color_flags)

    # ── L4-D: INTRA-LINE FONT MIXING ─────────────────────────────────────────
    line_flags = _check_intraline_mixing(fonts)
    flags.extend(line_flags)
    total_score += sum(_severity_score(f.severity) for f in line_flags)

    # ── L4-E: CHARACTER SPACING ANOMALY ──────────────────────────────────────
    spacing_flags = _check_character_spacing(fonts)
    flags.extend(spacing_flags)
    total_score += sum(_severity_score(f.severity) for f in spacing_flags)

    font_stats = _compute_stats(fonts)

    return {
        "layer": LayerName.FONT_FORENSICS,
        "passed": len(flags) == 0,
        "flags": [f.model_dump() for f in flags],
        "score_contribution": min(total_score, 40.0),
        "summary": _build_summary(flags, fonts),
        "processing_time_ms": int((time.time() - t0) * 1000),
        "font_stats": font_stats,
        "unique_fonts": font_stats.get("unique_fonts", []),
        "anomaly_count": len(flags),
        "metadata": {"spans_analyzed": len(fonts), "pages": len(set(f.get("page",0) for f in fonts))}
    }


def _check_size_anomalies(fonts: List[Dict]) -> List[Flag]:
    flags = []
    by_page = defaultdict(list)
    for span in fonts:
        by_page[span.get("page", 0)].append(span)

    for page_num, spans in by_page.items():
        sizes = [s["size"] for s in spans if s.get("size", 0) > 3]
        if len(sizes) < 8:
            continue

        mean_sz = float(np.mean(sizes))
        std_sz = float(np.std(sizes))
        if std_sz < 0.5:
            continue

        for span in spans:
            sz = span.get("size", 0)
            text = span.get("text", "").strip()
            if not text or sz < 3:
                continue

            is_financial = bool(FINANCIAL_KEYWORDS.search(text)) or bool(NUMERIC_PATTERN.match(text))
            if not is_financial:
                continue

            z = abs(sz - mean_sz) / std_sz if std_sz > 0 else 0
            if z < settings.FONT_ZSCORE_THRESHOLD:
                continue

            sev = Severity.CRITICAL if z > 5.0 else Severity.HIGH if z > 4.0 else Severity.MEDIUM
            flags.append(Flag(
                flag_type="font_size_anomaly",
                severity=sev,
                description=(
                    f"Numeric text '{text[:40]}' on page {page_num+1} uses font size {sz:.1f}pt "
                    f"— {z:.1f}σ from document mean {mean_sz:.1f}pt (std {std_sz:.2f}). "
                    f"Statistical outlier on financial figure consistent with character replacement."
                ),
                confidence=min(0.99, 0.5 + z * 0.08),
                location=FlagLocation(page=page_num, bbox=span.get("bbox"), text_sample=text[:60]),
                metadata={"z_score": round(z,2), "font_size": sz, "mean_size": round(mean_sz,2), "font": span.get("font","")},
                source_layer=LayerName.FONT_FORENSICS,
            ))
            if len(flags) >= 5:
                return flags

    return flags


def _check_font_family_consistency(fonts: List[Dict]) -> List[Flag]:
    flags = []
    by_page = defaultdict(list)
    for span in fonts:
        by_page[span.get("page", 0)].append(span)

    for page_num, spans in by_page.items():
        if len(spans) < 15:
            continue

        font_counts = defaultdict(int)
        for s in spans:
            base = _normalize_font(s.get("font", ""))
            if base:
                font_counts[base] += 1

        if not font_counts:
            continue

        total = sum(font_counts.values())
        dominant = max(font_counts, key=font_counts.get)
        dominant_ratio = font_counts[dominant] / total

        if dominant_ratio < 0.75:
            continue

        for span in spans:
            text = span.get("text", "").strip()
            base = _normalize_font(span.get("font", ""))
            if not text or not base or base == dominant:
                continue

            is_financial = bool(FINANCIAL_KEYWORDS.search(text)) or bool(NUMERIC_PATTERN.match(text))
            occurrences = font_counts.get(base, 0)

            if is_financial and occurrences <= 3:
                sev = Severity.HIGH if occurrences <= 1 else Severity.MEDIUM
                flags.append(Flag(
                    flag_type="suspicious_font_substitution",
                    severity=sev,
                    description=(
                        f"Financial text '{text[:40]}' on page {page_num+1} uses font '{span.get('font','')}' "
                        f"(appears {occurrences}x) while {dominant_ratio*100:.0f}% of document uses '{dominant}'. "
                        f"Rare foreign font on financial figure is strong indicator of text replacement."
                    ),
                    confidence=0.78 if occurrences == 1 else 0.65,
                    location=FlagLocation(page=page_num, bbox=span.get("bbox"), text_sample=text[:60]),
                    metadata={"anomalous_font": span.get("font",""), "dominant_font": dominant, "occurrences": occurrences},
                    source_layer=LayerName.FONT_FORENSICS,
                ))
                if len(flags) >= 4:
                    return flags

    return flags


def _check_color_anomalies(fonts: List[Dict]) -> List[Flag]:
    flags = []
    colors = [s.get("color", 0) for s in fonts if s.get("color") is not None]
    if not colors:
        return flags

    color_counts = defaultdict(int)
    for c in colors:
        color_counts[c] += 1

    total = len(colors)
    dominant = max(color_counts, key=color_counts.get)

    for span in fonts:
        color = span.get("color")
        text = span.get("text", "").strip()
        if color is None or color == dominant:
            continue

        is_financial = bool(FINANCIAL_KEYWORDS.search(text)) or bool(NUMERIC_PATTERN.match(text))
        if not is_financial:
            continue

        usage_ratio = color_counts.get(color, 0) / total
        if usage_ratio >= 0.05:
            continue

        color_hex = hex(color) if isinstance(color, int) else str(color)
        dominant_hex = hex(dominant) if isinstance(dominant, int) else str(dominant)
        flags.append(Flag(
            flag_type="text_color_anomaly",
            severity=Severity.MEDIUM,
            description=(
                f"Financial text '{text[:40]}' has unusual color {color_hex} "
                f"({usage_ratio*100:.1f}% of document) vs dominant {dominant_hex}. "
                f"Off-color on numeric content may indicate copy-paste from external source."
            ),
            confidence=0.60,
            location=FlagLocation(page=span.get("page", 0), text_sample=text[:60]),
            metadata={"color": color_hex, "dominant_color": dominant_hex, "usage_pct": round(usage_ratio*100, 2)},
            source_layer=LayerName.FONT_FORENSICS,
        ))
        if len(flags) >= 3:
            break

    return flags


def _check_intraline_mixing(fonts: List[Dict]) -> List[Flag]:
    flags = []
    lines: Dict[Tuple, List] = defaultdict(list)

    for span in fonts:
        bbox = span.get("bbox", [])
        if len(bbox) < 4:
            continue
        page = span.get("page", 0)
        y_bucket = round(bbox[1] / 4) * 4
        lines[(page, y_bucket)].append(span)

    for (page, y), line_spans in lines.items():
        if len(line_spans) < 2:
            continue

        line_text = " ".join(s.get("text","") for s in line_spans)
        has_financial = bool(FINANCIAL_KEYWORDS.search(line_text))
        if not has_financial:
            continue

        font_families = set(_normalize_font(s.get("font","")) for s in line_spans if s.get("font"))
        if len(font_families) < 2:
            continue

        flags.append(Flag(
            flag_type="intraline_font_mixing",
            severity=Severity.HIGH,
            description=(
                f"Financial line '{line_text[:50]}' on page {page+1} contains {len(font_families)} different "
                f"font families: {', '.join(sorted(font_families))}. "
                f"Mixed fonts within a single financial line strongly indicate character-level number replacement."
            ),
            confidence=0.82,
            location=FlagLocation(page=page, text_sample=line_text[:80]),
            metadata={"fonts": sorted(font_families), "line_text": line_text[:80]},
            source_layer=LayerName.FONT_FORENSICS,
        ))
        if len(flags) >= 3:
            break

    return flags


def _check_character_spacing(fonts: List[Dict]) -> List[Flag]:
    """Detect anomalous character spacing (kerning) on financial spans."""
    flags = []
    financial_spans = [s for s in fonts if bool(NUMERIC_PATTERN.match(s.get("text","").strip())) and s.get("bbox")]

    if len(financial_spans) < 4:
        return flags

    # Compute width-per-character as proxy for kerning
    widths = []
    for span in financial_spans:
        bbox = span.get("bbox", [0,0,0,0])
        text = span.get("text","")
        if len(text) < 2 or len(bbox) < 4:
            continue
        w = bbox[2] - bbox[0]
        chars = len(text.replace(" ",""))
        if chars > 0:
            widths.append((w / chars, span))

    if len(widths) < 4:
        return flags

    values = [v for v, _ in widths]
    mean_w = float(np.mean(values))
    std_w = float(np.std(values))
    if std_w < 0.5:
        return flags

    for w_per_char, span in widths:
        z = abs(w_per_char - mean_w) / std_w if std_w > 0 else 0
        if z > 3.5:
            text = span.get("text","").strip()
            flags.append(Flag(
                flag_type="kerning_anomaly",
                severity=Severity.MEDIUM,
                description=(
                    f"Numeric text '{text[:30]}' shows abnormal character spacing {w_per_char:.2f}px/char "
                    f"vs document mean {mean_w:.2f}px/char ({z:.1f}σ deviation). "
                    f"Kerning inconsistency on financial figures indicates replacement with externally rendered text."
                ),
                confidence=0.65,
                location=FlagLocation(page=span.get("page",0), bbox=span.get("bbox"), text_sample=text[:50]),
                metadata={"width_per_char": round(w_per_char,2), "mean": round(mean_w,2), "z_score": round(z,2)},
                source_layer=LayerName.FONT_FORENSICS,
            ))
            if len(flags) >= 2:
                break

    return flags


def _normalize_font(font: str) -> str:
    if not font:
        return ""
    f = font.lower()
    for suffix in ["-bold","-italic","-regular","-medium","-light",",bold",",italic","-condensed","-expanded"]:
        f = f.replace(suffix, "")
    return f.strip()


def _severity_score(sev: Severity) -> float:
    return {Severity.CRITICAL: 30.0, Severity.HIGH: 20.0, Severity.MEDIUM: 10.0, Severity.LOW: 5.0}.get(sev, 8.0)


def _compute_stats(fonts: List[Dict]) -> Dict:
    if not fonts:
        return {}
    sizes = [f["size"] for f in fonts if f.get("size", 0) > 0]
    font_names = [f.get("font","") for f in fonts if f.get("font")]
    return {
        "total_spans": len(fonts),
        "unique_fonts": list(set(font_names))[:15],
        "font_count": len(set(font_names)),
        "avg_size": round(float(np.mean(sizes)), 2) if sizes else 0,
        "size_std": round(float(np.std(sizes)), 2) if sizes else 0,
        "min_size": round(min(sizes), 2) if sizes else 0,
        "max_size": round(max(sizes), 2) if sizes else 0,
    }


def _no_fonts_result(t0: float, count: int) -> Dict:
    return {
        "layer": LayerName.FONT_FORENSICS, "passed": True, "flags": [],
        "score_contribution": 0.0,
        "summary": f"Insufficient font data ({count} spans) — font forensics skipped (image-only or sparse document).",
        "processing_time_ms": int((time.time() - t0) * 1000),
        "font_stats": {}, "unique_fonts": [], "anomaly_count": 0, "metadata": {}
    }


def _build_summary(flags: List[Flag], fonts: List[Dict]) -> str:
    if not flags:
        unique = len(set(f.get("font","") for f in fonts))
        return (f"Typography analysis complete. {len(fonts)} text spans across {unique} font(s). "
                f"No anomalies detected — consistent typography throughout.")
    crit = [f for f in flags if f.severity == Severity.CRITICAL]
    if crit:
        return (f"CRITICAL: {len(crit)} font anomaly/anomalies on financial figures. "
                f"Metrics deviate significantly from document baseline — consistent with targeted character-level replacement.")
    return (f"HIGH RISK: {len(flags)} typography anomaly/anomalies detected on financial content. "
            f"Manual review of flagged figures required.")
