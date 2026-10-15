"""Datas de publicação. Na base tudo fica em UTC ("2026-10-11T14:30:00+00:00"), para as
comparações de texto do SQLite funcionarem; o site mostra no horário de Brasília.

Só interessam vagas publicadas há no máximo MAX_AGE_HOURS (padrão 72 h)."""

import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BRASILIA = ZoneInfo("America/Sao_Paulo")
MAX_AGE_HOURS = float(os.getenv("VAGAS_MAX_AGE_HOURS", 72))

# "há 7 horas", "há 2 dias", "18 h", "1 d", "1 sem", "3 weeks ago"...
RELATIVE = re.compile(
    r"(\d+)\s*(minutos?|min|horas?|hours?|h|dias?|days?|d|semanas?|weeks?|sem|w|"
    r"m[eê]s(?:es)?|months?|mo|anos?|years?|a|y|yr)\b", re.I)
UNITS = [("min", timedelta(minutes=1)), ("h", timedelta(hours=1)), ("d", timedelta(days=1)),
         ("s", timedelta(weeks=1)), ("w", timedelta(weeks=1)), ("me", timedelta(days=30)),
         ("mo", timedelta(days=30)), ("a", timedelta(days=365)), ("y", timedelta(days=365))]


def utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def cutoff(hours: float | None = None) -> str:
    """Data/hora (UTC) mais antiga aceita: agora menos `hours` (no máximo MAX_AGE_HOURS)."""
    hours = min(hours or MAX_AGE_HOURS, MAX_AGE_HOURS)
    return utc_iso(now_utc() - timedelta(hours=hours))


def relative_delta(label: str | None) -> timedelta | None:
    m = RELATIVE.search(label or "")
    if not m:
        return None
    unit = m.group(2).lower()
    step = next(d for prefix, d in UNITS if unit.startswith(prefix))
    return int(m.group(1)) * step


def from_relative(label: str | None) -> str | None:
    """'há 3 h' / '2 d' / '1 sem' -> data/hora UTC aproximada."""
    delta = relative_delta(label)
    return utc_iso(now_utc() - delta) if delta is not None else None


def from_date(day: str | None, label: str | None = None) -> str | None:
    """Data de vaga do LinkedIn ("2026-10-09", dia no horário de Brasília). Se o texto
    relativo tiver precisão de horas ("há 7 horas"), usa ele; senão, o início do dia —
    a hipótese mais antiga, para nunca mostrar como recente algo de mais de 72 h."""
    delta = relative_delta(label)
    if delta is not None and delta < timedelta(days=1):
        return utc_iso(now_utc() - delta)
    if not day:
        return from_relative(label)
    try:
        start = datetime.fromisoformat(day[:10]).replace(tzinfo=BRASILIA)
    except ValueError:
        return from_relative(label)
    return utc_iso(start)


def normalize(value: str | None) -> str | None:
    """Qualquer ISO (com Z, offset ou só a data em Brasília) -> ISO UTC."""
    if not value:
        return None
    if len(value) == 10:
        return from_date(value)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BRASILIA)
    return utc_iso(dt)
