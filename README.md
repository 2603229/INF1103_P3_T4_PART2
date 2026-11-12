# 🛡️ Campus Safety Hazard Reporting System — INF1103 Part 2

## 1. 📌 Project overview

This project refactors the Phase 1 Campus Safety Hazard Reporting System into a modular object-oriented Python application. A command-line interface (CLI) accepts hazard reports; a Streamlit web dashboard supports incident review and management.

Every **new report** follows the four-manager workflow:

1. ⌨️ **IO Manager** — collects and validates user input.
2. 🤖 **AI Manager** — calls the live Gemini API, parses structured JSON and validates its fields.
3. 🧠 **Logic Manager** — evaluates severity, operational impact and historical frequency to determine priority and routing.
4. 💾 **Data Manager** — saves, retrieves and manages incidents using interchangeable JSON or SQLite repositories.

New incidents are **not saved** when the AI response is unavailable or invalid. The live Gemini API is needed for real submissions but **not** for the automated tests.

## 2. ✨ Main application functions

- 📝 Submit hazard reports with validation and optional image evidence.
- 🤖 Review AI-assisted hazard classification, calculated priority and routing.
- 📋 View recorded incidents and the top five most frequently reported hazards.
- 🖥️ Use the Streamlit dashboard to review records, update statuses, delete test incidents and export data.
- 📜 Maintain a persistent **Incident Status Audit Trail** for incident creation and subsequent status changes.
- 👤 Let staff **accept, flag or request further review** of saved Gemini assessments, with persistent human feedback history.
- 🗄️ Store data using JSON or **SQLite**, with full CRUD support, backup/restore and migration from JSON.
- 📥 Prepare downloadable incident CSV data in a background worker thread.

## 3. 🚀 Advanced features and Part 2 extensions
### 3.1 🗄️ SQLite database integration — advanced feature

**Implementation:** `campus_safety/data_manager/sqlite_incident_repository.py`  

**Related files:** `data_manager.py`, `incident_repository.py`, `json_incident_repository.py`, and `repository_factory.py` under `campus_safety/data_manager/`.

`DataManager` interacts with the abstract `IncidentRepository` contract, not directly with SQLite statements. Both `JsonIncidentRepository` and `SQLiteIncidentRepository` implement that contract, demonstrating interface-based design, polymorphism and the Liskov Substitution Principle (LSP).

| SQLite capability | Implementation |
| --- | --- |
| ➕ **Create** | Insert a validated incident and allocate a persistent incident ID. |
| 🔍 **Read** | Load and validate stored records for display, searching and summaries. |
| ✏️ **Update** | Persist modified records, including status and Audit Trail entries. |
| 🗑️ **Delete** | Remove a selected record through the Data Manager. |
| 💾 **Persistence** | Preserve incident data and the ID counter across application restarts. |
| 🔒 **Transactions** | Apply record changes atomically using parameterised SQL. |
| 🗃️ **Backup / restore** | Create consistent backups and validate data before restoration. |
| 🔄 **Migration** | Import an existing JSON database into an empty SQLite database without deleting the JSON source. |
| ⚠️ **Error handling** | Reject invalid or corrupted records and report controlled storage errors. |

The default SQLite filename is `hazardreports.sqlite3` when SQLite is selected. Its `incidents` table stores incident IDs and serialized record payloads; its `metadata` table preserves ID allocation information. **Audit history is stored with the corresponding incident**, not in a separate audit table.

### 3.2 📜 Incident Status Audit Trail — additional advanced capability and meaningful new feature

The **Incident Status Audit Trail** is the project's required **new meaningful Part 2 feature**. It is also an additional advanced workflow capability because it adds validated change-history tracking integrated with the domain model, persistent storage and Streamlit interface. **SQLite database integration remains the primary feature designated under the rubric's advanced-feature category.**

Every newly created incident starts with a creation-history entry. When its status changes, the application records:

- Incident ID and time of change (displayed in Singapore time in Streamlit).
- Previous status and new status.
- The reason entered by the person making the change.

The system validates status transitions and audit-history consistency. An unchanged status does not create a misleading new entry. History appears **newest first** in the Streamlit **Incident Status Audit Trail** panel and persists across restarts with the incident record.

**Where the Audit Trail is implemented:**

| File | Responsibility |
| --- | --- |
| `campus_safety/domain/incident_audit_entry.py` | Defines and validates an immutable audit-entry value. |
| `campus_safety/domain/hazard_report.py` | Records creation/status transitions and provides `change_status()` and `status_history()`. |
| `campus_safety/data_manager/data_manager.py` | Updates the selected incident and persists its new history through the repository. |
| `campus_safety/data_manager/sqlite_incident_repository.py` | Saves incident data and serialized history together. |
| `dashboard_oop.py` | Displays the status-change form and incident history. |
| `tests/test_status_audit_trail.py` | Contains 12 focused automated Audit Trail tests. |

