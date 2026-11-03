from pathlib import Path
import textwrap
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'res_mods/PnFMods/WowsExtractor'))
from performance_profiler import PerformanceProfiler
from ui_health import (
    AvatarRows, index_avatar_health, index_avatar_health_sample)
from damage_tracker import roster_ids_from_avatar


SOURCE = (Path(__file__).resolve().parents[1] /
          'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf-8')


def method(name, ns):
    start = SOURCE.index('    def ' + name + '(')
    ends = [pos for marker in ('\n    def ', '\n    @staticmethod')
            if (pos := SOURCE.find(marker, start + 1)) != -1]
    end = min(ends) if ends else -1
    code = SOURCE[start:end if end != -1 else None]
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(textwrap.dedent(code), ns)
    return ns[name]


def test_config_is_opt_in_and_unknown_values_are_off():
    current = {}
    load = method('_load_config', {
        '_load_mod_config': lambda: current,
        '_cfg_float': lambda cfg, key, default: default, 'STATE_INTERVAL': .1,
        'PerformanceProfiler': _DisabledProfiler})
    for config, expected in [({}, False), ({'collection_enabled': 'false'}, False),
                             ({'collection_enabled': 'yes'}, False),
                             ({'collection_enabled': 'TRUE'}, False),
                             ({'collection_enabled': 'true'}, True)]:
        c = type('C', (), {})()
        current.clear()
        current.update(config)
        load(c)
        assert c._collectionEnabled is expected
        assert c._diagnosticsEnabled is False
        assert c._positionFallbacksEnabled is False
        assert c._diagnosticsInterval == 1.0
        if not expected:
            assert c._performanceProfiler is None

    c = type('C', (), {})()
    current.clear()
    current.update({'collection_enabled': 'true', 'diagnostics_enabled': 'true'})
    load(c)
    assert c._collectionEnabled is True and c._diagnosticsEnabled is True
    current['position_fallbacks_enabled'] = 'true'
    load(c)
    assert c._positionFallbacksEnabled is True
    current['position_fallbacks_enabled'] = 'TRUE'
    load(c)
    assert c._positionFallbacksEnabled is False

    c = type('C', (), {})()
    ns = {'_load_mod_config': lambda: (_ for _ in ()).throw(ValueError()),
          '_cfg_float': lambda cfg, key, default: default, 'STATE_INTERVAL': .1,
          'PerformanceProfiler': _DisabledProfiler}
    method('_load_config', ns)(c)
    assert c._collectionEnabled is False


def test_diagnostic_scheduler_samples_twice_per_two_seconds_without_catchup():
    due = method('_diagnostics_due', {})
    c = type('C', (), {'_diagnosticsEnabled': True,
        '_diagnosticsInterval': 1.0, '_diagnosticsNextDue': None,
        '_diagnosticsLastSampleTs': None, '_diagnosticsLastNow': None})()
    samples = [now for now in [i / 10.0 for i in range(20)]
               if due(c, now)]
    assert samples == [0.0, 1.0]
    # A delayed tick samples once and schedules from its actual timestamp.
    assert due(c, 5.0) is True
    assert due(c, 5.01) is False
    assert c._diagnosticsNextDue == 6.0
    # Clock rollback reopens the schedule immediately; invalid time clears history.
    assert due(c, 4.0) is True
    assert due(c, float('nan')) is False
    assert c._diagnosticsNextDue is None
    assert due(c, 4.1) is True
    c._diagnosticsEnabled = False
    assert due(c, 4.2) is False
    assert c._diagnosticsNextDue is None


