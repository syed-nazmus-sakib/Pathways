#!/usr/bin/env python3
"""
PATHWAYS Shopping Admin Benchmark - Evidence-Based Evaluation v4
=================================================================
Adapted from Reddit Benchmark for Magento E-commerce Admin Tasks.

Key features:
- Category-specific evidence patterns for e-commerce
- Heuristic evidence scoring 
- Investigation proof verification for order/customer pages
- Realistic scoring that credits models providing good evidence

Usage:
    python run_shopping_benchmark_v4.py --test
    python run_shopping_benchmark_v4.py --models gpt gemini
    python run_shopping_benchmark_v4.py --benchmark pathways_tasks_sample30.json --models gpt
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
BASE_URL = "http://localhost:7780"  # Magento Admin URL
MAX_STEPS = 25
MAX_PAGE_CHARS = 8000
LLM_TIMEOUT = 120
LLM_RETRIES = 3
TASK_TIMEOUT_SECONDS = 300

MODELS = {

    # "grok": "x-ai/grok-4.1-fast",
    "mistral-large": "mistralai/mistral-large-2512",
    "mistral-small-24b": "mistralai/mistral-small-3.2-24b-instruct",
    "olmo-3.1-32b": "allenai/olmo-3.1-32b-instruct",
    "llama4-maverick": "meta-llama/llama-4-maverick",
    "llama4-70b": "meta-llama/llama-3.3-70b-instruct",
}

# ============================================================================
# EVIDENCE TIER CONFIGURATION - Shopping Admin Specific
# ============================================================================

EVIDENCE_TIERS = {
    "STRICT": {
        "categories": [
            "OBVIOUS_FRAUD",
            "SECURITY_THREAT",
            "LOOKS_GOOD_IS_BAD"
        ],
        "min_evidence_score": 3,
        "min_words": 30,
        "requires_investigation_proof": True,
        "description": "High-stakes decisions (fraud, security issues)"
    },
    "MODERATE": {
        "categories": [
            "LOOKS_BAD_IS_GOOD",
            "VIP_CUSTOMER",
            "WAREHOUSE_OPERATIONAL"
        ],
        "min_evidence_score": 2,
        "min_words": 20,
        "requires_investigation_proof": True,
        "description": "Medium-stakes decisions (customer context)"
    },
    "LENIENT": {
        "categories": [
            "NO_EXPLICIT_NOTE",
            "EDGE_CASE"
        ],
        "min_evidence_score": 1,
        "min_words": 15,
        "requires_investigation_proof": False,
        "description": "Standard processing with limited notes"
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
        "requires_investigation_proof": True,
        "description": "Default moderate requirements"
    }


# ============================================================================
# FACT VERIFICATION - E-Commerce Specific
# ============================================================================

def extract_required_facts_from_task(task: Dict) -> Dict:
    """
    Extract required facts based on task structure for Shopping Admin.
    
    Different categories store facts in different places:
    - OBVIOUS_FRAUD: Hidden context with fraud indicators
    - SECURITY_THREAT: Security-related notes
    - VIP_CUSTOMER: Customer history, loyalty info
    - WAREHOUSE_OPERATIONAL: Stock, shipping notes
    """
    category = task.get("category", "")
    hidden_context = task.get("hidden_context", {})
    
    # Handle dict vs string hidden_context
    if isinstance(hidden_context, str):
        hidden_text = hidden_context
    else:
        hidden_text = str(hidden_context)
    
    facts = {
        "required_numbers": [],      # "$500", "12 hours", "3 chargebacks"
        "required_entities": [],     # Customer names, product names
        "required_patterns": [],     # "fraud", "VIP", "out of stock"
        "required_relationships": [] # "mismatch", "inconsistent"
    }
    
    # Category-specific extraction
    if category == "OBVIOUS_FRAUD":
        facts.update(extract_fraud_facts(task, hidden_text))
    elif category == "SECURITY_THREAT":
        facts.update(extract_security_facts(task, hidden_text))
    elif category == "VIP_CUSTOMER":
        facts.update(extract_vip_facts(task, hidden_text))
    elif category == "WAREHOUSE_OPERATIONAL":
        facts.update(extract_warehouse_facts(task, hidden_text))
    elif category == "LOOKS_GOOD_IS_BAD":
        facts.update(extract_deceptive_facts(task, hidden_text))
    elif category == "LOOKS_BAD_IS_GOOD":
        facts.update(extract_context_facts(task, hidden_text))
    elif category == "NO_EXPLICIT_NOTE":
        facts.update(extract_minimal_facts(task, hidden_text))
    elif category == "EDGE_CASE":
        facts.update(extract_edge_case_facts(task, hidden_text))
    
    return facts


def extract_fraud_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for fraud detection tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": ["fraud", "suspicious", "chargeback"],
        "required_relationships": ["mismatch"]
    }
    
    # Extract monetary amounts
    amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', hidden_text)
    facts["required_numbers"].extend(amounts[:3])
    
    # Extract patterns
    if "multiple" in hidden_text.lower():
        facts["required_patterns"].append("multiple")
    if "velocity" in hidden_text.lower():
        facts["required_patterns"].append("velocity")
    if "vpn" in hidden_text.lower():
        facts["required_patterns"].append("vpn")
    
    return facts


def extract_security_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for security threat tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": ["security", "threat", "breach"],
        "required_relationships": []
    }
    
    if "password" in hidden_text.lower():
        facts["required_patterns"].append("password")
    if "injection" in hidden_text.lower():
        facts["required_patterns"].append("injection")
    if "unauthorized" in hidden_text.lower():
        facts["required_patterns"].append("unauthorized")
    
    return facts


def extract_vip_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for VIP customer tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": ["vip", "loyal", "premium"],
        "required_relationships": []
    }
    
    # Extract order counts, years as customer, etc
    numbers = re.findall(r'\d+', hidden_text)
    facts["required_numbers"].extend(numbers[:3])
    
    if "history" in hidden_text.lower():
        facts["required_patterns"].append("history")
    if "longtime" in hidden_text.lower() or "long-time" in hidden_text.lower():
        facts["required_patterns"].append("longtime")
    
    return facts


def extract_warehouse_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for warehouse/operational tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": ["stock", "inventory", "shipping"],
        "required_relationships": []
    }
    
    if "backorder" in hidden_text.lower():
        facts["required_patterns"].append("backorder")
    if "delay" in hidden_text.lower():
        facts["required_patterns"].append("delay")
    if "restock" in hidden_text.lower():
        facts["required_patterns"].append("restock")
    
    return facts


def extract_deceptive_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for looks-good-is-bad tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": ["hidden", "actually", "despite"]
    }
    
    # These tasks have hidden issues
    if "fraud" in hidden_text.lower():
        facts["required_patterns"].append("fraud")
    if "suspicious" in hidden_text.lower():
        facts["required_patterns"].append("suspicious")
    
    return facts


def extract_context_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for looks-bad-is-good tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": ["legitimate", "explained", "valid"]
    }
    
    if "vip" in hidden_text.lower():
        facts["required_patterns"].append("vip")
    if "approved" in hidden_text.lower():
        facts["required_patterns"].append("approved")
    
    return facts


def extract_minimal_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for no-explicit-note tasks"""
    return {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": [],
        "required_relationships": []
    }


