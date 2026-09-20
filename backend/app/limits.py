"""Per-user limits, so a public demo on free model quotas cannot be drained or knocked over.

The free tiers give the whole app a few hundred thousand tokens a day, so one visitor in a
loop could use up everybody's answers. There are no accounts, so "a user" is a client IP
address (see `client_ip`). Three small pieces:

- SlidingWindow: "at most N in the last W seconds" per key.
- ConcurrencyGate: "at most N at the same time", in total and per key.
- Limits: the policy. Which limits exist, their sizes (from settings) and their sentences.

A refusal is a LimitExceeded carrying the same two sentences every other API error has (what
happened, what to do next) plus the seconds for a Retry-After header. main.py turns it into a 429.
"""

from __future__ import annotations

import ipaddress
import math
import threading
import time
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.config import Settings

HOUR, DAY = 3600, 86400
BUSY_RETRY_S = 5  # a question takes a few seconds, so a slot is free again about this soon


class LimitExceeded(Exception):
    def __init__(self, message: str, next_step: str, retry_after_s: int):
        super().__init__(message)
        self.message, self.next_step, self.retry_after_s = message, next_step, retry_after_s


def client_ip(forwarded_for: str, socket_host: str | None, hops: int = 1) -> str:
    """The address limits are counted against.

    Each proxy appends the address it saw to X-Forwarded-For, so entries are forgeable from the
    left and trustworthy from the right. `hops` (settings.trusted_proxy_hops) is how many of our
    own proxies are in front: 1 means the nearest one appended the client's address, 2 means a
    CDN appended it and our router then appended the CDN's. Counting from the right is what a
    client cannot shift, because it cannot make our proxies stop appending. A header with fewer
    entries than that did not come through them, so the socket address is used instead, as it is
    when there is no header at all. Never set `hops` above the number of proxies actually in
    front: one hop too many reads the entry just before the real client, which is the first
    thing the client itself can write, and every visitor can then be anyone they like. Only the right-hand end is ever split, so a 16 KB header of
    commas is not parsed into a 16 KB list. Anything that does not parse as an address is
    ignored, so header text never becomes a dictionary key. An IPv6 customer is handed a whole
    /64, so the /64 is the user: otherwise one laptop has 2^64 identities.
    """
    entries = forwarded_for.rsplit(",", hops) if hops > 0 else []
    forwarded = entries[-hops] if len(entries) >= hops > 0 else ""
    for candidate in (forwarded, socket_host or ""):
        try:
            address = ipaddress.ip_address(candidate.strip())
        except ValueError:
            continue
        address = getattr(address, "ipv4_mapped", None) or address  # "::ffff:1.2.3.4" is 1.2.3.4
        if address.version == 6:
            return str(ipaddress.ip_network((address, 64), strict=False).network_address)
        return str(address)
    return "unknown"


class SlidingWindow:
    """Allows `limit` hits per key in any `window_s` seconds, by remembering when each hit happened.

    A sliding window rather than a counter reset on the hour, because a fixed reset lets
    somebody spend two allowances back to back across the boundary. Use one instance per kind
    of limit, so kinds cannot evict each other's keys.
    """

    # ponytail: counts live in this process, so they reset on a restart and each worker would
    # keep its own. Fine for one worker; move to the proxy or Redis when there is more than one.
    def __init__(self, max_keys: int = 10_000) -> None:
        # Least recently seen key first. Lists, not deques: most keys hold one or two hits and
        # an empty deque alone is 760 bytes, which matters when an attacker brings many addresses.
        self._hits: OrderedDict[str, list[float]] = OrderedDict()
        self._max_keys = max_keys
        self._lock = threading.Lock()  # routes and question workers run on different threads

    def __len__(self) -> int:
        return len(self._hits)

    def allow(self, key: str, limit: int, window_s: float, now: float) -> tuple[bool, int]:
        """Count a hit if there is room. Returns (allowed, seconds until a retry can succeed).
        A refused hit is not counted, so hammering a closed door does not keep it closed."""
        with self._lock:
            hits = [t for t in self._hits.pop(key, ()) if now - t < window_s]  # expired hits go here
            allowed = len(hits) < limit
            if allowed:
                hits.append(now)
            if hits:  # a key with nothing left in its window is simply not stored
                self._hits[key] = hits
            # Bounded memory even if an attacker cycles through addresses: forget whoever was
            # seen longest ago. Their count restarts, which costs far less than an OOM kill.
            while len(self._hits) > self._max_keys:
                self._hits.popitem(last=False)
            if allowed:
                return True, 0
            if not hits:  # a limit of zero: this kind of request is switched off
                return False, int(window_s)
            return False, max(1, math.ceil(hits[0] + window_s - now))  # when the oldest hit expires

    def refund(self, key: str) -> None:
        """Give back the newest hit (it turned out to cost nothing). Unknown keys are fine:
        the key may have expired or been evicted since the hit was counted."""
        with self._lock:
            hits = self._hits.get(key)
            if hits:
                hits.pop()
                if not hits:
                    del self._hits[key]


