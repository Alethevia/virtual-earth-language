#!/usr/bin/env python3
"""Versioned GHCNh migration; preserve legacy experiments and all negative results."""
import argparse
import io
import json
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from threadpoolctl import threadpool_limits
import quant_geo_phase1 as q
import verify_intervals as vi

ROOT = q.ROOT / 'ghcnh_v1'
BASE = 'https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/'
ELEMENTS = {'temperature': 'temp', 'dew_point_temperature': 'dew'}
NCEI = {'313','314','315','322','335','343','344','346'}
OTHER = {'220','221','222','223','347','348'}


def check_lock(root=ROOT):
    lock = json.loads((root/'lock.json').read_text())
    for name, digest in lock['sha256'].items():
        if q.sha256(q.ROOT/name) != digest:
            raise ValueError('Locked source changed: '+name)
    return lock


def parse(frame, station):
    required = ['STATION','DATE','LATITUDE','LONGITUDE']
    required += [v+s for v in ELEMENTS for s in ('','_Quality_Code','_Source_Code')]
    if not set(required).issubset(frame):
        raise ValueError('GHCNh schema changed')
    if set(frame.STATION.dropna()) != {station['ghcnh_id']}:
        raise ValueError('Wrong station identity')
    if frame.LATITUDE.isna().any() or frame.LONGITUDE.isna().any():
        raise ValueError('Missing station coordinates')
    if ((frame.LATITUDE-station['latitude']).abs()>.1).any() or ((frame.LONGITUDE-station['longitude']).abs()>.1).any():
        raise ValueError('Station moved or mapping differs by more than 0.1 degree')
    out = pd.DataFrame({'utc':pd.to_datetime(frame.DATE,utc=True,errors='raise')})
    for v, name in ELEMENTS.items():
        value = pd.to_numeric(frame[v],errors='raise')
        source = frame[v+'_Source_Code'].fillna('').astype(str).str.strip()
        code = frame[v+'_Quality_Code'].fillna('').astype(str).str.strip()
        unknown = value.notna() & ~source.isin(NCEI|OTHER)
        if unknown.any():
            raise ValueError('Undocumented temperature source: '+str(sorted(source[unknown].unique())))
        accepted = (source.isin(NCEI)&code.isin(['1','5'])) | (source.isin(OTHER)&code.eq('1'))
        # Numeric values are degrees Celsius, not integer tenths as in ISD TMP.
        out[name] = value.where(accepted & np.isfinite(value) & value.between(-100,70))
    out.loc[out.dew>out.temp+.5,'dew'] = np.nan
    for col in ('temp','dew'):
        if (out.groupby('utc')[col].nunique(dropna=False)>1).any():
            raise ValueError('Conflicting duplicate timestamp')
    return out.drop_duplicates('utc')


def retrieve(spec):
    url,path,expected = spec
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and expected and q.sha256(path)==expected['sha256']:
        return expected
    session=requests.Session()
    session.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
    r=session.get(url,timeout=(20,100));r.raise_for_status()
    if path.suffix=='.parquet':
        if r.content[:4]!=b'PAR1' or r.content[-4:]!=b'PAR1':raise ValueError('Not parquet')
    elif path.suffix=='.zip':q.validate_payload('nyiso',r.content)
    path.write_bytes(r.content)
    print('downloaded',path.name,len(r.content),flush=True)
    return dict(file=path.name,source=url,sha256=q.sha256(path),bytes=len(r.content),retrieved_utc=datetime.now(timezone.utc).isoformat())


def download(root=ROOT):
    check_lock(root);cfg=q.read_protocol(root);raw=root/'raw';raw.mkdir(exist_ok=True)
    mp=raw/'download_manifest.json'
    known={r['file']:r for r in json.loads(mp.read_text()).get('files',[])} if mp.exists() else {}
    legacy=q.ROOT/'replication_2025'
    old={r['file']:r for r in json.loads((legacy/'qa/download_manifest.json').read_text())['files']}
    specs=[]
    for kind,url,name in q.source_requests(cfg):
        if kind!='nyiso':continue
        cached=legacy/'raw'/name
        if cached.exists() and q.sha256(cached)==old[name]['sha256']:
            if not (raw/name).exists():shutil.copy2(cached,raw/name)
            known[name]=old[name]
        specs.append((url,raw/name,known.get(name)))
    for station in cfg['stations'].values():
        for year in range(2019,2027):
            name=f"GHCNh_{station['ghcnh_id']}_{year}.parquet"
            specs.append((BASE+f'access/by-year/{year}/parquet/'+name,raw/name,known.get(name)))
    manifest=dict(status='INCOMPLETE',protocol_sha256=q.sha256(root/'protocol.json'),files=[])
    with ThreadPoolExecutor(max_workers=3) as pool:
        for row in pool.map(retrieve,specs):
            if row['file'] in old and row['sha256']!=old[row['file']]['sha256']:
                raise ValueError('Original load archive revision')
            manifest['files'].append(row);q.dump_json(mp,manifest)
    manifest['status']='COMPLETE';q.dump_json(mp,manifest)


