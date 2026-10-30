"""Alerta de vagas no Telegram: lê as vagas novas da API pública do site (/api/jobs, sem
acessar a base) e publica cada uma num chat pelo bot de VAGAS_TELEGRAM_TOKEN.

Os ids já enviados ficam em data/telegram_alert_state.json (só os últimos 500). Cada
execução envia no máximo `limit` vagas, para não inundar o chat: as mais recentes ainda
não enviadas, em ordem de publicação. No modo agrupado (batch) vai UMA mensagem com todas
as pendentes que couberem no limite do Telegram (format_digest). Cada envio bem-sucedido (vaga ou resumo semanal)
também entra em data/telegram_alert_log.json com data/hora (últimas 500 entradas), base
do relatório diário do canal.

Além do id, há dedupe por conteúdo: a mesma vaga às vezes volta com outro id (ex.: a
UpVagas republica uma cópia por cidade da mesma vaga do Lever). A chave (content_key) é a
empresa normalizada (php.company_key; sem empresa, o autor) + o título normalizado (sem
acento, minúsculo, sem pontuação e sem refs tipo "REF#123"). Vaga cuja chave já foi
enviada nos últimos DEDUPE_DAYS dias (pelo `at`/`key` do log) não sai, mas o id entra no
estado para não ser reavaliada; no mesmo lote, só a mais recente de cada chave sai. Sem
empresa nem autor não há chave: vale só o id. Entradas antigas do log, sem `key`, contam
só pelo título normalizado. Log ilegível derruba a execução (tratá-lo como vazio
reenviaria tudo).

send_weekly manda, uma vez por semana, o mesmo post do LinkedIn (print do dashboard +
texto de resumo); a semana já enviada fica em data/telegram_digest_state.json."""

import json
import logging
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

from . import dates, php

log = logging.getLogger("vagas_php.telegram_alert")

VAGAS_API_URL = (os.getenv("VAGAS_API_URL") or "https://vagasphp.wouerner.dev").rstrip("/")
VAGAS_TELEGRAM_TOKEN = os.getenv("VAGAS_TELEGRAM_TOKEN", "")
VAGAS_TELEGRAM_CHAT_ID = os.getenv("VAGAS_TELEGRAM_CHAT_ID", "")
# Janela de postagem do alerta, "HH-HH" em horário de Brasília (início incluso, fim não).
VAGAS_TELEGRAM_ACTIVE_HOURS = os.getenv("VAGAS_TELEGRAM_ACTIVE_HOURS") or "8-19"

STATE_FILE = "telegram_alert_state.json"
STATE_MAX = 500
LOG_FILE = "telegram_alert_log.json"
LOG_MAX = 500
DIGEST_STATE_FILE = "telegram_digest_state.json"
CAPTION_MAX = 1024  # limite da legenda de foto no Telegram
# Limite de sendMessage. O Telegram conta o texto já sem as tags; aqui conta o HTML inteiro,
# então a mensagem que cabe fica bem abaixo do limite real.
MESSAGE_MAX = 4096
INDENT = "    "  # recuo dos detalhes de cada vaga no resumo agrupado
ATTEMPTS = 2
HEADERS = {"User-Agent": "vagas-php"}
DEDUPE_DAYS = 14  # janela do dedupe por conteúdo (content_key)
# Referência de vaga no título: "REF#123", "Ref. 0086E", "ref: AB-12"...
TITLE_REF = re.compile(r"\bref\b\.?\s*[#:]?\s*[a-z0-9-]*\d[a-z0-9-]*", re.IGNORECASE)


def fetch_jobs() -> list[dict]:
    """Vagas das últimas 72 h pela API pública (mais recentes primeiro)."""
    url = f"{VAGAS_API_URL}/api/jobs?hours=72&limit=200"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS),
                                        timeout=30) as resp:
                return json.loads(resp.read())["jobs"]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            log.warning("Falha ao ler %s (tentativa %d de %d): %s", url, attempt, ATTEMPTS, e)
            if attempt < ATTEMPTS:
                time.sleep(5)
    raise RuntimeError(f"Não foi possível ler as vagas de {url}")


