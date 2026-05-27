# Live switch checklist

Do not use this until paper trading works exactly as expected.

## Required before live

- [ ] You understand the broker API permission setup.
- [ ] You have completed any required broker certifications or trading permissions.
- [ ] You have tested the same symbols in paper.
- [ ] You have tested the same time windows in paper.
- [ ] You have verified that inactive intents are ignored.
- [ ] You have verified that non-allowlisted symbols are rejected.
- [ ] You have verified that outside-window orders are rejected.
- [ ] You have verified that spread failures are rejected.
- [ ] You have verified that the kill switch blocks all sends.
- [ ] You have reviewed commission / fee impact for tiny order sizes.
- [ ] You have reviewed day-trading / margin / settlement rules for your account.

## Live requires

- [ ] `environment = "live"`
- [ ] `live_enabled = true`
- [ ] `IBKR_MICROEXEC_LIVE_CONFIRM=YES_I_UNDERSTAND`
- [ ] CLI includes `--send`
- [ ] No `.kill_switch` file exists

## Emergency stop

Create the kill-switch file:

```bash
touch .kill_switch
```

Or run:

```bash
python -m ibkr_microexec.cli kill --config config/trading_plan.toml
```
