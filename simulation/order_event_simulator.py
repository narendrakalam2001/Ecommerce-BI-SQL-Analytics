# ============================================================
# ORDER EVENT SIMULATOR — E-Commerce BI & SQL Analytics System
# (mirrors simulation/applicant_simulator.py in the ML template —
#  generates synthetic live traffic to exercise the dashboard's
#  "Recent Orders Feed" and monitoring alerts.)
# ============================================================

import os
import time
import random
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

LOG_PATH = "logs/simulated_orders.csv"

STATES   = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF", "GO", "ES"]
CATEGORIES = ["bed_bath_table", "health_beauty", "sports_leisure",
              "furniture_decor", "computers_accessories", "watches_gifts"]

# ── 3 scenarios (mirrors the reference project's 3 applicant profiles) ──
SCENARIOS = {
    "normal_day": {
        "orders_per_tick": (3, 8),
        "price_range": (30, 250),
        "late_prob": 0.07,
        "review_range": (3, 5),
    },
    "flash_sale_spike": {
        "orders_per_tick": (25, 60),
        "price_range": (15, 120),
        "late_prob": 0.18,          # logistics strain under volume spike
        "review_range": (2, 5),
    },
    "logistics_disruption": {
        "orders_per_tick": (3, 8),
        "price_range": (30, 250),
        "late_prob": 0.55,          # simulates a courier/regional disruption
        "review_range": (1, 4),
    },
}


def _simulate_order(scenario: dict) -> dict:
    is_late = random.random() < scenario["late_prob"]
    return {
        "timestamp":     datetime.now().isoformat(timespec="seconds"),
        "customer_state":random.choice(STATES),
        "category":      random.choice(CATEGORIES),
        "price":         round(random.uniform(*scenario["price_range"]), 2),
        "is_late":       int(is_late),
        "review_score":  random.randint(1, 2) if is_late else random.randint(*scenario["review_range"]),
    }


def run_simulation(scenario_name: str = "normal_day", ticks: int = 20, tick_delay_sec: float = 1.0):
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_name}'. Choose from {list(SCENARIOS)}")

    scenario = SCENARIOS[scenario_name]
    os.makedirs("logs", exist_ok=True)
    logger.info("Starting simulation: scenario=%s ticks=%d", scenario_name, ticks)

    for tick in range(ticks):
        n_orders = random.randint(*scenario["orders_per_tick"])
        records = [_simulate_order(scenario) for _ in range(n_orders)]
        df = pd.DataFrame(records)

        df.to_csv(LOG_PATH, mode="a", header=not os.path.exists(LOG_PATH), index=False)
        logger.info("Tick %d/%d — wrote %d simulated orders (scenario=%s)",
                    tick + 1, ticks, n_orders, scenario_name)

        if tick_delay_sec:
            time.sleep(tick_delay_sec)

    logger.info("Simulation complete: scenario=%s", scenario_name)


if __name__ == "__main__":
    import sys
    scenario_arg = sys.argv[1] if len(sys.argv) > 1 else "normal_day"
    run_simulation(scenario_name=scenario_arg, ticks=10, tick_delay_sec=0.5)
