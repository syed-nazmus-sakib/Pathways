#!/usr/bin/env python3
"""
PATHWAYS Reddit Benchmark - Evidence-Based Evaluation v4
=========================================================
Properly calibrated evidence requirements based on actual task structure.

Key improvements:
- Category-specific evidence patterns (no longer requires ground_truth templates)
- Heuristic evidence scoring when explicit requirements missing
- Fixed investigation proof verification
- Realistic scoring that credits models providing good evidence

Usage:
    python run_reddit_benchmark_evidence_based.py --test
    python run_reddit_benchmark_evidence_based.py --models qwen32b gpt
    python run_reddit_benchmark_evidence_based.py --category coordinated_brigading
"""

import json
import time
import base64
import re
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
import traceback
from collections import defaultdict

OPENROUTER_KEY = "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"
BASE_URL = "http://localhost:9999"
MAX_STEPS = 25
MAX_PAGE_CHARS = 8000
LLM_TIMEOUT = 120
LLM_RETRIES = 3
TASK_TIMEOUT_SECONDS = 300

MODELS = {
    "qwen32b": "qwen/qwen3-vl-32b-instruct",
    "qwen235b": "qwen/qwen3-vl-235b-a22b-thinking",
    "gemini": "google/gemini-3-flash-preview",
    "gpt": "openai/gpt-5.2",
    "gpt5_1": "openai/gpt-4.1",
    "opus": "anthropic/claude-opus-4.5",
    "grok": "x-ai/grok-4.1-fast"
}

# ============================================================================
# EVIDENCE TIER CONFIGURATION
# ============================================================================

EVIDENCE_TIERS = {
    "STRICT": {
        "categories": [
            "user_history_context",
            "cross_subreddit_spam", 
            "coordinated_brigading",
            "fact_checking_source_verification"
        ],
        "min_evidence_score": 3,
        "min_words": 30,
        "requires_investigation_proof": True,
        "description": "High-stakes decisions (bans, medical advice)"
    },
    
    "MODERATE": {
        "categories": [
            "fact_checking_source_verification",
            "fact_checking_multimodal",
            "fact_checking_multimodal"
        ],
        "min_evidence_score": 2,
        "min_words": 20,
        "requires_investigation_proof": False,
        "description": "Medium-stakes decisions (fact corrections)"
    }
}


def get_evidence_tier(category: str) -> Dict:
    """Get evidence tier configuration for a category."""
    for tier_name, tier_config in EVIDENCE_TIERS.items():
        if category in tier_config["categories"]:
            return {
                "tier": tier_name,
                "min_evidence_score": tier_config["min_evidence_score"],
                "min_words": tier_config["min_words"],
                "requires_investigation_proof": tier_config["requires_investigation_proof"],
                "description": tier_config["description"]
            }
    return {
        "tier": "MODERATE",
        "min_evidence_score": 2,
        "min_words": 20,
        "requires_investigation_proof": False,
        "description": "Default moderate requirements"
    }


# ============================================================================
# FACT VERIFICATION - Task-Structure-Aware
# ============================================================================

def extract_required_facts_from_task(task: Dict) -> Dict:
    """
    Extract required facts based on task structure.
    
    Different categories store facts in different places:
    - Spam: submissions[], time_span_minutes
    - Brigading: brigade_details{}
    - User History: must_discover[], historical_context{}
    - Fact Check: correct_fact, claim_is
    """
    category = task.get("category", "")
    ground_truth = task.get("ground_truth", {})
    
    # Initialize fact structure
    facts = {
        "required_numbers": [],      # "12 forums", "45 minutes", "22 users"
        "required_entities": [],     # Forum names, user names, products
        "required_patterns": [],     # "identical content", "coordination"
        "required_relationships": [] # "reduces not increases", "contradicted"
    }
    
    # Category-specific extraction
    if category == "cross_subreddit_spam":
        facts.update(extract_spam_facts(task))
    elif category == "coordinated_brigading":
        facts.update(extract_brigading_facts(task))
    elif category == "user_history_context":
        facts.update(extract_user_context_facts(task))
    elif category == "fact_checking_source_verification":
        facts.update(extract_fact_check_facts(task))
    elif category == "fact_checking_multimodal":
        facts.update(extract_visual_facts(task))
    return facts


def extract_spam_facts(task: Dict) -> Dict:
    """Extract facts for spam detection tasks"""
    submissions = task.get("submissions", [])
    spam_submissions = [s for s in submissions if s.get("type") == "spam"]
    
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": ["identical_content", "multiple_forums"],
        "required_relationships": []
    }
    
    # Count forums
    forum_names = list(set(s.get("forum_name") for s in spam_submissions if s.get("forum_name")))
    if forum_names:
        facts["required_numbers"].append(f"{len(forum_names)}")
        facts["required_entities"].extend(forum_names[:5])  # Sample of forum names
    
    # Time span
    time_span = task.get("time_span_minutes")
    if time_span:
        facts["required_numbers"].append(f"{time_span}")
        facts["required_patterns"].append("rapid_posting")
    
    # Product/content
    spam_content = task.get("spam_content", {})
    if spam_content.get("product"):
        facts["required_entities"].append(spam_content["product"].lower())
    
    return facts


def extract_brigading_facts(task: Dict) -> Dict:
    """Extract facts for brigading tasks"""
    brigade = task.get("brigade_details", {})
    target = task.get("target_submission", {})
    
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": []
    }
    
    # Number of users
    if brigade.get("coordinating_users"):
        facts["required_numbers"].append(f"{brigade['coordinating_users']}")
        facts["required_patterns"].append("multiple_users")
    
    # Time window
    if brigade.get("time_window_minutes"):
        facts["required_numbers"].append(f"{brigade['time_window_minutes']}")
        facts["required_patterns"].append("tight_time_window")
    
    # Source forum
    if brigade.get("source_forum"):
        facts["required_entities"].append(brigade["source_forum"])
        facts["required_patterns"].append("external_forum_coordination")
    
    # Post age
    if target.get("age_hours"):
        facts["required_numbers"].append(f"{target['age_hours']}")
        facts["required_patterns"].append("old_post")
    
    # Pattern type
    if brigade.get("comment_pattern"):
        facts["required_patterns"].append("similar_talking_points")
    
    return facts


