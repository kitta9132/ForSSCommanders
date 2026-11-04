"""Main-owned cadence and API-budget tests for independent submarine groups."""
import ast
import json
from pathlib import Path
import textwrap
from types import MethodType, SimpleNamespace as Obj

import pytest
import test_health_sampling_cadence as health  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py'
SOURCE = MAIN_PATH.read_text(encoding='utf8')
TREE = ast.parse(SOURCE.replace('except Exception, e:',
                                'except Exception as e:'))

import sys  # noqa: E402

sys.path.insert(0, str(ROOT / 'res_mods/PnFMods/WowsExtractor'))
from submarine_telemetry import safe_submarine_probe  # noqa: E402
from torpedo_telemetry import shared_diagnostic_snapshot  # noqa: E402
from test_submarine_telemetry import (  # noqa: E402
    Hub, components, fixture_entity, wave_entity)
from test_submarine_probe_selection import counted_entity  # noqa: E402


def _method(name, namespace):
    start = SOURCE.index('    def ' + name + '(')
    ends = [pos for marker in ('\n    def ', '\n    @staticmethod')
            if (pos := SOURCE.find(marker, start + 1)) != -1]
    end = min(ends) if ends else SOURCE.find('\n\ndef _is_mapping', start)
    code = SOURCE[start:end if end != -1 else None]
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(textwrap.dedent(code), namespace)
    return namespace[name]


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _get(obj, name, default=None):
    try:
        return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name)
    except Exception:
        return default


def _namespace(cc=None):
    return {
        '_get': _get,
        '_try': _try,
        'CC': cc if cc is not None else components(),
        'safe_submarine_probe': safe_submarine_probe,
        'STATE_INTERVAL': 0.2,
        'COMPARISON_SAMPLING_INTERVAL': 1.0,
    }


def _collector(depth=False, battery=False, wave=False, diagnostics=False):
    ns = _namespace()
    obj = Obj(
        _selfDepthSamplingEnabled=depth,
        _batterySamplingEnabled=battery,
        _waveHitSamplingEnabled=wave,
        _diagnosticsEnabled=diagnostics,
        _diagnosticsInterval=1.0,
        _stateInterval=0.2,
        _comparisonSamplingInterval=1.0,
        _comparisonSamplingNextDue=None,
        _comparisonSamplingLastNow=None,
    )
    for name in ('_submarine_sampling_plan', '_collect_submarine_probes',
                 '_deadline_due', '_comparison_sampling_due'):
        setattr(obj, name, MethodType(_method(name, ns), obj))
    return obj, ns


def _hub(entity=None, wave=None):
    return Hub([entity if entity is not None else counted_entity()],
               [wave if wave is not None else wave_entity()])


@pytest.mark.parametrize('depth,battery,wave', [
    (False, False, False), (True, False, False), (False, True, False),
    (False, False, True), (True, True, False), (True, False, True),
    (False, True, True), (True, True, True),
])
def test_each_core_opt_in_is_independent_and_uses_only_selected_getters(
        depth, battery, wave):
    collector, _ns = _collector(depth, battery, wave)
    entity = counted_entity()
    hub = _hub(entity)
    plan = collector._submarine_sampling_plan(False, True)

    probes, wave_sampled = collector._collect_submarine_probes(
        hub, 2.0, False, True, plan)

    expected_calls = []
    if depth or battery:
        expected_calls.append('selfVehicle')
    if wave:
        expected_calls.append('waveHit')
    assert hub.calls == expected_calls
    assert entity.reads['sub'] == int(depth)
    assert entity.reads['bat'] == int(battery)
    assert wave_sampled is wave
    if depth:
        assert probes['selfSubmarineProbe']['components']['submarine']['status'] == 'available'
        assert probes['selfSubmarineProbe']['sampling']['depth'] == {
            'status': 'sampled', 'sampleTs': 2.0,
            'intervalSeconds': 0.2, 'source': 'core'}
    if battery:
        assert probes['selfSubmarineProbe']['components']['battery']['status'] == 'available'
        assert probes['selfSubmarineProbe']['sampling']['battery']['intervalSeconds'] == 1.0
    if wave:
        assert probes['waveHitProbe']['status'] == 'available'
        assert probes['waveHitProbe']['sampling']['sampleTs'] == 2.0
    json.dumps(probes, allow_nan=False)


