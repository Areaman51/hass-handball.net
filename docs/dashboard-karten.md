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
| `logo_overrides` | nein | Eigene Bildadressen je Mannschaft; siehe gemeinsamen Abschnitt unten |

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
| `logo_overrides` | Optional; eigene Bildadressen je Mannschaft, ohne `show_logo` zu übergehen |
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
| `logo_overrides` | Optional; eigene Bildadressen je Mannschaft, auch ohne Tabellen-Sensor |
| `title` | Optional; wird dem Spieltagsnamen vorangestellt |
| `highlight_team` | Optional; vollständiger Teamname, ohne Beachtung von Groß-/Kleinschreibung und äußeren Leerzeichen |

Die Pfeile blättern durch die gelieferten Spieltage; **Aktuell** folgt wieder dem vom Sensor bestimmten Spieltag. Mit zwei numerischen Torwerten zeigt die Karte ein Ergebnis, sonst die Anwurfzeit. Die Halle steht als Tooltip an der Partie. Die Datumsdarstellung erfolgt im Browser mit deutschem Format und dessen Zeitzone.

Falls nicht jede Partie eine erkannte Rundennummer enthält, gruppiert der Sensor nach **ISO-Kalenderwochen in UTC**. Ein Nachholspiel steht dann bei seinem tatsächlichen Termin, nicht zwingend beim ursprünglichen Spieltag. „Aktuell“ nutzt den mittleren angesetzten Termin der Gruppe plus zwei Stunden; es ist kein offizieller Ligastatus.

Die Team- und Tabellenkarte besitzen einen eigenen Konfigurationseditor. Die Spielplankarte hat derzeit keinen solchen Editor; die manuelle YAML-Konfiguration ist der verlässliche dokumentierte Weg.

## Eigene Vereinslogos: `logo_overrides`

Alle drei Karten unterstützen optional dieselbe individuelle Zuordnung **Mannschaftsname → Bildadresse**. Für eine gemeinsame Einstellung über alle Karten hinweg stattdessen die [zentrale Logo-Verwaltung der Integration](vereinslogos.md) verwenden; die folgenden manuellen `logo_overrides` haben als Karten-Ausnahme Vorrang. Die Funktion ist nicht auf bestimmte Vereine oder Wettbewerbe beschränkt. Damit lassen sich beispielsweise bereits beschnittene Vorschaubilder oder JPEGs mit eingebranntem Hintergrund durch eine bessere vorhandene Grafik ersetzen. Die Karte rekonstruiert keine fehlenden Bildteile und entfernt keine Farben aus einem Wappen.

### Schritt für Schritt: ein Logo austauschen

