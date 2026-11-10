# Entitäten, Attribute und Kalender

[Zur Hauptanleitung](../README.md)

Quelle: `sensor.py`, `binary_sensor.py`, `calendar.py`, die Klassen unter `sensors`/`calendars` und der Coordinator. Entitäts-IDs werden durch Home Assistant vergeben und können von Beispielen abweichen. Die folgenden Namen beschreiben Funktionen, nicht garantierte ID-Suffixe.

## Team-Entitäten

Ein Einzelteam erhält die folgenden neun Sensoren, einen Binärsensor und einen Kalender. Ein Vereinseintrag erzeugt dieselben Entitäten für **jedes ausgewählte Team**.

| Sensor | Zustand | Wichtige Attribute |
|---|---|---|
| **Alle Spiele** | Hinweis auf den nächsten Gegner oder „Keine Spiele verfügbar“/„Kein nächstes Spiel“ | `next_match`, `last_match`, `total_matches`, `upcoming_matches`, `recent_matches`; eigenes Teamlogo als `entity_picture` |
| **Heimspiel** | `vs Gegner` oder „Kein Heimspiel geplant“ | `opponent`, `home_team`, `away_team`, `location`, `startsAt`, `starts_at_local`, `starts_at_formatted`, `match_date`; Gegnerlogo |
| **Auswärtsspiel** | `@ Gegner` oder „Kein Auswärtsspiel geplant“ | wie Heimspiel, zusätzlich `competition` und `match_id`; Gegnerlogo |
| **Nächstes Spiel** | Gegnername oder „Kein nächstes Spiel“ | `match_date`, `match_time`, `home_team`, `away_team`, `field`, `starts_at` |
| **Statistik** | Zusammenfassung von Siegen, Unentschieden und Niederlagen oder „Noch keine beendeten Spiele“ | Zähler, Tore, Prozente und Mittelwerte; siehe unten |
| **Tabellenplatz** | Rang als Zahl, bei fehlender Tabelle kein Wert | `tournament_id`, `team_name`, `points`, `games_played`, `wins`, `draws`, `losses`, `goals_scored`, `goals_conceded`, `goal_difference` |
| **Live-Ticker** | exakt `Live` oder `Kein Live-Spiel` | bei laufendem Spiel `live_matches`, `total_live_matches` |
| **Live Events** | Ereignisanzahl als Text oder „Keine Live-Spiele“ | `game_id`, `events`, `total_events`, `last_update`, sofern ein Live-Abruf vorliegt |
| **Health** | `healthy`, `stale`, `error` oder `unknown` entsprechend den berechneten Daten | z. B. `reason`, `total_matches`, `played_matches`, `upcoming_matches`, `fetched_at`, gegebenenfalls `last_updated`; außerdem Laufzeitmessungen |

### Unterschiede der Spielansichten

- **Nächstes Spiel** sucht strikt nach einem Start in der Zukunft. Eine bereits angepfiffene Begegnung ist dort nicht mehr das nächste Spiel.
- **Heimspiel/Auswärtsspiel** halten die erste passende Begegnung bis zwei Stunden nach ihrem Beginn sichtbar. Sie sind keine Gesamtzählung aller Heim- oder Auswärtsspiele.
- **Alle Spiele** enthält unter `upcoming_matches` höchstens fünf künftige Roh-Spielobjekte und unter `recent_matches` höchstens fünf mit `state: Post`. Der Sensor stellt **nicht** den gesamten Spielplan als Attribut bereit.
- `last_match` ist die letzte Begegnung mit Startzeit bis jetzt. Sie muss nicht bereits beendet sein und muss noch kein Ergebnis besitzen.

### Spielobjekte und Zeitformate

Nicht alle Attribute haben dieselbe Form:

