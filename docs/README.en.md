# Handball.net Community for Home Assistant

**German is the primary documentation language:** [full installation and user guide](../README.md).

This is the community fork **Areaman51/hass-handball.net**, based on **miggi92/hass-handball.net** under the [MIT license](../LICENSE). Original copyright notices are retained. This fork does not imply that the original project has been abandoned. Collaboration with its maintainers and other contributors is welcome. This is not an official handball.net or Home Assistant integration.

## Release status

**0.1.0 is the first regular community-fork release, tagged v0.1.0.** The release contains the previously live-accepted hardening and all three bundled cards. This does not imply a complete feature/version test matrix. Switching an existing original installation to this fork has **not been tested in practice**.

The code combines the PR 88 history with additional public-client-token, request-scoped User-Agent, API/coordinator error-handling and security/robustness fixes. It is therefore not fully byte-identical to an unchanged running HA installation; validating a baseline does not mean those extra changes have been deployed. Python regression tests and additional Node tests are run locally. A real API smoke check of selected data paths succeeded, but this is not a full release acceptance. The pytest suite uses Home Assistant stubs when HA is absent; these are not real HA integration, browser or HACS migration tests. Final counts and results must refer to the specific tested commit. Existing GitHub workflows do not run pytest/Node.

## Installation and migration safety

Read the detailed [installation, migration and rollback guide in German](installation-und-umstieg.md) before changing an existing installation.

**Recommended: install as a custom repository, without copying files.** Catalogue inclusion is not required. On Home Assistant 2026.11 or newer, the Marketplace is built in; there is no separate HACS installation step.

1. Open **Settings → Marketplace → Add from link**, or use the [main guide's repository button](../README.md#empfohlen-benutzerdefiniertes-repository--ohne-dateikopieren).
2. Add `https://github.com/Areaman51/hass-handball.net` as an **Integration**. Accept the community-content warning and connect GitHub when prompted.
3. Choose **Install** on its repository page and select the regular **v0.1.0** version. The Marketplace downloads and places the files itself. Follow any restart prompt; restart HA after integration updates.
4. Configure **Handball.net** under **Settings → Devices & services**. All three JavaScript cards are included and loaded automatically by the backend; no separate card repository or manual resource registration is needed. Configuring desired dashboard cards and their entity IDs is still required.

The GitHub connection belongs to HA's Marketplace, not to a handball.net token field. Choose **v0.1.0** for a fixed release instead of the moving `main` branch. `zip_release: false` remains intentional: the automatic installer uses tagged source files, not the optional attached `handballnet.zip`. See the [official Marketplace guide](https://www.home-assistant.io/integrations/marketplace/) and [version rules](https://contributors.home-assistant.io/marketplace/guides/releases/). The [verification record](pruefstand.md) distinguishes native installer tests from full browser and migration acceptance.

For an existing original installation, create a full HA backup and preserve the previous complete component directory before changing sources. **Do not delete existing HA config entries, edit .storage, or install original and fork side by side.** Both use `handballnet`; a domain-owner conflict can block a second source. Do not select deletion/uninstallation just to unblock the fork. The controlled source migration remains untested. Manual source copying is documented only as a fallback, not the normal installation route. A full backup restore reverts later changes in its restored scope and needs a deliberate recovery decision.

No default-catalogue application or additional release is required for this custom-repository route. A successful fresh installation does not prove that an existing original repository can be migrated without further work; keep these acceptance boundaries separate.

## Setup

Add **Handball.net** through Settings → Devices & services. Choose:

- **Team → Manual Team ID:** a current provider team ID, not a complete URL or a historical legacy ID.
- **Team → Search by Club:** search for at least two characters, select a club, then select one or more teams. This creates a club entry even for one selected team.
- **Tournament → Search by Club:** resolve a phase from a selected team's first returned match; this may not identify the intended competition.
- **Tournament → Search by Competition:** choose competition and phase/group explicitly. There is no free-form tournament-ID step.

Options separate polling intervals from central logo management. `update_interval` defaults to 3600 seconds and `update_interval_live` to 15 seconds; reload the entry after interval changes if needed. Logo management selects a team, accepts an image URL or validated PNG/JPEG/WebP upload, and restores the API original after confirmation. Logo changes reach all three cards without API refresh or restart; per-card `logo_overrides` remain higher-priority exceptions. Uploaded images are publicly accessible static files, not a private photo store; see the [logo guide](vereinslogos.md). Team/club reconfiguration is implemented; a season selector, guaranteed automatic season migration and tournament reconfiguration are not.

## Features and important limits

Per-team game, statistics, table-position, health and live sensors, one live binary sensor and one calendar; club overview; tournament table, matchday schedule, positions and calendar. The no-table knockout helper has limitations and still relies on a legacy participant fallback.

“Live” primarily means a two-hour window after scheduled start, not a confirmed live status. Schedule/table caches can last one hour and team information six hours. The default polling interval may delay detecting a kickoff. Declared custom actions currently have handler-binding issues; prefer native HA entry reload and diagnostics UI.

Three cards are included and automatically loaded by the integration:

Next-match logos are 64×64 pixels with preserved aspect ratio; live-ticker, table and schedule logo sizes remain unchanged. The 12 November 2026 verification covered 155 Python and 144 Node tests, isolated native HA 2026.11.0/2026.11.1 logo checks and a targeted HA 2026.11.1 pilot with real options/upload/reset and six browser cases using HA-served files and actual card data. Those browser cases used a separate card wrapper, not a full authenticated HA/Companion-app test. The pilot user additionally accepted their own client display; full release and Marketplace/HACS migration acceptance remain separate.

```yaml
type: custom:handball-team-card
title: Example Club
next_match_entity: sensor.example_club_next_match
live_ticker_entity: sensor.example_club_live_ticker
```

Replace fictional entity IDs with actual IDs. `table_position_entity` is supported by the card, but the regular team table-position sensor currently lacks the `position` attribute it expects. See the [card guide](dashboard-karten.md) for this limitation and table/schedule examples. Built-in preview data is not evidence of a working connection.

## Troubleshooting and contributions

The client retrieves a public token automatically; there is no token field and no need to provide personal credentials or browser cookies. A 403 triggers one token refresh/retry; persistent rejection still needs investigation. Before sharing diagnostics or logs, remove tokens, private addresses, identifiers and unnecessary personal context.

- [Entity and calendar reference](entitaeten.md)
- [Troubleshooting, actions and polling](fehlersuche.md)
- [Development and test limitations](entwicklung.md)
- [Security, diagnostic privacy and inherited historical data](../SECURITY.md)
- [Contributing](../CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)

Runtime/authentication/database files have been removed from the current source tree, not from the preserved Git history or existing copies. There is no blanket assurance that historical commits contain no secrets. See [SECURITY.md](../SECURITY.md).

Please report fork issues in the fork rather than automatically sending them upstream. Original sponsorship information does not constitute support or funding for this fork.
