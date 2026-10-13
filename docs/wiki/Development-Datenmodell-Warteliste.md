<!-- Generiert mit `python manage.py generate_datamodel_docs`. Nicht von Hand bearbeiten, Beschreibungen stehen in tapir/core/services/data_model_docs_descriptions.py -->
# Datenmodell: Warteliste (`tapir.waiting_list`)

← [Datenmodell-Übersicht](Development-Datenmodell)

> **Abstract:** Protokolleinträge für bestätigte Wechsel von der Warteliste. Die Wartelisteneinträge liegen in `wirgarten.WaitingListEntry`.

0 Modelle, 1 Protokolleinträge.

## Protokolleinträge

Alle erben von [log.LogEntry](Development-Datenmodell-Protokoll#logentry) und speichern nur ihre zusätzlichen Felder in einer eigenen Tabelle.

### WaitingListChangeConfirmedLogEntry

**waiting list change confirmed log entry**

This log entry is created whenever a user uses a confirmation link they received per mail, coming from a waiting list entry

- Tabelle: `waiting_list_waitinglistchangeconfirmedlogentry`
- Erbt von `log.LogEntry` (Multi-Table-Inheritance, eigene Tabelle mit 1:1-Verweis)

| Feld | Typ | Schlüssel | Pflicht | Default | Beschreibung | Beziehung |
|---|---|---|---|---|---|---|
