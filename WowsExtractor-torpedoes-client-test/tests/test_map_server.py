import importlib.util
import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'serve_map.py'
spec = importlib.util.spec_from_file_location('serve_map', MODULE)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class MapServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.reader = server.SnapshotReader(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        (self.directory / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')

    def test_mismatch_missing_and_match(self):
        self.write('state', {'battleId': 'a', 'active': True})
        self.write('meta', {'battleId': 'b', 'secret': 'not combined'})
        result = self.reader.snapshot()
        self.assertFalse(result['metaMatches'])
        self.assertIsNone(result['meta']['data'])
        self.write('meta', {'battleId': 'a'})
        self.assertTrue(self.reader.snapshot()['metaMatches'])
        self.write('state', {'battleId': None, 'active': True})
        self.write('meta', {'battleId': None})
        self.assertFalse(self.reader.snapshot()['metaMatches'])

    def test_bad_json_cached_stale_and_recovery(self):
        self.write('state', {'battleId': 'a', 'active': True})
        self.assertFalse(self.reader.read('state')['stale'])
        (self.directory / 'state.json').write_text('{', encoding='utf-8')
        result = self.reader.read('state')
        self.assertTrue(result['stale'])
        self.assertIsNotNone(result['error'])
        self.assertEqual(result['data']['battleId'], 'a')
        self.write('state', {'battleId': 'b', 'active': True})
        self.assertEqual(self.reader.read('state')['data']['battleId'], 'b')

    def test_old_mtime(self):
        import os
        self.write('state', {'active': True})
        old = time.time() - 10
        os.utime(self.directory / 'state.json', (old, old))
        self.assertTrue(self.reader.read('state')['stale'])

    def test_routing_and_methods(self):
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(self.reader))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            conn = HTTPConnection('127.0.0.1', httpd.server_port)
            for method, path, expected in [('GET', '/', 200), ('HEAD', '/', 200),
                                           ('GET', '/api/snapshot', 200),
                                           ('GET', '/state.json', 404),
                                           ('GET', '/%2e%2e/state.json', 404),
                                           ('POST', '/api/snapshot', 405)]:
                conn.request(method, path)
                response = conn.getresponse()
                self.assertEqual(response.status, expected)
                response.read()
            conn.request('GET', '/api/snapshot', headers={'Host': 'external.example'})
            response = conn.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
            conn.close()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()

    def test_nonfinite_and_invalid_shapes_do_not_replace_cached_state(self):
        self.write('state', {'active': True, 'battleId': 'good'})
        self.reader.read('state')
        for raw in ('{"active":true,"ts":1e999}',
                    '{"active":"true"}', '{"active":true,"ships":{}}',
                    '{"active":true,"torpedoes":[null]}'):
            (self.directory / 'state.json').write_text(raw, encoding='utf8')
            result = self.reader.read('state')
            self.assertTrue(result['stale'])
            self.assertEqual(result['data']['battleId'], 'good')

    def test_unknown_avatar_observations_are_forwarded_separately_from_ships(self):
        state = {
            'active': True,
            'ships': [{'playerId': 20, 'vehicleId': 2000}],
            'avatarObservations': {
                'status': 'complete',
                'rows': [{'playerId': 24,
                          'apiPresence': {'status': 'missingInApi'},
                          'mapPosition': {'status': 'available'}}],
            },
            'futureUnknownField': {'kept': True},
        }
        self.write('state', state)
        result = self.reader.snapshot()['state']['data']
        self.assertEqual(result['ships'], state['ships'])
        self.assertEqual(result['avatarObservations'], state['avatarObservations'])
        self.assertEqual(result['futureUnknownField'], state['futureUnknownField'])
        self.assertEqual(len(result['ships']), 1)  # no observation-to-ship merge


if __name__ == '__main__':
    unittest.main()
