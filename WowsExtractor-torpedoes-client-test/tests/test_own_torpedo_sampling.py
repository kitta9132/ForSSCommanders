"""Own-torpedo distance exception: strict owner bool only, with bounded calls."""
from collections import Counter
import json
import os
import sys
from types import SimpleNamespace as Obj

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))
from torpedo_telemetry import (TorpedoMotion, TorpedoSamplingGroups,
                               TorpedoTelemetry, sampling_wire_payload)


class CountedTorpedo(object):
    def __init__(self, uiId=1, ownerId=7000, ownerTeamId=1,
                 ownerType='Ship', shotId=1, type='normal',
                 position=(0.0, 0.0, 0.0)):
        object.__setattr__(self, '_values', {
            'uiId': uiId, 'ownerId': ownerId, 'ownerTeamId': ownerTeamId,
            'ownerType': ownerType, 'shotId': shotId, 'type': type,
            'position': position})
        object.__setattr__(self, 'reads', Counter())

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        reads = object.__getattribute__(self, 'reads')
        if name in values:
            reads[name] += 1
            return values[name]
        raise AttributeError(name)

    def set_position(self, value):
        self._values['position'] = value


class CountedOwner(object):
    def __init__(self, team_id, is_player, reads):
        object.__setattr__(self, '_values', {
            'teamId': team_id, 'isObserver': False, 'isAlive': True,
            'isBot': not (is_player is True), 'uiId': 1,
            'isPlayer': is_player, 'subtype': 'Ship',
            'name': 'owner', 'playerName': 'player'})
        object.__setattr__(self, '_reads', reads)

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        reads = object.__getattribute__(self, '_reads')
        if name in values:
            reads[name] += 1
            return values[name]
        raise AttributeError(name)


class Battle(object):
    def __init__(self, rows, owner_values=None, owner_errors=None):
        self.rows = rows
        self.owner_values = dict(owner_values or {})
        self.owner_errors = set(owner_errors or ())
        self.collection_calls = 0
        self.owner_calls = Counter()
        self.owner_reads = Counter()

    def getAllTorpedoes(self):
        self.collection_calls += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.owner_calls[owner_id] += 1
        if owner_id in self.owner_errors:
            raise RuntimeError('owner unavailable')
        return CountedOwner(0, self.owner_values.get(owner_id, False),
                            self.owner_reads)


def context(self_position=(0.0, 0.0, 0.0), width=3000, height=3000):
    return {'selfPosition': list(self_position), 'mapWidth': width,
            'mapHeight': height, 'source': 'calibratedMapExtents',
            'inferred': True}


def adapter(rows, owner_values=None, owner_errors=None):
    battle = Battle(rows, owner_values, owner_errors)
    return TorpedoTelemetry(battle, Obj()), battle


def call_torpedoes(telemetry, team, sampler, now, ctx, self_ship_id=None):
    """Pass self_ship_id through the new API without changing call sites."""
    return telemetry.torpedoes(team, sampler, now, ctx,
                               self_ship_id=self_ship_id)


def set_owner(battle, owner_id, value):
    battle.owner_values[owner_id] = value


def sampled_owner_ids(rows):
    return set(row['ownerId'] for row in rows
               if row.get('ownerId') is not None and
               not isinstance(row.get('ownerId'), bool))