- `next_match`/`last_match` bei „Alle Spiele“ und in der Vereinsübersicht: `id`, `home_team`, `away_team`, `opponent`, `is_home`, `starts_at`, `starts_at_formatted`, `starts_at_local`, `field`. `last_match` ergänzt `home_goals`, `away_goals`, `state`.
- `home_team`, `away_team`, `opponent` in diesen Objekten sind Objekte mit `id`, `name`, `logo`. Auch der **Nächste-Spiel-Sensor** verwendet für `home_team` und `away_team` solche Objekte.
- Beim **Heim-/Auswärtsspiel-Sensor** sind `home_team`, `away_team` und `opponent` dagegen einfache Namen als Text. Seine Halle heißt `location`, nicht `field`.
- Die Roh-Spielobjekte in `upcoming_matches`, `recent_matches` und `live_matches` verwenden unter anderem `startsAt`, `homeTeam`, `awayTeam`, `homeGoals`, `awayGoals`, `tournament`, `isHomeMatch` und `isAway`.

`startsAt`, `starts_at`, `next_match_at` sowie numerische Spieltags-Zeitwerte sind **Unix-Epoch-Millisekunden**, keine Sekunden. Formatierte Team-Zeitangaben mit `formatted` beziehungsweise `match_date` werden derzeit als **UTC** mit UTC-Zusatz ausgegeben. Die mit `local` beziehungsweise `match_time` bezeichneten Zeichenketten verwenden die lokale Laufzeit-Zeitzone und tragen keinen Offset. Sie sind daher kein sicherer Ersatz für einen zeitzonenbewussten Zeitstempel. Die Karten formatieren nicht alle Daten auf dieselbe Weise; die Spielplankarte nutzt Browserzeit.

### Statistik

`total_matches`, `finished_matches`, `upcoming_matches`, `wins`, `draws`, `losses`, `goals_scored`, `goals_conceded`, `goal_difference`; bei vorhandenen abgeschlossenen Spielen zusätzlich `win_percentage`, `draw_percentage`, `loss_percentage`, `avg_goals_scored`, `avg_goals_conceded`.

Als beendet zählt der Code entweder `state == Post` **oder** zwei vorhandene Torwerte. Das kann bei laufenden Partien mit Zwischenstand zu einer anderen Einordnung als in der offiziellen Tabelle führen. Die Statistik ist eine Berechnung aus dem abgerufenen Spielplan, keine verbindliche Tabellenwertung. Im Sonderfall ohne beendete Spiele wird `total_matches` derzeit mit `0` ausgegeben, auch wenn künftige Spiele vorhanden sind.

### Health und Verfügbarkeit

- `unknown` mit `reason: no_matches_available`: erfolgreich betrachteter leerer Spielplan.
- `unknown` mit `reason: schedule_unavailable`: ein als nicht verfügbar markierter Spielplan; echte HTTP-Fehler werden im aktuellen Pfad normalerweise bereits als Updatefehler weitergereicht.
- `stale`: nur wenn die Quelle ein auswertbares `lastUpdated` liefert und dieses älter als zwei Stunden ist. Die neue API liefert dies üblicherweise nicht; alte Spieltermine allein bedeuten nicht „stale“.
- `healthy` bedeutet, dass die lokalen Prüfungen bestanden wurden, **nicht**, dass die Daten vollständig oder live sind.
- `performance` enthält die Team-Aktualisierungsdauer; `coordinator_performance` enthält Zeitstempel, Phasenlaufzeiten und gegebenenfalls die drei langsamsten Teamabfragen. Angaben in Millisekunden messen den lokalen Ablauf inklusive Cacheeffekten.

`degraded` und `unhealthy` stehen zwar in den Konstanten, werden durch die hier dokumentierte Health-Berechnung nicht regulär erzeugt. Bei gescheitertem Coordinator-Update können Coordinator-Sensoren stattdessen **`unavailable`** sein. Ein früherer gespeicherter Health-Wert ist dann kein Beleg für einen erfolgreichen neuen Abruf.

### Live-Binärsensor

**Live** ist `on`, wenn eine Partie zeitlich zwischen geplantem Start und zwei Stunden danach liegt. Attribute: `team_id`, `matches_count`. Der Binärsensor prüft keine bestätigte Live-Meldung und schließt verschobene oder bereits beendete Spiele nicht anhand des Status aus. Er ist deshalb nur bedingt als Automationsauslöser geeignet.

