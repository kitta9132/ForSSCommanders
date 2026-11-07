"""Frame-local avatar observations remain separate from API ship rows."""
import ast
import builtins
import json
from pathlib import Path
import textwrap
from types import MethodType, SimpleNamespace as Obj

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf8')
TREE = ast.parse(SOURCE.replace('except Exception, e:', 'except Exception as e:'))
DEFAULT_CC = object()
MISSING_FIELD = object()

import sys
sys.path.insert(0, str(ROOT / 'res_mods/PnFMods/WowsExtractor'))
from ui_health import AvatarRows, index_avatar_health, index_avatar_health_sample, normalize_ui_health
from damage_tracker import roster_ids_from_avatar


def top_function(name, namespace):
    node = next(item for item in TREE.body
                if isinstance(item, ast.FunctionDef) and item.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, 'Main.py', 'exec'), namespace)
    return namespace[name]


def method(name, namespace):
    start = SOURCE.index('    def ' + name + '(')
    ends = [pos for marker in ('\n    def ', '\n    @staticmethod')
            if (pos := SOURCE.find(marker, start + 1)) != -1]
    end = min(ends) if ends else SOURCE.find('\n\ndef _is_mapping', start)
    code = SOURCE[start:end if end != -1 else None]
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(textwrap.dedent(code), namespace)
    return namespace[name]


def attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def without_observation_builtins():
    restricted = dict(vars(builtins))
    for name in ('AttributeError', 'IndexError', 'TypeError', 'iter', 'next'):
        restricted.pop(name, None)
    return restricted


def restricted_function(function, namespace):
    namespace['__builtins__'] = without_observation_builtins()
    return __import__('types').FunctionType(function.__code__, namespace)


def main_namespace(cc):
    ns = {
        '_UNSET': object(), '_STRING_TYPES': (str,), '_INT_TYPES': (int,),
        'long': int, '_try': attempt, '_is_mapping': lambda value:
            isinstance(value, dict), 'CC': cc, 'AvatarRows': AvatarRows,
        'normalize_ui_health': normalize_ui_health,
        'index_avatar_health': index_avatar_health,
        'index_avatar_health_sample': index_avatar_health_sample,
        'roster_ids_from_avatar': roster_ids_from_avatar,
    }
    for name in ('_strict_player_lookup_key', '_observation_scalar',
                 '_observation_exception_name',
                 '_observation_field', '_map_norm_xy', '_point_xy', '_get',
                 '_visibility_type', '_visibility_raw', '_visibility_observation',
                 '_is_mapping'):
        if name == '_is_mapping':
            top_function(name, ns)
        else:
            top_function(name, ns)
    ns['_is_mapping'] = lambda value: isinstance(value, dict)
    return ns


class CountedEntity(dict):
    def __init__(self, **components):
        super().__init__(components)
        self.reads = {}

    def __getitem__(self, name):
        self.reads[name] = self.reads.get(name, 0) + 1
        return dict.__getitem__(self, name)


class CountedCC:
    def __init__(self, **values):
        self._values = values
        self.reads = {}

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        if name not in values:
            raise AttributeError(name)
        reads = object.__getattribute__(self, 'reads')
        reads[name] = reads.get(name, 0) + 1
        return values[name]


class AttributeAvatar:
    """Attribute-backed API component with an optional playerId property."""
    def __init__(self, avatar_id, player_id=MISSING_FIELD):
        self._avatar_id = avatar_id
        self._player_id = player_id
        self.reads = {'id': 0, 'playerId': 0}

    @property
    def id(self):
        self.reads['id'] += 1
        return self._avatar_id

    @property
    def playerId(self):
        self.reads['playerId'] += 1
        if self._player_id is MISSING_FIELD:
            raise AttributeError('playerId unavailable')
        return self._player_id


def avatar_entity(player_id, *, avatar_id=None, map_position=True,
                  health=(800, 1000, True), vehicle_id=None):
    avatar = {'playerId': player_id}
    if avatar_id is not None:
        avatar['id'] = avatar_id
    components = {'avatar': avatar}
    if vehicle_id is not None:
        components['vehicle'] = {'id': vehicle_id}
    if health is not None:
        value, maximum, alive = health
        components['health'] = {'value': value, 'max': maximum, 'isAlive': alive}
    if map_position is not False:
        if map_position is True:
            map_position = (0.25, 0.75)
        components['mapPosition'] = {'position': map_position, 'yaw': 0.0}
    return CountedEntity(**components)


