# ================================================================================
# PATHWAYS REDDIT BENCHMARK - COMPREHENSIVE METRICS GUIDE
# ================================================================================
# Final Documentation for ICML Paper
# Date: 2026-01-23
# ================================================================================

"""
This document provides complete explanations of all metrics, tables, and their
correct interpretations for the PATHWAYS Reddit Moderation Benchmark.

BENCHMARK OVERVIEW:
- 116 tasks across 6 categories
- 4 AI models tested: Gemini 3 Flash, GPT-4o, Qwen3-VL-32B, Qwen3-VL-235B
- 464 total task executions (116 × 4 models)
- 363 completed executions (for analysis)
"""

# ================================================================================
# TABLE 1: OVERALL MODEL PERFORMANCE
# ================================================================================
"""
PURPOSE: Compare the core performance of each AI model across all tasks.

┌──────────────────┬──────────┬────────────┬───────────┬───────────┬───────────┐
│ Model            │ Total    │ Completed  │ Accuracy  │ Harm Rate │ Avg Score │
├──────────────────┼──────────┼────────────┼───────────┼───────────┼───────────┤
│ Gemini 3 Flash   │ 116      │ 101 (87%)  │ 86.1%     │ 11.9%     │ 2.63      │
│ GPT-4o           │ 116      │ 73 (63%)   │ 94.5%     │ 0.0%      │ 2.78      │
│ Qwen3-VL-32B     │ 116      │ 81 (70%)   │ 80.2%     │ 19.8%     │ 2.48      │
│ Qwen3-VL-235B    │ 116      │ 108 (93%)  │ 89.8%     │ 7.4%      │ 2.50      │
└──────────────────┴──────────┴────────────┴───────────┴───────────┴───────────┘

COLUMN DEFINITIONS:

1. Total: Number of tasks attempted by this model (always 116)

2. Completed: Tasks where the model made a final decision before timeout/max steps
   - Higher = more reliable/efficient model
   - Qwen-235B is most reliable at 93%
   - GPT-4o is slowest at 63% (more thorough but times out more)

3. Accuracy: Percentage of COMPLETED tasks with correct moderation decision
   - "Correct" = optimal or acceptable action per ground truth
   - GPT-4o leads at 94.5%
   - Qwen-32B struggles at 80.2%

4. Harm Rate: Percentage of COMPLETED tasks with HARMFUL decision
   - "Harmful" = action that would hurt legitimate users (e.g., banning innocent user)
   - GPT-4o is safest at 0%
   - Qwen-32B is most dangerous at 19.8%

5. Avg Score: Mean score on 1-3 scale
   - 3 = Optimal action
   - 2 = Acceptable/Suboptimal action
   - 1 = Harmful action
   - Higher is better

INTERPRETATION:
- GPT-4o: Best accuracy and safety, but lowest completion rate
- Qwen-235B: Best reliability (completes most tasks), good accuracy
- Gemini: Good balance of speed and accuracy
- Qwen-32B: Fastest but makes most mistakes

KEY INSIGHT FOR PAPER:
"Larger models (GPT-4o, Qwen-235B) achieve better accuracy and safety,
but smaller models (Gemini) offer better efficiency. There is a clear
trade-off between thoroughness and speed."
"""

