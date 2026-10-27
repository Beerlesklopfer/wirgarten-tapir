> ⚠️ **Nicht maßgeblich.** Dieses Wiki gehört zu einem abgeschlossenen Proof of Concept für den
> Eigenbetrieb von Tapir und wird nicht gepflegt. Maßgeblich ist die Dokumentation im
> Hauptprojekt: [FoodCoopX/wirgarten-tapir – docs](https://github.com/FoodCoopX/wirgarten-tapir/tree/master/docs),
> Aufbau in Issue [#1300](https://github.com/FoodCoopX/wirgarten-tapir/issues/1300).

# Datenschutz und Löschung

> **Abstract:** Tapir speichert personenbezogene Daten der Mitglieder. Die DSGVO verlangt,
> dass man sie auf Antrag löscht (Art. 17), das Genossenschafts- und Steuerrecht verlangt, dass
> man einen Teil davon jahrelang aufbewahrt. Der Löschknopf in der Mitgliederliste löscht heute
> alles auf einmal und kennt diesen Unterschied nicht. Diese Seite hält fest, welche Daten wo
> liegen, was die Rechtslage verlangt und was noch offen ist. Sie ist die Grundlage für den
> Issue [#1123 „DSGVO-konforme Löschung“](https://github.com/FoodCoopX/wirgarten-tapir/issues/1123).

> **Hinweis:** Das ist eine technische Bestandsaufnahme mit einer Einordnung der Rechtslage,
> keine Rechtsberatung. Fristen und Rechtsgrundlagen muss die jeweilige Genossenschaft mit ihrem
> Prüfungsverband oder Datenschutzbeauftragten bestätigen. Was nicht aus dem Code folgt, steht
> unten als **offen**.

## Das Problem

Ein Mitglied verlangt: „Löscht alle meine Daten.“ Dabei stoßen zwei Pflichten aufeinander:

- **Recht auf Löschung** (Art. 17 DSGVO): Die Daten sind weg, sobald sie für den Zweck nicht
  mehr gebraucht werden oder die Einwilligung widerrufen wird.
- **Aufbewahrungspflichten**: Für Buchführung, Steuer und die Mitgliederliste der Genossenschaft
  darf man bestimmte Daten nicht löschen, auch nicht auf Wunsch.

Beides gilt gleichzeitig. Löscht man zu wenig, verletzt man die DSGVO. Löscht man zu viel,
fehlen Belege und der Nachweis, wer wann Mitglied war. Der Knopf **Mitglied löschen** in der Mitgliederliste
entfernt heute alles. Das ist für Probe- oder Testkonten richtig und für ein ausgeschiedenes
Mitglied mit Anteilen und Zahlungen vermutlich zu viel.

## Rechtslage in Kürze

| Regel | Inhalt | Folge für Tapir |
|---|---|---|
| Art. 5 Abs. 1 lit. e DSGVO | Speicherbegrenzung: Daten nur so lange, wie der Zweck es braucht | Jede Datenart braucht eine Frist |
| Art. 6 Abs. 1 DSGVO | Es braucht eine Rechtsgrundlage: Vertrag (lit. b), rechtliche Pflicht (lit. c), Einwilligung (lit. a) | Pro Datenart festhalten |
| Art. 17 Abs. 1 und 3 DSGVO | Löschung auf Antrag, **außer** bei gesetzlicher Aufbewahrungspflicht (Abs. 3 lit. b) oder zur Verteidigung von Rechtsansprüchen (lit. e) | Aufbewahrte Daten sperren statt löschen |
| Art. 18 DSGVO | Einschränkung der Verarbeitung | Gesperrte Daten dürfen nur noch für den Aufbewahrungszweck genutzt werden |
| Art. 12 Abs. 3 DSGVO | Antwort auf Anträge binnen **eines Monats** | Der Ablauf muss in der Praxis schnell gehen |
| Art. 15 DSGVO | Auskunft: Mitglied bekommt eine Kopie seiner Daten | Braucht dieselbe Datenübersicht wie die Löschung |
| Art. 28 DSGVO | Auftragsverarbeiter (Hosting, Mailversand, Keycloak) brauchen einen Vertrag | siehe „Wo Daten liegen“ |
| Art. 30 DSGVO | Verzeichnis der Verarbeitungstätigkeiten | Diese Seite ist die Vorlage dafür |
| §§ 30, 31 GenG | Die Genossenschaft führt eine **Mitgliederliste** und lässt Mitglieder Einsicht nehmen | Wer wann Mitglied war und mit wie vielen Anteilen, muss auffindbar bleiben |
| § 257 HGB, § 147 AO | Aufbewahrung von Büchern (10 Jahre), Buchungsbelegen (8 Jahre seit 2025, vorher 10) und Geschäftsbriefen (6 Jahre) | Zahlungen, Lastschriften und Anteilsbuchungen gehören dazu |
| § 195 BGB | Regelmäßige Verjährung 3 Jahre | Grund, Vertragsdaten noch eine Zeit zu behalten (Art. 17 Abs. 3 lit. e) |

Die Fristen beginnen mit dem Ende des Kalenderjahres, in dem der Beleg entstanden ist. Die
genaue Zuordnung der Tapir-Daten zu diesen Fristen ist **offen** und Sache der Genossenschaft.

## Wo Daten liegen

Alles stammt aus den Modellen von Tapir (`tapir/*/models.py`). Das **Datenmodell** ist in der
[Datenmodell-Übersicht](Development-Datenmodell) beschrieben.

| Bereich | Modelle | Personenbezogene Daten |
|---|---|---|
| Stammdaten | `TapirUser`, `Member` | Name, E-Mail, zwei Telefonnummern, Geburtsdatum, Adresse, Anrede, Sprache, Pseudonym, Student/in, Mitgliedsnummer |
| Bankdaten | `Member`, `MandateReference` | IBAN, Kontoinhaber, Einwilligungen (SEPA, Widerruf, Datenschutz) mit Zeitstempel |
| Genossenschaft | `CoopShareTransaction` | Anteilskäufe, -kündigungen, -übertragungen an andere Mitglieder |
| Verträge | `Subscription`, `AssociationMembership`, `SolidarityContribution` | Produkt, Laufzeit, Preis, Kündigung, Einwilligungen |
| Zahlungen | `Payment`, `MemberCredit`, `MemberPaymentRhythm`, `PaymentTransaction` | Beträge, Fälligkeiten, SEPA-Dateien (CSV/XML) |
| Lieferung | `MemberPickupLocation`, `Deliveries`, `Joker`, `DeliveryDonation`, `PreferredBread` | Abholort, Lieferhistorie, Joker, Brotwünsche |
| Warteliste | `WaitingListEntry` | **eigene Kopie** von Name, Adresse, Telefon, E-Mail, Wünsche, Kommentar |
| Zusatzadressen | `MemberExtraEmail`, `EmailChangeRequest` | weitere E-Mail-Adressen mit Namen, offene Änderungswünsche |
| Rückmeldungen | `QuestionaireTrafficSourceResponse`, `QuestionaireCancellationReasonResponse`, `OrderFeedback` | Freitext zu Kündigung und Bestellung |
| Protokoll | `LogEntry` und Unterklassen, `EmailLogEntry` | Wer hat wann was geändert, **vollständiger Inhalt versendeter Mails**, alte und neue Feldwerte |
| Exporte | `ExportedFile`, `CsvExport`, `PdfExport` und ihre Ergebnisse | erzeugte Dateien mit Namen und Adressen, Mail-Empfängerlisten |
| Hintergrundjobs | `ScheduledTask` | Argumente geplanter Aufgaben, möglicherweise Mitglieds-IDs |

Außerhalb der Datenbank:

- **Keycloak:** Benutzerkonto mit Name, E-Mail, Passwort-Hash und Ereignissen. Pro Instanz ein Realm
  ([Keycloak und Benutzer](Betrieb-Keycloak)).
- **Mailserver:** Versendete Mails liegen beim Empfänger und im Postausgang des Mailservers.
- **Datensicherung:** [Bareos](Betrieb-Datensicherung) sichert die Datenbank. Gelöschte Daten
  stecken weiter in den Sicherungen, siehe [Datensicherung, Archiv und Restore](#datensicherung-archiv-und-restore).
- **Dateisystem und Logs:** Nginx- und Anwendungslogs mit IP-Adressen und Anmeldenamen.

## Was „Mitglied löschen“ heute tut

Der Knopf ruft `DeleteMemberApiView` (`tapir/coop/views.py`) auf. In einer Transaktion löscht
er für das Mitglied:

- Änderungswünsche der E-Mail-Adresse, **alle Protokolleinträge** (als Akteur und als Betroffene/r)
  und Übertragungs-Protokolle,
- alle **Zahlungen** der Mandate,
- Joker, Abholorte, **Verträge**, **Anteilstransaktionen**, Lieferungen, Wartelisteneinträge,
  Fragebogen-Antworten und Mandate,
- noch nicht versendete Mails an das Mitglied,
- danach das Mitglied selbst und den **Keycloak-Benutzer**.

Das Löschen ist endgültig. Es gibt keine Anonymisierung und keine Sperre.

## Lücken

Aus dem Quelltext abgeleitet, noch nicht an einer laufenden Instanz geprüft:

1. **Zu viel gelöscht:** Zahlungen und Anteilstransaktionen sind Buchungsbelege. Die Mitgliederliste
   nach § 30 GenG braucht Eintritt, Austritt und Anteile. Beides verschwindet.
2. **Zu wenig gelöscht:**
   - `ExportedFile` und die automatischen Export-Ergebnisse (`AutomatedCsvExportResult`,
     `AutomatedPdfExportResult`) bleiben bestehen. Dort stehen Namen und Adressen.
   - Protokolleinträge anderer Personen können Daten des Mitglieds als Text oder in Feldwerten
     enthalten.
   - `ScheduledTask` kann Mitglieds-IDs in den Argumenten tragen.
   - Mitglieder-Daten stecken weiter in Mails, die schon raus sind, und in Datensicherungen
     (siehe nächster Abschnitt).
   - `MemberExtraEmail` und `MemberCredit` hängen am Mitglied, stehen aber nicht in der Liste des
     Löschknopfs. Ob sie über die Datenbank-Kaskade verschwinden, ist zu prüfen.
3. **Keine Auskunft:** Es gibt keine Funktion, die alle Daten eines Mitglieds gesammelt ausgibt
   (Art. 15).
4. **Keine Fristen:** Nichts löscht Daten automatisch, wenn die Aufbewahrungsfrist abläuft,
   zum Beispiel für Wartelisteneinträge, die nie zu einer Mitgliedschaft wurden.
5. **Kein Verzeichnis:** Es gibt kein Verarbeitungsverzeichnis nach Art. 30. Diese Seite liefert
   die Grundlage dafür.

## Offene Fragen

Diese Punkte entscheidet die Genossenschaft, nicht der Code:

- Welche Daten bleiben nach dem Austritt wie lange, und mit welcher Rechtsgrundlage?
- Lösung wie bei SuperCoop Berlin: Alles aus Tapir löschen und die rechtlich nötigen Angaben
  **auf Papier** aufbewahren? Oder Daten in Tapir **sperren oder anonymisieren** und nur die
  nötigen Felder behalten?
- Was geschieht mit Export-Dateien: Sofort löschen, nach Frist löschen oder Namen entfernen?
- Wie lange bleiben Datensicherungen, und wie stellt man nach einer Wiederherstellung sicher, dass
  bereits gelöschte Mitglieder nicht zurückkommen?
- Wer beantwortet Anträge (Art. 12 Abs. 3), und wie wird das protokolliert?

## Datensicherung, Archiv und Restore

Datensicherungen sind Pflicht (Art. 32 DSGVO: Verfügbarkeit und Wiederherstellbarkeit). Sie
widersprechen der Löschpflicht nicht, wenn man sie regelt. Die Regelung besteht aus **zwei
getrennten Sicherungen mit eigenen Jobs und Pools**. Die Einrichtung der Bareos-Jobs steht in
[Datensicherung (Bareos)](Betrieb-Datensicherung).

> **Stand:** Heute sichern `tapir-shared` und `tapir-<name>` im Pool `Tapir` mit dem Zeitplan
> `WeeklyCycle` (Full, Differential, Incremental), `VolumeRetention = 6 months`, `ActionOnPurge = None`.
> Always Incremental ist **nicht** eingerichtet, ein Archiv-Pool gibt es nicht. Die Tabelle
> unten ist ein **Vorschlag**, noch nicht umgesetzt.

| | Betriebs-Backup | Archiv |
|---|---|---|
| Zweck | Wiederherstellung nach Ausfall oder Fehler | gesetzliche Aufbewahrung (Steuer, Buchführung, Mitgliederliste) |
| Inhalt | Datenbank, Keycloak-Realm, Dateien | lesbarer Export der aufbewahrungspflichtigen Daten je Jahr und Mitglied (CSV/JSON/PDF) mit Prüfsummen |
| Schema | Always Incremental, kurze Job-Retention | Jahres-Full, **nicht** konsolidiert |
| Pool | `Tapir` | eigener Pool, zum Beispiel `Tapir-Archiv` |
| Aufbewahrung | Tage bis Wochen | 8 bis 10 Jahre, dann löschen |
| Volumes | `ActionOnPurge = Truncate`, damit gelöschte Daten nicht auf der Platte bleiben | verschlüsselt, getrennt gelagert |
| Zugriff | Betrieb | nur für den Aufbewahrungszweck, mit Protokoll, wer wann extrahiert hat (Art. 18) |
| Löschung in Tapir | bleibt bis zum Consolidate enthalten | enthält die Pflichtdaten, auch wenn sie in Tapir gelöscht sind |

### Was Always Incremental für die Löschung bedeutet

Eine Always-Incremental-Kette hält **alle Stände der Dateien seit dem letzten Full**. Der
Datenbank-Dump liegt immer unter demselben Pfad, jeder Lauf sichert ihn neu. Ein Mitglied, das in
Tapir gelöscht wird, steckt deshalb in allen älteren Dumps der Kette. Erst das Consolidate
schiebt den Stichtag über die Löschung hinaus, sobald ein Lauf älter als die
*Always Incremental Job Retention* ist. Die Aufbewahrung in der Sicherung ist also **Job-Retention
plus Zeit bis zum Consolidate**, begrenzt durch *Always Incremental Max Full Age*. Mit
`ActionOnPurge = None` bleiben die Daten außerdem auf dem Volume, bis es überschrieben wird. Die
genauen Abläufe sollte man an einem Testjob prüfen, bevor man Betroffenen eine Frist nennt.

### Restore ist ein Merge

Ein Restore stellt einen **Stand** wieder her. Das ist bei Tapir nicht genug:

- Der ganze Stand verliert alles, was seitdem passiert ist (neue Mitglieder, Zahlungen).
- Er bringt Mitglieder zurück, die inzwischen gelöscht wurden. Das verletzt Art. 17.
- Einzelne Tabellen zurückzuspielen bricht Fremdschlüssel und Summen.

Gebraucht wird die Wiederherstellung **eines zusammenhängenden Datensatzes** (Mitglied mit allen
abhängigen Daten). Dafür gibt es zwei Wege:

- **Bareos-Plugin** (Python-File-Daemon-Plugin): verworfen. Das Plugin kennt Dateien, keine
  Mitglieder und Fremdschlüssel. Die Fachlogik wäre doppelt und an die Bareos-Version gebunden.
- **Tapir-Befehl und lesbares Archiv** (Vorschlag): ein Befehl in `tapir-instance` schreibt die
  Pflichtdaten als Export, läuft als `RunScript before` des Archiv-Jobs und Bareos archiviert das
  Verzeichnis. Wer Daten für die Finanzverwaltung braucht, holt mit einem normalen Restore nur diese
  Dateien. Zum Wiederherstellen in Tapir selbst fügt ein zweiter Befehl ein Mitglied samt abhängigen
  Datensätzen wieder ein und beachtet dabei das **Löschprotokoll**.

Voraussetzungen:

1. Die Liste der abhängigen Modelle steht an **einer** Stelle und dient Löschung, Auskunft,
   Archiv und Restore. Heute steht sie fest in `DeleteMemberApiView`.
2. Ein **Löschprotokoll ohne Klardaten** (Mitglieds-ID, Zeitpunkt, Art der Löschung). Nach einem Restore werden
   die Löschungen seit dem Stichtag wieder angewendet.
3. Ein Test, der Löschen, Archiv und Restore durchspielt.

### Offene Punkte

- Ob das Archiv die **GoBD** erfüllt (unveränderbar, lesbar, auffindbar, auswertbar), bestätigen
  Steuerberater oder Prüfungsverband.
- Die **Mitgliederliste** (§§ 30, 31 GenG) muss Mitgliedern auf Wunsch zugänglich sein, das geht nicht
  nur aus einem Kaltarchiv. Entweder führt die Genossenschaft sie separat (Papier oder Datei), oder
  Tapir behält ein kleines Feldset (Mitgliedsnummer, Eintritt, Austritt, Anteile, Name).
- Die Mitglieder sind in der Datenschutzerklärung darüber zu informieren, dass Daten bis zum
  Ablauf der Fristen in Sicherung und Archiv liegen.

## Vorschlag für die Umsetzung

1. **Datenübersicht festschreiben:** Pro Modell und Feld Zweck, Rechtsgrundlage, Frist und
   Löschverhalten. Das ist die Tabelle oben, ergänzt um die Entscheidungen der Genossenschaft.
2. **Löschen bleibt vollständig**, solange die Pflichtdaten vorher im Archiv liegen (siehe oben).
   Der Löschknopf prüft, dass der Archivlauf nach der letzten Buchung gelaufen ist.
3. **Archiv und Restore** wie im Abschnitt davor, als eigene Jobs in eigenen Pools.
4. **Auskunft** aus derselben Datenübersicht erzeugen.
5. **Fristen** per Hintergrundjob umsetzen ([Hintergrundjobs](Development-Hintergrundjobs)).
6. **Exporte und Protokolle** einbeziehen.

Die Datenübersicht lässt sich als Hilfsmittel nutzen, damit neue Modelle nicht vergessen werden:
Ein Test könnte fehlschlagen, wenn ein Modell mit Bezug zu `Member` nicht in der Löschlogik oder in
der Datenübersicht vorkommt.

## Verwandte Seiten

- [Datenmodell](Development-Datenmodell), [Protokoll](Development-Datenmodell-Protokoll),
  [Exporte](Development-Datenmodell-Exporte)
- [Keycloak und Benutzer](Betrieb-Keycloak), [Datensicherung (Bareos)](Betrieb-Datensicherung)
- [Mitglieder verwalten](Handbuch-Verwaltung-Mitglieder)
