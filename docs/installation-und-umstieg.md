# Installation, Umstieg und Rollback

[Zur Hauptanleitung](../README.md)

## Stand und Entscheidung

Dokumentiert ist die reguläre Version **0.1.0**, Release-Tag **v0.1.0** im Repository **Areaman51/hass-handball.net**. `main` bleibt ein beweglicher Entwicklungsbranch. Der Release umfasst nicht automatisch eine vollständige Funktions-/Migrations-/Versionsmatrix; eine gesicherte Testinstanz ist für erste Versuche vorzuziehen.

Die Domain bleibt **`handballnet`**. Original und Fork schreiben in denselben Komponentenordner und bedienen dieselben Konfigurationseinträge. Sie sind **Alternativen, keine parallel installierbaren Integrationen**. Ein anderer Ordnername macht daraus keine zweite unabhängige Integration.

**Empfohlen ist die automatische Installation als benutzerdefiniertes Repository.** Eine Standardkatalog-Aufnahme ist nicht erforderlich. Kein ZIP-Download, Dateikopieren, separates Kartenrepository oder manueller Ressourcen-Eintrag gehört zu diesem normalen Weg. Der kontrollierte Wechsel einer bestehenden Originalquelle ist davon getrennt und wurde **noch nicht real getestet**.

## Automatische Neuinstallation als benutzerdefiniertes Repository

