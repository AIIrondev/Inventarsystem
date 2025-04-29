"""
Ausleihungssystem (Borrowing System)
====================================

Dieses Modul verwaltet sämtliche Ausleihungen im Inventarsystem.
Es bietet alle Funktionen, um Ausleihungen zu planen, zu aktivieren,
zu beenden und zu stornieren.

Hauptfunktionen:
- Erstellen neuer Ausleihungen (geplant oder sofort aktiv)
- Aktualisieren von Ausleihungsdaten
- Abschließen von Ausleihungen (Rückgabe)
- Suchen und Abrufen von Ausleihungen nach verschiedenen Kriterien
- Verwaltung des Ausleihungs-Lebenszyklus

Sammlungsstruktur:
- ausleihungen: Speichert alle Ausleihungsdatensätze mit ihrem Status
  - Status-Werte: 'planned' (geplant), 'active' (aktiv), 'completed' (abgeschlossen), 'cancelled' (storniert)
"""
'''
   Copyright 2025 Maximilian Gründinger

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
'''
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime


# === AUSLEIHUNG MANAGEMENT ===

def add_ausleihung(item_id, user_id, start, end=None, notes="", status="active", period=None):
    """
    Erstellt einen neuen Ausleihungsdatensatz in der Datenbank.
    Je nach Status wird eine aktive Ausleihe oder eine geplante Reservierung erstellt.
    
    Args:
        item_id (str): ID des auszuleihenden Gegenstands
        user_id (str): ID oder Benutzername des Ausleihers
        start (datetime): Startdatum/-zeit der Ausleihperiode
        end (datetime, optional): Enddatum/-zeit der Ausleihperiode
        notes (str, optional): Zusätzliche Notizen zu dieser Ausleihe
        status (str, optional): Status der Ausleihe ('planned', 'active', 'completed', 'cancelled')
        period (int, optional): Schulstunde (1-10) der Ausleihung
        
    Returns:
        ObjectId: ID des neuen Ausleihungsdatensatzes
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        ausleihung_data = {
            'Item': item_id,
            'User': user_id,
            'Start': start,
            'End': end,
            'Notes': notes,
            'Status': status,
            'Created': datetime.datetime.now(),
            'LastUpdated': datetime.datetime.now()
        }
        
        # Add period if provided
        if period is not None:
            ausleihung_data['Period'] = int(period)
        
        result = ausleihungen.insert_one(ausleihung_data)
        ausleihung_id = result.inserted_id
        
        client.close()
        return ausleihung_id
    except Exception as e:
        # print(f"Error adding ausleihung: {e}") # Log the error
        return None


def update_ausleihung(id, item_id=None, user_id=None, start=None, end=None, notes=None, status=None, period=None):
    """
    Aktualisiert einen bestehenden Ausleihungsdatensatz.
    Nur die angegebenen Felder werden aktualisiert.
    
    Args:
        id (str): ID des zu aktualisierenden Ausleihungsdatensatzes
        item_id (str, optional): ID des ausgeliehenen Gegenstands
        user_id (str, optional): ID oder Benutzername des Ausleihers
        start (datetime, optional): Startdatum/-zeit der Ausleihperiode
        end (datetime, optional): Enddatum/-zeit der Ausleihperiode
        notes (str, optional): Zusätzliche Notizen zu dieser Ausleihe
        status (str, optional): Status der Ausleihe
        period (int, optional): Schulstunde (1-10) der Ausleihung
        
    Returns:
        bool: True bei Erfolg, sonst False
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        update_data = {'LastUpdated': datetime.datetime.now()}
        
        # Nur angegebene Felder aktualisieren
        if item_id is not None:
            update_data['Item'] = item_id
        if user_id is not None:
            update_data['User'] = user_id
        if start is not None:
            update_data['Start'] = start
        if end is not None:
            update_data['End'] = end
        if notes is not None:
            update_data['Notes'] = notes
        if status is not None:
            update_data['Status'] = status
        if period is not None:
            update_data['Period'] = int(period)
            
        result = ausleihungen.update_one(
            {'_id': ObjectId(id)}, 
            {'$set': update_data}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        # print(f"Error updating ausleihung: {e}") # Log the error
        return False


def complete_ausleihung(id, end_time=None):
    """
    Markiert eine Ausleihe als abgeschlossen, indem das Enddatum gesetzt 
    und der Status auf 'completed' geändert wird.
    
    Args:
        id (str): ID des abzuschließenden Ausleihungsdatensatzes
        end_time (datetime, optional): Endzeitpunkt (Standard: aktuelle Zeit)
        
    Returns:
        bool: True bei Erfolg, sonst False
    """
    try:
        if end_time is None:
            end_time = datetime.datetime.now()
            
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        result = ausleihungen.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'End': end_time,
                'Status': 'completed',
                'LastUpdated': datetime.datetime.now()
            }}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        # print(f"Error completing ausleihung: {e}") # Log the error
        return False


