"""Research tests for a test-only three-tier far torpedo cadence.

These tests exercise the prototype sampler in ``tools/``.  They do not import
or modify the production sampler constants and do not install/run anything in
the game.  Private recording tests are opt-in through environment variables.
"""
from collections import Counter
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, 'res_mods', 'PnFMods',
                                'WowsExtractor'))
sys.path.insert(0, os.path.join(_ROOT, 'tools'))

from torpedo_telemetry import (  # noqa: E402
    TorpedoMotion, TorpedoSamplingGroups, TorpedoTelemetry,
    sampling_wire_payload)
from far_torpedo_1hz_candidate import (  # noqa: E402
    SAMPLING_MID, TieredTorpedoSamplingGroups,
    tiered_sampling_wire_payload)


class Torpedo(object):
    def __init__(self, uiId=1, ownerId=7000, shotId=1,
                 position=(0.0, 0.0, 0.0)):
        self.uiId = uiId
        self.ownerId = ownerId
        self.ownerTeamId = 0
        self.ownerType = 'Ship'
        self.shotId = shotId
        self.type = 'normal'
        self.position = position


class Owner(object):
    def __init__(self, is_player=False):
        self.teamId = 0
        self.isAlive = True
        self.isPlayer = is_player
        self.isBot = not is_player


class Battle(object):
    def __init__(self, rows, owners=None):
        self.rows = rows
        self.owners = owners or {}
        self.collection_calls = 0
        self.owner_calls = Counter()

    def getAllTorpedoes(self):
        self.collection_calls += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.owner_calls[owner_id] += 1
        return self.owners.get(
            owner_id, Owner(owner_id in (7000, 7001)))


def adapter(rows, owners=None):
    battle = Battle(rows, owners)
    return TorpedoTelemetry(battle, SimpleNamespace()), battle


def context(width=3000.0, height=3000.0, position=(0.0, 0.0, 0.0)):
    return {'selfPosition': list(position), 'mapWidth': width,
            'mapHeight': height, 'source': 'calibratedMapExtents',
            'inferred': True}


def member(ui_id, owner_id, shot_id, group):
    return {'uiId': ui_id, 'ownerId': owner_id, 'shotId': shot_id,
            'group': group}


def groups_by_id(rows):
    return dict((row['uiId'], row['sampling']) for row in rows)


def test_three_tier_boundaries_intervals_and_own_override():
    rows = [
        Torpedo(1, 7001, 1, (0, 0, 599.0)),
        Torpedo(2, 7001, 2, (0, 0, 600.0)),       # L/5 boundary: near
        Torpedo(3, 7002, 3, (0, 0, 600.1)),
        Torpedo(4, 7002, 4, (0, 0, 999.9)),
        Torpedo(5, 7003, 5, (0, 0, 1000.0)),      # L/3 boundary: mid
        Torpedo(6, 7003, 6, (0, 0, 1000.1)),
        Torpedo(7, 7000, 7, (0, 0, 1500.0)),      # own far: high
    ]
    owners = {7000: Owner(True), 7001: Owner(False),
              7002: Owner(False), 7003: Owner(False)}
    telemetry, _ = adapter(rows, owners)
    sampler = TieredTorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx, self_ship_id=7000)
    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx,
                                      self_ship_id=7000)
    groups = groups_by_id(out)
    assert [groups[index]['group'] for index in range(1, 8)] == [
        'high', 'high', 'mid', 'mid', 'mid', 'low', 'high']
    assert [groups[index]['intervalSeconds'] for index in range(1, 8)] == [
        0.2, 0.2, 0.5, 0.5, 0.5, 1.0, 0.2]
    assert [groups[index]['distanceStatus'] for index in range(1, 8)] == [
        'near', 'near', 'mid', 'mid', 'mid', 'far', 'far']
    classification = status['sampling']['classification']
    assert classification['nearCount'] == 2
    assert classification['midCount'] == 3
    assert classification['farCount'] == 2
    assert classification['unknownDistanceCount'] == 0
    assert classification['radiusWorld'] == pytest.approx(600.0)
    assert classification['midRadiusWorld'] == pytest.approx(1000.0)
    assert classification['radiusSource'] == 'min(mapWidth,mapHeight)/5'
    assert classification['midRadiusSource'] == 'min(mapWidth,mapHeight)/3'
    assert status['sampling']['classification']['intervalSeconds'] == 5.0
    assert status['sampling']['high']['intervalSeconds'] == 0.2
    assert status['sampling']['mid']['intervalSeconds'] == 0.5
    assert status['sampling']['low']['intervalSeconds'] == 1.0
    assert status['membership'] == [
        member(1, 7001, 1, 'high'), member(2, 7001, 2, 'high'),
        member(3, 7002, 3, 'mid'), member(4, 7002, 4, 'mid'),
        member(5, 7003, 5, 'mid'), member(6, 7003, 6, 'low'),
        member(7, 7000, 7, 'high')]


