"""Telegram Mini App proxy endpoints for smart home control."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import Context, HomeAssistant

try:
    from project_secrets import secret
except Exception:  # pragma: no cover - HA loads this from /config
    def secret(name: str, default: str | None = None, *, required: bool = False) -> str:
        if required and default is None:
            raise RuntimeError(f"Missing required secret: {name}")
        return default or ""


def _int_secret(name: str, default: int) -> int:
    """Read an int secret, falling back to a safe default on missing/garbage."""
    try:
        val = int(secret(name, str(default)))
    except (TypeError, ValueError):
        return default
    return val if val >= 0 else default


def _bool_secret(name: str, default: bool = False) -> bool:
    return secret(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


BOT_TOKEN = secret("TELEGRAM_BOT_TOKEN")
# Публичный репозиторий: настоящий Telegram-uid владельца сюда не пишем.
# 0 не совпадёт ни с одним реальным пользователем, поэтому без секрета
# TELEGRAM_ALLOWED_UID компонент закрыт для всех — отказ в безопасную сторону.
ALLOWED_UID = int(secret("TELEGRAM_ALLOWED_UID", "0"))
# P0: HA_TOKEN / HA_BASE_URL removed — calendar now uses the internal
# calendar.get_events service, so this component no longer needs an HA token.

# --- Telegram initData freshness (tightened from the old flat 86400s) ---------
# Reject stale initData (default 1h) and initData dated in the future beyond a
# small clock-skew allowance (default 5min). Both configurable via secrets.
MAX_AGE = _int_secret("MINIAPP_MAX_AGE", 3600)
MAX_FUTURE_SKEW = _int_secret("MINIAPP_MAX_FUTURE_SKEW", 300)

# --- Abuse limits -------------------------------------------------------------
# Hard cap on request body size (bytes). Bodies larger than this are rejected
# (413) before any JSON parsing, so an oversized payload can't burn CPU/memory.
MAX_BODY_BYTES = _int_secret("MINIAPP_MAX_BODY_BYTES", 16384)

# Token-bucket rate limit, applied per remote IP and per Telegram UID. Defaults
# allow comfortable interactive use while capping bursts/floods.
RATE_CAPACITY = _int_secret("MINIAPP_RATE_CAPACITY", 40)
RATE_REFILL_PER_SEC = float(_int_secret("MINIAPP_RATE_REFILL_PER_MIN", 120)) / 60.0

# Optional strict single-use replay rejection. DEFAULT OFF on purpose: a Telegram
# Web App hands the frontend ONE initData string per session and (correctly)
# reuses it for every API call, so rejecting duplicate hashes would break normal
# use. The freshness window above already bounds any replay to <= MAX_AGE. A
# truly robust nonce store would need HA persistent storage (helpers.storage.Store)
# to survive restarts / be shared across workers; that is intentionally deferred.
REJECT_REPLAY = _bool_secret("MINIAPP_REJECT_REPLAY", False)

STATE_IDS = {
    "weather.forecast_home",
    "sensor.smart_weather_station_temperature",
    "sensor.nord_pool_lv_current_price",
    # Read-only display flag, added 2026-08-16: the authoritative "are tomorrow's
    # day-ahead prices published yet" signal. The Mini App's «Завтра» chart uses it
    # ONLY to explain an empty curve honestly (published ~14:00 local). Display
    # only — the ACTION allow-lists below are untouched.
    "binary_sensor.nord_pool_lv_tomorrow_price_available",
    "sensor.ev_charger_status",
    "sensor.ev_charger_energy",
    "input_datetime.ev_charge_start",
    "input_boolean.ev_manual_mode",
    "sensor.boiler_total_energy",
    "input_number.midnight_boiler_energy",
    "sensor.akvarium_svet_total_energy",
    "input_number.midnight_akv_energy",
    "sensor.cherepakha_total_energy",
    "input_number.midnight_chep_energy",
    "sensor.zigbee_plug_2_total_energy",
    "input_number.midnight_gidro_energy",
    "input_number.midnight_ev_energy",
    # --- read-only additions 2026-07-27: the Mini App displays / verifies these but they
    # --- were missing from the allow-list, so they rendered as «нет данных» and the EV
    # --- command verification could never succeed. Display/verify only — the ACTION
    # --- allow-lists below are untouched.
    "sensor.terarium_total_energy",
    "input_number.midnight_kalarifer_energy",
    "input_number.cost_month_total",
    "switch.ev_charger_switch",
    "sensor.boiler_mode",
    "sensor.boiler_co_temperature",
    "sensor.boiler_co_setpoint",
    "sensor.boiler_cwu_temperature",
    "sensor.boiler_cwu_setpoint",
    "sensor.boiler_return_temperature",
    "sensor.boiler_fan_power",
    "switch.smart_plug_2_socket_1",
    "binary_sensor.boiler_co_pump",
    "binary_sensor.boiler_cwu_pump",
    "binary_sensor.boiler_circulation_pump",
    "climate.floor_heating",
    "climate.floor_heating_2",
    # --- Тёплые полы (ЭЛЕКТРИЧЕСКИЕ, не от котла), added 2026-07-31 -------------
    # Two independent Tuya floor thermostats, 4 entities each. Display + the floor
    # controls below need all of them; the two automations are shown so the Mini App
    # can explain (honestly) why the floor changes by itself.
    "binary_sensor.floor_heating_valve",
    "binary_sensor.floor_heating_valve_2",
    "switch.floor_heating_child_lock",
    "switch.floor_heating_child_lock_2",
    "switch.floor_heating_frost_protection",
    "switch.floor_heating_frost_protection_2",
    "automation.teplyi_pol_po_nord_pool_0_04_heat_30c_0_04_auto",
    "automation.teplyi_pol_dushevaia_1et_po_nord_pool_0_04_heat_30c_0_04_auto",
    "switch.voda_kran_switch_1",
    "input_boolean.security_armed",
    "input_boolean.night_saver",
    "input_boolean.rezhim_zhara",
    "binary_sensor.door_sensor_door",
    "binary_sensor.wifi_th_smoke_sensor_smoke",
    # --- Leak protection: the ONE source of truth the Mini App reads (added 2026-07-27).
    # Read-only display entity; the ACTION allow-lists below are untouched.
    "sensor.leak_protection_status",
    "binary_sensor.vannaia_moisture",
    "binary_sensor.water_sensor_4_moisture",
    "binary_sensor.garazh_moisture",
    "binary_sensor.kukhnia_moisture",
    "binary_sensor.lumi_cn_lumi_living_motion_v2_motion_state_p_2_1",
    "sensor.door_sensor_battery",
    "sensor.wifi_th_smoke_sensor_battery",
    "sensor.vannaia_battery",
    "sensor.water_sensor_4_battery",
    "sensor.kukhnia_battery",
    "sensor.garazh_battery",
    "light.prikhozhaia_i_fanar_light",
    "light.prikhozhaia_i_fanar_light_2",
    "light.svet_pervyi_etazh_1_light",
    "light.svet_pervyi_etazh_1_light_2",
    "light.vtoroi_etazh_light",
    "light.dream_color_rgb",
    "light.veranda_light",
    "switch.kukhnia_poloski_switch_1",
    "switch.kukhnia_poloski_switch_2",
    "switch.svet_tv_zona_switch_1",
    "switch.svet_tv_zona_switch_2",
    "switch.smart_switch_2ch_switch_1",
    "switch.smart_switch_2ch_switch_2",
    "switch.akvarium_svet_socket_1",
    "switch.retserkuliatsiia_goriachai_vody_socket_1",
    "switch.zigbee_plug_2_socket_1",
    "switch.kalarifer_socket_1",
    # --- Микроклимат по комнатам (temp / humidity / air / lux), added 2026-07-12 ---
    "sensor.kukhnia_temperature",
    "sensor.kukhnia_humidity",
    "sensor.lumi_cn_lumi_bedroom_th_v1_temperature_p_2_1",
    "sensor.lumi_cn_lumi_bedroom_th_v1_relative_humidity_p_2_2",
    "sensor.miaomiaoc_cn_blt_3_living_t1_temperature_p_2_1",
    "sensor.miaomiaoc_cn_blt_3_living_t1_relative_humidity_p_2_2",
    "sensor.miaomiaoc_cn_blt_3_bedroom2_t1_temperature_p_2_1",
    "sensor.miaomiaoc_cn_blt_3_bedroom2_t1_relative_humidity_p_2_2",
    "sensor.smart_weather_station_humidity",
    "sensor.zhimi_cn_purifier_mb3_temperature_p_3_8",
    "sensor.zhimi_cn_purifier_mb3_relative_humidity_p_3_7",
    "sensor.zhimi_cn_purifier_mb3_pm2_5_density_p_3_6",
    "sensor.lumi_cn_gateway_v3_illumination_p_5_1",
    "sensor.boiler_outside_temperature",
    # --- Ручная выдержка тёплого пола (2026-08-26) --------------------------------
    # ЕДИНСТВЕННЫЙ источник правды о выдержке: атрибуты reason/until/mins_left/held_temp.
    # Только показ — приложение рисует плашку «держим N° до HH:MM» и кнопку снятия.
    "binary_sensor.floor_hold_vannaia",
    "binary_sensor.floor_hold_dushevaia",
    # --- Устройства, которые были только на планшете (2026-08-26) -----------------
    "switch.gostinnaia_zanaveska_zona_switch_1",
    "switch.zigbee_plug_socket_1",
    "vacuum.kiborg",
    # --- Расходы за месяц по устройствам (2026-08-26). Только показ ---------------
    "input_number.cost_month_boiler",
    "input_number.cost_month_kalarifer",
    "input_number.cost_month_akv",
    "input_number.cost_month_chep",
    "input_number.cost_month_gidro",
    "input_number.cost_month_ev",
}

LIGHT_ENTITIES = {
    "light.prikhozhaia_i_fanar_light",
    "light.prikhozhaia_i_fanar_light_2",
    "light.svet_pervyi_etazh_1_light",
    "light.svet_pervyi_etazh_1_light_2",
    "light.vtoroi_etazh_light",
    "light.dream_color_rgb",
    "light.dream_color_rgb_2",
    "light.veranda_light",
}

SWITCH_ENTITIES = {
    "switch.ev_charger_switch",
    "switch.smart_plug_2_socket_1",
    "switch.voda_kran_switch_1",
    "switch.kukhnia_poloski_switch_1",
    "switch.kukhnia_poloski_switch_2",
    "switch.svet_tv_zona_switch_1",
    "switch.svet_tv_zona_switch_2",
    "switch.smart_switch_2ch_switch_1",
    "switch.smart_switch_2ch_switch_2",
    "switch.akvarium_svet_socket_1",
    "switch.retserkuliatsiia_goriachai_vody_socket_1",
    "switch.zigbee_plug_2_socket_1",
    "switch.kalarifer_socket_1",
    "switch.vkliuchit_svet_nad_akvariumom",
    "switch.vykliuchit_svet_nad_akvariumom",
    "switch.vkliuchit_svet_stena",
    "switch.vykliuchit_svet_stena",
    "switch.vkliuchit_svet_zanaveski",
    "switch.vykliuchit_svet_zanaveski",
    "switch.vkliuchit_svet_u_lestnitsy",
    # ВНИМАНИЕ на последнюю букву: «включить» кончается на -y, «выключить» на -i.
    # До 2026-08-26 здесь стояло switch.vkliuchit_svet_u_lestnitsi (без кавычек намеренно:
    # grep по allow-list не должен считать комментарий записью) — такой сущности
    # в доме нет вообще, а живого «выключить» не было, поэтому лестницу можно было
    # только включить. Проверять по /api/states, не по слуху.
    "switch.vykliuchit_svet_u_lestnitsi",
    # Были только на планшете до 2026-08-26.
    "switch.gostinnaia_zanaveska_zona_switch_1",
    "switch.zigbee_plug_socket_1",
    # Тёплые полы: child lock + frost protection per thermostat (2026-07-31).
    # Floor POWER / MODE / SETPOINT go through the climate branch, not here.
    "switch.floor_heating_child_lock",
    "switch.floor_heating_child_lock_2",
    "switch.floor_heating_frost_protection",
    "switch.floor_heating_frost_protection_2",
}

INPUT_BOOLEANS = {
    "input_boolean.security_armed",
    "input_boolean.ev_manual_mode",
    "input_boolean.night_saver",
    "input_boolean.rezhim_zhara",
}

AUTOMATION_ENTITIES = {
    # Слаг проверен по /api/states 2026-08-26: до этого здесь стоял
    # automation.ev_planirovshchik — такой сущности не существует.
    "automation.ev_zariadka_planirovshchik",
}

SCRIPT_ENTITIES = {
    "script.scene_away",
    "script.scene_cinema",
    "script.scene_guests",
    "script.rezhim_zhara_on",
    "script.rezhim_zhara_off",
    # One-shot "cancel the next charge" (2026-08-19). Writes only helpers and
    # sends one Telegram confirmation - it commands no device.
    "script.ev_cancel_next",
    # Ручная выдержка тёплого пола (2026-08-26): те же действия, что у кнопок
    # /floor_hold_off и /floor_hold_plus в Telegram. Пишут только хелперы.
    "script.floor_hold_off",
    "script.floor_hold_plus",
}

CLIMATE_ENTITIES = {
    "climate.floor_heating",
    "climate.floor_heating_2",
}

# Sane bounds for a floor-heating setpoint. A request outside this range is a
# client bug / abuse and earns a clean 400 rather than a 500 from float() below.
#
# TUYA SCALING BUG: these thermostats advertise `max_temp: 300.0` over the Tuya
# cloud (the device's real ceiling is the `upper_temp` DP = 500, i.e. 50.0 °C —
# the cloud forgets to divide by 10). So the entity's own max_temp must NEVER be
# used as a bound. 45 °C is the ceiling the Mini App / tablet UIs clamp to, and
# the backend enforces the same number independently of the frontend.
CLIMATE_TEMP_MIN = 5.0
CLIMATE_TEMP_MAX = 45.0
# The device's target_temp_step. A setpoint off-grid is a client bug -> refused.
CLIMATE_TEMP_STEP = 0.5
# hvac_mode values the frontend may push. The thermostats expose exactly these two.
CLIMATE_HVAC_MODES = {"off", "heat_cool"}

# Explicit calendar allow-list (in addition to any calendar.* ids in STATE_IDS).
# Empty by default: the state endpoint only ever advertises genuinely-registered
# calendar.* entities and the frontend echoes those exact ids back, so with an
# empty set we fall back to "must be a live calendar entity" (see
# _calendar_allowed) — preserving behavior for all of the owner's real calendars
# without pinning volatile entity ids, while still refusing arbitrary strings.
# Add ids here (or to STATE_IDS) to switch to strict pinning.
CALENDAR_ENTITIES: set[str] = set()
_STRICT_CALENDARS = bool(CALENDAR_ENTITIES) or any(
    e.startswith("calendar.") for e in STATE_IDS
)

VACUUM_ENTITIES = {
    "vacuum.kiborg",
}
VACUUM_SERVICES = {"start", "pause", "return_to_base"}

REST_COMMANDS = {
    "set_boiler_cwu_temp": {40, 45, 50, 55, 60},
    "set_boiler_co_temp": {50, 60, 68, 75},
}

SHELL_COMMANDS = {
    "ev_night2h",
    "ev_day2h",
}


# --- Кто нажал: человек, а не автоматика -------------------------------------
# HA отличает человека от автоматики по context.user_id: у действий из UI/панели/
# REST-токена он заполнен, у автоматизаций пуст. Компонент вызывал сервисы БЕЗ
# контекста, поэтому нажатие в телефоне приходило как «автоматика»: автоматизация
# 1791100001001 («принять установку человека» для тёплого пола) его не видела, и
# выставленную с телефона температуру возвращала автоматика по цене. Побочно все
# действия Mini App были анонимны в журнале HA.
#
# id владельца берём из атрибута user_id сущности person.* — ничего не хардкодим и
# не храним в секретах. Если найти не удалось, ведём себя как раньше (без контекста).
# Сущность person владельца: берётся из секретов, чтобы в публичном коде не было
# имени. Значение по умолчанию — нейтральное; на живом доме задаётся секретом.
OWNER_PERSON = secret("OWNER_PERSON_ENTITY", "person.owner")


def _owner_context(hass: HomeAssistant):
    """Контекст от имени владельца или None, если id найти не удалось."""
    state = hass.states.get(OWNER_PERSON)
    user_id = (state.attributes.get("user_id") if state else None) or None
    if not isinstance(user_id, str) or not user_id:
        return None
    return Context(user_id=user_id)


def _json(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, ensure_ascii=False, default=str),
        status=status,
        content_type="application/json",
    )


def _as_float(value: Any) -> float | None:
    """Best-effort float parse that never raises. Returns None on bad input.

    ``bool`` is rejected explicitly (it is an ``int`` subclass) so that a stray
    ``true`` cannot masquerade as ``1.0``.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


