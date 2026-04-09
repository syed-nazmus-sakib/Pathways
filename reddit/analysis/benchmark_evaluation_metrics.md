# Evaluation Framework for Autonomous Content Moderation Agents

This document outlines the comprehensive evaluation framework used to assess Large Language Model (LLM) agents on the Reddit Moderation Benchmark. The framework is designed to measure not just potential outcomes, but the integrity of the investigative process and the efficiency of agent actions.

## 1. Component Capabilities (Independent Metrics)
These metrics evaluate specific sub-skills required for the task in isolation. They answer the question: *"Regardless of the final outcome, how well did the agent perform this specific part of the workflow?"*

### A. Investigation Accuracy ($Acc_{Inv}$)
**Definition:** Measures the agent's ability to identify and retrieve necessary evidence sources (e.g., specific Wiki pages, User History profiles, or Comment threads) defined in the Ground Truth.
**Calculation:**
$$Acc_{Inv} = \frac{\mathbb{I}(\text{Critical URL Visited})}{\text{Total Tasks}}$$
*   **1.0 (Success):** The agent visited the "Must Visit" URL defined in the task (e.g., the specific wiki page contradicting the post).
*   **0.0 (Failure):** The agent failed to navigate to the source of truth, relying solely on surface knowledge or hallucination.

### B. Reasoning Alignment ($Acc_{Res}$)
**Definition:** Measures the extent to which the agent's internal monologue or provided justification aligns with the factual reality derived from the investigation.
**Calculation:**
A keyword recall metric based on critical facts ($F$) present in the Ground Truth ($GT$).
$$Acc_{Res} = \frac{| \{f \in F_{GT} \mid f \in \text{Reasoning}_{Agent}\} |}{|F_{GT}|}$$
*   **Logic:** If the ground truth reasoning involves "User has 3 prior bans", the agent must explicitly mention "3 prior bans" or equivalent semantic markers in its output.

### C. Decision Correctness ($Acc_{Dec}$)
**Definition:** Measures the accuracy of the final moderation action taken by the agent compared to the optimal ground truth action.
**Calculation:**
Weighted scoring allowing for semantic equivalents and "safe" failures.
$$Score(a_{model}, a_{opt}) = \begin{cases} 
1.0 & \text{if } a_{model} = a_{opt} \\
0.8 & \text{if } a_{model} \in \text{AcceptableAlternatives}(a_{opt}) \\
0.5 & \text{if } \text{Category}(a_{model}) = \text{Category}(a_{opt}) \text{ (e.g. both are Interventions)} \\
0.0 & \text{otherwise}
\end{cases}$$
*   **Note:** This metric is independent of investigation; an agent can guess the correct decision without evidence, which is why it is distinct from the Process Integrity metric below.

---

## 2. Process Integrity (Funnel Evaluation)
This metric enforces a strict dependency chain, penalizing agents that arrive at the correct decision through flawed processes (e.g., guessing or hallucinating).

### A. Proven Success Rate ($P_{Success}$)
**Definition:** The probability of a task being completed successfully where every preceding step was also valid. It models the conditional probability of success.
**Calculation:**
$$P_{Success} = Acc_{Inv} \times Acc_{Res} \times Acc_{Dec}$$
*   **Interpretation:** A score is only non-zero if the agent **Investigated** correct links AND **Reasoned** regarding the facts found AND **Decided** correctly.
*   **Purpose:** This serves as the primary rigorous benchmark score, filtering out "lucky guesses."

---

## 3. Investigative Efficiency (Machiavelli Metric)
Adapted from the "Power" metric in *Machiavelli* (Pan et al., 2023), this metric gives higher scores to agents that find evidence quickly and efficiently, penalizing meandering or aimless browsing.

### A. Investigative Efficiency ($E_{Inv}$)
**Definition:** The discounted cumulative impact of an agent's actions over its trajectory. An agent is more "efficient" if it navigates to high-value information states (Critical URLs) earlier in the trajectory.
**Calculation:**
$$E_{Inv}(\tau) = \sum_{t=1}^{T} \gamma^{t-1} \cdot V(s_t)$$
Where:
*   $\tau$ is the agent's trajectory of states $(s_1, s_2, ..., s_T)$.
*   $\gamma \in (0, 1]$ is the temporal discount factor (set to $\gamma = 0.9$), penalizing late discovery.
*   $V(s_t)$ is the Information Value of the state at step $t$:
    *   $V(s_t) = 1.0$ if $s_t$ corresponds to a **Critical Evidence URL** (e.g., the Wiki Page).
    *   $V(s_t) = 0.0$ for all other non-critical pages.
*   **Normalization:** The score is capped or normalized such that finding evidence at $t=1$ yields a score of 1.0.

**Logic:**
*   **Agent A** clicks the Wiki Link immediately (Step 1). Score $= 1.0$.
*   **Agent B** browses random subreddits for 5 steps, then clicks the Wiki Link (Step 6). Score $= 0.9^5 \approx 0.59$.
*   **Insight:** This distinguishes between agents that *know* where to look (high efficiency) and agents that *stumble* upon evidence (low efficiency).
