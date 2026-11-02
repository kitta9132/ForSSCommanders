"""Offline tests for the isolated fixed submarine/WaveHit candidates."""
import json
import builtins
import os
import sys
from types import FunctionType

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                               'PnFMods', 'WowsExtractor'))
from submarine_telemetry import (BATTERY_FIELDS, SUBMARINE_FIELDS,
                                 WAVE_HIT_FIELDS, safe_submarine_probe,
                                 self_submarine_probe, wave_hit_probe)


class Hub(object):
    def __init__(self, self_rows=None, wave_rows=None, self_error=None,
                 wave_error=None):
        self.data = {'selfVehicle': self_rows, 'waveHit': wave_rows}
        self.errors = {'selfVehicle': self_error, 'waveHit': wave_error}
        self.calls = []

    def getEntityCollections(self, name):
        self.calls.append(name)
        if self.errors[name]:
            raise self.errors[name]
        return self.data[name]


def components():
    return {'submarine': 'sub', 'battery': 'bat', 'waveHit': 'wh'}


def fixture_entity():
    return {'id': 22, 'sub': {'depth': -20.0, 'depthIndex': 1,
                             'showDepth': False, 'nearestDepthIndex': 0},
            'bat': {'value': 12.5, 'burnedValue': 2, 'maxCapacity': 100,
                    'baseSpendRate': 1, 'baseRegenRate': 2, 'currentRate': 3,
                    'burnRate': 4, 'batteryState': 0,
                    'isPotentiallyBurning': False}}


def wave_entity(ident=5, component=None):
    if component is None:
        component = {'targetID': 42, 'lifeTime': 0.0, 'maxLifeTime': 20,
                     'alertTime': 0, 'hitCount': 0, 'isActive': False,
                     'weaponType': 1}
    return {'id': ident, 'wh': component}


def test_success_reads_only_fixed_collections_once_and_serializes_json_safe():
    hub = Hub([fixture_entity()], [wave_entity()])
    out = safe_submarine_probe(hub, components(), 12.5)
    assert hub.calls == ['selfVehicle', 'waveHit']
    self_probe = out['selfSubmarineProbe']
    assert self_probe['status'] == 'available'
    assert self_probe['collection'] == dict(
        self_probe['collection'], status='available', complete=True, count=1)
    assert self_probe['entityIdCandidate'] == 22
    assert self_probe['components']['submarine']['fields']['depth'] == -20.0
    assert self_probe['components']['submarine']['fieldStatus']['showDepth'] == 'available'
    assert self_probe['components']['submarine']['fields']['showDepth'] is False
    assert out['waveHitProbe']['status'] == 'available'
    assert out['waveHitProbe']['rows'][0]['fields']['hitCount'] == 0
    assert out['waveHitProbe']['rows'][0]['fields']['isActive'] is False
    assert out['waveHitProbe']['rows'][0]['entityIdCandidate'] == 5
    json.dumps(out, allow_nan=False)


def test_non_submarine_or_missing_component_stays_unknown_not_false_or_zero():
    hub = Hub([{'id': 'candidate'}], [])
    out = safe_submarine_probe(hub, components())['selfSubmarineProbe']
    assert out['status'] == 'unknown'
    for name in ('submarine', 'battery'):
        assert out['components'][name]['status'] == 'unknown'
        assert set(out['components'][name]['fields'].values()) == {None}
        assert set(out['components'][name]['fieldStatus'].values()) == {'unknown'}


