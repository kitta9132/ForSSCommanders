"""Strict self ship ID ownership for torpedo rows (0.3.44)."""
import os
import sys
from types import SimpleNamespace as Obj

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))
from torpedo_telemetry import (
    TorpedoSamplingGroups, TorpedoTelemetry, _self_id_own)


class Torpedo(object):
    def __init__(self, uiId, ownerId, ownerTeamId=1,
                 position=(0.0, 0.0, 2000.0)):
        self.uiId = uiId
        self.ownerId = ownerId
        self.ownerTeamId = ownerTeamId
        self.ownerType = 'Ship'
        self.shotId = 1
        self.type = 'normal'
        self.position = position


class Owner(object):
    def __init__(self, isPlayer):
        self.teamId = 0
        self.isAlive = True
        self.isPlayer = isPlayer
        self.isBot = not isPlayer


class Battle(object):
    def __init__(self, rows, owners=None):
        self.rows = rows
        self.owners = dict(owners or {})

    def getAllTorpedoes(self):
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        return self.owners.get(owner_id)


def context():
    return {'selfPosition': [0.0, 0.0, 0.0], 'mapWidth': 3000,
            'mapHeight': 3000, 'source': 'calibratedMapExtents',
            'inferred': True}


def test_exact_int_match_is_own():
    result = _self_id_own(123, 123)
    assert result['isOwn'] is True
    assert result['reason'] == 'exactSelfShipIdMatch'


def test_different_int_is_not_own():
    result = _self_id_own(123, 456)
    assert result['isOwn'] is False
    assert result['reason'] == 'selfShipIdDiffers'


def test_string_match_is_own():
    result = _self_id_own('abc', 'abc')
    assert result['isOwn'] is True


def test_type_mismatch_is_unknown():
    result = _self_id_own(123, '123')
    assert result['isOwn'] is None
    assert result['reason'] == 'typeMismatch'


def test_unavailable_self_ship_id_is_unknown():
    result = _self_id_own(123, None)
    assert result['isOwn'] is None
    assert result['reason'] == 'selfShipIdUnavailable'


def test_none_owner_id_is_unknown():
    result = _self_id_own(None, 123)
    assert result['isOwn'] is None
    assert result['isOwn'] is not False
    assert result['reason'] == 'noneValue'


def test_bool_owner_id_is_rejected():
    result = _self_id_own(True, 123)
    assert result['isOwn'] is None
    assert result['reason'] == 'strictTypeRejected'


def test_nonfinite_owner_id_is_unknown():
    result = _self_id_own(float('nan'), 123)
    assert result['isOwn'] is None
    assert result['reason'] == 'nonFinite'


def test_empty_string_owner_id_is_unknown():
    result = _self_id_own('', 'self')
    assert result['isOwn'] is None
    assert result['reason'] == 'invalidId'


def test_torpedoes_publishes_is_own_source_and_reason():
    own = Torpedo(1, 900)
    telemetry = TorpedoTelemetry(Battle([own], {900: Owner(True)}), Obj())
    rows, _ = telemetry.torpedoes(
        0, TorpedoSamplingGroups(), 0.0, context(),
        self_ship_id=900)
    assert len(rows) == 1
    row = rows[0]
    assert row['isOwn'] is True
    assert 'battle.getSelfPlayerInfo().shipId' in row['isOwnSource']
    assert row['isOwnReason'] == 'exactSelfShipIdMatch'
    # owner.isPlayer is still preserved as a raw observation, not used for
    # the ownership decision.
    assert row['owner']['isPlayer'] is True


def test_torpedoes_non_own_publishes_false_and_differs_reason():
    row = Torpedo(1, 901)
    telemetry = TorpedoTelemetry(Battle([row], {901: Owner(False)}), Obj())
    rows, _ = telemetry.torpedoes(
        0, TorpedoSamplingGroups(), 0.0, context(),
        self_ship_id=900)
    assert rows[0]['isOwn'] is False
    assert rows[0]['isOwnReason'] == 'selfShipIdDiffers'


def test_torpedoes_without_self_ship_id_and_same_team_is_safety_high():
    # Same-team relation with unknown ownership cannot be told apart from the
    # self ship, so it stays on the safety side as high.
    row = Torpedo(1, 902, ownerTeamId=0)
    telemetry = TorpedoTelemetry(Battle([row], {902: Owner(False)}), Obj())
    rows, status = telemetry.torpedoes(
        0, TorpedoSamplingGroups(), 0.0, context())
    assert rows[0]['isOwn'] is None
    assert rows[0]['isOwnReason'] == 'selfShipIdUnavailable'
    assert rows[0]['sampling']['group'] == 'high'
    assert status['sampling']['teamPolicy']['safetyHigh'] == 1
