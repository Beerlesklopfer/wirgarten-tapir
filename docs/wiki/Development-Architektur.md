# Architektur

> **Abstract:** Ein klassischer Django-Monolith in Schichten: Templates und React-Seiten oben,
> darunter Django-Views und DRF-APIs, die Geschäftslogik in zustandslosen Service-Klassen und
> ganz unten die Modelle in PostgreSQL. Zeitgesteuerte Arbeit (Zahlungen, Verlängerungen,
> Exporte, Mails) erledigt Celery. Fachlich ist der Code in Django-Apps geschnitten; die
> historische App `wirgarten` hält noch die meisten Kernmodelle und gilt als Legacy, neue Logik
> entsteht in den Fach-Apps.

## Laufzeit-Komponenten

```mermaid
flowchart TB
    Browser[Browser] -->|HTTPS| Proxy[nginx / caddy]
    Proxy --> Gunicorn[Gunicorn: tapir.wsgi]
    Gunicorn --> Django[Django]
    Django --> PG[(PostgreSQL)]
    Django --> Redis[(Redis: Cache + Broker)]
    Django -->|Admin-API: Benutzer, Rollen| KC[Keycloak]
    Browser -->|Login OIDC| KC
    Beat[celery beat] -->|Zeitplan| Redis
    Redis --> Worker[celery worker]
    Worker --> PG
    Worker -->|SMTP| SMTP[Mailserver]
    Worker -->|IMAP Bounces| SMTP
```

Im Debian-Paket sind das drei systemd-Dienste (`tapir-web`, `tapir-celery`,
`tapir-celery-beat`) unter `tapir.target`, in Docker die Services `web`, `celery`,
`celery-beat`, dazu `db`, `redis`, `keycloak` und `vite` (siehe
[Entwicklungsumgebung](Development-Entwicklungsumgebung)).

## Schichten

```mermaid
flowchart TB
    subgraph UI[Darstellung]
        T[Django-Templates<br>core/base.html, Sidebar, App-Umschalter]
        R[React/TS-Seiten<br>src_frontend, django-vite]
    end
    subgraph Web[Web-Schicht]
        V[Template-Views<br>views_templates.py]
        A[DRF-Views / ViewSets<br>views.py, viewsets.py, serializers.py]
    end
    subgraph Logik[Geschäftslogik]
        S[Service-Klassen<br>tapir/&lt;app&gt;/services/]
        C[TapirCache<br>Request-Cache dict]
        P[Parameter<br>get_parameter_value]
    end
    subgraph Daten[Persistenz]
        M[Django-Modelle<br>TapirModel]
        L[LogEntry-Protokoll]
    end
    T --> V
    R -->|generierter API-Client| A
    V --> S
    A --> S
    Tasks[Celery-Tasks<br>tasks.py] --> S
    S --> C
    S --> P
    S --> M
    S --> L
```

Regeln:

- Views sind dünn: sie prüfen Rechte, lesen Eingaben und rufen Services auf.
- Services sind Klassen mit `@classmethod`/`@staticmethod`, ohne Zustand; fast jede Methode
  bekommt einen `cache: dict` (siehe [Konventionen](Development-Konventionen)).
- Modelle enthalten nur ihre Felder und kleine Helfer, die nur die eigenen Felder benutzen.
- Jede fachliche Änderung an einem Mitglied schreibt einen Protokolleintrag (`LogEntry`).

## Lebensweg eines Requests

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser (React)
    participant D as Django / DRF
    participant K as Keycloak
    participant S as Service
    participant DB as PostgreSQL
    B->>D: GET /farming/api/demand/?start_date=… (Session-Cookie, X-CSRFToken)
    D->>D: Authentifizierung (Session / Token)
    D->>K: Realm-Rollen des Nutzers (einmal je Request, gecacht am User)
    K-->>D: [farming.view, …]
    D->>D: Permission-Klassen (Flag an? Rolle vorhanden?)
    D->>S: ShareDemandService.get_demand(…, cache={})
    S->>DB: Bulk-Abfragen über TapirCache
    DB-->>S: Zeilen
    S-->>D: Dataclasses
    D-->>B: JSON (Serializer)
