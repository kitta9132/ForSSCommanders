"""Producer-side classification context uses a same-unit inferred map extent."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = (Path(__file__).resolve().parents[1] /
          'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE.replace('except Exception, e:', 'except Exception as e:'))


def load_context():
    collector = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
                     and n.name == 'Collector')
    method = next(n for n in collector.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_torpedo_sampling_context')
    vec = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == '_vec')
    ns = {}
    exec(compile(ast.Module(body=[vec, method], type_ignores=[]), '<context>', 'exec'), ns)
    return ns['_torpedo_sampling_context']


def diagnostics(status='available', xscale=1200, zscale=-1800, zaxis='ny'):
    return {'mapCalibration': {'status': status, 'coefficients': {
        'worldX': {'mapAxis': 'nx', 'scale': xscale},
        'worldZ': {'mapAxis': zaxis, 'scale': zscale}}}}


def test_context_uses_fitted_extents_not_raw_map_dimensions_or_km_guess():
    context = load_context()(None, {'position': [5, -30, 8], 'isObserver': False},
                             diagnostics())
    assert context == {'selfPosition': [5., -30., 8.], 'mapWidth': 1200.,
                       'mapHeight': 1800., 'source': 'calibratedMapExtents',
                       'inferred': True}


@pytest.mark.parametrize('diag', [diagnostics(status='collecting'), diagnostics(xscale=0),
    diagnostics(xscale=True), diagnostics(xscale=float('nan')),
    diagnostics(zscale=float('inf')), diagnostics(zaxis='nx'), {}])
def test_invalid_or_unavailable_calibration_disables_distance_classification(diag):
    assert load_context()(None, {'position': [0, 0, 0], 'isObserver': False}, diag) is None


@pytest.mark.parametrize('own', [None, {}, {'position': [0, 0, 0], 'isObserver': True},
    {'position': [float('nan'), 0, 0], 'isObserver': False},
    {'position': [0, 0, float('inf')], 'isObserver': False}])
def test_observer_or_unknown_self_position_does_not_use_another_ship_as_origin(own):
    assert load_context()(None, own, diagnostics()) is None


@pytest.mark.parametrize('complete,rows_count,members_count,expected', [
    (True, 1, 2, 'sampledSubset'), (False, 1, 1, 'sampledSubset'),
    (True, 1, 1, 'available')])
def test_producer_keeps_membership_and_does_not_join_ui_to_an_unverified_subset(
        complete, rows_count, members_count, expected):
    calls = []

    def attempt(fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def collect(team, sampling=None, now=None, context=None, self_ship_id=None):
        calls.append(('collect', team, sampling, now, context, self_ship_id))
        return ([{'uiId': i, 'position': [i, 0, i]} for i in range(rows_count)], {
            'available': True, 'status': 'available', 'membershipComplete': complete,
            'membership': [{'uiId': i} for i in range(members_count)],
            'sampling': {'low': {'status': 'notSampled'}}})

    def attach(rows, probe, status):
        calls.append(('join', status))

    ns = {'_UNSET': object(), '_try': attempt,
          '_get': lambda obj, name, default=None: getattr(obj, name, default),
          'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
          'battle': SimpleNamespace(getSelfPlayerInfo=lambda: None,
                                   getSelfPlayerShip=lambda: object()),
          'CC': None, 'dataHub': object(),
          'shared_diagnostic_snapshot': lambda hub: hub,
          'sampling_wire_payload': lambda rows, status: (rows, status),
          'ui_torpedo_depth_probe': lambda *args: {'rows': []},
          'attach_ui_depth_state': attach}
    collector = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
                     and n.name == 'Collector')
    method = next(n for n in collector.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_build_state')
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<producer>', 'exec'), ns)
    c = SimpleNamespace(_torpedoSamplingGroups=object(), _self_team=lambda info: 0,
        _capture_avatar_snapshot=lambda: {'entities': [], 'status': 'complete',
                                          'count': 0, 'limit': 256, 'reason': None},
        _remember_roster_vehicles=lambda entities: None,
        _collect_avatar_health=lambda entities: {},
        _build_ships=lambda *args: ([], {}),
        _build_avatar_observations=lambda *args: {'rows': []},
        _build_self=lambda *args: {'position': [0, 0, 0], 'isObserver': False},
        _torpedo_sampling_context=lambda *args: {'fixture': True},
        _torpedoes=SimpleNamespace(torpedoes=collect, armament=lambda ship: {},
                                  systems=lambda ship: {}),
        _torpedoMotion=SimpleNamespace(update=lambda *args, **kwargs:
                                      calls.append(('motion', kwargs))),
        _mapCalibration=SimpleNamespace(world_to_map=lambda *args: None),
        _damage=SimpleNamespace(snapshot=lambda: {}), _battleId='fixture', _active=True,
        _torpedoDepthSamplingEnabled=True, _torpedoDepthSamplingDue=True)
    state = ns['_build_state'](c, 8.0)
    assert calls[0][0] == 'collect'
    assert calls[0][2] is c._torpedoSamplingGroups
    assert calls[0][3:5] == (8.0, {'fixture': True})
    assert calls[0][5] is None
    assert ('join', expected) in calls
    membership = state['torpedoStatus']['membership']
    assert ('motion', {'membership': membership if complete else []}) in calls
    assert len(state['torpedoes']) == rows_count
    assert len(membership) == members_count
