"""Timestamp parsing shared by the importers: one date order per column, every row checked, nothing invented."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from ...config import cfg

_ISO_DATE = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_NUM_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b")
_NAMED_DATE = re.compile(r"(\d{1,2})[\s-]+([A-Za-z]{3,9})\.?[\s-]+(\d{4})|([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})")
_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2})(?:[.,](\d{1,6}))?)?\s*([AaPp]\.?[Mm]\.?)?")
_EXCEL_SERIAL = re.compile(r"^\d{5}(?:\.\d+)?$")
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

DAY_FIRST, MONTH_FIRST = "day-first (DD-MM-YYYY)", "month-first (MM-DD-YYYY)"


def _safe_date(y, m, d) -> date | None:
    try:
        return date(y, m, d)
    except (TypeError, ValueError):
        return None


def _seconds(m: re.Match) -> float | None:
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    ampm = (m.group(5) or "").replace(".", "").lower()
    if ampm:
        if 13 <= h <= 23 and ampm == "pm":
            pass  # "21:22 PM": a 24-hour time with a redundant suffix
        elif not 1 <= h <= 12:
            return None
        else:
            h = (h % 12) + (12 if ampm == "pm" else 0)
    if h > 23 or mi > 59 or s > 59:
        return None
    return h * 3600 + mi * 60 + s + (float("0." + m.group(4)) if m.group(4) else 0.0)


def _year(y: int) -> int:
    return y + 2000 if y < 100 else y


def parse_moment(raw: str | None, day_first: bool = False) -> tuple[date | None, float | None]:
    """(date, seconds of day) from ISO, numeric (order given by the column), named-month or Excel-serial text."""
    if not raw:
        return None, None
    text = str(raw).strip()
    if _EXCEL_SERIAL.match(text):  # Excel day number, e.g. 46161.8333
        serial = float(text)
        if 20000 < serial < 80000:
            moment = datetime(1899, 12, 30) + timedelta(days=serial)
            return moment.date(), moment.hour * 3600 + moment.minute * 60 + moment.second
    d, rest = None, text
    if m := _ISO_DATE.search(text):
        d, rest = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3))), text[m.end():]
    elif m := _NUM_DATE.search(text):
        a, b, y = int(m.group(1)), int(m.group(2)), _year(int(m.group(3)))
        d = _safe_date(y, b, a) if day_first else _safe_date(y, a, b)
        rest = text[m.end():]
    elif m := _NAMED_DATE.search(text):
        if m.group(1):
            day, month, y = int(m.group(1)), _MONTHS.get(m.group(2)[:3].lower()), int(m.group(3))
        else:
            day, month, y = int(m.group(5)), _MONTHS.get(m.group(4)[:3].lower()), int(m.group(6))
        d, rest = _safe_date(y, month, day), text[m.end():]
    t = _TIME.search(rest.replace("T", " ", 1) if rest.startswith("T") else rest)
    return d, (_seconds(t) if t else None)


def time_only(raw: str | None) -> bool:
    """A clock time with nothing that looks like a date (the shape of exports that dropped the date)."""
    text = str(raw or "")
    return bool(_TIME.search(text)) and not (_ISO_DATE.search(text) or _NUM_DATE.search(text) or _NAMED_DATE.search(text)
                                             or _EXCEL_SERIAL.match(text.strip()))


def _n(count: int, one: str, many: str) -> str:
    return f"{count:,} {one if count == 1 else many}"


def detect_order(values: list[str], dataset: str = "events") -> dict:
    """Decide DD-MM vs MM-DD once for a column.

    Proof wins (a first part above 12 can only be a day). With no proof either way, the reading that
    gives the tighter, more plausible time span wins; a tie falls back to `etl.dates.ambiguous_order`.
    """
    first = second = 0
    pairs = []
    for v in values:
        if not v or _ISO_DATE.search(v):
            continue
        if m := _NUM_DATE.search(v):
            a, b, y = int(m.group(1)), int(m.group(2)), _year(int(m.group(3)))
            first += a > 12
            second += b > 12
            pairs.append((a, b, y))
    if not pairs:
        return {"day_first": False, "order": "ISO or named months", "evidence": "unambiguous format", "mixed": False}
    if first and not second:
        return {"day_first": True, "order": DAY_FIRST, "evidence": _n(first, "value has", "values have") + " a day above 12", "mixed": False}
    if second and not first:
        return {"day_first": False, "order": MONTH_FIRST, "evidence": _n(second, "value has", "values have") + " a day above 12", "mixed": False}
    if first and second:  # both shapes present: only rows that prove their own order can be trusted
        return {"day_first": first >= second, "order": DAY_FIRST if first >= second else MONTH_FIRST, "mixed": True,
                "evidence": f"mixed: {first:,} rows read day-first, {second:,} month-first; ambiguous rows are rejected"}

    def span(day_first: bool) -> int:
        days = [d for a, b, y in pairs if (d := _safe_date(y, b, a) if day_first else _safe_date(y, a, b))]
        return (max(days) - min(days)).days if days else 10 ** 6
    df_span, mf_span = span(True), span(False)
    if df_span != mf_span:
        day_first = df_span < mf_span
        return {"day_first": day_first, "order": DAY_FIRST if day_first else MONTH_FIRST, "mixed": False,
                "evidence": f"no day above 12; the {'day' if day_first else 'month'}-first reading spans {min(df_span, mf_span)} days "
                            f"instead of {max(df_span, mf_span)}"}
    day_first = str(cfg.etl.dates.ambiguous_order.get(dataset, "day_first")).lower().startswith("day")
    return {"day_first": day_first, "order": DAY_FIRST if day_first else MONTH_FIRST, "mixed": False,
            "evidence": f"no day above 12 and both readings span the same days; using the {dataset} default"}


def self_evident(raw: str) -> bool | None:
    """For mixed columns: True/False when the value proves day-first/month-first, None when it cannot."""
    m = _NUM_DATE.search(raw or "")
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if a == b:
        return False  # same reading either way
    return True if a > 12 else False if b > 12 else None


def check(d: date | None, secs: float | None, raw: str | None, now: datetime) -> str | None:
    """Why a parsed timestamp cannot be used, or None when it is fine."""
    if not raw or not str(raw).strip():
        return "Missing timestamp"
    text = str(raw)
    if d is None and (_ISO_DATE.search(text) or _NUM_DATE.search(text) or _NAMED_DATE.search(text)):
        return "Invalid date"
    if d is None and secs is not None:
        return "Time without a date"
    if d is None:
        return "Unreadable timestamp"
    if secs is None and _TIME.search(str(raw)):
        return "Unreadable time of day"
    if d.year < int(cfg.etl.dates.earliest_year):
        return f"Date before {cfg.etl.dates.earliest_year}"
    moment = datetime.combine(d, datetime.min.time()) + timedelta(seconds=secs or 0)
    if moment > now + timedelta(hours=float(cfg.etl.dates.future_tolerance_hours)):
        return "Date in the future"
    return None


def precision(raw_values: list[str]) -> str:
    """Finest unit present in the column: seconds or minutes."""
    for v in raw_values:
        t = _TIME.search(v or "")
        if t and t.group(3) is not None:
            return "seconds"
    return "minutes"


def iso(d: date | None, secs: float | None) -> str | None:
    if d is None:
        return None
    secs = secs or 0.0
    whole = int(secs)
    ms = int(round((secs - whole) * 1000))
    if ms == 1000:
        whole, ms = whole + 1, 0
    stamp = datetime.combine(d, datetime.min.time()) + timedelta(seconds=whole)
    return stamp.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d}"
