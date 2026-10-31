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