Der Live-Events-Sensor nutzt die **erste** als laufend erkannte Partie. Keine Ereignisse kann „kein laufendes Spiel“, „keine gelieferten Ereignisse“ oder eine Datenstörung bedeuten; Zustand und Protokoll zusammen betrachten.

## Vereinsübersicht

Zusätzlich zu den ausgewählten Mannschaften entsteht **Verein**:

- Zustand: Anzahl konfigurierter Mannschaften, keine Live-Anzahl aller Vereinsmannschaften.
- Attribute: `club_id`, `club_name`, `team_count`, `teams`, `next_matches`, `team_cards`.
- `teams`: je Mannschaft `team_id`, `team_name`, `team_logo`, `next_match`, `last_match`, `table_position`, `is_live`.
- `next_matches`: nach Start sortierte nächste Begegnungen mit `team_id`, `team_name`, `team_logo`, `match`.
- `team_cards`: flache Dashboard-Ansicht mit `team_id`, `friendly_name`, `entity_picture`, `next_match`, `last_match`, `home_team`, `away_team`, `field`, `starts_at`, `starts_at_local`, `table_position`, `is_live`.

Die Übersicht ist nach nächstem Spiel und Teamnamen sortiert. Ein fester Listenindex ist daher keine dauerhafte Teamidentität. Das Vereinsbild wird aus einem vorhandenen Teamlogo abgeleitet. Es ist kein eigener Logo-Upload.

## Turnier-/Staffel-Entitäten

### Tabelle

Zustand: textliche Führung oder „Keine Tabellendaten verfügbar“.

Attribute: `tournament_name`, `tournament_acronym`, `organization`, `total_teams`, `table`, `leader`, `last_place`. Bei leerer Tabelle können Name und weitere Metadaten auf ID/leere Zeichenketten zurückfallen.

Jede `table`-Zeile enthält:

`position`, `team_id`, `team_name`, `team_acronym`, `team_logo`, `points`, `games_played`, `wins`, `draws`, `losses`, `goals_scored`, `goals_conceded`, `goal_difference`, `promoted`, `relegated`, `is_last_place`.

Der API-Client wählt aus einer gelieferten Tabellenhistorie die Zeilen mit der höchsten vorhandenen Rundennummer. Das ist keine frei wählbare historische Tabelle. Auf-/Abstieg und Kürzel können fehlen; `promoted`/`relegated` werden bei der neuen API-Normalisierung derzeit auf `None` gesetzt.

### Einzelne Positionssensoren

Beim Plattformaufbau wird für jede vorhandene Tabellenzeile ein Sensor **Platz N** angelegt. Zustand ist der aktuelle Rang als Zahl, **nicht der Mannschaftsname**.

Attribute: `team_id`, `team_name`, `team_acronym`, `position`, `points`, `games_played`, `wins`, `draws`, `losses`, `goals_scored`, `goals_conceded`, `goal_difference`, `promoted`, `relegated`, `win_percentage`, `draw_percentage`, `loss_percentage`, `avg_goals_scored`, `avg_goals_conceded`, `points_per_game`, `is_leader`, `is_last_place`, `is_promotion_zone`, `is_relegation_zone`; bei vorhandenen Daten Teamlogo als Bild.

**Grenzen:** Name und Unique ID basieren auf dem anfänglichen Rang, die spätere Datenauflösung versucht zuerst die anfängliche Team-ID. Deshalb ist „Platz N“ kein garantierter, dauerhaft derselbe Tabellenplatz. Neue Zeilen führen während des laufenden Setups nicht automatisch zum Nachanlegen weiterer Positionsentitäten; gegebenenfalls Eintrag neu laden. `points_per_game` hat derzeit eine auffällige Berechnungsformel und sollte nicht als belastbare sportliche Kennzahl verwendet werden.

### Spielplan-Sensor

Zustand: Anzahl der Begegnungen mit Startzeit in der Zukunft.

