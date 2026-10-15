"""Serviço contínuo: servidor MCP (HTTP) + coleta agendada das fontes de vagas.

Cada fonte tem o seu intervalo. As que não usam navegador (LinkedIn público, Gupy, GitHub
e os demais portais)
rodam numa thread comum; a busca de publicações usa o navegador logado, numa thread
única (o Playwright síncrono não é thread-safe e o perfil do Chromium só aceita um
navegador por vez — a trava em .session/ também coordena com o projeto linkedin).

Uso: python -m vagas_php.service   (MCP em http://HOST:PORT/mcp)
"""

import asyncio
import json
import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from . import collect, dates, linkedin_post, php
from .store import SOURCES, Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VAGAS_DATA_DIR", ROOT / "data"))
CONFIG_PATH = DATA_DIR / "config.json"
# Próximas coletas, para o site (outro processo) mostrar a defasagem dos dados.
SCHEDULE_PATH = DATA_DIR / "schedule.json"
RETRY_AFTER_ERROR = timedelta(minutes=30)
# Post diário no LinkedIn (print do dashboard): tentativas dentro desta janela após o horário.
DAILY_POST_WINDOW = timedelta(hours=3)
DAILY_POST_MAX_TRIES = 3
# Coletas agendadas: as fontes de vagas.
COLLECTORS = SOURCES
# Usa o navegador logado (sempre na mesma thread).
BROWSER = ("post",)
# Intervalo mínimo por fonte: a busca logada usa a sua conta do LinkedIn.
MIN_INTERVAL = {"linkedin": 0.5, "gupy": 0.5, "github": 0.25, "post": 2,
                "inhire": 1, "solides": 0.5, "catho": 1, "remotar": 0.5, "programathor": 1,
                "coodesh": 1, "nerdin": 1, "recrutei": 1, "upvagas": 0.5}

log = logging.getLogger("vagas_php.service")


def _days(spec: str) -> set[int]:
    """Dias da semana (0 = segunda ... 6 = domingo): "0-6", "0-4" ou "0,2,4"."""
    days = set()
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        days |= set(range(int(a), int(b or a) + 1))
    return days


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "sim")


@dataclass
class SourceConfig:
    enabled: bool
    interval_hours: float
    # Janela "HH-HH" em que a coleta pode rodar (ex.: "8-22"); vazio = o dia todo.
    active_hours: str = ""

    def validate(self, source: str) -> None:
        if self.interval_hours < MIN_INTERVAL[source]:
            raise ValueError(f"interval_hours mínimo de {source} é {MIN_INTERVAL[source]}")
        self.active_window()

    def active_window(self) -> tuple[int, int] | None:
        if not self.active_hours.strip():
            return None
        try:
            start, end = (int(x) for x in self.active_hours.split("-"))
        except ValueError:
            raise ValueError('active_hours deve ser "HH-HH", ex.: "8-22"') from None
        if not (0 <= start <= 23 and 0 <= end <= 24 and start != end):
            raise ValueError('active_hours inválido, ex.: "8-22" ou "22-6"')
        return start, end

    def is_active(self, now: datetime) -> bool:
        window = self.active_window()
        if not window:
            return True
        start, end = window
        h = now.hour
        return start <= h < end if start < end else (h >= start or h < end)

    def next_active(self, at: datetime) -> datetime:
        """`at`, ou o início da janela seguinte se `at` cai fora dela."""
        if self.is_active(at):
            return at
        t = at.replace(minute=0, second=0, microsecond=0)
        for _ in range(48):
            t += timedelta(hours=1)
            if self.is_active(t):
                return t
        return at