def cancel_ausleihung(id):
    """
    Storniert eine geplante Ausleihe durch Änderung des Status auf 'cancelled'.
    
    Args:
        id (str): ID der zu stornierenden Ausleihe
        
    Returns:
        bool: True bei Erfolg, sonst False
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        result = ausleihungen.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'Status': 'cancelled',
                'LastUpdated': datetime.datetime.now()
            }}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        # print(f"Error cancelling ausleihung: {e}") # Log the error
        return False


def remove_ausleihung(id):
    """
    Entfernt einen Ausleihungsdatensatz aus der Datenbank.
    Hinweis: Normalerweise ist es besser, Datensätze zu markieren als sie zu löschen.
    
    Args:
        id (str): ID des zu entfernenden Ausleihungsdatensatzes
        
    Returns:
        bool: True bei Erfolg, sonst False
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        result = ausleihungen.delete_one({'_id': ObjectId(id)})
        client.close()
        return result.deleted_count > 0
    except Exception as e:
        # print(f"Error removing ausleihung: {e}") # Log the error
        return False


# === AUSLEIHUNG RETRIEVAL ===

def get_ausleihung(id):
    """
    Ruft einen bestimmten Ausleihungsdatensatz anhand seiner ID ab.
    
    Args:
        id (str): ID des abzurufenden Ausleihungsdatensatzes
        
    Returns:
        dict: Der Ausleihungsdatensatz oder None, wenn nicht gefunden
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        ausleihung = ausleihungen.find_one({'_id': ObjectId(id)})
        client.close()
        return ausleihung
    except Exception as e:
        # print(f"Error retrieving ausleihung: {e}") # Log the error
        return None


def get_ausleihungen(status=None, start=None, end=None, date_filter='overlap'):
    """
    Ruft Ausleihungen nach verschiedenen Kriterien ab.
    
    Args:
        status (str/list, optional): Status(se) der Ausleihungen ('planned', 'active', 'completed', 'cancelled')
        start (str/datetime, optional): Startdatum für Datumsfilterung
        end (str/datetime, optional): Enddatum für Datumsfilterung
        date_filter (str, optional): Art des Datumsfilters ('overlap', 'start_in', 'end_in', 'contained')
        
    Returns:
        list: Liste von Ausleihungsdatensätzen
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        collection = db['ausleihungen']
        
        # Query erstellen
        query = {}
        
        # Status-Filter hinzufügen
        if status is not None:
            if isinstance(status, list):
                query['Status'] = {'$in': status}
            else:
                query['Status'] = status
        
        # Datum parsen, wenn als String angegeben
        if start is not None and isinstance(start, str):
            try:
                from dateutil import parser
                start = parser.parse(start)
            except:
                start = None
                
        if end is not None and isinstance(end, str):
            try:
                from dateutil import parser
                end = parser.parse(end)
            except:
                end = None
        
        # Datumsfilter hinzufügen
        if start is not None and end is not None:
            if date_filter == 'overlap':
                # Überlappende Ausleihungen (Standard)
                query['$or'] = [
                    # Ausleihe beginnt im Bereich
                    {'Start': {'$gte': start, '$lte': end}},
                    # Ausleihe endet im Bereich
                    {'End': {'$gte': start, '$lte': end}},
                    # Ausleihe umfasst den gesamten Bereich
                    {'Start': {'$lte': start}, 'End': {'$gte': end}},
                    # Aktive Ausleihungen ohne Ende, die vor dem Ende beginnen
                    {'Start': {'$lte': end}, 'End': None}
                ]
            elif date_filter == 'start_in':
                # Nur Ausleihungen, die im Bereich beginnen
                query['Start'] = {'$gte': start, '$lte': end}
            elif date_filter == 'end_in':
                # Nur Ausleihungen, die im Bereich enden
                query['End'] = {'$gte': start, '$lte': end}
            elif date_filter == 'contained':
                # Nur Ausleihungen, die vollständig im Bereich liegen
                query['Start'] = {'$gte': start}
                query['End'] = {'$lte': end}
        
        results = list(collection.find(query))
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving ausleihungen: {e}") # Log the error
        return []


