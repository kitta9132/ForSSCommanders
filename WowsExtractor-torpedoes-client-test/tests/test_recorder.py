import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import record_telemetry as rec


def write(path, **values):
    data = {'schema': 1, 'active': True, 'ts': 1., 'torpedoes': []}
    data.update(values)
    path.write_text(json.dumps(data), encoding='utf-8')


def test_torn_json_retries_and_end_and_type_changes_are_preserved(tmp_path):
    state = tmp_path / 'state.json'
    seen = {}
    write(state, torpedoes=[{'uiId': 1, 'type': 'normal'}])
    assert rec.poll_files(tmp_path, seen)[0]['data']['torpedoes'][0]['type'] == 'normal'
    assert rec.poll_files(tmp_path, seen) == []
    state.write_text('{"schema": 1, "active":')
    assert rec.poll_files(tmp_path, seen) == []
    write(state, ts=2., torpedoes=[{'uiId': 1, 'type': 'acoustic'}])
    assert rec.poll_files(tmp_path, seen)[0]['data']['torpedoes'][0]['type'] == 'acoustic'
    write(state, ts=3., active=False)
    assert rec.poll_files(tmp_path, seen)[0]['data']['active'] is False


@pytest.mark.parametrize('bad', [
    '{"schema":1,"active":true,"ts":NaN}',
    '{"schema":1,"active":true,"ts":1e999}',
    '{"schema":1,"active":"true"}',
    '{"schema":1,"active":true,"torpedoes":[null]}',
])
def test_invalid_payload_not_marked_as_seen(tmp_path, bad):
    (tmp_path / 'state.json').write_text(bad)
    seen = {}
    assert rec.poll_files(tmp_path, seen) == []
    assert seen == {}


def test_slim_capture_drops_roster_and_player_names_but_keeps_raw_type():
    data = {'schema': 1, 'active': True, 'self': {'playerName': 'private'},
            'ships': [], 'torpedoes': [{'uiId': 1, 'type': 'future_type'}]}
    out = rec.project_payload(data, 'state', True)
    assert 'self' not in out and 'ships' not in out
    assert out['torpedoes'][0]['type'] == 'future_type'


def test_cannot_overwrite_source_or_existing_recording(tmp_path):
    source = tmp_path / 'state.json'
    write(source)
    original = source.read_bytes()
    with pytest.raises(ValueError):
        rec.record(tmp_path, source, .05, seconds=.01)
    assert source.read_bytes() == original
    output = tmp_path / 'recording.jsonl'
    output.write_text('keep')
    with pytest.raises(FileExistsError):
        rec.record(tmp_path, output, .05, seconds=.01)
    assert output.read_text() == 'keep'


def test_capture_writes_parseable_jsonl_and_preserves_sources(tmp_path):
    source = tmp_path / 'state.json'
    write(source)
    original = source.read_bytes()
    output = tmp_path / 'recording.jsonl'
    assert rec.record(tmp_path, output, .05, seconds=.001) == 1
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert rows[0]['kind'] == 'state'
    assert 'observedAt' in rows[0]
    assert source.read_bytes() == original


def test_numbered_output_continues_existing_sequence(tmp_path):
    (tmp_path / 'without-atm-b01.jsonl').write_text('keep')
    (tmp_path / 'without-atm-b02.jsonl').write_text('keep')
    (tmp_path / 'unrelated99.jsonl').write_text('keep')
    output, handle = rec.open_numbered_output(tmp_path, 'without-atm-b')
    with handle:
        handle.write('new')
    assert output.name == 'without-atm-b03.jsonl'
    assert (tmp_path / 'without-atm-b01.jsonl').read_text() == 'keep'


def test_numbered_output_reserves_distinct_files(tmp_path):
    first, handle1 = rec.open_numbered_output(tmp_path, 'run-')
    try:
        second, handle2 = rec.open_numbered_output(tmp_path, 'run-')
        handle2.close()
    finally:
        handle1.close()
    assert first.name == 'run-01.jsonl'
    assert second.name == 'run-02.jsonl'


def test_numbered_output_rejects_path_prefix(tmp_path):
    with pytest.raises(ValueError):
        rec.open_numbered_output(tmp_path, '../bad')


def test_record_with_automatic_filename(tmp_path):
    write(tmp_path / 'state.json')
    assert rec.record(tmp_path, None, .05, seconds=.001,
                      output_dir=tmp_path / 'captures', prefix='test-') == 1
    assert (tmp_path / 'captures' / 'test-01.jsonl').is_file()


def test_slim_capture_keeps_ui_probe():
    probe = {'status': 'available', 'rows': [{'isHoming': False}]}
    out = rec.project_payload({'schema': 1, 'uiTorpedoProbe': probe}, 'state', True)
    assert out['uiTorpedoProbe'] == probe


def test_recorder_warns_when_active_state_stops_changing(tmp_path, monkeypatch, capsys):
    write(tmp_path / 'state.json')
    clock = [0.]
    monkeypatch.setattr(rec.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(rec.time, 'sleep', lambda interval: clock.__setitem__(0, clock[0] + 6.))
    assert rec.record(tmp_path, tmp_path / 'capture.jsonl', .05, seconds=6.) == 1
    assert 'WARNING: active state.json has not changed' in capsys.readouterr().out
