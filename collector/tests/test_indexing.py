"""Regras de indexing.publish sem rede e sem MySQL: SQLite em memória e publicador falso."""

import sqlite3
from datetime import timedelta

import pytest

from vagas import indexing

BASE = "https://vagasphp.wouerner.dev/vaga/"


class FakeStore:
    """O suficiente da Store para indexing: execute(sql, args) com "?"."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE indexing_log (url TEXT PRIMARY KEY, pushed_at TEXT, "
                        "status TEXT, detail TEXT)")

    def execute(self, sql, args=()):
        return self.db.execute(sql, args)

    def put(self, url, status, hours_ago):
        at = indexing._iso(indexing._now() - timedelta(hours=hours_ago))
        self.db.execute("INSERT INTO indexing_log VALUES (?, ?, ?, '')", (url, at, status))

    def rows(self):
        return dict(self.db.execute("SELECT url, status FROM indexing_log").fetchall())


class FakePublisher:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail or {}

    def __call__(self, url, type):
        self.calls.append(url)
        if url in self.fail:
            raise self.fail[url]


def urls(n):
    return [f"{BASE}{i}-dev-php" for i in range(1, n + 1)]


@pytest.fixture
def store():
    return FakeStore()


def test_sent_one_hour_ago_is_skipped(store):
    a, b = urls(2)
    store.put(a, "ok", 1)
    pub = FakePublisher()
    out = indexing.publish([a, b], store=store, publisher=pub)
    assert out["pulados"] == [a]
    assert out["enviados"] == [b] and pub.calls == [b]


def test_force_resends(store):
    (a,) = urls(1)
    store.put(a, "ok", 1)
    pub = FakePublisher()
    out = indexing.publish([a], force=True, store=store, publisher=pub)
    assert out["pulados"] == [] and out["enviados"] == [a] and pub.calls == [a]


def test_sent_over_24h_ago_is_sent_again(store):
    (a,) = urls(1)
    store.put(a, "ok", 25)
    out = indexing.publish([a], store=store, publisher=FakePublisher())
    assert out["enviados"] == [a]


def test_previous_failure_is_retried_and_not_counted(store):
    a, b = urls(2)
    store.put(a, "erro", 1)
    store.put(b, "sem_permissao", 1)
    pub = FakePublisher()
    out = indexing.publish([a, b], daily_cap=2, store=store, publisher=pub)
    assert pub.calls == [a, b] and out["pulados"] == []
    assert store.rows() == {a: "ok", b: "ok"}
    assert out["restante_hoje"] == 0


def test_daily_cap_cuts_batch(store):
    sent = urls(10)
    for u in sent[:8]:
        store.put(u, "ok", 2)
    new = [f"{BASE}novo-{i}" for i in range(5)]
    pub = FakePublisher()
    out = indexing.publish(sent[:8] + new, daily_cap=10, store=store, publisher=pub)
    assert pub.calls == new[:2]
    assert out["adiados"] == new[2:]
    assert out["restante_hoje"] == 0
    assert len(out["pulados"]) == 8


def test_daily_cap_reports_remaining(store):
    out = indexing.publish(urls(3), daily_cap=10, store=store, publisher=FakePublisher())
    assert out["restante_hoje"] == 7


def test_limit_cuts_batch(store):
    pub = FakePublisher()
    out = indexing.publish(urls(10), limit=3, store=store, publisher=pub)
    assert pub.calls == urls(3)
    assert out["adiados"] == urls(10)[3:]
    assert out["restante_hoje"] == indexing.DAILY_CAP - 3


def test_dry_run_writes_nothing(store):
    pub = FakePublisher()
    out = indexing.publish(urls(4), limit=2, dry_run=True, store=store, publisher=pub)
    assert out["dry_run"] is True and out["enviados"] == urls(2)
    assert pub.calls == [] and store.rows() == {}


def test_ownership_403_stops_and_is_not_sent(store):
    a, b, c = urls(3)
    err = indexing.OwnershipError("sem permissão no Search Console")
    pub = FakePublisher(fail={a: err})
    out = indexing.publish([a, b, c], store=store, publisher=pub)
    assert pub.calls == [a] and out["enviados"] == []
    assert out["falhas"][0]["url"] == a and "Search Console" in out["falhas"][0]["erro"]
    assert store.rows() == {a: "sem_permissao"}
    # não conta como enviada: a próxima execução tenta de novo
    assert indexing.publish([a], store=store, publisher=FakePublisher())["enviados"] == [a]


def test_quota_429_stops_batch_without_raising(store):
    a, b, c = urls(3)
    pub = FakePublisher(fail={b: indexing.QuotaError("HTTP 429: Quota exceeded")})
    out = indexing.publish([a, b, c], store=store, publisher=pub)
    assert pub.calls == [a, b]
    assert out["enviados"] == [a] and out["adiados"] == [c]
    assert out["restante_hoje"] == 0
    assert store.rows() == {a: "ok", b: "quota"}


def test_other_error_continues_batch(store):
    a, b = urls(2)
    pub = FakePublisher(fail={a: indexing.PublishError("HTTP 500: boom")})
    out = indexing.publish([a, b], store=store, publisher=pub)
    assert out["enviados"] == [b] and out["falhas"][0]["url"] == a


def test_no_credentials_warns_and_sends_nothing(store, monkeypatch, caplog):
    monkeypatch.delenv("VAGAS_INDEXING_SA_B64", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setattr(indexing, "_warned", False)
    out = indexing.publish(urls(2), store=store)
    assert out["enviados"] == [] and store.rows() == {}
    assert "sem credencial" in caplog.text


def test_invalid_credential_does_not_leak(store, monkeypatch, caplog):
    pytest.importorskip("google.oauth2")
    monkeypatch.setenv("VAGAS_INDEXING_SA_B64", "c2VncmVkby1zdXBlcg==")  # "segredo-super"
    monkeypatch.setattr(indexing, "_warned", False)
    assert indexing.credentials() is None
    assert "credencial inválida" in caplog.text and "segredo" not in caplog.text