def out_link(job: dict) -> str:
    """Link do anúncio pelo /out do site: o clique entra no rastreio. Sem url: ""."""
    url = (job.get("url") or "").strip()
    if not url:
        return ""
    query = urllib.parse.urlencode({"url": url, "job": job.get("id") or "", "page": "/",
                                    "source": job.get("source") or ""})
    return f"{VAGAS_API_URL}/out?{query}"


def destiny(url: str) -> str:
    """Texto visível do link: host sem "www." e o 1º segmento do caminho
    (ex.: "linkedin.com/jobs"), até 40 caracteres. URL ilegível: a própria URL."""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    host = (parts.hostname or "").removeprefix("www.")
    if not host:
        return url
    text = "/".join([host, *[s for s in parts.path.split("/") if s][:1]])
    return text if len(text) <= 40 else text[:39] + "…"


def format(job: dict) -> str:
    """Mensagem da vaga em HTML do Telegram. Campos vazios ficam de fora."""
    def line(emoji: str, *parts) -> str | None:
        text = " · ".join(escape(str(p).strip()) for p in parts if p and str(p).strip())
        return f"{emoji} {text}" if text else None

    title = (job.get("title") or "").strip()
    stack = ", ".join(s.strip() for s in (job.get("stack") or "").split(",") if s.strip())
    url = (job.get("url") or "").strip()
    lines = [f"<b>{escape(title)}</b>" if title else None,
             line("🏢", job.get("company")),
             line("📍", job.get("location")),
             line("💼", job.get("workplace"), job.get("seniority"), job.get("contract")),
             line("🐘", stack),
             f'🔗 <a href="{escape(out_link(job))}">{escape(destiny(url))}</a>' if url else None]
    return "\n".join(x for x in lines if x)


def digest_fit(jobs: list[dict]) -> tuple[str, int]:
    """(mensagem, quantas vagas couberam) do resumo agrupado: as vagas do fim saem até a
    mensagem caber em MESSAGE_MAX. Lista vazia: ("", 0)."""
    if not jobs:
        return "", 0
    today = dates.now_utc().astimezone(dates.BRASILIA)
    head = [f"<b>🐘 Vagas PHP</b> — {today:%d/%m}", "",
            "Vagas de PHP, Laravel e Symfony publicadas nas últimas horas:"]
    blocks = []
    for job in jobs:
        stack = ", ".join(s.strip() for s in (job.get("stack") or "").split(",") if s.strip())
        details = " · ".join(escape(str(p).strip()) for p in (
            job.get("company"), job.get("location"), job.get("workplace"),
            job.get("seniority"), stack) if p and str(p).strip())
        title = (job.get("title") or "").strip()
        url = (job.get("url") or "").strip()
        lines = [f"<b>{escape(title)}</b>" if title else None,
                 f"{INDENT}{details}" if details else None,
                 f'{INDENT}🔗 <a href="{escape(out_link(job))}">{escape(destiny(url))}</a>'
                 if url else None]
        blocks.append("\n".join(x for x in lines if x))
    n = len(blocks)
    while n:
        text = "\n".join(head) + "\n\n" + "\n\n".join(blocks[:n])
        if len(text) <= MESSAGE_MAX:
            break
        n -= 1
    if n < len(blocks):
        log.warning("Resumo agrupado acima de %d caracteres: couberam %d de %d vagas.",
                    MESSAGE_MAX, n, len(blocks))
    return (text, n) if n else ("", 0)


def format_digest(jobs: list[dict]) -> str:
    """UMA mensagem em HTML do Telegram com a lista de vagas (cabe em MESSAGE_MAX)."""
    return digest_fit(jobs)[0]


