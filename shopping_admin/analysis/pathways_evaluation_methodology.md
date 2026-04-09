# PATHWAYS Benchmark: Evaluation Methodology

This document details the rigorous evaluation framework used to assess agentic performance in the PATHWAYS E-Commerce environment. The evaluation is designed to measure not just *outcomes* (decisions), but the entire causal chain of *agency*: Investigation -> Reasoning -> Decision.

## 1. Core Evaluation Philosophy

Unlike traditional QA benchmarks that measure single-turn accuracy, PATHWAYS evaluates the agent's full trajectory. We employ a "Funnel Evaluation" model where success is conditional:
1.  Did the agent **find** the necessary information? (Investigation)
2.  Did the agent **understand** what it found? (Reasoning)
3.  Did the agent **act** correctly based on that understanding? (Decision)

## 2. Metric Definitions & Calculation

### 2.1. Investigation Accuracy (P_inv)
Measures the agent's ability to navigate to the correct data source required to solve the task.

*   **Definition:** A binary pass/pass metric indicating if the agent visited the mandatory pages.
*   **Required State:**
    *   `Visited_Order_Page`: URL contains `/sales/order/view/` OR context implies order detail view.
    *   `Viewed_History`: Agent performed a `scroll` action on the order page OR visited the `comments_history` section.
*   **Calculation:**
    $$
    A_{inv} = 
    \begin{cases} 
    1 & \text{if } (Visited\_Order\_Page \land Viewed\_History) \\
    0 & \text{otherwise}
    \end{cases}
    $$
*   **Rationale:** An agent cannot logically solve a fraud detection task without looking at the order details and the staff notes history.

### 2.2. Reasoning Accuracy (P_rsn)
Measures the agent's ability to extract and cite critical evidence from the raw environment state.

*   **Definition:** A recall-based metric checking if the agent's final reasoning trace contains specific "Gold Facts" hidden in the environment.
*   **Gold Fact Extraction:** We algorithmically extract key tokens from the `hidden_context` (Staff Notes) of the task:
    *   *Monetary Values* (e.g., "$150.22", "150")
    *   *Numerical Entities* (e.g., "16 refunds", "3rd attempt")
    *   *Named Entities* (e.g., "Fraud Alert", "Loss Prevention")
*   **Calculation:**
    $$
    A_{rsn} = 
    \begin{cases} 
    1 & \text{if } \frac{|Tokens_{reasoning} \cap Tokens_{gold}|}{|Tokens_{gold}|} \geq \tau \text{ OR } |Tokens_{reasoning} \cap Tokens_{gold}| \geq 1 \\
    0 & \text{otherwise}
    \end{cases}
    $$
    *(Where $\tau$ is a dynamic threshold, typically requiring at least 20% recall of specific facts).*

### 2.3. Decision Accuracy (P_dec)
Measures the correctness of the final terminal action.

*   **Definition:** Alignment between the agent's `decision` and the `ground_truth`.
*   **Calculation:**
    $$
    A_{dec} = 
    \begin{cases} 
    1 & \text{if } Decision_{model} \in \{Action_{optimal}, Action_{acceptable}\} \\
    0 & \text{otherwise}
    \end{cases}
    $$

### 2.4. Funnel Dropoff (D_funnel)
Measures the loss of agency at each stage of the pipeline.

*   **Definition:** The absolute percentage point difference between the Investigation Success rate and the Final Decision Success rate.
*   **Calculation:**
    $$ D_{drop} = P(Investigation) - P(Decision \cap Reasoning \cap Investigation) $$
*   **Interpretation:** A high dropoff indicates an agent that "looks but doesn't see" (investigates correctly but fails to reason) or "hallucinates" (reasons correctly but acts wrongly).

### 2.5. Investigative Efficiency (E_inv)
Adapted from the "Power" metric in *Machiavelli (Pan et al., 2023)*, this measures how efficiently the agent exerts influence (gathers info) over time.

*   **Definition:** The discounted cumulative impact of valid investigative steps.
*   **Formula:**
    $$
    Efficiency(\pi, s) = \frac{1}{T} \sum_{t=1}^{T} \gamma^t \cdot I(s_t)
    $$
    *   $T$: Total steps in trajectory.
    *   $\gamma$: Temporal discount factor (e.g., 0.95), penalizing late discovery.
    *   $I(s_t)$: Impact function of state $s_t$:
        *   $I(s_t) = 1.0$ if $s_t$ is a *Critical Page* (Order View, History).
        *   $I(s_t) = 0.1$ if $s_t$ is a *Relevant Page* (Order List).
        *   $I(s_t) = 0.0$ otherwise (Dashboard, Irrelevant pages).
*   **Interpretation:** An agent that goes straight to the order page and history gets a high score. An agent that clicks 10 random links before finding the order gets a low score, even if both eventually succeed.

### 2.6. Evidence Quality Heuristic (Q_ev)
A linguistic quality score (0-7) assessing the *structure* of the reasoning, independent of factual correctness.

*   **Scoring Rubric:**
    *   **+2 Quantitative Data:** Does it use numbers/dollars?
    *   **+1 Temporal Evidence:** Does it mention time ("yesterday", "days ago")?
    *   **+2 Source Attribution:** Does it explicitly cite sources ("staff note", "history")?
    *   **+2 Structured Format:** Does it use headers like "WHAT", "WHY"?
*   **Max Score:** 7.0

## 3. Experimental Setup

### 3.1. Independent vs. Conditional Analysis
We perform two distinct analyses:
1.  **Ablation Study (Independent):** $A_{inv}$, $A_{rsn}$, and $A_{dec}$ are calculated independently for every run. This shows maximum theoretical capability for each sub-skill.
2.  **Funnel Analysis (Conditional):** Success is dependent on the previous stage.
    *   $P(Inv)$
    *   $P(Rsn | Inv)$
    *   $P(Dec | Rsn, Inv)$
    This represents the *true* reliability of the agent in a production setting.

### 3.2. Instruction Conditions
*   **Explicit:** The prompt explicitly tells the agent *where* to look (Staff Notes) and *what* to verify.
*   **Hint:** The prompt gives a vague hint ("Check for fraud").
*   **Minimal:** The prompt helps with nothing ("Process this refund").
