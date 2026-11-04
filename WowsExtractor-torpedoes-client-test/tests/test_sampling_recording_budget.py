"""Offline recording replay reports anonymous budgets, not FPS estimates."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_sampling_recording as budget


def test_streaming_replay_counts_position_skips_and_keeps_source_unchanged(tmp_path):
    torpedo = {'uiId': 9, 'ownerId': 3, 'shotId': 4, 'ownerTeamId': 0,
               'ownerType': 'Ship', 'type': 'normal', 'position': [0, 0, 2000],
               'owner': {'teamId': 0, 'isAlive': True, 'isBot': True}}
    frames = []
    for ts in (0., 5., 5.2, 5.6):
        state = {'active': True, 'battleId': 'synthetic', 'ts': ts,
                 'self': {'teamId': 0, 'isObserver': False, 'position': [0, 0, 0]},
                 'diag': {'mapCalibration': {'status': 'available', 'coefficients': {
                     'worldX': {'mapAxis': 'nx', 'scale': 3000},
                     'worldZ': {'mapAxis': 'ny', 'scale': -3000}}}},
                 'torpedoes': [dict(torpedo)],
                 'torpedoStatus': {'available': True, 'status': 'available'}}
        frames.append({'kind': 'state', 'data': state})
    recording = tmp_path / 'synthetic.jsonl'
    recording.write_text('\n'.join(json.dumps(frame) for frame in frames) + '\n',
                         encoding='utf-8')
    original = recording.read_bytes()
    result = budget.replay(recording)
    assert result['budgets']['states'] == 4
    assert result['budgets']['originalRows'] == 4
    assert result['budgets']['sampledRows'] == 3
    assert result['budgets']['membershipRows'] == 4
    assert result['apiFieldReadCounts']['field.position'] == 3
    assert result['apiFieldReadCounts']['collection'] == 4
    assert result['budgets']['sampled.high'] == 1
    assert result['budgets']['sampled.low'] == 2
    assert 'FPS' in result['limitations']
    assert recording.read_bytes() == original
    assert 'synthetic' not in json.dumps(result)


def test_slim_recordings_warn_that_distance_classification_cannot_be_reconstructed(tmp_path):
    path = tmp_path / 'slim.jsonl'
    path.write_text(json.dumps({'kind': 'state', 'data': {
        'active': True, 'battleId': 'slim', 'ts': 1., 'torpedoes': []}}) + '\n',
        encoding='utf-8')
    result = budget.replay(path)
    assert result['budgets']['contextMissingStates'] == 1
    assert result['budgets']['contextInputsMissingStates'] == 1
    assert any('torpedoes-only' in text for text in result['warnings'])


def test_already_sampled_recordings_are_not_used_as_complete_position_inputs(tmp_path):
    path = tmp_path / 'sampled.jsonl'
    path.write_text(json.dumps({'kind': 'state', 'data': {
        'active': True, 'battleId': 'sampled', 'ts': 1., 'torpedoes': [],
        'torpedoStatus': {'sampling': {'status': 'available'}}}}) + '\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Already-sampled'):
        budget.replay(path)
