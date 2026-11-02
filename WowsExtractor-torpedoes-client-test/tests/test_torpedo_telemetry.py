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
from torpedo_telemetry import weapon_hub_probe, safe_weapon_hub_probe
from torpedo_telemetry import (weapon_context_probe, safe_weapon_context_probe,
                               game_clock_probe, safe_game_clock_probe)
from torpedo_telemetry import gun_reload_probe, safe_gun_reload_probe
from torpedo_telemetry import safe_selected_torpedo_params_probe
from torpedo_telemetry import selected_torpedo_params_probe
from torpedo_telemetry import safe_torpedo_tooltip_parameter_probe


def _meta(value):
    """Match the producer's fieldMeta shape for a raw candidate."""
    if isinstance(value, str):
        return {'type': 'str', 'stringLength': len(value),
                'truncated': len(value) > 128}
    if value is None:
        return {'type': None, 'stringLength': None, 'truncated': False}
    return {'type': type(value).__name__, 'stringLength': None,
            'truncated': False}


def _raw(value):
    if isinstance(value, str):
        return value[:128]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        return value
    return None


def _slot_row(slot_type=2, slot_id=7, component_status='available',
              type_status='available', id_status='available'):
    return {'componentStatus': component_status,
            'fieldStatus': {'type': type_status, 'id': id_status},
            'fieldMeta': {'type': _meta(slot_type), 'id': _meta(slot_id)},
            'fields': {'type': _raw(slot_type), 'id': _raw(slot_id)}}


def _ammo_row(ammo_id=7, descriptor='torpedo', component_status='available',
              descriptor_status='available'):
    return {'componentStatus': component_status,
            'fieldStatus': {'id': 'available'},
            'fieldMeta': {'id': _meta(ammo_id)},
            'fields': {'id': _raw(ammo_id)},
            'viewDataStatus': 'available',
            'viewDataFieldStatus': {'paramsDescriptor': descriptor_status},
            'viewDataFieldMeta': {'paramsDescriptor': _meta(descriptor)},
            'viewData': {'paramsDescriptor': _raw(descriptor),
                         'ammoId': 1234}}


def ttx_fixture(descriptor='torpedo', selected=2, slot_type=2, slot_id=7,
                ammo_id=7, rows=None, value=68.0, delta=-1.0,
                max_dist=10.0, max_delta=0.0,
                partial=False, truncated=False, multiple_self=False,
                missing_ship_ttx=False, self_entity=None):
    ctx = {'observations': {'controllerSelectedWeapon':
        {'status': 'available', 'raw': selected}},
        'torpedoArmament': {'selectedAmmoId': 700}}
    if rows is None:
        slots = [_slot_row(slot_type, slot_id)]
        ammos = [_ammo_row(ammo_id, descriptor)]
    else:
        slots, ammos = rows
    wh = {'collections': {
        'weaponSlot': {'status': 'partial' if partial else 'available', 'rows': slots, 'partial': partial, 'truncated': truncated},
        'ammo': {'status': 'available', 'rows': ammos, 'partial': False, 'truncated': False}}}
    variants = {}
    extra = value if isinstance(value, (int, float)) and not isinstance(value, bool) else 68.0
    for member, speed in (('torpedo', value), ('torpedoDeepwater', extra + 1),
                          ('torpedoAlt', extra + 2)):
        variants[member] = {'speed': {'value': speed, 'delta': delta},
                             'maxDist': {'value': max_dist, 'delta': max_delta}}
    component = {} if missing_ship_ttx else {'shipTTX': {'torpedoes': variants}}
    entity = {'sv-key': component} if self_entity is None else self_entity
    class Hub(object):
        def __init__(self): self.calls = []
        def getEntityCollections(self, name):
            self.calls.append(name)
            if name != 'selfVehicle': raise AssertionError(name)
            return [entity, entity] if multiple_self else [entity]
    hub = Hub()
    result = safe_selected_torpedo_params_probe(hub, {'selfVehicle': 'sv-key'}, ctx, wh)
    return result, hub


def test_selected_torpedo_ttx_routes_exact_descriptor_and_preserves_deltas():
    for descriptor, member, value in (('torpedo', 'torpedo', 68.0),
            ('torpedo_deepwater', 'torpedoDeepwater', 69.0),
            ('torpedo_alternative', 'torpedoAlt', 70.0)):
        result, hub = ttx_fixture(descriptor=descriptor)
        assert result['status'] == 'available'
        assert result['variant'] == descriptor
        assert result['fields']['speed']['raw'] == value
        assert result['fields']['speed']['delta']['raw'] == -1.0
        assert result['fields']['maxDist']['unitHint'] == 'km (TTX UI)'
        assert len(result['variants']) == 3
        assert hub.calls == ['selfVehicle']


def test_selected_torpedo_ttx_unknown_selector_keeps_raw_variants_without_fallback():
    result, _ = ttx_fixture(descriptor='new_descriptor')
    assert result['selection']['status'] == 'unknown'
    assert result['variant'] is None
    assert result['fields'] == {}
    assert len(result['variants']) == 3


def test_selected_torpedo_ttx_does_not_reuse_previous_snapshot_or_join_api_ids():
    first, _ = ttx_fixture(descriptor='torpedo')
    second, _ = ttx_fixture(descriptor='unknown', slot_type=9)
    assert first['variant'] == 'torpedo'
    assert second['variant'] is None
    assert second['fields'] == {}
    # These deliberately mismatched API/viewData IDs are not selector joins.
    second['variants']['torpedo']  # raw candidate is not selected output
    assert second['variant'] is None


def test_selected_torpedo_ttx_pinger_is_not_applicable():
    result, _ = ttx_fixture(descriptor='pinger')
    assert result['status'] == 'notApplicable'
    assert result['selection']['status'] == 'notApplicable'


@pytest.mark.parametrize('value,expected,raw', [
    (None, 'none', None), (0.0, 'available', 0.0), (float('nan'), 'nonFinite', None),
    (1000001.0, 'outOfBounds', None), ('68', 'nonNumeric', None), (True, 'nonNumeric', None)])
def test_selected_torpedo_ttx_field_status_and_bounds(value, expected, raw):
    result, _ = ttx_fixture(value=value)
    assert result['fields']['speed']['status'] == expected
    assert result['fields']['speed']['raw'] == raw


def test_selected_torpedo_ttx_field_getter_error_and_none_parent_are_distinct():
    class BadDiff(object):
        @property
        def value(self): raise RuntimeError('getter')
        @property
        def delta(self): return None
    result, _ = ttx_fixture()
    # Verify the fixed leaf reader's exception/None classification directly
    # without widening the probe's object inspection surface.
    import torpedo_telemetry as telemetry
    assert telemetry._ttx_number('x', *telemetry._ttx_read(BadDiff(), 'value'), 'knots')['status'] == 'readError'
    assert telemetry._ttx_number('x', *telemetry._ttx_read(BadDiff(), 'delta'), 'knots')['status'] == 'none'
    assert result['status'] == 'available'


def test_selected_torpedo_ttx_missing_ship_ttx_and_safe_error_are_isolated():
    result, _ = ttx_fixture()
    # The probe's output can be serialized even when a shape is unavailable.
    assert result['selfVehicle']['shipTTXStatus'] == 'available'
    class FailingHub(object):
        def getEntityCollections(self, name): raise RuntimeError('unavailable')
    failed = safe_selected_torpedo_params_probe(FailingHub(), {'selfVehicle': 'sv'},
                                                 {'observations': {}}, {'collections': {}})
    assert failed['selfVehicle']['collectionStatus'] == 'partial'
    assert failed['status'] != 'available'
    missing, _ = ttx_fixture(missing_ship_ttx=True)
    assert missing['selfVehicle']['shipTTXStatus'] == 'missing'
    assert missing['variants'] == {}


def test_selected_torpedo_ttx_rejects_nonunique_partial_and_bool_int_joins():
    result, _ = ttx_fixture(slot_id=1, ammo_id=True)
    assert result['selection']['status'] == 'unknown'
    result, _ = ttx_fixture()
    # `selectedWeapon` and slot type must be numeric, finite, and non-bool.
    result, _ = ttx_fixture(selected=True, slot_type=1)
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == 'nonNumeric'
    result, _ = ttx_fixture(partial=True)
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == 'partial'
    result, _ = ttx_fixture(truncated=True)
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == 'truncated'
    result, _ = ttx_fixture(multiple_self=True)
    assert result['selfVehicle']['collectionStatus'] == 'multiple'
    assert result['status'] == 'unknown'


