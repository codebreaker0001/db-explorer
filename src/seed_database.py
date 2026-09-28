"""
Seed Database Script
====================
This creates a sample e-commerce SQLite database for testing.

It builds 5 tables with realistic fake data:
- customers: people who buy stuff
- products: things for sale
- orders: purchases made by customers
- order_items: which products are in each order
- categories: product categories

Run this once:  python seed_database.py
It creates:     sample.db (a SQLite file in this folder)
"""

import sqlite3
import random
from datetime import datetime, timedelta


def create_database():
    # Connect to SQLite (creates the file if it doesn't exist)
    conn = sqlite3.connect("sample.db")
    cursor = conn.cursor()

    print("Creating tables...")

    # ─ ─ ─ Table 1: categories ─ ─ ─
    # Simple lookup table for product categories
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)

    # ─ ─ ─ Table 2: customers ─ ─ ─
    # People who buy things from our store
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            city TEXT,
            country TEXT DEFAULT 'India',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ─── Table 3: products ───
    # Things for sale. Each product belongs to a category.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            price REAL NOT NULL,
            stock_quantity INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)

    # ─── Table 4: orders ───
    # A purchase made by a customer
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            order_date TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'pending',
            total_amount REAL DEFAULT 0,
            shipping_address TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # ─── Table 5: order_items ───
    # Which products are in each order (an order can have multiple items)
    # This is called a "junction table" or "many-to-many" table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    print("Inserting sample data...")

    # ─── Insert Categories ───
    categories = [
        ("Electronics", "Gadgets, phones, and accessories"),
        ("Clothing", "Shirts, pants, and fashion items"),
        ("Books", "Physical and digital books"),
        ("Home & Kitchen", "Furniture, appliances, and decor"),
        ("Sports", "Sports equipment and fitness gear"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)",
        categories,
    )

    # ─── Insert Customers ───
    first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun",
                   "Ananya", "Diya", "Priya", "Isha", "Kavya",
                   "Rahul", "Sneha", "Rohan", "Meera", "Amit"]
    last_names = ["Sharma", "Patel", "Singh", "Kumar", "Gupta",
                  "Reddy", "Joshi", "Verma", "Yadav", "Chopra"]
    cities = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
              "Pune", "Kolkata", "Jaipur", "Ahmedabad", "Lucknow"]

    customers = []
    for i in range(30):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        email = f"{fn.lower()}.{ln.lower()}{i}@email.com"
        city = random.choice(cities)
        days_ago = random.randint(30, 365)
        created = datetime.now() - timedelta(days=days_ago)
        customers.append((fn, ln, email, city, "India", created.isoformat()))

    cursor.executemany(
        "INSERT OR IGNORE INTO customers (first_name, last_name, email, city, country, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        customers,
    )

    # ─── Insert Products ───
    products = [
        # Electronics (category 1)
        ("Wireless Earbuds", 1, 2499.00, 150, 1),
        ("USB-C Charger", 1, 799.00, 300, 1),
        ("Bluetooth Speaker", 1, 3999.00, 75, 1),
        ("Phone Case", 1, 499.00, 500, 1),
        ("Power Bank 10000mAh", 1, 1299.00, 200, 1),
        ("Smartwatch", 1, 8999.00, 40, 1),
        # Clothing (category 2)
        ("Cotton T-Shirt", 2, 599.00, 400, 1),
        ("Denim Jeans", 2, 1899.00, 200, 1),
        ("Running Shoes", 2, 3499.00, 100, 1),
        ("Winter Jacket", 2, 4999.00, 50, 0),  # Out of season
        # Books (category 3)
        ("Python Programming", 3, 699.00, 80, 1),
        ("Data Science Handbook", 3, 899.00, 60, 1),
        ("The Alchemist", 3, 350.00, 120, 1),
        # Home & Kitchen (category 4)
        ("Coffee Mug Set", 4, 799.00, 90, 1),
        ("Table Lamp", 4, 1499.00, 45, 1),
        ("Yoga Mat", 5, 999.00, 70, 1),
        # Sports (category 5)
        ("Cricket Bat", 5, 2999.00, 30, 1),
        ("Football", 5, 899.00, 55, 1),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO products (name, category_id, price, stock_quantity, is_active) "
        "VALUES (?, ?, ?, ?, ?)",
        products,
    )

    # ─── Insert Orders and Order Items ───
    statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    status_weights = [0.1, 0.15, 0.2, 0.45, 0.1]  # Most orders are delivered

    for _ in range(80):
        customer_id = random.randint(1, 30)
        days_ago = random.randint(1, 180)
        order_date = datetime.now() - timedelta(days=days_ago)
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        city = random.choice(cities)

        cursor.execute(
            "INSERT INTO orders (customer_id, order_date, status, total_amount, shipping_address) "
            "VALUES (?, ?, ?, 0, ?)",
            (customer_id, order_date.isoformat(), status, f"{random.randint(1,999)}, Main Road, {city}"),
        )
        order_id = cursor.lastrowid

        # Add 1-4 items to each order
        num_items = random.randint(1, 4)
        total = 0
        used_products = set()

        for _ in range(num_items):
            product_id = random.randint(1, 18)
            if product_id in used_products:
                continue
            used_products.add(product_id)

            quantity = random.randint(1, 3)
            # Get product price
            cursor.execute("SELECT price FROM products WHERE id = ?", (product_id,))
            price = cursor.fetchone()[0]
            total += price * quantity

            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                "VALUES (?, ?, ?, ?)",
                (order_id, product_id, quantity, price),
            )

        # Update the order total
        cursor.execute(
            "UPDATE orders SET total_amount = ? WHERE id = ?",
            (round(total, 2), order_id),
        )

    conn.commit()

    # ─── Print Summary ───
    print("\nDatabase created! Here's what's inside:\n")
    for table in ["categories", "customers", "products", "orders", "order_items"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()
    print(f"\nSaved to: sample.db")
    print("You're ready to test the MCP server!")


if __name__ == "__main__":
    create_database()