"""Bot que faz login no LinkedIn e lê posts: da timeline (feed) ou da busca de
publicações (ex.: "vaga php"). Derivado do bot do projeto linkedin."""

import fcntl
import os
import urllib.parse
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

BASE_URL = "https://www.linkedin.com"
# Pode apontar para a sessão do projeto linkedin (mesmo login e mesma trava de navegador).
SESSION_DIR = Path(os.getenv("VAGAS_SESSION_DIR") or Path(__file__).resolve().parent.parent / ".session")
# Contêineres de post: layout novo (classes ofuscadas, identificado por
# componentkey) e o layout clássico (data-urn).
POST_SELECTOR = ", ".join([
    '[componentkey^="update-card-focus"]',
    '[data-urn^="urn:li:activity"]',
    '[data-id^="urn:li:activity"]',
    '[data-urn^="urn:li:aggregate"]',
])
LOGIN_BUTTON = re.compile(r"^(Entrar|Sign in)$", re.I)
POST_MENU = re.compile(r"^(Abrir menu de controle da publicação de|Open control menu for post by) ")
COPY_LINK = re.compile(r"^(Copiar link da publicação|Copy link to post)$", re.I)
POST_ID = re.compile(r"(activity|ugcPost|share)[-:](\d{10,})")

# Mensagem de erro visível no formulário de login (ex.: "senha incorreta").
FORM_ERROR_JS = """
() => {
  for (const el of document.querySelectorAll(
      '[role="alert"], [aria-live], [id*="error"], .alert-content')) {
    const text = (el.innerText || '').trim();
    if (text && el.offsetParent !== null) return text;
  }
  return null;
}
"""