def get_active_ausleihungen(start=None, end=None):
    """
    Ruft alle aktiven (laufenden) Ausleihungen ab.
    
    Args:
        start (str/datetime, optional): Startdatum für Datumsfilterung
        end (str/datetime, optional): Enddatum für Datumsfilterung
        
    Returns:
        list: Liste aktiver Ausleihungsdatensätze
    """
    return get_ausleihungen(status='active', start=start, end=end)


def get_planned_ausleihungen(start=None, end=None):
    """
    Ruft alle geplanten Ausleihungen (Reservierungen) ab.
    
    Args:
        start (str/datetime, optional): Startdatum für Datumsfilterung
        end (str/datetime, optional): Enddatum für Datumsfilterung
        
    Returns:
        list: Liste geplanter Ausleihungsdatensätze
    """
    return get_ausleihungen(status='planned', start=start, end=end)


def get_completed_ausleihungen(start=None, end=None):
    """
    Ruft alle abgeschlossenen Ausleihungen ab.
    
    Args:
        start (str/datetime, optional): Startdatum für Datumsfilterung
        end (str/datetime, optional): Enddatum für Datumsfilterung
        
    Returns:
        list: Liste abgeschlossener Ausleihungsdatensätze
    """
    return get_ausleihungen(status='completed', start=start, end=end)


def get_cancelled_ausleihungen(start=None, end=None):
    """
    Ruft alle stornierten Ausleihungen ab.
    
    Args:
        start (str/datetime, optional): Startdatum für Datumsfilterung
        end (str/datetime, optional): Enddatum für Datumsfilterung
        
    Returns:
        list: Liste stornierter Ausleihungsdatensätze
    """
    return get_ausleihungen(status='cancelled', start=start, end=end)


# === SEARCH FUNCTIONS ===

def get_ausleihung_by_user(user_id, status=None):
    """
    Ruft Ausleihungen für einen bestimmten Benutzer ab.
    
    Args:
        user_id (str): ID oder Benutzername des Benutzers
        status (str/list, optional): Status(se) der Ausleihungen
        
    Returns:
        list: Liste von Ausleihungsdatensätzen des Benutzers
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        query = {'User': user_id}
        if status is not None:
            if isinstance(status, list):
                query['Status'] = {'$in': status}
            else:
                query['Status'] = status
            
        results = list(ausleihungen.find(query))
        client.close()
        return results
    except Exception as e:
        # print(f"Error retrieving ausleihungen for user {user_id}: {e}") # Log the error
        return []


def get_ausleihung_by_item(item_id, status=None, include_history=False):
    """
    Ruft Ausleihungen für einen bestimmten Gegenstand ab.
    
    Args:
        item_id (str): ID des Gegenstands
        status (str/list, optional): Status(se) der Ausleihungen
        include_history (bool): Bei True werden alle Ausleihungen zurückgegeben,
                               bei False nur die aktive/geplante
        
    Returns:
        dict/list: Die aktive Ausleihe (wenn include_history=False) 
                 oder alle Ausleihungen für diesen Gegenstand (wenn include_history=True)
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        if include_history:
            # Alle Ausleihungen für diesen Gegenstand abrufen
            query = {'Item': item_id}
            if status is not None:
                if isinstance(status, list):
                    query['Status'] = {'$in': status}
                else:
                    query['Status'] = status
                    
            results = list(ausleihungen.find(query).sort('Start', -1))  # Sort by start date, newest first
            client.close()
            return results
        else:
            # Nur die aktive Ausleihe oder geplante Reservierung abrufen
            query = {'Item': item_id}
            if status is not None:
                if isinstance(status, list):
                    query['Status'] = {'$in': status}
                else:
                    query['Status'] = status
            else:
                # Prioritize finding active borrowings first
                query['Status'] = 'active'
                
            ausleihung = ausleihungen.find_one(query)
            
            # If no active borrowing found, try planned
            if not ausleihung:
                query['Status'] = 'planned'
                ausleihung = ausleihungen.find_one(query)
            
            client.close()
            return ausleihung
    except Exception as e:
        print(f"Error retrieving ausleihungen for item {item_id}: {e}")  # Log the error
        return [] if include_history else None


