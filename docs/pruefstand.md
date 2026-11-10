# Prüfstand 0.0.32.dev0

Stand: **10. November 2026**. Geprüft wurde der zusammengeführte Entwicklungsquellbaum vor seiner Veröffentlichung auf `main`, einschließlich der zusätzlichen Karten- und Textdekodierungsreparaturen. Die ausgeführten Prüfungen sind unten getrennt von offenen Abnahmen aufgeführt.

## Tatsächlich ausgeführte Prüfungen

Umgebung: **Python 3.13.5**, frische virtuelle Testumgebung mit den direkten Abhängigkeiten aus `requirements-test.txt`; **Node.js v26.12.1**.

- `python -m pytest -q`: **61 bestanden**. Die Suite verwendet HA-Ersatzmodule; HTTP-Protokolltests nutzen echte lokale aiohttp-Sockets mit kontrollierten Antworten.
- `node --test tests/test_card_security.js`: **55 bestanden**. Reale Karten-/Editorquellen im Node-VM, simulierte DOM-Grenze; Tests für Escaping, unsichere Logo-URLs, gewöhnliche Logos, identische DOM-Updates und Konfigurationswechsel.
- `node --check` für alle drei mitgelieferten JavaScript-Karten: erfolgreich.
- `ruff check --select E9,F63,F7,F82 custom_components tests`: erfolgreich. Das ist eine gezielte Syntax-/Fehlerklassenprüfung, **kein vollständig grüner Lauf des umfangreichen repositoryweiten Ruff-Regelwerks**.
- Markdown-Verweisziele sowie 13 YAML-Beispiele statisch geprüft; historischer Changelog ab v0.0.31 unverändert erhalten.
- Echter, begrenzter Abruf über den zusammengeführten Client gegen handball.net: Teaminformation, vollständiger Spielplan über zwei Seiten (**26 eindeutige Spiele**, abgeglichen mit der API-Gesamtzahl) und Tabelle (**14 Mannschaften**) erfolgreich, keine HTTP-Fehler. Dies beschreibt einen Abruf ausgewählter Datenpfade, keine dauerhafte Verfügbarkeitszusage.

Für die vier neuen Dekodierungsfälle und die Karten-/URL-Sicherheitsregressionen wurden zuerst scheiternde Tests beobachtet und anschließend die vollständigen Suiten erneut erfolgreich ausgeführt. Testfixtures enthalten künstliche Angriffswerte und künstliche Tokenzeichenketten, keine aus einer privaten HA-Installation übernommenen Zugangsdaten.

## Was damit nicht abgenommen ist

- Kein vollständiger echter Home-Assistant-Integrationstest und kein vollständiger Browser-/Frontendtest.
- Kein praktischer HACS-Wechsel, kein Installations-/Update-/Rollback-End-to-End-Test.
- Keine vollständige Prüfung von Team-/Vereins-/Turnier-Neueinrichtung, Saisonwechsel, Kalenderzeitzonen, allen Live-Funktionen oder allen deklarierten Aktionen.
- Kein stabiles Fork-Release, kein Release-Asset und keine Zusage der Aufnahme in den HACS-Standardkatalog.
- Keine automatisch laufende pytest-/Node-Pipeline auf GitHub: die vorhandenen Workflows führen diese Suiten noch nicht aus. GitHub-Validierungsstatus ist separat am jeweiligen Commit zu prüfen.

Bekannte funktionale Einschränkungen bleiben ausdrücklich dokumentiert: Handlerbindung der drei Integrationsaktionen, Attributabweichung beim normalen Team-Tabellenplatzsensor und Legacy-Teilnehmerfallback für Turniere ohne Tabelle. Siehe [Fehlersuche](fehlersuche.md), [Dashboard-Karten](dashboard-karten.md) und [Entwicklung](entwicklung.md).

Die zusätzlichen Sicherheits-/Robustheitskorrekturen wurden bei dieser Veröffentlichung **nicht in eine produktive Home-Assistant-Installation ausgerollt**. Eine frühere Live-Prüfung der zugrunde liegenden Reparaturbasis ist nicht gleichbedeutend mit einer Aktivierung dieses gesamten Entwicklungsstands.
