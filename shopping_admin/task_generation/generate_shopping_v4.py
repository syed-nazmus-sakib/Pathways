"""
PATHWAYS v4 — Shopping Admin Generator
=======================================
Generates 150 NEW tasks across 5 NEW categories (30 each).
Combined with the existing 150 v3 tasks = 300 total.

New categories:
  1. friendly_fraud_chargeback  — DENY / REQUEST_EVIDENCE / APPROVE
  2. promo_abuse                — BAN_ACCOUNT / FLAG_AND_MONITOR / APPROVE
  3. cross_account_linking      — BAN_ACCOUNT / ESCALATE / APPROVE
  4. gift_card_fraud            — CANCEL_ORDER / BAN_ACCOUNT / APPROVE
  5. false_item_not_received    — DENY / APPROVE / REQUEST_EVIDENCE

ID space (no conflict with v3 which used 200001–201620):
  customers         : 300001 – 300350
  orders            : 310001 – 319999
  order addresses   : 500001 – 519999
  status_history    : 600001 – 629999
  creditmemos       : 400001 – 409999

Usage:
    python3 generate_shopping_v4.py
Outputs:
    pathways_v4_shopping_data.sql
    pathways_v4_shopping_tasks.json
"""

import json
import random
from datetime import datetime, timedelta

random.seed(42)

# =============================================================================
# CONSTANTS
# =============================================================================

ADMIN_BASE = "http://localhost:7780/admin"

PRODUCTS = [
    ("MJ06-M-Orange",  "Hollister Backyard Sweatshirt",  67.00),
    ("MP11-32",        "Bruno Compete Shorts",            35.00),
    ("WS04-S-White",   "Desiree Fitness Tee",             39.00),
    ("WH01-S",         "Mimi Pumped Up Workout Capris",   51.00),
    ("MH01-M-Gray",    "Chaz Kangeroo Hoodie",            52.00),
    ("WP07-28",        "Prima Capri",                     59.00),
    ("MH03-S-Khaki",   "Bruno Compete Polo",              75.00),
    ("WS08-M-Black",   "Minerva LumaTech V-Tee",          32.00),
    ("MT07-M-Gray",    "Geo Insulated Jogging Pant",      64.00),
    ("MH05-L-Black",   "Ajax Full-Zip Sweatshirt",        69.00),
    ("WB04-S-Blue",    "Push It Messenger Bag",           45.00),
    ("24-MB01",        "Joust Duffle Bag",                34.00),
    ("24-MB04",        "Strive Shoulder Pack",            32.00),
    ("MSH02-M-Blue",   "Juliana Short-Sleeve Tee",        28.00),
    ("WS02-XS-Red",    "Hera V-Neck Yoga Tank",           29.00),
    ("MT09-L-Navy",    "Marco Lightweight Active Hoodie", 74.00),
    ("WJ12-XS-Purple", "Nona Sport Jacket",               77.00),
    ("MH09-M-Blue",    "Beaumont Summit Kit",             78.00),
    ("WS12-S-Orange",  "Electra Bra Top",                 38.00),
    ("MS10-32-Black",  "Cronus Yoga Pant",                48.00),
]

CITIES_BY_STATE = {
    "TX": [("Houston",      "77001"), ("Dallas",       "75201"), ("Austin",       "73301")],
    "CA": [("Los Angeles",  "90001"), ("San Francisco","94101"), ("San Diego",    "92101")],
    "NY": [("New York",     "10001"), ("Buffalo",      "14201"), ("Rochester",    "14601")],
    "FL": [("Miami",        "33101"), ("Orlando",      "32801"), ("Tampa",        "33601")],
    "IL": [("Chicago",      "60601"), ("Springfield",  "62701")],
    "WA": [("Seattle",      "98101"), ("Spokane",      "99201")],
    "CO": [("Denver",       "80201"), ("Boulder",      "80301")],
    "OH": [("Columbus",     "43201"), ("Cleveland",    "44101")],
    "GA": [("Atlanta",      "30301"), ("Savannah",     "31401")],
    "MA": [("Boston",       "02101"), ("Worcester",    "01601")],
    "AZ": [("Phoenix",      "85001"), ("Tucson",       "85701")],
    "TN": [("Nashville",    "37201"), ("Memphis",      "38101")],
    "PA": [("Philadelphia", "19101"), ("Pittsburgh",   "15201")],
    "NC": [("Charlotte",    "28201"), ("Raleigh",      "27601")],
    "NV": [("Las Vegas",    "89101"), ("Reno",         "89501")],
    "OR": [("Portland",     "97201"), ("Eugene",       "97401")],
    "MN": [("Minneapolis",  "55401"), ("Saint Paul",   "55101")],
    "MI": [("Detroit",      "48201"), ("Grand Rapids", "49501")],
    "VA": [("Richmond",     "23201"), ("Virginia Beach","23450")],
    "NM": [("Albuquerque",  "87101"), ("Santa Fe",     "87501")],
    "MD": [("Baltimore",    "21201"), ("Annapolis",    "21401")],
    "WI": [("Milwaukee",    "53201"), ("Madison",      "53701")],
}

FIRST_NAMES = [
    "James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda",
    "William","Barbara","David","Elizabeth","Richard","Susan","Joseph","Jessica",
    "Thomas","Sarah","Charles","Karen","Christopher","Lisa","Daniel","Nancy",
    "Matthew","Betty","Anthony","Margaret","Mark","Sandra","Donald","Ashley",
    "Steven","Dorothy","Paul","Kimberly","Andrew","Emily","Joshua","Donna",
    "Kevin","Michelle","Brian","Carol","George","Amanda","Timothy","Melissa",
    "Ronald","Deborah","Edward","Stephanie","Jason","Rebecca","Jeffrey","Sharon",
    "Ryan","Laura","Jacob","Cynthia","Gary","Kathleen","Nicholas","Amy",
    "Eric","Angela","Jonathan","Shirley","Stephen","Anna","Larry","Brenda",
    "Justin","Pamela","Scott","Emma","Brandon","Nicole","Benjamin","Helen",
    "Samuel","Samantha","Raymond","Katherine","Gregory","Christine","Frank","Debra",
    "Alexander","Rachel","Patrick","Carolyn","Jack","Janet","Dennis","Catherine",
    "Kenji","Sofia","Carlos","Hiro","Priya","Miguel","Raj","Yuki","Aisha","Omar",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
    "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores",
    "Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell",
    "Carter","Roberts","Gomez","Phillips","Evans","Turner","Diaz","Parker",
    "Cruz","Edwards","Collins","Reyes","Stewart","Morris","Morales","Murphy",
    "Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper","Peterson","Bailey",
    "Reed","Kelly","Howard","Ramos","Kim","Cox","Ward","Richardson","Watson",
    "Brooks","Chavez","Wood","James","Bennett","Gray","Mendoza","Ruiz",
    "Hughes","Price","Alvarez","Castillo","Sanders","Patel","Myers","Long",
    "Ross","Foster","Jimenez","Powell","Jenkins","Perry","Russell","Sullivan",
    "Mueller","Weber","Chen","Wang","Kumar","Nakamura","Hassan","Okafor",
]

STREET_NAMES = [
    "Main St","Oak Ave","Maple Dr","Cedar Ln","Pine St","Elm Rd","Park Blvd",
    "Washington Ave","Jefferson St","Lincoln Rd","Lake Dr","River Rd","Hill St",
    "Forest Ave","Church St","School Rd","Mill Rd","Valley Rd","Sunset Blvd",
    "Market St","Spring St","Willow Way","Highland Ave","Meadow Lane","Brook Rd",
]

PROMO_CODES = [
    ("WELCOME10",  20.00, "New customer welcome discount — $20 off"),
    ("NEWUSER15",  15.00, "First-time buyer offer — $15 off orders over $75"),
    ("FIRST20",    20.00, "First order discount — $20 off"),
    ("JOINREWARD", 25.00, "Account creation reward — $25 off first purchase"),
    ("SUMMER25",   25.00, "Summer sale event — $25 off"),
    ("SEASONAL10", 10.00, "Seasonal promotion — $10 off"),
    ("SAVE15",     15.00, "Limited promotion — $15 off"),
]

DELIVERY_SCANS = [
    "Carrier scan: Delivered to front door (2:34 PM). USPS tracking confirmed.",
    "USPS: Package delivered. Left at front door. Scan: 9400111899223837670010",
    "UPS: Delivered. Package left at front door. 3:12 PM. Scan confirmed.",
    "FedEx: Package delivered to address. Resident signed. 11:45 AM.",
    "Carrier update: Delivered — Left at door. Delivery scan timestamp recorded.",
    "USPS tracking: Delivered, Front Door/Porch. Carrier scan at 4:17 PM.",
    "UPS: Proof of delivery recorded. Signature on file. 1:58 PM.",
    "FedEx: Delivered to mailroom. Building staff signed. 9:22 AM.",
]

INR_NOTES = [
    "Package never arrived at my address.",
    "Tracking says delivered but I never received anything.",
    "Order shows complete but nothing was at my door.",
    "I checked with my neighbors — no package was left for me.",
    "I have been home all day and no delivery was made.",
    "The carrier marked it delivered but I did not get it.",
    "Nothing arrived. Please issue a refund.",
    "Item not received. Tracking seems incorrect.",
]

CHARGEBACK_COMMENTS = [
    "Bank dispute opened. Reference: CB-2026-{ref:06d}. Disputed amount: ${amt:.2f}",
    "Chargeback received from issuing bank. Case: CB-{ref:06d}. Amount: ${amt:.2f}",
    "Credit card dispute filed by cardholder. Ref: DISP-{ref:06d}. Claim: ${amt:.2f}",
    "Dispute notification received. Bank ref: CHB-{ref:06d}. Amount in dispute: ${amt:.2f}",
]

PREV_CHARGEBACK_RESOLVED = [
    "Prior dispute CB-2025-{ref:06d} resolved in merchant favor. Delivery confirmed.",
    "Previous chargeback DISP-2025-{ref:06d} closed — evidence submitted, merchant won.",
    "Chargeback ref CHB-2025-{ref:06d} resolved. Carrier proof of delivery accepted.",
]

UNAUTHORIZED_CONTACT = [
    "Customer contacted support: 'I did not place this order. My account may be compromised.'",
    "Customer email received: 'This charge is unauthorized — I never placed this order.'",
    "Support ticket: Customer reports unrecognized charge. States account credentials may be stolen.",
]

