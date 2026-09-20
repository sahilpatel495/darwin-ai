"""Checks that the packaging files keep the promises the README makes.

Why this exists: Dockerfiles, YAML and .env files have no compiler. A new setting added to
config.py without a line in .env.example, a typo in a Render variable name, or a secret pasted
into a committed file would otherwise be found by a customer. These checks are static and need
no Docker; `make smoke` is the check that builds and runs the real image.

Run from the repo root: uv run pytest .github/scripts -q
"""

from __future__ import annotations

import http.client
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import warm
import yaml
from app.config import DEFAULT_CHAINS

ROOT = Path(__file__).resolve().parents[2]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _config_env_names() -> set[str]:
    """Every environment variable config.py reads: its quoted UPPER_CASE names plus one chain per role."""
    names = set(re.findall(r'"([A-Z][A-Z0-9_]+)"', _read("backend/app/config.py")))
    return names | {f"LLM_{role.upper()}_CHAIN" for role in DEFAULT_CHAINS}


def test_env_example_documents_every_setting() -> None:
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", _read(".env.example"), flags=re.MULTILINE))
    assert _config_env_names() - documented == set()


def test_env_example_sets_nothing_but_empty_api_keys() -> None:
    """A committed file must never carry a secret. Only the key lines are live, and they are
    empty, so a reader sees where keys go and nothing else changes when the file is copied."""
    live = [line for line in _read(".env.example").splitlines() if line and not line.startswith("#")]
    assert live, "expected the API key lines to be uncommented so users can see where keys go"
    for line in live:
        name, _, value = line.partition("=")
        assert name.endswith("_API_KEY") and value == "", line


def test_every_documented_setting_may_be_left_empty() -> None:
    """`cp .env.example .env` and hosting dashboards both produce `NAME=` lines, and .env.example
    promises that means "use the default". Without config._env the app dies on int("") at import.
    A fresh interpreter, because the settings are read once, when app.config is first imported."""
    names = re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", _read(".env.example"), flags=re.MULTILINE)
    env = {**os.environ, **dict.fromkeys(names, ""), "PYTHONPATH": str(ROOT / "backend")}
    code = "from app.config import chain, settings; assert settings.max_upload_mb == 25; assert chain('sql') == []"
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


def test_env_example_shows_the_real_default_chains() -> None:
    """The eval picks the models, so the defaults in config.py will change; the documented ones must follow."""
    example = _read(".env.example")
    for role, default in DEFAULT_CHAINS.items():
        assert f"# LLM_{role.upper()}_CHAIN={default}\n" in example, role


def test_render_blueprint_is_a_free_docker_service_with_no_secrets() -> None:
    (service,) = yaml.safe_load(_read("render.yaml"))["services"]
    assert (service["type"], service["runtime"], service["plan"]) == ("web", "docker", "free")
    assert service["healthCheckPath"] == "/healthz"
    env = {var["key"]: var for var in service["envVars"]}
    # Sized for the free instance: 512 MB of memory and a tenth of a CPU.
    assert env["MAX_UPLOAD_MB"]["value"] == "10"
    assert env["DUCKDB_MEMORY_LIMIT"]["value"] == "256MB"
    assert env["DUCKDB_THREADS"]["value"] == "2"
    for key, var in env.items():
        if key.endswith("_API_KEY"):
            assert var == {"key": key, "sync": False}, f"{key} must be entered in the dashboard"
    # The app silently ignores a variable it does not know, so a typo here would go unnoticed.
    assert set(env) - _config_env_names() == set()


def test_compose_is_one_service_on_port_8000_reading_dotenv() -> None:
    (service,) = yaml.safe_load(_read("docker-compose.yml"))["services"].values()
    assert service["ports"] == ["8000:8000"]
    assert service["env_file"] == [{"path": ".env", "required": False}]
    # The lock-down the README's security table promises.
    assert service["read_only"] is True and service["tmpfs"] == ["/tmp"]
    assert service["cap_drop"] == ["ALL"] and service["security_opt"] == ["no-new-privileges:true"]


