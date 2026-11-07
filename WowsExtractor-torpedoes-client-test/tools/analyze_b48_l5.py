"""Offline, anonymised analysis of the B48 L/5 recording.

This tool reads a private JSONL telemetry recording sequentially and prints
aggregate statistics only.  It never emits battle IDs, player IDs, vehicle IDs,
weapon IDs, owner names, or raw positions.  It does not modify runtime source,
install anything, or run the game/recorder.

Usage:
    python tools/analyze_b48_l5.py --recording recordings/without-atm-b48.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
from collections import Counter, OrderedDict, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PHASES = (
    'state_cycle_total',
    'snapshot_build_total',
    'avatar',
    'ships',
    'torpedoes',
    'submit',
    'gun_sampling',
    'self',
    'armament_systems',
    'submarine_sampling',
)

# A gap longer than this is treated as a stall/absence, not a cadence sample.
MAX_CONTINUITY_GAP_SECONDS = 5.0
# State.ts and classification.ts are floats written from the same clock.
TIME_EQUAL_TOLERANCE = 1e-9
# A session with fewer than this many active states is reported but excluded
# from the analysis.  B48 has one stale meta followed by one inactive state.
MIN_SESSION_ACTIVE_STATES = 2

BAND_DEFINITIONS = (
    ('all', 0, None),
    ('zero', 0, 0),
    ('1-49', 1, 49),
    ('50-99', 50, 99),
    ('100-179', 100, 179),
    ('180+', 180, None),
    ('positive', 1, None),
    ('ge50', 50, None),
)


def finite_number(value: Any) -> bool:
    """True for a finite int/float, excluding JSON booleans."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def finite_int(value: Any, default: int = 0) -> int:
    """Return a finite integer count, or default for malformed values."""
    if not finite_number(value):
        return default
    return int(value)


def horizon_distance(position_a: Any, position_b: Any) -> Optional[float]:
    """Horizontal game-world distance; None when either position is invalid."""
    if not (isinstance(position_a, (list, tuple))
            and isinstance(position_b, (list, tuple))
            and len(position_a) >= 3 and len(position_b) >= 3):
        return None
    if not all(finite_number(position_a[i]) for i in (0, 1, 2)):
        return None
    if not all(finite_number(position_b[i]) for i in (0, 1, 2)):
        return None
    return math.hypot(position_a[0] - position_b[0],
                      position_a[2] - position_b[2])


def distance_band(distance: Optional[float],
                  radius: Optional[float]) -> str:
    """L/5 near / L/5..L/3 mid / >L/3 far / unknown."""
    if not finite_number(distance) or not finite_number(radius) or radius <= 0:
        return 'unknown'
    if distance <= radius:
        return 'near'
    if distance <= radius * 3.0:
        return 'mid'
    return 'far'


def l3_band(distance: Optional[float],
            radius: Optional[float]) -> str:
    """Old L/3 geometry: near within 3*radius, otherwise far."""
    if not finite_number(distance) or not finite_number(radius) or radius <= 0:
        return 'unknown'
    return 'near' if distance <= radius * 3.0 else 'far'


def times_equal(left: Any, right: Any) -> bool:
    return (finite_number(left) and finite_number(right)
            and abs(left - right) <= TIME_EQUAL_TOLERANCE)


def quantile(values: Sequence[float], fraction: float) -> Optional[float]:
    """Nearest-rank quantile (ceil(q*n)), matching the existing docs."""
    if not values:
        return None
    ordered = sorted(values)
    if fraction <= 0:
        return ordered[0]
    if fraction >= 1:
        return ordered[-1]
    index = max(0, min(len(ordered) - 1,
                       int(math.ceil(fraction * len(ordered))) - 1))
    return ordered[index]


def phase_mean(phase: Any) -> Optional[float]:
    """total/count for one phase object, rejecting nonfinite/missing values."""
    if not isinstance(phase, dict):
        return None
    total = phase.get('total')
    count = phase.get('count')
    if not finite_number(total) or not finite_number(count) or count <= 0:
        return None
    mean = total / count
    return mean if math.isfinite(mean) else None


def weighted_phase_mean(windows: Iterable[Dict[str, Any]],
                        phase_name: str) -> Optional[float]:
    """Sum(total)/sum(count) across completed windows."""
    total_sum = 0.0
    count_sum = 0.0
    for window in windows:
        phase = (window.get('phases') or {}).get(phase_name)
        if not isinstance(phase, dict):
            continue
        total = phase.get('total')
        count = phase.get('count')
        if not finite_number(total) or not finite_number(count) or count <= 0:
            continue
        total_sum += float(total)
        count_sum += float(count)
    if count_sum <= 0:
        return None
    value = total_sum / count_sum
    return value if math.isfinite(value) else None


def perf_window_key(perf: Any) -> Optional[Tuple[float, float]]:
    """Stable dedup key for a completed 5-second performance window."""
    if not isinstance(perf, dict):
        return None
    start = perf.get('sampleStartSeconds')
    end = perf.get('sampleEndSeconds')
    if not finite_number(start) or not finite_number(end):
        return None
    return (float(start), float(end))


def counter_to_dict(counter: Counter) -> Dict[str, int]:
    return {str(key): int(value) for key, value in sorted(
        counter.items(), key=lambda item: (str(item[0]), str(item[1])))}


