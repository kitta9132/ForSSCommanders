"""Research tests for the test-only nearest-25 high-budget torpedo cap.

These tests exercise ``tools/torpedo_high_budget_25_candidate.py`` and
``tools/compare_torpedo_high_budget_25.py``.  They do not import or modify
production sampler constants and do not install/run anything in the game.
Private recording tests are opt-in through ``WOWS_HIGH_BUDGET_25_REPLAY=1``.
"""
from collections import Counter
import json
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
from torpedo_high_budget_25_candidate import (  # noqa: E402
    HIGH_BUDGET, CapTorpedoSamplingGroups)


class Torpedo(object):
    def __init__(self, uiId=1, ownerId=7000, shotId=1,
                 position=(0.0, 0.0, 0.0), position_error=False):
        object.__setattr__(self, '_values', {
            'uiId': uiId, 'ownerId': ownerId, 'ownerTeamId': 0,
            'ownerType': 'Ship', 'shotId': shotId, 'type': 'normal',
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

    @property
    def position_value(self):
        return self._values['position']


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
        if owner_id not in self.owners:
            self.owners[owner_id] = Owner(False)
        return self.owners[owner_id]


def adapter(rows, owners=None):
    battle = Battle(rows, owners)
    return TorpedoTelemetry(battle, SimpleNamespace()), battle


def context(width=3000.0, height=3000.0, position=(0.0, 0.0, 0.0)):
    return {'selfPosition': list(position), 'mapWidth': width,
            'mapHeight': height, 'source': 'calibratedMapExtents',
            'inferred': True}


def groups_by_id(rows):
    return dict((row['uiId'], row['sampling']) for row in rows)


def near_row(index, z=None, owner_id=None, ui_id=None):
    if z is None:
        z = 40.0 + index * 10.0
    return Torpedo(uiId=(index + 1 if ui_id is None else ui_id),
                   ownerId=(7100 + (index % 18) if owner_id is None
                            else owner_id),
                   shotId=index + 1, position=(index * 0.1, 0.0, z))


def classification_tick(telemetry, sampler, now, ctx=None,
                        self_ship_id=None):
    return telemetry.torpedoes(0, sampler, now, ctx or context(),
                               self_ship_id=self_ship_id)


def test_26_near_keeps_nearest_25_and_spills_one():
    rows = [near_row(index) for index in range(26)]
    telemetry, battle = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()

    first, status = classification_tick(telemetry, sampler, 0.0, ctx)
    assert len(first) == 26
    assert all(row['sampling']['group'] == 'high' for row in first)
    assert status['sampling']['classification']['newCount'] == 26

    second, status = classification_tick(telemetry, sampler, 5.0, ctx)
    groups = groups_by_id(second)
    classification = status['sampling']['classification']
    assert classification['nearCount'] == 26
    assert classification['highBudgetLimit'] == HIGH_BUDGET == 25
    assert classification['highBudgetEligibleCount'] == 26
    assert classification['highBudgetSelectedCount'] == 25
    assert classification['highBudgetSpillCount'] == 1
    # Nearest 25 by distance stay high, the farthest distance spills.
    assert groups[26]['group'] == 'low'
    assert all(groups[index]['group'] == 'high' for index in range(1, 26))
    assert groups[26]['distanceStatus'] == 'near'
    farthest = near_row(24).position_value
    farthest_squared = farthest[0] ** 2 + farthest[2] ** 2
    assert classification['highBudgetFarthestSelectedDistanceSquared'] == \
        pytest.approx(farthest_squared)
    assert classification['highBudgetFarthestSelectedWorldRatio'] == \
        pytest.approx(farthest_squared ** 0.5 / 3000.0)
    membership_groups = dict(
        (item['uiId'], item['group']) for item in status['membership'])
    assert membership_groups[26] == 'low'
    assert sum(1 for value in membership_groups.values()
               if value == 'high') == 25
    assert battle.collection_calls == 2


def test_equal_distance_ties_keep_enumeration_order_without_id_compare():
    # Mixed int/str uiIds are type-exact valid keys but not mutually sortable.
    rows = []
    for index in range(26):
        ui_id = ('id-%02d' % index) if index % 2 else (100 + index)
        rows.append(Torpedo(uiId=ui_id, ownerId=7100 + index % 18,
                            shotId=index + 1, position=(0.0, 0.0, 200.0)))
    telemetry, _ = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    # Must not raise on incomparable IDs; stable order selects the first 25.
    second, status = classification_tick(telemetry, sampler, 5.0, ctx)
    groups = groups_by_id(second)
    ids = [row['uiId'] for row in second]
    assert [groups[ui_id]['group'] for ui_id in ids[:25]] == ['high'] * 25
    assert groups[ids[25]]['group'] == 'low'
    assert status['sampling']['classification']['highBudgetSpillCount'] == 1


def test_own_is_high_at_every_distance_and_not_counted_in_the_budget():
    rows = [near_row(index) for index in range(26)]
    owners = {7200: Owner(True)}
    rows.append(Torpedo(uiId=900, ownerId=7200, shotId=900,
                        position=(0.0, 0.0, 100.0)))       # own near
    rows.append(Torpedo(uiId=901, ownerId=7200, shotId=901,
                        position=(0.0, 0.0, 2000.0)))      # own far
    rows.append(Torpedo(uiId=902, ownerId=7200, shotId=902,
                        position=(0.0, 0.0, 1500.0)))      # own far
    telemetry, _ = adapter(rows, owners)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx,
                        self_ship_id=7200)
    second, status = classification_tick(telemetry, sampler, 5.0, ctx,
                                         self_ship_id=7200)
    groups = groups_by_id(second)
    classification = status['sampling']['classification']
    # 5 own rows are high but excluded from the 25 slot budget.
    assert classification['highBudgetOwnCount'] == 3
    assert classification['highBudgetOwnNearCount'] == 1
    assert classification['highBudgetEligibleCount'] == 26
    assert classification['highBudgetSelectedCount'] == 25
    assert classification['highBudgetSpillCount'] == 1
    assert groups[900]['group'] == 'high'
    assert groups[901]['group'] == 'high'
    assert groups[902]['group'] == 'high'
    assert groups[901]['distanceStatus'] == 'far'
    assert groups[26]['group'] == 'low'
    high_rows = [row for row in second if row['sampling']['group'] == 'high']
    assert len(high_rows) == 28  # 25 capped + 3 own
    assert sum(1 for row in second
               if row['sampling']['distanceStatus'] == 'near') == 27


def test_boundary_is_inclusive_and_only_the_overflow_spills():
    rows = [near_row(index, z=40.0 + index * 5.0) for index in range(25)]
    rows.append(Torpedo(uiId=300, ownerId=7100, shotId=300,
                        position=(0.0, 0.0, 600.0)))       # exactly L/5
    rows.append(Torpedo(uiId=301, ownerId=7100, shotId=301,
                        position=(0.0, 0.0, 600.0001)))    # just outside
    telemetry, _ = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    second, status = classification_tick(telemetry, sampler, 5.0, ctx)
    groups = groups_by_id(second)
    classification = status['sampling']['classification']
    assert classification['nearCount'] == 26          # boundary inclusive
    assert classification['farCount'] == 1
    assert groups[300]['distanceStatus'] == 'near'
    assert groups[300]['group'] == 'low'              # farthest near spills
    assert groups[301]['distanceStatus'] == 'far'
    assert groups[301]['group'] == 'low'
    assert classification['highBudgetSpillCount'] == 1


def test_disappearance_frees_a_slot_at_the_next_classification_only():
    rows = [near_row(index) for index in range(26)]
    telemetry, battle = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    second, status = classification_tick(telemetry, sampler, 5.0, ctx)
    assert groups_by_id(second)[26]['group'] == 'low'

    # Closest row disappears.  Before the next classification the spilled row
    # stays low; it may only be re-selected at the next 5 second tick.
    battle.rows = rows[1:]
    before, status = classification_tick(telemetry, sampler, 5.2, ctx)
    assert 26 not in groups_by_id(before)
    assert status['sampling']['classificationDue'] is False

    reclassified, status = classification_tick(telemetry, sampler, 10.0, ctx)
    groups = groups_by_id(reclassified)
    assert groups[26]['group'] == 'high'
    assert status['sampling']['classification']['highBudgetSpillCount'] == 0
    assert status['sampling']['classification']['highBudgetSelectedCount'] == 25


def test_new_unknown_distance_identity_and_duplicate_are_cap_exempt():
    rows = [near_row(index) for index in range(26)]
    telemetry, battle = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)

    # 26 known rows plus a brand new near row between classifications.
    new_row = Torpedo(uiId=500, ownerId=7100, shotId=500,
                      position=(0.0, 0.0, 300.0))
    unknown_distance = Torpedo(uiId=501, ownerId=7100, shotId=501,
                               position=None)
    unknown_identity = Torpedo(uiId=None, ownerId=7100, shotId=502,
                               position=(0.0, 0.0, 350.0))
    battle.rows = rows + [new_row, unknown_distance, unknown_identity]
    out, status = classification_tick(telemetry, sampler, 0.2, ctx)
    groups = groups_by_id(out)
    assert groups[500]['group'] == 'high'
    assert groups[500]['reason'] == 'new'
    assert groups[500]['provisional'] is True
    assert out[-2]['sampling']['group'] == 'high'
    assert out[-2]['sampling']['distanceStatus'] == 'notClassified'
    assert out[-1]['sampling']['group'] == 'high'
    assert out[-1]['sampling']['identityStatus'] == 'unknown'
    assert status['membershipComplete'] is False

    # On the next classification the new row joins the budget; unknown
    # identity and unknown distance stay high outside it.  A duplicated
    # identity marks both of its occurrences, so it does not compete.
    duplicate = Torpedo(uiId=1, ownerId=7100, shotId=1,
                        position=(0.0, 0.0, 100.0))
    battle.rows = rows + [new_row, unknown_distance, unknown_identity,
                          duplicate]
    out, status = classification_tick(telemetry, sampler, 5.0, ctx)
    classification = status['sampling']['classification']
    assert classification['newCount'] == 0
    assert classification['unknownDistanceCount'] >= 1
    assert status['sampling']['duplicateIdentityCount'] >= 1
    assert all(row['sampling']['group'] == 'high'
               for row in out if row['sampling'].get('identityStatus')
               in ('unknown', 'duplicate'))
    # 25 available near rows (the duplicated one drops out) plus the newly
    # eligible 26th compete for the 25 slots.
    assert classification['highBudgetEligibleCount'] == 26
    assert classification['highBudgetSpillCount'] == 1


