#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate an index, complete source listing, hashes and a ZIP; stdlib only.

Use --verify to check the existing hashes without changing package files.
"""
import argparse
import hashlib
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'FILES.md', 'ALL_SOURCE.txt', 'SHA256SUMS.txt'}


def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
                  and not any(part.startswith('.') or part == '__pycache__'
                              for part in p.relative_to(ROOT).parts)
                  and p.relative_to(ROOT).parts[0] != 'recordings'
                  and p.suffix not in ('.pyc', '.pyo', '.zip'))


def verify():
    count = 0
    expected = set()
    for line in (ROOT / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        digest, name = line.split('  ', 1)
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe manifest path: ' + name)
        path = ROOT / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('checksum mismatch: ' + name)
        expected.add(name)
        count += 1
    actual = {p.relative_to(ROOT).as_posix() for p in files()
              if p.name != 'SHA256SUMS.txt'}
    if actual != expected:
        raise ValueError('manifest file list differs from package contents')
    print('Checksums OK:', count, 'files (manifest itself excluded)')


def build(output):
    if output.resolve().is_relative_to(ROOT):
        raise ValueError('ZIP output must be outside the package directory')
    if output.exists():
        raise FileExistsError(output)
    source_paths = [p for p in files() if p.suffix in ('.py', '.ini')]
    with (ROOT / 'ALL_SOURCE.txt').open('w', encoding='utf-8', newline='\n') as handle:
        handle.write('Complete source listing / 全ソース。閲覧用です。各ファイルを連結して実行しないでください。\n'
                     'PnFModsLoader.py is intentionally empty. No runtime telemetry or ATM binaries included.\n')
        for path in source_paths:
            handle.write('\n' + '=' * 78 + '\nFILE: ' + path.relative_to(ROOT).as_posix() + '\n' + '=' * 78 + '\n')
            handle.write(path.read_text(encoding='utf-8'))
            handle.write('\n')
    names = {p.relative_to(ROOT).as_posix() for p in files()} | GENERATED
    index = ['# 全ファイル一覧', '',
             '導入するのは `res_mods/` 内です。docs/tools/tests/examplesはゲーム外用です。', '',
             '| ファイル | 用途 |', '| --- | --- |']
    for name in sorted(names):
        if name.startswith('res_mods/'):
            role = 'ゲーム導入用（ローダーは既存を優先）'
        elif name.endswith('.bat') or name.endswith('.ps1'):
            role = 'Windows用の導入・復元・記録・表示ツール。ゲームへ入れない'
        elif name.startswith('viewer/'):
            role = 'ゲーム外の簡易2D表示。ゲームへ入れない'
        elif name.startswith('docs/'):
            role = '日本語ドキュメント'
        elif name.startswith('tests/') or name == 'pytest.ini':
            role = 'オフライン確認用。ゲームへ入れない'
        elif name.startswith('tools/'):
            role = '任意の外部ツール。ゲームへ入れない'
        elif name.startswith('examples/'):
            role = '架空の出力例。ゲームへ入れない'
        else:
            role = {'README.ja.md': '最初に読む', 'ALL_SOURCE.txt': '全ソース全文',
                    'SHA256SUMS.txt': '収録ファイルのSHA-256', 'LICENSE': 'MITライセンス',
                    'FILES.md': 'この一覧'}.get(name, 'パッケージ情報')
        index.append(f'| [{name}]({name}) | {role} |')
    (ROOT / 'FILES.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    manifest = []
    for path in files():
        if path.name == 'SHA256SUMS.txt':
            continue
        manifest.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  '
                        + path.relative_to(ROOT).as_posix())
    (ROOT / 'SHA256SUMS.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8')
    verify()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in files():
            archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    print('ZIP:', output)
    print('SHA256:', hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT.parent / (ROOT.name + '.zip'))
    args = parser.parse_args()
    if args.verify:
        verify()
    else:
        build(args.output)
