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
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from . import dates
from .bot import BASE_URL, LinkedInBot

log = logging.getLogger("vagas_php.linkedin_post")

DASHBOARD_URL = os.getenv("VAGAS_DASHBOARD_URL", "http://web:8000/dashboard")
SOURCES_TEXT = ("LinkedIn (vagas e publicações), Gupy, Catho, Sólides, Remotar, Programathor, "
                "Coodesh, Nerdin, Recrutei, UpVagas, InHire e dos repositórios de vagas no GitHub")


def text(k: dict, day: datetime) -> str:
    # Linha opcional no fim do post; vazia: sem assinatura. Lida aqui, depois do .env.
    signature = os.getenv("VAGAS_LINKEDIN_POST_SIGNATURE", "").strip()
    # Convite para o canal do Telegram, antes dos hashtags; vazia: sem a linha.
    telegram = os.getenv("VAGAS_LINKEDIN_POST_TELEGRAM", "https://t.me/vagas_php").strip()
    invite = (f"Receba o resumo semanal das vagas e alertas em tempo real no Telegram: {telegram}\n\n"
              if telegram else "")
    return f"""Montei um coletor de vagas PHP 🐘

Ele junta, a cada poucas horas, vagas de {SOURCES_TEXT}. Contam só vagas publicadas nas últimas 72 horas, incluindo Laravel, Symfony, WordPress, Magento e Drupal.

Hoje ({day:%d/%m}): {k['open']} vagas abertas, {k['new']} novas nas últimas 24 horas, {k['remote']} remotas, de {k['companies']} empresas.

Um filtro tira o que cita PHP mas não é vaga (cursos, listas de grupos, propaganda de currículo). As regras ficam públicas, por transparência.

{invite}#php #laravel #vagas #desenvolvimento""" + (f"\n\n{signature}" if signature else "")


def dashboard_screenshot(path: Path) -> dict:
    """Print do topo do dashboard (até a linha de "Modalidade") e os 4 números do topo."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 1000},
                                    device_scale_factor=2, color_scheme="light")
            # ?print=1: sem Google Analytics (não conta visita nem mostra o aviso de cookies).
            page.goto(DASHBOARD_URL + ("&" if "?" in DASHBOARD_URL else "?") + "print=1",
                      wait_until="networkidle")
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


# Onde procurar a caixa de publicação e o editor, em ordem. Os locators CSS do
# Playwright atravessam shadow roots abertos, então "#interop-outlet ..." alcança o
# editor dentro do shadow DOM (caixa antiga, Quill). Desde out/2026 a caixa é um
# <dialog> nativo no DOM principal, com editor TipTap/ProseMirror.
COMPOSER_EDITOR = ("[componentkey=ShareBox_textEditor][contenteditable=true], "
                   "div.ProseMirror[contenteditable=true], "
                   "div.ql-editor[contenteditable=true], "
                   "div[role=textbox][contenteditable=true]")
COMPOSER_BOXES = ("dialog[open]", "#interop-outlet", "body")


def find_composer(page, timeout: int = 20000):
    """(caixa, editor) da caixa de publicação aberta: a primeira caixa de
    COMPOSER_BOXES com um editor visível. A caixa é usada para achar os botões."""
    deadline = time.monotonic() + timeout / 1000
    while True:
        for box_sel in COMPOSER_BOXES:
            box = page.locator(box_sel)
            editor = box.locator(COMPOSER_EDITOR).first
            try:
                if editor.is_visible():
                    log.info("Caixa de publicação: %s", box_sel)
                    return box, editor
            except PlaywrightError:  # navegação no meio da busca
                pass
        if time.monotonic() > deadline:
            raise RuntimeError(
                f"Editor da caixa de publicação não encontrado em {timeout // 1000}s "
                f"(caixas {', '.join(COMPOSER_BOXES)}; editor {COMPOSER_EDITOR}). O LinkedIn "
                "pode ter mudado a caixa: rode python -m vagas_php post --probe.")
        page.wait_for_timeout(500)


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
        # Buscar só dentro da caixa evita pegar botões do feed com o mesmo nome (ex.:
        # "Avançar" de carrosséis).
        box, editor = find_composer(page)
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
            box.get_by_role("button", name=re.compile(r"^(Adicionar mídia|Add media|Mídia|Media)$")).click()
        chooser.value.set_files(str(image))
        # Etapa "Editor" da imagem: "Avançar" volta para a caixa com a imagem anexada.
        box.get_by_role("button", name=re.compile(r"^(Avançar|Next)$")).click(timeout=30000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(out_dir / "preview.png"))
        # Miniatura da imagem anexada: data: na caixa antiga, blob: na nova.
        attached = box.locator("img[src^='data:image'], img[src^='blob:']")
        if attached.count():
            attached.last.scroll_into_view_if_needed(timeout=5000)
        page.screenshot(path=str(out_dir / "preview-imagem.png"))

        typed = editor.inner_text()
        first_line, last_line = body.split("\n")[0], body.rstrip().split("\n")[-1]
        if typed.count(first_line) != 1 or last_line not in typed:
            raise RuntimeError("O texto na caixa de publicação não confere; nada publicado.")
        removable = box.get_by_role("button", name=re.compile(r"^(Remover conteúdo de mídia|Remove media)"))
        if not (removable.count() or attached.count()):
            raise RuntimeError("A imagem não foi anexada; nada publicado.")
        if dry_run:
            # Caixa antiga: Esc pede confirmação. Nova (<dialog>): "Fechar" pede confirmação.
            page.keyboard.press("Escape")
            discard = box.get_by_role("button", name=re.compile(r"^(Descartar|Discard)$"))
            try:
                discard.first.wait_for(timeout=3000)
            except PlaywrightError:
                box.get_by_role("button", name=re.compile(r"^(Fechar|Dismiss)$")).first.click(timeout=10000)
            discard.first.click(timeout=10000)
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
