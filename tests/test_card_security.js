/* Run with: node --test tests/test_card_security.js (no npm dependencies). */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

// Only the DOM boundary is doubled: execute the real registered cards/editors
// and retain every innerHTML write, including the identical-markup skip path.
class ElementDouble {
  attachShadow() {
    this.shadowRoot = {
      writes: 0,
      _html: "",
      set innerHTML(value) { this._html = value; this.writes++; },
      get innerHTML() { return this._html; },
      querySelectorAll() { return []; },
    };
    return this.shadowRoot;
  }
  dispatchEvent(event) { this.lastEvent = event; }
}

const registry = new Map();
const context = vm.createContext({
  HTMLElement: ElementDouble,
  customElements: { define(name, ctor) { registry.set(name, ctor); } },
  window: {}, URL,
  CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
});
for (const filename of ["handball-team-card.js", "handball-tournament-table-card.js"]) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../custom_components/handballnet/www", filename), "utf8"), context);
}

const attack = '<svg/onload=alert(1)>&"\'';
const escapedAttack = "&lt;svg/onload=alert(1)&gt;&amp;&quot;&#39;";
const stats = ["position", "wins", "draws", "losses", "games_played", "goals_scored", "goals_conceded", "goal_difference", "points"];

function teamFixture() {
  return {
    name: "handball-team-card",
    config: { table_position_entity: "sensor.position", next_match_entity: "sensor.next", live_ticker_entity: "sensor.live" },
    hass: { states: {
      "sensor.position": { state: "1", attributes: { team_name: "Team & Friends", ...Object.fromEntries(stats.map(key => [key, 1])) } },
      "sensor.next": { state: "Next", attributes: { match_date: "Sa, 19:30", field: "Halle", home_team: { name: "Home", logo: "/home.png" }, away_team: { name: "Away", logo: "https://logos.example/away.png" } } },
      "sensor.live": { state: "Live", attributes: { live_matches: [{ homeTeam: { name: "Live Home", logo: "/live-home.png" }, awayTeam: { name: "Live Away", logo: "/live-away.png" }, homeGoals: 4, awayGoals: 2 }] } },
    } },
  };
}

function tableFixture() {
  return {
    name: "handball-tournament-table-card",
    config: { entity: "sensor.table", highlight_team: "Team & Friends" },
    hass: { states: { "sensor.table": { state: "OK", attributes: {
      tournament_name: "League", organization: "Org", tournament_acronym: "L",
      table: [{ team_name: "Team & Friends", team_logo: "/home.png", ...Object.fromEntries(stats.map(key => [key, 1])) }],
    } } } },
  };
}

function render(fixture) {
  const card = new (registry.get(fixture.name))();
  card.setConfig(fixture.config);
  card.hass = fixture.hass;
  return card;
}

function assertEscaped(html) {
  assert.ok(html.includes(escapedAttack), "untrusted value must be escaped exactly once");
  assert.ok(!html.includes(attack), "raw attacker markup must not reach innerHTML");
  assert.doesNotMatch(html, /<svg\b/i);
  assert.ok(!html.includes("&amp;lt;svg"), "must not double-escape helper markup");
}

