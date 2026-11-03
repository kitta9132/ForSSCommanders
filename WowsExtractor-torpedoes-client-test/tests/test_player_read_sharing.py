from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'res_mods/PnFMods/WowsExtractor'))
from damage_tracker import DamageTracker, roster_ids_from_avatar


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
    encoding='utf-8')


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _mapping(value):
    return isinstance(value, dict)


def _function(name, ns):
    start = SOURCE.index('def ' + name + '(')
    ends = [pos for marker in ('\ndef ', '\nclass ')
            if (pos := SOURCE.find(marker, start + 1)) != -1]
    end = min(ends) if ends else len(SOURCE)
    exec(textwrap.dedent(SOURCE[start:end]), ns)
    return ns[name]


def _method(name, ns):
    start = SOURCE.index('    def ' + name + '(')
    ends = [pos for marker in ('\n    def ', '\n    @staticmethod')
            if (pos := SOURCE.find(marker, start + 1)) != -1]
    end = min(ends) if ends else len(SOURCE)
    exec(textwrap.dedent(SOURCE[start:end]), ns)
    return ns[name]


def _roster_reader(battle, cc=None, hub=None):
    ns = {
        '_UNSET': object(), '_try': _attempt,
        '_get': lambda obj, key, default=None: (
            obj.get(key, default) if isinstance(obj, dict)
            else getattr(obj, key, default)),
        '_is_mapping': _mapping, 'battle': battle, 'CC': cc, 'dataHub': hub,
        'roster_ids_from_avatar': roster_ids_from_avatar,
    }
    ns['_STRING_TYPES'] = (str,)
    ns['_INT_TYPES'] = (int,)
    for name in ('_strict_player_lookup_key', '_player_field',
                 '_plain_player_row'):
        _function(name, ns)
    remember_player = _method('_remember_player_vehicle', ns)
    remember_sampled = _method('_remember_sampled_player_vehicle', ns)
    remember_roster = _method('_remember_roster_vehicles', ns)
    return ns, remember_player, remember_sampled, remember_roster


def _sample_collector(remember_player, remember_sampled):
    class Collector(object):
        pass
    collector = Collector()
    collector._damage = DamageTracker()
    collector._remember_player_vehicle = lambda player: remember_player(
        collector, player)
    collector._remember_sampled_player_vehicle = lambda player: (
        remember_sampled(collector, player))
    return collector


class _Calibration(object):
    def observe(self, samples, now):
        return {'status': 'unknown', 'sampleCount': len(samples)}

    def map_to_world(self, x, y):
        return None


def _players_info(rows):
    by_vehicle = {
        (type(row['shipId']), row['shipId']): {
            'id': row['playerId'], 'teamId': row['teamId']}
        for row in rows
    }

    class Battle(object):
        def __init__(self):
            self.calls = {'info': 0, 'fallback': 0, 'vehicle': 0}

        def getPlayersInfo(self):
            self.calls['info'] += 1
            return rows

        def getPlayers(self):
            self.calls['fallback'] += 1
            return rows

        def getPlayerByVehicleId(self, vehicle_id):
            self.calls['vehicle'] += 1
            return by_vehicle.get((type(vehicle_id), vehicle_id))

        def getAllShips(self):
            return ships

        def getPlayerShipInfo(self, player_id):
            return None

        def getPlayerInfo(self, player_id):
            return None

    ships = []
    return Battle()


def test_strict_player_keys_keep_zero_types_and_reject_invalid_ids():
    ns, _, _, _ = _roster_reader(object())
    key = ns['_strict_player_lookup_key']
    assert key(0) == (int, 0)
    assert key(0.0) == (float, 0.0)
    assert key('0') == (str, '0')
    assert key(False) is None
    assert key(None) is None
    assert key(float('nan')) is None
    assert key(float('inf')) is None