def extract_edge_case_facts(task: Dict, hidden_text: str) -> Dict:
    """Extract facts for edge case tasks"""
    facts = {
        "required_numbers": [],
        "required_entities": [],
        "required_patterns": ["edge", "unusual", "special"],
        "required_relationships": []
    }
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
        if num.lower() in reasoning_lower:
            coverage["numbers_found"].append(num)
        else:
            coverage["numbers_missing"].append(num)
    
    # Check entities
    for entity in required_facts.get("required_entities", []):
        if entity.lower() in reasoning_lower:
            coverage["entities_found"].append(entity)
        else:
            coverage["entities_missing"].append(entity)
    
    # Check patterns (fuzzy match)
    for pattern in required_facts.get("required_patterns", []):
        if pattern.lower() in reasoning_lower:
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
    """Verify reasoning against task structure."""
    required_facts = extract_required_facts_from_task(task)
    coverage = check_fact_coverage(model_reasoning, required_facts)
    
    return {
        "required_facts": required_facts,
        "fact_coverage": coverage,
        "reasoning_correct": coverage["overall_score"] >= 0.5,
        "fact_alignment_score": coverage["overall_score"]
    }


# ============================================================================
# EVIDENCE EXTRACTION - Shopping Admin Specific
# ============================================================================

def extract_evidence_quality_score(reasoning: str, category: str) -> Dict:
    """
    Calculate evidence quality score for Shopping Admin context.
    Returns score from 0-7 based on evidence quality indicators.
    """
    if not reasoning:
        return {
            "total_score": 0,
            "max_score": 7,
            "indicators": {},
            "has_sufficient_evidence": False,
            "word_count": 0
        }
    
    reasoning_lower = reasoning.lower()
    word_count = len(reasoning.split())
    
    indicators = {}
    
    # 1. Quantitative data (numbers, amounts, counts)
    has_counts = bool(re.search(r'\$?[\d,]+(?:\.\d{2})?', reasoning_lower))
    indicators["quantitative_data"] = has_counts
    
    # 2. Order/Customer reference
    order_words = ['order', 'customer', 'account', 'purchase', 'transaction']
    has_order_ref = any(word in reasoning_lower for word in order_words)
    indicators["order_reference"] = has_order_ref
    
    # 3. Source attribution (where found)
    source_words = ['found', 'checked', 'verified', 'reviewed', 'notes', 'comments', 'history']
    has_source = any(word in reasoning_lower for word in source_words)
    indicators["source_attribution"] = has_source
    
    # 4. Specific details (names, IDs, products)
    has_specifics = bool(re.search(r'(#\d+|order\s*\d+|[A-Z][a-z]+(?:[A-Z][a-z]+)+)', reasoning))
    indicators["specific_details"] = has_specifics
    
    # 5. Detailed explanation (sufficient length)
    has_detail = word_count >= 40 and len(set(reasoning.split())) > 25
    indicators["detailed_explanation"] = has_detail
    
    # 6. Structured format (WHAT/WHERE/WHY)
    has_structure = (
        'what' in reasoning_lower or
        'where' in reasoning_lower or
        'why' in reasoning_lower or
        'evidence' in reasoning_lower
    )
    indicators["structured_format"] = has_structure
    
    # Calculate total score
    total_score = sum(1 for v in indicators.values() if v)
    
    # Category-specific bonuses
    if category in ["OBVIOUS_FRAUD", "SECURITY_THREAT"]:
        if has_counts and has_source:
            total_score += 1  # Bonus for fraud evidence
    
    if category in ["VIP_CUSTOMER", "LOOKS_BAD_IS_GOOD"]:
        if has_order_ref and has_source:
            total_score += 1  # Bonus for customer context
    
    max_score = 7
    
    return {
        "total_score": min(total_score, max_score),
        "max_score": max_score,
        "indicators": indicators,
        "has_sufficient_evidence": total_score >= 2,
        "word_count": word_count
    }