// Each test changes one untrusted value, so an unprotected sink cannot hide
// behind an escaped value from another field in the same rendered card.
for (const key of stats) {
  test(`team escapes table statistic ${key}`, () => {
    const f = teamFixture();
    f.hass.states["sensor.position"].attributes[key] = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
  test(`tournament escapes table statistic ${key}`, () => {
    const f = tableFixture();
    f.hass.states["sensor.table"].attributes.table[0][key] = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
}
for (const key of ["team_name"]) {
  test(`team escapes ${key}`, () => {
    const f = teamFixture();
    f.hass.states["sensor.position"].attributes[key] = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
}
for (const key of ["match_date", "field"]) {
  test(`team escapes next-match ${key}`, () => {
    const f = teamFixture();
    f.hass.states["sensor.next"].attributes[key] = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
}
for (const key of ["home_team", "away_team"]) {
  test(`team escapes next-match ${key} text and alt attribute`, () => {
    const f = teamFixture();
    f.hass.states["sensor.next"].attributes[key].name = attack;
    const html = render(f).shadowRoot.innerHTML;
    assertEscaped(html);
    assert.ok(html.includes(`alt="${escapedAttack}"`));
    assert.ok(html.includes(`class="match-name">${escapedAttack}</span>`));
  });
}
for (const key of ["homeTeam", "awayTeam", "homeGoals", "awayGoals"]) {
  test(`team escapes live ${key}`, () => {
    const f = teamFixture();
    const match = f.hass.states["sensor.live"].attributes.live_matches[0];
    if (key.endsWith("Team")) match[key].name = attack;
    else match[key] = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
}
for (const key of ["tournament_name", "organization", "tournament_acronym"]) {
  test(`tournament escapes ${key}`, () => {
    const f = tableFixture();
    f.hass.states["sensor.table"].attributes[key] = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
}
test("tournament escapes team name", () => {
  const f = tableFixture();
  f.hass.states["sensor.table"].attributes.table[0].team_name = attack;
  assertEscaped(render(f).shadowRoot.innerHTML);
});
test("tournament escapes missing-entity diagnostic", () => {
  const f = tableFixture();
  f.config.entity = "sensor." + attack;
  assertEscaped(render(f).shadowRoot.innerHTML);
});

const logoSinks = [
  { name: "next home", fixture: teamFixture, set(f, url) { f.hass.states["sensor.next"].attributes.home_team.logo = url; } },
  { name: "next away", fixture: teamFixture, set(f, url) { f.hass.states["sensor.next"].attributes.away_team.logo = url; } },
  { name: "live home", fixture: teamFixture, set(f, url) { f.hass.states["sensor.live"].attributes.live_matches[0].homeTeam.logo = url; } },
  { name: "live away", fixture: teamFixture, set(f, url) { f.hass.states["sensor.live"].attributes.live_matches[0].awayTeam.logo = url; } },
  { name: "tournament row", fixture: tableFixture, set(f, url) { f.hass.states["sensor.table"].attributes.table[0].team_logo = url; } },
];
const unsafeLogos = [
  "javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:image/svg+xml,<svg/onload=alert(1)>",
  "vbscript:alert(1)", "file:///etc/passwd", "blob:https://example.org/logo", "ftp://example.org/logo",
  "//untrusted.example/logo.png", "///untrusted.example/logo.png", "\\\\untrusted.example/logo.png",
  "/\\untrusted.example/logo.png", "java\nscript:alert(1)", "java\tscript:alert(1)",
  "\u0000javascript:alert(1)", "https://", "https:untrusted.example/logo", "http:/untrusted.example/logo",
  "", null, 42, {},
];
for (const sink of logoSinks) {
  test(`${sink.name} rejects unsafe image URL schemes and protocol-relative URLs`, () => {
    for (const url of unsafeLogos) {
      const f = sink.fixture();
      // Remove all other logos, so neither another image nor another safe
      // placeholder can accidentally satisfy the assertions for this sink.
      for (const other of logoSinks.filter(other => other.fixture === sink.fixture)) other.set(f, null);
      sink.set(f, url);
      const html = render(f).shadowRoot.innerHTML;
      assert.doesNotMatch(html, /<img\b/i, `must reject ${JSON.stringify(url)}`);
      assert.match(html, /placeholder/, "blocked logos retain the existing placeholder layout");
    }
  });
  test(`${sink.name} retains and attribute-escapes HTTP(S) and relative image URLs`, () => {
    for (const url of [
      "https://logos.example/a.png?a=1&b=2", "http://logos.example/a.png", "HTTPS://logos.example/a.png",
      "/local/a.png", "local/a.png", "./a.png", "../a.png", "/local/a.png?label=&quot;",
      '/local/a.png" onerror="alert(1)',
    ]) {
      const f = sink.fixture();
      for (const other of logoSinks.filter(other => other.fixture === sink.fixture)) other.set(f, null);
      sink.set(f, url);
      const html = render(f).shadowRoot.innerHTML;
      const expected = url.replaceAll("&", "&amp;").replaceAll('"', "&quot;");
      assert.ok(html.includes(`src="${expected}"`), `must preserve and escape ${url}`);
      assert.equal((html.match(/<img\b/g) || []).length, 1);
      // A quoted breakout would create another attribute; an encoded quote
      // remains part of src and is decoded only after HTML tokenization.
      assert.doesNotMatch(html, /<img\b[^>]*"\s+onerror\s*=/i);
    }
  });
}

for (const fixture of [teamFixture, tableFixture]) {
  const name = fixture().name;
  test(`${name} escapes configured title`, () => {
    const f = fixture();
    f.config.title = attack;
    assertEscaped(render(f).shadowRoot.innerHTML);
  });
  const editorKeys = name === "handball-team-card"
    ? ["title", "table_position_entity", "next_match_entity", "live_ticker_entity"]
    : ["entity", "title", "highlight_team"];
  for (const key of editorKeys) {
    test(`${name} editor escapes ${key} attribute`, () => {
      const editor = new (registry.get(name + "-editor"))();
      editor.setConfig({ ...fixture().config, [key]: attack });
      assertEscaped(editor.shadowRoot.innerHTML);
      assert.ok(editor.shadowRoot.innerHTML.includes(`value="${escapedAttack}"`));
    });
  }
  test(`${name} editor escapes sensor datalist text`, () => {
    const editor = new (registry.get(name + "-editor"))();
    editor.setConfig(fixture().config);
    editor.hass = { states: { ["sensor." + attack]: {} } };
    assertEscaped(editor.shadowRoot.innerHTML);
    assert.ok(editor.shadowRoot.innerHTML.includes(`<option value="sensor.${escapedAttack}"></option>`));
  });
  test(`${name} retains real markup, ordinary logos, identical-DOM skip and config updates`, () => {
    const f = fixture();
    const card = render(f);
    const initial = card.shadowRoot.innerHTML;
    assert.match(initial, /<ha-card>/);
    assert.match(initial, /<img [^>]*src="\/home\.png"/);
    assert.ok(initial.includes("Team &amp; Friends"));
    assert.ok(!initial.includes("&lt;img"));
    assert.equal(card.shadowRoot.writes, 1);
    card.hass = f.hass;
    assert.equal(card.shadowRoot.writes, 1, "unchanged state object must skip DOM writes");
    card.hass = JSON.parse(JSON.stringify(f.hass));
    assert.equal(card.shadowRoot.writes, 1, "equal new state object must skip DOM writes");
    card.setConfig({ ...f.config, title: "Changed & Title" });
    card.hass = f.hass;
    assert.equal(card.shadowRoot.writes, 2);
    assert.ok(card.shadowRoot.innerHTML.includes("Changed &amp; Title"));
  });
}