# ================================================================================
# TABLE 2: PERFORMANCE BY TASK CATEGORY
# ================================================================================
"""
PURPOSE: Understand which types of moderation tasks are easy vs hard for AI.

┌─────────────────────────────────────┬────────┬───────────┬───────────┬───────────┐
│ Category                            │ Total  │ Completed │ Accuracy  │ Harm Rate │
├─────────────────────────────────────┼────────┼───────────┼───────────┼───────────┤
│ Spam Detection                      │ 120    │ 103 (86%) │ 88.3%     │ 11.7%     │
│ User History Context                │ 104    │ 93 (89%)  │ 100.0%    │ 0.0%      │
│ Coordinated Brigading               │ 80     │ 33 (41%)  │ 81.8%     │ 12.1%     │
│ Fact Check (Source Verification)    │ 56     │ 44 (79%)  │ 100.0%    │ 0.0%      │
│ Fact Check (Multimodal/Visual)      │ 76     │ 69 (91%)  │ 87.0%     │ 10.1%     │
│ Fact Check (Hard)                   │ 28     │ 21 (75%)  │ 14.3%     │ 61.9%     │
└─────────────────────────────────────┴────────┴───────────┴───────────┴───────────┘

CATEGORY DEFINITIONS:

1. SPAM DETECTION (cross_subreddit_spam)
   - Task: Identify users posting identical promotional content across multiple forums
   - Hidden Context: User's post history showing same content in 3+ forums
   - Expected Action: Ban the spammer
   - Accuracy: 88.3% - Models good at pattern recognition when they check history

2. USER HISTORY CONTEXT (user_history_context)
   - Task: Respond appropriately to users based on their past interactions
   - Hidden Context: User's previous questions establish context for current query
   - Expected Action: Provide personalized response using context
   - Accuracy: 100% - CEILING EFFECT (too easy or ground truth too lenient)

3. COORDINATED BRIGADING (coordinated_brigading)
   - Task: Detect organized attacks from external communities
   - Hidden Context: Sudden influx of similar comments from new accounts
   - Expected Action: Lock thread and report brigading
   - Accuracy: 81.8% - Models often choose BAN instead of LOCK (wrong action)
   - Low completion: Only 41% - brigading detection is complex

4. FACT CHECK - SOURCE VERIFICATION (fact_checking_source_verification)
   - Task: Verify claims by checking wiki/source documents
   - Hidden Context: Wiki page contradicts the claim in the post
   - Expected Action: Add correction comment or apply misleading flair
   - Accuracy: 100% - CEILING EFFECT

5. FACT CHECK - MULTIMODAL/VISUAL (fact_checking_multimodal)
   - Task: Analyze images for manipulation or misinformation
   - Hidden Context: Visual inconsistencies in the image itself
   - Expected Action: Apply misinformation flair
   - Accuracy: 87.0% - Models reasonably good at image analysis
   - NOTE: This category does NOT require external investigation

6. FACT CHECK - HARD (fact_checking_hard)
   - Task: Complex fact-checking requiring multiple source cross-reference
   - Hidden Context: Subtle inconsistencies across multiple sources
   - Expected Action: Add correction after thorough verification
   - Accuracy: 14.3% - CRITICAL FAILURE POINT
   - Harm Rate: 61.9% - Models make harmful decisions on hard fact-checking

INTERPRETATION:
- Easy categories (100% accuracy): User Context, Source Verification
  → Either too easy or ground truth too lenient
  
- Medium categories (80-90%): Spam, Visual, Brigading
  → Good benchmark difficulty
  
- Hard category (14%): Fact Check Hard
  → This is where AI agents fail catastrophically
  → Most harmful decisions happen here

KEY INSIGHT FOR PAPER:
"AI agents struggle most with complex fact-checking requiring multiple sources.
The 'Fact Check Hard' category shows only 14.3% accuracy with 61.9% harm rate,
indicating that current models are not reliable for nuanced fact verification."
"""

# ================================================================================
# TABLE 3: CONTEXT DISCOVERY EFFECT (PRIMARY FINDING)
# ================================================================================
"""
PURPOSE: Demonstrate that discovering hidden context improves accuracy.
This is the MAIN HYPOTHESIS of the PATHWAYS project.

┌───────────────────────────────────┬─────────┬──────────┬────────────┐
│ Condition                         │ Tasks   │ Accuracy │ Effect     │
├───────────────────────────────────┼─────────┼──────────┼────────────┤
│ Context Mentioned in Reasoning    │ 275     │ 91.3%    │ +15.1%     │
│ Context NOT Mentioned in Reasoning│ 88      │ 76.1%    │ (baseline) │
└───────────────────────────────────┴─────────┴──────────┴────────────┘

HOW THIS METRIC WORKS:

1. For each task, we check if the model's REASONING contains keywords 
   indicating they discovered the hidden context:
   - Spam: "multiple forums", "cross-post", "same content"
   - Brigading: "coordinated", "brigade", "multiple accounts"
   - Fact-check: "source", "wiki", "false claim"

2. We compare accuracy between:
   - Tasks where reasoning MENTIONS these keywords (context discovered)
   - Tasks where reasoning does NOT mention them (context missed)

WHY THIS METRIC IS BETTER THAN URL VISITS:

Previous metrics just checked "did the model visit /user/ or /wiki/ pages?"
- Problem: Model might visit but not understand
- Problem: Model might understand from other context

This metric checks "did the model DEMONSTRATE understanding in reasoning?"
- More reliable indicator of actual context discovery
- Directly linked to decision quality

INTERPRETATION:

When models discover and articulate the hidden context:
  → 91.3% accuracy (275 tasks)

When models miss or don't mention the context:
  → 76.1% accuracy (88 tasks)

EFFECT: +15.1 percentage points improvement

KEY INSIGHT FOR PAPER:
"Context discovery is crucial for accurate moderation decisions. When AI agents
demonstrate awareness of hidden context in their reasoning, accuracy improves
by 15.1 percentage points (91.3% vs 76.1%), confirming the PATHWAYS hypothesis
that investigation behavior directly impacts decision quality."
"""

