# 🛡️ Campus Safety Hazard Reporting System — INF1103 Part 2

## 1. 📌 Project overview

This project refactors the Phase 1 Campus Safety Hazard Reporting System into a modular, object-oriented Python application. The current source declares **48 application classes in 47 Python class-bearing files** across the controller, four managers, domain objects and dashboard. `DashboardLaunchError` shares `launcher.py` with `DashboardLauncher`; built-in exception types are not counted as application classes. Students and staff submit hazard reports through a command-line interface (CLI). Each report is assessed by Google Gemini, prioritised by business rules and saved to a JSON or SQLite database.

Every **new report** follows the four-manager workflow, coordinated by `CampusSafetyApplication`:

1. ⌨️ **IO Manager** — collects and validates user input, and displays records, results and summaries.
2. 🤖 **AI Manager** — builds a privacy-aware prompt, calls the live Gemini API, parses the JSON reply and validates every field.
3. 🧠 **Logic Manager** — scores severity, operational impact and historical frequency to decide priority, routing and duplicates.
4. 💾 **Data Manager** — saves, loads, queries and filters incidents through interchangeable JSON or SQLite repositories.

> **Business rule:** a new incident is **not saved** if the AI assessment is unavailable or invalid. The live Gemini API is needed for real submissions but **not** for the automated tests.

| Deliverable                | Where                                                                                                                                                                                                                                   |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🆕 New feature             | **Facilities Search & Summary Report** — Section 6                                                                                                                                                                                      |
| 🚀 Advanced feature        | **SQLite database integration (full CRUD)** — Section 7.1                                                                                                                                                                               |
| 🖥️ Additional enhancements | **Dashboard sign-in and sign-out**, **AI Assessment Review & Feedback**, **Incident Status Audit Trail**, Streamlit dashboard, single-command launcher, live form previews, field clearing and background CSV export — Sections 7.2–7.5 |
| 🐳 Docker                  | `Dockerfile` — Section 8.2                                                                                                                                                                                                              |
| ⚙️ CI                      | `.github/workflows/python-tests.yml` — Section 9                                                                                                                                                                                        |
| ✅ Tests                   | **266 `unittest`-discoverable test cases** in the latest source, including 7 single-command launcher tests; 25 extra logic-manager tests and 3 pytest-style checks raise the expected `pytest` collection to **294**. Counts reflect code inspection, not a new full-suite pass — Section 9                      |

## 2. ✨ Main application functions

CLI menu (displayed by `IOManager`, dispatched by `CampusSafetyApplication.run()`):

1. **Submit New Hazard Report** — enter reporter details, location, people affected, asset and description, plus an optional image. Review the AI assessment and priority breakdown, then confirm to save.
2. **View All Logged Incidents** — list saved reports.
3. **View Top 5 Most Frequent Hazards** — the five most frequently reported AI hazard categories.
4. **Search and Filter Incidents** 🆕 — filter by location keyword, status, category and minimum severity.
5. **View Facilities Summary Report** 🆕 — active workload, backlog rate, urgent hazards, and counts by location and category.
6. **Exit**

The **Streamlit dashboard** (Section 7.4) works on the same database and adds management tasks. It requires a username/password sign-in before showing dashboard content:

- 📜 **Incident Status Audit Trail** — change an incident's status with a reason and view its history.
- 👤 **AI Assessment Review & Feedback** — accept, flag or request further review of a Gemini assessment.
- 📤 **Export** — CSV (prepared in a background thread) and TXT downloads.
- 🗃️ **Backup and restore** — automatic pre-change backups and confirmed restores; incident deletion is available in the incident workspace.
- ✨ **Live form feedback** — status and AI-review decisions preview immediately; typed fields clear after successful saves, not after invalid submissions.

## 3. 🔄 How the managers work together

The managers never call each other directly. `CampusSafetyApplication` passes one `HazardReport` object from manager to manager:

```text
IOManager.get_user_input()             -> HazardReport (validated input)
        |
AIManager.assess(report)               -> AIAssessment (5 validated fields)
report.attach_assessment(...)
        |
LogicManager.calculate_historical_frequency(...)   } compared against
LogicManager.check_duplicate(...)                  } existing records
LogicManager.evaluate(record)          -> Decision (priority, score, route)
report.apply_decision(...)
        |
IOManager.priority_calculation / pre_submission_summary / confirm
        |  (yes)
DataManager.save(report)               -> incident ID assigned, e.g. INCIDENT-001
IOManager.submission_success(report)
```

Integration details handled by `CampusSafetyApplication`:

- The Logic Manager works with plain dictionaries, so reports are converted with `HazardReport.as_dict()`, and its result is converted into a `Decision` object.
- Historical frequency is added to the record **before** scoring so that it contributes to the score.
- An attached image's relative path (e.g. `uploads/photo.png`) is resolved to a runtime-only path for Gemini. The absolute path is never saved.
- `AssessmentUnavailable`, `InvalidRecord` and `DataStoreError` are shown as user-friendly messages instead of tracebacks (see Section 10).

`main.py` is the **single-command launcher**: it uses `DashboardLauncher` (`campus_safety/dashboard/launcher.py`) to start the Streamlit dashboard in a background process and runs the reporting CLI in the same terminal. `CampusSafetyApplication.create_default()` loads `.env`, creates each manager and injects them.

### 3.1 End-to-end example: incident submission → dashboard

1. **Start both interfaces:** run `python main.py`; the entry point launches the dashboard in your browser and starts `CampusSafetyApplication` and its four managers in the terminal.
2. **Report a hazard:** select menu option 1 and enter a fictional reporter, site/location, affected asset, number of people and description; attach a supported image if available. `IOManager` validates the input and creates a `HazardReport`.
3. **Obtain an AI assessment:** `CampusSafetyApplication` invokes `AIManager`; the `AssessmentProvider` implementation returns a validated `AIAssessment`. If assessment fails, **nothing is saved**.
4. **Evaluate and confirm:** `LogicManager` checks historical frequency/duplicates, calculates priority and routing, and the CLI displays the results for user confirmation.
5. **Persist the record:** `DataManager` uses the configured `IncidentRepository` (JSON or SQLite) to store the report and assign its incident ID.
6. **Monitor and update:** use the dashboard that automatically opened in your browser and sign in with the dashboard credentials. It reads the same backend through `DataManager`. The user can inspect the incident, add a **status change with a reason** (audit history), or save a **human AI-review decision** (review history); neither review changes the original AI assessment.