def test_context_loss_and_recovery_do_not_drop_the_cap_spill():
    rows = [near_row(index) for index in range(26)]
    telemetry, _ = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    second, status = classification_tick(telemetry, sampler, 5.0, ctx)
    assert groups_by_id(second)[26]['group'] == 'low'

    lost, status = telemetry.torpedoes(0, sampler, 5.2, None)
    assert len(lost) == 26
    assert all(row['sampling']['group'] == 'high' for row in lost)
    assert all(row['sampling']['distanceStatus'] == 'unknown' for row in lost)
    assert status['sampling']['safetyHigh'] is True
    assert status['sampling']['promotedCount'] == 1

    # A valid context does not silently re-apply the cap before the next
    # scheduled classification.
    recovered, status = classification_tick(telemetry, sampler, 5.4, ctx)
    assert all(row['sampling']['group'] == 'high' for row in recovered)
    reclassified, status = classification_tick(telemetry, sampler, 10.0, ctx)
    assert groups_by_id(reclassified)[26]['group'] == 'low'


def test_clear_and_clock_rollback_reset_cap_state():
    rows = [near_row(index) for index in range(26)]
    telemetry, _ = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    second, _ = classification_tick(telemetry, sampler, 5.0, ctx)
    assert groups_by_id(second)[26]['group'] == 'low'

    sampler.clear()
    out, status = classification_tick(telemetry, sampler, 5.1, ctx)
    assert all(row['sampling']['group'] == 'high' for row in out)
    assert status['sampling']['classification']['newCount'] == 26
    assert status['sampling']['classification']['highBudgetSpillCount'] == 0

    classification_tick(telemetry, sampler, 10.0, ctx)
    rolled, status = classification_tick(telemetry, sampler, 9.9, ctx)
    assert all(row['sampling']['group'] == 'high' for row in rolled)
    assert status['sampling']['classification']['clockReset'] is True
    assert status['sampling']['classification']['newCount'] == 26


