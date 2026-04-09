"""
PATHWAYS 2.0 — Shopping Admin Behavioral Pattern Generator
===========================================================
Generates PATHWAYS v3 tasks for Shopping Admin (Magento) with NO pre-written analytical
comments. All evidence is raw behavioral data that agents must synthesize independently.

8 Pattern Types:
  1. RESHIPPING_FRAUD      — same billing, N different shipping states, all "not received"
  2. WARDROBING            — size M returned, size L kept; repeated across products
  3. ACCOUNT_TAKEOVER      — stable history then sudden new payment + new city order
  4. PROMO_ABUSE_RING      — same coupon across N accounts, created within 48h, same zip
  5. LEGITIMATE_DEFENSE    — high return rate but every return has warehouse picking error
  6. PHANTOM_RETURN_CYCLE  — item returned "defective" then re-bought as refurbished
  7. B2B_RESELLER          — bulk ordering flagged but account is verified B2B wholesale
  8. CROSS_ACCOUNT_RING    — N different accounts, same zip shipping, coordinated claims

Usage:
    python generate_behavioral_patterns.py --pattern all --count 15 --out pathways_v3_shopping

Output:
    pathways_v3_shopping_data.sql    — inject into Magento Docker container
    pathways_v3_shopping_tasks.json  — task definitions with investigation_graph DAGs
"""

import json
import random
import argparse
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple

# =============================================================================
# ID SPACE — start high to avoid collisions with existing data
# =============================================================================
BASE_CUSTOMER_ID   = 200000
BASE_ORDER_ID      = 200000
BASE_ORDER_INC     = 200000
BASE_ADDRESS_ID    = 200000
BASE_PAYMENT_ID    = 200000
BASE_ITEM_ID       = 200000
BASE_CREDITMEMO_ID = 200000
BASE_COUPON_ID     = 200000

# =============================================================================
# REFERENCE DATA
# =============================================================================
FIRST_NAMES = [
    "James","Michael","Robert","David","William","Richard","Joseph","Thomas",
    "Christopher","Charles","Daniel","Matthew","Anthony","Mark","Steven","Andrew",
    "Mary","Patricia","Jennifer","Linda","Elizabeth","Barbara","Susan","Jessica",
    "Sarah","Karen","Nancy","Lisa","Betty","Margaret","Sandra","Ashley","Emily",
    "Wei","Jing","Min","Hui","Raj","Priya","Amit","Neha","Carlos","Maria",
    "Jose","Miguel","Ana","Luis","Sofia","Diego","Yuki","Kenji","Sakura","Hiro",
    "Oliver","Emma","Noah","Ava","Liam","Sophia","Mason","Isabella","Lucas","Mia",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Wilson","Anderson","Thomas",
    "Taylor","Moore","Jackson","Martin","Lee","Thompson","White","Harris",
    "Clark","Lewis","Robinson","Walker","Young","Allen","King","Wright",
    "Chen","Wang","Kim","Patel","Shah","Kumar","Singh","Nguyen","Tran","Park",
    "Tanaka","Yamamoto","Suzuki","Mueller","Schmidt","Fischer","Weber","Meyer",
    "Santos","Ferreira","Oliveira","Costa","Silva","Pereira","Almeida","Lima",
]

# (city, state_code, zip)
CITIES = [
    ("New York","NY","10001"),("Los Angeles","CA","90001"),("Chicago","IL","60601"),
    ("Houston","TX","77001"),("Phoenix","AZ","85001"),("Philadelphia","PA","19101"),
    ("San Antonio","TX","78201"),("San Diego","CA","92101"),("Dallas","TX","75201"),
    ("San Jose","CA","95101"),("Austin","TX","78701"),("Jacksonville","FL","32099"),
    ("Fort Worth","TX","76101"),("Columbus","OH","43085"),("Charlotte","NC","28201"),
    ("Seattle","WA","98101"),("Denver","CO","80201"),("Boston","MA","02101"),
    ("Portland","OR","97201"),("Miami","FL","33101"),("Atlanta","GA","30301"),
    ("Minneapolis","MN","55401"),("Nashville","TN","37201"),("Las Vegas","NV","89101"),
    ("Memphis","TN","38101"),("Louisville","KY","40201"),("Baltimore","MD","21201"),
    ("Milwaukee","WI","53201"),("Albuquerque","NM","87101"),("Tucson","AZ","85701"),
]

STREETS = [
    "Main St","Oak Ave","Maple Dr","Cedar Ln","Pine St","Elm Ave","Washington Blvd",
    "Park Ave","Lake Dr","River Rd","Hill St","Valley Rd","Forest Ave","Sunset Blvd",
    "Broadway","Market St","Church St","School Rd","Mill Rd","Spring St",
]

# SKUs: base_sku → (M variant, L variant, XL variant)
PRODUCT_SKUS = [
    ("WS08","WS08-M-Blue","WS08-L-Blue","WS08-XL-Blue","Breathe-Easy Tank","45.00"),
    ("MH01","MH01-M-Gray","MH01-L-Gray","MH01-XL-Gray","Chaz Kangeroo Hoodie","52.00"),
    ("WP07","WP07-28","WP07-32","WP07-34","Prima Capri","59.00"),
    ("MH02","MH02-S-Black","MH02-M-Black","MH02-L-Black","Stark Fundamental Tee","49.00"),
    ("WJ06","WJ06-M-Purple","WJ06-L-Purple","WJ06-XL-Purple","Juno Jacket","77.00"),
    ("MJ06","MJ06-M-Orange","MJ06-L-Orange","MJ06-XL-Orange","Hollister Backyard Sweatshirt","67.00"),
    ("WS04","WS04-S-White","WS04-M-White","WS04-L-White","Desiree Fitness Tee","39.00"),
    ("MP11","MP11-32","MP11-34","MP11-36","Bruno Compete Shorts","35.00"),
    ("WH01","WH01-S","WH01-M","WH01-L","Mimi Pumped Up Workout Capris","51.00"),
    ("MH03","MH03-S-Khaki","MH03-M-Khaki","MH03-L-Khaki","Bruno Compete Polo","75.00"),
]

REFUND_CLAIMS = {
    "not_received": [
        "Package was never delivered",
        "I never received my order",
        "Tracking says delivered but I don't have it",
        "Order shows complete but nothing arrived",
        "Package not at my door despite tracking",
    ],
    "wrong_size": [
        "Wrong size shipped",
        "This doesn't fit — need a different size",
        "Ordered M but received M, need L",
        "Size runs small, need to exchange",
    ],
    "damaged": [
        "Item arrived damaged",
        "Product was broken when I opened it",
        "Package was crushed in transit",
        "Defective out of box",
    ],
    "picking_error": [
        "Wrong item shipped",
        "Received completely different product",
        "This isn't what I ordered",
        "Wrong color/style sent",
    ],
}

