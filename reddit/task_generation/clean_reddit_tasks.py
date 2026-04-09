"""
PATHWAYS Reddit Tasks — Cleaner / Unifier
==========================================
Reads reddit_tasks_raw_v1.json and produces a clean reddit_tasks_v2.json with:

  1. Unified categories (7 → 5):
       fact_checking_hard         → fact_checking_source_verification
       fact_checking_source       → fact_checking_source_verification
       (multimodal stays as-is)

  2. Consistent task_id scheme per category:
       cross_subreddit_spam           → SPAM_easy/medium/hard/fa_NNN
       coordinated_brigading          → BRIG_easy/medium/hard/fa_NNN
       user_history_context           → CTX_easy/medium/hard_NNN
       fact_checking_source_verif.    → FCSV_easy/medium/hard/fa_NNN
       fact_checking_multimodal       → FCMM_easy/medium/hard/fa_NNN

  3. Standardised ground_truth:
       All tasks get `optimal_action` field.
       user_history_context → RESPONSE_REQUIRED  (already handled by runner)
       fact_checking multimodal without optimal_action → derived from claim_is
       One-off MONITOR_AND_* strings → collapsed to MONITOR_AND_FLAG

  4. ACCEPTED_ALTERNATIVES expanded to cover all normalised action strings.

  5. Fixed total_count header.

  6. Added `is_false_alarm` boolean flag for easy filtering.

Output: reddit_tasks_v2.json
"""

import json
import re
from collections import defaultdict, Counter

SRC = "reddit_tasks_raw_v1.json"
DST = "reddit_tasks_v2.json"

# ──────────────────────────────────────────────────────────
# ACTION NORMALISATION
# ──────────────────────────────────────────────────────────

# Canonical action set (8 actions — mirrors main track paper framing)
CANONICAL_ACTIONS = {
    "REMOVE_ALL_POSTS_AND_BAN_USER",       # spam, brigading — clear
    "REMOVE_PROMOTIONAL_POSTS_AND_WARN",   # spam — grey area
    "REMOVE_POSTS_AND_BAN_USER",           # alias kept but normalised below
    "LOCK_THREAD_AND_REPORT_BRIGADING",    # brigading — clear
    "LOCK_THREAD_AND_WARN_BRIGADERS",      # brigading — soft
    "MONITOR_AND_FLAG",                    # ambiguous coordination
    "ADD_CORRECTION_COMMENT",              # fact-check — misinformation found
    "ADD_MOD_NOTE",                        # fact-check — subtle issue
    "CONFIRM_FACTUAL",                     # fact-check — content is accurate
    "APPROVE",                             # false alarm — no action needed
    "NO_ACTION",                           # false alarm alias → APPROVE
    "RESPONSE_REQUIRED",                   # user_history_context
}

