# Slay the Spire 2 Encounter Research Notes

Collected: 2026-06-15

Purpose: raw source notes for future `ENCOUNTERS.md` curation. This file is not
injected into the active agent prompt. Treat it as a scratchpad of public guide
claims, community observations, and source links.

## Source Index

- Reddit reference spreadsheet thread:
  https://www.reddit.com/r/slaythespire/comments/1rq3h9a/a_slay_the_spire_2_reference_enemy_attack/
  - Reddit post links a Google Sheet:
    https://docs.google.com/spreadsheets/d/1wlhrYjH8JwfPrPd0VaekzJrdKuOXCT23UwxHcQBayVc/edit?usp=sharing
  - Claims to cover stats, move lists, attack patterns for monsters, elites,
    bosses, act encounters/events, ancient options, and miscellaneous mechanics.
  - Best candidate source for exact encounter mechanics, but should be checked
    against current game version before converting to active rules.

- Steam guide: "Slay the Spire 2 Strategy Guide: Consistency, Decision-Making,
  and Winning More Runs 3.0 By Vile"
  https://steamcommunity.com/sharedfiles/filedetails/?id=3704645422
  - Emphasizes: build for what is coming next, consistency over raw card power,
    bad-card removal, preparing for elites/bosses, and adapting to the current
    run rather than forcing builds.
  - Useful framework for harness strategy config and run memory summaries.
  - Useful phrasing: ask "what does my deck do well?", "what does it lack?",
    and "what am I about to face?"

- Steam guides landing page:
  https://steamcommunity.com/app/2868840/guides/?browsefilter=trend&browsesort=trend&p=1&requiredtags%5B0%5D=english
  - Current English guide list includes broad strategy, relics, starter deck
    piloting, enchantments, and character/build guides.
  - Useful for later manual source discovery.

- Steam discussion: "If the sandworm is a skill issue, explain how to beat it"
  https://steamcommunity.com/app/2868840/discussions/0/798965065596319256/
  - Community take: The Insatiable / sandworm is fundamentally a damage race;
    one comment reduces it to "you just hit him."
  - Low confidence as standalone tactical advice, but reinforces the anti-stall
    interpretation.

- Reddit discussion: "Can someone explain how the sandpit / sandworm thing work?"
  https://www.reddit.com/r/slaythespire/comments/1rsfihe/can_someone_explain_how_the_sandpit_sandworm/
  - Community explanation: the boss gives Frantic Escape status cards, each
    increases the countdown by 1 when played, and each individual copy gets more
    expensive after use.
  - One comment says a bloated deck above roughly 25 cards can fail to find
    enough escapes. Treat as anecdotal but strategically plausible.

- Reddit discussion: "2 times I have now died to this damn worm..."
  https://www.reddit.com/r/slaythespire/comments/1rpawrq/2_times_i_have_now_died_to_this_damn_worm_playing/
  - Community comments emphasize killing the worm rather than playing every
    Frantic Escape.
  - Useful as a direct correction to our observed agent failure.

- NeonLightsMedia: "Slay The Spire 2 Insatiable Guide"
  https://www.neonlightsmedia.com/blog/slay-the-spire-2-insatiable-boss-guide
  - Describes Sandpit as a strict instant-death timer.
  - Advises thin, consistent decks; overlarge decks bury Frantic Escape cards.
  - Notes Frantic Escape consumes energy that could be damage or block, so do
    not automatically play every escape when the timer is comfortable.
  - Warns against exhausting escape cards accidentally.
  - Advises burst damage and fast scaling because the boss also ramps normal
    attack pressure.

- Phrasemaker: "Slay the Spire 2: The Insatiable Boss Guide"
  https://thephrasemaker.com/2026/03/13/slay-the-spire-2-the-insatiable-boss-guide/
  - Describes opening Sandpit/Frantic Escape mechanic and early turn priorities.
  - Advises using draw to find Frantic Escape when needed.
  - Recommends tanking early hits if healthy because the next act heals you, and
    dragging the fight is dangerous.
  - Note conflict: this guide leans toward playing Frantic Escape whenever
    possible, while other sources argue not to spend energy on Escape when the
    timer is already safe. For the harness, prefer the conditional rule:
    "play Escape when Sandpit is low or after the main damage line."