def frame(entities, ships, *, status='complete', now=10.0, cc=DEFAULT_CC):
    if cc is DEFAULT_CC:
        cc = Obj(avatar='avatar', vehicle='vehicle', health='health',
                 mapPosition='mapPosition', visibility='visibility')
    ns = main_namespace(cc)
    map_positions = method('_collect_map_positions', ns)
    collect_health = method('_collect_avatar_health', ns)
    build_observations = method('_build_avatar_observations', ns)
    holder = AvatarRows(entities, complete=(status == 'complete'))
    collector = Obj(_diagnosticsEnabled=False, _diagnosticsSampleDue=False,
                    _mapVisibility={}, _mapVisibilityDiagnostics={})
    if status == 'complete':
        health_index = collect_health(collector, holder)
    else:
        holder.sample_health(cc)  # preserve raw fields from captured rows only
        health_index = collect_health(collector, [])
    map_index = map_positions(collector, holder)
    snapshot = {'entities': holder, 'status': status, 'count': len(holder),
                'limit': 256, 'reason': None if status == 'complete' else 'iterationError'}
    observations = build_observations(collector, snapshot, now, ships)
    return observations, health_index, map_index, holder


@pytest.mark.parametrize(('map_count', 'expected_map_count'), [
    (24, 24), (20, 20), (0, 0),
])
def test_24_avatar_20_api_ship_coverage_and_map_variants(map_count, expected_map_count):
    entities = [avatar_entity(pid, map_position=(pid <= map_count))
                for pid in range(1, 25)]
    ships = [{'playerId': pid} for pid in range(1, 21)]
    observations, _health, _map_index, _holder = frame(entities, ships, now=37.5)

    assert len(observations['rows']) == 24
    assert len(ships) == 20  # avatar rows never become synthetic API ships
    assert observations['status'] == 'complete'
    assert observations['source'] == 'dataHub.getEntityCollections(avatar)'
    assert observations['sampleTs'] == 37.5
    coverage = observations['coverage']
    assert coverage['sampledEntityCount'] == 24
    assert coverage['inputComplete'] is True
    assert coverage['inputAvailability'] == 'available'
    assert coverage['distinctPlayerIdCount'] == 24
    assert coverage['apiMatchedCount'] == 20
    assert coverage['missingInApiCount'] == 4
    assert coverage['mapPositionAvailableCount'] == expected_map_count
    assert [r['apiPresence']['status'] for r in observations['rows'][-4:]] == [
        'missingInApi'] * 4
    assert observations['rows'][0]['mapPosition']['freshness'] == 'unknown'
    assert observations['rows'][0]['mapPosition']['source'] == 'dataHub.mapPosition'
    assert all(entity.reads.get('mapPosition', 0) == 1 for entity in entities)
    json.dumps(observations, allow_nan=False)


def test_partial_capture_keeps_raw_observations_but_never_asserts_api_absence_or_death():
    entities = [
        avatar_entity(0, health=(0, 900, True), map_position=(0.1, 0.2)),
        avatar_entity(77, health=(400, 900, None), map_position=(0.3, 0.4)),
    ]
    observations, health_index, _maps, _holder = frame(
        entities, [{'playerId': 0}], status='partial', now=23.0)
    assert health_index == {}  # incomplete index cannot update ships as alive/dead
    assert observations['status'] == 'partial'
    assert observations['sampleTs'] == 23.0
    assert observations['coverage']['inputComplete'] is False
    assert observations['coverage']['inputAvailability'] == 'available'
    assert observations['coverage']['apiMatchedCount'] == 1
    assert observations['coverage']['missingInApiCount'] == 0
    assert observations['coverage']['apiPresenceUnknownCount'] == 1
    assert observations['rows'][1]['apiPresence'] == {
        'status': 'unknown', 'source': 'state.ships', 'reason': 'inputIncomplete'}
    first_health = observations['rows'][0]['health']
    assert first_health['raw'] == {'value': 0, 'max': 900, 'isAlive': True}
    assert first_health['normalized'] == {
        'health': 900.0, 'maxHealth': 900.0, 'untickedFull': True}
    assert first_health['normalized'].get('alive') is not False
    assert observations['rows'][1]['health']['raw']['isAlive'] is None
    assert observations['rows'][0]['mapPosition']['status'] == 'available'
    json.dumps(observations, allow_nan=False)


