"""Shared test fixtures and network stubs for the MySmartHome test suite.

Goals
-----
* Unit tests must NEVER touch the real Home Assistant instance, the Elering
  price API, or the Tuya cloud.  Every outbound HTTP call made through the
  standard library (``urllib.request``) or ``requests`` (if installed) is
  intercepted by default and raises, so an accidental live call fails loudly
  instead of silently hitting production.
* Tests that genuinely need to exercise a real device are marked ``live`` and
  are deselected by default (see ``pyproject.toml`` / ``pytest_collection_modifyitems``).

Nothing here imports Home Assistant, paramiko, or any project module at import
time, so the suite collects cleanly on a bare CI runner.
"""
from __future__ import annotations

import json
from typing import Any

import pytest


# --------------------------------------------------------------------------- #
# Marker registration + default deselection of live-device tests
# --------------------------------------------------------------------------- #
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "unit: pure, hermetic test (no network, no devices)."
    )
    config.addinivalue_line(
        "markers",
        "integration: multi-module test; hermetic (stubbed HTTP), safe in CI.",
    )
    config.addinivalue_line(
        "markers",
        "live: test hits a real device/network (HA, Elering, Tuya). "
        "Deselected by default; run with `-m live`.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip ``live`` tests unless the user explicitly opts in with ``-m live``.

    We only auto-skip when the ``-m`` expression does not already mention
    ``live``; that way an explicit ``-m live`` (or ``-m "live and foo"``) run
    still executes them.
    """
    markexpr = config.getoption("-m", default="")
    if "live" in markexpr:
        return
    skip_live = pytest.mark.skip(reason="live-device test (run with `-m live`)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# --------------------------------------------------------------------------- #
# Sample data fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def sample_prices() -> list[float]:
    """24 hourly Nord Pool / Elering-style EUR/kWh prices for one day.

    Values are illustrative and deliberately span cheap (< 0.04) and
    expensive (> 0.10) so threshold logic can be exercised both ways.
    """
    return [
        0.021, 0.018, 0.015, 0.014, 0.017, 0.025,  # 00-05 (cheap night)
        0.048, 0.089, 0.132, 0.121, 0.098, 0.087,  # 06-11 (morning peak)
        0.076, 0.071, 0.069, 0.074, 0.093, 0.145,  # 12-17
        0.168, 0.151, 0.112, 0.081, 0.052, 0.033,  # 18-23 (evening peak)
    ]


@pytest.fixture
def elering_response(sample_prices: list[float]) -> dict[str, Any]:
    """Minimal Elering ``/api/nps/price`` JSON shape (EUR/MWh)."""
    return {
        "success": True,
        "data": {
            "lv": [
                {"timestamp": 1_700_000_000 + i * 3600, "price": p * 1000.0}
                for i, p in enumerate(sample_prices)
            ]
        },
    }


@pytest.fixture
def ha_state():
    """Factory building Home-Assistant-style state dicts.

    Usage::

        s = ha_state("sensor.nord_pool_lv_current_price", "0.048")
    """

    def _make(
        entity_id: str,
        state: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "entity_id": entity_id,
            "state": state,
            "attributes": attributes or {},
            "last_changed": "2026-07-15T00:00:00+00:00",
            "last_updated": "2026-07-15T00:00:00+00:00",
        }

    return _make


# --------------------------------------------------------------------------- #
# Fake HTTP layer
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Duck-typed stand-in for both ``urllib`` and ``requests`` responses."""

    def __init__(self, payload: Any = None, status: int = 200) -> None:
        if isinstance(payload, (bytes, bytearray)):
            self._body = bytes(payload)
        elif isinstance(payload, str):
            self._body = payload.encode("utf-8")
        else:
            self._body = json.dumps(payload if payload is not None else {}).encode(
                "utf-8"
            )
        self.status = status
        self.status_code = status  # requests-style alias

    # urllib-style
    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    # requests-style
    def json(self) -> Any:
        return json.loads(self._body.decode("utf-8"))

    @property
    def text(self) -> str:
        return self._body.decode("utf-8")

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


@pytest.fixture
def fake_http(monkeypatch: pytest.MonkeyPatch):
    """Intercept all outbound HTTP and return canned responses.

    Register routes by substring match on the URL::

        def test_x(fake_http):
            fake_http.route("elering.ee", {"success": True})
            ...  # code under test calls urllib/requests -> gets the canned body

    Any unmatched URL raises ``AssertionError`` so stray live calls are caught.
    """

    class _Router:
        def __init__(self) -> None:
            self._routes: list[tuple[str, FakeResponse]] = []
            self.calls: list[str] = []

        def route(self, url_substr: str, payload: Any = None, status: int = 200):
            self._routes.append((url_substr, FakeResponse(payload, status)))
            return self

        def _resolve(self, url: str) -> FakeResponse:
            self.calls.append(url)
            for needle, resp in self._routes:
                if needle in url:
                    return resp
            raise AssertionError(
                f"Unstubbed HTTP call to {url!r}. Tests must not hit the network; "
                f"register it with fake_http.route(...) or mark the test `live`."
            )

    router = _Router()

    def _fake_urlopen(req, *args, **kwargs):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        return router._resolve(url)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen, raising=True)

    # Stub requests.* only if the library is importable.
    try:
        import requests  # type: ignore

        def _fake_request(method, url, *args, **kwargs):
            return router._resolve(url)

        monkeypatch.setattr(requests, "request", _fake_request, raising=True)
        for verb in ("get", "post", "put", "delete", "patch", "head"):
            monkeypatch.setattr(
                requests,
                verb,
                lambda url, *a, _m=verb, **k: router._resolve(url),
                raising=True,
            )
    except Exception:
        pass

    return router


@pytest.fixture(autouse=True)
def _block_stray_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Fail loudly on any un-stubbed network call.

    Active for every test that is NOT marked ``live`` and does NOT already use
    the ``fake_http`` fixture (which installs its own controllable router).
    """
    if request.node.get_closest_marker("live"):
        return
    if "fake_http" in request.fixturenames:
        return

    def _blocked(*args: object, **kwargs: object):
        raise AssertionError(
            "Blocked un-stubbed network call. Use the `fake_http` fixture to "
            "stub responses, or mark the test with `@pytest.mark.live`."
        )

    monkeypatch.setattr("urllib.request.urlopen", _blocked, raising=True)
    try:
        import requests  # type: ignore

        monkeypatch.setattr(requests.sessions.Session, "request", _blocked, raising=True)
    except Exception:
        pass