def test_self_vehicle_empty_multiple_and_iteration_failure_never_select_partial():
    empty = self_submarine_probe(Hub([], []), components())
    assert empty['status'] == 'unknown'
    assert empty['collection']['status'] == 'available'
    assert empty['collection']['reason'] == 'empty'

    multiple_hub = Hub([fixture_entity(), fixture_entity()], [])
    multiple = self_submarine_probe(multiple_hub, components())
    assert multiple['status'] == 'unknown'
    assert multiple['collection']['count'] == 2
    assert multiple['collection']['complete'] is False
    assert multiple['collection']['reason'] == 'multiple'
    assert multiple['entityIdCandidate'] is None

    class Partial(object):
        def __iter__(self):
            yield fixture_entity()
            raise RuntimeError('partial')
    partial = self_submarine_probe(Hub(Partial(), []), components())
    assert partial['collection']['reason'] == 'iterationException'
    assert partial['collection']['failureStage'] == 'enumeration'
    assert partial['collection']['exceptionType'] == 'RuntimeError'
    assert 'partial' not in repr(partial['collection'])
    assert partial['collection']['complete'] is False
    assert partial['entityIdCandidate'] is None


def test_collection_enumerates_when_iter_and_next_names_are_unavailable():
    restricted_builtins = dict(vars(builtins))
    restricted_builtins.pop('iter')
    restricted_builtins.pop('next')
    restricted_globals = {
        '__builtins__': restricted_builtins,
        '_getter_status': __import__('submarine_telemetry')._getter_status,
        '_safe_exception_type': __import__('submarine_telemetry')._safe_exception_type,
    }
    restricted_collection = FunctionType(
        __import__('submarine_telemetry')._collection.__code__, restricted_globals)

    class RestrictedHub(object):
        def getEntityCollections(self, name):
            return [1, 2, 3]

    result, rows = restricted_collection(RestrictedHub(), 'selfVehicle', 8,
                                         stop_on_second=True)
    assert result['status'] == 'unknown'
    assert result['count'] == 2
    assert result['reason'] == 'multiple'
    assert rows == [1, 2]

    result, rows = restricted_collection(RestrictedHub(), 'waveHit', 2, False)
    assert result['status'] == 'available'
    assert result['complete'] is False
    assert result['count'] == 3
    assert result['truncated'] is True
    assert rows == [1, 2]


def test_self_vehicle_collection_is_bounded_at_eight_and_never_uses_first():
    result = self_submarine_probe(Hub([fixture_entity()] * 9, []), components())
    assert result['status'] == 'unknown'
    assert result['collection']['truncated'] is False  # second item resolves ambiguity
    assert result['collection']['reason'] == 'multiple'


def test_wavehit_empty_is_available_and_33rd_entity_marks_truncated():
    empty = wave_hit_probe(Hub([], []), components())
    assert empty['status'] == 'available'
    assert empty['rows'] == []
    assert empty['collection']['complete'] is True

    many = wave_hit_probe(Hub([], [wave_entity(i) for i in range(33)]), components())
    assert many['status'] == 'available'
    assert len(many['rows']) == 32
    assert many['truncated'] is True
    assert many['collection']['complete'] is False
    assert many['rows'][0]['fields']['targetID'] == 42
    assert many['rows'][0]['entityIdCandidate'] == 0


def test_wavehit_unknown_iterator_discards_partial_rows_and_unknown_component_is_explicit():
    class Partial(object):
        def __iter__(self):
            yield wave_entity()
            raise RuntimeError('iteration')
    failed = wave_hit_probe(Hub([], Partial()), components())
    assert failed['status'] == 'unknown'
    assert failed['rows'] == []
    assert failed['collection']['reason'] == 'iterationException'

    missing = wave_hit_probe(Hub([], [{'id': 9}]), components())
    row = missing['rows'][0]
    assert row['componentStatus'] == 'unknown'
    assert row['fieldStatus']['targetID'] == 'unknown'
    assert row['fieldReason']['targetID'] == 'componentMissing'
    assert row['fields']['targetID'] is None


