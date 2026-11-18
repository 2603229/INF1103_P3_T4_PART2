# 🛡️ Campus Safety Hazard Reporting System — INF1103 Part 2

## 1. 📌 Project overview

This project refactors the Phase 1 Campus Safety Hazard Reporting System into a modular, object-oriented Python application. The current source declares **34 project-defined classes across 33 Python class-bearing files** in the application controller, four managers, domain objects and dashboard. The two classes `DashboardLauncher` and `DashboardLaunchError` share `launcher.py`; the built-in exception types extended by project exceptions are not counted as application classes. Students and staff submit hazard reports through a command-line interface (CLI). Each report is assessed by Google Gemini, prioritised by business rules and saved to a JSON or SQLite database.

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
| ✅ Tests                   | **269 `unittest`-discoverable tests** and **272 `pytest` tests** (plus 77 reported subtests), all passing locally on 18 November 2026. This includes 7 single-command launcher tests and 3 additional pytest-style IO checks — Section 9                      |

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
| Business rules  | `LogicManager` delegates to `PriorityEvaluator` (which uses `ScoreCalculator`), `IncidentHistory` (which uses `TextMatcher`) and `IncidentReporter`. Priority predicates, routing and severity ordering are implemented within these existing classes                                            |
| Persistence     | `DataManager` → `IncidentRepository` ABC → JSON or SQLite implementation                                                                      |
| Program flow    | `CampusSafetyApplication` coordinating injected managers                                                                                      |

The Phase 1 domain rules are preserved, including the **multi-condition rule** using two AI fields: _Critical severity **and** Severe/Catastrophic impact → Critical priority_. In the running workflow, `PriorityEvaluator._is_critical()` applies that condition. There is no separate `CriticalRule` class in the supplied source.

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

Reporter name and contact are excluded from the prompt, and recognisable names, emails and Singapore phone numbers are redacted from free text (`GeminiPromptBuilder`). Images must be JPEG/PNG/WEBP, at most 10 MiB, and their content must match their extension (`ImageEvidenceProcessor`). `GeminiAssessor` attempts each configured model up to twice (by default) before trying the next model; model names and order come from `GEMINI_MODELS` when set. If every attempt fails, the application raises `AssessmentUnavailable` rather than saving an unassessed report. See Section 8.5 for troubleshooting.

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

**Implementation detail:** the running priority path is `LogicManager` → `PriorityEvaluator` → `ScoreCalculator`. `ScoreCalculator` contains the severity, impact and frequency point tables; `PriorityEvaluator` evaluates Critical → High → Normal conditions and selects the matching dispatch queue. `IncidentReporter` itself sorts incidents by severity and calculates facilities summaries. The supplied source does **not** contain separate `PriorityRule`, `Scorer`, `Router`, `FacilitySummaryBuilder` or `SeveritySorter` classes.

**Duplicate detection:** a new report matching an _open_ incident at the same location and asset is marked `Potential Duplicate of INCIDENT-xxx`. `TextMatcher` tolerates typos ("Libary" ≈ "Library") with its default similarity threshold of 0.85, but requires numbers and standalone single-letter identifiers to match ("Lab 1" ≠ "Lab 10"). Its threshold can be configured, including `1.0` for strict matching.

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

**Manual demonstration / verification (use a disposable test database):**

- **Status change:** Select an incident that is `Pending Review`, choose `In Progress`, confirm the live preview, enter a reason, save, then confirm the reason clears and an entry appears in **Activity history**.
- **AI review:** On a record with a completed Gemini assessment, choose `Flagged as Incorrect`, confirm the preview, enter a fictional reviewer name and reason, save, then confirm the inputs clear, the decision resets to `Accepted`, and the saved entry appears in **AI Review History**.
- **Validation:** Try submitting a status change with an empty reason or an AI review without a reviewer name. The warning should appear, and existing typed data should not be intentionally reset.
- **Data integrity:** Confirm that changing a review decision does **not** overwrite Gemini category, severity, risk summary, priority, or the incident's status.

## 8. 🛠️ Installation and run guide

### 8.1 Local (Windows PowerShell, Python 3.12)

```powershell
git clone https://github.com/2603229/INF1103_P3_T4_PART2.git
cd INF1103_P3_T4_PART2
python -m pip install -r requirements.txt
Copy-Item .env.example .env             # first-time setup (edit locally; do not commit)
# Set GEMINI_API_KEY for real submissions; change the demo dashboard password.
python -m unittest discover -s tests -t . -v
python main.py                          # launches dashboard + CLI together
# Optional alternatives:
python main.py --cli-only               # CLI without dashboard
python main.py --no-browser             # both, without automatic browser opening
python -m streamlit run dashboard.py    # dashboard only
```

