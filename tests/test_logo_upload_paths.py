"""Local upload filesystem boundaries: real files, no network or live HA."""

from __future__ import annotations

import asyncio
import errno
import hashlib
import os
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image

from custom_components.handballnet import logo_manager as lm


@pytest.fixture
def upload_case(tmp_path, monkeypatch):
    """Use HA's upload context contract and exercise the real executor path."""
    source = tmp_path / "incoming.png"
    Image.new("RGBA", (8, 6), "red").save(source, format="PNG")
    contents = source.read_bytes()
    digest = hashlib.sha256(contents).hexdigest()

    @contextmanager
    def uploaded(*_args):
        try:
            yield source
        finally:
            source.unlink(missing_ok=True)

    async def executor(func, *args):
        return await asyncio.to_thread(func, *args)

    monkeypatch.setattr(lm, "process_uploaded_file", uploaded)
    hass = SimpleNamespace(
        data={},
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
        async_add_executor_job=executor,
    )
    manager = lm.LogoManager(hass)
    return SimpleNamespace(
        root=tmp_path,
        source=source,
        contents=contents,
        digest=digest,
        directory=tmp_path / "www" / "handballnet" / "logos",
        manager=manager,
        file_id=str(uuid4()),
    )


def rejected(case):
    """Failures consume the upload but never publish state or notify listeners."""
    before = case.manager.as_attributes()
    events = []
    case.manager.async_listen(lambda: events.append(True))
    with pytest.raises(lm.LogoStorageError, match="storage_error"):
        asyncio.run(case.manager.async_set_upload("Test", case.file_id))
    assert not case.source.exists()
    assert case.manager.as_attributes() == before
    assert "_test_stores" not in case.manager.hass.data
    assert not events


@pytest.mark.parametrize("component", ["www", "handballnet", "logos"])
@pytest.mark.parametrize("dangling", [False, True])
def test_rejects_existing_directory_symlink(upload_case, component, dangling):
    case = upload_case
    parts = ["www", "handballnet", "logos"]
    index = parts.index(component)
    parent = case.root.joinpath(*parts[:index])
    parent.mkdir(parents=True, exist_ok=True)
    outside = case.root / "outside"
    if not dangling:
        outside.mkdir()
        (outside / "keep.png").write_bytes(b"existing unrelated asset")
    (parent / component).symlink_to(outside, target_is_directory=True)

    rejected(case)

    assert (parent / component).is_symlink()
    if dangling:
        assert not outside.exists()
    else:
        assert sorted(p.name for p in outside.iterdir()) == ["keep.png"]
        assert (outside / "keep.png").read_bytes() == b"existing unrelated asset"


@pytest.mark.parametrize("kind", ["matching", "different", "dangling"])
def test_existing_hash_symlink_is_never_followed_or_replaced(upload_case, kind):
    case = upload_case
    case.directory.mkdir(parents=True)
    outside = case.root / "outside.png"
    if kind != "dangling":
        outside.write_bytes(case.contents if kind == "matching" else b"preserve me")
    target = case.directory / f"{case.digest}.png"
    target.symlink_to(outside)

    rejected(case)

    assert target.is_symlink()
    assert list(case.directory.iterdir()) == [target]
    if kind == "dangling":
        assert not outside.exists()
    else:
        assert outside.read_bytes() == (
            case.contents if kind == "matching" else b"preserve me"
        )


def test_hash_collision_fifo_is_opened_nonblocking_and_rejected(
    upload_case, monkeypatch
):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    os.mkfifo(target)
    real_open = os.open

    def guarded_open(path, flags, *args, **kwargs):
        if str(path) == target.name:
            # Fail the old blocking open before the real FIFO can hang pytest.
            assert flags & os.O_NONBLOCK, (
                "Existing special files must never block the executor"
            )
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(lm.os, "open", guarded_open)
    rejected(case)
    assert list(case.directory.iterdir()) == [target]
    assert not target.is_file()


