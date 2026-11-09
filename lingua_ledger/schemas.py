"""Document schemas and the result envelope shared by extraction, validation and evaluation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class DocType(str, Enum):
    invoice = "invoice"
    receipt = "receipt"
    form = "form"
    contract = "contract"


class LineItem(BaseModel):
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total: float | None = None


class Invoice(BaseModel):
    vendor_name: str | None = None
    vendor_address: str | None = None
    vendor_tax_id: str | None = None
    customer_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = Field(None, description="ISO 8601 date, YYYY-MM-DD")
    due_date: str | None = Field(None, description="ISO 8601 date, YYYY-MM-DD")
    currency: str | None = Field(None, description="ISO 4217 code, e.g. EUR")
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax_rate: float | None = Field(None, description="Percent, e.g. 19 for 19%")
    tax_amount: float | None = None
    total: float | None = None
    iban: str | None = None
    payment_terms: str | None = None


class Receipt(BaseModel):
    merchant_name: str | None = None
    merchant_address: str | None = None
    date: str | None = Field(None, description="ISO 8601 date, YYYY-MM-DD")
    time: str | None = Field(None, description="HH:MM, 24 hour")
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax_amount: float | None = None
    service_charge: float | None = None
    discount: float | None = None
    total: float | None = None
    cash_paid: float | None = None
    change: float | None = None
    payment_method: str | None = None


class KeyValue(BaseModel):
    key: str
    value: str


class Form(BaseModel):
    title: str | None = None
    fields: list[KeyValue] = Field(
        default_factory=list, description="Every labelled field with its filled value"
    )


class Contract(BaseModel):
    document_name: str | None = None
    parties: list[str] = Field(default_factory=list)
    agreement_date: str | None = Field(None, description="ISO 8601 date")
    effective_date: str | None = Field(None, description="ISO 8601 date")
    expiration_date: str | None = Field(None, description="ISO 8601 date")
    governing_law: str | None = None
    renewal_term: str | None = None
    notice_period_to_terminate: str | None = None
    contract_type: str | None = None


SCHEMAS: dict[DocType, type[BaseModel]] = {
    DocType.invoice: Invoice,
    DocType.receipt: Receipt,
    DocType.form: Form,
    DocType.contract: Contract,
}


class Word(BaseModel):
    text: str
    conf: float = Field(description="OCR confidence 0-100")
    x0: int
    y0: int
    x1: int
    y1: int
    page: int = 0
    line: int = 0


class OcrPage(BaseModel):
    page: int
    width: int
    height: int
    words: list[Word]

    def text(self) -> str:
        lines: dict[int, list[Word]] = {}
        for w in self.words:
            lines.setdefault(w.line, []).append(w)
        ordered = sorted(lines.values(), key=lambda ws: (min(x.y0 for x in ws), min(x.x0 for x in ws)))
        return "\n".join(" ".join(x.text for x in sorted(ws, key=lambda x: x.x0)) for ws in ordered)


class Classification(BaseModel):
    doc_type: DocType
    language: str = Field(description="ISO 639-1 code of the dominant language")
    confidence: float = 0.0


class PathOutput(BaseModel):
    path: Literal["vision", "ocr_text"]
    data: dict[str, Any]
    self_confidence: dict[str, float] = Field(
        default_factory=dict, description="Model self-reported 0-1 per field"
    )
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None
    error: str | None = None


class RuleResult(BaseModel):
    rule: str
    fields: list[str]
    passed: bool | None = Field(description="None when not applicable")
    message: str = ""


class FieldResult(BaseModel):
    field: str
    value: Any
    confidence: float
    raw_score: float
    agree: bool | None
    ocr_conf: float | None
    validator: Literal["pass", "fail", "na"]
    self_conf: float | None
    vision_value: Any = None
    ocr_value: Any = None
    bbox: list[int] | None = None
    page: int | None = None
    arbiter: Literal["vision", "ocr", "other", "unreadable"] | None = None
    arbiter_value: Any = None
    needs_review: bool = False


class ArbiterVerdict(BaseModel):
    field: str
    vision_value: Any = None
    ocr_value: Any = None
    choice: Literal["vision", "ocr", "other", "unreadable"]
    value: Any = None
    confidence: float = 0.0
    cropped: bool = True


class ArbiterResult(BaseModel):
    model: str | None = None
    disputes: int = 0
    verdicts: list[ArbiterVerdict] = Field(default_factory=list)
    latency_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


class Anomaly(BaseModel):
    code: str
    severity: Literal["info", "warn", "high"]
    message: str
    fields: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    doc_id: str
    classification: Classification
    data: dict[str, Any]
    fields: list[FieldResult]
    rules: list[RuleResult]
    paths: list[PathOutput]
    review_threshold: float
    review_rate: float
    pages: int
    latency_s: float
    arbiter: ArbiterResult | None = None
    anomalies: list[Anomaly] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)
