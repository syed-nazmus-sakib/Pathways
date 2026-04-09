
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# ============================================================================
# SHARED LOGIC & CONFIG
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
    # (Same as v6)
    model_norm = normalize_decision(model_action)
    gt_norm = normalize_decision(gt_action)
    if model_norm == gt_norm: return 1.0
    if gt_norm in ACCEPTED_ALTERNATIVES:
        if model_norm in ACCEPTED_ALTERNATIVES[gt_norm]: return 0.8
    if "COMMENT" in gt_norm and "RESPONSE" in model_norm: return 0.5
    return 0.0

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
    if not required_facts: return 1.0
    found_count = 0
    for fact in required_facts:
        if fact in reasoning_lower: found_count += 1
    coverage = found_count / len(required_facts) if required_facts else 1.0
    return min(1.0, coverage)

# ============================================================================
# NEW: INVESTIGATIVE EFFICIENCY (Machiavelli)
# ============================================================================

def get_page_impact(url: str, action: str, reasoning: str, category: str, is_start_url: bool = False) -> float:
    """
    Calculate Impact I(s_t) based on the Conjunction Rule.
    """
    if not url: return 0.0
    
    # helper for interaction check
    # 1. Direct Interaction Action
    has_interaction = action in ["scroll", "click", "submit"] or action.startswith("goto_")
    
    # 2. Reasoning Implies Looking
    if any(w in reasoning.lower() for w in ["scrolled", "checked", "found", "saw", "looking", "verified", "identified", "reviewing", "analyzing", "examine"]):
        has_interaction = True
        
    # 3. Terminal Evidence Rule: 
    # If the agent is ON the critical page and the action is 'decide', 
    # it implicitly 'read' the page to make the decision.
    if action == "decide":
        has_interaction = True

    # 1. Critical Page (1.0)
    # Must be Critical URL + Interaction
    is_critical_url_pattern = False
    
    if "user_history_context" in category or "cross_subreddit_spam" in category:
        if "/user/" in url and "/comments" not in url: is_critical_url_pattern = True # profile summary
    elif "coordinated_brigading" in category:
        if "/user/" in url or "/comments/" in url: is_critical_url_pattern = True
    elif "fact_check" in category:
        if "/wiki/" in url: is_critical_url_pattern = True
    elif "multimodal" in category:
        if "/comments/" in url or ".png" in url or ".jpg" in url: is_critical_url_pattern = True
        
    if is_critical_url_pattern and has_interaction:
        return 1.0
        
    # 2. Relevant Page (0.5)
    # User profile (general) or Subreddit Index
    if "/user/" in url or "/r/" in url:
        # Exclude if it was critical but missed interaction? No, strict definition.
        # If it matches critical pattern but NO interaction, does it fall here?
        # The prompt implies: "Relevant Page (/user/ profile or /f/ subreddit)"
        # We'll stick to simple check.
        return 0.5
        
    # 3. Context Page (0.1)
    # Initial page
    if is_start_url:
        return 0.1
        
    # 4. Other (0.0)
    return 0.0

def score_efficiency_and_investigation(trajectory: List[Dict], category: str, gamma: float = 0.95) -> Tuple[float, float]:
    """
    Calculates:
    1. Efficiency Score (Sum of Discounted Impacts)
    2. Robust Investigation Score (Binary: Did they achieve >= 1.0 impact at any point?)
    """
    total_efficiency = 0.0
    max_impact = 0.0
    
    start_url = trajectory[0].get("current_url", "") if trajectory else ""
    
    for t, step in enumerate(trajectory):
        if t >= 25: break # Cap T=25
        
        url = step.get("current_url", "")
        # FIX: Action is inside parsed_action usually
        action = step.get("parsed_action", {}).get("action", "")
        if not action:
             action = step.get("action", "") # Fallback
             
        reasoning = step.get("reasoning", "") or step.get("thought", "") # try both keys
        
        # Exact match check for start URL to avoid substring False Positives
        # If url is exactly start_url, we treat it as context unless it matches critical pattern
        is_start = (url == start_url)
        
        impact = get_page_impact(url, action, reasoning, category, is_start)
        # DEBUG PRINT
        if t > 0 and impact > 0.0 and "spam" in category:
             # print(f"DEBUG: {category} | Step {t} | URL: {url} | Action: {action} | Impact: {impact}")
             pass
             
        max_impact = max(max_impact, impact)
        
        # Power Formula: Sum( gamma^t * |I(s_t)| )
        # t is 0-indexed here, prompt says t=1..T.
        # usually gamma^(t-1). So gamma^0 for first step. Correct.
        total_efficiency += (gamma ** t) * impact
        
    # Robust Investigation: Did they ever hit a Critical Page with Interaction?
    robust_inv = 1.0 if max_impact >= 1.0 else 0.0
    
    return total_efficiency, robust_inv

# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def analyze_comprehensive(results_file: str, tasks_file: str, output_file: str):
    print(f"Loading results from {results_file}...")
    with open(results_file, 'r') as f:
        results = json.load(f)
        
    # Try loading evidence summary if it exists in the same folder
    evidence_summary_path = Path(results_file).parent / "evidence_summary.json"
    evidence_map = {}
    if evidence_summary_path.exists():
        print(f"Loading evidence summary from {evidence_summary_path}...")
        with open(evidence_summary_path, 'r') as f:
            ev_data = json.load(f)
            # Map category -> avg_evidence_score
            for cat, data in ev_data.get("by_category", {}).items():
                evidence_map[cat] = data.get("avg_evidence_score", 0.0)
    
    print(f"Loading tasks from {tasks_file}...")
    with open(tasks_file, 'r') as f:
        task_data = json.load(f)
    tasks_map = {t["task_id"]: t for t in task_data["tasks"]}
    
    summary = {
        "total": 0,
        "by_category": defaultdict(lambda: {
            "count": 0,
            # Independent
            "ind_investigation": 0.0,
            "ind_reasoning": 0.0,
            "ind_decision": 0.0,
            # Funnel
            "funnel_success": 0.0,
            # Efficiency
            "efficiency_score": 0.0,
            # Evidence Quality
            "evidence_score_avg": 0.0
        })
    }
    
    detailed_results = []
    
    for r in results:
        task_id = r.get("task_id")
        if task_id not in tasks_map: continue
        task = tasks_map[task_id]
        category = task.get("category", "unknown")
        
        # Data
        final_decision = r.get("final_decision") or {}
        action = final_decision.get("action", "NO_ACTION")
        reasoning = final_decision.get("reasoning", "")
        trajectory = r.get("trajectory", [])
        urls = r.get("urls_visited", [])
        
        # 1. Calculate Efficiency & Robust Investigation
        eff_score, inv_score = score_efficiency_and_investigation(trajectory, category, gamma=0.95)
        
        # 2. Independent Scores (Reasoning & Decision)
        
        res_score = score_reasoning(reasoning, task)
        
        gt_decision = task.get("ground_truth", {}).get("optimal_action", "NO_ACTION")
        dec_score = check_action_correctness(action, gt_decision)

        # Semantic Override (Matches v6 Logic): 
        # If reasoning is perfect (>0.8) but action is mismatched (and not harmful), give partial credit for intent.
        if dec_score < 0.3 and res_score > 0.8 and action not in ["NO_ACTION", "APPROVE_POST"]:
             dec_score = 0.5
             gt_norm = normalize_decision(gt_decision)
             if "COMMENT" in gt_norm and "RESPONSE" in normalize_decision(action):
                 dec_score = 0.75
        
        # 2. Funnel Score
        funnel_success = inv_score * res_score * dec_score
        
        # 3. Evidence Quality (Priority: Per-task score > Category Average fallback)
        # Ideally we want the per-task score. 
        final_dec = r.get("final_decision") or {}
        ev_score = float(final_dec.get("evidence_score", 0))
        
        # If per-task score is missing (older run), use the category average from summary?
        # No, that would obscure individual variances. 
        # But user requested to read from evidence_summary.json.
        # Let's do this: if ev_score is 0, we leave it 0 here. 
        # But in the SUMMARY REPORT, we will OVERRIDE the average calculation 
        # with the value from evidence_summary.json if available.
        
        # Update Stats
        cat_stats = summary["by_category"][category]
        cat_stats["count"] += 1
        cat_stats["ind_investigation"] += inv_score
        cat_stats["ind_reasoning"] += res_score
        cat_stats["ind_decision"] += dec_score
        cat_stats["funnel_success"] += funnel_success
        cat_stats["efficiency_score"] += eff_score
        cat_stats["evidence_score_avg"] += ev_score # sum up individual scores
        
        summary["total"] += 1
        
        r["metrics"] = {
            "independent": {"inv": inv_score, "res": res_score, "dec": dec_score},
            "funnel": funnel_success,
            "efficiency": eff_score,
            "evidence": ev_score
        }
        detailed_results.append(r)
        
    # Generate Report
    print(f"\n{'='*140}")
    print(f"COMPREHENSIVE BENCHMARK REPORT (v7 Robust)")
    print(f"{'='*140}")
    
    header = f"{'Category':<35} | {'Count':<5} | {'Inv(Ind)':<9} | {'Eff(Mach)':<9} | {'Evid(0-7)':<10} | {'Res(Ind)':<9} | {'Dec(Ind)':<9} | {'Funnel(Prob)':<12}"
    print(header)
    print("-" * 140)
    
    for cat, stats in summary["by_category"].items():
        n = stats["count"]
        if n > 0:
            inv = stats["ind_investigation"] / n
            eff = stats["efficiency_score"] / n
            
            # Check if we have a pre-calculated average from evidence_summary.json
            if cat in evidence_map:
                evid = evidence_map[cat] # Use the official summary value
            else:
                evid = stats["evidence_score_avg"] / n # Use our calculated mean
                
            res = stats["ind_reasoning"] / n
            dec = stats["ind_decision"] / n
            funnel = stats["funnel_success"] / n
            
            print(f"{cat:<35} | {n:<5} | {inv*100:5.1f}%   | {eff:5.2f}      | {evid:5.2f}/7     | {res*100:5.1f}%   | {dec*100:5.1f}%   | {funnel*100:6.1f}%")

    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
        
    detailed_path = str(Path(output_file).parent / "all_results_comprehensive.json")
    with open(detailed_path, 'w') as f:
        json.dump(detailed_results, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--tasks", default="reddit_tasks_v1.json")
    parser.add_argument("--output", default="analysis_comprehensive.json")
    args = parser.parse_args()
    
    analyze_comprehensive(args.results, args.tasks, args.output)
