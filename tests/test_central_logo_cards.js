/* Run: node --test tests/test_central_logo_cards.js; real assets, DOM boundary only. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const decode = value => value.replace(/&quot;/g, '"').replace(/&#39;/g, "'")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
class DomNode {
  constructor() { this.writes = 0; this._html = ""; this.listeners = {}; this.children = {}; this.images = []; this.attributes = {}; this.style = {}; this.requests = []; }
  set innerHTML(value) {
    this._html = value; this.writes++; this.children = {};
    this.images = [...value.matchAll(/<img\b([^>]*)>/g)].map(match => {
      const node = new DomNode();
      node.attributes = Object.fromEntries([...match[1].matchAll(/([\w-]+)="([^"]*)"/g)]
        .map(attribute => [attribute[1], decode(attribute[2])]));
      node.requests.push(node.attributes.src);
      return node;
    });
  }
  get innerHTML() { return this._html; }
  querySelector(selector) { return this.children[selector] ||= new DomNode(); }
  querySelectorAll(selector) { return selector === "img" ? this.images : []; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  setAttribute(name, value) { this.attributes[name] = String(value); if (name === "src") this.requests.push(String(value)); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  emit(name) { for (const handler of this.listeners[name] || []) handler({ target: this }); }
}
class ElementDouble {
  attachShadow() { return this.shadowRoot = new DomNode(); }
  dispatchEvent(event) { this.lastEvent = event; }
}
function load(kinds) {
  const registry = new Map();
  const context = vm.createContext({ HTMLElement: ElementDouble, URL, window: {},
    customElements: { define(name, ctor) { registry.set(name, ctor); } },
    CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
  });
  for (const kind of kinds) vm.runInContext(fs.readFileSync(path.join(__dirname,
    "../custom_components/handballnet/www", `handball-${kind}-card.js`), "utf8"), context);
  return registry;
}
const kinds = ["team", "tournament-table", "schedule"];
const registry = load(kinds);
const home = "SG Example Town", away = "Other Club";
const central = { "  sg  EXAMPLE   town  ": "/central/home.png", "OTHER CLUB": "https://example.org/away.png" };
function fixture(kind) {
  const config = kind === "team"
    ? { next_match_entity: "sensor.next", live_ticker_entity: "sensor.live", table_position_entity: "sensor.position" }
    : { entity: `sensor.${kind}`, ...(kind === "schedule" ? { table_entity: "sensor.table" } : {}) };
  const rows = [{ team_name: home, team_logo: "/api/home.png", position: 1 }, { team_name: away, team_logo: "/api/away.png", position: 2 }];
  return { kind, config, hass: { states: {
    "sensor.position": { state: "1", attributes: { team_name: home } },
    "sensor.next": { state: "Next", attributes: { home_team: { name: home, logo: "/api/home.png" }, away_team: { name: away, logo: "/api/away.png" } } },
    "sensor.live": { state: "Live", attributes: { live_matches: [{ homeTeam: { name: home, logo: "/api/home.png" }, awayTeam: { name: away, logo: "/api/away.png" } }] } },
    "sensor.tournament-table": { state: "OK", attributes: { table: rows } },
    "sensor.table": { state: "OK", attributes: { table: rows } },
    "sensor.schedule": { state: "OK", attributes: { current_matchday_index: 0, matchdays: [{ label: "Matchday", start: 1800000000000, end: 1800000000000, matches: [{ home, away, starts_at: 1800000000000 }] }] } },
  } } };
}
function sourceId(f) { return f.kind === "team" ? "sensor.next" : f.config.entity; }
function publish(f, map, revision, id = sourceId(f)) {
  if (arguments.length < 2) map = central;
  if (arguments.length < 3) revision = 1;
  Object.assign(f.hass.states[id].attributes, { handballnet_logo_overrides: map, handballnet_logo_revision: revision });
}
function render(f, registrations = registry) {
  const card = new (registrations.get(`handball-${f.kind}-card`))();
  card.setConfig(f.config); card.hass = f.hass; return card;
}
function content(card, kind) { return kind === "schedule" ? card.shadowRoot.querySelector(".list") : card.shadowRoot; }
function images(card, kind) { return content(card, kind).querySelectorAll("img"); }
function sources(card, kind) { return images(card, kind).map(img => img.getAttribute("src")); }
function clone(value) { return JSON.parse(JSON.stringify(value)); }
function expected(kind, a, b) { return kind === "team" ? [a, b, a, b] : [a, b]; }

// Slice 2: unique manual -> central -> API -> invisible, with persistent failures.
for (const kind of kinds) {
  test(`${kind}: manual priority and failed manual use central before API exactly once`, () => {
    const f = fixture(kind); publish(f); f.config.logo_overrides = { [home]: "/manual.png" };
    const card = render(f); const img = images(card, kind)[0];
    assert.equal(img.getAttribute("src"), "/manual.png");
    img.emit("error"); assert.equal(img.getAttribute("src"), "/central/home.png");
    img.emit("error"); assert.equal(img.getAttribute("src"), "/api/home.png");
    img.emit("error"); assert.equal(img.getAttribute("src"), null);
    assert.equal(img.style.visibility, "hidden");
    img.emit("error"); assert.deepEqual(img.requests, ["/manual.png", "/central/home.png", "/api/home.png"]);
    card.hass = clone(f.hass);
    assert.ok(!sources(card, kind).includes("/central/home.png"));
    assert.ok(!sources(card, kind).includes("/manual.png"));
    assert.ok(!sources(card, kind).includes("/api/home.png"));
    const writes = content(card, kind).writes;
    card.hass = clone(f.hass); card.hass = f.hass;
    assert.equal(content(card, kind).writes, writes);
  });
  test(`${kind}: equal manual/central/API source has no retry`, () => {
    const f = fixture(kind); publish(f, { [home]: "/api/home.png" });
    f.config.logo_overrides = { [home]: "/api/home.png" };
    const card = render(f); const img = images(card, kind)[0];
    img.emit("error"); img.emit("error");
    assert.equal(img.getAttribute("src"), null); assert.deepEqual(img.requests, ["/api/home.png"]);
  });
  test(`${kind}: invalid manual entry leaves valid central source eligible`, () => {
    const f = fixture(kind); publish(f); f.config.logo_overrides = { [home]: "javascript:bad()" };
    assert.equal(sources(render(f), kind)[0], "/central/home.png");
  });
}

// Slice 3: explicit central edits cross both state-identity and identical-DOM skips.
for (const kind of kinds) {
  test(`${kind}: revision retries the same failed central URL even on the same state object`, () => {
    const f = fixture(kind); publish(f); const card = render(f); const img = images(card, kind)[0];
    img.emit("error"); assert.equal(img.getAttribute("src"), "/api/home.png");
    const writes = content(card, kind).writes;
    card.hass = f.hass; assert.equal(content(card, kind).writes, writes);
    publish(f, central, 2); card.hass = f.hass;
    assert.notEqual(images(card, kind)[0], img);
    assert.equal(images(card, kind)[0].getAttribute("src"), "/central/home.png");
  });
  test(`${kind}: map edits, removal and re-addition release only affected logo failures`, () => {
    const f = fixture(kind); publish(f); const card = render(f);
    const [first, second] = images(card, kind);
    first.emit("error"); first.emit("error"); second.emit("error"); second.emit("error");
    publish(f, { ...central, "  sg  EXAMPLE   town  ": "/central/fixed.png" }); card.hass = f.hass;
    assert.ok(sources(card, kind).includes("/central/fixed.png"));
    assert.ok(!sources(card, kind).includes(central["OTHER CLUB"]), "unrelated failed central stays cached");
    assert.ok(!sources(card, kind).includes("/api/away.png"), "unrelated failed API stays cached");
    publish(f, { "OTHER CLUB": central["OTHER CLUB"] }); card.hass = f.hass;
    assert.ok(sources(card, kind).includes("/api/home.png"), "central deletion restores API even after prior failure");
    publish(f); card.hass = f.hass;
    assert.ok(sources(card, kind).includes("/central/home.png"), "re-saved original source is retried");
  });
  test(`${kind}: ordinary and reordered equal maps never retry failed sources`, () => {
    const f = fixture(kind); publish(f); const card = render(f); const img = images(card, kind)[0];
    img.emit("error");
    card.hass = clone(f.hass);
    const root = content(card, kind), writes = root.writes, active = images(card, kind)[0];
    publish(f, { "OTHER CLUB": central["OTHER CLUB"], "sg example town": "/central/home.png" });
    card.hass = f.hass; card.hass = clone(f.hass);
    assert.equal(root.writes, writes); assert.equal(images(card, kind)[0], active);
    assert.equal(active.getAttribute("src"), "/api/home.png");
  });
}

// Slice 4: schedule is independent of a table and never reads unconfigured states.
test("schedule: no table_entity uses central home/away and hidden terminal images", () => {
  const f = fixture("schedule"); delete f.config.table_entity; publish(f);
  const card = render(f); assert.deepEqual(sources(card, f.kind), Object.values(central));
  const img = images(card, f.kind)[0]; img.emit("error"); img.emit("error");
  assert.deepEqual(img.requests, ["/central/home.png"]); assert.equal(img.style.visibility, "hidden");
  card.hass = clone(f.hass);
  assert.match(content(card, f.kind).innerHTML, /aria-hidden="true"/);
  publish(f, central, 2); card.hass = f.hass;
  assert.equal(sources(card, f.kind)[0], "/central/home.png");
});
test("schedule: undefined table_entity must not read a state named undefined", () => {
  const f = fixture("schedule"); delete f.config.table_entity;
  f.hass.states.undefined = { attributes: { handballnet_logo_overrides: central, handballnet_logo_revision: 99 } };
  assert.deepEqual(sources(render(f), f.kind), []);
});
test("schedule: normalized table API names remain available after central image fails", () => {
  const f = fixture("schedule"); publish(f);
  f.hass.states["sensor.table"].attributes.table[0].team_name = " sg  EXAMPLE  town ";
  const card = render(f); const img = images(card, f.kind)[0]; img.emit("error");
  assert.equal(img.getAttribute("src"), "/api/home.png");
});

// Slice 5: malformed revisions cannot accidentally turn ordinary updates into retries.
for (const kind of kinds) {
  test(`${kind}: malformed revision updates are ignored without retrying failed central URLs`, () => {
    const f = fixture(kind); publish(f); const card = render(f);
    images(card, kind)[0].emit("error"); card.hass = clone(f.hass);
    const root = content(card, kind), writes = root.writes;
    for (const revision of [undefined, null, "2", {}, [], 1.5, Infinity, NaN]) {
      publish(f, central, revision); card.hass = f.hass;
      assert.equal(images(card, kind)[0].getAttribute("src"), "/api/home.png");
      assert.equal(root.writes, writes, `invalid revision ${String(revision)} must not clear failure cache`);
    }
  });
  test(`${kind}: unsafe central URLs and malformed maps safely retain API originals`, () => {
    for (const map of [undefined, null, [], [central], true, 42, "bad"]) {
      const f = fixture(kind); publish(f, map);
      assert.deepEqual(sources(render(f), kind), expected(kind, "/api/home.png", "/api/away.png"));
    }
    for (const value of ["javascript:alert(1)", "JaVaScRiPt:bad()", "data:image/svg+xml,<svg/onload=alert(1)>",
      "vbscript:x", "file:///etc/passwd", "blob:https://example.org/a", "ftp://example.org/a", "//evil.example/a", "///evil.example/a",
      "\\\\evil.example/a", "/\\evil.example/a", "java\nscript:bad()", "java\tscript:bad()", "\u0000https://example.org/a",
      "https://", "https:evil.example/a", "http:/evil.example/a", "", null, {}, [], 42]) {
      const f = fixture(kind); publish(f, { [home]: value });
      assert.deepEqual(sources(render(f), kind), expected(kind, "/api/home.png", "/api/away.png"), JSON.stringify(value));
    }
  });
  test(`${kind}: central URLs are escaped in src and fallback attributes`, () => {
    for (const url of ['https://example.org/a?a=1&b=2', '/local/a.png" onerror="alert(1)', '/local/<a>\'&.png']) {
      const f = fixture(kind); publish(f, { [home]: url }); f.config.logo_overrides = { [home]: "/manual.png" };
      const card = render(f); const root = content(card, kind); const img = images(card, kind)[0];
      assert.doesNotMatch(root.innerHTML, /<img\b[^>]*"\s+onerror\s*=/i);
      assert.doesNotMatch(root.innerHTML, /<a>/);
      assert.equal(img.getAttribute("data-central-logo"), url);
      img.emit("error"); assert.equal(img.getAttribute("src"), url);
      delete f.config.logo_overrides;
      assert.equal(sources(render(f), kind)[0], url);
    }
  });
}

// Additional regression coverage of already implemented contracts (no new production behavior).
for (const id of ["sensor.next", "sensor.live", "sensor.position"]) {
  test(`team: central values can originate exclusively in configured ${id}`, () => {
    const f = fixture("team"); publish(f, central, 1, id);
    const card = render(f);
    assert.deepEqual(sources(card, f.kind), expected(f.kind, ...Object.values(central)));
    publish(f, { [home]: "/central/updated.png" }, 2, id); card.hass = f.hass;
    assert.equal(sources(card, f.kind)[0], "/central/updated.png");
  });
}
for (const kind of kinds) {
  test(`${kind}: standalone asset renders without imports, shared resources or requests`, () => {
    const f = fixture(kind); publish(f);
    f.hass.callWS = () => { throw new Error("no websocket transport permitted"); };
    assert.deepEqual(sources(render(f, load([kind])), kind), expected(kind, ...Object.values(central)));
  });
  test(`${kind}: unconfigured sensors cannot supply central logos or trigger rendering`, () => {
    const f = fixture(kind);
    f.hass.states["sensor.unrelated"] = { attributes: { handballnet_logo_overrides: central, handballnet_logo_revision: 1 } };
    const card = render(f); const writes = content(card, kind).writes;
    assert.deepEqual(sources(card, kind), expected(kind, "/api/home.png", "/api/away.png"));
    f.hass.states["sensor.unrelated"].attributes.handballnet_logo_revision++;
    card.hass = f.hass;
    assert.equal(content(card, kind).writes, writes);
  });
  test(`${kind}: configuration reload retries central logos even after all sources failed`, () => {
    const f = fixture(kind); publish(f); const card = render(f); const img = images(card, kind)[0];
    img.emit("error"); img.emit("error");
    card.setConfig(f.config); card.hass = f.hass;
    assert.notEqual(images(card, kind)[0], img);
    assert.equal(sources(card, kind)[0], "/central/home.png");
  });
  test(`${kind}: central revision without image failures retains identical DOM`, () => {
    const f = fixture(kind); publish(f); const card = render(f); const writes = content(card, kind).writes;
    publish(f, central, 2); card.hass = f.hass;
    assert.equal(content(card, kind).writes, writes);
  });
  test(`${kind}: API originals are not mutated by central rendering or error fallback`, () => {
    const f = fixture(kind); publish(f); const before = clone(f.hass);
    const card = render(f); images(card, kind)[0].emit("error");
    assert.deepEqual(f.hass, before);
  });
}
test("schedule: optional table_entity alone can publish central values", () => {
  const f = fixture("schedule"); publish(f, central, 1, "sensor.table");
  assert.deepEqual(sources(render(f), f.kind), Object.values(central));
});
test("schedule: configured missing table_entity never prevents central logos", () => {
  const f = fixture("schedule"); delete f.hass.states["sensor.table"]; publish(f);
  assert.deepEqual(sources(render(f), f.kind), Object.values(central));
});
test("tournament-table: show_logo false dominates manual and central including revisions", () => {
  const f = fixture("tournament-table"); publish(f); f.config.show_logo = false;
  f.config.logo_overrides = { [home]: "/manual.png" }; const card = render(f);
  assert.deepEqual(sources(card, f.kind), []);
  publish(f, central, 2); card.hass = f.hass;
  assert.deepEqual(sources(card, f.kind), []);
});
for (const kind of ["team", "tournament-table"]) {
  test(`${kind}: visual editor leaves manual YAML exceptions intact without adding a central UI`, () => {
    const f = fixture(kind); f.config.logo_overrides = { [home]: "/manual.png" };
    const editor = new (registry.get(`handball-${kind}-card-editor`))(); editor.setConfig(f.config);
    editor._onValueChanged({ target: { dataset: { key: "title" }, value: "Edited" } });
    assert.deepEqual(editor.lastEvent.detail.config.logo_overrides, f.config.logo_overrides);
    assert.doesNotMatch(editor.shadowRoot.innerHTML, /handballnet_logo_(overrides|revision)/);
  });
}

// Slice 1: central lookup travels only through configured sensor state attributes.
for (const kind of kinds) {
  test(`${kind}: normalized central map supplies home/away including live`, () => {
    const f = fixture(kind); publish(f);
    assert.deepEqual(sources(render(f), kind), expected(kind, central[Object.keys(central)[0]], central["OTHER CLUB"]));
  });
}