def test_strict_ids_duplicate_conflicts_and_avatar_id_are_not_join_fallbacks():
    entities = [
        avatar_entity(0, avatar_id=9),
        avatar_entity(False, avatar_id=1),
        avatar_entity(None, avatar_id=2),
        avatar_entity(None, map_position=(0.6, 0.4)),
        avatar_entity(5), avatar_entity(5),
    ]
    ships = [{'playerId': 0}, {'playerId': 2}, {'playerId': 5}, {'playerId': 5}]
    observations, _health, _maps, _holder = frame(entities, ships)
    rows = observations['rows']
    assert rows[0]['playerId'] == 0
    assert rows[0]['apiPresence']['status'] == 'matched'
    assert rows[1]['playerIdStatus'] == 'unknown'  # bool is not an ID
    assert rows[1]['apiPresence']['status'] == 'unknown'
    assert rows[2]['playerIdStatus'] == 'unknown'  # avatar.id=2 is not joined
    assert rows[2]['apiPresence']['reason'] == 'unmatchablePlayerId'
    assert rows[2]['identifierCandidates']['avatarId'] == {
        'source': 'dataHub.avatar.id', 'namespace': 'avatar.id',
        'status': 'available', 'raw': 2, 'semantics': 'unverified'}
    assert rows[4]['apiPresence']['reason'] == 'duplicateIdConflict'
    assert rows[5]['apiPresence']['reason'] == 'duplicateIdConflict'
    assert rows[3]['apiPresence']['reason'] == 'unmatchablePlayerId'
    assert rows[3]['mapPosition']['status'] == 'available'
    assert entities[3].reads['mapPosition'] == 1  # observation-only row fallback
    assert observations['coverage']['unmatchableIdCount'] == 3
    assert observations['coverage']['duplicateIdConflictCount'] == 1
    assert observations['coverage']['missingInApiCount'] == 0
    json.dumps(observations, allow_nan=False)


@pytest.mark.parametrize('player_id', [MISSING_FIELD, None], ids=['missing', 'none'])
def test_attribute_avatar_id_candidate_is_sampled_once_without_confirmed_join(player_id):
    avatars = [AttributeAvatar(pid, player_id=player_id) for pid in range(1, 13)]
    entities = [CountedEntity(
        avatar=avatar,
        health={'value': 500, 'max': 1000, 'isAlive': True},
        mapPosition={'position': (0.25, 0.75), 'yaw': 0.0})
        for avatar in avatars]
    ships = [{'playerId': pid} for pid in range(1, 13)]

    observations, _health, _maps, _holder = frame(entities, ships)

    assert all(avatar.reads == {'id': 1, 'playerId': 1} for avatar in avatars)
    assert all(entity.reads.get('mapPosition', 0) == 1 for entity in entities)
    assert all(row['playerIdStatus'] == 'unknown' for row in observations['rows'])
    assert all(row['apiPresence'] == {
        'status': 'unknown', 'source': 'state.ships',
        'reason': 'unmatchablePlayerId'} for row in observations['rows'])
    assert [row['identifierCandidates']['avatarId']['raw']
            for row in observations['rows']] == list(range(1, 13))
    consistency = observations['candidateConsistency']
    assert consistency['candidateAvailableCount'] == 12
    assert consistency['candidateExactValueMatchCount'] == 12
    assert consistency['candidateUnmatchedInSnapshotCount'] == 0
    assert consistency['candidateAmbiguousCount'] == 0
    assert consistency['candidateUnknownCount'] == 0
    # Confirmed coverage remains independent of the candidate value match.
    assert observations['coverage']['distinctPlayerIdCount'] == 0
    assert observations['coverage']['apiMatchedCount'] == 0
    assert observations['coverage']['unmatchableIdCount'] == 12
    json.dumps(observations, allow_nan=False)


