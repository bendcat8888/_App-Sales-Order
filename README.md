# Sales Order App & Management System (Solvang)

A Streamlit-based Sales Order (SO) Management application for Solvang that supports product browsing, cart-based ordering, multi-step approvals, finance review, attachments, and automated email notifications/reminders.

---

## Highlights

- **Product Catalog** with images
- **Shopping Cart** + SKU-level Notes/Remarks
- **Sales Orders** creation, status tracking, and audit trail
- **Approval Workflow** (SGF → Admin Level 1 Ethical → Admin Level 2)
- **Finance Review & Management** (filters, exports, review actions)
- **Booking Requests** workflow (incl. reminders/auto-cancel via scheduler)
- **Attachments** (images + PDFs) for orders/requests
- **Email Notifications** + Admin “Notification Management” (toggle, CC list, logs)

---

## Tech Stack

- **Python + Streamlit**
- **SQLite** database: `sales_order_inventory.db` (via `db_manager.py`)
- Optional: **SQL Server sync** for products using `pyodbc` (ODBC driver required)

---

## Repository Structure (key files)

- `Sales_Order_Inventory_App.py` — main Streamlit application entrypoint
- `db_manager.py` — SQLite models + database access layer
- `notification_scheduler.py` — background scheduler (reminders / auto-cancel)
- `products.csv`, `orders.csv`, `sales_order_LIST_OF_ACCOUNTS.csv` — CSV data files used by the app
- `product_images/` — product image assets
- `notification_enabled.txt` — global notification toggle persistence
- `email_notifications.log` — email send attempt logs (app + scheduler)
- `DEPLOYMENT_GUIDE_UBUNTU.md`, `QUICK_START.md`, `RUN_WITH_NOHUP.md` — deployment references

---

## Quick Start (Local)

### 1) Create and activate a virtual environment (recommended)

```powershell
cd "c:\Users\Benedic Cater\SynologyDrive\Software Development\Python Codes\_App Sales Order\so_solvang"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```powershell
pip install -r Requirements.txt
```

### 3) Run the app

```powershell
streamlit run Sales_Order_Inventory_App.py
```

---

## Email Notifications

This app sends email via **Gmail SMTP over SSL** (`smtp.gmail.com:465`).

### Send.txt (required for sending emails)

The application reads credentials from `Send.txt` located in the app directory. Supported formats:

**Option A (recommended):**
- Line 1 = Gmail account (SMTP username)
- Line 2 = Gmail App Password (SMTP password)

**Option B:**
- Line 1 only = Gmail App Password
- In this case, `GMAIL_ACCOUNT` is used from `Sales_Order_Inventory_App.py`

Example (DO NOT commit this file):
```text
your_email@gmail.com
your_gmail_app_password_here
```

### Enable/Disable notifications

Notifications can be toggled from the app’s **Notification Management** dialog (Super Admin). The state is persisted in:
- `notification_enabled.txt`

---

## Scheduler (Reminders / Auto-Cancel)

`notification_scheduler.py` handles background checks such as:
- Pending reminders (e.g., 16-hour reminders)
- Booking request auto-cancel (e.g., 24-hour rule, depending on configuration)

The scheduler respects the same notification toggle (`notification_enabled.txt`).

Run manually (example):
```powershell
python notification_scheduler.py
```

For Linux deployment, see:
- `QUICK_START.md`
- `DEPLOYMENT_GUIDE_UBUNTU.md`

---

## SQL Server Product Sync (Optional)

The app includes a “Sync Products from SQL Server” feature that:
- Connects using `pyodbc`
- Pulls from a table you specify
- Writes output to `products.csv`

You must install the proper ODBC driver on the host.

---

## Data Storage

- Primary storage is **SQLite**:
  - `sales_order_inventory.db`
- CSV files are also used for loading/migration and operational data depending on the workflow:
  - `products.csv`, `orders.csv`, `users.csv` (migrated to SQLite on first run if present), etc.

---

## Security / Secrets (IMPORTANT)

Do **NOT** commit credentials to GitHub.

These files must be local-only:
- `.streamlit/secrets.toml`
- `Send.txt`

Recommended `.gitignore` entries:
```gitignore
.streamlit/secrets.toml
Send.txt
```

If secrets were ever committed, treat them as compromised:
- Rotate passwords/tokens immediately
- Remove them from Git history using a history rewrite tool (e.g., `git filter-repo`)

---

## Support / Maintenance Notes

- For email-related issues, check:
  - `email_notifications.log`
  - Notification Management → Users Without Email / Send Log
- For scheduler status, check:
  - `notification_scheduler_heartbeat.txt` (if enabled in your deployment)

---