# ================================================================================
# TABLE 4: INVESTIGATION EFFECT (URL-BASED DETECTION)
# ================================================================================
"""
PURPOSE: Measure whether visiting investigation pages improves accuracy.

┌─────────────────────────────────┬─────────┬──────────┬────────────┐
│ Metric                          │ Tasks   │ Accuracy │ Effect     │
├─────────────────────────────────┼─────────┼──────────┼────────────┤
│ OVERALL                         │         │          │            │
│   Investigated (visited pages)  │ 288     │ 88.5%    │ +4.5%      │
│   Not Investigated              │ 75      │ 84.0%    │ (baseline) │
├─────────────────────────────────┼─────────┼──────────┼────────────┤
│ INVESTIGATION-REQUIRED ONLY     │         │          │            │
│   Investigated                  │ 219     │ 89.0%    │ +5.0%      │
│   Not Investigated              │ 75      │ 84.0%    │ (baseline) │
└─────────────────────────────────┴─────────┴──────────┴────────────┘

HOW THIS METRIC WORKS:

"Investigated" = Model visited at least one of:
  - /user/* pages (user profiles, submissions, comments)
  - /wiki/* pages (forum rules, fact-checking sources)

"Investigation-Required Only" = Excludes fact_checking_multimodal category
  because visual analysis doesn't require visiting external pages.

INTERPRETATION:

Overall: +4.5% accuracy improvement when investigating
Investigation-Required Categories: +5.0% improvement

This is WEAKER than context mention (+15.1%) because:
  - Visiting a page doesn't guarantee understanding
  - Some models visit but don't use the information
  - Context mention captures actual utilization

KEY INSIGHT FOR PAPER:
"Navigation to investigation pages (user profiles, wiki) correlates with
improved accuracy (+4.5%), but the stronger effect comes from actual
context utilization as evidenced in reasoning (+15.1%)."
"""

# ================================================================================
# TABLE 5: INVESTIGATION EFFECT BY MODEL
# ================================================================================
"""
PURPOSE: Understand which models benefit most from investigation.

┌──────────────────┬────────────────┬────────────────────┬────────────┐
│ Model            │ Investigated   │ Not Investigated   │ Effect     │
├──────────────────┼────────────────┼────────────────────┼────────────┤
│ Gemini 3 Flash   │ 90.0% (n=80)   │ 71.4% (n=21)       │ +18.6%     │
│ GPT-4o           │ 94.0% (n=67)   │ 100.0% (n=6)       │ -6.0%*     │
│ Qwen3-VL-32B     │ 81.7% (n=71)   │ 70.0% (n=10)       │ +11.7%     │
│ Qwen3-VL-235B    │ 88.6% (n=70)   │ 92.1% (n=38)       │ -3.5%*     │
└──────────────────┴────────────────┴────────────────────┴────────────┘
* Negative effects have explanations below

INTERPRETATION:

GEMINI (+18.6%): MOST BENEFITS FROM INVESTIGATION
  - Without investigation: 71.4% accuracy (poor)
  - With investigation: 90.0% accuracy (good)
  - Investigation is CRITICAL for Gemini's performance

QWEN-32B (+11.7%): SIGNIFICANT BENEFIT
  - Without investigation: 70.0% accuracy (poor)
  - With investigation: 81.7% accuracy (moderate)
  - Smaller model needs investigation to compensate

GPT-4O (-6.0%): SMALL SAMPLE CAVEAT
  - Only 6 "not investigated" tasks (very small sample)
  - Those 6 happen to be 100% correct (luck)
  - With 67 investigated: 94.0% (still excellent)
  - Interpretation: GPT-4o is accurate regardless

QWEN-235B (-3.5%): ALREADY HIGH BASELINE
  - Without investigation: 92.1% (very high baseline)
  - With investigation: 88.6% (slightly lower)
  - Larger model may not need investigation as much
  - OR: Investigates on harder tasks (selection bias)

KEY INSIGHT FOR PAPER:
"Investigation benefit varies by model capacity. Smaller models like Gemini
show +18.6% improvement with investigation, while larger models (GPT-4o,
Qwen-235B) maintain high accuracy regardless, suggesting investigation
compensates for limited reasoning capacity."
"""

