"""Damage events stay live; only snapshot construction shares the 1 Hz gate."""
from types import MethodType, SimpleNamespace as Obj

import test_health_sampling_cadence as health
from damage_tracker import DamageTracker


class CountingDamageTracker(DamageTracker):
    def __init__(self, resolve=None):
        self.snapshot_calls = 0
        super(CountingDamageTracker, self).__init__(resolve=resolve)

    def snapshot(self):
        self.snapshot_calls += 1
        return super(CountingDamageTracker, self).snapshot()


def _collector(resolve=None):
    ships, players, info, self_ship, entities = health.default_fixture()
    collector, namespace = health.make_collector(
        entities, ships, players, info, self_ship)
    collector._damage = CountingDamageTracker(resolve=resolve)
    collector._active = True
    collector._collectionEnabled = True
    collector._comparisonSamplingInterval = 1.0
    collector._comparisonSamplingDue = False
    collector._comparisonSamplingNextDue = None
    collector._comparisonSamplingLastNow = None
    for name in ('_on_damages', '_on_shell_info'):
        setattr(collector, name, MethodType(health.method(name, namespace),
                                            collector))
    return collector, namespace


def _attach_comparison_scheduler(collector, namespace):
    collector._deadline_due = MethodType(
        health.method('_deadline_due', namespace), collector)
    collector._comparison_sampling_due = MethodType(
        health.method('_comparison_sampling_due', namespace), collector)


def _snapshot(collector, now, due):
    collector._comparisonSamplingDue = due
    return collector._build_state(now)


def _deliver_events(collector, live, tick):
    if tick == 0:
        # A shell hit against an unloaded/unknown victim still enters the ledger.
        collector._on_shell_info(0, 10, damage=500)
    elif tick == 1:
        # A later named packet reassigns that amount; consumers must replace
        # snapshots rather than add per-field deltas blindly.
        collector._on_damages(20, [{'vehicleID': 10, 'damage': 500}])
    elif tick == 2:
        collector._on_shell_info(20, 10, damage=1000)
        # Simulate the killing blow after the live lookup has lost the victim;
        # DamageTracker's existing roster ledger still resolves it.
        live.pop(20, None)
        collector._on_damages(20, [{'vehicleID': 10, 'damage': 1000}])
    elif tick == 3:
        collector._on_damages(20, [{'vehicleID': 10, 'damage': 200}])


def test_damage_snapshot_shares_comparison_1hz_gate_but_events_remain_5hz():
    live_fast = {10: (100, 1), 20: (200, 2)}
    live_slow = dict(live_fast)
    fast, _fast_ns = _collector(lambda vid: live_fast.get(vid))
    slow, slow_ns = _collector(lambda vid: live_slow.get(vid))
    _attach_comparison_scheduler(slow, slow_ns)
    for collector in (fast, slow):
        collector._damage.remember(10, 100, 1)
        collector._damage.remember(20, 200, 2)

    fast_states = []
    slow_states = []
    ticks = [0.0, .2, .4, .6, .8, 1.0]
    for index, now in enumerate(ticks):
        _deliver_events(fast, live_fast, index)
        _deliver_events(slow, live_slow, index)
        fast_states.append(_snapshot(fast, now, True))
        due = slow._comparison_sampling_due(now)
        slow_states.append(_snapshot(slow, now, due))

    assert [state['damageSampling']['status'] for state in slow_states] == [
        'sampled', 'notSampled', 'notSampled', 'notSampled',
        'notSampled', 'sampled']
    assert [state['damageSampling']['sampleTs'] for state in slow_states] == [
        0.0, None, None, None, None, 1.0]
    assert all('damage' not in state for state in slow_states[1:5])
    assert [state['damageSampling'] for state in fast_states][1]['status'] == (
        'sampled')

    # The five-Hz snapshots observe the temporary unknown-victim bucket and
    # its later reassignment. This is a full replacement, not an additive delta.
    reassigned = fast_states[1]['damage']['inflicted']['100']
    assert reassigned == {'total': 500, 'byVictim': {'200': 500}}
    assert fast_states[0]['damage']['inflicted']['100'] == {
        'total': 500, 'byVictim': {}}

    latest_fast = fast_states[-1]['damage']
    latest_slow = slow_states[-1]['damage']
    assert latest_slow == latest_fast
    assert latest_slow['inflicted']['100']['total'] == 1700
    assert fast._damage.snapshot_calls == len(ticks)
    assert slow._damage.snapshot_calls == 2


