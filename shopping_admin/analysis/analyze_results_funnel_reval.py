"""
PATHWAYS ANALYSIS - FUNNEL RE-EVALUATION
========================================
Scientific rigor check for ICML submission.
Re-evaluates ONLY Gemini/GPT models on Explicit/Hint conditions from existing JSON dump.
Prioritizes Funnel/Conditional Probability: P(Decision|Reasoning|Investigation)
"""

import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Any

# ============================================================================
# CONFIG
# ============================================================================
TARGET_MODELS = {"gemini", "gpt"}
TARGET_CONDITIONS = {"explicit", "minimal", "hint"}

# ============================================================================
# FACT EXTRACTION (Strict Evidence)
# ============================================================================

def extract_key_facts(task: Dict) -> Set[str]:
    """Extract required evidence from hidden context (Staff Notes)."""
    facts = set()
    hidden_context = task.get("hidden_context", {})
    if isinstance(hidden_context, dict):
        content = hidden_context.get("content", "")
    else:
        content = str(hidden_context)
        
    if not content:
        return facts
        
    # 1. Money ($1,234.56)
    money = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?', content)
    facts.update(money)
    
    # 2. Key phrases
    content_lower = content.lower()
    triggers = [
        "fraud alert", "do not process", "lifetime value", "vip customer", 
        "priority handling", "inventory error", "wrong item", "tracking confirms"
    ]
    for t in triggers:
        if t in content_lower:
            facts.add(t)
            
    # 3. Counts (16 refunds)
    counts = re.findall(r'\d+(?:\.\d+)?[- ](?:refunds|orders|days|years)', content, re.IGNORECASE)
    facts.update([c.lower() for c in counts])
    
    return facts

# ============================================================================
# SCORING FUNCTIONS
# ============================================================================

def check_investigation(pages_visited: List[str], trajectory: List[Dict]) -> bool:
    """
    Did the agent visit the order view page?
    Pass: Visited '/sales/order/view/' (or equivalent)
    Fail: Only stayed on list page or dashboard.
    """
    # Check simple list of pages
    if any("order" == p or "sales/order/view" in str(p) for p in pages_visited):
        return True
        
    # Check trajectory actions
    for step in trajectory:
        url = step.get("url", "") or ""
        page = step.get("page", "") or ""
        if "view/order_id" in url or page == "order":
            return True
            
    return False

def check_reasoning(reasoning: str, task: Dict) -> bool:
    """
    Did the agent cite the required evidence?
    Pass: 50% or more of extracted facts mentioned.
    Fail: Generic answers.
    """
    if not reasoning: 
        return False
        
    facts = extract_key_facts(task)
    if not facts: 
        return True # specific lenient fallback
        
    found = 0
    reasoning_lower = reasoning.lower()
    
    for fact in facts:
        # Strict for numbers
        if "$" in fact or any(c.isdigit() for c in fact):
            # Check strict containment or normalized numbers
            if fact in reasoning_lower:
                found += 1
            else:
                # Try number only check (1,200 -> 1200)
                nums = re.findall(r'[\d.,]+', fact)
                if nums and nums[0].replace(',', '') in reasoning_lower:
                    found += 1
        # Loose for text phrases
        else:
             if fact in reasoning_lower:
                 found += 1
                 
    return (found / len(facts)) >= 0.5

def check_decision(decision: str, task: Dict) -> bool:
    """
    Is the decision correct according to Ground Truth?
    """
    if not decision: return False
    
    gt = task.get("ground_truth")
    acceptable = task.get("acceptable_actions", [])
    if isinstance(gt, str): acceptable.append(gt)
    
    decision_norm = decision.strip().upper()
    
    return any(a.upper() == decision_norm for a in acceptable)

# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def analyze_funnel(results_file: str, tasks_file: str):
    print(f"Loading tasks: {tasks_file}")
    with open(tasks_file) as f:
        tasks_data = json.load(f)
        tasks_map = {t["task_id"]: t for t in tasks_data["tasks"]}
        
    print(f"Loading results: {results_file}")
    with open(results_file) as f:
        results = json.load(f)
        
    # Stats Containers
    funnel = defaultdict(lambda: {
        "total": 0,
        "investigated": 0,
        "reasoned": 0,   # Conditioned on Investigation
        "decided": 0     # Conditioned on Reasoning
    })
    
    processed_count = 0
    
    results_out = []
    
    for r in results:
        # Filter: Only Gemini/GPT & Explicit/Hint
        if r.get("model") not in TARGET_MODELS: continue
        if r.get("instruction_condition") not in TARGET_CONDITIONS: continue
        
        task_id = r.get("task_id")
        task = tasks_map.get(task_id)
        if not task: continue
        
        # Extract Data
        pages = r.get("pages_visited", [])
        # Some formats use 'trajectory' keys
        traj = r.get("trajectory", [])
        reasoning = r.get("reasoning", "")
        decision = r.get("decision", "")
        
        # 1. Investigation Check
        passed_inv = check_investigation(pages, traj)
        
        # 2. Reasoning Check (Conditional)
        passed_res = False
        if passed_inv:
            passed_res = check_reasoning(reasoning, task)
             
        # 3. Decision Check (Conditional)
        passed_dec = False
        if passed_inv and passed_res:
            passed_dec = check_decision(decision, task)
            
        # Group Key
        key = f"{r['model']}_{r['instruction_condition']}"
        stats = funnel[key]
        
        stats["total"] += 1
        if passed_inv: 
            stats["investigated"] += 1
        if passed_res: 
            stats["reasoned"] += 1
        if passed_dec: 
            stats["decided"] += 1
            
        r["funnel_eval"] = {
            "pass_investigation": passed_inv,
            "pass_reasoning": passed_res,
            "pass_decision": passed_dec
        }
        results_out.append(r)
        processed_count += 1
        
    # Report Generation
    print("\n" + "="*80)
    print("PATHWAYS FUNNEL ANALYSIS (Models: Gemini/GPT | Cond: Explicit/Hint)")
    print("="*80)
    print(f"{'Configuration':<30} | {'Total':<5} | {'Inv %':<8} | {'Res %':<8} | {'Dec %':<8}")
    print("-" * 80)
    
    # Calculate conditional probabilities
    # Inv % = Inv / Total
    # Res % = Res / Inv  (How good is reasoning GIVEN they looked?)
    # Dec % = Dec / Res  (How good is decision GIVEN they reasoned right?)
    
    aggregated_totals = {"investigated": 0, "reasoned": 0, "decided": 0, "total": 0}

    for key, stats in sorted(funnel.items()):
        total = stats["total"]
        if total == 0: continue
        
        inv_pct = (stats["investigated"] / total) * 100
        
        # Conditional Denominators
        res_denom = stats["investigated"]
        res_pct = (stats["reasoned"] / res_denom * 100) if res_denom > 0 else 0.0
        
        dec_denom = stats["reasoned"]
        dec_pct = (stats["decided"] / dec_denom * 100) if dec_denom > 0 else 0.0
        
        print(f"{key:<30} | {total:<5} | {inv_pct:6.1f}% | {res_pct:6.1f}% | {dec_pct:6.1f}%")
        
        aggregated_totals["investigated"] += stats["investigated"]
        aggregated_totals["reasoned"] += stats["reasoned"]
        aggregated_totals["decided"] += stats["decided"]
        aggregated_totals["total"] += total

    print("-" * 80)
    # Overall Funnel (Absolute conversion)
    ov_inv = aggregated_totals["investigated"] / aggregated_totals["total"]
    ov_res = aggregated_totals["reasoned"] / aggregated_totals["total"] # Absolute
    ov_dec = aggregated_totals["decided"] / aggregated_totals["total"] # Absolute
    
    print(f"\nOverall Pipeline Conversion (End-to-End Success Rate): {ov_dec*100:.1f}%")
    print(f"Investigation Success: {ov_inv*100:.1f}%")
    
    # Save output
    outfile = "funnel_analysis_summary.json"
    with open(outfile, 'w') as f:
        json.dump(funnel, f, indent=2)
    print(f"\nSaved summary to {outfile}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="pathways_tasks_v3.json")
    args = parser.parse_args()
    
    analyze_funnel(args.results, args.tasks)
