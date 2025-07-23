import pandas as pd
import numpy as np
# import matplotlib.pyplot as plt
import random
# from simulation.models.vehicle import Vehicle
# from simulation.models.event import Event

from vehicle import Vehicle
from event import Event
import filenames

def simulate(adoption_rate, warmup_periods, access_params_filename, preference_params_filename):
    # simulation parameters

    total_days = warmup_periods + 1

    # ASSUMPTION 1
    print('Reading TTS data...')
    # read data

    persdata = pd.read_csv(filenames.raw_data_folder + filenames.persdata_name
                        ,
                        dtype={'hhld_num' : str,
                                'pers_num' : str}
                                )

    tripdata = pd.read_csv(filenames.raw_data_folder + filenames.tripdata_name
                        ,
                        dtype={'hhld_num' : str,
                                'pers_num' : str,
                                'trip_num' : str}
                                )

    hhlddata = pd.read_csv(filenames.raw_data_folder + filenames.hhlddata_name
                        ,
                        dtype={'hhld_num' : str})
    
    # ASSUMPTION 2
    print('Selecting drivers with adoption rate', adoption_rate, "...")
    persdata['pers_id'] = persdata['hhld_num'].apply(str) + persdata['pers_num'].apply(str)
    tripdata['pers_id'] = tripdata['hhld_num'].apply(str) + tripdata['pers_num'].apply(str)
    tripdata = tripdata[tripdata['mode_prime'] == 'D']
    persdata = persdata[persdata['pers_id'].isin(tripdata['pers_id'].unique())]
    persdata = persdata.sample(frac=adoption_rate)
    tripdata = tripdata[tripdata['pers_id'].isin(persdata['pers_id'].unique())]

    # tripdata = tripdata[]
    print('Reading parameter data...')
    parameter_data = pd.read_csv(access_params_filename)

    pop_density_quantiles = pd.read_csv(filenames.pop_density_quantiles_name)

    print('Processing trip data...')
    # ASSUMPTION 6
    # Convert times
    def convert_time(t):
        """Converts time to an integer between 0 and 287 
        representing the 5-minute bucket of the day.
        ex. '1835' -> 233 """
        t = int(t)
        hours = t // 100
        minutes = t % 100
        total_mins = hours * 60 + minutes
        five_min_buckets = int(total_mins // 5)
        return five_min_buckets
    tripdata['start_time'] = tripdata['start_time'].apply(convert_time)

    # ASSUMPTION 3
    # calculate trip lengths
    tripdata['duration'] = ((tripdata['trip_man_km'] * (1 / 50) * (60)) // 5).apply(int)
        # [km] * [hr / km] * [min / hr] * [increments / min]
    tripdata['end_time'] = tripdata['start_time'] + tripdata['duration']

    # expansion factors
    expf = hhlddata[['hhld_num', 'expf']]
    persdata = pd.merge(persdata, expf, on='hhld_num')

    print('Converting home locations to housing type locations...')
    hhld_dwellings = hhlddata[['hhld_num', 'dwell_type']]
    tripdata = pd.merge(tripdata, hhld_dwellings, on='hhld_num')
    tripdata.loc[tripdata.purp_orig == 'H', 'purp_orig'] = tripdata.dwell_type.apply(str)
    tripdata.loc[tripdata.purp_dest == 'H', 'purp_dest'] = tripdata.dwell_type.apply(str)

    print('Assigning chargers to stops...')
    # Join TTS trips with population density quantiles
    tripdata = pd.merge(tripdata, 
                        pop_density_quantiles, 
                        how='left',
                        left_on='da16_orig',
                        right_on='GEO_NAME')

    tripdata = tripdata.rename(columns={'GEO_NAME': 'GEO_NAME_orig',
                            'pop_density_quantile' : 'pop_density_quantile_orig'})

    tripdata = pd.merge(tripdata, 
                        pop_density_quantiles, 
                        how='left',
                        left_on='da16_dest',
                        right_on='GEO_NAME')

    tripdata = tripdata.rename(columns={'GEO_NAME': 'GEO_NAME_dest',
                            'pop_density_quantile' : 'pop_density_quantile_dest'})

    # Join TTS data with probability of chargers
    tripdata = pd.merge(tripdata, 
                        parameter_data,
                        how='left',
                        left_on=('purp_orig', 'pop_density_quantile_orig'),
                        right_on=('Code', 'density_quantile'))

    tripdata = tripdata.rename(columns={'Code': 'Code_orig',
                                        'Purpose' : 'Purpose_orig',
                                        'density_quantile' : 'density_quantile_orig',
                                        'p_charger' : 'p_charger_orig'
                                        })

    tripdata = pd.merge(tripdata, 
                        parameter_data,
                        how='left',
                        left_on=('purp_dest', 'pop_density_quantile_dest'),
                        right_on=('Code', 'density_quantile'))

    tripdata = tripdata.rename(columns={'Code': 'Code_dest',
                                        'Purpose' : 'Purpose_dest',
                                        'density_quantile' : 'density_quantile_dest',
                                        'p_charger' : 'p_charger_dest'
                                        })

    # stochasticize charger availability
    tripdata['random1'] = np.random.rand(len(tripdata), 1)
    tripdata['random2'] = np.random.rand(len(tripdata), 1)

    tripdata['charger_orig'] = tripdata['p_charger_orig'] > tripdata['random1']
    tripdata['charger_dest'] = tripdata['p_charger_dest'] > tripdata['random2']

    decision_params = pd.read_csv(preference_params_filename)
    decisions = decision_params.set_index('stop_type')['decision'].to_dict()

    # add charging decision override
    def decision_override(stop_type):
        return decisions[stop_type]

    tripdata['decision_override_orig'] = tripdata['purp_orig'].apply(decision_override)
    tripdata['decision_override_dest'] = tripdata['purp_dest'].apply(decision_override)

    print('Creating simulation vehicle parameters...')
    # ASSUMPTION 14
    # vehicle parameters
    battery_capacity = 100
    kwh_per_km = 0.195

    # charger speed default
    charger_speed = 12

    # simulation
    print('Setting up simulation...')
    def event_queue_sort_condition(event):
        return event.time, event.priority

    battery_logs = []
    demand_logs = []

    print('Simulating (this may take a while)...')
    
    for person in persdata.itertuples():
        # ASSUMPTION 4
        # ASSUMPTION 5
        # get expansion factor
        expansion_factor = persdata.loc[persdata['pers_id'] == person.pers_id].iloc[0].expf

        # ASSUMPTION 12
        # Replicate day to multiple days of trips (repeated the same each day)
        trips = tripdata[tripdata['pers_id'] == person.pers_id]
        trips_copy = trips.copy(deep=True)
        trips_temp = trips.copy(deep=True)

        for day in range(total_days):
            period_modifier = int(day * 288) 
            trips_temp['start_time'] = trips_copy['start_time'] + period_modifier
            trips_temp['end_time'] = trips_copy['end_time'] + period_modifier
            trips = pd.concat([trips, trips_temp])

        total_day_km = trips_copy['trip_man_km'].sum()

        # create a vehicle 
        vehicle = Vehicle(battery_capacity, 
                        random.random() * battery_capacity,
                        kwh_per_km,
                        total_day_km)
        event_queue = []

        # add the first location event as a stop at time 0
        first_stop_has_charger = trips.sort_values('trip_num').iloc[0].charger_orig   
        first_stop_duration = trips.sort_values('trip_num').iloc[0].start_time
        first_stop_decision_override = trips.sort_values('trip_num').iloc[0].decision_override_orig
        first_stop = Event(time=0,
                        action='stop',
                        parameters=[first_stop_has_charger, 
                                    first_stop_duration, 
                                    charger_speed,
                                    first_stop_decision_override],
                        priority=0)
        event_queue.append(first_stop)

        # iterate through trips
        for trip in trips.itertuples():
            go_event = Event(time=trip.start_time,
                                action='go',
                                priority=1
                                )
            event_queue.append(go_event)
            end_event = Event(time=trip.end_time,
                            action='stop',
                            parameters=[trip.charger_dest, 
                                        trip.duration, 
                                        charger_speed,
                                        trip.decision_override_dest],
                            priority=99
                            )
            event_queue.append(end_event)
        
        num_periods = int(total_days * 288)
        for t in range(num_periods):
            e = Event(time=t, 
                    action='execute_period', 
                    priority=2)
            event_queue.append(e)
        event_queue.sort(key=event_queue_sort_condition)
        for e in event_queue:
            if e.action == 'stop':
                vehicle.stop(has_charger=e.parameters[0], 
                            duration=e.parameters[1],
                            charger_speed=e.parameters[2],
                            decision_override = e.parameters[3])
            if e.action == 'go':
                vehicle.go()
            if e.action == 'execute_period':
                vehicle.execute_period(e.time)

        expanded_demand_log = {}
        for time in vehicle.demand_log.keys():
            expanded_demand_log[time] = vehicle.demand_log[time] * expansion_factor
        battery_logs.append(vehicle.battery_log)
        demand_logs.append(expanded_demand_log)
        if ((person.Index % 5000) == 0):
            print("Processed person", person.Index)

    print('Aggregating battery and demand logs...')
    battery_series = [pd.Series(list(x.values())) for x in battery_logs]
    demand_series = [pd.Series(list(x.values())) for x in demand_logs]

    battery_df = pd.concat(battery_series, axis=1)
    average = np.nanmean(battery_df.values)
    stdev = np.nanstd(battery_df.values)

    demand_df = pd.concat(demand_series, axis=1)
    demand_profile = demand_df.sum(axis=1).rename(preference)
    demand_profile = demand_profile.tail(288)

    # demand_profile.to_csv(filenames.output_filename)
    return demand_profile, average, stdev

accesses = ['everywhere', 'differentiated']
preferences = ['home', 'none', 'not_home']

for access in accesses:
    results = []
    battery_stats = []
    for preference in preferences:
        access_filename = filenames.access_filename_base + access + '.csv'
        preference_filename = filenames.preference_filename_base + preference + '.csv'
        result, battery_average, battery_stdev = simulate(filenames.adoption_rate, filenames.warmup_periods, access_filename, preference_filename)
        results.append(result)
        battery_stats.append(pd.DataFrame({
            'preference' : [preference],
        'average' : [battery_average],
        'stdev' : [battery_stdev]
        }))
    
        results_df = pd.concat(results, axis=1)
        results_df.to_csv(filenames.output_filename +'_' +access + '_results.csv')
        battery_df = pd.concat(battery_stats, axis=0)
        battery_df.to_csv(filenames.output_filename +'_' +access + '_battery.csv')

