# Sicherheit und Datenschutz

Diese Integration verwendet die öffentlich erreichbare handball.net-Webschnittstelle. Für die Einrichtung ist kein persönliches handball.net-Passwort vorgesehen. Der vom Webauftritt gelieferte öffentliche Client-Token wird zur Laufzeit abgerufen und nicht fest im Quellcode hinterlegt.

## Diagnose sicher teilen

- Diagnoseexporte können ausgewählte Mannschaften, Vereins-/Wettbewerbs-IDs, Spielorte, Konfigurationstitel und Spielinformationen enthalten. Vor Veröffentlichung prüfen und bei Bedarf kürzen.
- Keine Home-Assistant-Zugriffstokens, Anmeldedaten, vollständigen `.storage`-Verzeichnisse, Datenbanken, Bootstrap-HTML-Seiten oder Mitschnitte mit Headern in Issues hochladen.
- Der HTTP-Client redigiert ihm bekannte Client-Tokenwerte in seinen Fehlerausgaben. Das ersetzt keine Prüfung von Diagnosen und Logs vor dem Teilen.

## Sicherheitsprobleme melden

Bitte keine funktionsfähigen Zugangsdaten oder personenbezogenen Daten in öffentliche Issues schreiben. Falls GitHub in diesem Repository eine private Schwachstellenmeldung anbietet, diese verwenden. Andernfalls zunächst nur eine unverfängliche Kontaktanfrage im Issue-Tracker stellen und sensible Details erst über einen mit dem Maintainer vereinbarten nichtöffentlichen Kanal austauschen.

## Geerbte Repository-Historie

Dieses Projekt erhält die ursprüngliche Git-Historie. Ältere, bereits im Originalrepository vorhandene Entwicklungsstände enthielten Laufzeitdateien, darunter Home-Assistant-Authentifizierungsdaten und eine Datenbank. Diese Dateien wurden aus dem aktuellen Quellbaum entfernt und gegen erneutes versehentliches Hinzufügen ignoriert. **Das entfernt sie nicht aus älteren Commits, Tags oder Kopien.** Die Integrationsdateien aus `custom_components/handballnet/` sind von diesen Entwicklungsdateien getrennt.

Wer echte Zugangsdaten jemals öffentlich versioniert hat, muss sie an der jeweiligen Quelle widerrufen oder ersetzen. Eine reine Dateilöschung oder das Umschreiben einer einzelnen Kopie ist kein Widerruf. Dieser Fork behauptet nicht, die ursprünglichen Daten seien aktiv, zu einer bestimmten Installation gehörig oder aus allen Kopien entfernt.

## Grenzen

Der Fork wird unabhängig betrieben; er kann keine dauerhafte Verfügbarkeit oder unveränderte Zugriffsregeln der externen Schnittstelle garantieren. Bitte keine Zugriffssperren durch aggressive Wiederholungen oder parallele Lasttests verschärfen.
