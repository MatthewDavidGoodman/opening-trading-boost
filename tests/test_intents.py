from pathlib import Path

from ibkr_microexec.intents import load_trade_intents

ROOT = Path(__file__).resolve().parents[1]


def test_load_intents_example():
    intents = load_trade_intents(ROOT / "data" / "intents.example.csv")
    assert len(intents) == 2
    assert intents[0].symbol == "EXAMPLE"
    assert intents[0].active is False
