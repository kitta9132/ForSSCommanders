"""Distance-group torpedo sampling: numeric state, cadence and API budgets."""
from collections import Counter
import hashlib
import json
import os
import sys
from types import SimpleNamespace as Obj

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))
import torpedo_telemetry
from torpedo_telemetry import (TorpedoMotion, TorpedoSamplingGroups,
                               TorpedoTelemetry, sampling_wire_payload)


class CountedTorpedo(object):
    """Public-field double that counts each read; no hidden game internals."""
    def __init__(self, uiId=1, ownerId=7000, ownerTeamId=0,
                 ownerType='Ship', shotId=1, type='normal',
                 position=(0.0, 0.0, 0.0), position_error=False):
        object.__setattr__(self, '_values', {
            'uiId': uiId, 'ownerId': ownerId, 'ownerTeamId': ownerTeamId,
            'ownerType': ownerType, 'shotId': shotId, 'type': type,
            'position': position})
        object.__setattr__(self, '_position_error', position_error)
        object.__setattr__(self, 'reads', Counter())

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        reads = object.__getattribute__(self, 'reads')
        if name == 'position':
            reads['position'] += 1
            if object.__getattribute__(self, '_position_error'):
                raise RuntimeError('position unavailable')
            return values['position']
        if name in values:
            reads[name] += 1
            return values[name]
        raise AttributeError(name)

    def set_position(self, value):
        self._values['position'] = value

    def fail_position(self, value):
        object.__setattr__(self, '_position_error', value)


class Battle(object):
    def __init__(self, rows, owner_errors=None):
        self.rows = rows
        self.collection_calls = 0
        self.owner_calls = Counter()
        self.owner_errors = set(owner_errors or ())
        self.owner_alive = True

    def getAllTorpedoes(self):
        self.collection_calls += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.owner_calls[owner_id] += 1
        if owner_id in self.owner_errors:
            raise RuntimeError('owner unavailable')
        return Obj(teamId=0, isAlive=self.owner_alive, isPlayer=False,
                   isBot=True)


class StreamBattle(Battle):
    def __init__(self, factory):
        Battle.__init__(self, None)
        self.factory = factory

    def getAllTorpedoes(self):
        self.collection_calls += 1
        return self.factory()


def context(self_position=(0.0, 0.0, 0.0), width=3000, height=3000):
    return {'selfPosition': list(self_position), 'mapWidth': width,
            'mapHeight': height, 'source': 'calibratedMapExtents',
            'inferred': True}


def adapter(rows, owner_errors=None):
    battle = Battle(rows, owner_errors)
    return TorpedoTelemetry(battle, Obj()), battle


def member(ui_id, owner_id=7000, shot_id=1, group=None):
    entry = {'uiId': ui_id, 'ownerId': owner_id, 'shotId': shot_id}
    if group is not None:
        entry['group'] = group
    return entry


def test_initial_classification_samples_all_and_reports_complete_membership():
    rows = [CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                           position=(0, 0, 999.0)),
            CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                           position=(0, 0, 1000.0)),
            CountedTorpedo(uiId=3, ownerId=7003, shotId=3,
                           position=(0, 0, 1000.1))]
    telemetry, battle = adapter(rows)
    sampler = TorpedoSamplingGroups()
    out, status = telemetry.torpedoes(0, sampler, 100.0, context())

    assert status['available'] is True and status['status'] == 'available'
    assert [row['uiId'] for row in out] == [1, 2, 3]
    assert [row['sampling']['group'] for row in out] == ['high'] * 3
    assert all(row['sampling']['reason'] == 'classification' for row in out)
    assert all(row['sampling']['intervalSeconds'] == 0.2 for row in out)
    assert all(row['sampling']['sampleTs'] == 100.0 for row in out)
    assert all(row['sampling']['classificationTs'] == 100.0 for row in out)
    assert [row['position'] for row in out] == [
        [0.0, 0.0, 999.0], [0.0, 0.0, 1000.0], [0.0, 0.0, 1000.1]]
    assert status['membership'] == [
        member(1, 7001, 1, 'high'), member(2, 7002, 2, 'high'),
        member(3, 7003, 3, 'high')]
    assert status['membershipComplete'] is True
    sampling = status['sampling']
    assert sampling['status'] == 'available'
    assert sampling['classification']['ts'] == 100.0
    assert sampling['classification']['radiusWorld'] == 1000.0
    assert sampling['classification']['radiusSource'] == 'min(mapWidth,mapHeight)/3'
    assert sampling['classification']['mapSource'] == 'calibratedMapExtents'
    assert sampling['classification']['mapInferred'] is True
    assert sampling['classification']['selfPositionStatus'] == 'available'
    assert sampling['classification']['nearCount'] == 2  # boundary is near
    assert sampling['classification']['farCount'] == 1
    assert sampling['classification']['unknownDistanceCount'] == 0
    assert sampling['high']['status'] == 'sampled'
    assert sampling['high']['sampleTs'] == 100.0
    assert sampling['high']['intervalSeconds'] == 0.2
    assert sampling['low']['status'] == 'notSampled'
    assert sampling['low']['intervalSeconds'] == 0.5
    assert battle.collection_calls == 1
    assert [row.reads['position'] for row in rows] == [1, 1, 1]
    for row in rows:
        assert row.reads['uiId'] == 1
        assert row.reads['ownerId'] == 1
        assert row.reads['shotId'] == 1
        assert row.reads['ownerTeamId'] == 1
        assert row.reads['ownerType'] == 1
        assert row.reads['type'] == 1
    assert len(battle.owner_calls) == 3
    assert set(battle.owner_calls.values()) == {1}
    json.dumps({'rows': out, 'status': status}, allow_nan=False)


