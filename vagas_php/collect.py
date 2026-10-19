"""Coletores das fontes de vagas. Cada um devolve vagas como dicts no formato da tabela
`jobs` (relevantes e descartadas: as descartadas ficam na base para não serem
reprocessadas, mas o site só mostra as relevantes)."""

import hashlib
import math
import logging
import os
import re
import time
from datetime import datetime, timedelta

from . import (catho_jobs, coodesh_jobs, dates, github_jobs, gupy_jobs, inhire_jobs, jobposting,
               nerdin_jobs, php, programathor_jobs, public_jobs, recrutei_jobs, remotar_jobs,
               solides_jobs, upvagas_jobs)
from .bot import LinkedInBot, Post
from .store import Store

log = logging.getLogger("vagas_php.collect")


def _env_list(name: str, default: str) -> list[str]:
    return [x.strip() for x in (os.getenv(name) or default).split(",") if x.strip()]


# --- LinkedIn: busca pública de vagas (sem login) -----------------------------------

def collect_linkedin(store: Store, hours: float) -> dict:
    """Busca as palavras-chave nas últimas `hours` horas e baixa a descrição das vagas
    novas, que decide se a vaga é mesmo de PHP (a busca do LinkedIn é ampla)."""
    keywords = _env_list("VAGAS_LINKEDIN_KEYWORDS", "php,laravel,symfony,wordpress,magento,drupal")
    locations = _env_list("VAGAS_LINKEDIN_LOCATIONS", "Brasil")
    limit = int(os.getenv("VAGAS_LINKEDIN_LIMIT", 100))
    found: dict[str, public_jobs.PublicJob] = {}
    for location in locations:
        for kw in keywords:
            for job in public_jobs.search_jobs(kw, hours=hours, location=location, limit=limit):
                found.setdefault(job.id, job)
            time.sleep(2)

    known = store.known("linkedin")
    jobs, details_failed = [], 0
    for job in found.values():
        jid = f"linkedin:{job.id}"
        prev = known.get(jid)
        description = prev["description"] if prev else None
        if not description:
            try:
                description = public_jobs.job_details(job.id)["description"]
            except RuntimeError as e:
                details_failed += 1  # tenta de novo na próxima coleta
                log.warning("Detalhes da vaga %s: %s", job.id, e)
            time.sleep(1.5)
        jobs.append({
            "id": jid, "source": "linkedin",
            "relevant": php.is_php_job(job.title, description),
            "title": job.title, "company": job.company, "location": job.location,
            "salary": job.salary, "url": job.url, "description": description,
            "posted_at": dates.from_date(job.posted_date, job.posted),
            **php.details(job.title, job.location, description),
        })
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new,
            "failed": details_failed}


# --- Gupy: portal de vagas (sem login) ------------------------------------------

def collect_gupy(store: Store, since: datetime) -> dict:
    found: dict[int, gupy_jobs.GupyJob] = {}
    for term in gupy_jobs.terms():
        for job in gupy_jobs.search(term, since):
            found.setdefault(job.id, job)
        time.sleep(1)
    jobs = []
    for job in found.values():
        info = php.details(job.title, job.description)
        if job.internship and not info["seniority"]:
            info["seniority"] = "Estágio"
        jobs.append({
            "id": f"gupy:{job.id}", "source": "gupy",
            "relevant": php.is_php_job(job.title, job.description),
            "title": job.title, "company": job.company, "location": job.location,
            "url": job.url, "description": job.description, "posted_at": job.published,
            # Modalidade e contratação vêm da própria Gupy (mais confiável que o texto).
            **info, **{k: v for k, v in (("workplace", job.workplace),
                                          ("contract", job.contract)) if v},
        })
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new}


# --- Sólides: portal de vagas (sem login) ---------------------------------------

def collect_solides(store: Store, since: datetime) -> dict:
    day = since.astimezone(dates.BRASILIA).date()  # a Sólides só informa o dia
    found: dict[int, solides_jobs.SolidesJob] = {}
    for term in solides_jobs.terms():
        for job in solides_jobs.search(term, day):
            found.setdefault(job.id, job)
        time.sleep(1)
    jobs = []
    for job in found.values():
        info = php.details(job.title, job.description)
        jobs.append({
            "id": f"solides:{job.id}", "source": "solides",
            "relevant": php.is_php_job(job.title, job.description),
            "title": job.title, "company": job.company, "location": job.location,
            "salary": job.salary, "url": job.url, "description": job.description,
            "posted_at": dates.from_date(job.published),
            # Modalidade, contratação e senioridade vêm da própria Sólides.
            **info, **{k: v for k, v in (
                ("workplace", job.workplace), ("contract", job.contract),
                ("seniority", php._first(php.SENIORITY, job.seniority))) if v},
        })
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new}


