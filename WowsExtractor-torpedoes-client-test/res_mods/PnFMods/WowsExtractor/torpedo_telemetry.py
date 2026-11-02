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
                    depth_status, depth_value = _ttx_read(component, 'depth') \
                        if component is not _MISSING and component is not None \
                        else ('unknown', None)
                    depth = {'source': 'dataHub.torpedo.depth',
                             'status': depth_status, 'type': None, 'raw': None,
                             'unit': 'unknown', 'semantics': 'unverified'}
                    if depth_status == 'available':
                        depth['type'] = type(depth_value).__name__
                        if isinstance(depth_value, bool) or not isinstance(
                                depth_value, NUMBER_TYPES):
                            depth['status'] = 'nonNumeric'
                        elif not _finite(depth_value):
                            depth['status'] = 'nonFinite'
                        else:
                            depth['raw'] = depth_value
                    row['depth'] = depth
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
                  'isSpotted': None, 'spottedStatus': 'unknown', 'uiType': None,
                  'depth': {'source': 'dataHub.torpedo.depth',
                            'status': 'unknown', 'type': None, 'raw': None,
                            'unit': 'unknown', 'semantics': 'unverified'}}
        if item is not None:
            for name in ('isHoming', 'homingStatus', 'isSpotted', 'spottedStatus', 'uiType'):
                state[name] = item.get(name, state[name])
            depth = item.get('depth')
            if isinstance(depth, dict):
                state['depth'] = depth
        row['uiState'] = state


# Names and fields below are UI-derived probes, not a Python/dataHub contract.
WEAPON_PROBE_COLLECTIONS = ('weaponSlot', 'ammo', 'serialLoad')
WEAPON_PROBE_COMPONENTS = ('weaponSlot', 'progress', 'ammo', 'serialLoad')
WEAPON_SLOT_FIELDS = ('id', 'type', 'state', 'active', 'selected', 'shotCount',
                      'ammoParamsId', 'ident')
PROGRESS_FIELDS = ('value', 'max')
SERIAL_LOAD_FIELDS = ('index', 'weaponType', 'state')
AMMO_FIELDS = ('id', 'hasSecondaryAmmo', 'isAutoUsage', 'squadId')
VIEW_DATA_FIELDS = ('ammoId', 'title', 'description', 'subheader', 'iconPath',
                    'secondaryIconPath', 'uniqueFeatures', 'paramsDescriptor')
_CANDIDATE_STRING_LIMIT = 128


def _candidate_value(value, depth=0, budget=None):
    """Copy bounded scalar/container candidates; never inspect arbitrary objects."""
    if budget is None:
        budget = [64]
    if budget[0] <= 0 or depth > 3:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, STRING_TYPES):
        return value[:_CANDIDATE_STRING_LIMIT]
    if isinstance(value, NUMBER_TYPES):
        return value if _finite(value) else None
    if isinstance(value, (list, tuple)):
        result = []
        for item in value[:16]:
            budget[0] -= 1
            result.append(_candidate_value(item, depth + 1, budget))
        return result
    if isinstance(value, dict):
        result = {}
        for key in list(value.keys())[:16]:
            if not isinstance(key, STRING_TYPES) or key.startswith('_'):
                continue
            budget[0] -= 1
            result[key[:_CANDIDATE_STRING_LIMIT]] = _candidate_value(
                value[key], depth + 1, budget)
        return result
    return None


def _candidate_meta(value):
    """Describe the original scalar shape without changing the legacy raw copy.

    `truncated`/`stringLength` let join code reject 128-character prefixes that
    would otherwise collide. They are diagnostic metadata, not ID validation.
    """
    if isinstance(value, STRING_TYPES):
        return {'type': type(value).__name__, 'stringLength': len(value),
                'truncated': len(value) > _CANDIDATE_STRING_LIMIT}
    if value is None:
        return {'type': None, 'stringLength': None, 'truncated': False}
    return {'type': type(value).__name__, 'stringLength': None,
            'truncated': False}


def _probe_read(obj, key):
    if obj is None:
        return 'unknown', None
    try:
        if isinstance(obj, dict):
            if key not in obj:
                return 'unknown', None
            return 'available', obj[key]
        value = getattr(obj, key, _MISSING)
        return ('unknown', None) if value is _MISSING else ('available', value)
    except Exception:
        return 'unknown', None


def _probe_component_key(components, name):
    if components is None:
        return 'unsupported', None
    try:
        if isinstance(components, dict):
            if name not in components:
                return 'unsupported', None
            value = components[name]
        else:
            value = getattr(components, name, _MISSING)
            if value is _MISSING:
                return 'unsupported', None
        return ('unknown', None) if value is None else ('available', value)
    except Exception:
        return 'unknown', None


def _probe_component(entity, key):
    if entity is None or key is None:
        return 'unsupported' if key is None else 'unknown', None
    try:
        value = entity[key]
        return ('unknown', None) if value is None else ('available', value)
    except Exception:
        return 'unknown', None


def _probe_fields(obj, names):
    values, states, meta = {}, {}, {}
    for name in names:
        status, value = _probe_read(obj, name)
        states[name] = status
        if status == 'available':
            values[name] = _candidate_value(value)
            meta[name] = _candidate_meta(value)
        else:
            values[name] = None
            meta[name] = {'type': None, 'stringLength': None,
                          'truncated': False}
    return values, states, meta


def _empty_field_meta(names):
    return dict((name, {'type': None, 'stringLength': None, 'truncated': False})
                for name in names)


def _probe_collection(hub, name, component_key, component_name, fields,
                      progress_key=None):
    out = {'source': 'dataHub.' + name, 'status': 'unknown',
           'semantics': 'unverified', 'componentKeyStatus':
           'unsupported' if component_key is None else 'available',
           'componentKey': _candidate_value(component_key), 'rows': [],
           'truncated': False, 'partial': False}
    getter = _get(hub, 'getEntityCollections', _MISSING)
    if getter is _MISSING or not callable(getter):
        out['status'] = 'unsupported'
        return out
    try:
        entities = getter(name)
    except Exception:
        return out
    if entities is None:
        return out
    out['status'] = 'available'
    try:
        for index, entity in enumerate(entities):
            if index >= 32:
                out['truncated'] = True
                break
            row = {}
            id_status, entity_id = _probe_read(entity, 'id')
            row['entityIdCandidate'] = (_candidate_value(entity_id)
                                        if id_status == 'available' else None)
            row['componentStatus'] = component_name
            component_status, component = _probe_component(entity, component_key)
            row['componentStatus'] = component_status
            if component_status == 'available':
                row['fields'], row['fieldStatus'], row['fieldMeta'] = _probe_fields(
                    component, fields)
                if component_name == 'ammo':
                    view_status, view_data = _probe_read(component, 'viewData')
                    row['viewDataStatus'] = view_status
                    if view_status == 'available':
                        (row['viewData'], row['viewDataFieldStatus'],
                         row['viewDataFieldMeta']) = _probe_fields(
                             view_data, VIEW_DATA_FIELDS)
                    else:
                        row['viewData'] = None
                        row['viewDataFieldStatus'] = dict(
                            (key, view_status) for key in VIEW_DATA_FIELDS)
                        row['viewDataFieldMeta'] = _empty_field_meta(
                            VIEW_DATA_FIELDS)
                if component_name == 'weaponSlot':
                    # progress is a separate component on this same entity.
                    row['progressComponentStatus'] = 'unsupported'
                    row['progress'] = None
            if component_name == 'weaponSlot':
                row['fields'] = row.get('fields', {})
                row['fieldStatus'] = row.get('fieldStatus', {})
                row['fieldMeta'] = row.get('fieldMeta', _empty_field_meta(fields))
                progress_component_status, progress_component = _probe_component(
                    entity, progress_key)
                row['progressComponentStatus'] = progress_component_status
                if progress_component_status == 'available':
                    (row['progress'], row['progressFieldStatus'],
                     row['progressFieldMeta']) = _probe_fields(
                         progress_component, PROGRESS_FIELDS)
                else:
                    row['progress'] = None
                    row['progressFieldStatus'] = dict((key, progress_component_status)
                                                      for key in PROGRESS_FIELDS)
                    row['progressFieldMeta'] = _empty_field_meta(PROGRESS_FIELDS)
            elif component_name == 'serialLoad':
                progress_component_status, progress_component = _probe_component(
                    entity, progress_key)
                row['progressComponentStatus'] = progress_component_status
                if progress_component_status == 'available':
                    (row['progress'], row['progressFieldStatus'],
                     row['progressFieldMeta']) = _probe_fields(
                         progress_component, PROGRESS_FIELDS)
                else:
                    row['progress'] = None
                    row['progressFieldStatus'] = dict((key, progress_component_status)
                                                      for key in PROGRESS_FIELDS)
                    row['progressFieldMeta'] = _empty_field_meta(PROGRESS_FIELDS)
            out['rows'].append(row)
    except Exception:
        out['status'] = 'partial' if out['rows'] else 'unknown'
        out['partial'] = bool(out['rows'])
    return out


def weapon_hub_probe(hub, components):
    """Bounded read-only snapshot of UI-derived weapon collection candidates."""
    keys, key_status = {}, {}
    for name in WEAPON_PROBE_COMPONENTS:
        key_status[name], keys[name] = _probe_component_key(components, name)
    result = {'source': 'dataHub weapon UI candidates', 'status': 'unknown',
              'semantics': 'unverified', 'componentKeys': dict(
                  (name, {'status': key_status[name],
                          'value': _candidate_value(keys[name])
                           if key_status[name] == 'available' else None})
                  for name in WEAPON_PROBE_COMPONENTS),
              'collections': {}}
    for name in WEAPON_PROBE_COLLECTIONS:
        key = keys.get(name)
        if name == 'weaponSlot':
            fields, component = WEAPON_SLOT_FIELDS, 'weaponSlot'
        elif name == 'ammo':
            fields, component = AMMO_FIELDS, 'ammo'
        else:
            fields, component = SERIAL_LOAD_FIELDS, 'serialLoad'
        try:
            item = _probe_collection(hub, name, key, component, fields,
                                     keys.get('progress'))
            item['componentKeyStatus'] = key_status.get(name, 'unknown')
            item['sourceStatus'] = item['status']
            result['collections'][name] = item
        except Exception:
            result['collections'][name] = {'source': 'dataHub.' + name,
                'status': 'unknown', 'semantics': 'unverified', 'rows': [],
                'truncated': False, 'partial': False}
    statuses = [entry.get('status') for entry in result['collections'].values()]
    result['status'] = ('available' if 'available' in statuses and
                        all(s in ('available', 'unsupported') for s in statuses)
                        else ('partial' if any(s in ('available', 'partial') for s in statuses)
                              else 'unknown'))
    return result


