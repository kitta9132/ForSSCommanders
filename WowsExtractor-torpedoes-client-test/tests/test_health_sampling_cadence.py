"""Offline checks for the 0.35 shared HP (average 2 Hz) / comparison (1 Hz) groups.

The core state loop stays at 5 Hz: positions, yaw, map rows, visibility and the
ids needed for joins keep their cadence. Only the HP getters and the heavier
avatar identity comparison are gated. Everything here uses fake clocks and fake
components; no game/API calls are made.
"""
import ast
import builtins
from pathlib import Path
import textwrap
from types import FunctionType, MethodType, SimpleNamespace as Obj

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
    encoding='utf8')
TREE = ast.parse(SOURCE.replace('except Exception, e:', 'except Exception as e:'))

import sys  # noqa: E402

sys.path.insert(0, str(ROOT / 'res_mods/PnFMods/WowsExtractor'))
from ui_health import (  # noqa: E402
    AvatarRows, apply_ui_health, index_avatar_health,
    index_avatar_health_sample, normalize_ui_health)
from damage_tracker import roster_ids_from_avatar  # noqa: E402
from torpedo_telemetry import _identity_reject  # noqa: E402


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


def get_default(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _main_top_functions(namespace):
    for name in ('_strict_player_lookup_key', '_observation_scalar',
                 '_observation_exception_name', '_observation_field',
                 '_map_norm_xy', '_point_xy', '_vec', '_component_pos', '_get',
                 '_visibility_type', '_visibility_raw',
                 '_visibility_observation'):
        top_function(name, namespace)


def main_namespace(cc):
    ns = {
        '_UNSET': object(), '_STRING_TYPES': (str,), '_INT_TYPES': (int,),
        'long': int, '_try': attempt, '_is_mapping': lambda value:
            isinstance(value, dict), 'CC': cc, 'AvatarRows': AvatarRows,
        'normalize_ui_health': normalize_ui_health,
        'index_avatar_health': index_avatar_health,
        'index_avatar_health_sample': index_avatar_health_sample,
        'apply_ui_health': apply_ui_health,
        'roster_ids_from_avatar': roster_ids_from_avatar,
        '_identity_reject': _identity_reject,
    }
    _main_top_functions(ns)
    ns['_is_mapping'] = lambda value: isinstance(value, dict)
    return ns


# ---------------------------------------------------------------------------
# counted fake components
# ---------------------------------------------------------------------------
class Comp(object):
    """Attribute-backed component that counts every field read."""

    def __init__(self, **values):
        object.__setattr__(self, '_values', values)
        object.__setattr__(self, 'reads', {})

    def _bump(self, name):
        reads = object.__getattribute__(self, 'reads')
        reads[name] = reads.get(name, 0) + 1

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        if name not in values:
            raise AttributeError(name)
        self._bump(name)
        return values[name]


class CountedEntity(dict):
    def __init__(self, **components):
        dict.__init__(self, components)
        self.reads = {}

    def __getitem__(self, key):
        self.reads[key] = self.reads.get(key, 0) + 1
        return dict.__getitem__(self, key)


class CountedShip(object):
    def __init__(self, vehicle_id, player_team=1, position=(10.0, 0.0, 20.0),
                 health=None, max_health=None, alive=True, yaw=0.25,
                 name='ship'):
        object.__setattr__(self, '_values', {
            'id': vehicle_id, 'teamId': player_team,
            'health': health, 'maxHealth': max_health, 'yaw': yaw,
            'name': name, 'shipType': 'submarine', 'alive': alive,
        })
        object.__setattr__(self, '_position', position)
        object.__setattr__(self, 'reads', {})

    def _bump(self, name):
        reads = object.__getattribute__(self, 'reads')
        reads[name] = reads.get(name, 0) + 1

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        if name not in values:
            raise AttributeError(name)
        self._bump(name)
        return values[name]

    def getPosition(self):
        self._bump('getPosition')
        return list(object.__getattribute__(self, '_position'))

    def isAlive(self):
        self._bump('isAlive')
        return object.__getattribute__(self, '_values')['alive']


class Player(object):
    def __init__(self, player_id, ship_id, team_id=1):
        self.playerId = player_id
        self.shipId = ship_id
        self.teamId = team_id


class SelfInfo(object):
    def __init__(self, player_id, team_id, game_data):
        self.id = player_id
        self.teamId = team_id
        self.shipGameData = game_data


class Hub(object):
    def __init__(self, entities):
        self.entities = entities

    def getEntityCollections(self, name):
        return self.entities if name == 'avatar' else []


class Battle(object):
    def __init__(self, ships, players, self_info, self_ship):
        self.ships = ships
        self.players = players
        self.self_info = self_info
        self.self_ship = self_ship

    def getAllShips(self):
        return self.ships

    def getPlayersInfo(self):
        return self.players

    def getPlayers(self):
        return None

    def getPlayerByVehicleId(self, vehicle_id):
        for player in self.players:
            if player.shipId == vehicle_id:
                return player
        return None

    def getSelfPlayerInfo(self):
        return self.self_info

    def getSelfPlayerShip(self):
        return self.self_ship

    def getObserverShip(self):
        return None

    def isObserverMode(self):
        return False


class Damage(object):
    def remember_player_values(self, *args):
        return None

    def remember(self, *args):
        return None

    def clear(self):
        return None

    def snapshot(self):
        return {}


class MapCalibration(object):
    def observe(self, samples, now):
        return {'status': 'unknown'}

    def update(self, samples, now):
        pass

    def live_model_status(self):
        return {'status': 'unknown', 'coefficients': None}

    def snapshot(self):
        return {'status': 'unknown'}

    def map_to_world(self, *args):
        return None

    def world_to_map(self, *args):
        return None

    def clear(self):
        return None


class Torpedoes(object):
    def torpedoes(self, team, self_ship_id=None):
        return [], {'available': True, 'status': 'available'}

    def armament(self, ship=None):
        return {}

    def systems(self, ship=None):
        return {}


class Motion(object):
    def update(self, *args, **kwargs):
        return None

    def clear(self):
        return None


CC_KEYS = dict(avatar='avatar', vehicle='vehicle', health='health',
               mapPosition='mapPosition', visibility='visibility')


def avatar_entity(player_id, *, avatar_id=1000, vehicle_id=100,
                  health=(800, 1000, True), map_position=(0.25, 0.75),
                  yaw=0.5, visible=True):
    components = {
        'avatar': Comp(playerId=player_id, id=avatar_id, teamId=1,
                       shipId=vehicle_id),
        'vehicle': Comp(id=vehicle_id),
        'health': Comp(value=health[0], max=health[1], isAlive=health[2]),
    }
    if map_position is not False:
        components['mapPosition'] = Comp(position=map_position, yaw=yaw)
    if visible is not None:
        components['visibility'] = Comp(mapVisible=visible)
    return CountedEntity(**components)


METHODS = (
    '_capture_avatar_snapshot', '_remember_sampled_player_vehicle',
    '_remember_roster_vehicles', '_collect_avatar_health',
    '_collect_map_positions', '_build_avatar_observations', '_build_ships',
    '_build_self', '_build_state', '_self_team', '_relation',
    '_get_ship_position', '_position_from_obj', '_map_to_world',
    '_ship_world_position_threshold',
)


def make_collector(entities, ships, players, self_info, self_ship):
    ns = main_namespace(Obj(**CC_KEYS))
    ns.update({
        'dataHub': Hub(entities), 'battle': Battle(
            ships, players, self_info, self_ship),
        'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0', 'INVALID': -1,
        'shared_diagnostic_snapshot': lambda *args: {},
        'ui_torpedo_probe_without_state': lambda *args: {
            'status': 'notSampled', 'rows': []},
        'attach_ui_state': lambda *args: None,
        'ui_torpedo_depth_probe': lambda *args: {'status': 'notSampled',
                                                  'rows': []},
        'attach_ui_depth_state': lambda *args: None,
        'ui_torpedo_state_probe': lambda *args: {'status': 'notSampled',
                                                  'rows': []},
        'attach_ui_torpedo_state': lambda *args: None,
        'safe_weapon_hub_probe': lambda *args: {},
        'safe_weapon_context_probe': lambda *args: {},
        'safe_game_clock_probe': lambda *args: {},
        'safe_gun_reload_probe': lambda *args: {},
        'safe_submarine_probe': lambda *args: {},
        'safe_identity_candidates': lambda *args: {'status': 'notSampled'},
        'sampling_wire_payload': lambda rows, status: (rows, status),
    })
    c = Obj()
    for name in METHODS:
        setattr(c, name, MethodType(method(name, ns), c))
    c._active = True
    c._collectionEnabled = True
    c._diagnosticsEnabled = False
    c._diagnosticsSampleDue = False
    c._torpedoDepthSamplingEnabled = False
    c._torpedoDepthSamplingDue = False
    c._torpedoStateSamplingEnabled = False
    c._torpedoStateSamplingDue = False
    c._torpedoStateProvider = 'unknown'
    c._performanceProfiler = None
    c._profilerEnabled = False
    c._writer = None
    c._battleId = 'battle-1'
    c._selfTeam = ns['_UNSET']
    c._positionFallbacksEnabled = False
    c._torpedoSamplingGroups = None
    c._torpedoMotion = Motion()
    c._mapCalibration = MapCalibration()
    c._torpedoes = Torpedoes()
    c._damage = Damage()
    c._healthSamplingDue = True
    c._comparisonSamplingDue = True
    c._healthSamplingInterval = 0.5
    c._comparisonSamplingInterval = 1.0
    c._selfSystemsSamplingEnabled = True
    c._selfSystemsSamplingDue = True
    c._torpedoArmamentSamplingEnabled = True
    c._torpedoArmamentSamplingDue = True
    c._mapCalibrationSnapshotInterval = 1.0
    c._mapCalibrationSnapshotDue = False
    c._shipWorldPositionSamplingEnabled = True
    c._shipWorldPositionSamplingDue = True
    c._shipWorldPositionSamplingInterval = 1.0
    c._shipWorldPositionSamplingNextDue = None
    c._shipWorldPositionSamplingLastNow = None
    c._shipWorldPositionFarDivisor = 5.0
    c._shipWorldPositionSeenIds = {}
    c._shipWorldPositionSeenOrder = []
    c._shipWorldPositionSeenIdsLimit = 512
    return c, ns


def default_fixture(*, ship_health=(None, None), health=(500, 1000, True),
                    self_health=(700, 1200, True)):
    ship = CountedShip(101, health=ship_health[0], max_health=ship_health[1])
    second = CountedShip(102, player_team=1)
    self_ship = CountedShip(202, player_team=1, health=None)
    players = [Player(1, 101), Player(2, 102), Player(99, 202)]
    entities = [
        avatar_entity(1, avatar_id=11, vehicle_id=101, health=health),
        avatar_entity(99, avatar_id=99, vehicle_id=202, health=self_health),
        avatar_entity(2, avatar_id=12, vehicle_id=102,
                      health=(300, 900, True)),
    ]
    info = SelfInfo(99, 1, Comp(health=700, maxHealth=1200, yaw=0.1,
                                speed=3.0, isVisible=True))
    return [ship, second], players, info, self_ship, entities


# ---------------------------------------------------------------------------
# scheduler
# ---------------------------------------------------------------------------
def scheduler_collector():
    ns = {'_get': get_default}
    for name in ('_deadline_due', '_health_sampling_due',
                 '_comparison_sampling_due'):
        method(name, ns)
    c = Obj(_healthSamplingInterval=0.5, _healthSamplingNextDue=None,
            _healthSamplingLastNow=None,
            _comparisonSamplingInterval=1.0,
            _comparisonSamplingNextDue=None,
            _comparisonSamplingLastNow=None)
    c._deadline_due = MethodType(ns['_deadline_due'], c)
    c._health_sampling_due = MethodType(ns['_health_sampling_due'], c)
    c._comparison_sampling_due = MethodType(ns['_comparison_sampling_due'], c)
    return c


def test_health_scheduler_is_two_hz_on_point_two_ticks_and_comparison_one_hz():
    c = scheduler_collector()
    ticks = [0.0, .2, .4, .6, .8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0]
    health = [t for t in ticks if c._health_sampling_due(t)]
    comparison = [t for t in ticks
                  if c._comparison_sampling_due(t)]
    # Anchored 0.5 s deadlines quantized onto 0.2 s ticks: 0.4/0.6 s alternate.
    assert health == [0.0, .6, 1.0, 1.6, 2.0]
    assert comparison == [0.0, 1.0, 2.0]
    assert c._healthSamplingNextDue == 2.5
    assert c._comparisonSamplingNextDue == 3.0


def test_scheduler_first_due_rollback_frozen_and_no_catchup():
    c = scheduler_collector()
    assert c._health_sampling_due(0.0) is True
    assert c._healthSamplingNextDue == 0.5
    assert c._health_sampling_due(0.0) is False  # frozen clock: no repeats
    assert c._health_sampling_due(0.2) is False
    assert c._health_sampling_due(0.6) is True

    # Long stall: one sample now, phase restarts; missed periods are not replayed.
    assert c._health_sampling_due(5.0) is True
    assert c._healthSamplingNextDue == 5.5
    assert c._health_sampling_due(5.4) is False
    assert c._health_sampling_due(5.6) is True

    # Backwards clock resets immediately (first sample after rollback).
    assert c._health_sampling_due(1.0) is True
    assert c._healthSamplingNextDue == 1.5
    assert c._health_sampling_due(1.1) is False

    # Non-finite clock never samples and clears the deadline.
    assert c._health_sampling_due(float('nan')) is False
    assert c._healthSamplingNextDue is None
    assert c._health_sampling_due(2.0) is True
    assert c._health_sampling_due(float('inf')) is False
    assert c._healthSamplingNextDue is None


def test_comparison_scheduler_is_independent_of_health_group():
    c = scheduler_collector()
    assert c._health_sampling_due(0.0) is True
    assert c._comparison_sampling_due(0.0) is True
    assert c._health_sampling_due(0.4) is False
    assert c._comparison_sampling_due(0.4) is False
    assert c._health_sampling_due(0.6) is True
    assert c._comparison_sampling_due(0.6) is False
    assert c._comparison_sampling_due(1.0) is True
    assert c._comparisonSamplingNextDue == 2.0


def lifecycle_collector():
    ns = {
        '_now': lambda: 5.0, 'META_RETRY_SECONDS': 12.0,
        'META_RETRY_INTERVAL': 1.0, 'SCHEMA_VERSION': 1,
        'WIRE_API_VERSION': '1.0', 'logInfo': lambda *args: None,
        '_get': get_default, '_try': attempt,
        '_empty_avatar_observations': lambda *args: {'rows': []},
        'battle': Obj(getSelfPlayerInfo=lambda: None),
        'callbacks': Obj(perTick=lambda fn: 1),
    }
    for name in ('_on_battle_start', '_on_battle_quit', '_deadline_due',
                 '_health_sampling_due', '_comparison_sampling_due'):
        method(name, ns)
    c = Obj()
    for name in ('_on_battle_start', '_on_battle_quit', '_deadline_due',
                 '_health_sampling_due', '_comparison_sampling_due'):
        setattr(c, name, MethodType(ns[name], c))
    c._active = False
    c._battleStarted = False
    c._battleShown = False
    c._collectionEnabled = False
    c._stateFile = c._metaFile = None
    c._battleId = None
    c._initialTorpedoParameters = None
    c._torpedoSamplingGroups = None
    c._load_config = lambda: None
    c._resolve_paths = lambda: None
    c._mapCalibration = MapCalibration()
    c._torpedoMotion = Motion()
    c._damage = Obj(clear=lambda: None, snapshot=lambda: {})
    c._battleIdentity = Obj(start=lambda *args: 'next-battle')
    c._find_arena_id = lambda: None
    c._remember_player_vehicle = lambda player: None
    c._remember_roster_vehicles = lambda: None
    c._stop_tick = lambda: None
    c._start_collection = lambda: None
    c._write_state = lambda snap: None
    c._healthSamplingInterval = 0.5
    c._healthSamplingNextDue = 99.0
    c._healthSamplingLastNow = 90.0
    c._healthSamplingDue = True
    c._comparisonSamplingInterval = 1.0
    c._comparisonSamplingNextDue = 99.0
    c._comparisonSamplingLastNow = 90.0
    c._comparisonSamplingDue = True
    return c


def test_battle_start_and_quit_reset_both_group_schedules():
    c = lifecycle_collector()
    c._on_battle_start()
    assert c._healthSamplingNextDue is None
    assert c._healthSamplingLastNow is None
    assert c._healthSamplingDue is False
    assert c._comparisonSamplingNextDue is None
    assert c._comparisonSamplingLastNow is None
    assert c._comparisonSamplingDue is False
    # First frame of the next battle is due immediately.
    assert c._health_sampling_due(0.0) is True
    assert c._health_sampling_due(0.1) is False

    c._healthSamplingNextDue = 99.0
    c._healthSamplingLastNow = 90.0
    c._healthSamplingDue = True
    c._comparisonSamplingNextDue = 99.0
    c._comparisonSamplingLastNow = 90.0
    c._comparisonSamplingDue = True
    c._on_battle_quit()
    assert c._healthSamplingNextDue is None
    assert c._healthSamplingLastNow is None
    assert c._healthSamplingDue is False
    assert c._comparisonSamplingNextDue is None
    assert c._comparisonSamplingLastNow is None
    assert c._comparisonSamplingDue is False


# ---------------------------------------------------------------------------
# shared HP group / 5 Hz structural fields
# ---------------------------------------------------------------------------
def test_comparison_only_tick_does_not_report_zero_observed_health_rows():
    ships, players, info, self_ship, entities = default_fixture()
    c, _ns = make_collector(entities, ships, players, info, self_ship)
    c._healthSamplingDue = False
    c._comparisonSamplingDue = True
    state = c._build_state(10.0)
    assert state['avatarObservations']['comparisonSampling']['status'] == 'sampled'
    assert state['avatarObservations']['healthSampling']['status'] == 'notSampled'
    assert 'healthRawAvailableCount' not in state['avatarObservations']['coverage']
    assert 'uiHealth' not in state['diag']


def test_health_due_shares_avatar_ship_and_self_getters_once():
    ships, players, info, self_ship, entities = default_fixture()
    c, _ns = make_collector(entities, ships, players, info, self_ship)

    state = c._build_state(10.0)

    by_vehicle = {row['vehicleId']: row for row in state['ships']}
    assert by_vehicle[101]['health'] == 500
    assert by_vehicle[101]['maxHealth'] == 1000
    assert by_vehicle[101]['alive'] is True
    assert state['self']['health'] == 700
    assert state['self']['maxHealth'] == 1200
    assert state['healthSampling'] == {
        'status': 'sampled', 'sampleTs': 10.0, 'intervalSeconds': 0.5}
    observations = state['avatarObservations']
    assert observations['healthSampling'] is state['healthSampling']
    assert observations['comparisonSampling']['status'] == 'sampled'
    assert observations['comparisonSampling']['sampleTs'] == 10.0

    # One avatar health read feeds ships + self + observations in this tick.
    for entity in entities:
        assert entity.reads.get('health') == 1
        # Positions/ids remain core-rate reads on the same tick.
        assert entity.reads.get('avatar') == 1
        assert entity.reads.get('vehicle') == 1
        assert entity.reads.get('mapPosition') == 1
    assert ships[0].reads.get('health') == 1
    assert ships[0].reads.get('maxHealth') == 1
    assert ships[0].reads.get('isAlive') == 1
    assert ships[0].reads.get('getPosition') == 1
    assert ships[0].reads.get('yaw') == 1
    assert info.shipGameData.reads.get('health') == 1
    assert info.shipGameData.reads.get('maxHealth') == 1
    # self health came from shipGameData, so the ship HP getter is not repeated.
    assert self_ship.reads.get('health', 0) == 0


def test_non_due_health_reads_no_hp_getters_but_keeps_core_fields():
    ships, players, info, self_ship, entities = default_fixture()
    c, _ns = make_collector(entities, ships, players, info, self_ship)
    c._healthSamplingDue = False
    c._comparisonSamplingDue = False

    state = c._build_state(10.2)

    for row in state['ships']:
        assert 'health' not in row
        assert 'maxHealth' not in row
        assert 'alive' not in row
        # Structure data is still collected at the core rate.
        assert row['position'] is not None
        assert row['yaw'] == 0.25
        assert row['positionReadStatus']['attempted'] is True
    assert 'health' not in state['self']
    assert 'maxHealth' not in state['self']
    assert state['self']['yaw'] == 0.1
    assert state['healthSampling'] == {
        'status': 'notSampled', 'sampleTs': None, 'intervalSeconds': 0.5}
    assert state['diag']['healthSamplingStatus'] == 'notSampled'

    for entity in entities:
        assert entity.reads.get('health', 0) == 0
        assert entity.reads.get('avatar') == 1
        assert entity.reads.get('mapPosition') == 1
    for ship in ships:
        assert ship.reads.get('health', 0) == 0
        assert ship.reads.get('maxHealth', 0) == 0
        assert ship.reads.get('isAlive', 0) == 0
        assert ship.reads.get('getPosition') == 1
        assert ship.reads.get('yaw') == 1
    assert info.shipGameData.reads.get('health', 0) == 0
    assert info.shipGameData.reads.get('maxHealth', 0) == 0

    rows = state['avatarObservations']['rows']
    assert all(row['health'] == {
        'status': 'notSampled', 'source': 'dataHub.avatar.health',
        'sampleTs': None} for row in rows)
    # Compact off-due metadata only; no repeated fieldStatus/raw payload.
    assert set(rows[0]['health']) == {'status', 'source', 'sampleTs'}
    assert all(row['mapPosition']['status'] == 'available' for row in rows)
    assert all(row['playerId'] is not None for row in rows)
    assert all('avatarId' in row['identifierCandidates'] for row in rows)
    assert all(row['apiPresence'] == {'status': 'notSampled'} for row in rows)


def test_avatar_positions_and_visibility_stay_at_core_cadence():
    entities = [avatar_entity(1), avatar_entity(2, map_position=(0.5, 0.25))]
    ns = main_namespace(Obj(**CC_KEYS))
    collect = method('_collect_map_positions', ns)
    collector = Obj(_diagnosticsEnabled=True, _diagnosticsSampleDue=True,
                    _mapVisibility={}, _mapVisibilityDiagnostics={})
    holder = AvatarRows(entities)

    first = collect(collector, holder)
    second = collect(collector, holder)

    assert first == second
    assert first[2][0] == 0.5 and first[2][1] == 0.25
    assert first[1][2] == 0.5  # map yaw is retained at the core rate
    for entity in entities:
        assert entity.reads.get('mapPosition') == 2
        assert entity.reads.get('visibility') == 2
        assert entity.reads.get('health', 0) == 0
    assert collector._mapVisibility[1]['mapVisible'] is True
    assert collector._mapVisibility[2]['mapVisible'] is True


def test_comparison_gate_keeps_map_rows_but_marks_presence_not_sampled():
    ships, players, info, self_ship, entities = default_fixture()
    c, _ns = make_collector(entities, ships, players, info, self_ship)
    c._healthSamplingDue = False
    c._comparisonSamplingDue = False

    for index in range(5):
        state = c._build_state(20.0 + index * 0.2)
        rows = state['avatarObservations']['rows']
        assert len(rows) == len(entities)
        assert all(row['mapPosition']['status'] == 'available' for row in rows)
        assert all(row['apiPresence'] == {'status': 'notSampled'}
                   for row in rows)
        assert all(row['playerIdStatus'] == 'available' for row in rows)
        coverage = state['avatarObservations']['coverage']
        assert coverage['status'] == 'notSampled'
        assert coverage['sampleTs'] is None
        assert 'apiMatchedCount' not in coverage
        assert 'distinctPlayerIdCount' not in coverage
        consistency = state['avatarObservations']['candidateConsistency']
        assert consistency['status'] == 'notSampled'
        assert 'candidateExactValueMatchCount' not in consistency
    # Map rows were rebuilt on every core tick, not once per comparison.
    for entity in entities:
        assert entity.reads.get('mapPosition') == 5
        assert entity.reads.get('health', 0) == 0

    c._comparisonSamplingDue = True
    sampled = c._build_state(21.0)['avatarObservations']
    assert sampled['comparisonSampling']['status'] == 'sampled'
    # The self avatar's vehicle is exposed as state.self, not state.ships, so
    # two of the three captured avatars join the ship list. avatar.id stays a
    # separate unverified candidate namespace, so it matches no playerId here.
    assert sampled['coverage']['apiMatchedCount'] == 2
    assert sampled['candidateConsistency']['candidateAvailableCount'] == 3
    assert sampled['candidateConsistency'][
        'candidateExactValueMatchCount'] == 0


# ---------------------------------------------------------------------------
# partial capture, sentinels, reuse
# ---------------------------------------------------------------------------
def _partial_collector(entities, ships, players, info, self_ship):
    c, ns = make_collector(entities, ships, players, info, self_ship)
    holder = AvatarRows(entities, complete=False)
    snapshot = {'entities': holder, 'status': 'partial',
                'count': len(holder), 'limit': 256, 'reason': 'iterationError'}
    c._capture_avatar_snapshot = lambda: snapshot
    return c, holder


def test_partial_capture_reads_raw_health_only_when_due_and_never_indexes():
    ships, players, info, self_ship, entities = default_fixture()
    c, holder = _partial_collector(entities, ships, players, info, self_ship)
    state = c._build_state(30.0)

    # A partial health index cannot assert alive/dead or fill ship HP.
    assert all('health' not in row for row in state['ships'])
    rows = state['avatarObservations']['rows']
    assert all(row['health']['status'] == 'available' for row in rows)
    assert all(entity.reads.get('health') == 1 for entity in entities)
    assert state['healthSampling']['status'] == 'sampled'

    fresh_entities = default_fixture()[4]
    ships2, players2, info2, self_ship2, _ = default_fixture()
    c2, holder2 = _partial_collector(
        fresh_entities, ships2, players2, info2, self_ship2)
    c2._healthSamplingDue = False
    c2._comparisonSamplingDue = False
    state2 = c2._build_state(30.2)
    assert all(entity.reads.get('health', 0) == 0 for entity in fresh_entities)
    assert all(row['health']['status'] == 'notSampled'
               for row in state2['avatarObservations']['rows'])
    # The partial capture is re-read next frame; no object/row cache is kept.
    assert not hasattr(c2, '_avatarObservations')


def test_zero_health_alive_sentinel_and_death_are_same_sample():
    alive_ship = CountedShip(101)
    dead_ship = CountedShip(102, alive=True)  # stale API alive; UI says dead
    players = [Player(1, 101), Player(2, 102)]
    entities = [
        avatar_entity(1, vehicle_id=101, health=(0, 900, True)),
        avatar_entity(2, vehicle_id=102, health=(0, 900, False)),
    ]
    info = SelfInfo(1, 1, Comp(health=1, maxHealth=900, yaw=0.0, speed=0.0,
                               isVisible=True))
    c, _ns = make_collector(entities, [alive_ship, dead_ship], players,
                            info, CountedShip(202))
    state = c._build_state(40.0)
    by_vehicle = {row['vehicleId']: row for row in state['ships']}
    # value==0/isAlive=True is the Unbound "not ticked yet" full-bar sentinel.
    assert by_vehicle[101]['health'] == 900
    assert by_vehicle[101]['alive'] is True
    assert by_vehicle[102]['health'] == 0
    assert by_vehicle[102]['alive'] is False
    rows = {row['playerId']: row for row in state['avatarObservations']['rows']}
    assert rows[1]['health']['normalized']['untickedFull'] is True
    assert rows[2]['health']['normalized']['alive'] is False


def test_avatar_id_reuse_and_repeated_frames_do_not_reuse_previous_hp():
    ship = CountedShip(101)
    players = [Player(1, 101)]
    first_entity = avatar_entity(1, health=(1000, 1000, True))
    info = SelfInfo(1, 1, Comp(health=1000, maxHealth=1000, yaw=0.0,
                               speed=0.0, isVisible=True))
    c, _ns = make_collector([first_entity], [ship], players, info,
                            CountedShip(202))
    assert {r['vehicleId']: r for r in c._build_state(50.0)['ships']}[
        101]['health'] == 1000

    c._healthSamplingDue = False
    not_due = c._build_state(50.2)
    assert 'health' not in {r['vehicleId']: r for r in not_due['ships']}[101]
    assert first_entity.reads.get('health') == 1

    # Same player/vehicle id reused by a later entity: the next HP due sample
    # reads the new component value, not a cached frame row.
    c._capture_avatar_snapshot = lambda: {
        'entities': AvatarRows([
            avatar_entity(1, health=(400, 1000, True))]),
        'status': 'complete', 'count': 1, 'limit': 256, 'reason': None}
    c._healthSamplingDue = True
    due_again = c._build_state(50.6)
    assert {r['vehicleId']: r for r in due_again['ships']}[101]['health'] == 400
    assert due_again['healthSampling']['sampleTs'] == 50.6


# ---------------------------------------------------------------------------
# restricted Python 2 sandbox helpers
# ---------------------------------------------------------------------------
def restricted_builtins():
    restricted = dict(vars(builtins))
    for name in ('AttributeError', 'IndexError', 'TypeError', 'iter', 'next'):
        restricted.pop(name, None)
    return restricted


def test_observation_helper_survives_restricted_python2_builtins():
    ns = main_namespace(Obj(**CC_KEYS))
    build = method('_build_avatar_observations', ns)
    ns['__builtins__'] = restricted_builtins()
    restricted = FunctionType(build.__code__, ns)
    entities = [avatar_entity(1), avatar_entity(2)]
    holder = AvatarRows(entities)
    snapshot = {'entities': holder, 'status': 'complete', 'count': 2,
                'limit': 256, 'reason': None}
    collector = Obj(_healthSamplingDue=False, _comparisonSamplingDue=False,
                    _healthSamplingInterval=0.5,
                    _comparisonSamplingInterval=1.0)
    observations = restricted(collector, snapshot, 60.0, [])
    assert len(observations['rows']) == 2
    assert all(row['health']['status'] == 'notSampled'
               for row in observations['rows'])
    assert observations['coverage']['status'] == 'notSampled'
