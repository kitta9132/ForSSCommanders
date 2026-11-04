"""Ammunition performance is an initial observation, never a live refresh."""
import ast
from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace as Obj

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'res_mods/PnFMods/WowsExtractor'))
from torpedo_telemetry import TorpedoTelemetry

SOURCE = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf-8')
TREE = ast.parse(SOURCE.replace('except Exception, e:', 'except Exception as e:'))
COLLECTOR = next(n for n in TREE.body if isinstance(n, ast.ClassDef)
                 and n.name == 'Collector')


def load(name, ns):
    node = next(n for n in COLLECTOR.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<initial>', 'exec'), ns)
    return ns[name]


def attempt(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def test_initial_attempt_is_once_per_battle_and_copies_ammo_values():
    calls = Counter()
    params = {'speed': 75., 'maxDist': 9.}

    def selected(weapon):
        calls['selected'] += 1
        assert weapon == 2
        return 123

    def ammunition(ammo):
        calls['params'] += 1
        assert ammo == 123
        return params

    def ttx(*args):
        calls['ttx'] += 1
        return {'status': 'available', 'variants': {'torpedo': {'speed': 75.}}}

    ns = {'_try': attempt, 'dataHub': Obj(), 'CC': Obj(),
          'shared_diagnostic_snapshot': lambda hub: hub,
          'safe_weapon_context_probe': lambda *args: {},
          'safe_weapon_hub_probe': lambda *args: {},
          'safe_selected_torpedo_params_probe': ttx}
    c = Obj(_initialTorpedoParameters=None,
            _torpedoes=TorpedoTelemetry(Obj(getSelectedAmmoId=selected,
                getAmmoParams=ammunition), Obj(WeaponType=Obj(TORPEDO=2))))
    capture = load('_capture_initial_torpedo_parameters', ns)
    capture(c, 3.)
    initial = c._initialTorpedoParameters
    assert initial['sampleTs'] == 3.
    assert initial['policy'] == 'oncePerBattle'
    assert initial['dynamicAdjustments'] == 'externalMap'
    assert initial['ammunition']['ammoParams']['speed'] == 75.
    params['speed'] = 99.
    capture(c, 4.)
    assert c._initialTorpedoParameters is initial
    assert initial['ammunition']['ammoParams']['speed'] == 75.
    assert calls == {'selected': 1, 'params': 1, 'ttx': 1}
    json.dumps(initial, allow_nan=False)
    c._initialTorpedoParameters = None  # battle boundary
    capture(c, 10.)
    assert c._initialTorpedoParameters['sampleTs'] == 10.
    assert calls == {'selected': 2, 'params': 2, 'ttx': 2}


def test_initial_failure_is_unknown_and_does_not_start_a_polling_retry_loop():
    calls = []

    def fail(*args):
        calls.append('attempt')
        raise RuntimeError('not ready')

    ns = {'_try': attempt, 'dataHub': Obj(), 'CC': Obj(),
          'shared_diagnostic_snapshot': lambda hub: hub,
          'safe_weapon_context_probe': fail, 'safe_weapon_hub_probe': fail,
          'safe_selected_torpedo_params_probe': fail}
    c = Obj(_initialTorpedoParameters=None, _torpedoes=Obj(ammunition=fail))
    capture = load('_capture_initial_torpedo_parameters', ns)
    capture(c, 1.)
    first_calls = list(calls)
    for now in (1.2, 2., 10.):
        capture(c, now)
    assert calls == first_calls
    assert c._initialTorpedoParameters['ammunition']['ammoParamsStatus'] == 'unknown'
    assert c._initialTorpedoParameters['ttx']['status'] == 'unknown'


def test_recurring_module_samples_never_query_ammo_selection_or_performance():
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError('ammunition must not be read by armament')
    adapter = TorpedoTelemetry(Obj(getSelectedAmmoId=forbidden, getAmmoParams=forbidden),
                               Obj(WeaponType=Obj(TORPEDO=2)))
    for _ in range(5):
        modules = adapter.armament(Obj(getTorpedoesModulesState=lambda: []))
        assert modules == {'available': True, 'modulesStatus': 'available', 'modules': []}
    assert not calls
    body = ast.get_source_segment(SOURCE, next(n for n in COLLECTOR.body
        if isinstance(n, ast.FunctionDef) and n.name == '_build_state'))
    assert 'safe_selected_torpedo_params_probe(' not in body
    assert 'safe_torpedo_tooltip_parameter_probe(' not in body
    assert "'selectedTorpedoParamsProbe':" not in body
    assert "'torpedoTooltipParameterProbe':" not in body


def test_metadata_reuses_initial_sample_without_refreshing_it():
    initial = {'sampleTs': 1., 'policy': 'oncePerBattle', 'ammunition': {'ammoParams': {}}}
    ns = {'_UNSET': object(), '_coerce': lambda value: value,
          '_get': lambda obj, name, default=None: getattr(obj, name, default),
          '_now': lambda: 8., 'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
          'MOD_NAME': 'WowsExtractor', 'MOD_VERSION': 'test'}
    c = Obj(_battle_info_component=lambda: Obj(battleType=1, gameMode=2),
            _battleId='synthetic', _selfPlayerId=3, _initialTorpedoParameters=initial,
            _build_map_info=lambda info: {}, _build_roster=lambda: [])
    build = load('_build_meta', ns)
    for _ in range(3):
        meta = build(c)
        assert meta['torpedoInitialParams'] is initial
        assert meta['torpedoInitialParams']['sampleTs'] == 1.
