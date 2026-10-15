"""MySQL 8 com as vagas coletadas (LinkedIn, Gupy, posts do LinkedIn, GitHub, Remotar,
Programathor, Catho, Sólides, InHire e Coodesh) e o histórico
de execuções de cada coletor. O site usa a mesma base, só para leitura.

Conexão: DATABASE_URL=mysql://usuario:senha@host:3306/base[?ssl-mode=REQUIRED] (senha
com caracteres especiais vai codificada, ex.: @ -> %40)."""

import logging
import os
import re
import ssl
import threading
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, unquote, urlparse

import pymysql

from . import dates, php

log = logging.getLogger(__name__)

SOURCES = ("linkedin", "gupy", "post", "github", "remotar", "programathor", "catho", "solides",
           "inhire", "coodesh", "nerdin", "recrutei", "upvagas")
# Pessoa conta como procurando emprego enquanto tiver o selo, ou por SEEKER_ACTIVE_DAYS
# depois do último post dizendo que procura (quem nunca usou o selo).
SEEKER_ACTIVE_DAYS = float(os.getenv("VAGAS_SEEKERS_ACTIVE_DAYS", 30))
SEEKER_ACTIVE = "left_at IS NULL AND (open_to_work = 1 OR last_seen >= ?)"
# Só o mercado brasileiro conta: brazil = 1 (local do perfil no Brasil). Quem ainda não
# teve o perfil visitado fica com NULL (aguardando); quem é de fora (local ou posts em
# outra língua) fica com 0, guardado mas fora das contagens e das visitas.

