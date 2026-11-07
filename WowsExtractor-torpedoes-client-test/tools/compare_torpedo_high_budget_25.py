"""Offline nearest-25 high-budget torpedo comparison (test-only).

Baseline is the current production sampler (``TorpedoSamplingGroups``: L/5
high 5 Hz, L/5 outside average 2 Hz).  The candidate is the research-only
``CapTorpedoSamplingGroups`` in ``torpedo_high_budget_25_candidate`` which
keeps the nearest 25 non-own in-range rows high and spills the rest to low.

The tool replays unsampled B43/B44 records with the real producer adapter,
the real ``TorpedoMotion`` and the production wire compaction.  It also
reports a static B09 classification-tick high-cap geometry.  B09 is already
sampled, so it is explicitly a static projection, not a 5 second scheduler
replay.  The synthetic 216 torpedo / 22 owner benchmark uses cheap host
getters and must not be converted to game time or FPS.

No private recording paths, battle ids, owner ids, vehicle ids or weapon ids
are printed.  Output is aggregate only.
"""
import argparse
from collections import Counter, OrderedDict
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
from torpedo_high_budget_25_candidate import (  # noqa: E402
    HIGH_BUDGET, CapTorpedoSamplingGroups)

NEAR_BUCKETS = ((0.00, 0.04), (0.04, 0.08), (0.08, 0.12),
                (0.12, 0.16), (0.16, 0.2000001))


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


def _stats(values):
    if not values:
        return {'count': 0, 'min': None, 'median': None, 'max': None}
    return {'count': len(values), 'min': min(values),
            'median': statistics.median(values), 'max': max(values)}


def _ratio_bucket(ratio):
    for low, high in NEAR_BUCKETS:
        if low - 1e-12 <= ratio < high:
            return '%0.2f-%0.2f' % (low, high)
    return 'outside'


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


