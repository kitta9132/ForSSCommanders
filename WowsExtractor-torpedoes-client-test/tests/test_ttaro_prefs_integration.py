"""Main.py <-> TTaro prefs bridge integration (0.3.41, offline).

Composes the real Main methods (extracted from the Python 2 source and run
under Python 3) against the self-authored adapter and a stubbed framework
binding. Covers the lifecycle the user asked for: instantiate once, resolve and
bind lazily at load-complete, queue panel edits into the policy, apply them at
the tick gate before the frame is built, dispose on battle end, and the
absence fallback (no framework -> config.ini values stay in effect).

No game, no dataHub, no API enumeration: the stub binding only ever receives
one indexed subscribe per setting key.
"""
import textwrap
import types
from pathlib import Path
from types import SimpleNamespace as Obj

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / 'res_mods' / 'PnFMods' / 'WowsExtractor'

import sys  # noqa: E402
sys.path.insert(0, str(MODULE_DIR))

from ttaro_prefs_adapter import PrefsAdapter, component_key  # noqa: E402
from torpedo_telemetry import (  # noqa: E402
    TorpedoSamplingGroups, TorpedoSamplingSettings,
    normalize_torpedo_sampling_settings)

MAIN_SOURCE = (MODULE_DIR / 'Main.py').read_text(encoding='utf-8')


def load_main_method(name, namespace):
    """Extract one ``def name`` from Main.py and exec it into ``namespace``."""
    start = MAIN_SOURCE.index('    def ' + name + '(')
    end = MAIN_SOURCE.find('\n    def ', start + 1)
    code = textwrap.dedent(MAIN_SOURCE[start:end if end != -1 else None])
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(code, namespace)
    return namespace[name]


class StubBinding(object):
    """Minimal binding matching the adapter contract; no game access."""

    def __init__(self):
        self.values = {}
        self.callbacks = {}
        self.unsubscribed = []

    def subscribe(self, comp_key, callback):
        self.callbacks[comp_key] = callback
        return comp_key

    def unsubscribe(self, handle):
        self.unsubscribed.append(handle)
        self.callbacks.pop(handle, None)

    def read(self, comp_key):
        return self.values.get(comp_key)

    def emit(self, setting_key, value):
        self.values[component_key(setting_key)] = value
        callback = self.callbacks.get(component_key(setting_key))
        if callback is not None:
            callback(setting_key, value)


def _collector(globals_extra, method_names):
    ns = dict(globals_extra)
    for name in method_names:
        load_main_method(name, ns)
    # A method whose name matches a module helper overwrites it during exec;
    # restore the helper so direct name lookups resolve as they do at runtime.
    for key, value in globals_extra.items():
        ns[key] = value
    collector = Obj()
    for name in method_names:
        setattr(collector, name, types.MethodType(ns[name], collector))
    return collector


BRIDGE_METHODS = (
    '_torpedo_prefs_fallback',
    '_ensure_torpedo_prefs_adapter',
    '_discover_torpedo_prefs_binding',
    '_bind_torpedo_prefs_adapter',
    '_on_load_mods_completed',
    '_consume_torpedo_prefs',
    'dispose_torpedo_prefs_adapter',
    'queue_torpedo_sampling_settings',
    '_apply_pending_torpedo_sampling_settings',
)


def test_panel_values_are_reapplied_after_ini_reload_on_next_battle():
    stub = StubBinding()
    stub.values = {component_key('enemyHighBudget'): 31,
                   component_key('radiusDivisor'): 7.0}
    c = _collector({'PrefsAdapter': PrefsAdapter,
                    'build_ttaro_prefs_binding': lambda: stub,
                    'normalize_torpedo_sampling_settings': normalize_torpedo_sampling_settings},
                   BRIDGE_METHODS)
    c._torpedoSamplingSettings = TorpedoSamplingSettings()
    c._bind_torpedo_prefs_adapter('battleStart')
    c._consume_torpedo_prefs(0.0)
    assert c._torpedoSamplingSettings.enemy_high_budget == 31
    c.dispose_torpedo_prefs_adapter('battleEnd')
    c._torpedoSamplingSettings = TorpedoSamplingSettings()
    c._bind_torpedo_prefs_adapter('battleStart')
    c._consume_torpedo_prefs(20.0)
    assert c._torpedoSamplingSettings.enemy_high_budget == 31
    assert c._torpedoSamplingSettings.radius_divisor == 7.0