| Attribut | Bedeutung |
|---|---|
| `total_matches`, `played_matches`, `remaining_matches` | Zählung nach Startzeit; „played“ bedeutet hier angepfiffen/vergangen, nicht bestätigt beendet |
| `next_match_at` | Nächster Spielbeginn als Epoch-Millisekunden oder `None` |
| `current_matchday_index` | Nullbasierter Index der automatisch bestimmten aktuellen Gruppe |
| `matchday_mode` | `round` oder `calendar_week` |
| `matchdays` | Vollständige gruppierte Liste aus den geladenen Spielen |
| `upcoming_matches` | Höchstens 21 kommende Begegnungen |
| `recent_results` | Höchstens 21 Begegnungen mit vergangenem Start, neueste zuerst; Tore können fehlen |

Eine Spieltagsgruppe enthält `label`, `round`, `start`, `end`, `matches`. Eine kompakte Begegnung enthält `id`, `starts_at`, `home`, `away`, `field`, bei Ergebnisansichten zusätzlich `home_goals` und `away_goals`.

Wenn alle datierten Spiele eine ganzzahlige Rundennummer besitzen, wird danach gruppiert; andernfalls nach ISO-Kalenderwochen in UTC. Der aktuelle Spieltag richtet sich nach dem mittleren Starttermin plus zwei Stunden. Die großen Attribute `matchdays`, `upcoming_matches` und `recent_results` sind als nicht aufzuzeichnende Recorder-Attribute markiert. Historische Datenbankstände dieser Listen sollten daher nicht als Archiv des Spielplans vorausgesetzt werden.

### Verbleibende Teams

Wird nur angelegt, wenn beim Setup keine Tabelle erkannt wird. Zustand: Anzahl der heuristisch verbleibenden Teams. Attribute: `tournament_name`, `total_matches`, `remaining_teams_count`, `remaining_teams`; Listenelemente enthalten `team_id`, `team_name`, `team_logo`.

Der Code leitet Ausscheiden aus ungleichen numerischen Torwerten ab und berücksichtigt Teams mit zukünftigen Spielen weiter. Gruppenphasen, Hin-/Rückspiele, Zwischenstände, nicht vollständig geladene Runden oder Sonderwertungen können das Ergebnis verfälschen. Der Teilnehmer-Fallback ohne Tabelle verwendet noch die alte API; ein vollständiger Pokalbaum ist nicht garantiert.

## Kalender

Je Team ein Kalender **Spielplan**, pro Turnier ein eigener Kalender **Spielplan**. Ein Verein besitzt keinen zusätzlichen Sammelkalender; er bündelt mehrere Teamkalender.

- Termine sind aus dem Coordinator-Spielplan abgeleitet, nicht manuell editierbar.
- Titel: `Heimteam vs Auswärtsteam`, im Zeitfenster gegebenenfalls mit `(LIVE)`.
- Start aus dem Spielzeitstempel, Ende **fest zwei Stunden später**; keine verbindliche tatsächliche Spieldauer.
- Ort und Beschreibung enthalten die Halle, soweit vorhanden.
- Der aktuelle Termin ist eine laufende Begegnung, sonst die nächste. Ohne künftige oder laufende Partie kann dieser Teil leer sein, obwohl ältere Termine im Kalender vorhanden sind.
- Bereichsabfragen wählen derzeit Spiele nach **Start innerhalb des angefragten Bereichs** aus. Ein schon vor Bereichsbeginn gestartetes, noch laufendes Spiel wird dadurch nicht zwangsläufig mitgeliefert.
- Kalender nutzen dieselben gecachten Daten und haben keinen unabhängigen schnelleren API-Abruf.

## Verwendung in Dashboards und Automationen

Keinen Zustandstext als einzige Verfügbarkeitsprüfung verwenden. Vor Berechnungen fehlende Attribute sowie `unknown`/`unavailable` berücksichtigen. Konkrete Kartenbeispiele stehen in der [Kartenanleitung](dashboard-karten.md). Keine aus diesen Entitäten abgeleitete Anzeige als verbindliche Termin- oder Ergebnisquelle behandeln.
