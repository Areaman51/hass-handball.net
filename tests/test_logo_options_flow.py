"""Native options UX and safe shared-logo editing, without HA network access."""
import asyncio
from types import SimpleNamespace

import probatio as p
import pytest


@pytest.mark.parametrize('source_kind', ['url', 'upload'])
def test_explicit_same_source_save_bumps_revision_for_failed_image_retry(flow, tmp_path, monkeypatch, source_kind):
    from custom_components.handballnet import logo_manager as lm
    from contextlib import contextmanager
    from uuid import uuid4
    from PIL import Image

    @contextmanager
    def uploaded(*args):
        source = tmp_path / 'retry-image.png'
        Image.new('RGB', (8, 8), '#159aaf').save(source, format='PNG')
        try:
            yield source
        finally:
            source.unlink()

    monkeypatch.setattr(lm, 'process_uploaded_file', uploaded)

    async def save():
        if source_kind == 'url':
            return await flow.async_step_logo_url({'url': '/local/same.png'})
        return await flow.async_step_logo_upload({'file_id': str(uuid4())})

    async def scenario():
        await flow.async_step_logos({'team_name': 'SG Beispielstadt'})
        await save()
        manager = await lm.async_get_logo_manager(flow.hass)
        before = manager.as_attributes()['handballnet_logo_revision']
        result = await save()
        assert result['reason'] == 'logo_saved'
        assert manager.as_attributes()['handballnet_logo_revision'] == before + 1

    asyncio.run(scenario())


def test_url_dialog_surfaces_load_error_as_translated_form_error(flow, monkeypatch):
    from custom_components.handballnet import options_flow as of
    async def scenario():
        await flow.async_step_logos({'team_name': 'T'})
        async def fail(hass):
            raise of.LogoStorageError('storage_error')
        monkeypatch.setattr(of, 'async_get_logo_manager', fail)
        result = await flow.async_step_logo_url({'url': '/local/a.png'})
        assert result['type'] == 'form'
        assert result['errors']['base'] == 'storage_error'
    asyncio.run(scenario())


@pytest.mark.parametrize('language', ['de', 'en'])
def test_native_step_titles_are_static_and_team_name_is_in_description(language):
    import json
    from pathlib import Path

    translation = json.loads((Path(__file__).parents[1] / 'custom_components' /
        'handballnet' / 'translations' / f'{language}.json').read_text())
    for step in ['logo_action', 'logo_url', 'logo_upload', 'logo_restore']:
        data = translation['options']['step'][step]
        assert '{' not in data['title'], 'HA interpolates description placeholders, not step titles'
        assert '{team_name}' in data['description']


@pytest.mark.parametrize('language', ['de', 'en'])
def test_translations_cover_menus_forms_errors_and_confirmations(language):
    import json
    from pathlib import Path
    translation = json.loads((Path(__file__).parents[1] / 'custom_components' /
        'handballnet' / 'translations' / f'{language}.json').read_text())
    options = translation['options']
    assert set(options['step']['init']['menu_options']) == {'intervals', 'logos'}
    assert set(options['step']['logo_action']['menu_options']) == {'logo_url', 'logo_upload', 'logo_restore'}
    for step, fields in {
        'intervals': {'update_interval', 'update_interval_live'},
        'logos': {'team_name'}, 'logo_url': {'url'}, 'logo_upload': {'file_id'},
        'logo_restore': {'confirm'},
    }.items():
        assert options['step'][step]['title']
        assert options['step'][step]['description']
        assert fields <= options['step'][step]['data'].keys()
    assert {'invalid_interval', 'invalid_team_name', 'invalid_url', 'invalid_upload',
            'invalid_image', 'image_too_large', 'file_too_large', 'storage_error',
            'confirmation_required'} <= options['error'].keys()
    assert {'logo_saved', 'logo_restored', 'storage_error'} <= options['abort'].keys()
    assert translation['config']['step']['team']['data']['team_id']


