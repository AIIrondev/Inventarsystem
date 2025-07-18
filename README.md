# Inventarsystem

[![wakatime](https://wakatime.com/badge/user/30b8509f-5e17-4d16-b6b8-3ca0f3f936d3/project/8a380b7f-389f-4a7e-8877-0fe9e1a4c243.svg)](https://wakatime.com/badge/user/30b8509f-5e17-4d16-b6b8-3ca0f3f936d3/project/8a380b7f-389f-4a7e-8877-0fe9e1a4c243)

Ein webbasiertes Inventarverwaltungssystem, das es Benutzern ermöglicht, Gegenstände zu verfolgen, auszuleihen, zu reservieren und zurückzugeben. Das System verfügt über administrative Funktionen, Bildverwaltung, Buchungskalender und eine filterbasierte Artikelsuche.

## Funktionen

### Benutzeranmeldung
- Sichere Passwort-Richtlinien (mindestens 6 Zeichen!)
- Rollenbasierter Zugriff (Admin und reguläre Benutzer)

### Artikelverwaltung
- Hinzufügen und Löschen von Artikeln
- Ausleihen und Zurückgeben
- Detaillierte Artikelansicht mit Metadaten
- Anschaffungsdaten (Jahr, Kosten)
- Mehrfachbild-Upload und Verwaltung

### Buchungssystem
- Terminkalender für Reservierungen
- Farbcodierte Anzeige (aktuell, geplant, abgeschlossen)
- Konfliktprüfung bei Buchungen
- Automatische Aktivierung und Beendigung von Buchungen

### QR-Code-Funktionalität
- Automatische Generierung für jeden Artikel
- Scannen mit eingebautem QR-Scanner
- Schnellzugriff auf Artikeldetails

### Filterfunktionen
- Zweistufiges Filtersystem (Kategorie 1 und 2)
- Kombinierte Filter für präzise Ergebnisse

### Administratorwerkzeuge
- Benutzerverwaltung (Hinzufügen, Löschen)
- Protokollierung aller Ausleihen
- Zurücksetzen fehlerhafter Artikel

### Mobiloptimiertes Design
- Responsive Benutzeroberfläche
- Angepasste Bedienelemente für kleine Bildschirme

## Installation

### Voraussetzungen
- Python 3.7+
- MongoDB
- pip

### Lokale Einrichtung
Installation des Systems mit dem Installations-Skript (für Linux):

```bash
wget -O - https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
```
OR
 
```bash
curl -s https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
```

### Starten des Servers nach der erst Instalation

Als erstes müssen sie in die Website Direktion navigieren.
Anschließend führen sie den folgenden Comand aus:

```bash
sudo ./start.sh
```

** Dies ist nur notwendig falls der Server nicht automatisch Hochfährt nach einem Neustart. **

## Benutzerhandbuch

### Für reguläre Benutzer

#### Login und Hauptseite
- Nutzernamen und Passwort eingeben
- Auf den "Login"-Button klicken

#### Artikel durchsuchen
- Alle Artikel in einer kartenbasierten Ansicht durchblättern
- Jeder Artikel zeigt:
  - Name
  - Ort
  - Beschreibung
  - Bilder
  - Filterkategorien

#### Artikel filtern
- Dropdown-Menüs "Filter 1" und "Filter 2" nutzen
- Kombinierte Filter für präzise Ergebnisse
- "Alle" auswählen, um alle Artikel anzuzeigen

#### Artikel ausleihen und zurückgeben
- "Ausleihen"-Button klicken
- Zurückgeben durch erneuten Klick auf "Zurückgeben"
- System protokolliert Zeitpunkte

#### QR-Codes scannen
- "QR-Code scannen" Button klicken
- Kamera-Zugriff erlauben
- QR-Code scannen, um Detailansicht zu öffnen

#### Buchungssystem nutzen
- "Terminplan" öffnen
- Neue Buchung erstellen:
  - Objekt auswählen
  - Zeitraum festlegen
  - Notizen hinzufügen
  - Buchung bestätigen
- Eigene Buchungen sind farblich hervorgehoben
- Buchung stornieren durch Klick auf "Ausleihe stornieren"

### Für Administratoren

#### Admin-Oberfläche
- Anmeldung mit Admin-Zugangsdaten
- Erweiterte Verwaltungsfunktionen verfügbar

#### Neue Artikel hinzufügen
- "Artikel hochladen" Formular ausfüllen:
  - Name
  - Ort
  - Beschreibung
  - Filter-Kategorien
  - Anschaffungsjahr & -kosten
  - Interne Artikelnummer
  - Bilder hochladen
- "Hochladen" klicken

#### Artikel löschen
- Artikel suchen und "Delete" klicken

#### Ausgeliehene Artikel verwalten
- Alle Artikel, auch ausgeliehene, einsehen
- Artikel im Namen von Benutzern zurückgeben
- "Zurücksetzen" für problematische Artikel

#### Benutzer verwalten
- Neue Benutzer hinzufügen
- Bestehende Benutzer löschen
- Ausleihhistorie einsehen

#### Buchungssystem verwalten
- Alle Buchungen einsehen und verwalten
- Problematische Buchungen stornieren/bearbeiten

### QR-Code-System
- Jeder Artikel erhält automatisch einen QR-Code
- QR-Codes können gedruckt und an Objekten angebracht werden
- Scannen leitet direkt zur Artikelseite

## Systemanforderungen
- Moderner Webbrowser (Chrome, Firefox, Safari, Edge)
- Internetzugang
- Für Administratoren: Desktop-Umgebung empfohlen
- Für QR-Scanning: Gerät mit Kamera

## Lizenz
Dieses Projekt ist unter der Apache License, Version 2.0 lizenziert. Siehe die LICENSE-Datei für Details.

## Mitwirkende
**Maximilian Gründinger** - Projektgründer

Für technische Unterstützung oder Fragen bitte ein Issue im GitHub-Repository eröffnen.

## Fehlerbehebung

### PyMongo/Bson Konflikt beheben

Es kann zu einem Konflikt zwischen den Paketen `pymongo` und `bson` kommen, der sich durch folgende Fehlermeldung äußert:
```
ImportError: cannot import name '_get_object_size' from 'bson'
```

Dieser Konflikt tritt auf, wenn das separate `bson`-Paket zusammen mit `pymongo` installiert ist, wobei `pymongo` bereits seine eigene Version von `bson` enthält.

#### Schritte zur Fehlerbehebung:

1. **Fix-PyMongo-Skript ausführen**:
   ```bash
   sudo ./fix-pymongo.sh
   ```
   Dieses Skript entfernt das konfliktierende `bson`-Paket und installiert `pymongo` neu.

2. **Falls der erste Schritt nicht hilft, die virtuelle Umgebung neu erstellen**:
   ```bash
   sudo ./rebuild-venv.sh
   ```
   Dieses Skript erstellt die virtuelle Python-Umgebung komplett neu und installiert alle erforderlichen Pakete.

3. **Services neu starten**:
   ```bash
   sudo ./restart.sh
   ```

### Berechtigungsprobleme beheben

Wenn Sie Berechtigungsfehler wie `Keine Berechtigung` oder `Permission denied` sehen:

1. **Berechtigungen für kritische Verzeichnisse anpassen**:
   ```bash
   sudo ./fix-permissions.sh
   ```
   Dieses Skript korrigiert die Berechtigungen für die virtuelle Umgebung und wichtige Verzeichnisse.

2. **Logs-Verzeichnis manuell korrigieren**:
   ```bash
   sudo mkdir -p logs
   sudo chmod 777 logs
   ```

3. **Falls Python-Skripte nicht ausgeführt werden können**:
   ```bash
   sudo chmod +x *.py
   sudo chmod +x *.sh
   ```

### Backup und Wiederherstellung testen

So stellen Sie sicher, dass das Backup- und Wiederherstellungssystem korrekt funktioniert:

1. **Manuelles Backup erstellen**:
   ```bash
   sudo ./update.sh
   ```

2. **Backup-Liste anzeigen**:
   ```bash
   sudo ./restore.sh --list
   ```

3. **Neuestes Backup wiederherstellen** (nur zu Testzwecken):
   ```bash
   sudo ./restore.sh --date=latest
   ```

4. **Nach erfolgreicher Wiederherstellung prüfen**:
   ```bash
   sudo ./restart.sh
   ```
   Überprüfen Sie anschließend, ob alle Funktionen wie erwartet arbeiten.

### Überprüfung der MongoDB-Installation

Fehler bei der Datenbankverbindung beheben:

1. **MongoDB-Status überprüfen**:
   ```bash
   sudo systemctl status mongod
   ```

2. **Falls nicht aktiv, MongoDB starten**:
   ```bash
   sudo systemctl start mongod
   sudo systemctl enable mongod
   ```

3. **PyMongo-Installation überprüfen**:
   ```bash
   python3 -c "import pymongo; print(pymongo.__version__)"
   ```
   Dies sollte die Version ausgeben (z.B. `4.6.1`) ohne Fehlermeldungen.

### Probleme mit dem Backup-System

Wenn Backups fehlschlagen oder nicht angelegt werden:

1. **Manuelle Ausführung mit Logging**:
   ```bash
   sudo ./run-backup.sh --uri mongodb://localhost:27017/ --db Inventarsystem --out backups/$(date +%Y-%m-%d)
   ```

2. **Backup-Verzeichnis überprüfen**:
   ```bash
   ls -la backups/
   ```
   
3. **Log-Dateien auf Fehler überprüfen**:
   ```bash
   tail -n 50 logs/Backup_db.log
   tail -n 50 logs/daily_update.log
   ```

### Bildupload und Dateinamen

Das System verwendet einen sicheren Mechanismus für Bildupload-Dateinamen:

1. **Einzigartige Dateinamen**: Jedes hochgeladene Bild erhält einen vollständig einzigartigen Dateinamen basierend auf UUID.
2. **Nicht wiederverwendbare Dateinamen**: Selbst wenn Bilder den gleichen ursprünglichen Dateinamen haben, werden sie mit unterschiedlichen UUIDs gespeichert.
3. **Zeitstempelverwaltung**: Zusätzlich zum UUID enthalten die Dateinamen einen Zeitstempel für bessere Sortierung und Verfolgbarkeit.

Mehr Details finden Sie in der Datei `IMAGE_UPLOAD_CHANGES.md`.

### Sicherheitshinweis

Nachdem Sie diese Wartungsaufgaben abgeschlossen haben, empfehlen wir:

1. Überprüfen Sie die ordnungsgemäße Funktion des Systems.
2. Löschen Sie temporäre Backup-Dateien aus dem Verzeichnis `/tmp`, wenn diese nicht mehr benötigt werden.
3. Stellen Sie sicher, dass die Log-Rotation aktiv ist, damit die Log-Dateien nicht unbegrenzt wachsen.
