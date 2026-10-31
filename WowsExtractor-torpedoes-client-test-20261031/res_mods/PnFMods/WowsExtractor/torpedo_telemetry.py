# MIT License
# SPDX-License-Identifier: MIT
"""Public ModsAPI torpedo adapter. Compatible with game Python 2.7 and Python 3.

Only documented Torpedo/Player/Ship/_ModuleState fields are read. Ammo params
are a public SafeClass with no documented field list; copy its public data only.
UI diagnostics and finite-difference motion have separate source-labelled fields.
No private attributes, guessed homing fields or position extrapolation.
"""

import math

try:
    STRING_TYPES = (basestring,)
    NUMBER_TYPES = (int, long, float)
except NameError:
    STRING_TYPES = (str,)
    NUMBER_TYPES = (int, float)

TORPEDO_FIELDS = ('uiId', 'ownerId', 'ownerTeamId', 'ownerType', 'shotId', 'type')
OWNER_FIELDS = ('teamId', 'isObserver', 'isAlive', 'isBot',
                'uiId', 'isPlayer', 'subtype', 'name', 'playerName')
MODULE_FIELDS = ('type', 'currentHP', 'maxHP', 'state', 'critTimer')
_MISSING = object()


def _get(obj, key, default=None):
    try:
        return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key)
    except Exception:
        return default


def _finite(value):
    try:
        return (isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)
                and not math.isnan(value) and not math.isinf(value))
    except (ValueError, OverflowError, TypeError):
        return False


def vector(value):
    if value is None:
        return None
    try:
        xyz = [value.x, value.y, value.z]
    except Exception:
        try:
            xyz = [value[0], value[1], value[2]]
        except Exception:
            return None
    return [float(v) for v in xyz] if all(_finite(v) for v in xyz) else None


def public_data(value, depth=0, seen=None):
    """JSON-safe copy of public API data, bounded against cycles/deep wrappers.

    Unknown runtime objects never become repr strings (which may contain
    addresses). Methods and private names are never read or invoked.
    """
    if callable(value):
        return None
    if value is None or isinstance(value, (bool,) + STRING_TYPES):
        return value
    if isinstance(value, NUMBER_TYPES):
        return value if _finite(value) else None
    if depth >= 6:
        return None
    if seen is None:
        seen = set()
    marker = id(value)
    if marker in seen:
        return None
    seen.add(marker)
    try:
        if isinstance(value, (tuple, list)):
            return [public_data(v, depth + 1, seen) for v in value]
        if isinstance(value, dict):
            return dict((k, public_data(v, depth + 1, seen))
                        for k, v in value.items()
                        if isinstance(k, STRING_TYPES) and not k.startswith('_'))
        xyz = vector(value)
        if xyz is not None:
            return xyz
        result = {}
        for key in dir(value):
            if key.startswith('_'):
                continue
            item = _get(value, key, _MISSING)
            if item is not _MISSING and not callable(item):
                result[key] = public_data(item, depth + 1, seen)
        return result
    except Exception:
        return None
    finally:
        seen.remove(marker)


def _fields(obj, names):
    return dict((key, public_data(_get(obj, key))) for key in names)


def _call(obj, name, *args):
    fn = _get(obj, name)
    if not callable(fn):
        return 'unsupported', None
    try:
        value = fn(*args)
        return ('unknown' if value is None else 'available'), value
    except Exception:
        return 'unknown', None