def test_native_upload_and_confirmed_restore_leave_intervals_untouched(flow, tmp_path, monkeypatch):
    from contextlib import contextmanager
    from uuid import uuid4
    from PIL import Image
    from custom_components.handballnet import logo_manager as lm
    source = tmp_path / 'input-image'
    Image.new('RGBA', (8, 8), (20, 40, 60, 128)).save(source, format='PNG')
    file_id = str(uuid4())
    @contextmanager
    def uploaded(hass, actual_file_id):
        assert actual_file_id == file_id
        try:
            yield source
        finally:
            source.unlink()
    monkeypatch.setattr(lm, 'process_uploaded_file', uploaded)
    async def scenario():
        before = dict(flow.config_entry.options)
        await flow.async_step_logos({'team_name': 'Guest'})
        form = await flow.async_step_logo_upload()
        file_selector = next(iter(form['data_schema'].schema.values()))
        assert file_selector.serialize() == {'selector': {'file': {
            'accept': 'image/png,image/jpeg,image/webp',
        }}}
        result = await flow.async_step_logo_upload(form['data_schema']({'file_id': file_id}))
        assert result == {'type': 'abort', 'reason': 'logo_saved'}
        manager = await lm.async_get_logo_manager(flow.hass)
        assert manager.as_attributes()['handballnet_logo_overrides']['guest'].startswith('/local/handballnet/logos/')
        form = await flow.async_step_logo_restore()
        assert isinstance(form['data_schema'], p.Schema)
        assert manager.as_attributes()['handballnet_logo_revision'] == 1
        result = await flow.async_step_logo_restore({'confirm': False})
        assert result['errors']['confirm'] == 'confirmation_required'
        result = await flow.async_step_logo_restore({'confirm': True})
        assert result == {'type': 'abort', 'reason': 'logo_restored'}
        assert manager.as_attributes() == {
            'handballnet_logo_overrides': {}, 'handballnet_logo_revision': 2,
        }
        assert flow.config_entry.options == before
    asyncio.run(scenario())


def test_upload_and_storage_errors_stay_in_their_form(flow, monkeypatch):
    from uuid import uuid4
    from custom_components.handballnet import logo_manager as lm
    async def scenario():
        await flow.async_step_logos({'team_name': 'Guest'})
        result = await flow.async_step_logo_upload({'file_id': str(uuid4())})
        assert result['errors']['file_id'] == 'invalid_upload'
        manager = await lm.async_get_logo_manager(flow.hass)
        async def fail(*args, **kwargs):
            raise lm.LogoStorageError('storage_error')
        monkeypatch.setattr(manager, 'async_set_upload', fail)
        result = await flow.async_step_logo_upload({'file_id': str(uuid4())})
        assert result['errors']['base'] == 'storage_error'
        monkeypatch.setattr(manager, 'async_remove', fail)
        result = await flow.async_step_logo_restore({'confirm': True})
        assert result['errors']['base'] == 'storage_error'
    asyncio.run(scenario())


def test_logo_selection_uses_all_entries_and_saved_names_without_mutating_api(flow):
    import copy
    from custom_components.handballnet.logo_manager import async_get_logo_manager
    first = flow.config_entry
    first.runtime_data = SimpleNamespace(data={'teams': {'a': {
        'team_name': 'Club A', 'matches': [{'homeTeam': {'name': 'Club A'},
                                          'awayTeam': {'name': 'Guest A'}}],
        'next_match': {'home_team': {'name': 'Club A'}, 'away_team': {'name': 'Next Guest'}},
    }}})
    second = SimpleNamespace(runtime_data=SimpleNamespace(data={'tournament': {
        'tournament_info': {'name': 'Not a team'},
        'table_rows': [{'team_name': 'Tournament Guest'}],
        'matches': [{'homeTeam': {'name': 'Match Guest'}, 'awayTeam': {'name': 'club a'}}],
    }}))
    flow.hass.config_entries.async_entries = lambda domain: [first, second, SimpleNamespace()]
    before = copy.deepcopy(first.runtime_data.data)
    async def scenario():
        manager = await async_get_logo_manager(flow.hass)
        await manager.async_set_url('Previously Custom', '/local/old.png')
        form = await flow.async_step_logos()
        assert form['step_id'] == 'logos' and isinstance(form['data_schema'], p.Schema)
        selector = next(iter(form['data_schema'].schema.values()))
        assert selector.config['custom_value'] is True
        assert set(selector.config['options']) == {
            'Club A', 'Guest A', 'Next Guest', 'Tournament Guest', 'Match Guest', 'previously custom',
        }
        selected = form['data_schema']({'team_name': 'Manual Club'})
        result = await flow.async_step_logos(selected)
        assert result['type'] == 'menu' and result['step_id'] == 'logo_action'
        assert result['menu_options'] == ['logo_url', 'logo_upload', 'logo_restore']
        assert first.runtime_data.data == before
    asyncio.run(scenario())


