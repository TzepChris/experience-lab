# v0.1 artifact files

Authored report: [`EXPERIMENTAL_REPORT.md`](EXPERIMENTAL_REPORT.md).

Generated from saved summaries (do not edit by hand):

- [`tables.md`](tables.md)
- [`holdout_stats.json`](holdout_stats.json)
- [`xor_trace.json`](xor_trace.json)
- [`versions.json`](versions.json)
- [`figures/fig1_map_later_cost.png`](figures/fig1_map_later_cost.png)
- [`figures/fig2_map_delta_c_minus_a.png`](figures/fig2_map_delta_c_minus_a.png)
- [`figures/fig3_paired_cell_outcomes.png`](figures/fig3_paired_cell_outcomes.png)

Rebuild without rerunning A/B/C:

```powershell
.\.venv\Scripts\python.exe -m experience_lab.cli artifact --holdout results/checkpoint_geometry_holdout --development results/checkpoint_ul_stopping --output docs/v0.1
```
