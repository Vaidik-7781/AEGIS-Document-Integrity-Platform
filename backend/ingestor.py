import fitz
import hashlib
import io
import os
import re
import logging
from PIL import Image
from typing import Optional, List, Dict, Any
from models import DocumentType

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}
MAX_TEXT_LENGTH = 50_000


def parse_document(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return _parse_pdf(file_bytes, filename)
    elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp"}:
        return _parse_image(file_bytes, filename)
    return _error_doc(filename, f"Unsupported extension: {ext}", file_bytes)


def _parse_pdf(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages, all_fonts, all_images = [], [], []

        for page_num, page in enumerate(doc):
            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            page_text = ""
            page_fonts = []

            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        raw = span.get("text", "").strip()
                        if not raw:
                            continue
                        page_text += raw + " "
                        page_fonts.append({
                            "text": raw,
                            "font": span.get("font", ""),
                            "size": round(span.get("size", 0), 3),
                            "flags": span.get("flags", 0),
                            "color": span.get("color", 0),
                            "origin": span.get("origin", (0, 0)),
                            "bbox": list(span.get("bbox", [])),
                            "page": page_num,
                            "char_count": len(raw),
                            "has_digits": any(c.isdigit() for c in raw),
                        })

            all_fonts.extend(page_fonts)

            page_images = []
            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                try:
                    base_img = doc.extract_image(xref)
                    page_images.append({
                        "page": page_num,
                        "index": img_idx,
                        "bytes": base_img["image"],
                        "ext": base_img.get("ext", "png"),
                        "width": base_img.get("width", 0),
                        "height": base_img.get("height", 0),
                        "colorspace": base_img.get("colorspace", 0),
                    })
                    all_images.append(page_images[-1])
                except Exception as e:
                    logger.debug("Image extract error page %d img %d: %s", page_num, img_idx, e)

            pages.append({
                "page_num": page_num,
                "text": page_text.strip(),
                "fonts": page_fonts,
                "images": page_images,
                "width": page.rect.width,
                "height": page.rect.height,
                "rotation": page.rotation,
            })

        full_text = "\n".join(p["text"] for p in pages)[:MAX_TEXT_LENGTH]
        meta = doc.metadata or {}
        doc.close()

        return {
            "filename": filename,
            "type": "pdf",
            "text": full_text,
            "pages": pages,
            "images": all_images,
            "fonts": all_fonts,
            "metadata": {
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "creator": meta.get("creator", ""),
                "producer": meta.get("producer", ""),
                "creation_date": meta.get("creationDate", ""),
                "mod_date": meta.get("modDate", ""),
                "page_count": len(pages),
            },
            "raw_hash": compute_hash(file_bytes),
            "content_fingerprint": compute_content_fingerprint(full_text, all_fonts),
            "raw_bytes": file_bytes,
            "file_size": len(file_bytes),
            "document_type": _infer_doc_type(filename, full_text),
            "error": None,
        }
    except Exception as e:
        logger.error("PDF parse error for %s: %s", filename, e)
        return _error_doc(filename, str(e), file_bytes)


def _parse_image(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    try:
        img = Image.open(io.BytesIO(file_bytes))
        width, height = img.size
        mode = img.mode
    except Exception as e:
        return _error_doc(filename, str(e), file_bytes)

    img_data = {
        "page": 0, "index": 0,
        "bytes": file_bytes,
        "ext": os.path.splitext(filename)[1].replace(".", ""),
        "width": width, "height": height, "colorspace": 3,
    }
    return {
        "filename": filename,
        "type": "image",
        "text": "",
        "pages": [{"page_num": 0, "text": "", "fonts": [], "images": [img_data], "width": width, "height": height, "rotation": 0}],
        "images": [img_data],
        "fonts": [],
        "metadata": {"page_count": 1, "width": width, "height": height, "mode": mode},
        "raw_hash": compute_hash(file_bytes),
        "content_fingerprint": compute_hash(file_bytes),
        "raw_bytes": file_bytes,
        "file_size": len(file_bytes),
        "document_type": _infer_doc_type(filename, ""),
        "error": None,
    }


def _error_doc(filename: str, error: str, file_bytes: bytes) -> Dict[str, Any]:
    return {
        "filename": filename, "type": "unknown",
        "text": "", "pages": [], "images": [], "fonts": [],
        "metadata": {}, "raw_hash": compute_hash(file_bytes),
        "content_fingerprint": "", "raw_bytes": file_bytes,
        "file_size": len(file_bytes),
        "document_type": DocumentType.OTHER, "error": error,
    }


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_content_fingerprint(text: str, fonts: List[Dict]) -> str:
    normalized = " ".join(text.split()).lower()[:2000]
    font_sig = "|".join(f"{f['font']}:{f['size']}" for f in fonts[:20])
    return hashlib.sha256(f"{normalized}||{font_sig}".encode()).hexdigest()


def _infer_doc_type(filename: str, text: str) -> str:
    fn = filename.lower()
    tx = text.lower()
    patterns = {
        DocumentType.SALARY_SLIP: r"salary|payslip|pay slip|gross pay|net pay|basic pay|employee",
        DocumentType.ITR: r"income tax|itr|form 16|assessment year|pan\s*:|\btaxable\b",
        DocumentType.BANK_STATEMENT: r"bank statement|account statement|passbook|transaction|balance|debit|credit",
        DocumentType.LAND_RECORD: r"land record|property|survey no|khata|registry|ownership|area in|hectare|acre",
        DocumentType.LOAN_FORM: r"loan application|loan form|borrower|emi|repayment|sanctioned amount",
        DocumentType.IDENTITY: r"passport|aadhaar|voter id|driving licence|pan card",
    }
    for doc_type, pattern in patterns.items():
        if re.search(pattern, fn) or re.search(pattern, tx):
            return doc_type
    return DocumentType.OTHER