def test_mid_and_far_keep_existing_deadline_grid_without_catchup():
    rows = [Torpedo(1, 7003, 1, (0, 0, 800.0)),
            Torpedo(2, 7002, 2, (0, 0, 1500.0))]
    telemetry, _ = adapter(rows)
    sampler = TieredTorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    telemetry.torpedoes(0, sampler, 5.0, ctx)

    samples = {1: [], 2: []}
    tick = 52
    while tick <= 98:
        now = tick / 10.0
        out, _ = telemetry.torpedoes(0, sampler, now, ctx)
        for row in out:
            samples[row['uiId']].append(row['sampling']['sampleTs'])
        tick += 2
    assert samples[1] == [5.6, 6.0, 6.6, 7.0, 7.6, 8.0, 8.6, 9.0, 9.6]
    intervals = [b - a for a, b in zip(samples[1], samples[1][1:])]
    assert intervals == pytest.approx([0.4, 0.6] * 4)
    assert samples[2] == [6.0, 7.0, 8.0, 9.0]
    assert [b - a for a, b in zip(samples[2], samples[2][1:])] == [
        pytest.approx(1.0)] * 3

    # A large tick gap re-anchors to now + interval and never emits catch-up
    # rows.  The 1.0 s far group is not a backlog queue.
    far_telemetry, _ = adapter([rows[1]])
    far_sampler = TieredTorpedoSamplingGroups()
    far_telemetry.torpedoes(0, far_sampler, 0.0, ctx)
    far_telemetry.torpedoes(0, far_sampler, 5.0, ctx)
    out, _ = far_telemetry.torpedoes(0, far_sampler, 8.3, ctx)
    assert [row['uiId'] for row in out] == [2]
    out, _ = far_telemetry.torpedoes(0, far_sampler, 9.2, ctx)
    assert [row['uiId'] for row in out] == []
    out, _ = far_telemetry.torpedoes(0, far_sampler, 9.4, ctx)
    assert [row['uiId'] for row in out] == [2]


def test_own_promotion_overrides_a_stale_far_group():
    owners = {7001: Owner(False), 7002: Owner(False)}
    rows = [Torpedo(1, 7001, 1, (0, 0, 800.0)),
            Torpedo(2, 7002, 2, (0, 0, 1500.0))]
    telemetry, _ = adapter(rows, owners)
    sampler = TieredTorpedoSamplingGroups()
    ctx = context()
    # Start with row 1 as self so row 2 is a non-own far low row.
    telemetry.torpedoes(0, sampler, 0.0, ctx, self_ship_id=7001)
    out, _ = telemetry.torpedoes(0, sampler, 5.0, ctx,
                                 self_ship_id=7001)
    assert groups_by_id(out)[2]['group'] == 'low'

    # Switch self to row 2's owner; the stale far group must promote to high.
    out, _ = telemetry.torpedoes(0, sampler, 6.0, ctx,
                                 self_ship_id=7002)
    promoted = groups_by_id(out)[2]
    assert promoted['group'] == 'high'
    assert promoted['reason'] == 'highDue'
    assert promoted['intervalSeconds'] == 0.2
    # Row 1 stops being own but the cadence scheduler does not demote an enemy
    # between classifications; it keeps the old high schedule until the next
    # classification tick re-evaluates distance and team class.
    assert groups_by_id(out)[1]['group'] == 'high'
    out, _ = telemetry.torpedoes(0, sampler, 6.2, ctx,
                                 self_ship_id=7002)
    assert groups_by_id(out)[2]['group'] == 'high'
    out, _ = telemetry.torpedoes(0, sampler, 6.6, ctx,
                                 self_ship_id=7002)
    assert groups_by_id(out)[1]['group'] == 'high'
    assert groups_by_id(out)[2]['group'] == 'high'
    # At the next classification the stale row is re-evaluated as enemy mid.
    out, status = telemetry.torpedoes(0, sampler, 10.0, ctx,
                                      self_ship_id=7002)
    assert groups_by_id(out)[1]['group'] == 'mid'
    assert groups_by_id(out)[2]['group'] == 'high'
    assert status['sampling']['classification']['midCount'] == 1