**Architecture note:** `IOManager`, `AIManager`, `LogicManager` and `DataManager` are collaborators injected into `CampusSafetyApplication`; the CLI's **Input → Assess → Prioritise → Save** sequence is an execution flow, **not** evidence that managers directly call one another. The dashboard runs in a separate **background process**, automatically started by `main.py`; its script is `dashboard.py` (which imports `campus_safety/dashboard/dashboard_oop.py`). The dashboard does not submit new Gemini assessments.

## 4. 🔁 Refactoring from Phase 1

Phase 1 passed plain dictionaries between procedural functions and stored them in a JSON file. Phase 2 keeps the same record fields (so Phase 1 JSON records still load) but moves each responsibility into classes:

| Responsibility  | Phase 2 object-oriented design                                                                                                                |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Incident record | `HazardReport` entity with validated construction and controlled state changes                                                                |
| Input / output  | `IOManager` with `InputValidator` and `MediaHandler`, using injectable read/write callables                                                   |
| AI processing   | `AIManager` → `AssessmentProvider` ABC → `GeminiAssessor`, with `GeminiPromptBuilder`, `ImageEvidenceProcessor` and `AIAssessment` validation |
| Business rules  | `LogicManager` delegates to `PriorityEvaluator` (uses `ScoreCalculator`), `IncidentHistory` (uses `TextMatcher`) and `IncidentReporter`; additional Scorer, PriorityRule, Router and matching classes are implemented and tested separately                                            |
| Persistence     | `DataManager` → `IncidentRepository` ABC → JSON or SQLite implementation                                                                      |
| Program flow    | `CampusSafetyApplication` coordinating injected managers                                                                                      |

The Phase 1 domain rules are preserved, including the **multi-condition rule** using two AI fields: _Critical severity **and** Severe/Catastrophic impact → Critical priority_. In the running workflow, `PriorityEvaluator._is_critical()` applies that condition; `CriticalRule` is a separate class with equivalent logic, primarily exercised in rule tests.

## 5. 🧠 Business rules

### 5.1 Input validation

| Field           | Rule                                                                                    |
| --------------- | --------------------------------------------------------------------------------------- |
| Reporter name   | Letters, spaces, `'`, `.` and `-` only                                                  |
| Contact         | SIT email (`...@sit.singaporetech.edu.sg`) or an 8-digit number starting with 6, 8 or 9 |
| Location        | Not empty                                                                               |
| People affected | Whole number from 1 to 1000                                                             |
| Asset / summary | At least 5 characters in the CLI (`InputValidator`); at least 3 in the domain model     |
| Description     | At least 15 characters                                                                  |

### 5.2 AI assessment (`AIAssessment`)

Gemini must return a JSON object with **exactly** five string fields: `risk_summary`, `category`, `severity`, `operational_impact` and `contextual_insights`.

- Category: Electrical, Plumbing, Structural, HVAC, IT/Equipment
- Severity: Low, Medium, High, Critical
- Operational impact: Minor, Moderate, Severe, Catastrophic

Reporter name and contact are excluded from the prompt, and recognisable names, emails and Singapore phone numbers are redacted from free text (`GeminiPromptBuilder`). Images must be JPEG/PNG/WEBP, at most 10 MiB, and their content must match their extension (`ImageEvidenceProcessor`). `GeminiAssessor` retries failed calls and falls back through the models listed in `GEMINI_MODELS`.

### 5.3 Priority scoring (`LogicManager`)

| Factor                                                                          | Points                                           |
| ------------------------------------------------------------------------------- | ------------------------------------------------ |
| Severity                                                                        | Low 1 · Medium 2 · High 4 · Critical 5           |
| Operational impact                                                              | Minor 1 · Moderate 2 · Severe 4 · Catastrophic 5 |
| Historical frequency (resolved/closed incidents at the same location and asset) | 1 → 1 · 2–4 → 2 · 5+ → 3                         |

| Priority | Rule (first match wins)                                                     | Route                      |
| -------- | --------------------------------------------------------------------------- | -------------------------- |
| Critical | Severity Critical **and** impact Severe/Catastrophic                        | Urgent Emergency Dispatch  |
| High     | Severity High/Critical, **or** impact Severe/Catastrophic, **or** score ≥ 7 | Priority Maintenance Queue |
| Normal   | Everything else                                                             | Standard Maintenance Queue |

**Implementation detail:** the production priority path is `LogicManager` → `PriorityEvaluator` → `ScoreCalculator`. The separately implemented `PriorityRule` (`CriticalRule`, `HighRule`, `StandardRule`), `Scorer` (`FrequencyScorer`, `TableScorer` → `SeverityScorer` / `ImpactScorer`) and `Router` classes support isolated design demonstrations/tests but are **not called by the current default evaluator**. `IncidentReporter` directly produces facilities summaries; `FacilitySummaryBuilder` and `SeveritySorter` are present as separate helpers rather than as members of the default reporter.

**Duplicate detection:** a new report matching an _open_ incident at the same location and asset is marked `Potential Duplicate of INCIDENT-xxx`. `FuzzyMatcher` tolerates typos ("Libary" ≈ "Library") but requires numbers to match exactly ("Lab 1" ≠ "Lab 10").

## 6. 🆕 New feature — Facilities Search & Summary Report

**Problem it addresses:** in Phase 1, facilities staff could only scroll through every incident. They had no way to find the hazards in one building, see what is still waiting for repair, or measure the maintenance backlog.

**How a user accesses it:**

- **Menu option 4 — Search and Filter Incidents.** Enter a location keyword, then optionally choose a status, category and minimum severity by number (press Enter to skip any filter). Matching incidents are listed with their ID, location, category, severity, priority and status.
- **Menu option 5 — View Facilities Summary Report.** Shows active hazards (excluding Resolved/Closed), pending repairs, in-progress work, urgent (High/Critical priority) hazards, the **maintenance backlog rate** (pending ÷ active × 100), and active hazards by location and category.

**Classes involved:**

| Manager     | Class / method                                                                          | Responsibility                                                             |
| ----------- | --------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| IO          | `IOManager.get_search_criteria()`, `view_search_results()`, `view_facilities_summary()` | Collect and validate filters; display results and metrics                  |
| Data        | `DataManager.search()`                                                                  | Filter stored records by location, status, category and severity rank      |
| Logic       | `LogicManager.generate_facilities_summary()` → `IncidentReporter.build_summary()`                 | Apply the "active hazard" and "urgent" business rules and aggregate counts |
| Domain      | `FacilitySummaryReport`                                                                 | Immutable result value object with the computed `maintenance_backlog_rate` |
| Application | `CampusSafetyApplication.search_incidents()`, `facilities_summary()`                    | Pass data between the managers                                             |