def test_ini_reload_without_panel_does_not_replay_old_adapter_values():
    c = _collector({'PrefsAdapter': PrefsAdapter,
                    'build_ttaro_prefs_binding': lambda: None,
                    'normalize_torpedo_sampling_settings': normalize_torpedo_sampling_settings},
                   BRIDGE_METHODS)
    c._torpedoSamplingSettings = TorpedoSamplingSettings(enemy_high_budget=100)
    c._bind_torpedo_prefs_adapter('battleStart')
    c._consume_torpedo_prefs(0.0)
    c.dispose_torpedo_prefs_adapter('battleEnd')
    c._torpedoSamplingSettings = TorpedoSamplingSettings(enemy_high_budget=120)
    c._bind_torpedo_prefs_adapter('battleStart')
    c._consume_torpedo_prefs(20.0)
    assert c._torpedoSamplingSettings.enemy_high_budget == 120


def test_panel_default_equal_to_old_ini_still_overlays_new_ini():
    stub = StubBinding()
    stub.values = {component_key('enemyHighBudget'): 20,
                   component_key('radiusDivisor'): 5.0}
    c = _collector({'PrefsAdapter': PrefsAdapter,
                    'build_ttaro_prefs_binding': lambda: stub,
                    'normalize_torpedo_sampling_settings': normalize_torpedo_sampling_settings},
                   BRIDGE_METHODS)
    c._torpedoSamplingSettings = TorpedoSamplingSettings(enemy_high_budget=100)
    c._bind_torpedo_prefs_adapter('battleStart')
    c._consume_torpedo_prefs(0.0)
    assert c._torpedoSamplingSettings.enemy_high_budget == 20


# ------------------------------------------------------- instantiate once
def test_ensure_builds_adapter_once_and_uses_ini_fallback():
    settings = TorpedoSamplingSettings(radius_divisor=7.0,
                                       enemy_high_budget=9)
    collector = _collector(
        {'PrefsAdapter': PrefsAdapter},
        ('_torpedo_prefs_fallback', '_ensure_torpedo_prefs_adapter'))
    collector._torpedoSamplingSettings = settings
    collector._torpedoPrefsAdapter = None

    adapter = collector._ensure_torpedo_prefs_adapter()
    assert adapter is not None
    assert collector._ensure_torpedo_prefs_adapter() is adapter  # once only
    # No binding: the adapter reports the ini fallback after start().
    assert adapter.start() == 'ini'
    assert adapter.value('enemy_high_budget') == 9
    assert adapter.value('radius_divisor') == 7.0
    assert adapter.source() == 'ini'


def test_ensure_returns_none_when_the_adapter_module_is_absent():
    collector = _collector({}, ('_torpedo_prefs_fallback',
                                '_ensure_torpedo_prefs_adapter'))
    collector._torpedoSamplingSettings = TorpedoSamplingSettings()
    collector._torpedoPrefsAdapter = None
    assert collector._ensure_torpedo_prefs_adapter() is None


# ----------------------------------------------------------- lazy bind
def test_bind_without_framework_starts_adapter_on_ini_and_reports_false():
    settings = TorpedoSamplingSettings(radius_divisor=6.0,
                                       enemy_high_budget=11)
    collector = _collector(
        {'PrefsAdapter': PrefsAdapter,
         'build_ttaro_prefs_binding': lambda: None},
        BRIDGE_METHODS)
    collector._torpedoSamplingSettings = settings
    collector._torpedoSamplingSettingsPending = False
    collector._torpedoSamplingRevision = 0
    collector._torpedoPrefsAdapter = None
    collector._torpedoPrefsBinding = None
    collector._torpedoPrefsRevision = 0

    assert collector._bind_torpedo_prefs_adapter('loadComplete') is False
    adapter = collector._torpedoPrefsAdapter
    assert adapter is not None
    assert adapter.status() == 'running'
    assert adapter.source() == 'ini'
    assert adapter.value('enemy_high_budget') == 11
    assert adapter.handles() == []          # nothing subscribed: no framework