def test_core_depth_and_wavehit_are_five_hz_battery_reuses_comparison_one_hz():
    collector, _ns = _collector(True, True, True)
    entity = counted_entity()
    hub = _hub(entity)
    statuses = []
    for index in range(6):
        now = index * 0.2
        comparison_due = collector._comparison_sampling_due(now)
        plan = collector._submarine_sampling_plan(False, comparison_due)
        probes, _wave_sampled = collector._collect_submarine_probes(
            hub, now, False, comparison_due, plan)
        statuses.append((comparison_due,
                         probes['selfSubmarineProbe']['sampling']['battery']['status'],
                         probes['selfSubmarineProbe']['components']['battery']['status']))
        assert probes['selfSubmarineProbe']['sampling']['depth']['sampleTs'] == now
        assert probes['selfSubmarineProbe']['sampling']['depth']['intervalSeconds'] == 0.2
        assert probes['waveHitProbe']['sampling']['sampleTs'] == now

    assert [row[0] for row in statuses] == [True, False, False, False, False, True]
    assert [row[1] for row in statuses] == [
        'sampled', 'notSampled', 'notSampled', 'notSampled', 'notSampled', 'sampled']
    assert [row[2] for row in statuses] == [
        'available', 'notSampled', 'notSampled', 'notSampled', 'notSampled', 'available']
    assert hub.calls == ['selfVehicle', 'waveHit'] * 6
    assert entity.reads['sub'] == 6
    assert entity.reads['bat'] == 2


