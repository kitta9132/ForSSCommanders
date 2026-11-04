# -*- coding: utf-8 -*-
# MIT License
# Copyright (c) 2026 Tz-WIND/Lex_q
#
# SPDX-License-Identifier: MIT

API_VERSION = 'API_v1.0'
MOD_NAME = 'WowsExtractor'
MOD_VERSION = '0.3.30-atm-derived-state'

# ---------------------------------------------------------------------------
# WowsExtractor -- in-game data collector for the "8111 for WoWS" project.
#
# It collects *legal* (player-visible) battle data through the official
# ModsAPI and writes it to JSON files on disk. A separate local process
# (server/server.py) reads those files and exposes them over HTTP + WebSocket,
# similar to War Thunder's localhost:8111 telemetry.
#
#   meta.json   -- written once per battle: roster, map, consumable ranges.
#   state.json  -- written ~10x/sec: live ship positions, hp, damage, etc.
#
# This mod creates NO UI elements; it only reads game state and writes files.
# Everything is wrapped defensively: a missing/renamed API on a given client
# build degrades gracefully (the field is omitted) instead of crashing.
# ---------------------------------------------------------------------------

try:
    import events, ui, utils, dataHub, constants, battle, callbacks
except:
    pass

# `os` may not be directly importable inside the sandbox -- borrow it from a
# stdlib module that already imported it (same trick as ModsInstaller).
try:
    import os
except:
    try:
        import xml.sax.saxutils
        os = xml.sax.saxutils.os
    except:
        os = None

# The standard `json` module is *much* faster than our pure-python fallback.
# It may be blocked by the sandbox importer (like `os`), so this is best-effort.
try:
    import json as _json_module
except:
    _json_module = None

try:
    from .battle_identity import BattleIdentity, create_session_nonce
except:
    from battle_identity import BattleIdentity, create_session_nonce

try:
    from .emit_guard import should_write_state
except:
    from emit_guard import should_write_state

try:
    from .ui_health import (
        AvatarRows, apply_ui_health, index_avatar_health, normalize_ui_health,
        index_avatar_health_sample)
except:
    from ui_health import (
        AvatarRows, apply_ui_health, index_avatar_health, normalize_ui_health,
        index_avatar_health_sample)

try:
    from .torpedo_telemetry import (TorpedoTelemetry, attach_ui_state,
        TorpedoMotion, safe_weapon_hub_probe,
        safe_weapon_context_probe, safe_game_clock_probe,
        safe_gun_reload_probe, safe_selected_torpedo_params_probe,
        safe_torpedo_tooltip_parameter_probe, safe_identity_candidates,
        shared_diagnostic_snapshot, ui_torpedo_probe_without_state,
        ui_torpedo_depth_probe,
        ui_torpedo_state_probe, attach_ui_depth_state,
        attach_ui_torpedo_state)
except:
    from torpedo_telemetry import (TorpedoTelemetry, attach_ui_state,
        TorpedoMotion, safe_weapon_hub_probe,
        safe_weapon_context_probe, safe_game_clock_probe,
        safe_gun_reload_probe, safe_selected_torpedo_params_probe,
        safe_torpedo_tooltip_parameter_probe, safe_identity_candidates,
        shared_diagnostic_snapshot, ui_torpedo_probe_without_state,
        ui_torpedo_depth_probe,
        ui_torpedo_state_probe, attach_ui_depth_state,
        attach_ui_torpedo_state)

try:
    from .submarine_telemetry import safe_submarine_probe
except:
    from submarine_telemetry import safe_submarine_probe

try:
    from .performance_profiler import PerformanceProfiler
except:
    from performance_profiler import PerformanceProfiler

try:
    from .map_calibration import MapCalibration
except:
    from map_calibration import MapCalibration

try:
    from .damage_tracker import (
        DamageTracker, roster_ids_from_avatar)
except:
    from damage_tracker import (
        DamageTracker, roster_ids_from_avatar)

# One nonce per game/mod load prevents fallback IDs repeating after a restart.
SESSION_NONCE = create_session_nonce()


def _get_threading():
    """Best-effort handle to the `threading` module.

    The collector's only heavy per-frame cost (JSON encoding + disk I/O) is moved
    off the game thread onto a background writer when threading is available. The
    sandbox may block `import threading`; if so we try to borrow an already-loaded
    copy (same idea as the `os` trick) and otherwise fall back to synchronous
    writes -- correctness is identical either way, only smoothness differs.
    """
    try:
        import threading as _t
        if hasattr(_t, 'Thread'):
            return _t
    except:
        pass
    try:
        import sys as _sys
        for _m in list(_sys.modules.values()):
            try:
                _t = getattr(_m, 'threading', None)
                if _t is not None and hasattr(_t, 'Thread') and hasattr(_t, 'Lock'):
                    return _t
            except:
                pass
    except:
        pass
    return None


_threading = _get_threading()

# sentinel used to memoize values that may legitimately be None
_UNSET = object()

try:
    CC = constants.UiComponents
except:
    CC = None

STATE_INTERVAL = 0.2          # default seconds between state.json writes (~5 Hz); see config.ini
META_RETRY_INTERVAL = 0.5     # battleInfo/map can be late in very small battles
                              # (also gates the arena-id promotion probe)
META_RETRY_SECONDS = 12.0
SCHEMA_VERSION = 1
# Version of the JSON contract written to disk. Distinct from API_VERSION above,
# which declares the ModsAPI level to the PnFMods loader.
WIRE_API_VERSION = '1.0'
INVALID = -1


# ===========================================================================
# small utilities
# ===========================================================================
def logInfo(*args):
    try:
        utils.logInfo('[{}] {}'.format(MOD_NAME, ' '.join([_str(a) for a in args])))
    except:
        pass


def logError(*args):
    try:
        utils.logError('[{}] {}'.format(MOD_NAME, ' '.join([_str(a) for a in args])))
    except:
        pass


def _str(v):
    try:
        return str(v)
    except:
        try:
            return repr(v)
        except:
            return '?'


def _try(fn, default=None):
    """Call a zero-arg callable, swallowing any exception."""
    try:
        return fn()
    except:
        return default


def _get(obj, name, default=None):
    """getattr() that swallows exceptions -- like `_try(lambda: obj.name)` but
    without allocating a lambda on every call (this runs in the hot ship loop)."""
    try:
        return getattr(obj, name)
    except:
        return default


def _visibility_type(value):
    """Return a bounded type label without stringifying engine objects."""
    if value is None:
        return 'NoneType'
    if isinstance(value, bool):
        return 'bool'
    if isinstance(value, _INT_TYPES):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, _STRING_TYPES):
        return 'string'
    return 'object'


def _visibility_raw(value):
    """Only copy JSON-safe scalar values; reject non-finite numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, _INT_TYPES):
        return value
    if isinstance(value, float):
        if value != value or value in (float('inf'), float('-inf')):
            return None
        return value
    if isinstance(value, _STRING_TYPES) and len(value) <= 128:
        return value
    return None


def _observation_scalar(value):
    """Copy only JSON-safe finite scalar values into avatar observations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, _INT_TYPES):
        return value
    if isinstance(value, float):
        if value != value or value in (float('inf'), -float('inf')):
            return None
        return value
    if isinstance(value, _STRING_TYPES):
        return value
    return None


def _observation_exception_name(error):
    """Read only the exception class name, without repr/stringifying it."""
    try:
        return error.__class__.__name__
    except Exception:
        return ''


def _observation_field(obj, name):
    """Read one attribute/mapping field and label missing, None and failures."""
    if obj is None:
        return None, 'componentMissing'
    if _is_mapping(obj):
        try:
            value = obj.get(name, _UNSET)
        except Exception:
            return None, 'readError'
        if value is _UNSET:
            return None, 'missing'
    else:
        try:
            value = getattr(obj, name)
        except Exception as error:
            status = ('missing' if _observation_exception_name(error) ==
                      'AttributeError' else 'readError')
            return None, status
    if value is None:
        return None, 'none'
    return value, 'available'


def _empty_avatar_observations(status, source, reason=None):
    return {
        'status': status,
        'source': source,
        'sampleTs': None,
        'rows': [],
        'candidateConsistency': {
            'source': 'sameSnapshot.avatar.id == state.ships[].playerId',
            'candidateNamespace': 'avatar.id',
            'comparedNamespace': 'ships[].playerId',
            'comparison': 'strictScalarTypeAndValue',
            'semantics': 'unverified',
            'avatarInputComplete': False,
            'shipsCompleteness': 'unknown',
            'candidateAvailableCount': 0,
            'candidateExactValueMatchCount': 0,
            'candidateUnmatchedInSnapshotCount': 0,
            'candidateAmbiguousCount': 0,
            'candidateUnknownCount': 0,
            'duplicateAvatarIdCount': 0,
            'duplicateShipPlayerIdCount': 0,
        },
        'coverage': {
            'sampledEntityCount': 0,
            'inputStatus': status,
            'inputComplete': False,
            'inputAvailability': ('notSampled' if status in ('disabled', 'notSampled')
                                  else 'unknown'),
            'reason': reason,
            'distinctPlayerIdCount': 0,
            'apiMatchedCount': 0,
            'missingInApiCount': 0,
            'apiPresenceUnknownCount': 0,
            'unmatchableIdCount': 0,
            'duplicateIdConflictCount': 0,
            'mapPositionAvailableCount': 0,
            'healthRawAvailableCount': 0,
        },
    }


def _visibility_observation(source, status, value=None, reason=None):
    result = {'source': source, 'status': status,
              'raw': _visibility_raw(value), 'type': _visibility_type(value),
              'reason': reason}
    return result


# ---------------------------------------------------------------------------
# config file (config.ini next to this mod). Uses a trivial `key = value` format
# parsed with plain string ops, so it works even if json/configparser are blocked
# by the sandbox. A missing/garbled file just means built-in defaults.
# ---------------------------------------------------------------------------
def _parse_kv(text):
    cfg = {}
    try:
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        for line in text.split('\n'):
            line = line.strip()
            if not line or line[0] in ('#', ';') or '=' not in line:
                continue
            i = line.find('=')
            key = line[:i].strip().lower()
            val = line[i + 1:].strip()
            if key:
                cfg[key] = val
    except:
        pass
    return cfg


def _cfg_float(cfg, key, default):
    try:
        v = cfg.get(key)
        if v is None or v == '':
            return default
        return float(v)
    except:
        return default


def _load_mod_config():
    base = _try(lambda: utils.getModDir())
    if not base:
        return {}
    try:
        f = open(base + '/config.ini', 'rb')
        try:
            raw = f.read()
        finally:
            f.close()
        return _parse_kv(raw)
    except:
        return {}


def _now():
    return _try(lambda: utils.getTimeFromGameStart(), 0.0) or 0.0


# ---------------------------------------------------------------------------
# minimal JSON encoder (does not depend on the `json` module being importable)
# ---------------------------------------------------------------------------
try:
    _STRING_TYPES = (str, unicode)
    _INT_TYPES = (int, long)
except NameError:  # pragma: no cover - python3 safety, not used in game
    _STRING_TYPES = (str,)
    _INT_TYPES = (int,)