def test_self_movement_changes_the_cap_geometry_only_on_reclassification():
    rows = [near_row(index, z=40.0 + index * 8.0) for index in range(26)]
    telemetry, _ = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    classification_tick(telemetry, sampler, 0.0, context())
    second, _ = classification_tick(telemetry, sampler, 5.0, context())
    assert groups_by_id(second)[26]['group'] == 'low'

    # Move self away so the old near set is now outside L/5.  Between
    # classifications the stored groups do not change.
    moved = context(position=(0.0, 0.0, 2600.0))
    between, status = classification_tick(telemetry, sampler, 5.2, moved)
    assert status['sampling']['classificationDue'] is False
    assert groups_by_id(between)[1]['group'] == 'high'
    # The spilled low row is not due at 5.2, so it is absent from the sampled
    # rows; its stored group is still visible on the membership list.
    between_groups = dict((item['uiId'], item['group'])
                          for item in status['membership'])
    assert between_groups[26] == 'low'

    reclassified, status = classification_tick(telemetry, sampler, 10.0, moved)
    classification = status['sampling']['classification']
    groups = groups_by_id(reclassified)
    assert classification['nearCount'] == 0
    # Everything is far now: even previously-high rows become low.
    assert all(sample['group'] == 'low' for sample in groups.values())
    assert classification['highBudgetEligibleCount'] == 0
    assert classification['highBudgetSelectedCount'] == 0


