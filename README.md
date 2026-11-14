# 🛡️ Campus Safety Hazard Reporting System — INF1103 Part 2

**P3 Team 4 · Singapore Institute of Technology (SIT)**  

## 1. 📌 Project overview

This project refactors the Phase 1 Campus Safety Hazard Reporting System into a modular, object-oriented Python application. Students and staff submit hazard reports through a command-line interface (CLI). Each report is assessed by Google Gemini, prioritised by business rules and saved to a JSON or SQLite database.

Every **new report** follows the four-manager workflow, coordinated by `CampusSafetyApplication`:

1. ⌨️ **IO Manager** — collects and validates user input, and displays records, results and summaries.
2. 🤖 **AI Manager** — builds a privacy-aware prompt, calls the live Gemini API, parses the JSON reply and validates every field.
3. 🧠 **Logic Manager** — scores severity, operational impact and historical frequency to decide priority, routing and duplicates.
4. 💾 **Data Manager** — saves, loads, queries and filters incidents through interchangeable JSON or SQLite repositories.

> **Business rule:** a new incident is **not saved** if the AI assessment is unavailable or invalid. The live Gemini API is needed for real submissions but **not** for the automated tests.

| Deliverable | Where |
| --- | --- |
| 🆕 New feature | **Facilities Search & Summary Report** — Section 6 |
| 🚀 Advanced feature | **SQLite database integration (full CRUD)** — Section 7.1 |
| 🖥️ Additional enhancements | **AI Assessment Review & Feedback**, **Incident Status Audit Trail**, Streamlit dashboard, live form previews, field clearing and background CSV export — Sections 7.2–7.5 |
| 🐳 Docker | `Dockerfile` — Section 8.2 |
| ⚙️ CI | `.github/workflows/python-tests.yml` — Section 9 |
| ✅ Tests | **233 offline `unittest` tests passed**; 51 AI tests passed in a separate overlapping runner — Section 9 |

## 2. ✨ Main application functions

CLI menu (displayed by `IOManager`, dispatched by `CampusSafetyApplication.run()`):

1. **Submit New Hazard Report** — enter reporter details, location, people affected, asset and description, plus an optional image. Review the AI assessment and priority breakdown, then confirm to save.
2. **View All Logged Incidents** — list saved reports.
3. **View Top 5 Most Frequent Hazards** — the five most frequently reported AI hazard categories.
4. **Search and Filter Incidents** 🆕 — filter by location keyword, status, category and minimum severity.
5. **View Facilities Summary Report** 🆕 — active workload, backlog rate, urgent hazards, and counts by location and category.
6. **Exit**

The **Streamlit dashboard** (Section 7.4) works on the same database and adds management tasks:

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

`main.py` only starts the application. `CampusSafetyApplication.create_default()` loads `.env`, creates each manager and injects them.

### 3.1 End-to-end example: incident submission → dashboard

1. **Start the CLI:** run `python main.py`; the entry point creates `CampusSafetyApplication` and the four managers.
2. **Report a hazard:** select menu option 1 and enter a fictional reporter, site/location, affected asset, number of people and description; attach a supported image if available. `IOManager` validates the input and creates a `HazardReport`.
3. **Obtain an AI assessment:** `CampusSafetyApplication` invokes `AIManager`; the `AssessmentProvider` implementation returns a validated `AIAssessment`. If assessment fails, **nothing is saved**.
4. **Evaluate and confirm:** `LogicManager` checks historical frequency/duplicates, calculates priority and routing, and the CLI displays the results for user confirmation.
5. **Persist the record:** `DataManager` uses the configured `IncidentRepository` (JSON or SQLite) to store the report and assign its incident ID.
6. **Monitor and update:** in a separate terminal run the Streamlit dashboard. It reads the same backend through `DataManager`. The user can inspect the incident, add a **status change with a reason** (audit history), or save a **human AI-review decision** (review history); neither review changes the original AI assessment.

