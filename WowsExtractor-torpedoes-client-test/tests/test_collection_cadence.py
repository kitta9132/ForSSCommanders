"""Offline checks for the 0.3.22-cadence-budget collection schedule.

These load individual methods from Main.py instead of importing it, because the
module targets the game's Python 2 runtime. Fake clocks only: no game/API calls.
"""
from pathlib import Path
import textwrap
import types


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
    encoding='utf-8')


def _method(name, namespace):
    start = SOURCE.index('    def ' + name + '(')
    end = SOURCE.find('\n    def ', start + 1)
    if end < 0:
        end = SOURCE.find('\n\ndef _is_mapping(', start)
    code = textwrap.dedent(SOURCE[start:end])
    # The module itself is Python 2; normalize only the legacy except form.
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(code, namespace)
    return namespace[name]


def _source_default_state_interval():
    literal = SOURCE.split('STATE_INTERVAL = ', 1)[1].split()[0]
    return float(literal)


# ---------------------------------------------------------------------------
# state cadence
# ---------------------------------------------------------------------------
class _TickHarness(object):
    def __init__(self, interval, enabled=True):
        self._now_iter = iter(())
        self.interval = interval
        self.enabled = enabled
        self.builds = []
        self.writes = []
        self.meta_polls = []
        self.errors = []

    def _now(self):
        return next(self._now_iter)

    def _refresh_meta(self, now):
        self.meta_polls.append(now)

    def _diagnostics_due(self, now):
        return False

    def _build_state(self, now):
        self.builds.append(now)
        return {'active': True, 'ts': now}

    def _write_state(self, snapshot):
        self.writes.append(snapshot)

    def cook(self):
        ns = {'_now': self._now, '_get': getattr, '_str': str,
              'logError': self.errors.append}
        tick = _method('_tick', ns)
        collector = self
        collector._active = True
        collector._collectionEnabled = self.enabled
        collector._diagnosticsEnabled = False
        collector._diagnosticsSampleDue = False
        collector._diagnosticsLastNow = None
        collector._diagnosticsNextDue = None
        collector._diagnosticsLastSampleTs = None
        collector._diagnostics_due = self._diagnostics_due
        collector._torpedoDepthSamplingEnabled = False
        collector._torpedoDepthSamplingDue = False
        collector._torpedo_depth_sampling_due = lambda now: False
        collector._refresh_meta = self._refresh_meta
        collector._stateInterval = self.interval
        collector._lastWrite = 0.0
        collector._performanceProfiler = None
        collector._profilerEnabled = False
        collector._writer = None
        collector._build_state = self._build_state
        collector._write_state = self._write_state
        return tick

    def run(self, times):
        self._now_iter = iter(times)
        tick = self.cook()
        for _now in times:
            tick(self)
        return self


def test_default_state_interval_is_five_hz_and_explicit_point_one_is_kept():
    default = _source_default_state_interval()
    assert default == 0.2
    ns = {'_load_mod_config': lambda: {},
          '_cfg_float': lambda cfg, key, fallback: (
              float(cfg[key]) if key in cfg else fallback),
          'STATE_INTERVAL': default, 'PerformanceProfiler': _DisabledProfiler}
    load_config = _method('_load_config', ns)
    collector = type('C', (), {'_performanceProfiler': None,
                               '_profilerEnabled': False})()
    load_config(collector)
    assert collector._stateInterval == 0.2

    ns['_load_mod_config'] = lambda: {'collection_enabled': 'true',
                                      'state_interval': '0.1'}
    load_config(collector)
    assert collector._stateInterval == 0.1

    ns['_load_mod_config'] = lambda: {'collection_enabled': 'true',
                                      'state_interval': '0.01'}
    load_config(collector)
    assert collector._stateInterval == 0.02

    example = (ROOT / 'res_mods/PnFMods/WowsExtractor/config.example.ini').read_text(
        encoding='utf-8')
    assert 'state_interval = 0.2' in example


