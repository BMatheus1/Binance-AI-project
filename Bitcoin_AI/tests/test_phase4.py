import asyncio
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from btc_research.external import EventCalendar, ExternalEvent
from btc_research.labeling import make_targets
from btc_research.live_market import BinancePublicCollector
from btc_research.phase4 import _binary_half, _probability_distribution
from btc_research.phase4_live import _rest_klines, _stream_kline
from btc_research.validation import assert_disjoint, split_period


def test_targets_support_15_and_30_minutes(candles):
    target = make_targets(candles, horizons=[1, 5, 15, 30])
    for horizon in [15, 30]:
        assert target[f"return_{horizon}m"].iloc[20] == pytest.approx(
            candles.close.iloc[20 + horizon] / candles.open.iloc[21] - 1)
        assert target[f"event_end_{horizon}m"].iloc[20] == candles.open_time.iloc[20] + pd.Timedelta(minutes=horizon + 1)
        assert target[f"target_{horizon}m"].tail(horizon).isna().all()


def test_30m_target_and_split_do_not_cross_gap_or_boundary(candles):
    gapped = candles.drop(index=400).reset_index(drop=True)
    target = make_targets(gapped, horizons=[30])
    assert target.target_30m.iloc[370:400].isna().all()
    frame = pd.DataFrame({"decision_time": target.decision_time,
                          "event_end_30m": target.event_end_30m,
                          "target_30m": target.target_30m}).dropna()
    left = split_period(frame, 30, None, "2024-01-01 06:00", embargo=30)
    right = split_period(frame, 30, "2024-01-01 06:00", "2024-01-01 12:00", embargo=30)
    assert_disjoint(left, right, 30)


def test_phase4_baselines_and_probability_distribution():
    y = np.array([0, 1, 2, 0, 2])
    baseline = _binary_half(y)
    assert baseline["observations"] == 4 and baseline["log_loss"] == pytest.approx(np.log(2))
    p = np.tile([.2, .1, .7], (5, 1))
    distribution = _probability_distribution(p)
    assert distribution["mean"] == pytest.approx([.2, .1, .7])
    assert distribution["max_probability_quantiles"][2] == pytest.approx(.7)


def test_public_kline_parsers():
    row = [1_700_000_000_000, "100", "102", "99", "101", "2", 1_700_000_059_999,
           "201", 12, "1.2", "121", "0"]
    frame = _rest_klines([row])
    assert frame.open.iloc[0] == 100 and frame.trades.iloc[0] == 12
    payload = {"k": {"t": row[0], "T": row[6], "o": "100", "h": "102", "l": "99", "c": "101",
                       "v": "2", "q": "201", "n": 12, "V": "1.2", "Q": "121", "x": True}}
    live = _stream_kline(payload)
    assert live.equals(frame)


def test_collector_callback_receives_persisted_event(tmp_path):
    seen = []
    collector = BinancePublicCollector(tmp_path, "wss://example.invalid", "https://example.invalid",
                                       event_callback=lambda record: seen.append(record["payload"]["a"]))
    asyncio.run(collector._handle({"stream": "btcusdt@aggTrade",
                                   "data": {"e": "aggTrade", "a": 10, "E": 1_700_000_000_000}}))
    collector.storage.flush()
    assert seen == [10]
    assert list(tmp_path.rglob("*.jsonl"))


def test_event_calendar_is_causal_and_deduplicated(tmp_path):
    now = datetime.now(timezone.utc)
    event = ExternalEvent("official", "cpi", "CPI", "", now - pd.Timedelta(minutes=2),
                          now - pd.Timedelta(minutes=1), "macro", "official", "risk filter", .8)
    calendar = EventCalendar(tmp_path / "calendar.jsonl")
    calendar.add(event)
    assert calendar.risk_at(now).level == "elevated"
    with pytest.raises(ValueError, match="registrado"):
        calendar.add(event)
