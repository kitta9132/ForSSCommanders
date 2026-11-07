"""0.3.45 slow information groups: selfSystems, torpedoArmament, map calibration
snapshot, and far-ship world position/yaw cadence."""
import math
import os
import sys
from types import MethodType, SimpleNamespace as Obj

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                              'PnFMods', 'WowsExtractor'))

from test_health_sampling_cadence import (
    CC_KEYS, make_collector, Battle, Hub, method)


class _SelfShip(object):
    def __init__(self, position=(0.0, 0.0, 0.0)):
        self._position = position
        self.position_reads = 0

    def getPosition(self):
        self.position_reads += 1
        return self._position

    def getConsumablesState(self):
        return 'available', []

    def getRadarInfo(self):
        return 'available', None

    def getHydroAcousticSearchInfo(self):
        return 'available', None

    def getSubmarineLocatorInfo(self):
        return 'available', None

    def getTorpedoesModulesState(self):
        return []


class _Ship(object):
    def __init__(self, ship_id, player_id, position=None, map_pos=(0.5, 0.5),
                 yaw=0.1):
        self._Ship__id = ship_id
        self.id = ship_id
        self.uiId = ship_id
        self.playerId = player_id
        self.teamId = 2
        self.isAlive = lambda: True
        self._position = position
        self.position_reads = 0
        self._map_pos = map_pos
        self._yaw = yaw
        self.yaw_reads = 0

    def getPosition(self):
        self.position_reads += 1
        return self._position

    @property
    def yaw(self):
        self.yaw_reads += 1
        return self._yaw


def _self_info():
    return Obj(id=1, teamId=1, shipGameData={'health': 1000, 'maxHealth': 1000,
                                              'speed': 10})


def _make_collector_with_ships(ships, self_ship, entities=None):
    if entities is None:
        entities = []
    players = [{'playerId': ship.playerId, 'shipId': ship._Ship__id,
                'teamId': ship.teamId}
               for ship in ships]
    c, _ns = make_collector(entities, ships, players, _self_info(), self_ship)
    # Inject a deterministic map index keyed by playerId, since the real
    # _collect_map_positions reads from dataHub avatar entities.
    def _collect_map_positions(avatar_entities=None):
        c._mapVisibility = {}
        c._mapVisibilityDiagnostics = {}
        return {
            ship.playerId: (ship._map_pos[0], ship._map_pos[1], 0.0)
            for ship in ships
        }
    c._collect_map_positions = _collect_map_positions
    return c


def _fixed_calibration(scale=2000.0, status='available'):
    class FixedCalibration(object):
        def update(self, samples, now):
            pass

        def live_model_status(self):
            return {
                'status': status,
                'coefficients': {
                    'worldX': {'mapAxis': 'nx', 'scale': scale, 'offset': 0.0},
                    'worldZ': {'mapAxis': 'ny', 'scale': scale, 'offset': 0.0},
                },
            }

        def snapshot(self):
            return {'status': status}

        def map_to_world(self, mx, my):
            coeffs = self.live_model_status()['coefficients']
            x = coeffs['worldX']
            z = coeffs['worldZ']
            return [x['scale'] * mx + x['offset'], 0.0,
                    z['scale'] * my + z['offset']]

        def world_to_map(self, *args):
            return None

    return FixedCalibration()


def test_observer_position_is_not_used_as_self_distance_origin():
    far_ship = _Ship(1000, 7000, position=(1200.0, 0.0, 1200.0),
                     map_pos=(0.6, 0.6))
    c = _make_collector_with_ships([far_ship], _SelfShip())
    c._mapCalibration = _fixed_calibration()
    c._shipWorldPositionSamplingDue = False
    c._shipWorldPositionSeenIds = {(int, 1000): True}
    c._shipWorldPositionSeenOrder = [(int, 1000)]
    c._build_self = lambda *args, **kwargs: {
        'position': [0.0, 0.0, 0.0], 'isObserver': True}
    c._build_state(0.2)
    assert far_ship.position_reads == 1


def test_signed_calibration_scales_are_lengths_for_far_threshold():
    c = _make_collector_with_ships([], _SelfShip())
    c._mapCalibration = _fixed_calibration(scale=-2000.0)
    c._shipWorldPositionFarDivisor = 5.0
    assert c._ship_world_position_threshold() == 400.0


