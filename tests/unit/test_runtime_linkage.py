from types import SimpleNamespace

import pytest

import check_runtime_linkage as linkage


@pytest.fixture
def install_tree(tmp_path):
    library = tmp_path / "libtest.so.1"
    # ELF64, little endian, ET_DYN. No host compilation or ROS execution.
    library.write_bytes(b"\x7fELF\x02\x01" + bytes(10) + b"\x03\x00")
    (tmp_path / "libtest.so").symlink_to(library.name)
    (tmp_path / "setup.bash").write_text("# not an ELF file\n")
    return tmp_path


@pytest.mark.parametrize(
    "output,allow_drivers,missing",
    [
        ("libc.so.6 => /lib/libc.so.6 (0x123)\n", False, None),
        ("libcuda.so.1 => not found\n", False, "libcuda.so.1"),
        ("libcuda.so.1 => not found\n", True, None),
        ("libcudart.so.12 => not found\n", True, "libcudart.so.12"),
        ("libsl_zed.so => not found\n", True, "libsl_zed.so"),
        ("libcuda.so.1 => not found\nlibopencv_core.so => not found\n", True, "libopencv_core.so"),
    ],
)
def test_only_injected_driver_libraries_can_be_missing(
    monkeypatch, install_tree, output, allow_drivers, missing,
):
    calls = []

    def fake_ldd(args, **kwargs):
        calls.append(args)
        assert kwargs["env"]["LC_ALL"] == "C"
        return SimpleNamespace(returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(linkage.subprocess, "run", fake_ldd)
    errors = linkage.check_linkage(install_tree, allow_driver_libraries=allow_drivers)
    assert len(calls) == 1  # Symlink aliases must not duplicate work.
    if missing:
        assert len(errors) == 1
        assert f"missing {missing}" in errors[0]
    else:
        assert errors == []


@pytest.mark.parametrize(
    "output,expected_error",
    [("not a dynamic executable", False), ("statically linked", False), ("ldd: failed", True)],
)
def test_static_files_are_allowed_but_ldd_failures_are_reported(
    monkeypatch, install_tree, output, expected_error,
):
    monkeypatch.setattr(
        linkage.subprocess, "run",
        lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr=output),
    )
    errors = linkage.check_linkage(install_tree)
    assert bool(errors) == expected_error
    if errors:
        assert "ldd failed" in errors[0]


def test_missing_or_empty_install_is_not_a_success(tmp_path):
    assert "Missing install directory" in linkage.check_linkage(tmp_path / "missing")[0]
    assert "No ELF" in linkage.check_linkage(tmp_path)[0]
