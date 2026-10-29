import unittest
import numpy as np
import pandas as pd
from bridge_2024 import fit_mask,reproduce,common_sample,calendar_interval,boundary_revision_allowed,require_frozen_daily

class BridgeTests(unittest.TestCase):
    def test_only_boundary_archive_revision_can_be_considered(self):
        self.assertTrue(boundary_revision_allowed('GHCNh_USW00014733_2026.parquet'))
        self.assertFalse(boundary_revision_allowed('GHCNh_USW00014733_2025.parquet'))
        self.assertFalse(boundary_revision_allowed('nyiso_202601.zip'))
    def test_revised_archive_cannot_change_model_input(self):
        with self.assertRaises(ValueError):require_frozen_daily('new-input-hash','frozen-input-hash')
    def test_fit_excludes_both_evaluation_years(self):
        idx=pd.to_datetime(['2022-12-31','2023-12-31','2024-01-01','2025-01-01'])
        cfg=dict(start='2019-01-01',train_end='2022-12-31',validation_start='2023-01-01',validation_end='2023-12-31',test_start='2025-01-01',test_end='2025-12-31')
        self.assertEqual(fit_mask(idx,np.ones(4,dtype=bool),cfg).tolist(),[True,True,False,False])
    def test_changed_frozen_prediction_rejected(self):
        a=pd.DataFrame({'actual':[2.],'model':[1.]});b=a.copy();b['model']+=.1
        with self.assertRaises(AssertionError):reproduce(a,b)
    def test_pairing_checks_actual_load(self):
        a=pd.DataFrame({'actual':[2.,3.]},index=pd.to_datetime(['2024-01-01','2024-01-02']))
        b=a.iloc[1:].copy();x,y=common_sample(a,b);self.assertEqual(len(x),1)
        b['actual']=4.
        with self.assertRaises(AssertionError):common_sample(a,b)
    def test_full_calendar_includes_trailing_missing_days(self):
        d=pd.Series([2.],index=pd.to_datetime(['2025-12-24']))
        r=calendar_interval(d,2025,14,100,3)
        self.assertEqual(r['calendar_days'],365);self.assertEqual(r['calendar_end'],'2025-12-31')
        self.assertEqual(r['paired_mean_improvement'],2.)
