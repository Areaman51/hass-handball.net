# Fehlersuche, Diagnose und Abfrageverhalten

[Zur Hauptanleitung](../README.md)

## Zuerst unterscheiden

1. **Einrichtung scheitert:** Suchbegriff, aktuelle ID, API-Antwort und Log prüfen. Ein API-Fehler wird im Flow als `api_blocked` angezeigt, wenn der HTTP-Helfer eine Störung erkannt hat. Das ist kein Beweis für eine dauerhafte Sperre und nicht gleichbedeutend mit „Team existiert nicht“.
2. **Entitäten fehlen:** Setup-Fehler, ausgewählte Eintragsart und Teamliste prüfen. Ein Turnier erzeugt andere Sensoren als ein Team. Dynamisches Nachanlegen von Positionssensoren erfolgt nicht bei jedem Update.
3. **Entitäten sind leer/alt:** Anbieter, Cachezeiten, gewählte Staffel und `last_update_success` gemeinsam prüfen.
4. **Nur die Karte funktioniert nicht:** Existiert die Entität? Sind die erwarteten Attribute vorhanden? Erst danach JavaScript-Ressource und Browsercache prüfen.

Ein HTTP-Fehler ist kein erfolgreich geladener leerer Spielplan. Der aktuelle Client gibt Fehler weiter; misslungene Abfragen sollen keine vermeintlich gesunden leeren Daten in den Cache schreiben. Beim Coordinator-Fehler bleiben vorherige Daten grundsätzlich erhalten, Coordinator-Sensoren können aber nicht verfügbar werden. Teaminfo-/Logo- und Tabellenplatzabfragen sind teilweise Best Effort: Ein fehlender optionaler Datenbereich muss nicht den gesamten Abruf fehlschlagen lassen. In einem Verein kann ein wesentlicher Teamfehler den gemeinsamen Updatezyklus scheitern lassen.

## HTTP 403, Client-Token und User-Agent

Der gemeinsame HTTP-Helfer bedient die neue API `https://handball.net/api/new`.

- Vor API-Aufrufen lädt er die öffentliche Webseite `https://www.handball.net/` und liest das Meta-Tag `client-token`.
- Der Token wird pro HA-Instanz im Arbeitsspeicher für **15 Minuten** gecacht. Eine Sperre verhindert parallele doppelte Bootstrap-Abrufe.
- API-Requests verwenden `x-client-token`, einen zur API passenden **Referer ohne www** und den nur auf diese Requests begrenzten User-Agent `Mozilla/5.0`.
- Nach **403** wird der zurückgewiesene Token erneuert und der API-Aufruf **genau einmal** wiederholt. Das ist keine unbegrenzte Retry-Schleife.
- Timeout: **30 Sekunden pro HTTP-Anfrage**, nicht zwingend pro gesamtem Update. Weiterleitungen werden nicht automatisch verfolgt.

Die unterschiedliche Hostform ist beabsichtigt: Webseite/Bootstrap mit `www`, API-Referer ohne `www`. Nicht global den User-Agent von Home Assistant ändern und keine Sicherheitseinstellungen des eigenen Systems abschalten.

**Es gibt kein Tokenfeld im Config- oder Options-Flow.** Keine persönlichen Anmeldedaten, Browsercookies oder manuell abgeschriebenen Tokens eintragen. Der öffentliche Bootstrap kann sich beim Anbieter ändern; Token- und Headerbehandlung garantieren keine dauerhafte Erreichbarkeit und umgehen keine interaktive Challenge.

Wenn 403 bleibt:

1. Installierten Source-Commit und Integrationsversion prüfen. Nicht versehentlich nur einzelne Dateien zwischen Ständen mischen.
2. Im Log unterscheiden, ob bereits der **Bootstrap** oder erst die **API** abgewiesen wurde.
3. Statuscode, Endpunkt und gegebenenfalls Cloudflare-Ray-ID prüfen. Keine kompletten HTML-Seiten oder Header mit Tokens veröffentlichen.
4. HTTPS-/DNS-/Proxy-Verbindung der HA-Laufzeit prüfen. Ein funktionierender Desktopbrowser beweist nicht, dass derselbe Zugriff aus der HA-Umgebung gelingt.
5. Nicht aggressiv neu laden oder Intervalle verkürzen; abwarten und einen bereinigten Fehlerbericht erstellen.

## Weitere Fehlerbilder