For the normal integrated workflow, run **`python main.py`** in the project root. The dashboard starts automatically, and your browser opens at **http://localhost:8501** (or another available local port if 8501 is occupied). The CLI remains interactive in the same terminal. Both processes share environment settings and the same database. **When you exit the CLI, the dashboard server stops as well.** If a browser does not open, use the URL printed in the terminal. The dashboard first shows a sign-in form; use `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD` from `.env` (defaults `admin` / `admin123`, see Section 8.3). `DASHBOARD_PORT` optionally fixes the dashboard port; an explicit occupied port generates a warning rather than redirecting to a different service. The optional `.env` applies to both interfaces. The supplied `.env.example` selects **SQLite**; if `.env` is absent and the variable is unset, both use **JSON** storage by default; a Gemini API key is required only for real AI-assessed report submissions. If Streamlit is not installed, the CLI continues and displays installation instructions. A virtual environment is not required.

A virtual environment is optional; it is not required for these commands. SQLite is part of Python's standard library; do **not** install a separate `sqlite3` package.

### 8.2 🐳 Docker

Requires Docker Desktop to be running. No local Python installation is needed. **Create your own `.env` from `.env.example` before using the `--env-file .env` commands**; keep its credentials private.

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

Copy `.env.example` to `.env`, set your own secret values and keep `.env` outside Git and shared submissions. Environment variables supplied by the operating system or Docker take precedence over the file.

| Variable | Purpose | When unset |
| --- | --- | --- |
| `GEMINI_API_KEY` | Gemini API credential for real incident submissions | Live AI submission is unavailable |
| `GEMINI_MODELS` | Ordered, comma-separated Gemini model IDs; the provider tries each in turn | Code-defined list in `gemini_assessor.py` (`gemini-3.8-flash,gemini-3.6-flash` in this upload) |
| `HAZARD_STORAGE_BACKEND` | `json` or `sqlite` | `json`; the supplied `.env.example` uses `sqlite` |
| `SQLITE_DB_PATH` | Optional path for the SQLite database | `hazardreports.sqlite3` under `HAZARD_DATA_DIR` |
| `INCIDENTS_DB` | Optional path for the JSON repository | JSON repository's default path under `HAZARD_DATA_DIR` |
| `HAZARD_DATA_DIR` | Shared storage directory | Project folder locally; `/data` in Docker |
| `DASHBOARD_PORT` | Port selected by `python main.py` | `8501`, or a free port if in use; an explicitly set occupied port raises a warning |
| `DASHBOARD_USERNAME` | Local dashboard username | `admin` |
| `DASHBOARD_PASSWORD` | Local dashboard password | `admin123` — **replace this demo default** |

**Important:** `.env.example` is a template, not a secret configuration. Never commit `.env` or share Gemini keys, passwords, real reporter information, saved SQLite/JSON records or uploaded evidence. Changing storage backends does **not** migrate records automatically; the SQLite repository provides an explicit import API.

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

### 8.5 🤖 Gemini availability and troubleshooting

Live AI assessment uses `GeminiAssessor` (`campus_safety/ai_manager/gemini_assessor.py`). The built-in model order in this upload is `gemini-3.8-flash,gemini-3.6-flash`; the `GEMINI_MODELS` environment variable overrides it. Confirm the **exact model IDs and access** supported by your Gemini project before using them; the README does not establish that a particular model is currently available.

```dotenv
# Example only: replace with model IDs available to your API project.
# GEMINI_MODELS=your-primary-model,your-fallback-model
```

- **Both models report high demand, rate limiting or service unavailability:** this is an API-side response, not proof that the IO, Logic or Data Manager is broken. `GeminiAssessor` tries each model up to **two times** by default with a short delay between attempts, then moves to the next. If all attempts fail, **the incident is not saved**. Check model status, project quotas, rate limits and network access, then retry when service is available.
- **Model not found or not permitted:** verify `GEMINI_MODELS` against the model IDs available to the API key/project. Model fallback cannot help when **every** configured ID is unsupported or inaccessible.
- **Missing API key:** set `GEMINI_API_KEY` in `.env` or in the process environment. Do not hard-code the key or commit it.
- **Dashboard opens but no reports can be submitted:** the dashboard can still read existing records and manage them without live Gemini; **new incident submission requires a valid five-field response** from a working AI provider. Offline automated tests use stubs, so passing tests alone does not verify current Gemini availability.
- **Dashboard shows the wrong database:** use the **same** `HAZARD_STORAGE_BACKEND`, `HAZARD_DATA_DIR` and relevant database path settings for both CLI and dashboard. For Docker, use the same named `/data` volume. A database viewer is available under **Data & backups** when using SQLite.
- **Dashboard sign-in missing:** run the root entry point `python -m streamlit run dashboard.py` (or `python main.py`), which calls `incident_dashboard()` and its login gate. For Docker use the dashboard command in Section 8.2, check your `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`, and rebuild the image after code changes.

