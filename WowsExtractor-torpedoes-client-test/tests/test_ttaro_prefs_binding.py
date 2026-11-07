"""Offline tests for the self-authored TTaro prefs binding bridge.

Covers the adapter binding contract (subscribe/unsubscribe/read), the pure
event path, the provider seam, the default dataHub resolver (indexed lookup,
never a full enumeration) and Python 2 grammar safety. No game/API calls: the
dataHub is a stub installed on the module globals.
"""
import io
import os
import sys
import tokenize
from pathlib import Path
from types import SimpleNamespace as Obj

MODULE_DIR = (Path(__file__).resolve().parents[1] /
              'res_mods' / 'PnFMods' / 'WowsExtractor')
sys.path.insert(0, str(MODULE_DIR))

import ttaro_prefs_binding as binding_module  # noqa: E402
from ttaro_prefs_adapter import DEFAULTS, PrefsAdapter, component_key  # noqa: E402
from ttaro_prefs_binding import (ComponentBinding, build_binding,  # noqa: E402
                                 get_binding_provider, make_default_resolver,
                                 set_binding_provider,
                                 setting_key_from_component)


class Event(object):
    def __init__(self):
        self.handlers = []

    def add(self, handler):
        self.handlers.append(handler)

    def remove(self, handler):
        self.handlers.remove(handler)

    def fire(self):
        for handler in list(self.handlers):
            handler()


class Component(object):
    def __init__(self, value):
        self.data = {'value': value, 'visible': True}
        self.evDataChanged = Event()


class StubBinding(object):
    def __init__(self):
        self.subscribed = []
        self.unsubscribed = []
        self.callbacks = {}

    def subscribe(self, comp_key, callback):
        handle = object()
        self.subscribed.append((comp_key, handle))
        self.callbacks[comp_key] = callback
        return handle

    def unsubscribe(self, handle):
        self.unsubscribed.append(handle)

    def read(self, comp_key):
        return None

    def emit(self, setting_key, value):
        callback = self.callbacks.get(component_key(setting_key))
        if callback is not None:
            callback(setting_key, value)


class FakeHub(object):
    def __init__(self, entities=None):
        self.entities = dict(entities or {})
        self.index_calls = []

    def getEntityByIndex(self, key, component_id):
        self.index_calls.append((key, component_id))
        return self.entities.get(key)


def _install_fake_hub(monkeypatch, entities):
    hub = FakeHub(entities)
    constants = Obj(UiComponents=Obj(userPrefs='userPrefs',
                                     mods_DataComponent='mods_DataComponent'))
    holder = Obj(entity=Obj(_Entity__hub=hub))

    class UserPrefsEntity(object):
        def __getitem__(self, key):
            return holder

    data_hub = Obj(getSingleEntity=lambda name: UserPrefsEntity())
    monkeypatch.setattr(binding_module, 'dataHub', data_hub)
    monkeypatch.setattr(binding_module, 'constants', constants)
    return hub


# -------------------------------------------------------------- key mapping
def test_setting_key_from_component_reverses_the_adapter_format():
    assert setting_key_from_component(
        component_key('enemyHighBudget')) == 'enemyHighBudget'
    assert setting_key_from_component(
        component_key('radiusDivisor')) == 'radiusDivisor'
    assert setting_key_from_component('modPrefs.kitta.enemyHighBudget') == \
        'enemyHighBudget'
    assert setting_key_from_component('bareKey') == 'bareKey'
    assert setting_key_from_component('') is None
    assert setting_key_from_component(None) is None
    assert setting_key_from_component(5) is None


# ---------------------------------------------------------- component binding
def test_component_binding_pushes_pure_values_and_releases_once():
    component = Component(30)
    components = {component_key('enemyHighBudget'): component}
    binding = ComponentBinding(resolver=lambda key: components.get(key))
    seen = []
    handle = binding.subscribe(
        component_key('enemyHighBudget'),
        lambda key, value: seen.append((key, value)))
    assert handle is not None
    assert binding.read(component_key('enemyHighBudget')) == 30

    component.data['value'] = 40
    component.evDataChanged.fire()
    assert seen == [('enemyHighBudget', 40)]

    binding.unsubscribe(handle)
    component.evDataChanged.fire()
    assert seen == [('enemyHighBudget', 40)]      # released: no further push
    assert component.evDataChanged.handlers == []
    binding.unsubscribe(handle)                    # idempotent
    assert component.evDataChanged.handlers == []


