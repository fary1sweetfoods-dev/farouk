import time
import logging
import pandas as pd
import MetaTrader5 as mt5
from typing import Optional
from config import WATCHLIST, CONFIG
from scanner_pipeline import ScannerPipeline
from telegram_notifier import send_telegram_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MainRunner")


def fetch_mt5_dataframe(symbol: str, timeframe, count: int = 150) -> Optional[pd.DataFrame]:
    """Fetches OHLCV rates from MetaTrader 5 and converts them to a Pandas DataFrame."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df


def run_live_bot():
    logger.info("🚀 Starting Live Scanner Engine...")

    if not mt5.initialize():
        logger.error(f"❌ Failed to initialize MetaTrader 5, error code: {mt5.last_error()}")
        return

    logger.info("✅ MetaTrader 5 initialized successfully.")
    send_telegram_alert("🚀 **Scanner started via @Candle_rangebot**\nScan interval: 60s")

    try:
        scan_count = 0
        while True:
            scan_count += 1
            logger.info("----------------------------------------")
            logger.info(f"Running market scan cycle {scan_count} across {len(WATCHLIST)} symbols...")

            for symbol in WATCHLIST:
                try:
                    logger.info(f"Analyzing {symbol}...")

                    # Fetch multi-timeframe DataFrames from MT5
                    weekly_df = fetch_mt5_dataframe(symbol, mt5.TIMEFRAME_W1, count=150)
                    daily_df = fetch_mt5_dataframe(symbol, mt5.TIMEFRAME_D1, count=150)
                    h4_df = fetch_mt5_dataframe(symbol, mt5.TIMEFRAME_H4, count=200)

                    # Run self-contained pipeline scan
                    pipeline = ScannerPipeline(symbol=symbol, min_rr=CONFIG["min_rr"])
                    alert = pipeline.run(weekly_df, daily_df, h4_df)

                    if alert:
                        send_telegram_alert(alert.telegram_message)
                        logger.info(f"✅ Valid setup found and alerted for {symbol}!")

                except Exception as symbol_error:
                    logger.error(f"Error scanning {symbol}: {symbol_error}")
                    continue

            if scan_count % 10 == 0:
                send_telegram_alert(f"💗 Still watching ({scan_count} cycles done) — scanning market structures.")

            time.sleep(CONFIG["scan_interval"])

    except KeyboardInterrupt:
        logger.info("Scanner stopped by user.")
        send_telegram_alert("🔴 **Scanner stopped.**")
        mt5.shutdown()


if __name__ == "__main__":
    run_live_bot()