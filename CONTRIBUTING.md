# Zum Community-Fork beitragen

Danke für Fehlerberichte, Tests, Dokumentationsverbesserungen und Codebeiträge. Zusammenarbeit mit dem Originalprojekt von **miggi92** und anderen Beitragenden ist ausdrücklich willkommen. Der Fork behauptet nicht, dass das Original aufgegeben wurde. Beiträge bleiben unter der vorhandenen **MIT-Lizenz**; bestehende Urheberhinweise müssen erhalten bleiben.

## Wohin mit einem Beitrag?

Issues und Pull Requests für diesen Fork gehören zu **Areaman51/hass-handball.net**. Bitte nicht automatisch Supportanfragen zum Fork beim Originalprojekt eröffnen. Eine Rückführung gemeinsam nutzbarer Änderungen kann abgestimmt werden; ein eigener Fork-Beitrag verändert keinen offenen Upstream-PR von selbst.

Deutsch und Englisch sind willkommen. Die [README](README.md) ist die deutsche Hauptanleitung; eine [englische Kurzfassung](docs/README.en.md) erleichtert den Einstieg.

## Einen Fehler melden

Vorher [Fehlersuche](docs/fehlersuche.md) und bekannte Grenzen prüfen. Ein guter Bericht enthält:

- Integrationsversion und konkreten Commit, Home-Assistant-Version und Installationsart;
- Team-/Vereins-/Turniereintrag und betroffene Funktion;
- reproduzierbare Schritte, erwartetes und tatsächliches Verhalten;
- bereinigten Logausschnitt mit Zeitpunkt/Zeitzone, HTTP-Status und Endpunkt;
- Information, ob es ein echter HA-Lauf, ein Stub-Test oder eine Karten-Vorschau war;
- bei Karten die minimale Konfiguration mit neutralen Entitätsnamen.

Sicherheitsmeldungen und den transparenten Hinweis zu geerbten Laufzeit-/Authentifizierungs-/Datenbankdateien in der erhaltenen Git-Historie beschreibt [SECURITY.md](SECURITY.md). Die Bereinigung des aktuellen Sourcebaums entfernt keine alten Commits oder fremden Kopien.

**Datenschutz:** Keine Backups, `.storage`-Dateien, HA-Datenbanken, Zugangsdaten, Tokens, Cookies, private Systemadressen oder unbearbeiteten Diagnosedownloads anhängen. Team-/Vereinsdaten und Hallen können persönliche Zusammenhänge offenlegen; nur das für den Fehler notwendige Minimum teilen. Für reproduzierbare Tests bevorzugt neutrale synthetische Fixtures verwenden. Einen sicherheitsrelevanten Fund nicht durch Veröffentlichung des betroffenen Geheimnisses belegen. Es wird kein bestimmter vertraulicher Meldekanal zugesagt; falls keiner angeboten wird, zuerst ohne sensible Details um einen geeigneten Kanal bitten.

## Code und Tests

Die [Entwicklungsanleitung](docs/entwicklung.md) beschreibt Python 3.13+, virtuelle Umgebung und `requirements-test.txt`.

1. Kleine, klar abgegrenzte Änderung auf einem eigenen Branch vorbereiten.
2. Für einen reproduzierbaren Fehler möglichst zuerst einen fehlschlagenden Regressionstest schreiben.
3. `python -m pytest -q` in der dokumentierten Umgebung sowie für die JS-Regressionen `node --test tests/test_card_security.js` ausführen; tatsächliche Ergebnisse mit Python-/Node-Version und Datum angeben.
4. Betroffene Dateien gezielt linten und neue Verstöße beseitigen. Keine großen, fachfremden Formatierungsänderungen verstecken.
5. Bei Änderungen an Flows, Attributen, Karten oder Aktionen die Dokumentation und gegebenenfalls den Entwicklungsabschnitt des Changelogs aktualisieren.
6. Migrationsrisiken ausdrücklich nennen: Domain `handballnet`, Config-Entries, Unique IDs und Dashboard-/Automationsverweise sind Teil des Vertrags.

Die Tests mit HA-Stubs sind **keine echten Home-Assistant-Integrationstests**. Eine bestandene Suite belegt keine funktionierende Servicebindung, Browserdarstellung oder HACS-Migration. Manuelle Tests mit echter Testinstanz separat beschreiben; fehlende Tests offen benennen. Vorhandene GitHub-Workflows führen pytest/Node noch nicht aus, daher keinen automatischen Teststatus aus HACS-/hassfest-Ergebnissen ableiten.

## API und verantwortlicher Betrieb

- Keine Tokens oder persönlichen Daten in Code, Fixtures oder Logs einbauen.
- Fehler nicht als erfolgreich geladene leere Daten tarnen und fehlgeschlagene Antworten nicht als gültigen Cacheinhalt speichern.
- Abfrageintervalle, Caches und Retry-Grenzen respektieren; keine aggressive Dauerabfrage oder Sperrumgehung als Fehlerbehebung einführen.
- Config-/Options-/Service- und Kartenkonfiguration gegen den ausführenden Code prüfen, nicht nur gegen Kommentare.
- Echte HA-Handlerbindung, Verfügbarkeit bei Teilfehlern und Wiedererholung bei wesentlichen Änderungen separat testen.

## Pull-Request-Beschreibung

Kurz nennen: Problem, Änderung, Kompatibilitäts-/Migrationsfolgen, tatsächlich ausgeführte Tests und offene Prüfungen. Versions- oder Releasebehauptungen nur dann machen, wenn das entsprechende Artefakt und die Abnahme vorliegen. Der aktuelle Stand `0.0.32.dev0` auf `main` ist eine Entwicklungsversion; ein HACS-Quellenwechsel ist noch nicht praktisch abgenommen.

Es gibt keine garantierte Reaktions- oder Supportzeit. Sponsoring des Originals ist keine Supportzusage dieses Forks.