def test_selected_torpedo_ttx_nonunique_slot_and_missing_descriptor_remain_unknown():
    slot = _slot_row(slot_type=2, slot_id=7)
    ammo = _ammo_row(ammo_id=7, descriptor='torpedo')
    result, _ = ttx_fixture(rows=([slot, slot], [ammo]))
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == 'nonUnique'


def _variants(value=68.0, delta=-1.0, max_dist=10.0, max_delta=0.0):
    return {
        'torpedo': {'speed': {'value': value, 'delta': delta},
                    'maxDist': {'value': max_dist, 'delta': max_delta}},
        'torpedoDeepwater': {'speed': {'value': value + 1, 'delta': delta},
                             'maxDist': {'value': max_dist, 'delta': max_delta}},
        'torpedoAlt': {'speed': {'value': value + 2, 'delta': delta},
                       'maxDist': {'value': max_dist, 'delta': max_delta}},
    }


class _ShipTTXError(object):
    @property
    def shipTTX(self):
        raise RuntimeError('shipTTX getter failed')


def integration_fixture(descriptor='torpedo', selected=2, slot_type=2,
                        slot_id='slot-id', ammo_id='slot-id',
                        slot_component='normal', ammo_component='normal',
                        self_mode='normal', self_collection_raises=False,
                        variants=None):
    """Fake dataHub/CC that feeds the real producer probes end to end."""
    slot_entity = {'id': 'slot-entity'}
    if slot_component == 'normal':
        slot_entity['ws'] = {'id': slot_id, 'type': slot_type}
    elif slot_component == 'none':
        slot_entity['ws'] = None
    ammo_entity = {'id': 'ammo-entity'}
    if ammo_component == 'normal':
        ammo_entity['a'] = {'id': ammo_id,
                            'viewData': {'paramsDescriptor': descriptor}}
    elif ammo_component == 'none':
        ammo_entity['a'] = None
    controller_entity = {'id': 'controller-entity',
                         'wc': {'selectedWeapon': selected,
                                'activeIdWeapon': 99}}
    self_entity = {'id': 'self-entity'}
    if self_mode == 'componentMissing':
        pass
    elif self_mode == 'componentNone':
        self_entity['sv'] = None
    elif self_mode == 'shipMissing':
        self_entity['sv'] = {}
    elif self_mode == 'shipNone':
        self_entity['sv'] = {'shipTTX': None}
    elif self_mode == 'shipError':
        self_entity['sv'] = _ShipTTXError()
    else:
        self_entity['sv'] = {'shipTTX': {'torpedoes':
                                         _variants() if variants is None else variants}}

    class Hub(object):
        def __init__(self):
            self.calls = []

        def getEntityCollections(self, name):
            self.calls.append(name)
            if name == 'weaponSlot':
                return [slot_entity]
            if name == 'ammo':
                return [ammo_entity]
            if name == 'weaponController':
                return [controller_entity]
            if name == 'selfVehicle':
                if self_collection_raises:
                    raise RuntimeError('selfVehicle collection failed')
                return [self_entity]
            return []

        def getFirstWatcher(self, key):
            return Obj(entity=self_entity)

    components = {'weaponSlot': 'ws', 'progress': 'p', 'ammo': 'a',
                  'serialLoad': 'sl', 'selfVehicle': 'sv',
                  'weaponController': 'wc'}
    hub = Hub()
    weapon_hub = weapon_hub_probe(hub, components)
    weapon_context = weapon_context_probe(hub, components)
    selected_params = selected_torpedo_params_probe(
        hub, components, weapon_context, weapon_hub)
    return selected_params, weapon_hub, weapon_context, hub


def test_selected_torpedo_integration_real_producers_use_raw_scalar_schema():
    result, weapon_hub, context, hub = integration_fixture()
    slot = weapon_hub['collections']['weaponSlot']['rows'][0]
    ammo = weapon_hub['collections']['ammo']['rows'][0]
    assert slot['fields']['type'] == 2
    assert slot['fieldStatus']['type'] == 'available'
    assert slot['fields']['id'] == 'slot-id'
    assert slot['fieldMeta']['id'] == {
        'type': 'str', 'stringLength': 7, 'truncated': False}
    assert ammo['fields']['id'] == 'slot-id'
    assert ammo['viewData']['paramsDescriptor'] == 'torpedo'
    assert ammo['viewDataFieldMeta']['paramsDescriptor'] == {
        'type': 'str', 'stringLength': 7, 'truncated': False}
    assert context['observations']['controllerSelectedWeapon']['raw'] == 2
    assert result['selection']['status'] == 'available'
    assert result['selection']['descriptor'] == 'torpedo'
    assert result['variant'] == 'torpedo'
    assert result['status'] == 'available'
    assert result['fields']['speed']['raw'] == 68.0
    assert result['fields']['speed']['delta']['raw'] == -1.0
    assert result['leafStatus'] == 'available'
    assert result['stages']['selection'] == 'available'
    assert result['stages']['shipTTX'] == 'available'
    # API selectedAmmoId/viewData.ammoId are deliberately unrelated.
    assert hub.calls.count('selfVehicle') >= 2
    json.dumps(result, allow_nan=False)


def test_selected_torpedo_integration_b15_normal_only_partial_route_and_pinger():
    # Anonymous B15-shaped fixture: only the normal variant exists; deepwater
    # and alternative are present as None, so the route is partial even though
    # the selected variant and its four FloatDiff leaves are all available.
    variants = {
        'torpedo': {'speed': {'value': 75.0, 'delta': 0},
                    'maxDist': {'value': 9.0, 'delta': 0}},
        'torpedoDeepwater': None,
        'torpedoAlt': None,
    }
    result, _, _, _ = integration_fixture(variants=variants)
    assert result['selection']['status'] == 'available'
    assert result['selection']['reason'] is None
    assert result['selection']['descriptor'] == 'torpedo'
    assert result['variant'] == 'torpedo'
    assert result['status'] == 'available'
    assert result['variantStatus'] == 'available'
    assert result['leafStatus'] == 'available'
    assert result['ttxStatus'] == 'partial'
    assert result['stages'] == {
        'selection': 'available', 'selfVehicle': 'available',
        'shipTTX': 'available', 'variants': 'partial',
        'variant': 'available', 'leaf': 'available'}
    assert {name: entry['status'] for name, entry in result['variants'].items()} == {
        'torpedo': 'available', 'torpedo_deepwater': 'none',
        'torpedo_alternative': 'none'}
    speed = result['fields']['speed']
    assert speed['raw'] == 75.0 and speed['type'] == 'float'
    assert speed['status'] == 'available'
    assert speed['delta']['raw'] == 0 and speed['delta']['type'] == 'int'
    assert speed['delta']['status'] == 'available'
    max_dist = result['fields']['maxDist']
    assert max_dist['raw'] == 9.0 and max_dist['type'] == 'float'
    assert max_dist['status'] == 'available'
    assert max_dist['delta']['raw'] == 0 and max_dist['delta']['type'] == 'int'
    assert max_dist['delta']['status'] == 'available'

    # A pinger selection is notApplicable on its own route; it must not turn
    # the independent TTX route's partial status into a failure or reset it.
    pinger, _, _, _ = integration_fixture(descriptor='pinger', variants=variants)
    assert pinger['status'] == 'notApplicable'
    assert pinger['selection']['status'] == 'notApplicable'
    assert pinger['selection']['descriptor'] == 'pinger'
    assert pinger['stages']['selection'] == 'notApplicable'
    assert pinger['variantStatus'] == 'unknown'
    assert pinger['leafStatus'] == 'unknown'
    assert pinger['fields'] == {}
    assert pinger['ttxStatus'] == 'partial'
    assert pinger['stages']['variants'] == 'partial'
    json.dumps(result, allow_nan=False)
    json.dumps(pinger, allow_nan=False)


