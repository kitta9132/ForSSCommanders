"""Offline checks for install-wowsmod.ps1 and the auto-detecting wrapper.

The tests never touch the real game folder. Each PowerShell run uses a
synthetic package and a fake game root under pytest's temporary directory.
Only read-only dry-runs are mandatory; the two actual-install checks skip
when a WoWS process is present so a developer's running client is untouched.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'install-wowsmod.ps1'
WRAPPER = ROOT / 'install.bat'
BUILD = '13357625'

# Keep this in sync with $script:PythonFiles in install-wowsmod.ps1.
MODULE_NAMES = (
    'Main.py',
    'battle_identity.py',
    'damage_tracker.py',
    'emit_guard.py',
    'ui_health.py',
    'torpedo_telemetry.py',
    'submarine_telemetry.py',
    'map_calibration.py',
    'performance_profiler.py',
    'ttaro_prefs_adapter.py',
    'ttaro_prefs_binding.py',
)
COPY_FILES = MODULE_NAMES + ('config.example.ini',)
# Keep this in sync with $script:SchemaFiles in install-wowsmod.ps1.
SCHEMA_NAMES = ('kitta-wows-extractor.schema.json',)
SCHEMA_RELATIVE = tuple(
    'res_mods/ModSchemas/' + name for name in SCHEMA_NAMES)
RELATIVE_FILES = tuple(
    'res_mods/PnFMods/WowsExtractor/' + name for name in COPY_FILES
) + SCHEMA_RELATIVE + ('res_mods/PnFModsLoader.py',)
ATM_RELATIVE = (
    r'PnFMods\AdvancedTorpedoMarkerPy',
    r'gui\unbound2\PnFMods\AdvancedTorpedoMarker.unbound',
    r'gui\unbound2\PnFMods\AdvancedTorpedoMarkerMinimapFix.unbound',
)


def _powershell():
    if os.name != 'nt':
        pytest.skip('PowerShell installer checks require Windows')
    executable = shutil.which('powershell')
    if executable is None:
        pytest.skip('Windows PowerShell was not found')
    return executable


def _game_is_running():
    try:
        result = subprocess.run(
            ['tasklist', '/FO', 'CSV', '/NH'],
            capture_output=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    names = (b'worldofwarships.exe', b'worldofwarships64.exe',
             b'wowslauncher.exe')
    text = result.stdout.lower()
    return any(name in text for name in names)


def _skip_if_game_running():
    if _game_is_running():
        pytest.skip('a WoWS process is running; installer checks must not stop it')


def _make_package(tmp_path):
    package = tmp_path / 'package'
    mod = package / 'res_mods' / 'PnFMods' / 'WowsExtractor'
    mod.mkdir(parents=True)
    for name in MODULE_NAMES:
        (mod / name).write_bytes(('# fixture ' + name + '\n').encode('utf-8'))
    (mod / 'config.example.ini').write_bytes(b'collection_enabled = false\n')
    schemas = package / 'res_mods' / 'ModSchemas'
    schemas.mkdir(parents=True)
    for name in SCHEMA_NAMES:
        (schemas / name).write_bytes(
            ('# fixture schema ' + name + '\n').encode('utf-8'))
    (package / 'res_mods' / 'PnFModsLoader.py').write_bytes(b'')
    shutil.copy2(INSTALLER, package / 'install-wowsmod.ps1')

    lines = []
    for relative in RELATIVE_FILES:
        data = (package / relative).read_bytes()
        lines.append(hashlib.sha256(data).hexdigest() + '  ' + relative)
    (package / 'SHA256SUMS.txt').write_bytes(
        ('\n'.join(lines) + '\n').encode('ascii'))
    return package


def _make_game(tmp_path):
    game = tmp_path / 'game'
    (game / 'bin' / BUILD / 'res_mods').mkdir(parents=True)
    return game


def _res_mods(game):
    return game / 'bin' / BUILD / 'res_mods'


def _add_atm_and_shared_files(game):
    res_mods = _res_mods(game)
    atm_body = res_mods / 'PnFMods' / 'AdvancedTorpedoMarkerPy'
    atm_body.mkdir(parents=True)
    (atm_body / 'Main.pyc').write_bytes(b'atm-body')
    atm_ui = res_mods / 'gui' / 'unbound2' / 'PnFMods'
    atm_ui.mkdir(parents=True)
    (atm_ui / 'AdvancedTorpedoMarker.unbound').write_bytes(b'atm-ui')
    (atm_ui / 'AdvancedTorpedoMarkerMinimapFix.unbound').write_bytes(
        b'atm-minimap')

    shared = res_mods / 'PnFMods' / 'TTaroModUtils'
    shared.mkdir(parents=True)
    (shared / 'shared.py').write_bytes(b'shared-dependency')
    (res_mods / 'PnFModsLoader.py').write_bytes(b'existing-loader')


def _read_atm_item(path):
    if path.is_file():
        return ('file', path.read_bytes())
    if path.is_dir():
        return ('dir', {
            item.relative_to(path).as_posix(): item.read_bytes()
            for item in sorted(path.rglob('*')) if item.is_file()
        })
    return None


def _atm_snapshot(game):
    result = {}
    for relative in ATM_RELATIVE:
        result[relative] = _read_atm_item(_res_mods(game) / relative)
    return result


def _run_powershell(package, game, *extra):
    _skip_if_game_running()
    command = [
        _powershell(), '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(package / 'install-wowsmod.ps1'),
        '-Build', BUILD, '-GameRoot', str(game),
    ]
    command.extend(extra)
    try:
        result = subprocess.run(
            command, capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        pytest.skip('could not run Windows PowerShell: {0}'.format(error))
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    return result.returncode, output


def _backup_root(game):
    return _res_mods(game) / '_wowsmod_backups'


def _source_text():
    return INSTALLER.read_text(encoding='utf-8')


def _function_body(text, name):
    start = text.index('function ' + name)
    following = text.find('\nfunction ', start + 1)
    return text[start:] if following == -1 else text[start:following]


def test_default_atm_disable_is_preserved_and_withatm_is_explicit():
    text = _source_text()
    assert "[Alias('KeepAtm')]" in text
    assert '[switch]$WithAtm' in text
    assert '$atmDetected = $atmItemsNow.Count -gt 0' in text
    assert 'if ($WithAtm) {' in text
    assert '} elseif ($atmDetected) {' in text
    # There is exactly one actual Disable-Atm call, in the default branch.
    assert text.count('Disable-Atm -Items') == 1
    assert 'restore-atm.bat (after the no-ATM test)' in text


def test_elevation_reexec_passes_build_gameroot_and_withatm():
    body = _function_body(_source_text(), 'Invoke-ElevatedSelf')
    assert "' -Build '" in body
    assert "' -GameRoot '" in body
    assert 'if ($WithAtm) {' in body
    assert "' -WithAtm'" in body
    assert "' -Elevated'" in body


def test_rollback_only_restores_atm_the_installer_moved():
    text = _source_text()
    assert '$script:AtmManifestPath = $null' in text
    assert '$script:AtmManifestPath = $manifestPath' in text
    assert "Restore-AtmFromManifest -ManifestPath $script:AtmManifestPath" in text
    # The -WithAtm branch must not populate the rollback manifest at all.
    withatm_branch = text[text.index('if ($WithAtm) {', text.index(
        '$atmDetected =')):text.index('} elseif ($atmDetected) {')]
    assert 'Disable-Atm' not in withatm_branch
    assert 'AtmManifestPath' not in withatm_branch


def test_wrapper_exposes_withatm_without_changing_default_flag():
    text = WRAPPER.read_text(encoding='utf-8')
    assert '--with-atm' in text
    assert 'set "WITHATM=-WithAtm"' in text
    assert '%DRYRUN% %WITHATM%' in text
    assert 'ATM mode: disable' in text


def test_powershell_ast_parses_installer():
    _powershell()
    script = (
        "$tokens=$null;$errors=$null;"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile("
        "$env:INSTALLER_PATH,[ref]$tokens,[ref]$errors);"
        "if($errors.Count -gt 0){"
        "$errors | ForEach-Object { Write-Error $_.Message }; exit 1 };"
        "exit 0"
    )
    environment = dict(os.environ)
    environment['INSTALLER_PATH'] = str(INSTALLER)
    result = subprocess.run(
        [_powershell(), '-NoProfile', '-Command', script],
        capture_output=True, timeout=60, env=environment,
    )
    assert result.returncode == 0, result.stderr.decode(
        'utf-8', errors='replace')


def test_dryrun_default_without_atm_keeps_standard_message(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    code, output = _run_powershell(package, game, '-DryRun')
    assert code == 0, output
    assert 'ATM mode       : disable (default)' in output
    assert 'ATM disable    : no ATM load files detected - nothing to move' in output
    assert 'ATM disable    : yes' not in output
    assert not _backup_root(game).exists()


def test_dryrun_default_with_atm_plans_the_existing_move(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    _add_atm_and_shared_files(game)
    before = _atm_snapshot(game)
    code, output = _run_powershell(package, game, '-DryRun')
    assert code == 0, output
    assert 'ATM mode       : disable (default)' in output
    assert 'ATM disable    : yes' in output
    for relative in ATM_RELATIVE:
        assert relative in output
    assert 'restore-atm.bat (after the no-ATM test)' in output
    assert _atm_snapshot(game) == before
    assert not _backup_root(game).exists()


def test_dryrun_withatm_with_atm_keeps_all_load_files(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    _add_atm_and_shared_files(game)
    before = _atm_snapshot(game)
    code, output = _run_powershell(package, game, '-DryRun', '-WithAtm')
    assert code == 0, output
    assert 'ATM mode       : keep (explicit -WithAtm)' in output
    assert 'would stay in place' in output
    assert 'would be moved' not in output
    assert 'ATM restore    : not needed for this install' in output
    for relative in ATM_RELATIVE:
        assert relative in output
    assert _atm_snapshot(game) == before
    assert not _backup_root(game).exists()


def test_dryrun_withatm_without_atm_is_equivalent_to_no_atm(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    code, output = _run_powershell(package, game, '-DryRun', '-WithAtm')
    assert code == 0, output
    assert 'ATM mode       : keep (explicit -WithAtm)' in output
    assert 'no ATM load files detected - nothing would be moved or kept' in output
    assert 'ATM disable    : yes' not in output
    assert not _backup_root(game).exists()


def test_keepatm_alias_selects_the_same_keep_mode(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    _add_atm_and_shared_files(game)
    before = _atm_snapshot(game)
    code, output = _run_powershell(package, game, '-DryRun', '-KeepAtm')
    assert code == 0, output
    assert 'ATM mode       : keep (explicit -WithAtm)' in output
    assert _atm_snapshot(game) == before
    assert not _backup_root(game).exists()


def test_actual_withatm_install_leaves_atm_and_shared_files_untouched(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    _add_atm_and_shared_files(game)
    atm_before = _atm_snapshot(game)
    loader_before = (_res_mods(game) / 'PnFModsLoader.py').read_bytes()
    shared_before = (
        _res_mods(game) / 'PnFMods' / 'TTaroModUtils' / 'shared.py'
    ).read_bytes()

    code, output = _run_powershell(package, game, '-WithAtm')
    assert code == 0, output
    assert 'Installation completed successfully.' in output
    assert 'ATM           : kept - explicit -WithAtm' in output
    assert 'ATM note      : ATM presence is not proof of a state producer' in output
    assert _atm_snapshot(game) == atm_before
    assert (_res_mods(game) / 'PnFModsLoader.py').read_bytes() == loader_before
    assert (_res_mods(game) / 'PnFMods' / 'TTaroModUtils' /
            'shared.py').read_bytes() == shared_before
    installed = _res_mods(game) / 'PnFMods' / 'WowsExtractor'
    assert (installed / 'Main.py').read_bytes() == (
        package / 'res_mods' / 'PnFMods' / 'WowsExtractor' / 'Main.py'
    ).read_bytes()
    assert not list(_backup_root(game).glob('ATM_disabled_*'))


def test_actual_default_install_still_disables_and_records_atm(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    _add_atm_and_shared_files(game)
    upstream_before = _atm_snapshot(game)

    code, output = _run_powershell(package, game)
    assert code == 0, output
    assert 'Installation completed successfully.' in output
    assert 'ATM           : disabled' in output

    for relative in ATM_RELATIVE:
        assert not (_res_mods(game) / relative).exists()
    backups = list(_backup_root(game).glob('ATM_disabled_*'))
    assert len(backups) == 1
    manifest = backups[0] / 'atm-disable-manifest.json'
    assert manifest.is_file()
    manifest_data = json.loads(manifest.read_text(encoding='utf-8-sig'))
    assert manifest_data['status'] == 'disabled'
    assert {item['relativePath'] for item in manifest_data['items']} == set(ATM_RELATIVE)
    for relative, content in upstream_before.items():
        assert _read_atm_item(backups[0] / relative) == content

    # Shared dependencies are not part of the ATM allow-list.
    assert (_res_mods(game) / 'PnFModsLoader.py').read_bytes() == b'existing-loader'
    assert (_res_mods(game) / 'PnFMods' / 'TTaroModUtils' /
            'shared.py').read_bytes() == b'shared-dependency'


def _make_gui_only_atm_and_failing_target(game):
    """Create ATM gui files, then block target creation with a PnFMods file."""
    res_mods = _res_mods(game)
    gui = res_mods / 'gui' / 'unbound2' / 'PnFMods'
    gui.mkdir(parents=True)
    (gui / 'AdvancedTorpedoMarker.unbound').write_bytes(b'atm-ui')
    (gui / 'AdvancedTorpedoMarkerMinimapFix.unbound').write_bytes(b'atm-minimap')
    # The installer must create res_mods/PnFMods/WowsExtractor. A file at
    # res_mods/PnFMods forces a deterministic post-ATM-check failure without
    # touching the real game folder.
    (res_mods / 'PnFMods').write_bytes(b'blocked-parent')
    return {
        r'gui\unbound2\PnFMods\AdvancedTorpedoMarker.unbound': b'atm-ui',
        r'gui\unbound2\PnFMods\AdvancedTorpedoMarkerMinimapFix.unbound':
            b'atm-minimap',
    }


def test_withatm_failure_rollback_does_not_move_preserved_atm(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    expected = _make_gui_only_atm_and_failing_target(game)

    code, output = _run_powershell(package, game, '-WithAtm')
    assert code == 5, output
    assert 'Installation failed.' in output
    assert 'Installation completed successfully.' not in output
    for relative, content in expected.items():
        assert (_res_mods(game) / relative).read_bytes() == content
    assert not _backup_root(game).exists()


def test_default_failure_rollback_still_restores_the_atm_it_moved(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    expected = _make_gui_only_atm_and_failing_target(game)

    code, output = _run_powershell(package, game)
    assert code == 5, output
    assert 'Installation failed.' in output
    assert 'Installation completed successfully.' not in output
    for relative, content in expected.items():
        assert (_res_mods(game) / relative).read_bytes() == content

    backups = list(_backup_root(game).glob('ATM_disabled_*'))
    assert len(backups) == 1
    manifest_data = json.loads(
        (backups[0] / 'atm-disable-manifest.json').read_text(
            encoding='utf-8-sig'))
    assert manifest_data['status'] == 'restored'


def _package_schema_bytes(package):
    return (package / 'res_mods' / 'ModSchemas' /
            SCHEMA_NAMES[0]).read_bytes()


def _target_schema(game):
    return _res_mods(game) / 'ModSchemas' / SCHEMA_NAMES[0]


def test_installer_allow_lists_the_adapter_binding_and_schema():
    text = _source_text()
    assert 'ttaro_prefs_adapter.py' in text
    assert 'ttaro_prefs_binding.py' in text
    assert "$script:SchemaFiles = @('kitta-wows-extractor.schema.json')" in text
    assert "res_mods\\ModSchemas" in text


def test_dryrun_reports_schema_placement_and_keeps_other_schemas(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    schemas = _res_mods(game) / 'ModSchemas'
    schemas.mkdir(parents=True)
    (schemas / 'framework-owned.schema.json').write_bytes(b'framework')

    code, output = _run_powershell(package, game, '-DryRun')
    assert code == 0, output
    assert 'ModSchemas     : not present' in output
    assert 'other schemas stay untouched' in output
    assert (schemas / 'framework-owned.schema.json').read_bytes() == b'framework'
    assert not _backup_root(game).exists()


def test_actual_install_places_schema_and_keeps_other_schemas(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    schemas = _res_mods(game) / 'ModSchemas'
    schemas.mkdir(parents=True)
    (schemas / 'framework-owned.schema.json').write_bytes(b'framework')
    other_before = (schemas / 'framework-owned.schema.json').read_bytes()

    code, output = _run_powershell(package, game)
    assert code == 0, output
    assert 'Installation completed successfully.' in output
    assert 'ModSchemas    : kitta-wows-extractor.schema.json installed' in output
    assert _target_schema(game).read_bytes() == _package_schema_bytes(package)
    # Framework-owned and other schemas are never touched.
    assert (schemas / 'framework-owned.schema.json').read_bytes() == other_before
    assert not list(_backup_root(game).glob('ModSchemas_*'))
    installed = _res_mods(game) / 'PnFMods' / 'WowsExtractor'
    for name in ('ttaro_prefs_adapter.py', 'ttaro_prefs_binding.py'):
        assert (installed / name).is_file()


def test_actual_install_backs_up_and_replaces_our_existing_schema(tmp_path):
    package = _make_package(tmp_path)
    game = _make_game(tmp_path)
    schemas = _res_mods(game) / 'ModSchemas'
    schemas.mkdir(parents=True)
    (schemas / SCHEMA_NAMES[0]).write_bytes(b'previous-own-schema')
    (schemas / 'another-mod.schema.json').write_bytes(b'another')

    code, output = _run_powershell(package, game)
    assert code == 0, output
    assert 'Installation completed successfully.' in output
    assert _target_schema(game).read_bytes() == _package_schema_bytes(package)
    assert (schemas / 'another-mod.schema.json').read_bytes() == b'another'
    backups = list(_backup_root(game).glob('ModSchemas_*'))
    assert len(backups) == 1
    assert (backups[0] / SCHEMA_NAMES[0]).read_bytes() == b'previous-own-schema'