def test_main_tick_keeps_collection_alive_when_profiler_clock_fails(monkeypatch):
    import performance_profiler
    class BadTime(object):
        @staticmethod
        def clock():
            raise RuntimeError('do not leak this text')
    monkeypatch.setattr(performance_profiler, 'time', BadTime())
    profiler = PerformanceProfiler(True, True)
    assert profiler.status == 'clockException'
    writes, builds, errors = [], [], []
    now_values = iter([1.0, 2.0])
    ns = {'_now': lambda: next(now_values), '_get': getattr, '_str': str,
          'logError': errors.append}
    tick = method('_tick', ns)
    c = type('Collector', (), {})()
    c._active = c._collectionEnabled = True
    c._diagnosticsEnabled = False
    c._diagnosticsSampleDue = False
    c._diagnosticsLastNow = None
    c._diagnosticsNextDue = c._diagnosticsLastSampleTs = None
    c._diagnostics_due = lambda now: False
    c._refresh_meta = lambda now: None
    c._stateInterval, c._lastWrite = .1, 0.0
    c._performanceProfiler, c._profilerEnabled = profiler, True
    c._writer = None
    c._build_state = lambda now: builds.append(now) or {'active': True}
    c._write_state = writes.append
    tick(c)
    tick(c)
    assert builds == [1.0, 2.0]
    assert profiler.clock_calls == 1
    assert len(writes) == 2
    assert writes[0]['performance']['status'] == 'clockException'
    assert writes[0]['performance']['writerMode'] == 'syncEncodeWrite'
    assert not errors
    assert 'do not leak' not in repr(writes)


def test_config_profiler_isolation_and_no_reprobe_per_battle(monkeypatch):
    import performance_profiler
    clock = type('Clock', (), {'__init__': lambda self: setattr(self, 'calls', 0),
        '__call__': lambda self: setattr(self, 'calls', self.calls + 1) or
            self.calls * 0.1})()
    monkeypatch.setattr(performance_profiler, 'time', type('Time', (), {
        'clock': staticmethod(clock)})())
    config = {'profiler_enabled': 'true'}
    ns = {'_load_mod_config': lambda: config,
          '_cfg_float': lambda cfg, key, default: default,
          'STATE_INTERVAL': .1, 'PerformanceProfiler': PerformanceProfiler}
    load = method('_load_config', ns)
    c = type('Collector', (), {'_performanceProfiler': None,
                                '_profilerEnabled': False})()
    load(c)
    assert c._performanceProfiler is None
    assert clock.calls == 0

    config['collection_enabled'] = 'true'
    load(c)
    assert c._performanceProfiler.status == 'available'
    assert clock.calls == c._performanceProfiler.clock_calls == 8
    load(c)  # battle config refresh resets the window, not the clock probe
    assert clock.calls == c._performanceProfiler.clock_calls == 8


def test_disabled_start_tick_double_start_and_quit_do_not_poll_game_apis():
    calls = []
    ns = {'_now': lambda: 7., 'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
          'META_RETRY_SECONDS': 12., 'logInfo': calls.append,
          '_try': lambda fn: fn(), 'callbacks': type('Callbacks', (), {
              'perTick': staticmethod(lambda fn: calls.append('schedule')),
              'cancel': staticmethod(lambda h: calls.append('cancel'))})()}
    start = method('_start_collection', ns)
    tick = method('_tick', ns)
    quit_battle = method('_on_battle_quit', ns)
    battle_start = method('_on_battle_start', ns)
    battle_shown = method('_on_battle_shown', ns)
    ammo_changed = method('_on_artillery_ammo_changed', ns)
    c = type('C', (), {})()
    c._active = False
    c._collectionEnabled = False
    c._start_collection = lambda: start(c)
    c._battleStarted = c._battleShown = False
    c._battleId = 'offline'
    c._tickHandle = None
    c._stateFile = 'state.json'
    c._ballistics = type('B', (), {'start': lambda self: calls.append('ballistics-start'),
                                   'stop': lambda self: calls.append('ballistics-stop')})()
    c._write_state = lambda state: calls.append(state)
    c._damage = type('D', (), {'snapshot': lambda self: {},
                               'clear': lambda self: None})()
    c._mapCalibration = type('M', (), {'clear': lambda self: None})()
    c._torpedoMotion = type('M', (), {'clear': lambda self: None})()
    c._stop_tick = lambda: calls.append('stop-tick')
    c._build_state = lambda now: calls.append('build-state')
    c._refresh_meta = lambda now: calls.append('meta-poll')
    c._load_config = lambda: calls.append('config-load')
    c._resolve_paths = lambda: calls.append('resolve-paths')
    c._battleIdentity = type('I', (), {'start': lambda self, *args: 'offline'})()
    c._find_arena_id = lambda: calls.append('arena-api')
    c._remember_player_vehicle = lambda *args: calls.append('player-api')
    c._remember_roster_vehicles = lambda: calls.append('roster-api')
    c._ballistics.on_ammo_changed = lambda *args: calls.append('ballistics-event-api')
    c._stateInterval = .1
    c._lastWrite = 0.
    battle_start(c)
    battle_shown(c)
    ammo_changed(c, 1)
    start(c)
    start(c)
    tick(c)
    assert sum(isinstance(x, dict) for x in calls) == 1
    disabled = next(x for x in calls if isinstance(x, dict))
    assert disabled['collection']['status'] == 'disabled'
    assert not any(x in calls for x in ('schedule', 'ballistics-start',
                                         'build-state', 'meta-poll', 'arena-api',
                                         'player-api', 'roster-api',
                                         'ballistics-event-api'))
    quit_battle(c)
    assert calls[-1]['collection']['status'] == 'disabled'
    assert 'ballistics-stop' not in calls