@pytest.mark.parametrize('self_mode,component_status,ship_status', [
    ('componentMissing', 'unknown', 'unknown'),
    ('componentNone', 'unknown', 'unknown'),
    ('shipMissing', 'available', 'missing'),
    ('shipNone', 'available', 'none'),
    ('shipError', 'available', 'readError'),
])
def test_selected_torpedo_integration_selfvehicle_component_and_ttx_failures(
        self_mode, component_status, ship_status):
    result, _, _, _ = integration_fixture(self_mode=self_mode)
    assert result['selection']['status'] == 'available'
    assert result['selfVehicle']['componentStatus'] == component_status
    assert result['selfVehicle']['shipTTXStatus'] == ship_status
    assert result['variants'] == {}
    assert result['status'] == 'unknown'
    assert result['stages']['selection'] == 'available'
    assert result['stages']['shipTTX'] == ship_status


def test_selected_torpedo_integration_missing_slot_and_ammo_components_fail_closed():
    slot_missing, _, _, _ = integration_fixture(slot_component='missing')
    assert slot_missing['selection']['status'] == 'unknown'
    assert slot_missing['selection']['reason'] == 'incomplete'
    ammo_missing, _, _, _ = integration_fixture(ammo_component='none')
    assert ammo_missing['selection']['status'] == 'unknown'
    assert ammo_missing['selection']['reason'] == 'incomplete'


def test_selected_torpedo_ids_129_truncated_prefixes_are_never_joined():
    prefix = 'x' * 128
    result, _ = ttx_fixture(slot_id=prefix + 'a', ammo_id=prefix + 'b')
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == 'truncatedId'
    same_prefix, _ = ttx_fixture(slot_id=prefix + 'a', ammo_id=prefix + 'a')
    assert same_prefix['selection']['status'] == 'unknown'
    assert same_prefix['selection']['reason'] == 'truncatedId'


@pytest.mark.parametrize('slot_id,ammo_id,reason', [
    ('', 7, 'invalidId'), ('   ', 7, 'invalidId'),
    (' 7 ', '7', 'noMatch')])
def test_selected_torpedo_empty_whitespace_and_untrimmed_ids_do_not_match(
        slot_id, ammo_id, reason):
    result, _ = ttx_fixture(slot_id=slot_id, ammo_id=ammo_id)
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == reason


def test_selected_torpedo_zero_is_valid_but_bool_and_float_types_do_not_join():
    zero, _ = ttx_fixture(selected=0, slot_type=0, slot_id=0, ammo_id=0)
    assert zero['selection']['status'] == 'available'
    assert zero['variant'] == 'torpedo'
    bool_ammo, _ = ttx_fixture(slot_id=1, ammo_id=True)
    assert bool_ammo['selection']['status'] == 'unknown'
    assert bool_ammo['selection']['reason'] == 'invalidId'
    float_ammo, _ = ttx_fixture(slot_id=1, ammo_id=1.0)
    assert float_ammo['selection']['status'] == 'unknown'
    assert float_ammo['selection']['reason'] == 'noMatch'


def test_selected_torpedo_unknown_rows_cannot_enable_a_unique_match():
    good_slot = _slot_row(slot_type=2, slot_id=7)
    missing_type = _slot_row(slot_type=2, slot_id=7,
                             type_status='none')
    good_ammo = _ammo_row(ammo_id=7)
    slot_result, _ = ttx_fixture(rows=([good_slot, missing_type], [good_ammo]))
    assert slot_result['selection']['status'] == 'unknown'
    assert slot_result['selection']['reason'] == 'incomplete'

    missing_ammo = _ammo_row(ammo_id=7, component_status='unknown')
    ammo_result, _ = ttx_fixture(rows=([good_slot], [good_ammo, missing_ammo]))
    assert ammo_result['selection']['status'] == 'unknown'
    assert ammo_result['selection']['reason'] == 'incomplete'

    duplicate_ammo, _ = ttx_fixture(rows=([good_slot], [good_ammo, good_ammo]))
    assert duplicate_ammo['selection']['status'] == 'unknown'
    assert duplicate_ammo['selection']['reason'] == 'nonUnique'


@pytest.mark.parametrize('descriptor,reason', [
    ('Torpedo', 'unknownDescriptor'),
    (' torpedo ', 'unknownDescriptor'),
    ({'descriptor': 'torpedo'}, 'descriptorNonString'),
    (None, 'descriptorNone'),
    ('x' * 129, 'descriptorTruncated'),
])
def test_selected_torpedo_descriptor_is_verified_string_or_null_without_normalizing(
        descriptor, reason):
    result, _ = ttx_fixture(descriptor=descriptor)
    assert result['selection']['status'] == 'unknown'
    assert result['selection']['reason'] == reason
    assert result['selection']['descriptor'] == (descriptor
        if isinstance(descriptor, str) and len(descriptor) <= 128 else None)
    assert result['variant'] is None
    assert result['fields'] == {}


def test_selected_torpedo_floatdiff_value_and_delta_are_read_independently():
    mixed, _ = ttx_fixture(value=0.0, delta=float('inf'),
                           max_dist=float('nan'), max_delta=-2.0)
    speed = mixed['fields']['speed']
    assert speed['raw'] == 0.0 and speed['status'] == 'available'
    assert speed['delta']['status'] == 'nonFinite'
    assert speed['delta']['raw'] is None
    assert mixed['fields']['maxDist']['status'] == 'nonFinite'
    assert mixed['fields']['maxDist']['delta']['raw'] == -2.0
    assert mixed['leafStatus'] == 'partial'

    bounds, _ = ttx_fixture(value=1000001.0, delta=-1.0,
                            max_dist=10.0, max_delta=1000001.0)
    assert bounds['fields']['speed']['status'] == 'outOfBounds'
    assert bounds['fields']['speed']['delta']['raw'] == -1.0
    assert bounds['fields']['maxDist']['raw'] == 10.0
    assert bounds['fields']['maxDist']['delta']['status'] == 'outOfBounds'


def test_selected_torpedo_variant_parent_available_does_not_imply_leaf_available():
    result, _ = ttx_fixture(value=float('inf'))
    assert result['status'] == 'available'
    assert result['variantStatus'] == 'available'
    assert result['leafStatus'] == 'partial'
    assert result['fields']['speed']['status'] == 'nonFinite'
    assert result['fields']['speed']['delta']['status'] == 'available'


def test_selected_torpedo_top_status_is_not_availability_of_selfvehicle_only():
    result, _ = ttx_fixture(descriptor='new_descriptor')
    assert result['selfVehicle']['collectionStatus'] == 'available'
    assert result['selfVehicle']['shipTTXStatus'] == 'available'
    assert result['stages']['variants'] == 'available'
    assert result['status'] == 'unknown'


def test_selected_torpedo_pinger_keeps_ttx_route_failure_in_separate_stage():
    result, _ = ttx_fixture(descriptor='pinger', missing_ship_ttx=True)
    assert result['status'] == 'notApplicable'
    assert result['selection']['status'] == 'notApplicable'
    assert result['stages']['selection'] == 'notApplicable'
    assert result['stages']['shipTTX'] == 'missing'
    assert result['ttxStatus'] == 'missing'
    ok, _ = ttx_fixture(descriptor='pinger')
    assert ok['status'] == 'notApplicable'
    assert ok['ttxStatus'] == 'available'


def test_selected_torpedo_safe_boundary_keeps_existing_state():
    state = {'ships': [{'uiId': 3}], 'torpedoes': [], 'self': {'health': 10}}
    result, _, _, _ = integration_fixture(self_collection_raises=True)
    state['selectedTorpedoParamsProbe'] = result
    assert state['ships'] == [{'uiId': 3}]
    assert state['torpedoes'] == []
    assert state['self'] == {'health': 10}
    assert result['status'] != 'available'
    assert result['selfVehicle']['collectionStatus'] == 'partial'


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


@pytest.mark.parametrize('depth,expected_status,expected_raw', [
    (0, 'available', 0), (0.0, 'available', 0.0),
    (False, 'nonNumeric', None), (float('nan'), 'nonFinite', None),
    (float('inf'), 'nonFinite', None), (None, 'none', None),
])
def test_torpedo_depth_is_a_finite_nonbool_raw_candidate(depth, expected_status,
                                                          expected_raw):
    entity = {'id': 7, 't': {'type': 'magnetic', 'depth': depth},
              'm': {'data': {'isHoming': True, 'isSpotted': False}}}
    probe = ui_torpedo_probe(
        Obj(getEntityCollections=lambda name: [entity]),
        {'torpedo': 't', 'mods_DataComponent': 'm'}, [{'uiId': 7}])
    candidate = probe['rows'][0]['depth']
    assert candidate['source'] == 'dataHub.torpedo.depth'
    assert candidate['status'] == expected_status
    assert candidate['raw'] == expected_raw
    assert candidate['unit'] == 'unknown'
    rows = [{'uiId': 7, 'position': [1.0, 123.0, 3.0]}]
    attach_ui_state(rows, probe)
    assert rows[0]['uiState']['depth'] == candidate
    assert rows[0]['uiState']['isHoming'] is True
    assert rows[0]['uiState']['isSpotted'] is False
    assert rows[0]['uiState']['uiType'] == 'magnetic'
    json.dumps(probe, allow_nan=False)