@pytest.mark.parametrize('value,expected_status,expected_value,reason', [
    (0, 'available', 0, None), (False, 'unknown', None, 'expectedFiniteNumber'),
    (True, 'unknown', None, 'expectedFiniteNumber'),
    (float('nan'), 'unknown', None, 'expectedFiniteNumber'),
    (float('inf'), 'unknown', None, 'expectedFiniteNumber'),
    (float('-inf'), 'unknown', None, 'expectedFiniteNumber'),
    (None, 'unknown', None, 'noneValue'), ('9', 'unknown', None, 'expectedFiniteNumber'),
])
def test_numeric_candidates_require_finite_nonboolean_number(value, expected_status,
                                                              expected_value, reason):
    out = self_submarine_probe(Hub([{'sub': {'depth': value}, 'bat': {}}], []),
                               components())
    comp = out['components']['submarine']
    assert comp['fieldStatus']['depth'] == expected_status
    assert comp['fields']['depth'] == expected_value
    assert comp['fieldReason']['depth'] == reason
    json.dumps(out, allow_nan=False)


def test_bool_allowlist_is_strict_and_false_zero_are_retained():
    entity = {'sub': {'depth': 0, 'showDepth': False},
              'bat': {'isPotentiallyBurning': False}}
    probe = self_submarine_probe(Hub([entity], []), components())
    assert probe['components']['submarine']['fields']['depth'] == 0
    assert probe['components']['submarine']['fields']['showDepth'] is False
    assert probe['components']['battery']['fields']['isPotentiallyBurning'] is False
    entity['sub']['showDepth'] = 0
    rejected = self_submarine_probe(Hub([entity], []), components())
    assert rejected['components']['submarine']['fields']['showDepth'] is None
    assert rejected['components']['submarine']['fieldReason']['showDepth'] == 'expectedBoolean'


def test_missing_none_getter_errors_component_access_and_getter_absence_are_distinct():
    probe = self_submarine_probe(Hub([{'sub': {'depth': None}, 'bat': {}}], []),
                                 components())
    sub = probe['components']['submarine']
    assert sub['fieldReason']['depth'] == 'noneValue'
    assert sub['fieldReason']['depthIndex'] == 'attributeMissing'

    class BadComponent(object):
        @property
        def depth(self):
            raise RuntimeError('getter')
    bad = self_submarine_probe(Hub([{'sub': BadComponent(), 'bat': {}}], []),
                               components())
    assert bad['components']['submarine']['fieldReason']['depth'] == 'attributeReadException'

    class BadEntity(object):
        def __getitem__(self, key):
            raise RuntimeError('component')
    failed = self_submarine_probe(Hub([BadEntity()], []), components())
    assert failed['components']['submarine']['reason'] == 'componentReadException'

    unsupported = self_submarine_probe(Hub([fixture_entity()], []), None)
    assert unsupported['components']['submarine']['status'] == 'unsupported'
    assert unsupported['components']['battery']['status'] == 'unsupported'

    class NoGetter(object):
        pass
    no_getter = safe_submarine_probe(NoGetter(), components())
    assert no_getter['selfSubmarineProbe']['status'] == 'unsupported'
    assert no_getter['waveHitProbe']['status'] == 'unsupported'


def test_wavehit_allowlist_field_validation_and_objects_are_not_serialized():
    class Opaque(object):
        def __repr__(self):
            raise AssertionError('repr must not be called')
    source = {'targetID': Opaque(), 'lifeTime': 1.5, 'maxLifeTime': None,
              'alertTime': float('nan'), 'hitCount': True, 'isActive': False,
              'weaponType': 3}
    result = wave_hit_probe(Hub([], [wave_entity(component=source)]), components())
    row = result['rows'][0]
    assert set(row['fields']) == set(WAVE_HIT_FIELDS)
    assert row['fieldStatus']['targetID'] == 'unknown'
    assert row['fieldType']['targetID'] == 'object'
    assert row['fieldReason']['maxLifeTime'] == 'noneValue'
    assert row['fieldReason']['alertTime'] == 'expectedFiniteNumber'
    assert row['fieldReason']['hitCount'] == 'expectedFiniteNumber'
    assert row['fields']['isActive'] is False
    json.dumps(result, allow_nan=False)


