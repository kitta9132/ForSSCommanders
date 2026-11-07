"""Self identity candidates: observe, never infer, bounded reads."""
import math
import os
import sys
import textwrap
from collections import Counter
from pathlib import Path
from types import MethodType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
    encoding='utf-8')

sys.path.insert(0, str(ROOT / 'res_mods/PnFMods/WowsExtractor'))
from torpedo_telemetry import _identity_reject


def method(name, ns):
    """Extract one method body from Main.py and exec it in ns."""
    start = SOURCE.index('    def ' + name + '(')
    ends = [pos for marker in ('\n    def ', '\n    @staticmethod')
            if (pos := SOURCE.find(marker, start + 1)) != -1]
    end = min(ends) if ends else -1
    code = SOURCE[start:end if end != -1 else None]
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(textwrap.dedent(code), ns)
    return ns[name]


def _attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _stub_battle(observer_ship=None, observer_mode=False):
    class Battle(object):
        def getObserverShip(self):
            return observer_ship

        def isObserverMode(self):
            return observer_mode
    return Battle()


def _build_self_ns():
    return {
        '_UNSET': object(),
        '_try': _attempt,
        '_is_mapping': lambda obj: isinstance(obj, dict),
        '_vec': lambda value: list(value) if value is not None else None,
        '_identity_reject': _identity_reject,
        'apply_ui_health': lambda data, hp: None,
        'battle': _stub_battle(),
    }


def _make_collector():
    class Collector(object):
        pass
    return Collector()


def _find(candidates, namespace):
    for c in candidates:
        if c.get('namespace') == namespace:
            return c
    return None


class CountedInfo(object):
    def __init__(self, **values):
        self._values = values
        self.reads = Counter()

    def __getattr__(self, name):
        if name in self._values:
            self.reads[name] += 1
            return self._values[name]
        raise AttributeError(name)


class CountedShip(object):
    def __init__(self, position=None, **values):
        self._position = position
        self._values = values
        self.reads = Counter()

    def getPosition(self):
        self.reads['getPosition'] += 1
        return self._position

    def __getattr__(self, name):
        if name in self._values:
            self.reads[name] += 1
            return self._values[name]
        raise AttributeError(name)


def test_player_id_and_ship_id_are_observed_in_same_sample():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)
    info = CountedInfo(id=100, teamId=1, shipId=200)
    ship = CountedShip(position=(1.0, 2.0, 3.0), uiId=300,
                       vehicleId=400, _Ship__id=500, id=600,
                       health=700, maxHealth=1000, yaw=0.5)
    c = _make_collector()
    out = build_self(c, None, info, ship, health_due=False)

    assert out['playerId'] == 100
    assert out['teamId'] == 1
    pid = _find(out['identityCandidates'], 'playerId')
    assert pid['status'] == 'available'
    assert pid['raw'] == 100
    assert pid['attributeScope'] == 'public'
    assert pid['usedForIsOwn'] is False

    sid = _find(out['identityCandidates'], 'shipId')
    assert sid['status'] == 'available'
    assert sid['raw'] == 200
    assert sid['attributeScope'] == 'playerInfoCandidate'

    ui = _find(out['identityCandidates'], 'uiId')
    assert ui['status'] == 'available'
    assert ui['raw'] == 300
    assert ui['attributeScope'] == 'public'

    veh = _find(out['identityCandidates'], 'vehicleId')
    assert veh['status'] == 'available'
    assert veh['raw'] == 400
    assert veh['attributeScope'] == 'nonPublicShipAttribute'


def test_dict_self_player_info_is_supported():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)
    info = {'id': 101, 'teamId': 2, 'shipId': 201}
    ship = CountedShip(position=(0.0, 0.0, 0.0), uiId=301)
    c = _make_collector()
    out = build_self(c, None, info, ship, health_due=False)

    assert out['playerId'] == 101
    assert out['teamId'] == 2
    assert _find(out['identityCandidates'], 'playerId')['raw'] == 101
    assert _find(out['identityCandidates'], 'shipId')['raw'] == 201


