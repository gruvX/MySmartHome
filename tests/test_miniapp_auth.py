"""Unit tests for the Telegram Mini App backend (``miniapp_auth`` component).

These tests exercise the security-critical paths of
``custom_components/miniapp_auth/__init__.py`` WITHOUT touching Home Assistant,
Telegram, or any network:

* ``aiohttp`` / ``homeassistant`` are stubbed in ``sys.modules`` before the
  component is imported (neither is installed on the runner, and importing the
  real HA package would be heavy and network-adjacent).
* A fake ``hass`` (states + services) and a fake aiohttp request are used to
  drive the view coroutines directly.

Covered: HMAC valid/invalid, wrong UID, stale/future ``auth_date``, malformed
JSON, oversized body, bad/out-of-range climate temperature, action allow-list
enforcement, calendar allow-list, optional replay rejection, and rate limiting.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib.util
import json
import sys
import time
import types
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COMPONENT = REPO / "custom_components" / "miniapp_auth" / "__init__.py"

BOT_TOKEN = "123456:TEST-BOT-TOKEN"
UID = 100000000  # matches the component's default ALLOWED_UID


# --------------------------------------------------------------------------- #
# Stub the heavy third-party imports the component makes at module load time.
# --------------------------------------------------------------------------- #
def _install_stubs() -> None:
    if "aiohttp" not in sys.modules:
        aiohttp = types.ModuleType("aiohttp")
        web = types.ModuleType("aiohttp.web")

        class Response:
            def __init__(self, text="", status=200, content_type="application/json", **_):
                self.text = text
                self.status = status
                self.content_type = content_type

            def json(self):
                return json.loads(self.text)

        class Request:  # only used as a type annotation target
            pass

        web.Response = Response
        web.Request = Request
        aiohttp.web = web
        sys.modules["aiohttp"] = aiohttp
        sys.modules["aiohttp.web"] = web

    if "homeassistant" not in sys.modules:
        ha = types.ModuleType("homeassistant")
        ha_comp = types.ModuleType("homeassistant.components")
        ha_http = types.ModuleType("homeassistant.components.http")
        ha_core = types.ModuleType("homeassistant.core")

        class HomeAssistantView:
            url = ""
            name = ""
            requires_auth = True
            cors_allowed = False

        class HomeAssistant:
            pass

        class Context:
            """Дубль homeassistant.core.Context: компонент подписывает вызовы
            сервисов id владельца, чтобы HA видел человека, а не автоматику."""

            def __init__(self, user_id=None, parent_id=None, id=None):
                self.user_id = user_id
                self.parent_id = parent_id
                self.id = id

        ha_http.HomeAssistantView = HomeAssistantView
        ha_core.HomeAssistant = HomeAssistant
        ha_core.Context = Context
        ha.components = ha_comp
        ha_comp.http = ha_http
        sys.modules["homeassistant"] = ha
        sys.modules["homeassistant.components"] = ha_comp
        sys.modules["homeassistant.components.http"] = ha_http
        sys.modules["homeassistant.core"] = ha_core


def _load_component():
    # BOT_TOKEN is captured at import time; set it (and keep other config on the
    # tightened defaults) via env before loading.
    import os

    os.environ["TELEGRAM_BOT_TOKEN"] = BOT_TOKEN
    os.environ.setdefault("TELEGRAM_ALLOWED_UID", str(UID))
    # Make sure project_secrets (repo root) is importable by the component.
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    _install_stubs()
    spec = importlib.util.spec_from_file_location("miniapp_auth_under_test", COMPONENT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_component()


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeState:
    def __init__(self, entity_id, state="on", attributes=None):
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}
        self.last_changed = datetime(2026, 7, 15, tzinfo=timezone.utc)
        self.last_updated = datetime(2026, 7, 15, tzinfo=timezone.utc)


class FakeStates:
    def __init__(self, entities=None):
        self._d = {s.entity_id: s for s in (entities or [])}

    def get(self, entity_id):
        return self._d.get(entity_id)

    def async_all(self):
        return list(self._d.values())


class FakeServices:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.contexts = []
        self._response = response
        self._error = error

    async def async_call(self, domain, service, data=None, blocking=False,
                         return_response=False, context=None):
        self.contexts.append(context)
        self.calls.append((domain, service, dict(data or {}), blocking, return_response))
        if self._error is not None:
            raise self._error
        if return_response:
            return self._response
        return None


class FakeHass:
    def __init__(self, entities=None, cal_response=None, service_error=None):
        self.states = FakeStates(entities)
        self.services = FakeServices(cal_response, service_error)
        # Records every blocking callable the code offloads off the event loop.
        self.executor_calls = []

    async def async_add_executor_job(self, func, *args):
        """Stand-in for HA's executor offload: runs ``func`` synchronously but
        records that it was offloaded, so tests can assert blocking I/O is not
        run inline on the event loop."""
        self.executor_calls.append((getattr(func, "__name__", repr(func)), args))
        return func(*args)


class FakeRequest:
    def __init__(self, body, content_length=None, remote="1.2.3.4", raise_read=False):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        self._raw = body.encode("utf-8") if isinstance(body, str) else bytes(body)
        self.content_length = len(self._raw) if content_length is None else content_length
        self.remote = remote
        self._raise = raise_read

    async def read(self):
        if self._raise:
            raise RuntimeError("boom")
        return self._raw


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def make_init_data(
    *,
    bot_token=BOT_TOKEN,
    user_id=UID,
    auth_date=None,
    tamper=False,
    user_json=None,
):
    if auth_date is None:
        auth_date = int(time.time())
    if user_json is None:
        user_json = json.dumps({"id": user_id, "first_name": "owner"})
    params = {"auth_date": str(auth_date), "user": user_json, "query_id": "AAA"}
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    if tamper:
        h = ("0" * len(h)) if h[0] != "0" else ("1" * len(h))
    params["hash"] = h
    return urllib.parse.urlencode(params)


def run(coro):
    return asyncio.run(coro)


def body(init_data="", **kw):
    d = {"initData": init_data}
    d.update(kw)
    return d


@pytest.fixture(autouse=True)
def _reset_component_state():
    """Isolate rate-limiter / replay state and config between tests."""
    mod._RATE.reset()
    mod._SEEN.clear()
    saved = (mod.REJECT_REPLAY, mod._RATE.capacity, mod._RATE.refill)
    mod.REJECT_REPLAY = False
    mod._RATE.capacity = 10_000.0  # effectively unlimited for functional tests
    mod._RATE.refill = 10_000.0
    yield
    mod.REJECT_REPLAY, mod._RATE.capacity, mod._RATE.refill = saved
    mod._RATE.reset()
    mod._SEEN.clear()


# --------------------------------------------------------------------------- #
# _validate: HMAC + UID + freshness
# --------------------------------------------------------------------------- #
def test_validate_accepts_valid_signature():
    user = mod._validate(make_init_data())
    assert user is not None and user["id"] == UID


def test_validate_rejects_tampered_hash():
    assert mod._validate(make_init_data(tamper=True)) is None


def test_validate_rejects_wrong_bot_token():
    # Signed with a different bot token -> HMAC mismatch.
    assert mod._validate(make_init_data(bot_token="999:OTHER")) is None


def test_validate_rejects_wrong_uid():
    assert mod._validate(make_init_data(user_id=111)) is None


def test_validate_rejects_missing_hash():
    assert mod._validate("auth_date=123&user=%7B%7D") is None


def test_validate_rejects_non_string():
    assert mod._validate(None) is None  # type: ignore[arg-type]
    assert mod._validate(12345) is None  # type: ignore[arg-type]


def test_validate_rejects_stale_auth_date():
    old = int(time.time()) - (mod.MAX_AGE + 120)
    assert mod._validate(make_init_data(auth_date=old)) is None


def test_validate_accepts_recent_auth_date_within_window():
    recent = int(time.time()) - (mod.MAX_AGE - 60)
    assert mod._validate(make_init_data(auth_date=recent)) is not None


def test_validate_rejects_future_auth_date():
    future = int(time.time()) + mod.MAX_FUTURE_SKEW + 120
    assert mod._validate(make_init_data(auth_date=future)) is None


def test_validate_allows_small_future_skew():
    near_future = int(time.time()) + max(1, mod.MAX_FUTURE_SKEW - 30)
    assert mod._validate(make_init_data(auth_date=near_future)) is not None


def test_validate_rejects_nonint_auth_date():
    # Build init data whose auth_date is non-numeric but still correctly signed.
    params = {"auth_date": "notanumber", "user": json.dumps({"id": UID})}
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(key, check_str.encode(), hashlib.sha256).hexdigest()
    assert mod._validate(urllib.parse.urlencode(params)) is None


def test_validate_rejects_user_not_a_dict():
    # user is valid JSON but a list, not an object.
    assert mod._validate(make_init_data(user_json="[1,2,3]")) is None


def test_freshness_defaults_are_tightened():
    assert mod.MAX_AGE == 3600
    assert mod.MAX_FUTURE_SKEW == 300


# --------------------------------------------------------------------------- #
# Optional replay rejection
# --------------------------------------------------------------------------- #
def test_replay_allowed_by_default():
    init = make_init_data()
    assert mod._validate(init) is not None
    assert mod._validate(init) is not None  # reuse OK (Telegram reuses initData)


def test_replay_rejected_when_enabled():
    mod.REJECT_REPLAY = True
    init = make_init_data()
    assert mod._validate(init) is not None
    assert mod._validate(init) is None  # second use rejected


# --------------------------------------------------------------------------- #
# _read_json: body-size + malformed handling
# --------------------------------------------------------------------------- #
def test_read_json_ok():
    data, err = run(mod._read_json(FakeRequest({"a": 1})))
    assert err is None and data == {"a": 1}


def test_read_json_rejects_malformed():
    data, err = run(mod._read_json(FakeRequest("{not json")))
    assert data is None and err == "bad_request"


def test_read_json_rejects_non_object():
    data, err = run(mod._read_json(FakeRequest("[1,2,3]")))
    assert data is None and err == "bad_request"


def test_read_json_rejects_oversized_by_content_length():
    req = FakeRequest("{}", content_length=mod.MAX_BODY_BYTES + 1)
    data, err = run(mod._read_json(req))
    assert data is None and err == "too_large"


def test_read_json_rejects_oversized_by_actual_bytes():
    big = json.dumps({"x": "A" * (mod.MAX_BODY_BYTES + 100)})
    # Lie about content-length so the actual-bytes check is what catches it.
    req = FakeRequest(big, content_length=10)
    data, err = run(mod._read_json(req))
    assert data is None and err == "too_large"


def test_read_json_handles_read_exception():
    data, err = run(mod._read_json(FakeRequest("{}", raise_read=True)))
    assert data is None and err == "bad_request"


# --------------------------------------------------------------------------- #
# View-level: auth endpoint
# --------------------------------------------------------------------------- #
def _auth_view():
    return mod.MiniAppAuthView(FakeHass())


def test_auth_view_ok():
    resp = run(_auth_view().post(FakeRequest(body(make_init_data()))))
    assert resp.status == 200 and resp.json()["ok"] is True


def test_auth_view_rejects_bad_signature():
    resp = run(_auth_view().post(FakeRequest(body(make_init_data(tamper=True)))))
    assert resp.status == 401


def test_auth_view_rejects_oversized():
    req = FakeRequest(body(make_init_data()), content_length=mod.MAX_BODY_BYTES + 1)
    resp = run(_auth_view().post(req))
    assert resp.status == 413


def test_auth_view_rejects_malformed_json():
    resp = run(_auth_view().post(FakeRequest("{broken")))
    assert resp.status == 400


# --------------------------------------------------------------------------- #
# View-level: action allow-list enforcement
# --------------------------------------------------------------------------- #
def _action(hass, **payload):
    view = mod.MiniAppActionView(hass)
    req = FakeRequest(body(make_init_data(), **payload))
    return run(view.post(req)), hass


def test_action_allows_listed_switch():
    resp, hass = _action(
        FakeHass(),
        domain="switch",
        service="turn_on",
        entity_id="switch.akvarium_svet_socket_1",
    )
    assert resp.status == 200 and resp.json()["ok"] is True
    assert hass.services.calls[0][:2] == ("switch", "turn_on")
    assert hass.services.calls[0][3] is True


def test_action_returns_observed_entity_state_after_blocking_call():
    entity = FakeState("switch.akvarium_svet_socket_1", "on")
    resp, _ = _action(
        FakeHass([entity]),
        domain="switch",
        service="turn_on",
        entity_id=entity.entity_id,
    )
    assert resp.status == 200
    assert resp.json()["state"]["entity_id"] == entity.entity_id
    assert resp.json()["state"]["state"] == "on"


def test_action_reports_service_failure_instead_of_false_success():
    resp, hass = _action(
        FakeHass(service_error=RuntimeError("simulated HA failure")),
        domain="switch",
        service="turn_on",
        entity_id="switch.akvarium_svet_socket_1",
    )
    assert resp.status == 502
    assert resp.json() == {"error": "service_failed"}
    assert len(hass.services.calls) == 1


def test_action_rejects_unexpected_extra_without_calling_ha():
    resp, hass = _action(
        FakeHass(),
        domain="switch",
        service="turn_on",
        entity_id="switch.akvarium_svet_socket_1",
        extra={"transition": 1},
    )
    assert resp.status == 400
    assert resp.json() == {"error": "bad_extra"}
    assert hass.services.calls == []


def test_action_rejects_forbidden_domain():
    resp, hass = _action(
        FakeHass(),
        domain="lock",
        service="unlock",
        entity_id="lock.front_door",
    )
    assert resp.status == 403
    assert hass.services.calls == []


def test_action_rejects_entity_not_in_allowlist():
    resp, hass = _action(
        FakeHass(),
        domain="switch",
        service="turn_on",
        entity_id="switch.not_a_real_allowed_switch",
    )
    assert resp.status == 403
    assert hass.services.calls == []


def test_action_rejects_disallowed_service_on_allowed_entity():
    resp, hass = _action(
        FakeHass(),
        domain="switch",
        service="toggle",  # only turn_on/turn_off permitted
        entity_id="switch.akvarium_svet_socket_1",
    )
    assert resp.status == 403


def test_action_allows_script_scene():
    resp, hass = _action(
        FakeHass(),
        domain="script",
        service="turn_on",
        entity_id="script.scene_away",
    )
    assert resp.status == 200


# --------------------------------------------------------------------------- #
# View-level: действие приходит ОТ ИМЕНИ ЧЕЛОВЕКА (2026-08-26)
# --------------------------------------------------------------------------- #
# HA отличает человека от автоматики по context.user_id. Пока компонент вызывал
# сервисы без контекста, нажатие в телефоне выглядело как автоматика: выдержку
# тёплого пола (автоматизация 1791100001001) она не включала, и выставленную с
# телефона температуру возвращала автоматика по цене. Эти тесты держат фикс.
def test_action_passes_owner_context():
    hass = FakeHass([FakeState("person.owner", "home", {"user_id": "u-42"})])
    resp, hass = _action(
        hass,
        domain="switch",
        service="turn_on",
        entity_id="switch.akvarium_svet_socket_1",
    )
    assert resp.status == 200
    assert len(hass.services.contexts) == 1
    ctx = hass.services.contexts[0]
    assert ctx is not None and ctx.user_id == "u-42"


def test_action_without_owner_person_still_works():
    """Не нашли id владельца — ведём себя как раньше (без контекста), а не падаем."""
    resp, hass = _action(
        FakeHass(),
        domain="switch",
        service="turn_on",
        entity_id="switch.akvarium_svet_socket_1",
    )
    assert resp.status == 200
    assert hass.services.contexts == [None]


def test_owner_context_ignores_person_without_user_id():
    hass = FakeHass([FakeState("person.owner", "home", {})])
    resp, hass = _action(
        hass,
        domain="switch",
        service="turn_on",
        entity_id="switch.akvarium_svet_socket_1",
    )
    assert resp.status == 200
    assert hass.services.contexts == [None]


def test_action_rejects_non_string_entity_id():
    resp, hass = _action(
        FakeHass(),
        domain="switch",
        service="turn_on",
        entity_id={"evil": True},
    )
    assert resp.status == 400
    assert hass.services.calls == []


# --------------------------------------------------------------------------- #
# View-level: climate temperature handling
# --------------------------------------------------------------------------- #
def test_climate_allows_valid_setpoint():
    resp, hass = _action(
        FakeHass(),
        domain="climate",
        service="set_temperature",
        entity_id="climate.floor_heating",
        extra={"temperature": 30},
    )
    assert resp.status == 200


def test_climate_bad_temperature_type_returns_400_not_500():
    resp, hass = _action(
        FakeHass(),
        domain="climate",
        service="set_temperature",
        entity_id="climate.floor_heating",
        extra={"temperature": "hot"},
    )
    assert resp.status == 400
    assert hass.services.calls == []


def test_climate_missing_temperature_returns_400():
    resp, hass = _action(
        FakeHass(),
        domain="climate",
        service="set_temperature",
        entity_id="climate.floor_heating",
        extra={},
    )
    assert resp.status == 400


def test_climate_out_of_range_temperature_returns_400():
    resp, hass = _action(
        FakeHass(),
        domain="climate",
        service="set_temperature",
        entity_id="climate.floor_heating",
        extra={"temperature": 999},
    )
    assert resp.status == 400


def test_climate_any_on_grid_setpoint_in_range_allowed():
    """2026-07-31: the floor UIs expose a real −/+ stepper, so any 0.5 °C step in
    5–45 is legitimate (it used to be pinned to the single 30 °C cheap-price boost)."""
    for temp in (5, 5.5, 18, 22.5, 30, 44.5, 45):
        resp, hass = _action(
            FakeHass(),
            domain="climate",
            service="set_temperature",
            entity_id="climate.floor_heating",
            extra={"temperature": temp},
        )
        assert resp.status == 200, f"{temp} should be allowed"


def test_climate_off_grid_setpoint_returns_400():
    """The device's step is 0.5 °C — anything off that grid is a client bug."""
    for temp in (18.3, 20.25, 30.1):
        resp, hass = _action(
            FakeHass(),
            domain="climate",
            service="set_temperature",
            entity_id="climate.floor_heating",
            extra={"temperature": temp},
        )
        assert resp.status == 400, f"{temp} is off the 0.5 grid"
        assert hass.services.calls == []


