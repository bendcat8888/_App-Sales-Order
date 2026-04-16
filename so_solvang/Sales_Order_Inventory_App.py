import streamlit as st
import pandas as pd
import smtplib
import threading
import json
import uuid
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pyodbc
import os
import sys
import shutil
import ast
import re
from db_manager import DatabaseManager, CartItem, User, Product

# Role name aliases: old -> new (for fallback when reading from DB/CSV)
ROLE_ALIASES = {
    'Admin Level 1': 'Admin Level 1 Ethical',
    'Admin Ethical Level 1': 'Admin Level 1 Ethical',  # legacy name
    'Finance Staff Level 1': 'Ethical Staff Level 1',
}
# When looking up by new role, also check these old roles (for backward compatibility)
ROLE_FALLBACK_LOOKUP = {
    'Admin Level 1 Ethical': ['Admin Level 1', 'Admin Ethical Level 1'],
    'Ethical Staff Level 1': ['Finance Staff Level 1'],
}

def normalize_role(role):
    """Normalize role to new names; accepts old names for backward compatibility."""
    if not role or not str(role).strip():
        return role or ''
    return ROLE_ALIASES.get(str(role).strip(), str(role).strip())

# Page Configuration
st.set_page_config(
    page_title="Sales Order Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database Manager
if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()
    # Ensure default users exist (this is safe - only creates if database is empty)
    st.session_state.db.init_default_users()
    # One-time migration: import users from users.csv into SQLite (centralize to single table)
    _users_csv = 'users.csv'
    if os.path.exists(_users_csv):
        try:
            users_df = pd.read_csv(_users_csv)
            if not users_df.empty:
                for _, row in users_df.iterrows():
                    u = str(row.get('Username', '')).strip()
                    if u:
                        user = User(
                            username=u,
                            password=str(row.get('Password', '')),
                            role=normalize_role(str(row.get('Role', 'Sales Rep'))),
                            rep_code=str(row.get('RepCode', '')) if pd.notna(row.get('RepCode')) else '',
                            rep_name=str(row.get('RepName', '')) if pd.notna(row.get('RepName')) else '',
                            rep_company=str(row.get('RepCompany', '')) if pd.notna(row.get('RepCompany')) else '',
                            rep_dept=str(row.get('RepDept', '')) if pd.notna(row.get('RepDept')) else '',
                            rep_area=str(row.get('RepArea', '')) if pd.notna(row.get('RepArea')) else '',
                            registration_date=str(row.get('RegistrationDate', datetime.now().strftime('%Y-%m-%d'))) if pd.notna(row.get('RegistrationDate')) else datetime.now().strftime('%Y-%m-%d'),
                            account_type='Dispensing'
                        )
                        st.session_state.db.upsert_user(user)
                os.rename(_users_csv, _users_csv + '.migrated')
        except Exception as e:
            print(f"Users CSV migration: {e}")
db = st.session_state.db

# Global styles and theme enforcement (ensures purple theme persists even after reruns)
def load_global_styles():
    st.markdown(
        """
        <style>
            :root {
                /* Streamlit theme variables (mirror config.toml) */
                --primary-color: #7B2CBF; /* Purple from config.toml */
                --text-color: #262730;
                --background-color: #FFFFFF;
                --secondary-background-color: #F0F2F6;
            }

            /* --- Theme Enforcement (Prevents Fallback to Red/Gray) --- */

            /* Force all primary buttons to be purple */
            button[kind="primary"],
            div.stButton > button[kind="primary"],
            div.stButton > button[class*="primary"],
            .st-emotion-cache-12w0qpk button[kind="primary"] {
                background-color: var(--primary-color) !important;
                border-color: var(--primary-color) !important;
                color: #FFFFFF !important;
            }

            /* Fix hover states for primary buttons */
            button[kind="primary"]:hover,
            div.stButton > button[kind="primary"]:hover,
            .st-emotion-cache-12w0qpk button[kind="primary"]:hover {
                background-color: #6A1B9A !important; /* Darker purple on hover */
                border-color: #6A1B9A !important;
                filter: brightness(0.95) !important;
            }

            /* Inputs focus state */
            input:focus, textarea:focus, select:focus, div[data-baseweb="input"] input:focus {
                border-color: var(--primary-color) !important;
                box-shadow: 0 0 0 0.2rem rgba(123, 44, 191, 0.25) !important;
                outline: none !important;
            }

            /* Checkbox/Radio/Slider accents */
            input[type="checkbox"], input[type="radio"], .stProgress > div > div > div > div, div[role="slider"] > div {
                accent-color: var(--primary-color) !important;
                background-color: var(--primary-color) !important;
            }

            /* Link color */
            a { color: var(--primary-color) !important; }

            /* --- Layout & Components --- */

            /* Fixed footer styling (Purple bar at bottom) */
            .fixed-footer {
                position: fixed !important;
                left: 0 !important;
                right: 0 !important;
                bottom: 0 !important;
                background-color: var(--primary-color) !important;
                color: #FFFFFF !important;
                text-align: center !important;
                padding: 6px 0 !important;
                border-top: 1px solid #6A1B9A !important;
                z-index: 999999 !important;
                font-size: 0.8rem !important;
                box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1) !important;
                display: block !important;
                visibility: visible !important;
                opacity: 1 !important;
            }

            /* Ensure footer text is white */
            .fixed-footer p, .fixed-footer span, .fixed-footer div {
                color: #FFFFFF !important;
                margin: 0 !important;
            }

            /* Padding for main content to avoid footer overlap */
            .main .block-container {
                padding-bottom: 50px !important;
            }

            /* Data Editor highlights */
            div[data-testid="stDataFrame"] tbody tr:first-child td,
            div[data-testid="stDataFrameResizable"] tbody tr:first-child td {
                background-color: #f3e5f5 !important; /* Light purple highlight */
            }

            /* Common button centering for tables */
            div.stButton {
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
            }

            /* Target the button itself */
            div.stButton > button {
                display: flex !important;
                justify-content: center !important;
                align-items: center !important;
            }
            
            /* Center button icons/text */
            button[kind="secondary"], button[kind="primary"] {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                text-align: center !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Apply global styles on every run
load_global_styles()


# Inject fixed footer HTML (rendered once globally)
st.markdown("""
    <div class="fixed-footer">
        InnoGen's IT Department © 2026
    </div>
    <script>
    // Ensure footer is always visible and on top
    (function() {
        var footer = document.querySelector('.fixed-footer');
        if (footer) {
            footer.style.zIndex = '999999';
            footer.style.position = 'fixed';
            footer.style.display = 'block';
            footer.style.visibility = 'visible';
        }
        // Also append to body if not already there
        if (footer && footer.parentElement !== document.body) {
            document.body.appendChild(footer);
        }
    })();
    </script>
""", unsafe_allow_html=True)

# Initialize Session State
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'cart' not in st.session_state:
    st.session_state.cart = []
# Ensure cart items are Pydantic models (migration from dicts)
if st.session_state.cart and isinstance(st.session_state.cart[0], dict):
    new_cart = []
    for item in st.session_state.cart:
        if isinstance(item, dict):
            # Handle potential missing fields
            if 'notes_remarks' not in item:
                item['notes_remarks'] = ''
            if 'row_data' not in item:
                item['row_data'] = {}
            try:
                new_cart.append(CartItem(**item))
            except Exception:
                pass
        else:
            new_cart.append(item)
    st.session_state.cart = new_cart
if 'rep_code' not in st.session_state:
    st.session_state.rep_code = None
if 'rep_name' not in st.session_state:
    st.session_state.rep_name = None
if 'rep_company' not in st.session_state:
    st.session_state.rep_company = None
if 'rep_dept' not in st.session_state:
    st.session_state.rep_dept = None
if 'rep_area' not in st.session_state:
    st.session_state.rep_area = None
if 'show_submit_order_dialog' not in st.session_state:
    st.session_state.show_submit_order_dialog = False
# CRITICAL: If we just added to cart, clear dialog state immediately at top level
# This prevents dialog from rendering during widget processing
if st.session_state.get('just_added_to_cart', False):
    st.session_state.show_submit_order_dialog = False
    st.session_state.show_order_details_dialog = False
    st.session_state.show_disapprove_dialog = False
    st.session_state.show_disapprove_item_dialog = False
    st.session_state.show_unlock_dialog = False
    st.session_state.show_cancel_order_dialog = False
    st.session_state.dialog_button_clicked = False
if 'just_added_to_cart' not in st.session_state:
    st.session_state.just_added_to_cart = False
if 'show_order_details_dialog' not in st.session_state:
    st.session_state.show_order_details_dialog = False
if 'selected_order_id' not in st.session_state:
    st.session_state.selected_order_id = None
if 'dialog_button_clicked' not in st.session_state:
    st.session_state.dialog_button_clicked = False
if 'last_date_from' not in st.session_state:
    st.session_state.last_date_from = None
if 'last_date_to' not in st.session_state:
    st.session_state.last_date_to = None
if 'last_status_filter' not in st.session_state:
    st.session_state.last_status_filter = None
if 'last_submitted_order_id' not in st.session_state:
    st.session_state.last_submitted_order_id = None
if 'order_submission_success' not in st.session_state:
    st.session_state.order_submission_success = False
if 'show_print_view' not in st.session_state:
    st.session_state.show_print_view = False
if 'print_view_order_id' not in st.session_state:
    st.session_state.print_view_order_id = None
if 'show_disapprove_dialog' not in st.session_state:
    st.session_state.show_disapprove_dialog = False
if 'disapprove_order_id' not in st.session_state:
    st.session_state.disapprove_order_id = None
if 'show_unlock_dialog' not in st.session_state:
    st.session_state.show_unlock_dialog = False
if 'unlock_order_id' not in st.session_state:
    st.session_state.unlock_order_id = None
if 'show_cancel_order_dialog' not in st.session_state:
    st.session_state.show_cancel_order_dialog = False
if 'cancel_order_id' not in st.session_state:
    st.session_state.cancel_order_id = None
if 'show_cancel_br_by_creator_dialog' not in st.session_state:
    st.session_state.show_cancel_br_by_creator_dialog = False
if 'cancel_br_request_id' not in st.session_state:
    st.session_state.cancel_br_request_id = None
if 'admin_level' not in st.session_state:
    st.session_state.admin_level = None
if 'account_type' not in st.session_state:
    st.session_state.account_type = 'Dispensing'
if 'selected_booking_request_id' not in st.session_state:
    st.session_state.selected_booking_request_id = None
if 'is_view_only' not in st.session_state:
    st.session_state.is_view_only = False
if 'show_disapprove_item_dialog' not in st.session_state:
    st.session_state.show_disapprove_item_dialog = False
if 'disapprove_item_order_id' not in st.session_state:
    st.session_state.disapprove_item_order_id = None
if 'disapprove_item_index' not in st.session_state:
    st.session_state.disapprove_item_index = None
if 'show_accounts_dialog' not in st.session_state:
    st.session_state.show_accounts_dialog = False
if 'show_notification_management_dialog' not in st.session_state:
    st.session_state.show_notification_management_dialog = False
if 'notification_management_on' not in st.session_state:
    st.session_state.notification_management_on = True
if 'scroll_to_bottom_accounts' not in st.session_state:
    st.session_state.scroll_to_bottom_accounts = False
if 'accounts_add_mode' not in st.session_state:
    st.session_state.accounts_add_mode = False
if 'highlight_new_account_row' not in st.session_state:
    st.session_state.highlight_new_account_row = False
if 'order_uploaded_files' not in st.session_state:
    st.session_state.order_uploaded_files = []
if 'order_uploaded_files_dialog' not in st.session_state:
    st.session_state.order_uploaded_files_dialog = []
if 'booking_uploaded_files_dialog' not in st.session_state:
    st.session_state.booking_uploaded_files_dialog = []
if 'booking_uploaded_files_tab' not in st.session_state:
    st.session_state.booking_uploaded_files_tab = []
if 'qr_welcome_shown' not in st.session_state:
    st.session_state.qr_welcome_shown = False
if 'show_image_viewer' not in st.session_state:
    st.session_state.show_image_viewer = False
if 'viewer_image_path' not in st.session_state:
    st.session_state.viewer_image_path = None
if 'viewer_product_name' not in st.session_state:
    st.session_state.viewer_product_name = None
if 'show_add_account_dialog' not in st.session_state:
    st.session_state.show_add_account_dialog = False
if 'show_manage_users_dialog' not in st.session_state:
    st.session_state.show_manage_users_dialog = False
if 'show_manage_products_dialog' not in st.session_state:
    st.session_state.show_manage_products_dialog = False
if 'user_to_edit' not in st.session_state:
    st.session_state.user_to_edit = None
if 'product_to_edit' not in st.session_state:
    st.session_state.product_to_edit = None

# File paths (use script directory so files are found regardless of CWD)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_CSV = os.path.join(_APP_DIR, 'products.csv')
ORDERS_CSV = os.path.join(_APP_DIR, 'orders.csv')
USERS_CSV = os.path.join(_APP_DIR, 'users.csv')
SEND_TXT = os.path.join(_APP_DIR, 'Send.txt')
ACCOUNTS_CSV = os.path.join(_APP_DIR, 'sales_order_LIST_OF_ACCOUNTS.csv')
EMAIL_LOG_FILE = os.path.join(_APP_DIR, 'email_notifications.log')
NOTIFICATION_ENABLED_FILE = os.path.join(_APP_DIR, 'notification_enabled.txt')
# Sample notifications are sent TO this address when "Sample Sending Notification" is clicked
SAMPLE_NOTIFICATION_RECIPIENT = 'subscription@innogen-pharma.com'

def get_notification_enabled():
    """Read notification enabled state from file. Default True if file missing."""
    try:
        if os.path.exists(NOTIFICATION_ENABLED_FILE):
            with open(NOTIFICATION_ENABLED_FILE, 'r', encoding='utf-8') as f:
                val = f.read().strip().lower()
                return val not in ('false', '0', 'off', 'no')
    except Exception:
        pass
    return True

def set_notification_enabled(enabled):
    """Write notification enabled state to file."""
    try:
        with open(NOTIFICATION_ENABLED_FILE, 'w', encoding='utf-8') as f:
            f.write('True' if enabled else 'False')
        return True
    except Exception:
        return False
APP_URL = 'https://so.solvang-pharma.com/'  # Sales Order app URL for email buttons

# Email configuration
# Gmail account for SMTP authentication (required for Gmail SMTP)
# If Send.txt only contains the App Password, set this constant to your Gmail account email
# Example: GMAIL_ACCOUNT = 'your-email@gmail.com'
GMAIL_ACCOUNT = 'no-reply@innogen-pharma.com'  # Gmail account for SMTP authentication
SENDER_DISPLAY_NAME = 'Solvang SO App'  # Display name shown in recipient inbox (instead of "no-reply")

# User credentials - Fetched from SQLite Database
def fetch_users_from_db():
    try:
        db_users = db.get_all_users()  # Returns Dict[str, Dict]
        
        # If no users found, try to initialize defaults
        if not db_users:
            print("No users found in DB. Initializing default users...")
            if hasattr(db, 'init_default_users'):
                db.init_default_users()
                db_users = db.get_all_users()
            else:
                print("Warning: init_default_users method missing from db instance")
        
        # Roles that get account_type 'admin' (vs Dispensing)
        admin_roles = ('Admin', 'Admin Level 0', 'Admin Level 1 Ethical', 'Admin Level 2', 'Ethical Staff Level 1', 'Finance Staff Level 2', 'Admin / Finance Staff', 'Finance Staff', 'SGF Manager')
        # Role -> (admin_level, view_only). Admin Level 0 = Super Admin; Ethical Level 1/2 = approvers; Ethical Staff Level 1/2 = view-only for that level.
        ROLE_ADMIN_LEVEL_VIEW_ONLY = {
            'Admin Level 0': (0, False),
            'Admin Level 1 Ethical': (1, False),
            'Admin Level 2': (2, False),
            'Ethical Staff Level 1': (1, True),
            'Finance Staff Level 2': (2, True),
        }
        users_dict = {}
        for username, user_data in db_users.items():
            role = normalize_role(user_data.get('role', ''))
            raw_account_type = user_data.get('account_type', '') or ''
            if not str(raw_account_type).strip():
                account_type = 'admin' if role in admin_roles else 'Dispensing'
            else:
                account_type = str(raw_account_type).strip()
            admin_level, view_only = ROLE_ADMIN_LEVEL_VIEW_ONLY.get(role, (None, False))
            users_dict[username] = {
                'password': user_data.get('password', ''),
                'role': role,
                'rep_code': user_data.get('rep_code') if user_data.get('rep_code') and str(user_data.get('rep_code')) != 'nan' else None,
                'rep_name': user_data.get('rep_name') if user_data.get('rep_name') and str(user_data.get('rep_name')) != 'nan' else None,
                'rep_company': user_data.get('rep_company') if user_data.get('rep_company') and str(user_data.get('rep_company')) != 'nan' else None,
                'rep_dept': user_data.get('rep_dept') if user_data.get('rep_dept') and str(user_data.get('rep_dept')) != 'nan' else None,
                'rep_area': user_data.get('rep_area') if user_data.get('rep_area') and str(user_data.get('rep_area')) != 'nan' else None,
                'account_type': account_type,
                'admin_level': admin_level,
                'view_only': view_only,
            }
        return users_dict
    except Exception as e:
        st.error(f"Error loading users from database: {e}")
        return {}

USERS = fetch_users_from_db()

# Helper Functions
def safe_float_convert(value, default=0.0):
    """Safely convert a value to float, handling strings with commas and other formatting"""
    if pd.isna(value) or value == '' or value is None:
        return default
    try:
        # If already a number, return as float
        if isinstance(value, (int, float)):
            return float(value)
        # Convert to string and remove commas, spaces, and other formatting
        value_str = str(value).strip().replace(',', '').replace(' ', '').replace('₱', '').replace('P', '').replace('$', '')
        # Try to convert to float
        return float(value_str) if value_str else default
    except (ValueError, TypeError):
        return default

def get_cart_items_with_empty_notes():
    """Return list of (index, product_name) for cart items with empty Notes/Remarks. Used to block submission."""
    result = []
    for idx, item in enumerate(st.session_state.get('cart', [])):
        notes = getattr(item, 'notes_remarks', '') or ''
        if not str(notes).strip():
            result.append((idx, getattr(item, 'product_name', f'Item {idx+1}')))
    return result

def apply_so_history_notes_to_cart(customer_name: str, only_fill_empty: bool = True) -> bool:
    """
    Auto-fill Notes/Remarks for cart items from SO_history based on customer + SKU.
    Uses most recent transaction per (customer, sku). Exact match only.
    "N/A" if no customer history, or no SKU match.
    When only_fill_empty=True (default): only replace items with empty/N/A notes; preserve user-edited values.
    """
    if not customer_name or not str(customer_name).strip():
        return False
    cart = st.session_state.get('cart', [])
    if not cart:
        return False
    lookup = db.get_so_history_notes_lookup(customer_name)
    updated = False
    for item in cart:
        current_notes = getattr(item, 'notes_remarks', '') or ''
        if only_fill_empty:
            # Only replace if empty, blank, or N/A
            if current_notes and str(current_notes).strip() and str(current_notes).strip().upper() != 'N/A':
                continue  # Preserve user-edited value
        pname = getattr(item, 'product_name', '') or ''
        key = str(pname).strip().upper()
        if not key:
            item.notes_remarks = 'N/A'
            updated = True
            continue
        notes = lookup.get(key, 'N/A') if lookup else 'N/A'
        item.notes_remarks = notes
        updated = True
    return updated

def safe_parse_cart_items(cart_items_str):
    """Safely parse cart items string, handling nan values and other edge cases"""
    if not cart_items_str or cart_items_str == '':
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
            # Use regex to match 'nan' only when it's a string value (not part of a word)
            # Replace 'nan' and "nan" with None, but be careful with context
            # Pattern: match 'nan' or "nan" that appears as a dictionary value
            cleaned_str = re.sub(r":\s*['\"]nan['\"]", ": None", cart_items_str, flags=re.IGNORECASE)
            # Also handle cases where nan appears without quotes (from pandas)
            cleaned_str = re.sub(r":\s*nan\b", ": None", cleaned_str, flags=re.IGNORECASE)
            cart_items = ast.literal_eval(cleaned_str)
        except (ValueError, SyntaxError):
            # If still fails, try a more aggressive approach: replace all 'nan' strings
            try:
                cleaned_str = cart_items_str.replace("'nan'", "None").replace('"nan"', "None")
                cleaned_str = cleaned_str.replace("'NaN'", "None").replace('"NaN"', "None")
                # Also handle unquoted nan
                cleaned_str = re.sub(r'\bnan\b', 'None', cleaned_str, flags=re.IGNORECASE)
                cart_items = ast.literal_eval(cleaned_str)
            except (ValueError, SyntaxError):
                # If still fails, return empty list
                return []
    
    # Clean up any None values that were 'nan' strings in nested dicts
    if isinstance(cart_items, list):
        for item in cart_items:
            if isinstance(item, dict):
                # Clean the main item dict
                for key, value in list(item.items()):
                    if isinstance(value, str) and value.lower() == 'nan':
                        item[key] = None
                    elif isinstance(value, dict):
                        # Clean nested dicts (like row_data)
                        for nested_key, nested_value in list(value.items()):
                            if isinstance(nested_value, str) and nested_value.lower() == 'nan':
                                value[nested_key] = None
    
    return cart_items if isinstance(cart_items, list) else []

def load_products():
    """Load products from SQLite Database"""
    try:
        return db.get_all_products()
    except Exception as e:
        st.error(f"Error loading products: {e}")
        return pd.DataFrame()

def get_logo_path():
    """Get logo image path"""
    logo_path = "product_images/solvang_logo.png"
    return logo_path

def get_image_base64(image_path):
    """Convert image to base64 string for HTML display"""
    import base64
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return ""

def display_logo(width=200):
    """Display the SOLVANG Pharmaceuticals logo"""
    logo_path = get_logo_path()
    # Prefer the actual logo image when available; fall back to text-only header if missing.
    try:
        if os.path.exists(logo_path):
            st.image(logo_path, width=width)
        else:
            raise FileNotFoundError
    except Exception:
        st.markdown("""
        <div style="text-align: center; padding: 20px;">
            <h2 style="color: #7B2CBF; margin: 0;">SOLVANG</h2>
            <p style="color: #7B2CBF; margin: 5px 0 0 0; font-size: 14px;">Pharmaceuticals, Inc.</p>
        </div>
        """, unsafe_allow_html=True)

def get_product_image_path(product_code, product_name=None):
    """Get product image path, generate default if missing"""
    image_path = f"product_images/{product_code}.png"
    
    # If image exists, return it
    if os.path.exists(image_path):
        return image_path
    
    # Generate default image if missing
    return generate_default_product_image(product_code, product_name)

def generate_default_product_image(product_code, product_name=None):
    """Generate a default/placeholder product image"""
    from PIL import Image, ImageDraw, ImageFont
    
    # Default placeholder image path
    default_image_path = f"product_images/{product_code}.png"
    
    # Create product_images folder if it doesn't exist
    os.makedirs("product_images", exist_ok=True)
    
    # Default gray color for placeholder
    default_color = (220, 220, 220)  # Light gray
    
    # Create image
    width, height = 300, 300
    image = Image.new('RGB', (width, height), default_color)
    draw = ImageDraw.Draw(image)
    
    # Try to load font
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
        font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    except (OSError, IOError):
        try:
            font_large = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
    
    # Draw product code
    text = product_code
    bbox = draw.textbbox((0, 0), text, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) / 2
    y = (height - text_height) / 2 - 40
    draw.text((int(x), int(y)), text, fill=(100, 100, 100), font=font_large)
    
    # Draw "No Image" text
    placeholder_text = "No Image"
    bbox = draw.textbbox((0, 0), placeholder_text, font=font_small)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) / 2
    y = (height - text_height) / 2 + 20
    draw.text((int(x), int(y)), placeholder_text, fill=(150, 150, 150), font=font_small)
    
    # Draw product name if provided
    if product_name:
        name = product_name[:30] + "..." if len(product_name) > 30 else product_name
        bbox = draw.textbbox((0, 0), name, font=font_small)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) / 2
        y = (height - text_height) / 2 + 45
        draw.text((int(x), int(y)), name, fill=(120, 120, 120), font=font_small)
    
    # Save the default image
    try:
        image.save(default_image_path, 'PNG')
    except Exception:
        # If we can't save, return a placeholder path (image won't display but won't crash)
        pass
    
    return default_image_path

def get_orders_by_tag(rep_code, tag_type):
    """Get orders filtered by tag column matching rep_code.
    tag_type: 'PMR_tag', 'TSR_tag', 'DSMBU7_tag', 'DSMPSI_tag', 'DSM' (both BU7 and SPI),
    'TSR_or_PMR' (TSR_tag OR PMR_tag), or 'ALL' (TSR_tag OR PMR_tag OR DSMBU7_tag OR DSMPSI_tag).
    Common ID: user's rep_code must match the account tag stored in the order when it was submitted."""
    orders_df = load_orders()
    if orders_df.empty or not rep_code:
        return pd.DataFrame()
    rep = str(rep_code).strip()
    for tag_col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
        if tag_col not in orders_df.columns:
            orders_df[tag_col] = ''
        orders_df[tag_col] = orders_df[tag_col].fillna('').astype(str).str.strip()
    if tag_type == 'ALL':
        mask = (
            (orders_df['TSR_tag'] == rep) | (orders_df['PMR_tag'] == rep) |
            (orders_df['DSMBU7_tag'] == rep) | (orders_df['DSMPSI_tag'] == rep)
        )
    elif tag_type == 'DSM':
        mask = (orders_df['DSMBU7_tag'] == rep) | (orders_df['DSMPSI_tag'] == rep)
    elif tag_type == 'TSR_or_PMR':
        mask = (orders_df['TSR_tag'] == rep) | (orders_df['PMR_tag'] == rep)
    elif tag_type in ('PMR_tag', 'TSR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
        mask = orders_df[tag_type] == rep
    else:
        return pd.DataFrame()
    return orders_df[mask].sort_values('OrderDate', ascending=False).reset_index(drop=True)

def get_booking_requests_by_tag(rep_code):
    """Get booking requests where rep_code matches tsr_code OR account tags (TSR_tag, PMR_tag, DSMBU7_tag, DSMPSI_tag).
    Uses client_name to look up account tags."""
    if not rep_code:
        return pd.DataFrame()
    rep = str(rep_code).strip()
    br_df = db.get_all_booking_requests(status_filter=None)
    if br_df.empty:
        return pd.DataFrame()
    for col in ('tsr_code', 'client_name'):
        if col not in br_df.columns:
            br_df[col] = ''
        br_df[col] = br_df[col].fillna('').astype(str).str.strip()
    mask_tsr = br_df['tsr_code'] == rep
    accounts_df = load_accounts()
    if accounts_df.empty or 'Customer name' not in accounts_df.columns:
        return br_df[mask_tsr].sort_values('created_date', ascending=False).reset_index(drop=True)
    for tag_col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
        if tag_col not in accounts_df.columns:
            accounts_df[tag_col] = ''
        accounts_df[tag_col] = accounts_df[tag_col].fillna('').astype(str).str.strip()
    account_tag_match = (
        (accounts_df['TSR_tag'] == rep) | (accounts_df['PMR_tag'] == rep) |
        (accounts_df['DSMBU7_tag'] == rep) | (accounts_df['DSMPSI_tag'] == rep)
    )
    related_clients = set(accounts_df.loc[account_tag_match, 'Customer name'].astype(str).str.strip().tolist())
    mask_client = br_df['client_name'].apply(lambda x: str(x).strip() in related_clients)
    combined = br_df[mask_tsr | mask_client].drop_duplicates(subset=['request_id'])
    return combined.sort_values('created_date', ascending=False).reset_index(drop=True)

def load_orders():
    """Load orders from SQLite Database"""
    try:
        df = db.get_all_orders()
        if df.empty:
            # Create empty DF with correct columns for compatibility
            df = pd.DataFrame(columns=[
                'OrderID', 'OrderDate', 'Status', 'Printed', 'PrintedDate', 'PrintedTime',
                'ApprovedBySGF', 'ApprovedDateSGF', 'ApprovedByLevel1', 'ApprovedDateLevel1', 
                'ApprovedByLevel2', 'ApprovedDateLevel2', 'DisapprovedItems', 'ClientName', 
                'ClientDescription', 'ClientMobile', 'BillingAddress', 'ShippingAddress', 
                'ContactPerson1', 'ContactPerson1Mobile', 'ContactPerson2', 'ContactPerson2Mobile', 
                'PaymentTerms', 'DeliveryTerms', 'DeliveryDate', 'DiscountPercent', 'DiscountAmount', 
                'Subtotal', 'TotalAmount', 'Notes', 'Remarks', 'RepCode', 'RepName', 'RepCompany', 
                'RepDept', 'RepArea', 'ReviewedBy', 'ReviewedDate', 'CreatedBy', 'BR_CreatedBy',
                'BookingRequestID', 'CartItems', 'Attachments',
                'TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'
            ])
            return df

        # Ensure new approval columns exist for backward compatibility
        if 'ApprovedByLevel1' not in df.columns:
            df['ApprovedByLevel1'] = ''
        if 'ApprovedDateLevel1' not in df.columns:
            df['ApprovedDateLevel1'] = ''
        if 'ApprovedByLevel2' not in df.columns:
            df['ApprovedByLevel2'] = ''
        if 'ApprovedDateLevel2' not in df.columns:
            df['ApprovedDateLevel2'] = ''
        # Ensure SGF approval columns exist
        if 'ApprovedBySGF' not in df.columns:
            df['ApprovedBySGF'] = ''
        if 'ApprovedDateSGF' not in df.columns:
            df['ApprovedDateSGF'] = ''
        # Fill NaN values with empty strings for these columns
        df['ApprovedByLevel1'] = df['ApprovedByLevel1'].fillna('')
        df['ApprovedDateLevel1'] = df['ApprovedDateLevel1'].fillna('')
        df['ApprovedByLevel2'] = df['ApprovedByLevel2'].fillna('')
        df['ApprovedDateLevel2'] = df['ApprovedDateLevel2'].fillna('')
        df['ApprovedBySGF'] = df['ApprovedBySGF'].fillna('')
        df['ApprovedDateSGF'] = df['ApprovedDateSGF'].fillna('')
        # Ensure DisapprovedItems column exists
        if 'DisapprovedItems' not in df.columns:
            df['DisapprovedItems'] = '[]'
        df['DisapprovedItems'] = df['DisapprovedItems'].fillna('[]')
        # Ensure Attachments column exists for backward compatibility
        if 'Attachments' not in df.columns:
            df['Attachments'] = ''
        df['Attachments'] = df['Attachments'].fillna('')
        # Ensure booking request linkage columns exist for backward compatibility
        if 'BR_CreatedBy' not in df.columns:
            df['BR_CreatedBy'] = ''
        if 'BookingRequestID' not in df.columns:
            df['BookingRequestID'] = ''
        df['BR_CreatedBy'] = df['BR_CreatedBy'].fillna('')
        df['BookingRequestID'] = df['BookingRequestID'].fillna('')
        # Ensure tag columns exist for backward compatibility
        for tag_col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
            if tag_col not in df.columns:
                df[tag_col] = ''
            df[tag_col] = df[tag_col].fillna('')
        return df
    except Exception as e:
        st.error(f"Error loading orders: {e}")
        return pd.DataFrame()

def prepare_orders_csv_data(orders_df):
    """Prepare orders data for CSV export with complete details including cart items"""
    if orders_df.empty:
        return pd.DataFrame()
    
    # Create expanded rows - one row per product in each order
    export_data = []
    
    for idx, order_row in orders_df.iterrows():
        # Parse cart items
        cart_items_str = order_row.get('CartItems', '[]')
        cart_items = safe_parse_cart_items(cart_items_str)
        
        # If no cart items, create one row with order info only
        if not cart_items or len(cart_items) == 0:
            row_data = {
                'OrderID': order_row.get('OrderID', ''),
                'OrderDate': order_row.get('OrderDate', ''),
                'Status': order_row.get('Status', ''),
                'ClientName': order_row.get('ClientName', ''),
                'ClientDescription': order_row.get('ClientDescription', ''),
                'ClientMobile': order_row.get('ClientMobile', ''),
                'BillingAddress': order_row.get('BillingAddress', ''),
                'ShippingAddress': order_row.get('ShippingAddress', ''),
                'ContactPerson1': order_row.get('ContactPerson1', ''),
                'ContactPerson1Mobile': order_row.get('ContactPerson1Mobile', ''),
                'ContactPerson2': order_row.get('ContactPerson2', ''),
                'ContactPerson2Mobile': order_row.get('ContactPerson2Mobile', ''),
                'PaymentTerms': order_row.get('PaymentTerms', ''),
                'DeliveryTerms': order_row.get('DeliveryTerms', ''),
                'DeliveryDate': order_row.get('DeliveryDate', ''),
                'DiscountPercent': order_row.get('DiscountPercent', 0),
                'DiscountAmount': order_row.get('DiscountAmount', 0),
                'Subtotal': order_row.get('Subtotal', 0),
                'TotalAmount': order_row.get('TotalAmount', 0),
                'Notes': order_row.get('Notes', ''),
                'Remarks': order_row.get('Remarks', ''),
                'RepCode': order_row.get('RepCode', ''),
                'RepName': order_row.get('RepName', ''),
                'RepCompany': order_row.get('RepCompany', ''),
                'RepDept': order_row.get('RepDept', ''),
                'RepArea': order_row.get('RepArea', ''),
                'ReviewedBy': order_row.get('ReviewedBy', ''),
                'ReviewedDate': order_row.get('ReviewedDate', ''),
                'CreatedBy': order_row.get('CreatedBy', ''),
                'ProductCode': '',
                'ProductName': '',
                'ProductQuantity': '',
                'ProductPrice': '',
                'ProductSubtotal': ''
            }
            export_data.append(row_data)
        else:
            # Create one row per product
            for item in cart_items:
                row_data = {
                    'OrderID': order_row.get('OrderID', ''),
                    'OrderDate': order_row.get('OrderDate', ''),
                    'Status': order_row.get('Status', ''),
                    'ClientName': order_row.get('ClientName', ''),
                    'ClientDescription': order_row.get('ClientDescription', ''),
                    'ClientMobile': order_row.get('ClientMobile', ''),
                    'BillingAddress': order_row.get('BillingAddress', ''),
                    'ShippingAddress': order_row.get('ShippingAddress', ''),
                    'ContactPerson1': order_row.get('ContactPerson1', ''),
                    'ContactPerson1Mobile': order_row.get('ContactPerson1Mobile', ''),
                    'ContactPerson2': order_row.get('ContactPerson2', ''),
                    'ContactPerson2Mobile': order_row.get('ContactPerson2Mobile', ''),
                    'PaymentTerms': order_row.get('PaymentTerms', ''),
                    'DeliveryTerms': order_row.get('DeliveryTerms', ''),
                    'DeliveryDate': order_row.get('DeliveryDate', ''),
                    'DiscountPercent': order_row.get('DiscountPercent', 0),
                    'DiscountAmount': order_row.get('DiscountAmount', 0),
                    'Subtotal': order_row.get('Subtotal', 0),
                    'TotalAmount': order_row.get('TotalAmount', 0),
                    'Notes': order_row.get('Notes', ''),
                    'Remarks': order_row.get('Remarks', ''),
                    'RepCode': order_row.get('RepCode', ''),
                    'RepName': order_row.get('RepName', ''),
                    'RepCompany': order_row.get('RepCompany', ''),
                    'RepDept': order_row.get('RepDept', ''),
                    'RepArea': order_row.get('RepArea', ''),
                    'ReviewedBy': order_row.get('ReviewedBy', ''),
                    'ReviewedDate': order_row.get('ReviewedDate', ''),
                    'CreatedBy': order_row.get('CreatedBy', ''),
                    'ProductCode': item.get('product_code', ''),
                    'ProductName': item.get('product_name', ''),
                    'ProductQuantity': item.get('qty', 0),
                    'ProductPrice': safe_float_convert(item.get('price', 0)),
                    'ProductSubtotal': safe_float_convert(item.get('qty', 0)) * safe_float_convert(item.get('price', 0))
                }
                export_data.append(row_data)
    
    # Create DataFrame and sort by OrderID
    export_df = pd.DataFrame(export_data)
    if not export_df.empty and 'OrderID' in export_df.columns:
        export_df = export_df.sort_values('OrderID')
    
    return export_df


def get_consolidated_so_history():
    """
    Consolidate app orders (exploded by cart item) with SO_history from CSV.
    Returns a unified DataFrame with all columns from both sources.
    Related columns: ClientName<->CUSTOMER NAME, RepCode<->REP CODE, OrderDate<->Full_DATE, etc.
    """
    from datetime import datetime
    orders_df = load_orders()
    so_history_df = db.get_so_history_df()
    
    # CSV columns (SO_history) - all must be present in output
    csv_cols = [
        'AREA', 'Address', 'CLASS CODE', 'CUSTOMER CODE', 'CUSTOMER NAME', 'NOTES/REMARKS',
        'SALES UNIT', 'FREE GOODS', 'DISCOUNT', 'DISTRICT', 'DISTRICT MANAGER', 'DSMBU7 CODE',
        'DSMPSI', 'DSMPSI CODE', 'GROSS SALES', 'REMARKS', 'REP CODE', 'REP NAME',
        'SALES DISCOUNT', 'SCR', 'SKU NAME', 'TERMS', 'TSR', 'TSR CODE',
        'Source_Sheet', 'Full_DATE', 'MONTH', 'YEAR'
    ]
    # App order columns (for rows from orders)
    app_cols = [
        'OrderID', 'OrderDate', 'Status', 'ClientName', 'RepCode', 'RepName',
        'BillingAddress', 'ShippingAddress', 'PaymentTerms', 'TotalAmount',
        'ProductCode', 'ProductName', 'ProductQuantity', 'ProductPrice', 'ProductSubtotal'
    ]
    all_cols = ['Source'] + list(dict.fromkeys(app_cols + csv_cols))
    
    rows = []
    
    # 1. Add rows from app orders (exploded by cart item)
    if not orders_df.empty:
        for _, order_row in orders_df.iterrows():
            cart_items = safe_parse_cart_items(order_row.get('CartItems', '[]'))
            order_date = order_row.get('OrderDate', '')
            try:
                dt = datetime.strptime(str(order_date)[:10], '%Y-%m-%d') if order_date else datetime.now()
                full_date = dt.strftime('%Y-%m-%d')
                month, year = dt.month, dt.year
            except (ValueError, TypeError):
                full_date, month, year = '', None, None
            
            if not cart_items:
                row = {'Source': 'App', 'OrderID': order_row.get('OrderID', ''), 'OrderDate': order_date,
                       'Status': order_row.get('Status', ''), 'ClientName': order_row.get('ClientName', ''),
                       'RepCode': order_row.get('RepCode', ''), 'RepName': order_row.get('RepName', ''),
                       'BillingAddress': order_row.get('BillingAddress', ''), 'ShippingAddress': order_row.get('ShippingAddress', ''),
                       'PaymentTerms': order_row.get('PaymentTerms', ''), 'TotalAmount': order_row.get('TotalAmount', 0),
                       'ProductCode': '', 'ProductName': '', 'ProductQuantity': '', 'ProductPrice': '', 'ProductSubtotal': '',
                       'CUSTOMER NAME': order_row.get('ClientName', ''), 'REP CODE': order_row.get('RepCode', ''),
                       'REP NAME': order_row.get('RepName', ''), 'Address': order_row.get('ShippingAddress', '') or order_row.get('BillingAddress', ''),
                       'TERMS': order_row.get('PaymentTerms', ''), 'GROSS SALES': order_row.get('TotalAmount', 0),
                       'SKU NAME': '', 'Full_DATE': full_date, 'MONTH': month, 'YEAR': year}
                for c in csv_cols:
                    if c not in row:
                        row[c] = None
                rows.append(row)
            else:
                for item in cart_items:
                    qty = int(item.get('qty', 0))
                    price = safe_float_convert(item.get('price', 0))
                    subtotal = qty * price
                    row = {'Source': 'App', 'OrderID': order_row.get('OrderID', ''), 'OrderDate': order_date,
                           'Status': order_row.get('Status', ''), 'ClientName': order_row.get('ClientName', ''),
                           'RepCode': order_row.get('RepCode', ''), 'RepName': order_row.get('RepName', ''),
                           'BillingAddress': order_row.get('BillingAddress', ''), 'ShippingAddress': order_row.get('ShippingAddress', ''),
                           'PaymentTerms': order_row.get('PaymentTerms', ''), 'TotalAmount': order_row.get('TotalAmount', 0),
                           'ProductCode': item.get('product_code', ''), 'ProductName': item.get('product_name', ''),
                           'ProductQuantity': qty, 'ProductPrice': price, 'ProductSubtotal': subtotal,
                           'CUSTOMER NAME': order_row.get('ClientName', ''), 'REP CODE': order_row.get('RepCode', ''),
                           'REP NAME': order_row.get('RepName', ''), 'Address': order_row.get('ShippingAddress', '') or order_row.get('BillingAddress', ''),
                           'TERMS': order_row.get('PaymentTerms', ''), 'GROSS SALES': subtotal,
                           'SKU NAME': item.get('product_name', ''), 'NOTES/REMARKS': item.get('notes_remarks', ''),
                           'Full_DATE': full_date, 'MONTH': month, 'YEAR': year}
                    for c in csv_cols:
                        if c not in row:
                            row[c] = None
                    rows.append(row)
    
    # 2. Add rows from SO_history (CSV)
    if not so_history_df.empty:
        for _, r in so_history_df.iterrows():
            row = {'Source': 'SO_History'}
            for c in so_history_df.columns:
                row[c] = r.get(c)
            for c in app_cols:
                if c not in row:
                    row[c] = None
            rows.append(row)
    
    if not rows:
        return pd.DataFrame(columns=all_cols)
    
    df = pd.DataFrame(rows)
    for c in all_cols:
        if c not in df.columns:
            df[c] = None
    return df[all_cols]


def display_cart_items_with_images(cart_items):
    """Display cart items with product images in a formatted way"""
    if not cart_items or len(cart_items) == 0:
        st.info("No items found in this order.")
        return
    
    st.markdown("### Order Items")
    
    for idx, item in enumerate(cart_items):
        product_code = item.get('product_code', 'N/A')
        product_name = item.get('product_name', 'N/A')
        qty = safe_float_convert(item.get('qty', 0))
        price = safe_float_convert(item.get('price', 0))
        subtotal = qty * price
        notes_remarks = item.get('notes_remarks', '')
        
        with st.container(border=True):
            col_img, col_info, col_qty, col_price = st.columns([1, 4, 1, 2])
            
            with col_img:
                # Get and display product image
                image_path = get_product_image_path(product_code, product_name)
                if os.path.exists(image_path):
                    st.image(image_path, width=120)
                else:
                    st.write("📦")  # Fallback placeholder
            
            with col_info:
                st.markdown(f"**{product_name}**")
                st.caption(f"Code: {product_code}")
                # Display Notes/Remarks if available with neon-green highlight
                if notes_remarks:
                    st.markdown(
                        f'<p style="background-color: #39FF14; padding: 4px 8px; border-radius: 4px; margin: 4px 0; font-size: 0.85rem; color: #000;">📝 Notes/Remarks: {notes_remarks}</p>',
                        unsafe_allow_html=True
                    )
            
            with col_qty:
                st.markdown(f"**Qty:** {qty}")
            
            with col_price:
                st.markdown(f"**Price:** {price:.2f}")
                st.markdown(f"**Subtotal:** {subtotal:.2f}")
    
    # Display summary
    total_items = sum(item.get('qty', 0) for item in cart_items)
    total_amount = sum(safe_float_convert(item.get('qty', 0)) * safe_float_convert(item.get('price', 0)) for item in cart_items)
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Items", total_items)
    with col2:
        st.metric("Total Amount", f"{total_amount:.2f}")

def display_cart_items_admin(order_id, cart_items, disapproved_items_list=None):
    """Display cart items with Remove/Disapprove buttons for admin"""
    if not cart_items or len(cart_items) == 0:
        st.info("No items found in this order.")
        return
    
    # Add CSS for button text shrinking and Notes/Remarks highlight

    
    st.markdown("### Order Items")
    
    # Get list of disapproved item indices
    disapproved_indices = []
    if disapproved_items_list:
        for dis_item in disapproved_items_list:
            if 'item_index' in dis_item:
                disapproved_indices.append(dis_item['item_index'])
    
    for idx, item in enumerate(cart_items):
        # Skip if this item is already disapproved
        if idx in disapproved_indices:
            continue
            
        product_code = item.get('product_code', 'N/A')
        product_name = item.get('product_name', 'N/A')
        qty = safe_float_convert(item.get('qty', 0))
        price = safe_float_convert(item.get('price', 0))
        subtotal = qty * price
        notes_remarks = item.get('notes_remarks', '')
        
        with st.container(border=True):
            col_img, col_info, col_qty, col_price, col_action = st.columns([1, 3, 1, 1.5, 1])
            
            with col_img:
                # Get and display product image
                image_path = get_product_image_path(product_code, product_name)
                if os.path.exists(image_path):
                    st.image(image_path, width=120)
                else:
                    st.write("📦")  # Fallback placeholder
            
            with col_info:
                st.markdown(f"**{product_name}**")
                st.caption(f"Code: {product_code}")
                # Display Notes/Remarks if available with neon-green highlight
                if notes_remarks:
                    st.markdown(
                        f'<p style="background-color: #39FF14; padding: 4px 8px; border-radius: 4px; margin: 4px 0; font-size: 0.85rem; color: #000;">📝 Notes/Remarks: {notes_remarks}</p>',
                        unsafe_allow_html=True
                    )
            
            with col_qty:
                st.markdown(f"**Qty:** {qty}")
            
            with col_price:
                st.markdown(f"**Price:** {price:.2f}")
                st.markdown(f"**Subtotal:** {subtotal:.2f}")
            
            with col_action:
                if st.button("❌ Remove\n/ Disapprove", key=f"disapprove_item_{order_id}_{idx}", use_container_width=True, type="secondary"):
                    st.session_state.disapprove_item_order_id = order_id
                    st.session_state.disapprove_item_index = idx
                    st.session_state.show_disapprove_item_dialog = True
                    st.rerun()
    
    # Display disapproved items if any
    if disapproved_items_list and len(disapproved_items_list) > 0:
        st.markdown("---")
        st.markdown("### ❌ Removed/Disapproved Items")
        for dis_item in disapproved_items_list:
            with st.container(border=True):
                st.error(f"**{dis_item.get('product_name', 'N/A')}** (Code: {dis_item.get('product_code', 'N/A')})")
                st.caption(f"**Reason:** {dis_item.get('disapproval_reason', 'N/A')}")
                st.caption(f"Removed by: {dis_item.get('disapproved_by', 'N/A')} on {dis_item.get('disapproved_date', 'N/A')}")
    
    # Display summary (only for remaining items)
    remaining_items = [item for idx, item in enumerate(cart_items) if idx not in disapproved_indices]
    total_items = sum(item.get('qty', 0) for item in remaining_items)
    total_amount = sum(safe_float_convert(item.get('qty', 0)) * safe_float_convert(item.get('price', 0)) for item in remaining_items)
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Remaining Items", total_items)
    with col2:
        st.metric("Total Amount (Remaining)", f"{total_amount:.2f}")

def save_orders(df):
    """Save orders to SQLite Database"""
    try:
        return db.save_orders_df(df)
    except Exception as e:
        st.error(f"Error saving orders: {e}")
        return False

def _normalize_accounts_df(df):
    """Apply standard cleanup to accounts dataframe (Customer code, Area, SGF)."""
    if df.empty:
        return df
    if 'Customer code' in df.columns:
        def clean_customer_code(value):
            if pd.isna(value) or value == '' or value is None:
                return ''
            try:
                return str(int(float(str(value))))
            except (ValueError, TypeError):
                return str(value).split('.')[0] if '.' in str(value) else str(value)
        df = df.copy()
        df['Customer code'] = df['Customer code'].apply(clean_customer_code)
        df['Customer code'] = df['Customer code'].astype('object')
    if 'Area' in df.columns:
        df['Area'] = df['Area'].fillna('').astype(str).replace('nan', '').replace('NaN', '').replace('None', '')
        df['Area'] = df['Area'].astype('object')
    if 'SGF' not in df.columns:
        df['SGF'] = 'FALSE'
    else:
        df['SGF'] = df['SGF'].fillna('FALSE').astype(str).str.upper()
    if 'SGF_count' not in df.columns:
        df['SGF_count'] = 99
    else:
        df['SGF_count'] = pd.to_numeric(df['SGF_count'], errors='coerce').fillna(99)
    return df

def load_accounts():
    """Load accounts from SQLite Database"""
    try:
        df = db.get_all_accounts()
        if df.empty:
            return pd.DataFrame()
        return _normalize_accounts_df(df)
    except Exception as e:
        st.error(f"Error loading accounts: {e}")
        return pd.DataFrame()

def save_accounts(df, customer_codes_to_delete=None):
    """Save accounts to SQLite Database. customer_codes_to_delete: list of obsolete codes to remove (e.g. 396.0 when consolidating to 396)."""
    try:
        return db.save_accounts_df(df, customer_codes_to_delete=customer_codes_to_delete)
    except Exception as e:
        st.error(f"Error saving accounts: {e}")
        return False

# Required account fields for Booking Request (TSR needs these when completing order)
BR_ACCOUNT_REQUIRED_FIELDS = [
    ('Contact number1', 'Mobile'),
    ('Business address', 'Business Address'),
    ('Credit term', 'Credit Term / Payment Terms'),
    ('Contact person1', 'Contact Person'),
]

def get_account_empty_required_fields(client_name):
    """Return list of (db_col, label) for account fields that are empty. Used when PMR/Sales Rep submits Booking Request."""
    accounts_df = load_accounts()
    if accounts_df.empty or not client_name or not str(client_name).strip():
        return []
    if 'Customer name' not in accounts_df.columns:
        return []
    row = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()]
    if row.empty:
        return []
    r = row.iloc[0]
    empty = []
    for db_col, label in BR_ACCOUNT_REQUIRED_FIELDS:
        if db_col not in accounts_df.columns:
            continue
        val = str(r.get(db_col, '') or '').strip()
        if not val:
            empty.append((db_col, label))
    return empty

def update_account_fields_by_client_name(client_name, field_updates):
    """Update account fields for the given client name. field_updates: dict of {db_col: new_value}. Returns True on success."""
    if not client_name or not str(client_name).strip() or not field_updates:
        return False
    accounts_df = load_accounts()
    if accounts_df.empty or 'Customer name' not in accounts_df.columns:
        return False
    idx = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()].index
    if len(idx) == 0:
        return False
    for col, val in field_updates.items():
        if col in accounts_df.columns:
            accounts_df.at[idx[0], col] = str(val).strip() if val else ''
    return save_accounts(accounts_df)

def save_order_attachments(order_id, uploaded_files):
    """Save uploaded files for an order and return list of file paths"""
    if not uploaded_files or len(uploaded_files) == 0:
        return []
    
    # Create order_attachments directory if it doesn't exist
    attachments_dir = f"order_attachments/{order_id}"
    os.makedirs(attachments_dir, exist_ok=True)
    
    saved_files = []
    for uploaded_file in uploaded_files:
        try:
            # Create unique filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            safe_filename = f"{timestamp}_{uploaded_file.name}"
            file_path = os.path.join(attachments_dir, safe_filename)
            
            # Save the file
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            saved_files.append(file_path)
        except Exception as e:
            st.warning(f"Error saving file {uploaded_file.name}: {e}")
    
    return saved_files

def save_booking_request_attachments(request_id, uploaded_files):
    """Save uploaded files for a booking request and return list of file paths"""
    if not uploaded_files or len(uploaded_files) == 0:
        return []
    
    attachments_dir = f"booking_request_attachments/{request_id}"
    os.makedirs(attachments_dir, exist_ok=True)
    
    saved_files = []
    for uploaded_file in uploaded_files:
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            safe_filename = f"{timestamp}_{uploaded_file.name}"
            file_path = os.path.join(attachments_dir, safe_filename)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            saved_files.append(file_path)
        except Exception as e:
            st.warning(f"Error saving file {uploaded_file.name}: {e}")
    
    return saved_files

def get_booking_request_attachments(request_id):
    """Get list of file paths for attachments uploaded with a booking request. Returns empty list if none."""
    attachments_dir = f"booking_request_attachments/{request_id}"
    if not os.path.isdir(attachments_dir):
        return []
    paths = []
    for fname in os.listdir(attachments_dir):
        fp = os.path.join(attachments_dir, fname)
        if os.path.isfile(fp):
            paths.append(fp)
    return sorted(paths)

def copy_booking_request_attachments_to_order(request_id, order_id):
    """Copy booking request attachments to order folder and return list of new paths for the order."""
    br_paths = get_booking_request_attachments(request_id)
    if not br_paths:
        return []
    order_dir = f"order_attachments/{order_id}"
    os.makedirs(order_dir, exist_ok=True)
    new_paths = []
    for src in br_paths:
        try:
            fname = os.path.basename(src)
            dst = os.path.join(order_dir, fname)
            shutil.copy2(src, dst)
            new_paths.append(dst)
        except Exception as e:
            st.warning(f"Error copying attachment {os.path.basename(src)}: {e}")
    return new_paths

def is_br_overdue(created_date_str, hours=24):
    """Check if booking request created_date is older than specified hours."""
    if not created_date_str or str(created_date_str).strip() in ('', 'N/A', 'nan'):
        return False
    try:
        dt_str = str(created_date_str)[:19]
        created_dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        return (datetime.now() - created_dt).total_seconds() >= hours * 3600
    except (ValueError, TypeError):
        return False

def display_order_attachments(attachments_str):
    """Display order attachments (images and PDFs)"""
    if not attachments_str or attachments_str.strip() == '':
        return
    
    try:
        # Parse attachments string (stored as string representation of list)
        attachments = ast.literal_eval(attachments_str) if isinstance(attachments_str, str) else attachments_str
        if not attachments or len(attachments) == 0:
            return
        
        st.markdown("### 📎 Attachments")
        
        # Group attachments by type
        image_files = []
        pdf_files = []
        
        for file_path in attachments:
            if not file_path or not os.path.exists(file_path):
                continue
            
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                image_files.append(file_path)
            elif file_ext == '.pdf':
                pdf_files.append(file_path)
        
        # Display images
        if image_files:
            st.markdown("**Images:**")
            # Display images in a grid
            num_cols = 3
            for i in range(0, len(image_files), num_cols):
                cols = st.columns(num_cols)
                for j, file_path in enumerate(image_files[i:i+num_cols]):
                    with cols[j]:
                        try:
                            st.image(file_path, use_container_width=True)
                            st.caption(os.path.basename(file_path))
                        except Exception as e:
                            st.error(f"Error displaying image: {os.path.basename(file_path)} ({e})")
        
        # Display PDFs - use link to open in new browser tab (avoids st.download_button in form)
        if pdf_files:
            st.markdown("**PDF Files:**")
            for file_path in pdf_files:
                file_name = os.path.basename(file_path)
                try:
                    # Get file size
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
                    with st.container(border=True):
                        st.markdown(f"📄 **{file_name}**")
                        st.caption(f"Size: {file_size:.2f} MB")
                        # Embed PDF in iframe (works inside forms, no download_button)
                        with open(file_path, "rb") as pdf_file:
                            pdf_data = pdf_file.read()
                            b64 = base64.b64encode(pdf_data).decode('utf-8')
                            pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" type="application/pdf"></iframe>'
                            st.markdown(pdf_display, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error displaying PDF {file_name}: {e}")
        
    except (ValueError, SyntaxError):
        # If parsing fails, try to display as single file path
        if attachments_str and os.path.exists(attachments_str):
            file_ext = os.path.splitext(attachments_str)[1].lower()
            if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                st.markdown("### 📎 Attachments")
                st.image(attachments_str, use_container_width=True)
                st.caption(os.path.basename(attachments_str))
            elif file_ext == '.pdf':
                st.markdown("### 📎 Attachments")
                with open(attachments_str, "rb") as pdf_file:
                    pdf_data = pdf_file.read()
                    b64 = base64.b64encode(pdf_data).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Error displaying attachments: {e}")

def get_active_accounts():
    """Get only active accounts for selectbox - uses same data as List of Accounts, filtered by Active"""
    try:
        # Use load_accounts() (same source as List of Accounts) then filter - ensures consistency
        df = load_accounts()
        if df.empty:
            return pd.DataFrame()
        if 'Active' not in df.columns:
            return pd.DataFrame()
        # Filter: only include Active in (TRUE, 1, YES, Y); exclude FALSE, 0, NO, N, blank
        active_vals = df['Active'].fillna('').astype(str).str.strip().str.upper()
        is_active = active_vals.isin(('TRUE', '1', 'YES', 'Y'))
        # CRITICAL: Exclude customer names where ANY row has Active=FALSE (handles duplicate rows e.g. 1556 vs 1556.0)
        df = df.copy()
        df['_is_active'] = is_active
        names_all_active = df.groupby(df['Customer name'].astype(str).str.strip())['_is_active'].all()
        active_names_set = set(names_all_active[names_all_active].index)
        df = df[df['Customer name'].astype(str).str.strip().isin(active_names_set) & is_active].drop(columns=['_is_active'])
        return df
    except Exception as e:
        st.error(f"Error loading active accounts: {e}")
        return pd.DataFrame()

def check_sgf_eligibility(client_name):
    """Check if account needs SGF workflow (SGF == True AND SGF_count < 3)"""
    accounts_df = load_accounts()
    if accounts_df.empty:
        return False
    
    # Find account by Customer name
    if 'Customer name' not in accounts_df.columns:
        return False
    
    account_row = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()]
    if account_row.empty:
        return False
    
    account = account_row.iloc[0]
    
    # Check SGF status
    sgf = account.get('SGF', 'FALSE')
    if isinstance(sgf, str):
        sgf = sgf.upper() == 'TRUE'
    else:
        sgf = bool(sgf)
    
    if not sgf:
        return False
    
    # Check SGF_count
    sgf_count = account.get('SGF_count', 99)
    try:
        sgf_count = int(float(sgf_count))
    except (ValueError, TypeError):
        sgf_count = 99
    
    # Return True if SGF == True AND SGF_count < 3
    return sgf_count < 3

def get_account_tags(client_name):
    """Get TSR_tag, PMR_tag, DSMBU7_tag, DSMPSI_tag from the account by client (customer) name"""
    accounts_df = load_accounts()
    if accounts_df.empty or 'Customer name' not in accounts_df.columns:
        return {'TSR_tag': '', 'PMR_tag': '', 'DSMBU7_tag': '', 'DSMPSI_tag': ''}
    account_row = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()]
    if account_row.empty:
        return {'TSR_tag': '', 'PMR_tag': '', 'DSMBU7_tag': '', 'DSMPSI_tag': ''}
    row = account_row.iloc[0]
    return {
        'TSR_tag': str(row.get('TSR_tag', '') or '').strip(),
        'PMR_tag': str(row.get('PMR_tag', '') or '').strip(),
        'DSMBU7_tag': str(row.get('DSMBU7_tag', '') or '').strip(),
        'DSMPSI_tag': str(row.get('DSMPSI_tag', '') or '').strip()
    }

def get_account_type_by_client_name(client_name):
    """Get account type (Dispensing, TRADE, Distribution, Contract) from the account by client (customer) name"""
    accounts_df = load_accounts()
    if accounts_df.empty or 'Customer name' not in accounts_df.columns:
        return 'Dispensing'  # Default to Dispensing if not found
    account_row = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()]
    if account_row.empty:
        return 'Dispensing'  # Default to Dispensing if not found
    row = account_row.iloc[0]
    account_type = str(row.get('Account_Type', 'Dispensing') or 'Dispensing').strip()
    return account_type if account_type else 'Dispensing'

def format_order_status_display(order_row):
    """Format order status for display, showing Level 2 for accounts that skip L1 (TRADE/Dispensing/Distribution)"""
    status = order_row.get('Status', 'N/A')
    approved_by_l1 = order_row.get('ApprovedByLevel1', '')
    
    # For legacy orders with SYSTEM approval (skip L1), show as "Pending for Approval 2"
    if status == 'Pending' and approved_by_l1 == 'SYSTEM':
        return 'Pending for Approval 2'
    
    return status

def increment_sgf_count(client_name):
    """Increment SGF_count by 1 for the specified account"""
    accounts_df = load_accounts()
    if accounts_df.empty:
        return False
    
    if 'Customer name' not in accounts_df.columns:
        return False
    
    account_idx = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()].index
    if len(account_idx) == 0:
        return False
    
    idx = account_idx[0]
    current_count = accounts_df.at[idx, 'SGF_count']
    try:
        current_count = int(float(current_count))
    except (ValueError, TypeError):
        current_count = 0
    
    accounts_df.at[idx, 'SGF_count'] = current_count + 1
    return save_accounts(accounts_df)

def load_users_csv():
    """Load users from CSV file"""
    if os.path.exists(USERS_CSV):
        try:
            df = pd.read_csv(USERS_CSV)
            return df
        except Exception as e:
            st.error(f"Error loading users: {e}")
            return pd.DataFrame()
    else:
        return pd.DataFrame()

def save_users_csv(df):
    """Save users to CSV file"""
    try:
        df.to_csv(USERS_CSV, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving users: {e}")
        return False

def load_all_users():
    """Load users from SQLite database (centralized single table)"""
    return fetch_users_from_db()

def log_email_notification(level, message, to_email=None, subject=None, error=None):
    """Log email notification events to file"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}]"
        
        if to_email:
            log_entry += f" To: {to_email}"
        if subject:
            log_entry += f" Subject: {subject}"
        if message:
            log_entry += f" | {message}"
        if error:
            log_entry += f" | Error: {str(error)}"
        
        log_entry += "\n"
        
        with open(EMAIL_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as log_error:
        # If logging fails, at least print to console
        print(f"Failed to write to log file: {log_error}")

def build_notification_email(title, salutation, message_html, button_text='Access App', highlight_value=None):
    """Build email body with standard format: purple banner, content, clickable button, footer."""
    highlight_div = f'<div class="count">{highlight_value}</div>' if highlight_value is not None else ''
    return f"""
    <html>
    <head>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Sales Order Management System</h2>
            </div>
            <div class="content">
                <h3>{title}</h3>
                <p>{salutation}</p>
                {message_html}
                {highlight_div}
                <p style="text-align: center;">
                    <a href="{APP_URL}" class="button" style="display: inline-block; padding: 15px 30px; background-color: #7B2CBF; color: #FFFFFF !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; font-size: 16px; border: 2px solid #FFFFFF; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">{button_text}</a>
                </p>
                <p><strong>Note:</strong> This is an automated notification. Please do not reply to this email.</p>
            </div>
            <div class="footer">
                <p>InnoGen's IT Department © 2026</p>
                <p>This is an automated email notification.</p>
            </div>
        </div>
    </body>
    </html>
    """

def send_email_notification(to_email, subject, body, sender_email=None, cc_emails=None, trigger_category=None):
    """Send email notification using Gmail with filtered CC list"""
    try:
        if not get_notification_enabled():
            log_email_notification("INFO", "Notifications disabled (toggle OFF). Skipping send.", to_email=to_email, subject=subject)
            return False
        log_email_notification("INFO", f"Attempting to send email (trigger: {trigger_category})", to_email=to_email, subject=subject)
        
        if not os.path.exists(SEND_TXT):
            log_email_notification("ERROR", "Send.txt file not found. Email notifications disabled.", to_email=to_email, subject=subject)
            st.warning("Send.txt file not found. Email notifications disabled.")
            return False
        
        # Read Send.txt - can contain email on first line and password on second line, or just password
        with open(SEND_TXT, 'r') as f:
            lines = f.readlines()
        
        # Parse Send.txt: can contain email on first line and password on second line, or just password
        if len(lines) >= 2:
            # Format: email on first line, password on second line
            gmail_account = lines[0].strip()
            password = lines[1].strip()
        else:
            # Format: only password (backward compatibility)
            password = lines[0].strip() if lines else ''
            gmail_account = ''
        
        # If Gmail account not in Send.txt, try to get it from constant or session state
        if not gmail_account or not gmail_account.strip():
            # First try the constant
            if GMAIL_ACCOUNT and GMAIL_ACCOUNT.strip():
                gmail_account = GMAIL_ACCOUNT.strip()
                log_email_notification("INFO", f"Using Gmail account from constant: {gmail_account}", to_email=to_email, subject=subject)
            # Then try session state
            elif st.session_state.get('gmail_account'):
                gmail_account = st.session_state.get('gmail_account').strip()
                log_email_notification("INFO", f"Using Gmail account from session state: {gmail_account}", to_email=to_email, subject=subject)
            else:
                # No Gmail account found anywhere
                log_email_notification("ERROR", "Gmail account not found. Please either: 1) Add Gmail account as first line in Send.txt, or 2) Set GMAIL_ACCOUNT constant in code.", to_email=to_email, subject=subject)
                st.error("""Email configuration error: Gmail account not found.

Please configure the Gmail account using ONE of these methods:

Method 1: Add to Send.txt (Recommended)
  Line 1: your-gmail-account@gmail.com
  Line 2: your-app-password

Method 2: Set in code (Contact developer)
  Update GMAIL_ACCOUNT constant in Sales_Order_Inventory_App.py""")
                return False
        
        # Validate password
        if not password or not password.strip():
            log_email_notification("ERROR", "Password not found in Send.txt. Please add App Password.", to_email=to_email, subject=subject)
            st.error("Email configuration error: Password not found in Send.txt file.\n\nPlease add your Gmail App Password to Send.txt.")
            return False
        
        # Set display "From" address (can be different from Gmail account)
        if not sender_email:
            sender_email = st.session_state.get('sender_email', 'no-reply@innogen-pharma.com')
        
        # Use display name so inbox shows "Solvang SO App" instead of "no-reply"
        from_header = f'"{SENDER_DISPLAY_NAME}" <{sender_email}>'
        
        smtp_server = 'smtp.gmail.com'
        smtp_port = 465
        
        log_email_notification("INFO", f"Connecting to SMTP server: {smtp_server}:{smtp_port} (SSL)", to_email=to_email, subject=subject)
        
        msg = MIMEMultipart()
        msg['From'] = from_header
        msg['To'] = to_email
        
        # Build CC list: from DB based on trigger_category if not provided
        if isinstance(cc_emails, str):
            cc_list = [cc_emails]
        elif cc_emails:
            cc_list = list(cc_emails)
        else:
            # Fetch filtered CC list from DB
            cc_list = db.get_cc_emails(trigger_category=trigger_category)
        
        if cc_list:
            cc_string = ', '.join(cc_list)
            msg['Cc'] = cc_string
            log_email_notification("INFO", f"CC recipients: {cc_string}", to_email=to_email, subject=subject)
        
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
            log_email_notification("INFO", f"SSL connection established, logging in with Gmail account: {gmail_account}", to_email=to_email, subject=subject)
            server.login(gmail_account, password)
            
            log_email_notification("INFO", f"Sending email message", to_email=to_email, subject=subject)
            # Prepare recipients list (To + CC)
            recipients = [to_email] + cc_list
            server.send_message(msg, to_addrs=recipients)
        
        log_email_notification("SUCCESS", f"Email sent successfully", to_email=to_email, subject=subject)
        return True
    except smtplib.SMTPAuthenticationError as e:
        log_email_notification("ERROR", f"SMTP Authentication failed", to_email=to_email, subject=subject, error=e)
        st.error(f"Error sending email: Authentication failed. Please check your email credentials.")
        return False
    except smtplib.SMTPRecipientsRefused as e:
        log_email_notification("ERROR", f"SMTP Recipients refused", to_email=to_email, subject=subject, error=e)
        st.error(f"Error sending email: Invalid recipient email address: {to_email}")
        return False
    except smtplib.SMTPServerDisconnected as e:
        log_email_notification("ERROR", f"SMTP Server disconnected", to_email=to_email, subject=subject, error=e)
        st.error(f"Error sending email: Server disconnected. Please check your internet connection.")
        return False
    except Exception as e:
        log_email_notification("ERROR", f"Unexpected error occurred", to_email=to_email, subject=subject, error=e)
        st.error(f"Error sending email: {e}")
        return False

def get_user_email(username):
    """Get email address for a user by username"""
    try:
        users_dict = db.get_all_users()
        if username in users_dict:
            email = users_dict[username].get('email')
            return email.strip() if email and email.strip() else None
        return None
    except Exception as e:
        log_email_notification("ERROR", f"Error getting user email for {username}", error=e)
        return None

def get_emails_by_role(role):
    """Get all email addresses for users with a specific role (includes fallback for old role names)"""
    try:
        users_dict = db.get_all_users()
        roles_to_check = [role]
        if role in ROLE_FALLBACK_LOOKUP:
            roles_to_check.extend(ROLE_FALLBACK_LOOKUP[role])
        emails = []
        seen = set()
        for username, user_data in users_dict.items():
            user_role = user_data.get('role', '')
            if user_role in roles_to_check:
                email = user_data.get('email')
                if email and email.strip() and email.strip() not in seen:
                    emails.append(email.strip())
                    seen.add(email.strip())
        return emails
    except Exception as e:
        log_email_notification("ERROR", f"Error getting emails for role {role}", error=e)
        return []

def get_rep_code_by_username(username):
    """Get rep_code for a user by username. Returns empty string if not found."""
    try:
        if not username or not str(username).strip():
            return ''
        users_dict = db.get_all_users()
        if username in users_dict:
            rc = users_dict[username].get('rep_code', '') or ''
            return str(rc).strip() if rc else ''
        return ''
    except Exception:
        return ''

def get_user_email_by_rep_code(rep_code):
    """Get email address for a user by rep_code"""
    try:
        if not rep_code or not str(rep_code).strip():
            return None
        users_dict = db.get_all_users()
        for username, user_data in users_dict.items():
            user_rep_code = user_data.get('rep_code', '')
            if user_rep_code and str(user_rep_code).strip() == str(rep_code).strip():
                email = user_data.get('email')
                return email.strip() if email and email.strip() else None
        return None
    except Exception as e:
        log_email_notification("ERROR", f"Error getting user email for rep_code {rep_code}", error=e)
        return None

def send_order_notification_to_rep(order_id, order_data, status_message, notification_type="status_update"):
    """
    Send notification to Sales Rep or TSR about their order
    notification_type: "submitted", "status_update", "approved", "disapproved"
    """
    try:
        created_by = order_data.get('CreatedBy', '')
        if not created_by:
            return
        
        # Get user email
        user_email = get_user_email(created_by)
        if not user_email:
            log_email_notification("INFO", f"Skipping notification for {created_by} - no email address", 
                                 to_email=None, subject=f"Order {order_id}")
            db.insert_notification_log(
                notification_type='order_to_rep',
                recipient_type='User',
                recipient_id=created_by,
                order_id=order_id,
                request_id='',
                status='Failed to Send',
                message=f'No email for user {created_by}',
                error_message='Recipient email is null or not configured'
            )
            return
        
        # Get user role to determine subject format
        users_dict = db.get_all_users()
        user_role = users_dict.get(created_by, {}).get('role', '')
        is_rep_or_tsr = user_role in ('Sales Rep', 'TSR')
        
        if not is_rep_or_tsr:
            return
        
        # Subject format: Order ID# for easy monitoring (same for all progress flow)
        subject = f"Order {order_id} - {status_message}"
        
        client_name = order_data.get('ClientName', 'N/A')
        account_type = get_account_type_by_client_name(client_name) if client_name and client_name != 'N/A' else 'N/A'
        order_date = order_data.get('OrderDate', 'N/A')
        total_amount = order_data.get('TotalAmount', 0)
        status = order_data.get('Status', 'N/A')
        msg = f"""<p>You have an order update.</p>
            <p><strong>Order ID:</strong> {order_id}</p>
            <p><strong>Status:</strong> {status}</p>
            <p><strong>Client:</strong> {client_name}</p>
            <p><strong>Account Type:</strong> {account_type}</p>
            <p><strong>Order Date:</strong> {order_date}</p>
            <p><strong>Total Amount:</strong> {total_amount:.2f}</p>
            <p><strong>Message:</strong> {status_message}</p>
            <p>Please log in to the Sales Order Management System to view details.</p>"""
        body = build_notification_email("Order Notification", f"Dear {created_by},", msg, "View Order")
        
        # Determine trigger category for CC filtering
        trigger_category = 'submission_approval'
        if "Fully approved" in status_message:
            trigger_category = 'fully_approved'
        elif "Disapproved" in status_message:
            trigger_category = 'disapproved'
        elif notification_type == "submitted" or "Approved by Level 1" in status_message:
            trigger_category = 'submission_approval'
            
        send_email_notification(user_email, subject, body, trigger_category=trigger_category)
        log_email_notification("SUCCESS", f"Sent {notification_type} notification to {created_by} for order {order_id}", 
                             to_email=user_email, subject=subject)
    except Exception as e:
        log_email_notification("ERROR", f"Error sending notification to rep for order {order_id}", error=e)

def send_notification_to_related_users(order_id, order_data, status_message, notification_type="status_update"):
    """
    Send notification to users whose rep_code matches account tags (TSR_tag, PMR_tag, DSMBU7_tag, DSMPSI_tag)
    This notifies related TSR/PMR/DSM users based on the account/customer tags
    """
    try:
        # Get account tags from order
        tsr_tag = order_data.get('TSR_tag', '') or ''
        pmr_tag = order_data.get('PMR_tag', '') or ''
        dsmbu7_tag = order_data.get('DSMBU7_tag', '') or ''
        dsmpsi_tag = order_data.get('DSMPSI_tag', '') or ''
        
        # Collect unique rep codes to notify
        rep_codes_to_notify = set()
        if tsr_tag and str(tsr_tag).strip():
            rep_codes_to_notify.add(str(tsr_tag).strip())
        if pmr_tag and str(pmr_tag).strip():
            rep_codes_to_notify.add(str(pmr_tag).strip())
        if dsmbu7_tag and str(dsmbu7_tag).strip():
            rep_codes_to_notify.add(str(dsmbu7_tag).strip())
        if dsmpsi_tag and str(dsmpsi_tag).strip():
            rep_codes_to_notify.add(str(dsmpsi_tag).strip())
        
        # Exclude the order creator - they already receive send_order_notification_to_rep
        creator_rep_code = (order_data.get('RepCode', '') or '').strip()
        if not creator_rep_code:
            created_by = (order_data.get('CreatedBy', '') or '').strip()
            if created_by:
                creator_rep_code = get_rep_code_by_username(created_by)
        if creator_rep_code:
            rep_codes_to_notify.discard(str(creator_rep_code).strip())
        
        if not rep_codes_to_notify:
            return
        
        subject = f"Related Order {order_id} - {status_message}"
        client_name = order_data.get('ClientName', 'N/A')
        account_type = get_account_type_by_client_name(client_name) if client_name and client_name != 'N/A' else 'N/A'
        order_date = order_data.get('OrderDate', 'N/A')
        total_amount = order_data.get('TotalAmount', 0)
        status = order_data.get('Status', 'N/A')
        created_by = order_data.get('CreatedBy', 'N/A')
        msg = f"""<p>A related order has been updated.</p>
            <p><strong>Order ID:</strong> {order_id}</p>
            <p><strong>Status:</strong> {status}</p>
            <p><strong>Client:</strong> {client_name}</p>
            <p><strong>Account Type:</strong> {account_type}</p>
            <p><strong>Created By:</strong> {created_by}</p>
            <p><strong>Message:</strong> {status_message}</p>
            <p><em>This order is related to your account based on account tags (TSR/PMR/DSM).</em></p>
            <p>Please log in to the Sales Order Management System to view details.</p>"""
        body = build_notification_email("Related Order Notification", "Dear User,", msg, "View Order")
        
        # Determine trigger category for CC filtering
        trigger_category = 'submission_approval'
        if "Fully approved" in status_message:
            trigger_category = 'fully_approved'
        elif "Disapproved" in status_message:
            trigger_category = 'disapproved'
        elif notification_type == "submitted" or "Approved by Level 1" in status_message:
            trigger_category = 'submission_approval'
            
        # Send notification to each related user
        for rep_code in rep_codes_to_notify:
            related_user_email = get_user_email_by_rep_code(rep_code)
            if related_user_email:
                send_email_notification(related_user_email, subject, body, trigger_category=trigger_category)
                log_email_notification("SUCCESS", f"Sent related user notification to rep_code {rep_code} for order {order_id}", 
                                     to_email=related_user_email, subject=subject)
            else:
                log_email_notification("INFO", f"Skipping notification for rep_code {rep_code} - no email address or user not found", 
                                     to_email=None, subject=f"Order {order_id}")
    except Exception as e:
        log_email_notification("ERROR", f"Error sending notification to related users for order {order_id}", error=e)

def send_booking_request_notification_to_tsr(request_id, tsr_code, tsr_name, client_name, shipping_date, 
                                            special_instructions, remarks, created_by):
    """
    Send notification to TSR when a booking request is submitted by Sales Rep
    """
    try:
        # Get TSR email by rep_code
        tsr_email = get_user_email_by_rep_code(tsr_code)
        if not tsr_email:
            log_email_notification("INFO", f"Skipping booking request notification for TSR {tsr_code} - no email address", 
                                 to_email=None, subject=f"Booking Request {request_id}")
            db.insert_notification_log(
                notification_type='booking_request_new',
                recipient_type='TSR',
                recipient_id=tsr_code,
                order_id='',
                request_id=request_id,
                status='Failed to Send',
                message=f'No email for TSR {tsr_code} ({tsr_name})',
                error_message='Recipient email is null or not configured'
            )
            return
        
        subject = f"Booking Request {request_id} - New Request from {created_by}"
        account_type = get_account_type_by_client_name(client_name) if client_name and client_name != 'N/A' else 'N/A'
        extra = ''
        if special_instructions:
            extra += f'<p><strong>Special Instructions:</strong> {special_instructions}</p>'
        if remarks:
            extra += f'<p><strong>Remarks:</strong> {remarks}</p>'
        msg = f"""<p>You have a new booking request.</p>
            <p><strong>Request ID:</strong> {request_id}</p>
            <p><strong>Client:</strong> {client_name}</p>
            <p><strong>Account Type:</strong> {account_type}</p>
            <p><strong>Shipping Date:</strong> {shipping_date}</p>
            <p><strong>Created By:</strong> {created_by}</p>
            <p><strong>Status:</strong> Pending</p>
            {extra}
            <p>Please log in to the Sales Order Management System to complete this booking request.</p>"""
        body = build_notification_email("New Booking Request", f"Dear {tsr_name},", msg, "Complete Booking Request")
        
        if send_email_notification(tsr_email, subject, body, trigger_category='booking'):
            db.insert_notification_log(
                notification_type='booking_request_new',
                recipient_type='TSR',
                recipient_id=tsr_code,
                order_id='',
                request_id=request_id,
                status='Sent',
                message=f'Sent to TSR {tsr_code} ({tsr_name})',
                error_message=None
            )
        log_email_notification("SUCCESS", f"Sent booking request notification to TSR {tsr_code} ({tsr_name}) for request {request_id}", 
                             to_email=tsr_email, subject=subject)
    except Exception as e:
        log_email_notification("ERROR", f"Error sending booking request notification to TSR {tsr_code} for request {request_id}", error=e)
        db.insert_notification_log(
            notification_type='booking_request_new',
            recipient_type='TSR',
            recipient_id=tsr_code,
            order_id='',
            request_id=request_id,
            status='Failed to Send',
            message=str(e),
            error_message=str(e)
        )

def send_booking_request_cancelled_by_creator_notification(request_id, tsr_code, tsr_name, client_name, created_by, reason):
    """Notify TSR when the creator (Sales Rep) cancels a booking request. Includes cancellation reason."""
    try:
        tsr_email = get_user_email_by_rep_code(tsr_code)
        if not tsr_email:
            log_email_notification("INFO", f"Skipping cancelled-by-creator notification for TSR {tsr_code} - no email address",
                                 to_email=None, subject=f"Booking Request {request_id} Cancelled")
            return
        subject = f"Booking Request {request_id} - Cancelled by {created_by}"
        reason_html = f"<p><strong>Reason for cancellation:</strong> {reason or 'Not provided'}</p>" if reason else "<p><strong>Reason for cancellation:</strong> Not provided</p>"
        msg = f"""<p>A booking request assigned to you has been cancelled by the person who created it.</p>
            <p><strong>Request ID:</strong> {request_id}</p>
            <p><strong>Client:</strong> {client_name}</p>
            <p><strong>Cancelled by:</strong> {created_by}</p>
            {reason_html}
            <p>You no longer need to complete this request. Please log in to the Sales Order Management System if you need more details.</p>"""
        body = build_notification_email("Booking Request Cancelled", f"Dear {tsr_name},", msg, "View App")
        if send_email_notification(tsr_email, subject, body, trigger_category='booking'):
            db.insert_notification_log(
                notification_type='booking_request_cancelled_by_creator',
                recipient_type='TSR',
                recipient_id=tsr_code,
                order_id='',
                request_id=request_id,
                status='Sent',
                message=f'Cancelled by {created_by}; reason sent to TSR',
                error_message=None
            )
        log_email_notification("SUCCESS", f"Sent cancelled-by-creator notification to TSR {tsr_code} for request {request_id}", to_email=tsr_email, subject=subject)
    except Exception as e:
        log_email_notification("ERROR", f"Error sending cancelled-by-creator notification for request {request_id}", error=e)

def send_approval_notification_to_admin(order_id, order_data, admin_level):
    """
    Send notification to Admin Level 1 Ethical or Admin Level 2 when order needs their approval
    """
    try:
        # Get emails for the specific admin level (Level 1 = Admin Level 1 Ethical)
        role = 'Admin Level 1 Ethical' if admin_level == 1 else f'Admin Level {admin_level}'
        admin_emails = get_emails_by_role(role)
        
        if not admin_emails:
            log_email_notification("INFO", f"No {role} users with email addresses found", 
                                 to_email=None, subject=f"Order {order_id}")
            db.insert_notification_log(
                notification_type=f'approval_level{admin_level}',
                recipient_type=role,
                recipient_id='',
                order_id=order_id,
                request_id='',
                status='Failed to Send',
                message=f'No {role} users with email addresses',
                error_message='No admin users have email configured'
            )
            return
        
        subject = f"Order {order_id} - Pending Level {admin_level} Approval"
        client_name = order_data.get('ClientName', 'N/A')
        account_type = get_account_type_by_client_name(client_name) if client_name and client_name != 'N/A' else 'N/A'
        order_date = order_data.get('OrderDate', 'N/A')
        total_amount = order_data.get('TotalAmount', 0)
        created_by = order_data.get('CreatedBy', 'N/A')
        status = order_data.get('Status', 'N/A')
        remarks = order_data.get('Remarks', '') or ''
        remarks_section = f'<p><strong>Remarks:</strong> {remarks}</p>' if remarks.strip() else ''
        msg = f"""<p>This order requires your Level {admin_level} approval.</p>
            <p><strong>Order ID:</strong> {order_id}</p>
            <p><strong>Status:</strong> {status}</p>
            <p><strong>Client:</strong> {client_name}</p>
            <p><strong>Account Type:</strong> {account_type}</p>
            <p><strong>Order Date:</strong> {order_date}</p>
            <p><strong>Total Amount:</strong> {total_amount:.2f}</p>
            <p><strong>Created By:</strong> {created_by}</p>
            {remarks_section}
            <p>Please log in to the Sales Order Management System to review and approve this order.</p>"""
        salutation = "Dear Admin Level 1 Ethical," if admin_level == 1 else f"Dear Admin Level {admin_level},"
        body = build_notification_email("Order Approval Required", salutation, msg, "Review Order")
        
        # Send to all admins at this level
        for admin_email in admin_emails:
            if send_email_notification(admin_email, subject, body, trigger_category='submission_approval'):
                db.insert_notification_log(
                    notification_type=f'approval_level{admin_level}',
                    recipient_type=role,
                    recipient_id=admin_email,
                    order_id=order_id,
                    request_id='',
                    status='Sent',
                    message=f'Sent to {admin_email}',
                    error_message=None
                )
            log_email_notification("SUCCESS", f"Sent Level {admin_level} approval notification to {admin_email} for order {order_id}", 
                                 to_email=admin_email, subject=subject)
    except Exception as e:
        log_email_notification("ERROR", f"Error sending approval notification to Level {admin_level} for order {order_id}", error=e)
        try:
            _role = 'Admin Level 1 Ethical' if admin_level == 1 else f'Admin Level {admin_level}'
            db.insert_notification_log(
                notification_type=f'approval_level{admin_level}',
                recipient_type=_role,
                recipient_id='',
                order_id=order_id,
                request_id='',
                status='Failed to Send',
                message=str(e),
                error_message=str(e)
            )
        except Exception:
            pass

def count_pending_approvals(admin_level):
    """Count pending approvals for a specific admin level"""
    orders_df = load_orders()
    
    if orders_df.empty:
        return 0
    
    # Ensure approval columns exist
    if 'ApprovedByLevel1' not in orders_df.columns:
        orders_df['ApprovedByLevel1'] = ''
    if 'ApprovedByLevel2' not in orders_df.columns:
        orders_df['ApprovedByLevel2'] = ''
    if 'ApprovedDateLevel1' not in orders_df.columns:
        orders_df['ApprovedDateLevel1'] = ''
    if 'ApprovedDateLevel2' not in orders_df.columns:
        orders_df['ApprovedDateLevel2'] = ''
    
    orders_df['ApprovedByLevel1'] = orders_df['ApprovedByLevel1'].fillna('')
    orders_df['ApprovedByLevel2'] = orders_df['ApprovedByLevel2'].fillna('')
    orders_df['ApprovedDateLevel1'] = orders_df['ApprovedDateLevel1'].fillna('')
    orders_df['ApprovedDateLevel2'] = orders_df['ApprovedDateLevel2'].fillna('')
    
    if admin_level == 1:
        # Count orders that are Pending for Approval 1 (or legacy Pending) and not yet approved by Level 1 (Contract and ex-SGF only)
        pending_count = len(orders_df[
            (orders_df['Status'].isin(['Pending', 'Pending for Approval 1'])) & 
            (orders_df['ApprovedByLevel1'] == '')
        ])
    elif admin_level == 2:
        # Count orders that are Pending for Approval 2 (or legacy Pending), approved by Level 1 (or SYSTEM for TRADE), but not yet by Level 2
        status_str = orders_df['Status'].fillna('').astype(str)
        pending_count = len(orders_df[
            (status_str.str.startswith('Pending for Approval 2') | (orders_df['Status'] == 'Pending')) & 
            (orders_df['ApprovedByLevel1'] != '') &
            (orders_df['ApprovedByLevel2'] == '')
        ])
    else:
        return 0
    
    return pending_count

def count_pending_sgf_approvals():
    """Count pending SGF approvals"""
    orders_df = load_orders()
    
    if orders_df.empty:
        return 0
    
    # Ensure SGF approval columns exist
    if 'ApprovedBySGF' not in orders_df.columns:
        orders_df['ApprovedBySGF'] = ''
    orders_df['ApprovedBySGF'] = orders_df['ApprovedBySGF'].fillna('')
    
    # Count orders that are "Pending for SGF" and not yet approved by SGF
    pending_count = len(orders_df[
        (orders_df['Status'] == 'Pending for SGF') & 
        (orders_df['ApprovedBySGF'] == '')
    ])
    
    return pending_count

def send_sgf_notification():
    """Send email notification to SGF Manager about pending approvals"""
    sgf_email = "marijo.caling@innogen-pharma.com"  # Update with actual SGF manager email
    sender_email = "no-reply@innogen-pharma.com"
    log_email_notification("INFO", "SGF notification function called")
    
    # Count pending approvals
    pending_count = count_pending_sgf_approvals()
    log_email_notification("INFO", f"Pending SGF approvals count: {pending_count}")
    
    if pending_count == 0:
        log_email_notification("INFO", "No pending SGF approvals, skipping email notification")
        return True
    
    subject = f"New Pending SGF Approvals - {pending_count} Order(s) Awaiting Review"
    msg = f"""<p>You have <strong>{pending_count} pending order(s)</strong> awaiting your SGF approval.</p>
        <p>Please log in to the Sales Order Management System to review and approve these orders.</p>"""
    body = build_notification_email("New Pending SGF Approvals Notification", "Dear Ma'am / Sir,", msg, "Review Orders", highlight_value=pending_count)
    
    try:
        log_email_notification("INFO", f"Preparing to send SGF notification to {sgf_email}", to_email=sgf_email, subject=subject)
        result = send_email_notification(sgf_email, subject, body, sender_email, trigger_category='submission_approval')
        if result:
            log_email_notification("SUCCESS", f"SGF notification sent successfully", to_email=sgf_email, subject=subject)
        else:
            log_email_notification("ERROR", f"SGF notification failed to send", to_email=sgf_email, subject=subject)
        return result
    except Exception as e:
        log_email_notification("ERROR", f"Exception in send_sgf_notification", to_email=sgf_email, subject=subject, error=e)
        print(f"Error sending SGF notification: {e}")
        return False

def send_approval_notification(admin_level):
    """Send email notification to admin about pending approvals"""
    # Admin email addresses
    admin_emails = {
        1: "tonette.segismundo@solvang-pharma.com",
        2: "merin.ediline@innogen-pharma.ph"
    }
    
    sender_email = "no-reply@innogen-pharma.com"
    
    log_email_notification("INFO", f"Admin approval notification function called for admin_level={admin_level}")
    
    if admin_level not in admin_emails:
        log_email_notification("ERROR", f"Invalid admin_level: {admin_level}. Valid levels: {list(admin_emails.keys())}")
        return False
    
    to_email = admin_emails[admin_level]
    log_email_notification("INFO", f"Target email for admin_level {admin_level}: {to_email}")
    
    # Count pending approvals
    pending_count = count_pending_approvals(admin_level)
    log_email_notification("INFO", f"Pending approvals count for admin_level {admin_level}: {pending_count}")
    
    if pending_count == 0:
        # No pending approvals, no need to send email
        log_email_notification("INFO", f"No pending approvals for admin_level {admin_level}, skipping email notification")
        return True
    
    subject = f"New Pending Approvals - {pending_count} Order(s) Awaiting Review"
    msg = f"""<p>You have <strong>{pending_count} pending order(s)</strong> awaiting your approval.</p>
        <p>Please log in to the Sales Order Management System to review and approve these orders.</p>"""
    body = build_notification_email("New Pending Approvals Notification", f"Dear Admin Level {admin_level},", msg, "Review Orders", highlight_value=pending_count)
    
    # Send email
    try:
        log_email_notification("INFO", f"Preparing to send admin approval notification to {to_email}", to_email=to_email, subject=subject)
        result = send_email_notification(to_email, subject, body, sender_email, trigger_category='submission_approval')
        if result:
            log_email_notification("SUCCESS", f"Admin approval notification sent successfully", to_email=to_email, subject=subject)
        else:
            log_email_notification("ERROR", f"Admin approval notification failed to send", to_email=to_email, subject=subject)
        return result
    except Exception as e:
        log_email_notification("ERROR", f"Exception in send_approval_notification", to_email=to_email, subject=subject, error=e)
        # Don't show error to user, just log it
        print(f"Error sending approval notification: {e}")
        return False

def resend_notification_for_order(order_id):
    """Determine and resend the appropriate notification based on order status"""
    orders_df = load_orders()
    order = orders_df[orders_df['OrderID'] == order_id]
    
    if order.empty:
        log_email_notification("ERROR", f"Order {order_id} not found for notification resend")
        return False, "Order not found"
    
    order_row = order.iloc[0]
    status = order_row.get('Status', '')
    approved_by_sgf = order_row.get('ApprovedBySGF', '')
    approved_by_l1 = order_row.get('ApprovedByLevel1', '')
    approved_by_l2 = order_row.get('ApprovedByLevel2', '')
    
    # Fill NaN values
    approved_by_sgf = '' if pd.isna(approved_by_sgf) else str(approved_by_sgf).strip()
    approved_by_l1 = '' if pd.isna(approved_by_l1) else str(approved_by_l1).strip()
    approved_by_l2 = '' if pd.isna(approved_by_l2) else str(approved_by_l2).strip()
    
    log_email_notification("INFO", f"Re-sending notification for order {order_id}. Status: {status}, SGF: {approved_by_sgf}, L1: {approved_by_l1}, L2: {approved_by_l2}")
    
    # Determine which notification to send based on order status and approval state
    if status == 'Pending for SGF' and not approved_by_sgf:
        # Order is pending SGF approval
        log_email_notification("INFO", f"Sending SGF notification for order {order_id}")
        result = send_sgf_notification()
        if result:
            return True, "SGF notification sent successfully"
        else:
            return False, "Failed to send SGF notification"
    
    elif (status in ('Pending', 'Pending for Approval 1') or (isinstance(status, str) and status.startswith('Pending for Approval 1'))) and not approved_by_l1:
        # Order is pending Level 1 approval
        log_email_notification("INFO", f"Sending Admin Level 1 Ethical notification for order {order_id}")
        result = send_approval_notification(admin_level=1)
        if result:
            return True, "Admin Level 1 Ethical notification sent successfully"
        else:
            return False, "Failed to send Admin Level 1 Ethical notification"
    
    elif (status in ('Pending', 'Pending for Approval 2') or (isinstance(status, str) and status.startswith('Pending for Approval 2'))) and approved_by_l1 and not approved_by_l2:
        # Order is pending Level 2 approval
        log_email_notification("INFO", f"Sending Admin Level 2 notification for order {order_id}")
        result = send_approval_notification(admin_level=2)
        if result:
            return True, "Admin Level 2 notification sent successfully"
        else:
            return False, "Failed to send Admin Level 2 notification"
    
    else:
        # Order doesn't need notification (already approved or in different state)
        log_email_notification("INFO", f"Order {order_id} does not require notification. Status: {status}")
        return False, f"Order status '{status}' does not require notification"

def sync_products_from_sql():
    """Sync products from SQL Server database"""
    try:
        # SQL Server connection details - USER MUST CONFIGURE THESE
        # This is a template - user needs to provide actual connection details
        server = st.text_input("SQL Server Address", value="localhost\\SQLEXPRESS", autocomplete="off")
        database = st.text_input("Database Name", value="YourDatabase", autocomplete="off")
        username = st.text_input("SQL Username", value="sa", autocomplete="off")
        password = st.text_input("SQL Password", type="password", autocomplete="off")
        table_name = st.text_input("Table Name", value="Products", autocomplete="off")
        
        if st.button("Connect and Sync"):
            connection_string = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
            conn = pyodbc.connect(connection_string)
            
            query = f"SELECT * FROM {table_name}"
            df = pd.read_sql(query, conn)
            conn.close()
            
            # Save to products.csv
            df.to_csv(PRODUCTS_CSV, index=False)
            st.success(f"Successfully synced {len(df)} products from SQL Server!")
            st.rerun()
            
    except Exception as e:
        st.error(f"Error syncing from SQL Server: {e}")
        return False

# Authentication
def authenticate(username, password):
    """Authenticate user"""
    all_users = load_all_users()
    print(f"DEBUG: Authenticating user '{username}'")
    
    if username in all_users:
        stored_password = all_users[username]['password']
        is_match = stored_password == password
        print(f"DEBUG: User found. Password match: {is_match}")
        
        if is_match:
            return True, all_users[username]['role'], all_users[username]
    else:
        print(f"DEBUG: User '{username}' not found. Available users: {list(all_users.keys())}")
        
    return False, None, None

def login_page():
    """Display login page"""
    # Display logo at the top, aligned to the left
    display_logo(width=250)
    
    st.title("🔐 Sales Order Management System")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                authenticated, role, user_info = authenticate(username, password)
                if authenticated:
                    st.session_state.authenticated = True
                    st.session_state.user_role = role
                    st.session_state.username = username
                    st.session_state.admin_level = user_info.get('admin_level')
                    st.session_state.is_view_only = user_info.get('view_only', False)
                    st.session_state.account_type = user_info.get('account_type', 'Dispensing')
                    if role in ('Sales Rep', 'TSR'):
                        st.session_state.rep_code = user_info.get('rep_code')
                        st.session_state.rep_name = user_info.get('rep_name')
                        st.session_state.rep_company = user_info.get('rep_company')
                        st.session_state.rep_dept = user_info.get('rep_dept')
                        st.session_state.rep_area = user_info.get('rep_area')
                    # Clear registration-specific widget state that can conflict with widgets after login
                    if 'reg_account_type' in st.session_state:
                        del st.session_state['reg_account_type']
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        registration_page()

def registration_page():
    """User registration page"""
    st.subheader("New User Registration")
    st.info("Please fill in all required fields to create your account.")
    
    with st.form("registration_form"):
        st.markdown("### Login Information")
        username = st.text_input("Username *", key="reg_username",
                                 help="Choose a unique username for login", autocomplete="username")
        password = st.text_input("Password *", type="password", key="reg_password", autocomplete="new-password")
        confirm_password = st.text_input("Confirm Password *", type="password", key="reg_confirm_password", autocomplete="new-password")
        email = st.text_input("Email Address *", key="reg_email",
                              help="Email address for order notifications (required)", autocomplete="email")
        
        st.markdown("---")
        st.markdown("### Representative Information")
        col1, col2 = st.columns(2)
        with col1:
            rep_code = st.text_input("Code *", key="reg_rep_code",
                                    help="Your representative code", autocomplete="off")
            rep_name = st.text_input("Name *", key="reg_rep_name",
                                    help="Your full name", autocomplete="off")
            rep_company = st.text_input("Company *", key="reg_rep_company",
                                       help="SPI Ethical or SPI Distribution", autocomplete="off")
        with col2:
            rep_dept = st.text_input("Dept/DSM District *", key="reg_rep_dept",
                                    help="Department name or DSM Territory", autocomplete="off")
            rep_area = st.text_input("Area/PMR *", key="reg_rep_area",
                                    help="Your assigned area", autocomplete="off")
            account_type = st.selectbox(
                "Type of account *",
                options=["Dispensing", "TRADE", "Distribution", "Contract"],
                key="reg_account_type",
            )
        
        submit_registration = st.form_submit_button("Register", type="primary")
        
        if submit_registration:
            # Validation
            if not username or not username.strip():
                st.error("Username is required")
                return
            
            if not password or password != confirm_password:
                st.error("Passwords do not match or are empty")
                return
            
            # Validate email - REQUIRED FIELD
            if not email or not email.strip():
                st.error("Email Address is required. Please enter a valid email address.")
                return
            
            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email.strip()):
                st.error("Please enter a valid email address")
                return
            
            # Check if username already exists
            all_users = load_all_users()
            if username in all_users:
                st.error(f"Username '{username}' already exists. Please choose a different username.")
                return
            
            # Validate all required fields
            required_fields = {
                'Code': rep_code,
                'Name': rep_name,
                'Company': rep_company,
                'Dept': rep_dept,
                'Area': rep_area
            }
            
            missing_fields = [field for field, value in required_fields.items() if not value or str(value).strip() == '']
            
            if missing_fields:
                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
            else:
                # Create user via database (centralized - same table as Manage Users)
                try:
                    user = User(
                        username=username.strip(),
                        password=password,
                        role='Sales Rep',
                        rep_code=str(rep_code or ''),
                        rep_name=str(rep_name or ''),
                        rep_company=str(rep_company or ''),
                        rep_dept=str(rep_dept or ''),
                        rep_area=str(rep_area or ''),
                        registration_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        account_type=account_type or 'Dispensing',
                        email=email.strip() if email and email.strip() else None
                    )
                    if db.upsert_user(user):
                        st.success(f"Registration successful! Username '{username}' has been created.")
                        st.info("You can now login with your new credentials.")
                        st.balloons()
                    else:
                        st.error("Error saving registration. Please try again.")
                except Exception as e:
                    st.error(f"Error saving registration: {e}")

# Submit Order Dialog Function
@st.dialog(title="📝 Submit Order", width="large", dismissible=True)
def submit_order_dialog():
    """Dialog function for submitting orders"""
    # CRITICAL: Early return if we just added to cart (prevents flash)
    # This is a final safeguard in case the dialog was already queued to render
    if st.session_state.get('just_added_to_cart', False):
        clear_all_dialog_states()
        st.session_state.just_added_to_cart = False
        return  # Exit immediately without rendering
    
    st.header("Submit New Order")
    
    if not st.session_state.cart:
        st.warning("Your cart is empty. Please add products from the Browse Products tab.")
        st.info("💡 You can close this dialog by clicking outside or pressing ESC.")
        # If cart is empty and dialog is shown, provide a close button
        if st.button("Close", type="secondary", use_container_width=True):
            clear_all_dialog_states()
            st.rerun()
    else:
        st.markdown("---")
        st.subheader("Order Details")
        
        # Cart summary - wrapped in form to prevent reruns on every edit
        st.markdown("### Cart Summary")
        # Validation error: show when submission blocked due to empty Notes/Remarks
        if st.session_state.get('submit_order_notes_validation_failed', False):
            items_missing = get_cart_items_with_empty_notes()
            names = ", ".join(n for _, n in items_missing[:5])
            if len(items_missing) > 5:
                names += f", and {len(items_missing)-5} more"
            st.error(f"⚠️ Cannot submit: Notes/Remarks is required for every SKU. Missing for: **{names}**. Fill in the table below and click **💾 Save Changes (Notes /Remarks)** before submitting.")
            st.session_state.submit_order_notes_validation_failed = False
        if st.session_state.get('dialog_notes_auto_filled', False):
            st.success("Notes/Remarks auto-filled from SO history for selected customer. Review and save if needed.")
            st.session_state.dialog_notes_auto_filled = False
        st.info("✏️ Fill in **Notes/Remarks** for each SKU in the table below. Click **💾 Save Changes (Notes /Remarks)** twice to save (first tap captures edits, second tap saves).")
        # Convert CartItems to dicts for DataFrame - use pending edit from first tap if awaiting second tap
        if st.session_state.get('dialog_awaiting_second_save', False) and 'dialog_pending_notes_edit' in st.session_state:
            display_df = st.session_state.dialog_pending_notes_edit.copy()
        else:
            cart_data = [item.dict() for item in st.session_state.cart]
            cart_df = pd.DataFrame(cart_data)
            display_df = cart_df[['product_name', 'qty', 'price', 'notes_remarks']].copy()
            display_df['Total'] = display_df['qty'] * display_df['price']
            display_df = display_df[['product_name', 'qty', 'price', 'Total', 'notes_remarks']]
            display_df.columns = ['product_name', 'qty', 'price', 'Total', 'Notes/Remarks']
        
        # Wrap data_editor in a form to prevent reruns on every cell edit
        with st.form("dialog_cart_update_form"):
            # Use data_editor with only Notes/Remarks editable
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "product_name": st.column_config.TextColumn("Product Name", disabled=True),
                    "qty": st.column_config.NumberColumn("Qty", disabled=True, format="%d"),
                    "price": st.column_config.NumberColumn("Price", disabled=True, format="%.2f"),
                    "Total": st.column_config.NumberColumn("Total", disabled=True, format="%.2f"),
                    "Notes/Remarks": st.column_config.TextColumn("Notes/Remarks", width="large")
                },
                use_container_width=True,
                key="dialog_cart_editor"
            )
            
            update_cart = st.form_submit_button("💾 Save Changes (Notes /Remarks)", type="primary", use_container_width=True)
        
        # Two-tap save: first tap captures edits, second tap saves to cart
        if update_cart and not edited_df.empty:
            awaiting = st.session_state.get('dialog_awaiting_second_save', False)
            if not awaiting:
                # First tap: store edited_df, set flag, rerun (gives time for cell to commit)
                st.session_state.dialog_pending_notes_edit = edited_df.copy()
                st.session_state.dialog_awaiting_second_save = True
                if 'tab_cart_editor' in st.session_state:
                    del st.session_state.tab_cart_editor
                st.rerun()
            else:
                # Second tap: save to cart and show success
                current_TSR_tag = st.session_state.get('account_TSR_tag', '')
                current_PMR_tag = st.session_state.get('account_PMR_tag', '')
                current_DSMBU7_tag = st.session_state.get('account_DSMBU7_tag', '')
                current_DSMPSI_tag = st.session_state.get('account_DSMPSI_tag', '')
                current_client = st.session_state.get('dialog_client_name_select', '')
                for idx, row in edited_df.iterrows():
                    if idx < len(st.session_state.cart):
                        val = row.get('Notes/Remarks', '')
                        if val is None or (isinstance(val, str) and not str(val).strip()):
                            val = '-'
                        st.session_state.cart[idx].notes_remarks = str(val).strip()
                if 'dialog_pending_notes_edit' in st.session_state:
                    del st.session_state.dialog_pending_notes_edit
                st.session_state.dialog_awaiting_second_save = False
                if 'tab_cart_editor' in st.session_state:
                    del st.session_state.tab_cart_editor
                if current_client and current_client != '':
                    st.session_state.dialog_client_name_select = current_client
                if current_TSR_tag:
                    st.session_state.account_TSR_tag = current_TSR_tag
                if current_PMR_tag:
                    st.session_state.account_PMR_tag = current_PMR_tag
                if current_DSMBU7_tag:
                    st.session_state.account_DSMBU7_tag = current_DSMBU7_tag
                if current_DSMPSI_tag:
                    st.session_state.account_DSMPSI_tag = current_DSMPSI_tag
                st.session_state.dialog_place_order_saved = True  # Persistent success message
                st.rerun()
        
        if st.session_state.get('dialog_place_order_saved', False):
            st.success("Notes/Remarks saved successfully!")
        
        st.markdown("---")
        # Request Booking checkbox - Sales Rep ONLY (TSR never sees this)
        request_booking = False
        if st.session_state.get('authenticated', False) and st.session_state.get('user_role') == 'Sales Rep':
            if 'dialog_request_booking' not in st.session_state:
                st.session_state.dialog_request_booking = True
            request_booking = st.checkbox(
                "Request Booking (TRADE - Med Rep requests TSR to complete order)",
                key="dialog_request_booking",
                help="Check to create a booking request for a TSR to complete. Uncheck to submit direct order for Contract accounts."
            )
        
        # Get active accounts for selectbox (OUTSIDE form)
        active_accounts = get_active_accounts()
        
        # For Sales Rep: filter by Account_Type based on Request Booking checkbox
        # Request Booking TRUE -> show non-Contract (Dispensing, TRADE, Distribution)
        # Request Booking FALSE -> show only Contract accounts
        if st.session_state.get('authenticated', False) and st.session_state.get('user_role') == 'Sales Rep':
            if not active_accounts.empty and 'Account_Type' in active_accounts.columns:
                at_vals = active_accounts['Account_Type'].fillna('').astype(str).str.strip().str.upper()
                if request_booking:
                    active_accounts = active_accounts[at_vals != 'CONTRACT'].copy()
                else:
                    active_accounts = active_accounts[at_vals == 'CONTRACT'].copy()
        
        # Show Related Accounts Only: filter by PMR_tag or TSR_tag = user's RepCode (default True)
        show_related_only = st.checkbox(
            "Show Related Accounts Only",
            value=True,
            key="dialog_show_related_only",
            help="Filter accounts where your RepCode matches the account's PMR_tag or TSR_tag. Uncheck to see all accounts."
        )
        if show_related_only and st.session_state.get('authenticated', False):
            rep_code = str(st.session_state.get('rep_code', '') or '').strip()
            if rep_code and not active_accounts.empty and 'PMR_tag' in active_accounts.columns and 'TSR_tag' in active_accounts.columns:
                pmr_match = active_accounts['PMR_tag'].fillna('').astype(str).str.strip() == rep_code
                tsr_match = active_accounts['TSR_tag'].fillna('').astype(str).str.strip() == rep_code
                active_accounts = active_accounts[pmr_match | tsr_match].copy()
        
        customer_options = ['']  # Start with empty option
        
        if not active_accounts.empty and 'Customer name' in active_accounts.columns:
            # Get unique customer names and sort them
            customer_names = active_accounts['Customer name'].astype(str).str.strip()
            customer_names = customer_names[customer_names != ''].unique()
            customer_options.extend(sorted(customer_names.tolist()))
        
        # CRITICAL: Clear session state if stored selection is no longer in active options
        # Streamlit selectbox preserves session state value even when not in options - would show inactive accounts
        stored = st.session_state.get('dialog_client_name_select', '')
        if stored and stored not in customer_options:
            st.session_state.dialog_client_name_select = ''
        
        # Callback function to update fields when customer selection changes
        def update_dialog_customer_fields():
            selected = st.session_state.dialog_client_name_select
            if selected and not active_accounts.empty:
                # Filter DataFrame to get the selected client's data
                client_row = active_accounts[active_accounts['Customer name'].astype(str).str.strip() == selected]
                if not client_row.empty:
                    client_details = client_row.iloc[0]
                    # Update widget keys directly in session state
                    st.session_state.dialog_client_description = str(client_details.get('Customer code', '')).strip() if 'Customer code' in active_accounts.columns else ''
                    st.session_state.dialog_client_mobile = str(client_details.get('Contact number1', '')).strip() if 'Contact number1' in active_accounts.columns else ''
                    billing_addr = str(client_details.get('Business address', '')).strip() if 'Business address' in active_accounts.columns else ''
                    st.session_state.dialog_billing_address = billing_addr
                    st.session_state.dialog_shipping_address = billing_addr
                    st.session_state.dialog_contact_person_1 = str(client_details.get('Contact person1', '')).strip() if 'Contact person1' in active_accounts.columns else ''
                    st.session_state.dialog_payment_terms = str(client_details.get('Credit term', '')).strip() if 'Credit term' in active_accounts.columns else ''
                    
                    # CRITICAL: Store account tags in session state for persistence
                    # These tags are needed for notifications even if not displayed in UI
                    tsr_tag = str(client_details.get('TSR_tag', '') or '').strip() if 'TSR_tag' in active_accounts.columns else ''
                    st.session_state.account_TSR_tag = tsr_tag
                    st.session_state.account_PMR_tag = str(client_details.get('PMR_tag', '') or '').strip() if 'PMR_tag' in active_accounts.columns else ''
                    st.session_state.account_DSMBU7_tag = str(client_details.get('DSMBU7_tag', '') or '').strip() if 'DSMBU7_tag' in active_accounts.columns else ''
                    st.session_state.account_DSMPSI_tag = str(client_details.get('DSMPSI_tag', '') or '').strip() if 'DSMPSI_tag' in active_accounts.columns else ''
                    # Auto-fill TSR Code when Request Booking is True - match account TSR_tag to TSR rep_code
                    if st.session_state.get('dialog_request_booking', False) and tsr_tag:
                        tsr_df = db.get_users_by_account_type("TRADE")
                        if not tsr_df.empty:
                            match = tsr_df[tsr_df['RepCode'].astype(str).str.strip() == tsr_tag]
                            if not match.empty:
                                row = match.iloc[0]
                                tsr_option = f"{row.get('RepCode', '') or ''} - {row.get('RepName', '') or ''}"
                                st.session_state.dialog_tsr_select = tsr_option
                    # Auto-fill Notes/Remarks from SO_history (customer + SKU match, most recent first)
                    if apply_so_history_notes_to_cart(selected.strip()):
                        if 'dialog_cart_editor' in st.session_state:
                            del st.session_state.dialog_cart_editor
                        st.session_state.dialog_notes_auto_filled = True
            else:
                # Clear fields when no customer selected
                st.session_state.dialog_client_description = ''
                st.session_state.dialog_client_mobile = ''
                st.session_state.dialog_billing_address = ''
                st.session_state.dialog_shipping_address = ''
                st.session_state.dialog_contact_person_1 = ''
                st.session_state.dialog_payment_terms = ''
                # Clear account tags
                st.session_state.account_TSR_tag = ''
                st.session_state.account_PMR_tag = ''
                st.session_state.account_DSMBU7_tag = ''
                st.session_state.account_DSMPSI_tag = ''
                if st.session_state.get('dialog_request_booking', False):
                    st.session_state.dialog_tsr_select = "(Select TSR)"
        
        # Initialize widget keys if they don't exist
        if 'dialog_client_description' not in st.session_state:
            st.session_state.dialog_client_description = ''
        if 'dialog_client_mobile' not in st.session_state:
            st.session_state.dialog_client_mobile = ''
        if 'dialog_billing_address' not in st.session_state:
            st.session_state.dialog_billing_address = ''
        if 'dialog_shipping_address' not in st.session_state:
            st.session_state.dialog_shipping_address = ''
        if 'dialog_contact_person_1' not in st.session_state:
            st.session_state.dialog_contact_person_1 = ''
        if 'dialog_payment_terms' not in st.session_state:
            st.session_state.dialog_payment_terms = ''
        
        # Initialize account tags in session state if they don't exist
        # These tags are needed for notifications even if not displayed in UI
        if 'account_TSR_tag' not in st.session_state:
            st.session_state.account_TSR_tag = ''
        if 'account_PMR_tag' not in st.session_state:
            st.session_state.account_PMR_tag = ''
        if 'account_DSMBU7_tag' not in st.session_state:
            st.session_state.account_DSMBU7_tag = ''
        if 'account_DSMPSI_tag' not in st.session_state:
            st.session_state.account_DSMPSI_tag = ''
        
        st.subheader("Client Information")
        
        # Client Name selectbox - OUTSIDE the form so on_change callback works
        _help = "Select a customer to auto-fill client details and Notes/Remarks from SO history (per SKU)"
        if st.session_state.get('user_role') == 'Sales Rep':
            _help += ". Request Booking checked = non-Contract accounts; unchecked = Contract only."
        selected_customer = st.selectbox(
            "Account / Customer Name *",
            options=customer_options,
            index=0,  # Default to empty option (first option is empty string)
            key="dialog_client_name_select",
            help=_help,
            on_change=update_dialog_customer_fields
        )
        
        # Get customer name
        client_name = selected_customer.strip() if selected_customer else ''
        
        # Show entire form only when an account is selected
        if not client_name:
            if len(customer_options) <= 1:
                tips = []
                if st.session_state.get('user_role') == 'Sales Rep':
                    tips.append("**Request Booking**: checked = Dispensing/TRADE/Distribution; unchecked = Contract only")
                if st.session_state.get('rep_code'):
                    tips.append("**Show Related Accounts Only**: uncheck to see all accounts")
                st.info("No accounts match the current filter. " + (" Try: " + "; ".join(tips) + "." if tips else "Uncheck **Show Related Accounts Only** to see all accounts."))
            else:
                st.info("Select a customer from the list above to view and edit client details.")
        elif request_booking:
            # --- TRADE Special Flow: Booking Request form (Med Rep requests TSR to complete) ---
            st.markdown("### Booking Request (TRADE - Med Rep requests TSR to complete)")
            tsr_df = db.get_users_by_account_type("TRADE")
            tsr_options = ["(Select TSR)"] + [f"{row.get('RepCode', '') or ''} - {row.get('RepName', '') or ''}" for _, row in tsr_df.iterrows()] if not tsr_df.empty else ["(Select TSR)"]
            
            with st.form("booking_request_form_dialog"):
                # Check if account has empty required fields - PMR/Sales Rep must complete before submitting
                empty_account_fields = get_account_empty_required_fields(client_name)
                if empty_account_fields:
                    st.warning("**Complete Account Fields** — The selected account has empty required fields. Please fill them in and click **Update Account** before submitting the booking request.")
                    accounts_df = load_accounts()
                    account_row = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()].iloc[0] if not accounts_df.empty else {}
                    for db_col, label in empty_account_fields:
                        key_safe = f"dialog_br_account_{db_col.replace(' ', '_')}"
                        current = str(account_row.get(db_col, '') or '').strip()
                        if db_col == 'Business address':
                            st.text_area(f"{label} *", value=current, key=key_safe, placeholder=f"Enter {label.lower()}...")
                        else:
                            st.text_input(f"{label} *", value=current, key=key_safe, placeholder=f"Enter {label.lower()}...", autocomplete="off")
                    update_account_btn = st.form_submit_button("Update Account", use_container_width=True)
                    if update_account_btn:
                        updates = {}
                        for db_col, _ in empty_account_fields:
                            key_safe = f"dialog_br_account_{db_col.replace(' ', '_')}"
                            val = st.session_state.get(key_safe, '')
                            updates[db_col] = str(val).strip() if val else ''
                        if updates and update_account_fields_by_client_name(client_name, updates):
                            st.success("Account updated successfully. You can now submit the booking request.")
                            st.rerun()
                        else:
                            st.error("Failed to update account. Please try again.")
                    st.markdown("---")
                # TSR Code selection - Name is hidden to avoid confusion (it's already included in the selectbox display)
                tsr_select = st.selectbox("TSR Code *", options=tsr_options, key="dialog_tsr_select", 
                                         help="Select TSR from the list. The name is included in the selection.")
                
                if tsr_select and tsr_select != "(Select TSR)":
                    parts = tsr_select.split(" - ", 1)
                    tsr_code_val = (parts[0] or "").strip()
                    tsr_name_val = (parts[1] or "").strip() if len(parts) > 1 else ""
                else:
                    tsr_code_val = ""
                    tsr_name_val = ""
                
                shipping_date_br = st.date_input("Shipping Date:", key="dialog_booking_shipping_date")
                special_instructions_br = st.text_area("Special Instructions", key="dialog_booking_special_instructions", placeholder="Enter special instructions...")
                
                # Attached / Uploading Files (shown instead of Remarks when Request Booking is True)
                st.markdown("### Attach File(s) (Optional)")
                uploaded_files_br = st.file_uploader(
                    "Attach file(s) (Pictures and PDFs only)",
                    type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'],
                    accept_multiple_files=True,
                    key="dialog_booking_file_uploader",
                    help="Attach multiple files. Each file must be 100MB or less. Supported formats: Images (PNG, JPG, JPEG, GIF, BMP, WEBP) and PDFs."
                )
                
                if uploaded_files_br:
                    valid_files_br = []
                    invalid_files_br = []
                    for uploaded_file in uploaded_files_br:
                        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
                        if file_size_mb > 100:
                            invalid_files_br.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB - exceeds 100MB limit)")
                        else:
                            valid_files_br.append(uploaded_file)
                    if invalid_files_br:
                        st.error("The following files exceed the 100MB limit:\n" + "\n".join(f"- {f}" for f in invalid_files_br))
                    if valid_files_br:
                        st.session_state.booking_uploaded_files_dialog = valid_files_br
                        st.success(f"✅ {len(valid_files_br)} file(s) ready to attach")
                        for i, file in enumerate(valid_files_br, 1):
                            file_size_mb = len(file.getvalue()) / (1024 * 1024)
                            st.caption(f"{i}. {file.name} ({file_size_mb:.2f} MB)")
                    else:
                        st.session_state.booking_uploaded_files_dialog = []
                else:
                    st.session_state.booking_uploaded_files_dialog = []
                
                st.markdown("---")
                submit_booking_btn = st.form_submit_button("Submit Booking", type="primary", use_container_width=True)
                
                if submit_booking_btn:
                    if empty_account_fields:
                        st.error("Please complete the account fields above and click **Update Account** before submitting the booking request.")
                    else:
                        items_empty = get_cart_items_with_empty_notes()
                        if items_empty:
                            st.session_state.submit_order_notes_validation_failed = True
                            st.rerun()
                        elif not tsr_code_val or not tsr_name_val:
                            st.error("Please select a TSR.")
                        elif not st.session_state.cart:
                            st.error("Cart is empty. Add products before submitting a booking request.")
                        else:
                            with st.spinner("Submitting booking request..."):
                                request_id = f"BR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
                                cart_items_json = json.dumps([item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart])
                                remarks_br = ''
                                ship_date_str = shipping_date_br.strftime('%Y-%m-%d')
                                created_by = st.session_state.get('username', '')
                                if db.create_booking_request(request_id, tsr_code_val, tsr_name_val, client_name,
                                        ship_date_str, special_instructions_br or '', remarks_br,
                                        cart_items_json, created_by):
                                    br_files = st.session_state.get('booking_uploaded_files_dialog', [])
                                    if br_files:
                                        save_booking_request_attachments(request_id, br_files)
                                    def _send_br_notif_dialog():
                                        try:
                                            send_booking_request_notification_to_tsr(
                                                request_id, tsr_code_val, tsr_name_val, client_name,
                                                ship_date_str, special_instructions_br or '', remarks_br, created_by
                                            )
                                        except Exception as e:
                                            print(f"Background booking notification error: {e}")
                                    threading.Thread(target=_send_br_notif_dialog, daemon=True).start()
                                    
                                    st.success("Booking request submitted successfully! Check Request/Order History to track status.")
                                    st.session_state.show_submit_order_dialog = False
                                    st.session_state.cart = []
                                    st.session_state.booking_uploaded_files_dialog = []
                                    if 'dialog_opened_timestamp' in st.session_state:
                                        del st.session_state['dialog_opened_timestamp']
                                    st.rerun()
                                else:
                                    st.error("Failed to save booking request. Please try again.")
        else:
            with st.form("order_form_dialog"):
                # Client fields - auto-fill from session state when customer is selected
                client_description = st.text_area(
                    "Client Category *", 
                    key="dialog_client_description"
                )
                client_mobile = st.text_input(
                    "Mobile *", 
                    key="dialog_client_mobile",
                    autocomplete="tel"
                )
                col1, col2 = st.columns(2)
                with col1:
                    billing_address = st.text_area(
                        "Billing Address *", 
                        key="dialog_billing_address"
                    )
                with col2:
                    shipping_address = st.text_area(
                        "Shipping Address *", 
                        key="dialog_shipping_address"
                    )
                
                # Initialize contact person and payment terms keys if they don't exist
                if 'dialog_contact_person_1' not in st.session_state:
                    st.session_state.dialog_contact_person_1 = ''
                if 'dialog_payment_terms' not in st.session_state:
                    st.session_state.dialog_payment_terms = ''
                
                st.markdown("---")
                st.markdown("### Contact Persons")
                col1, col2 = st.columns(2)
                with col1:
                    contact_person_1 = st.text_input(
                        "Contact Person 1", 
                        key="dialog_contact_person_1",
                        autocomplete="off"
                    )
                    contact_person_1_mobile = st.text_input("Contact Person 1 Mobile", key="dialog_contact_person_1_mobile", autocomplete="tel")
                with col2:
                    contact_person_2 = st.text_input("Contact Person 2", key="dialog_contact_person_2", autocomplete="off")
                    contact_person_2_mobile = st.text_input("Contact Person 2 Mobile", key="dialog_contact_person_2_mobile", autocomplete="tel")
                
                st.markdown("---")
                st.subheader("Order Terms")
                payment_terms = st.text_input(
                    "Payment Terms *", 
                    key="dialog_payment_terms", 
                    placeholder="e.g., Net 30, COD, etc.",
                    autocomplete="off"
                )
                delivery_terms = st.text_area("Delivery Instructions *", key="dialog_delivery_terms",
                                             placeholder="Enter delivery instructions...")
                col1, col2 = st.columns(2)
                with col1:
                    delivery_date = st.date_input("Delivery Date / Requested Ship Date *", key="dialog_delivery_date")
                with col2:
                    discount_percent = st.number_input("Discount (%)", min_value=0.0, max_value=100.0, 
                                                       value=0.0, step=0.1, key="dialog_discount_percent", disabled=True)
                
                # Calculate and display totals with discount
                subtotal_calc = sum(item.qty * item.price for item in st.session_state.cart)
                discount_amount_calc = (subtotal_calc * discount_percent) / 100
                total_calc = subtotal_calc - discount_amount_calc
                
                st.markdown("---")
                st.markdown("### Order Summary")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Subtotal", f"{subtotal_calc:.2f}")
                with col2:
                    if discount_percent > 0:
                        st.metric(f"Discount ({discount_percent}%)", f"-{discount_amount_calc:.2f}")
                    else:
                        st.metric("Discount", "0.00")
                with col3:
                    st.metric("**Total Amount**", f"**{total_calc:.2f}**")
                
                st.markdown("---")
                st.subheader("Additional Information")
                notes = st.text_area("Notes / Special Instructions", key="dialog_notes")
                remarks = st.text_area("Remarks", key="dialog_remarks")
            
                # File attach section
                st.markdown("### Attach File(s) (Optional)")
                uploaded_files = st.file_uploader(
                    "Attach file(s) (Pictures and PDFs only)",
                    type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'],
                    accept_multiple_files=True,
                    key="dialog_file_uploader",
                    help="Attach multiple files. Each file must be 100MB or less. Supported formats: Images (PNG, JPG, JPEG, GIF, BMP, WEBP) and PDFs."
                )
                
                # Validate file sizes and store valid files
                if uploaded_files:
                    valid_files = []
                    invalid_files = []
                    
                    for uploaded_file in uploaded_files:
                        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)  # Convert to MB
                        if file_size_mb > 100:
                            invalid_files.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB - exceeds 100MB limit)")
                        else:
                            valid_files.append(uploaded_file)
                    
                    if invalid_files:
                        st.error("The following files exceed the 100MB limit:\n" + "\n".join(f"- {f}" for f in invalid_files))
                    
                    if valid_files:
                        st.session_state.order_uploaded_files_dialog = valid_files
                        st.success(f"✅ {len(valid_files)} file(s) ready to attach")
                        # Display uploaded file names
                        for i, file in enumerate(valid_files, 1):
                            file_size_mb = len(file.getvalue()) / (1024 * 1024)
                            st.caption(f"{i}. {file.name} ({file_size_mb:.2f} MB)")
                    else:
                        st.session_state.order_uploaded_files_dialog = []
                else:
                    st.session_state.order_uploaded_files_dialog = []
                
                # Rep information (auto-filled but editable)
                st.markdown("---")
                st.subheader("Representative Information")
                col1, col2 = st.columns(2)
                with col1:
                    rep_code = st.text_input("Code *", value=st.session_state.rep_code, key="dialog_rep_code", autocomplete="off")
                    rep_name = st.text_input("Name *", value=st.session_state.rep_name, key="dialog_rep_name", autocomplete="off")
                    rep_company = st.text_input("Company *", value=st.session_state.rep_company, key="dialog_rep_company", autocomplete="off")
                with col2:
                    rep_dept = st.text_input("Dept/DSM District *", value=st.session_state.rep_dept, key="dialog_rep_dept", autocomplete="off")
                    rep_area = st.text_input("Area/PMR *", value=st.session_state.rep_area, key="dialog_rep_area", autocomplete="off")
                
                col1, col2 = st.columns(2)
                with col1:
                    submit_order = st.form_submit_button("Submit Order", type="primary", use_container_width=True)
                with col2:
                    cancel_order = st.form_submit_button("Cancel", use_container_width=True)
                
                if cancel_order:
                    st.session_state.show_submit_order_dialog = False
                    dialog_key = 'dialog_opened_timestamp'
                    if dialog_key in st.session_state:
                        del st.session_state[dialog_key]
                    st.rerun()
                
                if submit_order:
                    # Validation - require Notes/Remarks per SKU
                    items_empty = get_cart_items_with_empty_notes()
                    if items_empty:
                        st.session_state.submit_order_notes_validation_failed = True
                        st.rerun()
                    # Validation - ensure client_name is set (redundant when form is shown, but kept for safety)
                    elif not client_name or client_name.strip() == '':
                        st.error("Please select a client name from the dropdown.")
                    else:
                        # Get values from widgets (they reflect session state)
                        client_description_val = client_description
                        client_mobile_val = client_mobile
                        billing_address_val = billing_address
                        shipping_address_val = shipping_address
                        contact_person_1_val = contact_person_1
                        payment_terms_val = payment_terms
                        
                        # Validation
                        required_fields = {
                            'Client Name': client_name,
                            'Client Category': client_description_val,
                            'Mobile': client_mobile_val,
                            'Billing Address': billing_address_val,
                            'Shipping Address': shipping_address_val,
                            'Payment Terms': payment_terms_val,
                            'Delivery Instructions': delivery_terms,
                            'Code': rep_code,
                            'Name': rep_name,
                            'Company': rep_company,
                            'Dept': rep_dept,
                            'Area': rep_area
                        }
                        
                        missing_fields = [field for field, value in required_fields.items() if not value or value.strip() == '']
                        
                        if missing_fields:
                            st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                        else:
                            with st.spinner("Submitting order... Saving data and sending notifications."):
                                # Create order
                                orders_df = load_orders()
                                order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                
                                # Save uploaded files if any
                                uploaded_files_list = st.session_state.get('order_uploaded_files_dialog', [])
                                attachment_paths = []
                                if uploaded_files_list:
                                    attachment_paths = save_order_attachments(order_id, uploaded_files_list)
                                
                                # Calculate totals
                                subtotal = sum(item.qty * item.price for item in st.session_state.cart)
                                discount_amount = (subtotal * discount_percent) / 100
                                total_amount = subtotal - discount_amount
                                
                                # Check if account needs SGF workflow
                                needs_sgf = check_sgf_eligibility(client_name)
                                
                                # Get account type and determine approval workflow
                                # Contract → Pending for Approval 1 (Level 1 then Level 2). TRADE/Dispensing/Distribution → skip L1.
                                account_type = get_account_type_by_client_name(client_name)
                                account_type_upper = account_type.upper()
                                skip_level1 = account_type_upper in ('TRADE', 'DISPENSING', 'DISTRIBUTION')
                                if needs_sgf:
                                    initial_status = 'Pending for SGF'
                                    approved_by_l1 = ''
                                    approved_date_l1 = ''
                                elif skip_level1:
                                    initial_status = 'Pending for Approval 2'
                                    approved_by_l1 = 'SYSTEM'
                                    approved_date_l1 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                else:
                                    # Contract only: go through Level 1 first
                                    initial_status = 'Pending for Approval 1'
                                    approved_by_l1 = ''
                                    approved_date_l1 = ''
                                
                                # Get account tags from selected account
                                account_tags = get_account_tags(client_name)
                                
                                # Create order record
                                order_data = {
                                'OrderID': order_id,
                                'OrderDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'Status': initial_status,
                                'Printed': '',
                                'PrintedDate': '',
                                'PrintedTime': '',
                                'ApprovedBySGF': '',
                                'ApprovedDateSGF': '',
                                'ApprovedByLevel1': approved_by_l1,
                                'ApprovedDateLevel1': approved_date_l1,
                                'ApprovedByLevel2': '',
                                'ApprovedDateLevel2': '',
                                'DisapprovedItems': '[]',
                                'ClientName': client_name,
                                'ClientDescription': client_description_val,
                                'ClientMobile': client_mobile_val,
                                'BillingAddress': billing_address_val,
                                'ShippingAddress': shipping_address_val,
                                'ContactPerson1': contact_person_1_val,
                                'ContactPerson1Mobile': contact_person_1_mobile,
                                'ContactPerson2': contact_person_2,
                                'ContactPerson2Mobile': contact_person_2_mobile,
                                'PaymentTerms': payment_terms_val,
                                'DeliveryTerms': delivery_terms,
                                'DeliveryDate': delivery_date.strftime('%Y-%m-%d'),
                                'DiscountPercent': discount_percent,
                                'DiscountAmount': discount_amount,
                                'Subtotal': subtotal,
                                'Notes': notes,
                                'RepCode': rep_code,
                                'RepName': rep_name,
                                'RepCompany': rep_company,
                                'RepDept': rep_dept,
                                'RepArea': rep_area,
                                'Remarks': remarks,
                                'TotalAmount': total_amount,
                                'CartItems': str([item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart]),
                                'Attachments': str(attachment_paths) if attachment_paths else '',
                                'CreatedBy': st.session_state.username,
                                'TSR_tag': account_tags['TSR_tag'],
                                'PMR_tag': account_tags['PMR_tag'],
                                'DSMBU7_tag': account_tags['DSMBU7_tag'],
                                'DSMPSI_tag': account_tags['DSMPSI_tag']
                            }
                            
                            # Add to orders DataFrame
                            new_order_df = pd.DataFrame([order_data])
                            if orders_df.empty:
                                orders_df = new_order_df
                            else:
                                orders_df = pd.concat([orders_df, new_order_df], ignore_index=True)
                            
                            if save_orders(orders_df):
                                # Send email notifications in background (don't block UI)
                                def _send_dialog_notifications():
                                    try:
                                        send_order_notification_to_rep(order_id, order_data.copy(), 
                                                                      "Order submitted successfully", 
                                                                      notification_type="submitted")
                                        send_notification_to_related_users(order_id, order_data.copy(), 
                                                                           "Related order submitted", 
                                                                           notification_type="submitted")
                                        if needs_sgf:
                                            send_sgf_notification()
                                        elif skip_level1:
                                            send_approval_notification_to_admin(order_id, order_data.copy(), admin_level=2)
                                            send_approval_notification(admin_level=2)
                                        else:
                                            send_approval_notification_to_admin(order_id, order_data.copy(), admin_level=1)
                                            send_approval_notification(admin_level=1)
                                    except Exception as e:
                                        print(f"Background notification error: {e}")
                                threading.Thread(target=_send_dialog_notifications, daemon=True).start()
                                
                                st.session_state.show_submit_order_dialog = False
                                st.session_state.cart = []
                                st.session_state.order_uploaded_files_dialog = []
                                st.session_state.last_submitted_order_id = order_id
                                st.session_state.order_submission_success = True
                                if needs_sgf:
                                    status_message = "Pending for SGF approval"
                                elif skip_level1:
                                    status_message = "Pending for Approval 2 (skips Level 1)"
                                else:
                                    status_message = "Pending for Approval 1"
                                if attachment_paths:
                                    st.success(f"Order {order_id} submitted successfully with {len(attachment_paths)} attachment(s)! Status: {status_message}")
                                else:
                                    st.success(f"Order {order_id} submitted successfully! Status: {status_message}")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("Error saving order. Please try again.")

# Order Details Dialog Function
@st.dialog(title="📋 Order Details", width="large", dismissible=True)
def order_details_dialog(order_id, orders_df):
    """Dialog function for displaying complete order details"""
    order = orders_df[orders_df['OrderID'] == order_id]
    
    if order.empty:
        st.error(f"Order {order_id} not found.")
        return
    
    order_row = order.iloc[0]
    
    st.header(f"Order {order_id}")
    
    # Basic Order Information
    st.subheader("Order Information")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Order ID:** {order_row.get('OrderID', 'N/A')}")
        st.markdown(f"**Order Date:** {order_row.get('OrderDate', 'N/A')}")
        # Format status display - show Level 2 for TRADE accounts
        display_status = format_order_status_display(order_row)
        st.markdown(f"**Status:** {display_status}")
    with col2:
        st.markdown(f"**Created By:** {order_row.get('CreatedBy', 'N/A')}")
        reviewed_by = order_row.get('ReviewedBy', '')
        if reviewed_by:
            st.markdown(f"**Reviewed By:** {reviewed_by}")
            st.markdown(f"**Reviewed Date:** {order_row.get('ReviewedDate', 'N/A')}")
        else:
            st.markdown("**Reviewed By:** Not reviewed")
        
        # Show approval status
        approved_by_sgf = order_row.get('ApprovedBySGF', '')
        approved_date_sgf = order_row.get('ApprovedDateSGF', '')
        approved_by_l1 = order_row.get('ApprovedByLevel1', '')
        approved_date_l1 = order_row.get('ApprovedDateLevel1', '')
        approved_by_l2 = order_row.get('ApprovedByLevel2', '')
        approved_date_l2 = order_row.get('ApprovedDateLevel2', '')
        
        if approved_by_sgf:
            st.success(f"✅ Approved by SGF Manager: {approved_by_sgf}")
            st.caption(f"Date: {approved_date_sgf}")
        if approved_by_l1:
            st.success(f"✅ Approved by Level 1: {approved_by_l1}")
            st.caption(f"Date: {approved_date_l1}")
        if approved_by_l2:
            st.success(f"✅ Approved by Level 2: {approved_by_l2}")
            st.caption(f"Date: {approved_date_l2}")
        elif approved_by_l1 and not approved_by_l2:
            st.warning("⏳ Waiting for Level 2 approval")
        elif order_row.get('Status') == 'Pending for SGF' and not approved_by_sgf:
            st.warning("⏳ Waiting for SGF Manager approval")
    with col3:
        st.markdown(f"**Subtotal:** {float(order_row.get('Subtotal', 0)):.2f}")
        discount_percent = float(order_row.get('DiscountPercent', 0))
        if discount_percent > 0:
            st.markdown(f"**Discount ({discount_percent}%):** -{float(order_row.get('DiscountAmount', 0)):.2f}")
        st.markdown(f"**Total Amount:** **{float(order_row.get('TotalAmount', 0)):.2f}**")
    
    st.markdown("---")
    
    # Client Information
    st.subheader("Client Information")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Account / Customer Name:** {order_row.get('ClientName', 'N/A')}")
        st.markdown(f"**Mobile:** {order_row.get('ClientMobile', 'N/A')}")
    with col2:
        st.markdown(f"**Client Category:** {order_row.get('ClientDescription', 'N/A')}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Billing Address:**")
        st.info(order_row.get('BillingAddress', 'N/A'))
    with col2:
        st.markdown("**Shipping Address:**")
        st.info(order_row.get('ShippingAddress', 'N/A'))
    
    st.markdown("---")
    st.subheader("Contact Persons")
    col1, col2 = st.columns(2)
    with col1:
        contact_person_1 = order_row.get('ContactPerson1', '')
        contact_person_1_mobile = order_row.get('ContactPerson1Mobile', '')
        if contact_person_1 or contact_person_1_mobile:
            st.markdown(f"**Contact Person 1:** {contact_person_1 if contact_person_1 else 'N/A'}")
            st.markdown(f"**Mobile:** {contact_person_1_mobile if contact_person_1_mobile else 'N/A'}")
    with col2:
        contact_person_2 = order_row.get('ContactPerson2', '')
        contact_person_2_mobile = order_row.get('ContactPerson2Mobile', '')
        if contact_person_2 or contact_person_2_mobile:
            st.markdown(f"**Contact Person 2:** {contact_person_2 if contact_person_2 else 'N/A'}")
            st.markdown(f"**Mobile:** {contact_person_2_mobile if contact_person_2_mobile else 'N/A'}")
    
    st.markdown("---")
    
    # Order Terms
    st.subheader("Order Terms")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Payment Terms:** {order_row.get('PaymentTerms', 'N/A')}")
    with col2:
        st.markdown(f"**Delivery Instructions:** {order_row.get('DeliveryTerms', 'N/A')}")
    with col3:
        st.markdown(f"**Delivery Date:** {order_row.get('DeliveryDate', 'N/A')}")
    
    st.markdown("---")
    
    # Representative Information
    st.subheader("Representative Information")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Code:** {order_row.get('RepCode', 'N/A')}")
        st.markdown(f"**Name:** {order_row.get('RepName', 'N/A')}")
        st.markdown(f"**Company:** {order_row.get('RepCompany', 'N/A')}")
    with col2:
        st.markdown(f"**Dept/DSM District:** {order_row.get('RepDept', 'N/A')}")
        st.markdown(f"**Area/PMR:** {order_row.get('RepArea', 'N/A')}")
    
    st.markdown("---")
    
    # Cart Items with Images
    cart_items_str = order_row.get('CartItems', '[]')
    disapproved_items_str = order_row.get('DisapprovedItems', '[]')
    try:
        # Try to parse the cart items string
        cart_items = safe_parse_cart_items(cart_items_str)
        
        # Parse disapproved items
        try:
            disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
        except (ValueError, SyntaxError):
            disapproved_items = []
        
        if cart_items and len(cart_items) > 0:
            # Get disapproved indices
            disapproved_indices = [dis_item.get('item_index', -1) for dis_item in disapproved_items if 'item_index' in dis_item]
            remaining_items = [item for idx, item in enumerate(cart_items) if idx not in disapproved_indices]
            
            if remaining_items:
                display_cart_items_with_images(remaining_items)
            
            # Show disapproved items if any
            if disapproved_items and len(disapproved_items) > 0:
                st.markdown("---")
                st.markdown("### ❌ Removed/Disapproved Items")
                for dis_item in disapproved_items:
                    with st.container(border=True):
                        st.error(f"**{dis_item.get('product_name', 'N/A')}** (Code: {dis_item.get('product_code', 'N/A')})")
                        st.caption(f"**Reason:** {dis_item.get('disapproval_reason', 'N/A')}")
                        st.caption(f"Removed by: {dis_item.get('disapproved_by', 'N/A')} on {dis_item.get('disapproved_date', 'N/A')}")
        else:
            st.info("No items found in this order.")
    except (ValueError, SyntaxError):
        st.warning(f"Could not parse cart items: {cart_items_str}")
        st.info("Cart items data may be in an unexpected format.")
    
    st.markdown("---")
    
    # Additional Information
    st.subheader("Additional Information")
    notes = order_row.get('Notes', '')
    remarks = order_row.get('Remarks', '')
    
    if notes:
        st.markdown("**Notes / Special Instructions:**")
        st.info(notes)
    
    if remarks:
        st.markdown("**Remarks:**")
        st.info(remarks)
    
    if not notes and not remarks:
        st.info("No additional information available.")
    
    st.markdown("---")
    
    # Display Attachments
    attachments_str = order_row.get('Attachments', '')
    if attachments_str:
        display_order_attachments(attachments_str)
        st.markdown("---")
    
    # Close button
    if st.button("Close", type="primary", use_container_width=True):
        st.session_state.show_order_details_dialog = False
        st.session_state.selected_order_id = None
        st.session_state.dialog_button_clicked = False
        st.rerun()

# Disapprove Item Dialog Function
@st.dialog(title="❌ Remove/Disapprove Item", width="medium", dismissible=True)
def disapprove_item_dialog(order_id, item_index, item_name, orders_df):
    """Dialog function for disapproving individual items with required reason"""
    st.header("Remove/Disapprove Item")
    st.warning(f"⚠️ Please provide a reason for removing/disapproving this item: **{item_name}**")
    
    order = orders_df[orders_df['OrderID'] == order_id]
    if not order.empty:
        order_row = order.iloc[0]
        st.markdown(f"**Order ID:** {order_id}")
        st.markdown(f"**Client:** {order_row.get('ClientName', 'N/A')}")
        st.markdown("---")
    
    with st.form("disapprove_item_form"):
        disapproval_reason = st.text_area(
            "Reason for Item Removal/Disapproval *",
            key="item_disapproval_reason",
            placeholder="Please provide a detailed reason for removing/disapproving this item...",
            help="This reason will be visible to the sales representative and client."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit_disapprove = st.form_submit_button("❌ Remove\n/ Disapprove Item", type="primary", use_container_width=True)
        with col2:
            cancel_disapprove = st.form_submit_button("Cancel", use_container_width=True)
        
        if cancel_disapprove:
            st.session_state.show_disapprove_item_dialog = False
            st.session_state.disapprove_item_order_id = None
            st.session_state.disapprove_item_index = None
            st.rerun()
        
        if submit_disapprove:
            # Validation - reason is required
            if not disapproval_reason or not disapproval_reason.strip():
                st.error("⚠️ Please provide a reason for item removal/disapproval. This field is required.")
            else:
                # Get current cart items and disapproved items
                orders_df = load_orders()
                order_idx = orders_df[orders_df['OrderID'] == order_id].index
                if len(order_idx) > 0:
                    # Parse cart items
                    cart_items_str = orders_df.at[order_idx[0], 'CartItems']
                    cart_items = safe_parse_cart_items(cart_items_str)
                    
                    # Get disapproved items
                    disapproved_items_str = orders_df.at[order_idx[0], 'DisapprovedItems'] if 'DisapprovedItems' in orders_df.columns else '[]'
                    try:
                        disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
                    except (ValueError, SyntaxError):
                        disapproved_items = []
                    
                    # Get the item to disapprove
                    if item_index < len(cart_items):
                        item_to_disapprove = cart_items[item_index].copy()
                        item_to_disapprove['disapproval_reason'] = disapproval_reason.strip()
                        item_to_disapprove['disapproved_by'] = st.session_state.username
                        item_to_disapprove['disapproved_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        item_to_disapprove['item_index'] = item_index
                        
                        # Add to disapproved items
                        disapproved_items.append(item_to_disapprove)
                        
                        # Update order
                        orders_df.at[order_idx[0], 'DisapprovedItems'] = str(disapproved_items)
                        
                        if save_orders(orders_df):
                            st.session_state.show_disapprove_item_dialog = False
                            st.session_state.disapprove_item_order_id = None
                            st.session_state.disapprove_item_index = None
                            st.success(f"Item '{item_name}' has been removed/disapproved.")
                            st.rerun()
                        else:
                            st.error("Error saving item disapproval. Please try again.")
                    else:
                        st.error("Invalid item index.")
                else:
                    st.error("Order not found.")

# Disapprove Order Dialog Function
@st.dialog(title="❌ Disapprove Order", width="medium", dismissible=True)
def disapprove_order_dialog(order_id, orders_df):
    """Dialog function for disapproving orders with required reason"""
    st.header(f"Disapprove Order {order_id}")
    st.warning("⚠️ Please provide a reason for disapproving this order. This reason will be visible in the order status.")
    
    order = orders_df[orders_df['OrderID'] == order_id]
    if not order.empty:
        order_row = order.iloc[0]
        st.markdown(f"**Client:** {order_row.get('ClientName', 'N/A')}")
        st.markdown(f"**Order Date:** {order_row.get('OrderDate', 'N/A')}")
        st.markdown(f"**Total Amount:** {float(order_row.get('TotalAmount', 0)):.2f}")
        st.markdown("---")
    
    with st.form("disapprove_form"):
        disapproval_reason = st.text_area(
            "Reason for Disapproval *",
            key="disapproval_reason",
            placeholder="Please provide a detailed reason for disapproving this order...",
            help="This reason will be added to the order status and will be visible to the sales representative."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit_disapprove = st.form_submit_button("❌ Disapprove Order", type="primary", use_container_width=True)
        with col2:
            cancel_disapprove = st.form_submit_button("Cancel", use_container_width=True)
        
        if cancel_disapprove:
            st.session_state.show_disapprove_dialog = False
            st.session_state.disapprove_order_id = None
            st.rerun()
        
        if submit_disapprove:
            # Validation - reason is required
            if not disapproval_reason or not disapproval_reason.strip():
                st.error("⚠️ Please provide a reason for disapproval. This field is required.")
            else:
                # Update order status with reason
                order_idx = orders_df[orders_df['OrderID'] == order_id].index
                if len(order_idx) > 0:
                    # Format status as "Disapproved (reason: ...)"
                    status_with_reason = f"Disapproved (reason: {disapproval_reason.strip()})"
                    orders_df.at[order_idx[0], 'Status'] = status_with_reason
                    orders_df.at[order_idx[0], 'ReviewedBy'] = st.session_state.username
                    orders_df.at[order_idx[0], 'ReviewedDate'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if save_orders(orders_df):
                        # Send notification to Sales Rep/TSR about disapproval
                        try:
                            order_row = orders_df.iloc[order_idx[0]]
                            order_dict = order_row.to_dict()
                            disapproval_msg = f"Order disapproved: {disapproval_reason.strip()}"
                            send_order_notification_to_rep(order_id, order_dict, 
                                                          disapproval_msg, 
                                                          notification_type="disapproved")
                            
                            # Notify related users about disapproval
                            send_notification_to_related_users(order_id, order_dict, 
                                                             disapproval_msg, 
                                                             notification_type="disapproved")
                        except Exception as e:
                            print(f"Error sending notification email: {e}")
                        
                        st.session_state.show_disapprove_dialog = False
                        st.session_state.disapprove_order_id = None
                        st.success(f"Order {order_id} has been disapproved with reason.")
                        st.rerun()
                    else:
                        st.error("Error saving disapproval. Please try again.")

# Cancel Order Dialog (Super Admin only - Manually Forced Cancel)
@st.dialog(title="🚫 Cancel Order (Manually Forced Cancel)", width="medium", dismissible=True)
def cancel_order_dialog(order_id, orders_df):
    """Dialog for Super Admin to cancel order with status Manually Forced Cancel"""
    st.header(f"Cancel Order {order_id}")
    st.warning("⚠️ This will set the order status to **Manually Forced Cancel**. This action is irreversible. Only Super Admin can perform this.")
    
    order = orders_df[orders_df['OrderID'] == order_id]
    if not order.empty:
        order_row = order.iloc[0]
        st.markdown(f"**Client:** {order_row.get('ClientName', 'N/A')}")
        st.markdown(f"**Order Date:** {order_row.get('OrderDate', 'N/A')}")
        st.markdown(f"**Total Amount:** {float(order_row.get('TotalAmount', 0)):.2f}")
        st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚫 Confirm Cancel", key="confirm_cancel_order", type="primary", use_container_width=True):
            order_idx = orders_df[orders_df['OrderID'] == order_id].index
            if len(order_idx) > 0:
                orders_df.at[order_idx[0], 'Status'] = 'Manually Forced Cancel'
                orders_df.at[order_idx[0], 'ReviewedBy'] = st.session_state.username
                orders_df.at[order_idx[0], 'ReviewedDate'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if save_orders(orders_df):
                    st.session_state.show_cancel_order_dialog = False
                    st.session_state.cancel_order_id = None
                    st.success(f"Order {order_id} has been cancelled (Manually Forced Cancel).")
                    st.rerun()
                else:
                    st.error("Error saving. Please try again.")
    with col2:
        if st.button("Cancel", key="cancel_cancel_order", use_container_width=True):
            st.session_state.show_cancel_order_dialog = False
            st.session_state.cancel_order_id = None
            st.rerun()

# Add Account Dialog Function
@st.dialog(title="➕ Add New Account", width="medium", dismissible=True)
def add_account_dialog():
    """Dialog function for adding new accounts"""
    st.header("Add New Account")
    
    with st.form("add_account_form"):
        customer_code = st.text_input("Customer Code *", key="new_customer_code", autocomplete="off")
        customer_name = st.text_input("Customer Name *", key="new_customer_name", autocomplete="off")
        credit_term = st.text_input("Credit Term *", key="new_credit_term", placeholder="e.g., COD, 30D, 60D", autocomplete="off")
        area = st.text_input("Area", key="new_area", placeholder="e.g., Central, North, South", autocomplete="off")
        account_type_add = st.selectbox(
            "Account Type *",
            options=["Dispensing", "TRADE", "Distribution", "Contract"],
            index=0,
            key="new_account_type",
            help="Select account type"
        )
        active = st.checkbox("Active", value=True, key="new_active")
        
        col1, col2 = st.columns(2)
        with col1:
            submit_add = st.form_submit_button("➕ Add Account", type="primary", use_container_width=True)
        with col2:
            cancel_add = st.form_submit_button("Cancel", use_container_width=True)
        
        if cancel_add:
            st.session_state.show_add_account_dialog = False
            st.rerun()
        
        if submit_add:
            # Validation
            if not customer_code or not customer_code.strip():
                st.error("Customer Code is required.")
            elif not customer_name or not customer_name.strip():
                st.error("Customer Name is required.")
            elif not credit_term or not credit_term.strip():
                st.error("Credit Term is required.")
            else:
                # Load existing accounts
                accounts_df = load_accounts()
                
                # Check if customer code already exists
                if not accounts_df.empty and 'Customer code' in accounts_df.columns:
                    if customer_code.strip() in accounts_df['Customer code'].astype(str).values:
                        st.error(f"Customer Code '{customer_code.strip()}' already exists. Please use a different code.")
                    else:
                        # Create new account record
                        # Special rule: If Credit Term is 'COD', set SGF=True and SGF_count=1
                        # Otherwise, default SGF=False and SGF_count=99
                        if credit_term.strip().upper() == 'COD':
                            sgf_value = 'TRUE'
                            sgf_count_value = 1
                        else:
                            sgf_value = 'FALSE'
                            sgf_count_value = 99
                        
                        new_account = {
                            'Customer code': customer_code.strip(),
                            'Customer name': customer_name.strip(),
                            'Credit term': credit_term.strip(),
                            'Area': area.strip() if area else '',
                            'Active': 'TRUE' if active else 'FALSE',
                            'SGF': sgf_value,
                            'SGF_count': sgf_count_value,
                            'Account_Type': account_type_add
                        }
                        
                        # Add to DataFrame
                        new_account_df = pd.DataFrame([new_account])
                        if accounts_df.empty:
                            accounts_df = new_account_df
                        else:
                            accounts_df = pd.concat([accounts_df, new_account_df], ignore_index=True)
                        
                        if save_accounts(accounts_df):
                            st.success(f"Account '{customer_name.strip()}' added successfully!")
                            st.session_state.show_add_account_dialog = False
                            st.rerun()
                        else:
                            st.error("Error saving account. Please try again.")
                else:
                    # If accounts_df is empty or missing Customer code column, create new structure
                    # Special rule: If Credit Term is 'COD', set SGF=True and SGF_count=1
                    # Otherwise, default SGF=False and SGF_count=99
                    if credit_term.strip().upper() == 'COD':
                        sgf_value = 'TRUE'
                        sgf_count_value = 1
                    else:
                        sgf_value = 'FALSE'
                        sgf_count_value = 99
                    
                    new_account = {
                        'Customer code': customer_code.strip(),
                        'Customer name': customer_name.strip(),
                        'Credit term': credit_term.strip(),
                        'Area': area.strip() if area else '',
                        'Active': 'TRUE' if active else 'FALSE',
                        'SGF': sgf_value,
                        'SGF_count': sgf_count_value,
                        'Account_Type': account_type_add
                    }
                    
                    new_account_df = pd.DataFrame([new_account])
                    if save_accounts(new_account_df):
                        st.success(f"Account '{customer_name.strip()}' added successfully!")
                        st.session_state.show_add_account_dialog = False
                        st.rerun()
                    else:
                        st.error("Error saving account. Please try again.")

# Manage Users Dialog Function
@st.dialog(title="👥 Manage Users", width="large", dismissible=True)
def manage_users_dialog():
    # Reset other dialog states to prevent conflicts
    st.session_state.show_manage_products_dialog = False
    
    st.header("Manage Users")
    
    # Get current user context
    current_username = st.session_state.get('username')
    current_role = st.session_state.get('user_role')
    current_admin_level = st.session_state.get('admin_level')
    
    # Determine access level
    # Administrator or Admin role has full access
    is_super_admin = (current_username == 'administrator') or (current_role == 'Admin') or (current_role == 'Admin Level 0')
    # Level 1 can only manage non-Finance
    is_level1 = (current_admin_level == 1)
    
    # Add User Form
    with st.expander("➕ Add / Edit User", expanded=st.session_state.user_to_edit is not None):
        with st.form("user_form"):
            # If editing, pre-fill values
            edit_data = st.session_state.user_to_edit or {}
            is_edit = st.session_state.user_to_edit is not None
            
            username = st.text_input("Username *", value=edit_data.get('Username', ''), disabled=is_edit, autocomplete="username")
            password = st.text_input("Password *", value=edit_data.get('Password', ''), type="password", autocomplete="new-password")
            email = st.text_input("Email Address *", value=edit_data.get('Email', ''),
                                  help="Email address for order notifications (required)", autocomplete="email")
            
            role_options = ["Sales Rep", "TSR", "Admin Level 0", "Admin Level 1 Ethical", "Admin Level 2", "Ethical Staff Level 1", "Finance Staff Level 2", "SGF Manager"]
            current_role_val = normalize_role(edit_data.get('Role', 'Sales Rep'))
            role_index = role_options.index(current_role_val) if current_role_val in role_options else 0
            role = st.selectbox("Role *", role_options, index=role_index,
                                help="Sales Rep = standard sales UI. TSR = different UI (Booking Request, TRADE flow, Related Orders by TSR tag). Admin Level 0 = Super Admin; Admin Level 1 Ethical/Admin Level 2 = approvers; Ethical Staff Level 1/Finance Staff Level 2 = view-only.")
            
            admin_roles = ('Admin', 'Admin Level 0', 'Admin Level 1 Ethical', 'Admin Level 2', 'Ethical Staff Level 1', 'Finance Staff Level 2', 'Admin / Finance Staff', 'Finance Staff', 'SGF Manager')
            current_account_type = edit_data.get('AccountType') or edit_data.get('account_type', '')
            if not current_account_type or not str(current_account_type).strip():
                if current_role_val == 'TSR':
                    current_account_type = 'TRADE'
                else:
                    current_account_type = 'admin' if current_role_val in admin_roles else 'Dispensing'
            account_type_options = ["Dispensing", "TRADE", "Distribution", "Contract", "admin"]
            account_type_index = account_type_options.index(current_account_type) if current_account_type in account_type_options else 0
            account_type = st.selectbox("Account Type *", account_type_options, index=account_type_index,
                                        help="Dispensing, TRADE, Distribution, or Contract for reps; admin for Finance/Admin/SGF")
            
            col1, col2 = st.columns(2)
            with col1:
                rep_code = st.text_input("Code", value=edit_data.get('RepCode', ''), autocomplete="off")
                rep_name = st.text_input("Name", value=edit_data.get('RepName', ''), autocomplete="off")
                rep_company = st.text_input("Company", value=edit_data.get('RepCompany', ''), autocomplete="off")
            with col2:
                rep_dept = st.text_input("Dept", value=edit_data.get('RepDept', ''), autocomplete="off")
                rep_area = st.text_input("Area", value=edit_data.get('RepArea', ''), autocomplete="off")
                registration_date = edit_data.get('RegistrationDate', datetime.now().strftime('%Y-%m-%d'))
            
            submitted = st.form_submit_button("Save User", type="primary", use_container_width=True)
            
            if submitted:
                # Validate required fields
                if not username or not password or not role:
                    st.error("Username, Password, and Role are required.")
                elif not email or not email.strip():
                    # Validate email - REQUIRED FIELD
                    st.error("Email Address is required. Please enter a valid email address.")
                else:
                    # Validate email format
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    if not re.match(email_pattern, email.strip()):
                        st.error("Please enter a valid email address")
                    elif is_level1 and rep_dept == 'Finance':
                        st.error("Access Denied: Level 1 Admin cannot create or edit Finance users.")
                    else:
                        # All validations passed - proceed with user creation/update
                        try:
                            user = User(
                                username=username,
                                password=password,
                                role=role,
                                rep_code=rep_code or '',
                                rep_name=rep_name or '',
                                rep_company=rep_company or '',
                                rep_dept=rep_dept or '',
                                rep_area=rep_area or '',
                                registration_date=registration_date,
                                account_type=account_type or 'Dispensing',
                                email=email.strip()
                            )
                            if db.upsert_user(user):
                                st.success(f"User {username} saved successfully!")
                                st.session_state.user_to_edit = None
                                st.rerun()
                            else:
                                st.error("Error saving user.")
                        except Exception as e:
                            st.error(f"Error saving user: {e}")
                        
        if is_edit:
            if st.button("Cancel Edit", use_container_width=True):
                st.session_state.user_to_edit = None
                st.rerun()

    # Bulk Upload Section
    with st.expander("📤 Bulk Upload Users", expanded=False):
        st.caption("Download the template, fill in user data, then upload the CSV. Existing rows are overwritten when Username or RepCode matches.")
        col_dl, col_up = st.columns(2)
        with col_dl:
            # Template columns (must match User model)
            template_columns = ['Username', 'Password', 'Role', 'RepCode', 'RepName', 'RepCompany', 'RepDept', 'RepArea', 'RegistrationDate', 'AccountType', 'Email']
            template_df = pd.DataFrame(columns=template_columns)
            template_df.loc[0] = [
                'sample_user', 'password123', 'Sales Rep', 'SR001', 'Sample Name', 'Company', 'Sales', 'North',
                datetime.now().strftime('%Y-%m-%d'), 'Dispensing', 'sample@example.com'
            ]
            template_csv = template_df.to_csv(index=False)
            st.download_button(
                "📥 Download Template",
                data=template_csv,
                file_name="users_template.csv",
                mime="text/csv",
                use_container_width=True,
                help="Download CSV template with all user fields. Fill in rows and upload below."
            )
        with col_up:
            uploaded_file = st.file_uploader("Upload CSV", type=['csv'], key="bulk_upload_users_csv", help="Upload filled template to bulk add/update users")
            # Skip re-processing after successful upload (prevents rerun loop - file stays in uploader)
            if st.session_state.get('bulk_upload_just_done'):
                st.session_state.bulk_upload_just_done = False
                uploaded_file = None  # Skip processing on this run
            process_btn = st.button("Process Upload", type="primary", key="bulk_upload_process_btn", use_container_width=True,
                                    help="Click to process the uploaded CSV file")
            if uploaded_file and process_btn:
                with st.spinner("Processing CSV..."):
                    try:
                        # Try UTF-8 first; fall back to cp1252 (Excel/Windows) or latin-1
                        try:
                            df = pd.read_csv(uploaded_file, encoding='utf-8')
                        except UnicodeDecodeError:
                            uploaded_file.seek(0)
                            try:
                                df = pd.read_csv(uploaded_file, encoding='cp1252')
                            except UnicodeDecodeError:
                                uploaded_file.seek(0)
                                df = pd.read_csv(uploaded_file, encoding='latin-1')
                        # Normalize column names (handle case/spaces)
                        df.columns = df.columns.str.strip()
                        required_cols = ['Username', 'Password', 'Role', 'Email']
                        missing = [c for c in required_cols if c not in df.columns]
                        if missing:
                            st.error(f"Template missing required columns: {missing}. Please use the downloaded template.")
                        else:
                            success_count = 0
                            error_rows = []
                            for idx, row in df.iterrows():
                                username = str(row.get('Username', '')).strip()
                                if not username:
                                    continue
                                password = str(row.get('Password', '')).strip()
                                role = normalize_role(str(row.get('Role', 'Sales Rep')).strip() or 'Sales Rep')
                                email = str(row.get('Email', '')).strip()
                                if not password or not role:
                                    error_rows.append((idx + 2, username, "Password and Role required"))
                                    continue
                                if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                                    error_rows.append((idx + 2, username, "Valid email required"))
                                    continue
                                if is_level1 and str(row.get('RepDept', '')).strip() == 'Finance':
                                    error_rows.append((idx + 2, username, "Level 1 cannot add Finance users"))
                                    continue
                                rep_code = str(row.get('RepCode', '')) if pd.notna(row.get('RepCode')) else ''
                                rep_name = str(row.get('RepName', '')) if pd.notna(row.get('RepName')) else ''
                                rep_company = str(row.get('RepCompany', '')) if pd.notna(row.get('RepCompany')) else ''
                                rep_dept = str(row.get('RepDept', '')) if pd.notna(row.get('RepDept')) else ''
                                rep_area = str(row.get('RepArea', '')) if pd.notna(row.get('RepArea')) else ''
                                reg_date = str(row.get('RegistrationDate', datetime.now().strftime('%Y-%m-%d'))) if pd.notna(row.get('RegistrationDate')) else datetime.now().strftime('%Y-%m-%d')
                                account_type = str(row.get('AccountType', 'Dispensing')).strip() or 'Dispensing'
                                try:
                                    user = User(username=username, password=password, role=role, rep_code=rep_code, rep_name=rep_name,
                                                rep_company=rep_company, rep_dept=rep_dept, rep_area=rep_area,
                                                registration_date=reg_date, account_type=account_type, email=email)
                                    upsert_fn = getattr(db, 'upsert_user_bulk_overwrite', db.upsert_user)
                                    if upsert_fn(user):
                                        success_count += 1
                                    else:
                                        error_rows.append((idx + 2, username, "Save failed"))
                                except Exception as e:
                                    error_rows.append((idx + 2, username, str(e)))
                            if success_count > 0:
                                st.success(f"Bulk upload: {success_count} user(s) saved.")
                            if error_rows:
                                st.warning(f"{len(error_rows)} row(s) skipped:")
                                for row_num, uname, err in error_rows[:10]:
                                    st.caption(f"Row {row_num} ({uname}): {err}")
                                if len(error_rows) > 10:
                                    st.caption(f"... and {len(error_rows) - 10} more")
                            if success_count > 0:
                                st.session_state.bulk_upload_just_done = True
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error reading CSV: {e}")
            elif uploaded_file and not process_btn:
                st.info("File selected. Click **Process Upload** to import users.")

    # List Users - All User Accounts Table
    users_df = db.get_all_users_df()
    if not users_df.empty:
        # Filter users based on access level
        if not is_super_admin:
            if is_level1:
                # Filter out Finance users
                users_df = users_df[users_df['RepDept'] != 'Finance']
            # Add other conditions if necessary for other roles

        # Sort table by Role, then RepDept
        sort_cols = [c for c in ['Role', 'RepDept'] if c in users_df.columns]
        if sort_cols:
            users_df = users_df.sort_values(by=sort_cols).reset_index(drop=True)

        col_title, col_download = st.columns([3, 1])
        with col_title:
            st.subheader("All User Accounts")
        with col_download:
            # Download full list including Password (for admin backup/restore)
            export_df = users_df.copy()
            csv_bytes = export_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 Download All (incl. Password)",
                data=csv_bytes,
                file_name=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="manage_users_download"
            )

        # Display table: hide password for security in main view; normalize Role for fallback (old names -> new)
        display_cols = [c for c in users_df.columns if c != 'Password']
        table_df = users_df[display_cols].copy()
        if 'Role' in table_df.columns:
            table_df['Role'] = table_df['Role'].apply(lambda r: normalize_role(r) if pd.notna(r) and str(r).strip() else r)
        st.dataframe(table_df, use_container_width=True, hide_index=True)
        
        # Actions
        st.subheader("Actions")
        col1, col2 = st.columns(2)
        with col1:
            user_to_action = st.selectbox("Select User", users_df['Username'].tolist(), key="user_action_select")
        
        with col2:
            col_edit, col_del = st.columns(2)
            with col_edit:
                # Disable Edit for non-super admins (Level 1 & 2)
                if st.button("✏️ Edit", use_container_width=True, disabled=not is_super_admin):
                    # Get user data
                    user_data = users_df[users_df['Username'] == user_to_action].iloc[0].to_dict()
                    st.session_state.user_to_edit = user_data
                    st.rerun()
            with col_del:
                # Disable Delete for non-super admins as well
                if st.button("🗑️ Delete", type="primary", use_container_width=True, disabled=not is_super_admin):
                    if db.delete_user(user_to_action):
                        st.success(f"User {user_to_action} deleted!")
                        st.rerun()
                    else:
                        st.error("Error deleting user.")

# Manage Products Dialog Function
@st.dialog(title="📦 Manage Products", width="large", dismissible=True)
def manage_products_dialog():
    # Reset other dialog states to prevent conflicts
    st.session_state.show_manage_users_dialog = False
    
    st.header("Manage Products")
    
    # Add/Edit Product Form
    with st.expander("➕ Add / Edit Product", expanded=st.session_state.product_to_edit is not None):
        with st.form("product_form"):
            edit_data = st.session_state.product_to_edit or {}
            is_edit = st.session_state.product_to_edit is not None
            
            col1, col2 = st.columns(2)
            with col1:
                product_code = st.text_input("Product Code *", value=edit_data.get('ProductCode', ''), disabled=is_edit, autocomplete="off")
                product_name = st.text_input("Product Name *", value=edit_data.get('ProductName', ''), autocomplete="off")
                unit_price = st.number_input("Unit Price *", value=float(edit_data.get('UnitPrice', 0.0)), min_value=0.0)
            with col2:
                category = st.text_input("Category", value=edit_data.get('Category', ''), autocomplete="off")
                manufacturer = st.text_input("Manufacturer", value=edit_data.get('Manufacturer', ''), autocomplete="off")
                stock_quantity = st.number_input("Stock Quantity", value=int(edit_data.get('StockQuantity', 0)), min_value=0)
            
            description = st.text_area("Description", value=edit_data.get('Description', ''))
            
            submitted = st.form_submit_button("Save Product", type="primary", use_container_width=True)
            
            if submitted:
                if not product_code or not product_name:
                    st.error("Product Code and Name are required.")
                else:
                    try:
                        product = Product(
                            product_code=product_code,
                            product_name=product_name,
                            description=description,
                            unit_price=unit_price,
                            stock_quantity=stock_quantity,
                            category=category,
                            manufacturer=manufacturer
                        )
                        if db.upsert_product(product):
                            st.success(f"Product {product_code} saved successfully!")
                            st.session_state.product_to_edit = None
                            st.rerun()
                        else:
                            st.error("Error saving product.")
                    except Exception as e:
                        st.error(f"Validation Error: {e}")
        
        if is_edit:
            if st.button("Cancel Edit", key="cancel_prod_edit", use_container_width=True):
                st.session_state.product_to_edit = None
                st.rerun()

    # List Products
    products_df = db.get_all_products()
    if not products_df.empty:
        # Search
        search_term = st.text_input("🔍 Search Products", placeholder="Search by name or code...", autocomplete="off")
        if search_term:
            products_df = products_df[
                products_df['ProductName'].str.contains(search_term, case=False, na=False) | 
                products_df['ProductCode'].str.contains(search_term, case=False, na=False)
            ]
        
        st.dataframe(products_df, use_container_width=True, hide_index=True)
        
        # Actions
        st.subheader("Actions")
        col1, col2 = st.columns(2)
        with col1:
            # Limit selection to filtered products
            prod_options = products_df['ProductCode'].tolist()
            prod_to_action = st.selectbox("Select Product", prod_options, key="prod_action_select")
        
        with col2:
            col_edit, col_del = st.columns(2)
            with col_edit:
                if st.button("✏️ Edit Product", use_container_width=True):
                    if prod_to_action:
                        prod_data = products_df[products_df['ProductCode'] == prod_to_action].iloc[0].to_dict()
                        st.session_state.product_to_edit = prod_data
                        st.rerun()
            with col_del:
                if st.button("🗑️ Delete Product", type="primary", use_container_width=True):
                    if prod_to_action and db.delete_product(prod_to_action):
                        st.success(f"Product {prod_to_action} deleted!")
                        st.rerun()
                    else:
                        st.error("Error deleting product.")

# Notification Scheduler status and control (Super Admin only)
_script_dir = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT_FILE = os.path.join(_script_dir, 'notification_scheduler_heartbeat.txt')
SCHEDULER_SCRIPT = os.path.join(_script_dir, 'notification_scheduler.py')

def get_scheduler_status():
    """Return (status_text, minutes_ago, is_likely_running). is_likely_running if last run < 90 min."""
    try:
        if not os.path.exists(HEARTBEAT_FILE):
            return "Never run", None, False
        with open(HEARTBEAT_FILE, 'r', encoding='utf-8') as f:
            ts_str = f.read().strip()
        if not ts_str:
            return "Never run", None, False
        from datetime import datetime
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f'):
            try:
                last_run = datetime.strptime(ts_str[:19], fmt)
                break
            except ValueError:
                continue
        else:
            return "Unknown format", None, False
        delta = datetime.now() - last_run
        minutes_ago = int(delta.total_seconds() / 60)
        if minutes_ago < 2:
            status = "Just ran"
        elif minutes_ago < 60:
            status = f"Last run {minutes_ago} min ago"
        elif minutes_ago < 1440:
            status = f"Last run {minutes_ago // 60} hours ago"
        else:
            status = f"Last run {minutes_ago // 1440} days ago"
        is_likely_running = minutes_ago < 90  # If run within 90 min, assume background scheduler is active
        return status, minutes_ago, is_likely_running
    except Exception as e:
        return f"Error: {e}", None, False

def run_scheduler_manual():
    """Run notification scheduler as subprocess (Windows/Ubuntu compatible)."""
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, SCHEDULER_SCRIPT],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=120
        )
        return result.returncode == 0, result.stdout or '', result.stderr or ''
    except subprocess.TimeoutExpired:
        return False, '', 'Scheduler timed out after 120 seconds'
    except Exception as e:
        return False, '', str(e)

# Notification Management Dialog (Super Admin only)
@st.dialog(title="🔔 Notification Management", width="large", dismissible=True)
def notification_management_dialog():
    """View notification send log and users without email - Super Admin only"""
    st.header("Notification Management")
    st.caption("Send log and users without email configuration. Failed to Send = recipient has no email or email is null.")
    
    # On/Off toggle: when ON notifications are sent; when OFF notification_scheduler and all sends stop
    notifications_on = st.toggle(
        "Notifications",
        value=get_notification_enabled(),
        key="notification_management_toggle",
        help="ON = send notifications. OFF = stop all notification sending (scheduler + app)."
    )
    # Persist to file so notification_scheduler (background) and app both respect it
    set_notification_enabled(notifications_on)
    st.session_state.notification_management_on = notifications_on
    
    if not notifications_on:
        st.warning("Notifications OFF. All notification sending is disabled (scheduler + app). Turn the toggle ON to resume.")
        if st.button("Close", key="close_notification_mgmt"):
            st.session_state.show_notification_management_dialog = False
            st.rerun()
        return
    
    tab_status, tab_log, tab_no_email, tab_cc = st.tabs(["⏱️ Scheduler Status", "📋 Send Log", "⚠️ Users Without Email", "📧 CC List"])
    
    with tab_status:
        st.subheader("Notification Scheduler Status")
        status_text, minutes_ago, is_likely_running = get_scheduler_status()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", status_text)
            if is_likely_running:
                st.success("Scheduler appears to be running in background (last run < 90 min ago)")
            else:
                st.warning("Scheduler may not be running. Last run was over 90 min ago or never.")
        with col2:
            st.caption("Background setup:")
            st.code("Windows: Task Scheduler → run run_notification_scheduler.bat every hour\nUbuntu: crontab -e → 0 * * * * python3 /path/to/notification_scheduler.py", language=None)
        
        st.markdown("---")
        st.subheader("Manual Actions")
        col_run, col_send, col_sample = st.columns(3)
        with col_run:
            if st.button("▶️ Run Scheduler Now", key="run_scheduler_btn", use_container_width=True,
                        help="Run the scheduler script as a subprocess (same as background run). Use if scheduler is not running."):
                with st.spinner("Running scheduler..."):
                    ok, out, err = run_scheduler_manual()
                    if ok:
                        st.success("Scheduler completed successfully.")
                        if out:
                            st.caption(out[:500])
                    else:
                        st.error("Scheduler failed or timed out.")
                        if err:
                            st.code(err[:500])
                st.rerun()
        with col_send:
            if st.button("📤 Send Notifications Now", key="send_notifications_btn", type="primary", use_container_width=True,
                        help="Execute notification logic immediately (TSR reminders, approval reminders, auto-cancel). For testing or immediate sending."):
                try:
                    if _script_dir not in sys.path:
                        sys.path.insert(0, _script_dir)
                    from notification_scheduler import run_scheduler
                    with st.spinner("Sending notifications..."):
                        run_scheduler()
                    st.success("Notifications sent. Check Send Log tab for results.")
                except Exception as e:
                    st.error(f"Error: {e}")
                st.rerun()
        with col_sample:
            if st.button("📧 Sample Sending Notification", key="sample_notification_btn", use_container_width=True,
                        help="Send sample of each notification type to subscription@innogen-pharma.com for verification."):
                try:
                    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    sd = datetime.now().strftime('%Y-%m-%d')
                    m1 = f"""<p>You have an order update.</p><p><strong>Order ID:</strong> ORD-SAMPLE</p><p><strong>Status:</strong> Pending</p><p><strong>Client:</strong> Sample Client</p><p><strong>Order Date:</strong> {ts}</p><p><strong>Total Amount:</strong> 1000.00</p><p><strong>Message:</strong> Order submitted successfully</p><p>Please log in to the Sales Order Management System to view details.</p>"""
                    m2 = f"""<p>You have a new booking request.</p><p><strong>Request ID:</strong> BR-SAMPLE</p><p><strong>Client:</strong> Sample Client</p><p><strong>Shipping Date:</strong> {sd}</p><p><strong>Created By:</strong> SampleUser</p><p><strong>Status:</strong> Pending</p><p>Please log in to the Sales Order Management System to complete this booking request.</p>"""
                    m3 = f"""<p>This order requires your Level 1 approval.</p><p><strong>Order ID:</strong> ORD-SAMPLE</p><p><strong>Status:</strong> Pending</p><p><strong>Client:</strong> Sample Client</p><p><strong>Order Date:</strong> {ts}</p><p><strong>Total Amount:</strong> 1000.00</p><p>Please log in to the Sales Order Management System to review and approve this order.</p>"""
                    m4 = f"""<p>This order requires your Level 2 approval.</p><p><strong>Order ID:</strong> ORD-SAMPLE</p><p><strong>Status:</strong> Pending</p><p><strong>Client:</strong> Sample Client</p><p>Please log in to the Sales Order Management System to review and approve this order.</p>"""
                    m5 = f"""<p><strong>Request ID:</strong> BR-SAMPLE</p><p><strong>Client:</strong> Sample Client</p><p><strong>Created:</strong> {ts} by SampleUser</p><p>This request will be auto-cancelled in 8 hours if not completed. Please log in to complete it.</p>"""
                    m6 = f"""<p>Order ORD-SAMPLE has been pending for over 16 hours. Please log in to approve.</p>"""
                    m7 = f"""<p>Order ORD-SAMPLE has been pending Level 2 approval for over 16 hours. Please log in to approve.</p>"""
                    m8 = f"""<p><strong>Request ID:</strong> BR-SAMPLE</p><p><strong>Client:</strong> Sample Client</p><p><strong>Status:</strong> Auto-Cancel</p><p><strong>Reason:</strong> Request was not completed within 24 hours.</p><p><strong>Cancelled At:</strong> {ts}</p><p>Please log in to the Sales Order Management System for details.</p>"""
                    samples = [
                        ("[Sample] Order ORD-SAMPLE - Order submitted successfully", build_notification_email("Order Notification", "Dear SampleUser,", m1, "View Order")),
                        ("[Sample] Booking Request BR-SAMPLE - New Request from SampleUser", build_notification_email("New Booking Request", "Dear TSR,", m2, "Complete Booking Request")),
                        ("[Sample] Order ORD-SAMPLE - Pending Level 1 Approval", build_notification_email("Order Approval Required", "Dear Admin Level 1 Ethical,", m3, "Review Order")),
                        ("[Sample] Order ORD-SAMPLE - Pending Level 2 Approval", build_notification_email("Order Approval Required", "Dear Admin Level 2,", m4, "Review Order")),
                        ("[Sample] Reminder: Booking Request BR-SAMPLE - Complete within 8 hours", build_notification_email("Booking Request Reminder", "Dear TSR,", m5, "Complete Booking Request")),
                        ("[Sample] Reminder: Order ORD-SAMPLE - Pending Level 1 Approval", build_notification_email("Approval Reminder", "Dear Admin Level 1 Ethical,", m6, "Review Orders")),
                        ("[Sample] Reminder: Order ORD-SAMPLE - Pending Level 2 Approval", build_notification_email("Approval Reminder", "Dear Admin Level 2,", m7, "Review Orders")),
                        ("[Sample] Booking Request BR-SAMPLE - Auto-Cancelled", build_notification_email("Booking Request Auto-Cancelled", "Dear User,", m8, "View App")),
                    ]
                    sent = 0
                    for subj, body in samples:
                        if send_email_notification(SAMPLE_NOTIFICATION_RECIPIENT, subj, body):
                            sent += 1
                    if sent == len(samples):
                        st.success(f"All {sent} sample notifications sent to {SAMPLE_NOTIFICATION_RECIPIENT}")
                    elif sent > 0:
                        st.warning(f"Sent {sent}/{len(samples)} samples. Check Send.txt for failures.")
                    else:
                        st.error("Failed to send sample notifications. Check Send.txt and email config.")
                except Exception as e:
                    st.error(f"Error: {e}")
                st.rerun()
    
    with tab_log:
        logs_df = db.get_notification_logs(limit=500)
        if logs_df.empty:
            st.info("No notification logs yet.")
        else:
            display_cols = ['timestamp', 'notification_type', 'recipient_type', 'recipient_id', 'order_id', 'request_id', 'status', 'message']
            available = [c for c in display_cols if c in logs_df.columns]
            st.dataframe(logs_df[available] if available else logs_df, use_container_width=True, hide_index=True)
            st.caption(f"Showing last 500 entries. Status: Sent = delivered; Failed to Send = no email or error.")
    
    with tab_no_email:
        users_dict = db.get_all_users()
        no_email_users = []
        for username, data in users_dict.items():
            email = data.get('email')
            if not email or not str(email).strip():
                role = data.get('role', '')
                rep_code = data.get('rep_code', '')
                rep_name = data.get('rep_name', '')
                no_email_users.append({'Username': username, 'Role': role, 'Rep Code': rep_code, 'Rep Name': rep_name})
        if not no_email_users:
            st.success("All users have email configured.")
        else:
            st.warning(f"{len(no_email_users)} user(s) without email - notifications to these users will show 'Failed to Send' in the log.")
            st.dataframe(pd.DataFrame(no_email_users), use_container_width=True, hide_index=True)
    
    with tab_cc:
        st.subheader("Email CC List")
        st.caption("All notification emails will CC these addresses. Add, edit, or delete rows. Click Save to apply.")
        cc_df = db.get_cc_emails_df()
        if cc_df.empty:
            cc_df = pd.DataFrame(columns=[
                'id', 'email', 'display_order', 'notify_booking', 
                'notify_submission_approval', 'notify_fully_approved', 
                'notify_disapproved', 'notify_overdue', 'notify_autocancel'
            ])
            cc_df = pd.concat([cc_df, pd.DataFrame([{
                'id': None, 'email': '', 'display_order': 0, 
                'notify_booking': True, 'notify_submission_approval': True, 
                'notify_fully_approved': True, 'notify_disapproved': False, 
                'notify_overdue': False, 'notify_autocancel': False
            }])], ignore_index=True)
        
        # Ensure boolean columns for editor and set defaults for new rows added via the editor UI
        for col in ['notify_booking', 'notify_submission_approval', 'notify_fully_approved']:
            if col in cc_df.columns:
                cc_df[col] = cc_df[col].astype(bool)
            else:
                cc_df[col] = True
        
        for col in ['notify_disapproved', 'notify_overdue', 'notify_autocancel']:
            if col in cc_df.columns:
                cc_df[col] = cc_df[col].astype(bool)
            else:
                cc_df[col] = False

        edited_cc = st.data_editor(
            cc_df,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "email": st.column_config.TextColumn("Email", required=True, width="large"),
                "notify_booking": st.column_config.CheckboxColumn("Booking"),
                "notify_submission_approval": st.column_config.CheckboxColumn("Submission & Approval"),
                "notify_fully_approved": st.column_config.CheckboxColumn("Fully Approved"),
                "notify_disapproved": st.column_config.CheckboxColumn("Disapproved"),
                "notify_overdue": st.column_config.CheckboxColumn("Overdue"),
                "notify_autocancel": st.column_config.CheckboxColumn("Auto-Cancel"),
                "display_order": st.column_config.NumberColumn("Order", width="small"),
            },
            use_container_width=True,
            num_rows="dynamic",
            key="notification_cc_editor",
            hide_index=True,
        )
        if st.button("💾 Save CC List", key="save_cc_list_btn", type="primary"):
            # Filter out rows with empty email
            to_save = edited_cc[edited_cc['email'].fillna('').astype(str).str.strip() != ''].copy()
            if to_save.empty:
                st.warning("At least one email is required. Add an email and save.")
            elif db.save_cc_emails(to_save):
                st.success("CC list saved. Changes apply to all future notifications.")
                st.rerun()
            else:
                st.error("Failed to save CC list.")
    
    if st.button("Close", key="close_notification_mgmt"):
        st.session_state.show_notification_management_dialog = False
        st.rerun()

# List of Accounts Dialog Function
@st.dialog(title="📋 List of Accounts", width="large", dismissible=True)
def accounts_dialog():
    """Dialog function for viewing and editing accounts"""
    st.header("List of Accounts")
    add_mode = st.session_state.get('accounts_add_mode', False)
    if add_mode:
        st.info("✏️ Add Mode: All columns are editable. Click 'Save Changes' to save and return to view mode.")
    else:
        st.info("Edit the Active status and Area using the toggle/fields. Click '➕ Add Account' to add new accounts (all columns will become editable).")
    
    # Bulk Upload Accounts - under expander
    with st.expander("📤 Bulk Upload Accounts", expanded=False):
        st.caption("Download the template, fill in account data, then upload the CSV to add/update multiple accounts.")
        all_cols = ['Customer code', 'Customer name', 'lvl1_short_name', 'lvl2_short_name', 'lvl3_short_name',
                    'Credit term', 'Class code', 'channel_code', 'br_name', 'Business address',
                    'Contact number1', 'tin', 'Contact person1', 'Active', 'Area', 'SGF', 'SGF_count',
                    'TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag', 'Account_Type']
        col_dl, col_up = st.columns(2)
        with col_dl:
            template_df = pd.DataFrame(columns=all_cols)
            template_df.loc[0] = [
                '1556', '1088 A. PHARMACY', '', '', '', 'COD', '', '', '', '',
                '', '', '', 'TRUE', 'North', 'FALSE', 99,
                'TSR001', 'CLI001', '', '', 'Dispensing'
            ]
            template_csv = template_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 Download Template",
                data=template_csv,
                file_name="accounts_template.csv",
                mime="text/csv",
                use_container_width=True,
                key="accounts_download_template",
                help="Download CSV template with account fields. Fill in rows and upload below."
            )
        with col_up:
            uploaded_accounts_file = st.file_uploader(
                "Upload CSV or Excel",
                type=['csv', 'xlsx', 'xls'],
                key="bulk_upload_accounts_csv",
                help="Upload filled template to bulk add/update accounts (CSV or Excel)"
            )
            if st.session_state.get('accounts_bulk_upload_just_done'):
                st.session_state.accounts_bulk_upload_just_done = False
                uploaded_accounts_file = None
            force_active_all = st.checkbox(
                "Set Active=TRUE for all uploaded accounts",
                value=False,
                key="bulk_upload_force_active",
                help="Override CSV Active column and mark all uploaded accounts as Active. Use when your CSV has FALSE/0/blank in Active but you want them all active."
            )
            process_accounts_btn = st.button(
                "Process Upload",
                type="primary",
                key="bulk_upload_accounts_process",
                use_container_width=True,
                help="Click to process the uploaded CSV/Excel file"
            )
            if uploaded_accounts_file and process_accounts_btn:
                progress_placeholder = st.empty()
                try:
                    # Support both CSV and Excel uploads
                    filename = getattr(uploaded_accounts_file, "name", "") or ""
                    lower_name = filename.lower()
                    if lower_name.endswith(".csv"):
                        try:
                            upload_df = pd.read_csv(uploaded_accounts_file, encoding='utf-8')
                        except UnicodeDecodeError:
                            uploaded_accounts_file.seek(0)
                            try:
                                upload_df = pd.read_csv(uploaded_accounts_file, encoding='cp1252')
                            except UnicodeDecodeError:
                                uploaded_accounts_file.seek(0)
                                upload_df = pd.read_csv(uploaded_accounts_file, encoding='latin-1')
                    elif lower_name.endswith(".xlsx"):
                        try:
                            upload_df = pd.read_excel(uploaded_accounts_file, engine='openpyxl')
                        except ImportError as e:
                            progress_placeholder.empty()
                            st.error(f"Error reading Excel file: {e}. Please install 'openpyxl' (pip install openpyxl) or upload as CSV instead.")
                            return
                    elif lower_name.endswith(".xls"):
                        try:
                            upload_df = pd.read_excel(uploaded_accounts_file, engine='xlrd')
                        except ImportError:
                            progress_placeholder.empty()
                            st.error("Old Excel (.xls) format requires 'xlrd'. Install with: pip install xlrd. Or save the file as .xlsx / CSV and upload instead.")
                            return
                        except Exception as e:
                            progress_placeholder.empty()
                            st.error(f"Error reading .xls file: {e}")
                            return
                    else:
                        progress_placeholder.empty()
                        st.error("Unsupported file type. Please upload a CSV or Excel file.")
                        return
                    upload_df.columns = upload_df.columns.str.strip()
                    # Normalize column names (case-insensitive, treat spaces and underscores alike)
                    # e.g. "TSR Tag" and "TSR_tag" both map to "TSR_tag" - template columns match exactly
                    def _norm_col(s):
                        return str(s).lower().replace(' ', '').replace('_', '')
                    col_map = {_norm_col(c): c for c in all_cols}
                    upload_df.columns = [col_map.get(_norm_col(c), c) for c in upload_df.columns]
                    required = ['Customer code', 'Customer name']
                    missing = [c for c in required if c not in upload_df.columns]
                    if missing:
                        st.error(f"Template missing required columns: {missing}. Please use the downloaded template.")
                    else:
                        # Filter: remove blanks and nulls - keep only rows with valid Customer code AND Customer name
                        before_count = len(upload_df)
                        cc_col = upload_df.get('Customer code', pd.Series(dtype=object))
                        cn_col = upload_df.get('Customer name', pd.Series(dtype=object))
                        cc_ok = cc_col.fillna('').astype(str).str.strip() != ''
                        cn_ok = cn_col.fillna('').astype(str).str.strip() != ''
                        upload_df = upload_df[cc_ok & cn_ok].copy().reset_index(drop=True)
                        skipped = before_count - len(upload_df)
                        if len(upload_df) == 0:
                            progress_placeholder.empty()
                            st.warning(f"No valid rows to process. All {before_count} row(s) had blank Customer code or Customer name.")
                        else:
                            if skipped > 0:
                                progress_placeholder.info(f"Filtered {skipped} blank/null row(s). Processing {len(upload_df)} valid rows...")
                            progress_placeholder.info("Loading accounts...")
                            accounts_df = load_accounts()
                            if accounts_df.empty:
                                accounts_df = pd.DataFrame(columns=all_cols)
                            for col in all_cols:
                                if col not in accounts_df.columns:
                                    accounts_df[col] = ''
                            def _norm_cc(v):
                                """Normalize customer code: 396, 396.0, '396' -> '396' for consistent string/numeric matching."""
                                if v is None or (isinstance(v, float) and pd.isna(v)):
                                    return ''
                                try:
                                    return str(int(float(str(v).strip())))
                                except (ValueError, TypeError):
                                    return str(v).strip()
                            success_count = 0
                            active_saved = 0
                            inactive_saved = 0
                            error_rows = []
                            new_rows_list = []
                            old_codes_to_delete = set()  # e.g. 396.0 when consolidating to 396
                            total = len(upload_df)
                            for idx, row in upload_df.iterrows():
                                if total > 20 and idx % 50 == 0:
                                    progress_placeholder.info(f"Processing row {idx + 1} of {total}...")
                                cc = _norm_cc(row.get('Customer code', ''))
                                cn = str(row.get('Customer name', '')).strip()
                                if not cc or not cn:
                                    continue
                                new_row = {c: '' for c in all_cols}
                                new_row['Active'] = 'TRUE'   # Default Active to True for bulk upload
                                new_row['SGF'] = 'FALSE'    # Default SGF to False for bulk upload
                                for col in all_cols:
                                    val = row.get(col, '')
                                    if pd.isna(val):
                                        val = ''
                                    if col == 'Active':
                                        if force_active_all:
                                            new_row[col] = 'TRUE'
                                        else:
                                            new_row[col] = 'FALSE' if str(val).strip().upper() in ('FALSE', '0', 'NO', 'N') else 'TRUE'
                                    elif col == 'SGF':
                                        new_row[col] = 'TRUE' if str(val).strip().upper() in ('TRUE', '1', 'YES', 'Y') else 'FALSE'
                                    elif col == 'SGF_count':
                                        try:
                                            new_row[col] = int(float(str(val))) if str(val).strip() else 99
                                        except (ValueError, TypeError):
                                            new_row[col] = 99
                                    elif col == 'Account_Type':
                                        # Accept value from 'Account_Type' or 'Account Type' (Excel may use space); case-insensitive
                                        v = str(val).strip() or str(row.get('Account Type', '')).strip() or 'Dispensing'
                                        v_upper = v.upper()
                                        if v_upper == 'TRADE':
                                            new_row[col] = 'TRADE'
                                        elif v_upper == 'DISTRIBUTION':
                                            new_row[col] = 'Distribution'
                                        elif v_upper == 'CONTRACT':
                                            new_row[col] = 'Contract'
                                        elif v_upper in ('DISPENSING', ''):
                                            new_row[col] = 'Dispensing'
                                        else:
                                            new_row[col] = 'Dispensing'
                                    else:
                                        new_row[col] = str(val).strip() if val else ''
                                new_row['Customer code'] = cc
                                new_row['Customer name'] = cn
                                # Ensure Active=TRUE, SGF=FALSE when blank (applies to both new and overwrite)
                                if not str(new_row.get('Active', '')).strip().upper() in ('TRUE', 'FALSE'):
                                    new_row['Active'] = 'TRUE'
                                if not str(new_row.get('SGF', '')).strip().upper() in ('TRUE', 'FALSE'):
                                    new_row['SGF'] = 'FALSE'
                                try:
                                    # Overwrite existing rows when Customer code + Customer name match
                                    # cc is already normalized; normalize DB values for match (396, 396.0, "396" all match)
                                    name_match = accounts_df['Customer name'].astype(str).str.strip() == cn
                                    cc_norm_match = accounts_df['Customer code'].apply(
                                        lambda x: _norm_cc(x) == cc
                                    )
                                    mask = name_match & cc_norm_match
                                    existing_idx = accounts_df[mask].index
                                    if len(existing_idx) > 0:
                                        # Overwrite ALL matching rows (handles duplicates like 1556 vs 1556.0)
                                        # Track old customer_codes we're replacing (e.g. 396.0 -> 396) for DB cleanup
                                        for idx in existing_idx:
                                            old_cc = str(accounts_df.at[idx, 'Customer code']).strip()
                                            if old_cc != cc:
                                                old_codes_to_delete.add(old_cc)
                                        for col in all_cols:
                                            val = new_row.get(col, '')
                                            for idx in existing_idx:
                                                accounts_df.at[idx, col] = val
                                    else:
                                        new_rows_list.append(new_row)
                                    success_count += 1
                                    if str(new_row.get('Active', '')).strip().upper() == 'TRUE':
                                        active_saved += 1
                                    else:
                                        inactive_saved += 1
                                except Exception as e:
                                    error_rows.append((idx + 2, cc, str(e)))
                            if new_rows_list:
                                progress_placeholder.info("Saving accounts...")
                                accounts_df = pd.concat([accounts_df, pd.DataFrame(new_rows_list)], ignore_index=True)
                            if success_count > 0:
                                # Normalize Customer code column (396.0, 396, "396" -> "396") for consistent dedup
                                accounts_df['Customer code'] = accounts_df['Customer code'].apply(_norm_cc)
                                # Drop duplicate customer_codes (e.g. two 396s after consolidating 396.0 -> 396)
                                accounts_df = accounts_df.drop_duplicates(subset=['Customer code'], keep='first').reset_index(drop=True)
                                if save_accounts(accounts_df, customer_codes_to_delete=list(old_codes_to_delete)):
                                    progress_placeholder.empty()
                                    msg = f"Bulk upload: {success_count} account(s) saved."
                                    if active_saved + inactive_saved > 0:
                                        msg += f" ({active_saved} Active, {inactive_saved} Inactive)"
                                    if skipped > 0:
                                        msg += f" ({skipped} blank/null row(s) filtered out)"
                                    st.success(msg)
                                    if inactive_saved > active_saved and not force_active_all:
                                        st.info("Tip: Many accounts were saved as Inactive because the CSV had FALSE/0/NO/N in the Active column. Check **Set Active=TRUE for all uploaded accounts** above to override.")
                                    st.session_state.accounts_bulk_upload_just_done = True
                                    st.rerun()
                                else:
                                    progress_placeholder.empty()
                                    st.error("Error saving accounts.")
                            if error_rows:
                                progress_placeholder.empty()
                                st.warning(f"{len(error_rows)} row(s) skipped:")
                                for row_num, code, err in error_rows[:10]:
                                    st.caption(f"Row {row_num} ({code}): {err}")
                                if len(error_rows) > 10:
                                    st.caption(f"... and {len(error_rows) - 10} more")
                            progress_placeholder.empty()
                except Exception as e:
                    try:
                        progress_placeholder.empty()
                    except NameError:
                        pass
                    st.error(f"Error reading CSV: {e}")
            elif uploaded_accounts_file and not process_accounts_btn:
                st.info("File selected. Click **Process Upload** to import accounts.")
    
    # Check SQLite for blank account rows and remove them (skip when user just clicked Add Account — that blank is intentional)
    if not st.session_state.get('highlight_new_account_row', False):
        db.check_and_remove_blank_accounts()
    
    accounts_df = load_accounts()
    
    # If AREA column doesn't exist, add it with empty values (for backward compatibility)
    if not accounts_df.empty and 'Area' not in accounts_df.columns:
        accounts_df['Area'] = ''
        accounts_df['Area'] = accounts_df['Area'].astype('object')
    # If SGF column doesn't exist, add it with default value False
    if not accounts_df.empty and 'SGF' not in accounts_df.columns:
        accounts_df['SGF'] = 'FALSE'
    # If SGF_count column doesn't exist, add it with default value 99
    if not accounts_df.empty and 'SGF_count' not in accounts_df.columns:
        accounts_df['SGF_count'] = 99
    # Tagging and Account_Type columns (backward compatibility)
    needs_save = False
    for col_name, default_val in [
        ('TSR_tag', ''), ('PMR_tag', ''), ('DSMBU7_tag', ''), ('DSMPSI_tag', ''),
        ('Account_Type', 'Dispensing')
    ]:
        if not accounts_df.empty and col_name not in accounts_df.columns:
            accounts_df[col_name] = default_val
            needs_save = True
    if needs_save:
        save_accounts(accounts_df)
    
    # Clean stored data: remove any rows with blank Customer Code/Name and duplicates (skip when user just added a blank row)
    if not st.session_state.get('highlight_new_account_row', False) and not accounts_df.empty and 'Customer code' in accounts_df.columns and 'Customer name' in accounts_df.columns:
        before_count = len(accounts_df)
        cc_ok = accounts_df['Customer code'].fillna('').astype(str).str.strip() != ''
        cn_ok = accounts_df['Customer name'].fillna('').astype(str).str.strip() != ''
        accounts_df = accounts_df[cc_ok & cn_ok].copy()
        dup_cols = ['Customer code'] + (['Account_Type'] if 'Account_Type' in accounts_df.columns else [])
        accounts_df = accounts_df.drop_duplicates(subset=dup_cols, keep='first').reset_index(drop=True)
        if len(accounts_df) < before_count:
            save_accounts(accounts_df)
    
    if accounts_df.empty:
        st.warning("No accounts found. Please ensure the accounts CSV file exists.")
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Close", type="primary", use_container_width=True):
                st.session_state.show_accounts_dialog = False
                # Reset add mode and highlight when closing dialog
                st.session_state.accounts_add_mode = False
                st.session_state.highlight_new_account_row = False
                st.rerun()
        with col2:
            if st.button("➕ Add Account", type="secondary", use_container_width=True):
                st.session_state.show_add_account_dialog = True
                st.rerun()
    else:
        # Select only the columns to display
        display_cols = ['Customer code', 'Customer name', 'Credit term', 'Area', 'Active', 'SGF', 'SGF_count',
                       'TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag', 'Account_Type']
        available_cols = [col for col in display_cols if col in accounts_df.columns]
        
        if len(available_cols) < len(display_cols):
            missing_cols = [col for col in display_cols if col not in accounts_df.columns]
            st.warning(f"Missing columns in CSV: {', '.join(missing_cols)}")
            st.info("Available columns: " + ", ".join(accounts_df.columns.tolist()))
        
        # Create display dataframe with only selected columns
        if available_cols:
            # Add buttons at the top right (Add Account, Download complete columns)
            col_title, col_add, col_download = st.columns([3, 1, 1])
            with col_title:
                row_count = len(accounts_df)
                st.markdown(f"### Accounts Table ({row_count:,} record{'s' if row_count != 1 else ''})")
            with col_add:
                if st.button("➕ Add Account", type="primary", use_container_width=True):
                    # Enable add mode to make all columns editable
                    st.session_state.accounts_add_mode = True
                    # Add a new empty row to accounts_df
                    new_row = {}
                    for col in available_cols:
                        if col == 'Active':
                            new_row[col] = 'TRUE'
                        elif col == 'SGF':
                            new_row[col] = 'FALSE'
                        elif col == 'SGF_count':
                            new_row[col] = 99
                        elif col == 'Account_Type':
                            new_row[col] = 'Dispensing'
                        elif col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
                            new_row[col] = ''
                        else:
                            new_row[col] = ''
                    
                    # Ensure all columns from accounts_df are included
                    for col in accounts_df.columns:
                        if col not in new_row:
                            if col == 'SGF':
                                new_row[col] = 'FALSE'
                            elif col == 'SGF_count':
                                new_row[col] = 99
                            elif col == 'Account_Type':
                                new_row[col] = 'Dispensing'
                            elif col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
                                new_row[col] = ''
                            else:
                                new_row[col] = ''
                    
                    new_row_df = pd.DataFrame([new_row])
                    if accounts_df.empty:
                        accounts_df = new_row_df
                    else:
                        accounts_df = pd.concat([accounts_df, new_row_df], ignore_index=True)
                    # Save the updated dataframe
                    save_accounts(accounts_df)
                    # Set flag to scroll to bottom and highlight new row after rerun
                    st.session_state.scroll_to_bottom_accounts = True
                    st.session_state.highlight_new_account_row = True
                    st.rerun()
            with col_download:
                # Download complete columns (full accounts_df) as CSV
                full_csv = accounts_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 Download",
                    data=full_csv,
                    file_name=f"accounts_complete_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    help="Download accounts with all columns",
                    use_container_width=True,
                    key="accounts_download_complete_btn"
                )
            
            # Active Accounts label (updates every toggle/rerun)
            if 'Active' in accounts_df.columns:
                active_count = (accounts_df['Active'].fillna('').astype(str).str.upper().str.strip() == 'TRUE').sum()
                st.caption(f"**Active Accounts:** {active_count:,}")
            
            # Button: Set Active=False for all ACTIVE accounts without PMR_tag (empty or null)
            if 'PMR_tag' in accounts_df.columns and 'Active' in accounts_df.columns:
                def _has_no_pmr_tag(s):
                    v = str(s).strip().upper() if pd.notna(s) and s != '' else ''
                    return v == '' or v in ('NONE', 'NAN', 'N/A', 'NULL')
                no_pmr_mask = accounts_df['PMR_tag'].apply(_has_no_pmr_tag)
                active_mask = accounts_df['Active'].fillna('').astype(str).str.upper().str.strip() == 'TRUE'
                # Count only ACTIVE accounts without PMR_tag (these will actually change)
                to_deactivate_count = (no_pmr_mask & active_mask).sum()
                if st.button(
                    f"Set Active=False for accounts without PMR_tag ({to_deactivate_count} active account{'s' if to_deactivate_count != 1 else ''} to deactivate)",
                    key="deactivate_no_pmr_btn",
                    help="Sets Active=False for active accounts where PMR_tag is empty or null."
                ):
                    if to_deactivate_count > 0:
                        accounts_df.loc[no_pmr_mask & active_mask, 'Active'] = 'FALSE'
                        if save_accounts(accounts_df):
                            st.success(f"Set Active=False for {to_deactivate_count} account(s) without PMR_tag.")
                            st.rerun()
                        else:
                            st.error("Failed to save accounts.")
                    else:
                        st.info("No active accounts without PMR_tag found. All accounts without PMR_tag are already inactive.")
            
            # Button: Remove duplicate account codes (e.g. 1556.0 when 1556 exists)
            dup_count = db.count_duplicate_account_codes()
            if st.button(
                f"Remove duplicate account codes ({dup_count} duplicate{'s' if dup_count != 1 else ''} to remove)",
                key="remove_dup_account_codes_btn",
                help="Removes rows where customer_code is 'X.0' when 'X' exists for same customer (e.g. 1556.0 when 1556). Keeps the integer version."
            ):
                if dup_count > 0:
                    removed = db.check_and_remove_duplicate_account_codes()
                    if removed > 0:
                        st.success(f"Removed {removed} duplicate account row(s). List of Accounts and selectbox now use same data.")
                        st.rerun()
                    else:
                        st.warning("No duplicates were removed.")
                else:
                    st.info("No duplicate account codes found.")
            
            display_df = accounts_df[available_cols].copy()
            
            # Preserve original index for mapping back to accounts_df
            display_df['_original_index'] = display_df.index
            
            # Exclude rows with blank Customer Code or Customer Name so they never appear (except when we just added one for the user to fill)
            if not st.session_state.get('highlight_new_account_row', False):
                if 'Customer code' in display_df.columns and 'Customer name' in display_df.columns:
                    cc_ok = display_df['Customer code'].fillna('').astype(str).str.strip() != ''
                    cn_ok = display_df['Customer name'].fillna('').astype(str).str.strip() != ''
                    display_df = display_df[cc_ok & cn_ok].copy()
            
            # Sort by Customer Name (case-insensitive); put new blank row at top when just added
            if 'Customer name' in display_df.columns:
                display_df['_sort_temp'] = display_df['Customer name'].astype(str).str.lower()
                na_pos = 'first' if st.session_state.get('highlight_new_account_row', False) else 'last'
                display_df = display_df.sort_values('_sort_temp', na_position=na_pos).reset_index(drop=True)
                display_df = display_df.drop(columns=['_sort_temp'])
            
            # Convert Active column to boolean for checkbox/toggle
            if 'Active' in display_df.columns:
                # Convert TRUE/FALSE strings to boolean
                display_df['Active'] = display_df['Active'].astype(str).str.upper() == 'TRUE'
            
            # Convert SGF column to boolean for checkbox/toggle
            if 'SGF' in display_df.columns:
                # Convert TRUE/FALSE strings to boolean
                display_df['SGF'] = display_df['SGF'].astype(str).str.upper() == 'TRUE'
            
            # Convert SGF_count column to numeric
            if 'SGF_count' in display_df.columns:
                display_df['SGF_count'] = pd.to_numeric(display_df['SGF_count'], errors='coerce').fillna(99)
            
            # Convert Customer code column to string type to avoid integer type issues
            if 'Customer code' in display_df.columns:
                # Convert to string, handling NaN values and removing decimals
                def clean_customer_code(value):
                    if pd.isna(value) or value == '' or value is None:
                        return ''
                    try:
                        # Try to convert to int first to remove decimals, then to string
                        return str(int(float(str(value))))
                    except (ValueError, TypeError):
                        # If conversion fails, just return as string without decimals
                        return str(value).split('.')[0] if '.' in str(value) else str(value)
                
                display_df['Customer code'] = display_df['Customer code'].apply(clean_customer_code)
                # Explicitly set dtype to object (string) to prevent integer interpretation
                display_df['Customer code'] = display_df['Customer code'].astype('object')
            
            # Convert Area column to string type to avoid float type issues
            if 'Area' in display_df.columns:
                # Convert to string, handling NaN values - use object dtype to ensure it's treated as string
                display_df['Area'] = display_df['Area'].fillna('').astype(str).replace('nan', '').replace('NaN', '').replace('None', '')
                # Explicitly set dtype to object (string) to prevent float interpretation
                display_df['Area'] = display_df['Area'].astype('object')
            
            # Use data_editor with editable columns (hide the _original_index column)
            # Only Area and Active are editable by default; all columns editable when in add mode
            add_mode = st.session_state.get('accounts_add_mode', False)
            
            column_config = {}
            for col in available_cols:
                if col == 'Active':
                    column_config[col] = st.column_config.CheckboxColumn(
                        "Active",
                        help="Toggle to activate/deactivate account"
                    )
                elif col == 'Customer code':
                    # Editable only when in add mode
                    column_config[col] = st.column_config.TextColumn(
                        "Customer Code", 
                        help="Enter customer code" if add_mode else "Customer code (editable when adding new account)",
                        disabled=not add_mode
                    )
                elif col == 'Customer name':
                    # Editable only when in add mode
                    column_config[col] = st.column_config.TextColumn(
                        "Customer Name", 
                        help="Enter customer name" if add_mode else "Customer name (editable when adding new account)",
                        disabled=not add_mode
                    )
                elif col == 'Credit term':
                    # Editable only when in add mode
                    column_config[col] = st.column_config.TextColumn(
                        "Credit Term", 
                        help="Enter credit term (e.g., COD, 30D)" if add_mode else "Credit term (editable when adding new account)",
                        disabled=not add_mode
                    )
                elif col == 'Area':
                    column_config[col] = st.column_config.TextColumn("Area", help="Edit the area for this account")
                elif col == 'SGF':
                    column_config[col] = st.column_config.CheckboxColumn(
                        "SGF",
                        help="Toggle SGF status"
                    )
                elif col == 'SGF_count':
                    column_config[col] = st.column_config.NumberColumn(
                        "SGF Count",
                        help="Enter SGF count",
                        min_value=0,
                        step=1,
                        format="%d"
                    )
                elif col == 'TSR_tag':
                    column_config[col] = st.column_config.TextColumn(
                        "TSR Tag",
                        help="Tag for TSR"
                    )
                elif col == 'PMR_tag':
                    column_config[col] = st.column_config.TextColumn(
                        "PMR Tag",
                        help="Tag for PMR"
                    )
                elif col == 'DSMBU7_tag':
                    column_config[col] = st.column_config.TextColumn(
                        "DSM BU7 Tag",
                        help="Tag for DSM BU7"
                    )
                elif col == 'DSMPSI_tag':
                    column_config[col] = st.column_config.TextColumn(
                        "DSM SPI Tag",
                        help="Tag for DSM SPI"
                    )
                elif col == 'Account_Type':
                    column_config[col] = st.column_config.SelectboxColumn(
                        "Account Type",
                        options=["Dispensing", "TRADE", "Distribution", "Contract"],
                        default="Dispensing",
                        required=True,
                        help="Select account type (restricted to valid options only)"
                    )
            
            # Create editor dataframe with only visible columns (exclude _original_index from display)
            editor_df = display_df[available_cols].copy()
            
            # Ensure Customer code column is string type in editor_df as well (explicit object dtype)
            if 'Customer code' in editor_df.columns:
                # Convert to string, handling NaN values and removing decimals
                def clean_customer_code(value):
                    if pd.isna(value) or value == '' or value is None:
                        return ''
                    try:
                        # Try to convert to int first to remove decimals, then to string
                        return str(int(float(str(value))))
                    except (ValueError, TypeError):
                        # If conversion fails, just return as string without decimals
                        return str(value).split('.')[0] if '.' in str(value) else str(value)
                
                editor_df['Customer code'] = editor_df['Customer code'].apply(clean_customer_code)
                editor_df['Customer code'] = editor_df['Customer code'].astype('object')
            
            # Ensure Area column is string type in editor_df as well (explicit object dtype)
            if 'Area' in editor_df.columns:
                editor_df['Area'] = editor_df['Area'].fillna('').astype(str).replace('nan', '').replace('NaN', '').replace('None', '')
                editor_df['Area'] = editor_df['Area'].astype('object')
            
            # Ensure SGF column is boolean type in editor_df
            if 'SGF' in editor_df.columns:
                editor_df['SGF'] = editor_df['SGF'].astype(bool) if 'SGF' in editor_df.columns else False
            
            # Ensure SGF_count column is numeric type in editor_df
            if 'SGF_count' in editor_df.columns:
                editor_df['SGF_count'] = pd.to_numeric(editor_df['SGF_count'], errors='coerce').fillna(99)
            # Ensure tagging and Account_Type columns have correct types
            for tag_col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
                if tag_col in editor_df.columns:
                    editor_df[tag_col] = editor_df[tag_col].fillna('').astype(str).replace('nan', '').replace('NaN', '')
            if 'Account_Type' in editor_df.columns:
                editor_df['Account_Type'] = editor_df['Account_Type'].fillna('Dispensing').astype(str).replace('nan', 'Dispensing')
                editor_df['Account_Type'] = editor_df['Account_Type'].apply(
                    lambda x: x if x in ('Dispensing', 'TRADE', 'Distribution', 'Contract') else 'Dispensing'
                )
            # Store _original_index separately for mapping during save
            original_indices = display_df['_original_index'].copy() if '_original_index' in display_df.columns else None
            
            # Highlight new row and show message when a row was just added
            if st.session_state.get('highlight_new_account_row', False):
                st.info("★ **New row added** — The row highlighted below is the new row. Fill in the details and click Save Changes.")
            
            edited_df = st.data_editor(
                editor_df,
                column_config=column_config,
                use_container_width=True,
                key="accounts_editor",
                num_rows="dynamic",  # Allow adding new rows
                hide_index=True
            )
            
            # Scroll to bottom if a new row was added
            if st.session_state.get('scroll_to_bottom_accounts', False):
                st.markdown("""
                    <script>
                    (function() {
                        // Wait for the data editor to be fully rendered
                        setTimeout(function() {
                            // Find the data editor container
                            const dataEditor = document.querySelector('[data-testid="stDataEditor"]');
                            if (dataEditor) {
                                // Scroll to the bottom of the data editor
                                dataEditor.scrollTop = dataEditor.scrollHeight;
                                // Also try scrolling the parent container
                                const parentContainer = dataEditor.closest('.element-container');
                                if (parentContainer) {
                                    parentContainer.scrollIntoView({ behavior: 'smooth', block: 'end' });
                                }
                            }
                            // Also try scrolling the dialog content
                            const dialogContent = document.querySelector('[data-testid="stDialog"]');
                            if (dialogContent) {
                                dialogContent.scrollTop = dialogContent.scrollHeight;
                            }
                        }, 300);
                    })();
                    </script>
                """, unsafe_allow_html=True)
                # Reset the flag
                st.session_state.scroll_to_bottom_accounts = False
            
            # Add _original_index back to edited_df for save mapping (only for existing rows)
            if original_indices is not None and len(original_indices) > 0:
                # Extend original_indices with None for new rows
                if len(edited_df) > len(original_indices):
                    extended_indices = list(original_indices.values) + [None] * (len(edited_df) - len(original_indices))
                    edited_df['_original_index'] = extended_indices
                else:
                    edited_df['_original_index'] = original_indices.values[:len(edited_df)]
            
            # Save button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Changes", type="primary", use_container_width=True):
                    # Reload accounts_df to get latest data
                    accounts_df = load_accounts()
                    
                    # Build new accounts dataframe from edited_df
                    new_accounts_list = []
                    
                    for idx in edited_df.index:
                        row_data = {}
                        is_new_row = False
                        
                        # Check if this is a new row (no _original_index or _original_index is None)
                        if '_original_index' not in edited_df.columns or pd.isna(edited_df.at[idx, '_original_index']):
                            is_new_row = True
                        else:
                            original_idx = int(edited_df.at[idx, '_original_index'])
                            if original_idx >= len(accounts_df):
                                is_new_row = True
                        
                        # Get all column values
                        for col in available_cols:
                            if col in edited_df.columns:
                                value = edited_df.at[idx, col]
                                
                                if col == 'Active':
                                    # Convert boolean to TRUE/FALSE string
                                    row_data[col] = 'TRUE' if value else 'FALSE'
                                elif col == 'SGF':
                                    # Convert boolean to TRUE/FALSE string
                                    row_data[col] = 'TRUE' if value else 'FALSE'
                                elif col == 'SGF_count':
                                    # Convert to integer
                                    try:
                                        row_data[col] = int(float(value)) if pd.notna(value) else 99
                                    except (ValueError, TypeError):
                                        row_data[col] = 99
                                elif col == 'Account_Type':
                                    val = str(value).strip() if pd.notna(value) else 'Dispensing'
                                    row_data[col] = val if val in ('Dispensing', 'TRADE', 'Distribution', 'Contract') else 'Dispensing'
                                else:
                                    # Handle text columns
                                    if pd.isna(value) or value is None:
                                        row_data[col] = ''
                                    else:
                                        row_data[col] = str(value).strip()
                        
                        # If it's a new row, add it; otherwise update existing
                        if is_new_row:
                            # Validate required fields for new rows
                            customer_code = row_data.get('Customer code', '').strip()
                            customer_name = row_data.get('Customer name', '').strip()
                            credit_term = row_data.get('Credit term', '').strip().upper()
                            
                            if customer_code and customer_name:
                                # Skip if Customer code + Account_Type combination already exists (avoid duplicates)
                                account_type = row_data.get('Account_Type', 'Dispensing').strip() or 'Dispensing'
                                existing_pairs = set()
                                if 'Customer code' in accounts_df.columns:
                                    for _, r in accounts_df.iterrows():
                                        cc = str(r.get('Customer code', '')).strip()
                                        at = str(r.get('Account_Type', 'Dispensing')).strip() or 'Dispensing'
                                        existing_pairs.add((cc, at))
                                existing_pairs.update(((r.get('Customer code', '').strip(), str(r.get('Account_Type', 'Dispensing') or 'Dispensing').strip()) for r in new_accounts_list))
                                if (customer_code, account_type) in existing_pairs:
                                    continue  # Skip duplicate Customer code + Account_Type
                                # Special rule: If Credit Term is 'COD', set SGF=True and SGF_count=1
                                if credit_term == 'COD':
                                    row_data['SGF'] = 'TRUE'
                                    row_data['SGF_count'] = 1
                                new_accounts_list.append(row_data)
                            # Skip empty new rows
                        else:
                            # Update existing row
                            original_idx = int(edited_df.at[idx, '_original_index'])
                            if original_idx < len(accounts_df):
                                for col in available_cols:
                                    if col in row_data:
                                        # Handle SGF_count as numeric
                                        if col == 'SGF_count':
                                            accounts_df.at[original_idx, col] = int(row_data[col])
                                        # Handle SGF as string (TRUE/FALSE)
                                        elif col == 'SGF':
                                            accounts_df.at[original_idx, col] = row_data[col]
                                        else:
                                            accounts_df.at[original_idx, col] = row_data[col]
                                # CRITICAL: Propagate Active to ALL rows with same Customer name (handles duplicates e.g. 1556 vs 1556.0)
                                # Ensures List of Accounts and selectbox see same data - single source of truth
                                if 'Active' in row_data and 'Customer name' in accounts_df.columns:
                                    cn = str(accounts_df.at[original_idx, 'Customer name']).strip()
                                    if cn:
                                        same_name_mask = accounts_df['Customer name'].astype(str).str.strip() == cn
                                        accounts_df.loc[same_name_mask, 'Active'] = row_data['Active']
                    
                    # Add new rows to accounts_df
                    if new_accounts_list:
                        new_rows_df = pd.DataFrame(new_accounts_list)
                        # Ensure Customer code is string type
                        if 'Customer code' in new_rows_df.columns:
                            new_rows_df['Customer code'] = new_rows_df['Customer code'].astype('object')
                        # Ensure Area is string type
                        if 'Area' in new_rows_df.columns:
                            new_rows_df['Area'] = new_rows_df['Area'].astype('object')
                        # Ensure SGF is string type
                        if 'SGF' in new_rows_df.columns:
                            new_rows_df['SGF'] = new_rows_df['SGF'].astype(str).str.upper()
                        # Ensure SGF_count is numeric type
                        if 'SGF_count' in new_rows_df.columns:
                            new_rows_df['SGF_count'] = pd.to_numeric(new_rows_df['SGF_count'], errors='coerce').fillna(99)
                        # Ensure tagging and Account_Type columns
                        for tag_col in ('TSR_tag', 'PMR_tag', 'DSMBU7_tag', 'DSMPSI_tag'):
                            if tag_col in new_rows_df.columns:
                                new_rows_df[tag_col] = new_rows_df[tag_col].fillna('').astype(str)
                        if 'Account_Type' in new_rows_df.columns:
                            new_rows_df['Account_Type'] = new_rows_df['Account_Type'].fillna('Dispensing').astype(str)
                            new_rows_df['Account_Type'] = new_rows_df['Account_Type'].apply(
                                lambda x: x if x in ('Dispensing', 'TRADE', 'Distribution', 'Contract') else 'Dispensing'
                            )
                        accounts_df = pd.concat([accounts_df, new_rows_df], ignore_index=True)
                    
                    # Remove rows with blank/null Customer Code or Customer Name before saving
                    if 'Customer code' in accounts_df.columns and 'Customer name' in accounts_df.columns:
                        cc_ok = accounts_df['Customer code'].fillna('').astype(str).str.strip() != ''
                        cn_ok = accounts_df['Customer name'].fillna('').astype(str).str.strip() != ''
                        accounts_df = accounts_df[cc_ok & cn_ok].copy()
                    
                    # Remove duplicates by Customer code and Account_Type (keep first occurrence)
                    dup_cols = ['Customer code']
                    if 'Account_Type' in accounts_df.columns:
                        dup_cols.append('Account_Type')
                    if dup_cols and not accounts_df.empty:
                        before_count = len(accounts_df)
                        accounts_df = accounts_df.drop_duplicates(subset=dup_cols, keep='first').reset_index(drop=True)
                        if len(accounts_df) < before_count:
                            st.info(f"Removed {before_count - len(accounts_df)} duplicate account(s) by Customer Code and Account_Type.")
                    
                    # Save the updated dataframe
                    if save_accounts(accounts_df):
                        st.success("Accounts updated successfully!")
                        # Reset add mode and highlight flag after saving
                        st.session_state.accounts_add_mode = False
                        st.session_state.highlight_new_account_row = False
                        st.rerun()
                    else:
                        st.error("Error saving accounts.")
            with col2:
                if st.button("Close", type="secondary", use_container_width=True):
                    # Remove rows with blank/null Customer Code or Customer Name and duplicates before closing
                    accounts_df = load_accounts()
                    if not accounts_df.empty and 'Customer code' in accounts_df.columns and 'Customer name' in accounts_df.columns:
                        cc_ok = accounts_df['Customer code'].fillna('').astype(str).str.strip() != ''
                        cn_ok = accounts_df['Customer name'].fillna('').astype(str).str.strip() != ''
                        accounts_df = accounts_df[cc_ok & cn_ok].copy()
                        dup_cols = ['Customer code'] + (['Account_Type'] if 'Account_Type' in accounts_df.columns else [])
                        accounts_df = accounts_df.drop_duplicates(subset=dup_cols, keep='first').reset_index(drop=True)
                        save_accounts(accounts_df)
                    st.session_state.show_accounts_dialog = False
                    # Reset add mode and highlight when closing dialog
                    st.session_state.accounts_add_mode = False
                    st.session_state.highlight_new_account_row = False
                    st.rerun()
            
        else:
            st.error("Required columns not found in accounts CSV file.")
            if st.button("Close", type="primary", use_container_width=True):
                st.session_state.show_accounts_dialog = False
                st.session_state.highlight_new_account_row = False
                st.rerun()

# Product Image Viewer Dialog Function
@st.dialog(title="🖼️ Product Image", width="large", dismissible=True)
def product_image_viewer_dialog(image_path, product_name, product_code):
    """Dialog function for viewing product images in large format"""
    st.header(f"{product_name}")
    st.caption(f"Product Code: {product_code}")
    st.markdown("---")
    
    if image_path and os.path.exists(image_path):
        # Display image in large format, centered with click-to-close functionality
        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            # Create a clickable image using HTML with JavaScript
            import base64
            try:
                with open(image_path, "rb") as img_file:
                    img_base64 = base64.b64encode(img_file.read()).decode()
                    img_ext = os.path.splitext(image_path)[1][1:].lower() or 'png'
                    
                    # Create clickable image container
                    st.markdown(f"""
                    <div style="position: relative; width: 100%; cursor: pointer;">
                        <img src="data:image/{img_ext};base64,{img_base64}" 
                             style="width: 100%; height: auto; display: block; cursor: pointer;" 
                             onclick="window.parent.postMessage({{type: 'streamlit:closeDialog'}}, '*');"
                             ondblclick="window.parent.postMessage({{type: 'streamlit:closeDialog'}}, '*');" />
                    </div>
                    """, unsafe_allow_html=True)
            except Exception:
                # Fallback to regular image display
                st.image(image_path, width=400)
            
            st.caption("💡 Click or double-click the image to close (or click outside the dialog)")
            
            # Add a visible close button as backup
            if st.button("Close", key=f"close_image_btn_{product_code}", use_container_width=True, type="primary"):
                st.session_state.show_image_viewer = False
                st.session_state.viewer_image_path = None
                st.session_state.viewer_product_name = None
                st.session_state.viewer_product_code = None
                st.rerun()
    else:
        st.warning("Image not found.")
    
    st.markdown("---")
    if st.button("Close", type="primary", use_container_width=True):
        st.session_state.show_image_viewer = False
        st.session_state.viewer_image_path = None
        st.session_state.viewer_product_name = None
        st.session_state.viewer_product_code = None
        st.rerun()

# Unlock Order Dialog Function
@st.dialog(title="🔓 Unlock Order for Edit", width="medium", dismissible=True)
def unlock_order_dialog(order_id, orders_df):
    """Dialog function for unlocking orders for edit with required reason"""
    st.header(f"Unlock Order {order_id} for Edit")
    st.warning("⚠️ Please provide a reason for unlocking this order. This reason will be visible in the order status.")
    
    order = orders_df[orders_df['OrderID'] == order_id]
    if not order.empty:
        order_row = order.iloc[0]
        st.markdown(f"**Client:** {order_row.get('ClientName', 'N/A')}")
        st.markdown(f"**Order Date:** {order_row.get('OrderDate', 'N/A')}")
        st.markdown(f"**Total Amount:** {float(order_row.get('TotalAmount', 0)):.2f}")
        st.markdown("---")
    
    with st.form("unlock_form"):
        unlock_reason = st.text_area(
            "Reason for Unlocking *",
            key="unlock_reason",
            placeholder="Please provide a detailed reason for unlocking this order for edit...",
            help="This reason will be added to the order status and will be visible to the sales representative."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submit_unlock = st.form_submit_button("🔓 Unlock for Edit", type="primary", use_container_width=True)
        with col2:
            cancel_unlock = st.form_submit_button("Cancel", use_container_width=True)
        
        if cancel_unlock:
            st.session_state.show_unlock_dialog = False
            st.session_state.unlock_order_id = None
            st.rerun()
        
        if submit_unlock:
            # Validation - reason is required
            if not unlock_reason or not unlock_reason.strip():
                st.error("⚠️ Please provide a reason for unlocking. This field is required.")
            else:
                # Update order status with reason
                order_idx = orders_df[orders_df['OrderID'] == order_id].index
                if len(order_idx) > 0:
                    # Format status as "Unlocked for Edit (reason: ...)"
                    status_with_reason = f"Unlocked for Edit (reason: {unlock_reason.strip()})"
                    orders_df.at[order_idx[0], 'Status'] = status_with_reason
                    orders_df.at[order_idx[0], 'ReviewedBy'] = st.session_state.username
                    orders_df.at[order_idx[0], 'ReviewedDate'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if save_orders(orders_df):
                        st.session_state.show_unlock_dialog = False
                        st.session_state.unlock_order_id = None
                        st.success(f"Order {order_id} has been unlocked for edit with reason.")
                        st.rerun()
                    else:
                        st.error("Error saving unlock status. Please try again.")

@st.dialog(title="🚫 Cancel Booking Request", width="medium", dismissible=True)
def cancel_booking_request_by_creator_dialog(request_id):
    """Dialog for creator (Sales Rep) to cancel their own booking request with required reason."""
    st.header("Cancel Booking Request")
    st.warning("Are you sure you want to cancel this booking request? The assigned TSR will no longer see it.")
    st.markdown(f"**Request ID:** {request_id}")
    st.markdown("---")
    br = db.get_booking_request_by_id(request_id)
    if br:
        st.markdown(f"**Client:** {br.get('client_name', 'N/A')}")
        st.markdown(f"**Assigned TSR:** {br.get('tsr_name', 'N/A')} ({br.get('tsr_code', 'N/A')})")
        st.markdown("---")
    with st.form("cancel_br_by_creator_form"):
        cancel_reason = st.text_area(
            "Reason for cancellation *",
            key="cancel_br_reason",
            placeholder="Please provide the reason for cancelling this booking request...",
            help="This reason will be shown to the assigned TSR and in cancellation history."
        )
        col1, col2 = st.columns(2)
        with col1:
            submit_cancel = st.form_submit_button("Confirm Cancel", type="primary", use_container_width=True)
        with col2:
            cancel_btn = st.form_submit_button("Back", use_container_width=True)
        if cancel_btn:
            st.session_state.show_cancel_br_by_creator_dialog = False
            st.session_state.cancel_br_request_id = None
            st.rerun()
        if submit_cancel:
            if not cancel_reason or not cancel_reason.strip():
                st.error("⚠️ Please provide a reason for cancellation. This field is required.")
            else:
                if db.update_booking_request_status(request_id, 'Cancelled by Creator', cancel_reason=cancel_reason.strip()):
                    if br:
                        tsr_code = br.get('tsr_code', '')
                        tsr_name = br.get('tsr_name', '') or 'TSR'
                        client_name = br.get('client_name', 'N/A')
                        created_by = br.get('created_by', '') or st.session_state.get('username', '')
                        try:
                            send_booking_request_cancelled_by_creator_notification(
                                request_id, tsr_code, tsr_name, client_name, created_by, cancel_reason.strip()
                            )
                        except Exception as e:
                            log_email_notification("ERROR", f"Error sending cancelled-by-creator email for {request_id}", error=e)
                    st.session_state.show_cancel_br_by_creator_dialog = False
                    st.session_state.cancel_br_request_id = None
                    st.success(f"Booking request {request_id} has been cancelled.")
                    st.rerun()
                else:
                    st.error("Failed to update booking request. Please try again.")

def build_order_print_html(order_row, cart_items):
    """Build a simple one-page HTML print view for an order."""
    # Format cart rows
    item_rows = ""
    for idx, item in enumerate(cart_items, start=1):
        qty = safe_float_convert(item.get('qty', 0))
        price = safe_float_convert(item.get('price', 0))
        subtotal = qty * price
        notes_remarks = str(item.get('notes_remarks', '') or '')
        item_rows += f"""
            <tr>
                <td style='padding:4px; border:1px solid #ccc; text-align:center;'>{idx}</td>
                <td style='padding:4px; border:1px solid #ccc;'>{item.get('product_code', '')}</td>
                <td style='padding:4px; border:1px solid #ccc;'>{item.get('product_name', '')}</td>
                <td style='padding:4px; border:1px solid #ccc; text-align:right;'>{qty:.2f}</td>
                <td style='padding:4px; border:1px solid #ccc; text-align:right;'>{price:.2f}</td>
                <td style='padding:4px; border:1px solid #ccc; text-align:right;'>{subtotal:.2f}</td>
                <td style='padding:4px; border:1px solid #ccc;'>{notes_remarks}</td>
            </tr>
        """
    
    subtotal = float(order_row.get('Subtotal', 0))
    discount_percent = float(order_row.get('DiscountPercent', 0))
    discount_amount = float(order_row.get('DiscountAmount', 0))
    total_amount = float(order_row.get('TotalAmount', 0))
    
    reviewed_by = order_row.get('ReviewedBy', '')
    reviewed_date = order_row.get('ReviewedDate', '')
    reviewed_block = f"<div><strong>Reviewed By:</strong> {reviewed_by or 'N/A'}</div>"
    if reviewed_by and reviewed_date:
        reviewed_block += f"<div><strong>Reviewed Date:</strong> {reviewed_date}</div>"

    # Booking Request linkage (if order came from a Booking Request)
    br_created_by = order_row.get('BR_CreatedBy', '')
    booking_block = f"<div><strong>Booking Request Created by:</strong> {br_created_by}</div>" if br_created_by else ""
    
    notes = str(order_row.get('Notes', '') or '').strip()
    remarks = order_row.get('Remarks', '')
    additional = ""
    if notes and notes.upper() != 'N/A':
        additional += f"<div><strong>Special Instructions:</strong> {notes}</div>"
    if remarks:
        additional += f"<div><strong>Remarks:</strong> {remarks}</div>"
    if not additional:
        additional = "<div>No additional notes.</div>"
    
    html = f"""
    <html>
    <head>
    </head>
    <body onload="window.print()">
        <div class="header">
            <div>
                <div class="title">Sales Order</div>
                <div>Order ID: {order_row.get('OrderID', '')}</div>
                <div>Date: {order_row.get('OrderDate', '')}</div>
                <div>Status: {format_order_status_display(order_row)}</div>
            </div>
            <div style="text-align:right;">
                <div><strong>Name:</strong> {order_row.get('RepName', '')}</div>
                <div><strong>Code:</strong> {order_row.get('RepCode', '')}</div>
                <div><strong>Dept/Area:</strong> {order_row.get('RepDept', '')} / {order_row.get('RepArea', '')}</div>
                {booking_block}
                {reviewed_block}
            </div>
        </div>
        
        <div class="section">
            <h4>Client Information</h4>
            <table>
                <tr>
                    <td><strong>Name:</strong> {order_row.get('ClientName', '')}</td>
                    <td><strong>Mobile:</strong> {order_row.get('ClientMobile', '')}</td>
                </tr>
                <tr>
                    <td colspan="2"><strong>Client Category:</strong> {order_row.get('ClientDescription', '')}</td>
                </tr>
                <tr>
                    <td><strong>Billing Address:</strong><br>{order_row.get('BillingAddress', '')}</td>
                    <td><strong>Shipping Address:</strong><br>{order_row.get('ShippingAddress', '')}</td>
                </tr>
                <tr>
                    <td><strong>Contact Person 1:</strong> {order_row.get('ContactPerson1', '')}<br><strong>Mobile:</strong> {order_row.get('ContactPerson1Mobile', '')}</td>
                    <td><strong>Contact Person 2:</strong> {order_row.get('ContactPerson2', '')}<br><strong>Mobile:</strong> {order_row.get('ContactPerson2Mobile', '')}</td>
                </tr>
            </table>
        </div>
        
        <div class="section">
            <h4>Order Terms</h4>
            <table>
                <tr>
                    <td><strong>Payment Terms:</strong> {order_row.get('PaymentTerms', '')}</td>
                    <td><strong>Delivery Instructions:</strong> {order_row.get('DeliveryTerms', '')}</td>
                    <td><strong>Delivery Date:</strong> {order_row.get('DeliveryDate', '')}</td>
                </tr>
            </table>
        </div>
        
        <div class="section">
            <h4>Items</h4>
            <table>
                <thead>
                    <tr>
                        <th style='padding:4px; border:1px solid #ccc; width:40px;'>#</th>
                        <th style='padding:4px; border:1px solid #ccc; width:120px;'>Code</th>
                        <th style='padding:4px; border:1px solid #ccc;'>Product</th>
                        <th style='padding:4px; border:1px solid #ccc; width:80px;'>Qty</th>
                        <th style='padding:4px; border:1px solid #ccc; width:90px;'>Price</th>
                        <th style='padding:4px; border:1px solid #ccc; width:100px;'>Subtotal</th>
                        <th style='padding:4px; border:1px solid #ccc; width:100px;'>Notes/Remarks</th>
                    </tr>
                </thead>
                <tbody>
                    {item_rows if item_rows else "<tr><td colspan='7' style='text-align:center; padding:6px; border:1px solid #ccc;'>No items found</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <div class="section" style="display:flex; justify-content:flex-end;">
            <table class="totals-table" style="width:320px;">
                <tr>
                    <td><strong>Subtotal</strong></td>
                    <td style="text-align:right;">{subtotal:.2f}</td>
                </tr>
                <tr>
                    <td><strong>Discount ({discount_percent:.1f}%)</strong></td>
                    <td style="text-align:right;">-{discount_amount:.2f}</td>
                </tr>
                <tr>
                    <td><strong>Total Amount</strong></td>
                    <td style="text-align:right; font-size:14px;"><strong>{total_amount:.2f}</strong></td>
                </tr>
            </table>
        </div>
        
        <div class="section">
            <h4>Additional Information</h4>
            {additional}
        </div>
    </body>
    </html>
    """
    return html

def render_print_view(order_id):
    """Render the print preview HTML for the given order ID."""
    orders_df = load_orders()
    if orders_df.empty:
        st.error("No orders found for printing.")
        return
    
    order = orders_df[orders_df['OrderID'] == order_id]
    if order.empty:
        st.error(f"Order {order_id} not found.")
        return
    
    order_row = order.iloc[0]
    cart_items_str = order_row.get('CartItems', '[]')
    disapproved_items_str = order_row.get('DisapprovedItems', '[]')
    cart_items = safe_parse_cart_items(cart_items_str)
    # Parse disapproved items
    try:
        disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
    except (ValueError, SyntaxError):
        disapproved_items = []
    
    # Filter out disapproved items for printing
    disapproved_indices = [dis_item.get('item_index', -1) for dis_item in disapproved_items if 'item_index' in dis_item]
    remaining_items = [item for idx, item in enumerate(cart_items) if idx not in disapproved_indices]
    
    st.subheader(f"🖨️ Print Preview - {order_id}")
    
    html = build_order_print_html(order_row, remaining_items)
    b64_html = base64.b64encode(html.encode('utf-8')).decode('ascii')
    
    col_ret, col_open, _ = st.columns([1, 1, 3])
    with col_ret:
        if st.button("← Return to Finance", type="primary", use_container_width=True):
            st.session_state.show_print_view = False
            st.session_state.print_view_order_id = None
            st.rerun()
    with col_open:
        st.markdown(
            f'<a href="data:text/html;base64,{b64_html}" target="_blank" rel="noopener" '
            'style="display:inline-block; padding:8px 16px; background:#1f77b4; color:white; text-decoration:none; border-radius:4px; width:100%; text-align:center; box-sizing:border-box;">'
            'Open in new tab</a>',
            unsafe_allow_html=True
        )
    
    st.info("Use your browser's print dialog to save as PDF.")
    st.components.v1.html(html, height=1100, scrolling=True)

def clear_all_dialog_states():
    """Centralized function to clear all dialog-related session states"""
    st.session_state.show_submit_order_dialog = False
    st.session_state.show_order_details_dialog = False
    st.session_state.show_disapprove_dialog = False
    st.session_state.show_disapprove_item_dialog = False
    st.session_state.show_unlock_dialog = False
    st.session_state.show_cancel_order_dialog = False
    st.session_state.cancel_order_id = None
    st.session_state.show_cancel_br_by_creator_dialog = False
    st.session_state.cancel_br_request_id = None
    st.session_state.dialog_button_clicked = False
    if 'dialog_pending_notes_edit' in st.session_state:
        del st.session_state.dialog_pending_notes_edit
    if 'dialog_awaiting_second_save' in st.session_state:
        del st.session_state.dialog_awaiting_second_save
    if 'dialog_place_order_saved' in st.session_state:
        del st.session_state.dialog_place_order_saved

# Sales Rep Interface
def sales_rep_interface():
    """Sales Rep main interface"""
    # CRITICAL: Clear dialog state FIRST if we just added to cart (prevents dialog flash)
    # This must happen before ANY dialog rendering logic or widget processing
    # Keep flag set during this render cycle to prevent dialog from showing
    if st.session_state.get('just_added_to_cart', False):
        clear_all_dialog_states()
        # Don't reset flag here - let it persist to prevent dialog during success message
        # Flag will be reset after dialog check passes
    
    # Show order details dialog if triggered (from Order History)
    dialog_triggered = st.session_state.get('show_order_details_dialog', False)
    selected_order_id = st.session_state.get('selected_order_id')
    button_clicked = st.session_state.get('dialog_button_clicked', False)
    
    if dialog_triggered and selected_order_id and button_clicked:
        orders_df = load_orders()
        order_details_dialog(st.session_state.selected_order_id, orders_df)
        # Reset button_clicked flag after dialog runs
        st.session_state.dialog_button_clicked = False
    
    # Show cancel booking request by creator dialog if triggered (from My Booking Requests)
    if st.session_state.get('show_cancel_br_by_creator_dialog', False) and st.session_state.get('cancel_br_request_id'):
        cancel_booking_request_by_creator_dialog(st.session_state.cancel_br_request_id)
    
    # Add CSS to center emoji in buttons and reduce container padding

    
    # Add CSS to reduce container padding and spacing for more compact cards

    
    st.title("📦 Sales Order Management")
    # Welcome banner - show logged-in user in main content
    _main_uname = st.session_state.get('username', '') or ''
    if _main_uname:
        st.caption(f"👋 Logged in as: **{_main_uname}**")
    
    # Sidebar - Logo and Shopping Cart
    with st.sidebar:
        # Display logo at the top of sidebar
        display_logo(width=200)
        # Welcome message - show logged-in user
        _uname = st.session_state.get('username', '') or ''
        if _uname:
            st.success(f"👋 Welcome, **{_uname}**")
        st.markdown("---")
        st.header("🛒 Shopping Cart")
        if st.session_state.cart:
            for idx, item in enumerate(st.session_state.cart):
                st.markdown(f"**{item.product_name}**")
                st.markdown(f"Qty: {item.qty} | Price: {item.price:.2f} each")
                if st.button("Remove", key=f"remove_{idx}"):
                    st.session_state.cart.pop(idx)
                    st.rerun()
            st.markdown("---")
            total = sum(item.qty * item.price for item in st.session_state.cart)
            st.markdown(f"**Total: {total:.2f}**")
            st.markdown("---")
            if st.button("📝 Place Order", type="primary", use_container_width=True):
                # Reset image viewer state when submitting order
                st.session_state.show_image_viewer = False
                st.session_state.viewer_image_path = None
                st.session_state.viewer_product_name = None
                st.session_state.viewer_product_code = None
                # Clear the "just added to cart" flag to ensure dialog shows
                st.session_state.just_added_to_cart = False
                # Set Submit Order dialog state
                st.session_state.show_submit_order_dialog = True
                st.rerun()
            if st.button("Clear Cart", type="secondary"):
                st.session_state.cart = []
                st.rerun()
        else:
            st.info("Cart is empty")
        
        st.markdown("---")
        if st.button("🔓 Logout"):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.username = None
            st.session_state.admin_level = None
            st.session_state.is_view_only = False
            st.session_state.cart = []
            st.session_state.show_submit_order_dialog = False
            st.session_state.show_order_details_dialog = False
            st.session_state.selected_order_id = None
            # Reset all dialog states on logout
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_manage_products_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
            st.session_state.show_notification_management_dialog = False
            # Clear booking request related session state
            if 'tab_request_booking' in st.session_state:
                del st.session_state.tab_request_booking
            if 'dialog_request_booking' in st.session_state:
                del st.session_state.dialog_request_booking
            if 'selected_booking_request_id' in st.session_state:
                del st.session_state.selected_booking_request_id
            if 'booking_request_loaded_id' in st.session_state:
                del st.session_state.booking_request_loaded_id
            if 'booking_client_name' in st.session_state:
                del st.session_state.booking_client_name
            st.rerun()
    
    # Reset dialog state if cart is empty (prevents dialog from showing on empty cart)
    if not st.session_state.cart and st.session_state.get('show_submit_order_dialog', False):
        st.session_state.show_submit_order_dialog = False
    
    # Reset image viewer dialog if Submit Order dialog is being shown
    if st.session_state.get('show_submit_order_dialog', False):
        st.session_state.show_image_viewer = False
        st.session_state.viewer_image_path = None
        st.session_state.viewer_product_name = None
        st.session_state.viewer_product_code = None
    
    # Show Submit Order dialog ONLY if all conditions are met
    # CRITICAL: Multiple checks to prevent dialog flash
    just_added = st.session_state.get('just_added_to_cart', False)
    dialog_state = st.session_state.get('show_submit_order_dialog', False)
    has_cart = bool(st.session_state.cart)
    
    # STRICT condition: Only show dialog if ALL are true:
    # 1. Dialog state is explicitly True
    # 2. We did NOT just add to cart (flag check)
    # 3. Cart has items
    # 4. Flag is not set (double-check)
    if dialog_state and has_cart and not just_added:
        # Final check before rendering - ensure flag is still not set
        if not st.session_state.get('just_added_to_cart', False):
            try:
                submit_order_dialog()
            except Exception:
                clear_all_dialog_states()
    
    # Success message removed to prevent dialog flash and reduce reruns
    
    # Main Content - Tabs (TRADE users get Booking Request as default first tab)
    account_type = st.session_state.get('account_type', 'Dispensing')
    completing_br = st.session_state.get('selected_booking_request_id', '')
    
    # When TSR clicks "Complete Order", load booking request into cart and client, then show Place Order first
    if completing_br and account_type == 'TRADE':
        br = db.get_booking_request_by_id(completing_br)
        if br and st.session_state.get('booking_request_loaded_id') != completing_br:
            try:
                # Store booking request creator for linkage to Sales Order
                st.session_state.br_created_by = br.get('created_by', '')
                cart_data = json.loads(br.get('cart_items', '[]'))
                st.session_state.cart = []
                for item in cart_data:
                    if isinstance(item, dict):
                        d = {k: v for k, v in item.items() if k in ('product_code', 'product_name', 'qty', 'price', 'notes_remarks', 'row_data')}
                        d.setdefault('notes_remarks', '')
                        d.setdefault('row_data', {})
                        st.session_state.cart.append(CartItem(**d))
                    else:
                        st.session_state.cart.append(CartItem(product_code='', product_name='', qty=1, price=0, notes_remarks=''))
                client_name_br = br.get('client_name', '')
                st.session_state.booking_client_name = client_name_br
                # Auto-fill Notes/Remarks from SO_history for this customer (most recent per SKU)
                apply_so_history_notes_to_cart(client_name_br)
                # Populate client fields from accounts
                active_accounts = get_active_accounts()
                if not active_accounts.empty and client_name_br:
                    client_row = active_accounts[active_accounts['Customer name'].astype(str).str.strip() == client_name_br]
                    if not client_row.empty:
                        cd = client_row.iloc[0]
                        st.session_state.client_description = str(cd.get('Customer code', '')).strip() or 'N/A'
                        st.session_state.client_mobile = str(cd.get('Contact number1', '')).strip() or 'N/A'
                        ba = str(cd.get('Business address', '')).strip() or 'N/A'
                        st.session_state.billing_address = ba
                        st.session_state.shipping_address = ba
                        st.session_state.contact_person_1 = str(cd.get('Contact person1', '')).strip() or 'N/A'
                        st.session_state.payment_terms = str(cd.get('Credit term', '')).strip() or 'N/A'
                    else:
                        # No matching account - set all to N/A so TSR can submit
                        st.session_state.client_description = 'N/A'
                        st.session_state.client_mobile = 'N/A'
                        st.session_state.billing_address = 'N/A'
                        st.session_state.shipping_address = 'N/A'
                        st.session_state.contact_person_1 = 'N/A'
                        st.session_state.payment_terms = 'N/A'
                else:
                    # No accounts or no client name - set all to N/A
                    st.session_state.client_description = st.session_state.get('client_description', '') or 'N/A'
                    st.session_state.client_mobile = st.session_state.get('client_mobile', '') or 'N/A'
                    st.session_state.billing_address = st.session_state.get('billing_address', '') or 'N/A'
                    st.session_state.shipping_address = st.session_state.get('shipping_address', '') or 'N/A'
                    st.session_state.contact_person_1 = st.session_state.get('contact_person_1', '') or 'N/A'
                    st.session_state.payment_terms = st.session_state.get('payment_terms', '') or 'N/A'
                st.session_state.booking_request_loaded_id = completing_br
                st.session_state.br_place_order_saved = False  # Reset when BR loads
                st.session_state.booking_request_special_instructions = br.get('special_instructions', '')
                st.session_state.booking_request_remarks = br.get('remarks', '')
                st.session_state.booking_request_shipping_date = br.get('shipping_date', '')
                
                # CRITICAL: Initialize Notes, Remarks, Delivery Instructions, and Delivery Date from booking request
                # Empty fields get "N/A" so TSR can submit (only Remarks is editable)
                special_instr = (br.get('special_instructions') or '').strip()
                st.session_state.notes = special_instr or 'N/A'
                st.session_state.remarks = br.get('remarks', '') or ''
                st.session_state.delivery_terms = special_instr or 'N/A'
                # Use shipping_date as delivery_date for order form
                ship_date = br.get('shipping_date', '')
                if ship_date:
                    try:
                        st.session_state.delivery_date = datetime.strptime(str(ship_date)[:10], '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        pass
            except Exception as e:
                st.error(f"Failed to load booking request: {e}")
    
    # Related Submitted Orders: match rep_code to TSR_tag OR PMR_tag OR DSMBU7_tag OR DSMPSI_tag (ignore account_type)
    rep_code = st.session_state.get('rep_code', '')
    _tag_type = 'ALL'  # Match any of the four tags
    show_related_orders = bool(rep_code)
    
    # Banner when Notes/Remarks validation failed - direct user to Cart Summary
    if st.session_state.get('submit_order_notes_validation_failed', False):
        st.error("⚠️ **Cannot submit:** Notes/Remarks is required for every SKU. Go to the **Place Order** tab → Cart Summary → fill in the table and click **💾 Save Changes (Notes /Remarks)** before submitting.")
    
    # Auto-Cancel count for Booking Request tab badge (TRADE users)
    auto_cancel_count = db.get_auto_cancel_count_for_tsr(st.session_state.get('rep_code', '')) if account_type == 'TRADE' else 0
    br_tab_label = f"📋 Booking Request ({auto_cancel_count} Auto-Cancel)" if auto_cancel_count > 0 else "📋 Booking Request"
    
    if account_type == 'TRADE':
        if completing_br:
            if show_related_orders:
                tab2, tab_br, tab1, tab3, tab4 = st.tabs(["📝 Complete Booking", br_tab_label, "🛍️ Browse Products", "📋 Request/Order History", "📋 Related Submitted Orders"])
            else:
                tab2, tab_br, tab1, tab3 = st.tabs(["📝 Complete Booking", br_tab_label, "🛍️ Browse Products", "📋 Request/Order History"])
                tab4 = None
        else:
            if show_related_orders:
                tab_br, tab1, tab2, tab3, tab4 = st.tabs([br_tab_label, "🛍️ Browse Products", "📝 Place Order", "📋 Request/Order History", "📋 Related Submitted Orders"])
            else:
                tab_br, tab1, tab2, tab3 = st.tabs([br_tab_label, "🛍️ Browse Products", "📝 Place Order", "📋 Request/Order History"])
                tab4 = None
    else:
        tab_br = None
        if show_related_orders:
            tab1, tab2, tab3, tab4 = st.tabs(["🛍️ Browse Products", "📝 Place Order", "📋 Request/Order History", "📋 Related Submitted Orders"])
        else:
            tab1, tab2, tab3 = st.tabs(["🛍️ Browse Products", "📝 Place Order", "📋 Request/Order History"])
            tab4 = None
    
    # Booking Request tab (TRADE / TSR only) - default view for TSR
    if tab_br is not None:
        with tab_br:
            if completing_br:
                if st.button("← Back to Booking Requests", key="back_br_list"):
                    st.session_state.selected_booking_request_id = ''
                    st.session_state.booking_request_loaded_id = ''
                    if 'booking_client_name' in st.session_state:
                        del st.session_state['booking_client_name']
                    if 'tab_pending_notes_edit' in st.session_state:
                        del st.session_state.tab_pending_notes_edit
                    if 'tab_awaiting_second_save' in st.session_state:
                        del st.session_state.tab_awaiting_second_save
                    st.rerun()
            else:
                rep_code = st.session_state.get('rep_code', '')
                if rep_code:
                    br_pending = db.get_booking_requests_by_tsr_code(rep_code)
                    br_all = db.get_booking_requests_by_tsr_code_all(rep_code)
                    br_history = br_all[br_all['status'] == 'Completed'] if not br_all.empty else pd.DataFrame()
                    
                    if auto_cancel_count > 0:
                        st.info(f"**{auto_cancel_count} Auto-Cancel** request{'s' if auto_cancel_count != 1 else ''} — view in Request/Order History tab.")
                    if br_pending.empty:
                        st.info("No pending booking requests.")
                    else:
                        st.subheader("Pending Booking Requests")
                        for _, row in br_pending.iterrows():
                            rid = row.get('request_id', '')
                            client = row.get('client_name', 'N/A')
                            created = row.get('created_date', '')[:19] if row.get('created_date') else ''
                            created_by = row.get('created_by', '')
                            with st.container(border=True):
                                col1, col2, col3 = st.columns([3, 2, 1])
                                with col1:
                                    st.markdown(f"**{client}**")
                                    st.caption(f"Request ID: {rid} | Created: {created} by {created_by}")
                                with col2:
                                    st.caption(f"Shipping: {row.get('shipping_date', '')}")
                                with col3:
                                    if st.button("Complete Order", key=f"br_complete_{rid}"):
                                        st.session_state.selected_booking_request_id = rid
                                        st.rerun()
                    
                    # Booking Request History (Completed only - Auto-Cancel moved to Request/Order History)
                    if not br_history.empty:
                        st.markdown("---")
                        st.subheader("Booking Request History")
                        st.caption("Completed = TSR finished the order. Auto-Cancel requests are shown in Request/Order History.")
                        for _, row in br_history.iterrows():
                            rid = row.get('request_id', '')
                            status = row.get('status', '')
                            client = row.get('client_name', 'N/A')
                            created = row.get('created_date', '')[:19] if row.get('created_date') else ''
                            created_by = row.get('created_by', '')
                            order_id = row.get('order_id', '')
                            with st.container(border=True):
                                col1, col2, col3 = st.columns([3, 2, 1])
                                with col1:
                                    st.markdown(f"**{client}**")
                                    st.caption(f"Request ID: {rid} | Created: {created} by {created_by}")
                                with col2:
                                    st.markdown(f"**Status:** {status}")
                                    if order_id:
                                        st.caption(f"Order: {order_id}")
                                with col3:
                                    if status == 'Auto-Cancel':
                                        st.warning("Auto-Cancel")
                                    elif status == 'Completed':
                                        st.success("Completed")
                else:
                    st.warning("Rep code not found. Cannot load booking requests.")
    
    with tab1:
        st.header("Product Catalog")
        products_df = load_products()
        
        if products_df.empty:
            st.warning("No products available. Please sync products from SQL Server (Admin tab) or create products.csv file.")
        else:
            # Search and filter
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("Search products", placeholder="Enter product name or code...", autocomplete="off")
            with col2:
                st.write("")  # Spacing
            
            # Filter products
            if search_term:
                mask = products_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                display_df = products_df[mask]
            else:
                display_df = products_df
            
            # Display products in a grid
            if not display_df.empty:
                # Determine columns to display
                if 'ProductCode' in display_df.columns or 'Product_Code' in display_df.columns:
                    code_col = 'ProductCode' if 'ProductCode' in display_df.columns else 'Product_Code'
                else:
                    code_col = display_df.columns[0]
                
                if 'ProductName' in display_df.columns or 'Product_Name' in display_df.columns:
                    name_col = 'ProductName' if 'ProductName' in display_df.columns else 'Product_Name'
                else:
                    name_col = display_df.columns[1] if len(display_df.columns) > 1 else display_df.columns[0]
                
                price_col = None
                for col in ['Price', 'UnitPrice', 'SellingPrice', 'Cost']:
                    if col in display_df.columns:
                        price_col = col
                        break
                if price_col is None and len(display_df.columns) > 2:
                    price_col = display_df.columns[2]
                
                # Display products in a grid with images
                for idx, row in display_df.iterrows():
                    # Use st.container() with border=True - widgets render properly inside containers
                    with st.container(border=True):
                        product_code = str(row.get(code_col, f'PROD{idx+1:03d}'))
                        product_name = row.get(name_col, 'N/A')
                        
                        # Get image path (will generate default if missing)
                        image_path = get_product_image_path(product_code, product_name)
                        
                        # Create columns for product display with image
                        # Always show image column since we have default images
                        col_img, col_info, col_price, col_qty, col_btn = st.columns([0.8, 4, 2, 1, 1.5])
                        
                        with col_img:
                            if os.path.exists(image_path):
                                st.image(image_path, use_container_width=True)
                            else:
                                st.write("📦")  # Simple placeholder
                        
                        with col_info:
                            st.markdown(f"**{product_name}**")
                            st.caption(f"Code: {product_code}")
                        
                        with col_price:
                            if price_col:
                                price_value = safe_float_convert(row.get(price_col, 0))
                                st.markdown(f"**Price:** {price_value:.2f}")
                            else:
                                st.markdown("**Price:** N/A")
                        
                        with col_qty:
                            qty = st.number_input("Qty", min_value=1, value=1, key=f"qty_{idx}")
                        
                        with col_btn:
                            # Add margin-top to align button with the number input field (label + input = ~23px offset)
                            st.markdown('<div style="margin-top: 23px;">', unsafe_allow_html=True)
                            add_to_cart_clicked = st.button("Add to Cart", key=f"add_{idx}", type="primary", use_container_width=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                            
                            if add_to_cart_clicked:
                                # OPTIMIZED: Minimal operations before rerun for faster response
                                # Step 1: Clear dialog state IMMEDIATELY (prevents flash)
                                clear_all_dialog_states()
                                st.session_state.just_added_to_cart = True
                                
                                # Step 2: Update cart efficiently (minimal operations)
                                price = safe_float_convert(row.get(price_col, 0)) if price_col else 0.0
                                cart = st.session_state.cart
                                found = False
                                for item in cart:
                                    if item.product_code == product_code:
                                        item.qty += qty
                                        found = True
                                        break
                                
                                if not found:
                                    cart.append(CartItem(
                                        product_code=product_code,
                                        product_name=product_name,
                                        qty=qty,
                                        price=price,
                                        notes_remarks='',
                                        row_data=row.to_dict()
                                    ))
                                
                                # Step 3: Reset image viewer (minimal state updates)
                                st.session_state.show_image_viewer = False
                                
                                # Step 4: Set toast notification message
                                st.session_state.added_product_name = product_name
                                
                                # Step 5: Single rerun - no success message, no extra operations
                                st.rerun()
            else:
                st.info("No products found matching your search.")
        
        # Show product image viewer dialog AFTER processing all buttons
        # This ensures "Add to Cart" resets happen before dialog check
        if st.session_state.get('show_image_viewer', False) and st.session_state.get('viewer_image_path'):
            product_image_viewer_dialog(
                st.session_state.viewer_image_path,
                st.session_state.viewer_product_name,
                st.session_state.viewer_product_code
            )
    
    with tab2:
        completing_br_id = st.session_state.get('selected_booking_request_id', '')
        if completing_br_id:
            st.info(f"Completing booking request **{completing_br_id}** — complete the form below and submit.")
            if st.button("← Back to Booking Requests", key="back_from_form"):
                st.session_state.selected_booking_request_id = ''
                st.session_state.booking_request_loaded_id = ''
                if 'br_place_order_saved' in st.session_state:
                    del st.session_state['br_place_order_saved']
                if 'booking_client_name' in st.session_state:
                    del st.session_state['booking_client_name']
                if 'tab_pending_notes_edit' in st.session_state:
                    del st.session_state.tab_pending_notes_edit
                if 'tab_awaiting_second_save' in st.session_state:
                    del st.session_state.tab_awaiting_second_save
                st.rerun()
            st.markdown("---")
        st.header("Submit New Order" if not completing_br_id else "Complete Booking Request")
        
        # Show success message if order was just submitted
        if st.session_state.get('order_submission_success', False) and st.session_state.get('last_submitted_order_id'):
            st.success(f"✅ Order {st.session_state.last_submitted_order_id} has been successfully submitted! Your cart has been cleared. Check the Request/Order History tab to view your order.")
            st.session_state.order_submission_success = False  # Reset flag after showing message
        
        if not st.session_state.cart:
            st.info("🛒 Your cart is empty. Please add products from the Browse Products tab to create an order.")
        else:
            is_completing_br = bool(completing_br_id)
            is_sales_rep = st.session_state.get('user_role', '') == 'Sales Rep'
            # Gray container if not saved, green if saved - for completing BR (TSR) and for Sales Rep
            show_form_coloring = is_completing_br or is_sales_rep
            if show_form_coloring:
                if is_completing_br:
                    form_saved = st.session_state.get('br_place_order_saved', False)
                else:
                    form_saved = st.session_state.get('tab_place_order_saved', False)
                form_bg = "#d4edda" if form_saved else "#e8e8e8"
                form_border = "#28a745" if form_saved else "#ccc"
            st.markdown("---")
            st.subheader("Order Details")
            
            # Cart summary - read-only when completing booking request (TSR Complete Order flow)
            st.markdown("### Cart Summary")
            if is_completing_br:
                st.caption("📋 Cart is pre-filled from the booking request and cannot be edited.")
            else:
                # Validation error: show when submission blocked due to empty Notes/Remarks
                if st.session_state.get('submit_order_notes_validation_failed', False):
                    items_missing = get_cart_items_with_empty_notes()
                    names = ", ".join(n for _, n in items_missing[:5])
                    if len(items_missing) > 5:
                        names += f", and {len(items_missing)-5} more"
                    st.error(f"⚠️ Cannot submit: Notes/Remarks is required for every SKU. Missing for: **{names}**. Fill in the table below and click **💾 Save Changes (Notes /Remarks)** before submitting.")
                    st.session_state.submit_order_notes_validation_failed = False
                if st.session_state.get('tab_notes_auto_filled', False):
                    st.success("Notes/Remarks auto-filled from SO history for selected customer. Review and save if needed.")
                    st.session_state.tab_notes_auto_filled = False
                st.info("✏️ Fill in **Notes/Remarks** for each SKU in the table below. Click **💾 Save Changes (Notes /Remarks)** twice to save (first tap captures edits, second tap saves).")
            # Ensure all cart items have notes_remarks field
            for item in st.session_state.cart:
                if not item.notes_remarks:
                    item.notes_remarks = ''
            
            # Convert CartItems to dicts for DataFrame - use pending edit from first tap if awaiting second tap
            if st.session_state.get('tab_awaiting_second_save', False) and 'tab_pending_notes_edit' in st.session_state:
                display_df = st.session_state.tab_pending_notes_edit.copy()
            else:
                cart_data = [item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart]
                cart_df = pd.DataFrame(cart_data)
                display_df = cart_df[['product_name', 'qty', 'price', 'notes_remarks']].copy()
                display_df['Total'] = display_df['qty'] * display_df['price']
                display_df = display_df[['product_name', 'qty', 'price', 'Total', 'notes_remarks']]
                display_df.columns = ['product_name', 'qty', 'price', 'Total', 'Notes/Remarks']
            
            if is_completing_br:
                # Read-only display when TSR completing booking request - cart cannot be edited
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                # Wrap data_editor in a form to prevent reruns on every cell edit
                with st.form("tab_cart_update_form"):
                    edited_df = st.data_editor(
                        display_df,
                        column_config={
                            "product_name": st.column_config.TextColumn("Product Name", disabled=True),
                            "qty": st.column_config.NumberColumn("Qty", disabled=True, format="%d"),
                            "price": st.column_config.NumberColumn("Price", disabled=True, format="%.2f"),
                            "Total": st.column_config.NumberColumn("Total", disabled=True, format="%.2f"),
                            "Notes/Remarks": st.column_config.TextColumn("Notes/Remarks", width="large")
                        },
                        use_container_width=True,
                        key="tab_cart_editor"
                    )
                    update_cart = st.form_submit_button("💾 Save Changes (Notes /Remarks)", type="primary", use_container_width=True)
                
                # Two-tap save: first tap captures edits, second tap saves to cart
                if update_cart and not edited_df.empty:
                    awaiting = st.session_state.get('tab_awaiting_second_save', False)
                    if not awaiting:
                        # First tap: store edited_df, set flag, rerun (gives time for cell to commit)
                        st.session_state.tab_pending_notes_edit = edited_df.copy()
                        st.session_state.tab_awaiting_second_save = True
                        if 'dialog_cart_editor' in st.session_state:
                            del st.session_state.dialog_cart_editor
                        st.rerun()
                    else:
                        # Second tap: save to cart and show success
                        current_client = st.session_state.get('client_name_select', '')
                        current_request_booking = st.session_state.get('tab_request_booking', False)
                        current_TSR_tag = st.session_state.get('account_TSR_tag', '')
                        current_PMR_tag = st.session_state.get('account_PMR_tag', '')
                        current_DSMBU7_tag = st.session_state.get('account_DSMBU7_tag', '')
                        current_DSMPSI_tag = st.session_state.get('account_DSMPSI_tag', '')
                        if current_client and isinstance(current_client, str):
                            current_client = current_client.strip()
                        else:
                            current_client = ''
                        for idx, row in edited_df.iterrows():
                            if idx < len(st.session_state.cart):
                                val = row.get('Notes/Remarks', '')
                                if val is None or (isinstance(val, str) and not str(val).strip()):
                                    val = '-'
                                st.session_state.cart[idx].notes_remarks = str(val).strip()
                        if 'tab_pending_notes_edit' in st.session_state:
                            del st.session_state.tab_pending_notes_edit
                        st.session_state.tab_awaiting_second_save = False
                        if 'dialog_cart_editor' in st.session_state:
                            del st.session_state.dialog_cart_editor
                        if current_client and current_client != '':
                            st.session_state.client_name_select = current_client
                        if current_request_booking:
                            st.session_state.tab_request_booking = True
                        if current_TSR_tag:
                            st.session_state.account_TSR_tag = current_TSR_tag
                        if current_PMR_tag:
                            st.session_state.account_PMR_tag = current_PMR_tag
                        if current_DSMBU7_tag:
                            st.session_state.account_DSMBU7_tag = current_DSMBU7_tag
                        if current_DSMPSI_tag:
                            st.session_state.account_DSMPSI_tag = current_DSMPSI_tag
                        st.session_state.tab_place_order_saved = True  # Gray -> green + persistent success message
                        st.rerun()
                
                if st.session_state.get('tab_place_order_saved', False):
                    st.success("Notes/Remarks saved successfully!")
            
            st.markdown("---")
            # Request Booking checkbox - Sales Rep ONLY (TSR never sees this; TSR completes requests, does not create them)
            # When completing booking request: request_booking=False so TSR sees order form, not Booking Request form
            if completing_br_id:
                request_booking = False
            elif st.session_state.get('authenticated', False) and st.session_state.get('user_role') == 'Sales Rep':
                if 'tab_request_booking' not in st.session_state:
                    st.session_state.tab_request_booking = True
                request_booking = st.checkbox(
                    "Request Booking (TRADE - Med Rep requests TSR to complete order)",
                    key="tab_request_booking",
                    help="Check to create a booking request for a TSR to complete. Uncheck to submit direct order for Contract accounts."
                )
            else:
                request_booking = False
            
            # Get active accounts for selectbox (OUTSIDE form)
            active_accounts = get_active_accounts()
            
            # For Sales Rep (not completing booking): filter by Account_Type based on Request Booking checkbox
            # Request Booking TRUE -> show non-Contract (Dispensing, TRADE, Distribution)
            # Request Booking FALSE -> show only Contract accounts
            # When completing_br_id: no filter (booking's client may be any type)
            if not completing_br_id and st.session_state.get('authenticated', False) and st.session_state.get('user_role') == 'Sales Rep':
                if not active_accounts.empty and 'Account_Type' in active_accounts.columns:
                    at_vals = active_accounts['Account_Type'].fillna('').astype(str).str.strip().str.upper()
                    if request_booking:
                        active_accounts = active_accounts[at_vals != 'CONTRACT'].copy()
                    else:
                        active_accounts = active_accounts[at_vals == 'CONTRACT'].copy()
            
            # Show Related Accounts Only: filter by PMR_tag or TSR_tag = user's RepCode (default True)
            if not completing_br_id:
                show_related_only = st.checkbox(
                    "Show Related Accounts Only",
                    value=True,
                    key="tab_show_related_only",
                    help="Filter accounts where your RepCode matches the account's PMR_tag or TSR_tag. Uncheck to see all accounts."
                )
                if show_related_only and st.session_state.get('authenticated', False):
                    rep_code = str(st.session_state.get('rep_code', '') or '').strip()
                    if rep_code and not active_accounts.empty and 'PMR_tag' in active_accounts.columns and 'TSR_tag' in active_accounts.columns:
                        pmr_match = active_accounts['PMR_tag'].fillna('').astype(str).str.strip() == rep_code
                        tsr_match = active_accounts['TSR_tag'].fillna('').astype(str).str.strip() == rep_code
                        active_accounts = active_accounts[pmr_match | tsr_match].copy()
            else:
                show_related_only = False
            
            customer_options = ['']  # Start with empty option
            
            if not active_accounts.empty and 'Customer name' in active_accounts.columns:
                # Get unique customer names and sort them
                customer_names = active_accounts['Customer name'].astype(str).str.strip()
                customer_names = customer_names[customer_names != ''].unique()
                customer_options.extend(sorted(customer_names.tolist()))
            
            # CRITICAL: Clear session state if stored selection is no longer in active options
            # Streamlit selectbox preserves session state value even when not in options - would show inactive accounts
            # Skip when completing_br_id - we may add the booking's client to options
            if not completing_br_id:
                stored = st.session_state.get('client_name_select', '')
                if stored and stored not in customer_options:
                    st.session_state.client_name_select = ''
            
            # Callback function to update fields when customer selection changes
            def update_tab_customer_fields():
                selected = st.session_state.client_name_select
                if selected and not active_accounts.empty:
                    # Filter DataFrame to get the selected client's data
                    client_row = active_accounts[active_accounts['Customer name'].astype(str).str.strip() == selected]
                    if not client_row.empty:
                        client_details = client_row.iloc[0]
                        # Update widget keys directly in session state
                        st.session_state.client_description = str(client_details.get('Customer code', '')).strip() if 'Customer code' in active_accounts.columns else ''
                        st.session_state.client_mobile = str(client_details.get('Contact number1', '')).strip() if 'Contact number1' in active_accounts.columns else ''
                        billing_addr = str(client_details.get('Business address', '')).strip() if 'Business address' in active_accounts.columns else ''
                        st.session_state.billing_address = billing_addr
                        st.session_state.shipping_address = billing_addr
                        st.session_state.contact_person_1 = str(client_details.get('Contact person1', '')).strip() if 'Contact person1' in active_accounts.columns else ''
                        st.session_state.payment_terms = str(client_details.get('Credit term', '')).strip() if 'Credit term' in active_accounts.columns else ''
                        
                        # CRITICAL: Store account tags in session state for persistence
                        # These tags are needed for notifications even if not displayed in UI
                        tsr_tag = str(client_details.get('TSR_tag', '') or '').strip() if 'TSR_tag' in active_accounts.columns else ''
                        st.session_state.account_TSR_tag = tsr_tag
                        st.session_state.account_PMR_tag = str(client_details.get('PMR_tag', '') or '').strip() if 'PMR_tag' in active_accounts.columns else ''
                        st.session_state.account_DSMBU7_tag = str(client_details.get('DSMBU7_tag', '') or '').strip() if 'DSMBU7_tag' in active_accounts.columns else ''
                        st.session_state.account_DSMPSI_tag = str(client_details.get('DSMPSI_tag', '') or '').strip() if 'DSMPSI_tag' in active_accounts.columns else ''
                        # Auto-fill TSR Code when Request Booking is True - match account TSR_tag to TSR rep_code
                        if st.session_state.get('tab_request_booking', False) and tsr_tag:
                            tsr_df = db.get_users_by_account_type("TRADE")
                            if not tsr_df.empty:
                                match = tsr_df[tsr_df['RepCode'].astype(str).str.strip() == tsr_tag]
                                if not match.empty:
                                    row = match.iloc[0]
                                    tsr_option = f"{row.get('RepCode', '') or ''} - {row.get('RepName', '') or ''}"
                                    st.session_state.tab_tsr_select = tsr_option
                        # Auto-fill Notes/Remarks from SO_history (customer + SKU match, most recent first)
                        if apply_so_history_notes_to_cart(selected.strip()):
                            if 'tab_cart_editor' in st.session_state:
                                del st.session_state.tab_cart_editor
                            st.session_state.tab_notes_auto_filled = True
                else:
                    # Clear fields when no customer selected
                    st.session_state.client_description = ''
                    st.session_state.client_mobile = ''
                    st.session_state.billing_address = ''
                    st.session_state.shipping_address = ''
                    st.session_state.contact_person_1 = ''
                    st.session_state.payment_terms = ''
                    # Clear account tags
                    st.session_state.account_TSR_tag = ''
                    st.session_state.account_PMR_tag = ''
                    st.session_state.account_DSMBU7_tag = ''
                    st.session_state.account_DSMPSI_tag = ''
                    if st.session_state.get('tab_request_booking', False):
                        st.session_state.tab_tsr_select = "(Select TSR)"
            
            # Initialize widget keys if they don't exist
            if 'client_description' not in st.session_state:
                st.session_state.client_description = ''
            if 'client_mobile' not in st.session_state:
                st.session_state.client_mobile = ''
            if 'billing_address' not in st.session_state:
                st.session_state.billing_address = ''
            if 'shipping_address' not in st.session_state:
                st.session_state.shipping_address = ''
            if 'contact_person_1' not in st.session_state:
                st.session_state.contact_person_1 = ''
            if 'payment_terms' not in st.session_state:
                st.session_state.payment_terms = ''
            
            # Initialize account tags in session state if they don't exist
            # These tags are needed for notifications even if not displayed in UI
            if 'account_TSR_tag' not in st.session_state:
                st.session_state.account_TSR_tag = ''
            if 'account_PMR_tag' not in st.session_state:
                st.session_state.account_PMR_tag = ''
            if 'account_DSMBU7_tag' not in st.session_state:
                st.session_state.account_DSMBU7_tag = ''
            if 'account_DSMPSI_tag' not in st.session_state:
                st.session_state.account_DSMPSI_tag = ''
            
            st.subheader("Client Information")
            
            # Client Name selectbox - disabled when completing booking request
            # Use booking_client_name when completing (avoids Streamlit "default value" conflict warning)
            _client_index = 0
            _client_name = (st.session_state.get('booking_client_name') or st.session_state.get('client_name_select') or '') if is_completing_br else (st.session_state.get('client_name_select', '') or '')
            if isinstance(_client_name, str):
                _client_name = _client_name.strip()
            
            # CRITICAL: Ensure client_name persists - if it was set before, keep it
            # This handles the case where Save Changes causes rerun and we need to restore selection
            if not _client_name and 'client_name_select' in st.session_state:
                stored_client = st.session_state.client_name_select
                if stored_client and isinstance(stored_client, str) and stored_client.strip() and stored_client.strip() != '':
                    _client_name = stored_client.strip()
            
            # Calculate index for selectbox - ensure we find the correct customer
            if _client_name and _client_name in customer_options:
                _client_index = customer_options.index(_client_name)
            elif _client_name and is_completing_br:
                # For completing booking request, add customer to options if not present
                customer_options = list(customer_options)
                if _client_name not in customer_options:
                    customer_options.insert(1, _client_name)
                _client_index = customer_options.index(_client_name)
            elif not _client_name:
                # No client selected - default to empty option (index 0)
                _client_index = 0
            
            selected_customer = st.selectbox(
                "Account / Customer Name  *",
                options=customer_options,
                index=_client_index,
                key="client_name_select",
                help="Select a customer to auto-fill details and Notes/Remarks from SO history" if not is_completing_br else "Pre-filled from booking request (read-only)",
                on_change=update_tab_customer_fields if not is_completing_br else None,
                disabled=is_completing_br
            )
            
            # Get customer name - ensure it persists
            client_name = selected_customer.strip() if selected_customer and selected_customer.strip() else ''
            
            # CRITICAL: If client_name is empty but we had a selection before, restore it
            # This handles edge cases where selectbox might reset to empty option after rerun
            if not client_name and 'client_name_select' in st.session_state:
                stored = st.session_state.client_name_select
                if stored and isinstance(stored, str) and stored.strip() and stored.strip() != '':
                    client_name = stored.strip()
                    # Update session state to ensure persistence
                    st.session_state.client_name_select = client_name
            
            # CRITICAL: Ensure account tags are loaded if client is selected but tags are missing
            # This handles cases where tags weren't loaded initially or were cleared
            if client_name and client_name.strip() and (
                not st.session_state.get('account_TSR_tag') and 
                not st.session_state.get('account_PMR_tag') and 
                not st.session_state.get('account_DSMBU7_tag') and 
                not st.session_state.get('account_DSMPSI_tag')
            ):
                # Tags are missing but client is selected - restore them from database
                account_tags = get_account_tags(client_name)
                if account_tags:
                    tsr_tag = account_tags.get('TSR_tag', '') or ''
                    st.session_state.account_TSR_tag = tsr_tag
                    st.session_state.account_PMR_tag = account_tags.get('PMR_tag', '')
                    st.session_state.account_DSMBU7_tag = account_tags.get('DSMBU7_tag', '')
                    st.session_state.account_DSMPSI_tag = account_tags.get('DSMPSI_tag', '')
                    # Auto-fill TSR Code when Request Booking is True
                    if st.session_state.get('tab_request_booking', False) and tsr_tag:
                        tsr_df = db.get_users_by_account_type("TRADE")
                        if not tsr_df.empty:
                            match = tsr_df[tsr_df['RepCode'].astype(str).str.strip() == tsr_tag]
                            if not match.empty:
                                row = match.iloc[0]
                                st.session_state.tab_tsr_select = f"{row.get('RepCode', '') or ''} - {row.get('RepName', '') or ''}"
            
            # Show entire form only when an account is selected
            if not client_name:
                if len(customer_options) <= 1 and not is_completing_br:
                    tips = []
                    if st.session_state.get('user_role') == 'Sales Rep':
                        tips.append("**Request Booking**: checked = Dispensing/TRADE/Distribution; unchecked = Contract only")
                    if st.session_state.get('rep_code'):
                        tips.append("**Show Related Accounts Only**: uncheck to see all accounts")
                    st.info("No accounts match the current filter. " + (" Try: " + "; ".join(tips) + "." if tips else "Uncheck **Show Related Accounts Only** to see all accounts."))
                else:
                    st.info("Select a customer from the list above to view and edit client details.")
            elif request_booking and not is_completing_br:
                # --- TRADE Special Flow: Booking Request form (Med Rep requests TSR to complete) ---
                # TSR completing a booking must NOT see this - they complete orders, not request them
                st.markdown("### Booking Request (TRADE - Med Rep requests TSR to complete)")
                tsr_df = db.get_users_by_account_type("TRADE")
                tsr_options = ["(Select TSR)"] + [f"{row.get('RepCode', '') or ''} - {row.get('RepName', '') or ''}" for _, row in tsr_df.iterrows()] if not tsr_df.empty else ["(Select TSR)"]
                
                with st.form("booking_request_form_tab"):
                    # Check if account has empty required fields - PMR/Sales Rep must complete before submitting
                    empty_account_fields = get_account_empty_required_fields(client_name)
                    if empty_account_fields:
                        st.warning("**Complete Account Fields** — The selected account has empty required fields. Please fill them in and click **Update Account** before submitting the booking request.")
                        accounts_df = load_accounts()
                        account_row = accounts_df[accounts_df['Customer name'].astype(str).str.strip() == str(client_name).strip()].iloc[0] if not accounts_df.empty else {}
                        for db_col, label in empty_account_fields:
                            key_safe = f"br_account_{db_col.replace(' ', '_')}"
                            current = str(account_row.get(db_col, '') or '').strip()
                            if db_col == 'Business address':
                                st.text_area(f"{label} *", value=current, key=key_safe, placeholder=f"Enter {label.lower()}...")
                            else:
                                st.text_input(f"{label} *", value=current, key=key_safe, placeholder=f"Enter {label.lower()}...", autocomplete="off")
                        update_account_btn = st.form_submit_button("Update Account", use_container_width=True)
                        if update_account_btn:
                            updates = {}
                            for db_col, _ in empty_account_fields:
                                key_safe = f"br_account_{db_col.replace(' ', '_')}"
                                val = st.session_state.get(key_safe, '')
                                updates[db_col] = str(val).strip() if val else ''
                            if updates and update_account_fields_by_client_name(client_name, updates):
                                st.success("Account updated successfully. You can now submit the booking request.")
                                st.rerun()
                            else:
                                st.error("Failed to update account. Please try again.")
                        st.markdown("---")
                    # TSR Code selection - Name is hidden to avoid confusion (it's already included in the selectbox display)
                    # Initialize from session state to persist across reruns
                    default_tsr = st.session_state.get('tab_tsr_select', "(Select TSR)")
                    tsr_index = 0
                    if default_tsr in tsr_options:
                        tsr_index = tsr_options.index(default_tsr)
                    tsr_select = st.selectbox("TSR Code *", options=tsr_options, index=tsr_index, key="tab_tsr_select",
                                             help="Select TSR from the list. The name is included in the selection.")
                    
                    # Initialize date from session state, default to today if not set
                    default_date = st.session_state.get('tab_booking_shipping_date')
                    if default_date is None:
                        default_date = datetime.now().date()
                    elif isinstance(default_date, str):
                        try:
                            default_date = datetime.strptime(default_date, '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            default_date = datetime.now().date()
                    # date_input with key automatically persists, but we initialize from session state for consistency
                    shipping_date_br = st.date_input("Shipping Date:", value=default_date, key="tab_booking_shipping_date")
                    
                    # Initialize text areas from session state to persist values
                    default_special_instructions = st.session_state.get('tab_booking_special_instructions', '')
                    special_instructions_br = st.text_area("Special Instructions", value=default_special_instructions, 
                                                          key="tab_booking_special_instructions", placeholder="Enter special instructions...")
                    
                    # Attached / Uploading Files (shown instead of Remarks when Request Booking is True)
                    st.markdown("### Attach File(s) (Optional)")
                    uploaded_files_br = st.file_uploader(
                        "Attach file(s) (Pictures and PDFs only)",
                        type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'],
                        accept_multiple_files=True,
                        key="tab_booking_file_uploader",
                        help="Attach multiple files. Each file must be 100MB or less. Supported formats: Images (PNG, JPG, JPEG, GIF, BMP, WEBP) and PDFs."
                    )
                    
                    if uploaded_files_br:
                        valid_files_br = []
                        invalid_files_br = []
                        for uploaded_file in uploaded_files_br:
                            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
                            if file_size_mb > 100:
                                invalid_files_br.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB - exceeds 100MB limit)")
                            else:
                                valid_files_br.append(uploaded_file)
                        if invalid_files_br:
                            st.error("The following files exceed the 100MB limit:\n" + "\n".join(f"- {f}" for f in invalid_files_br))
                        if valid_files_br:
                            st.session_state.booking_uploaded_files_tab = valid_files_br
                            st.success(f"✅ {len(valid_files_br)} file(s) ready to attach")
                            for i, file in enumerate(valid_files_br, 1):
                                file_size_mb = len(file.getvalue()) / (1024 * 1024)
                                st.caption(f"{i}. {file.name} ({file_size_mb:.2f} MB)")
                        else:
                            st.session_state.booking_uploaded_files_tab = []
                    else:
                        st.session_state.booking_uploaded_files_tab = []
                    
                    st.markdown("---")
                    submit_booking_btn = st.form_submit_button("Submit Booking", type="primary", use_container_width=True)
                    
                    if submit_booking_btn:
                        # Block submission if account has empty required fields
                        if empty_account_fields:
                            st.error("Please complete the account fields above and click **Update Account** before submitting the booking request.")
                        else:
                            # Extract TSR code and name from selection
                            if tsr_select and tsr_select != "(Select TSR)":
                                parts = tsr_select.split(" - ", 1)
                                tsr_code_val = (parts[0] or "").strip()
                                tsr_name_val = (parts[1] or "").strip() if len(parts) > 1 else ""
                            else:
                                tsr_code_val = ""
                                tsr_name_val = ""
                            
                            items_empty = get_cart_items_with_empty_notes()
                            if items_empty:
                                st.session_state.submit_order_notes_validation_failed = True
                                st.rerun()
                            elif not tsr_code_val or not tsr_name_val:
                                st.error("Please select a TSR.")
                            elif not st.session_state.cart:
                                st.error("Cart is empty. Add products before submitting a booking request.")
                            else:
                                with st.spinner("Submitting booking request..."):
                                    request_id = f"BR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
                                    cart_items_json = json.dumps([item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart])
                                    # Remarks hidden when Request Booking - pass empty string
                                    remarks_br = ''
                                    ship_date_str = shipping_date_br.strftime('%Y-%m-%d')
                                    created_by = st.session_state.get('username', '')
                                    if db.create_booking_request(request_id, tsr_code_val, tsr_name_val, client_name,
                                            ship_date_str, special_instructions_br or '', remarks_br,
                                            cart_items_json, created_by):
                                        # Save uploaded files for booking request if any
                                        br_files = st.session_state.get('booking_uploaded_files_tab', [])
                                        if br_files:
                                            save_booking_request_attachments(request_id, br_files)
                                        # Send notification to TSR in background (don't block UI)
                                        def _send_br_notification():
                                            try:
                                                send_booking_request_notification_to_tsr(
                                                    request_id, tsr_code_val, tsr_name_val, client_name,
                                                    ship_date_str, special_instructions_br or '',
                                                    remarks_br, created_by
                                                )
                                            except Exception as e:
                                                print(f"Background booking notification error: {e}")
                                        threading.Thread(target=_send_br_notification, daemon=True).start()
                                        
                                        st.success("Booking request submitted successfully! Check Request/Order History to track status.")
                                        st.session_state.cart = []
                                        st.session_state.booking_uploaded_files_tab = []
                                        # Clear booking request form fields after successful submission
                                        if 'tab_tsr_select' in st.session_state:
                                            st.session_state.tab_tsr_select = "(Select TSR)"
                                        if 'tab_booking_shipping_date' in st.session_state:
                                            del st.session_state.tab_booking_shipping_date
                                        if 'tab_booking_special_instructions' in st.session_state:
                                            st.session_state.tab_booking_special_instructions = ''
                                        st.rerun()
                                    else:
                                        st.error("Failed to save booking request. Please try again.")
            else:
                with st.form("order_form"):
                    # Client fields - when TSR completing booking: all read-only, only Remarks editable
                    # Empty required fields are pre-filled with "N/A" so TSR can submit
                    _readonly = is_completing_br
                    def _field_disabled(key, default=''):
                        if _readonly:
                            return True  # TSR Complete Booking: all client/order fields read-only
                        return False  # Normal order: all fields editable
                    st.text_area(
                        "Client Category *",
                        key="client_description",
                        disabled=_field_disabled("client_description")
                    )
                    st.text_input(
                        "Mobile *",
                        key="client_mobile",
                        disabled=_field_disabled("client_mobile"),
                        autocomplete="tel"
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        st.text_area(
                            "Billing Address *",
                            key="billing_address",
                            disabled=_field_disabled("billing_address")
                        )
                    with col2:
                        st.text_area(
                            "Shipping Address *",
                            key="shipping_address",
                            disabled=_field_disabled("shipping_address")
                        )
                    
                    # Initialize contact person and payment terms keys if they don't exist
                    if 'contact_person_1' not in st.session_state:
                        st.session_state.contact_person_1 = ''
                    if 'payment_terms' not in st.session_state:
                        st.session_state.payment_terms = ''
                    
                    st.markdown("---")
                    st.markdown("### Contact Persons")
                    col1, col2 = st.columns(2)
                    with col1:
                        contact_person_1 = st.text_input(
                            "Contact Person 1",
                            key="contact_person_1",
                            disabled=_field_disabled("contact_person_1"),
                            autocomplete="off"
                        )
                        contact_person_1_mobile = st.text_input("Contact Person 1 Mobile", key="contact_person_1_mobile", disabled=_field_disabled("contact_person_1_mobile"), autocomplete="tel")
                    with col2:
                        contact_person_2 = st.text_input("Contact Person 2", key="contact_person_2", disabled=_field_disabled("contact_person_2"), autocomplete="off")
                        contact_person_2_mobile = st.text_input("Contact Person 2 Mobile", key="contact_person_2_mobile", disabled=_field_disabled("contact_person_2_mobile"), autocomplete="tel")
                    
                    st.markdown("---")
                    st.subheader("Order Terms")
                    st.text_input(
                        "Payment Terms *",
                        key="payment_terms",
                        placeholder="e.g., Net 30, COD, etc.",
                        disabled=_field_disabled("payment_terms"),
                        autocomplete="off"
                    )
                    delivery_terms = st.text_area("Delivery Instructions *", key="delivery_terms",
                                                placeholder="Enter delivery instructions...", disabled=_field_disabled("delivery_terms"))
                    col1, col2 = st.columns(2)
                    with col1:
                        delivery_date = st.date_input("Delivery Date / Requested Ship Date *", key="delivery_date", disabled=_readonly)  # Date always from account/shipping
                    with col2:
                        discount_percent = st.number_input("Discount (%)", min_value=0.0, max_value=100.0,
                                                           value=0.0, step=0.1, key="discount_percent", disabled=True)
                    
                    # Calculate and display totals with discount
                    subtotal_calc = sum(item.qty * item.price for item in st.session_state.cart)
                    discount_amount_calc = (subtotal_calc * discount_percent) / 100
                    total_calc = subtotal_calc - discount_amount_calc
                    
                    st.markdown("---")
                    st.markdown("### Order Summary")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Subtotal", f"{subtotal_calc:.2f}")
                    with col2:
                        if discount_percent > 0:
                            st.metric(f"Discount ({discount_percent}%)", f"-{discount_amount_calc:.2f}")
                        else:
                            st.metric("Discount", "0.00")
                    with col3:
                        st.metric("**Total Amount**", f"**{total_calc:.2f}**")
                    
                    st.markdown("---")
                    st.subheader("Additional Information")
                    # Initialize Notes and Remarks session state if not set
                    # When completing booking request, these are already set from booking request data
                    if 'notes' not in st.session_state:
                        st.session_state.notes = ''
                    if 'remarks' not in st.session_state:
                        st.session_state.remarks = ''
                    
                    notes = st.text_area("Notes / Special Instructions", key="notes", disabled=_field_disabled("notes"))
                    remarks = st.text_area("Remarks", key="remarks")  # Only editable field when TSR completing
                    
                    # When completing BR: Save Changes button to mark form as saved (gray -> green)
                    if is_completing_br:
                        col_save, col_submit = st.columns(2)
                        with col_save:
                            save_changes_br = st.form_submit_button("💾 Save Changes", type="secondary", use_container_width=True,
                                                                    help="Save your changes. Form will turn green when saved.")
                        with col_submit:
                            submit_order = st.form_submit_button("Submit Order", type="primary", use_container_width=True)
                        if save_changes_br:
                            st.session_state.br_place_order_saved = True
                            st.success("Changes saved. Form is ready for submission.")
                            st.rerun()
                    else:
                        # Normal (non-booking) flow: only create the Submit Order button once,
                        # later in the form after Representative Information.
                        submit_order = False
                    
                    # Attachments section: when completing booking request, show view-only; otherwise show uploader
                    if is_completing_br:
                        # TSR completing: view-only display of files uploaded by Med Rep (no edit/upload)
                        st.markdown("### 📎 Attached Files (from Med Rep — View Only)")
                        br_attachments = get_booking_request_attachments(completing_br_id)
                        if br_attachments:
                            display_order_attachments(str(br_attachments))
                            st.caption("These files were attached by the Med Rep. They will be included with the order when you submit.")
                        else:
                            st.caption("No files were attached by the Med Rep.")
                        st.session_state.order_uploaded_files = []
                    else:
                        # Normal order: file uploader
                        st.markdown("### Attach File(s) (Optional)")
                        uploaded_files = st.file_uploader(
                            "Attach file(s) (Pictures and PDFs only)",
                            type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'],
                            accept_multiple_files=True,
                            key="tab_file_uploader",
                            help="Attach multiple files. Each file must be 100MB or less. Supported formats: Images (PNG, JPG, JPEG, GIF, BMP, WEBP) and PDFs."
                        )
                        
                        # Validate file sizes and store valid files
                        if uploaded_files:
                            valid_files = []
                            invalid_files = []
                            
                            for uploaded_file in uploaded_files:
                                file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)  # Convert to MB
                                if file_size_mb > 100:
                                    invalid_files.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB - exceeds 100MB limit)")
                                else:
                                    valid_files.append(uploaded_file)
                            
                            if invalid_files:
                                st.error("The following files exceed the 100MB limit:\n" + "\n".join(f"- {f}" for f in invalid_files))
                            
                            if valid_files:
                                st.session_state.order_uploaded_files = valid_files
                                st.success(f"✅ {len(valid_files)} file(s) ready to attach")
                                # Display uploaded file names
                                for i, file in enumerate(valid_files, 1):
                                    file_size_mb = len(file.getvalue()) / (1024 * 1024)
                                    st.caption(f"{i}. {file.name} ({file_size_mb:.2f} MB)")
                            else:
                                st.session_state.order_uploaded_files = []
                        else:
                            st.session_state.order_uploaded_files = []
                    
                    # Rep information (auto-filled but editable)
                    st.markdown("---")
                    st.subheader("Representative Information")
                    col1, col2 = st.columns(2)
                    with col1:
                        rep_code = st.text_input("Code *", value=st.session_state.rep_code, key="rep_code", autocomplete="off")
                        rep_name = st.text_input("Name *", value=st.session_state.rep_name, key="rep_name", autocomplete="off")
                        rep_company = st.text_input("Company *", value=st.session_state.rep_company, key="rep_company", autocomplete="off")
                    with col2:
                        rep_dept = st.text_input("Dept/DSM District *", value=st.session_state.rep_dept, key="rep_dept", autocomplete="off")
                        rep_area = st.text_input("Area/PMR *", value=st.session_state.rep_area, key="rep_area", autocomplete="off")
                    
                    if not is_completing_br:
                        submit_order = st.form_submit_button("Submit Order", type="primary")
                    
                    if submit_order:
                        # Validation - require Notes/Remarks per SKU (skip when completing booking - cart is read-only)
                        if not is_completing_br:
                            items_empty = get_cart_items_with_empty_notes()
                            if items_empty:
                                st.session_state.submit_order_notes_validation_failed = True
                                st.rerun()
                        # Get values from session state for validation
                        client_description_val = st.session_state.get('client_description', '')
                        client_mobile_val = st.session_state.get('client_mobile', '')
                        billing_address_val = st.session_state.get('billing_address', '')
                        shipping_address_val = st.session_state.get('shipping_address', '')
                        contact_person_1_val = st.session_state.get('contact_person_1', '')
                        payment_terms_val = st.session_state.get('payment_terms', '')
                        
                        # Validation - ensure client_name is set
                        if not client_name or client_name.strip() == '':
                            st.error("Please select a client name from the dropdown.")
                        else:
                            # Define is_trade_booking early so it's always set before any use (avoids UnboundLocalError on validation fail)
                            completing_br_id = st.session_state.get('selected_booking_request_id', '')
                            is_trade_booking = bool(completing_br_id and st.session_state.get('account_type') == 'TRADE')
                            # Validation
                            required_fields = {
                                'Client Name': client_name,
                                'Client Category': client_description_val,
                                'Mobile': client_mobile_val,
                                'Billing Address': billing_address_val,
                                'Shipping Address': shipping_address_val,
                                'Payment Terms': payment_terms_val,
                                'Delivery Instructions': delivery_terms,
                                'Code': rep_code,
                                'Name': rep_name,
                                'Company': rep_company,
                                'Dept/DSM District': rep_dept,
                                'Area/PMR': rep_area
                            }
                            
                            missing_fields = [field for field, value in required_fields.items() if not value or value.strip() == '']
                            
                            if missing_fields:
                                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                            else:
                                with st.spinner("Submitting order... Saving data and sending notifications."):
                                    # Create order
                                    orders_df = load_orders()
                                    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                    
                                    # Save uploaded files if any; when completing booking request, copy Med Rep's attachments to order
                                    uploaded_files_list = st.session_state.get('order_uploaded_files', [])
                                    attachment_paths = []
                                    if uploaded_files_list:
                                        attachment_paths = save_order_attachments(order_id, uploaded_files_list)
                                    # When TSR completes booking request, include Med Rep's uploaded files in the order
                                    completing_br_id_submit = st.session_state.get('selected_booking_request_id', '')
                                    if completing_br_id_submit and st.session_state.get('account_type') == 'TRADE':
                                        br_attachment_paths = copy_booking_request_attachments_to_order(completing_br_id_submit, order_id)
                                        attachment_paths = attachment_paths + br_attachment_paths
                                    
                                    # Calculate totals
                                    subtotal = sum(item.qty * item.price for item in st.session_state.cart)
                                    discount_amount = (subtotal * discount_percent) / 100
                                    total_amount = subtotal - discount_amount
                                    
                                    # Get account tags from selected account
                                    account_tags = get_account_tags(client_name)
                                    
                                    # Check if account needs SGF workflow
                                    needs_sgf = check_sgf_eligibility(client_name)
                                    
                                    # Get account type and determine approval workflow
                                    # Contract → Pending for Approval 1. TRADE/Dispensing/Distribution (and BR-completed) → skip L1.
                                    account_type = get_account_type_by_client_name(client_name)
                                    account_type_upper = account_type.upper()
                                    skip_level1 = (account_type_upper in ('TRADE', 'DISPENSING', 'DISTRIBUTION') or is_trade_booking)
                                    if needs_sgf:
                                        initial_status = 'Pending for SGF'
                                        approved_by_l1 = ''
                                        approved_date_l1 = ''
                                    elif skip_level1:
                                        initial_status = 'Pending for Approval 2'
                                        approved_by_l1 = 'SYSTEM'
                                        approved_date_l1 = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    else:
                                        # Contract only: go through Level 1 first
                                        initial_status = 'Pending for Approval 1'
                                        approved_by_l1 = ''
                                        approved_date_l1 = ''
                                    
                                    # Create order record
                                    order_data = {
                                        'OrderID': order_id,
                                        'OrderDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'Status': initial_status,
                                        'Printed': '',
                                        'PrintedDate': '',
                                        'PrintedTime': '',
                                        'ApprovedBySGF': '',
                                        'ApprovedDateSGF': '',
                                        'ApprovedByLevel1': approved_by_l1,
                                        'ApprovedDateLevel1': approved_date_l1,
                                        'ApprovedByLevel2': '',
                                        'ApprovedDateLevel2': '',
                                        'DisapprovedItems': '[]',
                                        'ClientName': client_name,
                                        'ClientDescription': client_description_val,
                                        'ClientMobile': client_mobile_val,
                                        'BillingAddress': billing_address_val,
                                        'ShippingAddress': shipping_address_val,
                                        'ContactPerson1': contact_person_1_val,
                                        'ContactPerson1Mobile': contact_person_1_mobile,
                                        'ContactPerson2': contact_person_2,
                                        'ContactPerson2Mobile': contact_person_2_mobile,
                                        'PaymentTerms': payment_terms_val,
                                        'DeliveryTerms': delivery_terms,
                                        'DeliveryDate': delivery_date.strftime('%Y-%m-%d'),
                                        'DiscountPercent': discount_percent,
                                        'DiscountAmount': discount_amount,
                                        'Subtotal': subtotal,
                                        'Notes': notes,
                                        'RepCode': rep_code,
                                        'RepName': rep_name,
                                        'RepCompany': rep_company,
                                        'RepDept': rep_dept,
                                        'RepArea': rep_area,
                                        'Remarks': remarks,
                                        'TotalAmount': total_amount,
                                        'CartItems': str([item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart]),
                                        'BR_CreatedBy': st.session_state.get('br_created_by', '') if is_trade_booking else '',
                                        'BookingRequestID': completing_br_id if is_trade_booking else '',
                                        'Attachments': str(attachment_paths) if attachment_paths else '',
                                        'CreatedBy': st.session_state.username,
                                        'TSR_tag': account_tags['TSR_tag'],
                                        'PMR_tag': account_tags['PMR_tag'],
                                        'DSMBU7_tag': account_tags['DSMBU7_tag'],
                                        'DSMPSI_tag': account_tags['DSMPSI_tag']
                                    }
                                    
                                    # Add to orders DataFrame
                                    new_order_df = pd.DataFrame([order_data])
                                    if orders_df.empty:
                                        orders_df = new_order_df
                                    else:
                                        orders_df = pd.concat([orders_df, new_order_df], ignore_index=True)
                                    
                                    if save_orders(orders_df):
                                        # Send email notifications in background thread (don't block UI)
                                        def _send_order_notifications():
                                            try:
                                                send_order_notification_to_rep(order_id, order_data.copy(), 
                                                                              "Order submitted successfully", 
                                                                              notification_type="submitted")
                                                send_notification_to_related_users(order_id, order_data.copy(), 
                                                                                 "Related order submitted", 
                                                                                 notification_type="submitted")
                                                if needs_sgf:
                                                    send_sgf_notification()
                                                elif skip_level1:
                                                    send_approval_notification_to_admin(order_id, order_data.copy(), admin_level=2)
                                                    send_approval_notification(admin_level=2)
                                                else:
                                                    send_approval_notification_to_admin(order_id, order_data.copy(), admin_level=1)
                                                    send_approval_notification(admin_level=1)
                                            except Exception as e:
                                                print(f"Background notification error: {e}")
                                        
                                        t = threading.Thread(target=_send_order_notifications, daemon=True)
                                        t.start()
                                        
                                        if is_trade_booking:
                                            db.update_booking_request_status(completing_br_id, 'Completed', order_id)
                                            st.session_state.selected_booking_request_id = ''
                                            st.session_state.booking_request_loaded_id = ''
                                            if 'booking_client_name' in st.session_state:
                                                del st.session_state['booking_client_name']
                                        
                                        # Clear cart and form state on success
                                        st.session_state.cart = []
                                        st.session_state.order_uploaded_files = []
                                        st.session_state.last_submitted_order_id = order_id
                                        st.session_state.order_submission_success = True
                                        if needs_sgf:
                                            status_message = "Pending for SGF approval"
                                        elif skip_level1:
                                            status_message = "Pending for Approval 2 (skips Level 1)"
                                        else:
                                            status_message = "Pending for Approval 1"
                                        if attachment_paths:
                                            st.success(f"Order {order_id} submitted successfully with {len(attachment_paths)} attachment(s)! ✅ Status: {status_message}. Check Request/Order History to view your order.")
                                        else:
                                            st.success(f"Order {order_id} submitted successfully! ✅ Status: {status_message}. Check Request/Order History to view your order.")
                                        st.balloons()
                                        st.rerun()
                                    else:
                                        st.error("Error saving order. Please try again.")
    
    with tab3:
        st.header("Request/Order History")
        
        # Show success message if order was just submitted
        if st.session_state.get('order_submission_success', False) and st.session_state.get('last_submitted_order_id'):
            st.success(f"🎉 Your order {st.session_state.last_submitted_order_id} has been successfully submitted! Status: Pending for Approval (awaiting finance review).")
            st.session_state.order_submission_success = False  # Reset flag after showing message
        
        # Show My Booking Requests (for Sales Reps who submitted booking requests) - exclude Auto-Cancel and Cancelled by Creator
        br_created_df = db.get_booking_requests_by_created_by(st.session_state.get('username', ''))
        if not br_created_df.empty:
            br_created_df = br_created_df[~br_created_df['status'].isin(['Auto-Cancel', 'Cancelled by Creator'])]
        if not br_created_df.empty:
            st.markdown("### My Booking Requests")
            st.caption("Booking requests you submitted for TSR to complete. Status: Pending = awaiting TSR; Completed = TSR has created the order.")
            for _, br_row in br_created_df.iterrows():
                rid = br_row.get('request_id', '')
                client = br_row.get('client_name', 'N/A')
                created = br_row.get('created_date', '')[:19] if br_row.get('created_date') else ''
                status = br_row.get('status', 'Pending')
                order_id = br_row.get('order_id', '')
                tsr_name = br_row.get('tsr_name', 'N/A')
                with st.expander(f"Request {rid} - {status} - {client} - {created}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Client:** {client}")
                        st.markdown(f"**TSR Assigned:** {tsr_name}")
                        st.markdown(f"**Created:** {created}")
                    with col2:
                        st.markdown(f"**Status:** {status}")
                        if order_id:
                            st.markdown(f"**Order ID:** {order_id}")
                            st.caption("TSR has completed this request.")
                            if st.button("🔍 View Order", key=f"view_br_order_{rid}", use_container_width=True):
                                st.session_state.selected_order_id = order_id
                                st.session_state.show_order_details_dialog = True
                                st.session_state.dialog_button_clicked = True
                                st.rerun()
                        else:
                            st.markdown("**Order ID:** —")
                            st.caption("Awaiting TSR to complete.")
                            if st.button("🚫 Cancel request", key=f"cancel_br_creator_{rid}", use_container_width=True, help="Cancel this booking request. You will be asked to provide a reason; the TSR will be notified."):
                                st.session_state.show_cancel_br_by_creator_dialog = True
                                st.session_state.cancel_br_request_id = rid
                                st.rerun()
                    
                    # Product / Cart details
                    cart_items_str = br_row.get('cart_items', '[]')
                    try:
                        cart_items_list = json.loads(cart_items_str) if isinstance(cart_items_str, str) else (cart_items_str or [])
                    except (json.JSONDecodeError, TypeError):
                        cart_items_list = []
                    if cart_items_list:
                        rows = []
                        for item in cart_items_list:
                            d = item if isinstance(item, dict) else {}
                            qty = int(d.get('qty', 1))
                            price = float(d.get('price', 0))
                            rows.append({
                                'Product Code': str(d.get('product_code', '')),
                                'Product Name': str(d.get('product_name', '')),
                                'Qty': qty,
                                'Price': price,
                                'Total': qty * price,
                                'Notes/Remarks': str(d.get('notes_remarks', '') or '')
                            })
                        cart_df = pd.DataFrame(rows)
                        st.markdown("**Products / Cart:**")
                        st.dataframe(cart_df, use_container_width=True, hide_index=True)
                        st.caption(f"Total: {cart_df['Total'].sum():,.2f}")
                    else:
                        st.caption("No products in this booking request.")
            st.markdown("---")
        
        # Auto-Cancel expander (booking requests auto-cancelled after 24h - moved from Booking Request tab)
        rep_code = st.session_state.get('rep_code', '')
        username = st.session_state.get('username', '')
        br_auto_cancel_df = db.get_booking_requests_auto_cancel_for_user(rep_code, username)
        if not br_auto_cancel_df.empty:
            st.markdown("### Auto-Cancel")
            st.caption("Booking requests cancelled after 24 hours without completion, or cancelled by you. View details below.")
            with st.expander(f"Auto-Cancel ({len(br_auto_cancel_df)} request{'s' if len(br_auto_cancel_df) != 1 else ''})", expanded=False):
                for _, br_row in br_auto_cancel_df.iterrows():
                    rid = br_row.get('request_id', '')
                    client = br_row.get('client_name', 'N/A')
                    created = br_row.get('created_date', '')[:19] if br_row.get('created_date') else ''
                    status_br = br_row.get('status', 'Auto-Cancel')
                    auto_cancel_date = br_row.get('auto_cancel_date', '')[:19] if br_row.get('auto_cancel_date') else 'N/A'
                    created_by = br_row.get('created_by', '')
                    cancel_reason = br_row.get('cancel_reason', '') or ''
                    with st.container(border=True):
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.markdown(f"**{client}**")
                            st.caption(f"Request ID: {rid} | Created: {created} by {created_by}")
                        with col2:
                            if status_br == 'Cancelled by Creator':
                                st.markdown(f"**Status:** Cancelled by you")
                            else:
                                st.markdown(f"**Auto-Cancelled:** {auto_cancel_date}")
                        if cancel_reason and str(cancel_reason).strip():
                            st.caption(f"**Reason for cancellation:** {cancel_reason}")
                        cart_items_str = br_row.get('cart_items', '[]')
                        try:
                            cart_items_list = json.loads(cart_items_str) if isinstance(cart_items_str, str) else (cart_items_str or [])
                        except (json.JSONDecodeError, TypeError):
                            cart_items_list = []
                        if cart_items_list:
                            rows = []
                            for item in cart_items_list:
                                d = item if isinstance(item, dict) else {}
                                qty = int(d.get('qty', 1))
                                price = float(d.get('price', 0))
                                rows.append({
                                    'Product Code': str(d.get('product_code', '')),
                                    'Product Name': str(d.get('product_name', '')),
                                    'Qty': qty,
                                    'Price': price,
                                    'Total': qty * price,
                                    'Notes/Remarks': str(d.get('notes_remarks', '') or '')
                                })
                            cart_df = pd.DataFrame(rows)
                            st.dataframe(cart_df, use_container_width=True, hide_index=True)
                            st.caption(f"Total: {cart_df['Total'].sum():,.2f}")
            st.markdown("---")
        
        orders_df = load_orders()
        
        st.markdown("### My Orders")
        if orders_df.empty:
            st.info("No orders found.")
        else:
            # Filter orders for this sales rep
            rep_orders = orders_df[orders_df['CreatedBy'] == st.session_state.username].copy()
            
            if rep_orders.empty:
                st.info("You have no orders yet.")
            else:
                # Sort by OrderDate descending
                rep_orders = rep_orders.sort_values('OrderDate', ascending=False)
                
                # Display orders
                for idx, row in rep_orders.iterrows():
                    # Check for disapproved items to update expander caption
                    disapproved_items_str = row.get('DisapprovedItems', '[]')
                    try:
                        disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
                    except (ValueError, SyntaxError):
                        disapproved_items = []
                    
                    disapproved_count = len(disapproved_items) if disapproved_items else 0
                    status = row['Status']
                    # Format status display - show Level 2 for TRADE accounts
                    display_status = format_order_status_display(row)
                    # Pending badge (red indicator) for easier visual scanning
                    is_pending_status = isinstance(display_status, str) and display_status.startswith('Pending')
                    pending_badge = "🔴 [PENDING] " if is_pending_status else ""
                    
                    # Build expander caption with disapproved items info
                    if disapproved_count > 0:
                        # Check if status already includes disapproved info
                        if 'removed/disapproved' not in status.lower() and 'disapproved' not in status.lower():
                            expander_caption = f"{pending_badge}Order {row['OrderID']} - {display_status} with {disapproved_count} removed/disapproved item(s) - {row['OrderDate']}"
                        else:
                            expander_caption = f"{pending_badge}Order {row['OrderID']} - {display_status} - {row['OrderDate']}"
                    else:
                        expander_caption = f"{pending_badge}Order {row['OrderID']} - {display_status} - {row['OrderDate']}"
                    
                    with st.expander(expander_caption):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Client:** {row['ClientName']}")
                            st.markdown(f"**Date:** {row['OrderDate']}")
                            # Format status display - show Level 2 for TRADE accounts
                            display_status = format_order_status_display(row)
                            st.markdown(f"**Status:** {display_status}")
                            st.markdown(f"**Total Amount:** {float(row.get('TotalAmount', 0)):.2f}")
                            
                            # Show approval status for clients
                            approved_by_l1 = row.get('ApprovedByLevel1', '')
                            approved_date_l1 = row.get('ApprovedDateLevel1', '')
                            approved_by_l2 = row.get('ApprovedByLevel2', '')
                            approved_date_l2 = row.get('ApprovedDateLevel2', '')
                            
                            if approved_by_l1:
                                if approved_by_l1 == 'SYSTEM':
                                    st.info(f"✅ Auto-approved by System (skips Level 1)")
                                else:
                                    st.info(f"✅ Approved by Level 1: {approved_by_l1} ({approved_date_l1})")
                            if approved_by_l2:
                                st.success(f"✅ Fully Approved by Level 2: {approved_by_l2} ({approved_date_l2})")
                            elif approved_by_l1 and not approved_by_l2:
                                st.warning("⏳ Waiting for Level 2 approval")
                        with col2:
                            st.markdown(f"**Name:** {row['RepName']} ({row['RepCode']})")
                            st.markdown(f"**Mobile:** {row['ClientMobile']}")
                            st.markdown(f"**Delivery Date:** {row.get('DeliveryDate', 'N/A')}")
                        
                        st.markdown("---")
                        st.markdown(f"**Client Category:** {row.get('ClientDescription', 'N/A')}")
                        st.markdown(f"**Payment Terms:** {row.get('PaymentTerms', 'N/A')}")
                        st.markdown(f"**Delivery Instructions:** {row.get('DeliveryTerms', 'N/A')}")
                        st.markdown(f"**Billing Address:** {row.get('BillingAddress', 'N/A')}")
                        st.markdown(f"**Shipping Address:** {row.get('ShippingAddress', 'N/A')}")
                        contact_person_1 = row.get('ContactPerson1', '')
                        contact_person_1_mobile = row.get('ContactPerson1Mobile', '')
                        contact_person_2 = row.get('ContactPerson2', '')
                        contact_person_2_mobile = row.get('ContactPerson2Mobile', '')
                        if contact_person_1 or contact_person_1_mobile:
                            st.markdown(f"**Contact Person 1:** {contact_person_1 if contact_person_1 else 'N/A'}")
                            st.markdown(f"**Contact Person 1 Mobile:** {contact_person_1_mobile if contact_person_1_mobile else 'N/A'}")
                        if contact_person_2 or contact_person_2_mobile:
                            st.markdown(f"**Contact Person 2:** {contact_person_2 if contact_person_2 else 'N/A'}")
                            st.markdown(f"**Contact Person 2 Mobile:** {contact_person_2_mobile if contact_person_2_mobile else 'N/A'}")
                        if row.get('Notes'):
                            st.markdown(f"**Notes:** {row.get('Notes', 'N/A')}")
                        if row.get('Remarks'):
                            st.markdown(f"**Remarks:** {row.get('Remarks', 'N/A')}")
                        
                        st.markdown("---")
                        
                        # Show disapproved items if any (already parsed above)
                        if disapproved_items and len(disapproved_items) > 0:
                            st.markdown("### ❌ Removed/Disapproved Items")
                            for dis_item in disapproved_items:
                                with st.container(border=True):
                                    st.error(f"**{dis_item.get('product_name', 'N/A')}** (Code: {dis_item.get('product_code', 'N/A')})")
                                    st.caption(f"**Reason:** {dis_item.get('disapproval_reason', 'N/A')}")
                                    st.caption(f"Removed by: {dis_item.get('disapproved_by', 'N/A')} on {dis_item.get('disapproved_date', 'N/A')}")
                            st.markdown("---")
                        
                        # View Details button to show ordered products
                        if st.button("🔍 View Details - Products Ordered", key=f"view_products_{row['OrderID']}_{idx}", use_container_width=True):
                            st.session_state.selected_order_id = row['OrderID']
                            st.session_state.show_order_details_dialog = True
                            st.session_state.dialog_button_clicked = True
                            st.rerun()
                        
                        # Show edit/cancel options only if status allows
                        if 'Unlocked for Edit' in row['Status']:
                            st.markdown("---")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("Edit Order", key=f"edit_{row['OrderID']}"):
                                    st.info("Edit functionality - To be implemented")
                            with col2:
                                if st.button("Cancel Order", key=f"cancel_{row['OrderID']}"):
                                    st.info("Cancel functionality - To be implemented")
        
        # Consolidated SO History (App orders + SO_history from CSV) - Admin and Super Admin only
        _can_view_so_history = normalize_role(st.session_state.get('user_role', '')) in ('Admin Level 0', 'Admin Level 1 Ethical', 'Admin Level 2') or st.session_state.get('username') == 'administrator'
        if _can_view_so_history:
            st.markdown("---")
            st.markdown("### Consolidated SO History")
            st.caption("Combined view: App orders (by product line) + SO History from CSV. Related columns: ClientName↔CUSTOMER NAME, RepCode↔REP CODE, OrderDate↔Full_DATE, TotalAmount↔GROSS SALES.")
            consolidated_df = get_consolidated_so_history()
            if consolidated_df.empty:
                st.info("No SO history data. Run load_so_history_from_csv.py to import the CSV into SO_history table.")
            else:
                st.dataframe(consolidated_df, use_container_width=True, hide_index=True)
    
    # Related Submitted Orders tab (rep_code matches TSR_tag OR PMR_tag OR DSMBU7_tag OR DSMPSI_tag)
    if tab4 is not None:
        with tab4:
            st.header("Related Submitted Orders")
            st.caption("Orders and booking requests for accounts where your rep code matches TSR_tag, PMR_tag, DSMBU7_tag, or DSMPSI_tag.")
            related_orders = get_orders_by_tag(rep_code, _tag_type)
            related_br = get_booking_requests_by_tag(rep_code)
            if related_orders.empty and related_br.empty:
                st.info("No related orders or booking requests found. They appear here when your rep code matches TSR_tag, PMR_tag, DSMBU7_tag, or DSMPSI_tag on the account.")

            if not related_br.empty:
                status_upper = related_br['status'].fillna('').astype(str).str.strip().str.upper()
                br_cancel = related_br[status_upper.str.contains('CANCEL', na=False)].copy().sort_values('created_date', ascending=False)
                br_active = related_br[~status_upper.str.contains('CANCEL', na=False)].copy().sort_values('created_date', ascending=False)
            else:
                br_cancel = pd.DataFrame()
                br_active = pd.DataFrame()
            related_orders = related_orders.sort_values('OrderDate', ascending=False) if not related_orders.empty else related_orders

            tab_br, tab_cancel, tab_orders = st.tabs(["📋 Related Booking Requests", "🚫 Related Auto-Cancel & Other Cancellations", "📦 Related Submitted Orders"])

            with tab_br:
                if br_active.empty:
                    st.info("No related booking requests.")
                else:
                    for idx, br_row in br_active.iterrows():
                        rid = br_row.get('request_id', '')
                        status = br_row.get('status', 'Pending')
                        client = br_row.get('client_name', 'N/A')
                        created = br_row.get('created_date', '')[:19] if br_row.get('created_date') else ''
                        created_by = br_row.get('created_by', '')
                        tsr_name = br_row.get('tsr_name', '')
                        tsr_code = br_row.get('tsr_code', '')
                        expander_caption = f"Booking Request {rid} - {status} - {created}"
                        with st.expander(expander_caption):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Client:** {client}")
                                st.markdown(f"**Created:** {created}")
                                st.markdown(f"**Status:** {status}")
                                st.markdown(f"**Assigned TSR:** {tsr_name or 'N/A'} ({tsr_code or 'N/A'})")
                            with col2:
                                st.markdown(f"**Created By:** {created_by}")
                                st.markdown(f"**Shipping Date:** {br_row.get('shipping_date', 'N/A')}")
                                order_id = br_row.get('order_id', '')
                                if order_id:
                                    st.markdown(f"**Completed Order:** {order_id}")
                            st.markdown("---")
                            if account_type == 'TRADE' and status == 'Pending' and tsr_code == rep_code:
                                if st.button("📝 Complete Booking", key=f"related_br_complete_{rid}_{idx}", use_container_width=True):
                                    st.session_state.selected_booking_request_id = rid
                                    st.session_state.booking_request_loaded_id = ''
                                    st.rerun()

            with tab_cancel:
                if br_cancel.empty:
                    st.info("No related auto-cancel or other cancellations.")
                else:
                    for idx, br_row in br_cancel.iterrows():
                        rid = br_row.get('request_id', '')
                        status = br_row.get('status', 'Pending')
                        client = br_row.get('client_name', 'N/A')
                        created = br_row.get('created_date', '')[:19] if br_row.get('created_date') else ''
                        created_by = br_row.get('created_by', '')
                        tsr_name = br_row.get('tsr_name', '')
                        tsr_code = br_row.get('tsr_code', '')
                        expander_caption = f"Booking Request {rid} - {status} - {created}"
                        with st.expander(expander_caption):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Client:** {client}")
                                st.markdown(f"**Created:** {created}")
                                st.markdown(f"**Status:** {status}")
                                st.markdown(f"**Assigned TSR:** {tsr_name or 'N/A'} ({tsr_code or 'N/A'})")
                            with col2:
                                st.markdown(f"**Created By:** {created_by}")
                                st.markdown(f"**Shipping Date:** {br_row.get('shipping_date', 'N/A')}")
                                cancel_reason = br_row.get('cancel_reason', '') or ''
                                if cancel_reason and str(cancel_reason).strip():
                                    st.markdown("---")
                                    st.markdown(f"**Reason for cancellation:** {cancel_reason}")

            with tab_orders:
                if related_orders.empty:
                    st.info("No related submitted orders.")
                else:
                    for idx, row in related_orders.iterrows():
                        disapproved_items_str = row.get('DisapprovedItems', '[]')
                        try:
                            disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
                        except (ValueError, SyntaxError):
                            disapproved_items = []
                        disapproved_count = len(disapproved_items) if disapproved_items else 0
                        status = row['Status']
                        if disapproved_count > 0 and 'disapproved' not in status.lower():
                            expander_caption = f"Order {row['OrderID']} - {status} with {disapproved_count} removed/disapproved item(s) - {row['OrderDate']}"
                        else:
                            expander_caption = f"Order {row['OrderID']} - {status} - {row['OrderDate']}"
                        with st.expander(expander_caption):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Client:** {row['ClientName']}")
                                st.markdown(f"**Date:** {row['OrderDate']}")
                                display_status = format_order_status_display(row)
                                st.markdown(f"**Status:** {display_status}")
                                st.markdown(f"**Total Amount:** {float(row.get('TotalAmount', 0)):.2f}")
                                approved_by_l1 = row.get('ApprovedByLevel1', '')
                                approved_date_l1 = row.get('ApprovedDateLevel1', '')
                                approved_by_l2 = row.get('ApprovedByLevel2', '')
                                if approved_by_l1:
                                    if approved_by_l1 == 'SYSTEM':
                                        st.info(f"✅ Auto-approved by System (skips Level 1)")
                                    else:
                                        st.info(f"✅ Approved by Level 1: {approved_by_l1} ({approved_date_l1})")
                                if approved_by_l2:
                                    st.success(f"✅ Fully Approved by Level 2: {approved_by_l2}")
                                elif approved_by_l1 and not approved_by_l2:
                                    st.warning("⏳ Waiting for Level 2 approval")
                            with col2:
                                st.markdown(f"**Name:** {row.get('RepName', '')} ({row.get('RepCode', '')})")
                                st.markdown(f"**Created By:** {row.get('CreatedBy', 'N/A')}")
                                st.markdown(f"**Delivery Date:** {row.get('DeliveryDate', 'N/A')}")
                            st.markdown("---")
                            if st.button("🔍 View Details", key=f"related_view_{row['OrderID']}_{idx}", use_container_width=True):
                                st.session_state.selected_order_id = row['OrderID']
                                st.session_state.show_order_details_dialog = True
                                st.session_state.dialog_button_clicked = True
                                st.rerun()

# Finance Staff Interface
def finance_staff_interface():
    """Finance Staff main interface"""
    st.title("💰 Finance - Order Review & Management")
    
    # Check if sync interface should be shown
    if st.session_state.get('show_sync', False):
        admin_sync_interface()
        return
    
    # If print view is requested, render it and return early
    if st.session_state.get('show_print_view') and st.session_state.get('print_view_order_id'):
        render_print_view(st.session_state.print_view_order_id)
        return
    
    
    # Show order details dialog if triggered
    # Only show if explicitly triggered by button click (not on filter changes)
    dialog_triggered = st.session_state.get('show_order_details_dialog', False)
    selected_order_id = st.session_state.get('selected_order_id')
    button_clicked = st.session_state.get('dialog_button_clicked', False)
    
    # Only show dialog if it's explicitly triggered by button click
    if dialog_triggered and selected_order_id and button_clicked:
        orders_df = load_orders()
        order_details_dialog(st.session_state.selected_order_id, orders_df)
        
        # After dialog runs, reset button_clicked flag to prevent re-opening on next rerun
        # If Close button was clicked, it already reset everything including this flag
        # If dialog was dismissed by clicking outside, this flag is still True, so we reset it
        # This ensures that on the next rerun (e.g., from filter change), dialog won't show
        st.session_state.dialog_button_clicked = False
    
    # Show disapprove dialog if triggered
    if st.session_state.get('show_disapprove_dialog', False) and st.session_state.get('disapprove_order_id'):
        orders_df = load_orders()
        disapprove_order_dialog(st.session_state.disapprove_order_id, orders_df)
    
    # Show cancel order dialog if triggered (Super Admin only)
    if st.session_state.get('show_cancel_order_dialog', False) and st.session_state.get('cancel_order_id'):
        orders_df = load_orders()
        cancel_order_dialog(st.session_state.cancel_order_id, orders_df)
    
    # Show unlock dialog if triggered
    if st.session_state.get('show_unlock_dialog', False) and st.session_state.get('unlock_order_id'):
        orders_df = load_orders()
        unlock_order_dialog(st.session_state.unlock_order_id, orders_df)
    
    # Show disapprove item dialog if triggered
    if st.session_state.get('show_disapprove_item_dialog', False) and st.session_state.get('disapprove_item_order_id') is not None:
        orders_df = load_orders()
        order = orders_df[orders_df['OrderID'] == st.session_state.disapprove_item_order_id]
        if not order.empty:
            order_row = order.iloc[0]
            cart_items_str = order_row.get('CartItems', '[]')
            cart_items = safe_parse_cart_items(cart_items_str)
            
            if st.session_state.disapprove_item_index < len(cart_items):
                item = cart_items[st.session_state.disapprove_item_index]
                item_name = item.get('product_name', 'Unknown Item')
                disapprove_item_dialog(st.session_state.disapprove_item_order_id, st.session_state.disapprove_item_index, item_name, orders_df)
    
    # Get admin level
    admin_level = st.session_state.get('admin_level')
    view_only = st.session_state.get('is_view_only', False)
    
    with st.sidebar:
        # Display logo at the top of sidebar
        display_logo(width=200)
        # Welcome message - show logged-in user
        _uname = st.session_state.get('username', '') or ''
        if _uname:
            st.success(f"👋 Welcome, **{_uname}**")
        st.markdown("---")
        st.header("Navigation")
        if st.button("🔓 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.username = None
            st.session_state.admin_level = None
            st.session_state.is_view_only = False
            # Reset all dialog states on logout
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_manage_products_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
            st.session_state.show_notification_management_dialog = False
            st.session_state.show_submit_order_dialog = False
            st.session_state.show_order_details_dialog = False
            st.rerun()
        
        st.markdown("---")
        st.header("Admin Functions")
        if st.button("🔄 Sync Products from SQL Server", use_container_width=True):
            st.session_state.show_sync = True
            st.rerun()
        
        # Show "List of Accounts" button for Admin Level 2 or Super Admin (Level 0)
        if admin_level in (0, 2):
            st.markdown("---")
            if st.button("📋 List of Accounts", use_container_width=True):
                st.session_state.show_accounts_dialog = True
                st.rerun()

        # Show "Notification Management" for Super Admin only (Admin Level 0)
        if admin_level == 0:
            st.markdown("---")
            if st.button("🔔 Notification Management", use_container_width=True):
                st.session_state.show_notification_management_dialog = True
                st.rerun()

        # Show "Manage Users" and "Manage Products" for Admin Level 1 Ethical or Admin / Finance Staff (excluding view-only)
        # Allow Admin Level 2 to also access these functions if they are not view-only
        # Fallback: Handle both old "Finance Staff" and new "Admin / Finance Staff" role names; normalize_role for old Level 1 names
        user_role = normalize_role(st.session_state.get('user_role', ''))
        is_finance_staff = user_role in ('Admin / Finance Staff', 'Finance Staff', 'Admin Level 0', 'Admin Level 1 Ethical', 'Admin Level 2', 'Ethical Staff Level 1', 'Finance Staff Level 2')
        if (admin_level in [1, 2] or is_finance_staff) and not view_only:
            st.markdown("---")
            if st.button("👥 Manage Users", use_container_width=True):
                # Reset other dialog states to prevent conflicts
                st.session_state.show_manage_products_dialog = False
                st.session_state.show_manage_users_dialog = True
                st.rerun()
            
            # Temporarily disabled - fixing dialog state management issue
            # TODO: Re-enable after dialog state management is fully tested
            st.button("📦 Manage Products", use_container_width=True, disabled=True, help="Temporarily disabled - fixing dialog state management")
    
    # Show notification management dialog if triggered (Super Admin only)
    if st.session_state.get('show_notification_management_dialog', False) and admin_level == 0:
        notification_management_dialog()
    
    # Show accounts dialog if triggered (Admin Level 2 or Super Admin)
    if st.session_state.get('show_accounts_dialog', False) and admin_level in (0, 2):
        accounts_dialog()
    
    # Show add account dialog if triggered (Admin Level 2 or Super Admin)
    if st.session_state.get('show_add_account_dialog', False) and admin_level in (0, 2):
        add_account_dialog()

    # Dialog state management - ensure only one dialog can be open at a time
    # Reset dialog states if multiple are set (shouldn't happen, but safety check)
    dialog_states = [
        st.session_state.get('show_manage_users_dialog', False),
        st.session_state.get('show_manage_products_dialog', False),
        st.session_state.get('show_accounts_dialog', False),
        st.session_state.get('show_add_account_dialog', False),
        st.session_state.get('show_notification_management_dialog', False)
    ]
    active_dialogs = sum(dialog_states)
    
    # If more than one dialog state is True, reset all except the first one found
    if active_dialogs > 1:
        if st.session_state.get('show_manage_users_dialog', False):
            st.session_state.show_manage_products_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
            st.session_state.show_notification_management_dialog = False
        elif st.session_state.get('show_manage_products_dialog', False):
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
            st.session_state.show_notification_management_dialog = False
    
    # Show manage users dialog if triggered
    if st.session_state.get('show_manage_users_dialog', False):
        try:
            # Ensure only this dialog is open
            st.session_state.show_manage_products_dialog = False
            manage_users_dialog()
        except Exception as e:
            # If dialog fails, reset state
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_manage_products_dialog = False
            if "Only one dialog" not in str(e):
                st.error(f"Error opening dialog: {e}")
    
    # Show manage products dialog if triggered (currently disabled via button)
    if st.session_state.get('show_manage_products_dialog', False):
        try:
            # Ensure only this dialog is open
            st.session_state.show_manage_users_dialog = False
            manage_products_dialog()
        except Exception as e:
            # If dialog fails, reset state
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_manage_products_dialog = False
            if "Only one dialog" not in str(e):
                st.error(f"Error opening dialog: {e}")
    
    # Get admin level
    admin_level = st.session_state.get('admin_level')
    admin_level_display = " (Super Admin)" if admin_level == 0 else (f" (Level {admin_level})" if admin_level else "")
    # Welcome banner - show logged-in user in main content
    _admin_uname = st.session_state.get('username', '') or ''
    if _admin_uname:
        st.caption(f"👋 Logged in as: **{_admin_uname}**")
    if view_only:
        st.info("🔒 View-only mode: approvals and edits are disabled.")
    
    # Main Content - Tabs (Pending Booking Request visible only for Super Admin and Admin Level 2)
    can_see_br_tab = admin_level in (0, 2)
    if can_see_br_tab:
        tab_pending_orders, tab_br, tab_all_orders, tab_approval, tab_so = st.tabs(["📋 All Pending Orders Review", "📋 Pending Booking Request", "📊 All Orders", "📜 Approval History", "📊 SO History"])
    else:
        tab_pending_orders, tab_all_orders, tab_approval, tab_so = st.tabs(["📋 All Pending Orders Review", "📊 All Orders", "📜 Approval History", "📊 SO History"])
    
    with tab_pending_orders:
        st.header(f"All Pending Orders - Review & Approve{admin_level_display}")
        orders_df = load_orders()
        
        if orders_df.empty:
            st.info("No orders found.")
        else:
            # Ensure approval columns exist (backward compatibility)
            if 'ApprovedByLevel1' not in orders_df.columns:
                orders_df['ApprovedByLevel1'] = ''
            if 'ApprovedDateLevel1' not in orders_df.columns:
                orders_df['ApprovedDateLevel1'] = ''
            if 'ApprovedByLevel2' not in orders_df.columns:
                orders_df['ApprovedByLevel2'] = ''
            if 'ApprovedDateLevel2' not in orders_df.columns:
                orders_df['ApprovedDateLevel2'] = ''
            # Fill NaN values
            orders_df['ApprovedByLevel1'] = orders_df['ApprovedByLevel1'].fillna('')
            orders_df['ApprovedDateLevel1'] = orders_df['ApprovedDateLevel1'].fillna('')
            orders_df['ApprovedByLevel2'] = orders_df['ApprovedByLevel2'].fillna('')
            orders_df['ApprovedDateLevel2'] = orders_df['ApprovedDateLevel2'].fillna('')
            
            # Filter pending orders based on admin level
            status_str = orders_df['Status'].fillna('').astype(str)
            if admin_level == 1:
                # Admin Level 1 Ethical sees orders that are Pending for Approval 1 (Contract and ex-SGF only)
                # TRADE/Dispensing/Distribution have ApprovedByLevel1 = 'SYSTEM' and skip Level 1
                # Also show "Pending for SGF" so they can see status, but can't approve until SGF approves
                pending_orders = orders_df[
                    ((orders_df['Status'].isin(['Pending', 'Pending for Approval 1']) | status_str.str.startswith('Pending for Approval 1')) & 
                     (orders_df['ApprovedByLevel1'] == '') &
                     (orders_df['ApprovedByLevel1'] != 'SYSTEM')) |
                    (orders_df['Status'] == 'Pending for SGF')
                ].copy()
            elif admin_level == 2:
                # Admin Level 2 sees orders that have been approved by Level 1 (or SYSTEM for TRADE) but not yet by Level 2
                pending_orders = orders_df[
                    (status_str.str.startswith('Pending for Approval 2') | (orders_df['Status'] == 'Pending')) & 
                    (orders_df['ApprovedByLevel1'] != '') &
                    (orders_df['ApprovedByLevel2'] == '')
                ].copy()
            elif admin_level == 0:
                # Super Admin: show ALL pending orders (both L1 and L2, including Pending for SGF)
                pending_orders = orders_df[
                    (orders_df['Status'].isin(['Pending', 'Pending for Approval 1', 'Pending for Approval 2']) | 
                     status_str.str.startswith('Pending for Approval 1') | status_str.str.startswith('Pending for Approval 2')) |
                    (orders_df['Status'] == 'Pending for SGF')
                ].copy()
            else:
                # Fallback for users without admin level (old admin accounts)
                pending_orders = orders_df[
                    orders_df['Status'].isin(['Pending', 'Pending for Approval 1', 'Pending for Approval 2']) | 
                    status_str.str.startswith('Pending for Approval 1') | status_str.str.startswith('Pending for Approval 2')
                ].copy()
            
            if pending_orders.empty:
                st.success("No pending orders. All orders have been reviewed.")
            else:
                # Sort by OrderDate
                pending_orders = pending_orders.sort_values('OrderDate', ascending=True)
                
                for idx, row in pending_orders.iterrows():
                    order_id = row['OrderID']
                    created_date = row.get('OrderDate', 'N/A')
                    if created_date and str(created_date) != 'N/A':
                        created_date = str(created_date)[:19]
                    created_by = row.get('CreatedBy', 'N/A')
                    status = row.get('Status', 'N/A')
                    expander_label = f"Order {order_id} | Created Date: {created_date} | Created by: {created_by} | Status: {status}"
                    
                    with st.expander(expander_label, expanded=False):
                        # Show approval status
                        approved_by_l1 = row.get('ApprovedByLevel1', '')
                        approved_date_l1 = row.get('ApprovedDateLevel1', '')
                        approved_by_l2 = row.get('ApprovedByLevel2', '')
                        approved_date_l2 = row.get('ApprovedDateLevel2', '')
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.markdown(f"**Client:** {row['ClientName']}")
                            st.markdown(f"**Name:** {row['RepName']} ({row['RepCode']})")
                            st.markdown(f"**Date:** {row['OrderDate']}")
                            st.markdown(f"**Total Amount:** {float(row.get('TotalAmount', 0)):.2f}")
                            # Show SGF status if pending for SGF
                            if row['Status'] == 'Pending for SGF':
                                approved_by_sgf = row.get('ApprovedBySGF', '')
                                if approved_by_sgf:
                                    st.info(f"✅ Approved by SGF: {approved_by_sgf}")
                                else:
                                    st.warning("⏳ Waiting for SGF Manager approval - Cannot approve until SGF approves")
                            if approved_by_l1:
                                if approved_by_l1 == 'SYSTEM':
                                    st.info(f"✅ Auto-approved by System (skips Level 1)")
                                else:
                                    st.info(f"✅ Approved by Level 1: {approved_by_l1} ({approved_date_l1})")
                        
                        with col2:
                            st.markdown(f"**Mobile:** {row['ClientMobile']}")
                            st.markdown(f"**Payment Terms:** {row.get('PaymentTerms', 'N/A')}")
                            st.markdown(f"**Delivery Date:** {row.get('DeliveryDate', 'N/A')}")
                        
                        with col3:
                            # Action buttons
                            if view_only:
                                st.caption("View-only user: approvals are disabled.")
                            else:
                                # Disable approval if status is "Pending for SGF" and not yet approved by SGF
                                can_approve = row['Status'] != 'Pending for SGF' or row.get('ApprovedBySGF', '') != ''
                                
                                col_approve, col_disapprove = st.columns(2)
                                with col_approve:
                                    if st.button("✅ Approve", key=f"approve_{row['OrderID']}", type="primary", disabled=not can_approve):
                                        orders_df = load_orders()  # Reload to get latest data
                                        order_idx = orders_df[orders_df['OrderID'] == row['OrderID']].index
                                        if len(order_idx) > 0:
                                            # Check remaining items
                                            cart_items_str = orders_df.at[order_idx[0], 'CartItems']
                                            disapproved_items_str = orders_df.at[order_idx[0], 'DisapprovedItems'] if 'DisapprovedItems' in orders_df.columns else '[]'
                                            cart_items = safe_parse_cart_items(cart_items_str)
                                            try:
                                                disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
                                            except (ValueError, SyntaxError):
                                                disapproved_items = []
                                            
                                            # Get disapproved indices
                                            disapproved_indices = [dis_item.get('item_index', -1) for dis_item in disapproved_items if 'item_index' in dis_item]
                                            remaining_items = [item for idx, item in enumerate(cart_items) if idx not in disapproved_indices]
                                            
                                            if len(remaining_items) == 0:
                                                st.error("Cannot approve order: All items have been removed/disapproved. At least one item must remain.")
                                            else:
                                                disapproved_count = len(disapproved_items)
                                                
                                                if admin_level == 1:
                                                    # Level 1 approval - mark as approved by Level 1, still pending for Level 2
                                                    orders_df.at[order_idx[0], 'ApprovedByLevel1'] = st.session_state.username
                                                    orders_df.at[order_idx[0], 'ApprovedDateLevel1'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                    if disapproved_count > 0:
                                                        orders_df.at[order_idx[0], 'Status'] = f'Pending for Approval 2 but {disapproved_count} Item(s) removed/disapproved'
                                                    else:
                                                        orders_df.at[order_idx[0], 'Status'] = 'Pending for Approval 2'  # Still pending for Level 2
                                                    if save_orders(orders_df):
                                                        # Send email notifications
                                                        try:
                                                            # Notify Sales Rep/TSR about Level 1 approval
                                                            order_row = orders_df.iloc[order_idx[0]]
                                                            order_dict = order_row.to_dict()
                                                            status_msg = f"Approved by Level 1" + (f" ({disapproved_count} item(s) removed/disapproved)" if disapproved_count > 0 else "")
                                                            send_order_notification_to_rep(row['OrderID'], order_dict, 
                                                                                          status_msg, 
                                                                                          notification_type="approved")
                                                            
                                                            # Notify related users about Level 1 approval
                                                            send_notification_to_related_users(row['OrderID'], order_dict, 
                                                                                               status_msg, 
                                                                                               notification_type="approved")
                                                            
                                                            # Notify Admin Level 2 about new pending approval
                                                            send_approval_notification_to_admin(row['OrderID'], order_dict, admin_level=2)
                                                            send_approval_notification(admin_level=2)
                                                        except Exception as e:
                                                            # Don't show error to user, just log it
                                                            print(f"Error sending notification email: {e}")
                                                        
                                                        if disapproved_count > 0:
                                                            st.success(f"Order {row['OrderID']} approved by Level 1! {disapproved_count} item(s) removed/disapproved. Waiting for Level 2 approval.")
                                                        else:
                                                            st.success(f"Order {row['OrderID']} approved by Level 1! Waiting for Level 2 approval.")
                                                        st.rerun()
                                                elif admin_level == 2 or admin_level == 0:
                                                    # Level 2 approval - final approval; Super Admin (level 0) can also do full approval
                                                    # For Admin Level 2, apply any edited Notes/Remarks before final approval
                                                    if admin_level == 2:
                                                        _notes_key = f"l2_notes_{row['OrderID']}"
                                                        _remarks_key = f"l2_remarks_{row['OrderID']}"
                                                        new_notes = st.session_state.get(_notes_key, orders_df.at[order_idx[0], 'Notes'])
                                                        new_remarks = st.session_state.get(_remarks_key, orders_df.at[order_idx[0], 'Remarks'])
                                                        orders_df.at[order_idx[0], 'Notes'] = new_notes
                                                        orders_df.at[order_idx[0], 'Remarks'] = new_remarks
                                                    # Only set Level 1 approval if not already set (preserve SYSTEM for TRADE accounts)
                                                    current_l1_approval = orders_df.at[order_idx[0], 'ApprovedByLevel1']
                                                    if not current_l1_approval or current_l1_approval == '':
                                                        orders_df.at[order_idx[0], 'ApprovedByLevel1'] = st.session_state.username
                                                        orders_df.at[order_idx[0], 'ApprovedDateLevel1'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                    orders_df.at[order_idx[0], 'ApprovedByLevel2'] = st.session_state.username
                                                    orders_df.at[order_idx[0], 'ApprovedDateLevel2'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                    if disapproved_count > 0:
                                                        orders_df.at[order_idx[0], 'Status'] = f'Approved but {disapproved_count} Item(s) removed/disapproved, re-book the removed Items'
                                                    else:
                                                        orders_df.at[order_idx[0], 'Status'] = 'Approved'
                                                    orders_df.at[order_idx[0], 'ReviewedBy'] = st.session_state.username
                                                    orders_df.at[order_idx[0], 'ReviewedDate'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                                    
                                                    # Increment SGF_count if order was approved by SGF Manager
                                                    client_name = row.get('ClientName', '')
                                                    approved_by_sgf = orders_df.at[order_idx[0], 'ApprovedBySGF']
                                                    if approved_by_sgf and approved_by_sgf.strip() != '':
                                                        try:
                                                            increment_sgf_count(client_name)
                                                        except Exception as e:
                                                            print(f"Error incrementing SGF_count: {e}")
                                                    
                                                    if save_orders(orders_df):
                                                        # Save to SO_history as backup (final approved transactions)
                                                        try:
                                                            _approved_order = orders_df.iloc[order_idx[0]].copy()
                                                            _approved_date = _approved_order.get('ApprovedDateLevel2', '') or ''
                                                            _order_dict = _approved_order.fillna('').to_dict()
                                                            db.append_approved_order_to_so_history(_order_dict, _approved_date)
                                                        except Exception as _e:
                                                            print(f"Error saving to SO_history: {_e}")
                                                        # Send email notification to Sales Rep/TSR about final approval
                                                        try:
                                                            order_row = orders_df.iloc[order_idx[0]]
                                                            order_dict = order_row.to_dict()
                                                            status_msg = "Fully approved" + (f" ({disapproved_count} item(s) removed/disapproved)" if disapproved_count > 0 else "")
                                                            send_order_notification_to_rep(row['OrderID'], order_dict, 
                                                                                          status_msg, 
                                                                                          notification_type="approved")
                                                            
                                                            # Notify related users about final approval
                                                            send_notification_to_related_users(row['OrderID'], order_dict, 
                                                                                               status_msg, 
                                                                                               notification_type="approved")
                                                        except Exception as e:
                                                            print(f"Error sending notification email: {e}")
                                                        
                                                        if disapproved_count > 0:
                                                            st.success(f"Order {row['OrderID']} fully approved! {disapproved_count} item(s) removed/disapproved, re-book the removed items.")
                                                        else:
                                                            st.success(f"Order {row['OrderID']} fully approved!")
                                                        st.rerun()
                                
                                with col_disapprove:
                                    if st.button("❌ Disapprove", key=f"disapprove_{row['OrderID']}"):
                                        # Trigger disapproval dialog with reason input
                                        st.session_state.disapprove_order_id = row['OrderID']
                                        st.session_state.show_disapprove_dialog = True
                                        st.rerun()
                                
                                # Show "Unlock for Edit" for Admin Level 1 Ethical or Super Admin (Level 0)
                                if admin_level in (0, 1):
                                    if st.button("🔓 Unlock for Edit", key=f"unlock_{row['OrderID']}"):
                                        # Trigger unlock dialog with reason input
                                        st.session_state.unlock_order_id = row['OrderID']
                                        st.session_state.show_unlock_dialog = True
                                        st.rerun()
                                
                                # Re-send Notifications button (only visible for administrator or Admin role)
                                current_username = st.session_state.get('username', '')
                                current_role = st.session_state.get('user_role', '')
                                is_admin_or_administrator = (current_username == 'administrator') or (current_role == 'Admin') or (current_role == 'Admin Level 0')
                                
                                if is_admin_or_administrator:
                                    if st.button("📧 Re-send Notifications", key=f"resend_notif_{row['OrderID']}", help="Re-send email notification for this order"):
                                        with st.spinner("Sending notification..."):
                                            success, message = resend_notification_for_order(row['OrderID'])
                                        if success:
                                            st.success(message)
                                        else:
                                            st.warning(message)
                                        st.rerun()
                                
                                # Cancel Order (Super Admin only) - Manually Forced Cancel
                                if admin_level == 0:
                                    if st.button("🚫 Cancel Order", key=f"cancel_order_{row['OrderID']}", help="Cancel this order (Manually Forced Cancel). Super Admin only."):
                                        st.session_state.cancel_order_id = row['OrderID']
                                        st.session_state.show_cancel_order_dialog = True
                                        st.rerun()

                        # Admin Level 2: allow editing of Notes / Special Instructions and Remarks before final approval
                        if admin_level == 2 and not view_only:
                            st.markdown("---")
                            st.markdown("**📝 Edit Additional Information (Admin Level 2)**")
                            st.caption("Adjust Notes / Special Instructions and Remarks before final approval.")
                            notes_key = f"l2_notes_{order_id}"
                            remarks_key = f"l2_remarks_{order_id}"
                            if notes_key not in st.session_state:
                                st.session_state[notes_key] = row.get('Notes', '')
                            if remarks_key not in st.session_state:
                                st.session_state[remarks_key] = row.get('Remarks', '')
                            st.text_area(
                                "Notes / Special Instructions",
                                key=notes_key,
                                height=80,
                            )
                            st.text_area(
                                "Remarks",
                                key=remarks_key,
                                height=80,
                            )

                        # Order details expander
                        with st.expander("View Full Order Details"):
                            st.markdown(f"**Client Category:** {row.get('ClientDescription', 'N/A')}")
                            st.markdown(f"**Billing Address:** {row.get('BillingAddress', 'N/A')}")
                            st.markdown(f"**Shipping Address:** {row.get('ShippingAddress', 'N/A')}")
                            contact_person_1 = row.get('ContactPerson1', '')
                            contact_person_1_mobile = row.get('ContactPerson1Mobile', '')
                            contact_person_2 = row.get('ContactPerson2', '')
                            contact_person_2_mobile = row.get('ContactPerson2Mobile', '')
                            if contact_person_1 or contact_person_1_mobile:
                                st.markdown(f"**Contact Person 1:** {contact_person_1 if contact_person_1 else 'N/A'}")
                                st.markdown(f"**Contact Person 1 Mobile:** {contact_person_1_mobile if contact_person_1_mobile else 'N/A'}")
                            if contact_person_2 or contact_person_2_mobile:
                                st.markdown(f"**Contact Person 2:** {contact_person_2 if contact_person_2 else 'N/A'}")
                                st.markdown(f"**Contact Person 2 Mobile:** {contact_person_2_mobile if contact_person_2_mobile else 'N/A'}")
                            st.markdown(f"**Delivery Instructions:** {row.get('DeliveryTerms', 'N/A')}")
                            st.markdown(f"**Company:** {row.get('RepCompany', 'N/A')}")
                            st.markdown(f"**Dept/DSM District:** {row.get('RepDept', 'N/A')}")
                            st.markdown(f"**Area/PMR:** {row.get('RepArea', 'N/A')}")
                            if row.get('Notes'):
                                st.markdown(f"**Notes:** {row.get('Notes', 'N/A')}")
                            if row.get('Remarks'):
                                st.markdown(f"**Remarks:** {row.get('Remarks', 'N/A')}")
                            
                            # Display Attachments if any
                            attachments_str = row.get('Attachments', '')
                            if attachments_str:
                                st.markdown("---")
                                display_order_attachments(attachments_str)
                            
                            st.markdown("---")
                            
                            # Display Order Items with Remove/Disapprove buttons for Admin
                            cart_items_str = row.get('CartItems', '[]')
                            disapproved_items_str = row.get('DisapprovedItems', '[]')
                            try:
                                # Try to parse the cart items string
                                cart_items = safe_parse_cart_items(cart_items_str)
                                
                                # Parse disapproved items
                                try:
                                    disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
                                except (ValueError, SyntaxError):
                                    disapproved_items = []
                                
                                if cart_items and len(cart_items) > 0:
                                    display_cart_items_admin(row['OrderID'], cart_items, disapproved_items)
                                else:
                                    st.info("No items found in this order.")
                            except (ValueError, SyntaxError):
                                st.warning(f"Could not parse cart items: {cart_items_str}")
                                st.info("Cart items data may be in an unexpected format.")
                        
                        st.markdown("---")
    
    if can_see_br_tab:
        with tab_br:
            st.header("Pending Booking Request - Awaiting TSR to Complete")
            br_pending_df = db.get_all_booking_requests(status_filter='Pending')
            if br_pending_df.empty:
                st.success("No pending booking requests. All requests have been completed by TSR.")
            else:
                br_pending_df = br_pending_df.sort_values('created_date', ascending=True)
                for idx, row in br_pending_df.iterrows():
                    request_id = row.get('request_id', 'N/A')
                    created_date = row.get('created_date', 'N/A')
                    if created_date and str(created_date) != 'N/A':
                        created_date = str(created_date)[:19]
                    created_by = row.get('created_by', 'N/A')
                    status = row.get('status', 'N/A')
                    expander_label = f"Request {request_id} | Created Date: {created_date} | Created by: {created_by} | Status: {status}"
                    with st.expander(expander_label, expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"**Client:** {row.get('client_name', 'N/A')}")
                            st.markdown(f"**TSR:** {row.get('tsr_name', 'N/A')} ({row.get('tsr_code', 'N/A')})")
                            st.markdown(f"**Shipping Date:** {row.get('shipping_date', 'N/A')}")
                            cart_items_str = row.get('cart_items', '[]')
                            cart_items = safe_parse_cart_items(cart_items_str)
                            total_amount = sum(safe_float_convert(item.get('qty', 0)) * safe_float_convert(item.get('price', 0)) for item in cart_items)
                            st.markdown(f"**Total Amount:** {total_amount:.2f}")
                            st.info("⏳ Awaiting TSR to complete this booking request.")
                        with col2:
                            st.markdown(f"**Created Date:** {row.get('created_date', 'N/A')[:19] if row.get('created_date') else 'N/A'}")
                            st.markdown(f"**Special Instructions:** {row.get('special_instructions', 'N/A') or 'N/A'}")
                            st.markdown(f"**Remarks:** {row.get('remarks', 'N/A') or 'N/A'}")
                        with col3:
                            is_overdue = is_br_overdue(row.get('created_date'), 24)
                            auto_cancel_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            if is_overdue:
                                if st.button("⏱️ Auto-Cancel", key=f"br_autocancel_{request_id}", help="Auto-cancel this and all other requests over 24 hours"):
                                    old_br = db.get_pending_booking_requests_older_than_hours(24)
                                    cancelled = 0
                                    for _, r in old_br.iterrows():
                                        rid = r.get('request_id', '')
                                        if rid and db.update_booking_request_status(rid, 'Auto-Cancel', auto_cancel_date=auto_cancel_ts):
                                            cancelled += 1
                                    st.success(f"Auto-cancelled {cancelled} booking request(s) (24h exceeded).")
                                    st.rerun()
                            if st.button("🚫 Force Cancel", key=f"br_forcecancel_{request_id}", help="Manually cancel this booking request"):
                                if db.update_booking_request_status(request_id, 'Force-Cancel'):
                                    st.success(f"Booking request {request_id} force-cancelled.")
                                    st.rerun()
                                else:
                                    st.error("Failed to update status.")
                        with st.expander("View Full Request Details"):
                            st.markdown(f"**Client:** {row.get('client_name', 'N/A')}")
                            st.markdown(f"**TSR Code:** {row.get('tsr_code', 'N/A')}")
                            st.markdown(f"**TSR Name:** {row.get('tsr_name', 'N/A')}")
                            st.markdown(f"**Shipping Date:** {row.get('shipping_date', 'N/A')}")
                            st.markdown(f"**Special Instructions:** {row.get('special_instructions', 'N/A') or 'N/A'}")
                            st.markdown(f"**Remarks:** {row.get('remarks', 'N/A') or 'N/A'}")
                            st.markdown("---")
                            if cart_items and len(cart_items) > 0:
                                display_cart_items_with_images(cart_items)
                            else:
                                st.info("No items found in this request.")
                            br_attachments = get_booking_request_attachments(request_id)
                            if br_attachments:
                                st.markdown("---")
                                st.markdown("**Attachments:**")
                                for att_path in br_attachments:
                                    if os.path.exists(att_path):
                                        st.caption(os.path.basename(att_path))
            
            st.markdown("---")
            st.subheader("Auto Cancel Booking Request")
            br_all_df = db.get_all_booking_requests()
            br_auto_cancel_df = br_all_df[br_all_df['status'].isin(['Auto-Cancel', 'Force-Cancel', 'Cancelled by Creator'])] if not br_all_df.empty else pd.DataFrame()
            if br_auto_cancel_df.empty:
                st.success("No auto-cancelled, force-cancelled, or cancelled-by-creator booking requests.")
            else:
                br_auto_cancel_df = br_auto_cancel_df.sort_values('created_date', ascending=True)
                for idx, row in br_auto_cancel_df.iterrows():
                    request_id = row.get('request_id', 'N/A')
                    created_date = row.get('created_date', 'N/A')
                    if created_date and str(created_date) != 'N/A':
                        created_date = str(created_date)[:19]
                    created_by = row.get('created_by', 'N/A')
                    status = row.get('status', 'N/A')
                    expander_label = f"Request {request_id} | Created Date: {created_date} | Created by: {created_by} | Status: {status}"
                    with st.expander(expander_label, expanded=False):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        with col1:
                            st.markdown(f"**Client:** {row.get('client_name', 'N/A')}")
                            st.markdown(f"**TSR:** {row.get('tsr_name', 'N/A')} ({row.get('tsr_code', 'N/A')})")
                            st.markdown(f"**Shipping Date:** {row.get('shipping_date', 'N/A')}")
                            cart_items_str = row.get('cart_items', '[]')
                            cart_items = safe_parse_cart_items(cart_items_str)
                            total_amount = sum(safe_float_convert(item.get('qty', 0)) * safe_float_convert(item.get('price', 0)) for item in cart_items)
                            st.markdown(f"**Total Amount:** {total_amount:.2f}")
                            br_status = row.get('status', '')
                            if br_status == 'Force-Cancel':
                                st.warning("⚠️ Force-cancelled by admin.")
                            elif br_status == 'Cancelled by Creator':
                                st.warning("⚠️ Cancelled by creator (Sales Rep).")
                                cancel_reason = row.get('cancel_reason', '') or ''
                                if cancel_reason and str(cancel_reason).strip():
                                    st.caption(f"**Reason:** {cancel_reason}")
                            else:
                                auto_cancel_date = row.get('auto_cancel_date', '')[:19] if row.get('auto_cancel_date') else 'N/A'
                                st.warning(f"⚠️ Auto-cancelled after 24 hours ({auto_cancel_date})")
                        with col2:
                            st.markdown(f"**Created Date:** {row.get('created_date', 'N/A')[:19] if row.get('created_date') else 'N/A'}")
                            st.markdown(f"**Special Instructions:** {row.get('special_instructions', 'N/A') or 'N/A'}")
                            st.markdown(f"**Remarks:** {row.get('remarks', 'N/A') or 'N/A'}")
                            cancel_reason = row.get('cancel_reason', '') or ''
                            if cancel_reason and str(cancel_reason).strip():
                                st.markdown(f"**Reason for cancellation:** {cancel_reason}")
                        with col3:
                            st.caption("View-only. Request was cancelled (auto, force, or by creator).")
                        with st.expander("View Full Request Details"):
                            st.markdown(f"**Client:** {row.get('client_name', 'N/A')}")
                            st.markdown(f"**TSR Code:** {row.get('tsr_code', 'N/A')}")
                            st.markdown(f"**TSR Name:** {row.get('tsr_name', 'N/A')}")
                            st.markdown(f"**Shipping Date:** {row.get('shipping_date', 'N/A')}")
                            if br_status == 'Force-Cancel':
                                st.markdown("**Cancelled:** Force-cancelled by admin")
                            elif br_status == 'Cancelled by Creator':
                                st.markdown("**Cancelled:** Cancelled by creator (Sales Rep)")
                                if cancel_reason and str(cancel_reason).strip():
                                    st.markdown(f"**Reason for cancellation:** {cancel_reason}")
                            else:
                                auto_cancel_date = row.get('auto_cancel_date', '')[:19] if row.get('auto_cancel_date') else 'N/A'
                                st.markdown(f"**Auto-Cancelled At:** {auto_cancel_date}")
                            st.markdown(f"**Special Instructions:** {row.get('special_instructions', 'N/A') or 'N/A'}")
                            st.markdown(f"**Remarks:** {row.get('remarks', 'N/A') or 'N/A'}")
                            st.markdown("---")
                            if cart_items and len(cart_items) > 0:
                                display_cart_items_with_images(cart_items)
                            else:
                                st.info("No items found in this request.")
                            br_attachments = get_booking_request_attachments(request_id)
                            if br_attachments:
                                st.markdown("---")
                                st.markdown("**Attachments:**")
                                for att_path in br_attachments:
                                    if os.path.exists(att_path):
                                        st.caption(os.path.basename(att_path))
    
    with tab_all_orders:
        st.header("All Orders")
        orders_df = load_orders()
        
        if orders_df.empty:
            st.info("No orders found.")
        else:
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.text_input(
                    "Filter by Status",
                    value="",
                    placeholder="All (leave blank) or type keyword e.g. Pending, Approved, Disapproved",
                    key="finance_all_orders_status_filter"
                )
            with col2:
                date_from = st.date_input("From Date", value=pd.to_datetime(orders_df['OrderDate']).min().date() 
                                         if not orders_df.empty else datetime.now().date())
            with col3:
                date_to = st.date_input("To Date", value=datetime.now().date())
            
            # Reset dialog state if filters changed (not triggered by View Details button)
            # This prevents dialog from appearing when filters are changed
            current_date_from = str(date_from)
            current_date_to = str(date_to)
            _status_kw = str(status_filter or '').strip()
            current_status_filter = _status_kw if _status_kw else 'All'
            
            # Check if any filter has changed
            filters_changed = (
                st.session_state.get('last_date_from') != current_date_from or 
                st.session_state.get('last_date_to') != current_date_to or
                st.session_state.get('last_status_filter') != current_status_filter
            )
            
            if filters_changed:
                # Always reset dialog state when filters change
                st.session_state.show_order_details_dialog = False
                st.session_state.selected_order_id = None
                st.session_state.dialog_button_clicked = False
                # Update tracked filter values
                st.session_state.last_date_from = current_date_from
                st.session_state.last_date_to = current_date_to
                st.session_state.last_status_filter = current_status_filter
            
            # Apply filters
            filtered_orders = orders_df.copy()
            _status_kw = str(status_filter or '').strip()
            if _status_kw and _status_kw.lower() != 'all':
                if _status_kw.lower() == 'approve' or _status_kw.lower() == 'approved':
                    # Special case: searching for 'approve' should not match 'disapprove'
                    # We use a regex that matches 'approve' but ignores 'disapprove'
                    filtered_orders = filtered_orders[
                        filtered_orders['Status'].fillna('').astype(str).str.contains(r'(?i)\bapproved?\b', regex=True) & 
                        ~filtered_orders['Status'].fillna('').astype(str).str.contains(r'(?i)disapproved?', regex=True)
                    ]
                else:
                    filtered_orders = filtered_orders[
                        filtered_orders['Status'].fillna('').astype(str).str.contains(_status_kw, case=False, na=False)
                    ]
            
            filtered_orders['OrderDate_dt'] = pd.to_datetime(filtered_orders['OrderDate'])
            filtered_orders = filtered_orders[
                (filtered_orders['OrderDate_dt'].dt.date >= date_from) &
                (filtered_orders['OrderDate_dt'].dt.date <= date_to)
            ]
            # Sort by ReviewedDate DESC (latest first); N/A at end
            if 'ReviewedDate' in filtered_orders.columns:
                filtered_orders = filtered_orders.sort_values('ReviewedDate', ascending=False, na_position='last').reset_index(drop=True)
            
            # Display summary
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Orders", len(filtered_orders))
            with col2:
                st.metric("Total Amount", f"{filtered_orders['TotalAmount'].sum():,.2f}")
            
            st.markdown("---")
            
            # Ensure print status columns exist in the dataframe
            if 'Printed' not in filtered_orders.columns:
                filtered_orders['Printed'] = ''
            if 'PrintedDate' not in filtered_orders.columns:
                filtered_orders['PrintedDate'] = ''
            if 'PrintedTime' not in filtered_orders.columns:
                filtered_orders['PrintedTime'] = ''
            
            # Display orders table with View Details buttons
            display_cols = ['OrderID', 'OrderDate', 'Status', 'ClientName', 'RepName', 
                          'RepCode', 'TotalAmount', 'ReviewedBy', 'ReviewedDate']
            available_cols = [col for col in display_cols if col in filtered_orders.columns]
            
            # Create a cleaner table layout with View Details buttons
            col_title, col_download = st.columns([3, 1])
            with col_title:
                st.markdown("### Orders Table")
            with col_download:
                # Prepare CSV data for download (same order as table: ReviewedDate DESC)
                filtered_sorted = filtered_orders.copy()
                csv_data = prepare_orders_csv_data(filtered_sorted)
                if not csv_data.empty:
                    csv_string = csv_data.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv_string,
                        file_name=f"orders_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        help="Download complete order details including all products"
                    )
                else:
                    st.download_button(
                        label="📥 Download CSV",
                        data="",
                        file_name="orders_export.csv",
                        mime="text/csv",
                        use_container_width=True,
                        disabled=True,
                        help="No data to export"
                    )
            
            # Create table with buttons - using a custom layout
            # Calculate column widths based on number of columns
            num_data_cols = len(available_cols)
            col_widths = [1] * num_data_cols + [0.8]  # Data columns + Actions column
            
            # Create header row with smaller font
            header_cols = st.columns(col_widths)
            for i, col_name in enumerate(available_cols):
                with header_cols[i]:
                    st.markdown(f'<div style="font-size: 0.9rem; font-weight: bold;">{col_name}</div>', unsafe_allow_html=True)
            with header_cols[-1]:
                st.markdown('<div style="font-size: 0.9rem; font-weight: bold;">Actions</div>', unsafe_allow_html=True)
            
            # Display each order as a table row with container
            for idx, row in filtered_orders.iterrows():
                with st.container(border=True):
                    row_cols = st.columns(col_widths)
                    
                    # Display data in each column with smaller font
                    for i, col_name in enumerate(available_cols):
                        with row_cols[i]:
                            value = row.get(col_name, 'N/A')
                            if col_name == 'TotalAmount':
                                display_val = f"{float(value):.2f}" if pd.notna(value) else 'N/A'
                                st.markdown(f'<div style="font-size: 0.85rem;">{display_val}</div>', unsafe_allow_html=True)
                            elif col_name == 'Status':
                                # Format status display - show Level 2 for TRADE accounts
                                display_status = format_order_status_display(row)
                                status_text = str(display_status) if pd.notna(value) else 'N/A'
                                printed = row.get('Printed', '')
                                if printed == 'Yes':
                                    printed_date = row.get('PrintedDate', '')
                                    printed_time = row.get('PrintedTime', '')
                                    if printed_date and printed_time:
                                        status_text += f" (Printed: {printed_date} {printed_time})"
                                st.markdown(f'<div style="font-size: 0.85rem;">{status_text}</div>', unsafe_allow_html=True)
                            else:
                                # Truncate long values for better display
                                display_value = str(value)[:50] + "..." if pd.notna(value) and len(str(value)) > 50 else (value if pd.notna(value) else 'N/A')
                                st.markdown(f'<div style="font-size: 0.85rem;">{display_value}</div>', unsafe_allow_html=True)
                    
                    # View Details and Print buttons in the last column
                    with row_cols[-1]:
                        # Create a fixed container for buttons - Gemini's solution
                        # Check for 'Approved' in status (handles the timestamped status)
                        status = row.get('Status', '')
                        
                        # Using [1, 1] ensures both slots take equal space even if one is empty
                        btn_col1, btn_col2 = st.columns([1, 1])
                        
                        with btn_col1:
                            if st.button("🔍", key=f"view_details_{row['OrderID']}_{idx}", use_container_width=True, help="View Order Details"):
                                st.session_state.selected_order_id = row['OrderID']
                                st.session_state.show_order_details_dialog = True
                                st.session_state.dialog_button_clicked = True
                                st.rerun()
                        
                        with btn_col2:
                            if 'Approved' in status:
                                if st.button("🖨️", key=f"print_{row['OrderID']}_{idx}", use_container_width=True, help="Print the Sales Order"):
                                    # Update order with print status then open print view
                                    orders_df = load_orders()
                                    order_idx = orders_df[orders_df['OrderID'] == row['OrderID']].index
                                    if len(order_idx) > 0:
                                        orders_df.at[order_idx[0], 'Printed'] = 'Yes'
                                        orders_df.at[order_idx[0], 'PrintedDate'] = datetime.now().strftime('%Y-%m-%d')
                                        orders_df.at[order_idx[0], 'PrintedTime'] = datetime.now().strftime('%H:%M:%S')
                                        if save_orders(orders_df):
                                            st.session_state.print_view_order_id = row['OrderID']
                                            st.session_state.show_print_view = True
                                            st.rerun()
                                        else:
                                            st.error("Error saving print status.")
                            else:
                                # This keeps the spacing consistent for non-approved rows
                                st.empty()
                
                # Add a subtle separator between rows (optional - can be removed for cleaner look)
                # st.markdown("---")
    
    with tab_approval:
        st.header(f"Approval History{admin_level_display}")
        orders_df = load_orders()
        
        if orders_df.empty:
            st.info("No orders found.")
        else:
            # Ensure approval columns exist (backward compatibility)
            if 'ApprovedByLevel1' not in orders_df.columns:
                orders_df['ApprovedByLevel1'] = ''
            if 'ApprovedDateLevel1' not in orders_df.columns:
                orders_df['ApprovedDateLevel1'] = ''
            if 'ApprovedByLevel2' not in orders_df.columns:
                orders_df['ApprovedByLevel2'] = ''
            if 'ApprovedDateLevel2' not in orders_df.columns:
                orders_df['ApprovedDateLevel2'] = ''
            # Fill NaN values
            orders_df['ApprovedByLevel1'] = orders_df['ApprovedByLevel1'].fillna('')
            orders_df['ApprovedDateLevel1'] = orders_df['ApprovedDateLevel1'].fillna('')
            orders_df['ApprovedByLevel2'] = orders_df['ApprovedByLevel2'].fillna('')
            orders_df['ApprovedDateLevel2'] = orders_df['ApprovedDateLevel2'].fillna('')
            
            # Filter orders based on admin level
            if admin_level == 1:
                # Show orders approved/disapproved/unlocked by Level 1
                history_orders = orders_df[
                    (orders_df['ApprovedByLevel1'] == st.session_state.username) |
                    (orders_df['Status'].str.contains('Disapproved', na=False)) |
                    (orders_df['Status'].str.contains('Unlocked', na=False))
                ].copy()
            elif admin_level == 2:
                # Show orders approved/disapproved by Level 2
                history_orders = orders_df[
                    (orders_df['ApprovedByLevel2'] == st.session_state.username) |
                    (orders_df['Status'].str.contains('Disapproved', na=False))
                ].copy()
            else:
                # Fallback for users without admin level
                history_orders = orders_df[
                    (orders_df['ReviewedBy'] == st.session_state.username) |
                    (orders_df['Status'].str.contains('Disapproved', na=False)) |
                    (orders_df['Status'].str.contains('Unlocked', na=False))
                ].copy()
            
            if history_orders.empty:
                st.info("No approval history found.")
            else:
                # Sort by OrderDate descending
                history_orders = history_orders.sort_values('OrderDate', ascending=False)
                
                for idx, row in history_orders.iterrows():
                    # Check for disapproved items to update expander caption
                    disapproved_items_str = row.get('DisapprovedItems', '[]')
                    try:
                        disapproved_items = ast.literal_eval(disapproved_items_str) if isinstance(disapproved_items_str, str) else disapproved_items_str
                    except (ValueError, SyntaxError):
                        disapproved_items = []
                    
                    disapproved_count = len(disapproved_items) if disapproved_items else 0
                    status = row['Status']
                    # Format status display - show Level 2 for TRADE accounts
                    display_status = format_order_status_display(row)
                    
                    # Build expander caption with disapproved items info
                    if disapproved_count > 0:
                        # Check if status already includes disapproved info
                        if 'removed/disapproved' not in status.lower() and 'disapproved' not in status.lower():
                            expander_caption = f"Order {row['OrderID']} - {display_status} with {disapproved_count} removed/disapproved item(s) - {row['OrderDate']}"
                        else:
                            expander_caption = f"Order {row['OrderID']} - {display_status} - {row['OrderDate']}"
                    else:
                        expander_caption = f"Order {row['OrderID']} - {display_status} - {row['OrderDate']}"
                    
                    with st.expander(expander_caption):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Client:** {row['ClientName']}")
                            st.markdown(f"**Date:** {row['OrderDate']}")
                            # Format status display - show Level 2 for TRADE accounts
                            display_status = format_order_status_display(row)
                            st.markdown(f"**Status:** {display_status}")
                            st.markdown(f"**Total Amount:** {float(row.get('TotalAmount', 0)):.2f}")
                            
                            # Show approval status
                            approved_by_l1 = row.get('ApprovedByLevel1', '')
                            approved_date_l1 = row.get('ApprovedDateLevel1', '')
                            approved_by_l2 = row.get('ApprovedByLevel2', '')
                            approved_date_l2 = row.get('ApprovedDateLevel2', '')
                            
                            if approved_by_l1:
                                st.success(f"✅ Approved by Level 1: {approved_by_l1} ({approved_date_l1})")
                            if approved_by_l2:
                                st.success(f"✅ Approved by Level 2: {approved_by_l2} ({approved_date_l2})")
                        
                        with col2:
                            st.markdown(f"**Name:** {row['RepName']} ({row['RepCode']})")
                            st.markdown(f"**Mobile:** {row['ClientMobile']}")
                            reviewed_by = row.get('ReviewedBy', '')
                            reviewed_date = row.get('ReviewedDate', '')
                            if reviewed_by:
                                st.markdown(f"**Reviewed By:** {reviewed_by}")
                            if reviewed_date:
                                st.markdown(f"**Reviewed Date:** {reviewed_date}")
                        
                        st.markdown("---")
                        
                        # View Details button
                        if st.button("🔍 View Details", key=f"history_view_{row['OrderID']}_{idx}", use_container_width=True):
                            st.session_state.selected_order_id = row['OrderID']
                            st.session_state.show_order_details_dialog = True
                            st.session_state.dialog_button_clicked = True
                            st.rerun()

    with tab_so:
        st.header("SO History")
        st.caption("Consolidated view: App orders (by product line) + SO History from CSV. Backup of final approved transactions.")
        consolidated_df = get_consolidated_so_history()
        if consolidated_df.empty:
            st.info("No SO history data. Run load_so_history_from_csv.py to import the CSV into SO_history table.")
        else:
            st.dataframe(consolidated_df, use_container_width=True, hide_index=True)

# SGF Manager Interface
def sgf_manager_interface():
    """SGF Manager main interface - limited access to SGF-eligible accounts only"""
    st.title("🔐 SGF Manager - Order Review & Approval")
    
    # Show order details dialog if triggered
    dialog_triggered = st.session_state.get('show_order_details_dialog', False)
    selected_order_id = st.session_state.get('selected_order_id')
    button_clicked = st.session_state.get('dialog_button_clicked', False)
    
    if dialog_triggered and selected_order_id and button_clicked:
        orders_df = load_orders()
        order_details_dialog(st.session_state.selected_order_id, orders_df)
        st.session_state.dialog_button_clicked = False
    
    # Show disapprove dialog if triggered
    if st.session_state.get('show_disapprove_dialog', False) and st.session_state.get('disapprove_order_id'):
        orders_df = load_orders()
        disapprove_order_dialog(st.session_state.disapprove_order_id, orders_df)
    
    with st.sidebar:
        display_logo(width=200)
        # Welcome message - show logged-in user
        _uname = st.session_state.get('username', '') or ''
        if _uname:
            st.success(f"👋 Welcome, **{_uname}**")
        st.markdown("---")
        st.header("Navigation")
        if st.button("🔓 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.username = None
            # Reset all dialog states on logout
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_manage_products_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
            st.session_state.show_notification_management_dialog = False
            st.session_state.show_submit_order_dialog = False
            st.session_state.show_order_details_dialog = False
            st.rerun()
    
    # Welcome banner - show logged-in user in main content
    _sgf_uname = st.session_state.get('username', '') or ''
    if _sgf_uname:
        st.caption(f"👋 Logged in as: **{_sgf_uname}**")
    st.info("🔒 SGF Manager Access: You can only view and approve orders for accounts where SGF = True and SGF_count < 3.")
    
    # Main Content - Pending SGF Orders
    st.header("Pending SGF Orders - Review & Approve")
    orders_df = load_orders()
    
    if orders_df.empty:
        st.info("No orders found.")
    else:
        # Ensure SGF approval columns exist
        if 'ApprovedBySGF' not in orders_df.columns:
            orders_df['ApprovedBySGF'] = ''
        if 'ApprovedDateSGF' not in orders_df.columns:
            orders_df['ApprovedDateSGF'] = ''
        orders_df['ApprovedBySGF'] = orders_df['ApprovedBySGF'].fillna('')
        orders_df['ApprovedDateSGF'] = orders_df['ApprovedDateSGF'].fillna('')
        
        # Filter for orders pending SGF approval
        pending_sgf_orders = orders_df[
            (orders_df['Status'] == 'Pending for SGF') & 
            (orders_df['ApprovedBySGF'] == '')
        ].copy()
        
        # Filter to only show orders for SGF-eligible accounts
        eligible_orders = []
        for idx, row in pending_sgf_orders.iterrows():
            client_name = row.get('ClientName', '')
            if check_sgf_eligibility(client_name):
                eligible_orders.append(idx)
        
        pending_sgf_orders = pending_sgf_orders.loc[eligible_orders].copy()
        
        if pending_sgf_orders.empty:
            st.success("No pending SGF orders. All orders have been reviewed.")
        else:
            # Sort by OrderDate
            pending_sgf_orders = pending_sgf_orders.sort_values('OrderDate', ascending=True)
            
            for idx, row in pending_sgf_orders.iterrows():
                with st.container():
                    st.markdown(f"### Order {row['OrderID']}")
                    
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"**Client:** {row['ClientName']}")
                        st.markdown(f"**Name:** {row['RepName']} ({row['RepCode']})")
                        st.markdown(f"**Date:** {row['OrderDate']}")
                        st.markdown(f"**Total Amount:** {float(row.get('TotalAmount', 0)):.2f}")
                        st.warning("⏳ Pending SGF Approval")
                    
                    with col2:
                        st.markdown(f"**Mobile:** {row['ClientMobile']}")
                        st.markdown(f"**Payment Terms:** {row.get('PaymentTerms', 'N/A')}")
                        st.markdown(f"**Delivery Date:** {row.get('DeliveryDate', 'N/A')}")
                    
                    with col3:
                        # Action buttons
                        col_approve, col_disapprove = st.columns(2)
                        with col_approve:
                            if st.button("✅ Approve", key=f"sgf_approve_{row['OrderID']}", type="primary"):
                                orders_df = load_orders()
                                order_idx = orders_df[orders_df['OrderID'] == row['OrderID']].index
                                if len(order_idx) > 0:
                                    # Mark as approved by SGF, change status to Pending for Admin Level 1 Ethical
                                    orders_df.at[order_idx[0], 'ApprovedBySGF'] = st.session_state.username
                                    orders_df.at[order_idx[0], 'ApprovedDateSGF'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    orders_df.at[order_idx[0], 'Status'] = 'Pending for Approval 1'
                                    
                                    if save_orders(orders_df):
                                        # Send email notification to Admin Level 1 Ethical
                                        try:
                                            send_approval_notification(admin_level=1)
                                        except Exception as e:
                                            print(f"Error sending notification email: {e}")
                                        
                                        st.success(f"Order {row['OrderID']} approved by SGF Manager! Proceeding to Admin Level 1 Ethical.")
                                        st.rerun()
                        
                        with col_disapprove:
                            if st.button("❌ Disapprove", key=f"sgf_disapprove_{row['OrderID']}"):
                                st.session_state.disapprove_order_id = row['OrderID']
                                st.session_state.show_disapprove_dialog = True
                                st.rerun()
                        
                        # Re-send Notifications button (only visible for administrator or Admin Level 0)
                        current_username = st.session_state.get('username', '')
                        current_role = st.session_state.get('user_role', '')
                        is_admin_or_administrator = (current_username == 'administrator') or (current_role == 'Admin') or (current_role == 'Admin Level 0')
                        
                        if is_admin_or_administrator:
                            if st.button("📧 Re-send Notifications", key=f"sgf_resend_notif_{row['OrderID']}", use_container_width=True, help="Re-send email notification for this order"):
                                with st.spinner("Sending notification..."):
                                    success, message = resend_notification_for_order(row['OrderID'])
                                if success:
                                    st.success(message)
                                else:
                                    st.warning(message)
                                st.rerun()
                    
                    # Order details expander
                    with st.expander("View Full Order Details"):
                        st.markdown(f"**Client Category:** {row.get('ClientDescription', 'N/A')}")
                        st.markdown(f"**Billing Address:** {row.get('BillingAddress', 'N/A')}")
                        st.markdown(f"**Shipping Address:** {row.get('ShippingAddress', 'N/A')}")
                        contact_person_1 = row.get('ContactPerson1', '')
                        contact_person_1_mobile = row.get('ContactPerson1Mobile', '')
                        contact_person_2 = row.get('ContactPerson2', '')
                        contact_person_2_mobile = row.get('ContactPerson2Mobile', '')
                        if contact_person_1 or contact_person_1_mobile:
                            st.markdown(f"**Contact Person 1:** {contact_person_1 if contact_person_1 else 'N/A'}")
                            st.markdown(f"**Contact Person 1 Mobile:** {contact_person_1_mobile if contact_person_1_mobile else 'N/A'}")
                        if contact_person_2 or contact_person_2_mobile:
                            st.markdown(f"**Contact Person 2:** {contact_person_2 if contact_person_2 else 'N/A'}")
                            st.markdown(f"**Contact Person 2 Mobile:** {contact_person_2_mobile if contact_person_2_mobile else 'N/A'}")
                        st.markdown(f"**Delivery Instructions:** {row.get('DeliveryTerms', 'N/A')}")
                        st.markdown(f"**Company:** {row.get('RepCompany', 'N/A')}")
                        st.markdown(f"**Dept/DSM District:** {row.get('RepDept', 'N/A')}")
                        st.markdown(f"**Area/PMR:** {row.get('RepArea', 'N/A')}")
                        if row.get('Notes'):
                            st.markdown(f"**Notes:** {row.get('Notes', 'N/A')}")
                        if row.get('Remarks'):
                            st.markdown(f"**Remarks:** {row.get('Remarks', 'N/A')}")
                        
                        # Display Attachments if any
                        attachments_str = row.get('Attachments', '')
                        if attachments_str:
                            st.markdown("---")
                            display_order_attachments(attachments_str)
                        
                        st.markdown("---")
                        
                        # Display Order Items
                        cart_items_str = row.get('CartItems', '[]')
                        try:
                            cart_items = safe_parse_cart_items(cart_items_str)
                            if cart_items and len(cart_items) > 0:
                                display_cart_items_with_images(cart_items)
                            else:
                                st.info("No items found in this order.")
                        except (ValueError, SyntaxError):
                            st.warning(f"Could not parse cart items: {cart_items_str}")
                    
                    st.markdown("---")

# Admin Sync Interface
def admin_sync_interface():
    """Admin SQL Server sync interface"""
    st.title("🔄 Sync Products from SQL Server")
    
    st.info("Configure your SQL Server connection details below:")
    
    with st.form("sync_form"):
        server = st.text_input("SQL Server Address", value="localhost\\SQLEXPRESS",
                              help="Format: server\\instance or IP address", autocomplete="off")
        database = st.text_input("Database Name", value="YourDatabase", autocomplete="off")
        username = st.text_input("SQL Username", value="sa", autocomplete="off")
        password = st.text_input("SQL Password", type="password", autocomplete="off")
        table_name = st.text_input("Table Name", value="Products",
                                   help="Name of the table containing product data", autocomplete="off")
        
        col1, col2 = st.columns(2)
        with col1:
            sync_button = st.form_submit_button("🔄 Sync Products", type="primary")
        with col2:
            cancel_button = st.form_submit_button("Cancel")
        
        if cancel_button:
            if 'show_sync' in st.session_state:
                del st.session_state.show_sync
            st.rerun()
        
        if sync_button:
            try:
                connection_string = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
                conn = pyodbc.connect(connection_string)
                
                query = f"SELECT * FROM {table_name}"
                df = pd.read_sql(query, conn)
                conn.close()
                
                if df.empty:
                    st.warning("No data found in the specified table.")
                else:
                    # Save to products.csv
                    df.to_csv(PRODUCTS_CSV, index=False)
                    st.success(f"✅ Successfully synced {len(df)} products from SQL Server!")
                    st.dataframe(df.head(10), use_container_width=True)
                    if 'show_sync' in st.session_state:
                        del st.session_state.show_sync
                    if st.button("Return to Finance Dashboard"):
                        st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error syncing from SQL Server: {str(e)}")
                st.info("Please check your connection details and ensure SQL Server is accessible.")

# Footer Function
def display_footer():
    """Display fixed footer bar at the bottom of the page"""
    st.markdown("""
        <div class="fixed-footer">
            InnoGen's IT Department © 2026
        </div>
    """, unsafe_allow_html=True)

# Main App Logic
def main():
    # Show toast notification if an item was just added to the cart
    if st.session_state.get('added_product_name'):
        st.toast(f"Added {st.session_state.added_product_name} to cart!", icon="🛒")
        st.session_state.added_product_name = None

    # CRITICAL: Top-level check to prevent dialog flash when adding to cart
    # This runs BEFORE any interface rendering, ensuring dialog state is cleared
    if st.session_state.get('just_added_to_cart', False):
        clear_all_dialog_states()
        # Keep flag set during render to prevent dialog from showing
    
    # QR-code specific behavior: if user came from ?source=qrcode, show a one-time welcome/install hint
    try:
        query_params = st.query_params
    except AttributeError:
        query_params = st.experimental_get_query_params()
    source_val = None
    if isinstance(query_params, dict):
        raw = query_params.get("source")
        if isinstance(raw, list):
            source_val = raw[0] if raw else None
        else:
            source_val = raw
    if source_val == "qrcode" and not st.session_state.get("qr_welcome_shown", False):
        st.toast("Scan successful! Welcome to the Solvang Mobile Portal.", icon="📱")
        st.info(
            "Tip: You can install this app on your phone for faster access. "
            "After a few visits, your browser may show an 'Install app' or 'Add to Home screen' option in its menu."
        )
        st.session_state.qr_welcome_shown = True
    
    if not st.session_state.authenticated:
        login_page()
    else:
        # Normalize role for fallback (handles old "Admin Level 1" / "Finance Staff Level 1" in session)
        user_role = normalize_role(st.session_state.user_role or '')
        if user_role in ('Sales Rep', 'TSR'):
            sales_rep_interface()
        elif user_role in ('Admin Level 0', 'Admin Level 1 Ethical', 'Admin Level 2', 'Ethical Staff Level 1', 'Finance Staff Level 2', 'Admin / Finance Staff', 'Finance Staff'):
            finance_staff_interface()
        elif user_role == 'SGF Manager':
            sgf_manager_interface()
        else:
            st.error("Unknown user role. Please contact administrator.")
    
    # Reset flag AFTER all rendering is complete (at the very end)
    if st.session_state.get('just_added_to_cart', False) and not st.session_state.get('show_submit_order_dialog', False):
        st.session_state.just_added_to_cart = False

if __name__ == "__main__":
    main()