def test_independent_probes_are_created_under_restricted_builtins():
    import builtins
    import submarine_telemetry
    restricted = dict(vars(builtins))
    for name in ('iter', 'next', 'enumerate', 'AttributeError', 'TypeError'):
        restricted.pop(name, None)
    ns = {'__builtins__': restricted, '__name__': 'restricted_submarine'}
    path = Path(submarine_telemetry.__file__)
    exec(compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec'), ns)
    probe = ns['safe_submarine_probe']
    assert 'enumerate' not in probe.__builtins__
    out = probe(_hub(), components(), 2., True, True, True)
    assert out['selfSubmarineProbe']['status'] == 'available'
    assert out['waveHitProbe']['status'] == 'available'
    json.dumps(out, allow_nan=False)


def test_heavy_due_preserves_legacy_all_group_call_and_output_shape_by_default():
    collector, _ns = _collector(diagnostics=True)
    entity = counted_entity()
    hub = _hub(entity)

    probes, wave_sampled = collector._collect_submarine_probes(
        hub, 3.0, True, True)

    assert hub.calls == ['selfVehicle', 'waveHit']
    assert entity.reads['sub'] == entity.reads['bat'] == 1
    assert probes['selfSubmarineProbe']['sampleTs'] == 3.0
    assert probes['waveHitProbe']['sampleTs'] == 3.0
    assert 'sampling' not in probes['selfSubmarineProbe']
    assert 'sampling' not in probes['waveHitProbe']
    assert wave_sampled is True


def test_heavy_due_does_not_override_an_opted_in_batterys_non_due_cadence():
    collector, _ns = _collector(battery=True, diagnostics=True)
    entity = counted_entity()
    hub = _hub(entity)
    plan = collector._submarine_sampling_plan(True, False)

    probes, _wave_sampled = collector._collect_submarine_probes(
        hub, 4.2, True, False, plan)

    assert hub.calls == ['selfVehicle', 'waveHit']
    assert entity.reads['sub'] == 1  # diagnostics fallback for depth
    assert entity.reads['bat'] == 0
    assert probes['selfSubmarineProbe']['components']['battery']['status'] == 'notSampled'
    assert probes['selfSubmarineProbe']['sampling']['battery'] == {
        'status': 'notSampled', 'sampleTs': None,
        'intervalSeconds': 1.0, 'source': 'scheduling'}
    assert probes['selfSubmarineProbe']['sampling']['depth']['source'] == 'diagnostics'


def test_all_off_non_due_does_not_call_getters_or_fabricate_empty_samples():
    collector, _ns = _collector()
    hub = _hub()
    plan = collector._submarine_sampling_plan(False, False)

    probes, wave_sampled = collector._collect_submarine_probes(
        hub, 5.0, False, False, plan)

    assert hub.calls == []
    assert probes == {
        'selfSubmarineProbe': {'status': 'disabled',
                               'source': 'config.diagnostics_enabled'},
        'waveHitProbe': {'status': 'disabled',
                         'source': 'config.diagnostics_enabled'}}
    assert wave_sampled is False


def test_shared_diagnostic_facade_keeps_original_collection_getter_budget():
    collector, _ns = _collector(True, True, True)
    entity = counted_entity()

    class SharedHub(object):
        def __init__(self):
            self.calls = []

        def getEntityCollections(self, name):
            self.calls.append(name)
            return {'torpedo': [], 'selfVehicle': [entity],
                    'waveHit': [wave_entity()]}[name]

    original = SharedHub()
    facade = shared_diagnostic_snapshot(original)
    facade.getEntityCollections('torpedo')
    facade.getEntityCollections('selfVehicle')
    facade.getEntityCollections('waveHit')
    plan = collector._submarine_sampling_plan(False, True)

    probes, _wave_sampled = collector._collect_submarine_probes(
        facade, 6.0, False, True, plan)

    assert original.calls.count('selfVehicle') == 1
    assert original.calls.count('waveHit') == 1
    assert entity.reads['sub'] == entity.reads['bat'] == 1
    assert probes['selfSubmarineProbe']['status'] == 'available'


@pytest.mark.parametrize('self_error,wave_error,expected_self,expected_wave', [
    (RuntimeError('self failed'), None, 'unknown', 'available'),
    (None, RuntimeError('wave failed'), 'available', 'unknown'),
])
def test_failure_in_one_collection_does_not_hide_the_other_group(
        self_error, wave_error, expected_self, expected_wave):
    collector, _ns = _collector(depth=True, wave=True)
    entity = counted_entity()
    hub = Hub([entity], [wave_entity()], self_error=self_error,
              wave_error=wave_error)
    plan = collector._submarine_sampling_plan(False, True)

    probes, _wave_sampled = collector._collect_submarine_probes(
        hub, 7.0, False, True, plan)

    assert probes['selfSubmarineProbe']['status'] == expected_self
    assert probes['waveHitProbe']['status'] == expected_wave
    assert entity.reads['sub'] == int(self_error is None)


def test_wavehit_partial_rows_keep_existing_raw_status_without_joining():
    class PartialRows(object):
        def __iter__(self):
            yield wave_entity(9)
            raise RuntimeError('partial')

    collector, _ns = _collector(wave=True)
    hub = Hub([], PartialRows())
    plan = collector._submarine_sampling_plan(False, False)

    probes, wave_sampled = collector._collect_submarine_probes(
        hub, 8.0, False, False, plan)

    wave = probes['waveHitProbe']
    assert wave_sampled is True
    assert wave['status'] == 'partial'
    assert wave['collection']['complete'] is False
    assert wave['partial'] is True
    assert wave['rows'][0]['entityIdCandidate'] == 9
    assert wave['rows'][0]['fields']['targetID'] == 42


def test_battery_comparison_gate_reopens_on_actual_battle_start():
    collector, ns = _collector(battery=True)

    class Resettable(object):
        def clear(self):
            return None

    class Identity(object):
        def start(self, *args):
            return 'battle-next'

    collector._load_config = lambda: None
    collector._resolve_paths = lambda: None
    collector._mapCalibration = Resettable()
    collector._torpedoMotion = Resettable()
    collector._damage = Resettable()
    collector._battleIdentity = Identity()
    collector._remember_player_vehicle = lambda player: None
    collector._remember_roster_vehicles = lambda *args: None
    collector._find_arena_id = lambda: 'arena'
    collector._collectionEnabled = True
    collector._battleShown = False
    collector._comparisonSamplingNextDue = 21.0
    collector._comparisonSamplingLastNow = 20.0
    ns['battle'] = Obj(getSelfPlayerInfo=lambda: Obj(id=1))
    on_battle_start = MethodType(_method('_on_battle_start', ns), collector)

    assert collector._comparison_sampling_due(20.2) is False
    on_battle_start()
    assert collector._comparisonSamplingNextDue is None
    assert collector._comparisonSamplingLastNow is None
    assert collector._comparison_sampling_due(40.0) is True
    plan = collector._submarine_sampling_plan(False, True)
    assert plan['sample_battery'] is True


def test_config_loader_defaults_off_and_collection_is_mandatory():
    values = {'collection_enabled': 'true',
              'self_depth_sampling_enabled': 'true',
              'battery_sampling_enabled': 'true',
              'wave_hit_sampling_enabled': 'true'}
    ns = _namespace()
    ns.update({
        '_load_mod_config': lambda: dict(values),
        '_cfg_float': lambda cfg, key, default: float(cfg.get(key, default)),
        'PerformanceProfiler': lambda *args: None,
    })
    config_loader = _method('_load_config', ns)
    collector = Obj(_performanceProfiler=None)
    MethodType(config_loader, collector)()
    assert collector._selfDepthSamplingEnabled is True
    assert collector._batterySamplingEnabled is True
    assert collector._waveHitSamplingEnabled is True

    values['collection_enabled'] = 'false'
    MethodType(config_loader, collector)()
    assert collector._selfDepthSamplingEnabled is False
    assert collector._batterySamplingEnabled is False
    assert collector._waveHitSamplingEnabled is False

    config_text = (ROOT / 'res_mods/PnFMods/WowsExtractor/config.example.ini').read_text(
        encoding='utf8')
    for name in ('self_depth_sampling_enabled', 'battery_sampling_enabled',
                 'wave_hit_sampling_enabled'):
        assert name + ' = false' in config_text


def test_collection_off_terminal_path_emits_no_probe_and_reads_no_api():
    calls = []
    ns = _namespace()
    ns.update({
        'SCHEMA_VERSION': 1,
        'WIRE_API_VERSION': '1.0',
        '_now': lambda: 12.0,
        '_empty_avatar_observations': lambda *args: {'status': 'disabled', 'rows': []},
        'logInfo': lambda *args: None,
    })
    terminal = _method('_start_collection', ns)
    collector = Obj(_active=False, _collectionEnabled=False,
                    _battleId='disabled-battle', _write_state=calls.append)
    MethodType(terminal, collector)()

    assert len(calls) == 1
    assert calls[0]['collection']['status'] == 'disabled'
    assert 'selfSubmarineProbe' not in calls[0]
    assert 'waveHitProbe' not in calls[0]
    assert 'safe_submarine_probe' not in calls[0]


def test_build_state_only_offers_current_wavehit_to_heavy_identity_candidates():
    ships, players, info, self_ship, avatars = health.default_fixture()

    class MainHub(object):
        def __init__(self):
            self.calls = []

        def getEntityCollections(self, name):
            self.calls.append(name)
            return {'avatar': avatars, 'selfVehicle': [counted_entity()],
                    'waveHit': [wave_entity()], 'torpedo': []}.get(name, [])

    collector, ns = health.make_collector(avatars, ships, players, info, self_ship)
    ns['STATE_INTERVAL'] = 0.2
    ns['COMPARISON_SAMPLING_INTERVAL'] = 1.0
    hub = MainHub()
    ns['dataHub'] = hub
    cc_values = dict(health.CC_KEYS)
    cc_values.update(components())
    ns['CC'] = Obj(**cc_values)
    ns['shared_diagnostic_snapshot'] = shared_diagnostic_snapshot
    ns['safe_submarine_probe'] = safe_submarine_probe
    identity_inputs = []
    ns['safe_identity_candidates'] = lambda *args: (
        identity_inputs.append(args[-1]) or {'status': 'candidate'})
    for name in ('_submarine_sampling_plan', '_collect_submarine_probes'):
        setattr(collector, name, MethodType(_method(name, ns), collector))

    all_off = collector._build_state(19.8)
    assert all_off['selfSubmarineProbe']['status'] == 'disabled'
    assert all_off['waveHitProbe']['status'] == 'disabled'
    assert hub.calls == ['avatar']
    hub.calls[:] = []

    collector._selfDepthSamplingEnabled = True
    collector._waveHitSamplingEnabled = True
    collector._batterySamplingEnabled = False

    core_only = collector._build_state(20.0)
    assert core_only['waveHitProbe']['status'] == 'available'
    assert core_only['waveHitProbe']['sampling']['source'] == 'core'
    assert core_only['identityCandidates']['status'] == 'disabled'
    assert identity_inputs == []

    collector._diagnosticsEnabled = True
    collector._diagnosticsSampleDue = True
    collector._comparisonSamplingDue = True
    heavy_due = collector._build_state(20.2)
    assert heavy_due['waveHitProbe']['status'] == 'available'
    assert len(identity_inputs) == 1
    assert identity_inputs[0] is heavy_due['waveHitProbe']
