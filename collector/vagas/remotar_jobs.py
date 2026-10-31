"""Vagas da Remotar (remotar.com.br), portal de vagas 100% remotas, pela API JSON que o
site usa, sem login. A busca olha título e descrição; os resultados vêm do mais recente
para o mais antigo: a paginação para ao passar do início da janela."""

import json
import time
import urllib.parse
from datetime import datetime

from . import config, jobposting
from .public_jobs import html_to_text

API = "https://api.remotar.com.br/jobs"
WORKPLACE = {"remote": "Remoto", "hybrid": "Híbrido", "onsite": "Presencial", "on-site": "Presencial"}


def terms() -> list[str]:
    """Termos buscados: VAGAS_REMOTAR_TERMS, senão a configuração (config.py)."""
    return config.search("remotar", "VAGAS_REMOTAR_TERMS")


PERIOD = {"monthly": " por mês", "yearly": " por ano", "hourly": " por hora"}


def _salary(s: dict | None) -> str | None:
    """A API manda os valores em centavos ("from": 187800 = R$ 1.878) e o período em
    "type" (monthly, yearly...)."""
    if not s or not (s.get("from") or s.get("to")):
        return None
    cur = {"BRL": "R$", "USD": "US$", "EUR": "€"}.get(s.get("currency") or "BRL", s.get("currency"))
    fmt = lambda v: f"{cur} {float(v) / 100:,.0f}".replace(",", ".")  # noqa: E731
    low, high = s.get("from"), s.get("to")
    value = f"{fmt(low)} a {fmt(high)}" if low and high and low != high else fmt(high or low)
    return value + PERIOD.get(s.get("type") or "", "")


def search(term: str, since: datetime, max_pages: int = 5) -> list[dict]:
    """Vagas ativas com `term` publicadas desde `since`, no formato da tabela jobs (sem
    relevant e detalhes de PHP)."""
    jobs = []
    for page in range(1, max_pages + 1):
        data = json.loads(jobposting.fetch(
            f"{API}?{urllib.parse.urlencode({'search': term, 'page': page})}", "Remotar"))
        items = data.get("data") or []
        for it in items:
            created = datetime.fromisoformat(it["createdAt"])
            if created < since:
                return jobs  # daqui para frente, só mais antigas
            if not it.get("active") or it.get("expired"):
                continue
            company = it.get("company") or {}
            tags = [t["tag"]["name"] for t in it.get("jobTags") or [] if t.get("tag")]
            reqs = [r["description"] for r in it.get("jobRequirements") or [] if r.get("description")]
            description = "\n".join(x for x in (
                it.get("subtitle"), html_to_text(it.get("description") or ""),
                "Requisitos:\n" + "\n".join(f"- {r}" for r in reqs) if reqs else None,
                "Tags: " + ", ".join(tags) if tags else None) if x)
            place = ", ".join(x for x in (it.get("city"), it.get("state")) if isinstance(x, str) and x)
            jobs.append({
                "id": f"remotar:{it['id']}", "title": (it.get("title") or "").strip(),
                "company": it.get("companyDisplayName") or company.get("name"),
                "location": place or "Remoto",
                "workplace": WORKPLACE.get(it.get("type") or ""),
                "salary": _salary(it.get("jobSalary")),
                "url": f"https://remotar.com.br/job/{it['id']}",
                "description": description or None,
                "posted_at": created.isoformat(),
                "tags": " ".join(tags),
            })
        meta = data.get("meta") or {}
        if page >= (meta.get("last_page") or 1):
            break
        time.sleep(1)
    return jobs
