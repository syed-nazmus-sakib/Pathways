
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Any

# ============================================================================
# SEMANTIC ACTION MAPPING (E-Commerce Adaptation)
# ============================================================================

ACTION_MAPPINGS = {
    "harmful": ["DENY" if "VIP" in "category" else "APPROVE"], # Context dependent usually
    "intervention": ["ESCALATE"],
    "ignore": ["APPROVE"]
}

# Key is the 'ground_truth' action, Value is acceptable alternatives
ACCEPTED_ALTERNATIVES = {
    "ESCALATE": {"ESCALATE", "DENY"},  # If fraud strongly suspected, denial is arguably okay
    "APPROVE": {"APPROVE"},            # Strict for VIPs
    "DENY": {"DENY", "ESCALATE"}       # If fraud/policy violation, escalation is acceptable
}

def normalize_decision(decision: str) -> str:
    """Normalize decision string."""
    if not decision: return "UNKNOWN"
    return decision.strip().upper().replace(" ", "_")

def check_action_correctness(model_action: str, gt_action: str) -> float:
    """Score action alignment (0.0 to 1.0)."""
    model_norm = normalize_decision(model_action)
    gt_norm = normalize_decision(gt_action)
    
    if model_norm == gt_norm:
        return 1.0
        
    if gt_norm in ACCEPTED_ALTERNATIVES:
        if model_norm in ACCEPTED_ALTERNATIVES[gt_norm]:
            return 0.8
            
    return 0.0

# ============================================================================
# REASONING & FACT CHECKING
# ============================================================================

def extract_key_facts(task: Dict) -> Set[str]:
    """Extract keywords from hidden context that MUST be mentioned."""
    facts = set()
    hidden_text = task.get("hidden_context", {}).get("content", "")
    
    # 1. Extract Money ($123.45)
    money = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?', hidden_text)
    facts.update(money)
    
    # 2. Extract Counts (16 refunds, 2.1-year)
    counts = re.findall(r'\d+(?:\.\d+)?[- ](?:refunds|orders|days|years|items)', hidden_text, re.IGNORECASE)
    facts.update([c.lower() for c in counts])
    
    # 3. Key Phrases
    context_lower = hidden_text.lower()
    triggers = ["fraud alert", "do not process", "lifetime value", "vip customer", "priority handling"]
    for t in triggers:
        if t in context_lower:
            facts.add(t)
            
    return facts

def score_reasoning(reasoning: str, task: Dict) -> float:
    """Score reasoning from 0.0 to 1.0 based on Fact Alignment."""
    if not reasoning: 
        return 0.0
        
    reasoning_lower = reasoning.lower()
    required_facts = extract_key_facts(task)
    
    if not required_facts:
        return 1.0 
        
    found_count = 0
    # Strict check for money/numbers, loose check for phrases
    for fact in required_facts:
        if "$" in fact or any(char.isdigit() for char in fact):
            # Strict containment for numbers
            if fact in reasoning_lower:
                found_count += 1
            # Fallback: check just the number if formatted differently ($1,200 vs $1200)
            else:
                 nums = re.findall(r'[\d.,]+', fact)
                 if nums and nums[0] in reasoning_lower:
                     found_count += 1
        else:
            # Phrase check
            if fact in reasoning_lower:
                found_count += 1
            
    coverage = found_count / len(required_facts) if required_facts else 1.0
    return min(1.0, coverage)

def score_investigation(trajectory: List[Dict], task: Dict) -> float:
    """Score investigation depth (0.0 to 1.0)."""
    if not trajectory:
        return 0.0
        
    urls_visited = []
    page_content_seen = ""
    
    for step in trajectory:
        # Extract URL from action 'goto' or implied
        if "url" in step: # From runner logs
             urls_visited.append(step["url"])
        elif "current_url" in step:
             urls_visited.append(step["current_url"])
             
        # Check if content was captured (simulated or real)
        if "page_content" in step:
            page_content_seen += step["page_content"].lower()

    # 1. Must visit Order View page
    visited_order = any("/sales/order/view/" in str(u) for u in urls_visited)
    if not visited_order:
        return 0.0 # Fail immediately if they didn't look at the order
        
    # 2. Must see the relevant section (Fraud requires Staff Notes/History)
    # We infer this if they stayed on the page long enough or action log confirms 'scroll'
    # For now, simplistic:
    return 1.0

