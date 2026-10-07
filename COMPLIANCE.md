# Discogs, Datenschutz und Namensvorprüfung

Recherche: 06.10.2026. Keine rechtliche Freigabe. Die vorhandene frühere Chat-Aussage, Opt-in allein sei ausreichend, ist angesichts der aktuellen Bedingungen zu pauschal.

## Wesentliche API-Grenze

Primärquelle: [Discogs API Terms of Use](https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use), dort zuletzt geändert am 27.05.2025.

Collection, Wantlist und Nutzername zählen als Restricted Data. Die Bedingungen verbieten deren Übertragung an Dritte und kommerzielle Nutzung. Zusätzlich bestehen Einschränkungen für das Umlenken von Traffic und das Umgehen des Discogs-Marktplatzes. Damit ist ein Netzwerk mit nutzerübergreifender Anzeige und Tausch-Anknüpfungspunkten **nicht eindeutig gedeckt**, selbst bei Nutzer-Einwilligung. Vor echtem Netzwerkbetrieb schriftlich mit Discogs klären. Keine Monetarisierung oder externen Transaktionen einbauen. Keine Annahme einer erteilten Sondergenehmigung.

`MATCHING_APPROVED=false` sperrt Matchliste, echte Vergleichsrouten und Sichtbarkeitsfreigaben. Die öffentliche Demo enthält ausschließlich erfundene Daten. Persönlicher Import nutzt nur den eigenen Account; auch dessen konkreten Anwendungsfall bei App-Registrierung korrekt beschreiben.

## Aktualität und Attribution

API-Inhalte dürfen nicht mehr als sechs Stunden veraltet angezeigt werden; Speicherung ist auf die notwendige Diensterbringung begrenzt. Der MVP nutzt den Beginn des vollständigen Imports als konservativen Zeitstempel, verbirgt veraltete Daten und löscht abgelaufene Snapshots. Kein CDN-/Browsercache für Profildaten. Keine dauerhafte Historie von Collections.

Die App enthält den verlangten Unabhängigkeitshinweis im Footer und neben echten API-Daten „Data provided by Discogs“ mit Links zur jeweils betroffenen Collection bzw. zum Release. Diese Links tragen kein `nofollow`. Cover-Thumbnails werden aus autorisierten frischen Snapshots über den eigenen Server geladen. Nur freigegebene Discogs-Bildhosts, geprüfte Bildformate und maximal zehn Minuten begrenzter RAM-Cache; keine externe Bildverbindung des Browsers.

## Dokumentation und Rate Limits

Offizielle Referenz: [Discogs Developers](https://www.discogs.com/developers). Das Portal und seine OAuth-Unterseite lieferten während der Recherche HTTP 403 und waren nicht direkt lesbar. Daher **keine vollständige aktuelle Dokumentationsverifikation behaupten**. Die Implementation verwendet OAuth 1.0a/HMAC-SHA1, `/oauth/request_token`, `/oauth/access_token`, `/oauth/identity`, `/users/<username>/collection/folders/0/releases` und `/users/<username>/wants`. Vor Freischaltung mit dem tatsächlichen Developer-Dashboard und zwei freiwilligen Accounts prüfen.

Bekannte Basislimits sind 60 authentifizierte bzw. 25 nicht authentifizierte Anfragen pro Minute pro IP; aktuelle Werte live über `X-Discogs-Ratelimit`, `X-Discogs-Ratelimit-Used`, `X-Discogs-Ratelimit-Remaining` bestätigen. Implementation drosselt vorsorglich auf etwa 40/min, wartet bei erschöpftem Limit und berücksichtigt 429/Retry-After. Kein Verteilen auf weitere Keys zur Limitumgehung. OAuth-Autorisierung kann Schreibrechte enthalten; Collection-, Wantlist- und Identitätsdaten werden ausschließlich gelesen. Nur der OAuth-Tokenaustausch verwendet POST; keine Collection-/Marketplace-Schreiboperationen. Die POST-Methoden wurden zusätzlich mit dem [Discogs-Client-Quellcode](https://github.com/joalla/discogs_client/blob/master/discogs_client/client.py) abgeglichen; der Live-Test der registrierten App bleibt erforderlich.

## Datenschutz vor öffentlicher Freischaltung

Primärquelle: [DSGVO, EUR-Lex](https://eur-lex.europa.eu/eli/reg/2016/679). Relevant sind insbesondere Zweckbindung/Minimierung/Speicherbegrenzung (Art. 5), Rechtsgrundlagen und Einwilligung (Art. 6/7), Transparenz (Art. 13), Auskunft/Export/Löschung (Art. 15/17/20), Auftragsverarbeitung und Schutzmaßnahmen (Art. 28/32) sowie internationale Transfers (Kapitel V).

Erforderlich: echte Betreiberidentität/Adresse/Kontakt; passende Hinweise und Rechtsgrundlagen prüfen; Hostingregion und Anbieter benennen; AV-Vertrag und Drittlandübermittlung prüfen; Protokollierung und Backup-Löschfristen festlegen. Eine Anmeldung und ein gesondertes Freigabe-Opt-in sind getrennt. Öffentliche Besucher erhalten keine echten Profile. Nutzer können exportieren, Freigaben zurücknehmen und ihre Daten löschen. Kein Analytics, kein Maildienst, keine Werbung.

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
