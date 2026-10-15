"""Vagas de empresas que usam a InHire (ATS: <empresa>.inhire.app/vagas), pela mesma API
pública que a página de carreiras usa, sem login. Não há busca entre empresas: cada
empresa (tenant) é consultada à parte. A lista vem de VAGAS_INHIRE_TENANTS mais as
empresas descobertas em links "<empresa>.inhire.app" nas vagas e posts já coletados."""

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass

from .public_jobs import USER_AGENT, html_to_text

API = "https://api.inhire.app/job-posts/public/pages"
# Empresas de tecnologia com página na InHire (achadas em buscas na web). As descobertas
# nas coletas se somam a estas.
DEFAULT_TENANTS = ("tqi,atlastechnol,clinicaexperts,objective,sympla,db1,zappts,lyncas,"
                   "bixtecnologia,programmers,jump,orizon,dock,rentbrella,edge,ninecon,mambape")
TENANT_LINK = re.compile(r"\b([a-z0-9][a-z0-9-]{1,62})\.inhire\.app\b", re.I)
NOT_TENANTS = {"api", "auth", "files", "www", "app", "vagas", "blog", "help"}

WORKPLACE = {"Remote": "Remoto", "Hybrid": "Híbrido", "On-site": "Presencial"}
CONTRACT = {"CLT": "CLT", "PJ": "PJ", "Freelancer": "Freelance", "Freelance": "Freelance"}


class TenantNotFound(RuntimeError):
    pass


@dataclass
class InhireJob:
    id: str                 # jobId (UUID)
    tenant: str
    title: str
    company: str | None
    location: str | None
    workplace: str | None
    contract: str | None
    description: str | None
    published: str | None   # ISO UTC
    url: str


def _get(tenant: str, path: str = "") -> dict:
    req = urllib.request.Request(API + path, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
        "X-Tenant": tenant, "X-Inhire-Client": "web-inhire"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise TenantNotFound(f"InHire: empresa {tenant!r} não encontrada") from e
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"InHire respondeu HTTP {e.code} ({tenant})") from e
    raise RuntimeError(f"Sem resposta da InHire ({tenant})")


def tenants(*texts: str | None) -> list[str]:
    """VAGAS_INHIRE_TENANTS mais as empresas citadas em links .inhire.app nos textos."""
    found = [t.strip().lower() for t in (os.getenv("VAGAS_INHIRE_TENANTS") or DEFAULT_TENANTS)
             .split(",") if t.strip()]
    for text in texts:
        found += [m.lower() for m in TENANT_LINK.findall(text or "")]
    return list(dict.fromkeys(t for t in found if t not in NOT_TENANTS))


def list_jobs(tenant: str) -> tuple[str | None, list[dict]]:
    """Nome da empresa e vagas publicadas (jobId, displayName, workplaceType, location)."""
    data = _get(tenant)
    return data.get("tenantName"), [j for j in data.get("jobsPage") or []
                                    if j.get("status", "published") == "published"]


def _slug(title: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "-"


def job_details(tenant: str, item: dict, company: str | None) -> InhireJob:
    d = _get(tenant, f"/{item['jobId']}")
    title = (d.get("displayName") or item.get("displayName") or "").strip()
    contracts = [CONTRACT[c] for c in d.get("contractType") or [] if c in CONTRACT]
    published = d.get("publishedAt") or d.get("createdAt")
    return InhireJob(
        id=item["jobId"], tenant=tenant, title=title,
        company=(d.get("tenantName") or company or tenant).strip(),
        location=d.get("location") or item.get("location"),
        workplace=WORKPLACE.get(d.get("workplaceType") or item.get("workplaceType") or ""),
        contract=contracts[0] if contracts else None,  # o filtro do site tem um valor só
        description=html_to_text(d.get("description") or "") or None,
        published=published.replace("Z", "+00:00") if published else None,
        url=f"https://{tenant}.inhire.app/vagas/{item['jobId']}/{_slug(title)}",
    )