def test_far_own_strict_true_keeps_high_deadline_not_core_tick_ten_hz():
    own = CountedTorpedo(uiId=1, ownerId=9100, shotId=1,
                         position=(0, 0, 2000.0))
    telemetry, battle = adapter([own], {9100: True})
    sampler = TorpedoSamplingGroups()
    motion = TorpedoMotion()
    ctx = context()
    samples = []
    last_owner_calls = 0
    last_position_reads = 0

    for step in range(0, 101):
        now = round(step / 10.0, 1)
        rows, status = call_torpedoes(telemetry, 0, sampler, now, ctx,
                                      self_ship_id=9100)
        for row in rows:
            # Main applies its calibrated conversion to every sampled row.
            row['mapPosition'] = [row['position'][0] / 100.0,
                                  row['position'][2] / 100.0]
        motion.update(rows, now, status['available'],
                      membership=status['membership'])
        owner_calls = sum(battle.owner_calls.values())
        if rows:
            assert len(rows) == 1
            assert rows[0]['isOwn'] is True
            assert rows[0]['sampling']['group'] == 'high'
            assert rows[0]['sampling']['intervalSeconds'] == 0.2
            assert rows[0]['position'] == [0.0, 0.0, 2000.0]
            assert rows[0]['mapPosition'] == [0.0, 20.0]
            samples.append(now)
            if step:
                assert rows[0]['motion']['available'] is True
                assert rows[0]['motion']['dt'] == pytest.approx(0.2)
        else:
            # A 0.1 s core tick is not an extra own sample and reads no owner
            # or position while the 0.2 s high deadline is not due.
            assert step % 2 == 1
            assert owner_calls == last_owner_calls
            assert own.reads['position'] == last_position_reads
        assert status['sampling']['high']['memberCount'] == 1
        assert status['sampling']['low']['memberCount'] == 0
        last_owner_calls = owner_calls
        last_position_reads = own.reads['position']

    assert samples == [round(step / 10.0, 1) for step in range(0, 101, 2)]
    assert own.reads['position'] == 51
    assert battle.owner_calls[9100] == 51  # one per actual sample, not per core tick
    assert battle.owner_reads['isPlayer'] == 51
    assert battle.collection_calls == 101
    json.dumps({'samples': samples}, allow_nan=False)


def test_far_non_own_values_stay_low_and_non_due_reads_no_position_or_owner():
    rows = [
        CountedTorpedo(uiId=1, ownerId=9201, shotId=1,
                       position=(0, 0, 2000.0)),  # strict False
        CountedTorpedo(uiId=2, ownerId=9202, shotId=2,
                       position=(0, 0, 2000.0)),  # None
        CountedTorpedo(uiId=3, ownerId=9203, shotId=3,
                       position=(0, 0, 2000.0)),  # int 1
        CountedTorpedo(uiId=4, ownerId=9204, shotId=4,
                       position=(0, 0, 2000.0)),  # str 'True'
        CountedTorpedo(uiId=5, ownerId=9205, shotId=5,
                       position=(0, 0, 2000.0)),  # int 0
    ]
    telemetry, battle = adapter(rows, {9201: False, 9202: None, 9203: 1,
                                       9204: 'True', 9205: 0})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    call_torpedoes(telemetry, 0, sampler, 0.0, ctx,
                   self_ship_id=9200)

    out, status = call_torpedoes(telemetry, 0, sampler, 5.0, ctx,
                                self_ship_id=9200)
    groups = dict((row['uiId'], row) for row in out)
    assert [groups[index]['sampling']['group'] for index in range(1, 6)] == [
        'low'] * 5
    assert groups[1]['isOwn'] is False
    # With a strict self ship ID, any valid scalar ownerId that does not match
    # the self ID is classified as non-own; only an invalid/unavailable ownerId
    # stays unknown.
    assert groups[2]['isOwn'] is False
    assert all(groups[index]['isOwn'] is False for index in range(3, 6))
    assert status['sampling']['classification']['farCount'] == 5

    before_owner = sum(battle.owner_calls.values())
    before_position = [row.reads['position'] for row in rows]
    out, status = call_torpedoes(telemetry, 0, sampler, 5.2, ctx,
                                 self_ship_id=9200)
    assert out == []
    assert sum(battle.owner_calls.values()) == before_owner
    assert [row.reads['position'] for row in rows] == before_position
    assert status['sampling']['low']['status'] == 'notSampled'

    out, status = call_torpedoes(telemetry, 0, sampler, 5.6, ctx,
                                 self_ship_id=9200)
    assert len(out) == 5
    assert all(row['sampling']['group'] == 'low' for row in out)
    assert status['sampling']['low']['status'] == 'sampled'
    for owner_id in range(9201, 9206):
        assert battle.owner_calls[owner_id] == 3  # 0.0, 5.0, 5.6
    assert battle.owner_reads['isPlayer'] == 15