def test_diagnostic_calls_are_gated_but_opt_in_path_keeps_probe_payload():
    # The active snapshot path retains its established payload when diagnostics
    # are explicitly enabled; the regular offline checker exercises this path.
    assert 'diagnostic_due = diagnostic_enabled and _get(' in SOURCE
    for fn in ('safe_weapon_hub_probe', 'safe_weapon_context_probe',
               'safe_game_clock_probe', 'safe_gun_reload_probe',
               'safe_selected_torpedo_params_probe',
               'safe_torpedo_tooltip_parameter_probe', 'safe_submarine_probe',
               'safe_identity_candidates'):
        assert SOURCE.count(fn + '(') >= 1
    assert "'source': 'config.diagnostics_enabled'" in SOURCE


def test_diagnostics_off_builds_fresh_disabled_shapes_without_probe_calls():
    calls = []
    fail_if_called = lambda *args, **kwargs: calls.append('unexpected-probe')
    ns = {'_UNSET': object(), '_try': lambda fn, default=None: fn(),
          '_get': lambda obj, key, default=None: getattr(obj, key, default),
          'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
           'dataHub': object(), 'CC': object(),
           'battle': type('Battle', (), {'getSelfPlayerInfo': lambda self: None,
               'getSelfPlayerShip': lambda self: None})(),
          'ui_torpedo_probe': fail_if_called, 'safe_weapon_hub_probe': fail_if_called,
          'safe_weapon_context_probe': fail_if_called, 'safe_game_clock_probe': fail_if_called,
          'safe_gun_reload_probe': fail_if_called,
          'safe_selected_torpedo_params_probe': fail_if_called,
          'safe_torpedo_tooltip_parameter_probe': fail_if_called,
           'safe_submarine_probe': fail_if_called,
           'safe_identity_candidates': fail_if_called,
           'shared_diagnostic_snapshot': fail_if_called,
          'attach_ui_state': fail_if_called}
    build = method('_build_state', ns)
    c = type('C', (), {})()
    c._active = True
    c._diagnosticsEnabled = False
    c._battleId = 'b'
    c._selfTeam = None
    c._capture_avatar_snapshot = lambda: {'entities': [], 'status': 'complete',
        'count': 0, 'limit': 256, 'reason': None}
    c._remember_roster_vehicles = lambda entities: None
    c._collect_avatar_health = lambda entities: {}
    c._build_ships = lambda now, hp, entities: ([], {})
    c._self_team = lambda self_info=None: 1
    c._torpedoes = type('T', (), {'torpedoes': lambda self, team: ([], {'available': True}),
        'armament': lambda self, ship=None: {}, 'systems': lambda self, ship=None: {}})()
    c._torpedoMotion = type('T', (), {'update': lambda *args: None})()
    c._mapCalibration = type('M', (), {'world_to_map': lambda *args: None})()
    c._build_self = lambda hp, info=None, ship=None: {}
    c._damage = type('D', (), {'snapshot': lambda self: {}})()
    c._ballistics = type('B', (), {'snapshot': lambda self: {}})()
    snapshot = build(c, 1.)
    assert not calls
    assert snapshot['weaponHubProbe'] == {
        'status': 'disabled', 'source': 'config.diagnostics_enabled'}
    assert snapshot['selfSubmarineProbe']['status'] == 'disabled'
    assert snapshot['identityCandidates']['status'] == 'disabled'
    c._diagnosticsEnabled = True
    c._diagnosticsSampleDue = False
    not_sampled = build(c, 2.)
    assert not_sampled['weaponHubProbe'] == {
        'status': 'notSampled', 'source': 'scheduling',
        'sampleTs': None}
    assert not_sampled['selfSubmarineProbe']['status'] == 'notSampled'
    assert not_sampled['uiTorpedoProbe']['status'] == 'notSampled'
    assert not calls


