"""Persistent state for the demo: vendors seen, documents posted and reviewer corrections.

A single JSON file under STATE_DIR, rewritten atomically. Small enough that reading the whole file on every
request is fine; the container's disk is ephemeral so the store also stays in memory.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .anomaly import fingerprint, vendor_key
from .config import STATE_DIR
from .normalize import normalize_text


class Correction(BaseModel):
    doc_id: str
    doc_type: str
    field: str
    raw_score: float
    accepted: bool
    value: Any = None
    corrected_value: Any = None
    ts: float = Field(default_factory=time.time)


class VendorRecord(BaseModel):
    key: str
    name: str | None = None
    documents: int = 0
    invoice_numbers: list[str] = Field(default_factory=list)
    fingerprints: list[str] = Field(default_factory=list)
    ibans: list[str] = Field(default_factory=list)
    currencies: list[str] = Field(default_factory=list)
    tax_rates: list[float] = Field(default_factory=list)
    last_seen: float = 0.0


class State(BaseModel):
    vendors: dict[str, VendorRecord] = Field(default_factory=dict)
    corrections: list[Correction] = Field(default_factory=list)
    posted: list[dict[str, Any]] = Field(default_factory=list)


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or STATE_DIR / "state.json"
        self.lock = threading.Lock()
        self.state = self._load()

    def _load(self) -> State:
        if self.path.exists():
            try:
                return State.model_validate_json(self.path.read_text())
            except ValueError:
                pass
        return State()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(self.state.model_dump_json())
            os.replace(tmp, self.path)
        except OSError:
            pass

    def vendor_for(self, data: dict[str, Any]) -> dict[str, Any] | None:
        key = vendor_key(data)
        rec = self.state.vendors.get(key) if key else None
        return rec.model_dump() if rec else None

    def remember(self, doc_id: str, doc_type: str, data: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            key = vendor_key(data)
            if key:
                rec = self.state.vendors.setdefault(
                    key, VendorRecord(key=key, name=data.get("vendor_name") or data.get("merchant_name"))
                )
                rec.documents += 1
                rec.last_seen = time.time()
                number = normalize_text(data.get("invoice_number") or "")
                if number and number not in rec.invoice_numbers:
                    rec.invoice_numbers.append(number)
                fp = fingerprint(data)
                if fp and fp not in rec.fingerprints:
                    rec.fingerprints.append(fp)
                iban = normalize_text(data.get("iban") or "").replace(" ", "")
                if iban and iban not in rec.ibans:
                    rec.ibans.append(iban)
                currency = str(data.get("currency") or "").upper()
                if currency and currency not in rec.currencies:
                    rec.currencies.append(currency)
                if isinstance(data.get("tax_rate"), (int, float)) and data["tax_rate"] not in rec.tax_rates:
                    rec.tax_rates.append(float(data["tax_rate"]))
            self.state.posted.append(
                {
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "vendor": key,
                    "total": data.get("total"),
                    "ts": time.time(),
                }
            )
            self._save()
            return self.summary()

    def add_corrections(self, items: list[Correction]) -> None:
        with self.lock:
            self.state.corrections.extend(items)
            self._save()

    def reset(self) -> None:
        with self.lock:
            self.state = State()
            if self.path.exists():
                try:
                    self.path.unlink()
                except OSError:
                    pass

    def summary(self) -> dict[str, Any]:
        return {
            "documents_posted": len(self.state.posted),
            "vendors": len(self.state.vendors),
            "corrections": len(self.state.corrections),
            "fields_fixed": sum(1 for c in self.state.corrections if not c.accepted),
        }


_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def load_json(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
