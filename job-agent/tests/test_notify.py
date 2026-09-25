from jobagent import notify


def test_returns_false_when_smtp_not_configured(monkeypatch):
    for var in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_EMAIL_TO"]:
        monkeypatch.delenv(var, raising=False)

    assert notify.send_shortlist_email("body") is False


class FakeSMTP:
    sent = []

    def __init__(self, host, port):
        FakeSMTP.sent.append({"host": host, "port": port})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        FakeSMTP.sent[-1]["user"] = user
        FakeSMTP.sent[-1]["password"] = password

    def send_message(self, msg):
        FakeSMTP.sent[-1]["msg"] = msg


def test_sends_when_smtp_configured(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("NOTIFY_EMAIL_TO", "me@example.com")
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []

    result = notify.send_shortlist_email("here's the shortlist")

    assert result is True
    assert FakeSMTP.sent[0]["host"] == "smtp.example.com"
    assert FakeSMTP.sent[0]["msg"]["Subject"] == "Job Application Agent: today's shortlist"
