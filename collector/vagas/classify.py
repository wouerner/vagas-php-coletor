"""Classifica textos de vagas: é vaga de engenharia de software da linguagem configurada
(config.py: termos e stack ficam na base)? Extrai modalidade, senioridade, contratação e
stack para os filtros do site."""

import re
import unicodedata

from . import config

# A linguagem vem da configuração (config.py), recalculada em _configure() quando ela é
# carregada da base: CORE são os termos fortes o bastante para, sozinhos no título, indicar
# vaga da linguagem (no PHP, WordPress, Magento e Drupal também contam); STACK, as
# tecnologias mostradas nos filtros do site, na ordem da configuração.
CORE: re.Pattern
STACK: dict[str, str] = {}
STACK_RE: dict[str, re.Pattern] = {}

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
# "buscamos" sozinho aparece em outros assuntos ("buscamos desenvolver funcionalidades",
# "buscamos melhorar"): só vale com alvo de pessoa/cargo ("buscamos um profissional",
# "Buscamos Desenvolvedor(a) Pleno", "buscamos alguém") ou como título de lista de
# requisitos ("O que buscamos?", "buscamos:", "Buscamos experiência com").
BUSCAMOS = (
    r"buscamos ((apenas|agora|hoje|tamb[eé]m|sempre) )?((um|uma|un|una|um\(a\)|un/a|a) )?((nov[oa]s?|bo[ma]s?) )?"
    r"(pessoas?|profissiona(l|is)|desenvolvedor|desarrollador|devs?\b|programador|"
    r"talentos?|candidat|analistas?|engenheir|especialistas?|colaborador|estagi[aá]ri|"
    r"tech lead|algu[eé]m|alguien|quem|perfil|experi[eê]ncia|para (o|a) (desafio|vaga|time|equipe))"
    r"|buscamos\s*[:?]")
