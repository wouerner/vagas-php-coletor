"""Site que lista as vagas PHP coletadas. Usa a base do coletor (MySQL) só para leitura.

Rotas: /             página (static/index.html)
       /api/jobs     vagas em JSON (filtros: q, source, workplace, seniority, stack, hours,
                     include_closed, limit, offset)
       /api/stats    totais por fonte e últimas coletas
       /dashboard    dashboard (static/dashboard.html)
       /api/dashboard  números do dashboard (days: dias da série diária, 3-90) e próximas coletas
       /regras       regras de filtro (static/regras.html)
       /api/rules    as regras (de php.RULES), quantas vagas cada uma decidiu e as
                     descartadas à mão
       /recrutadores tech recruiters que mais publicam vagas PHP (static/recrutadores.html)
       /api/recruiters  a lista: últimos 90 dias, VAGAS_RECRUITERS_MIN vagas ou mais (padrão
                     2), sem os perfis de VAGAS_RECRUITERS_HIDE (URLs, separadas por vírgula)

Google Analytics: com VAGAS_GA_ID=G-XXXXXXXXXX as páginas recebem a tag (static/analytics.html,
com aviso de consentimento). ?print=1 tira a tag (print do dashboard para o post diário).

Uso: python -m vagas_php.web   (http://WEB_HOST:WEB_PORT/)
"""

import json
import logging
import os
import re
from pathlib import Path

import uvicorn
from pymysql.err import ProgrammingError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from . import dates, php
from .store import SOURCES, Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VAGAS_DATA_DIR", ROOT / "data"))
STATIC = Path(__file__).resolve().parent / "static"

_store: Store | None = None

log = logging.getLogger(__name__)
GA_ID = os.getenv("VAGAS_GA_ID", "").strip()
if GA_ID and not re.fullmatch(r"G-[A-Z0-9]{4,20}", GA_ID):
    log.warning("VAGAS_GA_ID inválido (%r): Google Analytics desligado", GA_ID)
    GA_ID = ""


def store() -> Store:
    # Conecta na primeira requisição; as tabelas são criadas pelo coletor.
    global _store
    if _store is None:
        _store = Store(readonly=True, wait=0)
    return _store


def _number(value: str | None, default: float, low: float, high: float) -> float:
    try:
        return min(max(float(value), low), high)
    except (TypeError, ValueError):
        return default


def page(request: Request, name: str) -> HTMLResponse:
    html = (STATIC / name).read_text()
    if GA_ID and "print" not in request.query_params:
        tag = (STATIC / "analytics.html").read_text().replace("{GA_ID}", GA_ID)
        html = html.replace("</head>", tag + "</head>", 1)
    return HTMLResponse(html)


async def index(request: Request):
    return page(request, "index.html")


async def jobs(request: Request):
    p = request.query_params
    source = p.get("source") or None
    if source and source not in SOURCES:
        return JSONResponse({"error": f"source deve ser {', '.join(SOURCES)}"}, status_code=400)
    limit = int(_number(p.get("limit"), 50, 1, 200))
    try:
        rows = store().query_jobs(
            q=p.get("q") or None, source=source, workplace=p.get("workplace") or None,
            seniority=p.get("seniority") or None, stack=p.get("stack") or None,
            hours=_number(p.get("hours"), 72, 1, 72),
            include_closed=p.get("include_closed") in ("1", "true"),
            limit=limit + 1, offset=int(_number(p.get("offset"), 0, 0, 1e6)))
    except ProgrammingError:  # tabelas ainda não criadas pelo coletor
        rows = []
    return JSONResponse({"jobs": rows[:limit], "has_more": len(rows) > limit,
                         "max_age_hours": dates.MAX_AGE_HOURS})


async def dashboard_page(request: Request):
    return page(request, "dashboard.html")


def schedule() -> dict | None:
    """Próximas coletas, gravadas pelo coletor em data/schedule.json (a cada minuto)."""
    try:
        return json.loads((DATA_DIR / "schedule.json").read_text())
    except (OSError, ValueError):
        return None


async def dashboard(request: Request):
    days = int(_number(request.query_params.get("days"), 14, 3, 90))
    try:
        return JSONResponse({**store().dashboard(days), "schedule": schedule()})
    except ProgrammingError:
        return JSONResponse({"error": "base ainda vazia"}, status_code=503)


async def rules_page(request: Request):
    return page(request, "regras.html")


async def rules(request: Request):
    try:
        stats = store().rule_stats()
    except ProgrammingError:
        stats = {"counts": {}, "dismissed": []}
    return JSONResponse({"rules": php.RULES, **stats, "max_age_hours": dates.MAX_AGE_HOURS})


RECRUITERS_DAYS = 90
RECRUITERS_MIN = max(int(os.getenv("VAGAS_RECRUITERS_MIN") or 2), 1)
RECRUITERS_HIDE = [u.strip() for u in os.getenv("VAGAS_RECRUITERS_HIDE", "").split(",") if u.strip()]


async def recruiters_page(request: Request):
    return page(request, "recrutadores.html")


async def recruiters(request: Request):
    try:
        rows = store().recruiters(RECRUITERS_DAYS, RECRUITERS_MIN, RECRUITERS_HIDE)
    except ProgrammingError:
        rows = []
    return JSONResponse({"recruiters": rows, "days": RECRUITERS_DAYS, "min_jobs": RECRUITERS_MIN})


async def stats(request: Request):
    try:
        return JSONResponse(store().stats())
    except ProgrammingError:
        return JSONResponse({"sources": {}, "last_runs": {}})


app = Starlette(routes=[
    Route("/", index),
    Route("/api/jobs", jobs),
    Route("/api/stats", stats),
    Route("/dashboard", dashboard_page),
    Route("/api/dashboard", dashboard),
    Route("/regras", rules_page),
    Route("/api/rules", rules),
    Route("/recrutadores", recruiters_page),
    Route("/api/recruiters", recruiters),
])


if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("WEB_HOST", "127.0.0.1"), port=int(os.getenv("WEB_PORT", 8780)),
                proxy_headers=True)