def send(token: str, chat_id: str, text: str) -> dict:
    """sendMessage do Telegram; devolve o JSON da resposta (também nos erros HTTP)."""
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "false"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=data, headers=HEADERS)
    for retry in (True, False):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            # A URL leva o token: nunca entra no log nem nas exceções.
            try:
                body = json.loads(e.read())
            except ValueError:
                body = {"ok": False, "error_code": e.code, "description": f"HTTP {e.code}"}
            wait = (body.get("parameters") or {}).get("retry_after")
            if e.code == 429 and wait and retry:
                log.info("Telegram pediu para aguardar %s s (429); tentando de novo.", wait)
                time.sleep(int(wait) + 1)
                continue
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            return {"ok": False, "description": f"erro de rede: {getattr(e, 'reason', e)}"}
    return body


def send_photo(token: str, chat_id: str, image_path: Path, caption: str,
               dry_run: bool = False) -> dict:
    """sendPhoto do Telegram (multipart/form-data montado à mão, só com urllib).
    Devolve o JSON da resposta (também nos erros HTTP). dry_run: só imprime."""
    image_path = Path(image_path)
    if dry_run:
        print(f"[simulação] sendPhoto para o chat {chat_id or '(VAGAS_TELEGRAM_CHAT_ID vazio)'}: "
              f"{image_path} ({image_path.stat().st_size} bytes), legenda com "
              f"{len(caption)} caracteres:\n{caption}\n")
        return {"ok": True, "dry_run": True}
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("chat_id", str(chat_id)), ("caption", caption)):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                     .encode() + value.encode() + b"\r\n")
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; '
                 f'filename="{image_path.name}"\r\nContent-Type: image/png\r\n\r\n'.encode()
                 + image_path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendPhoto", data=b"".join(parts),
        headers={**HEADERS, "Content-Type": f"multipart/form-data; boundary={boundary}"})
    for retry in (True, False):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            # A URL leva o token: nunca entra no log nem nas exceções.
            try:
                body = json.loads(e.read())
            except ValueError:
                body = {"ok": False, "error_code": e.code, "description": f"HTTP {e.code}"}
            wait = (body.get("parameters") or {}).get("retry_after")
            if e.code == 429 and wait and retry:
                log.info("Telegram pediu para aguardar %s s (429); tentando de novo.", wait)
                time.sleep(int(wait) + 1)
                continue
            return body
        except (urllib.error.URLError, TimeoutError) as e:
            return {"ok": False, "description": f"erro de rede: {getattr(e, 'reason', e)}"}
    return body


def digest_sent_week(data_dir: Path) -> str | None:
    try:
        state = json.loads((data_dir / DIGEST_STATE_FILE).read_text())
    except (OSError, ValueError):
        return None
    return state.get("week") if isinstance(state, dict) else None


def send_weekly(data_dir: Path, dry_run: bool = False) -> dict:
    """Resumo semanal no Telegram: o mesmo print do dashboard e o mesmo texto do post do
    LinkedIn. Uma vez por semana ISO (estado em data/telegram_digest_state.json)."""
    # Importado aqui: linkedin_post lê VAGAS_DASHBOARD_URL no import, depois do .env.
    from . import dates, linkedin_post

    now = dates.now_utc().astimezone(dates.BRASILIA)
    year, week_no, _ = now.isocalendar()
    week = f"{year}-{week_no:02d}"
    if not dry_run and digest_sent_week(data_dir) == week:
        print(f"Resumo da semana {week} já enviado; nada a fazer.")
        return {"semana": week, "ok": True, "ja_enviado": True}
    if not dry_run and not (VAGAS_TELEGRAM_TOKEN and VAGAS_TELEGRAM_CHAT_ID):
        raise RuntimeError("Defina VAGAS_TELEGRAM_TOKEN e VAGAS_TELEGRAM_CHAT_ID no .env")

    out_dir = data_dir / "linkedin_posts" / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    image = out_dir / "dashboard_telegram.png"
    log.info("Gerando o print do dashboard em %s.", image)
    numbers = linkedin_post.dashboard_screenshot(image)
    caption = linkedin_post.text(numbers, now)
    log.info("Resumo da semana %s: %s%s.", week, numbers, " (simulação)" if dry_run else "")
    # A legenda de foto do Telegram aceita até 1024 caracteres; acima disso, o texto vai
    # numa mensagem logo depois da foto.
    long_text = len(caption) > CAPTION_MAX
    resp = send_photo(VAGAS_TELEGRAM_TOKEN, VAGAS_TELEGRAM_CHAT_ID, image,
                      "" if long_text else caption, dry_run=dry_run)
    if long_text and resp.get("ok"):
        log.info("Texto com %d caracteres (> %d): enviado em mensagem separada.",
                 len(caption), CAPTION_MAX)
        if dry_run:
            print(f"[simulação] sendMessage com o texto:\n{caption}\n")
        else:
            # send usa parse_mode HTML: escapado, o texto sai igual ao do post.
            resp = send(VAGAS_TELEGRAM_TOKEN, VAGAS_TELEGRAM_CHAT_ID, escape(caption))
    ok = bool(resp.get("ok"))
    if not ok:
        log.error("Telegram recusou o resumo da semana %s: %s", week, resp.get("description"))
    elif not dry_run:
        path = data_dir / DIGEST_STATE_FILE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"week": week, "at": now.isoformat(timespec="seconds"),
                                   "numbers": numbers}, ensure_ascii=False, indent=1))
        tmp.replace(path)
        log_append(data_dir, {"kind": "digest", "week": week})
        log.info("Resumo da semana %s enviado.", week)
    return {"numeros": numbers, "semana": week, "ok": ok, "imagem": str(image),
            "dry_run": dry_run}


