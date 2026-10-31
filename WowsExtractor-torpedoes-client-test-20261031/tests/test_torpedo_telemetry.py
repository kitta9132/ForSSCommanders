"""The actual game adapter with public API doubles (no game engine needed)."""
import json
import os
import sys
from types import SimpleNamespace as Obj

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))
from torpedo_telemetry import TorpedoTelemetry, public_data, vector, ui_torpedo_probe
from torpedo_telemetry import attach_ui_state, TorpedoMotion


def adapter(**api):
    return TorpedoTelemetry(Obj(**api), Obj(WeaponType=Obj(TORPEDO=2)))


def torpedo(**overrides):
    fields = dict(uiId=0, ownerId=77, ownerTeamId=0, ownerType='Ship',
                  shotId=4, type='Torpedo', position=Obj(x=12, y=-3, z=25))
    fields.update(overrides)
    return Obj(**fields)


def test_every_documented_field_owner_and_zero_ids_survive():
    calls = []
    owner = Obj(uiId=44, teamId=0, isPlayer=True, playerName='艦長',
                subtype='Submarine', name='Sub', isBot=False,
                isAlive=True, isObserver=False)

    def get_owner(owner_id):
        calls.append(owner_id)
        return owner

    rows, status = adapter(getAllTorpedoes=lambda: [torpedo(), torpedo(uiId=1)],
                           getTorpedoOwnerById=get_owner).torpedoes(self_team=0)
    assert status['available'] is True
    assert rows[0] == dict(uiId=0, ownerId=77, ownerTeamId=0, ownerType='Ship',
                          shotId=4, type='Torpedo', position=[12., -3., 25.],
                          relation=1, owner=vars(owner), isOwn=True)
    assert calls == [77]  # one owner lookup per snapshot, not per torpedo
    json.dumps(rows, allow_nan=False)


def test_no_owner_id_namespace_guess_or_hidden_fields():
    item = torpedo(ownerId=2000, ownerTeamId=1)
    item.targetId = 99
    item._private = 'hidden'
    rows, _ = adapter(getAllTorpedoes=lambda: [item]).torpedoes(self_team=0)
    assert rows[0]['isOwn'] is None
    assert rows[0]['relation'] == 2
    assert rows[0]['owner'] is None
    assert 'targetId' not in rows[0]
    assert '_private' not in rows[0]


def test_missing_self_team_and_position_are_unknown_not_zero():
    rows, _ = adapter(getAllTorpedoes=lambda: [torpedo(position=None)]).torpedoes()
    assert rows[0]['relation'] is None
    assert rows[0]['position'] is None


def test_empty_success_missing_api_none_and_exception_are_distinct():
    assert adapter(getAllTorpedoes=lambda: []).torpedoes()[1]['status'] == 'available'
    assert adapter().torpedoes()[1]['status'] == 'unsupported'
    assert adapter(getAllTorpedoes=lambda: None).torpedoes()[1]['status'] == 'unknown'

    def fail():
        raise RuntimeError('not ready')

    assert adapter(getAllTorpedoes=fail).torpedoes() == (
        [], dict(available=False, status='unknown', source='battle.getAllTorpedoes'))


def test_failed_enumeration_never_publishes_partial_list():
    def items():
        yield torpedo()
        raise RuntimeError('removed during enumeration')

    rows, status = adapter(getAllTorpedoes=items).torpedoes()
    assert rows == []
    assert status['available'] is False


def test_module_fields_selected_ammo_and_all_public_params():
    module = Obj(type='Torpedo', currentHP=10., maxHP=20., state=0,
                 critTimer=3., position=(1, 2, 3))
    ammo = Obj(id=123, torpedoSpeed=70., nested={'value': 1}, _private='ignored')
    ammo.method = lambda: pytest.fail('must never invoke ammo methods')
    a = adapter(getSelfPlayerShip=lambda: Obj(getTorpedoesModulesState=lambda: [module]),
                getSelectedAmmoId=lambda wt: 123 if wt == 2 else None,
                getAmmoParams=lambda aid: ammo if aid == 123 else None)
    out = a.armament()
    assert out['modules'] == [dict(vars(module), position=[1., 2., 3.])]
    assert out['selectedAmmoId'] == 123
    assert out['ammoParams'] == {'id': 123, 'torpedoSpeed': 70., 'nested': {'value': 1}}
    assert out['ammoParamsStatus'] == 'available'
    assert out['available'] is True


