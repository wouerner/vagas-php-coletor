"""Configuração dos coletores: a linguagem (nome, termos que a identificam, stack), o que
buscar em cada fonte e quem é o dono do site. Fica na base (tabela collector_config, um
JSON por chave): o mesmo código coleta vagas de qualquer linguagem, trocando só a
configuração. config_defaults.json tem os valores iniciais, gravados na base na primeira
subida (só as chaves que faltam: o que foi editado na base não é sobrescrito).

Quem abre a base (Store) carrega a configuração dela com load(); sem base (testes), valem
os valores iniciais. Variáveis de ambiente (VAGAS_GUPY_TERMS, VAGAS_GITHUB_REPOS...)
continuam valendo e têm prioridade sobre a base."""

import json
import os
from pathlib import Path

DEFAULTS_PATH = Path(__file__).with_name("config_defaults.json")
DEFAULTS: dict = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))

current: dict = dict(DEFAULTS)
_listeners = []


def on_load(fn):
    """Registra fn() para recalcular o que depende da configuração (ex.: regex do filtro)."""
    _listeners.append(fn)
    return fn


def load(values: dict) -> None:
    """Aplica a configuração lida da base (chaves que faltam ficam com o valor inicial)."""
    current.clear()
    current.update(DEFAULTS)
    current.update(values)
    for fn in _listeners:
        fn()


def get(name: str):
    return current[name]


def language() -> str:
    """Nome da linguagem das vagas ("PHP"), para textos e logs."""
    return current["language"]["name"]


def search(source: str, env: str) -> list[str]:
    """Termos de busca (ou repositórios, no GitHub) de uma fonte: a variável de ambiente
    `env` (separada por vírgula) se definida, senão a configuração da base."""
    raw = os.getenv(env)
    values = raw.split(",") if raw else current["search"].get(source, [])
    return [v.strip() for v in values if v.strip()]
