# SPDX-License-Identifier: MIT
"""Opt-in, bounded game-thread phase profiler (Python 2/3 compatible)."""
import math
try:
    NUMBER_TYPES = (int, long, float)
except NameError:
    NUMBER_TYPES = (int, float)
try:
    import time
except Exception:
    time = None


class PerformanceProfiler(object):
    PROBE_READS = 8
    WINDOW_SECONDS = 5.0
    PHASES = ('state_cycle_total', 'snapshot_build_total', 'avatar', 'self',
              'ships', 'torpedoes', 'armament_systems', 'diagnostics_due',
              'submit')

    def __init__(self, enabled=False, collection_enabled=False):
        self.enabled = bool(enabled and collection_enabled)
        self.clock = None
        self.clock_name = None
        self.source = None
        self.os_basis = 'assumed'
        self.resolution_observed = None
        self.status = 'disabled'
        self._stats = {}
        self._sample_start = None
        self._pending = None
        self.clock_calls = 0
        self._last_value = None
        if self.enabled:
            self._initialize()

    def _read(self):
        self.clock_calls += 1
        try:
            value = self.clock()
        except Exception:
            return None, 'clockException'
        if isinstance(value, bool) or not isinstance(value, NUMBER_TYPES):
            return None, 'nonNumeric'
        try:
            value = float(value)
            if math.isnan(value) or math.isinf(value):
                return None, 'nonFinite'
        except Exception:
            return None, 'nonNumeric'
        if self._last_value is not None and value < self._last_value:
            return None, 'clockReversed'
        self._last_value = value
        return value, None

    def _stop_clock(self, status):
        self.status = status
        self.clock = None
        self._pending = None

    def _initialize(self):
        if time is None:
            self.status = 'unsupported'
            return
        for name in ('clock', 'perf_counter', 'monotonic'):
            try:
                candidate = getattr(time, name, None)
            except Exception:
                candidate = None
            if callable(candidate):
                self.clock = candidate
                self.clock_name = name
                break
        if self.clock is None:
            self.status = 'unsupported'
            return
        self.source = 'time.' + self.clock_name
        previous = None
        smallest = None
        for unused in range(self.PROBE_READS):
            value, error = self._read()
            if error:
                self._stop_clock(error)
                return
            if previous is not None:
                if value < previous:
                    self.status = 'clockReversed'
                    self.clock = None
                    return
                if value > previous:
                    diff = value - previous
                    smallest = diff if smallest is None else min(smallest, diff)
            previous = value
        if smallest is None:
            self.status = 'resolutionUnknown'
            self.clock = None
            return
        self.resolution_observed = smallest
        self.status = 'available'

    def reset_battle(self):
        self._stats = {}
        self._sample_start = None
        self._pending = None

    def begin(self, phase):
        if (not self.enabled or self.status != 'available' or
                phase not in self.PHASES):
            return None
        value, error = self._read()
        if error:
            self._stop_clock(error)
            return None
        return (phase, value)

    def finish(self, token, completed=True):
        if token is None or not completed or not self.enabled or self.status != 'available':
            return
        if (not isinstance(token, tuple) or len(token) != 2 or
                token[0] not in self.PHASES):
            return
        phase, start = token
        end, error = self._read()
        if error:
            self._stop_clock(error)
            return
        if end < start:
            self._stop_clock('clockReversed')
            return
        if self._sample_start is None:
            self._sample_start = start
        row = self._stats.setdefault(phase, {'count': 0, 'total': 0.0, 'max': 0.0})
        elapsed = (end - start) * 1000.0
        row['count'] += 1
        row['total'] += elapsed
        row['max'] = max(row['max'], elapsed)
        if end - self._sample_start >= self.WINDOW_SECONDS:
            self._pending = {'status': 'available',
                             'clockStatus': 'available',
                             'durationUnit': 'ms',
                             'sampleStartSeconds': self._sample_start,
                             'sampleEndSeconds': end,
                             'timebase': {'source': self.source,
                                          'basis': self.os_basis},
                             'resolutionObserved': self.resolution_observed,
                             'resolutionStatus': 'observedNotGuaranteed',
                             'clockCalls': self.clock_calls,
                             'phases': self._stats}
            self._stats = {}
            self._sample_start = end

    def measure(self, phase, function, *args):
        token = self.begin(phase)
        completed = False
        try:
            result = function(*args)
            completed = True
            return result
        finally:
            self.finish(token, completed)

    def take_summary(self):
        result = self._pending
        self._pending = None
        if result is not None:
            return result
        status = ('notSampled' if self.enabled and self.status == 'available'
                  else self.status)
        return {'status': status, 'clockStatus': self.status,
                'durationUnit': 'ms',
                'timebase': {'source': self.source, 'basis': self.os_basis},
                'resolutionObserved': self.resolution_observed}
