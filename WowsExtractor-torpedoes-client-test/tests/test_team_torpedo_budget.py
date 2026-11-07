"""0.3.41 team-torpedo-budget policy and Main.py config wiring."""
from collections import Counter
import os
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace as Obj

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, 'res_mods', 'PnFMods', 'WowsExtractor'))

from torpedo_telemetry import (  # noqa: E402
    LegacyTorpedoSamplingGroups, SAMPLING_ENEMY_HIGH_BUDGET,
    SAMPLING_RADIUS_DIVISOR, SAMPLING_UI_SETTING_KEYS, TORPEDO_SAMPLING_POLICY,
    TorpedoSamplingGroups, TorpedoSamplingSettings, TorpedoTelemetry,
    normalize_torpedo_sampling_settings, sampling_wire_payload,
    torpedo_sampling_ui_contract)


class Torpedo(object):
    """Plain public-field row; no hidden game internals."""

    def __init__(self, uiId, ownerId, ownerTeamId, position,
                 shotId=1, type='normal', ownerType='Ship'):
        self.uiId = uiId
        self.ownerId = ownerId
        self.ownerTeamId = ownerTeamId
        self.ownerType = ownerType
        self.shotId = shotId
        self.type = type
        self.position = position


class Owner(object):
    def __init__(self, isPlayer, teamId=0):
        self.isPlayer = isPlayer
        self.teamId = teamId
        self.isAlive = True
        self.isBot = isPlayer is not True


class Battle(object):
    def __init__(self, rows, owners=None):
        self.rows = rows
        self.owners = dict(owners or {})
        self.owner_calls = Counter()

    def getAllTorpedoes(self):
        return self.rows

    def getTorpedoOwnerById(self, owner_id):
        self.owner_calls[owner_id] += 1
        return self.owners.get(owner_id)


def context(width=3000, height=3000, self_position=(0.0, 0.0, 0.0)):
    return {'selfPosition': list(self_position), 'mapWidth': width,
            'mapHeight': height, 'source': 'calibratedMapExtents',
            'inferred': True}


def policy(rows, owners=None):
    battle = Battle(rows, owners)
    return TorpedoTelemetry(battle, Obj()), battle


# --- settings and UI contract ----------------------------------------------

def test_settings_defaults_match_the_policy():
    settings = TorpedoSamplingSettings()
    assert TORPEDO_SAMPLING_POLICY == '0.3.41-team-torpedo-budget'
    assert settings.radius_divisor == SAMPLING_RADIUS_DIVISOR == 5.0
    assert settings.enemy_high_budget == SAMPLING_ENEMY_HIGH_BUDGET == 20
    assert settings.high_interval == 0.2
    assert settings.low_interval == 0.5
    assert settings.classification_interval == 5.0
    assert settings.ally_low is True


def test_settings_normalize_clamps_bad_values_without_raising():
    settings = normalize_torpedo_sampling_settings({
        'radius_divisor': '0', 'enemy_high_budget': '99999',
        'high_interval': 'nan', 'low_interval': 'not-a-number',
        'ally_low': 'false'}, source='unit')
    assert settings.radius_divisor == 1.0          # clamped low
    assert settings.enemy_high_budget == 512       # clamped high
    assert settings.high_interval == 0.2           # nonFinite -> default
    assert settings.low_interval == 0.5            # nonNumeric -> default
    assert settings.ally_low is False
    assert settings.source == 'unit'
    assert ('radius_divisor', 'clampedLow') in settings.issues


def test_ui_contract_publishes_only_the_two_knobs():
    contract = torpedo_sampling_ui_contract()
    assert contract['policy'] == TORPEDO_SAMPLING_POLICY
    assert tuple(contract['publishedFields']) == SAMPLING_UI_SETTING_KEYS
    assert [field['key'] for field in contract['fields']] == list(
        SAMPLING_UI_SETTING_KEYS)
    assert 'high_interval' in contract['internalFields']
    assert 'ally_low' in contract['internalFields']
    assert 'high_interval' not in contract['publishedFields']