def test_reclassification_changes_groups_and_samples_both_directions():
    near = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                          position=(0, 0, 500.0))
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, _ = adapter([near, far])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    first, _ = telemetry.torpedoes(0, sampler, 0.0, ctx)
    assert [row['sampling']['group'] for row in first] == ['high', 'high']

    classified, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    groups = dict((row['uiId'], row['sampling']) for row in classified)
    assert groups[1]['group'] == 'high'
    assert groups[2]['group'] == 'low'
    assert groups[2]['intervalSeconds'] == 0.5
    assert groups[2]['provisional'] is False
    assert groups[2]['reason'] == 'classification'
    assert status['sampling']['classification']['groupChangeCount'] == 1
    assert status['sampling']['low']['status'] == 'sampled'
    assert status['membership'] == [
        member(1, 7001, 1, 'high'), member(2, 7002, 2, 'low')]

    far.reads['position'] = 0
    only_high, status = telemetry.torpedoes(0, sampler, 5.2, ctx)
    assert [row['uiId'] for row in only_high] == [1]
    assert far.reads['position'] == 0
    assert status['sampling']['low']['status'] == 'notSampled'
    assert status['membership'] == [
        member(1, 7001, 1, 'high'), member(2, 7002, 2, 'low')]

    far.set_position((0, 0, 400.0))
    upgraded, status = telemetry.torpedoes(0, sampler, 10.0, ctx)
    groups = dict((row['uiId'], row['sampling']) for row in upgraded)
    assert groups[2]['group'] == 'high'
    assert groups[2]['reason'] == 'classification'
    assert status['sampling']['classification']['groupChangeCount'] == 1
    assert status['sampling']['high']['status'] == 'sampled'


def test_low_group_keeps_half_second_deadline_on_two_tenths_ticks():
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, _ = adapter([far])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    telemetry.torpedoes(0, sampler, 5.0, ctx)

    samples = []
    tick = 52
    while tick <= 98:
        now = tick / 10.0
        out, status = telemetry.torpedoes(0, sampler, now, ctx)
        if out:
            assert len(out) == 1
            samples.append(out[0]['sampling']['sampleTs'])
            assert status['sampling']['low']['status'] == 'sampled'
        else:
            assert status['sampling']['low']['status'] == 'notSampled'
        tick += 2

    assert samples == [5.6, 6.0, 6.6, 7.0, 7.6, 8.0, 8.6, 9.0, 9.6]
    intervals = [samples[index + 1] - samples[index]
                 for index in range(len(samples) - 1)]
    assert intervals == pytest.approx([0.4, 0.6] * 4)
    assert samples[-1] - samples[0] == pytest.approx(4.0)
    assert ((samples[-1] - samples[0]) / (len(samples) - 1)) == pytest.approx(0.5)


def test_new_identity_between_classifications_is_immediately_provisional_high():
    near = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                          position=(0, 0, 500.0))
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, _ = adapter([near])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)

    telemetry.battle.rows = [near, far]
    out, status = telemetry.torpedoes(0, sampler, 0.2, ctx)
    groups = dict((row['uiId'], row['sampling']) for row in out)
    assert groups[2]['group'] == 'high'
    assert groups[2]['reason'] == 'new'
    assert groups[2]['provisional'] is True
    assert groups[2]['distanceStatus'] == 'notClassified'
    assert status['membershipComplete'] is True

    # Still provisional high on the following normal tick.
    out, _ = telemetry.torpedoes(0, sampler, 0.4, ctx)
    groups = dict((row['uiId'], row['sampling']) for row in out)
    assert groups[2]['group'] == 'high'
    assert groups[2]['reason'] == 'highDue'

    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    groups = dict((row['uiId'], row['sampling']) for row in out)
    assert groups[2]['group'] == 'low'
    assert groups[2]['provisional'] is False
    assert status['sampling']['low']['status'] == 'sampled'


@pytest.mark.parametrize('bad_context,reason', [
    (None, 'contextMissing'),
    ({'mapWidth': 3000, 'mapHeight': 3000}, 'selfPositionUnavailable'),
    ({'selfPosition': [0, 0, 0], 'mapHeight': 3000},
     'mapDimensionsUnavailable'),
    ({'selfPosition': [0, 0, 0], 'mapWidth': 0, 'mapHeight': 3000},
     'mapDimensionsUnavailable'),
    ({'selfPosition': [0, float('nan'), 0], 'mapWidth': 3000,
      'mapHeight': 3000}, 'selfPositionUnavailable'),
])
def test_unknown_context_forces_every_identity_to_high(bad_context, reason):
    rows = [CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                           position=(0, 0, 500.0)),
            CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                           position=(0, 0, 2000.0))]
    telemetry, _ = adapter(rows)
    out, status = telemetry.torpedoes(
        0, TorpedoSamplingGroups(), 0.0, bad_context)
    assert [row['sampling']['group'] for row in out] == ['high', 'high']
    assert all(row['sampling']['distanceStatus'] == 'unknown' for row in out)
    classification = status['sampling']['classification']
    assert classification['status'] == 'unknown'
    assert classification['reason'] == reason
    assert classification['radiusWorld'] is None
    assert classification['radiusSource'] is None
    assert classification['selfPositionStatus'] == 'unknown'
    assert classification['unknownDistanceCount'] == 2
    assert status['membershipComplete'] is True
    assert [item['group'] for item in status['membership']] == ['high', 'high']


