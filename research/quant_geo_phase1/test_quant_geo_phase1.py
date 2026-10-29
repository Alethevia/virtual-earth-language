"""OFFLINE ARTIFICIAL-FIXTURE TESTS. No real electricity or weather results."""
import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import quant_geo_phase1 as q


def fixture_data():
    cfg = q.read_protocol()
    idx = pd.date_range(cfg['start'], cfg['end'], freq='D')
    rng = np.random.default_rng(101)
    n = len(idx); d = np.arange(n)
    out = pd.DataFrame(index=idx)
    for j, key in enumerate(cfg['stations']):
        t = 15 + 12*np.sin(2*np.pi*d/365.2425) + j + rng.normal(0, 2, n)
        out[key+'_temp'] = t
        out[key+'_dew'] = t - 5 - rng.uniform(0, 2, n)
    out['peak'] = 100 + .02*d + 3*np.maximum(out.LGA_temp-18.333, 0) + rng.normal(0, 2, n)
    for j, station in enumerate(cfg['stations'].values()):
        for zone in station['zones']:
            out['zone_'+zone] = 10 + j + rng.uniform(0,1,n)
    return out


class AlgebraTests(unittest.TestCase):
    def test_jensen_exact_identity_random(self):
        rng=np.random.default_rng(18); temp=rng.uniform(-20,45,(1000,5))
        w=rng.uniform(.1,1,5);w/=w.sum();theta=18.333333333333
        gap=np.maximum(temp-theta,0)@w-np.maximum(temp@w-theta,0)
        formula=(np.abs(temp-theta)@w-np.abs(temp@w-theta))/2
        np.testing.assert_allclose(gap,formula,atol=1e-12)
        self.assertGreaterEqual(gap.min(),-1e-12)

    def test_heating_cooling_gap_same(self):
        t=np.array([5.,30.,20.]);w=np.array([.2,.5,.3]);k=18.
        c=np.maximum(t-k,0)@w-max(t@w-k,0)
        h=np.maximum(k-t,0)@w-max(k-t@w,0)
        self.assertAlmostEqual(c,h)

    def test_spread_without_gap_above_threshold(self):
        t=np.array([28.,32.]);self.assertEqual(np.maximum(t-25,0).mean()-max(t.mean()-25,0),0)
        self.assertGreater(t.std(),0)

    def test_constructed_identity_example(self):
        w=np.array([.5,.5]);b=np.array([1.,4.]);t=np.array([20.,30.])
        self.assertEqual(np.sum(w*b*np.maximum(t-25,0)),10.)
        self.assertEqual(np.sum(w*b*np.maximum(t[::-1]-25,0)),2.5)


