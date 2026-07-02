# Live Bridge Mode

Live bridge mode controls the real visible Slay the Spire 2 app through the
`STS2_Bridge` in-game mod. It is separate from `sts2-cli` headless mode.

## Install the In-Game Bridge

```bash
./scripts/setup_live_bridge.sh
```

Then launch Slay the Spire 2 from Steam and enable `STS2_Bridge` in the game's
mod manager. The bridge listens on:

```text
http://localhost:15526/api/v1/singleplayer
```

## Check Connectivity

```bash
python3 -m live_bridge doctor
python3 -m live_bridge state
```

If `doctor.ok` is `true`, the visible-game backend is ready.

## Start a Visible Run

```bash
python3 -m live_bridge start-run --character IRONCLAD --ascension 0
```

## Send Actions

Native live action names:

```bash
python3 -m live_bridge action choose_map_node --arg index=0
python3 -m live_bridge action play_card --arg card_index=0 --arg target=jaw_worm_0
python3 -m live_bridge action end_turn
```

Headless-style JSON commands are also accepted:

```bash
python3 -m live_bridge send-json '{"cmd":"action","action":"end_turn"}'
python3 -m live_bridge send-json '{"cmd":"action","action":"play_card","args":{"card_index":0,"target_index":0}}'
```

For agent processes, use newline-delimited JSON:

```bash
python3 -m live_bridge repl
```

Each input line should be a JSON command object. Each output line is the latest
normalized game state.

## Backend Contract

`LiveSts2Client.send(command)` accepts these command shapes:

- `{"cmd":"state"}`
- `{"cmd":"raw_state"}`
- `{"cmd":"start_run","character":"Ironclad","ascension":0}`
- `{"cmd":"continue_game"}`
- `{"cmd":"quit"}`
- `{"cmd":"action","action":"...","args":{...}}`

Common `sts2-cli` actions are translated where possible, including:

- `play_card`
- `use_potion`
- `end_turn`
- `select_map_node`
- `choose_option`
- `select_card_reward`
- `skip_card_reward`
- `select_cards`
- `skip_select`
- `buy_card`
- `buy_relic`
- `buy_potion`
- `remove_card`
- `leave_room`
- `proceed`

The normalized state uses familiar decision names like `menu`, `map_select`,
`combat_play`, `event_choice`, `rest_site`, `shop`, `combat_rewards`,
`card_reward`, `card_select`, `hand_select`, `relic_select`, `treasure`, and
`game_over`.

## Codex Agent Harness

The first tuneable agent runner lives in `agent_harness/`.

```bash
python -m agent_harness doctor
python -m agent_harness decide --state-file agent_harness/examples/sample_combat_state.json
python -m agent_harness run --max-steps 1
python -m agent_harness run --max-steps 1 --execute
```

Edit `agent_profiles/codex_base/AGENTS.md` to tune the Codex profile. Agent run
traces are written as JSONL under `agent_runs/`. The dashboard displays state
snapshots, public rationales, selected actions, usage, tool events, and bridge
results.

After reinstalling or rebuilding the bridge DLL, fully restart Slay the Spire 2
before testing. The running game process keeps the old DLL loaded.
