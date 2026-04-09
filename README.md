# PATHWAYS: A Multi-Domain Behavioral Forensics Benchmark for Web Agents

This repository contains the code, tasks, evaluation scripts, and run logs for the PATHWAYS benchmark submitted to ICML. The benchmark evaluates web agents on **behavioral forensics** — tasks that require multi-hop UI navigation, synthesis of behavioral evidence, and principled decision-making. All evidence is embedded in raw behavioral data; no pre-written analytical conclusions are provided to the agent.

---

## Repository Structure

```
pathways_icml_submission/
├── README.md                          ← you are here
│
├── reddit/                            ← Reddit moderation benchmark
│   ├── tasks/                         ← task datasets
│   ├── task_generation/               ← scripts to regenerate tasks (new contribution)
│   ├── evaluation/                    ← benchmark runner scripts
│   ├── analysis/                      ← result analysis scripts
│   └── run_logs/                      ← actual agent run logs from the paper
│
├── shopping_admin/                    ← Magento Shopping Admin benchmark
│   ├── tasks/                         ← task datasets (v3 paper + v4 new)
│   ├── task_generation/               ← scripts to generate and inject tasks
│   ├── database/                      ← SQL files to populate the environment
│   ├── evaluation/                    ← benchmark runner scripts
│   ├── analysis/                      ← result analysis scripts
│   ├── verification/                  ← task viewer and verification report
│   └── run_logs/                      ← actual agent run logs from the paper
│
├── benchmark_core/                    ← core benchmark task JSON files
│   ├── pathways_benchmark_v2.json     ← v2 tasks (100 tasks, main paper eval)
│   ├── pathways_tasks_v3.json         ← v3 tasks (extended)
│   ├── pathways_adversarial_tasks.json← adversarial task variants
│   └── ...
│
├── results/                           ← aggregated results and paper tables
│   ├── comprehensive_metrics_output.json
│   ├── funnel_results_detailed.json
│   ├── ablation_results_detailed.json
│   ├── ablation_results_v2.json
│   ├── adversarial_analysis.json
│   └── paper_table.tex                ← LaTeX table from the paper
│
├── run_logs/                          ← primary evaluation run logs
│   ├── pathways_evidence_20260126_164024/   ← main GPT evaluation run
│   ├── pathways_evidence_20260127_*/        ← adversarial runs (gemini, gpt, qwen)
│   ├── pathways_full_20260116_022920/       ← full multi-model run
│   ├── pathways_full_20260124_164014/       ← llama evaluation run
│   └── pathways_qwen_20260117_125811/       ← Qwen evaluation run
│
└── methodology/                       ← design documents
    ├── decision_scoring_methodology.md
    ├── pathways_evaluation_methodology.md
    └── PATHWAYS_v3_Shopping_Admin_Design.md
```

---

## Environments

