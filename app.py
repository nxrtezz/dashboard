from flask import Flask, render_template, jsonify
import requests
import datetime
import pytz
import time
import threading

app = Flask(__name__)

# Global state for uptime monitoring
uptime_state = {
    'eeveeit': {
        'status': 'unknown',
        'last_check': None,
        'status_changed': False
    },
    'jellyfin': {
        'status': 'unknown',
        'last_check': None,
        'status_changed': False
    },
    'site_info': {
        'services': 0,
        'operators': 0,
        'vehicles': 0,
        'users': 0,
        'last_fetch': None,
        'users_increased': False
    },
    'user_history': []  # Store tuples of (timestamp, user_count)
}

def get_weather():
    try:
        # Using wttr.in for Titchfield, England (no API key required)
        response = requests.get('https://wttr.in/Titchfield?format=j1', timeout=10)
        data = response.json()
        
        current = data['current_condition'][0]
        temp_c = int(current['temp_C'])
        condition = current['weatherDesc'][0]['value']
        
        # Map weather conditions to icons
        condition_lower = condition.lower()
        if 'sunny' in condition_lower or 'clear' in condition_lower:
            icon = '☀️'
        elif 'cloud' in condition_lower or 'overcast' in condition_lower:
            icon = '☁️'
        elif 'rain' in condition_lower or 'drizzle' in condition_lower or 'shower' in condition_lower:
            icon = '🌧️'
        elif 'snow' in condition_lower:
            icon = '❄️'
        elif 'thunder' in condition_lower:
            icon = '⛈️'
        elif 'fog' in condition_lower or 'mist' in condition_lower:
            icon = '🌫️'
        elif 'partly' in condition_lower:
            icon = '⛅'
        else:
            icon = '🌤️'
        
        return {
            'temperature': temp_c,
            'condition': condition,
            'icon': icon
        }
    except Exception as e:
        print(f"Error fetching weather: {e}")
        # Fallback to hardcoded values if API fails
        return {
            'temperature': 18,
            'condition': 'Partly Cloudy',
            'icon': '⛅'
        }

def get_time():
    london = pytz.timezone('Europe/London')
    return datetime.now(london).strftime('%H:%M:%S')

def get_bus_data():
    stops = [
        '1900HA040094',
        '1900HA040095',
        '1900HA040115',
        '1900HA040114'
    ]
    
    all_buses = []
    operator = None
    
    for stop in stops:
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
        except Exception as e:
            print(f"Error fetching stop {stop}: {e}")
    
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
    
    # Filter out buses that have already departed and sort by time
    now = datetime.datetime.now(pytz.UTC)
    valid_buses = []
    
    for bus in all_buses:
        try:
            bus_time = datetime.datetime.fromisoformat(bus['aimed_time'].replace('+00:00', '+00:00'))
            if bus_time > now:
                valid_buses.append(bus)
        except:
            # If we can't parse the time, include it anyway
            valid_buses.append(bus)
    
    # Sort by aimed_time
    valid_buses.sort(key=lambda x: x['aimed_time'])
    
    # Cap at next 4 departures
    valid_buses = valid_buses[:4]
    
    return valid_buses

def check_uptime():
    global uptime_state
    
    # Check eeveeit.uk
    try:
        response = requests.get('https://eeveeit.uk', timeout=10)
        
        new_status = 'up'
        if response.status_code in [404, 502]:
            new_status = 'down'
        elif response.status_code >= 400:
            new_status = 'error'
        
        if uptime_state['eeveeit']['status'] != new_status and uptime_state['eeveeit']['status'] != 'unknown':
            uptime_state['eeveeit']['status_changed'] = True
        else:
            uptime_state['eeveeit']['status_changed'] = False
        
        uptime_state['eeveeit']['status'] = new_status
        uptime_state['eeveeit']['last_check'] = datetime.datetime.now().isoformat()
        
    except Exception as e:
        if uptime_state['eeveeit']['status'] != 'error' and uptime_state['eeveeit']['status'] != 'unknown':
            uptime_state['eeveeit']['status_changed'] = True
        else:
            uptime_state['eeveeit']['status_changed'] = False
        
        uptime_state['eeveeit']['status'] = 'error'
        uptime_state['eeveeit']['last_check'] = datetime.datetime.now().isoformat()
    
    # Check jellyfin.eeveeit.uk
    try:
        response = requests.get('https://jellyfin.eeveeit.uk', timeout=10)
        
        new_status = 'up'
        if response.status_code in [404, 502]:
            new_status = 'down'
        elif response.status_code >= 400:
            new_status = 'error'
        
        if uptime_state['jellyfin']['status'] != new_status and uptime_state['jellyfin']['status'] != 'unknown':
            uptime_state['jellyfin']['status_changed'] = True
        else:
            uptime_state['jellyfin']['status_changed'] = False
        
        uptime_state['jellyfin']['status'] = new_status
        uptime_state['jellyfin']['last_check'] = datetime.datetime.now().isoformat()
        
    except Exception as e:
        if uptime_state['jellyfin']['status'] != 'error' and uptime_state['jellyfin']['status'] != 'unknown':
            uptime_state['jellyfin']['status_changed'] = True
        else:
            uptime_state['jellyfin']['status_changed'] = False
        
        uptime_state['jellyfin']['status'] = 'error'
        uptime_state['jellyfin']['last_check'] = datetime.datetime.now().isoformat()
    
    # Fetch site info
    try:
        response = requests.get('https://eeveeit.uk/api/site-info', timeout=10)
        data = response.json()
        
        current_users = data.get('users', 0)
        now = datetime.datetime.now()
        
        # Add current user count to history
        uptime_state['user_history'].append((now, current_users))
        
        # Remove entries older than 12 hours
        twelve_hours_ago = now - timedelta(hours=12)
        uptime_state['user_history'] = [
            (timestamp, count) for timestamp, count in uptime_state['user_history']
            if timestamp > twelve_hours_ago
        ]
        
        # Check if user count has increased in the past 12 hours
        users_increased = False
        if len(uptime_state['user_history']) > 1:
            # Get the minimum user count from the past 12 hours
            min_users = min(count for _, count in uptime_state['user_history'])
            users_increased = current_users > min_users
        
        uptime_state['site_info'] = {
            'services': data.get('services', 0),
            'operators': data.get('operators', 0),
            'vehicles': data.get('vehicles', 0),
            'users': current_users,
            'last_fetch': datetime.datetime.now().isoformat(),
            'users_increased': users_increased
        }
    except Exception as e:
        print(f"Error fetching site info: {e}")
        uptime_state['site_info']['last_fetch'] = datetime.datetime.now().isoformat()

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
