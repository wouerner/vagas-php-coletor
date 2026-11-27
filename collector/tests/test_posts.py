"""Filtro de posts do LinkedIn (classify.post_verdict): o que é anúncio de vaga e o que não é."""

import pytest

from vagas import classify

# Post real (30/10/2026), resumido: opinião sobre vagas que pedem tecnologias demais. Cita PHP
# numa lista, abre com "Estamos contratando...?" e fala de "uma vaga de tecnologia".
OPINION_POST = """🚨 Estamos contratando profissionais de TI ou departamentos inteiros?
Hoje me deparei com uma vaga de tecnologia que me fez refletir sobre como algumas empresas
estruturam seus requisitos técnicos.
💻 Back-end: Java EE, Spring Boot, PHP, Python, Delphi, Node.js.
🗄️ Banco de dados: PostgreSQL, Oracle, SQL Server, MySQL, MongoDB, Redis.
Não questiono a importância de profissionais multidisciplinares.
💬 Minha pergunta para recrutadores, gestores de TI e profissionais da área:
Estamos buscando profissionais compatíveis com os desafios da função ou alguém que domine
todo o ecossistema tecnológico de uma organização?
Quero ouvir a opinião de vocês!
#TecnologiaDaInformação #RecrutamentoTI #DesenvolvimentoDeSoftware"""


def test_opinion_about_jobs_is_not_a_job():
    assert classify.post_verdict(OPINION_POST, "Anderson Luiz Heckmann") == "opinion"
    assert not classify.is_hiring_post(OPINION_POST)


@pytest.mark.parametrize("text", [
    # Pede opinião, mas diz como se candidatar.
    "Estamos contratando Desenvolvedor PHP Sênior, remoto. O que vocês acham do nosso "
    "processo? Candidate-se: https://empresa.gupy.io/jobs/1",
    "Me deparei com essa vaga de Desenvolvedor PHP Pleno e lembrei de vocês: "
    "https://www.linkedin.com/jobs/view/123",
    "Vaga para Desenvolvedor Laravel Pleno, PJ. Quero ouvir a opinião de vocês sobre o "
    "anúncio! Envie seu currículo para vagas@empresa.com.br",
    # Gancho comum de anúncio, no singular: não é pedido de opinião.
    "O que você acha de trabalhar numa empresa inovadora? Estamos contratando Desenvolvedor "
    "PHP Sênior, 100% remoto.",
])
def test_job_post_asking_for_opinion_is_still_a_job(text):
    assert classify.post_verdict(text) == "hiring_strong"


def test_opinion_rule_is_published():
    rules = {r["id"]: r for r in classify.RULES}
    assert rules["opinion"]["effect"] == "recusa"
    assert rules["opinion"]["patterns"] == classify.OPINION


# Falsos positivos reais do site PHP (21/11/2026), resumidos e sem nomes de pessoas.
@pytest.mark.parametrize("text, verdict", [
    # Estudante procurando o primeiro emprego; "uma vaga de desenvolvimento" no fim.
    ("Estou no 4o semestre de ADS e procurando minha primeira oportunidade em tecnologia.\n"
     "Base da faculdade: POO, Desenvolvimento Web (HTML, CSS, JavaScript, PHP) e Engenharia de "
     "Software.\nSe você conhece uma vaga de desenvolvimento, me chama!", "job_seeker"),
    # Indicação de candidato para recrutadores.
    ("Ei, tech recruiters! 🚨\nTrouxe a salvação daquela vaga de dev que parece não ter fim!\n"
     "Ele é Engenheiro de Software Full Stack, com Magento 2, PHP, Laravel e React.\n"
     "Tech recruiters, façam esse match acontecer!", "job_seeker"),
    # Propaganda de Discord e comunidades.
    ("Já trabalha com tecnologia? Conecte-se com profissionais da sua especialidade.\n"
     "Nosso Discord recebe divulgações de vagas diariamente! Inscreva-se: https://lnkd.in/x\n"
     "Para conhecer todos os grupos, confira este endereço.\nTambém temos o grupo Freelances "
     "T.I. II.\nConfira algumas comunidades: WordPress, desenvolvimento de software...",
     "aggregator"),
    # Vaga de marketing com WordPress nos requisitos.
    ("Vaga remota para Analista de Marketing Digital no Brasil atendendo o mercado dos EUA!\n"
     "Experiência com SEO e WordPress, gestão de WordPress e GA4.\nPractical knowledge of "
     "WordPress. Apply here!", "post_not_dev"),
    # Resumo do dia sem nenhuma vaga de fato.
    ("Hoje foram publicadas 9 vagas de início de carreira.\nO destaque do dia está em "
     "tecnologia, com vagas em backend PHP, QA e suporte.", "job_list"),
    # PHP só como uma das linguagens aceitas.
    ("NOVA OPORTUNIDADE | Engenheiro(a) Sénior de Infraestrutura & DevSecOps\nO que "
     "procuramos? Experiência em servidores, redes e firewalls. Experiência com PHP e/ou C#.",
     "post_lang_in_list"),
    ("Estamos buscando profissionais para Backend Engineer, com experiência em tecnologias "
     "como Java, PHP, C# ou desenvolvimento Fullstack. Japonês nível N2.",
     "post_lang_in_list"),
])
def test_false_positives_from_production(text, verdict):
    assert classify.post_verdict(text) == verdict
    assert not classify.is_hiring_post(text)