def test_infinite_divisor_falls_back_instead_of_zero_radius():
    c = _make_collector_with_ships([], _SelfShip())
    c._mapCalibration = _fixed_calibration()
    c._shipWorldPositionFarDivisor = float('inf')
    assert c._ship_world_position_threshold() == 400.0


def test_unknown_ship_id_never_skips_world_read():
    ship = _Ship(None, 7000, position=(1200.0, 0.0, 1200.0),
                 map_pos=(0.6, 0.6))
    c = _make_collector_with_ships([ship], _SelfShip())
    c._mapCalibration = _fixed_calibration()
    c._shipWorldPositionSamplingDue = False
    for now in (0.0, 0.2):
        c._build_ships(now, players_sample={'status': 'complete', 'index': {}},
                       self_position=[0.0, 0.0, 0.0])
    assert ship.position_reads == 2


def test_self_systems_and_torpedo_armament_sampling_metadata():
    ship = _Ship(1000, 7000)
    self_ship = _SelfShip()
    c = _make_collector_with_ships([ship], self_ship)
    c._selfSystemsSamplingDue = True
    c._torpedoArmamentSamplingDue = True
    state = c._build_state(0.0)
    assert state['selfSystems']['sampling']['status'] == 'sampled'
    assert state['torpedoArmament']['sampling']['status'] == 'sampled'

    c._selfSystemsSamplingDue = False
    c._torpedoArmamentSamplingDue = False
    state = c._build_state(0.1)
    assert state['selfSystems']['sampling']['status'] == 'notSampled'
    assert state['torpedoArmament']['sampling']['status'] == 'notSampled'
    assert state['selfSystems']['sampling']['sampleTs'] is None
    assert state['selfSystems']['status'] == 'notSampled'
    assert state['torpedoArmament']['status'] == 'notSampled'
    assert state['torpedoArmament']['available'] is False


def test_map_calibration_update_and_snapshot_gating():
    class CountedCalibration(object):
        def __init__(self):
            self.update_calls = 0
            self.live_calls = 0
            self.snapshot_calls = 0

        def update(self, samples, now):
            self.update_calls += 1

        def live_model_status(self):
            self.live_calls += 1
            return {'status': 'available', 'coefficients': None}

        def snapshot(self):
            self.snapshot_calls += 1
            return {'status': 'available', 'heavy': True}

        def map_to_world(self, *args):
            return None

        def world_to_map(self, *args):
            return None

    ship = _Ship(1000, 7000)
    self_ship = _SelfShip()
    c = _make_collector_with_ships([ship], self_ship)
    c._mapCalibration = CountedCalibration()
    c._mapCalibrationSnapshotDue = False
    c._build_state(0.0)
    assert c._mapCalibration.update_calls == 1
    # live_model_status is used both for the torpedo sampling context and for
    # the ships diagnostic output.
    assert c._mapCalibration.live_calls == 2
    assert c._mapCalibration.snapshot_calls == 0

    c._mapCalibrationSnapshotDue = True
    state = c._build_state(1.0)
    assert c._mapCalibration.update_calls == 2
    assert c._mapCalibration.live_calls == 4
    assert c._mapCalibration.snapshot_calls == 1
    assert state['diag']['mapCalibrationSnapshot']['heavy'] is True
    assert state['diag']['mapCalibrationSnapshot']['sampling']['status'] == 'sampled'
    assert state['diag']['mapCalibrationSnapshot']['sampling']['sampleTs'] == 1.0
    assert state['diag']['mapCalibrationSnapshot']['sampling']['intervalSeconds'] == 1.0


