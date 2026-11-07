"""Offline, anonymised investigation of B49/B48 classification gaps.

Reads a private JSONL telemetry recording and correlates
``torpedoStatus.sampling.classification.selfPositionStatus`` with the
corresponding ``self`` snapshot fields and ``diag.mapCalibration`` state.
No runtime source, game, recorder, or installation is touched.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from typing import Any, Dict, List, Optional


def finite_number(value: Any) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _self_position_present(self_state: Any) -> Optional[bool]:
    if not isinstance(self_state, dict):
        return None
    pos = self_state.get('position')
    if not isinstance(pos, (list, tuple)) or len(pos) < 3:
        return False
    return all(finite_number(pos[i]) for i in (0, 1, 2))


def _calibration_status(diag: Any) -> Any:
    if not isinstance(diag, dict):
        return None
    calibration = diag.get('mapCalibration')
    if not isinstance(calibration, dict):
        return None
    return calibration.get('status')


def _classification_reason(torpedo_status: Any) -> Any:
    if not isinstance(torpedo_status, dict):
        return None
    sampling = torpedo_status.get('sampling')
    if not isinstance(sampling, dict):
        return None
    classification = sampling.get('classification')
    if not isinstance(classification, dict):
        return None
    return classification.get('reason')


def _self_position_status(torpedo_status: Any) -> Any:
    if not isinstance(torpedo_status, dict):
        return None
    sampling = torpedo_status.get('sampling')
    if not isinstance(sampling, dict):
        return None
    classification = sampling.get('classification')
    if not isinstance(classification, dict):
        return None
    return classification.get('selfPositionStatus')


def _safe_keys(obj: Any) -> List[str]:
    if not isinstance(obj, dict):
        return []
    return sorted(str(k) for k in obj.keys())


def _team_class(owner_team_id: Any, self_team_id: Any) -> str:
    """Strict ownerTeamId/self.teamId comparison; never infer from ownerId."""
    if owner_team_id is None or self_team_id is None:
        return 'unknownTeam'
    return 'sameTeam' if owner_team_id == self_team_id else 'enemyTeam'


def _owner_stats(torpedoes: List[Any], self_player_id: Any,
                 ship_index: Dict[Any, Dict[str, Any]],
                 self_vehicle_ids: set, self_team_id: Any) -> Dict[str, Any]:
    total = 0
    owner_present = 0
    is_player_types: Counter = Counter()
    is_player_values: Counter = Counter()
    subtype_values: Counter = Counter()
    field_presence: Counter = Counter()
    non_null_fields: Counter = Counter()
    team_class_counter: Counter = Counter()
    owner_id_self_matches = 0
    owner_id_ship_player_matches = 0
    owner_id_ship_vehicle_matches = 0
    owner_id_self_vehicle_matches = 0
    owner_ids_seen = set()
    for row in torpedoes:
        if not isinstance(row, dict):
            continue
        total += 1
        owner_id = row.get('ownerId')
        owner_team_id = row.get('ownerTeamId')
        team_class_counter[_team_class(owner_team_id, self_team_id)] += 1
        if owner_id is not None:
            owner_ids_seen.add(owner_id)
        if owner_id == self_player_id:
            owner_id_self_matches += 1
        if owner_id in self_vehicle_ids:
            owner_id_self_vehicle_matches += 1
        ship = ship_index.get(owner_id)
        if isinstance(ship, dict):
            if ship.get('playerId') == owner_id:
                owner_id_ship_player_matches += 1
            if ship.get('vehicleId') == owner_id:
                owner_id_ship_vehicle_matches += 1
        owner = row.get('owner')
        if not isinstance(owner, dict):
            continue
        owner_present += 1
        for key, value in owner.items():
            field_presence[key] += 1
            if value is not None:
                non_null_fields[key] += 1
        is_player = owner.get('isPlayer')
        is_player_types[type(is_player).__name__ if is_player is not None else 'None'] += 1
        is_player_values[str(is_player)] += 1
        subtype = owner.get('subtype')
        subtype_values[subtype if subtype is not None else 'None'] += 1
    return {
        'rowCount': total,
        'ownerPresent': owner_present,
        'teamClass': dict(team_class_counter),
        'isPlayerTypes': dict(is_player_types),
        'isPlayerValues': dict(is_player_values),
        'subtypeValues': dict(subtype_values),
        'fieldPresence': dict(field_presence),
        'nonNullFields': dict(non_null_fields),
        'selfPlayerIdSeenAsOwnerId': (self_player_id in owner_ids_seen),
        'ownerIdSelfMatchCount': owner_id_self_matches,
        'ownerIdShipPlayerMatchCount': owner_id_ship_player_matches,
        'ownerIdShipVehicleMatchCount': owner_id_ship_vehicle_matches,
        'ownerIdSelfVehicleMatchCount': owner_id_self_vehicle_matches,
    }


def _self_vehicle_ids(ships: List[Any], self_player_id: Any) -> set:
    ids: set = set()
    if not isinstance(ships, list) or self_player_id is None:
        return ids
    for ship in ships:
        if not isinstance(ship, dict):
            continue
        if ship.get('playerId') == self_player_id:
            vehicle_id = ship.get('vehicleId')
            if vehicle_id is not None:
                ids.add(vehicle_id)
    return ids


def _ship_index(ships: List[Any]) -> Dict[Any, Dict[str, Any]]:
    index: Dict[Any, Dict[str, Any]] = {}
    if not isinstance(ships, list):
        return index
    for ship in ships:
        if not isinstance(ship, dict):
            continue
        for key in ('playerId', 'vehicleId'):
            value = ship.get(key)
            if value is not None and value not in index:
                index[value] = ship
    return index


def _health_alive_summary(self_state: Any) -> Dict[str, Any]:
    if not isinstance(self_state, dict):
        return {'available': False}
    summary: Dict[str, Any] = {}
    for key in ('health', 'maxHealth', 'isObserver', 'teamId',
                'yaw', 'speed', 'isVisible', 'isShipVisible'):
        value = self_state.get(key)
        if key in ('health', 'maxHealth') and finite_number(value):
            summary[key] = float(value)
        elif key in ('isObserver',) and isinstance(value, bool):
            summary[key] = value
        elif value is not None:
            summary[key] = value
    health = self_state.get('health')
    max_health = self_state.get('maxHealth')
    if finite_number(health) and finite_number(max_health) and max_health > 0:
        summary['healthRatio'] = float(health) / float(max_health)
    return summary


def _is_classification_due(torpedo_status: Any, ts: Any) -> bool:
    if not isinstance(torpedo_status, dict):
        return False
    sampling = torpedo_status.get('sampling')
    if not isinstance(sampling, dict):
        return False
    classification = sampling.get('classification')
    if not isinstance(classification, dict):
        return False
    if classification.get('due') is True:
        return True
    if classification.get('ts') == ts:
        return True
    return False


def investigate(recording_path: str) -> Dict[str, Any]:
    total = active = with_torpedoes = 0
    missing_states: List[Dict[str, Any]] = []
    self_position_status_counter: Counter = Counter()
    classification_reason_counter: Counter = Counter()
    calibration_status_counter: Counter = Counter()
    self_position_present_counter: Counter = Counter()
    self_position_false_summary: Counter = Counter()
    self_key_set: Counter = Counter()
    classification_ticks = 0
    classification_ticks_missing_self = 0
    owner_stats_accum = {
        'rowCount': 0,
        'ownerPresent': 0,
        'teamClass': Counter(),
        'isPlayerTypes': Counter(),
        'isPlayerValues': Counter(),
        'subtypeValues': Counter(),
        'fieldPresence': Counter(),
        'nonNullFields': Counter(),
        'selfPlayerIdSeenAsOwnerId': False,
        'ownerIdSelfMatchCount': 0,
        'ownerIdShipPlayerMatchCount': 0,
        'ownerIdShipVehicleMatchCount': 0,
        'ownerIdSelfVehicleMatchCount': 0,
    }

    with open(recording_path, 'r', encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception:
                continue
            if record.get('kind') != 'state':
                continue
            total += 1
            data = record.get('data', {}) or {}
            if not data.get('active'):
                continue
            active += 1

            self_state = data.get('self')
            diag = data.get('diag')
            torpedo_status = data.get('torpedoStatus')
            torpedoes = data.get('torpedoes') or []
            membership = (torpedo_status.get('membership') or []
                          if isinstance(torpedo_status, dict) else [])
            ts = data.get('ts')

            pos_present = _self_position_present(self_state)
            self_position_present_counter[pos_present] += 1
            if pos_present is False and isinstance(self_state, dict):
                self_position_false_summary[
                    'isObserver=%s' % self_state.get('isObserver')] += 1
                self_position_false_summary[
                    'hasHealth=%s' % ('health' in self_state)] += 1
                self_position_false_summary[
                    'hasAlive=%s' % ('alive' in self_state)] += 1
            if isinstance(self_state, dict):
                self_key_set.update(_safe_keys(self_state))

            cal_status = _calibration_status(diag)
            calibration_status_counter[cal_status] += 1

            cls_reason = _classification_reason(torpedo_status)
            classification_reason_counter[cls_reason] += 1

            sp_status = _self_position_status(torpedo_status)
            self_position_status_counter[sp_status] += 1

            if torpedoes or membership:
                with_torpedoes += 1

            self_player_id = (self_state.get('playerId')
                              if isinstance(self_state, dict) else None)
            self_team_id = (self_state.get('teamId')
                            if isinstance(self_state, dict) else None)
            ship_index = _ship_index(data.get('ships'))
            self_vehicle_ids_set = _self_vehicle_ids(data.get('ships'), self_player_id)
            row_stats = _owner_stats(torpedoes, self_player_id, ship_index,
                                     self_vehicle_ids_set, self_team_id)
            owner_stats_accum['rowCount'] += row_stats['rowCount']
            owner_stats_accum['ownerPresent'] += row_stats['ownerPresent']
            owner_stats_accum['teamClass'].update(row_stats['teamClass'])
            owner_stats_accum['isPlayerTypes'].update(row_stats['isPlayerTypes'])
            owner_stats_accum['isPlayerValues'].update(row_stats['isPlayerValues'])
            owner_stats_accum['subtypeValues'].update(row_stats['subtypeValues'])
            owner_stats_accum['fieldPresence'].update(row_stats['fieldPresence'])
            owner_stats_accum['nonNullFields'].update(row_stats['nonNullFields'])
            if row_stats['selfPlayerIdSeenAsOwnerId']:
                owner_stats_accum['selfPlayerIdSeenAsOwnerId'] = True
            owner_stats_accum['ownerIdSelfMatchCount'] += row_stats['ownerIdSelfMatchCount']
            owner_stats_accum['ownerIdShipPlayerMatchCount'] += row_stats['ownerIdShipPlayerMatchCount']
            owner_stats_accum['ownerIdShipVehicleMatchCount'] += row_stats['ownerIdShipVehicleMatchCount']
            owner_stats_accum['ownerIdSelfVehicleMatchCount'] += row_stats['ownerIdSelfVehicleMatchCount']

            if _is_classification_due(torpedo_status, ts):
                classification_ticks += 1
                if pos_present is not True or cal_status != 'available':
                    classification_ticks_missing_self += 1
                    missing_states.append({
                        'ts': ts,
                        'selfPositionPresent': pos_present,
                        'selfSummary': _health_alive_summary(self_state),
                        'selfKeys': _safe_keys(self_state),
                        'calibrationStatus': cal_status,
                        'classificationReason': cls_reason,
                        'torpedoCount': len(torpedoes),
                        'membershipCount': len(membership),
                    })

    return {
        'totalStates': total,
        'activeStates': active,
        'activeStatesWithTorpedoes': with_torpedoes,
        'classificationTicks': classification_ticks,
        'classificationTicksMissingContext': classification_ticks_missing_self,
        'selfPositionStatus': dict(self_position_status_counter),
        'classificationReason': dict(classification_reason_counter),
        'calibrationStatus': dict(calibration_status_counter),
        'selfPositionPresent': dict(self_position_present_counter),
        'selfPositionFalseSummary': dict(self_position_false_summary),
        'selfKeyDistribution': dict(self_key_set),
        'missingContextStates': missing_states,
        'ownerFieldStats': {
            'rowCount': owner_stats_accum['rowCount'],
            'ownerPresent': owner_stats_accum['ownerPresent'],
            'teamClass': dict(owner_stats_accum['teamClass']),
            'isPlayerTypes': dict(owner_stats_accum['isPlayerTypes']),
            'isPlayerValues': dict(owner_stats_accum['isPlayerValues']),
            'subtypeValues': dict(owner_stats_accum['subtypeValues']),
            'fieldPresence': dict(owner_stats_accum['fieldPresence']),
            'nonNullFields': dict(owner_stats_accum['nonNullFields']),
            'selfPlayerIdSeenAsOwnerId': owner_stats_accum['selfPlayerIdSeenAsOwnerId'],
            'ownerIdSelfMatchCount': owner_stats_accum['ownerIdSelfMatchCount'],
            'ownerIdShipPlayerMatchCount': owner_stats_accum['ownerIdShipPlayerMatchCount'],
            'ownerIdShipVehicleMatchCount': owner_stats_accum['ownerIdShipVehicleMatchCount'],
            'ownerIdSelfVehicleMatchCount': owner_stats_accum['ownerIdSelfVehicleMatchCount'],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Anonymised classification-gap investigation.')
    parser.add_argument('--recording', required=True,
                        help='Path to a JSONL telemetry recording.')
    parser.add_argument('--output', default=None,
                        help='Optional output JSON path (UTF-8).')
    args = parser.parse_args()

    result = investigate(args.recording)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as fh:
            fh.write(text)
    else:
        print(text)


if __name__ == '__main__':
    main()
