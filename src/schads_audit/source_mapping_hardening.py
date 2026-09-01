from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from .source_mapping import scan_source_items


PAYROLL_FIELD_ALIASES: dict[str, list[str]] = {
    "employee_id": [
        "employee id", "employee number", "employee no", "employee code", "emp id",
        "staff id", "staff number", "worker id", "person id",
    ],
    "pay_period_start": [
        "pay period start", "pay period starting", "period start", "payrun start",
        "pay run start", "pay period from", "period from",
    ],
    "pay_period_end": [
        "pay period end", "pay period ending", "period end", "payrun end",
        "pay run end", "pay period to", "period to",
    ],
    "pay_category": [
        "pay category", "pay category name", "pay category code",
        "earning category", "earnings category", "earning category name", "earnings category name",
        "earning name", "earnings name", "earning type", "earnings type",
        "earning description", "earnings description", "earnings line description",
        "pay item", "pay item name", "pay item code", "pay code", "earnings code",
    ],
    "amount": [
        "amount", "earnings amount", "earning amount", "gross amount", "line amount",
        "payment amount", "gross earnings", "total earnings", "line total", "value",
    ],
    "payroll_line_id": ["payroll line id", "earnings line id", "earning line id", "line id"],
    "pay_run_id": ["pay run id", "payrun id", "pay run identifier"],
    "timesheet_id": ["timesheet id", "entry id", "shift id", "time entry id"],
    "earning_date": ["earning date", "earnings date", "work date", "payment date"],
    "hours": ["hours", "paid hours", "units", "quantity"],
    "rate": ["rate", "hourly rate", "unit rate", "pay rate"],
}

PAYROLL_DATASET_ALIASES = (
    "payroll earnings", "earnings", "earnings details", "earnings detail",
    "payroll detail", "payroll details", "pay run audit", "payrun audit",
    "gross to net", "pay categories", "payroll",
)

AMBIGUOUS_NAME_HEADERS = {
    "name", "employee name", "full name", "display name", "first name", "last name",
    "staff name", "worker name", "person name", "surname", "forename",
}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _tokens(value: Any) -> set[str]:
    return set(_norm(value).split())


def _strict_header_score(column: str, aliases: list[str]) -> float:
    """Score semantic header matches without character-level fuzzy matching."""
    col = _norm(column)
    if not col:
        return 0.0
    best = 0.0
    col_tokens = _tokens(col)
    for alias in aliases:
        a = _norm(alias)
        if not a:
            continue
        if col == a:
            best = max(best, 1.0)
            continue
        alias_tokens = _tokens(a)
        if alias_tokens and alias_tokens.issubset(col_tokens):
            best = max(best, 0.94)
        elif col_tokens and col_tokens.issubset(alias_tokens) and len(col_tokens) >= 2:
            best = max(best, 0.88)
    return best


def _pay_category_header_allowed(column: str) -> bool:
    """Return True only for headers that explicitly describe an earning/pay item."""
    norm = _norm(column)
    if not norm or norm in AMBIGUOUS_NAME_HEADERS:
        return False
    tokens = _tokens(norm)
    if "name" in tokens and tokens & {"employee", "staff", "worker", "person", "first", "last", "full", "display"}:
        return False
    if tokens & {"category", "earning", "earnings", "pay", "payroll"}:
        return True
    if "item" in tokens and "pay" in tokens:
        return True
    return False


def _best_column(columns: list[str], field: str) -> tuple[str | None, float]:
    aliases = PAYROLL_FIELD_ALIASES[field]
    best_col: str | None = None
    best = 0.0
    for column in columns:
        if field == "pay_category" and not _pay_category_header_allowed(column):
            continue
        score = _strict_header_score(column, aliases)
        if score > best:
            best_col, best = str(column), score
    return best_col, best


def _dataset_name_score(item_name: Any) -> float:
    name = _norm(item_name)
    if not name:
        return 0.0
    name_tokens = _tokens(name)
    best = 0.0
    for alias in PAYROLL_DATASET_ALIASES:
        a = _norm(alias)
        if name == a:
            best = max(best, 1.0)
        elif _tokens(a).issubset(name_tokens):
            best = max(best, 0.9)
    return best


def _candidate(item: pd.Series) -> dict[str, Any]:
    columns = [str(c) for c in (item.get("columns") or [])]
    matches: dict[str, tuple[str | None, float]] = {
        field: _best_column(columns, field) for field in PAYROLL_FIELD_ALIASES
    }
    required = ("employee_id", "pay_period_start", "pay_period_end", "pay_category", "amount")
    required_scores = [matches[field][1] for field in required]
    complete = all(score >= 0.88 for score in required_scores)
    required_coverage = sum(score >= 0.88 for score in required_scores) / len(required)
    score = (0.75 * required_coverage) + (0.25 * _dataset_name_score(item.get("item_name")))
    return {
        "item": item,
        "matches": matches,
        "complete": complete,
        "score": score,
    }


def harden_payroll_earnings_draft(draft: dict[str, Any], source_root: str | Path) -> dict[str, Any]:
    """Replace generic payroll_earnings inference with safety-oriented detection.

    Actual-pay reconciliation needs an earning-line category. When the uploaded
    files do not expose a trustworthy employee identifier, pay period, category
    and amount, payroll_earnings is left disabled. The entitlement audit can then
    continue without actual-pay reconciliation instead of manufacturing a field
    match from unrelated columns.
    """
    inventory = scan_source_items(source_root)
    best: dict[str, Any] | None = None
    for _, item in inventory.iterrows():
        candidate = _candidate(item)
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    datasets = draft.setdefault("datasets", {})
    existing = datasets.setdefault("payroll_earnings", {})

    if best is None or not best["complete"]:
        suggestions = {}
        if best is not None:
            for field, (column, confidence) in best["matches"].items():
                suggestions[field] = {
                    "suggested_source": column if confidence >= 0.88 else None,
                    "confidence": round(confidence, 3),
                }
        existing.update({
            "enabled": False,
            "source": None,
            "columns": {},
            "_suggestions": suggestions,
            "_dataset_confidence": round(best["score"], 3) if best is not None else 0.0,
            "_actual_pay_status": "UNAVAILABLE",
        })
        return draft

    item = best["item"]
    columns: dict[str, Any] = {}
    suggestions: dict[str, Any] = {}
    for field, (column, confidence) in best["matches"].items():
        suggestions[field] = {
            "suggested_source": column if confidence >= 0.88 else None,
            "confidence": round(confidence, 3),
        }
        if column and confidence >= 0.88:
            columns[field] = {"source": column}

    existing.update({
        "enabled": True,
        "source": {"file": item.get("file"), "sheet": item.get("sheet"), "header": 0},
        "columns": columns,
        "_suggestions": suggestions,
        "_dataset_confidence": round(best["score"], 3),
        "_actual_pay_status": "AVAILABLE",
    })
    return draft
