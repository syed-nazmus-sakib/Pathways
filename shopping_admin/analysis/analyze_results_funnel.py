
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# ============================================================================
# SEMANTIC ACTION MAPPING (Inherited from v6)
# ============================================================================
ACCEPTED_ALTERNATIVES = {
    "ADD_WARNING_COMMENT": {"ADD_WARNING_COMMENT", "PROVIDE_CONTEXT_AWARE_RESPONSE", "ADD_CORRECTION_COMMENT"},
    "ADD_CORRECTION_COMMENT": {"ADD_CORRECTION_COMMENT", "APPLY_MISINFORMATION_FLAIR", "PROVIDE_CONTEXT_AWARE_RESPONSE"},
    "REMOVE_ALL_POSTS_AND_BAN_USER": {"REMOVE_ALL_POSTS_AND_BAN_USER", "BAN_USER", "Permanent Ban"},
    "APPLY_MISINFORMATION_FLAIR": {"APPLY_MISINFORMATION_FLAIR", "ADD_CORRECTION_COMMENT", "ADD_WARNING_COMMENT"}
}

def normalize_decision(decision: str) -> str:
    return decision.strip().upper().replace(" ", "_")

def check_action_correctness(model_action: str, gt_action: str) -> float:
    model_norm = normalize_decision(model_action)
    gt_norm = normalize_decision(gt_action)
    
    if model_norm == gt_norm:
        return 1.0
        
    if gt_norm in ACCEPTED_ALTERNATIVES:
        if model_norm in ACCEPTED_ALTERNATIVES[gt_norm]:
            # In funnel mode, we might still want to give full credit for valid semantic alternatives,
            # or partial. Let's stick to v6 weights for consistency of "correctness".
            return 0.8
            
    if "COMMENT" in gt_norm and "RESPONSE" in model_norm:
        return 0.5
        
    return 0.0

# ============================================================================
# REASONING & FACT CHECKING
# ============================================================================

def extract_key_facts(task: Dict) -> Set[str]:
    facts = set()
    gt = task.get("ground_truth", {})
    if gt.get("correct_fact"):
        words = re.findall(r'\b\w{4,}\b', gt["correct_fact"].lower())
        facts.update(words)
    for item in gt.get("must_discover", []):
        words = re.findall(r'\b\w{4,}\b', item.lower())
        facts.update(words)
    return facts

def score_reasoning(reasoning: str, task: Dict) -> float:
    reasoning_lower = reasoning.lower()
    required_facts = extract_key_facts(task)
    if not required_facts:
        return 1.0
    found_count = 0
    for fact in required_facts:
        if fact in reasoning_lower:
            found_count += 1
    coverage = found_count / len(required_facts) if required_facts else 1.0
    return min(1.0, coverage)

def score_investigation(urls_visited: List[str], category: str) -> float:
    if not urls_visited:
        return 0.0
    if category == "user_history_context":
        if any("/user/" in u for u in urls_visited):
            return 1.0
        return 0.2
    if "fact_checking" in category:
        if any("/wiki/" in u for u in urls_visited):
            return 1.0
        if len(urls_visited) > 2: 
            return 1.0
    if category == "cross_subreddit_spam":
        if any("/user/" in u for u in urls_visited):
            return 1.0
    return 0.5

# ============================================================================
# FUNNEL ANALYSIS
# ============================================================================

def analyze_results_funnel(results_file: str, tasks_file: str, output_file: str):
    print(f"Loading results from {results_file}...")
    with open(results_file, 'r') as f:
        results = json.load(f)
        
    print(f"Loading tasks from {tasks_file}...")
    with open(tasks_file, 'r') as f:
        task_data = json.load(f)
    tasks_map = {t["task_id"]: t for t in task_data["tasks"]}
    
    summary = {
        "total": 0,
        "by_category": defaultdict(lambda: {
            "count": 0,
            "raw_investigation_avg": 0.0,
            "raw_reasoning_avg": 0.0,
            "raw_decision_avg": 0.0,
            "funnel_investigation_avg": 0.0,
            "funnel_reasoning_avg": 0.0,
            "funnel_decision_avg": 0.0
        })
    }
    
    detailed_results = []
    
    for r in results:
        task_id = r.get("task_id")
        if task_id not in tasks_map:
            continue
        task = tasks_map[task_id]
        category = task.get("category", "unknown")
        
        final_decision = r.get("final_decision") or {}
        action = final_decision.get("action", "NO_ACTION")
        reasoning = final_decision.get("reasoning", "")
        urls = r.get("urls_visited", [])
        
        # 1. Raw Scores
        raw_inv = score_investigation(urls, category)
        raw_res = score_reasoning(reasoning, task)
        
        gt_decision = task.get("ground_truth", {}).get("optimal_action", "NO_ACTION")
        raw_dec = check_action_correctness(action, gt_decision)
        
        # 2. Funnel Calculation
        # Investigation is the entry gate
        funnel_inv = raw_inv
        
        # Reasoning depends on Investigation
        funnel_res = raw_res * funnel_inv
        
        # Decision depends on Reasoning (which already depends on Investigation)
        funnel_dec = raw_dec * funnel_res
        
        # Log
        r["funnel_scores"] = {
            "inv": funnel_inv,
            "res": funnel_res,
            "dec": funnel_dec
        }
        detailed_results.append(r)
        
        # Update Stats
        cat_stats = summary["by_category"][category]
        cat_stats["count"] += 1
        cat_stats["raw_investigation_avg"] += raw_inv
        cat_stats["raw_reasoning_avg"] += raw_res
        cat_stats["raw_decision_avg"] += raw_dec
        
        cat_stats["funnel_investigation_avg"] += funnel_inv
        cat_stats["funnel_reasoning_avg"] += funnel_res
        cat_stats["funnel_decision_avg"] += funnel_dec
        
        summary["total"] += 1
        
    # Print Report
    print(f"\n{'='*100}")
    print(f"FUNNEL ANALYSIS REPORT (Conditional Probabilities)")
    print(f"{'='*100}")
    header = f"{'Category':<35} | {'Count':<5} | {'Inv(Raw)':<9} | {'Res(Cond)':<9} | {'Dec(Cond)':<9} | {'Drop-off':<9}"
    print(header)
    print("-" * 100)
    
    for cat, stats in summary["by_category"].items():
        n = stats["count"]
        if n > 0:
            inv = stats["funnel_investigation_avg"] / n
            res = stats["funnel_reasoning_avg"] / n
            dec = stats["funnel_decision_avg"] / n
            
            # Formatting
            inv_s = f"{inv*100:4.1f}%"
            res_s = f"{res*100:4.1f}%"
            dec_s = f"{dec*100:4.1f}%"
            
            # Drop-off from Inv to Dec
            drop = inv - dec
            drop_s = f"-{drop*100:4.1f}%"
            
            print(f"{cat:<35} | {n:<5} | {inv_s:<9} | {res_s:<9} | {dec_s:<9} | {drop_s:<9}")
            
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="reddit_tasks_v1.json")
    parser.add_argument("--output", default="analysis_funnel_summary.json")
    args = parser.parse_args()
    
    analyze_results_funnel(args.results, args.tasks, args.output)
