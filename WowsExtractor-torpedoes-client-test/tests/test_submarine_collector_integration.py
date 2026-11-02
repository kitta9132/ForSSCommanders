from pathlib import Path
import subprocess
import sys
import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    'Main.py', 'battle_identity.py', 'damage_tracker.py', 'emit_guard.py',
    'ui_health.py', 'torpedo_telemetry.py', 'submarine_telemetry.py',
    'map_calibration.py',
)


def test_installer_and_offline_checker_require_all_collector_modules():
    installer = (ROOT / 'install-wowsmod.ps1').read_text(encoding='utf-8')
    checker = (ROOT / 'tools/check_collector_offline.py').read_text(encoding='utf-8')
    for module in MODULES:
        assert "'" + module + "'" in installer
        assert "'" + module + "'" in checker


def test_collector_offline_smoke_includes_safe_submarine_probe_failure():
    if not (3, 10) <= sys.version_info[:2] <= (3, 12):
        pytest.skip('offline lib2to3 collector checker supports Python 3.10-3.12')
    result = subprocess.run(
        [sys.executable, str(ROOT / 'tools/check_collector_offline.py')],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'submarine_telemetry.py' in result.stdout
    assert 'Collector live state' in result.stdout


def test_main_versions_and_emits_both_probe_keys():
    main = (ROOT / 'res_mods/PnFMods/WowsExtractor/Main.py').read_text(encoding='utf-8')
    assert "MOD_VERSION = '0.3.18-core-avatar-reuse'" in main
    assert 'safe_submarine_probe(diagnostic_hub, CC, now)' in main
    assert "'selfSubmarineProbe': submarine_probes['selfSubmarineProbe']" in main
    assert "'waveHitProbe': submarine_probes['waveHitProbe']" in main
