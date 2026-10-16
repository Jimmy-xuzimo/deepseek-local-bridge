import logging
from pathlib import Path

from app.bridge.base import Attachment
from app.bridge.deepseek import DeepSeekWebBackend
from app.config import AppConfig, Paths


def make_backend(tmp_path: Path) -> tuple[DeepSeekWebBackend, Paths]:
    paths = Paths(tmp_path / "data")
    paths.ensure()
    config = AppConfig(launch_browser_on_start=False)
    backend = DeepSeekWebBackend(config, paths, logging.getLogger("dsb-test"))
    return backend, paths


def test_prepare_upload_paths_copies_with_original_name(tmp_path):
    backend, paths = make_backend(tmp_path)
    stored = paths.uploads_dir / "file-abc123.txt"
    stored.write_text("密语", encoding="utf-8")
    attachment = Attachment(path=stored, filename="note.txt", kind="file")

    prepared, work_dir = backend._prepare_upload_paths([attachment])
    assert work_dir is not None
    prepared_path = Path(prepared[0])
    assert prepared_path.name == "note.txt"
    assert prepared_path.read_text(encoding="utf-8") == "密语"

    backend._cleanup_upload_dir(work_dir)
    assert not work_dir.exists()


def test_prepare_upload_paths_keeps_files_already_named_correctly(tmp_path):
    backend, paths = make_backend(tmp_path)
    stored = paths.uploads_dir / "note.txt"
    stored.write_text("hi", encoding="utf-8")
    attachment = Attachment(path=stored, filename="note.txt", kind="file")

    prepared, work_dir = backend._prepare_upload_paths([attachment])
    assert work_dir is None
    assert prepared == [str(stored)]


def test_safe_filename_strips_illegal_characters(tmp_path):
    backend, _paths = make_backend(tmp_path)
    cleaned = DeepSeekWebBackend._safe_filename('a/b\\c:d*e?f"g<h>i|j.txt')
    assert cleaned == "a_b_c_d_e_f_g_h_i_j.txt"
    assert DeepSeekWebBackend._safe_filename("") == "file"
    assert len(DeepSeekWebBackend._safe_filename("x" * 200)) == 80


def test_cleanup_upload_dir_refuses_outside_uploads(tmp_path):
    backend, paths = make_backend(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    backend._cleanup_upload_dir(outside)
    assert outside.exists()
