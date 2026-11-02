from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_bundle


def test_bundle_does_not_include_private_recordings(tmp_path, monkeypatch):
    (tmp_path / 'recordings').mkdir()
    (tmp_path / 'recordings' / 'private.jsonl').write_text('private')
    (tmp_path / 'README.md').write_text('public')
    monkeypatch.setattr(build_bundle, 'ROOT', tmp_path)
    assert [p.name for p in build_bundle.files()] == ['README.md']