**How it is tested:** `test_facilities_data_manager_search.py`, `test_facilities_logic_manager_summary.py`, `test_facility_summary_domain.py`, `test_facilities_workflow_integration.py`, the facilities summary tests in `test_logic_manager_rules.py`, the search/summary tests in `test_io_manager_cli.py`, and end-to-end tests in `test_application_workflow.py`.

## 7. 🚀 Advanced feature and other extensions

### 7.1 🗄️ SQLite database integration (advanced feature)

**Implementation:** `campus_safety/data_manager/sqlite_incident_repository.py`
**Related files:** `data_manager.py`, `incident_repository.py`, `json_incident_repository.py` and `repository_factory.py`.

`DataManager` depends on the abstract `IncidentRepository` contract, not on SQL statements. Both `JsonIncidentRepository` and `SQLiteIncidentRepository` implement it, so the backend is chosen in `.env` without changing any other code.

| SQLite capability       | Implementation                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------- |
| ➕ **Create**           | Insert a validated incident and allocate a persistent incident ID in one transaction. |
| 🔍 **Read**             | Load and validate stored records.                                                     |
| ✏️ **Update**           | Persist modified records, including status and audit history.                         |
| 🗑️ **Delete**           | Remove a selected record through `DataManager.delete()`.                              |
| 💾 **Persistence**      | Data and the ID counter survive restarts; deleted IDs are never reused.               |
| 🔒 **Transactions**     | Parameterised SQL with `BEGIN IMMEDIATE` to prevent concurrent ID collisions.         |
| 🗃️ **Backup / restore** | Consistent backups via the SQLite backup API; integrity-checked before restoring.     |
| 🔄 **Migration**        | `import_records()` imports existing JSON records into an empty SQLite database.       |
| ⚠️ **Error handling**   | Corrupt files or records raise `DataStoreError` instead of being silently discarded.  |

The default file is `hazardreports.sqlite3` (in `HAZARD_DATA_DIR`, or the project folder). The `incidents(incident_id, payload)` table stores each serialised incident, including `status_history` and `ai_review_history`; `metadata(key, value)` stores the ID counter.

**Tested by:** `test_data_repositories.py`, which runs the **same** CRUD, persistence, audit-trail, backup/restore and corruption tests against both JSON and SQLite, plus SQLite-specific corrupt-database and migration tests.

A separate `migrate_json_to_sqlite.py` command-line script is not included or required: the import capability is available through `SQLiteIncidentRepository.import_records()`. Switching storage backends does not automatically migrate records.

### 7.2 📜 Incident Status Audit Trail (additional enhancement)

**Problem solved:** facilities staff need an accountable record of how and why an incident changes from `Pending Review` to `In Progress` or `Resolved`, rather than seeing only its most recent status.

**How to use:** open **Streamlit → Incidents → select a case → Manage status**. Choose a new status, inspect the live unsaved preview, enter a reason and select **Save status and record history**. The **Activity history** tab displays the saved transitions.

**Implementation:** every new report starts with a creation entry (`Created → Pending Review`). Later changes create `IncidentAuditEntry` records containing the incident ID, timezone-aware timestamp, previous status, new status and reason. `HazardReport.change_status()` validates transitions; `DataManager.update_status()` persists the updated incident and `status_history()` retrieves the record. Submitting the same status creates **no duplicate entry**. The text field clears **only after a successful status change**; failed/invalid submissions retain entered text.

**Verification:** use an incident in a disposable repository; change `Pending Review → In Progress` with a nonempty reason, reload the case and verify the history entry and new status persist. Try an empty reason and an unchanged status to verify no incorrect audit entry is added. Automated coverage is included in `test_data_repositories.py`, `test_hazard_report_domain.py` and dashboard helper tests.

> **Scope:** this is an application-level activity history, **not** a cryptographically tamper-proof security log.

### 7.3 🧑‍💻 AI Assessment Review & Feedback (additional enhancement)

**Problem solved:** an AI-generated risk assessment may need human confirmation, correction feedback or escalation without deleting the initial assessment or losing review accountability.

**How to use:** open **Streamlit → Incidents → select a case → AI assessment & review**. Choose **Accepted**, **Flagged as Incorrect** or **Further Review Requested**, enter a reviewer name and reason, and select **Save AI review**. The decision is previewed immediately; after a successful save the name/reason fields clear and the decision resets to `Accepted`. The **AI Review History** section shows saved feedback.

**Implementation:** `AIReviewEntry` stores each review decision, reviewer, reason and timestamp; `HazardReport.add_ai_review()` validates it; `DataManager.record_ai_review()` persists it and `ai_review_history()` reads it. Reviews **do not overwrite** Gemini's `risk_summary`, `category`, `severity`, `operational_impact`, `contextual_insights`, assigned priority or incident status.

**Verification:** submit a review for a case with a complete saved AI assessment, reload the case and verify the feedback history persists while the original AI result remains unchanged. Confirm that an empty reason/invalid reviewer name is rejected without clearing valid form input. Automated coverage is included in `test_data_repositories.py` and `test_hazard_report_domain.py`; verify live form behaviour in a browser.

> **Scope:** reviewer names are self-entered and are **not verified against the signed-in username**. The dashboard has a basic sign-in gate, but is still a local educational prototype rather than a production approval system.

### 7.4 🖥️ Streamlit dashboard and threaded CSV export

**Implementation:** `campus_safety/dashboard/` — `dashboard_oop.py` (`IncidentDashboard` and the login check at entry), `dashboard_auth.py` (`DashboardAuth`), `dashboard_extensions.py` (presentation helpers), `background_export_service.py` (`BackgroundExportService`) and `launcher.py` (`DashboardLauncher`, used by `main.py`).

**Dashboard authentication:** `DashboardAuth.from_env().require_login()` runs before any dashboard content is rendered. Until a correct username/password is submitted, Streamlit shows a **Campus Safety Operations** sign-in form. After sign-in the username is kept in Streamlit session state and a **Log out** button appears in the sidebar; logging out clears that session value. Configure `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` in `.env` (Section 8.3); the fallback values for this prototype are `admin` and `admin123`. **Change the defaults before demonstrating, sharing or deploying.** Credentials are compared in constant time (`hmac.compare_digest`). This is a basic, session-based login, not production-grade identity management.