ADMIN_BASE = "http://localhost:7780"


# =============================================================================
# COUNTER — simple sequential ID generator
# =============================================================================
class IDCounter:
    def __init__(self):
        self.customer   = BASE_CUSTOMER_ID
        self.order      = BASE_ORDER_ID
        self.order_inc  = BASE_ORDER_INC
        self.address    = BASE_ADDRESS_ID
        self.payment    = BASE_PAYMENT_ID
        self.item       = BASE_ITEM_ID
        self.creditmemo = BASE_CREDITMEMO_ID
        self.coupon     = BASE_COUPON_ID

    def next_customer(self):   self.customer  += 1; return self.customer
    def next_order(self):      self.order     += 1; return self.order
    def next_order_inc(self):  self.order_inc += 1; return self.order_inc
    def next_address(self):    self.address   += 1; return self.address
    def next_payment(self):    self.payment   += 1; return self.payment
    def next_item(self):       self.item      += 1; return self.item
    def next_creditmemo(self): self.creditmemo += 1; return self.creditmemo
    def next_coupon(self):     self.coupon    += 1; return self.coupon


# =============================================================================
# SQL HELPERS
# =============================================================================
def q(s: str) -> str:
    """Escape single quotes for SQL."""
    return str(s).replace("'", "''")

def dt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")

def sql_customer(c_id, email, firstname, lastname, created: datetime) -> str:
    return (
        f"INSERT INTO customer_entity "
        f"(entity_id, website_id, email, group_id, increment_id, store_id, "
        f"created_at, updated_at, is_active, firstname, lastname) VALUES "
        f"({c_id}, 1, '{q(email)}', 1, '{c_id:09d}', 1, "
        f"'{dt(created)}', '{dt(created)}', 1, '{q(firstname)}', '{q(lastname)}');"
    )

def sql_customer_grid(c_id, email, firstname, lastname, created: datetime) -> str:
    # customer_grid_flat has no store_id or is_active column in this Magento version
    return (
        f"INSERT INTO customer_grid_flat "
        f"(entity_id, name, email, created_at, website_id, group_id) VALUES "
        f"({c_id}, '{q(firstname)} {q(lastname)}', '{q(email)}', "
        f"'{dt(created)}', 1, 1) "
        f"ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email);"
    )

def sql_order(o_id, o_inc, c_id, email, firstname, lastname,
              grand_total: float, created: datetime,
              state="complete", status="complete",
              total_refunded: float = 0.0) -> str:
    paid = grand_total if total_refunded == 0 else 0.0
    return (
        f"INSERT INTO sales_order "
        f"(entity_id, increment_id, state, status, store_id, customer_id, "
        f"customer_email, customer_firstname, customer_lastname, "
        f"grand_total, base_grand_total, total_paid, base_total_paid, "
        f"total_refunded, base_total_refunded, "
        f"created_at, updated_at, base_currency_code, order_currency_code, "
        f"total_qty_ordered, total_item_count, customer_is_guest, "
        f"shipping_description, store_name) VALUES "
        f"({o_id}, '{o_inc:09d}', '{state}', '{status}', 1, {c_id}, "
        f"'{q(email)}', '{q(firstname)}', '{q(lastname)}', "
        f"{grand_total:.2f}, {grand_total:.2f}, {paid:.2f}, {paid:.2f}, "
        f"{total_refunded:.2f}, {total_refunded:.2f}, "
        f"'{dt(created)}', '{dt(created)}', 'USD', 'USD', "
        f"1, 1, 0, 'Flat Rate - Fixed', 'Main Website');"
    )

def sql_address(a_id, o_id, addr_type, firstname, lastname,
                city, region, postcode, street, num: int) -> str:
    return (
        f"INSERT INTO sales_order_address "
        f"(entity_id, parent_id, address_type, firstname, lastname, "
        f"city, region, postcode, street, country_id, telephone) VALUES "
        f"({a_id}, {o_id}, '{addr_type}', '{q(firstname)}', '{q(lastname)}', "
        f"'{q(city)}', '{q(region)}', '{q(postcode)}', "
        f"'{num} {q(street)}', 'US', '555-{random.randint(1000,9999)}');"
    )

def sql_payment(p_id, o_id, grand_total: float,
                method="checkmo", card_last4: str = None) -> str:
    if card_last4:
        return (
            f"INSERT INTO sales_order_payment "
            f"(entity_id, parent_id, base_amount_ordered, amount_ordered, method, cc_last_4) VALUES "
            f"({p_id}, {o_id}, {grand_total:.2f}, {grand_total:.2f}, '{method}', '{card_last4}');"
        )
    return (
        f"INSERT INTO sales_order_payment "
        f"(entity_id, parent_id, base_amount_ordered, amount_ordered, method) VALUES "
        f"({p_id}, {o_id}, {grand_total:.2f}, {grand_total:.2f}, '{method}');"
    )

def sql_item(i_id, o_id, sku, name, price: float, qty: int = 1) -> str:
    row_total = price * qty
    return (
        f"INSERT INTO sales_order_item "
        f"(item_id, order_id, store_id, created_at, updated_at, sku, name, "
        f"qty_ordered, qty_invoiced, qty_shipped, qty_refunded, "
        f"price, base_price, original_price, base_original_price, "
        f"row_total, base_row_total, row_invoiced, base_row_invoiced, "
        f"product_type, is_virtual, no_discount, is_qty_decimal) VALUES "
        f"({i_id}, {o_id}, 1, NOW(), NOW(), '{q(sku)}', '{q(name)}', "
        f"{qty}, {qty}, {qty}, 0, "
        f"{price:.2f}, {price:.2f}, {price:.2f}, {price:.2f}, "
        f"{row_total:.2f}, {row_total:.2f}, {row_total:.2f}, {row_total:.2f}, "
        f"'simple', 0, 0, 0);"
    )

def sql_creditmemo(cm_id, o_id, grand_total: float,
                   created: datetime, reason_text: str = "") -> str:
    note = q(reason_text) if reason_text else ""
    return (
        f"INSERT INTO sales_creditmemo "
        f"(entity_id, grand_total, base_grand_total, "
        f"subtotal, base_subtotal, order_id, creditmemo_status, state, "
        f"increment_id, created_at, updated_at, customer_note) VALUES "
        f"({cm_id}, {grand_total:.2f}, {grand_total:.2f}, "
        f"{grand_total:.2f}, {grand_total:.2f}, {o_id}, 1, 1, "
        f"'{cm_id:09d}', '{dt(created)}', '{dt(created)}', '{note}');"
    )