def test_new_unknown_context_loss_and_reclassification():
    near = Torpedo(1, 7001, 1, (0, 0, 500.0))
    far = Torpedo(2, 7002, 2, (0, 0, 1500.0))
    unknown = Torpedo(3, 7003, 3, None)
    telemetry, battle = adapter([near], {})
    sampler = TieredTorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)

    battle.rows = [near, far]
    out, status = telemetry.torpedoes(0, sampler, 0.2, ctx)
    new = groups_by_id(out)[2]
    assert new['group'] == 'high' and new['provisional'] is True
    assert new['reason'] == 'new'
    assert new['distanceStatus'] == 'notClassified'

    battle.rows = [near, far, unknown]
    out, _ = telemetry.torpedoes(0, sampler, 0.4, ctx)
    assert groups_by_id(out)[3]['group'] == 'high'
    assert groups_by_id(out)[3]['distanceStatus'] == 'notClassified'
    assert groups_by_id(out)[3]['provisional'] is True

    out, status = telemetry.torpedoes(0, sampler, 0.6, None)
    assert all(row['sampling']['group'] == 'high' for row in out)
    assert all(row['sampling']['distanceStatus'] == 'unknown' for row in out)
    assert status['sampling']['safetyHigh'] is True

    out, status = telemetry.torpedoes(0, sampler, 5.0, ctx)
    groups = groups_by_id(out)
    assert groups[1]['group'] == 'high'
    assert groups[2]['group'] == 'low'
    assert groups[3]['group'] == 'high'
    assert status['sampling']['classification']['newCount'] == 0

    out, status = telemetry.torpedoes(0, sampler, 4.9, ctx)
    assert groups_by_id(out)[1]['group'] == 'high'
    assert out[0]['sampling']['provisional'] is True
    assert status['sampling']['classification']['clockReset'] is True


def test_identity_types_remain_type_exact_and_membership_is_not_truncated():
    rows = [Torpedo(1, 7000, 1, (0, 0, 500.0)),
            Torpedo(1.0, 7000, 1, (0, 0, 600.0)),
            Torpedo(True, 7000, 1, (0, 0, 700.0)),
            Torpedo(2, True, 1, (0, 0, 800.0))]
    telemetry, _ = adapter(rows)
    out, status = telemetry.torpedoes(
        0, TieredTorpedoSamplingGroups(), 0.0, context())
    assert len(out) == 4
    assert status['membershipComplete'] is False
    assert status['sampling']['unmatchableIdentityCount'] == 2
    assert status['sampling']['duplicateIdentityCount'] == 0
    assert len(status['membership']) == 2
    assert type(status['membership'][0]['uiId']) is int
    assert type(status['membership'][1]['uiId']) is float


def test_tiered_wire_contract_is_a_prototype_with_a_mid_group():
    rows = [Torpedo(1, 7003, 1, (0, 0, 800.0)),
            Torpedo(2, 7002, 2, (0, 0, 1500.0))]
    telemetry, _ = adapter(rows)
    sampler = TieredTorpedoSamplingGroups()
    telemetry.torpedoes(0, sampler, 0.0, context())
    out, status = telemetry.torpedoes(0, sampler, 5.0, context())
    out, wire = tiered_sampling_wire_payload(out, status)
    assert wire['membershipFields'] == ['uiId', 'ownerId', 'shotId']
    assert [item[2] for item in wire['membership']] == [1, 2]
    assert wire['sampling']['mid']['intervalSeconds'] == 0.5
    assert wire['sampling']['low']['intervalSeconds'] == 1.0
    assert wire['sampling']['classification']['midRadiusWorld'] == 1000.0
    assert [row['sampling']['group'] for row in out] == ['mid', 'low']
    # The production wire contract currently omits a mid summary.
    _, base_wire = sampling_wire_payload(
        [dict(row) for row in out], dict(status, sampling=dict(
            status['sampling'])))
    assert 'mid' not in base_wire['sampling']


def test_real_motion_loses_velocity_at_a_far_one_second_jittered_gap():
    far = Torpedo(1, 7003, 1, (0, 0, 1500.0))
    telemetry, _ = adapter([far])
    sampler = TieredTorpedoSamplingGroups()
    motion = TorpedoMotion()
    ctx = context()

    def tick(now):
        rows, status = telemetry.torpedoes(
            0, sampler, now, ctx)
        membership = (status['membership']
                      if status['membershipComplete'] is True else [])
        motion.update(rows, now, status['available'],
                      membership=membership)
        return rows

    tick(0.0)       # provisional high
    tick(5.0)       # classification, far low
    rows = tick(6.0)
    assert rows[0]['sampling']['group'] == 'low'
    assert rows[0]['motion']['available'] is True
    assert rows[0]['motion']['dt'] == pytest.approx(1.0)
    rows = tick(7.02)  # 1.02 s after the previous far sample
    assert rows[0]['sampling']['group'] == 'low'
    assert rows[0]['motion']['available'] is False
    assert rows[0]['motion']['dt'] is None
    assert rows[0]['motion']['observedAge'] == 0


