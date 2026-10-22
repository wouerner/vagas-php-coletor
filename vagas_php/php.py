"""Classifica textos de vagas: é vaga de engenharia de software com PHP? Extrai
modalidade, senioridade, contratação e stack PHP para os filtros do site."""

import re
import unicodedata

# Termos que indicam PHP (a linguagem ou o ecossistema).
PHP_STACK = {
    "PHP": r"\bphp\s?\d?(\.\d)?\b",
    "Laravel": r"\blaravel\b",
    "Symfony": r"\bsymfony\b",
    "CodeIgniter": r"\bcode\s?igniter\b",
    "CakePHP": r"\bcake\s?php\b",
    "Yii": r"\byii2?\b",
    "Laminas/Zend": r"\b(laminas|zend)\b",
    "Hyperf/Swoole": r"\b(hyperf|swoole|openswoole)\b",
    "Livewire": r"\blivewire\b",
    "Filament": r"\bfilament(php)?\b",
    "Magento": r"\bmagento\b",
    "WordPress": r"\bwordpress\b",
    "Drupal": r"\bdrupal\b",
}
PHP_STACK_RE = {name: re.compile(rx, re.I) for name, rx in PHP_STACK.items()}
# Frameworks e plataformas fortes o bastante para, sozinhos no título, indicar vaga PHP
# (WordPress, Magento e Drupal são PHP: temas, plugins e lojas contam).
PHP_CORE = re.compile(r"\b(php|laravel|symfony|code\s?igniter|cake\s?php|yii2?|laminas|"
                      r"hyperf|swoole|livewire|wordpress|magento|drupal)\b", re.I)

# Título de vaga de engenharia/desenvolvimento de software.
DEV_ROLE = re.compile(
    r"\b(desenvolvedor|desenvolvedora|developer|dev|programador|programadora|engenheir[oa]|"
    r"engineer|software|back[\s-]?end|full[\s-]?stack|tech\s?lead|l[ií]der t[eé]cnic[oa]|"
    r"arquitet[oa]|architect|staff|sre)\b", re.I)
# Títulos que mencionam tecnologia mas não são de engenharia (ex.: suporte, vendas).
NOT_DEV = re.compile(
    r"\b(vendas|sales|comercial|marketing|recrutador|recruiter|tech recruiter|"
    r"suporte|support|designer|professor|instrutor|teacher|redator|copywriter)\b", re.I)

# Post de LinkedIn anunciando vaga (e não alguém procurando emprego). Sinais fortes bastam;
# os fracos aparecem também em posts sobre outros assuntos ("uma oportunidade de aprender",
# "grupos com vagas de TI", "processo seletivo da faculdade") e só valem com estrutura de
# vaga (requisitos, benefícios, contratação...) e sem contexto de outro assunto.
HIRING = re.compile(
    r"(\bvaga (para|de|aberta|dispon|home|remota|h[ií]brida|presencial|tech|ti\b|100%)|"
    r"\bvagas (aberta|dispon|home|remota|h[ií]brida|presencial|tech)|nova vaga|"
    r"contratando|contratamos|contrata-se|estamos (buscando|procurando|contratando|em busca)|"
    r"buscamos|procuramos|oportunidade (incr[ií]vel|100%)|"
    # "está procurando" só vale se não for falando com quem procura emprego ("quem está
    # procurando emprego...", "está procurando trabalho?").
    r"(est[aá]|que) (buscando|procurando|contratando|em busca)(?! (de )?(um |uma |nova |novo )?"
    r"(emprego|trabalho|vaga|oportunidade|recoloca|recolocação|uma recoloca))|"
    r"busca (uma pessoa|um\(a\)|um profissional)|"
    # "divulgação" sozinha aparece em outros assuntos ("divulgação de vulnerabilidades").
    r"divulga(ndo|[cç][aã]o) (de |da |das |desta |dessa |essa |esta |uma |a |as )?"
    r"(nova |nossa )?(vagas?|oportunidades?)\b|candidate-se|candidatar-se|inscreva-se|envie (seu )?curr[ií]culo|"
    r"me chama no privado|repassando vagas|hiring|we'?re hiring|job opening|open position|"
    r"join (our|the) team)", re.I)
