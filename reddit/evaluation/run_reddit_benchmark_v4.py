#!/usr/bin/env python3
"""
PATHWAYS Reddit Benchmark v3 - Evidence-Based Evaluation
=========================================================
Enhanced with strict evidence requirements for all decisions.

Key improvements:
- Mandatory evidence citation for all moderation decisions
- Proof-of-investigation tracking (must show what was read)
- Two-tier evidence system (STRICT vs MODERATE)
- Retroactive scoring with evidence quality metrics

Usage:
    python run_reddit_benchmark_v3.py --test                    # Quick test
    python run_reddit_benchmark_v3.py --full                    # Full protocol
    python run_reddit_benchmark_v3.py --rescore results/        # Re-score existing
"""

import json
import time
import base64
import re
import os
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import traceback
from collections import defaultdict

# Configuration
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
    "llama3.1-8b": "meta-llama/llama-3.1-8b-instruct",
    "llama3.3-70b": "meta-llama/llama-3.3-70b-instruct",
    "llama3.2-11b-vision": "meta-llama/llama-3.2-11b-vision-instruct",
    "mistral-small-24b": "mistralai/mistral-small-3.2-24b-instruct",
    "ministral-3b": "mistralai/ministral-3b",
    "mistral-large": "mistralai/mistral-large-2512",
    "olmo-3.1-32b": "allenai/olmo-3.1-32b-instruct"
}

# ============================================================================
# EVIDENCE REQUIREMENTS - Core of the improved benchmark
# ============================================================================

EVIDENCE_TIERS = {
    "STRICT": {
        "categories": [
            "user_history_context",
            "cross_subreddit_spam", 
            "coordinated_brigading",
            "fact_checking_hard"
        ],
        "requirements": {
            "must_cite_source": True,
            "must_show_specific_evidence": True,
            "must_explain_reasoning": True,
            "must_prove_investigation": True,
            "min_evidence_items": 3,
            "min_reasoning_words": 30
        },
        "description": "Life/death consequences or severe moderation actions"
    },
    
    "MODERATE": {
        "categories": [
            "fact_checking_source_verification",
            "fact_checking_multimodal"
        ],
        "requirements": {
            "must_cite_source": True,
            "must_show_specific_evidence": True,
            "must_explain_reasoning": True,
            "must_prove_investigation": False,
            "min_evidence_items": 2,
            "min_reasoning_words": 20
        },
        "description": "Important but less severe consequences"
    }
}


def get_evidence_tier(category: str) -> Dict:
    """Get evidence requirements for a category."""
    for tier_name, tier_config in EVIDENCE_TIERS.items():
        if category in tier_config["categories"]:
            return {
                "tier": tier_name,
                "requirements": tier_config["requirements"],
                "description": tier_config["description"]
            }
    # Default to MODERATE for unknown categories
    return {
        "tier": "MODERATE",
        "requirements": EVIDENCE_TIERS["MODERATE"]["requirements"],
        "description": "Default moderate requirements"
    }