# --- portais com JSON-LD JobPosting: Catho, Programathor, Coodesh (sem login) ------

def _maybe_php_title(title: str) -> bool:
    """Título que is_php_job pode aceitar (cargo de desenvolvimento ou PHP no título):
    só esses valem baixar a página da vaga."""
    return php.job_verdict(title) != "not_dev" and bool(
        php.DEV_ROLE.search(title) or php.PHP_CORE.search(title))


def _jobposting_jobs(store: Store, source: str, candidates, details, delay: float = 1.5) -> dict:
    """Baixa a página das vagas novas com título que pode ser de PHP (`candidates`: (id,
    título ou endereço, URL)) e lê o JSON-LD JobPosting (`details(url)`). Vagas antigas
    também são guardadas, para não serem baixadas de novo: o site mostra só as das 72 h."""
    known = store.known(source)
    jobs, failed = [], 0
    for job_id, title, url in candidates:
        if f"{source}:{job_id}" in known or not _maybe_php_title(title):
            continue
        try:
            job = details(url)
        except (RuntimeError, OSError) as e:
            failed += 1  # tenta de novo na próxima coleta
            log.warning("%s %s: %s", source, job_id, e)
            continue
        info = php.details(job["title"], job["description"])
        if job["internship"] and not info["seniority"]:
            info["seniority"] = "Estágio"
        jobs.append({
            "id": f"{source}:{job_id}", "source": source,
            "relevant": php.is_php_job(job["title"], job["description"]),
            "title": job["title"] or title, "company": job["company"],
            "location": job["location"], "salary": job["salary"], "url": url,
            "description": job["description"], "posted_at": dates.from_date(job["published"]),
            # Modalidade e contratação do próprio portal, quando informadas.
            **info, **{k: job[k] for k in ("workplace", "contract") if job[k]},
        })
        time.sleep(delay)
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new,
            "listed": len(candidates), "failed": failed}


def collect_catho(store: Store, since: datetime) -> dict:
    """O filtro "últimos N dias" da Catho usa a data de atualização: a data de publicação
    de verdade vem da página da vaga."""
    days = max(1, math.ceil((dates.now_utc() - since).total_seconds() / 86400))
    found: dict[int, tuple[int, str, str]] = {}
    for term in catho_jobs.terms():
        for offer in catho_jobs.search(term, days):
            found.setdefault(offer[0], offer)
        time.sleep(1.5)
    return _jobposting_jobs(store, "catho", list(found.values()), catho_jobs.job_details)


def collect_programathor(store: Store) -> dict:
    found: dict[int, tuple[int, str, str]] = {}
    for page in programathor_jobs.pages():
        for job in programathor_jobs.list_jobs(page):
            found.setdefault(job[0], job)
        time.sleep(2)
    return _jobposting_jobs(store, "programathor", list(found.values()),
                            programathor_jobs.job_details, delay=2)


def collect_coodesh(store: Store, since: datetime) -> dict:
    """O sitemap tem todas as vagas abertas: só as alteradas dentro da janela podem ser
    novas."""
    day = since.astimezone(dates.BRASILIA).date().isoformat()
    listed = coodesh_jobs.list_jobs()
    candidates = [(job_id, title, url) for job_id, title, url, lastmod in listed
                  if not lastmod or lastmod >= day]
    # "listed" é o sitemap todo: vazio indica problema na fonte, não falta de vagas.
    return {**_jobposting_jobs(store, "coodesh", candidates, coodesh_jobs.job_details),
            "listed": len(listed)}


def collect_recrutei(store: Store, since: datetime) -> dict:
    """Como na Coodesh: o sitemap tem todas as vagas abertas, de todas as áreas, e só as
    alteradas dentro da janela podem ser novas."""
    day = since.astimezone(dates.BRASILIA).date().isoformat()
    listed = recrutei_jobs.list_jobs()
    candidates = [(job_id, title, url) for job_id, title, url, lastmod in listed
                  if not lastmod or lastmod >= day]
    return {**_jobposting_jobs(store, "recrutei", candidates, recrutei_jobs.job_details),
            "listed": len(listed)}


def collect_nerdin(store: Store) -> dict:
    return _jobposting_jobs(store, "nerdin", nerdin_jobs.search_all(), nerdin_jobs.job_details)


