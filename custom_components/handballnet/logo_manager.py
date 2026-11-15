"""Shared, persistent logo overrides; never mutate the API's original data."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import stat
import warnings
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.helpers.storage import Store
from PIL import Image, ImageOps, UnidentifiedImageError

from .const import DOMAIN


class LogoValidationError(ValueError):
    """User-correctable error, with a translated options-flow error code."""

    @property
    def code(self) -> str:
        return str(self)


class LogoStorageError(RuntimeError):
    """Durable storage could not be loaded or confirmed; do not report success."""


_JS_WHITESPACE = r"[\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+"


def normalize_team_name(name: str) -> str:
    """Match card trim/whitespace collapse/lower (intentionally not casefold)."""
    if not isinstance(name, str):
        raise LogoValidationError("invalid_team_name")
    normalized = re.sub(_JS_WHITESPACE, " ", name).strip(" ").lower()
    if not normalized or len(normalized) > 200 or re.search(r"[\x00-\x1f\x7f]", normalized):
        raise LogoValidationError("invalid_team_name")
    return normalized


def validate_logo_url(value: str) -> str:
    """HTTP(S) and relative URLs only; no downloads, credentials or controls."""
    if not isinstance(value, str) or re.search(r"[\x00-\x1f\x7f\\]", value):
        raise LogoValidationError("invalid_url")
    url = re.sub(rf"^{_JS_WHITESPACE}|{_JS_WHITESPACE}$", "", value)
    if not url or len(url) > 4096 or url.startswith("//"):
        raise LogoValidationError("invalid_url")
    try:
        parsed = urlsplit(url)
        if re.match(r"^[a-z][a-z\d+.-]*:", url, re.I):
            if not re.match(r"^https?://[^/]", url, re.I):
                raise ValueError
            if not parsed.hostname or parsed.username is not None or parsed.password is not None:
                raise ValueError
            if re.search(r"[\s<>%]", parsed.hostname):
                raise ValueError
            parsed.port  # Validate port syntax too.
        elif parsed.scheme or parsed.netloc:
            raise ValueError
    except ValueError as err:
        raise LogoValidationError("invalid_url") from err
    return url


STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.logos"
_MANAGER_KEY = "_logo_manager"
_LISTENERS_KEY = "_logo_manager_listeners"
_LOAD_LOCK_KEY = "_logo_manager_load_lock"
_DAMAGED_STORE_KEY = "_logo_manager_damaged_store"
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_DIMENSION = 4096
MAX_PIXELS = 16_000_000
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_LOGGER = logging.getLogger(__name__)
_UPLOAD_DIR_FD_OPERATIONS = frozenset((os.open, os.mkdir, os.link, os.unlink, os.stat))
_UPLOAD_NOFOLLOW_OPERATIONS = frozenset((os.link, os.stat))


@contextmanager
def _open_logo_directory(config_path: str) -> Iterator[int]:
    """Pin each directory below the trusted HA config anchor without symlinks."""
    if (
        os.name != "posix"
        or not all(getattr(os, flag, 0) for flag in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK"))
        or not _UPLOAD_DIR_FD_OPERATIONS.issubset(getattr(os, "supports_dir_fd", ()))
        or not _UPLOAD_NOFOLLOW_OPERATIONS.issubset(getattr(os, "supports_follow_symlinks", ()))
    ):
        raise LogoStorageError("storage_error")
    with ExitStack() as stack:
        directory_fd = os.open(config_path, os.O_RDONLY | os.O_DIRECTORY)
        stack.callback(os.close, directory_fd)
        chain = []
        for component in ("www", DOMAIN, "logos"):
            parent_fd = directory_fd
            try:
                os.mkdir(component, dir_fd=directory_fd)
            except FileExistsError:
                pass
            directory_fd = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=directory_fd,
            )
            stack.callback(os.close, directory_fd)
            chain.append((parent_fd, component, directory_fd))
        yield directory_fd
        # Descriptor-relative operations cannot be redirected by path replacement.
        # Also refuse success for a directory that visibly moved during the write.
        for parent_fd, component, child_fd in chain:
            current = os.stat(component, dir_fd=parent_fd, follow_symlinks=False)
            pinned = os.fstat(child_fd)
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
                raise LogoStorageError("storage_error")


def _verify_logo_file(directory_fd: int, name: str, digest: str) -> None:
    """Only reuse a bounded regular file, never a symlink or blocking FIFO."""
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_OUTPUT_BYTES:
            raise LogoStorageError("storage_error")
        with os.fdopen(fd, "rb", closefd=False) as existing:
            contents = existing.read(MAX_OUTPUT_BYTES + 1)
        if len(contents) > MAX_OUTPUT_BYTES or hashlib.sha256(contents).hexdigest() != digest:
            raise LogoStorageError("storage_error")
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise LogoStorageError("storage_error")
    finally:
        os.close(fd)


class LogoManager:
    """One loaded manager per Home Assistant instance."""

    def __init__(self, hass):
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True)
        self._overrides: dict[str, str] = {}
        self._revision = 0
        # Subscriptions outlive failed load attempts and belong to this HA instance.
        self._listeners: set[Callable[[], None]] = hass.data.setdefault(DOMAIN, {}).setdefault(_LISTENERS_KEY, set())
        self._save_lock = asyncio.Lock()

    async def _async_load(self) -> None:
        """Fail closed on malformed data, leaving the Store untouched for repair."""
        try:
            existed = await self.hass.async_add_executor_job(Path(self._store.path).exists)
            # Read-only loading prevents HA's automatic minor-version migration
            # from rewriting a payload before our validation has accepted it.
            data = await Store(self.hass, STORAGE_VERSION, STORAGE_KEY, read_only=True).async_load()
            if data is None:
                if existed or self.hass.data[DOMAIN].get(_DAMAGED_STORE_KEY):
                    # HA can move corrupt JSON aside and return None. Keep the
                    # registry unavailable on subsequent attempts in this session
                    # instead of silently accepting an empty replacement store.
                    self.hass.data[DOMAIN][_DAMAGED_STORE_KEY] = True
                    raise ValueError("Existing logo store returned no data; check HA storage repairs")
                return
            if not isinstance(data, dict) or set(data) != {"overrides", "revision"}:
                raise ValueError("Invalid logo store structure")
            revision, overrides = data["revision"], data["overrides"]
            if type(revision) is not int or revision < 0 or not isinstance(overrides, dict):
                raise ValueError("Invalid logo store types")
            validated = {}
            for name, url in overrides.items():
                name = normalize_team_name(name)
                if name in validated:
                    raise ValueError("Conflicting normalized logo names")
                validated[name] = validate_logo_url(url)
            self._overrides, self._revision = validated, revision
            self.hass.data[DOMAIN].pop(_DAMAGED_STORE_KEY, None)
        except Exception as err:
            _LOGGER.exception("Unable to load the central logo registry; existing data was not overwritten")
            raise LogoStorageError("storage_error") from err

    def async_listen(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Subscribe synchronously; callbacks take no arguments, after storage."""
        self._listeners.add(callback)
        return lambda: self._listeners.discard(callback)

    async def async_set_url(self, team_name: str, url: str, *, retry: bool = False) -> None:
        team, url = normalize_team_name(team_name), validate_logo_url(url)
        async with self._save_lock:
            await self._async_save({**self._overrides, team: url}, retry=retry)

    async def async_remove(self, team_name: str) -> None:
        """Restore API originals globally; never delete possibly shared files."""
        team = normalize_team_name(team_name)
        async with self._save_lock:
            overrides = dict(self._overrides)
            overrides.pop(team, None)
            await self._async_save(overrides)

    async def async_set_upload(self, team_name: str, file_id: str, *, retry: bool = False) -> None:
        """Consume HA's temporary upload entirely on the executor."""
        team = normalize_team_name(team_name)
        try:
            if not isinstance(file_id, str):
                raise ValueError
            UUID(file_id)
        except ValueError as err:
            raise LogoValidationError("invalid_upload") from err
        async with self._save_lock:
            job = asyncio.ensure_future(
                self.hass.async_add_executor_job(self._process_upload, file_id)
            )
            try:
                url = await asyncio.shield(job)
            except asyncio.CancelledError as cancelled:
                # The worker cannot be cancelled: keep its native upload context
                # (including cleanup) serialized, but never persist this flow.
                while not job.done():
                    try:
                        await asyncio.wait((job,))
                    except asyncio.CancelledError:
                        continue
                try:
                    job.result()
                except Exception as err:
                    raise cancelled from err
                raise
            await self._async_save({**self._overrides, team: url}, retry=retry)

    def _process_upload(self, file_id: str) -> str:
        try:
            return self._consume_upload(file_id)
        except LogoValidationError:
            raise
        except ValueError as err:
            raise LogoValidationError("invalid_upload") from err
        except (OSError, NotImplementedError) as err:
            raise LogoStorageError("storage_error") from err

    def _consume_upload(self, file_id: str) -> str:
        with process_uploaded_file(self.hass, file_id) as source:
            with source.open("rb") as file:
                raw = file.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise LogoValidationError("file_too_large")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(raw)) as image:
                        if image.format not in {"PNG", "JPEG", "WEBP"} or getattr(image, "n_frames", 1) != 1:
                            raise LogoValidationError("invalid_image")
                        width, height = image.size
                        if max(width, height) > MAX_DIMENSION or width * height > MAX_PIXELS:
                            raise LogoValidationError("image_too_large")
                        image.verify()
                    with Image.open(BytesIO(raw)) as image:
                        pixels = ImageOps.exif_transpose(image).convert("RGBA")
                        clean = Image.new("RGBA", pixels.size)
                        clean.paste(pixels)
                        output = BytesIO()
                        clean.save(output, format="PNG")
                contents = output.getvalue()
            except (Image.DecompressionBombError, Image.DecompressionBombWarning) as err:
                raise LogoValidationError("image_too_large") from err
            except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as err:
                if isinstance(err, LogoValidationError):
                    raise
                raise LogoValidationError("invalid_image") from err
            if len(contents) > MAX_OUTPUT_BYTES:
                raise LogoValidationError("file_too_large")
            digest = hashlib.sha256(contents).hexdigest()
            with _open_logo_directory(self.hass.config.path()) as directory_fd:
                target = f"{digest}.png"
                temporary = f".logo-{uuid4().hex}"
                temp_fd = os.open(
                    temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=directory_fd,
                )
                try:
                    with os.fdopen(temp_fd, "wb", closefd=False) as temp:
                        temp.write(contents)
                        temp.flush()
                        os.fsync(temp.fileno())
                    try:
                        # Relative to the pinned directory even if its path changes.
                        # link() never overwrites a possibly shared existing asset.
                        os.link(temporary, target, src_dir_fd=directory_fd,
                                dst_dir_fd=directory_fd, follow_symlinks=False)
                    except FileExistsError:
                        pass
                    # Check the published name as well as existing collisions: a
                    # directory writer may have exchanged the temporary source.
                    _verify_logo_file(directory_fd, target, digest)
                finally:
                    try:
                        os.close(temp_fd)
                    finally:
                        os.unlink(temporary, dir_fd=directory_fd)
            return f"/local/{DOMAIN}/logos/{digest}.png"

    async def _async_save(self, overrides: dict[str, str], *, retry: bool = False) -> None:
        # Explicit UI saves may retry a formerly broken source without changing
        # its URL. Ordinary internal no-ops must not cause network retry loops.
        if overrides == self._overrides and not retry:
            return
        # Once persistence starts, hold the caller's save lock until commit and
        # publication finish even if its flow/task is cancelled in the meantime.
        task = asyncio.create_task(self._async_commit(overrides))
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            task.result()
            raise

    async def _async_commit(self, overrides: dict[str, str]) -> None:
        revision = self._revision + 1
        payload = {"overrides": overrides, "revision": revision}
        try:
            await self._store.async_save(payload)
            # HA Store may log a WriteError rather than propagate it. A fresh
            # Store reads durable storage, not this writer's pending payload.
            confirmed = await Store(self.hass, STORAGE_VERSION, STORAGE_KEY, read_only=True).async_load()
            if confirmed != payload:
                raise LogoStorageError("storage_error")
        except Exception as err:
            _LOGGER.exception("Unable to confirm durable storage for the central logo registry")
            raise LogoStorageError("storage_error") from err
        self._overrides, self._revision = overrides, revision
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Central logo listener failed after a successful save")

    def as_attributes(self) -> dict:
        """Return a detached snapshot containing only safe overrides and revision."""
        return {
            "handballnet_logo_overrides": dict(self._overrides),
            "handballnet_logo_revision": self._revision,
        }


def async_listen_logo_changes(hass, callback: Callable[[], None]) -> Callable[[], None]:
    """Subscribe synchronously even while the optional store is unavailable."""
    listeners = hass.data.setdefault(DOMAIN, {}).setdefault(_LISTENERS_KEY, set())
    listeners.add(callback)
    return lambda: listeners.discard(callback)


def get_logo_manager(hass) -> LogoManager | None:
    """Return the already loaded manager without performing IO."""
    return hass.data.get(DOMAIN, {}).get(_MANAGER_KEY)


async def async_get_logo_manager(hass) -> LogoManager:
    """Load exactly one shared manager, including concurrent first callers."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    lock = domain_data.setdefault(_LOAD_LOCK_KEY, asyncio.Lock())
    async with lock:
        if (manager := get_logo_manager(hass)) is None:
            manager = LogoManager(hass)
            await manager._async_load()
            domain_data[_MANAGER_KEY] = manager
        return manager
