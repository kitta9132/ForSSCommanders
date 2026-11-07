"""Offline three-tier far-torpedo cadence research (test-only, no runtime edit).

Baseline is the current production sampler (L/5 high 5 Hz, L/5 far average
2 Hz).  The candidate is the research-only three-tier sampler in
``far_torpedo_1hz_candidate`` (L/5 high, L/5..L/3 mid 2 Hz, >L/3 far 1 Hz).

The tool replays unsampled B43/B44 records with the real producer adapter,
the real ``TorpedoMotion`` class and the current wire compaction.  It also
reports a static B09 classification-tick geometry estimate.  B09 is already
sampled, so it cannot reconstruct all non-classification positions; the B09
part is explicitly a static geometry projection, not a replay.

No private recording paths, battle ids, owner ids, vehicle ids or weapon ids
are printed.  Output is aggregate only.  Host Python 3 timing must not be
converted to game time or FPS.
"""
import argparse
from collections import Counter, OrderedDict, defaultdict
import json
import os
import statistics
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_SOURCE = os.path.join(os.path.dirname(_HERE), 'res_mods', 'PnFMods',
                       'WowsExtractor')
for _path in (_HERE, _SOURCE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from torpedo_telemetry import (  # noqa: E402
    TorpedoMotion, LegacyTorpedoSamplingGroups as TorpedoSamplingGroups,
    TorpedoTelemetry, sampling_wire_payload)
from far_torpedo_1hz_candidate import (  # noqa: E402
    SAMPLING_MID, TieredTorpedoSamplingGroups,
    tier_distance, tiered_sampling_wire_payload)


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                          allow_nan=False).encode('utf-8'))


def identity(row):
    return tuple((type(row.get(name)).__name__, row.get(name))
                 for name in ('uiId', 'ownerId', 'shotId'))


def context(state):
    own = state.get('self') or {}
    fit = state.get('diag', {}).get('mapCalibration', {})
    if own.get('isObserver') is not False or fit.get('status') != 'available':
        return None
    try:
        coeff = fit['coefficients']
        x, z = coeff['worldX'], coeff['worldZ']
        if (x.get('mapAxis') not in ('nx', 'ny') or
                z.get('mapAxis') not in ('nx', 'ny') or
                x.get('mapAxis') == z.get('mapAxis') or
                isinstance(x.get('scale'), bool) or
                isinstance(z.get('scale'), bool)):
            return None
        width = abs(float(coeff['worldX']['scale']))
        height = abs(float(coeff['worldZ']['scale']))
        pos = own['position']
        if (len(pos) != 3 or
                not all(-1e9 < value < 1e9 for value in pos) or
                not 0 < width < 1e9 or not 0 < height < 1e9):
            return None
        return {'selfPosition': pos, 'mapWidth': width, 'mapHeight': height,
                'source': 'calibratedMapExtents', 'inferred': True}
    except (KeyError, TypeError, ValueError):
        return None


class RecordedTorpedo(object):
    def __init__(self, row, counts):
        self.row = row
        self.counts = counts

    def __getattr__(self, name):
        self.counts['field.' + name] += 1
        return self.row.get(name)


class RecordedBattle(object):
    def __init__(self):
        self.rows = []
        self.owners = {}
        self.counts = Counter()

    def set_rows(self, rows):
        self.rows = [RecordedTorpedo(row, self.counts) for row in rows]
        self.owners = dict((row.get('ownerId'), row.get('owner'))
                           for row in rows)

    def getAllTorpedoes(self):
        self.counts['collection'] += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.counts['owner'] += 1
        return self.owners.get(owner_id)


def _gap_stats(values):
    if not values:
        return {'count': 0, 'median': None, 'max': None,
                'overOneSecond': 0, 'overOneSecondRatio': None}
    ordered = sorted(values)
    over = sum(1 for value in values if value > 1.0)
    return {'count': len(values),
            'median': statistics.median(values),
            'max': max(values),
            'overOneSecond': over,
            'overOneSecondRatio': over / float(len(values))}