def safe_weapon_hub_probe(hub, components):
    """Fail closed at the diagnostic boundary; callers keep their main state."""
    try:
        return weapon_hub_probe(hub, components)
    except Exception:
        return {'source': 'dataHub weapon UI candidates', 'status': 'unknown',
                'semantics': 'unverified', 'collections': {}, 'error': 'probeFailed'}


# UI-derived gun/reload-bar candidates. Keep fixed, small routes and no history.
GUN_RELOAD_COLLECTIONS = ('gun', 'reloadBar', 'gunBarrel')
GUN_FIELDS = ('id', 'index', 'type', 'state', 'position', 'status')
RELOAD_BAR_FIELDS = ('rowsCount', 'order', 'prevOrder', 'iconName', 'isOutOfBounds')
GUN_PROGRESS_FIELDS = ('value', 'min', 'max')
GUN_REFS_PER_MODIFIER = 16
GUN_REF_BUDGET = 16


def _gun_scalar(source, status, value=_MISSING):
    if status != 'available' or value is _MISSING or value is None:
        return {'source': source, 'status': 'unknown' if status == 'available' else status,
                'type': None, 'raw': None, 'semantics': 'unverified'}
    if isinstance(value, bool):
        safe = value
    elif isinstance(value, NUMBER_TYPES):
        if not _finite(value):
            return {'source': source, 'status': 'unknown', 'type': type(value).__name__,
                    'raw': None, 'semantics': 'unverified'}
        safe = value
    elif isinstance(value, STRING_TYPES):
        safe = value[:128]
    elif isinstance(value, (list, tuple)):
        safe = _candidate_value(value, budget=[32])
        if safe is None:
            return {'source': source, 'status': 'unknown', 'type': type(value).__name__,
                    'raw': None, 'semantics': 'unverified'}
    else:
        return {'source': source, 'status': 'unknown', 'type': type(value).__name__,
                'raw': None, 'semantics': 'unverified'}
    return {'source': source, 'status': 'available', 'type': type(value).__name__,
            'raw': safe, 'semantics': 'unverified'}


def _gun_component_fields(component, fields, prefix):
    values, statuses = {}, {}
    for field in fields:
        status, value = _probe_read(component, field)
        values[field] = _gun_scalar(prefix + '.' + field, status, value)
        statuses[field] = values[field]['status']
    return values, statuses


def _gun_collection(hub, components, name, component_name, fields):
    key_status, key = _probe_component_key(components, component_name)
    getter_status = _getter_status(hub, 'getEntityCollections')
    out = {'source': 'dataHub.getEntityCollections(%r)' % name,
           'status': 'unknown', 'semantics': 'unverified',
           'getterStatus': getter_status, 'componentKeyStatus': key_status,
           'rows': [], 'partial': False, 'truncated': False}
    if getter_status != 'available':
        out.update(status='unsupported', callStatus='unsupported')
        return out
    if key_status != 'available':
        out.update(status=key_status, callStatus=key_status)
        return out
    try:
        entities = hub.getEntityCollections(name)
    except Exception:
        out['callStatus'] = 'unknown'
        return out
    if entities is None:
        out['callStatus'] = 'unknown'
        return out
    out['callStatus'] = 'available'
    try:
        for index, entity in enumerate(entities):
            if index >= 32:
                out['truncated'] = True
                break
            row = {'componentStatus': 'unknown'}
            id_status, entity_id = _probe_read(entity, 'id')
            row['entityIdCandidate'] = _gun_scalar(name + '.entity.id', id_status, entity_id)
            cstatus, component = _probe_component(entity, key)
            row['componentStatus'] = cstatus
            if cstatus == 'available':
                row['fields'], row['fieldStatus'] = _gun_component_fields(
                    component, fields, name + '.' + component_name)
            if name in ('gun', 'gunBarrel'):
                pstatus, progress = _probe_component(
                    entity, _probe_component_key(components, 'progress')[1])
                row['progressComponentStatus'] = pstatus
                row['progress'] = None
                row['progressFieldStatus'] = dict((f, pstatus) for f in GUN_PROGRESS_FIELDS)
                if pstatus == 'available':
                    row['progress'], row['progressFieldStatus'] = _gun_component_fields(
                        progress, GUN_PROGRESS_FIELDS, name + '.progress')
            if name == 'reloadBar':
                weapon_status, weapon_key = _probe_component_key(components, 'weapon')
                ws, weapon = _probe_component(entity, weapon_key)
                row['weaponComponentStatus'] = weapon_status if weapon_status != 'available' else ws
                row['weaponType'] = _gun_scalar('reloadBar.weapon.type', *_probe_read(weapon, 'type')) \
                    if ws == 'available' else _gun_scalar('reloadBar.weapon.type', row['weaponComponentStatus'])
            if name == 'gun':
                modifier_key_status, modifier_key = _probe_component_key(
                    components, 'barrelsModifier')
                modifier_status, modifier = _probe_component(entity, modifier_key)
                modifier_status = (modifier_status if modifier_key_status == 'available'
                                   else modifier_key_status)
                row['barrelsModifierStatus'] = modifier_status
                row['mode'] = _gun_scalar(
                    'gun.barrelsModifier.mode', *_probe_read(modifier, 'mode')) \
                    if modifier_status == 'available' else _gun_scalar(
                        'gun.barrelsModifier.mode', modifier_status)
                for modifier_name, modifier_key_name, member in (
                        ('barrelsModifier', 'barrelsModifier', 'barrels'),
                        ('serialLoaderModifier', 'serialLoaderModifier', 'serialLoads')):
                    modifier_key_status, modifier_key = _probe_component_key(
                        components, modifier_key_name)
                    ms, modifier = _probe_component(entity, modifier_key)
                    mstatus = ms if modifier_key_status == 'available' else modifier_key_status
                    row[modifier_name + 'Status'] = mstatus
                    row[member] = []
                    if mstatus == 'available':
                        arr_status, arr = _probe_read(modifier, member)
                        row[member + 'Status'] = arr_status
                        if arr_status == 'available' and isinstance(arr, (list, tuple)):
                            row[member + 'Truncated'] = len(arr) > GUN_REFS_PER_MODIFIER
                            row[member] = [_gun_scalar(
                                'gun.%s.%s[%d]' % (modifier_name, member, n),
                                'available', value)
                                for n, value in enumerate(arr[:GUN_REFS_PER_MODIFIER])]
                        else:
                            row[member + 'Status'] = 'unknown'
                    else:
                        row[member + 'Status'] = mstatus
            out['rows'].append(row)
        out['status'] = 'available'
    except Exception:
        out['status'] = 'partial' if out['rows'] else 'unknown'
        out['partial'] = bool(out['rows'])
    return out


def gun_reload_probe(hub, components):
    """Bounded raw candidates for UI gun/reload-bar routes; no inferred joins."""
    result = {'source': 'dataHub UI gun reload candidates',
              'status': 'unknown', 'semantics': 'unverified',
              'collections': {}, 'getEntity': {'getterStatus': _getter_status(hub, 'getEntity'),
                                               'status': 'unsupported', 'resolved': 0,
                                               'budget': GUN_REF_BUDGET}}
    specs = {'gun': ('gun', GUN_FIELDS),
             'reloadBar': ('reloadBar', RELOAD_BAR_FIELDS),
             'gunBarrel': ('gunBarrel', ('id',))}
    for name, (component, fields) in specs.items():
        result['collections'][name] = _gun_collection(
            hub, components, name, component, fields)
    refs, seen, budget = [], set(), [GUN_REF_BUDGET]
    for row in result['collections']['gun']['rows']:
        for member in ('barrels', 'serialLoads'):
            for candidate in row.get(member, []):
                ident = candidate.get('raw') if candidate.get('status') == 'available' else None
                if ident is None or isinstance(ident, (list, tuple, dict)) or not (
                        isinstance(ident, STRING_TYPES + NUMBER_TYPES) or
                        isinstance(ident, bool)):
                    continue
                token = (type(ident).__name__, ident)
                if token in seen or budget[0] <= 0:
                    continue
                seen.add(token); budget[0] -= 1
                entry = {'source': candidate['source'], 'referenceId': candidate,
                         'matchStatus': 'unverified',
                         'scope': 'modifier-declared exact ID via dataHub.getEntity; unverified',
                         'entityStatus': 'unknown',
                         'progressComponentStatus': 'unknown', 'progress': None}
                if result['getEntity']['getterStatus'] == 'available':
                    try:
                        entity = hub.getEntity(ident)
                        if entity is None:
                            entry['entityStatus'] = 'unknown'
                        else:
                            entry['entityStatus'] = 'available'
                            pkey_status, pkey = _probe_component_key(components, 'progress')
                            ps, progress = _probe_component(entity, pkey)
                            entry['progressComponentStatus'] = ps if pkey_status == 'available' else pkey_status
                            if entry['progressComponentStatus'] == 'available':
                                entry['progress'], _ = _gun_component_fields(
                                    progress, GUN_PROGRESS_FIELDS, 'getEntity(id).progress')
                    except Exception:
                        entry['entityStatus'] = 'unknown'
                refs.append(entry)
    result['getEntity'].update(status=result['getEntity']['getterStatus'],
                               attempted=len(refs),
                               resolved=sum(1 for item in refs
                                            if item['entityStatus'] == 'available'),
                               remainingBudget=budget[0])
    result['references'] = refs
    statuses = [v['status'] for v in result['collections'].values()]
    result['status'] = ('available' if 'available' in statuses else
                        ('partial' if 'partial' in statuses else 'unknown'))
    return result