def test_torpedo_depth_missing_and_access_error_keep_distinct_reasons():
    class BrokenDepth(object):
        @property
        def depth(self):
            raise RuntimeError('depth unavailable')

    for component, expected in (({}, 'missing'),
                                (BrokenDepth(), 'readError')):
        probe = ui_torpedo_probe(
            Obj(getEntityCollections=lambda name, c=component:
                [{'id': 1, 't': c}]), Obj(torpedo='t'), [])
        candidate = probe['rows'][0]['depth']
        assert candidate['status'] == expected
        assert candidate['raw'] is None


def test_torpedo_depth_join_requires_unique_ui_id_and_does_not_reuse_frames():
    entity = {'id': 3, 't': {'depth': 12.5}}
    current = [entity]
    hub = Obj(getEntityCollections=lambda name: current)
    components = Obj(torpedo='t')
    api_rows = [{'uiId': 3, 'position': [0.0, 12.5, 0.0]}]
    first = ui_torpedo_probe(hub, components, api_rows)
    attach_ui_state(api_rows, first)
    assert api_rows[0]['uiState']['depth']['raw'] == 12.5
    assert api_rows[0]['uiState']['matchStatus'] == 'exactUiId'

    # The next snapshot has no matching UI observation; no cached depth or y fallback.
    current[:] = [{'id': 4, 't': {'depth': 99.0}}]
    second = ui_torpedo_probe(hub, components, api_rows)
    attach_ui_state(api_rows, second)
    assert api_rows[0]['uiState']['matchStatus'] == 'unknown'
    assert api_rows[0]['uiState']['depth']['status'] == 'unknown'
    assert api_rows[0]['uiState']['depth']['raw'] is None

    current[:] = [{'id': 3, 't': {'depth': 1.0}},
                  {'id': 3, 't': {'depth': 2.0}}]
    duplicate = ui_torpedo_probe(hub, components, api_rows)
    attach_ui_state(api_rows, duplicate)
    assert api_rows[0]['uiState']['matchStatus'] == 'unknown'
    assert api_rows[0]['uiState']['depth']['status'] == 'unknown'
    assert api_rows[0]['uiState']['depth']['raw'] is None


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


def test_weapon_probe_component_keys_missing_getter_and_empty_success():
    no_keys = weapon_hub_probe(Obj(getEntityCollections=lambda name: []), Obj())
    assert no_keys['componentKeys']['weaponSlot']['status'] == 'unsupported'
    assert no_keys['collections']['weaponSlot']['status'] == 'available'
    assert no_keys['collections']['weaponSlot']['rows'] == []
    assert no_keys['collections']['weaponSlot']['componentKeyStatus'] == 'unsupported'
    assert weapon_hub_probe(Obj(), Obj())['collections']['ammo']['status'] == 'unsupported'
    assert weapon_hub_probe(Obj(), None)['componentKeys']['progress']['status'] == 'unsupported'


def test_weapon_probe_slot_progress_is_separate_component_and_preserves_zero_false():
    slot = {'id': 'slot-0', 'ws': Obj(id='slot-0', type=0,
        state=0, active=False, selected=False, shotCount=0, ammoParamsId=0),
        'p': Obj(value=0., max=0.)}
    calls = []
    def collection(name):
        calls.append(name)
        return [slot] if name == 'weaponSlot' else []
    out = weapon_hub_probe(Obj(getEntityCollections=collection),
        Obj(weaponSlot='ws', progress='p', ammo='a', serialLoad='sl'))
    row = out['collections']['weaponSlot']['rows'][0]
    assert calls == ['weaponSlot', 'ammo', 'serialLoad']
    assert row['fields']['shotCount'] == 0 and row['fieldStatus']['shotCount'] == 'available'
    assert row['fields']['active'] is False and row['fieldStatus']['active'] == 'available'
    assert row['progress'] == {'value': 0., 'max': 0.}
    assert row['progressComponentStatus'] == 'available'


def test_weapon_probe_missing_none_and_throwing_component_getters_are_localized():
    class Broken(dict):
        def __getitem__(self, key):
            if key == 'ws':
                raise RuntimeError('component removed')
            return dict.__getitem__(self, key)
    entities = [Broken(id=1, p=Obj(value=0, max=0)),
                {'id': 2, 'ws': None, 'p': Obj(value=0, max=0)}]
    out = weapon_hub_probe(Obj(getEntityCollections=lambda name:
        entities if name == 'weaponSlot' else []),
        Obj(weaponSlot='ws', progress='p', ammo='a', serialLoad='sl'))
    rows = out['collections']['weaponSlot']['rows']
    assert [r['componentStatus'] for r in rows] == ['unknown', 'unknown']
    assert [r['progressComponentStatus'] for r in rows] == ['available', 'available']


def test_weapon_probe_generator_partial_failure_truncates_at_32_and_keeps_zero():
    def broken(name):
        if name != 'weaponSlot':
            return []
        yield {'id': 0, 'ws': Obj(id='slot', shotCount=0)}
        raise RuntimeError('enumeration failed')
    out = weapon_hub_probe(Obj(getEntityCollections=broken),
        Obj(weaponSlot='ws', progress='p', ammo='a', serialLoad='sl'))
    slots = out['collections']['weaponSlot']
    assert slots['status'] == 'partial' and slots['partial'] is True
    assert slots['rows'][0]['fields']['shotCount'] == 0

    hub = Obj(getEntityCollections=lambda name:
        [{'id': n, 'ws': Obj(shotCount=n)} for n in range(40)])
    truncated = weapon_hub_probe(hub, Obj(weaponSlot='ws', progress='p'))
    slots = truncated['collections']['weaponSlot']
    assert len(slots['rows']) == 32 and slots['truncated'] is True
    assert slots['rows'][0]['fields']['shotCount'] == 0


def test_weapon_probe_ammo_uses_fixed_viewdata_fields_and_safe_descriptor_shape():
    class Secret(object):
        def __repr__(self):
            pytest.fail('repr must not be called')
    ammo = Obj(id=0, hasSecondaryAmmo=False, isAutoUsage=False, squadId=0,
        viewData=Obj(ammoId='fish', title='Title', paramsDescriptor={
            'speed': 70., 'bad': float('inf'), 'opaque': Secret()}, secret='omit'))
    out = weapon_hub_probe(Obj(getEntityCollections=lambda name:
        [{'id': 'entity-ammo', 'a': ammo}] if name == 'ammo' else []),
        Obj(weaponSlot='ws', progress='p', ammo='a', serialLoad='sl'))
    row = out['collections']['ammo']['rows'][0]
    assert row['fields']['id'] == 0 and row['fields']['hasSecondaryAmmo'] is False
    assert row['viewData']['ammoId'] == 'fish' and row['viewData']['title'] == 'Title'
    assert row['viewDataFieldStatus']['paramsDescriptor'] == 'available'
    assert row['viewData']['paramsDescriptor'] == {'speed': 70., 'bad': None, 'opaque': None}
    assert 'secret' not in row['viewData']
    json.dumps(out, allow_nan=False)


def test_weapon_probe_serial_load_progress_and_candidate_ids_are_not_joined():
    serial = {'id': 'serial-entity', 'sl': Obj(index=0, weaponType=3, state=0),
              'p': Obj(value=0., max=4.)}
    ammo = {'id': 'ammo-entity', 'a': Obj(id='slot-id', viewData={})}
    hub = Obj(getEntityCollections=lambda name:
        [serial] if name == 'serialLoad' else ([ammo] if name == 'ammo' else []))
    out = weapon_hub_probe(hub, Obj(weaponSlot='ws', progress='p', ammo='a', serialLoad='sl'))
    load = out['collections']['serialLoad']['rows'][0]
    assert load['entityIdCandidate'] == 'serial-entity'
    assert load['fields'] == {'index': 0, 'weaponType': 3, 'state': 0}
    assert load['progress'] == {'value': 0., 'max': 4.}
    assert out['collections']['ammo']['rows'][0]['entityIdCandidate'] == 'ammo-entity'
    assert 'weaponSlot' not in load