The dashboard is organised into four navigation pages:

| Page               | Features                                                                                                                                                                                                                                              |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Overview**       | Total, active, high-priority and resolved counters; priority queue; workload-by-status chart; recently reported incidents. Summaries can auto-refresh every 15 seconds.                                                                               |
| **Incidents**      | Search, status/priority/category/date filters, sorting and pagination; inspect case details and image evidence; update status, save human AI reviews, view both histories, or delete a case with confirmation.                                        |
| **Insights**       | Incident category, severity and priority charts; monthly reporting trend; frequently reported locations.                                                                                                                                              |
| **Data & backups** | Prepare incident CSV exports in a worker thread; download CSV/TXT; list and restore available repository backups after confirmation. With the SQLite backend, a **read-only SQLite Database Viewer** shows the stored incidents table for inspection. |

`IncidentDashboard` receives a `DataManager` and does not access SQL or Gemini directly. The dashboard and CLI therefore reuse the same persistence, validation and incident domain logic. `BackgroundExportService` uses a `ThreadPoolExecutor` to produce a CSV from an incident snapshot without blocking the rest of the dashboard.

The dashboard displays **Singapore time (SGT)** where timestamps are shown. Auto-refresh is limited to Overview and Insights; incident forms deliberately do not refresh every 15 seconds to avoid interrupting edits. Charts and controls use a high-contrast light presentation theme, including readable white text on blue primary action buttons.

> **Security scope:** The sign-in form limits dashboard access within a Streamlit session, but it does not provide production-grade user management or verified reviewer identities. Reviewer names are self-entered, and status audit entries are application-level history rather than tamper-proof security logs. Do not expose the dashboard publicly or use real personal information for demonstration data.

### 7.5 ✨ Live status and AI-review forms

**Implementation:** `IncidentDashboard._manage_section()` and `IncidentDashboard._ai_review_section()` in `campus_safety/dashboard/dashboard_oop.py`.

These are **interface-level improvements** to existing `DataManager` operations. No repository schema, priority rules or saved Gemini assessment fields are changed.

| Form / field          | Interaction before saving                                                                                           | After a successful save                            | Invalid or unsuccessful save                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------- |
| **New status**        | Dropdown selection shows an immediate preview, e.g. `In Progress → Resolved (not saved yet)`.                       | Reflects the newly stored status.                  | Selected status is retained for correction. |
| **Reason for change** | Required for a genuine status change.                                                                               | Text box clears on the next rerun.                 | Entered text remains available.             |
| **Review decision**   | Dropdown shows the selected `Accepted`, `Flagged as Incorrect`, or `Further Review Requested` decision immediately. | Resets to the first supported option (`Accepted`). | Selected decision remains available.        |
| **Reviewer name**     | Required (at least two non-whitespace characters).                                                                  | Text box clears on the next rerun.                 | Entered text remains available.             |
| **Review reason**     | Required for a saved human AI review.                                                                               | Text box clears on the next rerun.                 | Entered text remains available.             |

**How it works:**

1. Choose a **New status** or **Review decision** from a dropdown. The dropdown is **outside** its `st.form()`, so Streamlit immediately redraws the preview as the selection changes. This is only a preview; **no database write occurs**.
2. Enter the reason (and reviewer name for AI feedback). Press the appropriate **Save** button to submit the form.
3. The dashboard validates the submission. A status that has not changed does not create another audit event; a genuine status change requires a reason. AI reviews require a reviewer name and reason, and are allowed only when the incident has a complete saved Gemini assessment.
4. On successful persistence through `DataManager.update_status()` or `DataManager.record_ai_review()`, a per-incident `st.session_state` reset flag is set. On rerun, the text inputs are cleared and the saved status or default review decision is shown.
5. When validation fails or a save fails, the reset flag is not set, so the user can correct the form instead of starting over.

**Important UI detail:** Because a selection outside `st.form()` triggers a rerun, **choose the dropdown value before typing long unsaved form text**. Live preview does not mean auto-save.

**Manual demonstration / verification (use a disposable test database):**

- **Status change:** Select an incident that is `Pending Review`, choose `In Progress`, confirm the live preview, enter a reason, save, then confirm the reason clears and an entry appears in **Activity history**.
- **AI review:** On a record with a completed Gemini assessment, choose `Flagged as Incorrect`, confirm the preview, enter a fictional reviewer name and reason, save, then confirm the inputs clear, the decision resets to `Accepted`, and the saved entry appears in **AI Review History**.
- **Validation:** Try submitting a status change with an empty reason or an AI review without a reviewer name. The warning should appear, and existing typed data should not be intentionally reset.
- **Data integrity:** Confirm that changing a review decision does **not** overwrite Gemini category, severity, risk summary, priority, or the incident's status.

The relevant UI state keys are scoped by incident ID (`cs_status_*_{incident_id}` and `cs_ai_*_{incident_id}`), so the forms of different incidents do not deliberately share values.

## 8. 🛠️ Installation and run guide

### 8.1 Local (Windows PowerShell, Python 3.12)

```powershell
git clone https://github.com/2603229/INF1103_P3_T4_PART2.git
cd INF1103_P3_T4_PART2
python -m pip install -r requirements.txt
# Optional: Copy-Item .env.example .env
# For real incident submissions, set GEMINI_API_KEY in your environment or .env.
python -m unittest discover -s tests -t . -v
python main.py                          # launches dashboard + CLI together
# Optional alternatives:
python main.py --cli-only               # CLI without dashboard
python main.py --no-browser             # both, without automatic browser opening
python -m streamlit run dashboard.py    # dashboard only
```

Run **only `python main.py`** in the project root. The dashboard starts automatically, and your browser opens at **http://localhost:8501** (or another available local port if 8501 is occupied). The CLI remains interactive in the same terminal. Both processes share environment settings and the same database. **When you exit the CLI, the dashboard server stops as well.** If a browser does not open, use the URL printed in the terminal. The dashboard first shows a sign-in form; use `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` from `.env` (defaults `admin` / `admin123`, see Section 8.3). `DASHBOARD_PORT` optionally fixes the dashboard port; an explicit occupied port generates a warning rather than redirecting to a different service. The optional `.env` applies to both interfaces. Without it, both use JSON storage by default; a Gemini API key is required only for real AI-assessed report submissions. If Streamlit is not installed, the CLI continues and displays installation instructions. A virtual environment is not required.