def test_far_ship_world_position_is_skipped_when_not_due():
    self_ship = _SelfShip(position=(0.0, 0.0, 0.0))
    # map position (0.6, 0.6) -> estimated (1200, 0, 1200) -> distance ~1697
    # threshold = min(2000,2000)/5 = 400, so it is far.
    far_ship = _Ship(1000, 7000, position=None, map_pos=(0.6, 0.6))
    c = _make_collector_with_ships([far_ship], self_ship)
    c._mapCalibration = _fixed_calibration(2000.0)
    players_sample = {
        'status': 'complete',
        'index': {(int, far_ship._Ship__id): {
            'playerId': far_ship.playerId, 'teamId': far_ship.teamId}}}

    # First observation is sampled even when far/non-due (new ship HIGH rule).
    c._shipWorldPositionSamplingDue = False
    rows, _diag = c._build_ships(
        0.0, ui_hp={}, avatar_entities=None, players_sample=players_sample,
        health_due=True, calibration_snapshot_due=False,
        self_position=[0.0, 0.0, 0.0])
    assert len(rows) == 1
    assert far_ship.position_reads == 1
    assert far_ship.yaw_reads == 1

    # After the first observation, a far non-due ship skips the getter.
    rows, diag = c._build_ships(
        1.0, ui_hp={}, avatar_entities=None, players_sample=players_sample,
        health_due=True, calibration_snapshot_due=False,
        self_position=[0.0, 0.0, 0.0])
    assert len(rows) == 1
    assert rows[0]['positionReadStatus']['status'] == 'notSampled'
    assert rows[0]['positionReadStatus']['reason'] == 'farShipWorldPositionSampling'
    assert rows[0]['positionReadPolicy']['policy'] == 'farShip1Hz'
    assert 'position' not in rows[0]
    assert far_ship.position_reads == 1
    assert far_ship.yaw_reads == 1
    assert rows[0]['yawSampling']['status'] == 'notSampled'
    assert rows[0]['yawSampling']['source'] == 'farShipWorldPositionSampling'
    assert 'yaw' not in rows[0]

    # When the slow gate becomes due the position is read again.
    c._shipWorldPositionSamplingDue = True
    rows, _diag = c._build_ships(
        2.0, ui_hp={}, avatar_entities=None, players_sample=players_sample,
        health_due=True, calibration_snapshot_due=False,
        self_position=[0.0, 0.0, 0.0])
    assert rows[0]['positionReadStatus']['status'] == 'unknown'
    assert rows[0]['positionReadStatus']['attempted'] is True
    assert rows[0]['positionReadStatus']['reason'] == 'none'
    assert far_ship.position_reads == 2
    assert far_ship.yaw_reads == 2


def test_near_ship_world_position_is_always_read():
    self_ship = _SelfShip(position=(0.0, 0.0, 0.0))
    near_ship = _Ship(1000, 7000, position=(1.0, 2.0, 3.0),
                      map_pos=(0.001, 0.001))
    c = _make_collector_with_ships([near_ship], self_ship)
    # Small scale -> threshold 20 world units; map_pos (0.001,0.001) -> 0.1 world
    # distance ~0.14 < 20 -> near.
    c._mapCalibration = _fixed_calibration(100.0)
    c._shipWorldPositionSamplingDue = False
    players_sample = {
        'status': 'complete',
        'index': {(int, near_ship._Ship__id): {
            'playerId': near_ship.playerId, 'teamId': near_ship.teamId}}}
    rows, _diag = c._build_ships(
        0.0, ui_hp={}, avatar_entities=None, players_sample=players_sample,
        health_due=True, calibration_snapshot_due=False,
        self_position=[0.0, 0.0, 0.0])
    assert rows[0]['positionReadStatus']['attempted'] is True
    assert rows[0]['positionReadStatus']['status'] == 'available'
    assert rows[0]['position'] == [1.0, 2.0, 3.0]
    assert rows[0]['yaw'] == 0.1
    assert rows[0]['yawSampling']['status'] == 'sampled'
    assert rows[0]['yawSampling']['source'] == 'ship.yaw'


def test_disabled_slow_group_reverts_to_core_cadence():
    ship = _Ship(1000, 7000)
    self_ship = _SelfShip()
    c = _make_collector_with_ships([ship], self_ship)
    c._stateInterval = 0.2
    # With the group OFF, _*_sampling_due returns True every tick (core
    # cadence). Simulate the due flags that _tick would have set.
    c._selfSystemsSamplingEnabled = False
    c._torpedoArmamentSamplingEnabled = False
    c._shipWorldPositionSamplingEnabled = False
    c._selfSystemsSamplingDue = True
    c._torpedoArmamentSamplingDue = True
    c._shipWorldPositionSamplingDue = True
    state = c._build_state(0.0)
    assert state['selfSystems']['sampling']['status'] == 'sampled'
    assert state['torpedoArmament']['sampling']['status'] == 'sampled'
    assert state['selfSystems']['sampling']['intervalSeconds'] == 0.2
    assert state['torpedoArmament']['sampling']['intervalSeconds'] == 0.2