@dataclass
class Config:
    sources: dict[str, SourceConfig] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Config":
        env = lambda name, default: os.getenv(name) or default  # noqa: E731
        cfg = cls({
            "linkedin": SourceConfig(
                enabled=_env_bool("VAGAS_LINKEDIN_ENABLED", True),
                interval_hours=float(env("VAGAS_LINKEDIN_INTERVAL_HOURS", 3))),
            "gupy": SourceConfig(
                enabled=_env_bool("VAGAS_GUPY_ENABLED", True),
                interval_hours=float(env("VAGAS_GUPY_INTERVAL_HOURS", 2))),
            "github": SourceConfig(
                enabled=_env_bool("VAGAS_GITHUB_ENABLED", True),
                interval_hours=float(env("VAGAS_GITHUB_INTERVAL_HOURS", 1))),
            "inhire": SourceConfig(
                enabled=_env_bool("VAGAS_INHIRE_ENABLED", True),
                interval_hours=float(env("VAGAS_INHIRE_INTERVAL_HOURS", 2))),
            "solides": SourceConfig(
                enabled=_env_bool("VAGAS_SOLIDES_ENABLED", True),
                interval_hours=float(env("VAGAS_SOLIDES_INTERVAL_HOURS", 2))),
            "catho": SourceConfig(
                enabled=_env_bool("VAGAS_CATHO_ENABLED", True),
                interval_hours=float(env("VAGAS_CATHO_INTERVAL_HOURS", 3))),
            "remotar": SourceConfig(
                enabled=_env_bool("VAGAS_REMOTAR_ENABLED", True),
                interval_hours=float(env("VAGAS_REMOTAR_INTERVAL_HOURS", 2))),
            "programathor": SourceConfig(
                enabled=_env_bool("VAGAS_PROGRAMATHOR_ENABLED", True),
                interval_hours=float(env("VAGAS_PROGRAMATHOR_INTERVAL_HOURS", 3))),
            "coodesh": SourceConfig(
                enabled=_env_bool("VAGAS_COODESH_ENABLED", True),
                interval_hours=float(env("VAGAS_COODESH_INTERVAL_HOURS", 3))),
            "nerdin": SourceConfig(
                enabled=_env_bool("VAGAS_NERDIN_ENABLED", True),
                interval_hours=float(env("VAGAS_NERDIN_INTERVAL_HOURS", 3))),
            "recrutei": SourceConfig(
                enabled=_env_bool("VAGAS_RECRUTEI_ENABLED", True),
                interval_hours=float(env("VAGAS_RECRUTEI_INTERVAL_HOURS", 3))),
            "upvagas": SourceConfig(
                enabled=_env_bool("VAGAS_UPVAGAS_ENABLED", True),
                interval_hours=float(env("VAGAS_UPVAGAS_INTERVAL_HOURS", 2))),
            "post": SourceConfig(
                enabled=_env_bool("VAGAS_POSTS_ENABLED", True),
                interval_hours=float(env("VAGAS_POSTS_INTERVAL_HOURS", 8)),
                active_hours=os.getenv("VAGAS_POSTS_ACTIVE_HOURS", "8-22")),
        })
        # Ajustes feitos via MCP (configure_scheduler) têm precedência sobre o .env.
        if CONFIG_PATH.exists():
            for source, saved in json.loads(CONFIG_PATH.read_text()).items():
                if source in cfg.sources:
                    known = {k: v for k, v in saved.items() if k in asdict(cfg.sources[source])}
                    cfg.sources[source] = SourceConfig(**{**asdict(cfg.sources[source]), **known})
        for source, sc in cfg.sources.items():
            sc.validate(source)
        return cfg

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps({k: asdict(v) for k, v in self.sources.items()}, indent=2))


