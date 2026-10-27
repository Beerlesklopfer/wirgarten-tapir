> ⚠️ **Nicht maßgeblich.** Dieses Wiki gehört zu einem abgeschlossenen Proof of Concept für den
> Eigenbetrieb von Tapir und wird nicht gepflegt. Maßgeblich ist die Dokumentation im
> Hauptprojekt: [FoodCoopX/wirgarten-tapir – docs](https://github.com/FoodCoopX/wirgarten-tapir/tree/master/docs),
> Aufbau in Issue [#1300](https://github.com/FoodCoopX/wirgarten-tapir/issues/1300).

# Paketierung und Betrieb

> **Abstract:** Im Betrieb läuft jede Tapir-Instanz (eine pro Solawi) als podman-Container unter
> systemd: Web (gunicorn), Celery-Worker und Celery-Beat aus dem Produktions-Image
> `ghcr.io/beerlesklopfer/wirgarten-tapir`. Ein gemeinsamer Keycloak-Container bedient alle
> Instanzen mit je einem eigenen Realm, ein gemeinsamer Redis-Container hält Warteschlangen und
> Caches aller Instanzen, jede in einer eigenen Datenbanknummer; PostgreSQL und nginx laufen auf dem Host. Das Debian-Paket
> `tapir` (`Architecture: all`, rund 400 KB) bringt nur die Werkzeuge `tapir-instance`,
> `tapir-kcadm` und `tapir-manage` sowie Vorlagen mit. Ein GitHub-Workflow baut bei Tags Image und
> Paket und veröffentlicht ein signiertes APT-Repository auf GitHub Pages.

## Aufbau auf dem Server

```mermaid
flowchart LR
    B["Browser"] --> N["nginx (Host)<br>sites-available/tapir-NAME"]
    N -->|"/"| W["tapir-NAME-web<br>gunicorn 127.0.0.1:PORT"]
    N -->|"/realms/ und /resources/"| K["tapir-keycloak<br>127.0.0.1:8800<br>ein Realm je Instanz"]
    W --- WB["tapir-NAME-worker<br>tapir-NAME-beat"]
    WB --- R["tapir-redis<br>127.0.0.1:6380<br>Datenbank je Instanz"]
    W --> P[("PostgreSQL (Host)<br>tapir_NAME, keycloak")]
    K --> P
    W -->|"Admin-API, Service-Account"| K
```

- Alle Container nutzen das Host-Netz und lauschen nur auf `127.0.0.1`.
- **Ein Keycloak für alle Domains:** Keycloak hat keinen globalen Hostnamen
  (`KC_HOSTNAME_STRICT=false`); jeder Realm setzt seine Domain über `frontendUrl`. Damit lautet der
  Aussteller (issuer) je Instanz `https://<domain>/realms/<realm>`.
- Schreibbare Daten liegen in `/var/lib/tapir/<name>` und sind im Container unter `/data`
  eingebunden: Medien, Uploads, Mail-Ablage, Fehlerprotokolle, Beat-Zeitplan. Die Container laufen
  als UID 10100.

## Produktions-Image

`docker/production/Containerfile` baut in drei Stufen:

1. **frontend:** `node:24-slim`, `pnpm run build` → `dist/`
2. **build:** `python:3.14-slim-trixie`, Abhängigkeiten aus `poetry.lock` mit uv (gehasht),
   `compilemessages`, `collectstatic`
3. **Laufzeit:** schlankes Python mit mjml und den Bibliotheken für weasyprint

Der Einstiegspunkt kennt die Rollen `web`, `worker`, `beat`, `migrate`, `manage <args>`. Die
Konfiguration kommt ausschließlich aus Umgebungsvariablen, also aus der env-Datei der Instanz.

## Lebenszyklus einer Instanz

```mermaid
flowchart TD
    C["tapir-instance create NAME --domain HOST --port PORT"] --> DB["PostgreSQL-Rolle und -Datenbank tapir_NAME"]
    DB --> KC["Keycloak-Container sicherstellen<br>Realm NAME mit Client-Secret, frontendUrl, Mailserver"]
    KC --> M["Image ziehen, migrate und parameter_definitions"]
    M --> U["Quadlet-Units schreiben, tapir-NAME.target starten"]
    U --> A["erster Admin (Tapir-Benutzer und Keycloak-Login)"]
    A --> NG["nginx-Site nach sites-available<br>aktive Site der Domain ergänzen"]
    NG --> CH["Prüfungen: Units, Tapir, Aussteller, Admin-API, nginx"]
    CH --> UP["tapir-instance upgrade NAME oder --all"]
    UP --> M
```

Vollständige Befehlsreferenz für den Betrieb: [tapir-instance](Betrieb-tapir-instance).

| Befehl | Zweck |
|---|---|
| `tapir-instance create` | neue Instanz, wiederholbar ohne doppelte Anlagen |
| `tapir-instance adopt <name>` | Installation des früheren nativen Pakets übernehmen (Datenbank, Dateien, Port bleiben) |
| `tapir-instance list`, `status` | Übersicht, Prüfungen |
| `tapir-instance upgrade <name>\|--all [--image]` | Image ziehen, migrieren, neu starten, prüfen |
| `tapir-instance user-add <name> <mail> [--admin]` | Tapir-Benutzer mit Keycloak-Login |
| `tapir-instance nginx <name>` | Site neu schreiben, z. B. HTTPS nach dem Zertifikat |
| `tapir-instance keycloak <name>` | Realm, Mailserver, Themes, Units und nginx auffrischen |
| `tapir-instance theme <name> <theme>` | Theme von Tapir und Keycloak |
| `tapir-instance param <name> [<key> [<value>]]` | in der Oberfläche gesperrte Parameter setzen |
| `tapir-instance remove <name> [--purge]` | entfernen, mit `--purge` auch Datenbank, Realm und Daten |
| `tapir-manage <name> <args>` | `manage.py` im laufenden Web-Container |
| `tapir-kcadm --realm <realm> …` | Keycloak auf der Kommandozeile, Realm immer ausdrücklich; nur root (`rwxrwx---`) |

## Debian-Paket und Installation

```mermaid
sequenceDiagram
    actor A as Admin
    participant APT as apt
    participant D as debconf
    participant T as tapir-instance
    A->>APT: apt install tapir postgresql nginx
    APT->>D: Name, Domain, Port, erster Admin, Image
    alt frühere native Installation vorhanden
        D->>T: adopt NAME --domain HOST
    else Neuinstallation
        D->>T: create NAME --domain HOST --port PORT
    end
    T-->>A: Prüfungen ok, Site in sites-available
    A->>A: Site aktivieren, certbot, tapir-instance nginx NAME
```

- `apt upgrade` aktualisiert nur die Werkzeuge. Instanzen werden ausdrücklich mit
  `tapir-instance upgrade` aktualisiert.
- Die nginx-Site wird nie automatisch aktiviert. Eine schon aktive Site der Domain bekommt die
  Keycloak-Pfade per `include` (mit Sicherung, `nginx -t` und Rücksicherung bei Fehler).
- **Testbarkeit:** Alle Pfade und Systembefehle in `tapir-instance` lassen sich per Umgebungsvariable
  umbiegen (`TAPIR_ETC`, `TAPIR_LIB`, `QUADLET_DIR`, `SYSTEMCTL`, `PSQL_ADMIN`, …). So läuft der
  komplette Ablauf auch rootless mit systemd-Benutzerdiensten. Container mit systemd und podman
  darin bitte nicht verschachteln: Das hat einen Entwicklungsrechner zum Stehen gebracht.

## Bau und Veröffentlichung

```mermaid
flowchart LR
    Tag["Tag v* oder manuell"] --> I["Image bauen<br>docker/production/Containerfile"]
    I --> G[("ghcr.io<br>Version, latest, edge, sha")]
    I --> D["packaging/build-deb.sh<br>tapir_VERSION_all.deb"]
    D --> R["GitHub-Release deb-VERSION"]
    R --> S["build-apt-repo.sh<br>signiert mit APT_GPG_PRIVATE_KEY"]
    S --> P[("GitHub Pages<br>APT-Repository")]
```

Einmalige Einrichtung (Pages-Quelle, Signaturschlüssel als Secret) und lokale Builds:
[packaging/README.md](https://github.com/Beerlesklopfer/wirgarten-tapir/blob/master/packaging/README.md).