- Untapped.gg: "Elites Intro Guide"
  https://sts2.untapped.gg/en/guides/elites-intro
  - General elite take: elites are high-value because they grant relics, more
    gold, and better rare-card odds.
  - Infested Prism note: very high HP Act 2 elite; Vital Spark gives energy the
    first time it takes attack damage each turn. Sequence attacks to exploit
    that energy while watching its block/attack alternation.

- Mobalytics boss compendium:
  https://mobalytics.gg/slay-the-spire-2/encounters/bosses
  - Work-in-progress boss index. Good for enemy names/act grouping and source
    discovery, not enough detail for active tactical rules yet.
  - Bosses listed include Ceremonial Beast, Kin Priest, Vantom, Lagavulin
    Matriarch, Soul Fysh, Waterfall Giant, Kaiser Crab, Knowledge Demon, The
    Insatiable, Doormaker, Queen, and Test Subject.

- PC Gamer: Vantom boss guide
  https://www.pcgamer.com/games/roguelike/slay-the-spire-2-vantom/
  - Vantom begins with Slippery stacks that reduce early damage instances to 1.
  - Multi-hit or low-cost attacks clear Slippery better than large single hits.
  - Attack potions can help because generated attacks persist for later fight
    use; Duplication potion is not ideal early unless desperate.
  - Damage ramps in a cycle and Wounds clog the hand. Since act-end healing is
    coming, some chip damage is acceptable, but large attack-cycle turns need
    defensive attention.

- PC Gamer: Doormaker boss guide
  https://www.pcgamer.com/games/roguelike/slay-the-spire-2-doormaker/
  - Likely outdated depending on current patch. Old guide says: kill Door first,
    use the stunned Doormaker turn for high damage/setup, avoid attrition, and
    consider delaying a Door kill to start next turn with energy for the exposed
    boss.

- Untapped.gg v0.105.0 patch article:
  https://sts2.untapped.gg/en/articles/slay-the-spire-2-v01050-patch-notes
  - Says Doormaker was replaced by Aeonglass. Current harness notes should avoid
    investing heavily in Doormaker unless the local game build still has it.

- GamesRadar / Kotaku coverage of Doormaker replacement:
  https://www.gamesradar.com/games/roguelike/slay-the-spire-2-patch-hits-the-nuclear-option-deletes-doormaker-boss-countless-players-hated-he-was-over-the-complexity-threshold-of-what-we-want/
  https://kotaku.com/slay-the-spire-2-doormaker-boss-update-aeonglass-defect-regent-buff-nerf-2000694262
  - Secondary confirmation that Doormaker was replaced by Aeonglass due to
    complexity concerns. Use only for patch-context notes, not tactics.

- Slashskill: "Slay the Spire 2 Boss Guide"
  https://www.slashskill.com/slay-the-spire-2-boss-guide-every-boss-attack-patterns-and-how-to-beat-them/
  - Broad boss guide with several specific turn-plan claims.
  - Treat as medium/low confidence until cross-checked; useful for bootstrapping
    candidate sections.

- Local shipped text:
  - `sts2-cli/localization_eng/encounters.json`
  - `sts2-cli/localization_eng/monsters.json`
  - `sts2-cli/localization_eng/powers.json`
  - `sts2-cli/localization_eng/cards.json`
  - Useful for names, ids, and mechanic text, not enough alone for strategy.

## Candidate Active Harness Rules

### General Encounter Adaptation

- First classify the fight:
  - damage race / hard timer
  - status-pressure fight
  - target-priority fight
  - scaling-pressure fight
  - disruption fight
  - mitigation/block check
- If a fight has a hard timer or escalating status pressure, generic HP
  preservation is secondary to ending the fight quickly.
- Every card choice should answer:
  - what the deck does well
  - what it lacks
  - what upcoming fight/problem it must solve
- Avoid bloating the deck with cards that do not solve immediate or upcoming
  problems.
- Shops are for refinement: card removal, key relics, key cards, and potions for
  known upcoming threats.

### The Insatiable / Sandpit / Frantic Escape

Source confidence: high, because multiple independent web/community sources
agree and the local trace confirmed this failure mode.

