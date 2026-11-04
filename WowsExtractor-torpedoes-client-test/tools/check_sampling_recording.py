"""Stream a private recording through the sampler and report anonymous budgets.

No recordings or extracted identities are written. Payload values are estimates:
original row values are retained for sampled rows, with new sampling metadata.
The game getters/FPS are not measured by this offline replay.
"""
import argparse
from collections import Counter
import json

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                      'res_mods/PnFMods/WowsExtractor'))
from torpedo_telemetry import TorpedoSamplingGroups, TorpedoTelemetry, sampling_wire_payload


class RecordedTorpedo:
    def __init__(self, row, counts):
        self.row = row
        self.counts = counts

    def __getattr__(self, name):
        self.counts['field.' + name] += 1
        return self.row.get(name)


class RecordedBattle:
    def __init__(self):
        self.rows = []
        self.owners = {}
        self.counts = Counter()

    def set_rows(self, rows):
        self.rows = [RecordedTorpedo(row, self.counts) for row in rows]
        self.owners = {row.get('ownerId'): row.get('owner') for row in rows}

    def getAllTorpedoes(self):
        self.counts['collection'] += 1
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.counts['owner'] += 1
        return self.owners.get(owner_id)


def identity(row):
    return tuple((type(row.get(name)).__name__, row.get(name))
                 for name in ('uiId', 'ownerId', 'shotId'))


def context(state):
    own = state.get('self') or {}
    fit = state.get('diag', {}).get('mapCalibration', {})
    if own.get('isObserver') is not False or fit.get('status') != 'available':
        return None
    try:
        coeff = fit['coefficients']
        x, z = coeff['worldX'], coeff['worldZ']
        if (x.get('mapAxis') not in ('nx', 'ny') or
                z.get('mapAxis') not in ('nx', 'ny') or
                x.get('mapAxis') == z.get('mapAxis') or
                isinstance(x.get('scale'), bool) or isinstance(z.get('scale'), bool)):
            return None
        width = abs(float(coeff['worldX']['scale']))
        height = abs(float(coeff['worldZ']['scale']))
        pos = own['position']
        if (len(pos) != 3 or not all(-1e9 < value < 1e9 for value in pos)
                or not 0 < width < 1e9 or not 0 < height < 1e9):
            return None
        return {'selfPosition': pos, 'mapWidth': width, 'mapHeight': height,
                'source': 'calibratedMapExtents', 'inferred': True}
    except (KeyError, TypeError, ValueError):
        return None


def encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                          allow_nan=False).encode('utf-8'))


def replay(path):
    battle = RecordedBattle()
    sampler = TorpedoSamplingGroups()
    adapter = TorpedoTelemetry(battle, None)
    counts = Counter()
    previous_battle = None
    with open(path, encoding='utf-8-sig') as stream:
        for line in stream:
            event = json.loads(line)
            state = event.get('data', {})
            if event.get('kind') != 'state' or state.get('active') is not True:
                continue
            if state.get('battleId') != previous_battle:
                sampler.clear()
                previous_battle = state.get('battleId')
            original = state.get('torpedoes', [])
            if (state.get('torpedoStatus') or {}).get('sampling') is not None:
                raise ValueError('Already-sampled recordings do not contain all per-tick positions; '
                                 'use an unsampled baseline recording.')
            battle.set_rows(original)
            classification_context = context(state)
            counts['contextMissingStates'] += classification_context is None
            counts['contextInputsMissingStates'] += (
                not (state.get('self') or {}).get('position') or
                not state.get('diag', {}).get('mapCalibration'))
            rows, status = adapter.torpedoes(
                (state.get('self') or {}).get('teamId'), sampling=sampler,
                now=state['ts'], context=classification_context)
            if (status.get('membershipComplete') is not True or
                    len(rows) != len(status.get('membership', []))):
                status['uiJoinStatus'] = 'notSampled'
                status['uiJoinReason'] = 'sampledSubset'
            rows, status = sampling_wire_payload(rows, status)
            counts['states'] += 1
            counts['originalRows'] += len(original)
            counts['originalOwnerBudget'] += len(set(
                (type(row.get('ownerId')).__name__, row.get('ownerId'))
                for row in original if row.get('ownerId') is not None))
            counts['sampledRows'] += len(rows)
            counts['membershipRows'] += len(status.get('membership', []))
            counts['incompleteMembershipStates'] += status.get('membershipComplete') is not True
            counts['originalCompactBytes'] += encoded_size(state)
            index = {identity(row): row for row in original}
            projected = []
            for row in rows:
                value = dict(index.get(identity(row), row))
                value['sampling'] = row.get('sampling')
                projected.append(value)
                counts['sampled.' + str((row.get('sampling') or {}).get('group'))] += 1
            output = dict(state, torpedoes=projected, torpedoStatus=status)
            counts['projectedCompactBytes'] += encoded_size(output)
    warnings = []
    if counts['contextMissingStates']:
        warnings.append('Classification context unavailable in some states; '
                        'those states use safety-high, not distance-based sampling.')
    if counts['contextInputsMissingStates']:
        warnings.append('Recording lacks self position or calibration inputs in some states; '
                        'torpedoes-only captures cannot reconstruct distance classification.')
    return {'budgets': dict(counts), 'apiFieldReadCounts': dict(battle.counts), 'warnings': warnings,
            'limitations': 'Offline call counts and projected bytes only; not game time or FPS.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording', type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.recording), ensure_ascii=False, indent=2))