def test_anonymized_b27_raw_shape_regression_has_no_history_or_target_join():
    """Captured-value shape only; this is not evidence for a Python game API."""
    # Anonymous IDs and selected values preserve the recorded raw transitions,
    # without retaining identifying recording data or assigning semantics.
    samples = [
        {'depth': 0.0, 'value': 255, 'currentRate': -1, 'batteryState': 0,
         'hitCount': 1, 'maxLifeTime': 25.0, 'lifeTime': 24.9913470997},
        {'depth': 30.0, 'value': 226.2857, 'currentRate': -1,
         'batteryState': 3, 'hitCount': 1, 'maxLifeTime': 25.0,
         'lifeTime': 16.8836727892},
        {'depth': 0.0, 'value': 211.0, 'currentRate': 0.6,
         'batteryState': 1, 'hitCount': 2, 'maxLifeTime': 50.0,
         'lifeTime': 49.9398380993},
    ]
    outputs = []
    for sample in samples:
        entity = {
            'id': 901,
            'sub': {'depth': sample['depth'], 'depthIndex': 0,
                    'showDepth': False, 'nearestDepthIndex': 0},
            'bat': {'value': sample['value'], 'burnedValue': 0,
                    'maxCapacity': 255.0, 'baseSpendRate': -1,
                    'baseRegenRate': 0.6,
                    'currentRate': sample['currentRate'], 'burnRate': 0,
                    'batteryState': sample['batteryState'],
                    'isPotentiallyBurning': False},
        }
        wh = {'targetID': 777, 'lifeTime': sample['lifeTime'],
              'maxLifeTime': sample['maxLifeTime'], 'alertTime': 8.3,
              'hitCount': sample['hitCount'], 'isActive': True,
              'weaponType': 6}
        outputs.append(safe_submarine_probe(
            Hub([entity], [wave_entity(ident=902, component=wh)]), components()))

    assert [out['selfSubmarineProbe']['components']['submarine']['fields']['depth']
            for out in outputs] == [0.0, 30.0, 0.0]
    expected_battery = [(255, -1, 0), (226.2857, -1, 3), (211.0, 0.6, 1)]
    expected_wave = [(1, 25.0, 24.9913470997),
                     (1, 25.0, 16.8836727892),
                     (2, 50.0, 49.9398380993)]
    for out, battery_values, wave_values in zip(outputs, expected_battery,
                                                 expected_wave):
        probe = out['selfSubmarineProbe']
        battery = probe['components']['battery']
        assert tuple(battery['fields'][name] for name in
                     ('value', 'currentRate', 'batteryState')) == battery_values
        assert battery['fields']['burnRate'] == 0
        assert battery['fields']['burnedValue'] == 0
        assert battery['fields']['isPotentiallyBurning'] is False
        assert battery['fieldStatus']['value'] == 'available'

        wave = out['waveHitProbe']
        assert wave['status'] == 'available'
        assert len(wave['rows']) == 1
        row = wave['rows'][0]
        assert tuple(row['fields'][name] for name in
                     ('hitCount', 'maxLifeTime', 'lifeTime')) == wave_values
        assert type(row['fields']['lifeTime']) is float
        assert type(row['fields']['maxLifeTime']) is float
        assert type(row['fields']['isActive']) is bool
        assert row['fields']['isActive'] is True
        assert row['entityIdCandidate'] == 902
        assert row['fields']['targetID'] == 777  # raw candidate, not joined
        assert set(row['fields']) == set(WAVE_HIT_FIELDS)
        assert 'history' not in out and 'target' not in row
        json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('active,expected,reason', [
    (True, True, None), (False, False, None),
    (1, None, 'expectedBoolean'), (0, None, 'expectedBoolean'),
    (None, None, 'noneValue'),
])
def test_wavehit_is_active_raw_bool_is_strict_and_null_is_not_reused(
        active, expected, reason):
    result = wave_hit_probe(
        Hub([], [wave_entity(component={'isActive': active})]), components())
    row = result['rows'][0]
    assert row['fields']['isActive'] is expected
    assert row['fieldReason']['isActive'] == reason
    assert row['fieldStatus']['isActive'] == ('available' if reason is None
                                               else 'unknown')


