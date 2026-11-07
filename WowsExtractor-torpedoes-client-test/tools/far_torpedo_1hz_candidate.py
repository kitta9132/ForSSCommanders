"""Test-only three-tier torpedo sampling prototype (not used by runtime).

The production sampler keeps ``TorpedoSamplingGroups`` at L/5 high 5 Hz and
L/5 far average 2 Hz.  This module adds a middle tier for research only:

* ``d <= min(mapWidth, mapHeight) / 5``: high, 0.2 s
* ``min / 5 < d <= min / 3``: mid, 0.5 s
* ``min / 3 < d``: low, 1.0 s
* strict owner ``isPlayer is True``: high at every distance
* new / unknown identity / unknown distance / context loss: provisional high

The base class, producer and game files are not modified.  ``mid`` is a new
wire group name; ``tiered_sampling_wire_payload`` is a research prototype and
must not be treated as an applied production contract.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SOURCE = os.path.join(os.path.dirname(_HERE), 'res_mods', 'PnFMods',
                       'WowsExtractor')
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)

from torpedo_telemetry import (  # noqa: E402
    LegacyTorpedoSamplingGroups as TorpedoSamplingGroups,
    _finite, _sampling_context, _SAMPLING_EPSILON,
    _SAMPLING_HIGH, _SAMPLING_LOW)

SAMPLING_MID = 'mid'
DEFAULT_MID_INTERVAL = 0.5
DEFAULT_FAR_INTERVAL = 1.0


def tier_distance(info, position):
    """Return (tier, squared_distance) using L/5 and L/3 thresholds.

    ``info`` is the existing producer context (L/5 radius, map extents and
    optional normalized-axis flag).  A missing position or context is
    ``unknown``; no previous position is reused.
    """
    if info.get('status') != 'available' or position is None:
        return 'unknown', None
    try:
        width = info.get('width')
        height = info.get('height')
        if not _finite(width) or not _finite(height) or width <= 0 or height <= 0:
            return 'unknown', None
        x, z = position[0], position[2]
        if info.get('normalized'):
            dx = (x - info['x']) * width
            dz = (z - info['z']) * height
        else:
            dx = x - info['x']
            dz = z - info['z']
        squared = dx * dx + dz * dz
        if not _finite(squared):
            return 'unknown', None
        short = min(width, height)
        near_squared = (short / 5.0) ** 2
        mid_squared = (short / 3.0) ** 2
        # Both boundaries are inclusive, matching the production L/5 rule.
        if squared <= near_squared:
            return 'near', squared
        if squared <= mid_squared:
            return 'mid', squared
        return 'far', squared
    except (KeyError, TypeError, ValueError, IndexError):
        return 'unknown', None


class TieredTorpedoSamplingGroups(TorpedoSamplingGroups):
    """Research-only three-tier schedule built on the production sampler."""

    CLASSIFICATION_INTERVAL = 5.0
    HIGH_INTERVAL = 0.2
    MID_INTERVAL = DEFAULT_MID_INTERVAL
    LOW_INTERVAL = DEFAULT_FAR_INTERVAL

    def clear(self):
        super(TieredTorpedoSamplingGroups, self).clear()
        self._last_mid_sample = None

    def _interval_for(self, group):
        if group == _SAMPLING_HIGH:
            return self.HIGH_INTERVAL
        if group == SAMPLING_MID:
            return self.MID_INTERVAL
        return self.LOW_INTERVAL

    def _group_for(self, distance_status, is_own, previous):
        if previous is None:
            return _SAMPLING_HIGH, True
        if is_own is True or distance_status in ('near', 'unknown'):
            return _SAMPLING_HIGH, False
        if distance_status == 'mid':
            return SAMPLING_MID, False
        return _SAMPLING_LOW, False

    def _observe_classification(self, observations, now, context,
                                membership_complete, context_info=None):
        info = context_info if context_info is not None else _sampling_context(context)
        observed = {}
        near = mid = far = unknown_distance = 0
        new_count = changed_count = provisional_count = 0
        sampled_high = sampled_mid = sampled_low = 0
        decisions = []
        for observation in observations:
            status = observation.get('identityStatus', 'unknown')
            key = observation.get('key')
            if status != 'available' or key is None:
                reason = ('duplicateIdentity' if status == 'duplicate'
                          else 'unknownIdentity')
                decisions.append(self._decision(
                    True, _SAMPLING_HIGH, self.HIGH_INTERVAL, reason, True,
                    'unknown', None, now))
                sampled_high += 1
                provisional_count += 1
                continue
            observed[key] = True
            distance_status, distance_squared = tier_distance(
                info, observation.get('position'))
            if distance_status == 'near':
                near += 1
            elif distance_status == 'mid':
                mid += 1
            elif distance_status == 'far':
                far += 1
            else:
                unknown_distance += 1
            previous = self._entries.get(key)
            group, provisional = self._group_for(
                distance_status, observation.get('isOwn'), previous)
            if previous is None:
                new_count += 1
            elif previous['group'] != group:
                changed_count += 1
            interval = self._interval_for(group)
            self._entries[key] = {
                'group': group, 'nextDue': now + interval,
                'lastSampled': now, 'provisional': provisional,
                'identity': observation.get('identity') or {},
                'classifiedTs': now,
                'distanceStatus': distance_status,
                'distanceSquared': distance_squared,
                'firstSeen': (previous['firstSeen']
                              if previous is not None else now)}
            if provisional:
                provisional_count += 1
            if group == _SAMPLING_HIGH:
                sampled_high += 1
            elif group == SAMPLING_MID:
                sampled_mid += 1
            else:
                sampled_low += 1
            decisions.append(self._decision(
                True, group, interval, 'classification', provisional,
                distance_status, distance_squared, now))
        pruned = 0
        if membership_complete:
            remove = [key for key in list(self._entries.keys())
                      if key not in observed]
            for key in remove:
                del self._entries[key]
                pruned += 1
        self._last_classification = now
        self._next_classification = now + self.CLASSIFICATION_INTERVAL
        self._classifications += 1
        available_context = info['status'] == 'available'
        short = None
        if available_context:
            short = min(info['width'], info['height'])
        self._classification = {
            'status': 'available' if available_context else 'unknown',
            'reason': info['reason'], 'ts': now,
            'nextDue': self._next_classification,
            'intervalSeconds': self.CLASSIFICATION_INTERVAL,
            'radiusWorld': info['radius'],
            'radiusSource': ('min(mapWidth,mapHeight)/5'
                             if available_context else None),
            'radiusSquared': info['radiusSquared'],
            'midRadiusWorld': (short / 3.0 if short is not None else None),
            'midRadiusSource': ('min(mapWidth,mapHeight)/3'
                                if available_context else None),
            'midRadiusSquared': (short * short / 9.0
                                 if short is not None else None),
            'mapWidth': info['width'], 'mapHeight': info['height'],
            'mapSource': info['source'], 'mapInferred': info['inferred'],
            'positionsNormalized': info['normalized'],
            'selfPositionStatus': ('available' if available_context
                                   else 'unknown'),
            'nearCount': near, 'midCount': mid, 'farCount': far,
            'unknownDistanceCount': unknown_distance,
            'classifiedCount': near + mid + far + unknown_distance,
            'newCount': new_count, 'groupChangeCount': changed_count,
            'provisionalHighCount': provisional_count,
            'prunedCount': pruned}
        if sampled_high:
            self._last_high_sample = now
        if sampled_mid:
            self._last_mid_sample = now
        if sampled_low:
            self._last_low_sample = now
        self._last_tick = {
            'ts': now, 'classificationDue': True,
            'highSampled': sampled_high > 0,
            'midSampled': sampled_mid > 0,
            'lowSampled': sampled_low > 0,
            'highCount': sampled_high, 'midCount': sampled_mid,
            'lowCount': sampled_low,
            'newCount': new_count, 'prunedCount': pruned}
        return decisions

    def _observe_cadence(self, observations, now, context_available=True):
        if not context_available:
            return self._observe_safety_high(observations, now)
        sampled_high = sampled_mid = sampled_low = 0
        new_count = 0
        decisions = []
        for observation in observations:
            status = observation.get('identityStatus', 'unknown')
            key = observation.get('key')
            if status != 'available' or key is None:
                reason = ('duplicateIdentity' if status == 'duplicate'
                          else 'unknownIdentity')
                decisions.append(self._decision(
                    True, _SAMPLING_HIGH, self.HIGH_INTERVAL, reason, True,
                    'unknown', None, self._last_classification))
                sampled_high += 1
                continue
            entry = self._entries.get(key)
            if entry is None:
                entry = {'group': _SAMPLING_HIGH,
                         'nextDue': now + self.HIGH_INTERVAL,
                         'lastSampled': now, 'provisional': True,
                         'identity': observation.get('identity') or {},
                         'classifiedTs': self._last_classification,
                         'distanceStatus': 'notClassified',
                         'distanceSquared': None, 'firstSeen': now}
                self._entries[key] = entry
                new_count += 1
                sampled_high += 1
                decisions.append(self._decision(
                    True, _SAMPLING_HIGH, self.HIGH_INTERVAL, 'new', True,
                    'notClassified', None, self._last_classification))
                continue
            group = entry['group']
            own = observation.get('isOwn') is True
            promoted_own = own and group != _SAMPLING_HIGH
            if promoted_own:
                group = _SAMPLING_HIGH
                entry['group'] = group
            interval = self._interval_for(group)
            if (promoted_own or
                    now + _SAMPLING_EPSILON >= entry['nextDue']):
                entry['nextDue'] = (now + interval if promoted_own else
                                    self._advance_due(
                                        entry['nextDue'], now, interval))
                entry['lastSampled'] = now
                if group == _SAMPLING_HIGH:
                    sampled_high += 1
                    reason = 'highDue'
                elif group == SAMPLING_MID:
                    sampled_mid += 1
                    reason = 'midDue'
                else:
                    sampled_low += 1
                    reason = 'lowDue'
                decisions.append(self._decision(
                    True, group, interval, reason,
                    entry['provisional'], entry['distanceStatus'],
                    entry['distanceSquared'], entry['classifiedTs']))
            else:
                decisions.append(self._decision(
                    False, group, interval, 'notDue', entry['provisional'],
                    entry['distanceStatus'], entry['distanceSquared'],
                    entry['classifiedTs']))
        if sampled_high:
            self._last_high_sample = now
        if sampled_mid:
            self._last_mid_sample = now
        if sampled_low:
            self._last_low_sample = now
        self._last_tick = {
            'ts': now, 'classificationDue': False,
            'highSampled': sampled_high > 0,
            'midSampled': sampled_mid > 0,
            'lowSampled': sampled_low > 0,
            'highCount': sampled_high, 'midCount': sampled_mid,
            'lowCount': sampled_low,
            'newCount': new_count, 'prunedCount': 0}
        return decisions

    def summary(self, now, options=None):
        options = options if isinstance(options, dict) else {}
        high_members = mid_members = low_members = 0
        for entry in self._entries.values():
            if entry['group'] == _SAMPLING_HIGH:
                high_members += 1
            elif entry['group'] == SAMPLING_MID:
                mid_members += 1
            else:
                low_members += 1
        tick = self._last_tick if isinstance(self._last_tick, dict) else {}
        classification = dict(self._classification)
        classification['due'] = bool(self._plan.get('classificationDue'))
        classification['clockReset'] = bool(self._plan.get('clockReset'))
        classification['classificationTs'] = self._last_classification
        classification['nextDue'] = self._next_classification
        classification['intervalSeconds'] = self.CLASSIFICATION_INTERVAL
        if self._last_classification is None:
            high_status = mid_status = low_status = 'notClassified'
        else:
            high_status = ('sampled' if tick.get('highSampled')
                           else 'notSampled')
            mid_status = ('sampled' if tick.get('midSampled')
                          else 'notSampled')
            low_status = ('sampled' if tick.get('lowSampled')
                          else 'notSampled')
        high = {'status': high_status, 'sampleTs': self._last_high_sample,
                'intervalSeconds': self.HIGH_INTERVAL,
                'sampledCount': tick.get('highCount', 0),
                'memberCount': high_members}
        mid = {'status': mid_status,
               'sampleTs': getattr(self, '_last_mid_sample', None),
               'intervalSeconds': self.MID_INTERVAL,
               'sampledCount': tick.get('midCount', 0),
               'memberCount': mid_members}
        low = {'status': low_status, 'sampleTs': self._last_low_sample,
               'intervalSeconds': self.LOW_INTERVAL,
               'sampledCount': tick.get('lowCount', 0),
               'memberCount': low_members}
        return {
            'status': options.get('samplingStatus', 'available'),
            'classification': classification,
            'classificationTs': self._last_classification,
            'classificationDue': bool(self._plan.get('classificationDue')),
            'radiusWorld': classification.get('radiusWorld'),
            'radiusSource': classification.get('radiusSource'),
            'midRadiusWorld': classification.get('midRadiusWorld'),
            'midRadiusSource': classification.get('midRadiusSource'),
            'mapSource': classification.get('mapSource'),
            'mapInferred': classification.get('mapInferred'),
            'selfPositionStatus': classification.get('selfPositionStatus'),
            'high': high, 'mid': mid, 'low': low,
            'newCount': tick.get('newCount', 0),
            'prunedCount': tick.get('prunedCount', 0),
            'safetyHigh': bool(tick.get('safetyHigh')),
            'promotedCount': tick.get('promotedCount', 0),
            'membershipComplete': bool(options.get(
                'membershipComplete', False)),
            'membershipCount': options.get('membershipCount', 0),
            'duplicateIdentityCount': options.get('duplicateCount', 0),
            'unmatchableIdentityCount': options.get('unknownCount', 0),
            'counters': options.get('counters', {})}


def tiered_sampling_wire_payload(rows, status):
    """Prototype wire compaction that keeps the new ``mid`` summary.

    This is a research contract only.  Applying it to the producer would be a
    runtime wire change (new group name and summary key).
    """
    if not isinstance(status.get('sampling'), dict):
        return rows, status
    out = dict(status)
    out['membershipFields'] = ['uiId', 'ownerId', 'shotId']
    out['membership'] = [[item.get('uiId'), item.get('ownerId'),
                          item.get('shotId')]
                         for item in status.get('membership', [])]
    summary = status['sampling']
    classification = summary.get('classification', {})
    out['sampling'] = {
        'status': summary.get('status'),
        'classification': dict((name, classification.get(name)) for name in (
            'status', 'reason', 'ts', 'nextDue', 'intervalSeconds',
            'radiusWorld', 'midRadiusWorld', 'mapSource', 'mapInferred')),
        'high': summary.get('high', {}), 'mid': summary.get('mid', {}),
        'low': summary.get('low', {}),
        'safetyHigh': bool(summary.get('safetyHigh')),
        'unmatchableIdentityCount': summary.get('unmatchableIdentityCount', 0),
        'duplicateIdentityCount': summary.get('duplicateIdentityCount', 0)}
    if summary.get('reason') is not None:
        out['sampling']['reason'] = summary['reason']
    for row in rows:
        sample = row.get('sampling', {})
        compact = {'group': sample.get('group'),
                   'sampleTs': sample.get('sampleTs')}
        if sample.get('provisional'):
            compact['provisional'] = True
        for name in ('identityStatus', 'positionStatus'):
            if sample.get(name) not in (None, 'available'):
                compact[name] = sample[name]
        row['sampling'] = compact
    return rows, out