def test_climate_setpoint_above_ui_clamp_returns_400():
    """The thermostats LIE about their ceiling (Tuya reports max_temp 300.0); the
    backend must enforce 45 °C itself and never trust the entity's own limit."""
    for temp in (45.5, 50, 300):
        resp, hass = _action(
            FakeHass(),
            domain="climate",
            service="set_temperature",
            entity_id="climate.floor_heating",
            extra={"temperature": temp},
        )
        assert resp.status == 400, f"{temp} must be refused"
        assert hass.services.calls == []


def test_climate_set_hvac_mode_ok():
    for mode in ("off", "heat_cool"):
        resp, hass = _action(
            FakeHass(),
            domain="climate",
            service="set_hvac_mode",
            entity_id="climate.floor_heating_2",
            extra={"hvac_mode": mode},
        )
        assert resp.status == 200, mode


def test_climate_set_hvac_mode_rejects_other_modes():
    for mode in ("heat", "cool", "auto", "dry", "", None):
        resp, hass = _action(
            FakeHass(),
            domain="climate",
            service="set_hvac_mode",
            entity_id="climate.floor_heating",
            extra={"hvac_mode": mode},
        )
        assert resp.status == 403, mode
        assert hass.services.calls == []


def test_climate_services_refused_on_foreign_entity():
    """The floor allow-list must not become a generic climate remote."""
    for service, extra in (
        ("set_temperature", {"temperature": 30}),
        ("set_hvac_mode", {"hvac_mode": "off"}),
        ("set_preset_mode", {"preset_mode": "auto"}),
    ):
        resp, hass = _action(
            FakeHass(),
            domain="climate",
            service=service,
            entity_id="climate.living_room",
            extra=extra,
        )
        assert resp.status == 403, service
        assert hass.services.calls == []