Für Home Assistant ab 2026.11 ist der Marketplace bereits eingebaut; HACS muss nicht separat installiert werden. Vollständige Schritte und direkter Button: [Hauptanleitung](../README.md#empfohlen-benutzerdefiniertes-repository--ohne-dateikopieren).

1. **Einstellungen → Marketplace** öffnen und bei Bedarf den Hinweis für Community-Inhalte bestätigen.
2. **Aus Link hinzufügen** wählen und `https://github.com/Areaman51/hass-handball.net` angeben; Kategorie **Integration**, falls abgefragt. Alternativ den My-Home-Assistant-Button in der Hauptanleitung benutzen.
3. Die angebotene GitHub-Verbindung über die Oberfläche herstellen, falls noch nicht vorhanden. Kein persönliches handball.net-Passwort und kein Token in einer YAML-Datei sind dafür nötig.
4. Quelle hinzufügen und auf der Repositoryseite **Installieren** wählen; die reguläre Version **v0.1.0** verwenden. Der Marketplace lädt den Inhalt selbst und legt die Integration an der richtigen Stelle ab.
5. Einen gegebenenfalls angeforderten Home-Assistant-Neustart ausführen; nach Integrationsupdates neu starten und den Client neu laden.
6. Die Integration unter **Einstellungen → Geräte & Dienste** einrichten. Gewünschte Dashboardkarten mit den tatsächlichen Entitäten konfigurieren. Die mitgelieferten JS-Karten werden vom Backend automatisch eingebunden; keine zusätzlichen Kartendateien oder Ressourcen installieren.

Mit **v0.1.0** wird der festgelegte Release-Tag statt des jeweils neuesten Main-Commits installiert. `zip_release: false` bleibt erhalten: der automatische Installer nutzt die Quelldateien dieses Tags, nicht das zusätzlich angehängte ZIP. [Offizielle Bedienung](https://www.home-assistant.io/integrations/marketplace/) und [Versionsauswahl](https://contributors.home-assistant.io/marketplace/guides/releases/) erklären die Plattformdetails. Praktische Testgrenzen stehen getrennt im [Prüfstand](pruefstand.md); direkte native Installeraufrufe sind keine behauptete vollständige Browserabnahme.

**Bei einer schon vorhandenen Originalinstallation hier stoppen und zuerst die folgenden Wechselhinweise lesen.** Nicht auf Verdacht die HA-Integration, deren Einträge oder Geräte löschen.

## Vor jedem Wechsel: Wiederherstellung vorbereiten

1. **Vollständiges Home-Assistant-Backup vor dem Eingriff erstellen.** Das Backup muss Konfiguration, Config-Entries und Geräte-/Entitätsregistrierungen enthalten. Datenbank und externe Daten bei Bedarf gesondert berücksichtigen. Nicht annehmen, dass eine reine Git-Sicherung der YAML-Dateien ausreicht.
2. Backup außerhalb der laufenden Instanz sichern. Prüfen, ob Archiv und erforderlicher Wiederherstellungsschlüssel beziehungsweise Notfallkit verfügbar sind. Backups können Zugangsdaten enthalten: nicht öffentlich hochladen.
3. Bisherigen vollständigen Ordner `custom_components/handballnet` separat **außerhalb von `custom_components`** sichern. Installierte Version, Bezugsquelle und nach Möglichkeit Commit notieren. Ein alter Download-Link allein ist kein gesicherter Rückweg.
4. Bestehende Einträge, Entitäts-IDs sowie verwendende Dashboards, Automationen und Skripte dokumentieren, ohne diese Informationen öffentlich zu teilen.
5. Klären, ob HACS den Komponentenordner verwaltet. Automatische oder manuelle Updates dürfen den neuen Source-Stand nicht ungeplant wieder überschreiben.

**Nicht tun:** Integration oder Config-Entries in „Geräte & Dienste“ löschen; `.storage` bearbeiten; Geräte vorsorglich entfernen; Original und Fork gleichzeitig installieren. Eine Sicherung des Komponentenordners allein stellt gelöschte Registrierungen nicht wieder her.

## Neue manuelle Installation

**Nur Ausweichweg für Entwicklung oder eine nicht verfügbare Automatikroute.** Für eine normale Neuinstallation den benutzerdefinierten Repositoryweg oben verwenden.

1. Im Fork den Tag **v0.1.0** auswählen und dessen Source-Archiv über GitHub herunterladen. Den konkreten Tag und Commit festhalten; `main` kann sich ändern.
2. Entpacken. Im Archiv den Ordner `custom_components/handballnet` suchen.
3. Nur diesen Ordner samt `www`, Übersetzungen, Sensoren, Kalendern und übrigen enthaltenen Dateien in das Home-Assistant-Konfigurationsverzeichnis unter `custom_components/handballnet` übernehmen.
4. Prüfen: Unter `custom_components/handballnet` muss direkt `manifest.json` liegen, nicht erst in einem weiteren Unterordner. Keine Dateien aus dem Entwicklungsordner `config` übernehmen.
5. Home Assistant neu starten und die Integration über die Oberfläche hinzufügen; siehe [Neueinrichtung](../README.md#neueinrichtung).

Ein Source-Archiv des Repositories enthält den Unterordner `custom_components/handballnet`. Das zusätzliche Release-Asset `handballnet.zip` enthält dagegen direkt die Dateien der Integration. Diese beiden Archivlayouts nicht verwechseln. Für die normale automatische Route ist kein manuelles Archiv erforderlich.

## Vorhandene Installation manuell ersetzen

1. Die Backup-Checkliste vollständig abarbeiten.
2. Fork-Source bereitstellen und den zu installierenden Commit notieren.
3. **Home Assistant stoppen**, bevor Dateien ausgetauscht werden.
4. Bisherigen Komponentenordner aus dem aktiven `custom_components`-Verzeichnis entfernen, nachdem seine separate Sicherung überprüft wurde. Den Fork-Ordner vollständig an seine Stelle kopieren. Nicht über einen unbekannten Altbestand hinweg einzelne Dateien mischen; sonst bleiben entfernte Module oder alter Bytecode zurück.
5. Genau eine aktive Kopie unter `custom_components/handballnet` sicherstellen. Domain und vorhandene HA-Konfigurationseinträge unverändert lassen.
6. Home Assistant starten. **Nicht erneut hinzufügen**, wenn die vorhandenen Einträge schon da sind.
7. Die Nachkontrolle unten durchführen. Einen von HACS verwalteten Installationsstand nicht irrtümlich als dauerhaft unabhängig von HACS betrachten; ein späteres HACS-Update kann ihn wieder ersetzen.

## Marketplace-/HACS-Route: Quellenwechsel weiterhin ungetestet

Ab Home Assistant 2026.11 ist der Marketplace eingebaut. Der Fork wird als benutzerdefiniertes Repository über den [My-Link in der Hauptanleitung](../README.md#empfohlen-benutzerdefiniertes-repository--ohne-dateikopieren) angeboten. Dafür ist eine GitHub-Verbindung erforderlich; eine benutzerdefinierte Quelle ist nicht dasselbe wie eine Aufnahme in den gemeinsamen Katalog. Für Neuinstallationen gilt die automatische Route oben; dieser Abschnitt betrifft den getrennten Quellenwechsel.

Repository-Adresse: `https://github.com/Areaman51/hass-handball.net`, Kategorie **Integration**, reguläre Version **v0.1.0**. `zip_release: false` setzt kein Release-Asset voraus. Ein automatischer Neuinstallationsnachweis ist keine praktische Migrationsabnahme; die manuelle Source-Route bleibt ausdrücklich ein Ausweichweg.

Bei einem bereits über Marketplace/HACS verwalteten Original kann der bestehende Besitzer derselben Domain `handballnet` eine zweite Quelle blockieren. Deshalb:

- Nicht beide Quellen parallel installieren.
- Die Repository-Verwaltung und die Home-Assistant-Konfigurationseinträge auseinanderhalten. Vor jeder angebotenen Entfernung genau prüfen, was betroffen wäre.
- Keine Löschaktion an der HA-Integration ausführen, um den Fork auswählbar zu machen.
- Nur fortfahren, wenn ein verständlicher Quellenwechsel ohne Löschen der HA-Einträge möglich und der Rückweg gesichert ist.
- Bei unklarer Wirkung abbrechen. Eine manuelle Source-Installation ersetzt nicht die bewusste Klärung der Verwaltungsquelle; spätere Updates dürfen den Stand nicht ungeplant überschreiben.

Diese Hinweise beschreiben Vorsichtsmaßnahmen, **keinen erfolgreich erprobten Marketplace-/HACS-Umstieg**. Ein gezielt geprüfter Backend-/Kartenpilot mit bestehenden Einträgen ist im [Prüfstand](pruefstand.md) davon abgegrenzt.

## Nachkontrolle

- Vorhandene Einträge werden geladen; kein zweiter Satz identischer Teams wurde angelegt.
- Geräte- und Entitäts-IDs mit dem Vorher-Stand vergleichen. Anzeigenamen sind keine Stabilitätsgarantie.
- Mindestens ein Team mit Spielen, Heim-/Auswärtserkennung, nächstem Spiel und Kalender prüfen.
- Turniertabelle und Spielplan prüfen, sofern eingerichtet. Fehlen Daten schon beim Anbieter, ist ein leerer Kalender allein kein Integrationsfehler.
- Protokoll auf Import-, API- und Coordinator-Fehler prüfen; bei Bedarf Diagnosedownload privat prüfen.
- Dashboard im Browser und gegebenenfalls in der Companion-App neu laden; doppelte JS-Ressourcen vermeiden.
- Verwendende Automationen und Skripte kontrollieren, insbesondere Schutz gegen `unknown`/`unavailable`.

## Rollback

### Nur die Komponenten-Dateien zurücksetzen

Wenn keine Einträge oder Registrierungen geändert wurden:

1. Home Assistant stoppen.
2. Fork-Komponentenordner entfernen und den **vollständig gesicherten vorherigen Ordner** unter `custom_components/handballnet` wiederherstellen.
3. Falls geändert, auch die HACS-Verwaltungsquelle kontrolliert auf den vorherigen Stand zurückführen; keine zweite Installation erzeugen.
4. Home Assistant starten, Browsercache bei Bedarf aktualisieren und dieselbe Nachkontrolle wiederholen.

Das setzt nur den Code zurück. Es garantiert nicht, dass eine ältere API-Version noch mit handball.net funktioniert.

### Bei veränderten oder gelöschten Einträgen/Registrierungen

Ein Dateirücktausch stellt gelöschte Config-Entries und Entitätszuordnungen **nicht** wieder her. In diesem Fall kann eine Wiederherstellung aus dem vorher angelegten vollständigen Backup notwendig sein. Dabei gehen alle seit dem Backup entstandenen Änderungen in den wiederhergestellten Bereichen verloren; Home Assistant wird neu gestartet. Vor einer Wiederherstellung den Umfang bewusst wählen und aktuelle, noch benötigte Änderungen sichern. Keine `.storage`-Dateien von Hand zusammenkopieren.

## Historische IDs

Der ursprüngliche Changelog zu v0.0.29 beschreibt einen historischen API-/ID-Wechsel samt damaliger Löschanweisung. Das ist **keine allgemeine Anleitung für diesen Fork-Wechsel**. Hier zuerst vorhandene Einträge erhalten, aktuelle IDs prüfen und die implementierte Neukonfiguration nutzen. Nicht aufgrund einer historischen Notiz vorsorglich löschen.
