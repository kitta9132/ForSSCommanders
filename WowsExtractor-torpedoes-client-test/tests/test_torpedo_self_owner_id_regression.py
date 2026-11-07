"""0.3.44 self-owner-id regression: non-due LOW rows must promote with current
self_ship_id and re-read position through real TorpedoTelemetry."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))
from test_torpedo_sampling_groups import (
    Battle, CountedTorpedo, adapter, context)
from torpedo_telemetry import TorpedoSamplingGroups


def test_low_row_promotes_to_high_when_self_ship_id_becomes_known():
    """A far LOW row sampled at t=0 with unknown ownership must be re-sampled
    with a current world position when the same snapshot learns self_ship_id."""
    far = CountedTorpedo(
        uiId=1, ownerId=12345, ownerTeamId=1, shotId=1,
        position=(0.0, 0.0, 2000.0))
    telemetry, battle = adapter([far])
    sampler = TorpedoSamplingGroups()
    ctx = context()

    # First observation: self_ship_id is unknown, enemy torpedo is far -> LOW.
    out, status = telemetry.torpedoes(
        self_team=0, sampling=sampler, now=0.0, context=ctx,
        self_ship_id=None)
    assert len(out) == 1
    assert out[0]['sampling']['group'] == 'low'
    assert out[0]['isOwn'] is None
    assert out[0]['isOwnReason'] == 'selfShipIdUnavailable'
    assert out[0]['position'] == [0.0, 0.0, 2000.0]
    assert out[0]['sampling']['positionStatus'] == 'available'
    assert far.reads['position'] == 1
    assert battle.owner_calls[12345] == 1

    # Non-due LOW tick with no self ID: no position or owner lookup.
    out, status = telemetry.torpedoes(
        self_team=0, sampling=sampler, now=0.2, context=ctx,
        self_ship_id=None)
    assert not out
    assert status['sampling']['low']['status'] == 'notSampled'
    assert far.reads['position'] == 1
    assert battle.owner_calls[12345] == 1

    # Same far row now matches the current self_ship_id: it must be promoted
    # to HIGH and its current world position must be read on this tick.
    out, status = telemetry.torpedoes(
        self_team=0, sampling=sampler, now=0.4, context=ctx,
        self_ship_id=12345)
    assert len(out) == 1
    row = out[0]
    assert row['sampling']['group'] == 'high'
    assert row['isOwn'] is True
    assert row['isOwnReason'] == 'exactSelfShipIdMatch'
    assert row['isOwnSource'] == 'battle.getSelfPlayerInfo().shipId == torpedo.ownerId'
    assert row['position'] == [0.0, 0.0, 2000.0]
    assert row['sampling']['positionStatus'] == 'available'
    assert row['sampling']['reason'] == 'highDue'
    assert far.reads['position'] == 2
    # The sampled row performs exactly one additional owner lookup on promotion.
    assert battle.owner_calls[12345] == 2


def test_low_row_stays_low_and_skips_reads_when_self_id_does_not_match():
    """A far enemy LOW row that does not match self_ship_id keeps skipping."""
    far = CountedTorpedo(
        uiId=2, ownerId=7001, ownerTeamId=1, shotId=1,
        position=(0.0, 0.0, 2000.0))
    telemetry, battle = adapter([far])
    sampler = TorpedoSamplingGroups()
    ctx = context()

    telemetry.torpedoes(
        self_team=0, sampling=sampler, now=0.0, context=ctx,
        self_ship_id=12345)
    assert far.reads['position'] == 1
    assert battle.owner_calls[7001] == 1

    out, status = telemetry.torpedoes(
        self_team=0, sampling=sampler, now=0.2, context=ctx,
        self_ship_id=12345)
    assert not out
    assert status['sampling']['low']['status'] == 'notSampled'
    assert far.reads['position'] == 1
    assert battle.owner_calls[7001] == 1
