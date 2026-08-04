from flask import Flask, render_template, jsonify, request
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

# Alarm state
alarm_state = {
    'time': None,  # Format: "HH:MM"
    'enabled': False,
    'last_triggered': None,
    'trigger_active': False  # Flag to indicate alarm just triggered
}

# Timer state
timer_state = {
    'duration': None,  # Duration in seconds
    'remaining': None,  # Remaining time in seconds
    'running': False,
    'paused': False,
    'start_time': None,
    'end_time': None
}

def get_weather():
    try:
        # Using wttr.in for Titchfield, England (no API key required)
        response = requests.get('https://wttr.in/Titchfield?format=j1', timeout=10)
        data = response.json()
        
        current = data['current_condition'][0]
        temp_c = int(current['temp_C'])
        condition = current['weatherDesc'][0]['value']
        
        # Get astronomy data (sunrise/sunset)
        astronomy = data.get('weather', [{}])[0].get('astronomy', [{}])[0]
        sunrise = astronomy.get('sunrise', 'N/A')
        sunset = astronomy.get('sunset', 'N/A')
        
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
            'icon': icon,
            'sunrise': sunrise,
            'sunset': sunset
        }
    except Exception as e:
        print(f"Error fetching weather: {e}")
        # Fallback to hardcoded values if API fails
        return {
            'temperature': 18,
            'condition': 'Partly Cloudy',
            'icon': '⛅',
            'sunrise': '06:00 AM',
            'sunset': '08:00 PM'
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
        response = requests.get('https://eeveeit.uk/api/site-info/', timeout=10)
        data = response.json()
        
        current_users = data.get('users', 0)
        now = datetime.datetime.now()
        
        # Add current user count to history
        uptime_state['user_history'].append((now, current_users))
        
        # Remove entries older than 12 hours
        twelve_hours_ago = now - datetime.timedelta(hours=12)
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
        # Keep existing data but update timestamp if we have historical data
        if uptime_state['user_history']:
            # Get the most recent user count from history
            last_users = uptime_state['user_history'][-1][1] if uptime_state['user_history'] else 0
            uptime_state['site_info']['users'] = last_users
            uptime_state['site_info']['last_fetch'] = datetime.datetime.now().isoformat()
            # Don't overwrite existing data with zeros
        else:
            # Set a default if no data exists
            uptime_state['site_info'] = {
                'services': 0,
                'operators': 0,
                'vehicles': 0,
                'users': 0,
                'last_fetch': datetime.datetime.now().isoformat(),
                'users_increased': False
            }

def uptime_monitor():
    while True:
        check_uptime()
        time.sleep(30)  # Check every 30 seconds

def alarm_monitor():
    global alarm_state
    while True:
        try:
            if alarm_state['enabled'] and alarm_state['time']:
                london = pytz.timezone('Europe/London')
                now = datetime.datetime.now(london)
                current_time = now.strftime('%H:%M')
                
                # Check if it's the alarm time and we haven't triggered it recently
                if current_time == alarm_state['time']:
                    # Check if we haven't triggered in the last minute
                    if (alarm_state['last_triggered'] is None or 
                        (now - datetime.datetime.fromisoformat(alarm_state['last_triggered'])).total_seconds() > 60):
                        alarm_state['last_triggered'] = now.isoformat()
                        alarm_state['trigger_active'] = True
                        print(f"ALARM TRIGGERED at {current_time}")
                
                # Reset trigger flag after 30 seconds
                if alarm_state['trigger_active'] and alarm_state['last_triggered']:
                    if (now - datetime.datetime.fromisoformat(alarm_state['last_triggered'])).total_seconds() > 30:
                        alarm_state['trigger_active'] = False
        except Exception as e:
            print(f"Error in alarm monitor: {e}")
        
        time.sleep(1)  # Check every second

# Start uptime monitor in background
monitor_thread = threading.Thread(target=uptime_monitor, daemon=True)
monitor_thread.start()

# Start alarm monitor in background
alarm_thread = threading.Thread(target=alarm_monitor, daemon=True)
alarm_thread.start()

def timer_monitor():
    global timer_state
    while True:
        try:
            if timer_state['running'] and timer_state['end_time']:
                now = datetime.datetime.now()
                end_time = datetime.datetime.fromisoformat(timer_state['end_time'])
                remaining = (end_time - now).total_seconds()
                
                if remaining <= 0:
                    timer_state['remaining'] = 0
                    timer_state['running'] = False
                    timer_state['paused'] = False
                    print("TIMER COMPLETED")
                else:
                    timer_state['remaining'] = remaining
        except Exception as e:
            print(f"Error in timer monitor: {e}")
        
        time.sleep(1)  # Check every second

# Start timer monitor in background
timer_thread = threading.Thread(target=timer_monitor, daemon=True)
timer_thread.start()

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
    # Return a clean version without the internal user_history
    return jsonify({
        'eeveeit': uptime_state['eeveeit'],
        'jellyfin': uptime_state['jellyfin'],
        'site_info': uptime_state['site_info']
    })

@app.route('/api/alarms', methods=['GET'])
def api_alarms_get():
    return jsonify(alarm_state)

@app.route('/api/alarms', methods=['POST'])
def api_alarms_set():
    data = request.json
    alarm_state['time'] = data.get('time')
    alarm_state['enabled'] = data.get('enabled', True)
    alarm_state['last_triggered'] = None  # Reset trigger time when setting new alarm
    return jsonify(alarm_state)

@app.route('/api/alarms', methods=['DELETE'])
def api_alarms_delete():
    alarm_state['time'] = None
    alarm_state['enabled'] = False
    alarm_state['last_triggered'] = None
    return jsonify(alarm_state)

@app.route('/alarms')
def alarms_page():
    return render_template('alarms.html')

@app.route('/api/alarm-triggered')
def api_alarm_triggered():
    return jsonify({'triggered': alarm_state['trigger_active']})

@app.route('/api/timers', methods=['GET'])
def api_timers_get():
    return jsonify(timer_state)

@app.route('/api/timers', methods=['POST'])
def api_timers_set():
    data = request.json
    timer_state['duration'] = data.get('duration')
    timer_state['remaining'] = data.get('duration')
    timer_state['running'] = False
    timer_state['paused'] = False
    timer_state['start_time'] = None
    timer_state['end_time'] = None
    return jsonify(timer_state)

@app.route('/api/timers/start', methods=['POST'])
def api_timers_start():
    if timer_state['remaining'] and not timer_state['running']:
        timer_state['running'] = True
        timer_state['paused'] = False
        timer_state['start_time'] = datetime.datetime.now().isoformat()
        timer_state['end_time'] = (datetime.datetime.now() + datetime.timedelta(seconds=timer_state['remaining'])).isoformat()
    return jsonify(timer_state)

@app.route('/api/timers/pause', methods=['POST'])
def api_timers_pause():
    if timer_state['running']:
        timer_state['running'] = False
        timer_state['paused'] = True
        # Calculate remaining time
        if timer_state['end_time']:
            end_time = datetime.datetime.fromisoformat(timer_state['end_time'])
            remaining = (end_time - datetime.datetime.now()).total_seconds()
            timer_state['remaining'] = max(0, remaining)
    return jsonify(timer_state)

@app.route('/api/timers/reset', methods=['POST'])
def api_timers_reset():
    timer_state['running'] = False
    timer_state['paused'] = False
    timer_state['remaining'] = timer_state['duration']
    timer_state['start_time'] = None
    timer_state['end_time'] = None
    return jsonify(timer_state)

@app.route('/api/timers', methods=['DELETE'])
def api_timers_delete():
    timer_state['duration'] = None
    timer_state['remaining'] = None
    timer_state['running'] = False
    timer_state['paused'] = False
    timer_state['start_time'] = None
    timer_state['end_time'] = None
    return jsonify(timer_state)

@app.route('/timer')
def timer_page():
    return render_template('timer.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
