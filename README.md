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

## Contributing Data

NED uses a **"Git-as-Source"** data model, meaning the canonical source of truth for all database content lives in the JSON files within the `resources/data/` directory. This approach ensures data integrity, version control, and transparency in the contribution process.

### How to Contribute Your Data

If you have experimental data, fragility models, or other relevant information to add to NED, please follow this workflow:

1. **Fork the repository**: Create your own fork of the NED repository on GitHub.

2. **Create a new branch**: Create a dedicated branch for your contribution (e.g., `add-ceiling-tile-data`).

3. **Add or edit JSON data files**: 
   - Navigate to the `resources/data/` directory
   - Use the template files in `resources/example_data/` as a guide for proper structure and formatting
   - Add your new data or edit existing JSON files following the established schema
   - Common data types include: `component.json`, `experiment.json`, `fragility_model.json`, and `reference.json`

4. **Validate your changes locally**:
   - Install the project dependencies: `pip install -r requirements.txt` and `pip install -r requirements-dev.txt`
   - Build the database from your updated JSON files: `python manage.py migrate` then `python manage.py ingest`
   - Run the validation tests: `python manage.py test`
   - Ensure all tests pass before proceeding

5. **Commit and push your changes**: Commit your JSON file changes with a descriptive message and push to your fork.

6. **Open a Pull Request**: Submit a Pull Request to the main NED repository with a clear description of:
   - What data you're adding
   - The source of the data
   - Any relevant context or notes for reviewers

Your contribution will be reviewed by the maintainers, who will check for data quality, schema compliance, and consistency with existing data. Once approved, your data will be merged into the canonical dataset.

## Contributors Guide

### Setting up a Virtual Environment (optional but recommended)
Setting up a virtual environment helps to ensure you are able to setup an isolated project for using the NED database locally and avoid conflicts with other dependencies. While there are many ways to setup a virtual environment, below is an example using Python's built in `venv` module.
```
python -m venv venv      # create a virtual environment called "venv"
venv\Scripts\activate     # (On Windows) activate your virtual environment
source venv/bin/activate # (On Mac) activate your virtual environment
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

### Adding Data to the Database
Data can be added to the database locally by either of the two methods
1) Launch the Django server and add data using the Django admin interface
2) Configure the json files in `resources/data` and run the following command:
```
python manage.py ingest
```
>Example json files can be found in `resources/example_data`

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

### Making Changes to the Schema (not recommended)
Changing the Django model may cause data corruption and validations issue with the existing data. After making changes, run the following commands to apply the changes to the sql db.
```
python manage.py makemigrations
python manage.py migrate
python manage.py ingest  # Rebuild database from JSON after schema changes
```

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

**Test coverage**: The project has 81 tests covering models, serializers, and data processing. When adding new features, consider adding corresponding tests.

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

#### Installing Development Dependencies
To run these tools locally, make sure you have all dependencies installed:

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

This installs all required packages including Django, djangorestframework, jsonschema, and ruff for code quality checks.

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
