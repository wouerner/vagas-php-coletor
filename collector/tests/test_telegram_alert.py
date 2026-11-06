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
    assert text.startswith("BairesDev · 5 vagas · 3 h 20 min")
    assert text.count("linkedin.com/jobs") == 5


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
    assert sent[0].count("BairesDev · 5 vagas") == 1
    assert sorted(telegram_alert.state_load(data_dir)) == ["acme", "b0", "b1", "b2", "b3", "b4"]


# Texto enxuto: sem rótulos com emoji e sem repetir "PHP" (o canal já é de PHP).

def test_single_job_message_is_compact():
    j = {**job("123", "Acme", 0, title="Dev Backend"), "location": "São Paulo, SP",
         "workplace": "Remoto", "seniority": "Pleno", "contract": "CLT",
         "stack": "PHP, Laravel, MySQL"}
    link = telegram_alert.out_link(j).replace("&", "&amp;")
    assert telegram_alert.format(j) == (
        "<b>Dev Backend</b>\n"
        "Acme · São Paulo, SP · Remoto · Pleno · CLT · Laravel, MySQL\n"
        f'<a href="{link}">abrir</a>')

def test_single_job_message_skips_empty_fields_and_php_only_stack():
    j = {**job("9", None, 0, title="Dev PHP"), "stack": "php"}
    text = telegram_alert.format(j)
    assert text.splitlines()[0] == "<b>Dev PHP</b>"
    assert len(text.splitlines()) == 2 and text.splitlines()[1].startswith("<a href=")


def test_digest_header_is_short_and_generic(monkeypatch):
    at_brasilia(monkeypatch, 2026, 11, 4)
    text = telegram_alert.format_digest([job("acme", "Acme", 0)])
    head = text.split("\n\n")[0]
    assert head == "<b>Novas vagas</b> · 04/11"
    assert "PHP" not in head and "🐘" not in text


# Rodapé de encorajamento: uma frase por dia, no fim de UMA mensagem de vagas.

def at_brasilia(monkeypatch, year, month, day, hour=10):
    """Fixa o relógio do módulo em `day` às `hour` h de Brasília."""
    now = datetime(year, month, day, hour, tzinfo=telegram_alert.dates.BRASILIA)
    monkeypatch.setattr(telegram_alert.dates, "now_utc",
                        lambda: now.astimezone(timezone.utc))


def footers(messages):
    return [m for m in messages if any(p in m for p in telegram_alert.ENCOURAGEMENTS)]


def test_encouragement_rotates_by_day_and_is_deterministic():
    days = [T0.date() + timedelta(days=i) for i in range(6)]
    phrases = [telegram_alert.encouragement(d) for d in days]
    assert phrases == [telegram_alert.encouragement(d) for d in days]  # mesma data, mesma frase
    assert all(a != b for a, b in zip(phrases, phrases[1:]))  # dias seguidos trocam
    assert set(phrases) == set(telegram_alert.ENCOURAGEMENTS)
    assert all("PHP" not in phrase for phrase in phrases)


def test_footer_goes_on_one_message_at_the_very_end(alert, monkeypatch):
    data_dir, sent, _ = alert
    at_brasilia(monkeypatch, 2026, 11, 4)
    plain = [telegram_alert.message_fit(g)[0]
             for g in reversed(telegram_alert.group_bursts(bairesdev_burst()))]
    telegram_alert.run(data_dir, limit=5, force=True)
    assert len(sent) == 2 and len(footers(sent)) == 1
    phrase = telegram_alert.encouragement(telegram_alert.today_brasilia())
    # Só a 1ª mensagem do dia leva o rodapé, no fim, e o resto do texto fica igual.
    assert sent[0] == f"{plain[0]}\n\n<i>{phrase}</i>"
    assert sent[1] == plain[1]
    state = json.loads((data_dir / telegram_alert.ENCOURAGEMENT_STATE_FILE).read_text())
    assert state["date"] == "2026-11-04"


def test_footer_only_once_per_day_across_runs(alert, monkeypatch):
    data_dir, sent, _ = alert
    at_brasilia(monkeypatch, 2026, 11, 4, hour=9)
    telegram_alert.run(data_dir, limit=1, force=True)  # rajada da BairesDev, com rodapé
    at_brasilia(monkeypatch, 2026, 11, 4, hour=15)
    telegram_alert.run(data_dir, limit=1, force=True)  # Acme, mesmo dia: sem rodapé
    assert len(sent) == 2 and footers(sent) == [sent[0]]
    # No dia seguinte volta, com outra frase.
    (data_dir / telegram_alert.STATE_FILE).unlink()
    (data_dir / telegram_alert.LOG_FILE).unlink()
    at_brasilia(monkeypatch, 2026, 11, 5, hour=9)
    telegram_alert.run(data_dir, limit=1, force=True)
    assert footers(sent) == [sent[0], sent[2]]
    assert sent[2].endswith(f"<i>{telegram_alert.encouragement(T0.date() + timedelta(days=2))}</i>")
    assert telegram_alert.encouragement(T0.date() + timedelta(days=1)) in sent[0]


def test_refused_message_does_not_spend_the_footer(alert, monkeypatch):
    data_dir, sent, replies = alert
    at_brasilia(monkeypatch, 2026, 11, 4)
    replies += [{"ok": False, "description": "Bad Request"}]
    telegram_alert.run(data_dir, limit=5, force=True)
    assert len(sent) == 1 and footers(sent) == sent
    assert not (data_dir / telegram_alert.ENCOURAGEMENT_STATE_FILE).exists()
    telegram_alert.run(data_dir, limit=5, force=True)  # tenta de novo: rodapé na 1ª aceita
    assert len(sent) == 3 and footers(sent[1:]) == [sent[1]]


def test_dry_run_shows_footer_once_and_records_nothing(alert, monkeypatch, capsys):
    data_dir, sent, _ = alert
    at_brasilia(monkeypatch, 2026, 11, 4)
    telegram_alert.run(data_dir, limit=5, force=True, dry_run=True)
    phrase = telegram_alert.encouragement(telegram_alert.today_brasilia())
    assert capsys.readouterr().out.count(phrase) == 1 and not sent
    assert not (data_dir / telegram_alert.ENCOURAGEMENT_STATE_FILE).exists()


def test_batch_gets_footer_at_the_end_once_per_day(alert, monkeypatch):
    data_dir, sent, _ = alert
    at_brasilia(monkeypatch, 2026, 11, 4)
    plain = telegram_alert.format_digest(bairesdev_burst())
    telegram_alert.run(data_dir, force=True, batch=True)
    phrase = telegram_alert.encouragement(telegram_alert.today_brasilia())
    assert sent == [f"{plain}\n\n<i>{phrase}</i>"]
    # Outra execução no mesmo dia, com vagas novas: sai sem rodapé.
    (data_dir / telegram_alert.STATE_FILE).unlink()
    (data_dir / telegram_alert.LOG_FILE).unlink()
    telegram_alert.run(data_dir, force=True, batch=True)
    assert len(sent) == 2 and sent[1] == plain


def test_footer_is_skipped_when_it_does_not_fit():
    assert telegram_alert.with_encouragement("x" * telegram_alert.MESSAGE_MAX,
                                             T0.date()) is None
