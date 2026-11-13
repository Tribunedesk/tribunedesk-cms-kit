"""Retries of a delivery, on the schedule of guide 1 scaled down (spec 1.1 D5.1).

Guide 1: after a network error, a timeout, `5xx`, `408`, `425` or `429` Tribune Desk tries
again after 2, 10, 30, 120, 360 and 840 minutes; any other status ends the send. A newer send
of the article cancels the pending retries of an older one. The mock waits `minutes * scale`
seconds (scale 1: a second for a minute; 0: no retries).
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from tdkit.mock.state import MockState, Send
from tdkit.sender import DeliveryResult

SCHEDULE_MINUTES = (2, 10, 30, 120, 360, 840)
RETRY_STATUSES = {408, 425, 429}


def should_retry(status: int | None) -> bool:
    """`None` is a network error or a timeout."""
    return status is None or status >= 500 or status in RETRY_STATUSES


def delivered(status: int | None) -> bool:
    return status is not None and 200 <= status < 300


class Retrier:
    """Schedules the next attempts of sends whose attempt asked for a retry."""

    def __init__(
        self,
        scale: float,
        attempt: Callable[[Send, int], DeliveryResult],
        state: MockState,
    ) -> None:
        self.scale, self.attempt, self.state = scale, attempt, state
        self._timers: set[threading.Timer] = set()
        self._lock = threading.Lock()
        self._stopped = False

    def after(self, send: Send, number: int, result: DeliveryResult) -> None:
        """Record the outcome of attempt `number` and schedule the next one when due."""
        with self.state.lock:
            if send.state != "awaiting":
                return
            if delivered(result.status):
                send.state = "delivered"
                return
            if not should_retry(result.status) or number > len(SCHEDULE_MINUTES):
                send.state = "failed"
                return
        if self.scale <= 0:
            return
        delay = SCHEDULE_MINUTES[number - 1] * self.scale
        with self._lock:
            if self._stopped:
                return
            timer = threading.Timer(delay, self._fire, args=(send, number + 1))
            timer.daemon = True
            self._timers.add(timer)
            timer.start()

    def _fire(self, send: Send, number: int) -> None:
        with self._lock:
            self._timers = {t for t in self._timers if t.is_alive()}
            if self._stopped:
                return
        with self.state.lock:
            if send.state != "awaiting":  # superseded by a newer send, or settled
                return
        self.after(send, number, self.attempt(send, number))

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            for timer in self._timers:
                timer.cancel()
            self._timers.clear()
