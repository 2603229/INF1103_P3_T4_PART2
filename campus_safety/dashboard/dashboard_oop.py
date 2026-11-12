"""Campus Safety Operations Console -- Streamlit OOP management dashboard.

Run: python -m streamlit run dashboard_oop.py

This module only handles presentation and user interaction. The uploaded
DataManager and domain classes remain the authorities for CRUD, validation,
status audit entries and saved AI reviews. New presentation-only capabilities
live in dashboard_extensions.py; the new asynchronous CSV service lives in
campus_safety/services/background_export_service.py.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
import os
from pathlib import Path
from textwrap import wrap as wrap_text
from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.data_manager.repository_factory import create_repository
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.domain.schema import VALID_STATUSES
from campus_safety.domain.ai_review_entry import REVIEW_DECISIONS
from campus_safety.services.background_export_service import BackgroundExportService