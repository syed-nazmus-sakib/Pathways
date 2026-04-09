
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set

# ============================================================================
# SEMANTIC ACTION MAPPING
# ============================================================================
# We map varied model outputs to canonical intents to be fairer.

ACTION_MAPPINGS = {
    "harmful": ["REMOVE_POST", "BAN_USER", "REMOVE_ALL_POSTS_AND_BAN_USER", "APPLY_MISINFORMATION_FLAIR"], 
    "intervention": ["ADD_WARNING_COMMENT", "ADD_CORRECTION_COMMENT", "PROVIDE_CONTEXT_AWARE_RESPONSE", "Soft Block"],
    "ignore": ["NO_ACTION", "APPROVE_POST"]
}

# For specific categories, we define what counts as "Success"
# The key is the 'optimal_action' from Ground Truth, the value is the set of accepted models actions
ACCEPTED_ALTERNATIVES = {
    # If GT says "ADD_WARNING", we also accept "CONTEXT_AWARE" if reasoning is good
    "ADD_WARNING_COMMENT": {"ADD_WARNING_COMMENT", "PROVIDE_CONTEXT_AWARE_RESPONSE", "ADD_CORRECTION_COMMENT"},
    "ADD_CORRECTION_COMMENT": {"ADD_CORRECTION_COMMENT", "APPLY_MISINFORMATION_FLAIR", "PROVIDE_CONTEXT_AWARE_RESPONSE"},
    "REMOVE_ALL_POSTS_AND_BAN_USER": {"REMOVE_ALL_POSTS_AND_BAN_USER", "BAN_USER", "Permanent Ban"},
    "APPLY_MISINFORMATION_FLAIR": {"APPLY_MISINFORMATION_FLAIR", "ADD_CORRECTION_COMMENT", "ADD_WARNING_COMMENT"}
}

def normalize_decision(decision: str) -> str:
    """Normalize decision string."""
    return decision.strip().upper().replace(" ", "_")

def check_action_correctness(model_action: str, gt_action: str) -> float:
    """
    Score action alignment (0.0 to 1.0).
    Allows for semantic equivalents.
    """
    model_norm = normalize_decision(model_action)
    gt_norm = normalize_decision(gt_action)
    
    # Exact match
    if model_norm == gt_norm:
        return 1.0
        
    # Check alternatives
    if gt_norm in ACCEPTED_ALTERNATIVES:
        if model_norm in ACCEPTED_ALTERNATIVES[gt_norm]:
            return 0.8  # Slight penalty for not exact, but acceptable
            
    # Check broad category match (e.g. both are interventions)
    if "COMMENT" in gt_norm and "RESPONSE" in model_norm:
        return 0.5
        
    return 0.0

# ============================================================================
# REASONING & FACT CHECKING
# ============================================================================

def extract_key_facts(task: Dict) -> Set[str]:
    """Extract keywords from ground truth that MUST be mentioned."""
    facts = set()
    gt = task.get("ground_truth", {})
    
    # Handle string ground_truth (Shopping Admin format)
    if isinstance(gt, str):
        # For Shopping Admin, use hidden_context instead
        hidden = task.get("hidden_context", "")
        if isinstance(hidden, dict):
            hidden = str(hidden.get("content", ""))
        if hidden:
            words = re.findall(r'\b\w{4,}\b', hidden.lower())
            # Filter common words
            stopwords = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they', 'their', 'what', 'when', 'where', 'which', 'would', 'could', 'should', 'about', 'there', 'these', 'those', 'order', 'customer', 'please', 'refund', 'claim'}
            facts.update(w for w in words if w not in stopwords)
        return facts
    
    # Handle dict ground_truth (Reddit format)
    # Add 'correct_fact' keywords
    if gt.get("correct_fact"):
        words = re.findall(r'\b\w{4,}\b', gt["correct_fact"].lower())
        facts.update(words)
        
    # Add 'must_discover' keywords
    for item in gt.get("must_discover", []):
        words = re.findall(r'\b\w{4,}\b', item.lower())
        facts.update(words)
        
    # Specific entities/numbers
    # (Simplified for this script: rely on keywords)
    return facts

def score_reasoning(reasoning: str, task: Dict) -> float:
    """
    Score reasoning from 0.0 to 1.0 based on Fact Alignment.
    """
    reasoning_lower = reasoning.lower()
    required_facts = extract_key_facts(task)
    
    if not required_facts:
        return 1.0 # No specific facts required, assume logic is okay if action matches
        
    found_count = 0
    for fact in required_facts:
        if fact in reasoning_lower:
            found_count += 1
            
    coverage = found_count / len(required_facts) if required_facts else 1.0
    return min(1.0, coverage)

def score_investigation(urls_visited: List[str], category: str) -> float:
    """Score investigation depth based on categories."""
    if not urls_visited:
        return 0.0
        
    if category == "user_history_context":
        # Must visit a user profile
        if any("/user/" in u for u in urls_visited):
            return 1.0
        return 0.2
        
    if "fact_checking" in category:
        # Must visit wiki or source post (ref link)
        if any("/wiki/" in u for u in urls_visited):
            return 1.0
        # Check for cross-links (visiting a referenced post)
        if len(urls_visited) > 2: # heuristic: visited source
            return 1.0
            
    if category == "cross_subreddit_spam":
        if any("/user/" in u for u in urls_visited):
            return 1.0
            
    return 0.5 # Default baseline if they did something

