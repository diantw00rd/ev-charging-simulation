# Model 
This repository contains the simulation code developed for analyzing non-overnight electric vehicle (EV) charging behavior under varying infrastructure and pricing conditions in Ontario, Canada.

The simulation integrates empirical travel behavior with a charging decision model derived from a stated-preference survey.

# Data

- **Transportation Tomorrow Survey 2016 (TTS 2016)**  
  Primary dataset used for simulation.  
  *Note: Original dataset is not distributed in this repo.*  

- **Synthetic test data**  
  A small toy dataset with the same structure as TTS 2016 to allow reproducibility of results and testing of the models.


# Travel and vehicle simulation
- Travel data source: the model uses real-world travel patterns from the 2016 Transportation Tomorrow Survey (TTS), representing weekday trip sequences in the Greater Toronto and Hamilton Area (GTHA).

- Trip chains: each vehicle's daily travel is simulated using sequences of trips with estimated durations and destinations based on survey responses.

- Vehicle attributes: EV types (with differing ranges and battery capacities) are randomly assigned to vehicles, accounting for a mix of small, mid-size, and long-range electric vehicles.

- State of Charge (SoC): A probabilistic model determines the initial SoC at the start of the day, reflecting partial overnight charging behavior observed in the population.

# Infrastructure and pricing scenarios
The model supports multiple scenarios varying:
- Charger accessibility (public and residential access)
- Electricity pricing (free, low, or high rates during daytime hours)

Charging is only considere during non-overnight hours (smart charging assumption that if vehcile is parked at home location and there is no more trips for the day - it is parked without charging. 

# Charging decision model
A discrete choice model (Generalized Estimating Equations, GEE) was estimated using survey responses.
Respondents chose whether or not they would charge under various hypothetical scenarios, considering:
- Remaining battery (SoC, in kWh)
- Parking duration (in minutes)
- Electricity price (in $/kWh)
- Anticipated further travel that day (in km)
The model outputs the probability of initiating a charge during each stop in the travel day.

# Simulation logic
At each stop in a vehicle’s simulated daily travel:
1. If a charger is available, the model estimates the probability of charging using the discrete choice model.
2. If charging occurs, energy demand is calculated based on parking time, vehicle battery size, and the remaining SoC.
3. Charging decisions and energy demand are aggregated across all vehicles to generate 24-hour load profiles.

# Alternative implementation
An alternate design of the simulation logic is provided in the /alternative/ folder. This version implements the same core functionality using a different code structure or logic flow. It may be useful for comparison, optimization, or experimentation with alternative approaches.

# ⚠️ [Disclaimer](https://hdl.handle.net/10012/22330)
This simulation code was developed as part of my Master’s thesis:
“Advancing Disaggregate Modeling of Electric Vehicle Charging Behaviour” at the University of Waterloo (2025).
The thesis is not yet published, and this repository is intended to support transparency and reproducibility of the simulation component.
Please note that model formulation and survey design were part of academic research and are subject to further development and validation.
All code in this repository is original work created by me and should be cited appropriately if used in related research.