def test_build_state_shares_self_position_with_ship_classifier():
    """The same getPosition() call feeds self state and far-ship distance."""
    self_ship = _SelfShip(position=(10.0, 0.0, 10.0))
    far_ship = _Ship(1000, 7000, position=None, map_pos=(0.6, 0.6))
    c = _make_collector_with_ships([far_ship], self_ship)
    c._mapCalibration = _fixed_calibration(2000.0)
    # The ship is new, so it is sampled regardless of far status. Mark it seen
    # beforehand so we can verify the far/non-due skip path.
    c._shipWorldPositionSeenIds[(int, far_ship._Ship__id)] = True
    c._shipWorldPositionSamplingDue = False
    c._selfSystemsSamplingDue = False
    c._torpedoArmamentSamplingDue = False
    c._torpedoDepthSamplingEnabled = False
    c._torpedoStateSamplingEnabled = False
    c._diagnosticsEnabled = False
    state = c._build_state(0.0)
    # getPosition() on self_ship should be called exactly once.
    assert self_ship.position_reads == 1
    assert state['self']['position'] == [10.0, 0.0, 10.0]
    # Far ship should be skipped (position not read).
    ship_row = state['ships'][0]
    assert ship_row['positionReadStatus']['status'] == 'notSampled'
    assert far_ship.position_reads == 0


def test_calibration_unavailable_keeps_all_ships_on_core_path():
    self_ship = _SelfShip(position=(0.0, 0.0, 0.0))
    far_ship = _Ship(1000, 7000, position=(1.0, 2.0, 3.0),
                     map_pos=(0.6, 0.6))
    c = _make_collector_with_ships([far_ship], self_ship)
    c._mapCalibration = _fixed_calibration(2000.0, status='unknown')
    c._shipWorldPositionSamplingDue = False
    players_sample = {
        'status': 'complete',
        'index': {(int, far_ship._Ship__id): {
            'playerId': far_ship.playerId, 'teamId': far_ship.teamId}}}
    rows, _diag = c._build_ships(
        0.0, ui_hp={}, avatar_entities=None, players_sample=players_sample,
        health_due=True, calibration_snapshot_due=False,
        self_position=[0.0, 0.0, 0.0])
    assert rows[0]['positionReadStatus']['status'] == 'available'
    assert rows[0]['position'] == [1.0, 2.0, 3.0]
    assert far_ship.position_reads == 1


def test_ship_world_position_threshold_rejects_non_finite_values():
    class BadCalibration(object):
        def __init__(self, scale):
            self._scale = scale

        def live_model_status(self):
            return {
                'status': 'available',
                'coefficients': {
                    'worldX': {'mapAxis': 'nx', 'scale': self._scale,
                               'offset': 0.0},
                    'worldZ': {'mapAxis': 'ny', 'scale': self._scale,
                               'offset': 0.0},
                },
            }

    c, _ = make_collector([], [], [], _self_info(), _SelfShip())
    for bad_scale in (float('nan'), float('inf'), -float('inf'), 0.0):
        c._mapCalibration = BadCalibration(bad_scale)
        assert c._ship_world_position_threshold() is None
    c._mapCalibration = BadCalibration(1000.0)
    c._shipWorldPositionFarDivisor = float('nan')
    assert c._ship_world_position_threshold() == 200.0
    c._shipWorldPositionFarDivisor = 0.0
    assert c._ship_world_position_threshold() == 200.0
    c._shipWorldPositionFarDivisor = -5.0
    assert c._ship_world_position_threshold() == 200.0
    c._shipWorldPositionFarDivisor = 5.0
    assert c._ship_world_position_threshold() == 200.0


def test_seen_id_tracker_is_bounded_and_safe_on_overflow():
    self_ship = _SelfShip(position=(0.0, 0.0, 0.0))
    ships = [_Ship(1000 + i, 7000 + i, position=(float(i), 0.0, 0.0),
                   map_pos=(0.6, 0.6)) for i in range(4)]
    c = _make_collector_with_ships(ships, self_ship)
    c._shipWorldPositionSeenIdsLimit = 2
    c._shipWorldPositionSeenIds = {}
    c._shipWorldPositionSeenOrder = []
    c._mapCalibration = _fixed_calibration(2000.0)
    c._shipWorldPositionSamplingDue = False

    players_sample = {
        'status': 'complete',
        'index': {(int, s._Ship__id): {
            'playerId': s.playerId, 'teamId': s.teamId}
                  for s in ships}}
    for frame in range(5):
        rows, _diag = c._build_ships(
            float(frame), ui_hp={}, avatar_entities=None,
            players_sample=players_sample,
            health_due=True, calibration_snapshot_due=False,
            self_position=[0.0, 0.0, 0.0])
        assert len(rows) == len(ships)
        assert len(c._shipWorldPositionSeenOrder) <= 2
        assert len(c._shipWorldPositionSeenIds) <= 2
    # Every ship was sampled at least once; bounded churn keeps memory capped.
    assert all(ship.position_reads >= 1 for ship in ships)


