"""
mt5_data_fetcher.py
Handles live data extraction from MetaTrader 5 terminal.
"""

import MetaTrader5 as mt5
import pandas as pd
from typing import Optional, Tuple


class MT5DataFetcher:
    def __init__(self):
        if not mt5.initialize():
            raise RuntimeError(f"MetaTrader 5 initialization failed. Error: {mt5.last_error()}")
        print("✅ MetaTrader 5 initialized successfully.")

    def shutdown(self):
        mt5.shutdown()

    def fetch_timeframe_data(self, symbol: str, timeframe: int, num_bars: int = 300) -> Optional[pd.DataFrame]:
        """Fetches live candles for a given symbol and timeframe from MT5."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
        if rates is None or len(rates) == 0:
            print(f"⚠️ Failed to fetch rates for {symbol} on timeframe {timeframe}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # Ensure standard OHLC naming
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].rename(
            columns={'tick_volume': 'volume'}
        )
        return df

    def get_multi_timeframe_dfs(self, symbol: str) -> Optional[Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
        """Extracts Weekly (W1), Daily (D1), and 4-Hour (H4) DataFrames."""
        # Ensure symbol is visible in Market Watch
        if not mt5.symbol_select(symbol, True):
            print(f"⚠️ Symbol {symbol} not available in MT5 Market Watch.")
            return None

        weekly_df = self.fetch_timeframe_data(symbol, mt5.TIMEFRAME_W1, num_bars=100)
        daily_df = self.fetch_timeframe_data(symbol, mt5.TIMEFRAME_D1, num_bars=200)
        h4_df = self.fetch_timeframe_data(symbol, mt5.TIMEFRAME_H4, num_bars=300)

        if weekly_df is None or daily_df is None or h4_df is None:
            return None

        return weekly_df, daily_df, h4_df