def test_depth_sampling_interval_is_opt_in_and_has_a_one_second_floor():
    config = {'collection_enabled': 'true',
              'torpedo_depth_sampling_enabled': 'true'}

    def cfg_float(values, key, fallback):
        try:
            value = values.get(key)
            return fallback if value in (None, '') else float(value)
        except Exception:
            return fallback

    load_config = _method('_load_config', {
        '_load_mod_config': lambda: config, '_cfg_float': cfg_float,
        'STATE_INTERVAL': .2, 'PerformanceProfiler': _DisabledProfiler})
    collector = type('C', (), {'_performanceProfiler': None,
                               '_profilerEnabled': False})()
    load_config(collector)
    assert collector._collectionEnabled is True
    assert collector._diagnosticsEnabled is False
    assert collector._torpedoDepthSamplingEnabled is True
    assert collector._torpedoDepthSamplingInterval == 1.0
    for invalid in ('bad', 'nan', 'inf', '-inf', '0.2', '-4'):
        config['torpedo_depth_sampling_interval'] = invalid
        load_config(collector)
        assert collector._torpedoDepthSamplingInterval == 1.0
    config['torpedo_depth_sampling_interval'] = '2.5'
    load_config(collector)
    assert collector._torpedoDepthSamplingInterval == 2.5
    config['collection_enabled'] = 'false'
    load_config(collector)
    assert collector._torpedoDepthSamplingEnabled is False


def test_independent_depth_scheduler_is_one_hz_no_catchup_and_rollback_safe():
    due = _method('_torpedo_depth_sampling_due', {
        '_get': lambda obj, key, default=None: getattr(obj, key, default)})
    collector = type('C', (), {
        '_torpedoDepthSamplingEnabled': True,
        '_torpedoDepthSamplingInterval': 1.0,
        '_torpedoDepthSamplingNextDue': None,
        '_torpedoDepthSamplingLastNow': None})()
    schedule = [0.0, .2, .4, .6, .8, 1.0, 1.2]
    assert [now for now in schedule if due(collector, now)] == [0.0, 1.0]
    assert due(collector, 5.0) is True
    assert due(collector, 5.1) is False
    assert due(collector, 4.0) is True  # game clock rollback resets immediately
    assert due(collector, float('nan')) is False
    assert collector._torpedoDepthSamplingNextDue is None
    assert due(collector, 4.1) is True
    collector._torpedoDepthSamplingEnabled = False
    assert due(collector, 4.2) is False
    assert collector._torpedoDepthSamplingNextDue is None


def test_per_tick_callback_builds_and_writes_only_on_due_five_hz_frames():
    harness = _TickHarness(0.2).run(
        [0.0, 0.19, 0.205, 0.39, 0.41, 0.60, 0.62, 0.80, 0.83])
    assert harness.builds == [0.205, 0.41, 0.62, 0.83]
    assert [item['ts'] for item in harness.writes] == [
        0.205, 0.41, 0.62, 0.83]
    assert harness.meta_polls == [0.0, 0.19, 0.205, 0.39, 0.41, 0.60,
                                  0.62, 0.80, 0.83]
    assert not harness.errors


def test_dense_per_tick_callback_never_builds_faster_than_the_interval():
    times = [index * 0.007 for index in range(300)]  # ~143 callbacks/s
    harness = _TickHarness(0.2).run(times)
    assert len(harness.builds) >= 9
    assert harness.builds[0] >= 0.2
    for previous, current in zip(harness.builds, harness.builds[1:]):
        assert current - previous >= 0.2 - 1e-9
        assert current - previous < 0.22
    assert len(harness.writes) == len(harness.builds)


def test_explicit_point_one_interval_keeps_ten_hz_compatibility():
    harness = _TickHarness(0.1).run(
        [0.0, 0.05, 0.099, 0.1, 0.15, 0.199, 0.2, 0.25])
    assert harness.builds == [0.1, 0.2]


def test_long_stall_does_not_replay_missed_state_frames():
    harness = _TickHarness(0.2).run([0.0, 0.2, 5.0, 5.01, 5.19, 5.2])
    assert harness.builds == [0.2, 5.0, 5.2]
    assert [item['ts'] for item in harness.writes] == [0.2, 5.0, 5.2]


def test_disabled_collection_makes_no_clock_build_or_write_calls():
    harness = _TickHarness(0.2, enabled=False)
    tick = harness.cook()
    tick(harness)  # _now iterator is empty: calling it here would raise
    assert harness.builds == [] and harness.writes == []
    assert harness.meta_polls == [] and not harness.errors