def test_component_binding_is_defensive_about_bad_components():
    binding = ComponentBinding(resolver=lambda key: None)
    assert binding.subscribe(component_key('enemyHighBudget'),
                             lambda *a: None) is None
    assert binding.read(component_key('enemyHighBudget')) is None
    binding.unsubscribe(None)
    binding.unsubscribe('not-a-handle')

    class NoEvent(object):
        data = {'value': 1}
    quiet = ComponentBinding(
        resolver=lambda key: NoEvent())
    assert quiet.subscribe(component_key('enemyHighBudget'),
                           lambda *a: None) is None


def test_component_binding_swallows_a_raising_callback():
    component = Component(1)
    binding = ComponentBinding(resolver=lambda key: component)
    binding.subscribe(component_key('enemyHighBudget'),
                      lambda key, value: (_ for _ in ()).throw(RuntimeError()))
    component.evDataChanged.fire()   # must not propagate


# --------------------------------------------------------------- provider seam
def test_build_binding_returns_none_without_provider_or_resolver(monkeypatch):
    monkeypatch.setattr(binding_module, '_PROVIDER', None)
    monkeypatch.setattr(binding_module, 'dataHub', None)
    monkeypatch.setattr(binding_module, 'constants', None)
    assert build_binding() is None


def test_build_binding_prefers_the_provider_and_can_be_cleared():
    sentinel = object()
    set_binding_provider(lambda: sentinel)
    try:
        assert build_binding() is sentinel
        assert get_binding_provider() is not None
    finally:
        set_binding_provider(None)
    assert get_binding_provider() is None


def test_build_binding_wraps_an_explicit_resolver():
    binding = build_binding(resolver=lambda key: None)
    assert isinstance(binding, ComponentBinding)


# ------------------------------------------------------- default dataHub path
def test_default_resolver_uses_indexed_lookup_not_enumeration(monkeypatch):
    enemy = Component(20)
    hub = _install_fake_hub(monkeypatch, {
        component_key('enemyHighBudget'):
            Obj(mods_DataComponent=enemy)})
    resolver = make_default_resolver()
    assert resolver is not None
    assert resolver(component_key('enemyHighBudget')) is enemy
    # One indexed lookup for the requested key; no list/collection walk.
    assert hub.index_calls == [
        (component_key('enemyHighBudget'), 'mods_DataComponent')]


def test_default_resolver_is_absent_without_the_game_modules(monkeypatch):
    monkeypatch.setattr(binding_module, 'dataHub', None)
    monkeypatch.setattr(binding_module, 'constants', None)
    assert make_default_resolver() is None


# ------------------------------------------------------- adapter integration
def test_adapter_with_binding_module_applies_framework_values(monkeypatch):
    enemy = Component(30)
    radius = Component(4.0)
    _install_fake_hub(monkeypatch, {
        component_key('enemyHighBudget'): Obj(mods_DataComponent=enemy),
        component_key('radiusDivisor'): Obj(mods_DataComponent=radius)})
    binding = build_binding()
    prefs = PrefsAdapter(binding=binding)
    assert prefs.start() == 'none'
    # Initial reads are queued as pending only; the first tick applies them.
    assert prefs.tick() == 2
    assert prefs.value('enemy_high_budget') == 30
    assert prefs.value('radius_divisor') == 4.0
    enemy.data['value'] = 27
    enemy.evDataChanged.fire()
    assert prefs.tick() == 1
    assert prefs.value('enemy_high_budget') == 27
    assert prefs.source() == 'ttaro'


# ------------------------------------------------------------ Python 2 grammar
def _source():
    return (MODULE_DIR / 'ttaro_prefs_binding.py').read_text(encoding='ascii')


def test_binding_module_is_ascii_and_declares_coding():
    assert _source().splitlines()[0] == '# -*- coding: utf-8 -*-'


def test_binding_module_parses_as_python2_grammar():
    source = _source()
    compile(source, 'ttaro_prefs_binding.py', 'exec')
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
        return
    refactor.RefactoringTool([]).refactor_string(
        source + '\n', 'ttaro_prefs_binding.py')
