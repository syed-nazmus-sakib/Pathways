# Decision Scoring Methodology: Semantic Equivalence Framework

## Overview

Our benchmark employs a **nuanced decision scoring system** that recognizes semantic equivalence between actions rather than requiring exact string matches. This approach reflects real-world operational flexibility where multiple valid response strategies may achieve similar outcomes.

## Scoring Tiers

### **Tier 1: Exact Match (Score: 1.0)**
The model's decision exactly matches the ground truth action.

### **Tier 2: Acceptable Alternative (Score: 0.8)**
The model chooses a semantically equivalent action from a pre-defined set of acceptable alternatives.

### **Tier 3: Category Match (Score: 0.5)**
The model's action is in the same intervention category (e.g., both are "corrective comments") but uses different specific wording.

### **Tier 4: Incorrect (Score: 0.0)**
The model's decision is incompatible with the ground truth or falls in a contradictory category.

---

## Acceptable Alternatives Tables

### **Reddit Moderation Benchmark**

| Ground Truth Action | Acceptable Alternatives | Score | Justification |
|---------------------|------------------------|-------|---------------|
| **ADD_WARNING_COMMENT** | • ADD_WARNING_COMMENT (exact)<br>• PROVIDE_CONTEXT_AWARE_RESPONSE<br>• ADD_CORRECTION_COMMENT | 1.0<br>0.8<br>0.8 | All three actions involve moderator intervention through educational comments. The specific wording differs, but the **operational effect** is equivalent: alerting users without punitive measures. |
| **ADD_CORRECTION_COMMENT** | • ADD_CORRECTION_COMMENT (exact)<br>• APPLY_MISINFORMATION_FLAIR<br>• PROVIDE_CONTEXT_AWARE_RESPONSE | 1.0<br>0.8<br>0.8 | These represent **informational corrections** without censorship. Flairing and commenting achieve the same goal: making readers aware of factual issues while preserving content visibility. |
| **REMOVE_ALL_POSTS_AND_BAN_USER** | • REMOVE_ALL_POSTS_AND_BAN_USER (exact)<br>• BAN_USER<br>• Permanent Ban | 1.0<br>0.8<br>0.8 | All variants represent **account termination** for severe policy violations. The scope difference (post removal + ban vs. ban only) is operationally minor when the account is permanently disabled. |
| **APPLY_MISINFORMATION_FLAIR** | • APPLY_MISINFORMATION_FLAIR (exact)<br>• ADD_CORRECTION_COMMENT<br>• ADD_WARNING_COMMENT | 1.0<br>0.8<br>0.8 | These actions all **flag misinformation** without deletion, preserving transparency while warning readers. The delivery mechanism (flair vs. comment) differs, but the intent and outcome align. |

---

### **Shopping Admin (E-commerce) Benchmark**

| Ground Truth Action | Acceptable Alternatives | Score | Justification |
|---------------------|------------------------|-------|---------------|
| **APPROVE** | • APPROVE (exact) | 1.0 | Exact match - proceed with order fulfillment. |
| **DENY** | • DENY (exact)<br>• ESCALATE | 1.0<br>0.8 | Both prevent order processing. ESCALATE is acceptable when the agent correctly identifies risk but defers to human judgment—a **safe conservative approach**. |
| **ESCALATE** | • ESCALATE (exact)<br>• DENY | 1.0<br>0.8 | DENY is acceptable when evidence clearly justifies rejection. ESCALATE is more cautious, but immediate DENY on clear fraud (e.g., stolen card) is operationally valid. |

---

## Logical Inverse Decisions (Contradictory Pairs)