def test_boundary_is_near_and_missing_position_stays_unknown_high():
    boundary = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                              position=(0, 0, 1000.0))
    outside = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                             position=(0, 0, 1000.0001))
    unknown = CountedTorpedo(uiId=3, ownerId=7003, shotId=3, position=None)
    telemetry, _ = adapter([boundary, outside, unknown])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    groups = dict((row['uiId'], row['sampling']) for row in out)
    assert groups[1]['group'] == 'high'  # exactly radius is near
    assert groups[2]['group'] == 'low'
    assert groups[3]['group'] == 'high'
    assert groups[3]['distanceStatus'] == 'unknown'
    assert out[2]['position'] is None
    classification = status['sampling']['classification']
    assert classification['nearCount'] == 1
    assert classification['farCount'] == 1
    assert classification['unknownDistanceCount'] == 1


def test_duplicate_and_unknown_identities_are_unmatchable_and_never_prune():
    valid = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                           position=(0, 0, 500.0))
    duplicate = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                               position=(0, 0, 600.0))
    unknown = CountedTorpedo(uiId=None, ownerId=7002, shotId=2,
                             position=(0, 0, 700.0))
    telemetry, _ = adapter([valid])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)

    telemetry.battle.rows = [valid, duplicate]
    out, status = telemetry.torpedoes(0, sampler, 0.2, ctx)
    assert len(out) == 2
    assert all(row['sampling']['identityStatus'] == 'duplicate' for row in out)
    assert all(row['sampling']['group'] == 'high' for row in out)
    assert status['membership'] == []
    assert status['membershipComplete'] is False
    assert status['sampling']['duplicateIdentityCount'] == 2

    # Only a duplicate is observed at reclassification. Incomplete membership
    # must not prune the previously valid identity.
    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    assert status['membershipComplete'] is False
    assert status['membership'] == []
    assert status['sampling']['prunedCount'] == 0
    telemetry.battle.rows = [valid]
    out, status = telemetry.torpedoes(0, sampler, 5.2, ctx)
    assert len(out) == 1
    assert out[0]['sampling']['reason'] == 'highDue'  # retained, not 'new'
    assert status['membership'] == [member(1, 7001, 1, 'high')]
    assert status['membershipComplete'] is True

    telemetry.battle.rows = [valid, unknown]
    out, status = telemetry.torpedoes(0, sampler, 10.0, ctx)
    assert len(out) == 2
    assert status['membershipComplete'] is False
    assert status['membership'] == [member(1, 7001, 1, 'high')]
    assert status['sampling']['unmatchableIdentityCount'] == 1
    assert status['sampling']['prunedCount'] == 0

    telemetry.battle.rows = [valid]
    out, status = telemetry.torpedoes(0, sampler, 10.2, ctx)
    assert status['membershipComplete'] is True
    assert len(out) == 1


def test_partial_enumeration_is_not_empty_success_and_preserves_state():
    valid = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                           position=(0, 0, 500.0))

    def failing():
        yield valid
        raise RuntimeError('removed during enumeration')

    battle = StreamBattle(lambda: [valid])
    telemetry = TorpedoTelemetry(battle, Obj())
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    battle.factory = failing
    out, status = telemetry.torpedoes(0, sampler, 0.2, ctx)
    assert out == []
    assert status['available'] is False
    assert status['status'] == 'partial'
    assert status['membership'] == []
    assert status['membershipComplete'] is False
    assert status['sampling']['status'] == 'partial'
    assert status['sampling']['high']['status'] == 'notSampled'
    assert status['sampling']['low']['status'] == 'notSampled'

    battle.factory = lambda: [valid]
    out, status = telemetry.torpedoes(0, sampler, 0.4, ctx)
    assert len(out) == 1
    assert out[0]['sampling']['reason'] == 'highDue'
    assert status['sampling']['prunedCount'] == 0

    def raising():
        raise RuntimeError('collection unavailable')

    battle.factory = raising
    out, status = telemetry.torpedoes(0, sampler, 0.6, ctx)
    assert out == []
    assert status['status'] == 'unknown'
    assert status['sampling']['status'] == 'unknown'
    assert status['membershipComplete'] is False


def test_position_read_failure_never_reuses_the_previous_position():
    torpedo = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                             position=(0, 0, 500.0))
    telemetry, _ = adapter([torpedo])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    first, _ = telemetry.torpedoes(0, sampler, 0.0, ctx)
    assert first[0]['position'] == [0.0, 0.0, 500.0]

    torpedo.fail_position(True)
    out, status = telemetry.torpedoes(0, sampler, 0.2, ctx)
    assert out[0]['position'] is None
    assert out[0]['sampling']['positionStatus'] == 'unknown'
    assert out[0]['sampling']['distanceStatus'] == 'near'
    assert torpedo.reads['position'] == 2

    torpedo.fail_position(False)
    torpedo.set_position((0, 0, 520.0))
    out, _ = telemetry.torpedoes(0, sampler, 0.4, ctx)
    assert out[0]['position'] == [0.0, 0.0, 520.0]
    assert torpedo.reads['position'] == 3


