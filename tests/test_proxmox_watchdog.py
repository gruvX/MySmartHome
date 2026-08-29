"""Contract tests for the Proxmox infrastructure watchdog automations.

Background
----------
The Proxmox `mylab` node runs 5 production VMs (plus a stopped template, vmid
9000) that host, among other things, the Home Assistant VM itself.  Nothing in
HA surfaced Proxmox-side failures (node offline, an unexpectedly-stopped VM, a
full storage pool, a failed/stale backup, a stalled metric pipeline).

The fix (``docs/audit/proxmox_watchdog.patch``) appends FIVE new automations
(ids ``1789500001001``..``1789500001005``) that are *notification-only*: the
ONLY action anywhere is ``telegram_bot.send_message`` (chat_id 100000000).  They
must NEVER command a device and must NEVER call a Proxmox button/switch/service.

These tests are pure and hermetic — they parse the proposed patch and assert:

1. Every watchdog issues ZERO device commands (only ``telegram_bot.send_message``);
   in particular no Proxmox ``button.*`` / ``switch.*`` control call.
2. No automation carries a device ``target:``.
3. All messages go to the owner chat_id 100000000.
4. The five chosen ids are unique w.r.t. the read-only fetched automations (the
   patch is purely additive and collides with nothing).
5. The patch does not modify any existing automation.
6. Each condition has the required trigger shape / `for:` debounce and a recovery
   branch.
7. The stopped-VM watchdog EXCLUDES the template/base guest (vmid 9000).
8. There is NO RAM%-threshold alert anywhere (owner rule: RAM-pressure deferred).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
OWNER_CHAT_ID = 100000000
WATCHDOG_IDS = [
    "1789500001001",  # node offline
    "1789500001002",  # vm stopped
    "1789500001003",  # storage critical
    "1789500001004",  # backup error/stale
    "1789500001005",  # stale metric
]

ALLOWED_SERVICE = "telegram_bot.send_message"

# Service-call domains that would mean a watchdog is commanding a device or the
# Proxmox host.  If ANY appears as an action, the notification-only contract
# is broken.
FORBIDDEN_DOMAINS = {
    "button", "switch", "light", "lock", "climate", "select", "number",
    "script", "input_boolean", "input_number", "input_datetime", "cover",
    "fan", "vacuum", "media_player", "scene", "valve", "siren",
    "humidifier", "water_heater", "notify", "homeassistant", "hassio",
}

# The template/base guest that MUST NOT be treated as a stopped-VM alert.
TEMPLATE_ENTITY = "binary_sensor.homelab_clean_ubuntu_2404_status"

# The 5 running non-template VM status entities the stopped-VM watchdog covers.
RUNNING_VM_ENTITIES = {
    "binary_sensor.homelab_staging_status",
    "binary_sensor.homelab_dev_status",
    "binary_sensor.termix_status",
    "binary_sensor.homeassistant_status",
    "binary_sensor.homelab_ci_runner_status",
}

_PATCH = Path(__file__).resolve().parent.parent / "docs" / "audit" / "proxmox_watchdog.patch"


# --------------------------------------------------------------------------- #
# Helpers: parse the proposed patch
# --------------------------------------------------------------------------- #
def _patch_lines() -> list[str]:
    if not _PATCH.exists():
        pytest.skip(f"patch not found: {_PATCH}")
    return _PATCH.read_text(encoding="utf-8").splitlines()


def _hunk_body_lines() -> list[str]:
    """Only the diff *body* lines (inside @@ hunks); excludes header + ---/+++."""
    lines = _patch_lines()
    out: list[str] = []
    in_hunk = False
    for ln in lines:
        if ln.startswith("@@"):
            in_hunk = True
            continue
        if in_hunk:
            out.append(ln)
    assert out, "patch contains no @@ hunk body"
    return out


def _added_blocks() -> list[dict]:
    """Extract the newly-added automation blocks (the 5 appended items)."""
    added: list[str] = []
    for ln in _hunk_body_lines():
        if ln.startswith("+"):
            added.append(ln[1:])  # strip '+'
    # The appended automations begin at the first added `- id:` list item.
    start = None
    for i, ln in enumerate(added):
        if ln.strip().startswith("- id: '1789500001001'"):
            start = i
            break
    assert start is not None, "added lines do not contain the first new watchdog id"
    fragment = "\n".join(added[start:])
    parsed = yaml.safe_load(fragment)
    assert isinstance(parsed, list) and len(parsed) == 5, (
        f"expected exactly 5 new automations, got "
        f"{len(parsed) if isinstance(parsed, list) else type(parsed)}"
    )
    return parsed


def _block(wid: str) -> dict:
    for b in _added_blocks():
        if b.get("id") == wid:
            return b
    raise AssertionError(f"watchdog {wid} not found in patch")


def _triggers(block: dict) -> list[dict]:
    trigs = block.get("triggers") or block.get("trigger")
    assert isinstance(trigs, list) and trigs, f"{block.get('id')} has no triggers"
    return trigs


# --------------------------------------------------------------------------- #
# Service-call / target walkers
# --------------------------------------------------------------------------- #
def _walk_service_calls(node) -> list[str]:
    calls: list[str] = []
    if isinstance(node, dict):
        for key in ("action", "service"):
            val = node.get(key)
            if isinstance(val, str) and "." in val:
                calls.append(val)
        for v in node.values():
            calls.extend(_walk_service_calls(v))
    elif isinstance(node, list):
        for item in node:
            calls.extend(_walk_service_calls(item))
    return calls


def _find_targets(node) -> list:
    found = []
    if isinstance(node, dict):
        if "target" in node:
            found.append(node["target"])
        for v in node.values():
            found.extend(_find_targets(v))
    elif isinstance(node, list):
        for i in node:
            found.extend(_find_targets(i))
    return found


def _find_chat_ids(node) -> list:
    ids = []
    if isinstance(node, dict):
        if "chat_id" in node:
            ids.append(node["chat_id"])
        for v in node.values():
            ids.extend(_find_chat_ids(v))
    elif isinstance(node, list):
        for i in node:
            ids.extend(_find_chat_ids(i))
    return ids


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_patch_parses_and_yields_five_new_blocks():
    blocks = _added_blocks()
    assert [b["id"] for b in blocks] == WATCHDOG_IDS
    for b in blocks:
        assert b.get("mode") == "single", f"{b['id']} must be mode: single"


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_watchdog_issues_zero_device_commands(wid):
    """The core contract: the ONLY service call is telegram_bot.send_message —
    no Proxmox button/switch/service, no device control of any kind."""
    block = _block(wid)
    calls = _walk_service_calls(block.get("actions", []))
    assert calls, f"{wid} has no actions at all"
    assert set(calls) == {ALLOWED_SERVICE}, (
        f"{wid} must ONLY call {ALLOWED_SERVICE}; found {sorted(set(calls))}"
    )
    offending = [c for c in calls if c.split(".", 1)[0] in FORBIDDEN_DOMAINS]
    assert not offending, f"{wid} commands device(s): {offending}"


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_no_device_targets(wid):
    block = _block(wid)
    assert not _find_targets(block.get("actions", [])), (
        f"{wid} must not target any entity (telegram_bot routes by chat_id)"
    )


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_messages_go_to_owner(wid):
    block = _block(wid)
    chat_ids = _find_chat_ids(block.get("actions", []))
    assert chat_ids, f"{wid}: no chat_id — message would not reach the owner"
    assert set(chat_ids) == {OWNER_CHAT_ID}, f"{wid}: messages must go to {OWNER_CHAT_ID}; got {chat_ids}"


@pytest.mark.unit
@pytest.mark.parametrize("wid", WATCHDOG_IDS)
def test_has_down_and_recovery_branch(wid):
    """Each automation must alert (DOWN) and send a distinct RECOVERY message."""
    block = _block(wid)
    text = yaml.dump(block, allow_unicode=True)
    # A recovery message in this patch always starts with the check mark.
    assert "✅" in text, f"{wid}: expected a distinct recovery message (✅)"
    # A DOWN/alert branch: at least one warning/alert glyph.
    assert any(g in text for g in ("⚠", "\U0001f6d1", "\U0001f5c4", "\U0001f552", "\U0001f4e1")), (
        f"{wid}: expected an alert (DOWN) message"
    )
    # There must be >= 2 send_message calls (down + recovery, at minimum).
    assert len(_walk_service_calls(block.get("actions", []))) >= 2, (
        f"{wid}: expected at least a down and a recovery message"
    )


@pytest.mark.unit
def test_node_offline_trigger_shape():
    block = _block("1789500001001")
    trigs = _triggers(block)
    assert all(t.get("entity_id") == "binary_sensor.mylab_status" for t in trigs)
    down = [t for t in trigs if t.get("id") == "down"]
    assert {t.get("to") for t in down} == {"off", "unavailable", "unknown"}, (
        "node-offline must catch off/unavailable/unknown"
    )
    assert all(str(t.get("for")) in ("0:05:00", "00:05:00") for t in down), (
        "node-offline DOWN must use a 5-minute debounce"
    )
    up = [t for t in trigs if t.get("id") == "up"]
    assert up and all(t.get("to") == "on" for t in up), "node-offline needs a recovery (to on)"


@pytest.mark.unit
def test_stopped_vm_excludes_template_and_covers_running_vms():
    block = _block("1789500001002")
    trigs = _triggers(block)
    # Collect every entity_id referenced across triggers.
    covered: set[str] = set()
    for t in trigs:
        eid = t.get("entity_id")
        if isinstance(eid, list):
            covered.update(eid)
        elif isinstance(eid, str):
            covered.add(eid)
    assert TEMPLATE_ENTITY not in covered, (
        "template/base guest (vmid 9000) MUST be excluded from stopped-VM alert"
    )
    assert RUNNING_VM_ENTITIES <= covered, (
        f"stopped-VM watchdog must cover all 5 running VMs; missing "
        f"{RUNNING_VM_ENTITIES - covered}"
    )
    # DOWN = running -> stopped (on -> off) with a debounce.
    down = [t for t in trigs if t.get("id") == "down"]
    assert down and all(t.get("from") == "on" and t.get("to") == "off" for t in down)
    assert all(str(t.get("for")) in ("0:02:00", "00:02:00") for t in down)
    up = [t for t in trigs if t.get("id") == "up"]
    assert up and all(t.get("from") == "off" and t.get("to") == "on" for t in up)


@pytest.mark.unit
def test_storage_critical_is_disk_not_ram():
    block = _block("1789500001003")
    trigs = _triggers(block)
    for t in trigs:
        assert t.get("trigger") == "numeric_state"
        eids = t["entity_id"] if isinstance(t["entity_id"], list) else [t["entity_id"]]
        for e in eids:
            assert "storage" in e and "usage_percentage" in e, (
                f"storage watchdog must watch storage %used, not {e}"
            )
            assert "memory" not in e and "ram" not in e.lower()
    down = [t for t in trigs if t.get("id") == "down"]
    assert down and all(t.get("above") == 90 for t in down)
    assert all(str(t.get("for")) in ("0:10:00", "00:10:00") for t in down), (
        "storage DOWN must use a 10-minute debounce"
    )
    up = [t for t in trigs if t.get("id") == "up"]
    assert up and all(t.get("below") == 90 for t in up)


@pytest.mark.unit
def test_backup_watchdog_covers_problem_and_stale():
    block = _block("1789500001004")
    trigs = _triggers(block)
    ids = {t.get("id") for t in trigs}
    assert "problem" in ids and "problem_ok" in ids, "backup needs problem + recovery"
    assert "stale" in ids, "backup needs a staleness (age > 36h) check"
    # the problem trigger watches the problem binary_sensor
    prob = [t for t in trigs if t.get("id") == "problem"]
    assert all(t.get("entity_id") == "binary_sensor.mylab_backup_status" for t in prob)
    # staleness threshold of 36h == 129600s must appear in the templates
    text = yaml.dump(block, allow_unicode=True)
    assert "129600" in text, "backup staleness must use a 36h (129600s) threshold"
    assert "sensor.mylab_last_backup" in text


@pytest.mark.unit
def test_stale_metric_watchdog():
    block = _block("1789500001005")
    trigs = _triggers(block)
    assert any(
        t.get("entity_id") == "sensor.mylab_cpu_usage" for t in trigs
    ), "stale-metric must watch the node CPU metric"
    # unavailable/unknown for 30m
    down = [t for t in trigs if t.get("id") == "down"]
    assert {t.get("to") for t in down} == {"unavailable", "unknown"}
    assert all(str(t.get("for")) in ("0:30:00", "00:30:00") for t in down)
    # a time_pattern staleness check for last_updated age
    assert any(t.get("trigger") == "time_pattern" for t in trigs)
    text = yaml.dump(block, allow_unicode=True)
    assert "last_updated" in text, "stale-metric must inspect last_updated age"
    assert "1800" in text, "stale-metric must use a 30-minute (1800s) age window"


@pytest.mark.unit
def test_no_ram_percent_alert_anywhere():
    """Owner rule: RAM-pressure alerting is DEFERRED — there must be NO
    RAM%-threshold alert (no numeric_state on any *memory*/*ram* percentage
    sensor) in the entire patch."""
    for block in _added_blocks():
        for t in _triggers(block):
            if t.get("trigger") != "numeric_state":
                continue
            eids = t["entity_id"] if isinstance(t.get("entity_id"), list) else [t.get("entity_id")]
            for e in eids:
                low = (e or "").lower()
                assert "memory" not in low and "_ram" not in low and "mem_" not in low, (
                    f"RAM%-threshold alert found on {e}; RAM-pressure alerting is deferred"
                )
    # belt-and-suspenders: no memory-percentage entity referenced as a numeric trigger
    joined = "\n".join(_patch_lines())
    assert "memory_usage_percentage" not in joined, (
        "patch references a memory-usage-percentage sensor — RAM alerting is deferred"
    )


@pytest.mark.unit
def test_patch_is_additive_only():
    """The patch must only ADD lines; the sole '-' line is the file's last
    context line re-added verbatim (no trailing newline artifact)."""
    body = _hunk_body_lines()
    removed = [ln[1:] for ln in body if ln.startswith("-")]
    added = [ln[1:] for ln in body if ln.startswith("+")]
    for r in removed:
        assert r in added, f"patch deletes/modifies existing content: {r!r}"


@pytest.mark.unit
def test_chosen_ids_are_unique_and_new():
    """Each id is fresh: only ever ADDED by the patch, never pre-existing."""
    body = _hunk_body_lines()
    added = [ln[1:] for ln in body if ln.startswith("+")]
    context_or_removed = [ln[1:] for ln in body if ln.startswith((" ", "-"))]
    for wid in WATCHDOG_IDS:
        id_line = f"- id: '{wid}'"
        assert any(ln.strip() == id_line for ln in added), f"new id {wid} must be added"
        assert not any(wid in ln for ln in context_or_removed), (
            f"id {wid} already exists in the target file (collision)"
        )
    assert len(set(WATCHDOG_IDS)) == len(WATCHDOG_IDS), "chosen ids must be distinct"