class Service:
    def __init__(self):
        self.store = Store()
        # O filtro de publicações pode ter mudado desde a coleta: reaplica ao que já está salvo.
        if changed := self.store.reclassify("post", php.is_php_hiring_post):
            log.info("Filtro de publicações reaplicado: %d mudaram (%s)", len(changed),
                     ", ".join(changed))
        if changed := self.store.reclassify_jobs():
            log.info("Filtro de vagas reaplicado: %d mudaram (%s)", len(changed),
                     ", ".join(changed[:20]) + ("..." if len(changed) > 20 else ""))
        self.config = Config.load()
        self.headless = _env_bool("LINKEDIN_HEADLESS", True)
        self.browser = ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")
        self.next_run: dict[str, datetime] = {}
        self.running: set[str] = set()
        self.locks = {s: asyncio.Lock() for s in COLLECTORS}
        self._wake = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        # Post diário no LinkedIn: horário (Brasília) e dias da semana (0 = segunda).
        self.daily_post = _env_bool("VAGAS_LINKEDIN_DAILY_POST", False)
        hour, minute = os.getenv("VAGAS_LINKEDIN_POST_TIME", "09:00").split(":")
        self.daily_post_time = (int(hour), int(minute))
        self.daily_post_days = _days(os.getenv("VAGAS_LINKEDIN_POST_DAYS", "0-6"))
        self.daily_post_tries: dict[str, list[datetime]] = {}
        self.daily_post_running = False

    async def collect(self, source: str, origin: str) -> dict:
        """Coleta uma fonte agora, desde a última coleta OK dela."""
        if source not in COLLECTORS:
            raise ValueError(f"fonte deve ser uma de {', '.join(COLLECTORS)}")
        async with self.locks[source]:
            self.running.add(source)
            self._write_schedule()
            log.info("Coleta %s (%s): iniciando", source, origin)
            # "post" usa o navegador: sempre na mesma thread. As outras são só HTTP.
            executor = self.browser if source in BROWSER else None
            try:
                result = await asyncio.get_running_loop().run_in_executor(
                    executor, collect.run, self.store, source, self.headless)
            except Exception:
                log.exception("Coleta %s (%s) falhou", source, origin)
                raise
            finally:
                self.running.discard(source)
                self._write_schedule()
            log.info("Coleta %s (%s): %s", source, origin, result)
            return result

    # --- agendador -----------------------------------------------------------

    def _schedule(self, source: str, after: datetime, delay: timedelta) -> None:
        jitter = random.uniform(-0.1, 0.1) * delay.total_seconds()  # evita horário fixo
        self.next_run[source] = after + delay + timedelta(seconds=jitter)

    def _initial_schedule(self) -> None:
        now = datetime.now().astimezone()
        for i, source in enumerate(self.config.sources):
            last = self.store.last_ok_start(source)
            first = now + timedelta(minutes=1 + i)  # escalona a primeira coleta
            if last:
                self._schedule(source, datetime.fromisoformat(last).astimezone(),
                               timedelta(hours=self.config.sources[source].interval_hours))
                self.next_run[source] = max(self.next_run[source], first)
            else:
                self.next_run[source] = first

    async def scheduler(self) -> None:
        while True:
            try:
                await self._scheduler_loop()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Agendador falhou; reiniciando em 60s")
                await asyncio.sleep(60)

    async def _scheduler_loop(self) -> None:
        self._initial_schedule()
        log.info("Agendador: %s", self._next_runs())
        self._write_schedule()
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=60)
            except TimeoutError:
                pass
            self._wake.clear()
            self._write_schedule()
            now = datetime.now().astimezone()
            for source, cfg in self.config.sources.items():
                if (not cfg.enabled or source in self.running or now < self.next_run[source]
                        or not cfg.is_active(now)):
                    continue
                task = asyncio.create_task(self._scheduled(source, now))
                self._tasks.add(task)  # mantém referência até terminar
                task.add_done_callback(self._tasks.discard)
            if self._daily_post_due():
                task = asyncio.create_task(self._daily_post())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)

    def _daily_post_due(self) -> bool:
        """Hora do post diário: dia escolhido, depois do horário (até a janela acabar),
        ainda não publicado hoje e com menos de 3 tentativas (30 min entre elas)."""
        if not self.daily_post or self.daily_post_running:
            return False
        now = dates.now_utc().astimezone(dates.BRASILIA)
        start = now.replace(hour=self.daily_post_time[0], minute=self.daily_post_time[1],
                            second=0, microsecond=0)
        if now.weekday() not in self.daily_post_days or not start <= now < start + DAILY_POST_WINDOW:
            return False
        day = now.date().isoformat()
        tries = self.daily_post_tries.get(day, [])
        if len(tries) >= DAILY_POST_MAX_TRIES or (tries and now - tries[-1] < RETRY_AFTER_ERROR):
            return False
        return not linkedin_post.posted_on(DATA_DIR, day)

    async def _daily_post(self) -> None:
        now = dates.now_utc().astimezone(dates.BRASILIA)
        self.daily_post_tries.setdefault(now.date().isoformat(), []).append(now)
        self.daily_post_running = True
        log.info("Post diário no LinkedIn: iniciando")
        try:
            # Usa o navegador logado: mesma thread da coleta "post".
            entry = await asyncio.get_running_loop().run_in_executor(
                self.browser, linkedin_post.run, DATA_DIR, self.headless)
            log.info("Post diário no LinkedIn: publicado %s", entry.get("numbers"))
        except Exception:
            log.exception("Post diário no LinkedIn falhou")
        finally:
            self.daily_post_running = False

    async def _scheduled(self, source: str, now: datetime) -> None:
        interval = timedelta(hours=self.config.sources[source].interval_hours)
        # Marca já a próxima, para o laço não disparar a mesma fonte de novo.
        self._schedule(source, now, interval)
        try:
            await self.collect(source, "agendada")
        except Exception:
            self._schedule(source, now, min(RETRY_AFTER_ERROR, interval))
        log.info("Agendador: próxima coleta %s em %s", source,
                 self.next_run[source].isoformat(timespec="minutes"))

    def _write_schedule(self) -> None:
        """Grava as próximas coletas (já ajustadas à janela de horário) para o site."""
        now = datetime.now().astimezone()
        sources = {}
        for source, cfg in self.config.sources.items():
            nxt = self.next_run.get(source)
            sources[source] = {
                "enabled": cfg.enabled, "running": source in self.running,
                "interval_hours": cfg.interval_hours, "active_hours": cfg.active_hours,
                "next_run": cfg.next_active(max(nxt, now)).isoformat(timespec="seconds")
                if cfg.enabled and nxt else None,
            }
        tmp = SCHEDULE_PATH.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"updated_at": now.isoformat(timespec="seconds"),
                                       "sources": sources}))
            tmp.replace(SCHEDULE_PATH)
        except OSError as e:
            log.warning("Não foi possível gravar %s: %s", SCHEDULE_PATH, e)

    def _next_runs(self) -> dict:
        return {s: t.isoformat(timespec="minutes") for s, t in self.next_run.items()}

    def reconfigure(self, source: str, **changes) -> None:
        if source not in self.config.sources:
            raise ValueError(f"fonte deve ser uma de {', '.join(COLLECTORS)}")
        old = self.config.sources[source]
        new = SourceConfig(**{**asdict(old), **changes})
        new.validate(source)
        self.config.sources[source] = new
        self.config.save()
        if new.interval_hours != old.interval_hours:
            last = self.store.last_ok_start(source)
            base = datetime.fromisoformat(last).astimezone() if last else datetime.now().astimezone()
            self._schedule(source, base, timedelta(hours=new.interval_hours))
        self._wake.set()

    def status(self) -> dict:
        return {
            "config": {k: asdict(v) for k, v in self.config.sources.items()},
            "collecting_now": sorted(self.running),
            "next_runs": self._next_runs(),
            "headless": self.headless,
            **self.store.stats(),
        }


