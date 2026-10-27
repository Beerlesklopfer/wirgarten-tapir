> ⚠️ **Nicht maßgeblich.** Dieses Wiki gehört zu einem abgeschlossenen Proof of Concept für den
> Eigenbetrieb von Tapir und wird nicht gepflegt. Maßgeblich ist die Dokumentation im
> Hauptprojekt: [FoodCoopX/wirgarten-tapir – docs](https://github.com/FoodCoopX/wirgarten-tapir/tree/master/docs),
> Aufbau in Issue [#1300](https://github.com/FoodCoopX/wirgarten-tapir/issues/1300).

# Verwaltung: Verträge

> **Kurz gesagt:** Neue Bestellungen und Kündigungen landen in **Zeichn. und Künd.**. Dort
> bestätigen Sie sie mit **Auswahl bestätigen** – das Mitglied bekommt eine Mail. Was Sie nicht
> bis zur Frist vor der ersten Lieferung bestätigen, bestätigt Tapir um 9:30 Uhr automatisch.
> In **Verträge** passen Sie einzelne Verträge an: Sonderkündigung, Probezeit, Preis.

## Zeichnungen und Kündigungen bestätigen

![Zeichnungen und Kündigungen](images/verwaltung-zeichnungen-kuendigungen.png)

```mermaid
flowchart TD
    N["Neue Bestellung<br>(Wizard, Mitgliederbereich, Warteliste)"] --> L["Zeichn. und Künd.<br>Zähler im Menü"]
    L --> C{"Prüfen"}
    C -->|in Ordnung| B["Zeilen anhaken →<br>Auswahl bestätigen (n)"]
    B --> M1["Mail: Bestellung vom Admin bestätigt"]
    C -->|nicht möglich| W["Auswahl widerrufen"]
    W --> W1["Widerrufen<br>Mail an Mitglied, Verträge und Anteile gelöscht"]
    W --> W2["Auf Warteliste verschieben<br>keine Mail, Wartelisteneintrag"]
    L -->|Frist läuft ab| A["9:30 Uhr automatische Bestätigung<br>(gelb markiert)"]
```

- Filter: **Alles Anzeigen**, **Nur Zeichnungen anzeigen**, **Nur Kündigungen Anzeigen**.
- Spalten: Mitglied, Verteilort, Änderungen (Zeichnung, Kündigung, Produktwechsel alt → neu,
  Anteile „gültig am“), Gültig ab.
- Widerrufen geht nur für künftige Zeichnungen; Kündigungen lassen sich nicht widerrufen.

## Vertragsliste

![Vertragsliste](images/verwaltung-vertraege.png)

**Filter:** Vertragsperiode, Mitglied, Abholort, Vertragsart, Variante, Mitgliedschafts-Typ,
dazu „Nur Verträge in der Probezeit“, „Nur beitragsbefreite Verträge“, „Innerhalb der
Vertragsperiode beendete Verträge“, „manuell geänderte Probezeit“.

**Symbole:** gekündigt, Probezeit, Probezeit manuell deaktiviert, Laufzeitende, Betrag
„Manuell editiert!“.

| Knopf (Vertrag auswählen) | Wofür | Achtung |
|---|---|---|
| **Vertragsstart-anpassen/Sonderkündigung** | Kulanz, Umzug, Härtefall | Neues Ende muss ein Sonntag sein; spätere Verträge und Solidarbeiträge werden angepasst bzw. gelöscht; ggf. Gutschriften; **keine** automatische Mail an das Mitglied |
| **Probezeit aktivieren/deaktivieren** | Keine Probezeit oder eigenes Probezeit-Ende (Sonntag) | |
| **Betrag ändern** | Standardbetrag, personalisierter Betrag oder beitragsbefreit | |
| **Gefilterte Liste exportieren** | CSV | |

## Lebenslauf eines Vertrags

```mermaid
stateDiagram-v2
    [*] --> Unbestaetigt: Bestellung
    Unbestaetigt --> Bestaetigt: Admin oder 9.30 Uhr automatisch
    Unbestaetigt --> Widerrufen: Admin
    Bestaetigt --> Probezeit
    Probezeit --> Laufend
    Laufend --> Gekuendigt: Mitglied oder Admin
    Laufend --> Verlaengert: 2 Uhr automatisch<br>(wenn eingeschaltet)
    Gekuendigt --> [*]
    Widerrufen --> [*]
```
