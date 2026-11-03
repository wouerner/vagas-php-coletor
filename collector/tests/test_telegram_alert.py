"""Rajadas no alerta do Telegram (telegram_alert.group_bursts): vagas da mesma empresa a até
12 h uma da outra viram uma mensagem só, como na listagem do site (web/src/Bursts.php)."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from vagas import telegram_alert

T0 = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc)


def job(id, company, minutes, title="Desenvolvedor PHP", location=None, source="linkedin"):
    """Vaga publicada `minutes` minutos antes de T0."""
    return {"id": id, "source": source, "title": title, "company": company,
            "location": location, "url": f"https://www.linkedin.com/jobs/view/{id}",
            "posted_at": (T0 - timedelta(minutes=minutes)).isoformat()}


def ids(groups):
    return [[j["id"] for j in g] for g in groups]


def bairesdev_burst():
    """Rajada como a da BairesDev em 03/11: uma vaga por cidade em 3 h 30, com o nome
    escrito de jeitos diferentes, e outra empresa no meio da lista."""
    cities = ["Curitiba", "São Paulo", "Recife", "Belo Horizonte", "Porto Alegre"]
    burst = [job(f"b{i}", "Bairesdev LLC" if i % 2 else "BairesDev", i * 50,
                 title=f"Desenvolvedor PHP {i}", location=c) for i, c in enumerate(cities)]
    return burst[:2] + [job("acme", "Acme", 70)] + burst[2:]


def test_bairesdev_burst_collapses_into_one_group():
    groups = telegram_alert.group_bursts(bairesdev_burst())
    assert ids(groups) == [["b0", "b1", "b2", "b3", "b4"], ["acme"]]
    text, included = telegram_alert.message_fit(groups[0])
    assert len(included) == 5
    assert text.startswith("🏢 <b>BairesDev</b> · 5 vagas publicadas em 3 h 20 min")
    assert text.count("🔗") == 5


def test_gap_over_12h_splits_the_company_in_two_groups():
    jobs = [job("new1", "BairesDev", 0), job("new2", "BairesDev", 60),
            # 12 h 01 min depois da anterior: outra rajada.
            job("old1", "BairesDev", 60 + 12 * 60 + 1), job("old2", "BairesDev", 60 + 13 * 60)]
    assert ids(telegram_alert.group_bursts(jobs)) == [["new1", "new2"], ["old1", "old2"]]
    # Exatamente 12 h ainda é a mesma rajada.
    jobs[2]["posted_at"] = (T0 - timedelta(minutes=60 + 12 * 60)).isoformat()
    assert ids(telegram_alert.group_bursts(jobs)) == [["new1", "new2", "old1", "old2"]]


def test_jobs_without_company_date_or_from_github_stay_standalone():
    no_company = [job("nc1", None, 0), job("nc2", "", 10)]
    no_date = [{**job("nd1", "Acme", 20), "posted_at": None},
               {**job("nd2", "Acme", 30), "posted_at": "ontem"},
               # first_seen não substitui posted_at.
               {**job("nd3", "Acme", 35), "posted_at": None, "first_seen": T0.isoformat()},
               {**job("nd4", "Acme", 36), "posted_at": None, "first_seen": T0.isoformat()}]
    github = [job("gh1", "Acme", 40, source="github"), job("gh2", "Acme", 50, source="github")]
    jobs = no_company + no_date + github
    assert ids(telegram_alert.group_bursts(jobs)) == [[j["id"]] for j in jobs]
    # Vaga sozinha sai no formato de sempre (format), sem cabeçalho de rajada.
    text, included = telegram_alert.message_fit([jobs[0]])
    assert text == telegram_alert.format(jobs[0]) and included == [jobs[0]]


@pytest.fixture
def alert(tmp_path, monkeypatch):
    """run() com a API e o Telegram falsos: devolve (data_dir, mensagens enviadas, respostas)."""
    sent, replies = [], []
    monkeypatch.setattr(telegram_alert, "VAGAS_TELEGRAM_TOKEN", "t")
    monkeypatch.setattr(telegram_alert, "VAGAS_TELEGRAM_CHAT_ID", "c")
    monkeypatch.setattr(telegram_alert, "fetch_jobs", bairesdev_burst)
    monkeypatch.setattr(telegram_alert.time, "sleep", lambda s: None)

    def send(token, chat_id, text):
        sent.append(text)
        return replies.pop(0) if replies else {"ok": True}
    monkeypatch.setattr(telegram_alert, "send", send)
    return tmp_path, sent, replies


def test_limit_caps_messages_and_state_gets_every_id_of_the_group(alert):
    data_dir, sent, _ = alert
    result = telegram_alert.run(data_dir, limit=1, force=True)
    assert len(sent) == 1 and result["messages"] == 1 and result["sent"] == 5
    assert telegram_alert.state_load(data_dir) == ["b0", "b1", "b2", "b3", "b4"]
    log = json.loads((data_dir / telegram_alert.LOG_FILE).read_text())
    assert [e["burst"] for e in log] == [5] * 5


def test_refused_group_is_not_recorded(alert):
    data_dir, sent, replies = alert
    # Sai primeiro o grupo mais antigo (Acme); a rajada é recusada e fica pendente.
    replies += [{"ok": True}, {"ok": False, "description": "Bad Request"}]
    result = telegram_alert.run(data_dir, limit=5, force=True)
    assert len(sent) == 2 and result["sent"] == 1
    assert telegram_alert.state_load(data_dir) == ["acme"]


def test_batch_puts_the_burst_in_one_block(alert):
    data_dir, sent, _ = alert
    result = telegram_alert.run(data_dir, force=True, batch=True)
    assert len(sent) == 1 and result["groups"] == 2 and result["sent"] == 6
    assert sent[0].count("🏢 <b>BairesDev</b> · 5 vagas") == 1
    assert sorted(telegram_alert.state_load(data_dir)) == ["acme", "b0", "b1", "b2", "b3", "b4"]
