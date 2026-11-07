"""Offline unit tests for tools/research_b49_classification_gaps.py.

These tests use synthetic fixtures and never touch the game, recorder, or
private recordings.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, 'tools'))

import research_b49_classification_gaps  # noqa: E402
from research_b49_classification_gaps import investigate  # noqa: E402


@pytest.fixture
def synthetic_recording():
    """A tiny JSONL with two states: one normal, one self.position missing."""
    lines = [
        json.dumps({'kind': 'meta'}),
        json.dumps({
            'kind': 'state',
            'data': {
                'ts': 10.0,
                'active': True,
                'self': {
                    'playerId': 100,
                    'teamId': 0,
                    'position': [1.0, 2.0, 3.0],
                    'health': 1000.0,
                    'maxHealth': 1000.0,
                    'isObserver': False,
                },
                'diag': {'mapCalibration': {'status': 'available'}},
                'torpedoStatus': {
                    'membership': [],
                    'sampling': {
                        'classification': {
                            'due': True,
                            'ts': 10.0,
                            'reason': None,
                        }
                    }
                },
                'torpedoes': [
                    {
                        'uiId': 1,
                        'ownerId': 200,
                        'ownerTeamId': 1,
                        'shotId': 10,
                        'position': [100.0, 0.0, 100.0],
                        'owner': {
                            'teamId': 1,
                            'isObserver': False,
                            'isAlive': True,
                            'isBot': False,
                            'isPlayer': None,
                            'subtype': None,
                        }
                    }
                ],
                'ships': []
            }
        }),
        json.dumps({
            'kind': 'state',
            'data': {
                'ts': 15.0,
                'active': True,
                'self': {
                    'playerId': 100,
                    'teamId': 0,
                    # position intentionally missing
                    'isObserver': False,
                },
                'diag': {'mapCalibration': {'status': 'available'}},
                'torpedoStatus': {
                    'membership': [],
                    'sampling': {
                        'classification': {
                            'due': True,
                            'ts': 15.0,
                            'reason': 'contextMissing',
                        }
                    }
                },
                'torpedoes': [
                    {
                        'uiId': 2,
                        'ownerId': 200,
                        'ownerTeamId': 1,
                        'shotId': 20,
                        'position': [110.0, 0.0, 110.0],
                        'owner': None,
                    }
                ],
                'ships': []
            }
        }),
    ]
    with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', suffix='.jsonl', delete=False) as fh:
        fh.write('\n'.join(lines))
        path = fh.name
    yield path
    os.unlink(path)


def test_anonymised_summary(synthetic_recording):
    result = investigate(synthetic_recording)
    assert result['totalStates'] == 2
    assert result['activeStates'] == 2
    assert result['classificationTicks'] == 2
    assert result['classificationTicksMissingContext'] == 1
    assert result['selfPositionPresent'] == {True: 1, False: 1}


def test_owner_field_stats(synthetic_recording):
    result = investigate(synthetic_recording)
    stats = result['ownerFieldStats']
    assert stats['rowCount'] == 2
    assert stats['ownerPresent'] == 1
    assert stats['isPlayerValues'] == {'None': 1}
    assert stats['nonNullFields'].get('teamId') == 1
    # Strict ownerTeamId/self.teamId classification (self=0, owner=1).
    assert stats['teamClass'] == {'enemyTeam': 2}
    # No private IDs are emitted in the summary.
    assert 'ownerIds' not in result


def test_team_class_unknown_when_self_team_missing():
    assert research_b49_classification_gaps._team_class(1, None) == 'unknownTeam'
    assert research_b49_classification_gaps._team_class(None, 1) == 'unknownTeam'
    assert research_b49_classification_gaps._team_class(1, 1) == 'sameTeam'
    assert research_b49_classification_gaps._team_class(1, 2) == 'enemyTeam'