def test_candidate_consistency_uses_strict_types_and_quarantines_duplicates_and_unsafe_ids():
    candidate_ids = [0, 4, 4, '5', 6.0, False, float('nan'),
                     float('inf'), object(), None]
    entities = [avatar_entity(None, avatar_id=avatar_id, map_position=False)
                for avatar_id in candidate_ids]
    ships = [{'playerId': pid} for pid in (0, 4, 4, 5, 6, False)]

    observations, _health, _maps, _holder = frame(entities, ships)

    candidates = [row['identifierCandidates']['avatarId']
                  for row in observations['rows']]
    assert [candidate['status'] for candidate in candidates] == [
        'available', 'available', 'available', 'available', 'available',
        'unknown', 'unknown', 'unknown', 'unknown', 'unknown']
    assert [candidate.get('raw') for candidate in candidates[:5]] == [
        0, 4, 4, '5', 6.0]
    assert all('raw' not in candidate for candidate in candidates[5:])
    assert candidates[5]['reason'] == 'invalidId'  # bool ID is never emitted
    assert candidates[6]['reason'] == 'invalidId'  # non-finite ID is never emitted
    assert candidates[7]['reason'] == 'invalidId'
    assert candidates[8]['reason'] == 'invalidId'  # no repr/string conversion
    assert candidates[9]['reason'] == 'notRecorded'

    consistency = observations['candidateConsistency']
    assert consistency['candidateAvailableCount'] == 5
    assert consistency['candidateExactValueMatchCount'] == 1  # integer zero
    assert consistency['candidateUnmatchedInSnapshotCount'] == 2  # str/int, float/int
    assert consistency['candidateAmbiguousCount'] == 2  # duplicate avatar + ships IDs
    assert consistency['candidateUnknownCount'] == 5
    assert consistency['duplicateAvatarIdCount'] == 1
    assert consistency['duplicateShipPlayerIdCount'] == 1
    # Candidate matches never promote strict playerId/apiPresence coverage.
    assert observations['coverage']['distinctPlayerIdCount'] == 0
    assert observations['coverage']['apiMatchedCount'] == 0
    assert observations['coverage']['unmatchableIdCount'] == len(entities)
    assert all(row['apiPresence']['status'] == 'unknown'
               for row in observations['rows'])
    json.dumps(observations, allow_nan=False)


def test_partial_cc_missing_and_unsampled_candidate_states_do_not_confirm_absence():
    partial, _health, _maps, _holder = frame(
        [avatar_entity(0, avatar_id=0), avatar_entity(77, avatar_id=77)],
        [{'playerId': 0}], status='partial')
    assert partial['candidateConsistency']['avatarInputComplete'] is False
    assert partial['candidateConsistency']['candidateExactValueMatchCount'] == 1
    assert partial['candidateConsistency']['candidateUnmatchedInSnapshotCount'] == 1
    assert partial['rows'][1]['apiPresence'] == {
        'status': 'unknown', 'source': 'state.ships', 'reason': 'inputIncomplete'}
    assert partial['coverage']['missingInApiCount'] == 0

    truncated, _health, _maps, _holder = frame(
        [avatar_entity(91, avatar_id=91)], [], status='truncated')
    assert truncated['candidateConsistency']['avatarInputComplete'] is False
    assert truncated['candidateConsistency'][
        'candidateUnmatchedInSnapshotCount'] == 1
    assert truncated['rows'][0]['apiPresence'] == {
        'status': 'unknown', 'source': 'state.ships', 'reason': 'inputIncomplete'}
    assert truncated['coverage']['missingInApiCount'] == 0

    no_cc, _health, _maps, _holder = frame(
        [avatar_entity(None, avatar_id=88)], [], cc=None)
    no_cc_candidate = no_cc['rows'][0]['identifierCandidates']['avatarId']
    assert no_cc_candidate['status'] == 'unknown'
    assert no_cc_candidate['reason'] == 'notRecorded'
    assert no_cc['candidateConsistency']['candidateUnknownCount'] == 1

    ns = main_namespace(Obj(avatar='avatar', vehicle='vehicle', health='health',
                            mapPosition='mapPosition'))
    build = method('_build_avatar_observations', ns)
    no_sample = build(Obj(), {'entities': [object()], 'status': 'complete'},
                      11.0, [])
    no_sample_candidate = no_sample['rows'][0]['identifierCandidates']['avatarId']
    assert no_sample_candidate['status'] == 'unknown'
    assert no_sample_candidate['reason'] == 'notRecorded'
    assert no_sample['candidateConsistency']['candidateUnknownCount'] == 1
    json.dumps(partial, allow_nan=False)
    json.dumps(truncated, allow_nan=False)
    json.dumps(no_cc, allow_nan=False)
    json.dumps(no_sample, allow_nan=False)