**Example workflow:** In the dashboard, select a test incident, change its status from **Pending Review** to **In Progress**, enter a reason, then select **Save status and record history**. Expand **Incident Status Audit Trail** to verify the previous status, new status, timestamp and reason. Restart the application to verify persistence.

**Scope:** This is an application-level history feature, **not a tamper-proof security log**. Deleting an incident also removes its active history; earlier backups may still contain it.

### 3.3 🧠 AI Assessment Review & Feedback —  human-oversight enhancement

**Purpose:** a human can evaluate a saved Gemini assessment without silently changing its severity, priority or routing. This is an additional feature; the original Incident Status Audit Trail remains the required meaningful new feature, and SQLite CRUD remains the primary advanced-feature category.

**Implementation:** `campus_safety/domain/ai_review_entry.py` (immutable validated review value); `campus_safety/domain/hazard_report.py` (`add_ai_review`, `ai_review_history`); `campus_safety/data_manager/data_manager.py` (`record_ai_review`, `ai_review_history`); `dashboard_oop.py` (review form and history); `tests/test_ai_review_workflow.py` (10 offline tests).

**AI review architecture (represented in the updated UML and Level 1 DFD):**

| File / class | Responsibility |
| --- | --- |
| `dashboard_oop.py` — `IncidentDashboard` | `_ai_review_section()` shows the saved Gemini result, collects the review decision, self-entered reviewer and reason, and displays review history. |
| `campus_safety/data_manager/data_manager.py` — `DataManager` | `record_ai_review()` loads the record, requests domain validation, then persists it using `IncidentRepository.replace_all()`. `ai_review_history()` retrieves saved reviews. |
| `campus_safety/domain/hazard_report.py` — `HazardReport` | `add_ai_review()` ensures that a saved Gemini assessment exists and appends a validated review; `ai_review_history()` reconstructs entries from the stored dictionaries. |
| `campus_safety/domain/ai_review_entry.py` — `AIReviewEntry` | A frozen dataclass containing `incident_id`, `reviewer`, `decision`, `reason`, `reviewed_at` with validation, `from_mapping()` and `as_dict()`. |
| `campus_safety/data_manager/{json_incident_repository,sqlite_incident_repository}.py` | Stores the same incident payload containing the `ai_review_history` list. There is **no separate AI-review SQLite table**. |
| `tests/test_ai_review_workflow.py` | Ten offline checks covering review decisions, invalid data, history persistence and separation from status / AI fields. |

**Human feedback flow:** A reviewer opens a saved incident in Streamlit → chooses **Accepted / Flagged as Incorrect / Further Review Requested** → enters their name and reason → `IncidentDashboard` calls `DataManager.record_ai_review()` → `HazardReport.add_ai_review()` creates an `AIReviewEntry` → the selected JSON or SQLite repository saves the updated incident → the dashboard calls `DataManager.ai_review_history()` to show the latest review first.

`AIManager` is **not** responsible for this human feedback. It generates and validates Gemini's original assessment. Review feedback does not trigger Gemini, edit the original assessment, recalculate priority, change incident status, or append an entry to the separate Incident Status Audit Trail.

**Use it:**

1. Ensure `.env` selects `HAZARD_STORAGE_BACKEND=sqlite` and contains a valid local Gemini key. Run `python main.py`.
2. Use CLI option **1** to submit a **fictional** incident, complete the live Gemini assessment and confirm saving. If Gemini reports `503 UNAVAILABLE`, the incident is not saved; rerun when the service is available or use the offline tests.
3. Open `http://localhost:8501`, select the incident, and expand **AI Assessment Review & Feedback** below the incident details.
4. Check the saved **Gemini category, severity, operational impact, risk summary and calculated priority**.
5. Choose **Accepted**, **Flagged as Incorrect** or **Further Review Requested**. Enter a reviewer name and a reason; click **Save AI review**.
6. Expand the panel again to read **AI Review History** (newest first), including the decision, reason, reviewer name and Singapore-time timestamp.
7. Restart `python main.py` and verify the history is still present. Try multiple reviews; prior entries remain visible. The original AI fields and Incident Status Audit Trail must not change merely because a reviewer disagrees.
8. Run `python run_tests.py --group review` for the 10 offline tests, or `python run_tests.py` for the full suite.

**Important:** reviewer names are self-entered and **not authenticated**. The feature records feedback, not a verified identity or a security-grade audit log. Flagging or requesting review does not automatically recalculate severity, priority or escalation, and must not be treated as a substitute for following campus safety procedures.

### 3.4 🖥️ Streamlit GUI and threaded CSV export — additional advanced features