def test_weapon_probe_is_history_free_and_failure_does_not_break_main_state():
    data = {'id': 'slot', 'ws': Obj(shotCount=3), 'p': Obj(value=0, max=1)}
    hub = Obj(getEntityCollections=lambda name: [data] if name == 'weaponSlot' else [])
    keys = Obj(weaponSlot='ws', progress='p', ammo='a', serialLoad='sl')
    first = weapon_hub_probe(hub, keys)
    data['ws'].shotCount = 0
    second = weapon_hub_probe(hub, keys)
    assert first['collections']['weaponSlot']['rows'][0]['fields']['shotCount'] == 3
    assert second['collections']['weaponSlot']['rows'][0]['fields']['shotCount'] == 0
    assert first is not second and first['collections'] is not second['collections']

    class Exploding(object):
        @property
        def weaponSlot(self):
            raise RuntimeError('CC unavailable')
    diagnostic = safe_weapon_hub_probe(hub, Exploding())
    state = {'ships': [{'id': 7}], 'torpedoes': []}
    state['weaponHubProbe'] = diagnostic
    assert state['ships'] == [{'id': 7}] and state['torpedoes'] == []
    assert diagnostic['componentKeys']['weaponSlot']['status'] == 'unknown'
    assert diagnostic['collections']['weaponSlot']['status'] == 'available'


def test_weapon_context_uses_ui_self_vehicle_controller_path_without_slot_join():
    watcher = Obj(entity=Obj(id=0, weaponController=Obj(
        selectedWeapon=2, activeIdWeapon=7)))
    calls = []
    hub = Obj(getFirstWatcher=lambda key: calls.append(key) or watcher)
    out = weapon_context_probe(hub, Obj(selfVehicle='sv', weaponSlot='ws'))
    assert calls == ['sv']
    assert out['selfVehicle']['entityId']['raw'] == 0
    assert out['selfVehicle']['entityId']['status'] == 'available'
    assert out['weaponController']['selectedWeapon'] == {
        'source': 'selfVehicle.weaponController.selectedWeapon',
        'status': 'available', 'type': 'int', 'raw': 2,
        'semantics': 'unverified'}
    assert out['weaponController']['activeIdWeapon'] == {
        'source': 'selfVehicle.weaponController.activeIdWeapon',
        'status': 'available', 'type': 'int', 'raw': 7,
        'semantics': 'unverified'}
    assert out['slotContext']['status'] == 'unavailable'
    assert 'matchedSlot' not in out
    json.dumps(out, allow_nan=False)


def test_weapon_context_unknown_does_not_turn_missing_controller_into_false():
    out = safe_weapon_context_probe(
        Obj(getFirstWatcher=lambda key: Obj(entity=Obj(id=1))),
        Obj(selfVehicle='sv'))
    assert out['status'] == 'available'
    assert out['weaponController']['status'] == 'unknown'
    assert 'selectedWeapon' not in out['weaponController']
    missing_getter = safe_weapon_context_probe(Obj(), Obj(selfVehicle='sv'))
    assert missing_getter['selfVehicle']['status'] == 'unsupported'
    assert safe_weapon_context_probe(Obj(), Obj())['selfVehicle']['status'] == 'unsupported'


def test_game_clock_probe_emits_fixed_raw_candidates_only():
    hub = Obj(
        getSingleComponent=lambda key: (Obj(currentTime=0., currentServerTime=12.5)
            if key == 'timer-key' else Obj(duration=11.)),
        getSingleEntity=lambda key: Obj(battleTimer=Obj(battleTime=123.),
                                       battleInfo=Obj(duration=10.)))
    out = game_clock_probe(hub, Obj(timer='timer-key', battleTimer='battle-key',
                                    battleInfo='info-key'))
    assert out['status'] == 'available'
    assert out['candidates']['timer.currentTime']['raw'] == 0.
    assert out['candidates']['timer.currentTime']['status'] == 'available'
    assert out['candidates']['timer.currentServerTime']['raw'] == 12.5
    assert out['candidates']['battleTimer.battleTime']['raw'] == 123.
    assert out['candidates']['battleInfo.duration']['raw'] == 11.
    assert out['candidates']['battleInfo.duration.battleTimerEntity']['raw'] == 10.
    assert out['candidates']['battleTimeLeft']['raw'] == 477.
    assert out['candidates']['battleTimeLeft']['source'].startswith('UI formula:')
    assert out['candidates']['battleTimeLeft']['inferred'] is True
    assert out['candidates']['battleTimeLeft']['formula'] == (
        'battleInfo.duration * 60 - battleTimer.battleTime')
    assert out['candidates']['battleTimeLeft']['formulaStatus'] == 'unverified'
    assert out['candidates']['battleTimeLeft']['sourceUnit'] == 'unverified'
    assert 'inferred' not in out['candidates']['battleTimer.battleTime']
    assert 'inferred' not in out['candidates']['battleInfo.duration']
    assert all(item['semantics'] == 'unverified'
               for item in out['candidates'].values())
    json.dumps(out, allow_nan=False)


def test_game_clock_probe_reads_each_clock_field_once():
    reads = {}
    calls = {'entity': 0}

    class Counted(object):
        def __init__(self, **values):
            self.values = values

        def __getattr__(self, name):
            reads[name] = reads.get(name, 0) + 1
            if name not in self.values:
                raise AttributeError(name)
            return self.values[name]

    def entity(key):
        calls['entity'] += 1
        return Counted(battleTimer=Counted(battleTime=3.),
                       battleInfo=Counted(duration=4.))
    hub = Obj(
        getSingleComponent=lambda key: (Counted(currentTime=1., currentServerTime=2.)
            if key == 'timer-key' else Counted(duration=4.)),
        getSingleEntity=entity)
    game_clock_probe(hub, Obj(timer='timer-key', battleTimer='battle-key',
                              battleInfo='info-key'))
    assert reads == {'currentTime': 1, 'currentServerTime': 1,
                     'battleTimer': 1, 'battleTime': 1,
                     'battleInfo': 1, 'duration': 2}
    assert calls['entity'] == 1


def test_game_clock_missing_and_throwing_paths_remain_unknown_not_zero():
    absent = safe_game_clock_probe(Obj(), Obj(timer='t', battleTimer='bt'))
    assert absent['status'] == 'unsupported'
    assert all(item['status'] == 'unsupported'
               for name, item in absent['candidates'].items()
               if name != 'battleTimeLeft')
    def fail(_):
        raise RuntimeError('not ready')
    failed = game_clock_probe(Obj(getSingleComponent=fail, getSingleEntity=fail),
                              Obj(timer='t', battleTimer='bt'))
    assert failed['candidates']['timer.currentTime']['status'] == 'unknown'
    assert failed['candidates']['timer.currentTime']['raw'] is None
    assert failed['candidates']['battleTimer.battleTime']['status'] == 'unknown'
    assert safe_game_clock_probe(Obj(), None)['status'] == 'unsupported'


def test_context_probe_distinguishes_key_getter_call_and_component_failures():
    missing_key = safe_weapon_context_probe(Obj(), Obj())
    assert missing_key['selfVehicle']['keyStatus'] == 'unsupported'
    assert missing_key['selfVehicle']['getterStatus'] == 'unsupported'
    no_getter = safe_weapon_context_probe(Obj(), Obj(selfVehicle='sv'))
    assert no_getter['selfVehicle']['keyStatus'] == 'available'
    assert no_getter['selfVehicle']['getterStatus'] == 'unsupported'

    def none(_): return None
    getter_none = safe_weapon_context_probe(Obj(getFirstWatcher=none), Obj(selfVehicle='sv'))
    assert getter_none['selfVehicle']['callStatus'] == 'unknown'
    def throws(_): raise RuntimeError('getter failed')
    getter_error = safe_weapon_context_probe(Obj(getFirstWatcher=throws), Obj(selfVehicle='sv'))
    assert getter_error['selfVehicle']['callStatus'] == 'unknown'

    collection_hub = Obj(getEntityCollections=lambda name: [{'id': 1}])
    missing_component = safe_weapon_context_probe(collection_hub,
        Obj(selfVehicle='sv', weaponController='wc', timer='tm',
            battleTimer='bt', battleInfo='bi'))
    row = missing_component['collections']['weaponController']['rows'][0]
    assert row['componentStatus'] == 'unknown'
    assert missing_component['collections']['weaponController']['componentKeyStatus'] == 'available'


