# Prüfstand 0.0.32.dev0

Stand: **12. November 2026**. Dieser Prüfstand umfasst die Sicherheits-/API-Basis, individuelle Logoquellen, zentrale Logo-Verwaltung und größere Nächstes-Spiel-Logos. Nach isolierten Prüfungen wurde ein gezielter Backend-/Karteneinbau in einer HA-2026.11.1-Pilotinstallation mit bestehenden Einträgen geprüft und vom Nutzer abgenommen. Kein vollständiger Marketplace-/HACS-Quellenwechsel und keine vollständige Releaseabnahme.

## Zentrale Logo-Verwaltung – 12. November 2026

- `python -m pytest -q`: **155 bestanden** mit der Stub-Testumgebung.
- `node --test tests/test_card_security.js tests/test_logo_overrides.js tests/test_central_logo_cards.js tests/test_next_match_logo_size.js`: **144 bestanden**, kein Fehler oder übersprungener Fall. Node-VM-/DOM-Doubles sind keine Browserabnahme. Vier ergänzte Größenregressionen prüfen echte generierte Karten-CSS/Markups: Nächstes Spiel mit Bildern/Platzhaltern 64×64, Live-Ticker weiterhin 40×40.
- `ruff check --select E9,F63,F7,F82 custom_components tests` sowie Syntaxprüfungen der drei JavaScript-Karten: erfolgreich. Nur die genannten Ruff-Regeln sind damit geprüft.
- Vier native Prüfschritte mit **HA 2026.11.0 / Python 3.14.9** bestanden: echte Sensoren erhalten die Zuordnungen; nativer URL-Optionsflow; nativer PNG-Upload mit erfolgreicher HTTP-Auslieferung; bestätigte Rückkehr zum API-Original. Der Upload funktioniert auch, wenn beim Frontendstart noch kein allgemeiner `/local`-Pfad vorhanden war. Die Fixture verwendet synthetische Config-Entries und Coordinator-Daten, nicht die vollständige API-Einrichtung.
- Zusätzlich den echten deutschen Optionsdialog im Chromium bedient: Mannschaft ausgewählt, eigene synthetische PNG-Datei hochgeladen und gespeichert. Neue Zuordnung und Revision bei **vier Sensorquellen** zurückgelesen, ohne API-Neuabfrage oder Neustart.
- Alle **drei Karten** in der angemeldeten isolierten HA-Oberfläche bei **390 und 1200 Pixeln** sichtbar geprüft: die zentral hochgeladene Beispielgrafik erscheint in Teamkarte, Tabelle und Spielplan. Bei 390 Pixeln kein horizontaler Seitenüberlauf. Das ist eine gezielte Sichtprüfung, kein behaupteter vollständiger automatisierter Browser-Regressionslauf.
- Im nativen Dialog sichtbare nicht ersetzte Titel-Platzhalter wurden durch statische Titel und dynamische Mannschaftsnamen im Beschreibungstext korrigiert; zwei zusätzliche Sprachregressionen wurden zuerst scheiternd und danach erfolgreich ausgeführt.
- Das unabhängige Backendreview fand einen Listenerfehler nach anfänglich defektem Logo-Speicher. Drei zusätzliche Regressionen prüfen jetzt den echten Integrationscode mit vier Sensorklassen, spätere Store-Reparatur, sofortige Veröffentlichung erst nach erfolgreicher Speicherung, ausbleibende API-/Reload-Aufrufe und korrektes Abmelden. Der Fehler wurde zusätzlich in einer gezielten nativen HA-Prüfung am alten Export reproduziert und nach dem Fix erfolgreich gegengeprüft. Die normale öffentliche Smoke-Fixture behält ihre vier oben genannten Schritte; diese zusätzliche native Recovery-Prüfung war ein gesonderter lokaler Prüflauf.

