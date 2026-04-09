# PATHWAYS 2.0: A NeurIPS-Level Benchmark for Multi-Hop Investigative Web Agents

## 1. Executive Summary & Critical Analysis
The original PATHWAYS benchmark effectively highlighted the "Navigation-Discovery Gap" and "Investigative Hallucination." However, an analysis of the task structure (e.g., `generate_pathways_sql.py`) reveals a critical limitation for a premier venue like NeurIPS: **the environment spoon-feeds the synthesis to the agent.** 

Currently, agents are tested on finding a single "hidden context"—typically a supervisor's comment in the order history (e.g., *"FRAUD ALERT: Customer has 12 refunds"*). This makes the task a **2-hop retrieval problem** (Order $\rightarrow$ Order Comments), not a true test of contextual deductive reasoning.

**The Redesign Goal:** PATHWAYS 2.0 will mandate *True Investigation*. We will eliminate pre-written supervisor comments. Instead, the agent must autonomously transverse multiple URLs, extract raw, disparate data (e.g., timestamps, IP addresses, shipping destinations), and synthesize this data into an investigative conclusion. 

---

## 2. Redesigning "True Investigation" (The "No Spoon-Feeding" Rule)

To achieve NeurIPS-level rigor, we will expand across three primary WebArena domains, requiring $N$-hop reasoning graphs.

### A. Shopping Admin (E-Commerce Forensics)
We will transition from "reading comments" to "behavioral forensic analysis" requiring 4–8 hops.
*   **The Reshipping Fraud Ring:**
    *   *Trigger:* A standard refund request for an $80 item.
    *   *The Investigation Trail:* 
        1. Agent views order (Hop 1). 
        2. Agent views Customer Profile (Hop 2). 
        3. Agent sees 8 recent orders and must open each (Hops 3-10). 
        4. Agent discovers that while the billing address is identical, each order ships to a different state. 
        5. Agent checks tracking links (Hops 11-18) to verify all were delivered.
    *   *Synthesis:* The agent must independently deduce this is a reshipping fraud network and deny the refund, rather than reading a comment telling them to do so.
*   **The "False Flag" Sizing Issue:**
    *   *Trigger:* Agent is tasked with reviewing an account with an automated "40% Return Rate" flag.
    *   *The Investigation Trail:* Agent cross-references the returned items with subsequent purchases to discover the user consistently returns a "Size M" and immediately purchases a "Size L" of the exact same SKU. 
    *   *Synthesis:* The agent recognizes a legitimate sizing struggle, overriding the strict algorithmic flag to approve the account.

### B. Reddit Moderation (Postmill - Sociological Investigation)
*   **The "Long-Con" Sockpuppet:**
    *   *Trigger:* A user posts a highly plausible but controversial news link. 
    *   *The Investigation Trail:* The agent must paginate through the user's history deeply (Hops 1-3). The agent notices that 6 months ago, the account exclusively posted in a foreign language on a specific geographic subreddit, then went dormant, and suddenly woke up posting flawless English political content.
    *   *Synthesis:* Detection of a purchased/compromised account for disinformation.
*   **Cross-Domain Fact Checking (Reddit + Wikipedia):**
    *   *Trigger:* A user in `r/AskDocs` asks for donations, claiming to be a specialist at a specific hospital.
    *   *The Investigation Trail:* The agent must navigate *out* of Reddit to the WebArena Wikipedia instance. The agent searches the hospital/specialist, cross-references demographic data or faculty lists, and realizes the claims mathematically contradict the user's Reddit history (where they previously stated they were a 22-year-old student).

### C. GitLab (Cybersecurity & Supply Chain)
*   **The Trojan Horse PR:**
    *   *Trigger:* A seemingly benign merge request fixing a README typo.
    *   *The Investigation Trail:* The agent must review the full file diffs, noticing an unexpected bump in a `package.json` dependency. The agent navigates to the dependency registry or the specific user's commit history across *other* repositories, discovering a pattern of injecting untrusted forks.

---

## 3. Docker Environment & Injection Mechanisms

The current architecture mounts customized `.tar` database snapshots for standard environments (Magento, Postmill, GitLab).

**The Upgraded Injection Pipeline:**
1.  **Procedural Behavioral Generators:** We will completely rewrite `generate_pathways_sql.py`. Instead of injecting strings into `sales_order_status_history`, the Python scripts will act as "Time-Series Data Simulators." They will procedurally generate mathematically sound tables of `sales_order`, `sales_shipment`, `customer_grid_flat`, and `customer_address_entity`. 
2.  **Cross-Entity Linking:** For Reddit, our Python bootstrappers will generate interconnected `users`, `posts`, and `comments` tables. We will inject precise temporal spacing (e.g., `created_at`) to simulate dormancy periods for sockpuppet accounts.
3.  **Snapshotting:** Once the massively populated, complex SQL scripts are generated, they will be loaded into the WebArena Docker initialization scripts just once, creating static, highly reproducible `.tar` volume snapshots for rapid evaluation.

---

## 4. Advanced Evaluation Metrics

To prove these tasks are harder and more meaningful, PATHWAYS 2.0 requires advanced metrics in `analyze_results.py`:

*   **Evidence Graph Traversal Score (EGTS):** 
    *   Each task has a defined *Directed Acyclic Graph (DAG)* of required evidence. We evaluate the agent's web trajectory log. Did the agent visit *all* required URLs to form a complete logical deduction? Partial credit is given for incomplete investigations.
*   **Synthesis Accuracy vs. Retrieval Accuracy:** 
    *   We isolate failures: Did the agent fail because it couldn't *find* the 5 tracking URLs (Retrieval Failure)? Or did it find all 5 URLs but still *fail to realize* they indicated a fraud ring (Synthesis Failure)?
*   **Strict Epistemic Calibration:**
    *   To ruthlessly penalize "Investigative Hallucination," the agent's final reasoning prompt will require citations (e.g., "I verified this on URL X"). If the agent cites a URL that does not appear in its action trajectory, it receives an automatic Path Failure and an Epistemic Penalty.

---

## 5. Implementation Roadmap for NeurIPS

*   **Phase 1: Task Taxonomy Design (Weeks 1-2)**
    *   Design 50 core "Behavioral Archetypes" (15 E-commerce, 15 Reddit, 10 GitLab, 10 Cross-Domain) focusing entirely on multi-hop data synthesis.
*   **Phase 2: The Data Simulator (Weeks 2-4)**
    *   Develop the procedural Python data generators to construct the thousands of database rows required to support the 50 archetypes without using explicit comments.
*   **Phase 3: Docker & Integration (Week 5)**
    *   Compile the SQL dumps, instantiate the Docker containers, and capture the new baseline snapshots (`pathways_v4_ecommerce.tar`, etc.).
*   **Phase 4: Trajectory Evaluator Engine (Week 6)**
    *   Refactor `run_pathways.py` and `analyze_benchmark.py` to parse LangGraph logs and calculate the new EGTS and Epistemic Calibration metrics.
*   **Phase 5: Baseline Benchmarking (Weeks 7-8)**
    *   Run GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Pro to empirically prove our hypothesis: current SOTA models completely collapse when forced to synthesize unspoken patterns across $>3$ hops.
