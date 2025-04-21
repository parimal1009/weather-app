import streamlit as st
import requests
import pandas as pd
import datetime
import sqlite3
import json
import csv
import os
from io import StringIO
import pytemperature
import folium
from streamlit_folium import folium_static
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


from dotenv import load_dotenv
import os

load_dotenv()

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
TIMEZONE_API_KEY = os.getenv("TIMEZONE_API_KEY")

# Database setup
def init_db():
    conn = sqlite3.connect('weather_app.db')
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
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Weather icons mapping
WEATHER_ICONS = {
    "01d": "☀️", "01n": "🌙",
    "02d": "⛅", "02n": "⛅",
    "03d": "☁️", "03n": "☁️",
    "04d": "☁️", "04n": "☁️",
    "09d": "🌧️", "09n": "🌧️",
    "10d": "🌦️", "10n": "🌦️",
    "11d": "⛈️", "11n": "⛈️",
    "13d": "❄️", "13n": "❄️",
    "50d": "🌫️", "50n": "🌫️"
}

# Helper functions
def get_coordinates(location):
    """Convert location string to coordinates using Geoapify (free tier)"""
    url = f"https://api.geoapify.com/v1/geocode/search?text={location}&apiKey={GEOAPIFY_API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data['features']:
                feature = data['features'][0]
                return feature['properties']['lat'], feature['properties']['lon'], feature['properties']
        return None, None, None
    except (GeocoderTimedOut, GeocoderServiceError, requests.exceptions.RequestException):
        return None, None, None

def get_current_weather(lat, lon):
    """Get current weather data from OpenWeather API (free tier)"""
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

def get_forecast(lat, lon):
    """Get 5-day forecast from OpenWeather API (free tier)"""
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

def get_timezone_info(lat, lon):
    """Get timezone information from TimezoneDB (free tier)"""
    url = f"http://api.timezonedb.com/v2.1/get-time-zone?key={TIMEZONE_API_KEY}&format=json&by=position&lat={lat}&lng={lon}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

def get_air_quality(lat, lon):
    """Get air quality data from OpenWeather (free tier)"""
    url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.exceptions.RequestException:
        return None