def test_far_non_due_reads_no_position_collection_once_and_own_promotion():
    near = Torpedo(uiId=1, ownerId=7300, shotId=1,
                   position=(0.0, 0.0, 300.0))
    far = Torpedo(uiId=2, ownerId=7301, shotId=2,
                  position=(0.0, 0.0, 2000.0))
    owners = {7300: Owner(False), 7301: Owner(False)}
    telemetry, battle = adapter([near, far], owners)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    # Start with the near row as the self ship so the far row is a confirmed
    # ally low; then change self to the far owner to verify promotion on the
    # row's own low due tick, not by scanning non-due rows.
    classification_tick(telemetry, sampler, 0.0, ctx,
                        self_ship_id=7300)
    classification_tick(telemetry, sampler, 5.0, ctx,
                        self_ship_id=7300)
    assert battle.collection_calls == 2

    near.reads.clear()
    far.reads.clear()
    battle.owner_calls.clear()
    out, status = classification_tick(telemetry, sampler, 5.2, ctx,
                                      self_ship_id=7300)
    assert battle.collection_calls == 3
    assert [row['uiId'] for row in out] == [1]
    assert near.reads['position'] == 1
    assert far.reads['position'] == 0          # far low not due: no read
    assert battle.owner_calls[7300] == 1
    assert battle.owner_calls[7301] == 0
    assert status['sampling']['low']['status'] == 'notSampled'

    # The far owner is now the strict self ship.
    far.reads.clear()
    battle.owner_calls.clear()
    out, _ = classification_tick(telemetry, sampler, 5.4, ctx,
                                 self_ship_id=7300)
    assert [row['uiId'] for row in out] == [1]
    assert far.reads['position'] == 0
    out, _ = classification_tick(telemetry, sampler, 5.6, ctx,
                                 self_ship_id=7301)
    groups = groups_by_id(out)
    assert groups[2]['group'] == 'high'
    assert groups[2]['reason'] == 'highDue'
    assert far.reads['position'] == 1
    assert battle.owner_calls[7301] == 1


def test_owner_lookup_is_cached_once_per_snapshot():
    rows = [Torpedo(uiId=index, ownerId=7400, shotId=index,
                    position=(0.0, 0.0, 300.0)) for index in range(1, 4)]
    telemetry, battle = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    assert battle.owner_calls[7400] == 1
    classification_tick(telemetry, sampler, 5.0, ctx)
    assert battle.owner_calls[7400] == 2
    battle.owner_calls.clear()
    classification_tick(telemetry, sampler, 5.2, ctx)
    assert battle.owner_calls[7400] == 1