Do not treat error strings such as “high demand” as evidence of success or fabricate an AI assessment. The system intentionally prevents unassessed incidents from entering the database.

## 9. ✅ Automated tests and CI

**Verified locally on 18 November 2026 using the source in this archive:**

- `python -m unittest discover -s tests -t . -q` — **269 tests passed**.
- `python -m pytest tests -q` — **272 tests passed, with 77 subtests reported as passed**.

These are offline automated results. They do **not** establish live Gemini availability, a successful Docker build, a visual browser smoke test or a completed GitHub-hosted CI run. The additional `pytest` cases are not needed to use the application.

```powershell
# Source syntax check
python -m compileall -q main.py dashboard.py campus_safety tests

# Standard unit-test suite, also used by GitHub Actions
python -m unittest discover -s tests -t . -v

# Optional focused runners
python -m tests.run_all_tests
python -m tests.run_ai_tests
python -m tests.run_application_tests
python -m unittest tests.test_single_command_launcher -v

# Optional pytest run (pytest is not a runtime dependency)
python -m pip install pytest
python -m pytest tests -q
```

### 9.1 Test coverage in this project version

| Area / test module | `unittest` tests | Main coverage |
| --- | ---: | --- |
| AI Manager (`tests/ai_manager_test/`, six modules) | 51 | Schema validation, provider contract, Gemini retries/fallback, prompts and images |
| `test_logic_manager_rules.py` | 42 | Priority conditions, score calculations, text matching and facilities summaries |
| `test_data_repositories.py` | 51 | JSON/SQLite CRUD, audit history, AI reviews, migration, backups and corruption |
| `test_hazard_report_domain.py` | 19 | Domain validation, status history and AI-review rules |
| `test_io_manager_cli.py` | 14 | CLI validation, menu and facilities search/summary output |
| `test_application_workflow.py` | 30 | Integrated workflow, cancellation and failure handling |
| `test_facilities_data_manager_search.py` | 10 | Storage search and filters |
| `test_facilities_logic_manager_summary.py` | 2 | Facilities aggregation |
| `test_facilities_workflow_integration.py` | 1 | Integrated facilities workflow |
| `test_facility_summary_domain.py` | 2 | Summary value object |
| `test_incident_exporter.py` | 4 | CSV/TXT export behavior |
| `test_background_export_service.py` | 9 | Threaded exports |
| `test_dashboard_extensions.py` | 22 | Dashboard helpers and presentation behavior |
| `test_dashboard_auth.py` | 5 | Dashboard credential validation |
| `test_single_command_launcher.py` | 7 | Single-command launch and process lifecycle |
| **Total discovered by `unittest`** | **269** | **269 passed locally** |

The separate file `tests/test_io_manager.py` contains **3 pytest-style tests** that standard `unittest` discovery does not collect. That explains the difference between the two test commands: **269 + 3 = 272 pytest tests**. Pytest reports **77 passed subtests** separately; do not add these to the 272 collected test count. The former `tests/logic_manager_test/` folder and its 25 additional tests do **not** exist in this archive, so commands for that folder should not be used.

**Manual browser verification is still needed:** open Streamlit, sign in and out, review live status/AI-review previews, verify form fields clear only after a successful save, inspect the SQLite viewer and confirm backed-up records remain accessible. Offline unit tests do not confirm live Gemini availability or the visual appearance of the app.

**CI configuration:** `.github/workflows/python-tests.yml` runs for pushes to `main` and `feature/**` and pull requests to `main`. Its `basic-checks` job verifies required files, compiles Python, installs dependencies, runs AI tests, checks dashboard imports and runs the **269-test `unittest`-discoverable suite**. A dependent `docker` job builds the image, reruns that suite in the container and smoke-tests CLI exit using menu option 6. This workflow does **not** run the 3 pytest-only checks. Consult actual GitHub Actions logs before claiming hosted CI or Docker success.

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

