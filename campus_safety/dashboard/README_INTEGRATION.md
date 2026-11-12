# Campus Safety — Management Dashboard integration (INF1103 Part 2)

This package contains **only** the new dashboard and its supporting UI modules. It does **not** include demo data, database files, tests, a virtual environment, `.env` files, or another copy of your teammates' managers and domain classes.

## Included files

```text
dashboard_oop.py
dashboard_extensions.py
campus_safety/
  services/
    background_export_service.py
requirements_dashboard.txt
README_INTEGRATION.md
optional_theme/
  streamlit_config.example.toml
```

## Merge with the team repository

1. Copy `dashboard_oop.py` and `dashboard_extensions.py` into the project root (alongside the team's `campus_safety/` directory).
2. Copy `campus_safety/services/background_export_service.py` into the existing package, preserving the directory structure. Do not overwrite a teammate's file without reviewing differences first.
3. Add any missing dependencies from `requirements_dashboard.txt` to the team's existing `requirements.txt`. **`python-dotenv` is not required by this dashboard.**
4. Keep the existing `DataManager`, domain classes, repositories, CLI launcher, and other project code unchanged.
5. Run from the project root:

```powershell
python -m pip install -r requirements_dashboard.txt
python -m streamlit run dashboard_oop.py
```

If dependencies have already been installed through the team's `requirements.txt`, skip the first command. No virtual environment is required for these commands (though teams may choose to use one).

## Data storage — no `.env` needed for this dashboard

The dashboard uses `DataManager(create_repository(backend))` to read and update the same database as the team's application. It uses the existing repository factory and **does not load an `.env` file**.

- **Default** (when no backend variable is defined): `json`, with the existing repository's default file path.
- **SQLite**: set `HAZARD_STORAGE_BACKEND=sqlite` in the operating-system/terminal environment. `SQLITE_DB_PATH` may optionally specify the shared SQLite file.
- **JSON**: set `HAZARD_STORAGE_BACKEND=json`. `INCIDENTS_DB` may optionally specify the shared JSON file.
- `HAZARD_DATA_DIR` can point both CLI and dashboard to the same shared data directory where supported by the repository.

For a SQLite session in Windows PowerShell, for example:

```powershell
$env:HAZARD_STORAGE_BACKEND="sqlite"
python -m streamlit run dashboard_oop.py
```

If the team's CLI writes to a custom database path, use the **same** backend and path for the dashboard. Do not change the backend without understanding where the existing records are stored; choosing SQLite instead of JSON does not migrate records.

If you used an earlier demo pack, clear leftover demo-specific environment variables before launching the integration build:

```powershell
Remove-Item Env:SQLITE_DB_PATH -ErrorAction SilentlyContinue
Remove-Item Env:INCIDENTS_DB -ErrorAction SilentlyContinue
Remove-Item Env:HAZARD_DATA_DIR -ErrorAction SilentlyContinue
```

This integration build rejects the previous demo database paths and refuses to display records marked `demo_fixture=True`. It does not delete or migrate data. The dashboard opens with an empty state if the selected database has no incidents.

## Required APIs from the existing prototype

- `DataManager.load()`
- `DataManager.update_status(incident_id, new_status, reason)`
- `DataManager.status_history(incident_id)`
- `DataManager.record_ai_review(incident_id, reviewer, decision, reason)`
- `DataManager.ai_review_history(incident_id)`
- `DataManager.delete(incident_id)`
- `DataManager.backups()`, `DataManager.restore(path)`, and `DataManager.export_txt(path)`
- `create_repository(backend)` and existing domain types (`HazardReport`, `VALID_STATUSES`, `REVIEW_DECISIONS`)

These calls matched the supplied `campus_safety.zip` prototype. Confirm method signatures still match the team's latest branch before merging.

## Features

- OOP `IncidentDashboard` class, clean Streamlit sidebar and responsive overview
- Priority queue, searchable/filterable incident workspace, detailed case view
- Status changes with reasons and persistent audit trail via `DataManager`
- Human AI-review decisions and history via `DataManager`
- Responsive thin, rounded horizontal bar charts with visible categorical labels
- Background CSV export using `BackgroundExportService` (Python standard library thread pool)
- Incident deletion and backup restoration with confirmation controls
- UI-only helpers isolated in `dashboard_extensions.py`; no SQL or Gemini calls in the dashboard

The included `optional_theme/streamlit_config.example.toml` may be merged into `.streamlit/config.toml` if your team wants the matching theme. This is optional.

## Integration cautions

Avoid committing production incident databases, backups, downloaded exports or API secrets to Git. The dashboard is not an authenticated safety-management product: reviewer names are self-entered, and its audit history is not tamper-proof. Do not deploy it publicly without suitable security controls. After merging, run the team's existing project checks and verify that the Streamlit dashboard uses the same real datastore as the CLI.
