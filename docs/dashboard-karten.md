# Dashboard-Karten

[Zur Hauptanleitung](../README.md)

Die folgenden Schlüssel sind aus den drei Dateien unter `custom_components/handballnet/www` geprüft. Beispiele sind für den YAML-Editor einer **einzelnen Dashboard-Karte** gedacht. Alle Entitäten sind fiktiv und müssen durch die tatsächlich vorhandenen IDs ersetzt werden. Die Beispiele wurden gegen den Quellcode geprüft, nicht als vollständiger Browser-/HA-End-to-End-Test abgenommen.

## Laden und Ressourcen

Beim Backend-Setup veröffentlicht die Integration:

- `/handballnet/handball-team-card.js`
- `/handballnet/handball-tournament-table-card.js`
- `/handballnet/handball-schedule-card.js`

Sie bindet die vorhandenen Dateien selbst über `add_extra_js_url` ein, mit einer `?v=`-Abfrage aus der Dateiänderungszeit gegen alte Caches. Nach einem Update Home Assistant neu starten und alle betroffenen Browser/Apps neu laden. Keine zusätzliche HACS-Frontendinstallation erforderlich.

Wenn „Custom element doesn't exist“ erscheint, zunächst Backend-Setup, vorhandene JS-Datei, Browser-Netzwerkfehler und Cache prüfen. Nur wenn die automatische Einbindung nicht funktioniert, die benötigte URL gezielt als Dashboard-Ressource vom Typ **JavaScript-Modul** testen. Beispielsweise für die Teamkarte:

```yaml
url: /handballnet/handball-team-card.js?v=0.0.32.dev0
type: module
```

Das ist eine **Ressourcendefinition**, keine Karte und keine Integrationskonfiguration. Im UI-Ressourcenmanager URL und Ressourcentyp in die vorgesehenen Felder eintragen. Nicht zusätzlich eine zweite Kopie derselben JS-Datei laden: Die Dateien registrieren ihre Custom Elements ohne Mehrfachregistrierungs-Schutz. Doppelte Einbindung kann selbst Fehler erzeugen. Manuell gesetzte Versionsparameter nach Dateiänderungen anpassen.

## `handball-team-card`

| Schlüssel | Pflicht | Bedeutung |
|---|---|---|
| `type` | ja | `custom:handball-team-card` |
| `title` | nein | Überschreibt den abgeleiteten Namen; besonders bei Auswärtsspielen sinnvoll |
| `next_match_entity` | mindestens eines der drei Entitätsfelder | Nächstes-Spiel-Sensor mit `home_team`/`away_team` als Objekten |
| `live_ticker_entity` | siehe oben | Live-Ticker-Sensor, **nicht** Live-Binärsensor oder Live-Events-Sensor |
| `table_position_entity` | siehe oben | Sensor mit Rang im Attribut `position` und Tabellenstatistik |

Ein Minimalbeispiel, das den normalen Team-Sensor nutzt:

```yaml
type: custom:handball-team-card
title: SG Beispielstadt
next_match_entity: sensor.sg_beispielstadt_naechstes_spiel
```

Mit Live-Anzeige:

```yaml
type: custom:handball-team-card
title: SG Beispielstadt
next_match_entity: sensor.sg_beispielstadt_naechstes_spiel
live_ticker_entity: sensor.sg_beispielstadt_live_ticker
```

Der Live-Bereich wird nur bei Sensorzustand **`Live`** und gefülltem `live_matches` gerendert. Fehlende Ergebnisse erscheinen als Platzhalter. Das Erkennungsfenster ist keine Bestätigung, dass der Anbieter tatsächlich Live-Ereignisse liefert.

### Bekannte Rang-Inkompatibilität

Die Karte prüft `attributes.position`. Der reguläre Team-Tabellenplatzsensor stellt den Rang derzeit **nur als Zustand** bereit; dieses Attribut fehlt. Daher ist folgende Zuweisung syntaktisch zulässig, zeigt mit dem aktuellen Sensor aber **keinen Tabellenabschnitt**:

```yaml
type: custom:handball-team-card
title: SG Beispielstadt
next_match_entity: sensor.sg_beispielstadt_naechstes_spiel
table_position_entity: sensor.sg_beispielstadt_tabellenplatz
```

Wenn zusätzlich ein Turnier eingerichtet wurde, liefert dessen **zum gewünschten Team gehörender Positionssensor** `position` tatsächlich als Attribut:

```yaml
type: custom:handball-team-card
title: SG Beispielstadt
next_match_entity: sensor.sg_beispielstadt_naechstes_spiel
live_ticker_entity: sensor.sg_beispielstadt_live_ticker
table_position_entity: sensor.beispielliga_platz_3
```