def test_ccbr_page_is_rejected_by_author_url():
    text = (
        "CCBR - Conexão Corporativa Brasil: EDIÇÃO ESPECIAL TECH — VAGAS 100% REMOTAS EM TECNOLOGIA "
        "(DE ESTÁGIO A SÊNIOR — COM FAIXAS DE ATÉ R$ 18.000/MÊS)!\n"
        "Confira as vagas e seleções disponíveis no portal: https://lnkd.in/ebhnDa8w"
    )
    author = "CCBR - Conexão Corporativa Brasil"
    author_url = "https://br.linkedin.com/company/ccbr-conex%C3%A3o-corporativo-brasil?trk=public_post_feed-actor-image"
    assert classify.post_verdict(text, author, author_url) == "aggregator_author"
    assert not classify.is_hiring_post(text, author, author_url)


def test_vaz10k_page_is_rejected_by_author_url():
    text = (
        "VAGA REMOTA: Desenvolvedor Backend SENIOR (HostGator) 💰 Remuneração: R$ 15.263/mês"
        " *Robert Half 2026 ... Comenta aqui embaixo \"HOSTGATOR\" e eu te mando o link direto"
    )
    author = "Gabriel Vaz"
    author_url = "https://br.linkedin.com/in/vaz10k?trk=public_post_feed-actor-image"
    assert classify.post_verdict(text, author, author_url) == "aggregator_author"
    assert not classify.is_hiring_post(text, author, author_url)


@pytest.mark.parametrize("text", [
    # Full stack com PHP e JavaScript: uma menção, mas JavaScript não conta como outra linguagem.
    "Estamos contratando Desenvolvedor Full Stack Pleno, remoto. Stack: PHP e JavaScript.",
    # Duas menções na lista (PHP e Laravel): vale, como nas vagas de portais.
    "VAGA | DESENVOLVEDOR(A) FULL STACK SÊNIOR\nTrabalhar com Python, Flask, Django, PHP e "
    "Laravel. Contratação CLT.",
    # Recrutador abre o post se apresentando: não é "cargo que não é de engenharia".
    "Sou tech recruiter e estou contratando Desenvolvedor PHP Sênior, 100% remoto. "
    "Candidate-se: https://empresa.gupy.io/jobs/1",
    # Primeira linha com marketing, mas a vaga é de dev.
    "Time de marketing digital contratando Desenvolvedor WordPress Pleno!\nRequisitos: PHP, "
    "WordPress, CLT.",
])
def test_real_job_posts_still_pass(text):
    assert classify.is_hiring_post(text), classify.post_verdict(text)


# Post real em produção (24/11/2026), resumido: vaga PHP em Buenos Aires, em espanhol. O site
# é para Brasil e Portugal.
SPANISH_POST = """🚀 ¡DESDE Manage Resources BUSCAMOS DESARROLLADOR/A PHP SEMI SENIOR!
💻 ¿Te apasiona el desarrollo de software y estás buscando nuevos desafíos tecnológicos?
🛠️ PRINCIPALES RESPONSABILIDADES
▪️ Desarrollar y mantener sistemas y aplicaciones.
🔎 REQUISITOS EXCLUYENTES
▪️ Al menos 3 años de experiencia en posiciones similares, trabajando en empresas.
▪️ Conocimientos sólidos de PHP, MySQL, CSS, JavaScript y HTML.
📍 Modalidad: Híbrida. Ubicación: Belgrano, CABA.
📩 Envianos tu CV a: rh@example.com.ar"""


def test_spanish_post_is_rejected():
    assert classify.post_verdict(SPANISH_POST) == "post_spanish"
    assert not classify.is_hiring_post(SPANISH_POST)


@pytest.mark.parametrize("title,description", [
    ("Desarrollador PHP Semi Senior", None),
    ("Wordpress y PHP Developer", "Buscamos un desarrollador con experiencia en WordPress y "
     "PHP para nuestro equipo. Trabajo remoto desde cualquier país de LATAM."),
    ("Backend Developer Jr", "¡Sé parte de Stefanini! Responsabilidades y atribuciones: "
     "realizar las tareas de desarrollo con PHP y Laravel en el equipo de producto."),
])
def test_spanish_jobs_are_rejected(title, description):
    assert classify.job_verdict(title, description) == "spanish"
    assert not classify.is_relevant_job(title, description)


@pytest.mark.parametrize("text", [
    # Vaga brasileira que pede espanhol continua valendo.
    "Estamos contratando Desenvolvedor PHP Pleno, remoto. Requisitos: Laravel, MySQL e "
    "inglês básico. Espanhol será um diferencial. Candidate-se: https://empresa.gupy.io/jobs/1",
    # Vaga em inglês continua valendo.
    "We're hiring a Senior PHP Developer (Laravel) to join our team. Remote from LATAM, "
    "paid in USD. Apply here: https://example.com/jobs/1",
])
def test_portuguese_and_english_posts_still_pass(text):
    assert classify.is_hiring_post(text), classify.post_verdict(text)


def test_portuguese_job_asking_for_spanish_still_passes():
    assert classify.job_verdict(
        "Desenvolvedor (a) .NET PLENO | C# + PHP + IA",
        "Estamos em busca de uma pessoa Desenvolvedora para atuar em um projeto. O que "
        "buscamos? Conhecimentos em PHP para manutenção. Inglês básico | Espanhol será um "
        "diferencial.") in classify.JOB_OK