def test_module_empty_success_is_not_missing_and_invalid_ammo_is_not_queried():
    a = adapter(getSelfPlayerShip=lambda: Obj(getTorpedoesModulesState=lambda: []),
                getSelectedAmmoId=lambda wt: -1,
                getAmmoParams=lambda _: pytest.fail('invalid ammo must not be queried'))
    out = a.armament()
    assert out['modulesStatus'] == 'available'
    assert out['modules'] == []
    assert out['selectedAmmoStatus'] == 'unknown'
    assert out['selectedAmmoId'] is None
    assert adapter().armament()['available'] is False


def test_serializer_cycles_nonfinite_private_and_vectors_are_json_safe():
    raw = {'bad': float('nan'), 'vector': Obj(x=1., y=2., z=3.), '_private': 'omit'}
    raw['cycle'] = raw
    out = public_data(raw)
    assert out == {'bad': None, 'vector': [1., 2., 3.], 'cycle': None}
    assert vector([1, float('inf'), 3]) is None
    json.dumps(out, allow_nan=False)


def test_type_is_reread_on_every_snapshot_without_inference_or_normalization():
    item = torpedo()
    a = adapter(getAllTorpedoes=lambda: [item])
    for raw_type in ('normal', 'acoustic', 'magnetic', 'normal', 'future_type', None):
        item.type = raw_type
        rows, status = a.torpedoes()
        assert status['available'] is True
        assert rows[0]['type'] == raw_type
        assert 'isHoming' not in rows[0]


def test_ui_probe_missing_api_and_keys_are_not_false():
    assert ui_torpedo_probe(Obj(), Obj(), [])['status'] == 'unsupported'
    out = ui_torpedo_probe(Obj(getEntityCollections=lambda name: [{}]), Obj(), [])
    assert out['status'] == 'available'
    assert out['rows'][0]['isHoming'] is None
    assert out['rows'][0]['homingStatus'] == 'unsupported'


@pytest.mark.parametrize('value,status,expected', [
    (True, 'available', True), (False, 'available', False),
    (None, 'unknown', None), (1, 'unknown', None), ('false', 'unknown', None)])
def test_ui_probe_boolean_is_not_inferred(value, status, expected):
    entity = {'t': Obj(type='magnetic'), 'm': Obj(data={'isHoming': value})}
    out = ui_torpedo_probe(Obj(getEntityCollections=lambda name: [entity]),
                           Obj(torpedo='t', mods_DataComponent='m'), [{'uiId': 9}])
    row = out['rows'][0]
    assert row['homingStatus'] == status and row['isHoming'] is expected
    assert row['uiType'] == 'magnetic' and row['entityIdCandidate'] is None
    assert out['apiUiIds'] == [9]  # no guessed entity/API join
    json.dumps(out, allow_nan=False)


def test_ui_probe_does_not_keep_previous_value_and_bounds_enumeration():
    data = {'isHoming': True}
    hub = Obj(getEntityCollections=lambda name: [{'m': Obj(data=data)}] * 100)
    keys = Obj(mods_DataComponent='m')
    assert ui_torpedo_probe(hub, keys, [])['truncated'] is True
    data.clear()
    out = ui_torpedo_probe(hub, keys, [])
    assert len(out['rows']) == 64
    assert out['rows'][0]['isHoming'] is None


def test_ui_probe_discards_partial_enumeration_on_failure():
    def entities(name):
        yield {}
        raise RuntimeError('removed')
    out = ui_torpedo_probe(Obj(getEntityCollections=entities), Obj(), [])
    assert out['status'] == 'unknown' and out['rows'] == []


@pytest.mark.parametrize('value,expected,status', [
    (True, True, 'available'), (False, False, 'available'),
    (None, None, 'unknown'), (0, None, 'unknown'), ('true', None, 'unknown')])
