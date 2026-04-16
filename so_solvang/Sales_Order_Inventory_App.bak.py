import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pyodbc
import os
import ast
import re
from db_manager import DatabaseManager, CartItem, User, Product

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
db = st.session_state.db

# Specific CSS to hide only the menu and the branding line
st.markdown("""
    <style>
    /* 1. Hide the Main Menu (the three dots) only */
    #MainMenu {visibility: hidden;}

    /* 2. Hide the default Streamlit branding footer text */
    /* This leaves your custom purple footer untouched */
    footer {visibility: hidden;}

    /* 3. Re-expose your custom footer if it was inside a footer tag */
    /* Adjust '.my-footer-class' to whatever class you gave your purple bar */
    .st-emotion-cache-12w0qpk { 
        visibility: visible; 
    }
    
    /* 4. Ensure the header remains visible for the sidebar toggle */
    /* But hide the 'Deploy' button if it appears */
    .stAppDeployButton {display:none;}
    </style>
    """, unsafe_allow_html=True)

# Add global CSS for fixed footer
st.markdown("""
    <style>
    /* Fixed footer styling - thin and overlapping sidebar, always on top */
    .fixed-footer {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        background-color: #7B2CBF !important;
        color: #FFFFFF !important;
        text-align: center !important;
        padding: 6px 0 !important;
        border-top: 1px solid #6A1B9A !important;
        z-index: 999999 !important;
        font-size: 0.8rem !important;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1) !important;
        margin: 0 !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
    }
    
    /* Add padding to main content area to prevent content from being hidden behind footer */
    .main .block-container {
        padding-bottom: 40px !important;
    }
    
    /* Ensure footer is above all Streamlit elements */
    section[data-testid="stSidebar"],
    div[data-testid="stAppViewContainer"],
    div[data-testid="stHeader"],
    header[data-testid="stHeader"] {
        z-index: 1 !important;
    }
    
    /* Ensure footer container is above everything */
    body > div.fixed-footer {
        z-index: 999999 !important;
    }
    
    /* Increase Streamlit image fullscreen button size */
    button[title="Fullscreen"],
    button[aria-label="Fullscreen"],
    div[data-testid="stImage"] button,
    div[data-testid="stImage"] button[title*="Fullscreen"],
    div[data-testid="stImage"] button[aria-label*="Fullscreen"] {
        width: 32px !important;
        height: 32px !important;
        min-width: 32px !important;
        min-height: 32px !important;
        padding: 6px !important;
        font-size: 16px !important;
    }
    </style>
""", unsafe_allow_html=True)

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
if 'admin_level' not in st.session_state:
    st.session_state.admin_level = None
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
if 'scroll_to_bottom_accounts' not in st.session_state:
    st.session_state.scroll_to_bottom_accounts = False
if 'accounts_add_mode' not in st.session_state:
    st.session_state.accounts_add_mode = False
if 'order_uploaded_files' not in st.session_state:
    st.session_state.order_uploaded_files = []
if 'order_uploaded_files_dialog' not in st.session_state:
    st.session_state.order_uploaded_files_dialog = []
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

# File paths
PRODUCTS_CSV = 'products.csv'
ORDERS_CSV = 'orders.csv'
USERS_CSV = 'users.csv'
SEND_TXT = 'Send.txt'
ACCOUNTS_CSV = 'sales_order_LIST_OF_ACCOUNTS.csv'
EMAIL_LOG_FILE = 'email_notifications.log'

