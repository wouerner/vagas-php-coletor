"""Vagas publicadas como issues em repositórios do GitHub (ex.: phpdevbr/vagas,
backend-br/vagas), pela API REST pública. GITHUB_TOKEN é opcional: sem ele o limite é
60 requisições/hora, suficiente para poucos repositórios a cada hora."""

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from . import config

API = "https://api.github.com"
MAX_PAGES = 10  # 100 issues por página

# Empresa no título: "... na Empresa", "... - Empresa", "... (Empresa)" ou "@ Empresa".
COMPANY_PATTERNS = [
    re.compile(r"\((?!remoto|h[ií]brido|presencial|pj|clt)([^()]{2,60})\)\s*$", re.I),
    re.compile(r"\s@\s*([^@\-()]{2,60})$"),
    re.compile(r"\s(?:na|no|at|em)\s+([A-Z][^\-()|]{1,60})$"),
    re.compile(r"\s[-–|]\s+([^\-–|()]{2,60})$"),
]


@dataclass
class GitHubJob:
    id: str              # "owner/repo#123"
    repo: str
    number: int
    title: str
    company: str | None
    labels: list[str]
    body: str | None
    author: str | None
    author_url: str | None
    url: str
    created_at: str
    closed_at: str | None


def _get(url: str) -> tuple[list | dict, dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "vagas-php",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and e.headers.get("x-ratelimit-remaining") == "0":
            reset = int(e.headers.get("x-ratelimit-reset", 0))
            wait = max(0, reset - int(time.time()))
            raise RuntimeError(f"Limite da API do GitHub atingido (libera em {wait // 60} min; "
                               "defina GITHUB_TOKEN para aumentar)") from e
        raise RuntimeError(f"GitHub respondeu HTTP {e.code} para {url}") from e


def _next_link(headers: dict) -> str | None:
    m = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link") or headers.get("link") or "")
    return m.group(1) if m else None


def company_from_title(title: str) -> str | None:
    for rx in COMPANY_PATTERNS:
        if m := rx.search(title.strip()):
            return m.group(1).strip(" .-") or None
    return None


def repos() -> list[str]:
    """Repositórios lidos: VAGAS_GITHUB_REPOS, senão a configuração (config.py)."""
    return config.search("github", "VAGAS_GITHUB_REPOS")


def fetch_issues(repo: str, since: str | None) -> list[GitHubJob]:
    """Issues do repositório atualizadas desde `since` (ISO), abertas e fechadas, para
    também saber quando uma vaga foi encerrada. Pull requests são ignorados."""
    params = {"state": "all", "sort": "updated", "direction": "desc", "per_page": "100"}
    if since:
        params["since"] = since
    url = f"{API}/repos/{repo}/issues?{urllib.parse.urlencode(params)}"
    jobs = []
    for _ in range(MAX_PAGES):
        items, headers = _get(url)
        for it in items:
            if "pull_request" in it:
                continue
            title = (it.get("title") or "").strip()
            jobs.append(GitHubJob(
                id=f"{repo}#{it['number']}", repo=repo, number=it["number"], title=title,
                company=company_from_title(title),
                labels=[lb["name"] for lb in it.get("labels", [])],
                body=it.get("body"),
                author=(it.get("user") or {}).get("login"),
                author_url=(it.get("user") or {}).get("html_url"),
                url=it["html_url"], created_at=it["created_at"], closed_at=it.get("closed_at"),
            ))
        url = _next_link(headers)
        if not url:
            break
    return jobs