def build_server(service: Service) -> MCPServer:
    mcp = MCPServer(
        name="vagas-php",
        instructions=(
            "Vagas de engenharia de software com PHP (Laravel, Symfony...) coletadas do "
            "LinkedIn (busca pública de vagas e publicações anunciando vagas), da Gupy, da "
            "Sólides, da Catho, da Remotar, da Programathor, da Coodesh, da Nerdin, da Recrutei, da UpVagas, de empresas que usam a InHire e de issues de repositórios de vagas no GitHub. Use list_jobs para consultar a base local."
        ),
    )
    local_read = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

    @mcp.tool(annotations=local_read)
    async def list_jobs(q: str | None = None, source: str | None = None,
                        workplace: str | None = None, seniority: str | None = None,
                        stack: str | None = None, hours: float = 72,
                        include_closed: bool = False, limit: int = 30,
                        offset: int = 0) -> dict:
        """Consulta as vagas PHP já coletadas, publicadas há no máximo 72 h (mais recentes
        primeiro). q: palavras no título/empresa/descrição; source: "linkedin", "gupy",
        "remotar", "programathor", "catho", "solides", "inhire", "coodesh", "nerdin", "recrutei", "upvagas", "post" ou "github"; workplace: "Remoto", "Híbrido" ou "Presencial"; seniority: "Estágio", "Júnior", "Pleno",
        "Sênior" ou "Especialista"; stack: ex. "Laravel"; hours: publicadas nas últimas N
        horas (máximo 72: vagas mais antigas não são consideradas)."""
        jobs = service.store.query_jobs(q, source, workplace, seniority, stack, hours,
                                        include_closed, limit=min(limit, 200), offset=offset)
        for j in jobs:
            if j["description"] and len(j["description"]) > 1500:
                j["description"] = j["description"][:1500] + "…"
        return {"count": len(jobs), "jobs": jobs}

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def collect_now(source: str) -> dict:
        """Coleta agora uma fonte: "linkedin" (vagas, sem login), "gupy" (sem login),
        "remotar", "programathor", "catho", "solides", "coodesh", "nerdin", "recrutei", "upvagas" (portais, sem login), "inhire" (páginas de carreira das empresas, sem login), "github" (issues) ou "post" (publicações, usa o navegador logado: mais lento)."""
        try:
            return await service.collect(source, "mcp")
        except ValueError as e:
            raise ToolError(str(e)) from e

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def check_post(url: str) -> dict:
        """Confere um post do LinkedIn pelo link (linkedin.com/posts/... ou lnkd.in/...):
        lê o post público (sem login), aplica o filtro e diz qual regra decidiu (rule,
        rule_title, rule_effect) e se aparece no site (relevant e in_window: publicado
        nas últimas 72 h). Guarda o post na base se falar de PHP, como a busca faria."""
        try:
            return await asyncio.get_running_loop().run_in_executor(
                None, collect.import_post, service.store, url)
        except RuntimeError as e:
            raise ToolError(str(e)) from e

    @mcp.tool(annotations=local_read)
    async def get_status() -> dict:
        """Configuração do agendador, próximas coletas, totais por fonte e últimas execuções."""
        return service.status()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True,
                                          openWorldHint=False))
    async def configure_scheduler(source: str, enabled: bool | None = None,
                                  interval_hours: float | None = None,
                                  active_hours: str | None = None) -> dict:
        """Altera a coleta agendada de uma fonte ("linkedin", "gupy", "remotar", "programathor",
        "catho", "solides", "inhire", "coodesh", "nerdin", "recrutei", "upvagas",
        "github" ou "post"),
        persistente. interval_hours: horas entre coletas; active_hours: janela "HH-HH"
        (ex. "8-22"), "" para o dia todo; enabled: liga/desliga."""
        changes = {k: v for k, v in dict(enabled=enabled, interval_hours=interval_hours,
                                         active_hours=active_hours).items() if v is not None}
        try:
            service.reconfigure(source, **changes)
        except ValueError as e:
            raise ToolError(str(e)) from e
        return service.status()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True,
                                          openWorldHint=False))
    async def dismiss_job(ref: str, reason: str | None = None, undo: bool = False) -> dict:
        """Marca uma vaga/publicação como "não é vaga" e a tira do site, da API e do
        list_jobs, mesmo se for coletada de novo. ref: id (ex. "post:urn:li:share:..."),
        URL ou número do post/vaga. reason: motivo opcional. undo: desfaz."""
        rows = service.store.dismiss(ref, reason, undo)
        if not rows:
            raise ToolError(f"Nenhuma vaga encontrada para {ref!r}")
        return {"dismissed": not undo, "jobs": rows}

    return mcp


async def main() -> None:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    service = Service()
    mcp = build_server(service)
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", 8000))
    security = TransportSecuritySettings(
        allowed_hosts=["localhost:*", "127.0.0.1:*"],
        allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
    )
    scheduler = asyncio.create_task(service.scheduler())
    log.info("MCP em http://%s:%d/mcp", host, port)
    try:
        await mcp.run_streamable_http_async(host=host, port=port, transport_security=security)
    finally:
        scheduler.cancel()


if __name__ == "__main__":
    asyncio.run(main())