**Architecture note:** `IOManager`, `AIManager`, `LogicManager` and `DataManager` are collaborators injected into `CampusSafetyApplication`; the CLI's **Input → Assess → Prioritise → Save** sequence is an execution flow, **not** evidence that managers directly call one another. The dashboard is an independent entry point in `campus_safety/dashboard/dashboard_oop.py` and does not submit new Gemini assessments.


## 4. 🔁 Refactoring from Phase 1

Phase 1 passed plain dictionaries between procedural functions and stored them in a JSON file. Phase 2 keeps the same record fields (so Phase 1 JSON records still load) but moves each responsibility into classes:

| Responsibility | Phase 2 object-oriented design |
| --- | --- |
| Incident record | `HazardReport` entity with validated construction and controlled state changes |
| Input / output | `IOManager` with `InputValidator` and `MediaHandler`, using injectable read/write callables |
| AI processing | `AIManager` → `AssessmentProvider` ABC → `GeminiAssessor`, with `GeminiPromptBuilder`, `ImageEvidenceProcessor` and `AIAssessment` validation |
| Business rules | `Scorer` / `PriorityRule` / `TextMatcher` hierarchies combined by `PriorityEvaluator` and `Router` |
| Persistence | `DataManager` → `IncidentRepository` ABC → JSON or SQLite implementation |
| Program flow | `CampusSafetyApplication` coordinating injected managers |

The Phase 1 domain rules are preserved, including the **multi-condition rule** using two AI fields: *Critical severity **and** Severe/Catastrophic impact → Critical priority* (`CriticalRule`).

## 5. 🧠 Business rules

### 5.1 Input validation

| Field | Rule |
| --- | --- |
| Reporter name | Letters, spaces, `'`, `.` and `-` only |
| Contact | SIT email (`...@sit.singaporetech.edu.sg`) or an 8-digit number starting with 6, 8 or 9 |
| Location | Not empty |
| People affected | Whole number from 1 to 1000 |
| Asset / summary | At least 5 characters in the CLI (`InputValidator`); at least 3 in the domain model |
| Description | At least 15 characters |

### 5.2 AI assessment (`AIAssessment`)

Gemini must return a JSON object with **exactly** five string fields: `risk_summary`, `category`, `severity`, `operational_impact` and `contextual_insights`.

- Category: Electrical, Plumbing, Structural, HVAC, IT/Equipment
- Severity: Low, Medium, High, Critical
- Operational impact: Minor, Moderate, Severe, Catastrophic

Reporter name and contact are excluded from the prompt, and recognisable names, emails and Singapore phone numbers are redacted from free text (`GeminiPromptBuilder`). Images must be JPEG/PNG/WEBP, at most 10 MiB, and their content must match their extension (`ImageEvidenceProcessor`). `GeminiAssessor` retries failed calls and falls back through the models listed in `GEMINI_MODELS`.

### 5.3 Priority scoring (`LogicManager`)

| Factor | Points |
| --- | --- |
| Severity | Low 1 · Medium 2 · High 4 · Critical 5 |
| Operational impact | Minor 1 · Moderate 2 · Severe 4 · Catastrophic 5 |
| Historical frequency (resolved/closed incidents at the same location and asset) | 1 → 1 · 2–4 → 2 · 5+ → 3 |

| Priority | Rule (first match wins) | Route |
| --- | --- | --- |
| Critical | Severity Critical **and** impact Severe/Catastrophic | Urgent Emergency Dispatch |
| High | Severity High/Critical, **or** impact Severe/Catastrophic, **or** score ≥ 7 | Priority Maintenance Queue |
| Normal | Everything else | Standard Maintenance Queue |

**Duplicate detection:** a new report matching an *open* incident at the same location and asset is marked `Potential Duplicate of INCIDENT-xxx`. `FuzzyMatcher` tolerates typos ("Libary" ≈ "Library") but requires numbers to match exactly ("Lab 1" ≠ "Lab 10").

## 6. 🆕 New feature — Facilities Search & Summary Report

