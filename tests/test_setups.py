from decimal import Decimal

from opening_trading_boost.setups import load_trade_setups


def test_load_final_project_setups():
    setups = load_trade_setups("data/final_project_trade_setups.csv")
    ids = {s.setup_id for s in setups}
    assert "SOUN_OPEN_RECLAIM" in ids
    assert "KOSS_LIQUIDITY_REJECT" in ids
    soun = next(s for s in setups if s.setup_id == "SOUN_OPEN_RECLAIM")
    assert soun.symbol == "SOUN"
    assert soun.live_enabled is True
    assert soun.max_notional_live == Decimal("250")
    koss = next(s for s in setups if s.setup_id == "KOSS_LIQUIDITY_REJECT")
    assert koss.live_enabled is False