def test_cc_missing_component_exception_and_nonfinite_values_stay_unknown():
    class BadEntity(CountedEntity):
        def __getitem__(self, name):
            self.reads[name] = self.reads.get(name, 0) + 1
            if name == 'mapPosition':
                raise RuntimeError('component unavailable')
            return dict.__getitem__(self, name)

    entities = [
        avatar_entity(1, map_position=False),
        BadEntity(avatar={'playerId': 2}, health={'value': float('nan'),
            'max': object(), 'isAlive': None}),
    ]
    observations, _health, _maps, _holder = frame(entities, [], now=5.0)
    assert observations['rows'][0]['mapPosition']['componentStatus'] == 'componentMissing'
    assert observations['rows'][1]['mapPosition']['componentStatus'] == 'componentReadError'
    assert observations['rows'][1]['health']['raw'] == {
        'value': None, 'max': None, 'isAlive': None}
    json.dumps(observations, allow_nan=False)

    no_cc, _health, _maps, _holder = frame(
        [avatar_entity(3)], [], now=6.0, cc=None)
    assert no_cc['rows'][0]['playerIdStatus'] == 'unknown'
    assert no_cc['rows'][0]['mapPosition']['componentStatus'] == 'ccKeyMissing'
    assert no_cc['rows'][0]['health']['componentStatus'] == 'ccKeyMissing'