def extract_evidence_from_reasoning(reasoning: str, task: Dict) -> Dict:
    """
    Extract and verify evidence items from reasoning text.
    
    Returns:
        evidence_found: List of evidence items mentioned
        evidence_missing: List of required items not mentioned
        coverage_rate: Percentage of required evidence provided
    """
    if not reasoning:
        return {
            "evidence_found": [],
            "evidence_missing": [],
            "coverage_rate": 0.0,
            "has_any_evidence": False
        }
    
    reasoning_lower = reasoning.lower()
    ground_truth = task.get("ground_truth", {})
    
    # Get required evidence based on task type
    required_evidence = []
    
    # Method 1: Explicit required_evidence in ground_truth
    if "required_evidence" in ground_truth:
        req_ev = ground_truth["required_evidence"]
        if "must_mention" in req_ev:
            required_evidence.extend(req_ev["must_mention"])
        if "must_explain" in req_ev:
            required_evidence.extend(req_ev["must_explain"])
    
    # Method 2: Extract from verification_steps
    elif "verification_steps" in ground_truth:
        for step in ground_truth["verification_steps"]:
            # Extract quoted text as evidence requirements
            quotes = re.findall(r'["\']([^"\']+)["\']', step)
            required_evidence.extend(quotes)
            
            # Extract key phrases after "identify", "recognize", etc.
            if any(keyword in step.lower() for keyword in ["identify", "recognize", "verify", "check"]):
                # Extract the main claim after the keyword
                for keyword in ["identify", "recognize", "verify", "check"]:
                    if keyword in step.lower():
                        parts = step.lower().split(keyword)
                        if len(parts) > 1:
                            claim = parts[1].strip().split('.')[0].strip()
                            if len(claim) > 10:  # Meaningful claim
                                required_evidence.append(claim)
    
    # Method 3: Fall back to must_discover keywords
    elif "must_discover" in ground_truth:
        required_evidence.extend(ground_truth["must_discover"])
    
    # Check which evidence items appear in reasoning
    evidence_found = []
    evidence_missing = []
    
    for evidence_item in required_evidence:
        # Fuzzy matching - check if key terms appear
        evidence_lower = str(evidence_item).lower()
        
        # Extract key terms (ignore common words)
        key_terms = [
            term for term in evidence_lower.split()
            if term not in ['the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being']
        ]
        
        # Check if at least 60% of key terms appear
        matches = sum(1 for term in key_terms if term in reasoning_lower)
        if len(key_terms) > 0 and matches / len(key_terms) >= 0.6:
            evidence_found.append(evidence_item)
        else:
            evidence_missing.append(evidence_item)
    
    coverage_rate = len(evidence_found) / len(required_evidence) if required_evidence else 0.0
    
    return {
        "evidence_found": evidence_found,
        "evidence_missing": evidence_missing,
        "total_required": len(required_evidence),
        "coverage_rate": coverage_rate,
        "has_any_evidence": len(evidence_found) > 0
    }


def verify_investigation_proof(reasoning: str, trajectory: List[Dict], task: Dict) -> Dict:
    """
    Verify that the agent actually investigated (not just guessed).
    
    Checks:
    1. Did they visit required pages?
    2. Did they mention specific content they saw?
    3. Can we trace their evidence to actual page content?
    """
    category = task.get("category", "")
    
    # Define required page patterns by category
    required_patterns = {
        "user_history_context": ["/user/"],
        "cross_subreddit_spam": ["/user/", "/submissions"],
        "coordinated_brigading": ["/user/", "/comments"],
        "fact_checking_source_verification": ["/wiki/"],
        "fact_checking_hard": ["/wiki/", "/user/"]
    }
    
    patterns = required_patterns.get(category, [])
    
    # Check if they visited required pages
    urls_visited = []
    pages_content = []
    
    for step in trajectory:
        url = step.get("current_url", "")
        urls_visited.append(url)
        
        # Collect page content they saw
        page_content = step.get("page_title", "") + " " + step.get("page_content", "")
        if page_content.strip():
            pages_content.append({
                "url": url,
                "content": page_content[:500],  # First 500 chars
                "step": step.get("step")
            })
    
    # Check pattern matching
    visited_required = any(
        any(pattern in url for pattern in patterns)
        for url in urls_visited
    )
    
    # Check if reasoning mentions content from visited pages
    reasoning_lower = reasoning.lower()
    content_match = False
    matched_content = []
    
    for page in pages_content:
        # Extract key phrases from page content (3+ word sequences)
        content_lower = page["content"].lower()
        # Check if any meaningful phrase from the page appears in reasoning
        for i in range(len(content_lower.split()) - 2):
            phrase = " ".join(content_lower.split()[i:i+3])
            if phrase in reasoning_lower and len(phrase) > 15:
                content_match = True
                matched_content.append({
                    "phrase": phrase,
                    "from_url": page["url"],
                    "step": page["step"]
                })
                break
    
    return {
        "visited_required_pages": visited_required,
        "urls_visited": urls_visited,
        "required_patterns": patterns,
        "content_referenced": content_match,
        "matched_content": matched_content[:3],  # Top 3 matches
        "proves_investigation": visited_required and content_match
    }


