# COVERTEST: Replication Package

This repository is the replication package of the paper *"COVERTEST:
Coverage-Guided Multi-Model LLM Orchestration for Integration Test Generation
of REST APIs"*. It contains the raw output of the 270-execution campaign
reported in the paper and the scripts that turn that raw output into the tables
and figures.

The tool itself is not included here. COVERTEST is maintained in its own
repository: <https://github.com/aurimrv/covertest>.

## What is COVERTEST

COVERTEST generates executable JUnit and REST Assured integration tests for
REST APIs, using code coverage of the implementation as the signal that drives
generation. It receives an OpenAPI specification, the Java sources, a runnable
artifact of the system under test, and an optional initial test suite, and runs
a six-phase, agent-based pipeline: baseline coverage analysis, REST endpoint
mapping, LLM test generation, a compilation gate, execution with automated
repair, and coverage measurement.

The pipeline is executed once per model listed in `LLM_MODELS_GEN`, so each
model is prompted only with the code the previous ones left uncovered. The
number of stages is therefore a configuration value, not a property of the
tool. Whatever cannot be compiled or repaired is withdrawn from the build at
class or method granularity, so reported coverage comes only from tests that
genuinely execute.

Installation and usage instructions are in the tool repository.

## Repository layout

```
.
├── projects/          the five systems under test, standalone copies
│   ├── features-service/
│   ├── ncs/
│   ├── restcountries/
│   ├── scs/
│   └── spring-actuator-demo/
│
├── generated_tests/   raw output of the 270 executions
│   └── sequence_NN/run_NN/<seed>/<sut>/
│        ├── ts01_synthesis_metrics.json      per-execution totals
│        ├── NN_ts01<model>_metrics.json      per-stage metrics
│        ├── NN_..._divergency_report.md      spec-vs-implementation report
│        ├── llm_debug/                       every prompt and every response
│        ├── src/                             the generated test suite
│        └── target/                          JaCoCo and Surefire reports
│
└── analysis/          scripts that reproduce the paper's tables and figures
    ├── data/           executions.csv (270 rows), steps.csv (810 rows)
    ├── extract.py      raw JSON -> the two CSVs
    ├── make_tables.py  -> Tables 3, 4, 5
    ├── make_figures.py -> Figures 3, 4
    └── README.md       details of the analysis pipeline
```

## Quick start: reproducing the paper's numbers

The consolidated CSVs are included, so no re-execution is needed:

```bash
pip install pandas numpy scipy matplotlib
cd analysis
python3 make_tables.py     # Tables 3, 4, 5 -> stdout and tables/
python3 make_figures.py    # Figures 3, 4  -> figures/
```

To rebuild the CSVs from the raw JSON instead of using the shipped ones:

```bash
cd analysis
python3 extract.py --root ../generated_tests --out data/
```

`extract.py` also runs consistency checks on the raw data (stage-chain
continuity, cost and token reconciliation between per-stage and per-execution
totals). See `analysis/README.md` for the column reference and for the two
mis-logged records that the script repairs.

## Running the tool

COVERTEST is distributed separately, at
<https://github.com/aurimrv/covertest>, where the installation and usage
instructions are maintained. The `projects/` directory of this repository
contains the five systems under test in the exact version used in the campaign,
so they can be used directly as targets when re-running the tool.

COVERTEST is model-agnostic: it works with any endpoint compatible with the
OpenAI API or reachable through an LLM gateway. The models are plain strings in
the configuration file, so no code changes are needed to add, remove, or
reorder them.

## The demonstration campaign

The campaign reported in Section 5 of the paper covers:

| Factor | Levels |
|---|---|
| Systems under test | `features-service`, `ncs`, `restcountries`, `scs`, `spring-actuator-demo` |
| Generation models | `qwen/qwen3.7-plus`, `openai/gpt-5-mini`, `z-ai/glm-5.2` |
| Model orderings | all 6 permutations of the three models |
| Seeds | 367, 450, 767 |
| Repetitions | 3 per configuration |
| **Total** | **6 × 5 × 3 × 3 = 270 executions** |

The `sequence_NN` directories map to the orderings as follows:

| Directory | Ordering |
|---|---|
| `sequence_01` | qwen3.7-plus → gpt-5-mini → glm-5.2 |
| `sequence_02` | qwen3.7-plus → glm-5.2 → gpt-5-mini |
| `sequence_03` | gpt-5-mini → qwen3.7-plus → glm-5.2 |
| `sequence_04` | gpt-5-mini → glm-5.2 → qwen3.7-plus |
| `sequence_05` | glm-5.2 → qwen3.7-plus → gpt-5-mini |
| `sequence_06` | glm-5.2 → gpt-5-mini → qwen3.7-plus |

For every system, the initial suite `T0` was generated once with EvoMaster
5.0.2 in black-box mode, with a one-hour search budget, a fixed seed, and
`JAVA_JUNIT_4` output emitted as a single suite. Because `T0` is shared by
every configuration, the baseline cannot confound the comparisons. The repair
model was fixed to `openai/gpt-5-mini` in every configuration; sampling used
temperature 0.2 and top-p 1.0.

Across the campaign, mean instruction coverage rose from 70.84% to 90.27%. The
whole campaign consumed 128.2 million tokens over 10,740 API requests, at a
total cost of US$131.16 and 92.3 hours of pipeline time.

## Environment

The reported results were produced with Java 11.0.27, Maven 3.9.11, JaCoCo
0.8.13, JUnit 4.13.2, and REST Assured 4.5.1, on Linux. Executions were
sequential to avoid interference between instances of the system under test.
The analysis scripts need Python 3.10+ with pandas, numpy, scipy, and
matplotlib.

Note that LLM providers do not guarantee determinism even at fixed seeds, and
hosted models are revised under stable names. Re-running the campaign will
therefore not reproduce the numbers exactly; the raw per-execution data in
`generated_tests/` is the archived record of the campaign as executed.

## Third-party components

The five systems under test come from the Web Fuzzing Dataset (EMB) and remain
under their original licenses. They are included here in the exact version used
in the campaign so that the pipeline can be run end to end without reassembling
the benchmark.