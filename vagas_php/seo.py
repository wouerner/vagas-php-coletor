"""Páginas para buscadores e robôs de IA: título, descrição, canonical, Open Graph e
JSON-LD no <head>, e conteúdo já renderizado no servidor (robôs como os da OpenAI não
executam JavaScript). As páginas em static/ marcam onde entra o conteúdo com
<!--ssr:nome-->; render() troca cada marca pelo HTML de `content`.

VAGAS_SITE_URL (ex.: https://vagasphp.wouerner.dev) fixa o endereço público usado no
canonical e no sitemap; sem ela, vem dos cabeçalhos do proxy (X-Forwarded-*).
"""

import json
import logging
import os
import re
import unicodedata
from html import escape
from pathlib import Path

from starlette.requests import Request

SITE_NAME = "Vagas PHP"
# Preview social (LinkedIn, Telegram, WhatsApp): static/og.png, servida em /og.png.
OG_IMAGE_ALT = "Vagas PHP — vagas de PHP, Laravel e Symfony"
STATIC = Path(__file__).resolve().parent / "static"
SITE_URL = os.getenv("VAGAS_SITE_URL", "").strip().rstrip("/")

log = logging.getLogger(__name__)
GA_ID = os.getenv("VAGAS_GA_ID", "").strip()
if GA_ID and not re.fullmatch(r"G-[A-Z0-9]{4,20}", GA_ID):
    log.warning("VAGAS_GA_ID inválido (%r): Google Analytics desligado", GA_ID)
    GA_ID = ""

# <title> e <meta name="description"> das páginas estáticas: render() troca pelos dados.
_OLD_HEAD = re.compile(r'\s*<title>.*?</title>|\s*<meta name="description"[^>]*>', re.S)


def site_url(request: Request) -> str:
    """Endereço público do site, sem barra no fim. Atrás da Cloudflare e do Traefik, o
    esquema e o host vêm de X-Forwarded-Proto/Host."""
    if SITE_URL:
        return SITE_URL
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    host = request.headers.get("x-forwarded-host", request.url.netloc).split(",")[0].strip()
    return f"{proto}://{host}"


def head(request: Request, title: str, description: str, path: str,
         jsonld: list[dict] | dict | None = None, noindex: bool = False) -> str:
    """Tags do <head>. `path` é o caminho canônico ("/vagas/laravel"), sem query string."""
    base = site_url(request)
    url = base + path
    t, d, u, img = escape(title), escape(description), escape(url), escape(base + "/og.png")
    tags = [f"<title>{t}</title>",
            f'<meta name="description" content="{d}">',
            f'<link rel="canonical" href="{u}">',
            f'<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="{SITE_NAME}">',
            f'<meta property="og:locale" content="pt_BR">',
            f'<meta property="og:title" content="{t}">',
            f'<meta property="og:description" content="{d}">',
            f'<meta property="og:url" content="{u}">',
            f'<meta property="og:image" content="{img}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            f'<meta property="og:image:alt" content="{OG_IMAGE_ALT}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{t}">',
            f'<meta name="twitter:description" content="{d}">',
            f'<meta name="twitter:image" content="{img}">']
    if noindex:
        tags.append('<meta name="robots" content="noindex">')
    for data in ([jsonld] if isinstance(jsonld, dict) else jsonld or []):
        # "</" escapado: o JSON não fecha o <script> antes da hora.
        body = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        tags.append(f'<script type="application/ld+json">{body}</script>')
    return "\n".join(tags)


def render(request: Request, name: str, *, title: str, description: str, path: str,
           content: dict[str, str] | None = None, jsonld=None, noindex: bool = False) -> str:
    """HTML de static/<name> com o <head> de head(), as marcas <!--ssr:nome--> trocadas
    pelo HTML de `content` (já escapado por quem chama) e a tag do GA (fora de ?print=1)."""
    html = _OLD_HEAD.sub("", (STATIC / name).read_text())
    tags = head(request, title, description, path, jsonld, noindex)
    html = html.replace("</head>", tags + "\n</head>", 1)
    for key, value in (content or {}).items():
        html = html.replace(f"<!--ssr:{key}-->", value)
    if GA_ID and "print" not in request.query_params:
        tag = (STATIC / "analytics.html").read_text().replace("{GA_ID}", GA_ID)
        html = html.replace("</head>", tag + "</head>", 1)
    return html


def slugify(text: str | None, limit: int = 70) -> str:
    """"Desenvolvedor(a) PHP Sênior" -> "desenvolvedor-a-php-senior"."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:limit].rstrip("-") or "vaga"


def job_path(job: dict) -> str | None:
    """Página da vaga no site (/vaga/<seq>-<título>), só para vagas de portais: posts do
    LinkedIn não são anúncios estruturados. O número (seq) identifica a vaga; o título
    no endereço é só para leitura."""
    if job.get("source") == "post" or not job.get("seq"):
        return None
    return f"/vaga/{job['seq']}-{slugify(job.get('title'))}"


def breadcrumbs(request: Request, *items: tuple[str, str]) -> dict:
    """JSON-LD BreadcrumbList a partir de pares (nome, caminho)."""
    base = site_url(request)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": name,
                                 "item": base + path}
                                for i, (name, path) in enumerate(items, 1)]}