def prepare(root=ROOT):
    check_lock(root);cfg=q.read_protocol(root);raw=root/'raw'
    manifest=json.loads((raw/'download_manifest.json').read_text())
    if manifest['status']!='COMPLETE' or manifest['protocol_sha256']!=q.sha256(root/'protocol.json'):
        raise ValueError('Incomplete or stale download')
    for row in manifest['files']:
        if q.sha256(raw/row['file'])!=row['sha256']:raise ValueError('Raw file changed')
    loads=[]
    for row in manifest['files']:
        if not row['file'].endswith('.zip'):continue
        with zipfile.ZipFile(raw/row['file']) as z:
            for name in z.namelist():
                if name.endswith('.csv'):loads.append(q.parse_nyiso_frame(pd.read_csv(z.open(name))))
    data,audit=q.daily_load(pd.concat(loads,ignore_index=True),cfg)
    quality=[]
    for key,station in cfg['stations'].items():
        observations=[]
        for year in range(2019,2027):
            frame=pd.read_parquet(raw/f"GHCNh_{station['ghcnh_id']}_{year}.parquet")
            # 2026 is used only for UTC hours belonging to New York 2025-12-31.
            frame=frame[(frame.DATE>=cfg['start']) & (frame.DATE<'2026-01-01T05:00:00')]
            observations.append(parse(frame,station))
            for v in ELEMENTS:
                for (source,code),n in frame.groupby([v+'_Source_Code',v+'_Quality_Code'],dropna=False).size().items():
                    quality.append(dict(station=key,year=year,element=v,source=str(source),code=str(code),rows=int(n)))
        wx=pd.concat(observations,ignore_index=True)
        if wx.utc.duplicated().any():raise ValueError('Duplicate timestamps across year files')
        data=data.join(q.daily_weather(wx,cfg).rename(columns=lambda c:key+'_'+c))
    out=root/'prepared';out.mkdir(exist_ok=True);data.index.name='date';data.to_csv(out/'daily.csv')
    audit.update(protocol_sha256=q.sha256(root/'protocol.json'),dataset='GHCNh 1.1.0',complete_weather_days=int(data[[k+'_'+v for k in cfg['stations'] for v in ('temp','dew')]].notna().all(axis=1).sum()))
    q.dump_json(out/'audit.json',audit)
    q.dump_json(out/'provenance.json',dict(status='OFFICIAL_ARCHIVE_PREPARED',daily_sha256=q.sha256(out/'daily.csv'),protocol_sha256=q.sha256(root/'protocol.json'),source_sha256=q.sha256(Path(q.__file__)),migration_source_sha256=q.sha256(Path(__file__)),raw_manifest_sha256=q.sha256(raw/'download_manifest.json'),audit_sha256=q.sha256(out/'audit.json')))
    qa=root/'qa';qa.mkdir(exist_ok=True);pd.DataFrame(quality).to_csv(qa/'quality_codes.csv',index=False)
    old=pd.read_csv(q.ROOT/'prepared/daily.csv',index_col='date',parse_dates=True)
    overlap=[]
    for year in range(2019,2025):
        for key in cfg['stations']:
            for variable in ('temp','dew'):
                col=key+'_'+variable;a=old.loc[str(year),col];b=data.loc[str(year),col]
                paired=pd.concat([a.rename('old'),b.rename('new')],axis=1).dropna()
                diff=paired.new-paired.old
                overlap.append(dict(year=year,station=key,variable=variable,old_usable=int(a.notna().sum()),new_usable=int(b.notna().sum()),paired=len(paired),mean_difference_c=float(diff.mean()),mae_difference_c=float(diff.abs().mean()),max_abs_difference_c=float(diff.abs().max())))
    pd.DataFrame(overlap).to_csv(qa/'overlap.csv',index=False)
    fs=q.wx_features(data,cfg,q.fit_exposure_weights(data,cfg));valid=data.peak.notna()&fs['B3_site_identity'].notna().all(axis=1)
    coverage={name:dict(eligible=int(m.sum()),usable=int((m&valid).sum()),fraction=float((m&valid).sum()/m.sum())) for name,m in q.split_masks(data.index,cfg).items()}
    q.dump_json(qa/'coverage.json',coverage)
    data.assign(usable=valid).loc['2025'].to_csv(qa/'daily_2025.csv',index_label='date')
    print(json.dumps(coverage,indent=2));print(pd.DataFrame(overlap).groupby('variable').mae_difference_c.mean())


def verify(root=ROOT):
    check_lock(root)
    cache=q.ROOT/'replication_2025/raw/interval_check'
    if cache.exists():shutil.copytree(cache,root/'raw/interval_check',dirs_exist_ok=True)
    vi.DATES=['20190115','20220715','20240310','20240715','20241103','20250309','20250715','20251102']
    vi.main(root)


def analyse(root=ROOT):
    check_lock(root)
    prov=json.loads((root/'prepared/provenance.json').read_text())
    if prov['migration_source_sha256']!=q.sha256(Path(__file__)):raise ValueError('Stale GHCNh preparation')
    q.analyse(root)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['download','prepare','verify','analyse'])
    args=ap.parse_args()
    with threadpool_limits(limits=1):globals()[args.command]()
