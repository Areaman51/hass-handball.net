# Entwicklung und Testgrenzen

[Zur Hauptanleitung](../README.md) · [Beitragen](../CONTRIBUTING.md)

## Entwicklungsstand

`main` ist als **0.0.32.dev0** dokumentiert, nicht als veröffentlichtes stabiles Fork-Release. Basis sind das Original von miggi92 und die PR-88-Historie mit Spielplan-/Karten-/Diagnoseverbesserungen. Zusätzliche November-Reparaturen betreffen öffentlichen Client-Token, requestspezifischen User-Agent sowie die Fehlerweitergabe in `http_client.py`, `api.py` und `coordinator.py`. Dazu kommen Sicherheitskorrekturen gegen HTML-/Script-Injektion in Team-/Tabellenkarten und eine kontrollierte Behandlung ungültiger Textdekodierung im HTTP-Pfad. Der öffentliche GitHub-Stand ist damit nicht mehr vollständig bytegleich mit einer unverändert weiterlaufenden HA-Installation. Eine Live-Prüfung des Ausgangsstands ist keine Ausrollung der zusätzlichen Korrekturen.

Quellgleichheit mit einem verwendeten Stand, ein erfolgreicher Abruf einzelner Endpunkte und eine bestandene Unit-Suite sind jeweils unterschiedliche Nachweise. Keiner davon ersetzt eine vollständige Releaseabnahme.

## Kleine Testumgebung

**Python 3.13 oder neuer** verwenden. Eine frische virtuelle Umgebung verhindert, dass eine zufällig bereits installierte Home-Assistant-Version die Stub-Tests verändert. Im geklonten Repository ausführen:

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Wenn eine andere unterstützte Python-Version installiert ist, nur den Interpreter des ersten Befehls entsprechend ersetzen. `requirements-test.txt` enthält die leichte Test-/Lint-Umgebung; dafür ist keine produktive HA-Installation erforderlich. Keine persönlichen HA-Konfigurationsdaten in das Repository kopieren.

Optional für die eigene Änderung:

```bash
python -m ruff check custom_components/handballnet tests
```

Das ist ein auszuführender Check, **keine Behauptung eines bereits fehlerfreien repositoryweiten Lint-Status**. Bestehende Verstöße und neu verursachte Verstöße getrennt benennen, keinen pauschalen Formatierungsumbau in eine Fehlerkorrektur mischen.

## JavaScript-Regressionen

Für die ergänzenden Karten-/Sicherheitsregressionen ist außerdem eine Node.js-Installation mit integriertem Test-Runner erforderlich. Im Repository ausführen:

```bash
node --version
node --test tests/test_card_security.js
```

Die Node-Tests laufen lokal und prüfen gezielte JS-Regressionen mit simuliertem Kontext. Sie sind kein echter Browser-/Home-Assistant-Frontendtest. Python- und Node-Ergebnisse getrennt angeben; ein grüner Lauf ersetzt den jeweils anderen nicht.

## Was pytest hier wirklich prüft

`tests/conftest.py` installiert bei fehlendem Home Assistant kleine Ersatzmodule und Klassen. Die Tests prüfen ausgewählte Python-Logik mit simulierten HTTP-/API-Antworten: unter anderem Einrichtungsabläufe, Normalisierung, Cache-/Abfrageverhalten und die ergänzten Fehler-/Token-/User-Agent-Regressionen.

**Das sind keine echten Home-Assistant-Integrationstests.** Insbesondere nicht automatisch abgedeckt:

- Einrichten, Optionsänderungen und Reload in einer realen HA-Instanz;
- das vollständige Config-Entry-/Geräte-/Entitätsregister und dessen Migration;
- echte HA-Service-Registrierung und Handleraufrufe;
- Browserdarstellung und Lebenszyklus der JavaScript-Karten;
- HACS-Installation, Quellenwechsel, Update oder Rollback;
- reale Cloudflare-/API-Erreichbarkeit oder ein kompletter Spieltag;
- vollständige Kalender- und Zeitzoneninteraktion.

Wenn Home Assistant importierbar ist, kann die Testsuite statt der Stubs echte Module verwenden. Deshalb Interpreter, frische Umgebung und installierte Anforderungen im Testbericht angeben. Ein grüner Stub-Test kann einen fehlerhaften HA-Handler oder ein fehlendes Kartenattribut nicht ausschließen.

## Dokumentierter Teststand

Die Python-Regressionssuite wurde auf dem zusammengeführten Ausgangsstand erfolgreich lokal ausgeführt. Ein echter API-Smoke für ausgewählte Datenpfade war ebenfalls erfolgreich. Zusätzliche Sicherheits-/Robustheitskorrekturen und Node-Regressionen erweitern diesen Stand; deshalb wird hier keine feste abschließende Testzahl vorgegeben. Bei Änderungen die tatsächlich ausgeführten Befehle, Python-/Node-Versionen, Datum, Commit und Ergebnisse ergänzen. Keine Testzahlen aus Erwartungen oder aus einer alten Ausgabe übernehmen.