# Extrai os posts visíveis no DOM. O layout novo do LinkedIn usa classes
# ofuscadas, então os campos saem de atributos de acessibilidade (aria-label,
# data-testid) e do texto visível do card; o layout clássico usa as classes antigas.
EXTRACT_POSTS_JS = r"""
(selector) => {
  const SEEKING = /buscando emprego|open to work|looking for a job/i;
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  // Textos com parte oculta para leitor de tela aparecem duplicados ("XX" -> "X").
  const undup = s => {
    s = clean(s);
    const h = s.length / 2;
    return Number.isInteger(h) && s.slice(0, h) === s.slice(h) ? s.slice(0, h) : s;
  };
  const pick = (root, selectors) => {
    for (const sel of selectors) {
      const el = root.querySelector(sel);
      if (el && el.innerText.trim()) return el.innerText.trim();
    }
    return null;
  };
  const isTime = l => /^(há\s|\d+\s?(min|h|d|sem|m|a|mo|w|y|yr)\b)/i.test(l);

  // "Fulano e mais 185 pessoas reagiram" -> "186"; "1.234 reações" -> "1.234".
  const reactionCount = lines => {
    const toInt = n => parseInt(n.replace(/[.,]/g, ''), 10);
    for (const l of lines) {
      let m = l.match(/(?:e mais|and)\s+([\d.,]+)\s+(?:pessoas?|outras pessoas|others?)\b/i);
      if (m) return String(toInt(m[1]) + 1);
      m = l.match(/^([\d.,]+)\s*(?:reações|reactions)\b/i);
      if (m) return String(toInt(m[1]));
    }
    const m = lines.find(l => /\s(reagiu|reacted)$/i.test(l) && l.length < 120);
    return m ? '1' : null;
  };

  const parseNew = c => {
    const lines = c.innerText.split('\n').map(clean).filter(Boolean)
      .filter(l => !/^(Publicação no feed|Feed post)$/i.test(l));
    let author = null;
    for (const el of c.querySelectorAll('[aria-label]')) {
      const m = el.getAttribute('aria-label')
        .match(/^(?:Abrir menu de controle da publicação de|Open control menu for post by)\s+(.+)$/i);
      if (m) { author = clean(m[1]); break; }
    }
    const ai = author ? lines.indexOf(author) : -1;
    const context = ai > 0 ? lines.slice(0, ai).join(' · ') : null;
    let headline = null;
    if (ai >= 0) {
      const rest = lines.slice(ai + 1).filter(l => !/^•/.test(l));
      if (rest.length && !isTime(rest[0])) headline = rest[0];
    }
    const timeLine = lines.find(isTime) || null;
    // Selo "buscando emprego" na foto do autor: vem no texto alternativo da imagem.
    const openToWork = !!author && [...c.querySelectorAll('img[alt]')].some(i => {
      const alt = i.getAttribute('alt');
      return alt.includes(author) && SEEKING.test(alt);
    });
    const textEl = c.querySelector('[data-testid="expandable-text-box"]');
    const find = re => { const l = lines.find(x => re.test(x)); return l ? undup(l) : null; };
    let authorUrl = null;
    for (const a of c.querySelectorAll('a[href*="/in/"], a[href*="/company/"]')) {
      const label = a.getAttribute('aria-label') || a.innerText || '';
      if (author && label.includes(author)) { authorUrl = a.href.split('?')[0]; break; }
    }
    return {
      urn: null, url: null, author, author_url: authorUrl, headline,
      time: timeLine ? timeLine.split('•')[0].trim() : null,
      text: textEl ? textEl.innerText.trim() : null,
      reactions: reactionCount(lines),
      comments: find(/^\d[\d.,]*\s*(coment|comment)/i),
      shares: find(/^\d[\d.,]*\s*(compartilhamento|repost|share)/i),
      context,
      open_to_work: openToWork,
      // Rótulo de anúncio (às vezes duplicado para leitor de tela: "PromovidoPromovido").
      // Sem o rótulo, a falta de horário também indica anúncio: post orgânico sempre
      // mostra "há N h/d".
      promoted: lines.some(l => /^(Promovid[oa]|Patrocinad[oa]|Promoted|Sponsored)\b/i.test(undup(l)))
        || !timeLine,
    };
  };

  const parseClassic = c => {
    const urnAttr = c.getAttribute('data-urn') || c.getAttribute('data-id') || '';
    const m = urnAttr.match(/urn:li:activity:\d+/);
    const urn = m ? m[0] : (urnAttr || null);
    return {
      urn,
      url: m ? `https://www.linkedin.com/feed/update/${m[0]}/` : null,
      author: pick(c, ['.update-components-actor__title span[aria-hidden="true"]',
                       '.update-components-actor__title']),
      author_url: (c.querySelector('.update-components-actor__meta-link, .update-components-actor__image') || {}).href || null,
      headline: pick(c, ['.update-components-actor__description span[aria-hidden="true"]',
                         '.update-components-actor__description']),
      time: pick(c, ['.update-components-actor__sub-description span[aria-hidden="true"]',
                     '.update-components-actor__sub-description']),
      text: pick(c, ['.feed-shared-update-v2__description .update-components-text',
                     '.update-components-text', '.feed-shared-inline-show-more-text']),
      reactions: pick(c, ['.social-details-social-counts__reactions-count']),
      comments: pick(c, ['.social-details-social-counts__comments']),
      shares: null,
      context: pick(c, ['.update-components-header__text-view']),
      open_to_work: null,
      promoted: false,
    };
  };

  // Mantém só os contêineres mais externos (evita duplicar posts aninhados).
  const all = [...document.querySelectorAll(selector)];
  const containers = all.filter(c => !all.some(o => o !== c && o.contains(c)));
  return containers.map(c => {
    const post = c.hasAttribute('componentkey') ? parseNew(c) : parseClassic(c);
    // Cartões sem autor nem texto são widgets do LinkedIn (ex.: "Pesquisar vagas").
    if (c.hasAttribute('componentkey') && !post.author && !post.text) return null;
    post.key = c.getAttribute('componentkey') || post.urn;
    post.raw_text = (post.author || post.text) ? null : c.innerText.trim().slice(0, 3000);
    return post;
  }).filter(Boolean);
}
"""

@dataclass
class Post:
    author: str | None
    author_url: str | None
    headline: str | None
    time: str | None
    text: str | None
    reactions: str | None
    comments: str | None
    shares: str | None
    context: str | None
    promoted: bool
    urn: str | None
    url: str | None
    raw_text: str | None
    open_to_work: bool | None = None  # selo "buscando emprego" na foto do autor


class LoginError(RuntimeError):
    pass


