"""MySQL 8 com as vagas coletadas (LinkedIn, Gupy, posts do LinkedIn, GitHub, Remotar,
Programathor, Catho, Sólides, InHire e Coodesh) e o histórico
de execuções de cada coletor. O site (web/, em PHP) usa a mesma base: lê as vagas e grava
só os cliques (tabela clicks).

A base é o contrato entre os dois lados (ver docs/contrato-base.md). O site não roda o
filtro (classify.py): o que ele precisa do filtro o coletor grava pronto, em
publish_site_data(): as colunas jobs.company_key e jobs.author_recruiter e a tabela
site_meta (taxonomia, regras, contagem por regra e agenda das coletas).

A configuração dos coletores (linguagem, termos de busca, dono do site) fica na tabela
collector_config (ver config.py): quem abre a base passa a usá-la.

Multi-tenant: uma base para todas as linguagens. jobs, runs, site_meta e collector_config
têm a coluna tenant ("php", "ruby"...), e cada Store lê e grava só o seu tenant
(VAGAS_TENANT, padrão "php"). A mesma vaga pode estar em dois tenants (chave
(tenant, id)): uma vaga full stack pode ser PHP e Ruby. Linhas de antes do multi-tenant
são do tenant "php".

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

from . import classify, config, dates

log = logging.getLogger(__name__)

SOURCES = ("linkedin", "gupy", "post", "github", "remotar", "programathor", "catho", "solides",
           "inhire", "coodesh", "nerdin", "recrutei", "upvagas")
# Datas ficam como texto ISO UTC ("2026-10-15T12:00:00+00:00"), comparadas como string.
# Chaves em utf8mb4_bin: ids e URLs diferem por maiúscula/acento; o resto usa a collation
# padrão (sem diferenciar maiúsculas nem acentos nas buscas com LIKE).
SCHEMA = [
    """CREATE TABLE IF NOT EXISTS jobs (
    tenant      VARCHAR(32) NOT NULL DEFAULT 'php',            -- linguagem: "php", "ruby"...
    id          VARCHAR(255) COLLATE utf8mb4_bin NOT NULL,     -- "linkedin:<id>", "gupy:<id>", "post:<urn ou hash>", "github:<repo>#<n>", "inhire:<uuid>", "<fonte>:<id>" nas demais
    seq         BIGINT NOT NULL AUTO_INCREMENT UNIQUE,         -- ordem de inserção (DEDUP); única entre os tenants
    source      VARCHAR(32) NOT NULL,  -- ver SOURCES
    relevant    TINYINT NOT NULL,      -- 1 = vaga de engenharia de software da linguagem configurada
    title       TEXT,
    company     VARCHAR(512),
    location    VARCHAR(512),
    workplace   VARCHAR(32),           -- Remoto | Híbrido | Presencial
    seniority   VARCHAR(32),           -- Estágio | Júnior | Pleno | Sênior | Especialista
    contract    VARCHAR(32),           -- CLT | PJ | Freelance
    stack       VARCHAR(512),          -- "PHP,Laravel"
    company_key VARCHAR(255),          -- classify.company_key(company): agrupa a empresa; NULL = não diz quem contrata
    salary      VARCHAR(255),
    url         TEXT,
    author      VARCHAR(512),
    author_url  TEXT,
    author_headline VARCHAR(512),      -- texto abaixo do nome do autor do post (cargo)
    author_recruiter TINYINT,          -- classify.is_recruiter(author_headline)
    description MEDIUMTEXT,
    posted_at   VARCHAR(40),           -- quando foi publicada (ISO; aproximada para posts)
    first_seen  VARCHAR(40) NOT NULL,
    last_seen   VARCHAR(40) NOT NULL,
    closed_at   VARCHAR(40),           -- issue fechada no GitHub
    dismissed   TEXT,                  -- descartada à mão ("não é vaga"): data e motivo
    PRIMARY KEY (tenant, id),
    INDEX jobs_list (relevant, posted_at),
    INDEX jobs_source (source)
)""",
    """CREATE TABLE IF NOT EXISTS runs (
    tenant      VARCHAR(32) NOT NULL DEFAULT 'php',
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
    tenant      VARCHAR(32) NOT NULL DEFAULT 'php',
    name        VARCHAR(64) NOT NULL,
    value       MEDIUMTEXT NOT NULL,   -- JSON
    updated_at  VARCHAR(40) NOT NULL,  -- ISO UTC
    PRIMARY KEY (tenant, name)
)""",
    # Configuração dos coletores (JSON): language, core, stack, search, self_author. Ver
    # config.py; os valores iniciais vêm de config_defaults.json.
    """CREATE TABLE IF NOT EXISTS collector_config (
    tenant      VARCHAR(32) NOT NULL DEFAULT 'php',
    name        VARCHAR(64) NOT NULL,
    value       MEDIUMTEXT NOT NULL,   -- JSON
    updated_at  VARCHAR(40) NOT NULL,  -- ISO UTC
    PRIMARY KEY (tenant, name)
)""",
]
# Tabelas por tenant e a chave primária de cada uma (bases de antes do multi-tenant são
# migradas em _add_tenant).
TENANT_TABLES = {"jobs": "(tenant, id)", "runs": None, "site_meta": "(tenant, name)",
                 "collector_config": "(tenant, name)"}

# A mesma vaga é anunciada várias vezes (ex.: um ID do LinkedIn por cidade): vale só a
# mais recente de cada título + empresa da mesma fonte, dentro do tenant (a consulta que
# usa DEDUP filtra o tenant; agrupar por ele impede que a linha de outro tenant esconda
# a deste).
DEDUP = """seq IN (SELECT max(seq) FROM jobs GROUP BY tenant, source,
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

    def __init__(self, url: str | None = None, readonly: bool = False, wait: float = 120,
                 tenant: str | None = None):
        self.args = connect_args(url)
        self.tenant = (tenant or config.default_tenant()).strip().lower()
        # Coletores rodam em threads diferentes: uma conexão por thread; a trava
        # serializa as escritas.
        self.local = threading.local()
        self.lock = threading.RLock()
        self._wait_for_db(wait)
        if not readonly:
            for statement in SCHEMA:
                self.execute(statement)
            self._add_columns()
            self._add_tenant()
            self._normalize_dates()
            self._seed_config()
        self.load_config()

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

    def _add_tenant(self) -> None:
        """Bases de antes do multi-tenant: acrescenta a coluna tenant (o que já existe fica
        no tenant "php") e põe o tenant na chave primária."""
        have = {(r[0], r[1]) for r in self.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE()")}
        for table, key in TENANT_TABLES.items():
            if (table, "tenant") not in have:
                self.execute(f"ALTER TABLE {table} ADD COLUMN tenant VARCHAR(32) NOT NULL "
                             "DEFAULT 'php' FIRST")
            if key and self._primary_key(table)[:1] != ["tenant"]:
                self.execute(f"ALTER TABLE {table} DROP PRIMARY KEY, ADD PRIMARY KEY {key}")

    def _primary_key(self, table: str) -> list[str]:
        return [r[0] for r in self.execute(
            "SELECT column_name FROM information_schema.key_column_usage WHERE table_schema = "
            "DATABASE() AND table_name = ? AND constraint_name = 'PRIMARY' "
            "ORDER BY ordinal_position", (table,))]

    def _seed_config(self) -> None:
        """Grava os valores iniciais da configuração do tenant (config_defaults.json) que
        ainda não estão na base; o que já está nela (inclusive editado à mão) fica."""
        now = now_iso()
        self.executemany("INSERT IGNORE INTO collector_config (tenant, name, value, updated_at) "
                         "VALUES (?, ?, ?, ?)",
                         [(self.tenant, name, json.dumps(value, ensure_ascii=False), now)
                          for name, value in config.defaults(self.tenant).items()])

    def get_config(self) -> dict:
        """A configuração do tenant gravada na base ({} se a tabela ainda não existe)."""
        try:
            rows = self.execute("SELECT name, value FROM collector_config WHERE tenant = ?",
                                (self.tenant,)).fetchall()
        except pymysql.err.ProgrammingError as e:
            if e.args[0] == 1146:  # tabela não existe (base aberta só para leitura)
                return {}
            raise
        return {r["name"]: json.loads(r["value"]) for r in rows}

    def load_config(self) -> None:
        """Passa a usar a configuração da base (filtro, termos de busca...)."""
        config.load(self.get_config(), self.tenant)

    def set_config(self, name: str, value) -> None:
        """Grava um item da configuração (JSON) e passa a usá-lo."""
        if name not in config.ITEMS:
            raise ValueError(f"configuração desconhecida: {name} (opções: "
                             f"{', '.join(config.ITEMS)})")
        current = self.get_config()
        try:  # valida antes de gravar (ex.: regex inválida): a base nunca fica quebrada
            config.load({**current, name: value}, self.tenant)
        except Exception as e:
            try:
                config.load(current, self.tenant)
            except ValueError:
                pass  # tenant ainda incompleto: segue sem configuração carregada
            raise ValueError(f"{name} inválido: {e}") from e
        self.execute("REPLACE INTO collector_config (tenant, name, value, updated_at) "
                     "VALUES (?, ?, ?, ?)",
                     (self.tenant, name, json.dumps(value, ensure_ascii=False), now_iso()))

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
        rows = self.execute("SELECT tenant, id, posted_at FROM jobs WHERE posted_at IS NOT NULL "
                            "AND posted_at NOT LIKE ?", ("%+00:00",)).fetchall()
        with self.tx():
            for tenant, job_id, posted in rows:
                self.execute("UPDATE jobs SET posted_at = ? WHERE tenant = ? AND id = ?",
                             (dates.normalize(posted), tenant, job_id))

    def known(self, source: str) -> dict[str, dict]:
        """id -> {description, relevant} das vagas já vistas de uma fonte."""
        return {r["id"]: dict(r) for r in self.execute(
            "SELECT id, description, relevant FROM jobs WHERE tenant = ? AND source = ?",
            (self.tenant, source))}

    def texts_mentioning(self, needle: str) -> list[str]:
        """Descrições e URLs de vagas que citam `needle` (ex.: "inhire.app", para
        descobrir empresas). Em todos os tenants: o que um coletor descobre vale para os
        outros."""
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
                exists = self.execute("SELECT 1 FROM jobs WHERE tenant = ? AND id = ?",
                                      (self.tenant, job["id"])).fetchone()
                new += bool(not exists and row["relevant"])
                self.execute(
                    f"""INSERT INTO jobs (tenant, id, {", ".join(FIELDS)}, first_seen, last_seen)
                        VALUES (?, ?, {", ".join("?" * len(FIELDS))}, ?, ?) AS new
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
                    (self.tenant, job["id"], *row.values(), now, now))
        return new

    def reclassify(self, source: str, classify) -> list[str]:
        """Reaplica o filtro (classify(description, author) -> bool) às vagas já salvas
        de uma fonte, para mudanças no filtro valerem também para o que já foi coletado
        (inclusive o bloqueio por autor: agregadores e o próprio site saem do site).
        Retorna os ids que mudaram."""
        rows = self.execute("SELECT id, description, author, relevant FROM jobs "
                            "WHERE tenant = ? AND source = ?", (self.tenant, source)).fetchall()
        changed = []
        for r in rows:
            ok = bool(classify(r["description"], r["author"]))
            if ok != bool(r["relevant"]):
                changed.append((int(ok), r["id"]))
        with self.tx():
            self.executemany("UPDATE jobs SET relevant = ? WHERE tenant = ? AND id = ?",
                             [(ok, self.tenant, job_id) for ok, job_id in changed])
        return [job_id for _, job_id in changed]

    def reclassify_jobs(self) -> list[str]:
        """Reaplica classify.is_relevant_job às vagas de portais já salvas (todas as fontes menos
        "post"), para mudanças na regra valerem também para o que já foi coletado. As
        etiquetas das issues do GitHub não ficam na base: issue aceita por etiqueta
        continua aceita. Retorna os ids que mudaram."""
        rows = self.execute("SELECT id, source, title, description, relevant FROM jobs "
                            "WHERE tenant = ? AND source != 'post'", (self.tenant,)).fetchall()
        changed = []
        for r in rows:
            ok = classify.is_relevant_job(r["title"], r["description"]) or (
                r["source"] == "github" and r["relevant"])
            if ok != bool(r["relevant"]):
                changed.append((int(ok), r["id"]))
        with self.tx():
            self.executemany("UPDATE jobs SET relevant = ? WHERE tenant = ? AND id = ?",
                             [(ok, self.tenant, job_id) for ok, job_id in changed])
        return [job_id for _, job_id in changed]

    def dismiss(self, ref: str, reason: str | None = None, undo: bool = False) -> list[dict]:
        """Marca como "não é vaga" (ou desfaz) pelo id, pela URL ou pelo número do
        post/vaga contido nela. Fica na base: novas coletas não trazem de volta."""
        ref = ref.strip()
        digits = re.findall(r"\d{12,}", ref)
        sql = "SELECT id, title, url FROM jobs WHERE tenant = ? AND (id = ? OR url = ?"
        args = [self.tenant, ref, ref]
        if digits:
            sql += " OR id LIKE ?"
            args.append(f"%{digits[-1]}%")
        sql += ")"
        rows = [dict(r) for r in self.execute(sql, args)]
        mark = None if undo else f"{now_iso()} {reason or ''}".strip()
        with self.tx():
            self.executemany("UPDATE jobs SET dismissed = ? WHERE tenant = ? AND id = ?",
                             [(mark, self.tenant, r["id"]) for r in rows])
        return rows

    def query_jobs(self, q: str | None = None, source: str | None = None,
                   workplace: str | None = None, seniority: str | None = None,
                   stack: str | None = None, hours: float | None = None,
                   include_closed: bool = False, include_irrelevant: bool = False,
                   limit: int = 50, offset: int = 0) -> list[dict]:
        sql, args = "SELECT * FROM jobs WHERE tenant = ?", [self.tenant]
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
               FROM jobs WHERE tenant = ? GROUP BY source""", (dates.cutoff(), self.tenant))}
        last = {}
        for source in SOURCES:
            run = self.execute("SELECT * FROM runs WHERE tenant = ? AND source = ? "
                               "ORDER BY id DESC LIMIT 1", (self.tenant, source)).fetchone()
            last[source] = dict(run) if run else None
        return {"sources": by_source, "last_runs": last, "open_total": self.open_count()}

    def open_count(self) -> int:
        """Vagas abertas que o site mostra (últimas 72 h, sem as repetidas): o mesmo que
        query_jobs sem filtros e sem limite."""
        return self.execute(
            f"""SELECT count(*) FROM jobs WHERE tenant = ? AND relevant = 1 AND dismissed IS NULL
                  AND closed_at IS NULL AND COALESCE(posted_at, first_seen) >= ? AND {DEDUP}""",
            (self.tenant, dates.cutoff())).fetchone()[0]

    def rule_counts(self) -> dict:
        """Quantas vagas/posts da base cada regra de filtro decidiu (página /regras). Posts
        recusados na busca nem chegam à base: não entram aqui."""
        counts = Counter()
        for source, title, description, author, relevant in self.execute(
                "SELECT source, title, description, author, relevant FROM jobs "
                "WHERE tenant = ? AND dismissed IS NULL", (self.tenant,)):
            if source == "post":
                counts[classify.post_verdict(description, author)] += 1
            else:  # etiquetas do GitHub não ficam na base: aceitas por elas = lang_title
                verdict = classify.job_verdict(title, description)
                counts["lang_title" if relevant and verdict not in classify.JOB_OK
                       else verdict] += 1
        return dict(counts)

    def refresh_derived(self) -> int:
        """Recalcula jobs.company_key e jobs.author_recruiter (classify.company_key
        e classify.is_recruiter) onde mudaram: vagas novas e mudanças no filtro. Retorna quantas
        linhas mudaram."""
        changed = []
        for r in self.execute("SELECT id, company, company_key, author_headline, "
                              "author_recruiter FROM jobs WHERE tenant = ?", (self.tenant,)):
            key = classify.company_key(r["company"])
            recruiter = int(classify.is_recruiter(r["author_headline"]))
            if key != r["company_key"] or recruiter != r["author_recruiter"]:
                changed.append((key, recruiter, r["id"]))
        with self.tx():
            self.executemany("UPDATE jobs SET company_key = ?, author_recruiter = ? "
                             "WHERE tenant = ? AND id = ?",
                             [(key, rec, self.tenant, job_id) for key, rec, job_id in changed])
        return len(changed)

    def set_meta(self, name: str, value) -> None:
        """Grava um item de site_meta (JSON) do tenant."""
        self.execute("REPLACE INTO site_meta (tenant, name, value, updated_at) VALUES (?, ?, ?, ?)",
                     (self.tenant, name, json.dumps(value, ensure_ascii=False), now_iso()))

    def publish_site_data(self) -> None:
        """Tudo o que o site precisa do filtro: colunas derivadas, taxonomia (stacks,
        modalidades, senioridades e fontes, na ordem do filtro), regras e contagem por regra."""
        self.refresh_derived()
        self.set_meta("taxonomy", {
            "stacks": list(classify.STACK),
            "workplaces": [label for label, _ in classify.WORKPLACE],
            "seniorities": [label for label, _ in classify.SENIORITY],
            "contracts": [label for label, _ in classify.CONTRACT],
            "sources": list(SOURCES),
        })
        self.set_meta("rules", classify.RULES)
        self.set_meta("rule_counts", self.rule_counts())

    def start_run(self, source: str) -> int:
        with self.tx():
            return self.execute("INSERT INTO runs (tenant, source, started_at) VALUES (?, ?, ?)",
                                (self.tenant, source, now_iso())).lastrowid

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
            rows = self.execute("SELECT * FROM runs WHERE tenant = ? AND source = ? "
                                "ORDER BY id DESC LIMIT ?", (self.tenant, source, n))
        else:
            rows = self.execute("SELECT * FROM runs WHERE tenant = ? ORDER BY id DESC LIMIT ?",
                                (self.tenant, n))
        return [dict(r) for r in rows]

    def last_ok_start(self, source: str) -> str | None:
        row = self.execute("SELECT started_at FROM runs WHERE tenant = ? AND source = ? "
                           "AND ok = 1 ORDER BY id DESC LIMIT 1", (self.tenant, source)).fetchone()
        return row[0] if row else None