def safe_gun_reload_probe(hub, components):
    try:
        return gun_reload_probe(hub, components)
    except Exception:
        return {'source': 'dataHub UI gun reload candidates', 'status': 'unknown',
                'semantics': 'unverified', 'collections': {}, 'references': [],
                'getEntity': {'getterStatus': 'unknown', 'status': 'unknown',
                              'resolved': 0, 'budget': GUN_REF_BUDGET},
                'error': 'probeFailed'}


def _raw_candidate(source, status, value=_MISSING):
    """Describe one fixed UI-derived candidate without assigning semantics."""
    available = status == 'available' and value is not _MISSING
    if available and isinstance(value, NUMBER_TYPES) and not isinstance(value, bool) \
            and not _finite(value):
        status, available = 'unknown', False
    return {'source': source, 'status': status if available else
            ('unknown' if status == 'available' else status),
            'type': type(value).__name__ if available else None,
            'raw': _candidate_value(value) if available else None,
            'semantics': 'unverified'}


def _getter_status(obj, name):
    value = _get(obj, name, _MISSING)
    return 'unsupported' if value is _MISSING or not callable(value) else 'available'


def _bounded_context_collection(hub, components, name, fields, limit=8):
    """Try one UI-named collection, keeping getter/key/component failures apart."""
    key_status, key = _probe_component_key(components, name)
    getter_status = _getter_status(hub, 'getEntityCollections')
    out = {'source': 'dataHub.getEntityCollections(%r)' % name,
           'semantics': 'unverified', 'status': 'unknown',
           'getterStatus': getter_status, 'callStatus': 'unknown',
           'componentKeyStatus': key_status, 'componentStatus': 'unknown',
           'rows': [], 'truncated': False, 'partial': False}
    if getter_status != 'available':
        out['callStatus'] = 'unsupported'
        out['status'] = 'unsupported'
        return out
    try:
        entities = hub.getEntityCollections(name)
    except Exception:
        out['callStatus'] = 'unknown'
        return out
    if entities is None:
        out['callStatus'] = 'unknown'
        return out
    out['callStatus'] = 'available'
    try:
        for index, entity in enumerate(entities):
            if index >= limit:
                out['truncated'] = True
                break
            row = {'entityId': _raw_candidate(name + '.entity.id', *_probe_read(entity, 'id'))}
            if key_status != 'available':
                row['componentStatus'] = key_status
            else:
                cstatus, comp = _probe_component(entity, key)
                row['componentStatus'] = cstatus
                if cstatus == 'available':
                    row['fields'], row['fieldStatus'] = {}, {}
                    for field in fields:
                        fstatus, value = _probe_read(comp, field)
                        row['fieldStatus'][field] = fstatus
                        row['fields'][field] = _raw_candidate(
                            name + '.' + field, fstatus, value)
            out['rows'].append(row)
        out['componentStatus'] = ('available' if any(
            row.get('componentStatus') == 'available' for row in out['rows']) else
            ('unknown' if key_status == 'available' else key_status))
        out['status'] = 'available'
    except Exception:
        out['status'] = 'partial' if out['rows'] else 'unknown'
        out['partial'] = bool(out['rows'])
    return out


def _single_collection_observation(collection, field, source, scope):
    """Select only an explicitly singleton, complete named-collection row."""
    result = {'source': source, 'status': 'unknown', 'raw': None, 'type': None,
              'semantics': 'unverified', 'unit': 'unverified', 'scope': scope}
    if (not isinstance(collection, dict) or collection.get('status') != 'available' or
            collection.get('partial') or collection.get('truncated')):
        return result
    rows = collection.get('rows')
    if not isinstance(rows, list) or len(rows) != 1:
        return result
    row = rows[0]
    if not isinstance(row, dict) or row.get('componentStatus') != 'available':
        return result
    candidate = row.get('fields', {}).get(field)
    if (not isinstance(candidate, dict) or candidate.get('status') != 'available' or
            candidate.get('raw') is None):
        return result
    result.update({'status': 'available', 'raw': candidate.get('raw'),
                   'type': candidate.get('type'),
                   'fieldSource': candidate.get('source')})
    return result


def _collection_clock_observation(battle_timer, battle_info):
    source = ('UI formula: battleInfo.collection.duration * 60 - '
              'battleTimer.collection.battleTime')
    result = {'source': source, 'status': 'unknown', 'raw': None, 'type': None,
              'semantics': 'unverified', 'inferred': True,
              'unit': 'seconds (assumed; unverified)',
              'formula': 'battleInfo.duration * 60 - battleTimer.battleTime',
              'formulaStatus': 'unverified', 'sourceUnit': 'unverified',
              'scope': ('Distinct battleTimer and battleInfo collection rows; same '
                        'snapshot only, assuming duration is minutes and battleTime seconds')}
    time_obs = _single_collection_observation(
        battle_timer, 'battleTime', 'dataHub.getEntityCollections("battleTimer").battleTime',
        'single row in named collection; no entity join')
    duration_obs = _single_collection_observation(
        battle_info, 'duration', 'dataHub.getEntityCollections("battleInfo").duration',
        'single row in named collection; no entity join')
    if (time_obs['status'] != 'available' or duration_obs['status'] != 'available' or
            not _finite(time_obs['raw']) or not _finite(duration_obs['raw']) or
            time_obs['raw'] < 0 or duration_obs['raw'] < 0):
        return result
    value = duration_obs['raw'] * 60.0 - time_obs['raw']
    if not _finite(value):
        return result
    result.update({'status': 'available', 'raw': value, 'type': type(value).__name__,
                   'sampleTs': None,
                   'routes': [time_obs['source'], duration_obs['source']]})
    return result


def _singleton_candidate(hub, getter, key_status, key, component_path, field):
    getter_status = _getter_status(hub, getter)
    out = {'source': 'dataHub.%s(CC.%s).%s' % (getter, component_path, field),
           'status': 'unknown', 'getterStatus': getter_status,
           'keyStatus': key_status, 'callStatus': 'unknown',
           'componentStatus': 'unknown', 'semantics': 'unverified',
           'raw': None, 'type': None}
    if getter_status != 'available':
        out['callStatus'] = 'unsupported'
        out['status'] = 'unsupported'
        return out
    if key_status != 'available':
        out['callStatus'] = key_status
        out['status'] = key_status
        return out
    call_status, obj = _call(hub, getter, key)
    out['callStatus'] = call_status
    if call_status != 'available':
        out['status'] = call_status
        return out
    component = obj
    if component_path:
        out['componentStatus'], component = _probe_read(obj, component_path)
    else:
        out['componentStatus'] = 'available'
    if out['componentStatus'] != 'available':
        out['status'] = out['componentStatus']
        return out
    status, value = _probe_read(component, field)
    candidate = _raw_candidate(out['source'], status, value)
    out.update(candidate)
    return out


def weapon_context_probe(hub, components):
    """Bounded, read-only UI-derived context candidates; no collection joins."""
    result = {'source': 'dataHub UI weapon context candidates',
              'status': 'unknown', 'semantics': 'unverified',
              'selfVehicle': {'source': 'dataHub.getFirstWatcher(CC.selfVehicle)',
                              'status': 'unknown', 'keyStatus': 'unknown',
                              'getterStatus': _getter_status(hub, 'getFirstWatcher'),
                              'callStatus': 'unknown', 'entityStatus': 'unknown'},
              'weaponController': {'source': 'selfVehicle.weaponController', 'status': 'unknown'},
              'collections': {},
              'slotContext': {'source': 'UI SlotRenderer _id / CC.weaponSlot',
                              'status': 'unavailable', 'semantics': 'unverified'}}
    key_status, key = _probe_component_key(components, 'selfVehicle')
    sv = result['selfVehicle']; sv['keyStatus'] = key_status
    if sv['getterStatus'] == 'unsupported':
        sv['callStatus'] = 'unsupported'; sv['status'] = 'unsupported'
    elif key_status != 'available':
        sv['callStatus'] = key_status; sv['status'] = key_status
    else:
        call_status, watcher = _call(hub, 'getFirstWatcher', key)
        sv['callStatus'] = call_status; sv['status'] = call_status
        if call_status == 'available':
            es, entity = _probe_read(watcher, 'entity'); sv['entityStatus'] = es
            if es == 'available':
                sv['status'] = 'available'
                id_status, eid = _probe_read(entity, 'id')
                sv['entityId'] = _raw_candidate('selfVehicle.entity.id', id_status, eid)
                cs, controller = _probe_read(entity, 'weaponController')
                result['weaponController']['status'] = cs
                if cs == 'available':
                    for field in ('selectedWeapon', 'activeIdWeapon'):
                        fs, value = _probe_read(controller, field)
                        result['weaponController'][field] = _raw_candidate(
                            'selfVehicle.weaponController.' + field, fs, value)
    specs = {'selfVehicle': ('selectedWeapon', 'activeIdWeapon'),
             'weaponController': ('selectedWeapon', 'activeIdWeapon')}
    for name, fields in specs.items():
        result['collections'][name] = _bounded_context_collection(
            hub, components, name, fields)
    controller = result['collections']['weaponController']
    result['observations'] = {
        'controllerSelectedWeapon': _single_collection_observation(
            controller, 'selectedWeapon',
            'dataHub.getEntityCollections("weaponController").selectedWeapon',
            'single weaponController collection row; not joined to weaponSlot; '
            'enum mapping unverified; UI predicate reference: '
            'docs/VALIDATION_0.3.4_B09_WEAPONS.ja.md L63'),
        'controllerActiveIdWeapon': _single_collection_observation(
            controller, 'activeIdWeapon',
            'dataHub.getEntityCollections("weaponController").activeIdWeapon',
            'single weaponController collection row; not joined to weaponSlot; '
            'enum/string meaning unverified')}
    result['observations']['controllerSelectedWeapon']['enumReference'] = (
        'docs/VALIDATION_0.3.4_B09_WEAPONS.ja.md L63; mapping unverified')
    statuses = [sv['status']] + [v['status'] for v in result['collections'].values()]
    result['status'] = 'available' if 'available' in statuses else (
        'unsupported' if all(s == 'unsupported' for s in statuses) else 'unknown')
    return result