def _strict_player_lookup_key(value):
    """Make a type-preserving key for a plain player/vehicle ID."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, _STRING_TYPES):
        if not value or not value.strip():
            return None
    elif isinstance(value, _INT_TYPES):
        pass
    elif isinstance(value, float):
        if value != value or value in (float('inf'), -float('inf')):
            return None
    else:
        return None
    try:
        hash(value)
    except Exception:
        return None
    return (type(value), value)


def _player_field(player, name):
    """Read one PlayerInfo field without coercing or retaining its object."""
    if _is_mapping(player):
        value = _try(lambda: player[name])
        if value is not None:
            return value
    return _get(player, name)


def _plain_player_row(player):
    """Return (strict vehicle key, plain playerId/teamId) for a roster row."""
    if player is None:
        return None
    player_id = _player_field(player, 'playerId')
    if player_id is None:
        player_id = _player_field(player, 'id')
    vehicle_id = _player_field(player, 'shipId')
    if vehicle_id is None:
        vehicle_id = _player_field(player, 'vehicleId')
    if vehicle_id is None:
        vehicle_id = _player_field(player, 'vehicleID')
    vehicle_key = _strict_player_lookup_key(vehicle_id)
    player_key = _strict_player_lookup_key(player_id)
    if vehicle_key is None:
        return None
    if player_key is None:
        return vehicle_key, None
    team_id = _player_field(player, 'teamId')
    if team_id is not None and _strict_player_lookup_key(team_id) is None:
        team_id = None
    return vehicle_key, {'playerId': player_id, 'teamId': team_id}


_ESCAPE = {
    '"': '\\"', '\\': '\\\\', '\b': '\\b', '\f': '\\f',
    '\n': '\\n', '\r': '\\r', '\t': '\\t',
}


def _json_str(s):
    try:
        if isinstance(s, unicode):
            s = s.encode('utf-8')
    except NameError:
        pass
    # Fast path: the vast majority of our strings (keys, names, enum values) need
    # no escaping. `min(s)`, `in` are C-level scans -- far cheaper than iterating
    # every character in pure Python, which is what dominated the old hot path.
    try:
        if not s or (min(s) >= ' ' and '"' not in s and '\\' not in s):
            return '"' + s + '"'
    except:
        pass
    out = ['"']
    for ch in s:
        if ch in _ESCAPE:
            out.append(_ESCAPE[ch])
        elif ord(ch) < 0x20:
            out.append('\\u%04x' % ord(ch))
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def _json(obj):
    if obj is None:
        return 'null'
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'
    if isinstance(obj, _INT_TYPES):
        return str(obj)
    if isinstance(obj, float):
        if obj != obj or obj in (float('inf'), float('-inf')):  # NaN/inf -> null
            return 'null'
        return repr(obj)
    if isinstance(obj, _STRING_TYPES):
        return _json_str(obj)
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            try:
                key = k if isinstance(k, _STRING_TYPES) else str(k)
            except:
                key = '?'
            parts.append(_json_str(key) + ':' + _json(v))
        return '{' + ','.join(parts) + '}'
    if isinstance(obj, (list, tuple)):
        return '[' + ','.join([_json(v) for v in obj]) + ']'
    # last resort
    return _json_str(_str(obj))


def json_dumps(obj):
    # Prefer the engine helper if present, then stdlib json, then our encoder.
    enc = getattr(utils, 'jsonEncode', None)
    if enc is not None:
        try:
            return enc(obj)
        except:
            pass
    if _json_module is not None:
        try:
            return _json_module.dumps(obj)
        except:
            pass
    return _json(obj)


def _serialize_safe(obj):
    """Thread-safe serializer for the background writer.

    Deliberately avoids `utils.jsonEncode` -- engine helpers are only safe to call
    on the game thread. Plain `json` / our pure-python encoder are fine off-thread,
    and since this no longer runs on the render thread its speed barely matters."""
    if _json_module is not None:
        try:
            return _json_module.dumps(obj)
        except:
            pass
    return _json(obj)


def _atomic_write(path, text):
    """Best-effort atomic write. Falls back to a plain write if os is missing.
    The server tolerates partial reads anyway (keeps last good snapshot)."""
    try:
        data = text
        try:
            if isinstance(text, unicode):
                data = text.encode('utf-8')
        except NameError:
            pass
        if os is None:
            f = open(path, 'wb')
            try:
                f.write(data)
            finally:
                f.close()
            return True
        tmp = path + '.tmp'
        f = open(tmp, 'wb')
        try:
            f.write(data)
        finally:
            f.close()
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
        os.rename(tmp, path)
        return True
    except Exception, e:
        logError('write failed for {}: {}'.format(path, _str(e)))
        return False


def _write_file(path, text):
    """Plain in-place overwrite (no temp+rename churn).

    Used for the high-frequency state.json. A reader that catches a half-written
    file just parses to None and keeps its last good snapshot (the server does
    exactly this), and the next write one state interval later (0.2s by default)
    heals it -- so we trade
    strict atomicity for far fewer syscalls and no per-tick "new file" that
    on-access antivirus would re-scan."""
    try:
        data = text
        try:
            if isinstance(text, unicode):
                data = text.encode('utf-8')
        except NameError:
            pass
        f = open(path, 'wb')
        try:
            f.write(data)
        finally:
            f.close()
        return True
    except Exception, e:
        logError('write failed for {}: {}'.format(path, _str(e)))
        return False


# ===========================================================================
# background writer -- keeps JSON encoding + disk I/O off the game thread
# ===========================================================================
class _AsyncWriter(object):
    """Single daemon thread that serializes plain-data snapshots and writes them
    to disk. The game thread only builds the (pure python) snapshot dict and drops
    it in a latest-wins slot per path; if the disk stalls we simply skip stale
    frames instead of backing up a queue or blocking rendering."""

    def __init__(self, threading_mod):
        self._lock = threading_mod.Lock()
        self._event = threading_mod.Event()
        self._pending = {}        # path -> latest snapshot dict (latest wins)
        self._alive = True
        th = threading_mod.Thread(target=self._run)
        try:
            th.setName('WowsExtractorWriter')
        except:
            pass
        try:
            th.setDaemon(True)
        except:
            try:
                th.daemon = True
            except:
                pass
        self._thread = th
        th.start()

    def submit(self, path, obj):
        self._lock.acquire()
        try:
            self._pending[path] = obj
        finally:
            self._lock.release()
        self._event.set()

    def _drain(self):
        self._lock.acquire()
        try:
            batch = self._pending
            self._pending = {}
        finally:
            self._lock.release()
        return batch

    def _run(self):
        while self._alive:
            try:
                self._event.wait(1.0)
                self._event.clear()
                batch = self._drain()
                for path, obj in batch.items():
                    try:
                        _write_file(path, _serialize_safe(obj))
                    except:
                        pass
            except:
                # the writer thread must never die on a transient error
                try:
                    self._event.clear()
                except:
                    pass


def _coerce(val):
    """Keep only JSON-friendly values; convert Vector3-likes to [x, y, z].
    Returns None for anything we don't want serialized (engine objects etc.)."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, long, float)):
        return val
    if isinstance(val, (str, unicode)):
        return val
    v = _vec(val)
    if v is not None:
        return v
    if isinstance(val, (list, tuple)):
        out = []
        for x in val:
            c = _coerce(x)
            if c is not None:
                out.append(c)
        return out
    return None


def _vec(pos):
    """Extract (x, y, z) from a Vector3 / tuple / object, defensively."""
    if pos is None:
        return None
    for attrs in (('x', 'y', 'z'),):
        try:
            return [float(getattr(pos, attrs[0])), float(getattr(pos, attrs[1])),
                    float(getattr(pos, attrs[2]))]
        except:
            pass
    try:
        return [float(pos[0]), float(pos[1]), float(pos[2])]
    except:
        return None


def _component_pos(comp):
    """Extract [x, y, z] from a dataHub position component (e.g. worldPosition).

    The component may itself behave like a Vector3, or wrap the coordinates under
    a sub-attribute, so probe both shapes defensively."""
    if comp is None:
        return None
    pos = _vec(comp)
    if pos:
        return pos
    for attr in ('position', 'worldPosition', 'point', 'value', 'pos', 'coords'):
        pos = _vec(_get(comp, attr))
        if pos:
            return pos
    return None


def _point_xy(pt):
    """Extract [x, y] from a 2D Point-like object (mapPosition.position)."""
    if pt is None:
        return None
    try:
        return [float(pt.x), float(pt.y)]
    except:
        pass
    try:
        return [float(pt[0]), float(pt[1])]
    except:
        return None


def _map_norm_xy(x, y):
    """Return trusted minimap-normalized [x, y], or None if the source is bogus."""
    try:
        nx = float(x)
        ny = float(y)
    except:
        return None
    if nx != nx or ny != ny:
        return None
    if nx < -0.01 or nx > 1.01 or ny < -0.01 or ny > 1.01:
        return None
    if nx < 0.0:
        nx = 0.0
    elif nx > 1.0:
        nx = 1.0
    if ny < 0.0:
        ny = 0.0
    elif ny > 1.0:
        ny = 1.0
    return [nx, ny]


def _looks_like_space(v):
    """True if `v` looks like an internal WoWS space id.

    Examples: "spaces/13_OC_new_dawn", "13_OC_new_dawn", "s02_Naval_Defense".
    The leading token is digits (13) or a letter + digits (s02). This lets the
    collector pick the recognition key out of a grab-bag of arena attributes,
    even when one of them is a localized display name instead.
    """
    if not isinstance(v, (str, unicode)):
        return False
    tail = v.replace('\\', '/').strip().strip('/').rsplit('/', 1)[-1]
    if '_' not in tail:
        return False
    head = tail.split('_', 1)[0]
    if head.isdigit():
        return True
    return len(head) >= 2 and head[0].isalpha() and head[1:].isdigit()


# ===========================================================================
# ballistics tracker (best-effort; mirrors PenetrationCalculator)
# ===========================================================================
class BallisticsTracker(object):
    def __init__(self):
        self._ammo = None
        self._modifiers = None
        self._squadron = False

    def start(self):
        self._modifiers = _try(lambda: battle.getAmmoModifiers())
        self._squadron = False
        self._refresh_selected()

    def stop(self):
        self._ammo = None
        self._modifiers = None
        self._squadron = False

    def _refresh_selected(self):
        wt = _try(lambda: constants.WeaponType.ARTILLERY)
        ammoId = _try(lambda: battle.getSelectedAmmoId(wt), INVALID)
        self.on_ammo_changed(ammoId)

    def on_ammo_changed(self, ammoId):
        if ammoId is None or ammoId == INVALID:
            self._ammo = None
            return
        if self._ammo is None or _try(lambda: self._ammo.id) != ammoId:
            self._ammo = _try(lambda: battle.getAmmoParams(ammoId))

    def on_weapon_changed(self, weaponType):
        wt = _try(lambda: constants.WeaponType.ARTILLERY)
        if weaponType == wt:
            self.on_ammo_changed(_try(lambda: battle.getSelectedAmmoId(weaponType), INVALID))
        else:
            self._ammo = None

    def on_squadron(self, bombParamsId):
        self._squadron = True
        self.on_ammo_changed(bombParamsId)

    def on_squadron_off(self, *a):
        self._squadron = False
        self.on_ammo_changed(INVALID)

    def snapshot(self):
        ammo = self._ammo
        if ammo is None:
            return {'available': False}
        data = {'available': True, 'squadronMode': bool(self._squadron)}
        data['ammoType'] = _try(lambda: ammo.ammoType)
        data['ammoId'] = _try(lambda: ammo.id)
        hoop = _try(lambda: battle.getSelfHoopRanging())
        impactSpeed = self._impact_speed(ammo, hoop)
        data['penetration'] = self._penetration(ammo, impactSpeed)
        data['impactSpeed'] = impactSpeed
        data['impactAngle'] = _try(lambda: __import__('math').degrees(hoop.pitch)) if hoop is not None else None
        isAP = data['ammoType'] == 'AP'
        isCS = data['ammoType'] == 'CS'
        if isAP or isCS:
            data['startRicochet'] = _try(lambda: ammo.bulletRicochetAt)
            data['alwaysRicochet'] = _try(lambda: ammo.bulletAlwaysRicochetAt)
            data['overmatch'] = _try(lambda: __import__('math').floor(ammo.bulletDiametr * 1000 / 14.3))
        if isAP:
            data['detonatorDelay'] = _try(lambda: ammo.bulletDetonator)
            data['detonatorThreshold'] = _try(lambda: ammo.bulletDetonatorThreshold)
        return data

    def _impact_speed(self, ammo, hoop):
        if self._squadron:
            return _try(lambda: ammo.bulletSpeed) if _try(lambda: ammo.ammoType) == 'AP' else None
        if hoop is None:
            return None
        gunPos = _try(lambda: hoop.gunPos)
        gunDir = _try(lambda: hoop.gunDir)
        if gunPos is None or gunDir is None:
            return None
        if _try(lambda: gunPos.y, 0) >= 0.001:
            return _try(lambda: battle.getAmmoImpactSpeed(ammo, gunPos, gunDir))
        return None

    def _penetration(self, ammo, impactSpeed):
        atype = _try(lambda: ammo.ammoType)
        if atype == 'HE':
            return _try(lambda: int(ammo.alphaPiercingHE))
        if atype == 'CS':
            return _try(lambda: int(ammo.alphaPiercingCS))
        if atype == 'AP' and impactSpeed:
            def calc():
                import math
                krupp = battle.getBulletKrupp(ammo, self._modifiers)
                raw = (krupp * (ammo.bulletMass * impactSpeed * impactSpeed) ** 0.69
                       * ammo.bulletDiametr ** (-1.07) * 0.0000001)
                if self._squadron:
                    return int(raw)
                normalize = math.radians(ammo.bulletCapNormalizeMaxAngle)
                hoop = battle.getSelfHoopRanging()
                angle = max(0, abs(hoop.pitch) - normalize)
                return int(raw * math.cos(angle))
            return _try(calc)
        return None


