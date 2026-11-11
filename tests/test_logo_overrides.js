/* Run with: node --test tests/test_logo_overrides.js (no npm dependencies). */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

// Double only the DOM boundary; load all three real, self-contained assets.
const decode = value => value.replace(/&quot;/g, '"').replace(/&#39;/g, "'")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
class DomNode {
  constructor() { this.writes = 0; this._html = ""; this.listeners = {}; this.children = {}; this.images = []; this.attributes = {}; this.style = {}; }
  set innerHTML(value) {
    this._html = value;
    this.writes++;
    this.children = {};
    this.images = [...value.matchAll(/<img\b([^>]*)>/g)].map(match => {
      const node = new DomNode();
      node.attributes = Object.fromEntries([...match[1].matchAll(/([\w-]+)="([^"]*)"/g)]
        .map(attribute => [attribute[1], decode(attribute[2])]));
      return node;
    });
  }
  get innerHTML() { return this._html; }
  querySelector(selector) { return this.children[selector] ||= new DomNode(); }
  querySelectorAll(selector) { return selector === "img" ? this.images : []; }
  getAttribute(name) { return this.attributes[name] ?? null; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  emit(name) { for (const handler of this.listeners[name] || []) handler({ target: this }); }
}
class ElementDouble {
  attachShadow() { return this.shadowRoot = new DomNode(); }
  dispatchEvent(event) { this.lastEvent = event; }
}
const registry = new Map();
const context = vm.createContext({
  HTMLElement: ElementDouble, URL, window: {},
  customElements: { define(name, ctor) { registry.set(name, ctor); } },
  CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
});
for (const name of ["team", "tournament-table", "schedule"]) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../custom_components/handballnet/www", `handball-${name}-card.js`), "utf8"), context);
}
const home = "SG Example Town";
const away = "Other Club";
const normalizedMapping = {
  "  sg  EXAMPLE   town  ": "/local/logos/example.png",
  "OTHER CLUB": "https://example.org/other.png",
};
function fixture(kind) {
  const config = kind === "team"
    ? { next_match_entity: "sensor.next", live_ticker_entity: "sensor.live" }
    : { entity: `sensor.${kind}`, ...(kind === "schedule" ? { table_entity: "sensor.table" } : {}) };
  const rows = [
    { team_name: home, team_logo: "/api/home.png", position: 1 },
    { team_name: away, team_logo: "/api/away.png", position: 2 },
  ];
  const hass = { states: {
    "sensor.next": { state: "Next", attributes: { home_team: { name: home, logo: "/api/home.png" }, away_team: { name: away, logo: "/api/away.png" } } },
    "sensor.live": { state: "Live", attributes: { live_matches: [{ homeTeam: { name: home, logo: "/api/home.png" }, awayTeam: { name: away, logo: "/api/away.png" } }] } },
    "sensor.tournament-table": { state: "OK", attributes: { table: rows } },
    "sensor.table": { state: "OK", attributes: { table: rows } },
    "sensor.schedule": { state: "OK", attributes: { current_matchday_index: 0, matchdays: [{ label: "Matchday", start: 1800000000000, end: 1800000000000, matches: [{ home, away, starts_at: 1800000000000 }] }] } },
  } };
  return { kind, config, hass };
}
function render(f) {
  const card = new (registry.get(`handball-${f.kind}-card`))();
  card.setConfig(f.config);
  card.hass = f.hass;
  return card;
}
function content(card, kind) { return kind === "schedule" ? card.shadowRoot.querySelector(".list") : card.shadowRoot; }
function sources(card, kind) { return content(card, kind).querySelectorAll("img").map(img => img.getAttribute("src")); }
function clone(value) { return JSON.parse(JSON.stringify(value)); }

test("tournament-table: normalized overrides cover all rows", () => {
  const f = fixture("tournament-table");
  f.config.logo_overrides = normalizedMapping;
  assert.deepEqual(sources(render(f), f.kind), Object.values(normalizedMapping));
});

for (const withTable of [true, false]) {
  test(`schedule: normalized home/away overrides with table_entity=${withTable}`, () => {
    const f = fixture("schedule");
    if (!withTable) delete f.config.table_entity;
    f.config.logo_overrides = normalizedMapping;
    assert.deepEqual(sources(render(f), f.kind), Object.values(normalizedMapping));
  });
}

for (const kind of ["team", "tournament-table", "schedule"]) {
  test(`${kind}: malformed override containers are rejected`, () => {
    for (const value of [[], "bad", 42, true]) {
      const f = fixture(kind); f.config.logo_overrides = value;
      assert.throws(() => render(f), /logo_overrides.*mapping/i);
    }
  });
  test(`${kind}: unsafe overrides fall back to API without attribute injection`, () => {
    for (const value of ["javascript:alert(1)", "data:image/svg+xml,<svg/onload=alert(1)>", "//evil.example/a.png", "\\\\evil.example/a.png", "https://", "java\nscript:alert(1)", null, {}, 42]) {
      const f = fixture(kind); f.config.logo_overrides = { [home]: value };
      assert.ok(sources(render(f), kind).includes("/api/home.png"), JSON.stringify(value));
    }
    const f = fixture(kind); f.config.logo_overrides = { [home]: '/local/a.png" onerror="alert(1)' };
    const card = render(f); const html = content(card, kind).innerHTML;
    assert.doesNotMatch(html, /<img\b[^>]*"\s+onerror\s*=/i);
    assert.ok(sources(card, kind).includes('/local/a.png" onerror="alert(1)'));
  });
  test(`${kind}: no override retains API sources and unmatched teams`, () => {
    const f = fixture(kind);
    const expected = kind === "team" ? ["/api/home.png", "/api/away.png", "/api/home.png", "/api/away.png"] : ["/api/home.png", "/api/away.png"];
    assert.deepEqual(sources(render(f), kind), expected);
    f.config.logo_overrides = { "Unrelated Team": "/other.png" };
    assert.deepEqual(sources(render(f), kind), expected);
  });
}

for (const kind of ["team", "tournament-table", "schedule"]) {
  test(`${kind}: image errors fall back once, then hide and remember failed sources`, () => {
    const f = fixture(kind); f.config.logo_overrides = { [home]: "/replacement.png" };
    const card = render(f); const img = content(card, kind).querySelectorAll("img")[0];
    assert.equal(img.getAttribute("src"), "/replacement.png");
    img.emit("error");
    assert.equal(img.getAttribute("src"), "/api/home.png");
    img.emit("error");
    assert.equal(img.getAttribute("src"), null);
    assert.equal(img.style.visibility, "hidden");
    img.emit("error");
    assert.equal(img.getAttribute("src"), null, "no repeated fallback after terminal failure");
    card.hass = clone(f.hass);
    assert.ok(!sources(card, kind).includes("/replacement.png"));
    assert.ok(!sources(card, kind).includes("/api/home.png"));
    const count = content(card, kind).writes;
    card.hass = clone(f.hass);
    assert.equal(content(card, kind).writes, count, "unchanged content retains DOM skip");
    card.setConfig({ ...f.config, logo_overrides: { [home]: "/fixed.png" } }); card.hass = f.hass;
    assert.ok(sources(card, kind).includes("/fixed.png"), "new configuration resets failed-logo state");
  });
  test(`${kind}: an override equal to API is never retried on error`, () => {
    const f = fixture(kind); f.config.logo_overrides = { [home]: "/api/home.png" };
    const card = render(f); const img = content(card, kind).querySelectorAll("img")[0];
    img.emit("error"); assert.equal(img.getAttribute("src"), null); assert.equal(img.style.visibility, "hidden");
  });
  test(`${kind}: replacement works when API logo is absent`, () => {
    const f = fixture(kind); f.config.logo_overrides = { [home]: "/replacement.png" };
    delete f.hass.states["sensor.next"].attributes.home_team.logo;
    delete f.hass.states["sensor.live"].attributes.live_matches[0].homeTeam.logo;
    delete f.hass.states["sensor.table"].attributes.table[0].team_logo;
    delete f.hass.states["sensor.tournament-table"].attributes.table[0].team_logo;
    assert.equal(f.hass.states["sensor.tournament-table"].attributes.table[0].team_logo, undefined);
    assert.ok(sources(render(f), kind).includes("/replacement.png"));
  });
}

for (const kind of ["team", "tournament-table", "schedule"]) {
  test(`${kind}: explicit same-configuration reload retries failed sources`, () => {
    const f = fixture(kind); f.config.logo_overrides = { [home]: "/replacement.png" };
    const card = render(f); const img = content(card, kind).querySelectorAll("img")[0];
    img.emit("error"); img.emit("error");
    assert.equal(img.style.visibility, "hidden");
    card.setConfig(f.config); card.hass = f.hass;
    const retried = content(card, kind).querySelectorAll("img")[0];
    assert.notEqual(retried, img, "explicit reload must rebuild failed image nodes");
    assert.equal(retried.getAttribute("src"), "/replacement.png");
  });
}
for (const kind of ["team", "tournament-table"]) {
  test(`${kind}: visual editor preserves logo_overrides when editing title`, () => {
    const f = fixture(kind); f.config.logo_overrides = normalizedMapping;
    const editor = new (registry.get(`handball-${kind}-card-editor`))();
    editor.setConfig(f.config);
    editor._onValueChanged({ target: { dataset: { key: "title" }, value: "New Title" } });
    assert.deepEqual(editor.lastEvent.detail.config.logo_overrides, normalizedMapping);
  });
}
test("tournament-table: show_logo false overrides configured replacement logos", () => {
  const f = fixture("tournament-table"); f.config.logo_overrides = normalizedMapping; f.config.show_logo = false;
  assert.deepEqual(sources(render(f), f.kind), []);
});
test("schedule: unsafe API logo is rejected without a replacement", () => {
  const f = fixture("schedule"); f.hass.states['sensor.table'].attributes.table[0].team_logo = 'javascript:alert(1)';
  assert.deepEqual(sources(render(f), f.kind), ['/api/away.png']);
});

// Vertical slices use the same contract at every actual card's HTML boundary.
test("team: normalized overrides cover next-match and live home/away", () => {
  const f = fixture("team");
  f.config.logo_overrides = normalizedMapping;
  const card = render(f);
  assert.deepEqual(sources(card, f.kind), [normalizedMapping["  sg  EXAMPLE   town  "], normalizedMapping["OTHER CLUB"], normalizedMapping["  sg  EXAMPLE   town  "], normalizedMapping["OTHER CLUB"]]);
});