def _scheduler_collector():
    ns = {'_get': lambda obj, name, default=None: getattr(obj, name, default)}
    for name in ('_deadline_due', '_self_systems_sampling_due',
                 '_torpedo_armament_sampling_due',
                 '_ship_world_position_sampling_due',
                 '_map_calibration_snapshot_due'):
        method(name, ns)
    c, _ = make_collector([], [], [], _self_info(), _SelfShip())
    c._deadline_due = MethodType(ns['_deadline_due'], c)
    return c, ns


def test_slow_group_schedulers_clamp_interval_and_handle_non_finite():
    c, ns = _scheduler_collector()
    # Non-finite intervals fall back to 1.0 s; sub-0.2 intervals are clamped.
    expectations = {
        0.05: 0.2,
        float('nan'): 1.0,
        float('inf'): 1.0,
        -float('inf'): 1.0,
    }
    for interval, expected in expectations.items():
        c._selfSystemsSamplingInterval = interval
        c._selfSystemsSamplingEnabled = True
        c._selfSystemsSamplingNextDue = None
        assert ns['_self_systems_sampling_due'](c, 0.0) is True
        assert c._selfSystemsSamplingNextDue == expected
        c._torpedoArmamentSamplingInterval = interval
        c._torpedoArmamentSamplingEnabled = True
        c._torpedoArmamentSamplingNextDue = None
        assert ns['_torpedo_armament_sampling_due'](c, 0.0) is True
        assert c._torpedoArmamentSamplingNextDue == expected
        c._shipWorldPositionSamplingInterval = interval
        c._shipWorldPositionSamplingEnabled = True
        c._shipWorldPositionSamplingNextDue = None
        assert ns['_ship_world_position_sampling_due'](c, 0.0) is True
        assert c._shipWorldPositionSamplingNextDue == expected
        c._mapCalibrationSnapshotInterval = interval
        c._mapCalibrationSnapshotNextDue = None
        assert ns['_map_calibration_snapshot_due'](c, 0.0) is True
        assert c._mapCalibrationSnapshotNextDue == expected


def test_slow_group_schedulers_off_revert_to_core_and_reset_deadline():
    c, ns = _scheduler_collector()
    c._selfSystemsSamplingEnabled = False
    c._selfSystemsSamplingNextDue = 5.0
    c._selfSystemsSamplingLastNow = 1.0
    assert ns['_self_systems_sampling_due'](c, 2.0) is True
    assert c._selfSystemsSamplingNextDue is None
    assert c._selfSystemsSamplingLastNow is None
    c._torpedoArmamentSamplingEnabled = False
    c._torpedoArmamentSamplingNextDue = 5.0
    c._torpedoArmamentSamplingLastNow = 1.0
    assert ns['_torpedo_armament_sampling_due'](c, 2.0) is True
    assert c._torpedoArmamentSamplingNextDue is None
    assert c._torpedoArmamentSamplingLastNow is None
    c._shipWorldPositionSamplingEnabled = False
    c._shipWorldPositionSamplingNextDue = 5.0
    c._shipWorldPositionSamplingLastNow = 1.0
    assert ns['_ship_world_position_sampling_due'](c, 2.0) is True
    assert c._shipWorldPositionSamplingNextDue is None
    assert c._shipWorldPositionSamplingLastNow is None


def test_new_near_ship_is_sampled_on_first_observation_even_when_non_due():
    self_ship = _SelfShip(position=(0.0, 0.0, 0.0))
    near_ship = _Ship(1000, 7000, position=(1.0, 2.0, 3.0),
                      map_pos=(0.001, 0.001))
    c = _make_collector_with_ships([near_ship], self_ship)
    c._mapCalibration = _fixed_calibration(100.0)
    c._shipWorldPositionSamplingDue = False
    players_sample = {
        'status': 'complete',
        'index': {(int, near_ship._Ship__id): {
            'playerId': near_ship.playerId, 'teamId': near_ship.teamId}}}
    rows, _diag = c._build_ships(
        0.0, ui_hp={}, avatar_entities=None, players_sample=players_sample,
        health_due=True, calibration_snapshot_due=False,
        self_position=[0.0, 0.0, 0.0])
    assert rows[0]['positionReadStatus']['status'] == 'available'
    assert rows[0]['position'] == [1.0, 2.0, 3.0]
    assert near_ship.position_reads == 1


