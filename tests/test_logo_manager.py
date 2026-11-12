"""Central logos: run against HA doubles, real image IO, no network."""
import asyncio
from types import SimpleNamespace

import pytest


def test_ha_corruption_recovery_does_not_turn_retry_into_empty_registry(hass, tmp_path, monkeypatch, caplog):
    from custom_components.handballnet import logo_manager as lm
    damaged = tmp_path / 'invalid-json-fixture'
    damaged.write_text('invalid')
    monkeypatch.setattr(lm.Store, 'path', property(lambda self: str(damaged)))
    async def moved_by_ha(self):
        # Real HA moves malformed JSON to a .corrupt backup and returns None.
        damaged.unlink(missing_ok=True)
        return None
    original_load = lm.Store.async_load
    monkeypatch.setattr(lm.Store, 'async_load', moved_by_ha)
    async def scenario():
        with pytest.raises(lm.LogoStorageError):
            await lm.async_get_logo_manager(hass)
        with pytest.raises(lm.LogoStorageError):
            await lm.async_get_logo_manager(hass)
        assert 'logo' in caplog.text.lower()
        monkeypatch.setattr(lm.Store, 'async_load', original_load)
        hass.data['_test_stores'] = {lm.STORAGE_KEY: {'overrides': {'restored': '/local/a.png'}, 'revision': 2}}
        assert (await lm.async_get_logo_manager(hass)).as_attributes()['handballnet_logo_revision'] == 2
    asyncio.run(scenario())


def test_existing_store_returning_none_is_not_treated_as_first_install(hass, tmp_path, monkeypatch):
    from custom_components.handballnet import logo_manager as lm
    damaged = tmp_path / 'damaged-store-fixture'
    damaged.write_text('{}')
    monkeypatch.setattr(lm.Store, 'path', property(lambda self: str(damaged)), raising=False)
    async def scenario():
        with pytest.raises(lm.LogoStorageError):
            await lm.async_get_logo_manager(hass)
        assert lm.get_logo_manager(hass) is None
        assert damaged.read_text() == '{}'
    asyncio.run(scenario())


def test_broken_listener_does_not_hide_persisted_success_or_other_listeners(hass, caplog):
    from custom_components.handballnet import logo_manager as lm
    async def scenario():
        manager = await lm.async_get_logo_manager(hass)
        events = []
        def broken():
            raise RuntimeError('listener crashed')
        manager.async_listen(broken)
        manager.async_listen(lambda: events.append(manager.as_attributes()))
        await manager.async_set_url('T', '/local/t.png')
        assert len(events) == 1
        assert manager.as_attributes()['handballnet_logo_revision'] == 1
        assert 'listener' in caplog.text.lower()
    asyncio.run(scenario())


def test_cancellation_during_save_finishes_transaction_before_unlocking(hass, monkeypatch):
    from custom_components.handballnet import logo_manager as lm
    async def scenario():
        manager = await lm.async_get_logo_manager(hass)
        saving, release = asyncio.Event(), asyncio.Event()
        save = manager._store.async_save
        async def slow_save(data):
            saving.set()
            await release.wait()
            await save(data)
        monkeypatch.setattr(manager._store, 'async_save', slow_save)
        request = asyncio.create_task(manager.async_set_url('A', '/local/a.png'))
        await saving.wait()
        request.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await request
        # Committed request must be reflected in memory even when caller cancelled.
        assert manager.as_attributes()['handballnet_logo_overrides'] == {'a': '/local/a.png'}
        assert manager.as_attributes()['handballnet_logo_revision'] == 1
        await manager.async_set_url('B', '/local/b.png')
        assert manager.as_attributes()['handballnet_logo_revision'] == 2
    asyncio.run(scenario())