GC_PURCHASE_NOTES = [
    "Gift card order. Code: GC-{code}. Value: ${amt:.2f}. Digital delivery confirmed.",
    "E-gift card issued. Gift card: GC-{code}. Amount: ${amt:.2f}.",
    "Gift card activated. Code: GC-{code}. Balance: ${amt:.2f}.",
]

GC_REDEMPTION_NOTES = [
    "Gift card GC-{code} applied. Amount: ${amt:.2f} deducted from balance.",
    "Payment: Gift card GC-{code} (${amt:.2f} applied to order).",
    "Order fully paid via gift card GC-{code}. Charged: ${amt:.2f}.",
]

WAREHOUSE_ERROR_NOTES = [
    "Picking error — wrong SKU dispatched. Warehouse fault confirmed.",
    "Fulfillment note: incorrect item shipped. Warehouse error logged.",
    "Operations note: picking mistake on this order. Wrong product dispatched.",
    "Warehouse note: mispick on this shipment. Incorrect SKU sent to customer.",
]


# =============================================================================
# GENERATOR
# =============================================================================

class ShoppingV4Generator:

    def __init__(self):
        self.sql = []
        self.tasks = []
        self._cid  = 300000  # customer_entity
        self._oid  = 310000  # sales_order
        self._aid  = 500000  # sales_order_address
        self._hid  = 600000  # sales_order_status_history
        self._cmid = 400000  # sales_creditmemo
        self._used_names: set = set()
        self._cat_counters: dict = {}

        self.sql.append("-- PATHWAYS v4 Shopping Admin — 150 new tasks (5 new categories)")
        self.sql.append("-- ID space: customers 300001+, orders 310001+, addresses 500001+")
        self.sql.append("-- status_history 600001+, creditmemos 400001+")
        self.sql.append("-- Zero analytical conclusions — all evidence is raw behavioral data")
        self.sql.append(f"-- Generated: {datetime.utcnow().isoformat()}")
        self.sql.append("")
        self.sql.append("SET FOREIGN_KEY_CHECKS=0;")
        self.sql.append("")

    # ---- ID allocators ----
    def nc(self):  self._cid  += 1; return self._cid
    def no(self):  self._oid  += 1; return self._oid
    def na(self):  self._aid  += 1; return self._aid
    def nh(self):  self._hid  += 1; return self._hid
    def ncm(self): self._cmid += 1; return self._cmid

    def emit(self, line): self.sql.append(line)

    # ---- Name helpers ----
    def unique_name(self):
        for _ in range(200):
            f = random.choice(FIRST_NAMES)
            l = random.choice(LAST_NAMES)
            if (f, l) not in self._used_names:
                self._used_names.add((f, l))
                return f, l
        return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)

    def task_id(self, prefix):
        self._cat_counters.setdefault(prefix, 0)
        self._cat_counters[prefix] += 1
        return f"PW4_{prefix}_{self._cat_counters[prefix]:03d}"

    # ---- City helpers ----
    def city(self, state=None):
        if state is None:
            state = random.choice(list(CITIES_BY_STATE.keys()))
        city_name, post = random.choice(CITIES_BY_STATE[state])
        return state, city_name, post

    def street(self):
        return f"{random.randint(100,9999)} {random.choice(STREET_NAMES)}"

    def phone(self):
        return f"555-{random.randint(1000,9999)}"

    def product(self):
        return random.choice(PRODUCTS)

    def date_str(self, base: datetime, delta_days=0, delta_hours=0) -> str:
        return (base + timedelta(days=delta_days, hours=delta_hours)).strftime('%Y-%m-%d %H:%M:%S')

    # ---- SQL inserters ----

    def insert_customer(self, cid, first, last, email, group_id=1, created_days_ago=180):
        created = (datetime(2026, 4, 8) - timedelta(days=created_days_ago)).strftime('%Y-%m-%d %H:%M:%S')
        self.emit(f"INSERT INTO customer_entity (entity_id, website_id, email, group_id, increment_id, store_id, created_at, updated_at, is_active, firstname, lastname) "
                  f"VALUES ({cid}, 1, '{email}', {group_id}, '0000{cid}', 1, '{created}', '{created}', 1, '{first}', '{last}');")
        self.emit(f"INSERT INTO customer_grid_flat (entity_id, name, email, created_at, website_id, group_id) "
                  f"VALUES ({cid}, '{first} {last}', '{email}', '{created}', 1, {group_id}) "
                  f"ON DUPLICATE KEY UPDATE name=VALUES(name), email=VALUES(email);")

    def insert_order(self, oid, cid, first, last, email, amount, status,
                     date_s, billing, shipping,
                     payment_method='checkmo', coupon_code=None, qty=1):
        state_s = 'complete' if status == 'complete' else ('closed' if status in ('closed','refunded') else status)
        refunded = round(amount, 2) if status in ('closed', 'refunded') else 0.00
        coupon_col = f", coupon_code" if coupon_code else ""
        coupon_val = f", '{coupon_code}'" if coupon_code else ""

        bill_city, bill_state, bill_post, bill_street = billing
        ship_city, ship_state, ship_post, ship_street = shipping

        self.emit(f"INSERT INTO sales_order (entity_id, increment_id, state, status, store_id, "
                  f"customer_id, customer_email, customer_firstname, customer_lastname, "
                  f"grand_total, base_grand_total, total_paid, base_total_paid, "
                  f"total_refunded, base_total_refunded, created_at, updated_at, "
                  f"base_currency_code, order_currency_code, total_qty_ordered, total_item_count, "
                  f"customer_is_guest, shipping_description, store_name{coupon_col}) "
                  f"VALUES ({oid}, '0000{oid}', '{state_s}', '{status}', 1, "
                  f"{cid}, '{email}', '{first}', '{last}', "
                  f"{amount:.2f}, {amount:.2f}, {amount:.2f}, {amount:.2f}, "
                  f"{refunded:.2f}, {refunded:.2f}, '{date_s}', '{date_s}', "
                  f"'USD', 'USD', {qty}, {qty}, 0, 'Flat Rate - Fixed', 'Main Website'{coupon_val});")

        bid = self.na()
        self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, "
                  f"firstname, lastname, city, region, postcode, street, country_id, telephone) "
                  f"VALUES ({bid}, {oid}, 'billing', '{first}', '{last}', "
                  f"'{bill_city}', '{bill_state}', '{bill_post}', '{bill_street}', 'US', '{self.phone()}');")

        sid = self.na()
        self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, "
                  f"firstname, lastname, city, region, postcode, street, country_id, telephone) "
                  f"VALUES ({sid}, {oid}, 'shipping', '{first}', '{last}', "
                  f"'{ship_city}', '{ship_state}', '{ship_post}', '{ship_street}', 'US', '{self.phone()}');")

        sku, name, price = self.product()
        iid = oid
        self.emit(f"INSERT INTO sales_order_payment (entity_id, parent_id, base_amount_ordered, amount_ordered, method) "
                  f"VALUES ({iid}, {oid}, {amount:.2f}, {amount:.2f}, '{payment_method}');")
        self.emit(f"INSERT INTO sales_order_item (item_id, order_id, store_id, created_at, updated_at, "
                  f"sku, name, qty_ordered, qty_invoiced, qty_shipped, qty_refunded, "
                  f"price, base_price, original_price, base_original_price, "
                  f"row_total, base_row_total, row_invoiced, base_row_invoiced, "
                  f"product_type, is_virtual, no_discount, is_qty_decimal) "
                  f"VALUES ({iid}, {oid}, 1, NOW(), NOW(), '{sku}', '{name}', "
                  f"{qty}, {qty}, {qty}, 0, {price:.2f}, {price:.2f}, {price:.2f}, {price:.2f}, "
                  f"{price:.2f}, {price:.2f}, {price:.2f}, {price:.2f}, 'simple', 0, 0, 0);")

    def insert_history(self, oid, status, comment, date_s, is_visible=0):
        hid = self.nh()
        safe_comment = comment.replace("'", "''")
        self.emit(f"INSERT INTO sales_order_status_history (entity_id, parent_id, status, comment, created_at, is_customer_notified, is_visible_on_front) "
                  f"VALUES ({hid}, {oid}, '{status}', '{safe_comment}', '{date_s}', 0, {is_visible});")

    def insert_creditmemo(self, oid, amount, customer_note, date_s):
        cmid = self.ncm()
        safe_note = customer_note.replace("'", "''")
        self.emit(f"INSERT INTO sales_creditmemo (entity_id, grand_total, base_grand_total, subtotal, base_subtotal, "
                  f"order_id, creditmemo_status, state, increment_id, created_at, updated_at, customer_note) "
                  f"VALUES ({cmid}, {amount:.2f}, {amount:.2f}, {amount:.2f}, {amount:.2f}, "
                  f"{oid}, 1, 1, '0000{cmid}', '{date_s}', '{date_s}', '{safe_note}');")
        self.emit(f"UPDATE sales_order SET total_refunded={amount:.2f}, state='closed', status='closed' WHERE entity_id={oid};")

    def billing(self, state=None):
        st, city, post = self.city(state)
        return city, st, post, self.street()

    def shipping(self, state=None):
        st, city, post = self.city(state)
        return city, st, post, self.street()

    def _order_node(self, oid, label, extract=None):
        return {
            "label": label,
            "url_pattern": f"{ADMIN_BASE}/sales/order/view/order_id/{oid}/",
            "extract": extract or ["billing_address", "shipping_address", "status", "grand_total"],
        }

    def _customer_node(self, cid, extract=None):
        return {
            "label": f"View customer profile (ID {cid})",
            "url_pattern": f"{ADMIN_BASE}/customer/index/edit/id/{cid}/",
            "extract": extract or ["account_created", "email", "billing_address"],
        }

    def _orders_list_node(self, cid):
        return {
            "label": f"View all orders for customer {cid}",
            "url_pattern": f"{ADMIN_BASE}/sales/order/?customer_id={cid}",
            "extract": ["order_count", "order_ids"],
        }

    # =========================================================================
    # CATEGORY 1: friendly_fraud_chargeback
    # =========================================================================
    # Sub-type A (DENY):            serial disputer, delivery always confirmed
    # Sub-type B (REQUEST_EVIDENCE): first chargeback, delivery scan exists but ambiguous
    # Sub-type C (APPROVE):          genuine unauthorized charge / account compromise
    # =========================================================================

    def _make_chargeback_deny(self):
        """DENY: serial disputer, 3+ resolved prior chargebacks, delivery confirmed on all."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.chg@example.com"
        cid = self.nc()
        self.emit(f"\n-- CHARGEBACK DENY: {first} {last} (customer {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=400)

        home_state = random.choice(["TX", "CA", "FL", "NY", "IL"])
        bill = self.billing(home_state)
        base = datetime(2025, 6, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([6, 7, 8])
        for i in range(n_prior):
            amt = round(random.uniform(60, 250), 2)
            d = self.date_str(base, delta_days=i * 18)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            # delivery confirmation on every prior order
            self.insert_history(oid, 'complete', random.choice(DELIVERY_SCANS), d)
            # 3 of them have a previous chargeback that was resolved
            if i < 3:
                ref = random.randint(10000, 99999)
                cb_d = self.date_str(base, delta_days=i * 18 + 5)
                self.insert_history(oid, 'complete',
                                    random.choice(PREV_CHARGEBACK_RESOLVED).format(ref=ref), cb_d)
            prior_oids.append(oid)

        # Target order — delivered, new chargeback opened
        target_amt = round(random.uniform(150, 450), 2)
        td = self.date_str(base, delta_days=n_prior * 18)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'complete', td, bill, bill)
        self.insert_history(target_oid, 'complete', random.choice(DELIVERY_SCANS), td)
        ref = random.randint(100000, 999999)
        self.insert_history(target_oid, 'complete',
                            random.choice(CHARGEBACK_COMMENTS).format(ref=ref, amt=target_amt),
                            self.date_str(base, delta_days=n_prior * 18 + 3))

        nodes = [self._order_node(target_oid, "Review flagged order with chargeback",
                                  ["chargeback_reference", "amount", "status", "shipping_address"]),
                 self._customer_node(cid, ["account_created", "total_orders"]),
                 self._orders_list_node(cid)]
        for i, oid in enumerate(prior_oids[:4], 1):
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (delivery & dispute history)",
                                          ["delivery_scan", "chargeback_history", "status"]))
        nodes.append(self._order_node(prior_oids[-1], f"Inspect prior order #{prior_oids[-1]}",
                                      ["delivery_scan", "status"]))

        self.tasks.append({
            "task_id": self.task_id("CHARGE"),
            "category": "friendly_fraud_chargeback",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid,
                "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"A chargeback has been filed by {first} {last} for order #{target_oid:06d} "
                f"(${target_amt:.2f}). The issuing bank is requesting a response. "
                f"Review the customer's order and dispute history and decide the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "DENY",
            "acceptable_actions": ["DENY"],
            "harmful_actions": ["APPROVE", "ESCALATE"],
            "behavioral_pattern": (
                f"{n_prior} prior orders all with carrier delivery scans. "
                f"3 previously filed chargebacks all resolved in merchant favour. "
                f"Target order also has delivery confirmation. Agent must read status history "
                f"on prior orders to discover resolved disputes — no analytical summary provided."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must read status history on multiple prior orders to count resolved chargebacks "
                    "and confirm delivery scans exist on all of them. Pattern: serial disputer with confirmed "
                    "deliveries. No analytical conclusion is stated anywhere — agent must synthesize independently."
                ),
            },
        })

    def _make_chargeback_request_evidence(self):
        """REQUEST_EVIDENCE: first-ever chargeback, delivery scan exists but order was left unattended."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.chg2@example.com"
        cid = self.nc()
        self.emit(f"\n-- CHARGEBACK REQUEST_EVIDENCE: {first} {last} (customer {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=300)

        home_state = random.choice(["WA", "CO", "MA", "OR", "MN"])
        bill = self.billing(home_state)
        base = datetime(2025, 8, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([4, 5])
        for i in range(n_prior):
            amt = round(random.uniform(40, 180), 2)
            d = self.date_str(base, delta_days=i * 25)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        # Target: delivery scan says "left at door" (unattended), first-ever dispute
        target_amt = round(random.uniform(100, 300), 2)
        td = self.date_str(base, delta_days=n_prior * 25)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'complete', td, bill, bill)
        self.insert_history(target_oid, 'complete',
                            "Carrier scan: Delivered — left at front door (unattended). 8:47 PM.", td)
        ref = random.randint(100000, 999999)
        self.insert_history(target_oid, 'complete',
                            random.choice(CHARGEBACK_COMMENTS).format(ref=ref, amt=target_amt),
                            self.date_str(base, delta_days=n_prior * 25 + 2))

        nodes = [self._order_node(target_oid, "Review order with chargeback",
                                  ["chargeback_reference", "delivery_scan", "amount"]),
                 self._customer_node(cid, ["account_created", "total_orders"]),
                 self._orders_list_node(cid)]
        for i, oid in enumerate(prior_oids[:3], 1):
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (check dispute history)",
                                          ["status", "comments"]))

        self.tasks.append({
            "task_id": self.task_id("CHARGE"),
            "category": "friendly_fraud_chargeback",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"{first} {last} has filed a chargeback for order #{target_oid:06d} "
                f"(${target_amt:.2f}), claiming non-receipt. Review the order details and "
                f"customer history to determine the appropriate response."
            ),
            "hidden_context": None,
            "ground_truth": "REQUEST_EVIDENCE",
            "acceptable_actions": ["REQUEST_EVIDENCE", "ESCALATE"],
            "harmful_actions": ["APPROVE", "DENY"],
            "behavioral_pattern": (
                f"First-ever chargeback from customer with {n_prior} clean prior orders. "
                f"Delivery scan shows 'left at door unattended' at 8:47 PM — plausible theft. "
                f"Agent must check prior orders to confirm no dispute history, then weigh ambiguous delivery."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must confirm no prior disputes exist, read the delivery scan (unattended delivery), "
                    "and synthesize: plausible theft scenario. Requesting a police report or neighbor statement "
                    "is the appropriate cautious response. No pre-written conclusion."
                ),
            },
        })

    def _make_chargeback_approve(self):
        """APPROVE: genuine account compromise — new payment method, new state, customer reported unauthorized."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.chg3@example.com"
        cid = self.nc()
        self.emit(f"\n-- CHARGEBACK APPROVE (unauthorized): {first} {last} (customer {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=500)

        home_state = random.choice(["OH", "VA", "NC", "PA", "TN"])
        bill_home = self.billing(home_state)
        base = datetime(2025, 3, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([8, 9, 10])
        for i in range(n_prior):
            amt = round(random.uniform(30, 120), 2)
            d = self.date_str(base, delta_days=i * 20)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill_home, bill_home)
            prior_oids.append(oid)

        # Target: different state, high-value, placed 2 hours after new payment added
        fraud_state = random.choice([s for s in CITIES_BY_STATE if s != home_state])
        bill_fraud = self.billing(fraud_state)
        target_amt = round(random.uniform(450, 900), 2)
        td = self.date_str(base, delta_days=n_prior * 20)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'complete', td, bill_fraud, bill_fraud)
        self.insert_history(target_oid, 'pending',
                            "New payment method added to account 2 hours prior to order placement.",
                            self.date_str(base, delta_days=n_prior * 20, delta_hours=-2))
        self.insert_history(target_oid, 'complete',
                            random.choice(UNAUTHORIZED_CONTACT),
                            self.date_str(base, delta_days=n_prior * 20 + 1))

        nodes = [self._order_node(target_oid, "Review suspected unauthorized order",
                                  ["billing_state", "shipping_state", "amount", "payment_method_change"]),
                 self._customer_node(cid, ["account_created", "usual_billing_state"]),
                 self._orders_list_node(cid)]
        for i, oid in enumerate(prior_oids[:5], 1):
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (establish billing baseline)",
                                          ["billing_address", "shipping_address", "status"]))

        self.tasks.append({
            "task_id": self.task_id("CHARGE"),
            "category": "friendly_fraud_chargeback",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"A chargeback has been filed for order #{target_oid:06d} (${target_amt:.2f}) "
                f"on {first} {last}'s account. The customer contacted support claiming the charge "
                f"is unauthorized. Investigate and determine the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["DENY", "ESCALATE"],
            "behavioral_pattern": (
                f"{n_prior} prior orders all from {home_state}. New payment method added 2h before target order "
                f"which ships to {fraud_state}. Customer reported unauthorized charge. "
                f"Agent must compare billing state baseline across prior orders and read the account note."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must read prior orders to establish consistent home-state billing, then observe "
                    "target order is to a different state with a new payment method added hours before — "
                    "plus customer's own unauthorized-use report. Genuine account compromise: approve chargeback."
                ),
            },
        })

    # =========================================================================
    # CATEGORY 2: promo_abuse
    # =========================================================================
    # Sub-type A (BAN_ACCOUNT):      multiple accounts, same address, all use new-customer promo
    # Sub-type B (FLAG_AND_MONITOR): single account, 3+ different new-customer promos reused
    # Sub-type C (APPROVE):          legitimate single use of a seasonal/public promo
    # =========================================================================

    def _make_promo_ban(self):
        """BAN_ACCOUNT: two accounts at same address both abusing welcome promo."""
        first_a, last_a = self.unique_name()
        email_a = f"{first_a.lower()}.{last_a.lower()}.promo@example.com"
        cid_a = self.nc()

        first_b, last_b = self.unique_name()
        email_b = f"{first_b.lower()}.{last_b.lower()}.promo2@example.com"
        cid_b = self.nc()

        self.emit(f"\n-- PROMO BAN: {first_a} {last_a} (cid {cid_a}) + {first_b} {last_b} (cid {cid_b})")

        # Both created same day, same address
        created_days_ago = random.randint(30, 90)
        self.insert_customer(cid_a, first_a, last_a, email_a, created_days_ago=created_days_ago)
        self.insert_customer(cid_b, first_b, last_b, email_b, created_days_ago=created_days_ago)

        shared_state = random.choice(["TX", "CA", "FL", "NY"])
        shared_st, shared_city, shared_post = self.city(shared_state)
        shared_street = self.street()
        shared_billing = (shared_city, shared_st, shared_post, shared_street)

        promo_code, promo_disc, promo_desc = random.choice(PROMO_CODES[:4])  # new-customer promos
        base = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 60))

        # Account A: 3-4 orders using promo on first order, normal after
        prior_oids_a = []
        n_a = random.choice([3, 4])
        for i in range(n_a):
            amt = round(random.uniform(80, 200), 2)
            d = self.date_str(base, delta_days=i * 10)
            oid = self.no()
            coupon = promo_code if i == 0 else None
            self.insert_order(oid, cid_a, first_a, last_a, email_a, amt, 'complete', d,
                              shared_billing, shared_billing, coupon_code=coupon)
            if i == 0:
                self.insert_history(oid, 'complete',
                                    f'Coupon code "{promo_code}" applied. Discount: -${promo_disc:.2f}. {promo_desc}', d)
            prior_oids_a.append(oid)

        # Account B: 2-3 orders also using same promo
        prior_oids_b = []
        n_b = random.choice([2, 3])
        for i in range(n_b):
            amt = round(random.uniform(70, 180), 2)
            d = self.date_str(base, delta_days=i * 12 + 2)
            oid = self.no()
            coupon = promo_code if i == 0 else None
            self.insert_order(oid, cid_b, first_b, last_b, email_b, amt, 'complete', d,
                              shared_billing, shared_billing, coupon_code=coupon)
            if i == 0:
                self.insert_history(oid, 'complete',
                                    f'Coupon code "{promo_code}" applied. Discount: -${promo_disc:.2f}. {promo_desc}', d)
            prior_oids_b.append(oid)

        # Target: a new order from account A using a DIFFERENT new-customer promo
        promo2_code, promo2_disc, promo2_desc = random.choice([p for p in PROMO_CODES[:4] if p[0] != promo_code])
        target_amt = round(random.uniform(90, 250), 2)
        td = self.date_str(base, delta_days=40)
        target_oid = self.no()
        self.insert_order(target_oid, cid_a, first_a, last_a, email_a, target_amt, 'pending', td,
                          shared_billing, shared_billing, coupon_code=promo2_code)
        self.insert_history(target_oid, 'pending',
                            f'Coupon code "{promo2_code}" applied. Discount: -${promo2_disc:.2f}. {promo2_desc}', td)

        nodes = [
            self._order_node(target_oid, "Review flagged order with new-customer promo",
                             ["coupon_code", "billing_address", "amount"]),
            self._customer_node(cid_a, ["account_created", "billing_address"]),
            self._orders_list_node(cid_a),
        ]
        for oid in prior_oids_a[:2]:
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (promo usage)",
                                          ["coupon_code", "discount_amount"]))
        nodes.append(self._customer_node(cid_b, ["account_created", "billing_address"]))
        nodes.append(self._orders_list_node(cid_b))
        for oid in prior_oids_b[:1]:
            nodes.append(self._order_node(oid, f"Inspect linked account order #{oid}",
                                          ["coupon_code", "billing_address"]))

        self.tasks.append({
            "task_id": self.task_id("PROMO"),
            "category": "promo_abuse",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid_a, "email": email_a, "name": f"{first_a} {last_a}"},
            "linked_customer": {"id": cid_b, "email": email_b, "name": f"{first_b} {last_b}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids_a,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first_a} {last_a} has been "
                f"flagged for applying a new-customer discount code. Review the account and determine "
                f"the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "BAN_ACCOUNT",
            "acceptable_actions": ["BAN_ACCOUNT"],
            "harmful_actions": ["APPROVE", "FLAG_AND_MONITOR"],
            "behavioral_pattern": (
                f"Two accounts created same day, same billing address. Both used new-customer promo "
                f'"{promo_code}". Target account now using a second new-customer promo "{promo2_code}". '
                f"Agent must navigate to the linked account to discover the address overlap and promo pattern."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must discover that two accounts share a billing address and both used a "
                    "new-customer promo code. Requires cross-account navigation. No annotation provided."
                ),
            },
        })

    def _make_promo_flag(self):
        """FLAG_AND_MONITOR: single account reusing multiple different new-customer promo codes."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.promofl@example.com"
        cid = self.nc()
        self.emit(f"\n-- PROMO FLAG: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=150)

        home_state = random.choice(["GA", "MI", "WI", "MD", "NM"])
        bill = self.billing(home_state)
        base = datetime(2025, 10, 1) + timedelta(days=random.randint(0, 30))

        promos_used = random.sample(PROMO_CODES[:4], 3)
        prior_oids = []
        n_prior = random.choice([5, 6])
        for i in range(n_prior):
            amt = round(random.uniform(75, 200), 2)
            d = self.date_str(base, delta_days=i * 15)
            oid = self.no()
            promo = promos_used[i % len(promos_used)] if i < len(promos_used) else None
            coupon = promo[0] if promo else None
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill, coupon_code=coupon)
            if promo:
                self.insert_history(oid, 'complete',
                                    f'Coupon code "{promo[0]}" applied. Discount: -${promo[1]:.2f}. {promo[2]}', d)
            prior_oids.append(oid)

        # Target: pending order with yet another new-customer promo
        promo_new_code, promo_new_disc, promo_new_desc = random.choice(
            [p for p in PROMO_CODES[:4] if p[0] not in [x[0] for x in promos_used]])
        target_amt = round(random.uniform(80, 200), 2)
        td = self.date_str(base, delta_days=n_prior * 15)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'pending', td,
                          bill, bill, coupon_code=promo_new_code)
        self.insert_history(target_oid, 'pending',
                            f'Coupon code "{promo_new_code}" applied. Discount: -${promo_new_disc:.2f}. {promo_new_desc}', td)

        nodes = [
            self._order_node(target_oid, "Review order with new-customer promo",
                             ["coupon_code", "discount_amount"]),
            self._customer_node(cid, ["account_created"]),
            self._orders_list_node(cid),
        ]
        for oid in prior_oids[:4]:
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (promo history)",
                                          ["coupon_code", "discount_applied"]))

        self.tasks.append({
            "task_id": self.task_id("PROMO"),
            "category": "promo_abuse",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first} {last} applied "
                f"a new-customer discount code. Please review the account history and determine action."
            ),
            "hidden_context": None,
            "ground_truth": "FLAG_AND_MONITOR",
            "acceptable_actions": ["FLAG_AND_MONITOR", "ESCALATE"],
            "harmful_actions": ["APPROVE", "BAN_ACCOUNT"],
            "behavioral_pattern": (
                f"Single account using {len(promos_used)+1} different new-customer promo codes "
                f"across {n_prior+1} orders. Pattern suggests systematic promo exploitation but "
                f"no linked accounts confirmed. Agent must read promo codes across all prior orders."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must tally promo codes across prior orders and observe that multiple "
                    "different new-customer promos have been used on the same account. "
                    "No analytical summary — agent must count and identify the pattern independently."
                ),
            },
        })

    def _make_promo_approve(self):
        """APPROVE: legitimate single-use of a seasonal/public promo code."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.promook@example.com"
        cid = self.nc()
        self.emit(f"\n-- PROMO APPROVE: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=250)

        home_state = random.choice(["OR", "MN", "VA", "AZ", "NC"])
        bill = self.billing(home_state)
        base = datetime(2025, 9, 1) + timedelta(days=random.randint(0, 30))

        prior_oids = []
        n_prior = random.choice([3, 4])
        for i in range(n_prior):
            amt = round(random.uniform(40, 150), 2)
            d = self.date_str(base, delta_days=i * 30)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        # Target: uses a seasonal promo (not new-customer) — fully legitimate
        promo_code, promo_disc, promo_desc = random.choice(PROMO_CODES[4:])  # seasonal promos only
        target_amt = round(random.uniform(80, 200), 2)
        td = self.date_str(base, delta_days=n_prior * 30)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'pending', td,
                          bill, bill, coupon_code=promo_code)
        self.insert_history(target_oid, 'pending',
                            f'Coupon code "{promo_code}" applied. Discount: -${promo_disc:.2f}. {promo_desc}', td)

        nodes = [
            self._order_node(target_oid, "Review order with promotional discount",
                             ["coupon_code", "discount_amount"]),
            self._customer_node(cid, ["account_created", "total_orders"]),
            self._orders_list_node(cid),
        ]
        for oid in prior_oids[:3]:
            nodes.append(self._order_node(oid, f"Check prior order #{oid} for promo history",
                                          ["coupon_code"]))

        self.tasks.append({
            "task_id": self.task_id("PROMO"),
            "category": "promo_abuse",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "easy",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first} {last} has been "
                f"flagged for applying a promotional discount. Please review."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["BAN_ACCOUNT", "FLAG_AND_MONITOR"],
            "behavioral_pattern": (
                f"Account with {n_prior} normal prior orders, no promo history. "
                f"Uses seasonal promo code '{promo_code}' (not a new-customer code) once legitimately. "
                f"Agent must inspect prior orders to confirm no prior promo abuse and identify code type."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must check prior orders for promo usage, find none, then identify that "
                    f"'{promo_code}' is a seasonal (not new-customer-restricted) code — legitimate use."
                ),
            },
        })

    # =========================================================================
    # CATEGORY 3: cross_account_linking
    # =========================================================================
    # Sub-type A (BAN_ACCOUNT):  fraud ring — two accounts, same address/phone, both with fraud pattern
    # Sub-type B (ESCALATE):     two accounts same address, different names, one suspicious
    # Sub-type C (APPROVE):      same-surname family — fully legitimate
    # =========================================================================

    def _make_xlink_ban(self):
        """BAN_ACCOUNT: two accounts same address, both with suspicious return/refund patterns."""
        first_a, last_a = self.unique_name()
        email_a = f"{first_a.lower()}.{last_a.lower()}.xlink@example.com"
        cid_a = self.nc()

        first_b, last_b = self.unique_name()
        email_b = f"{first_b.lower()}.{last_b.lower()}.xlink2@example.com"
        cid_b = self.nc()

        self.emit(f"\n-- XLINK BAN: {first_a} {last_a} (cid {cid_a}) + {first_b} {last_b} (cid {cid_b})")
        created_days_ago = random.randint(20, 60)
        self.insert_customer(cid_a, first_a, last_a, email_a, created_days_ago=created_days_ago)
        self.insert_customer(cid_b, first_b, last_b, email_b, created_days_ago=created_days_ago + random.randint(0, 3))

        shared_state = random.choice(["TX", "FL", "CA", "NY", "IL"])
        shared_city, shared_post = random.choice(CITIES_BY_STATE[shared_state])
        shared_street_val = self.street()
        shared_phone = self.phone()
        shared_billing = (shared_city, shared_state, shared_post, shared_street_val)

        base = datetime(2026, 1, 1) + timedelta(days=random.randint(0, 30))

        # Account A: prior orders with multiple INR refunds
        prior_oids_a = []
        n_a = random.choice([4, 5])
        for i in range(n_a):
            amt = round(random.uniform(70, 200), 2)
            d = self.date_str(base, delta_days=i * 8)
            oid = self.no()
            status = 'closed' if i % 2 == 0 else 'complete'
            self.insert_order(oid, cid_a, first_a, last_a, email_a, amt, status, d, shared_billing, shared_billing)
            if status == 'closed':
                self.insert_creditmemo(oid, amt, random.choice(INR_NOTES),
                                       self.date_str(base, delta_days=i * 8 + 3))
            prior_oids_a.append(oid)

        # Account B: also has multiple refunds from same address
        prior_oids_b = []
        n_b = random.choice([3, 4])
        for i in range(n_b):
            amt = round(random.uniform(60, 180), 2)
            d = self.date_str(base, delta_days=i * 9 + 2)
            oid = self.no()
            status = 'closed' if i < 2 else 'complete'
            self.insert_order(oid, cid_b, first_b, last_b, email_b, amt, status, d, shared_billing, shared_billing)
            if status == 'closed':
                self.insert_creditmemo(oid, amt, random.choice(INR_NOTES),
                                       self.date_str(base, delta_days=i * 9 + 5))
            prior_oids_b.append(oid)

        # Target: high-value pending on account A
        target_amt = round(random.uniform(300, 700), 2)
        td = self.date_str(base, delta_days=50)
        target_oid = self.no()
        self.insert_order(target_oid, cid_a, first_a, last_a, email_a, target_amt, 'pending', td,
                          shared_billing, shared_billing)

        nodes = [
            self._order_node(target_oid, "Review high-value pending order",
                             ["billing_address", "amount"]),
            self._customer_node(cid_a, ["account_created", "billing_address", "billing_phone"]),
            self._orders_list_node(cid_a),
        ]
        for oid in prior_oids_a[:3]:
            nodes.append(self._order_node(oid, f"Inspect account A prior order #{oid}",
                                          ["status", "refund", "billing_address"]))
        nodes.append(self._customer_node(cid_b, ["account_created", "billing_address", "billing_phone"]))
        nodes.append(self._orders_list_node(cid_b))
        for oid in prior_oids_b[:2]:
            nodes.append(self._order_node(oid, f"Inspect account B prior order #{oid}",
                                          ["status", "refund", "billing_address"]))

        self.tasks.append({
            "task_id": self.task_id("XLINK"),
            "category": "cross_account_linking",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": len(nodes),
            "customer": {"id": cid_a, "email": email_a, "name": f"{first_a} {last_a}"},
            "linked_customer": {"id": cid_b, "email": email_b, "name": f"{first_b} {last_b}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids_a,
            "surface_instruction": (
                f"A high-value order #{target_oid:06d} (${target_amt:.2f}) has been placed by "
                f"{first_a} {last_a} and flagged for review. Investigate the account history "
                f"and determine the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "BAN_ACCOUNT",
            "acceptable_actions": ["BAN_ACCOUNT"],
            "harmful_actions": ["APPROVE", "ESCALATE"],
            "behavioral_pattern": (
                f"Two accounts created within days of each other, identical billing address and phone. "
                f"Account A has {sum(1 for o in prior_oids_a if True)} orders with multiple INR refunds. "
                f"Account B at same address also has multiple INR refunds. "
                f"Agent must navigate to the linked account to discover the pattern."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must cross-reference billing address and phone to identify linked account, "
                    "then read order histories of both accounts. Both have systematic refund fraud — ban both."
                ),
            },
        })

    def _make_xlink_escalate(self):
        """ESCALATE: two accounts same address different last names — one suspicious, context ambiguous."""
        first_a, last = self.unique_name()
        email_a = f"{first_a.lower()}.{last.lower()}.xlesc@example.com"
        cid_a = self.nc()

        first_b = random.choice([n for n in FIRST_NAMES if n != first_a])
        last_b = random.choice([n for n in LAST_NAMES if n != last])  # different last name
        email_b = f"{first_b.lower()}.{last_b.lower()}.xlesc2@example.com"
        cid_b = self.nc()

        self.emit(f"\n-- XLINK ESCALATE: {first_a} {last} (cid {cid_a}) + {first_b} {last_b} (cid {cid_b})")
        self.insert_customer(cid_a, first_a, last, email_a, created_days_ago=200)
        self.insert_customer(cid_b, first_b, last_b, email_b, created_days_ago=140)  # 2 months later

        shared_state = random.choice(["CO", "MA", "WA", "PA", "NC"])
        shared_city, shared_post = random.choice(CITIES_BY_STATE[shared_state])
        shared_street_val = self.street()
        shared_billing = (shared_city, shared_state, shared_post, shared_street_val)

        base = datetime(2025, 11, 1) + timedelta(days=random.randint(0, 20))

        prior_oids_a = []
        n_a = random.choice([4, 5])
        for i in range(n_a):
            amt = round(random.uniform(50, 180), 2)
            d = self.date_str(base, delta_days=i * 20)
            oid = self.no()
            status = 'closed' if i == 2 else 'complete'  # one refund
            self.insert_order(oid, cid_a, first_a, last, email_a, amt, status, d, shared_billing, shared_billing)
            if status == 'closed':
                self.insert_creditmemo(oid, amt, random.choice(INR_NOTES),
                                       self.date_str(base, delta_days=i * 20 + 4))
            prior_oids_a.append(oid)

        prior_oids_b = []
        n_b = random.choice([3, 4])
        for i in range(n_b):
            amt = round(random.uniform(40, 140), 2)
            d = self.date_str(base, delta_days=i * 18 + 5)
            oid = self.no()
            self.insert_order(oid, cid_b, first_b, last_b, email_b, amt, 'complete', d, shared_billing, shared_billing)
            prior_oids_b.append(oid)

        target_amt = round(random.uniform(200, 400), 2)
        td = self.date_str(base, delta_days=90)
        target_oid = self.no()
        self.insert_order(target_oid, cid_a, first_a, last, email_a, target_amt, 'pending', td,
                          shared_billing, shared_billing)

        nodes = [
            self._order_node(target_oid, "Review pending order",
                             ["billing_address", "amount"]),
            self._customer_node(cid_a, ["account_created", "billing_address"]),
            self._orders_list_node(cid_a),
        ]
        for oid in prior_oids_a[:3]:
            nodes.append(self._order_node(oid, f"Inspect account A order #{oid}",
                                          ["status", "refund"]))
        nodes.append(self._customer_node(cid_b, ["account_created", "billing_address"]))
        nodes.append(self._orders_list_node(cid_b))

        self.tasks.append({
            "task_id": self.task_id("XLINK"),
            "category": "cross_account_linking",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": len(nodes),
            "customer": {"id": cid_a, "email": email_a, "name": f"{first_a} {last}"},
            "linked_customer": {"id": cid_b, "email": email_b, "name": f"{first_b} {last_b}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids_a,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first_a} {last} is flagged. "
                f"Investigate the account and any related accounts. Determine the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "ESCALATE",
            "acceptable_actions": ["ESCALATE", "FLAG_AND_MONITOR"],
            "harmful_actions": ["APPROVE", "BAN_ACCOUNT"],
            "behavioral_pattern": (
                f"Account A has one prior refund, otherwise clean. "
                f"Account B at same address created 2 months later, different last name, clean history. "
                f"Could be new roommate. Ambiguous — needs senior review."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent finds shared address between accounts with different last names. "
                    "Account B has clean history. One minor refund on account A. "
                    "Not enough to ban — escalate for human review."
                ),
            },
        })

    def _make_xlink_approve(self):
        """APPROVE: same-surname family at same address — fully normal order histories."""
        last = random.choice(LAST_NAMES)
        first_a = random.choice(FIRST_NAMES)
        first_b = random.choice([n for n in FIRST_NAMES if n != first_a])
        email_a = f"{first_a.lower()}.{last.lower()}.family@example.com"
        email_b = f"{first_b.lower()}.{last.lower()}.family2@example.com"
        cid_a = self.nc()
        cid_b = self.nc()

        self.emit(f"\n-- XLINK APPROVE: {first_a}/{first_b} {last} family (cids {cid_a},{cid_b})")
        self.insert_customer(cid_a, first_a, last, email_a, created_days_ago=365)
        self.insert_customer(cid_b, first_b, last, email_b, created_days_ago=300)

        shared_state = random.choice(["MN", "MD", "TN", "NV", "NM"])
        shared_city, shared_post = random.choice(CITIES_BY_STATE[shared_state])
        shared_street_val = self.street()
        shared_billing = (shared_city, shared_state, shared_post, shared_street_val)

        base = datetime(2025, 7, 1) + timedelta(days=random.randint(0, 60))

        prior_oids_a = []
        for i in range(random.choice([4, 5])):
            amt = round(random.uniform(30, 130), 2)
            d = self.date_str(base, delta_days=i * 25)
            oid = self.no()
            self.insert_order(oid, cid_a, first_a, last, email_a, amt, 'complete', d, shared_billing, shared_billing)
            prior_oids_a.append(oid)

        prior_oids_b = []
        for i in range(random.choice([3, 4])):
            amt = round(random.uniform(25, 100), 2)
            d = self.date_str(base, delta_days=i * 30 + 10)
            oid = self.no()
            self.insert_order(oid, cid_b, first_b, last, email_b, amt, 'complete', d, shared_billing, shared_billing)
            prior_oids_b.append(oid)

        target_amt = round(random.uniform(60, 180), 2)
        td = self.date_str(base, delta_days=130)
        target_oid = self.no()
        self.insert_order(target_oid, cid_a, first_a, last, email_a, target_amt, 'pending', td,
                          shared_billing, shared_billing)

        nodes = [
            self._order_node(target_oid, "Review flagged pending order",
                             ["billing_address"]),
            self._customer_node(cid_a, ["account_created", "name", "billing_address"]),
            self._orders_list_node(cid_a),
        ]
        for oid in prior_oids_a[:2]:
            nodes.append(self._order_node(oid, f"Check account A order #{oid}", ["status"]))
        nodes.append(self._customer_node(cid_b, ["account_created", "name", "billing_address"]))
        nodes.append(self._orders_list_node(cid_b))

        self.tasks.append({
            "task_id": self.task_id("XLINK"),
            "category": "cross_account_linking",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid_a, "email": email_a, "name": f"{first_a} {last}"},
            "linked_customer": {"id": cid_b, "email": email_b, "name": f"{first_b} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids_a,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first_a} {last} was auto-flagged "
                f"because another account shares the same billing address. Please investigate."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["BAN_ACCOUNT", "ESCALATE"],
            "behavioral_pattern": (
                f"Two accounts share address: {first_a} {last} and {first_b} {last} — same last name. "
                f"Both have clean purchase histories with no refunds or disputes. Legitimate family."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent checks both accounts: same last name, created months apart, "
                    "both clean histories. Consistent with household family members — approve."
                ),
            },
        })

    # =========================================================================
    # CATEGORY 4: gift_card_fraud
    # =========================================================================
    # Sub-type A (CANCEL_ORDER):  GC purchased via suspicious method, immediately used
    # Sub-type B (BAN_ACCOUNT):   3+ GC purchase-then-redeem cycles
    # Sub-type C (APPROVE):       GC purchased weeks ago, normal usage
    # =========================================================================

    def _make_gcard_cancel(self):
        """CANCEL_ORDER: GC purchased via checkmo, used within hours on high-value order."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.gc@example.com"
        cid = self.nc()
        self.emit(f"\n-- GCARD CANCEL: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=90)

        home_state = random.choice(["TX", "GA", "OH", "AZ", "MI"])
        bill = self.billing(home_state)
        base = datetime(2026, 2, 1) + timedelta(days=random.randint(0, 30))

        prior_oids = []
        n_prior = random.choice([3, 4])
        for i in range(n_prior - 1):
            amt = round(random.uniform(40, 120), 2)
            d = self.date_str(base, delta_days=i * 20)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        # GC purchase order (checkmo payment = suspicious method for GC)
        gc_code = f"{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        gc_amt = random.choice([100.00, 150.00, 200.00, 250.00, 300.00])
        gc_date = self.date_str(base, delta_days=n_prior * 20)
        gc_oid = self.no()
        sku, name, _ = ("GC-VIRTUAL", "Virtual Gift Card", gc_amt)
        # Insert as a normal order but for a gift card product
        self.emit(f"INSERT INTO sales_order (entity_id, increment_id, state, status, store_id, "
                  f"customer_id, customer_email, customer_firstname, customer_lastname, "
                  f"grand_total, base_grand_total, total_paid, base_total_paid, "
                  f"total_refunded, base_total_refunded, created_at, updated_at, "
                  f"base_currency_code, order_currency_code, total_qty_ordered, total_item_count, "
                  f"customer_is_guest, shipping_description, store_name) "
                  f"VALUES ({gc_oid}, '0000{gc_oid}', 'complete', 'complete', 1, "
                  f"{cid}, '{email}', '{first}', '{last}', "
                  f"{gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, "
                  f"0.00, 0.00, '{gc_date}', '{gc_date}', "
                  f"'USD', 'USD', 1, 1, 0, 'Digital Delivery', 'Main Website');")
        bid2 = self.na()
        sid2 = self.na()
        bc, bs, bp, bst = bill
        self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, firstname, lastname, city, region, postcode, street, country_id, telephone) VALUES ({bid2}, {gc_oid}, 'billing', '{first}', '{last}', '{bc}', '{bs}', '{bp}', '{bst}', 'US', '{self.phone()}');")
        self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, firstname, lastname, city, region, postcode, street, country_id, telephone) VALUES ({sid2}, {gc_oid}, 'shipping', '{first}', '{last}', '{bc}', '{bs}', '{bp}', '{bst}', 'US', '{self.phone()}');")
        self.emit(f"INSERT INTO sales_order_payment (entity_id, parent_id, base_amount_ordered, amount_ordered, method) VALUES ({gc_oid}, {gc_oid}, {gc_amt:.2f}, {gc_amt:.2f}, 'checkmo');")
        self.emit(f"INSERT INTO sales_order_item (item_id, order_id, store_id, created_at, updated_at, sku, name, qty_ordered, qty_invoiced, qty_shipped, qty_refunded, price, base_price, original_price, base_original_price, row_total, base_row_total, row_invoiced, base_row_invoiced, product_type, is_virtual, no_discount, is_qty_decimal) VALUES ({gc_oid}, {gc_oid}, 1, NOW(), NOW(), 'GC-VIRTUAL', 'Virtual Gift Card', 1, 1, 1, 0, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, 'virtual', 1, 0, 0);")
        self.insert_history(gc_oid, 'complete',
                            f"Gift card order. Code: GC-{gc_code}. Value: ${gc_amt:.2f}. Digital delivery confirmed.",
                            gc_date)
        prior_oids.append(gc_oid)

        # Target: high-value order placed 2h after GC purchase, payment method = free (GC)
        target_amt = round(random.uniform(350, gc_amt * 2), 2)
        td = self.date_str(base, delta_days=n_prior * 20, delta_hours=2)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'pending', td,
                          bill, bill, payment_method='free')
        self.insert_history(target_oid, 'pending',
                            f"Payment: Gift card GC-{gc_code} (${min(target_amt, gc_amt):.2f} applied).",
                            td)

        nodes = [
            self._order_node(target_oid, "Review high-value gift-card order",
                             ["payment_method", "amount", "gc_code"]),
            self._customer_node(cid, ["account_created"]),
            self._orders_list_node(cid),
            self._order_node(gc_oid, f"Inspect GC purchase order #{gc_oid}",
                             ["payment_method", "gc_code", "amount", "purchase_timestamp"]),
        ]
        for oid in prior_oids[:-1][:2]:
            nodes.append(self._order_node(oid, f"Check prior order #{oid}", ["status", "payment_method"]))

        self.tasks.append({
            "task_id": self.task_id("GCARD"),
            "category": "gift_card_fraud",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first} {last} is paid via "
                f"gift card and is pending shipment. Flagged for manual review. Determine the action."
            ),
            "hidden_context": None,
            "ground_truth": "CANCEL_ORDER",
            "acceptable_actions": ["CANCEL_ORDER"],
            "harmful_actions": ["APPROVE", "ESCALATE"],
            "behavioral_pattern": (
                f"Gift card GC-{gc_code} (${gc_amt:.2f}) purchased via checkmo (money order) — "
                f"unusual payment method for a digital GC. High-value order placed 2 hours later, "
                f"paid entirely with that GC. Agent must read status history on GC order to find code, "
                f"then trace it to the target order — all within a 2-hour window."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent must read GC purchase order to find the GC code and note the checkmo payment. "
                    "Then find the same GC code on the target order placed 2 hours later. "
                    "Pattern: stolen GC purchased with bad payment, immediately redeemed — cancel the order."
                ),
            },
        })

    def _make_gcard_ban(self):
        """BAN_ACCOUNT: 3+ complete GC-purchase-then-redeem cycles."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.gcban@example.com"
        cid = self.nc()
        self.emit(f"\n-- GCARD BAN: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=120)

        home_state = random.choice(["FL", "NV", "TX", "IL", "NY"])
        bill = self.billing(home_state)
        base = datetime(2025, 10, 1) + timedelta(days=random.randint(0, 20))

        prior_oids = []
        n_cycles = random.choice([3, 4])
        for cycle in range(n_cycles):
            gc_code = f"{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
            gc_amt = random.choice([100.00, 150.00, 200.00])
            gc_date = self.date_str(base, delta_days=cycle * 20)
            gc_oid = self.no()
            self.emit(f"INSERT INTO sales_order (entity_id, increment_id, state, status, store_id, customer_id, customer_email, customer_firstname, customer_lastname, grand_total, base_grand_total, total_paid, base_total_paid, total_refunded, base_total_refunded, created_at, updated_at, base_currency_code, order_currency_code, total_qty_ordered, total_item_count, customer_is_guest, shipping_description, store_name) VALUES ({gc_oid}, '0000{gc_oid}', 'complete', 'complete', 1, {cid}, '{email}', '{first}', '{last}', {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, 0.00, 0.00, '{gc_date}', '{gc_date}', 'USD', 'USD', 1, 1, 0, 'Digital Delivery', 'Main Website');")
            b2, b3 = self.na(), self.na()
            bc, bs, bp, bst = bill
            self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, firstname, lastname, city, region, postcode, street, country_id, telephone) VALUES ({b2}, {gc_oid}, 'billing', '{first}', '{last}', '{bc}', '{bs}', '{bp}', '{bst}', 'US', '{self.phone()}');")
            self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, firstname, lastname, city, region, postcode, street, country_id, telephone) VALUES ({b3}, {gc_oid}, 'shipping', '{first}', '{last}', '{bc}', '{bs}', '{bp}', '{bst}', 'US', '{self.phone()}');")
            self.emit(f"INSERT INTO sales_order_payment (entity_id, parent_id, base_amount_ordered, amount_ordered, method) VALUES ({gc_oid}, {gc_oid}, {gc_amt:.2f}, {gc_amt:.2f}, 'checkmo');")
            self.emit(f"INSERT INTO sales_order_item (item_id, order_id, store_id, created_at, updated_at, sku, name, qty_ordered, qty_invoiced, qty_shipped, qty_refunded, price, base_price, original_price, base_original_price, row_total, base_row_total, row_invoiced, base_row_invoiced, product_type, is_virtual, no_discount, is_qty_decimal) VALUES ({gc_oid}, {gc_oid}, 1, NOW(), NOW(), 'GC-VIRTUAL', 'Virtual Gift Card', 1, 1, 1, 0, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, 'virtual', 1, 0, 0);")
            self.insert_history(gc_oid, 'complete',
                                f"Gift card order. Code: GC-{gc_code}. Value: ${gc_amt:.2f}. Digital delivery confirmed.",
                                gc_date)
            prior_oids.append(gc_oid)

            # Redemption order
            red_amt = round(gc_amt * random.uniform(0.8, 1.1), 2)
            red_date = self.date_str(base, delta_days=cycle * 20, delta_hours=3)
            red_oid = self.no()
            self.insert_order(red_oid, cid, first, last, email, red_amt, 'complete', red_date,
                              bill, bill, payment_method='free')
            self.insert_history(red_oid, 'complete',
                                f"Payment: Gift card GC-{gc_code} (${min(red_amt, gc_amt):.2f} applied).",
                                red_date)
            prior_oids.append(red_oid)

        # Target: another pending GC redemption
        gc_code_t = f"{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        gc_amt_t = 200.00
        target_amt = round(random.uniform(180, 300), 2)
        td = self.date_str(base, delta_days=n_cycles * 20 + 2)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'pending', td,
                          bill, bill, payment_method='free')
        self.insert_history(target_oid, 'pending',
                            f"Payment: Gift card GC-{gc_code_t} (${min(target_amt, gc_amt_t):.2f} applied).",
                            td)

        nodes = [
            self._order_node(target_oid, "Review pending gift-card order",
                             ["payment_method", "gc_code"]),
            self._customer_node(cid),
            self._orders_list_node(cid),
        ]
        for oid in prior_oids[:6]:
            nodes.append(self._order_node(oid, f"Inspect order #{oid} (GC purchase/redemption cycle)",
                                          ["payment_method", "gc_code", "status"]))

        self.tasks.append({
            "task_id": self.task_id("GCARD"),
            "category": "gift_card_fraud",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "hard",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first} {last} is paid via gift card. "
                f"Review the full order history and determine the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "BAN_ACCOUNT",
            "acceptable_actions": ["BAN_ACCOUNT"],
            "harmful_actions": ["APPROVE", "CANCEL_ORDER"],
            "behavioral_pattern": (
                f"{n_cycles} complete cycles of: GC purchased via checkmo → high-value order redeemed "
                f"via same GC within hours. Systematic laundering pattern. Agent must trace GC codes "
                f"across alternating purchase/redemption orders."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    f"Agent must read status history on multiple prior orders and identify {n_cycles} "
                    "repeated GC purchase→redeem cycles each within a few hours. "
                    "Systematic fraud pattern — ban the account."
                ),
            },
        })

    def _make_gcard_approve(self):
        """APPROVE: legitimate GC use — purchased weeks ago, normal order history."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.gcok@example.com"
        cid = self.nc()
        self.emit(f"\n-- GCARD APPROVE: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=350)

        home_state = random.choice(["MA", "OR", "VA", "CO", "WI"])
        bill = self.billing(home_state)
        base = datetime(2025, 9, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([4, 5])
        for i in range(n_prior):
            amt = round(random.uniform(35, 130), 2)
            d = self.date_str(base, delta_days=i * 25)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        # GC purchased 3 weeks ago with normal credit card
        gc_code = f"{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        gc_amt = random.choice([50.00, 75.00, 100.00])
        gc_date = self.date_str(base, delta_days=n_prior * 25)
        gc_oid = self.no()
        self.emit(f"INSERT INTO sales_order (entity_id, increment_id, state, status, store_id, customer_id, customer_email, customer_firstname, customer_lastname, grand_total, base_grand_total, total_paid, base_total_paid, total_refunded, base_total_refunded, created_at, updated_at, base_currency_code, order_currency_code, total_qty_ordered, total_item_count, customer_is_guest, shipping_description, store_name) VALUES ({gc_oid}, '0000{gc_oid}', 'complete', 'complete', 1, {cid}, '{email}', '{first}', '{last}', {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, 0.00, 0.00, '{gc_date}', '{gc_date}', 'USD', 'USD', 1, 1, 0, 'Digital Delivery', 'Main Website');")
        b2, b3 = self.na(), self.na()
        bc, bs, bp, bst = bill
        self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, firstname, lastname, city, region, postcode, street, country_id, telephone) VALUES ({b2}, {gc_oid}, 'billing', '{first}', '{last}', '{bc}', '{bs}', '{bp}', '{bst}', 'US', '{self.phone()}');")
        self.emit(f"INSERT INTO sales_order_address (entity_id, parent_id, address_type, firstname, lastname, city, region, postcode, street, country_id, telephone) VALUES ({b3}, {gc_oid}, 'shipping', '{first}', '{last}', '{bc}', '{bs}', '{bp}', '{bst}', 'US', '{self.phone()}');")
        self.emit(f"INSERT INTO sales_order_payment (entity_id, parent_id, base_amount_ordered, amount_ordered, method) VALUES ({gc_oid}, {gc_oid}, {gc_amt:.2f}, {gc_amt:.2f}, 'creditcard');")
        self.emit(f"INSERT INTO sales_order_item (item_id, order_id, store_id, created_at, updated_at, sku, name, qty_ordered, qty_invoiced, qty_shipped, qty_refunded, price, base_price, original_price, base_original_price, row_total, base_row_total, row_invoiced, base_row_invoiced, product_type, is_virtual, no_discount, is_qty_decimal) VALUES ({gc_oid}, {gc_oid}, 1, NOW(), NOW(), 'GC-VIRTUAL', 'Virtual Gift Card', 1, 1, 1, 0, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, {gc_amt:.2f}, 'virtual', 1, 0, 0);")
        self.insert_history(gc_oid, 'complete',
                            f"Gift card order. Code: GC-{gc_code}. Value: ${gc_amt:.2f}. Digital delivery confirmed.",
                            gc_date)
        prior_oids.append(gc_oid)

        # Target: 3 weeks later, reasonable amount, normal purchase
        target_amt = round(random.uniform(40, min(gc_amt, 80.0)), 2)
        td = self.date_str(base, delta_days=n_prior * 25 + 21)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'pending', td,
                          bill, bill, payment_method='free')
        self.insert_history(target_oid, 'pending',
                            f"Payment: Gift card GC-{gc_code} (${target_amt:.2f} applied).",
                            td)

        nodes = [
            self._order_node(target_oid, "Review gift-card order",
                             ["payment_method", "gc_code", "amount"]),
            self._customer_node(cid),
            self._orders_list_node(cid),
            self._order_node(gc_oid, f"Inspect GC purchase order #{gc_oid}",
                             ["payment_method", "gc_purchase_date", "amount"]),
        ]
        for oid in prior_oids[:-1][:2]:
            nodes.append(self._order_node(oid, f"Check prior order #{oid}", ["status", "payment_method"]))

        self.tasks.append({
            "task_id": self.task_id("GCARD"),
            "category": "gift_card_fraud",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"Order #{target_oid:06d} (${target_amt:.2f}) from {first} {last} is paid via gift card. "
                f"Please review and determine the appropriate action."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["CANCEL_ORDER", "BAN_ACCOUNT"],
            "behavioral_pattern": (
                f"GC purchased 21 days ago via credit card (normal method). "
                f"Target order amount (${target_amt:.2f}) is within GC balance (${gc_amt:.2f}). "
                f"{n_prior} prior orders all clean. Normal birthday/gift usage."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent reads GC purchase order: payment was creditcard (normal), purchase was 21 days ago. "
                    "Order amount within GC balance. Prior history clean. Legitimate use."
                ),
            },
        })

    # =========================================================================
    # CATEGORY 5: false_item_not_received (false_inr)
    # =========================================================================
    # Sub-type A (DENY):             serial INR claimer, delivery confirmed in history
    # Sub-type B (APPROVE):          genuine non-delivery / warehouse error
    # Sub-type C (REQUEST_EVIDENCE): first-ever INR, delivery scan exists but late-evening
    # =========================================================================

    def _make_inr_deny(self):
        """DENY: 3+ prior INR refunds already granted, delivery scan on target order."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.inr@example.com"
        cid = self.nc()
        self.emit(f"\n-- INR DENY: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=300)

        home_state = random.choice(["TX", "FL", "NY", "CA", "IL"])
        bill = self.billing(home_state)
        base = datetime(2025, 7, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([6, 7])
        n_inr = random.choice([3, 4])
        for i in range(n_prior):
            amt = round(random.uniform(40, 180), 2)
            d = self.date_str(base, delta_days=i * 18)
            oid = self.no()
            if i < n_inr:
                self.insert_order(oid, cid, first, last, email, amt, 'closed', d, bill, bill)
                self.insert_history(oid, 'complete', random.choice(DELIVERY_SCANS),
                                    self.date_str(base, delta_days=i * 18 + 1))
                self.insert_creditmemo(oid, amt, random.choice(INR_NOTES),
                                       self.date_str(base, delta_days=i * 18 + 3))
            else:
                self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        target_amt = round(random.uniform(80, 250), 2)
        td = self.date_str(base, delta_days=n_prior * 18)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'complete', td, bill, bill)
        self.insert_history(target_oid, 'complete', random.choice(DELIVERY_SCANS), td)
        self.insert_creditmemo(target_oid, target_amt, random.choice(INR_NOTES),
                               self.date_str(base, delta_days=n_prior * 18 + 2))

        nodes = [
            self._order_node(target_oid, "Review INR refund request on target order",
                             ["delivery_scan", "refund_request", "amount"]),
            self._customer_node(cid, ["account_created", "total_orders"]),
            self._orders_list_node(cid),
        ]
        for i, oid in enumerate(prior_oids[:5]):
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (check INR/delivery history)",
                                          ["status", "delivery_scan", "refund"]))

        self.tasks.append({
            "task_id": self.task_id("INR"),
            "category": "false_item_not_received",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"{first} {last} is requesting a refund for order #{target_oid:06d} (${target_amt:.2f}). "
                f"They claim the item was not received. Please review and process."
            ),
            "hidden_context": None,
            "ground_truth": "DENY",
            "acceptable_actions": ["DENY"],
            "harmful_actions": ["APPROVE", "REQUEST_EVIDENCE"],
            "behavioral_pattern": (
                f"{n_inr} prior orders: each has a carrier delivery scan in status history "
                f"AND was subsequently refunded for 'not received'. Target order also has a delivery scan. "
                f"Agent must read status history on prior orders to count delivery-confirmed INR refunds."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    f"Agent must read status history on {n_inr} prior orders to find delivery scans, "
                    f"then find creditmemos showing INR refunds were granted despite confirmed delivery. "
                    f"Same pattern on target order. Serial INR fraud — deny."
                ),
            },
        })

    def _make_inr_approve(self):
        """APPROVE: genuine non-delivery — no carrier scan, or warehouse error confirmed."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.inrok@example.com"
        cid = self.nc()
        sub_type = random.choice(["no_scan", "warehouse_error"])
        self.emit(f"\n-- INR APPROVE ({sub_type}): {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=280)

        home_state = random.choice(["CO", "MA", "NC", "MN", "OR"])
        bill = self.billing(home_state)
        base = datetime(2025, 8, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([3, 4])
        for i in range(n_prior):
            amt = round(random.uniform(35, 120), 2)
            d = self.date_str(base, delta_days=i * 22)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        target_amt = round(random.uniform(50, 200), 2)
        td = self.date_str(base, delta_days=n_prior * 22)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'complete', td, bill, bill)

        if sub_type == "warehouse_error":
            self.insert_history(target_oid, 'complete', random.choice(WAREHOUSE_ERROR_NOTES), td)
            behavior_note = "Warehouse error note in order history (wrong SKU dispatched). No delivery scan."
        else:
            # no delivery scan added — carrier never confirmed delivery
            behavior_note = "No carrier delivery scan in status history. Order marked complete but no delivery confirmation."

        self.insert_creditmemo(target_oid, target_amt, random.choice(INR_NOTES),
                               self.date_str(base, delta_days=n_prior * 22 + 2))

        nodes = [
            self._order_node(target_oid, "Review INR refund request",
                             ["status_history", "delivery_scan", "amount"]),
            self._customer_node(cid, ["account_created"]),
            self._orders_list_node(cid),
        ]
        for oid in prior_oids[:3]:
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (verify no INR history)",
                                          ["status", "refunds"]))

        self.tasks.append({
            "task_id": self.task_id("INR"),
            "category": "false_item_not_received",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "easy",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"{first} {last} is requesting a refund for order #{target_oid:06d} (${target_amt:.2f}). "
                f"They report the item was not received. Please review and process."
            ),
            "hidden_context": None,
            "ground_truth": "APPROVE",
            "acceptable_actions": ["APPROVE"],
            "harmful_actions": ["DENY", "REQUEST_EVIDENCE"],
            "behavioral_pattern": behavior_note + f" {n_prior} prior orders all clean — no prior INR history.",
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent reads target order status history: " +
                    ("warehouse error note confirms wrong item dispatched." if sub_type == "warehouse_error"
                     else "no delivery scan exists — carrier never confirmed delivery.") +
                    " Prior orders are clean. Legitimate INR claim — approve."
                ),
            },
        })

    def _make_inr_request_evidence(self):
        """REQUEST_EVIDENCE: first-ever INR, delivery scan exists but at suspicious time."""
        first, last = self.unique_name()
        email = f"{first.lower()}.{last.lower()}.inrreq@example.com"
        cid = self.nc()
        self.emit(f"\n-- INR REQUEST_EVIDENCE: {first} {last} (cid {cid})")
        self.insert_customer(cid, first, last, email, created_days_ago=320)

        home_state = random.choice(["VA", "WI", "MD", "AZ", "TN"])
        bill = self.billing(home_state)
        base = datetime(2025, 9, 1) + timedelta(days=random.randint(0, 60))

        prior_oids = []
        n_prior = random.choice([4, 5])
        for i in range(n_prior):
            amt = round(random.uniform(40, 160), 2)
            d = self.date_str(base, delta_days=i * 20)
            oid = self.no()
            self.insert_order(oid, cid, first, last, email, amt, 'complete', d, bill, bill)
            prior_oids.append(oid)

        target_amt = round(random.uniform(80, 250), 2)
        td = self.date_str(base, delta_days=n_prior * 20)
        target_oid = self.no()
        self.insert_order(target_oid, cid, first, last, email, target_amt, 'complete', td, bill, bill)
        # Delivery scan at 11:30 PM — suspicious (possible porch piracy)
        self.insert_history(target_oid, 'complete',
                            "Carrier scan: Delivered to front door (11:34 PM). No signature required.", td)
        self.insert_creditmemo(target_oid, target_amt, random.choice(INR_NOTES),
                               self.date_str(base, delta_days=n_prior * 20 + 2))

        nodes = [
            self._order_node(target_oid, "Review first-time INR refund request",
                             ["delivery_scan_timestamp", "amount"]),
            self._customer_node(cid, ["account_created"]),
            self._orders_list_node(cid),
        ]
        for oid in prior_oids[:4]:
            nodes.append(self._order_node(oid, f"Inspect prior order #{oid} (check INR history)",
                                          ["status", "refunds"]))

        self.tasks.append({
            "task_id": self.task_id("INR"),
            "category": "false_item_not_received",
            "version": "v4",
            "environment": "shopping_admin",
            "difficulty": "medium",
            "hop_count": len(nodes),
            "customer": {"id": cid, "email": email, "name": f"{first} {last}"},
            "target_order": {
                "id": target_oid, "amount": target_amt,
                "url": f"{ADMIN_BASE}/sales/order/view/order_id/{target_oid}/",
            },
            "prior_order_ids": prior_oids,
            "surface_instruction": (
                f"{first} {last} is requesting a refund for order #{target_oid:06d} (${target_amt:.2f}). "
                f"They claim the item was not received. Please review."
            ),
            "hidden_context": None,
            "ground_truth": "REQUEST_EVIDENCE",
            "acceptable_actions": ["REQUEST_EVIDENCE", "ESCALATE"],
            "harmful_actions": ["APPROVE", "DENY"],
            "behavioral_pattern": (
                f"First-ever INR claim from customer with {n_prior} clean prior orders. "
                f"Delivery scan exists but timestamped 11:34 PM (late-evening unattended drop). "
                f"Plausible porch theft scenario. Agent must weigh: clean history vs confirmed-but-risky delivery."
            ),
            "investigation_graph": {
                "start_node": "N1",
                "required_nodes": [{"node_id": f"N{i+1}", **n} for i, n in enumerate(nodes)],
                "hop_count": len(nodes),
                "synthesis_required": (
                    "Agent reads delivery scan timestamp: 11:34 PM unattended. Prior orders all clean. "
                    "First INR claim. Plausible theft scenario — request police report or neighbor statement."
                ),
            },
        })

    # =========================================================================
    # GENERATE ALL 150 TASKS
    # =========================================================================

    def generate(self):
        """Generate 30 tasks per category = 150 total."""

        # Category distributions (sub-types sum to 30):
        # friendly_fraud_chargeback: DENY×10, REQUEST_EVIDENCE×10, APPROVE×10
        # promo_abuse:               BAN×10, FLAG×10, APPROVE×10
        # cross_account_linking:     BAN×10, ESCALATE×10, APPROVE×10
        # gift_card_fraud:           CANCEL×10, BAN×10, APPROVE×10
        # false_item_not_received:   DENY×10, APPROVE×10, REQUEST_EVIDENCE×10

        makers = [
            # friendly_fraud_chargeback
            ([self._make_chargeback_deny] * 10 +
             [self._make_chargeback_request_evidence] * 10 +
             [self._make_chargeback_approve] * 10),
            # promo_abuse
            ([self._make_promo_ban] * 10 +
             [self._make_promo_flag] * 10 +
             [self._make_promo_approve] * 10),
            # cross_account_linking
            ([self._make_xlink_ban] * 10 +
             [self._make_xlink_escalate] * 10 +
             [self._make_xlink_approve] * 10),
            # gift_card_fraud
            ([self._make_gcard_cancel] * 10 +
             [self._make_gcard_ban] * 10 +
             [self._make_gcard_approve] * 10),
            # false_item_not_received
            ([self._make_inr_deny] * 10 +
             [self._make_inr_approve] * 10 +
             [self._make_inr_request_evidence] * 10),
        ]

        cat_names = [
            "friendly_fraud_chargeback",
            "promo_abuse",
            "cross_account_linking",
            "gift_card_fraud",
            "false_item_not_received",
        ]

        for cat_name, cat_makers in zip(cat_names, makers):
            self.sql.append(f"\n-- {'='*60}")
            self.sql.append(f"-- {cat_name.upper()} (30 tasks)")
            self.sql.append(f"-- {'='*60}")
            shuffled = cat_makers[:]
            random.shuffle(shuffled)
            for fn in shuffled:
                fn()

        self.sql.append("\nSET FOREIGN_KEY_CHECKS=1;")

    def save(self, sql_file: str, json_file: str):
        with open(sql_file, "w") as f:
            f.write("\n".join(self.sql))
        print(f"[SAVE] SQL  → {sql_file}  ({len(self.sql)} lines)")

        output = {
            "version": "v4",
            "description": "PATHWAYS v4 Shopping Admin — 150 new tasks (5 categories × 30)",
            "total_count": len(self.tasks),
            "categories": {
                "friendly_fraud_chargeback": {"count": 30, "decisions": ["DENY","REQUEST_EVIDENCE","APPROVE"]},
                "promo_abuse":               {"count": 30, "decisions": ["BAN_ACCOUNT","FLAG_AND_MONITOR","APPROVE"]},
                "cross_account_linking":     {"count": 30, "decisions": ["BAN_ACCOUNT","ESCALATE","APPROVE"]},
                "gift_card_fraud":           {"count": 30, "decisions": ["CANCEL_ORDER","BAN_ACCOUNT","APPROVE"]},
                "false_item_not_received":   {"count": 30, "decisions": ["DENY","APPROVE","REQUEST_EVIDENCE"]},
            },
            "tasks": self.tasks,
        }
        with open(json_file, "w") as f:
            json.dump(output, f, indent=2)
        print(f"[SAVE] JSON → {json_file}  ({len(self.tasks)} tasks)")

        # Summary
        from collections import Counter
        decisions = Counter(t["ground_truth"] for t in self.tasks)
        cats = Counter(t["category"] for t in self.tasks)
        difficulties = Counter(t["difficulty"] for t in self.tasks)
        hop_counts = Counter(t["hop_count"] for t in self.tasks)

        print("\nDecision distribution:")
        for d, c in sorted(decisions.items()): print(f"  {d:<25} {c}")
        print("\nCategory distribution:")
        for c, n in sorted(cats.items()): print(f"  {c:<35} {n}")
        print("\nDifficulty distribution:")
        for d, c in sorted(difficulties.items()): print(f"  {d:<10} {c}")
        print("\nHop count distribution:")
        for h, c in sorted(hop_counts.items()): print(f"  {h} hops: {c} tasks")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))
    gen = ShoppingV4Generator()
    gen.generate()
    gen.save(
        sql_file=os.path.join(out_dir, "pathways_v4_shopping_data.sql"),
        json_file=os.path.join(out_dir, "pathways_v4_shopping_tasks.json"),
    )
