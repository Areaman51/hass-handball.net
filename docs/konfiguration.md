# Konfiguration und Saisonwechsel

[Zur Hauptanleitung](../README.md)

Quelle: `config_flow.py`, `options_flow.py`, `const.py` und die deutschen Übersetzungen unter `custom_components/handballnet`. Die Schlüssel dienen der Erklärung des Codes, **nicht als YAML-Konfiguration für `configuration.yaml`**.

## Startdialog

| Schlüssel | Bedeutung | Vorgabe |
|---|---|---|
| `entity_type` | Auswahl `team` oder `tournament` | Auswahl erforderlich |
| `update_interval` | Normaler Coordinator-Takt in Sekunden | `3600` |
| `update_interval_live` | Takt bei als laufend erkanntem Teamspiel in Sekunden | `15` |

`club` ist eine intern gespeicherte Eintragsart, aber keine dritte Auswahl im Startdialog. Die Intervallfelder prüfen derzeit auf ganze Zahlen, ohne positive Mindestwerte zu erzwingen. Nur sinnvolle positive Werte verwenden und bei Drosselung vergrößern.

## Team: manuelle Eingabe

`team_input_mode: manual` erwartet `team_id`. Nur die aktuelle ID eingeben, keine vollständige URL. Die Integration prüft `teams/{team_id}` und übernimmt den Namen. Historische Legacy-IDs sind nicht automatisch konvertierbar. Kein eigener API-Schlüssel und kein Konto sind Teil dieses Flows.

## Team: Vereinssuche und Mehrfachauswahl

1. `team_input_mode: club_search` wählen.
2. `club_query` mit mindestens zwei Zeichen ausfüllen.
3. Unter `club_id` einen gefundenen Verein auswählen.
4. Unter `selected_team_id` eine oder mehrere Mannschaften markieren. Trotz des Singulars ist dies hier eine **Mehrfachauswahl**.

Es entsteht ein `entity_type: club`-Eintrag mit `club_id`, `club_name` und `team_mapping` (Zuordnung konfigurierter Teamname → Team-ID). Falls geliefert, wird `federation_id` zur Teamsuche gespeichert. Die angezeigten Mannschaften werden um Varianten, Altersklasse/Geschlecht und nach Möglichkeit den Ligennamen ergänzt. Die zusätzliche Ligenabfrage ist Best Effort.

Dies gilt auch bei nur einer markierten Mannschaft. Die Vereinsübersicht umfasst nur die **ausgewählten** Teams, nicht automatisch alle Vereinsmannschaften. Neu hinzukommende Teams werden nicht selbstständig ausgewählt.

Team-Duplikate werden sowohl gegenüber Einzelteam-Einträgen als auch gegenüber Mannschaften in Vereinseinträgen geprüft. Für ein schon erfasstes Team keinen zusätzlichen Eintrag erzwingen.

## Turnier: zwei Suchwege

### Über Verein und Team

`tournament_input_mode: club_search` → `club_query` → `club_id` → **einzelne** `selected_team_id`.

Der Flow ruft Spiele des Teams ab und verwendet die Phase des **ersten zurückgegebenen Spiels**. Das ist keine garantierte Auswahl der neuesten Saison oder des gewünschten Wettbewerbs. Ohne veröffentlichten Spielplan kann keine Phase ermittelt werden. Bei mehreren Wettbewerben besser die Wettbewerbssuche wählen.

### Über Wettbewerb und Staffel

`tournament_input_mode: competition_search` → `competition_query` mit mindestens zwei Zeichen → `selected_competition_id` → `selected_phase_id`.

Intern werden `entity_type: tournament`, `tournament_id` und `tournament_name` gespeichert. `tournament_id` entspricht der ausgewählten **Phase/Staffel**. Die Suche kann Namen, Altersklassen, Geschlecht und Verband anzeigen. Es gibt keinen manuell auszufüllenden Turnier-ID-Schritt. Dieselbe Phase wird bei doppelter Einrichtung abgewiesen.

