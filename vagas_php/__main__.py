"""Uso:
  python -m vagas_php collect <fonte>|all [--show]   # coleta agora e grava em data/ (fontes: store.SOURCES)
  python -m vagas_php list [--q laravel] [--source github] [--hours 24] [--limit 20]
  python -m vagas_php migrate-sqlite data/vagas.db       # copia a base SQLite antiga para o MySQL
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import collect, migrate_sqlite
from .bot import LoginError
from .store import SOURCES, Store

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Vagas de engenharia de software com PHP.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect", help="coleta vagas agora")
    c.add_argument("source", choices=[*SOURCES, "all"])
    c.add_argument("--show", action="store_true",
                   help="navegador visível (necessário para 2FA/captcha na fonte post)")
    ls = sub.add_parser("list", help="lista as vagas já coletadas")
    ls.add_argument("--q")
    ls.add_argument("--source", choices=SOURCES)
    ls.add_argument("--hours", type=float, default=72, help="publicadas nas últimas N horas (máx. 72)")
    ls.add_argument("--limit", type=int, default=20)
    m = sub.add_parser("migrate-sqlite", help="copia a base SQLite antiga para o MySQL")
    m.add_argument("path", type=Path, help="ex.: data/vagas.db")
    m.add_argument("--force", action="store_true", help="apaga o que já houver no MySQL antes")
    args = parser.parse_args()

    store = Store()
    if args.cmd == "migrate-sqlite":
        return migrate_sqlite.run(store, args.path, force=args.force)
    if args.cmd == "list":
        return list_jobs(store, args)
    sources = SOURCES if args.source == "all" else (args.source,)
    status = 0
    for source in sources:
        try:
            result = collect.run(store, source, headless=not args.show)
            print(f"{source}: {result}")
        except (LoginError, RuntimeError, ValueError) as e:
            print(f"{source}: erro: {e}", file=sys.stderr)
            status = 1
    return status


def list_jobs(store: Store, args) -> int:
    jobs = store.query_jobs(q=args.q, source=args.source, hours=args.hours, limit=args.limit)
    for i, j in enumerate(jobs, 1):
        tags = " · ".join(t for t in (j["workplace"], j["seniority"], j["contract"], j["stack"]) if t)
        who = " · ".join(t for t in (j["company"] or j["author"], j["location"]) if t)
        print(f"\n#{i} [{j['source']}] {j['title']}\n   {who}"
              + (f"\n   {tags}" if tags else "") + f"\n   {(j['posted_at'] or '')[:10]}  {j['url']}")
    if not jobs:
        print("Nenhuma vaga encontrada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