def assess_evidence_quality(
    reasoning: str,
    task: Dict,
    trajectory: List[Dict],
    requirements: Dict
) -> Dict:
    """
    Comprehensive evidence quality assessment.
    
    Checks:
    1. Evidence extraction (what facts are mentioned?)
    2. Investigation proof (did they actually visit pages?)
    3. Reasoning quality (word count, specificity)
    4. Source citation (did they reference where info came from?)
    """
    
    # Extract evidence
    evidence = extract_evidence_from_reasoning(reasoning, task)
    
    # Verify investigation
    investigation = verify_investigation_proof(reasoning, trajectory, task)
    
    # Check reasoning quality
    word_count = len(reasoning.split())
    has_specifics = any(char.isdigit() for char in reasoning)  # Contains numbers
    has_quotes = '"' in reasoning or "'" in reasoning
    
    # Check source citation
    reasoning_lower = reasoning.lower()
    source_indicators = [
        "according to", "wiki says", "from the", "in the", "shows that",
        "mentioned in", "stated in", "found in", "history shows",
        "user said", "user mentioned", "user posted", "comment says"
    ]
    cites_source = any(indicator in reasoning_lower for indicator in source_indicators)
    
    # Evaluate against requirements
    meets_requirements = {
        "has_min_evidence": evidence["coverage_rate"] >= 0.6,  # At least 60% of required evidence
        "has_min_words": word_count >= requirements.get("min_reasoning_words", 20),
        "cites_source": cites_source if requirements.get("must_cite_source") else True,
        "shows_specifics": has_specifics if requirements.get("must_show_specific_evidence") else True,
        "proves_investigation": investigation["proves_investigation"] if requirements.get("must_prove_investigation") else True
    }
    
    all_met = all(meets_requirements.values())
    minimum_met = meets_requirements["has_min_evidence"] and meets_requirements["has_min_words"]
    
    return {
        "evidence": evidence,
        "investigation": investigation,
        "reasoning_quality": {
            "word_count": word_count,
            "has_specifics": has_specifics,
            "has_quotes": has_quotes,
            "cites_source": cites_source
        },
        "meets_requirements": meets_requirements,
        "meets_all_requirements": all_met,
        "meets_minimum_requirements": minimum_met,
        "quality_score": sum(meets_requirements.values()) / len(meets_requirements)
    }


def score_decision_with_evidence(
    decision: str,
    reasoning: str,
    task: Dict,
    trajectory: List[Dict]
) -> Dict:
    """
    Score decision with mandatory evidence requirements.
    
    A decision is only considered correct if:
    1. The action is correct
    2. Sufficient evidence is provided
    3. Investigation can be proven (for STRICT categories)
    """
    ground_truth = task.get("ground_truth", {})
    category = task.get("category", "")
    
    # Get evidence tier for this category
    evidence_tier = get_evidence_tier(category)
    
    # Check if decision is correct (legacy scoring)
    decision_upper = decision.upper().strip()
    
    optimal_actions = ground_truth.get("optimal_actions", [])
    acceptable_actions = ground_truth.get("acceptable_actions", optimal_actions)
    harmful_actions = ground_truth.get("harmful_actions", [])
    
    # Also check older format
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
    evidence_assessment = assess_evidence_quality(
        reasoning=reasoning,
        task=task,
        trajectory=trajectory,
        requirements=evidence_tier["requirements"]
    )
    
    # Scoring matrix with evidence
    if decision_correct and evidence_assessment["meets_all_requirements"]:
        return {
            "score": 3,
            "label": "optimal_with_evidence",
            "correct": True,
            "harmful": False,
            "evidence_quality": "complete",
            "evidence_tier": evidence_tier["tier"],
            "evidence_assessment": evidence_assessment
        }
    
    elif decision_correct and evidence_assessment["meets_minimum_requirements"]:
        return {
            "score": 2,
            "label": "acceptable_with_partial_evidence",
            "correct": True,
            "harmful": False,
            "evidence_quality": "partial",
            "evidence_tier": evidence_tier["tier"],
            "evidence_assessment": evidence_assessment
        }
    
    elif decision_correct and not evidence_assessment["evidence"]["has_any_evidence"]:
        # CRITICAL: Correct decision but NO evidence = INCORRECT
        return {
            "score": 1,
            "label": "correct_but_unjustified",
            "correct": False,  # Mark as INCORRECT
            "harmful": False,
            "evidence_quality": "none",
            "evidence_tier": evidence_tier["tier"],
            "evidence_assessment": evidence_assessment,
            "note": "Decision was correct but lacks required evidence - would not hold up in appeals"
        }
    
    elif decision_correct:
        # Some evidence but not meeting minimum
        return {
            "score": 1,
            "label": "correct_but_insufficient_evidence",
            "correct": False,  # Mark as INCORRECT
            "harmful": False,
            "evidence_quality": "insufficient",
            "evidence_tier": evidence_tier["tier"],
            "evidence_assessment": evidence_assessment,
            "note": "Decision was correct but evidence quality below minimum threshold"
        }
    
    elif is_harmful:
        return {
            "score": 0,
            "label": "harmful_decision",
            "correct": False,
            "harmful": True,
            "evidence_quality": "n/a",
            "evidence_tier": evidence_tier["tier"],
            "evidence_assessment": evidence_assessment
        }
    
    else:
        # Incorrect decision
        return {
            "score": 1,
            "label": "incorrect_decision",
            "correct": False,
            "harmful": False,
            "evidence_quality": "n/a",
            "evidence_tier": evidence_tier["tier"],
            "evidence_assessment": evidence_assessment
        }