def _ship_builder(battle):
    ns = {
        '_UNSET': object(), '_strict_player_lookup_key': None,
        '_get': lambda obj, key, default=None: (
            obj.get(key, default) if isinstance(obj, dict)
            else getattr(obj, key, default)),
        '_vec': lambda raw: list(raw) if isinstance(raw, (tuple, list))
        and len(raw) == 3 else None,
        '_try': _attempt, '_is_mapping': _mapping,
        '_map_norm_xy': lambda *args: None,
        '_visibility_raw': lambda value: value,
        '_visibility_observation': lambda *args: {}, 'long': int,
        'apply_ui_health': lambda *args, **kwargs: None,
        'battle': battle,
    }
    key_ns = {'_STRING_TYPES': (str,), '_INT_TYPES': (int,)}
    strict_key = _function('_strict_player_lookup_key', key_ns)
    ns['_strict_player_lookup_key'] = strict_key
    start = SOURCE.index('    def _position_from_obj(')
    end = SOURCE.index('\ndef _is_mapping(', start)
    exec(textwrap.dedent(SOURCE[start:end]), ns)

    class Harness(object):
        _position_from_obj = ns['_position_from_obj']
        _get_ship_position = ns['_get_ship_position']
        _build_ships = ns['_build_ships']
        _collect_map_positions = lambda self, entities=None: (
            setattr(self, '_mapVisibility', {}) or
            setattr(self, '_mapVisibilityDiagnostics', {}) or {})
        _relation = lambda self, team: 1 if team in (0, 1) else 2
        _map_to_world = lambda self, *args: None

    collector = Harness()
    collector._diagnosticsEnabled = False
    collector._diagnosticsSampleDue = False
    collector._positionFallbacksEnabled = False
    collector._positionDiagnostics = {}
    collector._damage = DamageTracker()
    collector._mapCalibration = _Calibration()
    return collector


def test_24_ships_share_one_player_list_and_preserve_ship_output():
    rows = [{'shipId': 5000 + index, 'playerId': 7000 + index,
             'teamId': 0 if index == 0 else (index % 2) + 1}
            for index in range(24)]
    battle = _players_info(rows)
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    sample = remember_roster(collector, [])
    assert battle.calls == {'info': 1, 'fallback': 0, 'vehicle': 0}
    assert sample['status'] == 'complete'
    assert len(sample['index']) == 24

    ships = [Obj(_Ship__id=row['shipId'], uiId=index,
                 teamId=row['teamId'], getPosition=lambda: (1, 2, 3),
                 isAlive=lambda: True, health=100, maxHealth=100)
             for index, row in enumerate(rows)]
    battle.getAllShips = lambda: ships
    builder = _ship_builder(battle)
    # Legacy direct-call behavior is the equivalence baseline.
    legacy, _ = builder._build_ships(1.0)
    assert battle.calls['vehicle'] == 24
    battle.calls['vehicle'] = 0
    shared, diag = builder._build_ships(1.0, players_sample=sample)
    assert battle.calls['vehicle'] == 0
    assert diag['playerReads'] == {
        'source': 'sampleLocalPlayersIndex', 'sampleStatus': 'complete',
        'indexHits': 24, 'vehicleLookups': 0}
    assert shared == legacy
    assert [ship['playerId'] for ship in shared] == [
        row['playerId'] for row in rows]
    assert shared[0]['teamId'] == 0
    assert collector._damage.lookup(5000) == (7000, 0)


def test_24_roster_rows_read_three_common_fields_once_instead_of_twice():
    class CountingRow(dict):
        def __init__(self, *args, **kwargs):
            dict.__init__(self, *args, **kwargs)
            self.reads = {}

        def __getitem__(self, name):
            self.reads[name] = self.reads.get(name, 0) + 1
            return dict.__getitem__(self, name)

    def rows():
        return [CountingRow(shipId=5000 + index, playerId=7000 + index,
                            teamId=0 if index == 0 else (index % 2) + 1)
                for index in range(24)]

    legacy_rows = rows()
    legacy_battle = _players_info(legacy_rows)
    for row in legacy_rows:
        row.reads.clear()
    ns, remember_player, remember_sampled, _ = _roster_reader(legacy_battle)
    legacy_collector = _sample_collector(remember_player, remember_sampled)
    for row in legacy_rows:
        remember_player(legacy_collector, row)
        ns['_plain_player_row'](row)
    assert sum(sum(row.reads.values()) for row in legacy_rows) == 144
    assert all(row.reads == {'playerId': 2, 'shipId': 2, 'teamId': 2}
               for row in legacy_rows)

    sampled_rows = rows()
    battle = _players_info(sampled_rows)
    for row in sampled_rows:
        row.reads.clear()
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    sample = remember_roster(collector, [])
    assert sample['status'] == 'complete'
    assert len(sample['index']) == 24
    assert sum(sum(row.reads.values()) for row in sampled_rows) == 72
    assert all(row.reads == {'playerId': 1, 'shipId': 1, 'teamId': 1}
               for row in sampled_rows)