A virtual environment is optional; it is not required for these commands. SQLite is part of Python's standard library; do **not** install a separate `sqlite3` package.

### 8.2 🐳 Docker

Requires Docker Desktop to be running. No local Python installation is needed.

```powershell
# Build the image (from the repository root)
docker build -t campus-safety .

# Run the automated tests inside the container (no API key needed)
docker run --rm campus-safety python -m unittest discover -s tests -t . -v

# Run the interactive CLI with persistent records and shared image evidence
docker run -it --rm --env-file .env `
  -v campus-safety-data:/data `
  -v "${PWD}\uploads:/app/uploads:rw" `
  campus-safety

# Run the dashboard using the same database volume and uploaded images
docker run --rm -p 8501:8501 --env-file .env `
  -v campus-safety-data:/data `
  -v "${PWD}\uploads:/app/uploads:ro" `
  campus-safety python -m streamlit run dashboard.py --server.address=0.0.0.0
```

The image's default command is `python main.py --cli-only`, so the interactive CLI `docker run` command above starts the CLI only; the dashboard is started explicitly by the last command and shows the same sign-in form. Inside Docker, the default database is stored under `/data` (`HAZARD_DATA_DIR=/data`), and the named `campus-safety-data` volume preserves it between CLI and dashboard runs. Leave `SQLITE_DB_PATH` / `INCIDENTS_DB` unset or point them **inside `/data`**; a custom path outside `/data` may not persist in this volume. Both Docker commands bind-mount the project's local `uploads/` directory at `/app/uploads` (read/write for the CLI so it can copy new evidence; read-only for the dashboard). Create `uploads/` locally before running Docker and enter a **container path**, e.g. `/app/uploads/wet_floor.jpg`, when the CLI asks for an image; a Windows `C:\...` path is not valid inside Docker. Git and Docker ignore local uploads by default, so image files are not bundled into the image. `.env` is excluded from the image by `.dockerignore` and supplied at runtime via `--env-file`. The graphical image picker is unavailable in the container; the CLI asks for a file path instead. **Use `dashboard.py` as the canonical Streamlit entry point**. `campus_safety/dashboard/dashboard_oop.py` also calls `incident_dashboard()` when executed directly, but `dashboard.py` makes the supported entry point unambiguous. Both normally show the sign-in screen until a valid login is entered. If an already-open browser session goes straight to the dashboard, use **Log out** or a new private browser session to test the login form.

### 8.3 🔐 Configuration (`.env`)

| Variable                          | Purpose                                            | Default                                                 |
| --------------------------------- | -------------------------------------------------- | ------------------------------------------------------- |
| `GEMINI_API_KEY`                  | Gemini credentials (required for real submissions) | —                                                       |
| `GEMINI_MODELS`                   | Comma-separated model fallback order               | Built-in list in `gemini_assessor.py`                   |
| `HAZARD_STORAGE_BACKEND`          | `json` or `sqlite`                                 | `json` when unset; `.env.example` selects `sqlite`      |
| `SQLITE_DB_PATH` / `INCIDENTS_DB` | Optional custom SQLite / JSON file path            | Under `HAZARD_DATA_DIR` when unset                      |
| `HAZARD_DATA_DIR`                 | Shared data folder for either backend              | Project folder (`/data` in Docker)                      |
| `DASHBOARD_PORT`                  | Local dashboard port for `python main.py`          | `8501` (automatic fallback when occupied)               |
| `DASHBOARD_USERNAME`              | Dashboard sign-in username                         | `admin`                                                 |
| `DASHBOARD_PASSWORD`              | Dashboard sign-in password                         | `admin123` (**change before demonstrating or sharing**) |

Never commit `.env`, share your key or show it in screenshots. Changing the backend does **not** transfer existing records. Use **fictional test data** when demonstrating the application.

### 8.4 🎨 Optional Streamlit theme

The dashboard contains its own `STYLE` CSS in `dashboard_oop.py`; **there is no required `dashboard_style.py` file**. The supplied project already includes `.streamlit/config.toml` at the repository root to keep Streamlit's native controls consistent with the light dashboard:

```toml
[theme]
base = "light"
primaryColor = "#176B9C"
backgroundColor = "#F5F8FC"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#17324D"
borderColor = "#CBD9E6"
font = "sans serif"
```

Streamlit can run without this file, but **keep the included version** for consistent contrast. Its location is **`<project root>/.streamlit/config.toml`**, not inside `campus_safety/dashboard/`.

## 9. ✅ Automated tests and CI

**Latest source inventory (18 November 2026):** `unittest` discovery includes **266** tests, and full `pytest` collection is expected to include **294** tests. The seven `tests.test_single_command_launcher` tests were executed separately on 18 November 2026 and all passed. Compared with the README’s previously recorded **259 / 287** passing totals from 17 November, the current source also contains **7** new tests in `test_single_command_launcher.py`. The additional 25 logic-manager tests and 3 pytest-style IO checks are collected separately, as explained below. These **updated totals were calculated from the test sources, not confirmed as passing in a new full-suite execution**. Offline tests use stubbed AI responses and temporary repositories; a live Gemini API key is not required.

```powershell
python -m compileall -q main.py dashboard.py campus_safety tests
python -m unittest discover -s tests -t . -v    # currently 266 discoverable tests
python -m tests.run_all_tests                    # grouped full-suite summary
python -m tests.run_ai_tests                     # overlapping AI subset: 51 tests
python -m tests.run_application_tests            # application workflow + main entry point: 30 tests
python -m unittest tests.test_single_command_launcher -v # 7 launcher tests
# Optional with pytest installed: python -m pytest tests -q  # expected: 294 tests
```

### 9.1 Test coverage in this project version

