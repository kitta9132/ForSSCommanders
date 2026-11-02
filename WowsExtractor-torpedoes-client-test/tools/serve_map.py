"""Read-only localhost viewer for WowsExtractor JSON files (Python 3.10+)."""
import argparse
import json
import time
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MOD_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\World of Warships\bin\13357625\res_mods\PnFMods\WowsExtractor"
STALE_SECONDS = 3.0


class SnapshotReader:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.cache = {}
        self._lock = threading.RLock()

    def read(self, name):
        with self._lock:
            return self._read(name)

    def _read(self, name):
        path = self.directory / (name + '.json')
        error = None
        for attempt in range(3):
            try:
                before = path.stat()
                data = json.loads(path.read_text(encoding='utf-8-sig'),
                                  parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                after = path.stat()
                signature = lambda stat: (stat.st_mtime_ns, stat.st_size, stat.st_ino)
                if signature(before) != signature(after):
                    raise ValueError('file changed during read')
                mtime = after.st_mtime
                if not isinstance(data, dict):
                    raise ValueError('JSON root must be an object')
                json.dumps(data, allow_nan=False)  # also rejects 1e999 -> infinity
                if name == 'state':
                    if type(data.get('active')) is not bool:
                        raise ValueError('state.active must be boolean')
                    for key in ('ships', 'torpedoes'):
                        if key in data and (not isinstance(data[key], list) or
                                            not all(isinstance(row, dict) for row in data[key])):
                            raise ValueError('invalid state collection')
                self.cache[name] = (data, mtime)
                break
            except (OSError, ValueError, UnicodeError) as exc:
                error = str(exc)
                if attempt < 2:
                    time.sleep(0.02)
        else:
            cached = self.cache.get(name)
            return {'data': cached[0] if cached else None, 'stale': True,
                    'ageSeconds': max(0, time.time() - cached[1]) if cached else None,
                    'error': 'read/JSON error'}
        age = max(0, time.time() - mtime)
        return {'data': data, 'stale': age > STALE_SECONDS, 'ageSeconds': age, 'error': None}

    def snapshot(self):
        with self._lock:
            return self._snapshot()

    def _snapshot(self):
        state, meta = self.read('state'), self.read('meta')
        s, m = state['data'], meta['data']
        # Null IDs do not establish identity, even if both are null.
        match = bool(s and m and s.get('battleId') is not None and
                     m.get('battleId') is not None and s['battleId'] == m['battleId'])
        if not match:
            meta['data'] = None
        return {'state': state, 'meta': meta, 'metaMatches': match}


def make_handler(reader):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            host = self.headers.get('Host', '').lower().split(':', 1)[0]
            if host not in ('127.0.0.1', 'localhost'):
                self.send_error(403, 'Local host header required')
                return
            path = urlsplit(self.path).path
            if path == '/api/snapshot':
                body = json.dumps(reader.snapshot(), ensure_ascii=False, allow_nan=False).encode('utf-8')
                content_type = 'application/json; charset=utf-8'
            elif path in ('/', '/index.html'):
                body = (ROOT / 'viewer' / 'index.html').read_bytes()
                content_type = 'text/html; charset=utf-8'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def reject(self):
            self.send_error(405, 'Method not allowed')

        do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = reject

        def log_message(self, format, *args):
            pass  # polling should not flood the console

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mod-dir', default=DEFAULT_MOD_DIR)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(SnapshotReader(args.mod_dir)))
    except OSError as exc:
        parser.exit(1, f'Cannot bind 127.0.0.1:{args.port} (port in use or unavailable): {exc}\n')
    url = f'http://127.0.0.1:{args.port}/'
    print(f'Read-only map: {url}\nReading: {args.mod_dir}\nCtrl+C to stop', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
