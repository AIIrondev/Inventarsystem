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

## Starten des Servers nach der erst Instalation

Als erstes müssen sie in die Website Direktion navigieren.
Anschließend führen sie den folgenden Comand aus:

```bash
sudo ./start-codespace.sh
```

## Optionale Autostart funktion(not finisched)

** Warnung nicht Fertig, mögliche Fehler die zu System Fehlern führen können ** 

Starten sie mit dem folgenden Comand den automatischen prozess:

```bash
sudo ./update.sh
```

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
