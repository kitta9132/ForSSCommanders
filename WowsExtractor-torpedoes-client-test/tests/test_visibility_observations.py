"""Exercise collection without importing the game runtime."""
from pathlib import Path
from types import SimpleNamespace as Obj
import ast
import textwrap
import json

SOURCE = (Path(__file__).resolve().parents[1] /
          'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf8')
SOURCE_TREE = ast.parse(SOURCE)


def method(name, ns):
    start = SOURCE.index('    def ' + name + '(')
    end = SOURCE.find('\n    def ', start + 1)
    if end < 0:
        end = SOURCE.find('\n\ndef _is_mapping', start)
    code = SOURCE[start:end].split('\n    @staticmethod')[0]
    exec(textwrap.dedent(code), ns)
    return ns[name]


def source_function(name, ns):
    """Execute the named top-level function from Main.py, not a test double."""
    node = next(item for item in SOURCE_TREE.body
                if isinstance(item, ast.FunctionDef) and item.name == name)
    module = ast.Module(body=[node], type_ignores=[])
    exec(compile(module, str(Path(__file__).resolve().parents[1] /
                             'res_mods/PnFMods/WowsExtractor/Main.py'), 'exec'), ns)
    return ns[name]


def visibility_ns(**values):
    ns = {'_is_mapping': lambda obj: isinstance(obj, dict), 'long': int,
          '_INT_TYPES': (int,), '_STRING_TYPES': (str,)}
    for name in ('_visibility_type', '_visibility_raw', '_visibility_observation'):
        source_function(name, ns)
    ns.update(values)
    return ns


def test_visibility_helpers_execute_main_source_and_enforce_safe_raw_contract():
    ns = visibility_ns()
    classify = ns['_visibility_type']
    raw = ns['_visibility_raw']
    observation = ns['_visibility_observation']

    assert classify(None) == 'NoneType'
    assert classify(False) == 'bool'
    assert classify(0) == 'int'
    assert classify(1.0) == 'float'
    assert classify('visible') == 'string'
    assert classify(object()) == 'object'
    assert raw(None) is None
    assert raw(False) is False
    assert raw(0) == 0
    assert raw(1) == 1
    assert raw(1.5) == 1.5
    assert raw('x' * 128) == 'x' * 128
    assert raw('x' * 129) is None
    assert raw(float('nan')) is None
    assert raw(float('inf')) is None
    assert raw(float('-inf')) is None
    assert raw(object()) is None
    assert observation('dataHub.visibility.mapVisible', 'none', None) == {
        'source': 'dataHub.visibility.mapVisible', 'status': 'none',
        'raw': None, 'type': 'NoneType', 'reason': None}
    json.dumps(observation('dataHub.visibility.mapVisible', 'nonBoolean',
                           float('nan'), 'nonFiniteNumber'), allow_nan=False)


