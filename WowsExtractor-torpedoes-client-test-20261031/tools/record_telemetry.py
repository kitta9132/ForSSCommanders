#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Optional desktop recorder. Python >=3.10; standard library only.

Reads the mod's JSON files; never imports or modifies the game/mod/ATM.
Output is an exclusively created JSONL file. A partial input is retried.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import time


def reject_constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def read_payload(path, kind):
    """Return one stable, minimally validated file revision, or None."""
    try:
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
        signature = lambda s: (s.st_mtime_ns, s.st_size, s.st_ino)
        if signature(before) != signature(after):
            return None
        data = json.loads(raw.decode('utf-8-sig'), parse_constant=reject_constant)
        if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1:
            return None
        if kind == 'state':
            if type(data.get('active')) is not bool:
                return None
            if 'torpedoes' in data and (not isinstance(data['torpedoes'], list)
                    or not all(isinstance(row, dict) for row in data['torpedoes'])):
                return None
        # json.loads can turn 1e999 into infinity without parse_constant.
        json.dumps(data, allow_nan=False)
        return data, after.st_mtime_ns, hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, ValueError, TypeError):
        return None


def project_payload(data, kind, torpedoes_only):
    if not torpedoes_only:
        return data
    keys = ('schema', 'apiVersion', 'battleId', 'active', 'ts',
            'torpedoes', 'torpedoStatus', 'torpedoArmament', 'uiTorpedoProbe') if kind == 'state' else (
            'schema', 'apiVersion', 'battleId', 'ts', 'mod', 'map')
    return {key: data[key] for key in keys if key in data}


def poll_files(mod_dir, seen, torpedoes_only=False):
    records = []
    for kind in ('meta', 'state'):
        result = read_payload(mod_dir / (kind + '.json'), kind)
        if result is None:
            continue
        data, mtime, digest = result
        if seen.get(kind) == digest:
            continue
        seen[kind] = digest
        records.append({
            'kind': kind,
            'observedAt': datetime.now(timezone.utc).isoformat(),
            'mtimeNs': mtime,
            'data': project_payload(data, kind, torpedoes_only),
        })
    return records


def open_numbered_output(directory, prefix):
    """Reserve the next number exclusively, including concurrent recorders."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', prefix):
        raise ValueError('prefix must contain only letters, digits, underscores or hyphens')
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(re.escape(prefix) + r'([0-9]+)\.jsonl$')
    number = max((int(match.group(1)) for path in directory.iterdir()
                  if (match := pattern.fullmatch(path.name))), default=0) + 1
    while True:
        output = directory / ('%s%02d.jsonl' % (prefix, number))
        try:
            return output, output.open('x', encoding='utf-8', newline='\n')
        except FileExistsError:
            number += 1


def record(mod_dir, output, interval, seconds=None, torpedoes_only=False,
           output_dir='recordings', prefix='run-'):
    mod_dir = Path(mod_dir).resolve()
    output = Path(output).resolve() if output is not None else None
    if not mod_dir.is_dir():
        raise ValueError('mod directory does not exist: ' + str(mod_dir))
    if interval < 0.02 or not interval < float('inf'):
        raise ValueError('interval must be finite and >= 0.02 seconds')
    if seconds is not None and not 0 < seconds < float('inf'):
        raise ValueError('seconds must be finite and positive')
    if output in ((mod_dir / 'state.json').resolve(), (mod_dir / 'meta.json').resolve()):
        raise ValueError('output must not replace a source JSON file')
    if output is None:
        output, handle = open_numbered_output(output_dir, prefix)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        handle = output.open('x', encoding='utf-8', newline='\n')
    count = 0
    seen = {}
    started = time.monotonic()
    last_report = started
    last_state_at = None
    last_state = None
    with handle:
        print('Recording:', mod_dir)
        print('Output:', output)
        print('Waiting for valid JSON; Ctrl+C stops recording.')
        try:
            while True:
                for event in poll_files(mod_dir, seen, torpedoes_only):
                    handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + '\n')
                    handle.flush()
                    count += 1
                    if event['kind'] == 'state':
                        last_state_at = time.monotonic()
                        last_state = event['data']
                now = time.monotonic()
                if now - last_report >= 5.:
                    if last_state is None:
                        print('Saved:', count, '- waiting for state.json')
                    else:
                        print('Saved:', count, 'active:', last_state.get('active'),
                              'ts:', last_state.get('ts'),
                              'torpedoes:', len(last_state.get('torpedoes', [])))
                        if last_state.get('active') and now - last_state_at >= 5.:
                            print('WARNING: active state.json has not changed for 5+ seconds. Check game/mod logs.')
                    last_report = now
                if seconds is not None and time.monotonic() - started >= seconds:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass
    print('Saved records:', count)
    if not count:
        print('No valid files observed. Check --mod-dir and battle status.')
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mod-dir', required=True, type=Path)
    parser.add_argument('--output', type=Path, help='explicit new filename (never overwritten)')
    parser.add_argument('--output-dir', type=Path, default=Path('recordings'),
                        help='directory for automatically numbered recordings')
    parser.add_argument('--prefix', default='run-', help='numbered filename prefix')
    parser.add_argument('--interval', type=float, default=0.05)
    parser.add_argument('--seconds', type=float)
    parser.add_argument('--torpedoes-only', action='store_true',
                        help='omit roster, self/ships and damage; NOT full anonymization')
    args = parser.parse_args()
    try:
        record(args.mod_dir, args.output, args.interval, args.seconds, args.torpedoes_only,
               args.output_dir, args.prefix)
    except (OSError, ValueError) as error:
        parser.exit(1, 'Error: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
