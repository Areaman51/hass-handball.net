# Handball.net Community für Home Assistant

Spielpläne, Tabellen, Mannschaften und Kalender von **handball.net** in Home Assistant – mit drei mitgelieferten Dashboard-Karten.

**Community-Fork:** [Areaman51/hass-handball.net](https://github.com/Areaman51/hass-handball.net)

**Basis und Dank:** [miggi92/hass-handball.net](https://github.com/miggi92/hass-handball.net), veröffentlicht unter der [MIT-Lizenz](LICENSE). Die ursprünglichen Urheber- und Lizenzhinweise bleiben erhalten.

Dieser Fork führt Verbesserungen aus der PR-88-Historie, zusätzliche Reparaturen am API-Zugriff und Sicherheits-/Robustheitskorrekturen zusammen. Der öffentliche Source-Stand ist dadurch nicht vollständig bytegleich mit einer unverändert weiterlaufenden HA-Installation; eine Prüfung des Ausgangsstands belegt keine Ausrollung dieser zusätzlichen Änderungen. Er ist ein eigenständiges Community-Angebot, keine offizielle Integration von handball.net oder Home Assistant. Damit ist **keine Aussage über eine Aufgabe des Originalprojekts** verbunden. Zusammenarbeit mit dem Originalprojekt und anderen Beitragenden ist ausdrücklich willkommen.

> **Entwicklungsstand: `0.0.32.dev0` auf `main`, kein veröffentlichtes Release.**
> Eine vollständige Releaseabnahme liegt nicht vor. Insbesondere ist der Wechsel einer vorhandenen HACS-Installation vom Original zum Fork **noch nicht praktisch getestet**. Vor einem Umstieg unbedingt [Backup, Umstieg und Rollback](docs/installation-und-umstieg.md) lesen. Bestehende Home-Assistant-Konfigurationseinträge **nicht löschen**.

[English summary](docs/README.en.md) · [Änderungen](CHANGELOG.md) · [Mitmachen](CONTRIBUTING.md) · [Sicherheit und historische Daten](SECURITY.md)

## Inhalt

- [Funktionen und Grenzen](#funktionen-und-grenzen)
- [Installation](#installation)
- [Neueinrichtung](#neueinrichtung)
- [Optionen und Saisonwechsel](#optionen-und-saisonwechsel)
- [Entitäten](#entitäten)
- [Dashboard-Karten](#dashboard-karten)
- [Aktualisierung und Fehlersuche](#aktualisierung-und-fehlersuche)
- [Dokumentation und Entwicklung](#dokumentation-und-entwicklung)
- [Lizenz und Unterstützung](#lizenz-und-unterstützung)

## Funktionen und Grenzen

- Einzelnes Team per aktueller Team-ID oder Vereinssuche einrichten.
- Einen Verein mit einer oder mehreren ausgewählten Mannschaften verwalten; zusätzliche Vereinsübersicht mit nächsten Spielen und Logos.
- Liga/Turnier über Verein und Team oder über Wettbewerb und Staffel auswählen.
- Pro Team Spiel-, Statistik-, Tabellen-, Gesundheits- und Live-Sensoren sowie einen Spielplankalender bereitstellen.
- Turniertabelle, Spielplan nach Spieltagen und Kalender anzeigen; bei fehlender Tabelle einen Hilfssensor für verbleibende Teams anlegen.
- Mitgelieferte Karten: `handball-team-card`, `handball-tournament-table-card`, `handball-schedule-card`.
- Optional eigene Vereinsbilder über `logo_overrides` statt fehlerhafter API-Vorschaubilder verwenden; [Konfiguration und Grenzen](docs/dashboard-karten.md#eigene-vereinslogos-logo_overrides).
- API-Fehler protokollieren und Diagnosedaten zum Prüfen bereitstellen.

Die Daten kommen von einem externen Dienst. Vollständigkeit, Verfügbarkeit und Live-Aktualität sind nicht garantiert. „Live“ wird überwiegend aus einem **Zweistundenfenster ab angesetztem Spielbeginn** abgeleitet, nicht aus einem bestätigten Spielstatus. API-Caches begrenzen die tatsächliche Aktualität. Pokale ohne Tabelle sind eingeschränkt, weil ein Teilnehmer-Fallback noch die alte API verwendet. Weitere Einschränkungen stehen in der [Entitätenreferenz](docs/entitaeten.md) und der [Kartenanleitung](docs/dashboard-karten.md).

## Installation

Voraussetzungen: eine gesicherte Home-Assistant-Installation, ausgehender HTTPS-Zugriff auf handball.net und die Bereitschaft, eine Entwicklungsversion zu testen. `hacs.json` nennt derzeit Home Assistant **2026.11.0** als Mindestversion; das ist keine Zusage einer vollständig getesteten Kompatibilitätsmatrix.

### Manuell aus Source – nachvollziehbarer Installationsweg

1. Den Branch **`main` dieses Forks** als Source-Archiv herunterladen: im Fork auf GitHub **Code → Download ZIP**, nachdem `main` ausgewählt wurde. Für reproduzierbare Installationen den verwendeten Commit notieren.
2. Archiv entpacken. Nur den darin enthaltenen Ordner **`custom_components/handballnet`** einschließlich seiner Unterordner verwenden, nicht das gesamte Repository.
3. Diesen Ordner in das Home-Assistant-Konfigurationsverzeichnis unter **`custom_components/handballnet`** kopieren. Das ist ein Pfad relativ zu deiner HA-Konfiguration; der tatsächliche Speicherort hängt von deiner Installation ab.
4. Bei vorhandener Installation erst das [Umstiegsverfahren](docs/installation-und-umstieg.md) befolgen: vollständiges Backup, bisherige Integrationsdateien separat sichern, Home Assistant stoppen und den alten Komponentenordner vollständig ersetzen. Keine zweite Kopie und keine verschachtelten `handballnet/handballnet`-Ordner anlegen.
5. Home Assistant starten beziehungsweise nach einer Neueinrichtung neu starten. Protokoll auf Ladefehler prüfen.
6. Erst bei einer **wirklichen Neuinstallation** die Integration wie unten beschrieben hinzufügen. Bei einem Umstieg vorhandene Einträge weiterverwenden.

Ein Fork-Release-Asset wird hierfür nicht benötigt. Die Entwicklungsversion ist kein bereits abgenommenes Release-ZIP.

### HACS als benutzerdefiniertes Repository – bedingt und ungetestet

Das Repository ist **nicht als Bestandteil des HACS-Standardkatalogs zugesagt**. Wenn deine HACS-Version benutzerdefinierte Integrations-Repositories unterstützt, verwende:

- Repository: `https://github.com/Areaman51/hass-handball.net`
- Kategorie: **Integration**
- Branch/Version: **`main` nur dann auswählen, wenn deine HACS-Version dies tatsächlich anbietet**.

Der Fork verwendet für diesen Entwicklungsstand `zip_release: false`; es wird kein vorhandenes Release-Asset vorausgesetzt. Das garantiert jedoch nicht, dass jede HACS-Version ein Repository ohne Fork-Release aus `main` installieren kann. Fehlt die Auswahl, **nicht ein anderes Release als Ersatz auswählen**, sondern manuell aus Source installieren.

Der Wechsel eines bereits verwalteten Original-Repositories zum Fork ist noch nicht real getestet. **Nicht die Integration in Home Assistant löschen und nicht Original und Fork parallel installieren.** Details und Rückweg: [Installation und Umstieg](docs/installation-und-umstieg.md).

## Neueinrichtung

Die Integration wird über die Oberfläche eingerichtet, **nicht über `configuration.yaml`**:

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen und nach **Handball.net** suchen. Bezeichnungen können je nach HA-Version/Sprache leicht abweichen.
2. Im ersten Dialog **Team** oder **Tournament/Turnier** wählen. „Verein“ ist kein eigener Startpunkt.
3. Bei Bedarf die Intervalle anpassen: `update_interval` standardmäßig **3600 Sekunden**, `update_interval_live` **15 Sekunden**. Zunächst die Standardwerte verwenden; keine Null- oder Negativwerte eingeben.

### Einzelnes Team per ID

Unter **Team** den Modus **Manual Team ID** wählen und die **aktuelle** Team-ID aus handball.net eintragen, keine vollständige URL. Der Code prüft die ID über den Team-Endpunkt. Historische IDs im Format `id.…` aus der alten API sind keine verlässliche Vorlage für die heutige API. Wenn die ID unklar ist, die Vereinssuche nutzen.

### Verein mit ausgewählten Teams

1. **Team → Search by Club** wählen.
2. Im Feld Vereinsname mindestens zwei Zeichen eingeben.
3. Den passenden Verein aus den Suchergebnissen auswählen, gegebenenfalls den Verband beachten.
4. Eine oder mehrere Mannschaften in der Mehrfachauswahl markieren. Altersklasse, Geschlecht und gegebenenfalls Wettbewerb helfen bei der Unterscheidung.
5. Bestätigen. Es entsteht ein **Vereinseintrag** mit den ausgewählten Teams und einer Vereinsübersicht – auch wenn nur ein Team ausgewählt wurde.

Ein bereits als Einzelteam oder in einem Verein konfiguriertes Team wird bei einer weiteren Auswahl als Duplikat abgewiesen. Für mehrere Mannschaften desselben Vereins daher vorzugsweise die Auswahl des vorhandenen Vereinseintrags ändern.

### Turnier, Liga oder Staffel

Unter **Tournament/Turnier** stehen zwei Wege zur Verfügung:

- **Search by Club:** Verein suchen → Verein auswählen → ein Team auswählen. Die Integration übernimmt die Phase aus dem ersten von der API gelieferten Spiel dieses Teams. Gibt es noch keinen Spielplan oder spielt das Team in mehreren Wettbewerben, kann dieser Weg ungeeignet sein.
- **Search by Competition:** Wettbewerbsnamen mit mindestens zwei Zeichen suchen → Wettbewerb auswählen → Phase/Staffel auswählen. Damit lässt sich die gewünschte Gruppe gezielter festlegen.

Intern bezeichnet `tournament_id` hier die **Phase/Staffel**, nicht die übergeordnete Wettbewerbs-ID. Eine freie manuelle Turnier-ID-Eingabe ist im aktuellen Einrichtungsdialog nicht implementiert.

## Optionen und Saisonwechsel

- **Optionen/Konfigurieren:** `update_interval` und `update_interval_live` ändern. Die Optionen enthalten keine Saison-, Team- oder Token-Einstellungen. Weil der Coordinator seine Intervalle bei der Erstellung einliest, den Eintrag anschließend neu laden, falls die Änderung nicht wirksam wird.
- **Neu konfigurieren:** Für Einzelteam- und Vereinseinträge implementiert. Eine Team-ID lässt sich manuell neu prüfen; eine Vereinssuche mit Teamauswahl speichert einen Vereinseintrag. Beim vorhandenen Verein wird nach Möglichkeit direkt die aktuelle Mannschaftsliste angeboten.
- Es gibt **keinen automatischen garantierten Saisonwechsel**, keinen Saisonwähler und keine implementierte Turnier-Neukonfiguration. Eine neue Staffel bei Bedarf als zusätzlichen Turniereintrag einrichten, Verweise prüfen und den alten Eintrag zunächst erhalten.
- Änderungen an Teamnamen, Auswahl oder Eintragsart können Entitäts-/Gerätezuordnungen beeinflussen. Vor Saisonänderungen sichern und Dashboard-/Automationsverweise anschließend kontrollieren; dauerhafte ID-Stabilität wird nicht zugesagt.

Die technischen Schlüssel und Grenzen erläutert [Konfiguration und Saisonwechsel](docs/konfiguration.md).

## Entitäten

| Einrichtung | Bereitgestellte Daten |
|---|---|
| Einzelteam | Neun Sensoren: Alle Spiele, Heimspiel, Auswärtsspiel, Nächstes Spiel, Statistik, Tabellenplatz, Live-Ticker, Live Events, Health; außerdem ein Live-Binärsensor und ein Kalender |
| Verein | Dieselben Entitäten für jedes ausgewählte Team plus ein Vereinsübersichtssensor |
| Turnier/Staffel | Tabelle, Spielplan-Sensor und Kalender; Positionssensoren aus den beim Einrichten vorhandenen Tabellenzeilen; ohne Tabelle zusätzlich „Verbleibende Teams“ |

Alle Beispiel-Entitätsnamen in dieser Dokumentation sind **fiktiv**. Die tatsächlichen IDs in Home Assistant prüfen und in den Beispielen ersetzen. Attribute sind teils strukturierte Objekte, nicht bloß Text. Insbesondere unterscheiden sich Teamobjekte im Nächste-Spiel-Sensor von den Zeichenketten im Heim-/Auswärtsspiel-Sensor.

Vollständige Übersicht mit Attributen, Zeitformaten und Einschränkungen: [Entitäten und Kalender](docs/entitaeten.md).

## Dashboard-Karten

Die Integration stellt die drei JavaScript-Dateien selbst bereit und bindet sie beim Laden des Backends über `add_extra_js_url` ein. Dafür werden weder `button-card` noch andere zusätzliche Karten benötigt. Nach Installation/Update Home Assistant neu starten und das Dashboard im Browser neu laden.

Im Dashboard eine manuelle Karte hinzufügen und ihre YAML-Konfiguration bearbeiten. Folgendes Beispiel nutzt nur den Nächste-Spiel- und Live-Ticker-Sensor:

```yaml
type: custom:handball-team-card
title: SG Beispielstadt
next_match_entity: sensor.sg_beispielstadt_naechstes_spiel
live_ticker_entity: sensor.sg_beispielstadt_live_ticker
```

Für eine **Turniereinrichtung**:

```yaml
type: custom:handball-tournament-table-card
entity: sensor.beispielliga_tabelle
title: Beispielliga
highlight_team: SG Beispielstadt
show_logo: true
```

```yaml
type: custom:handball-schedule-card
entity: sensor.beispielliga_spielplan
table_entity: sensor.beispielliga_tabelle
title: Beispielliga
highlight_team: SG Beispielstadt
```

**Bekannte Einschränkung der Teamkarte:** `table_position_entity` ist ein echter Konfigurationsschlüssel, die Karte erwartet aber ein Attribut `position`. Der normale Team-Tabellenplatzsensor liefert den Rang nur als Zustand, nicht als solches Attribut. Damit bleibt dieser Kartenabschnitt derzeit leer. Ein vorhandener Turnier-Positionssensor liefert das benötigte Attribut; die [Kartenanleitung](docs/dashboard-karten.md) zeigt beide Fälle und die Ressourcen-Fehlersuche. Auch Vorschaudaten sind kein Funktionsnachweis.

### Vereinslogos austauschen

Bereits beschnittene oder mit einem unerwünschten Hintergrund gelieferte API-Logos lassen sich in **allen drei Karten** durch eine eigene vorhandene Bildquelle ersetzen. Die [Schritt-für-Schritt-Anleitung](docs/dashboard-karten.md#schritt-für-schritt-ein-logo-austauschen) erklärt lokale Dateien unter `www/vereinslogos`, externe Bildadressen, die Zuordnung per `logo_overrides`, Bildwechsel trotz Browsercache und die Rückkehr zum API-Logo. Der Block wird derzeit je Karte gepflegt; eine zentrale Logo-Verwaltung im Optionen-Dialog der Integration ist **noch nicht enthalten**.

## Aktualisierung und Fehlersuche

Ein Coordinator bündelt die Abfragen je Eintrag. Team-/Vereinseinträge wechseln nach Erkennung eines laufenden Spiels vom Standard- auf das Live-Intervall. **Das ist kein Push-Dienst:** Spielpläne und Tabellen werden zusätzlich bis zu eine Stunde, Teaminformationen bis zu sechs Stunden gecacht. Der schnelle Live-Takt gilt nicht automatisch für alle Ergebnisdaten. Turniere bleiben im normalen Coordinator-Takt; ein Spielbeginn wird bei langem Standardintervall nicht sekundengenau erkannt.

Bei Fehlern:

1. Prüfen, ob das betroffene Team/die Staffel auf handball.net Daten hat.
2. Home-Assistant-Protokolle für `custom_components.handballnet` und gegebenenfalls den Diagnosedownload prüfen.
3. Bei **HTTP 403** den aktuellen Fork-Stand überprüfen: Der Client lädt selbst einen öffentlichen Client-Token aus der Webseite, setzt einen auf diese Requests begrenzten User-Agent und erneuert den Token nach 403 einmalig. Es gibt **kein Tokenfeld**, keine manuell zu kopierenden Cookies und keinen garantierten Schutz vor Sperren.
4. Bei **429** Intervalle vergrößern und wiederholtes manuelles Abfragen vermeiden.
5. Bei leeren oder alten Daten Health-Attribute, Coordinator-Erfolg, Cachezeiten und den gewählten Wettbewerb prüfen. Ein fehlgeschlagener Abruf ist nicht gleichbedeutend mit „keine Spiele“.

[Fehlersuche, Diagnose und Abfrageverhalten](docs/fehlersuche.md) beschreibt Statuscodes, Aktionen, Datenschutz und die bekannten Grenzen genauer.

## Dokumentation und Entwicklung

- [Installation, Umstieg und Rollback](docs/installation-und-umstieg.md)
- [Konfiguration und Saisonwechsel](docs/konfiguration.md)
- [Entitäten, Attribute und Kalender](docs/entitaeten.md)
- [Dashboard-Karten und YAML-Referenz](docs/dashboard-karten.md)
- [Fehlersuche, Diagnose und Caches](docs/fehlersuche.md)
- [Entwicklung und Testgrenzen](docs/entwicklung.md)
- [Prüfstand: 61 Python- und 55 Node-Tests, echte API-Abfragen](docs/pruefstand.md)
- [English summary](docs/README.en.md)

Entwicklung mit **Python 3.13 oder neuer**, isolierter virtueller Umgebung und `requirements-test.txt`. Die pytest-Suite verwendet bei fehlendem Home Assistant **HA-Stubs**; sie ersetzt keine Integrationstests in einer echten HA-Instanz, keine Browserprüfung und keine HACS-Umstiegsprüfung. Die Python-Regressionssuite und ergänzende Node-Tests werden lokal ausgeführt; ein erfolgreicher echter API-Smoke betraf ausgewählte Datenpfade. Eine abschließende Testzahl beziehungsweise Abnahme ist stets an den konkret geprüften Commit gebunden. Die vorhandenen GitHub-Workflows führen pytest/Node derzeit nicht aus. Details und reproduzierbare Befehle stehen in der [Entwicklungsdokumentation](docs/entwicklung.md).

## Lizenz und Unterstützung

Sicherheitsmeldungen, Diagnose-Datenschutz und die geerbte Repository-Historie erläutert [SECURITY.md](SECURITY.md). Historische Laufzeit-/Authentifizierungs-/Datenbankdateien wurden aus dem aktuellen Sourcebaum entfernt, bleiben aber möglicherweise in alten Commits und Kopien erhalten. Es gibt keine pauschale Zusage einer geheimnisfreien Git-Historie.

Die [MIT-Lizenz](LICENSE) einschließlich `Copyright (c) 2026 miggi92` bleibt erhalten. Die historische [Änderungshistorie](CHANGELOG.md) enthält weiterhin die ursprünglichen Beiträge und Versionshinweise. Historische Migrationsanweisungen darin ersetzen **nicht** die aktuelle Umstiegsanleitung dieses Forks.

Fehlerberichte, Dokumentationskorrekturen, Regressionstests und Pull Requests sind willkommen: [Beitragen](CONTRIBUTING.md). Bitte Fragen zum Fork im Fork einreichen und nicht automatisch beim Originalprojekt. Es gibt keine garantierte Reaktionszeit. Sponsorhinweise des Originals sind keine Finanzierung oder Supportzusage dieses Forks; hier wird keine solche Verbindung behauptet.