# ---------------------------------------------------------------------------
# meta / arena-id retry gate
# ---------------------------------------------------------------------------
class _Identity(object):
    def __init__(self, is_arena):
        self.is_arena = is_arena
        self.current = 'fallback-1'

    def promote(self, arena_id):
        if arena_id:
            self.is_arena = True
            self.current = 'arena-' + str(arena_id)
        return self.current


class _MetaHarness(object):
    def __init__(self, ready, is_arena, retry_until, last_write=0.0,
                 ready_result=True):
        self.battle_api_calls = 0
        self.build_calls = 0
        self.write_calls = 0
        self.written = []
        self.arena = None
        self.write_ok = True
        self.ready_result = ready_result
        self._metaFile = 'meta.json'
        self._metaRetryUntil = retry_until
        self._metaReady = ready
        self._lastMetaWrite = last_write
        self._metaProbeDue = None
        self._metaProbeLastNow = None
        self._battleId = 'fallback-1'
        self._battleIdentity = _Identity(is_arena)

    @property
    def explore_calls(self):
        return self.battle_api_calls

    def _battle_info_component(self):
        return None

    def _build_meta(self):
        self.build_calls += 1
        return {'battleId': self._battleId, 'roster': []}

    def _meta_ready_for_clients(self, meta):
        return self.ready_result

    def _atomic_write(self, path, meta):
        self.write_calls += 1
        self.written.append(meta)
        return self.write_ok


class _FakeArenaBattle(object):
    def __init__(self, harness):
        self.harness = harness

    def getArenaInfo(self):
        self.harness.battle_api_calls += 1
        if self.harness.arena is None:
            return {}
        return {'arenaUniqueId': self.harness.arena}


def _meta_harness(**kwargs):
    harness = _MetaHarness(**kwargs)
    ns = {'META_RETRY_INTERVAL': 0.5, '_now': lambda: 0.0,
          '_get': lambda obj, key, default=None: (
              obj.get(key, default) if isinstance(obj, dict)
              else getattr(obj, key, default)),
          '_try': lambda fn, default=None: _attempt(fn, default),
          '_coerce': lambda value: value,
          'battle': _FakeArenaBattle(harness),
          'json_dumps': lambda meta: meta,
          '_atomic_write': harness._atomic_write,
          'logInfo': lambda *args: None}
    harness._find_arena_id = types.MethodType(
        _method('_find_arena_id', ns), harness)
    harness._promote_battle_id = types.MethodType(
        _method('_promote_battle_id', ns), harness)
    harness._refresh_meta = types.MethodType(
        _method('_refresh_meta', ns), harness)
    return harness


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def test_ready_meta_writes_nothing_and_only_retries_arena_at_half_second():
    harness = _meta_harness(ready=True, is_arena=False, retry_until=20.0)
    for index in range(10):
        harness._refresh_meta(2.0 + index * 0.1)
    assert harness.explore_calls == 2       # 2.0 and 2.5 only
    assert harness.build_calls == 0 and harness.write_calls == 0


def test_ready_meta_with_arena_already_acquired_never_explores():
    harness = _meta_harness(ready=True, is_arena=True, retry_until=20.0)
    for index in range(10):
        harness._refresh_meta(2.0 + index * 0.1)
    assert harness.explore_calls == 0
    assert harness.build_calls == 0 and harness.write_calls == 0


def test_late_arena_promotion_writes_meta_with_matching_battle_id():
    harness = _meta_harness(ready=True, is_arena=False, retry_until=20.0)
    harness._refresh_meta(3.0)
    harness._refresh_meta(3.2)
    assert harness._battleId == 'fallback-1'
    harness.arena = '42'
    harness._refresh_meta(3.5)
    assert harness._battleIdentity.is_arena is True
    assert harness._battleId == 'arena-42'
    assert harness.explore_calls == 2
    assert harness.build_calls == 1 and harness.write_calls == 1
    assert harness.written[0]['battleId'] == 'arena-42'
    # Once the arena id is known there is no further probe.
    harness._refresh_meta(4.0)
    harness._refresh_meta(4.1)
    assert harness.explore_calls == 2
    assert harness.build_calls == 1 and harness.write_calls == 1