class LinkedInBot:
    def __init__(self, email: str | None = None, password: str | None = None,
                 headless: bool = True, session_dir: Path = SESSION_DIR):
        self.email = email or os.getenv("LINKEDIN_EMAIL")
        self.password = password or os.getenv("LINKEDIN_PASSWORD")
        self.headless = headless
        self.session_dir = session_dir
        self._pw = None
        self._lock_file = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def __enter__(self):
        if not self.headless:
            _ensure_display()
        self._acquire_session_lock()
        self._pw = sync_playwright().start()
        # Contexto persistente: cookies ficam em .session/, então o login
        # (e eventual verificação 2FA) só precisa acontecer uma vez.
        self.context = self._pw.chromium.launch_persistent_context(
            str(self.session_dir),
            headless=self.headless,
            locale="pt-BR",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self

    def __exit__(self, *exc):
        try:
            if self.context:
                self.context.close()
            if self._pw:
                self._pw.stop()
        finally:
            if self._lock_file:
                self._lock_file.close()  # libera o flock
                self._lock_file = None

    def _acquire_session_lock(self, timeout: int = 600) -> None:
        """Garante um único navegador por perfil, mesmo entre processos/containers
        (serviço agendado + comando manual). Com o lock em mãos, as travas do
        Chromium que sobraram de execuções interrompidas são seguramente obsoletas."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(self.session_dir / ".bot.lock", "w")
        deadline = time.time() + timeout
        waiting = False
        while True:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() > deadline:
                    self._lock_file.close()
                    self._lock_file = None
                    raise RuntimeError("Outro processo está usando o navegador do bot.")
                if not waiting:
                    print("Aguardando outro processo liberar o navegador do bot...")
                    waiting = True
                time.sleep(2)
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            (self.session_dir / name).unlink(missing_ok=True)

    def is_logged_in(self) -> bool:
        self.page.goto(f"{BASE_URL}/feed/", wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)
        return "/feed" in self.page.url

    def login(self, verification_timeout: int = 300) -> None:
        if self.is_logged_in():
            print("Sessão existente válida, login não necessário.")
            return
        if not self.email or not self.password:
            raise LoginError("Defina LINKEDIN_EMAIL e LINKEDIN_PASSWORD no arquivo .env")

        print("Fazendo login...")
        self.page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        # A página de login usa classes ofuscadas e pode renderizar um formulário
        # duplicado oculto, então buscamos campos visíveis por atributos semânticos.
        email = self.page.locator(
            "#username, input[autocomplete^='username'], input[type='email']").locator("visible=true").first
        password = self.page.locator(
            "#password, input[type='password']").locator("visible=true").first
        email.wait_for(timeout=20000)
        email.fill(self.email)
        password.fill(self.password)
        self.page.get_by_role("button", name=LOGIN_BUTTON, exact=True).locator("visible=true").first.click()

        deadline = time.time() + verification_timeout
        warned = False
        while time.time() < deadline:
            self.page.wait_for_timeout(1500)
            try:
                if self._login_finished(verification_timeout, warned):
                    print("Login realizado com sucesso.")
                    return
            except PlaywrightError:  # página navegou no meio da checagem; tenta de novo
                continue
            if not warned and ("/checkpoint" in self.page.url or "/challenge" in self.page.url):
                warned = True
        raise LoginError(f"Login não concluído a tempo (URL atual: {self.page.url})")

    def _login_finished(self, verification_timeout: int, warned: bool) -> bool:
        url = self.page.url
        if "/feed" in url:
            return True
        if "/checkpoint" in url or "/challenge" in url:
            if self.headless:
                raise LoginError(
                    "O LinkedIn pediu verificação (2FA/captcha). Rode novamente com "
                    "--show para concluir a verificação na janela do navegador."
                )
            if not warned:
                print("Verificação de segurança solicitada: conclua-a na janela do "
                      f"navegador (aguardando até {verification_timeout}s)...")
            return False
        if "/login" in url or "/uas/" in url:
            # Só checa erro de formulário antes da verificação; depois dela o
            # LinkedIn passa por páginas de redirecionamento sob /uas/.
            if not warned:
                error = self.page.evaluate(FORM_ERROR_JS)
                if error:
                    raise LoginError(f"Falha no login: {error}")
            return False
        # Redirecionado para outra página logada (home, perfil, etc.).
        return url.startswith(BASE_URL) and self.is_logged_in()

    def read_timeline(self, limit: int = 20, max_scrolls: int = 30,
                      with_links: bool = False, keep=None) -> list[Post]:
        """Lê até `limit` posts do feed. Com `with_links`, preenche `url`/`urn` de
        cada post pelo menu "Copiar link da publicação" (mais lento)."""
        if "/feed" not in self.page.url:
            self.page.goto(f"{BASE_URL}/feed/", wait_until="domcontentloaded")
        return self._collect_posts(limit, max_scrolls, with_links, keep)

    def search_posts(self, keywords: str, limit: int = 20, date_posted: str = "past-24h",
                     max_scrolls: int = 20, with_links: bool = True, keep=None) -> list[Post]:
        """Busca publicações por palavra-chave, mais recentes primeiro. `date_posted`:
        "past-24h", "past-week" ou "past-month". `keep(post)` escolhe quais posts entram
        no resultado (e só esses têm o link buscado, que é a parte lenta)."""
        params = {"keywords": keywords, "origin": "FACETED_SEARCH",
                  "sortBy": '"date_posted"', "datePosted": f'"{date_posted}"'}
        self.page.goto(f"{BASE_URL}/search/results/content/?{urllib.parse.urlencode(params)}",
                       wait_until="domcontentloaded")
        return self._collect_posts(limit, max_scrolls, with_links, keep)

    def _collect_posts(self, limit: int, max_scrolls: int, with_links: bool,
                       keep=None) -> list[Post]:
        try:
            self.page.wait_for_selector(POST_SELECTOR, timeout=20000)
        except Exception:
            pass

        seen: set[str] = set()
        posts: dict[str, Post] = {}
        stale = 0
        for _ in range(max_scrolls):
            self._expand_see_more()
            before = len(seen)
            for data in self.page.evaluate(EXTRACT_POSTS_JS, POST_SELECTOR):
                key = data.pop("key") or (data["text"] or data["raw_text"] or "")[:200]
                if not key or key in seen:
                    continue
                seen.add(key)
                post = Post(**data)
                if post.promoted or (keep and not keep(post)):
                    continue
                posts[key] = post
                if with_links and not post.url and len(posts) <= limit:
                    self._fill_link(key, post)
            if len(posts) >= limit:
                break
            self.page.mouse.wheel(0, 2500)
            self.page.wait_for_timeout(1800)
            stale = stale + 1 if len(seen) == before else 0
            if stale >= 5:
                break
        return list(posts.values())[:limit]

    def _fill_link(self, key: str, post: Post) -> None:
        card = self.page.locator(f'[componentkey="{key}"]')
        self.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE_URL)
        copy_item = self.page.get_by_role("menuitem", name=COPY_LINK).first
        for _ in range(3):
            try:
                # Limpa a área de transferência: se a cópia falhar em silêncio, não
                # herdamos o link do post anterior.
                self.page.evaluate("navigator.clipboard.writeText('')")
                card.scroll_into_view_if_needed(timeout=5000)
                card.get_by_role("button", name=POST_MENU).first.click(timeout=5000)
                # O menu às vezes não abre se a página ainda está hidratando.
                copy_item.wait_for(timeout=3000)
                copy_item.click(timeout=3000)
                link = ""
                for _ in range(6):
                    self.page.wait_for_timeout(300)
                    if link := self.page.evaluate("navigator.clipboard.readText()"):
                        break
            except PlaywrightError:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(1000)
                continue
            if link:
                post.url, post.urn = self.resolve_post_url(link)
                return

    def resolve_post_url(self, link: str) -> tuple[str, str | None]:
        """Expande links lnkd.in e devolve (url canônica, urn) do post."""
        link = link.strip()
        if link.startswith("/"):
            link = BASE_URL + link
        if "lnkd.in" in link:
            resp = self.context.request.get(link, max_redirects=0, fail_on_status_code=False)
            link = resp.headers.get("location", link)
        url = link.split("?")[0]
        m = POST_ID.search(url)
        urn = f"urn:li:{m.group(1)}:{m.group(2)}" if m else None
        return url, urn

    def _expand_see_more(self) -> None:
        # Clica em "...mais" / "see more" para pegar o texto completo dos posts.
        for btn in self.page.query_selector_all(
                "[componentkey^='update-card-focus'] [data-testid='expandable-text-button'], "
                "button.feed-shared-inline-show-more-text__see-more-less-toggle[aria-expanded='false']"):
            try:
                btn.click(timeout=1000)
            except Exception:
                pass

    def screenshot(self, path: str) -> None:
        self.page.screenshot(path=path, full_page=False)


def _ensure_display() -> None:
    """Aponta para a sessão gráfica local quando o shell não herdou DISPLAY
    (ex.: terminal sem sessão gráfica rodando na mesma máquina do desktop)."""
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
        return
    sockets = sorted(Path("/tmp/.X11-unix").glob("X*"))
    if not sockets:
        return
    os.environ["DISPLAY"] = f":{sockets[0].name[1:]}"
    if not os.getenv("XAUTHORITY"):
        runtime = Path(f"/run/user/{os.getuid()}")
        candidates = sorted(runtime.glob("xauth_*")) + sorted(runtime.glob(".mutter-Xwaylandauth.*"))
        candidates.append(Path.home() / ".Xauthority")
        for c in candidates:
            if c.exists():
                os.environ["XAUTHORITY"] = str(c)
                break


def posts_to_dicts(posts: list[Post]) -> list[dict]:
    return [asdict(p) for p in posts]