def safe_weapon_context_probe(hub, components):
    try:
        return weapon_context_probe(hub, components)
    except Exception:
        return {'source': 'dataHub selfVehicle weapon UI context',
                'status': 'unknown', 'semantics': 'unverified',
                'selfVehicle': {'source': 'dataHub.getFirstWatcher(CC.selfVehicle)',
                                'status': 'unknown', 'keyStatus': 'unknown',
                                'getterStatus': 'unknown', 'callStatus': 'unknown',
                                'entityStatus': 'unknown'},
                'weaponController': {'source': 'selfVehicle.weaponController',
                                     'status': 'unknown'},
                'collections': {},
                'slotContext': {'source': 'UI SlotRenderer _id / CC.weaponSlot',
                                'status': 'unavailable',
                                'semantics': 'unverified'}, 'error': 'probeFailed'}


TORPEDO_TTX_VARIANTS = {
    'torpedo': 'torpedo',
    'torpedo_deepwater': 'torpedoDeepwater',
    'torpedo_alternative': 'torpedoAlt',
}


def _strict_scalar(value):
    return (isinstance(value, STRING_TYPES) or
            (isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)
             and _finite(value)))


def _exact_scalar(left, right):
    # Do not let Python's bool/int equality silently join unrelated IDs.
    # On Python 2, int/long (and str/unicode) are distinct types, so an equal
    # value can be a false negative here. That is deliberate: no join is safer
    # than a guess.
    return (_strict_scalar(left) and _strict_scalar(right) and
            type(left) is type(right) and left == right)


def _probe_field_raw(row, field):
    """Read the producer's raw scalar only when its field status is available."""
    if not isinstance(row, dict):
        return None
    statuses = row.get('fieldStatus')
    if not isinstance(statuses, dict) or statuses.get(field) != 'available':
        return None
    fields = row.get('fields')
    return fields.get(field) if isinstance(fields, dict) else None


def _probe_field_meta(row, field, meta_key='fieldMeta'):
    if not isinstance(row, dict):
        return {}
    entries = row.get(meta_key)
    entry = entries.get(field) if isinstance(entries, dict) else None
    return entry if isinstance(entry, dict) else {}


def _valid_id_scalar(value):
    if isinstance(value, bool):
        return False
    if isinstance(value, STRING_TYPES):
        # Empty and whitespace-only strings are not usable IDs. Do not strip or
        # case-fold the value used for matching.
        return bool(value) and value.strip() != ''
    if isinstance(value, NUMBER_TYPES):
        return _finite(value)
    return False


def _probe_id_value(row, field, meta_key='fieldMeta'):
    """Return (value, rejectReason). Truncated strings are never joinable."""
    value = _probe_field_raw(row, field)
    if not _valid_id_scalar(value):
        return None, 'invalidId'
    meta = _probe_field_meta(row, field, meta_key)
    if meta.get('truncated') is True:
        return None, 'truncatedId'
    if isinstance(value, STRING_TYPES):
        length = meta.get('stringLength')
        if (not isinstance(length, int) or isinstance(length, bool) or
                length != len(value)):
            return None, 'unverifiedLength'
    return value, None


def _probe_descriptor(row):
    """Return (descriptor, rejectReason); only a verified string may be output."""
    view_status = row.get('viewDataStatus') if isinstance(row, dict) else None
    if view_status != 'available':
        return None, view_status or 'unknown'
    statuses = row.get('viewDataFieldStatus') if isinstance(row, dict) else None
    status = statuses.get('paramsDescriptor') if isinstance(statuses, dict) else 'unknown'
    if status != 'available':
        return None, status or 'unknown'
    view = row.get('viewData')
    value = view.get('paramsDescriptor') if isinstance(view, dict) else None
    meta = _probe_field_meta(row, 'paramsDescriptor', 'viewDataFieldMeta')
    if value is None:
        return None, 'none'
    if not isinstance(value, STRING_TYPES):
        return None, 'nonString'
    if meta.get('truncated') is True:
        return None, 'truncated'
    length = meta.get('stringLength')
    if (not isinstance(length, int) or isinstance(length, bool) or
            length != len(value)):
        return None, 'unverifiedLength'
    return value, None


# Same-snapshot namespace candidates. These are value-equality observations,
# never API contracts and never overrides of legacy identity fields.
_IDENTITY_MATCH_LIMIT = 8
_IDENTITY_STATIC_HINT = (
    'Components.Torpedo.ownerID:Integer(sync=false); namespace comment absent')
_IDENTITY_TARGET_HINT = (
    'Components.WaveHit.targetID:Integer(pk=true); static comment '
    '"Waved vehicle ID"; not a Python join contract')
_OWNER_VALIDATION_SCOPE = {
    'records': ['B10', 'B12', 'B14'],
    'rowCount': 2014,
    'trackCount': 4,
    'conditions': ['activeOnly', 'selfOnly', 'singleShipSnapshot'],
    'notCovered': ['enemyTorpedo', 'allyTorpedo', 'multiShipSnapshot',
                   'crossBattle', 'apiContract'],
    'recordIdentity': 'primary',
    'appliesTo': 'offlineEvidenceOnly',
}
_TARGET_VALIDATION_SCOPE = {
    'records': ['B27'],
    'rowCount': 439,
    'targetCount': 1,
    'conditions': ['activeOnly', 'enemyTarget', 'sevenShipSnapshot'],
    'notCovered': ['selfTarget', 'multipleTargets', 'targetSwitch',
                   'ownerId', 'apiContract'],
    'recordIdentity': 'primary',
    'appliesTo': 'offlineEvidenceOnly',
}


def _identity_type(value):
    name = type(value).__name__
    return name if name in ('bool', 'int', 'long', 'float', 'str', 'unicode',
                            'NoneType', 'list', 'tuple', 'dict') else 'object'


def _identity_reject(value, meta=None):
    """Return a fixed rejection reason; only strict joinable scalars pass.

    No stringification, trimming, case-folding or numeric coercion. A string
    that may have been truncated by an upstream candidate copy is rejected.
    """
    if value is _MISSING:
        return 'missingField'
    if value is None:
        return 'noneValue'
    if isinstance(value, bool):
        return 'strictTypeRejected'
    if isinstance(value, STRING_TYPES):
        if not value or value.strip() == '':
            return 'invalidId'
        length = len(value)
        if isinstance(meta, dict):
            if meta.get('truncated') is True:
                return 'truncatedId'
            declared = meta.get('stringLength')
            if declared is not None and (
                    isinstance(declared, bool) or
                    not isinstance(declared, NUMBER_TYPES) or
                    declared != length):
                return 'unverifiedLength'
        # Candidate copies may cut strings at this length; an exact 128-char
        # token cannot be distinguished from a truncated prefix.
        if length >= _CANDIDATE_STRING_LIMIT:
            return 'possiblyTruncatedId'
        return None
    if isinstance(value, NUMBER_TYPES):
        return None if _finite(value) else 'nonFinite'
    return 'strictTypeRejected'


def _ship_vehicle_index(ships):
    """Index observed vehicle IDs, keeping duplicates and gaps explicit."""
    result = {'source': 'sameSnapshot.ships[].vehicleId',
              'status': 'unknown', 'completeness': 'unknown',
              'count': None, 'validCount': 0, 'missingCount': 0,
              'invalidCount': 0, 'duplicateIdCount': 0,
              'indexStatus': 'unknown', 'reason': None,
              'index': {}}
    if not isinstance(ships, list):
        result['reason'] = 'shipsNotList'
        return result
    result['count'] = len(ships)
    result['status'] = 'available'
    if not ships:
        result['reason'] = 'shipsEmptyCompletenessUnknown'
        return result
    seen = {}
    for index, ship in enumerate(ships):
        value = _get(ship, 'vehicleId', _MISSING)
        reason = _identity_reject(value)
        if reason is not None:
            if reason == 'missingField':
                result['missingCount'] += 1
            else:
                result['invalidCount'] += 1
            continue
        key = (type(value), value)
        seen.setdefault(key, []).append(index)
    for key, indexes in seen.items():
        if len(indexes) > 1:
            result['duplicateIdCount'] += 1
        result['index'][key] = [{
            'rowRef': 'ships[%d]' % index,
            'playerId': _get(ships[index], 'playerId', _MISSING),
        } for index in indexes]
    result['validCount'] = sum(len(indexes) for indexes in seen.values())
    if result['duplicateIdCount']:
        result['indexStatus'] = 'duplicate'
    elif result['missingCount'] or result['invalidCount']:
        result['indexStatus'] = 'incomplete'
    else:
        result['indexStatus'] = 'uniqueObserved'
    return result


def _self_match_candidate(matches, self_player_id):
    """Describe, never decide, whether a matched ship is the self player."""
    result = {'source': 'sameSnapshot.ships[].playerId == self.playerId',
              'status': 'unknown', 'resolution': 'candidate',
              'basis': 'strictTypeAndValueEqualityOnly',
              'isOwnOverride': False, 'usedForIsOwn': False}
    if not matches:
        result['reason'] = 'noExactMatch'
        return result
    if len(matches) > 1:
        result['reason'] = 'ambiguousMultiple'
        return result
    if _identity_reject(self_player_id) is not None:
        result['reason'] = 'selfPlayerIdUnavailable'
        return result
    player_id = matches[0].get('playerId', _MISSING)
    if _identity_reject(player_id) is not None:
        result['reason'] = 'matchedShipPlayerIdUnavailable'
        return result
    if _exact_scalar(player_id, self_player_id):
        result['status'] = 'exactCandidate'
        result['reason'] = None
    else:
        result['status'] = 'nonExactCandidate'
        result['reason'] = 'strictValueDiffers'
    return result


