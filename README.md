# 🛡️ Campus Safety Hazard Reporting System — INF1103 Part 2

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
| 🐳 Docker | `Dockerfile` — Section 8.2 |
| ⚙️ CI | `.github/workflows/python-tests.yml` — Section 9 |
| ✅ Tests | 182 offline tests — Section 9 |

## 2. ✨ Main application functions

CLI menu (displayed by `IOManager`, dispatched by `CampusSafetyApplication.run()`):

1. **Submit New Hazard Report** — enter reporter details, location, people affected, asset and description, plus an optional image. Review the AI assessment and priority breakdown, then confirm to save.
2. **View All Logged Incidents** — list saved reports.
3. **View Top 5 Most Frequent Hazards** — the five most frequently reported AI hazard categories.
4. **Search and Filter Incidents** 🆕 — filter by location keyword, status, category and minimum severity.
5. **View Facilities Summary Report** 🆕 — active workload, backlog rate, urgent hazards, and counts by location and category.
6. **Exit**

Additional capabilities implemented in the domain and data layers (covered by automated tests; no menu option yet):

- 📜 **Incident Status Audit Trail** — `DataManager.update_status()` / `status_history()`.
- 👤 **AI Assessment Review & Feedback** — `DataManager.record_ai_review()` / `ai_review_history()`.
- 📤 **Export** — `DataManager.export_csv()` and `export_txt()`.
- 🗃️ **Backup and restore** — automatic pre-change backups, `DataManager.backups()` and `restore()`.

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

### 7.2 📜 Incident Status Audit Trail

Every new incident starts with a creation entry (`Created → Pending Review`). Each later status change records the incident ID, timezone-aware timestamp, previous status, new status and reason. An unchanged status adds no entry, and inconsistent histories are rejected. Implemented in `IncidentAuditEntry`, `HazardReport.change_status()` / `status_history()` and `DataManager.update_status()` / `status_history()`. This is an application-level history, **not** a tamper-proof security log.

### 7.3 🧑‍💻 AI Assessment Review & Feedback

Staff can record **Accepted**, **Flagged as Incorrect** or **Further Review Requested** against a saved Gemini assessment, with a reviewer name and reason. A review never changes the original AI fields, priority, status or Audit Trail. Implemented in `AIReviewEntry`, `HazardReport.add_ai_review()` and `DataManager.record_ai_review()`. Reviewer names are self-entered and **not authenticated**.

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
python main.py
```

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
```

Inside the container, data is stored in the `/data` volume (`HAZARD_DATA_DIR=/data`), so incidents persist between runs. `.env` is excluded from the image by `.dockerignore` and passed at run time with `--env-file`. The graphical image picker is unavailable in the container; the CLI falls back to asking for a file path.

### 8.3 🔐 Configuration (`.env`)

| Variable | Purpose | Default |
| --- | --- | --- |
| `GEMINI_API_KEY` | Gemini credentials (required for real submissions) | — |
| `GEMINI_MODELS` | Comma-separated model fallback order | Built-in list in `gemini_assessor.py` |
| `HAZARD_STORAGE_BACKEND` | `json` or `sqlite` | `json` |
| `SQLITE_DB_PATH` / `INCIDENTS_DB` | Database file for SQLite / JSON | Data folder |
| `HAZARD_DATA_DIR` | Shared data folder for either backend | Project folder (`/data` in Docker) |

Never commit `.env`, share your key or show it in screenshots. Changing the backend does **not** transfer existing records. Use **fictional test data** when demonstrating the application.

## 9. ✅ Automated tests and CI

All tests run offline using stubs, mocks and temporary databases; no Gemini key or network access is required.

```powershell
python -m unittest discover -s tests -t . -v      # everything (182 tests)
python -m tests.run_ai_tests                      # formatted AI Manager report
```

