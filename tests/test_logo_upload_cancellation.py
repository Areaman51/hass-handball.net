"""Offline cancellation regressions, runnable with doubles or native HA."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import shutil
import socket
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image
from homeassistant.components import file_upload

from custom_components.handballnet import logo_manager as lm


@asynccontextmanager
async def upload_environment(root, monkeypatch):
    """Use real HA upload contexts and Store when running in the native env."""
    def no_network(*args, **kwargs):
        raise AssertionError("Network prohibited in upload cancellation tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    config, uploads = root / "config", root / "uploads"
    config.mkdir()
    uploads.mkdir()
    files = {}
    native = hasattr(file_upload, "FileUploadData")
    if native:
        from homeassistant import loader
        from homeassistant.core import HomeAssistant

        hass = HomeAssistant(str(config))
        loader.async_setup(hass)
        hass.data[file_upload._DATA] = file_upload.FileUploadData(uploads, files)
    else:
        async def executor(func, *args):
            return await asyncio.to_thread(func, *args)

        hass = SimpleNamespace(
            data={}, config=SimpleNamespace(path=lambda *p: str(config.joinpath(*p))),
            async_add_executor_job=executor,
        )

        @contextmanager
        def uploaded(hass, file_id):
            # Match native HA's one-shot lookup and non-idempotent cleanup.
            if file_id not in files:
                raise ValueError("File does not exist")
            try:
                yield uploads / file_id / files[file_id]
            finally:
                files.pop(file_id)
                shutil.rmtree(uploads / file_id)

        monkeypatch.setattr(lm, "process_uploaded_file", uploaded)

    def new_upload():
        file_id = str(uuid4())
        directory = uploads / file_id
        directory.mkdir()
        source = directory / "image.png"
        Image.new("RGBA", (8, 6), "red").save(source, format="PNG")
        files[file_id] = source.name
        return file_id, directory

    try:
        manager = await lm.async_get_logo_manager(hass)
        yield manager, new_upload, files, config
    finally:
        if native:
            await hass.async_stop(force=True)


async def wait_thread(event):
    assert await asyncio.to_thread(event.wait, 5), "Worker synchronization timed out"


@pytest.mark.parametrize("cancel_count", [1, 3])
def test_cancelled_upload_serializes_retries_through_native_cleanup(
    tmp_path, monkeypatch, cancel_count,
):
    async def scenario():
        async with upload_environment(tmp_path, monkeypatch) as env:
            manager, new_upload, files, config = env
            file_id, source_dir = new_upload()
            initial = manager.as_attributes()
            notifications = []
            manager.async_listen(lambda: notifications.append(manager.as_attributes()))
            at_fsync, release_write = threading.Event(), threading.Event()
            at_cleanup, release_cleanup = threading.Event(), threading.Event()
            entered = []
            real_context, real_fsync = lm.process_uploaded_file, lm.os.fsync

            @contextmanager
            def gated_context(hass, upload_id):
                entered.append(upload_id)
                with real_context(hass, upload_id) as source:
                    try:
                        yield source
                    finally:
                        if len(entered) == 1:
                            at_cleanup.set()
                            assert release_cleanup.wait(5), "Cleanup release timed out"

            def gated_fsync(fd):
                at_fsync.set()
                assert release_write.wait(5), "Write release timed out"
                return real_fsync(fd)

            monkeypatch.setattr(lm, "process_uploaded_file", gated_context)
            monkeypatch.setattr(lm.os, "fsync", gated_fsync)
            first = asyncio.create_task(manager.async_set_upload("Cancelled", file_id))
            retries = []
            try:
                await wait_thread(at_fsync)
                for _ in range(cancel_count):
                    first.cancel()
                    await asyncio.sleep(0)
                retries = [asyncio.create_task(manager.async_set_upload("Retry", file_id))
                           for _ in range(3)]
                # Cancelling a lock waiter must not consume the upload either.
                waiter = asyncio.create_task(manager.async_set_upload("Waiter", file_id))
                retries.append(waiter)
                await asyncio.sleep(0)
                waiter.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await waiter
                assert manager._save_lock.locked(), "Cancelled worker released the save lock"
                assert not first.done(), "Cancellation returned before worker cleanup"
                assert entered == [file_id], "Retry entered an active upload context"
                release_write.set()
                await wait_thread(at_cleanup)
                for _ in range(cancel_count):
                    first.cancel()
                    await asyncio.sleep(0)
                assert manager._save_lock.locked(), "Native cleanup is outside serialization"
                assert entered == [file_id]
                assert manager.as_attributes() == initial and notifications == []
                assert not Path(manager._store.path).exists()
                release_cleanup.set()
                with pytest.raises(asyncio.CancelledError):
                    await first
                for retry in retries[:-1]:
                    with pytest.raises(lm.LogoValidationError, match="^invalid_upload$"):
                        await retry
                from custom_components.handballnet.options_flow import HandballNetOptionsFlowHandler

                flow = HandballNetOptionsFlowHandler(None)
                flow.hass = manager.hass
                flow._team_name = "retry"
                form = await flow.async_step_logo_upload({"file_id": file_id})
                assert form["type"] == "form" and form["step_id"] == "logo_upload"
                assert form["errors"] == {"file_id": "invalid_upload"}
                assert not source_dir.exists() and files == {}
                assert manager.as_attributes() == initial and notifications == []
                assert not Path(manager._store.path).exists()
                assert "_test_stores" not in manager.hass.data
                assert not list(config.rglob(".logo-*"))
                # Publication may finish, but never delete a possibly shared PNG.
                targets = list(config.rglob("*.png"))
                assert len(targets) == 1
                target_inode = targets[0].stat().st_ino
                normal_id, normal_dir = new_upload()
                await manager.async_set_upload("Normal", normal_id)
                assert not normal_dir.exists() and files == {}
                assert manager.as_attributes()["handballnet_logo_revision"] == 1
                assert set(manager.as_attributes()["handballnet_logo_overrides"]) == {"normal"}
                assert len(notifications) == 1
                assert targets[0].stat().st_ino == target_inode
                assert not manager._save_lock.locked()
            finally:
                release_write.set()
                release_cleanup.set()
                await asyncio.gather(first, *retries, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("failure", ["storage", "programming"])
def test_upload_worker_failure_keeps_error_contract_and_cancellation(
    tmp_path, monkeypatch, cancelled, failure,
):
    async def scenario():
        async with upload_environment(tmp_path, monkeypatch) as env:
            manager, new_upload, files, config = env
            file_id, source_dir = new_upload()
            initial = manager.as_attributes()
            notifications = []
            manager.async_listen(lambda: notifications.append(True))
            entered, release = threading.Event(), threading.Event()
            original_verify = lm._verify_logo_file
            injected = OSError("Synthetic write failure") if failure == "storage" else KeyError(file_id)

            def failing_verify(*args):
                entered.set()
                assert release.wait(5), "Failure release timed out"
                raise injected

            monkeypatch.setattr(lm, "_verify_logo_file", failing_verify)
            request = asyncio.create_task(manager.async_set_upload("Failed", file_id))
            try:
                await wait_thread(entered)
                if cancelled:
                    for _ in range(3):
                        request.cancel()
                        await asyncio.sleep(0)
                    assert not request.done()
                    assert manager._save_lock.locked()
                release.set()
                if cancelled:
                    with pytest.raises(asyncio.CancelledError) as caught:
                        await request
                    worker_error = caught.value.__cause__
                elif failure == "programming":
                    with pytest.raises(KeyError) as caught:
                        await request
                    worker_error = caught.value
                else:
                    with pytest.raises(lm.LogoStorageError) as caught:
                        await request
                    worker_error = caught.value
                if failure == "programming":
                    # Even a KeyError with exactly this file_id is not silently
                    # relabelled invalid_upload when it is a programming bug.
                    assert worker_error is injected
                else:
                    assert isinstance(worker_error, lm.LogoStorageError)
                    assert worker_error.__cause__ is injected
                assert manager.as_attributes() == initial and notifications == []
                assert not Path(manager._store.path).exists()
                assert "_test_stores" not in manager.hass.data
                assert not source_dir.exists() and files == {}
                assert not list(config.rglob(".logo-*"))
                assert not manager._save_lock.locked()
                with pytest.raises(lm.LogoValidationError, match="^invalid_upload$"):
                    await manager.async_set_upload("Retry", file_id)
                monkeypatch.setattr(lm, "_verify_logo_file", original_verify)
                normal_id, normal_dir = new_upload()
                await manager.async_set_upload("Normal", normal_id)
                assert not normal_dir.exists() and files == {}
                assert manager.as_attributes()["handballnet_logo_revision"] == 1
                assert notifications == [True]
            finally:
                release.set()
                await asyncio.gather(request, return_exceptions=True)

    asyncio.run(scenario())