Die abschließende lokale Prüfung dieses Entwicklungsquellbaums am **10. November 2026** ergab **61 bestandene Python-Tests und 55 bestandene Node-Tests**. Auch der echte API-Smoke war erfolgreich. Befehle, Umgebung, Umfang und Grenzen sind im [Prüfstand](pruefstand.md) festgehalten. Das ist **keine vollständige Releaseabnahme** und schließt die oben genannten End-to-End-Lücken nicht.

## Vollständige HA-Entwicklungsumgebung

`requirements.txt` ist von `requirements-test.txt` getrennt und enthält unter anderem eine festgelegte Home-Assistant-Version sowie Frontend-/Entwicklungswerkzeuge. Diese Anforderungen nicht unbesehen in eine produktive HA-Umgebung installieren. Für eine echte Integrationsprüfung eine **separate Testinstanz** und die zur gewählten HA-Version passende Python-Version verwenden.

Die in `hacs.json` genannte Mindestversion und die in `requirements.txt` fixierte Entwicklungsbasis sind unterschiedliche Angaben. Daraus lässt sich keine vollständig getestete Kompatibilitätsmatrix ableiten. Vor einem Release müssen diese Metadaten und die wirklich getesteten Versionen aufeinander abgestimmt werden.

Die mitgelieferten Entwicklungsskripte und Containerdateien sind Hilfsmittel, keine Zusage einer vollständigen sofort lauffähigen HA-Testinstanz. Keine reale Heimkonfiguration als Testfixture verwenden.

## Architektur zur Orientierung

- `config_flow.py`: Benutzerflow, Team-/Vereins-/Wettbewerbssuche und Team-/Vereins-Neukonfiguration.
- `options_flow.py`: genau zwei Abfrageintervalle.
- `http_client.py`: gemeinsamer neuer API-Zugriff, öffentlicher Token-Bootstrap, Header, Fehlerbehandlung und Logausschnitte.
- `api.py`: Pagination, Normalisierung und API-Caches; enthält noch Legacy-Fallbackcode.
- `coordinator.py`: gemeinsames Datenmodell je Config-Entry, parallele Teamabfragen, Live-Fenster, Turniersammlung und Laufzeitmessungen.
- `sensors/`, `binary_sensor.py`, `calendars/`: Entitäten aus den Coordinator-Daten.
- `diagnostics.py`: bereinigungsbedürftiger Diagnosedownload, kein vollständiger API-Trace.
- `www/`: eigenständige JS-Karten ohne zusätzlichen Buildschritt für die mitgelieferten Dateien.
- `__init__.py`: Plattform- und Frontend-Setup, Aktionsregistrierung.

Konfigurationsschlüssel und Attributverträge müssen an diesen Implementierungen geprüft werden. Kommentare und `services.yaml` allein beweisen keine funktionierende Laufzeitintegration; bekannte Abweichungen sind in [Karten](dashboard-karten.md) und [Fehlersuche](fehlersuche.md) dokumentiert.

## GitHub-Workflows: keine pytest-/Node-Abdeckung

Die vorhandenen Workflows umfassen HACS-Validierung, hassfest und einen Veröffentlichungsworkflow für Release-Assets. **Sie führen pytest und die Node-Tests derzeit nicht aus.** Ein grüner HACS-/hassfest-Status ist weder Unit-Testnachweis noch HACS-Umstiegsabnahme.

Der Veröffentlichungsworkflow reagiert auf veröffentlichte Releases. Seine Existenz bedeutet nicht, dass `0.0.32.dev0` bereits als Release verfügbar wäre. Für die jetzige Source-Installation ist `zip_release: false` vorgesehen. Die vorhandenen Workflows bleiben unverändert; pytest und Node-Tests werden lokal ausgeführt. Eine automatische Regressionstest-Pipeline ist damit nicht eingerichtet.

## Vor einer Veröffentlichung prüfen

- Unit-/Regressionstests in der dokumentierten frischen Umgebung ausführen und tatsächliches Ergebnis dokumentieren.
- Reale HA-Testinstanz: Einzelteam, Vereinsmehrfachauswahl, Turniersuche/Phase, Optionen und Neukonfiguration prüfen.
- Handlerbindung aller in `services.yaml` deklarierten Aktionen testen; die derzeit dokumentierten Grenzen vorher beheben oder ausdrücklich beibehalten.
- Datenstörungen und Wiedererholung prüfen, einschließlich Bootstrapfehler, 403 nach Retry, 429, HTML statt JSON und Teilfehlern im Verein.
- Karten mit realen Entitätsattributen, nicht nur Musterdaten, prüfen; normalen Team-Tabellenplatzvertrag berücksichtigen.
- Kalender, Zeitzonen, verschobene Spiele und Saisonänderungen prüfen.
- HACS-Neuinstallation und Wechsel vom Original separat und mit Backup/Rollback testen; bis dahin als ungetestet führen.
- Keine privaten Konfigurationsdateien, Datenbanken, Tokens oder internen Diagnoseberichte neu veröffentlichen; MIT-/Urheberhinweise erhalten. Die geerbte historische Belastung transparent gemäß [SECURITY.md](../SECURITY.md) behandeln. Entfernte Dateien im aktuellen Baum sind kein Widerruf von Zugangsdaten und keine Bereinigung aller historischen Kopien.
- Version, HACS-Metadaten, Branch, Changelog, Installationsroute und tatsächlich vorliegende Artefakte konsistent halten.
