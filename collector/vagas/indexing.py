"""Google Indexing API: avisa o Google das páginas de vaga (JobPosting) abertas.

É a via oficial e rápida para páginas com JobPosting: o Google rastreia a URL publicada em
minutos, sem esperar o sitemap. As URLs são as do sitemap do site (web/, em PHP): vagas
abertas de portais, em /vaga/<seq>-<título>. O endereço é contrato entre os dois lados
(job_path aqui, Seo::jobPath no site; os dois testam contra contracts/job_paths.json).

Credencial (conta de serviço, escopo indexing), na ordem:
  VAGAS_INDEXING_SA_B64           JSON da conta de serviço em base64, numa linha
  GOOGLE_APPLICATION_CREDENTIALS  caminho do arquivo JSON
Sem credencial: um aviso no log e nada é enviado (coleta e serviço seguem).

A conta de serviço precisa ser *Proprietário* (Owner) da propriedade no Search Console;
como "Completo" (Full) a API responde 403 "Failed to verify the URL ownership".

Quota do Google: 200 publicações por dia por projeto. Aqui o teto é DAILY_CAP, contado
pelas publicações bem-sucedidas das últimas 24 h em indexing_log.

Uso: python -m vagas indexing-push [--limit N] [--dry-run] [--force]
"""

import base64
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from . import dates

log = logging.getLogger(__name__)

ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"
SCOPE = "https://www.googleapis.com/auth/indexing"
DEFAULT_LIMIT = 50
DAILY_CAP = 150  # a quota é 200/dia: sobra margem para envios manuais
WINDOW = timedelta(hours=24)
TIMEOUT = 20
SITE_URL = "https://vagasphp.wouerner.dev"


class PublishError(Exception):
    """Falha ao publicar uma URL; as próximas do lote ainda podem dar certo."""


class OwnershipError(PublishError):
    """403: a conta de serviço não é Proprietário da propriedade no Search Console."""


class QuotaError(PublishError):
    """429 / RESOURCE_EXHAUSTED: a quota do dia acabou; o lote para."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(at: datetime) -> str:
    # Mesmo formato de store.now_iso: as datas são comparadas como texto.
    return at.isoformat(timespec="seconds")


_warned = False


def _warn_once(message: str) -> None:
    global _warned
    if not _warned:
        log.warning(message)
        _warned = True


def credentials():
    """Credencial da conta de serviço ou None (com um aviso). Nunca loga o conteúdo."""
    raw = os.getenv("VAGAS_INDEXING_SA_B64", "").strip()
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not raw and not path:
        _warn_once("Indexing API: sem credencial (defina VAGAS_INDEXING_SA_B64 ou "
                   "GOOGLE_APPLICATION_CREDENTIALS); nada enviado ao Google")
        return None
    try:
        from google.oauth2 import service_account
    except ImportError:
        _warn_once("Indexing API: pacote google-auth não instalado; nada enviado ao Google")
        return None
    try:
        if raw:
            info = json.loads(base64.b64decode(raw, validate=True))
            return service_account.Credentials.from_service_account_info(info, scopes=[SCOPE])
        return service_account.Credentials.from_service_account_file(path, scopes=[SCOPE])
    except Exception as e:  # só o tipo do erro: a mensagem poderia trazer parte da chave
        origem = "VAGAS_INDEXING_SA_B64" if raw else "GOOGLE_APPLICATION_CREDENTIALS"
        _warn_once(f"Indexing API: credencial inválida em {origem} ({type(e).__name__}); "
                   "nada enviado ao Google")
        return None


class GooglePublisher:
    """Publica uma URL por chamada na Indexing API. Levanta PublishError e subclasses."""

    def __init__(self, creds):
        from google.auth.transport.requests import AuthorizedSession
        self.session = AuthorizedSession(creds)

    def __call__(self, url: str, type: str) -> None:
        import requests
        try:
            r = self.session.post(ENDPOINT, json={"url": url, "type": type}, timeout=TIMEOUT)
        except (requests.RequestException, OSError) as e:
            raise PublishError(f"rede: {e.__class__.__name__}") from None
        except Exception as e:  # erro ao renovar o token (google.auth.exceptions)
            raise PublishError(f"autenticação: {e.__class__.__name__}") from None
        if r.status_code == 200:
            return
        try:
            error = r.json().get("error", {})
        except ValueError:
            error = {}
        message = str(error.get("message") or r.text[:300]).strip()
        if r.status_code == 429 or error.get("status") == "RESOURCE_EXHAUSTED":
            raise QuotaError(f"HTTP {r.status_code}: {message}")
        if r.status_code == 403 and "ownership" in message.lower():
            raise OwnershipError(
                "sem permissão no Search Console: a conta de serviço precisa ser "
                "Proprietário (Owner) da propriedade do site, não só Completo (Full) "
                f"[HTTP 403: {message}]")
        raise PublishError(f"HTTP {r.status_code}: {message}")


def slugify(text: str | None, limit: int = 70) -> str:
    """"Desenvolvedor(a) PHP Sênior" -> "desenvolvedor-a-php-senior"."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:limit].rstrip("-") or "vaga"