def test_own_true_survives_new_and_near_to_far_classifications():
    own = CountedTorpedo(uiId=1, ownerId=9300, shotId=1,
                         position=(0, 0, 2000.0))
    telemetry, battle = adapter([own], {9300: True})
    sampler = TorpedoSamplingGroups()
    ctx = context()

    first, status = call_torpedoes(telemetry, 0, sampler, 0.0, ctx,
                                   self_ship_id=9300)
    assert first[0]['sampling']['group'] == 'high'
    assert first[0]['sampling']['provisional'] is True
    assert first[0]['isOwn'] is True

    own.set_position((0, 0, 500.0))
    near, status = call_torpedoes(telemetry, 0, sampler, 5.0, ctx,
                                  self_ship_id=9300)
    assert near[0]['sampling']['group'] == 'high'
    assert near[0]['sampling']['distanceStatus'] == 'near'
    assert status['sampling']['classification']['nearCount'] == 1
    assert near[0]['isOwn'] is True

    own.set_position((0, 0, 2000.0))
    far, status = call_torpedoes(telemetry, 0, sampler, 10.0, ctx,
                                 self_ship_id=9300)
    assert far[0]['sampling']['group'] == 'high'
    assert far[0]['sampling']['distanceStatus'] == 'far'
    assert far[0]['isOwn'] is True
    assert status['sampling']['classification']['farCount'] == 1

    # A new own identity between classifications starts provisional high and
    # remains high at the next classification despite being far away.
    new_own = CountedTorpedo(uiId=2, ownerId=9300, shotId=2,
                             position=(0, 0, 2500.0))
    telemetry.battle.rows = [own, new_own]
    out, _ = call_torpedoes(telemetry, 0, sampler, 10.2, ctx,
                            self_ship_id=9300)
    groups = dict((row['uiId'], row) for row in out)
    assert groups[2]['sampling']['group'] == 'high'
    assert groups[2]['sampling']['reason'] == 'new'
    assert groups[2]['isOwn'] is True

    out, status = call_torpedoes(telemetry, 0, sampler, 15.0, ctx,
                                 self_ship_id=9300)
    groups = dict((row['uiId'], row) for row in out)
    assert groups[1]['sampling']['group'] == 'high'
    assert groups[2]['sampling']['group'] == 'high'
    assert groups[2]['sampling']['provisional'] is False
    assert groups[2]['sampling']['distanceStatus'] == 'far'
    assert status['sampling']['classification']['farCount'] == 2


def test_own_strict_true_stays_high_inside_the_l5_to_l3_band():
    own = CountedTorpedo(uiId=1, ownerId=9350, shotId=1,
                         position=(0, 0, 700.0))
    other = CountedTorpedo(uiId=2, ownerId=9351, shotId=2,
                           position=(0, 0, 700.0))
    telemetry, battle = adapter([own, other], {9350: True, 9351: False})
    sampler = TorpedoSamplingGroups()
    ctx = context()  # L/5 = 600, L/3 = 1000
    call_torpedoes(telemetry, 0, sampler, 0.0, ctx, self_ship_id=9350)
    out, status = call_torpedoes(telemetry, 0, sampler, 5.0, ctx,
                                self_ship_id=9350)
    groups = dict((row['uiId'], row['sampling']) for row in out)
    assert groups[1]['group'] == 'high'
    assert groups[1]['distanceStatus'] == 'far'
    assert groups[1]['intervalSeconds'] == 0.2
    assert groups[2]['group'] == 'low'
    assert status['sampling']['classification']['farCount'] == 2

    out, _ = call_torpedoes(telemetry, 0, sampler, 5.2, ctx,
                            self_ship_id=9350)
    assert [row['uiId'] for row in out] == [1]
    assert battle.owner_calls[9350] == 3
    assert battle.owner_calls[9351] == 2