- **Streamlit GUI:** `dashboard_oop.py` displays stored incidents, enables status updates and deletion, shows the Audit Trail, and periodically refreshes its incident view.
- **Threading:** `campus_safety/services/background_export_service.py` uses `ThreadPoolExecutor` to prepare CSV output from an in-memory incident snapshot without blocking the dashboard's main UI interaction. In Streamlit, use **Export incidents → Prepare CSV in background**, then download the result when ready.

### 3.5 🔍 How to run and verify SQLite features (manual demonstration)

Complete the **installation steps in Section 4** first. SQLite is built into Python; it does not need its own package or server. The following actions should be performed with **fictional records in a disposable test database**, not on production data.

1. **Select SQLite.** Stop any running CLI/dashboard, open `Project Code/.env` and set `HAZARD_STORAGE_BACKEND=sqlite`. For a separately isolated test database, optionally add `SQLITE_DB_PATH` with the full path to a new `.sqlite3` file. Otherwise the database is created as `Project Code/hazardreports.sqlite3`. Keep this private `.env` file out of the ZIP.
2. **Launch both interfaces.** In the `Project Code` terminal run `python main.py`, then open `http://localhost:8501`. The repository automatically creates the SQLite `incidents` and `metadata` tables when starting with an absent database.
3. **CREATE.** Choose CLI option **1**, submit a fictional hazard and confirm it. A successful **live Gemini** assessment is required; if Gemini is unavailable, the report is **not** saved.
4. **READ.** Choose CLI option **2** to list incidents. Open the Streamlit dashboard and select the saved incident to inspect its details.
5. **UPDATE.** In Streamlit, select a test incident under **Manage incident**, choose a different status, supply a reason and select **Save status and record history**. The status and its Audit Trail entry are committed together.
6. **PERSISTENCE.** Exit using CLI option **4**, then run `python main.py` again. The report, status, Audit Trail and ID counter should remain. Use the same backend and database path for CLI and dashboard.
7. **BACKUP/RESTORE.** Status updates and deletions create a pre-change SQLite backup. The Streamlit **Restore database backup** section lists snapshots; on a disposable test database only, select one and explicitly confirm a restore. Check that the previous records return.
8. **DELETE.** In Streamlit choose a disposable incident, tick **Confirm deletion of this incident**, and select **Delete selected incident**. Confirm it no longer appears in the CLI/dashboard. Deleting a record removes its active Audit Trail as well.

**Read-only database check:** From `Project Code`, if you used the default file path:

```powershell
python -c "import sqlite3; db=sqlite3.connect('file:hazardreports.sqlite3?mode=ro',uri=True); print('Incidents:',db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]); print('IDs:',db.execute('SELECT incident_id FROM incidents').fetchall()); db.close()"
```

The SQL database has an `incidents(incident_id, payload)` table and a `metadata(key, value)` table. The full incident data—including `status_history` and `ai_review_history`—is serialized inside each incident's `payload`, **not** stored in a separate audit-events table. SQLite supports transactional insert, read, update and delete operations using parameterised SQL. `DataManager` uses the `IncidentRepository` interface, so UI and business logic do not need backend-specific SQL.

**JSON-to-SQLite migration:** Only if you have existing JSON records, run `python migrate_json_to_sqlite.py --dry-run` first and `python migrate_json_to_sqlite.py --apply` after reviewing its output. The target SQLite database must be empty; migration does not delete the JSON original.

### 3.6 🧪 How to run and verify Incident Status Audit Trail (manual demonstration)

The Audit Trail is the **meaningful new Part 2 feature** and an **additional advanced capability**; SQLite CRUD is the primary rubric-listed advanced feature.

1. Ensure at least one **fictional** incident has been successfully saved. Start `python main.py` and open the Streamlit dashboard at `http://localhost:8501`.
2. Select the incident under **Select an incident**. Scroll to **Manage incident** and check its current status (for a new incident, **Pending Review**).
3. Choose **In Progress** and enter a reason such as `Maintenance team assigned to investigate the hazard`. Select **Save status and record history**.
4. Expand **Incident Status Audit Trail**. Check two entries: **Created → Pending Review** (reason `Incident created`) and **Pending Review → In Progress** (the reason you entered). The most recent change is shown first with Singapore-time timestamps.
5. Make another genuine change, such as **In Progress → Resolved**, and provide a new reason. Check that a third entry appears and previous entries remain unchanged.
6. Exit and restart the CLI/dashboard. Select the same incident and confirm the Audit Trail is still there in SQLite. Optionally run the dedicated automated tests shown in Section 5.
7. For an unchanged status, no extra history entry should be created. Invalid statuses and inconsistent persisted history must be rejected by the domain/repository validation.

**Implementation path:** `dashboard_oop.py` → `DataManager.update_status()` → `HazardReport.change_status()` → `IncidentAuditEntry` → active JSON/SQLite repository; displaying history uses `DataManager.status_history()` and `IncidentDashboard._history_section()`. `HazardReport` stores serialized history dictionaries and reconstructs validated audit values when read; it does not retain an owned list of live `IncidentAuditEntry` objects.

