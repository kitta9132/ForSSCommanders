"""Regression checks for the lightweight, bounded gun diagnostic route."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                               'PnFMods', 'WowsExtractor'))
import torpedo_telemetry
from torpedo_telemetry import (gun_reload_probe, safe_gun_reload_probe,
                               shared_diagnostic_snapshot)


def _gun_fixture(reference_ids=(7,)):
    collections = {
        'gun': [{'id': 1,
                 'g': {'id': 1, 'state': 0},
                 'p': {'value': 0, 'min': 0, 'max': 10},
                 'bm': {'barrels': list(reference_ids), 'mode': 0},
                 'sm': {'serialLoads': []}}],
        'reloadBar': [{'id': 2, 'rb': {'rowsCount': 0},
                       'weapon': {'type': 'gun'}}],
        'gunBarrel': [{'id': 3, 'gb': {'id': 3},
                       'p': {'value': 1, 'min': 0, 'max': 10}}],
    }
    calls = []

    def get_collections(name):
        calls.append(name)
        return collections[name]

    def get_entity(ident):
        calls.append(('entity', ident))
        return {'p': {'value': ident, 'min': 0, 'max': 10}}

    hub = SimpleNamespace(getEntityCollections=get_collections,
                          getEntity=get_entity)
    components = {'gun': 'g', 'progress': 'p', 'barrelsModifier': 'bm',
                  'serialLoaderModifier': 'sm', 'reloadBar': 'rb',
                  'weapon': 'weapon', 'gunBarrel': 'gb'}
    return hub, components, calls


def test_reference_opt_out_works_with_python2_restricted_builtins_and_json():
    hub, components, calls = _gun_fixture()
    original = torpedo_telemetry.__dict__['__builtins__']
    restricted = dict(original)
    for name in ('iter', 'next', 'enumerate', 'AttributeError', 'TypeError'):
        restricted.pop(name, None)
    # Functions retain their builtins mapping at creation on Python 3. Merely
    # replacing an imported module's __builtins__ would not test this budget.
    namespace = {'__builtins__': restricted, '__name__': 'restricted_gun_probe'}
    source = Path(torpedo_telemetry.__file__).read_text(encoding='utf-8-sig')
    exec(compile(source, torpedo_telemetry.__file__, 'exec'), namespace)
    probe = namespace['safe_gun_reload_probe']
    assert 'enumerate' not in probe.__builtins__
    result = probe(hub, components, resolve_references=False)
    assert result['status'] == 'available'
    assert result['collections']['gun']['rows'][0]['fields']['state']['raw'] == 0
    assert result['collections']['reloadBar']['rows'][0]['weaponType']['raw'] == 'gun'
    assert result['collections']['gunBarrel']['rows'][0]['progress']['value']['raw'] == 1
    assert result['references'] == []
    assert result['getEntity']['status'] == 'notSampled'
    assert result['getEntity']['attempted'] == 0
    assert not any(isinstance(call, tuple) and call[0] == 'entity'
                   for call in calls)
    json.dumps(result, allow_nan=False)


def test_gun_probe_reuses_shared_snapshot_collections_touched_by_another_consumer():
    hub, components, calls = _gun_fixture()
    snapshot = shared_diagnostic_snapshot(hub)

    # Another diagnostic consumer has already requested each fixed collection.
    for name in ('gun', 'reloadBar', 'gunBarrel'):
        list(snapshot.getEntityCollections(name))

    result = gun_reload_probe(snapshot, components, resolve_references=False)
    assert result['status'] == 'available'
    assert calls == ['gun', 'reloadBar', 'gunBarrel']
    assert result['getEntity']['status'] == 'notSampled'
    assert result['getEntity']['attempted'] == 0
    assert result['references'] == []


def test_default_reference_resolution_keeps_the_global_attempt_budget():
    hub, components, calls = _gun_fixture(tuple(range(1, 18)))
    result = gun_reload_probe(hub, components)
    assert result['getEntity']['attempted'] == 16
    assert result['getEntity']['resolved'] == 16
    assert result['getEntity']['remainingBudget'] == 0
    assert len(result['references']) == 16
    assert sum(1 for call in calls
               if isinstance(call, tuple) and call[0] == 'entity') == 16