def state_load(data_dir: Path) -> list[str]:
    try:
        ids = json.loads((data_dir / STATE_FILE).read_text())
    except FileNotFoundError:
        return []
    return ids if isinstance(ids, list) else []


def state_save(data_dir: Path, ids: list[str]) -> None:
    path = data_dir / STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ids[-STATE_MAX:], ensure_ascii=False, indent=1))
    tmp.replace(path)


def log_load(data_dir: Path) -> list[dict]:
    """Entradas de data/telegram_alert_log.json; arquivo ausente: lista vazia. Ilegível ou
    fora do formato: exceção (o dedupe depende dele; vazio reenviaria tudo)."""
    path = data_dir / LOG_FILE
    try:
        entries = json.loads(path.read_text())
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        raise RuntimeError(f"{path} ilegível; corrija ou restaure antes de rodar: {e}") from e
    if not isinstance(entries, list):
        raise RuntimeError(f"{path} fora do formato (esperava uma lista)")
    return entries


def log_append(data_dir: Path, entry: dict) -> None:
    """Acrescenta `entry` (com "at" em horário de Brasília) ao log, mantendo só as últimas
    LOG_MAX entradas. Uma falha ao gravar só vira aviso: não derruba o envio."""
    entry = {"at": dates.now_utc().astimezone(dates.BRASILIA).isoformat(timespec="seconds"),
             **entry}
    try:
        path = data_dir / LOG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps((log_load(data_dir) + [entry])[-LOG_MAX:],
                                  ensure_ascii=False, indent=1))
        tmp.replace(path)
    except OSError as e:
        log.warning("Não foi possível gravar %s: %s", LOG_FILE, e)