# --- classification policy --------------------------------------------------

def test_strict_own_is_high_at_every_distance_and_off_budget():
    # Under strict self ship ID, every own torpedo shares the self owner's ID.
    far_own = Torpedo(1, 900, 5, (0, 0, 2000.0))
    near_own = Torpedo(2, 900, 5, (0, 0, 100.0))
    enemies = [Torpedo(10 + index, 700 + index, 1, (0, 0, 200.0 + index))
               for index in range(3)]
    telemetry, _ = policy(
        [far_own, near_own] + enemies,
        {900: Owner(True, 5),
         700: Owner(False, 1), 701: Owner(False, 1), 702: Owner(False, 1)})
    rows, status = telemetry.torpedoes(
        0, TorpedoSamplingGroups(), 0.0, context(), self_ship_id=900)
    groups = dict((row['uiId'], row['sampling']['group']) for row in rows)
    assert groups[1] == 'high'   # far own still high
    assert groups[2] == 'high'
    team = status['sampling']['teamPolicy']
    assert team['ownHigh'] == 2
    assert team['enemyHigh'] == 3
    assert team['enemyHighLimit'] == 20


def test_confirmed_ally_is_low_on_first_observation_and_after():
    ally = Torpedo(1, 800, 0, (0, 0, 100.0))  # same team, isPlayer is False
    telemetry, _ = policy([ally], {800: Owner(False, 0)})
    sampler = TorpedoSamplingGroups()
    first, status = telemetry.torpedoes(
        0, sampler, 0.0, context(), self_ship_id=799)
    assert first[0]['sampling']['group'] == 'low'
    assert first[0]['sampling']['reason'] == 'classification'
    assert first[0]['sampling']['intervalSeconds'] == 0.5
    assert first[0]['sampling']['provisional'] is True
    assert status['sampling']['teamPolicy']['allyLow'] == 1

    out, status = telemetry.torpedoes(
        0, sampler, 5.0, context(), self_ship_id=799)
    assert out[0]['sampling']['group'] == 'low'
    assert out[0]['sampling']['provisional'] is False
    assert out[0]['sampling']['distanceStatus'] == 'near'


def test_same_team_unknown_isplayer_is_a_safety_high_not_an_ally():
    row = Torpedo(1, 810, 0, (0, 0, 100.0))
    telemetry, _ = policy([row], {810: Owner(None, 0)})
    out, status = telemetry.torpedoes(0, TorpedoSamplingGroups(), 0.0, context())
    assert out[0]['sampling']['group'] == 'high'
    team = status['sampling']['teamPolicy']
    assert team['safetyHigh'] == 1
    assert team['unknownTeamHigh'] == 1
    assert team['allyLow'] == 0


def test_enemy_unknown_distance_is_a_safety_high_not_counted():
    row = Torpedo(1, 820, 1, None)
    telemetry, _ = policy([row], {820: Owner(False, 1)})
    out, status = telemetry.torpedoes(0, TorpedoSamplingGroups(), 0.0, context())
    assert out[0]['sampling']['group'] == 'high'
    assert out[0]['sampling']['distanceStatus'] == 'unknown'
    team = status['sampling']['teamPolicy']
    assert team['unknownDistanceHigh'] == 1
    assert team['enemyHigh'] == 0


def test_unknown_team_is_a_safety_high():
    row = Torpedo(1, 830, None, (0, 0, 100.0))
    telemetry, _ = policy([row], {830: Owner(False, 1)})
    out, status = telemetry.torpedoes(0, TorpedoSamplingGroups(), 0.0, context())
    assert out[0]['sampling']['group'] == 'high'
    team = status['sampling']['teamPolicy']
    assert team['unknownTeamHigh'] == 1
    assert team['enemyHigh'] == 0