1. **Geeignete Grafik besorgen:** Ein vollständiges, gut lesbares Vereinslogo verwenden, vorzugsweise PNG. Nutzungsrechte beachten. Ein bereits beschnittenes Bild wird durch einen anderen Dateinamen oder CSS nicht wieder vollständig; ein schwarzer JPEG-Hintergrund wird nicht automatisch transparent.
2. **Bild bereitstellen:** Für eine lokale Datei im Home-Assistant-Konfigurationsverzeichnis den Ordner `www/vereinslogos` anlegen und beispielsweise `beispielstadt.png` hineinkopieren, etwa über eine vorhandene Dateiverwaltung oder Samba-Freigabe. Das ist eine Bilddatei, keine Änderung an `configuration.yaml`. Die zugehörige Browseradresse lautet `/local/vereinslogos/beispielstadt.png` – `www` wird in der URL also zu `local`. Alternativ eine direkt erreichbare Bildadresse verwenden, nicht die Adresse einer Webseite mit eingebettetem Bild. Bei HTTPS-Zugriff auf HA ebenfalls HTTPS für externe Bilder bevorzugen.
3. **Mannschaftsnamen prüfen:** Den vollständigen Namen aus der Tabelle beziehungsweise aus `home_team.name`/`away_team.name` des Nächste-Spiel-Sensors übernehmen. Diese Attribute stehen unter den HA-Zuständen. Zusätze wie „2“ oder unterschiedliche Mannschaftsnamen bleiben relevant; Groß-/Kleinschreibung und überzählige Leerzeichen werden dagegen vereinheitlicht.
4. **Karte bearbeiten:** Im Dashboard die betreffende Karte bearbeiten, ihren YAML-/Code-Editor öffnen und den unten gezeigten `logo_overrides`-Block **zusätzlich zu den bisherigen Feldern** eintragen. Den vorhandenen Kartentyp und die eigenen Entitäts-IDs erhalten. Das Beispiel ist kein Ersatz für die vollständige eigene Kartenkonfiguration.
5. **Weitere Karten berücksichtigen:** Soll das Logo auch in Tabelle und Spielplan erscheinen, denselben Zuordnungsblock in deren Karten ergänzen. Die Einstellung ist derzeit **pro Karte**, nicht zentral über den Optionen-Dialog der Integration.
6. **Speichern und prüfen:** Karte speichern und das Dashboard vollständig neu laden. Für eine geänderte Logo-Zuordnung oder eine neue Bilddatei ist kein Core-Neustart nötig; das setzt voraus, dass die unterstützende Kartenversion bereits installiert ist. Die Bildadresse bei Problemen direkt im Browser öffnen und Schreibweise, Dateiendung und Dateipfad kontrollieren. Bei einem gerade erst angelegten `www`-Verzeichnis prüfen, ob die Instanz `/local/` bereits bereitstellt; falls nicht, kann für diese erstmalige Einrichtung ein regulärer, bewusst eingeplanter HA-Neustart erforderlich sein.

Beispiel für eine einzelne Teamkarte:

```yaml
type: custom:handball-team-card
next_match_entity: sensor.sg_beispielstadt_naechstes_spiel
logo_overrides:
  "SG Beispielstadt": /local/vereinslogos/beispielstadt.png
  "TSV Anderer Ort": https://meinverein.example/bilder/wappen.png
```

Die Namen und Adressen sind **Platzhalter**. Die lokale Datei muss tatsächlich unter `www/vereinslogos/beispielstadt.png` innerhalb der HA-Konfiguration liegen; HA stellt sie dann unter `/local/vereinslogos/beispielstadt.png` bereit. Für eine externe Bildadresse die Verfügbarkeit, Nutzungsrechte und mögliche Zugriffsanforderungen prüfen. Eine PNG-Datei ist nicht automatisch transparent.

Denselben `logo_overrides`-Block kann man auch in die Konfiguration von `handball-tournament-table-card` und `handball-schedule-card` aufnehmen. Die Zuordnung gehört zur **jeweiligen Karte**, nicht zu einer globalen HA-Einstellung. Namen so verwenden, wie sie in deren Mannschaftsdaten stehen; Groß-/Kleinschreibung, äußere Leerzeichen und mehrfache Leerzeichen werden beim Vergleich vereinheitlicht. Eine Namensänderung oder ein abweichender Mannschaftszusatz kann eine weitere Zuordnung erfordern; es handelt sich nicht um eine unscharfe Vereinssuche.