def save_to_db(location, lat, lon, query_date, date_from, date_to, weather_data, notes="", tags=""):
    """Save weather query to database with additional fields"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''INSERT INTO weather_queries 
                 (location, latitude, longitude, query_date, date_from, date_to, weather_data, notes, tags)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (location, lat, lon, query_date, date_from, date_to, json.dumps(weather_data), notes, tags))
    conn.commit()
    conn.close()

def get_all_queries():
    """Get all saved weather queries from database"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''SELECT id, location, latitude, longitude, query_date, date_from, date_to, 
                 notes, tags, created_at FROM weather_queries ORDER BY created_at DESC''')
    rows = c.fetchall()
    conn.close()
    return rows

def get_query_by_id(query_id):
    """Get specific weather query by ID"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM weather_queries WHERE id = ?''', (query_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_query_in_db(query_id, location, lat, lon, date_from, date_to, weather_data, notes, tags):
    """Update weather query in database"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''UPDATE weather_queries 
                 SET location = ?, latitude = ?, longitude = ?, date_from = ?, date_to = ?, 
                     weather_data = ?, notes = ?, tags = ?
                 WHERE id = ?''',
              (location, lat, lon, date_from, date_to, json.dumps(weather_data), notes, tags, query_id))
    conn.commit()
    conn.close()

def delete_query_from_db(query_id):
    """Delete weather query from database"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''DELETE FROM weather_queries WHERE id = ?''', (query_id,))
    conn.commit()
    conn.close()

def save_location_to_db(name, address, lat, lon):
    """Save a location to the database for quick access"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''INSERT INTO saved_locations 
                 (name, address, latitude, longitude)
                 VALUES (?, ?, ?, ?)''',
              (name, address, lat, lon))
    conn.commit()
    conn.close()

def get_saved_locations():
    """Get all saved locations from database"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''SELECT id, name, address, latitude, longitude FROM saved_locations ORDER BY name''')
    rows = c.fetchall()
    conn.close()
    return rows

def display_weather(weather_data, air_quality_data=None):
    """Display weather data in a user-friendly format with more details"""
    if not weather_data:
        st.error("No weather data available")
        return
    
    if 'current' in weather_data:  # Current weather format
        weather = weather_data['current']
        st.subheader("Current Weather Details")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Temperature", f"{weather['temp']}°C")
            st.metric("Feels Like", f"{weather['feels_like']}°C")
            st.metric("Min/Max Temp", f"{weather.get('temp_min', 'N/A')}°C / {weather.get('temp_max', 'N/A')}°C")
        
        with col2:
            st.metric("Humidity", f"{weather['humidity']}%")
            st.metric("Pressure", f"{weather['pressure']} hPa")
            st.metric("Visibility", f"{weather.get('visibility', 'N/A')} meters")
        
        with col3:
            st.metric("Wind Speed", f"{weather['wind_speed']} m/s")
            st.metric("Wind Direction", f"{weather.get('wind_deg', 'N/A')}°")
            st.metric("Cloud Cover", f"{weather.get('clouds', 'N/A')}%")
        
        st.write(f"**Weather Conditions:** {weather['weather'][0]['main']} - {weather['weather'][0]['description'].capitalize()}")
        
        if weather.get('rain'):
            st.write(f"**Rain:** {weather['rain'].get('1h', 'N/A')}mm last hour")
        if weather.get('snow'):
            st.write(f"**Snow:** {weather['snow'].get('1h', 'N/A')}mm last hour")
        
        # Sunrise and sunset times
        if 'sunrise' in weather and 'sunset' in weather:
            sunrise = datetime.datetime.fromtimestamp(weather['sunrise']).strftime('%H:%M')
            sunset = datetime.datetime.fromtimestamp(weather['sunset']).strftime('%H:%M')
            st.write(f"**Sunrise:** {sunrise}, **Sunset:** {sunset}")
        
        # Air quality data
        if air_quality_data:
            st.subheader("Air Quality Information")
            aqi = air_quality_data['list'][0]['main']['aqi']
            aqi_map = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
            components = air_quality_data['list'][0]['components']
            
            st.metric("Air Quality Index", f"{aqi} - {aqi_map.get(aqi, 'Unknown')}")
            
            st.write("**Pollutants:**")
            cols = st.columns(4)
            with cols[0]:
                st.write(f"CO: {components.get('co', 'N/A')} μg/m³")
                st.write(f"NO: {components.get('no', 'N/A')} μg/m³")
            with cols[1]:
                st.write(f"NO₂: {components.get('no2', 'N/A')} μg/m³")
                st.write(f"O₃: {components.get('o3', 'N/A')} μg/m³")
            with cols[2]:
                st.write(f"SO₂: {components.get('so2', 'N/A')} μg/m³")
                st.write(f"NH₃: {components.get('nh3', 'N/A')} μg/m³")
            with cols[3]:
                st.write(f"PM2.5: {components.get('pm2_5', 'N/A')} μg/m³")
                st.write(f"PM10: {components.get('pm10', 'N/A')} μg/m³")
    
    else:  # Forecast format
        st.subheader("Detailed Weather Forecast")
        
        # Group forecast by day
        forecast_by_day = {}
        for item in weather_data['list']:
            date = datetime.datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
            if date not in forecast_by_day:
                forecast_by_day[date] = []
            forecast_by_day[date].append(item)
        
        for date, day_forecasts in forecast_by_day.items():
            with st.expander(f"**{date}** - {len(day_forecasts)} forecasts"):
                for item in day_forecasts:
                    time = datetime.datetime.fromtimestamp(item['dt']).strftime('%H:%M')
                    weather_icon = WEATHER_ICONS.get(item['weather'][0]['icon'], "☁️")
                    
                    col1, col2, col3 = st.columns([1,2,3])
                    with col1:
                        st.write(f"**{time}**")
                    with col2:
                        st.write(f"{weather_icon} {item['weather'][0]['main']}")
                    with col3:
                        st.write(f"Temp: {item['main']['temp']}°C (Feels like {item['main']['feels_like']}°C)")
                        st.write(f"Humidity: {item['main']['humidity']}%, Wind: {item['wind']['speed']} m/s")
                        if 'rain' in item:
                            st.write(f"Rain: {item['rain'].get('3h', 'N/A')}mm")
                        if 'snow' in item:
                            st.write(f"Snow: {item['snow'].get('3h', 'N/A')}mm")

def display_location_map(lat, lon, properties=None):
    """Display a map of the location with more details"""
    if lat and lon:
        m = folium.Map(location=[lat, lon], zoom_start=12)
        folium.Marker(
            [lat, lon],
            popup=f"Lat: {lat}, Lon: {lon}",
            tooltip="Weather Location"
        ).add_to(m)
        
        # Add more map features if properties are available
        if properties:
            if 'city' in properties:
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=5,
                    popup=f"{properties.get('city', 'Location')}",
                    color='blue',
                    fill=True,
                    fill_color='blue'
                ).add_to(m)
            
            if 'country' in properties:
                folium.Marker(
                    [lat, lon],
                    icon=folium.DivIcon(
                        html=f"""<div style="font-size: 12pt; color: black">{properties.get('country', '')}</div>"""
                    )
                ).add_to(m)
        
        folium_static(m)
        
        # Display additional location information if available
        if properties:
            st.subheader("Location Information")
            cols = st.columns(3)
            with cols[0]:
                if 'city' in properties:
                    st.write(f"**City:** {properties['city']}")
                if 'country' in properties:
                    st.write(f"**Country:** {properties['country']}")
                if 'postcode' in properties:
                    st.write(f"**Postal Code:** {properties['postcode']}")
            
            with cols[1]:
                if 'state' in properties:
                    st.write(f"**State/Region:** {properties['state']}")
                if 'county' in properties:
                    st.write(f"**County:** {properties['county']}")
                if 'continent' in properties:
                    st.write(f"**Continent:** {properties['continent']}")
            
            with cols[2]:
                if 'timezone' in properties:
                    st.write(f"**Timezone:** {properties['timezone']}")
                if 'formatted' in properties:
                    st.write(f"**Full Address:** {properties['formatted']}")