def ui_torpedo_probe(hub, components, api_rows):
    """Read-only diagnostic, not an authoritative homing/identity adapter.

    Collection spelling comes from ATM UI markup; Python availability is untested.
    No values are cached, joined to API rows or written back to the UI.
    """
    keys = dict((name, _get(components, name))
                for name in ('torpedo', 'mods_DataComponent'))
    out = {'source': 'dataHub.torpedo', 'producer': 'unknown',
           'status': 'unknown', 'componentKeys': dict(
               (name, public_data(key)) for name, key in keys.items()),
           'apiUiIds': [row.get('uiId') for row in api_rows[:64]],
           'rows': [], 'truncated': False}
    status, entities = _call(hub, 'getEntityCollections', 'torpedo')
    out['status'] = status
    if status != 'available':
        return out
    try:
        for index, entity in enumerate(entities):
            if index >= 64:
                out['truncated'] = True
                break
            row = {'entityIdCandidate': public_data(_get(entity, 'id'))}
            for name, key in keys.items():
                component = _MISSING
                if key is not None:
                    try:
                        component = entity[key]
                    except Exception:
                        pass
                if name == 'torpedo':
                    row['torpedoStatus'] = ('unsupported' if key is None else
                        ('unknown' if component is _MISSING else 'available'))
                    row['uiType'] = (None if component is _MISSING else
                                     public_data(_get(component, 'type')))
                else:
                    data = (_MISSING if component is _MISSING else
                            _get(component, 'data', _MISSING))
                    value = (_MISSING if data is _MISSING else
                             _get(data, 'isHoming', _MISSING))
                    row['homingSource'] = 'ui.mods_DataComponent'
                    row['homingStatus'] = ('unsupported' if key is None else
                        ('unknown' if value is _MISSING or type(value) is not bool
                         else 'available'))
                    row['isHoming'] = value if type(value) is bool else None
                    row['homingRaw'] = (None if value is _MISSING else
                                        public_data(value))
                    row['homingRawType'] = (None if value is _MISSING else
                                            type(value).__name__)
                    spotted = (_MISSING if data is _MISSING else
                               _get(data, 'isSpotted', _MISSING))
                    row['spottedSource'] = 'ui.mods_DataComponent'
                    row['spottedStatus'] = ('unsupported' if key is None else
                        ('unknown' if spotted is _MISSING or type(spotted) is not bool
                         else 'available'))
                    row['isSpotted'] = spotted if type(spotted) is bool else None
                    row['spottedRaw'] = (None if spotted is _MISSING else
                                         public_data(spotted))
                    row['spottedRawType'] = (None if spotted is _MISSING else
                                             type(spotted).__name__)
                    row['dataKeys'] = (sorted(k for k in data
                        if isinstance(k, STRING_TYPES) and not k.startswith('_'))[:32]
                        if isinstance(data, dict) else [])
            out['rows'].append(row)
    except Exception:
        out['status'] = 'unknown'
        out['rows'] = []
    return out


def attach_ui_state(rows, probe):
    """Join only unambiguous exact UI identifiers observed on this build."""
    index = {}
    duplicate = set()
    for item in probe.get('rows', []) if probe.get('status') == 'available' else []:
        key = item.get('entityIdCandidate')
        if key is None:
            continue
        if key in index:
            duplicate.add(key)
        index[key] = item
    for row in rows:
        key = row.get('uiId')
        item = index.get(key) if key not in duplicate else None
        state = {'source': 'ui.mods_DataComponent', 'producer': 'unknown',
                 'matchStatus': 'exactUiId' if item is not None else 'unknown',
                 'isHoming': None, 'homingStatus': 'unknown',
                 'isSpotted': None, 'spottedStatus': 'unknown', 'uiType': None}
        if item is not None:
            for name in ('isHoming', 'homingStatus', 'isSpotted', 'spottedStatus', 'uiType'):
                state[name] = item.get(name, state[name])
        row['uiState'] = state


class TorpedoMotion(object):
    """Finite differences in game-world units, not authoritative game speed.

    Gaps over one second and non-increasing time cannot yield current velocity.
    Membership/identity loss drops history; no extrapolation or stale reuse.
    """
    def __init__(self):
        self.clear()

    def clear(self):
        self._previous = {}

    def update(self, rows, now, available=True):
        if not available or not _finite(now):
            self.clear()
            return
        current = {}
        for row in rows:
            key = row.get('uiId')
            pos = vector(row.get('position'))
            motion = {'available': False, 'source': 'positionDifference',
                      'inferred': True, 'speedUnit': 'game_world_units_per_second',
                      'horizontalSpeed': None, 'headingRadians': None,
                      'velocity': None, 'dt': None, 'observedAge': None,
                      'observedDistance': None}
            row['motion'] = motion
            if key is None or pos is None:
                continue
            identity = (row.get('ownerId'), row.get('shotId'))
            previous = self._previous.get(key)
            first, distance = now, 0.0
            if previous is not None and previous[2] == identity:
                dt = now - previous[0]
                if 0 < dt <= 1.0:
                    first, distance = previous[3], previous[4]
                    delta = [pos[i] - previous[1][i] for i in range(3)]
                    velocity = [v / dt for v in delta]
                    speed = math.hypot(velocity[0], velocity[2])
                    distance += math.hypot(delta[0], delta[2])
                    if all(_finite(v) for v in velocity) and _finite(distance) and _finite(speed):
                        motion.update(available=True, dt=dt, velocity=velocity,
                            horizontalSpeed=speed, headingRadians=(
                                math.atan2(velocity[0], velocity[2]) if speed > 0 else None))
            if not _finite(distance):
                first, distance = now, 0.0
            age = now - first
            motion['observedAge'] = age if _finite(age) else None
            motion['observedDistance'] = distance
            current[key] = (now, pos, identity, first, distance)
        self._previous = current