PATHWAYS uses two web environments from [OE-Bench](https://oebench.github.io/) / WebArena:

| Platform | URL | Description |
|---|---|---|
| Magento Shopping Admin | `http://localhost:7780` | E-commerce admin panel |
| Postmill (Reddit clone) | `http://localhost:9999` | Social media moderation platform |

### Step 1: Download and Start OE-Bench Environments

```bash
# Download the OE-Bench environment Docker images
# Follow instructions at https://oebench.github.io/ to get the tar files

# Load and start Magento Shopping Admin
docker load < shopping_admin.tar
docker run -d -p 7780:80 --name shopping_admin shopping_admin:latest

# Load and start Postmill (Reddit clone)
docker load < postmill.tar
docker run -d -p 9999:80 --name postmill postmill:latest

# Verify both are running
curl -s -o /dev/null -w "%{http_code}" http://localhost:7780   # should return 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:9999   # should return 200
```

### Step 2: Install Dependencies

```bash
pip install playwright httpx
playwright install chromium
```

---

## Shopping Admin Benchmark

### Generating and Injecting Tasks

The Shopping Admin benchmark has two task sets:
- **v3** (150 tasks, used in the paper): covers 5 categories — return_fraud, account_takeover, payment_manipulation, bulk_order_fraud, loyalty_abuse
- **v4** (150 new tasks, new contribution): covers 5 new categories — friendly_fraud_chargeback, promo_abuse, cross_account_linking, gift_card_fraud, false_item_not_received

```bash
cd shopping_admin/

# Regenerate v3 tasks and SQL (optional — pre-generated files already included)
python3 task_generation/generate_shopping_v3.py

# Regenerate v4 tasks and SQL (optional — pre-generated files already included)
python3 task_generation/generate_shopping_v4.py

# Inject task data into the running Magento container
# (This populates the database with synthetic customers, orders, and history)
python3 task_generation/inject_and_verify_v3.py \
    --sql database/pathways_v3_shopping_data.sql \
    --host localhost --port 7780
```

### Running the Evaluation

```bash
cd shopping_admin/

# Run the full benchmark (all models)
python3 evaluation/run_shopping_benchmark_v4.py \
    --benchmark tasks/pathways_v3_shopping_tasks.json \
    --output ./results_$(date +%Y%m%d)

# Run a single model
python3 evaluation/run_shopping_benchmark_v4.py \
    --benchmark tasks/pathways_v3_shopping_tasks.json \
    --model gpt \
    --output ./results_gpt

# Dry run to verify setup (no API calls, no browser)
python3 evaluation/run_shopping_benchmark_v4.py \
    --benchmark tasks/pathways_v3_shopping_tasks.json \
    --dry-run

# Available model keys: gpt, gemini, qwen32b, qwen235b, opus, grok
```

### Analyzing Results

```bash
cd shopping_admin/

# Main analysis (generates per-model, per-category breakdown)
python3 analysis/analyze_results_v6.py --results ../run_logs/pathways_evidence_20260126_164024/all_results.json

# Funnel analysis (investigation depth breakdown)
python3 analysis/analyze_results_funnel_final.py

# Ablation study analysis
python3 analysis/analyze_results_ablation.py
```

---

## Reddit Benchmark

### Task Dataset

The Reddit benchmark contains 139 tasks across 5 categories:

| Category | Tasks | Actions |
|---|---|---|
| cross_subreddit_spam | 38 | REMOVE_ALL_POSTS_AND_BAN, REMOVE_PROMOTIONAL_AND_WARN, APPROVE |
| coordinated_brigading | 25 | LOCK_THREAD_AND_REPORT, LOCK_THREAD_AND_WARN, MONITOR_AND_FLAG, APPROVE |
| user_history_context | 26 | RESPONSE_REQUIRED |
| fact_checking_source_verification | 26 | ADD_CORRECTION_COMMENT, ADD_MOD_NOTE, CONFIRM_FACTUAL, APPROVE |
| fact_checking_multimodal | 24 | ADD_CORRECTION_COMMENT, CONFIRM_FACTUAL, APPROVE |

`tasks/reddit_tasks_v2.json` is the cleaned and unified version (new contribution — unified 7→5 categories, standardized 25+ action strings to 9 canonical actions).

### Regenerating Tasks (if needed)

```bash
cd reddit/

# Clean and regenerate reddit_tasks_v2.json from raw source
python3 task_generation/clean_reddit_tasks.py
# Reads:  tasks/reddit_tasks_raw_v1.json
# Writes: tasks/reddit_tasks_v2.json
```

### Running the Evaluation

```bash
cd reddit/

# Run the full benchmark
python3 evaluation/run_reddit_benchmark.py \
    --benchmark tasks/reddit_tasks_v2.json \
    --output ./results_$(date +%Y%m%d)

# Run a single model
python3 evaluation/run_reddit_benchmark.py \
    --benchmark tasks/reddit_tasks_v2.json \
    --model gpt \
    --output ./results_gpt

# Run a specific category
python3 evaluation/run_reddit_benchmark.py \
    --benchmark tasks/reddit_tasks_v2.json \
    --category fact_checking_source_verification

# Available model keys: gpt, gemini, qwen32b, qwen235b, opus, grok
```

### Analyzing Results

```bash
cd reddit/

python3 analysis/analyze_results_comprehensive.py \
    --results ../run_logs/pathways_final_run_logs/
```

---

## Models and API Configuration

The benchmark uses [OpenRouter](https://openrouter.ai/) to access all models via a unified API. The API key is configured in the runner scripts. To use your own key:

```bash
# Edit the OPENROUTER_KEY variable at the top of the runner script:
# evaluation/run_reddit_benchmark.py      → OPENROUTER_KEY = "sk-or-v1-..."
# evaluation/run_shopping_benchmark_v4.py → OPENROUTER_KEY = "sk-or-v1-..."
```

| Key | Model |
|---|---|
| `gpt` | openai/gpt-5.2 |
| `gemini` | google/gemini-3-flash-preview |
| `qwen32b` | qwen/qwen3-vl-32b-instruct |
| `qwen235b` | qwen/qwen3-vl-235b-a22b-thinking |
| `opus` | anthropic/claude-opus-4.5 |
| `grok` | x-ai/grok-4.1-fast |

---

## Run Logs

All run logs from the paper are included under `run_logs/` (primary benchmark) and `reddit/run_logs/` / `shopping_admin/run_logs/`.

| Directory | Description | Models |
|---|---|---|
| `run_logs/pathways_evidence_20260126_164024/` | Main evaluation run | GPT |
| `run_logs/pathways_evidence_20260127_192556/` | Adversarial run | Gemini |
| `run_logs/pathways_evidence_20260127_192644/` | Adversarial run | GPT |
| `run_logs/pathways_evidence_20260127_192700/` | Adversarial run | Qwen32b |
| `run_logs/pathways_evidence_20260127_192724/` | Adversarial run | Qwen235b |
| `run_logs/pathways_full_20260116_022920/` | Full multi-model run | Gemini, GPT, others |
| `run_logs/pathways_full_20260124_164014/` | LLaMA evaluation | llama3.1-8b |
| `run_logs/pathways_qwen_20260117_125811/` | Qwen evaluation | Qwen235b |
| `shopping_admin/run_logs/` | Shopping Admin runs | Mistral, LLaMA4, OLMo |
| `reddit/run_logs/` | Reddit task runs | RD_USER tasks |

Each run log directory contains:
- `all_results.json` — aggregated results with scores, decisions, trajectories
- `run_metadata.json` — run configuration (model, tasks, benchmark file)
- `<model>_<task_id>.json` — individual task result files
- `screenshots/` — browser screenshots per step

---

## Aggregated Results

Pre-computed results are in `results/`:

| File | Description |
|---|---|
| `comprehensive_metrics_output.json` | Per-model, per-category accuracy breakdown (4 models) |
| `funnel_results_detailed.json` | Investigation funnel analysis (1200 records, GPT + Gemini) |
| `ablation_results_detailed.json` | Ablation study (GPT + Gemini) |
| `ablation_results_v2.json` | Ablation study (Qwen32b + Qwen235b) |
| `adversarial_analysis.json` | Adversarial robustness analysis |
| `paper_table.tex` | LaTeX table from the paper (Table 1) |

---

## New Contributions (Rebuttal)

The following were added in response to reviewer feedback:

1. **Shopping Admin v4 tasks** (`shopping_admin/tasks/pathways_v4_shopping_tasks.json`)  
   150 new tasks across 5 new fraud categories with an 8-action decision taxonomy.  
   Generator: `shopping_admin/task_generation/generate_shopping_v4.py`

2. **Reddit task unification** (`reddit/tasks/reddit_tasks_v2.json`)  
   Cleaned and unified 139 tasks: 7 categories → 5, 25+ action strings → 9 canonical actions, false alarm detection, accepted alternatives.  
   Cleaner: `reddit/task_generation/clean_reddit_tasks.py`