# --- UpVagas: vagas remotas (API do WordPress, sem login) ---------------------------

def collect_upvagas(store: Store, since: datetime) -> dict:
    found: dict[int, upvagas_jobs.UpvagasJob] = {}
    for term in upvagas_jobs.terms():
        for job in upvagas_jobs.search(term, since):
            found.setdefault(job.id, job)
        time.sleep(1)
    jobs = []
    for j in found.values():
        info = php.details(j.title, j.description)
        if j.internship and not info["seniority"]:
            info["seniority"] = "Estágio"
        jobs.append({
            "id": f"upvagas:{j.id}", "source": "upvagas",
            "relevant": php.is_php_job(j.title, j.description),
            "title": j.title, "company": j.company, "location": j.location, "salary": j.salary,
            "url": j.url, "description": j.description, "posted_at": dates.normalize(j.published),
            **info, **{k: getattr(j, k) for k in ("workplace", "contract") if getattr(j, k)},
        })
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new}


# --- Remotar: vagas remotas (API, sem login) -----------------------------------------

def collect_remotar(store: Store, since: datetime) -> dict:
    found: dict[str, dict] = {}
    for term in remotar_jobs.terms():
        for job in remotar_jobs.search(term, since):
            found.setdefault(job["id"], job)
        time.sleep(1)
    jobs = []
    for job in found.values():
        tags = job.pop("tags")
        info = php.details(job["title"], tags, job["description"])
        jobs.append({**job, "source": "remotar",
                     "relevant": php.is_php_job(job["title"], job["description"]),
                     "posted_at": dates.normalize(job["posted_at"]),
                     **info, **({"workplace": job["workplace"]} if job["workplace"] else {})})
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new}


# --- InHire: páginas de carreira das empresas (sem login) ----------------------------

def collect_inhire(store: Store) -> dict:
    """Lista as vagas de cada empresa e baixa o detalhe só das novas com título que pode
    ser de vaga PHP (cargo de desenvolvimento ou PHP no título: is_php_job não aceita
    outras). Não há data na lista: as antigas são guardadas e o site mostra só as das
    últimas 72 h."""
    known = store.known("inhire")
    tenants = inhire_jobs.tenants(*store.texts_mentioning(".inhire.app"))
    jobs, listed, failed, missing = [], 0, 0, []
    for tenant in tenants:
        try:
            company, items = inhire_jobs.list_jobs(tenant)
        except inhire_jobs.TenantNotFound:
            missing.append(tenant)
            continue
        except (RuntimeError, OSError) as e:
            failed += 1
            log.warning("InHire %s: %s", tenant, e)
            continue
        listed += len(items)
        for item in items:
            title = item.get("displayName") or ""
            if f"inhire:{item['jobId']}" in known or not _maybe_php_title(title):
                continue
            try:
                job = inhire_jobs.job_details(tenant, item, company)
            except (RuntimeError, OSError) as e:
                failed += 1  # tenta de novo na próxima coleta
                log.warning("InHire %s/%s: %s", tenant, item["jobId"], e)
                continue
            jobs.append({
                "id": f"inhire:{job.id}", "source": "inhire",
                "relevant": php.is_php_job(job.title, job.description),
                "title": job.title, "company": job.company, "location": job.location,
                "url": job.url, "description": job.description,
                "posted_at": dates.normalize(job.published),
                **php.details(job.title, job.description),
                # Modalidade e contratação vêm da própria InHire.
                **{k: v for k, v in (("workplace", job.workplace), ("contract", job.contract)) if v},
            })
            time.sleep(0.5)
        time.sleep(1)
    if missing:
        log.info("InHire: empresas não encontradas: %s", ", ".join(missing))
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new,
            "tenants": len(tenants) - len(missing), "listed": listed, "failed": failed}


# --- GitHub: issues de repositórios de vagas ---------------------------------------

def collect_github(store: Store, since: str | None) -> dict:
    jobs = []
    for repo in github_jobs.repos():
        for it in github_jobs.fetch_issues(repo, since):
            labels = ",".join(it.labels)
            jobs.append({
                "id": f"github:{it.id}", "source": "github",
                "relevant": php.is_php_job(it.title, it.body, labels),
                "title": it.title, "company": it.company, "location": repo,
                "url": it.url, "author": it.author, "author_url": it.author_url,
                "description": it.body, "posted_at": dates.normalize(it.created_at), "closed_at": it.closed_at,
                **php.details(it.title, labels, it.body),
            })
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new}


