
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Tuple, Optional

TRADING_DAYS = 252

@dataclass
class PairMetrics:
    base: str
    alt: str
    start: str
    end: str
    n_obs: int
    ret_base: float
    ret_alt: float
    vol_base: float
    vol_alt: float
    avg_vol_base: float
    avg_vol_alt: float
    beta_alt_on_base: float
    corr: float
    r2: float
    alt_move_if_base_1pct: float
    base_move_for_alt_1pct: float
    target_ratio: Optional[float]

def _ann_vol(returns: pd.Series) -> float:
    return np.sqrt(TRADING_DAYS) * returns.std(ddof=0)

def _total_return(prices: pd.Series) -> float:
    s = prices.dropna()
    if s.empty:
        return np.nan
    return s.iloc[-1] / s.iloc[0] - 1.0

def compute_regression(x: pd.Series, y: pd.Series) -> Tuple[float, float, float]:
    df = pd.concat([x, y], axis=1).dropna()
    if df.shape[0] < 5:
        return np.nan, np.nan, np.nan
    X = df.iloc[:,0].values
    Y = df.iloc[:,1].values
    X_ = np.column_stack([np.ones_like(X), X])
    coef, *_ = np.linalg.lstsq(X_, Y, rcond=None)
    alpha_hat, beta_hat = coef[0], coef[1]
    y_hat = alpha_hat + beta_hat * X
    ss_res = float(np.sum((Y - y_hat)**2))
    ss_tot = float(np.sum((Y - Y.mean())**2))
    r2 = 1 - ss_res/ss_tot if ss_tot != 0 else np.nan
    return float(beta_hat), float(alpha_hat), float(r2)

def summarize_pair(base_close: pd.Series, alt_close: pd.Series, base_vol: pd.Series, alt_vol: pd.Series,
                   target_ratio: Optional[float], start: str, end: str) -> PairMetrics:
    base_close = base_close.dropna()
    alt_close = alt_close.dropna()
    idx = base_close.index.intersection(alt_close.index)
    base_close = base_close.loc[idx]
    alt_close = alt_close.loc[idx]

    base_ret = base_close.pct_change()
    alt_ret = alt_close.pct_change()

    avg_vol_base = base_vol.rolling(30).mean().reindex(idx).dropna()
    avg_vol_base = float(avg_vol_base.iloc[-1]) if not avg_vol_base.empty else np.nan
    avg_vol_alt  = alt_vol.rolling(30).mean().reindex(idx).dropna()
    avg_vol_alt  = float(avg_vol_alt.iloc[-1]) if not avg_vol_alt.empty else np.nan

    beta, alpha, r2 = compute_regression(base_ret, alt_ret)
    corr = pd.concat([base_ret, alt_ret], axis=1).dropna().corr().iloc[0,1] if len(base_ret.dropna())>2 else np.nan
    n_obs = int(pd.concat([base_ret, alt_ret], axis=1).dropna().shape[0])

    alt_move_if_base_1pct = beta * 0.01 if pd.notna(beta) else np.nan
    base_move_for_alt_1pct = (0.01 / beta) if (pd.notna(beta) and beta!=0) else np.nan

    return PairMetrics(
        base=base_close.name,
        alt=alt_close.name,
        start=str(pd.to_datetime(start).date()),
        end=str(pd.to_datetime(end).date()),
        n_obs=n_obs,
        ret_base=_total_return(base_close),
        ret_alt=_total_return(alt_close),
        vol_base=_ann_vol(base_ret.dropna()),
        vol_alt=_ann_vol(alt_ret.dropna()),
        avg_vol_base=avg_vol_base,
        avg_vol_alt=avg_vol_alt,
        beta_alt_on_base=float(beta) if pd.notna(beta) else np.nan,
        corr=float(corr) if pd.notna(corr) else np.nan,
        r2=float(r2) if pd.notna(r2) else np.nan,
        alt_move_if_base_1pct=float(alt_move_if_base_1pct) if pd.notna(alt_move_if_base_1pct) else np.nan,
        base_move_for_alt_1pct=float(base_move_for_alt_1pct) if pd.notna(base_move_for_alt_1pct) else np.nan,
        target_ratio=target_ratio
    )
