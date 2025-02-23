# Inventarsystem

## Database

### User

```json
{"_id": 12345678, "username": "Test Nutzer", "password": "Verschlüsseltes Password", "Berechtigungslevel": 1}
```

### Inventar

```json
{"_id": 123456789, "name": "Test Item", "Ort": "Test", "Image": "String saving", "Verfügbar": "Ja/Nein", "Zustand":"1-10", "Last Change": [("User":"user_id"),("Datum":20.03.2024)]}
```

### Ausleihungen

```json
{"_id": 1234567890, "user_id": 12345678, "inventar_object_id": 123456789, "datum": 20.03.2025}
```
## Server

## Web