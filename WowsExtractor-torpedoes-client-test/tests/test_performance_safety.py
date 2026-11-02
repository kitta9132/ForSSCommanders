from pathlib import Path
import textwrap


SOURCE = (Path(__file__).resolve().parents[1] /
          'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf-8')


def method(name, ns):
    start = SOURCE.index('    def ' + name + '(')
    end = SOURCE.find('\n    def ', start + 1)
    code = SOURCE[start:end if end != -1 else None]
    code = code.replace('except Exception, e:', 'except Exception as e:')
    exec(textwrap.dedent(code), ns)
    return ns[name]


def test_config_is_opt_in_and_unknown_values_are_off():
    current = {}
    load = method('_load_config', {
        '_load_mod_config': lambda: current,
        '_cfg_float': lambda cfg, key, default: default, 'STATE_INTERVAL': .1})
    for config, expected in [({}, False), ({'collection_enabled': 'false'}, False),
                             ({'collection_enabled': 'yes'}, False),
                             ({'collection_enabled': 'TRUE'}, False),
                             ({'collection_enabled': 'true'}, True)]:
        c = type('C', (), {})()
        current.clear()
        current.update(config)
        load(c)
        assert c._collectionEnabled is expected
        assert c._diagnosticsEnabled is False
        assert c._diagnosticsInterval == 1.0

    c = type('C', (), {})()
    current.clear()
    current.update({'collection_enabled': 'true', 'diagnostics_enabled': 'true'})
    load(c)
    assert c._collectionEnabled is True and c._diagnosticsEnabled is True

    c = type('C', (), {})()
    ns = {'_load_mod_config': lambda: (_ for _ in ()).throw(ValueError()),
          '_cfg_float': lambda cfg, key, default: default, 'STATE_INTERVAL': .1}
    method('_load_config', ns)(c)
    assert c._collectionEnabled is False


def test_diagnostic_scheduler_samples_twice_per_two_seconds_without_catchup():
    due = method('_diagnostics_due', {})
    c = type('C', (), {'_diagnosticsEnabled': True,
        '_diagnosticsInterval': 1.0, '_diagnosticsNextDue': None,
        '_diagnosticsLastSampleTs': None, '_diagnosticsLastNow': None})()
    samples = [now for now in [i / 10.0 for i in range(20)]
               if due(c, now)]
    assert samples == [0.0, 1.0]
    # A delayed tick samples once and schedules from its actual timestamp.
    assert due(c, 5.0) is True
    assert due(c, 5.01) is False
    assert c._diagnosticsNextDue == 6.0
    # Clock rollback reopens the schedule immediately; invalid time clears history.
    assert due(c, 4.0) is True
    assert due(c, float('nan')) is False
    assert c._diagnosticsNextDue is None
    assert due(c, 4.1) is True
    c._diagnosticsEnabled = False
    assert due(c, 4.2) is False
    assert c._diagnosticsNextDue is None


def test_disabled_start_tick_double_start_and_quit_do_not_poll_game_apis():
    calls = []
    ns = {'_now': lambda: 7., 'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
          'META_RETRY_SECONDS': 12., 'logInfo': calls.append,
          '_try': lambda fn: fn(), 'callbacks': type('Callbacks', (), {
              'perTick': staticmethod(lambda fn: calls.append('schedule')),
              'cancel': staticmethod(lambda h: calls.append('cancel'))})()}
    start = method('_start_collection', ns)
    tick = method('_tick', ns)
    quit_battle = method('_on_battle_quit', ns)
    battle_start = method('_on_battle_start', ns)
    battle_shown = method('_on_battle_shown', ns)
    ammo_changed = method('_on_artillery_ammo_changed', ns)
    c = type('C', (), {})()
    c._active = False
    c._collectionEnabled = False
    c._start_collection = lambda: start(c)
    c._battleStarted = c._battleShown = False
    c._battleId = 'offline'
    c._tickHandle = None
    c._stateFile = 'state.json'
    c._ballistics = type('B', (), {'start': lambda self: calls.append('ballistics-start'),
                                   'stop': lambda self: calls.append('ballistics-stop')})()
    c._write_state = lambda state: calls.append(state)
    c._damage = type('D', (), {'snapshot': lambda self: {},
                               'clear': lambda self: None})()
    c._mapCalibration = type('M', (), {'clear': lambda self: None})()
    c._torpedoMotion = type('M', (), {'clear': lambda self: None})()
    c._stop_tick = lambda: calls.append('stop-tick')
    c._build_state = lambda now: calls.append('build-state')
    c._refresh_meta = lambda now: calls.append('meta-poll')
    c._load_config = lambda: calls.append('config-load')
    c._resolve_paths = lambda: calls.append('resolve-paths')
    c._battleIdentity = type('I', (), {'start': lambda self, *args: 'offline'})()
    c._find_arena_id = lambda: calls.append('arena-api')
    c._remember_player_vehicle = lambda *args: calls.append('player-api')
    c._remember_roster_vehicles = lambda: calls.append('roster-api')
    c._ballistics.on_ammo_changed = lambda *args: calls.append('ballistics-event-api')
    c._stateInterval = .1
    c._lastWrite = 0.
    battle_start(c)
    battle_shown(c)
    ammo_changed(c, 1)
    start(c)
    start(c)
    tick(c)
    assert sum(isinstance(x, dict) for x in calls) == 1
    disabled = next(x for x in calls if isinstance(x, dict))
    assert disabled['collection']['status'] == 'disabled'
    assert not any(x in calls for x in ('schedule', 'ballistics-start',
                                         'build-state', 'meta-poll', 'arena-api',
                                         'player-api', 'roster-api',
                                         'ballistics-event-api'))
    quit_battle(c)
    assert calls[-1]['collection']['status'] == 'disabled'
    assert 'ballistics-stop' not in calls