# --- LinkedIn: publicações anunciando vagas PHP (logado) ----------------------------

def _post_title(text: str) -> str:
    """A primeira linha com texto. Se ela for só um chamado curto, sem vaga nem cargo
    ("Alô Devs!!!", ou "Meu Perfil" em posts que copiam a página da vaga), usa a primeira
    linha seguinte com cargo de desenvolvimento ou PHP."""
    lines = [line.strip(" #*•-–—🚀📢💼🔥✨👉➡️") for line in text.splitlines()]
    lines = [line for line in lines if len(line) >= 8]
    if not lines:
        return text.strip()[:140]
    first = lines[0]
    if len(first.split()) <= 3 and not re.search(r"vaga|oportunidade|contrat", first, re.I) \
            and not (php.DEV_ROLE.search(first) or php.PHP_CORE.search(first)):
        for line in lines[1:12]:
            if line.count("#") >= 2:  # linha de hashtags
                continue
            if php.DEV_ROLE.search(line) or php.PHP_CORE.search(line):
                return line.lstrip("#0123456789 -")[:140]
    return first[:140]


def post_to_job(post: Post) -> dict:
    text = post.text or post.raw_text or ""
    if post.urn:
        jid = f"post:{post.urn}"
    else:
        jid = "post:h:" + hashlib.sha1(f"{post.author}|{text[:300]}".encode()).hexdigest()[:20]
    return {
        "id": jid, "source": "post", "relevant": php.is_php_hiring_post(text),
        "title": _post_title(text), "company": None, "url": post.url,
        "author": post.author, "author_url": post.author_url, "description": text,
        "posted_at": dates.from_relative(post.time),
        **php.details(None, text),
    }


def search_hiring_posts(bot: LinkedInBot, date_posted: str) -> list[Post]:
    """Roda as buscas de publicações (no navegador já logado) e junta os resultados: os
    que anunciam vaga PHP e os recusados pelo filtro que falam de PHP."""
    keywords = _env_list("VAGAS_POSTS_KEYWORDS", "vaga php,vaga laravel,desenvolvedor php,pessoa desenvolvedora php,oportunidade php,vaga wordpress")
    limit = int(os.getenv("VAGAS_POSTS_PER_QUERY", 15))
    oldest = dates.cutoff()

    key = lambda p: p.urn or f"{p.author}|{(p.text or '')[:200]}"  # noqa: E731
    rejected: dict[str, Post] = {}

    def keep(p: Post) -> bool:
        # A busca só filtra por "24 h" ou "semana": o limite de 72 h é aplicado aqui.
        posted = dates.from_relative(p.time)
        if not (posted and posted > oldest):
            return False
        verdict = php.post_verdict(p.text or p.raw_text)
        # Recusados que falam de PHP também são guardados (fora do site): a página
        # /regras conta quantos cada regra barrou, e mudanças no filtro valem para eles
        # (reclassify). Posts de quem procura emprego não.
        if verdict not in php.POST_OK and verdict not in ("post_no_php", "job_seeker"):
            rejected.setdefault(key(p), p)
        return verdict in php.POST_OK

    posts: dict[str, Post] = {}
    for kw in keywords:
        for p in bot.search_posts(kw, limit=limit, date_posted=date_posted, keep=keep):
            posts.setdefault(key(p), p)
        bot.page.wait_for_timeout(3000)
    return list(posts.values()) + [p for k, p in rejected.items() if k not in posts]


POST_ID = re.compile(r"[-:](share|activity|ugcPost)[-:](\d{10,})")


