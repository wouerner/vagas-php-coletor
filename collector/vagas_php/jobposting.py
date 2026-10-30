"""Leitura do JSON-LD JobPosting (schema.org) que portais de vagas publicam em cada vaga
para o Google for Jobs (Catho, Programathor, Coodesh...): título, data, empresa, local,
modalidade, contratação, salário e descrição, sem depender do HTML de cada site."""

import json
import re
import time
import urllib.error
import urllib.request

from .public_jobs import html_to_text

# Alguns portais recusam (403) o user agent do Playwright headless e de bibliotecas HTTP.
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/140.0 Safari/537.36")
JSON_LD = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)

# employmentType: texto livre (Catho) ou os valores do schema.org.
CONTRACT = (("clt", "CLT"), ("efetivo", "CLT"), ("pj", "PJ"), ("contractor", "PJ"),
            ("autônomo", "Freelance"), ("freela", "Freelance"))
INTERNSHIP = ("estágio", "estagio", "trainee", "intern")


def fetch(url: str, site: str) -> str:
    """GET com até 3 tentativas (429, 5xx e conexão recusada, comuns sob carga)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "text/html,application/json",
        "Accept-Language": "pt-BR,pt;q=0.9"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == 2:
                raise RuntimeError(f"{site} respondeu HTTP {e.code}") from e
        except urllib.error.URLError as e:
            if attempt == 2:
                raise RuntimeError(f"{site}: {e.reason}") from e
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Sem resposta de {site}")


def json_ld(page: str) -> list[dict]:
    """Todos os objetos JSON-LD da página (soltos, em lista ou dentro de @graph)."""
    found = []
    for block in JSON_LD.findall(page):
        try:
            data = json.loads(block, strict=False)  # descrições com quebras de linha cruas
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        found += [item for item in items if isinstance(item, dict)]
    return found


def find(page: str) -> dict | None:
    """O primeiro JobPosting da página."""
    return next((d for d in json_ld(page) if d.get("@type") == "JobPosting"), None)


def _salary(base: dict | None) -> str | None:
    value = (base or {}).get("value") or {}
    if not isinstance(value, dict):
        return None
    low, high = value.get("minValue") or value.get("value"), value.get("maxValue")
    fmt = lambda v: f"R$ {float(v):,.0f}".replace(",", ".")  # noqa: E731
    if low and high and high != low:
        return f"{fmt(low)} a {fmt(high)}"
    return fmt(high or low) if (high or low) else None


def fields(post: dict) -> dict:
    """Campos do JobPosting no formato da tabela jobs (sem id, fonte e url)."""
    kind = post.get("employmentType") or ""
    kind = (" ".join(kind) if isinstance(kind, list) else kind).lower()
    contract = next((label for key, label in CONTRACT if key in kind), None)
    places = post.get("jobLocation") or []
    places = places if isinstance(places, list) else [places]
    address = (places[0].get("address") if places else None) or {}
    remote = post.get("jobLocationType") == "TELECOMMUTE"
    location = " - ".join(x for x in (address.get("addressLocality"), address.get("addressRegion"))
                          if x and x not in ("-", "Home Office", "HO")) or None
    org = post.get("hiringOrganization") or {}
    return {
        "title": (post.get("title") or "").strip(),
        "company": (org.get("name") if isinstance(org, dict) else org) or None,
        "location": location or ("Remoto" if remote else None),
        "workplace": "Remoto" if remote else None,
        "contract": contract,
        "internship": any(k in kind for k in INTERNSHIP),
        "salary": _salary(post.get("baseSalary")),
        "description": html_to_text(post.get("description") or "") or None,
        "published": (post.get("datePosted") or "")[:10] or None,  # dia (AAAA-MM-DD)
    }