def _identity_candidate(index_info, value, meta, field, row_ref,
                        static_hint, scope, self_player_id=None):
    """Build one candidate object without copying the raw ID value."""
    candidate = {
        'source': {'field': field, 'snapshot': 'sameState',
                   'contractStatus': 'unverified', 'staticHint': static_hint,
                   'apiCallAdded': False},
        'rawType': _identity_type(value) if value is not _MISSING else None,
        'rowRef': row_ref,
        'matchStatus': 'notEvaluated',
        'completeness': 'unknown',
        'resolution': 'notEvaluated',
        'unknownReason': None,
        'matchCount': 0,
        'matchesTruncated': False,
        'candidateMatches': [],
        'inferred': {
            'namespaceCandidate': 'ships.vehicleId',
            'status': 'candidate',
            'basis': 'sameSnapshotStrictValueEqualityOnly',
            'contractStatus': 'unverified',
            'isOwnOverride': False,
        },
        'validationScope': scope,
    }
    reason = _identity_reject(value, meta)
    if reason is not None:
        candidate['unknownReason'] = reason
        self_match = _self_match_candidate([], self_player_id) \
            if self_player_id is not None else None
        if self_match is not None:
            candidate['selfMatchCandidate'] = self_match
        return candidate, False
    if index_info.get('status') != 'available':
        candidate['unknownReason'] = (index_info.get('reason') or
                                      'shipsCollectionUnavailable')
        self_match = _self_match_candidate([], self_player_id) \
            if self_player_id is not None else None
        if self_match is not None:
            candidate['selfMatchCandidate'] = self_match
        return candidate, False

    key = (type(value), value)
    matches = index_info.get('index', {}).get(key, [])
    total = len(matches)
    candidate['matchCount'] = total
    candidate['matchesTruncated'] = total > _IDENTITY_MATCH_LIMIT
    output_matches = []
    self_statuses = []
    for match in matches[:_IDENTITY_MATCH_LIMIT]:
        entry = {'collection': 'ships', 'field': 'vehicleId',
                 'match': 'exact', 'rowRef': match['rowRef']}
        if self_player_id is not None:
            link = _self_match_candidate([match], self_player_id)
            entry['selfMatchStatus'] = link['status']
            self_statuses.append(link['status'])
        output_matches.append(entry)
    candidate['candidateMatches'] = output_matches

    if total == 0:
        candidate['matchStatus'] = 'noExactMatch'
        candidate['resolution'] = 'indeterminate'
        candidate['unknownReason'] = 'shipsCollectionCompletenessNotReported'
    elif total > 1:
        candidate['matchStatus'] = 'ambiguousMultiple'
        candidate['resolution'] = 'ambiguous'
        candidate['unknownReason'] = 'multipleShipsVehicleIdMatches'
    elif index_info.get('indexStatus') != 'uniqueObserved':
        # A missing/invalid/duplicated sibling means the observed index is not
        # a trustworthy unique index, even if this value has one match.
        candidate['matchStatus'] = 'unknown'
        candidate['resolution'] = 'indeterminate'
        candidate['unknownReason'] = ('shipsVehicleIdIndex' +
                                      str(index_info.get('indexStatus')).capitalize())
    else:
        candidate['matchStatus'] = 'uniqueExact'
        candidate['resolution'] = 'candidate'

    if self_player_id is not None:
        if total == 1 and candidate.get('matchStatus') == 'uniqueExact':
            candidate['selfMatchCandidate'] = _self_match_candidate(
                matches[:1], self_player_id)
        else:
            self_match = _self_match_candidate(matches, self_player_id)
            if total > 1 and self_statuses and all(
                    status == 'exactCandidate' for status in self_statuses):
                self_match['status'] = 'unknown'
                self_match['reason'] = 'ambiguousMultiple'
            elif total == 1:
                # The value matched, but the observed ship index was not a
                # trustworthy unique index in this frame.
                self_match['status'] = 'unknown'
                self_match['reason'] = candidate.get('unknownReason')
            candidate['selfMatchCandidate'] = self_match
    return candidate, True


def _wave_hit_usage(wave_hit_probe):
    """Only a complete, untruncated WaveHit collection is usable this frame."""
    usage = {'source': 'sameSnapshot.waveHitProbe',
             'status': 'skipped', 'reason': None, 'rowsConsidered': 0}
    if not isinstance(wave_hit_probe, dict):
        usage['reason'] = 'waveHitProbeUnavailable'
        return usage, []
    collection = wave_hit_probe.get('collection')
    collection = collection if isinstance(collection, dict) else {}
    if wave_hit_probe.get('status') != 'available':
        usage['reason'] = 'waveHitCollectionStatusNotAvailable'
        return usage, []
    if (wave_hit_probe.get('partial') is True or
            wave_hit_probe.get('truncated') is True or
            collection.get('truncated') is True):
        usage['reason'] = 'waveHitCollectionPartialOrTruncated'
        return usage, []
    if collection.get('complete') is not True:
        usage['reason'] = 'waveHitCollectionCompletenessUnknown'
        return usage, []
    rows = wave_hit_probe.get('rows')
    if not isinstance(rows, list):
        usage['reason'] = 'waveHitRowsNotList'
        return usage, []
    usage['status'] = 'evaluated'
    usage['rowsConsidered'] = len(rows)
    return usage, rows


def identity_candidates(ships, self_state, torpedoes, wave_hit_probe):
    """Pure same-frame identity candidate comparison; no history or API calls.

    Existing raw fields (`ownerId`, WaveHit `targetID`, `isOwn`, `owner`) are
    read only and never rewritten. Candidate zero matches remain indeterminate
    because the current ships enumeration does not report completeness.
    """
    self_player_id = (_get(self_state, 'playerId', _MISSING)
                      if isinstance(self_state, dict) else _MISSING)
    index_info = _ship_vehicle_index(ships)
    out = {'source': 'sameSnapshotValueEqualityCandidates',
           'status': 'unknown', 'semantics': 'unverified',
           'contractStatus': 'unverified', 'history': 'none',
           'apiCallsAdded': 0,
           'shipsCollection': {
               'source': index_info['source'],
               'status': index_info['status'],
               'completeness': 'unknown',
               'count': index_info['count'],
               'validCount': index_info['validCount'],
               'missingCount': index_info['missingCount'],
               'invalidCount': index_info['invalidCount'],
               'duplicateIdCount': index_info['duplicateIdCount'],
               'indexStatus': index_info['indexStatus'],
               'reason': index_info['reason'],
           },
           'torpedoRowsStatus': 'notEvaluated',
           'waveHitUsage': None,
           'evaluatedCount': 0,
           'exactCount': 0,
           'identityCandidates': []}
    candidates = out['identityCandidates']

    if isinstance(torpedoes, list):
        out['torpedoRowsStatus'] = 'evaluated'
        for index, row in enumerate(torpedoes):
            owner_id = (_get(row, 'ownerId', _MISSING)
                        if isinstance(row, dict) else _MISSING)
            candidate, evaluated = _identity_candidate(
                index_info, owner_id, None, 'torpedoes[].ownerId',
                'torpedoes[%d]' % index, _IDENTITY_STATIC_HINT,
                _OWNER_VALIDATION_SCOPE, self_player_id)
            if evaluated:
                out['evaluatedCount'] += 1
            if candidate.get('matchStatus') == 'uniqueExact':
                out['exactCount'] += 1
            candidates.append({'candidateRef': 'torpedo:%d' % index,
                               'rowRef': 'torpedoes[%d]' % index,
                               'ownerNamespaceCandidate': candidate})
    else:
        out['torpedoRowsStatus'] = 'notEvaluated'

    usage, wave_rows = _wave_hit_usage(wave_hit_probe)
    out['waveHitUsage'] = usage
    for index, row in enumerate(wave_rows):
        statuses = row.get('fieldStatus') if isinstance(row, dict) else None
        fields = row.get('fields') if isinstance(row, dict) else None
        target_id = _MISSING
        if isinstance(statuses, dict) and statuses.get('targetID') == 'available' \
                and isinstance(fields, dict):
            target_id = fields.get('targetID', _MISSING)
        meta = None
        if isinstance(row, dict):
            metas = row.get('fieldMeta')
            if isinstance(metas, dict):
                meta = metas.get('targetID')
        candidate, evaluated = _identity_candidate(
            index_info, target_id, meta,
            'waveHitProbe.rows[].fields.targetID',
            'waveHitProbe.rows[%d]' % index, _IDENTITY_TARGET_HINT,
            _TARGET_VALIDATION_SCOPE)
        if evaluated:
            out['evaluatedCount'] += 1
        if candidate.get('matchStatus') == 'uniqueExact':
            out['exactCount'] += 1
        candidates.append({'candidateRef': 'waveHit:%d' % index,
                           'rowRef': 'waveHitProbe.rows[%d]' % index,
                           'targetIdNamespaceCandidate': candidate})

    if out['exactCount']:
        out['status'] = 'available' if out['evaluatedCount'] == len(candidates) \
            else 'partial'
    elif out['evaluatedCount']:
        out['status'] = 'partial'
    else:
        out['status'] = 'unknown'
    return out


def safe_identity_candidates(ships, self_state, torpedoes, wave_hit_probe):
    """Contain helper failures so the caller keeps its existing state."""
    try:
        return identity_candidates(ships, self_state, torpedoes, wave_hit_probe)
    except Exception:
        return {'source': 'sameSnapshotValueEqualityCandidates',
                'status': 'unknown', 'semantics': 'unverified',
                'contractStatus': 'unverified', 'history': 'none',
                'apiCallsAdded': 0, 'shipsCollection': {},
                'torpedoRowsStatus': 'notEvaluated', 'waveHitUsage': None,
                'evaluatedCount': 0, 'exactCount': 0,
                'identityCandidates': [], 'error': 'probeFailed'}