def test_only_strict_bool_true_is_own_and_unknown_never_becomes_false():
    rows = [
        CountedTorpedo(uiId=1, ownerId=9401, shotId=1,
                       position=(0, 0, 2000.0)),  # True
        CountedTorpedo(uiId=2, ownerId=9402, shotId=2,
                       position=(0, 0, 2000.0)),  # False
        CountedTorpedo(uiId=3, ownerId=9403, shotId=3,
                       position=(0, 0, 2000.0)),  # int 1
        CountedTorpedo(uiId=4, ownerId=9404, shotId=4,
                       position=(0, 0, 2000.0)),  # str 'True'
        CountedTorpedo(uiId=5, ownerId=9405, shotId=5,
                       position=(0, 0, 2000.0)),  # None
        CountedTorpedo(uiId=6, ownerId=9406, shotId=6,
                       position=(0, 0, 2000.0)),  # exception
        CountedTorpedo(uiId=7, ownerId=9407, shotId=7,
                       position=(0, 0, 2000.0)),  # int 0
    ]
    telemetry, battle = adapter(
        rows, {9401: True, 9402: False, 9403: 1, 9404: 'True',
               9405: None, 9407: 0}, owner_errors={9406})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    call_torpedoes(telemetry, 0, sampler, 0.0, ctx,
                   self_ship_id=9401)

    out, status = call_torpedoes(telemetry, 0, sampler, 5.0, ctx,
                                self_ship_id=9401)
    groups = dict((row['uiId'], row) for row in out)
    assert groups[1]['sampling']['group'] == 'high'
    assert groups[1]['isOwn'] is True
    for index in range(2, 8):
        assert groups[index]['sampling']['group'] == 'low'
        assert groups[index]['isOwn'] is not True
    assert groups[2]['isOwn'] is False
    # Every non-own row has a valid scalar ownerId that is not equal to the
    # self ship ID, so all resolve to False rather than unknown.
    assert all(groups[index]['isOwn'] is False for index in range(3, 8))
    assert status['sampling']['classification']['farCount'] == 7
    assert battle.owner_calls[9406] == 2  # failed lookups are not cached across ticks


def test_owner_exception_then_current_true_promotes_low_due_row_without_contradiction():
    far = CountedTorpedo(uiId=1, ownerId=9500, shotId=1,
                         position=(0, 0, 2000.0))
    telemetry, battle = adapter([far], {9500: False})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    call_torpedoes(telemetry, 0, sampler, 0.0, ctx)

    battle.owner_errors = {9500}
    out, status = call_torpedoes(telemetry, 0, sampler, 5.0, ctx)
    assert out[0]['isOwn'] is None
    assert out[0]['sampling']['group'] == 'low'
    assert status['sampling']['classification']['farCount'] == 1

    # Low is not due at 5.2, so no owner read can expose a contradiction here.
    out, _ = call_torpedoes(telemetry, 0, sampler, 5.2, ctx)
    assert out == []
    assert battle.owner_calls[9500] == 2

    battle.owner_errors = set()
    set_owner(battle, 9500, True)
    out, status = call_torpedoes(telemetry, 0, sampler, 5.6, ctx,
                                self_ship_id=9500)
    assert out[0]['isOwn'] is True
    assert out[0]['sampling']['group'] == 'high'
    assert out[0]['sampling']['reason'] == 'highDue'
    assert status['sampling']['high']['sampledCount'] == 1
    assert status['sampling']['low']['sampledCount'] == 0
    assert status['membership'][0]['group'] == 'high'

    out, _ = call_torpedoes(telemetry, 0, sampler, 5.7, ctx,
                            self_ship_id=9500)
    assert out == []  # promotion must not retain the old low deadline phase
    out, _ = call_torpedoes(telemetry, 0, sampler, 5.8, ctx,
                            self_ship_id=9500)
    assert out[0]['isOwn'] is True
    assert out[0]['sampling']['group'] == 'high'
    out, status = call_torpedoes(telemetry, 0, sampler, 10.0, ctx,
                                 self_ship_id=9500)
    assert out[0]['isOwn'] is True
    assert out[0]['sampling']['group'] == 'high'
    assert status['sampling']['classification']['farCount'] == 1