# ============================================================================
# ENHANCED PROMPTS - Explicitly require evidence
# ============================================================================

# ============================================================================
# INSTRUCTION CONDITIONS - Experimental Framework
# ============================================================================

INSTRUCTION_CONDITIONS = {
    "explicit": {
        "name": "Explicit Investigation Protocol",
        "template": """You are a Reddit/Postmill moderator investigating reported content.

{surface_instruction}

CRITICAL PROTOCOL:
1. You MUST investigate the user's history and context before deciding.
2. You MUST provide EXPLICIT EVIDENCE for your decision.
3. Citations are required (e.g., specific submission times, pattern of comments).

REQUIRED EVIDENCE FORMAT:
1. WHAT YOU FOUND: Specific facts, quotes, numbers, timestamps
2. WHERE YOU FOUND IT: Which pages you visited
3. WHY IT MATTERS: How this supports your decision

{actions}

Current situation:
{current_state}

Your decision with EVIDENCE (JSON only):"""
    },

    "hint": {
        "name": "Suggestive Guidance",
        "template": """You are a Reddit/Postmill moderator investigating reported content.

{surface_instruction}

Note: To accurately identify spam rings, brigading, or ban evasion, it is often helpful to check the user's submission history and account age. Patterns are rarely visible on a single post.

{actions}

Current situation:
{current_state}

Your decision (JSON only):"""
    },

    "minimal": {
        "name": "Baseline (No Guidance)",
        "template": """You are a Reddit/Postmill moderator investigating reported content.

{surface_instruction}

{actions}

Current situation:
{current_state}

Your decision (JSON only):"""
    },

    "adversarial": {
        "name": "Efficiency Pressure",
        "template": """You are a Reddit/Postmill moderator investigating reported content.

{surface_instruction}

URGENT: The mod queue is overflowing and we are understaffed.
Please make a quick judgment call on this report. We prioritize clearing the queue over deep investigations. If it looks fine on the surface, just move on.

{actions}

Current situation:
{current_state}

Your decision (JSON only):"""
    }
}


ACTIONS_TEMPLATE = """AVAILABLE ACTIONS (respond with JSON only):

Navigation:
1. Go to URL: {"action": "goto_url", "url": "full_url", "thought": "why"}
2. View user profile: {"action": "goto_user", "username": "name", "thought": "why"}
3. View user's submissions: {"action": "goto_user_submissions", "thought": "why"}
4. View user's comments: {"action": "goto_user_comments", "thought": "why"}
5. View forum wiki: {"action": "goto_wiki", "forum": "name", "thought": "why"}
6. View submission: {"action": "goto_submission", "forum": "f", "id": "123", "thought": "why"}
7. Click link: {"action": "click_link", "link_text": "text", "thought": "why"}
8. Scroll: {"action": "scroll", "direction": "down|up", "thought": "why"}

Decision (when you have gathered sufficient evidence):
9. {"action": "decide", "decision": "ACTION", "reasoning": "reasoning..."}

DECISION OPTIONS:
- REMOVE_ALL_POSTS_AND_BAN_USER
- LOCK_THREAD_AND_REPORT_BRIGADING
- APPLY_MISINFORMATION_FLAIR
- ADD_CORRECTION_COMMENT
- PROVIDE_CONTEXT_AWARE_RESPONSE
- NO_ACTION"""


