# MIT License
# SPDX-License-Identifier: MIT
"""Bounded, read-only submarine and WaveHit dataHub candidates.

Names are UI/schema-derived candidates, not a Python API or semantic contract.
This module intentionally has no game imports and is safe to import offline.
"""

import math

try:
    STRING_TYPES = (basestring,)
    INTEGER_TYPES = (int, long)
    NUMBER_TYPES = (int, long, float)
except NameError:
    STRING_TYPES = (str,)
    INTEGER_TYPES = (int,)
    NUMBER_TYPES = (int, float)

SELF_LIMIT = 8
WAVE_HIT_LIMIT = 32
STRING_LIMIT = 128
_MISSING = object()

SUBMARINE_FIELDS = ('depth', 'depthIndex', 'showDepth', 'nearestDepthIndex')
BATTERY_FIELDS = ('value', 'burnedValue', 'maxCapacity', 'baseSpendRate',
                  'baseRegenRate', 'currentRate', 'burnRate', 'batteryState',
                  'isPotentiallyBurning')
WAVE_HIT_FIELDS = ('targetID', 'lifeTime', 'maxLifeTime', 'alertTime',
                   'hitCount', 'isActive', 'weaponType')
_BOOL_FIELDS = frozenset(('showDepth', 'isPotentiallyBurning', 'isActive'))

_DEPTH_INDEX = {0: 'SURFACE', 1: 'PERISCOPE', 2: 'WORKING',
                3: 'INVULNERABLE'}
_BATTERY_STATE = {0: 'IDLE', 1: 'CHARGING', 2: 'FROZEN',
                  3: 'SPENDING_NORMAL', 4: 'SPENDING_WARNING',
                  5: 'SPENDING_CRITICAL', 6: 'BURNING', 7: 'EMPTY'}
_UI_SOURCE = ('docs/RESEARCH_SUBMARINE_STATE_SEMANTICS.ja.md; '
              'extracted WoWS Components.xml/constants/battle.xml and '
              'unbound2/pc/battle UI references')
_SUBMARINE_SCOPE = ('B27 Undine TrainingBattle; 2,233 active state samples; '
                    'UI-context interpretation only, not a general server-state guarantee')
_WAVE_HIT_SCOPE = ('B27 recorded WaveHit row; 439 snapshots in the same '
                   'Undine TrainingBattle; UI-context interpretation only, '
                   'not a general server-state guarantee')


