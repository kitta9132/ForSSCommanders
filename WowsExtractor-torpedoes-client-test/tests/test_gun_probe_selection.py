"""Lightweight gun observations must not retry unknown modifier references."""
from types import SimpleNamespace

from test_torpedo_telemetry import gun_reload_probe, safe_gun_reload_probe


def test_reference_opt_out_preserves_direct_observations_without_entity_lookups():
    collections = {
        'gun': [{'id': 1, 'gun': {'id': 1, 'state': 0},
                 'progress': {'value': 0, 'min': 0, 'max': 10},
                 'barrelsModifier': {'barrels': [7, 8], 'mode': 0}}],
        'reloadBar': [], 'gunBarrel': []}
    cc = dict((key, key) for key in (
        'gun', 'progress', 'barrelsModifier', 'serialLoaderModifier',
        'reloadBar', 'gunBarrel', 'weapon'))
    calls = []
    hub = SimpleNamespace(getEntityCollections=lambda name: collections[name],
                          getEntity=lambda ident: calls.append(ident))
    full = gun_reload_probe(hub, cc)
    assert calls == [7, 8]
    calls[:] = []
    light = safe_gun_reload_probe(hub, cc, resolve_references=False)
    assert calls == []
    assert light['collections'] == full['collections']
    assert light['references'] == []
    assert light['getEntity']['status'] == 'notSampled'
    assert light['getEntity']['attempted'] == 0
    assert light['status'] == full['status']


def test_reference_opt_out_does_not_turn_unavailable_collections_into_success():
    hub = SimpleNamespace(getEntityCollections=lambda name: None,
                          getEntity=lambda ident: (_ for _ in ()).throw(
                              AssertionError('reference lookup must be skipped')))
    light = safe_gun_reload_probe(hub, {}, resolve_references=False)
    assert light['status'] == 'unknown'
    assert light['references'] == []
    assert light['getEntity']['status'] == 'notSampled'
    assert all(row['status'] != 'available'
               for row in light['collections'].values())