def distribution(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not values:
        return {
            'count': 0, 'min': None, 'p10': None, 'median': None,
            'mean': None, 'p90': None, 'p95': None, 'max': None,
            'over1s': 0, 'over5s': 0,
        }
    return {
        'count': len(values),
        'min': min(values),
        'p10': quantile(values, 0.10),
        'median': statistics.median(values),
        'mean': statistics.mean(values),
        'p90': quantile(values, 0.90),
        'p95': quantile(values, 0.95),
        'max': max(values),
        'over1s': sum(1 for value in values if value > 1.0),
        'over5s': sum(1 for value in values if value > 5.0),
    }


def _battle_key(meta: Any) -> Optional[str]:
    if not isinstance(meta, dict):
        return None
    battle_id = meta.get('battleId')
    if battle_id is None:
        return None
    return hashlib.sha1(str(battle_id).encode('utf-8')).hexdigest()[:12]


def _membership_identity(row: Any) -> Optional[Tuple[Any, Any, Any]]:
    if isinstance(row, (list, tuple)) and len(row) >= 3:
        return (row[0], row[1], row[2])
    if isinstance(row, dict):
        return (row.get('uiId'), row.get('ownerId'), row.get('shotId'))
    return None


def _membership_owner(row: Any, fields: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get('ownerId')
    if isinstance(row, (list, tuple)):
        if isinstance(fields, list) and 'ownerId' in fields:
            index = fields.index('ownerId')
            if index < len(row):
                return row[index]
        if len(row) >= 2:
            return row[1]
    return None


def _row_identity(row: Dict[str, Any]) -> Optional[Tuple[Any, Any, Any]]:
    return (row.get('uiId'), row.get('ownerId'), row.get('shotId'))


def _calibration_short_side(diag: Any) -> Optional[float]:
    if not isinstance(diag, dict):
        return None
    calibration = diag.get('mapCalibration')
    if not isinstance(calibration, dict):
        return None
    coefficients = calibration.get('coefficients')
    if not isinstance(coefficients, dict):
        return None
    scales = []
    for value in coefficients.values():
        if isinstance(value, dict) and finite_number(value.get('scale')):
            scale = abs(float(value['scale']))
            if scale > 0:
                scales.append(scale)
    return min(scales) if scales else None


class Session:
    """Streaming accumulator for one meta-delimited battle session."""

    def __init__(self, index: int, meta: Dict[str, Any]):
        self.index = index
        self.label = 'S%d' % index
        self.meta = meta
        self.battle_key = _battle_key(meta)
        self.meta_ts = meta.get('ts')
        self.states = 0
        self.inactive_states = 0
        self.active_states = 0
        self.battle_mismatch_states = 0
        self.first_ts: Optional[float] = None
        self.last_ts: Optional[float] = None
        self.membership_sum = 0
        self.detail_sum = 0
        self.max_membership = 0
        self.max_detail = 0
        self.max_owners = 0
        self.unique_identities = set()
        self.unique_owners = set()
        self.high_member = 0
        self.high_sampled = 0
        self.low_member = 0
        self.low_sampled = 0
        self.group_rows = Counter()
        self.sampling_status = Counter()
        self.classification = Counter()
        self.radius_values: List[float] = []
        self.map_short_sides: List[float] = []
        self.radius_ratios: List[float] = []
        self.radius_sources = Counter()
        self.radius_inferred = Counter()
        self.calibration_status = Counter()
        self.cl_ticks = 0
        self.cl_usable_ticks = 0
        self.cl_skipped_ticks = 0
        self.cl_full_position_ticks = 0
        self.cl_rows = 0
        self.cl_l5 = Counter()
        self.cl_l3 = Counter()
        self.cl_group_geometry = Counter()
        self.cl_actual_high_member = 0
        self.cl_actual_high_sampled = 0
        self.cl_actual_low_member = 0
        self.cl_actual_low_sampled = 0
        self.cl_own_true = 0
        self.cl_own_none = 0
        self.cl_high_non_near = 0
        self.cl_high_unknown_distance = 0
        self.cl_low_near = 0
        self.all_group_geometry = Counter()
        self.own_flags = Counter()
        self.owner_player_flags = Counter()
        self.detail_position_missing = 0
        self.map_position_status = Counter()
        self.motion_unavailable = Counter()
        self.speed_missing = Counter()
        self.last_sample: Dict[Tuple[Any, Any, Any], Tuple[float, str]] = {}
        self.gaps: Dict[str, List[float]] = defaultdict(list)
        self.gap_dropped_long = 0
        self.perf_windows: 'OrderedDict[Tuple[float, float], Dict[str, Any]]' = OrderedDict()
        self.perf_carriers: List[Dict[str, Any]] = []
        self.perf_not_sampled = 0
        self.perf_meta = {
            'writerMode': Counter(),
            'timebaseSource': Counter(),
            'timebaseBasis': Counter(),
            'durationUnit': Counter(),
            'clockStatus': Counter(),
            'resolutionStatus': Counter(),
        }
        self.probe_statuses: Dict[str, Counter] = {}
        self.provider = {
            'torpedoStatusSource': Counter(),
            'torpedoStatusStatus': Counter(),
            'membershipComplete': Counter(),
            'declaredProducer': Counter(),
            'producer': Counter(),
            'producerVerification': Counter(),
            'valueKind': Counter(),
            'semantics': Counter(),
            'dataComponentRows': Counter(),
            'dataComponentFlags': Counter(),
            'uiTorpedoProbeStatus': Counter(),
            'uiTorpedoProbeSource': Counter(),
            'stateProbeCollectionStatus': Counter(),
            'stateProbeJoinStatus': Counter(),
        }
        self.diag_lists = {
            'totalShips': [],
            'positionGetPositionAvailable': [],
            'positionSampledShips': [],
            'positionNotSampledShips': [],
            'positionFallbackNotSampledShips': [],
            'avatarCount': [],
            'avatarLimit': [],
            'playerIndexHits': [],
            'playerVehicleLookups': [],
        }
        self.diag_counters = {
            'positionPolicy': Counter(),
            'playerStatus': Counter(),
            'playerSource': Counter(),
            'avatarStatus': Counter(),
        }
        self._extract_meta(meta)

    def _extract_meta(self, meta: Dict[str, Any]) -> None:
        if not isinstance(meta, dict):
            return
        self.mod = meta.get('mod') if isinstance(meta.get('mod'), dict) else {}
        self.map_info = meta.get('map') if isinstance(meta.get('map'), dict) else {}
        roster = meta.get('roster') if isinstance(meta.get('roster'), list) else []
        self.roster = roster
        self.self_player_id = meta.get('selfPlayerId')
        self.self_ship = None
        for entry in roster:
            if not isinstance(entry, dict):
                continue
            if (self.self_player_id is not None
                    and entry.get('playerId') == self.self_player_id):
                self.self_ship = entry.get('shipName')
                break
        self.roster_ship_types = Counter(
            str(entry.get('shipType')) for entry in roster
            if isinstance(entry, dict) and entry.get('shipType') is not None)
        self.roster_teams = Counter(
            str(entry.get('teamId')) for entry in roster
            if isinstance(entry, dict) and entry.get('teamId') is not None)
        self.roster_ship_names = Counter(
            str(entry.get('shipName')) for entry in roster
            if isinstance(entry, dict) and entry.get('shipName') is not None)
        self.mod_version = str(self.mod.get('version')) if self.mod.get('version') is not None else None
        self.mod_name = str(self.mod.get('name')) if self.mod.get('name') is not None else None
        self.map_name = self.map_info.get('mapName')
        self.game_mode = meta.get('gameMode')
        self.battle_type = meta.get('battleType')
        self.api_version = meta.get('apiVersion')
        self.schema = meta.get('schema')

    def refresh_meta(self, meta: Dict[str, Any]) -> None:
        self.meta = meta
        self._extract_meta(meta)

    def feed_state(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return
        self.states += 1
        if data.get('active') is not True:
            self.inactive_states += 1
            return
        state_battle = _battle_key(data)
        if self.battle_key and state_battle and state_battle != self.battle_key:
            self.battle_mismatch_states += 1
            return
        self.active_states += 1
        ts = data.get('ts')
        if finite_number(ts):
            if self.first_ts is None:
                self.first_ts = float(ts)
            self.last_ts = float(ts)
        else:
            ts = None

        status = data.get('torpedoStatus')
        status = status if isinstance(status, dict) else {}
        membership = status.get('membership')
        membership = membership if isinstance(membership, list) else []
        membership_fields = status.get('membershipFields')
        details = data.get('torpedoes')
        details = details if isinstance(details, list) else []
        sampling = status.get('sampling')
        sampling = sampling if isinstance(sampling, dict) else {}
        classification = sampling.get('classification')
        classification = classification if isinstance(classification, dict) else {}
        self.classification[(str(classification.get('status')),
                             str(classification.get('mapSource')))] += 1

        radius = classification.get('radiusWorld')
        if finite_number(radius) and radius > 0:
            radius = float(radius)
            self.radius_values.append(radius)
            self.radius_sources[str(classification.get('mapSource'))] += 1
            self.radius_inferred[str(classification.get('mapInferred'))] += 1
            short_side = _calibration_short_side(data.get('diag'))
            if short_side is not None:
                self.map_short_sides.append(short_side)
                if radius > 0:
                    self.radius_ratios.append(short_side / radius)
                self.calibration_status['available'] += 1
            else:
                calibration = ((data.get('diag') or {}).get('mapCalibration')
                               if isinstance(data.get('diag'), dict) else None)
                if isinstance(calibration, dict):
                    self.calibration_status[str(calibration.get('status'))] += 1
                else:
                    self.calibration_status['missing'] += 1
            self._last_radius = radius
        else:
            radius = getattr(self, '_last_radius', None)

        membership_count = len(membership)
        detail_count = len(details)
        self.membership_sum += membership_count
        self.detail_sum += detail_count
        self.max_membership = max(self.max_membership, membership_count)
        self.max_detail = max(self.max_detail, detail_count)

        owners_this_state = set()
        membership_ids = set()
        for member in membership:
            identity = _membership_identity(member)
            if identity is not None:
                membership_ids.add(identity)
                self.unique_identities.add(identity)
            owner = _membership_owner(member, membership_fields)
            if owner is not None:
                owners_this_state.add(owner)
                self.unique_owners.add(owner)
        self.max_owners = max(self.max_owners, len(owners_this_state))

        for group in ('high', 'low'):
            group_obj = sampling.get(group)
            group_obj = group_obj if isinstance(group_obj, dict) else {}
            member_count = finite_int(group_obj.get('memberCount'))
            sampled_count = finite_int(group_obj.get('sampledCount'))
            self.sampling_status[(group, str(group_obj.get('status')))] += 1
            if group == 'high':
                self.high_member += member_count
                self.high_sampled += sampled_count
            else:
                self.low_member += member_count
                self.low_sampled += sampled_count

        self_pos = None
        self_obj = data.get('self')
        if isinstance(self_obj, dict):
            self_pos = self_obj.get('position')

        current_details = set()
        for row in details:
            if not isinstance(row, dict):
                continue
            identity = _row_identity(row)
            if identity is not None:
                current_details.add(identity)
                self.unique_identities.add(identity)
            row_sampling = row.get('sampling')
            row_sampling = row_sampling if isinstance(row_sampling, dict) else {}
            group = str(row_sampling.get('group'))
            self.group_rows[group] += 1

            position = row.get('position')
            if not (isinstance(position, (list, tuple)) and len(position) >= 3
                    and all(finite_number(value) for value in position[:3])):
                self.detail_position_missing += 1
                position = None
            self.map_position_status[(group, str(row.get('mapPositionStatus')))] += 1

            motion = row.get('motion')
            motion = motion if isinstance(motion, dict) else {}
            if motion.get('available') is not True:
                self.motion_unavailable[group] += 1
            elif not finite_number(motion.get('horizontalSpeed')):
                self.speed_missing[group] += 1

            self.own_flags[repr(row.get('isOwn'))] += 1
            owner_obj = row.get('owner')
            owner_obj = owner_obj if isinstance(owner_obj, dict) else {}
            self.owner_player_flags[repr(owner_obj.get('isPlayer'))] += 1

            distance = horizon_distance(position, self_pos)
            band = distance_band(distance, radius)
            old_band = l3_band(distance, radius)
            self.all_group_geometry[(group, band)] += 1

            if identity is not None and ts is not None:
                previous = self.last_sample.get(identity)
                if previous is not None:
                    previous_ts = previous[0]
                    gap = float(ts) - previous_ts
                    if gap > 0:
                        if gap <= MAX_CONTINUITY_GAP_SECONDS:
                            self.gaps[group].append(gap)
                            self.gaps['all'].append(gap)
                        else:
                            self.gap_dropped_long += 1
                self.last_sample[identity] = (float(ts), group)

            if (group == 'high' and band in ('mid', 'far')):
                self.cl_high_non_near += 1 if times_equal(
                    classification.get('ts'), ts) else 0
            if group == 'high' and band == 'unknown' and times_equal(
                    classification.get('ts'), ts):
                self.cl_high_unknown_distance += 1
            if group == 'low' and band == 'near' and times_equal(
                    classification.get('ts'), ts):
                self.cl_low_near += 1

        # Handle a classification tick exactly once, after all rows are seen.
        if times_equal(classification.get('ts'), ts):
            self.cl_ticks += 1
            if not finite_number(radius) or radius <= 0:
                self.cl_skipped_ticks += 1
            else:
                self.cl_usable_ticks += 1
                if membership_count == detail_count:
                    self.cl_full_position_ticks += 1
                self.cl_rows += detail_count
                high_obj = sampling.get('high')
                high_obj = high_obj if isinstance(high_obj, dict) else {}
                low_obj = sampling.get('low')
                low_obj = low_obj if isinstance(low_obj, dict) else {}
                self.cl_actual_high_member += finite_int(high_obj.get('memberCount'))
                self.cl_actual_high_sampled += finite_int(high_obj.get('sampledCount'))
                self.cl_actual_low_member += finite_int(low_obj.get('memberCount'))
                self.cl_actual_low_sampled += finite_int(low_obj.get('sampledCount'))
                for row in details:
                    if not isinstance(row, dict):
                        continue
                    row_sampling = row.get('sampling')
                    row_sampling = row_sampling if isinstance(row_sampling, dict) else {}
                    group = str(row_sampling.get('group'))
                    position = row.get('position')
                    distance = horizon_distance(position, self_pos)
                    band = distance_band(distance, radius)
                    old_band = l3_band(distance, radius)
                    self.cl_l5[band] += 1
                    self.cl_l3[old_band] += 1
                    self.cl_group_geometry[(group, band)] += 1
                    if row.get('isOwn') is True:
                        self.cl_own_true += 1
                    elif row.get('isOwn') is None:
                        self.cl_own_none += 1

        # Preserve a sampled identity across non-due ticks, but not across
        # disappearance from membership.
        if membership_ids or current_details:
            for identity in list(self.last_sample):
                if identity not in membership_ids and identity not in current_details:
                    del self.last_sample[identity]

        self._feed_performance(data, membership_count, detail_count, sampling)
        self._feed_probes(data)
        self._feed_diag(data)

    def _feed_performance(self, data: Dict[str, Any], membership_count: int,
                          detail_count: int, sampling: Dict[str, Any]) -> None:
        perf = data.get('performance')
        if not isinstance(perf, dict):
            return
        status = perf.get('status')
        for field in ('writerMode', 'durationUnit', 'clockStatus',
                      'resolutionStatus'):
            if perf.get(field) is not None:
                self.perf_meta[field][str(perf.get(field))] += 1
        timebase = perf.get('timebase')
        if isinstance(timebase, dict):
            if timebase.get('source') is not None:
                self.perf_meta['timebaseSource'][str(timebase.get('source'))] += 1
            if timebase.get('basis') is not None:
                self.perf_meta['timebaseBasis'][str(timebase.get('basis'))] += 1
        if status != 'available':
            self.perf_not_sampled += 1
            return
        key = perf_window_key(perf)
        if key is None:
            return
        if key not in self.perf_windows:
            self.perf_windows[key] = perf
        high_obj = sampling.get('high')
        high_obj = high_obj if isinstance(high_obj, dict) else {}
        low_obj = sampling.get('low')
        low_obj = low_obj if isinstance(low_obj, dict) else {}
        self.perf_carriers.append({
            'start': key[0],
            'end': key[1],
            'stateTs': data.get('ts'),
            'membership': membership_count,
            'details': detail_count,
            'high': finite_int(high_obj.get('memberCount')),
            'low': finite_int(low_obj.get('memberCount')),
        })

    def _feed_probes(self, data: Dict[str, Any]) -> None:
        for key, value in data.items():
            if not isinstance(value, dict):
                continue
            if not (key.endswith('Probe') or key in
                    ('performance', 'identityCandidates')):
                continue
            status = value.get('status')
            if status is not None:
                self.probe_statuses.setdefault(key, Counter())[str(status)] += 1
        status = data.get('torpedoStatus')
        status = status if isinstance(status, dict) else {}
        self.provider['torpedoStatusSource'][str(status.get('source'))] += 1
        self.provider['torpedoStatusStatus'][str(status.get('status'))] += 1
        self.provider['membershipComplete'][str(status.get('membershipComplete'))] += 1

        state_probe = data.get('torpedoStateProbe')
        state_probe = state_probe if isinstance(state_probe, dict) else {}
        for field in ('declaredProducer', 'producer',
                      'producerVerification', 'valueKind', 'semantics'):
            if state_probe.get(field) is not None:
                self.provider[field][str(state_probe.get(field))] += 1
        collection = state_probe.get('collection')
        if isinstance(collection, dict) and collection.get('status') is not None:
            self.provider['stateProbeCollectionStatus'][str(collection.get('status'))] += 1
        if state_probe.get('joinStatus') is not None:
            self.provider['stateProbeJoinStatus'][str(state_probe.get('joinStatus'))] += 1
        rows = state_probe.get('rows')
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                self.provider['dataComponentRows'][str(row.get('dataStatus'))] += 1
                flags = row.get('flags')
                if isinstance(flags, dict):
                    for flag_name, flag_value in flags.items():
                        if isinstance(flag_value, dict):
                            self.provider['dataComponentFlags'][
                                (str(flag_name), str(flag_value.get('status')))] += 1

        ui_probe = data.get('uiTorpedoProbe')
        ui_probe = ui_probe if isinstance(ui_probe, dict) else {}
        self.provider['uiTorpedoProbeStatus'][str(ui_probe.get('status'))] += 1
        self.provider['uiTorpedoProbeSource'][str(ui_probe.get('source'))] += 1

    def _feed_diag(self, data: Dict[str, Any]) -> None:
        diag = data.get('diag')
        if not isinstance(diag, dict):
            return
        total_ships = diag.get('totalShips')
        if finite_number(total_ships):
            self.diag_lists['totalShips'].append(float(total_ships))
        position_reads = diag.get('positionReads')
        position_reads = position_reads if isinstance(position_reads, dict) else {}
        self.diag_counters['positionPolicy'][
            str(position_reads.get('readPolicy'))] += 1
        for field, target in (
                ('getPosition:available', 'positionGetPositionAvailable'),
                ('sampledShips', 'positionSampledShips'),
                ('notSampledShips', 'positionNotSampledShips'),
                ('fallbackNotSampledShips', 'positionFallbackNotSampledShips')):
            value = position_reads.get(field)
            if finite_number(value):
                self.diag_lists[target].append(float(value))
        player_reads = diag.get('playerReads')
        player_reads = player_reads if isinstance(player_reads, dict) else {}
        self.diag_counters['playerStatus'][str(player_reads.get('sampleStatus'))] += 1
        self.diag_counters['playerSource'][str(player_reads.get('source'))] += 1
        for field, target in (('indexHits', 'playerIndexHits'),
                              ('vehicleLookups', 'playerVehicleLookups')):
            value = player_reads.get(field)
            if finite_number(value):
                self.diag_lists[target].append(float(value))
        avatar = diag.get('avatarSnapshotStatus')
        avatar = avatar if isinstance(avatar, dict) else {}
        self.diag_counters['avatarStatus'][str(avatar.get('status'))] += 1
        for field, target in (('count', 'avatarCount'), ('limit', 'avatarLimit')):
            value = avatar.get(field)
            if finite_number(value):
                self.diag_lists[target].append(float(value))

    def finish(self) -> Dict[str, Any]:
        included = (self.states >= 2
                    and self.active_states >= MIN_SESSION_ACTIVE_STATES)
        if included:
            exclusion_reason = None
        elif self.active_states == 0:
            exclusion_reason = 'stale/inactive meta session: no active states'
        else:
            exclusion_reason = 'too few active states'
        result = {
            'session': self.label,
            'included': included,
            'exclusionReason': exclusion_reason,
            'metaTs': self.meta_ts,
            'states': self.states,
            'inactiveStates': self.inactive_states,
            'activeStates': self.active_states,
            'battleMismatchStates': self.battle_mismatch_states,
            'firstTs': self.first_ts,
            'lastTs': self.last_ts,
            'durationSeconds': (self.last_ts - self.first_ts
                                if self.first_ts is not None
                                and self.last_ts is not None else None),
            'modVersion': self.mod_version,
            'modName': self.mod_name,
            'mapName': self.map_name,
            'gameMode': self.game_mode,
            'battleType': self.battle_type,
            'apiVersion': self.api_version,
            'schema': self.schema,
            'rosterCount': len(self.roster),
            'rosterShipTypes': counter_to_dict(self.roster_ship_types),
            'rosterTeams': counter_to_dict(self.roster_teams),
            'rosterShipNames': counter_to_dict(self.roster_ship_names),
            'selfShip': self.self_ship,
            'battleIdRecorded': bool(self.battle_key),
            'membershipRowsSum': self.membership_sum,
            'detailRowsSum': self.detail_sum,
            'maxConcurrentMembership': self.max_membership,
            'maxConcurrentDetail': self.max_detail,
            'maxOwnersPerState': self.max_owners,
            'uniqueIdentities': len(self.unique_identities),
            'uniqueOwners': len(self.unique_owners),
            'groupDetailRows': counter_to_dict(self.group_rows),
            'samplingStatus': counter_to_dict(self.sampling_status),
            'highMemberSum': self.high_member,
            'highSampledSum': self.high_sampled,
            'lowMemberSum': self.low_member,
            'lowSampledSum': self.low_sampled,
            'omittedRows': self.membership_sum - self.detail_sum,
            'omittedOverMembership': _ratio(
                self.membership_sum - self.detail_sum, self.membership_sum),
            'omittedOverDetail': _ratio(
                self.membership_sum - self.detail_sum, self.detail_sum),
            'highOmitted': self.high_member - self.high_sampled,
            'highOmissionRate': _ratio(
                self.high_member - self.high_sampled, self.high_member),
            'lowOmitted': self.low_member - self.low_sampled,
            'lowOmissionRate': _ratio(
                self.low_member - self.low_sampled, self.low_member),
            'classification': counter_to_dict(self.classification),
            'radiusWorld': _distribution_list(self.radius_values),
            'radiusSourceWorld': _distribution_list(self.map_short_sides),
            'radiusDivisor': _ratio_distribution(self.radius_ratios),
            'radiusSource': counter_to_dict(self.radius_sources),
            'radiusInferred': counter_to_dict(self.radius_inferred),
            'calibrationStatus': counter_to_dict(self.calibration_status),
            'classificationTicks': {
                'total': self.cl_ticks,
                'usable': self.cl_usable_ticks,
                'skipped': self.cl_skipped_ticks,
                'fullPositionTicks': self.cl_full_position_ticks,
                'rows': self.cl_rows,
                'l5': _with_ratio(counter_to_dict(self.cl_l5), self.cl_rows),
                'l3': _with_ratio(counter_to_dict(self.cl_l3), self.cl_rows),
                'groupGeometry': counter_to_dict(self.cl_group_geometry),
                'actualHighMember': self.cl_actual_high_member,
                'actualHighSampled': self.cl_actual_high_sampled,
                'actualLowMember': self.cl_actual_low_member,
                'actualLowSampled': self.cl_actual_low_sampled,
                'ownTrue': self.cl_own_true,
                'ownNone': self.cl_own_none,
                'highNonNear': self.cl_high_non_near,
                'highUnknownDistance': self.cl_high_unknown_distance,
                'lowNear': self.cl_low_near,
            },
            'allSampleGroupGeometry': counter_to_dict(self.all_group_geometry),
            'ownFlags': counter_to_dict(self.own_flags),
            'ownerPlayerFlags': counter_to_dict(self.owner_player_flags),
            'positionMissing': self.detail_position_missing,
            'mapPositionStatus': counter_to_dict(self.map_position_status),
            'motionUnavailable': counter_to_dict(self.motion_unavailable),
            'speedMissing': counter_to_dict(self.speed_missing),
            'intervals': {
                'all': distribution(self.gaps.get('all', [])),
                'high': distribution(self.gaps.get('high', [])),
                'low': distribution(self.gaps.get('low', [])),
                'droppedLong': self.gap_dropped_long,
            },
            'performance': self._performance_summary(),
            'probes': {name: counter_to_dict(counter)
                       for name, counter in sorted(self.probe_statuses.items())},
            'provider': _counter_mapping_to_dict(self.provider),
            'readMetadata': self._read_metadata_summary(),
        }
        return result

    def _performance_summary(self) -> Dict[str, Any]:
        windows = list(self.perf_windows.values())
        phase_stats = {}
        for phase_name in PHASES:
            means = [phase_mean((window.get('phases') or {}).get(phase_name))
                     for window in windows]
            means = [value for value in means if value is not None]
            counts = [
                finite_int(((window.get('phases') or {}).get(phase_name) or {}).get('count'))
                for window in windows
                if isinstance((window.get('phases') or {}).get(phase_name), dict)
            ]
            max_values = [
                ((window.get('phases') or {}).get(phase_name) or {}).get('max')
                for window in windows
                if isinstance((window.get('phases') or {}).get(phase_name), dict)
            ]
            max_values = [value for value in max_values if finite_number(value)]
            phase_stats[phase_name] = {
                'weightedMean': weighted_phase_mean(windows, phase_name),
                'totalCount': sum(counts),
                'maxSingle': max(max_values) if max_values else None,
                'windowMeanCount': len(means),
                'windowMeanMin': min(means) if means else None,
                'windowMeanMedian': statistics.median(means) if means else None,
                'windowMeanP95': quantile(means, 0.95),
                'windowMeanMax': max(means) if means else None,
            }

        heavy_window = None
        heavy_start = None
        heavy_end = None
        for key, window in self.perf_windows.items():
            mean = phase_mean((window.get('phases') or {}).get('state_cycle_total'))
            if mean is None:
                continue
            if heavy_window is None or mean > heavy_window[0]:
                heavy_window = (mean, window)
                heavy_start, heavy_end = key
        heavy = None
        if heavy_window is not None:
            _, window = heavy_window
            heavy = {
                'start': heavy_start,
                'end': heavy_end,
                'durationSeconds': (heavy_end - heavy_start
                                    if heavy_start is not None
                                    and heavy_end is not None else None),
                'windowCycleMean': heavy_window[0],
                'phases': {
                    phase_name: {
                        'mean': phase_mean((window.get('phases') or {}).get(phase_name)),
                        'max': ((window.get('phases') or {}).get(phase_name) or {}).get('max'),
                        'count': ((window.get('phases') or {}).get(phase_name) or {}).get('count'),
                    }
                    for phase_name in PHASES
                },
            }

        carrier_by_key = {}
        for carrier in self.perf_carriers:
            key = (carrier['start'], carrier['end'])
            carrier_by_key.setdefault(key, carrier)
        bands = []
        for name, low, high in BAND_DEFINITIONS:
            selected_keys = []
            membership_values = []
            for key, carrier in carrier_by_key.items():
                membership = carrier.get('membership')
                if not finite_number(membership):
                    continue
                if membership < low:
                    continue
                if high is not None and membership > high:
                    continue
                selected_keys.append(key)
                membership_values.append(float(membership))
            selected_windows = [self.perf_windows[key] for key in selected_keys
                                if key in self.perf_windows]
            if not selected_keys:
                continue
            mean_membership = (statistics.mean(membership_values)
                               if membership_values else None)
            weighted = {
                phase_name: weighted_phase_mean(selected_windows, phase_name)
                for phase_name in PHASES
            }
            torpedo_mean = weighted.get('torpedoes')
            bands.append({
                'name': name,
                'windowCount': len(selected_keys),
                'meanMembership': mean_membership,
                'weightedMeans': weighted,
                'torpedoesMsPerFish': (torpedo_mean / mean_membership
                                       if torpedo_mean is not None
                                       and mean_membership else None),
            })

        offsets = []
        for carrier in self.perf_carriers:
            end = carrier.get('end')
            state_ts = carrier.get('stateTs')
            if finite_number(end) and finite_number(state_ts):
                offsets.append(float(state_ts) - float(end))
        offset_stats = distribution(offsets) if offsets else distribution([])

        starts = [key[0] for key in self.perf_windows]
        ends = [key[1] for key in self.perf_windows]
        memberships = [carrier.get('membership')
                       for carrier in carrier_by_key.values()
                       if finite_number(carrier.get('membership'))]
        return {
            'uniqueWindows': len(self.perf_windows),
            'carrierRows': len(self.perf_carriers),
            'duplicateCarrierRows': len(self.perf_carriers) - len(self.perf_windows),
            'notSampledStates': self.perf_not_sampled,
            'sampleStartMin': min(starts) if starts else None,
            'sampleEndMax': max(ends) if ends else None,
            'zeroMembershipWindows': sum(1 for value in memberships if value == 0),
            'positiveMembershipWindows': sum(1 for value in memberships if value > 0),
            'phaseStats': phase_stats,
            'heavyWindow': heavy,
            'bands': bands,
            'stateTsMinusSampleEnd': offset_stats,
            'writerMode': counter_to_dict(self.perf_meta['writerMode']),
            'timebaseSource': counter_to_dict(self.perf_meta['timebaseSource']),
            'timebaseBasis': counter_to_dict(self.perf_meta['timebaseBasis']),
            'durationUnit': counter_to_dict(self.perf_meta['durationUnit']),
            'clockStatus': counter_to_dict(self.perf_meta['clockStatus']),
            'resolutionStatus': counter_to_dict(self.perf_meta['resolutionStatus']),
        }

    def _read_metadata_summary(self) -> Dict[str, Any]:
        return {
            'totalShips': _distribution_list(self.diag_lists['totalShips']),
            'positionGetPositionAvailable': _distribution_list(
                self.diag_lists['positionGetPositionAvailable']),
            'positionSampledShips': _distribution_list(
                self.diag_lists['positionSampledShips']),
            'positionNotSampledShips': _distribution_list(
                self.diag_lists['positionNotSampledShips']),
            'positionFallbackNotSampledShips': _distribution_list(
                self.diag_lists['positionFallbackNotSampledShips']),
            'avatarCount': _distribution_list(self.diag_lists['avatarCount']),
            'avatarLimit': _distribution_list(self.diag_lists['avatarLimit']),
            'playerIndexHits': _distribution_list(
                self.diag_lists['playerIndexHits']),
            'playerVehicleLookups': _distribution_list(
                self.diag_lists['playerVehicleLookups']),
            'positionPolicy': counter_to_dict(self.diag_counters['positionPolicy']),
            'playerStatus': counter_to_dict(self.diag_counters['playerStatus']),
            'playerSource': counter_to_dict(self.diag_counters['playerSource']),
            'avatarStatus': counter_to_dict(self.diag_counters['avatarStatus']),
        }


def _ratio(numerator: Any, denominator: Any) -> Optional[float]:
    if not finite_number(numerator) or not finite_number(denominator):
        return None
    if denominator == 0:
        return None
    value = float(numerator) / float(denominator)
    return value if math.isfinite(value) else None


def _distribution_list(values: Sequence[float]) -> Dict[str, Any]:
    if not values:
        return {'count': 0, 'min': None, 'median': None, 'max': None}
    return {
        'count': len(values),
        'min': min(values),
        'median': statistics.median(values),
        'max': max(values),
    }


def _ratio_distribution(values: Sequence[float]) -> Dict[str, Any]:
    if not values:
        return {'count': 0, 'min': None, 'median': None, 'max': None,
                'unique': {}}
    unique = Counter(round(float(value), 9) for value in values)
    return {
        'count': len(values),
        'min': min(values),
        'median': statistics.median(values),
        'max': max(values),
        'unique': {str(key): int(count)
                   for key, count in sorted(unique.items())},
    }


def _with_ratio(counter_dict: Dict[str, int], total: int) -> Dict[str, Any]:
    return {
        'counts': counter_dict,
        'ratios': {key: _ratio(value, total)
                   for key, value in counter_dict.items()},
    }


def _counter_mapping_to_dict(mapping: Dict[str, Counter]) -> Dict[str, Any]:
    result = {}
    for key, counter in sorted(mapping.items()):
        if counter and all(isinstance(item, tuple) for item in counter):
            result[key] = {
                '%s|%s' % item: int(value) for item, value in sorted(
                    counter.items(), key=lambda pair: (str(pair[0]), str(pair[1])))
            }
        else:
            result[key] = counter_to_dict(counter)
    return result


class RecordingAnalyzer:
    def __init__(self):
        self.sessions: List[Session] = []
        self.current: Optional[Session] = None
        self.meta_count = 0
        self.state_count = 0
        self.bad_json = 0
        self.meta_refreshes = 0
        self.battle_keys = set()

    def feed(self, record: Any) -> None:
        if not isinstance(record, dict):
            return
        kind = record.get('kind')
        data = record.get('data')
        if not isinstance(data, dict):
            return
        if kind == 'meta':
            self.meta_count += 1
            key = _battle_key(data)
            if key:
                self.battle_keys.add(key)
            if (self.current is not None and key is not None
                    and self.current.battle_key == key
                    and self.current.states > 0):
                self.current.refresh_meta(data)
                self.meta_refreshes += 1
                return
            session = Session(len(self.sessions) + 1, data)
            self.sessions.append(session)
            self.current = session
        elif kind == 'state':
            self.state_count += 1
            if self.current is None:
                self.current = Session(1, {})
                self.sessions.append(self.current)
            self.current.feed_state(data)

    def finish(self, recording: Optional[str] = None) -> Dict[str, Any]:
        sessions = [session.finish() for session in self.sessions]
        included = [session for session in sessions if session['included']]
        result = {
            'recording': os.path.basename(recording) if recording else None,
            'recordingBytes': (os.path.getsize(recording)
                               if recording and os.path.exists(recording) else None),
            'metaCount': self.meta_count,
            'stateCount': self.state_count,
            'badJsonLines': self.bad_json,
            'metaRefreshes': self.meta_refreshes,
            'battleIdCount': len(self.battle_keys),
            'sessionCount': len(sessions),
            'includedSessionCount': len(included),
            'sessions': sessions,
        }
        return result


def analyze_recording(path: str) -> Dict[str, Any]:
    analyzer = RecordingAnalyzer()
    with open(path, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                analyzer.bad_json += 1
                continue
            analyzer.feed(record)
    return analyzer.finish(path)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='Anonymised offline analysis of the B48 L/5 JSONL record.')
    parser.add_argument('--recording', default='recordings/without-atm-b48.jsonl',
                        help='private JSONL path (never printed raw)')
    parser.add_argument('--json-output', default=None,
                        help='optional path for the aggregate JSON')
    args = parser.parse_args(argv)
    result = analyze_recording(args.recording)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False)
    if args.json_output:
        with open(args.json_output, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.write('\n')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())