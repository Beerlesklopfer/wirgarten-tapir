> ⚠️ **Nicht maßgeblich.** Dieses Wiki gehört zu einem abgeschlossenen Proof of Concept für den
> Eigenbetrieb von Tapir und wird nicht gepflegt. Maßgeblich ist die Dokumentation im
> Hauptprojekt: [FoodCoopX/wirgarten-tapir – docs](https://github.com/FoodCoopX/wirgarten-tapir/tree/master/docs),
> Aufbau in Issue [#1300](https://github.com/FoodCoopX/wirgarten-tapir/issues/1300).

# Anmelden und Passwort

> **Kurz gesagt:** Du meldest dich mit deiner E-Mail-Adresse und deinem Passwort an. Das
> Passwort legst du beim ersten Mal über den Link in der Aktivierungs-E-Mail fest. Vergessen?
> Auf der Anmeldeseite „Passwort vergessen?“ klicken, du bekommst einen Link per E-Mail.

## Erste Anmeldung

```mermaid
flowchart LR
    A["E-Mail: Bitte aktiviere dein<br>Benutzerkonto"] --> B["Link anklicken"]
    B --> C["Passwort festlegen"]
    C --> D["E-Mail ist bestätigt"]
    D --> E(["Mitgliederbereich"])
```

## Anmeldung

Auf der Anmeldeseite **Benutzername oder E-Mail** und **Passwort** eingeben, auf Wunsch
**Angemeldet bleiben** ankreuzen, **Anmelden**.

## Passwort vergessen

```mermaid
flowchart LR
    A["Passwort vergessen?"] --> B["E-Mail-Adresse eingeben"]
    B --> C["E-Mail: Passwort zurücksetzen"]
    C --> D["Link öffnen<br>(nur begrenzte Zeit gültig)"]
    D --> E["Neues Passwort zweimal eingeben"]
    E --> F(["angemeldet"])
```

## Passwort ändern

Im Mitgliederbereich in der Karte **Persönliche Daten** auf **Passwort ändern** klicken. Nach dem
Speichern kommst du zurück und siehst „Das hat geklappt!“. Zusätzlich bekommst du eine E-Mail.

## E-Mail-Adresse ändern

Siehe [Mitgliederbereich](Handbuch-Mitgliederbereich#persönliche-daten-und-e-mail). Die
Anmeldung funktioniert danach mit der neuen Adresse.