HIRING = re.compile(
    r"(\bvaga (para|de|aberta|dispon|home|remota|h[ií]brida|presencial|tech|ti\b|100%)|"
    r"\bvagas (aberta|dispon|home|remota|h[ií]brida|presencial|tech)|nova vaga|"
    r"contratando|contratamos|contrata-se|estamos (buscando|procurando|contratando|em busca)|"
    rf"{BUSCAMOS}|procuramos|oportunidade (incr[ií]vel|100%)|"
    # "está procurando" só vale se não for falando com quem procura emprego ("quem está
    # procurando emprego...", "está procurando uma nova oportunidade?"): até 2 palavras
    # qualificadoras antes ("uma nova", "um novo", "uma boa").
    r"(est[aá]|que) (buscando|procurando|contratando|em busca)(?! (de )?"
    r"((um|uma|nov[oa]s?|bo[ma]s?|outr[oa]s?|melhor|primeir[oa]) ){0,2}"
    r"(emprego|trabalho|vaga|oportunidade|recoloca))|"
    r"busca (uma pessoa|um\(a\)|um profissional)|"
    # "divulgação" sozinha aparece em outros assuntos ("divulgação de vulnerabilidades").
    r"divulga(ndo|[cç][aã]o) (de |da |das |desta |dessa |essa |esta |uma |a |as )?"
    r"(nova |nossa )?(vagas?|oportunidades?)\b|candidate-se|candidatar-se|inscreva-se|envie (seu )?curr[ií]culo|"
    # "hiring" sozinho aparece em posts sobre contratação ("Something I've noticed in
    # hiring..."); só as formas de anúncio valem (#hiring é sinal fraco, em HIRING_WEAK).
    r"me chama no privado|repassando vagas|we['’]?re hiring|we are hiring|"
    r"\b(is|are|now|currently|actively) hiring\b|\bhiring (for|a|an)\b|job opening|"
    r"open position|join (our|the) team)", re.I)
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
# Contextos de posts que citam a linguagem mas não anunciam vaga: projeto pessoal, mudança de
# emprego, certificados. Só barram sinais fracos de contratação. Acrescente padrões aqui.
NOT_HIRING = [
    r"estou trabalhando (na|no|em)", r"\b(utilizei|desenvolvi|implementei|constru[ií])\b",
    r"\bmeu (projeto|portf[oó]lio|reposit[oó]rio|artigo|curso)\b",
    r"\b(encerro|encerrando) (hoje )?minha", r"\bminha jornada\b", r"\bnovo ciclo\b",
    r"\bcertificad[oa]s\b", r"\bparticipe d[oa]s?\b",
    r"\boportunidade de (aprender|aprendizado|crescimento pessoal)\b",
]
NOT_HIRING_RE = re.compile("|".join(f"({rx})" for rx in NOT_HIRING), re.I)
# Vitrine de projeto: alguém mostrando o sistema/app/portfólio que está desenvolvendo ou
# desenvolveu ("Estou desenvolvendo o SITF, uma plataforma criada para... divulgação de
# vagas"). Barra até sinal forte de contratação, a menos que o texto recrute de fato
# (RECRUITING: "candidate-se", "envie seu currículo"...). Acrescente padrões aqui.
SHOWCASE = [
    r"\bestou desenvolvendo\b", r"\b(em|na) fase (final )?de desenvolvimento\b",
    r"\bainda n[aã]o foi (oficialmente )?lan[cç]ad[oa]\b",
    r"\bprojeto (pessoal|acad[eê]mico|de faculdade|de estudos?|integrador)\b", r"\bTCC\b",
    r"\bmeu (projeto|sistema|app|aplicativo|portf[oó]lio|saas)\b",
    r"\b(plataforma|sistema|aplica[cç][aã]o|app) (web )?(criad[oa]|desenvolvid[oa]) "
    r"(para|por mim)\b",
    r"\bdesenvolvi (um|uma|o|a) (sistema|plataforma|app|aplicativo|site|projeto)\b",
    # Aluno mostrando trabalho de curso ("Gostaria de compartilhar um projeto que desenvolvi
    # durante o curso técnico em Desenvolvimento de Sistemas, no Senai... Nosso grupo,
    # formado por mim, ..."). Acrescente padrões aqui.
    r"\bprojeto que (eu )?(desenvolvi|desenvolvemos|criei|criamos|fiz|fizemos)\b",
    r"\b(desenvolvi|desenvolvemos) (durante|no|na) (o |a )?(curso|faculdade|gradua[cç][aã]o|disciplina)\b",
    r"\btrabalho de conclus[aã]o\b",
    r"\bnosso grupo,? (formado|composto|escolheu|desenvolveu|apresentou)\b",
    r"\bnossa equipe (escolheu|desenvolveu|apresentou)\b",
    r"\bapresentad[oa] pel[oa] (professor|professora|orientador|orientadora)\b",
    r"\bgostaria de compartilhar (um|o|meu|nosso) projeto\b",
    r"\bprojeto (da|de|do) (faculdade|curso|TCC|semestre)\b",
    r"\bfeira de (ci[eê]ncias|tecnologia)\b",
]
SHOWCASE_RE = re.compile("|".join(f"({rx})" for rx in SHOWCASE), re.I)
# Formação/instituição (Senai, "curso técnico"...) não é sinal de vitrine: aparece em
# anúncio real como requisito ("curso técnico em Informática pelo Senai"), e recusar vaga
# de verdade custa mais que deixar passar uma vitrine.


def is_showcase(text: str) -> bool:
    return bool(SHOWCASE_RE.search(text))
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
# Lista de vagas montada por terceiros ("🚨 5 VAGAS HOME OFFICE:", "Confira essas 7
# vagas..."): várias vagas de empresas e áreas diferentes, cada uma com o próprio link de
# candidatura. Vale com JOB_LIST_MIN chamadas de candidatura seguidas de link (na mesma
# linha ou na seguinte), ou com um cabeçalho "N vagas" (N >= JOB_LIST_MIN) e JOB_LIST_MIN
# links. Um anúncio de verdade tem um link só. Acrescente padrões aqui.
JOB_LIST_APPLY = [
    r"candidate-se", r"candidatura", r"inscri[cç][aã]o", r"inscreva-se", r"aplique",
    r"apply( here| now)?",
]
JOB_LIST_APPLY_RE = re.compile(
    r"\b(" + "|".join(JOB_LIST_APPLY) + r")\b[^\w\n]*(\n[^\w\n]*)?https?://", re.I)
