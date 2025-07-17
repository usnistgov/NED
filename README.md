# NED-Beta
> "Turning data into resilience one function at a time" - J.B.

#### Nonstructural Element Database
This repository provides remote hosting and version control for the development of NED, the Nonstructural Element Database. NED is a relational database that collects information from experimental, anayltical, and historic performance observations of nonstructural building elements into seismic fragilities and consequence models to support building-specific seismic performance research and assessments. Currenlty, the project is still in its early development phase and does not yet have consequence models or data from historical events, but has collected over 1500 expermental data points and compiled a fragility data set that includes and expands upon the full FEMA P-58 nonstructural database. The experimental test data and seismic fragility are explictitly realate through primary and foreign key architecture within the database to promote data transparency and reuse. Once completed, NED will be hosted on a stable and scalable web-based backend framework with restful API access points and a stand alone GUI for use by engineers and researchers.

## Database Architecture
The goal of this project is to develop a robust and scalable database of fragility and consequence models of nonstructural building elements for seismic performance evaluation. Data is organized in a way such that each data table represents an abtract portion of the fragility model, e.g., serperating observations of component performance from an experimentantal test from that of a fragility model and repair costs consequence models. It that way, that data is both nimble/scalable with new information and can be clearly linked back to original source data and models through explicit relational keys. The outcomes of this project will expand the applicability of performance- and recovery-based earthquake assessments, resulting in a publicly available database to support current research and building design. The figure below outlines the current portions of the database under development and future development plans.
 
<img width="3287" height="905" alt="ned_ERD" src="https://github.com/user-attachments/assets/dfba505e-a3d0-4797-98fb-fbcd8c9ef61a" />

## Repository Organization
- **db.sqlite3** - SQL implementation of the NED database.
- **ned_app** - Django application (python) facilitating database management (e.g., model definition, etc).
- **ned_proj** - Django project settings.
- **visualization_tools** - Jupyter notebook workflows that interact with the NED database to illustrate backend interactions via python.

### Data Schema
Model and field descriptions are provided in the docsigns in ned_app/models.py. The overview below provides a bried description of two of the fields found in the experiment model.

#### Component Subcategorization Hierarchy
To categorize building components, we rely on the UNIFORMAT II element classification system (NISTIR 6389). However, this system only classifies nonstructural components at a high level, and further detail is needed to adequately separate different types of components within each category for the purpose of assessing building performance.  Therefore, we propose a new subcategorization hierarchy consisting of four nested component attributes:
-	**Child Attribute 1: Connection Detail** – Describes the specific type of installation or connection type of the component, such as perimeter-fixed vs back-braced ceilings.
-	**Child Attribute 2: Material** – Describes a general grouping of components based on material, i.e., light weight vs heavy weight ceiling tiles or CPVC vs iron sprinkler pipes.
-	**Child Attribute 3: Size Class** - Describes a general grouping of components based on size, i.e., large gridded area of ceiling tiles or specific equipment size.
  
The purpose of the component subcategorization is to provide further structured detail to end users who use the collected data for fragility development. Each child attribute is only nested under the parent component category attribute; no explicit hierachy exists between child attribites and not all subcategorization layers need to be assigned if they are not applicable. Consistent naming, case, and spelling schemes should be used when populating subcategorization attributes. Reviewers should review the Sweets MasterFormat construction products database to familiarize themselves with general component taxonomy and terminology prior to developing subcategorization hierarchies for particular component types.

#### DS Class
To provide a structured detail of observed damage attributes, we propose a DS Class attribute consisting of the possible mutually exclusive classifications: 
-	**No damage**: no change in state was observed from the test.
-	**Inconsequential Damage**: (aesthetic) damage was observed but is unlikely to require repair or impact system operation (no action required). E.g., if the component was hidden would the building user ever know there was a problem? Or would the building performance be affected in any way? 
-	**Consequential Damage**: May require repair or impact system operation (observable and requires action).

![image](https://github.com/user-attachments/assets/b9f4a4bd-3083-4028-bc7b-dba06b1f3dd0)

The purpose of the DS Class attributes is to provides a first-pass structured grouping of observed damage to aid in later fragility development. However, we recognize that any grouping of damage states introduced subjectiveness into the process. Therefore, our goal is to implement as little subjectiveness as possible while still providing useful structured data for later users of the database.  This attributes simply acts to separate consequential damage from inconsequential damage. Further separation of consequential damage into multiple damage states is an attribute of the damage state itself and not the initial observation of damage and is therefore up to the fragility developer to refine. 

All observations of damage in the database are assigned into one of the three aforementioned DS classes; if for some reason a damage state class cannot be identified by the reviewer, it should be flagged as “unknown”. When in doubt, we err towards assigning observed damage as consequential, to allow the later fragility developers the option to decide whether or not to include the observation in their fragility development.

## Setting up the Django App
To set up the Djago app to intialize and interact with the sqlite NED database, first set up your virtual environment and then run the commands below to create the sqlite database from the Django model
```
python manage.py makemigrations
python manage.py migrate
```
## Adding data to the database
Data can be added to the database locally by either of the two methods
1) Lauch the Django server and add data using the Django admin interface
2) Configure the json files in `resources/data` and run the following command:
```
python manage.py ingest
```
>Example json files can be found in `resources/example_data`

## Launch the Django Admin
To launch and take advantage of the administrative interface, run the web server:
```
python manage.py runserver
```
Then, in a browser, launch the URL: http://localhost:8000/admin/


>Note, you may need to set up your own admin username and password by running the following command*
```
python manage.py createsuperuser
```

### Tip on virtual environment
For running python locally, I like to use visual studio code with the DB viewer extension, and set up the virtual environment by running the following commands
```
-m venv venv         # create a virtual environment called "venv"
venv\Sripts\activate # activate your virtual environmnet
pip install Django   # make sure the Django library is installed 
```

---

This repository is principally developed and maintained by:

1. Dustin Cook, Reserach Structural Engineer
   - Engineering Laboratory, Materials and Structural Systems Division, Earthquake Engineering Group
   - @dustin-cook
   - dustin.cook@nist.gov

Please reach out with questions and comments.