class VariantReplay(object):
    def __init__(self, name, sampler, wire):
        self.name = name
        self.sampler = sampler
        self.wire = wire
        self.battle = RecordedBattle()
        self.adapter = TorpedoTelemetry(self.battle, None)
        self.motion = TorpedoMotion()
        self.counts = Counter()
        self.motion_reasons = Counter()
        self.motion_by_tier = Counter()
        self.sampled_by_group = Counter()
        self.sampled_by_tier = Counter()
        self.gaps_by_tier = defaultdict(list)
        self.last_sample = {}
        self.sample_count = defaultdict(int)
        self.near_own_samples = 0
        self.class_ts = []
        self.class_counters = Counter()
        self._last_classification_ts = None

    def tick(self, team, now, classification_context, original,
             update_tiers=False, self_ship_id=None):
        rows, status = self.adapter.torpedoes(
            team, sampling=self.sampler, now=now,
            context=classification_context, self_ship_id=self_ship_id)
        if status.get('available') is not True:
            self.counts['unavailableStates'] += 1
        summary = status.get('sampling') or {}
        classification = summary.get('classification') or {}
        class_ts = classification.get('ts')
        is_classification = (class_ts is not None and
                             abs(class_ts - now) <= 1e-6)
        counters = summary.get('counters') or {}
        for name in ('enumerations', 'identityReads', 'positionReads',
                     'ownerLookups'):
            self.counts[name] += counters.get(name, 0)
        if is_classification:
            self.class_ts.append(now)
            for name in ('nearCount', 'midCount', 'farCount',
                         'unknownDistanceCount', 'newCount',
                         'groupChangeCount', 'provisionalHighCount',
                         'prunedCount', 'classifiedCount'):
                self.class_counters[name] += classification.get(name, 0) or 0
            if update_tiers:
                self.update_classification_tiers(rows)
        membership = (status.get('membership')
                      if status.get('membershipComplete') is True else [])
        self.motion.update(rows, now, status.get('available', False),
                           membership=membership)
        for row in rows:
            key = identity(row)
            sample = row.get('sampling') or {}
            group = sample.get('group')
            tier = self.tier_for(key)
            self.counts['sampledRows'] += 1
            self.sampled_by_group[group] += 1
            self.sampled_by_tier[tier] += 1
            motion = row.get('motion') or {}
            previous = self.last_sample.get(key)
            if motion.get('available') is True:
                self.motion_by_tier[(tier, 'available')] += 1
            else:
                reason = self._motion_reason(
                    row, sample, now, previous, status)
                self.motion_reasons[reason] += 1
                self.motion_by_tier[(tier, reason)] += 1
                self.counts['velocityUnknown'] += 1
            if previous is not None:
                self.gaps_by_tier[tier].append(now - previous[0])
            self.last_sample[key] = (now, row.get('position'), identity(row))
            self.sample_count[key] += 1
            if self.is_near_or_own(key, row):
                self.near_own_samples += 1
        wire_rows, wire_status = self.wire(rows, status)
        return wire_rows, wire_status

    def _motion_reason(self, row, sample, now, previous, status):
        if row.get('position') is None:
            return 'positionUnknown'
        if sample.get('identityStatus') not in (None, 'available'):
            return 'identityUnavailable'
        if previous is None:
            return 'firstObservation'
        if status.get('membershipComplete') is not True:
            return 'membershipIncomplete'
        delta = now - previous[0]
        if delta <= 0:
            return 'nonIncreasingTime'
        if delta > 1.0:
            return 'gapOverOneSecond'
        if previous[1] is None:
            return 'previousPositionUnknown'
        if previous[2] != identity(row):
            return 'identityChanged'
        return 'motionUnavailableOther'

    def update_classification_tiers(self, rows):
        for row in rows:
            key = identity(row)
            sample = row.get('sampling') or {}
            status = sample.get('distanceStatus')
            if status:
                self._tiers[key] = status
            if row.get('isOwn') is True:
                self._own[key] = True

    @property
    def _tiers(self):
        value = getattr(self, '_tier_values', None)
        if value is None:
            value = {}
            self._tier_values = value
        return value

    @property
    def _own(self):
        value = getattr(self, '_own_values', None)
        if value is None:
            value = {}
            self._own_values = value
        return value

    def tier_for(self, key):
        return self._tiers.get(key, 'unknown')

    def is_near_or_own(self, key, row):
        return self.tier_for(key) == 'near' or self._own.get(key) is True

    def result(self, original_compact_bytes, projected_compact_bytes,
               states):
        return {
            'states': states,
            'classificationTicks': len(self.class_ts),
            'classificationCounters': dict(self.class_counters),
            'sampledRows': self.counts['sampledRows'],
            'sampledByGroup': dict(self.sampled_by_group),
            'sampledByTier': dict(self.sampled_by_tier),
            'nearOwnSampledRows': self.near_own_samples,
            'positionReads': self.counts['positionReads'],
            'ownerLookups': self.counts['ownerLookups'],
            'identityReads': self.counts['identityReads'],
            'enumerations': self.counts['enumerations'],
            'unavailableStates': self.counts['unavailableStates'],
            'velocityUnknown': self.counts['velocityUnknown'],
            'velocityAvailable': sum(
                value for (tier, key), value in self.motion_by_tier.items()
                if key == 'available'),
            'motionReasons': dict(self.motion_reasons),
            'motionByTier': dict(('%s.%s' % key, value)
                                 for key, value in self.motion_by_tier.items()),
            'gapsByTier': dict((tier, _gap_stats(values))
                               for tier, values in self.gaps_by_tier.items()),
            'apiFieldReads': dict(self.battle.counts),
            'originalCompactBytes': original_compact_bytes,
            'projectedCompactBytes': projected_compact_bytes,
        }