def test_clock_drift_reanchors_deadline_without_catch_up():
    c, ns = _scheduler_collector()
    # Normal progression: 1s interval, next due at 1.0.
    assert ns['_deadline_due'](c, 0.0, True, 1.0, None, None) == (True, 1.0, 0.0)
    # Backwards/frozen clock (now < last_now) resets the deadline so the
    # current tick is sampled and does not strand a future deadline.
    assert ns['_deadline_due'](c, 0.5, True, 1.0, 2.0, 1.0) == (True, 1.5, 0.5)
    # Stall longer than one interval: re-anchor at now+interval, no catch-up.
    assert ns['_deadline_due'](c, 5.0, True, 1.0, 1.0, 0.0) == (True, 6.0, 5.0)
    # Frozen clock before deadline: not due.
    assert ns['_deadline_due'](c, 0.9, True, 1.0, 1.0, 0.0)[0] is False


def _load_config_namespace():
    ns = {
        '_cfg_float': lambda cfg, key, default: (
            float(cfg[key]) if key in cfg and cfg[key] not in (None, '')
            else default),
        '_load_mod_config': lambda: {},
        'normalize_torpedo_sampling_settings': None,
        'logInfo': lambda *args: None,
        'logError': lambda *args: None,
        'PerformanceProfiler': object,
        '_AsyncWriter': object,
        '_threading': None,
    }
    try:
        method('_load_config', ns)
    except Exception:
        pass
    return ns


def test_config_missing_slow_group_keys_use_defaults():
    ns = _load_config_namespace()
    c, _ = make_collector([], [], [], _self_info(), _SelfShip())
    c._collectionEnabled = True
    c._load_config = MethodType(ns['_load_config'], c)
    c._load_config()
    assert c._selfSystemsSamplingEnabled is True
    assert c._selfSystemsSamplingInterval == 1.0
    assert c._torpedoArmamentSamplingEnabled is True
    assert c._torpedoArmamentSamplingInterval == 1.0
    assert c._shipWorldPositionSamplingEnabled is True
    assert c._shipWorldPositionSamplingInterval == 1.0
    assert c._shipWorldPositionFarDivisor == 5.0
    assert c._mapCalibrationSnapshotInterval == 1.0


def test_config_off_groups_revert_to_core_cadence():
    ns = _load_config_namespace()
    c, sched = _scheduler_collector()
    c._collectionEnabled = True
    c._load_config = MethodType(ns['_load_config'], c)
    ns['_load_mod_config'] = lambda: {
        'collection_enabled': 'true',
        'self_systems_sampling_enabled': 'false',
        'torpedo_armament_sampling_enabled': 'false',
        'ship_world_position_sampling_enabled': 'false',
    }
    c._load_config()
    assert c._selfSystemsSamplingEnabled is False
    assert c._torpedoArmamentSamplingEnabled is False
    assert c._shipWorldPositionSamplingEnabled is False
    c._stateInterval = 0.2
    assert sched['_self_systems_sampling_due'](c, 0.0) is True
    assert c._selfSystemsSamplingNextDue is None
    assert sched['_torpedo_armament_sampling_due'](c, 0.0) is True
    assert c._torpedoArmamentSamplingNextDue is None
    assert sched['_ship_world_position_sampling_due'](c, 0.0) is True
    assert c._shipWorldPositionSamplingNextDue is None


def test_map_calibration_update_is_equivalent_to_observe_for_live_model():
    """update() + live_model_status() replaces observe() without breaking the
    live model contract used by the rest of the collector."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'res_mods',
                                  'PnFMods', 'WowsExtractor'))
    from map_calibration import MapCalibration
    samples = []
    for i in range(20):
        nx = (i % 5) * 0.2 + 0.1
        ny = (i // 5) * 0.2 + 0.1
        samples.append((nx, ny, 3000.0 * nx - 1500.0,
                        3000.0 * ny - 1500.0))
    old = MapCalibration()
    new = MapCalibration()
    for i, sample in enumerate(samples):
        old.observe([sample], i + 1.0)
        new.update([sample], i + 1.0)
    old_snapshot = old.snapshot()
    new_live = new.live_model_status()
    # The live model status carries the same usable coefficients.
    assert new_live['status'] == old_snapshot['status']
    assert new_live['coefficients'] is not None
    assert new_live['fitSampleCount'] == old_snapshot['fitSampleCount']