def test_bind_attaches_framework_binding_and_subscribes_each_key():
    stub = StubBinding()
    collector = _collector(
        {'PrefsAdapter': PrefsAdapter,
         'build_ttaro_prefs_binding': lambda: stub},
        BRIDGE_METHODS)
    collector._torpedoSamplingSettings = TorpedoSamplingSettings()
    collector._torpedoSamplingSettingsPending = False
    collector._torpedoSamplingRevision = 0
    collector._torpedoPrefsAdapter = None
    collector._torpedoPrefsBinding = None
    collector._torpedoPrefsRevision = 0

    assert collector._bind_torpedo_prefs_adapter('loadComplete') is True
    adapter = collector._torpedoPrefsAdapter
    assert adapter.status() == 'running'
    # Exactly one indexed subscribe per setting key; no enumeration.
    assert set(stub.callbacks.keys()) == {
        component_key('enemyHighBudget'), component_key('radiusDivisor')}
    assert len(adapter.handles()) == 2


def test_on_load_mods_completed_triggers_the_bind_gate():
    reasons = []
    collector = _collector({}, ())
    collector._bind_torpedo_prefs_adapter = (
        lambda reason=None: reasons.append(reason))
    bind = load_main_method('_on_load_mods_completed',
                            {'__builtins__': __builtins__})
    bind(collector)
    assert reasons == ['loadComplete']


def test_subscribe_load_complete_registers_only_when_the_event_exists():
    registered = []
    events = Obj(onLoadModsCompleted=lambda handler: registered.append(handler))
    ns = {'events': events, '__builtins__': __builtins__}
    method = load_main_method('_subscribe_torpedo_prefs_load_complete', ns)
    ns['events'] = events
    collector = Obj()
    handler = object()
    collector._on_load_mods_completed = handler
    method(collector)
    assert registered == [handler]

    quiet = load_main_method('_subscribe_torpedo_prefs_load_complete',
                             {'__builtins__': __builtins__})
    quiet(Obj())          # no events module: silent no-op


# --------------------------------------------------- consume -> queue -> apply
def test_consume_queues_framework_edits_once_per_change():
    stub = StubBinding()
    collector = _collector(
        {'PrefsAdapter': PrefsAdapter,
         'build_ttaro_prefs_binding': lambda: stub,
         'normalize_torpedo_sampling_settings':
             normalize_torpedo_sampling_settings},
        BRIDGE_METHODS)
    collector._torpedoSamplingSettings = TorpedoSamplingSettings()
    collector._torpedoSamplingSettingsPending = False
    collector._torpedoSamplingRevision = 0
    collector._torpedoPrefsAdapter = None
    collector._torpedoPrefsBinding = None
    collector._torpedoPrefsRevision = 0
    assert collector._bind_torpedo_prefs_adapter('loadComplete') is True

    calls = []
    real_queue = collector.queue_torpedo_sampling_settings

    def queue(values):
        calls.append(dict(values))
        return real_queue(values)

    collector.queue_torpedo_sampling_settings = queue

    stub.emit('enemyHighBudget', 25)
    stub.emit('radiusDivisor', 8.0)
    collector._consume_torpedo_prefs(1.0)
    assert calls == [{'enemy_high_budget': 25, 'radius_divisor': 8.0}]
    settings = collector._torpedoSamplingSettings
    assert settings.enemy_high_budget == 25
    assert settings.radius_divisor == 8.0
    assert collector._torpedoSamplingSettingsPending is True

    # No new edit: the tick applies nothing and the queue is not touched again.
    collector._consume_torpedo_prefs(1.1)
    assert len(calls) == 1


def test_consume_does_nothing_without_an_adapter():
    collector = _collector({}, ('_consume_torpedo_prefs',))
    collector._torpedoPrefsAdapter = None
    collector.queue_torpedo_sampling_settings = (
        lambda values: (_ for _ in ()).throw(AssertionError('queued')))
    collector._consume_torpedo_prefs(1.0)   # must not raise or queue


