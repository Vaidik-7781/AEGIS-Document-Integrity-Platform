from pydantic import BaseModel, Field, computed_field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import uuid


# ── ENUMS ─────────────────────────────────────────────────────────────────────

class Verdict(str, Enum):
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    REJECT = "REJECT"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class DocumentType(str, Enum):
    SALARY_SLIP = "salary_slip"
    ITR = "itr"
    BANK_STATEMENT = "bank_statement"
    LAND_RECORD = "land_record"
    LOAN_FORM = "loan_form"
    IDENTITY = "identity"
    OTHER = "other"

class LayerName(str, Enum):
    ELA = "ela"
    BLOCKCHAIN = "blockchain"
    CONTRADICTION = "contradiction"
    FONT_FORENSICS = "font_forensics"
    VERSION_DIFF = "version_diff"


# ── FLAG MODELS ────────────────────────────────────────────────────────────────

class FlagLocation(BaseModel):
    page: int = 0
    bbox: Optional[List[float]] = None
    text_sample: Optional[str] = None

class Flag(BaseModel):
    flag_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    flag_type: str
    severity: Severity
    description: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    location: Optional[FlagLocation] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_layer: Optional[LayerName] = None


# ── LAYER RESULT MODELS ────────────────────────────────────────────────────────

class LayerResult(BaseModel):
    layer: LayerName
    passed: bool
    flags: List[Flag] = Field(default_factory=list)
    score_contribution: float = Field(ge=0.0, default=0.0)
    summary: str = ""
    processing_time_ms: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def flag_count(self) -> int:
        return len(self.flags)

    @computed_field
    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == Severity.CRITICAL)


class ELAResult(LayerResult):
    layer: LayerName = LayerName.ELA
    ela_mean: float = 0.0
    ela_max: float = 0.0
    tampered_percentage: float = 0.0
    annotated_images: List[Dict[str, Any]] = Field(default_factory=list)


class BlockchainResult(LayerResult):
    layer: LayerName = LayerName.BLOCKCHAIN
    document_hashes: List[str] = Field(default_factory=list)
    notarized: bool = False
    tx_hashes: List[str] = Field(default_factory=list)
    tampered: bool = False


class ContradictionResult(LayerResult):
    layer: LayerName = LayerName.CONTRADICTION
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    contradictions_found: int = 0


class FontResult(LayerResult):
    layer: LayerName = LayerName.FONT_FORENSICS
    font_stats: Dict[str, Any] = Field(default_factory=dict)
    unique_fonts: List[str] = Field(default_factory=list)
    anomaly_count: int = 0


class VersionResult(LayerResult):
    layer: LayerName = LayerName.VERSION_DIFF
    is_resubmission: bool = False
    submission_count: int = 1
    diff_summary: Optional[str] = None
    financial_changes: int = 0


# ── SCORE BREAKDOWN ────────────────────────────────────────────────────────────

class LayerBreakdown(BaseModel):
    layer: LayerName
    score: float
    max_score: int
    passed: bool
    flag_count: int
    summary: str
    weight_pct: int


class ScoreData(BaseModel):
    risk_score: float = Field(ge=0.0, le=100.0)
    verdict: Verdict
    risk_level: RiskLevel
    layer_breakdown: List[LayerBreakdown] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def approve_probability(self) -> float:
        return max(0.0, 1.0 - (self.risk_score / 100.0))


# ── SUBMISSION / ANALYSIS ──────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    applicant_id: Optional[str] = None
    notes: Optional[str] = None


class DocumentInfo(BaseModel):
    filename: str
    file_size_bytes: int
    document_type: DocumentType = DocumentType.OTHER
    page_count: int = 1
    has_images: bool = False
    text_length: int = 0
    sha256_hash: str = ""


class AnalysisResult(BaseModel):
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    applicant_id: Optional[str] = None

    # Documents
    documents: List[DocumentInfo] = Field(default_factory=list)
    filenames: List[str] = Field(default_factory=list)

    # Results
    layer_results: List[LayerResult] = Field(default_factory=list)
    score_data: ScoreData

    # Summary
    total_flags: int = 0
    critical_flags: int = 0
    high_flags: int = 0
    all_flags: List[Flag] = Field(default_factory=list)

    # Report
    report_text: str = ""

    # Meta
    processing_time_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parse_errors: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def risk_score(self) -> float:
        return self.score_data.risk_score

    @computed_field
    @property
    def verdict(self) -> Verdict:
        return self.score_data.verdict


# ── WEBSOCKET PROGRESS ─────────────────────────────────────────────────────────

class ProgressEvent(BaseModel):
    event: Literal["start", "layer_start", "layer_complete", "done", "error"]
    submission_id: str
    message: str
    layer: Optional[LayerName] = None
    layer_result: Optional[Dict[str, Any]] = None
    progress_pct: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── API RESPONSES ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    uptime_seconds: float
    db_connected: bool
    ai_available: bool


class HashVerifyResponse(BaseModel):
    found: bool
    hash: str
    notarized_at: Optional[str] = None
    tx_hash: Optional[str] = None
    network: Optional[str] = None
    tampered: bool = False


class HistoryEntry(BaseModel):
    submission_id: str
    applicant_id: Optional[str]
    risk_score: float
    verdict: Verdict
    filenames: List[str]
    total_flags: int
    created_at: str


class HistoryResponse(BaseModel):
    total: int
    entries: List[HistoryEntry]
    page: int = 1
    per_page: int = 20
