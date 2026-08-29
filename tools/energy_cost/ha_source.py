"""READ-ONLY Home Assistant data source for the interval cost model.

This module ONLY reads from Home Assistant. It never calls a service, never
writes state, never reloads or restarts anything. It converts HA recorder data
into the ``Reading`` / ``PricePoint`` objects consumed by ``model``.

Two data planes exist in HA and matter for cost accuracy:

1. STATES HISTORY (REST ``/api/history/period``) — every state change.
   * Retention: recorder ``purge_keep_days`` (default 10 days; this box has no
     ``recorder:`` key, so 10 days).
   * Gives the EXACT per-15-min Nord Pool price and the raw counter readings
     (including ``unavailable``), so it supports EXACT per-interval cost — but
     only for the last ~10 days.

2. LONG-TERM STATISTICS (WebSocket ``recorder/statistics_during_period``) —
   kept indefinitely.
   * Energy sensors: hourly ``sum`` (exact hourly kWh) + ``state``.
   * Price sensor: hourly ``mean`` / ``min`` / ``max`` (``has_sum=false``).
     There is NO stored per-15-min price in long-term stats, and hourly-mean
     price is consumption-agnostic, so long-term stats can only APPROXIMATE
     per-interval cost (hourly_kWh * hourly_mean_price). 5-minute short-term
     statistics (also ~10-day retention) DO reconstruct per-quarter cost
     exactly because price is constant within each 15-min slot.

Practical consequence (documented in ENERGY_COST_MODEL.md): exact interval cost
is only reconstructable for ~10 days back. For correct long-term monthly totals
you must ACCUMULATE per-interval cost going forward.

Requires the ``HA_TOKEN`` secret (read in-process via project_secrets; never
printed). The WebSocket helper needs no extra dependency — it speaks the wire
protocol over a stdlib socket.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from project_secrets import secret  # noqa: E402

from .model import PricePoint, Reading  # noqa: E402

UTC = timezone.utc

PRICE_SENSOR = "sensor.nord_pool_lv_current_price"
PRICE_STEP = timedelta(minutes=15)  # LV Nord Pool market interval (verified 2026-07-15)


def _base_url() -> str:
    host = secret("HA_HOST", "")
    port = secret("HA_PORT", "8123")
    return secret("HA_BASE_URL", f"http://{host}:{port}")


def _headers() -> dict:
    tok = secret("HA_TOKEN", required=True)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# --------------------------------------------------------------------------- #
# States history (exact, ~10 day retention)
# --------------------------------------------------------------------------- #
def fetch_readings(entity_id: str, start: datetime, end: datetime) -> list[Reading]:
    """Cumulative-counter readings from states history. ``unavailable`` /
    ``unknown`` become ``Reading(value=None)`` gap markers, never 0."""
    import urllib.parse
    import urllib.request

    q = urllib.parse.urlencode(
        {"filter_entity_id": entity_id, "end_time": end.astimezone(UTC).isoformat()}
    )
    url = f"{_base_url()}/api/history/period/{start.astimezone(UTC).isoformat()}?{q}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    out: list[Reading] = []
    for series in data:
        for p in series:
            ts = datetime.fromisoformat(p["last_changed"])
            st = p["state"]
            if st in ("unavailable", "unknown", "", None):
                out.append(Reading(ts, None))
            else:
                try:
                    out.append(Reading(ts, float(st)))
                except ValueError:
                    out.append(Reading(ts, None))
    out.sort(key=lambda x: x.ts)
    return out


def fetch_prices(start: datetime, end: datetime) -> list[PricePoint]:
    """Exact per-15-min Nord Pool prices from the price sensor's state history.

    Each recorded state is the price valid from its timestamp until the next
    change. We snap to a 15-min grid for tidy [start,end) windows.
    """
    import urllib.parse
    import urllib.request

    q = urllib.parse.urlencode(
        {"filter_entity_id": PRICE_SENSOR, "end_time": end.astimezone(UTC).isoformat()}
    )
    url = f"{_base_url()}/api/history/period/{start.astimezone(UTC).isoformat()}?{q}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    raw: list[tuple[datetime, Optional[float]]] = []
    for series in data:
        for p in series:
            ts = datetime.fromisoformat(p["last_changed"]).astimezone(UTC)
            st = p["state"]
            try:
                raw.append((ts, float(st)))
            except (ValueError, TypeError):
                raw.append((ts, None))
    raw.sort(key=lambda x: x[0])
    points: list[PricePoint] = []
    for i, (ts, val) in enumerate(raw):
        nxt = raw[i + 1][0] if i + 1 < len(raw) else end.astimezone(UTC)
        if nxt > ts:
            points.append(PricePoint(ts, nxt, val))
    return points


# --------------------------------------------------------------------------- #
# Long-term / short-term statistics (WebSocket, read-only)
# --------------------------------------------------------------------------- #
class _WS:
    """Minimal WebSocket client for HA recorder statistics. Read-only usage."""

    def __init__(self) -> None:
        host = secret("HA_HOST", "")
        port = int(secret("HA_PORT", "8123"))
        self.s = socket.create_connection((host, port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(
            (
                f"GET /api/websocket HTTP/1.1\r\nHost: {host}:{port}\r\n"
                "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.s.recv(4096)
        self._recv()  # auth_required
        self._send({"type": "auth", "access_token": secret("HA_TOKEN", required=True)})
        self._recv()  # auth_ok
        self._id = 0

    def _send(self, obj: dict) -> None:
        data = json.dumps(obj).encode()
        hdr = bytearray([0x81])
        n = len(data)
        mask = os.urandom(4)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        hdr += mask
        self.s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _recv(self) -> dict:
        def rd(n: int) -> bytes:
            b = b""
            while len(b) < n:
                c = self.s.recv(n - len(b))
                if not c:
                    raise EOFError
                b += c
            return b

        h = rd(2)
        ln = h[1] & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", rd(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", rd(8))[0]
        return json.loads(rd(ln).decode())

    def cmd(self, payload: dict) -> dict:
        self._id += 1
        payload["id"] = self._id
        self._send(payload)
        while True:
            m = self._recv()
            if m.get("id") == self._id and m.get("type") == "result":
                return m

    def close(self) -> None:
        try:
            self.s.close()
        except Exception:
            pass


def fetch_statistics(
    entity_ids: list[str], start: datetime, end: datetime, period: str = "hour"
) -> dict:
    """Recorder statistics (read-only). period in {'5minute','hour','day','month'}.
    Energy ids carry 'sum'/'state'; the price id carries 'mean'/'min'/'max'."""
    ws = _WS()
    try:
        r = ws.cmd(
            {
                "type": "recorder/statistics_during_period",
                "start_time": start.astimezone(UTC).isoformat(),
                "end_time": end.astimezone(UTC).isoformat(),
                "statistic_ids": entity_ids,
                "period": period,
            }
        )
        return r.get("result", {})
    finally:
        ws.close()


__all__ = [
    "PRICE_SENSOR",
    "PRICE_STEP",
    "fetch_readings",
    "fetch_prices",
    "fetch_statistics",
]