def test_start_roster_cache_does_not_read_strict_index_fields():
    class CountingRow(dict):
        def __init__(self, *args, **kwargs):
            dict.__init__(self, *args, **kwargs)
            self.reads = {}

        def __getitem__(self, name):
            self.reads[name] = self.reads.get(name, 0) + 1
            return dict.__getitem__(self, name)

    row = CountingRow(shipId=77, playerId=42, teamId=0)
    battle = _players_info([row])
    row.reads.clear()
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    sample = remember_roster(collector)
    assert sample['status'] == 'complete' and sample['index'] == {}
    assert row.reads == {'playerId': 1, 'shipId': 1, 'teamId': 1}
    assert collector._damage.lookup(77) == (42, 0)


def test_mapping_item_and_attribute_conflicts_keep_consumer_specific_rules():
    class Hybrid(object):
        def __init__(self):
            self.item_reads = {}
            self.attr_reads = {}
            self.items = {'playerId': None, 'id': 7, 'shipId': None,
                          'vehicleId': 11, 'teamId': None}

        def keys(self):
            return self.items.keys()

        def __getitem__(self, name):
            self.item_reads[name] = self.item_reads.get(name, 0) + 1
            if name not in self.items:
                raise KeyError(name)
            return self.items[name]

        def _attribute(self, name, value):
            self.attr_reads[name] = self.attr_reads.get(name, 0) + 1
            return value

        @property
        def playerId(self):
            return self._attribute('playerId', 42)

        @property
        def id(self):
            return self._attribute('id', 99)

        @property
        def shipId(self):
            return self._attribute('shipId', 80)

        @property
        def vehicleId(self):
            return self._attribute('vehicleId', 12)

        @property
        def teamId(self):
            return self._attribute('teamId', 0)

    row = Hybrid()
    battle = _players_info([])
    ns, remember_player, remember_sampled, _ = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    index_row = remember_sampled(collector, row)

    # Damage semantics skip item None and continue through aliases; strict
    # semantics try the matching attribute when a mapping item is None.
    assert index_row == ((int, 80), {'playerId': 42, 'teamId': 0})
    assert collector._damage.lookup(11) == (7, None)
    assert row.item_reads == {
        'playerId': 1, 'id': 1, 'shipId': 1, 'vehicleId': 1, 'teamId': 1}
    assert row.attr_reads == {'playerId': 1, 'shipId': 1, 'teamId': 1}


def test_raising_player_accessors_are_memoized_without_losing_alias_fallback():
    class RaisingMapping(object):
        def __init__(self):
            self.item_reads = {}
            self.attr_reads = {}

        def keys(self):
            return ()

        def __getitem__(self, name):
            self.item_reads[name] = self.item_reads.get(name, 0) + 1
            raise KeyError(name)

        def _read(self, name, value):
            self.attr_reads[name] = self.attr_reads.get(name, 0) + 1
            if isinstance(value, Exception):
                raise value
            return value

        @property
        def playerId(self):
            return self._read('playerId', 42)

        @property
        def shipId(self):
            return self._read('shipId', RuntimeError('missing'))

        @property
        def vehicleId(self):
            return self._read('vehicleId', AttributeError('missing'))

        @property
        def vehicleID(self):
            return self._read('vehicleID', 77)

        @property
        def teamId(self):
            return self._read('teamId', 0)

    row = RaisingMapping()
    battle = _players_info([])
    ns, remember_player, remember_sampled, _ = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    index_row = remember_sampled(collector, row)
    assert index_row == ((int, 77), {'playerId': 42, 'teamId': 0})
    assert collector._damage.lookup(77) == (42, 0)
    assert row.item_reads == {
        'playerId': 1, 'shipId': 1, 'vehicleId': 1, 'vehicleID': 1,
        'teamId': 1}
    assert row.attr_reads == {
        'playerId': 1, 'shipId': 1, 'vehicleId': 1, 'vehicleID': 1,
        'teamId': 1}


def test_non_scalar_player_id_is_not_copied_or_stringified_into_index():
    class UnsafeId(object):
        def __float__(self):
            raise ValueError('not numeric')

        def __repr__(self):
            raise AssertionError('raw ID must not be stringified')

    battle = _players_info([{'shipId': 77, 'playerId': UnsafeId(),
                             'teamId': 1}])
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    sample = remember_roster(collector, [])
    assert sample['index'] == {}
    assert sample['seenKeys'] == {(int, 77): True}


