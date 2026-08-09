import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import uuid
import json
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from config import settings
from database import init_db, save_analysis_result, get_analysis_result, get_history, get_stats, get_blockchain_record
from ingestor import parse_document
from aggregator import compute_score, build_report
from models import ProgressEvent, LayerName, Verdict, AnalysisResult
from layers import ela, blockchain, contradiction, font_forensics, version_diff

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("aegis.main")
_start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("AEGIS v%s starting on %s:%s", settings.APP_VERSION, settings.HOST, settings.PORT)
    yield
    logger.info("AEGIS shutting down.")


app = FastAPI(
    title="AEGIS API",
    description="Intelligent Document Integrity Platform for Banking Underwriting",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── UTILS ──────────────────────────────────────────────────────────────────────

def _parse_all(files_data: list) -> tuple[list, list]:
    parsed, errors = [], []
    for name, data in files_data:
        doc = parse_document(data, name)
        if doc.get("error") and doc["type"] == "unknown":
            errors.append(f"{name}: {doc['error']}")
        else:
            parsed.append(doc)
    return parsed, errors


async def _run_layer(executor, fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fn, *args)


def _serialize_result(result: dict) -> dict:
    return json.loads(json.dumps(result, default=str))


# ── ROUTES ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
def health():
    try:
        stats = get_stats()
        db_ok = True
    except Exception:
        stats = {}
        db_ok = False

    ai_ok = bool(settings.GEMINI_API_KEY)
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "db_connected": db_ok,
        "ai_available": ai_ok,
        "stats": stats,
    }


@app.post("/analyze")
async def analyze(
    files: List[UploadFile] = File(...),
    applicant_id: Optional[str] = Query(default=None),
):
    t0 = time.time()
    submission_id = str(uuid.uuid4())

    if not files:
        raise HTTPException(400, "No files provided.")
    if len(files) > settings.MAX_FILES_PER_SUBMISSION:
        raise HTTPException(400, f"Max {settings.MAX_FILES_PER_SUBMISSION} files per submission.")

    # Read files
    files_data = []
    for f in files:
        data = await f.read()
        if len(data) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"{f.filename} exceeds {settings.MAX_FILE_SIZE_MB}MB limit.")
        files_data.append((f.filename, data))

    # Parse
    parsed_docs, parse_errors = _parse_all(files_data)
    if not parsed_docs:
        raise HTTPException(422, f"Could not parse documents: {'; '.join(parse_errors)}")

    filenames = [d["filename"] for d in parsed_docs]

    # Run all 5 layers in parallel
    layer_results = await asyncio.gather(
        _run_layer(None, _run_ela_all, parsed_docs),
        _run_layer(None, _run_blockchain_all, parsed_docs),
        _run_layer(None, _run_contradiction_all, parsed_docs),
        _run_layer(None, _run_font_all, parsed_docs),
        _run_layer(None, _run_version_all, parsed_docs, applicant_id, submission_id),
    )
    layer_results = list(layer_results)

    # Score
    score_data = compute_score(layer_results)
    report_text = build_report(layer_results, score_data, filenames, applicant_id)

    # Collect all flags
    all_flags = []
    for r in layer_results:
        for flag in r.get("flags", []):
            flag["source_layer"] = r.get("layer", "")
            all_flags.append(flag)

    critical = sum(1 for f in all_flags if f.get("severity") == "critical")
    high = sum(1 for f in all_flags if f.get("severity") == "high")
    processing_ms = int((time.time() - t0) * 1000)

    result = {
        "submission_id": submission_id,
        "applicant_id": applicant_id,
        "risk_score": score_data.risk_score,
        "verdict": score_data.verdict.value,
        "risk_level": score_data.risk_level.value,
        "total_flags": len(all_flags),
        "critical_flags": critical,
        "high_flags": high,
        "filenames": filenames,
        "layer_results": [_serialize_result(r) for r in layer_results],
        "score_data": _serialize_result(score_data.model_dump()),
        "all_flags": [_serialize_result(f) for f in all_flags],
        "report_text": report_text,
        "processing_time_ms": processing_ms,
        "parse_errors": parse_errors,
    }

    save_analysis_result(result)
    logger.info("Analysis %s: score=%.1f verdict=%s flags=%d time=%dms",
                submission_id, score_data.risk_score, score_data.verdict.value, len(all_flags), processing_ms)

    return JSONResponse(content=result)


# ── WEBSOCKET — REAL-TIME ANALYSIS ────────────────────────────────────────────

