"""Offline stub tests for the self-authored TTaro prefs adapter.

Covers the adapter contract only: notification purity, pending/consume,
dedup, strict invalid handling, clamping, unsubscribe lifecycle, registry
rebinding, TTaro-absent ini fallback, and Python 2 grammar safety of the
game module. No game/API calls; the binding is a stub. The tests also pin
the schema <-> adapter contract (keys/defaults/ranges) so DS integration
cannot drift silently.
"""
import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / 'res_mods' / 'PnFMods' / 'WowsExtractor'
SCHEMA_PATH = ROOT / 'res_mods' / 'ModSchemas' / 'kitta-wows-extractor.schema.json'

sys.path.insert(0, str(MODULE_DIR))
import ttaro_prefs_adapter as adapter_module
from ttaro_prefs_adapter import (DEFAULTS, MOD_ADDR, MOD_AUTHOR, MOD_SLUG,
                                 PrefsAdapter, SCHEMA_RELPATH, SETTING_SPECS,
                                 coerce_value, component_key,
                                 fallback_from_config)


class StubBinding(object):
    """Records subscribe/unsubscribe and can emit pure-value events."""

    def __init__(self, initial=None, fail_subscribe=False):
        self.subscribed = []
        self.unsubscribed = []
        self.callbacks = {}
        self.initial = initial or {}
        self.fail_subscribe = fail_subscribe

    def subscribe(self, comp_key, callback):
        if self.fail_subscribe:
            raise RuntimeError('no channel')
        handle = object()
        self.subscribed.append((comp_key, handle))
        self.callbacks[comp_key] = callback
        return handle

    def unsubscribe(self, handle):
        self.unsubscribed.append(handle)

    def read(self, comp_key):
        return self.initial.get(comp_key)

    def emit(self, setting_key, value):
        callback = self.callbacks.get(component_key(setting_key))
        if callback is not None:
            callback(setting_key, value)


def _running(fallback=None, binding=None):
    prefs = PrefsAdapter(binding=binding, fallback=fallback)
    prefs.start()
    return prefs


# ------------------------------------------------------------- notification
def test_notification_records_pending_pure_values_only():
    binding = StubBinding()
    prefs = _running(binding=binding)
    assert prefs.notify('enemyHighBudget', 30) is True
    # Deferred: nothing applied and no revision before the tick consumes.
    assert prefs.values() == dict(DEFAULTS)
    assert prefs.revision() == 0
    # A live-ish object is not a pure value: it must not enter pending.
    assert prefs.notify('enemyHighBudget', object()) is False
    assert prefs.notify('radiusDivisor', {'value': 4}) is False
    rejected = dict(prefs.rejected())
    assert rejected.get('radiusDivisor') == 'nonPureValue'
    applied = prefs.tick()
    assert applied == 1
    assert prefs.value('enemy_high_budget') == 30
    assert prefs.value('radius_divisor') == DEFAULTS['radius_divisor']


def test_subscription_handles_are_kept_across_frames_by_design():
    binding = StubBinding()
    prefs = _running(binding=binding)
    handles_before = prefs.handles()
    assert len(handles_before) == len(SETTING_SPECS)
    prefs.notify('enemyHighBudget', 25)
    prefs.tick()
    # Handles persist across notify/tick frames (unlike telemetry live
    # objects: this is the config subscription and is kept on purpose).
    assert prefs.handles() == handles_before
    assert binding.unsubscribed == []


# -------------------------------------------------------------------- dedup
def test_dedup_identical_value_does_not_bump_revision():
    prefs = _running()
    assert prefs.tick() == 0            # nothing pending
    prefs.notify('enemyHighBudget', DEFAULTS['enemy_high_budget'])
    assert prefs.tick() == 0            # same value: not a change
    assert prefs.revision() == 0
    prefs.notify('enemyHighBudget', 30)
    prefs.notify('enemyHighBudget', 30)  # duplicate notification collapses
    assert prefs.tick() == 1
    assert prefs.revision() == 1
    prefs.notify('enemyHighBudget', 30)  # back to applied value: dedup
    assert prefs.tick() == 0
    assert prefs.revision() == 1