# Email configuration
# Gmail account for SMTP authentication (required for Gmail SMTP)
# If Send.txt only contains the App Password, set this constant to your Gmail account email
# Example: GMAIL_ACCOUNT = 'your-email@gmail.com'
GMAIL_ACCOUNT = 'no-reply@innogen-pharma.com'  # Gmail account for SMTP authentication

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
        
        users_dict = {}
        for username, user_data in db_users.items():
            users_dict[username] = {
                'password': user_data.get('password', ''),
                'role': user_data.get('role', ''),
                'rep_code': user_data.get('rep_code') if user_data.get('rep_code') and str(user_data.get('rep_code')) != 'nan' else None,
                'rep_name': user_data.get('rep_name') if user_data.get('rep_name') and str(user_data.get('rep_name')) != 'nan' else None,
                'rep_company': user_data.get('rep_company') if user_data.get('rep_company') and str(user_data.get('rep_company')) != 'nan' else None,
                'rep_dept': user_data.get('rep_dept') if user_data.get('rep_dept') and str(user_data.get('rep_dept')) != 'nan' else None,
                'rep_area': user_data.get('rep_area') if user_data.get('rep_area') and str(user_data.get('rep_area')) != 'nan' else None,
                'admin_level': None, # Default
                'view_only': False   # Default
            }
            
            # Apply special permissions logic based on username (Legacy logic)
            if username == 'Admin1': 
                users_dict[username]['admin_level'] = 1
            elif username == 'Admin2': 
                users_dict[username]['admin_level'] = 2
            elif username == 'Finance2':
                users_dict[username]['admin_level'] = 2
                users_dict[username]['view_only'] = True
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
    if os.path.exists(logo_path):
        st.image(logo_path, width=width, use_container_width=False)
    else:
        # Fallback: Display text logo if image not found
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
                'RepDept', 'RepArea', 'ReviewedBy', 'ReviewedDate', 'CreatedBy', 'CartItems', 'Attachments'
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
                    st.image(image_path, use_container_width=True)
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
    st.markdown("""
        <style>
        /* Make Remove/Disapprove button text smaller and auto-shrink */
        button[key*="disapprove_item"] {
            font-size: 0.75rem !important;
            line-height: 1.2 !important;
            padding: 0.4rem 0.5rem !important;
            white-space: normal !important;
            word-wrap: break-word !important;
        }
        button[key*="disapprove_item"] p {
            font-size: 0.75rem !important;
            line-height: 1.2 !important;
            margin: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
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
                    st.image(image_path, use_container_width=True)
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

def load_accounts():
    """Load accounts from SQLite Database"""
    try:
        df = db.get_all_accounts()
        if df.empty:
            return pd.DataFrame()
            
        # Ensure compatibility with existing app logic
        # Convert Customer code column to string type if it exists
        if 'Customer code' in df.columns:
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
            
            df['Customer code'] = df['Customer code'].apply(clean_customer_code)
            df['Customer code'] = df['Customer code'].astype('object')

        # Convert Area column to string type
        if 'Area' in df.columns:
            df['Area'] = df['Area'].fillna('').astype(str).replace('nan', '').replace('NaN', '').replace('None', '')
            df['Area'] = df['Area'].astype('object')
            
        # Ensure SGF columns exist
        if 'SGF' not in df.columns:
            df['SGF'] = 'FALSE'
        else:
            df['SGF'] = df['SGF'].fillna('FALSE').astype(str).str.upper()
            
        if 'SGF_count' not in df.columns:
            df['SGF_count'] = 99
        else:
            df['SGF_count'] = pd.to_numeric(df['SGF_count'], errors='coerce').fillna(99)
            
        return df
    except Exception as e:
        st.error(f"Error loading accounts: {e}")
        return pd.DataFrame()

def save_accounts(df):
    """Save accounts to SQLite Database"""
    try:
        return db.save_accounts_df(df)
    except Exception as e:
        st.error(f"Error saving accounts: {e}")
        return False

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
                            st.image(file_path, use_container_width=True, caption=os.path.basename(file_path))
                        except Exception:
                            st.error(f"Error displaying image: {os.path.basename(file_path)}")
        
        # Display PDFs
        if pdf_files:
            st.markdown("**PDF Files:**")
            for file_path in pdf_files:
                file_name = os.path.basename(file_path)
                try:
                    # Get file size
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"📄 **{file_name}**")
                            st.caption(f"Size: {file_size:.2f} MB")
                        with col2:
                            # Read PDF and create download button
                            with open(file_path, "rb") as pdf_file:
                                pdf_data = pdf_file.read()
                                st.download_button(
                                    label="📥 Download",
                                    data=pdf_data,
                                    file_name=file_name,
                                    mime="application/pdf",
                                    key=f"download_pdf_{file_path}",
                                    use_container_width=True
                                )
                except Exception as e:
                    st.error(f"Error displaying PDF {file_name}: {e}")
        
    except (ValueError, SyntaxError):
        # If parsing fails, try to display as single file path
        if attachments_str and os.path.exists(attachments_str):
            file_ext = os.path.splitext(attachments_str)[1].lower()
            if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                st.markdown("### 📎 Attachments")
                st.image(attachments_str, use_container_width=True, caption=os.path.basename(attachments_str))
            elif file_ext == '.pdf':
                st.markdown("### 📎 Attachments")
                with open(attachments_str, "rb") as pdf_file:
                    pdf_data = pdf_file.read()
                    st.download_button(
                        label=f"📥 Download {os.path.basename(attachments_str)}",
                        data=pdf_data,
                        file_name=os.path.basename(attachments_str),
                        mime="application/pdf"
                    )
    except Exception as e:
        st.warning(f"Error displaying attachments: {e}")

def get_active_accounts():
    """Get only active accounts for selectbox"""
    accounts_df = load_accounts()
    if accounts_df.empty:
        return pd.DataFrame()
    
    # Filter for active accounts (Active = True or TRUE)
    if 'Active' in accounts_df.columns:
        # Handle both string and boolean values
        active_accounts = accounts_df[
            accounts_df['Active'].astype(str).str.upper() == 'TRUE'
        ].copy()
        return active_accounts
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
    """Load users from both hardcoded USERS dict and users.csv, merge them"""
    all_users = USERS.copy()
    
    users_df = load_users_csv()
    if not users_df.empty:
        for _, row in users_df.iterrows():
            username = str(row.get('Username', '')).strip()
            if username:
                admin_level = None
                if pd.notna(row.get('AdminLevel')):
                    try:
                        admin_level = int(row.get('AdminLevel'))
                    except (ValueError, TypeError):
                        admin_level = None
                
                all_users[username] = {
                    'password': str(row.get('Password', '')),
                    'role': str(row.get('Role', 'Sales Rep')),
                    'rep_code': str(row.get('RepCode', '')) if pd.notna(row.get('RepCode')) else None,
                    'rep_name': str(row.get('RepName', '')) if pd.notna(row.get('RepName')) else None,
                    'rep_company': str(row.get('RepCompany', '')) if pd.notna(row.get('RepCompany')) else None,
                    'rep_dept': str(row.get('RepDept', '')) if pd.notna(row.get('RepDept')) else None,
                    'rep_area': str(row.get('RepArea', '')) if pd.notna(row.get('RepArea')) else None,
                    'admin_level': admin_level
                }
    return all_users

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

def send_email_notification(to_email, subject, body, sender_email=None, cc_emails=None):
    """Send email notification using Gmail"""
    try:
        log_email_notification("INFO", f"Attempting to send email", to_email=to_email, subject=subject)
        
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
        
        smtp_server = 'smtp.gmail.com'
        smtp_port = 465
        
        log_email_notification("INFO", f"Connecting to SMTP server: {smtp_server}:{smtp_port} (SSL)", to_email=to_email, subject=subject)
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        
        # Add CC recipients if provided
        if cc_emails:
            if isinstance(cc_emails, list):
                cc_string = ', '.join(cc_emails)
            else:
                cc_string = str(cc_emails)
            msg['Cc'] = cc_string
            log_email_notification("INFO", f"CC recipients: {cc_string}", to_email=to_email, subject=subject)
        
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        
        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
            log_email_notification("INFO", f"SSL connection established, logging in with Gmail account: {gmail_account}", to_email=to_email, subject=subject)
            server.login(gmail_account, password)
            
            log_email_notification("INFO", f"Sending email message", to_email=to_email, subject=subject)
            # Prepare recipients list (To + CC)
            recipients = [to_email]
            if cc_emails:
                if isinstance(cc_emails, list):
                    recipients.extend(cc_emails)
                else:
                    recipients.append(str(cc_emails))
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
        # Count orders that are Pending and not yet approved by Level 1
        pending_count = len(orders_df[
            (orders_df['Status'] == 'Pending') & 
            (orders_df['ApprovedByLevel1'] == '')
        ])
    elif admin_level == 2:
        # Count orders that are Pending, approved by Level 1, but not yet by Level 2
        pending_count = len(orders_df[
            (orders_df['Status'] == 'Pending') & 
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
    cc_emails = ["demitamodra009@gmail.com", "merin.ediline@innogen-pharma.ph", "jsr.solvangpharma@gmail.com"]
    
    log_email_notification("INFO", "SGF notification function called")
    
    # Count pending approvals
    pending_count = count_pending_sgf_approvals()
    log_email_notification("INFO", f"Pending SGF approvals count: {pending_count}")
    
    if pending_count == 0:
        log_email_notification("INFO", "No pending SGF approvals, skipping email notification")
        return True
    
    # Create email subject and body
    subject = f"New Pending SGF Approvals - {pending_count} Order(s) Awaiting Review"
    
    body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #7B2CBF; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .count {{ font-size: 32px; font-weight: bold; color: #7B2CBF; text-align: center; margin: 20px 0; }}
            .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Sales Order Management System</h2>
            </div>
            <div class="content">
                <h3>New Pending SGF Approvals Notification</h3>
                <p>Dear Ma'am / Sir,</p>
                <p>You have <strong>{pending_count} pending order(s)</strong> awaiting your SGF approval.</p>
                <div class="count">{pending_count}</div>
                <p>Please log in to the Sales Order Management System to review and approve these orders.</p>
                <p><strong>Note:</strong> This is an automated notification. Please do not reply to this email.</p>
            </div>
            <div class="footer">
                <p>InnoGen's IT Department © 2026</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        log_email_notification("INFO", f"Preparing to send SGF notification to {sgf_email}", to_email=sgf_email, subject=subject)
        result = send_email_notification(sgf_email, subject, body, sender_email, cc_emails=cc_emails)
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
    cc_emails = ["demitamodra009@gmail.com", "merin.ediline@innogen-pharma.ph", "jsr.solvangpharma@gmail.com"]
    
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
    
    # Create email subject and body
    subject = f"New Pending Approvals - {pending_count} Order(s) Awaiting Review"
    
    body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #7B2CBF; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .count {{ font-size: 32px; font-weight: bold; color: #7B2CBF; text-align: center; margin: 20px 0; }}
            .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
            .button {{ display: inline-block; padding: 15px 30px; background-color: #7B2CBF; color: #FFFFFF !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; font-size: 16px; border: 2px solid #FFFFFF; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Sales Order Management System</h2>
            </div>
            <div class="content">
                <h3>New Pending Approvals Notification</h3>
                <p>Dear Admin Level {admin_level},</p>
                <p>You have <strong>{pending_count} pending order(s)</strong> awaiting your approval.</p>
                <div class="count">{pending_count}</div>
                <p>Please log in to the Sales Order Management System to review and approve these orders.</p>
                <p style="text-align: center;">
                    <a href="https://so.solvang-pharma.com/" class="button" style="display: inline-block; padding: 15px 30px; background-color: #7B2CBF; color: #FFFFFF !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; font-size: 16px; border: 2px solid #FFFFFF; text-shadow: 1px 1px 2px rgba(0,0,0,0.3);">Review Orders</a>
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
    
    # Send email
    try:
        log_email_notification("INFO", f"Preparing to send admin approval notification to {to_email}", to_email=to_email, subject=subject)
        result = send_email_notification(to_email, subject, body, sender_email, cc_emails=cc_emails)
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
    
    elif status == 'Pending' and not approved_by_l1:
        # Order is pending Level 1 approval
        log_email_notification("INFO", f"Sending Admin Level 1 notification for order {order_id}")
        result = send_approval_notification(admin_level=1)
        if result:
            return True, "Admin Level 1 notification sent successfully"
        else:
            return False, "Failed to send Admin Level 1 notification"
    
    elif status == 'Pending' and approved_by_l1 and not approved_by_l2:
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
        server = st.text_input("SQL Server Address", value="localhost\\SQLEXPRESS")
        database = st.text_input("Database Name", value="YourDatabase")
        username = st.text_input("SQL Username", value="sa")
        password = st.text_input("SQL Password", type="password")
        table_name = st.text_input("Table Name", value="Products")
        
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
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                authenticated, role, user_info = authenticate(username, password)
                if authenticated:
                    st.session_state.authenticated = True
                    st.session_state.user_role = role
                    st.session_state.username = username
                    st.session_state.admin_level = user_info.get('admin_level')
                    st.session_state.is_view_only = user_info.get('view_only', False)
                    if role == 'Sales Rep':
                        st.session_state.rep_code = user_info.get('rep_code')
                        st.session_state.rep_name = user_info.get('rep_name')
                        st.session_state.rep_company = user_info.get('rep_company')
                        st.session_state.rep_dept = user_info.get('rep_dept')
                        st.session_state.rep_area = user_info.get('rep_area')
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
                                 help="Choose a unique username for login")
        password = st.text_input("Password *", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password *", type="password", key="reg_confirm_password")
        
        st.markdown("---")
        st.markdown("### Representative Information")
        col1, col2 = st.columns(2)
        with col1:
            rep_code = st.text_input("Rep Code *", key="reg_rep_code",
                                    help="Your representative code")
            rep_name = st.text_input("Rep Name *", key="reg_rep_name",
                                    help="Your full name")
            rep_company = st.text_input("Rep Company *", key="reg_rep_company",
                                       help="SPI Ethical or SPI Distribution")
        with col2:
            rep_dept = st.text_input("Rep Dept/DSM *", key="reg_rep_dept",
                                    help="Department name or DSM Territory")
            rep_area = st.text_input("Rep Area/PMR *", key="reg_rep_area",
                                    help="Your assigned area")
        
        submit_registration = st.form_submit_button("Register", type="primary")
        
        if submit_registration:
            # Validation
            if not username or not username.strip():
                st.error("Username is required")
                return
            
            if not password or password != confirm_password:
                st.error("Passwords do not match or are empty")
                return
            
            # Check if username already exists
            all_users = load_all_users()
            if username in all_users:
                st.error(f"Username '{username}' already exists. Please choose a different username.")
                return
            
            # Validate all required fields
            required_fields = {
                'Rep Code': rep_code,
                'Rep Name': rep_name,
                'Rep Company': rep_company,
                'Rep Dept': rep_dept,
                'Rep Area': rep_area
            }
            
            missing_fields = [field for field, value in required_fields.items() if not value or str(value).strip() == '']
            
            if missing_fields:
                st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
            else:
                # Load existing users
                users_df = load_users_csv()
                
                # Create new user record
                new_user = {
                    'Username': username,
                    'Password': password,
                    'Role': 'Sales Rep',
                    'RepCode': rep_code,
                    'RepName': rep_name,
                    'RepCompany': rep_company,
                    'RepDept': rep_dept,
                    'RepArea': rep_area,
                    'RegistrationDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Add to DataFrame
                new_user_df = pd.DataFrame([new_user])
                if users_df.empty:
                    users_df = new_user_df
                else:
                    users_df = pd.concat([users_df, new_user_df], ignore_index=True)
                
                if save_users_csv(users_df):
                    st.success(f"Registration successful! Username '{username}' has been created.")
                    st.info("You can now login with your new credentials.")
                    st.balloons()
                else:
                    st.error("Error saving registration. Please try again.")

# Submit Order Dialog Function
@st.dialog(title="📝 Submit Order", width="large", dismissible=True)
def submit_order_dialog():
    """Dialog function for submitting orders"""
    st.header("Submit New Order")
    
    if not st.session_state.cart:
        st.warning("Your cart is empty. Please add products from the Browse Products tab.")
        st.info("💡 You can close this dialog by clicking outside or pressing ESC.")
        # If cart is empty and dialog is shown, provide a close button
        if st.button("Close", type="secondary", use_container_width=True):
            st.session_state.show_submit_order_dialog = False
            st.rerun()
    else:
        # Get active accounts for selectbox (OUTSIDE form)
        active_accounts = get_active_accounts()
        customer_options = ['']  # Start with empty option
        
        if not active_accounts.empty and 'Customer name' in active_accounts.columns:
            # Get unique customer names and sort them
            customer_names = active_accounts['Customer name'].astype(str).str.strip()
            customer_names = customer_names[customer_names != ''].unique()
            customer_options.extend(sorted(customer_names.tolist()))
        
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
            else:
                # Clear fields when no customer selected
                st.session_state.dialog_client_description = ''
                st.session_state.dialog_client_mobile = ''
                st.session_state.dialog_billing_address = ''
                st.session_state.dialog_shipping_address = ''
                st.session_state.dialog_contact_person_1 = ''
                st.session_state.dialog_payment_terms = ''
        
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
        
        st.markdown("---")
        st.subheader("Order Details")
        
        # Cart summary - wrapped in form to prevent reruns on every edit
        st.markdown("### Cart Summary")
        # Convert CartItems to dicts for DataFrame
        cart_data = [item.dict() for item in st.session_state.cart]
        cart_df = pd.DataFrame(cart_data)
        # Create display dataframe with Notes/Remarks column
        display_df = cart_df[['product_name', 'qty', 'price', 'notes_remarks']].copy()
        display_df['Total'] = display_df['qty'] * display_df['price']
        # Reorder columns: product_name, qty, price, Total, Notes/Remarks
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
        
        # Update cart items with edited notes_remarks only when Save Changes button is clicked
        if update_cart and not edited_df.empty:
            for idx, row in edited_df.iterrows():
                if idx < len(st.session_state.cart):
                    st.session_state.cart[idx].notes_remarks = row.get('Notes/Remarks', '')
            # Clear the tab form's editor state to force refresh
            if 'tab_cart_editor' in st.session_state:
                del st.session_state.tab_cart_editor
            st.success("Notes/Remarks saved successfully!")
            st.rerun()
        
        st.markdown("---")
        st.subheader("Client Information")
        
        # Client Name selectbox - OUTSIDE the form so on_change callback works
        selected_customer = st.selectbox(
            "Account / Customer Name *",
            options=customer_options,
            index=0,  # Default to empty option (first option is empty string)
            key="dialog_client_name_select",
            help="Select a customer from the list to auto-fill information",
            on_change=update_dialog_customer_fields
        )
        
        # Get customer name
        client_name = selected_customer if selected_customer else ''
        
        # Now start the form
        with st.form("order_form_dialog"):
            
            # Form fields - these will auto-fill from session state when customer is selected
            client_description = st.text_area(
                "Client Category *", 
                key="dialog_client_description"
            )
            client_mobile = st.text_input(
                "Mobile *", 
                key="dialog_client_mobile"
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
                    key="dialog_contact_person_1"
                )
                contact_person_1_mobile = st.text_input("Contact Person 1 Mobile", key="dialog_contact_person_1_mobile")
            with col2:
                contact_person_2 = st.text_input("Contact Person 2", key="dialog_contact_person_2")
                contact_person_2_mobile = st.text_input("Contact Person 2 Mobile", key="dialog_contact_person_2_mobile")
            
            st.markdown("---")
            st.subheader("Order Terms")
            payment_terms = st.text_input(
                "Payment Terms *", 
                key="dialog_payment_terms", 
                placeholder="e.g., Net 30, COD, etc."
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
                help="Attach multiple files. Each file must be 5MB or less. Supported formats: Images (PNG, JPG, JPEG, GIF, BMP, WEBP) and PDFs."
            )
            
            # Validate file sizes and store valid files
            if uploaded_files:
                valid_files = []
                invalid_files = []
                
                for uploaded_file in uploaded_files:
                    file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)  # Convert to MB
                    if file_size_mb > 5:
                        invalid_files.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB - exceeds 5MB limit)")
                    else:
                        valid_files.append(uploaded_file)
                
                if invalid_files:
                    st.error("The following files exceed the 5MB limit:\n" + "\n".join(f"- {f}" for f in invalid_files))
                
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
                rep_code = st.text_input("Rep Code *", value=st.session_state.rep_code, key="dialog_rep_code")
                rep_name = st.text_input("Rep Name *", value=st.session_state.rep_name, key="dialog_rep_name")
                rep_company = st.text_input("Rep Company *", value=st.session_state.rep_company, key="dialog_rep_company")
            with col2:
                rep_dept = st.text_input("Rep Dept/DSM *", value=st.session_state.rep_dept, key="dialog_rep_dept")
                rep_area = st.text_input("Rep Area/PMR *", value=st.session_state.rep_area, key="dialog_rep_area")
            
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
                # Validation - ensure client_name is set
                if not client_name or client_name.strip() == '':
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
                        'Rep Code': rep_code,
                        'Rep Name': rep_name,
                        'Rep Company': rep_company,
                        'Rep Dept': rep_dept,
                        'Rep Area': rep_area
                    }
                    
                    missing_fields = [field for field, value in required_fields.items() if not value or value.strip() == '']
                    
                    if missing_fields:
                        st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                    else:
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
                        initial_status = 'Pending for SGF' if needs_sgf else 'Pending'
                        
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
                            'ApprovedByLevel1': '',
                            'ApprovedDateLevel1': '',
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
                            'CreatedBy': st.session_state.username
                        }
                        
                        # Add to orders DataFrame
                        new_order_df = pd.DataFrame([order_data])
                        if orders_df.empty:
                            orders_df = new_order_df
                        else:
                            orders_df = pd.concat([orders_df, new_order_df], ignore_index=True)
                        
                        if save_orders(orders_df):
                            # Send email notification based on workflow
                            try:
                                if needs_sgf:
                                    # Send SGF notification
                                    send_sgf_notification()
                                else:
                                    # Send Admin Level 1 notification
                                    send_approval_notification(admin_level=1)
                            except Exception as e:
                                # Don't show error to user, just log it
                                print(f"Error sending notification email: {e}")
                            
                            st.session_state.show_submit_order_dialog = False
                            st.session_state.cart = []
                            st.session_state.order_uploaded_files_dialog = []  # Clear uploaded files
                            st.session_state.last_submitted_order_id = order_id
                            st.session_state.order_submission_success = True
                            status_message = "Pending for SGF approval" if needs_sgf else "Pending"
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
        st.markdown(f"**Status:** {order_row.get('Status', 'N/A')}")
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
        st.markdown(f"**Rep Code:** {order_row.get('RepCode', 'N/A')}")
        st.markdown(f"**Rep Name:** {order_row.get('RepName', 'N/A')}")
        st.markdown(f"**Rep Company:** {order_row.get('RepCompany', 'N/A')}")
    with col2:
        st.markdown(f"**Rep Dept/DSM:** {order_row.get('RepDept', 'N/A')}")
        st.markdown(f"**Rep Area/PMR:** {order_row.get('RepArea', 'N/A')}")
    
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
                        st.session_state.show_disapprove_dialog = False
                        st.session_state.disapprove_order_id = None
                        st.success(f"Order {order_id} has been disapproved with reason.")
                        st.rerun()
                    else:
                        st.error("Error saving disapproval. Please try again.")

# Add Account Dialog Function
@st.dialog(title="➕ Add New Account", width="medium", dismissible=True)
def add_account_dialog():
    """Dialog function for adding new accounts"""
    st.header("Add New Account")
    
    with st.form("add_account_form"):
        customer_code = st.text_input("Customer Code *", key="new_customer_code")
        customer_name = st.text_input("Customer Name *", key="new_customer_name")
        credit_term = st.text_input("Credit Term *", key="new_credit_term", placeholder="e.g., COD, 30D, 60D")
        area = st.text_input("Area", key="new_area", placeholder="e.g., Central, North, South")
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
                            'SGF_count': sgf_count_value
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
                        'SGF_count': sgf_count_value
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
    is_super_admin = (current_username == 'administrator') or (current_role == 'Admin')
    # Level 1 can only manage non-Finance
    is_level1 = (current_admin_level == 1)
    
    # Add User Form
    with st.expander("➕ Add / Edit User", expanded=st.session_state.user_to_edit is not None):
        with st.form("user_form"):
            # If editing, pre-fill values
            edit_data = st.session_state.user_to_edit or {}
            is_edit = st.session_state.user_to_edit is not None
            
            username = st.text_input("Username *", value=edit_data.get('Username', ''), disabled=is_edit)
            password = st.text_input("Password *", value=edit_data.get('Password', ''), type="password")
            
            role_options = ["Sales Rep", "Admin / Finance Staff", "SGF Manager", "Admin"]
            current_role_val = edit_data.get('Role', 'Sales Rep')
            role_index = role_options.index(current_role_val) if current_role_val in role_options else 0
            role = st.selectbox("Role *", role_options, index=role_index)
            
            col1, col2 = st.columns(2)
            with col1:
                rep_code = st.text_input("Rep Code", value=edit_data.get('RepCode', ''))
                rep_name = st.text_input("Rep Name", value=edit_data.get('RepName', ''))
                rep_company = st.text_input("Rep Company", value=edit_data.get('RepCompany', ''))
            with col2:
                rep_dept = st.text_input("Rep Dept", value=edit_data.get('RepDept', ''))
                rep_area = st.text_input("Rep Area", value=edit_data.get('RepArea', ''))
                registration_date = edit_data.get('RegistrationDate', datetime.now().strftime('%Y-%m-%d'))
            
            submitted = st.form_submit_button("Save User", type="primary", use_container_width=True)
            
            if submitted:
                if not username or not password or not role:
                    st.error("Username, Password, and Role are required.")
                elif is_level1 and rep_dept == 'Finance':
                    st.error("Access Denied: Level 1 Admin cannot create or edit Finance users.")
                else:
                    try:
                        user = User(
                            username=username,
                            password=password,
                            role=role,
                            rep_code=rep_code,
                            rep_name=rep_name,
                            rep_company=rep_company,
                            rep_dept=rep_dept,
                            rep_area=rep_area,
                            registration_date=registration_date
                        )
                        if db.upsert_user(user):
                            st.success(f"User {username} saved successfully!")
                            st.session_state.user_to_edit = None
                            st.rerun()
                        else:
                            st.error("Error saving user.")
                    except Exception as e:
                        st.error(f"Validation Error: {e}")
                        
        if is_edit:
            if st.button("Cancel Edit", use_container_width=True):
                st.session_state.user_to_edit = None
                st.rerun()

    # List Users
    users_df = db.get_all_users_df()
    if not users_df.empty:
        # Filter users based on access level
        if not is_super_admin:
            if is_level1:
                # Filter out Finance users
                users_df = users_df[users_df['RepDept'] != 'Finance']
            # Add other conditions if necessary for other roles
        
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
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
                product_code = st.text_input("Product Code *", value=edit_data.get('ProductCode', ''), disabled=is_edit)
                product_name = st.text_input("Product Name *", value=edit_data.get('ProductName', ''))
                unit_price = st.number_input("Unit Price *", value=float(edit_data.get('UnitPrice', 0.0)), min_value=0.0)
            with col2:
                category = st.text_input("Category", value=edit_data.get('Category', ''))
                manufacturer = st.text_input("Manufacturer", value=edit_data.get('Manufacturer', ''))
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
        search_term = st.text_input("🔍 Search Products", placeholder="Search by name or code...")
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
    
    accounts_df = load_accounts()
    
    # If AREA column doesn't exist, add it with empty values (for backward compatibility)
    if not accounts_df.empty and 'Area' not in accounts_df.columns:
        accounts_df['Area'] = ''  # This will be string type by default
        accounts_df['Area'] = accounts_df['Area'].astype('object')  # Explicitly set as object (string) type
    # If SGF column doesn't exist, add it with default value False
    if not accounts_df.empty and 'SGF' not in accounts_df.columns:
        accounts_df['SGF'] = 'FALSE'
    # If SGF_count column doesn't exist, add it with default value 99
    if not accounts_df.empty and 'SGF_count' not in accounts_df.columns:
        accounts_df['SGF_count'] = 99
    # Save the updated structure if any columns were added
    if not accounts_df.empty and ('Area' not in accounts_df.columns or 'SGF' not in accounts_df.columns or 'SGF_count' not in accounts_df.columns):
        if 'Area' not in accounts_df.columns:
            accounts_df['Area'] = ''
            accounts_df['Area'] = accounts_df['Area'].astype('object')
        if 'SGF' not in accounts_df.columns:
            accounts_df['SGF'] = 'FALSE'
        if 'SGF_count' not in accounts_df.columns:
            accounts_df['SGF_count'] = 99
        save_accounts(accounts_df)
    
    if accounts_df.empty:
        st.warning("No accounts found. Please ensure the accounts CSV file exists.")
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("Close", type="primary", use_container_width=True):
                st.session_state.show_accounts_dialog = False
                # Reset add mode when closing dialog
                st.session_state.accounts_add_mode = False
                st.rerun()
        with col2:
            if st.button("➕ Add Account", type="secondary", use_container_width=True):
                st.session_state.show_add_account_dialog = True
                st.rerun()
    else:
        # Select only the columns to display
        display_cols = ['Customer code', 'Customer name', 'Credit term', 'Area', 'Active', 'SGF', 'SGF_count']
        available_cols = [col for col in display_cols if col in accounts_df.columns]
        
        if len(available_cols) < len(display_cols):
            missing_cols = [col for col in display_cols if col not in accounts_df.columns]
            st.warning(f"Missing columns in CSV: {', '.join(missing_cols)}")
            st.info("Available columns: " + ", ".join(accounts_df.columns.tolist()))
        
        # Create display dataframe with only selected columns
        if available_cols:
            # Add button at the top right
            col_title, col_add = st.columns([4, 1])
            with col_title:
                st.markdown("### Accounts Table")
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
                        else:
                            new_row[col] = ''
                    
                    # Ensure all columns from accounts_df are included
                    for col in accounts_df.columns:
                        if col not in new_row:
                            if col == 'SGF':
                                new_row[col] = 'FALSE'
                            elif col == 'SGF_count':
                                new_row[col] = 99
                            else:
                                new_row[col] = ''
                    
                    new_row_df = pd.DataFrame([new_row])
                    if accounts_df.empty:
                        accounts_df = new_row_df
                    else:
                        accounts_df = pd.concat([accounts_df, new_row_df], ignore_index=True)
                    # Save the updated dataframe
                    save_accounts(accounts_df)
                    # Set flag to scroll to bottom after rerun
                    st.session_state.scroll_to_bottom_accounts = True
                    st.rerun()
            
            display_df = accounts_df[available_cols].copy()
            
            # Preserve original index for mapping back to accounts_df
            display_df['_original_index'] = display_df.index
            
            # Sort by Customer Name (case-insensitive)
            if 'Customer name' in display_df.columns:
                # Create a temporary column for sorting (case-insensitive)
                display_df['_sort_temp'] = display_df['Customer name'].astype(str).str.lower()
                display_df = display_df.sort_values('_sort_temp', na_position='last').reset_index(drop=True)
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
            # Store _original_index separately for mapping during save
            original_indices = display_df['_original_index'].copy() if '_original_index' in display_df.columns else None
            
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
                        accounts_df = pd.concat([accounts_df, new_rows_df], ignore_index=True)
                    
                    # Save the updated dataframe
                    if save_accounts(accounts_df):
                        st.success("Accounts updated successfully!")
                        # Reset add mode after saving so columns become restricted again
                        st.session_state.accounts_add_mode = False
                        st.rerun()
                    else:
                        st.error("Error saving accounts.")
            with col2:
                if st.button("Close", type="secondary", use_container_width=True):
                    st.session_state.show_accounts_dialog = False
                    # Reset add mode when closing dialog
                    st.session_state.accounts_add_mode = False
                    st.rerun()
            
        else:
            st.error("Required columns not found in accounts CSV file.")
            if st.button("Close", type="primary", use_container_width=True):
                st.session_state.show_accounts_dialog = False
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
                st.image(image_path, use_container_width=True)
            
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

def build_order_print_html(order_row, cart_items):
    """Build a simple one-page HTML print view for an order."""
    # Format cart rows
    item_rows = ""
    for idx, item in enumerate(cart_items, start=1):
        qty = safe_float_convert(item.get('qty', 0))
        price = safe_float_convert(item.get('price', 0))
        subtotal = qty * price
        notes_remarks = item.get('notes_remarks', '')
        notes_cell = f"<br><small style='color:#666;'>{notes_remarks}</small>" if notes_remarks else ""
        item_rows += f"""
            <tr>
                <td style='padding:4px; border:1px solid #ccc; text-align:center;'>{idx}</td>
                <td style='padding:4px; border:1px solid #ccc;'>{item.get('product_code', '')}</td>
                <td style='padding:4px; border:1px solid #ccc;'>{item.get('product_name', '')}{notes_cell}</td>
                <td style='padding:4px; border:1px solid #ccc; text-align:right;'>{qty:.2f}</td>
                <td style='padding:4px; border:1px solid #ccc; text-align:right;'>{price:.2f}</td>
                <td style='padding:4px; border:1px solid #ccc; text-align:right;'>{subtotal:.2f}</td>
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
    
    notes = order_row.get('Notes', '')
    remarks = order_row.get('Remarks', '')
    additional = ""
    if notes:
        additional += f"<div><strong>Notes:</strong> {notes}</div>"
    if remarks:
        additional += f"<div><strong>Remarks:</strong> {remarks}</div>"
    if not additional:
        additional = "<div>No additional notes.</div>"
    
    html = f"""
    <html>
    <head>
        <style>
            @media print {{
                @page {{ margin: 16mm; }}
            }}
            body {{ font-family: Arial, sans-serif; color: #222; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; }}
            .title {{ font-size: 20px; font-weight: bold; }}
            .section {{ margin-top: 12px; }}
            .section h4 {{ margin: 0 0 6px 0; }}
            table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
            .totals-table td {{ padding: 4px; }}
        </style>
    </head>
    <body onload="window.print()">
        <div class="header">
            <div>
                <div class="title">Sales Order</div>
                <div>Order ID: {order_row.get('OrderID', '')}</div>
                <div>Date: {order_row.get('OrderDate', '')}</div>
                <div>Status: {order_row.get('Status', '')}</div>
            </div>
            <div style="text-align:right;">
                <div><strong>Rep:</strong> {order_row.get('RepName', '')}</div>
                <div><strong>Rep Code:</strong> {order_row.get('RepCode', '')}</div>
                <div><strong>Dept/Area:</strong> {order_row.get('RepDept', '')} / {order_row.get('RepArea', '')}</div>
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
                    </tr>
                </thead>
                <tbody>
                    {item_rows if item_rows else "<tr><td colspan='6' style='text-align:center; padding:6px; border:1px solid #ccc;'>No items found</td></tr>"}
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
    st.info("Use your browser's print dialog to save as PDF.")
    
    html = build_order_print_html(order_row, remaining_items)
    st.components.v1.html(html, height=1100, scrolling=True)
    
    if st.button("Close Print View", type="secondary"):
        st.session_state.show_print_view = False
        st.session_state.print_view_order_id = None
        st.rerun()

# Sales Rep Interface
def sales_rep_interface():
    """Sales Rep main interface"""
    # Show order details dialog if triggered (from Order History)
    dialog_triggered = st.session_state.get('show_order_details_dialog', False)
    selected_order_id = st.session_state.get('selected_order_id')
    button_clicked = st.session_state.get('dialog_button_clicked', False)
    
    if dialog_triggered and selected_order_id and button_clicked:
        orders_df = load_orders()
        order_details_dialog(st.session_state.selected_order_id, orders_df)
        # Reset button_clicked flag after dialog runs
        st.session_state.dialog_button_clicked = False
    
    # Add CSS to center emoji in buttons and reduce container padding
    st.markdown("""
        <style>
        /* Center emoji and text in buttons */
        div[data-testid="stButton"] > button > div {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
            width: 100% !important;
        }
        /* Fix emoji alignment in button text */
        div[data-testid="stButton"] > button > div > p {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Add CSS to reduce container padding and spacing for more compact cards
    st.markdown("""
        <style>
        /* Reduce padding and spacing in containers with borders */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 8px 12px !important;
            margin-bottom: 8px !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("📦 Sales Order Management")
    
    # Sidebar - Logo and Shopping Cart
    with st.sidebar:
        # Display logo at the top of sidebar
        display_logo(width=200)
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
            if st.button("📝 Submit Order", type="primary", use_container_width=True):
                # Reset image viewer state when submitting order
                st.session_state.show_image_viewer = False
                st.session_state.viewer_image_path = None
                st.session_state.viewer_product_name = None
                st.session_state.viewer_product_code = None
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
    
    # Show Submit Order dialog if button was clicked
    if st.session_state.get('show_submit_order_dialog', False):
        submit_order_dialog()
    
    # Main Content - Tabs
    tab1, tab2, tab3 = st.tabs(["🛍️ Browse Products", "📝 Submit Order", "📋 Order History"])
    
    with tab1:
        st.header("Product Catalog")
        products_df = load_products()
        
        if products_df.empty:
            st.warning("No products available. Please sync products from SQL Server (Admin tab) or create products.csv file.")
        else:
            # Search and filter
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("Search products", placeholder="Enter product name or code...")
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
                                # Reset image viewer state when adding to cart
                                st.session_state.show_image_viewer = False
                                st.session_state.viewer_image_path = None
                                st.session_state.viewer_product_name = None
                                st.session_state.viewer_product_code = None
                                
                                price = safe_float_convert(row.get(price_col, 0)) if price_col else 0.0
                                
                                # Check if product already in cart
                                found = False
                                for item in st.session_state.cart:
                                    if item.product_code == product_code:
                                        item.qty += qty
                                        found = True
                                        break
                                
                                if not found:
                                    new_item = CartItem(
                                        product_code=product_code,
                                        product_name=product_name,
                                        qty=qty,
                                        price=price,
                                        notes_remarks='',
                                        row_data=row.to_dict()
                                    )
                                    st.session_state.cart.append(new_item)
                                st.success(f"Added {qty} x {product_name} to cart!")
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
        st.header("Submit New Order")
        
        # Show success message if order was just submitted
        if st.session_state.get('order_submission_success', False) and st.session_state.get('last_submitted_order_id'):
            st.success(f"✅ Order {st.session_state.last_submitted_order_id} has been successfully submitted with status 'Pending'! Your cart has been cleared. Check the Order History tab to view your order.")
            st.session_state.order_submission_success = False  # Reset flag after showing message
        
        if not st.session_state.cart:
            st.info("🛒 Your cart is empty. Please add products from the Browse Products tab to create an order.")
        else:
            # Get active accounts for selectbox (OUTSIDE form)
            active_accounts = get_active_accounts()
            customer_options = ['']  # Start with empty option
            
            if not active_accounts.empty and 'Customer name' in active_accounts.columns:
                # Get unique customer names and sort them
                customer_names = active_accounts['Customer name'].astype(str).str.strip()
                customer_names = customer_names[customer_names != ''].unique()
                customer_options.extend(sorted(customer_names.tolist()))
            
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
                else:
                    # Clear fields when no customer selected
                    st.session_state.client_description = ''
                    st.session_state.client_mobile = ''
                    st.session_state.billing_address = ''
                    st.session_state.shipping_address = ''
                    st.session_state.contact_person_1 = ''
                    st.session_state.payment_terms = ''
            
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
            
            st.markdown("---")
            st.subheader("Order Details")
            
            # Cart summary - wrapped in form to prevent reruns on every edit
            st.markdown("### Cart Summary")
            # Ensure all cart items have notes_remarks field
            for item in st.session_state.cart:
                if not item.notes_remarks:
                    item.notes_remarks = ''
            
            # Convert CartItems to dicts for DataFrame
            cart_data = [item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart]
            cart_df = pd.DataFrame(cart_data)
            # Create display dataframe with Notes/Remarks column
            display_df = cart_df[['product_name', 'qty', 'price', 'notes_remarks']].copy()
            display_df['Total'] = display_df['qty'] * display_df['price']
            # Reorder columns: product_name, qty, price, Total, Notes/Remarks
            display_df = display_df[['product_name', 'qty', 'price', 'Total', 'notes_remarks']]
            display_df.columns = ['product_name', 'qty', 'price', 'Total', 'Notes/Remarks']
            
            # Wrap data_editor in a form to prevent reruns on every cell edit
            with st.form("tab_cart_update_form"):
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
                    key="tab_cart_editor"
                )
                
                update_cart = st.form_submit_button("💾 Save Changes (Notes /Remarks)", type="primary", use_container_width=True)
            
            # Update cart items with edited notes_remarks only when Save Changes button is clicked
            if update_cart and not edited_df.empty:
                for idx, row in edited_df.iterrows():
                    if idx < len(st.session_state.cart):
                        st.session_state.cart[idx].notes_remarks = row.get('Notes/Remarks', '')
                # Clear the dialog form's editor state to force refresh
                if 'dialog_cart_editor' in st.session_state:
                    del st.session_state.dialog_cart_editor
                st.success("Notes/Remarks saved successfully!")
                st.rerun()
            
            st.markdown("---")
            st.subheader("Client Information")
            
            # Client Name selectbox - OUTSIDE the form so on_change callback works
            selected_customer = st.selectbox(
                "Account / Customer Name  *",
                options=customer_options,
                index=0,  # Default to empty option (first option is empty string)
                key="client_name_select",
                help="Select a customer from the list to auto-fill information",
                on_change=update_tab_customer_fields
            )
            
            # Get customer name
            client_name = selected_customer if selected_customer else ''
            
            # Now start the form
            with st.form("order_form"):
                
                # Form fields - these will auto-fill from session state when customer is selected
                st.text_area(
                    "Client Category *", 
                    key="client_description"
                )
                st.text_input(
                    "Mobile *", 
                    key="client_mobile"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    st.text_area(
                        "Billing Address *", 
                        key="billing_address"
                    )
                with col2:
                    st.text_area(
                        "Shipping Address *", 
                        key="shipping_address"
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
                        key="contact_person_1"
                    )
                    contact_person_1_mobile = st.text_input("Contact Person 1 Mobile", key="contact_person_1_mobile")
                with col2:
                    contact_person_2 = st.text_input("Contact Person 2", key="contact_person_2")
                    contact_person_2_mobile = st.text_input("Contact Person 2 Mobile", key="contact_person_2_mobile")
                
                st.markdown("---")
                st.subheader("Order Terms")
                st.text_input(
                    "Payment Terms *", 
                    key="payment_terms",
                    placeholder="e.g., Net 30, COD, etc."
                )
                delivery_terms = st.text_area("Delivery Instructions *", key="delivery_terms",
                                            placeholder="Enter delivery instructions...")
                col1, col2 = st.columns(2)
                with col1:
                    delivery_date = st.date_input("Delivery Date / Requested Ship Date *", key="delivery_date")
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
                notes = st.text_area("Notes / Special Instructions", key="notes")
                remarks = st.text_area("Remarks", key="remarks")
                
                # File attach section
                st.markdown("### Attach File(s) (Optional)")
                uploaded_files = st.file_uploader(
                    "Attach file(s) (Pictures and PDFs only)",
                    type=['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'pdf'],
                    accept_multiple_files=True,
                    key="tab_file_uploader",
                    help="Attach multiple files. Each file must be 5MB or less. Supported formats: Images (PNG, JPG, JPEG, GIF, BMP, WEBP) and PDFs."
                )
                
                # Validate file sizes and store valid files
                if uploaded_files:
                    valid_files = []
                    invalid_files = []
                    
                    for uploaded_file in uploaded_files:
                        file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)  # Convert to MB
                        if file_size_mb > 5:
                            invalid_files.append(f"{uploaded_file.name} ({file_size_mb:.2f} MB - exceeds 5MB limit)")
                        else:
                            valid_files.append(uploaded_file)
                    
                    if invalid_files:
                        st.error("The following files exceed the 5MB limit:\n" + "\n".join(f"- {f}" for f in invalid_files))
                    
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
                    rep_code = st.text_input("Rep Code *", value=st.session_state.rep_code, key="rep_code")
                    rep_name = st.text_input("Rep Name *", value=st.session_state.rep_name, key="rep_name")
                    rep_company = st.text_input("Rep Company *", value=st.session_state.rep_company, key="rep_company")
                with col2:
                    rep_dept = st.text_input("Rep Dept/DSM *", value=st.session_state.rep_dept, key="rep_dept")
                    rep_area = st.text_input("Rep Area/PMR *", value=st.session_state.rep_area, key="rep_area")
                
                submit_order = st.form_submit_button("Submit Order", type="primary")
                
                if submit_order:
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
                        # Validation
                        required_fields = {
                            'Client Name': client_name,
                            'Client Category': client_description_val,
                            'Mobile': client_mobile_val,
                            'Billing Address': billing_address_val,
                            'Shipping Address': shipping_address_val,
                            'Payment Terms': payment_terms_val,
                            'Delivery Instructions': delivery_terms,
                            'Rep Code': rep_code,
                            'Rep Name': rep_name,
                            'Rep Company': rep_company,
                            'Rep Dept': rep_dept,
                            'Rep Area': rep_area
                        }
                        
                        missing_fields = [field for field, value in required_fields.items() if not value or value.strip() == '']
                        
                        if missing_fields:
                            st.error(f"Please fill in all required fields: {', '.join(missing_fields)}")
                        else:
                            # Create order
                            orders_df = load_orders()
                            order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            
                            # Save uploaded files if any
                            uploaded_files_list = st.session_state.get('order_uploaded_files', [])
                            attachment_paths = []
                            if uploaded_files_list:
                                attachment_paths = save_order_attachments(order_id, uploaded_files_list)
                            
                            # Calculate totals
                            subtotal = sum(item.qty * item.price for item in st.session_state.cart)
                            discount_amount = (subtotal * discount_percent) / 100
                            total_amount = subtotal - discount_amount
                            
                            # Check if account needs SGF workflow
                            needs_sgf = check_sgf_eligibility(client_name)
                            initial_status = 'Pending for SGF' if needs_sgf else 'Pending'
                            
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
                                'ApprovedByLevel1': '',
                                'ApprovedDateLevel1': '',
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
                            'CartItems': str([item.model_dump() if hasattr(item, 'model_dump') else item.dict() for item in st.session_state.cart]),  # Store as string for CSV
                            'Attachments': str(attachment_paths) if attachment_paths else '',
                            'CreatedBy': st.session_state.username
                        }
                        
                        # Add to orders DataFrame
                        new_order_df = pd.DataFrame([order_data])
                        if orders_df.empty:
                            orders_df = new_order_df
                        else:
                            orders_df = pd.concat([orders_df, new_order_df], ignore_index=True)
                        
                        if save_orders(orders_df):
                            # Send email notification based on workflow
                            try:
                                if needs_sgf:
                                    # Send SGF notification
                                    send_sgf_notification()
                                else:
                                    # Send Admin Level 1 notification
                                    send_approval_notification(admin_level=1)
                            except Exception as e:
                                # Don't show error to user, just log it
                                print(f"Error sending notification email: {e}")
                            
                            # Clear cart and form state
                            st.session_state.cart = []
                            st.session_state.order_uploaded_files = []  # Clear uploaded files
                            st.session_state.last_submitted_order_id = order_id
                            st.session_state.order_submission_success = True
                            status_message = "Pending for SGF approval" if needs_sgf else "Pending"
                            if attachment_paths:
                                st.success(f"Order {order_id} submitted successfully with {len(attachment_paths)} attachment(s)! ✅ Status: {status_message}. Check Order History to view your order.")
                            else:
                                st.success(f"Order {order_id} submitted successfully! ✅ Status: {status_message}. Check Order History to view your order.")
                            st.balloons()
                            st.rerun()
                        else:
                            st.error("Error saving order. Please try again.")
    
    with tab3:
        st.header("Order History")
        
        # Show success message if order was just submitted
        if st.session_state.get('order_submission_success', False) and st.session_state.get('last_submitted_order_id'):
            st.success(f"🎉 Your order {st.session_state.last_submitted_order_id} has been successfully submitted! Status: Pending (awaiting finance review).")
            st.session_state.order_submission_success = False  # Reset flag after showing message
        
        orders_df = load_orders()
        
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
                    
                    # Build expander caption with disapproved items info
                    if disapproved_count > 0:
                        # Check if status already includes disapproved info
                        if 'removed/disapproved' not in status.lower() and 'disapproved' not in status.lower():
                            expander_caption = f"Order {row['OrderID']} - {status} with {disapproved_count} removed/disapproved item(s) - {row['OrderDate']}"
                        else:
                            expander_caption = f"Order {row['OrderID']} - {status} - {row['OrderDate']}"
                    else:
                        expander_caption = f"Order {row['OrderID']} - {status} - {row['OrderDate']}"
                    
                    with st.expander(expander_caption):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Client:** {row['ClientName']}")
                            st.markdown(f"**Date:** {row['OrderDate']}")
                            st.markdown(f"**Status:** {row['Status']}")
                            st.markdown(f"**Total Amount:** {float(row.get('TotalAmount', 0)):.2f}")
                            
                            # Show approval status for clients
                            approved_by_l1 = row.get('ApprovedByLevel1', '')
                            approved_date_l1 = row.get('ApprovedDateLevel1', '')
                            approved_by_l2 = row.get('ApprovedByLevel2', '')
                            approved_date_l2 = row.get('ApprovedDateLevel2', '')
                            
                            if approved_by_l1:
                                st.info(f"✅ Approved by Level 1: {approved_by_l1} ({approved_date_l1})")
                            if approved_by_l2:
                                st.success(f"✅ Fully Approved by Level 2: {approved_by_l2} ({approved_date_l2})")
                            elif approved_by_l1 and not approved_by_l2:
                                st.warning("⏳ Waiting for Level 2 approval")
                        with col2:
                            st.markdown(f"**Rep:** {row['RepName']} ({row['RepCode']})")
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
    
    # Add CSS to center button icons and style table
    st.markdown("""
        <style>
        /* 1. Target the button container to center it in the column */
        div.stButton {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }

        /* 2. Target the button itself - default styling for all buttons */
        div.stButton > button {
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }

        /* 3. Icon-only buttons in table (target by key pattern) - apply special styling */
        div.stButton > button[key*="view_details"],
        div.stButton > button[key*="print_"] {
            padding: 0px !important;
            width: 100% !important;
            height: 40px !important;
        }

        /* 4. Target the text/emoji wrapper inside icon-only buttons (Crucial) */
        div.stButton > button[key*="view_details"] p,
        div.stButton > button[key*="print_"] p {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            margin: 0px !important;
            line-height: 1 !important;
            font-size: 1.2rem !important;
        }
        
        /* 5. Ensure text buttons have proper padding (exclude icon-only buttons) */
        div.stButton > button:not([key*="view_details"]):not([key*="print_"]) {
            padding: 0.5rem 1rem !important;
        }
        /* Center button icons/text - but allow normal padding for text buttons */
        button[kind="secondary"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
        }
        button[kind="primary"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-align: center !important;
        }
        /* Make table text smaller */
        div[data-testid="stVerticalBlock"] > div[style*="flex"] {
            font-size: 0.85rem !important;
        }
        /* Make all text in table rows smaller */
        .stMarkdown, .stWrite {
            font-size: 0.85rem !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
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
            st.session_state.show_submit_order_dialog = False
            st.session_state.show_order_details_dialog = False
            st.rerun()
        
        st.markdown("---")
        st.header("Admin Functions")
        if st.button("🔄 Sync Products from SQL Server", use_container_width=True):
            st.session_state.show_sync = True
            st.rerun()
        
        # Show "List of Accounts" button only for Admin Level 2
        if admin_level == 2:
            st.markdown("---")
            if st.button("📋 List of Accounts", use_container_width=True):
                st.session_state.show_accounts_dialog = True
                st.rerun()

        # Show "Manage Users" and "Manage Products" for Admin Level 1 or Admin / Finance Staff (excluding view-only)
        # Allow Admin Level 2 to also access these functions if they are not view-only
        # Fallback: Handle both old "Finance Staff" and new "Admin / Finance Staff" role names
        user_role = st.session_state.get('user_role', '')
        is_finance_staff = user_role == 'Admin / Finance Staff' or user_role == 'Finance Staff'
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
    
    # Show accounts dialog if triggered (only for Admin Level 2)
    if st.session_state.get('show_accounts_dialog', False) and admin_level == 2:
        accounts_dialog()
    
    # Show add account dialog if triggered (only for Admin Level 2)
    if st.session_state.get('show_add_account_dialog', False) and admin_level == 2:
        add_account_dialog()

    # Dialog state management - ensure only one dialog can be open at a time
    # Reset dialog states if multiple are set (shouldn't happen, but safety check)
    dialog_states = [
        st.session_state.get('show_manage_users_dialog', False),
        st.session_state.get('show_manage_products_dialog', False),
        st.session_state.get('show_accounts_dialog', False),
        st.session_state.get('show_add_account_dialog', False)
    ]
    active_dialogs = sum(dialog_states)
    
    # If more than one dialog state is True, reset all except the first one found
    if active_dialogs > 1:
        if st.session_state.get('show_manage_users_dialog', False):
            st.session_state.show_manage_products_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
        elif st.session_state.get('show_manage_products_dialog', False):
            st.session_state.show_manage_users_dialog = False
            st.session_state.show_accounts_dialog = False
            st.session_state.show_add_account_dialog = False
    
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
    admin_level_display = f" (Level {admin_level})" if admin_level else ""
    if view_only:
        st.info("🔒 View-only mode: approvals and edits are disabled.")
    
    # Main Content - Tabs
    tab1, tab2, tab3 = st.tabs(["📋 Pending Orders Review", "📊 All Orders", "📜 Approval History"])
    
    with tab1:
        st.header(f"Pending Orders - Review & Approve{admin_level_display}")
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
            if admin_level == 1:
                # Admin Level 1 sees orders that are Pending (not yet reviewed by Level 1)
                # Also show "Pending for SGF" so they can see status, but can't approve until SGF approves
                pending_orders = orders_df[
                    ((orders_df['Status'] == 'Pending') & (orders_df['ApprovedByLevel1'] == '')) |
                    (orders_df['Status'] == 'Pending for SGF')
                ].copy()
            elif admin_level == 2:
                # Admin Level 2 sees orders that have been approved by Level 1 but not yet by Level 2
                pending_orders = orders_df[
                    (orders_df['Status'] == 'Pending') & 
                    (orders_df['ApprovedByLevel1'] != '') &
                    (orders_df['ApprovedByLevel2'] == '')
                ].copy()
            else:
                # Fallback for users without admin level (old admin accounts)
                pending_orders = orders_df[orders_df['Status'] == 'Pending'].copy()
            
            if pending_orders.empty:
                st.success("No pending orders. All orders have been reviewed.")
            else:
                # Sort by OrderDate
                pending_orders = pending_orders.sort_values('OrderDate', ascending=True)
                
                for idx, row in pending_orders.iterrows():
                    with st.container():
                        st.markdown(f"### Order {row['OrderID']}")
                        
                        # Show approval status
                        approved_by_l1 = row.get('ApprovedByLevel1', '')
                        approved_date_l1 = row.get('ApprovedDateLevel1', '')
                        approved_by_l2 = row.get('ApprovedByLevel2', '')
                        approved_date_l2 = row.get('ApprovedDateLevel2', '')
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.markdown(f"**Client:** {row['ClientName']}")
                            st.markdown(f"**Rep:** {row['RepName']} ({row['RepCode']})")
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
                                                        orders_df.at[order_idx[0], 'Status'] = f'Pending but {disapproved_count} Item(s) removed/disapproved'
                                                    else:
                                                        orders_df.at[order_idx[0], 'Status'] = 'Pending'  # Still pending for Level 2
                                                    if save_orders(orders_df):
                                                        # Send email notification to Admin Level 2 about new pending approvals
                                                        try:
                                                            send_approval_notification(admin_level=2)
                                                        except Exception as e:
                                                            # Don't show error to user, just log it
                                                            print(f"Error sending notification email: {e}")
                                                        
                                                        if disapproved_count > 0:
                                                            st.success(f"Order {row['OrderID']} approved by Level 1! {disapproved_count} item(s) removed/disapproved. Waiting for Level 2 approval.")
                                                        else:
                                                            st.success(f"Order {row['OrderID']} approved by Level 1! Waiting for Level 2 approval.")
                                                        st.rerun()
                                                elif admin_level == 2:
                                                    # Level 2 approval - final approval
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
                                                        # Order went through SGF workflow, increment count
                                                        try:
                                                            increment_sgf_count(client_name)
                                                        except Exception as e:
                                                            print(f"Error incrementing SGF_count: {e}")
                                                    
                                                    if save_orders(orders_df):
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
                                
                                # Only show "Unlock for Edit" for Admin Level 1
                                if admin_level == 1:
                                    if st.button("🔓 Unlock for Edit", key=f"unlock_{row['OrderID']}"):
                                        # Trigger unlock dialog with reason input
                                        st.session_state.unlock_order_id = row['OrderID']
                                        st.session_state.show_unlock_dialog = True
                                        st.rerun()
                                
                                # Re-send Notifications button (only visible for administrator or Admin role)
                                current_username = st.session_state.get('username', '')
                                current_role = st.session_state.get('user_role', '')
                                is_admin_or_administrator = (current_username == 'administrator') or (current_role == 'Admin')
                                
                                if is_admin_or_administrator:
                                    if st.button("📧 Re-send Notifications", key=f"resend_notif_{row['OrderID']}", help="Re-send email notification for this order"):
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
                            st.markdown(f"**Rep Company:** {row.get('RepCompany', 'N/A')}")
                            st.markdown(f"**Rep Dept/DSM:** {row.get('RepDept', 'N/A')}")
                            st.markdown(f"**Rep Area/PMR:** {row.get('RepArea', 'N/A')}")
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
    
    with tab2:
        st.header("All Orders")
        orders_df = load_orders()
        
        if orders_df.empty:
            st.info("No orders found.")
        else:
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox("Filter by Status", 
                                            ['All'] + list(orders_df['Status'].unique()))
            with col2:
                date_from = st.date_input("From Date", value=pd.to_datetime(orders_df['OrderDate']).min().date() 
                                         if not orders_df.empty else datetime.now().date())
            with col3:
                date_to = st.date_input("To Date", value=datetime.now().date())
            
            # Reset dialog state if filters changed (not triggered by View Details button)
            # This prevents dialog from appearing when filters are changed
            current_date_from = str(date_from)
            current_date_to = str(date_to)
            current_status_filter = str(status_filter)
            
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
            if status_filter != 'All':
                filtered_orders = filtered_orders[filtered_orders['Status'] == status_filter]
            
            filtered_orders['OrderDate_dt'] = pd.to_datetime(filtered_orders['OrderDate'])
            filtered_orders = filtered_orders[
                (filtered_orders['OrderDate_dt'].dt.date >= date_from) &
                (filtered_orders['OrderDate_dt'].dt.date <= date_to)
            ]
            
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
                # Prepare CSV data for download (using filtered orders, sorted by OrderID)
                filtered_sorted = filtered_orders.copy().sort_values('OrderID')
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
                                # Show status with print info if printed
                                status_text = str(value) if pd.notna(value) else 'N/A'
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
    
    with tab3:
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
                    
                    # Build expander caption with disapproved items info
                    if disapproved_count > 0:
                        # Check if status already includes disapproved info
                        if 'removed/disapproved' not in status.lower() and 'disapproved' not in status.lower():
                            expander_caption = f"Order {row['OrderID']} - {status} with {disapproved_count} removed/disapproved item(s) - {row['OrderDate']}"
                        else:
                            expander_caption = f"Order {row['OrderID']} - {status} - {row['OrderDate']}"
                    else:
                        expander_caption = f"Order {row['OrderID']} - {status} - {row['OrderDate']}"
                    
                    with st.expander(expander_caption):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Client:** {row['ClientName']}")
                            st.markdown(f"**Date:** {row['OrderDate']}")
                            st.markdown(f"**Status:** {row['Status']}")
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
                            st.markdown(f"**Rep:** {row['RepName']} ({row['RepCode']})")
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
            st.session_state.show_submit_order_dialog = False
            st.session_state.show_order_details_dialog = False
            st.rerun()
    
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
                        st.markdown(f"**Rep:** {row['RepName']} ({row['RepCode']})")
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
                                    # Mark as approved by SGF, change status to Pending for Admin Level 1
                                    orders_df.at[order_idx[0], 'ApprovedBySGF'] = st.session_state.username
                                    orders_df.at[order_idx[0], 'ApprovedDateSGF'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    orders_df.at[order_idx[0], 'Status'] = 'Pending'
                                    
                                    if save_orders(orders_df):
                                        # Send email notification to Admin Level 1
                                        try:
                                            send_approval_notification(admin_level=1)
                                        except Exception as e:
                                            print(f"Error sending notification email: {e}")
                                        
                                        st.success(f"Order {row['OrderID']} approved by SGF Manager! Proceeding to Admin Level 1.")
                                        st.rerun()
                        
                        with col_disapprove:
                            if st.button("❌ Disapprove", key=f"sgf_disapprove_{row['OrderID']}"):
                                st.session_state.disapprove_order_id = row['OrderID']
                                st.session_state.show_disapprove_dialog = True
                                st.rerun()
                        
                        # Re-send Notifications button (only visible for administrator or Admin role)
                        current_username = st.session_state.get('username', '')
                        current_role = st.session_state.get('user_role', '')
                        is_admin_or_administrator = (current_username == 'administrator') or (current_role == 'Admin')
                        
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
                        st.markdown(f"**Rep Company:** {row.get('RepCompany', 'N/A')}")
                        st.markdown(f"**Rep Dept/DSM:** {row.get('RepDept', 'N/A')}")
                        st.markdown(f"**Rep Area/PMR:** {row.get('RepArea', 'N/A')}")
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
                              help="Format: server\\instance or IP address")
        database = st.text_input("Database Name", value="YourDatabase")
        username = st.text_input("SQL Username", value="sa")
        password = st.text_input("SQL Password", type="password")
        table_name = st.text_input("Table Name", value="Products",
                                   help="Name of the table containing product data")
        
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
    if not st.session_state.authenticated:
        login_page()
    else:
        user_role = st.session_state.user_role
        if user_role == 'Sales Rep':
            sales_rep_interface()
        elif user_role == 'Admin / Finance Staff' or user_role == 'Finance Staff':
            # Fallback for both old and new role names
            finance_staff_interface()
        elif user_role == 'SGF Manager':
            sgf_manager_interface()
        else:
            st.error("Unknown user role. Please contact administrator.")

if __name__ == "__main__":
    main()