def import_post(store: Store, url: str) -> dict:
    """Lê um post público do LinkedIn pelo link (inclusive lnkd.in), sem login, aplica o
    filtro e guarda na base se falar de PHP (como a busca faz). Diz qual regra decidiu."""
    page = jobposting.fetch(url, "LinkedIn")  # segue o redirecionamento do lnkd.in
    m = re.search(r'https://www\.linkedin\.com/(?:posts|feed/update)/[^"\'<>\s?]+', page) \
        if "lnkd.in" in url else None
    if m and "SocialMediaPosting" not in page:
        url, page = m.group(0), jobposting.fetch(m.group(0), "LinkedIn")
    post = next((d for d in jobposting.json_ld(page) if d.get("@type") == "SocialMediaPosting"), None)
    if not post or not post.get("articleBody"):
        raise RuntimeError("não encontrei o texto do post (post privado ou removido?)")
    text = post["articleBody"]
    canonical = post.get("url") or post.get("mainEntityOfPage") or url
    canonical = canonical if isinstance(canonical, str) else url
    # A busca guarda os posts pelo urn de "share" (o do endereço /posts/...-share-N): o
    # mesmo id aqui evita duplicar o post se a busca também o encontrar.
    ident = next((m for t in (url, canonical, page) for m in POST_ID.finditer(t)
                  if m.group(1) == "share"), None) \
        or POST_ID.search(canonical) or POST_ID.search(url) or POST_ID.search(page)
    verdict = php.post_verdict(text)
    author = post.get("author") or {}
    job = {"id": f"post:urn:li:{ident.group(1)}:{ident.group(2)}" if ident else
           "post:h:" + hashlib.sha1(f"{author.get('name')}|{text[:300]}".encode()).hexdigest()[:20],
           "source": "post", "relevant": verdict in php.POST_OK, "title": _post_title(text),
           "company": None, "url": canonical.split("?")[0], "author": author.get("name"),
           "author_url": author.get("url"), "description": text,
           "posted_at": dates.normalize(post.get("datePublished")), **php.details(None, text)}
    saved = verdict not in ("post_no_php", "job_seeker")
    if saved:
        store.save_jobs([job])
    rule = next((r for r in php.RULES if r["id"] == verdict), {})
    return {"id": job["id"], "title": job["title"], "author": job["author"],
            "posted_at": job["posted_at"], "relevant": job["relevant"],
            "in_window": bool(job["posted_at"] and job["posted_at"] > dates.cutoff()),
            "rule": verdict, "rule_title": rule.get("title"), "rule_effect": rule.get("effect"),
            "saved": saved}


def save_posts(store: Store, posts: list[Post]) -> dict:
    jobs = [post_to_job(p) for p in posts]
    new = store.save_jobs(jobs)
    return {"found": len(jobs), "relevant": sum(j["relevant"] for j in jobs), "new": new}


# --- janelas de tempo ---------------------------------------------------------------

def since_last_run(store: Store, source: str) -> datetime:
    """Início da janela de busca: a última coleta OK (com 1 h de folga), mas nunca antes
    do limite de idade das vagas (72 h)."""
    oldest = datetime.fromisoformat(dates.cutoff())
    last = store.last_ok_start(source)
    if last:
        return max(datetime.fromisoformat(last) - timedelta(hours=1), oldest)
    return oldest


def date_posted_filter(since: datetime) -> str:
    return "past-24h" if dates.now_utc() - since <= timedelta(hours=24) else "past-week"


def run(store: Store, source: str, headless: bool = True) -> dict:
    """Coleta uma fonte desde a última coleta OK dela e registra a execução em `runs`.
    A fonte "post" abre o navegador logado: chame-a de uma única thread por vez."""
    since = since_last_run(store, source)
    log.info("Coleta %s: desde %s", source, since.isoformat(timespec="minutes"))
    run_id = store.start_run(source)
    try:
        if source == "linkedin":
            hours = (dates.now_utc() - since).total_seconds() / 3600
            result = collect_linkedin(store, hours)
        elif source == "gupy":
            result = collect_gupy(store, since)
        elif source == "remotar":
            result = collect_remotar(store, since)
        elif source == "programathor":
            result = collect_programathor(store)
        elif source == "coodesh":
            result = collect_coodesh(store, since)
        elif source == "recrutei":
            result = collect_recrutei(store, since)
        elif source == "nerdin":
            result = collect_nerdin(store)
        elif source == "upvagas":
            result = collect_upvagas(store, since)
        elif source == "catho":
            result = collect_catho(store, since)
        elif source == "solides":
            result = collect_solides(store, since)
        elif source == "inhire":
            result = collect_inhire(store)
        elif source == "github":
            result = collect_github(store, since.isoformat(timespec="seconds"))
        elif source == "post":
            with LinkedInBot(headless=headless) as bot:
                bot.login()
                posts = search_hiring_posts(bot, date_posted_filter(since))
            result = save_posts(store, posts)
        else:
            raise ValueError(f"fonte desconhecida: {source}")
    except Exception as e:
        store.finish_run(run_id, error=f"{type(e).__name__}: {e}")
        raise
    # Sem "listed" no resultado, a fonte já devolve só o que listou na janela (= found).
    store.finish_run(run_id, found=result["found"], new_jobs=result["new"],
                     listed=result.get("listed", result["found"]), failed=result.get("failed", 0))
    return result
