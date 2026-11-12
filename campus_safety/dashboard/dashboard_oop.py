"""Campus Safety Operations Console -- Streamlit OOP management dashboard.

Run: python -m streamlit run dashboard_oop.py

This module only handles presentation and user interaction. The uploaded
DataManager and domain classes remain the authorities for CRUD, validation,
status audit entries and saved AI reviews. New presentation-only capabilities
live in dashboard_extensions.py; the new asynchronous CSV service lives in
campus_safety/services/background_export_service.py.
"""