def test_hidden_and_unknown_visibility_do_not_discard_coordinates():
    def get(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)

    def attempt(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    entities = [
        {'avatar': {'playerId': 1}, 'visibility': {'mapVisible': False, 'visible': True},
         'mapPosition': {'position': [0.2, 0.3], 'yaw': 1}},
        {'avatar': {'playerId': 2},
         'mapPosition': {'position': [1.2, 0.3]}},
        {'avatar': {'playerId': 3}, 'visibility': {'mapVisible': True}},
    ]
    ns = visibility_ns(**{
        'CC': Obj(mapPosition='mapPosition', avatar='avatar', visibility='visibility'),
        'dataHub': Obj(getEntityCollections=lambda name: entities),
        '_get': get, '_try': attempt, '_point_xy': lambda p: p})
    collect = method('_collect_map_positions', ns)
    collector = Obj(_diagnosticsEnabled=True)
    result = collect(collector)
    assert result[1][:2] == (0.2, 0.3)
    assert result[2][:2] == (1.2, 0.3)  # raw out-of-range observation retained
    assert collector._mapVisibility == {
        1: {'mapVisible': False, 'visible': True}, 2: {}, 3: {'mapVisible': True}}
    diag = collector._mapVisibilityDiagnostics[1]['candidates']
    assert diag['mapVisible']['status'] == 'available'
    assert diag['mapVisible']['raw'] is False
    assert diag['visible']['source'] == 'dataHub.visibility.visible'
    assert diag['visible']['type'] == 'bool'
    assert collector._mapVisibilityDiagnostics[2]['candidates']['visible']['status'] == 'componentMissing'
    entities[:] = []
    assert collect(collector) == {}
    assert collector._mapVisibility == {}  # no previous-frame synthesis


def test_visibility_unknown_is_not_false_and_non_scalars_are_not_exported():
    entities = [{'avatar': {'playerId': 1},
                 'visibility': {'mapVisible': None, 'visible': False,
                                'isVisible': 'false', 'isShipVisible': 0}}]
    ns = visibility_ns(**{
        'CC': Obj(mapPosition=None, avatar='avatar', visibility='visibility'),
        'dataHub': Obj(getEntityCollections=lambda name: entities),
        '_get': lambda obj, key, default=None: (obj.get(key, default) if isinstance(obj, dict)
                                  else getattr(obj, key, default)),
        '_try': lambda fn, default=None: fn(), '_point_xy': lambda p: p})
    collector = Obj(_diagnosticsEnabled=True)
    assert method('_collect_map_positions', ns)(collector) == {}
    assert collector._mapVisibility == {1: {'visible': False, 'isShipVisible': 0}}
    candidates = collector._mapVisibilityDiagnostics[1]['candidates']
    assert candidates['mapVisible']['status'] == 'none'
    assert candidates['mapVisible']['raw'] is None
    assert candidates['visible']['status'] == 'available'
    assert candidates['isVisible']['status'] == 'nonBoolean'
    assert candidates['isVisible']['type'] == 'string'
    assert candidates['isShipVisible']['status'] == 'nonBoolean'
    assert candidates['isShipVisible']['raw'] == 0


def test_visibility_diagnostics_distinguish_missing_error_component_and_cc_key():
    class Broken(object):
        @property
        def visible(self):
            raise RuntimeError('not ready')

    class ComponentFailure(dict):
        def __getitem__(self, key):
            if key == 'visibility':
                raise RuntimeError('component unavailable')
            return dict.__getitem__(self, key)

    entities = [
        {'avatar': {'playerId': 1}, 'visibility': Broken()},
        {'avatar': {'playerId': 2}},
        ComponentFailure(avatar={'playerId': 3}),
    ]
    ns = visibility_ns(**{
        'CC': Obj(mapPosition=None, avatar='avatar', visibility='visibility'),
        'dataHub': Obj(getEntityCollections=lambda name: entities),
        '_get': lambda obj, key, default=None: (obj.get(key, default) if isinstance(obj, dict)
                                  else getattr(obj, key, default)),
        '_try': lambda fn, default=None: fn(), '_point_xy': lambda p: p})
    collector = Obj(_diagnosticsEnabled=True)
    method('_collect_map_positions', ns)(collector)
    first = collector._mapVisibilityDiagnostics[1]['candidates']
    assert first['mapVisible']['status'] == 'missing'
    assert first['mapVisible']['reason'] == 'attributeMissing'
    assert first['visible']['status'] == 'readError'
    assert first['visible']['reason'] == 'attributeReadException'
    assert collector._mapVisibilityDiagnostics[2]['candidates']['mapVisible']['status'] == 'componentMissing'
    assert collector._mapVisibilityDiagnostics[3]['candidates']['mapVisible']['status'] == 'componentReadError'

    ns['CC'] = Obj(mapPosition=None, avatar='avatar')
    method('_collect_map_positions', ns)(collector)
    assert collector._mapVisibilityDiagnostics[1]['candidates']['mapVisible']['status'] == 'ccKeyMissing'


def test_nonfinite_visibility_is_not_exported_as_json_number():
    entities = [{'avatar': {'playerId': 1}, 'visibility': {
        'mapVisible': float('nan'), 'visible': float('inf'),
        'isVisible': float('-inf'), 'isShipVisible': object()}}]
    ns = visibility_ns(**{
        'CC': Obj(mapPosition=None, avatar='avatar', visibility='visibility'),
        'dataHub': Obj(getEntityCollections=lambda name: entities),
        '_get': lambda obj, key, default=None: (obj.get(key, default) if isinstance(obj, dict)
                                  else getattr(obj, key, default)),
        '_try': lambda fn, default=None: fn(), '_point_xy': lambda p: p})
    collector = Obj(_diagnosticsEnabled=True)
    method('_collect_map_positions', ns)(collector)
    assert collector._mapVisibility == {1: {}}
    candidates = collector._mapVisibilityDiagnostics[1]['candidates']
    assert candidates['mapVisible']['status'] == 'nonBoolean'
    assert candidates['mapVisible']['raw'] is None
    assert candidates['mapVisible']['reason'] == 'nonFiniteNumber'
    assert candidates['visible']['raw'] is None
    assert candidates['isShipVisible']['type'] == 'object'
    assert candidates['isShipVisible']['raw'] is None
    json.dumps(collector._mapVisibilityDiagnostics, allow_nan=False)


def test_ship_api_visibility_is_a_separate_diagnostic_source():
    ships = [Obj(_Ship__id=100, teamId=1, isVisible=False, isShipVisible=0),
             Obj(_Ship__id=101, teamId=1, isVisible=True)]
    ns = visibility_ns(**{
        '_try': lambda fn, default=None: _attempt(fn, default),
        '_get': lambda obj, key, default=None: getattr(obj, key, default),
        '_map_norm_xy': lambda x, y: None,
        'apply_ui_health': lambda *args, **kwargs: None,
        'battle': Obj(getAllShips=lambda: ships,
                      getPlayerByVehicleId=lambda vehicle_id:
                      Obj(id=vehicle_id - 90, teamId=1)),
        'INVALID': -1})
    build = method('_build_ships', ns)
    class Damage(object):
        def remember(self, *args):
            pass
    class Calibration(object):
        def observe(self, *args):
            pass
        def snapshot(self):
            return {'status': 'unknown'}
    def collect_map_positions(collector):
        collector._mapVisibility = {10: {'mapVisible': 0},
                                    11: {'mapVisible': 1}}
        collector._mapVisibilityDiagnostics = {
            pid: {'componentStatus': 'available', 'candidates': {
                'mapVisible': ns['_visibility_observation'](
                    'dataHub.visibility.mapVisible', 'nonBoolean', value,
                    'expectedBoolean')}}
            for pid, value in ((10, 0), (11, 1))}
        return {}

    collector = Obj(_diagnosticsEnabled=True, _positionDiagnostics={}, _mapVisibility={},
                    _mapVisibilityDiagnostics={}, _damage=Damage(),
                    _mapCalibration=Calibration(),
                    _self_team=lambda: 1, _relation=lambda team: 1,
                    _get_ship_position=lambda *args: None,
                    _collect_map_positions=lambda: collect_map_positions(collector),
                    _map_to_world=lambda *args: None)
    rows, _diag = build(collector, 0.1, {})
    visibility = rows[0]['visibility']
    assert visibility['shipApi'] == {'isVisible': False, 'isShipVisible': 0}
    assert visibility['dataHubCandidates']['mapVisible']['raw'] == 0
    assert visibility['status'] == 'available'
    assert rows[0]['visible'] is False
    assert visibility['shipApiCandidates']['isVisible'] == {
        'source': 'shipApi.isVisible', 'status': 'available', 'raw': False,
        'type': 'bool', 'reason': None}
    assert visibility['shipApiCandidates']['isShipVisible']['status'] == 'nonBoolean'
    assert visibility['shipApiCandidates']['isShipVisible']['raw'] == 0
    assert rows[1]['visibility']['dataHubCandidates']['mapVisible']['raw'] == 1
    assert rows[1]['visible'] is True
    assert rows[1]['visibility']['status'] == 'available'
    json.dumps(rows, allow_nan=False)


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default