def test_clock_rollback_clears_group_state_and_forces_classification():
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, _ = adapter([far])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    assert out[0]['sampling']['group'] == 'low'

    out, status = telemetry.torpedoes(0, sampler, 4.9, ctx)
    assert len(out) == 1
    assert out[0]['sampling']['group'] == 'high'  # cleared -> new provisional
    classification = status['sampling']['classification']
    assert classification['clockReset'] is True
    assert classification['ts'] == 4.9
    assert classification['newCount'] == 1


@pytest.mark.parametrize('lost_context', [
    None,
    {'mapWidth': 3000, 'mapHeight': 3000},
    {'selfPosition': [0, 0, 0], 'mapWidth': 0, 'mapHeight': 3000},
])
def test_context_loss_promotes_a_previous_far_group_without_waiting_five_seconds(
        lost_context):
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, _ = adapter([far])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    out, _ = telemetry.torpedoes(0, sampler, 5.0, ctx)
    assert out[0]['sampling']['group'] == 'low'

    far.reads['position'] = 0
    out, status = telemetry.torpedoes(0, sampler, 5.2, lost_context)
    assert len(out) == 1
    assert out[0]['sampling']['group'] == 'high'
    assert out[0]['sampling']['reason'] == 'contextUnavailable'
    assert out[0]['sampling']['distanceStatus'] == 'unknown'
    assert far.reads['position'] == 1
    assert status['sampling']['safetyHigh'] is True
    assert status['sampling']['promotedCount'] == 1
    assert status['sampling']['high']['status'] == 'sampled'
    assert status['sampling']['low']['status'] == 'notSampled'
    assert status['membership'] == [member(2, 7002, 2, 'high')]

    # A valid context does not silently restore the old low group; the safety
    # promotion remains until the next scheduled five-second classification.
    out, status = telemetry.torpedoes(0, sampler, 5.4, ctx)
    assert out[0]['sampling']['group'] == 'high'
    assert out[0]['sampling']['reason'] == 'highDue'
    assert status['membership'] == [member(2, 7002, 2, 'high')]

    out, status = telemetry.torpedoes(0, sampler, 10.0, ctx)
    assert out[0]['sampling']['group'] == 'low'
    assert status['sampling']['classification']['groupChangeCount'] == 1


def test_clear_resets_for_a_new_battle_without_reusing_old_grouping():
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, _ = adapter([far])
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    telemetry.torpedoes(0, sampler, 5.0, ctx)
    sampler.clear()
    out, status = telemetry.torpedoes(0, sampler, 5.1, ctx)
    assert len(out) == 1
    assert out[0]['sampling']['group'] == 'high'
    assert out[0]['sampling']['reason'] == 'classification'
    assert status['sampling']['classification']['ts'] == 5.1
    assert status['sampling']['classification']['newCount'] == 1


def test_identity_keys_are_type_exact_and_strictly_json_scalars():
    rows = [CountedTorpedo(uiId=1, ownerId=7000, shotId=1,
                           position=(0, 0, 500.0)),
            CountedTorpedo(uiId=1.0, ownerId=7000, shotId=1,
                           position=(0, 0, 600.0)),
            CountedTorpedo(uiId=True, ownerId=7000, shotId=1,
                           position=(0, 0, 700.0)),
            CountedTorpedo(uiId=2, ownerId=True, shotId=1,
                           position=(0, 0, 800.0))]
    telemetry, _ = adapter(rows)
    out, status = telemetry.torpedoes(
        0, TorpedoSamplingGroups(), 0.0, context())
    assert len(out) == 4
    assert status['membershipComplete'] is False
    assert status['sampling']['unmatchableIdentityCount'] == 2
    assert status['sampling']['duplicateIdentityCount'] == 0
    membership = status['membership']
    assert len(membership) == 2
    assert membership[0]['uiId'] == 1
    assert type(membership[0]['uiId']) is int
    assert membership[1]['uiId'] == 1.0
    assert type(membership[1]['uiId']) is float
    json.dumps({'rows': out, 'status': status}, allow_nan=False)


def test_216_torpedoes_22_owners_keep_budget_and_skip_non_due_low_reads():
    near = [CountedTorpedo(uiId=10000 + index, ownerId=7000 + index % 10,
                           shotId=index + 1, position=(index, 0, 500.0))
            for index in range(108)]
    far = [CountedTorpedo(uiId=10000 + index, ownerId=7010 + index % 12,
                          shotId=index + 1, position=(index, 0, 2000.0))
           for index in range(108, 216)]
    rows = near + far
    telemetry, battle = adapter(rows)
    sampler = TorpedoSamplingGroups()
    ctx = context()

    first, status = telemetry.torpedoes(0, sampler, 0.0, ctx)
    assert len(first) == 216
    assert status['sampling']['high']['memberCount'] == 216
    assert status['sampling']['low']['memberCount'] == 0
    assert battle.collection_calls == 1
    assert len(battle.owner_calls) == 22
    assert set(battle.owner_calls.values()) == {1}
    assert all(row.reads['position'] == 1 for row in rows)

    second, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    assert len(second) == 216
    assert status['sampling']['high']['memberCount'] == 108
    assert status['sampling']['low']['memberCount'] == 108
    assert status['sampling']['classification']['groupChangeCount'] == 108
    assert set(battle.owner_calls.values()) == {2}
    assert all(row.reads['position'] == 2 for row in rows)

    high_only, status = telemetry.torpedoes(0, sampler, 5.2, ctx)
    assert len(high_only) == 108
    assert status['sampling']['low']['status'] == 'notSampled'
    assert status['sampling']['low']['sampledCount'] == 0
    assert all(row.reads['position'] == 3 for row in near)
    assert all(row.reads['position'] == 2 for row in far)
    for index in range(10):
        assert battle.owner_calls[7000 + index] == 3
    for index in range(12):
        assert battle.owner_calls[7010 + index] == 2
    assert len(status['membership']) == 216

    both, status = telemetry.torpedoes(0, sampler, 5.6, ctx)
    assert len(both) == 216
    assert status['sampling']['low']['status'] == 'sampled'
    assert all(row.reads['position'] == 4 for row in near)
    assert all(row.reads['position'] == 3 for row in far)
    for index in range(10):
        assert battle.owner_calls[7000 + index] == 4
    for index in range(12):
        assert battle.owner_calls[7010 + index] == 3


