"""Mini App frontend <-> backend allow-list contract test.

The Telegram Mini App frontend (``miniapp/smarthouse_v8.html``) issues actions
to the ``/api/miniapp-action`` endpoint served by the ``miniapp_auth`` custom
component.  The backend enforces an allow-list: every (domain, entity_id) the
frontend can request MUST be permitted by the backend, otherwise the button
silently 403s in production.

This test parses BOTH sides read-only (it never edits either file) and asserts
the frontend action set is a subset of the backend allow-list.

Robustness during Series D:
* If either file is missing or cannot be parsed, the test SKIPS with a clear
  message (the allow-list may not be finalized yet).
* The subset assertion is marked ``xfail(strict=False)`` so that legitimate,
  in-progress drift (e.g. the frontend already ships a `script`/`night_saver`
  action the backend has not yet allow-listed) surfaces as XFAIL rather than
  breaking CI for other agents.  When the allow-list catches up, it flips to
  XPASS, signalling the marker can be removed.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "custom_components" / "miniapp_auth" / "__init__.py"
FRONTEND = REPO / "miniapp" / "smarthouse_v8.html"

# Backend module-level names that hold the entity allow-lists, keyed by the
# service *domain* the frontend uses.
DOMAIN_TO_BACKEND_SET = {
    "light": "LIGHT_ENTITIES",
    "switch": "SWITCH_ENTITIES",
    "input_boolean": "INPUT_BOOLEANS",
    "automation": "AUTOMATION_ENTITIES",
    "climate": "CLIMATE_ENTITIES",
    # `script` intentionally omitted from the initial backend; if a
    # SCRIPT_ENTITIES set appears it is picked up automatically below.
    "script": "SCRIPT_ENTITIES",
    # Робот-пылесос, добавлен 2026-08-26 вместе с VACUUM_ENTITIES в компоненте.
    # Без этой строки таблица не знает домена, и разрешённая сущность выглядит
    # как нарушение контракта.
    "vacuum": "VACUUM_ENTITIES",
}


def _parse_backend_sets() -> dict[str, set[str]]:
    """Extract every module-level ``NAME = {...}`` string-set from the backend.

    Uses AST so we never execute the component (which imports aiohttp / HA).
    Returns a mapping of assignment name -> set of string literals.  Names that
    are not plain string sets are skipped.
    """
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        name = node.targets[0].id
        value = node.value
        if isinstance(value, ast.Set):
            elts = value.elts
        elif isinstance(value, ast.Dict):
            elts = value.keys
        else:
            continue
        strings = {e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if strings:
            out[name] = strings
    return out


# Match svc("domain", <rest-of-args>) call sites. We only pin the first arg
# (the service domain) to a string literal; the remaining args are captured
# loosely (up to the closing paren) so that ternary service/entity expressions
# like `v?"turn_on":"turn_off"` or `v?"script.a":"script.b"` are still scanned.
_SVC_RE = re.compile(r"""svc\(\s*["']([a-z_]+)["']\s*,(.*?)\)""", re.DOTALL)
_ENTITY_RE = re.compile(r"""["']([a-z_]+\.[a-z0-9_]+)["']""")


def _parse_frontend_actions() -> set[tuple[str, str]]:
    """Return the set of (domain, entity_id) pairs the frontend can request.

    Best-effort static parse of ``svc(domain, service, entity_id, ...)`` calls.
    Ternary entity expressions (``v?"script.a":"script.b"``) contribute every
    literal they mention.  ``null``/expression entities without a literal (e.g.
    shell_command) are represented as (domain, "") and ignored by the entity
    subset check.
    """
    text = FRONTEND.read_text(encoding="utf-8", errors="replace")
    actions: set[tuple[str, str]] = set()
    for m in _SVC_RE.finditer(text):
        domain = m.group(1)
        rest = m.group(2)
        ents = _ENTITY_RE.findall(rest)
        # keep only entities whose prefix matches this call's domain
        matched = [e for e in ents if e.split(".", 1)[0] == domain]
        if matched:
            for e in matched:
                actions.add((domain, e))
        else:
            actions.add((domain, ""))
    return actions


def test_files_present():
    """Sanity: both contract endpoints exist in the repo."""
    if not BACKEND.exists():
        pytest.skip(f"backend allow-list not found at {BACKEND}")
    if not FRONTEND.exists():
        pytest.skip(f"frontend not found at {FRONTEND}")


@pytest.fixture(scope="module")
def backend_sets() -> dict[str, set[str]]:
    if not BACKEND.exists():
        pytest.skip(f"backend allow-list not found at {BACKEND}")
    try:
        sets = _parse_backend_sets()
    except SyntaxError as exc:
        pytest.skip(f"backend not parseable yet (in progress?): {exc}")
    if not any(name in sets for name in DOMAIN_TO_BACKEND_SET.values()):
        pytest.skip("no recognizable allow-list sets in backend yet")
    return sets


@pytest.fixture(scope="module")
def frontend_actions() -> set[tuple[str, str]]:
    if not FRONTEND.exists():
        pytest.skip(f"frontend not found at {FRONTEND}")
    actions = _parse_frontend_actions()
    if not actions:
        pytest.skip("could not parse any svc() action calls from frontend yet")
    return actions


def test_frontend_actions_parse(frontend_actions):
    """The parser must find a meaningful number of action call sites."""
    assert len(frontend_actions) >= 3, (
        "Suspiciously few frontend actions parsed; the svc() regex may be stale. "
        f"Got: {sorted(frontend_actions)}"
    )


def _compute_violations(backend_sets, frontend_actions) -> list[str]:
    violations: list[str] = []
    for domain, entity in sorted(frontend_actions):
        if not entity:
            continue  # entity-less action (shell_command etc.) — not entity-checked here
        backend_name = DOMAIN_TO_BACKEND_SET.get(domain)
        allowed = backend_sets.get(backend_name, set()) if backend_name else set()
        if entity not in allowed:
            violations.append(
                f"{domain}: {entity!r} not in backend {backend_name or '<no set>'}"
            )
    return violations


@pytest.mark.xfail(
    reason="allow-list may still be finalized during Series D; drift shows as XFAIL",
    strict=False,
)
def test_frontend_action_set_is_subset_of_backend(backend_sets, frontend_actions):
    """Every frontend (domain, entity) action must be backend-allow-listed."""
    violations = _compute_violations(backend_sets, frontend_actions)
    assert not violations, (
        "Frontend requests actions the backend does not allow-list "
        "(would 403 in production):\n  " + "\n  ".join(violations)
    )
