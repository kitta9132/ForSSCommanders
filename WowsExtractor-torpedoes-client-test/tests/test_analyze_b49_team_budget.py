"""Unit tests for tools.analyze_b49_team_budget.

These tests use synthetic records and do not import or modify production code,
the game client, or the private recording.  They verify the anonymised
aggregator behaves correctly for the team-torpedo-budget specific counters and
expected edge cases.
"""
import json
import math
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, 'tools'))

import analyze_b49_team_budget  # noqa: E402
from analyze_b49_team_budget import (  # noqa: E402
    RecordingAnalyzer, Session, _membership_identity, _team_policy_snapshot,
    analyze_recording, distance_band, finite_number, horizon_distance, l3_band,
    perf_window_key, phase_mean, quantile, times_equal, weighted_phase_mean)


def state(ts, active=True, membership=None, torpedoes=None, sampling=None,
          performance=None, diag=None, battle_id=None,
          self_position=(0.0, 0.0, 0.0)):
    data = {'ts': ts, 'active': active}
    if self_position is not None:
        data['self'] = {'position': list(self_position)}
    if membership is not None:
        data['torpedoStatus'] = {
            'membership': membership,
            'membershipComplete': True,
            'status': 'available',
            'source': 'battle.getAllTorpedoes',
            'sampling': sampling or {},
        }
    if torpedoes is not None:
        data['torpedoes'] = torpedoes
    if performance is not None:
        data['performance'] = performance
    if diag is not None:
        data['diag'] = diag
    if battle_id is not None:
        data['battleId'] = battle_id
    return {'kind': 'state', 'data': data}


def meta(battle_id='b1', ts=0.0, version='0.3.42-launch-restricted-builtins',
         roster=None, self_player_id=None, map_name='MAP_OCEAN'):
    return {'kind': 'meta', 'data': {
        'battleId': battle_id,
        'ts': ts,
        'mod': {'name': 'WowsExtractor', 'version': version},
        'roster': roster or [],
        'selfPlayerId': self_player_id,
        'map': {'mapName': map_name},
        'apiVersion': '1.0',
        'schema': 1,
        'gameMode': 'TrainingBattle',
        'battleType': 'TrainingBattle',
    }}


def torpedo(ui_id=1, owner_id=1, shot_id=1, group='high',
            position=(0.0, 0.0, 0.0), is_own=None, motion_available=True):
    return {
        'uiId': ui_id,
        'ownerId': owner_id,
        'shotId': shot_id,
        'sampling': {'group': group, 'sampleTs': 0.0},
        'position': list(position),
        'isOwn': is_own,
        'motion': {'available': motion_available,
                   'horizontalSpeed': 10.0 if motion_available else None},
        'mapPositionStatus': 'available',
    }


def classification(radius=100.0, ts=None):
    return {
        'classification': {
            'status': 'available',
            'mapSource': 'calibratedMapExtents',
            'mapInferred': True,
            'radiusWorld': radius,
            'ts': ts,
            'intervalSeconds': 5.0,
        },
    }


def team_policy(**overrides):
    defaults = {
        'policy': '0.3.41-team-torpedo-budget',
        'radiusDivisor': 5.0,
        'enemyHighLimit': 20,
        'ownHigh': 0,
        'allyLow': 0,
        'enemyHigh': 0,
        'enemyLow': 0,
        'safetyHigh': 0,
        'unknownTeamHigh': 0,
        'unknownDistanceHigh': 0,
    }
    defaults.update(overrides)
    return {'teamPolicy': defaults}


class TestDistanceHelpers:
    def test_distance_band_boundaries(self):
        assert distance_band(50.0, 100.0) == 'near'
        assert distance_band(100.0, 100.0) == 'near'
        assert distance_band(100.0001, 100.0) == 'mid'
        assert distance_band(300.0, 100.0) == 'mid'
        assert distance_band(300.0001, 100.0) == 'far'

    def test_distance_band_invalid_is_unknown(self):
        assert distance_band(None, 100.0) == 'unknown'
        assert distance_band(50.0, 0) == 'unknown'
        assert distance_band(float('nan'), 100.0) == 'unknown'

    def test_l3_band(self):
        assert l3_band(300.0, 100.0) == 'near'
        assert l3_band(300.0001, 100.0) == 'far'
        assert l3_band(None, 100.0) == 'unknown'

    def test_horizon_distance(self):
        assert horizon_distance((0.0, 0.0, 0.0), (3.0, 0.0, 4.0)) == 5.0
        assert horizon_distance(None, (0.0, 0.0, 0.0)) is None
        assert horizon_distance((0.0, 0.0, 0.0), (0.0, float('nan'), 0.0)) is None


