# Ausleihungs-Planungssystem – Funktionsdiagramm & Verifikation

Dieses Dokument beschreibt die wesentlichen Flüsse des Termin-/Buchungssystems (Planung von Ausleihen) und bewertet, ob es anhand des aktuellen Codes funktionsfähig ist. Diagramme sind in Mermaid gehalten.

## Komponentenüberblick

- HTTP-Routen in `Web/app.py`
  - `POST /plan_booking` – Mehrtägige/mehrstündige Planung (je Stunde iterativ)
  - `POST /add_booking` – Einfache Planung mit Start/End-Datum
  - `POST /schedule_appointment` – Planung per Datum + Stundenbereich (Start-/Endstunde)
  - `POST /cancel_booking/<id>` – Stornieren
  - `GET /terminplan` – UI
- Geschäftslogik in `Web/ausleihung.py`
  - `add_planned_booking()`/`add_ausleihung()` – Erstellen
  - `check_booking_conflict()` – Konfliktprüfung (zeitlich oder stundengenau)
  - `check_booking_period_range_conflict()` – Konfliktprüfung über Stundenbereich
  - `get_current_status()` – Statusableitung (planned/active/completed/cancelled)
- Scheduler in `Web/app.py`
  - `update_appointment_statuses()` – minütliche Statusaktualisierung via `get_current_status()`
- Hilfen
  - `get_period_times()` – Mappt Schulstunde → Start/Ende lt. `SCHOOL_PERIODS` (aus `config.json`)

## Funktionsdiagramm: Planung (mehrere Tage/Stunden)

```mermaid
flowchart TD
  A[Client: Terminplan-UI] -->|POST /plan_booking| B{Validierung}
  B -->|ok| C[Parse booking_date / booking_end_date]
  C --> D[Bestimme Stundenliste (period_start..period_end)]
  D --> E[Für jeden Tag: process_day_bookings]
  E --> F{get_period_times(tag, periode)}
  F -->|ok| G[Konfliktprüfung: au.check_booking_conflict(item, start, end, period)]
  G -->|kein Konflikt| H[Erzeuge planned Booking: au.add_planned_booking]
  G -->|Konflikt| I[Fehlerliste ergänzen]
  H --> J[booking_ids sammeln]
  I --> J
  J --> K{Fehler aufgetreten?}
  K -->|nein| L[Antwort: success=true, booking_ids]
  K -->|ja| M[Antwort: partial=true oder Fehler 400]
```

## Funktionsdiagramm: Planung (ein Termin mit Stundenbereich)

```mermaid
flowchart TD
  A[Client: Terminplan-UI] -->|POST /schedule_appointment| B{Validierung}
  B -->|ok| C[Parse Datum]
  C --> D[get_period_times(Startstunde)]
  C --> E[get_period_times(Endstunde)]
  D --> F[Start-Zeit]
  E --> G[End-Zeit]
  F --> H[Konfliktprüfung]
  G --> H
  H -->|kein Konflikt| I[au.add_planned_booking (planned)]
  I --> J[it.update_item_next_appointment]
  J --> K[Antwort: success=true, appointment_id]
  H -->|Konflikt| L[Antwort: 409 Conflict]
```

Hinweis: Derzeit wird in `schedule_appointment` nur `au.check_booking_conflict(..., period=start_period)` aufgerufen. Das prüft bei Stundenbereichen nur die Startstunde (siehe Verifikation unten).

## Funktionsdiagramm: Automatische Statusupdates (Scheduler)

```mermaid
flowchart TD
  S[Scheduler: jede Minute] --> A[DB: alle planned/active Buchungen]
  A --> B[get_current_status(aus Eintrag)]
  B --> C{Status geändert?}
  C -->|ja| D[DB: set Status + LastUpdated]
  C -->|nein| E[keine Aktion]
  D --> F[Loggen/Counter]
  E --> F
  F --> G[Fertig]
```

## Verifikation (funktional)

- Planung über `/plan_booking`:
  - Pro Tag und pro gewählter Stunde wird:
    - Zeitfenster via `get_period_times()` gebildet,
    - konfliktfrei via `au.check_booking_conflict()` geprüft,
    - bei Erfolg als `planned` via `au.add_planned_booking()` gespeichert.
  - Ergebnis: Teilsucces/Fehler werden korrekt aggregiert und zurückgegeben. → Funktionsfähig.
- Planung über `/add_booking`:
  - Nimmt Start/Ende als Datum/Uhrzeit, erstellt `planned` via `au.add_planned_booking()`. → Funktionsfähig.
- Planung über `/schedule_appointment` (ein Datum, Stundenbereich):
  - Start-/Endzeit werden korrekt aus `SCHOOL_PERIODS` abgeleitet.
  - Konfliktprüfung ruft jedoch `check_booking_conflict(..., period=start_period)` auf → prüft nur die Startstunde statt gesamten Bereichs. → Siehe „Auffälligkeiten“.
  - Bei Erfolg wird zusätzlich `it.update_item_next_appointment` gesetzt. → Funktionsfähig, mit o.g. Lücke bei Konflikten.
- Automatik (Scheduler):
  - `update_appointment_statuses()` lädt alle `planned`/`active`, ermittelt neuen Status via `au.get_current_status()` und schreibt Änderungen zurück. → Funktionsfähig.

## Auffälligkeiten / Verbesserungen

- Mögliche Konfliktlücke bei Stundenbereichen in `/schedule_appointment`:
  - Aktuell: `check_booking_conflict(..., period=start_period)` prüft nur die Startstunde periodengenau (kein Zeit-Overlap-Check, weil `period` gesetzt ist).
  - Empfehlung: Entweder
    - `au.check_booking_period_range_conflict(item_id, start_datetime, end_datetime, period=start, period_end=end)` verwenden, oder
    - analog zu `/plan_booking` alle Perioden im Bereich einzeln prüfen (Schleife) oder
    - `check_booking_conflict` ohne `period` aufrufen, damit Zeit-Overlap für das gesamte Intervall greift.
- Kleinere Code-Themen (nicht blockierend für Planung):
  - `ausleihung.complete_ausleihung()`/`cancel_ausleihung()` aktualisieren `items` mit `{'_id': ObjectId(id)}` – hier ist `id` die Ausleihungs-ID, nicht die Item-ID. Sollte separat korrigiert werden, betrifft aber die Planungslogik nicht direkt.
  - `ensure_timezone_aware()` benennt sich irreführend: es entfernt `tzinfo` (setzt nicht wirklich TZ). Der Rest des Planers arbeitet konsistent mit naiven Datumswerten.
  - Dopplung der Funktionssignatur `get_bookings_starting_now` in `ausleihung.py` (harmlos).

## Fazit

- Die Kernpfade für Planung, Konfliktprüfung (per Periode), Speichern sowie automatische Statusübergänge sind implementiert und lauffähig.
- Einzig die Konfliktprüfung für Stundenbereiche in `/schedule_appointment` sollte auf Bereichs-Prüfung umgestellt werden (siehe Empfehlung), um Kollisionen innerhalb des Intervalls sicher zu erkennen.

```text
Statusübergänge (get_current_status):
- planned → active (bei Startzeit erreicht)
- active → completed (nach Endzeit)
- cancelled bleibt cancelled
```