def test_floor_switches_are_allow_listed_and_scoped():
    """child lock + frost protection per thermostat, and nothing else new."""
    from custom_components.miniapp_auth import STATE_IDS, SWITCH_ENTITIES

    floor_switches = {
        "switch.floor_heating_child_lock",
        "switch.floor_heating_child_lock_2",
        "switch.floor_heating_frost_protection",
        "switch.floor_heating_frost_protection_2",
    }
    assert floor_switches <= SWITCH_ENTITIES
    # every entity the floor UI reads must be delivered by the state endpoint
    assert floor_switches <= STATE_IDS
    assert {
        "climate.floor_heating",
        "climate.floor_heating_2",
        "binary_sensor.floor_heating_valve",
        "binary_sensor.floor_heating_valve_2",
        "automation.teplyi_pol_po_nord_pool_0_04_heat_30c_0_04_auto",
        "automation.teplyi_pol_dushevaia_1et_po_nord_pool_0_04_heat_30c_0_04_auto",
    } <= STATE_IDS
    # the valve is READ-ONLY: it must never be commandable
    assert "binary_sensor.floor_heating_valve" not in SWITCH_ENTITIES
    for eid in floor_switches:
        for service in ("turn_on", "turn_off"):
            resp, _ = _action(
                FakeHass(), domain="switch", service=service, entity_id=eid, extra={}
            )
            assert resp.status == 200, (eid, service)