# --------------------------------------------------------------- disposal
def test_dispose_releases_handles_and_stops_the_adapter():
    stub = StubBinding()
    collector = _collector(
        {'PrefsAdapter': PrefsAdapter,
         'build_ttaro_prefs_binding': lambda: stub,
         'normalize_torpedo_sampling_settings':
             normalize_torpedo_sampling_settings},
        BRIDGE_METHODS)
    collector._torpedoSamplingSettings = TorpedoSamplingSettings()
    collector._torpedoSamplingSettingsPending = False
    collector._torpedoSamplingRevision = 0
    collector._torpedoPrefsAdapter = None
    collector._torpedoPrefsBinding = None
    collector._torpedoPrefsRevision = 0
    collector._bind_torpedo_prefs_adapter('battleStart')

    adapter = collector._torpedoPrefsAdapter
    collector.dispose_torpedo_prefs_adapter('battleEnd')
    assert adapter.status() == 'stopped'
    assert len(stub.unsubscribed) == 2      # both handles released once
    assert stub.callbacks == {}
    collector.dispose_torpedo_prefs_adapter('battleEnd')   # idempotent


# ------------------------------------- fallback broad values are not clamped
def test_ini_fallback_keeps_broader_values_but_panel_clamps():
    settings = TorpedoSamplingSettings(radius_divisor=1.0,
                                       enemy_high_budget=100)
    stub = StubBinding()
    collector = _collector(
        {'PrefsAdapter': PrefsAdapter,
         'build_ttaro_prefs_binding': lambda: stub,
         'normalize_torpedo_sampling_settings':
             normalize_torpedo_sampling_settings},
        BRIDGE_METHODS)
    collector._torpedoSamplingSettings = settings
    collector._torpedoSamplingSettingsPending = False
    collector._torpedoSamplingRevision = 0
    collector._torpedoPrefsAdapter = None
    collector._torpedoPrefsBinding = None
    collector._torpedoPrefsRevision = 0
    collector._bind_torpedo_prefs_adapter('loadComplete')
    adapter = collector._torpedoPrefsAdapter

    # ini fallback is broader than the panel range and must NOT be folded.
    assert adapter.value('enemy_high_budget') == 100
    assert adapter.value('radius_divisor') == 1.0

    # Panel edits use the UI path and ARE clamped to the safe range.
    stub.emit('enemyHighBudget', 999)
    stub.emit('radiusDivisor', 0.5)
    adapter.tick()
    assert adapter.value('enemy_high_budget') == 64
    assert adapter.value('radius_divisor') == 2.0

    # Invalid panel input keeps the current value.
    stub.emit('enemyHighBudget', True)
    adapter.tick()
    assert adapter.value('enemy_high_budget') == 64


# ------------------------------------------------------ tick gate ordering
def test_tick_runs_consume_then_apply_then_build():
    ns = {'_now': lambda: 1.0,
          '_get': lambda obj, key, default=None: getattr(obj, key, default),
          '_str': str, 'logError': lambda message: None,
          '__builtins__': __builtins__}
    tick = load_main_method('_tick', ns)

    order = []
    collector = Obj(
        _active=True, _collectionEnabled=True, _diagnosticsLastNow=None,
        _diagnostics_due=lambda now: False,
        _torpedo_depth_sampling_due=lambda now: False,
        _torpedo_state_sampling_due=lambda now: False,
        _selfSystemsSamplingEnabled=True,
        _selfSystemsSamplingDue=False,
        _self_systems_sampling_due=lambda now: False,
        _torpedoArmamentSamplingEnabled=True,
        _torpedoArmamentSamplingDue=False,
        _torpedo_armament_sampling_due=lambda now: False,
        _mapCalibrationSnapshotInterval=1.0,
        _mapCalibrationSnapshotDue=False,
        _map_calibration_snapshot_due=lambda now: False,
        _shipWorldPositionSamplingEnabled=True,
        _shipWorldPositionSamplingDue=False,
        _ship_world_position_sampling_due=lambda now: False,
        _refresh_meta=lambda now: None, _performanceProfiler=None,
        _stateInterval=0.2, _lastWrite=0.0, _diagnosticsInterval=1.0,
        _writer=None, _profilerEnabled=False)
    collector._consume_torpedo_prefs = lambda now: order.append(('consume', now))
    collector._apply_pending_torpedo_sampling_settings = (
        lambda now: order.append(('apply', now)))
    collector._build_state = lambda now: order.append(('build', now)) or {
        'active': True}
    collector._write_state = lambda snap: None
    tick(collector)
    assert order == [('consume', 1.0), ('apply', 1.0), ('build', 1.0)]
