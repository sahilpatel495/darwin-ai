"""Per-user limits: each one trips at its count, recovers after its window, and leaks nothing.

Time is a clock the test moves by hand, so nothing here sleeps and nothing is flaky.
"""

import threading

import pytest

from app.config import Settings
from app.limits import ConcurrencyGate, LimitExceeded, Limits, SlidingWindow, client_ip

IP, OTHER_IP = "203.0.113.9", "198.51.100.7"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> Clock:
    return Clock()


def ask(limits: Limits, ip: str = IP, session: str = "s1") -> None:
    with limits.question(ip, session):
        pass


def hold(gate: ConcurrencyGate, key: str) -> None:
    with gate.hold(key):
        pass


def refused(call, *args) -> LimitExceeded:
    with pytest.raises(LimitExceeded) as caught:
        call(*args)
    return caught.value


# --------------------------------------------------------------------------
# SlidingWindow
# --------------------------------------------------------------------------


def test_window_trips_at_the_limit_and_recovers_when_the_oldest_hit_expires():
    window = SlidingWindow()
    assert [window.allow("a", 3, 60, now) for now in (0, 10, 20)] == [(True, 0)] * 3
    assert window.allow("a", 3, 60, 30) == (False, 30)  # the hit from t=0 leaves the window at t=60
    assert window.allow("a", 3, 60, 59.5) == (False, 1)  # rounded up: never invite a retry that would fail
    assert window.allow("b", 3, 60, 59.5) == (True, 0)  # another key has its own count
    assert window.allow("a", 3, 60, 60) == (True, 0)  # and the two refusals above were not counted


def test_refund_gives_the_hit_back_and_forgets_the_empty_key():
    window = SlidingWindow()
    window.allow("a", 1, 60, 0)
    window.refund("a")
    assert len(window) == 0
    assert window.allow("a", 1, 60, 1) == (True, 0)
    window.refund("never seen")  # a refund for a key that was evicted meanwhile is harmless


def test_a_limit_of_zero_refuses_everything_and_tracks_nothing():
    window = SlidingWindow()
    assert window.allow("a", 0, 60, 0) == (False, 60)
    assert len(window) == 0


def test_ten_thousand_addresses_do_not_grow_memory_without_bound():
    window = SlidingWindow(max_keys=100)
    for i in range(10_000):
        window.allow(f"10.0.{i // 256}.{i % 256}", 1, 3600, now=i)
    assert len(window) == 100
    assert window.allow("10.0.39.15", 1, 3600, now=10_000)[0] is False  # the newest address is still counted
    assert window.allow("10.0.0.0", 1, 3600, now=10_000)[0] is True  # the oldest was evicted and starts again


def test_window_counts_exactly_under_concurrent_callers():
    window, allowed = SlidingWindow(), []

    def hammer() -> None:
        for _ in range(100):
            allowed.append(window.allow("a", 50, 60, 0)[0])

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(allowed) == 50


# --------------------------------------------------------------------------
# ConcurrencyGate
# --------------------------------------------------------------------------


def test_gate_refuses_at_once_per_address_and_in_total_then_frees_every_slot():
    gate = ConcurrencyGate(total=2, per_key=1)
    with gate.hold("a"):
        assert "already" in refused(hold, gate, "a").message  # same address, second question
        with gate.hold("b"):
            assert "as many questions as it can" in refused(hold, gate, "c").message  # the demo is full
    with gate.hold("a"), gate.hold("c"):  # nothing leaked: both slots are free again
        pass


def test_gate_frees_the_slot_when_the_work_raises():
    gate = ConcurrencyGate(total=1, per_key=1)
    with pytest.raises(RuntimeError), gate.hold("a"):
        raise RuntimeError("the worker died")
    with gate.hold("a"):
        pass


# --------------------------------------------------------------------------
# Limits: the policy
# --------------------------------------------------------------------------


def test_hourly_question_limit_says_what_was_hit_and_when_to_come_back(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=2), clock=clock)
    ask(limits)
    clock.advance(12 * 60)
    ask(limits)
    problem = refused(ask, limits)
    assert problem.message == "You have reached this demo's limit of 2 questions an hour."
    assert problem.next_step == "You can ask again in about 48 minutes."
    assert problem.retry_after_s == 48 * 60
    ask(limits, OTHER_IP, "s2")  # somebody else is not affected
    clock.advance(48 * 60)
    ask(limits)  # the first question is an hour old now


def test_daily_question_limit(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=2, asks_per_ip_per_day=3), clock=clock)
    for _ in range(3):
        ask(limits)
        clock.advance(2 * 3600)
    problem = refused(ask, limits)
    assert "3 questions a day" in problem.message and problem.next_step == "You can ask again in about 18 hours."
    assert problem.retry_after_s == 18 * 3600
    clock.advance(18 * 3600)
    ask(limits)


