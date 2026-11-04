"""Main-owned gun reload cadence, sharing, and API-budget checks."""
import builtins
import json
from pathlib import Path
import sys
import textwrap
from types import MethodType, SimpleNamespace as Obj

import test_health_sampling_cadence as health  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'res_mods/PnFMods/WowsExtractor'))
import torpedo_telemetry  # noqa: E402
from torpedo_telemetry import (  # noqa: E402
    safe_gun_reload_probe, safe_weapon_hub_probe, shared_diagnostic_snapshot)


class Hub(object):
    def __init__(self, collections):
        self.collections = collections
        self.calls = []
        self.entity_calls = []

    def getEntityCollections(self, name):
        self.calls.append(name)
        return self.collections.get(name, [])

    def getEntity(self, ident):
        self.entity_calls.append(ident)
        return {'p': {'value': ident, 'min': 0, 'max': 10}}


def _components():
    values = dict(health.CC_KEYS)
    values.update({
        'gun': 'g', 'progress': 'p', 'barrelsModifier': 'bm',
        'serialLoaderModifier': 'sm', 'reloadBar': 'rb',
        'weapon': 'weapon', 'gunBarrel': 'gb', 'weaponSlot': 'ws',
        'ammo': 'ammo', 'serialLoad': 'sl', 'selfVehicle': 'sv',
        'waveHit': 'wave', 'torpedo': 'torpedo',
    })
    return Obj(**values)


def _entity(**components):
    entity = health.CountedEntity(**components)
    return entity


def _fixture_collections():
    gun = _entity(
        g=health.Comp(id=1, state=0, index=1, type=2, position=(1, 2, 3),
                      status=0),
        p=health.Comp(value=0, min=0, max=10),
        bm=health.Comp(mode=0, barrels=[7, 8]),
        sm=health.Comp(serialLoads=[]))
    reload_bar = _entity(
        rb=health.Comp(rowsCount=2, order=1, prevOrder=0, iconName='x',
                       isOutOfBounds=False),
        weapon=health.Comp(type='gun'))
    gun_barrel = _entity(
        gb=health.Comp(id=3), p=health.Comp(value=1, min=0, max=10))
    weapon_slot = _entity(
        ws=health.Comp(id=4, type=2, state=0, active=True, selected=False,
                       shotCount=1, ammoParamsId=5, ident=6),
        p=health.Comp(value=0, max=10))
    ammo = _entity(ammo=health.Comp(id=5, hasSecondaryAmmo=False,
                                    isAutoUsage=False, squadId=0))
    serial_load = _entity(
        sl=health.Comp(index=0, weaponType=2, state=0),
        p=health.Comp(value=0, max=10))
    rows = {
        'gun': [gun], 'reloadBar': [reload_bar], 'gunBarrel': [gun_barrel],
        'weaponSlot': [weapon_slot], 'ammo': [ammo], 'serialLoad': [serial_load],
    }
    entities = {'gun': gun, 'reloadBar': reload_bar, 'gunBarrel': gun_barrel,
                'weaponSlot': weapon_slot, 'ammo': ammo,
                'serialLoad': serial_load}
    return rows, entities


def _method(name, namespace):
    source = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
        encoding='utf8')
    start = source.index('    def ' + name + '(')
    ends = [pos for marker in ('\n    def ', '\n    @staticmethod')
            if (pos := source.find(marker, start + 1)) != -1]
    end = min(ends) if ends else source.find('\n\ndef _is_mapping', start)
    code = source[start:end if end != -1 else None]
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(textwrap.dedent(code), namespace)
    return namespace[name]


def _collector(*, enabled=False, heavy=False, interval=0.2):
    ships, players, info, self_ship, avatars = health.default_fixture()
    collector, ns = health.make_collector(avatars, ships, players, info, self_ship)
    rows, entities = _fixture_collections()
    hub = Hub(dict(rows, avatar=avatars))
    shared_calls = []

    def shared(hub_arg):
        shared_calls.append(hub_arg)
        return shared_diagnostic_snapshot(hub_arg)

    ns.update({
        'dataHub': hub,
        'CC': _components(),
        'STATE_INTERVAL': 0.2,
        'shared_diagnostic_snapshot': shared,
        'safe_gun_reload_probe': safe_gun_reload_probe,
        'safe_weapon_hub_probe': safe_weapon_hub_probe,
        'safe_weapon_context_probe': lambda *args: {'status': 'available'},
        'safe_game_clock_probe': lambda *args: {'status': 'available'},
    })
    collector._gunReloadSamplingEnabled = enabled
    collector._diagnosticsEnabled = heavy
    collector._diagnosticsSampleDue = heavy
    collector._stateInterval = interval
    collector._collect_submarine_probes = MethodType(
        lambda self, *args: ({
            'selfSubmarineProbe': {'status': 'available'},
            'waveHitProbe': {'status': 'available'}}, True), collector)
    return collector, ns, hub, shared_calls, entities