# Datas ficam como texto ISO UTC ("2026-10-15T12:00:00+00:00"), comparadas como string.
# Chaves em utf8mb4_bin: ids e URLs diferem por maiúscula/acento; o resto usa a collation
# padrão (sem diferenciar maiúsculas nem acentos nas buscas com LIKE).
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS jobs (
    id          VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY, -- "linkedin:<id>", "gupy:<id>", "post:<urn ou hash>", "github:<repo>#<n>", "inhire:<uuid>", "<fonte>:<id>" nas demais
    seq         BIGINT NOT NULL AUTO_INCREMENT UNIQUE,         -- ordem de inserção (DEDUP)
    source      VARCHAR(32) NOT NULL,  -- ver SOURCES
    relevant    TINYINT NOT NULL,      -- 1 = vaga de engenharia de software com PHP
    title       TEXT,
    company     VARCHAR(512),
    location    VARCHAR(512),
    workplace   VARCHAR(32),           -- Remoto | Híbrido | Presencial
    seniority   VARCHAR(32),           -- Estágio | Júnior | Pleno | Sênior | Especialista
    contract    VARCHAR(32),           -- CLT | PJ | Freelance
    stack       VARCHAR(512),          -- "PHP,Laravel"
    salary      VARCHAR(255),
    url         TEXT,
    author      VARCHAR(512),
    author_url  TEXT,
    description MEDIUMTEXT,
    posted_at   VARCHAR(40),           -- quando foi publicada (ISO; aproximada para posts)
    first_seen  VARCHAR(40) NOT NULL,
    last_seen   VARCHAR(40) NOT NULL,
    closed_at   VARCHAR(40),           -- issue fechada no GitHub
    dismissed   TEXT,                  -- descartada à mão ("não é vaga"): data e motivo
    INDEX jobs_list (relevant, posted_at),
    INDEX jobs_source (source)
)""",
    # Pessoas com perfil PHP procurando emprego (LinkedIn). Guardadas sem prazo; o site
    # só mostra quantidades (dashboard), os dados ficam para o MCP (list_seekers).
    """CREATE TABLE IF NOT EXISTS people (
    profile_url   VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY, -- https://www.linkedin.com/in/<slug>/
    name          VARCHAR(512),
    headline      TEXT,
    location      VARCHAR(512),        -- do perfil (só depois da primeira visita)
    brazil        TINYINT,             -- 1 Brasil, 0 fora, NULL ainda não se sabe
    seeking_roles TEXT,                -- "Cargos de Desenvolvedor PHP..." do bloco do selo
    stack         VARCHAR(512),
    seniority     VARCHAR(32),
    open_to_work  TINYINT,             -- selo "buscando emprego": 1, 0 ou NULL (não visto)
    first_seen    VARCHAR(40) NOT NULL, -- primeira vez vista procurando emprego
    last_seen     VARCHAR(40) NOT NULL, -- último sinal de procura (post ou selo)
    checked_at    VARCHAR(40),         -- última visita ao perfil
    left_at       VARCHAR(40)          -- quando tirou o selo (NULL: ainda procurando)
)""",
    """CREATE TABLE IF NOT EXISTS people_posts (
    id          VARCHAR(255) COLLATE utf8mb4_bin PRIMARY KEY, -- "post:<urn ou hash>"
    profile_url VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    url         TEXT,
    text        MEDIUMTEXT,
    posted_at   VARCHAR(40),
    first_seen  VARCHAR(40) NOT NULL,
    INDEX people_posts_profile (profile_url)
)""",
    # Entradas (começou ou voltou a procurar) e saídas (tirou o selo), para os volumes por
    # dia/semana/mês.
    """CREATE TABLE IF NOT EXISTS people_events (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    profile_url VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,
    kind        VARCHAR(16) NOT NULL,  -- entered | left
    at          VARCHAR(40) NOT NULL,
    INDEX people_events_at (kind, at)
)""",
    # Quantas pessoas estavam procurando em cada dia (Brasília), gravado pelo serviço.
    """CREATE TABLE IF NOT EXISTS people_daily (
    day    VARCHAR(10) PRIMARY KEY,
    active INT NOT NULL,
    brazil INT NOT NULL
)""",
    """CREATE TABLE IF NOT EXISTS runs (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    source      VARCHAR(32) NOT NULL,
    started_at  VARCHAR(40) NOT NULL,
    finished_at VARCHAR(40),
    ok          TINYINT,
    found       INT,
    new_jobs    INT,
    error       TEXT,
    INDEX runs_source (source, id)
)""",
]

# A mesma vaga é anunciada várias vezes (ex.: um ID do LinkedIn por cidade): vale só a
# mais recente de cada título + empresa da mesma fonte.
DEDUP = """seq IN (SELECT max(seq) FROM jobs GROUP BY source,
             lower(COALESCE(title, '')), lower(COALESCE(company, author, '')))"""

FIELDS = ("source", "relevant", "title", "company", "location", "workplace", "seniority",
          "contract", "stack", "salary", "url", "author", "author_url", "description",
          "posted_at", "closed_at")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect_args(url: str | None = None) -> dict:
    url = url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("defina DATABASE_URL=mysql://usuario:senha@host:3306/base")
    u = urlparse(url)
    if u.scheme not in ("mysql", "mysql+pymysql") or not u.path.strip("/"):
        raise RuntimeError("DATABASE_URL deve ser mysql://usuario:senha@host:3306/base")
    # TLS como no cliente mysql: ?ssl-mode=REQUIRED (cifra, sem validar o certificado),
    # VERIFY_CA ou VERIFY_IDENTITY (validam pela CA de ?ssl-ca=/caminho.pem ou do sistema).
    params = {k.lower(): v[-1] for k, v in parse_qs(u.query).items()}
    mode = params.get("ssl-mode", "DISABLED").upper()
    tls = {}
    if mode == "REQUIRED":
        ctx = ssl.create_default_context()
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
        tls = {"ssl": ctx}
    elif mode in ("VERIFY_CA", "VERIFY_IDENTITY"):
        ctx = ssl.create_default_context(cafile=params.get("ssl-ca"))
        ctx.check_hostname = mode == "VERIFY_IDENTITY"
        tls = {"ssl": ctx}
    elif mode not in ("DISABLED", "PREFERRED"):
        raise RuntimeError(f"ssl-mode inválido: {mode}")
    return {**tls, "host": u.hostname or "localhost", "port": u.port or 3306,
            "user": unquote(u.username or ""), "password": unquote(u.password or ""),
            "database": unquote(u.path.strip("/")), "charset": "utf8mb4", "autocommit": True,
            "connect_timeout": 10,
            # sql_mode padrão do MySQL 8 (bancos gerenciados podem vir com ANSI_QUOTES etc.);
            # group_concat (classificação de pessoas) corta em 1024 bytes por padrão.
            "init_command": "SET SESSION sql_mode = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,"
                            "NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,"
                            "NO_ENGINE_SUBSTITUTION', group_concat_max_len = 1048576, "
                            "time_zone = '+00:00'"}


class Row(tuple):
    """Linha acessível por posição e por nome, como sqlite3.Row: dict(row) funciona."""

    def __new__(cls, values, names):
        row = super().__new__(cls, (_plain(v) for v in values))
        row._names = names
        return row

    def keys(self):
        return self._names

    def __getitem__(self, key):
        if isinstance(key, str):
            return tuple.__getitem__(self, self._names.index(key))
        return tuple.__getitem__(self, key)


def _plain(value):
    # sum()/count() voltam como Decimal no MySQL: o JSON do site não aceita.
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


class Result:
    def __init__(self, cursor):
        names = tuple(d[0] for d in cursor.description or ())
        self.rows = [Row(r, names) for r in cursor.fetchall()] if names else []
        self.lastrowid = cursor.lastrowid

    def __iter__(self):
        return iter(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Store:
    # Conexão ociosa há mais que isso é testada (ping) antes de usar: o MySQL derruba
    # conexões paradas (wait_timeout) e a base pode estar em outro servidor.
    IDLE_CHECK = 60

    def __init__(self, url: str | None = None, readonly: bool = False, wait: float = 120):
        self.args = connect_args(url)
        # Coletores rodam em threads diferentes: uma conexão por thread; a trava
        # serializa as escritas.
        self.local = threading.local()
        self.lock = threading.RLock()
        self._wait_for_db(wait)
        if not readonly:
            for statement in SCHEMA:
                self.execute(statement)
            self._classify_people()
            self._normalize_dates()

    def _wait_for_db(self, wait: float) -> None:
        """Na subida o MySQL pode ainda não aceitar conexões: tenta por `wait` s."""
        deadline = time.monotonic() + wait
        while True:
            try:
                self._conn()
                return
            except pymysql.err.OperationalError as e:
                if time.monotonic() >= deadline:
                    raise
                log.warning("MySQL indisponível (%s); tentando de novo em 3 s", e)
                time.sleep(3)

    def _conn(self) -> pymysql.connections.Connection:
        conn = getattr(self.local, "conn", None)
        if conn is None:
            conn = self.local.conn = pymysql.connect(**self.args)
        elif time.monotonic() - self.local.used > self.IDLE_CHECK and not self.local.in_tx:
            conn.ping(reconnect=True)
        self.local.used = time.monotonic()
        self.local.in_tx = getattr(self.local, "in_tx", False)
        return conn

    @staticmethod
    def _sql(sql: str) -> str:
        # As consultas usam "?" (como no SQLite); o PyMySQL espera "%s" e "%%".
        return sql.replace("%", "%%").replace("?", "%s")

    def execute(self, sql: str, args=()) -> Result:
        with self._conn().cursor() as cur:
            cur.execute(self._sql(sql), tuple(args))
            return Result(cur)

    def executemany(self, sql: str, rows) -> None:
        rows = list(rows)
        if rows:
            with self._conn().cursor() as cur:
                cur.executemany(self._sql(sql), rows)

    @contextmanager
    def tx(self):
        """Transação (e trava de escrita) na conexão da thread."""
        with self.lock:
            conn = self._conn()
            conn.begin()
            self.local.in_tx = True
            try:
                yield
            except BaseException:
                conn.rollback()
                raise
            else:
                conn.commit()
            finally:
                self.local.in_tx = False

    def _classify_people(self) -> None:
        """Preenche people.brazil de quem ainda não tem: pelo local do perfil ou, sem
        local, como de fora se nenhum post da pessoa está em português."""
        rows = self.execute(
            """SELECT profile_url, location, (SELECT group_concat(text SEPARATOR ' ') FROM people_posts pp
                                              WHERE pp.profile_url = p.profile_url)
               FROM people p WHERE brazil IS NULL""").fetchall()
        with self.tx():
            for url, location, texts in rows:
                br = php.is_brazil(location)
                if br is None and texts and not php.looks_portuguese(texts):
                    br = False
                if br is not None:
                    self.execute("UPDATE people SET brazil = ? WHERE profile_url = ?",
                                    (int(br), url))

    def _normalize_dates(self) -> None:
        """Bases antigas guardavam posted_at como veio da fonte ("2026-10-09",
        "...Z"); converte tudo para ISO UTC, que é o que as consultas comparam."""
        rows = self.execute("SELECT id, posted_at FROM jobs WHERE posted_at IS NOT NULL "
                               "AND posted_at NOT LIKE ?", ("%+00:00",)).fetchall()
        with self.tx():
            for job_id, posted in rows:
                self.execute("UPDATE jobs SET posted_at = ? WHERE id = ?",
                                (dates.normalize(posted), job_id))

    def known(self, source: str) -> dict[str, dict]:
        """id -> {description, relevant} das vagas já vistas de uma fonte."""
        return {r["id"]: dict(r) for r in self.execute(
            "SELECT id, description, relevant FROM jobs WHERE source = ?", (source,))}

    def texts_mentioning(self, needle: str) -> list[str]:
        """Descrições e URLs de vagas que citam `needle` (ex.: "inhire.app", para
        descobrir empresas)."""
        like = f"%{needle}%"
        return [r[0] for r in self.execute(
            "SELECT CONCAT(COALESCE(description, ''), ' ', COALESCE(url, '')) FROM jobs "
            "WHERE description LIKE ? OR url LIKE ?", (like, like))]

    def save_jobs(self, jobs: list[dict]) -> int:
        """Insere ou atualiza; retorna quantas vagas relevantes eram novas."""
        now, new = now_iso(), 0
        with self.tx():
            for job in jobs:
                row = {f: job.get(f) for f in FIELDS}
                exists = self.execute("SELECT 1 FROM jobs WHERE id = ?", (job["id"],)).fetchone()
                new += bool(not exists and row["relevant"])
                self.execute(
                    f"""INSERT INTO jobs (id, {", ".join(FIELDS)}, first_seen, last_seen)
                        VALUES (?, {", ".join("?" * len(FIELDS))}, ?, ?) AS new
                        ON DUPLICATE KEY UPDATE
                            relevant = new.relevant, title = new.title,
                            company = COALESCE(new.company, jobs.company),
                            location = COALESCE(new.location, jobs.location),
                            workplace = COALESCE(new.workplace, jobs.workplace),
                            seniority = COALESCE(new.seniority, jobs.seniority),
                            contract = COALESCE(new.contract, jobs.contract),
                            stack = COALESCE(new.stack, jobs.stack),
                            salary = COALESCE(new.salary, jobs.salary),
                            url = COALESCE(new.url, jobs.url),
                            description = CASE WHEN char_length(COALESCE(new.description, ''))
                                                    > char_length(COALESCE(jobs.description, ''))
                                               THEN new.description ELSE jobs.description END,
                            posted_at = COALESCE(jobs.posted_at, new.posted_at),
                            closed_at = new.closed_at,
                            last_seen = new.last_seen""",
                    (job["id"], *row.values(), now, now))
        return new

    def reclassify(self, source: str, classify) -> list[str]:
        """Reaplica o filtro (classify(description) -> bool) às vagas já salvas de uma
        fonte, para mudanças no filtro valerem também para o que já foi coletado.
        Retorna os ids que mudaram."""
        rows = self.execute("SELECT id, description, relevant FROM jobs WHERE source = ?",
                               (source,)).fetchall()
        changed = [(int(bool(classify(r["description"]))), r["id"]) for r in rows
                   if bool(classify(r["description"])) != bool(r["relevant"])]
        with self.tx():
            self.executemany("UPDATE jobs SET relevant = ? WHERE id = ?", changed)
        return [job_id for _, job_id in changed]

    def reclassify_jobs(self) -> list[str]:
        """Reaplica php.is_php_job às vagas de portais já salvas (todas as fontes menos
        "post"), para mudanças na regra valerem também para o que já foi coletado. As
        etiquetas das issues do GitHub não ficam na base: issue aceita por etiqueta
        continua aceita. Retorna os ids que mudaram."""
        rows = self.execute("SELECT id, source, title, description, relevant FROM jobs "
                               "WHERE source != 'post'").fetchall()
        changed = []
        for r in rows:
            ok = php.is_php_job(r["title"], r["description"]) or (r["source"] == "github"
                                                                   and r["relevant"])
            if ok != bool(r["relevant"]):
                changed.append((int(ok), r["id"]))
        with self.tx():
            self.executemany("UPDATE jobs SET relevant = ? WHERE id = ?", changed)
        return [job_id for _, job_id in changed]

    def dismiss(self, ref: str, reason: str | None = None, undo: bool = False) -> list[dict]:
        """Marca como "não é vaga" (ou desfaz) pelo id, pela URL ou pelo número do
        post/vaga contido nela. Fica na base: novas coletas não trazem de volta."""
        ref = ref.strip()
        digits = re.findall(r"\d{12,}", ref)
        sql = "SELECT id, title, url FROM jobs WHERE id = ? OR url = ?"
        args = [ref, ref]
        if digits:
            sql += " OR id LIKE ?"
            args.append(f"%{digits[-1]}%")
        rows = [dict(r) for r in self.execute(sql, args)]
        mark = None if undo else f"{now_iso()} {reason or ''}".strip()
        with self.tx():
            self.executemany("UPDATE jobs SET dismissed = ? WHERE id = ?",
                                [(mark, r["id"]) for r in rows])
        return rows

    def query_jobs(self, q: str | None = None, source: str | None = None,
                   workplace: str | None = None, seniority: str | None = None,
                   stack: str | None = None, hours: float | None = None,
                   include_closed: bool = False, include_irrelevant: bool = False,
                   limit: int = 50, offset: int = 0) -> list[dict]:
        sql, args = "SELECT * FROM jobs WHERE 1=1", []
        if not include_irrelevant:
            sql += " AND relevant = 1 AND dismissed IS NULL"
        if not include_closed:
            sql += " AND closed_at IS NULL"
        if source:
            sql += " AND source = ?"
            args.append(source)
        for col, value in (("workplace", workplace), ("seniority", seniority)):
            if value:
                sql += f" AND {col} = ?"
                args.append(value)
        if stack:
            sql += " AND CONCAT(',', stack, ',') LIKE ?"
            args.append(f"%,{stack},%")
        if q:
            for word in q.split():
                sql += " AND (title LIKE ? OR company LIKE ? OR description LIKE ? OR location LIKE ?)"
                args += [f"%{word}%"] * 4
        # Só vagas publicadas nas últimas `hours` horas, nunca mais que 72 h.
        sql += " AND COALESCE(posted_at, first_seen) >= ?"
        args.append(dates.cutoff(hours))
        sql += f" AND {DEDUP}"
        sql += " ORDER BY COALESCE(posted_at, first_seen) DESC, first_seen DESC, seq DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        return [dict(r) for r in self.execute(sql, args)]

    def stats(self) -> dict:
        by_source = {r["source"]: dict(r) for r in self.execute(
            """SELECT source, count(*) total, sum(relevant AND dismissed IS NULL) relevant,
                      sum(relevant AND dismissed IS NULL AND closed_at IS NULL
                          AND COALESCE(posted_at, first_seen) >= ?) open
               FROM jobs GROUP BY source""", (dates.cutoff(),))}
        last = {}
        for source in SOURCES:
            run = self.execute("SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT 1",
                                  (source,)).fetchone()
            last[source] = dict(run) if run else None
        return {"sources": by_source, "last_runs": last}

    def dashboard(self, days: int = 14) -> dict:
        """Números do dashboard. Distribuições: vagas abertas das últimas 72 h (as que o
        site mostra). Série diária: vagas novas por dia de publicação (dia de Brasília)
        nos últimos `days` dias, incluindo as já encerradas."""
        today = datetime.now(dates.BRASILIA).date()
        first_day = today - timedelta(days=days - 1)
        start = datetime.combine(first_day, datetime.min.time(), dates.BRASILIA)
        rows = [dict(r) for r in self.execute(
            f"""SELECT source, company, workplace, seniority, contract, stack, closed_at,
                       COALESCE(posted_at, first_seen) AS posted
                FROM jobs WHERE relevant = 1 AND dismissed IS NULL AND {DEDUP}
                  AND COALESCE(posted_at, first_seen) >= ?""", (dates.utc_iso(start),))]
        cut72, cut24, cut48 = dates.cutoff(), dates.cutoff(24), dates.cutoff(48)
        live = [r for r in rows if r["posted"] >= cut72 and not r["closed_at"]]

        def count(key, items=live, missing="Não informado"):
            return Counter((r[key] or missing) for r in items).most_common()

        daily = {(first_day + timedelta(days=i)).isoformat(): Counter() for i in range(days)}
        for r in rows:
            day = datetime.fromisoformat(r["posted"]).astimezone(dates.BRASILIA).date().isoformat()
            if day in daily:
                daily[day][r["source"]] += 1
        stacks = Counter(s for r in live for s in (r["stack"] or "").split(",")
                         if s and s != "PHP")
        runs = {}
        for source in (*SOURCES, "seekers"):
            last = self.execute("SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT 1",
                                   (source,)).fetchone()
            day = self.execute(
                "SELECT count(*) total, sum(ok = 1) ok, sum(ok = 0) failed, sum(new_jobs) new "
                "FROM runs WHERE source = ? AND started_at >= ?", (source, cut24)).fetchone()
            last_ok = self.execute("SELECT finished_at FROM runs WHERE source = ? AND ok = 1 "
                                      "ORDER BY id DESC LIMIT 1", (source,)).fetchone()
            runs[source] = {"last": dict(last) if last else None, "last_24h": dict(day),
                            "last_ok_at": last_ok[0] if last_ok else None}
        since = self.execute("SELECT min(first_seen) FROM jobs").fetchone()[0]
        return {
            "max_age_hours": dates.MAX_AGE_HOURS,
            "kpis": {
                "open": len(live),
                "new_24h": sum(r["posted"] >= cut24 for r in rows),
                "prev_24h": sum(cut48 <= r["posted"] < cut24 for r in rows),
                "remote": sum(r["workplace"] == "Remoto" for r in live),
                "companies": len({r["company"] for r in live if r["company"]}),
            },
            "by_source": [[s, sum(r["source"] == s for r in live)] for s in SOURCES],
            "daily": [{"day": d, **{s: c[s] for s in SOURCES}} for d, c in daily.items()],
            "workplace": count("workplace"),
            "seniority": count("seniority"),
            "contract": count("contract"),
            "stack": stacks.most_common(8),
            "companies": Counter(r["company"] for r in live if r["company"]).most_common(8),
            "runs": runs,
            "collecting_since": since,
        }

    def rule_stats(self) -> dict:
        """Quantas vagas/posts da base cada regra de filtro decidiu (página /regras) e as
        descartadas à mão. Posts recusados na busca nem chegam à base: não entram aqui."""
        counts = Counter()
        for source, title, description, relevant in self.execute(
                "SELECT source, title, description, relevant FROM jobs WHERE dismissed IS NULL"):
            if source == "post":
                counts[php.post_verdict(description)] += 1
            else:  # etiquetas do GitHub não ficam na base: aceitas por elas = php_title
                verdict = php.job_verdict(title, description)
                counts["php_title" if relevant and verdict not in php.JOB_OK else verdict] += 1
        dismissed = [dict(r) for r in self.execute(
            "SELECT source, title, url, dismissed FROM jobs WHERE dismissed IS NOT NULL "
            "ORDER BY dismissed DESC")]
        return {"counts": dict(counts), "dismissed": dismissed}

    def start_run(self, source: str) -> int:
        with self.tx():
            return self.execute("INSERT INTO runs (source, started_at) VALUES (?, ?)",
                                   (source, now_iso())).lastrowid

    def finish_run(self, run_id: int, found: int = 0, new_jobs: int = 0,
                   error: str | None = None) -> None:
        with self.tx():
            self.execute(
                "UPDATE runs SET finished_at = ?, ok = ?, found = ?, new_jobs = ?, error = ? "
                "WHERE id = ?", (now_iso(), error is None, found, new_jobs, error, run_id))

    def last_runs(self, source: str | None = None, n: int = 5) -> list[dict]:
        if source:
            rows = self.execute("SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT ?",
                                   (source, n))
        else:
            rows = self.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (n,))
        return [dict(r) for r in rows]

    def last_ok_start(self, source: str) -> str | None:
        row = self.execute("SELECT started_at FROM runs WHERE source = ? AND ok = 1 "
                              "ORDER BY id DESC LIMIT 1", (source,)).fetchone()
        return row[0] if row else None

    # --- pessoas procurando emprego ---------------------------------------------

    def _seeker_cut(self) -> str:
        return dates.utc_iso(dates.now_utc() - timedelta(days=SEEKER_ACTIVE_DAYS))

    def _event(self, url: str, kind: str, at: str) -> None:
        self.execute("INSERT INTO people_events (profile_url, kind, at) VALUES (?, ?, ?)",
                        (url, kind, at))

    def save_seeker(self, person: dict, post: dict | None = None) -> bool:
        """Registra alguém visto procurando emprego (post ou selo na busca). Retorna True
        se é uma entrada: pessoa nova, ou que tinha tirado o selo e voltou a procurar."""
        url, now = person["profile_url"], now_iso()
        seen_at = min((post or {}).get("posted_at") or now, now)
        badge = 1 if person.get("open_to_work") else None
        with self.tx():
            row = self.execute("SELECT * FROM people WHERE profile_url = ?", (url,)).fetchone()
            if not row:
                self.execute(
                    """INSERT INTO people (profile_url, name, headline, stack, seniority,
                                           open_to_work, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (url, person.get("name"), person.get("headline"), person.get("stack"),
                     person.get("seniority"), badge, seen_at, seen_at))
                self._event(url, "entered", seen_at)
                entered = True
            else:
                entered = bool(row["left_at"] and seen_at > row["left_at"])
                self.execute(
                    """UPDATE people SET name = COALESCE(?, name), headline = COALESCE(?, headline),
                              stack = COALESCE(?, stack), seniority = COALESCE(?, seniority),
                              open_to_work = COALESCE(?, open_to_work),
                              last_seen = GREATEST(last_seen, ?),
                              left_at = CASE WHEN ? THEN NULL ELSE left_at END
                       WHERE profile_url = ?""",
                    (person.get("name"), person.get("headline"), person.get("stack"),
                     person.get("seniority"), badge, seen_at, entered, url))
                if entered:
                    self._event(url, "entered", seen_at)
            if post:
                self.execute(
                    """INSERT IGNORE INTO people_posts (id, profile_url, url, text, posted_at, first_seen)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (post["id"], url, post.get("url"), post.get("text"), post.get("posted_at"), now))
        return entered

    def profiles_to_check(self, limit: int, recheck_hours: float) -> list[str]:
        """Perfis de quem está procurando (no Brasil ou ainda sem local), nunca visitados
        primeiro, depois os visitados há mais tempo (e há mais de `recheck_hours`)."""
        old = dates.utc_iso(dates.now_utc() - timedelta(hours=recheck_hours))
        return [r[0] for r in self.execute(
            f"""SELECT profile_url FROM people WHERE {SEEKER_ACTIVE}
                  AND COALESCE(brazil, 1) AND (checked_at IS NULL OR checked_at < ?)
                ORDER BY checked_at IS NOT NULL, checked_at LIMIT ?""",
            (self._seeker_cut(), old, limit))]

    def record_check(self, url: str, info: dict | None) -> str | None:
        """Resultado da visita ao perfil. Retorna "left" se a pessoa tirou o selo,
        "entered" se voltou a usá-lo, None se nada mudou."""
        now = now_iso()
        with self.tx():
            row = self.execute("SELECT * FROM people WHERE profile_url = ?", (url,)).fetchone()
            if not row:
                return None
            if not info or info.get("missing"):
                self.execute("UPDATE people SET checked_at = ? WHERE profile_url = ?", (now, url))
                return None
            br = php.is_brazil(info.get("location"))
            self.execute("UPDATE people SET brazil = COALESCE(?, brazil) WHERE profile_url = ?",
                            (None if br is None else int(br), url))
            badge = bool(info.get("open_to_work"))
            change = None
            if badge and row["left_at"]:
                change = "entered"
            elif not badge and row["open_to_work"] == 1 and not row["left_at"]:
                change = "left"
            self.execute(
                """UPDATE people SET name = COALESCE(?, name), headline = COALESCE(?, headline),
                          location = COALESCE(?, location),
                          seeking_roles = COALESCE(?, seeking_roles),
                          open_to_work = ?, checked_at = ?,
                          last_seen = CASE WHEN ? THEN ? ELSE last_seen END,
                          left_at = CASE WHEN ? = 'left' THEN ? WHEN ? THEN NULL ELSE left_at END
                   WHERE profile_url = ?""",
                (info.get("name"), info.get("headline"), info.get("location"),
                 info.get("seeking_roles"), int(badge), now, badge, now,
                 change, now, badge, url))
            if change:
                self._event(url, change, now)
        return change

    def snapshot_seekers(self) -> None:
        """Grava quantas pessoas estão procurando hoje (dia de Brasília): todas (active)
        e no Brasil (brazil, a que o dashboard usa)."""
        day = datetime.now(dates.BRASILIA).date().isoformat()
        active, brazil = self.execute(
            f"SELECT count(*), COALESCE(sum(brazil = 1), 0) FROM people WHERE {SEEKER_ACTIVE}",
            (self._seeker_cut(),)).fetchone()
        with self.tx():
            self.execute("INSERT INTO people_daily (day, active, brazil) VALUES (?, ?, ?) "
                            "AS new ON DUPLICATE KEY UPDATE active = new.active, brazil = new.brazil", (day, active, brazil))

    def seekers_dashboard(self) -> dict:
        """Só quantidades (nada que identifique pessoas) e só do Brasil: procurando agora,
        entradas e saídas hoje / 7 dias / 30 dias, e séries por dia (30), semana (12) e mês
        (12). Uma entrada conta quando o perfil da pessoa confirma que ela é do Brasil."""
        cut = self._seeker_cut()
        now = datetime.now(dates.BRASILIA)
        today = now.date()
        active = self.execute(
            f"""SELECT COALESCE(sum(brazil = 1), 0) total,
                       COALESCE(sum(brazil = 1 AND open_to_work = 1), 0) badge,
                       COALESCE(sum(brazil IS NULL), 0) pending,
                       COALESCE(sum(brazil = 0), 0) abroad
                FROM people WHERE {SEEKER_ACTIVE}""", (cut,)).fetchone()
        week0 = today - timedelta(days=today.weekday() + 7 * 11)
        month0 = (today.replace(day=1) - timedelta(days=330)).replace(day=1)
        start = min(today - timedelta(days=29), week0, month0)
        since = dates.utc_iso(datetime.combine(start, datetime.min.time(), dates.BRASILIA))
        events = [(k, datetime.fromisoformat(at).astimezone(dates.BRASILIA).date())
                  for k, at in self.execute(
                      """SELECT kind, at FROM people_events e JOIN people p USING (profile_url)
                         WHERE p.brazil = 1 AND at >= ?""", (since,))]
        snapshots = dict(self.execute(
            "SELECT day, brazil FROM people_daily WHERE day >= ?", (start.isoformat(),)).fetchall())

        def periods(keys, key_of):
            rows = {k: {"period": k, "entered": 0, "left": 0, "active": None} for k in keys}
            for kind, day in events:
                if (k := key_of(day)) in rows:
                    rows[k][kind] += 1
            for day, n in sorted(snapshots.items()):  # o último dia do período vale
                if (k := key_of(datetime.fromisoformat(day).date())) in rows:
                    rows[k]["active"] = n
            return list(rows.values())

        week_of = lambda d: (d - timedelta(days=d.weekday())).isoformat()  # noqa: E731
        days = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
        weeks = [(week0 + timedelta(weeks=i)).isoformat() for i in range(12)]
        months, m = [], month0
        while m <= today:
            months.append(m.strftime("%Y-%m"))
            m = (m + timedelta(days=32)).replace(day=1)

        def count(kind, n_days):
            first = today - timedelta(days=n_days - 1)
            return sum(k == kind and d >= first for k, d in events)

        first_run = self.execute(
            "SELECT min(started_at) FROM runs WHERE source = 'seekers' AND ok = 1").fetchone()[0]
        return {
            "active_days": SEEKER_ACTIVE_DAYS,
            "kpis": {
                "active": active["total"], "badge": active["badge"],
                "pending": active["pending"], "abroad": active["abroad"],
                "entered": {"today": count("entered", 1), "week": count("entered", 7),
                            "month": count("entered", 30)},
                "left": {"today": count("left", 1), "week": count("left", 7),
                         "month": count("left", 30)},
                "tracked": self.execute("SELECT count(*) FROM people WHERE brazil = 1").fetchone()[0],
            },
            "daily": periods(days, lambda d: d.isoformat()),
            "weekly": periods(weeks, week_of),
            "monthly": periods(months, lambda d: d.strftime("%Y-%m")),
            "collecting_since": first_run,
        }

    def query_seekers(self, q: str | None = None, status: str = "active",
                      brazil: bool | None = True, limit: int = 50, offset: int = 0) -> list[dict]:
        """Pessoas (dados completos, para o MCP). status: active | left | all; brazil: True
        só Brasil, False só de fora, None todas (inclusive as ainda sem local)."""
        sql, args = "SELECT p.*, (SELECT url FROM people_posts pp WHERE pp.profile_url = p.profile_url " \
                    "ORDER BY posted_at DESC LIMIT 1) last_post_url FROM people p WHERE 1=1", []
        if status == "active":
            sql += f" AND {SEEKER_ACTIVE}"
            args.append(self._seeker_cut())
        elif status == "left":
            sql += " AND left_at IS NOT NULL"
        if brazil is not None:
            sql += " AND brazil = ?"
            args.append(int(brazil))
        if q:
            for word in q.split():
                sql += " AND (name LIKE ? OR headline LIKE ? OR location LIKE ? OR seeking_roles LIKE ?)"
                args += [f"%{word}%"] * 4
        sql += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        return [dict(r) for r in self.execute(sql, args)]
