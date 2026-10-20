# Discogs, Datenschutz und Namensvorprüfung

Recherche: 06.10.2026. Keine rechtliche Freigabe. Die vorhandene frühere Chat-Aussage, Opt-in allein sei ausreichend, ist angesichts der aktuellen Bedingungen zu pauschal.

## Wesentliche API-Grenze

Primärquelle: [Discogs API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use), dort zuletzt geändert am 27.05.2025.

Collection, Wantlist und Nutzername zählen als Restricted Data. Die Bedingungen verbieten deren Übertragung an Dritte und kommerzielle Nutzung. Zusätzlich bestehen Einschränkungen für das Umlenken von Traffic und das Umgehen des Discogs-Marktplatzes. Damit ist ein Netzwerk mit nutzerübergreifender Anzeige und Tausch-Anknüpfungspunkten **nicht eindeutig gedeckt**, selbst bei Nutzer-Einwilligung. Vor echtem Netzwerkbetrieb schriftlich mit Discogs klären. Keine Monetarisierung oder externen Transaktionen einbauen. Keine Annahme einer erteilten Sondergenehmigung.

`MATCHING_APPROVED=false` sperrt Matchliste, echte Vergleichsrouten und Sichtbarkeitsfreigaben. Die öffentliche Demo enthält ausschließlich erfundene Daten. Persönlicher Import nutzt nur den eigenen Account; auch dessen konkreten Anwendungsfall bei App-Registrierung korrekt beschreiben.

## Aktualität und Attribution

API-Inhalte dürfen nicht mehr als sechs Stunden veraltet angezeigt werden; Speicherung ist auf die notwendige Diensterbringung begrenzt. Der MVP nutzt den Beginn des vollständigen Imports als konservativen Zeitstempel, verbirgt veraltete Daten und löscht abgelaufene Snapshots. Kein CDN-/Browsercache für Profildaten. Keine dauerhafte Historie von Collections.

Beim Besuch der Collection-Seite werden abgelaufene Imports teilnehmender Mitglieder über den bestehenden, gedrosselten Importdienst automatisch erneuert. Der Abgleich wartet auf frische, vollständige Imports; alte API-Daten werden nicht länger gespeichert oder angezeigt. Pausierte und gesperrte Accounts bleiben ausgenommen. Fehlgeschlagene Verbindungen werden frühestens nach einer Stunde erneut automatisch versucht.

Die App enthält den verlangten Unabhängigkeitshinweis im Footer und neben echten API-Daten „Data provided by Discogs“ mit Links zur jeweils betroffenen Collection bzw. zum Release. Diese Links tragen kein `nofollow`. Cover-Thumbnails werden aus autorisierten frischen Snapshots über den eigenen Server geladen. Nur freigegebene Discogs-Bildhosts, geprüfte Bildformate und maximal zehn Minuten begrenzter RAM-Cache; keine externe Bildverbindung des Browsers.

## Dokumentation und Rate Limits