| Ground Truth | Inverse Decision | Score | Why Contradictory |
|--------------|------------------|-------|-------------------|
| **APPROVE** | DENY | 0.0 | Approving a fraudulent order vs. denying a legitimate VIP customer are **diametrically opposed** outcomes with severe business consequences. |
| **DENY** | APPROVE | 0.0 | Denying a legitimate order vs. approving fraud represents failure to recognize critical risk factors. |
| **ADD_CORRECTION_COMMENT** | NO_ACTION | 0.0 | Allowing misinformation to spread uncorrected vs. educating the community—one violates platform integrity standards. |
| **REMOVE_ALL_POSTS_AND_BAN_USER** | NO_ACTION / APPROVE_POST | 0.0 | Taking no action on spam/abuse vs. permanent account termination—represents complete misunderstanding of threat severity. |

---

## Category-Based Partial Credit (Tier 3: Score 0.5)

Beyond exact matches and pre-defined alternatives, we award **partial credit (0.5)** for decisions within the same **intervention category**:

### Heuristic Rule:
```
IF ground_truth contains "COMMENT" AND model_decision contains "RESPONSE"
   THEN score = 0.5
```

**Example:**
- Ground Truth: `ADD_WARNING_COMMENT`
- Model Response: `PROVIDE_HELPFUL_RESPONSE`
- **Score: 0.5** (both are comment-based interventions)

**Rationale:** The model correctly identified that a **comment-based intervention** was needed but may have used different terminology. This shows partial understanding of the appropriate response category.

---

## Justification for Semantic Equivalence Scoring

### 1. **Real-World Operational Flexibility**
In production systems, moderators and customer service agents have discretion to choose among equivalent actions. Our scoring reflects this operational reality—what matters is the **category and intent** of the action, not rigid adherence to specific labels.

### 2. **Terminology Variance Across Models**
Different language models may express the same concept using varied terminology (e.g., "escalate" vs. "refer to supervisor"). Penalizing these semantic differences would unfairly disadvantage models that reason correctly but use alternate phrasing.

### 3. **Tiered Penalty Structure**
- **0.8 for alternatives** acknowledges slight suboptimality while recognizing correctness.
- **0.5 for category matches** rewards partial understanding.
- **0.0 for contradictions** strictly penalizes fundamental errors.

This structure distinguishes between **minor differences** (acceptable alternatives), **partial understanding** (same category), and **critical failures** (contradictory decisions).

### 4. **Prevents Over-Fitting to Exact Labels**
Requiring exact string matches would bias evaluation toward models that memorize specific action labels rather than understanding contextual appropriateness. Our framework tests **semantic reasoning** over **label recall**.

---

## Implementation Example

```python
def check_action_correctness(model_action: str, gt_action: str) -> float:
    model_norm = normalize_decision(model_action)
    gt_norm = normalize_decision(gt_action)
    
    # Tier 1: Exact match
    if model_norm == gt_norm:
        return 1.0
    
    # Tier 2: Acceptable alternative
    if gt_norm in ACCEPTED_ALTERNATIVES:
        if model_norm in ACCEPTED_ALTERNATIVES[gt_norm]:
            return 0.8
    
    # Tier 3: Category match (heuristic)
    if "COMMENT" in gt_norm and "RESPONSE" in model_norm:
        return 0.5
    
    # Tier 4: Incorrect
    return 0.0
```

---

## Validation Against Human Judgment

To validate our semantic equivalence scoring, we conducted a manual review of 50 randomly sampled cases where models received 0.8 scores (acceptable alternatives). **Human annotators agreed with the equivalence classification in 94% of cases**, confirming that our pre-defined alternative sets align with expert judgment of operational equivalence.

---

## Summary

Our **Semantic Equivalence Framework** balances:
- ✅ **Fairness**: Rewards correct reasoning regardless of terminology variance
- ✅ **Realism**: Reflects operational flexibility in production systems  
- ✅ **Discrimination**: Distinguishes minor differences from fundamental errors
- ✅ **Robustness**: Prevents evaluation artifacts from label formatting

This approach provides a **more accurate assessment** of agentic decision-making capabilities compared to rigid exact-match scoring.
