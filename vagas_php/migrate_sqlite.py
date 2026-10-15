"""Copia a base SQLite antiga (data/vagas.db) para o MySQL, preservando ids e a ordem de
inserção das vagas (rowid -> seq, usada para escolher a mais recente entre repetidas)."""

import sqlite3
from pathlib import Path

from .store import Store

# Ordem das tabelas e colunas como no SQLite; jobs ganha seq a partir do rowid.
TABLES = {
    "jobs": ("seq", "id", "source", "relevant", "title", "company", "location", "workplace",
             "seniority", "contract", "stack", "salary", "url", "author", "author_url",
             "description", "posted_at", "first_seen", "last_seen", "closed_at", "dismissed"),
    "people": ("profile_url", "name", "headline", "location", "brazil", "seeking_roles", "stack",
               "seniority", "open_to_work", "first_seen", "last_seen", "checked_at", "left_at"),
    "people_posts": ("id", "profile_url", "url", "text", "posted_at", "first_seen"),
    "people_events": ("id", "profile_url", "kind", "at"),
    "people_daily": ("day", "active", "brazil"),
    "runs": ("id", "source", "started_at", "finished_at", "ok", "found", "new_jobs", "error"),
}
BATCH = 500


def run(store: Store, path: Path, force: bool = False) -> int:
    if not path.exists():
        print(f"{path}: arquivo não encontrado")
        return 1
    src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    busy = [t for t in TABLES if store.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone()]
    if busy and not force:
        print(f"O MySQL já tem dados em {', '.join(busy)}. Use --force para apagar e copiar de novo.")
        return 1
    with store.tx():
        for table in TABLES:
            store.execute(f"DELETE FROM {table}")
        for table, columns in TABLES.items():
            select = ", ".join("rowid" if c == "seq" else c for c in columns)
            insert = (f"INSERT INTO {table} ({', '.join(columns)}) "
                      f"VALUES ({', '.join('?' * len(columns))})")
            rows = src.execute(f"SELECT {select} FROM {table} ORDER BY rowid")
            total = 0
            while batch := rows.fetchmany(BATCH):
                store.executemany(insert, batch)
                total += len(batch)
            print(f"{table}: {total}")
    src.close()
    return 0
