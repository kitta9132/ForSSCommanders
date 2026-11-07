# -*- coding: utf-8 -*-
# MIT License
# Copyright (c) 2026 Tz-WIND/Lex_q
#
# SPDX-License-Identifier: MIT
"""Optional bridge from the game's TTaro Mod Config surface to the
WowsExtractor prefs adapter binding contract (self-authored).

This module is deliberately independent of the third-party TTaro sources. It
never imports or copies TTaroModUtils / ModForge code; it only consumes the
same documented surface the framework publishes to every consumer:

  * one dataHub component per setting, addressed under
    ``constants.UiComponents.mods_DataComponent`` with the key
    ``modPrefs.<author>.<settingKey>`` (the adapter's ``component_key``);
  * the component exposes ``data`` (a mapping that carries a ``value`` field)
    and an ``evDataChanged`` event with ``add(fn)`` / ``remove(fn)``.

How a component handle is obtained is game-build specific and stays OUTSIDE
this module: it is passed in as a ``resolver`` callable, so offline tests can
inject stubs and the game wiring can be reconciled with the final adapter
contract without ever touching the adapter itself.

``PrefsAdapter`` only ever sees a plain binding object with::

    subscribe(component_key, callback) -> handle or None
    unsubscribe(handle)                -> None
    read(component_key) -> raw value or None

Event handlers capture PURE SCALAR VALUES ONLY: they read the current value and
forward it, never retaining a component and never mutating applied state. The
adapter validates the value later in its own ``tick``.

When no resolver/provider is available (framework absent) ``build_binding``
returns ``None`` and the adapter stays on its config.ini fallback: nothing else
changes (absence fallback).

Targets the game's embedded Python 2 runtime and stays valid Python 3 for the
offline test suite (no f-strings, no annotations, ASCII only).
"""

# The adapter is the single source of truth for the component-key format. The
# import is guarded so this module also runs standalone in offline harnesses.
try:
    from ttaro_prefs_adapter import COMPONENT_PREFIX
except Exception:
    COMPONENT_PREFIX = 'modPrefs.'

try:
    _STRING_TYPES = (str, unicode)   # Python 2 game runtime
except NameError:
    _STRING_TYPES = (str,)           # Python 3 offline tests

# Standard ModsAPI modules. Import is best-effort: offline harnesses have no
# game and simply get no default resolver (absence fallback).
try:
    import dataHub
except Exception:
    dataHub = None

try:
    import constants
except Exception:
    constants = None


def setting_key_from_component(component_key_value):
    """Reverse the adapter's component-key format back to a schema key.

    ``modPrefs.kitta.enemyHighBudget`` -> ``enemyHighBudget``. Only the last
    dot-separated segment is the schema key (the schema scanner refuses key
    prefixes, so a schema key itself contains no dot). Returns None for a
    non-string or empty input so the caller can skip the subscription.
    """
    if not isinstance(component_key_value, _STRING_TYPES):
        return None
    text = component_key_value
    prefix = COMPONENT_PREFIX
    if prefix and text.startswith(prefix):
        text = text[len(prefix):]
    if not text:
        return None
    if '.' not in text:
        return text
    return text.rsplit('.', 1)[-1]


def _read_value(component):
    """Read the published ``value`` from a component, never raising."""
    if component is None:
        return None
    data = getattr(component, 'data', None)
    if data is None:
        return None
    try:
        if 'value' in data:
            return data['value']
    except Exception:
        return None
    return None