# ------------------------------------------------------------------ pending
def test_pending_latest_value_wins_and_consume_clears():
    prefs = _running()
    prefs.notify('enemyHighBudget', 30)
    prefs.notify('enemyHighBudget', 40)
    assert prefs.tick() == 1            # latest wins, one applied change
    assert prefs.value('enemy_high_budget') == 40
    assert prefs.tick() == 0            # pending consumed and cleared
    assert prefs.revision() == 1


def test_notify_while_stopped_is_ignored():
    binding = StubBinding()
    prefs = _running(binding=binding)
    prefs.stop('battleEnd')
    assert prefs.notify('enemyHighBudget', 30) is False
    assert prefs.tick() == 0
    assert prefs.values() == dict(DEFAULTS)
    assert prefs.status() == 'stopped'


# ------------------------------------------------------------------ invalid
def test_invalid_values_keep_current_value():
    prefs = _running()
    baseline = prefs.values()
    bad_values = [
        ('enemyHighBudget', True),            # strict: bool rejected
        ('enemyHighBudget', 20.5),            # non-integral for int kind
        ('enemyHighBudget', float('nan')),    # non-finite
        ('enemyHighBudget', float('inf')),    # non-finite
        ('enemyHighBudget', 'high'),          # non-numeric
        ('radiusDivisor', False),             # strict: bool rejected
        ('radiusDivisor', float('inf')),
        ('radiusDivisor', '5'),
    ]
    for key, raw in bad_values:
        prefs.notify(key, raw)
        assert prefs.tick() == 0
        assert prefs.values() == baseline
        assert prefs.revision() == 0
    reasons = [reason for (_key, reason) in prefs.rejected()]
    assert 'boolRejected' in reasons
    assert 'nonIntegral' in reasons
    assert 'nonFinite' in reasons
    assert 'nonNumeric' in reasons


def test_unknown_keys_are_rejected():
    prefs = _running()
    assert prefs.notify('collection_enabled', True) is False
    assert prefs.tick() == 0
    assert ('collection_enabled', 'unknownKey') in prefs.rejected()
    assert prefs.values() == dict(DEFAULTS)


def test_out_of_range_numbers_clamp_to_schema_safe_range():
    prefs = _running()
    prefs.notify('enemyHighBudget', 999)
    prefs.tick()
    assert prefs.value('enemy_high_budget') == 64
    prefs.notify('enemyHighBudget', -5)
    prefs.tick()
    assert prefs.value('enemy_high_budget') == 1
    prefs.notify('radiusDivisor', 1000.0)
    prefs.tick()
    assert prefs.value('radius_divisor') == 10.0
    prefs.notify('radiusDivisor', 0.5)
    prefs.tick()
    assert prefs.value('radius_divisor') == 2.0


def test_coerce_value_contract():
    assert coerce_value('enemyHighBudget', 20) == (True, 20, None)
    assert coerce_value('enemyHighBudget', 20.0) == (True, 20, None)
    ok, _value, reason = coerce_value('enemyHighBudget', True)
    assert (ok, reason) == (False, 'boolRejected')
    ok, _value, reason = coerce_value('nope', 1)
    assert (ok, reason) == (False, 'unknownKey')
    ok, value, reason = coerce_value('radiusDivisor', 4)
    assert (ok, value, reason) == (True, 4.0, None)


# -------------------------------------------------------------- unsubscribe
def test_unsubscribe_releases_each_handle_once_on_battle_end_and_unload():
    binding = StubBinding()
    prefs = _running(binding=binding)
    assert len(binding.subscribed) == len(SETTING_SPECS)
    released = prefs.stop('battleEnd')
    assert released == len(SETTING_SPECS)
    assert len(binding.unsubscribed) == len(SETTING_SPECS)
    assert prefs.stop('battleEnd') == 0     # idempotent: nothing double-frees
    assert len(binding.unsubscribed) == len(SETTING_SPECS)
    # Next battle resubscribes, mod unload releases again exactly once.
    prefs.start()
    assert len(binding.subscribed) == 2 * len(SETTING_SPECS)
    assert prefs.stop('modUnload') == len(SETTING_SPECS)
    assert len(binding.unsubscribed) == 2 * len(SETTING_SPECS)


