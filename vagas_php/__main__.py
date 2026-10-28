"""Uso:
  python -m vagas_php collect <fonte>|all [--show]   # coleta agora e grava em data/ (fontes: store.SOURCES)
  python -m vagas_php list [--q laravel] [--source github] [--hours 24] [--limit 20]
  python -m vagas_php migrate-sqlite data/vagas.db       # copia a base SQLite antiga para o MySQL
  python -m vagas_php post [--dry-run] [--show]           # post diário no LinkedIn (print de VAGAS_DASHBOARD_URL)
  python -m vagas_php post --probe [--show]               # diagnóstico da caixa de publicação (não publica)
  python -m vagas_php telegram-alert [--dry-run] [--limit 5] [--force] [--batch]  # vagas novas da API pública no Telegram
  python -m vagas_php telegram-digest [--dry-run]         # resumo semanal no Telegram (mesmo post do LinkedIn)
  python -m vagas_php indexing-push [--limit 50] [--dry-run] [--force]  # vagas abertas na Google Indexing API
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from . import collect, migrate_sqlite
from .bot import LoginError
from .store import SOURCES, Store

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def history_readable(path: Path) -> bool:
    """True se o histórico de posts não existe (primeiro post) ou é uma lista JSON."""
    if not path.exists():
        return True
    try:
        ok = isinstance(json.loads(path.read_text()), list)
    except (OSError, ValueError):
        ok = False
    if not ok:
        print(f"Histórico de posts ilegível em {path}; corrija ou remova o arquivo "
              "antes de publicar. Nada publicado.", file=sys.stderr)
    return ok


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
    p = sub.add_parser("post", help="publica agora o post diário no LinkedIn")
    p.add_argument("--dry-run", action="store_true",
                   help="monta o post e descarta o rascunho, sem publicar")
    p.add_argument("--show", action="store_true", help="navegador visível (para 2FA/captcha)")
    p.add_argument("--probe", action="store_true",
                   help="diagnóstico: abre a caixa de publicação, grava o HTML e lista os "
                        "editores encontrados (nunca publica; ignora --dry-run)")
    t = sub.add_parser("telegram-alert", help="envia ao Telegram as vagas novas da API pública")
    t.add_argument("--dry-run", action="store_true",
                   help="imprime as mensagens sem enviar e sem gravar o estado")
    t.add_argument("--limit", type=int, default=5, help="máximo de vagas por execução")
    t.add_argument("--force", action="store_true",
                   help="ignora a janela de VAGAS_TELEGRAM_ACTIVE_HOURS (uso manual/teste)")
    t.add_argument("--batch", action="store_true",
                   help="agrupa todas as vagas pendentes numa mensagem só (ignora --limit)")
    d =sub.add_parser("telegram-digest",
                       help="envia ao Telegram o resumo semanal (print do dashboard + texto do "
                            "post do LinkedIn); uma vez por semana")
    d.add_argument("--dry-run", action="store_true",
                   help="gera a imagem e imprime o texto sem enviar e sem gravar o estado")
    ix = sub.add_parser("indexing-push",
                        help="publica na Google Indexing API as vagas abertas ainda não "
                             "anunciadas (mesmas URLs do sitemap)")
    ix.add_argument("--limit", type=int, default=50, help="máximo de URLs por execução")
    ix.add_argument("--dry-run", action="store_true",
                    help="lista as URLs que seriam publicadas, sem chamar a API e sem gravar")
    ix.add_argument("--force", action="store_true",
                    help="publica de novo as já enviadas com sucesso nas últimas 24 h")
    args = parser.parse_args()

    if args.cmd == "telegram-digest":
        # Importado aqui: o módulo lê VAGAS_TELEGRAM_* no import, depois do .env.
        from . import telegram_alert
        try:
            print(telegram_alert.send_weekly(DATA_DIR, dry_run=args.dry_run))
        except RuntimeError as e:
            print(f"telegram-digest: erro: {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "telegram-alert":
        # Importado aqui: o módulo lê VAGAS_API_URL e VAGAS_TELEGRAM_* no import, depois do .env.
        from . import telegram_alert
        try:
            print(telegram_alert.run(DATA_DIR, limit=args.limit, dry_run=args.dry_run,
                                     force=args.force, batch=args.batch))
        except RuntimeError as e:
            print(f"telegram-alert: erro: {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "post" and args.probe:
        return probe_composer(headless=not args.show)
    if args.cmd == "post":
        # Importado aqui: o módulo lê VAGAS_DASHBOARD_URL no import, depois do .env.
        from . import dates, linkedin_post
        # Mesma referência de dia que linkedin_post.run (horário de Brasília).
        today = dates.now_utc().astimezone(dates.BRASILIA).date().isoformat()
        # history_load devolve [] se o arquivo estiver ilegível: publicaria de novo e
        # linkedin_post.run sobrescreveria o histórico só com a entrada de hoje.
        if not args.dry_run and not history_readable(DATA_DIR / "linkedin_posts.json"):
            return 1
        if not args.dry_run and linkedin_post.posted_on(DATA_DIR, today):
            print(f"Post de hoje ({today}) já publicado; nada a fazer.")
            return 0
        entry =linkedin_post.run(DATA_DIR, headless=not args.show, dry_run=args.dry_run)
        print(entry)
        return 0

    store = Store()
    if args.cmd == "migrate-sqlite":
        return migrate_sqlite.run(store, args.path, force=args.force)
    if args.cmd == "list":
        return list_jobs(store, args)
    if args.cmd == "indexing-push":
        from . import indexing
        result = indexing.publish(indexing.open_urls(store), limit=args.limit,
                                  dry_run=args.dry_run, force=args.force, store=store)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
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


# Percorre o documento e todos os shadow roots abertos (recursivamente) e descreve os
# elementos que podem ser o editor da caixa de publicação.
PROBE_JS = """() => {
  const groups = {contenteditable: '[contenteditable]', textbox: '[role=textbox]',
                  dialog: '[role=dialog]', 'ql-editor': '[class*="ql-editor"]'};
  const out = Object.fromEntries(Object.keys(groups).map(k => [k, []]));
  const shadows = [], iframes = [];
  const path = el => {
    const parts = [];
    for (let n = el; n; ) {
      if (n.nodeType === 1) parts.unshift(n.tagName.toLowerCase() + (n.id ? '#' + n.id : ''));
      if (n.parentNode) n = n.parentNode;
      else if (n.host) { parts.unshift('::shadow'); n = n.host; }
      else break;
      if (parts.length > 8) break;
    }
    return parts.slice(-6).join(' > ');
  };
  const describe = (el, inShadow) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return {tag: el.tagName.toLowerCase(), id: el.id || '', class: (el.getAttribute('class') || '').slice(0, 120),
            role: el.getAttribute('role') || '', aria_label: el.getAttribute('aria-label') || '',
            data_placeholder: el.getAttribute('data-placeholder') || '',
            contenteditable: el.getAttribute('contenteditable'),
            visible: r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none',
            in_shadow: inShadow, path: path(el)};
  };
  const walk = (root, inShadow) => {
    for (const [k, sel] of Object.entries(groups))
      root.querySelectorAll(sel).forEach(el => out[k].push(describe(el, inShadow)));
    root.querySelectorAll('iframe').forEach(f => iframes.push(
      {id: f.id || '', src: (f.getAttribute('src') || '').slice(0, 150), title: f.title || '',
       in_shadow: inShadow, path: path(f)}));
    root.querySelectorAll('*').forEach(el => {
      if (el.shadowRoot) {
        shadows.push({host: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''), path: path(el)});
        walk(el.shadowRoot, true);
      }
    });
  };
  walk(document, false);
  // Conteúdo dos shadow roots (o page.content() não o inclui).
  const shadowHtml = [];
  const dump = root => root.querySelectorAll('*').forEach(el => {
    if (el.shadowRoot) { shadowHtml.push([path(el), el.shadowRoot.innerHTML]); dump(el.shadowRoot); }
  });
  dump(document);
  return {groups: out, shadows, iframes, shadowHtml};
}"""


def probe_composer(headless: bool = True) -> int:
    """Diagnóstico da caixa de publicação do LinkedIn. Nunca publica."""
    import re

    from .bot import BASE_URL, LinkedInBot

    out_file = DATA_DIR / "probe_composer.html"
    with LinkedInBot(headless=headless) as bot:
        bot.login()
        page = bot.page
        page.goto(f"{BASE_URL}/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        page.get_by_text(re.compile(r"^(Começar publicação|Começar um post|Start a post)$")).first.click()
        page.wait_for_timeout(12000)
        try:
            frames = []
            for frame in page.frames:
                try:
                    frames.append((frame, frame.evaluate(PROBE_JS)))
                except Exception as e:  # frame que sumiu ou bloqueou a avaliação
                    print(f"frame {frame.url[:100]}: não avaliado ({e})")
            html = [page.content()]
            for frame, info in frames:
                for host, inner in info["shadowHtml"]:
                    html.append(f"\n<!-- ===== shadow root de {host} (frame {frame.url[:100]}) ===== -->\n{inner}")
                if frame is not page.main_frame:
                    try:
                        html.append(f"\n<!-- ===== iframe {frame.url[:150]} ===== -->\n{frame.content()}")
                    except Exception:
                        pass
            out_file.write_text("".join(html))
            print(f"\nHTML gravado em {out_file} ({sum(map(len, html))} caracteres)")

            for frame, info in frames:
                main = frame is page.main_frame
                print(f"\n######## frame {'principal' if main else 'filho'}: {frame.url[:120]}")
                for name, items in info["groups"].items():
                    print(f"\n== {name}: {len(items)}")
                    for el in items:
                        print(f"  - <{el['tag']}> id={el['id']!r} class={el['class']!r} role={el['role']!r} "
                              f"aria-label={el['aria_label']!r} data-placeholder={el['data_placeholder']!r} "
                              f"contenteditable={el['contenteditable']!r} visível={el['visible']} "
                              f"shadow={el['in_shadow']}\n      caminho: {el['path']}")
                print(f"\n== shadow roots abertos: {len(info['shadows'])}")
                for s in info["shadows"]:
                    print(f"  - host <{s['host']}>  caminho: {s['path']}")
                print(f"\n== iframes: {len(info['iframes'])}")
                for f in info["iframes"]:
                    print(f"  - id={f['id']!r} title={f['title']!r} src={f['src']!r} shadow={f['in_shadow']}"
                          f"\n      caminho: {f['path']}")
            print(f"\nframes do Playwright: {len(page.frames)}")
            for frame in page.frames:
                print(f"  - {frame.name!r} {frame.url[:150]}")
        finally:
            # Descarta o rascunho, se a caixa ficou aberta. Nada é publicado.
            page.keyboard.press("Escape")
            page.wait_for_timeout(1500)
            discard = page.get_by_role("button", name=re.compile(r"^(Descartar|Discard)$"))
            if discard.count():
                discard.first.click(timeout=10000)
                page.wait_for_timeout(1500)
                print("\nRascunho descartado.")
    return 0


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
