# Inventarsystem

[![wakatime](https://wakatime.com/badge/user/30b8509f-5e17-4d16-b6b8-3ca0f3f936d3/project/8a380b7f-389f-4a7e-8877-0fe9e1a4c243.svg)](https://wakatime.com/badge/user/30b8509f-5e17-4d16-b6b8-3ca0f3f936d3/project/8a380b7f-389f-4a7e-8877-0fe9e1a4c243)

**Aktuelle Version: 2.5.18**

Ein webbasiertes Inventarverwaltungssystem, das es Benutzern ermöglicht, Gegenstände zu verfolgen, auszuleihen, zu reservieren und zurückzugeben. Das System verfügt über administrative Funktionen, Bildverwaltung, Buchungskalender und eine filterbasierte Artikelsuche.

## Systemübersicht und Wartung

Das Inventarsystem bietet folgende Wartungsskripte:
- `update.sh` - Aktualisiert das System, erstellt ein Backup und installiert Abhängigkeiten
- `fix-permissions.sh` - Behebt Berechtigungsprobleme der virtuellen Umgebung
- `fix-all-permissions.sh` - Umfassende Korrektur aller Berechtigungen im System
- `fix-pymongo.sh` - Behebt Konflikte zwischen pymongo und bson
- `rebuild-venv.sh` - Baut die virtuelle Python-Umgebung neu auf
- `start.sh`, `stop.sh`, `restart.sh` - Dienste steuern
- `Backup-DB.py` - Manuelles Backup der Datenbank erstellen
- `restore.sh` - Vorhandenes Backup wiederherstellen

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
- Sicheres Bildspeichersystem mit UUID-basierten, einmaligen Dateinamen

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

## Schritt-für-Schritt-Anleitungen

### Installation und Einrichtung

#### Erstinstallation des Systems
1. Laden Sie das Installationsskript herunter und führen Sie es aus:
   ```bash
   wget -O - https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
   ```
   
   ODER
   
   ```bash
   curl -s https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
   ```

2. Folgen Sie den Anweisungen im Installationsskript:
   - Bestätigen Sie die Installation von abhängigen Paketen
   - Warten Sie, bis MongoDB und andere Komponenten installiert sind
   - Beachten Sie das Installationsprotokoll auf Fehler

3. Nach der Installation:
   ```bash
   cd /pfad/zum/Inventarsystem
   sudo ./start.sh
   ```

4. Überprüfen Sie die Installation:
   - Öffnen Sie einen Webbrowser
   - Navigieren Sie zu `https://[Server-IP-Adresse]`
   - Sie sollten die Login-Seite sehen
   
5. Bei Installations- oder Berechtigungsproblemen:
   - Führen Sie `sudo ./fix-all-permissions.sh` aus, um umfassend alle Berechtigungen zu korrigieren
   - Oder führen Sie `sudo ./fix-permissions.sh` für eine gezielte Korrektur der Python-Umgebung aus
   - Falls pymongo/bson-Fehler auftreten, führen Sie `sudo ./fix-pymongo.sh` aus
   - Bei anhaltenden Problemen führen Sie `sudo ./rebuild-venv.sh` aus, um die Python-Umgebung komplett neu zu erstellen

#### Konfiguration der Datenbank
1. Die MongoDB-Datenbank wird automatisch erstellt und konfiguriert
2. Bei Bedarf können Sie die Datenbankverbindung in `config.json` anpassen:
   ```bash
   sudo nano config.json
   ```
   
3. Standardwerte für die Datenbankverbindung:
   ```json
   {
     "dbg": false,
     "key": "IhrGeheimSchlüssel",
     "ver": "2.5.18",
     "host": "0.0.0.0",
     "port": 443
   }
   ```

### System starten und stoppen

#### System starten
1. Navigieren Sie zum Installationsverzeichnis:
   ```bash
   cd /pfad/zum/Inventarsystem
   ```

2. Führen Sie das Start-Skript aus:
   ```bash
   sudo ./start.sh
   ```
   
3. Überprüfen Sie den Status:
   ```bash
   sudo systemctl status inventarsystem-gunicorn.service
   sudo systemctl status inventarsystem-nginx.service
   ```

#### System stoppen
1. Navigieren Sie zum Installationsverzeichnis:
   ```bash
   cd /pfad/zum/Inventarsystem
   ```
   
2. Führen Sie das Stopp-Skript aus:
   ```bash
   sudo ./stop.sh
   ```

#### System neustarten
1. Bei Konfigurationsänderungen oder Updates:
   ```bash
   cd /pfad/zum/Inventarsystem
   sudo ./restart.sh
   ```

### Benutzerverwaltung

#### Erstellen des ersten Administratorkontos
1. Führen Sie das User-Generation-Skript aus:
   ```bash
   cd /pfad/zum/Inventarsystem
   source .venv/bin/activate
   python Web/generate_user.py
   ```
   
2. Geben Sie die erforderlichen Informationen ein:
   - Benutzername
   - Passwort (mindestens 6 Zeichen)
   - Admin-Status (ja/nein)

#### Benutzer hinzufügen (als Administrator)
1. Loggen Sie sich mit Ihrem Administrator-Konto ein
2. Navigieren Sie zu "Benutzer verwalten"
3. Klicken Sie auf "Neuen Benutzer hinzufügen"
4. Geben Sie folgende Daten ein:
   - Benutzername (eindeutig)
   - Passwort (mindestens 6 Zeichen)
   - Admin-Status (ja/nein)
5. Klicken Sie auf "Speichern"

#### Benutzer löschen
1. Loggen Sie sich als Administrator ein
2. Navigieren Sie zu "Benutzer verwalten"
3. Finden Sie den zu löschenden Benutzer
4. Klicken Sie auf das Löschsymbol neben dem Benutzernamen
5. Bestätigen Sie die Löschaktion

### Artikelverwaltung

#### Artikel hinzufügen
1. Loggen Sie sich als Administrator ein
2. Klicken Sie auf "Artikel hochladen"
3. Füllen Sie das Formular mit folgenden Informationen aus:
   - Name des Artikels
   - Ort (Standort/Raum)
   - Beschreibung (Details zum Artikel)
   - Filter-Kategorien (Unterrichtsfach, Materialtyp, etc.)
   - Anschaffungsjahr (optional)
   - Anschaffungskosten (optional)
   - Code (interne Artikelnummer, kann automatisch generiert werden)
4. Laden Sie ein oder mehrere Bilder des Artikels hoch:
   - Klicken Sie auf "Dateien auswählen"
   - Wählen Sie Bilder vom Computer aus
   - Unterstützte Formate: JPG, JPEG, PNG, GIF, MP4, MOV, etc.
5. Klicken Sie auf "Artikel hochladen"

#### Artikel bearbeiten
1. Finden Sie den Artikel in der Übersicht
2. Klicken Sie auf das Bearbeitungssymbol
3. Aktualisieren Sie die gewünschten Informationen
4. Fügen Sie neue Bilder hinzu oder entfernen Sie bestehende
5. Klicken Sie auf "Änderungen speichern"

#### Artikel löschen
1. Finden Sie den Artikel in der Übersicht
2. Klicken Sie auf das Löschsymbol (Mülleimer)
3. Bestätigen Sie die Löschaktion
4. Der Artikel und alle zugehörigen Bilder und QR-Codes werden entfernt

### Ausleihverwaltung

#### Artikel ausleihen (als Benutzer)
1. Finden Sie den gewünschten Artikel in der Übersicht
2. Klicken Sie auf "Ausleihen"
3. Das System protokolliert automatisch:
   - Ausleihzeitpunkt
   - Ausleihenden Benutzer
   - Status des Artikels wird auf "Ausgeliehen" gesetzt

#### Artikel zurückgeben
1. Navigieren Sie zu "Meine ausgeliehenen Artikel"
2. Finden Sie den zurückzugebenden Artikel
3. Klicken Sie auf "Zurückgeben"
4. Das System aktualisiert automatisch:
   - Rückgabezeitpunkt
   - Status des Artikels wird auf "Verfügbar" gesetzt
   - Die Ausleihhistorie wird aktualisiert

#### Ausleihungen planen
1. Navigieren Sie zum "Terminplan"
2. Klicken Sie auf das "+"-Symbol oder "Neue Buchung"
3. Wählen Sie folgende Informationen aus:
   - Artikel (aus Dropdown-Liste)
   - Startdatum und -zeit
   - Enddatum und -zeit
   - Schulstunden/Perioden (optional)
   - Notizen (Grund der Ausleihe, etc.)
4. Klicken Sie auf "Buchung erstellen"
5. Der Termin erscheint farblich markiert im Kalender

### QR-Code-System

#### QR-Codes drucken
1. Loggen Sie sich als Administrator ein
2. Navigieren Sie zu einem Artikel
3. Klicken Sie auf "QR-Code anzeigen"
4. Verwenden Sie die Druckfunktion Ihres Browsers (Ctrl+P)
5. Drucken Sie den QR-Code und befestigen Sie ihn am Artikel

#### QR-Codes scannen
1. Loggen Sie sich im System ein
2. Klicken Sie auf "QR-Code scannen"
3. Erlauben Sie den Kamerazugriff
4. Richten Sie die Kamera auf den QR-Code
5. Das System öffnet automatisch die Artikeldetails
6. Sie können dann den Artikel ausleihen oder zurückgeben

### Berichterstellung und Protokollierung

#### Ausleihhistorie anzeigen
1. Loggen Sie sich als Administrator ein
2. Navigieren Sie zu "Protokolle"
3. Filtern Sie nach Bedarf:
   - Nach Zeitraum
   - Nach Benutzer
   - Nach Artikel
4. Die Liste zeigt:
   - Ausgeliehene Artikel
   - Ausleihdatum und -zeit
   - Rückgabedatum und -zeit
   - Benutzer

### Datensicherung und Wiederherstellung

#### Manuelles Backup erstellen
1. Führen Sie das Backup-Skript aus:
   ```bash
   sudo ./update.sh
   ```
   
2. Das Backup wird erstellt unter:
   ```
   /var/backups/Inventarsystem-YYYY-MM-DD.tar.gz
   ```

#### Backup wiederherstellen
1. Zeigen Sie verfügbare Backups an:
   ```bash
   sudo ./restore.sh --list
   ```
   
2. Wählen Sie ein Backup zum Wiederherstellen:
   ```bash
   sudo ./restore.sh --date=2025-07-15
   ```
   
   ODER für das neueste Backup:
   ```bash
   sudo ./restore.sh --date=latest
   ```
   
3. Starten Sie das System neu:
   ```bash
   sudo ./restart.sh
   ```

### Wartung und Updates

#### System aktualisieren
1. Navigieren Sie zum Installationsverzeichnis:
   ```bash
   cd /pfad/zum/Inventarsystem
   ```
   
2. Führen Sie das Update-Skript aus:
   ```bash
   sudo ./update.sh
   ```
   
3. Das Skript unterstützt verschiedene Parameter:
   ```bash
   sudo ./update.sh --restart-server        # Mit automatischem Neustart der Dienste
   sudo ./update.sh --compression-level=5   # Mit angepasstem Kompressionslevel (0-9)
   sudo ./update.sh --help                  # Hilfe und weitere Optionen anzeigen
   ```
   
4. Das Skript führt folgende Aktionen aus:
   - Erstellt ein Backup des aktuellen Systems
   - Holt die neuesten Änderungen vom Git-Repository
   - Installiert erforderliche Abhängigkeiten
   - Behebt mögliche Konflikte zwischen pymongo und bson
   - Korrigiert Berechtigungen für kritische Verzeichnisse
   - Startet die Dienste neu (falls --restart-server angegeben wurde)

#### Virtuelle Umgebung neu aufbauen
Falls Probleme mit Python-Abhängigkeiten auftreten:

1. Führen Sie das Rebuild-Skript aus:
   ```bash
   sudo ./rebuild-venv.sh
   ```
   
2. Das Skript führt automatisch folgende Schritte aus:
   - Sichert die alte virtuelle Umgebung in `.venv_backup_[Zeitstempel]`
   - Erstellt eine neue virtuelle Umgebung
   - Installiert alle erforderlichen Pakete aus requirements.txt
   - Löst potenzielle Konflikte zwischen pymongo und bson
   - Setzt korrekte Berechtigungen für alle Dateien
   - Verifiziert die neue Umgebung mit einem Testlauf
   - Löscht die Backup-Umgebung nach erfolgreicher Überprüfung
   
3. Nach Abschluss starten Sie das System neu:
   ```bash
   sudo ./restart.sh
   ```

#### Berechtigungen korrigieren
Bei Zugriffsfehlern:

1. Führen Sie das Berechtigungskorrekturs-Skript aus für grundlegende Berechtigungen:
   ```bash
   sudo ./fix-permissions.sh
   ```
   
2. Für eine umfassende Korrektur aller Berechtigungsprobleme nutzen Sie:
   ```bash
   sudo ./fix-all-permissions.sh
   ```
   Dieses Skript behebt alle bekannten Berechtigungsprobleme im gesamten System, einschließlich:
   - Logs-Verzeichnisse und Dateien
   - Skript-Ausführungsrechte
   - Git Repository-Berechtigungen
   - Web-Upload-Verzeichnisse
   - QR-Code-Verzeichnisse
   - Thumbnails und Vorschaubilder
   - Python virtuelle Umgebung
   - MongoDB-Zugriffsrechte

3. Stellen Sie sicher, dass das Logs-Verzeichnis korrekte Berechtigungen hat:
   ```bash
   sudo chmod 777 logs
   ```

#### Log-Dateien überprüfen
1. System-Logs anzeigen:
   ```bash
   sudo journalctl -u inventarsystem-gunicorn.service -f
   sudo journalctl -u inventarsystem-nginx.service -f
   ```
   
2. Anwendungs-Logs anzeigen:
   ```bash
   tail -n 50 logs/error.log
   tail -n 50 logs/access.log
   ```

### Filter und Kategorien verwalten

#### Filter-Kategorien hinzufügen
1. Loggen Sie sich als Administrator ein
2. Navigieren Sie zu "Filter verwalten"
3. Wählen Sie die Filter-Kategorie aus (1, 2 oder 3)
4. Geben Sie neue Filterwerte ein
5. Klicken Sie auf "Speichern"

#### Standorte verwalten
1. Loggen Sie sich als Administrator ein
2. Navigieren Sie zu "Standorte verwalten"
3. Geben Sie neue Standorte ein oder bearbeiten/löschen Sie bestehende
4. Klicken Sie auf "Speichern"

### Benutzerdefinierte Anpassungen

#### Systemeinstellungen ändern
1. Öffnen Sie die Konfigurationsdatei:
   ```bash
   sudo nano config.json
   ```
   
2. Passen Sie folgende Einstellungen nach Bedarf an:
   - `dbg`: Debug-Modus (true/false)
   - `key`: Geheimer Schlüssel für Session-Sicherheit
   - `ver`: Versionsnummer
   - `host`: Host-Adresse (0.0.0.0 für alle Schnittstellen)
   - `port`: Port-Nummer (Standard: 443 für HTTPS)
   - `schoolPeriods`: Definition der Schulstunden

3. Speichern Sie die Datei und starten Sie das System neu:
   ```bash
   sudo ./restart.sh
   ```

#### SSL-Zertifikate aktualisieren
1. Platzieren Sie Ihre neuen Zertifikatsdateien in den Ordner `certs/`:
   - `inventarsystem.crt` (Zertifikat)
   - `inventarsystem.key` (Privater Schlüssel)
   
2. Stellen Sie sicher, dass die Dateien die korrekten Berechtigungen haben:
   ```bash
   sudo chmod 600 certs/inventarsystem.key
   sudo chmod 644 certs/inventarsystem.crt
   ```

3. Aktualisieren Sie die Nginx-Konfiguration (falls erforderlich):
   ```bash
   sudo nano /etc/nginx/sites-available/inventarsystem
   ```

4. Starten Sie das System neu:
   ```bash
   sudo ./restart.sh
   ```

5. Überprüfen Sie die SSL-Konfiguration:
   ```bash
   openssl s_client -connect localhost:443 -servername localhost
   ```

#### Systemsicherung und Disaster Recovery

1. **Vollständige Systemsicherung erstellen**:
   ```bash
   sudo ./update.sh --full-backup
   ```

2. **Notfall-Wiederherstellung nach Systemausfall**:
   ```bash
   # System neu installieren (falls erforderlich)
   wget -O - https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
   
   # Zum Installationsverzeichnis wechseln
   cd /pfad/zum/Inventarsystem
   
   # Backup wiederherstellen
   sudo ./restore.sh --date=latest --full
   
   # System neu starten
   sudo ./restart.sh
   ```

3. **Regelmäßige Backups planen**:
   ```bash
   # Crontab bearbeiten
   sudo crontab -e
   
   # Tägliches Backup um 3:00 Uhr morgens hinzufügen
   0 3 * * * cd /pfad/zum/Inventarsystem && ./update.sh --backup-only >> logs/backup.log 2>&1
   ```

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

### Häufige Probleme und Lösungen

#### Webserver startet nicht
Wenn der Webserver nach einem Neustart oder Update nicht startet:

1. **Status der Dienste prüfen**:
   ```bash
   sudo systemctl status inventarsystem-gunicorn.service
   sudo systemctl status inventarsystem-nginx.service
   ```

2. **Log-Dateien auf Fehler prüfen**:
   ```bash
   sudo tail -n 50 /var/log/nginx/error.log
   sudo tail -n 50 logs/error.log
   ```

3. **Dienste neu starten**:
   ```bash
   sudo ./restart.sh
   ```

4. **Berechtigungen korrigieren**:
   ```bash
   sudo ./fix-permissions.sh
   ```

#### Datenbank-Verbindungsprobleme
Bei Fehlermeldungen bezüglich der MongoDB-Verbindung:

1. **MongoDB-Status überprüfen**:
   ```bash
   sudo systemctl status mongodb
   ```

2. **MongoDB neu starten**:
   ```bash
   sudo systemctl restart mongodb
   ```

3. **Konfiguration überprüfen**:
   ```bash
   sudo nano config.json
   ```

#### Fehler bei Bildoperationen
Bei Problemen beim Bild-Upload oder QR-Code-Generierung:

1. **Berechtigungen der Upload-Verzeichnisse überprüfen**:
   ```bash
   sudo ls -la Web/uploads
   sudo ls -la Web/QRCodes
   ```

2. **Berechtigungen korrigieren**:
   ```bash
   sudo chmod -R 755 Web/uploads
   sudo chmod -R 755 Web/QRCodes
   ```

3. **Log-Dateien auf spezifische Fehler prüfen**:
   ```bash
   sudo tail -n 100 logs/error.log | grep "image"
   sudo tail -n 100 logs/error.log | grep "upload"
   ```

#### Anmelde-/Authentifizierungsprobleme
Bei Problemen mit der Benutzeranmeldung:

1. **Session-Cookies löschen** im Browser des Benutzers

2. **Admin-Benutzer zurücksetzen**:
   ```bash
   source .venv/bin/activate
   python Web/generate_user.py
   ```

3. **MongoDB-Benutzerdaten überprüfen**:
   ```bash
   source .venv/bin/activate
   python -c "from pymongo import MongoClient; print(list(MongoClient().Inventarsystem.users.find({}, {'Username': 1, 'Admin': 1, '_id': 0})))"
   ```

### Fehlerbehebung

#### PyMongo/Bson Konflikt beheben

Es kann zu einem Konflikt zwischen den Paketen `pymongo` und `bson` kommen, der sich durch folgende Fehlermeldung äußert:
```
ImportError: cannot import name '_get_object_size' from 'bson'
```

Dieser Konflikt tritt auf, wenn das separate `bson`-Paket zusammen mit `pymongo` installiert ist, wobei `pymongo` bereits seine eigene Version von `bson` enthält.

##### Schritte zur Fehlerbehebung:

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

#### Berechtigungsprobleme beheben

Wenn Sie Berechtigungsfehler wie `Keine Berechtigung` oder `Permission denied` sehen:

1. **Umfassende Berechtigung-Reparatur durchführen**:
   ```bash
   sudo ./fix-all-permissions.sh
   ```
   Dieses Skript behebt systematisch alle bekannten Berechtigungsprobleme im gesamten System und loggt alle Aktionen in `logs/permission_fixes.log`.

2. **Alternativ: Gezielte Berechtigungskorrektur**:
   ```bash
   sudo ./fix-permissions.sh
   ```
   Dieses Skript korrigiert die Berechtigungen primär für die virtuelle Umgebung und kritische Verzeichnisse.

3. **Logs-Verzeichnis manuell korrigieren**:
   ```bash
   sudo mkdir -p logs
   sudo chmod 777 logs
   ```

4. **Falls Python-Skripte nicht ausgeführt werden können**:
   ```bash
   sudo chmod +x *.py
   sudo chmod +x *.sh
   ```

5. **Git Repository-Probleme beheben**:
   ```bash
   git config --global --add safe.directory "$(pwd)"
   ```

#### Backup und Wiederherstellung testen

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

#### Überprüfung der MongoDB-Installation

1. **MongoDB-Status überprüfen**:
   ```bash
   sudo systemctl status mongodb
   ```

2. **MongoDB-Verbindung testen**:
   ```bash
   source .venv/bin/activate
   python -c "from pymongo import MongoClient; print('MongoDB connection successful' if MongoClient().server_info() else 'Failed')"
   ```

3. **MongoDB-Version überprüfen**:
   ```bash
   mongod --version
   ```

4. **MongoDB-Protokolle überprüfen**:
   ```bash
   sudo journalctl -u mongodb
   ```

5. **MongoDB-Reparatur bei Beschädigung**:
   ```bash
   sudo systemctl stop mongodb
   sudo mongod --repair --dbpath /var/lib/mongodb
   sudo systemctl start mongodb
   ```

#### Probleme mit dem Backup-System

1. **Backup-Verzeichnis überprüfen**:
   ```bash
   ls -la /var/backups/
   ```

2. **Speicherplatz überprüfen**:
   ```bash
   df -h
   ```

3. **Backup manuell erzwingen**:
   ```bash
   sudo ./update.sh --force-backup
   ```

4. **Backup entpacken und inspizieren**:
   ```bash
   mkdir -p ~/temp_backup
   sudo tar -xzf /var/backups/Inventarsystem-YYYY-MM-DD.tar.gz -C ~/temp_backup
   ls -la ~/temp_backup
   ```

#### Beispiel: Beheben von Bild-Upload und QR-Code Problemen

Wenn Probleme bei Bild-Uploads oder der QR-Code Generierung auftreten:

1. **Überprüfen Sie die Verzeichnisstruktur**:
   ```bash
   sudo ls -la Web/uploads Web/QRCodes Web/thumbnails Web/previews
   ```
   
2. **Fehlende Verzeichnisse anlegen**:
   ```bash
   sudo mkdir -p Web/uploads Web/QRCodes Web/thumbnails Web/previews
   ```
   
3. **Berechtigungen umfassend korrigieren**:
   ```bash
   sudo ./fix-all-permissions.sh
   ```
   
4. **Oder gezielte Korrektur für Bildverzeichnisse**:
   ```bash
   sudo chmod -R 755 Web/uploads Web/QRCodes Web/thumbnails Web/previews
   sudo chown -R $(whoami):$(whoami) Web/uploads Web/QRCodes Web/thumbnails Web/previews
   ```
   
5. **System neustarten und testen**:
   ```bash
   sudo ./restart.sh
   ```
   
   Testen Sie dann den Bild-Upload und die QR-Code Generierung erneut.

## Änderungsprotokoll

### Version 2.5.18
- Verbesserte Berechtigungsverwaltung mit dem neuen `fix-all-permissions.sh` Skript
- Erweiterte Backup- und Wiederherstellungsfunktionen in `update.sh`
- Unterstützung für anpassbare Kompressionslevel bei Backups (`--compression-level`)
- Robustere Fehlerbehebung bei pymongo/bson-Konflikten
- Automatische Korrektur von Gitrepository-Berechtigungen
- Verbesserte Logik bei Fehlern in der virtuellen Umgebung

## Schlussfolgerung

Das Inventarsystem ist eine komplette Lösung für die Verwaltung von Inventar, mit besonderem Fokus auf Bildungseinrichtungen. Es bietet robuste Werkzeuge für das Ausleihen, Zurückgeben und Verfolgen von Gegenständen, sowie umfassende Administratorfunktionen.

Mit den verbesserten Wartungsskripten ist das System jetzt noch zuverlässiger und einfacher zu warten, selbst bei komplexen Installationen. Die automatischen Berechtigungskorrekturen und Backup-Funktionen sorgen für eine reibungslose Benutzererfahrung und Datensicherheit.

Für weitere Unterstützung oder Feature-Anfragen öffnen Sie bitte ein Issue im GitHub-Repository.