## Optionen

Der native Optionsdialog trennt **Abfrageintervalle** und **Logos verwalten**. Die Intervalle `update_interval` und `update_interval_live` verlangen positive ganze Sekundenwerte. Gespeicherte Optionen gehen beim nächsten Erstellen des Coordinators den ursprünglichen Einrichtungswerten vor; andere vorhandene Optionen bleiben beim Bearbeiten erhalten.

Die zentrale Logo-Verwaltung gilt für bekannte oder manuell benannte Mannschaften über alle Handball.net-Einträge hinweg. Sie unterstützt Bildadresse, geprüften Upload und bestätigtes Entfernen der zentralen Ausnahme. Dabei werden keine Abfrageintervalle geändert und keine externen Daten neu geladen. Siehe [Vereinslogos verwalten](vereinslogos.md).

Der Code registriert derzeit keinen eigenen Options-Update-Listener zum automatischen Neuaufbau des Coordinators. Nach **Intervalländerungen** den Eintrag daher bei Bedarf über Home Assistant neu laden. Das ist nicht nötig für Logoänderungen: Die relevanten Sensoren abonnieren deren gemeinsamen Manager und aktualisieren ihre Logoattribute unmittelbar. Der Dienst `handballnet.reload_config` ist zwar deklariert, hat aber aktuell eine Signatur-Inkonsistenz; siehe [Fehlersuche](fehlersuche.md#aktionen).

## Neukonfiguration

Nur für Einzelteam- und Vereinseinträge implementiert; Turniere werden mit `invalid_reconfigure_entry` abgewiesen.

- **Einzelteam manuell:** aktuelle/neue `team_id` prüfen und im vorhandenen Eintrag speichern. Der Eintrag wird neu geladen.
- **Verein:** Wenn möglich lädt der Flow sofort die aktuelle Mannschaftsliste des gespeicherten Vereins und schlägt weiterhin gültige Team-IDs vor. Auswahl ändern und speichern.
- **Vereinssuche im Reconfigure-Flow:** Verein auswählen und Teams markieren. Dieser Weg speichert einen **Vereinseintrag**, auch wenn er von einem bisherigen Einzelteam-Eintrag aus gestartet wurde. Er ist keine Zusage, die alte Eintragsart oder sämtliche Entitäts-IDs zu erhalten.

Die gespeicherte Mannschaftsauswahl wird ersetzt, nicht nur ergänzt. Beim Entfernen/Umbenennen von Teams können bisherige Geräte bereinigt werden. Vorher Backup erstellen und danach alle Verweise prüfen.

## Saisonwechsel

Es gibt keinen Saisonparameter, keinen Saison-Assistenten und keine garantierte automatische Migration von IDs.

1. Vollständiges Backup erstellen und bisherige IDs/Verweise privat festhalten.
2. Auf handball.net prüfen, welche Mannschaft und Staffel zur gewünschten Saison gehören und ob schon Spiele vorliegen.
3. Vorhandene Team-/Vereinseinträge über **Neu konfigurieren** aktualisieren, statt die Integration zu löschen. Bei Vereinseinträgen gültige Mannschaften erneut auswählen.
4. Für eine neue Turnierphase einen neuen Turniereintrag über Wettbewerb/Staffel einrichten. Den alten Eintrag zunächst behalten; erst Daten und Verweise prüfen. Es gibt keine garantierte Übernahme alter Turnier-Entitäts-IDs.
5. Dashboards und Automationen auf die tatsächlich vorhandenen Entitäten abstimmen. Bei Änderungen an IDs oder Namen alle Verbraucher prüfen.

Unique IDs von Team-Entitäten enthalten die Eintrags-ID und einen aus dem konfigurierten Namen abgeleiteten Anteil. Eine bloße Zusage „Domain gleich, deshalb bleiben alle Entitäten immer gleich“ wäre falsch. Der Dateiumstieg ohne Konfigurationsänderung und eine fachliche Neukonfiguration sind unterschiedliche Vorgänge.
