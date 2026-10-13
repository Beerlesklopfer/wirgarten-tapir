# Datensicherung mit Bareos

> **Abstract:** Jede Instanz bekommt eine **eigene Bareos-Sicherung**, den Job `tapir-<name>`
> mit gleichnamigem FileSet. Bevor Bareos Dateien liest, ruft der Job auf dem Server
> `tapir-instance backup <name>` auf. Das schreibt nach `/var/backups/tapir/<name>/` einen Dump der
> Datenbank (`pg_dump -Fc`) und einen Export des Keycloak-Realms mit Benutzern, Passwort-Hashes,
> Rollen und Clients. Bareos sichert dann dieses Verzeichnis, die env-Datei, `/var/lib/tapir/<name>`
> und die nginx-Site. Einmal je Server sichert der Job `tapir-shared` die gemeinsamen Teile:
> die ganze Keycloak-Datenbank, `/etc/tapir` und die lizenzierten Schriften.
> `tapir-instance bareos` erzeugt die Director-Konfiguration (Bareos, künftig auch
> onesimus-dird); den Überblick über Pools, Jobs und Clients gibt
> [Onesimus](https://github.com/Beerlesklopfer/Onesimus). Läuft der Director auf demselben
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
Den Director, der sichern darf, legt das Paket schon an:
`/etc/bareos/bareos-fd.d/director/bareos-dir.conf` mit einem zufällig erzeugten Passwort.

```
Director {
  Name = bareos-dir                 # Name des Directors
  Password = "<Passwort des Clients>"
}
```

`Name` muss der Name des Directors sein (steht dort in `bareos-dir.d/director/*.conf`). Das
Passwort aus dieser Datei kommt in den Client-Eintrag des Directors; es gehört nicht in Tickets
oder Chats.

Auf dem Director der passende Client (`/etc/bareos/bareos-dir.d/client/forgeiec-fd.conf`). Ihn
erzeugt `tapir-instance bareos --all` mit, samt Passwort aus der Datei oben (Schritt 3):

```
Client {
  Name = forgeiec-fd
  Address = forgeiec.io
  Password = "<Passwort aus bareos-fd.d/director/bareos-dir.conf>"
  Passive = yes          # Director im Heimnetz: alle Verbindungen gehen von dort aus
}
```

#### Director im Heimnetz: `Passive = yes`

Ohne `Passive` baut der File Daemon auf dem Server selbst eine Verbindung zum Storage Daemon auf
(Port 9103). Steht der Storage Daemon im Heimnetz hinter einem Router, kommt diese Verbindung
nicht an und der Job wartet, bis er abbricht. Mit `Passive = yes` verbinden sich Director **und**
Storage Daemon zum File Daemon; der Server muss das Heimnetz nie erreichen.

```mermaid
flowchart LR
    subgraph H["Heimnetz"]
        D["bareos-dir"]
        S["bareos-sd"]
    end
    subgraph V["Server forgeiec.io"]
        F["bareos-fd :9102"]
    end
    D -->|"Steuerung"| F
    S -->|"Daten (Passive = yes)"| F
```

Nötig ist dann nur: Port 9102 auf dem Server ist vom Anschluss des Heimnetzes aus erreichbar
(Firewall des Servers, am besten nur für dessen Adresse). Im Heimnetz wird kein Port freigegeben.

#### Verschlüsselung

Bareos verschlüsselt jede Verbindung ab Werk mit **TLS-PSK** (TLS 1.3, AES-256): Schlüssel ist
das Passwort des jeweiligen Eintrags, beide Seiten weisen sich damit gegenseitig aus. Eine
CA oder Zertifikate braucht es dafür nicht.

X.509-Zertifikate (auch von Let's Encrypt) lassen sich in Bareos eintragen (`TLS Certificate`,
`TLS Key`, `TLS Verify Peer`), werden aber zwischen Bareos-Diensten **nicht** benutzt, solange
beide Seiten das Passwort kennen: Bareos bevorzugt dann immer TLS-PSK. Getestet mit Bareos 25.1.2
(Director, Storage und File Daemon mit Zertifikat und `TLS Require`, `TLS Verify Peer = yes`):
alle Verbindungen liefen über PSK, ein falscher `TLS Allowed CN` blieb ohne Wirkung. Zertifikate
von Let's Encrypt eignen sich außerdem nicht als Client-Zertifikate; sie enthalten seit 2026 nur
noch „TLS Web Server Authentication“.

Darum gilt für die Tapir-Sicherung:

- lange, zufällige Passwörter (die Pakete erzeugen sie so) und `TLS Require = yes` in den
  Einträgen, damit nie unverschlüsselt übertragen wird;
- für vertrauliche Daten auf fremdem Speicher zusätzlich die Verschlüsselung auf dem Client
  (`PKI Signatures`, `PKI Encryption`, eigener Schlüssel im File Daemon): dann liegen die Dumps
  auch auf den Volumes nur verschlüsselt.

### 2. Einstellungen

```sh
sudo cp /usr/share/tapir/bareos.env.example /etc/tapir/bareos.env
sudo editor /etc/tapir/bareos.env
```

| Variable | Vorgabe | Bedeutung |
|---|---|---|
| `BAREOS_CLIENT` | `<kurzer Hostname, klein>-fd` | Name des Clients im Director |
| `BAREOS_CLIENT_ADDRESS` | `hostname -f`, ohne Domain die Domain der ersten Instanz | Adresse, unter der der Director den Server erreicht, z. B. `forgeiec.io` |
| `BAREOS_DIRECTOR` | `bareos-dir` | Name des Directors in `bareos-fd.d/director/`; dessen Passwort kommt in den Client |
| `BAREOS_PASSIVE` | `yes` | passiver Client (Director im Heimnetz), `no` für einen Director, den der Server erreichen kann |
| `BAREOS_FD_CONFIG` | `/etc/bareos/bareos-fd.d` | Konfiguration des File Daemon auf dem Server |
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
sudo sh -c 'umask 077; tapir-instance bareos --all > /root/tapir-bareos.conf'   # Client, tapir-shared, alle Instanzen
sudo tapir-instance bareos ackervielfalt                                       # nur FileSet und Job einer Instanz
```

Die Datei beginnt mit einer **Anleitung in Kommentaren**: was im File Daemon auf dem Server für
den Director stehen muss (mit Prüfung, ob die Datei da ist), wohin die Datei auf dem Director
gehört, welche Rechte sie braucht und wie man testet. Jeder Teil beginnt mit dem Daemon, der ihn
liest, und seiner Zieldatei:

| Kopfzeile | wohin |
|---|---|
| `# [bareos-fd]  File: /etc/bareos/bareos-fd.d/director/bareos-dir.conf` | auf dem Tapir-Server; nur als Kommentar gezeigt, das Paket hat die Datei angelegt (mit Prüfung „found“/„NOT FOUND“) |
| `# [bareos-dir]  File: /etc/bareos/bareos-dir.d/client/forgeiec-fd.conf` | auf dem Director-Rechner: der Client |
| `# [bareos-dir]  File: /etc/bareos/bareos-dir.d/job/tapir-ackervielfalt.conf` | auf dem Director-Rechner: FileSet und Job einer Instanz |
 Man
kann die Teile so verteilen oder die ganze Datei in eine einzige `*.conf` legen; Bareos überliest
die Kommentare.

`--all` (und `--shared`) enthält den **Client** mit dem Passwort des File Daemon, die Datei deshalb
nur für root lesbar ablegen und nach dem Kopieren löschen. Auf dem Director als eine Datei
ablegen, z. B. `bareos-dir.d/job/tapir-forgeiec.conf` (Bareos liest jede `*.conf` unter
`bareos-dir.d/*/`), prüfen und neu laden:

```sh
sudo -u bareos bareos-dir -t && echo reload | sudo bconsole
```

**Director auf demselben Rechner:**

```sh
sudo tapir-instance bareos --all --write /etc/bareos/bareos-dir.d
```

`--write` legt `client/<client>.conf` und je Instanz `job/tapir-<name>.conf` mit FileSet und Job an
(Rechte `0640`, Gruppe `bareos`); FileSets einer älteren Version unter `fileset/` räumt es weg. Einen Client gleichen Namens, den der Director schon aus einer anderen
Datei kennt (z. B. `bareos-fd` aus dem Paket), lässt es stehen.

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

Client (Teil von `--shared` und `--all`) mit `BAREOS_CLIENT=forgeiec-fd` und
`BAREOS_CLIENT_ADDRESS=forgeiec.io`:

```
# Written by tapir-instance bareos - Client forgeiec-fd (forgeiec.io), contains the password of the file daemon
Client {
  Name = "forgeiec-fd"
  Description = "Tapir server forgeiec.io"
  Address = "forgeiec.io"
  Password = "<aus /etc/bareos/bareos-fd.d/director/bareos-dir.conf>"
  Passive = yes
}
```

FileSet und Job der Instanz `ackervielfalt`:

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

## Werkzeuge rund um Bareos

| Projekt | Was es ist | Nutzen für die Tapir-Sicherung |
|---|---|---|
| [Onesimus](https://github.com/Beerlesklopfer/Onesimus) ([onesimus.io](https://onesimus.io)) | Qt-Desktop-Oberfläche für Bareos und Bacula; spricht den Director über die bconsole-Schnittstelle an, nie direkt die Datenbank (GPL-3.0, Alpha) | Belegung der Pools, Wachstum und Prognosen, Verbrauch je Job und Client (also je Tapir-Instanz), wiederverwendbare Volumes – vom Arbeitsplatz aus, ohne Web-Oberfläche auf dem Backup-Server |
| **onesimus-dird** (in Arbeit, heute [baReos-dird](https://github.com/Beerlesklopfer/baReos-dird), nicht öffentlich) | Director nativ in Rust, entsteht als Fork von Bareos und ersetzt `bareos-dir`; spricht das Bareos-Protokoll mit den C++-Daemons (File und Storage Daemon, TLS-PSK) und als neues Protokoll **gRPC**; liest dasselbe Verzeichnis `bareos-dir.d` | Die von `tapir-instance bareos` erzeugten FileSets und Jobs sind gewöhnliche Bareos-Konfiguration; mit dem neuen Director sind sie noch nicht getestet (vor allem `RunScript` vor dem Job) |

Beide Projekte sind in Entwicklung (Onesimus: Alpha). Für die Sicherung der Solawi-Daten ist der
Director von Bareos selbst der getestete Weg. onesimus-dird ist noch nicht veröffentlicht; das Repository baReos-dird ist nur mit Zugang sichtbar.

### Option: X.509 mit onesimus-dird (geplant)

> **Abstract:** Der Transport ist bei Bareos immer verschlüsselt (TLS-PSK). onesimus-dird soll
> zusätzlich eine Anmeldung mit **X.509-Zertifikaten** anbieten. Der Director weist sich auf
> seinem gRPC-Zugang mit dem Let's-Encrypt-Zertifikat aus, das auf dem Tapir-Server ohnehin
> entsteht und dort auch den Intranet-Namen des Director-Rechners enthält. Ein Bareos-Job sichert
> Zertifikat und Schlüssel auf dem Server und spielt sie alle n Wochen auf dem Director-Rechner
> zurück; so bleibt das Zertifikat dort aktuell. Konsolen und die Oberfläche Onesimus melden sich
> später mit Zertifikaten aus einer eigenen CA an.
> Stand: Die Bareos-Jobs dafür sind getestet; gRPC mit eigenem Zertifikat gibt es in onesimus-dird,
> die Anmeldung per Client-Zertifikat ist noch nicht gebaut. onesimus-dird wird gerade weiter gebaut
> und verändert: Direktiven, Vorgaben und Abläufe unten können sich noch ändern.

```mermaid
flowchart LR
    subgraph V["Server forgeiec.io"]
        C["certbot: Zertifikat bareos<br>forgeiec.io + Intranet-Name"]
        H["deploy-Hook: Kopie nach<br>/var/backups/tapir/_tls"]
        F["bareos-fd"]
        C --> H --> F
    end
    subgraph I["Intranet"]
        R["Job tapir-tls-restore<br>alle n Wochen"]
        D["onesimus-dird<br>Grpc Tls Certificate"]
        K["Onesimus, Konsolen"]
    end
    F -->|"Job tapir-tls"| R
    R --> D
    K -->|"gRPC über TLS"| D
```

**Zwei Zertifikatsquellen:** Let's Encrypt stellt nur noch Server-Zertifikate aus („TLS Web
Server Authentication“, am Zertifikat von forgeiec.io nachgesehen). Für den Director passt das.
Für die Anmeldung von Konsolen braucht es Client-Zertifikate mit „TLS Web Client
Authentication“; sie kommen aus einer eigenen kleinen CA (z. B. step-ca oder openssl), und
onesimus-dird bildet CN oder SAN des Zertifikats auf den Namen der Console ab.

#### 1. Zertifikat auf dem Server, mit Intranet-Namen

Ein eigenes Zertifikat `bareos`, damit die Website-Zertifikate unberührt bleiben. Beispiel für den
Director-Rechner `pdc.intranet.bernau.family`. Let's Encrypt prüft jeden Namen von außen,
der Intranet-Name steht aber nur im internen DNS:

| Weg | Was zu tun ist | Folge |
|---|---|---|
| **HTTP-01** (einfach) | in der öffentlichen Zone `bernau.family` einen A-Eintrag `pdc.intranet` auf die Adresse von forgeiec.io; der interne DNS beantwortet den Namen im Heimnetz weiter mit der internen Adresse (Split-DNS) | der Hostname ist öffentlich sichtbar; nginx auf dem Server muss für diesen Namen `/.well-known/acme-challenge/` aus `/var/www/html` ausliefern (Standard-Site) |
| **DNS-01** | certbot setzt den TXT-Eintrag `_acme-challenge.pdc.intranet.bernau.family` über die API des DNS-Anbieters | außer dem TXT-Eintrag nichts Öffentliches; braucht ein certbot-Plugin für den Anbieter der Zone `bernau.family` |

```sh
sudo certbot certonly --cert-name bareos --webroot -w /var/www/html \
    -d forgeiec.io -d pdc.intranet.bernau.family
```

Nach jeder Erneuerung legt ein Hook Zertifikat und Schlüssel als echte Dateien (keine Links) dort
ab, wo die Sicherung sie mitnimmt. Datei `/etc/letsencrypt/renewal-hooks/deploy/bareos-tls`
(Rechte `0755`):

```sh
#!/bin/sh
# Copies the certificate "bareos" for the Bareos job tapir-tls
[ "$(basename "$RENEWED_LINEAGE")" = bareos ] || exit 0
install -d -m 0700 /var/backups/tapir/_tls
install -m 0644 "$RENEWED_LINEAGE/fullchain.pem" /var/backups/tapir/_tls/fullchain.pem
install -m 0600 "$RENEWED_LINEAGE/privkey.pem" /var/backups/tapir/_tls/privkey.pem
```

Einmal sofort ausführen:
`sudo RENEWED_LINEAGE=/etc/letsencrypt/live/bareos /etc/letsencrypt/renewal-hooks/deploy/bareos-tls`.

#### 2. Jobs: sichern und alle n Wochen zurückspielen

Auf dem Director. `tapir-tls` sichert das Verzeichnis; `tapir-tls-restore` spielt den zuletzt
gesicherten Stand über dessen Bootstrap-Datei auf dem Director-Rechner zurück (Client `bareos-fd`
ist dort der File Daemon) und legt die Dateien nach `/etc/onesimus/tls`.

```
FileSet {
  Name = "tapir-tls"
  Include {
    Options { Signature = XXH128 }
    File = "/var/backups/tapir/_tls"
  }
}
Schedule {
  Name = "tapir-tls"
  Run = Full w00/w02 mon at 04:00       # jede zweite Woche
}
Schedule {
  Name = "tapir-tls-restore"
  Run = w00/w02 mon at 04:30
}
Job {
  Name = "tapir-tls"
  JobDefs = "DefaultJob"
  Client = "forgeiec-fd"
  FileSet = "tapir-tls"
  Schedule = "tapir-tls"
  Level = Full
  Write Bootstrap = "/var/lib/bareos/tapir-tls.bsr"
}
Job {
  Name = "tapir-tls-restore"
  Type = Restore
  Client = "bareos-fd"                  # File Daemon auf dem Director-Rechner
  FileSet = "tapir-tls"
  Storage = File
  Pool = Full
  Messages = Standard
  Schedule = "tapir-tls-restore"
  Bootstrap = "/var/lib/bareos/tapir-tls.bsr"
  Regex Where = "!/var/backups/tapir/_tls!/etc/onesimus/tls!"
  Replace = Always
  RunScript {
    RunsWhen = After
    RunsOnClient = yes
    Command = "/usr/local/sbin/onesimus-tls-installed"
  }
}
```

Das Skript danach, `/usr/local/sbin/onesimus-tls-installed` (Rechte `0755`), setzt die Rechte,
prüft das Zertifikat und startet den Director verzögert neu. Er liest Zertifikat und Schlüssel
nur beim Start, und ein sofortiger Neustart würde den laufenden Job abbrechen:

```sh
#!/bin/sh
set -e
dir=/etc/onesimus/tls
chown root:bareos "$dir/fullchain.pem" "$dir/privkey.pem"
chmod 0644 "$dir/fullchain.pem"
chmod 0640 "$dir/privkey.pem"
openssl x509 -in "$dir/fullchain.pem" -noout -checkend 604800   # mindestens 7 Tage gültig
systemd-run --on-active=5min --unit=onesimus-tls-restart systemctl restart onesimus-dird
```

**Wie groß darf n sein?** Let's-Encrypt-Zertifikate gelten 90 Tage, certbot erneuert 30 Tage vor
Ablauf. Damit das neue Zertifikat ankommt, bevor das alte abläuft: n ≤ 4 Wochen; `w00/w02`
(alle zwei Wochen) lässt Luft für einen ausgefallenen Lauf. Die angekündigten kürzeren Laufzeiten
bei Let's Encrypt verlangen später ein kleineres n.

Getestet mit Bareos 25.1.2: Sicherung mit `Write Bootstrap`, zeitgesteuerter Restore-Job mit
`Bootstrap`, `Regex Where` und `RunScript` danach; der Schlüssel kam unverändert an. Der Schlüssel
liegt danach auf zwei Rechnern und in den Bareos-Volumes: Volumes verschlüsseln (PKI im File
Daemon) und den Pool kurz aufbewahren.

#### 3. onesimus-dird

gRPC gibt es nur über TLS. Einträge im Director (`bareos-dir.d/director/*.conf`), Stand 13.10.2026
(in Entwicklung, maßgeblich ist die Dokumentation von onesimus-dird):

| Direktive | Vorgabe | Bedeutung |
|---|---|---|
| `Grpc Port` | `DirPort` + 1000, also `0.0.0.0:10101` bei `DirPort = 9101` | Port des gRPC-Zugangs, lauscht auf allen Adressen: in der Firewall nur fürs Intranet öffnen |
| `Grpc Tls Certificate`, `Grpc Tls Key` | – | eigenes Zertifikat; ohne sie erzeugt der Director beim ersten Start ein selbst signiertes im Arbeitsverzeichnis |
| `Mdns Advertise` | an | kündigt sich als `_onesimus-dir._tcp` an, mit gRPC-Port und Zertifikats-Fingerprint im TXT-Eintrag |
| `Working Directory` | – | dort liegt das selbst erzeugte Zertifikat |

```
Director {
  ...
  Grpc Tls Certificate = /etc/onesimus/tls/fullchain.pem
  Grpc Tls Key = /etc/onesimus/tls/privkey.pem
}
```

| | selbst signiert (Standard) | Let's Encrypt |
|---|---|---|
| Prüfung durch Onesimus | Fingerprint, beim ersten Verbinden gemerkt (auch per mDNS bekannt) | öffentliche CA und Name des Directors |
| nach Erneuerung | Fingerprint bleibt über Neustarts gleich | Fingerprint ändert sich alle 60 Tage, Festhalten ist dann nicht sinnvoll |
| Name im Intranet | beliebig | muss im Zertifikat stehen (Abschnitt 1) |

Anmeldung heute: Name und Passwort der Console wie über das Bareos-Protokoll, das Passwort selbst
wird nie übertragen; danach braucht jeder Aufruf das Session-Token. Geplant: Anmeldung per
Client-Zertifikat (gRPC mit mTLS) aus der eigenen CA, Zuordnung CN/SAN → Console.

## Hinweise

- `remove` löscht den Bareos-Job (mit `BAREOS_CONFIG_DIR`); die Sicherungen im Bareos-Katalog
  bleiben, bis ihre Aufbewahrungszeit abläuft. `/var/backups/tapir/<name>/` bleibt auch nach
  `remove --purge` stehen und ist von Hand zu löschen.
- Der Job läuft als root auf dem Server. In der Konsole des Directors darf daher nur, wer auch
  root auf dem Tapir-Server sein darf.
- Ein Job, der nur mit `FAIL` endet, steht in `messages` mit der Meldung von `tapir-instance`,
  z. B. `dump of the database of <name> failed`. Häufige Ursachen und Abhilfe:
  [Fehlersuche](Betrieb-Fehlersuche#sicherung-schlägt-fehl).
