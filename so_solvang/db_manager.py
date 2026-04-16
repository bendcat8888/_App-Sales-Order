import sqlite3
import json
import logging
import ast
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
import pandas as pd
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = "sales_order_inventory.db"


def _get_db_path(db_name: str = DB_NAME) -> str:
    """Return absolute path to DB file (ensures same DB used regardless of CWD)."""
    if os.path.isabs(db_name):
        return db_name
    _dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(_dir, db_name)


# --- Pydantic Models ---

class CartItem(BaseModel):
    product_code: str
    product_name: str
    qty: int
    price: float
    notes_remarks: Optional[str] = ""
    row_data: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def total(self) -> float:
        return self.qty * self.price

class Product(BaseModel):
    product_code: str = Field(alias='ProductCode')
    product_name: str = Field(alias='ProductName')
    description: Optional[str] = Field(default=None, alias='Description')
    unit_price: float = Field(default=0.0, alias='UnitPrice')
    stock_quantity: int = Field(default=0, alias='StockQuantity')
    category: Optional[str] = Field(default=None, alias='Category')
    manufacturer: Optional[str] = Field(default=None, alias='Manufacturer')

class User(BaseModel):
    username: str
    password: str
    role: str
    rep_code: Optional[str] = None
    rep_name: Optional[str] = None
    rep_company: Optional[str] = None
    rep_dept: Optional[str] = None
    rep_area: Optional[str] = None
    registration_date: Optional[str] = None
    account_type: Optional[str] = "Dispensing"  # "Dispensing" or "admin"
    email: Optional[str] = None

class Account(BaseModel):
    customer_code: str
    customer_name: str
    lvl1_short_name: Optional[str] = None
    lvl2_short_name: Optional[str] = None
    lvl3_short_name: Optional[str] = None
    credit_term: Optional[str] = None
    class_code: Optional[str] = None
    channel_code: Optional[str] = None
    br_name: Optional[str] = None
    business_address: Optional[str] = None
    contact_number1: Optional[str] = None
    tin: Optional[str] = None
    contact_person1: Optional[str] = None
    active: str = 'TRUE'
    area: Optional[str] = ''
    sgf: str = 'FALSE'
    sgf_count: int = 99

class Order(BaseModel):
    order_id: str
    order_date: str
    status: str
    client_name: str
    total_amount: float
    items: List[CartItem] = []
    # Add other fields as needed for the UI, but this is a base structure

# --- Database Manager ---

