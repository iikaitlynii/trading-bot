"""Deterministic synthetic examples with independently known bin totals."""
import unittest
import numpy as np
import pandas as pd
from volume_profile import profile


class VolumeProfileTests(unittest.TestCase):
    def fixture(self):
        # One spanning candle gives 1 per bin; point candles add 9,1,7,0.
        return pd.DataFrame(dict(date=['2026-10-19','2026-10-20','2026-10-21','2026-10-22','2026-10-23'],
                                 low=[100.,100.5,101.5,102.5,103.5],
                                 high=[104.,100.5,101.5,102.5,103.5],
                                 close=[102.,100.5,101.5,102.5,103.5],volume=[4.,9.,1.,7.,1.]))

    def run_profile(self, f=None, **kwargs):
        return profile(self.fixture() if f is None else f, start='2026-10-19',end='2026-10-23',bins=4,**kwargs)

    def test_known_totals_and_levels(self):
        p=self.run_profile()
        self.assertEqual([b['volume'] for b in p['bins']], [10,2,8,2])
        self.assertEqual((p['poc'],p['val'],p['vah']), (100.5,100,103))
        self.assertEqual(p['hvn'],[102.5]);self.assertEqual(p['lvn'],[101.5])
        self.assertAlmostEqual(p['value_area_achieved'],20/22)
        self.assertEqual(p['total_volume'],22)
        self.assertIn('APPROXIMATE',p['evidence'])

    def test_ties_flat_profiles_and_full_area(self):
        f=self.fixture();f['volume']=[4,1,1,1,1]
        p=self.run_profile(f,value_area=1)
        self.assertEqual(p['poc'],100.5);self.assertEqual(p['vah'],104)
        self.assertEqual(p['hvn'],[]);self.assertEqual(p['lvn'],[])
        f=self.fixture();f['volume']=[4,1,8,1,8]
        p=self.run_profile(f)
        # POC index 1; equal adjacent bins choose lower before expanding upward.
        self.assertTrue(p['bins'][0]['value_area'])

    def test_conservation_and_scale_invariance(self):
        f=self.fixture();p=self.run_profile(f);f.volume*=7;q=self.run_profile(f)
        self.assertAlmostEqual(q['total_volume'],p['total_volume']*7)
        for key in ('poc','vah','val','hvn','lvn'):self.assertEqual(p[key],q[key])

    def test_bad_data_is_rejected_without_repairs(self):
        cases=[]
        f=self.fixture();cases.extend([f.iloc[:-1],f.iloc[::-1],pd.concat([f.iloc[:1],f])])
        for col,val in [('volume',0),('volume',-1),('volume',np.nan),('high',np.inf),('close',200),('low',0),('volume','unknown')]:
            f=self.fixture();f[col]=f[col].astype(object);f.loc[0,col]=val;cases.append(f)
        for f in cases:
            with self.subTest(frame=f.to_dict()),self.assertRaises(ValueError):self.run_profile(f)

    def test_invalid_parameters_and_constant_range(self):
        for area in (0,1.1,np.nan,True):
            with self.assertRaises(ValueError):self.run_profile(value_area=area)
        f=self.fixture();f[['low','high','close']]=100.
        with self.assertRaises(ValueError):self.run_profile(f)
        for bins in (1,101,True,2.5):
            with self.assertRaises(ValueError):profile(self.fixture(),start='2026-10-19',end='2026-10-23',bins=bins)

if __name__=='__main__':unittest.main()
