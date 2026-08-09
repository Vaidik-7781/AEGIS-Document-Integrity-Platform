import cv2
import numpy as np
from PIL import Image
import io
import base64
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from models import Flag, FlagLocation, Severity, LayerName
from config import settings

logger = logging.getLogger(__name__)

# ── CONSTANTS ──────────────────────────────────────────────────────────────────
ELA_QUALITIES = [70, 80, 90]       # Multi-quality ELA
CLONE_PATCH_SIZE = 16              # For copy-move detection
MIN_TAMPERED_AREA = 300            # Min contour area to flag
HIGH_ELA_THRESHOLD = 40.0         # High suspicion
CRITICAL_ELA_THRESHOLD = 60.0     # Critical suspicion


def run(parsed_doc: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    images = parsed_doc.get("images", [])

    if not images:
        return _no_images_result(t0)

    all_flags: List[Flag] = []
    annotated: List[Dict] = []
    total_score = 0.0
    aggregate_ela_mean = 0.0
    aggregate_tampered_pct = 0.0

    for img_data in images:
        r = _analyze_single_image(img_data)
        if r is None:
            continue

        all_flags.extend(r["flags"])
        total_score += r["score"]
        aggregate_ela_mean += r["ela_mean"]
        aggregate_tampered_pct += r["tampered_pct"]
        if r.get("annotated_b64"):
            annotated.append({"page": img_data.get("page", 0), "b64": r["annotated_b64"]})

    n = max(len(images), 1)
    final_score = min(total_score, 40.0)

    return {
        "layer": LayerName.ELA,
        "passed": len(all_flags) == 0,
        "flags": [f.model_dump() for f in all_flags],
        "score_contribution": final_score,
        "summary": _build_summary(all_flags, images),
        "processing_time_ms": int((time.time() - t0) * 1000),
        "ela_mean": round(aggregate_ela_mean / n, 2),
        "ela_max": 0.0,
        "tampered_percentage": round(aggregate_tampered_pct / n, 2),
        "annotated_images": annotated,
        "metadata": {
            "images_analyzed": len(images),
            "images_flagged": sum(1 for f in all_flags if f.severity in (Severity.HIGH, Severity.CRITICAL)),
        }
    }


def _analyze_single_image(img_data: Dict) -> Optional[Dict]:
    raw = img_data.get("bytes", b"")
    if not raw:
        return None
    try:
        original = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        logger.debug("ELA: cannot open image: %s", e)
        return None

    # ── 1. MULTI-QUALITY ELA ─────────────────────────────────────────────────
    ela_maps = []
    for q in ELA_QUALITIES:
        buf = io.BytesIO()
        original.save(buf, format="JPEG", quality=q)
        buf.seek(0)
        recomp = Image.open(buf).convert("RGB")
        diff = np.abs(np.array(original, dtype=np.float32) - np.array(recomp, dtype=np.float32))
        ela_maps.append(diff)

    ela_combined = np.mean(ela_maps, axis=0)
    ela_amplified = np.clip(ela_combined * settings.ELA_AMPLIFY, 0, 255).astype(np.uint8)
    ela_gray = cv2.cvtColor(ela_amplified, cv2.COLOR_RGB2GRAY)

    ela_mean = float(np.mean(ela_gray))
    ela_std  = float(np.std(ela_gray))
    ela_max  = float(np.max(ela_gray))
    _, thresh = cv2.threshold(ela_gray, settings.ELA_THRESHOLD * 2, 255, cv2.THRESH_BINARY)
    total_px = thresh.shape[0] * thresh.shape[1]
    tampered_px = int(np.sum(thresh > 0))
    tampered_pct = round((tampered_px / max(total_px, 1)) * 100, 2)

    # ── 2. NOISE INCONSISTENCY ───────────────────────────────────────────────
    noise_score = _noise_analysis(np.array(original))

    # ── 3. BLOCKING ARTIFACT DETECTION ──────────────────────────────────────
    block_score = _blocking_artifact_score(ela_gray)

    # ── 4. COMPOSITE SUSPICION SCORE ────────────────────────────────────────
    suspicion = (
        0.50 * (ela_mean / 100.0) +
        0.25 * (tampered_pct / 100.0) +
        0.15 * noise_score +
        0.10 * block_score
    )

    flags: List[Flag] = []
    score = 0.0

    if ela_mean > CRITICAL_ELA_THRESHOLD or tampered_pct > 25.0:
        severity = Severity.CRITICAL
        score = 35.0
    elif ela_mean > HIGH_ELA_THRESHOLD or tampered_pct > 12.0:
        severity = Severity.HIGH
        score = 22.0
    elif ela_mean > settings.ELA_THRESHOLD or tampered_pct > 5.0:
        severity = Severity.MEDIUM
        score = 12.0
    else:
        severity = None

    annotated_b64 = None
    if severity:
        contours = _find_tampered_contours(thresh)
        desc = (
            f"Multi-quality ELA detected pixel-level manipulation. "
            f"Mean error {ela_mean:.1f}/255 across {len(ELA_QUALITIES)} compression levels. "
            f"{tampered_pct:.1f}% of image pixels show abnormal compression artifacts "
            f"(noise inconsistency: {noise_score:.2f}, block artifact score: {block_score:.2f}). "
            f"{len(contours)} distinct tampered region(s) identified."
        )
        flags.append(Flag(
            flag_type="visual_tampering",
            severity=severity,
            description=desc,
            confidence=min(0.99, suspicion + 0.3),
            location=FlagLocation(
                page=img_data.get("page", 0),
                image_index=img_data.get("index", 0) if hasattr(FlagLocation, 'image_index') else None,
            ),
            metadata={
                "ela_mean": round(ela_mean, 2),
                "ela_max": round(ela_max, 2),
                "ela_std": round(ela_std, 2),
                "tampered_pct": tampered_pct,
                "noise_score": round(noise_score, 3),
                "block_score": round(block_score, 3),
                "contour_count": len(contours),
            },
            source_layer=LayerName.ELA,
        ))
        annotated_b64 = _annotate_image(original, thresh, contours)

    return {
        "flags": flags, "score": score,
        "ela_mean": ela_mean, "tampered_pct": tampered_pct,
        "annotated_b64": annotated_b64,
    }


def _noise_analysis(img_arr: np.ndarray) -> float:
    gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY).astype(np.float32)
    h, w = gray.shape
    if h < 32 or w < 32:
        return 0.0
    block_size = 16
    noise_levels = []
    for y in range(0, h - block_size, block_size):
        for x in range(0, w - block_size, block_size):
            block = gray[y:y+block_size, x:x+block_size]
            noise_levels.append(np.std(block - cv2.blur(block, (3, 3))))
    if not noise_levels:
        return 0.0
    arr = np.array(noise_levels)
    # High variance in noise = inconsistent = suspicious
    return float(np.std(arr) / (np.mean(arr) + 1e-6))