def _membership_identities(membership):
    return tuple(
        (type(item.get('uiId')).__name__, item.get('uiId'),
         type(item.get('ownerId')).__name__, item.get('ownerId'),
         type(item.get('shotId')).__name__, item.get('shotId'))
        for item in (membership or []))


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
        self.sampled_by_group = Counter()
        self.high_per_tick = Counter()
        self.max_high_per_tick = 0
        self.class_ticks = 0
        self.class_counters = Counter()
        self.cap = Counter()
        self.cap_farthest_ratios = []
        self.cap_farthest_world = []
        self.near_ratio_buckets = Counter()
        self.near_sampled = 0
        self.near_low_sampled = 0
        self.dt_over_one = 0
        self.max_dt = 0.0
        self.last_sample = {}
        self.membership_identities = ()
        self.high_low_flips = 0
        self.last_classification_group = {}
        self.top25_same_owner = Counter()
        self.top25_same_owner_max = 0
        self.exception_high_total = 0
        self.exception_high_max = 0
        self.classification_high_max = 0

    def tick(self, team, now, classification_context, self_ship_id=None):
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
                     'ownerLookups', 'sampledRows'):
            self.counts[name] += counters.get(name, 0)
        if is_classification:
            self.class_ticks += 1
            for name in (
                    'nearCount', 'farCount', 'unknownDistanceCount',
                    'newCount', 'groupChangeCount', 'provisionalHighCount',
                    'prunedCount', 'classifiedCount',
                    'highBudgetEligibleCount', 'highBudgetSelectedCount',
                    'highBudgetSpillCount', 'highBudgetOwnCount',
                    'highBudgetOwnNearCount', 'highBudgetNewCount',
                    'highBudgetUnknownDistanceCount'):
                self.class_counters[name] += classification.get(name, 0) or 0
            near_count = classification.get('nearCount', 0) or 0
            if near_count > HIGH_BUDGET:
                self.cap['ticksNearOver25'] += 1
            self.cap['nearOver25Exceed'] += max(0, near_count - HIGH_BUDGET)
            eligible = classification.get('highBudgetEligibleCount')
            if eligible is not None:
                if eligible > HIGH_BUDGET:
                    self.cap['ticksEligibleOver25'] += 1
                self.cap['eligibleTotal'] += eligible
                self.cap['selectedTotal'] += (
                    classification.get('highBudgetSelectedCount') or 0)
                self.cap['spillTotal'] += (
                    classification.get('highBudgetSpillCount') or 0)
            ratio = classification.get(
                'highBudgetFarthestSelectedWorldRatio')
            if ratio is not None:
                self.cap_farthest_ratios.append(ratio)
            squared = classification.get(
                'highBudgetFarthestSelectedDistanceSquared')
            if squared is not None:
                try:
                    self.cap_farthest_world.append(squared ** 0.5)
                except (TypeError, ValueError):
                    pass
            short = None
            width = classification.get('mapWidth')
            height = classification.get('mapHeight')
            try:
                if width and height:
                    short = min(float(width), float(height))
            except (TypeError, ValueError):
                short = None
            for row in rows:
                sample = row.get('sampling') or {}
                if sample.get('distanceStatus') != 'near':
                    continue
                squared = sample.get('distanceSquared')
                if short and squared is not None:
                    try:
                        ratio = (float(squared) ** 0.5) / short
                        self.near_ratio_buckets[_ratio_bucket(ratio)] += 1
                    except (TypeError, ValueError):
                        pass
            current_groups = {}
            selected_per_owner = Counter()
            class_high_count = 0
            for row in rows:
                sample = row.get('sampling') or {}
                key = identity(row)
                group = sample.get('group')
                current_groups[key] = group
                previous_group = self.last_classification_group.get(key)
                if (previous_group is not None and group is not None and
                        previous_group != group):
                    self.high_low_flips += 1
                if group == 'high':
                    class_high_count += 1
                    if (sample.get('distanceStatus') == 'near' and
                            sample.get('identityStatus') == 'available' and
                            not sample.get('provisional') and
                            row.get('isOwn') is not True):
                        selected_per_owner[row.get('ownerId')] += 1
            self.last_classification_group = current_groups
            if selected_per_owner:
                self.top25_same_owner_max = max(
                    self.top25_same_owner_max,
                    max(selected_per_owner.values()))
            selected_count = classification.get(
                'highBudgetSelectedCount') or 0
            self.classification_high_max = max(
                self.classification_high_max, class_high_count)
            exception_high = class_high_count - selected_count
            if exception_high < 0:
                exception_high = 0
            self.exception_high_total += exception_high
            self.exception_high_max = max(self.exception_high_max,
                                          exception_high)
        membership = (status.get('membership')
                      if status.get('membershipComplete') is True else [])
        self.membership_identities = _membership_identities(
            status.get('membership') or [])
        self.motion.update(rows, now, status.get('available', False),
                           membership=membership)
        high_count = 0
        for row in rows:
            sample = row.get('sampling') or {}
            group = sample.get('group')
            self.sampled_by_group[group] += 1
            if sample.get('distanceStatus') == 'near':
                self.near_sampled += 1
                if group == 'low':
                    self.near_low_sampled += 1
            if group == 'high':
                high_count += 1
            motion = row.get('motion') or {}
            if motion.get('available') is True:
                delta = motion.get('dt')
                if delta is not None:
                    if delta > 1.0:
                        self.dt_over_one += 1
                    if delta > self.max_dt:
                        self.max_dt = delta
            else:
                reason = self._motion_reason(
                    row, sample, now, status)
                self.motion_reasons[reason] += 1
                self.counts['velocityUnknown'] += 1
        self.high_per_tick[high_count] += 1
        if high_count > self.max_high_per_tick:
            self.max_high_per_tick = high_count
        wire_rows, wire_status = self.wire(rows, status)
        return wire_rows, wire_status

    def _motion_reason(self, row, sample, now, status):
        if row.get('position') is None:
            return 'positionUnknown'
        if sample.get('identityStatus') not in (None, 'available'):
            return 'identityUnavailable'
        key = identity(row)
        previous = self.last_sample.get(key)
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
        if previous[2] != key:
            return 'identityChanged'
        return 'motionUnavailableOther'

    def remember_rows(self, rows, now):
        for row in rows:
            key = identity(row)
            self.last_sample[key] = (now, row.get('position'), key)

    def result(self, original_compact_bytes, projected_compact_bytes, states):
        return {
            'states': states,
            'classificationTicks': self.class_ticks,
            'classificationCounters': dict(self.class_counters),
            'classificationHighMax': self.classification_high_max,
            'highLowFlips': self.high_low_flips,
            'top25SameOwnerMax': self.top25_same_owner_max,
            'exceptionHighTotal': self.exception_high_total,
            'exceptionHighMax': self.exception_high_max,
            'capCounters': dict(self.cap),
            'capFarthestSelectedRatio': _stats(self.cap_farthest_ratios),
            'capFarthestSelectedWorld': _stats(self.cap_farthest_world),
            'nearDistanceRatioBuckets': dict(self.near_ratio_buckets),
            'nearSampledRows': self.near_sampled,
            'nearLowSampledRows': self.near_low_sampled,
            'sampledRows': self.counts['sampledRows'],
            'sampledByGroup': dict(self.sampled_by_group),
            'highPerTickMax': self.max_high_per_tick,
            'highPerTickDistribution': dict(
                (str(key), value)
                for key, value in sorted(self.high_per_tick.items())),
            'positionReads': self.counts['positionReads'],
            'ownerLookups': self.counts['ownerLookups'],
            'identityReads': self.counts['identityReads'],
            'enumerations': self.counts['enumerations'],
            'unavailableStates': self.counts['unavailableStates'],
            'velocityUnknown': self.counts['velocityUnknown'],
            'motionReasons': dict(self.motion_reasons),
            'dtOverOneSecond': self.dt_over_one,
            'maxDt': self.max_dt,
            'apiFieldReads': dict(self.battle.counts),
            'originalCompactBytes': original_compact_bytes,
            'projectedCompactBytes': projected_compact_bytes,
        }