**Controlled database startup failure:** If a selected SQLite file is corrupt or inaccessible, `run_oop.py` now prints a clear startup error and exits with a nonzero status instead of displaying an uncaught traceback. The Streamlit dashboard likewise displays an `Incident database unavailable` message. Neither path silently discards or overwrites the damaged file. The three regression tests in `tests/test_startup_error_handling.py` verify this behaviour and normal startup.

## 4. 🛠️ Installation and complete run guide (Windows PowerShell)

Follow these steps **in order** after extracting the submission ZIP. Commands assume PowerShell and Python 3.12.

### Step 1 — 📁 Open the project folder

In PowerShell, navigate to the extracted `Project Code` folder:

```powershell
cd "P3_T4_ProjectPart2Final\Project Code"
```

If you opened `Project Code` directly in VS Code, its integrated terminal may already be in the correct folder. Check that `requirements.txt`, `main.py` and `run_tests.py` are visible before continuing.

### Step 2 — 🐍 Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv

.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, then run the activation command again. This does not change the machine-wide execution policy.

### Step 3 — 📦 Install the project requirements

```powershell
python -m pip install --upgrade pip

python -m pip install -r requirements.txt
```

This installs dependencies including `google-genai`, `python-dotenv`, `streamlit`, and the other packages specified in `requirements.txt`. SQLite itself is part of Python's standard library; **do not install an additional `sqlite3` package**.

### Step 4 — 🔐 Configure `.env` locally

Copy the supplied **safe, blank template** to a local `.env` file, then edit it:

```powershell
Copy-Item .env.example .env

notepad .env
```

In `.env`, enter your **new valid** Gemini API key next to `GEMINI_API_KEY=`. Keep `HAZARD_STORAGE_BACKEND=sqlite` for the SQLite demonstration. The template deliberately ships without a key and is safe to submit. Do **not** share `.env`, take screenshots that reveal the key, or put it into this README, source code, Git, Docker or the ZIP. **Revoke/rotate the key found in the earlier submission ZIP before using the application again.**

If you already have a private local `.env`, you may edit it instead of overwriting it. The application defaults to JSON if `HAZARD_STORAGE_BACKEND` is unset. Use `json` instead of `sqlite` to select JSON storage. **Changing the backend does not automatically transfer or synchronize records.**

Storage-path variables are `SQLITE_DB_PATH` (SQLite), `INCIDENTS_DB` (JSON) and `HAZARD_DATA_DIR` (shared data directory). Make sure the CLI and Streamlit use the **same backend and path**.

### Step 5 — ✅ Run the offline automated tests

```powershell
python run_tests.py  
```

The latest reviewed version contains **159 tests**. Successful output ends with:

```text
Total Tests : 159
Passed      : 159
Failed      : 0
Errors      : 0
Missing test groups: 0
FINAL RESULT: ALL TESTS PASSED
```

Messages such as `simulated timeout`, `network unavailable` and `Malformed AI JSON` are expected from negative tests using mocks, not evidence of a live Gemini outage.

### Step 6 — ▶️ Start the CLI and Streamlit dashboard

```powershell
python main.py
```

The CLI menu appears in PowerShell, and Streamlit is launched at **http://localhost:8501**. Open that address in a browser if it does not open automatically.

CLI menu options:

1. **Submit New Hazard Report** — enter reporter details, affected location, people affected and hazard description; a valid live Gemini response is required before saving.
2. **View All Logged Incidents** — display saved reports.
3. **View Top 5 Most Frequent Hazards** — display the most frequently reported hazard categories.
4. **Exit** — stop the CLI and the dashboard process started by it.

Alternatively, to launch only one interface:

```powershell
# CLI only

python main.py --no-dashboard

# Dashboard only (run in its own PowerShell terminal)

python -m streamlit run dashboard_oop.py
```

### Step 7 — 🔎 Verify a complete incident workflow

Use **fictional test data**, not personal or real incident records:

1. Select CLI option **1** and enter a synthetic campus hazard (for example, a water leak in a fictional test room). Wait for the live Gemini assessment and confirm submission.
2. Select CLI option **2** to verify that the incident was saved. Use option **3** to check the frequency summary.
3. Open **http://localhost:8501** and confirm that the incident appears in Streamlit.
4. Select the incident, change its status, enter a reason and select **Save status and record history**.
5. Expand **Incident Status Audit Trail** and verify the old/new status, reason and timestamp.
6. Restart the application and verify that the incident and Audit Trail are still saved in SQLite.
7. Optionally test **Prepare CSV in background**, download the file and inspect its synthetic records.
8. Only on a **disposable test database**, verify incident deletion and backup/restore behaviour.

If Gemini returns `503 UNAVAILABLE` or an invalid response, the application should display a controlled error and **not save an unassessed report**. An API availability error does not by itself mean the local code is broken.

