# PATHWAYS v3 — Shopping Admin Domain: Design, Rationale, and Task Taxonomy

**Benchmark:** PATHWAYS (Probing Agent Trajectories, Heuristics, and Reasoning Without Analytic Yield Statements)  
**Domain:** E-Commerce Administration (Magento / OneStopShop)  
**Version:** 3.0  
**Total Tasks:** 150  
**Status:** Fully injected and verified (150/150 pass)

---

## 1. Motivation and Core Design Principle

### 1.1 The Problem with Existing Benchmarks

Existing web agent benchmarks largely evaluate *task completion* in the sense of navigating to a goal state and executing an action. WebArena [1] demonstrated that GPT-4-based agents achieve only 14.4% success on realistic web tasks versus 78.2% for humans — a compelling capability gap. However, most tasks in WebArena and related benchmarks (Mind2Web [2], WebShop [3]) have a critical structural property: **the information needed to complete the task is either directly visible on the starting page or reachable within 1-2 navigations**.

The original PATHWAYS v1/v2 benchmark [4] attempted to address this by introducing *hidden context* — placing decisive information in a location the agent would have to find. However, an analysis of the v1/v2 design reveals a fundamental limitation: the hidden context was injected as a **pre-written analytical text comment** in the Magento `sales_order_status_history` table:

```
"FRAUD ALERT: Customer has 9 refunds in 59 days. ALL claims are 
'item not received' but tracking confirms delivery. Total refunded: 
$1,667.77. Refund rate: 93%. DO NOT PROCESS — Escalate to Loss 
Prevention immediately."
```

This reduces what should be an *investigation* task to a **2-hop retrieval task**: navigate to the order → find and read the pre-written verdict. The agent is not synthesizing evidence; it is reading a human-written conclusion. Consequently, the evaluation metric `P_inv` in v1/v2 — which checked merely whether the agent visited the order page and scrolled to comments — was measuring navigation behavior, not investigative reasoning.

This limitation directly undermines the paper's central claim: that agents fail at *investigation and context discovery*. If the task does not require investigation (only retrieval of a pre-written note), then evidence of failure at that task is not evidence of failure at investigation.

### 1.2 The PATHWAYS v3 Design Principle: Behavioral Forensics

PATHWAYS v3 eliminates all pre-written analytical comments. **Zero `FRAUD ALERT` strings. Zero pre-synthesized conclusions. No supervisor notes.** Instead, the hidden context is encoded entirely in raw behavioral data — order records, shipping addresses, SKU sequences, payment methods, timestamps — distributed across multiple database entities, each accessible only by navigating to a distinct URL.

The agent must:
1. Navigate to multiple specific pages (6–15 hops depending on task)
2. Observe raw, uninterpreted data on each page
3. Mentally (or explicitly) cross-reference the observations
4. Synthesize the pattern independently
5. Reach the correct decision

This design is grounded in the distinction drawn by Huang et al. [5] between *retrieval-augmented generation* (finding and reading a text answer) and *compositional reasoning* (assembling multiple observations into a conclusion that is not stated anywhere). PATHWAYS v3 exclusively evaluates the latter.

---

## 2. Environment: Magento Shopping Admin

### 2.1 Platform

The Shopping Admin domain uses a **Magento 2 e-commerce back-office** (OneStopShop), the same environment used in WebArena [1]. The agent operates as an authorized store administrator with access to:

- **Sales → Orders**: Individual order detail pages showing order items, billing/shipping addresses, order status, payment method, and status history
- **Sales → Customers**: Customer profile pages showing account information, order count, lifetime value, default addresses
- **Sales → Order Grid**: Filterable list of all orders, searchable by customer email, status, date range
- **Catalog**: Product listing pages with SKU, pricing, and inventory data
- **Sales → Credit Memos**: Refund records associated with specific orders

The environment runs in a Docker container at `http://localhost:7780` and is accessed via Playwright-based browser automation, identical to the WebArena evaluation harness.

### 2.2 Why E-Commerce Administration?

E-commerce fraud adjudication is a canonical *investigative decision-making* task in the real world. A fraud analyst reviewing a refund request must:
- Understand what the customer is claiming
- Retrieve the customer's transaction history
- Cross-reference behavioral signals (shipping patterns, return patterns, account age)
- Apply domain knowledge to synthesize a judgment