def test_default_off_does_not_build_diagnostic_facade_or_call_gun_collections():
    collector, ns, hub, shared_calls, _entities = _collector()
    state = collector._build_state(4.0)

    assert state['gunReloadProbe']['status'] == 'disabled'
    assert state['gunReloadProbe']['source'] == 'config.diagnostics_enabled'
    assert shared_calls == []
    assert hub.calls == ['avatar']
    assert hub.entity_calls == []


def test_core_sampling_uses_raw_probe_and_emits_core_timestamp_and_interval():
    collector, _ns, hub, shared_calls, _entities = _collector(
        enabled=True, interval=0.4)
    state = collector._build_state(7.25)
    probe = state['gunReloadProbe']

    assert probe['status'] == 'available'
    assert probe['collections']['gun']['rows'][0]['fields']['state']['raw'] == 0
    assert probe['collections']['gun']['rows'][0]['progress']['value']['raw'] == 0
    assert probe['sampleTs'] == 7.25
    assert probe['sampling'] == {
        'status': 'sampled', 'sampleTs': 7.25,
        'intervalSeconds': 0.4, 'source': 'core'}
    assert hub.calls.count('gun') == 1
    assert hub.calls.count('reloadBar') == 1
    assert hub.calls.count('gunBarrel') == 1
    assert hub.entity_calls == []
    assert len(shared_calls) == 1
    json.dumps(state, allow_nan=False)


def test_heavy_and_core_sampling_share_one_probe_and_each_collection_read():
    collector, ns, hub, _shared_calls, entities = _collector(
        enabled=True, heavy=True)
    probe_calls = []

    def counted_probe(*args, **kwargs):
        probe_calls.append((args, kwargs))
        return safe_gun_reload_probe(*args, **kwargs)

    ns['safe_gun_reload_probe'] = counted_probe
    state = collector._build_state(9.0)

    assert len(probe_calls) == 1
    assert probe_calls[0][1] == {'resolve_references': False}
    for name in ('gun', 'reloadBar', 'gunBarrel'):
        assert hub.calls.count(name) == 1
        assert state['gunReloadProbe']['collections'][name]['status'] == 'available'
    assert hub.entity_calls == []
    assert state['gunReloadProbe']['getEntity']['status'] == 'notSampled'
    assert state['gunReloadProbe']['getEntity']['attempted'] == 0

    # Heavy weaponHub progress reads are on weaponSlot/serialLoad rows, not gun
    # rows. Reuse barrelsModifier for mode and member list within this probe.
    assert entities['gun'].reads['g'] == 1
    assert entities['gun'].reads['p'] == 1
    assert entities['gun'].reads['bm'] == 1
    assert entities['gun'].reads['sm'] == 1
    assert entities['reloadBar'].reads['rb'] == 1
    assert entities['reloadBar'].reads['weapon'] == 1
    assert entities['gunBarrel'].reads['gb'] == 1
    assert entities['gunBarrel'].reads['p'] == 1
    assert entities['weaponSlot'].reads['ws'] == 1
    assert entities['weaponSlot'].reads['p'] == 1
    assert entities['ammo'].reads['ammo'] == 1
    assert entities['serialLoad'].reads['sl'] == 1
    assert entities['serialLoad'].reads['p'] == 1
    assert state['gunReloadProbe']['sampling']['source'] == 'core'


def test_heavy_only_keeps_modifier_reference_resolution():
    collector, ns, hub, _shared_calls, _entities = _collector(heavy=True)
    full_calls = []

    def counted_probe(*args, **kwargs):
        full_calls.append((args, kwargs))
        return safe_gun_reload_probe(*args, **kwargs)

    ns['safe_gun_reload_probe'] = counted_probe
    state = collector._build_state(10.0)

    assert len(full_calls) == 1
    assert full_calls[0][1] == {}
    assert state['gunReloadProbe']['getEntity']['attempted'] == 2
    assert hub.entity_calls == [7, 8]
    assert 'sampling' not in state['gunReloadProbe']


def test_probe_failure_stays_unknown_with_sampling_metadata_and_state_survives():
    collector, ns, _hub, _shared_calls, _entities = _collector(enabled=True)

    def fail_probe(*args, **kwargs):
        raise RuntimeError('probe failure')

    ns['safe_gun_reload_probe'] = fail_probe
    state = collector._build_state(12.5)

    assert state['gunReloadProbe']['status'] == 'unknown'
    assert state['gunReloadProbe']['error'] == 'probeFailed'
    assert state['gunReloadProbe']['sampleTs'] == 12.5
    assert state['gunReloadProbe']['sampling'] == {
        'status': 'sampled', 'sampleTs': 12.5,
        'intervalSeconds': 0.2, 'source': 'core'}
    assert isinstance(state['ships'], list)
    assert state['torpedoStatus']['status'] == 'available'


