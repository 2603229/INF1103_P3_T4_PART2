"""Root-level Streamlit entry point for the integrated Campus Safety project.

Run from the project root:
    python -m streamlit run dashboard.py

Use ``python main.py`` to launch both the CLI and this dashboard together.
This standalone entry point remains available if only the dashboard is needed.
Both use the same configuration and repository; neither seeds sample records.
"""
from campus_safety.dashboard.dashboard_oop import incident_dashboard


if __name__ == "__main__":
    incident_dashboard()