def _plain(text: str | None) -> str:
    """Sem acento, minúsculo, só [a-z0-9] e espaços simples."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def title_key(title: str | None) -> str:
    """Título normalizado para o dedupe: _plain sem as refs (TITLE_REF)."""
    title = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    return _plain(TITLE_REF.sub(" ", title))


def content_key(job: dict) -> str | None:
    """"empresa|título" normalizados (empresa por php.company_key; sem ela, o autor).
    None sem empresa nem autor, ou sem título: aí vale só o id."""
    who = php.company_key(job.get("company")) or _plain(job.get("author")).replace(" ", "")
    title = title_key(job.get("title"))
    return f"{who}|{title}" if who and title else None


def recent_keys(entries: list[dict], days: int = DEDUPE_DAYS) -> tuple[set[str], set[str]]:
    """(chaves, títulos) das vagas enviadas nos últimos `days` dias. Entradas antigas, sem
    "key", só têm o título (o log não guardava a empresa): entram em `títulos`. Entrada com
    `at` ilegível conta como recente (na dúvida, não reenvia)."""
    since = dates.now_utc() - timedelta(days=days)
    keys, titles = set(), set()
    for e in entries:
        if not isinstance(e, dict) or e.get("kind") != "job":
            continue
        try:
            at = datetime.fromisoformat(e.get("at") or "")
            if at.tzinfo is None:
                at = at.replace(tzinfo=dates.BRASILIA)
            if at < since:
                continue
        except (TypeError, ValueError):
            pass
        if "key" in e:
            if e["key"]:
                keys.add(e["key"])
        elif title := title_key(e.get("title")):
            titles.add(title)
    return keys, titles


def dedupe(pending: list[dict], entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """(vagas a enviar, duplicadas). Duplicada: chave enviada nos últimos DEDUPE_DAYS dias
    (recent_keys) ou repetida no lote (`pending` vem da mais recente para a mais antiga:
    fica a primeira)."""
    keys, titles = recent_keys(entries)
    keep, dups = [], []
    for job in pending:
        key = content_key(job)
        if key and (key in keys or key.split("|", 1)[1] in titles):
            dups.append(job)
            continue
        if key:
            keys.add(key)
        keep.append(job)
    return keep, dups


def active_hours() -> tuple[int, int]:
    """(início, fim) de VAGAS_TELEGRAM_ACTIVE_HOURS ("8-19")."""
    try:
        start, end = (int(x) for x in VAGAS_TELEGRAM_ACTIVE_HOURS.split("-"))
    except ValueError:
        raise RuntimeError(f"VAGAS_TELEGRAM_ACTIVE_HOURS inválido: "
                           f"{VAGAS_TELEGRAM_ACTIVE_HOURS!r} (use HH-HH, ex.: 8-19)")
    if not (0 <= start <= 23 and 0 <= end <= 24):
        raise RuntimeError(f"VAGAS_TELEGRAM_ACTIVE_HOURS fora de 0-24: "
                           f"{VAGAS_TELEGRAM_ACTIVE_HOURS!r}")
    return start, end


def in_window(hour: int, start: int, end: int) -> bool:
    # start > end atravessa a meia-noite (ex.: 22-6).
    return start <= hour < end if start <= end else hour >= start or hour < end


def run(data_dir: Path, limit: int = 5, dry_run: bool = False, force: bool = False,
        batch: bool = False) -> dict:
    """Envia as vagas ainda não enviadas (no máximo `limit`). dry_run: só imprime.
    batch: UMA mensagem com todas as pendentes (format_digest), sem `limit`; as que não
    couberem no limite do Telegram ficam pendentes para a próxima execução.
    Fora de VAGAS_TELEGRAM_ACTIVE_HOURS não envia nada (as vagas ficam pendentes para a
    próxima execução dentro da janela); force ignora a janela."""
    if not force:
        start, end = active_hours()
        now = dates.now_utc().astimezone(dates.BRASILIA)
        if not in_window(now.hour, start, end):
            print(f"Fora do horário de postagem ({now:%H:%M}, janela {start:02d}-{end:02d}); "
                  "nada enviado.")
            return {"skipped_window": True, "now": now.strftime("%H:%M"),
                    "window": f"{start:02d}-{end:02d}", "sent": 0, "dry_run": dry_run}
    if not dry_run and not (VAGAS_TELEGRAM_TOKEN and VAGAS_TELEGRAM_CHAT_ID):
        raise RuntimeError("Defina VAGAS_TELEGRAM_TOKEN e VAGAS_TELEGRAM_CHAT_ID no .env")
    sent_ids = state_load(data_dir)
    known = set(sent_ids)
    jobs = fetch_jobs()
    unsent = [j for j in jobs if j.get("id") and j["id"] not in known]
    # Sem link a mensagem não serve: vagas sem url (ex.: as de publicações) ficam de fora.
    pending = [j for j in unsent if (j.get("url") or "").strip()]
    skipped = len(unsent) - len(pending)
    pending, dups = dedupe(pending, log_load(data_dir))
    for job in dups:
        log.info("Vaga repetida (mesma empresa e título nos últimos %d dias ou no lote), "
                 "não enviada: %s (%s)", DEDUPE_DAYS, job["id"], job.get("title"))
    if dups and not dry_run:
        # O id entra no estado para a vaga não ser reavaliada a cada execução.
        sent_ids += [j["id"] for j in dups]
        state_save(data_dir, sent_ids)
    if batch:
        return run_batch(data_dir, jobs, pending, skipped, len(dups), dry_run)
    to_send = list(reversed(pending[:limit]))  # as mais recentes, a mais antiga primeiro
    log.info("%d vagas na API, %d ainda não enviadas (%d ignoradas sem URL, %d repetidas); "
             "enviando %d%s.", len(jobs), len(pending), skipped, len(dups), len(to_send),
             " (simulação)" if dry_run else "")

    sent = 0
    for job in to_send:
        text = format(job)
        if dry_run:
            print(f"--- {job['id']}\n{text}\n")
            continue
        resp = send(VAGAS_TELEGRAM_TOKEN, VAGAS_TELEGRAM_CHAT_ID, text)
        if not resp.get("ok"):
            # Para aqui: a vaga fica pendente e volta na próxima execução.
            log.error("Telegram recusou a vaga %s: %s", job["id"], resp.get("description"))
            break
        sent_ids.append(job["id"])
        state_save(data_dir, sent_ids)  # a cada envio: uma falha depois não reenvia esta
        log_append(data_dir, {"kind": "job", "id": job["id"], "source": job.get("source"),
                              "title": job.get("title"), "key": content_key(job)})
        sent += 1
        log.info("Vaga enviada: %s (%s)", job["id"], job.get("title"))
        time.sleep(1)
    if dry_run:
        print(f"{skipped} vaga(s) ignorada(s) por falta de URL; {len(dups)} repetida(s).")
    return {"api": len(jobs), "pending": len(pending), "sent": sent, "skipped": skipped,
            "duplicates": len(dups), "dry_run": dry_run}


def run_batch(data_dir: Path, jobs: list[dict], pending: list[dict], skipped: int,
              duplicates: int, dry_run: bool) -> dict:
    """Modo agrupado de run: uma só mensagem com as vagas pendentes (mais recentes primeiro;
    as mais antigas saem se passar do limite) e todas as enviadas gravadas no estado e no log."""
    text, n = digest_fit(pending)
    included = pending[:n]
    log.info("%d vagas na API, %d ainda não enviadas (%d ignoradas sem URL, %d repetidas); "
             "enviando %d numa mensagem só (%d caracteres)%s.", len(jobs), len(pending),
             skipped, duplicates, n, len(text), " (simulação)" if dry_run else "")
    result = {"api": len(jobs), "pending": len(pending), "sent": 0, "skipped": skipped,
              "duplicates": duplicates, "batch": True, "included": n, "chars": len(text),
              "dry_run": dry_run}
    if not included:
        return result
    if dry_run:
        print(f"--- mensagem única: {n} vaga(s), {len(text)} caracteres\n{text}\n")
        print(f"{skipped} vaga(s) ignorada(s) por falta de URL; {duplicates} repetida(s).")
        return result
    resp = send(VAGAS_TELEGRAM_TOKEN, VAGAS_TELEGRAM_CHAT_ID, text)
    if not resp.get("ok"):
        # Nada gravado: as vagas ficam pendentes e voltam na próxima execução.
        log.error("Telegram recusou o resumo agrupado: %s", resp.get("description"))
        return result
    sent_ids = state_load(data_dir) + [j["id"] for j in included]
    state_save(data_dir, sent_ids)
    for job in included:
        log_append(data_dir, {"kind": "job", "id": job["id"], "source": job.get("source"),
                              "title": job.get("title"), "key": content_key(job),
                              "batch": True})
    log.info("Resumo agrupado enviado com %d vaga(s).", n)
    return {**result, "sent": n}
