# NED-Beta
> "Turning data into resilience one function at a time" - J.B.

#### Nonstructural Element Database
This repository provides remote hosting and version control for the development of NED, the Nonstructural Element Database. NED is a relational database that collects information from experimental, analytical, and historic performance observations of nonstructural building elements into seismic fragilities and consequence models to support building-specific seismic performance research and assessments. Currently, the project is still in its active development and does not yet have consequence models or data from historical events, but has collected over 2000 experimental data points and compiled a fragility data set that includes and expands upon the full FEMA P-58 nonstructural database. The experimental test data and seismic fragility are explicitly related through primary and foreign key architecture within the database to promote data transparency and reuse.

## Database Architecture
The goal of this project is to develop a robust and scalable database of fragility and consequence models of nonstructural building elements for seismic performance evaluation. Data is organized in a way such that each data table represents an abstract portion of the fragility model, e.g., separating observations of component performance from an experimental test from that of a fragility model and repair costs consequence models. In that way, that data is both nimble/scalable with new information and can be clearly linked back to original source data and models through explicit relational keys. The outcomes of this project will expand the applicability of performance- and recovery-based earthquake assessments, resulting in a publicly available database to support current research and building design. The figure below outlines the current portions of the database under development and future development plans.

<img width="950" height="1232" alt="ned_erd" src="https://github.com/user-attachments/assets/52debba8-324a-43c4-9f27-7906e7200c7c" />

