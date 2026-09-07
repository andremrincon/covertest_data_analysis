# ANOMTOOL replication package -- analysis scripts

This folder reproduces Tables 3-5 and Figures 3-4 of the AST 2027 paper
("ANOMTOOL: Coverage-Guided Multi-Model LLM Orchestration for Integration
Test Generation of REST APIs") from the raw per-execution data of the
270-execution campaign.

## Pipeline

```
generated_tests/                         (raw output of ANOMTOOL, not
  sequence_01/run_01/367/features-.../     included here -- see below)
    ts01_synthesis_metrics.json
    00_..._metrics.json
    01_..._metrics.json
    02_..._metrics.json
  ...
        |
        v  extract.py
data/executions.csv   (270 rows, one per execution)
data/steps.csv        (810 rows, one per generation stage)
        |
        v  make_tables.py           v  make_figures.py
tables/table3_*.csv/.tex     figures/fig03_coverage_evolution.pdf/.png
tables/table4_*.csv/.tex     figures/fig04_gain_by_position.pdf/.png
tables/table5_*.csv/.tex
```

`data/executions.csv` and `data/steps.csv` are included pre-built in this
package, so `make_tables.py` and `make_figures.py` can be run immediately
without the raw JSON. `extract.py` is provided for full end-to-end
reproducibility, in case the raw `generated_tests/` tree is also released.

## Quick start

```bash
pip install pandas numpy scipy matplotlib

# Uses the pre-built data/executions.csv and data/steps.csv:
python3 make_tables.py
python3 make_figures.py
```

Both scripts print their output to stdout in addition to writing files, so
you can check the numbers against the PDF without opening anything else.

## Rebuilding the CSVs from raw data

If you have the raw `generated_tests/` directory (see the directory layout
above -- it is one `ts01_synthesis_metrics.json` plus three per-stage
`NN_..._metrics.json` files per execution, for 270 executions):

```bash
python3 extract.py --root /path/to/generated_tests --out data/
```

This re-derives `executions.csv` and `steps.csv` directly from the JSON,
and runs a battery of consistency checks (stage-chain continuity, i.e.
stage *k*'s final coverage must equal stage *k+1*'s initial coverage;
cost/token reconciliation between the per-stage and per-execution totals)
printed at the end of the run.

## Known data issue

Two of the 270 raw `ts01_synthesis_metrics.json` files
(`sequence_06/run_01/450/features-service` and
`sequence_06/run_03/767/features-service`) have their **first-stage**
metrics file overwritten by a retried run, which corrupts only `C1` for
those two executions (`T0`, `C2`, and `C3` are unaffected). The other
seven sibling runs of the same (sequence, project) cell agree exactly on
`C1 = 80.96` for that cell, which is the value `extract.py` substitutes by
default.

- `extract.py --repair` (default): applies this substitution. This is the
  version whose numbers match the published tables exactly.
- `extract.py --no-repair`: keeps the raw (corrupted) `C1` for those two
  rows, for a sensitivity check. The `flagged` column in both CSVs marks
  the two affected executions either way, so you can filter them out
  entirely if you prefer to simply exclude rather than repair
  (`df[~df.flagged]`, n = 268 executions / 804 steps).

## Files

| File | Produces | Reads |
|---|---|---|
| `extract.py` | `data/executions.csv`, `data/steps.csv` | raw `generated_tests/` |
| `make_tables.py` | `tables/table{3,4,5}_*.csv` and `.tex` | `data/*.csv` |
| `make_figures.py` | `figures/fig0{3,4}_*.pdf` and `.png` | `data/*.csv` |

## Column reference

**`executions.csv`** (one row per execution, 270 rows):

| Column | Meaning |
|---|---|
| `sequence`, `seq_num` | model-ordering sequence (`sequence_01`..`sequence_06`) |
| `run`, `seed` | replication run and EvoMaster/LLM seed |
| `project` | SUT name |
| `seq_label`, `m1`/`m2`/`m3` | model order, e.g. `qwen3.7-plus -> gpt-5-mini -> glm-5.2` |
| `T0`, `C1`, `C2`, `C3` | instruction coverage (%) before the campaign and after each stage |
| `gain` | `C3 - T0` |
| `time_min`, `tokens`, `cost`, `requests` | totals for the full 3-stage execution |
| `flagged` | `True` for the two executions affected by the known data issue |

**`steps.csv`** (one row per generation stage, 810 rows = 270 x 3):

| Column | Meaning |
|---|---|
| `position` | 1, 2, or 3 -- position of this model in the ordering |
| `model` | generation model used at this stage |
| `init`, `fin`, `gain` | coverage before/after this stage and the gain |
| `tokens`, `cost`, `requests`, `time_min` | totals for this stage only |
