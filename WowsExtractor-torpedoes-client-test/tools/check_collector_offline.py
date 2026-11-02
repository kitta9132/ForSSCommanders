#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline Python 2 grammar and collector wiring checks; Python 3.10-3.12.

No game imports/calls or runtime file writes. Does not validate engine compatibility.
"""
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj
import warnings


def main():
    if not (3, 10) <= sys.version_info[:2] <= (3, 12):
        raise SystemExit('Use Python 3.10-3.12 for this optional lib2to3 check.')
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    from lib2to3.refactor import RefactoringTool
    root = Path(__file__).resolve().parents[1] / 'res_mods/PnFMods/WowsExtractor'
    sys.path.insert(0, str(root))
    expected_modules = ('Main.py', 'battle_identity.py', 'damage_tracker.py',
                        'emit_guard.py', 'ui_health.py', 'torpedo_telemetry.py',
                        'submarine_telemetry.py', 'map_calibration.py',
                        'performance_profiler.py')
    missing = [name for name in expected_modules if not (root / name).is_file()]
    if missing:
        raise SystemExit('Missing required collector modules: ' + ', '.join(missing))
    parser = RefactoringTool(['lib2to3.fixes.fix_except'])
    paths = sorted(root.glob('*.py'))
    for path in paths:
        parser.refactor_string(path.read_text(encoding='utf-8'), str(path))
    print('Python 2 grammar parsed:', len(paths), 'modules')
    print('Required modules:', ', '.join(expected_modules))
    source = str(parser.refactor_string((root / 'Main.py').read_text(), 'Main.py'))
    source = source.replace('gCollector = Collector()', 'gCollector = None')
    ns = {'__name__': 'offline_collector', '__file__': str(root / 'Main.py'), '__package__': None}
    exec(compile(source, str(root / 'Main.py'), 'exec'), ns)
    from torpedo_telemetry import TorpedoTelemetry
    from submarine_telemetry import safe_submarine_probe
    api = Obj(getAllTorpedoes=lambda: [Obj(uiId=1, ownerId=3, ownerTeamId=0,
        ownerType='Ship', shotId=2, type='future_type', position=(1, -2, 3))])
    collector = ns['Collector'].__new__(ns['Collector'])
    collector._remember_roster_vehicles = lambda entities: None
    collector._collect_avatar_health = lambda entities: {}
    collector._build_ships = lambda now, hp, entities: ([{'uiId': 5}], {})
    collector._build_self = lambda hp, info=None, ship=None: {'teamId': 0}
    collector._self_team = lambda info=None: 0
    collector._torpedoes = TorpedoTelemetry(api, Obj())
    collector._damage = Obj(snapshot=lambda: {'inflicted': {}, 'received': {}, 'teamTotal': {}})
    collector._mapCalibration = Obj(clear=lambda: None)
    collector._torpedoMotion = Obj(clear=lambda: None)
    collector._ballistics = Obj(snapshot=lambda: {'available': False}, stop=lambda: None)
    collector._active = True
    collector._collectionEnabled = True
    collector._diagnosticsEnabled = True
    collector._diagnosticsSampleDue = True
    collector._battleId = 'offline-battle'
    collection_calls = []
    ns['dataHub'] = Obj(getEntityCollections=lambda name:
                        collection_calls.append(name) or [])
    original_data_hub = ns['dataHub']
    ns['CC'] = Obj(selfVehicle='selfVehicle-key', submarine='submarine-key',
                   battery='battery-key', waveHit='waveHit-key')
    snap = collector._build_state(1.)
    assert ns['dataHub'] is original_data_hub
    duplicated = sorted(name for name in set(collection_calls)
                        if collection_calls.count(name) > 1)
    assert not duplicated, 'diagnostic collection calls were not shared: ' + repr(duplicated)
    assert collection_calls.count('avatar') == 1, collection_calls
    print('Main diagnostic collection API calls:',
          {name: collection_calls.count(name) for name in sorted(set(collection_calls))})
    assert snap['ships'] == [{'uiId': 5}]
    assert snap['torpedoes'][0]['position'] == [1., -2., 3.]
    assert snap['torpedoes'][0]['type'] == 'future_type'
    assert snap['selfSystems']['consumables']['status'] == 'unsupported'
    assert snap['selfSubmarineProbe']['sampleTs'] == 1.
    assert snap['waveHitProbe']['sampleTs'] == 1.
    json.dumps(snap, allow_nan=False)

    def fail():
        raise RuntimeError('offline injected failure')

    collector._torpedoes = Obj(torpedoes=lambda team: fail(),
                               armament=lambda ship=None: fail())
    snap = collector._build_state(2.)
    assert snap['ships'] == [{'uiId': 5}]
    assert snap['torpedoes'] == [] and snap['torpedoStatus']['status'] == 'unknown'
    assert snap['torpedoArmament']['available'] is False
    assert snap['selfSubmarineProbe']['status'] == 'unknown'
    ns['safe_submarine_probe'] = fail
    snap = collector._build_state(3.)
    assert snap['ships'] == [{'uiId': 5}]
    assert snap['self'] == {'teamId': 0}
    assert snap['selfSubmarineProbe']['status'] == 'unknown'
    assert snap['waveHitProbe']['status'] == 'unknown'
    json.dumps(snap, allow_nan=False)
    collector._stop_tick = lambda: None
    frames = []
    collector._write_state = frames.append
    collector._on_battle_quit()
    assert frames[0]['active'] is False and frames[0]['torpedoes'] == []
    assert frames[0]['torpedoStatus']['available'] is False
    assert frames[0]['torpedoArmament']['available'] is False
    print('Collector live state, failure isolation and terminal state: OK')
    # Exercise the actual map/ship integration, not only the standalone fitter.
    from map_calibration import MapCalibration
    geo = ns['Collector'].__new__(ns['Collector'])
    geo._mapCalibration = MapCalibration()
    geo._mapVisibility = {}
    geo._mapVisibilityDiagnostics = {}
    geo._damage = Obj(remember=lambda *args: None)
    geo._relation = lambda team: 1 if team == 0 else 2
    geo._get_ship_position = lambda ship, pid, vid: ship.pos
    own = Obj(id=1, teamId=0, uiId=1, pos=[0., 0., 0.], isAlive=lambda: True)
    enemy = Obj(id=2, teamId=1, uiId=2, pos=None, isAlive=lambda: True)
    ns['battle'] = Obj(getAllShips=lambda: [own, enemy],
                       getPlayerByVehicleId=lambda vid: Obj(id=vid, teamId=vid - 1))
    geo._collect_map_positions = lambda avatar_entities=None: {
        1: (.5, .5, 0.), 2: (.6, .4, 0.)}
    ships, diagnostics = geo._build_ships(1.)
    assert ships[0]['positionSource'] == 'shipOrPlayerApi'
    assert ships[1].get('position') is None  # no invented fit from one point
    assert ships[1]['mapPositionFreshness'] == 'unverified'
    assert diagnostics['mapSamples'] == 1
    grid = [(.1 + i * .15, .2 + j * .1) for i in range(5) for j in range(5)]
    geo._mapCalibration.observe([(mx, my, 1200. * mx - 600., 600. - 1200. * my)
                                 for mx, my in grid], 2.)
    ships, diagnostics = geo._build_ships(3.)
    assert diagnostics['mapCalibration']['status'] == 'available'
    assert ships[1]['positionSource'] == 'calibratedMapPosition'
    assert abs(ships[1]['position'][0] - 120.) < 1e-6
    assert abs(ships[1]['position'][2] - 120.) < 1e-6
    ns['battle'].getAllShips = lambda: [own]
    ships, diagnostics = geo._build_ships(4.)
    assert len(ships) == 1
    assert 'ghosts' not in diagnostics
    assert not any(key in ships[0] for key in (
        'lastPosition', 'lastPositionSource', 'lastNx', 'lastNy',
        'lastYaw', 'lastHealth', 'lastSeenTs', 'staleSeconds'))
    print('Collector map integration, source labels and uncalibrated position: OK')
    print('These are offline doubles, not a game client test.')


if __name__ == '__main__':
    main()
