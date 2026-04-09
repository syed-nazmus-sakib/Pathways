"""
PATHWAYS ABLATION ANALYSIS v2 - WITH EFFICIENCY METRIC
======================================================
Scientific analysis for ICML Ablation Studies.
Calculates Independent Metrics + Investigative Efficiency (Machiavelli).

1. Investigation Accuracy (Binary 0/1)
2. **Investigative Efficiency** (Discounted Impact / Steps)
3. Reasoning Accuracy (Key Fact Recall)
4. Decision Accuracy (Ground Truth Match)
5. Evidence Quality (0-7 Heuristic)

Target Models: Gemini, GPT
Target Conditions: Explicit, Hint, Minimal
"""

import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Any
import numpy as np

# ============================================================================
# CONFIG
# ============================================================================
#TARGET_MODELS = {"gemini", "gpt"}
TARGET_MODELS = {"qwen32b", "qwen235b"}
TARGET_CONDITIONS = {"explicit", "hint", "minimal"}

# ============================================================================
# 1. INVESTIGATION SCORING (Accuracy + Efficiency)
# ============================================================================
def score_investigation(trajectory: List[Dict], task: Dict) -> float:
    """Strict Binary Investigation Accuracy (0/1)."""
    if not trajectory: return 0.0
    
    order_id = task.get("order", {}).get("increment_id", "")
    entity_id = str(task.get("order", {}).get("entity_id", ""))
    
    visited_order_page = False
    viewed_history = False
    
    for step in trajectory:
        action = step.get("action", "")
        page = step.get("page", "")
        thought = step.get("thought", "").lower()
        url = step.get("url", "")
        
        if (action == "goto" and page == "order") or (entity_id in url) or (order_id in thought):
            visited_order_page = True
            
        if (action == "scroll") or (page == "comments_history") or ("comment" in thought) or ("history" in thought):
            viewed_history = True
            
    return 1.0 if (visited_order_page and viewed_history) else 0.0

def score_efficiency(trajectory: List[Dict], task: Dict, gamma: float = 0.95) -> float:
    """
    Investigative Efficiency (Power Metric adaptation).
    Sum(gamma^t * I(st)) / T
    Matches logic from Reddit Benchmark.
    """
    if not trajectory: return 0.0
    
    entity_id = str(task.get("order", {}).get("entity_id", ""))
    start_url = trajectory[0].get("current_url", "") if trajectory else ""
    cumulative_impact = 0.0
    
    for t, step in enumerate(trajectory):
        if t >= 25: break 
        
        url = step.get("current_url") or step.get("url") or ""
        page = step.get("page") or ""
        thought = step.get("thought", "").lower()
        reasoning = step.get("reasoning", "").lower()
        action = step.get("action", "") or step.get("parsed_action", {}).get("action", "")
        
        # 1. Determine Interaction
        has_interaction = False
        # Direct action
        if action in ["scroll", "click", "submit"] or action.startswith("goto_"):
            has_interaction = True
        # Reasoning implies reading
        if any(w in (thought + reasoning) for w in ["scrolled", "checked", "found", "saw", "looking", "verified", "identified", "reviewing", "examine", "read"]):
            has_interaction = True
        # Terminal decision implies reading current page
        if action == "decide":
            has_interaction = True
            
        impact = 0.0
        
        # 2. Assign Impact Score
        is_order_view = (entity_id in url) or (page == "order") or ("view/order_id" in url)
        is_history_view = (page == "comments_history") or ("comment" in url)
        is_order_list = ("sales/order" in url and "view" not in url) or (page == "orders")
        
        # Critical (1.0): Order Details + Interaction
        if (is_order_view or is_history_view) and has_interaction:
            impact = 1.0
            
        # Relevant (0.5): Order List / Search
        elif is_order_list:
            impact = 0.5
            
        # Context (0.1): Start Page (if not above)
        elif url == start_url:
            impact = 0.1
            
        cumulative_impact += (gamma ** t) * impact
        
    return cumulative_impact

# ============================================================================
# 2. REASONING SCORING (Robust Fact Extraction)
# ============================================================================
def extract_key_tokens(text: str) -> Set[str]:
    if not text: return set()
    
    # 1. Money/Numbers
    raw_nums = re.findall(r'\$?\d+(?:,\d{3})*(?:\.\d+)?', text)
    tokens = set()
    for n in raw_nums:
        tokens.add(n)
        tokens.add(n.replace('$', '').replace(',', ''))
        
    # 2. Proper Nouns / Keywords
    caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    for c in caps:
        if c.lower() not in {"the", "a", "this", "that"}:
            tokens.add(c.lower())
            
    return tokens

def score_reasoning(reasoning: str, task: Dict) -> float:
    if not reasoning: return 0.0
    
    hidden_content = task.get("hidden_context", {}).get("content", "")
    if not hidden_content: return 1.0
        
    gold_facts = extract_key_tokens(hidden_content)
    if not gold_facts:
        clean_context = re.sub(r'[^\w\s]', '', hidden_content.lower()).split()
        gold_facts = set(clean_context) - {"the", "a", "an", "in"}
        
    if not gold_facts: return 1.0
    
    reasoning_lower = reasoning.lower()
    found_count = 0
    for fact in gold_facts:
        if fact in reasoning_lower: found_count += 1
            
    threshold = max(1, len(gold_facts) * 0.2)
    return 1.0 if found_count >= threshold else 0.0