def replay_recording(path, compute_bytes=True):
    baseline = VariantReplay('baseline', TorpedoSamplingGroups(),
                             sampling_wire_payload)
    candidate = VariantReplay('candidate', CapTorpedoSamplingGroups(),
                              sampling_wire_payload)
    states = 0
    original_rows = 0
    membership_rows = 0
    membership_identity_mismatch_states = 0
    membership_row_mismatch_states = 0
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
                for variant in (baseline, candidate):
                    variant.sampler.clear()
                    variant.motion.clear()
                    variant.last_sample = {}
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
            baseline.battle.set_rows(original)
            candidate.battle.set_rows(original)
            baseline_rows, baseline_status = baseline.tick(
                team, state['ts'], classification_context,
                self_ship_id=self_ship_id)
            candidate_rows, candidate_status = candidate.tick(
                team, state['ts'], classification_context,
                self_ship_id=self_ship_id)
            baseline.remember_rows(baseline_rows, state['ts'])
            candidate.remember_rows(candidate_rows, state['ts'])
            baseline_membership = baseline.membership_identities
            candidate_membership = candidate.membership_identities
            membership_rows += len(candidate_membership)
            if baseline_membership != candidate_membership:
                membership_identity_mismatch_states += 1
            if len(baseline_membership) != len(candidate_membership):
                membership_row_mismatch_states += 1
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
        'membershipIdentityMismatchStates': membership_identity_mismatch_states,
        'membershipRowMismatchStates': membership_row_mismatch_states,
    }
    baseline_result = baseline.result(
        original_bytes if compute_bytes else None,
        baseline_bytes if compute_bytes else None, states)
    candidate_result = candidate.result(
        original_bytes if compute_bytes else None,
        candidate_bytes if compute_bytes else None, states)
    for result in (baseline_result, candidate_result):
        result.update(common)
    baseline_high = baseline_result['sampledByGroup'].get('high', 0)
    candidate_high = candidate_result['sampledByGroup'].get('high', 0)
    comparison = {
        'sampledRowsCandidateMinusBaseline': (
            candidate_result['sampledRows'] - baseline_result['sampledRows']),
        'highRowsCandidateMinusBaseline': candidate_high - baseline_high,
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
        'membershipIdentitiesEqual': (
            membership_identity_mismatch_states == 0 and
            membership_row_mismatch_states == 0),
        'classificationTicksEqual': (
            candidate_result['classificationTicks'] ==
            baseline_result['classificationTicks']),
        'candidateSampledByGroupSum': sum(
            candidate_result['sampledByGroup'].values()),
        'baselineSampledByGroupSum': sum(
            baseline_result['sampledByGroup'].values()),
        'dtOverOneSecondBaseline': baseline_result['dtOverOneSecond'],
        'dtOverOneSecondCandidate': candidate_result['dtOverOneSecond'],
        'velocityUnknownBaseline': baseline_result['velocityUnknown'],
        'velocityUnknownCandidate': candidate_result['velocityUnknown'],
        'highLowFlipsCandidate': candidate_result['highLowFlips'],
        'top25SameOwnerMaxCandidate': candidate_result['top25SameOwnerMax'],
        'exceptionHighMaxCandidate': candidate_result['exceptionHighMax'],
        'classificationHighMaxBaseline': (
            baseline_result['classificationHighMax']),
        'classificationHighMaxCandidate': (
            candidate_result['classificationHighMax']),
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


def b09_cap_static(path):
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
                'near': 0, 'far': 0, 'unknown': 0,
                'ownNear': 0, 'ownTotal': 0,
                'rowsClassified': 0,
                'ticksNearOver25': 0, 'nearOver25Exceed': 0,
                'eligibleTotal': 0, 'selectedTotal': 0, 'spillTotal': 0,
                'top25SameOwnerMax': 0,
                'nearPerTick': [], 'nearRatioBuckets': Counter(),
                'farthestSelectedRatios': []})
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
            short = min(width, height)
            if short <= 0:
                item['skippedTicks'] += 1
                continue
            radius_squared = (short / 5.0) ** 2
            near_distances = []
            non_own_near = []
            near = far = unknown = own_near = own_total = 0
            for row in rows:
                position = row.get('position')
                if position is None or len(position) != 3:
                    unknown += 1
                    continue
                dx = position[0] - self_position[0]
                dz = position[2] - self_position[2]
                squared = dx * dx + dz * dz
                item['rowsClassified'] += 1
                if squared <= radius_squared:
                    near += 1
                    near_distances.append((squared ** 0.5) / short)
                    if row.get('isOwn') is True:
                        own_near += 1
                    else:
                        non_own_near.append((squared, row.get('ownerId')))
                else:
                    far += 1
                if row.get('isOwn') is True:
                    own_total += 1
            item['near'] += near
            item['far'] += far
            item['unknown'] += unknown
            item['ownNear'] += own_near
            item['ownTotal'] += own_total
            item['nearPerTick'].append(near)
            eligible = near - own_near
            selected = min(HIGH_BUDGET, eligible)
            spill = max(0, eligible - HIGH_BUDGET)
            item['eligibleTotal'] += eligible
            item['selectedTotal'] += selected
            item['spillTotal'] += spill
            if near > HIGH_BUDGET:
                item['ticksNearOver25'] += 1
            item['nearOver25Exceed'] += max(0, near - HIGH_BUDGET)
            near_distances.sort()
            for ratio in near_distances:
                item['nearRatioBuckets'][_ratio_bucket(ratio)] += 1
            non_own_near.sort(key=lambda entry: entry[0])
            if selected:
                selected_owners = Counter()
                for _squared, owner_id in non_own_near[:selected]:
                    selected_owners[owner_id] += 1
                if selected_owners:
                    item['top25SameOwnerMax'] = max(
                        item['top25SameOwnerMax'],
                        max(selected_owners.values()))
                item['farthestSelectedRatios'].append(
                    near_distances[selected - 1])
    result = []
    for item in sessions.values():
        if item['detailRows'] == 0:
            continue
        total = item['near'] + item['far'] + item['unknown']
        near_per_tick = item['nearPerTick']
        item['classifiedTotal'] = total
        item['nearPerTickStats'] = _stats(near_per_tick)
        item['farthestSelectedRatio'] = _stats(
            item['farthestSelectedRatios'])
        item['nearRatioBuckets'] = dict(item['nearRatioBuckets'])
        item['ticksNearOver25Ratio'] = (
            item['ticksNearOver25'] / float(item['classificationTicks'])
            if item['classificationTicks'] else None)
        del item['nearPerTick']
        del item['farthestSelectedRatios']
        result.append(item)
    return {
        'sessions': result,
        'note': 'B09 is already sampled; this is classification-tick static '
                'geometry and a high-cap prospect only, not a 5 second '
                'scheduler replay. near totals can be compared with the old '
                'L/5 document (S2=324, S3=248) and max class rows 87.',
    }


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


