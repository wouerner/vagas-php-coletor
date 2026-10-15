"""Vagas da Catho (catho.com.br), sem login. A busca (/vagas/<termo>/, permitida no
robots.txt) é uma página HTML, ordenada da mais recente para a mais antiga e filtrada
pelos últimos N dias; a página de cada vaga traz um JSON-LD JobPosting com data,
contratação, empresa, local, salário e descrição."""

import html
import os
import re
import time
import urllib.parse

from . import jobposting

BASE = "https://www.catho.com.br"
DEFAULT_TERMS = "php,laravel,symfony,codeigniter,wordpress,magento,drupal"
OFFER = re.compile(r'<li data-offer-item="(\d+)"(.*?)</li>', re.S)
OFFER_LINK = re.compile(r'<a href="(/vagas/[^"]+/\d+/?)" title="([^"]*)"')


def terms() -> list[str]:
    return [t.strip() for t in (os.getenv("VAGAS_CATHO_TERMS") or DEFAULT_TERMS).split(",")
            if t.strip()]


def search(term: str, days: int, max_pages: int = 5) -> list[tuple[int, str, str]]:
    """(id, título, URL) das vagas com `term` publicadas ou atualizadas nos últimos
    `days` dias. Vagas patrocinadas aparecem em toda página: os ids repetidos são
    ignorados."""
    slug = urllib.parse.quote(term.strip().lower().replace(" ", "-"))
    found: dict[int, tuple[int, str, str]] = {}
    for page in range(1, max_pages + 1):
        params = {"order": "dataAtualizacao", "lastdays": days, **({"page": page} if page > 1 else {})}
        body = jobposting.fetch(f"{BASE}/vagas/{slug}/?{urllib.parse.urlencode(params)}", "Catho")
        new = 0
        for offer_id, card in OFFER.findall(body):
            link = OFFER_LINK.search(card)
            if link and int(offer_id) not in found:
                found[int(offer_id)] = (int(offer_id), html.unescape(link.group(2)).strip(),
                                        BASE + link.group(1))
                new += 1
        if not new:
            break
        time.sleep(1.5)
    return list(found.values())


def job_details(url: str) -> dict:
    post = jobposting.find(jobposting.fetch(url, "Catho"))
    if not post:
        raise RuntimeError(f"Catho: {url} sem JobPosting")
    return jobposting.fields(post)