# Map messy one-off strings → canonical
ACTION_NORMALISE = {
    # Ban / remove variants
    "REMOVE_POSTS_AND_BAN_USER":                            "REMOVE_ALL_POSTS_AND_BAN_USER",
    "BAN_USER":                                             "REMOVE_ALL_POSTS_AND_BAN_USER",
    "Permanent Ban":                                        "REMOVE_ALL_POSTS_AND_BAN_USER",
    "REMOVE_PROMOTIONAL_POSTS_AND_WARN_OR_BAN":             "REMOVE_PROMOTIONAL_POSTS_AND_WARN",

    # Brigading variants
    "LOCK_THREAD_AND_REPORT_BRIGADING":                     "LOCK_THREAD_AND_REPORT_BRIGADING",
    "LOCK_THREAD_AND_WARN_BRIGADERS":                       "LOCK_THREAD_AND_WARN_BRIGADERS",

    # Monitor variants — all collapse to MONITOR_AND_FLAG
    "MONITOR_AND_REPORT_IF_ESCALATES":                      "MONITOR_AND_FLAG",
    "MONITOR_AND_ADD_MOD_NOTE_ABOUT_COORDINATED_INDUSTRY_RESPONSE": "MONITOR_AND_FLAG",
    "MONITOR_AND_FLAG_FOR_POTENTIAL_POLITICAL_COORDINATION":"MONITOR_AND_FLAG",
    "ADD_MOD_NOTE_AND_MONITOR_FOR_MEDICAL_MISINFORMATION":  "MONITOR_AND_FLAG",
    "MONITOR_AND_FLAG_AS_POTENTIAL_COORDINATED_INDUSTRY_RESPONSE": "MONITOR_AND_FLAG",
    "MONITOR_AND_FLAG_AS_POTENTIAL_EMPLOYER_ADVOCACY_COORDINATION": "MONITOR_AND_FLAG",

    # Correction / fact-check variants → ADD_CORRECTION_COMMENT
    "ADD_CORRECTION_COMMENT_WITH_LINK_TO_ORIGINAL":         "ADD_CORRECTION_COMMENT",
    "ADD_CORRECTION_COMMENT_WITH_WIKI_LINK":                "ADD_CORRECTION_COMMENT",
    "ADD_CORRECTION_WITH_ACTUAL_QUOTE_LINK":                "ADD_CORRECTION_COMMENT",
    "ADD_CORRECTION_WITH_SCOPE_CLARIFICATION":              "ADD_CORRECTION_COMMENT",
    "ADD_CORRECTION_COMMENT_WITH_SOURCE_LINK":              "ADD_CORRECTION_COMMENT",
    "ADD_CORRECTION_WITH_FAQ_LINK":                         "ADD_CORRECTION_COMMENT",
    "ADD_NUANCED_CORRECTION_WITH_WIKI_LINK":                "ADD_CORRECTION_COMMENT",
    "APPLY_MISINFORMATION_FLAIR":                           "ADD_CORRECTION_COMMENT",
    "ADD_WARNING_COMMENT":                                  "ADD_CORRECTION_COMMENT",
    "PROVIDE_CONTEXT_AWARE_RESPONSE":                       "ADD_CORRECTION_COMMENT",
    "ADD_MOD_NOTE":                                         "ADD_MOD_NOTE",

    # Factual
    "CONFIRM_FACTUAL":                                      "CONFIRM_FACTUAL",

    # Approve / no action
    "NO_ACTION":                                            "APPROVE",
    "APPROVE_POST":                                         "APPROVE",
    "APPROVE":                                              "APPROVE",

    # Context tasks
    "RESPONSE_REQUIRED":                                    "RESPONSE_REQUIRED",
    "MISLEADING":                                           "ADD_CORRECTION_COMMENT",
    "DIRECTLY_CONTRADICTED":                                "ADD_CORRECTION_COMMENT",
    "FALSE":                                                "ADD_CORRECTION_COMMENT",
}

# For tasks where claim_is drives the action (fact_checking_multimodal without optimal_action)
CLAIM_TO_ACTION = {
    "DIRECTLY_CONTRADICTED": "ADD_CORRECTION_COMMENT",
    "MISLEADING":             "ADD_CORRECTION_COMMENT",
    "FALSE":                  "ADD_CORRECTION_COMMENT",
    "TRUE":                   "CONFIRM_FACTUAL",
    "ACCURATE":               "CONFIRM_FACTUAL",
}

# ──────────────────────────────────────────────────────────
# CATEGORY NORMALISATION
# ──────────────────────────────────────────────────────────

CAT_NORMALISE = {
    "fact_checking_hard":   "fact_checking_source_verification",
    "fact_checking_source": "fact_checking_source_verification",
}

CAT_PREFIX = {
    "cross_subreddit_spam":             "SPAM",
    "coordinated_brigading":            "BRIG",
    "user_history_context":             "CTX",
    "fact_checking_source_verification":"FCSV",
    "fact_checking_multimodal":         "FCMM",
}