SYNTHETIC_MODES = ('allNear', 'halfNear', 'ownMixed')


def synthetic_rows(mode):
    """Fixed 216 torpedo / 22 owner layout for the three cap stress cases."""
    rows = []
    owners = {}
    own_owner_ids = {7000}
    for owner_id in range(7000, 7022):
        owners[owner_id] = SyntheticOwner(owner_id in own_owner_ids)
    non_own_owners = [owner_id for owner_id in range(7000, 7022)
                      if owner_id not in own_owner_ids]
    counter = [0]

    def near_position(index):
        # L = 3000, L/5 = 600: z in 50..455 stays in the high radius.
        return [index * 0.1, 0.0, 50.0 + (index % 10) * 45.0]

    def far_position(index):
        return [index * 0.1, 0.0, 800.0 + (index % 10) * 160.0]

    def append(owner_id, position):
        counter[0] += 1
        rows.append(SyntheticTorpedo(10000 + counter[0],
                                     owner_id, counter[0], position))

    if mode == 'allNear':
        for index in range(216):
            append(non_own_owners[index % len(non_own_owners)],
                   near_position(index))
    elif mode == 'halfNear':
        for index in range(108):
            append(non_own_owners[index % len(non_own_owners)],
                   near_position(index))
        for index in range(108):
            append(non_own_owners[index % len(non_own_owners)],
                   far_position(index))
    elif mode == 'ownMixed':
        # 54 own rows split near/far, 162 non-own rows all near.
        own_ids = sorted(own_owner_ids)
        for index in range(54):
            position = (near_position(index) if index % 2 == 0
                        else far_position(index))
            append(own_ids[index % len(own_ids)], position)
        for index in range(162):
            append(non_own_owners[index % len(non_own_owners)],
                   near_position(index))
    else:
        raise ValueError('unknown synthetic mode: %s' % mode)
    return rows, owners


