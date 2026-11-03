from pathlib import Path
from types import SimpleNamespace as Obj
import textwrap
import re
import builtins


def adapter(restricted=False):
    source = (Path(__file__).resolve().parents[1] /
              'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf8')
    start = source.index('    def _position_from_obj(')
    end = source.index('\n    def ', start + 1)
    def attempt(fn):
        try:
            return fn()
        except Exception:
            return None
    ns = {'_get': lambda obj, key: getattr(obj, key, None),
          '_vec': lambda raw: list(raw) if isinstance(raw, (list, tuple)) and len(raw) == 3 else None,
          '_try': attempt, '_is_mapping': lambda obj: isinstance(obj, dict)}
    if restricted:
        allowed = dict(vars(builtins))
        allowed.pop('AttributeError')
        ns['__builtins__'] = allowed
    exec(textwrap.dedent(source[start:end]), ns)
    cls = type('PositionHarness', (), {'_position_from_obj': ns['_position_from_obj']})
    obj = cls()
    obj._positionDiagnostics = {}
    return obj


def test_position_probe_distinguishes_missing_none_and_invalid():
    c = adapter()
    assert c._position_from_obj(Obj(position=None, worldPosition='bad')) is None
    assert c._positionDiagnostics['getPosition:missing'] == 1
    assert c._positionDiagnostics['position:none'] == 1
    assert c._positionDiagnostics['worldPosition:invalidVector'] == 1


def test_position_probe_failure_does_not_stop_fallback():
    def fail():
        raise RuntimeError('not ready')
    c = adapter()
    assert c._position_from_obj(Obj(getPosition=fail, worldPosition=(1, 2, 3))) == [1, 2, 3]
    assert c._positionDiagnostics['getPosition:error'] == 1
    assert c._positionDiagnostics['worldPosition:available'] == 1


def test_game_python2_sources_declare_encoding_when_non_ascii():
    folder = Path(__file__).resolve().parents[1] / 'res_mods/PnFMods/WowsExtractor'
    for path in folder.glob('*.py'):
        raw = path.read_bytes()
        if any(byte >= 128 for byte in raw):
            header = b'\n'.join(raw.splitlines()[:2])
            assert re.search(br'coding[:=]\s*utf-8', header), path.name


def test_position_probe_does_not_require_attributeerror_builtin():
    c = adapter(restricted=True)
    assert c._position_from_obj(Obj()) is None
    assert c._positionDiagnostics['getPosition:missing'] == 1
    def fail():
        raise AttributeError('game wrapper')
    assert c._position_from_obj(Obj(getPosition=fail, position=[1, 2, 3])) == [1, 2, 3]
    assert c._positionDiagnostics['getPosition:error'] == 1


def position_reader(battle):
    source = (Path(__file__).resolve().parents[1] /
              'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf8')
    start = source.index('    def _position_from_obj(')
    end = source.index('\n    def _collect_map_positions(', start)
    ns = {'_UNSET': object(), '_get': lambda obj, key, default=None:
          obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default),
          '_vec': lambda raw: list(raw) if isinstance(raw, (list, tuple)) and
          len(raw) == 3 else None, '_try': lambda fn, default=None:
          _attempt(fn, default), '_is_mapping': lambda obj: isinstance(obj, dict),
          'battle': battle}
    exec(textwrap.dedent(source[start:end]), ns)
    cls = type('PositionHarness', (), {
        '_position_from_obj': ns['_position_from_obj'],
        '_get_ship_position': ns['_get_ship_position']})
    obj = cls()
    obj._positionDiagnostics = {}
    return obj


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def test_direct_core_position_one_call_and_no_lookup_retry_for_none_or_exception():
    class Battle(object):
        def getPlayerShipInfo(self, pid):
            raise AssertionError('core path must not request player info')
        getPlayerInfo = getPlayerShipInfo
        def getPlayerByVehicleId(self, vid):
            raise AssertionError('must reuse caller lookup, never retry')
    for result in (None, RuntimeError('bad getter')):
        calls = []
        def get_position():
            calls.append(1)
            if isinstance(result, Exception):
                raise result
            return result
        ship = Obj(getPosition=get_position, position=(9, 8, 7))
        c = position_reader(Battle())
        pos, status = c._get_ship_position(ship, 7, 70, player=None,
                                             allow_fallback=False)
        assert pos is None and calls == [1]
        assert status['status'] == 'unknown'
        assert status['fallbackStatus'] == 'notSampled'
        assert c._positionDiagnostics['getPosition:' +
            ('none' if result is None else 'error')] == 1


def test_due_optin_fallback_reuses_cached_player_and_does_not_cache_positions():
    calls = {'shipLookup': 0, 'info': 0, 'direct': 0}
    class Battle(object):
        def getPlayerByVehicleId(self, vid):
            calls['shipLookup'] += 1
            raise AssertionError('resolver must not lookup vehicle again')
        def getPlayerShipInfo(self, pid):
            calls['info'] += 1
            return {'worldPosition': (4, 5, 6)}
        def getPlayerInfo(self, pid):
            raise AssertionError('first fallback succeeded')
    c = position_reader(Battle())
    player = {'id': 7}
    def ship_position():
        calls['direct'] += 1
        return None
    ship = Obj(getPosition=ship_position)
    pos, status = c._get_ship_position(ship, 7, 70, player=player,
                                         allow_fallback=True)
    assert pos == [4, 5, 6]
    assert status['fallbackStatus'] == 'available'
    assert calls == {'shipLookup': 0, 'info': 1, 'direct': 1}
    # Fresh next-frame call is independent; there is no previous-position cache.
    Battle.getPlayerShipInfo = lambda self, pid: None
    pos2, status2 = c._get_ship_position(ship, 7, 70, player=None,
                                           allow_fallback=True)
    assert pos2 is None and status2['status'] == 'unknown'
    assert calls['direct'] == 2


