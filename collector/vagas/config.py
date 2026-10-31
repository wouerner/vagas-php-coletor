"""Configuração dos coletores, por tenant (a linguagem: "php", "ruby"...): nome, termos que
identificam a linguagem, stack, o que buscar em cada fonte e quem é o dono do site. Fica
na base (tabela collector_config, um JSON por tenant e item): o mesmo código coleta vagas
de qualquer linguagem, trocando só a configuração. config_defaults.json tem os valores
iniciais de cada tenant, gravados na base na primeira subida (só os itens que faltam: o
que foi editado na base não é sobrescrito).

Um processo coleta um tenant só (VAGAS_TENANT, padrão "php"): o filtro (classify.py)
usa a configuração carregada. Quem abre a base (Store) carrega a do seu tenant com load();
sem base (testes), valem os valores iniciais do tenant. Variáveis de ambiente
(VAGAS_GUPY_TERMS, VAGAS_GITHUB_REPOS...) continuam valendo para o tenant padrão (php) e
têm prioridade sobre a base."""

import json
import os
from pathlib import Path

DEFAULTS_PATH = Path(__file__).with_name("config_defaults.json")
# tenant -> item -> valor
TENANT_DEFAULTS: dict[str, dict] = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
ITEMS = ("language", "core", "stack", "search", "self_author")
# Tenant das linhas de antes do multi-tenant e o único com site hoje (web/ mostra só ele).
DEFAULT_TENANT = "php"


def default_tenant() -> str:
    return (os.getenv("VAGAS_TENANT") or DEFAULT_TENANT).strip().lower()


def defaults(tenant: str) -> dict:
    """Valores iniciais de um tenant ({} se o arquivo não tem esse tenant)."""
    return TENANT_DEFAULTS.get(tenant, {})


tenant: str = default_tenant()
current: dict = dict(defaults(tenant))
_listeners = []


def on_load(fn):
    """Registra fn() para recalcular o que depende da configuração (ex.: regex do filtro)."""
    _listeners.append(fn)
    return fn


def load(values: dict, tenant_name: str | None = None) -> None:
    """Aplica a configuração de um tenant: a lida da base sobre os valores iniciais dele.
    Falta de item (tenant novo sem valores iniciais nem configuração na base) é erro: um
    tenant nunca herda os termos de outro."""
    global tenant
    name = tenant_name or tenant
    merged = {**defaults(name), **values}
    if missing := [item for item in ITEMS if item not in merged]:
        raise ValueError(f"tenant {name!r} sem configuração de {', '.join(missing)}: grave com "
                         f"python -m vagas config set NOME '<json>' ou em config_defaults.json")
    tenant = name
    current.clear()
    current.update(merged)
    for fn in _listeners:
        fn()


def get(name: str):
    return current[name]


def language() -> str:
    """Nome da linguagem das vagas ("PHP"), para textos e logs."""
    return current["language"]["name"]


def search(source: str, env: str) -> list[str]:
    """Termos de busca (ou repositórios, no GitHub) de uma fonte: a variável de ambiente
    `env` (separada por vírgula) se definida, senão a configuração do tenant. As variáveis
    (VAGAS_GUPY_TERMS...) são de antes do multi-tenant e valem só para o tenant padrão:
    nos outros, os termos de PHP de um .env compartilhado nunca entram."""
    raw = os.getenv(env) if tenant == DEFAULT_TENANT else None
    values = raw.split(",") if raw else current["search"].get(source, [])
    return [v.strip() for v in values if v.strip()]