| Area / test module                                 |   Tests | Main coverage                                                                                                          |
| -------------------------------------------------- | ------: | ---------------------------------------------------------------------------------------------------------------------- |
| AI Manager (`tests/ai_manager_test/`, six modules) |      51 | Schema validation, provider abstraction, Gemini retries/fallback, prompts and image validation                         |
| `test_logic_manager_rules.py`                      |      42 | Priority rules, severity/impact scoring, history, duplicate matching, injected configuration, facilities summary rules |
| `test_data_repositories.py`                        |      50 | JSON/SQLite CRUD, status audit, AI review, migrations, persistence, backups and corruption                             |
| `test_hazard_report_domain.py`                     |      17 | Domain validation, incident state changes, AI review rules                                                             |
| `test_io_manager_cli.py`                           |      14 | CLI, validation loops, search criteria and facilities output                                                           |
| `test_application_workflow.py`                     |      30 | End-to-end submission, cancellation, failure handling, menu routes and `main()` start-up/exit codes                    |
| `test_facilities_data_manager_search.py`           |      10 | Incident filters and searches                                                                                          |
| `test_facilities_logic_manager_summary.py`         |       2 | Facilities summaries                                                                                                   |
| `test_facilities_workflow_integration.py`          |       1 | Integrated facilities search/summary                                                                                   |
| `test_facility_summary_domain.py`                  |       2 | Facility summary result validation                                                                                     |
| `test_incident_exporter.py`                        |       4 | Exporter behaviour                                                                                                     |
| `test_background_export_service.py`                |       9 | Threaded export service and task handling                                                                              |
| `test_dashboard_extensions.py`                     |      22 | Dashboard presentation/helper logic                                                                                    |
| `test_dashboard_auth.py`                           |       5 | Dashboard credential checking                                                                                          |
| `test_single_command_launcher.py`                 |       7 | One-command launch, CLI fallback, child process lifecycle and port selection                                           |
| **Total discoverable `unittest` tests**            | **266** | **Current source inventory; run the suite to confirm a pass**                                                         |

Two sets of tests are **not collected by `unittest` discovery** and are therefore **excluded** from the 266-test total:

- `tests/test_io_manager.py` contains **three pytest-style checks**. Run them with `python -m pytest tests/test_io_manager.py -v`.
- `tests/logic_manager_test/` (`test_priority_rules.py`, `test_scoring.py`) contains **25 `unittest` tests** for the priority rules and scorers, but the folder has no `__init__.py`, so discovery skips it. Run them with `python -m unittest tests.logic_manager_test.test_scoring tests.logic_manager_test.test_priority_rules`, or with `pytest`. The CI workflow does not run them either.

`pytest` is not listed in the runtime `requirements.txt`; install it separately with `python -m pip install pytest`. `python -m pytest tests -q` should collect **294** tests (266 discoverable `unittest` tests + 25 logic-manager tests + 3 pytest-style checks). This is a **test-count expectation**, not a claim that all 294 have passed.

**Browser verification is separate:** the automated dashboard tests primarily cover helper logic, credential checking and export services. Manually verify Streamlit rendering, the sign-in and log-out flow, live selectbox previews, button contrast and the field-clearing behaviour described in Section 7.5. The inventory above does **not** establish a passing run, Docker startup or successful GitHub-hosted CI execution.

**CI configuration:** `.github/workflows/python-tests.yml` runs on pushes to `main` and `feature/**`, and pull requests to `main`. The `basic-checks` job checks essential files, compiles Python, installs dependencies, runs AI tests, imports the dashboard and runs the complete `unittest` suite. The `docker` job builds the image, runs the same suite in the container and smoke-tests the CLI using menu option 6. **Review GitHub Actions results separately** before claiming CI/Docker success in the engineering report.

## 10. ⚠️ Exception handling

| Exception                                | Raised by                                               | Typical cause                                                                                                             | Handled by                                                                | Outcome                                                                    |
| ---------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `InvalidRecord` (`ValueError`)           | `HazardReport`, `AIAssessment`, audit/review entries    | Invalid input, AI schema mismatch, invalid status change                                                                  | `GeminiAssessor` (retries), `CampusSafetyApplication.submit_report()`     | Error message; report not saved                                            |
| `AssessmentUnavailable` (`RuntimeError`) | `GeminiAssessor`, `AIManager`, `ImageEvidenceProcessor` | Missing key, network failure, timeout, malformed JSON after retries, invalid image                                        | `CampusSafetyApplication.submit_report()`                                 | "AI assessment unavailable… NOT saved"; menu continues                     |
| `DataStoreError` (`RuntimeError`)        | JSON and SQLite repositories, `IncidentExporter`        | Corrupt or unreadable file, SQLite error, duplicate ID, failed backup                                                     | `main.py` at startup; `CampusSafetyApplication.run()` / `submit_report()` | Clear message, exit code 1 at startup; damaged files are never overwritten |
| `ValueError`                             | `create_repository()`                                   | Unsupported `HAZARD_STORAGE_BACKEND` value                                                                                | `main.py`                                                                 | Startup error, exit code 1                                                 |
| `DashboardLaunchError` (`RuntimeError`)  | `DashboardLauncher`                                     | Streamlit not installed, `dashboard.py` missing, invalid or occupied `DASHBOARD_PORT`, or the server process cannot start | `main.main()`                                                             | "[Dashboard] Not started" warning; the CLI continues without the dashboard |
| `OSError`                                | `MediaHandler.attach_image()`                           | Image cannot be copied                                                                                                    | `MediaHandler`                                                            | Continues without the image                                                |
| `KeyboardInterrupt` / `EOFError`         | User presses Ctrl+C or input closes                     | —                                                                                                                         | `CampusSafetyApplication.run()`                                           | Goodbye message, clean exit                                                |

A missing database file is not an error: it is treated as an empty database and created on the first save.

## 11. 🗂️ Project structure

The following is the **actual source and test layout** in this project version. Generated databases, `.env`, uploads and Python cache files are intentionally omitted.

