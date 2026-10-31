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
    assert config.get("search") == config.defaults("php")["search"]
    assert classify.SELF_AUTHOR == config.defaults("php")["self_author"]


def test_env_overrides_search(monkeypatch):
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == config.defaults("php")["search"]["gupy"]
    monkeypatch.setenv("VAGAS_GUPY_TERMS", " ruby , rails ,")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["ruby", "rails"]
    monkeypatch.setenv("VAGAS_GUPY_TERMS", "")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == config.defaults("php")["search"]["gupy"]


def test_ruby_tenant_defaults():
    try:
        config.load({}, "ruby")
        assert config.tenant == "ruby"
        assert classify.is_relevant_job("Pessoa Desenvolvedora Ruby on Rails Sênior")
        assert classify.is_relevant_job("Backend Developer (Rails)")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        # "Ruby on Rails" é uma menção só: uma vez na descrição não basta.
        assert not classify.is_relevant_job("Backend Engineer", "Kotlin. Familiarity with Ruby on Rails.")
        assert classify.is_relevant_job("Backend Engineer", "Ruby on Rails. Testes em Ruby.")
        assert classify.details("Dev Rails", "Ruby, Sidekiq e RSpec")["stack"] == "Ruby,Rails,Sidekiq,RSpec"
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == ["jobs-ruby", "jobs-ruby-on-rails"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")


def test_unknown_tenant_never_inherits_another():
    with pytest.raises(ValueError, match="sem configuração"):
        config.load({"language": RUBY["language"]}, "elixir")
    assert config.tenant == "php"  # a configuração anterior continua valendo
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")


def test_env_terms_only_for_default_tenant(monkeypatch):
    monkeypatch.setenv("VAGAS_GUPY_TERMS", "php,laravel")
    try:
        config.load({}, "ruby")
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["ruby", "rails"]
    finally:
        config.load({}, "php")
    assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["php", "laravel"]
