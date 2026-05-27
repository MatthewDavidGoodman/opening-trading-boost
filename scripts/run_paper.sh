#!/usr/bin/env bash
set -euo pipefail

python -m ibkr_microexec.cli validate-config --config config/trading_plan.toml
python -m ibkr_microexec.cli review-intents --config config/trading_plan.toml --intents data/intents.csv
python -m ibkr_microexec.cli run-once --config config/trading_plan.toml --intents data/intents.csv --broker ibkr --audit logs/audit.jsonl
