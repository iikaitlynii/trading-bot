"""Direct price-gate regressions; production v2 additionally requires raw bundles.

Same-close integration assertions are superseded by test_simulation_v2.py.
"""
from datetime import date
import unittest
import numpy as np
import pandas as pd
from market_data import completed_history, extract_close


class MarketDataQualityTests(unittest.TestCase):
    def history(self,crypto=False,end=None,n=220):
        return pd.Series(np.linspace(10,30,n),index=pd.date_range(end=end or ('2026-01-13' if crypto else '2026-01-14'),periods=n,freq='D' if crypto else 'B'))
    def validate(self,series,crypto=False):
        return completed_history(series,minimum=100 if crypto else 200,today=date(2026,1,14),
                                 completed_through=date(2026,1,13) if crypto else date(2026,1,14),
                                 max_age_days=2 if crypto else 4,daily=crypto,weekdays_only=not crypto)
    def test_invalid_numeric_values_inside_windows_are_rejected(self):
        for crypto in (False,True):
            for value in (np.nan,np.inf,-np.inf,0,-1,'bad','12.5',True,1j,pd.NA):
                for offset in (-1,-20):
                    a=self.history(crypto).astype(object);a.iloc[offset]=value
                    if isinstance(value,(float,int)) and not isinstance(value,bool):a=a.astype(float)
                    with self.subTest(crypto=crypto,value=value,offset=offset),self.assertRaises(ValueError):self.validate(a,crypto)
    def test_malformed_and_incomplete_histories_rejected(self):
        for crypto in (False,True):
            a=self.history(crypto);dup=a.copy();dup.index=a.index[:-1].append(a.index[-2:-1])
            nat=a.copy();nat.index=a.index[:-1].append(pd.DatetimeIndex([pd.NaT]))
            cases=[pd.Series(dtype=float),a.iloc[-10:],dup,nat,a.iloc[::-1],a.set_axis(a.index.astype(str)),a.reset_index(drop=True),a.to_frame(),self.history(crypto,end='2026-01-15'),self.history(crypto,end='2026-01-05')]
            for bad in cases:
                with self.subTest(crypto=crypto),self.assertRaises(ValueError):self.validate(bad,crypto)
    def test_crypto_interior_gaps_rejected(self):
        a=self.history(True)
        with self.assertRaisesRegex(ValueError,'missing daily'):self.validate(a.drop(a.index[-10]),True)
    def test_weekend_stock_bar_rejected(self):
        a=self.history();idx=list(a.index);idx[-3]=pd.Timestamp('2026-01-11');a.index=pd.DatetimeIndex(idx)
        with self.assertRaisesRegex(ValueError,'weekend'):self.validate(a)
    def test_unfinished_crypto_bar_is_excluded(self):
        a=self.history(True,end='2026-01-14');a.iloc[-1]=0
        b=self.validate(a,True);self.assertEqual(b.index[-1].date(),date(2026,1,13));self.assertEqual(b.iloc[-1],a.iloc[-2])
    def test_unrounded_tiny_prices_are_preserved(self):
        a=self.history()*1e-8;pd.testing.assert_series_equal(self.validate(a),a)
    def test_symbol_selection_preserves_bad_rows(self):
        a=self.history();a.iloc[-1]=np.nan
        data=pd.DataFrame({('Close','OTHER'):a.fillna(999),('Close','AAPL'):a})
        pd.testing.assert_series_equal(extract_close(data,'AAPL'),data[('Close','AAPL')])
        with self.assertRaises(KeyError):extract_close(data,'MISSING')
    def test_before_close_and_weekend_completed_bounds(self):
        a=self.history()
        b=completed_history(a,minimum=200,today=date(2026,1,14),completed_through=date(2026,1,13),max_age_days=4,weekdays_only=True)
        self.assertEqual(b.index[-1].date(),date(2026,1,13))
        a=self.history(end='2026-01-09')
        b=completed_history(a,minimum=200,today=date(2026,1,12),completed_through=date(2026,1,9),max_age_days=4,weekdays_only=True)
        pd.testing.assert_series_equal(a,b)
