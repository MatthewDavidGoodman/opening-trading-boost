from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from opening_trading_boost.features import FeatureConfig, build_features_for_frame


def test_build_features_for_frame_has_labels_and_time_fields():
    start = datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc)
    rows = []
    for i in range(40):
        price = 10 + i * 0.02
        rows.append(
            {
                "datetime": start + timedelta(minutes=5 * i),
                "open": price,
                "high": price + 0.05,
                "low": price - 0.05,
                "close": price + 0.01,
                "volume": 1000 + i * 10,
            }
        )
    df = pd.DataFrame(rows)
    features = build_features_for_frame(df, "TEST", FeatureConfig(forward_bars=3))
    assert {"symbol", "ret_1", "rel_volume_20", "label_forward_up", "minute_of_day_et"}.issubset(
        features.columns
    )
    assert features["symbol"].eq("TEST").all()
    assert len(features) > 0
