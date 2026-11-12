"""Native HA 2026.11 integration fixture; loopback, no real HA or API access."""
from __future__ import annotations
import argparse,asyncio,hashlib,io,json,logging,os,pathlib,shutil,signal,socket,tempfile,uuid
from types import MappingProxyType
import aiohttp
from PIL import Image
from homeassistant import auth,loader
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components import onboarding
from homeassistant.components.http.config import async_get_and_load_store
from homeassistant.setup import async_setup_component

REPO=pathlib.Path(__file__).resolve().parents[1]
WORK=pathlib.Path(os.environ.get('HANDBALLNET_NATIVE_WORKSPACE') or tempfile.mkdtemp(prefix='handballnet-native-',dir=os.environ.get('TMPDIR')))
WORK.mkdir(parents=True,exist_ok=True)
async def main(serve):
    configdir=WORK/('native-central-'+uuid.uuid4().hex)
    (configdir/'custom_components').mkdir(parents=True)
    (configdir/'custom_components/__init__.py').write_text('')
    shutil.copytree(REPO/'custom_components/handballnet',configdir/'custom_components/handballnet',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    assert not (configdir/'www').exists()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    providers=[{'type':'trusted_networks','trusted_networks':['127.0.0.1/32'],'allow_bypass_login':True}]
    hass=HomeAssistant(str(configdir));loader.async_setup(hass)
    store=onboarding.OnboardingStorage(hass,onboarding.STORAGE_VERSION,onboarding.STORAGE_KEY,private=True)
    await store.async_save({'done':list(onboarding.STEPS)})
    cfg={'homeassistant':{'name':'Lokaler Logo-Test','latitude':0,'longitude':0,'elevation':0,'unit_system':'metric','time_zone':'Europe/Berlin','country':'DE','auth_providers':providers},'http':{'server_host':'127.0.0.1','server_port':port},'api':{},'frontend':{},'config':{},'logger':{'default':'warning'}}
    checks=[]
    def passed(name,**data):
        checks.append({'name':name,'passed':True,**data});print(json.dumps(checks[-1]),flush=True)
    try:
        assert await async_from_config_dict(cfg,hass) is hass
        user=await hass.auth.async_create_user('Lokaler Logo-Test',group_ids=[GROUP_ID_ADMIN],local_only=True)
        await hass.async_start();await hass.async_block_till_done()
        await (await async_get_and_load_store(hass)).async_promote_pending()
        assert hass.http.server_port==port
        local_routes=[resource.canonical for resource in hass.http.app.router.resources() if resource.canonical.startswith('/local')]
        print('NATIVE_LOCAL_ROUTE_BASELINE',json.dumps({'www_created_during_native_bootstrap':(configdir/'www').exists(),'local_routes':local_routes}),flush=True)
        assert await async_setup_component(hass,'handballnet',{})
        from custom_components.handballnet.logo_manager import async_get_logo_manager
        manager=await async_get_logo_manager(hass)
        original='/static/icons/favicon-192x192.png'
        data={'teams':{'T':{'team_name':'SG Beispielstadt','next_match':{'home_team':{'name':'SG Beispielstadt','logo':original},'away_team':{'name':'TSV Gast','logo':original},'starts_at_formatted':'Samstag, 12:00'},'live_matches':[]}},'tournament':{'table_rows':[{'team_name':'SG Beispielstadt','team_logo':original,'position':1,'points':2},{'team_name':'TSV Gast','team_logo':original,'position':2,'points':0}],'matches':[{'id':'M','startsAt':1900000000000,'homeTeam':{'name':'SG Beispielstadt'},'awayTeam':{'name':'TSV Gast'}}]}}
        entries=[]
        for title,entry_data in [('Team-Fixture',{'entity_type':'team','team_id':'T','team_name':'SG Beispielstadt'}),('Liga-Fixture',{'entity_type':'tournament','tournament_id':'Q','tournament_name':'Beispielliga'})]:
            entry=ConfigEntry(version=1,minor_version=1,domain='handballnet',title=title,data=entry_data,options={'update_interval':7200,'update_interval_live':20,'preserved_option':'fixture'},source='user',unique_id=None,discovery_keys=MappingProxyType({}),subentries_data=[])
            hass.config_entries._entries[entry.entry_id]=entry
            coordinator=DataUpdateCoordinator(hass,logging.getLogger('native-logo-fixture'),name=title,config_entry=None)
            coordinator.async_set_updated_data(data);entry.runtime_data=coordinator;entries.append(entry)
        hass.config_entries._async_schedule_save()
        from custom_components.handballnet.sensors.team.next_match_sensor import HandballNextMatchSensor
        from custom_components.handballnet.sensors.team.live_ticker_sensor import HandballLiveTickerSensor
        from custom_components.handballnet.sensors.tournament.tournament_table_sensor import HandballTournamentTableSensor
        from custom_components.handballnet.sensors.tournament.tournament_schedule_sensor import HandballTournamentScheduleSensor
        entities=[HandballNextMatchSensor(entries[0].runtime_data,entries[0],'T','SG Beispielstadt'),HandballLiveTickerSensor(entries[0].runtime_data,entries[0],'T','SG Beispielstadt'),HandballTournamentTableSensor(entries[1].runtime_data,entries[1],'Q'),HandballTournamentScheduleSensor(entries[1].runtime_data,entries[1],'Q')]
        ids=['sensor.logo_test_next','sensor.logo_test_live','sensor.logo_test_table','sensor.logo_test_schedule']
        for entity,eid in zip(entities,ids):entity.entity_id=eid
        component=EntityComponent(logging.getLogger('native-logo-fixture'),'sensor',hass)
        await component.async_add_entities(entities)
        await hass.async_block_till_done()
        assert all(hass.states.get(eid) is not None for eid in ids)
        passed('native sensor entities registered',entities=ids)
        before_options=[dict(e.options) for e in entries]
        refresh=await hass.auth.async_create_refresh_token(user,client_id=base+'/')
        token=hass.auth.async_create_access_token(refresh)
        async with aiohttp.ClientSession(headers={'Authorization':'Bearer '+token}) as client:
            async def new_flow(entry):
                result=await hass.config_entries.options.async_init(entry.entry_id)
                assert result['type']=='menu' and result['menu_options']==['intervals','logos']
                result=await hass.config_entries.options.async_configure(result['flow_id'],{'next_step_id':'logos'})
                assert result['step_id']=='logos'
                result=await hass.config_entries.options.async_configure(result['flow_id'],{'team_name':'SG Beispielstadt'})
                assert result['step_id']=='logo_action'
                return result
            result=await new_flow(entries[0]);result=await hass.config_entries.options.async_configure(result['flow_id'],{'next_step_id':'logo_url'})
            assert result['step_id']=='logo_url'
            result=await hass.config_entries.options.async_configure(result['flow_id'],{'url':'/local/test-url.png'})
            assert result['type']=='abort' and result['reason']=='logo_saved'
            assert [dict(e.options) for e in entries]==before_options
            assert all(hass.states.get(eid).attributes['handballnet_logo_overrides']=={'sg beispielstadt':'/local/test-url.png'} for eid in ids)
            assert entries[0].runtime_data.data['teams']['T']['next_match']['home_team']['logo']==original
            passed('native options URL applies immediately across team and tournament; originals/options preserved')
            raw=io.BytesIO();Image.new('RGB',(80,45),'#159aaf').save(raw,format='PNG')
            form=aiohttp.FormData();form.add_field('file',raw.getvalue(),filename='synthetic-logo.png',content_type='image/png')
            async with client.post(base+'/api/file_upload',data=form) as response:
                assert response.status==200;upload=await response.json()
            result=await new_flow(entries[1]);result=await hass.config_entries.options.async_configure(result['flow_id'],{'next_step_id':'logo_upload'})
            assert result['step_id']=='logo_upload'
            result=await hass.config_entries.options.async_configure(result['flow_id'],{'file_id':upload['file_id']})
            assert result['type']=='abort' and result['reason']=='logo_saved'
            url=manager.as_attributes()['handballnet_logo_overrides']['sg beispielstadt']
            assert all(hass.states.get(eid).attributes['handballnet_logo_overrides']['sg beispielstadt']==url for eid in ids)
            async with client.get(base+url) as response:
                body=await response.read()
                assert response.status==200,{'image_status':response.status,'image_url':url,'no_www_at_frontend_start':True}
                assert response.headers['Content-Type'].startswith('image/png')
                assert hashlib.sha256(body).hexdigest() in url
            passed('native upload persists, is served immediately on first www creation and reaches all four source entities',image_url=url)
            result=await new_flow(entries[0]);result=await hass.config_entries.options.async_configure(result['flow_id'],{'next_step_id':'logo_restore'})
            assert result['step_id']=='logo_restore'
            result=await hass.config_entries.options.async_configure(result['flow_id'],{'confirm':True})
            assert result['type']=='abort' and result['reason']=='logo_restored'
            assert all(hass.states.get(eid).attributes['handballnet_logo_overrides']=={} for eid in ids)
            assert [dict(e.options) for e in entries]==before_options
            passed('native confirmed reset updates all source entities; options preserved')
        report={'checks':checks,'config_dir':str(configdir),'base':base,'entry_ids':[e.entry_id for e in entries],'entity_ids':ids,'live_ha_contacted':False,'github_modified':False}
        (WORK/'native-central-report.json').write_text(json.dumps(report,indent=2));print('NATIVE_E2E_PASSED',len(checks),flush=True)
        if serve:
            stop=asyncio.Event();loop=asyncio.get_running_loop()
            for signum in [signal.SIGTERM,signal.SIGINT]:loop.add_signal_handler(signum,stop.set)
            print('NATIVE_TEST_UI_READY',base,flush=True)
            await stop.wait()
    finally:
        await hass.async_stop(force=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--serve',action='store_true');args=parser.parse_args();asyncio.run(main(args.serve))