JOB_LIST_HEADER = [r"\b(\d+) (novas )?vagas\b", r"\b(essas|estas|as) (\d+) vagas\b"]
JOB_LIST_HEADER_RES = [re.compile(rx, re.I) for rx in JOB_LIST_HEADER]
JOB_LIST_MIN = 3
URL_RE = re.compile(r"https?://", re.I)
# Autor de post que é agregador de vagas, pelo NOME de quem publicou: páginas e
# consultorias que republicam anúncios genéricos de outras empresas, sem curadoria (e
# que ficam velhos). Não contratam: o anúncio que interessa é o de quem contrata. O
# critério é o nome denunciar o agregador ("Vagas Remotas", "DEVagas", "Jobs Brasil",
# "Recrutei Empregos"...) ou ser de página/consultoria conhecida que só repassa vaga. Nome
# de pessoa nunca entra aqui: um padrão só vale se não casa com nome de gente ("vagas?" e
# "jobs?" sem \b no começo pegam "DEVagas", "AloVagas!" e "MangaJobs", e nome de pessoa
# não tem essas palavras). Os nomes são comparados sem acento. Acrescente padrões aqui.
AGGREGATOR_AUTHOR = [
    r"vagas?\b", r"jobs?\b", r"\bempregos?\b", r"\bemprega\b",
    r"\bcandidat[ae] a[ií]\b", r"\bcaderno nacional\b", r"\brecrut(ei|a)\b",
    r"\bhunting\b", r"\bespecialistas em recrutamento\b", r"\bconsultoria de gente\b",
    r"\bassessoria de carreira\b", r"\bassessoria\b", r"^impulso$", r"\bcomunidade\b",
    r"^home office$",
]
AGGREGATOR_AUTHOR_RE = re.compile("|".join(f"({rx})" for rx in AGGREGATOR_AUTHOR), re.I)
# O dono do site (configuração "self_author": nomes e perfis): o post diário no LinkedIn
# (linkedin_post.py) cita as vagas e voltaria na busca de publicações. O site não se
# auto-coleta. Recalculados em _configure().
SELF_AUTHOR: dict
SELF_AUTHOR_RE: re.Pattern
SELF_AUTHOR_URL_RE: re.Pattern
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
# Salário citado no texto ("💰 Remuneração: R$ 5.800,00 (Bruto Mensal)", "Salário entre
# R$ 2.000,00 e R$ 3.000,00"), gravado no formato que Vaga::SALARY do site (web/src/Vaga.php) lê: "R$ 5.800",
# "R$ 2.000 a R$ 3.000", "US$ 7.083 por mês" (sem centavos; real sem período é mensal).
# Só vale valor na mesma linha de uma palavra de contexto. A linha com contexto que diz
# não ter valor ("a combinar", "competitivo"...) encerra a busca, mesmo citando R$ (é
# desconto ou benefício, não salário). Valor isolado depois de "até" ou "a partir de" é
# teto ou piso, não o salário: fica de fora. Acrescente padrões aqui.
SALARY_CONTEXT = [
    r"sal[aá]rios?", r"remunera[cç][aã]o", r"faixa salarial", r"piso", r"salary",
    r"rango salarial",
]
SALARY_CONTEXT_RE = re.compile(r"\b(" + "|".join(SALARY_CONTEXT) + r")\b", re.I)
# Moeda: R$, ou dólar escrito US$, USD, "USD $" ou $ sozinho (nunca colado a letra, para não
# pegar o $ de R$). Milhar por ponto (8.801) ou, só em dólar, por vírgula como no inglês
# (85,000): em reais a vírgula é centavo (5.800,00), e "R$ 1,600" é ambíguo e fica de fora
# (_salary_in). Valor seguido de mil/k/M ("$150M in annual bookings") não é salário.
SALARY_VALUE = (r"(R\$|US\$|\bUSD(?:\s?\$)?|(?<![a-z$])\$)\s?"
                r"(\d{1,3}(?:\.\d{3})+|\d{1,3}(?:,\d{3})+|\d+)(?:[.,]\d{2})?"
                r"(?![\d.,]*\d|\s*(?:mil|k|m)\b)")
