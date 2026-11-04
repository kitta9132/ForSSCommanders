"""Offline identity-namespace candidates; no game engine or new API calls."""
import copy
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))
from torpedo_telemetry import identity_candidates, safe_identity_candidates
from submarine_telemetry import wave_hit_probe


MISSING = object()
ROOT = Path(__file__).resolve().parents[1]


def _ship(vehicle_id=MISSING, player_id=MISSING, team_id=1):
    row = {'teamId': team_id, 'relation': 1}
    if vehicle_id is not MISSING:
        row['vehicleId'] = vehicle_id
    if player_id is not MISSING:
        row['playerId'] = player_id
    return row


def _torpedo(owner_id=MISSING, is_own=None, owner=None):
    row = {'uiId': 1, 'shotId': 2, 'isOwn': is_own,
           'owner': {'isPlayer': is_own} if owner is None else owner}
    if owner_id is not MISSING:
        row['ownerId'] = owner_id
    return row


def _wave_row(target_id=MISSING, field_status=None):
    status = 'available' if target_id is not MISSING else 'unknown'
    statuses = {name: 'unknown' for name in
                ('targetID', 'lifeTime', 'maxLifeTime', 'alertTime',
                 'hitCount', 'isActive', 'weaponType')}
    statuses['targetID'] = field_status or status
    fields = {name: None for name in statuses}
    if target_id is not MISSING:
        fields['targetID'] = target_id
    return {'entityIdCandidate': 1, 'componentStatus': 'available',
            'fields': fields, 'fieldStatus': statuses,
            'fieldReason': {name: None for name in statuses},
            'fieldType': {name: type(fields[name]).__name__
                          for name in statuses}}


def _wave_probe(rows=None, complete=True, truncated=False, partial=False,
                status='available'):
    rows = [] if rows is None else rows
    return {'source': 'dataHub.waveHit', 'status': status,
            'semantics': 'unverified', 'sampleTs': 100.,
            'collection': {'source': "dataHub.getEntityCollections('waveHit')",
                           'status': status, 'complete': complete,
                           'count': len(rows), 'truncated': truncated,
                           'reason': None},
            'componentKeyStatus': 'available', 'rows': rows,
            'truncated': truncated, 'partial': partial}


def _find(out, key):
    for entry in out['identityCandidates']:
        if key in entry:
            return entry[key]
    return None