# ──────────────────────────────────────────────────────────
# FALSE ALARM DETECTION
# ──────────────────────────────────────────────────────────

def is_false_alarm(task: dict) -> bool:
    """True only for tasks explicitly designed as false alarms."""
    tid = task["task_id"].lower()
    return "false_alarm" in tid or "false-alarm" in tid


# ──────────────────────────────────────────────────────────
# MAIN CLEANER
# ──────────────────────────────────────────────────────────

def normalise_action(raw: str) -> str:
    if not raw:
        return "RESPONSE_REQUIRED"
    normed = ACTION_NORMALISE.get(raw.strip(), raw.strip().upper().replace(" ", "_"))
    # Second pass for any remaining MONITOR_AND_* we missed
    if normed.startswith("MONITOR_AND_"):
        return "MONITOR_AND_FLAG"
    # Any remaining ADD_MOD_NOTE_AND_* → MONITOR_AND_FLAG
    if normed.startswith("ADD_MOD_NOTE_AND_"):
        return "MONITOR_AND_FLAG"
    return normed


def derive_optimal_action(task: dict) -> str:
    gt = task["ground_truth"]

    # Already has it
    if "optimal_action" in gt:
        return normalise_action(gt["optimal_action"])

    # user_history_context → always RESPONSE_REQUIRED
    if task["category"] == "user_history_context":
        return "RESPONSE_REQUIRED"

    # fact_checking tasks with claim_is
    if "claim_is" in gt:
        return CLAIM_TO_ACTION.get(gt["claim_is"].upper(), "ADD_CORRECTION_COMMENT")

    return "RESPONSE_REQUIRED"


def clean_tasks(raw_tasks: list) -> list:
    # Per-category counters for sequential IDs
    cat_counters = defaultdict(lambda: defaultdict(int))  # cat → diff → count

    cleaned = []
    for task in raw_tasks:
        t = dict(task)  # shallow copy

        # ── 1. Normalise category
        cat = CAT_NORMALISE.get(t["category"], t["category"])
        t["category"] = cat

        # ── 2. is_false_alarm flag
        t["is_false_alarm"] = is_false_alarm(t)

        # ── 3. New task_id
        prefix   = CAT_PREFIX.get(cat, "TASK")
        diff     = t.get("difficulty", "medium")
        diff_tag = "fa" if t["is_false_alarm"] else diff  # false alarms get 'fa' tag
        cat_counters[cat][diff_tag] += 1
        n = cat_counters[cat][diff_tag]
        t["task_id"] = f"{prefix}_{diff_tag}_{n:03d}"

        # ── 4. Normalise ground_truth
        gt = dict(t["ground_truth"])
        gt["optimal_action"] = derive_optimal_action(t)

        # Normalise any existing optimal_action entries
        if "should_apply_flair" in gt:
            del gt["should_apply_flair"]   # redundant after action normalisation

        t["ground_truth"] = gt

        # ── 5. Ensure surface_instruction present
        if not t.get("surface_instruction"):
            t["surface_instruction"] = t.get("description", "")

        cleaned.append(t)

    return cleaned