### Step 8 — ⏹️ Exit the application

In the CLI, select **4** to exit. If Streamlit was launched separately, stop that terminal with **Ctrl+C**. To leave the virtual environment after testing, run:

```powershell
deactivate
```

## 5. ✅ Automated test scripts and evidence

Automated tests run without live AI credentials and cover all four managers, OOP concepts and relationships, business rules, AI failure handling, JSON/SQLite CRUD, Audit Trail, migration, backup/restore and threaded exports.

```powershell
# Run from Project Code

python run_tests.py

# Formatted individual results for all 159 tests

python run_tests.py --details

# Focused, easy-to-read AI Review test results (10 tests)

python run_tests.py --group review

# Full Python tracebacks when a test fails (optional)

python run_tests.py --tracebacks

# Standard Python unittest output

python -m unittest discover -s tests -v

# Run just the 12 Audit Trail tests

python -m unittest discover -s tests -p "test_status_audit_trail.py" -v

# Run just the eight Week 10 relationship/type-hint tests

python -m unittest discover -s tests -p "test_lab8_relationships_and_types.py" -v

# Run the three SQLite startup regression tests

# Formatted report for the 3 startup regression tests (recommended)

python run_tests.py --group startup

# AI Assessment Review & Feedback (10 tests)

python run_tests.py --group review

# Standard Python unittest output for the same 3 tests

python -m unittest discover -s tests -p "test_startup_error_handling.py" -v
```

To use the **separate official test launcher**, navigate to the parent `P3_T4_ProjectPart2Final` folder and run:

```powershell
cd ..

python "Test Script\test_script.py"
```

For readable terminal output, prefer `python run_tests.py --group startup` or `python run_tests.py --group review` rather than the default `unittest -v` command. Failed tests now display a concise cause instead of a lengthy traceback; add `--tracebacks` for complete diagnostics. The AI Review test closes its SQLite connection explicitly before deleting its temporary database, preventing Windows `WinError 32` file-lock cleanup errors. The formatted runner uses the same test files and reports any failures or missing test groups.

Both test entry points should run the same 159-test suite. Re-run tests on the exact final submitted revision.

## 6. 🔄 JSON-to-SQLite migration

Migration is needed **only** if you have an existing JSON database to import into an **empty** SQLite database. Back up existing data before applying it.

```powershell
# From Project Code

python migrate_json_to_sqlite.py --dry-run

python migrate_json_to_sqlite.py --apply
```

Inspect the source/target paths and counts in the dry run first. The migration preserves incident IDs and saved history and leaves the JSON source untouched. If `hazardreportdb.json` is missing in a fresh installation, migration is unnecessary; you can use SQLite directly.

## 7. 🗂️ Project structure and design references

```text
Project Code/
├── campus_safety/
│   ├── application.py                  # Application controller and default manager construction
│   ├── workflow.py                     # AI → Logic → Data workflow
│   ├── ai_manager/                     # Assessment contract and Gemini implementation
│   ├── logic_manager/                  # Risk and routing policies
│   ├── data_manager/                   # DataManager, repository contract, JSON and SQLite
│   ├── domain/                         # HazardReport, audit entries and validation
│   ├── io_manager/                     # CLI input and output
│   └── services/                       # Background CSV export
├── tests/                              # 159 offline automated tests
├── diagrams/                           # Full UML, AI review overview, main and storage DFDs
├── main.py                             # Main CLI entry point
├── run_oop.py                          # CLI bootstrap and environment loading
├── dashboard_oop.py                    # Streamlit incident dashboard
├── migrate_json_to_sqlite.py           # Data Migration
├── run_tests.py                        # Complete automated test runner
├── requirements.txt
├── .env.example                       # Safe blank local configuration template
├── verify_submission.py               # Checks files and ZIPs for unsafe artifacts
├── Dockerfile
└── README.md
```

- [Full updated UML class diagram](diagrams/INF1103_UML_Class_Diagram.png) — shows `AIReviewEntry`, `HazardReport`, `DataManager`, the repositories, and separate status / AI review histories.
- [Level 1 data-flow diagram](diagrams/INF1103_Data_Flow_Diagram.png) — includes Collect AI Feedback, the human reviewer, the Data Manager and the active data store.
- [Focused Human AI Review UML overview](diagrams/INF1103_AI_Review_UML_Overview.png) — easier-to-read feature diagram for the engineering report.
- [Supplementary storage and migration DFD](diagrams/INF1103_Storage_Operations_DFD.png) — showing status and AI review histories stored with incidents.

**Diagram formats:** This ZIP includes the four PNG diagrams listed above. It does **not** include editable `.dot` or `.svg` diagram source files. The full UML represents inheritance, association, aggregation, composition and polymorphism; verify diagrams against the final code before using them in your report. The **dashed dependency from `HazardReport` to `AIReviewEntry`** means review objects are created/validated as needed, not permanently stored as composed objects.

