# Nonstructural Element Database (NED)

An interactive data explorer for seismic fragility and consequence modeling of nonstructural building components. NED provides curated experimental data, fragility models, and research references to support loss estimation frameworks like FEMA P-58.

![Streamlit](https://img.shields.io/badge/Streamlit-1.56-red)
![Python](https://img.shields.io/badge/Python-3.11+-blue)

## What's in the database

| Data type | Count | Description |
|---|---|---|
| Components | 71 | Nonstructural building component types classified by NISTIR taxonomy |
| Experiments | 2,393+ | Individual experimental test observations with damage state classifications |
| Fragility Models | 511 | Lognormal fragility models with curve parameters (median, beta) per damage state |
| Fragility Curves | 1,008 | Individual damage-state curves within fragility models |
| References | 63 | Research publications and studies |

## Running locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. The SQLite database (`backend/db.sqlite3`) is bundled in the repo — no external database setup is needed.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DB_PATH` | `backend/db.sqlite3` | Path to the SQLite database file |
| `APP_USERNAME` | `ned` | Login username |
| `APP_PASSWORD` | `ned2026` | Login password |

The app requires a login before any content is visible. The defaults (`ned` / `ned2026`) work out of the box for local development. To use different credentials locally, set the variables before running:

```bash
export APP_USERNAME=myuser
export APP_PASSWORD=mysecretpassword
streamlit run app.py
```

Always override the defaults before deploying to a shared environment. See [DEPLOYMENT.md](deploy/DEPLOYMENT.md) for how to pass these as Cloud Run environment variables.

## App pages

### Home

Project overview with aggregate statistics (total experiments, fragility models, etc.) and a description of the database architecture.

### Components

Browse all 71 component types. Components follow a four-level NISTIR taxonomy:

**Major Group → Group → Element → Subelement**

For example: *Mechanical, Electrical, Plumbing → Fire Protection → Sprinkler Systems → Horizontal Piping*

Users can filter by Major Group and Group using sidebar dropdowns, or search by component ID, name, or element classification. Each component links to a detail page showing its associated fragility models and experimental data, both downloadable as CSV.

### Fragility Model Detail

Displays a single fragility model's metadata — material, size class, component description, and reference citation with DOI link — along with all its damage-state curves (median, beta, EDP metric/unit, basis, number of observations).

### Experiment Detail

Shows all metadata for an individual test observation: specimen identifier, test type, loading protocol, EDP value and metric, damage state rank and classification, damage description, and prior damage history. Links back to the source reference.

### Data Dictionary

Renders the human-readable data dictionary (`assets/data_dictionary.md`): a field-by-field description of the main database tables, including definitions, accepted data types, bounds, and the exact values allowed in choice fields.

## Deep linking

The app supports query-parameter navigation for bookmarking and sharing:

| URL pattern | Page |
|---|---|
| `?component=<id>` | Component detail |
| `?fragility_model=<id>` | Fragility model detail |
| `?experiment=<id>` | Experiment detail |

## Database schema

All data lives in a single SQLite file. The app is strictly read-only.

### Core tables

**ned_app_component** — Central component registry. Each row is a component type classified by the four-level NISTIR taxonomy (`major_group`, `group`, `element`, `subelement`) with a human-readable `name` and formatted `component_id`.

**ned_app_reference** — Research publications. Stores author, title, year, study type, and a `csl_data` column containing full CSL-JSON citation metadata.

**ned_app_experiment** — Individual test observations. Each record ties to one component and one reference, and captures the specimen, test type, loading protocol, engineering demand parameter (EDP metric, unit, value), damage state rank/class, and a free-text damage description.

**ned_app_fragilitymodel** — Fragility model definitions. Links to a component and reference, with fields for P-58 fragility ID, material, size class, and component description.

**ned_app_fragilitycurve** — Lognormal curve parameters for each damage state within a fragility model: `median`, `beta`, `edp_metric`, `edp_unit`, `basis`, and `num_observations`.

### Bridge tables

- **ned_app_componentfragilitymodelbridge** — Many-to-many link between components and fragility models.
- **ned_app_experimentfragilitymodelbridge** — Many-to-many link between experiments and fragility models.

### Taxonomy reference

`backend/nistir_labels.json` maps NISTIR taxonomy codes to human-readable labels across the full four-level hierarchy.

## Project structure

```
├── app.py                      # Entry point: page config, CSS, auth gate, routing
├── auth.py                     # Login form and credential check
├── db.py                       # All SQLite query functions
├── styles.py                   # Global CSS injected at startup
├── utils.py                    # Shared UI helpers (fmt, attr, strip_prefix)
├── views/                      # One module per page
│   ├── home.py
│   ├── components.py
│   ├── component_detail.py
│   ├── fragility_model.py
│   ├── experiment.py
│   └── data_dictionary.py
├── assets/
│   ├── logo.png                # App logo
│   └── data_dictionary.md      # Human-readable schema reference (rendered by data_dictionary.py)
├── backend/                    # Files synced from the backend repo — do not edit here
│   ├── db.sqlite3              # SQLite database
├── .streamlit/
│   └── config.toml             # Streamlit config (light theme)
└── requirements.txt            # Python dependencies
```

## Dependencies

- **streamlit** 1.56.0 — Web framework
- **pandas** 2.1.4 — Data manipulation and SQL query results
- **sqlite3** — Database access (Python standard library)
