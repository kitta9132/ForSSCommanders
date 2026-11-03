import os
import sys
import builtins
from types import SimpleNamespace as Obj

import pytest

ROOT = os.path.join(os.path.dirname(__file__), '..', 'res_mods', 'PnFMods', 'WowsExtractor')
sys.path.insert(0, ROOT)
from torpedo_telemetry import (shared_diagnostic_snapshot,
    safe_weapon_hub_probe, safe_weapon_context_probe)
from submarine_telemetry import safe_submarine_probe
import torpedo_telemetry


def test_missing_getter_is_unsupported_without_attributeerror_builtin(monkeypatch):
    monkeypatch.setattr(torpedo_telemetry, 'AttributeError', None, raising=False)
    hub = shared_diagnostic_snapshot(Obj())
    context = safe_weapon_context_probe(hub, Obj())
    assert context['collections']['selfVehicle']['getterStatus'] == 'unsupported'
    assert context['collections']['selfVehicle']['status'] == 'unsupported'
    submarine = safe_submarine_probe(hub, Obj(), 1.0)
    assert submarine['selfSubmarineProbe']['collection']['getterStatus'] == 'unsupported'


def test_same_named_collection_is_called_once_and_replayed_for_consumers():
    calls = []
    rows = {'selfVehicle': [], 'weaponSlot': []}

    def get_collection(name):
        calls.append(name)
        return rows[name]

    hub = shared_diagnostic_snapshot(Obj(getEntityCollections=get_collection))
    safe_weapon_context_probe(hub, Obj())
    safe_submarine_probe(hub, Obj(), 1.0)
    safe_weapon_hub_probe(hub, Obj())
    assert calls.count('selfVehicle') == 1
    assert calls.count('weaponSlot') == 1


@pytest.mark.parametrize('outcome', [None, 'exception'])
def test_getter_none_and_exception_are_cached_without_facade_availability_change(outcome):
    calls = []

    def get_collection(name):
        calls.append(name)
        if outcome == 'exception':
            raise RuntimeError('private failure detail')
        return None

    hub = shared_diagnostic_snapshot(Obj(getEntityCollections=get_collection))
    first = safe_weapon_context_probe(hub, Obj())['collections']['selfVehicle']
    second = safe_submarine_probe(hub, Obj(), 1.0)['selfSubmarineProbe']['collection']
    assert first['status'] == 'unknown'
    assert second['status'] == 'unknown'
    assert calls.count('selfVehicle') == 1


def test_partial_iteration_replays_rows_then_same_partial_status():
    calls = []

    def broken_rows():
        yield Obj(id=7)
        raise RuntimeError('must not be serialized')

    def get_collection(name):
        calls.append(name)
        return broken_rows()

    hub = shared_diagnostic_snapshot(Obj(getEntityCollections=get_collection))
    context = safe_weapon_context_probe(hub, Obj())['collections']['selfVehicle']
    submarine = safe_submarine_probe(hub, Obj(), 1.0)['selfSubmarineProbe']['collection']
    assert context['status'] == 'partial' and context['partial'] is True
    assert context['rows'][0]['entityId']['raw'] == 7
    assert submarine['status'] == 'partial'
    assert submarine['count'] == 1
    assert submarine['reason'] == 'iterationException'
    assert calls.count('selfVehicle') == 1


@pytest.mark.parametrize('size, truncated', [(32, False), (33, True)])
def test_largest_consumer_limit_and_plus_one_truncation(size, truncated):
    calls = []
    rows = [Obj(id=index) for index in range(size)]
    hub = shared_diagnostic_snapshot(Obj(getEntityCollections=lambda name:
        calls.append(name) or rows))
    result = safe_weapon_hub_probe(hub, Obj())['collections']['weaponSlot']
    assert result['truncated'] is truncated
    assert len(result['rows']) == min(size, 32)
    assert calls == ['weaponSlot', 'ammo', 'serialLoad']


def test_names_are_independent_unknown_names_passthrough_and_samples_are_fresh():
    calls = []
    api = object()
    source = Obj(getEntityCollections=lambda name: calls.append(name) or [name],
                 getEntity=api)
    one = shared_diagnostic_snapshot(source)
    assert one.getEntity is api
    assert list(one.getEntityCollections('timer')) == ['timer']
    assert list(one.getEntityCollections('battleTimer')) == ['battleTimer']
    assert list(one.getEntityCollections('custom')) == ['custom']
    two = shared_diagnostic_snapshot(source)
    assert list(two.getEntityCollections('timer')) == ['timer']
    assert calls == ['timer', 'battleTimer', 'custom', 'timer']

    unsupported = shared_diagnostic_snapshot(Obj())
    result = safe_weapon_context_probe(unsupported, Obj())
    assert result['collections']['selfVehicle']['status'] == 'unsupported'


def test_facade_does_not_stringify_iteration_exceptions():
    def rows():
        yield Obj(id=1)
        raise RuntimeError('sensitive detail')

    hub = shared_diagnostic_snapshot(Obj(getEntityCollections=lambda name: rows()))
    output = safe_weapon_context_probe(hub, Obj())
    assert 'sensitive detail' not in repr(output)


def test_shared_snapshot_consumers_need_no_iter_or_next_builtin():
    restricted = dict(vars(builtins))
    restricted.pop('iter')
    restricted.pop('next')
    original = torpedo_telemetry.__dict__['__builtins__']
    torpedo_telemetry.__dict__['__builtins__'] = restricted
    try:
        hub = shared_diagnostic_snapshot(Obj(getEntityCollections=lambda name:
            [Obj(id=4)]))
        result = safe_weapon_context_probe(hub, Obj())
    finally:
        torpedo_telemetry.__dict__['__builtins__'] = original
    assert result['collections']['selfVehicle']['rows'][0]['entityId']['raw'] == 4


def test_main_only_constructs_facade_in_due_branch_and_does_not_swap_global_hub():
    with open(os.path.join(ROOT, 'Main.py'), encoding='utf-8') as source:
        text = source.read()
    assert 'lambda: shared_diagnostic_snapshot(dataHub)' in text
    assert 'if diagnostic_due or depth_sampling_due:' in text
    assert text.index('if diagnostic_due or depth_sampling_due:') < text.index(
        'if diagnostic_due:\n            weapon_probe')
    assert 'dataHub = diagnostic_hub' not in text
    assert 'dataHub = shared_diagnostic_snapshot' not in text
