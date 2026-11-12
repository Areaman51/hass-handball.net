/* Run: node --test tests/test_next_match_logo_size.js; real card render, DOM boundary only. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

// Existing card harnesses are file-local. Keep this boundary small and execute
// the actual asset: assertions inspect generated shadow markup/CSS, not source.
class ElementDouble {
  attachShadow() {
    return this.shadowRoot = { innerHTML: "", querySelectorAll() { return []; } };
  }
}
const registry = new Map();
const context = vm.createContext({
  HTMLElement: ElementDouble, URL, window: {},
  customElements: { define(name, ctor) { registry.set(name, ctor); } },
});
vm.runInContext(fs.readFileSync(path.join(__dirname,
  "../custom_components/handballnet/www/handball-team-card.js"), "utf8"), context);

function render(withLogos) {
  const home = { name: "Home Club", ...(withLogos ? { logo: "/home.png" } : {}) };
  const away = { name: "Away Club", ...(withLogos ? { logo: "/away.png" } : {}) };
  const card = new (registry.get("handball-team-card"))();
  card.setConfig({ next_match_entity: "sensor.next", live_ticker_entity: "sensor.live" });
  card.hass = { states: {
    "sensor.next": { state: "Next", attributes: { home_team: home, away_team: away } },
    "sensor.live": { state: "Live", attributes: {
      live_matches: [{ homeTeam: home, awayTeam: away, homeGoals: 12, awayGoals: 10 }],
    } },
  } };
  return card.shadowRoot.innerHTML;
}

function rule(html, selector) {
  const css = html.match(/<style>([\s\S]*?)<\/style>/)?.[1];
  assert.ok(css, "the actual render must emit its stylesheet");
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const matches = [...css.matchAll(new RegExp(`(?:^|[}\\n])\\s*${escaped}\\s*\\{([^}]*)\\}`, "g"))];
  assert.equal(matches.length, 1, `one rendered CSS rule for ${selector}`);
  return Object.fromEntries(matches[0][1].split(";").filter(value => value.trim()).map(value => {
    const colon = value.indexOf(":");
    return [value.slice(0, colon).trim(), value.slice(colon + 1).trim()];
  }));
}

for (const withLogos of [true, false]) {
  test(`next match: ${withLogos ? "images" : "placeholders"} render at 64x64 with contained logos`, () => {
    const html = render(withLogos);
    assert.match(html, /Nächstes Spiel/);
    const markup = withLogos ? /<img\b[^>]*class="match-logo"/g
      : /<span class="match-logo placeholder"/g;
    assert.equal([...html.matchAll(markup)].length, 2, "home and away use next-match logo styles");
    const base = rule(html, ".match-logo");
    const dimensions = withLogos ? base : rule(html, ".match-logo.placeholder");
    assert.equal(dimensions.width, "64px");
    assert.equal(dimensions.height, "64px");
    assert.equal(base["object-fit"], "contain");
  });

  test(`live ticker: ${withLogos ? "images" : "placeholders"} remain 40x40`, () => {
    const html = render(withLogos);
    const markup = withLogos ? /<img\b[^>]*class="live-logo"/g
      : /<span class="live-logo placeholder"/g;
    assert.equal([...html.matchAll(markup)].length, 2);
    const base = rule(html, ".live-logo");
    const dimensions = withLogos ? base : rule(html, ".live-logo.placeholder");
    assert.equal(dimensions.width, "40px");
    assert.equal(dimensions.height, "40px");
    assert.equal(base["object-fit"], "contain");
    assert.match(html, /12&thinsp;:&thinsp;10/);
  });
}