**Problem it addresses:** in Phase 1, facilities staff could only scroll through every incident. They had no way to find the hazards in one building, see what is still waiting for repair, or measure the maintenance backlog.

**How a user accesses it:**

- **Menu option 4 — Search and Filter Incidents.** Enter a location keyword, then optionally choose a status, category and minimum severity by number (press Enter to skip any filter). Matching incidents are listed with their ID, location, category, severity, priority and status.
- **Menu option 5 — View Facilities Summary Report.** Shows active hazards (excluding Resolved/Closed), pending repairs, in-progress work, urgent (High/Critical priority) hazards, the **maintenance backlog rate** (pending ÷ active × 100), and active hazards by location and category.

**Classes involved:**

| Manager | Class / method | Responsibility |
| --- | --- | --- |
| IO | `IOManager.get_search_criteria()`, `view_search_results()`, `view_facilities_summary()` | Collect and validate filters; display results and metrics |
| Data | `DataManager.search()` | Filter stored records by location, status, category and severity rank |
| Logic | `LogicManager.generate_facilities_summary()` → `FacilitySummaryBuilder` | Apply the "active hazard" and "urgent" business rules and aggregate counts |
| Domain | `FacilitySummaryReport` | Immutable result value object with the computed `maintenance_backlog_rate` |
| Application | `CampusSafetyApplication.search_incidents()`, `facilities_summary()` | Pass data between the managers |

**How it is tested:** `test_facilities_data_manager_search.py`, `test_facilities_logic_manager_summary.py`, `test_facility_summary_domain.py`, `test_facilities_workflow_integration.py`, the `FacilitiesSummaryRuleTests` in `test_logic_manager_rules.py`, the search/summary tests in `test_io_manager_cli.py`, and end-to-end tests in `test_application_workflow.py`.

## 7. 🚀 Advanced feature and other extensions

### 7.1 🗄️ SQLite database integration (advanced feature)

**Implementation:** `campus_safety/data_manager/sqlite_incident_repository.py`
**Related files:** `data_manager.py`, `incident_repository.py`, `json_incident_repository.py` and `repository_factory.py`.

`DataManager` depends on the abstract `IncidentRepository` contract, not on SQL statements. Both `JsonIncidentRepository` and `SQLiteIncidentRepository` implement it, so the backend is chosen in `.env` without changing any other code.

| SQLite capability | Implementation |
| --- | --- |
| ➕ **Create** | Insert a validated incident and allocate a persistent incident ID in one transaction. |
| 🔍 **Read** | Load and validate stored records. |
| ✏️ **Update** | Persist modified records, including status and audit history. |
| 🗑️ **Delete** | Remove a selected record through `DataManager.delete()`. |
| 💾 **Persistence** | Data and the ID counter survive restarts; deleted IDs are never reused. |
| 🔒 **Transactions** | Parameterised SQL with `BEGIN IMMEDIATE` to prevent concurrent ID collisions. |
| 🗃️ **Backup / restore** | Consistent backups via the SQLite backup API; integrity-checked before restoring. |
| 🔄 **Migration** | `import_records()` imports existing JSON records into an empty SQLite database. |
| ⚠️ **Error handling** | Corrupt files or records raise `DataStoreError` instead of being silently discarded. |

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

> **Scope:** reviewer names are self-entered, **not authenticated**; the current dashboard is a local educational prototype, not a production approval system.

### 7.4 🖥️ Streamlit dashboard and threaded CSV export

**Implementation:** `campus_safety/dashboard/` — `dashboard_oop.py` (`IncidentDashboard`), `dashboard_extensions.py` (presentation helpers) and `background_export_service.py` (`BackgroundExportService`).

The dashboard is organised into four navigation pages:

| Page | Features |
| --- | --- |
| **Overview** | Total, active, high-priority and resolved counters; priority queue; workload-by-status chart; recently reported incidents. Summaries can auto-refresh every 15 seconds. |
| **Incidents** | Search, status/priority/category/date filters, sorting and pagination; inspect case details and image evidence; update status, save human AI reviews, view both histories, or delete a case with confirmation. |
| **Insights** | Incident category, severity and priority charts; monthly reporting trend; frequently reported locations. |
| **Data & backups** | Prepare incident CSV exports in a worker thread; download CSV/TXT; list and restore available repository backups after confirmation. |

