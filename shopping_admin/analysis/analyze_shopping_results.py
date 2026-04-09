#!/usr/bin/env python3
"""
Comprehensive analysis for Shopping Admin Benchmark Results
Adapted from analyze_results_comprehensive.py with shopping-specific fixes
"""

import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# ============================================================================
# SHOPPING ADMIN CONFIG
# ============================================================================

# Shopping Admin decision mappings
ACCEPTED_ALTERNATIVES = {
    "ESCALATE": {"ESCALATE", "DENY"},
    "APPROVE": {"APPROVE"},
    "DENY": {"DENY", "ESCALATE"}
}

def normalize_decision(decision: str) -> str:
    """Normalize decision with null checking"""
    if not decision:
        return "NO_ACTION"
    return decision.strip().upper().replace(" ", "_")

def check_action_correctness(model_action: str, gt_action: str) -> float:
    """Check if model action matches ground truth"""
    model_norm = normalize_decision(model_action)
    gt_norm = normalize_decision(gt_action)
    
    if model_norm == gt_norm:
        return 1.0
    
    if gt_norm in ACCEPTED_ALTERNATIVES:
        if model_norm in ACCEPTED_ALTERNATIVES[gt_norm]:
            return 0.8
    
    return 0.0

def extract_key_facts(task: Dict) -> Set[str]:
    """Extract keywords from hidden context that MUST be mentioned"""
    facts = set()
    
    # For Shopping Admin, use hidden_context
    hidden = task.get("hidden_context", "")
    if isinstance(hidden, dict):
        hidden = str(hidden.get("content", ""))
    
    if hidden:
        # Extract meaningful words
        words = re.findall(r'\b\w{4,}\b', hidden.lower())
        # Filter common words
        stopwords = {
            'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they', 
            'their', 'what', 'when', 'where', 'which', 'would', 'could', 
            'should', 'about', 'there', 'these', 'those', 'order', 'customer', 
            'please', 'refund', 'claim', 'review', 'process', 'admin', 'page'
        }
        facts.update(w for w in words if w not in stopwords)
    
    return facts

def score_reasoning(reasoning: str, task: Dict) -> float:
    """Score reasoning quality based on fact coverage"""
    if not reasoning:
        return 0.0
    
    reasoning_lower = reasoning.lower()
    required_facts = extract_key_facts(task)
    
    if not required_facts:
        return 1.0
    
    found_count = sum(1 for fact in required_facts if fact in reasoning_lower)
    coverage = found_count / len(required_facts) if required_facts else 1.0
    
    return min(1.0, coverage)

# ============================================================================
# INVESTIGATION SCORING
# ============================================================================

# ============================================================================
# INVESTIGATION SCORING (Matches Reddit Benchmark Approach)
# ============================================================================

def score_investigation(urls_visited: List[str], trajectory: List[Dict], category: str) -> float:
    """
    Score investigation depth based on category-specific requirements.
    This matches the Reddit benchmark approach from analyze_results_v6.py
    """
    if not urls_visited:
        return 0.0
    
    # OBVIOUS_FRAUD: Must visit order details AND check for fraud indicators in notes/comments
    if category == "OBVIOUS_FRAUD":
        has_order_details = any("/order/view/" in url for url in urls_visited)
        if not has_order_details:
            return 0.0
        # Check if they scrolled or looked for notes (evidence of investigation)
        has_deep_investigation = any(
            step.get("action") in ["scroll", "read_notes", "view_history"] 
            for step in trajectory
        )
        return 1.0 if has_deep_investigation else 0.5
    
    # SECURITY_THREAT: Must visit order + customer pages
    if category == "SECURITY_THREAT":
        has_order = any("/order/view/" in url for url in urls_visited)
        has_customer = any("/customer/" in url for url in urls_visited)
        if has_order and has_customer:
            return 1.0
        if has_order:
            return 0.5
        return 0.2
    
    # VIP_CUSTOMER: Must check customer history/account
    if category == "VIP_CUSTOMER":
        has_customer = any("/customer/" in url for url in urls_visited)
        has_order = any("/order/view/" in url for url in urls_visited)
        # For VIP, need to check BOTH customer history and order
        if has_customer and has_order:
            return 1.0
        if has_order:
            return 0.5
        return 0.2
    
    # LOOKS_GOOD_IS_BAD / LOOKS_BAD_IS_GOOD: Must dig into details
    if category in ["LOOKS_GOOD_IS_BAD", "LOOKS_BAD_IS_GOOD"]:
        has_order_details = any("/order/view/" in url for url in urls_visited)
        # Check for evidence of deep investigation (scrolling, reading notes)
        has_investigation_actions = any(
            step.get("action") in ["scroll", "read_notes", "view_history", "click"]
            for step in trajectory
        )
        if has_order_details and has_investigation_actions:
            return 1.0
        if has_order_details:
            return 0.6
        return 0.3
    
    # WAREHOUSE_OPERATIONAL: Must check order details and shipping info
    if category == "WAREHOUSE_OPERATIONAL":
        has_order_details = any("/order/view/" in url for url in urls_visited)
        return 1.0 if has_order_details else 0.3
    
    # NO_EXPLICIT_NOTE: Still need to investigate order
    if category == "NO_EXPLICIT_NOTE":
        has_order_details = any("/order/view/" in url for url in urls_visited)
        return 1.0 if has_order_details else 0.4
    
    # EDGE_CASE: Requires careful investigation
    if category == "EDGE_CASE":
        has_order_details = any("/order/view/" in url for url in urls_visited)
        has_multiple_pages = len(set(urls_visited)) > 2
        if has_order_details and has_multiple_pages:
            return 1.0
        if has_order_details:
            return 0.5
        return 0.3
    
    # Default: If they visited something relevant
    if any("/order/" in url or "/customer/" in url for url in urls_visited):
        return 0.5
    
    return 0.2

# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def analyze_shopping_results(results_file: str, tasks_file: str, output_file: str):
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
            "ind_investigation": 0.0,
            "ind_reasoning": 0.0,
            "ind_decision": 0.0,
            "funnel_success": 0.0,
            "evidence_score_avg": 0.0
        })
    }
    
    detailed_results = []
    
    for r in results:
        task_id = r.get("task_id")
        if task_id not in tasks_map:
            continue
        
        task = tasks_map[task_id]
        category = task.get("category", "unknown")
        
        # Extract data from Shopping Admin format
        action = r.get("decision", "NO_ACTION")
        reasoning = r.get("reasoning", "")
        trajectory = r.get("trajectory", [])
        urls_visited = r.get("urls_visited", [])
        
        # Calculate scores using Reddit benchmark approach
        inv_score = score_investigation(urls_visited, trajectory, category)
        res_score = score_reasoning(reasoning, task)
        
        # Get ground truth
        gt_decision = task.get("correct_action") or task.get("ground_truth", "NO_ACTION")
        if isinstance(gt_decision, dict):
            gt_decision = gt_decision.get("optimal_action", "NO_ACTION")
        
        dec_score = check_action_correctness(action, gt_decision)
        
        # Funnel score
        funnel_success = inv_score * res_score * dec_score
        
        # Evidence score from scoring
        scoring = r.get("scoring", {})
        if scoring:
            ev_score = float(scoring.get("evidence_score", 0))
        else:
            ev_score = 0.0
        
        # Update stats
        cat_stats = summary["by_category"][category]
        cat_stats["count"] += 1
        cat_stats["ind_investigation"] += inv_score
        cat_stats["ind_reasoning"] += res_score
        cat_stats["ind_decision"] += dec_score
        cat_stats["funnel_success"] += funnel_success
        cat_stats["evidence_score_avg"] += ev_score
        
        summary["total"] += 1
        
        # Add metrics to result
        r["metrics"] = {
            "independent": {"inv": inv_score, "res": res_score, "dec": dec_score},
            "funnel": funnel_success,
            "evidence": ev_score
        }
        detailed_results.append(r)
    
    # Generate Report
    print(f"\n{'='*120}")
    print(f"SHOPPING ADMIN BENCHMARK REPORT (Reddit-style Investigation)")
    print(f"{'='*120}")
    
    header = f"{'Category':<35} | {'Count':<5} | {'Invest':<6} | {'Reason':<6} | {'Decide':<6} | {'Evid(0-7)':<10} | {'Funnel':<6}"
    print(header)
    print("-" * 120)
    
    for cat in sorted(summary["by_category"].keys()):
        stats = summary["by_category"][cat]
        n = stats["count"]
        if n > 0:
            inv = stats["ind_investigation"] / n
            res = stats["ind_reasoning"] / n
            dec = stats["ind_decision"] / n
            evid = stats["evidence_score_avg"] / n
            funnel = stats["funnel_success"] / n
            
            print(f"{cat:<35} | {n:<5} | {inv*100:4.1f}% | {res*100:4.1f}% | {dec*100:4.1f}% | {evid:5.2f}/7    | {funnel*100:4.1f}%")
    
    print("=" * 120)
    print(f"\nTotal tasks analyzed: {summary['total']}")
    
    # Calculate overall averages
    total_inv = sum(stats["ind_investigation"] for stats in summary["by_category"].values())
    total_res = sum(stats["ind_reasoning"] for stats in summary["by_category"].values())
    total_dec = sum(stats["ind_decision"] for stats in summary["by_category"].values())
    total_funnel = sum(stats["funnel_success"] for stats in summary["by_category"].values())
    
    if summary["total"] > 0:
        print(f"\nOverall Averages:")
        print(f"  Investigation: {total_inv/summary['total']*100:.1f}%")
        print(f"  Reasoning:     {total_res/summary['total']*100:.1f}%")
        print(f"  Decision:      {total_dec/summary['total']*100:.1f}%")
        print(f"  Funnel:        {total_funnel/summary['total']*100:.1f}%")
    
    # Save outputs
    print(f"\nSaving summary to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(dict(summary), f, indent=2, default=dict)
    
    detailed_path = str(Path(output_file).parent / "all_results_shopping_comprehensive.json")
    print(f"Saving detailed results to {detailed_path}...")
    with open(detailed_path, 'w') as f:
        json.dump(detailed_results, f, indent=2)
    
    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Comprehensive analysis for Shopping Admin Benchmark")
    parser.add_argument("--results", required=True, help="Path to all_results.json")
    parser.add_argument("--tasks", default="pathways_tasks_sample30.json", help="Path to tasks JSON file")
    parser.add_argument("--output", default="analysis_shopping_comprehensive.json", help="Output file path")
    args = parser.parse_args()
    
    analyze_shopping_results(args.results, args.tasks, args.output)