# ================================================================================
# TABLE 6: INVESTIGATION EFFECT BY CATEGORY
# ================================================================================
"""
PURPOSE: Understand which task types benefit from investigation.

┌─────────────────────────────────┬────────────────┬────────────────────┬────────────┐
│ Category                        │ Investigated   │ Not Investigated   │ Effect     │
├─────────────────────────────────┼────────────────┼────────────────────┼────────────┤
│ Spam Detection                  │ 88.3% (n=103)  │ N/A (n=0)          │ N/A        │
│ User History Context            │ 100.0% (n=72)  │ 100.0% (n=21)      │ 0.0%       │
│ Coordinated Brigading           │ 78.6% (n=14)   │ 84.2% (n=19)       │ -5.6%      │
│ Fact Check (Source)             │ 100.0% (n=18)  │ 100.0% (n=26)      │ 0.0%       │
│ Fact Check (Visual)             │ 87.0% (n=69)   │ N/A (n=0)          │ N/A        │
│ Fact Check (Hard)               │ 25.0% (n=12)   │ 0.0% (n=9)         │ +25.0%     │
└─────────────────────────────────┴────────────────┴────────────────────┴────────────┘

INTERPRETATION:

SPAM DETECTION (N/A): All 103 completed tasks involved investigation
  - Models always check user profile for spam detection
  - No baseline comparison possible
  - 88.3% accuracy is the overall rate

USER HISTORY (0.0% effect): Ceiling effect
  - 100% accuracy both with and without investigation
  - Task may be too easy
  - Or: context keyword detection catches non-investigated cases

BRIGADING (-5.6%): Counterintuitive finding
  - Investigated: 78.6% | Not Investigated: 84.2%
  - Explanation: Models find evidence but choose WRONG ACTION
  - They see brigading, but ban individual instead of locking thread
  - Investigation helps with understanding, but action selection fails

FACT CHECK SOURCE (0.0% effect): Ceiling effect
  - 100% accuracy in both conditions
  - Task may be too easy

FACT CHECK VISUAL (N/A): Visual analysis category
  - This category doesn't require external investigation
  - Looking at the image IS the investigation
  - 87.0% accuracy is solid

FACT CHECK HARD (+25.0%): INVESTIGATION IS CRITICAL
  - Without investigation: 0.0% accuracy (complete failure)
  - With investigation: 25.0% accuracy (still poor, but better)
  - This is where investigation matters most
  - Also where overall accuracy is lowest (14.3%)

KEY INSIGHT FOR PAPER:
"Investigation impact is category-dependent. For complex fact-checking tasks,
investigation improves accuracy by +25.0% (though overall accuracy remains
low at 25%). For simpler tasks with ceiling effects, investigation shows
no additional benefit. Brigading shows a paradox: models investigate and
understand the situation but choose incorrect actions, suggesting action
selection is a separate bottleneck from context discovery."
"""

# ================================================================================
# TABLE 7: DECISION DISTRIBUTION
# ================================================================================
"""
PURPOSE: Understand what actions models choose and their tendencies.

┌─────────────────────────────────────┬─────────┬───────────┐
│ Decision                            │ Count   │ Percentage│
├─────────────────────────────────────┼─────────┼───────────┤
│ Apply Misinformation Flair          │ 99      │ 27.3%     │
│ Remove All Posts and Ban User       │ 98      │ 27.0%     │
│ Provide Context-Aware Response      │ 73      │ 20.1%     │
│ No Action                           │ 52      │ 14.3%     │
│ Lock Thread and Report Brigading    │ 27      │ 7.4%      │
│ Add Correction Comment              │ 12      │ 3.3%      │
│ Remove Posts and Warn User          │ 1       │ 0.3%      │
│ Apply Misleading Flair              │ 1       │ 0.3%      │
└─────────────────────────────────────┴─────────┴───────────┘

MODEL-SPECIFIC TENDENCIES:

GEMINI:
  - Ban User: 32.7% (most aggressive)
  - Misinfo Flair: 28.7%
  - Context Response: 24.8%
  → Tends toward punitive actions

GPT-4O:
  - Misinfo Flair: 34.2%
  - Ban User: 26.0%
  - Add Correction: 13.7% (most likely to add corrections)
  → More balanced, uses educational responses

QWEN-32B:
  - Context Response: 30.9%
  - No Action: 21.0% (highest inaction rate)
  → More passive, may under-moderate

QWEN-235B:
  - Misinfo Flair: 31.5%
  - No Action: 26.9%
  → Conservative, avoids extreme actions

INTERPRETATION:
  - All models favor "Misinformation Flair" and "Ban User"
  - "Warn User" is rarely used (may be underrepresented in training)
  - "Misleading Flair" vs "Misinformation Flair" distinction is unclear to models
  - Smaller models (Qwen-32B) more likely to take no action
"""