def _blocking_artifact_score(ela_gray: np.ndarray) -> float:
    h, w = ela_gray.shape
    block_size = 8
    boundaries = []
    for y in range(block_size, h - block_size, block_size):
        row_diff = np.abs(ela_gray[y, :].astype(float) - ela_gray[y-1, :].astype(float))
        boundaries.append(np.mean(row_diff))
    for x in range(block_size, w - block_size, block_size):
        col_diff = np.abs(ela_gray[:, x].astype(float) - ela_gray[:, x-1].astype(float))
        boundaries.append(np.mean(col_diff))
    if not boundaries:
        return 0.0
    avg_boundary = np.mean(boundaries)
    avg_interior = np.mean(ela_gray)
    return float(avg_boundary / (avg_interior + 1.0))


def _find_tampered_contours(thresh: np.ndarray) -> List[Tuple]:
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if cv2.contourArea(c) > MIN_TAMPERED_AREA]


def _annotate_image(original: Image.Image, thresh: np.ndarray, contours: List) -> Optional[str]:
    try:
        img_cv = cv2.cvtColor(np.array(original), cv2.COLOR_RGB2BGR)
        # Draw heat overlay
        heat = cv2.applyColorMap(thresh, cv2.COLORMAP_HOT)
        overlay = cv2.addWeighted(img_cv, 0.7, heat, 0.3, 0)
        # Draw bounding boxes
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(overlay, "TAMPERED", (x, max(y-6, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)
        out = Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.debug("Annotation error: %s", e)
        return None


def _no_images_result(t0: float) -> Dict:
    return {
        "layer": LayerName.ELA, "passed": True, "flags": [],
        "score_contribution": 0.0, "ela_mean": 0.0, "ela_max": 0.0,
        "tampered_percentage": 0.0, "annotated_images": [],
        "processing_time_ms": int((time.time() - t0) * 1000),
        "summary": "No images found in document — ELA analysis skipped.",
        "metadata": {"images_analyzed": 0},
    }


def _build_summary(flags: List[Flag], images: List) -> str:
    if not flags:
        return f"ELA analysis complete. {len(images)} image(s) passed all compression integrity checks."
    crit = [f for f in flags if f.severity == Severity.CRITICAL]
    high = [f for f in flags if f.severity == Severity.HIGH]
    if crit:
        return (f"CRITICAL: {len(crit)} image(s) show strong multi-algorithm ELA evidence of digital manipulation. "
                f"Pixel compression patterns are inconsistent with authentic document scanning.")
    return (f"HIGH RISK: {len(high)} image(s) show significant ELA anomalies. "
            f"Compression artifacts indicate targeted editing of document regions.")