def replay_recording(path, compute_bytes=True):
    baseline = VariantReplay('baseline', TorpedoSamplingGroups(),
                             sampling_wire_payload)
    candidate = VariantReplay('candidate', TieredTorpedoSamplingGroups(),
                              tiered_sampling_wire_payload)
    states = 0
    original_rows = 0
    original_owner_budget = 0
    membership_rows = 0
    incomplete_membership_states = 0
    original_bytes = 0
    baseline_bytes = 0
    candidate_bytes = 0
    previous_battle = object()
    with open(path, encoding='utf-8-sig') as stream:
        for line in stream:
            event = json.loads(line)
            if event.get('kind') != 'state':
                continue
            state = event.get('data', {})
            if state.get('active') is not True:
                continue
            if state.get('battleId') != previous_battle:
                baseline.sampler.clear()
                candidate.sampler.clear()
                baseline.motion.clear()
                candidate.motion.clear()
                baseline._tier_values = {}
                candidate._tier_values = {}
                baseline._own_values = {}
                candidate._own_values = {}
                previous_battle = state.get('battleId')
            original = state.get('torpedoes') or []
            if (state.get('torpedoStatus') or {}).get('sampling') is not None:
                raise ValueError(
                    'Already-sampled recording cannot provide all per-tick '
                    'positions; use an unsampled baseline or the B09 static '
                    'classification-tick estimate.')
            if compute_bytes:
                original_bytes += encoded_size(state)
            classification_context = context(state)
            self_state = state.get('self') or {}
            team = self_state.get('teamId')
            self_ship_id = self_state.get('shipId')
            states += 1
            original_rows += len(original)
            original_owner_budget += len(set(
                (type(row.get('ownerId')).__name__, row.get('ownerId'))
                for row in original if row.get('ownerId') is not None))
            baseline.battle.set_rows(original)
            candidate.battle.set_rows(original)
            # Candidate first so its classification tier labels are available
            # to the baseline sample rows in the same tick.
            candidate_rows, candidate_status = candidate.tick(
                team, state['ts'], classification_context, original,
                update_tiers=True, self_ship_id=self_ship_id)
            candidate_class_ts = (candidate_status.get('sampling', {})
                                  .get('classification', {}).get('ts'))
            if (candidate_class_ts is not None and
                    abs(candidate_class_ts - state['ts']) <= 1e-6):
                baseline._tier_values = dict(candidate._tier_values)
                baseline._own_values = dict(candidate._own_values)
            baseline_rows, baseline_status = baseline.tick(
                team, state['ts'], classification_context, original,
                self_ship_id=self_ship_id)
            membership_rows += len(candidate_status.get('membership') or [])
            incomplete_membership_states += (
                candidate_status.get('membershipComplete') is not True)
            if compute_bytes:
                index = dict((identity(row), row) for row in original)
                for variant, rows, status in (
                        (baseline, baseline_rows, baseline_status),
                        (candidate, candidate_rows, candidate_status)):
                    projected = []
                    for row in rows:
                        value = dict(index.get(identity(row), row))
                        value['sampling'] = row.get('sampling')
                        projected.append(value)
                    total = encoded_size(dict(
                        state, torpedoes=projected,
                        torpedoStatus=status))
                    if variant is baseline:
                        baseline_bytes += total
                    else:
                        candidate_bytes += total
    common = {
        'states': states,
        'originalRows': original_rows,
        'membershipRows': membership_rows,
        'incompleteMembershipStates': incomplete_membership_states,
        'originalOwnerBudget': original_owner_budget,
    }
    baseline_result = baseline.result(
        original_bytes if compute_bytes else None,
        baseline_bytes if compute_bytes else None, states)
    candidate_result = candidate.result(
        original_bytes if compute_bytes else None,
        candidate_bytes if compute_bytes else None, states)
    for result in (baseline_result, candidate_result):
        result.update(common)
    comparison = {
        'sampledRowsCandidateMinusBaseline': (
            candidate_result['sampledRows'] - baseline_result['sampledRows']),
        'positionReadsCandidateMinusBaseline': (
            candidate_result['positionReads'] -
            baseline_result['positionReads']),
        'ownerLookupsCandidateMinusBaseline': (
            candidate_result['ownerLookups'] -
            baseline_result['ownerLookups']),
        'identityReadsEqual': (
            candidate_result['identityReads'] ==
            baseline_result['identityReads']),
        'enumerationsEqual': (
            candidate_result['enumerations'] ==
            baseline_result['enumerations']),
        'membershipRowsEqualOriginal': membership_rows == original_rows,
        'classificationTicksEqual': (
            candidate_result['classificationTicks'] ==
            baseline_result['classificationTicks']),
        'nearOwnSampledRowsEqual': (
            candidate_result['nearOwnSampledRows'] ==
            baseline_result['nearOwnSampledRows']),
        'candidateSampledByGroupSum': sum(
            candidate_result['sampledByGroup'].values()),
    }
    return {'baseline': baseline_result, 'candidate': candidate_result,
            'comparison': comparison}


