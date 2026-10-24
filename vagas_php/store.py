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
    author_headline VARCHAR(512),      -- texto abaixo do nome do autor do post (cargo)
    description MEDIUMTEXT,
    posted_at   VARCHAR(40),           -- quando foi publicada (ISO; aproximada para posts)
    first_seen  VARCHAR(40) NOT NULL,
    last_seen   VARCHAR(40) NOT NULL,
    closed_at   VARCHAR(40),           -- issue fechada no GitHub
    dismissed   TEXT,                  -- descartada à mão ("não é vaga"): data e motivo
    INDEX jobs_list (relevant, posted_at),
    INDEX jobs_source (source)
)""",
    """CREATE TABLE IF NOT EXISTS runs (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    source      VARCHAR(32) NOT NULL,
    started_at  VARCHAR(40) NOT NULL,
    finished_at VARCHAR(40),
    ok          TINYINT,
    found       INT,                   -- vagas processadas (as que a coleta baixou/analisou)
    listed      INT,                   -- itens que a fonte listou, antes de tirar as já conhecidas
    failed      INT,                   -- vagas cujo detalhe falhou (tenta de novo na próxima)
    new_jobs    INT,
    error       TEXT,
    INDEX runs_source (source, id)
)""",
    # Cliques nos links para o anúncio original (/out do site). O site grava aqui mesmo
    # com a Store só leitura; quem cria a tabela é o coletor.
    """CREATE TABLE IF NOT EXISTS clicks (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    at          VARCHAR(40) NOT NULL,  -- ISO UTC, como em runs
    job_id      VARCHAR(255),          -- id da vaga ("linkedin:123"), quando houver
    url         TEXT NOT NULL,         -- destino do clique
    page        VARCHAR(255),          -- página do site de onde saiu o clique
    source      VARCHAR(32),           -- fonte da vaga, quando houver
    INDEX clicks_at (at)
)""",
]

# A mesma vaga é anunciada várias vezes (ex.: um ID do LinkedIn por cidade): vale só a
# mais recente de cada título + empresa da mesma fonte.
DEDUP = """seq IN (SELECT max(seq) FROM jobs GROUP BY source,
             lower(COALESCE(title, '')), lower(COALESCE(company, author, '')))"""

FIELDS = ("source", "relevant", "title", "company", "location", "workplace", "seniority",
          "contract", "stack", "salary", "url", "author", "author_url", "author_headline",
          "description",
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
            self._add_columns()
            self._normalize_dates()

    def _add_columns(self) -> None:
        """Colunas criadas depois da tabela: o CREATE TABLE IF NOT EXISTS não as acrescenta."""
        have = {(r[0], r[1]) for r in self.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE()")}
        for table, column, ddl in (("runs", "listed", "INT AFTER found"),
                                   ("runs", "failed", "INT AFTER listed"),
                                   ("jobs", "author_headline", "VARCHAR(512) AFTER author_url")):
            if (table, column) not in have:
                self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

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
                            author_headline = COALESCE(new.author_headline, jobs.author_headline),
                            description = CASE WHEN char_length(COALESCE(new.description, ''))
                                                    > char_length(COALESCE(jobs.description, ''))
                                               THEN new.description ELSE jobs.description END,
                            posted_at = COALESCE(jobs.posted_at, new.posted_at),
                            closed_at = new.closed_at,
                            last_seen = new.last_seen""",
                    (job["id"], *row.values(), now, now))
        return new

    def reclassify(self, source: str, classify) -> list[str]:
        """Reaplica o filtro (classify(description, author) -> bool) às vagas já salvas
        de uma fonte, para mudanças no filtro valerem também para o que já foi coletado
        (inclusive o bloqueio por autor: agregadores e o próprio site saem do site).
        Retorna os ids que mudaram."""
        rows = self.execute("SELECT id, description, author, relevant FROM jobs "
                               "WHERE source = ?", (source,)).fetchall()
        changed = []
        for r in rows:
            ok = bool(classify(r["description"], r["author"]))
            if ok != bool(r["relevant"]):
                changed.append((int(ok), r["id"]))
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
        return {"sources": by_source, "last_runs": last, "open_total": self.open_count()}

    def open_count(self) -> int:
        """Vagas abertas que o site mostra (últimas 72 h, sem as repetidas): o mesmo que
        query_jobs sem filtros e sem limite."""
        return self.execute(
            f"""SELECT count(*) FROM jobs WHERE relevant = 1 AND dismissed IS NULL
                  AND closed_at IS NULL AND COALESCE(posted_at, first_seen) >= ? AND {DEDUP}""",
            (dates.cutoff(),)).fetchone()[0]

    def job_facets(self, days: int = 90) -> list[dict]:
        """Fonte, empresa, modalidade, senioridade, contratação e stack das vagas aceitas
        dos últimos `days` dias, sem as repetidas e incluindo as já encerradas: números
        das páginas por tema (/vagas/laravel...)."""
        since = dates.utc_iso(dates.now_utc() - timedelta(days=days))
        return [dict(r) for r in self.execute(
            f"""SELECT source, company, workplace, seniority, contract, stack,
                       COALESCE(posted_at, first_seen) AS posted
                FROM jobs WHERE relevant = 1 AND dismissed IS NULL AND {DEDUP}
                  AND COALESCE(posted_at, first_seen) >= ?""", (since,))]

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
        for source in SOURCES:
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
        for source, title, description, author, relevant in self.execute(
                "SELECT source, title, description, author, relevant FROM jobs "
                "WHERE dismissed IS NULL"):
            if source == "post":
                counts[php.post_verdict(description, author)] += 1
            else:  # etiquetas do GitHub não ficam na base: aceitas por elas = php_title
                verdict = php.job_verdict(title, description)
                counts["php_title" if relevant and verdict not in php.JOB_OK else verdict] += 1
        dismissed = [dict(r) for r in self.execute(
            "SELECT source, title, url, dismissed FROM jobs WHERE dismissed IS NOT NULL "
            "ORDER BY dismissed DESC")]
        return {"counts": dict(counts), "dismissed": dismissed}

    def recruiters(self, days: int = 90, min_jobs: int = 2, hidden=()) -> list[dict]:
        """Tech recruiters (php.is_recruiter no headline) que publicaram vagas PHP aceitas
        nos últimos `days` dias (página /recrutadores), com `min_jobs` ou mais vagas. Os
        perfis de `hidden` (pediram para sair) ficam de fora."""
        profile = lambda url: url.split("?")[0].rstrip("/").lower()  # noqa: E731
        hidden = {profile(u) for u in hidden if u}
        since = dates.utc_iso(dates.now_utc() - timedelta(days=days))
        people: dict[str, dict] = {}
        for r in self.execute(
                f"""SELECT author, author_url, author_headline, stack,
                           COALESCE(posted_at, first_seen) AS posted
                    FROM jobs WHERE source = 'post' AND relevant = 1 AND dismissed IS NULL
                      AND author_url IS NOT NULL AND {DEDUP}
                      AND COALESCE(posted_at, first_seen) >= ?
                    ORDER BY posted DESC""", (since,)):
            key = profile(r["author_url"])
            if key in hidden:
                continue
            p = people.setdefault(key, {"name": r["author"], "url": r["author_url"].split("?")[0],
                                        "headline": r["author_headline"], "jobs": 0,
                                        "last_posted": r["posted"], "stack": Counter()})
            p["headline"] = p["headline"] or r["author_headline"]  # o mais recente que houver
            p["jobs"] += 1
            p["stack"].update(s for s in (r["stack"] or "").split(",") if s and s != "PHP")
        out = [{**p, "stack": [s for s, _ in p["stack"].most_common(4)]} for p in people.values()
               if p["jobs"] >= min_jobs and php.is_recruiter(p["headline"])]
        return sorted(out, key=lambda p: (p["jobs"], p["last_posted"]), reverse=True)

    def companies(self, days: int = 90, min_jobs: int = 2) -> list[dict]:
        """Empresas que mais anunciaram vagas PHP aceitas nos últimos `days` dias (página
        /empresas), com `min_jobs` ou mais vagas. Agrupa por php.company_key, que também
        tira as que não dizem quem contrata."""
        since = dates.utc_iso(dates.now_utc() - timedelta(days=days))
        companies: dict[str, dict] = {}
        for r in self.execute(
                f"""SELECT source, company, workplace, stack,
                           COALESCE(posted_at, first_seen) AS posted
                    FROM jobs WHERE relevant = 1 AND dismissed IS NULL AND company IS NOT NULL
                      AND {DEDUP} AND COALESCE(posted_at, first_seen) >= ?
                    ORDER BY posted DESC""", (since,)):
            if not (key := php.company_key(r["company"])):
                continue
            c = companies.setdefault(key, {"names": Counter(), "jobs": 0, "last_posted": r["posted"],
                                           "sources": Counter(), "workplace": Counter(),
                                           "stack": Counter()})
            c["names"][r["company"].strip()] += 1
            c["jobs"] += 1
            c["sources"][r["source"]] += 1
            c["workplace"][r["workplace"] or "Não informado"] += 1
            c["stack"].update(s for s in (r["stack"] or "").split(",") if s and s != "PHP")
        out = [{"name": c["names"].most_common(1)[0][0], "jobs": c["jobs"],
                "last_posted": c["last_posted"], "sources": [s for s, _ in c["sources"].most_common()],
                "workplace": c["workplace"].most_common(),
                "stack": [s for s, _ in c["stack"].most_common(4)]}
               for c in companies.values() if c["jobs"] >= min_jobs]
        return sorted(out, key=lambda c: (c["jobs"], c["last_posted"]), reverse=True)

    def start_run(self, source: str) -> int:
        with self.tx():
            return self.execute("INSERT INTO runs (source, started_at) VALUES (?, ?)",
                                   (source, now_iso())).lastrowid

    def finish_run(self, run_id: int, found: int = 0, new_jobs: int = 0,
                   error: str | None = None, listed: int | None = None,
                   failed: int | None = None) -> None:
        with self.tx():
            self.execute(
                "UPDATE runs SET finished_at = ?, ok = ?, found = ?, listed = ?, failed = ?, "
                "new_jobs = ?, error = ? WHERE id = ?",
                (now_iso(), error is None, found, listed, failed, new_jobs, error, run_id))

    def last_runs(self, source: str | None = None, n: int = 5) -> list[dict]:
        if source:
            rows = self.execute("SELECT * FROM runs WHERE source = ? ORDER BY id DESC LIMIT ?",
                                   (source, n))
        else:
            rows = self.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (n,))
        return [dict(r) for r in rows]

    def log_click(self, job_id: str | None, url: str, page: str | None,
                  source: str | None) -> None:
        """Grava um clique para o anúncio original. Falha na base (tabela ainda não
        criada pelo coletor, MySQL fora) só vira aviso: o redirecionamento continua."""
        try:
            self.execute("INSERT INTO clicks (at, job_id, url, page, source) VALUES (?, ?, ?, ?, ?)",
                         (now_iso(), (job_id or None) and job_id[:255], url,
                          (page or None) and page[:255], (source or None) and source[:32]))
        except pymysql.MySQLError as e:
            log.warning("clique não gravado (%s): %s", e, url)

    def click_stats(self, days: int = 7) -> dict:
        """Cliques dos últimos `days` dias: total, por vaga, por fonte e por dia (UTC)."""
        since = dates.utc_iso(dates.now_utc() - timedelta(days=days))
        total = self.execute("SELECT count(*) FROM clicks WHERE at >= ?", (since,)).fetchone()[0]
        by_job = self.execute(
            "SELECT job_id, url, count(*) n FROM clicks WHERE at >= ? "
            "GROUP BY job_id, url ORDER BY n DESC", (since,))
        by_source = self.execute(
            "SELECT source, count(*) n FROM clicks WHERE at >= ? GROUP BY source ORDER BY n DESC",
            (since,))
        by_day = self.execute(
            "SELECT left(at, 10) day, count(*) FROM clicks WHERE at >= ? GROUP BY day ORDER BY day",
            (since,))
        return {"total": total, "by_job": [list(r) for r in by_job],
                "by_source": [list(r) for r in by_source], "by_day": [list(r) for r in by_day]}

    def last_ok_start(self, source: str) -> str | None:
        row = self.execute("SELECT started_at FROM runs WHERE source = ? AND ok = 1 "
                              "ORDER BY id DESC LIMIT 1", (source,)).fetchone()
        return row[0] if row else None
