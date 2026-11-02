from types import SimpleNamespace
import re

import pytest

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / 'res_mods/PnFMods/WowsExtractor'
sys.path.insert(0, str(ROOT))
import performance_profiler as profiler_module


class Clock(object):
    def __init__(self, step=0.01):
        self.value = 0.0
        self.step = step
        self.calls = 0
    def __call__(self):
        self.calls += 1
        self.value += self.step
        return self.value


def install_clock(monkeypatch, clock):
    fake_time = SimpleNamespace(clock=clock)
    monkeypatch.setattr(profiler_module, 'time', fake_time)


def test_disabled_and_collection_off_never_call_clock(monkeypatch):
    def forbidden():
        raise AssertionError('clock must not be read')
    install_clock(monkeypatch, forbidden)
    for enabled, collection in ((False, False), (True, False), (False, True)):
        p = profiler_module.PerformanceProfiler(enabled, collection)
        assert p.status == 'disabled'
        assert p.clock_calls == 0
        assert p.begin('ships') is None


def test_no_numbers_dependency_and_bool_is_rejected(monkeypatch):
    assert 'numbers' not in profiler_module.__dict__
    install_clock(monkeypatch, lambda: True)
    p = profiler_module.PerformanceProfiler(True, True)
    assert p.status == 'nonNumeric'
    assert p.take_summary()['clockStatus'] == 'nonNumeric'


@pytest.mark.parametrize('value, expected', [
    (None, 'nonNumeric'), (True, 'nonNumeric'), (float('nan'), 'nonFinite'),
    (float('inf'), 'nonFinite'), (-float('inf'), 'nonFinite')])
def test_invalid_probe_values_are_not_measured(monkeypatch, value, expected):
    install_clock(monkeypatch, lambda: value)
    p = profiler_module.PerformanceProfiler(True, True)
    assert p.status == expected
    assert p.take_summary()['status'] == expected


def test_clock_exception_reverse_flat_and_unsupported(monkeypatch):
    def raises():
        raise RuntimeError('secret detail must not escape')
    install_clock(monkeypatch, raises)
    assert profiler_module.PerformanceProfiler(True, True).status == 'clockException'

    values = iter([1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 0.5])
    install_clock(monkeypatch, lambda: next(values))
    assert profiler_module.PerformanceProfiler(True, True).status == 'clockReversed'

    install_clock(monkeypatch, lambda: 4.0)
    assert profiler_module.PerformanceProfiler(True, True).status == 'resolutionUnknown'
    monkeypatch.setattr(profiler_module, 'time', SimpleNamespace())
    assert profiler_module.PerformanceProfiler(True, True).status == 'unsupported'


def test_valid_zero_duration_summary_and_battle_reset(monkeypatch):
    clock = Clock(0.1)
    install_clock(monkeypatch, clock)
    p = profiler_module.PerformanceProfiler(True, True)
    assert p.status == 'available'
    clock.step = 0.0
    for unused in range(60):
        token = p.begin('ships')
        p.finish(token)
    summary = p.take_summary()
    assert summary['status'] == 'notSampled'
    assert summary['clockStatus'] == 'available'
    assert 'phases' not in summary
    p.reset_battle()
    assert p._stats == {} and p._sample_start is None


def test_five_second_window_exception_isolation_and_no_stale_payload(monkeypatch):
    clock = Clock(0.1)
    install_clock(monkeypatch, clock)
    p = profiler_module.PerformanceProfiler(True, True)
    for unused in range(26):
        p.measure('state_cycle_total', lambda: None)
    summary = p.take_summary()
    assert summary['status'] == 'available'
    assert summary['durationUnit'] == 'ms'
    assert summary['sampleEndSeconds'] - summary['sampleStartSeconds'] >= 5.0
    assert summary['timebase'] == {'source': 'time.clock', 'basis': 'assumed'}
    assert summary['phases']['state_cycle_total']['count'] >= 1
    state = p.take_summary()
    assert state['status'] == 'notSampled' and state['clockStatus'] == 'available'
    assert state['timebase']['source'] == 'time.clock'
    assert state['timebase']['basis'] == 'assumed'
    assert state['resolutionObserved'] == pytest.approx(0.1)
    before = p._stats.get('broken', {}).get('count', 0)
    with pytest.raises(ValueError):
        p.measure('broken', lambda: (_ for _ in ()).throw(ValueError()))
    assert p._stats.get('broken', {}).get('count', 0) == before


def test_clock_call_budget_is_18_per_cycle_after_fixed_probe(monkeypatch):
    clock = Clock()
    install_clock(monkeypatch, clock)
    p = profiler_module.PerformanceProfiler(True, True)
    assert p.clock_calls == 8
    phases = profiler_module.PerformanceProfiler.PHASES
    for phase in phases:
        token = p.begin(phase)
        p.finish(token)
    assert p.clock_calls == 8 + 2 * len(phases) == 26
    p.reset_battle()


def test_main_uses_exactly_the_nine_budgeted_phase_boundaries():
    source = (ROOT / 'Main.py').read_text(encoding='utf-8')
    for phase in profiler_module.PerformanceProfiler.PHASES:
        boundary = re.compile(r'profiler\.(?:begin|measure)\(\s*[\'\"]' +
                              re.escape(phase) + r'[\'\"]')
        assert len(boundary.findall(source)) == 1, phase
    assert len(profiler_module.PerformanceProfiler.PHASES) == 9


def test_reverse_during_measurement_stops_without_clock_switch(monkeypatch):
    values = iter([float(i) for i in range(8)] + [9.0, 8.0])
    install_clock(monkeypatch, lambda: next(values))
    p = profiler_module.PerformanceProfiler(True, True)
    token = p.begin('ships')
    p.finish(token)
    assert p.status == 'clockReversed'
    assert p.source == 'time.clock'
    assert p.begin('ships') is None


def test_reverse_between_phases_stops_and_does_not_fallback(monkeypatch):
    values = iter([float(i) for i in range(8)] + [10.0, 11.0, 9.0])
    install_clock(monkeypatch, lambda: next(values))
    p = profiler_module.PerformanceProfiler(True, True)
    p.measure('ships', lambda: None)
    token = p.begin('torpedoes')
    assert token is None
    assert p.status == 'clockReversed'
    assert p.source == 'time.clock'
    assert p.take_summary()['clockStatus'] == 'clockReversed'


def test_phase_allowlist_rejects_unknown_without_reads_or_stats(monkeypatch):
    clock = Clock()
    install_clock(monkeypatch, clock)
    p = profiler_module.PerformanceProfiler(True, True)
    reads = p.clock_calls
    assert p.begin('unexpected') is None
    p.finish(('unexpected', 0.0))
    assert p.clock_calls == reads
    assert p._stats == {}
    assert len(p._stats) == 0