def test_core_avatar_capture_is_bounded_fresh_and_preserves_failure_status():
    calls = []
    source = list(range(256))
    ns = {'dataHub': type('Hub', (), {'getEntityCollections':
        lambda self, name: calls.append(name) or source})(),
        'AvatarRows': AvatarRows}
    capture = method('_capture_avatar_snapshot', ns)
    snap = capture(type('C', (), {})())
    assert snap == {'entities': source, 'status': 'complete', 'count': 256,
                    'limit': 256, 'reason': None}
    assert snap['entities'].complete is True
    assert calls == ['avatar']

    source.append(256)
    next_snap = capture(type('C', (), {})())
    assert next_snap['status'] == 'truncated' and next_snap['count'] == 256
    assert next_snap['entities'] == source[:256]
    assert next_snap['entities'].complete is False
    assert calls == ['avatar', 'avatar']  # no cross-frame reuse

    ns['dataHub'].getEntityCollections = lambda name: []
    empty = capture(type('C', (), {})())
    assert empty['status'] == 'complete' and empty['count'] == 0
    ns['dataHub'].getEntityCollections = lambda name: None
    none = capture(type('C', (), {})())
    assert none['status'] == 'partial' and none['reason'] == 'none'
    ns['dataHub'].getEntityCollections = lambda name: (_ for _ in ()).throw(RuntimeError())
    failed = capture(type('C', (), {})())
    assert failed['status'] == 'partial' and failed['reason'] == 'getterError'

    def broken_rows():
        yield 'first'
        raise RuntimeError('after row')
    ns['dataHub'].getEntityCollections = lambda name: broken_rows()
    partial = capture(type('C', (), {})())
    assert partial['entities'] == ['first']
    assert partial['entities'].complete is False
    assert partial['status'] == 'partial' and partial['reason'] == 'iterationError'


def test_roster_event_caller_keeps_independent_lookup_without_state_argument():
    calls = []
    ns = {'_UNSET': object(), '_try': lambda fn, default=None: _attempt(fn, default),
          '_get': lambda obj, key, default=None: (obj.get(key, default)
              if isinstance(obj, dict) else getattr(obj, key, default)),
          '_is_mapping': lambda obj: isinstance(obj, dict),
          'battle': type('Battle', (), {'getPlayersInfo': lambda self: []})(),
          'CC': type('CC', (), {'avatar': 'avatar', 'vehicle': 'vehicle'})(),
          'dataHub': type('Hub', (), {'getEntityCollections': lambda self, name:
              calls.append(name) or [{'avatar': {}, 'vehicle': {}}]})(),
          'roster_ids_from_avatar': lambda avatar, vehicle: None}
    class Damage(object):
        def remember(self, *args):
            pass
    remember = method('_remember_roster_vehicles', ns)
    collector = type('C', (), {'_damage': Damage()})()
    remember(collector)       # event caller: independent getter remains
    remember(collector, [])   # state caller: supplied capture; no getter
    assert calls == ['avatar']


