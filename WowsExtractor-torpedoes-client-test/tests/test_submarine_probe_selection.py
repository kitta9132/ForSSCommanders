"""Selective probe primitives for independent depth/Battery/WaveHit schedules."""
from collections import Counter
import json

import pytest

from test_submarine_telemetry import Hub, components, fixture_entity, wave_entity
from submarine_telemetry import safe_submarine_probe
from torpedo_telemetry import shared_diagnostic_snapshot


class Counted(dict):
    def __init__(self, values):
        super().__init__(values)
        self.reads = Counter()

    def __getitem__(self, name):
        self.reads[name] += 1
        return super().__getitem__(name)


def counted_entity():
    values = fixture_entity()
    values['sub'] = Counted(values['sub'])
    values['bat'] = Counted(values['bat'])
    return Counted(values)


def test_no_due_groups_make_no_collection_or_component_reads():
    entity = counted_entity()
    wave = wave_entity()
    hub = Hub([entity], [wave])
    out = safe_submarine_probe(hub, components(), 1., False, False, False)
    assert hub.calls == []
    assert not entity.reads
    assert out['selfSubmarineProbe']['status'] == 'notSampled'
    assert out['selfSubmarineProbe']['sampleTs'] is None
    assert out['waveHitProbe']['status'] == 'notSampled'
    assert out['waveHitProbe']['rows'] == []
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('depth,battery,expected', [(True, False, 'sub'), (False, True, 'bat')])
def test_only_due_component_is_read(depth, battery, expected):
    entity = counted_entity()
    hub = Hub([entity], [wave_entity()])
    out = safe_submarine_probe(hub, components(), 2., depth, battery, False)
    assert hub.calls == ['selfVehicle']
    assert entity.reads[expected] == 1
    assert entity.reads['bat' if expected == 'sub' else 'sub'] == 0
    selected = 'submarine' if depth else 'battery'
    omitted = 'battery' if depth else 'submarine'
    assert out['selfSubmarineProbe']['components'][selected]['status'] == 'available'
    assert out['selfSubmarineProbe']['components'][omitted]['status'] == 'notSampled'
    assert out['waveHitProbe']['status'] == 'notSampled'
    assert out['selfSubmarineProbe']['sampleTs'] == 2.


def test_wave_only_does_not_fetch_self_vehicle_or_battery():
    hub = Hub([counted_entity()], [wave_entity()])
    out = safe_submarine_probe(hub, components(), 3., False, False, True)
    assert hub.calls == ['waveHit']
    assert out['waveHitProbe']['status'] == 'available'
    assert out['waveHitProbe']['sampleTs'] == 3.
    assert out['selfSubmarineProbe']['status'] == 'notSampled'


def test_shared_snapshot_keeps_getter_budget_when_other_consumers_are_due():
    entity = counted_entity()
    hub = Hub([entity], [wave_entity()])
    shared = shared_diagnostic_snapshot(hub)
    shared.getEntityCollections('selfVehicle')  # another same-tick consumer
    out = safe_submarine_probe(shared, components(), 4., True, True, True)
    assert hub.calls.count('selfVehicle') == 1
    assert hub.calls.count('waveHit') == 1
    assert entity.reads['sub'] == entity.reads['bat'] == 1
    assert out['selfSubmarineProbe']['status'] == 'available'


def test_unavailable_due_collection_does_not_turn_the_other_group_into_failure():
    out = safe_submarine_probe(Hub(None, []), components(), 5., True, False, False)
    assert out['selfSubmarineProbe']['status'] == 'unknown'
    assert out['selfSubmarineProbe']['components']['submarine']['status'] == 'unknown'
    assert out['selfSubmarineProbe']['components']['battery']['status'] == 'notSampled'
    assert out['waveHitProbe']['status'] == 'notSampled'