```text
INF1103_P3_T4_PART2/
├── .github/
│   └── workflows/
│       └── python-tests.yml
├── campus_safety/
│   ├── __init__.py
│   ├── application.py                 # Coordinates IO → AI → Logic → Data
│   ├── runtime.py                     # Shared .env and datastore bootstrap
│   ├── domain/                        # HazardReport, Decision, schema and audit/review entities
│   ├── io_manager/                    # IOManager, input validation and media handling
│   ├── ai_manager/                    # AI providers, assessment, Gemini prompt and image helpers
│   ├── logic_manager/                 # Scorers, priority rules, routing and facilities summary
│   ├── data_manager/                  # JSON/SQLite repositories, storage, export and factory
│   └── dashboard/
│       ├── dashboard_oop.py           # Streamlit dashboard, live previews and clear-on-save forms
│       ├── dashboard_auth.py          # DashboardAuth: username/password sign-in gate
│       ├── dashboard_extensions.py    # Dashboard presentation helpers
│       ├── background_export_service.py
│       ├── launcher.py                # DashboardLauncher: background Streamlit process for main.py
│       ├── README_INTEGRATION.md      # Original dashboard hand-over notes (this README takes precedence)
│       └── optional_theme/
├── tests/
│   ├── __init__.py
│   ├── ai_manager_test/               # AI Manager unit tests and stub providers
│   ├── logic_manager_test/            # Priority-rule and scorer tests (no __init__.py; see Section 9.1)
│   ├── test_application_workflow.py
│   ├── test_background_export_service.py
│   ├── test_dashboard_auth.py
│   ├── test_dashboard_extensions.py
│   ├── test_data_repositories.py
│   ├── test_hazard_report_domain.py
│   ├── test_io_manager.py            # Three additional pytest checks
│   ├── test_io_manager_cli.py
│   ├── test_logic_manager_rules.py
│   ├── test_facilities_data_manager_search.py
│   ├── test_facilities_logic_manager_summary.py
│   ├── test_facilities_workflow_integration.py
│   ├── test_facility_summary_domain.py
│   ├── test_incident_exporter.py
│   ├── test_single_command_launcher.py # 7 one-command startup/port tests
│   ├── run_all_tests.py              # Grouped full-suite results
│   ├── run_ai_tests.py               # Focused AI subset
│   └── run_application_tests.py      # Application workflow + main entry point subset
├── .streamlit/config.toml             # Included native Streamlit light theme
├── main.py                            # Starts dashboard and CLI in one command
├── dashboard.py                       # Root Streamlit entry point
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .env.example                       # Configuration template; contains no real credentials
├── requirements.txt
└── README.md
```

## 12. 🧱 OOP implementation guide

| Concept                           | Where it is implemented                                                                                                                                                                                                                                             | Evidence                                                                                                                                                                                                                |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 🧱 **Classes and objects**        | Managers, `CampusSafetyApplication`, `HazardReport`, `AIAssessment`, `Decision`, repositories, rules, scorers                                                                                                                                                       | Objects collaborate to assess, prioritise and store incidents.                                                                                                                                                          |
| 🔐 **Encapsulation**              | `HazardReport`, managers, repositories, `PriorityRule`                                                                                                                                                                                                              | Underscore-prefixed attributes (`_fields`, `_repository`, `_provider`); `HazardReport.get()` / `as_dict()` return deep copies; state changes go through validated methods. `PriorityRule` exposes read-only properties. |
| 🧩 **Abstract classes**           | `AssessmentProvider`, `IncidentRepository`, `PriorityRule`, `Scorer`                                                                                                                                                                                 | Each extends `ABC` with `@abstractmethod` operations. `IncidentRepository.replace_all()` also provides shared validation; `TableScorer` is an intermediate abstract class because the inherited `name` property is not implemented. **`TextMatcher` is a concrete base class**, not an ABC.                                              |
| 📜 **Interfaces / contracts**     | The same ABCs                                                                                                                                                                                                                                                       | Clients depend on the contract, not on a specific implementation.                                                                                                                                                       |
| 🌳 **Inheritance and overriding** | `GeminiAssessor`; `JsonIncidentRepository`, `SQLiteIncidentRepository`; `CriticalRule`, `HighRule`, `StandardRule`; `SeverityScorer`, `ImpactScorer`, `FrequencyScorer`; `ExactMatcher`, `FuzzyMatcher`; `InvalidRecord`, `DataStoreError`, `AssessmentUnavailable` | Subclasses override `assess`, `matches`, `score` and `replace_all`. Repositories call `super().replace_all()`; rules call `super().__init__()`.                                                                         |
| 🔄 **Polymorphism**               | `AIManager` → any `AssessmentProvider`; `DataManager` → any `IncidentRepository`; `IncidentHistory` → an interchangeable `TextMatcher`. Separately, the `PriorityRule` and `Scorer` families demonstrate overridden methods.                                                     | The same interface method works with different provider, repository and matcher implementations. Tests swap Gemini for `ConstantProvider`/`StubProvider`, SQLite for JSON, and `FuzzyMatcher` for `ExactMatcher`. In the running default priority workflow, `PriorityEvaluator` uses its own predicate rules and `ScoreCalculator` uses fixed point tables; it does **not** iterate the separately defined `PriorityRule` or `Scorer` subclasses.                                 |
| 🔗 **Association**                | `HazardReport` ↔ `AIAssessment` / `Decision`; `IOManager` ↔ `HazardReport`                                                                                                                                                                                          | Objects use each other in method calls (`attach_assessment()`, `apply_decision()`, `submission_success()`) without keeping or owning them.                                                                              |
| 🧺 **Aggregation**                | `CampusSafetyApplication` ◇ four managers; `IncidentDashboard` ◇ `DataManager`; `DataManager` ◇ `IncidentRepository`; `AIManager` ◇ `AssessmentProvider`; `LogicManager` ◇ optional evaluator/matcher/reporter                                                        | Parts are created elsewhere and injected; they can exist and be tested independently.                                                                                                                                   |
| 🏗️ **Composition**                | `IOManager` ◆ `MediaHandler`; `DataManager` ◆ `IncidentExporter`; `BackgroundExportService` ◆ `ThreadPoolExecutor`; `PriorityEvaluator` ◆ its default `ScoreCalculator`                                                                                               | The owner creates the part in its constructor and controls its lifetime; the part is not shared.                                                                                                                        |

**Value objects:** `Decision`, `AIAssessment`, `IncidentAuditEntry`, `AIReviewEntry` and `FacilitySummaryReport` are frozen dataclasses, validated on construction.

### 12.1 🧩 SOLID evidence

- **SRP:** each manager has one responsibility, and `CampusSafetyApplication` only coordinates. Inside the managers, responsibilities are split further: `GeminiPromptBuilder` (prompt), `ImageEvidenceProcessor` (images), `InputValidator` (input rules), `MediaHandler` (file copying), `Router` (routing), `FacilitySummaryBuilder` (summary metrics), `IncidentExporter` (file output), `DashboardAuth` (dashboard sign-in) and `DashboardLauncher` (background dashboard process).
- **OCP:** the provider and repository contracts allow new implementations to be injected without changing their manager clients. `TextMatcher` can also be replaced in `IncidentHistory`. The separate `PriorityRule` and `Scorer` subclasses demonstrate extensible class hierarchies, but **are not wired into the current default `PriorityEvaluator`/`ScoreCalculator` execution path**; integrating them into live scoring would require additional changes. The configuration tests in `test_logic_manager_rules.py` (e.g. `test_custom_high_score_threshold`, `test_custom_calculator_can_be_injected`) demonstrate configurable thresholds and an injected calculator. A new storage backend name must still be registered in `repository_factory.py`.
- **LSP:** `JsonIncidentRepository` and `SQLiteIncidentRepository` share the **same** test contract in `test_data_repositories.py`; `ConstantProvider`/`StubProvider` stand in for the AI provider; `ExactMatcher` and `FuzzyMatcher` can each be passed where `TextMatcher` is expected. These substitutions leave the consuming interfaces unchanged.
- **DIP:** `CampusSafetyApplication`, `AIManager`, `DataManager` and `LogicManager` can receive collaborators through their constructors; `CampusSafetyApplication.create_default()` chooses the default implementations. The dashboard receives a `DataManager` rather than constructing its own persistence adapter in the UI class.