# ============================================================================
# 3. DECISION & EVIDENCE SCORING
# ============================================================================
def score_decision(decision: str, task: Dict) -> float:
    if not decision: return 0.0
    gt = task.get("ground_truth")
    acceptable = task.get("acceptable_actions", [])
    if isinstance(gt, str): acceptable.append(gt)
    d_norm = decision.strip().upper()
    return 1.0 if any(a.upper() == d_norm for a in acceptable) else 0.0

def score_evidence_quality(reasoning: str) -> float:
    if not reasoning: return 0.0
    score = 0
    r_lower = reasoning.lower()
    
    # Quant (2)
    if bool(re.search(r'\d+', reasoning)) or "$" in reasoning: score += 2
    # Temporal (1)
    if any(w in r_lower for w in ["days ago", "yesterday", "jan", "feb", "202"]): score += 1
    # Source (2)
    if any(w in r_lower for w in ["comment", "staff note", "history", "order page"]): score += 2
    # Structure (2)
    if "what you found" in r_lower or "why it matters" in r_lower: score += 2
    
    return min(score, 7.0)

# ============================================================================
# MAIN LOOP
# ============================================================================
def analyze_ablation(results_file: str, tasks_file: str, output_file: str):
    print(f"Loading Task Definitions: {tasks_file}")
    with open(tasks_file) as f:
        tasks_data = json.load(f)
        tasks_map = {t["task_id"]: t for t in tasks_data["tasks"]}
        
    print(f"Loading Results: {results_file}")
    with open(results_file) as f:
        results = json.load(f)
        
    # Data: model -> category -> condition -> metrics
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "n": 0, "inv": 0.0, "eff": 0.0, "res": 0.0, "dec": 0.0, "ev": 0.0
    })))
    
    categories_found = set()
    detailed_out = []
    
    for r in results:
        model = r.get("model")
        cond = r.get("instruction_condition")
        task_id = r.get("task_id")
        
        if model not in TARGET_MODELS: continue
        if cond not in TARGET_CONDITIONS: continue
        
        task = tasks_map.get(task_id)
        if not task: continue
        
        category = task.get("category", "UNKNOWN")
        categories_found.add(category)
        
        traj = r.get("trajectory", [])
        reasoning = r.get("reasoning", "")
        decision = r.get("decision", "")
        
        # Calculate scores
        inv = score_investigation(traj, task)
        eff = score_efficiency(traj, task) # NEW METRIC
        res = score_reasoning(reasoning, task)
        dec = score_decision(decision, task)
        ev = score_evidence_quality(reasoning)
        
        # Aggregate
        m = data[model][category][cond]
        m["n"] += 1
        m["inv"] += inv
        m["eff"] += eff
        m["res"] += res
        m["dec"] += dec
        m["ev"] += ev
        
        r["ablation_metrics_v2"] = {
            "inv": inv, "eff": eff, "res": res, "dec": dec, "ev": ev
        }
        detailed_out.append(r)

    # OUTPUT TABLES
    for model in sorted(TARGET_MODELS):
        print("\n" + "="*160)
        print(f"MODEL ANALYSIS: {model.upper()} (With Efficiency)")
        print("="*160)
        
        conditions = ["explicit", "hint", "minimal"]
        
        header1 = f"{'Category':<25} |"
        for c in conditions:
            header1 += f" {c.upper():^41} |" # Wider column for 3-decimal data
        print(header1)
        
        # Adjusted header for new column widths
        header2 = f"{'':<25} |"
        for _ in conditions:
            header2 += f" {'Inv':<6} {'Eff':<6} {'Rsn':<6} {'Dec':<6} {'EvQ':<6} {'N':<2} |"
        print(header2)
        print("-" * 160)
        
        for cat in sorted(categories_found):
            row_str = f"{cat:<25} |"
            
            for cond in conditions:
                stats = data[model][cat][cond]
                n = stats["n"]
                if n > 0:
                    inv_p = (stats["inv"] / n) * 100
                    eff_avg = stats["eff"] / n # Average efficient impact sum
                    res_p = (stats["res"] / n) * 100
                    dec_p = (stats["dec"] / n) * 100
                    ev_avg = stats["ev"] / n
                    
                    # Updates: 3 decimal places
                    row_str += f" {inv_p:6.3f} {eff_avg:6.3f} {res_p:6.3f} {dec_p:6.3f} {ev_avg:6.3f} {n:<2} |"
                else:
                    row_str += f" {'-':^39} |"
            print(row_str)
            
    print("\nLegend: Inv=%, Eff=Efficiency(ImpactSum), Rsn=%, Dec=%, EvQ=0-7")

    with open(output_file, 'w') as f:
        json.dump(detailed_out, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="pathways_tasks_v3.json")
    parser.add_argument("--output", default="ablation_results_v2.json")
    args = parser.parse_args()
    
    analyze_ablation(args.results, args.tasks, args.output)