def test_owner_failure_and_recovery_are_cached_per_snapshot_only():
    near = CountedTorpedo(uiId=1, ownerId=7000, shotId=1,
                          position=(0, 0, 500.0))
    far = CountedTorpedo(uiId=2, ownerId=7001, shotId=2,
                         position=(0, 0, 2000.0))
    telemetry, battle = adapter([near, far], owner_errors={7001})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    assert battle.owner_calls[7001] == 1
    telemetry.torpedoes(0, sampler, 5.0, ctx)
    assert battle.owner_calls[7001] == 2

    battle.owner_errors = set()
    out, _ = telemetry.torpedoes(0, sampler, 5.2, ctx)
    assert [row['uiId'] for row in out] == [1]
    assert battle.owner_calls[7001] == 2  # far low is not due; no owner lookup
    assert battle.owner_calls[7000] == 3


def test_normalized_context_uses_axis_scales_for_a_world_circle():
    near = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                          position=(0.6, 0, 0.5))
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0.5, 0, 0.9))
    telemetry, _ = adapter([near, far])
    sampler = TorpedoSamplingGroups()
    ctx = {'selfPosition': [0.5, 0.0, 0.5], 'mapWidth': 4000,
           'mapHeight': 2000, 'source': 'calibratedMapExtents',
           'inferred': True, 'positionsNormalized': True}
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    groups = dict((row['uiId'], row['sampling']['group']) for row in out)
    assert groups[1] == 'high'  # dx 400 in world units
    assert groups[2] == 'low'   # dz 800 > min(4000,2000)/3
    classification = status['sampling']['classification']
    assert classification['positionsNormalized'] is True
    assert classification['radiusWorld'] == pytest.approx(2000.0 / 3.0)


def test_motion_membership_retains_non_due_numeric_history_and_prunes():
    motion = TorpedoMotion()
    membership = [member(2, 7002, 2, 'low')]
    far = {'uiId': 2, 'ownerId': 7002, 'shotId': 2,
           'position': [0, 0, 2000.0]}
    motion.update([far], 0.0, True, membership)
    assert far['motion']['available'] is False

    motion.update([], 0.2, True, membership)  # non-due low: no row this tick
    far['position'] = [0, 0, 2100.0]
    motion.update([far], 0.6, True, membership)
    assert far['motion']['available'] is True
    assert far['motion']['dt'] == pytest.approx(0.6)
    assert far['motion']['velocity'][2] == pytest.approx(100.0 / 0.6)

    far['position'] = [0, 0, 2300.0]
    motion.update([far], 2.0, True, membership)  # dt > 1 resets history
    assert far['motion']['available'] is False
    assert far['motion']['observedAge'] == 0

    motion.update([], 2.2, True, [])  # normal empty membership prunes history
    far['position'] = [0, 0, 2400.0]
    motion.update([far], 2.4, True, membership)
    assert far['motion']['available'] is False


def test_motion_without_membership_keeps_the_legacy_drop_on_absent_rows():
    motion = TorpedoMotion()
    far = {'uiId': 2, 'ownerId': 7002, 'shotId': 2,
           'position': [0, 0, 2000.0]}
    motion.update([far], 0.0)
    motion.update([], 0.2)
    far['position'] = [0, 0, 2100.0]
    motion.update([far], 0.4)
    assert far['motion']['available'] is False


def test_strict_motion_does_not_alias_numeric_id_types_or_duplicate_rows():
    motion = TorpedoMotion()
    first = {'uiId': 1, 'ownerId': 7001, 'shotId': 1, 'position': [0, 0, 0]}
    motion.update([first], 0., True, [dict(first)])
    changed = dict(first, uiId=1.0, position=[100, 0, 0])
    motion.update([changed], .2, True, [dict(changed)])
    assert changed['motion']['available'] is False
    duplicate = dict(changed, position=[200, 0, 0])
    motion.update([changed, duplicate], .4, True, [dict(changed), dict(duplicate)])
    assert not changed['motion']['available']
    assert not duplicate['motion']['available']
    unsafe = dict(first, uiId=['not', 'an', 'id'])
    motion.update([unsafe], .6, True, [])
    assert not unsafe['motion']['available']