def _finite(value):
    try:
        return (isinstance(value, NUMBER_TYPES) and not isinstance(value, bool)
                and not math.isnan(value) and not math.isinf(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _safe_type(value):
    """Only emit primitive runtime type names, never inspect arbitrary objects."""
    name = type(value).__name__
    return name if name in ('bool', 'int', 'long', 'float', 'str', 'unicode',
                            'NoneType', 'list', 'tuple', 'dict') else 'object'


def _candidate(value, depth=0, budget=None):
    """Copy only bounded JSON primitives/containers; no repr/dir/object access."""
    if budget is None:
        budget = [32]
    if budget[0] <= 0 or depth > 2:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, STRING_TYPES):
        return value[:STRING_LIMIT]
    if isinstance(value, NUMBER_TYPES):
        return value if _finite(value) else None
    if isinstance(value, (list, tuple)):
        result = []
        for item in value[:8]:
            if budget[0] <= 0:
                break
            budget[0] -= 1
            result.append(_candidate(item, depth + 1, budget))
        return result
    if isinstance(value, dict):
        result = {}
        for key in list(value.keys())[:8]:
            if (budget[0] <= 0 or not isinstance(key, STRING_TYPES)
                    or key.startswith('_')):
                continue
            budget[0] -= 1
            result[key[:STRING_LIMIT]] = _candidate(value[key], depth + 1, budget)
        return result
    return None


def _read(obj, key):
    if obj is None:
        return 'unknown', None, 'componentMissing'
    try:
        if isinstance(obj, dict):
            if key not in obj:
                return 'unknown', None, 'attributeMissing'
            value = obj[key]
        else:
            value = getattr(obj, key, _MISSING)
            if value is _MISSING:
                return 'unknown', None, 'attributeMissing'
    except Exception:
        return 'unknown', None, 'attributeReadException'
    if value is None:
        return 'unknown', None, 'noneValue'
    return 'available', value, None


def _component_key(cc, name):
    if cc is None:
        return 'unsupported', None
    try:
        if isinstance(cc, dict):
            if name not in cc:
                return 'unsupported', None
            key = cc[name]
        else:
            key = getattr(cc, name, _MISSING)
            if key is _MISSING:
                return 'unsupported', None
    except Exception:
        return 'unknown', None
    return ('unsupported', None) if key is None else ('available', key)


def _getter_status(hub):
    if hub is None:
        return 'unsupported'
    try:
        getter = getattr(hub, 'getEntityCollections', _MISSING)
    except Exception:
        return 'unknown'
    return 'available' if callable(getter) else 'unsupported'


def _safe_exception_type(error):
    """Return a fixed allowlisted exception class label; never stringify it."""
    name = type(error).__name__
    allowed = ('AttributeError', 'IndexError', 'KeyError', 'NameError',
               'RuntimeError', 'StopIteration', 'TypeError', 'ValueError')
    return name if name in allowed else 'other'


def _collection(hub, name, limit, stop_on_second=False):
    result = {'source': 'dataHub.getEntityCollections(%r)' % name,
              'status': 'unknown', 'complete': False, 'count': None,
              'truncated': False, 'reason': None}
    getter_status = _getter_status(hub)
    result['getterStatus'] = getter_status
    if getter_status != 'available':
        result['status'] = getter_status
        result['reason'] = 'getterUnsupported' if getter_status == 'unsupported' else 'getterReadException'
        return result, []
    try:
        entities = hub.getEntityCollections(name)
    except Exception:
        result['reason'] = 'getterCallException'
        return result, []
    if entities is None:
        result['reason'] = 'collectionNone'
        return result, []
    found = []
    try:
        for _, entity in enumerate(entities):
            found.append(entity)
            if stop_on_second and len(found) == 2:
                result.update(status='unknown', complete=False, count=2,
                              reason='multiple')
                return result, found
            if len(found) > limit:
                result.update(status='unknown' if stop_on_second else 'available',
                              complete=False, count=len(found), truncated=True,
                               reason='truncated')
                return result, found[:limit]
    except Exception as error:
        result.update(status='unknown', complete=False, count=None,
                      reason='iterationException', failureStage='enumeration',
                      exceptionType=_safe_exception_type(error))
        return result, []
    result.update(status='available', complete=True, count=len(found))
    return result, found


def _field_value(value, field):
    if field in _BOOL_FIELDS:
        if type(value) is bool:
            return 'available', value, None
        return 'unknown', None, 'expectedBoolean'
    if _finite(value):
        return 'available', value, None
    return 'unknown', None, 'expectedFiniteNumber'


def _fields(component, names, source):
    values, statuses, reasons, types = {}, {}, {}, {}
    for name in names:
        read_status, value, reason = _read(component, name)
        raw_type = _safe_type(value) if read_status == 'available' else None
        if read_status == 'available':
            status, safe_value, validation_reason = _field_value(value, name)
            reason = validation_reason
        else:
            status, safe_value = read_status, None
        values[name] = safe_value
        statuses[name] = status
        reasons[name] = reason
        types[name] = raw_type
    return {'source': source, 'status': 'available', 'fields': values,
            'fieldStatus': statuses, 'fieldReason': reasons,
            'fieldType': types}


def _interpretation(component, field, source_detail, scope, mapper=None,
                    unit_hint=None, note=None):
    """Build separate UI-context metadata without changing a raw field."""
    raw = component['fields'].get(field)
    status = component['fieldStatus'].get(field, 'unknown')
    interpreted = None
    if status == 'available':
        if mapper is None:
            interpreted, status = raw, 'available'
        elif isinstance(raw, NUMBER_TYPES) and not isinstance(raw, bool) and _finite(raw):
            try:
                interpreted = mapper(raw)
            except (KeyError, TypeError, ValueError):
                interpreted = None
            status = 'available' if interpreted is not None else 'unknown'
        else:
            status = 'unknown'
    result = {'source': _UI_SOURCE + '; ' + source_detail,
              'status': status, 'raw': raw,
              'interpretation': interpreted, 'scope': scope}
    if unit_hint is not None:
        result['unitHint'] = unit_hint
    if note is not None:
        result['note'] = note
    return result


def _submarine_interpretations(component):
    return {
        'depth': _interpretation(
            component, 'depth', 'markers_elements.unbound:952-1002; '
            'telegraph.unbound:727-767,949-984', _SUBMARINE_SCOPE,
            unit_hint='m', note='UI display context only; raw is not rounded or converted.'),
        'depthIndex': _interpretation(
            component, 'depthIndex', 'constants/battle.xml:10-24; '
            'main_hud.unbound:67-70', _SUBMARINE_SCOPE,
            mapper=lambda value: _DEPTH_INDEX[value] if type(value) in INTEGER_TYPES else None,
            note='INVULNERABLE is the UI enum name, not a guarantee of physical invulnerability.'),
    }


def _battery_interpretations(component):
    return {
        'batteryState': _interpretation(
            component, 'batteryState', 'constants/battle.xml:574-588; '
            'submarine_battery.unbound:49-89,108-109,211-219',
            _SUBMARINE_SCOPE,
            mapper=lambda value: _BATTERY_STATE[value] if type(value) in INTEGER_TYPES else None,
            note='UI enum label only; no rate, percentage, or remaining-time derivation.'),
    }


def _wave_hit_interpretations(component):
    return {
        'lifeTime': _interpretation(
            component, 'lifeTime', 'markers/wave_hit_marker.unbound:8-18,24-51',
            _WAVE_HIT_SCOPE, unit_hint='s',
            note='Direct UI countdown input; maxLifeTime is not used or assigned a unit.'),
    }


def _empty_component(name, status, reason=None):
    names = SUBMARINE_FIELDS if name == 'submarine' else BATTERY_FIELDS
    return {'source': 'dataHub.selfVehicle.' + name, 'status': status,
            'reason': reason, 'fields': dict((key, None) for key in names),
            'fieldStatus': dict((key, status) for key in names),
            'fieldReason': dict((key, reason) for key in names),
            'fieldType': dict((key, None) for key in names)}


def self_submarine_probe(hub, cc, sample_ts=None):
    """Read selfVehicle only after a complete singleton collection observation."""
    collection, entities = _collection(hub, 'selfVehicle', SELF_LIMIT,
                                       stop_on_second=True)
    result = {'source': 'dataHub.selfVehicle', 'status': 'unknown',
              'semantics': 'unverified', 'sampleTs': _candidate(sample_ts),
              'collection': collection, 'entityIdCandidate': None,
              'components': {}}
    if collection['status'] != 'available' or not collection['complete']:
        result['status'] = collection['status']
        for name in ('submarine', 'battery'):
            result['components'][name] = _empty_component(name, 'unknown',
                                                          collection.get('reason'))
        return result
    if collection['count'] == 0:
        result['status'] = 'unknown'
        result['collection']['reason'] = 'empty'
        for name in ('submarine', 'battery'):
            result['components'][name] = _empty_component(name, 'unknown', 'selfVehicleMissing')
        return result

    entity = entities[0]
    id_status, entity_id, _ = _read(entity, 'id')
    if id_status == 'available':
        result['entityIdCandidate'] = _candidate(entity_id)
    component_statuses = []
    for name, fields in (('submarine', SUBMARINE_FIELDS),
                         ('battery', BATTERY_FIELDS)):
        key_status, key = _component_key(cc, name)
        if key_status != 'available':
            comp = _empty_component(name, key_status,
                                    'componentKeyUnsupported' if key_status == 'unsupported'
                                    else 'componentKeyReadException')
        else:
            try:
                value = entity[key]
            except (KeyError, IndexError, TypeError):
                comp = _empty_component(name, 'unknown', 'componentMissing')
            except Exception:
                comp = _empty_component(name, 'unknown', 'componentReadException')
            else:
                if value is None:
                    comp = _empty_component(name, 'unknown', 'componentMissing')
                else:
                    comp = _fields(value, fields, 'dataHub.selfVehicle.' + name)
        if comp['status'] == 'available':
            comp['interpretations'] = (_submarine_interpretations(comp)
                                       if name == 'submarine' else
                                       _battery_interpretations(comp))
        result['components'][name] = comp
        component_statuses.append(comp['status'])
    result['status'] = ('available' if 'available' in component_statuses else
                        ('unsupported' if all(s == 'unsupported' for s in component_statuses)
                         else 'unknown'))
    return result


def wave_hit_probe(hub, cc, sample_ts=None):
    """Read at most 32 CC.waveHit entities; preserve raw candidates, no joins."""
    collection, entities = _collection(hub, 'waveHit', WAVE_HIT_LIMIT)
    key_status, key = _component_key(cc, 'waveHit')
    result = {'source': 'dataHub.waveHit', 'status': collection['status'],
              'semantics': 'unverified', 'sampleTs': _candidate(sample_ts),
              'collection': collection, 'componentKeyStatus': key_status,
              'rows': [], 'truncated': collection['truncated'], 'partial': False}
    if collection['status'] != 'available':
        return result
    for entity in entities:
        id_status, entity_id, _ = _read(entity, 'id')
        row = {'entityIdCandidate': _candidate(entity_id) if id_status == 'available' else None,
               'componentStatus': key_status, 'fields': dict((f, None) for f in WAVE_HIT_FIELDS),
               'fieldStatus': dict((f, key_status) for f in WAVE_HIT_FIELDS),
               'fieldReason': dict((f, None) for f in WAVE_HIT_FIELDS),
               'fieldType': dict((f, None) for f in WAVE_HIT_FIELDS)}
        if key_status == 'available':
            try:
                component = entity[key]
            except (KeyError, IndexError, TypeError):
                component_status = 'unknown'
                reason = 'componentMissing'
            except Exception:
                component_status = 'unknown'
                reason = 'componentReadException'
            else:
                if component is None:
                    component_status, reason = 'unknown', 'componentMissing'
                else:
                    component_status, reason = 'available', None
                    data = _fields(component, WAVE_HIT_FIELDS, 'dataHub.waveHit')
                    row.update(fields=data['fields'], fieldStatus=data['fieldStatus'],
                               fieldReason=data['fieldReason'], fieldType=data['fieldType'])
                    row['interpretations'] = _wave_hit_interpretations(data)
            row['componentStatus'] = component_status
            if component_status != 'available':
                row['fieldStatus'] = dict((f, component_status) for f in WAVE_HIT_FIELDS)
                row['fieldReason'] = dict((f, reason) for f in WAVE_HIT_FIELDS)
        result['rows'].append(row)
    return result


def safe_submarine_probe(hub, cc, sample_ts=None):
    """Contain all probe failures so an integrating Main can keep its state."""
    try:
        submarine = self_submarine_probe(hub, cc, sample_ts)
    except Exception:
        submarine = {'source': 'dataHub.selfVehicle', 'status': 'unknown',
                     'semantics': 'unverified', 'sampleTs': _candidate(sample_ts),
                     'collection': {'source': "dataHub.getEntityCollections('selfVehicle')",
                                    'status': 'unknown', 'complete': False,
                                    'count': None, 'truncated': False,
                                    'reason': 'probeFailed'},
                     'entityIdCandidate': None, 'components': {}}
    try:
        wave_hit = wave_hit_probe(hub, cc, sample_ts)
    except Exception:
        wave_hit = {'source': 'dataHub.waveHit', 'status': 'unknown',
                    'semantics': 'unverified', 'sampleTs': _candidate(sample_ts),
                    'collection': {'source': "dataHub.getEntityCollections('waveHit')",
                                   'status': 'unknown', 'complete': False,
                                   'count': None, 'truncated': False,
                                   'reason': 'probeFailed'},
                    'componentKeyStatus': 'unknown', 'rows': [],
                    'truncated': False, 'partial': False}
    return {'selfSubmarineProbe': submarine, 'waveHitProbe': wave_hit}