class TorpedoTelemetry(object):
    def __init__(self, battle_api, constants_api):
        self.battle = battle_api
        self.constants = constants_api

    def systems(self):
        """Documented self-ship consumables; never a sonar-ping target timer."""
        _, ship = _call(self.battle, 'getSelfPlayerShip')
        status, items = _call(ship, 'getConsumablesState')
        rows = []
        if status == 'available':
            try:
                rows = [_fields(item, ('icon', 'num', 'currentState', 'endTime'))
                        for item in items]
            except Exception:
                status, rows = 'unknown', []
        out = {'consumables': {'status': status, 'items': rows,
               'source': 'Ship.getConsumablesState'}, 'search': {}}
        for name, method in (('radar', 'getRadarInfo'),
                             ('hydroAcoustic', 'getHydroAcousticSearchInfo'),
                             ('submarineLocator', 'getSubmarineLocatorInfo')):
            state, value = _call(ship, method)
            values = []
            shape = None
            if state == 'available':
                shape = 'list' if isinstance(value, (list, tuple)) else 'object'
                try:
                    values = [_fields(item, ('distShip', 'state', 'workTimeLeft'))
                              for item in (value if shape == 'list' else [value])]
                except Exception:
                    state, values = 'unknown', []
            out['search'][name] = {'status': state, 'items': values,
                                    'source': 'Ship.' + method, 'shape': shape}
        return out

    def torpedoes(self, self_team=None):
        status, items = _call(self.battle, 'getAllTorpedoes')
        out = []
        owners = {}
        if status == 'available':
            try:
                for torpedo in items:
                    row = _fields(torpedo, TORPEDO_FIELDS)
                    row['position'] = vector(_get(torpedo, 'position'))
                    team = row['ownerTeamId']
                    row['relation'] = (None if team is None or self_team is None
                                       else (1 if team == self_team else 2))
                    owner_id = row['ownerId']
                    if owner_id is not None and owner_id not in owners:
                        owner_status, owner = _call(
                            self.battle, 'getTorpedoOwnerById', owner_id)
                        owners[owner_id] = (_fields(owner, OWNER_FIELDS)
                                            if owner_status == 'available' else None)
                    row['owner'] = owners.get(owner_id)
                    # ownerId is NOT documented as a player/vehicle id. Never
                    # equate these namespaces. Ship.isPlayer is public instead.
                    row['isOwn'] = _get(row['owner'], 'isPlayer')
                    if type(row['isOwn']) is not bool:
                        row['isOwn'] = None
                    out.append(row)
            except Exception:
                # A failed/incomplete enumeration is not a successful empty list.
                status = 'unknown'
                out = []
        return out, {'available': status == 'available', 'status': status,
                     'source': 'battle.getAllTorpedoes'}

    def armament(self):
        _, ship = _call(self.battle, 'getSelfPlayerShip')
        modules_status, modules = _call(ship, 'getTorpedoesModulesState')
        if ship is None:
            modules_status = 'unknown'
        module_rows = []
        if modules_status == 'available':
            try:
                for module in modules:
                    row = _fields(module, MODULE_FIELDS)
                    row['position'] = vector(_get(module, 'position'))
                    module_rows.append(row)
            except Exception:
                modules_status = 'unknown'
                module_rows = []
        weapon_type = _get(_get(self.constants, 'WeaponType'), 'TORPEDO')
        ammo_status, ammo_id = ('unsupported', None)
        if weapon_type is not None:
            ammo_status, ammo_id = _call(self.battle, 'getSelectedAmmoId', weapon_type)
        if ammo_id == -1:
            ammo_status, ammo_id = 'unknown', None
        params_status, params = ('unknown', None)
        if ammo_status == 'available':
            params_status, raw = _call(self.battle, 'getAmmoParams', ammo_id)
            params = public_data(raw)
            if params is None and params_status == 'available':
                params_status = 'unknown'
        return {
            'available': modules_status == 'available' or ammo_status == 'available',
            'modulesStatus': modules_status, 'modules': module_rows,
            'selectedAmmoStatus': ammo_status, 'selectedAmmoId': public_data(ammo_id),
            'ammoParamsStatus': params_status, 'ammoParams': params,
        }
