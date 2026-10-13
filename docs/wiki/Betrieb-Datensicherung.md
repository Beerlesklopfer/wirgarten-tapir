# Datensicherung mit Bareos

> **Abstract:** Jede Instanz bekommt eine **eigene Bareos-Sicherung**, den Job `tapir-<name>`
> mit gleichnamigem FileSet. Bevor Bareos Dateien liest, ruft der Job auf dem Server
> `tapir-instance backup <name>` auf. Das schreibt nach `/var/backups/tapir/<name>/` einen Dump der
> Datenbank (`pg_dump -Fc`) und einen Export des Keycloak-Realms mit Benutzern, Passwort-Hashes,
> Rollen und Clients. Bareos sichert dann dieses Verzeichnis, die env-Datei, `/var/lib/tapir/<name>`
> und die nginx-Site. Einmal je Server sichert der Job `tapir-shared` die gemeinsamen Teile:
> die ganze Keycloak-Datenbank, `/etc/tapir` und die lizenzierten Schriften.
> `tapir-instance bareos` erzeugt die Director-Konfiguration. Läuft der Director auf demselben
> Rechner, legen `create`, `adopt` und `remove` die Jobs selbst an und entfernen sie wieder.
> `tapir-instance restore <name>` spielt eine Sicherung zurück: eine Instanz allein, ohne die
> anderen anzufassen.

## Was gesichert wird

| Job | Inhalt | Zweck |
|---|---|---|
| `tapir-<name>` | `/var/backups/tapir/<name>/tapir.dump` | Datenbank der Instanz (Mitglieder, Verträge, Zahlungen, Parameter, …) |
| | `/var/backups/tapir/<name>/realm.json` | Keycloak-Realm der Instanz: Logins mit Passwort-Hashes, Rollen, Gruppen, Clients, SMTP, Theme |
| | `/var/backups/tapir/<name>/backup.info` | Zeitpunkt, Domain, Realm, Image und dessen Digest |
| | `/etc/tapir/instances/<name>.env` | Konfiguration der Instanz |
| | `/var/lib/tapir/<name>/` | Uploads, Medien, Fehlerprotokolle, beat-Zeitplan |
| | `/etc/nginx/sites-available/tapir-<name>` | nginx-Site |
| `tapir-shared` | `/var/backups/tapir/_shared/keycloak.dump` | ganze Keycloak-Datenbank (alle Realms und `master`) |
| | `/etc/tapir/` ohne `instances/` und `initial-passwords/` | `keycloak.env` (Admin- und DB-Passwort), `bareos.env` |
| | `/var/lib/tapir/keycloak/`, `/var/lib/tapir/theme-fonts/` | Keycloak-Themes, lizenzierte Schriften (nicht im Paket) |
| | `/etc/nginx/snippets/tapir-keycloak.conf`, Quadlets `tapir-keycloak` und `tapir-redis` | gemeinsame Einrichtung |

Nicht gesichert werden der Inhalt von Redis (Warteschlange und Cache, wird neu aufgebaut), die
Container-Images (liegen in ghcr.io, `backup.info` nennt den Digest), die Zertifikate unter
`/etc/letsencrypt` (certbot stellt sie neu aus) und die Startpasswörter in `/etc/tapir/initial-passwords/`.

## Ablauf eines Jobs

```mermaid
sequenceDiagram
    participant D as Bareos Director
    participant F as bareos-fd (Server, root)
    participant T as tapir-instance backup NAME
    participant P as PostgreSQL
    participant K as tapir-keycloak
    participant S as Storage Daemon
    D->>F: Job tapir-NAME starten
    F->>T: RunScript (vor dem Lesen)
    T->>P: pg_dump -Fc tapir_NAME
    T->>K: kc.sh export --realm REALM --users same_file
    T-->>F: /var/backups/tapir/NAME/ fertig (Exit 0)
    F->>S: FileSet tapir-NAME
    S-->>D: Job OK
    Note over T,F: Exit ≠ 0 bricht den Job ab (FailJobOnError)
```

