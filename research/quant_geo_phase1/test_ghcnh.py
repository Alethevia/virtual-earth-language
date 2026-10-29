import unittest
import pandas as pd
from ghcnh_migrate import parse

class GHCNhTests(unittest.TestCase):
    def frame(self, source='343', code='5'):
        return pd.DataFrame(dict(STATION=['USW00014733'],DATE=['2025-01-01T00:00:00'],LATITUDE=[42.95],LONGITUDE=[-78.74],temperature=[12.3],temperature_Source_Code=[source],temperature_Quality_Code=[code],dew_point_temperature=[5.],dew_point_temperature_Source_Code=[source],dew_point_temperature_Quality_Code=[code]))
    station=dict(ghcnh_id='USW00014733',latitude=42.9489,longitude=-78.7367)
    def test_celsius_not_scaled(self):self.assertEqual(parse(self.frame(),self.station).temp.iloc[0],12.3)
    def test_source_specific_code(self):
        self.assertTrue(parse(self.frame('223','5'),self.station).temp.isna().all())
        self.assertEqual(parse(self.frame('223','1'),self.station).temp.iloc[0],12.3)
    def test_lowercase_qc_and_unknown_source(self):
        self.assertTrue(parse(self.frame(code='l'),self.station).temp.isna().all())
        with self.assertRaises(ValueError):parse(self.frame('999'),self.station)
    def test_wrong_identity(self):
        f=self.frame();f.STATION='OTHER'
        with self.assertRaises(ValueError):parse(f,self.station)
    def test_conflicting_duplicates(self):
        f=self.frame();g=f.copy();g.temperature=15.
        with self.assertRaises(ValueError):parse(pd.concat([f,g],ignore_index=True),self.station)