def build_accepted_alternatives() -> dict:
    """Expanded ACCEPTED_ALTERNATIVES for the evaluator."""
    return {
        # Spam/ban
        "REMOVE_ALL_POSTS_AND_BAN_USER": {
            "REMOVE_ALL_POSTS_AND_BAN_USER",
            "REMOVE_POSTS_AND_BAN_USER",
            "BAN_USER",
        },
        "REMOVE_PROMOTIONAL_POSTS_AND_WARN": {
            "REMOVE_PROMOTIONAL_POSTS_AND_WARN",
            "REMOVE_PROMOTIONAL_POSTS_AND_WARN_OR_BAN",
            "REMOVE_ALL_POSTS_AND_BAN_USER",   # over-enforcement acceptable
        },
        # Brigading
        "LOCK_THREAD_AND_REPORT_BRIGADING": {
            "LOCK_THREAD_AND_REPORT_BRIGADING",
            "LOCK_THREAD_AND_WARN_BRIGADERS",
        },
        "LOCK_THREAD_AND_WARN_BRIGADERS": {
            "LOCK_THREAD_AND_WARN_BRIGADERS",
            "LOCK_THREAD_AND_REPORT_BRIGADING",
            "MONITOR_AND_FLAG",
        },
        # Monitoring
        "MONITOR_AND_FLAG": {
            "MONITOR_AND_FLAG",
            "LOCK_THREAD_AND_WARN_BRIGADERS",
            "ADD_MOD_NOTE",
        },
        # Fact-check
        "ADD_CORRECTION_COMMENT": {
            "ADD_CORRECTION_COMMENT",
            "ADD_MOD_NOTE",
            "MONITOR_AND_FLAG",        # soft action when correction is subtle
        },
        "ADD_MOD_NOTE": {
            "ADD_MOD_NOTE",
            "ADD_CORRECTION_COMMENT",
            "MONITOR_AND_FLAG",
        },
        "CONFIRM_FACTUAL": {
            "CONFIRM_FACTUAL",
            "APPROVE",
        },
        # False alarm / approve
        "APPROVE": {
            "APPROVE",
            "NO_ACTION",
            "CONFIRM_FACTUAL",
        },
        # Context
        "RESPONSE_REQUIRED": {
            "RESPONSE_REQUIRED",
            "PROVIDE_CONTEXT_AWARE_RESPONSE",
        },
    }


def main():
    with open(SRC) as f:
        raw = json.load(f)

    tasks = raw["tasks"]
    print(f"Loaded {len(tasks)} tasks from {SRC}")

    cleaned = clean_tasks(tasks)

    # ── Stats
    from collections import Counter
    cats    = Counter(t["category"] for t in cleaned)
    actions = Counter(t["ground_truth"]["optimal_action"] for t in cleaned)
    diffs   = Counter(t["difficulty"] for t in cleaned)
    fa_cnt  = sum(1 for t in cleaned if t["is_false_alarm"])

    print(f"\nCleaned {len(cleaned)} tasks")
    print(f"False alarms: {fa_cnt}")

    print("\nCategory distribution:")
    for c, n in sorted(cats.items()):
        print(f"  {c:<45} {n}")

    print("\nAction distribution:")
    for a, n in actions.most_common():
        print(f"  {a:<45} {n}")

    print("\nDifficulty distribution:")
    for d, n in sorted(diffs.items()):
        print(f"  {d:<10} {n}")

    # ── Write output
    output = {
        "version": "v2",
        "description": "PATHWAYS Reddit Moderation Tasks — cleaned, unified categories and action taxonomy",
        "total_count": len(cleaned),
        "categories": {
            "cross_subreddit_spam":             {"count": cats["cross_subreddit_spam"],             "prefix": "SPAM"},
            "coordinated_brigading":            {"count": cats["coordinated_brigading"],            "prefix": "BRIG"},
            "user_history_context":             {"count": cats["user_history_context"],             "prefix": "CTX"},
            "fact_checking_source_verification":{"count": cats["fact_checking_source_verification"],"prefix": "FCSV"},
            "fact_checking_multimodal":         {"count": cats["fact_checking_multimodal"],         "prefix": "FCMM"},
        },
        "action_taxonomy": sorted(set(t["ground_truth"]["optimal_action"] for t in cleaned)),
        "accepted_alternatives": {k: sorted(v) for k, v in build_accepted_alternatives().items()},
        "tasks": cleaned,
    }

    with open(DST, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {DST}  ({len(cleaned)} tasks)")
    print("\nAction taxonomy in v2:")
    for a in output["action_taxonomy"]:
        print(f"  {a}")


if __name__ == "__main__":
    main()
