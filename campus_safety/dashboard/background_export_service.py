"""Prepare incident CSV downloads in an isolated worker thread.

NEW SERVICE -- not provided by the uploaded prototype's DataManager.
The worker receives a defensive in-memory snapshot, never a repository, a
SQLite connection or a Streamlit session object.
"""

from __future__ import annotations

import csv
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from io import StringIO
import json
from typing import Any, Mapping, Sequence

from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.schema import SCHEMA_FIELDS
