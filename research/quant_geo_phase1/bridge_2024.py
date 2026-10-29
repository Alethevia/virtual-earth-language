#!/usr/bin/env python3
"""Post-hoc same-version bridge. Refit fixed models; never search new parameters."""
import argparse
import json
import shutil
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import sklearn
from threadpoolctl import threadpool_limits
import quant_geo_phase1 as q
import ghcnh_migrate as g

ROOT=q.ROOT/'bridge_2024'


def check_lock():
    lock=json.loads((ROOT/'lock.json').read_text())
    for name,digest in lock['sha256'].items():
        if q.sha256(q.ROOT/name)!=digest:raise ValueError('Bridge input changed: '+name)
    g.check_lock()
    return lock


def restore():
    """Recover the exact published input snapshot, refusing archive revisions."""
    check_lock();root=g.ROOT;raw=root/'raw';raw.mkdir(exist_ok=True)
    manifest=json.loads((root/'qa/download_manifest.json').read_text())
    def fetch(row):
        actual=g.retrieve((row['source'],raw/row['file'],row))
        if actual['sha256']!=row['sha256']:raise ValueError('Archive revision: '+row['file'])
        return row['file']
    with ThreadPoolExecutor(max_workers=3) as pool:
        names=list(pool.map(fetch,manifest['files']))
    cfg=q.read_protocol(root);loads=[]
    for row in manifest['files']:
        if row['file'].endswith('.zip'):
            with zipfile.ZipFile(raw/row['file']) as z:
                for name in z.namelist():
                    if name.endswith('.csv'):loads.append(q.parse_nyiso_frame(pd.read_csv(z.open(name))))
    data,_=q.daily_load(pd.concat(loads,ignore_index=True),cfg)
    for key,station in cfg['stations'].items():
        pieces=[]
        for year in range(2019,2027):
            frame=pd.read_parquet(raw/f"GHCNh_{station['ghcnh_id']}_{year}.parquet")
            frame=frame[(frame.DATE>=cfg['start'])&(frame.DATE<'2026-01-01T05:00:00')]
            pieces.append(g.parse(frame,station))
        weather=pd.concat(pieces,ignore_index=True)
        if weather.utc.duplicated().any():raise ValueError('Duplicate UTC observations')
        data=data.join(q.daily_weather(weather,cfg).rename(columns=lambda c:key+'_'+c))
    prepared=root/'prepared';prepared.mkdir(exist_ok=True)
    candidate=prepared/'daily.restored.csv';data.index.name='date';data.to_csv(candidate)
    expected=json.loads((root/'qa/preparation_provenance.json').read_text())
    if q.sha256(candidate)!=expected['daily_sha256']:
        raise ValueError('Rebuilt input differs from the published snapshot; no bridge will run')
    candidate.replace(prepared/'daily.csv')
    shutil.copy2(root/'qa/download_manifest.json',raw/'download_manifest.json')
    shutil.copy2(root/'qa/preparation_audit.json',prepared/'audit.json')
    shutil.copy2(root/'qa/preparation_provenance.json',prepared/'provenance.json')
    q.dump_json(ROOT/'qa/restoration.json',dict(status='EXACT_SNAPSHOT_RESTORED',files_verified=len(names),
        verified_utc=datetime.now(timezone.utc).isoformat(),daily_sha256=expected['daily_sha256'],
        note='Download-manifest timestamps retain original retrieval times; this is the new verification time.'))
    print('Exact input snapshot restored:',len(names),'files',flush=True)


def fit_mask(index,valid,cfg):
    # Explicitly exclude both already-observed evaluation years.
    masks=q.split_masks(index,cfg)
    return valid & (masks['train']|masks['validation'])


def reproduce(actual,expected):
    if not actual.index.equals(expected.index) or list(actual)!=list(expected):
        raise ValueError('Frozen prediction dates or columns differ')
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-7)
    return float(np.abs(actual.to_numpy()-expected.to_numpy()).max())


def common_sample(a,b):
    dates=a.index.intersection(b.index).sort_values()
    if dates.empty:raise ValueError('No paired dates')
    np.testing.assert_allclose(a.loc[dates,'actual'],b.loc[dates,'actual'],rtol=0,atol=1e-8)
    return a.loc[dates],b.loc[dates]


def calendar_interval(differences,year,block,replicates,seed):
    dates=pd.date_range(f'{year}-01-01',f'{year}-12-31',freq='D')
    if not differences.index.is_unique or not differences.index.isin(dates).all():
        raise ValueError('Invalid year or duplicate dates')
    return dict(calendar_start=str(dates.min().date()),calendar_end=str(dates.max().date()),
                calendar_days=len(dates),**q.paired_block_interval(differences.reindex(dates),block,replicates,seed))


