#!/usr/bin/env python3
"""One post-hoc refit with the already-published legacy B2 parameters; no search."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import quant_geo_phase1 as q
import ghcnh_migrate as g
import bridge_2024 as bridge


def main():
    bridge.check_lock()
    root=bridge.ROOT;qa=root/'qa'
    lock=json.loads((root/'sensitivity_lock.json').read_text())
    for name,digest in lock['sha256'].items():
        if q.sha256(q.ROOT/name)!=digest:raise ValueError('Sensitivity input changed: '+name)
    cfg=q.read_protocol(g.ROOT);prov=q.validate_analysis_inputs(g.ROOT)
    bridge.require_frozen_daily(prov['daily_sha256'],lock['daily_sha256'])
    data=pd.read_csv(g.ROOT/'prepared/daily.csv',index_col='date',parse_dates=True)
    fs=q.wx_features(data,cfg,q.fit_exposure_weights(data,cfg))
    valid=data.peak.notna()&fs['B3_site_identity'].notna().all(axis=1)
    train=bridge.fit_mask(data.index,valid,cfg)
    old=json.loads((q.ROOT/'qa/empirical_20261029/model_selection.json').read_text())
    current=json.loads((g.ROOT/'qa/model_selection.json').read_text())
    # This isolates the B2 parameter choice within the new data version. The B3
    # saved parameters are identical in the old and new studies.
    assert old['hgb__B3_site_identity']['parameters']==current['hgb__B3_site_identity']['parameters']
    params=old['hgb__B2_distribution']['parameters']
    models=[m for p,m in q.model_candidates('hgb',cfg['seed']) if p==params]
    if len(models)!=1:raise ValueError('Legacy B2 not in original candidate grid')
    model=models[0];model.fit(fs['B2_distribution'].loc[train],data.loc[train,'peak'])
    old_predictions=pd.read_csv(q.ROOT/'qa/empirical_20261029/test_predictions.csv',index_col='date',parse_dates=True)
    predictions=[];metrics=[];intervals=[]
    for year,path in [(2024,qa/'ghcnh_2024_predictions.csv'),(2025,qa/'reproduced_2025_predictions.csv')]:
        base=pd.read_csv(path,index_col='date',parse_dates=True)
        frame=pd.DataFrame({'actual':base.actual,'legacy_parameter_B2':model.predict(fs['B2_distribution'].loc[base.index]),
                            'selected_parameter_B2':base.hgb__B2_distribution,'unchanged_B3':base.hgb__B3_site_identity})
        predictions.append(frame)
        scopes=[('native',frame)]
        if year==2024:scopes.append(('common',frame.loc[frame.index.intersection(old_predictions.index)]))
        for scope,pred in scopes:
            for name in ['legacy_parameter_B2','selected_parameter_B2','unchanged_B3']:
                metrics.append(dict(year=year,scope=scope,model=name,**q.score(pred.actual.to_numpy(),pred[name].to_numpy(),24966.5)))
            for comparator in ['legacy_parameter_B2','selected_parameter_B2']:
                gain=((pred.actual-pred[comparator]).abs()-(pred.actual-pred.unchanged_B3).abs()).where(pred.actual>=24966.5)
                for block in cfg['bootstrap_block_days']:
                    intervals.append(dict(year=year,scope=scope,comparator=comparator,**bridge.calendar_interval(gain,year,block,cfg['bootstrap_replicates'],cfg['seed'])))
    pd.concat(predictions).to_csv(qa/'baseline_sensitivity_predictions.csv',index_label='date')
    pd.DataFrame(metrics).to_csv(qa/'baseline_sensitivity_metrics.csv',index=False)
    q.dump_json(qa/'baseline_sensitivity_intervals.json',intervals)
    q.dump_json(qa/'baseline_sensitivity_execution.json',dict(status='POST_HOC_PARAMETER_SENSITIVITY',model_fits=1,
        parameter_searches=0,legacy_B2_parameters=params,current_B2_parameters=current['hgb__B2_distribution']['parameters'],
        B3_parameters_identical=True,training_days=int(train.sum()),lock=lock,source_sha256=q.sha256(Path(__file__)),
        limitation='Diagnostic after observing the bridge. Neither comparator replaces either published primary model or restores an independent holdout.'))
    print(pd.DataFrame(metrics).to_string(index=False))


if __name__=='__main__':
    with threadpool_limits(limits=1):main()
