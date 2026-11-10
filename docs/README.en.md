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

HACS is an optional, conditional route: add `https://github.com/Areaman51/hass-handball.net` as a custom **Integration** repository only if your HACS version supports it. Select **main only if offered**. `zip_release: false` avoids requiring a release asset, but does not guarantee that every HACS version can install an unreleased branch. Use manual source installation if it cannot. No inclusion in the HACS default catalogue is claimed. Existing HACS source switching remains untested.

## Setup

Add **Handball.net** through Settings → Devices & services. Choose:

- **Team → Manual Team ID:** a current provider team ID, not a complete URL or a historical legacy ID.
- **Team → Search by Club:** search for at least two characters, select a club, then select one or more teams. This creates a club entry even for one selected team.
- **Tournament → Search by Club:** resolve a phase from a selected team's first returned match; this may not identify the intended competition.
- **Tournament → Search by Competition:** choose competition and phase/group explicitly. There is no free-form tournament-ID step.

Options expose `update_interval` (default 3600 seconds) and `update_interval_live` (15 seconds). Reload the entry after changing options if needed. Team/club reconfiguration is implemented; a season selector, guaranteed automatic season migration and tournament reconfiguration are not.

## Features and important limits

Per-team game, statistics, table-position, health and live sensors, one live binary sensor and one calendar; club overview; tournament table, matchday schedule, positions and calendar. The no-table knockout helper has limitations and still relies on a legacy participant fallback.

“Live” primarily means a two-hour window after scheduled start, not a confirmed live status. Schedule/table caches can last one hour and team information six hours. The default polling interval may delay detecting a kickoff. Declared custom actions currently have handler-binding issues; prefer native HA entry reload and diagnostics UI.

Three cards are included and automatically loaded by the integration:

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