def analyse():
    lock=check_lock();root=g.ROOT;cfg=q.read_protocol(root)
    provenance=q.validate_analysis_inputs(root)
    if provenance['migration_source_sha256']!=q.sha256(Path(g.__file__)):
        raise ValueError('Stale migration code')
    data=pd.read_csv(root/'prepared/daily.csv',index_col='date',parse_dates=True)
    features=q.wx_features(data,cfg,q.fit_exposure_weights(data,cfg))
    valid=data.peak.notna()&features['B3_site_identity'].notna().all(axis=1)
    train=fit_mask(data.index,valid,cfg)
    if data.index[train].max()>pd.Timestamp('2023-12-31'):raise ValueError('Evaluation data entered fit')
    selection=json.loads((root/'qa/model_selection.json').read_text())
    frozen=pd.read_csv(root/'qa/test_predictions.csv',index_col='date',parse_dates=True)
    legacy=pd.read_csv(q.ROOT/'qa/empirical_20261029/test_predictions.csv',index_col='date',parse_dates=True)
    observed24=valid&(data.index.year==2024)
    if observed24.sum()/366<cfg['minimum_usable_fraction_each_split']:raise ValueError('2024 coverage failure')
    new24=pd.DataFrame({'actual':data.loc[observed24,'peak']})
    check25=pd.DataFrame({'actual':data.loc[frozen.index,'peak']})
    for label,saved in selection.items():
        family,representation=label.split('__')
        x=features[representation] if not representation.startswith('identity_scramble_') else q.wx_features(
            data,cfg,q.fit_exposure_weights(data,cfg),permutation_seed=int(representation.rsplit('_',1)[1]))['B3_site_identity']
        if x.shape[1]!=saved['features']:raise ValueError('Feature schema changed')
        models=[model for params,model in q.model_candidates(family,cfg['seed']) if params==saved['parameters']]
        if len(models)!=1:raise ValueError('Unknown frozen model')
        model=models[0];model.fit(x.loc[train],data.loc[train,'peak'])
        check25[label]=model.predict(x.loc[frozen.index])
        new24[label]=model.predict(x.loc[new24.index])
        print('Refit frozen pipeline',label,flush=True)
    # Fail closed before computing any bridge metrics.
    delta=reproduce(check25,frozen)
    old_common,new_common=common_sample(legacy,new24)
    threshold=float(data.loc[data.index<=cfg['train_end'],'peak'].quantile(cfg['tail_quantile_training_only']))
    frames={'ISD_2024_native':legacy,'GHCNh_2024_native':new24,'GHCNh_2025_native':check25,
            'ISD_2024_common':old_common,'GHCNh_2024_common':new_common}
    metrics=[];intervals=[]
    for scope,pred in frames.items():
        for label in selection:
            family,representation=label.split('__')
            metrics.append(dict(scope=scope,family=family,representation=representation,
                **q.score(pred.actual.to_numpy(),pred[label].to_numpy(),threshold)))
        year=int(pred.index[0].year)
        for family in ('hgb','ridge'):
            diff=((pred.actual-pred[family+'__B2_distribution']).abs()-(pred.actual-pred[family+'__B3_site_identity']).abs()).where(pred.actual>=threshold)
            for block in cfg['bootstrap_block_days']:
                intervals.append(dict(scope=scope,family=family,**calendar_interval(diff,year,block,cfg['bootstrap_replicates'],cfg['seed'])))
    qa=ROOT/'qa';qa.mkdir(exist_ok=True)
    new24.to_csv(qa/'ghcnh_2024_predictions.csv',index_label='date')
    check25.to_csv(qa/'reproduced_2025_predictions.csv',index_label='date')
    pd.DataFrame(metrics).to_csv(qa/'metrics.csv',index=False)
    q.dump_json(qa/'full_calendar_intervals.json',intervals)
    old_selection=json.loads((q.ROOT/'qa/empirical_20261029/model_selection.json').read_text())
    q.dump_json(qa/'parameter_comparison.json',{k:dict(legacy=old_selection[k]['parameters'],ghcnh=selection[k]['parameters'],
        changed=old_selection[k]['parameters']!=selection[k]['parameters']) for k in selection})
    comparison=pd.DataFrame(index=pd.date_range('2024-01-01','2024-12-31',freq='D'))
    comparison['ISD_usable']=comparison.index.isin(legacy.index)
    comparison['GHCNh_usable']=comparison.index.isin(new24.index)
    comparison['actual_load_mw']=data.peak.reindex(comparison.index)
    comparison['high_load']=comparison.actual_load_mw>=threshold
    comparison.to_csv(qa/'coverage_2024.csv',index_label='date')
    q.dump_json(qa/'execution.json',dict(status='POST_HOC_SAME_VERSION_BRIDGE',model_fits=13,new_parameter_searches=0,
        training_days=int(train.sum()),training_end=str(data.index[train].max().date()),
        new_2024_days=len(new24),legacy_2024_days=len(legacy),common_2024_days=len(old_common),
        frozen_2025_max_difference_mw=delta,threshold_mw=threshold,lock=lock,
        source_sha256=q.sha256(Path(__file__)),data_sha256=provenance['daily_sha256'],
        versions=dict(python=sys.version.split()[0],numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__),
        limitations=['Both evaluation years already observed; bridge is descriptive, not new independent validation.',
        'Historical same-date version comparison includes training samples, weather values and previously selected parameters; not pure sensor measurement causality.',
        'Supplementary intervals span every calendar day; the published 2025 primary interval is preserved unchanged.',
        'No pooled two-year success claim, test-year tuning, geographic transfer or day-ahead forecast validation.']))
    print(pd.DataFrame(metrics).query("representation in ['B2_distribution','B3_site_identity']").to_string(index=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['restore','analyse']);args=ap.parse_args()
    with threadpool_limits(limits=1):globals()[args.command]()