def test_non_due_damage_sampling_does_not_call_snapshot_and_failure_is_unknown():
    collector, _namespace = _collector()
    sampled = _snapshot(collector, 4.0, True)
    assert sampled['damage'] == {
        'inflicted': {}, 'received': {}, 'teamTotal': {}}
    assert collector._damage.snapshot_calls == 1

    for now in (4.2, 4.4, 4.6, 4.8):
        state = _snapshot(collector, now, False)
        assert state['damageSampling'] == {
            'status': 'notSampled', 'sampleTs': None,
            'intervalSeconds': 1.0}
        assert 'damage' not in state
    assert collector._damage.snapshot_calls == 1

    class BrokenDamage(object):
        def remember(self, *args):
            return None

        def snapshot(self):
            raise RuntimeError('snapshot failed')

    collector._damage = BrokenDamage()
    failed = _snapshot(collector, 5.0, True)
    assert failed['damageSampling'] == {
        'status': 'sampled', 'sampleTs': 5.0, 'intervalSeconds': 1.0}
    assert failed['damage'] is None


def test_comparison_scheduler_handles_clock_rollback_without_extra_scheduler():
    collector, namespace = _collector()
    _attach_comparison_scheduler(collector, namespace)

    assert collector._comparison_sampling_due(10.0) is True
    assert collector._comparison_sampling_due(10.2) is False
    assert collector._comparison_sampling_due(9.0) is True
    assert collector._comparisonSamplingNextDue == 10.0
    assert collector._comparison_sampling_due(9.2) is False


def test_battle_start_resets_shared_comparison_schedule_and_damage_ledger():
    collector = health.lifecycle_collector()
    collector._damage = CountingDamageTracker()
    collector._damage.remember(10, 100, 1)
    collector._damage.remember(20, 200, 2)
    collector._damage.on_damages(20, [{'vehicleID': 10, 'damage': 50}])
    collector._comparisonSamplingDue = True
    collector._comparisonSamplingNextDue = 20.0
    collector._comparisonSamplingLastNow = 19.0

    collector._on_battle_start()

    assert collector._comparisonSamplingDue is False
    assert collector._comparisonSamplingNextDue is None
    assert collector._comparisonSamplingLastNow is None
    assert collector._damage.snapshot() == {
        'inflicted': {}, 'received': {}, 'teamTotal': {}}


def test_quit_flushes_events_received_after_last_due_sample():
    live = {10: (100, 1), 20: (200, 2)}
    collector, namespace = _collector(lambda vid: live.get(vid))
    collector._damage.remember(10, 100, 1)
    collector._damage.remember(20, 200, 2)
    writes = []
    collector._write_state = writes.append
    collector._stop_tick = lambda: None
    collector._battleStarted = True
    collector._battleShown = True
    namespace['_now'] = lambda: 12.4
    health.top_function('_empty_avatar_observations', namespace)
    quit_battle = MethodType(health.method('_on_battle_quit', namespace),
                             collector)

    _snapshot(collector, 12.0, True)
    collector._on_damages(20, [{'vehicleID': 10, 'damage': 300}])
    assert collector._damage.snapshot_calls == 1
    _snapshot(collector, 12.2, False)
    assert collector._damage.snapshot_calls == 1

    quit_battle()

    final = writes[-1]
    assert final['active'] is False
    assert final['damageSampling'] == {
        'status': 'sampled', 'sampleTs': 12.4, 'intervalSeconds': 1.0}
    assert final['damage']['inflicted']['100']['total'] == 300
    assert collector._damage.snapshot_calls == 2


def test_collection_off_quit_marks_damage_disabled_without_snapshot():
    collector, namespace = _collector()
    collector._collectionEnabled = False
    collector._write_state = lambda state: setattr(collector, 'written', state)
    collector._stop_tick = lambda: None
    collector._battleStarted = True
    collector._battleShown = True
    namespace['_now'] = lambda: 15.0
    health.top_function('_empty_avatar_observations', namespace)
    quit_battle = MethodType(health.method('_on_battle_quit', namespace),
                             collector)

    quit_battle()

    assert collector._damage.snapshot_calls == 0
    assert collector.written['damage'] == {}
    assert collector.written['damageSampling'] == {
        'status': 'disabled', 'sampleTs': None, 'intervalSeconds': 1.0}


def test_collection_off_start_keeps_empty_damage_api_without_snapshot_call():
    collector, namespace = _collector()
    collector._collectionEnabled = False
    collector._active = False
    collector._battleId = 'disabled-battle'
    writes = []
    collector._write_state = writes.append
    namespace['SCHEMA_VERSION'] = 1
    namespace['WIRE_API_VERSION'] = '1.0'
    namespace['_now'] = lambda: 16.0
    namespace['logInfo'] = lambda *args: None
    health.top_function('_empty_avatar_observations', namespace)
    start = MethodType(health.method('_start_collection', namespace), collector)

    start()

    assert collector._damage.snapshot_calls == 0
    assert writes[-1]['damage'] == {}
    assert writes[-1]['damageSampling'] == {
        'status': 'disabled', 'sampleTs': None, 'intervalSeconds': 1.0}