def test_only_the_nearest_enemies_keep_the_high_slots():
    rows = [Torpedo(100 + index, 9000 + index, 1, (0, 0, float(100 + index)))
            for index in range(25)]
    owners = dict((9000 + index, Owner(False, 1)) for index in range(25))
    telemetry, _ = policy(rows, owners)
    out, status = telemetry.torpedoes(0, TorpedoSamplingGroups(), 0.0, context())
    groups = dict((row['uiId'], row['sampling']['group']) for row in out)
    high = [index for index in range(25) if groups[100 + index] == 'high']
    assert high == list(range(20))  # the nearest 20 by horizontal distance
    team = status['sampling']['teamPolicy']
    assert team['enemyHigh'] == 20
    assert team['enemyLow'] == 5
    assert team['enemyHighLimit'] == 20


def test_new_near_enemy_joins_the_budget_between_classifications():
    first = Torpedo(1, 400, 1, (0, 0, 100.0))
    new_near = Torpedo(2, 401, 1, (0, 0, 120.0))
    new_far = Torpedo(3, 402, 1, (0, 0, 2000.0))
    telemetry, battle = policy([first], {400: Owner(False, 1)})
    sampler = TorpedoSamplingGroups()
    telemetry.torpedoes(0, sampler, 0.0, context())

    battle.rows = [first, new_near, new_far]
    battle.owners[401] = Owner(False, 1)
    battle.owners[402] = Owner(False, 1)
    out, status = telemetry.torpedoes(0, sampler, 0.2, context())
    groups = dict((row['uiId'], row['sampling']) for row in out)
    assert groups[2]['group'] == 'high' and groups[2]['reason'] == 'new'
    assert groups[3]['group'] == 'low' and groups[3]['distanceStatus'] == 'far'
    assert status['sampling']['teamPolicy']['enemyHigh'] == 2


def test_context_loss_keeps_own_high_ally_low_and_others_high():
    own = Torpedo(1, 500, 5, (0, 0, 2000.0))
    ally = Torpedo(2, 501, 0, (0, 0, 2000.0))
    enemy = Torpedo(3, 502, 1, (0, 0, 2000.0))
    telemetry, _ = policy([own, ally, enemy],
                          {500: Owner(True, 5), 501: Owner(False, 0),
                           502: Owner(False, 1)})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx, self_ship_id=500)
    telemetry.torpedoes(0, sampler, 5.0, ctx, self_ship_id=500)

    out, status = telemetry.torpedoes(0, sampler, 5.2, None,
                                      self_ship_id=500)
    groups = dict((row['uiId'], row['sampling']['group']) for row in out)
    assert groups[1] == 'high'
    # The ally keeps its low schedule: it is not promoted, so it is not due now.
    assert 2 not in groups
    assert groups[3] == 'high'
    assert out[-1]['sampling']['reason'] == 'contextUnavailable'
    membership = dict((item['uiId'], item['group'])
                      for item in status['membership'])
    assert membership == {1: 'high', 2: 'low', 3: 'high'}
    assert status['sampling']['safetyHigh'] is True


def test_apply_settings_reanchors_without_clearing_or_all_high_burst():
    own = Torpedo(1, 600, 5, (0, 0, 2000.0))
    ally = Torpedo(2, 601, 0, (0, 0, 100.0))
    low_enemy = Torpedo(3, 602, 1, (0, 0, 2000.0))
    telemetry, _ = policy([own, ally, low_enemy],
                          {600: Owner(True, 5), 601: Owner(False, 0),
                           602: Owner(False, 1)})
    sampler = TorpedoSamplingGroups()
    ctx = context()
    telemetry.torpedoes(0, sampler, 0.0, ctx)
    telemetry.torpedoes(0, sampler, 5.0, ctx)
    before = dict((key, entry['group'])
                  for key, entry in sampler._entries.items())
    assert sorted(before.values()) == ['high', 'low', 'low']

    changed = normalize_torpedo_sampling_settings(
        {'low_interval': 0.8, 'enemy_high_budget': 5}, source='ui')
    assert sampler.apply_settings(changed, now=5.1) is True
    after = dict((key, entry['group'])
                 for key, entry in sampler._entries.items())
    assert after == before  # no stored low row became a high burst
    assert sampler.LOW_INTERVAL == 0.8
    assert sampler.enemy_high_budget == 5
    for entry in sampler._entries.values():
        interval = (sampler.HIGH_INTERVAL if entry['group'] == 'high'
                    else sampler.LOW_INTERVAL)
        assert entry['nextDue'] == 5.1 + interval
    # Re-applying the identical snapshot is a no-op.
    assert sampler.apply_settings(changed, now=5.2) is False