- Ohne passende individuelle Zuordnung wird die zentrale Quelle verwendet, sofern vorhanden, sonst das bisherige API-Logo.
- Die Teamkarte berücksichtigt Ersatzlogos im nächsten Spiel und im Live-Bereich, jeweils für Heim und Gast.
- Die Tabellenkarte berücksichtigt sie pro Mannschaftszeile; `show_logo: false` bleibt wirksam.
- Die Spielplankarte kann ein passendes Ersatzlogo auch ohne `table_entity` zeigen. Für nicht zugeordnete Teams kommen die bisherigen Logos weiterhin aus der optionalen Tabelle.
- Zulässig sind HTTP-/HTTPS- und relative Bildadressen. Unsichere Schemes, protokollrelative Adressen, Backslashes und Steuerzeichen werden abgewiesen. Ungültige Bildwerte ersetzen keine gültigen API-Logos.
- Eine gültige Adresse garantiert noch kein abrufbares Bild. Bei einem Ladefehler versucht die Karte das API-Logo und endet bei weiterem Fehlschlag mit einem neutralen leeren Bildplatz statt einer Endlosschleife. Fehlgeschlagene Quellen werden pro Karteninstanz bis zur erneuten Konfiguration beziehungsweise zum Neuladen gemerkt; gewöhnliche HA-Zustandsupdates starten keine dauernden Wiederholungen.
- `logo_overrides` muss eine Zuordnung sein, keine Liste oder einzelne Zeichenkette. Falsche Containerformate führen zu einer verständlichen Konfigurationsfehlermeldung; ungültige einzelne Bildwerte verwenden dagegen den API-Fallback.
- Die bestehenden visuellen Editoren behalten den Block beim Ändern anderer Felder bei; die Logo-Zuordnung selbst wird im YAML-Editor gepflegt.

### Ein bereits verwendetes Bild aktualisieren oder zurücksetzen

- **Bildinhalt austauschen:** Lokale `/local/`-Dateien können von Browsern und Apps länger gecacht werden. Für eine neue Grafik vorzugsweise einen neuen Dateinamen verwenden, etwa `beispielstadt-v2.png`, und die Zuordnung anpassen. Alternativ den Versionsparameter ändern, etwa `/local/vereinslogos/beispielstadt.png?v=2`. Danach die Karte speichern und vollständig neu laden. Eine fehlerhafte Bildquelle wird bis zur erneuten Konfiguration/Neuladung bewusst nicht dauernd erneut versucht.
- **Wieder das API-Logo verwenden:** Den betreffenden Mannschaftseintrag aus `logo_overrides` entfernen und speichern. Gibt es keine weiteren Zuordnungen, kann der gesamte Block entfallen. Danach die Karte neu laden. Ohne diese Karten-Ausnahme gilt zunächst eine vorhandene zentrale Logo-Zuordnung. Fehlt diese zentrale Zuordnung oder ist ihre Bildquelle nicht ladbar, versucht die Karte das API-Bild. Erst wenn auch dieses fehlt oder nicht geladen werden kann, bleibt ein neutraler leerer Bildplatz. Soll tatsächlich das API-Original statt einer zentralen Zuordnung gelten, zusätzlich in der zentralen Logo-Verwaltung die betreffende Mannschaft wählen, **API-Original wiederherstellen** auswählen und das Entfernen bestätigen. Diese zentrale Entfernung gilt **integrationsweit über alle Handball.net-Konfigurationseinträge hinweg und für alle Karten ohne eigene individuelle Ausnahme** für diese Mannschaft, nicht nur für die gerade bearbeitete Karte. Andere individuelle `logo_overrides`-Ausnahmen bleiben unverändert und weiterhin vorrangig.
- **Weiter altes Bild sichtbar:** Im Browser einen Hard-Reload durchführen; in der Companion-App gegebenenfalls den Frontend-Cache zurücksetzen. Keine zweite Kartenressource hinzufügen und keinen Integrationseintrag löschen.

**Zentrale Alternative:** Unter **Einstellungen → Geräte & Dienste → Handball.net → Optionen/Konfigurieren → Logos verwalten** lässt sich dieselbe Mannschaft zentral für alle Karten einstellen und ein geprüftes Bild hochladen. [Bedienung, Grenzen und Datenschutz](vereinslogos.md). Eine vorhandene individuelle `logo_overrides`-Zuordnung der Karte bleibt vorrangig; diesen Eintrag entfernen, wenn stattdessen die zentrale Quelle gelten soll.

Ein weißes Rechteck oder schwarzer Hintergrund, der bereits zur Quelldatei gehört, verschwindet durch `object-fit: contain` nicht. Für einen anderen Hintergrund ist eine geeignete alternative Grafik nötig. Vereinsbilder werden nicht automatisch gesucht oder als Bestandteil dieses MIT-Repositories weiterverteilt.

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
