"""Offline checks for the read-only build resolver and the .bat wrappers.

These tests use temporary game roots only. They never read or change the real
game folder, and the wrapper checks use a fake ``py`` command so the recorder
and map server are not started.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / 'tools' / 'resolve-wows-build.ps1'
BUILD = '13533378'
WRAPPERS = (
    'install.bat',
    'restore-atm.bat',
    'record.bat',
    'launch-map.bat',
)


def _powershell():
    if os.name != 'nt':
        pytest.skip('the build resolver is a Windows PowerShell script')
    executable = shutil.which('powershell')
    if executable is None:
        pytest.skip('Windows PowerShell was not found')
    return executable


def _run_resolver(game_root, *extra):
    command = [
        _powershell(), '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', str(RESOLVER), '-GameRoot', str(game_root),
    ]
    command.extend(extra)
    result = subprocess.run(command, capture_output=True, timeout=60)
    stdout = result.stdout.decode('utf-8', errors='replace').strip()
    stderr = result.stderr.decode('utf-8', errors='replace').strip()
    return result.returncode, stdout, stderr


def _make_game(tmp_path, builds=(BUILD,), name='game (x86)'):
    game = tmp_path / name
    for build in builds:
        (game / 'bin' / build).mkdir(parents=True)
    return game


def _write_preferences(game, build):
    (game / 'preferences.xml').write_text(
        '<root><net_credentials><last_server_version>\t'
        '15,10,0,{0}\t</last_server_version></net_credentials></root>\n'
        .format(build),
        encoding='utf-8',
    )


def _write_log(game, entries):
    profile = game / 'profile'
    profile.mkdir(parents=True, exist_ok=True)
    lines = []
    for build, stamp in entries:
        lines.append(
            'WorldOfWarships64 15,10,0,{0} (compiled at 00:00:00 Jan 1 2026) '
            'starting on {1}'.format(build, stamp)
        )
    (profile / 'python.log').write_text(
        '\n'.join(lines) + '\n', encoding='utf-8')


def _make_fake_python(tmp_path):
    fake = tmp_path / 'fake-python'
    fake.mkdir(exist_ok=True)
    (fake / 'capture.py').write_text(
        'import os, sys\n'
        'with open(os.environ["CAPTURE"], "w", encoding="utf-8") as handle:\n'
        '    handle.write("\\n".join(sys.argv))\n',
        encoding='utf-8',
    )
    (fake / 'py.bat').write_text(
        '@echo off\n'
        '"{0}" "%~dp0capture.py" %*\n'.format(sys.executable),
        encoding='ascii',
    )
    return fake


def _run_bat(name, game, capture, *args):
    env = dict(os.environ)
    env.pop('WOWS_BUILD', None)
    env['WOWS_GAME_ROOT'] = str(game)
    env['CAPTURE'] = str(capture)
    env['PATH'] = str(_make_fake_python(game.parent)) + os.pathsep + env['PATH']
    result = subprocess.run(
        ['cmd', '/c', name] + list(args),
        cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=90,
    )
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    return result.returncode, output


def test_explicit_build_wins_and_is_checked(tmp_path):
    game = _make_game(tmp_path, ('11111111', '22222222'))
    _write_preferences(game, '22222222')
    _write_log(game, [('22222222', 'Fri Jan  2 00:00:00 2026')])

    code, stdout, stderr = _run_resolver(game, '-Build', '11111111')
    assert code == 0
    assert stdout == '11111111'
    assert stderr == ''


def test_explicit_build_without_bin_fails(tmp_path):
    game = _make_game(tmp_path, ('22222222',))
    code, stdout, stderr = _run_resolver(game, '-Build', '11111111')
    assert code != 0
    assert stdout == ''
    assert 'no installed bin folder' in stderr


def test_invalid_explicit_build_fails(tmp_path):
    game = _make_game(tmp_path)
    code, stdout, stderr = _run_resolver(game, '-Build', 'not-a-build')
    assert code != 0
    assert stdout == ''
    assert 'digits only' in stderr


def test_preferences_build_is_used_without_log(tmp_path):
    game = _make_game(tmp_path)
    _write_preferences(game, BUILD)

    code, stdout, stderr = _run_resolver(game)
    assert code == 0
    assert stdout == BUILD
    assert stderr == ''


def test_latest_python_log_start_is_used(tmp_path):
    game = _make_game(tmp_path, ('11111111', '22222222'))
    _write_log(game, [
        ('11111111', 'Thu Jan  1 00:00:00 2026'),
        ('22222222', 'Fri Jan  2 00:00:00 2026'),
    ])

    code, stdout, stderr = _run_resolver(game)
    assert code == 0
    assert stdout == '22222222'
    assert stderr == ''


def test_conflicting_preferences_and_log_fail(tmp_path):
    game = _make_game(tmp_path, ('11111111', '22222222'))
    _write_preferences(game, '11111111')
    _write_log(game, [('22222222', 'Fri Jan  2 00:00:00 2026')])

    code, stdout, stderr = _run_resolver(game)
    assert code != 0
    assert stdout == ''
    assert 'disagree' in stderr


def test_missing_evidence_fails(tmp_path):
    game = _make_game(tmp_path)
    code, stdout, stderr = _run_resolver(game)
    assert code != 0
    assert stdout == ''
    assert 'No launch build could be confirmed' in stderr


def test_detected_build_without_bin_fails(tmp_path):
    game = _make_game(tmp_path, ('11111111',))
    _write_preferences(game, '22222222')

    code, stdout, stderr = _run_resolver(game)
    assert code != 0
    assert stdout == ''
    assert 'no installed bin folder' in stderr


def test_resolver_reads_shared_files():
    text = RESOLVER.read_text(encoding='utf-8')
    assert 'FileShare]::ReadWrite' in text


def test_wrappers_call_the_resolver_and_quote_the_game_root():
    for name in WRAPPERS:
        text = (ROOT / name).read_text(encoding='utf-8')
        assert 'tools\\resolve-wows-build.ps1' in text, name
        assert '-GameRoot "%GAMEROOT%"' in text, name
        assert 'WOWS_GAME_ROOT' in text, name
        assert 'WOWS_BUILD' in text, name


def test_install_and_restore_forward_the_resolved_build():
    install = (ROOT / 'install.bat').read_text(encoding='utf-8')
    assert '-Build "%BUILD%" -GameRoot "%GAMEROOT%" %DRYRUN% %WITHATM%' in install
    restore = (ROOT / 'restore-atm.bat').read_text(encoding='utf-8')
    assert '-Build "%BUILD%" -GameRoot "%GAMEROOT%" %DRYRUN%' in restore


def test_launch_map_forwards_resolved_mod_dir_before_user_args(tmp_path):
    game = _make_game(tmp_path)
    _write_preferences(game, BUILD)
    capture = tmp_path / 'launch-map-args.txt'

    code, output = _run_bat('launch-map.bat', game, capture, '--help')
    assert code == 0, output
    args = capture.read_text(encoding='utf-8').splitlines()
    index = args.index('--mod-dir')
    assert args[index + 1] == str(
        game / 'bin' / BUILD / 'res_mods' / 'PnFMods' / 'WowsExtractor')
    assert '--help' in args
    assert args.index('--mod-dir') < args.index('--help')


def test_record_wrappers_use_resolved_mod_dir_and_prefix(tmp_path):
    game = _make_game(tmp_path)
    _write_preferences(game, BUILD)

    capture = tmp_path / 'record-args.txt'
    code, output = _run_bat('record.bat', game, capture)
    assert code == 0, output
    args = capture.read_text(encoding='utf-8').splitlines()
    index = args.index('--mod-dir')
    assert args[index + 1] == str(
        game / 'bin' / BUILD / 'res_mods' / 'PnFMods' / 'WowsExtractor')
    prefix = args.index('--prefix')
    assert args[prefix + 1] == 'without-atm-b'

    capture = tmp_path / 'record-with-atm-args.txt'
    code, output = _run_bat('record-with-atm.bat', game, capture)
    assert code == 0, output
    args = capture.read_text(encoding='utf-8').splitlines()
    prefix = args.index('--prefix')
    assert args[prefix + 1] == 'with-atm-b'
    assert '--with-atm' not in args