def display_timezone_info(timezone_data):
    """Display timezone information"""
    if not timezone_data:
        return
    
    st.subheader("Timezone Information")
    cols = st.columns(3)
    with cols[0]:
        st.write(f"**Timezone Name:** {timezone_data.get('zoneName', 'N/A')}")
        st.write(f"**Abbreviation:** {timezone_data.get('abbreviation', 'N/A')}")
    with cols[1]:
        st.write(f"**GMT Offset:** {timezone_data.get('gmtOffset', 'N/A')} seconds")
        st.write(f"**Current Time:** {timezone_data.get('formatted', 'N/A')}")
    with cols[2]:
        st.write(f"**DST:** {'Yes' if timezone_data.get('dst', '0') == '1' else 'No'}")
        st.write(f"**Country Code:** {timezone_data.get('countryCode', 'N/A')}")

def export_data(data, format_type):
    """Export data in different formats with more comprehensive data handling"""
    if format_type == 'JSON':
        return json.dumps(data, indent=2)
    elif format_type == 'CSV':
        output = StringIO()
        writer = csv.writer(output)
        
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # Handle list of dictionaries
                writer.writerow(data[0].keys())  # header
                for row in data:
                    writer.writerow(row.values())
            else:
                # Handle simple list
                writer.writerow(["Value"])
                for item in data:
                    writer.writerow([item])
        elif isinstance(data, dict):
            # Handle single dictionary
            writer.writerow(data.keys())
            writer.writerow(data.values())
        else:
            # Handle simple value
            writer.writerow(["Value"])
            writer.writerow([data])
            
        return output.getvalue()
    elif format_type == 'XML':
        def dict_to_xml(tag, d):
            elem = f'<{tag}>'
            if isinstance(d, dict):
                for key, val in d.items():
                    elem += dict_to_xml(key, val)
            elif isinstance(d, list):
                for item in d:
                    elem += dict_to_xml('item', item)
            else:
                elem += str(d)
            elem += f'</{tag}>'
            return elem
        
        if isinstance(data, (dict, list)):
            return dict_to_xml('data', data)
        else:
            return f'<data>{data}</data>'
    return str(data)