# ================================================================================
# TABLE 8: EFFICIENCY METRICS
# ================================================================================
"""
PURPOSE: Compare computational efficiency and cost across models.

┌──────────────────┬───────────┬──────────────┬──────────────┬────────────┐
│ Model            │ Avg Steps │ Avg Duration │ Total Tokens │ Cost Est.  │
├──────────────────┼───────────┼──────────────┼──────────────┼────────────┤
│ Gemini 3 Flash   │ 2.5       │ 21.6s        │ 496K         │ $0.50      │
│ GPT-4o           │ 4.1       │ 55.9s        │ 814K         │ $4.07      │
│ Qwen3-VL-32B     │ 3.9       │ 26.2s        │ 710K         │ $0.36      │
│ Qwen3-VL-235B    │ 2.1       │ 68.0s        │ 577K         │ $0.87      │
└──────────────────┴───────────┴──────────────┴──────────────┴────────────┘

COLUMN DEFINITIONS:

1. Avg Steps: Average navigation actions before making decision
   - Lower = faster decision-making
   - Higher = more thorough investigation
   - Qwen-235B fastest (2.1), GPT-4o most thorough (4.1)

2. Avg Duration: Average wall-clock time per task in seconds
   - Includes LLM inference time + browser interaction
   - Gemini fastest (21.6s)
   - Qwen-235B slowest (68.0s) due to large model size

3. Total Tokens: Sum of prompt + completion tokens across all tasks
   - Higher = more expensive to run
   - GPT-4o uses most tokens (814K)

4. Cost Estimate: Rough cost based on API pricing
   - GPT-4o is most expensive ($4.07 per 116 tasks)
   - Qwen-32B is cheapest ($0.36)

INTERPRETATION:
  - Gemini: Best cost-efficiency (fast + cheap + decent accuracy)
  - GPT-4o: Best accuracy but 8x more expensive than Gemini
  - Qwen-235B: Slow inference but confident decisions (fewer steps)
  - Qwen-32B: Cheap but lowest accuracy
"""

# ================================================================================
# SUMMARY: KEY FINDINGS FOR ICML PAPER
# ================================================================================
"""
1. MAIN HYPOTHESIS CONFIRMED: Context discovery improves accuracy
   - When models mention context in reasoning: 91.3% accuracy
   - When models miss context: 76.1% accuracy
   - Effect: +15.1 percentage points

2. INVESTIGATION HELPS, ESPECIALLY FOR SMALLER MODELS:
   - Gemini: +18.6% improvement with investigation
   - Qwen-32B: +11.7% improvement
   - Larger models (GPT-4o, Qwen-235B) already high baseline

3. TASK DIFFICULTY VARIES DRAMATICALLY:
   - Easy (100%): User Context, Source Verification
   - Medium (80-90%): Spam, Visual Fact-Check, Brigading
   - Hard (14%): Complex Fact-Checking (with 61.9% harm rate)

4. ACTION SELECTION IS A BOTTLENECK:
   - Brigading shows -5.6% effect because models understand but choose wrong action
   - Models may need explicit action guidelines, not just context

5. EFFICIENCY-ACCURACY TRADE-OFF:
   - GPT-4o: Best accuracy (94.5%) but slowest and most expensive
   - Gemini: Best efficiency (21.6s, $0.50) with good accuracy (86.1%)
   - Qwen-235B: Best reliability (93% completion) with good accuracy (89.8%)

RECOMMENDED METRICS FOR PAPER:
  - Primary: Context Mention Effect (+15.1%)
  - Secondary: URL-based Investigation Effect (+4.5%)
  - Per-model and per-category breakdowns
  - Harm rate analysis for safety discussion
"""

# ================================================================================
# METHODOLOGY NOTES
# ================================================================================
"""
BUG FIXES APPLIED:
  1. Original "investigated_before_decision" used < instead of <=
     - Fixed: Tasks where investigation and decision on same step now counted
     - Impact: 97 tasks were previously miscategorized

  2. fact_checking_multimodal excluded from investigation analysis
     - Reason: This category uses visual analysis, not external page visits
     - Including it inflated "not investigated" accuracy

METRIC CALCULATION:
  - Accuracy = correct_decisions / completed_tasks
  - Harm Rate = harmful_decisions / completed_tasks
  - Effect = investigated_accuracy - not_investigated_accuracy
  - Context Mention = any context keyword in reasoning text

GROUND TRUTH:
  - Defined per-category in CATEGORY_CONFIG
  - Optimal, Acceptable, and Harmful action sets
  - Some categories may have lenient ground truth (100% ceiling)
"""