def get_ausleihungen_by_date_range(start_date, end_date, status=None):
    """
    Ruft Ausleihungen ab, die in einem bestimmten Zeitraum aktiv waren.
    
    Args:
        start_date (datetime): Beginn des Zeitraums
        end_date (datetime): Ende des Zeitraums
        status (str/list, optional): Status(se) der Ausleihungen
        
    Returns:
        list: Liste von Ausleihungsdatensätzen im Zeitraum
    """
    return get_ausleihungen(status=status, start=start_date, end=end_date)


def check_ausleihung_conflict(item_id, start_date, end_date, period=None):
    """
    Prüft, ob es Konflikte mit bestehenden Ausleihungen oder aktiven Ausleihen gibt.
    
    Args:
        item_id (str): ID des zu prüfenden Gegenstands
        start_date (datetime): Vorgeschlagenes Startdatum
        end_date (datetime): Vorgeschlagenes Enddatum
        period (int, optional): Schulstunde für die Prüfung

    Returns:
        bool: True, wenn ein Konflikt besteht, sonst False
    """
    try:
        print(f"Checking booking conflict for item {item_id}, period {period}, start {start_date}, end {end_date}")
        
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        # Get the date component for filtering
        booking_date = start_date.date()
        
        # First, get all active and planned bookings for this item
        all_bookings = list(ausleihungen.find({
            'Item': item_id,
            'Status': {'$in': ['planned', 'active']}
        }))
        
        # Print all relevant bookings for debugging
        print(f"Found {len(all_bookings)} existing bookings for this item")
        for bk in all_bookings:
            bk_id = str(bk.get('_id'))
            bk_status = bk.get('Status')
            bk_period = bk.get('Period', 'None')
            bk_start = bk.get('Start')
            bk_user = bk.get('User')
            print(f"  - Booking {bk_id}: Status={bk_status}, Period={bk_period}, Start={bk_start}, User={bk_user}")

        # If we're booking by period, check for period conflicts
        if period is not None:
            period_int = int(period)
            
            # Check bookings on the same day with the same period
            for booking in all_bookings:
                booking_start = booking.get('Start')
                if not booking_start:
                    continue
                    
                # Compare just the date part
                existing_date = booking_start.date()
                if existing_date == booking_date:
                    # If this booking has the same period, it's a conflict
                    if booking.get('Period') == period_int:
                        print(f"CONFLICT: Same day, same period. Period: {period_int}, Date: {booking_date}")
                        client.close()
                        return True
        
        # If no period specified, check for time overlaps
        else:
            for booking in all_bookings:
                booking_start = booking.get('Start')
                booking_end = booking.get('End')
                
                if not booking_start:
                    continue
                
                # Set default end time if not specified
                if not booking_end:
                    booking_end = booking_start + datetime.timedelta(hours=1)
                
                # Check for overlap
                # 1. New booking starts during existing booking
                # 2. New booking ends during existing booking
                # 3. New booking completely contains existing booking
                # 4. Existing booking completely contains new booking
                if ((start_date >= booking_start and start_date < booking_end) or
                    (end_date > booking_start and end_date <= booking_end) or
                    (start_date <= booking_start and end_date >= booking_end) or
                    (start_date >= booking_start and end_date <= booking_end)):
                    print(f"CONFLICT: Time overlap. New booking: {start_date}-{end_date}, Existing: {booking_start}-{booking_end}")
                    client.close()
                    return True
        
        print("No conflicts found!")
        client.close()
        return False
        
    except Exception as e:
        print(f"Error checking booking conflicts: {e}")
        import traceback
        traceback.print_exc()
        return True  # Bei Fehler Konflikt annehmen, um auf Nummer sicher zu gehen


# === AUTOMATISIERTE VERARBEITUNG ===

def get_ausleihungen_starting_now(current_time):
    """
    Ruft Ausleihungen ab, die jetzt beginnen sollen (innerhalb eines Zeitfensters).
    
    Args:
        current_time (datetime): Aktuelle Zeit für den Vergleich
    
    Returns:
        list: Liste von Ausleihungen, die jetzt beginnen sollen
    """
    try:
        # Zeitfenster definieren (1 Stunde vor und nach jetzt)
        h_1 = datetime.timedelta(hours=1)
        start_time = current_time - h_1
        end_time = current_time + h_1
        
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        query = {
            'Status': 'planned',
            'Start': {
                '$lte': end_time,
                '$gte': start_time
            }
        }
        
        bookings = list(ausleihungen.find(query))
        client.close()
        return bookings
    except Exception as e:
        return []