def test_ship_team_id_is_read_once_for_hit_miss_and_diagnostic_fallback():
    class TeamShip(object):
        def __init__(self):
            self.team_reads = 0
            self._Ship__id = 77
            self.uiId = 1

        @property
        def teamId(self):
            self.team_reads += 1
            return 0

        def getPosition(self):
            return (1, 2, 3)

        def isAlive(self):
            return True

    sample = {'status': 'complete', 'index': {
        (int, 77): {'playerId': 42, 'teamId': 0}}}
    for mode in ('hit', 'miss', 'diagnosticFallback'):
        battle = _players_info([])
        ship = TeamShip()
        battle.getAllShips = lambda ship=ship: [ship]
        lookups = []

        def lookup(vehicle_id):
            lookups.append(vehicle_id)
            return {'id': 42, 'teamId': 0}

        battle.getPlayerByVehicleId = lookup
        builder = _ship_builder(battle)
        if mode == 'miss':
            players_sample = {'status': 'partial', 'index': {}}
        else:
            players_sample = sample
        if mode == 'diagnosticFallback':
            builder._positionFallbacksEnabled = True
            builder._diagnosticsEnabled = True
            builder._diagnosticsSampleDue = True

        output, _ = builder._build_ships(
            1.0, players_sample=players_sample)
        assert ship.team_reads == 1
        assert output[0]['teamId'] == 0
        assert output[0]['playerId'] == 42
        assert lookups == ([] if mode == 'hit' else [77])


def test_partial_duplicate_and_invalid_rows_fall_back_without_false_joins():
    partial_rows = [
        {'shipId': 10, 'playerId': 0, 'teamId': 0},
        {'shipId': 20, 'playerId': 200, 'teamId': 1},
        {'shipId': 20, 'playerId': 201, 'teamId': 1},
        {'shipId': True, 'playerId': 300, 'teamId': 1},
        {'shipId': 30, 'playerId': None, 'teamId': 1},
        {'shipId': 30, 'playerId': 303, 'teamId': 1},
        {'shipId': '50', 'playerId': 500, 'teamId': 1},
        {'shipId': 60, 'playerId': None, 'teamId': 1},
    ]

    class Battle(object):
        def __init__(self):
            self.calls = {'info': 0, 'fallback': 0, 'vehicle': []}

        def getPlayersInfo(self):
            self.calls['info'] += 1
            def items():
                for row in partial_rows:
                    yield row
                raise RuntimeError('partial enumeration')
            return items()

        def getPlayers(self):
            self.calls['fallback'] += 1
            return None

        def getAllShips(self):
            return ships

        def getPlayerByVehicleId(self, vehicle_id):
            self.calls['vehicle'].append(vehicle_id)
            if vehicle_id == 20:
                return {'id': 999, 'teamId': 2}
            if vehicle_id == True:
                return {'id': 301, 'teamId': 1}
            if vehicle_id == 30:
                raise RuntimeError('lookup exception')
            if vehicle_id == 50:
                return {'id': 505, 'teamId': 2}
            if vehicle_id == 60:
                return {'id': 606, 'teamId': 2}
            if vehicle_id == 40:
                return None
            return None

        def getPlayerShipInfo(self, player_id):
            return None

        def getPlayerInfo(self, player_id):
            return None

    ships = [Obj(_Ship__id=vehicle, uiId=index, teamId=None,
                 getPosition=lambda: (1, 2, 3), isAlive=lambda: True)
             for index, vehicle in enumerate((10, 20, True, 30, 40, 50, 60))]
    ships.append(Obj(_Ship__id=None, uiId=7, teamId=None,
                     getPosition=lambda: (1, 2, 3), isAlive=lambda: True))
    battle = Battle()
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(battle)
    collector = _sample_collector(remember_player, remember_sampled)
    sample = remember_roster(collector, [])
    assert sample['status'] == 'partial'
    assert sample['index'][(int, 10)] == {'playerId': 0, 'teamId': 0}
    assert (int, 20) not in sample['index']  # conflicting duplicate is blocked
    assert (bool, True) not in sample['index']
    assert (int, 30) not in sample['index']  # invalid row makes duplicate ambiguous

    builder = _ship_builder(battle)
    output, _ = builder._build_ships(1.0, players_sample=sample)
    assert battle.calls['vehicle'] == [20, True, 30, 40, 50, 60]
    assert output[0]['playerId'] == 0 and output[0]['teamId'] == 0
    assert output[1]['playerId'] == 999
    assert output[2]['playerId'] == 301
    assert 'playerId' not in output[3] and 'playerId' not in output[4]
    assert output[5]['playerId'] == 505  # string/int key mismatch falls back
    assert output[6]['playerId'] == 606  # row with invalid player ID falls back
    assert 'playerId' not in output[7]  # None vehicle ID stays unknown


