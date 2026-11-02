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