def test_synthetic_216_torpedoes_22_owners_host_cost_is_not_a_game_metric():
    import compare_far_torpedo_1hz
    result = compare_far_torpedo_1hz.synthetic_benchmark(
        repeats=2, ticks=60)
    baseline = result['baseline']
    candidate = result['candidate']
    assert result['rows'] == 216 and result['owners'] == 22
    assert result['hostOnly'] is True
    assert baseline['enumerations'] == candidate['enumerations'] == 120
    assert baseline['identityReads'] == candidate['identityReads']
    assert candidate['sampledRows'] < baseline['sampledRows']
    assert candidate['positionReads'] == candidate['sampledRows']
    assert sum(candidate['sampledByGroup'].values()) == candidate['sampledRows']
    assert candidate['sampledByGroup']['high'] == \
        baseline['sampledByGroup']['high']
    assert candidate['sampledByGroup']['mid'] > 0
    assert candidate['sampledByGroup']['low'] > 0
    assert candidate['medianTickMs'] > 0
    assert baseline['medianTickMs'] > 0


B43_EXPECTED = {
    'states': 1194, 'originalRows': 95413, 'membershipRows': 95413,
    'incompleteMembershipStates': 0, 'sampledRows': 73711,
    'sampled.high': 59145, 'sampled.low': 14566,
    'positionReads': 73711, 'ownerLookups': 11371,
    'classificationTicks': 48}
B44_EXPECTED = {
    'states': 743, 'originalRows': 9671, 'membershipRows': 9671,
    'incompleteMembershipStates': 0, 'sampledRows': 6044,
    'sampled.high': 3640, 'sampled.low': 2404,
    'positionReads': 6044, 'ownerLookups': 1391,
    'classificationTicks': 30}


@pytest.mark.skipif(
    os.environ.get('WOWS_FAR_1HZ_REPLAY') != '1',
    reason='set WOWS_FAR_1HZ_REPLAY=1 to replay private recordings')
@pytest.mark.parametrize('name,expected', [
    ('without-atm-b43.jsonl', B43_EXPECTED),
    ('without-atm-b44.jsonl', B44_EXPECTED)])
def test_private_baseline_replay_and_three_tier_invariants(name, expected):
    import compare_far_torpedo_1hz
    path = os.path.join(_ROOT, 'recordings', name)
    if not os.path.exists(path):
        pytest.skip('private recording is not available')
    result = compare_far_torpedo_1hz.replay_recording(
        path, compute_bytes=False)
    baseline = result['baseline']
    candidate = result['candidate']
    comparison = result['comparison']
    assert baseline['states'] == expected['states']
    assert baseline['originalRows'] == expected['originalRows']
    assert baseline['membershipRows'] == expected['membershipRows']
    assert baseline['incompleteMembershipStates'] == 0
    assert baseline['sampledRows'] == expected['sampledRows']
    assert baseline['sampledByGroup']['high'] == expected['sampled.high']
    assert baseline['sampledByGroup']['low'] == expected['sampled.low']
    assert baseline['positionReads'] == expected['positionReads']
    assert baseline['ownerLookups'] == expected['ownerLookups']
    assert baseline['classificationTicks'] == expected['classificationTicks']

    assert candidate['states'] == expected['states']
    assert candidate['originalRows'] == expected['originalRows']
    assert candidate['membershipRows'] == expected['membershipRows']
    assert candidate['incompleteMembershipStates'] == 0
    assert candidate['positionReads'] == candidate['sampledRows']
    assert sum(candidate['sampledByGroup'].values()) == \
        candidate['sampledRows']
    assert candidate['sampledRows'] < baseline['sampledRows']
    assert candidate['sampledByGroup']['high'] == \
        baseline['sampledByGroup']['high']
    assert comparison['identityReadsEqual'] is True
    assert comparison['enumerationsEqual'] is True
    assert comparison['membershipRowsEqualOriginal'] is True
    assert comparison['classificationTicksEqual'] is True
    assert comparison['nearOwnSampledRowsEqual'] is True
    assert candidate['ownerLookups'] <= baseline['ownerLookups']

    assert baseline['motionReasons'].get('gapOverOneSecond', 0) == 0
    assert candidate['motionReasons'].get('gapOverOneSecond', 0) > 0
    assert candidate['velocityUnknown'] > baseline['velocityUnknown']
    far_gaps = candidate['gapsByTier']['far']
    assert far_gaps['max'] > 1.0
    assert far_gaps['overOneSecondRatio'] > 0.5
    assert candidate['sampledByTier']['far'] < \
        baseline['sampledByTier']['far']
