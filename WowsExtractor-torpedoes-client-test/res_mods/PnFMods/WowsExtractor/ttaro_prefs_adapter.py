# -*- coding: utf-8 -*-
"""Optional TTaro Mod Config prefs adapter for WowsExtractor (self-authored).

Written from scratch for this mod (kitta). It does not import, wrap or copy
TTaroModUtils / ModForge code (no license grant was found for those third
party sources; see docs/DESIGN_TTARO_PREFS_ADAPTER.ja.md). It only speaks to
the framework through the standard dataHub surface that the framework
publishes: per-key ``mods_DataComponent`` entries named ``modPrefs.<key>``
with ``evDataChanged`` notification, subscribed through an injected binding
object so offline tests can stub the game entirely.

Design rules (contract, do not weaken):

* Event callbacks capture PURE SCALAR VALUES ONLY. They never touch the UI,
  never hold API objects and never mutate applied state. They may only record
  pending values (latest value wins per key).
* Applied state changes only inside ``tick()`` (``consume_pending``), so the
  collector observes settings at a stable point in its own frame. ``revision``
  increments once per tick that applied at least one change.
* Validation is strict: unknown keys are rejected; booleans, non-numbers and
  non-finite numbers are invalid and KEEP THE CURRENT VALUE; finite numbers
  are clamped to the schema safe range. Invalid input never reaches state.
* Subscription handles are held ACROSS FRAMES by design. This is the config
  surface and is intentionally different from the telemetry live-object
  prohibition (torpedo_telemetry keeps no API objects between frames). Every
  handle is tracked explicitly and released exactly once on mod unload or
  battle end (``stop``), and re-acquired on registry rebinding (``rebind``).
* The dependency is optional: without the framework (or without a binding)
  the adapter falls back to the config.ini values it was given and reports
  ``source() == 'ini'``. Nothing else changes.

This module targets the game's embedded Python 2 runtime and stays valid
Python 3 for the offline test suite (no f-strings, no annotations, ASCII).
"""

# ---------------------------------------------------------------- identity
MOD_AUTHOR = 'kitta'
MOD_SLUG = 'wows-extractor'
MOD_ADDR = MOD_AUTHOR + '.' + MOD_SLUG
SCHEMA_FILE = 'kitta-wows-extractor.schema.json'
SCHEMA_RELPATH = 'res_mods/ModSchemas/' + SCHEMA_FILE
COMPONENT_PREFIX = 'modPrefs.'

# ---------------------------------------------------------- setting contract
# Single source of truth for shape keys / defaults / safe ranges. The schema
# file (SCHEMA_RELPATH) and the collector contract keys must agree with this
# table; the offline tests enforce that. Only NEW settings are listed here:
# pre-existing config.ini keys are deliberately not exposed in the panel yet.
#
# kind 'int'   : integral numbers only (integral floats are converted,
#                fractional floats are invalid -> keep current value).
# kind 'float' : finite numbers.
SETTING_SPECS = (
    {
        'key': 'enemyHighBudget',          # schema / hub key (kitta.enemyHighBudget)
        'contractKey': 'enemy_high_budget',  # collector + config.ini key
        'kind': 'int',
        'default': 20,
        'min': 1,
        'max': 64,
    },
    {
        'key': 'radiusDivisor',
        'contractKey': 'radius_divisor',
        'kind': 'float',
        'default': 5.0,
        'min': 2.0,
        'max': 10.0,
    },
)

SPEC_BY_KEY = dict((s['key'], s) for s in SETTING_SPECS)
SPEC_BY_CONTRACT = dict((s['contractKey'], s) for s in SETTING_SPECS)
DEFAULTS = dict((s['contractKey'], s['default']) for s in SETTING_SPECS)


def component_key(setting_key):
    """DataHub/ui component name the framework publishes this setting under."""
    return COMPONENT_PREFIX + MOD_AUTHOR + '.' + setting_key


# ------------------------------------------------------------- number types
try:
    _NUMBER_TYPES = (int, long, float)   # Python 2 game runtime
    _INT_TYPES = (int, long)
    _STRING_TYPES = (str, unicode)
except NameError:                        # Python 3 offline tests
    _NUMBER_TYPES = (int, float)
    _INT_TYPES = (int,)
    _STRING_TYPES = (str,)


def _is_finite(number):
    return (number == number and
            number != float('inf') and
            number != -float('inf'))