| Meldung/Status | Einordnung und nächster Schritt |
|---|---|
| `401` | Anbieter verlangt Authentisierung; kein Benutzer-Login in der Integration vorgesehen. Stand und Protokoll prüfen. |
| `404` | Ressource/ID/Endpunkt nicht vorhanden; aktuelle IDs beziehungsweise API-Änderung prüfen. |
| `429` | Drosselung; Intervalle erhöhen, Diagnosen und manuelle Refreshs begrenzen. |
| Timeout/Verbindungsproblem | Netzwerk, DNS, TLS, Proxy und Anbieterstatus prüfen. |
| HTTP 200, aber kein JSON | Mögliche HTML-/Challenge-Antwort oder API-Änderung. Status 200 allein ist kein erfolgreicher Datenabruf. |
| JSON ist kein Objekt oder `success: false` | Unbrauchbare API-Antwort; der Helfer meldet einen Fehler. |
| „Keine Spiele“ bei erfolgreichem Abruf | Spielplan noch nicht veröffentlicht, falsche Mannschaft/Phase oder echte leere Daten möglich. |
| Tabelle korrekt, Teamkarte ohne Rang | Bekannte Attributabweichung: Team-Sensor hat Rang im Zustand, Karte erwartet `position`. Siehe [Karten](dashboard-karten.md). |
| Fehlender Pokalspielplan | Teilnehmerermittlung ohne Tabelle hat noch einen Legacy-API-Fallback; nicht als vollständig unterstützt betrachten. |
| „Live“ ohne Ereignisse | Zeitfenster ist aktiv; Anbieter liefert möglicherweise keinen Ticker. Logs auf echte Abruffehler prüfen. |

## Abfrageverhalten und Cachegrenzen

| Einstellung/Cache | Wert und Wirkung |
|---|---|
| `update_interval` | Standard **3600 Sekunden**; Coordinator startet in diesem Takt |
| `update_interval_live` | Standard **15 Sekunden**, sobald ein Team-/Vereinsupdate eine Partie im Zweistundenfenster erkennt |
| Team-Spielplan-Cache | **3600 Sekunden**, je API-Client; dadurch können auch Ergebnisse trotz Live-Takt alt bleiben |
| Ligentabellen-Cache | **3600 Sekunden** |
| Teaminformationen-Cache | **21600 Sekunden** |
| Öffentlicher Client-Token | **900 Sekunden**, gemeinsam pro HA-Instanz |

Es gibt **keinen hier aktiven unabhängigen 60-Sekunden-Live-Sucher**, obwohl `LIVE_GAME_CHECK_INTERVAL = 60` in den Konstanten steht. Der Coordinator erkennt einen Spielbeginn erst bei einem seiner Updates. Bei normalem Stundentakt kann das entsprechend verspätet geschehen. Kalender oder zusätzliche Sensoren schaffen keinen eigenen kürzeren Abfrageweg.

Turniere wechseln im aktuellen Code nicht automatisch auf den Team-Live-Takt. Der Coordinator liest Tabellen, ermittelt Mannschaften und sammelt zugehörige Teamspielpläne; Ergebnisse werden nach Spiel-ID dedupliziert und auf die Phase gefiltert. Zusätzliche Teilnehmer werden nur begrenzt verfolgt; der Code setzt eine Schutzgrenze von 256 bekannten Teams. Das ist keine Garantie für beliebig große oder unvollständige Turniere.

Die Caches gehören zum jeweiligen API-Client/Coordinator und sind nicht als instanzweites zentrales Cacheversprechen zu verstehen. Unterschiedliche Einträge können Abfragen duplizieren. Ein Refresh fordert einen Coordinator-Lauf an, **umgeht die API-Caches jedoch nicht**. Nach einem bewusst notwendigen Eintrags-Reload entsteht ein neuer Coordinator mit neuen API-Caches; nicht dauernd neu laden, um diese Schutzwirkung zu umgehen.

## Aktionen

Quelle: `services.yaml` **und** die Registrierung in `__init__.py`. Eine deklarierte Aktion bedeutet nicht automatisch, dass ihr Handler fehlerfrei funktioniert.