## Repository Organization
- **resources/data/** - Canonical JSON data files serving as the single source of truth for the database.
- **ned_app** - Django application (python) facilitating database management (e.g., model definition, serializers, management commands).
- **ned_proj** - Django project settings.
- **resources/example_data/** - Template JSON files for contributors to use when adding new data.
- **scripts** - General project scripts that are outside the Django application management process.
- **visualization_tools** - Jupyter notebook workflows that interact with the NED database to illustrate backend interactions via python.
- **db.sqlite3** - SQLite database file (disposable build artifact, generated from JSON data via `python manage.py ingest`).

### Data Schema
Model and field descriptions are provided in the docstrings in ned_app/models.py. The overview below provides a brief description of two of the fields found in the experiment model.

#### Component Subcategorization Hierarchy
To categorize building components, we rely on the UNIFORMAT II element classification system (NISTIR 6389). However, this system only classifies nonstructural components at a high level, and further detail is needed to adequately separate different types of components within each category for the purpose of assessing building performance.  Therefore, we propose a new subcategorization hierarchy consisting of four nested component attributes:
-	**Child Attribute 1: Connection Detail** – Describes the specific type of installation or connection type of the component, such as perimeter-fixed vs back-braced ceilings.
-	**Child Attribute 2: Material** – Describes a general grouping of components based on material, e.g., light weight vs heavy weight ceiling tiles or CPVC vs iron sprinkler pipes.
-	**Child Attribute 3: Size Class** - Describes a general grouping of components based on size, e.g., large gridded area of ceiling tiles or specific equipment size.

The purpose of the component subcategorization is to provide further structured detail to end users who use the collected data for fragility development. Each child attribute is only nested under the parent component category attribute; no explicit hierarchy exists between child attributes and not all subcategorization layers need to be assigned if they are not applicable. Consistent naming, case, and spelling schemes should be used when populating subcategorization attributes. Reviewers should review the Sweets MasterFormat construction products database to familiarize themselves with general component taxonomy and terminology prior to developing subcategorization hierarchies for particular component types.

#### DS Class
To provide a structured detail of observed damage attributes, we propose a DS Class attribute consisting of the possible mutually exclusive classifications: 
-	**No damage**: no change in state was observed from the test.
-	**Inconsequential Damage**: (aesthetic) damage was observed but is unlikely to require repair or impact system operation (no action required). E.g., if the component was hidden would the building user ever know there was a problem? Or would the building performance be affected in any way? 
-	**Consequential Damage**: May require repair or impact system operation (observable and requires action).

![image](https://github.com/user-attachments/assets/b9f4a4bd-3083-4028-bc7b-dba06b1f3dd0)

The purpose of the DS Class attribute is to provide a first-pass structured grouping of observed damage to aid in later fragility development. However, we recognize that any grouping of damage states introduces subjectiveness into the process. Therefore, our goal is to implement as little subjectiveness as possible while still providing useful structured data for later users of the database. This attribute simply acts to separate consequential damage from inconsequential damage. Further separation of consequential damage into multiple damage states is an attribute of the damage state itself and not the initial observation of damage and is therefore up to the fragility developer to refine.

All observations of damage in the database are assigned into one of the three aforementioned DS classes; if for some reason a damage state class cannot be identified by the reviewer, it should be flagged as “unknown”. When in doubt, we err towards assigning observed damage as consequential, to allow the later fragility developers the option to decide whether or not to include the observation in their fragility development.

## Visualization Tools
Several jupyter-notebook-based database user interface tools are provided in the `visualization_tools` subdirectory. These tools allow users to interact with data in the SQL database, query specific data views, and download cvs files without the need to code. 

Two predefined workflows are provided:
- **visualization_tools/view_experemints.ipynb** - Queury experimental tests of nonstructural components in the database by component type and component detail, download data, and plot distributions of peak test demands at the occurrence of various damage states.
- **visualization_tools/view_experemints.ipynb** - Queury fragility models of nonstructural components in the database by component type and component detail, download data, and plot fragility curves for various damage states.

### Running the Notebook
Prior to running a notebook, first ensure that all required packages have been installed by running the following command:
```
pip install -r visualization_tools/requirements.txt
```

Once all required packages have been installed, open the Jupyter Notbeook by running the following command:
```
Jupter Notebook
```

For additional instructions please see the Juptyer Notebook installation instructions: https://jupyter.org/install

## Exporting Data to CSV

The NED database includes a management command for simple table queries and exporting results to CSV files. The command does not currently handle more complex table queries such as filtering by partial strings or joining results across tables.

### Using the `query_to_csv` Command

The `query_to_csv` management command allows you to export any database table to CSV format with optional filtering and field selection.

#### Basic Usage

**Export all records from a table:**
```bash
python manage.py query_to_csv --model Experiment --output_file exports/all_experiments.csv
```

This exports all fields from the Experiment table to a CSV file. The output directory will be created automatically if it doesn't exist.

#### Available Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--model` | Yes | Model name to query (e.g., `Experiment`, `Reference`, `Component`, `FragilityModel`) |
| `--output_file` | Yes | Path where the CSV file will be saved |
| `--fields` | No | Comma-separated list of specific fields to export (default: all fields) |
| `--filter` | No | Comma-separated key=value pairs to filter results |

#### Examples

**Export specific fields only:**
```bash
python manage.py query_to_csv --model Experiment \
  --output_file exports/experiment_summary.csv \
  --fields id,specimen,material,test_type
```

**Export with filters (AND logic):**
```bash
python manage.py query_to_csv --model Experiment \
  --output_file exports/steel_tensile_tests.csv \
  --filter material=Steel,test_type=Tensile
```

**Combine field selection and filtering:**
```bash
python manage.py query_to_csv --model Experiment \
  --output_file exports/filtered_data.csv \
  --fields id,specimen,material,peak_demand \
  --filter reviewer=John,ds_class=Consequential
```

#### Available Models
To see all available models in the database, run:

```bash
python manage.py query_to_csv --list-models
```

This will display a complete list of queryable models. Use the exact model name (case-sensitive) when specifying the `--model` argument.

#### Tips and Best Practices

- **Filter logic**: Multiple filters use AND logic (all conditions must match). For complex queries, consider using the Django shell
- **Large exports**: For tables with thousands of records, specify `--fields` to reduce file size
- **Dates and special characters**: The CSV output uses UTF-8 encoding to properly handle special characters common in engineering data
- **Verify output**: Open the CSV file in your preferred spreadsheet application (Excel, Google Sheets, etc.) to verify the export

#### Troubleshooting

**"Model not found" error:**
```bash
# Ensure the model name matches exactly (case-sensitive)
python manage.py query_to_csv --model experiment  # ❌ Wrong (lowercase)
python manage.py query_to_csv --model Experiment  # ✅ Correct
```

**No data exported:**
Check your filter conditions. If a filter returns no results, the command will report "No data found matching criteria."

```bash
# Debug: Export all records first to see what values exist
python manage.py query_to_csv --model Experiment --output_file test.csv

# Then apply filters based on actual values in the data
python manage.py query_to_csv --model Experiment --output_file filtered.csv --filter material=Steel
```

**File path issues on Windows:**
Use forward slashes or raw strings in PowerShell:
```powershell
# Using forward slashes
python manage.py query_to_csv --model Experiment --output_file exports/data.csv

# Or escape backslashes
python manage.py query_to_csv --model Experiment --output_file exports\\data.csv
```


## Importing Data from CSV

The NED database includes a management command for importing new records from CSV files directly into the canonical JSON source data. This provides an alternative to manually editing JSON files, which may be preferable for contributors working primarily in spreadsheet tools.

> **Important:** The import commands only convert your CSV into JSON and append it to the source files — they do **not** validate the data. After importing, you must (1) check JSON files in the `resources/data/` directory to ensure what has been appended to the source files is correct, (2) run `python manage.py ingest` to load the new records into the database, and (3) run `python manage.py test` to validate them. `ingest` reports any invalid records and exits with a non-zero status if any fail.

### Using the `import_model` Command

Use `import_model` to import **Reference**, **Experiment**, or **ExperimentFragilityModelBridge** records from a CSV. For fragility models, curves, and component links, use [`import_fragility`](#using-the-import_fragility-command) instead.

#### Basic Usage

```bash
python manage.py import_model --model Experiment --input_file my_data.csv
```

#### Available Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--model` | Yes | Model name to import (`Reference`, `Experiment`, or `ExperimentFragilityModelBridge`) |
| `--input_file` | Yes | Path to the CSV file containing new records |
| `--dry_run` | No | Report what would be appended without writing any changes |
| `--list-models` | No | Show all models that support CSV import |

### Using the `import_fragility` Command

The `import_fragility` command imports fragility models, their damage-state curves, and component links all at once from a single flat join CSV. This is the recommended workflow for adding new fragility models.

Each row in the CSV represents one damage state (one `FragilityCurve`). Multiple rows sharing the same `reference` and `model_id` belong to the same fragility model and must repeat the model-level fields identically.

#### Basic Usage

```bash
python manage.py import_fragility --input_file my_fragilities.csv
```

#### Available Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--input_file` | Yes | Path to the fragility import CSV file |
| `--dry_run` | No | Report what would be appended without writing any changes |


### Templates

CSV templates with example rows are provided in `resources/import_templates/`. Copy the relevant template, replace the example row(s) with your data, and remove any rows you do not wish to import.

### CSV Conventions

- **Foreign key columns** accept natural key values, not numeric IDs:
  - `reference` → the `reference_id` string (e.g., `SMITH-2020-EXP`)
  - `component` → the `component_id` string (e.g., `D.50.2.1.A`)
  - `fragility_model` → the full `fragility_model_id` string (e.g., `SMITH-2020-EXP|fra001`)
  - `experiment` → the experiment `id` string
- **Choice fields** must exactly match one of the valid values. See `ned_app/models.py` for accepted values.
- **Optional numeric fields** (e.g., `alt_edp_value`) may be left blank; they will be stored as `null`.
- **Values containing commas** must be wrapped in double quotes (standard CSV quoting).
- Files should be **UTF-8** encoded and **comma-delimited**. Some non-US Excel versions save semicolon-delimited CSVs; if the importer reports this, re-save as *CSV UTF-8 (Comma delimited)*.
- Because the `Reference` model stores citation data as nested CSL-JSON, the CSV template uses flattened `csl_*` columns that the command reconstructs internally.

### Examples

**Preview an import without writing changes:**
```bash
python manage.py import_model --model Experiment \
  --input_file my_experiments.csv \
  --dry_run
```

**Import references:**
```bash
python manage.py import_model --model Reference \
  --input_file my_references.csv
```

**Import experiments:**
```bash
python manage.py import_model --model Experiment \
  --input_file my_experiments.csv
```

**Import fragility model and curves:**
```bash
python manage.py import_fragility --input_file my_fragilities.csv
```

### Tips

- **Import order matters for foreign keys.** Import `Reference` records before `Experiment` records that reference them; `ingest` resolves foreign keys by natural key, so the target records must already be present.
- **Use `--dry_run` first** to preview which records would be appended (and surface the column warning) before changing the JSON files.
- **Always run `ingest` and the test suite after importing** — they are where invalid values, choices, and foreign keys are caught.
- **Commit after each successful batch.** Once `ingest` and the tests pass, commit before starting the next import. Each commit is a safe checkpoint: if a later batch fails validation, you can restore to it without losing the batches you already verified.
- **Windows path syntax**: Use forward slashes or quoted backslashes in PowerShell:
  ```powershell
  python manage.py import_model --model Experiment --input_file exports/my_data.csv
  ```

### Recovering from a failed import

If `ingest` reports errors, **stop before committing.** The invalid records are already in the canonical JSON files, because the import step only converts and appends without validating. `ingest` also applies records one at a time without a wrapping transaction, so the database now holds whatever it created before the failure. Since `ingest` never deletes, restoring the JSON is not enough on its own; you must also rebuild the database.

Assuming your last good batch is already committed (see the tip above), recover in two steps:

1. **Discard the appended JSON**, which reverts only the failed batch:
   ```bash
   git restore resources/data/
   ```
2. **Rebuild the database** from the restored source, so it no longer contains the partially-applied records:
   ```bash
   rm -f db.sqlite3
   python manage.py migrate
   python manage.py ingest
   ```

Then fix the CSV and import again.


## Contributors Guide

### Setting up a Virtual Environment (optional but recommended)
Setting up a virtual environment helps to ensure you are able to setup an isolated project for using the NED database locally and avoid conflicts with other dependencies. While there are many ways to setup a virtual environment, below is an example using Python's built in `venv` module.
```
python -m venv venv      # create a virtual environment called "venv"
# Activate on Windows (Command Prompt / PowerShell)
venv\Scripts\activate
# Activate on Git Bash / Bash on Windows
source venv/Scripts/activate
# Activate on macOS / Linux / WSL
source venv/bin/activate
```

### Installing the Required Packages
Be sure that all packages below have been installed in your virtual or global environment.

**For production dependencies:**
```
pip install -r requirements.txt
```

**For development dependencies (includes ruff for code quality):**
```
pip install -r requirements-dev.txt
```

### Local Development Setup

After installing dependencies, you must set up the local database:

```bash
# 1. Apply database migrations
python manage.py migrate

# 2. Build the database from canonical JSON data (REQUIRED)
python manage.py ingest
```

The `ingest` command reads all JSON files from `resources/data/` and populates the SQLite database. This step is mandatory for local development, as the `db.sqlite3` file is not tracked in version control—it's a disposable build artifact generated from the JSON source data.

### How to Add New Data or Modify Existing Data
We welcome contributions of new experimental results, reference data, and fragility models! Because NED uses a **"Git-as-Source"** architecture, adding data, or correctinng existing records involves working directly with the JSON files that serve as our single source of truth.


Follow this step-by-step guide to contribute:

#### 1. Fork and Branch
Create your own fork of the repository and start a new feature branch for your specific contribution (e.g., `data/add-ucsd-experiments`).


#### 2. Add Your Data or Edit existing data
You have two options for adding data:

**Option A — Edit JSON directly** (recommended for small additions or when working in a code editor):
Directly edit the JSON files in the `resources/data/` directory.
*   **Important:** Do **not** use the Django Admin interface or a web API to input new data.
*   **Templates:** Check `resources/example_data/` for examples of proper formatting.

**Option B — Import from CSV** (useful for larger datasets or contributors who prefer spreadsheet tools):
Populate a CSV template from `resources/import_templates/` and use the appropriate import command:
```bash
# References, experiments, and experiment-fragility links
python manage.py import_model --model Experiment --input_file my_data.csv

# Fragility models, curves, and component links (all in one flat CSV)
python manage.py import_fragility --input_file my_fragilities.csv
```
See [Importing Data from CSV](#importing-data-from-csv) for full instructions.
*   **Common Files:**
    *   `experiments.json`: For new experimental results.
    *   `references.json`: For new bibliographic references.
    *   `fragility_model.json`: For new fragility functions.
*   **Editing Existing Records:** Only modify field values; do **not** change the data structure or schema.    

If modifying existing data:
*   **Important:** Only modify field values; do not change the structure or schema.
*   **Examples of valid modifications:**
    *   Correcting spelling or grammar in descriptions
    *   Updating numeric values or material classifications
    *   Adding or refining component details
    *   Correcting references or citations

#### 3. Validate Locally (Recommended)
Before submitting, we strongly recommend building the database locally to catch any errors. This ensures your data fits the schema and doesn't break any links.

**Setup your local DB:**
```bash
python manage.py migrate
python manage.py ingest
```

**Regenerate the fixture snapshot:**

**Windows (PowerShell):**
```powershell
$env:PYTHONUTF8 = "1"
python manage.py dumpdata ned_app --indent 2 --output ned_app/fixtures/initial_data.json
```

**macOS/Linux/WSL:**
```bash
PYTHONUTF8=1 python manage.py dumpdata ned_app --indent 2 --output ned_app/fixtures/initial_data.json
```

*   *Why:* The fixture is a snapshot of the expected database state. Your data modifications must be captured in it so tests pass. Always use `--output` (or `-o`) rather than shell redirection (`>`). On Windows, also set `PYTHONUTF8=1` so Python's entire I/O stack uses UTF-8 — without it, Django's serializer will fail or corrupt any non-ASCII characters (e.g., Unicode fractions, special hyphens) when the Windows system code page is active.

**Run the integrity check:**
```bash
python manage.py test ned_app.tests
```
*   *What this checks:* It verifies that all Foreign Keys match (e.g., every experiment points to a valid component ID) and that Primary Keys are unique.

#### 4. Submit a Pull Request
Commit your changes and open a Pull Request (PR) to the `main` branch. 

**In your PR description, please include:**
*   A summary of what data you are adding, or what data was modified and why
*   The specific records or fields that changed, if any and the rationale for the change (e.g., "Corrected spelling to match FEMA P-58 terminology").
*   The source of the data (citations, reports) or any citations or references that support the changes made.
*   Any context notes that would help the reviewer.

#### What Happens Next? (The Review Process)
A project maintainer will review your PR. They will check the "JSON Diff" to see exactly what data is entering the system or what data changed and ensure the automated tests pass. Once approved and merged, your data is effectively "published" and will be live on the next deployment!


### How to Modify the Database Structure

**For Developers:** If you need to change the database schema (e.g., adding a new field like `data_source_type`, renaming a column, or creating a new table), you must follow a strict "Round-Trip" protocol. This ensures that the mapping between our JSON source of truth and the runtime database remains perfectly synced.

#### Step 1: Prepare Your Workspace
Start with a fresh local database populated with the current canonical data. **Keep a copy of this database** — you will need it later to apply your new migrations.
```bash
cp db.sqlite3 db_before_changes.sqlite3
rm -f db.sqlite3
python manage.py migrate
python manage.py ingest
```

#### Step 2: Implement Schema Change & Data Migration
Modify `models.py` and create your migrations.
*   **Critical:** If your schema change affects existing data (e.g., adding a required field), your migration file must also include the logic to migrate the existing data.
*   *Example:* Use `RunPython` operations or default values in the migration to ensure all 2000+ existing rows remain valid.
```bash
python manage.py makemigrations
```

#### Step 3: Update the Pipelines
Update the remaining code to match the **new** schema:
*   **`serializer.py`:** Update serializer fields and classes to reflect the new model structure.
*   **`ingest` command:** Update the logic to map JSON keys to your new DB fields.
*   **`export_data` command:** Update the logic to serialize your new DB fields back to JSON.
*   **`admin.py`:** Register any new models and update existing admin classes as needed.
*   *Constraint:* The loop `Export(Ingest(Source))` must be idempotent (lossless).

#### Step 4: Apply Migrations to the Saved Database
Restore the database you saved in Step 1 and apply your new migrations to it. This transforms the data **through the migration**, ensuring correctness without relying on the updated serializers (which expect the new schema).
```bash
cp db_before_changes.sqlite3 db.sqlite3
python manage.py migrate
```

#### Step 5: Export Updated Canonical Data
Export the migrated database to generate the updated canonical JSON files and fixture:
```bash
python manage.py export_data --output_dir resources/data/
python manage.py dumpdata ned_app --indent 2 --exclude contenttypes --exclude auth.permission -o ned_app/fixtures/initial_data.json
```

#### Step 6: Verification (The "Round-Trip" Protocol)
Run these tests to prove that data flows safely in both directions:
```bash
python manage.py test ned_app.tests.test_data_integrity.DataIntegrityTests.test_db_round_trip
python manage.py test ned_app.tests.test_data_integrity.DataIntegrityTests.test_json_to_db_to_json_round_trip_is_lossless
```

#### Step 7: Update and Run Unit Tests
Review and update existing unit tests to match the new schema, and add tests for any new models, serializers, or commands. Ensure the full test suite passes:
```bash
python manage.py test ned_app.tests
```

#### Step 8: Finalize and Commit
Update `README.md` and templates in `resources/example_data/` if your change affects the user-facing data structure. Commit all changed files (models, migrations, updated JSONs, scripts, and fixtures) and open your PR.

### Launch the Django Admin
To launch and take advantage of the administrative interface, run the web server:
```
python manage.py runserver
```
Then, in a browser, launch the URL: http://localhost:8000/admin/


>Note, you may need to set up your own admin username and password by running the following command*
```
python manage.py createsuperuser
```

## Architecture Overview

NED implements a **"Git-as-Source"** data pipeline where JSON files serve as the single source of truth for all database content. This architecture ensures data integrity, version control, and reproducibility.

### Key Components

**1. Canonical Data Source (`resources/data/`)**
- All authoritative data lives in JSON files within the `resources/data/` directory
- These files are version-controlled and serve as the definitive source of truth
- Changes to the database must be preserved eventually by updating these JSON files

**2. Database as Build Artifact (`db.sqlite3`)**
- The SQLite database file is a disposable build artifact, not tracked in version control
- It is generated from the JSON source files and can be rebuilt at any time
- Think of it like compiled code: it's derived from the source (JSON) and can be regenerated

**3. Ingestion Pipeline (`python manage.py ingest`)**
- Reads JSON files from `resources/data/`
- Validates data against defined schemas
- Populates the SQLite database using Django models and serializers
- Implements idempotent operations (can be run multiple times safely)
- This command must be run after `migrate` to build a working local database

**4. Export Pipeline (`python manage.py export_data`)**
- Reads data from the database
- Serializes models back to JSON format
- Writes canonical JSON files to `resources/data/`
- Used to generate the authoritative JSON after making changes via Django admin or code

### Data Flow

```
JSON Files (resources/data/) 
    ↓ [python manage.py ingest]
SQLite Database (db.sqlite3)
    ↓ [python manage.py export_data]
JSON Files (resources/data/)
```

This bidirectional pipeline enables both programmatic data entry (via JSON) and manual curation (via Django admin), while maintaining JSON as the canonical source.


### Code quality assurance
We use automated checks at every commit to maintain a high-quality codebase. Our continuous integration (CI) pipeline runs four types of tests that must all pass before code can be merged. Please ensure all of the following tests pass before committing new code.

#### 1. Code Linting with Ruff
Ruff checks your Python code for style issues, potential bugs, and code quality problems. It enforces consistent coding standards across the project.

**To run locally:**
```bash
ruff check
```

**To fix auto-fixable issues:**
```bash
ruff check --fix
```

**Common issues and fixes:**
- **Unused imports**: Remove any imports that aren't used in your code
- **Unused variables**: Remove variables that are assigned but never used
- **Line too long**: Break long lines to stay under 85 characters
- **Missing docstrings**: Add Google-style docstrings to functions and classes

**Configuration**: Ruff settings are defined in `pyproject.toml`.

#### 2. Code Formatting with Ruff
Ruff format ensures consistent code formatting across the entire codebase. It automatically formats your Python code to match the project's style guidelines.

**To check formatting without making changes:**
```bash
ruff format --check
```

**To automatically format your code:**
```bash
ruff format
```

**Key formatting rules:**
- **Single quotes**: Use single quotes for strings (e.g., `'hello'` not `"hello"`)
- **Line length**: Maximum 85 characters per line
- **Indentation**: 4 spaces (no tabs)
- **Import sorting**: Imports are automatically organized

#### 3. Spell Checking with Codespell
Codespell catches spelling mistakes in text files, comments, and docstrings. This helps maintain professional documentation and code comments.

**To run locally:**
```bash
codespell .
```

**Handling false positives:**
- Add words to `ignore_words.txt` if they generate false positives
- Skip entire files by adding them to the `skip` list in `pyproject.toml`
- Common technical terms and abbreviations are already in the ignore list

**What it checks:**
- Python code comments and docstrings
- Markdown files (like this README)
- Configuration files
- Excludes: Jupyter notebooks, resources/, and visualization_tools/ directories

#### 4. Unit Tests with Django Test Suite
The project includes comprehensive unit tests that verify the functionality of models, serializers, and data processing components. All tests must pass to ensure your changes don't break existing functionality.

**To run all tests:**
```bash
python manage.py test ned_app.tests
```

**To run specific test files:**
```bash
python manage.py test ned_app.tests.test_models
python manage.py test ned_app.tests.test_serializers
python manage.py test ned_app.tests.test_data_processor
```

**To run a specific test method:**
```bash
python manage.py test ned_app.tests.test_models.ReferenceModelTest.test_csl_data_validation
```

**Understanding test output:**
- **OK**: All tests passed
- **FAIL**: A test failed - check the error message for details
- **ERROR**: A test couldn't run due to an error in the test setup

**Common test failure causes:**
- **Database issues**: Make sure you haven't changed model fields without creating migrations
- **Missing test data**: Ensure test fixtures and sample data are properly set up
- **Import errors**: Check that all required dependencies are installed with `pip install -r requirements.txt` and `pip install -r requirements-dev.txt`

**Test coverage**: The project has 169 tests covering models, serializers, and data processing. When adding new features, consider adding corresponding tests.

**Data Integrity Tests**: The test suite includes critical end-to-end validation tests that ensure the integrity of the Git-as-Source data pipeline:
- `test_db_round_trip`: Validates that data can be exported from the database and re-ingested without loss
- `test_json_to_db_to_json_round_trip_is_lossless`: Ensures complete round-trip fidelity between JSON source files and the database

These tests are essential for maintaining data quality and ensuring that the `ingest` and `export_data` commands work correctly together.

#### Running All Quality Checks Locally
To run all quality checks that the continuous integration (CI) pipeline will run, use these commands in sequence:

```bash
# 1. Check code formatting
ruff format --check

# 2. Run linting
ruff check

# 3. Check spelling
codespell .

# 4. Run unit tests
python manage.py test ned_app.tests
```


---

This repository is principally developed and maintained by:

1. Dustin Cook, Research Structural Engineer
   - Engineering Laboratory, Materials and Structural Systems Division, Earthquake Engineering Group
   - @dustin-cook
   - dustin.cook@nist.gov

Please reach out with questions and comments.

## Disclaimer:
Certain equipment, instruments, software, or materials are identified here in order to specify the data/code adequately.  Such identification is not intended to imply recommendation or endorsement of any product or service by NIST, nor is it intended to imply that the materials or equipment identified are necessarily the best available for the purpose.

NIST-developed software is provided by NIST as a public service. You may use, copy, and distribute copies of the software in any medium, provided that you keep intact this entire notice. You may improve, modify, and create derivative works of the software or any portion of the software, and you may copy and distribute such modifications or works. Modified works should carry a notice stating that you changed the software and should note the date and nature of any such change. Please explicitly acknowledge the National Institute of Standards and Technology as the source of the software.

NIST-developed software is expressly provided "AS IS." NIST MAKES NO WARRANTY OF ANY KIND, EXPRESS, IMPLIED, IN FACT, OR ARISING BY OPERATION OF LAW, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, AND DATA ACCURACY. NIST NEITHER REPRESENTS NOR WARRANTS THAT THE OPERATION OF THE SOFTWARE WILL BE UNINTERRUPTED OR ERROR-FREE, OR THAT ANY DEFECTS WILL BE CORRECTED. NIST DOES NOT WARRANT OR MAKE ANY REPRESENTATIONS REGARDING THE USE OF THE SOFTWARE OR THE RESULTS THEREOF, INCLUDING BUT NOT LIMITED TO THE CORRECTNESS, ACCURACY, RELIABILITY, OR USEFULNESS OF THE SOFTWARE.

You are solely responsible for determining the appropriateness of using and distributing the software and you assume all risks associated with its use, including but not limited to the risks and costs of program errors, compliance with applicable laws, damage to or loss of data, programs or equipment, and the unavailability or interruption of operation. This software is not intended to be used in any situation where a failure could cause risk of injury or damage to property. The software developed by NIST employees is not subject to copyright protection within the United States.
