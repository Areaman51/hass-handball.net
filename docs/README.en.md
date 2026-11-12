# Handball.net Community for Home Assistant

**German is the primary documentation language:** [full installation and user guide](../README.md).

This is the community fork **Areaman51/hass-handball.net**, based on **miggi92/hass-handball.net** under the [MIT license](../LICENSE). Original copyright notices are retained. This fork does not imply that the original project has been abandoned. Collaboration with its maintainers and other contributors is welcome. This is not an official handball.net or Home Assistant integration.

## Development status

**0.0.32.dev0 on main is a development version, not a published fork release.** There has been no complete release acceptance. Switching an existing HACS installation from the original to this fork has **not been tested in practice**.

The code combines the PR 88 history with additional public-client-token, request-scoped User-Agent, API/coordinator error-handling and security/robustness fixes. It is therefore not fully byte-identical to an unchanged running HA installation; validating a baseline does not mean those extra changes have been deployed. Python regression tests and additional Node tests are run locally. A real API smoke check of selected data paths succeeded, but this is not a full release acceptance. The pytest suite uses Home Assistant stubs when HA is absent; these are not real HA integration, browser or HACS migration tests. Final counts and results must refer to the specific tested commit. Existing GitHub workflows do not run pytest/Node.

## Installation and migration safety

Read the detailed [installation, migration and rollback guide in German](installation-und-umstieg.md) before changing an existing installation.

1. Create a full Home Assistant backup, keep it outside the running instance, and verify that any required recovery key is available. Also preserve the complete previous component directory separately.
2. Download this fork's **main source archive** and note the commit. Copy only `custom_components/handballnet` into the corresponding directory relative to your HA configuration, including all subdirectories.
3. For replacement, stop HA first and replace the whole old component directory rather than mixing individual files. Start HA and verify existing entries, entities, calendars and dashboards.
4. **Do not delete existing HA config entries. Do not edit .storage. Do not install the original and the fork side by side.** Both use the domain `handballnet`.
5. A code-only rollback means stopping HA and restoring the entire saved previous component directory. Deleted entries or registries cannot be recovered by restoring Python files; a backup restore may then be required and reverts later changes in the restored scope.

Home Assistant 2026.11 includes the Marketplace, which shares the HACS catalogue and `hacs.json` format. The [main guide's Marketplace link](../README.md#marketplace-als-benutzerdefiniertes-repository--migration-noch-ungetestet) offers this fork as a custom **Integration** repository; a GitHub connection is required. Without published releases, the Marketplace uses the latest default-branch commit, still a development version. No default-catalogue inclusion, successful Marketplace installation or practical source migration is claimed. Original and fork use the same domain, so an existing domain owner may block the second repository. Keep HA entries and follow the migration precautions rather than deleting them.

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