def test_24_avatar_core_outputs_match_independent_getters_and_share_one_call():
    fixture = [{'avatar': {'playerId': pid}, 'vehicle': {'id': 1000 + pid},
                'health': {'value': 800 - pid, 'max': 1000, 'isAlive': True},
                'mapPosition': {'position': (pid / 100.0, pid / 200.0), 'yaw': pid}}
               for pid in range(1, 25)]
    getter_calls = []
    hub = type('Hub', (), {'getEntityCollections': lambda self, name:
        getter_calls.append(name) or fixture})()
    cc = type('CC', (), {'avatar': 'avatar', 'vehicle': 'vehicle',
        'health': 'health', 'mapPosition': 'mapPosition', 'visibility': 'visibility'})()
    def make_ns():
        return {'_UNSET': object(), '_try': _attempt,
            '_get': lambda obj, key, default=None: (obj.get(key, default)
                if isinstance(obj, dict) else getattr(obj, key, default)),
            '_is_mapping': lambda obj: isinstance(obj, dict), 'dataHub': hub, 'CC': cc,
            'battle': type('Battle', (), {'getPlayersInfo': lambda self: []})(),
            'roster_ids_from_avatar': lambda avatar, vehicle:
                (avatar.get('playerId'), vehicle.get('id'), 1),
            'index_avatar_health': lambda entities, _cc: {
                row['avatar']['playerId']: row['health'] for row in entities},
            '_point_xy': lambda point: point}
    class Damage(object):
        def __init__(self):
            self.rows = []
        def remember(self, *args):
            self.rows.append(args)
    roster = method('_remember_roster_vehicles', make_ns())
    health = method('_collect_avatar_health', make_ns())
    positions = method('_collect_map_positions', make_ns())
    def consumer():
        damage = Damage()
        collector = type('C', (), {'_damage': damage,
            '_diagnosticsEnabled': False, '_diagnosticsSampleDue': False})()
        roster(collector)
        hp = health(collector)
        maps = positions(collector)
        return damage.rows, hp, maps
    independent = consumer()
    assert getter_calls == ['avatar', 'avatar', 'avatar']
    getter_calls[:] = []
    def shared_consumer():
        damage = Damage()
        collector = type('C', (), {'_damage': damage,
            '_diagnosticsEnabled': False, '_diagnosticsSampleDue': False})()
        rows = hub.getEntityCollections('avatar')
        roster(collector, rows)
        hp = health(collector, rows)
        maps = positions(collector, rows)
        return damage.rows, hp, maps
    shared = shared_consumer()
    assert shared == independent
    assert getter_calls == ['avatar']
    assert len(shared[0]) == len(shared[1]) == len(shared[2]) == 24


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


class _DisabledProfiler(object):
    def __init__(self, enabled, collection_enabled):
        self.enabled = bool(enabled and collection_enabled)
    def reset_battle(self):
        pass


def test_build_state_shares_fresh_core_snapshot_even_when_diagnostics_off():
    calls = []
    rows = [object() for _ in range(24)]
    ns = {'_UNSET': object(), '_try': lambda fn, default=None: fn(),
          '_get': lambda obj, key, default=None: getattr(obj, key, default),
          'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
           'dataHub': object(), 'CC': object(), 'attach_ui_state': lambda *a: None,
           'battle': type('Battle', (), {'getSelfPlayerInfo': lambda self: None,
               'getSelfPlayerShip': lambda self: None})()}
    build = method('_build_state', ns)
    c = type('C', (), {})()
    c._active, c._diagnosticsEnabled, c._diagnosticsSampleDue = True, False, False
    c._performanceProfiler, c._profilerEnabled = None, False
    c._battleId, c._selfTeam = 'b', None
    captured = {'entities': rows, 'status': 'complete',
        'count': 24, 'limit': 256, 'reason': None}
    c._capture_avatar_snapshot = lambda: captured
    c._remember_roster_vehicles = lambda entities: calls.append(('roster', entities))
    c._collect_avatar_health = lambda entities: calls.append(('health', entities)) or {}
    c._build_ships = lambda now, hp, entities: (
        calls.append(('ships', entities)) or ([], {}))
    c._self_team = lambda self_info=None: 1
    c._torpedoes = type('T', (), {'torpedoes': lambda self, team: ([], {'available': True}),
        'armament': lambda self, ship=None: {}, 'systems': lambda self, ship=None: {}})()
    c._torpedoMotion = type('T', (), {'update': lambda *args: None})()
    c._mapCalibration = type('M', (), {'world_to_map': lambda *args: None})()
    c._build_self = lambda hp, info=None, ship=None: {}
    c._damage = type('D', (), {'snapshot': lambda self: {}})()
    c._ballistics = type('B', (), {'snapshot': lambda self: {}})()
    complete = build(c, 1.)
    assert 'performance' not in complete
    assert [name for name, _ in calls] == ['roster', 'health', 'ships']
    assert all(entities is rows for _, entities in calls)
    assert calls[1][1] is calls[0][1]
    assert complete['diag']['avatarSnapshotStatus']['status'] == 'complete'
    calls[:] = []
    captured.update({'entities': rows[:1], 'status': 'partial', 'count': 1,
                     'reason': 'iterationError'})
    partial = build(c, 2.)
    assert calls[1][1] == []  # partial health cannot assert alive/dead by absence
    assert partial['diag']['avatarSnapshotStatus'] == {
        'status': 'partial', 'count': 1, 'limit': 256,
        'reason': 'iterationError'}