def test_rebind_releases_stale_handles_and_resubscribes():
    first = StubBinding()
    prefs = _running(binding=first)
    stale_handles = [handle for (_key, handle) in prefs.handles()]
    second = StubBinding()
    prefs.rebind(second)
    assert sorted(map(id, first.unsubscribed)) == sorted(map(id, stale_handles))
    assert len(second.subscribed) == len(SETTING_SPECS)
    # Notifications through the rebound registry still reach the adapter.
    second.emit('enemyHighBudget', 33)
    assert prefs.tick() == 1
    assert prefs.value('enemy_high_budget') == 33
    prefs.stop('modUnload')
    assert len(second.unsubscribed) == len(SETTING_SPECS)
    # A failed resubscribe is survivable and tracked as a null handle.
    third = StubBinding(fail_subscribe=True)
    prefs.rebind(third)
    prefs.start()
    assert prefs.handles() != []
    assert prefs.stop('modUnload') == 0     # null handles never release


# ------------------------------------------------------------------ absent
def test_absent_falls_back_to_ini_values():
    fallback = fallback_from_config(
        {'enemy_high_budget': 30, 'radius_divisor': 4,
         'collection_enabled': 'true'})
    prefs = PrefsAdapter(binding=None, fallback=fallback)
    assert prefs.start() == 'ini'
    assert prefs.source() == 'ini'
    assert prefs.value('enemy_high_budget') == 30
    assert prefs.value('radius_divisor') == 4.0
    # Unrelated ini keys are not imported into the contract.
    assert 'collection_enabled' not in prefs.values()


def test_absent_without_fallback_stays_on_defaults():
    prefs = PrefsAdapter(binding=None, fallback=None)
    assert prefs.start() == 'none'
    assert prefs.source() == 'none'
    assert prefs.values() == dict(DEFAULTS)


def test_absent_with_invalid_fallback_keeps_defaults():
    fallback = {'enemy_high_budget': True, 'radius_divisor': float('nan')}
    prefs = PrefsAdapter(binding=None, fallback=fallback)
    assert prefs.start() == 'none'
    assert prefs.values() == dict(DEFAULTS)


def test_ini_fallback_superseded_by_framework_values():
    binding = StubBinding()
    fallback = fallback_from_config({'enemy_high_budget': 12})
    prefs = PrefsAdapter(binding=binding, fallback=fallback)
    prefs.start()
    assert prefs.value('enemy_high_budget') == 12
    assert prefs.source() == 'ini'
    binding.emit('enemyHighBudget', 44)
    prefs.tick()
    assert prefs.value('enemy_high_budget') == 44
    assert prefs.source() == 'ttaro'


def test_binding_initial_read_is_pending_only():
    binding = StubBinding(
        initial={component_key('enemyHighBudget'): 27})
    prefs = PrefsAdapter(binding=binding)
    prefs.start()
    # The initial read is a pending pure value: applied at the first tick.
    assert prefs.values() == dict(DEFAULTS)
    assert prefs.tick() == 1
    assert prefs.value('enemy_high_budget') == 27


# ------------------------------------------------------- Python 2 grammar
def _adapter_source():
    return (MODULE_DIR / 'ttaro_prefs_adapter.py').read_text(encoding='ascii')


def test_game_module_is_ascii_and_declares_coding():
    source = _adapter_source()
    first_line = source.splitlines()[0]
    assert first_line == '# -*- coding: utf-8 -*-'