HIRING_WEAK = re.compile(
    r"(oportunidades? (para|de|novas|abertas)|vagas (de|para)|processo seletivo|"
    r"(seguem|continuam|est[aã]o) abertas|#vagas?\w*|#hiring|#emprego|"
    r"(?m:^\W*(oportunidade|vaga)s?\b))", re.I)  # "Oportunidade GlobalTI (SP)" no começo da linha
HIRING_TAG = re.compile(r"#(vagas?\w*|hiring|emprego)\b", re.I)  # #vagas, #VagasTech, #VagasTI...
# Estrutura típica de anúncio de vaga (cada termo conta uma vez).
JOB_MARKERS = re.compile(
    r"\b(requisitos|benef[ií]cios|remunera[cç][aã]o|sal[aá]rio|contrata[cç][aã]o|clt|pj|"
    r"modelo de trabalho|regime|atribui[cç][oõ]es|responsabilidades|diferenciais|local:)",
    re.I)
# Contextos de posts que citam PHP mas não anunciam vaga: projeto pessoal, mudança de
# emprego, certificados. Só barram sinais fracos de contratação. Acrescente padrões aqui.
NOT_HIRING = [
    r"estou trabalhando (na|no|em)", r"\b(utilizei|desenvolvi|implementei|constru[ií])\b",
    r"\bmeu (projeto|portf[oó]lio|reposit[oó]rio|artigo|curso)\b",
    r"\b(encerro|encerrando) (hoje )?minha", r"\bminha jornada\b", r"\bnovo ciclo\b",
    r"\bcertificad[oa]s\b", r"\bparticipe d[oa]s?\b",
    r"\boportunidade de (aprender|aprendizado|crescimento pessoal)\b",
]
NOT_HIRING_RE = re.compile("|".join(f"({rx})" for rx in NOT_HIRING), re.I)
# Divulgação de grupos/canais/comunidades de vagas, sem curadoria ("Vagas T.I. - Remotas",
# "nosso Discord"...): barrada mesmo com sinal forte de contratação. Uma menção só é comum
# no rodapé de anúncios de verdade ("entre no grupo do Telegram"), então precisa de
# AGGREGATOR_MIN padrões diferentes. Acrescente padrões aqui.
AGGREGATOR = [
    r"\bdiscord\b", r"\btelegram\b", r"\bgrupos? de vagas\b", r"\bnossos grupos\b",
    r"\bnossas comunidades\b", r"\b(grupo|canal|comunidade) (do|no) whats\s?app\b",
    r"\bvagas t\.?i\.? -", r"\b(entre|participe) (no|do|nos|dos) (nosso )?(grupo|canal)",
    r"\bcanal de vagas\b",
]
AGGREGATOR_RES = [re.compile(rx, re.I) for rx in AGGREGATOR]
AGGREGATOR_MIN = 3
HASHTAG_OR_URL = re.compile(r"(#\w+|hashtag\s*#?\w+|https?://\S+)", re.I)
JOB_SEEKER = re.compile(
    r"(#opentowork|open to work|estou (em busca|buscando|procurando|dispon[ií]vel)|"
    r"procuro (uma )?(vaga|oportunidade|recoloca)|em busca de (uma )?(nova )?(oportunidade|"
    r"recoloca)|recoloca[cç][aã]o|(aberto|aberta|dispon[ií]vel) (a|para) (novas )?oportunidades|"
    r"looking for (a )?(new )?(job|role|position|opportunit)|actively looking|"
    r"seeking (a )?(new )?(job|role|position|opportunit)|open to (new )?(roles|opportunities)|"
    r"b[uú]squeda activa|buscando (nuevas )?oportunidades)", re.I)