class DatabaseManager:
    def __init__(self, db_name: str = None):
        self.db_name = _get_db_path(db_name or DB_NAME)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Products Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_code TEXT PRIMARY KEY,
            product_name TEXT,
            description TEXT,
            unit_price REAL,
            stock_quantity INTEGER,
            category TEXT,
            manufacturer TEXT
        )
        ''')
        
        # Users Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            role TEXT,
            rep_code TEXT,
            rep_name TEXT,
            rep_company TEXT,
            rep_dept TEXT,
            rep_area TEXT,
            registration_date TEXT,
            account_type TEXT DEFAULT 'Dispensing',
            email TEXT
        )
        ''')
        # Migration: add account_type column if missing (existing DBs)
        try:
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'account_type' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN account_type TEXT DEFAULT 'Dispensing'")
                # Backfill: set account_type='admin' for admin/finance/SGF users
                cursor.execute("""
                    UPDATE users SET account_type = 'admin' 
                    WHERE role IN ('Admin', 'Admin / Finance Staff', 'Finance Staff', 'SGF Manager',
                                   'Admin Level 0', 'Admin Level 1', 'Admin Level 2', 'Finance Staff Level 1', 'Finance Staff Level 2')
                """)
                # Set 'Dispensing' for any remaining null/empty
                cursor.execute("UPDATE users SET account_type = 'Dispensing' WHERE account_type IS NULL OR account_type = ''")
        except Exception as e:
            logger.warning(f"Migration for account_type: {e}")
        
        # Migration: add email column if missing (existing DBs)
        try:
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'email' not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except Exception as e:
            logger.warning(f"Migration for email: {e}")

        # Migration: migrate usernames to new role-based roles (one-time; do not overwrite Finance1/Ethical1 - preserve admin edits)
        try:
            cursor.execute("UPDATE users SET role = 'Admin Level 0' WHERE username = 'administrator' AND role IN ('Finance Staff', 'Admin', 'Admin / Finance Staff')")
            cursor.execute("UPDATE users SET role = 'Admin Level 1' WHERE username = 'Admin1'")
            cursor.execute("UPDATE users SET role = 'Admin Level 2' WHERE username = 'Admin2'")
            cursor.execute("UPDATE users SET role = 'Finance Staff Level 2' WHERE username = 'Finance2'")
            # Removed: Finance1 role reset - was overwriting admin edits on every startup
            cursor.execute("UPDATE users SET role = 'Admin Level 1 Ethical' WHERE role = 'Admin Ethical Level 1'")
            conn.commit()
        except Exception as e:
            logger.warning(f"Migration for role-based roles: {e}")

        # Migration: rename finance1 -> Finance1 so it persists on every reload (e.g. on server)
        try:
            cursor.execute("SELECT 1 FROM users WHERE username = 'finance1' LIMIT 1")
            if cursor.fetchone():
                cursor.execute("SELECT 1 FROM users WHERE username = 'Finance1' LIMIT 1")
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO users (username, password, role, rep_code, rep_name, rep_company, rep_dept, rep_area, registration_date, account_type)
                        SELECT 'Finance1', password, 'Finance Staff Level 1', rep_code, rep_name, rep_company, rep_dept, rep_area, registration_date, COALESCE(account_type, 'admin')
                        FROM users WHERE username = 'finance1'
                    """)
                cursor.execute("DELETE FROM users WHERE username = 'finance1'")
                conn.commit()
                logger.info("Migration: renamed finance1 -> Finance1")
        except Exception as e:
            logger.warning(f"Migration finance1 -> Finance1: {e}")

        # Accounts Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            customer_code TEXT PRIMARY KEY,
            customer_name TEXT,
            lvl1_short_name TEXT,
            lvl2_short_name TEXT,
            lvl3_short_name TEXT,
            credit_term TEXT,
            class_code TEXT,
            channel_code TEXT,
            br_name TEXT,
            business_address TEXT,
            contact_number1 TEXT,
            tin TEXT,
            contact_person1 TEXT,
            active TEXT,
            area TEXT,
            sgf TEXT,
            sgf_count INTEGER,
            tsr_tag TEXT,
            pmr_tag TEXT,
            dsmbu7_tag TEXT,
            dsmpsi_tag TEXT,
            account_type TEXT DEFAULT 'Dispensing'
        )
        ''')
        # Migration: add tagging and account_type columns if missing (existing DBs)
        try:
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [col[1] for col in cursor.fetchall()]
            for col_name, default_sql in [
                ('tsr_tag', ''), ('pmr_tag', ''), ('dsmbu7_tag', ''), ('dsmpsi_tag', ''),
                ('account_type', "DEFAULT 'Dispensing'")
            ]:
                if col_name not in columns:
                    stmt = f"ALTER TABLE accounts ADD COLUMN {col_name} TEXT {default_sql}".strip()
                    cursor.execute(stmt)
            cursor.execute("UPDATE accounts SET account_type = 'Dispensing' WHERE account_type IS NULL OR account_type = ''")
        except Exception as e:
            logger.warning(f"Migration for accounts tagging columns: {e}")
        
        # Orders Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            order_date TEXT,
            status TEXT,
            client_name TEXT,
            client_description TEXT,
            client_mobile TEXT,
            billing_address TEXT,
            shipping_address TEXT,
            payment_terms TEXT,
            delivery_terms TEXT,
            delivery_date TEXT,
            notes TEXT,
            rep_code TEXT,
            rep_name TEXT,
            rep_company TEXT,
            rep_dept TEXT,
            rep_area TEXT,
            remarks TEXT,
            total_amount REAL,
            created_by TEXT,
            reviewed_by TEXT,
            reviewed_date TEXT,
            discount_percent REAL,
            discount_amount REAL,
            subtotal REAL,
            printed TEXT,
            printed_date TEXT,
            printed_time TEXT,
            approved_by_level1 TEXT,
            approved_date_level1 TEXT,
            approved_by_level2 TEXT,
            approved_date_level2 TEXT,
            approved_by_sgf TEXT,
            approved_date_sgf TEXT,
            contact_person1 TEXT,
            contact_person1_mobile TEXT,
            contact_person2 TEXT,
            contact_person2_mobile TEXT,
            attachments TEXT,
            disapproved_items TEXT,
            tsr_tag TEXT,
            pmr_tag TEXT,
            dsmbu7_tag TEXT,
            dsmpsi_tag TEXT
        )
        ''')
        # Migration: add tag columns to orders if missing
        try:
            cursor.execute("PRAGMA table_info(orders)")
            ord_cols = [col[1] for col in cursor.fetchall()]
            for tag_col in ('tsr_tag', 'pmr_tag', 'dsmbu7_tag', 'dsmpsi_tag'):
                if tag_col not in ord_cols:
                    cursor.execute(f"ALTER TABLE orders ADD COLUMN {tag_col} TEXT")
        except Exception as e:
            logger.warning(f"Migration for orders tag columns: {e}")
        # Migration: add booking request linkage columns to orders if missing
        try:
            cursor.execute("PRAGMA table_info(orders)")
            ord_cols = [col[1] for col in cursor.fetchall()]
            for br_col in ('br_created_by', 'booking_request_id'):
                if br_col not in ord_cols:
                    cursor.execute(f"ALTER TABLE orders ADD COLUMN {br_col} TEXT")
        except Exception as e:
            logger.warning(f"Migration for orders br_created_by/booking_request_id: {e}")
        
        # Order Items Table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            product_code TEXT,
            product_name TEXT,
            quantity INTEGER,
            price REAL,
            row_data TEXT,
            notes_remarks TEXT,
            FOREIGN KEY(order_id) REFERENCES orders(order_id)
        )
        ''')
        # Migration: add notes_remarks to order_items if missing (existing DBs)
        try:
            cursor.execute("PRAGMA table_info(order_items)")
            oi_cols = [col[1] for col in cursor.fetchall()]
            if 'notes_remarks' not in oi_cols:
                cursor.execute("ALTER TABLE order_items ADD COLUMN notes_remarks TEXT")
                conn.commit()
        except Exception as e:
            logger.warning(f"Migration for order_items notes_remarks: {e}")
        
        # Booking Request Table (TRADE Special Flow - Med Rep requests TSR to complete)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS booking_request (
            request_id TEXT PRIMARY KEY,
            tsr_code TEXT,
            tsr_name TEXT,
            client_name TEXT,
            shipping_date TEXT,
            special_instructions TEXT,
            remarks TEXT,
            cart_items TEXT,
            created_by TEXT,
            created_date TEXT,
            status TEXT DEFAULT 'Pending',
            order_id TEXT,
            auto_cancel_date TEXT
        )
        ''')
        # Migration: add auto_cancel_date if missing (existing DBs)
        try:
            cursor.execute("PRAGMA table_info(booking_request)")
            br_cols = [col[1] for col in cursor.fetchall()]
            if 'auto_cancel_date' not in br_cols:
                cursor.execute("ALTER TABLE booking_request ADD COLUMN auto_cancel_date TEXT")
                conn.commit()
        except Exception as e:
            logger.warning(f"Migration for booking_request auto_cancel_date: {e}")
        # Migration: add cancel_reason for Cancelled by Creator (and other cancellations)
        try:
            cursor.execute("PRAGMA table_info(booking_request)")
            br_cols = [col[1] for col in cursor.fetchall()]
            if 'cancel_reason' not in br_cols:
                cursor.execute("ALTER TABLE booking_request ADD COLUMN cancel_reason TEXT")
                conn.commit()
        except Exception as e:
            logger.warning(f"Migration for booking_request cancel_reason: {e}")
        
        # Notification Log (for Super Admin - send status tracking)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            notification_type TEXT,
            recipient_type TEXT,
            recipient_id TEXT,
            order_id TEXT,
            request_id TEXT,
            status TEXT,
            message TEXT,
            error_message TEXT
        )
        ''')
        
        # Notification Sent Tracking (to avoid duplicate sends, track last sent time)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_sent_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT,
            entity_id TEXT,
            notification_type TEXT,
            sent_at TEXT,
            UNIQUE(entity_type, entity_id, notification_type)
        )
        ''')
        
        # Notification CC List (editable in Super Admin - Email Notification Management)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_cc_email (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            notify_booking INTEGER DEFAULT 1,
            notify_submission_approval INTEGER DEFAULT 1,
            notify_fully_approved INTEGER DEFAULT 1,
            notify_disapproved INTEGER DEFAULT 0,
            notify_overdue INTEGER DEFAULT 0,
            notify_autocancel INTEGER DEFAULT 0
        )
        ''')
        # Migration: add trigger columns if missing
        try:
            cursor.execute("PRAGMA table_info(notification_cc_email)")
            cc_cols = [col[1] for col in cursor.fetchall()]
            
            # Map of column names to their new default values
            new_cc_cols_defaults = {
                'notify_booking': 1,
                'notify_submission_approval': 1,
                'notify_fully_approved': 1,
                'notify_disapproved': 0,
                'notify_overdue': 0,
                'notify_autocancel': 0
            }
            
            for col, default_val in new_cc_cols_defaults.items():
                if col not in cc_cols:
                    cursor.execute(f"ALTER TABLE notification_cc_email ADD COLUMN {col} INTEGER DEFAULT {default_val}")
            conn.commit()
        except Exception as e:
            logger.warning(f"Migration for notification_cc_email: {e}")
        
        # SO History Table (from ETHICAL consolidated CSV - sales order history)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS so_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area TEXT,
            address TEXT,
            class_code TEXT,
            customer_code TEXT,
            customer_name TEXT,
            notes_remarks TEXT,
            sales_unit REAL,
            free_goods REAL,
            discount REAL,
            district TEXT,
            district_manager TEXT,
            dsmbu7_code TEXT,
            dsmpsi TEXT,
            dsmpsi_code TEXT,
            gross_sales REAL,
            remarks TEXT,
            rep_code TEXT,
            rep_name TEXT,
            sales_discount REAL,
            scr TEXT,
            sku_name TEXT,
            terms TEXT,
            tsr TEXT,
            tsr_code TEXT,
            source_sheet TEXT,
            full_date TEXT,
            month INTEGER,
            year INTEGER
        )
        ''')
        # Migration: convert decimal values in notes_remarks to percentage strings (0.2 -> "20%")
        try:
            cursor.execute("SELECT id, notes_remarks FROM so_history WHERE notes_remarks IS NOT NULL AND notes_remarks != ''")
            for row in cursor.fetchall():
                rid, nr = row[0], row[1]
                new_val = DatabaseManager._notes_remarks_to_percent_str(nr)
                if new_val is not None and new_val != nr:
                    cursor.execute("UPDATE so_history SET notes_remarks = ? WHERE id = ?", (new_val, rid))
        except Exception as e:
            logger.warning(f"Migration for so_history notes_remarks: {e}")
        
        conn.commit()
        conn.close()
        
        # Initialize default users if database is empty
        self.init_default_users()
        # Initialize default CC emails if table is empty
        self.init_default_cc_emails()
        # Update user emails from mapping (location/area -> email)
        self.init_user_emails_from_mapping()

    def init_user_emails_from_mapping(self):
        """Update user emails based on location/username mapping."""
        email_mapping = {
            'northluzon': 'roseann.paningbatan1525@gmail.com',
            'netarau': 'mendozaabigail2098@gmail.com',
            'bulacan': 'Leleydelossantos@gmail.com',
            'qc2': 'abellamariaestefhane@gmail.com',
            'qc1': 'fajardoalbert14@gmail.com',
            'Southluzon': 'eloisaandreapaule@gmail.com',
            'marizanti': 'cheriflores03@gmail.com',
            'makati': 'jmtanare@gmail.com',
            'cavite': 'iza.anayiotou@gmail.com',
            'laguna': 'erroljaybombales@gmail.com',
        }
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for username, email in email_mapping.items():
                cursor.execute(
                    "UPDATE users SET email = ? WHERE LOWER(username) = LOWER(?)",
                    (email, str(username).strip())
                )
            conn.commit()
        except Exception as e:
            logger.warning(f"init_user_emails_from_mapping: {e}")
            conn.rollback()
        finally:
            conn.close()

    def init_default_cc_emails(self):
        """Seed default CC emails if notification_cc_email table is empty."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM notification_cc_email")
            if cursor.fetchone()[0] == 0:
                defaults = [
                    ('subscription@innogen-pharma.com', 0),
                    ('irish.finianos@solvang-pharma.com', 1),
                    ('rhioirishfinianos@gmail.com', 2),
                    ('merin.ediline@innogen-pharma.ph', 3),
                    ('jsr.solvangpharma@gmail.com', 4),
                ]
                cursor.executemany(
                    "INSERT OR IGNORE INTO notification_cc_email (email, display_order) VALUES (?, ?)",
                    defaults
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"init_default_cc_emails: {e}")
        finally:
            conn.close()

    def get_cc_emails(self, trigger_category: str = None) -> List[str]:
        """Get CC email list from database, optionally filtered by trigger category."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if trigger_category:
                # Map trigger categories to column names
                category_map = {
                    'booking': 'notify_booking',
                    'submission_approval': 'notify_submission_approval',
                    'fully_approved': 'notify_fully_approved',
                    'disapproved': 'notify_disapproved',
                    'overdue': 'notify_overdue',
                    'autocancel': 'notify_autocancel'
                }
                col = category_map.get(trigger_category)
                if col:
                    cursor.execute(f"SELECT email FROM notification_cc_email WHERE {col} = 1 ORDER BY display_order, id")
                else:
                    cursor.execute("SELECT email FROM notification_cc_email ORDER BY display_order, id")
            else:
                cursor.execute("SELECT email FROM notification_cc_email ORDER BY display_order, id")
            return [row[0] for row in cursor.fetchall() if row[0] and str(row[0]).strip()]
        except Exception as e:
            logger.warning(f"get_cc_emails: {e}")
            return []
        finally:
            conn.close()

    def get_cc_emails_df(self) -> pd.DataFrame:
        """Get CC emails as DataFrame for data_editor."""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM notification_cc_email ORDER BY display_order, id",
                conn
            )
            return df
        except Exception as e:
            logger.warning(f"get_cc_emails_df: {e}")
            return pd.DataFrame(columns=[
                'id', 'email', 'display_order', 'notify_booking', 
                'notify_submission_approval', 'notify_fully_approved', 
                'notify_disapproved', 'notify_overdue', 'notify_autocancel'
            ])
        finally:
            conn.close()

    def save_cc_emails(self, df: pd.DataFrame) -> bool:
        """Replace CC emails with contents of dataframe."""
        if df.empty or 'email' not in df.columns:
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM notification_cc_email")
            seen = set()
            for i, row in df.iterrows():
                email = str(row.get('email', '')).strip()
                if email and email.lower() not in seen:
                    seen.add(email.lower())
                    display_order = int(row.get('display_order', i)) if pd.notna(row.get('display_order')) else i
                    
                    # Get checkbox values (handle missing columns by defaulting based on requirements)
                    n_booking = int(row.get('notify_booking', 1))
                    n_sub_app = int(row.get('notify_submission_approval', 1))
                    n_fully = int(row.get('notify_fully_approved', 1))
                    n_dis = int(row.get('notify_disapproved', 0))
                    n_overdue = int(row.get('notify_overdue', 0))
                    n_auto = int(row.get('notify_autocancel', 0))

                    cursor.execute('''
                        INSERT INTO notification_cc_email (
                            email, display_order, notify_booking, 
                            notify_submission_approval, notify_fully_approved, 
                            notify_disapproved, notify_overdue, notify_autocancel
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (email, display_order, n_booking, n_sub_app, n_fully, n_dis, n_overdue, n_auto))
            conn.commit()
            return True
        except Exception as e:
            logger.warning(f"save_cc_emails: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def init_default_users(self):
        """Initialize default users only if they don't exist. Preserves existing users' email/password/role changes."""
        admin_roles = ('Admin Level 0', 'Admin Level 1', 'Admin Level 2', 'Finance Staff Level 1', 'Finance Staff Level 2', 'SGF Manager')
        default_users = {
            'administrator': {'password': 'P@ssw0rd123', 'role': 'Admin Level 0', 'rep_code': None, 'rep_name': 'Super Administrator',
                             'rep_company': None, 'rep_dept': 'Finance', 'rep_area': None, 'account_type': 'admin'},
            'Ethical1': {'password': 'Admin1', 'role': 'Admin Level 1', 'rep_code': None, 'rep_name': 'Admin Level 1 Ethical',
                         'rep_company': None, 'rep_dept': 'Finance', 'rep_area': None, 'account_type': 'admin'},
            'Finance1': {'password': 'Admin2', 'role': 'Admin Level 2', 'rep_code': None, 'rep_name': 'Finance Staff Level 1 Viewer',
                         'rep_company': None, 'rep_dept': 'Finance', 'rep_area': None, 'account_type': 'admin'},
            'Finance2': {'password': 'fin123', 'role': 'Finance Staff Level 2', 'rep_code': None, 'rep_name': 'Finance Staff Level 2 Viewer',
                        'rep_company': None, 'rep_dept': 'Finance', 'rep_area': None, 'account_type': 'admin'},
            'SGF': {'password': 'SGF123', 'role': 'SGF Manager', 'rep_code': None, 'rep_name': 'SGF Manager',
                    'rep_company': None, 'rep_dept': 'Finance', 'rep_area': None, 'account_type': 'admin'},
        }
        existing_usernames = set(self.get_all_users().keys())
        for username, data in default_users.items():
            if username in existing_usernames:
                continue  # Skip - preserve existing user (email, password, role changes)
            account_type = data.get('account_type', 'admin' if data.get('role') in admin_roles else 'Dispensing')
            user = User(
                username=username,
                password=data.get('password', ''),
                role=data.get('role', ''),
                rep_code=str(data.get('rep_code') or ''),
                rep_name=str(data.get('rep_name') or ''),
                rep_company=str(data.get('rep_company') or ''),
                rep_dept=str(data.get('rep_dept') or ''),
                rep_area=str(data.get('rep_area') or ''),
                registration_date=datetime.now().strftime("%Y-%m-%d"),
                account_type=account_type or 'Dispensing'
            )
            self.upsert_user(user)

    # --- CRUD Operations ---

    # Products
    def get_all_products(self) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM products", conn)
            # Rename columns to match what the app expects (PascalCase)
            df = df.rename(columns={
                'product_code': 'ProductCode',
                'product_name': 'ProductName',
                'description': 'Description',
                'unit_price': 'UnitPrice',
                'stock_quantity': 'StockQuantity',
                'category': 'Category',
                'manufacturer': 'Manufacturer'
            })
            return df
        finally:
            conn.close()

    def upsert_product(self, product: Product):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO products (product_code, product_name, description, unit_price, stock_quantity, category, manufacturer)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_code) DO UPDATE SET
                product_name=excluded.product_name,
                description=excluded.description,
                unit_price=excluded.unit_price,
                stock_quantity=excluded.stock_quantity,
                category=excluded.category,
                manufacturer=excluded.manufacturer
            ''', (
                product.product_code,
                product.product_name,
                product.description,
                product.unit_price,
                product.stock_quantity,
                product.category,
                product.manufacturer
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error upserting product: {e}")
            return False
        finally:
            conn.close()
            
    def delete_product(self, product_code: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM products WHERE product_code = ?", (product_code,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting product: {e}")
            return False
        finally:
            conn.close()

    # Users
    def get_all_users(self) -> Dict[str, Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            users_dict = {}
            for row in rows:
                users_dict[row['username']] = {
                    'password': row['password'],
                    'role': row['role'],
                    'rep_code': row['rep_code'],
                    'rep_name': row['rep_name'],
                    'rep_company': row['rep_company'],
                    'rep_dept': row['rep_dept'],
                    'rep_area': row['rep_area'],
                    'registration_date': row['registration_date'],
                    'account_type': row['account_type'] if 'account_type' in row.keys() and row['account_type'] else 'Dispensing',
                    'email': row['email'] if 'email' in row.keys() else None
                }
            return users_dict
        finally:
            conn.close()
            
    def get_all_users_df(self) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM users", conn)
            # Rename columns to match what the app expects
            df = df.rename(columns={
                'username': 'Username',
                'password': 'Password',
                'role': 'Role',
                'rep_code': 'RepCode',
                'rep_name': 'RepName',
                'rep_company': 'RepCompany',
                'rep_dept': 'RepDept',
                'rep_area': 'RepArea',
                'registration_date': 'RegistrationDate',
                'account_type': 'AccountType',
                'email': 'Email'
            })
            return df
        finally:
            conn.close()

    def upsert_user(self, user: User):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            account_type = (user.account_type or 'Dispensing').strip() or 'Dispensing'
            cursor.execute('''
            INSERT INTO users (username, password, role, rep_code, rep_name, rep_company, rep_dept, rep_area, registration_date, account_type, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password=excluded.password,
                role=excluded.role,
                rep_code=excluded.rep_code,
                rep_name=excluded.rep_name,
                rep_company=excluded.rep_company,
                rep_dept=excluded.rep_dept,
                rep_area=excluded.rep_area,
                registration_date=excluded.registration_date,
                account_type=excluded.account_type,
                email=excluded.email
            ''', (
                user.username,
                user.password,
                user.role,
                user.rep_code,
                user.rep_name,
                user.rep_company,
                user.rep_dept,
                user.rep_area,
                user.registration_date,
                account_type,
                user.email or ''
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error upserting user: {e}")
            return False
        finally:
            conn.close()
            
    def upsert_user_bulk_overwrite(self, user: User) -> bool:
        """
        Upsert for bulk upload: overwrite existing row when Username OR RepCode matches.
        - If username exists: overwrite that row
        - Else if rep_code exists (and non-empty): delete old user, insert new (handles username change)
        - Else: insert new user
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            account_type = (user.account_type or 'Dispensing').strip() or 'Dispensing'
            # Check if username exists
            cursor.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?)", (user.username,))
            if cursor.fetchone():
                # Overwrite by username
                cursor.execute('''
                UPDATE users SET password=?, role=?, rep_code=?, rep_name=?, rep_company=?,
                    rep_dept=?, rep_area=?, registration_date=?, account_type=?, email=?
                WHERE LOWER(username) = LOWER(?)
                ''', (
                    user.password, user.role, user.rep_code or '', user.rep_name or '',
                    user.rep_company or '', user.rep_dept or '', user.rep_area or '',
                    user.registration_date or '', account_type, user.email or '',
                    user.username
                ))
                conn.commit()
                return True
            # Check if rep_code exists (and non-empty) - user may have been renamed
            if user.rep_code and str(user.rep_code).strip():
                cursor.execute("SELECT username FROM users WHERE rep_code = ?", (user.rep_code.strip(),))
                row = cursor.fetchone()
                if row:
                    old_username = row[0]
                    cursor.execute("DELETE FROM users WHERE username = ?", (old_username,))
            # Insert new user
            cursor.execute('''
            INSERT INTO users (username, password, role, rep_code, rep_name, rep_company, rep_dept, rep_area, registration_date, account_type, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user.username, user.password, user.role, user.rep_code or '',
                user.rep_name or '', user.rep_company or '', user.rep_dept or '',
                user.rep_area or '', user.registration_date or '', account_type,
                user.email or ''
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error bulk upserting user: {e}")
            return False
        finally:
            conn.close()

    def delete_user(self, username: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False
        finally:
            conn.close()

    def update_user_email(self, username: str, email: str) -> bool:
        """Update email for a user by username. Username match is case-insensitive."""
        if not username or not str(username).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET email = ? WHERE LOWER(username) = LOWER(?)",
                (str(email).strip() if email else '', str(username).strip())
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user email: {e}")
            return False
        finally:
            conn.close()

    # Booking Requests (TRADE Special Flow)
    def create_booking_request(self, request_id: str, tsr_code: str, tsr_name: str, client_name: str,
                               shipping_date: str, special_instructions: str, remarks: str,
                               cart_items: str, created_by: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO booking_request (request_id, tsr_code, tsr_name, client_name, shipping_date,
                special_instructions, remarks, cart_items, created_by, created_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
            ''', (request_id, tsr_code, tsr_name, client_name, shipping_date,
                  special_instructions, remarks, cart_items, created_by,
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating booking request: {e}")
            return False
        finally:
            conn.close()

    def get_booking_requests_by_tsr_code(self, tsr_code: str) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM booking_request WHERE tsr_code = ? AND status = 'Pending' ORDER BY created_date DESC",
                conn, params=(tsr_code,)
            )
            return df
        finally:
            conn.close()

    def get_booking_requests_by_tsr_code_all(self, tsr_code: str) -> pd.DataFrame:
        """Get all booking requests for TSR (Pending, Completed, Auto-Cancel) for History view."""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM booking_request WHERE tsr_code = ? ORDER BY created_date DESC",
                conn, params=(tsr_code,)
            )
            return df
        finally:
            conn.close()

    def get_booking_requests_by_created_by(self, created_by: str) -> pd.DataFrame:
        """Get all booking requests created by a user (e.g., Sales Rep) for Request/Order History."""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM booking_request WHERE created_by = ? ORDER BY created_date DESC",
                conn, params=(created_by,)
            )
            return df
        finally:
            conn.close()

    def get_booking_requests_auto_cancel_for_user(self, rep_code: str, username: str) -> pd.DataFrame:
        """Get Auto-Cancel and Cancelled-by-Creator booking requests: TSR sees those assigned to them; creator sees those they created."""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                """SELECT * FROM booking_request 
                   WHERE (status = 'Auto-Cancel' AND (tsr_code = ? OR created_by = ?)) 
                      OR (status = 'Cancelled by Creator' AND (tsr_code = ? OR created_by = ?))
                   ORDER BY COALESCE(auto_cancel_date, created_date) DESC""",
                conn, params=(rep_code or '', username or '', rep_code or '', username or '')
            )
            return df
        finally:
            conn.close()

    def get_auto_cancel_count_for_tsr(self, rep_code: str) -> int:
        """Count Auto-Cancel booking requests assigned to this TSR (for counter badge)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM booking_request WHERE status = 'Auto-Cancel' AND tsr_code = ?",
                (rep_code or '',)
            )
            return cursor.fetchone()[0] or 0
        finally:
            conn.close()

    def get_booking_request_by_id(self, request_id: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM booking_request WHERE request_id = ?", (request_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()

    def update_booking_request_status(self, request_id: str, status: str, order_id: str = None,
                                      auto_cancel_date: str = None, cancel_reason: str = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            reason_val = (cancel_reason or '').strip() if cancel_reason else None
            if status == 'Auto-Cancel' and auto_cancel_date:
                if order_id:
                    cursor.execute("UPDATE booking_request SET status = ?, order_id = ?, auto_cancel_date = ?, cancel_reason = ? WHERE request_id = ?",
                                   (status, order_id, auto_cancel_date, reason_val, request_id))
                else:
                    cursor.execute("UPDATE booking_request SET status = ?, auto_cancel_date = ?, cancel_reason = ? WHERE request_id = ?",
                                   (status, auto_cancel_date, reason_val, request_id))
            elif order_id:
                cursor.execute("UPDATE booking_request SET status = ?, order_id = ?, cancel_reason = ? WHERE request_id = ?",
                               (status, order_id, reason_val, request_id))
            else:
                cursor.execute("UPDATE booking_request SET status = ?, cancel_reason = ? WHERE request_id = ?",
                               (status, reason_val, request_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating booking request: {e}")
            return False
        finally:
            conn.close()

    def get_all_booking_requests(self, status_filter: str = None) -> pd.DataFrame:
        """Get all booking requests, optionally filtered by status (Pending, Completed, Auto-Cancel)."""
        conn = self.get_connection()
        try:
            if status_filter:
                df = pd.read_sql_query(
                    "SELECT * FROM booking_request WHERE status = ? ORDER BY created_date DESC",
                    conn, params=(status_filter,)
                )
            else:
                df = pd.read_sql_query(
                    "SELECT * FROM booking_request ORDER BY created_date DESC",
                    conn
                )
            return df
        finally:
            conn.close()

    def get_pending_booking_requests_older_than_hours(self, hours: float) -> pd.DataFrame:
        """Get pending booking requests created more than X hours ago."""
        conn = self.get_connection()
        try:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            df = pd.read_sql_query(
                "SELECT * FROM booking_request WHERE status = 'Pending' AND created_date < ? ORDER BY created_date ASC",
                conn, params=(cutoff,)
            )
            return df
        finally:
            conn.close()

    def insert_notification_log(self, notification_type: str, recipient_type: str, recipient_id: str,
                                 order_id: str, request_id: str, status: str, message: str, error_message: str = None) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO notification_log (timestamp, notification_type, recipient_type, recipient_id, order_id, request_id, status, message, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), notification_type, recipient_type, recipient_id or '',
                  order_id or '', request_id or '', status, message or '', error_message or ''))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error inserting notification log: {e}")
            return False
        finally:
            conn.close()

    def get_notification_logs(self, limit: int = 500) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM notification_log ORDER BY timestamp DESC LIMIT ?",
                conn, params=(limit,)
            )
            return df
        finally:
            conn.close()

    def get_last_notification_sent(self, entity_type: str, entity_id: str, notification_type: str) -> Optional[str]:
        """Get last sent timestamp for a notification. Returns None if never sent."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT sent_at FROM notification_sent_tracking
            WHERE entity_type = ? AND entity_id = ? AND notification_type = ?
            ''', (entity_type, entity_id, notification_type))
            row = cursor.fetchone()
            return row['sent_at'] if row else None
        finally:
            conn.close()

    def upsert_notification_sent_tracking(self, entity_type: str, entity_id: str, notification_type: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
            DELETE FROM notification_sent_tracking WHERE entity_type = ? AND entity_id = ? AND notification_type = ?
            ''', (entity_type, entity_id, notification_type))
            cursor.execute('''
            INSERT INTO notification_sent_tracking (entity_type, entity_id, notification_type, sent_at)
            VALUES (?, ?, ?, ?)
            ''', (entity_type, entity_id, notification_type, ts))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error upserting notification tracking: {e}")
            return False
        finally:
            conn.close()

    def get_users_by_account_type(self, account_type: str) -> pd.DataFrame:
        """Get users filtered by account_type (e.g., TRADE for TSR list)"""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query(
                "SELECT * FROM users WHERE account_type = ? ORDER BY rep_name",
                conn, params=(account_type,)
            )
            df = df.rename(columns={
                'username': 'Username', 'rep_code': 'RepCode', 'rep_name': 'RepName'
            })
            return df
        finally:
            conn.close()

    # Accounts
    def get_all_accounts(self) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM accounts", conn)
            # Rename columns to match CSV headers
            df = df.rename(columns={
                'customer_code': 'Customer code',
                'customer_name': 'Customer name',
                'lvl1_short_name': 'lvl1_short_name',
                'lvl2_short_name': 'lvl2_short_name',
                'lvl3_short_name': 'lvl3_short_name',
                'credit_term': 'Credit term',
                'class_code': 'Class code',
                'channel_code': 'channel_code',
                'br_name': 'br_name',
                'business_address': 'Business address',
                'contact_number1': 'Contact number1',
                'tin': 'tin',
                'contact_person1': 'Contact person1',
                'active': 'Active',
                'area': 'Area',
                'sgf': 'SGF',
                'sgf_count': 'SGF_count',
                'tsr_tag': 'TSR_tag',
                'pmr_tag': 'PMR_tag',
                'dsmbu7_tag': 'DSMBU7_tag',
                'dsmpsi_tag': 'DSMPSI_tag',
                'account_type': 'Account_Type'
            })
            return df
        finally:
            conn.close()

    def get_active_accounts(self) -> pd.DataFrame:
        """Get only active accounts - filters at DB level for reliability."""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query("""
                SELECT * FROM accounts 
                WHERE UPPER(TRIM(COALESCE(CAST(active AS TEXT), ''))) IN ('TRUE', '1', 'YES', 'Y')
            """, conn)
            if df.empty:
                return df
            df = df.rename(columns={
                'customer_code': 'Customer code',
                'customer_name': 'Customer name',
                'lvl1_short_name': 'lvl1_short_name',
                'lvl2_short_name': 'lvl2_short_name',
                'lvl3_short_name': 'lvl3_short_name',
                'credit_term': 'Credit term',
                'class_code': 'Class code',
                'channel_code': 'channel_code',
                'br_name': 'br_name',
                'business_address': 'Business address',
                'contact_number1': 'Contact number1',
                'tin': 'tin',
                'contact_person1': 'Contact person1',
                'active': 'Active',
                'area': 'Area',
                'sgf': 'SGF',
                'sgf_count': 'SGF_count',
                'tsr_tag': 'TSR_tag',
                'pmr_tag': 'PMR_tag',
                'dsmbu7_tag': 'DSMBU7_tag',
                'dsmpsi_tag': 'DSMPSI_tag',
                'account_type': 'Account_Type'
            })
            return df
        finally:
            conn.close()

    def check_and_remove_blank_accounts(self) -> int:
        """Remove rows in SQLite accounts table where customer_code or customer_name is null/blank. Returns number of rows deleted."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                DELETE FROM accounts
                WHERE (customer_code IS NULL OR trim(COALESCE(customer_code, '')) = '')
                   OR (customer_name IS NULL OR trim(COALESCE(customer_name, '')) = '')
            ''')
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Error removing blank accounts: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def count_duplicate_account_codes(self) -> int:
        """Count duplicate rows where customer_code is 'X.0' when 'X' exists (e.g. 1556.0 when 1556)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT rowid, customer_code, customer_name FROM accounts WHERE customer_code LIKE '%.0'")
            count = 0
            for row in cursor.fetchall():
                rowid, cc, cn = row[0], str(row[1]), str(row[2])
                try:
                    clean_cc = str(int(float(cc)))
                    cursor.execute(
                        "SELECT 1 FROM accounts WHERE customer_code = ? AND customer_name = ? AND rowid != ?",
                        (clean_cc, cn, rowid)
                    )
                    if cursor.fetchone():
                        count += 1
                except (ValueError, TypeError):
                    pass
            return count
        finally:
            conn.close()

    def check_and_remove_duplicate_account_codes(self) -> int:
        """Remove duplicate rows where customer_code is 'X.0' when 'X' exists (e.g. 1556.0 when 1556).
        Returns number of rows deleted. Ensures single row per customer for consistent Active status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        deleted = 0
        try:
            cursor.execute("SELECT rowid, customer_code, customer_name FROM accounts WHERE customer_code LIKE '%.0'")
            to_delete = []
            for row in cursor.fetchall():
                rowid, cc, cn = row[0], str(row[1]), str(row[2])
                try:
                    clean_cc = str(int(float(cc)))
                    cursor.execute(
                        "SELECT 1 FROM accounts WHERE customer_code = ? AND customer_name = ? AND rowid != ?",
                        (clean_cc, cn, rowid)
                    )
                    if cursor.fetchone():
                        to_delete.append(rowid)
                except (ValueError, TypeError):
                    pass
            for rowid in to_delete:
                cursor.execute("DELETE FROM accounts WHERE rowid = ?", (rowid,))
                deleted += cursor.rowcount
            conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Error removing duplicate account codes: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def delete_accounts_by_customer_codes(self, customer_codes: list) -> int:
        """Delete accounts with the given customer codes. Used when consolidating duplicates (e.g. 396.0 -> 396)."""
        if not customer_codes:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            placeholders = ','.join('?' * len(customer_codes))
            cursor.execute(f"DELETE FROM accounts WHERE customer_code IN ({placeholders})", [str(c).strip() for c in customer_codes])
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Error deleting accounts by customer codes: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def save_accounts_df(self, df: pd.DataFrame, customer_codes_to_delete: list = None) -> bool:
        # This function mimics the original save_accounts behavior (overwrite)
        # But using SQLite efficiently
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            # Delete obsolete rows (e.g. 396.0 when consolidating to 396) before upsert
            if customer_codes_to_delete:
                placeholders = ','.join('?' * len(customer_codes_to_delete))
                cursor.execute(f"DELETE FROM accounts WHERE customer_code IN ({placeholders})", [str(c).strip() for c in customer_codes_to_delete])
            
            for _, row in df.iterrows():
                cursor.execute('''
                INSERT INTO accounts (
                    customer_code, customer_name, lvl1_short_name, lvl2_short_name, lvl3_short_name,
                    credit_term, class_code, channel_code, br_name, business_address,
                    contact_number1, tin, contact_person1, active, area, sgf, sgf_count,
                    tsr_tag, pmr_tag, dsmbu7_tag, dsmpsi_tag, account_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(customer_code) DO UPDATE SET
                    customer_name=excluded.customer_name,
                    lvl1_short_name=excluded.lvl1_short_name,
                    lvl2_short_name=excluded.lvl2_short_name,
                    lvl3_short_name=excluded.lvl3_short_name,
                    credit_term=excluded.credit_term,
                    class_code=excluded.class_code,
                    channel_code=excluded.channel_code,
                    br_name=excluded.br_name,
                    business_address=excluded.business_address,
                    contact_number1=excluded.contact_number1,
                    tin=excluded.tin,
                    contact_person1=excluded.contact_person1,
                    active=excluded.active,
                    area=excluded.area,
                    sgf=excluded.sgf,
                    sgf_count=excluded.sgf_count,
                    tsr_tag=excluded.tsr_tag,
                    pmr_tag=excluded.pmr_tag,
                    dsmbu7_tag=excluded.dsmbu7_tag,
                    dsmpsi_tag=excluded.dsmpsi_tag,
                    account_type=excluded.account_type
                ''', (
                    str(row.get('Customer code', '')),
                    str(row.get('Customer name', '')),
                    str(row.get('lvl1_short_name', '')),
                    str(row.get('lvl2_short_name', '')),
                    str(row.get('lvl3_short_name', '')),
                    str(row.get('Credit term', '')),
                    str(row.get('Class code', '')),
                    str(row.get('channel_code', '')),
                    str(row.get('br_name', '')),
                    str(row.get('Business address', '')),
                    str(row.get('Contact number1', '')),
                    str(row.get('tin', '')),
                    str(row.get('Contact person1', '')),
                    str(row.get('Active', 'TRUE')),
                    str(row.get('Area', '')),
                    str(row.get('SGF', 'FALSE')),
                    int(float(row.get('SGF_count', 99))),
                    str(row.get('TSR_tag', '')),
                    str(row.get('PMR_tag', '')),
                    str(row.get('DSMBU7_tag', '')),
                    str(row.get('DSMPSI_tag', '')),
                    str(row.get('Account_Type', 'Dispensing'))
                ))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving accounts: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # Orders
    def get_all_orders(self) -> pd.DataFrame:
        conn = self.get_connection()
        try:
            # Fetch orders
            orders_df = pd.read_sql_query("SELECT * FROM orders", conn)
            
            if orders_df.empty:
                return orders_df

            # Rename columns to match app expectations
            orders_df = orders_df.rename(columns={
                'order_id': 'OrderID',
                'order_date': 'OrderDate',
                'status': 'Status',
                'client_name': 'ClientName',
                'client_description': 'ClientDescription',
                'client_mobile': 'ClientMobile',
                'billing_address': 'BillingAddress',
                'shipping_address': 'ShippingAddress',
                'payment_terms': 'PaymentTerms',
                'delivery_terms': 'DeliveryTerms',
                'delivery_date': 'DeliveryDate',
                'notes': 'Notes',
                'rep_code': 'RepCode',
                'rep_name': 'RepName',
                'rep_company': 'RepCompany',
                'rep_dept': 'RepDept',
                'rep_area': 'RepArea',
                'remarks': 'Remarks',
                'total_amount': 'TotalAmount',
                'created_by': 'CreatedBy',
                'reviewed_by': 'ReviewedBy',
                'reviewed_date': 'ReviewedDate',
                'discount_percent': 'DiscountPercent',
                'discount_amount': 'DiscountAmount',
                'subtotal': 'Subtotal',
                'printed': 'Printed',
                'printed_date': 'PrintedDate',
                'printed_time': 'PrintedTime',
                'approved_by_level1': 'ApprovedByLevel1',
                'approved_date_level1': 'ApprovedDateLevel1',
                'approved_by_level2': 'ApprovedByLevel2',
                'approved_date_level2': 'ApprovedDateLevel2',
                'approved_by_sgf': 'ApprovedBySGF',
                'approved_date_sgf': 'ApprovedDateSGF',
                'contact_person1': 'ContactPerson1',
                'contact_person1_mobile': 'ContactPerson1Mobile',
                'contact_person2': 'ContactPerson2',
                'contact_person2_mobile': 'ContactPerson2Mobile',
                'attachments': 'Attachments',
                'disapproved_items': 'DisapprovedItems',
                'tsr_tag': 'TSR_tag',
                'pmr_tag': 'PMR_tag',
                'dsmbu7_tag': 'DSMBU7_tag',
                'dsmpsi_tag': 'DSMPSI_tag',
                'br_created_by': 'BR_CreatedBy',
                'booking_request_id': 'BookingRequestID'
            })
            # Ensure BR columns exist (old DBs may not have them before migration)
            if 'BR_CreatedBy' not in orders_df.columns:
                orders_df['BR_CreatedBy'] = ''
            if 'BookingRequestID' not in orders_df.columns:
                orders_df['BookingRequestID'] = ''
            orders_df['BR_CreatedBy'] = orders_df['BR_CreatedBy'].fillna('')
            orders_df['BookingRequestID'] = orders_df['BookingRequestID'].fillna('')
            # Backfill BR_CreatedBy and BookingRequestID from completed booking_request for orders that lack them
            br_df = pd.read_sql_query(
                "SELECT order_id, request_id, created_by FROM booking_request WHERE order_id IS NOT NULL AND order_id != '' AND status = 'Completed'",
                conn
            )
            if not br_df.empty:
                for _, br_row in br_df.iterrows():
                    oid = br_row.get('order_id', '')
                    if not oid:
                        continue
                    mask = orders_df['OrderID'] == oid
                    if mask.any():
                        rid = br_row.get('request_id', '')
                        cby = br_row.get('created_by', '')
                        if rid or cby:
                            orders_df.loc[mask, 'BookingRequestID'] = str(rid or '')
                            orders_df.loc[mask, 'BR_CreatedBy'] = str(cby or '')
            
            # Fetch items for each order and reconstruct CartItems list
            # Optimization: Fetch all items in one query
            items_df = pd.read_sql_query("SELECT * FROM order_items", conn)
            
            # Fetch booking requests linked to orders (for Notes/Remarks fallback when order_items lacks them)
            br_df = pd.read_sql_query(
                "SELECT order_id, request_id, cart_items FROM booking_request WHERE order_id IS NOT NULL AND order_id != ''",
                conn
            )
            br_by_order = {}
            if not br_df.empty:
                for _, row in br_df.iterrows():
                    oid = row.get('order_id', '')
                    if oid:
                        br_by_order[oid] = {'request_id': row.get('request_id', ''), 'cart_items': row.get('cart_items', '[]')}
            
            # Group by order_id
            cart_items_map = {}
            if not items_df.empty:
                grouped = items_df.groupby('order_id')
                for order_id, group in grouped:
                    items_list = []
                    for _, item in group.iterrows():
                        # Reconstruct the dict structure expected by the app
                        try:
                            row_data = json.loads(item['row_data']) if item['row_data'] else {}
                        except:
                            row_data = {}
                        notes_remarks = str(item.get('notes_remarks', '') or '').strip()
                        items_list.append({
                            'product_code': item['product_code'],
                            'product_name': item['product_name'],
                            'qty': item['quantity'],
                            'price': item['price'],
                            'row_data': row_data,
                            'notes_remarks': notes_remarks
                        })
                    # Fallback: if any item has empty notes_remarks, try to map from booking request
                    br_info = br_by_order.get(order_id)
                    if br_info and br_info.get('cart_items'):
                        try:
                            br_cart = json.loads(br_info['cart_items']) if isinstance(br_info['cart_items'], str) else br_info['cart_items']
                        except (json.JSONDecodeError, TypeError):
                            br_cart = []
                        if isinstance(br_cart, list) and br_cart:
                            # Build lookup by product_code (primary) and product_name (fallback)
                            br_notes_map = {}
                            for br_item in br_cart:
                                if isinstance(br_item, dict):
                                    pc = str(br_item.get('product_code', '') or '').strip()
                                    pn = str(br_item.get('product_name', '') or '').strip()
                                    nr = str(br_item.get('notes_remarks', '') or '').strip()
                                    if nr:
                                        if pc:
                                            br_notes_map[('code', pc)] = nr
                                        if pn:
                                            br_notes_map[('name', pn.upper())] = nr
                            # Fill missing notes_remarks from booking request
                            for oi in items_list:
                                if not oi.get('notes_remarks', '').strip():
                                    pc = str(oi.get('product_code', '') or '').strip()
                                    pn = str(oi.get('product_name', '') or '').strip().upper()
                                    nr = br_notes_map.get(('code', pc)) or br_notes_map.get(('name', pn)) or ''
                                    if nr:
                                        oi['notes_remarks'] = nr
                    cart_items_map[order_id] = str(items_list) # Store as string representation of list to match CSV format behavior
            
            # Apply to orders_df
            orders_df['CartItems'] = orders_df['OrderID'].map(lambda x: cart_items_map.get(x, '[]'))
            
            return orders_df
        finally:
            conn.close()

    def save_orders_df(self, df: pd.DataFrame) -> bool:
        """Save dataframe of orders to database (upsert)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            
            for _, row in df.iterrows():
                # Extract order data
                order_data = row.to_dict()
                
                # Extract cart items
                cart_items_str = row.get('CartItems', '[]')
                # Use simple parsing or rely on string format if it was just loaded
                # Ideally we parse it properly
                import ast
                import re
                try:
                    cart_items_list = ast.literal_eval(cart_items_str) if isinstance(cart_items_str, str) else cart_items_str
                except:
                    cart_items_list = []
                
                # Convert to CartItem objects
                cart_items = []
                if isinstance(cart_items_list, list):
                    for item in cart_items_list:
                        if isinstance(item, dict):
                            cart_items.append(CartItem(
                                product_code=str(item.get('product_code', '')),
                                product_name=str(item.get('product_name', '')),
                                qty=int(float(item.get('qty', 0))),
                                price=float(item.get('price', 0)),
                                row_data=item.get('row_data', {}),
                                notes_remarks=str(item.get('notes_remarks', '') or '')
                            ))
                
                # Upsert order
                # Use the existing save_order logic but inside this transaction?
                # No, save_order has its own transaction. I should copy the INSERT/UPDATE logic here.
                # Or just call save_order (but that would commit each time).
                # Better to duplicate logic for performance or make save_order take a connection.
                
                # Let's use the query from save_order
                cursor.execute('''
                INSERT INTO orders (
                    order_id, order_date, status, client_name, client_description, client_mobile,
                    billing_address, shipping_address, payment_terms, delivery_terms, delivery_date,
                    notes, rep_code, rep_name, rep_company, rep_dept, rep_area, remarks,
                    total_amount, created_by, reviewed_by, reviewed_date, discount_percent,
                    discount_amount, subtotal, printed, printed_date, printed_time,
                    approved_by_level1, approved_date_level1, approved_by_level2, approved_date_level2,
                    approved_by_sgf, approved_date_sgf, contact_person1, contact_person1_mobile,
                    contact_person2, contact_person2_mobile, attachments, disapproved_items,
                    tsr_tag, pmr_tag, dsmbu7_tag, dsmpsi_tag, br_created_by, booking_request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    status=excluded.status,
                    client_name=excluded.client_name,
                    client_description=excluded.client_description,
                    client_mobile=excluded.client_mobile,
                    billing_address=excluded.billing_address,
                    shipping_address=excluded.shipping_address,
                    payment_terms=excluded.payment_terms,
                    delivery_terms=excluded.delivery_terms,
                    delivery_date=excluded.delivery_date,
                    notes=excluded.notes,
                    remarks=excluded.remarks,
                    total_amount=excluded.total_amount,
                    reviewed_by=excluded.reviewed_by,
                    reviewed_date=excluded.reviewed_date,
                    discount_percent=excluded.discount_percent,
                    discount_amount=excluded.discount_amount,
                    subtotal=excluded.subtotal,
                    printed=excluded.printed,
                    printed_date=excluded.printed_date,
                    printed_time=excluded.printed_time,
                    approved_by_level1=excluded.approved_by_level1,
                    approved_date_level1=excluded.approved_date_level1,
                    approved_by_level2=excluded.approved_by_level2,
                    approved_date_level2=excluded.approved_date_level2,
                    approved_by_sgf=excluded.approved_by_sgf,
                    approved_date_sgf=excluded.approved_date_sgf,
                    attachments=excluded.attachments,
                    disapproved_items=excluded.disapproved_items,
                    tsr_tag=excluded.tsr_tag,
                    pmr_tag=excluded.pmr_tag,
                    dsmbu7_tag=excluded.dsmbu7_tag,
                    dsmpsi_tag=excluded.dsmpsi_tag,
                    br_created_by=excluded.br_created_by,
                    booking_request_id=excluded.booking_request_id
                ''', (
                    order_data.get('OrderID'),
                    order_data.get('OrderDate'),
                    order_data.get('Status'),
                    order_data.get('ClientName'),
                    order_data.get('ClientDescription'),
                    order_data.get('ClientMobile'),
                    order_data.get('BillingAddress'),
                    order_data.get('ShippingAddress'),
                    order_data.get('PaymentTerms'),
                    order_data.get('DeliveryTerms'),
                    order_data.get('DeliveryDate'),
                    order_data.get('Notes'),
                    order_data.get('RepCode'),
                    order_data.get('RepName'),
                    order_data.get('RepCompany'),
                    order_data.get('RepDept'),
                    order_data.get('RepArea'),
                    order_data.get('Remarks'),
                    order_data.get('TotalAmount'),
                    order_data.get('CreatedBy'),
                    order_data.get('ReviewedBy'),
                    order_data.get('ReviewedDate'),
                    order_data.get('DiscountPercent'),
                    order_data.get('DiscountAmount'),
                    order_data.get('Subtotal'),
                    order_data.get('Printed'),
                    order_data.get('PrintedDate'),
                    order_data.get('PrintedTime'),
                    order_data.get('ApprovedByLevel1'),
                    order_data.get('ApprovedDateLevel1'),
                    order_data.get('ApprovedByLevel2'),
                    order_data.get('ApprovedDateLevel2'),
                    order_data.get('ApprovedBySGF'),
                    order_data.get('ApprovedDateSGF'),
                    order_data.get('ContactPerson1'),
                    order_data.get('ContactPerson1Mobile'),
                    order_data.get('ContactPerson2'),
                    order_data.get('ContactPerson2Mobile'),
                    order_data.get('Attachments'),
                    order_data.get('DisapprovedItems'),
                    str(order_data.get('TSR_tag', '') or ''),
                    str(order_data.get('PMR_tag', '') or ''),
                    str(order_data.get('DSMBU7_tag', '') or ''),
                    str(order_data.get('DSMPSI_tag', '') or ''),
                    str(order_data.get('BR_CreatedBy', '') or ''),
                    str(order_data.get('BookingRequestID', '') or '')
                ))
                
                # Update items (Delete existing and re-insert)
                # This is heavy but ensures consistency
                cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_data.get('OrderID'),))
                
                for item in cart_items:
                    notes_remarks = getattr(item, 'notes_remarks', '') or ''
                    cursor.execute('''
                    INSERT INTO order_items (
                        order_id, product_code, product_name, quantity, price, row_data, notes_remarks
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        order_data.get('OrderID'),
                        item.product_code,
                        item.product_name,
                        item.qty,
                        item.price,
                        json.dumps(item.row_data),
                        str(notes_remarks)
                    ))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error saving orders: {e}")
            return False
        finally:
            conn.close()

    def save_order(self, order_data: Dict[str, Any], cart_items: List[CartItem]) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION")
            
            # 1. Upsert Order
            cursor.execute('''
            INSERT INTO orders (
                order_id, order_date, status, client_name, client_description, client_mobile,
                billing_address, shipping_address, payment_terms, delivery_terms, delivery_date,
                notes, rep_code, rep_name, rep_company, rep_dept, rep_area, remarks,
                total_amount, created_by, reviewed_by, reviewed_date, discount_percent,
                discount_amount, subtotal, printed, printed_date, printed_time,
                approved_by_level1, approved_date_level1, approved_by_level2, approved_date_level2,
                approved_by_sgf, approved_date_sgf, contact_person1, contact_person1_mobile,
                contact_person2, contact_person2_mobile, attachments, disapproved_items
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_id) DO UPDATE SET
                status=excluded.status,
                client_name=excluded.client_name,
                client_description=excluded.client_description,
                client_mobile=excluded.client_mobile,
                billing_address=excluded.billing_address,
                shipping_address=excluded.shipping_address,
                payment_terms=excluded.payment_terms,
                delivery_terms=excluded.delivery_terms,
                delivery_date=excluded.delivery_date,
                notes=excluded.notes,
                remarks=excluded.remarks,
                total_amount=excluded.total_amount,
                reviewed_by=excluded.reviewed_by,
                reviewed_date=excluded.reviewed_date,
                discount_percent=excluded.discount_percent,
                discount_amount=excluded.discount_amount,
                subtotal=excluded.subtotal,
                printed=excluded.printed,
                printed_date=excluded.printed_date,
                printed_time=excluded.printed_time,
                approved_by_level1=excluded.approved_by_level1,
                approved_date_level1=excluded.approved_date_level1,
                approved_by_level2=excluded.approved_by_level2,
                approved_date_level2=excluded.approved_date_level2,
                approved_by_sgf=excluded.approved_by_sgf,
                approved_date_sgf=excluded.approved_date_sgf,
                attachments=excluded.attachments,
                disapproved_items=excluded.disapproved_items
            ''', (
                order_data.get('OrderID'),
                order_data.get('OrderDate'),
                order_data.get('Status'),
                order_data.get('ClientName'),
                order_data.get('ClientDescription'),
                order_data.get('ClientMobile'),
                order_data.get('BillingAddress'),
                order_data.get('ShippingAddress'),
                order_data.get('PaymentTerms'),
                order_data.get('DeliveryTerms'),
                order_data.get('DeliveryDate'),
                order_data.get('Notes'),
                order_data.get('RepCode'),
                order_data.get('RepName'),
                order_data.get('RepCompany'),
                order_data.get('RepDept'),
                order_data.get('RepArea'),
                order_data.get('Remarks'),
                float(order_data.get('TotalAmount', 0)),
                order_data.get('CreatedBy'),
                order_data.get('ReviewedBy'),
                order_data.get('ReviewedDate'),
                float(order_data.get('DiscountPercent', 0)),
                float(order_data.get('DiscountAmount', 0)),
                float(order_data.get('Subtotal', 0)),
                order_data.get('Printed'),
                order_data.get('PrintedDate'),
                order_data.get('PrintedTime'),
                order_data.get('ApprovedByLevel1'),
                order_data.get('ApprovedDateLevel1'),
                order_data.get('ApprovedByLevel2'),
                order_data.get('ApprovedDateLevel2'),
                order_data.get('ApprovedBySGF'),
                order_data.get('ApprovedDateSGF'),
                order_data.get('ContactPerson1'),
                order_data.get('ContactPerson1Mobile'),
                order_data.get('ContactPerson2'),
                order_data.get('ContactPerson2Mobile'),
                order_data.get('Attachments'),
                str(order_data.get('DisapprovedItems', '[]'))
            ))
            
            # 2. Delete existing items for this order
            cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_data.get('OrderID'),))
            
            # 3. Insert new items
            for item in cart_items:
                notes_remarks = getattr(item, 'notes_remarks', '') or ''
                cursor.execute('''
                INSERT INTO order_items (order_id, product_code, product_name, quantity, price, row_data, notes_remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    order_data.get('OrderID'),
                    item.product_code,
                    item.product_name,
                    item.qty,
                    item.price,
                    json.dumps(item.row_data),
                    str(notes_remarks)
                ))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving order: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # SO History (from ETHICAL consolidated CSV)
    @staticmethod
    def _notes_remarks_to_percent_str(val):
        """Convert decimal to percentage string (0.2 -> '20%'). Non-decimals return as string."""
        if pd.isna(val) or val == '' or val is None:
            return None
        try:
            n = float(val)
            if 0 <= n <= 1:
                return f"{int(round(n * 100))}%"
            return str(val)
        except (ValueError, TypeError):
            return str(val).strip() if val else None

    def save_so_history_df(self, df: pd.DataFrame, replace_all: bool = False) -> bool:
        """Save SO history DataFrame to so_history table.
        replace_all=True: deletes all rows (legacy). replace_all=False: deletes only non-App rows, preserves App-approved backup."""
        if df.empty:
            return True
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if replace_all:
                cursor.execute("DELETE FROM so_history")
            else:
                cursor.execute("DELETE FROM so_history WHERE source_sheet IS NULL OR source_sheet != 'App'")
            col_map = {
                'AREA': 'area', 'Address': 'address', 'CLASS CODE': 'class_code',
                'CUSTOMER CODE': 'customer_code', 'CUSTOMER NAME': 'customer_name',
                'NOTES/REMARKS': 'notes_remarks', 'SALES UNIT': 'sales_unit',
                'FREE GOODS': 'free_goods', 'DISCOUNT': 'discount', 'DISTRICT': 'district',
                'DISTRICT MANAGER': 'district_manager', 'DSMBU7 CODE': 'dsmbu7_code',
                'DSMPSI': 'dsmpsi', 'DSMPSI CODE': 'dsmpsi_code', 'GROSS SALES': 'gross_sales',
                'REMARKS': 'remarks', 'REP CODE': 'rep_code', 'REP NAME': 'rep_name',
                'SALES DISCOUNT': 'sales_discount', 'SCR': 'scr', 'SKU NAME': 'sku_name',
                'TERMS': 'terms', 'TSR': 'tsr', 'TSR CODE': 'tsr_code',
                'Source_Sheet': 'source_sheet', 'Full_DATE': 'full_date',
                'MONTH': 'month', 'YEAR': 'year'
            }
            for _, row in df.iterrows():
                vals = {db_col: None for db_col in col_map.values()}
                for csv_col, db_col in col_map.items():
                    if csv_col in row.index:
                        v = row.get(csv_col)
                        if pd.isna(v):
                            vals[db_col] = None
                        elif db_col in ('sales_unit', 'free_goods', 'discount', 'gross_sales', 'sales_discount'):
                            try:
                                vals[db_col] = float(v)
                            except (ValueError, TypeError):
                                vals[db_col] = None
                        elif db_col in ('month', 'year'):
                            try:
                                vals[db_col] = int(float(v))
                            except (ValueError, TypeError):
                                vals[db_col] = None
                        elif db_col == 'notes_remarks':
                            _nr = self._notes_remarks_to_percent_str(v)
                            vals[db_col] = str(_nr) if _nr is not None else None
                        else:
                            vals[db_col] = str(v).strip() if v is not None else None
                cursor.execute('''
                INSERT INTO so_history (area, address, class_code, customer_code, customer_name,
                    notes_remarks, sales_unit, free_goods, discount, district, district_manager,
                    dsmbu7_code, dsmpsi, dsmpsi_code, gross_sales, remarks, rep_code, rep_name,
                    sales_discount, scr, sku_name, terms, tsr, tsr_code, source_sheet, full_date, month, year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    vals.get('area'), vals.get('address'), vals.get('class_code'),
                    vals.get('customer_code'), vals.get('customer_name'), vals.get('notes_remarks'),
                    vals.get('sales_unit'), vals.get('free_goods'), vals.get('discount'),
                    vals.get('district'), vals.get('district_manager'), vals.get('dsmbu7_code'),
                    vals.get('dsmpsi'), vals.get('dsmpsi_code'), vals.get('gross_sales'),
                    vals.get('remarks'), vals.get('rep_code'), vals.get('rep_name'),
                    vals.get('sales_discount'), vals.get('scr'), vals.get('sku_name'),
                    vals.get('terms'), vals.get('tsr'), vals.get('tsr_code'),
                    vals.get('source_sheet'), vals.get('full_date'), vals.get('month'), vals.get('year')
                ))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error saving SO history: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_so_history_notes_lookup(self, customer_name: str) -> Dict[str, str]:
        """
        Get Notes/Remarks lookup for a customer from SO_history.
        Returns dict: normalized_sku_name -> notes_remarks (most recent transaction wins).
        Optimized for fast cart auto-fill - uses single query, vectorized processing.
        """
        if not customer_name or not str(customer_name).strip():
            return {}
        conn = self.get_connection()
        try:
            cust_norm = str(customer_name).strip().upper()
            df = pd.read_sql_query(
                """SELECT sku_name, notes_remarks, full_date, id 
                   FROM so_history 
                   WHERE TRIM(UPPER(COALESCE(customer_name,''))) = ? 
                   AND notes_remarks IS NOT NULL AND TRIM(notes_remarks) != ''
                   ORDER BY CASE WHEN full_date IS NULL THEN 1 ELSE 0 END, full_date DESC, id DESC""",
                conn, params=(cust_norm,)
            )
            if df.empty:
                return {}
            # First occurrence per sku_name wins (already ordered by recent)
            result = {}
            for _, row in df.iterrows():
                sku = str(row.get('sku_name', '') or '').strip()
                if not sku:
                    continue
                key = sku.upper()
                if key not in result:
                    result[key] = str(row.get('notes_remarks', '') or '').strip()
            return result
        except Exception as e:
            logger.error(f"Error getting SO history notes lookup: {e}")
            return {}
        finally:
            conn.close()

    def get_so_history_df(self) -> pd.DataFrame:
        """Get SO history as DataFrame with display-friendly column names."""
        conn = self.get_connection()
        try:
            df = pd.read_sql_query("SELECT * FROM so_history ORDER BY id", conn)
            if df.empty:
                return df
            df = df.drop(columns=['id'], errors='ignore')
            df = df.rename(columns={
                'area': 'AREA', 'address': 'Address', 'class_code': 'CLASS CODE',
                'customer_code': 'CUSTOMER CODE', 'customer_name': 'CUSTOMER NAME',
                'notes_remarks': 'NOTES/REMARKS', 'sales_unit': 'SALES UNIT',
                'free_goods': 'FREE GOODS', 'discount': 'DISCOUNT', 'district': 'DISTRICT',
                'district_manager': 'DISTRICT MANAGER', 'dsmbu7_code': 'DSMBU7 CODE',
                'dsmpsi': 'DSMPSI', 'dsmpsi_code': 'DSMPSI CODE', 'gross_sales': 'GROSS SALES',
                'remarks': 'REMARKS', 'rep_code': 'REP CODE', 'rep_name': 'REP NAME',
                'sales_discount': 'SALES DISCOUNT', 'scr': 'SCR', 'sku_name': 'SKU NAME',
                'terms': 'TERMS', 'tsr': 'TSR', 'tsr_code': 'TSR CODE',
                'source_sheet': 'Source_Sheet', 'full_date': 'Full_DATE',
                'month': 'MONTH', 'year': 'YEAR'
            })
            if 'NOTES/REMARKS' in df.columns:
                df['NOTES/REMARKS'] = df['NOTES/REMARKS'].fillna('').astype(str)
            return df
        except Exception as e:
            logger.error(f"Error getting SO history: {e}")
            return pd.DataFrame()
        finally:
            conn.close()

    def append_approved_order_to_so_history(self, order_row: Dict[str, Any], approved_date_str: str) -> bool:
        """
        Append a final approved order (Admin Level 2) to so_history as backup.
        Creates one row per cart item. Date/Month/Year based on final approval date.
        Excludes disapproved items.
        """
        try:
            cart_items_str = order_row.get('CartItems', '[]')
            try:
                cart_items = ast.literal_eval(cart_items_str) if isinstance(cart_items_str, str) else (cart_items_str or [])
            except (ValueError, SyntaxError):
                cart_items = []
            if not isinstance(cart_items, list):
                cart_items = []

            disapproved_str = order_row.get('DisapprovedItems', '[]')
            try:
                disapproved = ast.literal_eval(disapproved_str) if isinstance(disapproved_str, str) else (disapproved_str or [])
            except (ValueError, SyntaxError):
                disapproved = []
            disapproved_indices = {d.get('item_index', -1) for d in disapproved if isinstance(d, dict)}
            remaining_items = [item for idx, item in enumerate(cart_items) if idx not in disapproved_indices and isinstance(item, dict)]

            if not remaining_items:
                return True

            try:
                dt = datetime.strptime(str(approved_date_str)[:19], '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                try:
                    dt = datetime.strptime(str(approved_date_str)[:10], '%Y-%m-%d')
                except (ValueError, TypeError):
                    dt = datetime.now()
            full_date = dt.strftime('%Y-%m-%d')
            month, year = dt.month, dt.year

            accounts_df = self.get_all_accounts()
            client_name = str(order_row.get('ClientName', '')).strip()
            customer_code = ''
            class_code = ''
            area = ''
            if not accounts_df.empty and 'Customer name' in accounts_df.columns:
                match = accounts_df[accounts_df['Customer name'].astype(str).str.strip().str.upper() == client_name.upper()]
                if not match.empty:
                    customer_code = str(match.iloc[0].get('Customer code', '')).strip()
                    class_code = str(match.iloc[0].get('Class code', '')).strip()
                    area = str(match.iloc[0].get('Area', '')).strip()

            address = str(order_row.get('ShippingAddress', '') or order_row.get('BillingAddress', '')).strip()
            rep_code = str(order_row.get('RepCode', '')).strip()
            rep_name = str(order_row.get('RepName', '')).strip()
            terms = str(order_row.get('PaymentTerms', '')).strip()

            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                for item in remaining_items:
                    qty = int(float(item.get('qty', 0)))
                    price = float(item.get('price', 0))
                    gross_sales = qty * price
                    sku_name = str(item.get('product_name', '')).strip()
                    notes_remarks = str(item.get('notes_remarks', '')).strip()
                    notes_remarks = self._notes_remarks_to_percent_str(notes_remarks) or notes_remarks or None

                    cursor.execute('''
                    INSERT INTO so_history (area, address, class_code, customer_code, customer_name,
                        notes_remarks, sales_unit, free_goods, discount, district, district_manager,
                        dsmbu7_code, dsmpsi, dsmpsi_code, gross_sales, remarks, rep_code, rep_name,
                        sales_discount, scr, sku_name, terms, tsr, tsr_code, source_sheet, full_date, month, year)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        area, address, class_code, customer_code, client_name,
                        notes_remarks, float(qty), None, None, None, None,
                        None, None, None, gross_sales, None, rep_code, rep_name,
                        None, None, sku_name, terms, None, rep_code,
                        'App', full_date, month, year
                    ))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error appending order to SO history: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Error in append_approved_order_to_so_history: {e}")
            return False

db = DatabaseManager()