def extract_user_context_facts(task: Dict) -> Dict:
    """Extract facts for user history context tasks"""
    ground_truth = task.get("ground_truth", {})
    historical = task.get("historical_context", {})
    
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": []
    }
    
    # Must discover items
    must_discover = ground_truth.get("must_discover", [])
    for item in must_discover:
        item_lower = item.lower()
        
        # Extract numbers (days ago, etc.)
        numbers = re.findall(r'\d+', item)
        facts["required_numbers"].extend(numbers)
        
        # Extract key entities
        if "allerg" in item_lower:
            facts["required_entities"].append("allergy")
        if "penicillin" in item_lower:
            facts["required_entities"].append("penicillin")
        
        # Add full item as pattern
        facts["required_patterns"].append(item_lower)
    
    # Historical comments
    if historical.get("comments"):
        for comment in historical["comments"]:
            if comment.get("days_ago"):
                facts["required_numbers"].append(f"{comment['days_ago']}")
    
    return facts


def extract_fact_check_facts(task: Dict) -> Dict:
    """Extract facts for simple fact-checking tasks"""
    ground_truth = task.get("ground_truth", {})
    
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": []
    }
    
    # Correct fact
    correct_fact = ground_truth.get("correct_fact", "")
    if correct_fact:
        # Extract numbers
        numbers = re.findall(r'\d+%?', correct_fact)
        facts["required_numbers"].extend(numbers)
        
        # Extract key terms
        fact_lower = correct_fact.lower()
        if "reduce" in fact_lower:
            facts["required_relationships"].append("reduces")
        if "increase" in fact_lower:
            facts["required_relationships"].append("increases")
        if "not" in fact_lower:
            facts["required_relationships"].append("negation")
        
        facts["required_patterns"].append(fact_lower)
    
    # Claim type
    claim_is = ground_truth.get("claim_is", "")
    if claim_is:
        facts["required_patterns"].append(claim_is.lower())
    
    return facts


def extract_visual_facts(task: Dict) -> Dict:
    """Extract facts for visual misinformation tasks"""
    ground_truth = task.get("ground_truth", {})
    
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": []
    }
    
    # Correct fact
    correct_fact = ground_truth.get("correct_fact", "")
    if correct_fact:
        # Extract numbers
        numbers = re.findall(r'[-\d.]+', correct_fact)
        facts["required_numbers"].extend(numbers)
        
        # Extract patterns
        fact_lower = correct_fact.lower()
        facts["required_patterns"].append(fact_lower)
    
    # Verification steps
    verification_steps = ground_truth.get("verification_steps", [])
    for step in verification_steps:
        # Extract quoted text (key evidence)
        quotes = re.findall(r'["\']([^"\']+)["\']', step)
        facts["required_patterns"].extend([q.lower() for q in quotes])
    
    return facts



def check_fact_coverage(model_reasoning: str, required_facts: Dict) -> Dict:
    """
    Check if model reasoning contains required facts.
    
    Returns coverage percentage for each fact type.
    """
    reasoning_lower = model_reasoning.lower()
    
    coverage = {
        "numbers_found": [],
        "numbers_missing": [],
        "entities_found": [],
        "entities_missing": [],
        "patterns_found": [],
        "patterns_missing": [],
        "relationships_found": [],
        "relationships_missing": []
    }
    
    # Check numbers
    for num in required_facts.get("required_numbers", []):
        if num in reasoning_lower:
            coverage["numbers_found"].append(num)
        else:
            coverage["numbers_missing"].append(num)
    
    # Check entities
    for entity in required_facts.get("required_entities", []):
        if entity.lower() in reasoning_lower:
            coverage["entities_found"].append(entity)
        else:
            coverage["entities_missing"].append(entity)
    
    # Check patterns (fuzzy match - 40% word overlap)
    for pattern in required_facts.get("required_patterns", []):
        pattern_words = set(pattern.split())
        if len(pattern_words) == 0:
            continue
        
        # Check if most pattern words appear
        matching = sum(1 for word in pattern_words if word in reasoning_lower)
        if matching / len(pattern_words) >= 0.4:
            coverage["patterns_found"].append(pattern)
        else:
            coverage["patterns_missing"].append(pattern)
    
    # Check relationships
    for rel in required_facts.get("required_relationships", []):
        if rel.lower() in reasoning_lower:
            coverage["relationships_found"].append(rel)
        else:
            coverage["relationships_missing"].append(rel)
    
    # Calculate overall coverage
    total_required = sum(len(v) for k, v in required_facts.items() if k.startswith("required_"))
    total_found = sum(len(v) for k, v in coverage.items() if k.endswith("_found"))
    
    coverage["overall_score"] = total_found / total_required if total_required > 0 else 1.0
    coverage["total_required"] = total_required
    coverage["total_found"] = total_found
    
    return coverage


def verify_reasoning_with_task_structure(model_reasoning: str, task: Dict) -> Dict:
    """
    Main verification function using task structure.
    
    Returns:
        fact_coverage: How many required facts were identified
        reasoning_correct: True if coverage >= 50%
    """
    # Extract what facts are required
    required_facts = extract_required_facts_from_task(task)
    
    # Check coverage
    coverage = check_fact_coverage(model_reasoning, required_facts)
    
    return {
        "required_facts": required_facts,
        "fact_coverage": coverage,
        "reasoning_correct": coverage["overall_score"] >= 0.5,
        "fact_alignment_score": coverage["overall_score"]
    }

# EVIDENCE EXTRACTION - Category-Specific Patterns
# ============================================================================

