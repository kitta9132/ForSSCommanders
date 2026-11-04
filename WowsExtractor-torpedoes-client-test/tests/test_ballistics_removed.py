"""The submarine collector must not retain the inherited artillery calculator."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_artillery_calculation_and_its_event_hooks_are_removed():
    source = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(
        encoding='utf-8')
    for forbidden in (
            'BallisticsTracker', '_ballistics', "'ballistics':",
            'getAmmoModifiers', 'getSelfHoopRanging', 'getAmmoImpactSpeed',
            'getBulletKrupp', 'onArtilleryAmmoChanged', 'onWeaponTypeChanged',
            'onSquadronActivated', 'onSquadronDeactivated'):
        assert forbidden not in source
    # Damage shell events are intentionally separate from the calculator.
    assert '_damage.on_shell' in source
    assert '_damage.snapshot()' in source


def test_torpedo_ammunition_and_systems_are_not_removed_with_artillery():
    source = (ROOT / 'res_mods/PnFMods/WowsExtractor/torpedo_telemetry.py').read_text(
        encoding='utf-8')
    for retained in ('getAmmoParams', 'getSelectedAmmoId', 'getTorpedoesModulesState',
                     'getConsumablesState', 'getSubmarineLocatorInfo'):
        assert retained in source


def test_live_example_does_not_advertise_removed_output():
    import json
    example = json.loads((ROOT / 'examples/state.live.json').read_text(
        encoding='utf-8'))
    assert 'ballistics' not in example