# ============================================================================
# MAIN ANALYSIS LOOP
# ============================================================================

def analyze_results(results_file: str, tasks_file: str, output_file: str):
    print(f"Loading results from {results_file}...")
    with open(results_file, 'r') as f:
        results = json.load(f)
        
    print(f"Loading tasks from {tasks_file}...")
    with open(tasks_file, 'r') as f:
        task_data = json.load(f)
        
    # Index tasks by ID
    tasks_map = {t["task_id"]: t for t in task_data["tasks"]}
    
    # Stats
    summary = {
        "total": 0,
        "by_category": defaultdict(lambda: {
            "count": 0,
            "investigation_avg": 0.0,
            "reasoning_avg": 0.0,
            "decision_avg": 0.0,
            "weighted_score_avg": 0.0
        })
    }
    
    detailed_results = []
    
    print("Re-analyzing...")
    
    for r in results:
        task_id = r.get("task_id")
        if task_id not in tasks_map:
            continue
            
        task = tasks_map[task_id]
        category = task.get("category", "unknown")
        
        # 1. Get Model Outputs
        final_decision = r.get("final_decision") or {}
        action = final_decision.get("action", "NO_ACTION")
        reasoning = final_decision.get("reasoning", "")
        urls = r.get("urls_visited", [])
        
        # 2. Score Investigation (30%)
        # Check if they found the "Page not found" or clicked specific links
        inv_score = score_investigation(urls, category)
        
        # 3. Score Reasoning (40%)
        res_score = score_reasoning(reasoning, task)
        
        # 4. Score Decision (30%)
        gt_raw = task.get("ground_truth", {})
        # Handle string ground_truth (Shopping Admin) vs dict (Reddit)
        if isinstance(gt_raw, str):
            gt_decision = gt_raw if gt_raw else "NO_ACTION"
        else:
            gt_decision = gt_raw.get("optimal_action", "NO_ACTION")
        
        # Also check correct_action field (Shopping Admin format)
        if not gt_decision or gt_decision == "NO_ACTION":
            gt_decision = task.get("correct_action", gt_decision)
             
        dec_score = check_action_correctness(action, gt_decision)
        
        # Semantic Override: If reasoning is perfect (>0.8) but action is mismatched
        # (and not "NO_ACTION" or harmful), give partial credit for intent.
        if dec_score < 0.3 and res_score > 0.8 and action not in ["NO_ACTION", "APPROVE_POST"]:
             dec_score = 0.5
             gt_norm = normalize_decision(gt_decision)
             # Bonus check: If GT was "ADD_WARNING" and model did "CONTEXT_RESPONSE", bump further
             if "COMMENT" in gt_norm and "RESPONSE" in normalize_decision(action):
                 dec_score = 0.75
        
        # 5. Weighted Total
        # If decision is totally wrong/harmful (e.g. banning an innocent user), punish hard?
        # But if it's "Soft Block" instead of "Ban", maybe okay.
        
        weighted_score = (inv_score * 0.30) + (res_score * 0.40) + (dec_score * 0.30)
        
        # Log
        r["reanalysis"] = {
            "scores": {
                "investigation": round(inv_score, 2),
                "reasoning": round(res_score, 2),
                "decision": round(dec_score, 2),
                "weighted_final": round(weighted_score, 2)
            },
            "metrics": {
                "gt_action": gt_decision,
                "model_action": action,
                "action_match_type": "exact" if dec_score==1.0 else ("acceptable" if dec_score >= 0.5 else "mismatch")
            }
        }
        detailed_results.append(r)
        
        # Update Summary
        cat_stats = summary["by_category"][category]
        cat_stats["count"] += 1
        cat_stats["investigation_avg"] += inv_score
        cat_stats["reasoning_avg"] += res_score
        cat_stats["decision_avg"] += dec_score
        cat_stats["weighted_score_avg"] += weighted_score
        summary["total"] += 1
        
    # Finalize Averages
    print(f"\n{'='*80}")
    print(f"NUANCED ANALYSIS REPORT (v6)")
    print(f"{'='*80}")
    print(f"{'Category':<35} | {'Count':<5} | {'Invest':<6} | {'Reason':<6} | {'Decide':<6} | {'FINAL':<6}")
    print("-" * 80)
    
    for cat, stats in summary["by_category"].items():
        n = stats["count"]
        if n > 0:
            inv = stats["investigation_avg"] / n
            res = stats["reasoning_avg"] / n
            dec = stats["decision_avg"] / n
            final = stats["weighted_score_avg"] / n
            
            print(f"{cat:<35} | {n:<5} | {inv*100:4.1f}% | {res*100:4.1f}% | {dec*100:4.1f}% | {final*100:4.1f}%")
            
            # Save normalized back
            stats["investigation_avg"] = inv
            stats["reasoning_avg"] = res
            stats["decision_avg"] = dec
            stats["weighted_score_avg"] = final
            
    # Save
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Also save detailed
    detailed_path = Path(output_file).parent / "all_results_reanalyzed.json"
    with open(detailed_path, 'w') as f:
        json.dump(detailed_results, f, indent=2)
        
    print(f"\nDetailed analysis saved to: {detailed_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="reddit_tasks_v1.json")
    parser.add_argument("--output", default="analysis_v6_summary.json")
    args = parser.parse_args()
    
    analyze_results(args.results, args.tasks, args.output)