def _json_scalars(value):
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(_json_scalars(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_json_scalars(item))
        return result
    return [value]


def test_owner_self_only_unique_exact_preserves_legacy_is_own():
    torpedoes = [_torpedo(10, is_own=None)]
    ships = [_ship(10, 77)]
    out = identity_candidates(ships, {'playerId': 77}, torpedoes,
                              _wave_probe())
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == 'uniqueExact'
    assert candidate['completeness'] == 'unknown'
    assert candidate['resolution'] == 'candidate'
    assert candidate['inferred']['status'] == 'candidate'
    assert candidate['inferred']['isOwnOverride'] is False
    assert candidate['matchCount'] == 1
    assert len(candidate['candidateMatches']) == 1
    assert candidate['candidateMatches'][0]['rowRef'] == 'ships[0]'
    assert candidate['selfMatchCandidate']['status'] == 'exactCandidate'
    assert candidate['selfMatchCandidate']['isOwnOverride'] is False
    assert candidate['selfMatchCandidate']['usedForIsOwn'] is False
    assert candidate['validationScope']['records'] == ['B10', 'B12', 'B14']
    assert candidate['validationScope']['conditions'] == [
        'activeOnly', 'selfOnly', 'singleShipSnapshot']
    # Raw legacy fields are read only. No raw ID is copied into a candidate.
    assert torpedoes[0]['isOwn'] is None
    assert torpedoes[0]['owner'] == {'isPlayer': None}
    assert 'ownerId' not in candidate and 'vehicleId' not in candidate
    assert 'playerId' not in candidate and 'targetShipId' not in candidate
    encoded = _json_scalars(candidate)
    assert 77 not in encoded and 10 not in encoded


def test_wave_hit_enemy_target_is_candidate_only_without_target_ship_field():
    ships = [_ship(10, 77, 1), _ship(20, 88, 2)]
    out = identity_candidates(ships, {'playerId': 77},
                              [_torpedo(MISSING)], _wave_probe(
                                  [_wave_row(20)]))
    candidate = _find(out, 'targetIdNamespaceCandidate')
    assert candidate['matchStatus'] == 'uniqueExact'
    assert candidate['completeness'] == 'unknown'
    assert candidate['resolution'] == 'candidate'
    assert candidate['matchCount'] == 1
    assert candidate['candidateMatches'] == [{
        'collection': 'ships', 'field': 'vehicleId', 'match': 'exact',
        'rowRef': 'ships[1]'}]
    assert candidate['validationScope']['records'] == ['B27']
    assert 'targetShipId' not in candidate
    assert 'targetShipId' not in out
    assert 'selfMatchCandidate' not in candidate


def test_duplicate_vehicle_ids_are_ambiguous_and_candidate_matches_are_bounded():
    ships = [_ship(10, 77) for _ in range(10)]
    out = identity_candidates(ships, {'playerId': 77}, [_torpedo(10)],
                              _wave_probe())
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == 'ambiguousMultiple'
    assert candidate['resolution'] == 'ambiguous'
    assert candidate['matchCount'] == 10
    assert candidate['matchesTruncated'] is True
    assert len(candidate['candidateMatches']) == 8
    assert candidate['selfMatchCandidate']['status'] == 'unknown'
    # No first-row selection: all bounded candidate rows stay references.
    assert [item['rowRef'] for item in candidate['candidateMatches']] == [
        'ships[%d]' % index for index in range(8)]


def test_missing_player_or_vehicle_is_never_nonself_false():
    # Missing matched-ship playerId: value match is still exact, self link unknown.
    out = identity_candidates([_ship(10)], {'playerId': 77}, [_torpedo(10)],
                              _wave_probe())
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == 'uniqueExact'
    assert candidate['selfMatchCandidate']['status'] == 'unknown'
    assert candidate['selfMatchCandidate']['reason'] == \
        'matchedShipPlayerIdUnavailable'

    # Missing vehicleId makes the observed index incomplete, so no uniqueExact.
    out = identity_candidates([_ship(MISSING, 77), _ship(10, 78)],
                              {'playerId': 77}, [_torpedo(10)], _wave_probe())
    assert out['shipsCollection']['indexStatus'] == 'incomplete'
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == 'unknown'
    assert candidate['resolution'] == 'indeterminate'
    assert candidate['unknownReason'] == 'shipsVehicleIdIndexIncomplete'
    assert candidate['selfMatchCandidate']['status'] == 'unknown'
    assert 'nonself' not in json.dumps(candidate).lower()
    assert '"isOwn": false' not in json.dumps(candidate)

    # Missing vehicleId with no match remains indeterminate, not false.
    out = identity_candidates([_ship(MISSING, 77)], {'playerId': 77},
                              [_torpedo(10)], _wave_probe())
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == 'noExactMatch'
    assert candidate['resolution'] == 'indeterminate'
    assert candidate['selfMatchCandidate']['status'] == 'unknown'


def test_zero_matches_are_indeterminate_not_nonself_or_false():
    out = identity_candidates([_ship(10, 77)], {'playerId': 77},
                              [_torpedo(99)], _wave_probe())
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == 'noExactMatch'
    assert candidate['resolution'] == 'indeterminate'
    assert candidate['matchCount'] == 0
    assert candidate['candidateMatches'] == []
    assert candidate['selfMatchCandidate']['status'] == 'unknown'
    assert 'nonself' not in json.dumps(candidate).lower()
    assert '"isOwn": false' not in json.dumps(candidate)


@pytest.mark.parametrize('ship_id,owner_id,status,match_status', [
    (1, True, 'strictTypeRejected', 'notEvaluated'),
    (0, False, 'strictTypeRejected', 'notEvaluated'),
    (1, 1.0, None, 'noExactMatch'),
    (1, '1', None, 'noExactMatch'),
    (1, float('nan'), 'nonFinite', 'notEvaluated'),
    (1, float('inf'), 'nonFinite', 'notEvaluated'),
    (0, 0, None, 'uniqueExact'),
    ('abc', 'abc', None, 'uniqueExact'),
    ('x' * 128, 'x' * 128, 'possiblyTruncatedId', 'notEvaluated'),
])
def test_strict_scalar_types_are_finite_bool_excluded_and_never_coerced(
        ship_id, owner_id, status, match_status):
    out = identity_candidates([_ship(ship_id, 77)], {'playerId': 77},
                              [_torpedo(owner_id)], _wave_probe())
    candidate = _find(out, 'ownerNamespaceCandidate')
    assert candidate['matchStatus'] == match_status
    if status is not None:
        assert candidate['unknownReason'] == status


@pytest.mark.parametrize('kwargs,reason', [
    ({'complete': False}, 'waveHitCollectionCompletenessUnknown'),
    ({'truncated': True}, 'waveHitCollectionPartialOrTruncated'),
    ({'partial': True}, 'waveHitCollectionPartialOrTruncated'),
    ({'status': 'unknown'}, 'waveHitCollectionStatusNotAvailable'),
])
def test_incomplete_partial_or_truncated_wave_rows_are_not_used(kwargs, reason):
    out = identity_candidates([_ship(20, 88)], {'playerId': 77}, [],
                              _wave_probe([_wave_row(20)], **kwargs))
    assert out['waveHitUsage']['status'] == 'skipped'
    assert out['waveHitUsage']['reason'] == reason
    assert _find(out, 'targetIdNamespaceCandidate') is None


def test_no_history_is_reused_between_snapshots():
    ships = [_ship(20, 88)]
    first = identity_candidates(ships, {'playerId': 77}, [],
                                _wave_probe([_wave_row(20)]))
    assert _find(first, 'targetIdNamespaceCandidate')['matchStatus'] == \
        'uniqueExact'

    second = identity_candidates(ships, {'playerId': 77}, [],
                                 _wave_probe([_wave_row(99)]))
    candidate = _find(second, 'targetIdNamespaceCandidate')
    assert candidate['matchStatus'] == 'noExactMatch'
    assert candidate['matchCount'] == 0
    assert candidate['resolution'] == 'indeterminate'
    # Exactly one current-frame entry; no cached first-frame match.
    assert len(second['identityCandidates']) == 1


def test_malformed_helper_inputs_fail_closed_without_raising(monkeypatch):
    out = safe_identity_candidates(object(), object(), object(), object())
    assert out['status'] == 'unknown'
    assert out['identityCandidates'] == []

    import torpedo_telemetry as telemetry

    def fail(*args):
        raise RuntimeError('helper')

    monkeypatch.setattr(telemetry, 'identity_candidates', fail)
    out = telemetry.safe_identity_candidates(None, None, None, None)
    assert out['status'] == 'unknown'
    assert out['identityCandidates'] == []
    assert out['error'] == 'probeFailed'

    out = identity_candidates(None, None, [None, {'ownerId': 10}], None)
    assert out['torpedoRowsStatus'] == 'evaluated'
    assert len(out['identityCandidates']) == 2
    first = out['identityCandidates'][0]['ownerNamespaceCandidate']
    second = out['identityCandidates'][1]['ownerNamespaceCandidate']
    assert first['matchStatus'] == 'notEvaluated'
    assert second['matchStatus'] == 'notEvaluated'
    assert out['waveHitUsage']['status'] == 'skipped'


def test_identity_comparison_does_not_modify_legacy_raw_snapshot():
    ships = [_ship(10, 77), _ship(20, 88, 2)]
    self_state = {'playerId': 77, 'teamId': 1}
    torpedoes = [_torpedo(10, is_own=True, owner={'isPlayer': True}),
                 _torpedo(20, is_own=False, owner={'isPlayer': False})]
    probe = _wave_probe([_wave_row(20)])
    before = copy.deepcopy((ships, self_state, torpedoes, probe))

    identity_candidates(ships, self_state, torpedoes, probe)

    assert (ships, self_state, torpedoes, probe) == before
    assert torpedoes[0]['isOwn'] is True
    assert torpedoes[1]['isOwn'] is False
    assert torpedoes[0]['owner'] == {'isPlayer': True}
    assert probe['rows'][0]['fields']['targetID'] == 20


def test_real_wave_hit_producer_shape_integrates_without_extra_api_calls():
    class Hub(object):
        def __init__(self):
            self.calls = []

        def getEntityCollections(self, name):
            self.calls.append(name)
            assert name == 'waveHit'
            return [{'id': 1, 'wh': {
                'targetID': 20, 'lifeTime': 12.0, 'maxLifeTime': 25.0,
                'alertTime': 0.0, 'hitCount': 1, 'isActive': True,
                'weaponType': 0}}]

    hub = Hub()
    probe = wave_hit_probe(hub, {'waveHit': 'wh'}, 100.)
    assert hub.calls == ['waveHit']
    out = identity_candidates([_ship(10, 77), _ship(20, 88, 2)],
                              {'playerId': 77}, [], probe)
    assert hub.calls == ['waveHit']
    candidate = _find(out, 'targetIdNamespaceCandidate')
    assert candidate['matchStatus'] == 'uniqueExact'
    assert candidate['source']['apiCallAdded'] is False


def test_main_state_assembly_calls_safe_identity_candidates():
    main = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
        encoding='utf-8')
    assert "MOD_VERSION = '0.3.32-remove-ballistics'" in main
    assert 'safe_identity_candidates' in main
    assert 'self_state = self._build_self(ui_hp, self_info, self_ship)' in main
    assert ("safe_identity_candidates(ships, self_state, torpedoes,\n"
            "                    submarine_probes['waveHitProbe'])") in main
    assert "'identityCandidates': identity_candidates_state" in main
    assert "'self': self_state" in main