@pytest.mark.parametrize('kind,code', [
    ('svg', 'invalid_image'), ('html', 'invalid_image'), ('gif', 'invalid_image'),
    ('truncated', 'invalid_image'), ('oversize', 'file_too_large'),
    ('wide', 'image_too_large'), ('pixels', 'image_too_large'),
    ('animated', 'invalid_image'),
])
def test_upload_rejects_unsafe_or_excessive_images(hass, tmp_path, monkeypatch, kind, code):
    from contextlib import contextmanager
    from uuid import uuid4
    from PIL import Image
    from custom_components.handballnet import logo_manager as lm
    source = tmp_path / 'input.png'
    if kind in ('svg', 'html'):
        source.write_text('<svg onload="alert(1)"></svg>' if kind == 'svg' else '<html>bad</html>')
    elif kind == 'oversize':
        source.write_bytes(b'x' * (5 * 1024 * 1024 + 1))
    elif kind == 'gif':
        Image.new('RGB', (2, 2)).save(source, format='GIF')
    elif kind == 'wide':
        Image.new('RGB', (4097, 1)).save(source, format='PNG')
    elif kind == 'pixels':
        Image.new('RGB', (4096, 4096)).save(source, format='PNG')
    elif kind == 'animated':
        Image.new('RGB', (2, 2), 'red').save(source, format='WEBP', save_all=True,
            append_images=[Image.new('RGB', (2, 2), 'blue')], duration=100)
    else:
        Image.new('RGB', (2, 2)).save(source, format='PNG')
        source.write_bytes(source.read_bytes()[:-12])
    @contextmanager
    def uploaded(*args):
        try:
            yield source
        finally:
            source.unlink()
    monkeypatch.setattr(lm, 'process_uploaded_file', uploaded)
    async def scenario():
        manager = await lm.async_get_logo_manager(hass)
        with pytest.raises(lm.LogoValidationError, match=code):
            await manager.async_set_upload('T', str(uuid4()))
        assert manager.as_attributes()['handballnet_logo_revision'] == 0
        assert not source.exists()
        assert not tmp_path.joinpath('www').exists()
    asyncio.run(scenario())


@pytest.mark.parametrize('file_id', ['../../etc/passwd', '', None, 'not-a-uuid'])
def test_upload_id_must_be_native_selector_uuid(hass, monkeypatch, file_id):
    from custom_components.handballnet import logo_manager as lm
    def unexpected(*args):
        pytest.fail('Invalid ID must not reach the upload service')
    monkeypatch.setattr(lm, 'process_uploaded_file', unexpected)
    async def scenario():
        manager = await lm.async_get_logo_manager(hass)
        with pytest.raises(lm.LogoValidationError, match='invalid_upload'):
            await manager.async_set_upload('T', file_id)
    asyncio.run(scenario())


def test_missing_upload_is_a_user_correctable_error(hass):
    from uuid import uuid4
    from custom_components.handballnet import logo_manager as lm
    async def scenario():
        manager = await lm.async_get_logo_manager(hass)
        with pytest.raises(lm.LogoValidationError, match='invalid_upload'):
            await manager.async_set_upload('T', str(uuid4()))
    asyncio.run(scenario())


@pytest.mark.parametrize('image_format', ['PNG', 'JPEG', 'WEBP'])
def test_upload_copies_inside_context_reencodes_png_and_keeps_shared_image(hass, tmp_path, monkeypatch, image_format):
    from contextlib import contextmanager
    import hashlib
    from pathlib import Path
    import threading
    from PIL import Image
    from uuid import uuid4
    from custom_components.handballnet import logo_manager as lm

    source = tmp_path / 'untrusted-user-name.html'
    Image.new('RGB', (32, 24), 'red').save(source, format=image_format)
    file_id = str(uuid4())
    main_thread = threading.get_ident()
    @contextmanager
    def uploaded(hass_arg, id_arg):
        assert hass_arg is hass and id_arg == file_id
        assert threading.get_ident() != main_thread
        try:
            yield source
        finally:
            source.unlink()
    monkeypatch.setattr(lm, 'process_uploaded_file', uploaded, raising=False)
    async def scenario():
        manager = await lm.async_get_logo_manager(hass)
        await manager.async_set_upload('Team A', file_id)
        attrs = manager.as_attributes()
        url = attrs['handballnet_logo_overrides']['team a']
        target = Path(hass.config.path('www', 'handballnet', 'logos', url.rsplit('/', 1)[1]))
        assert url == f'/local/handballnet/logos/{hashlib.sha256(target.read_bytes()).hexdigest()}.png'
        with Image.open(target) as image:
            assert image.format == 'PNG' and image.size == (32, 24)
            assert not image.info
        assert not source.exists()
        assert list(target.parent.iterdir()) == [target]
        await manager.async_set_url('Team B', url)
        await manager.async_remove('Team A')
        assert target.exists()
        assert manager.as_attributes()['handballnet_logo_overrides'] == {'team b': url}
    asyncio.run(scenario())