def test_clear_and_clock_reset_do_not_carry_own_group_history():
    own = CountedTorpedo(uiId=1, ownerId=9600, shotId=1,
                         position=(0, 0, 2000.0))
    telemetry, battle = adapter([own], {9600: True})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    call_torpedoes(telemetry, 0, sampler, 0.0, ctx, self_ship_id=9600)
    out, _ = call_torpedoes(telemetry, 0, sampler, 5.0, ctx,
                            self_ship_id=9600)
    assert out[0]['sampling']['group'] == 'high'

    sampler.clear()
    set_owner(battle, 9600, False)
    out, status = call_torpedoes(telemetry, 0, sampler, 5.1, ctx,
                                self_ship_id=9601)
    # Cleared then reclassified: an enemy far row is low, not the old own high.
    assert out[0]['sampling']['group'] == 'low'
    assert out[0]['sampling']['provisional'] is True
    assert out[0]['isOwn'] is False
    out, status = call_torpedoes(telemetry, 0, sampler, 10.1, ctx,
                                 self_ship_id=9601)
    assert out[0]['sampling']['group'] == 'low'
    assert out[0]['isOwn'] is False

    set_owner(battle, 9600, True)
    out, _ = call_torpedoes(telemetry, 0, sampler, 10.6, ctx,
                            self_ship_id=9600)
    assert out[0]['sampling']['group'] == 'high'
    assert out[0]['isOwn'] is True
    # Clock rollback clears the identity/group schedule. The same current key
    # must not inherit the old own-high entry as a direct ownership claim.
    set_owner(battle, 9600, False)
    out, status = call_torpedoes(telemetry, 0, sampler, 9.9, ctx,
                                self_ship_id=9601)
    # Clock rollback clears the schedule; the same current key is reclassified
    # low as a far enemy rather than inheriting the old own-high entry.
    assert out[0]['sampling']['group'] == 'low'
    assert out[0]['sampling']['provisional'] is True
    assert out[0]['isOwn'] is False
    assert status['sampling']['classification']['clockReset'] is True
    out, status = call_torpedoes(telemetry, 0, sampler, 14.9, ctx,
                                 self_ship_id=9601)
    assert out[0]['sampling']['group'] == 'low'
    assert out[0]['isOwn'] is False