def test_player_getter_fallback_empty_none_and_next_frame_are_distinct():
    calls = []

    class Battle(object):
        def __init__(self, info, fallback):
            self.info, self.fallback = info, fallback

        def getPlayersInfo(self):
            calls.append('info')
            if isinstance(self.info, Exception):
                raise self.info
            return self.info

        def getPlayers(self):
            calls.append('fallback')
            if isinstance(self.fallback, Exception):
                raise self.fallback
            return self.fallback

    empty_battle = Battle([], [{'shipId': 1, 'playerId': 2, 'teamId': 3}])
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(empty_battle)
    collector = _sample_collector(remember_player, remember_sampled)
    empty = remember_roster(collector, [])
    assert empty['status'] == 'complete' and empty['index'] == {}
    assert calls == ['info']  # successful empty list does not trigger fallback

    calls[:] = []
    fallback_row = {'shipId': 1, 'playerId': 2, 'teamId': 3}
    fallback_battle = Battle(RuntimeError('info failed'), [fallback_row])
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(fallback_battle)
    collector = _sample_collector(remember_player, remember_sampled)
    fallback = remember_roster(collector, [])
    assert fallback['index'][(int, 1)]['playerId'] == 2
    assert calls == ['info', 'fallback']

    calls[:] = []
    unavailable_battle = Battle(None, RuntimeError('fallback failed'))
    ns, remember_player, remember_sampled, remember_roster = _roster_reader(unavailable_battle)
    collector = _sample_collector(remember_player, remember_sampled)
    unavailable = remember_roster(collector, [])
    assert unavailable['status'] == 'unavailable'
    assert unavailable['index'] == {}
    assert calls == ['info', 'fallback']

    # A later frame builds a new empty context; previous player IDs are not kept.
    ships = [Obj(_Ship__id=1, uiId=1, teamId=1,
                 getPosition=lambda: (1, 2, 3), isAlive=lambda: True)]
    unavailable_battle.getAllShips = lambda: ships
    unavailable_battle.calls = []
    unavailable_battle.getPlayerByVehicleId = lambda vid: (
        unavailable_battle.calls.append(vid) or None)
    builder = _ship_builder(unavailable_battle)
    previous = {'status': 'complete', 'index': {
        (int, 1): {'playerId': 2, 'teamId': 3}}}
    current, _ = builder._build_ships(1.0, players_sample=unavailable)
    assert unavailable_battle.calls == [1]
    assert 'playerId' not in current[0]
    assert previous['index'][(int, 1)]['playerId'] == 2


def test_diagnostic_fallback_uses_original_player_object_on_due_sample():
    player = {'id': 42, 'teamId': 0, 'worldPosition': (4, 5, 6)}

    class Battle(object):
        def __init__(self):
            self.lookups = 0

        def getAllShips(self):
            return [Obj(_Ship__id=77, uiId=1, teamId=None,
                        getPosition=lambda: None, isAlive=lambda: True)]

        def getPlayerByVehicleId(self, vehicle_id):
            self.lookups += 1
            return player

        def getPlayerShipInfo(self, player_id):
            return None

        def getPlayerInfo(self, player_id):
            return None

    battle = Battle()
    builder = _ship_builder(battle)
    builder._positionFallbacksEnabled = True
    builder._diagnosticsEnabled = True
    builder._diagnosticsSampleDue = True
    sample = {'status': 'complete', 'index': {
        (int, 77): {'playerId': 42, 'teamId': 0}}}
    output, _ = builder._build_ships(1.0, players_sample=sample)
    assert battle.lookups == 1
    assert output[0]['position'] == [4, 5, 6]
    assert output[0]['playerId'] == 42
    assert output[0]['teamId'] == 0
    assert output[0]['positionReadPolicy']['fallbackStatus'] == 'available'
