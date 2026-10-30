"""MySQL 8 com as vagas coletadas (LinkedIn, Gupy, posts do LinkedIn, GitHub, Remotar,
Programathor, Catho, Sólides, InHire e Coodesh) e o histórico
de execuções de cada coletor. O site (web/, em PHP) usa a mesma base: lê as vagas e grava
só os cliques (tabela clicks).

A base é o contrato entre os dois lados (ver docs/contrato-base.md). O site não roda o
filtro (php.py): o que ele precisa do filtro o coletor grava pronto, em publish_site_data():
as colunas jobs.company_key e jobs.author_recruiter e a tabela site_meta (taxonomia, regras,
contagem por regra e agenda das coletas).

Conexão: DATABASE_URL=mysql://usuario:senha@host:3306/base[?ssl-mode=REQUIRED] (senha
com caracteres especiais vai codificada, ex.: @ -> %40)."""

import json
import logging
import os
import re
import ssl
import threading
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
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
    company_key VARCHAR(255),          -- php.company_key(company): agrupa a empresa; NULL = não diz quem contrata
    salary      VARCHAR(255),
    url         TEXT,
    author      VARCHAR(512),
    author_url  TEXT,
    author_headline VARCHAR(512),      -- texto abaixo do nome do autor do post (cargo)
    author_recruiter TINYINT,          -- php.is_recruiter(author_headline)
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
    # Google Indexing API (indexing.py): última tentativa de publicar cada URL de vaga.
    # A chave é VARCHAR (o MySQL não aceita TEXT como chave primária sem prefixo).
    """CREATE TABLE IF NOT EXISTS indexing_log (
    url         VARCHAR(512) COLLATE utf8mb4_bin PRIMARY KEY, -- URL absoluta da página da vaga
    pushed_at   VARCHAR(40) NOT NULL,  -- ISO UTC, como em runs
    status      VARCHAR(32) NOT NULL,  -- ok | erro | sem_permissao | quota
    detail      TEXT,                  -- mensagem do Google na falha
    INDEX indexing_log_status (status, pushed_at)
)""",
    # Dados para o site que só o coletor sabe calcular (JSON): taxonomy, rules, rule_counts,
    # schedule. Ver publish_site_data() e docs/contrato-base.md.
    """CREATE TABLE IF NOT EXISTS site_meta (
    name        VARCHAR(64) PRIMARY KEY,
    value       MEDIUMTEXT NOT NULL,   -- JSON
    updated_at  VARCHAR(40) NOT NULL   -- ISO UTC
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
                                   ("jobs", "author_headline", "VARCHAR(512) AFTER author_url"),
                                   ("jobs", "company_key", "VARCHAR(255) AFTER stack"),
                                   ("jobs", "author_recruiter", "TINYINT AFTER author_headline")):
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

    def rule_counts(self) -> dict:
        """Quantas vagas/posts da base cada regra de filtro decidiu (página /regras). Posts
        recusados na busca nem chegam à base: não entram aqui."""
        counts = Counter()
        for source, title, description, author, relevant in self.execute(
                "SELECT source, title, description, author, relevant FROM jobs "
                "WHERE dismissed IS NULL"):
            if source == "post":
                counts[php.post_verdict(description, author)] += 1
            else:  # etiquetas do GitHub não ficam na base: aceitas por elas = php_title
                verdict = php.job_verdict(title, description)
                counts["php_title" if relevant and verdict not in php.JOB_OK else verdict] += 1
        return dict(counts)

    def refresh_derived(self) -> int:
        """Recalcula jobs.company_key e jobs.author_recruiter (php.company_key e
        php.is_recruiter) onde mudaram: vagas novas e mudanças no filtro. Retorna quantas
        linhas mudaram."""
        changed = []
        for r in self.execute("SELECT id, company, company_key, author_headline, "
                              "author_recruiter FROM jobs"):
            key = php.company_key(r["company"])
            recruiter = int(php.is_recruiter(r["author_headline"]))
            if key != r["company_key"] or recruiter != r["author_recruiter"]:
                changed.append((key, recruiter, r["id"]))
        with self.tx():
            self.executemany("UPDATE jobs SET company_key = ?, author_recruiter = ? WHERE id = ?",
                             changed)
        return len(changed)

    def set_meta(self, name: str, value) -> None:
        """Grava um item de site_meta (JSON)."""
        self.execute("REPLACE INTO site_meta (name, value, updated_at) VALUES (?, ?, ?)",
                     (name, json.dumps(value, ensure_ascii=False), now_iso()))

    def publish_site_data(self) -> None:
        """Tudo o que o site precisa do filtro: colunas derivadas, taxonomia (stacks,
        modalidades, senioridades e fontes, na ordem do filtro), regras e contagem por regra."""
        self.refresh_derived()
        self.set_meta("taxonomy", {
            "stacks": list(php.PHP_STACK),
            "workplaces": [label for label, _ in php.WORKPLACE],
            "seniorities": [label for label, _ in php.SENIORITY],
            "contracts": [label for label, _ in php.CONTRACT],
            "sources": list(SOURCES),
        })
        self.set_meta("rules", php.RULES)
        self.set_meta("rule_counts", self.rule_counts())

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

    def last_ok_start(self, source: str) -> str | None:
        row = self.execute("SELECT started_at FROM runs WHERE source = ? AND ok = 1 "
                              "ORDER BY id DESC LIMIT 1", (source,)).fetchone()
        return row[0] if row else None