def test_named_collections_are_bounded_partial_and_never_choose_a_self_row():
    entities = [{'id': n, 'sv': Obj(selectedWeapon=n)} for n in range(12)]
    def collection(name):
        if name == 'selfVehicle':
            def rows():
                for item in entities:
                    if item['id'] == 4:
                        raise RuntimeError('iteration failed')
                    yield item
            return rows()
        return []
    hub = Obj(getEntityCollections=collection)
    result = safe_weapon_context_probe(hub, Obj(selfVehicle='sv'))
    route = result['collections']['selfVehicle']
    assert route['status'] == 'partial' and route['partial'] is True
    assert len(route['rows']) == 4
    assert route['rows'][0]['fields']['selectedWeapon']['raw'] == 0
    assert 'selectedWeapon' not in result['selfVehicle']

    complete = safe_weapon_context_probe(
        Obj(getEntityCollections=lambda name: entities), Obj(selfVehicle='sv'))
    route = complete['collections']['selfVehicle']
    assert route['truncated'] is True and len(route['rows']) == 8


def test_clock_finite_false_zero_and_no_cross_route_inference():
    hub = Obj(getSingleComponent=lambda key: Obj(currentTime=False,
            currentServerTime=float('inf')) if key == 't' else Obj(duration=10.),
        getSingleEntity=lambda key: Obj(battleTimer=Obj(battleTime=0.)),
        getEntityCollections=lambda name: [])
    out = game_clock_probe(hub, Obj(timer='t', battleTimer='bt', battleInfo='bi'))
    assert out['candidates']['timer.currentTime']['raw'] is False
    assert out['candidates']['timer.currentTime']['type'] == 'bool'
    assert out['candidates']['timer.currentServerTime']['status'] == 'unknown'
    assert out['candidates']['battleTimer.battleTime']['raw'] == 0
    assert out['candidates']['battleInfo.duration']['raw'] == 10.
    assert out['candidates']['battleTimeLeft']['status'] == 'unknown'
    assert out['candidates']['battleTimeLeft']['raw'] is None
    assert out['candidates']['battleInfo.duration']['raw'] == 10.
    assert out['candidates']['battleInfo.collection']['rows'] == []


def test_context_collection_missing_key_still_reports_route_and_no_state_reuse():
    calls = []
    hub = Obj(getEntityCollections=lambda name: calls.append(name) or [])
    first = safe_weapon_context_probe(hub, Obj())
    second = safe_weapon_context_probe(hub, Obj(selfVehicle='sv'))
    assert calls == ['selfVehicle', 'weaponController'] * 2
    assert first['collections']['selfVehicle']['componentKeyStatus'] == 'unsupported'
    assert second['collections']['selfVehicle']['componentKeyStatus'] == 'available'
    assert first is not second


def test_collection_observations_require_one_complete_row_and_keep_slot_separate():
    from torpedo_telemetry import safe_weapon_context_probe

    class Entity(dict):
        pass

    rows = [Entity(wc={'selectedWeapon': 0, 'activeIdWeapon': 'torpedo'})]
    slot_rows = [Entity(ws={'selected': False})]
    def collections(name):
        return rows if name == 'weaponController' else (
            slot_rows if name == 'weaponSlot' else [])
    out = safe_weapon_context_probe(Obj(getEntityCollections=collections),
        {'selfVehicle': 'sv', 'weaponController': 'wc'})
    obs = out['observations']
    assert obs['controllerSelectedWeapon']['status'] == 'available'
    assert obs['controllerSelectedWeapon']['raw'] == 0
    assert obs['controllerSelectedWeapon']['type'] == 'int'
    assert obs['controllerActiveIdWeapon']['raw'] == 'torpedo'
    assert 'weaponSlot' in obs['controllerSelectedWeapon']['scope']
    assert 'selected' not in obs

    for bad_rows, expected in (([], 'unknown'), (rows * 2, 'unknown')):
        candidate = safe_weapon_context_probe(
            Obj(getEntityCollections=lambda name: bad_rows if name == 'weaponController' else []),
            {'selfVehicle': 'sv', 'weaponController': 'wc'})
        assert candidate['observations']['controllerSelectedWeapon']['status'] == expected
    for return_value in (None, RuntimeError('collection call failed')):
        def broken_collection(name):
            if name != 'weaponController':
                return []
            if isinstance(return_value, Exception):
                raise return_value
            return return_value
        candidate = safe_weapon_context_probe(
            Obj(getEntityCollections=broken_collection),
            {'selfVehicle': 'sv', 'weaponController': 'wc'})
        assert candidate['observations']['controllerSelectedWeapon']['status'] == 'unknown'
    class BrokenRows(object):
        def __iter__(self):
            yield rows[0]
            raise RuntimeError('partial')
    partial = safe_weapon_context_probe(
        Obj(getEntityCollections=lambda name: BrokenRows() if name == 'weaponController' else []),
        {'selfVehicle': 'sv', 'weaponController': 'wc'})
    assert partial['collections']['weaponController']['partial'] is True
    assert partial['observations']['controllerSelectedWeapon']['status'] == 'unknown'
    truncated = safe_weapon_context_probe(
        Obj(getEntityCollections=lambda name: rows * 9 if name == 'weaponController' else []),
        {'selfVehicle': 'sv', 'weaponController': 'wc'})
    assert truncated['observations']['controllerSelectedWeapon']['status'] == 'unknown'


def test_collection_clock_observations_same_snapshot_formula_and_fail_closed():
    def run(time, duration, extra=False):
        def entity(component, **fields):
            return {component: fields}
        def collections(name):
            if name == 'battleTimer':
                return [entity('bt', battleTime=time)]
            if name == 'battleInfo':
                return [entity('bi', duration=duration)]
            if name == 'timer':
                return [entity('tm', currentTime=12.5, currentServerTime=99.)]
            return []
        if extra:
            original = collections
            collections = lambda name: original(name) * 2 if name == 'battleInfo' else original(name)
        return safe_game_clock_probe(Obj(getEntityCollections=collections),
            {'timer': 'tm', 'battleTimer': 'bt', 'battleInfo': 'bi'})

    out = run(20, 10.)
    obs = out['observations']
    assert obs['timerCurrentTime']['raw'] == 12.5
    assert obs['battleTimerBattleTime']['raw'] == 20
    assert obs['battleInfoDuration']['raw'] == 10.
    remaining = obs['inferredBattleRemaining']
    assert remaining['raw'] == 580.
    assert remaining['inferred'] is True
    assert remaining['status'] == 'available'
    assert 'Distinct' in remaining['scope'] and 'same snapshot' in remaining['scope']
    assert run(0, 0)['observations']['inferredBattleRemaining']['raw'] == 0
    assert run(-1, 10)['observations']['battleTimerBattleTime']['raw'] == -1
    assert run(-1, 10)['observations']['inferredBattleRemaining']['status'] == 'unknown'
    assert run(2, 10, extra=True)['observations']['inferredBattleRemaining']['status'] == 'unknown'
    assert run(float('inf'), 10)['observations']['battleTimerBattleTime']['status'] == 'unknown'


def test_collection_observations_reject_null_boolean_and_are_not_reused():
    state = {'time': 2}
    def collection(name):
        if name == 'weaponController':
            return [{'wc': {'selectedWeapon': state['time'],
                            'activeIdWeapon': None}}]
        return []
    hub = Obj(getEntityCollections=collection)
    keys = {'selfVehicle': 'sv', 'weaponController': 'wc'}
    first = safe_weapon_context_probe(hub, keys)
    state['time'] = 0
    second = safe_weapon_context_probe(hub, keys)
    assert first['observations']['controllerSelectedWeapon']['raw'] == 2
    assert second['observations']['controllerSelectedWeapon']['raw'] == 0
    assert first['observations']['controllerActiveIdWeapon']['status'] == 'unknown'
    assert first is not second
    state['time'] = False
    boolean = safe_weapon_context_probe(hub, keys)
    assert boolean['observations']['controllerSelectedWeapon']['type'] == 'bool'
    assert boolean['observations']['controllerSelectedWeapon']['raw'] is False