| Aktion | Daten | Tatsächlicher Umfang/Grenze |
|---|---|---|
| `handballnet.refresh_team_data` | Pflichtfeld `team_id` als Text | Sucht den ersten Coordinator, in dessen geladenen `teams` das Team vorkommt, und fordert ein Update dieses **gesamten Eintrags** an. Kein gezielter Cache-Bypass; bei unbekanntem Team keine aussagekräftige Rückgabe. |
| `handballnet.diagnose_team` | Pflichtfeld `team_id` als Text | Im YAML beschrieben, Handler ist derzeit aber nicht passend an `hass` und `ServiceCall` gebunden. Nicht als zuverlässig nutzbaren Diagnoseweg voraussetzen. |
| `handballnet.reload_config` | keine Felder | Im Code deklariert/registriert, Handler erwartet jedoch ein HA-Objekt statt des beim Dienstaufruf übergebenen `ServiceCall`. Für einen verlässlichen Reload die HA-Eintragsoberfläche oder einen Neustart nutzen. |

Auch `refresh_team_data` ist derzeit direkt mit einem zweiparametrigen Handler registriert und nicht an das HA-Objekt gebunden. Die oben beschriebene Logik ist die **implementierte Absicht**, keine erfolgreiche Ende-zu-Ende-Dienstabnahme. Bis zur Reparatur der Handlerbindung sind die nativen HA-Funktionen zum Neuladen und der Diagnosedownload vorzuziehen.

Die reale Form eines Refresh-Aufrufs im Aktions-YAML wäre:

```yaml
action: handballnet.refresh_team_data
data:
  team_id: "AKTUELLE_TEAM_ID_EINTRAGEN"
```

Der Platzhalter muss durch die eigene aktuelle ID ersetzt werden. Wegen der genannten Handlergrenze ist dieses Beispiel **keine Zusage einer derzeit funktionierenden Aktion**. Als `team_id` wird eine Anbieter-ID erwartet, keine HA-Entitäts-ID wie `sensor.…`. Es gibt keine entsprechend implementierte `tournament_id`-Refresh-Aktion.

## Diagnose und Datenschutz

Der Diagnosedownload eines Eintrags liefert laut `diagnostics.py`:

- Titel, Version, gespeicherte `data` und `options` des Config-Entries;
- API-Basis-/Referer-Informationen und zuletzt fehlschlagende Endpunkte;
- Coordinator-Erfolg, Intervall und letzte Exception;
- je Team Zusammenfassung, Health, nächstes/letztes Spiel sowie bis zu fünf erste und fünf letzte Rohspiele.

Ein Turniereintrag erhält dabei nicht dieselbe ausführliche Turnier-Zusammenfassung wie ein Team. Der Diagnosedownload ist kein vollständiger Netzwerk-Trace.

Der Client protokolliert bei Fehlern unter anderem Endpunkt, Parameter, Status, Referer, gegebenenfalls `cf-ray` und einen begrenzten Antwortausschnitt. Gleiche Fehler werden je Endpunkt zunächst auf WARNING, Wiederholungen auf DEBUG ausgegeben; Erholung wird auf INFO gemeldet. Bekannte Tokenwerte werden vor dem Kürzen der Ausschnitte redigiert. **Das ersetzt keine eigene Prüfung vor dem Teilen.**

Diagnosen enthalten Konfigurationsdaten sowie Team-/Vereinsnamen, IDs und Spielorte. Solche Angaben können persönliche Zusammenhänge offenlegen, auch wenn die Spiele öffentlich sind. Keine vollständige HA-Konfiguration, Backups, Authentisierungsdaten, Tokens, Cookies, private Adressen oder unbearbeiteten Diagnosen veröffentlichen. Erst lokal prüfen, unnötige Werte entfernen und nur die minimale reproduzierbare Information teilen.

Wenn weitere Details nötig sind, die Integrations-Debugprotokollierung über die HA-Oberfläche aktivieren, den Fehler möglichst einmal reproduzieren, Logging wieder abschalten und die Datei vor einem Upload bereinigen. Große Logsammlungen sind kein Ersatz für ein kleines nachvollziehbares Beispiel.

## Inhalt eines brauchbaren Fehlerberichts

- Fork und konkreter Commit/Version, HA-Version und Installationsart.
- Eintragsart Team/Verein/Turnier, betroffene Funktion und Zeitpunkt mit Zeitzone.
- Erwartetes und beobachtetes Verhalten, auch ob handball.net selbst Daten zeigt.
- Bereinigter Logausschnitt mit Status und Endpunkt, keine Tokenwerte.
- Ob ein echter HA-Lauf, ein Stub-Test oder nur eine Karten-Vorschau beobachtet wurde.
- Bereits ausprobierte Schritte und ob ein Cacheablauf abgewartet wurde.
