
def hedge_shares(qty_alt: float, price_alt: float, price_base: float, beta_alt_on_base: float):
    if price_alt is None or price_base is None or beta_alt_on_base is None:
        return None
    if price_base == 0:
        return None
    factor_shares = beta_alt_on_base * (price_alt / price_base)
    shares_base = factor_shares * qty_alt
    return {
        "factor_shares_per_alt": float(factor_shares),
        "shares_base_for_qty_alt": float(shares_base),
    }
