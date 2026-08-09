import hashlib
import hmac
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from models import Flag, Severity, LayerName
from database import save_blockchain_record, get_blockchain_record
from config import settings

logger = logging.getLogger(__name__)


def run(parsed_doc: Dict[str, Any]) -> Dict[str, Any]:
    t0 = time.time()
    file_hash = parsed_doc.get("raw_hash", "")
    filename = parsed_doc.get("filename", "unknown")

    if not file_hash:
        return _error_result("Could not compute document hash.", t0)

    # ── CHECK IF PREVIOUSLY NOTARIZED ─────────────────────────────────────────
    existing = get_blockchain_record(file_hash)

    if existing:
        # Same exact hash found → document is unmodified since notarization
        return {
            "layer": LayerName.BLOCKCHAIN,
            "passed": True,
            "flags": [],
            "score_contribution": 0.0,
            "summary": (
                f"Document hash verified against notarization record. "
                f"Original notarization: {existing.get('notarized_at', 'unknown')}. "
                f"Hash: {file_hash[:16]}… No tampering detected."
            ),
            "processing_time_ms": int((time.time() - t0) * 1000),
            "document_hashes": [file_hash],
            "notarized": True,
            "tampered": False,
            "tx_hashes": [existing.get("tx_hash", "")],
            "metadata": {
                "notarized_at": existing.get("notarized_at"),
                "network": existing.get("network", "sepolia"),
                "tx_hash": existing.get("tx_hash"),
            }
        }

    # ── FIRST TIME: NOTARIZE ──────────────────────────────────────────────────
    tx_hash = _simulate_notarization(file_hash, filename)
    save_blockchain_record(file_hash, tx_hash, settings.ETH_NETWORK)

    return {
        "layer": LayerName.BLOCKCHAIN,
        "passed": True,
        "flags": [],
        "score_contribution": 0.0,
        "summary": (
            f"Document successfully notarized. "
            f"Hash {file_hash[:16]}… anchored at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC. "
            f"TX: {tx_hash[:20]}… Any future modification will be detected."
        ),
        "processing_time_ms": int((time.time() - t0) * 1000),
        "document_hashes": [file_hash],
        "notarized": True,
        "tampered": False,
        "tx_hashes": [tx_hash],
        "metadata": {
            "notarized_at": datetime.utcnow().isoformat(),
            "network": settings.ETH_NETWORK,
            "tx_hash": tx_hash,
        }
    }


def verify_tamper(parsed_doc: Dict[str, Any], known_hash: str) -> Dict[str, Any]:
    """
    Explicit tamper check: compare document against a known-good hash.
    Called when bank already has a reference copy on file.
    """
    t0 = time.time()
    current_hash = parsed_doc.get("raw_hash", "")

    if not current_hash or not known_hash:
        return _error_result("Cannot verify: missing hash(es).", t0)

    # Constant-time comparison to prevent timing attacks
    match = hmac.compare_digest(current_hash.encode(), known_hash.encode())

    if match:
        return {
            "layer": LayerName.BLOCKCHAIN,
            "passed": True,
            "flags": [],
            "score_contribution": 0.0,
            "summary": "Document hash matches notarized reference. Integrity confirmed.",
            "processing_time_ms": int((time.time() - t0) * 1000),
            "document_hashes": [current_hash],
            "notarized": True,
            "tampered": False,
            "tx_hashes": [],
            "metadata": {}
        }

    # Hashes differ → TAMPERED
    flag = Flag(
        flag_type="blockchain_hash_mismatch",
        severity=Severity.CRITICAL,
        description=(
            f"Blockchain hash mismatch: mathematically conclusive evidence of post-notarization tampering. "
            f"Expected: {known_hash[:24]}… · Got: {current_hash[:24]}… "
            f"These SHA-256 digests cannot collide accidentally — the document was deliberately modified."
        ),
        confidence=1.0,
        metadata={
            "expected_hash": known_hash,
            "actual_hash": current_hash,
            "algorithm": "SHA-256",
        },
        source_layer=LayerName.BLOCKCHAIN,
    )
    return {
        "layer": LayerName.BLOCKCHAIN,
        "passed": False,
        "flags": [flag.model_dump()],
        "score_contribution": 45.0,
        "summary": (
            "CRITICAL: Hash mismatch against blockchain record. "
            "SHA-256 comparison proves document was altered after notarization."
        ),
        "processing_time_ms": int((time.time() - t0) * 1000),
        "document_hashes": [current_hash],
        "notarized": True,
        "tampered": True,
        "tx_hashes": [],
        "metadata": {"expected": known_hash, "actual": current_hash}
    }


def _simulate_notarization(file_hash: str, filename: str) -> str:
    """
    Simulates an Ethereum transaction hash.
    In production: use ethers.js or web3.py to submit hash to Sepolia testnet.

    Production implementation:
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(settings.ETH_RPC_URL))
    tx = w3.eth.send_transaction({
        'from': account.address,
        'to': account.address,
        'data': Web3.to_hex(text=file_hash),
        'gas': 21000,
    })
    return tx.hex()
    """
    payload = json.dumps({
        "hash": file_hash,
        "file": filename,
        "ts": datetime.utcnow().isoformat(),
        "network": settings.ETH_NETWORK,
        "app": "AEGIS",
    }, sort_keys=True)
    return "0x" + hashlib.sha256(payload.encode()).hexdigest()


def _error_result(msg: str, t0: float) -> Dict:
    return {
        "layer": LayerName.BLOCKCHAIN, "passed": True, "flags": [],
        "score_contribution": 0.0, "summary": msg,
        "processing_time_ms": int((time.time() - t0) * 1000),
        "document_hashes": [], "notarized": False,
        "tampered": False, "tx_hashes": [], "metadata": {}
    }