def get_user_preferences():
    """Get user preferences from database"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM user_preferences LIMIT 1''')
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'temperature_unit': row[1],
            'wind_speed_unit': row[2],
            'pressure_unit': row[3],
            'theme': row[4]
        }
    else:
        # Default preferences
        return {
            'temperature_unit': 'celsius',
            'wind_speed_unit': 'm/s',
            'pressure_unit': 'hPa',
            'theme': 'light'
        }

def save_user_preferences(preferences):
    """Save user preferences to database"""
    conn = sqlite3.connect('weather_app.db')
    c = conn.cursor()
    
    # Clear existing preferences
    c.execute('''DELETE FROM user_preferences''')
    
    # Insert new preferences
    c.execute('''INSERT INTO user_preferences 
                 (temperature_unit, wind_speed_unit, pressure_unit, theme)
                 VALUES (?, ?, ?, ?)''',
              (preferences['temperature_unit'], preferences['wind_speed_unit'], 
               preferences['pressure_unit'], preferences['theme']))
    
    conn.commit()
    conn.close()

# Streamlit app
def main():
    st.set_page_config(
        page_title="Weather App", 
        page_icon="⛅", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'current_location' not in st.session_state:
        st.session_state.current_location = None
    if 'current_coords' not in st.session_state:
        st.session_state.current_coords = None
    
    # App header
    st.title("🌦️ Comprehensive Weather App")
    st.markdown("""
        Get current weather, forecasts, and historical data for any location worldwide.
        Save your queries and access them anytime.
    """)
    
    # Navigation
    menu = [
        "Current Weather", 
        "5-Day Forecast", 
        "Weather by Date Range", 
        "Saved Queries", 
        "Saved Locations",
        "Settings"
    ]
    choice = st.sidebar.selectbox("Menu", menu)
    
    # Settings page
    if choice == "Settings":
        st.header("User Settings")
        
        # Get current preferences
        preferences = get_user_preferences()
        
        # Settings form
        with st.form("settings_form"):
            st.subheader("Units")
            temp_unit = st.selectbox(
                "Temperature Unit",
                ["celsius", "fahrenheit", "kelvin"],
                index=["celsius", "fahrenheit", "kelvin"].index(preferences['temperature_unit'])
            )
            
            wind_unit = st.selectbox(
                "Wind Speed Unit",
                ["m/s", "km/h", "mph", "knots"],
                index=["m/s", "km/h", "mph", "knots"].index(preferences['wind_speed_unit'])
            )
            
            pressure_unit = st.selectbox(
                "Pressure Unit",
                ["hPa", "mmHg", "inHg", "atm"],
                index=["hPa", "mmHg", "inHg", "atm"].index(preferences['pressure_unit'])
            )
            
            st.subheader("Appearance")
            theme = st.selectbox(
                "Theme",
                ["light", "dark"],
                index=["light", "dark"].index(preferences['theme'])
            )
            
            if st.form_submit_button("Save Settings"):
                new_preferences = {
                    'temperature_unit': temp_unit,
                    'wind_speed_unit': wind_unit,
                    'pressure_unit': pressure_unit,
                    'theme': theme
                }
                save_user_preferences(new_preferences)
                st.success("Settings saved successfully!")
    
    # Current Weather page
    elif choice == "Current Weather":
        st.header("Current Weather Conditions")
        
        # Location input options
        input_method = st.radio("Location Input Method:", 
                               ["Enter Location", "Select Saved Location", "Use Current Location (Simulated)"],
                               horizontal=True)
        
        location = None
        lat, lon = None, None
        properties = None
        
        if input_method == "Enter Location":
            location = st.text_input("Enter location (city, zip code, landmark, etc.):", 
                                   placeholder="e.g., New York, 10001, Eiffel Tower")
            if location:
                lat, lon, properties = get_coordinates(location)
                if lat and lon:
                    st.success(f"Location found: {properties.get('formatted', location)}")
                else:
                    st.error("Could not determine coordinates for this location")
        
        elif input_method == "Select Saved Location":
            saved_locations = get_saved_locations()
            if saved_locations:
                location_options = {f"{loc[1]} ({loc[2]})": (loc[3], loc[4]) for loc in saved_locations}
                selected = st.selectbox("Choose a saved location:", list(location_options.keys()))
                lat, lon = location_options[selected]
                properties = {'formatted': selected.split('(')[0].strip()}
            else:
                st.info("No saved locations found. Please save locations first.")
        
        elif input_method == "Use Current Location (Simulated)":
            if st.button("Get Weather for My Location"):
                # In a real app, this would use browser geolocation
                st.warning("This would use browser geolocation in a real app. Using New York as demo.")
                lat, lon = 40.7128, -74.0060  # Default to New York
                properties = {
                    'city': 'New York',
                    'country': 'United States',
                    'formatted': 'New York, NY, USA'
                }
        
        # Display weather if location is set
        if lat and lon:
            with st.spinner("Fetching weather data..."):
                weather_data = get_current_weather(lat, lon)
                air_quality_data = get_air_quality(lat, lon)
                timezone_data = get_timezone_info(lat, lon)
                
                if weather_data:
                    # Display weather information
                    display_weather({"current": weather_data}, air_quality_data)
                    
                    # Display map and location info
                    display_location_map(lat, lon, properties)
                    
                    # Display timezone info
                    display_timezone_info(timezone_data)
                    
                    # Save to database
                    notes = st.text_area("Add notes about this weather query:", 
                                        placeholder="Any additional notes you want to save...")
                    tags = st.text_input("Add tags (comma separated):", 
                                        placeholder="e.g., vacation, home, work")
                    
                    if st.button("Save This Query"):
                        save_to_db(
                            properties.get('formatted', f"Lat: {lat}, Lon: {lon}"),
                            lat, lon,
                            str(datetime.date.today()),
                            None, None,
                            weather_data,
                            notes,
                            tags
                        )
                        st.success("Query saved successfully!")
                        
                        # Option to save location
                        if st.checkbox("Save this location for quick access"):
                            name = st.text_input("Location name:", 
                                               value=properties.get('city', properties.get('formatted', 'My Location')))
                            if st.button("Save Location"):
                                save_location_to_db(
                                    name,
                                    properties.get('formatted', f"Lat: {lat}, Lon: {lon}"),
                                    lat, lon
                                )
                                st.success("Location saved successfully!")
                else:
                    st.error("Could not fetch weather data for this location")
    
    # 5-Day Forecast page
    elif choice == "5-Day Forecast":
        st.header("5-Day Weather Forecast")
        
        # Location input
        location = st.text_input("Enter location for forecast:", 
                               placeholder="e.g., London, 90210, Tokyo Tower")
        
        if location:
            lat, lon, properties = get_coordinates(location)
            if lat and lon:
                st.success(f"Location found: {properties.get('formatted', location)}")
                
                with st.spinner("Fetching forecast data..."):
                    forecast_data = get_forecast(lat, lon)
                    if forecast_data:
                        # Display forecast
                        display_weather(forecast_data)
                        
                        # Display map
                        display_location_map(lat, lon, properties)
                        
                        # Save to database
                        notes = st.text_area("Add notes about this forecast:", 
                                           placeholder="Any additional notes you want to save...")
                        tags = st.text_input("Add tags (comma separated):", 
                                           placeholder="e.g., vacation, home, work")
                        
                        if st.button("Save This Forecast"):
                            save_to_db(
                                properties.get('formatted', f"Lat: {lat}, Lon: {lon}"),
                                lat, lon,
                                str(datetime.date.today()),
                                None, None,
                                forecast_data,
                                notes,
                                tags
                            )
                            st.success("Forecast saved successfully!")
                    else:
                        st.error("Could not fetch forecast data for this location")
            else:
                st.error("Could not determine coordinates for this location")
    
    # Weather by Date Range page
    elif choice == "Weather by Date Range":
        st.header("Weather by Date Range")
        
        # Location input
        location = st.text_input("Enter location:", 
                               placeholder="e.g., Paris, 75001, Statue of Liberty")
        
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("From date:", datetime.date.today())
        with col2:
            date_to = st.date_input("To date:", datetime.date.today() + datetime.timedelta(days=5))
        
        if st.button("Get Weather for Date Range"):
            if date_from > date_to:
                st.error("End date must be after start date")
            else:
                lat, lon, properties = get_coordinates(location)
                if lat and lon:
                    st.success(f"Location found: {properties.get('formatted', location)}")
                    
                    with st.spinner("Fetching weather data for date range..."):
                        # Note: This is simulated since historical API requires paid plan
                        forecast_data = get_forecast(lat, lon)
                        if forecast_data:
                            weather_data = []
                            for item in forecast_data['list']:
                                item_date = datetime.datetime.fromtimestamp(item['dt']).date()
                                if date_from <= item_date <= date_to:
                                    weather_data.append(item)
                            
                            if weather_data:
                                st.subheader(f"Weather from {date_from} to {date_to}")
                                display_weather({"list": weather_data})
                                
                                # Display map
                                display_location_map(lat, lon, properties)
                                
                                # Save to database
                                notes = st.text_area("Add notes about this weather data:", 
                                                   placeholder="Any additional notes you want to save...")
                                tags = st.text_input("Add tags (comma separated):", 
                                                   placeholder="e.g., vacation, home, work")
                                
                                if st.button("Save This Weather Data"):
                                    save_to_db(
                                        properties.get('formatted', f"Lat: {lat}, Lon: {lon}"),
                                        lat, lon,
                                        str(datetime.date.today()),
                                        str(date_from), str(date_to),
                                        weather_data,
                                        notes,
                                        tags
                                    )
                                    st.success("Weather data saved successfully!")
                            else:
                                st.error("No weather data available for this date range")
                        else:
                            st.error("Could not fetch weather data for this location")
                else:
                    st.error("Could not determine coordinates for this location")
    
    # Saved Queries page
    elif choice == "Saved Queries":
        st.header("Saved Weather Queries")
        
        queries = get_all_queries()
        if queries:
            st.subheader("Your Saved Weather Queries")
            
            # Search and filter options
            col1, col2 = st.columns(2)
            with col1:
                search_term = st.text_input("Search queries by location or tags:")
            with col2:
                sort_option = st.selectbox("Sort by:", ["Most Recent", "Oldest", "Location A-Z", "Location Z-A"])
            
            # Filter and sort queries
            filtered_queries = queries
            if search_term:
                filtered_queries = [
                    q for q in queries
                    if search_term.lower() in q[1].lower() or 
                    (q[8] and search_term.lower() in q[8].lower())
                ]
            
            if sort_option == "Most Recent":
                filtered_queries = sorted(filtered_queries, key=lambda x: x[9], reverse=True)
            elif sort_option == "Oldest":
                filtered_queries = sorted(filtered_queries, key=lambda x: x[9])
            elif sort_option == "Location A-Z":
                filtered_queries = sorted(filtered_queries, key=lambda x: x[1].lower())
            elif sort_option == "Location Z-A":
                filtered_queries = sorted(filtered_queries, key=lambda x: x[1].lower(), reverse=True)
            
            # Display queries
            for query in filtered_queries:
                query_id, location, lat, lon, query_date, date_from, date_to, notes, tags, created_at = query
                
                with st.expander(f"📌 {location} - {created_at}"):
                    col1, col2, col3 = st.columns([3,1,1])
                    with col1:
                        st.write(f"**Location:** {location}")
                        if date_from and date_to:
                            st.write(f"**Date Range:** {date_from} to {date_to}")
                        else:
                            st.write(f"**Query Date:** {query_date}")
                        if notes:
                            st.write(f"**Notes:** {notes}")
                        if tags:
                            st.write(f"**Tags:** {tags}")
                    
                    with col2:
                        if st.button(f"🔍 View", key=f"view_{query_id}"):
                            st.session_state['view_query'] = query_id
                    
                    with col3:
                        if st.button(f"🗑️ Delete", key=f"delete_{query_id}"):
                            delete_query_from_db(query_id)
                            st.experimental_rerun()
            
            # Query details view
            if 'view_query' in st.session_state:
                st.divider()
                query_data = get_query_by_id(st.session_state['view_query'])
                if query_data:
                    st.subheader(f"Query Details - {query_data[1]}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Location:** {query_data[1]}")
                        st.write(f"**Coordinates:** {query_data[2]}, {query_data[3]}")
                        st.write(f"**Query Date:** {query_data[4]}")
                        if query_data[5] and query_data[6]:
                            st.write(f"**Date Range:** {query_data[5]} to {query_data[6]}")
                        st.write(f"**Created At:** {query_data[10]}")
                    
                    with col2:
                        if query_data[8]:
                            st.write(f"**Notes:** {query_data[8]}")
                        if query_data[9]:
                            st.write(f"**Tags:** {query_data[9]}")
                    
                    # Display weather data
                    st.subheader("Weather Data")
                    weather_data = json.loads(query_data[7])
                    if isinstance(weather_data, list):  # Date range data
                        display_weather({"list": weather_data})
                    else:  # Current or forecast data
                        display_weather(weather_data)
                    
                    # Display map
                    display_location_map(query_data[2], query_data[3])
                    
                    # Export options
                    st.subheader("Export Data")
                    export_format = st.selectbox("Select export format:", ["JSON", "CSV", "XML"], key="export_format")
                    if st.button("Generate Export"):
                        exported = export_data(weather_data, export_format)
                        st.download_button(
                            label="Download Exported Data",
                            data=exported,
                            file_name=f"weather_data_{query_data[0]}.{export_format.lower()}",
                            mime="text/plain"
                        )
                    
                    # Update functionality
                    st.subheader("Update Query")
                    with st.form(f"update_form_{query_data[0]}"):
                        new_location = st.text_input("Location:", value=query_data[1])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            new_date_from = st.text_input("Start date:", value=query_data[5] if query_data[5] else "")
                        with col2:
                            new_date_to = st.text_input("End date:", value=query_data[6] if query_data[6] else "")
                        
                        new_notes = st.text_area("Notes:", value=query_data[8] if query_data[8] else "")
                        new_tags = st.text_input("Tags:", value=query_data[9] if query_data[9] else "")
                        
                        if st.form_submit_button("Update Query"):
                            # Get new coordinates if location changed
                            if new_location != query_data[1]:
                                new_lat, new_lon, _ = get_coordinates(new_location)
                                if not new_lat or not new_lon:
                                    st.error("Could not determine coordinates for the new location")
                                    new_lat, new_lon = query_data[2], query_data[3]
                            else:
                                new_lat, new_lon = query_data[2], query_data[3]
                            
                            # Get updated weather data if needed
                            if (new_location != query_data[1] or 
                                new_date_from != query_data[5] or 
                                new_date_to != query_data[6]):
                                
                                if new_date_from and new_date_to:
                                    # Simulate getting historical data
                                    forecast = get_forecast(new_lat, new_lon)
                                    if forecast:
                                        new_weather_data = []
                                        for item in forecast['list']:
                                            item_date = datetime.datetime.fromtimestamp(item['dt']).date()
                                            from_date = datetime.datetime.strptime(new_date_from, '%Y-%m-%d').date()
                                            to_date = datetime.datetime.strptime(new_date_to, '%Y-%m-%d').date()
                                            if from_date <= item_date <= to_date:
                                                new_weather_data.append(item)
                                    else:
                                        new_weather_data = weather_data
                                else:
                                    new_weather_data = get_current_weather(new_lat, new_lon)
                            else:
                                new_weather_data = weather_data
                            
                            if new_weather_data:
                                update_query_in_db(
                                    query_data[0], 
                                    new_location, 
                                    new_lat, 
                                    new_lon,
                                    new_date_from, 
                                    new_date_to, 
                                    new_weather_data,
                                    new_notes,
                                    new_tags
                                )
                                st.success("Query updated successfully!")
                                st.experimental_rerun()
                            else:
                                st.error("Could not fetch updated weather data")
        else:
            st.info("No saved queries found. Save some weather queries to see them here.")
    
    # Saved Locations page
    elif choice == "Saved Locations":
        st.header("Saved Locations")
        
        saved_locations = get_saved_locations()
        if saved_locations:
            st.subheader("Your Saved Locations")
            
            # Display locations in a table
            location_data = []
            for loc in saved_locations:
                location_data.append({
                    "ID": loc[0],
                    "Name": loc[1],
                    "Address": loc[2],
                    "Latitude": loc[3],
                    "Longitude": loc[4],
                    "Saved On": loc[5]
                })
            
            df = pd.DataFrame(location_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Location actions
            st.subheader("Location Actions")
            selected_id = st.selectbox("Select a location to manage:", [loc[0] for loc in saved_locations])
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("View on Map"):
                    selected_loc = next(loc for loc in saved_locations if loc[0] == selected_id)
                    m = folium.Map(location=[selected_loc[3], selected_loc[4]], zoom_start=12)
                    folium.Marker(
                        [selected_loc[3], selected_loc[4]],
                        popup=f"{selected_loc[1]} ({selected_loc[2]})",
                        tooltip="Saved Location"
                    ).add_to(m)
                    folium_static(m)
            
            with col2:
                if st.button("Delete Location"):
                    conn = sqlite3.connect('weather_app.db')
                    c = conn.cursor()
                    c.execute('''DELETE FROM saved_locations WHERE id = ?''', (selected_id,))
                    conn.commit()
                    conn.close()
                    st.experimental_rerun()
        else:
            st.info("No saved locations found. Save some locations to see them here.")

if __name__ == "__main__":
    main()