Offizielle Referenz: [Discogs Developers](https://www.discogs.com/developers). Das Portal und seine OAuth-Unterseite lieferten während der Recherche HTTP 403 und waren nicht direkt lesbar. Daher **keine vollständige aktuelle Dokumentationsverifikation behaupten**. Die Implementation verwendet OAuth 1.0a/HMAC-SHA1, `/oauth/request_token`, `/oauth/access_token`, `/oauth/identity`, `/users/<username>/collection/folders/0/releases` und `/users/<username>/wants`. Vor Freischaltung mit dem tatsächlichen Developer-Dashboard und zwei freiwilligen Accounts prüfen.

Bekannte Basislimits sind 60 authentifizierte bzw. 25 nicht authentifizierte Anfragen pro Minute pro IP; aktuelle Werte live über `X-Discogs-Ratelimit`, `X-Discogs-Ratelimit-Used`, `X-Discogs-Ratelimit-Remaining` bestätigen. Implementation drosselt vorsorglich auf etwa 40/min, wartet bei erschöpftem Limit und berücksichtigt 429/Retry-After. Kein Verteilen auf weitere Keys zur Limitumgehung. OAuth-Autorisierung kann Schreibrechte enthalten; Collection-, Wantlist- und Identitätsdaten werden ausschließlich gelesen. Nur der OAuth-Tokenaustausch verwendet POST; keine Collection-/Marketplace-Schreiboperationen. Die POST-Methoden wurden zusätzlich mit dem [Discogs-Client-Quellcode](https://github.com/joalla/discogs_client/blob/master/discogs_client/client.py) abgeglichen; der Live-Test der registrierten App bleibt erforderlich.

## Datenschutz vor öffentlicher Freischaltung

Primärquelle: [DSGVO, EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679). Relevant sind insbesondere Zweckbindung/Minimierung/Speicherbegrenzung (Art. 5), Rechtsgrundlagen und Einwilligung (Art. 6/7), Transparenz (Art. 13), Auskunft/Export/Löschung (Art. 15/17/20), Auftragsverarbeitung und Schutzmaßnahmen (Art. 28/32) sowie internationale Transfers (Kapitel V).

Erforderlich: echte Betreiberidentität/Adresse/Kontakt; passende Hinweise und Rechtsgrundlagen prüfen; Hostingregion und Anbieter benennen; AV-Vertrag und Drittlandübermittlung prüfen; Protokollierung und Backup-Löschfristen festlegen. Die Anmeldung holt Import- und Vergleichseinwilligung gemeinsam ein; ein weiterer Freigabe-Haken ist nicht vorgesehen. Öffentliche Besucher erhalten keine echten Profile. Nutzer können exportieren, Freigaben zurücknehmen und ihre Daten löschen. Kein Analytics, kein Maildienst, keine Werbung.

Nginx-Vorlage deaktiviert Access-Logs, damit OAuth-Callback-Querys nicht geloggt werden. Vor Betrieb zusätzlich Logs des vorgeschalteten Providers prüfen. Sicherheitsbegrenzung speichert für zehn Minuten einen mit dem App-Schlüssel gehashten Client-Identifier. Dies im endgültigen Datenschutztext dokumentieren. Backups müssen Tokenverschlüsselung respektieren und gelöschte Daten dürfen bei Restore nicht wieder dauerhaft erscheinen. Für die erste Testphase keine lang laufenden Snapshots/Backups mit importierten Daten.

## Namen — unverbindlicher Web-Vorabcheck

- **CrateSignal**: bestehender Anbieter [Cratesignal](https://www.cratesignalfba.com/) gefunden. Deshalb als Kandidat verworfen.
- **Collection Relay**: bei exakter Websuche kein eindeutiger gleichnamiger Musikplattformtreffer; im Musikbereich existiert bereits [Relay](https://relay-music.app/). Daher ausschließlich interner Working Title, keine behauptete Marken- oder Domainfreiheit.
- Vor endgültiger Wahl: DPMA/EUIPO/WIPO, Domains, Firmenregister und Appstores gezielt prüfen. Sämtliches sichtbares Branding kommt aus `WORKING_TITLE`.

Quelle zur Discogs-Namensverwendung: [Application Name and Description Policy](https://support.discogs.com/hc/en-us/articles/360009207054-Application-Name-and-Description-Policy). Keine behauptete Partnerschaft oder offizielle Discogs-App.

## Optionales Regal-Radio

Der Player nutzt nach explizitem OK öffentlich bei Discogs verlinkte YouTube-Videos und den regulären sichtbaren IFrame-Player, keine Audioextraktion und keine verdeckte Hintergrundwiedergabe. Mindestgröße 200×200, Native Controls/Branding bleiben erhalten. Keine YouTube-Verbindung vor Zustimmung. Beim Abspielen werden IP/Browserdaten und die Website-Origin an Google übertragen; Datenschutztext berücksichtigt dies. Automatische Folge nur bei sichtbarem Player. Origin-only Referer wird am Embed gesetzt; OAuth-Seiten behalten no-referrer. Primärquellen: [YouTube Required Minimum Functionality](https://developers.google.com/youtube/terms/required-minimum-functionality), [IFrame API](https://developers.google.com/youtube/iframe_api_reference). Marvin hat echten Account-Import und Player anhand seiner Screenshots bestätigt. Das neue kompakte Layout wurde lokal mit simuliertem Player geprüft; echte Streaming-Wiedergabe nach Aktivierung erneut prüfen. Das Video bleibt fest sichtbar und vollständig deckend, nur zusätzliche Bedienelemente erhalten eine zurückhaltendere Darstellung.


## Nutzerbestätigung vom 07.10.2026
Marvin hat auf die Rückfrage ausdrücklich „Vergleiche wurden freigegeben“ geantwortet. Die Ticketantwort selbst wurde nicht eingesehen. Auf dieser Grundlage ist die Aktivierung der bestehenden opt-in-basierten Vergleiche autorisiert. Vorherige vorsichtige Bewertung oben bleibt als Recherchehistorie bestehen. Die API Terms wurden erneut am 07.10.2026 gelesen (unverändert, Last Updated 27.05.2025). Kein Handel/Marketplace-Schreibzugriff oder Monetarisierung ergänzt. Einladungslinks enthalten nur eine signierte interne ID und verfallen nach sieben Tagen; Gäste sehen weder Einladenden-Namen noch seine Collection. Links erlauben Registrierung ohne separaten Einladungscode; gemeinsame Testseiten-Zugangsdaten bleiben zusätzlich nötig. Freigabe bedeutet ausdrücklich Sichtbarkeit unter angemeldeten Teilnehmern. URL besitzt keine Discogs-Tokens. Nutzernamen und Vergleichsdaten erscheinen nur nach beiderseitigem Opt-in; Snapshots bleiben auf sechs Stunden beschränkt.


## Kompaktere Quellenangaben (07.10.2026)
API Terms erneut geprüft: Attribution muss direkt bei API-Daten stehen und auf die passende Discogs-Seite verlinken. Kein alleiniger Footer-Hinweis. Albumkacheln enthalten daher eine kleine Quellenzeile; die ganze Kachel ist der Release-Link (neuer Tab, noopener/noreferrer, kein nofollow). Das stilisierte Regal hat einen Collection-Quellenlink direkt am Titel. Quellenzeilen bei Genres sind in die angrenzende Collection-Quellenangabe aufgenommen. Die Rückenfarben/Breiten sind Illustration, keine von Discogs bezogenen Rückenabbildungen. Nutzer-Suche enthält ausschließlich freigegebene frische Teilnehmer hinter Anmeldung und Freigabe des Suchenden.

### BGL-Freundschaften und Chat
BGL-eigene Daten, keine Discogs-Nachrichten: Anfrage mit beidseitiger Bestätigung, private Nachrichten nur zwischen bestätigten Kontakten bei beiderseits aktivierter Profilfreigabe. Chat sendet keine Daten an Discogs/YouTube. Präsenz und Tippstatus werden nur bestätigten Kontakten angezeigt und verfallen nach 60 bzw. sechs Sekunden. Nachrichten bleiben bis zur Löschung eines beteiligten Accounts in der aktiven DB; Accountlöschung entfernt per Foreign-Key-Cascade die Beziehung und deren Chat. Auskunftsexport enthält Kontakte und selbst gesendete Nachrichten. Sichtbarkeit zurücknehmen sperrt Zugriff, löscht keine Nachrichten. Datensicherungen folgen den bereits vom Betreiber festzulegenden Backup-Fristen. Datenschutzseite ergänzt; Betreiberangaben für Imprint werden aus bestehenden ENV-Feldern übernommen.

## Vergleichsteilnahme im regulären Anmeldeschritt (07.10.2026)
Die separate Sichtbarkeits-Checkbox entfällt. Der vorhandene Import-Haken erklärt und bestätigt ausdrücklich Mitgliedersuche sowie Sichtbarkeit von Profil, Collection und Wantlist unter angemeldeten Mitgliedern. Der zweite Haken bleibt die Altersbestätigung. Neue und zurückkehrende Accounts werden erst nach dieser aktualisierten OAuth-Anmeldung sichtbar. Alte private Accounts werden nicht pauschal umgestellt; sie durchlaufen einmal den regulären Anmeldeschritt mit der neuen Erklärung. Alte Formulare und noch laufende OAuth-Anmeldungen ohne neue Zustimmungsfassung aktivieren keine Vergleichsteilnahme. Gäste bleiben ausgeschlossen, frische Imports bleiben für Datenzugriff erforderlich, die Discogs-Freigabe bleibt serverseitig konfiguriert und Sperren gelten weiter. Unter den Account-Einstellungen kann Teilnahme pausiert oder der Account gelöscht werden; die nächste reguläre Anmeldung nimmt Teilnahme wieder auf. Diese Ablaufbeschreibung ersetzt die frühere separate Freigabe in den historischen Abschnitten.


## Technische Änderung: Album-Abgleich

Der aktive Score ist mit dieser Version `album-cosine-v2`: Gemeinsame Discogs-Master-IDs gruppieren Pressungen. Ohne eindeutige Master-Zuordnung gilt die Release-ID; ähnliche Titel werden nicht als Identität geraten. Kopien und mehrere Pressungen desselben identifizierten Albums zählen einmal. Beide Versionen bleiben mit ihren importierten Angaben und Discogs-Links sichtbar. Wantlist- und Tauschtreffer bleiben auf konkrete Releases bezogen. Es werden keine zusätzlichen Discogs-Endpunkte, Drittanbieter-Textdienste oder neuen Datenempfänger eingeführt. Online-/Tippstatus und Nachrichten behalten die bestehende Beschränkung auf bestätigte Kontakte.


## Audit des bestehenden Stands · 20.10.2026

Ausgangspunkt: bestehender produktiver Code, kein Rückbau auf den MVP. Laut aktuellem Betreiber-Update prüft Discogs die Anfrage weiterhin. Diese Prüfung ist keine Sonderfreigabe. Die bestehende Konfiguration von `MATCHING_APPROVED` und die Vergleichsfunktionen werden durch diesen UI-/Compliance-Patch nicht verändert. Die oben beschriebene Restricted-Data-Grenze bleibt klärungsbedürftig; Disclaimer, Attribution und Nutzerzustimmung allein lösen sie nicht auf.

Geprüfte Primärquelle: [API Terms of Use](https://support.discogs.com/hc/articles/360009334593-API-Terms-of-Use), Abschnitte API USE AND RESTRICTIONS (3, 5) und DISCOGS INTELLECTUAL PROPERTY. Vollständiger vorgeschriebener Unabhängigkeitshinweis im gemeinsamen Footer, direkt verlinkte Quellen bei echten Releases und Übersichten, keine `nofollow`-Links. Layout und BlackGoldLink-Marke bleiben bestehen. Keine bezahlten Funktionen, Werbung, Marketplace-Schreibzugriffe oder Weitergabe an Werbedienste implementiert.

Speicherung: `users` hält Discogs-ID/-Namen, verschlüsselte OAuth-Credentials und Zustimmung; `snapshots(user_id,data,fetched_at)` hält ausschließlich den aktuellen vollständigen Collection-/Wantlist-Import. Whitelist beim Import: IDs, Master-ID, Titel, Jahr, Künstler, Genres/Stile, Medienformate, Labels und erlaubte Thumbnail-URL; keine privaten Notizen, Zustände, Preise oder Nutzernachrichten. `fetched_at` ist der Beginn des Imports, nicht sein Ende. Teilimporte ersetzen keinen vollständigen Snapshot. `jobs` enthält Status/Zeiten, keine Sammlungshistorie; Entfernung nach sieben Tagen. Accounts/Tokens verbleiben bis zur Löschung. Die bestehende Export-/Löschfunktion und externe Backup-Fristen bleiben getrennt zu prüfen.

Aktualität: `TTL=6*3600`; `snapshot()`, Vergleich, Rangliste und Cover-Freigabe schließen abgelaufene Imports serverseitig aus. Webanfragen und der Worker löschen abgelaufene Snapshots. `refresh_imports()` stellt veraltete aktive Mitglieder in die vorhandene serielle Queue; kein zusätzlicher API-Importer. Persistente Drosselung, verbleibendes API-Limit, 429 und Retry-After werden beachtet. Thumbnails: höchstens zehn Minuten RAM, begrenzt durch die zugehörige Importgültigkeit. Musikmetadaten: höchstens eine Stunde, ebenfalls durch Importgültigkeit begrenzt.

Gefundene Lücke: Bereits gerenderte Collection-/Vergleichsseiten blieben in offenen Tabs sichtbar. Ergänzung: serverseitig aus dem ältesten beteiligten Import berechnete Restgültigkeit, konservativer Browser-Timer ab Navigationsbeginn, erneute Kontrolle bei Fokus/Tab-Rückkehr. Nach Ablauf entfernt `freshness.js` die betroffenen Collection-/Vergleichsbereiche, stoppt Szene und Player und bietet eine manuelle Aktualisierung. Chat und ungesendeter Text bleiben stehen; kein erzwungenes Neuladen. Der Browser-Schutz setzt JavaScript voraus und kann durch den Browser suspendierte Tabs erst bei ihrer Wiederaufnahme bereinigen.

Zugriff: Daten und Jobs sind an `user_id` gebunden. Eigene Imports erfordern eine angemeldete Sitzung; fremde Sammlungen zusätzlich aktive Teilnahme, Matching-Schalter und frische Snapshots. Cover prüfen die Berechtigung auch bei Cache-Treffern. Chat setzt bestätigte Freundschaft voraus; CSRF bleibt aktiv. Bestehende Tests für versteckte/abgelaufene/fremde Profile, Cover und Chat bleiben bestehen. Keine Datenbankmigration und keine Änderung der Score-/Albumidentität.

Betroffen: gemeinsame Footer-/Quellen-Templates, Versionsvergleich und dessen CSS, kleiner Gültigkeitswert im Template-Kontext (`app.py`), Browser-Ablaufkontrolle und Stop-Ereignisse in Szene/Player sowie Tests. Hauptrisiko: eine Collection-Ansicht verschwindet bei Ablauf bewusst; der Nutzer startet eine Aktualisierung selbst. Anonyme Demo-Daten erhalten keine Discogs-Importfrist und werden nicht als echte API-Daten ausgegeben.
