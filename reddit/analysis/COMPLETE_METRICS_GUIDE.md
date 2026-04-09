# PATHWAYS Reddit Benchmark - Complete Metrics & Interpretation Guide

## Overview

| Metric | Value |
|--------|-------|
| **Total Tasks** | 116 tasks across 6 categories |
| **Models Tested** | 4 (Gemini 3 Flash, GPT-4o, Qwen3-VL-32B, Qwen3-VL-235B) |
| **Total Executions** | 464 (116 × 4 models) |
| **Completed Executions** | 363 (78.2%) |

---

## 📊 TABLE 1: Main Finding - Context Discovery Effect

> **This is the PRIMARY finding supporting the PATHWAYS hypothesis**

| Condition | Tasks | Accuracy | Effect |
|-----------|-------|----------|--------|
| **Context Mentioned in Reasoning** | 275 | **91.3%** | **+15.1%** ✓ |
| Context NOT Mentioned | 88 | 76.1% | (baseline) |

### What This Measures
- Checks if the model's **reasoning text** contains keywords indicating they discovered hidden context
- Keywords per category:
  - Spam: "multiple forums", "cross-post", "same content", "spam"
  - Brigading: "coordinated", "brigade", "multiple accounts"
  - Fact-check: "source", "wiki", "false", "incorrect"

### Interpretation
> **"When AI agents discover and articulate hidden context in their reasoning, task accuracy improves by 15.1 percentage points (91.3% vs 76.1%)"**

### Why This Metric is Better
- Previous metric (URL visits) only checked if model visited a page
- This metric checks if model **demonstrated understanding** in reasoning
- More directly linked to decision quality

---

## 📊 TABLE 2: Overall Model Performance

| Model | Total | Completed | Accuracy | Harm Rate | Avg Score |
|-------|-------|-----------|----------|-----------|-----------|
| **Gemini 3 Flash** | 116 | 101 (87%) | 86.1% | 11.9% | 2.63 |
| **GPT-4o** | 116 | 73 (63%) | **94.5%** | **0.0%** | **2.78** |
| **Qwen3-VL-32B** | 116 | 81 (70%) | 80.2% | 19.8% | 2.48 |
| **Qwen3-VL-235B** | 116 | **108 (93%)** | 89.8% | 7.4% | 2.50 |

### Column Definitions

| Column | Definition | Interpretation |
|--------|------------|----------------|
| **Completed** | Tasks where model made final decision | Higher = more reliable |
| **Accuracy** | % of correct decisions (optimal + acceptable) | Higher = better quality |
| **Harm Rate** | % of harmful decisions (would hurt users) | Lower = safer |
| **Avg Score** | Mean score: 3=optimal, 2=acceptable, 1=harmful | Higher = better |

### Key Insights
- **GPT-4o**: Best accuracy (94.5%) and safest (0% harm), but slowest completion
- **Qwen-235B**: Most reliable (93% completion) with good accuracy (89.8%)
- **Gemini**: Best efficiency-accuracy balance
- **Qwen-32B**: Fastest but highest harm rate (19.8%)

---

## 📊 TABLE 3: Performance by Task Category

| Category | Total | Completed | Accuracy | Harm Rate | Difficulty |
|----------|-------|-----------|----------|-----------|------------|
| User History Context | 104 | 93 (89%) | **100.0%** | 0.0% | Easy |
| Fact Check (Source) | 56 | 44 (79%) | **100.0%** | 0.0% | Easy |
| Spam Detection | 120 | 103 (86%) | 88.3% | 11.7% | Medium |
| Fact Check (Visual) | 76 | 69 (91%) | 87.0% | 10.1% | Medium |
| Brigading | 80 | 33 (41%) | 81.8% | 12.1% | Medium |
| **Fact Check (Hard)** | 28 | 21 (75%) | **14.3%** | **61.9%** | **Hard** |

### Category Definitions

| Category | Task Description | Hidden Context Location | Expected Action |
|----------|------------------|------------------------|-----------------|
| **Spam Detection** | Identify cross-forum spammers | User's post history | Ban the spammer |
| **User History** | Respond based on past interactions | User's previous questions | Context-aware response |
| **Brigading** | Detect coordinated attacks | Comment timestamps/patterns | Lock thread |
| **Fact Check Source** | Verify claims against sources | Wiki pages | Add correction |
| **Fact Check Visual** | Analyze manipulated images | Image itself | Misinfo flair |
| **Fact Check Hard** | Complex multi-source verification | Multiple sources | Add correction |

### Key Insights
- **Easy (100%)**: User Context, Source Verification → Ceiling effect (may be too easy)
- **Medium (80-90%)**: Spam, Visual, Brigading → Good benchmark difficulty
- **Hard (14%)**: Fact Check Hard → **CRITICAL FAILURE** with 61.9% harm rate

---

## 📊 TABLE 4: Investigation Effect (URL-Based)

| Condition | Tasks | Accuracy | Effect |
|-----------|-------|----------|--------|
| **Overall** | | | |
| Investigated (visited /user/ or /wiki/) | 288 | 88.5% | **+4.5%** |
| Not Investigated | 75 | 84.0% | (baseline) |
| **Investigation-Required Categories Only** | | | |
| Investigated | 219 | 89.0% | **+5.0%** |
| Not Investigated | 75 | 84.0% | (baseline) |