This maps directly onto the multi-hop web investigation capability that PATHWAYS aims to evaluate. The Magento admin interface provides a naturalistic, realistic environment where the investigation path is *implicit* — the agent must decide which pages to visit, what to look for, and how the pieces connect — unlike synthetic environments where navigation paths are pre-specified.

The choice also directly contrasts with the consumer-facing shopping interface (used in WebShop [3] and WebArena's shopping domain), which presents simpler product-search tasks. The *administrative* interface is richer in investigative depth because it exposes behavioral history not visible to end users.

---

## 3. Task Generation Architecture

### 3.1 SQL Injection Approach

Each task instance is created by injecting a synthetic behavioral dataset into the live Magento PostgreSQL/MySQL database. The injection pipeline consists of:

1. **`generate_behavioral_patterns.py`** — a Python generator that produces:
   - `customer_entity` records (unique customers with realistic names/emails)
   - `sales_order` records (with correct state/status fields)
   - `sales_order_address` records (billing + shipping for every order)
   - `sales_order_payment` records
   - `sales_order_item` records (with real Magento SKUs from the catalog)
   - `sales_creditmemo` records (for return patterns)
   - `sales_order_status_history` records — **operational notes only** (e.g., "Picking error — wrong SKU dispatched"), never analytical conclusions

2. **ID space management**: All injected entities use IDs ≥ 200,000, far above the existing data ceiling (max customer_id: 70, max order_id: 308), ensuring zero collisions.

3. **Reproducibility**: A fixed random seed (`--seed 2026`) produces identical task sets across re-runs, enabling reproducible evaluation.

### 3.2 Investigation Graph Schema

Every task includes a formal `investigation_graph` object:

```json
{
  "start_node": "N1",
  "required_nodes": [
    {
      "node_id": "N1",
      "label": "View target order",
      "url_pattern": "http://localhost:7780/admin/sales/order/view/order_id/200008/",
      "extract": ["customer_email", "billing_city", "shipping_city", "grand_total"]
    },
    ...
  ],
  "hop_count": 10,
  "synthesis_required": "Compare shipping addresses across all prior orders..."
}
```

This DAG structure enables the **Evidence DAG Completion Score (EDCS)** metric: the fraction of required investigation nodes the agent actually visits. It also formally defines what "complete investigation" means for each task, making evaluation unambiguous.

---

## 4. Task Categories

### 4.1 Reshipping Fraud Ring
**Count:** 30 tasks | **Difficulty:** Hard | **Hops:** 10

**Behavioral Pattern:**  
A single customer account accumulates 7 prior orders. Each order has an identical billing address but a *different* shipping address in a different US state. All 7 prior orders are in `closed` status (refund previously granted). All listed the same claim type ("not received"). The 8th order (the target) follows the same pattern.

**Why it's hard:**  
The fraud signal is *distributed* — no single order reveals the pattern. The agent must open all 7 prior orders, observe the shipping address on each, and independently recognize that (a) billing is constant, (b) shipping is systematically diversified, and (c) all prior refunds were granted. A reshipping fraud ring operates by recruiting "mules" at different addresses to receive packages and forward them; the constant billing address is the fraudster's own payment identity while the diverse shipping addresses represent the mule network.

**Investigation path:**  
`Target Order → Customer Profile → Order History List → Prior Order 1 ... Prior Order 7`

**Ground truth:** `ESCALATE`  
**Adversarial surface:** The claim ("Package was never delivered") is plausible in isolation. Only the cross-order address pattern reveals the fraud.

**Cited literature:** Reshipping fraud is documented as a major e-commerce fraud vector by the FBI Internet Crime Report [6] and is discussed in fraud detection literature [7]. The multi-account/multi-address pattern is a well-known signal used by commercial fraud platforms (Signifyd, Kount).

---

### 4.2 Wardrobing / Size-Exchange Detection
**Count:** 30 tasks | **Difficulty:** Medium-Hard | **Hops:** 15

**Behavioral Pattern:**  
A customer with a ~50% return rate has a history of purchasing Size M of a product, returning it with reason "wrong size", then immediately purchasing Size L of the *exact same SKU* and keeping it. This pair (M-return + L-keep) repeats across 6 different product categories over several months.

**Why it's hard:**  
This is a *defend the legitimate customer* task. The surface signal (high return rate = fraud flag) points toward denial, but the underlying behavioral pattern reveals a legitimate sizing behavior. The agent must:
1. Navigate to the customer profile and see the flag
2. Open each of the 12 prior orders (6 return orders + 6 keep orders)
3. Observe the SKU patterns: `WS08-M-Blue` (closed/refunded) followed by `WS08-L-Blue` (complete/kept)
4. Recognize the base SKU identity (same product, different size)
5. Override the algorithmic flag and approve

The 15-hop requirement (12 prior orders + 3 overhead nodes) makes this the highest-hop task in the benchmark.

**Ground truth:** `APPROVE`  
**Adversarial surface:** The automated 50% return rate flag, displayed prominently in the customer profile, is deliberately designed to push the agent toward denial.

**Cited literature:** "Wardrobing" (purchasing items for temporary use then returning) is a well-documented retail fraud pattern [8]. However, size-exchange returns are explicitly *legitimate* and distinguishable from wardrobing by the consistent size-upgrade pattern across product categories [9].

---

### 4.3 Account Takeover
**Count:** 30 tasks | **Difficulty:** Hard | **Hops:** 7

**Behavioral Pattern:**  
A customer account has 15 historical orders spanning ~2 years, all shipped to the same city (the "home" city matching the billing address). Then, within the last 24 hours:
- A new credit card was added to the account
- A high-value order ($400–$900) was placed using that new card
- The order ships to a different US state

**Why it's hard:**  
The account takeover signal requires *temporal cross-referencing*: the agent must notice not just the geographic anomaly (different shipping city) but also that the new payment method was added immediately before the anomalous order. Each of these facts lives on a different page — the order page shows the shipping city, the customer profile shows the stored payment methods and their creation dates, and the order history list shows the geographic consistency of prior orders.

**Investigation path:**  
`High-Value Order → Customer Profile → Order History (3 samples) → Payment Methods Section`

**Ground truth:** `ESCALATE`  
**Adversarial surface:** The customer is known (not a guest, has a long history), which can falsely suggest legitimacy.

**Cited literature:** Account takeover (ATO) is among the top fraud categories in e-commerce [10]. The combination of new payment method + new shipping geography is a canonical ATO signal documented in fraud intelligence literature [7, 11].

---

### 4.4 Legitimate Customer Defense (Warehouse Error)
**Count:** 30 tasks | **Difficulty:** Medium | **Hops:** 7

**Behavioral Pattern:**  
A customer has a ~50% return rate, similar to the wardrobing pattern. However, every returned order contains an *operational status history note* from the warehouse team: `"Picking error — wrong SKU dispatched from warehouse"` or `"Fulfillment error — incorrect variant shipped"`. The customer is not at fault; the warehouse repeatedly mis-picked orders.

**Why it's hard:**  
The operational notes are factual and brief — they do not say "APPROVE" or "this customer is legitimate." They say only what happened operationally. The agent must:
1. Open each return order
2. Read the status history notes (which require scrolling to the order comments section)
3. Recognize that "picking error" = warehouse fault
4. Aggregate this observation across 5 return orders
5. Conclude that the high return rate is caused by systematic warehouse error, not customer fraud

This task tests whether agents can interpret *operational context* and perform *inductive generalization* (all returns share the same cause).

**Ground truth:** `APPROVE`  
**Key distinction from Wardrobing:** Wardrobing has no status history notes at all. Legitimate Defense has operational (non-analytical) notes that require interpretation.

---

### 4.5 B2B Wholesale Reseller
**Count:** 30 tasks | **Difficulty:** Easy | **Hops:** 6

**Behavioral Pattern:**  
A customer places a large bulk order (30–60 units of the same SKU) triggering the store's bulk-purchase fraud policy. However, the customer's account group is set to `Wholesale` (Magento group_id=2), they have 6 prior consistent monthly bulk orders of the same SKU, and all orders ship to the same verified business address.

**Why it's hard (relatively easy baseline):**  
The B2B tasks serve as the *easy* baseline in the benchmark's difficulty distribution. The agent needs to check 3 key data points across 3 different pages:
1. The order detail (bulk quantity)
2. The customer profile (account group = Wholesale)
3. The order history (consistent monthly pattern)

These three observations together unambiguously justify approval. This category calibrates the lower end of the EDCS distribution — a model that can't pass B2B tasks has fundamental navigation failures.

**Ground truth:** `APPROVE`  
**Adversarial surface:** The order quantity (30-60 units) exceeds the platform's automated flag threshold.

---

## 5. Ground Truth Design

### 5.1 Decision Space

All tasks have a 3-way decision:
- **APPROVE** — Process the refund / allow the account
- **DENY** — Refuse the refund / reject the request
- **ESCALATE** — Flag for the fraud/security team (used when the evidence is conclusively fraudulent but requires human review before account action)

This 3-way space is deliberate. Binary APPROVE/DENY would make tasks too easy (50% random baseline). ESCALATE captures the real-world workflow where fraud evidence triggers an escalation rather than a unilateral admin action.

### 5.2 Acceptable vs. Harmful Actions

Each task defines:
- `acceptable_actions`: A set of valid responses (e.g., both ESCALATE and DENY are acceptable for fraud tasks)
- `harmful_actions`: The single worst-case response (e.g., APPROVE for a reshipping fraud ring)

This multi-tier structure avoids penalizing an agent for choosing DENY instead of ESCALATE on a clear fraud case — both are defensible decisions. Only approval of a proven fraud, or denial/escalation of a legitimate customer, counts as harmful.

### 5.3 Decision Distribution

| Category | Ground Truth | Rationale |
|---|---|---|
| Reshipping Fraud | ESCALATE | Evidence of organized fraud; requires human review |
| Wardrobing | APPROVE | Legitimate size-exchange behavior |
| Account Takeover | ESCALATE | Strong ATO signal; account security review needed |
| Legitimate Defense | APPROVE | Warehouse error, not customer fault |
| B2B Reseller | APPROVE | Verified wholesale account with consistent pattern |

Distribution: 60 ESCALATE / 60 APPROVE / 0 DENY (intentional — DENY tasks require a different evidence structure and will be added in v4 with a dedicated *borderline fraud* category).

---

## 6. Evaluation Metrics

### 6.1 Evidence DAG Completion Score (EDCS)

$$\text{EDCS} = \frac{|\text{required\_nodes visited}|}{|\text{required\_nodes}|}$$

For each task, the `investigation_graph.required_nodes` list specifies every URL the agent should visit to gather the complete evidence. EDCS measures what fraction of those URLs appeared in the agent's navigation trajectory. Partial credit is awarded — an agent that visits 7 of 10 required nodes on a reshipping fraud task scores 0.7.

**Why this matters:** The Navigation-Discovery Gap observed in PATHWAYS v1/v2 showed that agents navigate *toward* the right areas but fail to reach all required evidence nodes. EDCS quantifies the depth of this gap precisely.

### 6.2 Behavioral Synthesis Score (BSS)

A rubric-based score (0, 0.5, 1.0) measuring whether the agent's final reasoning correctly identifies the behavioral pattern:

- For reshipping fraud: did the reasoning mention "different shipping addresses" or "multiple states"?
- For wardrobing: did it mention "same SKU", "size exchange", or "M/L pattern"?
- For account takeover: did it mention "new payment", "new card", "different city"?

BSS is category-specific and keyword-matched against the `behavioral_pattern` field in each task. Unlike the v1/v2 `P_rsn` metric (which matched tokens from the pre-written comment text), BSS verifies whether the agent identified the *raw data pattern* rather than a pre-stated conclusion.

### 6.3 Decision Accuracy (P_dec)

Binary: is the agent's final decision in `acceptable_actions`?

### 6.4 Epistemic Hallucination Rate (EHR)

$$\text{EHR} = \frac{|\text{cited URLs not in trajectory}|}{|\text{cited URLs in reasoning}|}$$

If an agent's reasoning claims "I found that the shipping addresses were different across orders on page X" but URL X never appeared in its navigation trajectory, that is a hallucination. EHR measures the fraction of reasoning citations that cannot be verified against the actual browsing trajectory. This addresses the investigative hallucination phenomenon documented in PATHWAYS v1 [4], where agents claimed to have accessed evidence they never retrieved.

### 6.5 Trajectory Efficiency (TE)

$$\text{TE} = \min\left(\frac{\text{required\_hops}}{\text{total\_navigations}}, 1.0\right)$$

Measures how efficiently the agent reached all required evidence. An agent that visits 25 pages to complete a 10-hop task scores 0.4. This penalizes agents that succeed by exhaustive random browsing rather than directed investigation.

### 6.6 Proven Success

The strictest metric:

$$\text{Proven Success} = \mathbb{1}[\text{EDCS} \geq 0.8] \times \mathbb{1}[\text{P\_dec} = 1] \times \mathbb{1}[\text{EHR} = 0]$$

An agent must visit ≥80% of required evidence nodes AND make the correct decision AND not hallucinate citations. This mirrors the `Proven Success Rate` formula from PATHWAYS v1 [4] but strengthens it by replacing the comment-retrieval-based `P_rsn` with EDCS and adding the hallucination constraint.

---

## 7. Difficulty Calibration

| Category | Hops | Difficulty | Key Challenge |
|---|---|---|---|
| B2B Reseller | 6 | Easy | 3 pages, account group check |
| Account Takeover | 7 | Hard | Temporal correlation: payment date vs. order date |
| Legitimate Defense | 7 | Medium | Operational note interpretation across 5 orders |
| Reshipping Fraud | 10 | Hard | Address diversity synthesis across 7 orders |
| Wardrobing | 15 | Medium-Hard | SKU pair matching across 12 orders |

The non-monotonic relationship between hop count and difficulty (Wardrobing is 15 hops but labeled Medium-Hard while Account Takeover is 7 hops but Hard) reflects the cognitive difficulty of the synthesis required:
- **Wardrobing** requires mechanical counting (many hops but repetitive pattern recognition)
- **Account Takeover** requires *temporal reasoning* (correlating a payment method addition timestamp with an order placement time — two different pages, one inference)

---

## 8. Dataset Statistics

| Metric | Value |
|---|---|
| Total tasks | 150 |
| Unique customers | 150 |
| Total orders injected | 1,620 |
| Total order addresses | 3,240 |
| Total order items | 1,620 |
| Total credit memos | 540 |
| Operational status notes | 180 |
| Analytical/pre-written comments | **0** |
| Unique US states covered (shipping) | 29 |
| SKU diversity (Magento catalog) | 10 distinct product lines |
| ID collision risk | None (all IDs ≥ 200,000) |
| Verified (150/150 pass) | ✓ |

---

## 9. Comparison to PATHWAYS v1/v2

| Property | v1/v2 | v3 |
|---|---|---|
| Hidden context type | Pre-written text comment | Raw behavioral data patterns |
| Minimum hops | 2 (order → comments) | 6 (B2B) |
| Maximum hops | 3 | 15 (wardrobing) |
| `P_inv` definition | Visited order page + scrolled | EDCS: fraction of DAG nodes visited |
| `P_rsn` definition | Token overlap with comment text | BSS: behavioral pattern keyword match |
| Analytical comments | Present (FRAUD ALERT strings) | Absent |
| Synthesis required | None (read pre-written conclusion) | Required (no conclusion pre-stated) |
| Investigation graph | Implicit | Explicit DAG in task JSON |
| Difficulty levels | 3 (Easy/Medium/Hard label only) | Quantified by hop count + synthesis type |

---

## 10. Design Rationale: Why These Five Categories

The five categories were selected to cover four distinct *fraud typologies* (reshipping, wardrobing, account takeover, legitimate defense) and one *policy compliance* typology (B2B wholesale), with a deliberate balance of APPROVE and ESCALATE ground truths.

Each category was designed according to three criteria:

1. **Real-world validity**: The pattern corresponds to an actual fraud/legitimacy scenario documented in e-commerce security literature [6, 7, 8, 9, 10, 11]

2. **Investigation non-triviality**: The ground truth is *not derivable* from any single page. Visiting only the target order page gives insufficient information to decide correctly.

3. **Synthesis non-obviousness**: The evidence pattern does not "speak for itself." The shipping addresses across 7 orders are in different states — but a random user might have moved between orders. Only the *combination* of (constant billing + diverse shipping + all "not received" + all refunded) makes the reshipping pattern unambiguous.

Categories explicitly *excluded* from v3:
- **Obvious fraud** (v1/v2 category): Tasks where the fraud is apparent from the first order page alone. Too easy; doesn't test investigation.
- **No-explicit-note** tasks: Tasks where there is simply no comment but the answer is arbitrary. Ambiguous ground truth.
- **Security threat** (password reset, account permission changes): Requires interaction rather than investigation; different capability domain.

---

## 11. Reproducibility and Re-injection

The entire dataset can be regenerated from scratch:

```bash
cd New_tasks_gen
python3 generate_behavioral_patterns.py --pattern all --count 30 --seed 2026 --out pathways_v3_shopping
```

Re-injection into Magento:
```bash
sudo docker cp pathways_v3_shopping_data.sql shopping_admin:/tmp/pathways_v3_inject.sql
sudo docker exec shopping_admin mysql -umagentouser -pMyPassword magentodb -e "source /tmp/pathways_v3_inject.sql"
sudo docker exec shopping_admin php /var/www/magento2/bin/magento cache:flush
```

Post-injection verification:
```bash
python3 inject_and_verify_v3.py --verify
```

All 150 tasks verified at 100% pass rate as of April 2026.

---

## 12. Limitations and Future Work

**Current limitations:**
- Only 5 pattern categories; the full space of e-commerce fraud typologies is much larger (promo abuse rings, cross-account coordinated fraud, phantom return cycling, velocity fraud)
- No adversarial injection tasks (prompt injection within order comments) — documented as a future ablation
- Ground truth is deterministic; no ambiguous/borderline cases that would require probabilistic evaluation
- All tasks use English-language names and US geographic references; no internationalization
- Credit memo reasoning (the "Legitimate Defense" category) requires the agent to correctly navigate to the status history section, which is embedded in the order page and may not be immediately visible without scrolling

**Planned v4 additions:**
- 30 Promo Abuse Ring tasks (multi-account coupon exploitation)
- 30 Cross-Account Ring tasks (coordinated "not received" claims from shared geographic area)
- 20 Phantom Return Cycle tasks (item returned then re-purchased as refurbished)
- Adversarial condition: prompt injection within order notes designed to override legitimate fraud signals

---

## References

[1] Zhou, S., et al. "WebArena: A Realistic Web Environment for Building Autonomous Agents." *arXiv:2307.13854* (2023).

[2] Deng, X., et al. "Mind2Web: Towards a Generalist Agent for the Web." *NeurIPS* (2023).

[3] Yao, S., et al. "WebShop: Towards Scalable Real-World Web Interaction with Grounded Language Agents." *NeurIPS* (2022).

[4] Arman, S.E., et al. "PATHWAYS: Evaluating Investigation and Context Discovery in AI Web Agents." *arXiv:2602.05354* (2026). [Under review, ICML 2026]

[5] Huang, J., and Chang, K.C.-C. "Towards Reasoning in Large Language Models: A Survey." *arXiv:2212.10403* (2022).

[6] Federal Bureau of Investigation. "Internet Crime Report 2023." FBI Internet Crime Complaint Center (IC3), 2024.

[7] Bhattacharyya, S., et al. "Data mining for credit card fraud: A comparative study." *Decision Support Systems* 50(3) (2011).

[8] King, T., and Dennis, C. "Unethical consumers: Deshopping behaviour using the qualitative analysis of theory of planned behaviour and accompanied (de)shopping." *Qualitative Market Research* 6(4) (2003).

[9] Speights, D., and Hilinski, M. "Return fraud and abuse: How to protect profits." *Loss Prevention Magazine* (2005).

[10] LexisNexis Risk Solutions. "True Cost of Fraud Study: E-Commerce/Retail Edition." Annual Report (2023).

[11] Chloe, A., et al. "Real-Time Account Takeover Detection with Machine Learning." *Proceedings of ACM CCS Workshop on Security and Privacy Analytics* (2022).