def test_wire_publishes_team_policy_only_for_the_production_sampler():
    row = Torpedo(1, 700, 1, (0, 0, 100.0))
    telemetry, _ = policy([row], {700: Owner(False, 1)})
    rows, status = telemetry.torpedoes(0, TorpedoSamplingGroups(), 0.0, context())
    _, wire = sampling_wire_payload(rows, status)
    assert wire['sampling']['teamPolicy']['policy'] == TORPEDO_SAMPLING_POLICY
    assert wire['sampling']['teamPolicy']['enemyHigh'] == 1

    legacy_rows, legacy_status = telemetry.torpedoes(
        0, LegacyTorpedoSamplingGroups(), 0.0, context())
    _, legacy_wire = sampling_wire_payload(legacy_rows, legacy_status)
    assert 'teamPolicy' not in legacy_wire['sampling']


# --- Main.py wiring ---------------------------------------------------------

MAIN_SOURCE = (Path(__file__).resolve().parents[1] /
               'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
                   encoding='utf-8')


def load_main_method(name, namespace):
    start = MAIN_SOURCE.index('    def ' + name + '(')
    end = MAIN_SOURCE.find('\n    def ', start + 1)
    code = textwrap.dedent(MAIN_SOURCE[start:end if end != -1 else None])
    # The module itself is Python 2; normalize only the legacy except form.
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(code, namespace)
    return namespace[name]


class _DisabledProfiler(object):
    status = 'disabled'

    def reset_battle(self):
        pass


def test_load_config_parses_and_normalizes_sampling_knobs():
    ns = {
        '_load_mod_config': lambda: {
            'collection_enabled': 'true',
            'torpedo_sampling_radius_divisor': '10',
            'torpedo_sampling_enemy_high_budget': '7'},
        '_cfg_float': lambda cfg, key, fallback: (
            float(cfg[key]) if key in cfg else fallback),
        'STATE_INTERVAL': 0.2,
        'PerformanceProfiler': _DisabledProfiler,
        'normalize_torpedo_sampling_settings':
            normalize_torpedo_sampling_settings,
    }
    collector = type('C', (), {'_performanceProfiler': None,
                               '_profilerEnabled': False})()
    load_main_method('_load_config', ns)(collector)
    settings = collector._torpedoSamplingSettings
    assert settings.radius_divisor == 10.0
    assert settings.enemy_high_budget == 7
    assert settings.source == 'config'
    assert collector._torpedoSamplingSettingsPending is True


def test_load_config_keeps_defaults_for_invalid_sampling_knobs():
    ns = {
        '_load_mod_config': lambda: {
            'collection_enabled': 'true',
            'torpedo_sampling_radius_divisor': 'oops',
            'torpedo_sampling_enemy_high_budget': '0'},
        '_cfg_float': lambda cfg, key, fallback: (
            float(cfg[key]) if key in cfg else fallback),
        'STATE_INTERVAL': 0.2,
        'PerformanceProfiler': _DisabledProfiler,
        'normalize_torpedo_sampling_settings':
            normalize_torpedo_sampling_settings,
    }
    collector = type('C', (), {'_performanceProfiler': None,
                               '_profilerEnabled': False})()
    load_main_method('_load_config', ns)(collector)
    settings = collector._torpedoSamplingSettings
    assert settings.radius_divisor == 5.0   # nonNumeric -> default
    assert settings.enemy_high_budget == 1   # clamped low