def test_main_build_ships_24_direct_getters_and_vehicle_lookups_are_one_each():
    source = (Path(__file__).resolve().parents[1] /
              'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf8')
    start = source.index('    def _position_from_obj(')
    end = source.index('\n\ndef _is_mapping(', start)
    calls = {'vehicle': 0, 'direct': 0, 'info': 0, 'maps': 0}
    ships = []
    players = {}
    for i in range(24):
        ship = Obj(_Ship__id=1000 + i, teamId=1, uiId=i,
                   getPosition=lambda i=i: calls.__setitem__(
                       'direct', calls['direct'] + 1) or
                       (None if i == 0 else (i, 2, 3)),
                   isAlive=lambda: True)
        ships.append(ship)
        players[1000 + i] = Obj(id=2000 + i, teamId=1)
    class Battle(object):
        def getAllShips(self):
            return ships
        def getPlayerByVehicleId(self, vehicle):
            calls['vehicle'] += 1
            if vehicle == 1000:
                return players[vehicle]
            if vehicle % 3 == 1:
                raise RuntimeError('lookup failed')
            if vehicle % 3 == 2:
                return None
            return players.get(vehicle)
        def getPlayerShipInfo(self, pid):
            calls['info'] += 1
            return Obj(worldPosition=(4, 5, 6))
        getPlayerInfo = getPlayerShipInfo
    class Damage(object):
        def remember(self, *args):
            pass
    class Calibration(object):
        def __init__(self):
            self.observe_calls = 0
            self.snapshot_calls = 0
        def observe(self, *args):
            self.observe_calls += 1
            return {'status': 'unknown', 'observeBatch': self.observe_calls}
        def snapshot(self):
            self.snapshot_calls += 1
            return {'status': 'unknown'}
    def collect_maps(collector, avatar_entities=None):
        calls['maps'] += 1
        collector._mapVisibility = {}
        collector._mapVisibilityDiagnostics = {}
        return {}
    ns = {'_UNSET': object(), 'battle': Battle(), '_get': lambda obj, key,
          default=None: obj.get(key, default) if isinstance(obj, dict) else
          getattr(obj, key, default), '_vec': lambda raw: list(raw) if
          isinstance(raw, (list, tuple)) and len(raw) == 3 else None,
          '_try': _attempt, '_is_mapping': lambda obj: isinstance(obj, dict),
          '_map_norm_xy': lambda *args: None,
          '_visibility_raw': lambda value: value,
          '_visibility_observation': lambda *args: {}, 'long': int,
          'apply_ui_health': lambda *args, **kwargs: None}
    exec(textwrap.dedent(source[start:end]), ns)
    class Harness(object):
        _position_from_obj = ns['_position_from_obj']
        _get_ship_position = ns['_get_ship_position']
        _build_ships = ns['_build_ships']
        _collect_map_positions = collect_maps
        _relation = lambda self, team: 1
        _map_to_world = lambda self, *args: None
    c = Harness()
    c._diagnosticsEnabled = False
    c._diagnosticsSampleDue = False
    c._positionFallbacksEnabled = False
    c._positionDiagnostics = {}
    c._damage = Damage()
    c._mapCalibration = Calibration()
    rows, diag = c._build_ships(1.0)
    assert len(rows) == 24
    assert calls == {'vehicle': 24, 'direct': 24, 'info': 0, 'maps': 1}
    assert c._mapCalibration.observe_calls == 1
    assert c._mapCalibration.snapshot_calls == 0
    assert diag['mapCalibration'] == {'status': 'unknown', 'observeBatch': 1}
    assert diag['positionReadPolicy'] == {
        'policy': 'coreDirectOnly', 'sampledShips': 0, 'notSampledShips': 24}
    assert rows[0]['positionReadStatus']['status'] == 'unknown'
    assert all(row['positionReadStatus']['status'] == 'available' for row in rows[1:])
    assert all(row['positionReadPolicy']['fallbackStatus'] == 'notSampled'
               for row in rows)

    # Explicit opt-in alone is insufficient: no extended read on a non-due frame.
    c._positionFallbacksEnabled = True
    c._diagnosticsEnabled = True
    c._diagnosticsSampleDue = False
    rows_not_due, diag_not_due = c._build_ships(2.0)
    assert calls['info'] == 0
    assert diag_not_due['positionReads']['sampledShips'] == 0
    assert rows_not_due[0]['positionReadPolicy']['fallbackStatus'] == 'notSampled'

    # Only the enabled diagnostic due sample runs compatibility fallback.
    c._diagnosticsSampleDue = True
    rows_due, diag_due = c._build_ships(3.0)
    assert calls == {'vehicle': 72, 'direct': 72, 'info': 1, 'maps': 3}
    assert rows_due[0]['positionReadStatus']['status'] == 'unknown'
    assert rows_due[0]['positionReadPolicy']['fallbackStatus'] == 'available'
    assert rows_due[0]['positionReadPolicy']['fallbackSource'] == 'diagnosticFallback'
    assert rows_due[0]['position'] == [4, 5, 6]
    assert diag_due['positionReads']['sampledShips'] == 1
    assert diag_due['positionReads']['notSampledShips'] == 23
    assert c._mapCalibration.observe_calls == 3
    assert c._mapCalibration.snapshot_calls == 0
    assert diag_due['mapCalibration'] == {'status': 'unknown', 'observeBatch': 3}