class TestQuantileAndMeans:
    def test_quantile_empty(self):
        assert quantile([], 0.5) is None

    def test_quantile_matches_nearest_rank(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert quantile(values, 0.95) == 10
        assert quantile(values, 0.1) == 1
        assert quantile(values, 0.5) == 5

    def test_phase_mean_rejects_nonfinite(self):
        assert phase_mean({'total': 10.0, 'count': 2}) == 5.0
        assert phase_mean({'total': float('nan'), 'count': 2}) is None
        assert phase_mean({'total': 10.0, 'count': 0}) is None
        assert phase_mean({'total': 10.0}) is None

    def test_weighted_phase_mean_ignores_missing_phases(self):
        windows = [
            {'phases': {'a': {'total': 10.0, 'count': 2}}},
            {'phases': {'a': {'total': 30.0, 'count': 3},
                        'b': {'total': 1.0, 'count': 0}}},
            {'phases': {'c': {'total': 9.0, 'count': 1}}},
        ]
        assert weighted_phase_mean(windows, 'a') == 40.0 / 5.0
        assert weighted_phase_mean(windows, 'b') is None
        assert weighted_phase_mean(windows, 'missing') is None


class TestTeamPolicySnapshot:
    def test_snapshot_keeps_safe_values_only(self):
        raw = {
            'policy': '0.3.41-team-torpedo-budget',
            'radiusDivisor': 5.0,
            'enemyHighLimit': 20,
            'ownHigh': 0,
            'allyLow': 0,
            'enemyHigh': 10,
            'enemyLow': 5,
            'safetyHigh': 0,
            'unknownTeamHigh': 0,
            'unknownDistanceHigh': 0,
            'privateField': 'secret',
        }
        snap = _team_policy_snapshot(raw)
        assert snap['policy'] == '0.3.41-team-torpedo-budget'
        assert snap['enemyHigh'] == 10
        assert 'privateField' not in snap

    def test_snapshot_rejects_non_numeric_counts(self):
        raw = {'enemyHigh': 'lots', 'enemyHighLimit': 20}
        snap = _team_policy_snapshot(raw)
        assert snap.get('enemyHigh') is None
        assert snap.get('enemyHighLimit') == 20


class TestPerformanceDedup:
    def test_perf_window_key(self):
        assert perf_window_key({'sampleStartSeconds': 1.0,
                                'sampleEndSeconds': 2.0}) == (1.0, 2.0)
        assert perf_window_key({'sampleStartSeconds': 1.0}) is None

    def test_dedupes_duplicate_performance_windows(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        base_perf = {
            'status': 'available',
            'sampleStartSeconds': 0.0,
            'sampleEndSeconds': 5.0,
            'writerMode': 'syncEncodeWrite',
            'timebase': {'source': 'time.clock', 'basis': 'assumed'},
            'durationUnit': 'ms',
            'clockStatus': 'available',
            'phases': {
                'state_cycle_total': {'total': 100.0, 'count': 10, 'max': 15.0},
            },
        }
        analyzer.feed(state(0.0, performance=base_perf))
        dup = dict(base_perf)
        dup['phases'] = {
            'state_cycle_total': {'total': 120.0, 'count': 10, 'max': 18.0},
        }
        analyzer.feed(state(0.2, performance=dup))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['performance']['uniqueWindows'] == 1
        assert s['performance']['carrierRows'] == 2
        assert s['performance']['duplicateCarrierRows'] == 1
        # First window kept.
        assert s['performance']['phaseStats']['state_cycle_total']['weightedMean'] == 10.0

    def test_missing_performance_does_not_crash(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        analyzer.feed(state(0.0, performance={'status': 'notSampled'}))
        analyzer.feed(state(0.2))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['performance']['uniqueWindows'] == 0
        assert s['performance']['notSampledStates'] == 1


class TestSessions:
    def test_session_reset_on_new_meta_and_stale_exclusion(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta('old-battle', ts=0.0))
        analyzer.feed(state(0.0, active=False))
        analyzer.feed(meta('new-battle', ts=10.0))
        analyzer.feed(state(10.0, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=10.0),
                                     **team_policy()}))
        analyzer.feed(state(10.2, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=10.2),
                                     **team_policy()}))
        result = analyzer.finish()
        assert result['battleIdCount'] == 2
        assert result['sessionCount'] == 2
        assert result['includedSessionCount'] == 1
        s1 = result['sessions'][0]
        s2 = result['sessions'][1]
        assert s1['exclusionReason'] == 'stale/inactive meta session: no active states'
        assert s2['included'] is True
        assert s2['activeStates'] == 2
        assert s2['uniqueIdentities'] == 1
        assert s2['teamPolicy']['present'] is True

    def test_battle_mismatch_is_excluded_from_session(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta('main', ts=0.0))
        analyzer.feed(state(0.0, battle_id='main', membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=0.0),
                                     **team_policy()}))
        analyzer.feed(state(0.2, battle_id='other', membership=[(2, 2, 2)],
                           torpedoes=[torpedo(ui_id=2, owner_id=2)],
                           sampling={**classification(100.0, ts=0.2),
                                     **team_policy()}))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['activeStates'] == 1
        assert s['battleMismatchStates'] == 1
        assert s['uniqueIdentities'] == 1