| Test file | Tests | Covers |
| --- | --- | --- |
| `ai_manager_test/test_ai_assessment_validation.py` | 8 | AI field and schema validation |
| `ai_manager_test/test_ai_manager.py` | 4 | Provider delegation, unvalidated results, substitution |
| `ai_manager_test/test_assessment_provider.py` | 4 | Abstract provider contract |
| `ai_manager_test/test_gemini_assessor.py` | 19 | Prompt, JSON parsing, malformed JSON, timeouts, retries, model fallback, images |
| `ai_manager_test/test_gemini_prompt_builder.py` | 7 | Prompt content and personal-data redaction |
| `ai_manager_test/test_image_evidence_processor.py` | 9 | Image type, size, corruption and mismatch checks |
| `test_logic_manager_rules.py` | 29 | Scoring points, multi-condition Critical rule, High/Normal, routing, frequency, duplicates, sorting, OCP/LSP substitution |
| `test_data_repositories.py` | 40 | JSON **and** SQLite CRUD, persistence, audit trail, AI review, backups, corrupt files, migration, factory |
| `test_hazard_report_domain.py` | 17 | Input validation, encapsulation, status transitions, AI review rules |
| `test_io_manager_cli.py` | 14 | Menu, input validation loops, search criteria, result and summary display |
| `test_application_workflow.py` | 19 | Full IO → AI → Logic → Data workflow, AI failure, cancellation, search/summary, menu, `main()` startup errors |
| `test_facilities_data_manager_search.py` | 7 | `DataManager.search()` filters |
| `test_facilities_logic_manager_summary.py` | 2 | Facilities summary metrics |
| `test_facilities_workflow_integration.py` | 1 | Search combined with summary |
| `test_facility_summary_domain.py` | 2 | `FacilitySummaryReport` backlog rate |
| **Total** | **182** | |

Log messages such as `simulated timeout`, `offline` and `Malformed AI JSON` during the AI tests are expected; they come from deliberate failure tests.

**Continuous integration** (`.github/workflows/python-tests.yml`) runs on pushes to `main` and `feature/**` branches, and on pull requests to `main`:

1. **basic-checks** — verifies required files (including the `Dockerfile`), compiles all Python files, installs requirements, runs the formatted AI test report and the full test suite.
2. **docker** — builds the image, runs the full test suite inside the container, and starts the CLI in the container to confirm it launches and exits cleanly.

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

## 11. 🗂️ Project structure

```text
INF1103_P3_T4_PART2/
├── campus_safety/
│   ├── application.py            # CampusSafetyApplication: coordinates the four managers
│   ├── domain/                   # HazardReport, Decision, FacilitySummaryReport, audit/review entries, schema, errors
│   ├── io_manager/               # IOManager, InputValidator, MediaHandler
│   ├── ai_manager/               # AIManager, AssessmentProvider, GeminiAssessor, prompt and image helpers
│   ├── logic_manager/            # LogicManager, rules, scorers, matchers, router, history, summary builder
│   └── data_manager/             # DataManager, IncidentRepository, JSON and SQLite, exporter, factory
├── tests/                        # 182 offline unittest tests (+ ai_manager_test/ and run_ai_tests.py)
├── test_io_manager.py            # IO Manager author's original pytest-style checks
├── .github/workflows/python-tests.yml
├── Dockerfile
├── .dockerignore
├── .env.example                  # Safe blank configuration template
├── main.py                       # Entry point
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
| 🧺 **Aggregation** | `CampusSafetyApplication` ◇ four managers; `DataManager` ◇ `IncidentRepository`; `AIManager` ◇ `AssessmentProvider`; `LogicManager` ◇ optional evaluator/sorter/matcher | Parts are created elsewhere and injected; they can exist and be tested independently. |
| 🏗️ **Composition** | `IOManager` ◆ `MediaHandler`; `DataManager` ◆ `IncidentExporter`; `PriorityEvaluator` ◆ `ScoreCalculator` ◆ scorers | The owner creates the part in its constructor and controls its lifetime; the part is not shared. |

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