class _RateLimiter:
    """Tiny in-memory token-bucket rate limiter.

    Runs entirely inside HA's single asyncio event loop (aiohttp handlers are
    coroutines), so no locking is required. State is per-process and resets on
    restart — adequate for flood protection, not a distributed quota.
    """

    def __init__(self, capacity: float, refill_per_sec: float) -> None:
        self.capacity = float(capacity)
        self.refill = float(refill_per_sec)
        self._buckets: dict[str, tuple[float, float]] = {}

    def allow(self, key: str, cost: float = 1.0, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.refill)
        if len(self._buckets) > 8192:  # opportunistic prune of idle/full buckets
            self._buckets = {
                k: v
                for k, v in self._buckets.items()
                if v[0] < self.capacity or (now - v[1]) < 3600
            }
        if tokens < cost:
            self._buckets[key] = (tokens, now)
            return False
        self._buckets[key] = (tokens - cost, now)
        return True

    def reset(self) -> None:
        self._buckets.clear()


class _TTLCache:
    """Bounded TTL set of recently-seen hashes (optional replay defense)."""

    def __init__(self, ttl: float) -> None:
        self.ttl = float(ttl)
        self._d: dict[str, float] = {}

    def seen(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        exp = self._d.get(key)
        return exp is not None and exp > now

    def add(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        if len(self._d) > 8192:
            self._d = {k: e for k, e in self._d.items() if e > now}
        self._d[key] = now + self.ttl

    def clear(self) -> None:
        self._d.clear()


_RATE = _RateLimiter(RATE_CAPACITY, RATE_REFILL_PER_SEC)
_SEEN = _TTLCache(MAX_AGE)


def _calendar_allowed(hass: HomeAssistant, entity_id: Any) -> bool:
    """Gate a caller-supplied calendar id before we read its events.

    Must be a ``calendar.*`` id that is either explicitly allow-listed (STATE_IDS
    or CALENDAR_ENTITIES) or, in the non-strict default, a genuinely-registered
    calendar entity — never an arbitrary string.
    """
    if not isinstance(entity_id, str) or not entity_id.startswith("calendar."):
        return False
    if entity_id in STATE_IDS or entity_id in CALENDAR_ENTITIES:
        return True
    if _STRICT_CALENDARS:
        return False
    return hass.states.get(entity_id) is not None


def _validate(init_data: str) -> dict[str, Any] | None:
    if not BOT_TOKEN or not isinstance(init_data, str):
        return None
    try:
        params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    except (TypeError, ValueError):
        return None
    received = params.pop("hash", "")
    params.pop("signature", None)
    if not received:
        return None
    try:
        auth_date = int(params.get("auth_date", 0))
    except (TypeError, ValueError):
        return None
    now = time.time()
    if auth_date <= 0:
        return None
    if now - auth_date > MAX_AGE:  # too old
        return None
    if auth_date - now > MAX_FUTURE_SKEW:  # dated in the future beyond skew
        return None
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        user = json.loads(params.get("user", "{}"))
    except Exception:
        return None
    if not isinstance(user, dict) or user.get("id") != ALLOWED_UID:
        return None
    if REJECT_REPLAY:
        if _SEEN.seen(received):
            return None
        _SEEN.add(received)
    return user


async def _read_json(request: web.Request) -> tuple[dict[str, Any] | None, str | None]:
    """Read + size-limit + JSON-parse the body. Never raises.

    Returns ``(data, error)`` where error is None / "too_large" / "bad_request".
    """
    clen = request.content_length
    if clen is not None and clen > MAX_BODY_BYTES:
        return None, "too_large"
    try:
        raw = await request.read()
    except Exception:
        return None, "bad_request"
    if len(raw) > MAX_BODY_BYTES:
        return None, "too_large"
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return None, "bad_request"
    if not isinstance(data, dict):
        return None, "bad_request"
    return data, None


async def _guarded(
    request: web.Request,
) -> tuple[dict[str, Any] | None, dict[str, Any], web.Response | None]:
    """Shared front door for every endpoint.

    Order: IP rate-limit -> body size/parse -> Telegram auth -> UID rate-limit.
    Returns ``(user, data, error_response)``. If ``error_response`` is not None
    the caller must return it verbatim. If it is None and ``user`` is None, the
    caller emits its own 401 (kept per-view so response bodies stay unchanged).
    """
    ip = request.remote or "?"
    if not _RATE.allow(f"ip:{ip}"):
        return None, {}, _json({"error": "rate_limited"}, status=429)
    data, err = await _read_json(request)
    if err == "too_large":
        return None, {}, _json({"error": "too_large"}, status=413)
    if err is not None:
        return None, {}, _json({"error": "bad_request"}, status=400)
    user = _validate(data.get("initData", ""))
    if user is None:
        return None, data, None
    if not _RATE.allow(f"uid:{user.get('id')}"):
        return None, data, _json({"error": "rate_limited"}, status=429)
    return user, data, None


def _state_obj(state) -> dict[str, Any]:
    return {
        "entity_id": state.entity_id,
        "state": state.state,
        "attributes": dict(state.attributes),
        "last_changed": state.last_changed.isoformat(),
        "last_updated": state.last_updated.isoformat(),
    }


def _read_today_prices() -> dict[str, Any]:
    try:
        with open("/config/www/today_prices.json", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"prices": {}, "updated": None}
    if isinstance(data, list):
        return {"prices": {}, "today": [float(x) for x in data[:24] if isinstance(x, (int, float))], "updated": None}
    if isinstance(data, dict):
        prices = data.get("prices")
        if isinstance(prices, dict):
            safe_prices: dict[str, dict[str, float]] = {}
            for day, hours in prices.items():
                if not isinstance(day, str) or not isinstance(hours, dict):
                    continue
                safe_hours = {}
                for hour, value in hours.items():
                    try:
                        h = int(hour)
                        v = float(value)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= h <= 23:
                        safe_hours[str(h)] = v
                if safe_hours:
                    safe_prices[day] = safe_hours
            return {"prices": safe_prices, "updated": data.get("updated")}
        values = data.get("today") or data.get("data") or []
        if isinstance(values, list):
            out = []
            for item in values[:24]:
                if isinstance(item, (int, float)):
                    out.append(float(item))
                elif isinstance(item, dict):
                    val = item.get("price") or item.get("value")
                    if isinstance(val, (int, float)):
                        out.append(float(val))
            return {"prices": {}, "today": out, "updated": data.get("updated")}
    return {"prices": {}, "updated": None}


def _cal_when(value: Any) -> dict[str, str]:
    """Map a calendar.get_events ISO string to the REST-like {date|dateTime} shape
    the Mini App frontend expects."""
    text = str(value or "")
    if not text:
        return {}
    return {"date": text} if len(text) == 10 else {"dateTime": text}


class MiniAppAuthView(HomeAssistantView):
    url = "/api/miniapp-auth"
    name = "api:miniapp_auth"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        user, _data, err = await _guarded(request)
        if err is not None:
            return err
        if user is None:
            return _json({"ok": False}, status=401)
        return _json({"ok": True, "mode": "proxy"})


class MiniAppStateView(HomeAssistantView):
    url = "/api/miniapp-state"
    name = "api:miniapp_state"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        user, _data, err = await _guarded(request)
        if err is not None:
            return err
        if user is None:
            return _json({"error": "unauthorized"}, status=401)
        states = []
        for state in self.hass.states.async_all():
            if state.entity_id in STATE_IDS or state.entity_id.startswith("calendar."):
                states.append(_state_obj(state))
        # _read_today_prices does blocking file I/O; never run it inline on the
        # event loop. Offload to the executor and fall back to the safe empty
        # shape if the executor itself errors, so the state endpoint never 500s.
        try:
            prices = await self.hass.async_add_executor_job(_read_today_prices)
        except Exception:
            prices = {"prices": {}, "updated": None}
        return _json({"states": states, "prices": prices})


class MiniAppCalendarView(HomeAssistantView):
    url = "/api/miniapp-calendar"
    name = "api:miniapp_calendar"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        user, data, err = await _guarded(request)
        if err is not None:
            return err
        if user is None:
            return _json({"error": "unauthorized"}, status=401)
        start = str(data.get("start", ""))
        end = str(data.get("end", ""))
        events: list[dict[str, Any]] = []
        raw_ids = data.get("calendarIds", [])
        if not isinstance(raw_ids, list):
            raw_ids = []
        ids = [x for x in raw_ids if _calendar_allowed(self.hass, x)]
        for entity_id in ids[:4]:
            try:
                resp = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
                    blocking=True,
                    return_response=True,
                )
                got = ((resp or {}).get(entity_id) or {}).get("events", []) or []
                for event in got[:4]:
                    if not isinstance(event, dict):
                        continue
                    events.append({
                        "start": _cal_when(event.get("start")),
                        "end": _cal_when(event.get("end")),
                        "summary": event.get("summary"),
                        "description": event.get("description"),
                        "location": event.get("location"),
                        "cal": entity_id,
                    })
            except Exception:
                continue
        events.sort(key=lambda e: str((e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date") or ""))
        return _json({"events": events[:8]})


class MiniAppActionView(HomeAssistantView):
    url = "/api/miniapp-action"
    name = "api:miniapp_action"
    requires_auth = False
    cors_allowed = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        user, data, err = await _guarded(request)
        if err is not None:
            return err
        if user is None:
            return _json({"error": "unauthorized"}, status=401)

        domain = str(data.get("domain", ""))
        service = str(data.get("service", ""))
        entity_id = data.get("entity_id")
        if entity_id is not None and not isinstance(entity_id, str):
            return _json({"error": "bad_request"}, status=400)
        extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}

        allowed = False
        if domain == "light" and service in {"turn_on", "turn_off"} and entity_id in LIGHT_ENTITIES:
            allowed = True
        elif domain == "switch" and service in {"turn_on", "turn_off"} and entity_id in SWITCH_ENTITIES:
            allowed = True
        elif domain == "input_boolean" and service in {"turn_on", "turn_off"} and entity_id in INPUT_BOOLEANS:
            allowed = True
        elif domain == "automation" and service == "trigger" and entity_id in AUTOMATION_ENTITIES:
            allowed = True
        elif domain == "script" and service == "turn_on" and entity_id in SCRIPT_ENTITIES:
            allowed = True
        elif domain == "shell_command" and service in SHELL_COMMANDS and not entity_id:
            allowed = True
        elif domain == "climate" and entity_id in CLIMATE_ENTITIES:
            if service == "set_preset_mode" and extra.get("preset_mode") in {"auto", "manual"}:
                allowed = True
            elif service == "set_hvac_mode" and extra.get("hvac_mode") in CLIMATE_HVAC_MODES:
                allowed = True
            elif service == "set_temperature":
                temp = _as_float(extra.get("temperature"))
                if temp is None or not (CLIMATE_TEMP_MIN <= temp <= CLIMATE_TEMP_MAX):
                    return _json({"error": "bad_temperature"}, status=400)
                # Must sit on the device's 0.5 °C grid (float-safe comparison).
                if round(temp / CLIMATE_TEMP_STEP) * CLIMATE_TEMP_STEP != round(temp, 1):
                    return _json({"error": "bad_temperature"}, status=400)
                allowed = True
        elif domain == "vacuum" and service in VACUUM_SERVICES and entity_id in VACUUM_ENTITIES:
            allowed = True
        elif domain == "rest_command" and service in REST_COMMANDS:
            try:
                temp = int(extra.get("temp"))
            except (TypeError, ValueError):
                temp = None
            allowed = temp in REST_COMMANDS[service]

        if not allowed:
            return _json({"error": "not_allowed"}, status=403)

        # Never forward caller-controlled keys that are not part of the exact
        # action contract.  In particular, a permitted entity/service pair must
        # not become a vehicle for arbitrary HA service parameters.
        allowed_extra: set[str] = set()
        if domain == "climate":
            allowed_extra = {
                "set_temperature": {"temperature"},
                "set_hvac_mode": {"hvac_mode"},
                "set_preset_mode": {"preset_mode"},
            }.get(service, set())
        elif domain == "rest_command":
            allowed_extra = {"temp"}
        if set(extra) != allowed_extra:
            return _json({"error": "bad_extra"}, status=400)

        service_data = dict(extra)
        if entity_id:
            service_data["entity_id"] = entity_id
        try:
            # Blocking means HA has completed (or failed) the service handler;
            # it does not claim that a cloud/device action physically succeeded.
            # context: действие инициировал человек (см. _owner_context выше)
            await self.hass.services.async_call(
                domain, service, service_data, blocking=True,
                context=_owner_context(self.hass),
            )
        except Exception:
            return _json({"error": "service_failed"}, status=502)

        result: dict[str, Any] = {"ok": True}
        if entity_id:
            current = self.hass.states.get(entity_id)
            if current is None:
                result["state"] = None
            else:
                result["state"] = _state_obj(current)
        return _json(result)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.http.register_view(MiniAppAuthView(hass))
    hass.http.register_view(MiniAppStateView(hass))
    hass.http.register_view(MiniAppCalendarView(hass))
    hass.http.register_view(MiniAppActionView(hass))
    return True
