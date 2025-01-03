# NED-Beta
> "Turning data into resilience one function at a time" - J.B.

#### Nonstructural Element Database
This repository provides remote hosting and version control for the development of NED, the Nonstructural Element Database. NED is a relational database that collects information from experimental, anayltical, and historic performance observations of nonstructural building elements into seismic fragilities and consequence models to support building-specific seismic performance research and assessments. Currenlty, the project is still in its early development phase and does not yet have consequence models or data from historical events, but has collected over 1500 expermental data points and compiled a fragility data set that includes and expands upon the full FEMA P-58 nonstructural database. The experimental test data and seismic fragility are explictitly realate through primary and foreign key architecture within the database to promote data transparency and reuse. Once completed, NED will be hosted on a stable and scalable web-based backend framework with restful API access points and a stand alone GUI for use by engineers and researchers.

## Database Architecture
The goal of this project is to develop a robust and scalable database of fragility and consequence models of nonstructural building elements for seismic performance evaluation. Data is organized in a way such that each data table represents an abtract portion of the fragility model, e.g., serperating observations of component performance from an experimentantal test from that of a fragility model and repair costs consequence models. It that way, that data is both nimble/scalable with new information and can be clearly linked back to original source data and models through explicit relational keys. The outcomes of this project will expand the applicability of performance- and recovery-based earthquake assessments, resulting in a publicly available database to support current research and building design. The figure below outlines the current portions of the database under development and future development plans.
 
![image](https://github.com/user-attachments/assets/bdc7e08a-554e-4cfc-9a85-e0cfb10a2cad)

## Repository Organization
- **data** - database tables. Currently implmented as csv tables with attributes defined as column headers.
- **scehma** - data schema for each table in the *data* directory. Currenlty implemented as json files that provide the name, datatype, and description of each attribute (column) within each csv data table.
- **visualization** - Juptyer notebook visualization and data interfacing scripts. Low-code alternative for developing GUI interactions. These scripts are usefull if you want to explore and visualize what data is available within the current database.

### Data Tables
- **db_experiment.csv** - Database containing observations of damage from experimental tests of nonstructural building components. Each database entry represents a sigle test of a given specimen (e.g., five different tests of a particular partion wall speciment represents five seperate entries in the table).
- **db_fragility.csv** - Database containing seismic fragilities of nonstrcural building components. Each database entry represents a fragility model of an individual damage state (e.g., a FEMA P-58 fragility with three damage states would use three rows in this database).
- **db_nistir.csv** - NIST IR Uniformat II Element Classification System. https://www.nist.gov/publications/uniformat-ii-elemental-classification-building-specifications-cost-estimating-and-cost
- **db_reference.csv** - Database containing references of experimental programs used to populate *db_experiment.csv*.
- **db_relate_exp_frag.csv** - Relational database table that develops a many-to-many relationship between experimental observations and seismic fragilities.

### Data Schema
The following section provides a detailed description of several data attributes within the database. General descrptions of all attributes can be found in the *schema* subdirectory.

#### Component Subcategorization Hierarchy
To categorize building components, we rely on the UNIFORMAT II element classification system (NISTIR 6389). However, this system only classifies nonstructural components at a high level, and further detail is needed to adequately separate different types of components within each category for the purpose of assessing building performance.  Therefore, we propose a new subcategorization hierarchy consisting of four nested component attributes:
-	**Child Attribute 1: Component Subtype** - Describes the major subgrouping of components within the NISTIR class. Can separate full system tests from individual components tests, or major types of components like full height from partial height walls. 
-	**Child Attribute 2: Connection Detail** – Describes the specific type of installation or connection type of the component, such as perimeter-fixed vs back-braced ceilings.
-	**Child Attribute 3: Material Class** – Describes a general grouping of components based on material, i.e., light weight vs heavy weight ceiling tiles or CPVC vs iron sprinkler pipes.
-	**Child Attribute 4: Size Class** - Describes a general grouping of components based on size, i.e., large gridded area of ceiling tiles or specific equipment size.

![image](https://github.com/user-attachments/assets/5f4af1ad-7a57-41d7-97ce-d86d7de96565)

The purpose of the component subcategorization is to provide further structured detail to end users who use the collected data for fragility development. Each child attribute is only nested under the parent component category attribute; no explicit hierachy exists between child attribites and not all subcategorization layers need to be assigned if they are not applicable. Cnsistent naming, case, and spelling schemes should be used when populating subcategorization attributes. Reviewers should review the Sweets MasterFormat construction products database to familiarize themselves with general component taxonomy and terminology prior to developing subcategorization hierarchies for particular component types.

#### DS Class
To provide a structured detail of observed damage attributes, we propose a DS Class attribute consisting of the possible mutually exclusive classifications: 
-	**No damage**: no change in state was observed from the test.
-	**Inconsequential Damage**: (aesthetic) damage was observed but is unlikely to require repair or impact system operation (no action required). E.g., if the component was hidden would the building user ever know there was a problem? Or would the building performance be affected in any way? 
-	**Consequential Damage**: May require repair or impact system operation (observable and requires action).

![image](https://github.com/user-attachments/assets/b9f4a4bd-3083-4028-bc7b-dba06b1f3dd0)

The purpose of the DS Class attributes is to provides a first-pass structured grouping of observed damage to aid in later fragility development. However, we recognize that any grouping of damage states introduced subjectiveness into the process. Therefore, our goal is to implement as little subjectiveness as possible while still providing useful structured data for later users of the database.  This attributes simply acts to separate consequential damage from inconsequential damage. Further separation of consequential damage into multiple damage states is an attribute of the damage state itself and not the initial observation of damage and is therefore up to the fragility developer to refine. 

All observations of damage in the database are assigned into one of the three aforementioned DS classes; if for some reason a damage state class cannot be identified by the reviewer, it should be flagged as “unknown”. When in doubt, we err towards assigning observed damage as consequential, to allow the later fragility developers the option to decide whether or not to include the observation in their fragility development.

---

This repository is principally developed and maintained by:

1. Dustin Cook, Reserach Structural Engineer
   - Engineering Laboratory, Materials and Structural Systems Division, Earthquake Engineering Group
   - @dustin-cook
   - dustin.cook@nist.gov

Please reach out with questions and comments.