### 🧭 Architecture workflow summaries

The following compact diagrams supplement the linked UML and data-flow diagrams. They illustrate how the implemented features interact and may be reused in the engineering report. In the Level 1 DFD, **Collect AI Feedback** is a **logical process** for the Streamlit review workflow, **not an extra Python manager or class**; review validation is performed by `HazardReport` when `DataManager` records it.

**💾 Persistence architecture (JSON or SQLite)**

⌨️ **CLI** → 📥 **IO** → 🤖 **AI** → 🧠 **Logic** → 💾 **Data** → 🗄️ **JSON / SQLite**. The 🖥️ Streamlit dashboard reads and updates data through the Data Manager.

```text
New report: CLI → IO Manager → AI Manager → Logic Manager
                                                 |
                                                 v
                                             DataManager ← Streamlit dashboard
                                                 |
                                                 v
                                      IncidentRepository (Abstract Base Class)
                                            /          \
                                           v            v
                                JsonIncidentRepository  SQLiteIncidentRepository
                                           |            |
                                           v            v
                                   JSON data file     SQLite database
```

Both storage implementations use the same repository contract. A new incident is saved only after the AI assessment has been validated and the risk rules have been applied. The dashboard reads or modifies saved incidents through `DataManager`.

**📜 Incident Status Audit Trail workflow**

🖥️ **Dashboard** → 🔄 **Status update** → ✅ **Validation** → 💾 **Persistence** → 📜 **Audit history**.

```text
Streamlit: choose incident, new status and reason
                     |
                     v
           DataManager.update_status()
                     |
                     v
           HazardReport.change_status()
                     |
                     v
     Create and validate an IncidentAuditEntry
                     |
                     v
      Persist updated incident + audit history
            (JSON or SQLite repository)
                     |
                     v
        DataManager.status_history()
                     |
                     v
       Streamlit: Incident Status Audit Trail
```

Audit entries include the previous status, new status, timestamp and reason. They are stored with the incident record; they are **not** maintained in a separate SQLite audit table.

**🧑‍💻 Human review workflow (separate from incident status updates)**

👤 **Reviewer** → 🖥️ **Streamlit** → 📝 **Review entry** → 💾 **Repository** → 📋 **Review history**.

```text
Safety officer → Streamlit AI Assessment Review form
               → select Accepted / Flagged / Further Review
               → enter reviewer and feedback reason
               → DataManager.record_ai_review()
               → HazardReport.add_ai_review()
               → AIReviewEntry (validated, immutable value)
               → IncidentRepository (JSON or SQLite incident payload)
               → DataManager.ai_review_history()
               → Streamlit AI Review History
```

A flagged review **does not automatically change** Gemini severity, score, priority, the incident status or the Incident Status Audit Trail. A separate authorised decision is needed for operational action. The feature overview and the updated Level 1 DFD make this distinction explicit.

## 8. 🧱 OOP implementation guide — concept-by-concept and file-by-file

All nine required OOP concepts are implemented in the project code. The descriptions below refer to **actual classes, their relationships and methods**; `__init__.py` package markers and compatibility/constant modules do not create unnecessary classes.

| Required concept | Where it is implemented | Evidence in the code |
| --- | --- | --- |
| 🧱 **Classes and objects** | All four manager classes, `CampusSafetyApplication`, `HazardWorkflow`, `HazardReport`, `AIAssessment`, `Decision`, `IncidentDashboard`, `AIReviewEntry`, repositories | Runtime instances collaborate to process, evaluate, store and display incidents. |
| 🔐 **Encapsulation** | `HazardReport`; managers and repositories | `HazardReport._fields` is private by convention, `get()`/`as_dict()` return deep copies, and public domain methods validate state changes. Private repository/manager attributes avoid exposing storage internals. |
| 🧩 **Abstract classes** | `AssessmentProvider`, `PriorityPolicy`, `IncidentRepository` | Each extends Python `ABC` and declares required operations using `@abstractmethod`. |
| 🌳 **Inheritance and overriding** | `GeminiAssessor(AssessmentProvider)`, `CampusRiskPolicy(PriorityPolicy)`, `JsonIncidentRepository(IncidentRepository)`, `SQLiteIncidentRepository(IncidentRepository)` | Concrete classes implement the abstract behaviours; both repositories override `replace_all()` and use `super().replace_all(...)` for reusable parent validation. Custom exception subclasses also use inheritance. |
| 📜 **Interfaces/contracts** | IncidentRepository, AssessmentProvider, and PriorityPolicy use Python Abstract Base Classes (ABCs) to define contracts that concrete implementations must follow. This supports interchangeable implementations, abstraction, and polymorphism. | Clients depend on typed provider, policy and repository contracts, rather than specific implementations. |
| 🔗 **Association** | `IncidentDashboard` ↔ injected `DataManager`; `HazardWorkflow` ↔ `HazardReport` | Dashboard uses a DataManager created separately; the workflow processes an existing report without owning its whole lifecycle. |
| 🧺 **Aggregation** | `DataManager` ↔ `IncidentRepository`; `HazardWorkflow` ↔ manager objects | Managers/repositories are passed into other objects and can exist independently of the receiving objects. |
| 🏗️ **Composition** | `BackgroundExportService` → `ThreadPoolExecutor`; default `CampusSafetyApplication` object graph | The export service creates, owns and shuts down its worker pool. The application normally constructs and coordinates default managers and workflow, while still supporting injected alternatives. |
| 🔄 **Polymorphism** | `DataManager` using `IncidentRepository`; `AIManager` using `AssessmentProvider`; `LogicManager` using `PriorityPolicy` | Callers invoke the same interface operations regardless of concrete implementations; cross-backend tests exercise JSON and SQLite substitutions. |

