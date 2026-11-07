"""Test-only nearest-25 high-budget torpedo sampler prototype.

Production keeps ``TorpedoSamplingGroups``: every torpedo inside ``L/5``
(``L = min(mapWidth, mapHeight)``) is high at 5 Hz and everything outside is
low at average 2 Hz.  This research module keeps the same two wire groups
(``high`` / ``low``) and the same 5 second classification, but caps the
distance-selected high set on each classification tick:

* non-own, known distance, inside ``L/5``, already classified: only the
  nearest ``HIGH_BUDGET`` (25) by horizontal distance stay high 5 Hz;
* the remaining in-range rows spill to low average 2 Hz;
* outside ``L/5`` stays low average 2 Hz;
* strict ``owner.isPlayer is True`` is high at every distance and is **never
  counted against the 25 slot budget**;
* new identity, unknown distance, unknown/duplicate identity and lost context
  keep the existing safety-side high and are cap exceptions, so the total
  number of high rows is not bounded by 25.

The base class, producer and game files are not modified.  The selection is
done on the classification tick only; between classifications a row keeps its
group and the existing five-second re-classification delay is unchanged.  No
hysteresis is added.  Equal distances are resolved by the stable enumeration
order only, so no strict identity value is ever compared.  The wire payload is
the production ``sampling_wire_payload`` (``high`` / ``low``); cap metadata is
adapter-local research output and is not yet a wire contract.
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
    _sampling_context, _sampling_distance,
    _SAMPLING_HIGH, _SAMPLING_LOW)

HIGH_BUDGET = 25


class CapTorpedoSamplingGroups(TorpedoSamplingGroups):
    """Nearest-25 high budget on top of the production distance sampler."""

    HIGH_BUDGET = HIGH_BUDGET

    def _observe_classification(self, observations, now, context,
                                membership_complete, context_info=None):
        info = (context_info if context_info is not None
                else _sampling_context(context))
        observed = {}
        near = far = unknown_distance = 0
        new_count = changed_count = provisional_count = 0
        sampled_high = sampled_low = 0
        own_count = own_near_count = 0
        details = []
        candidates = []

        order = 0
        for observation in observations:
            status = observation.get('identityStatus', 'unknown')
            key = observation.get('key')
            if status != 'available' or key is None:
                details.append((observation, status, key, None, None, None))
                continue
            observed[key] = True
            distance_status, distance_squared = _sampling_distance(
                info, observation.get('position'))
            if distance_status == 'near':
                near += 1
            elif distance_status == 'far':
                far += 1
            else:
                unknown_distance += 1
            previous = self._entries.get(key)
            is_own = observation.get('isOwn') is True
            if is_own:
                own_count += 1
                if distance_status == 'near':
                    own_near_count += 1
            # The 25 slot budget only holds non-own, already classified rows
            # with a known in-range distance.  Own, new, unknown distance and
            # unknown identity are exceptions handled on the second pass.
            if (distance_status == 'near' and not is_own and
                    previous is not None):
                candidates.append((distance_squared, order, key))
            details.append((observation, status, key, distance_status,
                            distance_squared, previous))
            order += 1

        # Stable sort by distance only.  Equal distances keep the enumeration
        # order, so no strict identity value is ever compared.
        ordered = sorted(candidates, key=lambda item: item[0])
        limit = self.HIGH_BUDGET
        selected = {}
        for _distance_squared, _order, key in ordered[:limit]:
            selected[key] = True
        eligible_count = len(candidates)
        selected_count = len(selected)
        spill_count = eligible_count - selected_count
        farthest_squared = (ordered[selected_count - 1][0]
                            if selected_count else None)
        short = None
        if info.get('status') == 'available':
            short = min(info['width'], info['height'])
        farthest_ratio = None
        if farthest_squared is not None and short:
            try:
                farthest_ratio = (farthest_squared ** 0.5) / float(short)
            except (TypeError, ValueError):
                farthest_ratio = None

        decisions = []
        for (observation, status, key, distance_status, distance_squared,
             previous) in details:
            if status != 'available' or key is None:
                reason = ('duplicateIdentity' if status == 'duplicate'
                          else 'unknownIdentity')
                decisions.append(self._decision(
                    True, _SAMPLING_HIGH, self.HIGH_INTERVAL, reason, True,
                    'unknown', None, now))
                sampled_high += 1
                provisional_count += 1
                continue
            if previous is None:
                group = _SAMPLING_HIGH
                provisional = True
                new_count += 1
            else:
                is_own = observation.get('isOwn') is True
                if is_own or distance_status == 'unknown':
                    group = _SAMPLING_HIGH
                elif distance_status == 'near':
                    group = (_SAMPLING_HIGH if key in selected
                             else _SAMPLING_LOW)
                else:
                    group = _SAMPLING_LOW
                provisional = False
                if previous['group'] != group:
                    changed_count += 1
            interval = (self.HIGH_INTERVAL if group == _SAMPLING_HIGH
                        else self.LOW_INTERVAL)
            entry = {'group': group, 'nextDue': now + interval,
                     'lastSampled': now, 'provisional': provisional,
                     'identity': observation.get('identity') or {},
                     'classifiedTs': now,
                     'distanceStatus': distance_status,
                     'distanceSquared': distance_squared,
                     'firstSeen': (previous['firstSeen']
                                   if previous is not None else now)}
            self._entries[key] = entry
            if provisional:
                provisional_count += 1
            if group == _SAMPLING_HIGH:
                sampled_high += 1
            else:
                sampled_low += 1
            decisions.append(self._decision(
                True, group, interval, 'classification', provisional,
                distance_status, distance_squared, now))

        pruned = 0
        if membership_complete:
            remove = []
            for key in list(self._entries.keys()):
                if key not in observed:
                    remove.append(key)
            for key in remove:
                del self._entries[key]
                pruned += 1
        self._last_classification = now
        self._next_classification = now + self.CLASSIFICATION_INTERVAL
        self._classifications += 1
        available_context = info['status'] == 'available'
        self._classification = {
            'status': 'available' if available_context else 'unknown',
            'reason': info['reason'], 'ts': now,
            'nextDue': self._next_classification,
            'intervalSeconds': self.CLASSIFICATION_INTERVAL,
            'radiusWorld': info['radius'],
            'radiusSource': ('min(mapWidth,mapHeight)/5'
                             if available_context else None),
            'radiusSquared': info['radiusSquared'],
            'mapWidth': info['width'], 'mapHeight': info['height'],
            'mapSource': info['source'], 'mapInferred': info['inferred'],
            'positionsNormalized': info['normalized'],
            'selfPositionStatus': ('available' if available_context
                                   else 'unknown'),
            'nearCount': near, 'farCount': far,
            'unknownDistanceCount': unknown_distance,
            'classifiedCount': near + far + unknown_distance,
            'newCount': new_count, 'groupChangeCount': changed_count,
            'provisionalHighCount': provisional_count,
            'prunedCount': pruned,
            # Cap research metadata (adapter-local; not on the wire yet).
            'highBudgetLimit': self.HIGH_BUDGET,
            'highBudgetEligibleCount': eligible_count,
            'highBudgetSelectedCount': selected_count,
            'highBudgetSpillCount': spill_count,
            'highBudgetOwnCount': own_count,
            'highBudgetOwnNearCount': own_near_count,
            'highBudgetNewCount': new_count,
            'highBudgetUnknownDistanceCount': unknown_distance,
            'highBudgetFarthestSelectedDistanceSquared': farthest_squared,
            'highBudgetFarthestSelectedWorldRatio': farthest_ratio,
        }
        if sampled_high:
            self._last_high_sample = now
        if sampled_low:
            self._last_low_sample = now
        self._last_tick = {
            'ts': now, 'classificationDue': True,
            'highSampled': sampled_high > 0, 'lowSampled': sampled_low > 0,
            'highCount': sampled_high, 'lowCount': sampled_low,
            'newCount': new_count, 'prunedCount': pruned}
        return decisions
