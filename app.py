from flask import Flask, render_template, jsonify
import requests
import datetime
import pytz
import time
import threading

app = Flask(__name__)

# Global state for uptime monitoring
uptime_state = {
    'status': 'unknown',
    'last_check': None,
    'status_changed': False
}

# Hardcoded weather (simulated)
def get_weather():
    return {
        'temperature': 18,
        'condition': 'Partly Cloudy',
        'icon': '⛅'
    }

def get_time():
    london = pytz.timezone('Europe/London')
    return datetime.datetime.now(london).strftime('%H:%M:%S')

def get_bus_data():
    stops = [
        '1900HA040094',
        '1900HA040095',
        '1900HA040115',
        '1900HA040114'
    ]
    
    all_buses = []
    operator = None
    
    for i, stop in enumerate(stops):
        if i == 2:  # Add line separator between stops 2 and 3
            all_buses.append({'separator': True})
        
        try:
            response = requests.get(f'https://bustimes.org/stops/{stop}/times.json', timeout=5)
            data = response.json()
            
            if data.get('times'):
                for bus in data['times']:
                    if not operator and bus.get('service', {}).get('operators'):
                        operator = bus['service']['operators'][0]['id']
                    
                    bus_info = {
                        'line': bus['service']['line_name'],
                        'destination': bus['destination']['name'],
                        'aimed_time': bus['aimed_departure_time'],
                        'delay': bus.get('delay'),
                        'trip_id': bus['trip_id']
                    }
                    all_buses.append(bus_info)
            else:
                all_buses.append({'no_departures': True})
        except Exception as e:
            all_buses.append({'error': str(e)})
    
    # Fetch vehicle info if we have an operator
    if operator:
        try:
            vehicles_response = requests.get(f'https://bustimes.org/vehicles.json?operator={operator}', timeout=5)
            vehicles_data = vehicles_response.json()
            
            # Create a mapping of trip_id to vehicle info
            vehicle_map = {}
            for vehicle in vehicles_data:
                if 'trip_id' in vehicle:
                    vehicle_map[vehicle['trip_id']] = vehicle
            
            # Add vehicle info to buses
            for bus in all_buses:
                if 'trip_id' in bus and bus['trip_id'] in vehicle_map:
                    vehicle = vehicle_map[bus['trip_id']]
                    bus['vehicle'] = f"{vehicle.get('name', '')}"
        except Exception as e:
            print(f"Error fetching vehicles: {e}")
    
    return all_buses

def check_uptime():
    global uptime_state
    url = 'https://eeveeit.uk'
    
    try:
        response = requests.get(url, timeout=10)
        
        new_status = 'up'
        if response.status_code in [404, 502]:
            new_status = 'down'
        elif response.status_code >= 400:
            new_status = 'error'
        
        if uptime_state['status'] != new_status and uptime_state['status'] != 'unknown':
            uptime_state['status_changed'] = True
        else:
            uptime_state['status_changed'] = False
        
        uptime_state['status'] = new_status
        uptime_state['last_check'] = datetime.datetime.now().isoformat()
        
    except Exception as e:
        if uptime_state['status'] != 'error' and uptime_state['status'] != 'unknown':
            uptime_state['status_changed'] = True
        else:
            uptime_state['status_changed'] = False
        
        uptime_state['status'] = 'error'
        uptime_state['last_check'] = datetime.datetime.now().isoformat()

def uptime_monitor():
    while True:
        check_uptime()
        time.sleep(30)  # Check every 30 seconds

# Start uptime monitor in background
monitor_thread = threading.Thread(target=uptime_monitor, daemon=True)
monitor_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/weather')
def api_weather():
    return jsonify(get_weather())

@app.route('/api/time')
def api_time():
    return jsonify({'time': get_time()})

@app.route('/api/buses')
def api_buses():
    return jsonify(get_bus_data())

@app.route('/api/uptime')
def api_uptime():
    return jsonify(uptime_state)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
