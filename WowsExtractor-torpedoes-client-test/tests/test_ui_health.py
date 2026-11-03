# MIT License -- dataHub avatar health component (TTaroTeamPanel source).
import os
import sys

MOD_DIR = os.path.join(
    os.path.dirname(__file__), "..", "res_mods", "PnFMods", "WowsExtractor")
sys.path.insert(0, MOD_DIR)

import ui_health as H  # noqa: E402


class _CC(object):
    health = "health"
    avatar = "avatar"
    vehicle = "vehicle"


class _Comp(object):
    def __init__(self, **fields):
        self.__dict__.update(fields)


class _Entity(object):
    def __init__(self, components):
        self._components = components

    def __getitem__(self, key):
        return self._components[key]


def _avatar_entity(health, avatar, vehicle=None):
    components = {"health": health, "avatar": avatar}
    if vehicle is not None:
        components["vehicle"] = vehicle
    return _Entity(components)


def test_indexes_health_value_and_max_by_player_id():
    entities = [_avatar_entity(
        _Comp(value=50000, max=80000, isAlive=True),
        _Comp(playerId=805828113, id=268369920),
    )]
    index = H.index_avatar_health(entities, _CC)
    rec = index[805828113]
    assert rec["health"] == 50000
    assert rec["maxHealth"] == 80000


def test_indexes_the_same_row_under_avatar_id_and_vehicle_id():
    entities = [_avatar_entity(
        _Comp(value=50000, max=80000, isAlive=True),
        _Comp(playerId=805828113, id=268369920),
        _Comp(id=268369921),
    )]
    index = H.index_avatar_health(entities, _CC)
    assert index[805828113] is index[268369920]
    assert index[268369921] is index[268369920]


def test_alive_zero_value_is_treated_as_full_hp():
    # TTaro/Autospy: value==0 while isAlive means the bar has not received
    # its first tick yet, not that the ship is dead.
    rec = H.normalize_ui_health(0, 80000, True)
    assert rec == {"health": 80000, "maxHealth": 80000, "untickedFull": True}


def test_dead_ship_emits_zero_health_and_keeps_max():
    rec = H.normalize_ui_health(0, 80000, False)
    assert rec == {"health": 0, "maxHealth": 80000, "alive": False}


def test_apply_fills_missing_health_from_ui_index():
    entry = {"playerId": 805828113, "vehicleId": 268369920}
    index = {
        268369920: {"health": 50000, "maxHealth": 80000},
    }
    H.apply_ui_health(entry, index)
    assert entry["health"] == 50000
    assert entry["maxHealth"] == 80000


def test_apply_does_not_overwrite_battle_ship_health():
    entry = {
        "playerId": 1,
        "health": 77850,
        "maxHealth": None,
    }
    index = {1: {"health": 72000, "maxHealth": 97700}}
    H.apply_ui_health(entry, index)
    assert entry["health"] == 77850
    assert entry["maxHealth"] == 97700


def test_apply_matches_vehicle_id_when_player_id_namespaces_differ():
    # Live capture: objects.playerId was the vehicle-like id; roster used
    # avatar.playerId. UI health is on the avatar entity under both ids.
    entry = {"playerId": 268369920}
    index = {
        805828113: {"health": 1000, "maxHealth": 2000},
        268369920: {"health": 1000, "maxHealth": 2000},
    }
    H.apply_ui_health(entry, index)
    assert entry["health"] == 1000
    assert entry["maxHealth"] == 2000


def test_dead_flag_without_hp_numbers_is_still_dead():
    rec = H.normalize_ui_health(None, None, False)
    assert rec["health"] == 0
    assert rec["alive"] is False


def test_indexes_dead_flag_even_without_hp_numbers():
    entities = [_avatar_entity(
        _Comp(value=None, max=None, isAlive=False),
        _Comp(playerId=901),
    )]
    index = H.index_avatar_health(entities, _CC)
    assert index[901]["health"] == 0
    assert index[901]["alive"] is False


def test_unspotted_does_not_copy_an_unticked_full_bar():
    """灭点 bars often sit at value=0/isAlive=True. That Unbound sentinel
    means 'not ticked yet' on a spotted ship, not 'full HP in the dark'."""
    entry = {"playerId": 1, "alive": True}
    index = {1: H.normalize_ui_health(0, 80000, True)}
    H.apply_ui_health(entry, index, for_unspotted=True)
    assert entry.get("health") is None
    assert entry["maxHealth"] == 80000
    assert entry["alive"] is True


