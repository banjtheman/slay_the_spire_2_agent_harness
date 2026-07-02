# Slay the Spire 2 Codex Base Agent

This directory is the tuneable Codex profile for the booth demo.
Curated encounter tactics live in `ENCOUNTERS.md`; keep those notes short and
specific so they can be injected only when the current fight matches.

When invoked by `python -m agent_harness`, Codex receives a normalized game
state and must return exactly one JSON object:

```json
{
  "rationale": "short public reasoning summary",
  "action": "play_card",
  "args": {"card_index": 0, "target_index": 0},
  "expected": "short expected outcome",
  "confidence": 0.75
}
```

Guidelines:

- Prefer valid, simple actions over elaborate plans.
- Keep `rationale` display-safe and concise.
- Preserve HP aggressively unless lethal damage is available.
- Use potions before they become irrelevant. In elites, bosses, dangerous
  hallway fights, or lethal-risk turns, a potion is usually better spent than
  saved.
- Full potion slots waste future rewards. If all slots are full, be more
  willing to use a potion in combat.
- From Act 2 onward, do not carry full potion slots through heavy chip damage.
  If HP is below about 75% or incoming damage exceeds block by 10+, use
  sustain/defensive potions such as Regen or Dexterity unless lethal is
  available immediately.
- Gold is only useful when spent. With high gold, prefer shop paths and buy
  strong relics/cards/removal instead of carrying huge gold totals forward.
- If a screen says to choose several cards to remove because of Pale Tooth,
  treat it as temporary removal for upgrades after battle. Pick cards with
  valuable upgrades, not the worst junk cards you would permanently remove.
- Do not take low-impact cards just because a reward is available.
- Use exact indices from the supplied state.
- Do not call the bridge yourself; return the action JSON and let the runner
  execute it.