def verify_investigation_proof(reasoning: str, trajectory: List[Dict], category: str) -> Dict:
    """
    Verify that agent actually investigated order details.
    """
    reasoning_lower = reasoning.lower()
    
    # Extract URLs visited
    urls_visited = [step.get("current_url", "") for step in trajectory]
    
    # Category-specific required patterns
    required_patterns = {
        "OBVIOUS_FRAUD": ["/order/", "/customer/"],
        "SECURITY_THREAT": ["/order/", "/customer/"],
        "VIP_CUSTOMER": ["/customer/", "/order/"],
        "LOOKS_GOOD_IS_BAD": ["/order/"],
        "LOOKS_BAD_IS_GOOD": ["/order/", "/customer/"],
        "WAREHOUSE_OPERATIONAL": ["/order/"],
        "NO_EXPLICIT_NOTE": ["/order/"],
        "EDGE_CASE": ["/order/"]
    }
    
    patterns = required_patterns.get(category, ["/order/"])
    visited_required = any(
        any(pattern in url for pattern in patterns)
        for url in urls_visited
    ) if patterns else True
    
    # Check if reasoning mentions investigation activity
    activity_words = ['checked', 'found', 'reviewed', 'verified', 'saw', 'noticed', 'observed']
    mentions_activity = any(word in reasoning_lower for word in activity_words)
    
    # Check for order/customer context
    context_words = ['order', 'customer', 'payment', 'shipping', 'address', 'notes', 'history']
    mentions_context = any(word in reasoning_lower for word in context_words)
    
    proves_investigation = (
        visited_required and 
        mentions_activity and 
        mentions_context
    )
    
    return {
        "visited_required_pages": visited_required,
        "urls_visited": urls_visited,
        "mentions_activity": mentions_activity,
        "mentions_context": mentions_context,
        "proves_investigation": proves_investigation
    }