- Der Export des Realms läuft neben dem laufenden Keycloak (Profil `nonserver`, liest direkt die
  Datenbank). Anmeldungen laufen während der Sicherung weiter.
- Ein Job dauert für eine kleine Solawi wenige Sekunden; die Hälfte davon braucht der Start der
  Java-Laufzeit für den Export.
- Die Dateien werden erst unter `*.tmp` geschrieben und nach Erfolg umbenannt. Schlägt ein Schritt
  fehl, bleibt die vorige Sicherung stehen und der Job meldet den Fehler.
- `/var/backups/tapir/` gehört root mit `0700`, jede Datei hat `0600`. Die Dumps enthalten
  Passwort-Hashes, Client-Secrets und das SMTP-Passwort.

## Einrichtung

### 1. File Daemon auf dem Tapir-Server

```sh
sudo apt install bareos-filedaemon
```

`bareos-fd` läuft unter Debian als root; das ist nötig, weil `tapir-instance` nur für root ist.
Der Director, der sichern darf, steht in `/etc/bareos/bareos-fd.d/director/<director>.conf`:

```
Director {
  Name = bareos-dir                 # Name des Directors
  Password = "<Passwort des Clients>"
}
```

Auf dem Director der passende Client (`/etc/bareos/bareos-dir.d/client/forgeiec-fd.conf`):

```
Client {
  Name = forgeiec-fd
  Address = forgeiec.io
  Password = "<Passwort des Clients>"
}
```

Port 9102 muss vom Director aus erreichbar sein. Für Sicherungen über fremde Netze empfiehlt sich
TLS (bei Bareos Standard) und die Verschlüsselung auf dem Client (PKI-Schlüssel im File Daemon),
weil die Dumps vertrauliche Daten enthalten.

### 2. Einstellungen

```sh
sudo cp /usr/share/tapir/bareos.env.example /etc/tapir/bareos.env
sudo editor /etc/tapir/bareos.env
```

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `BAREOS_CLIENT` | `<kurzer Hostname>-fd` | Name des Clients im Director |
| `BAREOS_JOBDEFS` | `DefaultJob` | JobDefs mit Zeitplan, Pools, Storage und Messages |
| `BAREOS_SCHEDULE` | – (aus JobDefs) | eigener Zeitplan, z. B. `WeeklyCycle` |
| `BAREOS_POOL` | – (aus JobDefs) | eigener Pool |
| `BAREOS_STORAGE` | – (aus JobDefs) | eigenes Storage |
| `BAREOS_SIGNATURE` | `XXH128` | Prüfsumme; Bareos älter als 22 braucht `MD5` |
| `BAREOS_CONFIG_DIR` | – | Director auf diesem Rechner: dort pflegt `tapir-instance` die Jobs selbst |
| `BAREOS_RELOAD` | `bconsole` | Befehl, der nach Änderungen `reload` liest; `none` = selbst neu laden |

### 3. Jobs anlegen

**Director auf einem anderen Rechner:** die Konfiguration erzeugen und dorthin kopieren.

```sh
sudo tapir-instance bareos --all > tapir-bareos.conf     # alle Instanzen und tapir-shared
sudo tapir-instance bareos ackervielfalt                 # nur eine Instanz
```

Auf dem Director den Inhalt in `bareos-dir.d/fileset/` und `bareos-dir.d/job/` ablegen (oder als
eine Datei z. B. `bareos-dir.d/job/tapir-forgeiec.conf`), prüfen und neu laden:

```sh
sudo -u bareos bareos-dir -t && echo reload | sudo bconsole
```

**Director auf demselben Rechner:**

```sh
sudo tapir-instance bareos --all --write /etc/bareos/bareos-dir.d
```

Mit `BAREOS_CONFIG_DIR=/etc/bareos/bareos-dir.d` in `bareos.env` geschieht das danach von selbst:
`create` und `adopt` legen `tapir-<name>` an (und einmalig `tapir-shared`), `remove` löscht den
Job. Es werden nur Dateien gelöscht, die mit `# Written by tapir-instance` beginnen.

### 4. Erster Lauf

```sh
sudo bconsole
*run job=tapir-ackervielfalt yes
*wait
*messages
*list files jobid=<id>
```