def test_observation_helpers_survive_restricted_exception_builtins():
    class AttributeFailure:
        @property
        def position(self):
            raise RuntimeError('private getter detail')

    main_ns = main_namespace(Obj(mapPosition='mapPosition'))
    for name in ('_observation_exception_name', '_observation_field'):
        function = main_ns[name]
        main_ns[name] = restricted_function(function, main_ns)
    observe_field = main_ns['_observation_field']
    assert observe_field(Obj(), 'position') == (None, 'missing')
    assert observe_field(AttributeFailure(), 'position') == (None, 'readError')
    assert observe_field(None, 'position') == (None, 'componentMissing')
    assert observe_field({'position': None}, 'position') == (None, 'none')
    assert 'private getter detail' not in str(
        observe_field(AttributeFailure(), 'position'))

    import ui_health
    health_ns = {}
    for name in ('_comp_get', '_observation_exception_name',
                 '_entity_comp_observation', '_field_observation',
                 '_sample_avatar_health'):
        health_ns[name] = restricted_function(getattr(ui_health, name), health_ns)
    sample_health = health_ns['_sample_avatar_health']

    class HealthFieldFailure:
        @property
        def value(self):
            raise RuntimeError('private health detail')

    class HybridHealth:
        @property
        def value(self):
            raise RuntimeError('property fallback')
        def __getitem__(self, name):
            return {'value': 123, 'max': 900, 'isAlive': True}[name]

    class NoneHybridHealth:
        @property
        def value(self):
            return None
        def __getitem__(self, name):
            raise AssertionError('None attribute must retain legacy precedence')

    class ReadErrorEntity(dict):
        def __getitem__(self, name):
            if name == 'health':
                raise RuntimeError('private component detail')
            return dict.__getitem__(self, name)

    cc = Obj(health='health')
    missing_component, missing_meta = sample_health({}, cc)
    assert missing_meta['componentStatus'] == 'componentMissing'
    assert missing_component == {'value': None, 'max': None, 'isAlive': None}
    no_cc, no_cc_meta = sample_health({'health': {}}, None)
    assert no_cc_meta['componentStatus'] == 'ccKeyMissing'
    assert no_cc == {'value': None, 'max': None, 'isAlive': None}
    read_error, read_error_meta = sample_health(
        ReadErrorEntity(health={}), cc)
    assert read_error_meta['componentStatus'] == 'componentReadError'
    assert read_error_meta['fieldStatus']['value'] == 'componentMissing'
    absent_fields, absent_meta = sample_health({'health': HealthFieldFailure()}, cc)
    assert absent_meta['fieldStatus']['value'] == 'readError'
    assert absent_fields['value'] is None
    hybrid_fields, hybrid_meta = sample_health({'health': HybridHealth()}, cc)
    assert hybrid_fields['value'] == 123
    assert hybrid_meta['fieldStatus']['value'] == 'available'
    none_fields, none_meta = sample_health({'health': NoneHybridHealth()}, cc)
    assert none_fields['value'] is None
    assert none_meta['fieldStatus']['value'] == 'none'
    assert 'private health detail' not in str(absent_meta)

    class MapReadErrorEntity(CountedEntity):
        def __getitem__(self, name):
            if name == 'mapPosition':
                raise RuntimeError('private map detail')
            return CountedEntity.__getitem__(self, name)

    cc_with_map = Obj(avatar='avatar', vehicle='vehicle', health='health',
                      mapPosition='mapPosition', visibility='visibility')
    map_ns = main_namespace(cc_with_map)
    map_method = method('_collect_map_positions', map_ns)
    map_ns['_collect_map_positions'] = restricted_function(map_method, map_ns)
    map_observe = method('_build_avatar_observations', map_ns)
    map_ns['_build_avatar_observations'] = restricted_function(map_observe, map_ns)
    collector = Obj(_diagnosticsEnabled=False, _diagnosticsSampleDue=False,
                    _mapVisibility={}, _mapVisibilityDiagnostics={})
    entities = AvatarRows([
        avatar_entity(1, map_position=False),
        MapReadErrorEntity(avatar={'playerId': 2}, health={
            'value': 20, 'max': 100, 'isAlive': True}),
    ])
    entities.sample_health(cc_with_map)
    map_ns['_collect_map_positions'](collector, entities)
    snapshot = {'entities': entities, 'status': 'complete', 'count': 2,
                'limit': 256, 'reason': None}
    observations = map_ns['_build_avatar_observations'](
        collector, snapshot, 5.0, [])
    assert observations['rows'][0]['mapPosition']['componentStatus'] == 'componentMissing'
    assert observations['rows'][1]['mapPosition']['componentStatus'] == 'componentReadError'
    assert observations['rows'][1]['health']['raw']['value'] == 20
    assert 'private map detail' not in str(observations)

    no_cc_ns = main_namespace(None)
    no_cc_map = method('_collect_map_positions', no_cc_ns)
    no_cc_ns['_collect_map_positions'] = restricted_function(no_cc_map, no_cc_ns)
    no_cc_holder = AvatarRows([avatar_entity(3)])
    no_cc_map(collector, no_cc_holder)
    no_cc_build = method('_build_avatar_observations', no_cc_ns)
    no_cc_ns['_build_avatar_observations'] = restricted_function(no_cc_build, no_cc_ns)
    no_cc_observations = no_cc_ns['_build_avatar_observations'](
        collector, {'entities': no_cc_holder, 'status': 'complete'}, 6.0, [])
    assert no_cc_observations['rows'][0]['mapPosition']['componentStatus'] == 'ccKeyMissing'
    assert no_cc_observations['rows'][0]['health']['componentStatus'] == 'ccKeyMissing'


def test_each_frame_uses_current_sample_and_map_component_is_read_once():
    first_entities = [avatar_entity(1, avatar_id=101,
                                    map_position=(0.2, 0.3), health=(10, 20, True))]
    first, _health, _maps, _holder = frame(first_entities, [], now=10.0)
    second_entities = [avatar_entity(1, avatar_id=202,
                                     map_position=(0.8, 0.7), health=(18, 20, True))]
    second, _health, _maps, _holder = frame(second_entities, [], now=20.0)
    assert first['sampleTs'] == 10.0 and second['sampleTs'] == 20.0
    assert first['rows'][0]['mapPosition']['raw'] == [0.2, 0.3]
    assert second['rows'][0]['mapPosition']['raw'] == [0.8, 0.7]
    assert first['rows'][0]['identifierCandidates']['avatarId']['raw'] == 101
    assert second['rows'][0]['identifierCandidates']['avatarId']['raw'] == 202
    assert second['rows'][0]['health']['raw']['value'] == 18
    assert first_entities[0].reads['mapPosition'] == 1
    assert second_entities[0].reads['mapPosition'] == 1
    invalid_clock, _health, _maps, _holder = frame(
        [avatar_entity(1)], [], now=float('nan'))
    assert invalid_clock['sampleTs'] is None
    json.dumps(invalid_clock, allow_nan=False)


