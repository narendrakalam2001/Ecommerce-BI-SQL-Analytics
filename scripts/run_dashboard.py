# Entry point: launches the Streamlit monitoring dashboard.
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess

if __name__ == "__main__":
    subprocess.run(["streamlit", "run", os.path.join(os.path.dirname(__file__), "..", "monitoring", "monitoring_dashboard.py")])