def test_compact_wire_metadata_preserves_identity_and_freshness_without_game_fields_loss():
    from torpedo_telemetry import sampling_wire_payload
    item = CountedTorpedo(uiId=1, ownerId=7001, shotId=1, position=(0, 0, 500))
    telemetry, _ = adapter([item])
    rows, status = telemetry.torpedoes(0, TorpedoSamplingGroups(), 0., context())
    original_membership = list(status['membership'])
    position = list(rows[0]['position'])
    rows, wire = sampling_wire_payload(rows, status)
    assert status['membership'] == original_membership  # motion's input is unmodified
    assert wire['membershipFields'] == ['uiId', 'ownerId', 'shotId']
    assert wire['membership'] == [[1, 7001, 1]]
    assert rows[0]['position'] == position
    assert rows[0]['sampling'] == {'group': 'high', 'sampleTs': 0., 'provisional': True}
    assert wire['sampling']['classification']['radiusWorld'] == 1000.


# Captured from the pre-optimization post-parent telemetry module. The full
# digest covers every wire row/sampling field and the compact status; the
# readable tuples keep row order, groups, sample timestamps and budgets visible.
REFERENCE_REPLAY = (
    (0.0, [(1, 7001, 1, 'high', 0.0), (2, 7002, 2, 'high', 0.0)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 0.0, 1000.0),
     (('sampled', 2, 2, 0.0), ('notSampled', 0, 0, None), False)),
    (0.2, [(1, 7001, 1, 'high', 0.2), (2, 7002, 2, 'high', 0.2)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 0.0, 1000.0),
     (('sampled', 2, 2, 0.2), ('notSampled', 0, 0, None), False)),
    (0.6, [(1, 7001, 1, 'high', 0.6), (2, 7002, 2, 'high', 0.6)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 0.0, 1000.0),
     (('sampled', 2, 2, 0.6), ('notSampled', 0, 0, None), False)),
    (5.0, [(1, 7001, 1, 'high', 5.0), (2, 7002, 2, 'low', 5.0)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 5.0, 1000.0),
     (('sampled', 1, 1, 5.0), ('sampled', 1, 1, 5.0), False)),
    (5.2, [(1, 7001, 1, 'high', 5.2)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 5.0, 1000.0),
     (('sampled', 1, 1, 5.2), ('notSampled', 0, 1, 5.0), False)),
    (5.6, [(1, 7001, 1, 'high', 5.6), (2, 7002, 2, 'low', 5.6)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 5.0, 1000.0),
     (('sampled', 1, 1, 5.6), ('sampled', 1, 1, 5.6), False)),
    (6.0, [(1, 7001, 1, 'high', 6.0), (2, 7002, 2, 'low', 6.0)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 5.0, 1000.0),
     (('sampled', 1, 1, 6.0), ('sampled', 1, 1, 6.0), False)),
    (6.2, [(1, 7001, 1, 'high', 6.2), (2, 7002, 2, 'high', 6.2),
           (None, 7003, 3, 'high', 6.2)],
     [(1, 7001, 1), (2, 7002, 2)], False,
     ('available', None, 5.0, 1000.0),
     (('sampled', 3, 2, 6.2), ('notSampled', 0, 0, 6.0), True)),
    (6.4, [(1, 7001, 1, 'high', 6.4), (2, 7002, 2, 'high', 6.4)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 5.0, 1000.0),
     (('sampled', 2, 2, 6.4), ('notSampled', 0, 0, 6.0), False)),
    (10.0, [(1, 7001, 1, 'high', 10.0), (2, 7002, 2, 'low', 10.0)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 10.0, 1000.0),
     (('sampled', 1, 1, 10.0), ('sampled', 1, 1, 10.0), False)),
    (10.2, [(1, 7001, 1, 'high', 10.2)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 10.0, 1000.0),
     (('sampled', 1, 1, 10.2), ('notSampled', 0, 1, 10.0), False)),
    (10.6, [(1, 7001, 1, 'high', 10.6), (2, 7002, 2, 'low', 10.6)],
     [(1, 7001, 1), (2, 7002, 2)], True,
     ('available', None, 10.0, 1000.0),
     (('sampled', 1, 1, 10.6), ('sampled', 1, 1, 10.6), False)),
)
REFERENCE_REPLAY_DIGEST = (
    'a0723ccc1dac4fe08e87d9bfd62017c8d9f535d98995830f075d8a436eb73bcf')


def _reference_snapshot(rows, status):
    rows, status = sampling_wire_payload(rows, status)
    sampling = status['sampling']
    high, low = sampling['high'], sampling['low']
    visible = (
        [(row['uiId'], row['ownerId'], row['shotId'],
          row['sampling']['group'], row['sampling']['sampleTs'])
         for row in rows],
        [tuple(item) for item in status['membership']],
        status['membershipComplete'],
        (sampling['classification']['status'],
         sampling['classification']['reason'],
         sampling['classification']['ts'],
         sampling['classification']['radiusWorld']),
        ((high['status'], high['sampledCount'], high['memberCount'],
          high['sampleTs']),
         (low['status'], low['sampledCount'], low['memberCount'],
          low['sampleTs']),
         sampling['safetyHigh']))
    digest_value = {
        'rows': [[type(row.get('uiId')).__name__,
                  row.get('uiId'), row.get('ownerId'), row.get('shotId'),
                  row.get('sampling', {}).get('group'),
                  row.get('sampling', {}).get('sampleTs')]
                 for row in rows],
        'membership': status['membership'],
        'membershipComplete': status['membershipComplete'],
        'sampling': sampling,
    }
    return visible, digest_value