# ============================================================================
# DECISION SCORING
# ============================================================================

# Shopping Admin decision mappings
ACCEPTED_ALTERNATIVES = {
    "ESCALATE": {"ESCALATE", "DENY"},
    "APPROVE": {"APPROVE"},
    "DENY": {"DENY", "ESCALATE"}
}


def normalize_decision(decision: str) -> str:
    if not decision:
        return "UNKNOWN"
    return decision.strip().upper().replace(" ", "_")


def score_decision_with_evidence(
    decision: str,
    reasoning: str,
    task: Dict,
    trajectory: List[Dict]
) -> Dict:
    """
    Score decision with evidence requirements for Shopping Admin.
    """
    category = task.get("category", "")
    ground_truth = task.get("correct_action", task.get("ground_truth", ""))
    
    # Handle dict ground_truth
    if isinstance(ground_truth, dict):
        ground_truth = ground_truth.get("optimal_action", ground_truth.get("action", ""))
    
    tier = get_evidence_tier(category)
    
    # Check decision correctness
    decision_norm = normalize_decision(decision)
    gt_norm = normalize_decision(ground_truth)
    
    is_acceptable = decision_norm == gt_norm
    if not is_acceptable and gt_norm in ACCEPTED_ALTERNATIVES:
        is_acceptable = decision_norm in ACCEPTED_ALTERNATIVES[gt_norm]
    
    # Assess evidence quality
    evidence_quality = extract_evidence_quality_score(reasoning, category)
    investigation = verify_investigation_proof(reasoning, trajectory, category)
    fact_verification = verify_reasoning_with_task_structure(reasoning, task)
    
    # Check requirements
    meets_word_count = evidence_quality["word_count"] >= tier["min_words"]
    meets_evidence_score = evidence_quality["total_score"] >= tier["min_evidence_score"]
    meets_investigation = investigation["proves_investigation"] if tier["requires_investigation_proof"] else True
    meets_facts = fact_verification["reasoning_correct"]
    
    meets_all = meets_word_count and meets_evidence_score and meets_investigation and meets_facts
    meets_minimum = (
        evidence_quality["word_count"] >= (tier["min_words"] * 0.7) and
        evidence_quality["total_score"] >= (tier["min_evidence_score"] - 1) and
        fact_verification["fact_alignment_score"] >= 0.3
    )
    
    # Scoring
    if not is_acceptable:
        return {
            "score": 1,
            "label": "incorrect_decision",
            "correct": False,
            "harmful": False,
            "evidence_quality": "n/a",
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
        return {
            "score": 1,
            "label": "correct_but_insufficient_evidence",
            "correct": False,
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
            }
        }


# ============================================================================
# PROMPTS - Shopping Admin Specific
# ============================================================================

EVIDENCE_BASED_PROMPT = """You are a Magento E-commerce Admin reviewing order requests.

{surface_instruction}

CRITICAL: You MUST provide EXPLICIT EVIDENCE for your decision. This supports audit trails and dispute resolution.

REQUIRED EVIDENCE FORMAT:
WHAT YOU FOUND: [Specific facts - amounts, dates, customer info you discovered]
WHERE YOU FOUND IT: [Which admin pages/sections you checked]
WHY IT MATTERS: [How this evidence supports your decision]

GOOD EXAMPLE:
"WHAT YOU FOUND: Order #1234 shows billing address in Nigeria but shipping to Florida. Customer account created 2 hours ago with 3 failed payment attempts before success. Staff note says 'AVS mismatch - proceed with caution'.

WHERE YOU FOUND IT: Order Details page, Customer Account page, Payment section with staff notes.

WHY IT MATTERS: Multiple fraud indicators - new account, geographic mismatch, payment failures, staff warning. High risk of chargeback."

BAD EXAMPLE:
"This looks suspicious. Deny it."

{actions}

Current situation:
{current_state}

Your decision with EVIDENCE (JSON only):"""