`IncidentDashboard` receives a `DataManager` and does not access SQL or Gemini directly. The dashboard and CLI therefore reuse the same persistence, validation and incident domain logic. `BackgroundExportService` uses a `ThreadPoolExecutor` to produce a CSV from an incident snapshot without blocking the rest of the dashboard.

The dashboard displays **Singapore time (SGT)** where timestamps are shown. Auto-refresh is limited to Overview and Insights; incident forms deliberately do not refresh every 15 seconds to avoid interrupting edits. Charts and controls use a high-contrast light presentation theme, including readable white text on blue primary action buttons.

> **Security scope:** This is a local prototype, not an authenticated operational deployment. A reviewer name is self-entered, and status audit entries are application-level history rather than tamper-proof security logs. Do not expose the dashboard publicly or use real personal information for demonstration data.

### 7.5 ✨ Live status and AI-review forms (November 2026 update)

**Implementation:** `IncidentDashboard._manage_section()` and `IncidentDashboard._ai_review_section()` in `campus_safety/dashboard/dashboard_oop.py`.

These are **interface-level improvements** to existing `DataManager` operations. No repository schema, priority rules or saved Gemini assessment fields are changed.

| Form / field | Interaction before saving | After a successful save | Invalid or unsuccessful save |
| --- | --- | --- | --- |
| **New status** | Dropdown selection shows an immediate preview, e.g. `In Progress → Resolved (not saved yet)`. | Reflects the newly stored status. | Selected status is retained for correction. |
| **Reason for change** | Required for a genuine status change. | Text box clears on the next rerun. | Entered text remains available. |
| **Review decision** | Dropdown shows the selected `Accepted`, `Flagged as Incorrect`, or `Further Review Requested` decision immediately. | Resets to the first supported option (`Accepted`). | Selected decision remains available. |
| **Reviewer name** | Required (at least two non-whitespace characters). | Text box clears on the next rerun. | Entered text remains available. |
| **Review reason** | Required for a saved human AI review. | Text box clears on the next rerun. | Entered text remains available. |

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
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env          # add your Gemini API key
python -m unittest discover -s tests -t . -v
python main.py                                                   # CLI
python -m streamlit run campus_safety/dashboard/dashboard_oop.py # dashboard (second terminal)
```

The dashboard opens at **http://localhost:8501**. Always start it from the project root with `python -m streamlit` so the `campus_safety` package can be imported. To use both interfaces together, run the CLI and Streamlit dashboard in **separate PowerShell terminals**. Keep `HAZARD_STORAGE_BACKEND` and the database path consistent across both.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal and try again. SQLite is part of Python's standard library; do **not** install a separate `sqlite3` package.

### 8.2 🐳 Docker

Requires Docker Desktop to be running. No local Python installation is needed.

```powershell
# Build the image (from the repository root)
docker build -t campus-safety .

# Run the automated tests inside the container (no API key needed)
docker run --rm campus-safety python -m unittest discover -s tests -t . -v

# Run the interactive CLI with your .env and a persistent data volume
docker run -it --rm --env-file .env -v campus-safety-data:/data campus-safety