def _b09_extent(state, classification):
    fit = (state.get('diag') or {}).get('mapCalibration') or {}
    if fit.get('status') == 'available':
        try:
            coeff = fit['coefficients']
            width = abs(float(coeff['worldX']['scale']))
            height = abs(float(coeff['worldZ']['scale']))
            if 0 < width < 1e9 and 0 < height < 1e9:
                return width, height, 'diag'
        except (KeyError, TypeError, ValueError):
            pass
    radius = classification.get('radiusWorld')
    try:
        if radius is not None and 0 < float(radius) < 1e9:
            # B09 was recorded with the 0.3.38 L/3 radius.
            return float(radius) * 3.0, float(radius) * 3.0, 'radius*3'
    except (TypeError, ValueError):
        pass
    return None


def b09_static(path):
    sessions = OrderedDict()
    with open(path, encoding='utf-8-sig') as stream:
        for line in stream:
            event = json.loads(line)
            if event.get('kind') != 'state':
                continue
            state = event.get('data', {})
            if state.get('active') is not True:
                continue
            battle = state.get('battleId')
            item = sessions.setdefault(battle, {
                'states': 0, 'detailRows': 0, 'membershipRows': 0,
                'classificationTicks': 0, 'emptyClassificationTicks': 0,
                'skippedTicks': 0, 'maxClassRows': 0,
                'near': 0, 'mid': 0, 'far': 0, 'unknown': 0,
                'ownNear': 0, 'ownMid': 0, 'ownFar': 0, 'ownUnknown': 0,
                'rowsClassified': 0})
            item['states'] += 1
            rows = state.get('torpedoes') or []
            status = state.get('torpedoStatus') or {}
            item['detailRows'] += len(rows)
            item['membershipRows'] += len(status.get('membership') or [])
            classification = ((status.get('sampling') or {})
                              .get('classification') or {})
            ts = classification.get('ts')
            if ts is None or abs(ts - state.get('ts')) > 1e-6:
                continue
            item['classificationTicks'] += 1
            if not rows:
                item['emptyClassificationTicks'] += 1
                continue
            extent = _b09_extent(state, classification)
            own = state.get('self') or {}
            self_position = own.get('position')
            if (status.get('membershipComplete') is not True or
                    extent is None or own.get('isObserver') is not False or
                    self_position is None or len(self_position) != 3):
                item['skippedTicks'] += 1
                continue
            item['maxClassRows'] = max(item['maxClassRows'], len(rows))
            width, height, _source = extent
            info = {'status': 'available', 'x': self_position[0],
                    'z': self_position[2], 'width': width,
                    'height': height, 'normalized': False}
            for row in rows:
                tier, _squared = tier_distance(info, row.get('position'))
                if tier == 'near':
                    item['near'] += 1
                elif tier == 'mid':
                    item['mid'] += 1
                elif tier == 'far':
                    item['far'] += 1
                else:
                    item['unknown'] += 1
                item['rowsClassified'] += 1
                if row.get('isOwn') is True:
                    key = 'own' + tier.capitalize()
                    if key in item:
                        item[key] += 1
    result = []
    for item in sessions.values():
        if item['detailRows'] == 0:
            continue
        total = item['near'] + item['mid'] + item['far'] + item['unknown']
        item['classifiedTotal'] = total
        item['midRatioOfClassified'] = (
            item['mid'] / float(total) if total else None)
        item['farRatioOfClassified'] = (
            item['far'] / float(total) if total else None)
        result.append(item)
    return {'sessions': result,
            'note': 'B09 is already sampled; this is classification-tick '
                    'static geometry only, not a scheduler replay.'}


