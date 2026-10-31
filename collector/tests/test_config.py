"""Configuração dos coletores (config.py): a linguagem e os termos vêm da base, e o mesmo
filtro vale para qualquer linguagem."""

import pytest

from vagas import classify, config

RUBY = {
    "language": {"name": "Ruby", "slug": "ruby", "examples": "Ruby, Rails ou Sinatra"},
    "core": r"\b(ruby|rails|sinatra)\b",
    "stack": [["Ruby", r"\bruby\b"], ["Rails", r"\brails\b"]],
}


@pytest.fixture
def ruby():
    config.load(RUBY)
    yield
    config.load({})


def test_defaults_are_php():
    assert classify.is_relevant_job("Desenvolvedor Laravel Pleno")
    assert not classify.is_relevant_job("Desenvolvedor Ruby on Rails")
    assert list(classify.STACK)[:3] == ["PHP", "Laravel", "Symfony"]


def test_language_comes_from_config(ruby):
    assert classify.is_relevant_job("Desenvolvedor Ruby on Rails")
    assert not classify.is_relevant_job("Desenvolvedor Laravel Pleno")
    assert classify.job_verdict("Desenvolvedor Laravel Pleno") == "no_lang"
    assert classify.details("Dev Rails Sênior", "Ruby 3")["stack"] == "Ruby,Rails"
    assert classify.is_hiring_post("Estamos contratando pessoa desenvolvedora Ruby, remoto")
    rules = {r["id"]: r for r in classify.RULES}
    assert rules["lang_title"]["title"].startswith("Ruby")
    assert rules["lang_title"]["patterns"] == [RUBY["core"]]


def test_missing_keys_keep_defaults(ruby):
    assert config.get("search") == config.DEFAULTS["search"]
    assert classify.SELF_AUTHOR == config.DEFAULTS["self_author"]


def test_env_overrides_search(monkeypatch):
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == config.DEFAULTS["search"]["gupy"]
    monkeypatch.setenv("VAGAS_GUPY_TERMS", " ruby , rails ,")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["ruby", "rails"]
    monkeypatch.setenv("VAGAS_GUPY_TERMS", "")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == config.DEFAULTS["search"]["gupy"]