@pytest.mark.parametrize('data', [
    {}, [], {'overrides': {}, 'revision': -1}, {'overrides': {}, 'revision': True},
    {'overrides': [], 'revision': 0},
    {'overrides': {'Team': 'javascript:alert(1)'}, 'revision': 1},
    {'overrides': {'Team': '/a', ' team ': '/b'}, 'revision': 2},
    {'overrides': {}, 'revision': 1, 'unknown_future_data': True},
])
def test_corrupt_payload_is_not_published_or_silently_overwritten(hass, data):
    async def scenario():
        from custom_components.handballnet.logo_manager import (
            async_get_logo_manager, get_logo_manager, LogoStorageError, STORAGE_KEY,
        )
        hass.data['_test_stores'] = {STORAGE_KEY: data}
        with pytest.raises(LogoStorageError):
            await async_get_logo_manager(hass)
        assert get_logo_manager(hass) is None
        assert hass.data['_test_stores'][STORAGE_KEY] == data
    asyncio.run(scenario())


def test_read_failure_is_retryable_not_empty_success(hass, monkeypatch):
    async def scenario():
        from custom_components.handballnet import logo_manager as lm
        load = lm.Store.async_load
        async def fail(self):
            raise OSError('storage unreadable')
        monkeypatch.setattr(lm.Store, 'async_load', fail)
        with pytest.raises(lm.LogoStorageError):
            await lm.async_get_logo_manager(hass)
        assert lm.get_logo_manager(hass) is None
        monkeypatch.setattr(lm.Store, 'async_load', load)
        assert (await lm.async_get_logo_manager(hass))._store.kwargs['atomic_writes'] is True
    asyncio.run(scenario())


@pytest.mark.parametrize('silent', [False, True])
def test_storage_failure_keeps_memory_and_listeners_unchanged(hass, monkeypatch, silent):
    async def scenario():
        from custom_components.handballnet.logo_manager import (
            async_get_logo_manager, LogoStorageError,
        )
        manager = await async_get_logo_manager(hass)
        await manager.async_set_url('A', '/local/a.png')
        before = manager.as_attributes()
        events = []
        manager.async_listen(lambda: events.append(True))
        async def fail(data):
            if not silent:
                raise OSError('disk full')
        monkeypatch.setattr(manager._store, 'async_save', fail)
        with pytest.raises(LogoStorageError):
            await manager.async_set_url('B', '/local/b.png')
        assert manager.as_attributes() == before
        assert not events
    asyncio.run(scenario())


def test_parallel_saves_serialize_and_remove_is_global_without_noop_events(hass, monkeypatch):
    async def scenario():
        from custom_components.handballnet.logo_manager import async_get_logo_manager
        manager = await async_get_logo_manager(hass)
        save = manager._store.async_save
        active = 0
        async def slow_save(data):
            nonlocal active
            active += 1
            assert active == 1
            await asyncio.sleep(0.001)
            await save(data)
            active -= 1
        monkeypatch.setattr(manager._store, 'async_save', slow_save)
        events = []
        manager.async_listen(lambda: events.append(manager.as_attributes()))
        await asyncio.gather(*(
            manager.async_set_url(f'Team {i}', f'/local/{i}.png') for i in range(10)
        ))
        assert len(manager.as_attributes()['handballnet_logo_overrides']) == 10
        assert manager.as_attributes()['handballnet_logo_revision'] == 10
        await manager.async_set_url(' TEAM 0 ', '/local/0.png')
        await manager.async_remove(' TEAM 0 ')
        await manager.async_remove('Team 0')
        assert len(events) == 11
        assert 'team 0' not in manager.as_attributes()['handballnet_logo_overrides']
    asyncio.run(scenario())