class SyntheticTorpedo(object):
    def __init__(self, ui_id, owner_id, shot_id, position):
        object.__setattr__(self, '_values', {
            'uiId': ui_id, 'ownerId': owner_id, 'ownerTeamId': 0,
            'ownerType': 'Ship', 'shotId': shot_id, 'type': 'normal',
            'position': position})
        object.__setattr__(self, 'reads', Counter())

    def __getattr__(self, name):
        values = object.__getattribute__(self, '_values')
        reads = object.__getattribute__(self, 'reads')
        if name in values:
            reads[name] += 1
            return values[name]
        raise AttributeError(name)


class SyntheticOwner(object):
    def __init__(self, is_player):
        self.teamId = 0
        self.isAlive = True
        self.isPlayer = is_player
        self.isBot = not is_player


class SyntheticBattle(object):
    def __init__(self, rows, owners):
        self.rows = rows
        self.owners = owners
        self.counts = Counter()

    def getAllTorpedoes(self):
        self.counts['collection'] += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.counts['owner'] += 1
        return self.owners.get(owner_id)


def synthetic_rows():
    rows = []
    owners = {}
    own_owners = set(range(7000, 7004))
    for owner_id in range(7000, 7022):
        owners[owner_id] = SyntheticOwner(owner_id in own_owners)
    shot = 0
    # 54 non-own near, 54 mid, 54 far, plus 54 own split across the tiers.
    plan = []
    for index in range(54):
        plan.append((7004 + index % 18, 'near'))
    for index in range(54):
        plan.append((7004 + index % 18, 'mid'))
    for index in range(54):
        plan.append((7004 + index % 18, 'far'))
    for index in range(54):
        plan.append((7000 + index % 4, ('near', 'mid', 'far')[index % 3]))
    for index, (owner_id, tier) in enumerate(plan):
        shot += 1
        fraction = (index % 10) / 10.0
        if tier == 'near':
            z = 100.0 + 480.0 * fraction
        elif tier == 'mid':
            z = 620.0 + 360.0 * fraction
        else:
            z = 1040.0 + 1360.0 * fraction
        rows.append(SyntheticTorpedo(10000 + index, owner_id, shot,
                                     [index * 0.1, 0.0, z]))
    return rows, owners


def _summarize_benchmark(runs):
    return {
        'medianTickMs': statistics.median(runs['tickMs']),
        'tickMs': runs['tickMs'],
        'totalMs': statistics.median(runs['totalMs']),
        'sampledRows': runs['sampledRows'],
        'positionReads': runs['positionReads'],
        'ownerLookups': runs['ownerLookups'],
        'identityReads': runs['identityReads'],
        'enumerations': runs['enumerations'],
        'sampledByGroup': dict(runs['sampledByGroup']),
        'velocityUnknown': runs['velocityUnknown'],
        'apiFieldReads': dict(runs['apiFieldReads']),
    }