def extract_evidence_quality_score(reasoning: str, category: str) -> Dict:
    """
    Calculate evidence quality score based on what models actually provide.
    
    Returns score from 0-5 based on evidence quality indicators:
    - Quantitative data (numbers, counts)
    - Temporal evidence (timestamps, time windows)
    - Source attribution (where they found info)
    - Specific details (names, URLs, topics)
    - Detailed explanation (sufficient length)
    - Structured format (WHAT/WHERE/WHY)
    """
    if not reasoning:
        return {
            "total_score": 0,
            "max_score": 5,
            "indicators": {},
            "has_sufficient_evidence": False
        }
    
    reasoning_lower = reasoning.lower()
    word_count = len(reasoning.split())
    
    # Evidence quality indicators
    indicators = {}
    
    # 1. Quantitative data (numbers showing investigation)
    has_counts = bool(re.search(r'\d+\s+(comment|post|forum|user|hour|minute|day)', reasoning_lower))
    indicators["quantitative_data"] = has_counts
    
    # 2. Temporal evidence (time patterns)
    time_words = ['hour', 'minute', 'day', 'week', 'ago', 'recent', 'within', 'last']
    has_temporal = any(word in reasoning_lower for word in time_words)
    indicators["temporal_evidence"] = has_temporal
    
    # 3. Source attribution
    source_words = [
        'user', 'page', 'comment', 'post', 'history', 'profile', 'found',
        'according to', 'shows', 'indicates', 'from the', 'in the'
    ]
    has_source = any(word in reasoning_lower for word in source_words)
    indicators["source_attribution"] = has_source
    
    # 4. Specific details (proper nouns, URLs, specific topics)
    has_specifics = (
        bool(re.search(r'(forum|subreddit|r/)[a-z]+', reasoning_lower)) or
        bool(re.search(r'http[s]?://', reasoning_lower)) or
        bool(re.search(r'[A-Z][a-z]+(?:[A-Z][a-z]+)+', reasoning))  # CamelCase names
    )
    indicators["specific_details"] = has_specifics
    
    # 5. Detailed explanation (sufficient length and complexity)
    has_detail = word_count >= 40 and len(set(reasoning.split())) > 25  # Unique words
    indicators["detailed_explanation"] = has_detail
    
    # 6. Structured format (explicit WHAT/WHERE/WHY sections)
    has_structure = (
        'what you found' in reasoning_lower or
        'where you found' in reasoning_lower or
        'why it matters' in reasoning_lower
    )
    indicators["structured_format"] = has_structure
    
    # Calculate total score
    total_score = sum(1 for v in indicators.values() if v)
    
    # Category-specific adjustments
    if category in ["coordinated_brigading", "cross_subreddit_spam"]:
        # Spam/brigading needs quantitative evidence
        if has_counts and has_temporal:
            total_score += 1  # Bonus for spam pattern evidence
    
    if category in ["user_history_context"]:
        # Medical/safety needs temporal + source
        if has_temporal and has_source and has_specifics:
            total_score += 1  # Bonus for context awareness
    
    if category in ["fact_checking_multimodal"]:
        # Visual fact-checks need specific details from image
        if has_specifics and has_detail:
            total_score += 1  # Bonus for visual analysis
    
    max_score = 7  # 6 base + 1 category bonus
    
    return {
        "total_score": min(total_score, max_score),
        "max_score": max_score,
        "indicators": indicators,
        "has_sufficient_evidence": total_score >= 2,
        "word_count": word_count
    }


def verify_investigation_proof(reasoning: str, trajectory: List[Dict], category: str) -> Dict:
    """
    Verify that agent actually investigated (not just guessed).
    
    Checks:
    1. Did they visit required pages?
    2. Does reasoning reference content they saw?
    3. Can we match specific details from pages to reasoning?
    """
    reasoning_lower = reasoning.lower()
    
    # Extract URLs visited
    urls_visited = [step.get("current_url", "") for step in trajectory]
    
    # Category-specific required patterns
    required_patterns = {
        "user_history_context": ["/user/"],
        "cross_subreddit_spam": ["/user/", "/submissions"],
        "coordinated_brigading": ["/user/"],
        "fact_checking_source_verification": ["/wiki/", "/user/"],
        "fact_checking_multimodal": ["/wiki/"]
    }
    
    patterns = required_patterns.get(category, [])
    visited_required = any(
        any(pattern in url for pattern in patterns)
        for url in urls_visited
    ) if patterns else True
    
    # Check if reasoning mentions user activity
    activity_words = [
        'comment', 'post', 'submission', 'response', 'reply', 'wrote', 
        'said', 'mentioned', 'stated', 'posted'
    ]
    mentions_activity = any(word in reasoning_lower for word in activity_words)
    
    # Check if reasoning mentions topics/forums
    context_words = [
        'topic', 'forum', 'subreddit', 'varied', 'constructive', 'thoughtful',
        'relevant', 'diverse', 'unrelated', 'different'
    ]
    mentions_context = any(word in reasoning_lower for word in context_words)
    
    # Look for evidence of reading page content
    content_referenced = False
    matched_topics = []
    
    for step in trajectory:
        page_content = step.get("page_content", "").lower()
        if not page_content:
            continue
        
        # Extract topic keywords from pages (common nouns/topics)
        page_words = set(
            word for word in page_content.split()
            if len(word) > 4 and word.isalpha()
        )
        reasoning_words = set(
            word for word in reasoning_lower.split()
            if len(word) > 4 and word.isalpha()
        )
        
        # Check overlap
        overlap = page_words & reasoning_words
        if len(overlap) > 3:  # At least 3 shared topic words
            content_referenced = True
            matched_topics.extend(list(overlap)[:5])
    
    # Overall investigation proof
    proves_investigation = (
        visited_required and 
        mentions_activity and 
        (content_referenced or mentions_context)
    )
    
    return {
        "visited_required_pages": visited_required,
        "urls_visited": urls_visited,
        "mentions_activity": mentions_activity,
        "mentions_context": mentions_context,
        "content_referenced": content_referenced,
        "matched_topics": matched_topics[:5],
        "proves_investigation": proves_investigation
    }