SYNTHETIC_SHAPES = {
    'allNear': {'nearRows': 216, 'farRows': 0, 'ownRows': 0},
    'halfNear': {'nearRows': 108, 'farRows': 108, 'ownRows': 0},
    'ownMixed': {'nearRows': 189, 'farRows': 27, 'ownRows': 54},
}


def _summarize_benchmark(runs):
    return {
        'medianTickMs': statistics.median(runs['tickMs']),
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
    variants = {}
    for mode in SYNTHETIC_MODES:
        results = {}
        for variant, sampler_class in (
                ('baseline', TorpedoSamplingGroups),
                ('candidate', CapTorpedoSamplingGroups)):
            runs = {'tickMs': [], 'sampledRows': 0, 'positionReads': 0,
                    'ownerLookups': 0, 'identityReads': 0,
                    'enumerations': 0, 'sampledByGroup': Counter(),
                    'velocityUnknown': 0, 'apiFieldReads': Counter()}
            for _repeat in range(repeats):
                rows, owners = synthetic_rows(mode)
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
                        self_ship_id=7000)
                    membership = (status.get('membership')
                                  if status.get('membershipComplete') is True
                                  else [])
                    motion.update(sample_rows, now,
                                  status.get('available', False),
                                  membership=membership)
                    counters = ((status.get('sampling') or {})
                                .get('counters') or {})
                    for name in ('enumerations', 'identityReads',
                                 'positionReads', 'ownerLookups',
                                 'sampledRows'):
                        repeat_counts[name] += counters.get(name, 0)
                    for row in sample_rows:
                        sample = row.get('sampling') or {}
                        repeat_groups[sample.get('group')] += 1
                        if row.get('motion', {}).get('available') is not True:
                            repeat_counts['velocityUnknown'] += 1
                elapsed = time.perf_counter() - start
                runs['tickMs'].append(elapsed / ticks * 1000.0)
                for name in ('sampledRows', 'positionReads', 'ownerLookups',
                             'identityReads', 'enumerations',
                             'velocityUnknown'):
                    runs[name] += repeat_counts.get(name, 0)
                runs['sampledByGroup'].update(repeat_groups)
                runs['apiFieldReads'].update(battle.counts)
            results[variant] = _summarize_benchmark(runs)
        shape = SYNTHETIC_SHAPES[mode]
        variants[mode] = {
            'rows': 216, 'owners': 22,
            'nearRows': shape['nearRows'], 'farRows': shape['farRows'],
            'ownRows': shape['ownRows'],
            'repeats': repeats, 'ticks': ticks,
            'baseline': results['baseline'],
            'candidate': results['candidate'],
        }
    return {
        'variants': variants,
        'hostOnly': True,
        'note': 'Host Python 3 timing with synthetic cheap getters; not game '
                'time and not an FPS improvement rate. The candidate timing '
                'includes the cap selection sort.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', action='append', default=[],
                        help='unsampled recording to replay (B43/B44)')
    parser.add_argument('--b09', default=None,
                        help='B09 recording for static classification-tick '
                             'high-cap geometry (not a replay)')
    parser.add_argument('--synthetic', action='store_true',
                        help='run synthetic 216 torpedo / 22 owner benchmark')
    parser.add_argument('--no-bytes', action='store_true',
                        help='skip compact-byte encoding for faster replay')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--ticks', type=int, default=200)
    parser.add_argument('--json-output', default=None)
    args = parser.parse_args()
    output = {'scope': 'offline research; runtime source not modified',
              'highBudget': HIGH_BUDGET}
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
        output['b09Static'] = b09_cap_static(args.b09)
    if args.synthetic:
        output['synthetic'] = synthetic_benchmark(args.repeats, args.ticks)
    text = json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_output:
        with open(args.json_output, 'w', encoding='utf-8') as stream:
            stream.write(text + '\n')
    print(text)


if __name__ == '__main__':
    main()