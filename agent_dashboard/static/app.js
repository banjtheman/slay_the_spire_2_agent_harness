const state = {
  activeRunId: null,
  offset: 0,
  polling: null,
  seen: 0,
  sidebarCollapsed: localStorage.getItem("sts2-sidebar-collapsed") === "1",
  promptDirty: false,
  promptLoading: false,
};

const $ = (id) => document.getElementById(id);

function fmtTokens(value) {
  const n = Number(value || 0);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function usageParts(usage = {}) {
  const input = Number(usage.input_tokens || 0);
  const cached = Number(usage.cached_input_tokens || 0);
  const output = Number(usage.output_tokens || 0);
  return {
    input,
    cached,
    billableInput: Math.max(0, input - cached),
    output,
  };
}

function fmtUsageSplit(usage = {}) {
  const parts = usageParts(usage);
  return `Input ${fmtTokens(parts.input)} (${fmtTokens(parts.cached)} cached, ${fmtTokens(parts.billableInput)} billable) · Output ${fmtTokens(parts.output)}`;
}

function fmtTime(ms) {
  const seconds = Math.round(Number(ms || 0) / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function fmtCost(value) {
  if (value === null || value === undefined) return "--";
  return `$${Number(value).toFixed(4)}`;
}

function humanize(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function fmtPercent(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${Math.round(n * 100)}%`;
}

function compactList(values, fallback) {
  const items = Array.isArray(values) ? values.filter(Boolean) : [];
  return items.length ? items.join(", ") : fallback;
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = value;
}

function selectedModelConfig() {
  const harness = $("harness-select")?.value || "codex-cli";
  const model = $("model-select")?.value || "";
  const options = MODEL_CATALOG[harness] || MODEL_CATALOG["codex-cli"];
  return {
    harness,
    selected: options.find((item) => item.id === model) || options[0],
  };
}

const MODEL_CATALOG = {
  "codex-cli": [
    {
      id: "gpt-5.5",
      label: "GPT-5.5",
      defaultEffort: "medium",
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "xhigh"]],
    },
    {
      id: "gpt-5",
      label: "GPT-5",
      defaultEffort: "medium",
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "xhigh"]],
    },
    {
      id: "gpt-5.4-mini",
      label: "GPT-5.4 Mini",
      defaultEffort: "medium",
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "xhigh"]],
    },
  ],
  "claude-code": [
    {
      id: "sonnet",
      label: "Claude Sonnet",
      defaultEffort: "medium",
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "xhigh"], ["max", "max"]],
    },
    {
      id: "opus",
      label: "Claude Opus",
      defaultEffort: "high",
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "xhigh"], ["max", "max"]],
    },
    {
      id: "claude-haiku-4-5",
      label: "Claude Haiku 4.5",
      defaultEffort: "low",
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"]],
    },
    {
      id: "fable",
      label: "Claude Fable",
      defaultEffort: "medium",
      efforts: [["medium", "adaptive/default"], ["high", "high"], ["xhigh", "xhigh"], ["max", "max"]],
    },
  ],
  "cursor-cli": [
    {
      id: "composer-2.5",
      label: "Composer 2.5",
      defaultEffort: "fast",
      variants: { standard: "composer-2.5", fast: "composer-2.5-fast" },
      efforts: [["standard", "standard"], ["fast", "fast"]],
    },
    {
      id: "gpt-5.5",
      label: "GPT-5.5",
      defaultEffort: "medium",
      variants: {
        none: "gpt-5.5-none",
        low: "gpt-5.5-low",
        medium: "gpt-5.5-medium",
        high: "gpt-5.5-high",
        xhigh: "gpt-5.5-extra-high",
        "medium-fast": "gpt-5.5-medium-fast",
        "high-fast": "gpt-5.5-high-fast",
        "xhigh-fast": "gpt-5.5-extra-high-fast",
      },
      efforts: [["none", "none"], ["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "extra high"], ["medium-fast", "medium fast"], ["high-fast", "high fast"], ["xhigh-fast", "extra high fast"]],
    },
    {
      id: "claude-opus-4-8",
      label: "Claude Opus 4.8",
      defaultEffort: "high",
      variants: {
        low: "claude-opus-4-8-low",
        medium: "claude-opus-4-8-medium",
        high: "claude-opus-4-8-high",
        xhigh: "claude-opus-4-8-xhigh",
        max: "claude-opus-4-8-max",
        "thinking-low": "claude-opus-4-8-thinking-low",
        "thinking-medium": "claude-opus-4-8-thinking-medium",
        "thinking-high": "claude-opus-4-8-thinking-high",
        "thinking-xhigh": "claude-opus-4-8-thinking-xhigh",
        "thinking-max": "claude-opus-4-8-thinking-max",
      },
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "extra high"], ["max", "max"], ["thinking-low", "thinking low"], ["thinking-medium", "thinking medium"], ["thinking-high", "thinking high"], ["thinking-xhigh", "thinking extra high"], ["thinking-max", "thinking max"]],
    },
    {
      id: "claude-4.6-sonnet",
      label: "Claude Sonnet 4.6",
      defaultEffort: "medium",
      variants: { medium: "claude-4.6-sonnet-medium", thinking: "claude-4.6-sonnet-medium-thinking" },
      efforts: [["medium", "medium"], ["thinking", "thinking"]],
    },
    {
      id: "claude-4.5-sonnet",
      label: "Claude Sonnet 4.5",
      defaultEffort: "default",
      variants: { default: "claude-4.5-sonnet", thinking: "claude-4.5-sonnet-thinking" },
      efforts: [["default", "default"], ["thinking", "thinking"]],
    },
    {
      id: "gpt-5.4",
      label: "GPT-5.4",
      defaultEffort: "medium",
      variants: {
        low: "gpt-5.4-low",
        medium: "gpt-5.4-medium",
        high: "gpt-5.4-high",
        xhigh: "gpt-5.4-xhigh",
        "medium-fast": "gpt-5.4-medium-fast",
        "high-fast": "gpt-5.4-high-fast",
      },
      efforts: [["low", "low"], ["medium", "medium"], ["high", "high"], ["xhigh", "extra high"], ["medium-fast", "medium fast"], ["high-fast", "high fast"]],
    },
    {
      id: "auto",
      label: "Auto",
      defaultEffort: "auto",
      variants: { auto: "auto" },
      efforts: [["auto", "auto"]],
    },
  ],
};

function updateModelOptions() {
  const harness = $("harness-select")?.value || "codex-cli";
  const model = $("model-select");
  const reasoning = $("reasoning-select");
  if (!model || !reasoning) return;
  const current = model.value;
  const options = MODEL_CATALOG[harness] || MODEL_CATALOG["codex-cli"];
  model.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    return option;
  }));
  if (options.some((item) => item.id === current)) {
    model.value = current;
  } else {
    model.value = options[0].id;
  }
  updateReasoningOptions();
}

function updateReasoningOptions() {
  const reasoning = $("reasoning-select");
  if (!reasoning) return;
  const { harness, selected } = selectedModelConfig();
  const current = reasoning.value;
  reasoning.replaceChildren(...selected.efforts.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
  reasoning.value = selected.efforts.some(([value]) => value === current) ? current : selected.defaultEffort;
  setText("reasoning-label", harness === "cursor-cli" ? "Variant" : "Reasoning");
  updateResolvedModelHint();
}

function resolveSelectedModel() {
  const effort = $("reasoning-select")?.value || "";
  const { selected } = selectedModelConfig();
  if (selected?.variants) return selected.variants[effort] || selected.variants[selected.defaultEffort] || selected.id;
  return selected?.id || "";
}

function updateResolvedModelHint() {
  const { harness } = selectedModelConfig();
  const resolved = resolveSelectedModel();
  const hint = harness === "cursor-cli"
    ? `Exact Cursor model id: ${resolved}`
    : `Model id: ${resolved}`;
  setText("model-resolved", hint);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

async function loadProfiles() {
  const select = $("profile-select");
  if (!select) return;
  try {
    const data = await api("/api/profiles");
    const profiles = Array.isArray(data.profiles) ? data.profiles : [];
    if (profiles.length) {
      const current = select.value;
      select.replaceChildren(...profiles.map((profile) => {
        const option = document.createElement("option");
        option.value = profile.agent_workdir;
        option.textContent = profile.label || profile.name || profile.agent_workdir;
        return option;
      }));
      select.value = profiles.some((profile) => profile.agent_workdir === current)
        ? current
        : profiles[0].agent_workdir;
    }
    await loadPrompt();
  } catch (err) {
    setPromptStatus(err.message);
  }
}

async function loadPrompt() {
  const select = $("profile-select");
  const editor = $("agents-md-editor");
  if (!select || !editor) return;
  state.promptLoading = true;
  editor.disabled = true;
  setPromptStatus("loading");
  try {
    const data = await api(`/api/profile?agent_workdir=${encodeURIComponent(select.value)}`);
    const profile = data.profile || {};
    editor.value = profile.agents_md || "";
    state.promptDirty = false;
    setPromptStatus(profile.agents_path || "AGENTS.md");
  } catch (err) {
    editor.value = "";
    state.promptDirty = false;
    setPromptStatus(err.message);
  } finally {
    state.promptLoading = false;
    editor.disabled = false;
  }
}

async function savePrompt({ silent = false } = {}) {
  const select = $("profile-select");
  const editor = $("agents-md-editor");
  if (!select || !editor || state.promptLoading) return false;
  if (!silent) setPromptStatus("saving");
  try {
    const data = await api("/api/profile", {
      method: "POST",
      body: JSON.stringify({
        agent_workdir: select.value,
        agents_md: editor.value,
      }),
    });
    state.promptDirty = false;
    const profile = data.profile || {};
    setPromptStatus(silent ? profile.agents_path || "AGENTS.md" : "saved");
    return true;
  } catch (err) {
    setPromptStatus(err.message);
    return false;
  }
}

function setPromptStatus(value) {
  setText("prompt-status", value || "AGENTS.md");
}

async function refreshStatus() {
  try {
    const data = await api("/api/status");
    const bridge = data.bridge || {};
    setText("bridge-status", bridge.ok ? `Bridge ok at ${bridge.base_url}` : bridge.error || "Bridge offline");
    const current = data.current_state || {};
    const decision = current.decision || bridge.decision || "unknown";
    setText("state-chip", decision);
    setText("live-status", decision);
    setText("hero-subtitle", describeLiveState(current, bridge));
    $("state-json").textContent = JSON.stringify(current, null, 2);
    const context = current.context || {};
    setText("floor-label", context.floor == null ? "floor --" : `floor ${context.floor}`);
    if (!state.activeRunId) {
      setText("current-status", current.decision || "idle");
    }
    const running = (data.runs || []).find((run) => ["queued", "running", "stopping"].includes(run.status));
    const latest = (data.runs || [])[0];
    if (!state.activeRunId && (running || latest)) attachRun((running || latest).id);
  } catch (err) {
    setText("bridge-status", err.message);
    setText("state-chip", "offline");
    setText("live-status", "offline");
    setText("hero-subtitle", "Bridge connection is offline.");
  }
}

function collectForm() {
  const form = new FormData($("run-form"));
  const pricing = {
    input_per_million: form.get("input_per_million"),
    cached_input_per_million: form.get("cached_input_per_million"),
    output_per_million: form.get("output_per_million"),
  };
  const harness = String(form.get("harness") || "codex-cli");
  return {
    harness,
    model: resolveSelectedModel(),
    reasoning_effort: harness === "cursor-cli" ? "medium" : form.get("reasoning_effort"),
    model_family: form.get("model"),
    model_variant: form.get("reasoning_effort"),
    agent_workdir: form.get("agent_workdir"),
    character: form.get("character"),
    ascension: Number(form.get("ascension")),
    max_steps: Number(form.get("max_steps")),
    step_delay: Number(form.get("step_delay")),
    start_run: form.get("start_run") === "on",
    allow_tools: form.get("allow_tools") === "on",
    web_search: form.get("web_search") === "on",
    execute: true,
    strategy: {
      risk: form.get("risk"),
      map_priority: form.get("map_priority"),
      potion_policy: form.get("potion_policy"),
    },
    pricing,
  };
}

function setRunControls(running) {
  $("play-button").disabled = running;
  $("stop-button").disabled = !running;
}

function attachRun(runId) {
  state.activeRunId = runId;
  state.offset = 0;
  state.seen = 0;
  $("timeline").innerHTML = "";
  $("event-count").textContent = "0 events";
  setRunControls(true);
  if (state.polling) clearInterval(state.polling);
  state.polling = setInterval(pollRun, 1200);
  pollRun();
}

async function pollRun() {
  if (!state.activeRunId) return;
  try {
    const [runData, eventsData] = await Promise.all([
      api(`/api/runs/${state.activeRunId}`),
      api(`/api/runs/${state.activeRunId}/events?offset=${state.offset}`),
    ]);
    const run = runData.run || {};
    const summary = eventsData.summary || runData.summary || {};
    state.offset = eventsData.offset || state.offset;
    renderSummary(run, summary);
    for (const event of eventsData.events || []) appendEvent(event);
    if (["completed", "failed", "stopped"].includes(run.status)) {
      clearInterval(state.polling);
      state.polling = null;
      setRunControls(false);
      if (run.status === "failed") appendEvent({ event: "agent_error", error: run.error, ts: new Date().toISOString() });
    }
  } catch (err) {
    appendEvent({ event: "agent_error", error: err.message, ts: new Date().toISOString() });
  }
}

function renderSummary(run, summary) {
  $("run-title").textContent = `${run.status || "run"} ${run.id || ""}`;
  $("trace-path").textContent = run.trace_path || "trace not created";
  $("metric-actions").textContent = summary.actions || 0;
  const usage = summary.usage || {};
  const parts = usageParts(usage);
  $("metric-input").textContent = fmtTokens(parts.input);
  $("metric-billable").textContent = `billable ${fmtTokens(parts.billableInput)}`;
  $("metric-cached").textContent = fmtTokens(parts.cached);
  $("metric-output").textContent = fmtTokens(parts.output);
  $("metric-time").textContent = fmtTime(summary.latency_ms || 0);
  $("metric-cost").textContent = fmtCost(summary.cost_estimate_usd);
  if (summary.last_state) {
    $("state-json").textContent = JSON.stringify(summary.last_state, null, 2);
    setText("state-chip", summary.last_state.decision || "unknown");
    setText("live-status", run.status ? `${run.status} / ${summary.last_state.decision || "unknown"}` : summary.last_state.decision || "unknown");
    setText("hero-subtitle", describeLiveState(summary.last_state, {}));
    const context = summary.last_state.context || {};
    setText("floor-label", context.floor == null ? "floor --" : `floor ${context.floor}`);
  }
  if (summary.memory) {
    $("memory-json").textContent = JSON.stringify(summary.memory, null, 2);
  }
  renderPlanSummary(summary.memory, summary);
  renderCurrentMove(run, summary);
}

function appendEvent(event) {
  state.seen += 1;
  $("event-count").textContent = `${state.seen} events`;
  const item = document.createElement("article");
  const kind = event.event || event.type || "event";
  item.className = `timeline-item ${classForEvent(kind)}`;
  const title = document.createElement("div");
  title.className = "timeline-title";
  const left = document.createElement("span");
  left.textContent = titleForEvent(event);
  const right = document.createElement("span");
  right.textContent = event.ts ? new Date(event.ts).toLocaleTimeString() : "";
  title.append(left, right);
  item.append(title);

  const body = document.createElement("div");
  body.className = "timeline-body";
  body.textContent = bodyForEvent(event);
  item.append(body);

  const toolEvents = event.decision && Array.isArray(event.decision.tool_events) ? event.decision.tool_events : [];
  if (toolEvents.length) {
    const pre = document.createElement("pre");
    pre.className = "timeline-code";
    pre.textContent = JSON.stringify(toolEvents, null, 2);
    item.append(pre);
  }

  $("timeline").prepend(item);
}

function classForEvent(kind) {
  if (kind.includes("error") || kind === "wait_limit") return "error";
  if (kind === "agent_decision" || kind === "action_result") return "action";
  return "state";
}

function titleForEvent(event) {
  if (event.event === "agent_decision") {
    const decision = event.decision || {};
    return `Agent chose ${decision.action || "action"} #${event.step ?? ""}`;
  }
  if (event.event === "action_result") return `Bridge action #${event.step ?? ""}`;
  if (event.event === "state") return `State ${event.state?.decision || ""}`;
  if (event.event === "state_wait") return `Waiting ${event.waits || ""}`;
  if (event.event === "start_run") return "Started visible run";
  if (event.event === "runner_stopped") return "Runner stopped";
  return event.event || event.type || "Event";
}

function bodyForEvent(event) {
  if (event.event === "agent_decision") {
    const decision = event.decision || {};
    const usage = decision.usage || {};
    return `${decision.rationale || ""} Expected: ${decision.expected || ""} ${fmtUsageSplit(usage)}.`;
  }
  if (event.event === "action_result") {
    return event.last_action_result?.message || JSON.stringify(event.last_action_result || {});
  }
  if (event.event === "state") {
    const context = event.state?.context || {};
    return `decision=${event.state?.decision || "unknown"} act=${context.act ?? "--"} floor=${context.floor ?? "--"}`;
  }
  if (event.event === "state_wait") {
    return `Waiting for a transient game state to settle.`;
  }
  return event.error || event.message || "";
}

function renderPlanSummary(memory, summary) {
  const container = $("plan-summary");
  if (!memory) {
    $("plan-updated").textContent = "waiting";
    const empty = document.createElement("div");
    empty.className = "plan-empty";
    empty.textContent = "Waiting for the first agent decision.";
    container.replaceChildren(empty);
    return;
  }

  const run = memory.run_summary || {};
  const build = memory.build_plan || {};
  const resources = memory.resource_plan || {};
  const map = memory.map_plan || {};
  const recent = Array.isArray(memory.recent_decisions) ? memory.recent_decisions : [];
  const notable = Array.isArray(memory.notable_events) ? memory.notable_events : [];
  const displayResources = fillResourceGaps(resources, recent);
  const lastMapChoice = recent.slice().reverse().find((item) => item.map_choice);
  const cards = [
    {
      label: "Thesis",
      value: planThesis(build, displayResources, run),
    },
    {
      label: "Route",
      value: routePlan(map, lastMapChoice),
    },
    {
      label: "Deck",
      value: deckPlan(build, recent, notable),
    },
    {
      label: "Resources",
      value: resourcePlan(displayResources),
    },
    {
      label: "Next Read",
      value: nextRead(run, displayResources),
    },
  ];

  $("plan-updated").textContent = run.floor == null ? "live" : `floor ${run.floor}`;
  const nodes = cards.map((card) => planCard(card.label, card.value));
  if (recent.length) nodes.push(recentCard(recent.slice(-4)));
  if (notable.length) nodes.push(planCard("Notable", notable[notable.length - 1]));
  container.replaceChildren(...nodes);
}

function fillResourceGaps(resources, recent) {
  const result = { ...resources };
  for (const item of recent.slice().reverse()) {
    if (result.gold == null && item.gold != null) result.gold = item.gold;
    if (result.hp_ratio == null && item.hp != null) {
      const maxHp = item.max_hp || 80;
      result.hp_ratio = Number(item.hp) / Number(maxHp);
    }
    if (result.hp == null && item.hp != null) result.hp = item.hp;
  }
  return result;
}

function planCard(label, value) {
  const card = document.createElement("article");
  card.className = "plan-card";
  const title = document.createElement("h3");
  title.textContent = label;
  const body = document.createElement("p");
  body.textContent = value || "No plan recorded yet.";
  card.append(title, body);
  return card;
}

function recentCard(items) {
  const card = document.createElement("article");
  card.className = "plan-card recent-plan";
  const title = document.createElement("h3");
  title.textContent = "Recent Decisions";
  const list = document.createElement("ul");
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = `${humanize(item.action)}: ${item.rationale || "No rationale recorded."}`;
    list.append(li);
  }
  card.append(title, list);
  return card;
}

function planThesis(build, resources, run) {
  const archetype = humanize(build.archetype || "ironclad midrange");
  const priority = Array.isArray(build.priorities) && build.priorities[0] ? build.priorities[0] : null;
  const stance = resources.stance && resources.stance !== "normal" ? ` Resource stance is ${humanize(resources.stance)}.` : "";
  if (priority) return `Playing ${archetype}; current priority is ${priority}.${stance}`;
  if ((run.floor || 0) <= 1) return `Opening as ${archetype}; improve early combat, preserve HP, and keep route options open.${stance}`;
  return `Playing ${archetype}; keep the deck focused and convert map rewards into boss-ready power.${stance}`;
}

function routePlan(map, lastMapChoice) {
  if (lastMapChoice?.map_choice?.path_preview) {
    const preview = lastMapChoice.map_choice.path_preview;
    const forced = compactList(preview.forced_nodes, "no forced chain recorded");
    return `Committed to a ${humanize(lastMapChoice.map_choice.type)} path: shop in ${preview.nearest_shop ?? "--"}, rest in ${preview.nearest_rest ?? "--"}, elite in ${preview.nearest_elite ?? "--"}. Forced line: ${forced}.`;
  }
  const choices = Array.isArray(map.choices) ? map.choices : [];
  if (choices.length) {
    const bestShop = choices.filter((item) => item.nearest_shop != null).sort((a, b) => a.nearest_shop - b.nearest_shop)[0];
    const bestRest = choices.filter((item) => item.nearest_rest != null).sort((a, b) => a.nearest_rest - b.nearest_rest)[0];
    const bits = [];
    if (bestShop) bits.push(`shop path index ${bestShop.index} in ${bestShop.nearest_shop}`);
    if (bestRest) bits.push(`rest path index ${bestRest.index} in ${bestRest.nearest_rest}`);
    return `${map.guidance || "Comparing visible paths."} ${bits.join("; ") || ""}`.trim();
  }
  return "No route decision yet; waiting for the map.";
}

function deckPlan(build, recent = [], notable = []) {
  const inferred = inferDeckPriorities(recent, notable);
  const priorities = compactList(build.priorities, inferred || "efficient damage, reliable block, and scaling that fits the relics");
  const avoid = compactList(build.avoid, "low-impact filler");
  return `Prioritize ${priorities}. Avoid ${avoid}.`;
}

function inferDeckPriorities(recent, notable) {
  const text = [
    ...recent.map((item) => item.rationale || ""),
    ...notable,
  ].join(" ");
  const priorities = [];
  if (/inflame|strength|twin strike|multi-hit|multi hit/i.test(text)) priorities.push("strength-scaling attacks and multi-hit cards");
  if (/remove|low-impact|filler|deck quality/i.test(text)) priorities.push("keeping the deck lean");
  return priorities.join(", ");
}

function resourcePlan(resources) {
  const potions = compactList(resources.potion_names, "none");
  const guidance = resources.guidance || resources.potion_guidance || "Spend HP, gold, and potions when they materially improve survival or power.";
  return `${fmtPercent(resources.hp_ratio)} HP, ${resources.gold ?? "--"} gold, ${resources.potion_count ?? 0} potions (${potions}). ${guidance}`;
}

function nextRead(run, resources) {
  const decision = run.decision || "unknown";
  if (decision === "combat_play") {
    return "In combat: check lethal first, then block incoming damage, then improve future turns. Use a potion if it prevents major HP loss or wins a dangerous fight.";
  }
  if (decision === "map_select") {
    return "On map: compare forced fights against nearest shop/rest/elite and pick the route that best matches HP, gold, and deck strength.";
  }
  if (decision === "shop") {
    return "At shop: convert gold into immediate power; prioritize strong relics, premium cards, and removal over leaving with unused gold.";
  }
  if (decision === "rest") {
    return resources.stance === "survive_to_rest" ? "At rest: heal unless the upgrade removes a larger near-term risk." : "At rest: upgrade if HP is safe; heal if the next path can punish low HP.";
  }
  if (decision === "combat_rewards" || decision === "card_reward" || decision === "card_select") {
    return "At reward: take cards that serve the build plan; skip weak filler and respect special selection prompts.";
  }
  return "Resolve the current screen, then re-evaluate route, resources, and deck direction.";
}

function renderCurrentMove(run, summary) {
  const container = $("current-move");
  const state = summary.last_state || {};
  const context = state.context || {};
  const decision = state.decision || "unknown";
  setText("current-status", run.status ? `${run.status} / ${decision}` : decision);

  const title = document.createElement("strong");
  title.textContent = run.status === "failed" ? "Run Failed" : summary.last_action ? humanize(summary.last_action) : "Observing game state";

  const rationale = document.createElement("p");
  rationale.textContent = run.status === "failed" && run.error ? run.error : summary.last_rationale || readableStateLine(state);

  const meta = document.createElement("div");
  meta.className = "current-meta";
  const floor = context.floor == null ? "floor --" : `floor ${context.floor}`;
  const act = context.act == null ? "act --" : `act ${context.act}`;
  const usage = summary.usage || {};
  const parts = usageParts(usage);
  const harness = run.config?.harness ? humanize(run.config.harness) : "agent";
  meta.textContent = `${harness} · ${act} · ${floor} · ${summary.actions || 0} actions · input ${fmtTokens(parts.input)} · cached ${fmtTokens(parts.cached)} · output ${fmtTokens(parts.output)} · ${fmtCost(summary.cost_estimate_usd)}`;

  container.replaceChildren(title, rationale, meta);
}

function describeLiveState(current, bridge) {
  if (!bridge?.ok && bridge?.error) return "Bridge connection is offline.";
  const decision = current?.decision || bridge?.decision || "menu";
  const context = current?.context || {};
  const floor = context.floor == null ? "floor not set" : `floor ${context.floor}`;
  const act = context.act == null ? "act not set" : `act ${context.act}`;
  if (decision === "menu") return "Visible game is at the menu; start a run to begin the climb.";
  if (decision === "combat_play") return `Live combat on ${act}, ${floor}; watching card choices, damage math, and potion timing.`;
  if (decision === "map_select") return `Route planning on ${act}, ${floor}; comparing shops, rests, elites, and forced fights.`;
  if (decision === "shop") return `Shop decision on ${act}, ${floor}; converting gold into power.`;
  if (decision === "combat_rewards" || decision === "card_reward") return `Reward decision on ${act}, ${floor}; updating the run plan.`;
  return `${humanize(decision)} on ${act}, ${floor}.`;
}

function readableStateLine(state) {
  if (!state || !state.decision) return "Waiting for the run to start.";
  const player = state.player || {};
  const hp = player.hp == null ? "HP --" : `${player.hp}/${player.max_hp ?? "--"} HP`;
  if (state.decision === "combat_play") {
    const enemies = Array.isArray(state.enemies) ? state.enemies : [];
    const enemy = enemies[0];
    return enemy ? `In combat against ${enemy.name}; player is at ${hp}.` : `In combat; player is at ${hp}.`;
  }
  if (state.decision === "map_select") return "Choosing the next route on the act map.";
  if (state.decision === "event_choice") return state.event_name ? `Resolving ${state.event_name}.` : "Resolving an event.";
  if (state.decision === "combat_rewards") return "Reviewing combat rewards.";
  if (state.decision === "shop") return "Evaluating shop purchases.";
  return `Current decision: ${humanize(state.decision)}.`;
}

$("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setRunControls(true);
  try {
    if (state.promptDirty) {
      const saved = await savePrompt({ silent: true });
      if (!saved) throw new Error("Prompt save failed; run was not started.");
    }
    const data = await api("/api/runs", {
      method: "POST",
      body: JSON.stringify(collectForm()),
    });
    attachRun(data.run.id);
  } catch (err) {
    setRunControls(false);
    appendEvent({ event: "agent_error", error: err.message, ts: new Date().toISOString() });
  }
});

$("stop-button").addEventListener("click", async () => {
  if (!state.activeRunId) return;
  await api(`/api/runs/${state.activeRunId}/stop`, { method: "POST", body: "{}" });
  $("run-title").textContent = `stopping ${state.activeRunId}`;
});

function applySidebarState() {
  const shell = document.querySelector(".shell");
  const button = $("sidebar-toggle");
  if (!shell || !button) return;
  shell.classList.toggle("sidebar-collapsed", state.sidebarCollapsed);
  button.setAttribute("aria-expanded", String(!state.sidebarCollapsed));
  button.title = state.sidebarCollapsed ? "Expand controls" : "Collapse controls";
  const text = button.querySelector(".sr-only");
  if (text) text.textContent = state.sidebarCollapsed ? "Expand controls" : "Collapse controls";
  const icon = button.querySelector(".sidebar-toggle-icon");
  if (icon) icon.textContent = state.sidebarCollapsed ? "›" : "‹";
}

$("sidebar-toggle").addEventListener("click", () => {
  state.sidebarCollapsed = !state.sidebarCollapsed;
  localStorage.setItem("sts2-sidebar-collapsed", state.sidebarCollapsed ? "1" : "0");
  applySidebarState();
});

$("harness-select")?.addEventListener("change", updateModelOptions);
$("model-select")?.addEventListener("change", updateReasoningOptions);
$("reasoning-select")?.addEventListener("change", updateResolvedModelHint);
$("profile-select")?.addEventListener("change", loadPrompt);
$("reload-prompt-button")?.addEventListener("click", loadPrompt);
$("save-prompt-button")?.addEventListener("click", () => savePrompt());
$("agents-md-editor")?.addEventListener("input", () => {
  if (state.promptLoading) return;
  state.promptDirty = true;
  setPromptStatus("unsaved");
});

updateModelOptions();
loadProfiles();
applySidebarState();
setRunControls(false);
refreshStatus();
setInterval(refreshStatus, 4000);
