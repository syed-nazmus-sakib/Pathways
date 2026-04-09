"""
PATHWAYS FUNNEL ANALYSIS - CONDITIONAL METRICS (FINAL)
======================================================
Scientific analysis for ICML.
Calculates CONDITIONAL Accuracies (The Funnel):
1. P(Investigation)
2. P(Reasoning | Investigation)
3. P(Decision | Reasoning, Investigation)
4. Dropoff (Inv - Final Success)

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
TARGET_MODELS = {"gemini", "gpt"} #for ./pathways_full_20260116_022920/all_results.json
#TARGET_MODELS = {"qwen32b", "qwen235b"} #for ./pathways_qwen_20260117_125811/all_results.json
TARGET_CONDITIONS = {"explicit", "hint", "minimal"}

# ============================================================================
# SCORING HELPERS (Identical to Ablation Script)
# ============================================================================
def score_investigation(trajectory: List[Dict], task: Dict) -> bool:
    """Pass/Fail Investigation Check"""
    if not trajectory: return False
    
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
            
        if (action == "scroll") or (page == "comments_history") or ("comment" in thought):
            viewed_history = True
            
    # Strict: Must do BOTH
    return visited_order_page and viewed_history

def extract_key_tokens(text: str) -> Set[str]:
    """Extract strictly meaningful tokens: Numbers, Money, Proper Nouns."""
    if not text: return set()
    
    # 1. Extract Money/Numbers specifics (keep original formatting and normalized)
    # Matches: $150.00, 150.00, 150, 15 refunds
    raw_nums = re.findall(r'\$?\d+(?:,\d{3})*(?:\.\d+)?', text)
    tokens = set()
    for n in raw_nums:
        tokens.add(n)
        tokens.add(n.replace('$', '').replace(',', ''))
        
    # 2. Extract Capitalized phrases (Proper Nouns / Keywords)
    # Matches: "Fraud Alert", "Lisa Anderson", "Loss Prevention"
    # Simple heuristic: sequence of capitalized words
    caps = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    for c in caps:
        if c.lower() not in {"the", "a", "this", "that"}:
            tokens.add(c.lower())
            
    return tokens

def score_reasoning(reasoning: str, task: Dict) -> bool:
    """Pass/Fail Reasoning Check (Critical Fact Recall)"""
    if not reasoning: return False
    
    hidden_content = task.get("hidden_context", {}).get("content", "")
    if not hidden_content: return True # Nothing to find
    
    # Extract Gold Facts from Ground Truth Context
    gold_facts = extract_key_tokens(hidden_content)
    
    if not gold_facts: 
        # Fallback to simple containment if no numbers/entities found
        # (e.g. "Do not process this.")
        clean_context = re.sub(r'[^\w\s]', '', hidden_content.lower()).split()
        gold_facts = set(clean_context) - {"the", "a", "an", "to", "of", "in"}
        
    if not gold_facts: return True
    
    # Check Model Reasoning
    reasoning_lower = reasoning.lower()
    
    found_count = 0
    for fact in gold_facts:
        # Check strict containment (e.g. "150.00" in text)
        if fact in reasoning_lower:
            found_count += 1
            
    # CRITERIA:
    # If explicit/hint condition, they usually cite specific numbers.
    # Pass if they cite at least 1 critical fact if few facts exist,
    # or > 20% if many exist.
    
    threshold = max(1, len(gold_facts) * 0.2)
    return found_count >= threshold

def score_decision(decision: str, task: Dict) -> bool:
    """Pass/Fail Decision Check"""
    if not decision: return False
    
    gt = task.get("ground_truth")
    acceptable = task.get("acceptable_actions", [])
    if isinstance(gt, str): acceptable.append(gt)
    
    d_norm = decision.strip().upper()
    return any(a.upper() == d_norm for a in acceptable)

# ============================================================================
# MAIN LOOP
# ============================================================================
def analyze_funnel(results_file: str, tasks_file: str, output_file: str):
    print(f"Loading Task Definitions: {tasks_file}")
    with open(tasks_file) as f:
        tasks_data = json.load(f)
        tasks_map = {t["task_id"]: t for t in tasks_data["tasks"]}
        
    print(f"Loading Results: {results_file}")
    with open(results_file) as f:
        results = json.load(f)
        
    # Data Structure: model -> category -> condition -> metrics
    # metrics = {n, inv_pass, res_pass_cond, dec_pass_cond}
    # We need access to raw counts to calculate conditionals later
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "n": 0, 
        "passed_inv": 0, 
        "passed_res_given_inv": 0, # Passed Res AND Inv
        "passed_dec_given_all": 0  # Passed Dec AND Res AND Inv
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
        
        # Extract & Score
        traj = r.get("trajectory", [])
        reasoning = r.get("reasoning", "")
        decision = r.get("decision", "")
        
        # 1. Evaluate separately first
        is_inv = score_investigation(traj, task)
        is_res = score_reasoning(reasoning, task)
        is_dec = score_decision(decision, task)
        
        # 2. Apply Funnel Logic
        # Passed Inv?
        pass_level_1 = is_inv
        
        # Passed Res (Given Inv)?
        pass_level_2 = pass_level_1 and is_res
        
        # Passed Dec (Given All)?
        pass_level_3 = pass_level_2 and is_dec
        
        # Aggregate
        m = data[model][category][cond]
        m["n"] += 1
        if pass_level_1: m["passed_inv"] += 1
        if pass_level_2: m["passed_res_given_inv"] += 1
        if pass_level_3: m["passed_dec_given_all"] += 1
        
        r["funnel_metrics"] = {
            "p_inv": pass_level_1,
            "p_res_cond": pass_level_2,
            "p_dec_cond": pass_level_3
        }
        detailed_out.append(r)

    # OUTPUT TABLES
    for model in sorted(TARGET_MODELS):
        print("\n" + "="*140)
        print(f"FUNNEL ANALYSIS: {model.upper()} (Conditional Probabilities)")
        print("="*140)
        
        conditions = ["explicit", "hint", "minimal"]
        
        # Header Row
        header1 = f"{'Category':<25} |"
        for c in conditions:
            header1 += f" {c.upper():^30} |"
        print(header1)
        
        # Sub-header
        header2 = f"{'':<25} |"
        for _ in conditions:
            header2 += f" {'Inv%':<5} {'Rsn%':<5} {'Dec%':<5} {'Drop':<5} {'N':<3} |"
        print(header2)
        print("-" * 140)
        
        for cat in sorted(categories_found):
            row_str = f"{cat:<25} |"
            
            for cond in conditions:
                stats = data[model][cat][cond]
                n = stats["n"]
                
                if n > 0:
                    # P(Inv) = Inv / N
                    p_inv = (stats["passed_inv"] / n) * 100
                    
                    # P(Res | Inv) = Passed Both / Passed Inv
                    denom_res = stats["passed_inv"]
                    p_res = (stats["passed_res_given_inv"] / denom_res * 100) if denom_res > 0 else 0.0
                    
                    # P(Dec | Res, Inv) = Passed All / Passed Res+Inv
                    denom_dec = stats["passed_res_given_inv"]
                    p_dec = (stats["passed_dec_given_all"] / denom_dec * 100) if denom_dec > 0 else 0.0
                    
                    # Dropoff (Inv - Final Overall Success)
                    # Overall Success = Passed All / N
                    p_final = (stats["passed_dec_given_all"] / n) * 100
                    dropoff = p_inv - p_final
                    
                    row_str += f" {p_inv:5.0f} {p_res:5.0f} {p_dec:5.0f} {dropoff:5.1f} {n:<3} |"
                else:
                    row_str += f" {'-':^28} |"
            print(row_str)
            
    print("\nLegend: Inv=P(Inv), Rsn=P(Rsn|Inv), Dec=P(Dec|Rsn,Inv), Drop=Inv% - FinalSuccess%")

    with open(output_file, 'w') as f:
        json.dump(detailed_out, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="pathways_tasks_v3.json")
    parser.add_argument("--output", default="funnel_results_detailed.json")
    args = parser.parse_args()
    
    analyze_funnel(args.results, args.tasks, args.output)