# Run the dashboard on the same data volume, then open http://localhost:8501
docker run --rm -p 8501:8501 --env-file .env -v campus-safety-data:/data campus-safety python -m streamlit run campus_safety/dashboard/dashboard_oop.py --server.address=0.0.0.0
```

Inside the container, data is stored in the `/data` volume (`HAZARD_DATA_DIR=/data`), so incidents persist between runs and are shared by the CLI and dashboard containers. Attached images are saved inside the CLI container (`/app/uploads`), so the dashboard container cannot preview them. `.env` is excluded from the image by `.dockerignore` and passed at run time with `--env-file`. The graphical image picker is unavailable in the container; the CLI falls back to asking for a file path.

### 8.3 🔐 Configuration (`.env`)

| Variable | Purpose | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Gemini credentials (required for real submissions) | — |
| `GEMINI_MODELS` | Comma-separated model fallback order | Built-in list in `gemini_assessor.py` |
| `HAZARD_STORAGE_BACKEND` | `json` or `sqlite` | `json` |
| `SQLITE_DB_PATH` / `INCIDENTS_DB` | Database file for SQLite / JSON | Data folder |
| `HAZARD_DATA_DIR` | Shared data folder for either backend | Project folder (`/data` in Docker) |

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

**Verified against the supplied ZIP on 14 November 2026:** **233/233 `unittest` tests passed** locally (no failures or errors). The **separate AI Manager runner passed 51/51**; its 51 tests are already included within the full 233, so these totals must **not** be added together. Offline tests use stubbed AI responses and temporary repositories and do not require a live Gemini API key.

```powershell
python -m compileall -q main.py campus_safety tests
python -m unittest discover -s tests -t . -v    # full suite: 233 tests
python -m tests.run_all_tests                    # grouped full-suite summary
python -m tests.run_ai_tests                     # overlapping AI subset: 51 tests
```

### 9.1 Test coverage in this project version

| Area / test module | Tests | Main coverage |
| --- | ---: | --- |
| AI Manager (`tests/ai_manager_test/`, six modules) | 51 | Schema validation, provider abstraction, Gemini retries/fallback, prompts and image validation |
| `test_logic_manager_rules.py` | 29 | Priority rules, severity/impact scoring, history, duplicate matching, OOP substitution |
| `test_data_repositories.py` | 50 | JSON/SQLite CRUD, status audit, AI review, migrations, persistence, backups and corruption |
| `test_hazard_report_domain.py` | 17 | Domain validation, incident state changes, AI review rules |
| `test_io_manager_cli.py` | 14 | CLI, validation loops, search criteria and facilities output |
| `test_application_workflow.py` | 22 | End-to-end submission, cancellation, failure handling and menu routes |
| `test_facilities_data_manager_search.py` | 10 | Incident filters and searches |
| `test_facilities_logic_manager_summary.py` | 2 | Facilities summaries |
| `test_facilities_workflow_integration.py` | 1 | Integrated facilities search/summary |
| `test_facility_summary_domain.py` | 2 | Facility summary result validation |
| `test_incident_exporter.py` | 4 | Exporter behaviour |
| `test_background_export_service.py` | 9 | Threaded export service and task handling |
| `test_dashboard_extensions.py` | 22 | Dashboard presentation/helper logic |
| **Total `unittest` tests** | **233** | **233 passed in this verification** |

`tests/test_io_manager.py` contains **three separate pytest-style checks**, not collected by `unittest` discovery and therefore **excluded** from the 233-test total. To execute them separately, install `pytest` and run `python -m pytest tests/test_io_manager.py -v`; `pytest` is not listed in the runtime `requirements.txt`.

**Browser verification is separate:** the automated dashboard tests primarily cover helper logic and export services. Manually verify Streamlit rendering, live selectbox previews, button contrast and the field-clearing behaviour described in Section 7.5. The local test results above do **not** establish Docker startup or successful GitHub-hosted CI runs.

**CI configuration:** `.github/workflows/python-tests.yml` runs on pushes to `main` and `feature/**`, and pull requests to `main`. The `basic-checks` job checks essential files, compiles Python, installs dependencies, runs AI tests, imports the dashboard and runs the complete `unittest` suite. The `docker` job builds the image, runs the same suite in the container and smoke-tests the CLI using menu option 6. **Review GitHub Actions results separately** before claiming CI/Docker success in the engineering report.

## 10. ⚠️ Exception handling

| Exception | Raised by | Typical cause | Handled by | Outcome |
| --- | --- | --- | --- | --- |
| `InvalidRecord` (`ValueError`) | `HazardReport`, `AIAssessment`, audit/review entries | Invalid input, AI schema mismatch, invalid status change | `GeminiAssessor` (retries), `CampusSafetyApplication.submit_report()` | Error message; report not saved |
| `AssessmentUnavailable` (`RuntimeError`) | `GeminiAssessor`, `AIManager`, `ImageEvidenceProcessor` | Missing key, network failure, timeout, malformed JSON after retries, invalid image | `CampusSafetyApplication.submit_report()` | "AI assessment unavailable… NOT saved"; menu continues |
| `DataStoreError` (`RuntimeError`) | JSON and SQLite repositories, `IncidentExporter` | Corrupt or unreadable file, SQLite error, duplicate ID, failed backup | `main.py` at startup; `CampusSafetyApplication.run()` / `submit_report()` | Clear message, exit code 1 at startup; damaged files are never overwritten |
| `ValueError` | `create_repository()` | Unsupported `HAZARD_STORAGE_BACKEND` value | `main.py` | Startup error, exit code 1 |
| `OSError` | `MediaHandler.attach_image()` | Image cannot be copied | `MediaHandler` | Continues without the image |
| `KeyboardInterrupt` / `EOFError` | User presses Ctrl+C or input closes | — | `CampusSafetyApplication.run()` | Goodbye message, clean exit |

A missing database file is not an error: it is treated as an empty database and created on the first save.

### Engineering Report traceability notes

Use the mappings below as the code-to-report source of truth. Keep the 6-page report's UML, data-flow diagram, SQLite description and exception matrix aligned with these methods.

| Report element | Exact code mapping |
| --- | --- |
| UML: controller and managers | [`CampusSafetyApplication.create_default()` and `__init__()`](./campus_safety/application.py) construct and hold `IOManager`, `AIManager`, `LogicManager` and `DataManager`. |
| UML: provider and repository abstractions | [`AIManager.__init__()`](./campus_safety/ai_manager/ai_manager.py) depends on `AssessmentProvider`, implemented by [`GeminiAssessor`](./campus_safety/ai_manager/gemini_assessor.py). [`DataManager.__init__()`](./campus_safety/data_manager/data_manager.py) depends on `IncidentRepository`, implemented by [`JsonIncidentRepository`](./campus_safety/data_manager/json_incident_repository.py) and [`SQLiteIncidentRepository`](./campus_safety/data_manager/sqlite_incident_repository.py). `IOManager.__init__()` creates its `MediaHandler` from [`media.py`](./campus_safety/io_manager/media.py). |
| UML: logic and export collaborators | [`LogicManager.__init__()`](./campus_safety/logic_manager/logic_manager.py) holds its evaluator, sorter, optional matcher and summary builder; `DataManager.__init__()` creates an `IncidentExporter`. |
| New-report data flow | [`CampusSafetyApplication.submit_report()`](./campus_safety/application.py) calls `IOManager.get_user_input()` → `CampusSafetyApplication.assess()` → `AIManager.assess()` → `AssessmentProvider.assess()`; then `CampusSafetyApplication.evaluate()` calls `LogicManager.calculate_historical_frequency()`, `check_duplicate()` and `evaluate()`, applies the `Decision` to `HazardReport`, and `DataManager.save()` delegates to `IncidentRepository.save()`. |
| SQLite schema | [`SQLiteIncidentRepository.__init__()`](./campus_safety/data_manager/sqlite_incident_repository.py) creates `incidents(incident_id TEXT PRIMARY KEY, payload TEXT NOT NULL)` and `metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)`. Each payload serializes one report, including status and AI-review histories; `metadata.last_issued` preserves the ID counter. |
| SQLite transactions | [`SQLiteIncidentRepository.save()`](./campus_safety/data_manager/sqlite_incident_repository.py) uses `BEGIN IMMEDIATE` to allocate the ID, insert the payload and update the counter atomically. `replace_all()` backs up first, starts an immediate transaction, validates the current rows and concurrent-change snapshot, then applies inserts/updates/deletes and updates the counter. `get_by_id()` queries the `incident_id` primary key directly. |

| Exception scenario | Origin and propagation | Handling / outcome |
| --- | --- | --- |
| Gemini API unavailable | [`GeminiAssessor.assess()`](./campus_safety/ai_manager/gemini_assessor.py) reports a missing key immediately; API errors are retried and then become `AssessmentUnavailable`. `AIManager.assess()` propagates provider failures. | [`CampusSafetyApplication.submit_report()`](./campus_safety/application.py) displays the assessment error and does not save the report. |
| Malformed Gemini JSON | `GeminiAssessor.parse_response()` raises `InvalidRecord` for malformed JSON. During `GeminiAssessor.assess()`, it is treated as a failed attempt; after retries the provider raises `AssessmentUnavailable`. | `CampusSafetyApplication.submit_report()` catches the assessment/validation exception and does not save the report. |
| Corrupt SQLite database or payload | [`SQLiteIncidentRepository.__init__()` and `load()`](./campus_safety/data_manager/sqlite_incident_repository.py) validate the database and payloads and raise `DataStoreError` on corruption. | [`main.main()`](./main.py) reports startup failure and exits with code 1; at runtime `CampusSafetyApplication.run()` displays a database-unavailable error. |
| Invalid user input | [`IOManager.get_user_input()`](./campus_safety/io_manager/io_manager.py) uses `InputValidator` to reprompt; [`HazardReport.from_input()`](./campus_safety/domain/hazard_report.py) raises `InvalidRecord` if domain validation fails. | `CampusSafetyApplication.submit_report()` displays an invalid-report error and returns without saving. |

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
│   ├── domain/                        # HazardReport, Decision, schema and audit/review entities
│   ├── io_manager/                    # IOManager, input validation and media handling
│   ├── ai_manager/                    # AI providers, assessment, Gemini prompt and image helpers
│   ├── logic_manager/                 # Scorers, priority rules, routing and facilities summary
│   ├── data_manager/                  # JSON/SQLite repositories, storage, export and factory
│   └── dashboard/
│       ├── dashboard_oop.py           # Streamlit dashboard, live previews and clear-on-save forms
│       ├── dashboard_extensions.py    # Dashboard presentation helpers
│       ├── background_export_service.py
│       ├── README_INTEGRATION.md      # Dashboard's earlier integration notes
│       └── optional_theme/
├── tests/
│   ├── __init__.py
│   ├── ai_manager_test/               # AI Manager unit tests and stub providers
│   ├── test_application_workflow.py
│   ├── test_background_export_service.py
│   ├── test_dashboard_extensions.py
│   ├── test_data_repositories.py
│   ├── test_hazard_report_domain.py
│   ├── test_io_manager.py            # Three pytest checks (not in the 233 unittest tests)
│   ├── test_io_manager_cli.py
│   ├── test_logic_manager_rules.py
│   ├── test_facilities_data_manager_search.py
│   ├── test_facilities_logic_manager_summary.py
│   ├── test_facilities_workflow_integration.py
│   ├── test_facility_summary_domain.py
│   ├── test_incident_exporter.py
│   ├── run_all_tests.py              # Grouped full-suite results
│   └── run_ai_tests.py               # Focused AI subset
├── .streamlit/config.toml             # Included native Streamlit light theme
├── main.py                            # CLI entry point
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .env.example                       # Configuration template; contains no real credentials
├── requirements.txt
└── README.md
```


## 12. 🧱 OOP implementation guide

| Concept | Where it is implemented | Evidence |
| --- | --- | --- |
| 🧱 **Classes and objects** | Managers, `CampusSafetyApplication`, `HazardReport`, `AIAssessment`, `Decision`, repositories, rules, scorers | Objects collaborate to assess, prioritise and store incidents. |
| 🔐 **Encapsulation** | `HazardReport`, managers, repositories, `PriorityRule` | Underscore-prefixed attributes (`_fields`, `_repository`, `_provider`); `HazardReport.get()` / `as_dict()` return deep copies; state changes go through validated methods. `PriorityRule` exposes read-only properties. |
| 🧩 **Abstract classes** | `AssessmentProvider`, `IncidentRepository`, `PriorityRule`, `Scorer`, `TextMatcher` | Each extends `ABC` with `@abstractmethod` operations. `IncidentRepository.replace_all()` also provides shared validation; `TableScorer` is an intermediate abstract class. |
| 📜 **Interfaces / contracts** | The same ABCs | Clients depend on the contract, not on a specific implementation. |
| 🌳 **Inheritance and overriding** | `GeminiAssessor`; `JsonIncidentRepository`, `SQLiteIncidentRepository`; `CriticalRule`, `HighRule`, `StandardRule`; `SeverityScorer`, `ImpactScorer`, `FrequencyScorer`; `ExactMatcher`, `FuzzyMatcher`; `InvalidRecord`, `DataStoreError`, `AssessmentUnavailable` | Subclasses override `assess`, `matches`, `score` and `replace_all`. Repositories call `super().replace_all()`; rules call `super().__init__()`. |
| 🔄 **Polymorphism** | `AIManager` → any `AssessmentProvider`; `DataManager` → any `IncidentRepository`; `PriorityEvaluator` loops over `PriorityRule`s; `ScoreCalculator` loops over `Scorer`s; `IncidentHistory` → any `TextMatcher` | The same call works on different concrete classes with no type checks. Tests swap Gemini for `ConstantProvider`/`StubProvider`, SQLite for JSON, and `FuzzyMatcher` for `ExactMatcher`. |
| 🔗 **Association** | `HazardReport` ↔ `AIAssessment` / `Decision`; `IOManager` ↔ `HazardReport` | Objects use each other in method calls (`attach_assessment()`, `apply_decision()`, `submission_success()`) without keeping or owning them. |
| 🧺 **Aggregation** | `CampusSafetyApplication` ◇ four managers; `IncidentDashboard` ◇ `DataManager`; `DataManager` ◇ `IncidentRepository`; `AIManager` ◇ `AssessmentProvider`; `LogicManager` ◇ optional evaluator/sorter/matcher | Parts are created elsewhere and injected; they can exist and be tested independently. |
| 🏗️ **Composition** | `IOManager` ◆ `MediaHandler`; `DataManager` ◆ `IncidentExporter`; `BackgroundExportService` ◆ `ThreadPoolExecutor`; `PriorityEvaluator` ◆ `ScoreCalculator` ◆ scorers | The owner creates the part in its constructor and controls its lifetime; the part is not shared. |

**Value objects:** `Decision`, `AIAssessment`, `IncidentAuditEntry`, `AIReviewEntry` and `FacilitySummaryReport` are frozen dataclasses, validated on construction.

### 12.1 🧩 SOLID evidence

- **SRP:** each manager has one responsibility, and `CampusSafetyApplication` only coordinates. Inside the managers, responsibilities are split further: `GeminiPromptBuilder` (prompt), `ImageEvidenceProcessor` (images), `InputValidator` (input rules), `MediaHandler` (file copying), `Router` (routing), `FacilitySummaryBuilder` (summary metrics) and `IncidentExporter` (file output).
- **OCP:** new behaviour is added by writing a new subclass, without editing existing classes: a new `PriorityRule`, `Scorer`, `TextMatcher`, `AssessmentProvider` or `IncidentRepository`. `test_custom_rule_can_be_added_without_editing_evaluator` demonstrates this. (A new storage backend name must still be registered in `repository_factory.py`.)
- **LSP:** `JsonIncidentRepository` and `SQLiteIncidentRepository` pass the **same** test contract in `test_data_repositories.py`; `ConstantProvider`/`StubProvider` replace `GeminiAssessor`; `ExactMatcher` replaces `FuzzyMatcher`. Client code is unchanged in every case.
- **DIP:** `CampusSafetyApplication`, `AIManager`, `DataManager` and `LogicManager` receive their collaborators through constructors; only `create_default()` chooses the concrete classes.


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