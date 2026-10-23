"""Alerta de vagas no Telegram: lê as vagas novas da API pública do site (/api/jobs, sem
acessar a base) e publica cada uma num chat pelo bot de VAGAS_TELEGRAM_TOKEN.

Os ids já enviados ficam em data/telegram_alert_state.json (só os últimos 500). Cada
execução envia no máximo `limit` vagas, para não inundar o chat: as mais recentes ainda
não enviadas, em ordem de publicação. Cada envio bem-sucedido (vaga ou resumo semanal)
também entra em data/telegram_alert_log.json com data/hora (últimas 500 entradas), base
do relatório diário do canal.

send_weekly manda, uma vez por semana, o mesmo post do LinkedIn (print do dashboard +
texto de resumo); a semana já enviada fica em data/telegram_digest_state.json."""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html import escape
from pathlib import Path

from . import dates

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
ATTEMPTS = 2
HEADERS = {"User-Agent": "vagas-php"}


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
    """Entradas de data/telegram_alert_log.json; arquivo ausente ou ilegível: lista vazia."""
    try:
        entries = json.loads((data_dir / LOG_FILE).read_text())
    except (OSError, ValueError):
        return []
    return entries if isinstance(entries, list) else []


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


def run(data_dir: Path, limit: int = 5, dry_run: bool = False, force: bool = False) -> dict:
    """Envia as vagas ainda não enviadas (no máximo `limit`). dry_run: só imprime.
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
    batch = list(reversed(pending[:limit]))  # as mais recentes, a mais antiga primeiro
    log.info("%d vagas na API, %d ainda não enviadas (%d ignoradas sem URL); enviando %d%s.",
             len(jobs), len(pending), skipped, len(batch), " (simulação)" if dry_run else "")

    sent = 0
    for job in batch:
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
                              "title": job.get("title")})
        sent += 1
        log.info("Vaga enviada: %s (%s)", job["id"], job.get("title"))
        time.sleep(1)
    if dry_run:
        print(f"{skipped} vaga(s) ignorada(s) por falta de URL.")
    return {"api": len(jobs), "pending": len(pending), "sent": sent, "skipped": skipped,
            "dry_run": dry_run}
