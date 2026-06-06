import pytest
from pathlib import Path
from src.utils import get_project_root, get_audio_dir, get_output_dir, get_data_raw_dir, get_data_processed_dir, hash_string


class TestPaths:
    def test_get_project_root(self):
        root = get_project_root()
        assert root.exists()
        assert (root / "src").exists()
        assert (root / "pyproject.toml").exists()

    def test_get_audio_dir(self):
        d = get_audio_dir()
        assert "audio" in str(d)
        assert d.is_absolute()

    def test_get_output_dir(self):
        d = get_output_dir()
        assert "output" in str(d)
        assert d.is_absolute()

    def test_get_data_raw_dir(self):
        d = get_data_raw_dir()
        assert "raw" in str(d)
        assert "data" in str(d)

    def test_get_data_processed_dir(self):
        d = get_data_processed_dir()
        assert "processed" in str(d)
        assert "data" in str(d)

    def test_all_paths_under_project_root(self):
        root = get_project_root()
        assert str(get_audio_dir()).startswith(str(root))
        assert str(get_output_dir()).startswith(str(root))
        assert str(get_data_raw_dir()).startswith(str(root))
        assert str(get_data_processed_dir()).startswith(str(root))


class TestHashString:
    def test_hash_string_length(self):
        h = hash_string("test")
        assert len(h) == 12

    def test_hash_string_hex(self):
        h = hash_string("test")
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_string_deterministic(self):
        assert hash_string("hello") == hash_string("hello")

    def test_hash_string_different_inputs(self):
        assert hash_string("hello") != hash_string("world")

    def test_hash_string_empty(self):
        h = hash_string("")
        assert len(h) == 12
        assert isinstance(h, str)

    def test_hash_string_unicode(self):
        h1 = hash_string("你好")
        h2 = hash_string("你好")
        assert h1 == h2
        assert hash_string("你好") != hash_string("您好")

    def test_hash_string_whitespace_sensitive(self):
        assert hash_string("hello") != hash_string("hello ")
