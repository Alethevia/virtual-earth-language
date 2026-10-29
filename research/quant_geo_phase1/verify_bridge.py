#!/usr/bin/env python3
"""Recompute saved bridge metrics independently of the modelling scorer."""
import json
import numpy as np
import pandas as pd
import quant_geo_phase1 as q


def main():
    root=q.ROOT/'bridge_2024';qa=root/'qa'
    read=lambda path:pd.read_csv(path,index_col='date',parse_dates=True)
    old=read(q.ROOT/'qa/empirical_20261029/test_predictions.csv')
    new=read(qa/'ghcnh_2024_predictions.csv')
    y25=read(qa/'reproduced_2025_predictions.csv')
    common=old.index.intersection(new.index)
    frames={'ISD_2024_native':old,'GHCNh_2024_native':new,'GHCNh_2025_native':y25,
            'ISD_2024_common':old.loc[common],'GHCNh_2024_common':new.loc[common]}
    execution=json.loads((qa/'execution.json').read_text())
    threshold=execution['threshold_mw'];metrics=pd.read_csv(qa/'metrics.csv')
    for _,row in metrics.iterrows():
        p=frames[row.scope];error=(p.actual-p[row.family+'__'+row.representation]).to_numpy()
        mask=p.actual.to_numpy()>=threshold
        expected=[np.abs(error).mean(),np.sqrt(np.mean(error**2)),np.abs(error[mask]).mean(),np.maximum(error[mask],0).mean()]
        observed=[row.MAE,row.RMSE,row.high_load_MAE,row.high_load_underprediction]
        np.testing.assert_allclose(observed,expected,rtol=0,atol=1e-8)
        assert row.n==len(p) and row.high_load_n==mask.sum()
    intervals=json.loads((qa/'full_calendar_intervals.json').read_text())
    for row in intervals:
        p=frames[row['scope']];f=row['family'];mask=p.actual>=threshold
        gain=((p.actual-p[f+'__B2_distribution']).abs()-(p.actual-p[f+'__B3_site_identity']).abs())[mask]
        np.testing.assert_allclose(row['paired_mean_improvement'],gain.mean(),rtol=0,atol=1e-8)
        assert row['calendar_end'].endswith('12-31')
    sensitivity=pd.read_csv(qa/'baseline_sensitivity_metrics.csv')
    senspred=read(qa/'baseline_sensitivity_predictions.csv')
    for _,row in sensitivity.iterrows():
        p=senspred[senspred.index.year==row.year]
        if row.scope=='common':p=p.loc[p.index.intersection(old.index)]
        error=(p.actual-p[row.model]).to_numpy();mask=p.actual.to_numpy()>=threshold
        expected=[np.abs(error).mean(),np.sqrt(np.mean(error**2)),np.abs(error[mask]).mean(),np.maximum(error[mask],0).mean()]
        np.testing.assert_allclose([row.MAE,row.RMSE,row.high_load_MAE,row.high_load_underprediction],expected,rtol=0,atol=1e-8)
    q.dump_json(qa/'metric_verification.json',dict(status='ALL_MATCHED',metric_rows=len(metrics),
        error_metrics_recomputed=len(metrics)*4,interval_means_checked=len(intervals),absolute_tolerance_mw=1e-8,
        sensitivity_metric_rows=len(sensitivity),sensitivity_error_metrics_recomputed=len(sensitivity)*4,
        original_2025_predictions_sha256=q.sha256(q.ROOT/'ghcnh_v1/qa/test_predictions.csv'),
        bridge_2024_predictions_sha256=q.sha256(qa/'ghcnh_2024_predictions.csv')))
    print('Verified',len(metrics)*4+len(sensitivity)*4,'error metrics and',len(intervals),'bridge interval means')


if __name__=='__main__':main()
