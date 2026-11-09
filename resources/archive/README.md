# Archive

`observation_id_map.json` maps each observation's old `exp…` id, from before the
Experiment split, to its `observation_id`. Use it to translate an old id, such as one in
a published `?experiment=` link or a citation, to the current record.

The map is as of commit `46157fa` (tag `observation-split-lossless`), where the checks
proving the split lost nothing last ran. Later relabels don't update it, so an
`observation_id` may have changed since; the git history of `resources/data/` shows how.
