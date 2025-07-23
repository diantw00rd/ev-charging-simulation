import random
# thoughts - maybe restructure so vehicle has a time counter....
class Vehicle:
    def __init__(self, battery_capacity, initial_battery_level, kwh_per_km, total_day_km):
        # vehicle characteristics
        # ASSUMPTION 10
        self.battery_capacity = battery_capacity
        self.power_per_time_increment = (kwh_per_km * 50) * (1 / 60) * (5)
        self.kwh_per_km = kwh_per_km
            # [kwh / km] * [km / hr] * [hr / min] * [min / increment]
        self.km_per_time_increment = 50 / 60 * 5
            # [km / hr] * [hr / min] * [min / increment]
            # will be approximate
        self.total_day_km = total_day_km

        # vehicle state
        self.battery_level = initial_battery_level
        self.energy_demand = 0
        self.is_charging = False
        self.is_driving = False

        # logs
        self.battery_log = {}
        self.demand_log = {}
        self.charging_log = {}

    # actions
    def _plug_in(self, charger_speed):
        self.is_charging = True
        self.energy_demand = charger_speed / 12
    
    def _stop_charging(self):
        self.is_charging = False
        self.energy_demand = 0

    def stop(self, has_charger, duration, charger_speed=12, decision_override=False):
        # ASSUMPTION 7
        self.is_driving = False
        # option 1 charging condition: battery level is less than needed for a full day of travel
            # with safety factor 2
        not_enough_battery = (2 * self.total_day_km) > ((self.battery_level / self.kwh_per_km))
            # kwh * [km / kwh]
        # option 2 charging condition: 80% battery
        # not_enough_battery = self.battery_level < (self.battery_capacity * 0.8)
        
        # if you (want to charge) and (can charge) and (are there more than 10 minutes)
            # decision override: you only care about your decision override if you have enough battery
            # if you do not have enough battery you charge wherever you can
        if ((not_enough_battery | decision_override) & (has_charger & (duration >= 6))):
            self._plug_in(charger_speed)
        
    def go(self):
        self._stop_charging()
        self.is_driving = True

    def execute_period(self, time):
        # ASSUMPTION 13
        # if the vehicle is plugged in
        if (self.is_charging & (self.battery_level < self.battery_capacity)):
            self.battery_level += self.energy_demand
        elif self.battery_level >= self.battery_capacity:
            # battery is full
            self._stop_charging()

        # ASSUMPTION 11
        # if the vehicle is driving
        if self.is_driving:
            # use the battery
            self.battery_level -= self.power_per_time_increment
            # remaining day km is commented out since we run the same day over and over again
            # self.remaining_day_km -= self.km__per_time_increment

        # log battery level and charging demand
        self.battery_log[time] = self.battery_level
        self.demand_log[time] = self.energy_demand