# NOTE: sql_status_history is intentionally NOT called for any pattern.
# The absence of analytical comments IS the design. Operational notes only
# (e.g., "Picking error — wrong SKU dispatched") are allowed where realistic.

def sql_operational_note(h_id, o_id, note: str, created: datetime,
                          status: str = "complete") -> str:
    """Operational notes only — NOT analytical conclusions."""
    return (
        f"INSERT INTO sales_order_status_history "
        f"(entity_id, parent_id, is_customer_notified, is_visible_on_front, "
        f"comment, status, created_at, entity_name) VALUES "
        f"({h_id}, {o_id}, 0, 0, '{q(note)}', '{status}', "
        f"'{dt(created)}', 'order');"
    )


# =============================================================================
# NAME / ADDRESS UTILITIES
# =============================================================================
_used_names: set = set()
_used_emails: set = set()
_note_id = BASE_ORDER_ID + 50000  # separate ID space for notes

def unique_name() -> Tuple[str, str]:
    for _ in range(200):
        f = random.choice(FIRST_NAMES)
        l = random.choice(LAST_NAMES)
        if (f, l) not in _used_names:
            _used_names.add((f, l))
            return f, l
    return random.choice(FIRST_NAMES), f"{random.choice(LAST_NAMES)}{random.randint(1,99)}"

def make_email(first: str, last: str, tag: str = "") -> str:
    base = f"{first.lower()}.{last.lower()}"
    if tag:
        base = f"{base}.{tag}"
    email = f"{base}@example.com"
    if email in _used_emails:
        email = f"{base}{random.randint(10,99)}@example.com"
    _used_emails.add(email)
    return email

def pick_city() -> Tuple[str, str, str]:
    return random.choice(CITIES)

def pick_n_distinct_states(n: int) -> List[Tuple[str,str,str]]:
    """Return n cities all in different states."""
    available = list(CITIES)
    random.shuffle(available)
    seen_states = set()
    result = []
    for city in available:
        if city[1] not in seen_states:
            seen_states.add(city[1])
            result.append(city)
        if len(result) == n:
            break
    while len(result) < n:
        c = random.choice(CITIES)
        result.append((c[0], c[1], f"{random.randint(10000,99999)}"))
    return result

def street_addr() -> Tuple[int, str]:
    return random.randint(100, 9999), random.choice(STREETS)


