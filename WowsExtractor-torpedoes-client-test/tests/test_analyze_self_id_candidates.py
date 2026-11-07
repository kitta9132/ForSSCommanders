"""Offline tests for the self-id candidate analyzer."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from analyze_self_id_candidates import analyze


ROOT = Path(__file__).resolve().parents[1]


def _state(battle_id='b1', mod_version='0.3.43-self-id-observation',
           self_candidates=None, torpedoes=None):
    self_candidates = self_candidates or []
    torpedoes = torpedoes or []
    return {
        'schema': 1,
        'apiVersion': '1.0',
        'battleId': battle_id,
        'mod': {'name': 'WowsExtractor', 'version': mod_version},
        'active': True,
        'ts': 1.0,
        'self': {'teamId': 0, 'identityCandidates': self_candidates},
        'ships': [],
        'torpedoes': torpedoes,
    }


def _candidate(namespace, status, raw=None):
    return {
        'source': 'test', 'namespace': namespace,
        'semantics': 'unverified', 'attributeScope': 'test',
        'status': status, 'rawType': type(raw).__name__ if raw is not None else None,
        'raw': raw, 'usedForIsOwn': False, 'isOwnOverride': False,
    }


def _torpedo(owner_id, is_own=None):
    return {
        'uiId': 1, 'ownerId': owner_id, 'ownerTeamId': 0,
        'ownerType': 'Ship', 'shotId': 1, 'type': 'normal',
        'position': [0.0, 0.0, 0.0], 'isOwn': is_own,
    }


def _write(tmp_path, *lines):
    path = tmp_path / 'self_id.jsonl'
    with path.open('w', encoding='utf-8') as f:
        for obj in lines:
            f.write(json.dumps(obj) + '\n')
    return str(path)


def test_match_and_mismatch_are_aggregated(tmp_path):
    path = _write(
        tmp_path,
        _state(
            self_candidates=[
                _candidate('shipId', 'available', 200),
                _candidate('uiId', 'available', 300),
            ],
            torpedoes=[_torpedo(200, is_own=None)]),
        _state(
            self_candidates=[_candidate('shipId', 'available', 200)],
            torpedoes=[_torpedo(999, is_own=False)]),
    )
    result = analyze(path)
    assert result['validStates'] == 2
    assert result['candidates']['shipId']['match'] == 1
    assert result['candidates']['shipId']['mismatch'] == 1
    assert result['candidates']['shipId']['matchConsistency'] == 'mixed'
    assert result['candidates']['uiId']['match'] == 0
    assert result['candidates']['uiId']['mismatch'] == 1
    assert result['candidates']['uiId']['matchConsistency'] == 'consistentMismatch'


def test_cli_omits_private_battle_and_path(tmp_path, capsys):
    from analyze_self_id_candidates import main
    path = _write(tmp_path, _state(battle_id='private-battle-token'))
    main([path])
    text = capsys.readouterr().out
    assert 'private-battle-token' not in text
    assert str(tmp_path) not in text
    assert 'battleId' not in json.loads(text)


def test_no_torpedoes_and_unavailable_candidates_are_counted(tmp_path):
    path = _write(
        tmp_path,
        _state(self_candidates=[_candidate('shipId', 'available', 200)],
               torpedoes=[]),
        _state(self_candidates=[_candidate('shipId', 'missing')],
               torpedoes=[_torpedo(200)]),
    )
    result = analyze(path)
    assert result['candidates']['shipId']['noTorpedoes'] == 1
    assert result['candidates']['shipId']['candidateUnavailable'] == 1
    assert result['candidates']['shipId']['matchConsistency'] == 'insufficient'


def test_session_and_version_mismatches_are_reported(tmp_path):
    path = _write(
        tmp_path,
        _state(battle_id='b1', mod_version='0.3.43-self-id-observation'),
        _state(battle_id='b2', mod_version='0.3.43-self-id-observation'),
        _state(battle_id='b2', mod_version='0.3.42'),
    )
    result = analyze(path)
    assert result['sessionMismatches'] == 2
    assert result['battleId'] == 'b1'
    assert result['modVersion'] == '0.3.43-self-id-observation'


def test_type_mismatch_and_invalid_lines_are_skipped(tmp_path):
    path = _write(
        tmp_path,
        {'kind': 'meta', 'data': {}},
        _state(),
        'not-json',
    )
    result = analyze(path)
    assert result['typeMismatches'] == 1
    assert result['validStates'] == 1
    assert result['invalidStates'] == 1


def test_cross_candidate_consistency(tmp_path):
    path = _write(
        tmp_path,
        _state(self_candidates=[
            _candidate('shipId', 'available', 100),
            _candidate('uiId', 'available', 100),
        ]),
        _state(self_candidates=[
            _candidate('shipId', 'available', 100),
            _candidate('uiId', 'available', 200),
        ]),
        _state(self_candidates=[_candidate('shipId', 'available', 100)]),
    )
    result = analyze(path)
    assert result['crossCandidateConsistency'] == {
        'agree': 1, 'disagree': 1, 'insufficient': 1}


def test_is_own_counts_are_aggregated_anonymously(tmp_path):
    path = _write(
        tmp_path,
        _state(
            self_candidates=[_candidate('shipId', 'available', 200)],
            torpedoes=[
                _torpedo(200, is_own=True),
                _torpedo(200, is_own=None),
            ]),
        _state(
            self_candidates=[_candidate('shipId', 'available', 200)],
            torpedoes=[_torpedo(200, is_own=False)]),
    )
    result = analyze(path)
    assert result['candidates']['shipId']['isOwnTrue'] == 1
    assert result['candidates']['shipId']['isOwnFalse'] == 1
    assert result['candidates']['shipId']['isOwnNone'] == 1


def test_raw_values_are_not_echoed_in_summary(tmp_path):
    path = _write(
        tmp_path,
        _state(self_candidates=[_candidate('shipId', 'available', 12345)],
               torpedoes=[_torpedo(12345)]),
    )
    result = analyze(path)
    dumped = json.dumps(result)
    assert '12345' not in dumped