def test_queue_and_gate_apply_settings_without_clearing_state():
    ns = {'normalize_torpedo_sampling_settings':
          normalize_torpedo_sampling_settings,
          'torpedo_sampling_ui_contract': torpedo_sampling_ui_contract}
    apply_method = load_main_method(
        '_apply_pending_torpedo_sampling_settings', ns)
    queue_method = load_main_method('queue_torpedo_sampling_settings', ns)
    contract_method = load_main_method('torpedo_sampling_ui_contract', ns)
    # The method exec overwrote the module helper name; restore it so the
    # method's globals lookup resolves the imported helper as it does at runtime.
    ns['torpedo_sampling_ui_contract'] = torpedo_sampling_ui_contract

    collector = Obj()
    sampler = TorpedoSamplingGroups()
    own = Torpedo(1, 900, 5, (0, 0, 2000.0))
    telemetry, _ = policy([own], {900: Owner(True, 5)})
    telemetry.torpedoes(0, sampler, 0.0, context())
    collector._torpedoSamplingGroups = sampler
    collector._torpedoSamplingSettings = sampler._settings
    collector._torpedoSamplingRevision = 0
    collector._torpedoSamplingSettingsPending = False

    assert queue_method(collector, {'radius_divisor': 8,
                                    'enemy_high_budget': 3}) is True
    assert collector._torpedoSamplingSettingsPending is True
    before = dict((key, entry['group'])
                  for key, entry in sampler._entries.items())
    apply_method(collector, 1.0)
    assert collector._torpedoSamplingSettingsPending is False
    assert sampler.radius_divisor == 8.0
    assert sampler.enemy_high_budget == 3
    assert dict((key, entry['group'])
                for key, entry in sampler._entries.items()) == before

    contract = contract_method(collector)
    assert [field['key'] for field in contract['fields']] == list(
        SAMPLING_UI_SETTING_KEYS)
    assert contract['source'] == 'ui'


def test_tick_gate_applies_pending_settings_before_building_state():
    ns = {'_now': lambda: 1.0,
          '_get': lambda obj, key, default=None: getattr(obj, key, default),
          '_str': str, 'logError': lambda message: None}
    tick = load_main_method('_tick', ns)
    apply_fn = load_main_method(
        '_apply_pending_torpedo_sampling_settings',
        {'normalize_torpedo_sampling_settings':
         normalize_torpedo_sampling_settings})

    applied = []
    collector = Obj(
        _active=True, _collectionEnabled=True, _diagnosticsLastNow=None,
        _diagnostics_due=lambda now: False,
        _torpedo_depth_sampling_due=lambda now: False,
        _torpedo_state_sampling_due=lambda now: False,
        _selfSystemsSamplingEnabled=True,
        _selfSystemsSamplingDue=False,
        _self_systems_sampling_due=lambda now: False,
        _torpedoArmamentSamplingEnabled=True,
        _torpedoArmamentSamplingDue=False,
        _torpedo_armament_sampling_due=lambda now: False,
        _mapCalibrationSnapshotInterval=1.0,
        _mapCalibrationSnapshotDue=False,
        _map_calibration_snapshot_due=lambda now: False,
        _shipWorldPositionSamplingEnabled=True,
        _shipWorldPositionSamplingDue=False,
        _ship_world_position_sampling_due=lambda now: False,
        _refresh_meta=lambda now: None, _performanceProfiler=None,
        _stateInterval=0.2, _lastWrite=0.0, _diagnosticsInterval=1.0,
        _writer=None, _profilerEnabled=False,
        _torpedoSamplingSettingsPending=True,
        _torpedoSamplingSettings=TorpedoSamplingSettings(
            radius_divisor=8.0, enemy_high_budget=4))

    class Sampler(object):
        radius_divisor = 5.0
        enemy_high_budget = 20

        def apply_settings(self, settings, now):
            applied.append((settings.radius_divisor, now))
            return True

    collector._torpedoSamplingGroups = Sampler()
    collector._apply_pending_torpedo_sampling_settings = (
        lambda now: apply_fn(collector, now))

    def build(now):
        applied.append(('build', now))
        return {'active': True}

    collector._build_state = build
    collector._write_state = lambda snap: None
    tick(collector)
    assert applied == [(8.0, 1.0), ('build', 1.0)]
    assert collector._torpedoSamplingSettingsPending is False
