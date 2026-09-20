"""Measure what one small instance carries, with no model in the loop.

Why this exists: half of DarwinLens (the Overview and the ten guided analyses) never calls a
model, so its ceiling is CPU, memory and the session store — not a token quota. That ceiling is
the number you need to size a host, and it is the one number the eval harness cannot tell you.
The model tier has a completely different, quota-bound limit and is deliberately out of scope
here: nothing in this script sends a question to `/ask`, and the server is started without an
`--env-file`, so no provider key is even in its environment.

What it does: starts the API itself on :8050 from this checkout with the hosted memory settings
and the abuse limits raised out of the way, walks N simulated analysts through a realistic
no-model journey in parallel (guest token -> session -> sample data -> catalog -> dashboard ->
picker -> four guided analyses -> preview -> delete), samples the server's resident memory with
`ps` once a second, then runs one round where three analysts upload the 15 MB attendance file at
the same time so the one-ingest-at-a-time gate can be seen answering its human 429.

Run it:  uv run python scripts/loadtest.py            (rounds of 5, 15, 30)
         uv run python scripts/loadtest.py --rounds 5 (one round)
         uv run python scripts/loadtest.py --selftest (the arithmetic, no server)

Raw numbers land in scripts/.loadtest/<timestamp>.json; docs/CAPACITY.md is written from them
by hand. Stdlib only, so it runs anywhere the app runs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path(__file__).resolve().parent / ".loadtest"
PORT = 8050
BASE = f"http://127.0.0.1:{PORT}"
BIG_FILE = ROOT / "test_files" / "attendance_punches_2025.csv"

# The hosted shape we are measuring, plus the abuse limits pushed out of the way so the test
# measures the machine rather than the limiter. MAX_SESSIONS, DUCKDB_* and CROSSCHECK are the
# deployment's real values (render.yaml's 512 MB tier); the rest are test-only.
SERVER_ENV = {
    "DUCKDB_MEMORY_LIMIT": "256MB",
    "DUCKDB_THREADS": "2",
    "MAX_SESSIONS": "12",
    "CROSSCHECK": "off",
    # Raised for the test only. A real deploy keeps these small; see docs/CAPACITY.md.
    "SESSIONS_PER_IP_PER_HOUR": "100000",
    "UPLOADS_PER_IP_PER_HOUR": "100000",
    "ASKS_PER_IP_PER_HOUR": "100000",
    "ASKS_PER_IP_PER_DAY": "100000",
    "ASKS_PER_SESSION": "100000",
    "MAX_CONCURRENT_ASKS": "100",
    "MAX_CONCURRENT_ASKS_PER_IP": "100",
}
# Not raisable: app.limits hard-codes GUESTS_PER_HOUR = 20 per address, so the test mints one
# guest per round and shares it, the way one browser session would be shared by one analyst.
GUEST_BUDGET_NOTE = "GUESTS_PER_HOUR is hard-coded at 20/address; one guest is minted per round."

# Tried in order; the first four that can be filled from the session's own columns are run.
# Every kind here takes only required inputs that a demo_data column can satisfy.
ANALYSIS_KINDS = ("breakdown", "trend", "top_n", "distribution", "share")


# --------------------------------------------------------------------------- measurement


@dataclass
class Sample:
    route: str
    status: int
    ms: float


@dataclass
class Recorder:
    """Samples from every thread in one round. Appends under a lock; lists are not atomic."""

    samples: list[Sample] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, route: str, status: int, ms: float) -> None:
        with self._lock:
            self.samples.append(Sample(route, status, ms))


def _pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest sample at or above p% of the sorted list.

    No interpolation, because with 5 to 30 journeys per route the p95 should be a latency that
    actually happened, not an average of two that did not.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def summarise(samples: list[Sample]) -> dict[str, dict]:
    """Per route: how many calls, how many failed, and the latency of the ones that worked.

    Percentiles cover successful calls only. A 404 from an evicted session answers in under a
    millisecond, and letting those into the p50 would make a saturated server look fast.
    """
    routes: dict[str, dict] = {}
    for sample in samples:
        row = routes.setdefault(sample.route, {"count": 0, "ok": 0, "statuses": {}, "_ok_ms": []})
        row["count"] += 1
        row["statuses"][str(sample.status)] = row["statuses"].get(str(sample.status), 0) + 1
        if 200 <= sample.status < 300:
            row["ok"] += 1
            row["_ok_ms"].append(sample.ms)
    for row in routes.values():
        ms = row.pop("_ok_ms")
        row["errors"] = row["count"] - row["ok"]
        row["p50_ms"] = round(_pct(ms, 50), 1)
        row["p95_ms"] = round(_pct(ms, 95), 1)
        row["max_ms"] = round(max(ms), 1) if ms else 0.0
    return routes


class MemorySampler:
    """The server process's resident size, once a second, via `ps`.

    RSS from the OS rather than anything inside the process: the number that gets a container
    OOM-killed is the one the kernel counts, and DuckDB's arena is not visible to Python.
    """

    def __init__(self, pid: int, period_s: float = 1.0) -> None:
        self.pid, self._period = pid, period_s
        self._stop = threading.Event()
        self.samples: list[tuple[float, float]] = []  # (monotonic, MB)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.wait(self._period):
            mb = rss_mb(self.pid)
            if mb is not None:
                self.samples.append((time.monotonic(), mb))

    def start(self) -> None:
        mb = rss_mb(self.pid)
        if mb is not None:
            self.samples.append((time.monotonic(), mb))
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def between(self, start: float, end: float) -> list[float]:
        return [mb for t, mb in self.samples if start <= t <= end]


def rss_mb(pid: int) -> float | None:
    """Resident set size in MB, or None once the process is gone."""
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                             capture_output=True, text=True, timeout=5, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return round(int(out) / 1024, 1) if out.isdigit() else None


# --------------------------------------------------------------------------- HTTP


def call(method: str, path: str, token: str = "", body: object = None, timeout: float = 120.0,
         raw: tuple[str, bytes] | None = None) -> tuple[int, dict | list | None, float]:
    """One request. Returns (status, decoded JSON or None, elapsed ms). Never raises for HTTP.

    An error status is data here, not an exception: a 429 from the ingest gate and a 404 from an
    evicted session are both results this test exists to count.
    """
    data, headers = None, {"Accept": "application/json"}
    if raw is not None:
        headers["Content-Type"], data = raw
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            status = response.status
    except urllib.error.HTTPError as e:
        payload, status = e.read(), e.code
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # A connection that never answered is a failure of the server under load, so it is
        # recorded as one (599) rather than crashing the analyst's thread.
        return 599, {"error": type(e).__name__}, (time.monotonic() - started) * 1000
    elapsed = (time.monotonic() - started) * 1000
    try:
        return status, json.loads(payload) if payload else None, elapsed
    except ValueError:
        return status, None, elapsed


def multipart(filename: str, data: bytes, content_type: str = "text/csv") -> tuple[str, bytes]:
    """A one-file multipart body for the `files` field, built by hand: no requests, no httpx."""
    boundary = uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n").encode()
    return f"multipart/form-data; boundary={boundary}", head + data + f"\r\n--{boundary}--\r\n".encode()


def guest_token(rec: Recorder) -> str:
    """A bearer token for a guest, or "" if this build has no accounts yet.

    The accounts layer is landing while this was written, so a 404 here is a valid answer: the
    journey then runs unauthenticated, which is what the app did last week.
    """
    status, body, ms = call("POST", "/api/auth/guest")
    rec.add("POST /api/auth/guest", status, ms)
    return body.get("token", "") if status == 200 and isinstance(body, dict) else ""


# --------------------------------------------------------------------------- the journey


def pick_requests(catalog: dict) -> list[dict]:
    """Four guided analyses of different kinds, built from this session's own picker.

    Inputs are filled from one table at a time so a request never needs a join the analyst has
    not confirmed — `sqlbuild.from_clause` refuses an unlinked one, and a refusal is a 422, not
    a measurement. Optional inputs are left blank and options left out, so each analysis runs
    with the picker's own defaults.
    """
    kinds = {k["key"]: k for k in catalog.get("kinds", [])}
    by_table: dict[str, dict[str, str]] = {}  # table -> column kind -> first ref of that kind
    for column in catalog.get("columns", []):
        table = column["ref"].split(".")[0]
        by_table.setdefault(table, {}).setdefault(column["kind"], column["ref"])

    requests: list[dict] = []
    for key in ANALYSIS_KINDS:
        kind = kinds.get(key)
        if kind is None:
            continue
        needed = [slot for slot in kind["inputs"] if not slot.get("optional")]
        for columns in by_table.values():
            filled = {slot["key"]: next((columns[k] for k in slot["accepts"] if k in columns), "")
                      for slot in needed}
            if all(filled.values()):
                requests.append({"kind": key, "inputs": filled, "options": {}})
                break
        if len(requests) == 4:
            break
    return requests


def journey(rec: Recorder, token: str) -> str:
    """One analyst, start to finish. Returns "done", "evicted" or "failed".

    "evicted" is its own outcome because it is not a fault: MAX_SESSIONS is an LRU, so past that
    many concurrent analysts the store drops the least recently used one and its owner gets the
    app's human 404. Counting that as an error would hide what the number actually means.
    """
    status, body, ms = call("POST", "/api/sessions", token)
    rec.add("POST /api/sessions", status, ms)
    if status != 200 or not isinstance(body, dict):
        return "failed"
    sid = body["session_id"]
    prefix = f"/api/sessions/{sid}"

    # The sample is read in under `limits.ingest()`, which admits one file at a time for the
    # whole host. A busy analyst retries; 20 tries covers a round of 30 queueing behind a
    # sample load that takes about a third of a second on its own.
    for attempt in range(20):
        status, _, ms = call("POST", f"{prefix}/sample", token)
        rec.add("POST /sample", status, ms)
        if status != 429:
            break
        time.sleep(0.5 + 0.1 * attempt)
    if status == 404:
        return "evicted"
    if status != 200:
        return "failed"

    steps: list[tuple[str, str, str, object]] = [
        ("GET /catalog", "GET", f"{prefix}/catalog", None),
        ("GET /dashboard", "GET", f"{prefix}/dashboard", None),
        ("GET /analyses", "GET", f"{prefix}/analyses", None),
    ]
    picker: dict = {}
    tables: list[str] = []
    for label, method, path, payload in steps:
        status, result, ms = call(method, path, token, payload)
        rec.add(label, status, ms)
        if status == 404:
            return "evicted"
        if status != 200:
            return "failed"
        if label == "GET /analyses" and isinstance(result, dict):
            picker = result
        if label == "GET /catalog" and isinstance(result, dict):
            tables = [t["name"] for t in result.get("tables", []) if not t.get("is_view")]

    for request in pick_requests(picker):
        status, _, ms = call("POST", f"{prefix}/analyses/run", token, request)
        rec.add(f"POST /analyses/run [{request['kind']}]", status, ms)
        if status == 404:
            return "evicted"

    if tables:
        status, _, ms = call("GET", f"{prefix}/tables/{tables[0]}/preview?limit=50", token)
        rec.add("GET /preview", status, ms)
        if status == 404:
            return "evicted"

    status, _, ms = call("DELETE", prefix, token)
    rec.add("DELETE /sessions/{id}", status, ms)
    return "done" if status == 204 else "failed"


def run_round(analysts: int, memory: MemorySampler) -> dict:
    """N analysts through the journey at once, with the memory window around them."""
    rec = Recorder()
    token = guest_token(rec)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=analysts) as pool:
        outcomes = list(pool.map(lambda _: journey(rec, token), range(analysts)))
    wall_s = time.monotonic() - started
    peak = memory.between(started, time.monotonic())
    time.sleep(3)  # let the deleted sessions' connections close before reading "at rest"
    rest = rss_mb(memory.pid)
    return {
        "analysts": analysts,
        "wall_s": round(wall_s, 2),
        "completed": outcomes.count("done"),
        "evicted": outcomes.count("evicted"),
        "failed": outcomes.count("failed"),
        "peak_rss_mb": max(peak) if peak else 0.0,
        "rest_rss_mb": rest,
        "routes": summarise(rec.samples),
    }


def run_ingest_round(memory: MemorySampler) -> dict:
    """Three analysts upload the same 15 MB file at once.

    The point is the refusal, not the throughput: `limits.ingest()` holds a single semaphore for
    the whole host because reading a spreadsheet in is the memory peak on a small instance, and
    two at once is what kills the process. One upload should be read; the others should get the
    app's two-sentence 429 immediately, and resident memory should stay near one file's cost.
    """
    if not BIG_FILE.exists():
        print(f"  {BIG_FILE.name} missing; generating it (this takes a minute)")
        subprocess.run(["uv", "run", "python", "test_files/generate.py"], cwd=ROOT, check=True)
    payload = BIG_FILE.read_bytes()  # shared by all three: the bytes on the wire are identical
    content_type, body = multipart(BIG_FILE.name, payload)
    rec = Recorder()
    token = guest_token(rec)

    sessions = []
    for _ in range(3):
        status, result, ms = call("POST", "/api/sessions", token)
        rec.add("POST /api/sessions", status, ms)
        if status == 200 and isinstance(result, dict):
            sessions.append(result["session_id"])

    def upload(sid: str) -> int:
        status, _, ms = call("POST", f"/api/sessions/{sid}/files", token,
                             raw=(content_type, body), timeout=600)
        rec.add("POST /files [15 MB]", status, ms)
        return status

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=len(sessions)) as pool:
        statuses = list(pool.map(upload, sessions))
    wall_s = time.monotonic() - started
    peak = memory.between(started, time.monotonic())
    for sid in sessions:
        call("DELETE", f"/api/sessions/{sid}", token)
    time.sleep(3)
    return {
        "file_mb": round(len(payload) / 1024 / 1024, 2),
        "uploads": len(sessions),
        "wall_s": round(wall_s, 2),
        "accepted": sum(1 for s in statuses if s == 200),
        "refused_429": sum(1 for s in statuses if s == 429),
        "other": sorted(s for s in statuses if s not in (200, 429)),
        "peak_rss_mb": max(peak) if peak else 0.0,
        "rest_rss_mb": rss_mb(memory.pid),
        "routes": summarise(rec.samples),
    }


# --------------------------------------------------------------------------- server


def interpreter() -> str:
    """The Python that has the project's dependencies. The venv directly when it is there, so
    the server is one process with one PID for `ps`; `uv` only to find it otherwise."""
    venv = ROOT / ".venv" / "bin" / "python"
    if venv.exists():
        return str(venv)
    out = subprocess.run(["uv", "run", "python", "-c", "import sys; print(sys.executable)"],
                         cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def start_server(work_dir: Path, log_path: Path) -> subprocess.Popen:
    """Start uvicorn on PORT with the test's environment, and wait for /healthz.

    No `--env-file`: the server is started with no provider key in its environment, so the
    no-model claim is enforced by the setup rather than asserted in prose. Nothing here prints
    the environment it built.
    """
    env = {**os.environ, **SERVER_ENV, "WORK_DIR": str(work_dir)}
    log = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [interpreter(), "-m", "uvicorn", "app.main:app", "--app-dir", "backend",
         "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        if proc.poll() is not None:
            raise RuntimeError(f"the server exited during start-up; see {log_path}")
        status, _, _ = call("GET", "/healthz", timeout=2)
        if status == 200:
            return proc
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError(f"the server did not answer /healthz on :{PORT}; see {log_path}")


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def machine() -> dict:
    """Enough about this host that a number in docs/CAPACITY.md can be read in context."""
    def sysctl(name: str) -> str:
        out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, check=False)
        return out.stdout.strip()
    total = sysctl("hw.memsize")
    return {
        "platform": platform.platform(),
        "cpu": sysctl("machdep.cpu.brand_string") or platform.processor(),
        "cpus": os.cpu_count(),
        "ram_gb": round(int(total) / 1024**3, 1) if total.isdigit() else None,
        "python": platform.python_version(),
    }


# --------------------------------------------------------------------------- output


def print_report(report: dict) -> None:
    host = report["machine"]
    print(f"\n  {host['cpu']} | {host['cpus']} CPUs | {host['ram_gb']} GB | python {host['python']}")
    print(f"  MAX_SESSIONS={SERVER_ENV['MAX_SESSIONS']} "
          f"DUCKDB_MEMORY_LIMIT={SERVER_ENV['DUCKDB_MEMORY_LIMIT']} "
          f"DUCKDB_THREADS={SERVER_ENV['DUCKDB_THREADS']} CROSSCHECK=off | no model is called")
    print(f"  idle server: {report['baseline_rss_mb']} MB resident\n")

    print(f"  {'analysts':>8} {'wall s':>7} {'done':>5} {'evicted':>8} {'failed':>7} {'peak MB':>8} {'rest MB':>8}")
    for r in report["rounds"]:
        print(f"  {r['analysts']:>8} {r['wall_s']:>7.1f} {r['completed']:>5} {r['evicted']:>8} "
              f"{r['failed']:>7} {r['peak_rss_mb']:>8.1f} {r['rest_rss_mb']:>8.1f}")

    for r in report["rounds"]:
        print(f"\n  {r['analysts']} analysts at once")
        print(f"  {'route':<34} {'n':>4} {'err':>4} {'p50 ms':>9} {'p95 ms':>9} {'max ms':>9}")
        for name, row in r["routes"].items():
            print(f"  {name:<34} {row['count']:>4} {row['errors']:>4} "
                  f"{row['p50_ms']:>9.1f} {row['p95_ms']:>9.1f} {row['max_ms']:>9.1f}")

    ingest = report.get("ingest_round")
    if ingest:
        print(f"\n  {ingest['uploads']} x {ingest['file_mb']} MB upload at once: "
              f"{ingest['accepted']} read, {ingest['refused_429']} refused with 429, "
              f"peak {ingest['peak_rss_mb']} MB, {ingest['wall_s']}s")
        for name, row in ingest["routes"].items():
            print(f"  {name:<34} {row['count']:>4} {row['errors']:>4} "
                  f"{row['p50_ms']:>9.1f} {row['p95_ms']:>9.1f} {row['max_ms']:>9.1f}")


def selftest() -> None:
    """The one piece of arithmetic worth a check: the percentile and the summary it feeds."""
    assert _pct([], 50) == 0.0
    assert _pct([7.0], 95) == 7.0
    assert _pct([1.0, 2.0, 3.0, 4.0], 50) == 2.0  # nearest rank, no interpolation
    assert _pct(list(map(float, range(1, 101))), 95) == 95.0
    rows = summarise([Sample("a", 200, 10.0), Sample("a", 200, 30.0), Sample("a", 429, 1.0)])
    assert rows["a"] == {"count": 3, "ok": 2, "statuses": {"200": 2, "429": 1},
                         "errors": 1, "p50_ms": 10.0, "p95_ms": 30.0, "max_ms": 30.0}, rows
    picked = pick_requests({
        "kinds": [{"key": "breakdown", "inputs": [{"key": "measure", "accepts": ["measure"]},
                                                  {"key": "by", "accepts": ["category"]}]},
                  {"key": "distribution", "inputs": [{"key": "measure", "accepts": ["measure"]}]}],
        "columns": [{"ref": "pay.gross", "kind": "measure"}, {"ref": "pay.dept", "kind": "category"}]})
    assert [p["kind"] for p in picked] == ["breakdown", "distribution"], picked
    assert picked[0]["inputs"] == {"measure": "pay.gross", "by": "pay.dept"}
    print("selftest ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rounds", type=int, nargs="+", default=[5, 15, 30],
                        help="how many analysts in each round (default: 5 15 30)")
    parser.add_argument("--no-ingest", action="store_true", help="skip the 15 MB upload round")
    parser.add_argument("--selftest", action="store_true", help="check the arithmetic and exit")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = OUT_DIR / f"{stamp}-server.log"
    work_dir = Path(tempfile.mkdtemp(prefix="darwinlens-loadtest-"))
    print(f"starting the API on :{PORT} (no model, no --env-file); server log -> {log_path}")
    proc = start_server(work_dir, log_path)
    memory = MemorySampler(proc.pid)
    report: dict = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "machine": machine(),
                    "server_env": SERVER_ENV, "note": GUEST_BUDGET_NOTE, "rounds": []}
    try:
        memory.start()
        time.sleep(2)  # the first request imports pandas and DuckDB; measure idle after that
        call("GET", "/healthz")
        report["baseline_rss_mb"] = rss_mb(proc.pid)
        for analysts in args.rounds:
            print(f"  round: {analysts} analysts")
            report["rounds"].append(run_round(analysts, memory))
        if not args.no_ingest:
            print("  round: 3 x 15 MB upload at once")
            report["ingest_round"] = run_ingest_round(memory)
        report["rss_samples_mb"] = [mb for _, mb in memory.samples]
    finally:
        memory.stop()
        stop_server(proc)
        shutil.rmtree(work_dir, ignore_errors=True)

    out = OUT_DIR / f"{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_report(report)
    print(f"\n  raw numbers: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