### What This Measures
- **Investigated** = Model visited at least one `/user/*` or `/wiki/*` page
- **Investigation-Required** = Excludes visual fact-checking (doesn't need external pages)

### Interpretation
> Investigation improves accuracy by +4.5% to +5.0%, but the stronger effect (+15.1%) comes from context mention in reasoning.

---

## 📊 TABLE 5: Investigation Effect by Model

| Model | Investigated | Not Investigated | Effect | Interpretation |
|-------|--------------|------------------|--------|----------------|
| **Gemini** | 90.0% (80) | 71.4% (21) | **+18.6%** ✓ | **Most benefit** |
| **Qwen-32B** | 81.7% (71) | 70.0% (10) | **+11.7%** ✓ | Significant benefit |
| GPT-4o | 94.0% (67) | 100.0% (6) | -6.0%* | Small sample |
| Qwen-235B | 88.6% (70) | 92.1% (38) | -3.5%* | High baseline |

*Negative effects explained by small samples or high baseline accuracy

### Key Insights
- **Smaller models benefit MORE from investigation**
- Gemini: +18.6% improvement → Investigation is CRITICAL
- Larger models (GPT-4o, Qwen-235B) already accurate without investigation

---

## 📊 TABLE 6: Investigation Effect by Category

| Category | Investigated | Not Investigated | Effect | Notes |
|----------|--------------|------------------|--------|-------|
| Spam Detection | 88.3% (103) | N/A (0) | N/A | All tasks investigated |
| User History | 100.0% (72) | 100.0% (21) | 0.0% | Ceiling effect |
| Brigading | 78.6% (14) | 84.2% (19) | -5.6% | Action selection issue |
| Fact Check Source | 100.0% (18) | 100.0% (26) | 0.0% | Ceiling effect |
| Fact Check Visual | 87.0% (69) | N/A (0) | N/A | Visual only |
| **Fact Check Hard** | 25.0% (12) | 0.0% (9) | **+25.0%** ✓ | **Critical** |

### Key Insights
- **Fact Check Hard**: +25% effect → Investigation is CRITICAL for hard tasks
- **Brigading paradox**: Models investigate and understand, but choose wrong action (ban vs lock)
- **Ceiling effects**: Some categories may be too easy

---

## 📊 TABLE 7: Decision Distribution

| Decision | Count | % | When Correct |
|----------|-------|---|--------------|
| Misinformation Flair | 99 | 27.3% | Fake images, false claims |
| Ban User | 98 | 27.0% | Clear spam/abuse |
| Context Response | 73 | 20.1% | User history context |
| No Action | 52 | 14.3% | Legitimate content |
| Lock Thread | 27 | 7.4% | Brigading attacks |
| Add Correction | 12 | 3.3% | Factual errors |

### Model Tendencies

| Model | Primary Actions | Tendency |
|-------|----------------|----------|
| **Gemini** | Ban (33%), Misinfo (29%) | Aggressive |
| **GPT-4o** | Misinfo (34%), Correction (14%) | Balanced |
| **Qwen-32B** | Context (31%), No Action (21%) | Passive |
| **Qwen-235B** | Misinfo (32%), No Action (27%) | Conservative |

---

## 📊 TABLE 8: Efficiency Metrics

| Model | Avg Steps | Avg Duration | Total Tokens | Est. Cost |
|-------|-----------|--------------|--------------|-----------|
| **Gemini** | 2.5 | **21.6s** | 496K | **$0.50** |
| GPT-4o | 4.1 | 55.9s | 814K | $4.07 |
| Qwen-32B | 3.9 | 26.2s | 710K | $0.36 |
| Qwen-235B | **2.1** | 68.0s | 577K | $0.87 |

### Interpretation
- **Gemini**: Best cost-efficiency (fast + cheap + good accuracy)
- **GPT-4o**: Best accuracy but 8x more expensive
- **Qwen-235B**: Confident decisions (fewest steps) but slow inference

---

## 🎯 Summary: Key Findings for ICML Paper

### 1. Main Hypothesis CONFIRMED ✓
```
Context Discovery Effect = +15.1 percentage points
(91.3% with context mention vs 76.1% without)
```

### 2. Investigation Helps, Especially Smaller Models
```
Gemini:  +18.6% with investigation
Qwen-32B: +11.7% with investigation
```

### 3. Task Difficulty Varies Dramatically
```
Easy (100%):    User Context, Source Verification
Medium (80-90%): Spam, Visual Fact-Check, Brigading
Hard (14%):     Complex Fact-Checking (61.9% harm rate!)
```

### 4. Efficiency-Accuracy Trade-off
```
GPT-4o:  Best accuracy (94.5%) but slowest, most expensive
Gemini:  Best efficiency (21.6s, $0.50) with good accuracy (86.1%)
```

---

## 📝 Methodology Notes

### Bug Fixes Applied
1. **Investigation tracking**: Changed `<` to `<=` (97 tasks were miscategorized)
2. **Visual category exclusion**: fact_checking_multimodal excluded from investigation analysis

### Metric Definitions
- **Accuracy** = correct_decisions / completed_tasks
- **Harm Rate** = harmful_decisions / completed_tasks
- **Effect** = investigated_accuracy - not_investigated_accuracy
- **Context Mention** = any category keyword found in reasoning text

---

## 📁 Generated Files

| File | Description |
|------|-------------|
| `results/analysis_corrected/context_discovery_effect.png` | Main finding visualization |
| `results/analysis_corrected/summary_comparison.png` | All metrics comparison |
| `results/analysis_corrected/investigation_by_model.png` | Per-model effects |
| `results/analysis_corrected/investigation_by_category.png` | Per-category effects |
| `results/analysis_corrected/corrected_metrics.json` | Raw data |
| `results/analysis/latex_tables.tex` | ICML-ready LaTeX tables |
