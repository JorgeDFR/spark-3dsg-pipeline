from types import SimpleNamespace

import validate_source


def test_svo_missing_file_does_not_load_sdk(monkeypatch, tmp_path):
    def unexpected_load(name):
        raise AssertionError("missing input should be reported first")
    monkeypatch.setattr(validate_source.ctypes, "CDLL", unexpected_load)
    assert "does not exist" in validate_source.validate_svo(tmp_path / "missing.svo")[0]


def sdk_fixture(monkeypatch, tmp_path):
    svo = tmp_path / "sample.svo"
    svo.touch()
    library = tmp_path / "libsl_zed.so"
    library.touch()
    monkeypatch.setattr(validate_source, "ZED_LIBRARY", library)
    return svo, library


def test_svo_loads_absolute_sdk_path_without_relying_on_cache(monkeypatch, tmp_path):
    svo, library = sdk_fixture(monkeypatch, tmp_path)
    loaded = []
    monkeypatch.setattr(validate_source.ctypes, "CDLL", loaded.append)
    assert validate_source.validate_svo(svo) == []
    assert loaded == [str(library)]
    assert library.is_absolute()


def test_svo_reports_missing_sdk_dependency(monkeypatch, tmp_path):
    svo, library = sdk_fixture(monkeypatch, tmp_path)
    def missing_library(name):
        raise OSError("libnvcuvid.so.1: cannot open shared object file")
    monkeypatch.setattr(validate_source.ctypes, "CDLL", missing_library)
    monkeypatch.setattr(validate_source.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        stdout="libnvcuvid.so.1 => not found\n", stderr="",
    ))
    errors = validate_source.validate_svo(svo)
    assert len(errors) == 1
    assert str(library) in errors[0]
    assert "libnvcuvid.so.1 => not found" in errors[0]
    assert "NVIDIA Container Toolkit" in errors[0]


def test_svo_distinguishes_missing_sdk_file(monkeypatch, tmp_path):
    svo, library = sdk_fixture(monkeypatch, tmp_path)
    library.unlink()
    assert "file missing or broken symlink" in validate_source.validate_svo(svo)[0]


def test_svo_reports_sdk_directory_permission_without_traceback(monkeypatch, tmp_path):
    svo, library = sdk_fixture(monkeypatch, tmp_path)
    original = type(library).is_file

    def denied_stat(path):
        if path == library:
            raise PermissionError(13, "Permission denied", str(path))
        return original(path)

    monkeypatch.setattr(type(library), "is_file", denied_stat)
    errors = validate_source.validate_svo(svo)
    assert len(errors) == 1
    assert "cannot access ZED SDK" in errors[0]
    assert "traversal access" in errors[0]
    assert "make build-preprocess" in errors[0]


def test_svo_reports_unreadable_sdk_file_before_loading(monkeypatch, tmp_path):
    svo, library = sdk_fixture(monkeypatch, tmp_path)
    original = type(library).open

    def denied_open(path, *args, **kwargs):
        if path == library:
            raise PermissionError(13, "Permission denied", str(path))
        return original(path, *args, **kwargs)

    def unexpected_load(name):
        raise AssertionError("unreadable file should be reported before loading")

    monkeypatch.setattr(type(library), "open", denied_open)
    monkeypatch.setattr(validate_source.ctypes, "CDLL", unexpected_load)
    assert "cannot access ZED SDK" in validate_source.validate_svo(svo)[0]
