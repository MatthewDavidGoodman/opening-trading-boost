#!/usr/bin/env bash
set -euo pipefail
pytest -q
python -m ibkr_microexec.cli validate-config --config config/trading_plan.example.toml
python -m ibkr_microexec.cli review-intents --config config/trading_plan.example.toml --intents data/intents.example.csv