def _is_pure_scalar(value):
    """Pure plain data only: bool / number / string. No containers, no objects.

    This is the purity gate for event callbacks: pending may only ever hold
    values like these, never a dict/list or a live game/API object.
    """
    return (isinstance(value, bool) or
            isinstance(value, _NUMBER_TYPES) or
            isinstance(value, _STRING_TYPES))


def coerce_value(setting_key, value, clamp=True):
    """Strictly validate one raw value.

    Returns (ok, coerced_value, reason). ``reason`` is None on success and a
    short machine token on rejection ('unknownKey', 'boolRejected',
    'nonNumeric', 'nonFinite', 'nonIntegral'). Rejected values must not be
    applied: the caller keeps the current value.

    ``clamp`` controls only the finite-number range fold. UI input uses
    ``clamp=True`` (the panel safe range). The config.ini fallback uses
    ``clamp=False`` so a broader ini value is never silently rewritten to the
    narrower panel range; it is still rejected when it is not a valid number.
    """
    spec = SPEC_BY_KEY.get(setting_key)
    if spec is None:
        return False, None, 'unknownKey'
    if isinstance(value, bool):
        return False, None, 'boolRejected'
    if not isinstance(value, _NUMBER_TYPES):
        return False, None, 'nonNumeric'
    number = float(value)
    if not _is_finite(number):
        return False, None, 'nonFinite'
    if spec['kind'] == 'int':
        if not isinstance(value, _INT_TYPES) and number != int(number):
            return False, None, 'nonIntegral'
    if clamp:
        if number < spec['min']:
            number = float(spec['min'])
        elif number > spec['max']:
            number = float(spec['max'])
    if spec['kind'] == 'int':
        return True, int(number), None
    return True, number, None


def fallback_from_config(config):
    """Map a parsed config.ini dict onto contract keys (ini fallback values).

    Unknown / missing keys simply keep defaults; values are NOT validated
    here, the adapter validates them strictly on ingest like any other input.
    """
    out = {}
    if not isinstance(config, dict):
        return out
    for spec in SETTING_SPECS:
        if spec['contractKey'] in config:
            out[spec['contractKey']] = config[spec['contractKey']]
    return out


