"""Exercise collection without importing the game runtime."""
from pathlib import Path
from types import SimpleNamespace as Obj
import textwrap

SOURCE = (Path(__file__).resolve().parents[1] /
          'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf8')


def method(name, ns):
    start = SOURCE.index('    def ' + name + '(')
    end = SOURCE.find('\n    def ', start + 1)
    code = SOURCE[start:end].split('\n    @staticmethod')[0]
    exec(textwrap.dedent(code), ns)
    return ns[name]


def test_hidden_and_unknown_visibility_do_not_discard_coordinates():
    def get(obj, key):
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    def attempt(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    entities = [
        {'avatar': {'playerId': 1}, 'visibility': {'mapVisible': False},
         'mapPosition': {'position': [0.2, 0.3], 'yaw': 1}},
        {'avatar': {'playerId': 2},
         'mapPosition': {'position': [1.2, 0.3]}},
        {'avatar': {'playerId': 3}, 'visibility': {'mapVisible': True}},
    ]
    ns = {'CC': Obj(mapPosition='mapPosition', avatar='avatar', visibility='visibility'),
          'dataHub': Obj(getEntityCollections=lambda name: entities),
          '_get': get, '_try': attempt, '_point_xy': lambda p: p}
    collect = method('_collect_map_positions', ns)
    collector = Obj()
    result = collect(collector)
    assert result[1][:2] == (0.2, 0.3)
    assert result[2][:2] == (1.2, 0.3)  # raw out-of-range observation retained
    assert collector._mapVisibility == {
        1: {'mapVisible': False}, 2: {}, 3: {'mapVisible': True}}
    entities[:] = []
    assert collect(collector) == {}
    assert collector._mapVisibility == {}  # no previous-frame synthesis