def test_production_wire_stays_high_low_and_cap_metadata_is_not_wire():
    rows = [near_row(index) for index in range(26)]
    telemetry, _ = adapter(rows)
    sampler = CapTorpedoSamplingGroups()
    ctx = context()
    classification_tick(telemetry, sampler, 0.0, ctx)
    out, status = classification_tick(telemetry, sampler, 5.0, ctx)
    # Adapter-local summary carries the research cap metadata.
    assert status['sampling']['classification']['highBudgetLimit'] == 25
    wire_rows, wire = sampling_wire_payload(out, status)
    assert set(wire['sampling'].keys()) == {
        'status', 'classification', 'high', 'low', 'safetyHigh',
        'unmatchableIdentityCount', 'duplicateIdentityCount'}
    assert 'mid' not in wire['sampling']
    assert 'highBudgetLimit' not in wire['sampling']['classification']
    assert [row['sampling']['group'] for row in wire_rows].count('low') == 1
    assert all(set(row['sampling']).issubset(
        {'group', 'sampleTs', 'provisional', 'identityStatus',
         'positionStatus'}) for row in wire_rows)
    # The wire remains JSON-safe and carries no private identifiers beyond
    # the existing identity membership contract.
    json.dumps({'rows': wire_rows, 'status': wire}, allow_nan=False)


def test_synthetic_216_torpedoes_22_owners_includes_own_and_host_cost():
    import compare_torpedo_high_budget_25
    result = compare_torpedo_high_budget_25.synthetic_benchmark(
        repeats=1, ticks=60)
    assert result['hostOnly'] is True
    assert set(result['variants'].keys()) == {'allNear', 'halfNear', 'ownMixed'}
    all_near = result['variants']['allNear']
    half_near = result['variants']['halfNear']
    own_mixed = result['variants']['ownMixed']
    for variant in (all_near, half_near, own_mixed):
        assert variant['rows'] == 216 and variant['owners'] == 22
        assert variant['baseline']['enumerations'] == 60
        assert variant['candidate']['enumerations'] == 60
        assert variant['baseline']['identityReads'] == \
            variant['candidate']['identityReads']
        assert variant['candidate']['sampledRows'] < \
            variant['baseline']['sampledRows']
        assert variant['candidate']['positionReads'] == \
            variant['candidate']['sampledRows']
        assert sum(variant['candidate']['sampledByGroup'].values()) == \
            variant['candidate']['sampledRows']
        assert variant['candidate']['sampledByGroup']['high'] > 0
        assert variant['candidate']['sampledByGroup']['low'] > 0
        assert variant['candidate']['medianTickMs'] > 0
        assert variant['baseline']['medianTickMs'] > 0
    # Own rows are always high and are not part of the 25 slot budget.
    assert own_mixed['ownRows'] == 54
    assert own_mixed['candidate']['sampledByGroup']['high'] > \
        all_near['candidate']['sampledByGroup']['high']


def _unsampled_state(ts, battle_id, rows, self_position=(0.0, 0.0, 0.0)):
    return {
        'kind': 'state',
        'data': {
            'active': True,
            'battleId': battle_id,
            'ts': ts,
            'self': {'isObserver': False, 'isObserverKnown': True,
                     'teamId': 0, 'position': list(self_position)},
            'diag': {'mapCalibration': {
                'status': 'available',
                'coefficients': {
                    'worldX': {'mapAxis': 'nx', 'scale': 3000.0},
                    'worldZ': {'mapAxis': 'ny', 'scale': 3000.0}}}},
            'torpedoes': rows,
        },
    }


def test_replay_tool_reports_mimo_extra_metrics(tmp_path):
    import compare_torpedo_high_budget_25 as tool

    def near_position(index):
        return [index * 0.1, 0.0, 40.0 + index * 10.0]

    rows = [{'uiId': index + 1, 'ownerId': 7100, 'shotId': index + 1,
             'position': near_position(index)} for index in range(26)]
    first = _unsampled_state(0.0, 'battle-x', rows)
    second = _unsampled_state(5.0, 'battle-x', rows)
    # Swap the nearest and farthest rows so exactly two groups flip between the
    # second and third classification ticks.
    swapped = [dict(row) for row in rows]
    swapped[0]['position'] = near_position(25)
    swapped[25]['position'] = near_position(0)
    third = _unsampled_state(10.0, 'battle-x', swapped)
    path = tmp_path / 'mini.jsonl'
    with open(path, 'w', encoding='utf-8') as stream:
        for event in (first, second, third):
            stream.write(json.dumps(event) + '\n')

    result = tool.replay_recording(str(path), compute_bytes=False)
    candidate = result['candidate']
    comparison = result['comparison']
    assert candidate['classificationTicks'] == 3
    # All 26 rows share one owner, so a full 25 slot budget is one owner.
    assert candidate['top25SameOwnerMax'] == 25
    # First tick is all-new safety high (26), which is the cap exception peak.
    assert candidate['classificationHighMax'] == 26
    assert candidate['exceptionHighTotal'] >= 26
    assert candidate['exceptionHighMax'] >= 26
    # Tick 2 spills one row low/high, tick 3 flips one high->low and one
    # low->high: at least three flips in total.
    assert candidate['highLowFlips'] >= 3
    assert comparison['top25SameOwnerMaxCandidate'] == 25
    assert comparison['classificationHighMaxCandidate'] == 26
    assert comparison['exceptionHighMaxCandidate'] >= 26