def test_session_limit_follows_the_session_across_addresses(clock):
    limits = Limits(Settings(asks_per_session=2), clock=clock)
    ask(limits, IP)
    ask(limits, OTHER_IP)
    problem = refused(ask, limits, "192.0.2.1")
    assert "This session" in problem.message and "new session" in problem.next_step
    ask(limits, IP, "s2")  # a new session starts from zero


def test_a_question_refused_by_one_limit_is_not_charged_to_the_others(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=3, asks_per_session=1), clock=clock)
    ask(limits, IP, "s1")
    for _ in range(5):
        refused(ask, limits, IP, "s1")  # the session is spent; none of these may eat the hourly allowance
    ask(limits, IP, "s2")
    ask(limits, IP, "s3")
    assert "an hour" in refused(ask, limits, IP, "s4").message


def test_a_cached_answer_is_refunded(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=1, asks_per_ip_per_day=1, asks_per_session=1), clock=clock)
    ask(limits)
    limits.refund_question(IP, "s1")
    ask(limits)  # all three counters gave the hit back
    refused(ask, limits)


def test_sessions_and_uploads_have_their_own_hourly_limits(clock):
    limits = Limits(Settings(sessions_per_ip_per_hour=2, uploads_per_ip_per_hour=1), clock=clock)
    limits.new_session(IP)
    limits.new_session(IP)
    problem = refused(limits.new_session, IP)
    assert "2 new sessions an hour" in problem.message and problem.retry_after_s == 3600
    limits.upload(IP)
    assert "1 upload an hour" in refused(limits.upload, IP).message
    clock.advance(3600)
    limits.new_session(IP)
    limits.upload(IP)


def test_limits_of_different_kinds_do_not_interfere(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=1, sessions_per_ip_per_hour=1, uploads_per_ip_per_hour=1), clock=clock)
    limits.upload(IP)
    refused(limits.upload, IP)
    limits.new_session(IP)  # out of uploads, still allowed a session
    refused(limits.new_session, IP)
    ask(limits)  # out of both, still allowed a question
    refused(ask, limits)
    limits.upload(OTHER_IP)  # and nobody else lost anything
    limits.new_session(OTHER_IP)
    ask(limits, OTHER_IP, "s2")


def test_a_busy_refusal_is_immediate_and_costs_nothing(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=2, max_concurrent_asks_per_ip=1), clock=clock)
    with limits.question(IP, "s1"):
        problem = refused(ask, limits)
        assert "already" in problem.message and 0 < problem.retry_after_s <= 10
    ask(limits)  # the refusal above was not counted, so this is question 2 of 2
    assert "an hour" in refused(ask, limits).message


def test_a_question_refused_by_a_count_does_not_keep_its_slot(clock):
    limits = Limits(Settings(asks_per_ip_per_hour=1, max_concurrent_asks=1), clock=clock)
    ask(limits)
    assert "an hour" in refused(ask, limits).message
    ask(limits, OTHER_IP, "s2")  # the only slot is free: the refused question gave it back


def test_short_waits_are_phrased_for_people(clock):
    limits = Limits(Settings(uploads_per_ip_per_hour=1), clock=clock)
    limits.upload(IP)
    clock.advance(3600 - 30)
    assert refused(limits.upload, IP).next_step == "You can upload again in less than a minute."
    clock.advance(-60)
    assert refused(limits.upload, IP).next_step == "You can upload again in about 2 minutes."  # 90 s, rounded


# --------------------------------------------------------------------------
# Who "a user" is
# --------------------------------------------------------------------------


def test_the_user_is_the_address_the_proxy_appended_not_one_the_client_typed():
    assert client_ip("1.1.1.1, 203.0.113.9", "10.0.0.1") == "203.0.113.9"
    assert client_ip("2.2.2.2, 203.0.113.9", "10.0.0.1") == "203.0.113.9"  # a forged first hop changes nothing
    assert client_ip("", "198.51.100.7") == "198.51.100.7"  # no proxy in front: the socket address
    assert client_ip("", None) == "unknown"


def test_text_that_is_not_an_address_never_becomes_a_key():
    assert client_ip("x" * 16_000, "198.51.100.7") == "198.51.100.7"
    assert client_ip("1.1.1.1, <script>", None) == "unknown"


def test_one_ipv6_customer_is_one_user():
    assert client_ip("2001:db8:1:2:aaaa::1", None) == client_ip("2001:db8:1:2:bbbb::2", None)
    assert client_ip("2001:db8:1:3::1", None) != client_ip("2001:db8:1:2::1", None)
    assert client_ip("::ffff:203.0.113.9", None) == "203.0.113.9"  # IPv4 seen through a dual-stack socket
