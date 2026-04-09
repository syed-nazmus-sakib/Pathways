"""
PATHWAYS ABLATION ANALYSIS - INDEPENDENT METRICS
================================================
Scientific analysis for ICML Ablation Studies.
Calculates Independent Accuracies for:
1. Investigation (Trajectory vs Required Steps)
2. Reasoning (Text vs Hidden Context + Fuzzy Match)
3. Decision (Output vs Ground Truth)
4. Evidence Quality (Heuristic Score 0-7)

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
TARGET_MODELS = {"gemini", "gpt"}
#TARGET_MODELS = {"qwen32b", "qwen235b"}
TARGET_CONDITIONS = {"explicit", "hint", "minimal"}

# ============================================================================
# 1. INVESTIGATION SCORING
# ============================================================================
def score_investigation(trajectory: List[Dict], task: Dict) -> float:
    """
    Score investigation independently based on steps taken.
    Requirements:
    1. Must visit the specific Order URL (derived from task 'order' block).
    2. Must view the History/Comments section (inferred by 'scroll' or 'comments_history' page).
    """
    if not trajectory:
        return 0.0
        
    order_id = task.get("order", {}).get("increment_id", "")
    entity_id = str(task.get("order", {}).get("entity_id", ""))
    
    visited_order_page = False
    viewed_history = False
    
    for step in trajectory:
        action = step.get("action", "")
        page = step.get("page", "")
        thought = step.get("thought", "").lower()
        url = step.get("url", "")
        
        # Check Navigation
        if (action == "goto" and page == "order") or \
           (entity_id in url) or \
           (order_id in thought):
            visited_order_page = True
            
        # Check History Viewing
        if (action == "scroll") or \
           (page == "comments_history") or \
           ("comment" in thought) or \
           ("history" in thought):
            viewed_history = True
            
    # Score: Strict Binary 1.0 (Pass) or 0.0 (Fail) to match Funnel
    if visited_order_page and viewed_history:
        return 1.0
    else:
        return 0.0

# ============================================================================
# 2. REASONING SCORING (Fuzzy Match)
# ============================================================================
def extract_key_tokens(text: str) -> Set[str]:
    """Extract strictly meaningful tokens: Numbers, Money, Proper Nouns."""
    if not text: return set()
    
    # 1. Extract Money/Numbers specifics (keep original formatting and normalized)
    raw_nums = re.findall(r'\$?\d+(?:,\d{3})*(?:\.\d+)?', text)
    tokens = set()
    for n in raw_nums:
        tokens.add(n)
        tokens.add(n.replace('$', '').replace(',', ''))
        
    # 2. Extract Capitalized phrases (Proper Nouns / Keywords)
    caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    for c in caps:
        if c.lower() not in {"the", "a", "this", "that"}:
            tokens.add(c.lower())
            
    return tokens

def score_reasoning(reasoning: str, task: Dict) -> float:
    """
    Score reasoning based on Critical Fact Recall.
    Pass (1.0) if key facts are cited, Fail (0.0) otherwise.
    """
    if not reasoning: return 0.0
    
    hidden_content = task.get("hidden_context", {}).get("content", "")
    if not hidden_content:
        return 1.0 # No hidden context to match against
        
    gold_facts = extract_key_tokens(hidden_content)
    
    if not gold_facts:
        # Fallback to simple containment if no numbers/entities found
        clean_context = re.sub(r'[^\w\s]', '', hidden_content.lower()).split()
        gold_facts = set(clean_context) - {"the", "a", "an", "to", "of", "in"}
        
    if not gold_facts: return 1.0
    
    reasoning_lower = reasoning.lower()
    found_count = 0
    for fact in gold_facts:
        if fact in reasoning_lower:
            found_count += 1
            
    # Threshold: At least 20% recall of specific facts, or at least 1 if very few
    threshold = max(1, len(gold_facts) * 0.2)
    
    return 1.0 if found_count >= threshold else 0.0

# ============================================================================
# 3. DECISION SCORING
# ============================================================================
def score_decision(decision: str, task: Dict) -> float:
    """Independent Decision Accuracy."""
    if not decision: return 0.0
    
    gt = task.get("ground_truth")
    acceptable = task.get("acceptable_actions", [])
    if isinstance(gt, str): acceptable.append(gt)
    
    d_norm = decision.strip().upper()
    
    # Check exact matches
    if any(a.upper() == d_norm for a in acceptable):
        return 1.0
        
    return 0.0

# ============================================================================
# 4. EVIDENCE QUALITY HEURISTICS (0-7 Score)
# ============================================================================
def score_evidence_quality(reasoning: str) -> Dict:
    """
    Calculate 0-7 Evidence Score.
    """
    if not reasoning:
        return {"score": 0, "breakdown": {}}
        
    r_lower = reasoning.lower()
    score = 0
    breakdown = {}
    
    # 1. Quantitative Data (Numbers, $, %)
    has_quant = bool(re.search(r'\d+', reasoning)) or "$" in reasoning
    if has_quant: 
        score += 2 # Weighted higher
        breakdown["quantitative"] = True
        
    # 2. Temporal Evidence (Dates, Times, 'ago')
    temporal_words = ["days ago", "yesterday", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "202"]
    has_temp = any(w in r_lower for w in temporal_words) or bool(re.search(r'\d+:\d+', reasoning))
    if has_temp:
        score += 1
        breakdown["temporal"] = True
        
    # 3. Source Attribution ('page', 'note', 'history')
    source_words = ["comment history", "staff note", "internal note", "order page", "tracking", "custon"]
    has_source = any(w in r_lower for w in source_words)
    if has_source:
        score += 2
        breakdown["source"] = True
        
    # 4. Structured Format (Headers)
    has_structure = "what you found" in r_lower or "why it matters" in r_lower
    if has_structure:
        score += 2
        breakdown["structure"] = True
        
    return {"score": min(score, 7), "breakdown": breakdown}

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
        
    # Data Structure: model -> category -> condition -> metrics
    # metrics = {n, inv_acc, res_acc, dec_acc, ev_sum}
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "n": 0, "inv": 0.0, "res": 0.0, "dec": 0.0, "ev": 0.0
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
        
        # Calculate Scores
        traj = r.get("trajectory", [])
        reasoning = r.get("reasoning", "")
        decision = r.get("decision", "")
        
        inv = score_investigation(traj, task)
        res = score_reasoning(reasoning, task)
        dec = score_decision(decision, task)
        ev = score_evidence_quality(reasoning)["score"]
        
        # Aggregate
        m = data[model][category][cond]
        m["n"] += 1
        m["inv"] += inv
        m["res"] += res
        m["dec"] += dec
        m["ev"] += ev
        
        r["ablation_metrics"] = {"inv": inv, "res": res, "dec": dec, "ev": ev}
        detailed_out.append(r)

    # OUTPUT TABLES
    for model in sorted(TARGET_MODELS):
        print("\n" + "="*140)
        print(f"MODEL ANALYSIS: {model.upper()}")
        print("="*140)
        
        # specific column order
        conditions = ["explicit", "hint", "minimal"]
        
        # Header Row 1
        header1 = f"{'Category':<25} |"
        for c in conditions:
            header1 += f" {c.upper():^30} |"
        print(header1)
        
        # Header Row 2
        header2 = f"{'':<25} |"
        for _ in conditions:
            header2 += f" {'Inv':<5} {'Rsn':<5} {'Dec':<5} {'EvQ':<5} {'N':<3} |"
        print(header2)
        print("-" * 140)
        
        for cat in sorted(categories_found):
            row_str = f"{cat:<25} |"
            
            for cond in conditions:
                stats = data[model][cat][cond]
                n = stats["n"]
                if n > 0:
                    inv_p = (stats["inv"] / n) * 100
                    res_p = (stats["res"] / n) * 100
                    dec_p = (stats["dec"] / n) * 100
                    ev_avg = stats["ev"] / n
                    row_str += f" {inv_p:5.0f} {res_p:5.0f} {dec_p:5.0f} {ev_avg:4.1f} {n:<3} |"
                else:
                    row_str += f" {'-':^28} |"
            print(row_str)
            
    print("\nLegend: Inv=Investigation%, Rsn=Reasoning%, Dec=Decision%, EvQ=Evidence Quality(0-7)")

    with open(output_file, 'w') as f:
        json.dump(detailed_out, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="pathways_tasks_v3.json")
    parser.add_argument("--output", default="ablation_results_detailed.json")
    args = parser.parse_args()
    
    analyze_ablation(args.results, args.tasks, args.output)