The following is the **actual source and test layout** in this project version. Generated databases, `.env`, uploads, Git history and Python cache files are intentionally omitted. The source archive contains these local artifacts, but they should not be included in a public submission.

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
│   ├── logic_manager/                 # PriorityEvaluator, ScoreCalculator, TextMatcher, history and summary
│   ├── data_manager/                  # JSON/SQLite repositories, storage, export and factory
│   └── dashboard/
│       ├── dashboard_oop.py           # Streamlit dashboard, live previews and clear-on-save forms
│       ├── dashboard_auth.py          # DashboardAuth: username/password sign-in gate
│       ├── dashboard_extensions.py    # Dashboard presentation helpers
│       ├── background_export_service.py
│       ├── launcher.py                # DashboardLauncher: background Streamlit process for main.py
│       └── optional_theme/
├── tests/
│   ├── __init__.py
│   ├── ai_manager_test/               # AI Manager unit tests and stub providers
│   ├── test_application_workflow.py
│   ├── test_background_export_service.py
│   ├── test_dashboard_auth.py
│   ├── test_dashboard_extensions.py
│   ├── test_data_repositories.py
│   ├── test_hazard_report_domain.py
│   ├── test_io_manager.py             # Three additional pytest-only checks
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

This section describes the **classes that actually exist in the supplied project**, not earlier experimental or removed classes. The class inventory below can be used to check the UML diagram and the one-class-per-file requirement.

| Concept | Actual project evidence | Explanation |
| --- | --- | --- |
| **Classes and objects** | `CampusSafetyApplication`, four managers, `HazardReport`, `AIAssessment`, `Decision`, repositories and dashboard classes | Objects coordinate input, Gemini assessment, priority decisions, persistence and display. |
| **Encapsulation** | `HazardReport`, `AIManager`, `DataManager`, `PriorityEvaluator`, `TextMatcher` | Internal attributes are managed through methods/properties. `HazardReport.get()` and `as_dict()` return defensive copies; `TextMatcher.threshold` validates values. |
| **Abstraction** | `AssessmentProvider`, `IncidentRepository` | Both are abstract base classes (`ABC`) defining operations concrete implementations must provide. |
| **Inheritance / overriding** | `GeminiAssessor(AssessmentProvider)`; `JsonIncidentRepository(IncidentRepository)`; `SQLiteIncidentRepository(IncidentRepository)` | Concrete implementations fulfil the provider/repository contracts. `InvalidRecord`, `AssessmentUnavailable`, `DataStoreError` and `DashboardLaunchError` extend Python exception types. |
| **Polymorphism** | `AIManager` with different `AssessmentProvider` instances; `DataManager` with either repository | The caller uses a common `assess()` or persistence interface regardless of which concrete implementation is injected. Offline tests inject stub or constant AI providers. |
| **Dependency injection / aggregation** | `CampusSafetyApplication` receives all four managers; `AIManager` receives a provider; `DataManager` receives a repository; `IncidentDashboard` receives a `DataManager` | Collaborating objects can be constructed and tested separately from their clients. |
| **Composition / owned helpers** | `IOManager` constructs `MediaHandler`; `DataManager` constructs `IncidentExporter`; `PriorityEvaluator` constructs its default `ScoreCalculator`; `BackgroundExportService` owns a `ThreadPoolExecutor` | Each owner creates and manages its internal helper under the default construction path. |
| **Dependencies / associations** | `CampusSafetyApplication` passes `HazardReport` to managers; `LogicManager` delegates to `IncidentHistory`, `PriorityEvaluator`, `IncidentReporter`; the dashboard uses `DashboardAuth` | A method call or temporary object use is a dependency, not necessarily an ownership relationship. |

**Immutable value objects:** `Decision`, `AIAssessment`, `IncidentAuditEntry`, `AIReviewEntry` and `FacilitySummaryReport` are frozen dataclasses. `HazardReport` is a mutable, validated domain entity with controlled state changes.

### 12.1 🧩 SOLID evidence

- **Single Responsibility Principle (SRP):** the four managers have distinct roles, while `CampusSafetyApplication` orchestrates them. Supporting classes separate prompt construction (`GeminiPromptBuilder`), image processing (`ImageEvidenceProcessor`), input validation (`InputValidator`), priority calculation (`ScoreCalculator`), historical matching (`IncidentHistory`), facilities reporting (`IncidentReporter`), export (`IncidentExporter`) and dashboard login (`DashboardAuth`).
- **Open/Closed Principle (OCP):** clients can accept additional implementations of `AssessmentProvider` and `IncidentRepository` without changing their high-level call sites. `PriorityEvaluator` accepts an injected calculator and configurable queue/threshold settings. Selecting a completely new repository backend by name still requires a factory change in `repository_factory.py`.
- **Liskov Substitution Principle (LSP):** both JSON and SQLite repositories implement the same `IncidentRepository` operations and are exercised through shared repository tests; AI provider test doubles fulfil the same `AssessmentProvider` contract as `GeminiAssessor`.
- **Interface Segregation Principle (ISP):** the provider abstraction concentrates on `assess()`, while the repository abstraction concentrates on persistence. They keep AI-specific operations separate from data storage 

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