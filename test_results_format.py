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
    setattr(fake, "PushDeer", DummyPushDeer)
    monkeypatch.setitem(sys.modules, "pypushdeer", fake)
    sys.modules.pop("checkin", None)
    return importlib.import_module("checkin")


def test_format_results_outputs_one_row_per_cookie_with_requested_summary(monkeypatch):
    checkin = load_checkin(monkeypatch)
    config = types.SimpleNamespace(verbose=False, cookies_list=["a", "b", "c"])
    checker = checkin.Checker(config)
    checker.results = [
        checkin.CheckinResult(
            cookie_index=1,
            domain="glados.cloud",
            account="wildpunchiang724@gmail.com",
            status="签到失败",
            points="0",
            days="30 天",
            points_total="30 积分",
            code=checkin.CheckinStatus.FAILURE,
        ),
        checkin.CheckinResult(
            cookie_index=2,
            domain="glados.cloud",
            account="404coldboy@gmail.com",
            status="签到成功",
            points="5",
            days="14 天",
            points_total="112 积分",
            code=checkin.CheckinStatus.SUCCESS,
        ),
        checkin.CheckinResult(
            cookie_index=3,
            domain="railgun.info",
            account="buwenjiang724@gmail.com",
            status="已签到",
            points="0",
            days="14 天",
            points_total="89 积分",
            code=checkin.CheckinStatus.REPEAT,
        ),
        # Same cookie on the fallback domain must not create an extra notification row.
        checkin.CheckinResult(
            cookie_index=3,
            domain="glados.cloud",
            account="buwenjiang724@gmail.com",
            status="签到失败",
            points="0",
            days="None 天",
            points_total="None 积分",
            code=checkin.CheckinStatus.FAILURE,
        ),
    ]

    title, content, log_content = checker.format_results()

    assert title == "GLaDOS 签到完成 ✅1 ❌1 🔁1"
    assert content == "\n".join(
        [
            "1. wildpunchiang724@gmail.com | ❌ 签到失败 | P:- | 剩余积分:30 | 剩余:30 天",
            "2. 404coldboy@gmail.com | ✅ 签到成功 | P:5 | 剩余积分:112 | 剩余:14 天",
            "3. buwenjiang724@gmail.com | 🔁 已签到 | P:- | 剩余积分:89 | 剩余:14 天",
        ]
    )
    assert log_content == content


def test_checkin_all_keeps_one_final_result_per_cookie_and_stops_after_repeat(monkeypatch):
    checkin = load_checkin(monkeypatch)
    config = types.SimpleNamespace(
        verbose=False,
        cookies_list=["cookie-one", "cookie-two"],
        DOMAINS=["glados.cloud", "railgun.info"],
        EXCHANGE_PLANS={"plan500": 500},
        exchange_plan="plan500",
    )
    calls = []

    def fake_checkin_on_domain(self, cookie, cookie_idx, domain):
        calls.append((cookie_idx, domain))
        if cookie_idx == 1 and domain == "glados.cloud":
            return checkin.CheckinResult(
                cookie_index=1,
                domain=domain,
                account="one@example.com",
                status="签到失败",
                code=checkin.CheckinStatus.FAILURE,
            )
        if cookie_idx == 1 and domain == "railgun.info":
            return checkin.CheckinResult(
                cookie_index=1,
                domain=domain,
                account="one@example.com",
                status="签到成功",
                points="3",
                days="20 天",
                code=checkin.CheckinStatus.SUCCESS,
            )
        return checkin.CheckinResult(
            cookie_index=2,
            domain=domain,
            account="two@example.com",
            status="已签到",
            points="0",
            days="9 天",
            code=checkin.CheckinStatus.REPEAT,
        )

    monkeypatch.setattr(checkin.Checker, "_checkin_on_domain", fake_checkin_on_domain)

    checker = checkin.Checker(config)
    checker.checkin_all()

    assert calls == [(1, "glados.cloud"), (1, "railgun.info"), (2, "glados.cloud")]
    assert len(checker.results) == 2
    assert [result.code for result in checker.results] == [checkin.CheckinStatus.SUCCESS, checkin.CheckinStatus.REPEAT]


def test_config_extracts_email_from_raw_cookie(monkeypatch):
    monkeypatch.setenv("GLADOS_COOKIES", "koa:sess={\"email\":\"bird@example.com\"}")
    checkin = load_checkin(monkeypatch)

    config = checkin.Config()

    assert config.account_names == ["bird@example.com"]


def test_config_still_loads_verbose_env(monkeypatch):
    monkeypatch.setenv("GLADOS_COOKIES", "koa:sess=dummy")
    monkeypatch.setenv("GLADOS_VERBOSE", "true")
    checkin = load_checkin(monkeypatch)

    config = checkin.Config()

    assert config.verbose is True


def test_checkin_on_domain_uses_status_email_and_total_points(monkeypatch):
    checkin = load_checkin(monkeypatch)
    config = types.SimpleNamespace(verbose=False, EXCHANGE_PLANS={"plan500": 500}, exchange_plan="plan500")

    class FakeAPI:
        def __init__(self, domain, cookie_index, verbose=False):
            self.domain = domain
            self.cookie_index = cookie_index
            self.verbose = verbose

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_status(self, cookie):
            return "28 天", 0, "from-status@example.com"

        def checkin(self, cookie):
            return {"status": "签到成功", "points": "5", "code": checkin.CheckinStatus.SUCCESS}

        def get_points(self, cookie):
            return "123 积分", 123

        def exchange(self, cookie, plan, required_points):
            return "兑换失败: 积分不足"

    monkeypatch.setattr(checkin, "API", FakeAPI)

    result = checkin.Checker(config)._checkin_on_domain("cookie", 1, "glados.cloud")

    assert result.account == "from-status@example.com"
    assert result.points_total == "123 积分"