Ohne Bareos lässt sich der vorbereitende Schritt allein prüfen:

```sh
sudo tapir-instance backup ackervielfalt
sudo ls -l /var/backups/tapir/ackervielfalt/
```

## Erzeugte Konfiguration

Beispiel für die Instanz `ackervielfalt` mit `BAREOS_CLIENT=forgeiec-fd`:

```
# Written by tapir-instance bareos - Tapir ackervielfalt (https://ackervielfalt.forgeiec.io): database, Keycloak realm, files
FileSet {
  Name = "tapir-ackervielfalt"
  Description = "Tapir ackervielfalt (https://ackervielfalt.forgeiec.io): database, Keycloak realm, files"
  Include {
    Options {
      Signature = XXH128
      Compression = LZ4
    }
    File = "/var/backups/tapir/ackervielfalt"
    File = "/etc/tapir/instances/ackervielfalt.env"
    File = "/var/lib/tapir/ackervielfalt"
    File = "/etc/nginx/sites-available/tapir-ackervielfalt"
  }
}
Job {
  Name = "tapir-ackervielfalt"
  Description = "Tapir ackervielfalt (https://ackervielfalt.forgeiec.io): database, Keycloak realm, files"
  JobDefs = "DefaultJob"
  Client = "forgeiec-fd"
  FileSet = "tapir-ackervielfalt"
  # One bootstrap file per job: the default (%c.bsr) would be shared by all jobs of the client
  Write Bootstrap = "/var/lib/bareos/%c-%n.bsr"
  RunScript {
    RunsWhen = Before
    RunsOnClient = yes
    FailJobOnError = yes
    Command = "/usr/sbin/tapir-instance backup ackervielfalt"
  }
}
```

`Write Bootstrap` ist je Job eigen, weil `DefaultJob` `%c.bsr` setzt und sich sonst alle Jobs
eines Clients eine Bootstrap-Datei teilen würden. Inkrementelle Läufe enthalten die Dumps immer
vollständig, weil sie bei jedem Lauf neu geschrieben werden; die übrigen Dateien nur, wenn sie
sich geändert haben.

## Wiederherstellen

```mermaid
flowchart TD
    Q{"Was ist verloren?"} -->|"Daten einer Instanz<br>(Bedienfehler, Import)"| A["bconsole: Dateien von tapir-NAME<br>zurück, where=/"]
    A --> R["tapir-instance restore NAME"]
    Q -->|"ganzer Server"| N["Debian, PostgreSQL, nginx,<br>podman, tapir, bareos-fd installieren"]
    N --> SH["bconsole: tapir-shared zurück, where=/"]
    SH --> AL["bconsole: tapir-NAME je Instanz zurück"]
    AL --> R2["tapir-instance restore NAME<br>je Instanz"]
    R2 --> NG["nginx-Sites aktivieren, certbot"]
    R --> C["Prüfungen grün"]
    NG --> C
```

### Eine Instanz zurücksetzen

1. Dateien mit Bareos zurückholen. Mit `where=/` landen sie an ihrem Platz, die laufende Instanz
   bleibt davon unberührt, bis `restore` läuft:

   ```sh
   sudo bconsole
   *restore client=forgeiec-fd fileset=tapir-ackervielfalt where=/ select current all done yes
   ```

   Ein älterer Stand: statt `current` z. B. `before="2026-10-01 00:00:00"`. Vorsichtiger ist ein
   eigenes Ziel (`where=/tmp/bareos-restores`), dann im nächsten Schritt `--from` angeben.

2. Zurückspielen:

   ```sh
   sudo tapir-instance restore ackervielfalt
   # oder aus dem Ziel des Restores:
   sudo tapir-instance restore ackervielfalt --from /tmp/bareos-restores/var/backups/tapir/ackervielfalt
   ```

`restore` fragt nach dem Namen der Instanz (ohne Terminal: `--yes`) und dann:

| Schritt | Wirkung |
|---|---|
| Instanz anhalten | Web, Worker und Beat stoppen |
| Datenbank | lokal: Datenbank löschen und neu anlegen, Rolle mit dem Passwort aus der env-Datei, `pg_restore`; entfernt: `pg_restore --clean` |
| Realm | Realm löschen und aus `realm.json` neu anlegen (alle Logins mit ihren Passwörtern), danach URLs, Secret, SMTP und Theme wie bei `keycloak` setzen; fehlt Keycloak ganz, wird er aus `keycloak.env` neu eingerichtet |
| Redis | Datenbanknummer sicherstellen, Cache der Instanz leeren |
| Image, Migration | Image ziehen, `migrate` (eine ältere Sicherung wird auf den Stand des Images gehoben) |
| Start | Units schreiben, starten; nginx-Site schreiben, falls sie fehlt |
| Prüfungen | wie `status` |

| Option | Bedeutung |
|---|---|
| `--from <dir>` | Verzeichnis mit `tapir.dump` (und `realm.json`), Vorgabe `/var/backups/tapir/<name>` |
| `--no-realm` | nur die Datenbank, der Realm bleibt wie er ist (z. B. wenn nur ein Import schiefging) |
| `--yes` | ohne Rückfrage |

Andere Instanzen laufen währenddessen weiter. Wer mit `--no-realm` eine ältere Datenbank
zurückholt, behält die heutigen Logins; Mitglieder, die es nur in der alten Datenbank gibt,
haben dann noch ihren Login, Mitglieder, die seitdem dazukamen, einen Login ohne Tapir-Benutzer.

`restore` kann eine Sicherung nicht in ein **älteres** Image einspielen als das, mit dem sie
entstand. `backup.info` nennt den Digest; zurück auf genau diesen Stand:

```sh
sudo tapir-instance upgrade ackervielfalt --image ghcr.io/beerlesklopfer/wirgarten-tapir@sha256:<digest>
```

### Ganzer Server

1. Debian 13, PostgreSQL, nginx und das Paket `tapir` aus dem APT-Repository installieren
   ([Installation](Betrieb#installation)), dazu `bareos-filedaemon` mit demselben Client-Namen und
   Passwort wie vorher.
2. `tapir-shared` zurückholen (`where=/`): bringt `keycloak.env`, die Themes und die Schriften.
3. Für jede Instanz `tapir-<name>` zurückholen und `tapir-instance restore <name> --yes` aufrufen.
   Der erste Aufruf richtet Redis und Keycloak ein; jede Instanz bekommt ihren Realm aus der
   eigenen Sicherung.
4. nginx-Sites aktivieren, Zertifikate neu ausstellen ([erste Schritte](Betrieb#erste-schritte)).

Alternativ zu den Realm-Exporten lässt sich die ganze Keycloak-Datenbank zurückspielen, etwa wenn
der Realm `master` mit weiteren Admins gebraucht wird. Danach die Instanzen mit `--no-realm`
zurückspielen:

```sh
sudo systemctl stop tapir-keycloak
sudo runuser -u postgres -- psql -c 'DROP DATABASE IF EXISTS keycloak WITH (FORCE)' -c 'CREATE DATABASE keycloak OWNER keycloak'
sudo runuser -u postgres -- pg_restore --no-owner --role=keycloak -d keycloak < /var/backups/tapir/_shared/keycloak.dump
sudo systemctl start tapir-keycloak
```

## Hinweise

- `remove` löscht den Bareos-Job (mit `BAREOS_CONFIG_DIR`); die Sicherungen im Bareos-Katalog
  bleiben, bis ihre Aufbewahrungszeit abläuft. `/var/backups/tapir/<name>/` bleibt auch nach
  `remove --purge` stehen und ist von Hand zu löschen.
- Der Job läuft als root auf dem Server. In der Konsole des Directors darf daher nur, wer auch
  root auf dem Tapir-Server sein darf.
- Ein Job, der nur mit `FAIL` endet, steht in `messages` mit der Meldung von `tapir-instance`,
  z. B. `dump of the database of <name> failed`. Häufige Ursachen und Abhilfe:
  [Fehlersuche](Betrieb-Fehlersuche#sicherung-schlägt-fehl).