def test_owner_lookup_budget_tracks_sampled_owner_keys_and_no_duplicate_fields():
    rows = [
        CountedTorpedo(uiId=1, ownerId=9701, shotId=1,
                       position=(0, 0, 2000.0)),  # own far: high
        CountedTorpedo(uiId=2, ownerId=9702, shotId=2,
                       position=(0, 0, 2000.0)),  # enemy far: low
        CountedTorpedo(uiId=3, ownerId=9702, shotId=3,
                       position=(0, 0, 2000.0)),  # same owner: one lookup
        CountedTorpedo(uiId=4, ownerId=True, shotId=4,
                       position=(0, 0, 2000.0)),  # invalid owner id: no lookup
    ]
    telemetry, battle = adapter(rows, {9701: True, 9702: False})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    expected = [
        (0.0, {9701, 9702}),
        (0.2, {9701}),
        (5.0, {9701, 9702}),
        (5.2, {9701}),
        (5.6, {9701, 9702}),
        (10.0, {9701, 9702}),
    ]
    # Baseline = one owner lookup per distinct sampled owner key per tick. On
    # classification ticks every row is sampled, so the pre-read replaces (does
    # not add to) the sampled rows' lookups; non-due far rows read nothing.
    for now, owner_ids in expected:
        before_calls = sum(battle.owner_calls.values())
        before_reads = battle.owner_reads['isPlayer']
        sampled_before = dict(battle.owner_calls)
        out, status = call_torpedoes(telemetry, 0, sampler, now, ctx,
                                    self_ship_id=9701)
        delta_calls = sum(battle.owner_calls.values()) - before_calls
        delta_reads = battle.owner_reads['isPlayer'] - before_reads
        assert delta_calls == len(owner_ids)
        assert delta_reads == len(owner_ids)
        assert sampled_owner_ids(out) == owner_ids
        for owner_id in owner_ids:
            assert battle.owner_calls[owner_id] - sampled_before.get(owner_id, 0) == 1
        invalid = [row for row in out if row['uiId'] == 4]
        if invalid:
            assert invalid[0]['owner'] is None
            assert invalid[0]['isOwn'] is None
            assert invalid[0]['ownerId'] is True
        assert status['membershipComplete'] is False  # bool ownerId is unmatchable

    # One sampled own row plus the unknown identity at 10.2: the far low rows
    # are not due, and the own row reuses its pre-read owner cache this tick.
    before = sum(battle.owner_calls.values())
    out, status = call_torpedoes(telemetry, 0, sampler, 10.2, ctx,
                                self_ship_id=9701)
    assert [row['uiId'] for row in out] == [1, 4]
    assert sum(battle.owner_calls.values()) - before == 1
    assert status['sampling']['low']['status'] == 'notSampled'


def test_duplicate_identity_with_own_owner_is_unmatchable_and_one_lookup_per_tick():
    first = CountedTorpedo(uiId=1, ownerId=9900, shotId=1,
                           position=(0, 0, 2000.0))
    duplicate = CountedTorpedo(uiId=1, ownerId=9900, shotId=1,
                               position=(0, 0, 2100.0))
    telemetry, battle = adapter([first, duplicate], {9900: True})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    rows, status = call_torpedoes(telemetry, 0, sampler, 0.0, ctx,
                                 self_ship_id=9900)
    assert len(rows) == 2
    assert all(row['isOwn'] is True for row in rows)
    assert all(row['sampling']['group'] == 'high' for row in rows)
    assert all(row['sampling']['identityStatus'] == 'duplicate' for row in rows)
    assert status['membershipComplete'] is False
    assert status['membership'] == []
    assert status['sampling']['duplicateIdentityCount'] == 2
    assert battle.owner_calls[9900] == 1

    rows, status = call_torpedoes(telemetry, 0, sampler, 5.0, ctx)
    assert len(rows) == 2
    assert status['membership'] == []
    assert battle.owner_calls[9900] == 2  # one current lookup, not per row


def test_wire_subset_keeps_low_membership_while_own_row_is_sampled():
    own = CountedTorpedo(uiId=1, ownerId=9801, shotId=1,
                         position=(0, 0, 2000.0))
    low = CountedTorpedo(uiId=2, ownerId=9802, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, battle = adapter([own, low], {9801: True, 9802: False})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    call_torpedoes(telemetry, 0, sampler, 0.0, ctx,
                   self_ship_id=9801)
    call_torpedoes(telemetry, 0, sampler, 5.0, ctx,
                   self_ship_id=9801)

    rows, status = call_torpedoes(telemetry, 0, sampler, 5.2, ctx,
                                  self_ship_id=9801)
    rows, wire = sampling_wire_payload(rows, status)
    assert [row['uiId'] for row in rows] == [1]
    assert rows[0]['sampling'] == {'group': 'high', 'sampleTs': 5.2}
    assert wire['membershipComplete'] is True
    assert wire['membership'] == [[1, 9801, 1], [2, 9802, 2]]
    assert wire['sampling']['high']['memberCount'] == 1
    assert wire['sampling']['low']['memberCount'] == 1
    assert wire['sampling']['low']['status'] == 'notSampled'
    json.dumps({'rows': rows, 'status': wire}, allow_nan=False)