def test_ui_spotted_is_independent_of_homing(value, expected, status):
    data = {'isHoming': True, 'isSpotted': value}
    hub = Obj(getEntityCollections=lambda name: [{'m': Obj(data=data)}])
    row = ui_torpedo_probe(hub, Obj(mods_DataComponent='m'), [])['rows'][0]
    assert row['isSpotted'] is expected and row['spottedStatus'] == status
    assert row['isHoming'] is True
    assert row['spottedSource'] == 'ui.mods_DataComponent'
    data.pop('isSpotted')
    row = ui_torpedo_probe(hub, Obj(mods_DataComponent='m'), [])['rows'][0]
    assert row['isSpotted'] is None and row['spottedStatus'] == 'unknown'


def test_ui_join_keeps_false_and_rejects_ambiguous_ids():
    rows = [{'uiId': 4}, {'uiId': 5}]
    probe = {'status': 'available', 'rows': [
        {'entityIdCandidate': 4, 'isHoming': False, 'homingStatus': 'available'},
        {'entityIdCandidate': 5}, {'entityIdCandidate': 5}]}
    attach_ui_state(rows, probe)
    assert rows[0]['uiState']['isHoming'] is False
    assert rows[0]['uiState']['matchStatus'] == 'exactUiId'
    assert rows[1]['uiState']['matchStatus'] == 'unknown'


def test_motion_is_derived_and_does_not_reuse_gaps_or_identity():
    motion = TorpedoMotion()
    def step(ts, pos, shot=1):
        row = {'uiId': 0, 'ownerId': 0, 'shotId': shot, 'position': pos}
        motion.update([row], ts)
        return row['motion']
    assert step(1., [0, 0, 0])['available'] is False
    out = step(1.5, [3, 0, 4])
    assert out['horizontalSpeed'] == 10.
    assert out['velocity'] == [6., 0., 8.]
    assert out['observedDistance'] == 5. and out['observedAge'] == .5
    assert step(1.5, [3, 0, 4])['available'] is False
    assert step(3., [3, 0, 4])['available'] is False
    assert step(3.1, [3, 0, 4], shot=2)['available'] is False
    motion.update([], 3.2)
    assert step(3.3, [3, 0, 4], shot=2)['available'] is False
    motion.clear()
    assert step(3.4, [3, 0, 4], shot=2)['available'] is False


def test_motion_stationary_and_unavailable_are_not_heading_or_stale_speed():
    motion = TorpedoMotion()
    row = {'uiId': 1, 'position': [0, 0, 0]}
    motion.update([row], 1.)
    motion.update([row], 1.1)
    assert row['motion']['horizontalSpeed'] == 0.
    assert row['motion']['headingRadians'] is None
    motion.update([], 1.2, available=False)
    motion.update([row], 1.3)
    assert row['motion']['available'] is False


def test_motion_overflow_never_emits_nonfinite_json():
    motion = TorpedoMotion()
    row = {'uiId': 1, 'position': [1e308, 0., 1e308]}
    motion.update([row], 1.)
    row['position'] = [-1e308, 0., -1e308]
    motion.update([row], 1.1)
    assert row['motion']['available'] is False
    json.dumps(row, allow_nan=False)


def test_self_systems_only_documented_fields_and_preserves_zero():
    ship = Obj(getConsumablesState=lambda: [Obj(icon='hydro', num=0,
                   currentState=2, endTime=13., _hidden='no')],
               getRadarInfo=lambda: None,
               getHydroAcousticSearchInfo=lambda: Obj(distShip=42., state=1, workTimeLeft=0.),
               getSubmarineLocatorInfo=lambda: [Obj(distShip=10., state=0, workTimeLeft=3.)])
    out = adapter(getSelfPlayerShip=lambda: ship).systems()
    assert out['consumables']['items'] == [dict(icon='hydro', num=0, currentState=2, endTime=13.)]
    assert out['search']['radar']['status'] == 'unknown'
    assert out['search']['hydroAcoustic']['items'][0]['workTimeLeft'] == 0.
    assert out['search']['submarineLocator']['shape'] == 'list'
    json.dumps(out, allow_nan=False)


def test_self_systems_unsupported_is_not_empty_success():
    out = adapter().systems()
    assert out['consumables']['status'] == 'unsupported'
    assert all(r['status'] == 'unsupported' for r in out['search'].values())