@pytest.mark.parametrize('url', [
    'javascript:alert(1)', 'data:image/png;base64,a', '//evil.org/a.png',
    '\\\\evil.org/a.png', 'https://', 'https:evil.org/a.png', 'http:/evil.org',
    'java\nscript:alert(1)', '\x00/local/a.png', '/local/\\evil.png',
    '', '   ', None, 42, {}, 'https://user:password@host/logo.png',
])
def test_unsafe_url_never_changes_store_or_attributes(hass, url):
    async def scenario():
        from custom_components.handballnet.logo_manager import (
            async_get_logo_manager, LogoValidationError,
        )
        manager = await async_get_logo_manager(hass)
        with pytest.raises(LogoValidationError, match='invalid_url'):
            await manager.async_set_url('Known Team', url)
        assert manager.as_attributes()['handballnet_logo_revision'] == 0
        assert '_test_stores' not in hass.data
    asyncio.run(scenario())


@pytest.mark.parametrize('url', [
    'https://example.org/logo.png?q=1&x=2', 'HTTP://example.org/a.jpg',
    '/local/logos/a.png', 'images/a.webp', '../logos/a.png',
])
def test_safe_urls_are_accepted_without_network(hass, url):
    async def scenario():
        from custom_components.handballnet.logo_manager import async_get_logo_manager
        manager = await async_get_logo_manager(hass)
        await manager.async_set_url('T', url)
        assert manager.as_attributes()['handballnet_logo_overrides'] == {'t': url}
    asyncio.run(scenario())


@pytest.mark.parametrize('name', ['', '\ufeff \t', None, 42, 'a\x00b', 'x' * 201])
def test_invalid_team_names_are_rejected(hass, name):
    async def scenario():
        from custom_components.handballnet.logo_manager import (
            async_get_logo_manager, LogoValidationError,
        )
        manager = await async_get_logo_manager(hass)
        with pytest.raises(LogoValidationError, match='invalid_team_name'):
            await manager.async_set_url(name, '/local/a.png')
    asyncio.run(scenario())


@pytest.fixture
def hass(tmp_path):
    async def executor(func, *args):
        return await asyncio.to_thread(func, *args)

    return SimpleNamespace(
        data={},
        config=SimpleNamespace(path=lambda *parts: str(tmp_path.joinpath(*parts))),
        async_add_executor_job=executor,
    )


def test_shared_loaded_singleton_and_detached_snapshot(hass):
    async def scenario():
        from custom_components.handballnet.logo_manager import (
            async_get_logo_manager, get_logo_manager,
        )
        assert get_logo_manager(hass) is None
        first, second = await asyncio.gather(
            async_get_logo_manager(hass), async_get_logo_manager(hass)
        )
        assert first is second is hass.data['handballnet']['_logo_manager']
        assert get_logo_manager(hass) is first
        assert first.as_attributes() == {
            'handballnet_logo_overrides': {}, 'handballnet_logo_revision': 0,
        }
        snapshot = first.as_attributes()
        snapshot['handballnet_logo_overrides']['not persisted'] = '/local/x.png'
        assert first.as_attributes()['handballnet_logo_overrides'] == {}
    asyncio.run(scenario())


def test_url_save_normalizes_name_persists_and_notifies_after_save(hass):
    async def scenario():
        from custom_components.handballnet.logo_manager import async_get_logo_manager
        manager = await async_get_logo_manager(hass)
        events = []
        unsubscribe = manager.async_listen(lambda: events.append(
            (manager.as_attributes(), dict(hass.data['_test_stores']))
        ))
        await manager.async_set_url('  SG\u00a0 Straße  I  ', ' https://example.org/logo.png ')
        attrs = manager.as_attributes()
        assert attrs == {
            'handballnet_logo_overrides': {'sg straße i': 'https://example.org/logo.png'},
            'handballnet_logo_revision': 1,
        }
        assert len(events) == 1
        assert next(iter(events[0][1].values())) == {
            'overrides': attrs['handballnet_logo_overrides'], 'revision': 1,
        }
        hass.data['handballnet'].pop('_logo_manager')
        restored = await async_get_logo_manager(hass)
        assert restored.as_attributes() == attrs
        unsubscribe()
        await manager.async_set_url('SG Straße I', '/local/other.png')
        assert len(events) == 1
    asyncio.run(scenario())