WORKPLACE = [
    ("Remoto", re.compile(r"\b(remot[oa]|remote|home\s?office|anywhere|100% remoto)\b", re.I)),
    ("Híbrido", re.compile(r"\b(h[ií]brid[oa]|hybrid)\b", re.I)),
    ("Presencial", re.compile(r"\b(presencial|on[\s-]?site)\b", re.I)),
]
SENIORITY = [
    ("Estágio", re.compile(r"\b(est[aá]gi[oa]|estagi[aá]ri[oa]|intern(ship)?|trainee)\b", re.I)),
    ("Júnior", re.compile(r"\b(j[uú]nior|jr\.?)\b", re.I)),
    ("Pleno", re.compile(r"\b(pleno|pl\.?|mid[\s-]?level)\b", re.I)),
    ("Sênior", re.compile(r"\b(s[eê]nior|sr\.?)\b", re.I)),
    ("Especialista", re.compile(r"\b(especialista|staff|principal|tech\s?lead|l[ií]der|lead|"
                                r"arquitet[oa]|architect)\b", re.I)),
]
CONTRACT = [
    ("CLT", re.compile(r"\bclt\b", re.I)),
    ("PJ", re.compile(r"\bpj\b", re.I)),
    ("Freelance", re.compile(r"\b(freela(ncer?)?|contractor)\b", re.I)),
]


def _first(rules, *texts) -> str | None:
    """Primeiro rótulo que casa, procurando nos textos em ordem (título antes do corpo)."""
    for text in texts:
        if not text:
            continue
        for label, rx in rules:
            if rx.search(text):
                return label
    return None


def stack(*texts: str | None) -> list[str]:
    blob = " ".join(t for t in texts if t)
    return [name for name, rx in PHP_STACK_RE.items() if rx.search(blob)]


# Motivos de cada decisão (ids das regras em RULES).
JOB_OK = ("php_title", "php_description")
POST_OK = ("hiring_strong", "hiring_weak")


def job_verdict(title: str | None, description: str | None = None,
                labels: str | None = None) -> str:
    """Por que uma vaga de portal (LinkedIn Vagas e demais portais, InHire, GitHub) entra ou não: um id de
    RULES. Entram as de JOB_OK."""
    title = title or ""
    if NOT_DEV.search(title) and not DEV_ROLE.search(title):
        return "not_dev"
    if PHP_CORE.search(title) or (labels and PHP_CORE.search(labels)):
        return "php_title"
    if DEV_ROLE.search(title) and description and len(PHP_CORE.findall(description)) >= 2:
        return "php_description"
    return "no_php"


def is_php_job(title: str | None, description: str | None = None,
               labels: str | None = None) -> bool:
    """Vaga de engenharia de software com PHP: PHP/framework no título ou nas etiquetas,
    ou título de desenvolvimento com PHP em destaque na descrição (2+ menções: uma só
    costuma ser PHP numa lista de linguagens aceitas)."""
    return job_verdict(title, description, labels) in JOB_OK


def _job_title_line(text: str) -> bool:
    """Alguma linha com cara de título de vaga: cargo de desenvolvimento + PHP +
    senioridade ou modalidade ("• Pessoa Desenvolvedora PHP Sênior | 100% remoto"). Num
    post curto, senioridade, modalidade ou contratação podem vir em outra linha
    ("Desenvolvedor WordPress Full Stack" / "Modelo PJ/ Hibrido")."""
    short = len(text) < 400
    terms = lambda t: _first(SENIORITY, t) or _first(WORKPLACE, t) or _first(CONTRACT, t)  # noqa: E731
    for line in text.splitlines():
        line = HASHTAG_OR_URL.sub(" ", line)
        if (len(line) <= 160 and DEV_ROLE.search(line) and PHP_CORE.search(line)
                and (_first(SENIORITY, line) or _first(WORKPLACE, line) or (short and terms(text)))):
            return True
    return False