def test_gun_reload_probe_separate_progress_raw_sources_and_false_zero():
    gun = {'g': {'id': 0, 'index': 0, 'type': 'torpedo', 'state': 0,
                 'position': 0.0, 'status': False},
           'p': {'value': 0, 'min': 0.0, 'max': 45.0},
           'bm': {'barrels': [7, 7, 8], 'mode': 0},
           'sm': {'serialLoads': []}}
    bar = {'rb': {'rowsCount': 0, 'order': 0, 'prevOrder': 0,
                  'iconName': 'reload', 'isOutOfBounds': False},
           'weapon': {'type': 'gunType'}}
    barrel = {'gb': {'id': 7}, 'p': {'value': 13.0, 'min': 0.0, 'max': 45.0}}
    refs = {7: {'p': {'value': 13.0, 'min': 0.0, 'max': 45.0}},
            8: {'p': {'value': 21.0, 'min': 0.0, 'max': 45.0}}}
    collections = {'gun': [{'id': 100, 'g': gun['g'], 'p': gun['p'],
                            'bm': gun['bm'], 'sm': gun['sm']}],
                   'reloadBar': [{'id': 200, 'rb': bar['rb'], 'weapon': bar['weapon']}],
                   'gunBarrel': [{'id': 7, 'gb': barrel['gb'], 'p': barrel['p']}]}
    hub = Obj(getEntityCollections=lambda name: collections[name],
              getEntity=lambda ident: refs[ident])
    cc = {'gun': 'g', 'progress': 'p', 'barrelsModifier': 'bm',
          'serialLoaderModifier': 'sm', 'reloadBar': 'rb',
          'weapon': 'weapon', 'gunBarrel': 'gb'}
    out = gun_reload_probe(hub, cc)
    g = out['collections']['gun']['rows'][0]
    assert g['fields']['id']['raw'] == 0
    assert g['fields']['status']['raw'] is False
    assert g['progress']['value']['raw'] == 0
    assert g['mode']['raw'] == 0
    assert g['progress']['value']['source'] == 'gun.progress.value'
    assert out['collections']['reloadBar']['rows'][0]['weaponType']['raw'] == 'gunType'
    assert out['collections']['gunBarrel']['rows'][0]['progress']['value']['raw'] == 13.0
    assert len(out['references']) == 2  # duplicate modifier IDs resolved only once
    assert out['references'][0]['progress']['value']['raw'] == 13.0
    assert 'unverified' in out['references'][0]['scope']
    assert all('source' in row['referenceId'] for row in out['references'])


def test_gun_reload_missing_none_exception_empty_partial_truncated_and_no_carry():
    base_cc = {'gun': 'g', 'progress': 'p', 'barrelsModifier': 'bm',
               'serialLoaderModifier': 'sm', 'reloadBar': 'rb', 'gunBarrel': 'gb',
               'weapon': 'w'}
    missing = safe_gun_reload_probe(Obj(), base_cc)
    assert missing['collections']['gun']['getterStatus'] == 'unsupported'
    assert missing['getEntity']['getterStatus'] == 'unsupported'
    assert safe_gun_reload_probe(Obj(getEntityCollections=lambda name: None), base_cc)[
        'collections']['gun']['status'] == 'unknown'
    assert safe_gun_reload_probe(Obj(getEntityCollections=lambda name: (_ for _ in ()).throw(
        RuntimeError())), base_cc)['collections']['gun']['status'] == 'unknown'
    empty = safe_gun_reload_probe(Obj(getEntityCollections=lambda name: []), base_cc)
    assert empty['collections']['gun']['status'] == 'available'
    assert empty['collections']['gun']['rows'] == []
    no_key = safe_gun_reload_probe(Obj(getEntityCollections=lambda name: []), {})
    assert no_key['collections']['gun']['componentKeyStatus'] == 'unsupported'
    assert no_key['collections']['gun']['rows'] == []

    entity = {'g': {'id': float('nan'), 'index': object(), 'type': 'x', 'state': 0,
                    'position': object(), 'status': None},
              'p': {'value': float('inf'), 'min': False, 'max': 0}}
    partial = safe_gun_reload_probe(Obj(getEntityCollections=lambda name: (
        Broken() if name == 'gun' else [])), base_cc)
    assert partial['collections']['gun']['partial'] is True
    assert partial['collections']['gun']['status'] == 'partial'
    many = [{'id': i, 'g': {'id': i, 'state': 0}} for i in range(33)]
    truncated = safe_gun_reload_probe(Obj(getEntityCollections=lambda name: (
        many if name == 'gun' else [])), base_cc)
    assert truncated['collections']['gun']['truncated'] is True
    assert len(truncated['collections']['gun']['rows']) == 32
    assert truncated['collections']['gun']['rows'][0]['fields']['id']['raw'] == 0
    assert truncated['collections']['gun']['rows'][0]['fields']['state']['raw'] == 0

    first = safe_gun_reload_probe(Obj(getEntityCollections=lambda name: []), base_cc)
    second = safe_gun_reload_probe(Obj(getEntityCollections=lambda name: []), base_cc)
    assert first is not second
    assert second['references'] == []


class Broken(object):
    def __iter__(self):
        yield {'id': 1, 'g': {'id': 1}}
        raise RuntimeError('late enumeration failure')


def test_gun_reload_nonfinite_object_and_reference_ids_never_guess_join():
    gun = {'id': float('nan'), 'index': object(), 'type': 0, 'state': False,
           'position': object(), 'status': None}
    modifier = {'barrels': [11], 'mode': object()}
    hub = Obj(getEntityCollections=lambda name: ([{'id': 55, 'g': gun, 'bm': modifier,
            'p': {'value': float('inf'), 'min': False, 'max': 0}}] if name == 'gun' else
            ([{'id': 999, 'gb': {'id': 999}, 'p': {'value': 44}}]
             if name == 'gunBarrel' else [])),
        getEntity=lambda ident: {'p': {'value': 3, 'min': 0, 'max': 10}})
    cc = {'gun': 'g', 'progress': 'p', 'barrelsModifier': 'bm',
          'serialLoaderModifier': 'sm', 'reloadBar': 'rb', 'gunBarrel': 'gb'}
    out = safe_gun_reload_probe(hub, cc)
    row = out['collections']['gun']['rows'][0]
    assert row['fields']['id']['status'] == 'unknown'
    assert row['fields']['index']['status'] == 'unknown'
    assert row['fields']['state']['raw'] is False
    assert row['progress']['value']['status'] == 'unknown'
    assert out['references'][0]['progress']['value']['raw'] == 3
    assert out['collections']['gunBarrel']['rows'][0]['entityIdCandidate']['raw'] == 999
    assert out['references'][0]['referenceId']['raw'] == 11
    assert out['references'][0]['matchStatus'] == 'unverified'


def test_gun_reload_safe_boundary_keeps_existing_state_on_probe_failure():
    class ExplodingComponents(object):
        @property
        def gun(self):
            raise RuntimeError('component registry unavailable')
    diagnostic = safe_gun_reload_probe(Obj(), ExplodingComponents())
    state = {'ships': [{'uiId': 9}], 'torpedoes': [], 'self': {'health': 100}}
    state['gunReloadProbe'] = diagnostic
    assert state['ships'] == [{'uiId': 9}]
    assert state['torpedoes'] == []
    assert state['self'] == {'health': 100}
    assert diagnostic['status'] == 'unknown'


def _parameter_diag(avatar_rows, parameter_rows, descriptor='torpedo', error=None):
    calls = []
    def collection(name):
        calls.append(name)
        if name == 'playerAvatar':
            if error == 'avatar': raise RuntimeError('avatar unavailable')
            return avatar_rows
        if name == 'parameter':
            if error == 'parameter': raise RuntimeError('parameter unavailable')
            if error == 'parameterPartial':
                def rows():
                    yield parameter_rows[0]
                    raise RuntimeError('parameter iteration failed')
                return rows()
            return parameter_rows
        return []
    hub = Obj(getEntityCollections=collection)
    comps = Obj(parameter='parameter-key')
    selected = {'selection': {'descriptor': descriptor}}
    out = safe_torpedo_tooltip_parameter_probe(hub, comps, selected)
    return out, calls