def test_build_context_is_an_allow_list_that_never_readmits_secrets() -> None:
    """Allowing a folder allows everything in it, so secrets-shaped names are refused again afterwards.
    Found by building from a context with backend/.git, backend/key.pem and demo_data/prod.env planted."""
    rules = _read(".dockerignore").split("\n")
    rules = [rule for rule in rules if rule and not rule.startswith("#")]
    assert rules[0] == "*", "fail closed: ignore everything, then allow by name"
    last_allow = max(i for i, rule in enumerate(rules) if rule.startswith("!"))
    assert {"**/.env*", "**/*.env", "**/.git", "**/*.pem", "**/*.key"} <= set(rules[last_allow + 1 :])


def test_image_runs_as_a_normal_user_with_one_worker() -> None:
    dockerfile = _read("Dockerfile")
    assert dockerfile.rindex("USER 1000") > dockerfile.rindex("COPY "), "app files must stay root-owned"
    assert "--frozen" in dockerfile and "--no-dev" in dockerfile
    assert "--port ${PORT:-8000}" in dockerfile
    assert "--workers 1" in dockerfile, "sessions live in memory; a second worker would not see them"


def test_ci_runs_backend_tests_and_the_frontend_build() -> None:
    ci = _read(".github/workflows/ci.yml")
    assert yaml.safe_load(ci)["jobs"]
    for command in ("pytest", "pnpm typecheck", "pnpm build"):
        assert command in ci


def test_keepwarm_pings_every_ten_minutes_and_skips_without_a_url() -> None:
    workflow = yaml.safe_load(_read(".github/workflows/keepwarm.yml"))
    triggers = workflow.get("on") or workflow[True]  # YAML 1.1 reads a bare `on` key as boolean true
    assert triggers["schedule"] == [{"cron": "*/10 * * * *"}]
    assert "vars.APP_URL != ''" in workflow["jobs"]["ping"]["if"]


def test_makefile_has_every_target_the_readme_mentions() -> None:
    targets = set(re.findall(r"^([a-z]+):", _read("Makefile"), flags=re.MULTILINE))
    assert {"setup", "dev", "test", "eval", "fixtures", "build", "up", "warm"} <= targets
    # Commands only (in backticks or starting a code line), not the English verb "make".
    assert set(re.findall(r"(?:`|^)make ([a-z]+)", _read("README.md"), flags=re.MULTILINE)) - targets == set()


def test_readme_links_the_documents_a_reviewer_needs() -> None:
    readme = _read("README.md")
    for needle in ("```mermaid", "docs/DESIGN.md", "DECISIONS.md", "WRITEUP.md", "docs/AI_WORKFLOW.md", "Apache-2.0"):
        assert needle in readme
    assert "playwright install" in readme, "on a clean machine the end-to-end test has no browser without it"


def test_warm_reads_the_final_event_and_skips_heartbeats() -> None:
    stream = 'event: step\ndata: {"stage": "generate"}\n\n: ping\n\nevent: answer\ndata: {"kind": "clarify"}\n\n'
    assert warm.last_event(stream) == ("answer", {"kind": "clarify"})
    assert warm.last_event(": ping\n\n")[0] == "error"


@pytest.mark.parametrize(
    "reply",
    ["<html>Service waking up</html>", '{"hello": "world"}', http.client.RemoteDisconnected("closed")],
    ids=["a web page", "some other API", "a dropped connection"],
)
def test_warm_explains_a_bad_reply_in_a_sentence(monkeypatch, capsys, reply) -> None:
    """A mistyped URL or a host that restarts mid-run must end in a sentence and exit 1, not a stack trace."""

    def fake_post(url: str, body: dict | None = None) -> str:
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(warm, "_post", fake_post)
    assert warm.main("https://example.com") == 1
    assert "https://example.com" in capsys.readouterr().out
