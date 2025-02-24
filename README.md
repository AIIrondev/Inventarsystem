# Inventarsystem

## Database

### User

```json
{"_id": 12345678, "username": "Test Nutzer", "password": "Verschlüsseltes Password", "Berechtigungslevel": 1}
```

### Inventar

```json
{"_id": 123456789, "name": "Test Item", "Ort": "Test", "Image": "String saving", "Verfügbar": "Ja/Nein", "Zustand":"1-10", "Last Change": ["User":"user_id","Datum":"20.03.2024"]}
```

### Ausleihungen

```json
{"_id": 1234567890, "user_id": 12345678, "inventar_object_id": 123456789, "datum": "20.03.2025"}
```
## Server

Interner Server der eine Website und Datenbank hosten mit allen Funktionen

## Web

Beim Betreten der Website wird man auf den Login Template geroutet oder falls ein Session Token vorliegt direkt in die Haupt Seite geschoben. Auf dieser kann direkt durch alle Database Items zugegriffen werden, wenn eine Höhere Berechtigung besteht können neue Nutzer und Items erstellt werden. Wenn man als Client auf ein Item klickt, gibt einem die Website die Möglichkeit den Lagerort(mit Bild) einzusehen, ob es im Moment verfügbar ist und wenn man es benötigt auch ausleihen kann.