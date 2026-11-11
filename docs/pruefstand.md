# Prüfstand 0.0.32.dev0

Stand: **11. November 2026**. Dieser Prüfstand umfasst die zuvor zusammengeführte Sicherheits-/API-Basis und die optionalen Logoquellen in allen drei Karten. Die folgenden Nachweise sind lokale Regressionen, gezielte Browserprüfungen und eine begrenzte Pilotinstallation – keine vollständige Releaseabnahme.

## Tatsächlich ausgeführte Prüfungen

Umgebung: **Python 3.13.5**, frische virtuelle Testumgebung mit den direkten Abhängigkeiten aus `requirements-test.txt`; **Node.js v26.12.1**.

- `python -m pytest -q`: **61 bestanden**. Die Suite verwendet HA-Ersatzmodule; HTTP-Protokolltests nutzen echte lokale aiohttp-Sockets mit kontrollierten Antworten.
- `node --test tests/test_card_security.js tests/test_logo_overrides.js`: **84 bestanden**. Reale Karten-/Editorquellen im Node-VM, simulierte DOM-Grenze; 55 bisherige Sicherheitsregressionen und 29 ergänzende Logo-/Fallback-/Konfigurationsregressionen. Geprüft werden unter anderem Normalisierung, unsichere Bildadressen, fehlende API-Logos, Konfigurationswechsel, begrenzte Fehlerpfade und erneute Konfiguration nach Ladefehlern.
- `node --check` für alle drei mitgelieferten JavaScript-Karten: erfolgreich.
- `ruff check --select E9,F63,F7,F82 custom_components tests`: erfolgreich. Das ist eine gezielte Syntax-/Fehlerklassenprüfung, **kein vollständig grüner Lauf des umfangreichen repositoryweiten Ruff-Regelwerks**.
- Markdown-Verweisziele sowie 14 YAML-Beispiele statisch geprüft; historischer Changelog ab v0.0.31 unverändert erhalten.
- 32 echte Chromium-Fälle mit kontrollierten Testdaten auf 390 und 768 Pixeln erfolgreich: alle drei Karten, gültige/ungültige/fehlende Ersatzquellen, begrenzter Fallback, Zustandsupdates und Konfigurationswechsel. Die lokale Kartenhülle ist kein vollständiges HA-Frontend.
- Nach freigegebenem gezieltem Frontend-Einbau in einer Pilotinstallation drei JS-Dateien und die lokale Bilddatei über die tatsächlich von HA ausgelieferten URLs hashgenau geprüft; gespeicherte Logo-Zuordnungen zurückgelesen und übrige Dashboardinhalte durch inversen Vergleich unverändert bestätigt. HA-Konfigurationsprüfung gültig und laufende Integration gesund, kein Core-Neustart für diesen Eingriff.
- Zusätzlich sechs Browserfälle mit genau diesen HA-ausgelieferten JS-/Bilddateien, den gespeicherten Kartenkonfigurationen und einem frischen Snapshot tatsächlicher Entitätsdaten: alle drei Karten bei 390 und 1100 Pixeln erfolgreich. Separate Kartenhülle; **keine vollständige angemeldete HA-/Companion-App-Abnahme**. Das vollständige Logo wurde geladen, ohne JS-Fehler oder horizontalen Seitenüberlauf.
- Unabhängiges Read-only-Code-/Sicherheitsreview der Logo-Erweiterung ohne Sicherheits- oder Logikbefunde.
- Echter, begrenzter Abruf über den zusammengeführten Client gegen handball.net: Teaminformation, vollständiger Spielplan über zwei Seiten (**26 eindeutige Spiele**, abgeglichen mit der API-Gesamtzahl) und Tabelle (**14 Mannschaften**) erfolgreich, keine HTTP-Fehler. Dies beschreibt einen Abruf ausgewählter Datenpfade, keine dauerhafte Verfügbarkeitszusage.

Für die vier neuen Dekodierungsfälle und die Karten-/URL-Sicherheitsregressionen wurden zuerst scheiternde Tests beobachtet und anschließend die vollständigen Suiten erneut erfolgreich ausgeführt. Testfixtures enthalten künstliche Angriffswerte und künstliche Tokenzeichenketten, keine aus einer privaten HA-Installation übernommenen Zugangsdaten.

## Was damit nicht abgenommen ist

- Kein vollständiger echter Home-Assistant-Integrationstest und kein vollständiger Browser-/Frontendtest.
- Kein praktischer HACS-Wechsel, kein Installations-/Update-/Rollback-End-to-End-Test.
- Keine vollständige Prüfung von Team-/Vereins-/Turnier-Neueinrichtung, Saisonwechsel, Kalenderzeitzonen, allen Live-Funktionen oder allen deklarierten Aktionen.
- Kein stabiles Fork-Release, kein Release-Asset und keine Zusage der Aufnahme in den HACS-Standardkatalog.
- Keine automatisch laufende pytest-/Node-Pipeline auf GitHub: die vorhandenen Workflows führen diese Suiten noch nicht aus. GitHub-Validierungsstatus ist separat am jeweiligen Commit zu prüfen.

Bekannte funktionale Einschränkungen bleiben ausdrücklich dokumentiert: Handlerbindung der drei Integrationsaktionen, Attributabweichung beim normalen Team-Tabellenplatzsensor und Legacy-Teilnehmerfallback für Turniere ohne Tabelle. Siehe [Fehlersuche](fehlersuche.md), [Dashboard-Karten](dashboard-karten.md) und [Entwicklung](entwicklung.md).

Die Sicherheitskorrekturen und anschließend die drei Logo-Karten wurden gezielt in einer Pilotinstallation aktiviert und begrenzt geprüft. Das belegt **keinen vollständigen HACS-/Fork-Wechsel** und keine Installation des gesamten Quellbaums einschließlich aller Metadaten. Die Anleitungen zur Neuinstallation, Migration und zum vollständigen Rollback bleiben gesondert abzunehmen.