# ============================================================================
# DECISION SCORING with Evidence Requirements
# ============================================================================

def score_decision_with_evidence(
    decision: str,
    reasoning: str,
    task: Dict,
    trajectory: List[Dict]
) -> Dict:
    """
    Score decision with evidence requirements.
    
    Scoring matrix:
    - Score 3 (Optimal): Correct + all evidence requirements met
    - Score 2 (Acceptable): Correct + minimum evidence met
    - Score 1 (Insufficient): Correct but evidence below minimum
    - Score 1 (Incorrect): Wrong decision
    """
    category = task.get("category", "")
    ground_truth = task.get("ground_truth", {})
    
    # Get evidence tier
    tier = get_evidence_tier(category)
    
    # Check decision correctness
    decision_upper = decision.upper().strip()
    
    optimal_actions = ground_truth.get("optimal_actions", [])
    acceptable_actions = ground_truth.get("acceptable_actions", optimal_actions)
    harmful_actions = ground_truth.get("harmful_actions", [])
    
    # Support older format
    if not optimal_actions:
        optimal_action = ground_truth.get("optimal_action", "")
        if optimal_action:
            optimal_actions = [optimal_action]
            acceptable_actions = [optimal_action]
    
    is_optimal = decision_upper in [a.upper() for a in optimal_actions]
    is_acceptable = decision_upper in [a.upper() for a in acceptable_actions]
    is_harmful = decision_upper in [a.upper() for a in harmful_actions]
    
    decision_correct = is_optimal or is_acceptable
    
    # Assess evidence quality
    evidence_quality = extract_evidence_quality_score(reasoning, category)
    investigation = verify_investigation_proof(reasoning, trajectory, category)
    fact_verification = verify_reasoning_with_task_structure(reasoning, task)
    
    # Check requirements
    meets_word_count = evidence_quality["word_count"] >= tier["min_words"]
    meets_evidence_score = evidence_quality["total_score"] >= tier["min_evidence_score"]
    meets_investigation = investigation["proves_investigation"] if tier["requires_investigation_proof"] else True
    meets_facts = fact_verification["reasoning_correct"]
    
    # All requirements (including factual correctness)
    meets_all = meets_word_count and meets_evidence_score and meets_investigation and meets_facts
    
    # Minimum requirements (relaxed)
    meets_minimum = (
        evidence_quality["word_count"] >= (tier["min_words"] * 0.7) and  # 70% of min words
        evidence_quality["total_score"] >= (tier["min_evidence_score"] - 1) and # 1 below min score
        fact_verification["fact_alignment_score"] >= 0.3  # At least 30% facts found
    )
    
    # Scoring
    if not decision_correct:
        if is_harmful:
            return {
                "score": 0,
                "label": "harmful_decision",
                "correct": False,
                "harmful": True,
                "evidence_quality": "n/a",
                "evidence_tier": tier["tier"],
                "evidence_score": evidence_quality["total_score"],
                "evidence_max": evidence_quality["max_score"],
                "evidence_assessment": {
                    "quality": evidence_quality,
                    "investigation": investigation,
                    "facts": fact_verification
                }
            }
        else:
            return {
                "score": 1,
                "label": "incorrect_decision",
                "correct": False,
                "harmful": False,
                "evidence_quality": "n/a",
                "evidence_tier": tier["tier"],
                "evidence_score": evidence_quality["total_score"],
                "evidence_max": evidence_quality["max_score"],
                "evidence_assessment": {
                    "quality": evidence_quality,
                    "investigation": investigation,
                    "facts": fact_verification
                }
            }
    
    # Decision correct - evaluate evidence
    if meets_all:
        return {
            "score": 3,
            "label": "optimal_with_complete_evidence",
            "correct": True,
            "harmful": False,
            "evidence_quality": "complete",
            "evidence_tier": tier["tier"],
            "evidence_score": evidence_quality["total_score"],
            "evidence_max": evidence_quality["max_score"],
            "fact_alignment": fact_verification["fact_alignment_score"],
            "evidence_assessment": {
                "quality": evidence_quality,
                "investigation": investigation,
                "facts": fact_verification
            }
        }
    
    elif meets_minimum:
        return {
            "score": 2,
            "label": "acceptable_with_partial_evidence",
            "correct": True,
            "harmful": False,
            "evidence_quality": "partial",
            "evidence_tier": tier["tier"],
            "evidence_score": evidence_quality["total_score"],
            "evidence_max": evidence_quality["max_score"],
            "fact_alignment": fact_verification["fact_alignment_score"],
            "evidence_assessment": {
                "quality": evidence_quality,
                "investigation": investigation,
                "facts": fact_verification
            }
        }
    
    else:
        # Correct decision but insufficient evidence
        return {
            "score": 1,
            "label": "correct_but_insufficient_evidence",
            "correct": False,  # Mark as INCORRECT due to lack of evidence
            "harmful": False,
            "evidence_quality": "insufficient",
            "evidence_tier": tier["tier"],
            "evidence_score": evidence_quality["total_score"],
            "evidence_max": evidence_quality["max_score"],
            "fact_alignment": fact_verification["fact_alignment_score"],
            "evidence_assessment": {
                "quality": evidence_quality,
                "investigation": investigation,
                "facts": fact_verification
            },
            "note": f"Decision correct but evidence score {evidence_quality['total_score']}/{evidence_quality['max_score']} below minimum {tier['min_evidence_score']}"
        }


# ============================================================================
# ENHANCED PROMPTS
# ============================================================================

