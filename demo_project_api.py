import sqlite3
import json
import os
import requests
from datetime import datetime, timezone
import sys
print(sys.executable)


API_KEY = "d9d443bb523d80aa0986c8e317a2bd33"
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
CITIES = ["DELHI","MUMBAI","PUNE"]
RAW = "/home/akhil_vm/project_data_engineering/raw_json"
DB_FILE = "/home/akhil_vm/project_data_engineering/weather.db"


def create_tables():
    CREATE_RAW = """
                 CREATE TABLE IF NOT EXISTS raw_weather(
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 CITY TEXT NOT NULL,
                 fetched_at TEXT DEFAULT(datetime('now')),
                 raw_json TEXT NOT NULL
                 );
                 """
    CREATE_PARSED = """
                    CREATE TABLE IF NOT EXISTS WEATHER_OBSERVATIONS(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT,
                    country TEXT,
                    temperature REAL,
                    humidity_pct INTEGER,
                    feels_like REAL,
                    temp_max REAL,
                    temp_min REAL
                    );
                    """
    
    conn = sqlite3.connect(DB_FILE)
    curr = conn.cursor()
    curr.execute(CREATE_RAW)
    curr.execute(CREATE_PARSED)
    conn.commit()
    conn.close()

def fetch_weather(city, api_key = None):
    params = {
        "q": city,
        "appid" : api_key or API_KEY,
        "units": "meteric"
    }
    response = requests.get(BASE_URL, params = params, timeout = 10)
    response.raise_for_status()
    return response.json()

def save_raw_json(data,city):
    os.makedirs(RAW,exist_ok = True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{city.lower().replace(' ', '_')}_{timestamp}.json"
    filepath = os.path.join(RAW, filename)
    with open(filepath, "w") as f:
        json.dump(data,f,indent=2)
    return filepath

def fetch_all_cities(api_key= None):
    results = []
    for city in CITIES:
        try:
            data = fetch_weather(city, api_key= api_key)
            filepath = save_raw_json(data,city)
            results.append((city,data))
        except requests.exceptions.HTTPError as e:
            print(f"{city} HTTP Error Occured: {e}")
        except requests.exceptions.ConnectionError:
            print(f"{city} Connrction Error occured.")
        except Exception as e:
            print(f"{city} - {e}")
    return results

def load_raw_to_db(results):
    INSERT_RAW = """INSERT INTO raw_weather(city,raw_json)
                    VALUES(?,?)
                    """
    conn = sqlite3.connect(DB_FILE) 
    curr = conn.cursor()
    count = 0

    for city, data in results:
        try:
            raw_json_str = json.dumps(data)
            curr.execute(INSERT_RAW,(city,raw_json_str))
            count += 1
        except Exception as e:
            print(f"Failed to insert {city}: {e}")
    conn.commit()
    conn.close()

def parse_weather_data(data):
    main = data.get("main",{})
    wind = data.get("wind",{})
    clouds = data.get("clouds",{})
    weather = data.get("weather",{})
    sys = data.get("sys",{})
    return{
        "city": data.get("name"),
        "country": sys.get("country"),
        "temperature": main.get("temp"),
        "humidity": main.get("humidity"),
        "feels_like": main.get("feels_like"),
        "temp_max": main.get("temp_max"),
        "temp_min": main.get("temp_min")
            }

def load_parsed_to_db(results):
    INSERT_PARSED = """
                    INSERT INTO WEATHER_OBSERVATIONS(city,country,temperature,humidity_pct,feels_like,temp_max,temp_min)
                    VALUES(:city,:country,:temperature,:humidity,:feels_like,:temp_max,:temp_min)
                    """
    conn = sqlite3.connect(DB_FILE)
    curr = conn.cursor()
    count = 0
    for city, data in results:
        try:
            record = parse_weather_data(data)
            curr.execute(INSERT_PARSED,record)
            print(f"Parsed & Inserted id={curr.lastrowid}, {city} "
                  f"{record['temperature']} C | {record['humidity']}% | Feels Like: {record['feels_like']} C")
            count +=1
        except Exception as e:
            print(f"Failed to Insert {city} : {e}")
    conn.commit()
    conn.close()
    print(f"\n {count} records inserted into WEATHER_OBSERVATIONS")

def run_query(query, description):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    conn.close()

    if not rows:
        print(" No Data Found")
        return
    col_width = [max(len(str(col)),max(len(str(row[col])) for row in rows))
                 for col in columns]

    header = " ".join(str(col).ljust(col_width[i]) for i, col in enumerate(columns))
    print(header)
    print("-" * len(header))

    for row in rows:
        print(" ".join(str(row[col]).ljust(col_width[i]) for i, col in enumerate(columns)))

    print(f"\n {description} - {len(rows)} records found.")

def query_results():
    run_query("""
              SELECT * FROM WEATHER_OBSERVATIONS
              """, "TOTAL TABLE")

def main():
    create_tables()
    results = fetch_all_cities()
    if not results:
        print("\n No data fetched. Check your API Key and internet connection")
        return

    load_raw_to_db(results)
    load_parsed_to_db(results)
    query_results()

if __name__ == "__main__":
    main()