SALARY_RANGE_SEP = [r"a", r"e", r"at[eé]", r"-", r"–"]
SALARY_RE = re.compile(
    SALARY_VALUE + r"(?:\s*(?:" + "|".join(SALARY_RANGE_SEP) + r")\s*" + SALARY_VALUE + r")?",
    re.I)
SALARY_PERIOD = [
    ("por mês", r"(bruto )?mensal|por m[eê]s|ao m[eê]s|/m[eê]s|per month|monthly"),
    ("por ano", r"por ano|anual|ao ano|/ano|per year|annual|yearly"),
    ("por hora", r"por hora|/hora|hora|per hour|hourly"),
]
SALARY_PERIOD_RES = [(label, re.compile(r"^\W{0,3}(" + rx + r")\b", re.I))
                     for label, rx in SALARY_PERIOD]
SALARY_REJECT = [
    r"a combinar", r"a convenir", r"combinar", r"a definir", r"ser[aá] informad[ao]",
    r"informad[ao] na entrevista", r"informar na entrevista", r"compat[ií]vel com o mercado",
    r"competitiv[oa]s?", r"confidencial",
]
SALARY_REJECT_RE = re.compile(r"\b(" + "|".join(SALARY_REJECT) + r")\b", re.I)
# Valor logo antes ou logo depois destas palavras não é salário ("desconto de R$ 1,00").
SALARY_NOT_PAY_RE = re.compile(r"(desconto( de)?|n[oa]s? benef[ií]cios?)\W{0,3}$", re.I)
SALARY_NOT_PAY_AFTER_RE = re.compile(r"^\W{0,3}(n[oa]s? benef[ií]cios?)\b", re.I)
SALARY_BOUND_RE = re.compile(r"\b(at[eé]|a partir de|acima de|up to)\W{0,3}$", re.I)


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
    return [name for name, rx in STACK_RE.items() if rx.search(blob)]


# Motivos de cada decisão (ids das regras em RULES).
JOB_OK = ("lang_title", "lang_description")
POST_OK = ("hiring_strong", "hiring_weak")


def job_verdict(title: str | None, description: str | None = None,
                labels: str | None = None) -> str:
    """Por que uma vaga de portal (LinkedIn Vagas e demais portais, InHire, GitHub) entra ou não: um id de
    RULES. Entram as de JOB_OK."""
    title = title or ""
    if NOT_DEV.search(title) and not DEV_ROLE.search(title):
        return "not_dev"
    if CORE.search(title) or (labels and CORE.search(labels)):
        return "lang_title"
    if DEV_ROLE.search(title) and description and len(CORE.findall(description)) >= 2:
        return "lang_description"
    return "no_lang"


def is_relevant_job(title: str | None, description: str | None = None,
                    labels: str | None = None) -> bool:
    """Vaga de engenharia de software da linguagem: termo de CORE no título ou nas
    etiquetas, ou título de desenvolvimento com a linguagem em destaque na descrição (2+
    menções: uma só costuma ser a linguagem numa lista de linguagens aceitas)."""
    return job_verdict(title, description, labels) in JOB_OK