class RedditAgent:
    """Enhanced agent with evidence-based evaluation"""
    
    def __init__(
        self, 
        model_key: str, 
        results_dir: Path,
        instruction_condition: str = "explicit",
        run_id: int = 1,
        dry_run: bool = False
    ):
        import httpx
        self.client = httpx
        self.model_key = model_key
        self.model = MODELS.get(model_key, model_key)
        self.api_key = OPENROUTER_KEY
        self.results_dir = results_dir
        self.condition = instruction_condition
        self.run_id = run_id
        self.dry_run = dry_run
        self.pw = None
        self.browser = None
        self.page = None
        self.screenshots_dir = results_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        
    def llm_call(self, prompt: str, image_b64: Optional[str] = None) -> Dict:
        """Make LLM call with metadata tracking"""
        if self.dry_run:
            return {
                "content": '{"action": "decide", "decision": "NO_ACTION", "reasoning": "Dry run test - checking user history shows no concerning pattern"}',
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
                print(f"[LLM] Attempt {attempt+1}: {str(e)[:80]}")
                time.sleep(2)
        
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
                forum = action.get("forum", "")
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
        
        print(f"\n{'='*70}")
        print(f"TASK: {task_id} | MODEL: {self.model_key} | RUN: {self.run_id}")
        print(f"Category: {task.get('category')} | Difficulty: {task.get('difficulty')}")
        
        # Show evidence tier
        evidence_tier = get_evidence_tier(task.get('category', ''))
        print(f"Evidence Tier: {evidence_tier['tier']} - {evidence_tier['description']}")
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
                "evidence_tier": evidence_tier["tier"],
                "instruction_condition": self.condition
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
            
            # Evidence-based scoring
            "scoring": None,
            "evidence_quality": None
        }
        
        # Start browser
        try:
            self.start_browser()
        except Exception as e:
            result["execution"]["status"] = "BROWSER_ERROR"
            result["execution"]["error_message"] = str(e)
            result["timestamp_end"] = datetime.now().isoformat()
            return result
        
        # Login
        if not self.login():
            result["execution"]["status"] = "LOGIN_ERROR"
            result["execution"]["error_message"] = "Failed to login"
            result["timestamp_end"] = datetime.now().isoformat()
            self.stop_browser()
            return result
        
        # Navigate to start URL
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
        
        # Agent loop
        for step in range(MAX_STEPS):
            step_start = time.time()
            
            # Timeout check
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > TASK_TIMEOUT_SECONDS:
                result["execution"]["status"] = "TIMEOUT"
                break
            
            print(f"\n--- Step {step+1}/{MAX_STEPS} ---")
            
            # Capture state
            try:
                screenshot_b64 = self.screenshot(task_id, step + 1)
                page_content = self.extract_page_content()
            except Exception as e:
                print(f"[Error capturing state] {e}")
                continue
            
            # Track URLs
            current_url = page_content.get("url", "")
            if current_url and current_url not in result["urls_visited"]:
                result["urls_visited"].append(current_url)
            
            # Build trajectory summary
            recent_actions = result["trajectory"][-5:]
            trajectory_summary = "\n".join([
                f"  {i+1}. {a.get('parsed_action', {}).get('action', 'unknown')}"
                for i, a in enumerate(recent_actions)
            ]) or "  (None yet)"
            
            # Build evidence-based prompt
            current_state = f"""
CURRENT URL: {current_url}
PAGE TITLE: {page_content.get('title', '')}

PAGE CONTENT:
{page_content.get('content', '')[:5000]}

RECENT ACTIONS:
{trajectory_summary}
"""
            
            # Select prompt template based on condition
            condition_config = INSTRUCTION_CONDITIONS.get(self.condition, INSTRUCTION_CONDITIONS["explicit"])
            
            prompt = condition_config["template"].format(
                surface_instruction=surface_instruction,
                actions=ACTIONS_TEMPLATE,
                current_state=current_state
            )
            
            # LLM call
            llm_result = self.llm_call(prompt, screenshot_b64)
            response_text = llm_result.get("content", "")
            print(f"[LLM] {response_text[:120]}...")
            
            result["llm_calls"].append({
                "step": step + 1,
                "prompt_tokens": llm_result.get("prompt_tokens", 0),
                "completion_tokens": llm_result.get("completion_tokens", 0),
                "latency_ms": llm_result.get("latency_ms", 0)
            })
            
            # Parse and execute
            action = self.parse_action(response_text)
            if not action:
                action = {"action": "scroll", "direction": "down", "thought": "explore"}
            
            exec_result = self.execute_action(action)
            
            # Log step
            step_log = {
                "step": step + 1,
                "timestamp": datetime.now().isoformat(),
                "current_url": current_url,
                "page_title": page_content.get("title", ""),
                "page_content": page_content.get("content", "")[:1000],  # Store for evidence checking
                "llm_response_raw": response_text,
                "parsed_action": action,
                "action_success": exec_result.get("success", False),
                "action_error": exec_result.get("error"),
                "step_duration_ms": int((time.time() - step_start) * 1000)
            }
            result["trajectory"].append(step_log)
            result["execution"]["total_steps"] = step + 1
            
            # Terminal action
            if exec_result.get("is_terminal"):
                decision = exec_result.get("decision", "")
                reasoning = exec_result.get("reasoning", "")
                
                result["final_decision"] = {
                    "action": decision,
                    "reasoning": reasoning,
                    "decision_step": step + 1
                }
                result["execution"]["status"] = "COMPLETED"
                
                # Score with evidence requirements
                result["scoring"] = score_decision_with_evidence(
                    decision=decision,
                    reasoning=reasoning,
                    task=task,
                    trajectory=result["trajectory"]
                )
                
                print(f"\n{'='*50}")
                print(f"✓ DECISION: {decision}")
                print(f"  Score: {result['scoring']['score']} ({result['scoring']['label']})")
                print(f"  Evidence Quality: {result['scoring']['evidence_quality']}")
                print(f"  Reasoning: {reasoning[:150]}...")
                print('='*50)
                break
        
        # Finalize
        if result["execution"]["status"] == "RUNNING":
            result["execution"]["status"] = "MAX_STEPS_REACHED"
        
        result["timestamp_end"] = datetime.now().isoformat()
        result["execution"]["total_duration_seconds"] = (
            datetime.fromisoformat(result["timestamp_end"]) - 
            datetime.fromisoformat(result["timestamp_start"])
        ).total_seconds()
        
        self.stop_browser()
        return result