@app.websocket("/ws/analyze")
async def ws_analyze(websocket: WebSocket):
    await websocket.accept()
    submission_id = str(uuid.uuid4())
    t0 = time.time()

    try:
        # Receive metadata
        meta = await websocket.receive_json()
        applicant_id = meta.get("applicant_id")

        await websocket.send_json({
            "event": "start",
            "submission_id": submission_id,
            "message": "Connected. Send file data.",
            "progress_pct": 0,
        })

        # Receive file data as JSON [{name, b64}]
        file_msg = await websocket.receive_json()
        files_raw = file_msg.get("files", [])
        if not files_raw:
            await websocket.send_json({"event": "error", "message": "No files received.", "submission_id": submission_id})
            return

        # Decode files
        import base64
        files_data = []
        for f in files_raw:
            data = base64.b64decode(f["data"])
            files_data.append((f["name"], data))

        # Parse
        parsed_docs, parse_errors = _parse_all(files_data)
        if not parsed_docs:
            await websocket.send_json({"event": "error", "message": "Parse failed.", "submission_id": submission_id})
            return

        filenames = [d["filename"] for d in parsed_docs]

        # Run each layer sequentially with progress updates
        layer_fns = [
            (LayerName.ELA, "L1 Visual ELA Scanner", lambda: _run_ela_all(parsed_docs)),
            (LayerName.BLOCKCHAIN, "L2 Blockchain Verification", lambda: _run_blockchain_all(parsed_docs)),
            (LayerName.CONTRADICTION, "L3 AI Contradiction Engine", lambda: _run_contradiction_all(parsed_docs)),
            (LayerName.FONT_FORENSICS, "L4 Font Forensics", lambda: _run_font_all(parsed_docs)),
            (LayerName.VERSION_DIFF, "L5 Version Diff", lambda: _run_version_all(parsed_docs, applicant_id, submission_id)),
        ]

        layer_results = []
        for i, (layer_name, label, fn) in enumerate(layer_fns):
            pct = int((i / len(layer_fns)) * 80)
            await websocket.send_json({
                "event": "layer_start",
                "submission_id": submission_id,
                "layer": layer_name.value,
                "message": f"Running {label}…",
                "progress_pct": pct,
            })

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, fn)
            layer_results.append(result)

            await websocket.send_json({
                "event": "layer_complete",
                "submission_id": submission_id,
                "layer": layer_name.value,
                "message": f"{label} complete — {'PASSED' if result.get('passed') else 'FLAGGED'}",
                "progress_pct": pct + 16,
                "layer_result": _serialize_result(result),
            })

        # Score and save
        score_data = compute_score(layer_results)
        report_text = build_report(layer_results, score_data, filenames, applicant_id)
        all_flags = []
        for r in layer_results:
            for flag in r.get("flags", []):
                flag["source_layer"] = r.get("layer", "")
                all_flags.append(flag)

        processing_ms = int((time.time() - t0) * 1000)
        full_result = {
            "submission_id": submission_id,
            "applicant_id": applicant_id,
            "risk_score": score_data.risk_score,
            "verdict": score_data.verdict.value,
            "risk_level": score_data.risk_level.value,
            "total_flags": len(all_flags),
            "critical_flags": sum(1 for f in all_flags if f.get("severity") == "critical"),
            "filenames": filenames,
            "layer_results": [_serialize_result(r) for r in layer_results],
            "score_data": _serialize_result(score_data.model_dump()),
            "all_flags": [_serialize_result(f) for f in all_flags],
            "report_text": report_text,
            "processing_time_ms": processing_ms,
        }
        save_analysis_result(full_result)

        await websocket.send_json({
            "event": "done",
            "submission_id": submission_id,
            "message": f"Analysis complete. Score: {score_data.risk_score}/100 — {score_data.verdict.value}",
            "progress_pct": 100,
            "result": full_result,
        })

    except WebSocketDisconnect:
        logger.info("WS client disconnected: %s", submission_id)
    except Exception as e:
        logger.error("WS error %s: %s", submission_id, e)
        try:
            await websocket.send_json({"event": "error", "submission_id": submission_id, "message": str(e)})
        except Exception:
            pass


@app.get("/report/{submission_id}")
def get_report(submission_id: str):
    result = get_analysis_result(submission_id)
    if not result:
        raise HTTPException(404, "Report not found.")
    return JSONResponse(content=result)