def _job_title_line(text: str) -> bool:
    """Alguma linha com cara de título de vaga: cargo de desenvolvimento + linguagem
    (CORE) + senioridade ou modalidade ("• Pessoa Desenvolvedora PHP Sênior | 100%
    remoto"). Num post curto, senioridade, modalidade ou contratação podem vir em outra
    linha ("Desenvolvedor WordPress Full Stack" / "Modelo PJ/ Hibrido")."""
    short = len(text) < 400
    terms = lambda t: _first(SENIORITY, t) or _first(WORKPLACE, t) or _first(CONTRACT, t)  # noqa: E731
    for line in text.splitlines():
        line = HASHTAG_OR_URL.sub(" ", line)
        if (len(line) <= 160 and DEV_ROLE.search(line) and CORE.search(line)
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


def is_job_list(text: str) -> bool:
    """Lista de vagas (JOB_LIST_*): várias chamadas de candidatura com link, ou cabeçalho
    "N vagas" com vários links."""
    if len(JOB_LIST_APPLY_RE.findall(text)) >= JOB_LIST_MIN:
        return True
    header = any(int(re.search(r"\d+", m.group(0)).group(0)) >= JOB_LIST_MIN
                 for rx in JOB_LIST_HEADER_RES for m in rx.finditer(text))
    return header and len(URL_RE.findall(text)) >= JOB_LIST_MIN


def _plain_name(name: str | None) -> str:
    """Nome sem acentos e espaços nas pontas ("Emprega São José" -> "Emprega Sao Jose")."""
    name = unicodedata.normalize("NFKD", (name or "").strip())
    return name.encode("ascii", "ignore").decode()


def is_aggregator_author(author: str | None) -> bool:
    """Quem publicou é agregador de vagas (AGGREGATOR_AUTHOR), pelo nome."""
    return bool(author and AGGREGATOR_AUTHOR_RE.search(_plain_name(author)))


def is_self_author(author: str | None, author_url: str | None = None) -> bool:
    """Quem publicou é o dono do site (SELF_AUTHOR), pelo nome ou pelo perfil."""
    return bool((author and SELF_AUTHOR_RE.search(_plain_name(author)))
                or (author_url and SELF_AUTHOR_URL_RE.search(author_url.split("?")[0])))


def post_verdict(text: str | None, author: str | None = None) -> str:
    """Por que um post do LinkedIn entra ou não: um id de RULES. Entram os de POST_OK.
    O autor (nome de quem publicou) barra os posts do próprio site e os de agregadores."""
    if is_self_author(author):
        return "self_author"
    if not text:
        return "post_no_lang"
    body = HASHTAG_OR_URL.sub(" ", text)
    mentions = len(CORE.findall(body))
    if not (mentions and (DEV_ROLE.search(body) or mentions >= 2)):
        return "post_no_lang"
    if is_aggregator(text):
        return "aggregator"
    if is_job_list(text):
        return "job_list"
    # Agregador barra antes de julgar o texto: o anúncio pode ser bom, mas não é de quem
    # contrata.
    if is_aggregator_author(author):
        return "aggregator_author"
    # "Estou em busca de pessoas..." é recrutador, não alguém procurando emprego.
    if JOB_SEEKER.search(text) and not RECRUITING.search(text):
        return "job_seeker"
    # Quem mostra o próprio projeto pode citar "divulgação de vagas" sem contratar ninguém.
    if is_showcase(text) and not RECRUITING.search(text):
        return "showcase"
    if HIRING.search(text):
        return "hiring_strong"
    if not HIRING_WEAK.search(text):
        return "no_hiring"
    if NOT_HIRING_RE.search(text):
        return "other_subject"
    return "hiring_weak" if _job_ad_shape(text) else "no_hiring"


def is_hiring_post(text: str | None, author: str | None = None) -> bool:
    """Post do LinkedIn que anuncia vaga da linguagem: cita a linguagem (CORE) no texto
    junto de um cargo de desenvolvimento, ou mais de uma vez (hashtags e links não contam:
    posts genéricos enchem de #php #java...); não é divulgação de grupos (AGGREGATOR) nem lista de vagas
    de terceiros (JOB_LIST_*), nem de agregador
    de vagas (AGGREGATOR_AUTHOR) ou do próprio site (SELF_AUTHOR), nem de alguém
    procurando emprego; e tem sinal claro de contratação."""
    return post_verdict(text, author) in POST_OK


# Recrutador "em busca de pessoas" para uma vaga: o texto parece de quem procura emprego.
RECRUITING = re.compile(
    r"(candidate-se|candidatar-se|inscreva-se|envie (seu )?curr[ií]culo|estou conduzindo|"
    r"(em busca|procurando|buscando) (de )?(pessoas|profissionais|talentos|candidat)|"
    rf"{BUSCAMOS}|contratamos|estamos contratando|apply here|we'?re hiring)", re.I)


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


def _amount(digits: str) -> str:
    return f"{int(re.sub(r'[.,]', '', digits)):,}".replace(",", ".")


def _currency(symbol: str) -> str:
    return "R$" if symbol.upper() == "R$" else "US$"


def _salary_in(line: str) -> str | None:
    """Salário da linha (que já tem palavra de contexto), no formato de Vaga::SALARY do site (web/src/Vaga.php)."""
    for m in SALARY_RE.finditer(line):
        before, after = line[:m.start()], line[m.end():]
        if SALARY_NOT_PAY_RE.search(before) or SALARY_NOT_PAY_AFTER_RE.search(after):
            continue
        cur, low, high = _currency(m.group(1)), m.group(2), m.group(4)
        if high and _currency(m.group(3)) != cur:  # não mistura moedas
            high = None
        if cur == "R$" and "," in low + (high or ""):  # vírgula de milhar só em dólar
            continue
        if not high and SALARY_BOUND_RE.search(before):
            continue
        out = f"{cur} {_amount(low)}"
        if high and _amount(high) != _amount(low):
            out += f" a {cur} {_amount(high)}"
        period = next((label for label, rx in SALARY_PERIOD_RES if rx.search(after)), None)
        if cur == "US$" and not period:  # dólar sem período o site descarta (web/src/Vaga.php)
            continue
        if period and not (cur == "R$" and period == "por mês"):
            out += f" {period}"
        return out
    return None


def salary_from_text(title: str | None, *texts: str | None) -> str | None:
    """Salário citado no texto, priorizando o título; None se o texto não informa valor."""
    for text in (title, *texts):
        for line in (text or "").splitlines():
            if not SALARY_CONTEXT_RE.search(line):
                continue
            if SALARY_REJECT_RE.search(line):
                return None
            if found := _salary_in(line):
                return found
    return None


def details(title: str | None, *texts: str | None) -> dict:
    """Modalidade, senioridade, contratação, stack e salário, priorizando o título."""
    return {
        "workplace": _first(WORKPLACE, title, *texts),
        "seniority": _first(SENIORITY, title) or _first(SENIORITY, *texts),
        "contract": _first(CONTRACT, title, *texts),
        "stack": ",".join(stack(title, *texts)) or None,
        "salary": salary_from_text(title, *texts),
    }



# --- regras publicadas no site (página /regras) -------------------------------------
# Texto para pessoas + as expressões usadas de fato, tiradas das constantes acima: a
# página nunca fica diferente do filtro. Mantenha a ordem em que as regras são aplicadas.

def _patterns(*rxs) -> list[str]:
    out = []
    for rx in rxs:
        out += rx if isinstance(rx, list) else [getattr(rx, "pattern", rx)]
    return out


def _rules() -> list[dict]:
    """Regras com o nome e os termos da linguagem configurada."""
    lang = config.get("language")
    name, slug, examples = lang["name"], lang["slug"], lang["examples"]
    return [
        {"group": "vagas", "id": "not_dev", "effect": "recusa",
         "title": "Cargo que não é de engenharia",
         "text": "Título de vendas, suporte, design, ensino, recrutamento etc., sem cargo de "
                 f"desenvolvimento junto, fica de fora mesmo citando {name}.",
         "patterns": _patterns(NOT_DEV)},
        {"group": "vagas", "id": "lang_title", "effect": "aceita",
         "title": f"{name} ou tecnologia do ecossistema no título",
         "text": f"{examples} no título da vaga (ou nas etiquetas da issue, no GitHub).",
         "patterns": _patterns(CORE)},
        {"group": "vagas", "id": "lang_description", "effect": "aceita",
         "title": f"Cargo de desenvolvimento com {name} em destaque na descrição",
         "text": f"Título de desenvolvimento (desenvolvedor, back-end, full stack...) e {name} "
                 f"citado 2 ou mais vezes na descrição. Uma menção só costuma ser {name} numa "
                 f"lista de linguagens aceitas, e não conta.",
         "patterns": _patterns(DEV_ROLE)},
        {"group": "vagas", "id": "no_lang", "effect": "recusa",
         "title": f"Sem {name} em destaque",
         "text": "O que não se encaixa nas regras acima: a busca dos sites é ampla e traz vagas "
                 "de outras linguagens.", "patterns": []},

        {"group": "posts", "id": "self_author", "effect": "recusa",
         "title": "Post do próprio site",
         "text": "Os posts do dono do site no LinkedIn (o post diário com as vagas) citam vagas "
                 f"{name} e voltariam na busca: o site não coleta a si mesmo. Vale pelo nome ou pelo "
                 "perfil de quem publicou.",
         "patterns": _patterns(SELF_AUTHOR["names"], SELF_AUTHOR["urls"])},
        {"group": "posts", "id": "post_no_lang", "effect": "recusa",
         "title": f"Não fala de {name}",
         "text": f"O texto precisa citar {name} (ou tecnologia do ecossistema: {examples}) junto "
                 f"de um cargo de desenvolvimento, ou mais de uma vez. Hashtags e links não "
                 f"contam: muitos posts enchem de #{slug} #java #python.",
         "patterns": _patterns(CORE)},
        {"group": "posts", "id": "aggregator", "effect": "recusa",
         "title": "Divulgação de grupos e canais de vagas, sem curadoria",
         "text": f"Posts que divulgam grupos, canais e comunidades de vagas (Discord, Telegram, "
                 f"WhatsApp, \"Vagas T.I. - Remotas\"...): {AGGREGATOR_MIN} ou mais das expressões "
                 f"abaixo, diferentes entre si. Vale mesmo quando o texto tem sinal de "
                 f"contratação: queremos o anúncio da vaga, não a propaganda do grupo. Uma menção "
                 f"só (\"entre no nosso grupo do Telegram\" no fim de um anúncio) não barra.",
         "patterns": _patterns(AGGREGATOR)},
        {"group": "posts", "id": "job_list", "effect": "recusa",
         "title": "Lista de vagas montada por terceiros",
         "text": f"Posts que listam várias vagas, cada uma com o próprio link de candidatura "
                 f"(\"🚨 5 VAGAS HOME OFFICE\", \"Confira essas 7 vagas...\"): {JOB_LIST_MIN} ou "
                 f"mais chamadas de candidatura (\"Candidate-se:\", \"Inscrição:\", \"Apply:\"...) "
                 f"seguidas de link, ou um cabeçalho \"N vagas\" ({JOB_LIST_MIN} ou mais) com "
                 f"{JOB_LIST_MIN} ou mais links. Vale mesmo quando o texto tem sinal de "
                 f"contratação: queremos o anúncio de quem contrata, não listas montadas por "
                 f"terceiros, sem curadoria. Um anúncio com um link só não barra.",
         "patterns": _patterns([JOB_LIST_APPLY_RE.pattern], JOB_LIST_HEADER)},
        {"group": "posts", "id": "aggregator_author", "effect": "recusa",
         "title": "Publicado por agregador de vagas",
         "text": "Páginas, comunidades e consultorias que republicam anúncios genéricos de outras "
                 "empresas, sem curadoria (\"Vagas Remotas\", \"DEVagas\", \"Jobs Brasil\", "
                 "\"Recrutei Empregos\", \"Comunidade ...\", \"Home Office\"...): não são quem contrata, e as vagas costumam chegar velhas. O "
                 "bloqueio é pelo nome de quem publicou (sem acentos), não pelo texto, e vale "
                 "antes de julgar o anúncio. Nomes de pessoas não são bloqueados.",
         "patterns": _patterns(AGGREGATOR_AUTHOR)},
        {"group": "posts", "id": "job_seeker", "effect": "recusa",
         "title": "Pessoa procurando emprego",
         "text": "Posts de quem procura vaga (#opentowork, \"estou em busca de oportunidade\"...) "
                 "não são anúncios. Texto de "
                 "recrutador (\"estou em busca de pessoas\", \"candidate-se\"...) não conta como "
                 "procura de emprego.",
         "patterns": _patterns(JOB_SEEKER)},
        {"group": "posts", "id": "showcase", "effect": "recusa",
         "title": "Vitrine de projeto pessoal",
         "text": "Posts de quem mostra o próprio projeto, sistema, app ou portfólio (\"estou "
                 "desenvolvendo\", \"meu projeto\", \"TCC\"...) não são anúncios, mesmo que o "
                 "projeto fale de vagas (\"plataforma para divulgação de vagas\"). Se o texto "
                 "também recruta (\"candidate-se\", \"envie seu currículo\", \"contratamos\"...), "
                 "vale como anúncio.",
         "patterns": _patterns(SHOWCASE)},
        {"group": "posts", "id": "hiring_strong", "effect": "aceita",
         "title": "Sinal forte de contratação",
         "text": "\"Vaga para\", \"contratando\", \"estamos buscando\", \"candidate-se\", "
                 "\"envie seu currículo\", \"we're hiring\"... \"Está procurando\" não vale quando "
                 "vem seguido de emprego, trabalho, vaga ou oportunidade, mesmo com até 2 palavras "
                 "no meio (\"uma nova oportunidade\", \"um novo emprego\"): aí o post fala com quem "
                 "procura emprego (\"quem está procurando emprego sabe...\"), não anuncia vaga. "
                 "\"Hiring\" sozinho também não vale (aparece em posts sobre contratação), só em "
                 "forma de anúncio: \"we're hiring\", \"now hiring\", \"hiring a/for\"...",
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
                 f"desenvolvimento + {name} + senioridade ou modalidade, ex.: \"Pessoa "
                 f"Desenvolvedora {name} Sênior | 100% remoto\"; num post curto, de até 400 caracteres, senioridade, "
                 "modalidade ou contratação podem vir em outra linha) ou um post curto (menos de "
                 "300 caracteres) com hashtag de vaga.",
         "patterns": _patterns(HIRING_WEAK, JOB_MARKERS)},
        {"group": "posts", "id": "no_hiring", "effect": "recusa",
         "title": "Sem sinal de contratação",
         "text": f"Fala de {name}, mas não anuncia vaga.", "patterns": []},

        {"group": "recrutadores", "id": "recruiter", "effect": "aceita",
         "title": "Headline de recrutamento",
         "text": f"Entra na página de recrutadores quem publicou vagas {name} aceitas nos últimos "
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


def _configure() -> None:
    """Recalcula o que vem da configuração: termos da linguagem, stack, dono do site e as
    regras publicadas (que citam a linguagem e trazem as expressões)."""
    global CORE, STACK, STACK_RE, SELF_AUTHOR, SELF_AUTHOR_RE, SELF_AUTHOR_URL_RE, RULES
    CORE = re.compile(config.get("core"), re.I)
    STACK = {name: rx for name, rx in config.get("stack")}
    STACK_RE = {name: re.compile(rx, re.I) for name, rx in STACK.items()}
    SELF_AUTHOR = config.get("self_author")
    SELF_AUTHOR_RE = re.compile("|".join(f"({rx})" for rx in SELF_AUTHOR["names"]), re.I)
    SELF_AUTHOR_URL_RE = re.compile("|".join(f"({rx})" for rx in SELF_AUTHOR["urls"]), re.I)
    RULES = _rules()


RULES: list[dict] = []
config.on_load(_configure)
_configure()