class ComponentBinding(object):
    """Adapter binding backed by live dataHub components.

    ``resolver(component_key) -> component or None``. Only the documented
    ``data`` / ``evDataChanged`` fields are touched. A subscription handle is a
    ``(component, handler)`` pair so it can be released exactly once.
    """

    def __init__(self, resolver=None, log=None):
        self._resolver = resolver
        self._log = log
        self._handles = []

    def _component(self, component_key_value):
        resolver = self._resolver
        if resolver is None:
            return None
        try:
            return resolver(component_key_value)
        except Exception:
            return None

    def subscribe(self, component_key_value, callback):
        """Register ``callback(setting_key, value)`` for a component's changes."""
        component = self._component(component_key_value)
        if component is None:
            return None
        event = getattr(component, 'evDataChanged', None)
        add = getattr(event, 'add', None)
        if not callable(add):
            return None
        setting_key = setting_key_from_component(component_key_value)
        if setting_key is None:
            return None

        def handler(*_args):
            # Pure-scalar push: forward the current scalar, swallow any error.
            try:
                callback(setting_key, _read_value(component))
            except Exception:
                pass

        try:
            add(handler)
        except Exception:
            return None
        handle = (component, handler)
        self._handles.append(handle)
        return handle

    def unsubscribe(self, handle):
        """Release one subscription handle; safe for a null/foreign handle."""
        if handle is None:
            return
        try:
            component, handler = handle
        except Exception:
            return
        event = getattr(component, 'evDataChanged', None)
        remove = getattr(event, 'remove', None)
        if callable(remove):
            try:
                remove(handler)
            except Exception:
                pass
        try:
            self._handles.remove(handle)
        except ValueError:
            pass

    def read(self, component_key_value):
        """Current scalar value for a component, or None when unavailable."""
        return _read_value(self._component(component_key_value))

    def handles(self):
        return list(self._handles)


# -- default game resolver ---------------------------------------------------
def _resolve_component_hub():
    """Locate the dataHub component hub once, using the standard read surface.

    Returns the hub object that exposes ``getEntityByIndex(key, componentId)``,
    or None when the game modules are unavailable. The accessor name on the
    entity object is name-mangled by the engine, so a few spellings are tried.
    """
    hub_mod = dataHub
    cc = getattr(constants, 'UiComponents', None)
    if hub_mod is None or cc is None:
        return None
    user_prefs = getattr(cc, 'userPrefs', None)
    if user_prefs is None:
        return None
    try:
        entity = hub_mod.getSingleEntity('userPrefs')
    except Exception:
        return None
    if entity is None:
        return None
    try:
        component = entity[user_prefs]
    except Exception:
        component = None
    candidates = (component, entity)
    for candidate in candidates:
        if candidate is None:
            continue
        sub = getattr(candidate, 'entity', candidate)
        for attr in ('_Entity__hub', '__hub', 'hub'):
            hub = getattr(sub, attr, None)
            if hub is None and sub is not candidate:
                hub = getattr(candidate, attr, None)
            if hub is not None and callable(
                    getattr(hub, 'getEntityByIndex', None)):
                return hub
    return None


def make_default_resolver():
    """Build a component resolver from the live dataHub, or None when absent.

    The returned callable maps an adapter component key
    (``modPrefs.kitta.<settingKey>``) to the published component. It is a
    single indexed lookup per key, never a full enumeration of settings.
    """
    hub = _resolve_component_hub()
    if hub is None:
        return None
    cc = getattr(constants, 'UiComponents', None)
    component_id = getattr(cc, 'mods_DataComponent', None)
    getter = getattr(hub, 'getEntityByIndex', None)
    if not callable(getter) or component_id is None:
        return None

    def resolve(component_key_value):
        try:
            entity = getter(component_key_value, component_id)
        except Exception:
            return None
        if entity is None:
            return None
        try:
            return entity.mods_DataComponent
        except Exception:
            return None

    return resolve


# -- provider seam -----------------------------------------------------------
# The game wiring (final adapter contract) installs a provider that returns a
# ready binding. No provider -> no binding -> the adapter stays on config.ini.
_PROVIDER = None


def set_binding_provider(provider):
    """Install (or clear with None) the process-wide binding provider."""
    global _PROVIDER
    _PROVIDER = provider


def get_binding_provider():
    return _PROVIDER


def build_binding(resolver=None, provider=None):
    """Return a binding for the adapter, or None when the framework is absent.

    Order: an explicit ``provider`` argument, then the installed provider, then
    a ``resolver`` wrapped in ``ComponentBinding``. Any failure yields None so
    the caller falls back to config.ini (absence fallback).
    """
    source = provider if provider is not None else _PROVIDER
    if callable(source):
        try:
            binding = source()
        except Exception:
            binding = None
        if binding is not None:
            return binding
    if resolver is None:
        resolver = make_default_resolver()
    if resolver is None:
        return None
    return ComponentBinding(resolver)