@app.get("/report/{submission_id}/text")
def get_report_text(submission_id: str):
    result = get_analysis_result(submission_id)
    if not result:
        raise HTTPException(404, "Report not found.")
    return PlainTextResponse(content=result.get("report_text", ""))


@app.get("/history")
def history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    verdict: Optional[str] = Query(default=None),
):
    return get_history(page=page, per_page=per_page, verdict_filter=verdict)


@app.get("/stats")
def stats():
    return get_stats()


@app.get("/hash/{file_hash}")
def check_hash(file_hash: str):
    record = get_blockchain_record(file_hash)
    if record:
        return {"found": True, "hash": file_hash, "notarized_at": record.get("notarized_at"),
                "tx_hash": record.get("tx_hash"), "network": record.get("network"), "tampered": False}
    return {"found": False, "hash": file_hash, "tampered": False}


# ── LAYER RUNNER HELPERS (sync, for executor) ──────────────────────────────────

def _run_ela_all(docs):
    results, total_score = [], 0.0
    all_flags, all_images = [], []
    for doc in docs:
        r = ela.run(doc)
        all_flags.extend(r.get("flags", []))
        all_images.extend(r.get("annotated_images", []))
        total_score += r.get("score_contribution", 0)
    return {
        "layer": LayerName.ELA.value, "passed": len(all_flags) == 0,
        "flags": all_flags, "score_contribution": min(total_score, 40.0),
        "summary": "; ".join(set(r.get("summary","") for r in [ela.run(d) for d in docs[:1]])),
        "annotated_images": all_images,
        "processing_time_ms": sum(r.get("processing_time_ms",0) for r in [ela.run(d) for d in []]),
        "metadata": {"docs": len(docs)},
    }


def _run_blockchain_all(docs):
    results, all_flags = [], []
    hashes, txs = [], []
    total_score = 0.0
    summaries = []
    for doc in docs:
        r = blockchain.run(doc)
        results.append(r)
        all_flags.extend(r.get("flags", []))
        hashes.extend(r.get("document_hashes", []))
        txs.extend(r.get("tx_hashes", []))
        total_score += r.get("score_contribution", 0)
        summaries.append(r.get("summary", ""))
    return {
        "layer": LayerName.BLOCKCHAIN.value, "passed": len(all_flags) == 0,
        "flags": all_flags, "score_contribution": min(total_score, 45.0),
        "summary": " | ".join(s for s in summaries if s)[:400],
        "document_hashes": hashes, "notarized": True, "tampered": False,
        "tx_hashes": txs, "processing_time_ms": 0, "metadata": {}
    }


def _run_contradiction_all(docs):
    return contradiction.run(docs)


def _run_font_all(docs):
    results, all_flags = [], []
    total_score = 0.0
    all_fonts_stats = {}
    summaries = []
    for doc in docs:
        r = font_forensics.run(doc)
        results.append(r)
        all_flags.extend(r.get("flags", []))
        total_score += r.get("score_contribution", 0)
        summaries.append(r.get("summary", ""))
        if r.get("font_stats"):
            all_fonts_stats = r["font_stats"]
    return {
        "layer": LayerName.FONT_FORENSICS.value, "passed": len(all_flags) == 0,
        "flags": all_flags, "score_contribution": min(total_score, 40.0),
        "summary": " | ".join(s for s in summaries if s)[:400],
        "font_stats": all_fonts_stats, "unique_fonts": all_fonts_stats.get("unique_fonts", []),
        "anomaly_count": len(all_flags), "processing_time_ms": 0, "metadata": {}
    }


def _run_version_all(docs, applicant_id, submission_id):
    results, all_flags = [], []
    total_score = 0.0
    summaries = []
    for doc in docs:
        r = version_diff.run(doc, applicant_id=applicant_id, submission_id=submission_id)
        results.append(r)
        all_flags.extend(r.get("flags", []))
        total_score += r.get("score_contribution", 0)
        summaries.append(r.get("summary", ""))
    return {
        "layer": LayerName.VERSION_DIFF.value, "passed": len(all_flags) == 0,
        "flags": all_flags, "score_contribution": min(total_score, 40.0),
        "summary": " | ".join(s for s in summaries if s)[:400],
        "is_resubmission": any(r.get("is_resubmission") for r in results),
        "submission_count": max((r.get("submission_count",1) for r in results), default=1),
        "diff_summary": next((r.get("diff_summary") for r in results if r.get("diff_summary")), None),
        "financial_changes": sum(r.get("financial_changes",0) for r in results),
        "processing_time_ms": 0, "metadata": {}
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
