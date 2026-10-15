"""Post diário no LinkedIn: print do topo do dashboard (números, pizza por site e vagas por
dia) com um texto de resumo, publicado pela sessão logada do bot.

Antes de publicar, confere a caixa de publicação: o texto aparece uma vez só (o LinkedIn
pode restaurar um rascunho) e a imagem está anexada. A prévia e o resultado ficam em
data/linkedin_posts/ e o histórico em data/linkedin_posts.json (um post por dia, no
máximo)."""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import dates
from .bot import BASE_URL, LinkedInBot

log = logging.getLogger("vagas_php.linkedin_post")

DASHBOARD_URL = os.getenv("VAGAS_DASHBOARD_URL", "http://web:8000/dashboard")
SIGNATURE = "Deus seja Louvado"
SOURCES_TEXT = ("LinkedIn (vagas e publicações), Gupy, Catho, Sólides, Remotar, Programathor, "
                "Coodesh, Nerdin, Recrutei, UpVagas, InHire e dos repositórios de vagas no GitHub")


def text(k: dict, day: datetime) -> str:
    return f"""Montei um coletor de vagas PHP 🐘

Ele junta, a cada poucas horas, vagas de {SOURCES_TEXT}. Contam só vagas publicadas nas últimas 72 horas, incluindo Laravel, Symfony, WordPress, Magento e Drupal.

Hoje ({day:%d/%m}): {k['open']} vagas abertas, {k['new']} novas nas últimas 24 horas, {k['remote']} remotas, de {k['companies']} empresas.

Um filtro tira o que cita PHP mas não é vaga (cursos, listas de grupos, propaganda de currículo). As regras ficam públicas, por transparência.

#php #laravel #vagas #desenvolvimento

{SIGNATURE}"""


def dashboard_screenshot(path: Path) -> dict:
    """Print do topo do dashboard (até a linha de "Modalidade") e os 4 números do topo."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 1000},
                                    device_scale_factor=2, color_scheme="light")
            page.goto(DASHBOARD_URL, wait_until="networkidle")
            page.wait_for_function("document.getElementById('k-open').textContent.trim() !== '–'",
                                   timeout=30000)
            page.wait_for_timeout(1500)  # gráficos
            k = page.evaluate("""() => Object.fromEntries(
                [['open','k-open'],['new','k-new'],['remote','k-remote'],['companies','k-companies']]
                .map(([key, id]) => [key, document.getElementById(id).textContent.trim()]))""")
            top = page.evaluate("""() => document.getElementById('b-workplace')
                .closest('section').getBoundingClientRect().top + scrollY""")
            page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": 1200, "height": top - 30})
        finally:
            browser.close()
    if not all(re.fullmatch(r"\d+", v) for v in k.values()):
        raise RuntimeError(f"Dashboard sem números: {k}")
    return {key: int(v) for key, v in k.items()}


def publish(body: str, image: Path, out_dir: Path, headless: bool = True,
            dry_run: bool = False) -> None:
    """Abre a caixa de publicação, escreve o texto, anexa a imagem, confere e publica
    (com dry_run, para antes de publicar e descarta o rascunho)."""
    with LinkedInBot(headless=headless) as bot:
        bot.login()
        page = bot.page
        page.goto(f"{BASE_URL}/feed/", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        page.get_by_text(re.compile(r"^(Começar publicação|Começar um post|Start a post)$")).first.click()
        # A caixa de publicação fica num shadow DOM; buscar só dentro dela evita pegar
        # botões do feed com o mesmo nome (ex.: "Avançar" de carrosséis).
        box = page.locator("#interop-outlet")
        editor = box.locator("div.ql-editor[contenteditable=true], "
                             "div[role=textbox][contenteditable=true]").first
        editor.wait_for(timeout=20000)
        editor.click()
        page.keyboard.press("Control+A")  # rascunho restaurado de uma tentativa anterior
        page.keyboard.press("Backspace")
        for i, line in enumerate(body.split("\n")):
            if i:
                page.keyboard.press("Enter")
            if line:
                page.keyboard.insert_text(line)
        page.wait_for_timeout(1000)
        with page.expect_file_chooser(timeout=15000) as chooser:
            box.get_by_role("button", name=re.compile(r"^(Adicionar mídia|Add media)$")).click()
        chooser.value.set_files(str(image))
        # Etapa "Editor" da imagem: "Avançar" volta para a caixa com a imagem anexada.
        box.get_by_role("button", name=re.compile(r"^(Avançar|Next)$")).click(timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(out_dir / "preview.png"))
        box.locator("img[src^='data:image']").last.scroll_into_view_if_needed(timeout=5000)
        page.screenshot(path=str(out_dir / "preview-imagem.png"))

        typed = editor.inner_text()
        first_line = body.split("\n")[0]
        if typed.count(first_line) != 1 or SIGNATURE not in typed:
            raise RuntimeError("O texto na caixa de publicação não confere; nada publicado.")
        removable = box.get_by_role("button", name=re.compile(r"^(Remover conteúdo de mídia|Remove media)"))
        if not removable.count():
            raise RuntimeError("A imagem não foi anexada; nada publicado.")
        if dry_run:
            page.keyboard.press("Escape")
            box.get_by_role("button", name=re.compile(r"^(Descartar|Discard)$")).click(timeout=10000)
            page.wait_for_timeout(1500)
            return

        box.get_by_role("button", name=re.compile(r"^(Publicar|Post)$")).click()
        page.get_by_text(re.compile(r"Publicação (bem-sucedida|concluída)|Post successful", re.I)) \
            .first.wait_for(timeout=60000)
        page.screenshot(path=str(out_dir / "done.png"))
        # Oferta de "transformar em vaga" (teste pago): recusa.
        no = box.get_by_role("button", name=re.compile(r"^(Não|No)$"))
        if no.count():
            no.first.click()
        page.wait_for_timeout(2000)


def run(data_dir: Path, headless: bool = True, dry_run: bool = False) -> dict:
    """Print do dashboard + post. Grava o resultado no histórico (menos com dry_run)."""
    now = dates.now_utc().astimezone(dates.BRASILIA)
    out_dir = data_dir / "linkedin_posts" / now.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    entry = {"at": now.isoformat(timespec="seconds"), "day": now.date().isoformat()}
    try:
        image = out_dir / "dashboard.png"
        entry["numbers"] = dashboard_screenshot(image)
        body = text(entry["numbers"], now)
        (out_dir / "texto.txt").write_text(body)
        publish(body, image, out_dir, headless, dry_run)
        entry["ok"] = True
    except Exception as e:
        entry.update(ok=False, error=f"{type(e).__name__}: {e}")
        raise
    finally:
        if dry_run:
            entry["dry_run"] = True
        else:
            history = history_load(data_dir)
            (data_dir / "linkedin_posts.json").write_text(
                json.dumps([*history, entry][-200:], ensure_ascii=False, indent=1))
    log.info("Post diário %s: %s", "testado (sem publicar)" if dry_run else "publicado",
             entry["numbers"])
    return entry


def history_load(data_dir: Path) -> list[dict]:
    try:
        return json.loads((data_dir / "linkedin_posts.json").read_text())
    except (OSError, ValueError):
        return []


def posted_on(data_dir: Path, day: str) -> bool:
    return any(e.get("ok") and e.get("day") == day for e in history_load(data_dir))
