# Inventarsystem

[![wakatime](https://wakatime.com/badge/user/30b8509f-5e17-4d16-b6b8-3ca0f3f936d3/project/8a380b7f-389f-4a7e-8877-0fe9e1a4c243.svg)](https://wakatime.com/badge/user/30b8509f-5e17-4d16-b6b8-3ca0f3f936d3/project/8a380b7f-389f-4a7e-8877-0fe9e1a4c243)

**Aktuelle Version: 3.0.2**

Ein modernes webbasiertes Inventarverwaltungssystem zur Verwaltung, Ausleihe, Reservierung und Rückgabe von Gegenständen.
Das System richtet sich insbesondere an Bildungseinrichtungen, Organisationen und Labore.

---

## Inhaltsverzeichnis

- [Systemübersicht](#systemübersicht)
- [Hauptfunktionen](#hauptfunktionen)
- [Installation](#installation)
- [Erste Einrichtung](#erste-einrichtung)
- [Systembetrieb](#systembetrieb)
- [Benutzerverwaltung](#benutzerverwaltung)
- [Artikelverwaltung](#artikelverwaltung)
- [Buchungssystem](#buchungssystem)
- [Backup & Wiederherstellung](#backup--wiederherstellung)
- [Wartung & Updates](#wartung--updates)
- [Versionsverwaltung](#versionsverwaltung)
- [Konfiguration](#konfiguration)
- [Fehlerbehebung](#fehlerbehebung)
- [Systemanforderungen](#systemanforderungen)
- [Lizenz Rechtliches & Datenschutz](#lizenz-rechtliches--datenschutz)

---

## Systemübersicht

Das Inventarsystem stellt folgende Wartungsskripte bereit:

| Skript | Beschreibung |
|---|---|
| `update.sh` | Aktualisiert System + Backup |
| `fix-all.sh` | Intelligentes Reparaturskript |
| `rebuild-venv.sh` | Python-Umgebung neu erstellen |
| `start.sh` | Dienste starten |
| `stop.sh` | Dienste stoppen |
| `restart.sh` | Dienste neu starten |
| `Backup-DB.py` | Manuelles DB-Backup |
| `restore.sh` | Backup wiederherstellen |
| `manage-version.sh` | Versionssteuerung |

---

## Hauptfunktionen

### Benutzeranmeldung

- Sichere Passwortregeln (mindestens 6 Zeichen)
- Rollenbasiertes System
  - Administrator
  - Standardbenutzer
- Session-basierte Authentifizierung

### Artikelverwaltung

- Artikel hinzufügen / löschen
- Ausleihen & Rückgabe
- Metadatenverwaltung
- Anschaffungsdaten (Jahr, Kosten)
- Mehrfach-Bildupload
- UUID-basierte Dateinamen
- Detaillierte Artikelansicht

### Buchungssystem

- Konfliktprüfung
- Automatische Aktivierung
- Automatische Beendigung
- Kalenderansicht
- Perioden-Unterstützung (Schulstunden)

### Barcode-Scanner

- Integrierter Scanner
- Schnelles Auffinden von Artikeln
- Mobile-optimiert

### Filtersystem

- Dreistufige Filter
- Kombinierbare Suche
- Kategorie-Management

### Administrator-Tools

- Benutzerverwaltung
- Ausleihprotokolle
- Artikel-Reset
- Standortverwaltung

### Responsive Design

- Mobil optimiert
- Touch-freundlich
- Desktop-fähig

---

## Installation

### Voraussetzungen

- Python >= 3.7
- MongoDB
- pip
- Linux-System (empfohlen)

### Installation (automatisch)

**Option 1**

```bash
wget -O - https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
```

**Option 2**

```bash
curl -s https://raw.githubusercontent.com/aiirondev/Inventarsystem/main/install.sh | sudo bash
```

---

## Erste Einrichtung

Nach der Installation:

```bash
cd /opt/Inventarsystem
sudo ./start.sh
```

Öffnen Sie dann im Browser:

```
https://[SERVER-IP]
```

---

## Systembetrieb

### Starten

```bash
sudo ./start.sh
```

### Stoppen

```bash
sudo ./stop.sh
```

### Neustarten

```bash
sudo ./restart.sh
```

### Status prüfen

```bash
sudo systemctl status inventarsystem-gunicorn.service
sudo systemctl status inventarsystem-nginx.service
```

---

## Benutzerverwaltung

### Erstes Admin-Konto erstellen

```bash
cd /pfad/zum/Inventarsystem
source .venv/bin/activate
python Web/generate_user.py
```

### Benutzer über GUI hinzufügen

1. Als Admin anmelden
2. Benutzer verwalten
3. Neuen Benutzer hinzufügen
4. Daten eingeben
5. Speichern

---

## Artikelverwaltung

### Artikel hinzufügen

1. Admin anmelden
2. Artikel hochladen
3. Formular ausfüllen
4. Bilder hochladen
5. Speichern

### Unterstützte Formate

- JPG / JPEG
- PNG
- GIF
- MP4
- MOV

### Artikel bearbeiten

1. Bearbeitungssymbol klicken
2. Änderungen speichern

### Artikel löschen

1. Mülleimer klicken
2. Bestätigen

---

## Buchungssystem

### Artikel ausleihen

1. Artikel öffnen
2. Ausleihen klicken

Das System protokolliert automatisch.

### Artikel zurückgeben

1. Meine ausgeliehenen Artikel öffnen
2. Zurückgeben klicken

### Buchung planen

1. Terminplan öffnen
2. Zeitraum wählen
3. Speichern

---

## Backup & Wiederherstellung

### Backup erstellen

```bash
sudo ./update.sh
```

Backup-Pfad:

```
/var/backups/Inventarsystem-YYYY-MM-DD.tar.gz
```

### Backup wiederherstellen

```bash
sudo ./restore.sh --list
sudo ./restore.sh --date=latest
sudo ./restart.sh
```

---

## Wartung & Updates

### System aktualisieren

```bash
sudo ./update.sh
```

Optionen:

```bash
--restart-server
--compression-level=5
--help
```

### Virtuelle Umgebung neu erstellen

```bash
sudo ./rebuild-venv.sh
sudo ./restart.sh
```

### Komplettreparatur

```bash
sudo ./fix-all.sh
```

---

## Versionsverwaltung

Mit `manage-version.sh` können Sie gezielt Versionen steuern, Downgrades durchführen und Versionen pinnen.

### Beispiele

```bash
# Dauerhaft auf eine Version (Tag, Commit oder Branch) pinnen
./manage-version.sh pin v2.5.17 --restart

# Einmalig auf eine Version wechseln
./manage-version.sh use <ref> --restart

# Aktuellen Status anzeigen
./manage-version.sh status

# Pin entfernen und zur Hauptversion zurückkehren
./manage-version.sh clear --restart
```

### Wichtige Hinweise

- Pin wird in `.version-lock` gespeichert
- Unterstützt: Tags, Branches, Commits
- Erstellt automatische Backups vor jedem Wechsel
- Bewahrt Datenverzeichnisse über den Versionswechsel hinweg

---

## Konfiguration

### config.json bearbeiten

```bash
sudo nano config.json
```

Beispiel:

```json
{
  "dbg": false,
  "key": "IhrGeheimSchlüssel",
  "ver": "2.6.2",
  "host": "0.0.0.0",
  "port": 443
}
```

### SSL aktualisieren

```bash
sudo chmod 600 certs/inventarsystem.key
sudo chmod 644 certs/inventarsystem.crt
```

---

## Fehlerbehebung

### Webserver startet nicht

```bash
sudo systemctl status inventarsystem-gunicorn.service
sudo systemctl status inventarsystem-nginx.service
```

### MongoDB-Probleme

```bash
sudo systemctl restart mongodb
```

### PyMongo/BSON-Konflikt

```bash
sudo ./fix-all.sh
```

oder

```bash
sudo ./rebuild-venv.sh
```

### Bild-Upload Probleme

```bash
sudo ./fix-all.sh
```

Verzeichnisse prüfen:

```bash
sudo ls -la Web/uploads
sudo ls -la Web/QRCodes
sudo ls -la Web/thumbnails
```

### Empfohlener Troubleshooting-Workflow

1. Status prüfen
2. Logs prüfen
3. `fix-all.sh` ausführen
4. Neustarten

Automatische Überwachung einrichten:

```bash
sudo ./fix-all.sh --setup-cron
```

---

## Systemanforderungen

- Moderner Webbrowser (Chrome, Firefox, Safari, Edge)
- Internetzugang
- Kamera für QR-Scan
- Desktop empfohlen für Admins

---

## Lizenz Rechtliches & Datenschutz

Dieses Projekt ist auf Transparenz und Datensparsamkeit ausgelegt. Um einen rechtskonformen Betrieb (insbesondere gemäß DSGVO) zu gewährleisten, wurden folgende Dokumente erstellt:

* **[Lizenz](./Legal/LICENSE)** 

* **[Datenschutzerklärung](./Legal/PRIVACY.md):** Erläutert, welche personenbezogenen Daten (z. B. Inventarzuordnungen, Logins) verarbeitet werden.
* **[Datenverarbeitung & Dokumentation](./Legal/DATA_PROCESSING.md):** Details zu den technischen Abläufen und Speichermechanismen innerhalb des Systems.
* **[Rechtsgrundlage](./Legal/LEGAL_BASIS.md):** Informationen für Administratoren zur rechtmäßigen Nutzung im geschäftlichen oder privaten Umfeld.
* **[Sicherheit & Mechanismen](./Legal/SECURITY.md):** Übersicht der implementierten Schutzmaßnahmen (Hashing, Zugriffskontrolle).

> **Wichtiger Hinweis:** Die bereitgestellten Dokumente dienen als Vorlage. Als Betreiber einer Instanz dieses Inventarsystems sind Sie selbst dafür verantwortlich, diese an Ihre spezifische Hosting-Umgebung und Ihre internen Prozesse anzupassen.

---

## Mitwirkende

**Maximilian Gründinger** — Projektgründer

Für technische Unterstützung oder Fragen bitte ein Issue im GitHub-Repository eröffnen.

---

Das Inventarsystem ist eine robuste, wartungsfreundliche Komplettlösung für Inventarverwaltung mit Fokus auf Bildungseinrichtungen.
Durch automatisierte Wartung, integrierte Backups und intelligente Diagnose lässt sich das System zuverlässig betreiben und skalieren.
