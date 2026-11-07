#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline aggregate analysis of self identity candidates vs torpedo ownerId.

Reads a recording (JSONL of state snapshots, optionally wrapped in
``{"kind":"state","data":{...}}``) and compares the raw values of each self
identity candidate against the ``ownerId`` of the torpedo rows in the same
snapshot.  Output is anonymous aggregate counts only; raw IDs are not echoed.
"""
import json
import sys
from collections import Counter
from pathlib import Path


CANDIDATE_NAMESPACES = (
    'playerId', 'shipId', 'uiId', '_Ship__id', 'id', 'vehicleId')


def _exact_scalar(a, b):
    if a is None or b is None:
        return False
    try:
        if isinstance(a, bool) or isinstance(b, bool):
            return False
        if type(a) is not type(b):
            return False
        if isinstance(a, (int, float)):
            if a != a or b != b:
                return False
            if a == b:
                return True
        return a == b
    except Exception:
        return False


def _unwrap_state(line_obj):
    if isinstance(line_obj, dict) and 'data' in line_obj:
        return line_obj['data']
    return line_obj


def _validate_state(state):
    reasons = []
    if not isinstance(state, dict):
        reasons.append('stateNotDict')
        return reasons
    if state.get('schema') != 1:
        reasons.append('schemaMismatch')
    if state.get('apiVersion') != '1.0':
        reasons.append('apiVersionMismatch')
    return reasons


def _candidate_value(candidate):
    if not isinstance(candidate, dict):
        return None
    if candidate.get('status') != 'available':
        return None
    raw = candidate.get('raw')
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        if raw != raw:
            return None
        return raw
    return None


def analyze(recording_path):
    path = Path(recording_path)
    if not path.is_file():
        raise SystemExit('Recording not found: ' + str(path))

    total_lines = 0
    valid_states = 0
    invalid_states = 0
    session_mismatches = 0
    type_mismatches = 0
    mod_version = None
    battle_id = None
    seen_battle_ids = set()
    seen_mod_versions = set()

    candidate_counts = {ns: Counter() for ns in CANDIDATE_NAMESPACES}
    candidate_match_rows = {ns: Counter() for ns in CANDIDATE_NAMESPACES}
    cross_consistency = Counter()

    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                invalid_states += 1
                continue

            if isinstance(obj, dict) and obj.get('kind') not in (None, 'state'):
                type_mismatches += 1
                continue

            state = _unwrap_state(obj)
            reasons = _validate_state(state)
            if reasons:
                invalid_states += 1
                continue

            valid_states += 1

            current_battle = state.get('battleId')
            if current_battle is not None:
                if battle_id is None:
                    battle_id = current_battle
                    seen_battle_ids.add(current_battle)
                elif current_battle not in seen_battle_ids:
                    session_mismatches += 1
                    seen_battle_ids.add(current_battle)

            mod = state.get('mod')
            if isinstance(mod, dict):
                current_version = mod.get('version')
                if current_version is not None:
                    if mod_version is None:
                        mod_version = current_version
                        seen_mod_versions.add(current_version)
                    elif current_version not in seen_mod_versions:
                        session_mismatches += 1
                        seen_mod_versions.add(current_version)

            self_state = state.get('self') or {}
            candidates = self_state.get('identityCandidates') or []
            candidate_by_ns = {}
            available_values = []
            for cnd in candidates:
                ns = cnd.get('namespace')
                if ns in CANDIDATE_NAMESPACES and ns not in candidate_by_ns:
                    candidate_by_ns[ns] = cnd
                    val = _candidate_value(cnd)
                    if val is not None:
                        available_values.append(val)

            if len(available_values) >= 2:
                if all(v == available_values[0] for v in available_values):
                    cross_consistency['agree'] += 1
                else:
                    cross_consistency['disagree'] += 1
            else:
                cross_consistency['insufficient'] += 1

            torpedoes = state.get('torpedoes')
            if not isinstance(torpedoes, list):
                torpedoes = []

            for ns in CANDIDATE_NAMESPACES:
                candidate = candidate_by_ns.get(ns)
                counts = candidate_counts[ns]
                row_counts = candidate_match_rows[ns]
                if candidate is None:
                    counts['candidateUnavailable'] += 1
                    continue
                value = _candidate_value(candidate)
                if value is None:
                    counts['candidateUnavailable'] += 1
                    continue
                counts['available'] += 1
                if not torpedoes:
                    counts['noTorpedoes'] += 1
                    continue
                matched = False
                for row in torpedoes:
                    if not isinstance(row, dict):
                        continue
                    owner_id = row.get('ownerId')
                    if _exact_scalar(owner_id, value):
                        matched = True
                        is_own = row.get('isOwn')
                        if is_own is True:
                            row_counts['isOwnTrue'] += 1
                        elif is_own is False:
                            row_counts['isOwnFalse'] += 1
                        else:
                            row_counts['isOwnNone'] += 1
                if matched:
                    counts['match'] += 1
                else:
                    counts['mismatch'] += 1

    summary = {
        'recording': str(path),
        'totalLines': total_lines,
        'validStates': valid_states,
        'invalidStates': invalid_states,
        'sessionMismatches': session_mismatches,
        'typeMismatches': type_mismatches,
        'battleId': battle_id,
        'modVersion': mod_version,
        'crossCandidateConsistency': dict(cross_consistency),
        'candidates': {},
    }

    for ns in CANDIDATE_NAMESPACES:
        counts = candidate_counts[ns]
        rows = candidate_match_rows[ns]
        match_count = counts.get('match', 0)
        mismatch_count = counts.get('mismatch', 0)
        if match_count > 0 and mismatch_count == 0:
            consistency = 'consistentMatch'
        elif mismatch_count > 0 and match_count == 0:
            consistency = 'consistentMismatch'
        elif match_count > 0 and mismatch_count > 0:
            consistency = 'mixed'
        else:
            consistency = 'insufficient'
        summary['candidates'][ns] = {
            'states': counts.get('candidateUnavailable', 0) + counts.get('available', 0),
            'available': counts.get('available', 0),
            'candidateUnavailable': counts.get('candidateUnavailable', 0),
            'noTorpedoes': counts.get('noTorpedoes', 0),
            'match': match_count,
            'mismatch': mismatch_count,
            'matchConsistency': consistency,
            'isOwnTrue': rows.get('isOwnTrue', 0),
            'isOwnFalse': rows.get('isOwnFalse', 0),
            'isOwnNone': rows.get('isOwnNone', 0),
        }

    return summary


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1:
        raise SystemExit('Usage: analyze_self_id_candidates.py <recording.jsonl>')
    summary = analyze(argv[0])
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