class ParsingTests(unittest.TestCase):
    def test_dst_expected_hours(self):
        self.assertEqual(q.expected_hours(pd.Timestamp('2023-03-12')),23)
        self.assertEqual(q.expected_hours(pd.Timestamp('2023-11-05')),25)
        self.assertEqual(q.expected_hours(pd.Timestamp('2024-02-29')),24)

    def test_fall_back_two_distinct_hours(self):
        f=pd.DataFrame({'Time Stamp':['11/05/2023 01:00:00']*2,'Time Zone':['EDT','EST'],
                        'Name':['N.Y.C.']*2,'Integrated Load':[1,2]})
        out=q.parse_nyiso_frame(f)
        self.assertEqual(out.utc.iloc[1]-out.utc.iloc[0],pd.Timedelta(hours=1))
        self.assertEqual(out.zone.tolist(),['NYC','NYC'])

    def test_unknown_timezone_rejected(self):
        f=pd.DataFrame({'Time Stamp':['01/01/2024 00:00:00'],'Time Zone':['BAD'],
                        'Name':['WEST'],'Integrated Load':[1]})
        with self.assertRaises(ValueError):q.parse_nyiso_frame(f)

    def test_negative_load_rejected(self):
        f=pd.DataFrame({'Time Stamp':['01/01/2024 00:00:00'],'Time Zone':['EST'],
                        'Name':['WEST'],'Integrated Load':[-1]})
        with self.assertRaises(ValueError):q.parse_nyiso_frame(f)

    def test_weather_flags_and_sentinel(self):
        f=pd.DataFrame({'DATE':pd.date_range('2024-01-01',periods=4,freq='h').astype(str),
                        'TMP':['+0200,1','+9999,1','+0100,3','+0300,5'],
                        'DEW':['+0100,1','+0000,1','+0000,1','+0200,5']})
        v=q.parse_weather_frame(f)
        self.assertEqual(v.temp.iloc[0],20)
        self.assertTrue(v.temp.iloc[1:3].isna().all())
        self.assertEqual(v.temp.iloc[3],30)

    def test_dewpoint_above_temp_rejected(self):
        f=pd.DataFrame({'DATE':['2024-01-01'],'TMP':['+0100,1'],'DEW':['+0200,1']})
        self.assertTrue(pd.isna(q.parse_weather_frame(f).dew.iloc[0]))

    def test_noaa_html_is_not_data(self):
        with self.assertRaises((ValueError,pd.errors.ParserError)):
            q.validate_payload('noaa',b'<html>Service unavailable</html>')

    def test_zip_schema(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('day.csv','Time Stamp,Time Zone,Name,Integrated Load\n01/01/2024 00:00:00,EST,WEST,1\n')
        q.validate_payload('nyiso',b.getvalue())
        with self.assertRaises(zipfile.BadZipFile):q.validate_payload('nyiso',b'notzip')

    def test_weather_daily_coverage_no_imputation(self):
        cfg=q.read_protocol();ts=pd.date_range('2024-01-01 05:00',periods=24,freq='h',tz='UTC')
        df=pd.DataFrame({'utc':ts,'temp':np.ones(24)*10,'dew':np.ones(24)*5})
        df.loc[:2,'temp']=np.nan
        out=q.daily_weather(df,cfg)
        self.assertTrue(pd.isna(out.temp.iloc[0]))
        self.assertEqual(out.dew.iloc[0],5)

    def test_duplicate_subhour_readings_not_double_hours(self):
        cfg=q.read_protocol();ts=pd.date_range('2024-01-01 05:00',periods=24,freq='h',tz='UTC')
        df=pd.DataFrame({'utc':ts,'temp':np.ones(24)*10,'dew':np.ones(24)*5})
        df=pd.concat([df,df],ignore_index=True)
        out=q.daily_weather(df,cfg)
        self.assertEqual(out.temp_hours.iloc[0],24)

    def _load_fixture(self):
        cfg=q.read_protocol();cfg=copy.deepcopy(cfg)
        cfg.update(start='2024-01-01',end='2024-01-01')
        cfg['stations']={'A':{'zones':['WEST']},'B':{'zones':['NYC']}}
        ts=pd.date_range('2024-01-01 05:00',periods=24,freq='h',tz='UTC')
        a=np.where(np.arange(24)<12,15.,5.);b=20-a
        f=pd.concat([pd.DataFrame({'utc':ts,'zone':'WEST','load':a}),pd.DataFrame({'utc':ts,'zone':'NYC','load':b})])
        return cfg,f

    def test_system_peak_not_sum_of_zonal_peaks(self):
        cfg,f=self._load_fixture();d,_=q.daily_load(f,cfg)
        self.assertEqual(d.peak.iloc[0],20.)
        self.assertEqual(f.groupby('zone').load.max().sum(),30.)

    def test_missing_zone_hour_removes_day(self):
        cfg,f=self._load_fixture();f=f.iloc[1:]
        d,_=q.daily_load(f,cfg);self.assertTrue(pd.isna(d.peak.iloc[0]))

    def test_conflicting_duplicates_rejected(self):
        cfg,f=self._load_fixture();dup=f.iloc[:1].copy();dup['load']=999
        with self.assertRaises(ValueError):q.daily_load(pd.concat([f,dup]),cfg)


class LeakageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=q.read_protocol();cls.data=fixture_data()

    def test_lags_exclude_current_target(self):
        d=self.data.copy();before=q.calendar_lags(d);i=pd.Timestamp('2023-05-01')
        d.loc[i,'peak']+=10000;after=q.calendar_lags(d)
        np.testing.assert_array_equal(before.loc[i].to_numpy(),after.loc[i].to_numpy())
        self.assertNotEqual(before.loc[i+pd.Timedelta(days=1),'load_lag_1'],after.loc[i+pd.Timedelta(days=1),'load_lag_1'])

    def test_no_calendar_gap_shift(self):
        with self.assertRaises(ValueError):q.calendar_lags(self.data.drop(self.data.index[10]))

    def test_training_only_weights(self):
        a=q.fit_exposure_weights(self.data,self.cfg);d=self.data.copy()
        cols=[c for c in d if c.startswith('zone_')]
        d.loc['2023-01-01':,cols]=999999
        np.testing.assert_array_equal(a,q.fit_exposure_weights(d,self.cfg))

    def test_splits_disjoint_and_2024_leap(self):
        m=q.split_masks(self.data.index,self.cfg)
        self.assertFalse(np.any(m['train'] & m['validation']))
        self.assertFalse(np.any(m['test'] & m['validation']))
        self.assertEqual(m['test'].sum(),366)
        self.assertEqual(sum(x.sum() for x in m.values()),len(self.data))

    def test_shuffle_only_changes_identity(self):
        w=q.fit_exposure_weights(self.data,self.cfg)
        a=q.wx_features(self.data,self.cfg,w);b=q.wx_features(self.data,self.cfg,w,17)
        pd.testing.assert_frame_equal(a['B2_distribution'],b['B2_distribution'])
        extras=[c for c in a['B3_site_identity'] if c.startswith('site_')]
        self.assertFalse(a['B3_site_identity'][extras].equals(b['B3_site_identity'][extras]))

    def test_shuffle_date_key_not_position(self):
        w=q.fit_exposure_weights(self.data,self.cfg)
        a=q.wx_features(self.data,self.cfg,w,17)['B3_site_identity']
        b=q.wx_features(self.data.iloc[10:],self.cfg,w,17)['B3_site_identity']
        cols=[c for c in a if c.startswith('site_')]
        pd.testing.assert_frame_equal(a.loc[b.index,cols],b[cols])

    def test_feature_groups_nested(self):
        w=q.fit_exposure_weights(self.data,self.cfg);f=q.wx_features(self.data,self.cfg,w)
        names=list(f)
        for a,b in zip(names,names[1:]):self.assertTrue(set(f[a]).issubset(f[b]))

    def test_hyperparameter_selection_ignores_test_labels(self):
        d=self.data; x=q.calendar_lags(d).dropna();y=d.loc[x.index,'peak'];m=q.split_masks(x.index,self.cfg)
        p,a=q.fit_selected(x,y,m,'ridge',7)
        yy=y.copy();yy.loc[m['test']]=1e9
        pp,b=q.fit_selected(x,yy,m,'ridge',7)
        np.testing.assert_array_equal(p,pp);self.assertEqual(a,b)


class ReportingTests(unittest.TestCase):
    def test_metric_subset(self):
        s=q.score(np.array([1,10,20]),np.array([2,8,16]),10)
        self.assertEqual(s['high_load_n'],2);self.assertEqual(s['high_load_MAE'],3)
        self.assertEqual(s['high_load_underprediction'],3)

    def test_constant_block_bootstrap(self):
        s=pd.Series(np.ones(90),index=pd.date_range('2024-01-01',periods=90))
        r=q.paired_block_interval(s,14,100,3)
        self.assertEqual(r['lower_95'],1);self.assertEqual(r['upper_95'],1)

    def test_analysis_cannot_use_missing_data(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'protocol.json').write_text(json.dumps(q.read_protocol()))
            with self.assertRaises(FileNotFoundError):q.analyse(p)
            self.assertFalse((p/'results'/'empirical_report.json').exists())

    def test_request_list(self):
        jobs=list(q.source_requests(q.read_protocol()))
        self.assertEqual(sum(k=='nyiso' for k,_,_ in jobs),72)
        self.assertEqual(sum(k=='noaa' for k,_,_ in jobs),30)
        self.assertTrue(all(u.startswith('https://') for _,u,_ in jobs))

    def test_invalid_probability_weights(self):
        d=fixture_data()
        with self.assertRaises(ValueError):q.wx_features(d,q.read_protocol(),np.ones(5))


if __name__=='__main__':
    with threadpool_limits(limits=1):
        unittest.main(verbosity=2)
