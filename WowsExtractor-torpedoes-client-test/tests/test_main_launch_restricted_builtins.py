"""Regression: Main.py launch path survives restricted Python 2 builtins.

The WoWS Python 2 runtime exposes a restricted builtin namespace that does
not include ``globals()``. 0.3.41 introduced several ``globals().get(...)``
calls in Main.py for optional TTaro prefs / torpedo-policy helpers; at mod
load these raised ``NameError: global name 'globals' is not defined`` and the
collector never started, leaving B49 recordings empty.

This test execs the real Main.py source with ``globals`` removed from
``__builtins__``, stubs the game modules, and walks the actual launch path:

    import -> instantiate -> load-complete -> battle start -> battle shown -> tick

It runs twice: with and without a live TTaro framework binding, to confirm that
neither path makes core unusable.
"""
import builtins
import re
import sys
from pathlib import Path
from types import SimpleNamespace as Obj

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / 'res_mods' / 'PnFMods' / 'WowsExtractor'
sys.path.insert(0, str(MODULE_DIR))
MAIN_SOURCE = (MODULE_DIR / 'Main.py').read_text(encoding='utf-8')


class _QuietLog(object):
    def __call__(self, *args):
        pass


GAME_MODULE_NAMES = ('events', 'ui', 'utils', 'dataHub', 'constants',
                     'battle', 'callbacks', 'threading')


@pytest.fixture
def game_stubs(monkeypatch, tmp_path):
    """Provide minimal game modules so Main.py's guarded imports succeed.

    The fixture removes the stub modules from ``sys.modules`` after the test
    so other tests see the real import state.
    """
    events = Obj(
        onBattleStart=lambda fn: None,
        onBattleShown=lambda fn: None,
        onBattleQuit=lambda fn: None,
        onReceiveDamagesOnShip=lambda fn: None,
        onReceiveShellInfo=lambda fn: None,
        onLoadModsCompleted=lambda fn: None,
    )
    ui = Obj()
    utils = Obj(
        getModDir=lambda: str(tmp_path),
        getTimeFromGameStart=lambda: 1.0,
        logInfo=_QuietLog(),
        logError=_QuietLog(),
        jsonEncode=None,
    )
    dataHub = Obj(
        getEntityCollections=lambda name: [],
        getSingleEntity=lambda name: None,
        getPrimaryEntity=lambda *args: None,
        getSingleComponent=lambda *args: None,
        getEntity=lambda *args: None,
    )
    constants = Obj(UiComponents=Obj())
    battle = Obj(
        getSelfPlayerInfo=lambda: Obj(id=1, teamId=0),
        getSelfPlayerShip=lambda: Obj(),
        getSelfPlayer=lambda: Obj(teamId=0),
        getAllShips=lambda: [],
        getPlayersInfo=lambda: None,
        getPlayers=lambda: None,
        getPlayerByVehicleId=lambda vid: None,
        getArenaInfo=lambda: None,
    )
    callbacks = Obj(perTick=lambda fn: 7, cancel=lambda handle: None)
    # Pretend threading is unavailable so the async writer is never started.
    threading = Obj()

    previous = {}
    for name, mod in (('events', events), ('ui', ui), ('utils', utils),
                      ('dataHub', dataHub), ('constants', constants),
                      ('battle', battle), ('callbacks', callbacks),
                      ('threading', threading)):
        previous[name] = sys.modules.get(name)
        sys.modules[name] = mod
    yield
    for name in GAME_MODULE_NAMES:
        if previous[name] is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous[name]


def _restricted_builtins():
    """Return a copy of builtins with ``globals`` removed.

    Also drops the builtins the existing restricted-builtin tests already
    guard against, so this launch-path regression exercises the same contract.
    """
    restricted = dict(vars(builtins))
    for name in ('globals', 'enumerate', 'iter', 'next', 'AttributeError',
                 'TypeError'):
        restricted.pop(name, None)
    return restricted


def _exec_main():
    """Exec Main.py under restricted builtins and return its namespace."""
    # Main.py targets the game's Python 2 runtime; convert the one Python 2
    # syntax form (`except Exception, e:`) that Python 3 rejects.
    source = re.sub(r'except Exception, ([a-zA-Z_][a-zA-Z0-9_]*):',
                    r'except Exception as \1:', MAIN_SOURCE)
    sys.path.insert(0, str(MODULE_DIR))
    try:
        ns = {
            '__name__': 'WowsExtractor_restricted_launch_test',
            '__file__': str(MODULE_DIR / 'Main.py'),
            '__package__': None,
            '__builtins__': _restricted_builtins(),
        }
        exec(compile(source, str(MODULE_DIR / 'Main.py'), 'exec'), ns)
        return ns
    finally:
        sys.path.remove(str(MODULE_DIR))


def _lifecycle_smoke(gcollector):
    """Walk load-complete / battle start / shown / tick and assert core works."""
    # load-complete bind gate (0.3.41 TTaro integration)
    gcollector._on_load_mods_completed()
    # battle lifecycle
    gcollector._on_battle_start()
    gcollector._on_battle_shown()

    # Now force collection on and run a minimal tick without relying on the
    # full dataHub/ship build path.
    gcollector._active = True
    gcollector._collectionEnabled = True
    gcollector._stateFile = '/tmp/state.json'
    gcollector._stateInterval = 0.0
    gcollector._refresh_meta = lambda now=None: None

    written = []
    emitted = []

    def build_state(now):
        written.append(('build', now))
        return {
            'schema': 1, 'apiVersion': '1.0', 'battleId': gcollector._battleId,
            'active': True, 'ts': now, 'ships': [], 'self': None,
            'torpedoes': [], 'damage': {},
        }

    gcollector._build_state = build_state
    gcollector._write_state = emitted.append
    gcollector._tick()
    assert written == [('build', 1.0)]
    assert len(emitted) == 1
    assert emitted[0]['active'] is True


def test_launch_path_without_globals_and_without_ttaro(game_stubs, monkeypatch):
    """Core starts and ticks when no TTaro framework binding is available."""
    import ttaro_prefs_binding
    monkeypatch.setattr(ttaro_prefs_binding, 'build_binding', lambda: None)
    ns = _exec_main()
    gcollector = ns['gCollector']
    assert isinstance(gcollector, ns['Collector'])
    _lifecycle_smoke(gcollector)
    # With no framework binding the adapter stays on ini fallback / defaults.
    adapter = gcollector._torpedoPrefsAdapter
    assert adapter is None or adapter.source() in ('ini', 'none')


def test_launch_path_without_globals_and_with_ttaro(game_stubs, monkeypatch):
    """Core starts and ticks when a TTaro framework binding is present."""

    class StubBinding(object):
        def __init__(self):
            self.handles = []

        def subscribe(self, comp_key, callback):
            self.handles.append((comp_key, callback))
            return object()

        def unsubscribe(self, handle):
            pass

        def read(self, comp_key):
            return None

    stub = StubBinding()
    import ttaro_prefs_binding
    monkeypatch.setattr(ttaro_prefs_binding, 'build_binding', lambda: stub)
    ns = _exec_main()
    gcollector = ns['gCollector']
    assert isinstance(gcollector, ns['Collector'])
    _lifecycle_smoke(gcollector)
    # Framework present: the adapter should have subscribed to each setting key.
    adapter = gcollector._torpedoPrefsAdapter
    assert adapter is not None
    assert gcollector._torpedoPrefsBinding is stub
    assert len(adapter.handles()) == 2