def test_climate_bool_temperature_rejected():
    resp, hass = _action(
        FakeHass(),
        domain="climate",
        service="set_temperature",
        entity_id="climate.floor_heating",
        extra={"temperature": True},
    )
    assert resp.status == 400


def test_climate_preset_mode_ok():
    resp, hass = _action(
        FakeHass(),
        domain="climate",
        service="set_preset_mode",
        entity_id="climate.floor_heating",
        extra={"preset_mode": "auto"},
    )
    assert resp.status == 200


# --------------------------------------------------------------------------- #
# _as_float unit checks
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "value,expected",
    [
        (30, 30.0),
        (30.5, 30.5),
        ("30", 30.0),
        (" 30.0 ", 30.0),
        ("nan_but_not", None),
        ("", None),
        (True, None),
        (False, None),
        (None, None),
        ({"x": 1}, None),
        ([1], None),
    ],
)
def test_as_float(value, expected):
    assert mod._as_float(value) == expected


# --------------------------------------------------------------------------- #
# Calendar allow-list
# --------------------------------------------------------------------------- #
def test_calendar_allowed_rejects_non_calendar_domain():
    hass = FakeHass(entities=[FakeState("sensor.kukhnia_temperature")])
    assert mod._calendar_allowed(hass, "sensor.kukhnia_temperature") is False