def test_avatar_collection_unavailable_is_distinct_from_partial_iteration():
    cc = Obj(avatar='avatar', vehicle='vehicle', health='health',
             mapPosition='mapPosition', visibility='visibility')
    ns = main_namespace(cc)
    build = method('_build_avatar_observations', ns)
    collector = Obj()
    unavailable = build(collector, {
        'entities': AvatarRows([], complete=False), 'status': 'partial',
        'count': 0, 'limit': 256, 'reason': 'getterError'}, 8.0, [])
    partial = build(collector, {
        'entities': AvatarRows([], complete=False), 'status': 'partial',
        'count': 0, 'limit': 256, 'reason': 'iterationError'}, 8.0, [])
    assert unavailable['coverage']['inputAvailability'] == 'unavailable'
    assert partial['coverage']['inputAvailability'] == 'available'


def test_main_state_reuses_existing_getter_budget_for_24_avatars_and_20_ships():
    cc = CountedCC(avatar='avatar', vehicle='vehicle', health='health',
                   mapPosition='mapPosition', visibility='visibility')
    avatar_components = [AttributeAvatar(pid, player_id=pid)
                         for pid in range(1, 25)]
    entities = [CountedEntity(
        avatar=avatar,
        vehicle={'id': 1000 + pid},
        health={'value': 800, 'max': 1000, 'isAlive': True},
        mapPosition={'position': (pid / 100.0, 0.5), 'yaw': 0.0})
        for pid, avatar in enumerate(avatar_components, 1)]
    player_rows = [{'playerId': pid, 'shipId': 1000 + pid,
                    'teamId': 1 if pid <= 12 else 2}
                   for pid in range(1, 21)]
    api_ships = [Obj(_Ship__id=1000 + pid, uiId=pid, teamId=1 if pid <= 12 else 2,
                     isAlive=lambda: True, getPosition=lambda: None)
                 for pid in range(1, 21)]
    calls = {'avatar': 0, 'playersInfo': 0, 'players': 0, 'allShips': 0,
             'vehicleLookup': 0, 'selfInfo': 0, 'selfShip': 0}

    class Hub:
        def getEntityCollections(self, name):
            if name != 'avatar':
                raise AssertionError('unexpected collection: ' + name)
            calls['avatar'] += 1
            return entities

    class Battle:
        def getSelfPlayerInfo(self):
            calls['selfInfo'] += 1
            return None
        def getSelfPlayerShip(self):
            calls['selfShip'] += 1
            return None
        def getPlayersInfo(self):
            calls['playersInfo'] += 1
            return player_rows
        def getPlayers(self):
            calls['players'] += 1
            return player_rows
        def getAllShips(self):
            calls['allShips'] += 1
            return api_ships
        def getPlayerByVehicleId(self, vehicle_id):
            calls['vehicleLookup'] += 1
            raise AssertionError('strict full index should satisfy all ships')

    ns = main_namespace(cc)
    ns.update({
        'dataHub': Hub(), 'battle': Battle(), '_mapCalibration': None,
        '_try': attempt, 'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
        'INVALID': -1, 'apply_ui_health': __import__('ui_health').apply_ui_health,
        'TorpedoTelemetry': None,
    })
    c = Obj()
    for name in ('_capture_avatar_snapshot', '_remember_sampled_player_vehicle',
                 '_remember_roster_vehicles',
                 '_collect_avatar_health', '_collect_map_positions',
                 '_build_avatar_observations', '_build_ships', '_build_state'):
        fn = method(name, ns)
        setattr(c, name, MethodType(fn, c))
    build_observations = c._build_avatar_observations

    def build_observations_without_new_cc_reads(*args):
        before = dict(cc.reads)
        result = build_observations(*args)
        assert cc.reads == before
        return result

    c._build_avatar_observations = build_observations_without_new_cc_reads
    c._active = True
    c._diagnosticsEnabled = False
    c._diagnosticsSampleDue = False
    c._performanceProfiler = None
    c._battleId = 'fixture'
    c._selfTeam = None
    c._remember_player_vehicle = lambda player: None
    c._damage = Obj(remember=lambda *args: None,
                    snapshot=lambda: {'inflicted': {}, 'received': {}, 'teamTotal': {}})
    c._mapCalibration = Obj(
        observe=lambda samples, now: {'status': 'unknown'},
        update=lambda samples, now: None,
        live_model_status=lambda: {'status': 'unknown', 'coefficients': None},
        snapshot=lambda: {'status': 'unknown'},
        world_to_map=lambda *args: None)
    c._positionFallbacksEnabled = False
    c._relation = lambda team: 1 if team == 1 else 2
    c._map_to_world = lambda *args: None
    c._ship_world_position_threshold = lambda: None
    c._selfSystemsSamplingEnabled = True
    c._selfSystemsSamplingDue = True
    c._torpedoArmamentSamplingEnabled = True
    c._torpedoArmamentSamplingDue = True
    c._mapCalibrationSnapshotInterval = 1.0
    c._mapCalibrationSnapshotDue = False
    c._shipWorldPositionSamplingEnabled = True
    c._shipWorldPositionSamplingDue = True
    c._shipWorldPositionFarDivisor = 5.0
    c._get_ship_position = lambda *args, **kwargs: (None, {
        'status': 'unknown', 'source': 'ship.getPosition', 'attempted': True,
        'reason': 'none', 'policy': 'coreDirectOnly', 'fallbackStatus': 'notSampled',
        'fallbackSource': None})
    c._self_team = lambda info=None: 1
    c._build_self = lambda hp, info=None, ship=None: {}
    c._torpedoes = Obj(torpedoes=lambda team: ([], {'available': True,
        'status': 'available'}), armament=lambda ship=None: {},
        systems=lambda ship=None: {})
    c._torpedoMotion = Obj(update=lambda *args: None)

    state = c._build_state(44.0)
    assert calls == {'avatar': 1, 'playersInfo': 1, 'players': 0,
                     'allShips': 1, 'vehicleLookup': 0,
                     'selfInfo': 1, 'selfShip': 1}
    assert len(state['ships']) == 20
    assert len(state['avatarObservations']['rows']) == 24
    assert state['avatarObservations']['coverage']['apiMatchedCount'] == 20
    assert state['avatarObservations']['coverage']['missingInApiCount'] == 4
    assert state['avatarObservations']['candidateConsistency'][
        'candidateExactValueMatchCount'] == 20
    assert state['avatarObservations']['candidateConsistency'][
        'candidateUnmatchedInSnapshotCount'] == 4
    assert state['avatarObservations']['sampleTs'] == state['ts']
    assert all(entity.reads['mapPosition'] == 1 for entity in entities)
    assert all(entity.reads == {
        'avatar': 1, 'vehicle': 1, 'health': 1, 'mapPosition': 1}
        for entity in entities)
    assert all(avatar.reads == {'id': 1, 'playerId': 1}
               for avatar in avatar_components)
    # Existing producer CC accesses; observation assembly adds none (checked
    # by the wrapper above).
    assert cc.reads == {
        'avatar': 26, 'vehicle': 25, 'health': 24,
        'mapPosition': 1, 'visibility': 1}
    json.dumps(state, allow_nan=False)


def test_disabled_collection_and_terminal_frame_never_retain_observations():
    calls = []
    ns = {'_now': lambda: 9.0, '_try': attempt, 'SCHEMA_VERSION': 1,
          'WIRE_API_VERSION': '1.0', '_empty_avatar_observations':
              top_function('_empty_avatar_observations', main_namespace(None)),
          'logInfo': lambda *args: None}
    start = method('_start_collection', ns)
    quit_battle = method('_on_battle_quit', ns)
    c = Obj(_active=False, _collectionEnabled=False, _battleId='fixture',
            _damage=Obj(snapshot=lambda: {}), _mapCalibration=Obj(clear=lambda: None),
            _torpedoMotion=Obj(clear=lambda: None), _stop_tick=lambda: None,
            _write_state=calls.append)
    start(c)
    assert calls[-1]['avatarObservations']['status'] == 'disabled'
    assert calls[-1]['avatarObservations']['rows'] == []
    assert not hasattr(c, '_avatarObservations')
    quit_battle(c)
    assert calls[-1]['active'] is False
    assert calls[-1]['avatarObservations']['status'] == 'notSampled'
    assert calls[-1]['avatarObservations']['rows'] == []
    assert not hasattr(c, '_avatarObservations')