def _ttx_read(obj, key):
    if obj is None:
        return 'none', None
    try:
        if isinstance(obj, dict):
            if key not in obj:
                return 'missing', None
            value = obj[key]
        else:
            value = getattr(obj, key, _MISSING)
            if value is _MISSING:
                return 'missing', None
    except Exception:
        return 'readError', None
    return ('none', None) if value is None else ('available', value)


def _selected_weapon_type(observations):
    obs = observations.get('controllerSelectedWeapon', {}) if isinstance(observations, dict) else {}
    if obs.get('status') != 'available':
        return obs.get('status', 'unknown'), None
    value = obs.get('raw')
    if not isinstance(value, NUMBER_TYPES) or isinstance(value, bool) or not _finite(value):
        return 'nonNumeric', None
    return 'available', value


def _ttx_number(source, status, value, unit_hint):
    result = {'source': source, 'status': status, 'raw': None, 'type': None,
              'unitHint': unit_hint, 'semantics': 'unverified'}
    if status != 'available':
        return result
    result['type'] = type(value).__name__
    if value is None:
        result['status'] = 'none'
    elif isinstance(value, bool) or not isinstance(value, NUMBER_TYPES):
        result['status'] = 'nonNumeric'
    elif not _finite(value):
        result['status'] = 'nonFinite'
    elif value < -1000000 or value > 1000000:
        result['status'] = 'outOfBounds'
    else:
        result.update(status='available', raw=value)
    return result


def _ttx_diff_field(ttx, name, prefix, unit_hint):
    status, diff = _ttx_read(ttx, name)
    base = prefix + '.' + name
    if status != 'available':
        field = _ttx_number(base + '.value', status, None, unit_hint)
        delta = _ttx_number(base + '.delta', status, None, unit_hint)
    else:
        value_status, value = _ttx_read(diff, 'value')
        delta_status, delta_value = _ttx_read(diff, 'delta')
        field = _ttx_number(base + '.value', value_status, value, unit_hint)
        delta = _ttx_number(base + '.delta', delta_status, delta_value, unit_hint)
    field['delta'] = delta
    return field


def _ttx_variant(ttx_root, variant, member):
    source = 'dataHub.getEntityCollections("selfVehicle")[CC.selfVehicle].shipTTX.torpedoes.' + member
    result = {'source': source, 'status': 'unknown', 'fields': {}}
    torpedoes_status, torpedoes = _ttx_read(ttx_root, 'torpedoes')
    if torpedoes_status != 'available':
        result['status'] = torpedoes_status
        return result
    variant_status, ttx = _ttx_read(torpedoes, member)
    if variant_status != 'available':
        result['status'] = variant_status
        return result
    result['status'] = 'available'
    result['fields'] = {
        'speed': _ttx_diff_field(ttx, 'speed', source, 'knots (TTX UI)'),
        'maxDist': _ttx_diff_field(ttx, 'maxDist', source, 'km (TTX UI)'),
    }
    return result


def _leaf_status(fields):
    """Aggregate the selected variant's value/delta leaves, independently."""
    statuses = []
    for name in ('speed', 'maxDist'):
        field = fields.get(name) if isinstance(fields, dict) else None
        if not isinstance(field, dict):
            statuses.append('unknown')
            continue
        statuses.append(field.get('status', 'unknown'))
        delta = field.get('delta')
        statuses.append(delta.get('status', 'unknown')
                        if isinstance(delta, dict) else 'unknown')
    if not statuses:
        return 'unknown'
    if all(status == 'available' for status in statuses):
        return 'available'
    if any(status == 'available' for status in statuses):
        return 'partial'
    for status in statuses:
        if status not in (None, 'unknown'):
            return status
    return 'unknown'


def _variant_route_status(self_vehicle, variants):
    """TTX route status independent of selection (pinger included)."""
    statuses = [entry.get('status') for entry in variants.values()
                if isinstance(entry, dict)]
    if statuses:
        if all(status == 'available' for status in statuses):
            return 'available'
        if any(status == 'available' for status in statuses):
            return 'partial'
        for status in statuses:
            if status not in (None, 'unknown'):
                return status
        return 'unknown'
    for key in ('shipTTXStatus', 'componentStatus', 'collectionStatus'):
        status = self_vehicle.get(key)
        if status not in (None, 'unknown'):
            return status
    return 'unknown'


def selected_torpedo_params_probe(hub, components, weapon_context, weapon_hub):
    """Read-only selected descriptor -> fixed selfVehicle shipTTX candidates."""
    out = {'source': 'dataHub.getEntityCollections("selfVehicle")[CC.selfVehicle].shipTTX.torpedoes',
           'status': 'unknown', 'semantics': 'unverified',
           'selection': {'source': 'weaponContextProbe.controllerSelectedWeapon + weaponHubProbe.weaponSlot.type + ammo.id + viewData.paramsDescriptor',
                         'status': 'unknown', 'reason': None, 'descriptor': None},
           'selfVehicle': {'status': 'unknown', 'collectionStatus': 'unknown',
                           'componentStatus': 'unknown', 'shipTTXStatus': 'unknown'},
           'variant': None, 'variantStatus': 'unknown', 'leafStatus': 'unknown',
           'ttxStatus': 'unknown', 'stages': {}, 'fields': {}, 'variants': {},
           'displaySemantics': {
               'speed': {'candidate': 'staticTTXDisplayCandidate',
                         'liveAdjusted': False,
                         'battleTooltipAlternativeOverridePossible': True},
               'maxDist': {'candidate': 'staticTTXDisplayCandidate',
                           'liveAdjusted': False}}}
    # Reuse the already collected, singleton observations; never use activeIdWeapon
    # or torpedoArmament.selectedAmmoId as a join key.
    try:
        obs = weapon_context.get('observations', {})
        selected_status, selected_type = _selected_weapon_type(obs)
        collections = (weapon_hub.get('collections', {})
                       if isinstance(weapon_hub, dict) else {})
        slots = (collections.get('weaponSlot', {})
                 if isinstance(collections, dict) else {})
        ammos = (collections.get('ammo', {})
                 if isinstance(collections, dict) else {})
        slots = slots if isinstance(slots, dict) else {}
        ammos = ammos if isinstance(ammos, dict) else {}
        selection = out['selection']
        if selected_status != 'available':
            selection['status'] = 'unknown'
            selection['reason'] = selected_status
        elif any(c.get('status') != 'available' or c.get('partial') or c.get('truncated')
                 for c in (slots, ammos)):
            selection['status'] = 'unknown'
            selection['reason'] = ('truncated' if any(c.get('truncated') for c in (slots, ammos))
                                   else 'partial' if any(c.get('partial') or c.get('status') == 'partial'
                                                         for c in (slots, ammos)) else 'unknown')
        else:
            slot_rows, slot_incomplete = [], False
            for row in slots.get('rows', []):
                if (not isinstance(row, dict) or
                        row.get('componentStatus') != 'available' or
                        row.get('fieldStatus', {}).get('type') != 'available'):
                    # A missing component/type row could be the selected slot;
                    # never ignore it to manufacture a unique match.
                    slot_incomplete = True
                    continue
                raw_type = _probe_field_raw(row, 'type')
                if not (isinstance(raw_type, NUMBER_TYPES) and
                        not isinstance(raw_type, bool) and _finite(raw_type)):
                    slot_incomplete = True
                    continue
                if _exact_scalar(raw_type, selected_type):
                    slot_rows.append(row)
            if len(slot_rows) > 1:
                selection['status'] = 'unknown'
                selection['reason'] = 'nonUnique'
            elif slot_incomplete:
                selection['status'] = 'unknown'
                selection['reason'] = 'incomplete'
            elif len(slot_rows) != 1:
                selection['status'] = 'unknown'
                selection['reason'] = 'noMatch'
            else:
                slot = slot_rows[0]
                slot_id, slot_id_reason = _probe_id_value(slot, 'id')
                if slot_id is None:
                    selection['status'] = 'unknown'
                    selection['reason'] = slot_id_reason
                else:
                    ammo_rows, ammo_incomplete = [], False
                    ammo_reason = None
                    for row in ammos.get('rows', []):
                        if (not isinstance(row, dict) or
                                row.get('componentStatus') != 'available'):
                            ammo_incomplete = True
                            continue
                        ammo_id, reject_reason = _probe_id_value(row, 'id')
                        if ammo_id is None:
                            ammo_incomplete = True
                            if ammo_reason is None:
                                ammo_reason = reject_reason
                            continue
                        if _exact_scalar(ammo_id, slot_id):
                            ammo_rows.append(row)
                    if len(ammo_rows) > 1:
                        selection['status'] = 'unknown'
                        selection['reason'] = 'nonUnique'
                    elif ammo_incomplete:
                        selection['status'] = 'unknown'
                        selection['reason'] = ammo_reason or 'incomplete'
                    elif len(ammo_rows) != 1:
                        selection['status'] = 'unknown'
                        selection['reason'] = 'noMatch'
                    else:
                        descriptor, descriptor_reason = _probe_descriptor(
                            ammo_rows[0])
                        if descriptor is None:
                            selection['status'] = 'unknown'
                            selection['reason'] = ('descriptor' +
                                descriptor_reason[:1].upper() +
                                descriptor_reason[1:])
                        else:
                            selection['descriptor'] = descriptor
                            if descriptor == 'pinger':
                                selection['status'] = 'notApplicable'
                                out['status'] = 'notApplicable'
                            elif descriptor not in TORPEDO_TTX_VARIANTS:
                                # No case/whitespace normalization and no
                                # fallback to another variant.
                                selection['status'] = 'unknown'
                                selection['reason'] = 'unknownDescriptor'
                            else:
                                selection['status'] = 'available'
                                out['variant'] = descriptor
    except Exception:
        out['selection']['status'] = 'unknown'
        out['selection']['reason'] = 'probeFailed'

    # The original entity is needed because the ordinary whitelist intentionally
    # does not retain shipTTX. Only a complete singleton collection is eligible.
    sv = out['selfVehicle']
    getter_status = _getter_status(hub, 'getEntityCollections')
    if getter_status != 'available':
        sv['collectionStatus'] = sv['status'] = 'unsupported'
    else:
        try:
            entities = hub.getEntityCollections('selfVehicle')
            if entities is None:
                sv['collectionStatus'] = 'unknown'
            else:
                rows = []
                for index, entity in enumerate(entities):
                    if index >= 2:
                        sv['collectionStatus'] = 'truncated'
                        break
                    rows.append(entity)
                else:
                    sv['collectionStatus'] = 'available'
                if sv['collectionStatus'] == 'available' and len(rows) != 1:
                    sv['collectionStatus'] = 'unknown' if not rows else 'multiple'
                if sv['collectionStatus'] == 'available':
                    key_status, key = _probe_component_key(components, 'selfVehicle')
                    if key_status != 'available':
                        sv['componentStatus'] = key_status
                    else:
                        cs, component = _probe_component(rows[0], key)
                        sv['componentStatus'] = cs
                        if cs == 'available':
                            ts, ship_ttx = _ttx_read(component, 'shipTTX')
                            sv['shipTTXStatus'] = ts
                            sv['status'] = ts
                            if ts == 'available':
                                for descriptor, member in TORPEDO_TTX_VARIANTS.items():
                                    out['variants'][descriptor] = _ttx_variant(ship_ttx, descriptor, member)
        except Exception:
            sv['collectionStatus'] = 'partial'
    selected_variant = None
    if out['selection']['status'] == 'available':
        selected_variant = out['variants'].get(out['selection']['descriptor'])
        if isinstance(selected_variant, dict):
            out['fields'] = selected_variant.get('fields', {})
            out['variantStatus'] = selected_variant.get('status', 'unknown')
            out['leafStatus'] = _leaf_status(out['fields'])
        else:
            out['variantStatus'] = 'unknown'
            out['leafStatus'] = 'unknown'
    out['ttxStatus'] = _variant_route_status(sv, out['variants'])
    out['stages'] = {
        'selection': out['selection']['status'],
        'selfVehicle': sv['status'],
        'shipTTX': sv['shipTTXStatus'],
        'variants': out['ttxStatus'],
        'variant': out['variantStatus'],
        'leaf': out['leafStatus'],
    }
    # Top-level status is the selected result, never just a successful
    # selfVehicle collection. A variant parent being available does not mean
    # its FloatDiff leaves are available; read leafStatus/field status too.
    if out['selection']['status'] == 'notApplicable':
        out['status'] = 'notApplicable'
    elif out['selection']['status'] != 'available' or selected_variant is None:
        out['status'] = 'unknown'
    else:
        out['status'] = out['variantStatus']
    return out