def test_oversized_existing_hash_file_is_rejected_before_read(upload_case, monkeypatch):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    oversized = case.contents + b"x"
    target.write_bytes(oversized)
    monkeypatch.setattr(lm, "MAX_OUTPUT_BYTES", len(case.contents))
    real_fdopen = os.fdopen

    def guarded_fdopen(fd, mode, *args, **kwargs):
        assert mode != "rb", "Oversized target must be rejected by fstat before reading"
        return real_fdopen(fd, mode, *args, **kwargs)

    monkeypatch.setattr(lm.os, "fdopen", guarded_fdopen)
    rejected(case)
    assert target.read_bytes() == oversized
    assert list(case.directory.iterdir()) == [target]


def test_existing_hash_file_read_is_bounded_even_if_file_grows(
    upload_case, monkeypatch
):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    target.write_bytes(case.contents)
    limit = len(case.contents)
    monkeypatch.setattr(lm, "MAX_OUTPUT_BYTES", limit)
    real_fdopen = os.fdopen
    reads = []

    @contextmanager
    def checked_fdopen(fd, mode, *args, **kwargs):
        with real_fdopen(fd, mode, *args, **kwargs) as stream:
            if mode != "rb":
                yield stream
                return
            # A concurrent writer can enlarge a file after its fstat check.
            with target.open("ab") as writer:
                writer.write(b"x" * 1024)

            def bounded_read(size=-1):
                assert 0 <= size <= limit + 1, (
                    "Target reads must have an explicit byte bound"
                )
                reads.append(size)
                return stream.read(size)

            yield SimpleNamespace(read=bounded_read)

    monkeypatch.setattr(lm.os, "fdopen", checked_fdopen)
    rejected(case)
    assert reads == [limit + 1]
    assert list(case.directory.iterdir()) == [target]


@pytest.mark.parametrize("component", ["www", "handballnet", "logos"])
def test_directory_replaced_with_symlink_during_publication_fails_closed(
    upload_case, monkeypatch, component
):
    case = upload_case
    case.directory.mkdir(parents=True)
    parts = ["www", "handballnet", "logos"]
    replaced = case.root.joinpath(*parts[: parts.index(component) + 1])
    detached = case.root / "detached"
    outside = case.root / "outside"
    outside.mkdir()
    (outside / "preserve.png").write_bytes(b"unrelated")
    real_link = os.link

    def racing_link(src, dst, *args, **kwargs):
        replaced.rename(detached)
        replaced.symlink_to(outside, target_is_directory=True)
        return real_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(lm.os, "link", racing_link)
    rejected(case)
    assert replaced.is_symlink()
    assert sorted(p.name for p in outside.iterdir()) == ["preserve.png"]
    assert (outside / "preserve.png").read_bytes() == b"unrelated"
    assert not list(detached.rglob(".logo-*"))


def test_temporary_source_swapped_for_symlink_during_link_is_not_accepted(
    upload_case, monkeypatch
):
    case = upload_case
    case.directory.mkdir(parents=True)
    outside = case.root / "outside.png"
    outside.write_bytes(case.contents)
    real_link = os.link

    def racing_link(src, dst, *args, **kwargs):
        os.unlink(src, dir_fd=kwargs["src_dir_fd"])
        os.symlink(outside, src, dir_fd=kwargs["src_dir_fd"])
        return real_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(lm.os, "link", racing_link)
    rejected(case)
    assert outside.read_bytes() == case.contents
    assert not list(case.directory.glob(".logo-*"))