def test_observer_fallback_is_not_recorded_as_self_candidate():
    ns = _build_self_ns()
    ns['battle'] = _stub_battle(observer_ship=CountedShip(
        position=(9.0, 9.0, 9.0), uiId=999, vehicleId=888))
    build_self = method('_build_self', ns)
    info = None
    c = _make_collector()
    out = build_self(c, None, None, None, health_due=False)

    assert out['position'] == [9.0, 9.0, 9.0]
    ui = _find(out['identityCandidates'], 'uiId')
    assert ui['status'] == 'none'
    assert ui.get('raw') is None
    veh = _find(out['identityCandidates'], 'vehicleId')
    assert veh['status'] == 'none'


def test_bool_nonfinite_and_unsupported_types_are_rejected():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)
    info = CountedInfo(id=True, shipId=float('nan'))
    ship = CountedShip(position=(0.0, 0.0, 0.0), uiId=0,
                       vehicleId={'not': 'scalar'},
                       _Ship__id=['list-id'], id=None)
    c = _make_collector()
    out = build_self(c, None, info, ship, health_due=False)

    assert _find(out['identityCandidates'], 'playerId')['status'] == \
        'strictTypeRejected'
    assert _find(out['identityCandidates'], 'shipId')['status'] == 'nonFinite'
    assert _find(out['identityCandidates'], 'uiId')['status'] == 'available'
    assert _find(out['identityCandidates'], 'uiId')['raw'] == 0
    assert _find(out['identityCandidates'], 'vehicleId')['status'] == \
        'strictTypeRejected'
    assert _find(out['identityCandidates'], '_Ship__id')['status'] == \
        'strictTypeRejected'
    assert _find(out['identityCandidates'], 'id')['status'] == 'none'


def test_missing_none_and_read_error_fields_are_distinct():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)

    class BadInfo(object):
        @property
        def id(self):
            raise RuntimeError('id unavailable')

        @property
        def teamId(self):
            return 1

    info = BadInfo()
    ship = CountedShip(position=(0.0, 0.0, 0.0))
    c = _make_collector()
    out = build_self(c, None, info, ship, health_due=False)

    assert _find(out['identityCandidates'], 'playerId')['status'] == 'readError'
    assert _find(out['identityCandidates'], 'shipId')['status'] == 'missing'
    assert _find(out['identityCandidates'], 'uiId')['status'] == 'missing'


def test_identity_candidates_are_present_even_when_health_not_due():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)
    info = CountedInfo(id=1, teamId=0)
    ship = CountedShip(position=(0.0, 0.0, 0.0))
    c = _make_collector()
    out = build_self(c, None, info, ship, health_due=False)

    assert 'identityCandidates' in out
    assert len(out['identityCandidates']) == 6


def test_candidate_read_budget_is_bounded_and_no_globals_vars_dir():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)
    info = CountedInfo(id=1, teamId=0, shipId=10)
    ship = CountedShip(position=(0.0, 0.0, 0.0), uiId=2, vehicleId=3,
                       _Ship__id=4, id=5)
    c = _make_collector()
    build_self(c, None, info, ship, health_due=False)

    # info.id, teamId, shipId = 3 reads; ship uiId + 3 non-public attrs = 4.
    assert sum(info.reads.values()) == 3
    assert ship.reads['getPosition'] == 1
    assert sum(ship.reads.values()) == 5  # 4 attr + getPosition

    source = textwrap.dedent(SOURCE)

    def _used_outside_comment(src, token):
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith('#'):
                continue
            if token in line:
                return True
        return False

    assert not _used_outside_comment(source, 'globals(')
    assert not _used_outside_comment(source, 'vars(')
    assert not _used_outside_comment(source, 'dir(')


def test_candidate_never_sets_is_own_or_overrides_legacy_is_own():
    ns = _build_self_ns()
    build_self = method('_build_self', ns)
    info = CountedInfo(id=1, teamId=0, shipId=99)
    ship = CountedShip(position=(0.0, 0.0, 0.0), uiId=2, vehicleId=99)
    c = _make_collector()
    out = build_self(c, None, info, ship, health_due=False)

    for cnd in out['identityCandidates']:
        assert cnd.get('isOwnOverride') is False
        if cnd['namespace'] == 'shipId' and cnd['source'] == 'battle.getSelfPlayerInfo().shipId':
            assert cnd.get('usedForIsOwn') is True
        else:
            assert cnd.get('usedForIsOwn') is False