def test_unspotted_copies_ui_death_onto_an_alive_ghost():
    entry = {"playerId": 1, "alive": True}
    index = {1: H.normalize_ui_health(0, 80000, False)}
    H.apply_ui_health(entry, index, for_unspotted=True)
    assert entry["health"] == 0
    assert entry["alive"] is False


def test_spotted_still_gets_the_unticked_full_bar():
    entry = {"playerId": 1}
    index = {1: H.normalize_ui_health(0, 80000, True)}
    H.apply_ui_health(entry, index)
    assert entry["health"] == 80000
    assert entry["maxHealth"] == 80000


def test_sample_health_index_matches_standalone_reader():
    entities = [
        _avatar_entity(
            _Comp(value=0, max=80000, isAlive=True),
            _Comp(playerId=1, id=11, teamId=1),
            _Comp(id=111)),
        _avatar_entity(
            _Comp(value=0, max=80000, isAlive=False),
            _Comp(playerId=2, id=12, teamId=0)),
        _avatar_entity(
            _Comp(value=None, max=None, isAlive=True),
            _Comp(playerId=3, id=13)),
    ]
    standalone = H.index_avatar_health(entities, _CC)
    rows = H.AvatarRows(entities)
    shared = H.index_avatar_health_sample(rows.sample_health(_CC))
    assert shared == standalone
    assert shared[1] == {"health": 80000, "maxHealth": 80000,
                         "untickedFull": True}
    assert shared[2]["health"] == 0 and shared[2]["alive"] is False
    assert 3 not in shared  # None/max None is not a health record


def test_sample_ids_keep_zero_ids_and_avatar_ship_id_fallback():
    zero = _avatar_entity(
        _Comp(value=1, max=2, isAlive=True),
        _Comp(playerId=0, id=0, teamId=0, shipId=0),
        _Comp(id=0))
    rows = H.AvatarRows([zero])
    sample = rows.sample_ids(_CC)
    assert sample["rows"][0]["avatar"] == {
        "playerId": 0, "id": 0, "teamId": 0, "shipId": 0}
    assert sample["rows"][0]["vehicle"] == {"id": 0}

    fallback = _avatar_entity(
        _Comp(value=1, max=2, isAlive=True),
        _Comp(playerId=7, id=17, teamId=1, shipId=77),
        _Comp())
    row = H.AvatarRows([fallback]).sample_ids(_CC)["rows"][0]
    assert row["vehicle"] == {}
    assert row["avatar"]["shipId"] == 77


def test_avatar_rows_are_per_capture_and_cache_only_within_the_holder():
    first = H.AvatarRows([_avatar_entity(
        _Comp(value=10, max=20, isAlive=True), _Comp(playerId=1))])
    assert first.sample_health(_CC)[0]["health"]["value"] == 10
    assert first.sample_ids(_CC) is first.sample_ids(_CC)

    second = H.AvatarRows([_avatar_entity(
        _Comp(value=99, max=100, isAlive=True), _Comp(playerId=2))])
    row = second.sample_health(_CC)[0]
    assert row["avatar"]["playerId"] == 2
    assert row["health"]["value"] == 99


def test_incomplete_avatar_rows_refuse_health_even_when_called_directly():
    holder = H.AvatarRows([_avatar_entity(
        _Comp(value=10, max=20, isAlive=True), _Comp(playerId=1))],
        complete=False)
    assert holder.sample_ids(_CC)["rows"][0]["avatar"]["playerId"] == 1
    assert holder.sample_health(_CC) == []
    assert H.index_avatar_health_sample(holder.sample_health(_CC)) == {}


def test_sample_handles_missing_components_and_raising_entity():
    class Broken(object):
        def __getitem__(self, key):
            raise RuntimeError("component unavailable")

    rows = H.AvatarRows([Broken(), _avatar_entity(
        _Comp(value=5, max=10, isAlive=True), _Comp(playerId=3))])
    sample = rows.sample_health(_CC)
    assert sample[0]["avatar"] is None and sample[0]["vehicle"] is None
    assert sample[0]["health"] == {
        "value": None, "max": None, "isAlive": None}
    index = H.index_avatar_health_sample(sample)
    assert index[3]["health"] == 5
    assert H.index_avatar_health_sample([]) == {}


def test_sample_ids_without_cc_never_index_unknown_aliases():
    row = H.sample_avatar_ids(_avatar_entity(
        _Comp(value=5, max=10, isAlive=True), _Comp(playerId=3)), None)
    assert row == {"avatar": None, "vehicle": None}
    assert H.index_avatar_health_sample([dict(row, health={
        "value": 5, "max": 10, "isAlive": True})]) == {}
