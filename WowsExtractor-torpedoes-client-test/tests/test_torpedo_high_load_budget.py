"""API-call budgets, not runtime estimates, for the observed B43 peak."""
from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'res_mods/PnFMods/WowsExtractor'))
from torpedo_telemetry import TorpedoTelemetry


class PeakBattle:
    def __init__(self):
        self.collection_calls = 0
        self.owner_calls = Counter()
        self.alive = True
        self.failed_owner = None
        self.rows = [SimpleNamespace(
            uiId=10000 + index, ownerId=7000 + index % 22,
            ownerTeamId=index % 22 % 2, ownerType='Destroyer',
            shotId=index + 1, type='normal', position=(index, 0, -index))
            for index in range(216)]

    def getAllTorpedoes(self):
        self.collection_calls += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.owner_calls[owner_id] += 1
        if owner_id == self.failed_owner:
            raise RuntimeError('owner unavailable')
        return SimpleNamespace(teamId=(owner_id - 7000) % 2,
                               isAlive=self.alive, isBot=True)


def test_216_torpedoes_and_22_owners_are_not_truncated_or_relooked_up_per_row():
    battle = PeakBattle()
    adapter = TorpedoTelemetry(battle, SimpleNamespace())
    rows, status = adapter.torpedoes(self_team=0)
    assert status['status'] == 'available'
    assert len(rows) == 216
    assert [row['uiId'] for row in rows] == [10000 + i for i in range(216)]
    assert battle.collection_calls == 1
    assert len(battle.owner_calls) == 22
    assert set(battle.owner_calls.values()) == {1}
    assert all(row['position'] == [i, 0, -i] for i, row in enumerate(rows))
    assert all(row['relation'] == (1 if row['ownerTeamId'] == 0 else 2)
               for row in rows)
    assert all(row['owner']['isAlive'] is True for row in rows)
    assert all(row['isOwn'] is None for row in rows)


def test_owner_failure_is_shared_only_within_the_current_snapshot():
    battle = PeakBattle()
    adapter = TorpedoTelemetry(battle, SimpleNamespace())
    battle.failed_owner = 7003
    first, status = adapter.torpedoes(self_team=0)
    assert status['available'] is True
    assert battle.owner_calls[7003] == 1
    assert all(row['owner'] is None for row in first if row['ownerId'] == 7003)
    battle.failed_owner = None
    battle.alive = False
    second, status = adapter.torpedoes(self_team=0)
    assert status['available'] is True
    assert battle.collection_calls == 2
    assert set(battle.owner_calls.values()) == {2}
    assert all(row['owner']['isAlive'] is False for row in second)
    assert all(row['owner']['isAlive'] is True for row in first
               if row['ownerId'] != 7003)


def test_missing_owner_ids_do_not_trigger_owner_lookups():
    battle = PeakBattle()
    for row in battle.rows:
        row.ownerId = None
    rows, status = TorpedoTelemetry(battle, SimpleNamespace()).torpedoes(0)
    assert status['available'] is True
    assert len(rows) == 216
    assert battle.collection_calls == 1
    assert not battle.owner_calls
    assert all(row['owner'] is None and row['isOwn'] is None for row in rows)
