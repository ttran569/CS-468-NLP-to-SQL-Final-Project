#!/usr/bin/env python3
import json
import os
import random
import re
import sqlite3
import subprocess
import threading
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
DB_PATH = ROOT / "business_insights.sqlite"
MODEL_NAME = "hf.co/rahul042/gemma_3_finetune:Q8_0"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
PORT = int(os.environ.get("PORT", "8765"))

SQL_SYSTEM_PROMPT = """
You generate SQLite SELECT queries for a business insights dashboard.
Return only SQL. Do not return markdown, explanation, comments, or JSON.
Use only the tables and columns listed here.

Schema:
stores(store_id, store_name, region, city, manager_name, store_tier, opened_on, monthly_recurring_revenue, employees, nps_score, churn_risk)
customers(customer_id, customer_name, store_id, segment, signup_date, lifetime_value, health_score, account_status)
products(product_id, product_name, category, price, unit_cost, supplier, active)
transactions(transaction_id, transaction_date, store_id, customer_id, product_id, channel, status, quantity, revenue, discount_percent, gross_margin)

Relationships:
customers.store_id = stores.store_id
transactions.store_id = stores.store_id
transactions.customer_id = customers.customer_id
transactions.product_id = products.product_id

Business vocabulary:
MRR means stores.monthly_recurring_revenue.
Revenue means transactions.revenue unless the user specifically asks for MRR.
Margin means transactions.gross_margin.
Churn risk means stores.churn_risk.
Only count transactions with status = 'Closed Won' when asking about won sales or realized revenue.

Rules:
Only produce one read-only SELECT statement.
Prefer clear column aliases for manager-facing results.
Do not add a LIMIT clause unless the user explicitly asks for a limited number of rows.
""".strip()


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stores (
            store_id INTEGER PRIMARY KEY,
            store_name TEXT NOT NULL,
            region TEXT NOT NULL,
            city TEXT NOT NULL,
            manager_name TEXT NOT NULL,
            store_tier TEXT NOT NULL,
            opened_on TEXT NOT NULL,
            monthly_recurring_revenue INTEGER NOT NULL,
            employees INTEGER NOT NULL,
            nps_score INTEGER NOT NULL,
            churn_risk TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            customer_name TEXT NOT NULL,
            store_id INTEGER NOT NULL,
            segment TEXT NOT NULL,
            signup_date TEXT NOT NULL,
            lifetime_value INTEGER NOT NULL,
            health_score INTEGER NOT NULL,
            account_status TEXT NOT NULL,
            FOREIGN KEY (store_id) REFERENCES stores(store_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price INTEGER NOT NULL,
            unit_cost INTEGER NOT NULL,
            supplier TEXT NOT NULL,
            active INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY,
            transaction_date TEXT NOT NULL,
            store_id INTEGER NOT NULL,
            customer_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            channel TEXT NOT NULL,
            status TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            revenue INTEGER NOT NULL,
            discount_percent INTEGER NOT NULL,
            gross_margin INTEGER NOT NULL,
            FOREIGN KEY (store_id) REFERENCES stores(store_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
        """
    )

    cur.execute("SELECT COUNT(*) AS count FROM stores")
    if cur.fetchone()["count"] >= 125:
        conn.close()
        return

    cur.executescript(
        """
        DELETE FROM transactions;
        DELETE FROM customers;
        DELETE FROM products;
        DELETE FROM stores;
        """
    )

    random.seed(42)
    regions = ["West", "South", "Midwest", "Northeast"]
    cities = [
        "Austin",
        "Denver",
        "Fresno",
        "Madison",
        "Nashville",
        "Phoenix",
        "Portland",
        "Raleigh",
        "Sacramento",
        "Tampa",
    ]
    first = ["Avery", "Jordan", "Taylor", "Morgan", "Riley", "Casey", "Jamie", "Drew"]
    last = ["Patel", "Kim", "Garcia", "Nguyen", "Johnson", "Singh", "Lopez", "Brown"]
    tiers = ["Flagship", "Growth", "Standard", "Emerging"]
    risks = ["Low", "Medium", "High"]
    today = date(2026, 5, 20)

    stores = []
    for store_id in range(1, 126):
        region = regions[(store_id - 1) % len(regions)]
        tier = random.choices(tiers, weights=[15, 30, 40, 15])[0]
        base_mrr = {"Flagship": 52000, "Growth": 36000, "Standard": 24000, "Emerging": 15500}[tier]
        mrr = max(6000, int(random.gauss(base_mrr, 7200)))
        nps = max(12, min(96, int(random.gauss(65 if mrr > 25000 else 52, 15))))
        risk = random.choices(risks, weights=[55, 32, 13] if mrr > 25000 else [25, 43, 32])[0]
        stores.append(
            (
                store_id,
                f"Store {store_id:03d}",
                region,
                random.choice(cities),
                f"{random.choice(first)} {random.choice(last)}",
                tier,
                str(today - timedelta(days=random.randint(120, 2400))),
                mrr,
                random.randint(8, 54),
                nps,
                risk,
            )
        )
    cur.executemany("INSERT INTO stores VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", stores)

    segments = ["Enterprise", "Mid-Market", "Small Business", "Consumer"]
    statuses = ["Active", "Watchlist", "Paused", "Churned"]
    customers = []
    for customer_id in range(1, 126):
        store_id = random.randint(1, 125)
        segment = random.choices(segments, weights=[14, 29, 37, 20])[0]
        ltv = int(random.gauss({"Enterprise": 19000, "Mid-Market": 9800, "Small Business": 4300, "Consumer": 950}[segment], 1600))
        health = max(8, min(100, int(random.gauss(71, 18))))
        status = random.choices(statuses, weights=[74, 14, 7, 5])[0]
        customers.append(
            (
                customer_id,
                f"{random.choice(['Northstar', 'Brightline', 'Summit', 'Harvest', 'Crescent', 'Pioneer'])} Account {customer_id:03d}",
                store_id,
                segment,
                str(today - timedelta(days=random.randint(15, 1300))),
                max(150, ltv),
                health,
                status,
            )
        )
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", customers)

    categories = ["Core SaaS", "Analytics", "Support", "Payments", "Inventory", "Training"]
    products = []
    for product_id in range(1, 126):
        category = random.choice(categories)
        price = random.randint(49, 999)
        unit_cost = max(8, int(price * random.uniform(0.18, 0.56)))
        products.append(
            (
                product_id,
                f"{category} Pack {product_id:03d}",
                category,
                price,
                unit_cost,
                random.choice(["Atlas Co", "Mercer Supply", "Union Works", "Kite Labs", "Fieldstone"]),
                1 if random.random() > 0.08 else 0,
            )
        )
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", products)

    product_lookup = {row[0]: row for row in products}
    transactions = []
    for transaction_id in range(1, 126):
        product_id = random.randint(1, 125)
        product = product_lookup[product_id]
        quantity = random.randint(1, 14)
        discount = random.choices([0, 5, 10, 15, 20, 25], weights=[40, 20, 16, 12, 8, 4])[0]
        revenue = int(product[3] * quantity * (1 - discount / 100))
        margin = revenue - product[4] * quantity
        transactions.append(
            (
                transaction_id,
                str(today - timedelta(days=random.randint(0, 364))),
                random.randint(1, 125),
                random.randint(1, 125),
                product_id,
                random.choice(["Retail", "Online", "Partner", "Inside Sales"]),
                random.choices(["Closed Won", "Refunded", "Open", "Canceled"], weights=[78, 5, 12, 5])[0],
                quantity,
                revenue,
                discount,
                margin,
            )
        )
    cur.executemany("INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", transactions)
    conn.commit()
    conn.close()


def table_schema():
    return {
        "stores": [
            "store_id",
            "store_name",
            "region",
            "city",
            "manager_name",
            "store_tier",
            "opened_on",
            "monthly_recurring_revenue",
            "employees",
            "nps_score",
            "churn_risk",
        ],
        "customers": [
            "customer_id",
            "customer_name",
            "store_id",
            "segment",
            "signup_date",
            "lifetime_value",
            "health_score",
            "account_status",
        ],
        "products": ["product_id", "product_name", "category", "price", "unit_cost", "supplier", "active"],
        "transactions": [
            "transaction_id",
            "transaction_date",
            "store_id",
            "customer_id",
            "product_id",
            "channel",
            "status",
            "quantity",
            "revenue",
            "discount_percent",
            "gross_margin",
        ],
    }


def run_sql(sql):
    cleaned = clean_sql(sql)
    conn = connect_db()
    try:
        rows = [dict(row) for row in conn.execute(cleaned).fetchall()]
    finally:
        conn.close()
    return cleaned, rows


def clean_sql(sql):
    sql = sql.strip().strip("`")
    sql = re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.IGNORECASE | re.MULTILINE).strip()
    sql = sql.rstrip(";")
    lowered = sql.lower()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")
    banned = [" insert ", " update ", " delete ", " drop ", " alter ", " create ", " attach ", " detach ", " pragma ", " vacuum "]
    padded = f" {lowered} "
    if any(word in padded for word in banned) or ";" in sql:
        raise ValueError("The generated query was blocked because it was not read-only.")
    return sql


def ollama_chat(question, temperature=0):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": temperature, "num_predict": 300},
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data.get("message", {}).get("content", "").strip()


def extract_model_payload(text, question):
    json_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if json_match:
        try:
            payload = json.loads(json_match.group(0))
            return {
                "summary": str(payload.get("summary") or f"I found the records that answer: {question}"),
                "sql": str(payload.get("sql") or ""),
            }
        except json.JSONDecodeError:
            pass
    sql_match = re.search(r"select\b.*", text, flags=re.IGNORECASE | re.DOTALL)
    return {
        "summary": f"I found the records that answer: {question}",
        "sql": sql_match.group(0).strip() if sql_match else text.strip(),
    }


def answer_question(question):
    raw = ollama_chat(question)
    model_payload = extract_model_payload(raw, question)
    sql, rows = run_sql(model_payload["sql"])
    summary = summarize_rows(question, rows)
    return {"summary": summary, "sql": sql, "rows": rows, "row_count": len(rows)}


def summarize_rows(question, rows):
    if not rows:
        return f"No records matched: {question}"
    if len(rows) == 1 and len(rows[0]) == 1:
        value = next(iter(rows[0].values()))
        return f"The answer is {value}."
    if len(rows) == 1:
        details = ", ".join(f"{key.replace('_', ' ')}: {value}" for key, value in rows[0].items())
        return f"Here is the matching business result: {details}."
    return f"I found {len(rows)} matching records for: {question}"


def pull_model():
    status = model_status()
    if status["installed"]:
        return {"ok": True, "installed": True, "output": "Model is already installed locally."}

    completed = subprocess.run(
        ["ollama", "pull", MODEL_NAME],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "installed": completed.returncode == 0,
        "output": (completed.stdout + completed.stderr).strip()[-4000:],
    }


def model_status():
    try:
        completed = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=15, check=False)
        output = completed.stdout + completed.stderr
        return {"ok": completed.returncode == 0, "installed": MODEL_NAME in output, "output": output}
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "installed": False, "output": str(exc)}


def warm_model():
    try:
        if model_status()["installed"]:
            ollama_chat("How many stores are in the database?")
    except Exception:
        pass


def metrics():
    conn = connect_db()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS store_count,
            SUM(monthly_recurring_revenue) AS total_mrr,
            AVG(monthly_recurring_revenue) AS avg_mrr,
            SUM(CASE WHEN monthly_recurring_revenue < 25000 THEN 1 ELSE 0 END) AS under_25k,
            AVG(nps_score) AS avg_nps
        FROM stores
        """
    ).fetchone()
    region_rows = [dict(r) for r in conn.execute(
        """
        SELECT region, SUM(monthly_recurring_revenue) AS mrr
        FROM stores
        GROUP BY region
        ORDER BY mrr DESC
        """
    )]
    product_rows = [dict(r) for r in conn.execute(
        """
        SELECT p.category, SUM(t.revenue) AS revenue
        FROM transactions t
        JOIN products p ON p.product_id = t.product_id
        WHERE t.status = 'Closed Won'
        GROUP BY p.category
        ORDER BY revenue DESC
        """
    )]
    risk_rows = [dict(r) for r in conn.execute(
        """
        SELECT churn_risk, COUNT(*) AS stores
        FROM stores
        GROUP BY churn_risk
        ORDER BY stores DESC
        """
    )]
    conn.close()
    return {
        "cards": dict(row),
        "regions": region_rows,
        "categories": product_rows,
        "risk": risk_rows,
    }


def sample_data():
    conn = connect_db()
    data = {
        "stores": [dict(r) for r in conn.execute("SELECT * FROM stores ORDER BY store_id LIMIT 8")],
        "transactions": [dict(r) for r in conn.execute("SELECT * FROM transactions ORDER BY transaction_date DESC LIMIT 8")],
    }
    conn.close()
    return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        return

    def send_json(self, payload, status=200):
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        if self.path == "/api/metrics":
            self.send_json(metrics())
        elif self.path == "/api/sample-data":
            self.send_json(sample_data())
        elif self.path == "/api/schema":
            self.send_json(table_schema())
        elif self.path == "/api/model-status":
            self.send_json(model_status())
        else:
            super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/query":
                body = self.read_json()
                question = (body.get("question") or "").strip()
                if not question:
                    self.send_json({"error": "Ask a business question first."}, status=400)
                    return
                self.send_json(answer_question(question))
            elif self.path == "/api/pull-model":
                self.send_json(pull_model())
            else:
                self.send_json({"error": "Not found"}, status=404)
        except urllib.error.URLError:
            self.send_json(
                {
                    "error": "Ollama is not reachable. Start Ollama locally, then pull the model from the dashboard.",
                    "model": MODEL_NAME,
                },
                status=503,
            )
        except subprocess.TimeoutExpired:
            self.send_json({"error": "Model pull timed out. Ollama may still be downloading in the background."}, status=504)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=500)


if __name__ == "__main__":
    init_db()
    threading.Thread(target=warm_model, daemon=True).start()
    print(f"Business Insights Dashboard running at http://localhost:{PORT}")
    print(f"Database: {DB_PATH}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
