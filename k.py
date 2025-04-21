import streamlit as st
import requests
import sqlite3
import json
from datetime import datetime

# Initialize database
def init_db():
    conn = sqlite3.connect('weather_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weather_entries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  location TEXT,
                  temperature REAL,
                  conditions TEXT,
                  notes TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# Weather API function
def get_weather(location):
    API_KEY = "f7a8a9a0a9a0a9a0a9a0a9a0a9a0a9a0"  # Free OpenWeatherMap key
    url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units=metric"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'temperature': data['main']['temp'],
                'conditions': data['weather'][0]['description'],
                'success': True
            }
        return {'error': f"API Error: {response.status_code}", 'success': False}
    except Exception as e:
        return {'error': str(e), 'success': False}

# Database functions
def save_to_db(location, temperature, conditions, notes):
    conn = sqlite3.connect('weather_data.db')
    c = conn.cursor()
    c.execute('''INSERT INTO weather_entries 
                 (location, temperature, conditions, notes)
                 VALUES (?, ?, ?, ?)''',
              (location, temperature, conditions, notes))
    conn.commit()
    conn.close()

def get_all_entries():
    conn = sqlite3.connect('weather_data.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM weather_entries ORDER BY created_at DESC''')
    rows = c.fetchall()
    conn.close()
    return rows

# Streamlit UI
def main():
    st.set_page_config(page_title="Weather Data App", page_icon="🌤️")
    st.title("🌤️ Weather Data Collector")
    
    # Input form
    with st.form("weather_form"):
        st.subheader("Add New Weather Data")
        location = st.text_input("Location (City):", placeholder="Enter a city name")
        notes = st.text_area("Your Notes:", placeholder="Add any observations...")
        
        submitted = st.form_submit_button("Submit")
        
        if submitted:
            if location:
                # Get live weather data
                weather = get_weather(location)
                
                if weather['success']:
                    # Save to database
                    save_to_db(
                        location,
                        weather['temperature'],
                        weather['conditions'],
                        notes
                    )
                    st.success("Data saved successfully!")
                    
                    # Display current weather
                    st.subheader("Current Weather")
                    cols = st.columns(3)
                    cols[0].metric("Location", location)
                    cols[1].metric("Temperature", f"{weather['temperature']}°C")
                    cols[2].metric("Conditions", weather['conditions'].title())
                    
                    if notes:
                        st.info(f"Your notes: {notes}")
                else:
                    st.error(f"Couldn't fetch weather: {weather['error']}")
            else:
                st.warning("Please enter a location")

    # Display saved data
    st.subheader("Saved Weather Entries")
    entries = get_all_entries()
    
    if entries:
        for entry in entries:
            with st.expander(f"{entry[1]} - {entry[4]}"):
                cols = st.columns(3)
                cols[0].metric("Temp", f"{entry[2]}°C")
                cols[1].metric("Conditions", entry[3])
                cols[2].metric("Recorded", entry[4][:16])
                
                if entry[4]:
                    st.caption(f"Notes: {entry[4]}")
                
                if st.button("Delete", key=f"del_{entry[0]}"):
                    conn = sqlite3.connect('weather_data.db')
                    c = conn.cursor()
                    c.execute('''DELETE FROM weather_entries WHERE id = ?''', (entry[0],))
                    conn.commit()
                    conn.close()
                    st.experimental_rerun()
    else:
        st.info("No entries yet. Submit some data above!")

    # Data export
    st.subheader("Export Data")
    if entries:
        if st.button("Export as JSON"):
            data = []
            for entry in entries:
                data.append({
                    'id': entry[0],
                    'location': entry[1],
                    'temperature': entry[2],
                    'conditions': entry[3],
                    'notes': entry[4],
                    'created_at': entry[5]
                })
            
            st.download_button(
                label="Download JSON",
                data=json.dumps(data, indent=2),
                file_name="weather_data.json",
                mime="application/json"
            )
    else:
        st.warning("No data to export")

if __name__ == "__main__":
    main()