def test_wavehit_missing_value_in_later_snapshot_does_not_reuse_previous_frame():
    component = {'isActive': True}
    hub = Hub([], [wave_entity(component=component)])
    first = wave_hit_probe(hub, components())
    assert first['rows'][0]['fields']['isActive'] is True

    component.pop('isActive')
    later = wave_hit_probe(hub, components())
    row = later['rows'][0]
    assert row['fields']['isActive'] is None
    assert row['fieldStatus']['isActive'] == 'unknown'
    assert row['fieldReason']['isActive'] == 'attributeMissing'


def test_fixed_field_sets_and_independent_safe_boundary_survive_probe_failures():
    assert SUBMARINE_FIELDS == ('depth', 'depthIndex', 'showDepth', 'nearestDepthIndex')
    assert BATTERY_FIELDS == ('value', 'burnedValue', 'maxCapacity', 'baseSpendRate',
                              'baseRegenRate', 'currentRate', 'burnRate',
                              'batteryState', 'isPotentiallyBurning')
    out = safe_submarine_probe(Hub(None, None, RuntimeError(), None), components())
    assert out['selfSubmarineProbe']['status'] == 'unknown'
    assert out['waveHitProbe']['status'] == 'unknown'
    json.dumps(out, allow_nan=False)


def test_ui_interpretations_are_separate_scoped_and_preserve_raw_values():
    entity = {
        'sub': {'depth': 0.064, 'depthIndex': 3, 'showDepth': False,
                'nearestDepthIndex': 2},
        'bat': {'batteryState': 7, 'value': 0, 'maxCapacity': 255},
    }
    wave = {'lifeTime': 0.0, 'maxLifeTime': 50.0, 'isActive': False}
    out = safe_submarine_probe(
        Hub([entity], [wave_entity(component=wave)]), components(), 44.0)
    submarine = out['selfSubmarineProbe']['components']['submarine']
    battery = out['selfSubmarineProbe']['components']['battery']
    row = out['waveHitProbe']['rows'][0]

    assert submarine['fields']['depth'] == 0.064  # no UI display rounding
    assert submarine['interpretations']['depth']['raw'] == 0.064
    assert submarine['interpretations']['depth']['unitHint'] == 'm'
    assert 'markers_elements.unbound' in submarine['interpretations']['depth']['source']
    assert 'B27 Undine TrainingBattle' in submarine['interpretations']['depth']['scope']
    assert submarine['fields']['depthIndex'] == 3
    assert submarine['interpretations']['depthIndex']['interpretation'] == 'INVULNERABLE'
    assert 'not a guarantee' in submarine['interpretations']['depthIndex']['note']
    assert battery['fields']['batteryState'] == 7
    assert battery['interpretations']['batteryState']['interpretation'] == 'EMPTY'
    assert battery['fields']['value'] == 0
    assert 'ratio' not in battery['interpretations']

    assert row['fields']['lifeTime'] == 0.0
    assert row['interpretations']['lifeTime']['raw'] == 0.0
    assert row['interpretations']['lifeTime']['unitHint'] == 's'
    assert row['interpretations']['lifeTime']['interpretation'] == 0.0
    assert 'maxLifeTime' not in row['interpretations']
    assert row['fields']['maxLifeTime'] == 50.0
    assert 'maxLifeTime' in row['interpretations']['lifeTime']['note']
    json.dumps(out, allow_nan=False)