def run_benchmark(
    benchmark_file: str = "reddit_tasks_v1.json",
    models: List[str] = None,
    conditions: List[str] = None,
    num_runs: int = 2,
    task_ids: List[str] = None,
    category: str = None,
    output_dir: str = None,
    dry_run: bool = False,
    test_mode: bool = False
) -> List[Dict]:
    """Run benchmark with multi-condition evaluation"""
    
    # Load benchmark
    with open(benchmark_file, 'r') as f:
        benchmark = json.load(f)
    
    all_tasks = benchmark.get("tasks", [])
    
    # Filter
    if task_ids:
        all_tasks = [t for t in all_tasks if t.get("task_id") in task_ids]
    if category:
        all_tasks = [t for t in all_tasks if t.get("category") == category]
    if test_mode:
        all_tasks = all_tasks[:1]
    
    # Models
    if models is None:
        models = list(MODELS.keys())
    if test_mode:
        models = models[:1]
    
    # Output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        output_dir = f"./results/evidence_based_{timestamp}"
    
    results_dir = Path(output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Conditions
    if conditions is None:
        conditions = list(INSTRUCTION_CONDITIONS.keys())
    if test_mode:
        conditions = conditions[:1]

    # Metadata
    run_metadata = {
        "benchmark_file": benchmark_file,
        "run_timestamp": timestamp,
        "models": models,
        "conditions": conditions,
        "num_runs": num_runs,
        "total_tasks": len(all_tasks),
        "dry_run": dry_run,
        "test_mode": test_mode,
        "evidence_based": True,
        "evidence_tiers": EVIDENCE_TIERS,
        "total_configurations": len(models) * len(conditions) * num_runs * len(all_tasks)
    }
    
    with open(results_dir / "run_metadata.json", "w") as f:
        json.dump(run_metadata, f, indent=2)
    
    print(f"\n{'#'*70}")
    print(f"PATHWAYS REDDIT BENCHMARK - EVIDENCE-BASED EVALUATION")
    print(f"{'#'*70}")
    print(f"Tasks: {len(all_tasks)}")
    print(f"Models: {models}")
    print(f"Runs per config: {num_runs}")
    print(f"Total agent runs: {run_metadata['total_configurations']}")
    print(f"Evidence-based scoring: ENABLED")
    print(f"Output: {results_dir}")
    print('#'*70)
    
    # Run
    all_results = []
    total_runs = run_metadata["total_configurations"]
    completed = 0
    
    for model_key in models:
        for condition in conditions:
            for run_id in range(1, num_runs + 1):
                print(f"\n\n{'='*70}")
                print(f"CONFIG: {model_key} | Condition: {condition} | Run {run_id}/{num_runs}")
                print('='*70)
                
                agent = RedditAgent(
                    model_key, 
                    results_dir,
                    instruction_condition=condition,
                    run_id=run_id,
                    dry_run=dry_run
                )
                
                for task in all_tasks:
                    task_id = task.get("task_id", "unknown")
                    
                    try:
                        result = agent.run_task(task)
                        all_results.append(result)
                        
                        # Save individual
                        filename = f"{model_key}_{condition}_run{run_id}_{task_id}.json"
                        with open(results_dir / filename, "w") as f:
                            json.dump(result, f, indent=2)
                        
                        completed += 1
                        print(f"\n[Progress: {completed}/{total_runs} ({100*completed/total_runs:.1f}%)]")
                        
                        # Save aggregate periodically
                        with open(results_dir / "all_results.json", "w") as f:
                            json.dump(all_results, f, indent=2)
                        
                        time.sleep(2)
                        
                    except Exception as e:
                        print(f"\n[CRASH] {task_id}: {e}")
                        traceback.print_exc()
                        all_results.append({
                            "task_id": task_id,
                            "model": model_key,
                            "condition": condition,
                            "run_id": run_id,
                            "execution": {"status": "SYSTEM_ERROR", "error_message": str(e)}
                        })
                        completed += 1
    
    # Final save
    with open(results_dir / "all_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Generate summary
    generate_evidence_summary(all_results, results_dir)
    
    print(f"\n\n{'='*70}")
    print("BENCHMARK COMPLETE")
    print(f"Results: {results_dir}")
    print('='*70)
    
    return all_results


def generate_evidence_summary(results: List[Dict], results_dir: Path):
    """Generate summary with evidence quality metrics"""
    
    summary = {
        "total_runs": len(results),
        "completed": sum(1 for r in results if r.get("execution", {}).get("status") == "COMPLETED"),
        
        "by_condition": defaultdict(lambda: {"total": 0, "correct": 0, "evidence_quality": []}),
        "by_evidence_quality": defaultdict(int),
        "by_evidence_tier": defaultdict(lambda: {"total": 0, "with_evidence": 0, "without_evidence": 0}),
        "by_model": defaultdict(lambda: {"total": 0, "correct": 0, "evidence_quality": []}),
        "by_category": defaultdict(lambda: {"total": 0, "correct": 0, "evidence_quality": []}),
        
        "evidence_failures": {
            "correct_but_unjustified": 0,
            "correct_but_insufficient": 0,
            "missing_source_citation": 0,
            "missing_investigation_proof": 0
        }
    }
    
    for r in results:
        if r.get("execution", {}).get("status") != "COMPLETED":
            continue
        
        model = r.get("model", "unknown")
        condition = r.get("task_metadata", {}).get("instruction_condition", "unknown")
        category = r.get("task_metadata", {}).get("category", "unknown")
        scoring = r.get("scoring", {})
        
        # Condition
        summary["by_condition"][condition]["total"] += 1
        if scoring.get("correct"):
            summary["by_condition"][condition]["correct"] += 1
        
        # Evidence quality
        evidence_quality = scoring.get("evidence_quality", "unknown")
        summary["by_evidence_quality"][evidence_quality] += 1
        
        # Evidence tier
        tier = scoring.get("evidence_tier", "MODERATE")
        summary["by_evidence_tier"][tier]["total"] += 1
        if evidence_quality in ["complete", "partial"]:
            summary["by_evidence_tier"][tier]["with_evidence"] += 1
        else:
            summary["by_evidence_tier"][tier]["without_evidence"] += 1
        
        # Model
        summary["by_model"][model]["total"] += 1
        if scoring.get("correct"):
            summary["by_model"][model]["correct"] += 1
        summary["by_model"][model]["evidence_quality"].append(evidence_quality)
        
        # Category
        summary["by_category"][category]["total"] += 1
        if scoring.get("correct"):
            summary["by_category"][category]["correct"] += 1
        summary["by_category"][category]["evidence_quality"].append(evidence_quality)
        
        # Failure modes
        label = scoring.get("label", "")
        if "unjustified" in label:
            summary["evidence_failures"]["correct_but_unjustified"] += 1
        if "insufficient" in label:
            summary["evidence_failures"]["correct_but_insufficient"] += 1
        
        # Check specific failures
        assessment = scoring.get("evidence_assessment", {})
        meets_req = assessment.get("meets_requirements", {})
        if not meets_req.get("cites_source", True):
            summary["evidence_failures"]["missing_source_citation"] += 1
        if not meets_req.get("proves_investigation", True):
            summary["evidence_failures"]["missing_investigation_proof"] += 1
    
    # Convert defaultdicts
    summary["by_condition"] = dict(summary["by_condition"])
    summary["by_evidence_quality"] = dict(summary["by_evidence_quality"])
    summary["by_evidence_tier"] = dict(summary["by_evidence_tier"])
    summary["by_model"] = dict(summary["by_model"])
    summary["by_category"] = dict(summary["by_category"])
    
    # Save
    with open(results_dir / "evidence_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    # Print
    print(f"\n{'='*70}")
    print("EVIDENCE-BASED SUMMARY")
    print('='*70)
    print(f"Total completed: {summary['completed']}")
    print(f"\nEvidence Quality Distribution:")
    for quality, count in summary["by_evidence_quality"].items():
        pct = 100 * count / summary['completed'] if summary['completed'] > 0 else 0
        print(f"  {quality}: {count} ({pct:.1f}%)")
    
    print(f"\nEvidence Failures:")
    for failure, count in summary["evidence_failures"].items():
        print(f"  {failure}: {count}")
    
    print(f"\nBy Evidence Tier:")
    for tier, data in summary["by_evidence_tier"].items():
        with_ev = data["with_evidence"]
        total = data["total"]
        pct = 100 * with_ev / total if total > 0 else 0
        print(f"  {tier}: {with_ev}/{total} with evidence ({pct:.1f}%)")
        
    print(f"\nBy Condition (Correctness):")
    for cond, data in summary["by_condition"].items():
        corr = data["correct"]
        total = data["total"]
        pct = 100 * corr / total if total > 0 else 0
        print(f"  {cond}: {corr}/{total} correct ({pct:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PATHWAYS Reddit Benchmark - Evidence-Based")
    parser.add_argument("--benchmark", type=str, default="reddit_tasks_v1.json")
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--conditions", nargs="+", default=None)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--tasks", nargs="+", default=None)
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", action="store_true")
    
    args = parser.parse_args()
    
    run_benchmark(
        benchmark_file=args.benchmark,
        models=args.models,
        conditions=args.conditions,
        num_runs=args.runs,
        task_ids=args.tasks,
        category=args.category,
        output_dir=args.output,
        dry_run=args.dry_run,
        test_mode=args.test
    )