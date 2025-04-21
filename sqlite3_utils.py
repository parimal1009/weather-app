import sqlite3
import json
from datetime import datetime

class WeatherDB:
    def __init__(self, db_name='weather_app.db'):
        self.db_name = db_name
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize database tables if they don't exist"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            
            # Main weather queries table
            c.execute('''CREATE TABLE IF NOT EXISTS weather_queries
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          location TEXT,
                          latitude REAL,
                          longitude REAL,
                          query_date TEXT,
                          date_from TEXT,
                          date_to TEXT,
                          weather_data TEXT,
                          notes TEXT,
                          tags TEXT,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # User preferences table
            c.execute('''CREATE TABLE IF NOT EXISTS user_preferences
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          temperature_unit TEXT DEFAULT 'celsius',
                          wind_speed_unit TEXT DEFAULT 'm/s',
                          pressure_unit TEXT DEFAULT 'hPa',
                          theme TEXT DEFAULT 'light')''')
            
            # Locations table for quick access
            c.execute('''CREATE TABLE IF NOT EXISTS saved_locations
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          name TEXT,
                          address TEXT,
                          latitude REAL,
                          longitude REAL,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # Weather alerts table
            c.execute('''CREATE TABLE IF NOT EXISTS weather_alerts
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          location_id INTEGER,
                          alert_type TEXT,
                          threshold_value REAL,
                          is_active INTEGER DEFAULT 1,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          FOREIGN KEY(location_id) REFERENCES saved_locations(id))''')
            
            conn.commit()
    
    def save_weather_query(self, location, lat, lon, query_date=None, 
                          date_from=None, date_to=None, weather_data=None, 
                          notes=None, tags=None):
        """Save a weather query to the database"""
        if query_date is None:
            query_date = str(datetime.now().date())
        
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO weather_queries 
                         (location, latitude, longitude, query_date, date_from, date_to, 
                          weather_data, notes, tags)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (location, lat, lon, query_date, date_from, date_to, 
                       json.dumps(weather_data), notes, tags))
            conn.commit()
            return c.lastrowid
    
    def get_all_queries(self, limit=100, offset=0):
        """Get all saved weather queries with pagination"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM weather_queries 
                          ORDER BY created_at DESC 
                          LIMIT ? OFFSET ?''', (limit, offset))
            return [dict(row) for row in c.fetchall()]
    
    def get_query_by_id(self, query_id):
        """Get a specific weather query by ID"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM weather_queries WHERE id = ?''', (query_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def update_query(self, query_id, **kwargs):
        """Update a weather query with the provided fields"""
        if not kwargs:
            return False
        
        set_clause = ', '.join(f"{key} = ?" for key in kwargs.keys())
        values = list(kwargs.values())
        values.append(query_id)
        
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute(f'''UPDATE weather_queries 
                          SET {set_clause}
                          WHERE id = ?''', values)
            conn.commit()
            return c.rowcount > 0
    
    def delete_query(self, query_id):
        """Delete a weather query by ID"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''DELETE FROM weather_queries WHERE id = ?''', (query_id,))
            conn.commit()
            return c.rowcount > 0
    
    def save_location(self, name, address, lat, lon):
        """Save a location to the database"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO saved_locations 
                         (name, address, latitude, longitude)
                         VALUES (?, ?, ?, ?)''',
                      (name, address, lat, lon))
            conn.commit()
            return c.lastrowid
    
    def get_all_locations(self):
        """Get all saved locations"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM saved_locations ORDER BY name''')
            return [dict(row) for row in c.fetchall()]
    
    def get_location_by_id(self, location_id):
        """Get a specific location by ID"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM saved_locations WHERE id = ?''', (location_id,))
            row = c.fetchone()
            return dict(row) if row else None
    
    def delete_location(self, location_id):
        """Delete a location by ID"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''DELETE FROM saved_locations WHERE id = ?''', (location_id,))
            conn.commit()
            return c.rowcount > 0
    
    def get_user_preferences(self):
        """Get user preferences"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM user_preferences LIMIT 1''')
            row = c.fetchone()
            if row:
                return dict(row)
            
            # Insert default preferences if none exist
            default_prefs = {
                'temperature_unit': 'celsius',
                'wind_speed_unit': 'm/s',
                'pressure_unit': 'hPa',
                'theme': 'light'
            }
            c.execute('''INSERT INTO user_preferences 
                         (temperature_unit, wind_speed_unit, pressure_unit, theme)
                         VALUES (?, ?, ?, ?)''',
                      (default_prefs['temperature_unit'], 
                       default_prefs['wind_speed_unit'],
                       default_prefs['pressure_unit'],
                       default_prefs['theme']))
            conn.commit()
            return default_prefs
    
    def update_user_preferences(self, **kwargs):
        """Update user preferences"""
        if not kwargs:
            return False
        
        # First clear existing preferences
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''DELETE FROM user_preferences''')
            
            # Insert new preferences
            c.execute('''INSERT INTO user_preferences 
                         (temperature_unit, wind_speed_unit, pressure_unit, theme)
                         VALUES (?, ?, ?, ?)''',
                      (kwargs.get('temperature_unit', 'celsius'),
                       kwargs.get('wind_speed_unit', 'm/s'),
                       kwargs.get('pressure_unit', 'hPa'),
                       kwargs.get('theme', 'light')))
            conn.commit()
            return True
    
    def add_weather_alert(self, location_id, alert_type, threshold_value):
        """Add a weather alert for a location"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO weather_alerts 
                         (location_id, alert_type, threshold_value)
                         VALUES (?, ?, ?)''',
                      (location_id, alert_type, threshold_value))
            conn.commit()
            return c.lastrowid
    
    def get_alerts_for_location(self, location_id):
        """Get all alerts for a specific location"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM weather_alerts 
                          WHERE location_id = ? AND is_active = 1
                          ORDER BY created_at DESC''', (location_id,))
            return [dict(row) for row in c.fetchall()]
    
    def update_alert_status(self, alert_id, is_active):
        """Update the active status of an alert"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''UPDATE weather_alerts 
                         SET is_active = ?
                         WHERE id = ?''', (is_active, alert_id))
            conn.commit()
            return c.rowcount > 0
    
    def delete_alert(self, alert_id):
        """Delete a weather alert"""
        with sqlite3.connect(self.db_name) as conn:
            c = conn.cursor()
            c.execute('''DELETE FROM weather_alerts WHERE id = ?''', (alert_id,))
            conn.commit()
            return c.rowcount > 0
    
    def search_queries(self, search_term, limit=50):
        """Search weather queries by location or tags"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM weather_queries 
                          WHERE location LIKE ? OR tags LIKE ?
                          ORDER BY created_at DESC
                          LIMIT ?''', 
                      (f'%{search_term}%', f'%{search_term}%', limit))
            return [dict(row) for row in c.fetchall()]
    
    def get_queries_by_date_range(self, start_date, end_date):
        """Get queries created within a date range"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM weather_queries 
                          WHERE date(created_at) BETWEEN ? AND ?
                          ORDER BY created_at DESC''', 
                      (start_date, end_date))
            return [dict(row) for row in c.fetchall()]
    
    def get_queries_by_location(self, location_id):
        """Get queries for a specific saved location"""
        with sqlite3.connect(self.db_name) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # First get the location coordinates
            c.execute('''SELECT latitude, longitude FROM saved_locations 
                          WHERE id = ?''', (location_id,))
            loc = c.fetchone()
            if not loc:
                return []
            
            # Then find queries with matching coordinates
            c.execute('''SELECT * FROM weather_queries 
                          WHERE ROUND(latitude, 4) = ROUND(?, 4)
                          AND ROUND(longitude, 4) = ROUND(?, 4)
                          ORDER BY created_at DESC''', 
                      (loc['latitude'], loc['longitude']))
            return [dict(row) for row in c.fetchall()]