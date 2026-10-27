> ⚠️ **Nicht maßgeblich.** Dieses Wiki gehört zu einem abgeschlossenen Proof of Concept für den
> Eigenbetrieb von Tapir und wird nicht gepflegt. Maßgeblich ist die Dokumentation im
> Hauptprojekt: [FoodCoopX/wirgarten-tapir – docs](https://github.com/FoodCoopX/wirgarten-tapir/tree/master/docs),
> Aufbau in Issue [#1300](https://github.com/FoodCoopX/wirgarten-tapir/issues/1300).

<!-- Generiert mit `python manage.py generate_datamodel_docs`. Nicht von Hand bearbeiten, Beschreibungen stehen in tapir/core/services/data_model_docs_descriptions.py -->
# Datenmodell: Genossenschaft (`tapir.coop`)

← [Datenmodell-Übersicht](Development-Datenmodell)

> **Abstract:** Protokolleinträge rund um Genossenschaftsanteile (Zeichnung, Kündigung, Widerruf). Die Anteilsbuchungen selbst liegen in `wirgarten.CoopShareTransaction`.

0 Modelle, 4 Protokolleinträge.

## Protokolleinträge

Alle erben von [log.LogEntry](Development-Datenmodell-Protokoll#logentry) und speichern nur ihre zusätzlichen Felder in einer eigenen Tabelle.

### CoopSharesCancelledDuringTrialLogEntry

**coop shares cancelled during trial log entry**

- Tabelle: `coop_coopsharescancelledduringtriallogentry`
- Erbt von `log.LogEntry` (Multi-Table-Inheritance, eigene Tabelle mit 1:1-Verweis)

| Feld | Typ | Schlüssel | Pflicht | Default | Beschreibung | Beziehung |
|---|---|---|---|---|---|---|
| `nb_shares` | IntegerField |  | ja |  |  |  |
| `shares_would_have_been_valid_at` | DateField |  | ja |  |  |  |

### CoopSharesCancelledLogEntry

**coop shares cancelled log entry**

- Tabelle: `coop_coopsharescancelledlogentry`
- Erbt von `log.LogEntry` (Multi-Table-Inheritance, eigene Tabelle mit 1:1-Verweis)

| Feld | Typ | Schlüssel | Pflicht | Default | Beschreibung | Beziehung |
|---|---|---|---|---|---|---|
| `nb_shares` | IntegerField |  | ja |  |  |  |
| `cancellation_valid_at` | DateField |  | ja |  |  |  |

### CoopSharesPurchasedLogEntry

**coop shares purchased log entry**

- Tabelle: `coop_coopsharespurchasedlogentry`
- Erbt von `log.LogEntry` (Multi-Table-Inheritance, eigene Tabelle mit 1:1-Verweis)

| Feld | Typ | Schlüssel | Pflicht | Default | Beschreibung | Beziehung |
|---|---|---|---|---|---|---|
| `coop_share_transaction` | CharField(1024) |  | ja |  |  |  |

### CoopSharesRevokedLogEntry

**coop shares revoked log entry**

- Tabelle: `coop_coopsharesrevokedlogentry`
- Erbt von `log.LogEntry` (Multi-Table-Inheritance, eigene Tabelle mit 1:1-Verweis)

| Feld | Typ | Schlüssel | Pflicht | Default | Beschreibung | Beziehung |
|---|---|---|---|---|---|---|
| `coop_share_transactions` | CharField(1024) |  | ja |  |  |  |