def test_each_core_state_is_a_fresh_probe_not_a_copied_prior_row():
    collector, _ns, hub, _shared_calls, _entities = _collector(enabled=True)
    first = collector._build_state(1.0)['gunReloadProbe']
    second = collector._build_state(1.4)['gunReloadProbe']

    assert first['sampleTs'] == 1.0
    assert second['sampleTs'] == 1.4
    assert first['sampling']['intervalSeconds'] == 0.2
    assert second['collections']['gun']['rows'][0] is not \
        first['collections']['gun']['rows'][0]
    assert hub.calls.count('gun') == 2
    assert hub.calls.count('reloadBar') == 2
    assert hub.calls.count('gunBarrel') == 2


def test_config_option_defaults_off_and_requires_collection_opt_in():
    values = {'collection_enabled': 'false',
              'gun_reload_sampling_enabled': 'true'}

    class Profiler(object):
        PHASES = ('state_cycle_total',)

        def __init__(self, *args):
            self.PHASES = type(self).PHASES

    ns = {
        '_load_mod_config': lambda: dict(values),
        '_cfg_float': lambda cfg, key, default: float(cfg.get(key, default)),
        'STATE_INTERVAL': 0.2,
        'PerformanceProfiler': Profiler,
    }
    load_config = _method('_load_config', ns)
    collector = Obj(_performanceProfiler=None, _profilerEnabled=False)
    MethodType(load_config, collector)()
    assert collector._gunReloadSamplingEnabled is False

    values.update(collection_enabled='true', gun_reload_sampling_enabled='true')
    MethodType(load_config, collector)()
    assert collector._gunReloadSamplingEnabled is True

    values.pop('gun_reload_sampling_enabled')
    MethodType(load_config, collector)()
    assert collector._gunReloadSamplingEnabled is False

    config_text = (ROOT / 'res_mods/PnFMods/WowsExtractor/config.example.ini').read_text(
        encoding='utf8')
    assert 'gun_reload_sampling_enabled = false' in config_text


def test_profiler_registers_and_records_independent_sampling_phases(monkeypatch):
    import performance_profiler
    from test_performance_profiler import Clock, install_clock
    install_clock(monkeypatch, Clock())
    values = {'collection_enabled': 'true', 'profiler_enabled': 'true',
              'gun_reload_sampling_enabled': 'true'}

    ns = {
        '_load_mod_config': lambda: dict(values),
        '_cfg_float': lambda cfg, key, default: float(cfg.get(key, default)),
        'STATE_INTERVAL': 0.2,
        'PerformanceProfiler': performance_profiler.PerformanceProfiler,
    }
    load_config = _method('_load_config', ns)
    collector = Obj(_performanceProfiler=None, _profilerEnabled=False)
    MethodType(load_config, collector)()
    assert 'gun_sampling' in collector._performanceProfiler.PHASES
    profiler = collector._performanceProfiler
    for phase in ('gun_sampling', 'submarine_sampling'):
        token = profiler.begin(phase)
        assert token is not None
        profiler.finish(token)
        assert profiler._stats[phase]['count'] == 1


def test_profiler_separates_core_gun_phase_but_counts_heavy_tick_in_diagnostics():
    class Profiler(object):
        status = 'available'
        PHASES = ('avatar', 'self', 'ships', 'torpedoes',
                  'armament_systems', 'diagnostics_due', 'gun_sampling')

        def __init__(self):
            self.measured = []
            self.begun = []

        def begin(self, phase):
            assert phase in self.PHASES
            self.begun.append(phase)
            return phase

        def finish(self, token, completed=True):
            return None

        def measure(self, phase, function, *args):
            assert phase in self.PHASES
            self.measured.append(phase)
            return function(*args)

    core, _ns, _hub, _shared, _entities = _collector(enabled=True)
    core_profiler = Profiler()
    core._performanceProfiler = core_profiler
    core._build_state(14.0)
    assert 'gun_sampling' in core_profiler.measured
    assert 'diagnostics_due' not in core_profiler.begun

    heavy, _ns, _hub, _shared, _entities = _collector(enabled=True, heavy=True)
    heavy_profiler = Profiler()
    heavy._performanceProfiler = heavy_profiler
    heavy._build_state(15.0)
    assert 'diagnostics_due' in heavy_profiler.begun
    assert 'gun_sampling' not in heavy_profiler.measured


def test_limited_builtins_probe_uses_reexecuted_module_namespace():
    rows, _entities = _fixture_collections()
    hub = Hub(rows)
    restricted = dict(vars(builtins))
    for name in ('iter', 'next', 'enumerate', 'AttributeError', 'TypeError'):
        restricted.pop(name, None)
    namespace = {'__builtins__': restricted, '__name__': 'restricted_gun_probe'}
    source = Path(torpedo_telemetry.__file__).read_text(encoding='utf-8-sig')
    exec(compile(source, torpedo_telemetry.__file__, 'exec'), namespace)
    probe = namespace['safe_gun_reload_probe']

    result = probe(hub, _components(), resolve_references=False)
    assert 'enumerate' not in probe.__builtins__
    assert result['status'] == 'available'
    assert result['collections']['gun']['rows'][0]['fields']['state']['raw'] == 0
    assert result['getEntity']['status'] == 'notSampled'
    assert result['getEntity']['attempted'] == 0
    assert hub.entity_calls == []
    json.dumps(result, allow_nan=False)