def test_main_state_reuses_actual_self_producers_once_and_never_across_frames():
    from types import MethodType

    calls = {'info': 0, 'ship': 0, 'observer': 0, 'team': 0,
             'armament': [], 'systems': []}
    ship = type('Ship', (), {
        'getPosition': lambda self: (1, 2, 3),
        'getTorpedoesModulesState': lambda self: [],
        'getConsumablesState': lambda self: [],
        'getRadarInfo': lambda self: None,
        'getHydroAcousticSearchInfo': lambda self: None,
        'getSubmarineLocatorInfo': lambda self: None,
        'health': 800, 'maxHealth': 1000, 'yaw': 0.5})()
    info = type('Info', (), {'id': 42, 'teamId': 1,
        'shipGameData': {'health': 800, 'maxHealth': 1000, 'speed': 10}})()
    observer = type('Observer', (), {'getPosition': lambda self: (9, 9, 9)})()
    class Battle(object):
        def getSelfPlayerInfo(self):
            calls['info'] += 1
            if calls['info'] >= 3:
                raise RuntimeError('self info unavailable')
            return info if calls['info'] == 1 else None
        def getSelfPlayerShip(self):
            calls['ship'] += 1
            if calls['ship'] >= 3:
                raise RuntimeError('self ship unavailable')
            return ship if calls['ship'] == 1 else None
        def getObserverShip(self):
            calls['observer'] += 1
            return observer
        def getSelfPlayer(self):
            calls['team'] += 1
            raise AssertionError('must use captured self info')
        def isObserverMode(self):
            return calls['ship'] >= 2
    class Torpedoes(object):
        def torpedoes(self, self_team):
            return [], {'available': True, 'status': 'available'}
        def armament(self, self_ship):
            calls['armament'].append(self_ship)
            return {'available': self_ship is not None}
        def systems(self, self_ship):
            calls['systems'].append(self_ship)
            return {'status': 'available' if self_ship is not None else 'unknown'}

    ns = {'_UNSET': object(), '_try': _attempt,
        '_get': lambda obj, key, default=None: (obj.get(key, default)
            if isinstance(obj, dict) else getattr(obj, key, default)),
        '_is_mapping': lambda obj: isinstance(obj, dict),
        '_vec': lambda value: list(value) if value is not None else None,
        'apply_ui_health': lambda data, hp: None,
        'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
        'battle': Battle(), 'dataHub': object(), 'CC': object(),
        'attach_ui_state': lambda *args: None}
    build = method('_build_state', ns)
    build_self = method('_build_self', ns)
    self_team = method('_self_team', ns)
    class Collector(object):
        pass
    c = Collector()
    c._active, c._diagnosticsEnabled, c._diagnosticsSampleDue = True, False, False
    c._battleId, c._selfTeam = 'test', ns['_UNSET']
    c._capture_avatar_snapshot = lambda: {'entities': [], 'status': 'complete',
        'count': 0, 'limit': 256, 'reason': None}
    c._remember_roster_vehicles = lambda entities: None
    c._collect_avatar_health = lambda entities: {}
    c._build_ships = lambda now, hp, entities: ([], {'totalShips': 0})
    c._torpedoes = Torpedoes()
    c._torpedoMotion = type('Motion', (), {'update': lambda *args: None})()
    c._mapCalibration = type('Map', (), {'world_to_map': lambda *args: None})()
    c._build_self = MethodType(build_self, c)
    c._self_team = MethodType(self_team, c)
    c._damage = type('Damage', (), {'snapshot': lambda self: {}})()
    c._ballistics = type('Ballistics', (), {'snapshot': lambda self: {}})()

    first = build(c, 1.0)
    assert (calls['info'], calls['ship'], calls['team']) == (1, 1, 0)
    assert first['self'] == {'playerId': 42, 'teamId': 1, 'health': 800,
        'maxHealth': 1000, 'speed': 10, 'position': [1, 2, 3],
        'yaw': 0.5, 'isObserver': False}
    assert calls['armament'] == [ship] and calls['systems'] == [ship]
    assert first['torpedoArmament']['available'] is True

    second = build(c, 2.0)
    assert (calls['info'], calls['ship']) == (2, 2)
    assert calls['observer'] == 1  # only _build_self fallback; never weapon input
    assert calls['armament'] == [ship, None]
    assert calls['systems'] == [ship, None]
    assert second['self'] == {'position': [9, 9, 9], 'isObserver': True}
    assert 'teamId' not in second['self']
    assert second['torpedoArmament']['available'] is False
    assert second['selfSystems']['status'] == 'unknown'

    third = build(c, 3.0)
    assert (calls['info'], calls['ship']) == (3, 3)
    assert calls['armament'] == [ship, None, None]
    assert calls['systems'] == [ship, None, None]
    assert calls['observer'] == 2
    assert 'teamId' not in third['self']
    assert third['torpedoArmament']['available'] is False