def test_calendar_allowed_rejects_arbitrary_string():
    assert mod._calendar_allowed(FakeHass(), "not-an-entity") is False
    assert mod._calendar_allowed(FakeHass(), 12345) is False


def test_calendar_allowed_rejects_unknown_calendar_in_nonstrict_mode():
    # Non-strict default: unknown calendar (not registered) is refused.
    hass = FakeHass(entities=[])
    assert mod._calendar_allowed(hass, "calendar.ghost") is False


def test_calendar_allowed_accepts_registered_calendar_nonstrict():
    hass = FakeHass(entities=[FakeState("calendar.personal")])
    assert mod._calendar_allowed(hass, "calendar.personal") is True


def test_calendar_view_reads_only_allowed_calendars():
    cal_response = {
        "calendar.personal": {
            "events": [
                {"start": "2026-07-16", "end": "2026-07-17", "summary": "Trip"},
            ]
        }
    }
    hass = FakeHass(entities=[FakeState("calendar.personal")], cal_response=cal_response)
    view = mod.MiniAppCalendarView(hass)
    payload = body(
        make_init_data(),
        calendarIds=["calendar.personal", "calendar.ghost", "sensor.evil", "not-real"],
        start="2026-07-15T00:00:00+00:00",
        end="2026-07-22T00:00:00+00:00",
    )
    resp = run(view.post(FakeRequest(payload)))
    assert resp.status == 200
    out = resp.json()
    assert len(out["events"]) == 1 and out["events"][0]["summary"] == "Trip"
    # Only the allowed, registered calendar was queried.
    queried = [c[2].get("entity_id") for c in hass.services.calls]
    assert queried == ["calendar.personal"]


