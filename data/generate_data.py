"""
LogiTrack Sample Data Generator
Generates realistic, intentionally-messy CSV data for the Fabric Data Engineering project:
- orders.csv        (Bronze source: simulated SQL export)
- shipments.csv      (Bronze source: simulated SQL export)
- regional_sales_<region>.xlsx  (Bronze source: manual Excel uploads)

Messiness injected on purpose (mirrors real-world data):
- Duplicate order/shipment IDs
- Null / missing customer names, addresses
- Inconsistent date formats
- Inconsistent region casing ("east", "East", "EAST")
- Negative or zero quantities (bad data)
- Trailing whitespace in text fields
"""

import csv
import random
import datetime
import os

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample")
for _d in ("orders", "shipments", "regional_sales"):
    os.makedirs(os.path.join(OUT_DIR, _d), exist_ok=True)
REGIONS = ["East", "West", "North", "South"]
REGION_CASING_VARIANTS = {
    "East": ["East", "east", "EAST", " East"],
    "West": ["West", "west", "WEST"],
    "North": ["North", "north", "North "],
    "South": ["South", "south", "SOUTH"],
}
CITIES = {
    "East": ["New York", "Boston", "Philadelphia"],
    "West": ["Los Angeles", "San Francisco", "Seattle"],
    "North": ["Chicago", "Minneapolis", "Detroit"],
    "South": ["Houston", "Dallas", "Atlanta"],
}
PRODUCTS = [
    ("SKU-1001", "Wireless Mouse", 19.99),
    ("SKU-1002", "Mechanical Keyboard", 79.99),
    ("SKU-1003", "USB-C Hub", 34.50),
    ("SKU-1004", "Laptop Stand", 45.00),
    ("SKU-1005", "Webcam 1080p", 59.99),
    ("SKU-1006", "Noise Cancelling Headphones", 149.99),
    ("SKU-1007", "Office Chair", 220.00),
    ("SKU-1008", "Standing Desk", 399.00),
]
FIRST_NAMES = ["James", "Maria", "Wei", "Fatima", "Liam", "Sofia", "Arjun", "Emma", "Noah", "Olga"]
LAST_NAMES = ["Smith", "Garcia", "Chen", "Khan", "Brown", "Rossi", "Patel", "Kim", "Novak", "Silva"]
CARRIERS = ["FedEx", "UPS", "DHL", "USPS"]
VEHICLE_IDS = [f"VH-{i:03d}" for i in range(1, 21)]

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]


def random_date(start_days_ago=180, end_days_ago=0):
    delta = random.randint(end_days_ago, start_days_ago)
    d = datetime.date.today() - datetime.timedelta(days=delta)
    fmt = random.choice(DATE_FORMATS)
    return d.strftime(fmt), d  # messy string version + real date object


def maybe_blank(value, blank_rate=0.05):
    return "" if random.random() < blank_rate else value


def messy_region(region):
    return random.choice(REGION_CASING_VARIANTS[region])


def gen_customers(n=300):
    customers = []
    for cid in range(1, n + 1):
        region = random.choice(REGIONS)
        city = random.choice(CITIES[region])
        customers.append({
            "customer_id": f"CUST-{cid:05d}",
            "name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "region": region,
            "city": city,
        })
    return customers


def gen_orders(customers, n=1000, dup_rate=0.03, bad_rate=0.04):
    orders = []
    order_id_counter = 1
    for _ in range(n):
        cust = random.choice(customers)
        order_date_str, order_date_real = random_date()
        sku, pname, price = random.choice(PRODUCTS)
        qty = random.randint(1, 5)

        # Inject bad data
        if random.random() < bad_rate:
            qty = random.choice([0, -1, -3])

        order_id = f"ORD-{order_id_counter:06d}"
        order_id_counter += 1

        row = {
            "order_id": order_id,
            "customer_id": cust["customer_id"],
            "customer_name": maybe_blank(cust["name"], 0.03),
            "region": messy_region(cust["region"]),
            "city": cust["city"],
            "order_date": order_date_str,
            "sku": sku,
            "product_name": pname,
            "quantity": qty,
            "unit_price": price,
            "order_total": round(qty * price, 2) if qty > 0 else round(qty * price, 2),
        }
        orders.append(row)

        # Inject duplicate rows (same order_id re-appears, simulating a re-export/failed dedup)
        if random.random() < dup_rate:
            orders.append(dict(row))  # exact duplicate

    random.shuffle(orders)
    return orders


def gen_shipments(orders, n_ratio=0.9, dup_rate=0.03):
    shipments = []
    ship_id_counter = 1
    sampled_orders = random.sample(orders, int(len(orders) * n_ratio))
    for o in sampled_orders:
        ship_date_str, ship_date_real = random_date(start_days_ago=170, end_days_ago=1)
        status = random.choices(
            ["Delivered", "In Transit", "Delayed", "Cancelled"],
            weights=[0.6, 0.2, 0.15, 0.05],
        )[0]
        row = {
            "shipment_id": f"SHIP-{ship_id_counter:06d}",
            "order_id": o["order_id"],
            "carrier": random.choice(CARRIERS),
            "vehicle_id": random.choice(VEHICLE_IDS),
            "ship_date": ship_date_str,
            "status": status,
            "region": messy_region(o["region"].strip().title() if o["region"].strip().title() in REGIONS else random.choice(REGIONS)),
            "delivery_days": maybe_blank(random.randint(1, 10), 0.05),
        }
        ship_id_counter += 1
        shipments.append(row)
        if random.random() < dup_rate:
            shipments.append(dict(row))

    random.shuffle(shipments)
    return shipments


def write_csv(rows, path, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def gen_regional_sales_csv(region, out_dir):
    """Simulates a manual weekly Excel-style export per region (kept as CSV here; convert to .xlsx if needed)."""
    rows = []
    for week in range(1, 13):
        week_date = datetime.date.today() - datetime.timedelta(weeks=(12 - week))
        rows.append({
            "region": messy_region(region),
            "week_ending": week_date.strftime(random.choice(DATE_FORMATS)),
            "total_orders": random.randint(50, 400),
            "total_revenue": round(random.uniform(5000, 50000), 2),
            "notes": maybe_blank(random.choice(["", "Promo week", "Holiday impact", "Normal"]), 0.5),
        })
    path = os.path.join(out_dir, "regional_sales", f"regional_sales_{region.lower()}.csv")
    write_csv(rows, path, ["region", "week_ending", "total_orders", "total_revenue", "notes"])


if __name__ == "__main__":
    customers = gen_customers(300)
    orders = gen_orders(customers, n=1000)
    shipments = gen_shipments(orders)

    write_csv(
        orders,
        os.path.join(OUT_DIR, "orders", "orders.csv"),
        ["order_id", "customer_id", "customer_name", "region", "city", "order_date",
         "sku", "product_name", "quantity", "unit_price", "order_total"],
    )
    write_csv(
        shipments,
        os.path.join(OUT_DIR, "shipments", "shipments.csv"),
        ["shipment_id", "order_id", "carrier", "vehicle_id", "ship_date", "status", "region", "delivery_days"],
    )
    for region in REGIONS:
        gen_regional_sales_csv(region, OUT_DIR)

    print(f"Generated {len(orders)} order rows (with duplicates/bad data injected)")
    print(f"Generated {len(shipments)} shipment rows")
    print("Generated regional sales files for:", REGIONS)
