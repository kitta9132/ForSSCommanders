"""Exercise actual lifecycle methods without importing the Python 2 game module."""
from pathlib import Path
from types import SimpleNamespace as Obj
import textwrap

import pytest


SOURCE = (Path(__file__).resolve().parents[1] /
          'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf-8')


def load_method(name, namespace):
    start = SOURCE.index('    def ' + name + '(')
    end = SOURCE.find('\n    def ', start + 1)
    code = textwrap.dedent(SOURCE[start:end if end != -1 else None])
    exec(code, namespace)
    return namespace[name]


@pytest.fixture
def harness():
    calls = []
    ns = {'_now': lambda: 100., 'META_RETRY_SECONDS': 12.,
          'META_RETRY_INTERVAL': 1., 'SCHEMA_VERSION': 1,
          'WIRE_API_VERSION': '1.0', 'logInfo': calls.append,
          '_get': lambda obj, key, default=None: getattr(obj, key, default),
          '_try': lambda fn: fn(), 'json_dumps': lambda data: '{}',
          'battle': Obj(getSelfPlayerInfo=lambda: Obj(id=1)),
          'callbacks': Obj(perTick=lambda fn: calls.append('schedule') or 7)}
    names = ('_on_battle_start', '_on_battle_shown', '_start_collection',
             '_on_battle_quit', '_refresh_meta')
    cls = type('CollectorHarness', (), {n: load_method(n, ns) for n in names})
    c = cls()
    c._active = c._battleStarted = c._battleShown = False
    c._collectionEnabled = True
    c._stateFile = c._metaFile = None
    c._battleId = None
    c._load_config = lambda: None
    def paths():
        c._stateFile, c._metaFile = 'state.json', 'meta.json'
    c._resolve_paths = paths
    c._damage = Obj(clear=lambda: None, snapshot=lambda: {})
    c._mapCalibration = Obj(clear=lambda: None)
    c._torpedoMotion = Obj(clear=lambda: None)
    c._remember_player_vehicle = lambda p: None
    c._remember_roster_vehicles = lambda: None
    c._battleIdentity = Obj(start=lambda *args: 'new-battle', is_arena=True)
    c._find_arena_id = lambda: None
    c._promote_battle_id = lambda: False
    c._build_meta = lambda: {'roster': []}
    c._meta_ready_for_clients = lambda meta: True
    c._stop_tick = lambda: None
    c._tick = lambda: calls.append('tick')
    c._write_state = lambda snap: calls.append(snap)
    ns['_atomic_write'] = lambda path, text: calls.append(('write', path)) or True
    return c, calls, ns


@pytest.mark.parametrize('order', [('shown', 'start'), ('start', 'shown')])
def test_waits_for_both_events_and_initializes_before_output(harness, order):
    c, calls, _ = harness
    getattr(c, '_on_battle_' + order[0])()
    assert not c._active
    assert not calls
    getattr(c, '_on_battle_' + order[1])()
    assert c._active and c._battleId == 'new-battle'
    assert ('write', 'meta.json') in calls
    assert calls.count('schedule') == 1
    c._on_battle_shown()
    assert calls.count('schedule') == 1
    c._on_battle_quit()
    assert not c._battleStarted and not c._battleShown and not c._active
    calls.clear()
    c._on_battle_shown()
    assert not c._active and not calls
    c._on_battle_start()
    assert c._active and ('write', 'meta.json') in calls


def test_missing_meta_path_does_not_write_or_report_success(harness):
    c, calls, _ = harness
    c._refresh_meta(force=True)
    assert not calls


def test_battle_start_and_quit_reset_the_meta_probe_schedule(harness):
    c, _calls, _ns = harness
    c._metaProbeDue = 99.0
    c._metaProbeLastNow = 98.0
    c._on_battle_quit()
    assert c._metaProbeDue is None and c._metaProbeLastNow is None

    c._metaProbeDue = 99.0
    c._metaProbeLastNow = 98.0
    c._on_battle_start()
    assert c._metaProbeDue is None and c._metaProbeLastNow is None


def test_sampling_group_membership_is_cleared_at_both_battle_boundaries(harness):
    c, calls, _ = harness
    c._torpedoSamplingGroups = Obj(clear=lambda: calls.append('sampling-clear'))
    c._on_battle_start()
    assert calls.count('sampling-clear') == 1
    c._on_battle_shown()
    c._on_battle_quit()
    assert calls.count('sampling-clear') == 2


def test_failed_meta_write_remains_retryable_and_does_not_report_success(harness):
    c, calls, ns = harness
    c._on_battle_start()
    ns['_atomic_write'] = lambda path, text: False
    c._refresh_meta(force=True)
    assert c._lastMetaWrite == 0.
    assert not c._metaReady
    assert not calls
    ns['_atomic_write'] = lambda path, text: True
    c._refresh_meta(now=102.)
    assert c._metaReady and c._lastMetaWrite == 102.
    assert len(calls) == 1
