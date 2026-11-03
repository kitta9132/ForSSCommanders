# -*- coding: utf-8 -*-
# MIT License
"""Read live HP from the dataHub avatar `health` component.

TTaroTeamPanel / Autospy bind Unbound to the same component:

    healthComponent.value      current HP
    healthComponent.max        max HP
    healthComponent.isAlive

`battle.getAllShips().health` is empty on some client builds; this UI-layer
component is populated for the whole roster, spotted or not.

Kept free of game APIs so the join rules can be tested outside the sandbox
(Python 2 and 3).
"""


def _comp_get(obj, name):
    if obj is None:
        return None
    try:
        return getattr(obj, name)
    except Exception:
        pass
    try:
        return obj[name]
    except Exception:
        return None


def _entity_comp(entity, key):
    if entity is None or key is None:
        return None
    try:
        return entity[key]
    except Exception:
        return None


def _observation_exception_name(error):
    """Read only an exception class name; never format the exception object."""
    try:
        return error.__class__.__name__
    except Exception:
        return ""


def _entity_comp_observation(entity, key):
    """Read one component while retaining bounded availability metadata."""
    if entity is None or key is None:
        return None, "ccKeyMissing"
    try:
        component = entity[key]
    except Exception as error:
        status = ("componentMissing" if _observation_exception_name(error)
                  in ("KeyError", "IndexError") else "componentReadError")
        return None, status
    if component is None:
        return None, "componentMissing"
    return component, "available"


def _field_observation(obj, name):
    """Read a component field once per access path with safe failure labels."""
    if obj is None:
        return None, "componentMissing"
    try:
        value = getattr(obj, name)
    except Exception as attribute_error:
        try:
            value = obj[name]
        except Exception as item_error:
            attribute_name = _observation_exception_name(attribute_error)
            item_name = _observation_exception_name(item_error)
            # _comp_get tries item access after any attribute failure. Keep that
            # fallback, but only label normal absence as missing; a failed
            # property getter or unexpected item error remains a readError.
            normal_attribute_miss = attribute_name == "AttributeError"
            normal_item_miss = item_name in (
                "KeyError", "IndexError", "TypeError", "AttributeError")
            return None, ("missing" if normal_attribute_miss and normal_item_miss
                          else "readError")
    if value is None:
        return None, "none"
    return value, "available"


def _is_alive_flag(value):
    if value is False or value == 0:
        return False
    if value is True or value == 1:
        return True
    return None


def _as_number(value):
    if value is None or value is False:
        return None
    if value is True:
        return None
    try:
        return float(value)
    except Exception:
        return None


def normalize_ui_health(value, maximum, is_alive):
    """Return {health, maxHealth} or None.

    Unbound treats value==0 while still alive as "bar not yet ticked" and
    draws a full bar. Copying raw 0 would mark the ship dead in the collector.
    That sentinel is marked ``untickedFull`` so unspotted (灭点) rows can
    refuse it: a dark bar sitting at 0 is not full HP.
    """
    alive = _is_alive_flag(is_alive)
    max_hp = _as_number(maximum)
    cur = _as_number(value)
    if alive is False:
        return {"health": 0, "maxHealth": max_hp, "alive": False}
    if max_hp is None and cur is None:
        return None
    if alive is True and (cur is None or cur <= 0):
        if max_hp is None or max_hp <= 0:
            return None
        return {"health": max_hp, "maxHealth": max_hp, "untickedFull": True}
    if cur is None:
        return None if max_hp is None else {"health": None, "maxHealth": max_hp}
    rec = {"health": cur}
    rec["maxHealth"] = max_hp
    return rec


def _alias_ids(avatar, vehicle):
    ids = []
    for src, name in ((avatar, "playerId"), (avatar, "id"), (vehicle, "id")):
        value = _comp_get(src, name)
        if value is None or value in ids:
            continue
        ids.append(value)
    return ids


def index_avatar_health(entities, cc):
    """Map every avatar/vehicle id on an entity to its UI health record."""
    index = {}
    if not entities or cc is None:
        return index
    health_key = _comp_get(cc, "health")
    avatar_key = _comp_get(cc, "avatar")
    vehicle_key = _comp_get(cc, "vehicle")
    for entity in entities:
        health = _entity_comp(entity, health_key)
        rec = normalize_ui_health(
            _comp_get(health, "value"),
            _comp_get(health, "max"),
            _comp_get(health, "isAlive"),
        )
        if rec is None:
            continue
        avatar = _entity_comp(entity, avatar_key)
        vehicle = _entity_comp(entity, vehicle_key)
        for alias in _alias_ids(avatar, vehicle):
            index[alias] = rec
    return index


