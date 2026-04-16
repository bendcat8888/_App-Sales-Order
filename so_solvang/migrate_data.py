import pandas as pd
import sqlite3
import json
import ast
import re
import os
from db_manager import DatabaseManager, CartItem, Product, User, Account

def safe_parse_cart_items(cart_items_str):
    """Safely parse cart items string, handling nan values and other edge cases"""
    if not cart_items_str or pd.isna(cart_items_str) or cart_items_str == '':
        return []
    
    # If already a list, return as is
    if isinstance(cart_items_str, list):
        return cart_items_str
    
    # If it's not a string, try to convert
    if not isinstance(cart_items_str, str):
        try:
            return list(cart_items_str) if cart_items_str else []
        except (TypeError, ValueError):
            return []
    
    try:
        # First, try to parse directly
        cart_items = ast.literal_eval(cart_items_str)
    except (ValueError, SyntaxError):
        # If parsing fails, try replacing 'nan' strings with None
        try:
            # Replace 'nan' (as string) with None in the string representation
            cleaned_str = re.sub(r":\s*['\"]nan['\"]", ": None", cart_items_str, flags=re.IGNORECASE)
            # Also handle cases where nan appears without quotes (from pandas)
            cleaned_str = re.sub(r":\s*nan\b", ": None", cleaned_str, flags=re.IGNORECASE)
            cart_items = ast.literal_eval(cleaned_str)
        except (ValueError, SyntaxError):
            print(f"Failed to parse cart items: {cart_items_str[:50]}...")
            return []
            
    return cart_items

def migrate():
    print("Starting migration...")
    db = DatabaseManager()
    
    # 1. Products
    if os.path.exists('products.csv'):
        print("Migrating products...")
        try:
            df = pd.read_csv('products.csv')
            for _, row in df.iterrows():
                # Handle price with commas and quotes
                price_str = str(row.get('UnitPrice', 0)).replace(',', '').replace('"', '').replace("'", "")
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0

                # Handle stock quantity
                stock_str = str(row.get('StockQuantity', 0)).replace(',', '')
                try:
                    stock = int(float(stock_str))
                except ValueError:
                    stock = 0

                product = Product(
                    ProductCode=str(row.get('ProductCode', '')),
                    ProductName=str(row.get('ProductName', '')),
                    Description=str(row.get('Description', '')),
                    UnitPrice=price,
                    StockQuantity=stock,
                    Category=str(row.get('Category', '')),
                    Manufacturer=str(row.get('Manufacturer', ''))
                )
                db.upsert_product(product)
            print(f"Migrated {len(df)} products.")
        except Exception as e:
            print(f"Error migrating products: {e}")
    else:
        print("products.csv not found.")

    # 2. Users
    if os.path.exists('users.csv'):
        print("Migrating users...")
        try:
            df = pd.read_csv('users.csv')
            for _, row in df.iterrows():
                user = User(
                    username=str(row.get('Username', '')),
                    password=str(row.get('Password', '')),
                    role=str(row.get('Role', '')),
                    rep_code=str(row.get('RepCode', '')),
                    rep_name=str(row.get('RepName', '')),
                    rep_company=str(row.get('RepCompany', '')),
                    rep_dept=str(row.get('RepDept', '')),
                    rep_area=str(row.get('RepArea', '')),
                    registration_date=str(row.get('RegistrationDate', ''))
                )
                db.upsert_user(user)
            print(f"Migrated {len(df)} users.")
        except Exception as e:
            print(f"Error migrating users: {e}")
    else:
        print("users.csv not found.")

    # 3. Accounts
    if os.path.exists('sales_order_LIST_OF_ACCOUNTS.csv'):
        print("Migrating accounts...")
        try:
            # Try reading with different encodings
            try:
                df = pd.read_csv('sales_order_LIST_OF_ACCOUNTS.csv', encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv('sales_order_LIST_OF_ACCOUNTS.csv', encoding='cp1252')
            
            db.save_accounts_df(df)
            print(f"Migrated {len(df)} accounts.")
        except Exception as e:
            print(f"Error migrating accounts: {e}")
    else:
        print("sales_order_LIST_OF_ACCOUNTS.csv not found.")

    # 4. Orders
    if os.path.exists('orders.csv'):
        print("Migrating orders...")
        try:
            df = pd.read_csv('orders.csv')
            count = 0
            for _, row in df.iterrows():
                # Prepare Order data
                order_data = row.to_dict()
                
                # Parse CartItems
                cart_items_raw = safe_parse_cart_items(row.get('CartItems', '[]'))
                cart_items = []
                for item in cart_items_raw:
                    try:
                        # Handle row_data if it exists
                        row_data = item.get('row_data', {})
                        if isinstance(row_data, str):
                            try:
                                row_data = json.loads(row_data)
                            except:
                                pass # Keep as is or empty dict
                        
                        cart_item = CartItem(
                            product_code=str(item.get('product_code', '')),
                            product_name=str(item.get('product_name', '')),
                            qty=int(float(item.get('qty', 0))),
                            price=float(item.get('price', 0)),
                            row_data=row_data if isinstance(row_data, dict) else {}
                        )
                        cart_items.append(cart_item)
                    except Exception as e:
                        print(f"Error parsing item in order {row.get('OrderID')}: {e}")
                
                db.save_order(order_data, cart_items)
                count += 1
            print(f"Migrated {count} orders.")
        except Exception as e:
            print(f"Error migrating orders: {e}")
    else:
        print("orders.csv not found.")

    print("Migration completed.")

if __name__ == "__main__":
    migrate()