### 8.1 🔌 Application entry points and workflow files

| File | Class / OOP role | Important methods or behaviour |
| --- | --- | --- |
| `main.py` | Compatibility entry point; no application class declared here | Calls `run_oop.main()`. |
| `run_oop.py` | Composition bootstrap / boundary error handling; no class declared here | Loads `.env`, parses `--no-dashboard`, constructs `CampusSafetyApplication`, catches startup `DataStoreError`/`ValueError`. |
| `campus_safety/application.py` | `CampusSafetyApplication`: class/object composition, manager dependency injection, encapsulation | `__init__`, `submit`, `view_all`, `top_five`, `run`. |
| `campus_safety/workflow.py` | `HazardWorkflow`: aggregation of independently usable managers; association with the incident domain object | `prepare`, `commit`, `submit` implement AI → logic → persistence. |
| `campus_safety/workflow_error.py` | `WorkflowError`: custom exception inheritance | Reports controlled workflow failures. |
| `dashboard_oop.py` | `IncidentDashboard`: UI class, injected `DataManager` association and encapsulation | `render`, `_ai_review_section`, `_manage_section`, `_history_section`, `_export_section`; `incident_dashboard()` handles repository startup failure. |
| `migrate_json_to_sqlite.py` | Migration orchestration using repository objects; no new domain class | `migrate`, `main`; retains JSON source when importing into empty SQLite. |

### 8.2 🤝 IO, AI and Logic files

| File | Class / OOP concept | Important methods or responsibility |
| --- | --- | --- |
| `campus_safety/io_manager/io_manager.py` | `IOManager`: encapsulated CLI presentation, object collaboration | `get_user_input`, `menu`, `confirm`, `view_all_reports`, `view_frequent_hazards`. |
| `campus_safety/ai_manager/assessment_provider.py` | `AssessmentProvider(ABC)`: abstract class and interface | Abstract `assess(report)`. |
| `campus_safety/ai_manager/gemini_assessor.py` | `GeminiAssessor(AssessmentProvider)`: inheritance, overriding and interface polymorphism | Implements `assess`; uses `build_prompt`, `parse_response`, `_image_part` for live API/validation. |
| `campus_safety/ai_manager/ai_manager.py` | `AIManager`: encapsulation, dependency injection of `AssessmentProvider`, polymorphic delegation | `assess(report)` calls the chosen provider. |
| `campus_safety/ai_manager/ai_assessment.py` | `AIAssessment`: structured value object, validation/encapsulation | `from_mapping`, `as_dict` validate/serialize five AI fields. |
| `campus_safety/ai_manager/assessment_unavailable.py` | `AssessmentUnavailable`: custom exception inheritance | Signals unavailable/invalid AI outcomes. |
| `campus_safety/logic_manager/priority_policy.py` | `PriorityPolicy(ABC)`: abstract policy interface | Abstract `evaluate(...)`. |
| `campus_safety/logic_manager/campus_risk_policy.py` | `CampusRiskPolicy(PriorityPolicy)`: inheritance and method overriding | `score_breakdown`, `route`, `evaluate`; severity, impact, frequency and routing rules. |
| `campus_safety/logic_manager/logic_manager.py` | `LogicManager`: encapsulation, dependency injection and polymorphism through `PriorityPolicy` | `evaluate`, `historical_frequency`, `duplicate_check`, `sort_by_severity`, `top_hazards`. |

### 8.3 💾 Domain, persistence and background-service files

