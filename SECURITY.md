# Sicherheit und Datenschutz

Diese Integration verwendet die öffentlich erreichbare handball.net-Webschnittstelle. Für die Einrichtung ist kein persönliches handball.net-Passwort vorgesehen. Der vom Webauftritt gelieferte öffentliche Client-Token wird zur Laufzeit abgerufen und nicht fest im Quellcode hinterlegt.

## Diagnose sicher teilen

- Diagnoseexporte können ausgewählte Mannschaften, Vereins-/Wettbewerbs-IDs, Spielorte, Konfigurationstitel und Spielinformationen enthalten. Vor Veröffentlichung prüfen und bei Bedarf kürzen.
- Keine Home-Assistant-Zugriffstokens, Anmeldedaten, vollständigen `.storage`-Verzeichnisse, Datenbanken, Bootstrap-HTML-Seiten oder Mitschnitte mit Headern in Issues hochladen.
- Der HTTP-Client redigiert ihm bekannte Client-Tokenwerte in seinen Fehlerausgaben. Das ersetzt keine Prüfung von Diagnosen und Logs vor dem Teilen.

## Sicherheitsprobleme melden

Bitte keine funktionsfähigen Zugangsdaten oder personenbezogenen Daten in öffentliche Issues schreiben. Falls GitHub in diesem Repository eine private Schwachstellenmeldung anbietet, diese verwenden. Andernfalls zunächst nur eine unverfängliche Kontaktanfrage im Issue-Tracker stellen und sensible Details erst über einen mit dem Maintainer vereinbarten nichtöffentlichen Kanal austauschen.

## Prüfung des aktuellen Quellstands – 12. November 2026

Der Integrationscode wurde zusätzlich unabhängig vollständig gelesen: 48 Python-Dateien, drei JavaScript-Karten samt visuellen Editoren sowie relevante Upload-, HTTP-, Options-, Workflow- und Dependency-Grenzen. **Kein bestätigter sicherheitsbedingter Veröffentlichungsblocker im geprüften aktuellen Code gefunden.** Das ist keine Garantie lückenloser Sicherheit.

- 155 Python- und 144 Node-Regressionen bestanden. Zusätzliche lokale Proben umfassten 396 URL-Prüfungen, 280 Angriffsdaten-Renderings mit anschließendem HTML-Parsing, 118 abgewiesene unsichere Python-URL-Werte und native Offline-Prüfungen von Upload-/Autorisierungsgrenzen. Kein freier Penetrationstest oder Angriff auf produktive Dienste.
- Bandit meldete keine High-/Medium-Kandidaten. Die zwei Low-Treffer wurden am Code geprüft: ein interner Cache-Schlüssel und eine feste öffentliche Bootstrap-URL, keine eingebauten Kennwörter. Der heuristische Scan des aktuellen versionierten Textbestands bestätigte keine echten Secrets.
- Ein zusätzlicher Advisory-Abgleich mit pip-audit fand bei den sieben festgelegten direkten Testanforderungen sowie einem Snapshot aller 126 Pakete der isolierten nativen HA-2026.11.1-Testumgebung keine bekannten Schwachstellen. Das beschreibt diese Versionen und den damaligen Datenbankstand, nicht alle zusätzlichen Pakete einer produktiven HA-Installation.

Nicht blockierende Härtungspunkte bleiben offen:

1. Der geerbte Legacy-HTTP-Pfad sollte explizite Redirect- und Timeout-Regeln erhalten oder entfernt werden. Eine ausnutzbare SSRF wurde nicht nachgewiesen.
2. Antwortgrößen, Seiten-/Datensatzanzahl und gleichzeitige API-Abfragen sollten zusätzliche globale Obergrenzen erhalten.
3. Für ein Bedrohungsmodell mit weniger vertrauenswürdigen lokalen Dateisystem-Mitschreibern kann der Upload-Verzeichnispfad zusätzlich gegen bereits vorhandene Verzeichnis-Symlinks abgesichert werden. Teamname, Upload-ID und ursprünglicher Dateiname steuern den Zielpfad nicht.
4. Release-Tags sollten im Veröffentlichungsworkflow über Umgebungsvariablen statt direkt in Shellquelltext übernommen und validiert werden; Actions können auf überprüfte Commit-SHAs gepinnt werden. Ein Rechteübergang durch unprivilegierte PR-Autoren wurde nicht festgestellt. Die Workflows wurden durch diese Prüfung nicht geändert.

Öffentliche `/local`-Bilder, browserseitig geladene externe Logoquellen und die dokumentierte Aufbewahrung unreferenzierter Uploads sind beabsichtigte Eigenschaften. Keine vertraulichen Bilder dafür verwenden. Das Audit und der Secret-Scan bereinigen **nicht** die unten beschriebene geerbte Git-Historie und belegen keinen Widerruf früherer Zugangsdaten. Browser-/HA-End-to-End-Prüfungen, ein vollständiger Produktionsaudit und eine Quellcodeprüfung aller Fremdpakete sind damit nicht behauptet.

## Geerbte Repository-Historie

Dieses Projekt erhält die ursprüngliche Git-Historie. Ältere, bereits im Originalrepository vorhandene Entwicklungsstände enthielten Laufzeitdateien, darunter Home-Assistant-Authentifizierungsdaten und eine Datenbank. Diese Dateien wurden aus dem aktuellen Quellbaum entfernt und gegen erneutes versehentliches Hinzufügen ignoriert. **Das entfernt sie nicht aus älteren Commits, Tags oder Kopien.** Die Integrationsdateien aus `custom_components/handballnet/` sind von diesen Entwicklungsdateien getrennt.

Wer echte Zugangsdaten jemals öffentlich versioniert hat, muss sie an der jeweiligen Quelle widerrufen oder ersetzen. Eine reine Dateilöschung oder das Umschreiben einer einzelnen Kopie ist kein Widerruf. Dieser Fork behauptet nicht, die ursprünglichen Daten seien aktiv, zu einer bestimmten Installation gehörig oder aus allen Kopien entfernt.

## Grenzen

Der Fork wird unabhängig betrieben; er kann keine dauerhafte Verfügbarkeit oder unveränderte Zugriffsregeln der externen Schnittstelle garantieren. Bitte keine Zugriffssperren durch aggressive Wiederholungen oder parallele Lasttests verschärfen.