def test_game_module_parses_as_python2_grammar():
    source = _adapter_source()
    compile(source, 'ttaro_prefs_adapter.py', 'exec')   # valid Python 3
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    for token in tokens:
        if token.type == tokenize.STRING:
            prefix = token.string.split("'", 1)[0].split('"', 1)[0].lower()
            assert 'f' not in prefix, 'f-string is Python 3 only'
        elif token.type == tokenize.OP:
            assert token.string not in ('->', ':='), 'Python 3 only syntax'
        elif token.type == tokenize.NAME:
            assert token.string not in ('async', 'await', 'nonlocal',
                                        'print'), 'Python 2 incompatible'
    try:
        from lib2to3 import refactor
    except ImportError:
        return  # lib2to3 is gone on Python 3.13+: token scan above still ran
    tool = refactor.RefactoringTool([])
    tool.refactor_string(source + '\n', 'ttaro_prefs_adapter.py')


def test_python2_names_path_executes():
    # Execute the module with Python 2 builtin names present so the guarded
    # (int, long, float) branch is the one under test.
    source = _adapter_source()
    namespace = {'long': int, 'unicode': str, 'basestring': str}
    exec(compile(source, 'ttaro_prefs_adapter.py', 'exec'), namespace)
    assert namespace['_NUMBER_TYPES'] == (int, int, float)
    assert namespace['_INT_TYPES'] == (int, int)
    ok, value, reason = namespace['coerce_value']('radiusDivisor', 3)
    assert (ok, value, reason) == (True, 3.0, None)


# ----------------------------------------------------- schema contract
def _schema():
    return json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))


def _walk_settings(nodes):
    for node in nodes:
        if node.get('kind') == 'setting':
            yield node
        for child in node.get('children') or []:
            for setting in _walk_settings([child]):
                yield setting


def test_schema_registers_mod_identity_with_unique_self_authored_fields():
    data = _schema()
    assert data['schemaVersion'] >= 4
    assert data['author'] == MOD_AUTHOR == 'kitta'
    assert data['modName'] == 'WowsExtractor'
    assert data['slug'] == MOD_SLUG == 'wows-extractor'
    assert MOD_ADDR == 'kitta.wows-extractor'
    # scanner rules: plain id without path chars; slug without dots
    mod_id = data['id']
    assert isinstance(mod_id, str) and mod_id
    assert not any(ch in mod_id for ch in ('/', '\\', ':', '..'))
    assert '.' not in data['slug']
    # author charset: lowercase alphanumeric, starts with a letter,
    # not a reserved DataHub name.
    assert re.match(r'^[a-z][a-z0-9]*$', data['author'])
    assert data['author'] not in ('registry', 'installedMods', 'framework',
                                  'uiState', 'dragState')
    assert SCHEMA_RELPATH == 'res_mods/ModSchemas/kitta-wows-extractor.schema.json'
    assert SCHEMA_PATH.name == 'kitta-wows-extractor.schema.json'
    assert adapter_module.SCHEMA_FILE == SCHEMA_PATH.name


def test_schema_settings_match_adapter_contract():
    data = _schema()
    settings = list(_walk_settings(data['tree']))
    keys = sorted(setting['key'] for setting in settings)
    assert keys == sorted(spec['key'] for spec in SETTING_SPECS)
    for setting in settings:
        spec = next(s for s in SETTING_SPECS if s['key'] == setting['key'])
        assert setting['control'] == 'slider'
        assert setting['default'] == spec['default']
        assert setting['min'] == spec['min']
        assert setting['max'] == spec['max']
        assert setting['min'] <= setting['default'] <= setting['max']
        assert 'step' in setting and 'decimals' in setting
        if spec['kind'] == 'int':
            assert setting['decimals'] == 0
        # prefix-collision guard (scanner refuses key prefixes):
        for other in settings:
            assert not other['key'].startswith(setting['key'] + '.')


def test_defaults_and_component_keys_shape():
    assert DEFAULTS == {'enemy_high_budget': 20, 'radius_divisor': 5.0}
    assert component_key('enemyHighBudget') == 'modPrefs.kitta.enemyHighBudget'
    assert component_key('radiusDivisor') == 'modPrefs.kitta.radiusDivisor'