### 12.2 Current class inventory and UML relationship guide

The **48 project-defined classes** were counted from the top-level `class` declarations in `campus_safety/**/*.py` on 18 November 2026. They are distributed as follows; `main.py`, `dashboard.py`, `runtime.py`, package initialisers and helper modules that define no classes are **not extra classes**.

| Layer / folder | Class count | Classes |
| --- | ---: | --- |
| Application controller | **1** | `CampusSafetyApplication` |
| IO Manager | **3** | `IOManager`, `InputValidator`, `MediaHandler` |
| AI Manager | **7** | `AIManager`, `AIAssessment`, `AssessmentProvider`, `GeminiAssessor`, `GeminiPromptBuilder`, `ImageEvidenceProcessor`, `AssessmentUnavailable` |
| Logic Manager | **20** | `LogicManager`, `CriticalRule`, `HighRule`, `StandardRule`, `PriorityRule`, `ScoreCalculator`, `Scorer`, `TableScorer`, `SeverityScorer`, `ImpactScorer`, `FrequencyScorer`, `PriorityEvaluator`, `Router`, `TextMatcher`, `ExactMatcher`, `FuzzyMatcher`, `IncidentHistory`, `IncidentReporter`, `SeveritySorter`, `FacilitySummaryBuilder` |
| Data Manager | **6** | `DataManager`, `DataStoreError`, `IncidentExporter`, `IncidentRepository`, `JsonIncidentRepository`, `SQLiteIncidentRepository` |
| Domain | **6** | `HazardReport`, `Decision`, `FacilitySummaryReport`, `IncidentAuditEntry`, `AIReviewEntry`, `InvalidRecord` |
| Dashboard | **5** | `IncidentDashboard`, `DashboardAuth`, `BackgroundExportService`, `DashboardLauncher`, `DashboardLaunchError` |
| **Total** | **48** | **48 application classes across 47 source files** |

**Inheritance (UML generalisation, hollow triangle pointing to the parent):**

```text
AssessmentProvider <|-- GeminiAssessor
IncidentRepository <|-- JsonIncidentRepository
IncidentRepository <|-- SQLiteIncidentRepository
PriorityRule <|-- CriticalRule
PriorityRule <|-- HighRule
PriorityRule <|-- StandardRule
Scorer <|-- FrequencyScorer
Scorer <|-- TableScorer
TableScorer <|-- SeverityScorer
TableScorer <|-- ImpactScorer
TextMatcher <|-- ExactMatcher
TextMatcher <|-- FuzzyMatcher
ValueError <|-- InvalidRecord
RuntimeError <|-- AssessmentUnavailable
RuntimeError <|-- DataStoreError
RuntimeError <|-- DashboardLaunchError
```

Here `Parent <|-- Child` means **Child inherits from Parent**. `ValueError` and `RuntimeError` are **Python built-in classes** shown only as inheritance parents, and are **not included** in the 48-class count. `DashboardLaunchError` and `DashboardLauncher` are separate project classes declared in the same `launcher.py` file.

**Important current collaborations (use directed association/dependency arrows where applicable, not inheritance):**

- `CampusSafetyApplication` holds the four injected managers: `IOManager`, `AIManager`, `LogicManager`, `DataManager`.
- `IOManager` creates `MediaHandler` and calls input validation helpers from `InputValidator`; it constructs/returns `HazardReport` instances for submissions.
- `AIManager` uses an `AssessmentProvider` (normally `GeminiAssessor`), which uses `GeminiPromptBuilder` and `ImageEvidenceProcessor` and produces `AIAssessment`.
- `LogicManager` uses `PriorityEvaluator`, temporarily creates `IncidentHistory` for matching/frequency and uses `IncidentReporter` for sorting and facilities summaries. `PriorityEvaluator` uses `ScoreCalculator`; `IncidentHistory` uses a `TextMatcher` (or substitutable subtype).
- `DataManager` holds an `IncidentRepository` and creates `IncidentExporter`; repository implementations store/retrieve `HazardReport` records, including `IncidentAuditEntry` and `AIReviewEntry` histories. `HazardReport` also attaches `AIAssessment` and `Decision` value objects; the facilities summary operation returns `FacilitySummaryReport`.
- `incident_dashboard()` calls `DashboardAuth` **before** constructing `IncidentDashboard`; it then injects `DataManager` into `IncidentDashboard`. Dashboard export handling uses `BackgroundExportService`. `DashboardLauncher` starts the Streamlit process from `main.py`. These classes have **dependencies/associations**, not inheritance from one another.
- Custom exception **dependencies** are separate from their superclass arrows: invalid domain records raise `InvalidRecord`, AI failures raise `AssessmentUnavailable`, storage failures raise `DataStoreError`, and dashboard launch failures raise `DashboardLaunchError`. Their actual callers catch/handle them as documented in Section 10.

**UML accuracy note:** the class inventory includes classes kept for standalone examples or tests. In the latest runtime flow, `PriorityEvaluator` does not instantiate `PriorityRule` subclasses, `ScoreCalculator` does not call the separate `Scorer` hierarchy, and `IncidentReporter` does not call `FacilitySummaryBuilder` / `SeveritySorter`. Do not draw these as **runtime ownership/composition** relationships without changing the implementation. A source import, dependency, aggregation, association, composition and inheritance are **different UML relationships**; choose arrows based on actual object creation and method calls.

## 👥 Created By

🎓 **INF1103 – Programming Fundamentals with DevOps**

🏫 **Team 4 | Singapore Institute of Technology (SIT)**

### 👨‍💻 Team Members

- CHAN RUI RU
- CHEE BO YU
- KOH KA-WEI DARRYL
- CHUA QIN NI JAMIE
- KHUN AUNG HEIN
- CHIA SENG CHAN

## 🔗 Repository

[INF1103 Team 4 – GitHub](https://github.com/2603229/INF1103_P3_T4_PART2)