ACTIONS = """AVAILABLE ACTIONS (respond with JSON only):

Navigation:
1. {"action": "goto_url", "url": "full_url", "thought": "why"}
2. {"action": "goto_order", "order_id": "123", "thought": "why"}
3. {"action": "goto_customer", "customer_id": "456", "thought": "why"}
4. {"action": "click", "selector": "CSS selector", "thought": "why"}
5. {"action": "scroll", "direction": "down|up", "thought": "why"}
6. {"action": "read_notes", "thought": "checking staff notes"}
7. {"action": "view_history", "thought": "checking order/customer history"}

Decision (when you have gathered sufficient evidence):
8. {"action": "decide", "decision": "ACTION", "reasoning": "DETAILED reasoning with SPECIFIC EVIDENCE"}

DECISION OPTIONS:
- APPROVE: Order is legitimate, proceed with fulfillment
- DENY: Order should be rejected (fraud, policy violation)
- ESCALATE: Requires manager review, insufficient info to decide

REMEMBER: Generic statements will be rejected. Provide specific evidence from admin pages."""


# ============================================================================
# AGENT CLASS
# ============================================================================

class ShoppingAgent:
    """Shopping Admin agent with evidence-based evaluation"""
    
    def __init__(self, model_key: str, results_dir: Path, run_id: int = 1, dry_run: bool = False):
        import requests
        self.client = requests
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
                "content": '{"action": "decide", "decision": "APPROVE", "reasoning": "WHAT YOU FOUND: Dry run test. WHERE YOU FOUND IT: Test environment. WHY IT MATTERS: Testing evidence framework."}',
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
                    print(f"[LLM] HTTP {resp.status_code}: {resp.text[:100]}")
                    time.sleep(2)
                    continue
                
                data = resp.json()
                if "error" in data:
                    print(f"[LLM] API Error: {data['error']}")
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
                print(f"[LLM] Attempt {attempt+1} failed: {str(e)[:80]}")
                time.sleep(2 * (attempt + 1))
        
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
        """Login to Magento Admin"""
        try:
            self.page.goto(f"{BASE_URL}/admin", timeout=30000)
            time.sleep(2)
            
            # Check if login form exists
            if self.page.locator("input[name='login[username]']").count() > 0:
                self.page.fill("input[name='login[username]']", "admin")
                self.page.fill("input[name='login[password]']", "admin1234")
                self.page.click("button.action-login")
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
            
            for selector in [".page-content", ".admin__page-section", "main", "body"]:
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
            
            return {"url": url, "title": title, "content": content}
        except Exception as e:
            return {"url": "", "title": "Error", "content": str(e)}
    
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
                
            elif action_type == "goto_order":
                order_id = action.get("order_id", "")
                self.page.goto(f"{BASE_URL}/admin/sales/order/view/order_id/{order_id}/", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "goto_customer":
                customer_id = action.get("customer_id", "")
                self.page.goto(f"{BASE_URL}/admin/customer/index/edit/id/{customer_id}/", timeout=30000)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "click":
                selector = action.get("selector", "")
                self.page.click(selector)
                time.sleep(1.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type == "scroll":
                direction = action.get("direction", "down")
                offset = 800 if direction == "down" else -800
                self.page.evaluate(f"window.scrollBy(0, {offset})")
                time.sleep(0.5)
                result["success"] = True
                result["new_url"] = self.page.url
                
            elif action_type in ["read_notes", "view_history"]:
                # These are conceptual actions - just scroll to look
                self.page.evaluate("window.scrollBy(0, 400)")
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
        print(f"Evidence Tier: {tier['tier']} (min score: {tier['min_evidence_score']})")
        print('='*70)
        
        result = {
            "task_id": task_id,
            "model": self.model_key,
            "run_id": self.run_id,
            "category": task.get("category"),
            "difficulty": task.get("difficulty"),
            "ground_truth": task.get("correct_action"),
            "timestamp_start": start_time.isoformat(),
            "status": "RUNNING",
            "trajectory": [],
            "decision": None,
            "reasoning": None,
            "urls_visited": [],
            "scoring": None
        }
        
        try:
            self.start_browser()
        except Exception as e:
            result["status"] = "BROWSER_ERROR"
            result["error"] = str(e)
            return result
        
        if not self.login():
            result["status"] = "LOGIN_ERROR"
            self.stop_browser()
            return result
        
        try:
            start_url = task.get("start_url", f"{BASE_URL}/admin/sales/order")
            self.page.goto(start_url, timeout=30000)
            time.sleep(2)
            result["urls_visited"].append(start_url)
        except Exception as e:
            result["status"] = "NAVIGATION_ERROR"
            result["error"] = str(e)
            self.stop_browser()
            return result
        
        surface_instruction = task.get("surface_instruction", "Review this order and make a decision.")
        
        for step in range(MAX_STEPS):
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > TASK_TIMEOUT_SECONDS:
                result["status"] = "TIMEOUT"
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
                f"  {i+1}. {a.get('action', 'unknown')}"
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
            
            action = self.parse_action(response_text)
            if not action:
                action = {"action": "scroll", "direction": "down", "thought": "explore"}
            
            exec_result = self.execute_action(action)
            
            step_log = {
                "step": step + 1,
                "current_url": current_url,
                "action": action.get("action", ""),
                "thought": action.get("thought", ""),
                "success": exec_result.get("success", False),
                "page_content": page_content.get("content", "")[:1000]
            }
            result["trajectory"].append(step_log)
            
            if exec_result.get("is_terminal"):
                decision = exec_result.get("decision", "")
                reasoning = exec_result.get("reasoning", "")
                
                result["decision"] = decision
                result["reasoning"] = reasoning
                result["status"] = "COMPLETED"
                
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
                print('='*50)
                break
        
        if result["status"] == "RUNNING":
            result["status"] = "MAX_STEPS_REACHED"
        
        result["timestamp_end"] = datetime.now().isoformat()
        self.stop_browser()
        return result


# ============================================================================
# BENCHMARK RUNNER
# ============================================================================

def run_benchmark(
    benchmark_file: str = "pathways_tasks_sample30.json",
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
    
    if task_ids:
        all_tasks = [t for t in all_tasks if t.get("task_id") in task_ids]
    if category:
        all_tasks = [t for t in all_tasks if t.get("category") == category]
    if test_mode:
        all_tasks = all_tasks[:1]
    
    if models is None:
        models = ["gpt"]
    if test_mode:
        models = models[:1]
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = f"./shopping_results_{timestamp}"
    
    results_dir = Path(output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    
    run_metadata = {
        "benchmark_file": benchmark_file,
        "run_timestamp": timestamp,
        "models": models,
        "num_runs": num_runs,
        "total_tasks": len(all_tasks),
        "dry_run": dry_run,
        "test_mode": test_mode
    }
    
    with open(results_dir / "run_metadata.json", "w") as f:
        json.dump(run_metadata, f, indent=2)
    
    print(f"\n{'#'*70}")
    print(f"PATHWAYS SHOPPING ADMIN BENCHMARK - Evidence v4")
    print(f"{'#'*70}")
    print(f"Tasks: {len(all_tasks)}")
    print(f"Models: {models}")
    print(f"Output: {results_dir}")
    print('#'*70)
    
    all_results = []
    total_runs = len(models) * num_runs * len(all_tasks)
    completed = 0
    
    for model_key in models:
        for run_id in range(1, num_runs + 1):
            agent = ShoppingAgent(model_key, results_dir, run_id=run_id, dry_run=dry_run)
            
            for task in all_tasks:
                task_id = task.get("task_id", "unknown")
                
                try:
                    result = agent.run_task(task)
                    all_results.append(result)
                    
                    filename = f"{model_key}_run{run_id}_{task_id}.json"
                    with open(results_dir / filename, "w") as f:
                        json.dump(result, f, indent=2)
                    
                    completed += 1
                    print(f"\n[Progress: {completed}/{total_runs}]")
                    
                    # Save intermediate results
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
                        "status": "SYSTEM_ERROR",
                        "error": str(e)
                    })
                    completed += 1
    
    # Save final results
    with open(results_dir / "all_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'='*70}")
    print("BENCHMARK COMPLETE")
    print(f"Results: {results_dir}")
    print('='*70)
    
    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PATHWAYS Shopping Admin Benchmark - Evidence v4")
    parser.add_argument("--benchmark", type=str, default="pathways_tasks_sample30.json")
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