def test_reference_replay_matches_pre_optimization_snapshot_sequence():
    near = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                          position=(0, 0, 500.0))
    far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                         position=(0, 0, 2000.0))
    unknown = CountedTorpedo(uiId=None, ownerId=7003, shotId=3,
                             position=(0, 0, 700.0))
    telemetry, battle = adapter([near, far])
    sampler = TorpedoSamplingGroups()
    plan = ((0.0, False, False), (0.2, False, False), (0.6, False, False),
            (5.0, False, False), (5.2, False, False), (5.6, False, False),
            (6.0, False, False), (6.2, True, True), (6.4, False, False),
            (10.0, False, False), (10.2, False, False), (10.6, False, False))
    actual = []
    digest_value = hashlib.sha256()
    for now, add_unknown, lost_context in plan:
        battle.rows = [near, far]
        if add_unknown:
            battle.rows.append(unknown)
        rows, status = telemetry.torpedoes(
            0, sampler, now, None if lost_context else context())
        visible, snapshot = _reference_snapshot(rows, status)
        actual.append((now,) + visible)
        digest_value.update(json.dumps(
            snapshot, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode('utf-8'))

    assert tuple(actual) == REFERENCE_REPLAY
    assert digest_value.hexdigest() == REFERENCE_REPLAY_DIGEST


REFERENCE_RECORDINGS = {
    'without-atm-b43.jsonl': {
        'digest': 'fceea141693d6072aa9afb2e9776b2510f2c800cc0d5dca89e6158192b5dc86a',
        'budgets': {
            'states': 1194, 'originalRows': 95413,
            'originalOwnerBudget': 12654, 'sampledRows': 85987,
            'membershipRows': 95413, 'incompleteMembershipStates': 0,
            'originalCompactBytes': 137408822,
            'projectedCompactBytes': 137312512,
            'sampled.high': 79643, 'sampled.low': 6344},
        'api': {
            'collection': 1194, 'field.ownerId': 95413,
            'field.ownerTeamId': 85987, 'field.ownerType': 85987,
            'field.position': 85987, 'field.shotId': 95413,
            'field.type': 85987, 'field.uiId': 95413, 'owner': 12293}},
    'without-atm-b44.jsonl': {
        'digest': 'e52389754219c96d25e89a63da7d5d8648decf59f5cad90bbf53ff1f4328d528',
        'budgets': {
            'states': 743, 'originalRows': 9671,
            'originalOwnerBudget': 1998, 'sampledRows': 7870,
            'membershipRows': 9671, 'incompleteMembershipStates': 0,
            'originalCompactBytes': 28110393,
            'projectedCompactBytes': 27750363,
            'sampled.high': 6678, 'sampled.low': 1192},
        'api': {
            'collection': 743, 'field.ownerId': 9671,
            'field.ownerTeamId': 7870, 'field.ownerType': 7870,
            'field.position': 7870, 'field.shotId': 9671,
            'field.type': 7870, 'field.uiId': 9671, 'owner': 1833}},
}


class _RecordingTorpedo(object):
    def __init__(self, row, counts):
        self.row = row
        self.counts = counts

    def __getattr__(self, name):
        self.counts['field.' + name] += 1
        return self.row.get(name)


class _RecordingBattle(object):
    def __init__(self):
        self.rows = []
        self.owners = {}
        self.counts = Counter()

    def set_rows(self, rows):
        self.rows = [_RecordingTorpedo(row, self.counts) for row in rows]
        self.owners = dict((row.get('ownerId'), row.get('owner'))
                           for row in rows)

    def getAllTorpedoes(self):
        self.counts['collection'] += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.counts['owner'] += 1
        return self.owners.get(owner_id)


def _recording_identity(row):
    return tuple((type(row.get(name)).__name__, row.get(name))
                 for name in ('uiId', 'ownerId', 'shotId'))


def _recording_context(state):
    own = state.get('self') or {}
    fit = state.get('diag', {}).get('mapCalibration', {})
    if own.get('isObserver') is not False or fit.get('status') != 'available':
        return None
    try:
        coeff = fit['coefficients']
        width = abs(float(coeff['worldX']['scale']))
        height = abs(float(coeff['worldZ']['scale']))
        pos = own['position']
        if (len(pos) != 3 or not all(-1e9 < value < 1e9 for value in pos)
                or not 0 < width < 1e9 or not 0 < height < 1e9):
            return None
        return {'selfPosition': pos, 'mapWidth': width, 'mapHeight': height,
                'source': 'calibratedMapExtents', 'inferred': True}
    except (KeyError, TypeError, ValueError):
        return None


def _encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                          allow_nan=False).encode('utf-8'))


def _recording_canonical(rows, status):
    return {
        'available': status.get('available'),
        'status': status.get('status'),
        'membershipComplete': status.get('membershipComplete'),
        'membershipFields': status.get('membershipFields'),
        'membership': status.get('membership'),
        'sampling': status.get('sampling'),
        'rows': [{
            'identity': [type(row.get(name)).__name__
                         for name in ('uiId', 'ownerId', 'shotId')],
            'ids': [row.get('uiId'), row.get('ownerId'), row.get('shotId')],
            'sampling': row.get('sampling'),
            'position': row.get('position'),
            'mapPosition': row.get('mapPosition'),
            'mapPositionStatus': row.get('mapPositionStatus'),
        } for row in rows],
    }