def test_force_is_immediate_and_a_failed_write_still_waits_half_second():
    harness = _meta_harness(ready=False, is_arena=False, retry_until=20.0)
    harness.write_ok = False
    harness._refresh_meta(5.0, force=True)
    assert harness.explore_calls == 1
    assert harness.build_calls == 1 and harness.write_calls == 1
    assert harness._lastMetaWrite == 0.0 and harness._metaReady is False
    assert harness._metaProbeDue == 5.5
    for now in (5.1, 5.2, 5.3, 5.4):
        harness._refresh_meta(now)
    assert harness.explore_calls == 1
    assert harness.build_calls == 1 and harness.write_calls == 1
    harness._refresh_meta(5.5)
    assert harness.explore_calls == 2
    assert harness.build_calls == 2 and harness.write_calls == 2
    harness.write_ok = True
    harness._refresh_meta(6.0)
    assert harness.explore_calls == 3
    assert harness.write_calls == 3
    assert harness._metaReady is True and harness._lastMetaWrite == 6.0


def test_deadline_expiry_stops_probe_and_meta_rebuild():
    harness = _meta_harness(ready=False, is_arena=False, retry_until=12.0,
                            ready_result=False)
    harness._refresh_meta(11.0, force=True)
    assert harness.explore_calls == 1 and harness.build_calls == 1
    harness._refresh_meta(11.5)
    assert harness.explore_calls == 2 and harness.build_calls == 2
    harness._refresh_meta(12.1)
    harness._refresh_meta(13.0)
    assert harness.explore_calls == 2 and harness.build_calls == 2
    assert harness.write_calls == 2


def test_arena_already_acquired_is_not_explored_before_meta_ready():
    harness = _meta_harness(ready=False, is_arena=True, retry_until=20.0)
    harness._refresh_meta(1.0, force=True)
    # The forced start probe is intentional; periodic frames add no exploration.
    assert harness.explore_calls == 1
    for index in range(1, 10):
        harness._refresh_meta(1.0 + index * 0.1)
    assert harness.explore_calls == 1


def test_frozen_zero_clock_probes_once_not_every_frame():
    harness = _meta_harness(ready=True, is_arena=False, retry_until=20.0)
    for _ in range(20):
        harness._refresh_meta(0.0)
    assert harness.explore_calls == 1
    assert harness._metaProbeDue == 0.5

    started = _meta_harness(ready=True, is_arena=False, retry_until=20.0)
    started._refresh_meta(0.0, force=True)
    for _ in range(19):
        started._refresh_meta(0.0)
    assert started.explore_calls == 1


def test_nonfinite_clock_never_probes_per_frame():
    harness = _meta_harness(ready=False, is_arena=False, retry_until=20.0)
    for value in (float('nan'), float('inf'), float('-inf')):
        harness._refresh_meta(value)
    assert harness.explore_calls == 0
    assert harness.build_calls == 0 and harness.write_calls == 0
    assert harness._metaProbeDue is None
    harness._refresh_meta(1.0)
    assert harness.explore_calls == 1

    forced = _meta_harness(ready=False, is_arena=False, retry_until=20.0)
    forced._refresh_meta(float('nan'), force=True)
    assert forced.explore_calls == 1 and forced.write_calls == 1
    for _ in range(5):
        forced._refresh_meta(float('nan'))
    assert forced.explore_calls == 1


def test_backwards_clock_reopens_the_probe_gate_without_catchup():
    harness = _meta_harness(ready=True, is_arena=False, retry_until=100.0)
    harness._refresh_meta(10.0)
    harness._refresh_meta(10.2)
    assert harness.explore_calls == 1
    harness._refresh_meta(5.0)             # rollback resets the deadline
    assert harness.explore_calls == 2
    assert harness._metaProbeDue == 5.5
    harness._refresh_meta(5.2)
    assert harness.explore_calls == 2


class _DisabledProfiler(object):
    def __init__(self, enabled, collection_enabled):
        self.enabled = bool(enabled and collection_enabled)