def synthetic_benchmark(repeats=5, ticks=200):
    ctx = {'selfPosition': [0.0, 0.0, 0.0], 'mapWidth': 3000.0,
           'mapHeight': 3000.0, 'source': 'synthetic',
           'inferred': True}
    results = {}
    for variant, sampler_class, wire in (
            ('baseline', TorpedoSamplingGroups, sampling_wire_payload),
            ('candidate', TieredTorpedoSamplingGroups,
             tiered_sampling_wire_payload)):
        runs = {'tickMs': [], 'totalMs': [], 'sampledRows': 0,
                'positionReads': 0, 'ownerLookups': 0, 'identityReads': 0,
                'enumerations': 0, 'sampledByGroup': Counter(),
                'velocityUnknown': 0, 'apiFieldReads': Counter()}
        for _repeat in range(repeats):
            rows, owners = synthetic_rows()
            battle = SyntheticBattle(rows, owners)
            adapter = TorpedoTelemetry(battle, None)
            sampler = sampler_class()
            motion = TorpedoMotion()
            repeat_counts = Counter()
            repeat_groups = Counter()
            start = time.perf_counter()
            for index in range(ticks):
                now = index * 0.2
                sample_rows, status = adapter.torpedoes(
                    0, sampling=sampler, now=now, context=ctx,
                    self_ship_id=1)
                membership = (status.get('membership')
                              if status.get('membershipComplete') is True
                              else [])
                motion.update(sample_rows, now,
                              status.get('available', False),
                              membership=membership)
                counters = ((status.get('sampling') or {})
                            .get('counters') or {})
                for name in ('enumerations', 'identityReads',
                             'positionReads', 'ownerLookups', 'sampledRows'):
                    repeat_counts[name] += counters.get(name, 0)
                for row in sample_rows:
                    repeat_groups[(row.get('sampling') or {}).get('group')] += 1
                    if row.get('motion', {}).get('available') is not True:
                        repeat_counts['velocityUnknown'] += 1
                wire(sample_rows, status)
            elapsed = time.perf_counter() - start
            runs['tickMs'].append(elapsed / ticks * 1000.0)
            runs['totalMs'].append(elapsed * 1000.0)
            for name in ('sampledRows', 'positionReads', 'ownerLookups',
                         'identityReads', 'enumerations',
                         'velocityUnknown'):
                runs[name] += repeat_counts.get(name, 0)
            runs['sampledByGroup'].update(repeat_groups)
            runs['apiFieldReads'].update(battle.counts)
        results[variant] = _summarize_benchmark(runs)
    return {
        'rows': 216, 'owners': 22,
        'nearRows': 72, 'midRows': 72, 'farRows': 72, 'ownRows': 54,
        'repeats': repeats, 'ticks': ticks,
        'baseline': results['baseline'],
        'candidate': results['candidate'],
        'hostOnly': True,
        'note': 'Host Python 3 timing with synthetic cheap getters; not game '
                'time and not an FPS improvement rate.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', action='append', default=[],
                        help='unsampled recording to replay (B43/B44)')
    parser.add_argument('--b09', default=None,
                        help='B09 recording for static classification-tick '
                             'geometry (not a replay)')
    parser.add_argument('--synthetic', action='store_true',
                        help='run synthetic 216 torpedo / 22 owner benchmark')
    parser.add_argument('--no-bytes', action='store_true',
                        help='skip compact-byte encoding for faster replay')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--ticks', type=int, default=200)
    parser.add_argument('--json-output', default=None)
    args = parser.parse_args()
    output = {'scope': 'offline research; runtime source not modified'}
    if args.recording:
        output['recordings'] = {}
        for path in args.recording:
            name = os.path.basename(path)
            if name.startswith('without-atm-b43'):
                label = 'B43'
            elif name.startswith('without-atm-b44'):
                label = 'B44'
            else:
                label = name
            output['recordings'][label] = replay_recording(
                path, compute_bytes=not args.no_bytes)
    if args.b09:
        output['b09Static'] = b09_static(args.b09)
    if args.synthetic:
        output['synthetic'] = synthetic_benchmark(args.repeats, args.ticks)
    text = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_output:
        with open(args.json_output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