def safe_selected_torpedo_params_probe(hub, components, weapon_context, weapon_hub):
    try:
        return selected_torpedo_params_probe(hub, components, weapon_context, weapon_hub)
    except Exception:
        return {'source': 'dataHub selfVehicle shipTTX torpedo candidates',
                'status': 'unknown', 'semantics': 'unverified',
                'selection': {'status': 'unknown', 'descriptor': None},
                'selfVehicle': {'status': 'unknown'}, 'variant': None,
                'variantStatus': 'unknown', 'leafStatus': 'unknown',
                'ttxStatus': 'unknown', 'stages': {},
                'fields': {}, 'variants': {}, 'error': 'probeFailed'}


PARAMETER_FIELDS = ('ownerID', 'id', 'baseValue', 'currentValue', 'source',
                    'status', 'type')
PARAMETER_NAMES = {'torpedo': 'torpedoSpeed',
                   'torpedo_alternative': 'torpedoSpeedAlt',
                   'torpedo_deepwater': 'torpedoSpeedDeepwater'}


def _owner_key_scalar(value):
    """Use only UI-like scalar spelling; never stringify bools/objects."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, STRING_TYPES):
        return value if value and value.strip() and len(value) <= 128 else None
    if isinstance(value, NUMBER_TYPES) and _finite(value):
        text = str(value)
        return text if text and len(text) <= 128 else None
    return None


def torpedo_tooltip_parameter_probe(hub, components, selected_torpedo):
    """Collect fixed parameter candidates; only exact proven UI-key matches select."""
    selection = selected_torpedo.get('selection', {}) if isinstance(selected_torpedo, dict) else {}
    descriptor = selection.get('descriptor') if isinstance(selection, dict) else None
    out = {'source': 'dataHub playerAvatar owner + parameter candidates',
           'status': 'unknown', 'semantics': 'unverified',
           'ownerEntityId': {'source': "getEntityCollections('playerAvatar').entity.id",
                             'status': 'unknown', 'raw': None, 'type': None},
           'parameterName': PARAMETER_NAMES.get(descriptor),
           'ownerKeyCandidate': None,
           'parameterCollection': {'status': 'unknown', 'getterStatus': 'unknown',
                                   'callStatus': 'unknown', 'componentKeyStatus': 'unknown',
                                   'rows': [], 'partial': False, 'truncated': False},
           'selectedParameter': {'status': 'unknown', 'reason': 'unverifiedShape',
                                 'fields': {}, 'ownerMatchStatus': 'unknown',
                                 'matchBasis': 'unverified'},
           'stages': {'owner': 'unknown', 'parameterCollection': 'unknown',
                      'match': 'unknown'}}
    if not isinstance(descriptor, STRING_TYPES):
        out['selectedParameter'].update(status='notApplicable', reason='unknownDescriptor')
        return out
    if descriptor == 'pinger':
        out['selectedParameter'].update(status='notApplicable', reason='pinger')
        out['stages']['match'] = 'notApplicable'
        return out
    if descriptor not in PARAMETER_NAMES:
        out['selectedParameter'].update(reason='unknownDescriptor')
        return out

    # GUI SlotRenderer sets ownerEntity from CC.playerAvatar for non-airplane weapons.
    # Only a complete singleton collection row is a usable Python candidate.
    owner = out['ownerEntityId']
    getter_status = _getter_status(hub, 'getEntityCollections')
    owner_collection_status = 'unknown'
    if getter_status != 'available':
        owner_collection_status = 'unsupported'
    else:
        try:
            entities = hub.getEntityCollections('playerAvatar')
            if entities is not None:
                rows = []
                truncated = False
                for index, entity in enumerate(entities):
                    if index >= 8:
                        truncated = True
                        break
                    rows.append(entity)
                if truncated:
                    owner_collection_status = 'truncated'
                elif len(rows) != 1:
                    owner_collection_status = 'unknown' if not rows else 'multiple'
                else:
                    id_status, entity_id = _probe_read(rows[0], 'id')
                    if (id_status == 'available' and _valid_id_scalar(entity_id) and
                            (not isinstance(entity_id, STRING_TYPES) or len(entity_id) <= 128)):
                        owner.update(status='available', raw=_candidate_value(entity_id),
                                     type=type(entity_id).__name__)
                        owner_collection_status = 'available'
                    else:
                        owner_collection_status = (id_status if id_status != 'available'
                            else 'unknown')
        except Exception:
            owner_collection_status = 'unknown'
    out['stages']['owner'] = owner_collection_status
    owner_key_id = _owner_key_scalar(owner.get('raw')) if owner.get('status') == 'available' else None
    param_name = out['parameterName']
    if owner_key_id is not None:
        candidate_key = owner_key_id + '_' + param_name
        if len(candidate_key) <= 128:
            out['ownerKeyCandidate'] = candidate_key

    # Keep the route stages distinct: component key, getter, call, then fields.
    route = out['parameterCollection']
    key_status, key = _probe_component_key(components, 'parameter')
    route['componentKeyStatus'] = key_status
    route['componentKeyCandidate'] = _candidate_value(key) if key_status == 'available' else None
    route['getterStatus'] = getter_status
    if getter_status != 'available':
        route.update(status='unsupported', callStatus='unsupported')
    elif key_status != 'available':
        route.update(status=key_status, callStatus=key_status)
    else:
        try:
            entities = hub.getEntityCollections('parameter')
            if entities is not None:
                route['callStatus'] = 'available'
                for index, entity in enumerate(entities):
                    if index >= 64:
                        route['truncated'] = True
                        break
                    row = {'entityIdCandidate': _raw_candidate(
                        'parameter.entity.id', *_probe_read(entity, 'id'))}
                    cs, component = _probe_component(entity, key)
                    row['componentStatus'] = cs
                    if cs == 'available':
                        row['fields'], row['fieldStatus'], row['fieldMeta'] = {}, {}, {}
                        for field in PARAMETER_FIELDS:
                            fs, value = _probe_read(component, field)
                            row['fieldStatus'][field] = fs
                            row['fieldMeta'][field] = (_candidate_meta(value)
                                if fs == 'available' else
                                {'type': None, 'stringLength': None, 'truncated': False})
                            candidate = _raw_candidate('parameter.' + field, fs, value)
                            if field in ('baseValue', 'currentValue') and fs == 'available':
                                if value is None:
                                    candidate['status'] = 'none'
                                    candidate['raw'] = None
                                elif (isinstance(value, bool) or
                                        not isinstance(value, NUMBER_TYPES)):
                                    candidate['status'] = 'nonNumeric'
                                    candidate['raw'] = None
                                elif not _finite(value):
                                    candidate['status'] = 'nonFinite'
                                    candidate['raw'] = None
                                elif value < -1000000 or value > 1000000:
                                    candidate['status'] = 'outOfBounds'
                                    candidate['raw'] = None
                            row['fields'][field] = candidate
                    route['rows'].append(row)
                route['status'] = 'available'
        except Exception:
            route['status'] = 'partial' if route['rows'] else 'unknown'
            route['partial'] = bool(route['rows'])
    out['stages']['parameterCollection'] = route['status']

    # Parameter has a composite primary key: (ownerID, id). The GUI's
    # ownerKeyCandidate is retained as diagnostic metadata only; it is not the
    # component.id value and must never be used as a fallback selector.
    owner_id = owner.get('raw') if owner.get('status') == 'available' else None
    parameter_name = out.get('parameterName')
    matches, incomplete = [], False
    for row in route.get('rows', []):
        if row.get('componentStatus') != 'available':
            incomplete = True
            continue
        fields = row.get('fields', {})
        id_field = fields.get('id') if isinstance(fields, dict) else None
        owner_field = fields.get('ownerID') if isinstance(fields, dict) else None
        component_id = id_field.get('raw') if isinstance(id_field, dict) else None
        component_owner = owner_field.get('raw') if isinstance(owner_field, dict) else None
        if (row.get('fieldStatus', {}).get('id') != 'available' or
                not isinstance(id_field, dict) or id_field.get('status') != 'available' or
                row.get('fieldMeta', {}).get('id', {}).get('truncated') is True or
                not _valid_id_scalar(component_id) or
                row.get('fieldStatus', {}).get('ownerID') != 'available' or
                not isinstance(owner_field, dict) or owner_field.get('status') != 'available' or
                row.get('fieldMeta', {}).get('ownerID', {}).get('truncated') is True or
                not _valid_id_scalar(component_owner)):
            incomplete = True
            continue
        if (_exact_scalar(component_id, parameter_name) and
                _exact_scalar(component_owner, owner_id)):
            matches.append(row)
    chosen = out['selectedParameter']
    if owner_collection_status != 'available' or route.get('status') not in ('available', 'partial'):
        chosen['reason'] = 'ownerUnknown' if owner_collection_status != 'available' else 'collectionUnknown'
    elif route.get('partial') or route.get('truncated'):
        chosen['reason'] = 'truncated' if route.get('truncated') else 'partial'
    elif incomplete:
        chosen['reason'] = 'incomplete'
    elif len(matches) > 1:
        chosen['reason'] = 'duplicate'
    elif len(matches) == 1:
        row = matches[0]
        chosen['fields'] = row.get('fields', {})
        fields = chosen['fields']
        required = ('ownerID', 'id', 'baseValue', 'currentValue')
        fields_ok = all(row.get('fieldStatus', {}).get(field) == 'available' and
                        isinstance(fields.get(field), dict) and
                        fields[field].get('status') == 'available'
                        for field in required)
        owner_field = fields.get('ownerID') if isinstance(fields, dict) else None
        owner_raw = owner_field.get('raw') if isinstance(owner_field, dict) else None
        if (not fields_ok or row.get('fieldMeta', {}).get('ownerID', {}).get('truncated') is True or
                not _valid_id_scalar(owner_raw)):
            chosen['reason'] = 'ownerFieldUnavailable'
            chosen['ownerMatchStatus'] = 'unknown'
        elif not _exact_scalar(owner_raw, owner.get('raw')):
            # Namespace equivalence is not established: record the strict
            # scalar discrepancy, but never normalize or choose another row.
            chosen['reason'] = 'ownerMismatchCandidate'
            chosen['ownerMatchStatus'] = 'nonExactScalarCandidate'
        else:
            chosen.update(status='available', reason=None,
                          ownerMatchStatus='exactScalarCandidate',
                          matchBasis='parameter.ownerIDAndIdExactCompositeCandidate')
    else:
        chosen['reason'] = 'noExactMatch'
    out['stages']['match'] = chosen['status']
    out['status'] = chosen['status']
    return out


def safe_torpedo_tooltip_parameter_probe(hub, components, selected_torpedo):
    try:
        return torpedo_tooltip_parameter_probe(hub, components, selected_torpedo)
    except Exception:
        return {'source': 'dataHub playerAvatar owner + parameter candidates',
                'status': 'unknown', 'semantics': 'unverified',
                'ownerEntityId': {'status': 'unknown'},
                'parameterCollection': {'status': 'unknown', 'rows': []},
                'selectedParameter': {'status': 'unknown', 'reason': 'probeFailed',
                                      'fields': {}},
                'stages': {'owner': 'unknown', 'parameterCollection': 'unknown',
                           'match': 'unknown'}, 'error': 'probeFailed'}


def _battle_timer_entity_candidates(hub, key_status, key):
    """Read the same singleton entity once for timer and sibling BattleInfo."""
    getter_status = _getter_status(hub, 'getSingleEntity')
    bases = {}
    for name, path in (('battleTimer.battleTime', 'battleTimer.battleTime'),
                       ('battleInfo.duration.battleTimerEntity', 'battleInfo.duration')):
        bases[name] = {'source': 'dataHub.getSingleEntity(CC.battleTimer).' + path,
                       'getterStatus': getter_status, 'keyStatus': key_status,
                       'callStatus': 'unknown', 'componentStatus': 'unknown',
                       'status': 'unknown', 'raw': None, 'type': None,
                       'semantics': 'unverified'}
    if getter_status != 'available':
        for item in bases.values():
            item['callStatus'] = item['status'] = 'unsupported'
        return bases
    if key_status != 'available':
        for item in bases.values():
            item['callStatus'] = item['status'] = key_status
        return bases
    call_status, entity = _call(hub, 'getSingleEntity', key)
    for item in bases.values():
        item['callStatus'] = call_status
    if call_status != 'available':
        for item in bases.values():
            item['status'] = call_status
        return bases
    for name, component_name, field in (
            ('battleTimer.battleTime', 'battleTimer', 'battleTime'),
            ('battleInfo.duration.battleTimerEntity', 'battleInfo', 'duration')):
        component_status, component = _probe_read(entity, component_name)
        item = bases[name]
        item['componentStatus'] = component_status
        if component_status != 'available':
            item['status'] = component_status
            continue
        field_status, value = _probe_read(component, field)
        item.update(_raw_candidate(item['source'], field_status, value))
    return bases


def game_clock_probe(hub, components):
    """Capture separately sourced fixed UI clock candidates; never merge paths."""
    result = {'source': 'dataHub UI game clock candidates',
              'status': 'unknown', 'semantics': 'unverified', 'candidates': {}}
    timer_key_status, timer_key = _probe_component_key(components, 'timer')
    for field in ('currentTime', 'currentServerTime'):
        result['candidates']['timer.' + field] = _singleton_candidate(
            hub, 'getSingleComponent', timer_key_status, timer_key, '', field)
    battle_key_status, battle_key = _probe_component_key(components, 'battleTimer')
    result['candidates'].update(_battle_timer_entity_candidates(
        hub, battle_key_status, battle_key))
    info_status, info_key = _probe_component_key(components, 'battleInfo')
    result['candidates']['battleInfo.duration'] = _singleton_candidate(
        hub, 'getSingleComponent', info_status, info_key, '', 'duration')
    # Explicit bounded named-collection routes are diagnostic only; they are
    # not fallback values and are never combined with singleton results.
    for name, fields in (('timer', ('currentTime', 'currentServerTime')),
                         ('battleTimer', ('battleTime',)),
                         ('battleInfo', ('duration',))):
        result['candidates'][name + '.collection'] = _bounded_context_collection(
            hub, components, name, fields)

    timer_collection = result['candidates']['timer.collection']
    battle_collection = result['candidates']['battleTimer.collection']
    info_collection = result['candidates']['battleInfo.collection']
    result['observations'] = {
        'timerCurrentTime': _single_collection_observation(
            timer_collection, 'currentTime',
            'dataHub.getEntityCollections("timer").currentTime',
            'single timer collection row; unit/meaning unverified'),
        'battleTimerBattleTime': _single_collection_observation(
            battle_collection, 'battleTime',
            'dataHub.getEntityCollections("battleTimer").battleTime',
            'single battleTimer collection row; unit/meaning unverified'),
        'battleInfoDuration': _single_collection_observation(
            info_collection, 'duration',
            'dataHub.getEntityCollections("battleInfo").duration',
            'single battleInfo collection row; unit/meaning unverified'),
        'inferredBattleRemaining': _collection_clock_observation(
            battle_collection, info_collection)}

    time_candidate = result['candidates']['battleTimer.battleTime']
    duration_candidate = result['candidates']['battleInfo.duration.battleTimerEntity']
    left_status, time_left = 'unknown', _MISSING
    if (time_candidate['status'] == 'available' and
            duration_candidate['status'] == 'available' and
            time_candidate.get('source', '').startswith('dataHub.getSingleEntity') and
            duration_candidate.get('source', '').startswith('dataHub.getSingleEntity') and
            _finite(time_candidate['raw']) and _finite(duration_candidate['raw'])):
        left_status = 'available'
        time_left = duration_candidate['raw'] * 60.0 - time_candidate['raw']
        if not _finite(time_left):
            left_status, time_left = 'unknown', _MISSING
    elif (time_candidate['status'] == 'unsupported' or
          duration_candidate['status'] == 'unsupported'):
        left_status = 'unsupported'
    time_left_candidate = _raw_candidate(
        'UI formula: battleInfo.duration * 60 - battleTimer.battleTime',
        left_status, time_left)
    time_left_candidate.update({
        'inferred': True,
        'formula': 'battleInfo.duration * 60 - battleTimer.battleTime',
        'formulaStatus': 'unverified',
        'sourceUnit': 'unverified',
    })
    result['candidates']['battleTimeLeft'] = time_left_candidate
    statuses = [item['status'] for item in result['candidates'].values()]
    result['status'] = ('available' if 'available' in statuses else
                        ('unsupported' if all(s == 'unsupported' for s in statuses)
                         else 'unknown'))
    return result


def safe_game_clock_probe(hub, components):
    try:
        return game_clock_probe(hub, components)
    except Exception:
        return {'source': 'dataHub UI game clock candidates', 'status': 'unknown',
                'semantics': 'unverified', 'candidates': {}, 'error': 'probeFailed'}


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