class PrefsAdapter(object):
    """Optional settings adapter: TTaro Mod Config -> collector contract.

    Lifecycle::

        adapter = PrefsAdapter(binding, fallback)
        adapter.start()          # subscribe handles (or fall back to ini)
        ...
        adapter.tick()           # once per collector tick: consume pending
        values = adapter.values()
        ...
        adapter.stop('battleEnd')   # or 'modUnload': release handles once
        adapter.start()             # next battle: resubscribe

    ``binding`` is any object with::

        subscribe(component_key, callback) -> handle or None
        unsubscribe(handle)                -> None
        read(component_key) -> raw value   # optional; may be absent/None

    ``callback`` receives ``(setting_key, pure_value)``. The adapter's
    ``notify`` is the callback target and is also safe to call directly from
    a tick path (e.g. ini reload). ``log`` is an optional callable(str).
    """

    def __init__(self, binding=None, fallback=None, log=None):
        self._binding = None
        self._log = log
        self._values = dict(DEFAULTS)
        self._pending = {}
        self._revision = 0
        self._source = 'none'
        self._status = 'stopped'
        self._handles = []          # [(setting_key, handle)]; explicit list
        self._rejected = []         # bounded [(setting_key, reason)]
        self._fallback = {}
        if isinstance(fallback, dict):
            for spec in SETTING_SPECS:
                raw = fallback.get(spec['contractKey'])
                if raw is None:
                    continue
                # Fallback is the broader config.ini source: validate strictly
                # but never fold it into the narrower panel range.
                ok, value, _reason = coerce_value(spec['key'], raw, clamp=False)
                if ok:
                    self._fallback[spec['contractKey']] = value
        self._binding = binding

    # -- reporting ---------------------------------------------------------
    def values(self):
        """Applied settings as {contractKey: value} (copy)."""
        return dict(self._values)

    def value(self, contract_key):
        return self._values.get(contract_key)

    def revision(self):
        return self._revision

    def source(self):
        """'ttaro' (framework values seen), 'ini' (fallback) or 'none'."""
        return self._source

    def status(self):
        return self._status

    def rejected(self):
        """Bounded list of (setting_key, reason) for diagnostics."""
        return list(self._rejected)

    def handles(self):
        """Current subscription handles as (setting_key, handle) pairs."""
        return list(self._handles)

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        """Subscribe (when a binding exists) and seed from ini fallback.

        Returns the resulting source token. Idempotent while running: a
        second ``start()`` does not double-subscribe.
        """
        if self._status == 'running':
            return self._source
        self._status = 'running'
        for spec in SETTING_SPECS:
            contract = spec['contractKey']
            if contract in self._fallback:
                self._values[contract] = self._fallback[contract]
                self._source = 'ini'
        binding = self._binding
        if binding is not None:
            for spec in SETTING_SPECS:
                self._subscribe_one(binding, spec)
        return self._source

    def _subscribe_one(self, binding, spec):
        key = spec['key']
        handle = None
        try:
            handle = binding.subscribe(component_key(key), self.notify)
        except Exception:
            handle = None
        self._handles.append((key, handle))
        # Optional initial read: pending only, applied on the next tick.
        read = getattr(binding, 'read', None)
        if callable(read):
            try:
                raw = read(component_key(key))
            except Exception:
                raw = None
            if raw is not None:
                self.notify(key, raw)

    def stop(self, reason=None):
        """Release every subscription handle exactly once.

        Called on battle end and on mod unload. Pending values are dropped;
        applied values stay for the lifetime of the process. Idempotent.
        Returns the number of handles released.
        """
        self._status = 'stopped'
        self._pending = {}
        return self._unsubscribe_all()

    def _unsubscribe_all(self):
        binding = self._binding
        released = 0
        seen = set()
        handles = self._handles
        self._handles = []
        for (_key, handle) in handles:
            if handle is None:
                continue
            marker = id(handle)
            if marker in seen:      # shared handle objects release once
                continue
            seen.add(marker)
            released += 1
            if binding is None:
                continue
            unsubscribe = getattr(binding, 'unsubscribe', None)
            if not callable(unsubscribe):
                continue
            try:
                unsubscribe(handle)
            except Exception:
                pass
        return released

    def rebind(self, binding=None):
        """Registry rebinding: drop stale handles, resubscribe.

        The framework recreates its dataHub components on reload/rebind, so
        old handles may reference dead components. Safe to call at any time,
        including while stopped (then it only swaps the binding).
        """
        self._unsubscribe_all()
        if binding is not None:
            self._binding = binding
        if self._status == 'running':
            current = self._binding
            if current is not None:
                for spec in SETTING_SPECS:
                    self._subscribe_one(current, spec)

    # -- event path (pure values only) ------------------------------------
    def notify(self, key, value):
        """Event callback target. Records pending PURE SCALARS only.

        No UI access, no applied-state mutation, no API object retention:
        containers and game objects are rejected right here so the pending
        buffer can never hold anything but plain data. Type/finite/range
        validation happens later in ``tick``; invalid values keep the
        current value there.
        """
        if self._status != 'running':
            return False
        if key not in SPEC_BY_KEY:
            self._record_rejected(key, 'unknownKey')
            return False
        if not _is_pure_scalar(value):
            self._record_rejected(key, 'nonPureValue')
            return False
        self._pending[key] = value
        return True

    def notify_many(self, values):
        """Convenience for batched pure-value notifications (dict)."""
        if not isinstance(values, dict):
            return 0
        count = 0
        for key in values:
            if self.notify(key, values[key]):
                count += 1
        return count

    def _record_rejected(self, key, reason):
        self._rejected.append((key, reason))
        if len(self._rejected) > 32:
            del self._rejected[:-32]

    # -- tick path (consume_pending / revision) ---------------------------
    def tick(self):
        """Consume pending values, apply valid ones, bump revision once.

        Returns the number of applied changes in this tick (0 when nothing
        pending or everything invalid/identical). Call once per collector
        tick; state never changes outside this method.
        """
        if self._status != 'running':
            return 0
        pending = self._pending
        self._pending = {}
        applied = 0
        for key in sorted(pending.keys()):
            ok, value, reason = coerce_value(key, pending[key])
            if not ok:
                self._record_rejected(key, reason)
                continue
            contract = SPEC_BY_KEY[key]['contractKey']
            if self._values.get(contract) == value:
                continue        # dedup: identical value is not a change
            self._values[contract] = value
            applied += 1
            self._source = 'ttaro'
        if applied:
            self._revision += 1
        return applied
