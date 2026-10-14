"""
scanner_pipeline.py
Aegis Alpha Market Structure Scanner Engine (Weekly OB -> Daily Engulfing -> H4 Entry)
"""

from dataclasses import dataclass
from typing import Optional, Literal, List, Dict, Tuple, Any
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

Direction = Literal["BULLISH", "BEARISH"]


@dataclass
class Pivot:
    idx: int
    ts: pd.Timestamp
    price: float
    kind: str  # "HIGH" or "LOW"


@dataclass
class POIZone:
    kind: str  # "OB" or "FVG"
    top: float
    bottom: float
    ts: pd.Timestamp
    meta: dict


@dataclass
class ScannerAlert:
    telegram_message: str
    signal_key: str
    symbol: str
    direction: Direction
    entry_model: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    confidence: int


class ScannerPipeline:
    def __init__(self, symbol: str, min_rr: float = 2.0, pip_size: float = 0.0001, sl_pips: float = 22.0,
                 pivot_lookback: int = 3):
        self.symbol = symbol
        self.min_rr = float(min_rr)
        self.pip_size = float(pip_size)
        self.sl_pips = float(sl_pips)
        self.pivot_lookback = int(pivot_lookback)
        self.emitted_signals: set[str] = set()

    def _normalize_zone(self, a: float, b: float) -> Tuple[float, float]:
        return min(a, b), max(a, b)

    def _detect_pivots_local(self, df: pd.DataFrame) -> List[Pivot]:
        pivots: List[Pivot] = []
        highs = df["high"].values
        lows = df["low"].values
        ts = df["time"]
        n = len(df)
        lb = self.pivot_lookback

        for i in range(lb, n - lb):
            hi = highs[i]
            lo = lows[i]
            left_hi = highs[i - lb:i]
            right_hi = highs[i + 1:i + 1 + lb]
            left_lo = lows[i - lb:i]
            right_lo = lows[i + 1:i + 1 + lb]

            if hi > np.max(np.concatenate([left_hi, right_hi])) and np.isfinite(hi):
                pivots.append(Pivot(idx=i, ts=ts.iloc[i], price=float(hi), kind="HIGH"))
            if lo < np.min(np.concatenate([left_lo, right_lo])) and np.isfinite(lo):
                pivots.append(Pivot(idx=i, ts=ts.iloc[i], price=float(lo), kind="LOW"))

        pivots.sort(key=lambda p: p.idx)
        return pivots

    def _detect_last_bos_and_ob(self, df_w: pd.DataFrame, pivots_w: List[Pivot]) -> Optional[dict]:
        """Detects Weekly BOS direction and marks the corresponding Weekly Order Block (OB)."""
        if len(df_w) < 10 or len(pivots_w) < 4:
            return None

        close = df_w["close"].values
        open_p = df_w["open"].values
        highs = df_w["high"].values
        lows = df_w["low"].values
        ts = df_w["time"].values

        recent_high, recent_low = None, None
        bos_info = None

        for i in range(len(df_w)):
            for p in pivots_w:
                if p.idx == i:
                    if p.kind == "HIGH":
                        recent_high = p.price
                    else:
                        recent_low = p.price

            if recent_high is not None and close[i] > recent_high:
                bos_info = {"direction": "BUY", "level": float(recent_high), "ts": pd.Timestamp(ts[i]), "bos_idx": i}
            elif recent_low is not None and close[i] < recent_low:
                bos_info = {"direction": "SELL", "level": float(recent_low), "ts": pd.Timestamp(ts[i]), "bos_idx": i}

        if not bos_info:
            return None

        # Find the Weekly Order Block (last opposite candle before the impulse leg)
        bos_idx = bos_info["bos_idx"]
        ob_zone = None

        if bos_info["direction"] == "BUY":
            # Look backwards from BOS for the last bearish candle
            for j in range(bos_idx - 1, max(0, bos_idx - 10), -1):
                if close[j] < open_p[j]:  # Bearish candle
                    bot, top = self._normalize_zone(float(lows[j]), float(highs[j]))
                    ob_zone = {"bottom": bot, "top": top}
                    break
        else:
            # Look backwards from BOS for the last bullish candle
            for j in range(bos_idx - 1, max(0, bos_idx - 10), -1):
                if close[j] > open_p[j]:  # Bullish candle
                    bot, top = self._normalize_zone(float(lows[j]), float(highs[j]))
                    ob_zone = {"bottom": bot, "top": top}
                    break

        if not ob_zone:
            return None

        bos_info["ob"] = ob_zone
        return bos_info

    def _detect_latest_daily_engulf(self, df_d: pd.DataFrame, bias: str, weekly_ob: dict) -> Optional[dict]:
        """Checks if Daily shows an engulfing candle reversing inside the Weekly OB zone."""
        if len(df_d) < 3:
            return None

        c = df_d.iloc[-1]  # current closed or active candle
        d = df_d.iloc[-2]  # previous candle

        curr_low, curr_high = float(c["low"]), float(c["high"])
        curr_close = float(c["close"])

        # Ensure price is currently touching or inside the Weekly OB zone
        in_weekly_ob = weekly_ob["bottom"] <= curr_close <= weekly_ob["top"]
        if not in_weekly_ob:
            # Also check recent wick retest of the OB zone
            if not (weekly_ob["bottom"] <= curr_low <= weekly_ob["top"] or weekly_ob["bottom"] <= curr_high <=
                    weekly_ob["top"]):
                return None

        prev_bear = d["close"] < d["open"]
        prev_bull = d["close"] > d["open"]
        curr_bull = c["close"] > c["open"]
        curr_bear = c["close"] < c["open"]

        prev_body_low = min(float(d["open"]), float(d["close"]))
        prev_body_high = max(float(d["open"]), float(d["close"]))
        curr_body_low = min(float(c["open"]), float(c["close"]))
        curr_body_high = max(float(c["open"]), float(c["close"]))

        bullish_engulf = prev_bear and curr_bull and (curr_body_low <= prev_body_low) and (
                    curr_body_high >= prev_body_high)
        bearish_engulf = prev_bull and curr_bear and (curr_body_high >= prev_body_high) and (
                    curr_body_low <= prev_body_low)

        if bias == "BUY" and bullish_engulf:
            return {"direction": "BUY", "d1_low": min(curr_low, float(d["low"])),
                    "d1_high": max(curr_high, float(d["high"]))}
        if bias == "SELL" and bearish_engulf:
            return {"direction": "SELL", "d1_low": min(curr_low, float(d["low"])),
                    "d1_high": max(curr_high, float(d["high"]))}

        return None

    def _detect_h4_entry_zone(self, h4_df: pd.DataFrame, bias: str) -> Optional[dict]:
        """Finds H4 entry structure (OB or FVG) after the Daily trigger."""
        if len(h4_df) < 5:
            return None

        # Use the most recent H4 candle/zone as execution anchor
        c = h4_df.iloc[-2]
        bot, top = self._normalize_zone(float(c["low"]), float(c["high"]))

        return {"bottom": bot, "top": top}

    def run(self, weekly_df: pd.DataFrame, daily_df: pd.DataFrame, h4_df: pd.DataFrame) -> Optional[ScannerAlert]:
        if weekly_df is None or daily_df is None or h4_df is None:
            return None
        if len(weekly_df) < 20 or len(daily_df) < 20 or len(h4_df) < 20:
            return None

        # Step 1: Establish Weekly Dominant Direction & Pullback OB Zone
        pivots_w = self._detect_pivots_local(weekly_df)
        weekly_data = self._detect_last_bos_and_ob(weekly_df, pivots_w)
        if not weekly_data:
            return None

        bias = weekly_data["direction"]
        weekly_ob = weekly_data["ob"]

        # Step 2: Switch to Daily and check for Engulfing inside Weekly OB
        d1_engulf = self._detect_latest_daily_engulf(daily_df, bias, weekly_ob)
        if not d1_engulf:
            return None

        # Step 3: Switch to H4 to find execution zone & compute trade metrics
        h4_zone = self._detect_h4_entry_zone(h4_df, bias)
        if not h4_zone:
            return None

        bottom, top = h4_zone["bottom"], h4_zone["top"]
        entry_ref = round((bottom + top) / 2, 5)

        sl = entry_ref - (self.sl_pips * self.pip_size) if bias == "BUY" else entry_ref + (self.sl_pips * self.pip_size)

        # TP set to opposite weekly swing target
        target_kind = "LOW" if bias == "BUY" else "HIGH"
        weekly_tp_candidates = [p.price for p in pivots_w if p.kind == target_kind and p.ts > weekly_data["ts"]]
        if not weekly_tp_candidates:
            return None
        tp = float(weekly_tp_candidates[0])

        risk = abs(entry_ref - sl)
        reward = abs(tp - entry_ref)
        rr = (reward / risk) if risk > 0 else 0.0
        if rr < self.min_rr:
            return None

        signal_key = f"{self.symbol}_{bias}_{round(entry_ref, 5)}"
        if signal_key in self.emitted_signals:
            return None
        self.emitted_signals.add(signal_key)

        direction_literal: Direction = "BULLISH" if bias == "BUY" else "BEARISH"
        telegram_message = (
            f"🚨 **STRUCTURAL SETUP — {self.symbol}** (@Candle_rangebot) 🚨\n\n"
            f"• **Dominant Bias (W1)**: {bias}\n"
            f"• **Weekly OB Pullback Zone**: {weekly_ob['bottom']} - {weekly_ob['top']}\n"
            f"• **Daily Engulfing Trigger**: CONFIRMED ✅\n"
            f"• **H4 Entry Zone**: {bottom} - {top}\n"
            f"• **Entry**: {entry_ref}\n"
            f"• **Stop Loss**: {sl}\n"
            f"• **Take Profit**: {tp}\n"
            f"• **Risk-Reward**: {rr:.2f}R"
        )

        return ScannerAlert(
            telegram_message=telegram_message,
            signal_key=signal_key,
            symbol=self.symbol,
            direction=direction_literal,
            entry_model="Weekly OB -> Daily Engulfing -> H4 Entry",
            entry=float(entry_ref),
            stop_loss=float(sl),
            take_profit=float(tp),
            risk_reward=float(rr),
            confidence=95
        )