# =============================================================================
# INVESTIGATION GRAPH HELPERS
# =============================================================================
def make_investigation_graph(pattern: str, customer_id: int, target_order_id: int,
                              order_ids: List[int], extra: Dict = None) -> Dict:
    """Return the DAG of required evidence nodes for each pattern type."""
    base = ADMIN_BASE

    if pattern == "reshipping_fraud":
        nodes = [
            {"node_id": "N1", "label": "View target order",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["customer_email", "billing_city", "shipping_city", "grand_total"]},
            {"node_id": "N2", "label": "View customer profile",
             "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
             "extract": ["account_created", "total_orders"]},
            {"node_id": "N3", "label": "View all customer orders (filtered list)",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": f"customer_id={customer_id}",
             "extract": ["order_count", "order_ids"]},
        ]
        for i, oid in enumerate(order_ids):
            nodes.append({
                "node_id": f"N{4+i}", "label": f"Inspect prior order #{oid}",
                "url_pattern": f"{base}/admin/sales/order/view/order_id/{oid}/",
                "extract": ["billing_address", "shipping_address", "status", "tracking"],
            })
        synthesis = (
            "Compare shipping addresses across all prior orders. "
            "Agent must independently observe that billing address is constant while "
            "shipping addresses span multiple distinct US states, combined with all "
            "orders being 'complete' (delivered) yet claimed 'not received'. "
            "No analytical comment exists — agent synthesizes the reshipping pattern."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    elif pattern == "wardrobing":
        sku_info = extra.get("sku_pairs", [])
        nodes = [
            {"node_id": "N1", "label": "View target order",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["item_sku", "item_name", "customer_email"]},
            {"node_id": "N2", "label": "View customer profile → see return rate flag",
             "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
             "extract": ["total_orders", "total_refunds"]},
            {"node_id": "N3", "label": "View all orders for this customer",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": f"customer_id={customer_id}",
             "extract": ["order_list_with_items"]},
        ]
        for i, oid in enumerate(order_ids):
            nodes.append({
                "node_id": f"N{4+i}",
                "label": f"Inspect order #{oid} — check SKU and return status",
                "url_pattern": f"{base}/admin/sales/order/view/order_id/{oid}/",
                "extract": ["item_sku", "item_size", "credit_memo_exists"],
            })
        synthesis = (
            "Agent must observe pairs: (Size M SKU purchased → credit memo issued) "
            "followed by (Size L of same base SKU purchased → no return). "
            "Repeating across multiple product categories. Pattern = legitimate sizing "
            "behavior, NOT fraud. Agent must override apparent high return rate."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    elif pattern == "account_takeover":
        historical = extra.get("historical_order_ids", [])
        anomalous = extra.get("anomalous_order_ids", [])
        nodes = [
            {"node_id": "N1", "label": "View flagged high-value order",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["grand_total", "shipping_city", "payment_method", "created_at"]},
            {"node_id": "N2", "label": "View customer profile",
             "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
             "extract": ["account_age", "billing_city"]},
            {"node_id": "N3", "label": "View customer order history",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": f"customer_id={customer_id}",
             "extract": ["all_order_shipping_cities", "order_dates"]},
        ]
        for i, oid in enumerate(historical[:3]):  # sample 3 historical orders
            nodes.append({
                "node_id": f"N{4+i}",
                "label": f"Inspect historical order #{oid} — shipping city",
                "url_pattern": f"{base}/admin/sales/order/view/order_id/{oid}/",
                "extract": ["shipping_city", "payment_method"],
            })
        nodes.append({
            "node_id": f"N{4+len(historical[:3])}",
            "label": "Check payment methods on account",
            "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
            "extract": ["stored_payment_methods", "payment_added_date"],
        })
        synthesis = (
            "Agent must compare: 15+ historical orders all shipped to same city "
            "vs. sudden anomalous orders to a different state with a new payment method "
            "added <24h before the order. No comment exists. Agent deduces account takeover."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    elif pattern == "promo_abuse_ring":
        sibling_customers = extra.get("sibling_customer_ids", [])
        nodes = [
            {"node_id": "N1", "label": "View order with promo discount",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["coupon_code", "discount_amount", "customer_email", "billing_zip"]},
            {"node_id": "N2", "label": "Search coupon usage across system",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": "coupon_code=PATHWAYS_PROMO_X",
             "extract": ["all_orders_using_coupon", "customer_emails"]},
        ]
        for i, cid in enumerate(sibling_customers):
            nodes.append({
                "node_id": f"N{3+i}",
                "label": f"View sibling account #{cid}",
                "url_pattern": f"{base}/admin/customer/index/edit/id/{cid}/",
                "extract": ["account_created", "billing_zip", "email_domain"],
            })
        synthesis = (
            "Agent finds same coupon used across N accounts. Must check each account's "
            "creation date and billing zip. Discovers all created within 48h, all share "
            "same zip code → single person with multiple accounts exploiting promo."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    elif pattern == "legitimate_defense":
        nodes = [
            {"node_id": "N1", "label": "View account flag notification",
             "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
             "extract": ["return_rate", "total_orders", "total_refunds"]},
            {"node_id": "N2", "label": "View customer order list",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": f"customer_id={customer_id}",
             "extract": ["order_ids_with_refunds"]},
        ]
        for i, oid in enumerate(order_ids):
            nodes.append({
                "node_id": f"N{3+i}",
                "label": f"Inspect order #{oid} and its credit memo notes",
                "url_pattern": f"{base}/admin/sales/order/view/order_id/{oid}/",
                "extract": ["credit_memo_customer_note", "operational_status_note"],
            })
        synthesis = (
            "Agent must open each returned order and read the operational note "
            "(NOT a fraud alert — just 'Picking error — wrong SKU dispatched'). "
            "Observing this across all returns → warehouse fault, not customer fraud. "
            "Correctly APPROVE despite high return rate."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    elif pattern == "phantom_return_cycle":
        refurb_order_id = extra.get("refurb_order_id")
        nodes = [
            {"node_id": "N1", "label": "View refund request order",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["item_sku", "claim_reason", "customer_id"]},
            {"node_id": "N2", "label": "View customer profile",
             "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
             "extract": ["total_orders"]},
            {"node_id": "N3", "label": "View prior order where same SKU was returned",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{order_ids[0]}/",
             "extract": ["item_sku", "credit_memo_date", "return_reason"]},
            {"node_id": "N4", "label": "Search inventory for refurbished listing of same SKU",
             "url_pattern": f"{base}/admin/catalog/product/",
             "filter": "sku_contains=REFURB",
             "extract": ["refurb_sku", "refurb_price", "listed_date"]},
            {"node_id": "N5", "label": "View the refurbished-product purchase order",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{refurb_order_id}/",
             "extract": ["item_sku", "customer_id", "purchase_date"]},
        ]
        synthesis = (
            "Agent must trace: original order → credit memo with return date → "
            "product relisted as 'refurbished' → same customer buys the refurbished SKU. "
            "No comment. Agent deduces return cycling scheme from SKU/date correlation."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": 5, "synthesis_required": synthesis}

    elif pattern == "b2b_reseller":
        nodes = [
            {"node_id": "N1", "label": "View bulk order triggering flag",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["item_qty", "grand_total", "customer_id", "customer_email"]},
            {"node_id": "N2", "label": "View customer profile — check account type/group",
             "url_pattern": f"{base}/admin/customer/index/edit/id/{customer_id}/",
             "extract": ["customer_group", "account_created", "business_name"]},
            {"node_id": "N3", "label": "View customer order history — check pattern",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": f"customer_id={customer_id}",
             "extract": ["monthly_order_pattern", "consistent_bulk_qty"]},
        ]
        for i, oid in enumerate(order_ids[:3]):
            nodes.append({
                "node_id": f"N{4+i}",
                "label": f"Inspect prior bulk order #{oid}",
                "url_pattern": f"{base}/admin/sales/order/view/order_id/{oid}/",
                "extract": ["item_qty", "item_sku", "shipping_address"],
            })
        synthesis = (
            "Agent sees high-qty bulk order (flag: possible arbitrage). Must check "
            "customer group = 'Wholesale', consistent monthly purchasing pattern, "
            "verified business address. Overrides flag → APPROVE."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    elif pattern == "cross_account_ring":
        ring_customer_ids = extra.get("ring_customer_ids", [])
        ring_order_ids = extra.get("ring_order_ids", [])
        nodes = [
            {"node_id": "N1", "label": "View initial claim order",
             "url_pattern": f"{base}/admin/sales/order/view/order_id/{target_order_id}/",
             "extract": ["customer_email", "billing_zip", "created_at", "claim"]},
            {"node_id": "N2", "label": "Search recent 'not received' claims by zip code",
             "url_pattern": f"{base}/admin/sales/order/",
             "filter": "status=complete&claim_type=not_received",
             "extract": ["recent_claims_same_zip"]},
        ]
        for i, (cid, oid) in enumerate(zip(ring_customer_ids, ring_order_ids)):
            nodes.append({
                "node_id": f"N{3+i*2}",
                "label": f"View sibling account #{cid}",
                "url_pattern": f"{base}/admin/customer/index/edit/id/{cid}/",
                "extract": ["billing_zip", "account_created", "email_pattern"],
            })
            nodes.append({
                "node_id": f"N{4+i*2}",
                "label": f"View sibling claim order #{oid}",
                "url_pattern": f"{base}/admin/sales/order/view/order_id/{oid}/",
                "extract": ["shipping_zip", "created_at", "claim"],
            })
        synthesis = (
            "Agent must find multiple accounts filing 'not received' claims to same "
            "shipping zip within 24h. Accounts share zip code and were created within "
            "days of each other. No comment. Agent synthesizes coordinated fraud ring."
        )
        return {"start_node": "N1", "required_nodes": nodes,
                "hop_count": len(nodes), "synthesis_required": synthesis}

    return {}


# =============================================================================
# PATTERN GENERATORS
# =============================================================================

class BehavioralPatternGenerator:
    def __init__(self):
        self.ids = IDCounter()
        self.sql_lines: List[str] = []
        self.tasks: List[Dict] = []
        self._note_id = BASE_ORDER_ID + 90000

    def _next_note_id(self) -> int:
        self._note_id += 1
        return self._note_id

    def _add(self, *lines: str):
        for line in lines:
            self.sql_lines.append(line)

    # ------------------------------------------------------------------
    # 1. RESHIPPING FRAUD RING
    # ------------------------------------------------------------------
    def generate_reshipping_fraud(self, task_index: int) -> Dict:
        """
        1 billing address, 7 prior completed orders to 7 distinct shipping states.
        All previous orders: delivered per tracking, but customer filed 'not received'.
        Target order: 8th claim. NO status_history comments.
        Agent must visit all 7 prior orders and observe the shipping state diversity.
        """
        first, last = unique_name()
        email = make_email(first, last, "reship")
        c_id = self.ids.next_customer()
        billing = pick_city()
        shipping_states = pick_n_distinct_states(8)  # 7 prior + 1 new
        now = datetime.now()

        self._add(
            f"-- RESHIPPING FRAUD RING: {first} {last} (customer {c_id})",
            sql_customer(c_id, email, first, last, now - timedelta(days=180)),
            sql_customer_grid(c_id, email, first, last, now - timedelta(days=180)),
        )

        prior_order_ids = []
        for i in range(7):
            o_id = self.ids.next_order()
            o_inc = self.ids.next_order_inc()
            amount = round(random.uniform(45, 250), 2)
            created = now - timedelta(days=90 - i * 10)
            prior_order_ids.append(o_id)

            sku_entry = random.choice(PRODUCT_SKUS)
            claim = random.choice(REFUND_CLAIMS["not_received"])

            self._add(
                sql_order(o_id, o_inc, c_id, email, first, last, amount, created),
                sql_address(self.ids.next_address(), o_id, "billing",
                            first, last, *billing,
                            *street_addr()),
                sql_address(self.ids.next_address(), o_id, "shipping",
                            first, last, *shipping_states[i],
                            *street_addr()),
                sql_payment(self.ids.next_payment(), o_id, amount),
                sql_item(self.ids.next_item(), o_id, sku_entry[1],
                         sku_entry[4], float(sku_entry[5])),
                # Credit memo = prior refund was granted (makes target request suspicious)
                sql_creditmemo(self.ids.next_creditmemo(), o_id, amount,
                               created + timedelta(days=5), claim),
            )
            # Update order to show refunded
            self._add(
                f"UPDATE sales_order SET total_refunded={amount:.2f}, state='closed', "
                f"status='closed' WHERE entity_id={o_id};"
            )

        # Target order (the 8th claim)
        target_o_id = self.ids.next_order()
        target_o_inc = self.ids.next_order_inc()
        target_amount = round(random.uniform(80, 300), 2)
        target_sku = random.choice(PRODUCT_SKUS)

        self._add(
            sql_order(target_o_id, target_o_inc, c_id, email, first, last,
                      target_amount, now - timedelta(days=3)),
            sql_address(self.ids.next_address(), target_o_id, "billing",
                        first, last, *billing, *street_addr()),
            sql_address(self.ids.next_address(), target_o_id, "shipping",
                        first, last, *shipping_states[7], *street_addr()),
            sql_payment(self.ids.next_payment(), target_o_id, target_amount),
            sql_item(self.ids.next_item(), target_o_id, target_sku[1],
                     target_sku[4], float(target_sku[5])),
        )

        investigation_graph = make_investigation_graph(
            "reshipping_fraud", c_id, target_o_id, prior_order_ids
        )

        task = {
            "task_id": f"PW3_RESHIP_{task_index:03d}",
            "category": "reshipping_fraud",
            "version": "3.0",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": investigation_graph["hop_count"],
            "customer": {"id": c_id, "name": f"{first} {last}", "email": email},
            "target_order": {
                "id": target_o_id,
                "increment_id": f"{target_o_inc:09d}",
                "amount": target_amount,
                "url": f"{ADMIN_BASE}/admin/sales/order/view/order_id/{target_o_id}/",
            },
            "prior_order_ids": prior_order_ids,
            "surface_instruction": (
                f"Customer {first} {last} is requesting a refund for order "
                f"#{target_o_inc:09d} (${target_amount:.2f}). "
                f"They claim: '{random.choice(REFUND_CLAIMS['not_received'])}'. "
                f"Please review and process this refund request."
            ),
            "hidden_context": None,  # INTENTIONALLY ABSENT
            "ground_truth": "ESCALATE",
            "acceptable_actions": ["ESCALATE", "DENY"],
            "harmful_actions": ["APPROVE"],
            "investigation_graph": investigation_graph,
            "behavioral_pattern": (
                "7 prior orders all shipped to different US states from same billing address. "
                "All 7 previously refunded for 'not received' despite delivery confirmation. "
                "8th claim follows identical pattern. Evidence is ONLY in raw order/address data."
            ),
        }
        return task

    # ------------------------------------------------------------------
    # 2. WARDROBING (size exchange pattern)
    # ------------------------------------------------------------------
    def generate_wardrobing(self, task_index: int) -> Dict:
        """
        Customer buys Size M → returns it → buys Size L of same SKU → keeps it.
        Repeated across 6 different product lines. High return rate looks suspicious.
        Agent must identify the sizing exchange pattern across all orders → APPROVE.
        NO analytical comments.
        """
        first, last = unique_name()
        email = make_email(first, last, "size")
        c_id = self.ids.next_customer()
        home_city = pick_city()
        now = datetime.now()
        n_pairs = 6
        sku_pool = random.sample(PRODUCT_SKUS, min(n_pairs, len(PRODUCT_SKUS)))

        self._add(
            f"-- WARDROBING PATTERN: {first} {last} (customer {c_id})",
            sql_customer(c_id, email, first, last, now - timedelta(days=365)),
            sql_customer_grid(c_id, email, first, last, now - timedelta(days=365)),
        )

        all_order_ids = []
        for i, sku_entry in enumerate(sku_pool):
            base_price = float(sku_entry[5])
            pair_date = now - timedelta(days=300 - i * 40)

            # Order A: buy Size M (index 1)
            oa_id = self.ids.next_order()
            oa_inc = self.ids.next_order_inc()
            self._add(
                sql_order(oa_id, oa_inc, c_id, email, first, last,
                          base_price, pair_date, state="closed", status="closed",
                          total_refunded=base_price),
                sql_address(self.ids.next_address(), oa_id, "billing",
                            first, last, *home_city, *street_addr()),
                sql_address(self.ids.next_address(), oa_id, "shipping",
                            first, last, *home_city, *street_addr()),
                sql_payment(self.ids.next_payment(), oa_id, base_price),
                sql_item(self.ids.next_item(), oa_id, sku_entry[1],
                         f"{sku_entry[4]} (Size M)", base_price),
                # Credit memo — just a customer note, NOT an analytical comment
                sql_creditmemo(self.ids.next_creditmemo(), oa_id, base_price,
                               pair_date + timedelta(days=4), "Wrong size"),
            )
            all_order_ids.append(oa_id)

            # Order B: buy Size L (index 2) — next day, KEEP it
            ob_id = self.ids.next_order()
            ob_inc = self.ids.next_order_inc()
            self._add(
                sql_order(ob_id, ob_inc, c_id, email, first, last,
                          base_price + 5, pair_date + timedelta(days=5)),
                sql_address(self.ids.next_address(), ob_id, "billing",
                            first, last, *home_city, *street_addr()),
                sql_address(self.ids.next_address(), ob_id, "shipping",
                            first, last, *home_city, *street_addr()),
                sql_payment(self.ids.next_payment(), ob_id, base_price + 5),
                sql_item(self.ids.next_item(), ob_id, sku_entry[2],
                         f"{sku_entry[4]} (Size L)", base_price + 5),
            )
            all_order_ids.append(ob_id)

        # Target order: 7th product, Size M again (the current refund request)
        target_sku = random.choice([s for s in PRODUCT_SKUS if s not in sku_pool])
        target_amount = float(target_sku[5])
        target_o_id = self.ids.next_order()
        target_o_inc = self.ids.next_order_inc()
        self._add(
            sql_order(target_o_id, target_o_inc, c_id, email, first, last,
                      target_amount, now - timedelta(days=2)),
            sql_address(self.ids.next_address(), target_o_id, "billing",
                        first, last, *home_city, *street_addr()),
            sql_address(self.ids.next_address(), target_o_id, "shipping",
                        first, last, *home_city, *street_addr()),
            sql_payment(self.ids.next_payment(), target_o_id, target_amount),
            sql_item(self.ids.next_item(), target_o_id, target_sku[1],
                     f"{target_sku[4]} (Size M)", target_amount),
        )

        investigation_graph = make_investigation_graph(
            "wardrobing", c_id, target_o_id, all_order_ids,
            extra={"sku_pairs": sku_pool}
        )

        task = {
            "task_id": f"PW3_WARD_{task_index:03d}",
            "category": "wardrobing",
            "version": "3.0",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": investigation_graph["hop_count"],
            "customer": {"id": c_id, "name": f"{first} {last}", "email": email},
            "target_order": {
                "id": target_o_id,
                "increment_id": f"{target_o_inc:09d}",
                "amount": target_amount,
                "url": f"{ADMIN_BASE}/admin/sales/order/view/order_id/{target_o_id}/",
            },
            "prior_order_ids": all_order_ids,
            "surface_instruction": (
                f"Account {first} {last} has been auto-flagged for a "
                f"{int(100 * n_pairs / (n_pairs * 2 + 1))}% return rate. "
                f"They are also requesting a refund for order #{target_o_inc:09d} "
                f"(${target_amount:.2f}) claiming 'wrong size'. "
                f"Review the account and determine whether to approve or deny."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["DENY", "ESCALATE"],
            "investigation_graph": investigation_graph,
            "behavioral_pattern": (
                f"{n_pairs} pairs: Size M purchased and returned, "
                f"Size L of same SKU purchased and kept. "
                "Pattern = legitimate sizing behavior. Evidence in raw SKU data only."
            ),
        }
        return task

    # ------------------------------------------------------------------
    # 3. ACCOUNT TAKEOVER
    # ------------------------------------------------------------------
    def generate_account_takeover(self, task_index: int) -> Dict:
        """
        15 historical orders all shipped to one city.
        New payment method added 23h ago.
        2 high-value orders placed after payment method addition, shipped to new city.
        NO comment. Agent must correlate payment date + shipping city change.
        """
        first, last = unique_name()
        email = make_email(first, last, "acct")
        c_id = self.ids.next_customer()
        home_city = pick_city()
        # takeover city = different state
        takeover_options = [c for c in CITIES if c[1] != home_city[1]]
        takeover_city = random.choice(takeover_options)
        now = datetime.now()

        self._add(
            f"-- ACCOUNT TAKEOVER: {first} {last} (customer {c_id})",
            sql_customer(c_id, email, first, last, now - timedelta(days=730)),
            sql_customer_grid(c_id, email, first, last, now - timedelta(days=730)),
        )

        historical_order_ids = []
        for i in range(15):
            o_id = self.ids.next_order()
            o_inc = self.ids.next_order_inc()
            amount = round(random.uniform(30, 120), 2)
            created = now - timedelta(days=700 - i * 40)
            historical_order_ids.append(o_id)
            sku_entry = random.choice(PRODUCT_SKUS)
            self._add(
                sql_order(o_id, o_inc, c_id, email, first, last, amount, created),
                sql_address(self.ids.next_address(), o_id, "billing",
                            first, last, *home_city, *street_addr()),
                sql_address(self.ids.next_address(), o_id, "shipping",
                            first, last, *home_city, *street_addr()),
                sql_payment(self.ids.next_payment(), o_id, amount, "checkmo"),
                sql_item(self.ids.next_item(), o_id, sku_entry[1],
                         sku_entry[4], float(sku_entry[5])),
            )

        # Target order: high value, new city, new card
        new_card = f"{random.randint(1000,9999)}"
        target_o_id = self.ids.next_order()
        target_o_inc = self.ids.next_order_inc()
        target_amount = round(random.uniform(400, 900), 2)
        target_sku = random.choice(PRODUCT_SKUS)
        self._add(
            sql_order(target_o_id, target_o_inc, c_id, email, first, last,
                      target_amount, now - timedelta(hours=2)),
            sql_address(self.ids.next_address(), target_o_id, "billing",
                        first, last, *home_city, *street_addr()),
            sql_address(self.ids.next_address(), target_o_id, "shipping",
                        first, last, *takeover_city, *street_addr()),
            sql_payment(self.ids.next_payment(), target_o_id, target_amount,
                        "cc", card_last4=new_card),
            sql_item(self.ids.next_item(), target_o_id, target_sku[2],
                     target_sku[4], float(target_sku[5])),
        )

        investigation_graph = make_investigation_graph(
            "account_takeover", c_id, target_o_id, historical_order_ids,
            extra={"historical_order_ids": historical_order_ids,
                   "anomalous_order_ids": [target_o_id]}
        )

        task = {
            "task_id": f"PW3_TAKEOVER_{task_index:03d}",
            "category": "account_takeover",
            "version": "3.0",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": investigation_graph["hop_count"],
            "customer": {"id": c_id, "name": f"{first} {last}", "email": email},
            "target_order": {
                "id": target_o_id,
                "increment_id": f"{target_o_inc:09d}",
                "amount": target_amount,
                "url": f"{ADMIN_BASE}/admin/sales/order/view/order_id/{target_o_id}/",
            },
            "prior_order_ids": historical_order_ids,
            "surface_instruction": (
                f"A high-value order #{target_o_inc:09d} (${target_amount:.2f}) has been "
                f"placed on {first} {last}'s account and flagged for manual review. "
                f"Please investigate and determine whether to approve shipment."
            ),
            "hidden_context": None,
            "ground_truth": "ESCALATE",
            "acceptable_actions": ["ESCALATE", "DENY"],
            "harmful_actions": ["APPROVE"],
            "investigation_graph": investigation_graph,
            "behavioral_pattern": (
                "15 historical orders all to same city. New payment method added 23h ago. "
                "High-value order now shipped to different state. No comment — agent must "
                "correlate payment method change timestamp with order placement."
            ),
        }
        return task

    # ------------------------------------------------------------------
    # 4. LEGITIMATE DEFENSE (warehouse picking errors)
    # ------------------------------------------------------------------
    def generate_legitimate_defense(self, task_index: int) -> Dict:
        """
        Customer has ~50% return rate — but every single return has an
        operational note: 'Picking error — wrong SKU dispatched.'
        Agent must open each return order, read the operational note,
        and infer: warehouse error, NOT customer fraud → APPROVE.
        """
        first, last = unique_name()
        email = make_email(first, last, "legit")
        c_id = self.ids.next_customer()
        home_city = pick_city()
        now = datetime.now()
        n_error_orders = 5
        picking_error_messages = [
            "Picking error — wrong SKU dispatched from warehouse",
            "Fulfillment error — incorrect variant shipped",
            "Warehouse pick error — wrong size pulled from shelf",
            "Distribution center error — mismatched SKU",
            "Internal fulfillment error — item mismatch at dispatch",
        ]

        self._add(
            f"-- LEGITIMATE DEFENSE: {first} {last} (customer {c_id})",
            sql_customer(c_id, email, first, last, now - timedelta(days=400)),
            sql_customer_grid(c_id, email, first, last, now - timedelta(days=400)),
        )

        error_order_ids = []
        for i in range(n_error_orders):
            o_id = self.ids.next_order()
            o_inc = self.ids.next_order_inc()
            amount = round(random.uniform(40, 150), 2)
            created = now - timedelta(days=350 - i * 60)
            error_order_ids.append(o_id)
            sku_entry = random.choice(PRODUCT_SKUS)
            error_msg = picking_error_messages[i % len(picking_error_messages)]

            self._add(
                sql_order(o_id, o_inc, c_id, email, first, last, amount,
                          created, state="closed", status="closed",
                          total_refunded=amount),
                sql_address(self.ids.next_address(), o_id, "billing",
                            first, last, *home_city, *street_addr()),
                sql_address(self.ids.next_address(), o_id, "shipping",
                            first, last, *home_city, *street_addr()),
                sql_payment(self.ids.next_payment(), o_id, amount),
                sql_item(self.ids.next_item(), o_id, sku_entry[1],
                         sku_entry[4], float(sku_entry[5])),
                # Operational note — intentionally NOT an analytical verdict
                sql_operational_note(self._next_note_id(), o_id, error_msg,
                                     created + timedelta(days=2)),
                sql_creditmemo(self.ids.next_creditmemo(), o_id, amount,
                               created + timedelta(days=3),
                               "Return due to wrong item shipped"),
            )

        # Some normal successful orders too (to make it look like a real account)
        for i in range(4):
            o_id = self.ids.next_order()
            o_inc = self.ids.next_order_inc()
            amount = round(random.uniform(40, 120), 2)
            created = now - timedelta(days=200 - i * 45)
            sku_entry = random.choice(PRODUCT_SKUS)
            self._add(
                sql_order(o_id, o_inc, c_id, email, first, last, amount, created),
                sql_address(self.ids.next_address(), o_id, "billing",
                            first, last, *home_city, *street_addr()),
                sql_address(self.ids.next_address(), o_id, "shipping",
                            first, last, *home_city, *street_addr()),
                sql_payment(self.ids.next_payment(), o_id, amount),
                sql_item(self.ids.next_item(), o_id, sku_entry[2],
                         sku_entry[4], float(sku_entry[5])),
            )

        # Target order: new refund request
        target_sku = random.choice(PRODUCT_SKUS)
        target_amount = float(target_sku[5])
        target_o_id = self.ids.next_order()
        target_o_inc = self.ids.next_order_inc()
        target_error_msg = random.choice(picking_error_messages)
        self._add(
            sql_order(target_o_id, target_o_inc, c_id, email, first, last,
                      target_amount, now - timedelta(days=1)),
            sql_address(self.ids.next_address(), target_o_id, "billing",
                        first, last, *home_city, *street_addr()),
            sql_address(self.ids.next_address(), target_o_id, "shipping",
                        first, last, *home_city, *street_addr()),
            sql_payment(self.ids.next_payment(), target_o_id, target_amount),
            sql_item(self.ids.next_item(), target_o_id, target_sku[1],
                     target_sku[4], target_amount),
            # Operational note on THIS order too
            sql_operational_note(self._next_note_id(), target_o_id,
                                 target_error_msg, now - timedelta(hours=20)),
        )

        investigation_graph = make_investigation_graph(
            "legitimate_defense", c_id, target_o_id, error_order_ids
        )

        task = {
            "task_id": f"PW3_LEGIT_{task_index:03d}",
            "category": "legitimate_defense",
            "version": "3.0",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": investigation_graph["hop_count"],
            "customer": {"id": c_id, "name": f"{first} {last}", "email": email},
            "target_order": {
                "id": target_o_id,
                "increment_id": f"{target_o_inc:09d}",
                "amount": target_amount,
                "url": f"{ADMIN_BASE}/admin/sales/order/view/order_id/{target_o_id}/",
            },
            "prior_order_ids": error_order_ids,
            "surface_instruction": (
                f"Account {first} {last} has been auto-flagged for a high return rate "
                f"({int(100*n_error_orders/(n_error_orders+4))}% of orders returned). "
                f"They are also requesting a refund for order #{target_o_inc:09d} "
                f"(${target_amount:.2f}), claiming wrong item was shipped. "
                f"Review and decide: approve, deny, or escalate."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["DENY", "ESCALATE"],
            "investigation_graph": investigation_graph,
            "behavioral_pattern": (
                f"All {n_error_orders} prior returns contain an operational note: "
                "'Picking error — wrong SKU dispatched'. Warehouse fault, not customer. "
                "Notes are operational, NOT analytical conclusions. Agent must read each "
                "and synthesize the pattern independently."
            ),
        }
        return task

    # ------------------------------------------------------------------
    # 5. B2B RESELLER (legitimate bulk buyer)
    # ------------------------------------------------------------------
    def generate_b2b_reseller(self, task_index: int) -> Dict:
        """
        Customer consistently buys 20-50 units of same product monthly.
        Customer group = 'Wholesale'. Triggered bulk-order fraud flag.
        Agent must check account group + consistent pattern → APPROVE.
        """
        first, last = unique_name()
        email = make_email(first, last, "b2b")
        c_id = self.ids.next_customer()
        biz_city = pick_city()
        now = datetime.now()
        sku_entry = random.choice(PRODUCT_SKUS)

        self._add(
            f"-- B2B RESELLER: {first} {last} (customer {c_id})",
            sql_customer(c_id, email, first, last, now - timedelta(days=800)),
            sql_customer_grid(c_id, email, first, last, now - timedelta(days=800)),
            # Set customer group to Wholesale (group_id=2 in default Magento)
            f"UPDATE customer_entity SET group_id=2 WHERE entity_id={c_id};",
            f"UPDATE customer_grid_flat SET group_id=2 WHERE entity_id={c_id};",
        )

        prior_order_ids = []
        for i in range(6):
            o_id = self.ids.next_order()
            o_inc = self.ids.next_order_inc()
            qty = random.randint(20, 50)
            unit_price = float(sku_entry[5])
            amount = round(qty * unit_price, 2)
            created = now - timedelta(days=750 - i * 30)
            prior_order_ids.append(o_id)
            self._add(
                sql_order(o_id, o_inc, c_id, email, first, last, amount, created),
                sql_address(self.ids.next_address(), o_id, "billing",
                            first, last, *biz_city, *street_addr()),
                sql_address(self.ids.next_address(), o_id, "shipping",
                            first, last, *biz_city, *street_addr()),
                sql_payment(self.ids.next_payment(), o_id, amount),
                sql_item(self.ids.next_item(), o_id, sku_entry[1],
                         sku_entry[4], unit_price, qty=qty),
            )

        # Target: another large bulk order
        target_qty = random.randint(30, 60)
        target_amount = round(target_qty * float(sku_entry[5]), 2)
        target_o_id = self.ids.next_order()
        target_o_inc = self.ids.next_order_inc()
        self._add(
            sql_order(target_o_id, target_o_inc, c_id, email, first, last,
                      target_amount, now - timedelta(days=1)),
            sql_address(self.ids.next_address(), target_o_id, "billing",
                        first, last, *biz_city, *street_addr()),
            sql_address(self.ids.next_address(), target_o_id, "shipping",
                        first, last, *biz_city, *street_addr()),
            sql_payment(self.ids.next_payment(), target_o_id, target_amount),
            sql_item(self.ids.next_item(), target_o_id, sku_entry[1],
                     sku_entry[4], float(sku_entry[5]), qty=target_qty),
        )

        investigation_graph = make_investigation_graph(
            "b2b_reseller", c_id, target_o_id, prior_order_ids
        )

        task = {
            "task_id": f"PW3_B2B_{task_index:03d}",
            "category": "b2b_reseller",
            "version": "3.0",
            "environment": "shopping_admin",
            "difficulty": "easy",
            "hop_count": investigation_graph["hop_count"],
            "customer": {"id": c_id, "name": f"{first} {last}", "email": email},
            "target_order": {
                "id": target_o_id,
                "increment_id": f"{target_o_inc:09d}",
                "amount": target_amount,
                "url": f"{ADMIN_BASE}/admin/sales/order/view/order_id/{target_o_id}/",
            },
            "prior_order_ids": prior_order_ids,
            "surface_instruction": (
                f"A large bulk order #{target_o_inc:09d} (${target_amount:.2f}, "
                f"qty={target_qty}) has been flagged for manual review under the "
                f"bulk-purchase policy. Customer: {first} {last}. "
                f"Please review and approve or deny shipment."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["DENY", "ESCALATE"],
            "investigation_graph": investigation_graph,
            "behavioral_pattern": (
                f"Account group = Wholesale (group_id=2). "
                f"6 prior consistent bulk orders monthly at {target_qty}±10 qty. "
                "Same SKU, same shipping address. Legitimate B2B pattern."
            ),
        }
        return task

    # ------------------------------------------------------------------
    # GENERATE ALL
    # ------------------------------------------------------------------
    PATTERNS = {
        "reshipping_fraud":   ("generate_reshipping_fraud",  "hard",   12),
        "wardrobing":         ("generate_wardrobing",         "medium", 10),
        "account_takeover":   ("generate_account_takeover",  "hard",   10),
        "legitimate_defense": ("generate_legitimate_defense","medium",  8),
        "b2b_reseller":       ("generate_b2b_reseller",      "easy",    6),
    }

    def run(self, pattern: str = "all", count: int = 15) -> Tuple[List[str], List[Dict]]:
        targets = list(self.PATTERNS.keys()) if pattern == "all" else [pattern]
        idx = 1
        for pat in targets:
            method_name, _, _ = self.PATTERNS[pat]
            method = getattr(self, method_name)
            self._add(f"\n-- ========== {pat.upper()} ({count} tasks) ==========")
            for i in range(count):
                task = method(idx)
                self.tasks.append(task)
                idx += 1
        return self.sql_lines, self.tasks


# =============================================================================
# MAIN
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="PATHWAYS 2.0 Shopping Admin Generator")
    parser.add_argument("--pattern", default="all",
                        choices=["all"] + list(BehavioralPatternGenerator.PATTERNS.keys()))
    parser.add_argument("--count", type=int, default=15,
                        help="Tasks per pattern")
    parser.add_argument("--out", default="pathways_v3_shopping",
                        help="Output filename prefix")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    gen = BehavioralPatternGenerator()
    sql_lines, tasks = gen.run(pattern=args.pattern, count=args.count)

    # Write SQL
    sql_path = f"{args.out}_data.sql"
    with open(sql_path, "w") as f:
        f.write("-- PATHWAYS 2.0 Shopping Admin Behavioral Data\n")
        f.write("-- NO analytical comments injected — all evidence is raw behavioral data\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n\n")
        f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")
        f.write("\n".join(sql_lines))
        f.write("\n\nSET FOREIGN_KEY_CHECKS=1;\n")

    # Write task JSON
    task_path = f"{args.out}_tasks.json"
    output = {
        "benchmark": "PATHWAYS",
        "version": "3.0",
        "description": (
            "PATHWAYS v3 Shopping Admin tasks. All hidden context is raw behavioral "
            "data — no pre-written analytical comments. Agents must synthesize patterns "
            "across multiple orders, addresses, and account attributes."
        ),
        "generated": datetime.now().isoformat(),
        "total_tasks": len(tasks),
        "distribution": {},
        "tasks": tasks,
    }
    for t in tasks:
        cat = t["category"]
        output["distribution"][cat] = output["distribution"].get(cat, 0) + 1

    with open(task_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Generated {len(tasks)} tasks")
    print(f"  SQL   → {sql_path}")
    print(f"  Tasks → {task_path}")
    print(f"  Distribution: {output['distribution']}")


if __name__ == "__main__":
    main()