class TestTeamPolicyAccounting:
    def test_enemy_high_over_limit_is_counted(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        analyzer.feed(state(0.0, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=0.0),
                                     **team_policy(enemyHigh=21)}))
        analyzer.feed(state(0.2, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=0.2),
                                     **team_policy(enemyHigh=20)}))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['teamPolicy']['enemyHighOverLimitStates'] == 1
        assert s['teamPolicy']['enemyHighPositiveStates'] == 2
        assert s['teamPolicy']['enemyHighAtLimitStates'] == 1

    def test_safety_high_can_exceed_budget_without_enemy_over_limit(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        analyzer.feed(state(0.0, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=0.0),
                                     **team_policy(unknownTeamHigh=25)}))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['teamPolicy']['enemyHighOverLimitStates'] == 0
        assert s['teamPolicy']['totalHighOverBudgetStates'] == 1

    def test_first_enemy_high_positive_timestamp_is_recorded(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        analyzer.feed(state(1.0, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=1.0),
                                     **team_policy()}))
        analyzer.feed(state(2.0, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling={**classification(100.0, ts=2.0),
                                     **team_policy(enemyHigh=5)}))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['teamPolicy']['firstEnemyHighPositiveTs'] == 2.0

    def test_team_policy_absence_reported(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        analyzer.feed(state(0.0, membership=[(1, 1, 1)],
                           torpedoes=[torpedo()],
                           sampling=classification(100.0, ts=0.0)))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['teamPolicy']['present'] is False


class TestGeometryAndSampling:
    def test_classification_tick_geometry_matches_groups(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        rows = [
            torpedo(1, 1, 1, 'high', (50.0, 0.0, 0.0)),   # near
            torpedo(2, 1, 2, 'low', (200.0, 0.0, 0.0)),    # mid
            torpedo(3, 1, 3, 'low', (400.0, 0.0, 0.0)),    # far
        ]
        analyzer.feed(state(0.0, membership=[(1, 1, 1), (2, 1, 2), (3, 1, 3)],
                           torpedoes=rows,
                           sampling={'high': {'memberCount': 1, 'sampledCount': 1},
                                     'low': {'memberCount': 2, 'sampledCount': 2},
                                     **classification(100.0, ts=0.0),
                                     **team_policy()}))
        result = analyzer.finish()
        s = result['sessions'][0]
        cl = s['classificationTicks']
        assert cl['usable'] == 1
        assert cl['rows'] == 3
        assert cl['l5']['counts'] == {'near': 1, 'mid': 1, 'far': 1}
        assert cl['l3']['counts'] == {'near': 2, 'far': 1}
        assert cl['groupGeometry'] == {
            "('high', 'near')": 1,
            "('low', 'mid')": 1,
            "('low', 'far')": 1,
        }

    def test_non_classification_samples_still_classified(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        rows = [torpedo(1, 1, 1, 'high', (200.0, 0.0, 0.0))]
        analyzer.feed(state(0.0, membership=[(1, 1, 1)],
                           torpedoes=rows,
                           sampling={'high': {'memberCount': 1, 'sampledCount': 1},
                                     'low': {'memberCount': 0, 'sampledCount': 0},
                                     **classification(100.0, ts=0.0),
                                     **team_policy()}))
        rows2 = [torpedo(1, 1, 1, 'high', (200.0, 0.0, 0.0))]
        analyzer.feed(state(0.2, membership=[(1, 1, 1)],
                           torpedoes=rows2,
                           sampling={'high': {'memberCount': 1, 'sampledCount': 1},
                                     'low': {'memberCount': 0, 'sampledCount': 0},
                                     **classification(100.0, ts=0.0),
                                     **team_policy()}))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['classificationTicks']['usable'] == 1
        # Both sampled rows are high+mid (non-near due to lag, not own/new).
        assert s['allSampleGroupGeometry']["('high', 'mid')"] == 2


class TestIntervalsAndContinuity:
    def test_interval_gaps_and_continuity_reset(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        rows = [torpedo(1, 1, 1, 'high', (0.0, 0.0, 0.0))]
        analyzer.feed(state(0.0, membership=[(1, 1, 1)], torpedoes=rows,
                           sampling={'high': {'memberCount': 1, 'sampledCount': 1},
                                     'low': {'memberCount': 0, 'sampledCount': 0},
                                     **classification(100.0, ts=0.0),
                                     **team_policy()}))
        analyzer.feed(state(0.2, membership=[(1, 1, 1)], torpedoes=rows,
                           sampling={'high': {'memberCount': 1, 'sampledCount': 1},
                                     'low': {'memberCount': 0, 'sampledCount': 0},
                                     **classification(100.0, ts=0.2),
                                     **team_policy()}))
        # Disappearance resets continuity.
        analyzer.feed(state(1.0, membership=[], torpedoes=[],
                           sampling={'high': {'memberCount': 0, 'sampledCount': 0},
                                     'low': {'memberCount': 0, 'sampledCount': 0},
                                     **classification(100.0, ts=1.0),
                                     **team_policy()}))
        analyzer.feed(state(1.2, membership=[(1, 1, 1)], torpedoes=rows,
                           sampling={'high': {'memberCount': 1, 'sampledCount': 1},
                                     'low': {'memberCount': 0, 'sampledCount': 0},
                                     **classification(100.0, ts=1.2),
                                     **team_policy()}))
        result = analyzer.finish()
        s = result['sessions'][0]
        assert s['intervals']['high']['count'] == 2
        assert pytest.approx(s['intervals']['high']['min'], 0.001) == 0.2
        assert s['intervals']['droppedLong'] == 0


class TestIdentityHelpers:
    def test_membership_identity(self):
        assert _membership_identity([1, 2, 3]) == (1, 2, 3)
        assert _membership_identity({'uiId': 1, 'ownerId': 2, 'shotId': 3}) == (1, 2, 3)
        assert _membership_identity('bad') is None


class TestMiscellaneous:
    def test_finite_number_rejects_bool_and_nan(self):
        assert finite_number(1.0) is True
        assert finite_number(1) is True
        assert finite_number(True) is False
        assert finite_number(float('nan')) is False
        assert finite_number(None) is False

    def test_times_equal_tolerance(self):
        assert times_equal(1.0, 1.0 + 1e-12) is True
        assert times_equal(1.0, 1.1) is False

    def test_terminal_frame_tracked(self):
        analyzer = RecordingAnalyzer()
        analyzer.feed(meta())
        analyzer.feed(state(0.0, active=False))
        result = analyzer.finish()
        assert result['terminalFrameValid'] is True
        assert result['terminalFrameKind'] == 'state'
        assert result['terminalFrameActive'] is False


def test_main_module_runs_without_error_on_private_record(tmp_path):
    """The tool must not crash on the actual private recording."""
    recording = os.path.join(_ROOT, 'recordings', 'without-atm-b49.jsonl')
    if not os.path.exists(recording):
        pytest.skip('private recording not present')
    out = tmp_path / 'out.json'
    result = analyze_b49_team_budget.main([
        '--recording', recording,
        '--json-output', str(out),
    ])
    assert result == 0
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['recordingBytes'] > 0
    assert data['stateCount'] > 0
    assert data['totalRecords'] == data['metaCount'] + data['stateCount']
    assert data['badJsonLines'] == 0
    assert data['terminalFrameValid'] is True
    assert data['terminalFrameActive'] is False
    # Anonymity: raw battle/player IDs must not leak to the JSON output.
    text = out.read_text(encoding='utf-8')
    assert '"selfPlayerId"' not in text
    assert '"playerId"' not in text
    assert '"battleId":' not in text
    # B49 is a single included session.
    assert data['includedSessionCount'] == 1
    # Team policy is present for the team-budget build.
    s = data['sessions'][0]
    assert s['teamPolicy']['present'] is True
    assert '0.3.41-team-torpedo-budget' in s['teamPolicy']['policies']
