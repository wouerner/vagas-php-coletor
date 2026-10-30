"""Contrato com o site (web/, em PHP): o endereço das páginas de vaga, que o indexing
anuncia ao Google, e os dados de site_meta. Ver docs/contrato-base.md."""

import json
from pathlib import Path

import pytest

from vagas_php import indexing, php
from vagas_php.store import SOURCES, Store

CASES = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "job_paths.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda c: str(c["job"]["seq"]))
def test_job_path_matches_site(case):
    assert indexing.job_path(case["job"]) == case["path"]


class FakeStore(Store):
    """Store sem MySQL: grava o que publish_site_data mandaria para a base."""

    def __init__(self, rows):
        self.rows, self.meta, self.updates = rows, {}, []

    def execute(self, sql, args=()):
        assert sql.startswith("SELECT"), sql
        return self.rows

    def executemany(self, sql, rows):
        self.updates += list(rows)

    def tx(self):
        from contextlib import nullcontext
        return nullcontext()

    def set_meta(self, name, value):
        self.meta[name] = json.loads(json.dumps(value, ensure_ascii=False))


def test_refresh_derived_only_updates_what_changed():
    rows = [
        {"id": "a", "company": "XPTO LTDA", "company_key": "xpto", "author_headline": None, "author_recruiter": 0},
        {"id": "b", "company": "Acme S.A.", "company_key": None, "author_headline": "Tech Recruiter", "author_recruiter": 0},
        {"id": "c", "company": "Vaga confidencial", "company_key": "x", "author_headline": None, "author_recruiter": 0},
    ]
    store = FakeStore(rows)
    assert store.refresh_derived() == 2
    assert store.updates == [("acme", 1, "b"), (None, 0, "c")]


def test_site_meta_is_json_with_taxonomy_in_filter_order(monkeypatch):
    store = FakeStore([])
    monkeypatch.setattr(store, "rule_counts", lambda: {"php_title": 3})
    store.publish_site_data()
    tax = store.meta["taxonomy"]
    assert tax["stacks"][0] == "PHP" and "Laravel" in tax["stacks"]
    assert tax["workplaces"] == [label for label, _ in php.WORKPLACE]
    assert tax["seniorities"] == [label for label, _ in php.SENIORITY]
    assert tax["sources"] == list(SOURCES)
    assert {r["id"] for r in store.meta["rules"]} == {r["id"] for r in php.RULES}
    assert store.meta["rule_counts"] == {"php_title": 3}
