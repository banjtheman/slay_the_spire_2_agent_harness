# Agent Harness

This layer runs tuneable agents against the visible Slay the Spire 2 bridge.
Each harness receives the current normalized game state and must return one JSON
action.

Supported harnesses:

- `codex-cli`: calls `codex exec` with schema-constrained output.
- `claude-code`: calls `claude -p` with `--json-schema`.
- `cursor-cli`: calls `cursor-agent -p`; requires `cursor-agent login` or
  `CURSOR_API_KEY`.

## Check Setup

```bash
python -m agent_harness doctor
```

## Ask An Agent For One Move Without Touching The Game

```bash
python -m agent_harness decide \
  --harness codex-cli \
  --state-file agent_harness/examples/sample_combat_state.json
```

Claude Code:

```bash
python -m agent_harness decide \
  --harness claude-code \
  --model sonnet \
  --state-file agent_harness/examples/sample_combat_state.json
```

Cursor Agent:

```bash
python -m agent_harness decide \
  --harness cursor-cli \
  --model composer-2.5-fast \
  --state-file agent_harness/examples/sample_combat_state.json
```

Cursor model ids encode the thinking/speed tier, so choose exact ids from:

```bash
cursor-agent models
```

Useful starting points:

- `composer-2.5-fast`
- `composer-2.5`
- `gpt-5.5-medium`
- `gpt-5.5-high`
- `gpt-5.5-extra-high`
- `claude-opus-4-8-thinking-high`
- `claude-4.6-sonnet-medium-thinking`

## Ask An Agent For One Live Move

Dry-run mode logs the decision but does not apply it:

```bash
python -m agent_harness run --harness codex-cli --max-steps 1
```

Apply the action to the visible game:

```bash
python -m agent_harness run --harness codex-cli --max-steps 1 --execute
```

Run several visible actions:

```bash
python -m agent_harness run --harness cursor-cli --model composer-2.5-fast --max-steps 10 --execute
```

Start a fresh visible run first:

```bash
python -m agent_harness run --start-run --character IRONCLAD --ascension 0 --max-steps 10 --execute
```

Trace files are written to `agent_runs/*.jsonl`. They include normalized state
snapshots, public rationale, selected actions, CLI command metadata, tool events
when available, bridge results, and errors. The dashboard tails these files to
show the agent's public reasoning, usage, and tool calls.

If you rebuild or reinstall `STS2_Bridge`, fully restart Slay the Spire 2 before
testing. The running game process keeps the old DLL loaded.

## Tune Agent Profiles

Edit:

```text
agent_profiles/codex_base/AGENTS.md
```

That directory is passed as the harness working directory. You can make alternate
profiles by copying the directory and passing:

```bash
python -m agent_harness run --agent-workdir agent_profiles/my_profile --max-steps 1
```