Die native Fixture und ihre reproduzierbaren Befehle stehen in [Entwicklung](entwicklung.md#nativer-logo-smoke-unter-ha-2026110), die Bedienung in [Vereinslogos](vereinslogos.md). Kein produktiver Backend-Einbau und keine vollständige HACS-/Releaseabnahme durch diese Tests.

## Gezielter Backend-/Kartenpilot – 12. November 2026

- Zusätzlich beide nativen Prüfpfade unter der exakten Pilotversion **HA 2026.11.1** erfolgreich ausgeführt; die isolierte Testumgebung bleibt von der produktiven Instanz getrennt.
- Nach Sicherung 14 gezielte Laufzeitdateien installiert, bestehende Einträge/Optionen/Entitäten erhalten und genau einen Core-Neustart durchgeführt. Beide Integrationseinträge geladen, 29 aktive Entitäten verfügbar, Teamhealth gesund und Konfigurationsprüfung gültig. Manifestmetadaten und Verwaltungsquelle wurden beim Pilot nicht vollständig auf den Fork umgestellt; nur die zusätzliche Upload-Abhängigkeit ergänzt.
- Echte native Optionsflows der Pilotinstanz für Bildadresse, Bildupload und bestätigtes API-Reset durchgeführt. Änderungen sofort bei vier Sensorquellen und anschließend in der persistenten Registry zurückgelesen. Ein vollständiges eigenes Vereinslogo zentral hinterlegt, danach nur die drei bisherigen individuellen Zuordnungen entfernt; übrige Dashboardinhalte durch inversen Vergleich unverändert bestätigt.
- Auslieferung aller drei JS-Dateien mit und ohne aktuelle Versionsquery hashgenau geprüft. Sechs echte Browserfälle mit diesen Bytes, Bildern sowie frischen gespeicherten Kartenkonfigurationen/Entitätsdaten: alle drei Karten bei 390/1100 Pixeln, zentrale Grafik geladen, keine JS-Fehler oder horizontaler Seitenüberlauf. Nächstes-Spiel-Logos 64×64, Tabelle und Spielplan weiterhin 20×20. Separate Kartenhülle; **keine vollständige angemeldete HA-/Companion-App-Abnahme**. Die eigene Clientdarstellung wurde zusätzlich vom Pilotnutzer bestätigt.
- Der Pilot bestätigt diese Funktionen, nicht jede Integrationsfunktion und keinen vollständigen Marketplace-/HACS-Migrationsweg. Keine privaten Grafiken, Entitätskennungen, Zugangsdaten oder Installationssicherungen im Repository.

## Historischer Prüfstand der individuellen Overrides – 11. November 2026

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

- Kein vollständiger Einrichtungs-/Migrationstest der Gesamtintegration und kein vollständiger Browser-/Frontendtest. Der native Logo-Smoke und die gezielte Logo-Sichtprüfung decken nur ihre genannten Teilpfade ab.
- Kein praktischer HACS-Wechsel, kein Installations-/Update-/Rollback-End-to-End-Test.
- Keine vollständige Prüfung von Team-/Vereins-/Turnier-Neueinrichtung, Saisonwechsel, Kalenderzeitzonen, allen Live-Funktionen oder allen deklarierten Aktionen.
- Kein stabiles Fork-Release, kein Release-Asset und keine Zusage der Aufnahme in den HACS-Standardkatalog.
- Keine automatisch laufende pytest-/Node-Pipeline auf GitHub: die vorhandenen Workflows führen diese Suiten noch nicht aus. GitHub-Validierungsstatus ist separat am jeweiligen Commit zu prüfen.

Bekannte funktionale Einschränkungen bleiben ausdrücklich dokumentiert: Handlerbindung der drei Integrationsaktionen, Attributabweichung beim normalen Team-Tabellenplatzsensor und Legacy-Teilnehmerfallback für Turniere ohne Tabelle. Siehe [Fehlersuche](fehlersuche.md), [Dashboard-Karten](dashboard-karten.md) und [Entwicklung](entwicklung.md).

Die Sicherheitskorrekturen und anschließend die drei Logo-Karten wurden gezielt in einer Pilotinstallation aktiviert und begrenzt geprüft. Das belegt **keinen vollständigen HACS-/Fork-Wechsel** und keine Installation des gesamten Quellbaums einschließlich aller Metadaten. Die Anleitungen zur Neuinstallation, Migration und zum vollständigen Rollback bleiben gesondert abzunehmen.