def test_calendar_view_handles_non_list_calendarids():
    hass = FakeHass()
    view = mod.MiniAppCalendarView(hass)
    payload = body(make_init_data(), calendarIds="calendar.personal")
    resp = run(view.post(FakeRequest(payload)))
    assert resp.status == 200
    assert resp.json()["events"] == []
    assert hass.services.calls == []


# --------------------------------------------------------------------------- #
# State view
# --------------------------------------------------------------------------- #
def test_state_view_returns_allowlisted_states_only():
    entities = [
        FakeState("sensor.kukhnia_temperature", "21.5"),
        FakeState("calendar.personal", "on"),
        FakeState("sensor.secret_not_allowed", "42"),
    ]
    view = mod.MiniAppStateView(FakeHass(entities=entities))
    resp = run(view.post(FakeRequest(body(make_init_data()))))
    assert resp.status == 200
    ids = {s["entity_id"] for s in resp.json()["states"]}
    assert "sensor.kukhnia_temperature" in ids
    assert "calendar.personal" in ids  # calendars are surfaced for the frontend
    assert "sensor.secret_not_allowed" not in ids


def test_state_view_requires_auth():
    view = mod.MiniAppStateView(FakeHass())
    resp = run(view.post(FakeRequest(body(make_init_data(tamper=True)))))
    assert resp.status == 401


