"""
Module: Strategy Execution - Stage 3+ (Inducement & Entry Logic)
Description: Handles inducement detection, POI selection, entry limit generation,
             invalidation tracking, and Risk-Reward (RR) gating.
"""

from typing import Optional, Dict, Any, List
import pandas as pd


def find_inducement_close_beyond(
        h4_df: pd.DataFrame,
        pivots_h4: list,
        direction: str,
        pip_buffer_pips: float = 0.0
) -> Optional[Dict[str, Any]]:
    """
    Detects inducement via liquidity sweep + close acceptance beyond a minor structural level.
    """
    if h4_df is None or len(h4_df) < 5 or not pivots_h4:
        return None

    closes = h4_df["close"].values
    highs = h4_df["high"].values
    lows = h4_df["low"].values
    ts = h4_df["time"].values

    # Look for a minor sweep of a recent pivot
    recent_pivots = pivots_h4[-5:]

    for p in recent_pivots:
        if direction.upper() == "BUY" and p.kind == "LOW":
            # Looking for a sweep below a swing low followed by a reclaim/close back above
            for i in range(p.idx + 1, len(h4_df) - 1):
                swept = lows[i] < p.price
                closed_back = closes[i] > p.price
                if swept and closed_back:
                    return {
                        "level": float(p.price),
                        "sweep_index": i,
                        "ts": pd.Timestamp(ts[i])
                    }

        elif direction.upper() == "SELL" and p.kind == "HIGH":
            # Looking for a sweep above a swing high followed by a reclaim/close back below
            for i in range(p.idx + 1, len(h4_df) - 1):
                swept = highs[i] > p.price
                closed_back = closes[i] < p.price
                if swept and closed_back:
                    return {
                        "level": float(p.price),
                        "sweep_index": i,
                        "ts": pd.Timestamp(ts[i])
                    }

    return None


def choose_poi_next_to_inducement(valid_zones: List[Any], inducement_level: float, direction: str) -> Optional[Any]:
    """Selects the valid POI zone associated with or immediately preceding the inducement."""
    if not valid_zones:
        return None
    # Filter zones that align with the bias and proximity to inducement
    filtered = [z for z in valid_zones if (z.bottom <= inducement_level <= z.top) or (
        z.bottom > inducement_level if direction.upper() == "SELL" else z.top < inducement_level)]
    if filtered:
        return filtered[-1]
    return valid_zones[-1]  # Fallback to the most recent zone


def build_entry_limits_from_inducement(poi: Any, direction: str, inducement_level: float, pip_size: float,
                                       offset_pips_list: tuple) -> List[float]:
    """Generates precise entry limit prices inside the POI based on offset rules."""
    limits = []
    base_price = inducement_level if inducement_level >= poi.bottom and inducement_level <= poi.top else poi.bottom

    for offset in offset_pips_list:
        if direction.upper() == "BUY":
            price = base_price + (offset * pip_size)
            if price <= poi.top:
                limits.append(round(price, 5))
        else:
            price = base_price - (offset * pip_size)
            if price >= poi.bottom:
                limits.append(round(price, 5))

    return limits if limits else [round(poi.bottom + (poi.top - poi.bottom) * 0.5, 5)]


def get_invalidation_swing_level_from_choch(pivots_h4: list, choch_level: float, direction: str) -> Optional[float]:
    """Finds the structural swing pivot anchoring the invalidation level."""
    target_kind = "HIGH" if direction.upper() == "BUY" else "LOW"
    candidates = [p.price for p in pivots_h4 if p.kind == target_kind]
    if not candidates:
        return None
    return float(candidates[-1])


def compute_sl_outside_invalidation(direction: str, invalidation_level: float, pip_size: float,
                                    buffer_pips: float = 1.5) -> float:
    """Computes stop loss slightly outside the structural invalidation level."""
    if direction.upper() == "BUY":
        return round(invalidation_level - (buffer_pips * pip_size), 5)
    else:
        return round(invalidation_level + (buffer_pips * pip_size), 5)


def compute_rr(entry: float, sl: float, tp: float) -> float:
    """Computes Risk-Reward ratio."""
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0:
        return 0.0
    return reward / risk


def execute_stage_3_entry(
        h4_df: Any,
        pivots_h4: List[Any],
        valid_zones: List[Any],
        choch: Dict[str, Any],
        bias: str,
        weekly_tp: float,
        pip_size: float = 0.0001,
        min_rr: float = 2.0
) -> Optional[Dict[str, float]]:
    """
    Evaluates market structure for Stage 3+ inducement entry and calculates
    entry limits, invalidation, stop loss, and risk-reward gating.
    """

    # 1) Find inducement using sweep + close acceptance
    inducement = find_inducement_close_beyond(
        h4_df,
        pivots_h4,
        direction=bias,
        pip_buffer_pips=0.0,
    )
    if not inducement:
        return None

    # 2) Choose POI next to the identified inducement
    selected = choose_poi_next_to_inducement(
        valid_zones,
        inducement_level=inducement["level"],
        direction=bias
    )
    if not selected:
        return None

    # 3) Build strict entry limits (1–2 pips beyond inducement and inside POI)
    entry_limits = build_entry_limits_from_inducement(
        poi=selected,
        direction=bias,
        inducement_level=inducement["level"],
        pip_size=pip_size,
        offset_pips_list=(1.0, 1.5, 2.0),
    )
    if not entry_limits:
        return None

    # Safe index check for entry_limits
    entry_ref = entry_limits[1] if len(entry_limits) > 1 else entry_limits[0]

    # 4) Invalidation = ChoCh opposite pivot level (strict anchor)
    invalidation_level = get_invalidation_swing_level_from_choch(
        pivots_h4,
        choch["level"],
        direction=bias
    )
    if invalidation_level is None:
        return None

    # 5) Compute Stop Loss (SL) slightly outside invalidation level
    sl = compute_sl_outside_invalidation(
        direction=bias,
        invalidation_level=invalidation_level,
        pip_size=pip_size,
        buffer_pips=1.5
    )

    # 6) Take Profit (TP) + Risk-Reward (RR) Gating
    tp = weekly_tp
    rr = compute_rr(entry_ref, sl, tp)
    if rr < min_rr:
        return None

    return {
        "entry": entry_ref,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "invalidation": invalidation_level
    }