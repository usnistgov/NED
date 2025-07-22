# NED-Beta
> "Turning data into resilience one function at a time" - J.B.

#### Nonstructural Element Database
This repository provides remote hosting and version control for the development of NED, the Nonstructural Element Database. NED is a relational database that collects information from experimental, analytical, and historic performance observations of nonstructural building elements into seismic fragilities and consequence models to support building-specific seismic performance research and assessments. Currently, the project is still in its early development phase and does not yet have consequence models or data from historical events, but has collected over 1500 experimental data points and compiled a fragility data set that includes and expands upon the full FEMA P-58 nonstructural database. The experimental test data and seismic fragility are explicitly related through primary and foreign key architecture within the database to promote data transparency and reuse. Once completed, NED will be hosted on a stable and scalable web-based backend framework with restful API access points and a stand-alone GUI for use by engineers and researchers.

## Database Architecture
The goal of this project is to develop a robust and scalable database of fragility and consequence models of nonstructural building elements for seismic performance evaluation. Data is organized in a way such that each data table represents an abstract portion of the fragility model, e.g., separating observations of component performance from an experimental test from that of a fragility model and repair costs consequence models. In that way, that data is both nimble/scalable with new information and can be clearly linked back to original source data and models through explicit relational keys. The outcomes of this project will expand the applicability of performance- and recovery-based earthquake assessments, resulting in a publicly available database to support current research and building design. The figure below outlines the current portions of the database under development and future development plans.

<img width="859" height="1918" alt="ned_ERD" src="https://github.com/user-attachments/assets/ba00a466-9ce4-454d-b671-b5bcc5b4d75c" />

## Repository Organization
- **db.sqlite3** - SQL implementation of the NED database.
- **ned_app** - Django application (python) facilitating database management (e.g., model definition, etc).
- **ned_proj** - Django project settings.
- **visualization_tools** - Jupyter notebook workflows that interact with the NED database to illustrate backend interactions via python.

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

## Contributers Guide

### Setting up a Virtual Environment (optional but recommended)
Setting up a virtual environment helps to ensure you are able to setup an isolated project for using the NED database locally and avoid conflicts with other dependencies. While there are many ways to setup a virtual environment, below is an example using Python's built in `venv` module.
```
python -m venv venv      # create a virtual environment called "venv"
venv\Scripts\activate     # (On Windows) activate your virtual environment
source venv/bin/activate # (On Mac) activate your virtual environment
```

### Installing the Required Packages
Be sure that all packages below have been installed in your virtual or global environment.
```
pip install Django
pip install djangorestframework
```

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

### Making Changes to the Schema (not recommended)
Changing the Django model may cause data corruption and validations issue with the existing data. After making changes, run the following commands to apply the changes to the sql db.
```
python manage.py makemigrations
python manage.py migrate
```
---

This repository is principally developed and maintained by:

1. Dustin Cook, Research Structural Engineer
   - Engineering Laboratory, Materials and Structural Systems Division, Earthquake Engineering Group
   - @dustin-cook
   - dustin.cook@nist.gov

Please reach out with questions and comments.