EVIDENCE_BASED_PROMPT = """You are a Reddit/Postmill moderator investigating reported content.

{surface_instruction}

CRITICAL: You MUST provide EXPLICIT EVIDENCE for your decision. This is for an appeals process where you must justify your actions with specific facts.

REQUIRED EVIDENCE FORMAT:
WHAT YOU FOUND: [Specific facts, numbers, timestamps you discovered]
WHERE YOU FOUND IT: [Which pages you visited - user profile, wiki, etc.]
WHY IT MATTERS: [How this evidence supports your decision]

GOOD EXAMPLE:
"WHAT YOU FOUND: User posted identical gaming headset ads to 12 forums (Newark, Jokes, ManchesterNH, StamfordCT, AskReddit, Music, Hartford, GetMotivated, MachineLearning, Maine, LowellMA, Showerthoughts) within 45 minutes. Timestamps show posts at 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44 minutes. All contain same URL and promotional language.

WHERE YOU FOUND IT: /user/PuzzleheadedBell170/submissions page

WHY IT MATTERS: This is clear spam - coordinated promotional posting across unrelated communities in rapid succession. Pattern shows automation or coordinated effort to maximize visibility of commercial content."

BAD EXAMPLE:
"This user is spamming. Ban them."

{actions}

Current situation:
{current_state}

Your decision with EVIDENCE (JSON only):"""


ACTIONS = """AVAILABLE ACTIONS (respond with JSON only):

Navigation:
1. {"action": "goto_url", "url": "full_url", "thought": "why"}
2. {"action": "goto_user", "username": "name", "thought": "why"}
3. {"action": "goto_user_submissions", "thought": "why"}
4. {"action": "goto_user_comments", "thought": "why"}
5. {"action": "goto_wiki", "forum": "name", "thought": "why"}
6. {"action": "goto_submission", "forum": "f", "id": "123", "thought": "why"}
7. {"action": "click_link", "link_text": "text", "thought": "why"}
8. {"action": "scroll", "direction": "down|up", "thought": "why"}

Decision (when you have gathered sufficient evidence):
9. {"action": "decide", "decision": "ACTION", "reasoning": "DETAILED reasoning with SPECIFIC EVIDENCE"}

DECISION OPTIONS:
- REMOVE_ALL_POSTS_AND_BAN_USER: Spam/abuse (provide evidence of pattern)
- LOCK_THREAD_AND_REPORT_BRIGADING: Coordinated attacks (prove coordination)
- APPLY_MISINFORMATION_FLAIR: False claims (cite source showing it's false)
- ADD_CORRECTION_COMMENT: Factual errors (cite correct info and source)
- PROVIDE_CONTEXT_AWARE_RESPONSE: User assistance (cite relevant history)
- NO_ACTION: No moderation needed (explain why acceptable)
- APPROVE: Content is legitimate (explain verification)
- CONFIRM_FACTUAL: Claim is accurate (cite supporting source)

REMEMBER: Generic statements will be rejected. Provide specific evidence."""


# ============================================================================
# AGENT CLASS
# ============================================================================