def _job_ad_shape(text: str) -> bool:
    """Estrutura de anúncio: 2+ itens (requisitos, benefícios, CLT/PJ...), uma linha com
    cara de título de vaga, ou post curto com hashtag de vaga."""
    markers = {m.lower() for m in JOB_MARKERS.findall(text)}
    return bool(len(markers) >= 2 or _job_title_line(text)
                or (len(text) < 300 and HIRING_TAG.search(text)))


def is_hiring(text: str) -> bool:
    """Tem sinal forte de contratação, ou sinal fraco sem contexto de outro assunto
    (NOT_HIRING) e com 2+ marcas de anúncio de vaga, ou num post curto com hashtag de vaga
    ("Dev PHP Sênior - Campinas #vagas")."""
    if HIRING.search(text):
        return True
    return bool(HIRING_WEAK.search(text) and _job_ad_shape(text)
                and not NOT_HIRING_RE.search(text))


def is_aggregator(text: str) -> bool:
    return sum(bool(rx.search(text)) for rx in AGGREGATOR_RES) >= AGGREGATOR_MIN


def post_verdict(text: str | None) -> str:
    """Por que um post do LinkedIn entra ou não: um id de RULES. Entram os de POST_OK."""
    if not text:
        return "post_no_php"
    body = HASHTAG_OR_URL.sub(" ", text)
    php_mentions = len(PHP_CORE.findall(body))
    if not (php_mentions and (DEV_ROLE.search(body) or php_mentions >= 2)):
        return "post_no_php"
    if is_aggregator(text):
        return "aggregator"
    # "Estou em busca de pessoas..." é recrutador, não alguém procurando emprego.
    if JOB_SEEKER.search(text) and not RECRUITING.search(text):
        return "job_seeker"
    if HIRING.search(text):
        return "hiring_strong"
    if not HIRING_WEAK.search(text):
        return "no_hiring"
    if NOT_HIRING_RE.search(text):
        return "other_subject"
    return "hiring_weak" if _job_ad_shape(text) else "no_hiring"


def is_php_hiring_post(text: str | None) -> bool:
    """Post do LinkedIn que anuncia vaga PHP: cita PHP no texto junto de um cargo de
    desenvolvimento, ou mais de uma vez (hashtags e links não contam: posts genéricos
    enchem de #php #java...); não é lista de vagas/grupos (AGGREGATOR) nem de alguém
    procurando emprego; e tem sinal claro de contratação."""
    return post_verdict(text) in POST_OK


# Recrutador "em busca de pessoas" para uma vaga: o texto parece de quem procura emprego.
RECRUITING = re.compile(
    r"(candidate-se|candidatar-se|inscreva-se|envie (seu )?curr[ií]culo|estou conduzindo|"
    r"(em busca|procurando|buscando) (de )?(pessoas|profissionais|talentos|candidat)|"
    r"buscamos|contratamos|estamos contratando|apply here|we'?re hiring)", re.I)


# Headline (o texto abaixo do nome) de quem trabalha com recrutamento: página /recrutadores.
RECRUITER = re.compile(
    r"\b(recruit\w*|recrut\w*|talent acquisition|aquisi[cç][aã]o de talentos|talent partner|"
    r"head\s?hunt\w*|(tech|talent|it) hunter)", re.I)


def is_recruiter(headline: str | None) -> bool:
    return bool(headline and RECRUITER.search(headline))


# Nome de empresa que não diz quem contrata (página /empresas): vaga confidencial e sites
# de vagas que repostam anúncios de outras empresas no LinkedIn. Acrescente padrões aqui.
NOT_EMPLOYER = re.compile(
    r"\b(confidencia(l|is)|sigilos[ao]|n[aã]o divulgad[ao]|jobgether|buscar\s?vagas)\b", re.I)