def test_diagnostic_calls_are_gated_but_opt_in_path_keeps_probe_payload():
    # The active snapshot path retains its established payload when diagnostics
    # are explicitly enabled; the regular offline checker exercises this path.
    assert 'diagnostic_due = diagnostic_enabled and _get(' in SOURCE
    for fn in ('safe_weapon_hub_probe', 'safe_weapon_context_probe',
               'safe_game_clock_probe', 'safe_gun_reload_probe',
               'safe_selected_torpedo_params_probe',
               'safe_torpedo_tooltip_parameter_probe', 'safe_submarine_probe',
               'safe_identity_candidates'):
        assert SOURCE.count(fn + '(') >= 1
    assert "'source': 'config.diagnostics_enabled'" in SOURCE


def test_diagnostics_off_builds_fresh_disabled_shapes_without_probe_calls():
    calls = []
    fail_if_called = lambda *args, **kwargs: calls.append('unexpected-probe')
    ns = {'_UNSET': object(), '_try': lambda fn, default=None: fn(),
          '_get': lambda obj, key, default=None: getattr(obj, key, default),
          'SCHEMA_VERSION': 1, 'WIRE_API_VERSION': '1.0',
          'dataHub': object(), 'CC': object(),
          'ui_torpedo_probe': fail_if_called, 'safe_weapon_hub_probe': fail_if_called,
          'safe_weapon_context_probe': fail_if_called, 'safe_game_clock_probe': fail_if_called,
          'safe_gun_reload_probe': fail_if_called,
          'safe_selected_torpedo_params_probe': fail_if_called,
          'safe_torpedo_tooltip_parameter_probe': fail_if_called,
           'safe_submarine_probe': fail_if_called,
           'safe_identity_candidates': fail_if_called,
           'shared_diagnostic_snapshot': fail_if_called,
          'attach_ui_state': fail_if_called}
    build = method('_build_state', ns)
    c = type('C', (), {})()
    c._active = True
    c._diagnosticsEnabled = False
    c._battleId = 'b'
    c._selfTeam = None
    c._remember_roster_vehicles = lambda: None
    c._collect_avatar_health = lambda: {}
    c._build_ships = lambda now, hp: ([], {})
    c._self_team = lambda: 1
    c._torpedoes = type('T', (), {'torpedoes': lambda self, team: ([], {'available': True}),
        'armament': lambda self: {}, 'systems': lambda self: {}})()
    c._torpedoMotion = type('T', (), {'update': lambda *args: None})()
    c._mapCalibration = type('M', (), {'world_to_map': lambda *args: None})()
    c._build_self = lambda hp: {}
    c._damage = type('D', (), {'snapshot': lambda self: {}})()
    c._ballistics = type('B', (), {'snapshot': lambda self: {}})()
    snapshot = build(c, 1.)
    assert not calls
    assert snapshot['weaponHubProbe'] == {
        'status': 'disabled', 'source': 'config.diagnostics_enabled'}
    assert snapshot['selfSubmarineProbe']['status'] == 'disabled'
    assert snapshot['identityCandidates']['status'] == 'disabled'
    c._diagnosticsEnabled = True
    c._diagnosticsSampleDue = False
    not_sampled = build(c, 2.)
    assert not_sampled['weaponHubProbe'] == {
        'status': 'notSampled', 'source': 'scheduling',
        'sampleTs': None}
    assert not_sampled['selfSubmarineProbe']['status'] == 'notSampled'
    assert not_sampled['uiTorpedoProbe']['status'] == 'notSampled'
    assert not calls