def get_ausleihungen_ending_now(current_time):
    """
    Ruft Ausleihungen ab, die jetzt enden sollen (innerhalb eines Zeitfensters).
    
    Args:
        current_time (datetime): Aktuelle Zeit für den Vergleich
    
    Returns:
        list: Liste von Ausleihungen, die jetzt enden sollen
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        # Zeitfenster erstellen (5 Minuten vor und nach)
        window = datetime.timedelta(minutes=5)
        start_time = current_time - window
        end_time = current_time + window
        
        # Ausleihungen finden, die:
        # 1. Den Status 'active' haben
        # 2. Ein Enddatum innerhalb dieses Zeitfensters haben
        query = {
            'Status': 'active',
            'End': {'$gte': start_time, '$lte': end_time}
        }
        
        bookings = list(ausleihungen.find(query))
        client.close()
        return bookings
    except Exception as e:
        return []


def activate_ausleihung(id):
    """
    Aktiviert eine geplante Ausleihe.
    
    Args:
        id (str): ID der zu aktivierenden Ausleihe
        
    Returns:
        bool: True bei Erfolg, sonst False
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        # Zuerst prüfen, ob die Ausleihe existiert und den Status 'planned' hat
        ausleihung = ausleihungen.find_one({'_id': ObjectId(id)})
        if not ausleihung or ausleihung.get('Status') != 'planned':
            client.close()
            return False
            
        # Ausleihe aktivieren
        result = ausleihungen.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'Status': 'active',
                'LastUpdated': datetime.datetime.now()
            }}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        return False


# === KOMPATIBILITÄTSFUNKTIONEN ===

# Hilfsmethoden für alte Funktionsaufrufe, um Abwärtskompatibilität zu gewährleisten

def add_planned_booking(item_id, user, start_date, end_date, notes="", period=None):
    """Kompatibilitätsfunktion - erstellt eine geplante Ausleihe"""
    return add_ausleihung(item_id, user, start_date, end_date, notes, status='planned', period=period)

def check_booking_conflict(item_id, start_date, end_date, period=None):
    """Kompatibilitätsfunktion - prüft auf Ausleihungskonflikte mit Periodenunterstützung"""
    return check_ausleihung_conflict(item_id, start_date, end_date, period)

def cancel_booking(booking_id):
    """Kompatibilitätsfunktion - storniert eine Ausleihe"""
    return cancel_ausleihung(booking_id)

def get_booking(booking_id):
    """Kompatibilitätsfunktion - ruft eine einzelne Ausleihe ab"""
    return get_ausleihung(booking_id)

def get_active_bookings(start=None, end=None):
    """Kompatibilitätsfunktion - ruft aktive Ausleihungen ab"""
    return get_active_ausleihungen(start, end)

def get_planned_bookings(start=None, end=None):
    """Kompatibilitätsfunktion - ruft geplante Ausleihungen ab"""
    return get_planned_ausleihungen(start, end)

def get_completed_bookings(start=None, end=None):
    """Kompatibilitätsfunktion - ruft abgeschlossene Ausleihungen ab"""
    return get_completed_ausleihungen(start, end)

def mark_booking_active(booking_id, ausleihung_id=None):
    """Kompatibilitätsfunktion - markiert eine Ausleihe als aktiv und verknüpft optional eine Ausleihungs-ID"""
    try:
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        ausleihungen = db['ausleihungen']
        
        # Basisupdate-Daten mit Status-Änderung
        update_data = {
            'Status': 'active',
            'LastUpdated': datetime.datetime.now()
        }
        
        # Wenn eine Ausleihungs-ID angegeben wurde, diese auch verknüpfen
        if ausleihung_id:
            update_data['AusleihungId'] = ausleihung_id
            
        # Update durchführen
        result = ausleihungen.update_one(
            {'_id': ObjectId(booking_id)},
            {'$set': update_data}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error activating booking: {e}")
        # Fallback zur alten Methode bei Fehlern
        return activate_ausleihung(booking_id)

def mark_booking_completed(booking_id):
    """Kompatibilitätsfunktion - markiert eine Ausleihe als abgeschlossen"""
    return complete_ausleihung(booking_id)

def get_bookings_starting_now(current_time):
    """Kompatibilitätsfunktion - ruft startende Ausleihungen ab"""
    return get_ausleihungen_starting_now(current_time)

def get_bookings_ending_now(current_time):
    """Kompatibilitätsfunktion - ruft endende Ausleihungen ab"""
    return get_ausleihungen_ending_now(current_time)