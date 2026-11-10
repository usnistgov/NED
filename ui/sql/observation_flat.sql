-- One flat row per observation, in the shape ui/db.py queries. TEMP, so the database
-- file never stores it; run as one execute() with no params.
CREATE TEMP VIEW IF NOT EXISTS ned_app_observation_flat AS
SELECT
    o.observation_id                              AS observation_id,
    COALESCE(sp.reference_id, pr.reference_id)    AS reference_id,
    COALESCE(NULLIF(sp.name, ''), sp.label)       AS specimen,
    COALESCE(CAST(t.test_order AS TEXT), '')      AS specimen_inspection_sequence,
    sp.contributor                                AS contributor,
    sp.component_id                               AS component_id,
    sp.comp_detail                                AS comp_detail,
    sp.material                                   AS material,
    sp.size_class                                 AS size_class,
    sp.governing_design_standard                  AS governing_design_standard,
    sp.design_objective                           AS design_objective,
    sp.comp_description                           AS comp_description,
    t.test_type                                   AS test_type,
    t.loading_protocol                            AS loading_protocol,
    t.peak_test_amplitude                         AS peak_test_amplitude,
    f.location                                    AS location,
    o.legacy_prior_damage_repaired                AS prior_damage_repaired,
    o.legacy_prior_damage                         AS prior_damage,
    o.legacy_ds_rank                              AS ds_rank,
    o.ds_description                              AS ds_description,
    o.ds_class                                    AS ds_class,
    o.edp_metric                                  AS edp_metric,
    o.edp_unit                                    AS edp_unit,
    o.edp_value                                   AS edp_value,
    o.alt_edp_metric                              AS alt_edp_metric,
    o.alt_edp_unit                                AS alt_edp_unit,
    o.alt_edp_value                               AS alt_edp_value,
    o.notes                                       AS notes
FROM ned_app_observation o
JOIN ned_app_test     t  ON t.test_id      = o.test_id
JOIN ned_app_specimen sp ON sp.specimen_id = t.specimen_id
JOIN ned_app_program  pr ON pr.program_id  = sp.program_id
JOIN ned_app_facility f  ON f.label        = sp.facility_id;