`platz_3` ist nur ein fiktives Beispiel. Den Sensor anhand von `team_name`/`team_id` prüfen: Der anfängliche Positionsname ist nicht zwingend dauerhaft ein Rang-Slot. Keine fremde Mannschaft allein wegen des passenden aktuellen Rangnamens auswählen.

**Achtung Demo:** Wenn keine der konfigurierten Entitäten existiert, kann die Teamkarte eingebaute Musterdaten anzeigen. Eine hübsche Vorschau beweist deshalb nicht, dass die Einrichtung funktioniert. Entitäten immer unter den HA-Zuständen prüfen.

## `handball-tournament-table-card`

Diese Karte benötigt den **Tabelle-Sensor eines Turniereintrags**, nicht den Tabellenplatzsensor eines Teams.

```yaml
type: custom:handball-tournament-table-card
entity: sensor.beispielliga_tabelle
title: Beispielliga
highlight_team: SG Beispielstadt
show_logo: true
```

| Schlüssel | Vorgabe/Bedeutung |
|---|---|
| `entity` | Pflicht; Daten aus `attributes.table` |
| `title` | Optional; sonst `tournament_name` oder „Tabelle“ |
| `highlight_team` | Optional; vollständiger Teamname, verglichen ohne äußere Leerzeichen und unabhängig von Groß-/Kleinschreibung |
| `show_logo` | Standard `true`; nur `false` schaltet Logos ab |
| `debug` | Optional `true`; technische Zähler für Instanz, `hass`-Updates und DOM-Schreibvorgänge; keine API-Gesundheitsanzeige |

Angezeigt werden Rang, Mannschaft, Spiele, Siege, Unentschieden, Niederlagen, Tore, Tordifferenz und Punkte. Auf-/Abstiegsmarkierungen erscheinen nur, wenn entsprechende Daten vorhanden sind; die aktuelle API-Normalisierung setzt sie nicht verlässlich. Beim speziellen Stub-Entitätsnamen der Kartenvorschau gibt es ebenfalls Musterdaten.

## `handball-schedule-card`

Diese Karte benötigt den **Spielplan-Sensor eines Turniereintrags**. Der gleichnamige Kalender oder ein Team-„Alle Spiele“-Sensor ist keine passende Datenquelle.

```yaml
type: custom:handball-schedule-card
entity: sensor.beispielliga_spielplan
table_entity: sensor.beispielliga_tabelle
title: Beispielliga
highlight_team: SG Beispielstadt
```

| Schlüssel | Bedeutung |
|---|---|
| `entity` | Pflicht; Sensor mit `matchdays` und `current_matchday_index` |
| `table_entity` | Optional; Tabellen-Sensor derselben Staffel, ergänzt Logos über Teamnamen |
| `title` | Optional; wird dem Spieltagsnamen vorangestellt |
| `highlight_team` | Optional; vollständiger Teamname, ohne Beachtung von Groß-/Kleinschreibung und äußeren Leerzeichen |

Die Pfeile blättern durch die gelieferten Spieltage; **Aktuell** folgt wieder dem vom Sensor bestimmten Spieltag. Mit zwei numerischen Torwerten zeigt die Karte ein Ergebnis, sonst die Anwurfzeit. Die Halle steht als Tooltip an der Partie. Die Datumsdarstellung erfolgt im Browser mit deutschem Format und dessen Zeitzone.

Falls nicht jede Partie eine erkannte Rundennummer enthält, gruppiert der Sensor nach **ISO-Kalenderwochen in UTC**. Ein Nachholspiel steht dann bei seinem tatsächlichen Termin, nicht zwingend beim ursprünglichen Spieltag. „Aktuell“ nutzt den mittleren angesetzten Termin der Gruppe plus zwei Stunden; es ist kein offizieller Ligastatus.

Die Team- und Tabellenkarte besitzen einen eigenen Konfigurationseditor. Die Spielplankarte hat derzeit keinen solchen Editor; die manuelle YAML-Konfiguration ist der verlässliche dokumentierte Weg.

## Ohne Custom Cards

Vereinsübersicht oder einzelne Sensoren lassen sich auch mit einer eingebauten Entitätenkarte anzeigen:

```yaml
type: entities
entities:
  - entity: sensor.sg_beispielstadt_verein
  - entity: sensor.sg_beispielstadt_naechstes_spiel
  - entity: binary_sensor.sg_beispielstadt_live
```

Das ist zugleich eine einfache Gegenprobe: Sind schon die Zustände dort leer oder nicht verfügbar, ist das kein reines Darstellungsproblem der JavaScript-Karten.