```

## Apps

```mermaid
flowchart LR
    subgraph Kern
        wirgarten[wirgarten<br>Legacy-Kern]
        accounts[accounts]
        configuration[configuration]
        log[log]
        core[core]
        utils[utils]
    end
    subgraph Fach[Fach-Apps]
        subscriptions & coop & deliveries & pickup_locations & payments
        solidarity_contribution & waiting_list & associations & products
        bestell_wizard & generic_exports
    end
    subgraph Module[Optionale Module]
        bakery[bakery<br>Bäckerei]
        farming[farming<br>Anbau]
    end
    Fach --> Kern
    Module --> Kern
    Module --> Fach
    tapir_mail[(tapir_mail<br>externes Paket)] --- wirgarten
```

| App | Aufgabe |
|---|---|
| `wirgarten` | Legacy-Kern: fast alle Kernmodelle, alte Funktions-Services in `service/`, Formulare und Views |
| `accounts` | `TapirUser`, Keycloak-Anbindung, E-Mail-Änderung |
| `core` | `TapirModel`, Sidebar, App-Umschalter, Themes, Basis-Templates |
| `configuration` | Parameter-Modell, Konfigurationsseite |
| `log` | Protokolleinträge |
| `utils` | `TapirCache`, `TapirCacheManager`, Shortcuts, Import |
| `subscriptions` | Bestellungen anwenden, Probezeit, Kündigung, Verlängerung, Bestätigung |
| `coop` | Genossenschaftsanteile, Mitgliedsnummern, Austritt |
| `deliveries` | Lieferzyklen, Liefertermine, Joker, Spenden, Kommissionierliste |
| `pickup_locations` | Depot-Zuordnung, Kapazitäten, Liefergebühren |
| `payments` | Monatliche Zahlungen, SEPA-Export, Zahlungsrhythmus, Gutschriften |
| `solidarity_contribution` | Solidarbeiträge |
| `waiting_list` | Warteliste und Bestätigungsablauf |
| `associations` | Vereinsmitgliedschaften |
| `products` | Produktänderungen, Steuersätze (nur Services) |
| `bestell_wizard` | Öffentlicher Anmelde-Assistent |
| `generic_exports` | Konfigurierbare CSV/PDF-Exporte |
| `bakery` | Modul Brotanteile mit Backplan-Solver (OR-Tools) |
| `farming` | Modul Anbauplanung, siehe [Anbau-App](Development-Anbau-App) |

## URL-Struktur

| Präfix | Inhalt |
|---|---|
| `/` | Weiterleitung je nach Rolle (Mitgliederbereich oder Admin-Dashboard) |
| `/accounts/` | Login (leitet auf `/accounts/oidc/keycloak/login`), Logout |
| `/tapir/` | Legacy-Views aus `wirgarten` |
| `/tapirmail/`, `/mailing/` | Mail-Oberfläche aus `tapir_mail` |
| `/config/` | Konfigurationsseite |
| `/<app>/` | Jede Fach-App hat ihren eigenen Präfix (`/subscriptions/`, `/bakery/`, `/farming/` …) |

Ein Schema- oder Swagger-Endpunkt ist nicht veröffentlicht; das OpenAPI-Schema wird offline als
`schema.yml` erzeugt (siehe [Frontend](Development-Frontend)).

## Legacy und Weiterentwicklung

Alles unter `tapir/wirgarten` folgt nicht den heutigen Konventionen. Wer dort etwas ändert,
schreibt den betroffenen Teil möglichst neu und zieht ihn in eine Fach-App. Die Modelle bleiben
vorerst in `wirgarten`, weil Migrationen über App-Grenzen aufwendig sind.