class _ReadCounter(object):
    def __init__(self):
        self.components = 0
        self.properties = 0


class _CountedComp(object):
    def __init__(self, counter, **fields):
        self._counter = counter
        self._fields = fields

    def __getattr__(self, name):
        if name not in self._fields:
            raise AttributeError(name)
        self._counter.properties += 1
        return self._fields[name]


class _CountedEntity(object):
    def __init__(self, counter, components):
        self._counter = counter
        self._components = components

    def __getitem__(self, key):
        self._counter.components += 1
        return self._components[key]


def _avatar_read_rows(counter, count=24):
    rows = []
    for pid in range(1, count + 1):
        rows.append(_CountedEntity(counter, {
            'avatar': _CountedComp(
                counter, playerId=pid, id=100000 + pid,
                teamId=1 if pid % 2 else 0, shipId=2000 + pid),
            'vehicle': _CountedComp(counter, id=2000 + pid),
            'health': _CountedComp(counter, value=1000 - pid, max=1000,
                                   isAlive=True),
            'mapPosition': _CountedComp(
                counter, position=(pid / 100.0, pid / 200.0), yaw=pid),
        }))
    return rows


def _avatar_read_ns(cc):
    ns = {
        '_try': _attempt,
        '_get': lambda obj, key, default=None: (
            obj.get(key, default) if isinstance(obj, dict)
            else getattr(obj, key, default)),
        '_is_mapping': lambda obj: isinstance(obj, dict),
        '_point_xy': lambda pt: [float(pt[0]), float(pt[1])],
        'CC': cc,
        'battle': type('Battle', (), {'getPlayersInfo': lambda self: []})(),
        'dataHub': object(),
        'roster_ids_from_avatar': roster_ids_from_avatar,
        'index_avatar_health': index_avatar_health,
        'index_avatar_health_sample': index_avatar_health_sample,
    }
    method('_remember_roster_vehicles', ns)
    method('_collect_avatar_health', ns)
    method('_collect_map_positions', ns)
    return ns


class _AvatarDamage(object):
    def __init__(self):
        self.rows = []

    def remember(self, *args):
        self.rows.append(args)


def _avatar_collector():
    return type('C', (), {
        '_damage': _AvatarDamage(),
        '_diagnosticsEnabled': False, '_diagnosticsSampleDue': False,
        '_mapVisibility': {}, '_mapVisibilityDiagnostics': {}})()