# ===========================================================================
# main collector
# ===========================================================================
class Collector(object):
    def __init__(self):
        self._stateFile = None
        self._metaFile = None
        self._tickHandle = None
        self._lastWrite = 0.0
        self._active = False
        self._battleStarted = False
        self._battleShown = False
        self._selfPlayerId = None
        self._battleIdentity = BattleIdentity(SESSION_NONCE)
        self._battleId = None
        self._selfTeam = _UNSET       # memoized once per snapshot build
        self._stateInterval = STATE_INTERVAL
        self._collectionEnabled = False
        self._diagnosticsEnabled = False
        self._torpedoDepthSamplingEnabled = False
        self._torpedoDepthSamplingInterval = 1.0
        self._torpedoDepthSamplingNextDue = None
        self._torpedoDepthSamplingLastNow = None
        self._torpedoDepthSamplingDue = False
        self._profilerEnabled = False
        self._positionFallbacksEnabled = False
        self._performanceProfiler = None
        self._diagnosticsInterval = 1.0
        self._diagnosticsNextDue = None
        self._diagnosticsLastSampleTs = None
        self._diagnosticsLastNow = None
        self._diagnosticsSampleDue = False
        self._lastMetaWrite = 0.0
        self._metaRetryUntil = 0.0
        self._metaReady = False
        self._metaProbeDue = None     # next arena-id probe time (game clock)
        self._metaProbeLastNow = None # last clock value, for rollback detection
        self._load_config()
        self._damage = DamageTracker(resolve=self._live_vehicle_player)
        self._ballistics = BallisticsTracker()
        self._torpedoes = TorpedoTelemetry(battle, constants)
        self._torpedoMotion = TorpedoMotion()
        self._mapCalibration = MapCalibration()
        # cached map->world affine (per battle/map); derived at runtime from ships
        # that expose BOTH getPosition() (world) and the mapPosition component.
        self._mapTransform = None

        # Move JSON encoding + disk writes off the game thread when possible.
        self._writer = None
        if self._collectionEnabled and _threading is not None:
            try:
                self._writer = _AsyncWriter(_threading)
                logInfo('async writer enabled (encoding + disk I/O off game thread)')
            except Exception, e:
                self._writer = None
                logError('async writer unavailable, using sync writes: {}'.format(_str(e)))

        events.onBattleStart(self._on_battle_start)
        events.onBattleShown(self._on_battle_shown)
        events.onBattleQuit(self._on_battle_quit)
        events.onReceiveDamagesOnShip(self._on_damages)
        _try(lambda: events.onReceiveShellInfo(self._on_shell_info))
        # ballistics (best effort; some builds may not expose all of these)
        _try(lambda: events.onArtilleryAmmoChanged(self._on_artillery_ammo_changed))
        _try(lambda: events.onWeaponTypeChanged(self._on_weapon_type_changed))
        _try(lambda: events.onSquadronActivated(self._on_squadron_activated))
        _try(lambda: events.onSquadronDeactivated(self._on_squadron_deactivated))
        logInfo('loaded v{} (state interval {}s)'.format(MOD_VERSION, self._stateInterval))

    # -- config -------------------------------------------------------------
    def _load_config(self):
        """(Re)read config.ini from the mod folder. Called at load and again on
        each battle start, so edits are picked up without restarting the game."""
        try:
            cfg = _load_mod_config()
            if not isinstance(cfg, dict):
                cfg = {}
        except:
            cfg = {}
        # Collection is opt-in. Only the literal, valid value "true" enables it.
        self._collectionEnabled = cfg.get('collection_enabled') == 'true'
        self._diagnosticsEnabled = (
            self._collectionEnabled and cfg.get('diagnostics_enabled') == 'true')
        self._positionFallbacksEnabled = (
            self._collectionEnabled and cfg.get('position_fallbacks_enabled') == 'true')
        profiler_enabled = (
            self._collectionEnabled and cfg.get('profiler_enabled') == 'true')
        # Keep OFF as None: no disabled-profiler wrappers or closures on each
        # frame. A failed opt-in profiler remains available for status output.
        if profiler_enabled:
            if (getattr(self, '_performanceProfiler', None) is None or
                    not getattr(self, '_profilerEnabled', False)):
                self._performanceProfiler = PerformanceProfiler(True, True)
        else:
            self._performanceProfiler = None
        self._profilerEnabled = profiler_enabled
        self._diagnosticsInterval = max(
            _cfg_float(cfg, 'diagnostics_interval', 1.0), 0.1)
        self._torpedoDepthSamplingEnabled = (
            self._collectionEnabled and
            cfg.get('torpedo_depth_sampling_enabled') == 'true')
        depth_interval = _cfg_float(
            cfg, 'torpedo_depth_sampling_interval', 1.0)
        try:
            depth_interval = float(depth_interval)
            if (depth_interval != depth_interval or
                    depth_interval == float('inf') or
                    depth_interval == -float('inf')):
                depth_interval = 1.0
        except Exception:
            depth_interval = 1.0
        self._torpedoDepthSamplingInterval = max(depth_interval, 1.0)
        self._torpedoDepthSamplingNextDue = None
        self._torpedoDepthSamplingLastNow = None
        self._torpedoDepthSamplingDue = False
        self._torpedoStateSamplingEnabled = (
            self._collectionEnabled and
            cfg.get('torpedo_state_sampling_enabled') == 'true')
        state_interval = _cfg_float(
            cfg, 'torpedo_state_sampling_interval', 1.0)
        try:
            state_interval = float(state_interval)
            if (state_interval != state_interval or
                    state_interval == float('inf') or
                    state_interval == -float('inf')):
                state_interval = 1.0
        except Exception:
            state_interval = 1.0
        self._torpedoStateSamplingInterval = max(state_interval, 1.0)
        self._torpedoStateSamplingNextDue = None
        self._torpedoStateSamplingLastNow = None
        self._torpedoStateSamplingDue = False
        # A provider declaration names the expected third-party producer only.
        # It never enables sampling and cannot be verified from the generic
        # mods_DataComponent field at runtime. Unknown/malformed values fail
        # closed to "unknown".
        if cfg.get('torpedo_state_provider') == 'advanced_torpedo_marker':
            self._torpedoStateProvider = 'advanced_torpedo_marker'
        else:
            self._torpedoStateProvider = 'unknown'
        self._diagnosticsNextDue = None
        self._diagnosticsLastSampleTs = None
        self._diagnosticsLastNow = None
        self._diagnosticsSampleDue = False
        if self._performanceProfiler is not None:
            self._performanceProfiler.reset_battle()
        # clamp the interval so a typo (0 / negative) can't hammer the disk
        self._stateInterval = max(_cfg_float(cfg, 'state_interval', STATE_INTERVAL), 0.02)

    # -- paths --------------------------------------------------------------
    def _resolve_paths(self):
        base = _try(lambda: utils.getModDir())
        if not base:
            base = '.'
        self._stateFile = base + '/state.json'
        self._metaFile = base + '/meta.json'
        try:
            abspath = os.path.abspath(self._stateFile) if os else self._stateFile
        except:
            abspath = self._stateFile
        logInfo('writing telemetry to: {}'.format(abspath))

    # -- lifecycle ----------------------------------------------------------
    def _on_battle_start(self, *args):
        self._load_config()
        self._resolve_paths()
        self._mapCalibration.clear()
        self._torpedoMotion.clear()
        self._damage.clear()
        self._mapTransform = None
        self._diagnosticsNextDue = None
        self._diagnosticsLastSampleTs = None
        self._diagnosticsLastNow = None
        self._torpedoDepthSamplingNextDue = None
        self._torpedoDepthSamplingLastNow = None
        self._torpedoDepthSamplingDue = False
        self._lastMetaWrite = 0.0
        self._metaRetryUntil = 0.0
        self._metaReady = False
        self._metaProbeDue = None
        self._metaProbeLastNow = None
        if self._collectionEnabled:
            self._selfPlayerId = _try(lambda: battle.getSelfPlayerInfo().id)
            self._remember_player_vehicle(_try(lambda: battle.getSelfPlayerInfo()))
            self._remember_roster_vehicles()
            self._battleId = self._battleIdentity.start(
                self._selfPlayerId, self._find_arena_id())
        else:
            self._selfPlayerId = None
            self._battleId = self._battleIdentity.start(None, None)
        self._battleStarted = True
        if self._battleShown:
            self._start_collection()

    def _find_arena_id(self):
        """Return the raw arena id when the client has exposed it yet."""
        for getter in (
                lambda: battle.getArenaInfo(),
                lambda: self._battle_info_component()):
            info = _try(getter)
            if info is None:
                continue
            for key in ('arenaUniqueId', 'arenaUniqueID', 'uniqueId',
                        'uniqueID', 'arenaId', 'arenaID', 'battleId'):
                val = _coerce(_get(info, key))
                if val not in (None, '', 0):
                    return val
        return None

    def _promote_battle_id(self):
        """Promote a fallback id when the arena id arrives after battle start."""
        before = self._battleId
        self._battleId = self._battleIdentity.promote(self._find_arena_id())
        return self._battleId != before

    def _on_battle_shown(self, *args):
        # Some clients show the battle UI during loading, before onBattleStart.
        # Wait for both events so paths and per-battle identity are initialized.
        self._battleShown = True
        if self._battleStarted:
            self._start_collection()

    def _start_collection(self):
        if self._active:
            return
        self._active = True
        if not self._collectionEnabled:
            # Keep lifecycle visible without polling game APIs or scheduling ticks.
            self._write_state({'schema': SCHEMA_VERSION,
                'apiVersion': WIRE_API_VERSION, 'battleId': self._battleId,
                'active': True, 'collection': {'status': 'disabled',
                    'source': 'config.collection_enabled'}, 'ts': _now(),
                'ships': [], 'self': None, 'torpedoes': [], 'damage': {},
                'avatarObservations': _empty_avatar_observations(
                    'disabled', 'config.collection_enabled')})
            logInfo('collection disabled by config')
            return
        self._ballistics.start()
        self._metaRetryUntil = _now() + META_RETRY_SECONDS
        self._remember_roster_vehicles()
        self._refresh_meta(force=True)
        # start the high-frequency state loop
        self._stop_tick()
        self._tickHandle = _try(lambda: callbacks.perTick(self._tick))
        self._lastWrite = 0.0
        self._tick()  # write an immediate first frame

    def _on_battle_quit(self, *args):
        self._active = False
        self._battleStarted = False
        self._battleShown = False
        self._metaProbeDue = None
        self._metaProbeLastNow = None
        self._mapCalibration.clear()
        self._torpedoMotion.clear()
        self._stop_tick()
        if self._collectionEnabled:
            self._ballistics.stop()
        self._mapTransform = None
        # write one final snapshot marking the battle inactive (through the same
        # single writer, so it can't race a still-queued "active" frame)
        try:
            snap = {'schema': SCHEMA_VERSION, 'apiVersion': WIRE_API_VERSION,
                    'battleId': self._battleId, 'active': False, 'ts': _now(),
                    'ships': [], 'self': None,
                    'torpedoes': [],
                    'torpedoStatus': {'available': False, 'status': 'unknown'},
                    'torpedoArmament': {'available': False},
                    'avatarObservations': _empty_avatar_observations(
                        'notSampled', 'lifecycle', 'battleEnded'),
                    'damage': self._damage.snapshot()}
            if not self._collectionEnabled:
                snap['collection'] = {'status': 'disabled',
                                      'source': 'config.collection_enabled'}
            self._write_state(snap)
        except:
            pass

    def _stop_tick(self):
        if self._tickHandle is not None:
            _try(lambda: callbacks.cancel(self._tickHandle))
            self._tickHandle = None

    def _live_vehicle_player(self, vehicle_id):
        """Live ModsAPI lookup. Returns (playerId, teamId) or None.

        Unreliable on a killing blow -- the vehicle is often already gone --
        which is why DamageTracker consults its roster cache first.
        """
        player = _try(lambda: battle.getPlayerByVehicleId(vehicle_id))
        if player is None:
            return None
        pid = _get(player, 'id')
        if pid is None and _is_mapping(player):
            pid = _try(lambda: player['id'])
        if pid is None:
            return None
        team = _get(player, 'teamId')
        if team is None and _is_mapping(player):
            team = _try(lambda: player['teamId'])
        return (pid, team)

    def _remember_player_vehicle(self, player, vehicle_id=None, team_id=None):
        if player is not None and self._damage.remember_player(player):
            return
        pid = _get(player, 'id') if player is not None else None
        if pid is None and player is not None and _is_mapping(player):
            pid = _try(lambda: player['id'])
        if vehicle_id is None and player is not None:
            vehicle_id = _get(player, 'shipId')
            if vehicle_id is None and _is_mapping(player):
                vehicle_id = _try(lambda: player['shipId'])
        if team_id is None and player is not None:
            team_id = _get(player, 'teamId')
            if team_id is None and _is_mapping(player):
                team_id = _try(lambda: player['teamId'])
        if vehicle_id is not None and pid is not None:
            self._damage.remember(vehicle_id, pid, team_id)

    def _remember_sampled_player_vehicle(self, player):
        """Read a roster PlayerInfo once per access path, then serve both users.

        DamageTracker's mapping/attribute precedence differs from the strict
        ship index reader. Cache item and attribute outcomes separately so
        both consumers keep their existing fallback rules without retaining
        the raw PlayerInfo in the returned plain row.
        """
        if player is None:
            return None
        is_mapping = _is_mapping(player)
        reads = {}

        def item_value(name):
            key = ('item', name)
            if key not in reads:
                try:
                    reads[key] = (True, player[name])
                except:
                    reads[key] = (False, None)
            return reads[key]

        def attr_value(name):
            key = ('attr', name)
            if key not in reads:
                try:
                    reads[key] = (True, getattr(player, name))
                except:
                    reads[key] = (False, None)
            return reads[key]

        def damage_value(names):
            for name in names:
                ok, value = item_value(name)
                if not ok:
                    ok, value = attr_value(name)
                if ok and value is not None:
                    return value
            return None

        # Match damage_tracker._get_field's item-first semantics, including
        # its rule that an item value of None advances to the next alias.
        damage_pid = damage_value(('playerId', 'id'))
        damage_vehicle = damage_value(('shipId', 'vehicleId', 'vehicleID'))
        damage_team = damage_value(('teamId',))
        remembered = None
        try:
            remembered = self._damage.remember_player_values(
                damage_vehicle, damage_pid, damage_team)
        except:
            pass

        # Preserve _remember_player_vehicle's legacy fallback, used only when
        # DamageTracker could not normalize both IDs. Attribute access comes
        # first here; a mapping-key fallback is used only for a None value.
        if remembered is False:
            try:
                ok, pid = attr_value('id')
                if not ok:
                    pid = None
                if pid is None and is_mapping:
                    ok, pid = item_value('id')
                    if not ok:
                        pid = None
                ok, vehicle_id = attr_value('shipId')
                if not ok:
                    vehicle_id = None
                if vehicle_id is None and is_mapping:
                    ok, vehicle_id = item_value('shipId')
                    if not ok:
                        vehicle_id = None
                ok, team_id = attr_value('teamId')
                if not ok:
                    team_id = None
                if team_id is None and is_mapping:
                    ok, team_id = item_value('teamId')
                    if not ok:
                        team_id = None
                if vehicle_id is not None and pid is not None:
                    self._damage.remember(vehicle_id, pid, team_id)
            except:
                pass

        def strict_value(names):
            for name in names:
                if is_mapping:
                    ok, value = item_value(name)
                    if not ok or value is None:
                        ok, value = attr_value(name)
                else:
                    ok, value = attr_value(name)
                if ok and value is not None:
                    return value
            return None

        player_id = strict_value(('playerId', 'id'))
        vehicle_id = strict_value(('shipId', 'vehicleId', 'vehicleID'))
        vehicle_key = _strict_player_lookup_key(vehicle_id)
        player_key = _strict_player_lookup_key(player_id)
        if vehicle_key is None:
            return None
        if player_key is None:
            return vehicle_key, None
        team_id = strict_value(('teamId',))
        if team_id is not None and _strict_player_lookup_key(team_id) is None:
            team_id = None
        return vehicle_key, {'playerId': player_id, 'teamId': team_id}

    def _remember_roster_vehicles(self, avatar_entities=None):
        """Cache vehicleId -> playerId for the whole roster, including ships
        that are already dead or were never in getAllShips() this tick.

        PlayerInfo.shipId survives destruction; getPlayerByVehicleId does not.
        The returned strict plain index is local to this state build only.
        """
        build_player_index = avatar_entities is not None
        players = _try(lambda: battle.getPlayersInfo())
        if players is None:
            players = _try(lambda: battle.getPlayers())
        player_sample = {'status': 'unavailable', 'index': {},
                         'seenKeys': {}, 'duplicateKeys': {}}
        if players is not None:
            player_sample['status'] = 'complete'
            items = players
            if _is_mapping(players):
                items = _try(lambda: players.values())
                if items is None:
                    items = ()
                    player_sample['status'] = 'partial'
            try:
                for player in items:
                    if build_player_index:
                        row = self._remember_sampled_player_vehicle(player)
                    else:
                        _try(lambda p=player: self._remember_player_vehicle(p))
                        continue
                    if row is None:
                        continue
                    key, values = row
                    if key in player_sample['duplicateKeys']:
                        continue
                    if key in player_sample['seenKeys']:
                        # Even identical duplicates are ambiguous for this join.
                        player_sample['index'].pop(key, None)
                        player_sample['duplicateKeys'][key] = True
                        continue
                    player_sample['seenKeys'][key] = True
                    if values is not None:
                        player_sample['index'][key] = values
            except Exception:
                # Prefix rows remain usable, but this sample is explicitly partial.
                player_sample['status'] = 'partial'
        if CC is None:
            return player_sample
        av_key = _get(CC, 'avatar')
        veh_key = _get(CC, 'vehicle')
        if av_key is None:
            return player_sample
        if avatar_entities is None:
            avatar_entities = _try(
                lambda: dataHub.getEntityCollections('avatar'), []) or []
        sample_reader = getattr(avatar_entities, 'sample_ids', None)
        sample = (_try(lambda: sample_reader(CC))
                  if sample_reader is not None else None)
        if sample is not None:
            for row in sample['rows']:
                rec = roster_ids_from_avatar(row.get('avatar'), row.get('vehicle'))
                if rec is not None:
                    self._damage.remember(rec[0], rec[1], rec[2])
            return player_sample
        for entity in avatar_entities or []:
            avatar = _try(lambda e=entity, k=av_key: e[k])
            vehicle = _try(lambda e=entity, k=veh_key: e[k]) if veh_key is not None else None
            rec = roster_ids_from_avatar(avatar, vehicle)
            if rec is not None:
                self._damage.remember(rec[0], rec[1], rec[2])
        return player_sample

    def _on_damages(self, victimId, damages):
        if not self._collectionEnabled or not self._active:
            return
        _try(lambda: self._damage.on_damages(victimId, damages))

    def _on_shell_info(self, victimId, shooterId, ammoId=None, matId=None,
                       shotId=None, booleans=None, damage=0, shotPosition=None,
                       *args):
        if self._collectionEnabled and self._active:
            _try(lambda: self._damage.on_shell(victimId, shooterId, damage))

    def _on_artillery_ammo_changed(self, *args):
        if self._collectionEnabled and self._active:
            _try(lambda: self._ballistics.on_ammo_changed(*args))

    def _on_weapon_type_changed(self, *args):
        if self._collectionEnabled and self._active:
            _try(lambda: self._ballistics.on_weapon_changed(*args))

    def _on_squadron_activated(self, *args):
        if self._collectionEnabled and self._active:
            _try(lambda: self._ballistics.on_squadron(*args))

    def _on_squadron_deactivated(self, *args):
        if self._collectionEnabled and self._active:
            _try(lambda: self._ballistics.on_squadron_off(*args))

    # -- state output -------------------------------------------------------
    def _write_state(self, snap):
        """Emit a state snapshot. With the background writer, the game thread does
        no encoding or disk I/O at all -- it just hands off the plain dict. Without
        it, fall back to an in-place synchronous write."""
        path = self._stateFile
        if not path:
            return
        # Drop a late live frame that would overwrite the quit-written inactive
        # snapshot (tick can finish building after `_on_battle_quit`).
        if not should_write_state(self._active, snap):
            return
        w = self._writer
        if w is not None:
            try:
                w.submit(path, snap)
                return
            except:
                pass
        _write_file(path, json_dumps(snap))

    # -- per-frame (throttled) ---------------------------------------------
    def _tick(self, *args):
        if not self._active or not self._collectionEnabled:
            return
        now = _now()
        previous_now = self._diagnosticsLastNow
        try:
            clock_ok = (float(now) == float(now) and
                        float(now) != float('inf') and
                        float(now) != -float('inf'))
        except Exception:
            clock_ok = False
        if not clock_ok or (previous_now is not None and now < previous_now):
            self._diagnosticsNextDue = None
            self._diagnosticsLastSampleTs = None
            self._diagnosticsLastNow = None
            self._torpedoDepthSamplingNextDue = None
            self._torpedoDepthSamplingLastNow = None
            self._torpedoDepthSamplingDue = False
            self._torpedoStateSamplingNextDue = None
            self._torpedoStateSamplingLastNow = None
            self._torpedoStateSamplingDue = False
            if previous_now is not None and clock_ok:
                self._lastWrite = 0.0
        self._refresh_meta(now)
        if (now - self._lastWrite) < self._stateInterval:
            return
        profiler = _get(self, '_performanceProfiler')
        measure_profiler = (profiler if profiler is not None and
                            profiler.status == 'available' else None)
        self._diagnosticsSampleDue = self._diagnostics_due(now)
        self._torpedoDepthSamplingDue = self._torpedo_depth_sampling_due(now)
        self._torpedoStateSamplingDue = self._torpedo_state_sampling_due(now)
        self._lastWrite = now
        cycle = (measure_profiler.begin('state_cycle_total')
                 if measure_profiler is not None else None)
        cycle_completed = False
        try:
            snap = (measure_profiler.measure('snapshot_build_total', self._build_state, now)
                    if measure_profiler is not None else self._build_state(now))
            # Quit can land while we were building; never overwrite the terminal
            # inactive frame with a stale live snapshot.
            if not self._active:
                return
            if self._profilerEnabled:
                snap['performance'] = profiler.take_summary()
                snap['performance']['writerMode'] = (
                    'asyncHandoff' if self._writer is not None else
                    'syncEncodeWrite')
            submit = (measure_profiler.begin('submit')
                      if measure_profiler is not None else None)
            submitted = False
            try:
                self._write_state(snap)
                submitted = True
                cycle_completed = True
            finally:
                if measure_profiler is not None:
                    measure_profiler.finish(submit, submitted)
            if self._diagnosticsSampleDue:
                self._diagnosticsLastSampleTs = now
                self._diagnosticsNextDue = now + self._diagnosticsInterval
        except Exception, e:
            logError('tick failed: {}'.format(_str(e)))
        finally:
            if measure_profiler is not None:
                measure_profiler.finish(cycle, cycle_completed)
            self._diagnosticsSampleDue = False
            self._torpedoDepthSamplingDue = False
            self._torpedoStateSamplingDue = False

    def _torpedo_depth_sampling_due(self, now):
        """Schedule the independent depth-only probe without catch-up samples."""
        if not _get(self, '_torpedoDepthSamplingEnabled', False):
            self._torpedoDepthSamplingNextDue = None
            self._torpedoDepthSamplingLastNow = None
            return False
        try:
            now = float(now)
            if now != now or now == float('inf') or now == -float('inf'):
                self._torpedoDepthSamplingNextDue = None
                self._torpedoDepthSamplingLastNow = None
                return False
        except Exception:
            self._torpedoDepthSamplingNextDue = None
            self._torpedoDepthSamplingLastNow = None
            return False
        previous = self._torpedoDepthSamplingLastNow
        if previous is not None and now < previous:
            self._torpedoDepthSamplingNextDue = None
        self._torpedoDepthSamplingLastNow = now
        due = (self._torpedoDepthSamplingNextDue is None or
               now >= self._torpedoDepthSamplingNextDue)
        if due:
            interval = _get(self, '_torpedoDepthSamplingInterval', 1.0)
            try:
                interval = max(float(interval), 1.0)
            except Exception:
                interval = 1.0
            if interval != interval or interval == float('inf') or interval == -float('inf'):
                interval = 1.0
            self._torpedoDepthSamplingNextDue = now + interval
        return due

    def _torpedo_state_sampling_due(self, now):
        """Schedule independent fixed-field state sampling at no more than 1 Hz."""
        if not _get(self, '_torpedoStateSamplingEnabled', False):
            self._torpedoStateSamplingNextDue = None
            self._torpedoStateSamplingLastNow = None
            return False
        try:
            now = float(now)
            if now != now or now == float('inf') or now == -float('inf'):
                self._torpedoStateSamplingNextDue = None
                self._torpedoStateSamplingLastNow = None
                return False
        except Exception:
            self._torpedoStateSamplingNextDue = None
            self._torpedoStateSamplingLastNow = None
            return False
        previous = self._torpedoStateSamplingLastNow
        if previous is not None and now < previous:
            self._torpedoStateSamplingNextDue = None
        self._torpedoStateSamplingLastNow = now
        due = (self._torpedoStateSamplingNextDue is None or
               now >= self._torpedoStateSamplingNextDue)
        if due:
            interval = _get(self, '_torpedoStateSamplingInterval', 1.0)
            try:
                interval = max(float(interval), 1.0)
            except Exception:
                interval = 1.0
            if interval != interval or interval == float('inf') or interval == -float('inf'):
                interval = 1.0
            self._torpedoStateSamplingNextDue = now + interval
        return due

    def _diagnostics_due(self, now):
        """Schedule one complete diagnostics sample; never replay missed periods."""
        if not self._diagnosticsEnabled:
            self._diagnosticsNextDue = None
            self._diagnosticsLastSampleTs = None
            self._diagnosticsLastNow = None
            return False
        try:
            now = float(now)
            if now != now or now == float('inf') or now == -float('inf'):
                self._diagnosticsNextDue = None
                self._diagnosticsLastSampleTs = None
                self._diagnosticsLastNow = None
                return False
        except Exception:
            self._diagnosticsNextDue = None
            self._diagnosticsLastSampleTs = None
            self._diagnosticsLastNow = None
            return False
        previous = self._diagnosticsLastNow
        if previous is not None and now < previous:
            self._diagnosticsNextDue = None
            self._diagnosticsLastSampleTs = None
        self._diagnosticsLastNow = now
        due = self._diagnosticsNextDue is None or now >= self._diagnosticsNextDue
        if due:
            # Advance from actual sample time. A late tick cannot trigger catch-up.
            self._diagnosticsNextDue = now + self._diagnosticsInterval
        return due

    # -- relation helper ----------------------------------------------------
    def _self_team(self, self_info=_UNSET):
        """Self team id, memoized for the duration of one snapshot build so we
        don't hit the engine ~24x per frame (once per ship)."""
        if self._selfTeam is _UNSET:
            team = None
            if self_info is not _UNSET:
                team = _try(lambda: self_info.teamId)
            else:
                try:
                    team = battle.getSelfPlayer().teamId
                except:
                    team = _try(lambda: battle.getSelfPlayerInfo().teamId)
            self._selfTeam = team
        return self._selfTeam

    def _relation(self, teamId):
        # 0 = self team in observer? We use: 0=self,1=ally,2=enemy
        selfTeam = self._self_team()
        if selfTeam is None or teamId is None:
            return INVALID
        return 1 if teamId == selfTeam else 2

    # -- meta (static per battle) ------------------------------------------
    def _battle_info_component(self):
        """Return the BattleInfo component from whichever dataHub path is ready."""
        for getter in (
                lambda: dataHub.getSingleEntity('battleInfo')[CC.battleInfo],
                lambda: dataHub.getSingleComponent(CC.battleInfo),
                lambda: dataHub.getSingleEntity('battleData')[CC.battleInfo]):
            comp = _try(getter)
            if comp is not None:
                return comp
        for entity in _try(lambda: dataHub.getEntityCollections('battleData'), []) or []:
            comp = _try(lambda e=entity: e[CC.battleInfo])
            if comp is not None:
                return comp
        return None

    def _meta_has_precise_map(self, info):
        if not info:
            return False
        for key in ('id', 'geometryName', 'geometry', 'spaceName', 'spaceId',
                    'mapPath', 'mapName', 'name', 'arenaName'):
            if _looks_like_space(info.get(key)):
                return True
        for keys in (('minX', 'maxX', 'minZ', 'maxZ'),
                     ('minX', 'maxX', 'minY', 'maxY')):
            ok = True
            for key in keys:
                if not isinstance(info.get(key), (int, long, float)):
                    ok = False
                    break
            if ok:
                return True
        return False

    def _meta_ready_for_clients(self, meta):
        mode = meta.get('battleType') or meta.get('gameMode')
        return bool(mode) and self._meta_has_precise_map(meta.get('map') or {})

    def _refresh_meta(self, now=None, force=False):
        if not self._metaFile:
            return
        if now is None:
            now = _now()
        clock_ok = False
        now_value = 0.0
        try:
            now_value = float(now)
            clock_ok = (now_value == now_value and
                        now_value != float('inf') and
                        now_value != -float('inf'))
        except Exception:
            clock_ok = False
        if clock_ok:
            previous = _get(self, '_metaProbeLastNow')
            if previous is not None and now_value < previous:
                # A backwards clock must not leave a stale future deadline.
                self._metaProbeDue = None
            self._metaProbeLastNow = now_value
        elif not force:
            # Without a usable game clock we cannot schedule a retry; never fall
            # back to probing every frame.
            return

        probe_due = (force or _get(self, '_metaProbeDue') is None or
                     (clock_ok and now_value >= _get(self, '_metaProbeDue')))
        if probe_due:
            # Spend the retry budget before doing any work. A failed build/write
            # or a slow probe still waits the full interval (no catch-up).
            if clock_ok:
                self._metaProbeDue = now_value + META_RETRY_INTERVAL
            else:
                self._metaProbeDue = None

        within_retry = force or (not _get(self, '_metaRetryUntil')) or (
            clock_ok and now_value <= self._metaRetryUntil)
        promoted = False
        if probe_due and within_retry and (
                force or not self._battleIdentity.is_arena):
            promoted = self._promote_battle_id()
        if self._metaReady and not force and not promoted:
            return
        if not force and not probe_due:
            return
        if (not force) and not within_retry and not promoted:
            return
        if (not force) and not promoted \
                and (now_value - self._lastMetaWrite) < META_RETRY_INTERVAL:
            return
        try:
            meta = self._build_meta()
        except Exception:
            return
        if not _atomic_write(self._metaFile, json_dumps(meta)):
            return
        self._lastMetaWrite = now_value
        self._metaReady = self._meta_ready_for_clients(meta)
        if force or self._metaReady:
            logInfo('meta.json written ({} players, ready={})'.format(
                len(meta.get('roster', [])), self._metaReady))

    def _build_meta(self):
        self._selfTeam = _UNSET
        battleInfo = self._battle_info_component()
        battleType = _coerce(_get(battleInfo, 'battleType'))
        gameMode = _coerce(_get(battleInfo, 'gameMode'))
        meta = {
            'schema': SCHEMA_VERSION,
            'apiVersion': WIRE_API_VERSION,
            'battleId': self._battleId,
            'mod': {'name': MOD_NAME, 'version': MOD_VERSION},
            'ts': _now(),
            'battleType': battleType or gameMode,
            'gameMode': gameMode,
            'selfPlayerId': self._selfPlayerId,
            'map': self._build_map_info(battleInfo),
            'roster': self._build_roster(),
        }
        return meta

    def _build_map_info(self, battleInfo=None):
        """Collect the map's identity (for server-side recognition) and, when
        the client exposes them, raw world bounds.

        The server only needs a recognizable space id (e.g. ``13_OC_new_dawn``)
        to look up exact, origin-centred bounds; numeric bounds here are an
        optional bonus that takes priority when present. We probe several
        sources because attribute names vary across client builds -- whichever
        one carries the space id, the server resolver will match it.
        """
        info = {}
        # String-ish identifiers first, then any numeric bounds we can find.
        name_keys = ('geometryName', 'geometry', 'mapName', 'spaceName',
                     'spaceId', 'mapPath', 'name', 'mapId', 'arenaName')
        num_keys = ('width', 'height', 'size', 'worldSize', 'spaceBounds',
                    'bounds', 'minX', 'maxX', 'minY', 'maxY', 'minZ', 'maxZ')

        def scan(obj):
            if obj is None:
                return
            for key in name_keys + num_keys:
                if info.get(key) is not None:
                    continue
                v = _coerce(_get(obj, key))
                if v is not None:
                    info[key] = v

        # 1) arena info method on `battle`
        scan(_try(lambda: battle.getArenaInfo()))
        # 2) the battleInfo component (same entity used for battleType)
        scan(battleInfo if battleInfo is not None else self._battle_info_component())
        # 3) mapInfo and dataHub arena/space entities
        mapId = info.get('mapId')
        mapEnt = _try(lambda: dataHub.getPrimaryEntity(CC.mapInfo, mapId))
        scan(_try(lambda: mapEnt[CC.mapInfo]))
        for ename in ('arena', 'arenaInfo', 'minimap', 'space', 'spaceInfo'):
            ent = _try(lambda e=ename: dataHub.getSingleEntity(e))
            if ent is None:
                continue
            scan(_try(lambda e=ename, x=ent: x[getattr(CC, e)]))

        # Promote the first space-looking value to `id`: the recognition key
        # the server uses to resolve the friendly name and exact bounds.
        for key in ('geometryName', 'geometry', 'mapName', 'spaceName',
                    'spaceId', 'mapPath', 'name', 'mapId'):
            if _looks_like_space(info.get(key)):
                info['id'] = info[key]
                break
        return info

    def _build_roster(self):
        roster = {}
        # avatars: team / ship class / ship name / tier
        for entity in _try(lambda: dataHub.getEntityCollections('avatar'), []) or []:
            a = _try(lambda: entity[CC.avatar])
            if a is None:
                continue
            pid = _try(lambda: a.playerId)
            if pid is None:
                pid = _try(lambda: a.id)
            if pid is None:
                continue
            rec = roster.setdefault(pid, {'playerId': pid})
            rec['teamId'] = _try(lambda: a.teamId)
            rec['relation'] = self._relation(rec['teamId'])
            rec['name'] = _try(lambda: a.name)
            rec['shipType'] = _try(lambda: a.shipType)
            rec['shipName'] = _try(lambda: a.ship.ref.ship.fullName)
            rec['shipTier'] = _try(lambda: a.ship.ref.ship.level)
        # shipBattleInfo: consumables (ranges & cooldowns)
        for entity in _try(lambda: dataHub.getEntityCollections('shipBattleInfo'), []) or []:
            s = _try(lambda: entity[CC.shipBattleInfo])
            if s is None:
                continue
            pid = _try(lambda: s.playerId)
            if pid is None:
                continue
            rec = roster.setdefault(pid, {'playerId': pid})
            cons = self._extract_consumables(s)
            if cons:
                rec['consumables'] = cons
        return list(roster.values())

    def _extract_consumables(self, ship):
        out = []
        main = _try(lambda: list(ship.mainConsumables), []) or []
        alt = _try(lambda: [c for lst in ship.altConsumables for c in lst], []) or []
        for cons in (main + alt):
            title = _try(lambda: cons.title)
            if title is None:
                continue
            item = {'title': title, 'abilityId': _try(lambda: cons.abilityId)}
            params = {}
            for cat in ('activeAttributes', 'usageAttributes'):
                catObj = _try(lambda: getattr(cons, cat))
                if catObj is None:
                    continue
                for typ in ('neutral', 'positive', 'negative'):
                    lst = _try(lambda: getattr(catObj, typ))
                    if not lst:
                        continue
                    for attr in lst:
                        name = _try(lambda: attr.paramName)
                        if name is None:
                            continue
                        val = _try(lambda: attr.measuredValue)
                        if val is None:
                            val = _try(lambda: attr.numericValue)
                        params[name] = val
            if params:
                item['params'] = params
            out.append(item)
        return out

    # -- state (per frame) --------------------------------------------------
    def _capture_avatar_snapshot(self):
        """Capture one bounded, fresh avatar view for this state build only."""
        limit = 256
        try:
            entities = dataHub.getEntityCollections('avatar')
        except Exception:
            return {'entities': [], 'status': 'partial', 'count': 0,
                    'limit': limit, 'reason': 'getterError'}
        if entities is None:
            return {'entities': [], 'status': 'partial', 'count': 0,
                    'limit': limit, 'reason': 'none'}
        rows = AvatarRows(complete=False)
        try:
            for index, entity in enumerate(entities):
                if index >= limit:
                    return {'entities': rows, 'status': 'truncated',
                            'count': len(rows), 'limit': limit,
                            'reason': 'rowLimit'}
                rows.append(entity)
        except Exception:
            return {'entities': rows, 'status': 'partial',
                    'count': len(rows), 'limit': limit,
                    'reason': 'iterationError'}
        rows.complete = True
        return {'entities': rows, 'status': 'complete',
                'count': len(rows), 'limit': limit, 'reason': None}

    def _build_state(self, now):
        self._selfTeam = _UNSET   # recompute self team once for this frame
        # Capture fresh self API results once per state; None is a captured
        # unknown, not a request to retry in another consumer.
        profiler = getattr(self, '_performanceProfiler', None)
        if profiler is not None and profiler.status != 'available':
            profiler = None
        if profiler is not None:
            def capture_self():
                info = _try(lambda: battle.getSelfPlayerInfo())
                ship = _try(lambda: battle.getSelfPlayerShip())
                return info, ship, self._self_team(info)
            self_info, self_ship, self_team = profiler.measure('self', capture_self)
        else:
            self_info = _try(lambda: battle.getSelfPlayerInfo())
            self_ship = _try(lambda: battle.getSelfPlayerShip())
            self_team = self._self_team(self_info)
        diagnostic_enabled = _get(self, '_diagnosticsEnabled', False) is True
        diagnostic_due = diagnostic_enabled and _get(
            self, '_diagnosticsSampleDue', False) is True
        depth_sampling_enabled = _get(
            self, '_torpedoDepthSamplingEnabled', False) is True
        depth_sampling_due = depth_sampling_enabled and _get(
            self, '_torpedoDepthSamplingDue', False) is True
        state_sampling_enabled = _get(
            self, '_torpedoStateSamplingEnabled', False) is True
        state_sampling_due = state_sampling_enabled and _get(
            self, '_torpedoStateSamplingDue', False) is True
        state_provider = _get(self, '_torpedoStateProvider', 'unknown')
        if state_provider != 'advanced_torpedo_marker':
            state_provider = 'unknown'
        state_value_kind = ('thirdPartyDerived'
                            if state_provider == 'advanced_torpedo_marker'
                            else 'unknown')
        avatar_phase = profiler.begin('avatar') if profiler is not None else None
        avatar_snapshot = self._capture_avatar_snapshot()
        avatar_entities = avatar_snapshot['entities']
        players_sample = self._remember_roster_vehicles(avatar_entities)
        # Partial captures expose raw health only for captured entities. Their
        # incomplete health index remains empty, so absence cannot assert life.
        if avatar_snapshot['status'] == 'complete':
            ui_hp = self._collect_avatar_health(avatar_entities)
        else:
            sample_health = getattr(avatar_entities, 'sample_health', None)
            if sample_health is not None:
                _try(lambda: sample_health(CC))
            ui_hp = self._collect_avatar_health([])
        if profiler is not None:
            profiler.finish(avatar_phase)

        if profiler is not None:
            def build_ships_and_avatar_observations():
                built_ships, built_diag = self._build_ships(
                    now, ui_hp, avatar_entities, players_sample)
                observations = self._build_avatar_observations(
                    avatar_snapshot, now, built_ships)
                return built_ships, built_diag, observations

            ships, diag, avatar_observations = profiler.measure(
                'ships', build_ships_and_avatar_observations)
        else:
            ships, diag = self._build_ships(
                now, ui_hp, avatar_entities, players_sample)
            avatar_observations = self._build_avatar_observations(
                avatar_snapshot, now, ships)
        diag['avatarSnapshotStatus'] = {
            'status': avatar_snapshot['status'], 'count': avatar_snapshot['count'],
            'limit': avatar_snapshot['limit'], 'reason': avatar_snapshot['reason']}
        torpedoes_phase = profiler.begin('torpedoes') if profiler is not None else None
        torpedoes, torpedo_status = _try(
            lambda: self._torpedoes.torpedoes(self_team),
            ([], {'available': False, 'status': 'unknown',
                   'source': 'battle.getAllTorpedoes'}))
        diagnostic_hub = None
        if diagnostic_due or depth_sampling_due or state_sampling_due:
            diagnostic_hub = _try(
                lambda: shared_diagnostic_snapshot(dataHub), None)
        if diagnostic_due:
            probe = _try(lambda: ui_torpedo_probe_without_state(
                              diagnostic_hub, CC, torpedoes),
                          {'status': 'unknown', 'source': 'dataHub.torpedo'})
            _try(lambda: attach_ui_state(
                torpedoes, probe, torpedo_status.get('status')))
        else:
            probe = ({'status': 'notSampled', 'source': 'scheduling',
                      'sampleTs': None, 'rows': []} if diagnostic_enabled else
                     {'status': 'disabled', 'source': 'config.diagnostics_enabled',
                      'rows': []})
        if depth_sampling_due:
            depth_probe = _try(lambda: ui_torpedo_depth_probe(
                                   diagnostic_hub, CC),
                {'source': 'dataHub.torpedo.depth', 'status': 'unknown',
                 'semantics': 'unverified', 'rows': [],
                 'collection': {'status': 'unknown', 'count': 0,
                     'limit': 64, 'truncated': False, 'partial': False,
                     'reason': 'probeFailed'}})
            _try(lambda: attach_ui_depth_state(
                torpedoes, depth_probe, torpedo_status.get('status')))
            depth_probe['sampleTs'] = now
            depth_probe['intervalSeconds'] = _get(
                self, '_torpedoDepthSamplingInterval', 1.0)
        else:
            depth_probe = {
                'source': 'dataHub.torpedo.depth',
                'status': ('notSampled' if depth_sampling_enabled else 'disabled'),
                'producer': 'unknown', 'semantics': 'unverified',
                'sampleTs': None,
                'intervalSeconds': _get(self, '_torpedoDepthSamplingInterval', 1.0),
                'collection': {'status': ('notSampled' if depth_sampling_enabled
                                           else 'disabled'),
                    'count': 0, 'limit': 64, 'truncated': False,
                    'partial': False, 'reason': None},
                'componentKeyStatus': 'notSampled', 'rows': []}
        if state_sampling_due:
            torpedo_state_probe = _try(lambda: ui_torpedo_state_probe(
                diagnostic_hub, CC, state_provider),
                {'source': 'ui.mods_DataComponent.data', 'producer': 'unknown',
                 'semantics': 'unverified', 'status': 'unknown',
                 'componentKeyStatus': 'unknown', 'rows': [],
                 'collection': {'status': 'unknown', 'count': 0,
                     'limit': 64, 'truncated': False, 'partial': False,
                     'reason': 'probeFailed'}, 'joinStatus': 'notAttempted',
                 'declaredProducer': state_provider,
                 'producerVerification': 'notVerified',
                 'valueKind': state_value_kind})
            _try(lambda: attach_ui_torpedo_state(
                torpedoes, torpedo_state_probe, torpedo_status.get('status')))
            torpedo_state_probe['sampleTs'] = now
            torpedo_state_probe['intervalSeconds'] = _get(
                self, '_torpedoStateSamplingInterval', 1.0)
        else:
            torpedo_state_probe = {
                'source': 'ui.mods_DataComponent.data', 'producer': 'unknown',
                'semantics': 'unverified',
                'status': ('notSampled' if state_sampling_enabled else 'disabled'),
                'sampleTs': None,
                'intervalSeconds': _get(
                    self, '_torpedoStateSamplingInterval', 1.0),
                'componentKeyStatus': 'notSampled',
                'collection': {'status': ('notSampled' if state_sampling_enabled
                                           else 'disabled'),
                    'count': 0, 'limit': 64, 'truncated': False,
                    'partial': False, 'reason': None},
                'rows': [], 'joinStatus': 'notAttempted',
                'declaredProducer': state_provider,
                'producerVerification': 'notVerified',
                'valueKind': state_value_kind}
        _try(lambda: self._torpedoMotion.update(
            torpedoes, now, torpedo_status.get('available', False)))
        for torpedo in torpedoes:
            pos = torpedo.get('position')
            normalized = (_try(lambda: self._mapCalibration.world_to_map(pos[0], pos[2]))
                          if pos else None)
            torpedo['mapPosition'] = normalized
            torpedo['mapPositionStatus'] = 'available' if normalized else 'unknown'
            torpedo['mapPositionSource'] = 'calibratedWorldPosition' if normalized else None
        if profiler is not None:
            profiler.finish(torpedoes_phase)
        disabled = {'status': 'disabled', 'source': 'config.diagnostics_enabled'}
        unsampled = {'status': 'notSampled', 'source': 'scheduling',
                     'sampleTs': None}
        diagnostics_phase = (profiler.begin('diagnostics_due')
                             if profiler is not None and diagnostic_due else None)
        if diagnostic_due:
            weapon_probe = _try(lambda: safe_weapon_hub_probe(diagnostic_hub, CC),
                {'source': 'dataHub weapon UI candidates', 'status': 'unknown',
                 'semantics': 'unverified', 'collections': {}})
            weapon_context = _try(lambda: safe_weapon_context_probe(diagnostic_hub, CC),
                {'source': 'dataHub selfVehicle weapon UI context',
                 'status': 'unknown', 'semantics': 'unverified'})
            game_clock = _try(lambda: safe_game_clock_probe(diagnostic_hub, CC),
                {'source': 'dataHub UI game clock candidates',
                 'status': 'unknown', 'semantics': 'unverified', 'candidates': {}})
            gun_reload = _try(lambda: safe_gun_reload_probe(diagnostic_hub, CC),
                {'source': 'dataHub UI gun reload candidates', 'status': 'unknown',
                 'semantics': 'unverified', 'collections': {}, 'references': [],
                 'error': 'probeFailed'})
            selected_torpedo_params = _try(
                lambda: safe_selected_torpedo_params_probe(
                    diagnostic_hub, CC, weapon_context, weapon_probe),
                {'source': 'dataHub selfVehicle shipTTX torpedo candidates',
                 'status': 'unknown', 'semantics': 'unverified',
                 'selection': {'status': 'unknown', 'descriptor': None},
                 'selfVehicle': {'status': 'unknown'}, 'variant': None,
                 'fields': {}, 'variants': {}, 'error': 'probeFailed'})
            torpedo_tooltip_parameter = _try(
                lambda: safe_torpedo_tooltip_parameter_probe(
                    diagnostic_hub, CC, selected_torpedo_params),
                {'source': 'dataHub playerAvatar owner + parameter candidates',
                 'status': 'unknown', 'semantics': 'unverified',
                 'ownerEntityId': {'status': 'unknown'},
                 'parameterCollection': {'status': 'unknown', 'rows': []},
                 'selectedParameter': {'status': 'unknown',
                    'reason': 'probeFailed', 'fields': {}},
                 'stages': {'owner': 'unknown', 'parameterCollection': 'unknown',
                    'match': 'unknown'}})
            submarine_probes = _try(lambda: safe_submarine_probe(diagnostic_hub, CC, now),
                {'selfSubmarineProbe': {'source': 'dataHub.selfVehicle',
                    'status': 'unknown', 'semantics': 'unverified',
                    'sampleTs': now, 'collection': {}, 'entityIdCandidate': None,
                    'components': {}},
                 'waveHitProbe': {'source': 'dataHub.waveHit', 'status': 'unknown',
                    'semantics': 'unverified', 'sampleTs': now, 'collection': {},
                    'componentKeyStatus': 'unknown', 'rows': [],
                    'truncated': False, 'partial': False}})
            for _probe in (weapon_context, game_clock):
                for _observation in _get(_probe, 'observations', {}).values():
                    _observation['sampleTs'] = now
        else:
            state = unsampled if diagnostic_enabled else disabled
            weapon_probe = dict(state)
            weapon_context = dict(state)
            game_clock = dict(state)
            gun_reload = dict(state)
            selected_torpedo_params = dict(state)
            torpedo_tooltip_parameter = dict(state)
            submarine_probes = {'selfSubmarineProbe': dict(state),
                                'waveHitProbe': dict(state)}
        if profiler is not None and diagnostic_due:
            profiler.finish(diagnostics_phase)
        self_state = self._build_self(ui_hp, self_info, self_ship)
        if diagnostic_due:
            identity_candidates_state = _try(
                lambda: safe_identity_candidates(ships, self_state, torpedoes,
                    submarine_probes['waveHitProbe']), dict(disabled))
        else:
            identity_candidates_state = dict(unsampled if diagnostic_enabled else disabled)
        if diagnostic_due:
            for _sample in (probe, weapon_probe, weapon_context, game_clock,
                            gun_reload, selected_torpedo_params,
                            torpedo_tooltip_parameter,
                            submarine_probes['selfSubmarineProbe'],
                            submarine_probes['waveHitProbe'],
                            identity_candidates_state):
                if isinstance(_sample, dict):
                    _sample['sampleTs'] = now
        if profiler is not None:
            def build_armament_systems():
                return (_try(lambda: self._torpedoes.armament(self_ship),
                             {'available': False}),
                        _try(lambda: self._torpedoes.systems(self_ship),
                             {'status': 'unknown'}))
            armament_systems = profiler.measure(
                'armament_systems', build_armament_systems)
        else:
            armament_systems = (
                _try(lambda: self._torpedoes.armament(self_ship), {'available': False}),
                _try(lambda: self._torpedoes.systems(self_ship), {'status': 'unknown'}))
        return {
            'schema': SCHEMA_VERSION,
            'apiVersion': WIRE_API_VERSION,
            'battleId': self._battleId,
            'active': bool(self._active),
            'ts': now,
            'self': self_state,
            'ships': ships,
            'avatarObservations': avatar_observations,
            'torpedoes': torpedoes,
            'identityCandidates': identity_candidates_state,
            'torpedoStatus': torpedo_status,
            'uiTorpedoProbe': probe,
            'torpedoDepthProbe': depth_probe,
            'torpedoStateProbe': torpedo_state_probe,
            'weaponHubProbe': weapon_probe,
            'gunReloadProbe': gun_reload,
            'weaponContextProbe': weapon_context,
            'selectedTorpedoParamsProbe': selected_torpedo_params,
            'torpedoTooltipParameterProbe': torpedo_tooltip_parameter,
            'selfSubmarineProbe': submarine_probes['selfSubmarineProbe'],
            'waveHitProbe': submarine_probes['waveHitProbe'],
            'gameClockProbe': game_clock,
            'torpedoArmament': armament_systems[0],
            'selfSystems': armament_systems[1],
            'damage': self._damage.snapshot(),
            'ballistics': _try(lambda: self._ballistics.snapshot(), {'available': False}),
            'diag': diag,
        }

    def _build_avatar_observations(self, avatar_snapshot, now, ships):
        """Report only current captured-avatar fields, separate from API ships."""
        entities = avatar_snapshot.get('entities', []) or []
        input_status = avatar_snapshot.get('status', 'unknown')
        input_complete = input_status == 'complete'
        sample_reader = getattr(entities, 'sample_ids', None)
        sample = _try(lambda: sample_reader(CC)) if sample_reader is not None else None
        sample_rows = sample.get('rows', []) if isinstance(sample, dict) else []

        ship_counts = {}
        for ship in ships or []:
            player_id = ship.get('playerId') if isinstance(ship, dict) else None
            key = _strict_player_lookup_key(player_id)
            if key is None:
                continue
            ship_counts[key] = ship_counts.get(key, 0) + 1

        observation_ids = {}
        candidate_ids = {}
        row_ids = []
        for index in range(len(entities)):
            row = sample_rows[index] if index < len(sample_rows) else {}
            avatar = row.get('avatar') if isinstance(row, dict) else None
            # avatar.id remains separate and is never a fallback for the
            # confirmed observation-to-ships join.
            player_id = avatar.get('playerId') if isinstance(avatar, dict) else None
            key = _strict_player_lookup_key(player_id)
            safe_id = _observation_scalar(player_id) if key is not None else None
            if safe_id is None:
                key = None
            # This candidate comes from the already shared AvatarRows sample.
            # Do not reread the game component or use it for confirmed joins.
            avatar_id = (avatar.get('id', _UNSET)
                         if isinstance(avatar, dict) else _UNSET)
            candidate_key = _strict_player_lookup_key(avatar_id)
            candidate_id = (_observation_scalar(avatar_id)
                            if candidate_key is not None else None)
            if candidate_id is None:
                candidate_key = None
                candidate_status = 'unknown'
                candidate_reason = ('notRecorded' if avatar_id is _UNSET or
                                    avatar_id is None else 'invalidId')
            else:
                candidate_status = 'available'
                candidate_reason = None
            row_ids.append((key, safe_id, candidate_key, candidate_id,
                            candidate_status, candidate_reason, row))
            if key is not None:
                observation_ids[key] = observation_ids.get(key, 0) + 1
            if candidate_key is not None:
                candidate_ids[candidate_key] = candidate_ids.get(candidate_key, 0) + 1

        conflicts = set(key for key, count in observation_ids.items() if count > 1)
        conflicts.update(key for key, count in ship_counts.items() if count > 1)
        candidate_conflicts = set(
            key for key, count in candidate_ids.items() if count > 1)
        candidate_ship_conflicts = set(
            key for key, count in ship_counts.items() if count > 1)
        candidate_available = candidate_exact = candidate_unmatched = 0
        candidate_ambiguous = candidate_unknown = 0
        for (_key, _player_id, candidate_key, _candidate_id, _status,
             _reason, _row) in row_ids:
            if candidate_key is None:
                candidate_unknown += 1
            else:
                candidate_available += 1
                if (candidate_key in candidate_conflicts or
                        candidate_key in candidate_ship_conflicts):
                    candidate_ambiguous += 1
                elif candidate_key in ship_counts:
                    candidate_exact += 1
                else:
                    candidate_unmatched += 1

        out_rows = []
        matched = missing = unknown = unmatchable = 0
        map_available = health_available = 0
        for (key, player_id, candidate_key, candidate_id,
             candidate_status, candidate_reason, sampled) in row_ids:
            row = {}
            if key is None:
                row['playerIdStatus'] = 'unknown'
                row['apiPresence'] = {'status': 'unknown', 'source': 'state.ships',
                                      'reason': 'unmatchablePlayerId'}
                unmatchable += 1
                unknown += 1
            else:
                row['playerId'] = player_id
                row['playerIdStatus'] = 'available'
                if key in conflicts:
                    row['apiPresence'] = {'status': 'unknown', 'source': 'state.ships',
                                          'reason': 'duplicateIdConflict'}
                    unknown += 1
                elif key in ship_counts:
                    row['apiPresence'] = {'status': 'matched', 'source': 'state.ships'}
                    matched += 1
                elif input_complete:
                    row['apiPresence'] = {'status': 'missingInApi',
                                          'source': 'state.ships'}
                    missing += 1
                else:
                    row['apiPresence'] = {'status': 'unknown', 'source': 'state.ships',
                                          'reason': 'inputIncomplete'}
                    unknown += 1

            candidate = {
                'source': 'dataHub.avatar.id',
                'namespace': 'avatar.id',
                'status': candidate_status,
                'semantics': 'unverified',
            }
            if candidate_key is not None:
                candidate['raw'] = candidate_id
            else:
                candidate['reason'] = candidate_reason
            row['identifierCandidates'] = {'avatarId': candidate}

            map_sample = sampled.get('mapPosition') if isinstance(sampled, dict) else None
            if isinstance(map_sample, dict):
                map_row = dict(map_sample)
            else:
                map_row = {
                    'status': 'unknown', 'source': 'dataHub.mapPosition',
                    'componentStatus': 'ccKeyMissing' if CC is None else 'notSampled',
                    'reason': 'ccUnavailable' if CC is None else 'notSampled',
                    'freshness': 'unknown',
                    'raw': [None, None], 'nx': None, 'ny': None,
                }
            if map_row.get('status') == 'available':
                map_available += 1
            row['mapPosition'] = map_row

            health_sample = sampled.get('health') if isinstance(sampled, dict) else None
            health_observation = (sampled.get('healthObservation')
                                 if isinstance(sampled, dict) else None)
            if isinstance(health_sample, dict):
                raw = {name: _observation_scalar(health_sample.get(name))
                       for name in ('value', 'max', 'isAlive')}
                health_observation = (health_observation
                                      if isinstance(health_observation, dict) else {})
                field_status = dict(health_observation.get('fieldStatus', {}))
                component_status = health_observation.get('componentStatus', 'unknown')
                for name in raw:
                    if health_sample.get(name) is not None and raw[name] is None:
                        field_status[name] = 'unsafeScalar'
                has_raw = any(raw[name] is not None for name in raw)
                safe_normalized = None
                normalizable = all(
                    health_sample.get(name) is None or raw[name] is not None
                    for name in ('value', 'max', 'isAlive'))
                normalized = (normalize_ui_health(
                    health_sample.get('value'), health_sample.get('max'),
                    health_sample.get('isAlive')) if normalizable else None)
                if isinstance(normalized, dict):
                    safe_normalized = {}
                    for name, value in normalized.items():
                        safe_value = _observation_scalar(value)
                        if safe_value is not None:
                            safe_normalized[name] = safe_value
                    if not safe_normalized:
                        safe_normalized = None
                health_status = 'available' if has_raw else 'unknown'
            else:
                raw = {'value': None, 'max': None, 'isAlive': None}
                field_status = {'value': 'notSampled', 'max': 'notSampled',
                                'isAlive': 'notSampled'}
                component_status = 'ccKeyMissing' if CC is None else 'notSampled'
                safe_normalized = None
                health_status = 'unknown'
            if health_status == 'available':
                health_available += 1
            row['health'] = {
                'status': health_status,
                'source': 'dataHub.avatar.health',
                'componentStatus': component_status,
                'fieldStatus': field_status,
                'raw': raw,
                'normalized': safe_normalized,
            }
            out_rows.append(row)

        return {
            'status': input_status,
            'source': 'dataHub.getEntityCollections(avatar)',
            'sampleTs': _observation_scalar(now),
            'rows': out_rows,
            'candidateConsistency': {
                'source': 'sameSnapshot.avatar.id == state.ships[].playerId',
                'candidateNamespace': 'avatar.id',
                'comparedNamespace': 'ships[].playerId',
                'comparison': 'strictScalarTypeAndValue',
                'semantics': 'unverified',
                'avatarInputComplete': input_complete,
                'shipsCompleteness': 'unknown',
                'candidateAvailableCount': candidate_available,
                'candidateExactValueMatchCount': candidate_exact,
                'candidateUnmatchedInSnapshotCount': candidate_unmatched,
                'candidateAmbiguousCount': candidate_ambiguous,
                'candidateUnknownCount': candidate_unknown,
                'duplicateAvatarIdCount': len(candidate_conflicts),
                'duplicateShipPlayerIdCount': len(candidate_ship_conflicts),
            },
            'coverage': {
                'sampledEntityCount': len(entities),
                'inputStatus': input_status,
                'inputComplete': input_complete,
                'inputAvailability': ('unavailable' if avatar_snapshot.get(
                    'reason') in ('getterError', 'none') else
                    ('available' if input_status in ('complete', 'partial', 'truncated')
                     else 'unknown')),
                'reason': avatar_snapshot.get('reason'),
                'limit': avatar_snapshot.get('limit'),
                'distinctPlayerIdCount': len(observation_ids),
                'apiMatchedCount': matched,
                'missingInApiCount': missing,
                'apiPresenceUnknownCount': unknown,
                'unmatchableIdCount': unmatchable,
                'duplicateIdConflictCount': len(conflicts),
                'mapPositionAvailableCount': map_available,
                'healthRawAvailableCount': health_available,
            },
        }

    def _collect_avatar_health(self, entities=None):
        """Live HP from the same dataHub `health` component TTaroTeamPanel binds."""
        if CC is None:
            return {}
        sample_reader = getattr(entities, 'sample_health', None)
        if sample_reader is not None:
            return index_avatar_health_sample(
                _try(lambda: sample_reader(CC)) or [])
        if entities is None:
            entities = _try(lambda: dataHub.getEntityCollections('avatar'), []) or []
        return index_avatar_health(entities, CC)

    def _build_self(self, ui_hp=None, self_info=_UNSET, self_ship=_UNSET):
        info = (_try(lambda: battle.getSelfPlayerInfo())
                if self_info is _UNSET else self_info)
        data = {}
        if info is not None:
            data['playerId'] = _try(lambda: info.id)
            data['teamId'] = _try(lambda: info.teamId)
            gd = _try(lambda: info.shipGameData)
            if gd is not None:
                for k in ('health', 'maxHealth', 'yaw', 'speed', 'isVisible', 'isShipVisible'):
                    v = _try(lambda: gd[k]) if _is_mapping(gd) else _try(lambda: getattr(gd, k))
                    if v is not None:
                        data[k] = v
        ship = (_try(lambda: battle.getSelfPlayerShip())
                if self_ship is _UNSET else self_ship)
        if ship is None:
            ship = _try(lambda: battle.getObserverShip())
        if ship is not None:
            pos = _vec(_try(lambda: ship.getPosition()))
            if pos:
                data['position'] = pos
            for k in ('health', 'maxHealth', 'yaw'):
                if k not in data:
                    v = _try(lambda: getattr(ship, k))
                    if v is not None:
                        data[k] = v
        data['isObserver'] = _try(lambda: battle.isObserverMode(), False)
        apply_ui_health(data, ui_hp)
        return data if data else None

    def _position_from_obj(self, obj, skip_get_position=False):
        """Extract world position from a ship-like object or mapping."""
        if obj is None:
            return None
        missing = object()
        names = (('position', 'worldPosition', 'positionHull') if skip_get_position
                 else ('getPosition', 'position', 'worldPosition', 'positionHull'))
        for name in names:
            result = 'missing'
            raw = None
            try:
                raw = getattr(obj, name, missing)
                result = 'missing' if raw is missing else ('none' if raw is None else 'value')
                if raw is missing:
                    raw = None
            except Exception:
                result = 'error'
            if result == 'value' and name == 'getPosition' and callable(raw):
                try:
                    raw = raw()
                    result = 'none' if raw is None else 'value'
                except Exception:
                    raw = None
                    result = 'error'
            pos = _vec(raw)
            if result == 'value':
                result = 'available' if pos else 'invalidVector'
            attempts = getattr(self, '_positionDiagnostics', None)
            if attempts is not None:
                key = name + ':' + result
                attempts[key] = attempts.get(key, 0) + 1
            if pos:
                return pos
        gd = _get(obj, 'shipGameData')
        if gd is not None:
            for key in ('position', 'worldPosition'):
                if _is_mapping(gd):
                    pos = _vec(_try(lambda k=key: gd[k]))
                else:
                    pos = _vec(_try(lambda k=key: getattr(gd, k)))
                if pos:
                    return pos
            if _is_mapping(gd):
                try:
                    if gd.get('x') is not None and gd.get('z') is not None:
                        y = gd.get('y', 0.0)
                        return [float(gd['x']), float(y), float(gd['z'])]
                except:
                    pass
        if _is_mapping(obj):
            for key in ('position', 'worldPosition'):
                pos = _vec(_try(lambda k=key: obj[k]))
                if pos:
                    return pos
        return None

    def _get_ship_position(self, ship, playerId=None, vehId=None, player=_UNSET,
                           allow_fallback=False):
        """Read the public ship getter once; expensive legacy paths are sampled only."""
        direct = None
        # Read getPosition exactly once; do not let a failing/None getter trigger
        # another lookup or a second call on the same ship object.
        missing = object()
        attr_error = False
        try:
            getter = getattr(ship, 'getPosition', missing) if ship is not None else missing
        except Exception:
            getter = None
            attr_error = True
        status = 'error' if attr_error else 'missing'
        raw = None
        if getter is None and not attr_error:
            status = 'none'
        elif getter is not missing and not attr_error:
            try:
                raw = getter() if callable(getter) else getter
                status = 'none' if raw is None else 'value'
            except Exception:
                status = 'error'
        pos = _vec(raw)
        if pos:
            status = 'available'
            direct = pos
        elif status == 'value':
            status = 'invalidVector'
        attempts = getattr(self, '_positionDiagnostics', None)
        if attempts is not None:
            key = 'getPosition:' + status
            attempts[key] = attempts.get(key, 0) + 1
        details = {'status': 'available' if direct else 'unknown',
                   'source': 'ship.getPosition',
                   'attempted': True, 'reason': None if direct else status,
                   'policy': 'diagnosticExtendedFallback' if allow_fallback else
                              'coreDirectOnly',
                   'fallbackStatus': 'notSampled', 'fallbackSource': None}
        if direct:
            return direct, details
        if not allow_fallback:
            return None, details
        details['fallbackStatus'] = 'attempted'

        # The extended compatibility search is intentionally 1Hz diagnostic-only.
        # Never perform a second getPlayerByVehicleId lookup: None and exceptions
        # from the caller's lookup are final for this frame.
        candidates = [(lambda: ship, True)]
        if playerId is not None:
            candidates.extend([(lambda: _try(
                lambda: battle.getPlayerShipInfo(playerId)), False),
                               (lambda: _try(
                lambda: battle.getPlayerInfo(playerId)), False)])
        if player is not _UNSET and player is not None:
            candidates.append((lambda: player, False))
            pid = _get(player, 'id')
            if pid is not None and pid != playerId:
                candidates.extend([(lambda: _try(
                    lambda: battle.getPlayerShipInfo(pid)), False),
                                   (lambda: _try(
                    lambda: battle.getPlayerInfo(pid)), False)])
        for candidate_getter, skip_getter in candidates:
            # ship/player getPosition was already read once above/on the direct
            # object; only the historical non-getPosition candidates are retried.
            candidate = candidate_getter()
            found = self._position_from_obj(candidate, skip_get_position=skip_getter)
            if found:
                details.update({'fallbackSource': 'diagnosticFallback',
                                'fallbackStatus': 'available'})
                return found, details
        details['fallbackStatus'] = 'unknown'
        return None, details

    def _collect_map_positions(self, avatar_entities=None):
        """Map playerId -> (mapX, mapY, mapYaw) from each ship entity's
        mapPosition component.

        ship.getPosition() and the worldPosition component are only populated for
        ships rendered in our own 3D bubble. The mapPosition component, however, is
        populated for EVERY ship drawn on the minimap -- including enemies spotted
        only by a teammate. Its `position` is a 2D Point in minimap space, which we
        convert to world coordinates via a per-battle calibration (see
        _fit_map_transform)."""
        out = {}
        self._mapVisibility = {}
        self._mapVisibilityDiagnostics = {}
        if CC is None:
            return out
        mpKey = _get(CC, 'mapPosition')
        avKey = _get(CC, 'avatar')
        visKey = _get(CC, 'visibility')
        if avatar_entities is None:
            avatar_entities = _try(
                lambda: dataHub.getEntityCollections('avatar'), []) or []
        sample_reader = getattr(avatar_entities, 'sample_ids', None)
        sample = (_try(lambda: sample_reader(CC))
                  if sample_reader is not None else None)
        sample_rows = sample['rows'] if sample is not None else None

        def read_map_position(entity, sample_row, keep_map_yaw):
            if mpKey is None:
                component = None
                component_status = 'ccKeyMissing'
            else:
                try:
                    component = entity[mpKey]
                    component_status = ('componentMissing' if component is None
                                        else 'available')
                except Exception as error:
                    component = None
                    component_status = (
                        'componentMissing' if _observation_exception_name(error)
                        in ('KeyError', 'IndexError') else 'componentReadError')
            position = None
            position_status = component_status
            xy = None
            yaw = None
            if component_status == 'available':
                position, position_status = _observation_field(component, 'position')
                if position_status == 'available':
                    xy = _point_xy(position)
                    if xy is None:
                        position_status = 'invalidCoordinates'
                    elif keep_map_yaw:
                        yaw = _get(component, 'yaw')
            raw = [None, None]
            nx = ny = None
            position_valid = False
            if xy is not None:
                raw = [_observation_scalar(xy[0]), _observation_scalar(xy[1])]
                position_valid = raw[0] is not None and raw[1] is not None
                if position_valid:
                    normalized = _map_norm_xy(xy[0], xy[1])
                    if normalized is not None:
                        nx, ny = normalized
                else:
                    position_status = 'nonFiniteCoordinates'
            map_row = {
                'status': 'available' if position_valid else 'unknown',
                'source': 'dataHub.mapPosition',
                'componentStatus': component_status,
                'positionStatus': position_status,
                'reason': None if position_valid else position_status,
                'freshness': 'unknown',
                'raw': raw,
                'nx': nx,
                'ny': ny,
            }
            if sample_row is not None:
                sample_row['mapPosition'] = map_row
            return (xy, yaw)

        for index, entity in enumerate(avatar_entities or []):
            sample_row = (sample_rows[index] if sample_rows is not None and
                          index < len(sample_rows) else None)
            if sample_rows is not None and index < len(sample_rows):
                avatar = sample_row.get('avatar') if sample_row is not None else None
                pid = avatar.get('playerId') if avatar is not None else None
                if pid is None and avatar is not None:
                    pid = avatar.get('id')
            else:
                a = (_try(lambda e=entity: e[avKey]) if avKey is not None else None)
                pid = _get(a, 'playerId') if a is not None else None
                if pid is None and a is not None:
                    pid = _get(a, 'id')

            if pid is not None:
                if (_get(self, '_diagnosticsEnabled', False) is not True or
                        _get(self, '_diagnosticsSampleDue', True) is not True):
                    self._mapVisibility[pid] = {}
                    self._mapVisibilityDiagnostics[pid] = {
                        'status': ('notSampled' if _get(
                            self, '_diagnosticsEnabled', False) is True else 'disabled'),
                        'source': ('scheduling' if _get(
                            self, '_diagnosticsEnabled', False) is True else
                            'config.diagnostics_enabled'), 'sampleTs': None}
                else:
                    raw_visibility = {}
                    candidate_diagnostics = {}
                    vis = None
                    visibility_component_status = 'available'
                    if visKey is None:
                        visibility_component_status = 'ccKeyMissing'
                    else:
                        try:
                            vis = entity[visKey]
                            if vis is None:
                                visibility_component_status = 'componentMissing'
                        except KeyError:
                            visibility_component_status = 'componentMissing'
                        except Exception:
                            visibility_component_status = 'componentReadError'
                    for name in ('mapVisible', 'visible', 'isVisible', 'isShipVisible'):
                        source = 'dataHub.visibility.' + name
                        if visibility_component_status != 'available':
                            candidate_diagnostics[name] = _visibility_observation(
                                source, visibility_component_status, None,
                                visibility_component_status)
                            continue
                        missing = object()
                        try:
                            if _is_mapping(vis):
                                value = vis.get(name, missing)
                            else:
                                value = getattr(vis, name, missing)
                            if value is missing:
                                status = 'missing'
                                reason = 'attributeMissing'
                            elif value is None:
                                status = 'none'
                                reason = 'valueNone'
                            elif isinstance(value, bool):
                                status = 'available'
                                reason = None
                            else:
                                status = 'nonBoolean'
                                reason = ('nonFiniteNumber' if isinstance(value, float)
                                          and _visibility_raw(value) is None else 'expectedBoolean')
                            candidate_diagnostics[name] = _visibility_observation(
                                source, status, value if value is not missing else None, reason)
                            if isinstance(value, (bool, int, long, float)):
                                safe_value = _visibility_raw(value)
                                if safe_value is not None:
                                    raw_visibility[name] = safe_value
                        except Exception:
                            candidate_diagnostics[name] = _visibility_observation(
                                source, 'readError', None, 'attributeReadException')
                    self._mapVisibility[pid] = raw_visibility
                    self._mapVisibilityDiagnostics[pid] = {
                        'componentStatus': visibility_component_status,
                        'candidates': candidate_diagnostics}

            xy, yaw = read_map_position(entity, sample_row, pid is not None)
            if pid is not None and xy is not None:
                out[pid] = (xy[0], xy[1], yaw)
        return out

    @staticmethod
    def _fit_axis(ms, ws):
        """Least-squares fit w = a*m + b; returns (a, b, residual) or None."""
        n = len(ms)
        if n < 2:
            return None
        mean_m = sum(ms) / n
        mean_w = sum(ws) / n
        var_m = sum((m - mean_m) ** 2 for m in ms)
        if var_m <= 1e-6:
            return None
        cov = sum((ms[i] - mean_m) * (ws[i] - mean_w) for i in range(n))
        a = cov / var_m
        b = mean_w - a * mean_m
        res = sum((ws[i] - (a * ms[i] + b)) ** 2 for i in range(n))
        return (a, b, res)

    def _fit_map_transform(self, samples):
        """Derive the affine mapping minimap-space -> world from ships that expose
        both. `samples` = [(mapX, mapY, worldX, worldZ), ...].

        Returns ('A'|'B', ax, bx, az, bz) where 'A' means worldX<-mapX, worldZ<-mapY
        and 'B' means the axes are swapped. We try both and keep the better fit, so
        we don't have to assume the minimap's axis orientation up front.

        Needs >=3 samples: with only 2 points both orientations fit exactly, so a
        later frame that drops one axis (ships aligned) can flip A<->B and make
        map-only enemies jump on the overlay."""
        if len(samples) < 3:
            return None
        mxs = [s[0] for s in samples]
        mys = [s[1] for s in samples]
        wxs = [s[2] for s in samples]
        wzs = [s[3] for s in samples]
        a_x = self._fit_axis(mxs, wxs)
        a_z = self._fit_axis(mys, wzs)
        b_x = self._fit_axis(mys, wxs)
        b_z = self._fit_axis(mxs, wzs)
        cands = []
        if a_x and a_z:
            cands.append(('A', a_x[2] + a_z[2], a_x, a_z))
        if b_x and b_z:
            cands.append(('B', b_x[2] + b_z[2], b_x, b_z))
        if not cands:
            return None
        cands.sort(key=lambda c: c[1])
        kind, _res, fx, fz = cands[0]
        return (kind, fx[0], fx[1], fz[0], fz[1])

    def _map_to_world(self, mx, my):
        return self._mapCalibration.map_to_world(mx, my)

    def _build_ships(self, now, ui_hp=None, avatar_entities=None,
                     players_sample=_UNSET):
        self._positionDiagnostics = {}
        player_reads = {
            'source': 'sampleLocalPlayersIndex',
            'sampleStatus': (players_sample.get('status', 'unknown')
                             if isinstance(players_sample, dict) else 'notProvided'),
            'indexHits': 0, 'vehicleLookups': 0}
        ships = _try(lambda: battle.getAllShips(), []) or []
        mapIndex = self._collect_map_positions(avatar_entities)   # playerId -> (mapX, mapY, mapYaw)
        fallback_due = (_get(self, '_positionFallbacksEnabled', False) is True and
                        _get(self, '_diagnosticsEnabled', False) is True and
                        _get(self, '_diagnosticsSampleDue', False) is True)

        # -- pass 1: resolve ids + world positions; calibrate map->world ---------
        infos = []
        calib = []
        for ship in ships:
            vehId = None
            for _name in ('_Ship__id', 'id', 'vehicleId'):
                vehId = _get(ship, _name)
                if vehId is not None:
                    break
            player = None
            sample_row = None
            player_key = (_strict_player_lookup_key(vehId)
                          if vehId is not None else None)
            if (not fallback_due and players_sample is not _UNSET and
                    isinstance(players_sample, dict) and player_key is not None):
                sample_row = players_sample.get('index', {}).get(player_key)
            if sample_row is not None:
                player_reads['indexHits'] += 1
                pid = sample_row.get('playerId')
                player_team = sample_row.get('teamId')
            else:
                if vehId is not None:
                    player_reads['vehicleLookups'] += 1
                player = (_try(lambda: battle.getPlayerByVehicleId(vehId))
                          if vehId is not None else None)
                pid = _get(player, 'id') if player is not None else None
                if pid is None and player is not None and _is_mapping(player):
                    pid = _try(lambda: player['id'])
                player_team = _get(player, 'teamId') if player is not None else None
                if (player_team is None and player is not None and
                        _is_mapping(player)):
                    player_team = _try(lambda: player['teamId'])
            ship_team = _get(ship, 'teamId')
            if vehId is not None and pid is not None:
                self._damage.remember(
                    vehId, pid, ship_team if player_team is None else player_team)
            worldPos, position_read = self._get_ship_position(
                ship, pid, vehId, player=player, allow_fallback=fallback_due)
            fallback_attempted = position_read['fallbackStatus'] != 'notSampled'
            count_key = ('fallbackSampledShips' if fallback_attempted else
                         'fallbackNotSampledShips')
            self._positionDiagnostics[count_key] = self._positionDiagnostics.get(count_key, 0) + 1
            infos.append((ship, vehId, player, sample_row, pid, player_team,
                          ship_team, worldPos, position_read))
            if worldPos and pid is not None:
                mp = mapIndex.get(pid)
                if mp is not None and self._mapVisibility.get(pid, {}).get('mapVisible') != False:
                    calib.append((mp[0], mp[1], worldPos[0], worldPos[2]))
        # Accumulate spatially distinct samples across frames, including self.
        # The adapter validates geometry/holdout errors before accepting a fit.
        # observe() already returns the diagnostics snapshot for this batch; do
        # not rebuild the same plain-data snapshot a second time.
        calibration = self._mapCalibration.observe(calib, now)

        # -- pass 2: build per-ship entries --------------------------------------
        out = []
        nAlly = 0
        nAllyVis = 0
        nEnemy = 0
        nEnemyVis = 0
        for ship, vehId, player, sample_row, pid, player_team, ship_team, worldPos, position_read in infos:
            entry = {}
            entry['uiId'] = _get(ship, 'uiId')
            if vehId is not None:
                entry['vehicleId'] = vehId
            teamId = ship_team
            entry['teamId'] = teamId
            entry['relation'] = self._relation(teamId)
            entry['alive'] = _try(lambda: ship.isAlive())
            ui_visibility = self._mapVisibility.get(pid, {})
            ui_diagnostics = self._mapVisibilityDiagnostics.get(pid, {})
            api_visibility = {}
            api_diagnostics = {}
            for name in ('isVisible', 'isShipVisible'):
                source = 'shipApi.' + name
                missing = object()
                try:
                    if _is_mapping(ship):
                        value = ship.get(name, missing)
                    else:
                        value = getattr(ship, name, missing)
                    if value is missing:
                        status = 'missing'
                        reason = 'attributeMissing'
                    elif value is None:
                        status = 'none'
                        reason = 'valueNone'
                    elif isinstance(value, bool):
                        status = 'available'
                        reason = None
                    else:
                        status = 'nonBoolean'
                        reason = ('nonFiniteNumber' if isinstance(value, float)
                                  and _visibility_raw(value) is None else 'expectedBoolean')
                    api_diagnostics[name] = _visibility_observation(
                        source, status, value if value is not missing else None, reason)
                    if isinstance(value, (bool, int, long, float)):
                        safe_value = _visibility_raw(value)
                        if safe_value is not None:
                            api_visibility[name] = safe_value
                except Exception:
                    api_diagnostics[name] = _visibility_observation(
                        source, 'readError', None, 'attributeReadException')
            raw_map_visible = ui_visibility.get('mapVisible')
            # This is a UI flag, not an inferred spotting/server state.
            map_visible = (bool(raw_map_visible) if raw_map_visible in (True, False)
                           and raw_map_visible is not None else None)
            entry['visibility'] = {
                'source': 'dataHub.visibility',
                'status': 'available' if ui_visibility else 'unknown',
                'raw': ui_visibility,
                'shipApi': api_visibility,
                'dataHubCandidates': ui_diagnostics.get('candidates', {}),
                'shipApiCandidates': api_diagnostics,
                'dataHubComponentStatus': ui_diagnostics.get(
                    'componentStatus', 'componentMissing'),
                'semantics': 'unverified',
                'uiMeaning': 'minimapMarkerVisibility',
                'worldVisibleSource': ('dataHub.visibility.visible'
                                       if 'visible' in ui_visibility else None),
            }
            entry['visible'] = map_visible
            entry['visibleSource'] = 'dataHub.visibility.mapVisible' if map_visible is not None else None
            if player is not None or sample_row is not None:
                entry['playerId'] = pid
                if entry.get('teamId') is None:
                    entry['teamId'] = player_team
                    entry['relation'] = self._relation(entry['teamId'])

            pos = worldPos
            entry['positionReadStatus'] = {
                'status': position_read['status'],
                'source': position_read['source'],
                'attempted': position_read['attempted'],
                'reason': position_read['reason'],
            }
            entry['positionReadPolicy'] = {
                'source': 'ship.getPosition',
                'policy': position_read['policy'],
                'fallbackStatus': position_read['fallbackStatus'],
                'fallbackSource': position_read['fallbackSource'],
                'attempted': position_read['fallbackStatus'] != 'notSampled',
            }
            entry['positionSource'] = 'shipOrPlayerApi' if worldPos else None
            mp = mapIndex.get(pid) if pid is not None else None
            if mp is not None:
                entry['mapPositionRaw'] = [mp[0], mp[1]]
            norm = _map_norm_xy(mp[0], mp[1]) if mp is not None else None
            if norm is not None:
                # mapPosition is already minimap-normalized; this keeps 1v1
                # enemies drawable even when only self is available to calibrate.
                entry['nx'] = norm[0]
                entry['ny'] = norm[1]
                entry['mapPositionSource'] = 'dataHub.mapPosition'
                entry['mapPositionFreshness'] = 'unverified'
            if not pos and mp is not None:
                # spotted-but-not-rendered ship (e.g. enemy lit only by a teammate):
                # getPosition() is None, but mapPosition is populated -- convert it
                # to world coordinates using the calibrated transform.
                pos = self._map_to_world(mp[0], mp[1])
                if pos is not None:
                    entry['positionSource'] = 'calibratedMapPosition'
            if pos:
                entry['position'] = pos
            entry['positionAvailable'] = bool(pos or norm is not None)
            for k in ('yaw', 'health', 'maxHealth', 'name'):
                v = _get(ship, k)
                if v is not None:
                    entry[k] = v
            # 3D ship.health is empty on some builds; fill from dataHub avatar
            # health (the component TTaroTeamPanel's side bars already use).
            apply_ui_health(entry, ui_hp, for_unspotted=entry.get('visible') is False)
            # spotted-only enemies have no ship.yaw; fall back to mapPosition yaw
            if entry.get('yaw') is None and mp is not None and mp[2] is not None:
                entry['yaw'] = mp[2]
            # ship class lives on `subtype` on this build (`shipType` is None)
            shipType = _get(ship, 'shipType')
            if shipType is None:
                shipType = _get(ship, 'subtype')
            if shipType is not None:
                entry['shipType'] = shipType
            # track ally/enemy visibility counts for diagnostics
            rel = entry.get('relation')
            if rel == 2:
                nEnemy += 1
                if entry.get('visible') is True:
                    nEnemyVis += 1
            elif rel == 1:
                nAlly += 1
                if entry.get('visible') is True:
                    nAllyVis += 1

            out.append(entry)

        nHp = 0
        for row in out:
            if row.get('maxHealth') is not None:
                nHp += 1
        sampled_ships = sum(1 for row in out if row.get(
            'positionReadPolicy', {}).get('attempted'))
        position_reads = dict(self._positionDiagnostics)
        position_reads.update({
            'readPolicy': ('diagnosticExtendedFallback' if fallback_due else
                           'coreDirectOnly'),
            'sampledShips': sampled_ships,
            'notSampledShips': len(out) - sampled_ships,
            'sampleDue': bool(_get(self, '_diagnosticsEnabled', False) is True and
                              _get(self, '_diagnosticsSampleDue', False) is True),
        })
        return out, {
            'totalShips': len(ships),
            'playerReads': player_reads,
            'allies': nAlly,
            'alliesVisible': nAllyVis,
            'enemies': nEnemy,
            'enemiesVisible': nEnemyVis,
            'mapCalib': calibration.get('status'),
            'mapSamples': len(calib),
            'mapCalibration': calibration,
            'positionReads': position_reads,
            'positionReadPolicy': {
                'policy': position_reads['readPolicy'],
                'sampledShips': sampled_ships,
                'notSampledShips': len(out) - sampled_ships,
            },
            'uiHealth': nHp,
        }


def _is_mapping(o):
    try:
        return hasattr(o, 'keys') and hasattr(o, '__getitem__')
    except:
        return False


gCollector = Collector()