@pytest.mark.parametrize(
    "capability",
    ["O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "dir_fd", "follow_symlinks"],
)
def test_unsupported_filesystem_capabilities_fail_closed(
    upload_case, monkeypatch, capability
):
    if capability == "dir_fd":
        monkeypatch.setattr(lm.os, "supports_dir_fd", set())
    elif capability == "follow_symlinks":
        monkeypatch.setattr(lm.os, "supports_follow_symlinks", set())
    else:
        monkeypatch.delattr(lm.os, capability)
    rejected(upload_case)
    assert not (upload_case.root / "www").exists()


def test_runtime_unsupported_link_is_a_storage_error_without_fallback(
    upload_case, monkeypatch
):
    def unsupported(*args, **kwargs):
        raise NotImplementedError("Synthetic unsupported filesystem")

    monkeypatch.setattr(lm.os, "link", unsupported)
    rejected(upload_case)
    assert list(upload_case.directory.iterdir()) == []


def test_hash_name_replaced_by_symlink_after_read_is_not_accepted(
    upload_case, monkeypatch
):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    target.write_bytes(case.contents)
    outside = case.root / "outside.png"
    outside.write_bytes(case.contents)
    real_fdopen = os.fdopen

    @contextmanager
    def racing_fdopen(fd, mode, *args, **kwargs):
        with real_fdopen(fd, mode, *args, **kwargs) as stream:
            yield stream
            if mode == "rb":
                target.unlink()
                target.symlink_to(outside)

    monkeypatch.setattr(lm.os, "fdopen", racing_fdopen)
    rejected(case)
    assert target.is_symlink()
    assert outside.read_bytes() == case.contents
    assert not list(case.directory.glob(".logo-*"))


def test_matching_regular_hash_reuses_inode_and_preserves_unreferenced_assets(
    upload_case,
):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    target.write_bytes(case.contents)
    unrelated = case.directory / "unreferenced.png"
    unrelated.write_bytes(b"keep this unreferenced asset")
    before = target.stat()
    unrelated_before = unrelated.stat()

    asyncio.run(case.manager.async_set_upload("First", case.file_id))

    after = target.stat()
    assert (after.st_ino, after.st_mtime_ns, after.st_mode) == (
        before.st_ino,
        before.st_mtime_ns,
        before.st_mode,
    )
    assert target.read_bytes() == case.contents
    assert unrelated.read_bytes() == b"keep this unreferenced asset"
    unrelated_after = unrelated.stat()
    assert (
        unrelated_after.st_ino,
        unrelated_after.st_mtime_ns,
        unrelated_after.st_mode,
    ) == (
        unrelated_before.st_ino,
        unrelated_before.st_mtime_ns,
        unrelated_before.st_mode,
    )
    asyncio.run(
        case.manager.async_set_url("Second", f"/local/handballnet/logos/{target.name}")
    )
    asyncio.run(case.manager.async_remove("First"))
    asyncio.run(case.manager.async_remove("Second"))
    assert set(case.directory.iterdir()) == {target, unrelated}
    assert not case.source.exists()


@pytest.mark.parametrize("kind", ["different_file", "directory", "hardlink"])
def test_nonmatching_hash_collision_preserves_existing_entry(upload_case, kind):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    outside = case.root / "outside.png"
    if kind == "directory":
        target.mkdir()
        (target / "keep").write_bytes(b"untouched")
    elif kind == "hardlink":
        outside.write_bytes(b"untouched")
        os.link(outside, target)
    else:
        target.write_bytes(b"untouched")
    before = target.stat()
    rejected(case)
    after = target.stat()
    assert (after.st_ino, after.st_mtime_ns, after.st_mode) == (
        before.st_ino,
        before.st_mtime_ns,
        before.st_mode,
    )
    assert (
        target / "keep" if kind == "directory" else target
    ).read_bytes() == b"untouched"
    if kind == "hardlink":
        assert outside.read_bytes() == b"untouched"
    assert list(case.directory.iterdir()) == [target]


def test_temp_symlink_collision_is_never_overwritten_or_deleted(
    upload_case, monkeypatch
):
    case = upload_case
    case.directory.mkdir(parents=True)
    outside = case.root / "outside.png"
    outside.write_bytes(b"preserve")
    temporary = case.directory / ".logo-predictable-test-only"
    temporary.symlink_to(outside)
    monkeypatch.setattr(
        lm, "uuid4", lambda: SimpleNamespace(hex="predictable-test-only")
    )
    rejected(case)
    assert temporary.is_symlink()
    assert outside.read_bytes() == b"preserve"
    assert list(case.directory.iterdir()) == [temporary]


@pytest.mark.parametrize("operation", ["fsync", "link"])
def test_write_or_link_failure_cleans_only_own_temporary_file(
    upload_case, monkeypatch, operation
):
    case = upload_case
    case.directory.mkdir(parents=True)
    unrelated = case.directory / "unreferenced.png"
    unrelated.write_bytes(b"keep")

    def failed(*args, **kwargs):
        raise OSError("Synthetic local failure")

    monkeypatch.setattr(lm.os, operation, failed)
    rejected(case)
    assert list(case.directory.iterdir()) == [unrelated]
    assert unrelated.read_bytes() == b"keep"


@pytest.mark.parametrize("kind", ["matching", "different", "symlink"])
def test_competing_hash_creation_is_atomic_no_overwrite(upload_case, monkeypatch, kind):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    outside = case.root / "outside.png"
    outside.write_bytes(case.contents)
    real_link = os.link

    def competing_link(src, dst, *args, **kwargs):
        temporary = case.directory / src
        assert temporary.read_bytes() == case.contents
        assert not temporary.is_symlink()
        assert temporary.stat().st_mode & 0o777 == 0o600
        if kind == "symlink":
            target.symlink_to(outside)
        else:
            target.write_bytes(case.contents if kind == "matching" else b"competitor")
        return real_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(lm.os, "link", competing_link)
    if kind == "matching":
        asyncio.run(case.manager.async_set_upload("Test", case.file_id))
        assert target.read_bytes() == case.contents
    else:
        rejected(case)
        if kind == "different":
            assert target.read_bytes() == b"competitor"
        else:
            assert target.is_symlink()
    assert list(case.directory.iterdir()) == [target]
    assert outside.read_bytes() == case.contents


@pytest.mark.parametrize("component", ["www", "handballnet", "logos"])
def test_symlink_swap_between_mkdir_and_open_never_reaches_outside(
    upload_case, monkeypatch, component
):
    case = upload_case
    outside = case.root / "outside"
    outside.mkdir()
    real_mkdir = os.mkdir
    raced = []

    def racing_mkdir(path, *args, **kwargs):
        result = real_mkdir(path, *args, **kwargs)
        if path == component and "dir_fd" in kwargs:
            os.rmdir(path, dir_fd=kwargs["dir_fd"])
            os.symlink(outside, path, dir_fd=kwargs["dir_fd"])
            raced.append(True)
        return result

    monkeypatch.setattr(lm.os, "mkdir", racing_mkdir)
    rejected(case)
    assert raced == [True]
    assert list(outside.iterdir()) == []


def test_hash_symlink_swap_just_before_open_is_rejected(upload_case, monkeypatch):
    case = upload_case
    case.directory.mkdir(parents=True)
    target = case.directory / f"{case.digest}.png"
    target.write_bytes(case.contents)
    outside = case.root / "outside.png"
    outside.write_bytes(case.contents)
    real_open = os.open
    raced = []

    def racing_open(path, flags, *args, **kwargs):
        if str(path) == target.name:
            target.unlink()
            target.symlink_to(outside)
            raced.append(True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(lm.os, "open", racing_open)
    rejected(case)
    assert raced == [True]
    assert target.is_symlink()
    assert outside.read_bytes() == case.contents


def test_temp_descriptor_is_closed_when_stream_construction_fails(
    upload_case, monkeypatch
):
    real_open, real_fdopen = os.open, os.fdopen
    temporary_fds = []

    def tracked_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        if flags & os.O_CREAT:
            temporary_fds.append(fd)
        return fd

    def failed_fdopen(fd, mode, *args, **kwargs):
        if mode == "wb":
            raise OSError("Synthetic stream construction failure")
        return real_fdopen(fd, mode, *args, **kwargs)

    monkeypatch.setattr(lm.os, "open", tracked_open)
    monkeypatch.setattr(lm.os, "fdopen", failed_fdopen)
    rejected(upload_case)
    assert list(upload_case.directory.iterdir()) == []
    assert len(temporary_fds) == 1
    try:
        with pytest.raises(OSError) as error:
            os.fstat(temporary_fds[0])
        assert error.value.errno == errno.EBADF
    finally:
        # Keep the intentionally failing baseline run from leaking the test FD.
        try:
            os.close(temporary_fds[0])
        except OSError:
            pass