def test_avatar_sample_24_rows_reduces_component_and_id_reads_once():
    cc = type('CC', (), {
        'avatar': 'avatar', 'vehicle': 'vehicle', 'health': 'health',
        'mapPosition': 'mapPosition', 'visibility': 'visibility'})()
    ns = _avatar_read_ns(cc)
    legacy_reads = _ReadCounter()
    legacy_rows = _avatar_read_rows(legacy_reads)
    legacy_collector = _avatar_collector()
    ns['_remember_roster_vehicles'](legacy_collector, legacy_rows)
    legacy_hp = ns['_collect_avatar_health'](legacy_collector, legacy_rows)
    legacy_maps = ns['_collect_map_positions'](legacy_collector, legacy_rows)
    # 2+3+2 component reads and 3+6+3 id/property reads per row.
    assert legacy_reads.components == 168
    assert legacy_reads.properties == 288

    shared_reads = _ReadCounter()
    holder = AvatarRows(_avatar_read_rows(shared_reads))
    shared_collector = _avatar_collector()
    ns['_remember_roster_vehicles'](shared_collector, holder)
    shared_hp = ns['_collect_avatar_health'](shared_collector, holder)
    shared_maps = ns['_collect_map_positions'](shared_collector, holder)
    # avatar+vehicle+health+mapPosition components once; ids/health/yaw once.
    assert shared_reads.components == 96
    assert shared_reads.properties == 240
    assert legacy_reads.components + legacy_reads.properties == 456
    assert shared_reads.components + shared_reads.properties == 336
    assert legacy_collector._damage.rows == shared_collector._damage.rows
    assert legacy_hp == shared_hp
    assert legacy_maps == shared_maps
    assert len(shared_collector._damage.rows) == 24
    assert (2002, 2, 0) in shared_collector._damage.rows
    assert shared_hp[1]['health'] == 999
    assert shared_maps[1] == (0.01, 0.005, 1)


def test_partial_avatar_rows_keep_map_and_roster_but_skip_health_index():
    cc = type('CC', (), {
        'avatar': 'avatar', 'vehicle': 'vehicle', 'health': 'health',
        'mapPosition': 'mapPosition', 'visibility': 'visibility'})()
    ns = _avatar_read_ns(cc)
    reads = _ReadCounter()
    holder = AvatarRows(_avatar_read_rows(reads, count=2))
    collector = _avatar_collector()
    ns['_remember_roster_vehicles'](collector, holder)
    # _build_state passes [] for partial/truncated snapshots: absence must not
    # become dead/alive and the health index stays empty.
    assert ns['_collect_avatar_health'](collector, []) == {}
    maps = ns['_collect_map_positions'](collector, holder)
    assert maps == {1: (0.01, 0.005, 1), 2: (0.02, 0.01, 2)}
    assert len(collector._damage.rows) == 2
    assert collector._mapVisibility == {1: {}, 2: {}}


def test_shared_sample_missing_components_cc_none_and_no_next_frame_reuse():
    cc = type('CC', (), {
        'avatar': 'avatar', 'vehicle': 'vehicle', 'health': 'health',
        'mapPosition': 'mapPosition', 'visibility': 'visibility'})()
    ns = _avatar_read_ns(cc)

    class Broken(object):
        def __getitem__(self, key):
            raise RuntimeError('component unavailable')

    readable = _CountedEntity(_ReadCounter(), {
        'avatar': _CountedComp(_ReadCounter(), playerId=5),
        'health': _CountedComp(_ReadCounter(), value=5, max=10,
                               isAlive=True),
        'mapPosition': _CountedComp(
            _ReadCounter(), position=(0.5, 0.5), yaw=0)})
    holder = AvatarRows([Broken(), readable])
    collector = _avatar_collector()
    ns['_remember_roster_vehicles'](collector, holder)
    hp = ns['_collect_avatar_health'](collector, holder)
    maps = ns['_collect_map_positions'](collector, holder)
    assert hp == {5: {'health': 5, 'maxHealth': 10}}
    assert maps == {5: (0.5, 0.5, 0)}
    assert collector._damage.rows == []

    # A later empty capture must not reuse the previous holder's sample.
    empty = AvatarRows([])
    next_collector = _avatar_collector()
    ns['_remember_roster_vehicles'](next_collector, empty)
    assert ns['_collect_avatar_health'](next_collector, empty) == {}
    assert ns['_collect_map_positions'](next_collector, empty) == {}
    assert next_collector._damage.rows == []
    assert holder._sample is not None and empty._sample is not None

    ns['CC'] = None
    ns['_remember_roster_vehicles'](next_collector, empty)
    assert ns['_collect_avatar_health'](next_collector, empty) == {}
    assert ns['_collect_map_positions'](next_collector, empty) == {}


def test_collection_off_tick_never_builds_avatar_state():
    calls = []
    tick = method('_tick', {'_now': lambda: 1.0})
    c = type('C', (), {})()
    c._active = True
    c._collectionEnabled = False
    c._build_state = lambda now: calls.append(now)
    tick(c)
    assert calls == []