def test_url_edit_saves_shared_manager_but_never_replaces_entry_options(flow):
    import copy
    from custom_components.handballnet.logo_manager import async_get_logo_manager
    before = copy.deepcopy(flow.config_entry.options)
    async def scenario():
        await flow.async_step_logos({'team_name': 'Own Club'})
        result = await flow.async_step_logo_url({'url': 'javascript:bad'})
        assert result['errors']['url'] == 'invalid_url'
        result = await flow.async_step_logo_url({'url': '/local/own.png'})
        assert result == {'type': 'abort', 'reason': 'logo_saved'}
        manager = await async_get_logo_manager(flow.hass)
        assert manager.as_attributes()['handballnet_logo_overrides'] == {'own club': '/local/own.png'}
        await flow.async_step_logos({'team_name': ' OWN CLUB '})
        form = await flow.async_step_logo_url()
        assert form['data_schema']({}) == {'url': '/local/own.png'}
        assert flow.config_entry.options == before
    asyncio.run(scenario())


@pytest.fixture
def flow(tmp_path):
    from custom_components.handballnet.options_flow import async_get_options_flow
    entry = SimpleNamespace(
        entry_id='entry-a', data={'update_interval': 7200, 'update_interval_live': 30},
        options={'update_interval': 1800, 'keep_existing': {'a': 1}},
    )
    async def executor(func, *args):
        return await asyncio.to_thread(func, *args)
    handler = async_get_options_flow(entry)
    handler.config_entry = entry  # The existing no-HA stub only; not production code.
    handler.hass = SimpleNamespace(
        data={}, config=SimpleNamespace(path=lambda *p: str(tmp_path.joinpath(*p))),
        async_add_executor_job=executor,
        config_entries=SimpleNamespace(async_entries=lambda domain: [entry]),
    )
    return handler


def test_root_menu_and_native_interval_edit_preserve_unrelated_options(flow):
    async def scenario():
        root = await flow.async_step_init()
        assert root['type'] == 'menu'
        assert root['menu_options'] == ['intervals', 'logos']
        form = await flow.async_step_intervals()
        assert isinstance(form['data_schema'], p.Schema)
        assert form['data_schema']({}) == {'update_interval': 1800, 'update_interval_live': 30}
        result = await flow.async_step_intervals({'update_interval': 900, 'update_interval_live': 15})
        assert result['data'] == {
            'update_interval': 900, 'update_interval_live': 15, 'keep_existing': {'a': 1},
        }
        assert flow.config_entry.options == {'update_interval': 1800, 'keep_existing': {'a': 1}}
    asyncio.run(scenario())


@pytest.mark.parametrize('value', [0, -1, True, 1.5, 'bad'])
def test_invalid_interval_is_a_form_error(flow, value):
    async def scenario():
        result = await flow.async_step_intervals({'update_interval': value, 'update_interval_live': 15})
        assert result['type'] == 'form'
        assert result['errors']['base'] == 'invalid_interval'
    asyncio.run(scenario())