# Sufixos societários, ignorados ao agrupar ("XPTO LTDA" e "Xpto" são a mesma empresa).
COMPANY_SUFFIX = re.compile(
    r"[\s,.-]+(ltda|me|epp|eireli|s\.?\s?/?a\.?|inc|llc|ltd|gmbh)\.?$", re.I)


def company_key(name: str | None) -> str | None:
    """Chave para agrupar a mesma empresa escrita de jeitos diferentes; None se o nome
    não identifica quem contrata (NOT_EMPLOYER)."""
    if not name or NOT_EMPLOYER.search(name):
        return None
    name = unicodedata.normalize("NFKD", name.strip())
    while (stripped := COMPANY_SUFFIX.sub("", name)) != name:
        name = stripped
    return re.sub(r"[^a-z0-9]", "", name.encode("ascii", "ignore").decode().lower()) or None


def details(title: str | None, *texts: str | None) -> dict:
    """Modalidade, senioridade, contratação e stack, priorizando o título."""
    return {
        "workplace": _first(WORKPLACE, title, *texts),
        "seniority": _first(SENIORITY, title) or _first(SENIORITY, *texts),
        "contract": _first(CONTRACT, title, *texts),
        "stack": ",".join(stack(title, *texts)) or None,
    }



# --- regras publicadas no site (página /regras) -------------------------------------
# Texto para pessoas + as expressões usadas de fato, tiradas das constantes acima: a
# página nunca fica diferente do filtro. Mantenha a ordem em que as regras são aplicadas.

def _patterns(*rxs) -> list[str]:
    out = []
    for rx in rxs:
        out += rx if isinstance(rx, list) else [getattr(rx, "pattern", rx)]
    return out