def job_path(job: dict) -> str | None:
    """Página da vaga no site (/vaga/<seq>-<título>), só para vagas de portais."""
    if job.get("source") == "post" or not job.get("seq"):
        return None
    return f"/vaga/{job['seq']}-{slugify(job.get('title'))}"


def open_urls(store) -> list[str]:
    """URLs absolutas das vagas abertas: as mesmas páginas de vaga do sitemap."""
    from .store import DEDUP
    base = (os.getenv("VAGAS_SITE_URL") or SITE_URL).strip().rstrip("/")
    rows = store.execute(
        f"""SELECT seq, source, title, COALESCE(posted_at, first_seen) AS posted FROM jobs
            WHERE source != 'post' AND relevant = 1 AND dismissed IS NULL
              AND closed_at IS NULL AND COALESCE(posted_at, first_seen) >= ? AND {DEDUP}
            ORDER BY posted DESC""", (dates.cutoff(),))
    return [base + job_path(dict(r)) for r in rows]


def _recent_ok(store, since: str) -> set[str]:
    rows = store.execute("SELECT url FROM indexing_log WHERE status = 'ok' AND pushed_at >= ?",
                         (since,)).fetchall()
    return {r[0] for r in rows}


def _record(store, url: str, status: str, detail: str | None) -> None:
    # Uma linha por URL (a última tentativa). REPLACE funciona no MySQL e no SQLite (testes).
    store.execute("REPLACE INTO indexing_log (url, pushed_at, status, detail) "
                  "VALUES (?, ?, ?, ?)", (url, _iso(_now()), status, (detail or "")[:1000]))


def publish(urls, type: str = "URL_UPDATED", limit: int = DEFAULT_LIMIT,
            daily_cap: int = DAILY_CAP, dry_run: bool = False, force: bool = False,
            *, store=None, publisher=None) -> dict:
    """Publica `urls` na Indexing API e grava cada tentativa em indexing_log.

    Pula as já publicadas com sucesso nas últimas 24 h (salvo `force`); envia no máximo
    `limit` por execução e não passa de `daily_cap` sucessos em 24 h. 403 de propriedade
    e 429 de quota param o lote sem levantar exceção. `dry_run` não chama a API nem grava.
    `publisher(url, type)` substitui a chamada real (testes)."""
    if store is None:
        from .store import Store
        store = Store()
    since = _iso(_now() - WINDOW)
    recent = _recent_ok(store, since)
    room = max(0, daily_cap - len(recent))
    out = {"enviados": [], "pulados": [], "falhas": [], "adiados": [],
           "restante_hoje": room, "dry_run": dry_run}

    pending = []
    for url in dict.fromkeys(urls):  # sem repetidas, na ordem dada
        if url in recent and not force:
            out["pulados"].append(url)
        else:
            pending.append(url)
    batch, out["adiados"] = pending[:min(limit, room)], pending[min(limit, room):]
    if not batch:
        return out
    if dry_run:
        out["enviados"] = batch
        out["restante_hoje"] = room - len(batch)
        return out

    if publisher is None:
        creds = credentials()
        if creds is None:
            out["adiados"] = pending
            return out
        publisher = GooglePublisher(creds)

    for i, url in enumerate(batch):
        try:
            publisher(url, type)
        except OwnershipError as e:
            # Vale para o domínio todo: as outras URLs falhariam igual.
            log.warning("Indexing API: %s", e)
            _record(store, url, "sem_permissao", str(e))
            out["falhas"].append({"url": url, "erro": str(e)})
            out["adiados"] = batch[i + 1:] + out["adiados"]
            break
        except QuotaError as e:
            log.warning("Indexing API: quota esgotada (%s); lote interrompido", e)
            _record(store, url, "quota", str(e))
            out["falhas"].append({"url": url, "erro": str(e)})
            out["adiados"] = batch[i + 1:] + out["adiados"]
            room = len(out["enviados"])  # o Google disse que acabou: restante_hoje = 0
            break
        except PublishError as e:
            log.warning("Indexing API: %s: %s", url, e)
            _record(store, url, "erro", str(e))
            out["falhas"].append({"url": url, "erro": str(e)})
        else:
            _record(store, url, "ok", None)
            out["enviados"].append(url)
    out["restante_hoje"] = max(0, room - len(out["enviados"]))
    if out["enviados"]:
        log.info("Indexing API: %d URL(s) publicadas (%s)", len(out["enviados"]), type)
    return out
