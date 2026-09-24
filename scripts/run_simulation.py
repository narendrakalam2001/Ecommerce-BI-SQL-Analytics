# Entry point: generates simulated live order traffic for the dashboard feed.
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

from simulation.order_event_simulator import run_simulation, LOG_PATH

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "normal_day"
    print(f"Starting simulation: scenario='{scenario}' ... (writing to {LOG_PATH})")
    run_simulation(scenario_name=scenario, ticks=20, tick_delay_sec=1.0)
    print(f"Done. Simulated orders appended to {LOG_PATH}")