def _param_entity(ident='torpedoSpeed', owner=7, base=70., current=75.):
    return {'id': ident, 'parameter-key': Obj(ownerID=owner, id=ident,
        baseValue=base, currentValue=current, source='raw', status=1, type='float')}


def test_tooltip_parameter_probe_uses_producer_and_exact_composite_fields():
    out, calls = _parameter_diag([{'id': 7}], [_param_entity()])
    assert calls == ['playerAvatar', 'parameter']
    assert out['ownerEntityId']['raw'] == 7
    assert out['ownerKeyCandidate'] == '7_torpedoSpeed'
    assert out['selectedParameter']['status'] == 'available'
    assert out['selectedParameter']['fields']['currentValue']['raw'] == 75.
    assert out['selectedParameter']['fields']['baseValue']['raw'] == 70.
    assert out['semantics'] == 'unverified'
    json.dumps(out, allow_nan=False)

    assert out['selectedParameter']['matchBasis'] == \
        'parameter.ownerIDAndIdExactCompositeCandidate'
    # GUI lookup spelling remains metadata and is not confused with component.id.
    assert out['ownerKeyCandidate'] == '7_torpedoSpeed'


def test_tooltip_parameter_probe_excludes_known_other_composite_rows_only():
    selected, _ = _parameter_diag([{'id': 7}], [
        _param_entity(owner=8), _param_entity(ident='torpedoSpeedAlt'),
        _param_entity(owner=7, current=75.)])
    assert selected['selectedParameter']['status'] == 'available'
    assert selected['selectedParameter']['fields']['currentValue']['raw'] == 75.

    duplicate, _ = _parameter_diag([{'id': 7}], [
        _param_entity(), _param_entity()])
    assert duplicate['selectedParameter']['reason'] == 'duplicate'

    # A known different owner is excluded, but a missing owner field keeps the
    # collection incomplete rather than being silently ignored.
    missing = _param_entity()
    del missing['parameter-key'].ownerID
    incomplete, _ = _parameter_diag([{'id': 7}], [
        _param_entity(owner=8), missing])
    assert incomplete['selectedParameter']['reason'] == 'incomplete'


def test_tooltip_parameter_probe_is_strict_and_does_not_fallback_to_gui_key():
    wrong_type, _ = _parameter_diag([{'id': 7}], [_param_entity(owner='7')])
    assert wrong_type['selectedParameter']['status'] == 'unknown'
    assert wrong_type['selectedParameter']['reason'] == 'noExactMatch'
    no_fallback, _ = _parameter_diag([{'id': 7}], [
        _param_entity(ident='7_torpedoSpeed')])
    assert no_fallback['selectedParameter']['status'] == 'unknown'
    assert no_fallback['selectedParameter']['reason'] == 'noExactMatch'


def test_tooltip_parameter_probe_is_snapshot_only_and_safe_failure_preserves_main_state():
    entity = _param_entity(current=70.)
    first, _ = _parameter_diag([{'id': 7}], [entity])
    entity['parameter-key'].currentValue = 75.
    second, _ = _parameter_diag([{'id': 7}], [entity])
    assert first['selectedParameter']['fields']['currentValue']['raw'] == 70.
    assert second['selectedParameter']['fields']['currentValue']['raw'] == 75.
    assert first is not second
    state = {'ships': [{'id': 4}], 'torpedoes': [{'uiId': 8}]}
    state['torpedoTooltipParameterProbe'] = safe_torpedo_tooltip_parameter_probe(
        Obj(getEntityCollections=lambda _name: (_ for _ in ()).throw(RuntimeError())),
        Obj(parameter='p'), {'selection': {'descriptor': 'torpedo'}})
    assert state['ships'] == [{'id': 4}]
    assert state['torpedoes'] == [{'uiId': 8}]
    assert state['torpedoTooltipParameterProbe']['status'] == 'unknown'
    assert state['torpedoTooltipParameterProbe']['stages']['owner'] == 'unknown'


@pytest.mark.parametrize('avatars,reason', [([], 'unknown'),
    ([{'id': 7}, {'id': 8}], 'multiple'), ([{'id': True}], 'unknown'),
    ([{'id': 'x' * 129}], 'unknown')])
def test_tooltip_parameter_probe_requires_single_valid_player_avatar(avatars, reason):
    out, _ = _parameter_diag(avatars, [_param_entity()])
    assert out['ownerEntityId']['status'] == 'unknown'
    assert out['stages']['owner'] == reason
    assert out['selectedParameter']['status'] == 'unknown'


def test_tooltip_parameter_probe_duplicate_partial_truncated_and_failures_are_unknown():
    duplicate, _ = _parameter_diag([{'id': 7}], [_param_entity(), _param_entity()])
    assert duplicate['selectedParameter']['reason'] == 'duplicate'
    partial, _ = _parameter_diag([{'id': 7}], [_param_entity(), {'id': 2}])
    assert partial['selectedParameter']['reason'] == 'incomplete'
    trunc, _ = _parameter_diag([{'id': 7}], [_param_entity(i) for i in range(65)])
    assert trunc['parameterCollection']['truncated'] is True
    assert len(trunc['parameterCollection']['rows']) == 64
    assert trunc['selectedParameter']['reason'] == 'truncated'
    bad_owner, _ = _parameter_diag([{'id': 7}], [], error='avatar')
    assert bad_owner['stages']['owner'] == 'unknown'
    bad_param, _ = _parameter_diag([{'id': 7}], [], error='parameter')
    assert bad_param['parameterCollection']['status'] == 'unknown'
    assert bad_param['selectedParameter']['status'] == 'unknown'
    pinger, calls = _parameter_diag([], [], descriptor='pinger')
    assert pinger['selectedParameter']['status'] == 'notApplicable'
    assert calls == []


@pytest.mark.parametrize('owner,reason', [
    (8, 'noExactMatch'),
    (True, 'incomplete'),
    (float('nan'), 'incomplete'),
    (None, 'incomplete'),
])
def test_tooltip_parameter_owner_id_discrepancy_is_diagnostic_not_a_join(owner, reason):
    out, _ = _parameter_diag([{'id': 7}], [_param_entity(owner=owner)])
    selected = out['selectedParameter']
    assert selected['status'] == 'unknown'
    assert selected['reason'] == reason
    assert selected['ownerMatchStatus'] == 'unknown'


def test_tooltip_parameter_missing_owner_id_is_unknown():
    entity = _param_entity()
    del entity['parameter-key'].ownerID
    out, _ = _parameter_diag([{'id': 7}], [entity])
    assert out['selectedParameter']['status'] == 'unknown'
    assert out['selectedParameter']['ownerMatchStatus'] == 'unknown'
    assert out['selectedParameter']['reason'] == 'incomplete'


def test_tooltip_parameter_id_prefix_truncation_cannot_match_and_partial_is_distinct():
    long_owner = 'x' * 115
    gui_key = long_owner + '_torpedoSpeed'
    assert len(gui_key) == 128
    too_long_id = 'torpedoSpeed' + ('x' * 130)
    truncated, _ = _parameter_diag([{'id': long_owner}], [
        _param_entity(ident=too_long_id, owner=long_owner)])
    row = truncated['parameterCollection']['rows'][0]
    assert row['fieldMeta']['id']['truncated'] is True
    assert truncated['selectedParameter']['status'] == 'unknown'
    assert truncated['selectedParameter']['reason'] == 'incomplete'

    partial, _ = _parameter_diag([{'id': 7}], [_param_entity()], error='parameterPartial')
    assert partial['parameterCollection']['status'] == 'partial'
    assert partial['selectedParameter']['reason'] == 'partial'
    collection_truncated, _ = _parameter_diag(
        [{'id': 7}], [_param_entity(i) for i in range(65)])
    assert collection_truncated['selectedParameter']['reason'] == 'truncated'


@pytest.mark.parametrize('current,status', [(float('nan'), 'nonFinite'),
    (float('inf'), 'nonFinite'), (None, 'none'), (1000001., 'outOfBounds'),
    (True, 'nonNumeric')])
def test_tooltip_parameter_values_are_bounded_and_invalid_values_not_selected(current, status):
    out, _ = _parameter_diag([{'id': 7}], [_param_entity(current=current)])
    assert out['selectedParameter']['status'] == 'unknown'
    assert out['selectedParameter']['fields']['currentValue']['status'] == status