| File | Class / OOP concept | Important methods or responsibility |
| --- | --- | --- |
| `campus_safety/domain/hazard_report.py` | `HazardReport`: entity class, encapsulation, defensive copies, validated domain operations | `from_input`, `from_storage`, `attach_assessment`, `apply_decision`, `assign_identity`, `change_status`, `_append_audit`, `status_history`, `add_ai_review`, `ai_review_history`, `as_dict`. |
| `campus_safety/domain/incident_audit_entry.py` | `IncidentAuditEntry`: immutable audit value object with validation | `__post_init__`, `from_mapping`, `as_dict`. |
| `campus_safety/domain/decision.py` | `Decision`: validated risk/route value object | `__post_init__` verifies decision fields. |
| `campus_safety/domain/invalid_record.py` | `InvalidRecord`: custom `ValueError` subclass | Allows invalid domain input to be handled explicitly. |
| `campus_safety/domain/schema.py` | Shared validation constants; no class | `SCHEMA_FIELDS`, `VALID_STATUSES`. |
| `campus_safety/data_manager/incident_repository.py` | `IncidentRepository(ABC)`: abstract class/interface, parent-method reuse, OCP/LSP | `load`, `save`, `replace_all`, `create_backup`, `list_backups`, `restore_backup`; shared replacement validation. |
| `campus_safety/data_manager/json_incident_repository.py` | `JsonIncidentRepository(IncidentRepository)`: inheritance, overriding, `super()` reuse | JSON CRUD, ID allocation and backups through the same repository API. |
| `campus_safety/data_manager/sqlite_incident_repository.py` | `SQLiteIncidentRepository(IncidentRepository)`: inheritance, overriding, `super()` reuse and polymorphic substitutability | SQLite tables, transactional CRUD, ID metadata, backups/restores and `import_records`. |
| `campus_safety/data_manager/data_manager.py` | `DataManager`: aggregation of injected `IncidentRepository`, SRP, polymorphism | `load`, `save`, `get_by_id`, `update_status`, `status_history`, `record_ai_review`, `ai_review_history`, `delete`, `clear`, `backups`, `restore`; delegates exports. |
| `campus_safety/data_manager/incident_exporter.py` | `IncidentExporter`: file output and formatting | `export_csv`, `export_txt`; writes report snapshots without owning repository access. |
| `campus_safety/data_manager/repository_factory.py` | Factory function; interface-based selection without declaring another class | `create_repository()` returns the chosen `IncidentRepository` implementation. |
| `campus_safety/data_manager/data_store_error.py` | `DataStoreError`: custom `RuntimeError` subclass | Distinguishes storage failures from domain and AI errors. |
| `campus_safety/services/background_export_service.py` | `BackgroundExportService`: encapsulation and composition of `ThreadPoolExecutor` | `submit_csv`, `_render_csv`, `close`; worker receives snapshots, not live SQLite/Streamlit objects. |
| `campus_safety/models.py`, `campus_safety/contracts.py` | Backward-compatible import modules; no classes defined here | Re-export domain models/interfaces to older imports. |
| All `__init__.py` files | Python package markers, not separate OOP classes | Make the module structure importable. |

The `tests/test_*.py` files use Python `unittest.TestCase` inheritance and mocks/fakes to validate concrete behaviour, including **12 Audit Trail tests**, **8 Week 10 relationship/type-hint tests**, **13 cross-backend substitution tests**, and **3 startup error-handling tests** plus **10 AI review tests**. `run_tests.py` collects all **159** tests. Tests document expected behaviour; they are not counted as application-domain classes.

### 8.4 🧩 SRP, OCP and LSP evidence

- **SRP:** `IOManager` handles input/output, `AIManager` coordinates the assessment provider, `LogicManager` performs risk logic, `DataManager` coordinates persistence, and `HazardReport` enforces incident state rules. `IncidentDashboard` handles UI rather than direct SQL.
- **OCP:** A new implementation of `IncidentRepository`, `AssessmentProvider` or `PriorityPolicy` can be introduced without rewriting manager business methods; a new backend identifier still requires registering the option in `repository_factory.py`.
- **LSP:** `JsonIncidentRepository` and `SQLiteIncidentRepository` satisfy the same persistence operations and shared validation expectations. Cross-backend acceptance tests run the same client use cases against both; no claim is made that the backends have identical physical storage formats.
- **Type hints and relationships (Week 10 Lab 8):** Typed manager, repository, policy, provider and dashboard references describe class contracts; the full UML shows the applicable multiplicities and relationship symbols. Python type annotations do not themselves enforce runtime types.

The code demonstrates classes/objects, encapsulation, abstract classes and interfaces, inheritance, association, aggregation, composition and polymorphism. SRP, OCP and LSP guide the separation of managers, providers, repositories and business policies. The **engineering report** (maximum six pages) explains the required design evidence in more detail and is submitted separately from TeamAId task-management evidence.

### 🧠 AI Review implementation summary

The review form sends validated decisions through `IncidentDashboard` → `DataManager` → `HazardReport.add_ai_review()` → the existing `IncidentRepository` → JSON or SQLite. `AIReviewEntry` is one immutable value object per history entry, with one class in its own file. The UI reads the saved result back through `DataManager.ai_review_history()`. This preserves the original Gemini assessment and the separate incident-status audit history.

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