RULES = [
    {"group": "vagas", "id": "not_dev", "effect": "recusa",
     "title": "Cargo que não é de engenharia",
     "text": "Título de vendas, suporte, design, ensino, recrutamento etc., sem cargo de "
             "desenvolvimento junto, fica de fora mesmo citando PHP.",
     "patterns": _patterns(NOT_DEV)},
    {"group": "vagas", "id": "php_title", "effect": "aceita",
     "title": "PHP ou framework PHP no título",
     "text": "PHP, Laravel, Symfony, CodeIgniter, CakePHP, Yii, Laminas, Hyperf/Swoole, "
             "Livewire, WordPress, Magento ou Drupal no título da vaga (ou nas etiquetas da "
             "issue, no GitHub).",
     "patterns": _patterns(PHP_CORE)},
    {"group": "vagas", "id": "php_description", "effect": "aceita",
     "title": "Cargo de desenvolvimento com PHP em destaque na descrição",
     "text": "Título de desenvolvimento (desenvolvedor, back-end, full stack...) e PHP citado "
             "2 ou mais vezes na descrição. Uma menção só costuma ser PHP numa lista de "
             "linguagens aceitas, e não conta.",
     "patterns": _patterns(DEV_ROLE)},
    {"group": "vagas", "id": "no_php", "effect": "recusa",
     "title": "Sem PHP em destaque",
     "text": "O que não se encaixa nas regras acima: a busca dos sites é ampla e traz vagas "
             "de outras linguagens.", "patterns": []},

    {"group": "posts", "id": "post_no_php", "effect": "recusa",
     "title": "Não fala de PHP",
     "text": "O texto precisa citar PHP (ou framework/plataforma PHP, inclusive WordPress, "
             "Magento e Drupal) junto de um cargo de "
             "desenvolvimento, ou mais de uma vez. Hashtags e links não contam: muitos "
             "posts enchem de #php #java #python.", "patterns": _patterns(PHP_CORE)},
    {"group": "posts", "id": "aggregator", "effect": "recusa",
     "title": "Divulgação de grupos e canais de vagas, sem curadoria",
     "text": f"Posts que divulgam grupos, canais e comunidades de vagas (Discord, Telegram, "
             f"WhatsApp, \"Vagas T.I. - Remotas\"...): {AGGREGATOR_MIN} ou mais das expressões "
             f"abaixo, diferentes entre si. Vale mesmo quando o texto tem sinal de "
             f"contratação: queremos o anúncio da vaga, não a propaganda do grupo. Uma menção "
             f"só (\"entre no nosso grupo do Telegram\" no fim de um anúncio) não barra.",
     "patterns": _patterns(AGGREGATOR)},
    {"group": "posts", "id": "job_seeker", "effect": "recusa",
     "title": "Pessoa procurando emprego",
     "text": "Posts de quem procura vaga (#opentowork, \"estou em busca de oportunidade\"...) "
             "não são anúncios. Texto de "
             "recrutador (\"estou em busca de pessoas\", \"candidate-se\"...) não conta como "
             "procura de emprego.",
     "patterns": _patterns(JOB_SEEKER)},
    {"group": "posts", "id": "hiring_strong", "effect": "aceita",
     "title": "Sinal forte de contratação",
     "text": "\"Vaga para\", \"contratando\", \"estamos buscando\", \"candidate-se\", "
             "\"envie seu currículo\", \"we're hiring\"... \"Está procurando\" não vale quando "
             "vem seguido de emprego, trabalho, vaga ou oportunidade: aí o post fala com quem "
             "procura emprego (\"quem está procurando emprego sabe...\"), não anuncia vaga.",
     "patterns": _patterns(HIRING)},
    {"group": "posts", "id": "other_subject", "effect": "recusa",
     "title": "Outro assunto",
     "text": "Com sinal fraco de contratação (abaixo), posts sobre projeto pessoal, troca de "
             "emprego, certificados etc. ficam de fora.", "patterns": _patterns(NOT_HIRING)},
    {"group": "posts", "id": "hiring_weak", "effect": "aceita",
     "title": "Sinal fraco de contratação com cara de anúncio",
     "text": "\"Oportunidade para\", \"oportunidades abertas\", \"processo seletivo\", "
             "#vagas, #VagasTech, uma linha começando com \"Oportunidade\" ou \"Vaga\"... só "
             "valem com cara de anúncio: 2 ou mais itens de anúncio (requisitos, benefícios, "
             "salário, CLT/PJ...), uma linha com cara de título de vaga (cargo de "
             "desenvolvimento + PHP + senioridade ou modalidade, ex.: \"Pessoa Desenvolvedora "
             "PHP Sênior | 100% remoto\"; num post curto, de até 400 caracteres, senioridade, "
             "modalidade ou contratação podem vir em outra linha) ou um post curto (menos de "
             "300 caracteres) com hashtag de vaga.",
     "patterns": _patterns(HIRING_WEAK, JOB_MARKERS)},
    {"group": "posts", "id": "no_hiring", "effect": "recusa",
     "title": "Sem sinal de contratação",
     "text": "Fala de PHP, mas não anuncia vaga.", "patterns": []},

    {"group": "recrutadores", "id": "recruiter", "effect": "aceita",
     "title": "Headline de recrutamento",
     "text": "Entra na página de recrutadores quem publicou vagas PHP aceitas nos últimos "
             "90 dias (o mínimo de vagas aparece na página) e tem no headline do LinkedIn (o texto abaixo do nome) Tech "
             "Recruiter, recrutamento, Talent Acquisition, headhunter... Páginas de vagas e "
             "devs que divulgam vagas não entram.",
     "patterns": _patterns(RECRUITER)},

    {"group": "empresas", "id": "not_employer", "effect": "recusa",
     "title": "Nome que não diz quem contrata",
     "text": "A página de empresas soma as vagas de portais dos últimos 90 dias por empresa. "
             "Vaga confidencial e sites de vagas que repostam anúncios de outras empresas "
             "ficam de fora dela (as vagas continuam no site). Nomes escritos de jeitos "
             "diferentes (maiúsculas, acentos, LTDA, ME, S.A.) contam como a mesma empresa.",
     "patterns": _patterns(NOT_EMPLOYER)},
]