def _replay_recording(path):
    battle = _RecordingBattle()
    sampler = TorpedoSamplingGroups()
    telemetry = TorpedoTelemetry(battle, None)
    counts = Counter()
    digest_value = hashlib.sha256()
    previous_battle = object()
    with open(path, encoding='utf-8-sig') as stream:
        for line in stream:
            event = json.loads(line)
            state = event.get('data', {})
            if event.get('kind') != 'state' or state.get('active') is not True:
                continue
            if state.get('battleId') != previous_battle:
                sampler.clear()
                previous_battle = state.get('battleId')
            original = state.get('torpedoes', [])
            battle.set_rows(original)
            rows, status = telemetry.torpedoes(
                (state.get('self') or {}).get('teamId'), sampling=sampler,
                now=state['ts'], context=_recording_context(state))
            rows, status = sampling_wire_payload(rows, status)
            digest_value.update(json.dumps(
                _recording_canonical(rows, status), sort_keys=True,
                separators=(',', ':'), ensure_ascii=False,
                allow_nan=False).encode('utf-8'))
            counts['states'] += 1
            counts['originalRows'] += len(original)
            counts['originalOwnerBudget'] += len(set(
                (type(row.get('ownerId')).__name__, row.get('ownerId'))
                for row in original if row.get('ownerId') is not None))
            counts['sampledRows'] += len(rows)
            counts['membershipRows'] += len(status.get('membership', []))
            counts['incompleteMembershipStates'] += (
                status.get('membershipComplete') is not True)
            counts['originalCompactBytes'] += _encoded_size(state)
            index = dict((_recording_identity(row), row)
                         for row in original)
            projected = []
            for row in rows:
                value = dict(index.get(_recording_identity(row), row))
                value['sampling'] = row.get('sampling')
                projected.append(value)
                counts['sampled.' + str(
                    (row.get('sampling') or {}).get('group'))] += 1
            output = dict(state, torpedoes=projected, torpedoStatus=status)
            counts['projectedCompactBytes'] += _encoded_size(output)
    return digest_value.hexdigest(), counts, battle.counts


@pytest.mark.skipif(
    os.environ.get('WOWS_SAMPLING_REPLAY') != '1',
    reason='set WOWS_SAMPLING_REPLAY=1 to replay private recordings')
@pytest.mark.parametrize('recording', sorted(REFERENCE_RECORDINGS))
def test_private_recording_reference_replay_keeps_exact_snapshot_budget(
        recording):
    path = os.path.join(os.path.dirname(__file__), '..', 'recordings',
                        recording)
    if not os.path.exists(path):
        pytest.skip('private recording is not available')
    expected = REFERENCE_RECORDINGS[recording]
    digest_value, counts, api_counts = _replay_recording(path)
    assert digest_value == expected['digest']
    assert dict(counts) == expected['budgets']
    assert dict(api_counts) == expected['api']


def test_incomplete_identity_observations_do_not_retain_old_schedules_forever():
    item = CountedTorpedo(uiId=1, ownerId=7001, shotId=1, position=(0, 0, 500))
    telemetry, battle = adapter([item])
    sampler = TorpedoSamplingGroups()
    telemetry.torpedoes(0, sampler, 0., context())
    assert len(sampler._entries) == 1
    # This incomplete but successful enumeration does not assert disappearance.
    item.uiId = None
    telemetry.torpedoes(0, sampler, 5., context())
    assert len(sampler._entries) == 1
    telemetry.torpedoes(0, sampler, 11., context())
    assert not sampler._entries
    item.uiId = 1
    rows, _ = telemetry.torpedoes(0, sampler, 11.2, context())
    assert rows[0]['sampling']['group'] == 'high'
    assert rows[0]['sampling']['provisional'] is True


def test_bad_sampler_decision_count_is_not_reported_as_a_successful_empty_list():
    class BrokenSampler(TorpedoSamplingGroups):
        def observe(self, *args, **kwargs):
            return []
    telemetry, _ = adapter([CountedTorpedo()])
    rows, status = telemetry.torpedoes(0, BrokenSampler(), 0., context())
    assert rows == []
    assert status['status'] == 'unknown'
    assert status['available'] is False
    assert status['membershipComplete'] is False
    assert status['sampling']['reason'] == 'samplingError'


def test_sampling_does_not_require_optional_sandbox_builtins():
    original = torpedo_telemetry.__dict__['__builtins__']
    restricted = dict(original)
    for name in ('iter', 'next', 'AttributeError', 'TypeError'):
        restricted.pop(name, None)
    torpedo_telemetry.__dict__['__builtins__'] = restricted
    try:
        near = CountedTorpedo(uiId=1, ownerId=7001, shotId=1,
                              position=(0, 0, 500.0))
        far = CountedTorpedo(uiId=2, ownerId=7002, shotId=2,
                             position=(0, 0, 2000.0))
        telemetry, _ = adapter([near, far])
        sampler = TorpedoSamplingGroups()
        ctx = context()
        out, status = telemetry.torpedoes(0, sampler, 0.0, ctx)
        assert len(out) == 2 and status['membershipComplete'] is True
        out, status = telemetry.torpedoes(0, sampler, 0.2, ctx)
        assert len(out) == 2
        assert status['sampling']['low']['status'] == 'notSampled'
    finally:
        torpedo_telemetry.__dict__['__builtins__'] = original
