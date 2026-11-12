# Vereinslogos zentral verwalten

[Zur Hauptanleitung](../README.md) · [Karten-Ausnahmen](dashboard-karten.md#eigene-vereinslogos-logo_overrides)

Dieser Entwicklungsstand ergänzt die bisherige Kartenkonfiguration um eine **zentrale Logo-Verwaltung direkt in der Integration**. Die folgende Bedienung setzt die Installation dieses neuen Backend- und Kartenstands voraus; eine vorhandene ältere Version erhält die Menüpunkte nicht durch eine YAML-Änderung.

## Ein Logo hinterlegen

1. **Einstellungen → Geräte & Dienste → Handball.net** öffnen und bei einem vorhandenen Eintrag **Konfigurieren/Optionen** wählen. Die genaue Beschriftung hängt von der HA-Oberfläche ab.
2. **Logos verwalten** auswählen.
3. Die Mannschaft aus der Liste wählen oder ihren vollständigen Namen eingeben. Die Liste berücksichtigt bekannte Mannschaften aus den Daten aller eingerichteten Team-, Vereins- und Turniereinträge sowie vorhandene Zuordnungen. Es erfolgt dafür keine zusätzliche Suche bei handball.net.
4. **Bild-URL setzen oder bearbeiten** oder **Bilddatei hochladen** wählen.
5. Eine direkte Bildadresse beziehungsweise eine Bilddatei angeben und bestätigen. Nach bestätigter Speicherung informiert der Dialog über das Ergebnis.

Die Zuordnung gilt anschließend **für alle drei mitgelieferten Karten und über die verschiedenen Handball.net-Konfigurationseinträge hinweg**. Keine Wiederholung in jeder Karte und keine zusätzliche YAML-Zuordnung nötig. Nach der erstmaligen Installation des neuen Codes die geöffneten Browser/Apps einmal vollständig neu laden; spätere Änderungen im Logo-Dialog werden über die bestehenden Entitäten direkt an die Karten weitergegeben. Logoänderungen lösen keine externe Datenabfrage und keinen Core-Neustart aus.

## Mannschaftsnamen und Vorrang

Namen werden ohne Beachtung von Groß-/Kleinschreibung und überzähligen Leerzeichen verglichen. Andere Zusätze wie „2“ sind dagegen andere Namen. Die Zuordnung erfolgt nach Namen, nicht nach einer unscharfen Vereins- oder Bildersuche. Eine Umbenennung kann daher eine weitere oder geänderte Zuordnung erfordern.

Die Reihenfolge ist:

1. gültige individuelle Ausnahme der Karte unter `logo_overrides`,
2. gültige zentrale Logo-Zuordnung,
3. bisheriges API-Bild,
4. neutraler leerer Bildplatz, falls keine Quelle funktioniert.

Einzelne fehlerhafte Quellen werden ohne Endlosschleife übersprungen. Gewöhnliche HA-Zustandsupdates starten keine dauernden Wiederholungen. Bewusstes erneutes Speichern derselben Bildquelle im zentralen Dialog erlaubt einen neuen Versuch nach einer zwischenzeitlichen Störung.

**Wenn ein zentrales Logo nicht erscheint:** Zuerst prüfen, ob die betreffende Karte bereits eine individuelle `logo_overrides`-Zuordnung für diese Mannschaft enthält. Diese absichtliche Ausnahme hat weiterhin Vorrang. Soll künftig die zentrale Einstellung gelten, nur diesen Mannschaftseintrag aus der Kartenkonfiguration entfernen; andere Ausnahmen erhalten.

## Zulässige Bilder und Adressen

- Uploads: vollständige, nicht animierte **PNG-, JPEG- oder WebP-Dateien**.
- Maximal **5 MiB Eingangsdaten**, **4096 Pixel je Seite**, **16 Millionen Pixel insgesamt**. Die erzeugte PNG-Datei darf maximal 16 MiB groß sein.
- SVG, HTML, Animationen und beschädigte Dateien werden als Upload abgewiesen.
- Bilder werden anhand ihres Inhalts geprüft und als PNG ohne übernommene Metadaten neu gespeichert. Der ursprüngliche Dateiname wird nicht als Speicherpfad benutzt. Ein Inhalts-Hash erzeugt eine neue, cachefeste Adresse für ein tatsächlich verändertes Bild.
- Bildadressen dürfen sichere HTTP(S)-URLs oder relative Pfade wie `/local/vereinslogos/beispiel.png` sein. Eine Webseitenadresse mit eingebettetem Logo ist nicht automatisch eine Bildadresse. Keine Zugangsdaten in URLs eintragen. Bei HTTPS-Zugriff auf HA auch für externe Bilder HTTPS verwenden.
- Die Integration lädt externe Adressen **nicht serverseitig herunter**. Der Browser lädt solche Bilder wie die bisherigen API-Logos; Verfügbarkeit und gegebenenfalls externe Zugriffsanforderungen beachten.

Bilder werden nicht automatisch im Internet gesucht. Bereits verlorene Bildteile werden nicht rekonstruiert und schwarze oder weiße Hintergründe nicht pauschal entfernt. Dafür eine tatsächlich geeignete Grafik verwenden und Nutzungsrechte beachten. Eine PNG-Datei ist nicht zwangsläufig transparent.

## Auf das API-Original zurücksetzen

Den Dialog erneut öffnen, die betreffende Mannschaft wählen und **API-Original wiederherstellen** auswählen. Das Entfernen der zentralen Ausnahme muss bestätigt werden. Danach gilt wieder das API-Bild – sofern nicht weiterhin eine individuelle Karten-Ausnahme Vorrang hat.

Die API-Daten werden nie mit der Ersatzgrafik überschrieben. Abfrageintervalle und andere gespeicherte Eintragsoptionen bleiben bei Logoänderungen erhalten. Intervalle lassen sich weiterhin separat über **Abfrageintervalle** bearbeiten; dabei werden positive ganze Sekundenwerte verlangt.

## Speicherung, Datenschutz und Sicherung

Die zentrale Zuordnung liegt in einem eigenen, von HA verwalteten Store. Hochgeladene Grafiken liegen im HA-Konfigurationsverzeichnis unter `www/handballnet/logos` und werden unter `/local/handballnet/logos/<inhaltshash>.png` ausgeliefert. Die Integration stellt genau diesen Unterpfad selbst bereit, auch wenn `/local` beim ursprünglichen Frontendstart noch nicht registriert war.

**Diese Bildadressen sind öffentlich erreichbar, soweit die HA-Webadresse erreichbar ist; es gibt keine individuelle Bild-Anmeldung.** Keine privaten Fotos oder vertraulichen Dokumente dort hochladen. Die Grafiken sind Teil der eigenen HA-Konfiguration, nicht Bestandteil dieses GitHub-Repositories oder seiner MIT-Lizenz.

Beim Entfernen einer Zuordnung wird die hochgeladene Datei bewusst **nicht gelöscht**: Eine andere Zuordnung könnte sie noch verwenden. Auch ein abgebrochener oder nicht sicher bestätigter Speicherversuch kann eine ungenutzte Bilddatei hinterlassen. Automatisches Aufräumen solcher Dateien ist nicht Teil dieser Version.

Vor Backend-Updates die bisherige Integration und die HA-Konfiguration einschließlich verwalteter Daten und `www` sichern. Ein Austausch neuer Python-Module kann einen regulären HA-Neustart erfordern; der spätere reine Logo-Wechsel im Dialog nicht. Vorhandene Integrationseinträge für ein Update nicht löschen. Einen Konfigurations-Store nicht direkt bearbeiten oder aus einer fremden Installation kopieren.

## Fehlerfälle

Bei Speicherfehlern bestätigt der Dialog die Änderung nicht. Speicherplatz und HA-Protokoll prüfen; beschädigte bestehende Logo-Daten werden nicht still durch eine leere Zuordnung überschrieben. Eine nicht ladbare optionale Logo-Verwaltung soll die übrigen Handballdaten nicht abschalten; diese verwenden dann weiter die API-Logos. Der Fehler bleibt protokolliert und muss gezielt behoben werden.

Nach einem fehlgeschlagenen Upload muss eine Datei gegebenenfalls erneut ausgewählt werden, weil HA temporäre Uploads nach der Verarbeitung entfernt. Eine erfolgreich bestätigte Logoänderung benötigt weder eine neue handball.net-Abfrage noch das Löschen oder Neueinrichten der Integration.
