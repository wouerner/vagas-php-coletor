"""Níveis de confiança internos (site_meta trust_levels): Store e CLI `trust`, sem MySQL
e sem Playwright."""

import json
from contextlib import nullcontext

import pytest

from vagas import __main__ as cli
from vagas import classify
from vagas.store import (TRUST_META, Result, Store, trust_company_key,
                         trust_recruiter_key)


class FakeCursor:
    def __init__(self, rows):
        self.description = [("value",)] if rows is not None else None
        self._rows, self.lastrowid = rows or [], None

    def fetchall(self):
        return self._rows


class MetaStore(Store):
    """Store sem MySQL: site_meta num dict {(tenant, name): json}; get_meta e set_meta
    (os de verdade) passam pelo SQL abaixo."""

    def __init__(self, tenant="php"):
        self.tenant, self.site_meta = tenant, {}

    def execute(self, sql, args=()):
        if sql.startswith("SELECT value FROM site_meta"):
            value = self.site_meta.get(tuple(args))
            return Result(FakeCursor([(value,)] if value is not None else []))
        if sql.startswith("REPLACE INTO site_meta"):
            tenant, name, value, _updated_at = args
            self.site_meta[(tenant, name)] = value
            return Result(FakeCursor(None))
        raise AssertionError(sql)

    def tx(self):
        return nullcontext()


def test_trust_levels_are_stored_in_site_meta_and_round_trip():
    store = MetaStore()
    assert store.get_trust_levels() == {"companies": {}, "recruiters": {}}

    key = store.set_trust_level("companies", "Acme LTDA", "confiante", reason="pagou em dia")
    store.set_trust_level("recruiters", "Maria Silva", "desconfiado", reason="vaga fantasma",
                          source="telegram", author_url="https://www.linkedin.com/in/maria/")

    raw = json.loads(store.site_meta[("php", TRUST_META)])
    assert set(raw) == {"companies", "recruiters"}
    entry = raw["companies"][key]
    assert set(entry) == {"level", "reason", "updated_at", "source"}
    assert entry["level"] == "confiante" and entry["reason"] == "pagou em dia"
    assert entry["source"] == "manual" and entry["updated_at"]

    levels = store.get_trust_levels()
    assert levels["companies"][key]["level"] == "confiante"
    rec = levels["recruiters"]["https://www.linkedin.com/in/maria"]
    assert rec["level"] == "desconfiado" and rec["source"] == "telegram"

    # Regravar troca a entrada, não duplica.
    store.set_trust_level("companies", "ACME", "neutro")
    assert store.get_trust_levels()["companies"] == {key: store.get_trust_levels()["companies"][key]}
    assert store.get_trust_levels()["companies"][key]["level"] == "neutro"


def test_list_is_in_stable_order_and_tenant_scoped():
    store = MetaStore()
    store.set_trust_level("recruiters", "Zeca", "neutro")
    store.set_trust_level("companies", "Zeta", "neutro")
    store.set_trust_level("recruiters", "Ana", "confiante")
    store.set_trust_level("companies", "Alfa", "desconfiado")
    assert [(e["namespace"], e["key"]) for e in store.list_trust_levels()] == [
        ("companies", "alfa"), ("companies", "zeta"), ("recruiters", "ana"), ("recruiters", "zeca")]
    assert [e["key"] for e in store.list_trust_levels("recruiters")] == ["ana", "zeca"]
    assert all(name == TRUST_META and tenant == "php" for tenant, name in store.site_meta)


def test_set_rejects_invalid_level_namespace_and_empty_name():
    store = MetaStore()
    with pytest.raises(ValueError):
        store.set_trust_level("companies", "Acme", "talvez")
    with pytest.raises(ValueError):
        store.set_trust_level("empresas", "Acme", "neutro")
    with pytest.raises(ValueError):
        store.set_trust_level("recruiters", "  ", "neutro")
    assert store.site_meta == {}


def test_company_key_prefers_classify_company_key():
    assert trust_company_key("Acme Tecnologia LTDA") == classify.company_key("Acme Tecnologia LTDA")
    assert trust_company_key("Acme S.A.") == trust_company_key("ACME") == "acme"


def test_company_key_falls_back_to_normalized_name():
    # Nomes que não identificam o empregador não têm company_key.
    name = "  Vaga   Confidencial "
    assert classify.company_key(name) is None
    assert trust_company_key(name) == "vaga confidencial"
    assert trust_company_key(None) is None and trust_company_key("") is None


def test_recruiter_key_prefers_author_url():
    url = "https://www.linkedin.com/in/maria-silva"
    assert trust_recruiter_key("Maria Silva", url) == url
    assert trust_recruiter_key("Outro Nome", f" {url}/ ") == url


def test_recruiter_key_falls_back_to_normalized_author():
    assert trust_recruiter_key("  Maria   Silva ") == "maria silva"
    assert trust_recruiter_key("João Ninguém", "") == "joao ninguem"
    assert trust_recruiter_key(None, None) is None


def test_publish_site_data_leaves_trust_levels_untouched(monkeypatch):
    store = MetaStore()
    store.set_trust_level("companies", "Acme", "confiante")
    before = store.site_meta[("php", TRUST_META)]
    written = []
    monkeypatch.setattr(store, "refresh_derived", lambda: 0)
    monkeypatch.setattr(store, "rule_counts", lambda: {})
    monkeypatch.setattr(store, "set_meta", lambda name, value: written.append(name))
    store.publish_site_data()
    assert TRUST_META not in written
    assert store.site_meta[("php", TRUST_META)] == before


def run_cli(monkeypatch, store, *argv):
    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(cli, "Store", lambda tenant=None: store)
    monkeypatch.setattr("sys.argv", ["vagas", *argv])
    return cli.main()


def test_cli_set_and_list_show_both_namespaces(monkeypatch, capsys):
    store = MetaStore()
    assert run_cli(monkeypatch, store, "trust", "set", "empresa", "Acme LTDA", "confiante",
                   "--motivo", "pagou em dia") == 0
    assert run_cli(monkeypatch, store, "trust", "set", "recrutador", "Maria Silva",
                   "desconfiado", "--url", "https://www.linkedin.com/in/maria") == 0
    capsys.readouterr()

    assert run_cli(monkeypatch, store, "trust", "list") == 0
    out = capsys.readouterr().out
    assert "[companies]" in out and "[recruiters]" in out
    assert out.index("[companies]") < out.index("[recruiters]")
    assert "acme: confiante" in out and "pagou em dia" in out
    assert "https://www.linkedin.com/in/maria: desconfiado" in out


def test_cli_list_empty_and_filtered(monkeypatch, capsys):
    store = MetaStore()
    assert run_cli(monkeypatch, store, "trust", "list") == 0
    out = capsys.readouterr().out
    assert "[companies]\n  (nenhum)" in out and "[recruiters]\n  (nenhum)" in out
    assert run_cli(monkeypatch, store, "trust", "list", "--tipo", "recrutador") == 0
    out = capsys.readouterr().out
    assert "[recruiters]" in out and "[companies]" not in out


def test_cli_module_does_not_import_collect_or_playwright():
    # Processo limpo: outros testes podem ter importado esses módulos neste.
    import subprocess
    import sys
    from pathlib import Path
    code = ("import sys, vagas.__main__; "
            "bad = [m for m in ('vagas.collect', 'vagas.migrate_sqlite', 'vagas.bot', "
            "'playwright') if m in sys.modules]; print(bad); sys.exit(1 if bad else 0)")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          cwd=Path(__file__).resolve().parents[1])
    assert done.returncode == 0, done.stdout + done.stderr
