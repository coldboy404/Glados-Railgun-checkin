import importlib
import sys
import types


class DummyPushDeer:
    def __init__(self, pushkey=None):
        self.pushkey = pushkey

    def send_text(self, title, desp=""):
        return None


def load_checkin(monkeypatch):
    fake = types.ModuleType("pypushdeer")
    fake.PushDeer = DummyPushDeer
    monkeypatch.setitem(sys.modules, "pypushdeer", fake)
    sys.modules.pop("checkin", None)
    return importlib.import_module("checkin")


def test_config_loads_telegram_secrets(monkeypatch):
    monkeypatch.setenv("TG_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TG_CHAT_ID", "456")
    monkeypatch.setenv("GLADOS_COOKIES", "koa:sess=a; koa:sess.sig=b")
    checkin = load_checkin(monkeypatch)

    config = checkin.Config()

    assert config.tg_bot_token == "123:abc"
    assert config.tg_chat_id == "456"


def test_push_service_sends_telegram_when_configured(monkeypatch):
    checkin = load_checkin(monkeypatch)
    config = types.SimpleNamespace(
        push_key="",
        tg_bot_token="123:abc",
        tg_chat_id="456",
    )
    calls = []

    class Response:
        status_code = 200
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return Response()

    monkeypatch.setattr(checkin.requests, "post", fake_post)

    assert checkin.PushService(config).send("标题", "内容") is True
    assert calls == [
        (
            "https://api.telegram.org/bot123:abc/sendMessage",
            {"chat_id": "456", "text": "标题\n\n内容"},
            10,
        )
    ]
