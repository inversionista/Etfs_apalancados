
import numpy as np
import pandas as pd
from sklearn.linear_model import TheilSenRegressor
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

def returns(series: pd.Series) -> pd.Series:
    return series.pct_change().dropna()

def rolling_beta(x_ret: pd.Series, y_ret: pd.Series, window: int=60) -> pd.Series:
    df = pd.concat([x_ret, y_ret], axis=1).dropna()
    df.columns = ["x","y"]
    betas = []
    idxs = []
    for i in range(window, len(df)+1):
        win = df.iloc[i-window:i]
        X = sm.add_constant(win["x"].values)
        model = sm.OLS(win["y"].values, X).fit()
        betas.append(model.params[1])
        idxs.append(win.index[-1])
    return pd.Series(betas, index=idxs, name="beta_rolling")

def beta_ols(x_ret: pd.Series, y_ret: pd.Series) -> float:
    df = pd.concat([x_ret, y_ret], axis=1).dropna()
    df.columns = ["x","y"]
    X = sm.add_constant(df["x"].values)
    model = sm.OLS(df["y"].values, X).fit()
    return float(model.params[1])

def beta_robust_theilsen(x_ret: pd.Series, y_ret: pd.Series) -> float:
    df = pd.concat([x_ret, y_ret], axis=1).dropna()
    df.columns = ["x","y"]
    model = TheilSenRegressor()
    model.fit(df[["x"]].values, df["y"].values)
    return float(model.coef_[0])

def beta_wls(x_ret: pd.Series, y_ret: pd.Series) -> float:
    df = pd.concat([x_ret, y_ret], axis=1).dropna()
    df.columns = ["x","y"]
    vol = df["y"].rolling(20).std().fillna(df["y"].std())
    w = 1.0/(vol**2).replace(0, np.nan).fillna((vol**2).mean())
    X = sm.add_constant(df["x"].values)
    model = sm.WLS(df["y"].values, X, weights=w.values).fit()
    return float(model.params[1])

def hedge_ratio_cointegration(x_price: pd.Series, y_price: pd.Series):
    lx = np.log(x_price.dropna()); ly = np.log(y_price.dropna())
    idx = lx.index.intersection(ly.index)
    lx, ly = lx.loc[idx], ly.loc[idx]
    X = sm.add_constant(lx.values)
    model = sm.OLS(ly.values, X).fit()
    beta = float(model.params[1])
    resid = ly.values - (model.params[0] + beta*lx.values)
    adf_stat, pval, *_ = adfuller(resid, maxlag=1, regression="c", autolag="AIC")
    return {"beta": beta, "adf_stat": float(adf_stat), "pvalue": float(pval)}

def simulate_hedge_pnl(qty_alt: float, qty_base: float, alt_price: pd.Series, base_price: pd.Series) -> pd.DataFrame:
    alt_pnl = qty_alt * alt_price.diff().fillna(0.0)
    base_pnl = qty_base * base_price.diff().fillna(0.0)
    pnl = alt_pnl + base_pnl
    df = pd.DataFrame({"alt_pnl": alt_pnl, "base_pnl": base_pnl, "total_pnl": pnl})
    df["cum_pnl"] = df["total_pnl"].cumsum()
    return df

def hedge_effectiveness(unhedged_ret: pd.Series, hedged_ret: pd.Series) -> float:
    v_u = float(unhedged_ret.dropna().var())
    v_h = float(hedged_ret.dropna().var())
    if v_u == 0:
        return float("nan")
    return 1.0 - (v_h / v_u)
