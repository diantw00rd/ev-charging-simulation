import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Load data
file_path = 'data.xlsx' 
data = pd.read_excel(file_path)

# Define constants
base_day = datetime.strptime("04:00", "%H:%M")
interval_labels = [(base_day + timedelta(minutes=5 * i)).strftime("%H:%M") for i in range(288)]

# EV types
ev_types = {
    'Kia': {'battery_kwh': 30, 'consumption_kwh_per_km': 0.173},
    'Nissan': {'battery_kwh': 62, 'consumption_kwh_per_km': 0.180},
    'Tesla Model 3': {'battery_kwh': 75, 'consumption_kwh_per_km': 0.160},
    'BMW': {'battery_kwh': 42.5, 'consumption_kwh_per_km': 0.130},
    'Tesla Model S': {'battery_kwh': 100, 'consumption_kwh_per_km': 0.200}
}

# Assign EV to each person
unique_persons = data[['hhld_num', 'pers_num', 'expf']].drop_duplicates()
np.random.seed(42)
assigned_vehicles = []
for _, row in unique_persons.iterrows():
    ev_choice = np.random.choice(list(ev_types.keys()))
    battery = ev_types[ev_choice]['battery_kwh']
    if np.random.rand() < 0.472:
        soc_kwh = battery
    else:
        soc_kwh = np.random.uniform(0.25, 0.80) * battery
    assigned_vehicles.append({
        'hhld_num': row['hhld_num'],
        'pers_num': row['pers_num'],
        'expf': row['expf'],
        'ev_type': ev_choice,
        'battery_kwh': battery,
        'consumption_per_km': ev_types[ev_choice]['consumption_kwh_per_km'],
        'soc_kwh': soc_kwh
    })
vehicle_states = pd.DataFrame(assigned_vehicles)

# Format time fields
data['start_dt'] = pd.to_datetime(data['start_time'], format='%H:%M')
data['end_dt'] = pd.to_datetime(data['end_time'], format='%H:%M')
data.loc[data['end_dt'] < data['start_dt'], 'end_dt'] += timedelta(days=1)
data['start_dt'] = data['start_dt'].apply(lambda dt: base_day.replace(hour=dt.hour, minute=dt.minute))
data['end_dt'] = data['end_dt'].apply(lambda dt: base_day.replace(hour=dt.hour, minute=dt.minute))

# Helper function
def is_driving(current_time, start, end):
    return start <= current_time < end

# Initialize tracking
final_energy = np.zeros(288)
total_soc_delta = 0.0
total_stops = 0
charging_stops = 0

# Simulate each person
grouped = data.groupby(['hhld_num', 'pers_num'])
person_counter = 0

for (hhld, person), person_trips in grouped:
    person_counter += 1
    if person_counter % 1000 == 0:
        print(f"{person_counter} persons processed...")

    person_trips = person_trips.sort_values(by='start_dt').reset_index(drop=True)
    vehicle = vehicle_states[(vehicle_states['hhld_num'] == hhld) & 
                             (vehicle_states['pers_num'] == person)].iloc[0]
    state = {
        'soc': vehicle['soc_kwh'],
        'battery_kwh': vehicle['battery_kwh'],
        'consumption_kwh_per_km': vehicle['consumption_per_km'],
        'expf': vehicle['expf'],
        'charging': False,
        'charger_speed': 0,
        'next_trip_index': 0
    }

    soc_initial = state['soc']

    if not person_trips.empty:
        first_trip_start = person_trips.iloc[0]['start_dt']
    else:
        first_trip_start = base_day + timedelta(days=1)

    for i in range(288):
        current_time = base_day + timedelta(minutes=5 * i)
        energy_used = 0.0

        # Skip pre-first-trip idle time
        if current_time < first_trip_start:
            continue

        # Driving
        if state['next_trip_index'] < len(person_trips):
            trip = person_trips.iloc[state['next_trip_index']]
            if is_driving(current_time, trip['start_dt'], trip['end_dt']):
                trip_duration = (trip['end_dt'] - trip['start_dt']).total_seconds() / 60
                km_per_min = trip['trip_man_km'] / trip_duration
                distance = km_per_min * 5
                energy = distance * state['consumption_kwh_per_km']
                state['soc'] -= energy
            elif current_time >= trip['end_dt']:
                state['next_trip_index'] += 1

        # Parking / Charging
        if state['next_trip_index'] > 0:
            last_trip = person_trips.iloc[state['next_trip_index'] - 1]
            at_home = last_trip['purp_dest'] == 'H'
        else:
            at_home = False
        no_more_trips = state['next_trip_index'] >= len(person_trips)

        is_new_parking = (i == 0 or (
            is_driving(base_day + timedelta(minutes=5 * (i - 1)), 
                       person_trips.iloc[state['next_trip_index'] - 1]['start_dt'], 
                       person_trips.iloc[state['next_trip_index'] - 1]['end_dt']) if state['next_trip_index'] > 0 else False
        ))

        if not (state['next_trip_index'] < len(person_trips) and is_driving(current_time, trip['start_dt'], trip['end_dt'])):
            if is_new_parking:
                total_stops += 1  # Track all parking events considered

                if at_home and no_more_trips:
                    state['charging'] = False
                else:
                    stop_start = current_time
                    if state['next_trip_index'] < len(person_trips):
                        stop_end = person_trips.iloc[state['next_trip_index']]['start_dt']
                    else:
                        stop_end = base_day + timedelta(days=1)

                    stop_duration = (stop_end - stop_start).total_seconds() / 60
                    remaining_km = person_trips[state['next_trip_index']:]['trip_man_km'].sum()
                    soc_pct = 100 * state['soc'] / state['battery_kwh']
                    z = 1.584 - 0.039 * soc_pct + 0.001 * stop_duration + 0.019 * remaining_km - 4.650 * 0.158
                    p_charge = 1 / (1 + np.exp(-z))
                    state['charging'] = p_charge >= 0.5 and state['soc'] < state['battery_kwh']
                    if state['charging']:
                        state['charger_speed'] = np.random.choice([12, 50])
                        charging_stops += 1  # Track charging decisions

            if state['charging'] and state['soc'] < state['battery_kwh']:
                charge_added = state['charger_speed'] * (5 / 60)
                soc_before = state['soc']
                state['soc'] = min(state['soc'] + charge_added, state['battery_kwh'])
                actual_added = state['soc'] - soc_before
                energy_used = actual_added * state['expf']

                if state['soc'] >= state['battery_kwh']:
                    state['charging'] = False

        final_energy[i] += energy_used

    soc_final = state['soc']
    total_soc_delta += (soc_final - soc_initial)

# Print summary stats
print(f"Total net change in SoC across all vehicles: {total_soc_delta:.2f} kWh")
charging_percentage = 100 * charging_stops / total_stops
print(f"Charging started at {charging_stops} of {total_stops} stops "
      f"({charging_percentage:.2f}%)")

# Save results
result_df = pd.DataFrame({
    'time': interval_labels,
    'energy_used': final_energy
})
result_df.to_excel('simulation.xlsx', index=False)