class ConcurrencyGate:
    """At most `total` questions in flight, and at most `per_key` of them from one address.

    Full means refuse now, not wait: a queued question would hold a thread and an open
    connection while it waits, which is exactly the resource the gate exists to protect.
    Memory is bounded by `total`: only addresses with a question in flight are stored.
    """

    def __init__(self, total: int, per_key: int) -> None:
        self._total, self._per_key = total, per_key
        self._in_flight: Counter[str] = Counter()
        self._lock = threading.Lock()

    @contextmanager
    def hold(self, key: str) -> Iterator[None]:
        """Take a slot for the length of the `with` block. The `finally` frees it on every way
        out: a normal return, an error answer or an exception."""
        with self._lock:
            if self._in_flight[key] >= self._per_key:
                raise LimitExceeded(f"You already have {_count(self._per_key, 'question')} being answered.",
                                    "Wait for an answer to arrive, then ask again.", BUSY_RETRY_S)
            if sum(self._in_flight.values()) >= self._total:
                raise LimitExceeded("This demo is answering as many questions as it can right now.",
                                    "Please ask again in a few seconds.", BUSY_RETRY_S)
            self._in_flight[key] += 1
        try:
            yield
        finally:
            with self._lock:
                self._in_flight[key] -= 1
                if not self._in_flight[key]:
                    del self._in_flight[key]


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _about(seconds: int) -> str:
    """People plan around "about 12 minutes", not "714 seconds". Minutes are rounded up so
    nobody is invited back too early; the exact figure is in the Retry-After header."""
    if seconds < 60:
        return "less than a minute"
    minutes = math.ceil(seconds / 60)
    if minutes < 90:
        return f"about {_count(minutes, 'minute')}"
    return f"about {_count(round(minutes / 60), 'hour')}"


def _reached(limit: int, noun: str, per: str) -> str:
    return f"You have reached this demo's limit of {_count(limit, noun)} {per}."


class Limits:
    """The demo's policy: which limits exist, how big they are, and what a refusal says.

    Sizes come from `settings` once, at construction; tests build a new Limits to change one.
    The clock is injectable so tests move time by hand. It is monotonic by default because a
    wall clock can jump (NTP, a changed system time) and a window must not.
    """

    def __init__(self, settings: Settings, clock: Callable[[], float] = time.monotonic) -> None:
        self._settings, self._clock = settings, clock
        self._asks_hour, self._asks_day, self._asks_session = SlidingWindow(), SlidingWindow(), SlidingWindow()
        self._sessions, self._uploads = SlidingWindow(), SlidingWindow()
        self._gate = ConcurrencyGate(settings.max_concurrent_asks, settings.max_concurrent_asks_per_ip)
        self._ingest_slot = threading.BoundedSemaphore(1)

    @contextmanager
    def ingest(self) -> Iterator[None]:
        """One file read at a time, for everybody: reading a spreadsheet in is the memory peak
        on a 512 MB host (the whole file as text, then a frame, then a DuckDB table), and two
        at once is what kills the process. A second reader is refused now rather than queued,
        because queueing would hold its request open while still owing all that memory.
        """
        if not self._ingest_slot.acquire(blocking=False):
            raise LimitExceeded("Another upload is being read.", "Try again in a few seconds.", BUSY_RETRY_S)
        try:
            yield
        finally:
            self._ingest_slot.release()

    def new_session(self, ip: str) -> None:
        """Each session is a DuckDB connection and a temp folder, and the store keeps only a few."""
        limit = self._settings.sessions_per_ip_per_hour
        self._charge(self._sessions, ip, limit, HOUR, _reached(limit, "new session", "an hour"),
                     "You can start another in {wait}.")

    def upload(self, ip: str) -> None:
        """Reading a file in is the most CPU and memory a visitor can ask for without a model."""
        limit = self._settings.uploads_per_ip_per_hour
        self._charge(self._uploads, ip, limit, HOUR, _reached(limit, "upload", "an hour"),
                     "You can upload again in {wait}.")

    @contextmanager
    def question(self, ip: str, session_id: str) -> Iterator[None]:
        """Admit one question or raise LimitExceeded. The concurrency slot is held for the
        length of the `with` block.

        The gate goes first, so a busy refusal uses up no allowance. If one of the counts then
        refuses, the counts already charged are given back and leaving the `with` frees the
        slot: a refused question costs the visitor nothing.
        """
        s = self._settings
        charges = (
            (self._asks_hour, ip, s.asks_per_ip_per_hour, HOUR,
             _reached(s.asks_per_ip_per_hour, "question", "an hour"), "You can ask again in {wait}."),
            (self._asks_day, ip, s.asks_per_ip_per_day, DAY,
             _reached(s.asks_per_ip_per_day, "question", "a day"), "You can ask again in {wait}."),
            # Keyed by session, not address: it bounds one shared or leaked session link,
            # wherever the questions come from.
            (self._asks_session, session_id, s.asks_per_session, DAY,
             f"This session has reached the demo's limit of {_count(s.asks_per_session, 'question')} a day.",
             "Start a new session, or ask again here in {wait}."),
        )
        with self._gate.hold(ip):
            charged: list[tuple[SlidingWindow, str]] = []
            try:
                for window, key, *rest in charges:
                    self._charge(window, key, *rest)
                    charged.append((window, key))
            except LimitExceeded:
                for window, key in charged:
                    window.refund(key)
                raise
            yield

    def refund_question(self, ip: str, session_id: str) -> None:
        """The answer came from the shared answer cache: no model was called, so it is free."""
        for window, key in ((self._asks_hour, ip), (self._asks_day, ip), (self._asks_session, session_id)):
            window.refund(key)

    def _charge(self, window: SlidingWindow, key: str, limit: int, span: int, message: str, next_step: str) -> None:
        allowed, retry = window.allow(key, limit, span, self._clock())
        if not allowed:
            raise LimitExceeded(message, next_step.format(wait=_about(retry)), retry)
