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


def test_lua_tenant_defaults():
    try:
        config.load({}, "lua")
        assert config.tenant == "lua"
        assert classify.is_relevant_job("Desenvolvedor Lua Sênior")
        assert classify.is_relevant_job("Backend Engineer (OpenResty)")
        assert classify.is_relevant_job("Roblox Developer")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Backend Engineer", "Go e Kubernetes. Scripts em Lua.")
        assert classify.is_relevant_job("Backend Engineer", "Lua no gateway. LuaJIT e OpenResty.")
        assert classify.details("Dev Lua", "LuaJIT, OpenResty e Nginx")["stack"] == "Lua,LuaJIT,OpenResty,Nginx"
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == ["jobs-lua"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")


def test_java_tenant_defaults():
    try:
        config.load({}, "java")
        assert config.tenant == "java"
        assert classify.is_relevant_job("Desenvolvedor Java Sênior")
        assert classify.is_relevant_job("Backend Developer (Spring Boot)")
        assert classify.is_relevant_job("Engenheiro de Software Quarkus")
        assert classify.is_relevant_job("Backend Engineer", "Micronaut e Hibernate. APIs em Jakarta EE.")
        # JavaScript não é Java.
        assert not classify.is_relevant_job("Desenvolvedor JavaScript Pleno")
        assert not classify.is_relevant_job("Desenvolvedor Java Script Pleno")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Frontend Engineer", "React e JavaScript. Backend em Java.")
        assert (classify.details("Dev Java", "Spring Boot, Spring Cloud, Hibernate e Jakarta EE")["stack"]
                == "Java,Spring Boot,Spring,Jakarta EE,Hibernate")
        assert classify.details("Dev JavaScript", "Node")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == [
            "jobs-java", "jobs-spring-boot", "jobs-spring", "jobs-hibernate"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "java", "spring boot", "spring", "quarkus", "micronaut", "jakarta ee", "hibernate"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")


def test_python_tenant_defaults():
    try:
        config.load({}, "python")
        assert config.tenant == "python"
        assert classify.is_relevant_job("Desenvolvedor Python Sênior")
        assert classify.is_relevant_job("Backend Developer (Django)")
        assert classify.is_relevant_job("Engenheiro de Software Python3/FastAPI")
        assert classify.is_relevant_job("Pessoa Desenvolvedora Fast API Pleno")
        assert classify.is_relevant_job("Backend Engineer", "APIs em Flask e Django, com Celery.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        # Python citado uma vez só, ou em vaga que não é de desenvolvimento, não entra.
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Scripts em Python.")
        assert not classify.is_relevant_job("Analista de Dados", "Python, pandas e SQL. Python avançado.")
        assert not classify.is_relevant_job("Analista de BI", "PySpark e Power BI.")
        assert (classify.details("Dev Python", "Django, Fast API, Celery, SQLAlchemy e pytest")["stack"]
                == "Python,Django,FastAPI,Celery,SQLAlchemy,Pytest")
        assert classify.details("Analista de BI", "PySpark")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == [
            "jobs-python", "jobs-django", "jobs-flask"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == ["python", "django", "flask", "fastapi"]
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Python Django")


def test_nodejs_tenant_defaults():
    try:
        config.load({}, "nodejs")
        assert config.tenant == "nodejs"
        assert classify.is_relevant_job("Desenvolvedor Node.js Sênior")
        assert classify.is_relevant_job("Pessoa Desenvolvedora NodeJS Pleno")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): "node-js" vira "node js".
        assert classify.is_relevant_job("desenvolvedor node js pleno")
        assert classify.is_relevant_job("Backend Developer (NestJS)")
        assert classify.is_relevant_job("Desenvolvedor Backend Node Pleno")
        assert classify.is_relevant_job("Full Stack Developer (Node + React)")
        assert classify.is_relevant_job("Backend Engineer", "APIs em Fastify e Express.js, com TypeScript.")
        # Front-end e JavaScript em geral não são Node.js.
        assert not classify.is_relevant_job("Desenvolvedor Front-end React")
        assert not classify.is_relevant_job("Desenvolvedor JavaScript Pleno")
        assert not classify.is_relevant_job("Desenvolvedor React Native", "React, TypeScript e Next.js.")
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Backend em Node.js.")
        # "node" sozinho é ambíguo: nó de Kubernetes, de rede, de blockchain.
        assert not classify.is_relevant_job("Kubernetes Node Administrator")
        assert not classify.is_relevant_job(
            "DevOps Engineer", "Cada worker node do cluster Kubernetes roda o node exporter. Node pools na AWS.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")
        assert (classify.details("Dev Node.js", "NestJS, Express, Fastify e TypeScript")["stack"]
                == "Node.js,Express,NestJS,Fastify,TypeScript")
        assert classify.details("Dev Backend Node", "AdonisJS e Koa")["stack"] == "Node.js,AdonisJS,Koa"
        assert classify.details("Dev React", "Cartão American Express")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES") == [
            "jobs-node-js", "jobs-nest-js", "jobs-express", "jobs-adonis-js", "jobs-koa"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "node.js", "nodejs", "node", "nestjs", "express.js", "fastify", "adonisjs"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith("Node.js")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor Node.js")


def test_dotnet_tenant_defaults():
    try:
        config.load({}, "dotnet")
        assert config.tenant == "dotnet"
        assert classify.is_relevant_job("Desenvolvedor .NET Sênior")
        assert classify.is_relevant_job("Desenvolvedor C# Pleno")
        assert classify.is_relevant_job("Pessoa Desenvolvedora C#/.NET")
        assert classify.is_relevant_job("Backend Developer (ASP.NET Core)")
        assert classify.is_relevant_job("Desenvolvedor Dotnet Júnior")
        assert classify.is_relevant_job("Programador VB.NET")
        # Título vindo do endereço da vaga (Programathor, Nerdin...): sem "#" nem ponto.
        assert classify.is_relevant_job("desenvolvedor c sharp pleno")
        assert classify.is_relevant_job("desenvolvedor net senior")
        assert classify.is_relevant_job("Backend Engineer", "APIs em ASP.NET Core com Entity Framework e Blazor.")
        # "\b" não casa em volta de "#" e ".": C e C++ não são C#, e ".net" de endereço não conta.
        assert not classify.is_relevant_job("Desenvolvedor C Embarcado")
        assert not classify.is_relevant_job("Desenvolvedor C++ Sênior")
        assert not classify.is_relevant_job("Analista de Redes", "Acesse empresa.net e www.provedor.net/vagas.")
        assert not classify.is_relevant_job("Analista de Marketing", "Net promoter score e internet.")
        assert not classify.is_relevant_job("Desenvolvedor PHP Laravel")
        assert not classify.is_relevant_job("Desenvolvedor Java Spring Boot")
        assert not classify.is_relevant_job("Frontend Engineer", "React e TypeScript. Backend em .NET.")
        assert (classify.details("Dev .NET", "C#, ASP.NET Core, Entity Framework e Blazor")["stack"]
                == ".NET,C#,ASP.NET,Blazor,Entity Framework")
        assert classify.details("Dev C Sharp", "Xamarin, .NET MAUI, WPF, F# e VB.NET")["stack"] == (
            ".NET,C#,MAUI,Xamarin,WPF,F#,VB.NET")
        assert classify.details("Dev C++", "Linux embarcado")["stack"] is None
        assert config.search("programathor", "VAGAS_PROGRAMATHOR_PAGES")[:3] == [
            "jobs-net", "jobs-c-sharp", "jobs-asp-net"]
        assert config.search("gupy", "VAGAS_GUPY_TERMS") == [
            "c#", ".net", "dotnet", "asp.net", "blazor", "entity framework"]
        assert config.search("github", "VAGAS_GITHUB_REPOS") == ["dotnetdevbr/vagas", "backend-br/vagas"]
        rules = {r["id"]: r for r in classify.RULES}
        assert rules["lang_title"]["title"].startswith(".NET")
    finally:
        config.load({}, "php")
    assert config.tenant == "php"
    assert classify.is_relevant_job("Desenvolvedor PHP Laravel")
    assert not classify.is_relevant_job("Desenvolvedor .NET")


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