def test_state_view_offloads_blocking_price_read_to_executor():
    """The state view must not read the prices file inline on the event loop;
    it offloads _read_today_prices via async_add_executor_job."""
    hass = FakeHass(entities=[FakeState("sensor.kukhnia_temperature", "21.5")])
    view = mod.MiniAppStateView(hass)
    resp = run(view.post(FakeRequest(body(make_init_data()))))
    assert resp.status == 200
    assert "prices" in resp.json()
    # Exactly the blocking price reader was offloaded to the executor.
    offloaded = [name for name, _ in hass.executor_calls]
    assert "_read_today_prices" in offloaded


def test_state_view_survives_executor_failure():
    """If the executor offload itself raises, the endpoint still returns a 200
    with the safe empty price shape rather than a 500."""

    class BoomHass(FakeHass):
        async def async_add_executor_job(self, func, *args):
            raise RuntimeError("executor down")

    hass = BoomHass(entities=[FakeState("sensor.kukhnia_temperature", "21.5")])
    view = mod.MiniAppStateView(hass)
    resp = run(view.post(FakeRequest(body(make_init_data()))))
    assert resp.status == 200
    assert resp.json()["prices"] == {"prices": {}, "updated": None}


# --------------------------------------------------------------------------- #
# _read_today_prices: robust file open (context manager + safe fallback)
# --------------------------------------------------------------------------- #
def test_read_today_prices_missing_file_returns_fallback():
    # The hard-coded /config/www/today_prices.json does not exist on the test
    # runner; the open() must be caught and the safe empty shape returned.
    out = mod._read_today_prices()
    assert out == {"prices": {}, "updated": None}


def test_read_today_prices_parses_dict_prices(tmp_path, monkeypatch):
    """A well-formed prices file is parsed; the open is via a context manager so
    the descriptor is always released."""
    f = tmp_path / "today_prices.json"
    f.write_text(
        json.dumps({"prices": {"2026-07-16": {"0": 0.021, "13": 0.074}}, "updated": "x"}),
        encoding="utf-8",
    )
    real_open = open

    def fake_open(path, *a, **k):
        return real_open(f, *a, **k)

    monkeypatch.setattr("builtins.open", fake_open)
    out = mod._read_today_prices()
    assert out["updated"] == "x"
    assert out["prices"]["2026-07-16"]["13"] == 0.074


def test_read_today_prices_handles_garbage_file(tmp_path, monkeypatch):
    f = tmp_path / "today_prices.json"
    f.write_text("{ not valid json", encoding="utf-8")
    real_open = open
    monkeypatch.setattr("builtins.open", lambda p, *a, **k: real_open(f, *a, **k))
    assert mod._read_today_prices() == {"prices": {}, "updated": None}


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #
def test_rate_limiter_blocks_burst_then_refills():
    rl = mod._RateLimiter(capacity=3, refill_per_sec=1.0)
    t = 1000.0
    assert rl.allow("k", now=t) is True
    assert rl.allow("k", now=t) is True
    assert rl.allow("k", now=t) is True
    assert rl.allow("k", now=t) is False  # bucket empty
    assert rl.allow("k", now=t + 2) is True  # refilled 2 tokens


def test_rate_limiter_keys_are_independent():
    rl = mod._RateLimiter(capacity=1, refill_per_sec=0.0)
    assert rl.allow("a", now=5) is True
    assert rl.allow("a", now=5) is False
    assert rl.allow("b", now=5) is True


def test_action_view_rate_limited_returns_429():
    # Shrink the live limiter and hammer the same IP.
    mod._RATE.reset()
    mod._RATE.capacity = 2.0
    mod._RATE.refill = 0.0
    hass = FakeHass()
    view = mod.MiniAppActionView(hass)

    def hit():
        req = FakeRequest(
            body(make_init_data(), domain="switch", service="turn_on",
                 entity_id="switch.akvarium_svet_socket_1"),
            remote="9.9.9.9",
        )
        return run(view.post(req)).status

    statuses = [hit() for _ in range(5)]
    assert 429 in statuses