- This is a race. Sandpit is an instant-death timer, not a normal incoming
  damage problem.
- Frantic Escape is a resource trade:
  - upside: +1 Sandpit timer
  - downside: spends energy and each specific copy gets more expensive after use
- Do not play Frantic Escape automatically when Sandpit is already safe.
- Good default:
  - Sandpit 1-2: Escape becomes high priority unless lethal is available.
  - Sandpit 3+: prefer meaningful damage, Vulnerable, Strength, draw, or setup.
  - Sandpit 4-5: Escape is usually lower priority than racing damage unless the
    hand has no meaningful offensive line.
- Avoid playing multiple Frantic Escapes in one turn unless death is otherwise
  imminent.
- Use draw/generation potions while energy remains, not after spending energy.
- Keep enough card velocity to find Frantic Escape. Deck bloat makes the fight
  much worse.
- Be careful with random exhaust effects if Frantic Escape is needed later.
- Tanking early chip can be correct because act-end healing follows, but letting
  the fight drag is not.

### Vantom / Slippery

Source confidence: medium/high.

- Vantom starts with Slippery stacks that reduce early damage instances to 1.
- Multi-hit, low-cost, or generated attacks are better early than big single-hit
  attacks.
- Avoid wasting one big attack into Slippery unless there is no better way to
  remove stacks.
- Save strongest block or defensive potion for the large spike turn in the
  attack cycle.
- Since act-end healing follows, accept some small chip while clearing Slippery
  and building toward the damage window.
- Wounds/statuses reduce hand quality over time, so do not over-stall.

### Infested Prism

Source confidence: medium.

- Very high-HP Act 2 elite.
- Vital Spark grants energy the first time it takes Attack damage each turn.
- Sequence the first attack carefully to gain the energy before playing the rest
  of the turn.
- Watch whether the enemy is blocking or attacking; do not waste big hits into a
  block-heavy turn if a better setup/defense line exists.
- Because Vital Spark refunds energy, one low-cost attack can unlock more plays.

### Soul Fysh

Source confidence: medium/low until cross-checked.

- Status-pressure plus Intangible-window fight.
- Beckon/status management matters; exhausting or cycling statuses prevents
  unblockable damage.
- Best damage windows are before Intangible turns.
- Do not spend strong attacks into Intangible when damage is reduced to 1.
- Vulnerable/status pressure ramps over cycles, so end the fight before the deck
  becomes clogged.

### Ceremonial Beast

Source confidence: medium/low until cross-checked.

- Scaling-pressure fight with Strength increases.
- Control or exploit the stun/Ringing threshold around the major HP breakpoint.
- Do not let the fight drag if the deck cannot scale defensively.
- Prepare a burst turn before crossing the threshold.

### Kaiser Crab

Source confidence: low from Steam discussion only.

- Appears to be a damage mitigation / shield check.
- Weak is valuable against large claw hits.
- 99 shield can fall away after turn end; do not overcommit into temporary block
  if a better defensive/targeting line exists.
- Need exact mechanics from the reference sheet/local code before active rules.

### Doormaker / Aeonglass Patch Caveat

Source confidence: high for patch caveat, low for current tactics.

- Doormaker guides may be stale because v0.105.0 reportedly replaced Doormaker
  with Aeonglass.
- Before adding active rules, check the current local game build and source ids.
- If Doormaker appears in an older build:
  - kill Door to expose boss
  - use stunned/exposed turn for damage/setup
  - avoid attrition; burst during exposure windows
  - consider delaying Door kill until next turn if it lets you start boss
    exposure with full energy
- For Aeonglass, research current mechanics separately before writing rules.

## Open Research Tasks

- Pull exact encounter move patterns from the Reddit Google Sheet or local
  decompiled/game data.
- Add active `ENCOUNTERS.md` sections for:
  - Vantom
  - Infested Prism
  - Kaiser Crab
  - Knowledge Demon
  - Soul Fysh
  - Ceremonial Beast
  - current Act 3 bosses in the installed build
- Add source/confidence comments to active rules so users can distinguish
  verified local mechanics from web/community heuristics.
- Consider a dashboard "research notes" debug panel that shows which guide
  section matched the current fight.
