<!-- Generiert mit `python manage.py generate_datamodel_docs`. Nicht von Hand bearbeiten, Beschreibungen stehen in tapir/core/services/data_model_docs_descriptions.py -->
# Datenmodell: Werkzeuge (`tapir.utils`)

← [Datenmodell-Übersicht](Development-Datenmodell)

> **Abstract:** Hilfsfunktionen; im Datenmodell nur der Protokolleintrag für importierte Mitglieder.

0 Modelle, 1 Protokolleinträge.

## Protokolleinträge

Alle erben von [log.LogEntry](Development-Datenmodell-Protokoll#logentry) und speichern nur ihre zusätzlichen Felder in einer eigenen Tabelle.

### MemberImportedLogEntry

**member imported log entry**

- Tabelle: `utils_memberimportedlogentry`
- Erbt von `log.LogEntry` (Multi-Table-Inheritance, eigene Tabelle mit 1:1-Verweis)

| Feld | Typ | Schlüssel | Pflicht | Default | Beschreibung | Beziehung |
|---|---|---|---|---|---|---|
| `values` | HStoreField |  | ja |  |  |  |
