> ⚠️ **Nicht maßgeblich.** Dieses Wiki gehört zu einem abgeschlossenen Proof of Concept für den
> Eigenbetrieb von Tapir und wird nicht gepflegt. Maßgeblich ist die Dokumentation im
> Hauptprojekt: [FoodCoopX/wirgarten-tapir – docs](https://github.com/FoodCoopX/wirgarten-tapir/tree/master/docs),
> Aufbau in Issue [#1300](https://github.com/FoodCoopX/wirgarten-tapir/issues/1300).

# Fachliche Abläufe

> **Abstract:** Ein Interessent meldet sich über den Bestell-Wizard an. Daraus entstehen in
> einer Transaktion Mitglied, Keycloak-Konto, Verträge, Depot-Zuordnung, Genossenschaftsanteile
> bzw. Vereinsmitgliedschaft und Solidarbeitrag. Ab dann arbeiten nächtliche Celery-Jobs:
> Bestätigung nach Fristablauf, monatliche Zahlungen mit SEPA-Export, Kommissionierlisten vor
> jeder Lieferung und automatische Verlängerung in die nächste Anbauperiode. Fast jede Regel
> (Probezeit, Fristen, Joker, Zyklen) ist per Parameter einstellbar und hängt an „heute“ –
> deshalb immer `get_today(cache)` verwenden.

## Anmeldung über den Bestell-Wizard

```mermaid
sequenceDiagram
    autonumber
    actor I as Interessent
    participant W as Bestell-Wizard (React)
    participant API as BestellWizardConfirmOrderApiView
    participant F as BestellWizardOrderFulfiller
    participant KC as Keycloak
    participant M as tapir_mail
    I->>W: Produkte, Depot, Anteile, Bankdaten
    W->>API: POST (transaction.atomic)
    API->>API: OrderValidator, Kapazitäten prüfen
    alt Bestellung oder „jetzt Mitglied werden“
        API->>F: create_member_and_fulfill_order
        F->>F: erstes Depot mit freier Kapazität wählen
        F->>F: Member anlegen, Mitgliedsnummer
        F->>KC: Benutzer anlegen, Verifizierungsmail
        F->>F: Zahlungsrhythmus zuweisen
        F->>F: ApplyTapirOrderManager: Verträge
        F->>F: MemberPickupLocationSetter: Depot
        F->>F: Genossenschaftsanteile oder Vereinsmitgliedschaft
        F->>F: Solidarbeitrag, Fragebogen
        F->>M: Bestätigungsmail (Trigger)
    end
    opt Wunsch nicht erfüllbar
        API->>API: Wartelisteneintrag anlegen
    end
    API-->>W: OK
```

Wichtige Klassen: `tapir/bestell_wizard/views.py` (`BestellWizardConfirmOrderApiView`),
`tapir/bestell_wizard/services/bestell_wizard_order_fulfiller.py`,
`tapir/subscriptions/services/apply_tapir_order_manager.py`.

## Lebenszyklus eines Vertrags

```mermaid
stateDiagram-v2
    [*] --> Bestellt: ApplyTapirOrderManager
    Bestellt --> Probezeit: Start (nächster Montag nach Änderungsfrist)
    Bestellt --> Bestaetigt: Admin bestätigt / automatische Bestätigung um 9.30 Uhr
    Probezeit --> Bestaetigt
    Probezeit --> Gekuendigt: Kündigung in Probezeit (sofort zum Probezeitende)
    Bestaetigt --> Laufend
    Laufend --> Gekuendigt: Kündigung vor Ablauf der Kündigungsfrist
    Laufend --> Verlaengert: AutomaticSubscriptionRenewalService um 2 Uhr
    Verlaengert --> Laufend: neuer Vertrag in der nächsten Anbauperiode
    Gekuendigt --> Beendet: end_date erreicht
    Laufend --> Beendet: Periodenende ohne Verlängerung
    Beendet --> [*]
```

| Schritt | Logik | Ort |
|---|---|---|
| Startdatum | nächster Montag, dessen Lieferänderungs-Frist minus Puffer noch nicht vorbei ist | `ContractStartDateCalculator` |
| Probezeit | Start + `TRIAL_PERIOD_DURATION` Wochen − 1 Tag, oder Override am Vertrag; bei gelieferten Produkten ab Montag der ersten Lieferwoche | `TrialPeriodManager` |
| Kündigung | in der Probezeit zum Probezeitende, sonst nur bei aktiver Verlängerung; künftige Verträge werden gelöscht, laufende bekommen `cancellation_ts` und gekürztes `end_date` | `SubscriptionCancellationManager` |
| Kündigungsfrist | `end_date` minus N Wochen/Monate je Produktart und Periode (`NoticePeriod`) | `NoticePeriodManager` |
| Verlängerung | Parameter an, nicht gekündigt, Folgeperiode existiert, Frist abgelaufen, Produkt nicht gelöscht, Kapazität frei | `AutomaticSubscriptionRenewalService` |
| Bestätigung | automatisch nach Ablauf der Änderungsfrist, mit Mail | `AutomaticConfirmationManager` |

Prognosen (z. B. Bedarf der Anbau-App, Kapazitätsplanung) arbeiten mit „virtuellen“, noch nicht
gespeicherten Verlängerungen: `AutomaticSubscriptionRenewalService.get_subscriptions_and_renewals`.

## Lieferungen, Zyklen und Joker

```mermaid
flowchart TD
    W[Kalenderwoche] --> Z{Lieferzyklus der Produktart}
    Z -->|weekly| P
    Z -->|odd_weeks / even_weeks| G{ISO-Woche passt?}
    Z -->|every_four_weeks| V{Abstand zum Startpunkt durch 4 teilbar?}
    Z -->|custom| C{CustomCycleScheduledDeliveryWeek vorhanden?}
    Z -->|no_delivery| N[keine Lieferung]
    G -->|ja| P
    V -->|ja| P
    C -->|ja| P
    G & V & C -->|nein| N
    P{Woche in weeks_without_delivery der Anbauperiode?} -->|ja| N
    P -->|nein| J{Joker des Mitglieds in dieser Woche<br>und Produktart joker-fähig?}
    J -->|ja| N2[keine Lieferung, Gutschrift nach Frist]
    J -->|nein| D{Lieferung gespendet?}
    D -->|ja| S[geht an das im Parameter gewählte Depot<br>oder entfällt]
    D -->|nein| L[Lieferung ans Depot des Mitglieds<br>Liefertag ggf. per DeliveryDayAdjustment verschoben]
```

- Liefertermine: `DeliveryDateCalculator`, `DeliveryCycleService`, `WeeksWithoutDeliveryService`.
- Joker-Regeln: `JokerManagementService.can_joker_be_used_in_week` (Jokers an, max. je Periode,
  Einschränkungen, Frist, keine Spende in derselben Woche).
- Gutschrift für Joker: `JokerCreditCreator` (täglich 06:00) erzeugt `payments.MemberCredit`.
- Kommissionierliste: `PickListBuilder`; CSV-Export am Tag nach der Depot-Änderungsfrist.

## Depot und Kapazität

```mermaid
flowchart LR
    Sub[Subscription<br>Menge × ProductPrice.size] -->|M-Äquivalente| PT[Kapazität der Produktart<br>ProductCapacity je Periode]
    Sub --> Dep[Kapazität des Depots<br>PickupLocationCapability]
    WL[Reservierungen der Warteliste] --> Dep
    WL --> PT
    Dep -->|voll| Warteliste
    PT -->|voll| Warteliste
```

- Die Depot-Zuordnung ist zeitlich versioniert (`MemberPickupLocation.valid_from`); lesen mit
  `MemberPickupLocationGetter`, schreiben nur über `MemberPickupLocationSetter`.
- Kommissioniermodus (`PICKING_MODE`): nach Anteilen (M-Äquivalente) oder nach Kisten
  (`ProductBasketSizeEquivalence`, `PickupLocationBasketCapacity`).

## Zahlungen

```mermaid
flowchart LR
    subgraph täglich 23:59
        B[MonthPaymentBuilder] -->|Verträge, Solidarbeiträge,<br>Vereinsbeiträge, Liefergebühren| Pay[(Payment<br>Status DUE)]
    end
    subgraph Anteilskauf
        CS[CoopSharePurchaseHandler] --> Pay
    end
    subgraph täglich 05:00
        Pay --> E[PaymentExportBuilder]
        E --> CSV[CSV]
        E --> XML[SEPA pain.008 XML]
        E --> T[(PaymentTransaction)]
    end
    T -.->|verknüpfte Zahlungen sind eingefroren| Pay
    Credit[(MemberCredit<br>Joker, Gebührenerstattung)] --> B
```

- Abgerechnet wird je Mitglied × Produktart im Zahlungsrhythmus des Mitglieds
  (`MemberPaymentRhythm`: monatlich bis jährlich).
- Verträge in der Probezeit werden nachträglich für den Vormonat abgerechnet.
- Jede Lastschrift braucht ein `MandateReference` (SEPA-Mandat).
- Künftige Zahlungen neu berechnen: `SubscriptionPaymentsRebuilder`.

## Genossenschaftsanteile

| Buchungstyp | Wirkung |
|---|---|
| `PURCHASE` | Zeichnung, positiv; erzeugt Zahlung über `CoopSharePurchaseHandler` |
| `CANCELLATION` | Kündigung, negativ |
| `TRANSFER_OUT` / `TRANSFER_IN` | Übertragung zwischen Mitgliedern |

Bestand = Summe der Mengen mit `valid_at <= heute`. Ob Anteile oder Vereinsmitgliedschaften
gelten, entscheidet die Rechtsform der Instanz (`legal_status_is_cooperative()` u. a. in
`tapir/wirgarten/utils.py`).

## Warteliste

```mermaid
sequenceDiagram
    actor I as Interessent / Mitglied
    actor A as Admin
    participant T as Tapir
    I->>T: Wunsch (Produkte, Depots) ohne freie Kapazität
    T->>T: WaitingListEntry + Wünsche, reserviert Kapazität
    A->>T: Platz frei → Bestätigungslink senden
    T->>I: Mail mit confirmation_link_key
    I->>T: bestätigt
    T->>T: WaitingListEntryConfirmationApplier: Mitglied, Verträge, Depot
```

## Wo die Zeit herkommt

Alle Abläufe hängen am Stichtag. `get_today(cache)` und `get_now(cache)` (Europe/Berlin) aus
`tapir/wirgarten/utils.py` sind Pflicht. Auf Debug-Instanzen lässt sich die Zeit über den
Parameter `TESTS_OVERRIDE_DATE_PRESET` verstellen; in Tests gibt es `mock_timezone`.