def _plain_fields(obj, names):
    """Copy selected component properties into a plain dict.

    Missing/None/raising properties are omitted, which is the same value the
    legacy per-consumer readers observe. 0 and False are real values here and
    must survive (playerId/teamId can legitimately be 0 in these APIs).
    """
    if obj is None:
        return None
    out = {}
    for name in names:
        value = _comp_get(obj, name)
        if value is not None:
            out[name] = value
    return out


def sample_avatar_ids(entity, cc):
    """Read the avatar/vehicle ids needed by roster, health and map joins once."""
    avatar_key = _comp_get(cc, "avatar")
    vehicle_key = _comp_get(cc, "vehicle")
    return {
        "avatar": _plain_fields(
            _entity_comp(entity, avatar_key),
            ("playerId", "id", "teamId", "shipId")),
        "vehicle": _plain_fields(_entity_comp(entity, vehicle_key), ("id",)),
    }


def _sample_avatar_health(entity, cc):
    """Read raw health once and return values plus observation metadata."""
    health_key = _comp_get(cc, "health")
    health, component_status = _entity_comp_observation(entity, health_key)
    fields = {}
    statuses = {}
    for name in ("value", "max", "isAlive"):
        value, status = _field_observation(health, name)
        fields[name] = value
        statuses[name] = status
    return ({"value": fields["value"], "max": fields["max"],
             "isAlive": fields["isAlive"]},
            {"componentStatus": component_status, "fieldStatus": statuses})


def sample_avatar_health(entity, cc):
    """Read the raw UI health fields once; normalize/index later."""
    return _sample_avatar_health(entity, cc)[0]


def index_avatar_health_sample(rows):
    """Build the same health index from pre-read sample rows.

    Kept separate from ``index_avatar_health`` so the standalone entity reader
    stays byte-for-byte compatible, while the shared path uses the same
    normalize and alias helpers.
    """
    index = {}
    for row in rows or ():
        health = row.get("health") or {}
        rec = normalize_ui_health(
            health.get("value"), health.get("max"), health.get("isAlive"))
        if rec is None:
            continue
        for alias in _alias_ids(row.get("avatar"), row.get("vehicle")):
            index[alias] = rec
    return index


class AvatarRows(list):
    """One captured avatar list plus its state-local plain-data sample.

    The sample is built once by the first core consumer (roster, health or map
    positions) and lives only on this captured list. It is never stored on the
    Collector, so a later frame cannot reuse stale ids/health. ``complete`` is
    False for partial/truncated captures, where absence of a health row must
    not become an alive/dead assertion even if the health reader is called
    directly.
    """

    def __init__(self, rows=(), complete=True):
        list.__init__(self, rows)
        self._sample = None
        self.complete = complete

    def sample_ids(self, cc):
        sample = self._sample
        if sample is None:
            rows = []
            for entity in self:
                rows.append(sample_avatar_ids(entity, cc))
            sample = {"rows": rows}
            self._sample = sample
        return sample

    def sample_health(self, cc):
        # Partial captures still expose raw health for entities actually seen.
        # They never create a health index: absence from an incomplete capture
        # remains unknown rather than alive/dead.
        sample = self.sample_ids(cc)
        rows = sample["rows"]
        for index, entity in enumerate(self):
            row = rows[index]
            if "health" not in row:
                row["health"], row["healthObservation"] = _sample_avatar_health(
                    entity, cc)
        return rows if self.complete else []


def apply_ui_health(entry, index, for_unspotted=False):
    """Fill missing health / maxHealth on a ship or self dict. Returns entry.

    ``for_unspotted``: last-seen / 灭点 rows. Do not copy the Unbound
    "value==0 means full bar" sentinel, and let UI ``isAlive=False``
    overwrite a ghost that was still flagged alive.
    """
    if not isinstance(entry, dict) or not index:
        return entry
    rec = None
    for key in ("playerId", "vehicleId", "uiId"):
        alias = entry.get(key)
        if alias is None:
            continue
        rec = index.get(alias)
        if rec is not None:
            break
    if rec is None:
        return entry
    if rec.get("alive") is False:
        entry["alive"] = False
    copy_health = rec.get("health") is not None
    if for_unspotted and rec.get("untickedFull"):
        copy_health = False
    if entry.get("health") is None and copy_health:
        entry["health"] = rec["health"]
    if entry.get("maxHealth") is None and rec.get("maxHealth") is not None:
        entry["maxHealth"] = rec["maxHealth"]
    return entry