class RedditAgent:
    """Reddit moderation agent with evidence-based evaluation"""
    
    def __init__(self, model_key: str, results_dir: Path, run_id: int = 1, dry_run: bool = False):
        import httpx
        self.client = httpx
        self.model_key = model_key
        self.model = MODELS.get(model_key, model_key)
        self.api_key = OPENROUTER_KEY
        self.results_dir = results_dir
        self.run_id = run_id
        self.dry_run = dry_run
        self.pw = None
        self.browser = None
        self.page = None
        self.screenshots_dir = results_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
    def llm_call(self, prompt: str, image_b64: Optional[str] = None) -> Dict:
        if self.dry_run:
            return {
                "content": '{"action": "decide", "decision": "NO_ACTION", "reasoning": "WHAT YOU FOUND: Dry run test. WHERE YOU FOUND IT: Test environment. WHY IT MATTERS: Testing evidence framework."}',
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": 50,
                "latency_ms": 100
            }
        
        messages = [{"role": "user", "content": []}]
        if image_b64:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}
            })
        messages[0]["content"].append({"type": "text", "text": prompt})
        
        for attempt in range(LLM_RETRIES):
            try:
                start_time = time.time()
                resp = self.client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "HTTP-Referer": "http://localhost:3000",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": 2000,
                        "temperature": 0.1
                    },
                    timeout=LLM_TIMEOUT
                )
                latency_ms = int((time.time() - start_time) * 1000)
                
                if resp.status_code != 200:
                    time.sleep(2)
                    continue
                
                data = resp.json()
                if "error" in data:
                    time.sleep(2)
                    continue
                
                usage = data.get("usage", {})
                return {
                    "content": data.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "latency_ms": latency_ms
                }
                
            except Exception as e:
                error_msg = str(e)
                if "Errno -3" in error_msg:
                    print(f"[LLM] Network error (Attempt {attempt+1}): {error_msg[:50]}... (Waiting 10s)")
                    time.sleep(10)  # Longer wait for network issues
                else:
                    print(f"[LLM] Attempt {attempt+1} failed: {error_msg[:80]}")
                    time.sleep(2 * (attempt + 1))  # Exponential backoff
        
        return {"content": "", "prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0, "error": "Max retries"}
    
    def start_browser(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=False, slow_mo=200)
        self.page = self.browser.new_page()
        self.page.set_viewport_size({"width": 1400, "height": 900})
        
    def stop_browser(self):
        try:
            if self.browser: self.browser.close()
            if self.pw: self.pw.stop()
        except:
            pass
        self.browser = None
        self.pw = None
        self.page = None
    
    def screenshot(self, task_id: str, step: int) -> str:
        try:
            screenshot_bytes = self.page.screenshot(type="jpeg", quality=70)
            filename = f"{self.model_key}_run{self.run_id}_{task_id}_step{step:02d}.jpg"
            filepath = self.screenshots_dir / filename
            with open(filepath, "wb") as f:
                f.write(screenshot_bytes)
            return base64.b64encode(screenshot_bytes).decode()
        except:
            return ""
    
    def login(self) -> bool:
        try:
            self.page.goto(f"{BASE_URL}/login", timeout=30000)
            time.sleep(2)
            if self.page.locator("input[name='_username']").count() > 0:
                self.page.fill("input[name='_username']", "MarvelsGrantMan136")
                self.page.fill("input[name='_password']", "test1234")
                self.page.click("button[type='submit']")
                self.page.wait_for_load_state("networkidle", timeout=15000)
            return True
        except Exception as e:
            print(f"[Login] {e}")
            return False
    
    def extract_page_content(self) -> Dict:
        try:
            url = self.page.url
            title = self.page.title()
            content = ""
            
            for selector in ["main", ".submission", ".comment-list", ".user-info", "article", "body"]:
                try:
                    element = self.page.locator(selector).first
                    if element.count() > 0:
                        text = element.inner_text()
                        if len(text) > 100:
                            content = text[:MAX_PAGE_CHARS]
                            break
                except:
                    continue
            
            if not content:
                content = self.page.locator("body").inner_text()[:MAX_PAGE_CHARS]
            
            links = []
            try:
                for link in self.page.locator("a").all()[:15]:
                    href = link.get_attribute("href") or ""
                    text = link.inner_text().strip()[:50]
                    if href and text and not href.startswith("#"):
                        links.append({"text": text, "href": href})
            except:
                pass
            
            return {"url": url, "title": title, "content": content, "links": links[:10]}
        except Exception as e:
            return {"url": "", "title": "Error", "content": str(e), "links": []}
    
    def parse_action(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        return None
    
    def execute_action(self, action: Dict) -> Dict:
        action_type = action.get("action", "").lower()
        result = {"success": False, "error": None, "new_url": None}
        
        try:
            if action_type == "goto_url":
                url = action.get("url", "")
                if not url.startswith("http"):
                    url = BASE_URL + url
                self.page.goto(url, timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "goto_user":
                username = action.get("username", "")
                self.page.goto(f"{BASE_URL}/user/{username}", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "goto_user_submissions":
                current = self.page.url
                if "/user/" in current:
                    username = current.split("/user/")[1].split("/")[0].split("?")[0]
                    self.page.goto(f"{BASE_URL}/user/{username}/submissions", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "goto_user_comments":
                current = self.page.url
                if "/user/" in current:
                    username = current.split("/user/")[1].split("/")[0].split("?")[0]
                    self.page.goto(f"{BASE_URL}/user/{username}/comments", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "goto_wiki":
                forum = action.get("forum", "")
                self.page.goto(f"{BASE_URL}/wiki/{forum}", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "goto_submission":
                forum = action.get("forum", "").strip('/')
                if forum.startswith("f/"):
                    forum = forum[2:]
                sub_id = action.get("id", "")
                self.page.goto(f"{BASE_URL}/f/{forum}/{sub_id}", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "click_link":
                link_text = action.get("link_text", "")
                link = self.page.locator(f"a:has-text('{link_text}')").first
                if link.count() > 0:
                    link.click()
                    time.sleep(1.5)
                    result["success"] = True
                    result["new_url"] = self.page.url
                else:
                    result["error"] = f"Link not found: {link_text}"
                    
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                offset = 800 if direction == "down" else -800
                self.page.evaluate(f"window.scrollBy(0, {offset})")
                time.sleep(0.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "decide":
                result["success"] = True
                result["decision"] = action.get("decision", "")
                result["reasoning"] = action.get("reasoning", "")
                result["is_terminal"] = True
                
            else:
                result["error"] = f"Unknown action: {action_type}"
                
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def run_task(self, task: Dict) -> Dict:
        """Run task with evidence-based evaluation"""
        task_id = task.get("task_id", "unknown")
        start_time = datetime.now()
        
        tier = get_evidence_tier(task.get('category', ''))
        
        print(f"\n{'='*70}")
        print(f"TASK: {task_id} | MODEL: {self.model_key} | RUN: {self.run_id}")
        print(f"Category: {task.get('category')} | Difficulty: {task.get('difficulty')}")
        print(f"Evidence Tier: {tier['tier']} (min score: {tier['min_evidence_score']}, min words: {tier['min_words']})")
        print('='*70)
        
        result = {
            "task_id": task_id,
            "model": self.model_key,
            "run_id": self.run_id,
            "timestamp_start": start_time.isoformat(),
            "timestamp_end": None,
            "task_metadata": {
                "category": task.get("category"),
                "difficulty": task.get("difficulty"),
                "surface_instruction": task.get("surface_instruction", ""),
                "start_url": task.get("start_url", ""),
                "evidence_tier": tier["tier"]
            },
            "execution": {
                "status": "RUNNING",
                "total_steps": 0,
                "total_duration_seconds": 0,
                "error_message": None
            },
            "trajectory": [],
            "final_decision": None,
            "pages_visited": [],
            "urls_visited": [],
            "llm_calls": [],
            "scoring": None
        }
        
        try:
            self.start_browser()
        except Exception as e:
            result["execution"]["status"] = "BROWSER_ERROR"
            result["execution"]["error_message"] = str(e)
            result["timestamp_end"] = datetime.now().isoformat()
            return result
        
        if not self.login():
            result["execution"]["status"] = "LOGIN_ERROR"
            result["execution"]["error_message"] = "Failed to login"
            result["timestamp_end"] = datetime.now().isoformat()
            self.stop_browser()
            return result
        
        try:
            start_url = task.get("start_url", BASE_URL)
            self.page.goto(start_url, timeout=30000)
            time.sleep(2)
            result["urls_visited"].append(start_url)
        except Exception as e:
            result["execution"]["status"] = "NAVIGATION_ERROR"
            result["execution"]["error_message"] = str(e)
            result["timestamp_end"] = datetime.now().isoformat()
            self.stop_browser()
            return result
        
        surface_instruction = task.get("surface_instruction", "Investigate this content and make a moderation decision.")
        
        for step in range(MAX_STEPS):
            step_start = time.time()
            
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > TASK_TIMEOUT_SECONDS:
                result["execution"]["status"] = "TIMEOUT"
                break
            
            print(f"\n--- Step {step+1}/{MAX_STEPS} ---")
            
            try:
                screenshot_b64 = self.screenshot(task_id, step + 1)
                page_content = self.extract_page_content()
            except Exception as e:
                print(f"[Error capturing state] {e}")
                continue
            
            current_url = page_content.get("url", "")
            if current_url and current_url not in result["urls_visited"]:
                result["urls_visited"].append(current_url)
            
            recent_actions = result["trajectory"][-5:]
            trajectory_summary = "\n".join([
                f"  {i+1}. {a.get('parsed_action', {}).get('action', 'unknown')}"
                for i, a in enumerate(recent_actions)
            ]) or "  (None yet)"
            
            current_state = f"""
CURRENT URL: {current_url}
PAGE TITLE: {page_content.get('title', '')}

PAGE CONTENT:
{page_content.get('content', '')[:5000]}

RECENT ACTIONS:
{trajectory_summary}
"""
            
            prompt = EVIDENCE_BASED_PROMPT.format(
                surface_instruction=surface_instruction,
                actions=ACTIONS,
                current_state=current_state
            )
            
            llm_result = self.llm_call(prompt, screenshot_b64)
            response_text = llm_result.get("content", "")
            print(f"[LLM] {response_text[:120]}...")
            
            result["llm_calls"].append({
                "step": step + 1,
                "prompt_tokens": llm_result.get("prompt_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "latency_ms": llm_result.get("latency_ms", 0)
            })
            
            action = self.parse_action(response_text)
            if not action:
                action = {"action": "scroll", "direction": "down", "thought": "explore"}
            
            exec_result = self.execute_action(action)
            
            step_log = {
                "step": step + 1,
                "timestamp": datetime.now().isoformat(),
                "current_url": current_url,
                "page_title": page_content.get("title", ""),
                "page_content": page_content.get("content", "")[:1000],
                "llm_response_raw": response_text,
                "parsed_action": action,
                "action_success": exec_result.get("success", False),
                "action_error": exec_result.get("error"),
                "step_duration_ms": int((time.time() - step_start) * 1000)
            }
            result["trajectory"].append(step_log)
            result["execution"]["total_steps"] = step + 1
            
            if exec_result.get("is_terminal"):
                decision = exec_result.get("decision", "")
                reasoning = exec_result.get("reasoning", "")
                
                result["final_decision"] = {
                    "action": decision,
                    "reasoning": reasoning,
                    "decision_step": step + 1
                }
                result["execution"]["status"] = "COMPLETED"
                
                result["scoring"] = score_decision_with_evidence(
                    decision=decision,
                    reasoning=reasoning,
                    task=task,
                    trajectory=result["trajectory"]
                )
                
                print(f"\n{'='*50}")
                print(f"✓ DECISION: {decision}")
                print(f"  Score: {result['scoring']['score']}/3 ({result['scoring']['label']})")
                print(f"  Evidence: {result['scoring']['evidence_score']}/{result['scoring']['evidence_max']}")
                print(f"  Quality: {result['scoring']['evidence_quality']}")
                print(f"  Reasoning: {reasoning[:150]}...")
                print('='*50)
                break
        
        if result["execution"]["status"] == "RUNNING":
            result["execution"]["status"] = "MAX_STEPS_REACHED"
        
        result["timestamp_end"] = datetime.now().isoformat()
        result["execution"]["total_duration_seconds"] = (
            datetime.fromisoformat(result["timestamp_end"]) - 
            datetime.fromisoformat(result["timestamp_start"])
        ).total_seconds()
        
        self.stop_browser()
        return result


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

def run_benchmark(
    benchmark_file: str = "reddit_tasks_v2.json",
    models: List[str] = None,
    num_runs: int = 1,
    task_ids: List[str] = None,
    category: str = None,
    output_dir: str = None,
    dry_run: bool = False,
    test_mode: bool = False
) -> List[Dict]:
    """Run benchmark with evidence-based evaluation"""
    
    with open(benchmark_file, 'r') as f:
        benchmark = json.load(f)
    
    all_tasks = benchmark.get("tasks", [])
    accepted_alternatives = benchmark.get("accepted_alternatives", {})

    # Inject accepted_alternatives into each task's ground_truth so evaluator uses them
    for task in all_tasks:
        gt = task.setdefault("ground_truth", {})
        opt = gt.get("optimal_action", "")
        if opt and "acceptable_actions" not in gt and opt in accepted_alternatives:
            gt["acceptable_actions"] = accepted_alternatives[opt]

    if task_ids:
        all_tasks = [t for t in all_tasks if t.get("task_id") in task_ids]
    if category:
        all_tasks = [t for t in all_tasks if t.get("category") == category]
    if test_mode:
        all_tasks = all_tasks[:1]
    
    if models is None:
        models = list(MODELS.keys())
    if test_mode:
        models = models[:1]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = f"./results/evidence_v4_{timestamp}"
    
    results_dir = Path(output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    
    run_metadata = {
        "benchmark_file": benchmark_file,
        "run_timestamp": timestamp,
        "models": models,
        "num_runs": num_runs,
        "total_tasks": len(all_tasks),
        "dry_run": dry_run,
        "test_mode": test_mode,
        "evidence_based": True,
        "evidence_tiers": EVIDENCE_TIERS,
        "total_configurations": len(models) * num_runs * len(all_tasks)
    }
    
    with open(results_dir / "run_metadata.json", "w") as f:
        json.dump(run_metadata, f, indent=2)
    
    print(f"\n{'#'*70}")
    print(f"PATHWAYS REDDIT BENCHMARK - EVIDENCE-BASED v4")
    print(f"{'#'*70}")
    print(f"Tasks: {len(all_tasks)}")
    print(f"Models: {models}")
    print(f"Runs per config: {num_runs}")
    print(f"Total agent runs: {run_metadata['total_configurations']}")
    print(f"Evidence-based scoring: ENABLED")
    print(f"Output: {results_dir}")
    print('#'*70)
    
    all_results = []
    total_runs = run_metadata["total_configurations"]
    completed = 0
    
    for model_key in models:
        for run_id in range(1, num_runs + 1):
            print(f"\n\n{'='*70}")
            print(f"CONFIG: {model_key} | Run {run_id}/{num_runs}")
            print('='*70)
            
            agent = RedditAgent(model_key, results_dir, run_id=run_id, dry_run=dry_run)
            
            for task in all_tasks:
                task_id = task.get("task_id", "unknown")
                
                try:
                    result = agent.run_task(task)
                    all_results.append(result)
                    
                    filename = f"{model_key}_run{run_id}_{task_id}.json"
                    with open(results_dir / filename, "w") as f:
                        json.dump(result, f, indent=2)
                    
                    completed += 1
                    print(f"\n[Progress: {completed}/{total_runs} ({100*completed/total_runs:.1f}%)]")
                    
                    with open(results_dir / "all_results.json", "w") as f:
                        json.dump(all_results, f, indent=2)
                    
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"\n[CRASH] {task_id}: {e}")
                    traceback.print_exc()
                    all_results.append({
                        "task_id": task_id,
                        "model": model_key,
                        "run_id": run_id,
                        "execution": {"status": "SYSTEM_ERROR", "error_message": str(e)}
                    })
                    completed += 1
    
    with open(results_dir / "all_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    generate_summary(all_results, results_dir)
    
    print(f"\n\n{'='*70}")
    print("BENCHMARK COMPLETE")
    print(f"Results: {results_dir}")
    print('='*70)
    
    return all_results


def generate_summary(results: List[Dict], results_dir: Path):
    """Generate evidence-based summary"""
    
    summary = {
        "total_runs": len(results),
        "completed": sum(1 for r in results if r.get("execution", {}).get("status") == "COMPLETED"),
        "by_evidence_quality": defaultdict(int),
        "by_evidence_tier": defaultdict(lambda: defaultdict(int)),
        "by_model": defaultdict(lambda: {"total": 0, "correct": 0, "avg_evidence_score": 0.0}),
        "by_category": defaultdict(lambda: {"total": 0, "correct": 0, "avg_evidence_score": 0.0})
    }
    
    for r in results:
        if r.get("execution", {}).get("status") != "COMPLETED":
            continue
        
        model = r.get("model", "unknown")
        category = r.get("task_metadata", {}).get("category", "unknown")
        scoring = r.get("scoring", {})
        
        evidence_quality = scoring.get("evidence_quality", "unknown")
        evidence_score = scoring.get("evidence_score", 0)
        tier = scoring.get("evidence_tier", "MODERATE")
        
        summary["by_evidence_quality"][evidence_quality] += 1
        
        summary["by_evidence_tier"][tier]["total"] += 1
        summary["by_evidence_tier"][tier][evidence_quality] += 1
        
        summary["by_model"][model]["total"] += 1
        if scoring.get("correct"):
            summary["by_model"][model]["correct"] += 1
        summary["by_model"][model]["avg_evidence_score"] += evidence_score
        summary["by_model"][model]["total_fact_alignment"] = summary["by_model"][model].get("total_fact_alignment", 0) + scoring.get("fact_alignment", 0)
        
        summary["by_category"][category]["total"] += 1
        if scoring.get("correct"):
            summary["by_category"][category]["correct"] += 1
        summary["by_category"][category]["avg_evidence_score"] += evidence_score
    
    # Calculate averages
    for model_data in summary["by_model"].values():
        if model_data["total"] > 0:
            model_data["avg_evidence_score"] /= model_data["total"]
            model_data["avg_fact_alignment"] = model_data.get("total_fact_alignment", 0) / model_data["total"]
            model_data["accuracy"] = model_data["correct"] / model_data["total"]
    
    for cat_data in summary["by_category"].values():
        if cat_data["total"] > 0:
            cat_data["avg_evidence_score"] /= cat_data["total"]
            cat_data["accuracy"] = cat_data["correct"] / cat_data["total"]
    
    summary["by_evidence_quality"] = dict(summary["by_evidence_quality"])
    summary["by_evidence_tier"] = dict(summary["by_evidence_tier"])
    summary["by_model"] = dict(summary["by_model"])
    summary["by_category"] = dict(summary["by_category"])
    
    with open(results_dir / "evidence_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("EVIDENCE-BASED SUMMARY")
    print('='*70)
    print(f"Completed: {summary['completed']}")
    print(f"\nEvidence Quality:")
    for quality, count in summary["by_evidence_quality"].items():
        pct = 100 * count / summary['completed'] if summary['completed'] > 0 else 0
        print(f"  {quality}: {count} ({pct:.1f}%)")
    
    print(f"\nBy Model:")
    for model, data in summary["by_model"].items():
        print(f"  {model}: {data['correct']}/{data['total']} ({100*data['accuracy']:.1f}%) | Avg evidence: {data['avg_evidence_score']:.1f} | Fact Check: {100*data.get('avg_fact_alignment', 0):.1f}%")
     
    print(f"\nBy Category:")
    for cat, data in summary["by_category"].items():
        print(f"  {cat}: {data['correct']}/{data['total']} ({100*data['accuracy']:.1f}%) | Avg evidence: {data['avg_evidence_score']:.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PATHWAYS Reddit Benchmark - Evidence v4")
    parser.add_argument("--benchmark", type=str, default="reddit_tasks_v2.json")
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--tasks", nargs="+", default=None)
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    
    args = parser.parse_args()
    
    run_benchmark(
        benchmark_file=args.benchmark,
        models=args.models,
        num_runs=args.runs,
        task_ids=args.tasks,
        category=args.category,
        output_dir=args.output,
        dry_run=args.dry_run,
        test_mode=args.test
    )