def test_documented_ui_enum_mappings_cover_only_the_public_fixed_values():
    depth_names = ('SURFACE', 'PERISCOPE', 'WORKING', 'INVULNERABLE')
    battery_names = ('IDLE', 'CHARGING', 'FROZEN', 'SPENDING_NORMAL',
                     'SPENDING_WARNING', 'SPENDING_CRITICAL', 'BURNING', 'EMPTY')
    for raw, expected in enumerate(depth_names):
        probe = self_submarine_probe(
            Hub([{'sub': {'depthIndex': raw}, 'bat': {}}], []), components())
        sub = probe['components']['submarine']
        assert sub['fields']['depthIndex'] == raw
        assert sub['interpretations']['depthIndex']['interpretation'] == expected
    for raw, expected in enumerate(battery_names):
        probe = self_submarine_probe(
            Hub([{'sub': {}, 'bat': {'batteryState': raw}}], []), components())
        battery = probe['components']['battery']
        assert battery['fields']['batteryState'] == raw
        assert battery['interpretations']['batteryState']['interpretation'] == expected


@pytest.mark.parametrize('field,value,raw,status', [
    ('depthIndex', 9, 9, 'unknown'),
    ('depthIndex', 1.0, 1.0, 'unknown'),  # enum interpretation requires integer
    ('depthIndex', True, None, 'unknown'),
])
def test_unknown_or_invalid_enum_interpretation_keeps_existing_raw_contract(
        field, value, raw, status):
    probe = self_submarine_probe(
        Hub([{'sub': {field: value}, 'bat': {'batteryState': 99}}], []),
        components())
    submarine = probe['components']['submarine']
    metadata = submarine['interpretations'][field]
    assert submarine['fields'][field] == raw
    assert submarine['fieldStatus'][field] == ('available' if raw is not None else 'unknown')
    assert metadata['status'] == status
    assert metadata['raw'] == raw
    assert metadata['interpretation'] is None

    battery = probe['components']['battery']
    assert battery['fields']['batteryState'] == 99
    assert battery['fieldStatus']['batteryState'] == 'available'
    assert battery['interpretations']['batteryState']['status'] == 'unknown'
    assert battery['interpretations']['batteryState']['raw'] == 99
    json.dumps(probe, allow_nan=False)


def test_ui_interpretations_keep_strict_bool_and_nonfinite_unknown_and_do_not_carry():
    hub = Hub([{'sub': {'depth': float('nan'), 'depthIndex': 0},
                'bat': {'batteryState': 1}}],
              [wave_entity(component={'lifeTime': float('inf')})])
    first = safe_submarine_probe(hub, components())
    sub = first['selfSubmarineProbe']['components']['submarine']
    wave = first['waveHitProbe']['rows'][0]
    assert sub['fields']['depth'] is None
    assert sub['fieldStatus']['depth'] == 'unknown'
    assert sub['interpretations']['depth']['status'] == 'unknown'
    assert sub['interpretations']['depth']['raw'] is None
    assert sub['interpretations']['depthIndex']['interpretation'] == 'SURFACE'
    assert wave['fields']['lifeTime'] is None
    assert wave['fieldStatus']['lifeTime'] == 'unknown'
    assert wave['interpretations']['lifeTime']['status'] == 'unknown'

    hub.data['selfVehicle'][0]['sub']['showDepth'] = 0
    hub.data['selfVehicle'][0]['sub']['depthIndex'] = 8
    hub.data['selfVehicle'][0]['bat']['batteryState'] = True
    hub.data['waveHit'][0]['wh']['lifeTime'] = 0.0
    later = safe_submarine_probe(hub, components())
    sub = later['selfSubmarineProbe']['components']['submarine']
    battery = later['selfSubmarineProbe']['components']['battery']
    wave = later['waveHitProbe']['rows'][0]
    assert sub['fields']['showDepth'] is None
    assert sub['fieldStatus']['showDepth'] == 'unknown'
    assert sub['fields']['depthIndex'] == 8
    assert sub['interpretations']['depthIndex']['status'] == 'unknown'
    assert battery['fields']['batteryState'] is None
    assert battery['fieldStatus']['batteryState'] == 'unknown'
    assert battery['interpretations']['batteryState']['status'] == 'unknown'
    assert wave['fields']['lifeTime'] == 0.0
    assert wave['interpretations']['lifeTime']['status'] == 'available'
    assert wave['interpretations']['lifeTime']['raw'] == 0.0
    json.dumps(later, allow_nan=False)