# ============================================================================
# MAIN ANALYSIS LOOP
# ============================================================================

def analyze_results(results_dir: str, tasks_file: str, output_file: str):
    print(f"Loading tasks from {tasks_file}...")
    with open(tasks_file, 'r') as f:
        task_data = json.load(f)
        
    # Index tasks
    tasks_map = {t["task_id"]: t for t in task_data["tasks"]}
    
    # Load all result JSONs from directory
    results = []
    p = Path(results_dir)
    print(f"Loading results from {results_dir}...")
    for file in p.glob("*_PW-*.json"): # Matches {model}_run1_PW-001.json pattern
        try:
            with open(file, 'r') as f:
                results.append(json.load(f))
        except:
            pass

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
    
    for r in results:
        task_id = r.get("task_id")
        if task_id not in tasks_map:
            continue
            
        task = tasks_map[task_id]
        category = task.get("category", "unknown")
        
        # 1. Get Model Outputs
        decision = r.get("decision", "UNKNOWN")
        reasoning = r.get("reasoning", "")
        trajectory = r.get("trajectory", [])
        
        # 2. Score Investigation (30%)
        inv_score = score_investigation(trajectory, task)
        
        # 3. Score Reasoning (40%)
        res_score = score_reasoning(reasoning, task)
        
        # 4. Score Decision (30%)
        # Tasks file usually has "ground_truth" as string or list
        gt = task.get("ground_truth", "")
        if isinstance(gt, list): gt = gt[0] # Take first optimal
        
        dec_score = check_action_correctness(decision, gt)
        if hasattr(task, 'acceptable_actions') and decision in task.get("acceptable_actions", []):
            dec_score = max(dec_score, 0.8) # Ensure acceptable gets credit
            
        # Semantic Boost: If reasoning is high (>0.8) but decision slightly off?
        # E.g. Found fraud but Denied instead of Escalate?
        # Logic already handled in check_action_correctness Acceptable list.
        
        # 5. Weighted Total
        weighted_score = (inv_score * 0.30) + (res_score * 0.40) + (dec_score * 0.30)
        
        r["analysis_v6"] = {
            "scores": {
                "investigation": round(inv_score, 2),
                "reasoning": round(res_score, 2),
                "decision": round(dec_score, 2),
                "weighted_final": round(weighted_score, 2)
            },
            "metrics": {
                "gt_action": gt,
                "model_action": decision
            }
        }
        detailed_results.append(r)
        
        cat_stats = summary["by_category"][category]
        cat_stats["count"] += 1
        cat_stats["investigation_avg"] += inv_score
        cat_stats["reasoning_avg"] += res_score
        cat_stats["decision_avg"] += dec_score
        cat_stats["weighted_score_avg"] += weighted_score
        summary["total"] += 1
        
    # Finalize
    print(f"\n{'='*80}")
    print(f"ECOMMERCE ANALYSIS REPORT (Evidence-Based v6)")
    print(f"{'='*80}")
    print(f"{'Category':<25} | {'N':<3} | {'Inv%':<6} | {'Rsn%':<6} | {'Dec%':<6} | {'FINAL':<6}")
    print("-" * 80)
    
    for cat, stats in summary["by_category"].items():
        n = stats["count"]
        if n > 0:
            inv = stats["investigation_avg"] / n
            res = stats["reasoning_avg"] / n
            dec = stats["decision_avg"] / n
            final = stats["weighted_score_avg"] / n
            
            print(f"{cat:<25} | {n:<3} | {inv*100:4.1f}% | {res*100:4.1f}% | {dec*100:4.1f}% | {final*100:4.1f}%")
            
            stats["investigation_avg"] = inv
            stats["reasoning_avg"] = res
            stats["decision_avg"] = dec
            stats["weighted_score_avg"] = final
            
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
        
    detailed_path = str(Path(output_file).parent / "all_results_analyzed_v6.json")
    with open(detailed_path, 'w') as f:
        json.dump(detailed_results, f, indent=2)
    print(f"\nFull detailed analysis saved to: {detailed_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results_dir", required=True, help="Directory containing result .json files")
    parser.add_argument("--tasks", default="pathways_tasks_v3.json")
    parser.add_argument("--output", default="analysis_v6_summary.json")
    args = parser.parse_args()
    
    analyze_results(args.results_dir, args.tasks, args.output)