B43_EXPECTED = {
    'states': 1194, 'originalRows': 95413, 'sampledRows': 73711,
    'sampled.high': 59145, 'sampled.low': 14566,
    'ownerLookups': 11371, 'classificationTicks': 48}
B44_EXPECTED = {
    'states': 743, 'originalRows': 9671, 'sampledRows': 6044,
    'sampled.high': 3640, 'sampled.low': 2404,
    'ownerLookups': 1391, 'classificationTicks': 30}


@pytest.mark.skipif(
    os.environ.get('WOWS_HIGH_BUDGET_25_REPLAY') != '1',
    reason='set WOWS_HIGH_BUDGET_25_REPLAY=1 to replay private recordings')
@pytest.mark.parametrize('name,expected', [
    ('without-atm-b43.jsonl', B43_EXPECTED),
    ('without-atm-b44.jsonl', B44_EXPECTED)])
def test_private_baseline_replay_and_cap_invariants(name, expected):
    import compare_torpedo_high_budget_25
    path = os.path.join(_ROOT, 'recordings', name)
    if not os.path.exists(path):
        pytest.skip('private recording is not available')
    result = compare_torpedo_high_budget_25.replay_recording(
        path, compute_bytes=False)
    baseline = result['baseline']
    candidate = result['candidate']
    comparison = result['comparison']
    assert baseline['states'] == expected['states']
    assert baseline['originalRows'] == expected['originalRows']
    assert baseline['sampledRows'] == expected['sampledRows']
    assert baseline['sampledByGroup']['high'] == expected['sampled.high']
    assert baseline['sampledByGroup']['low'] == expected['sampled.low']
    assert baseline['ownerLookups'] == expected['ownerLookups']
    assert baseline['classificationTicks'] == expected['classificationTicks']

    assert candidate['states'] == expected['states']
    assert candidate['originalRows'] == expected['originalRows']
    assert candidate['sampledRows'] <= baseline['sampledRows']
    assert candidate['positionReads'] == candidate['sampledRows']
    assert sum(candidate['sampledByGroup'].values()) == \
        candidate['sampledRows']
    assert comparison['identityReadsEqual'] is True
    assert comparison['enumerationsEqual'] is True
    assert comparison['membershipRowsEqualOriginal'] is True
    assert comparison['membershipIdentitiesEqual'] is True
    assert comparison['classificationTicksEqual'] is True
    # The cap keeps the same average 2 Hz low cadence, so it does not lose
    # velocity the way the far 1 Hz candidate did.
    assert candidate['dtOverOneSecond'] == 0
    assert candidate['velocityUnknown'] == baseline['velocityUnknown']
    assert candidate['ownerLookups'] <= baseline['ownerLookups']

    if name.startswith('without-atm-b43'):
        assert candidate['capCounters']['ticksNearOver25'] > 0
        assert candidate['capCounters']['spillTotal'] > 0
        assert candidate['sampledRows'] < baseline['sampledRows']
        assert candidate['nearLowSampledRows'] > 0
        assert candidate['top25SameOwnerMax'] <= HIGH_BUDGET
        assert candidate['exceptionHighMax'] >= candidate['top25SameOwnerMax']
        assert candidate['classificationHighMax'] >= HIGH_BUDGET
    else:
        # B44 never exceeds 25 in-range non-own rows per classification tick.
        assert candidate['capCounters']['spillTotal'] == 0
        assert candidate['sampledRows'] == baseline['sampledRows']