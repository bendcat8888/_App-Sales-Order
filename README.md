# 🛒 Sales Order & Management System (Solvang)
**A Full-Stack E-Commerce & Workflow Automation Solution for Enterprise Logistics**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

## 🛠 Tech Stack

| Category | Tools |
| :--- | :--- |
| **Frontend/UI** | **Streamlit** (Custom Cart UI, Multi-step Modals, Image Gallery) |
| **Backend** | **Python 3.12** (Object-Oriented Database Management) |
| **Database** | **SQLite** (Primary) + **MS SQL Server** (Product Sync via pyodbc) |
| **Automation** | **Background Schedulers** (Automated Email Reminders & Order Expiry) |
| **Communication** | **SMTP/SSL Integration** (Real-time Gmail notifications) |
| **Deployment** | Linux/Ubuntu (Bash scripts & `nohup` process management) |

---

## 🎯 Project Overview
This system is an end-to-end **Sales Order (SO) Platform** designed for Solvang. It manages the entire lifecycle of a sale—from product browsing and cart management to multi-level administrative approvals and final finance review.

### 🌟 High-Level Capabilities
* **Dynamic Product Catalog:** Interactive inventory browsing with high-resolution image support.
* **Complex Cart Logic:** SKU-level remarks, inventory checking, and seamless order creation.
* **Automated Approval Workflow:** A 3-tier approval hierarchy (SGF → Admin L1 → Admin L2) ensuring corporate compliance.
* **Smart Scheduling:** A custom background process (`notification_scheduler.py`) that monitors order age, sends 16-hour reminders, and auto-cancels expired booking requests.

---

## 🚀 Key Professional Features

### 📦 Order & Inventory Management
* **Cart-to-Order Pipeline:** Built a robust shopping cart experience within the Streamlit framework.
* **Data Synchronization:** Implemented a sync engine to pull real-time product data from **MS SQL Server** into the local SQLite instance.
* **Attachment Engine:** Supports PDF and Image uploads for order documentation and financial proof.

### 📧 Automated Notification System
* **Gmail SMTP Integration:** Real-time email triggers for status updates and approvals.
* **Admin Control Panel:** A "Notification Management" dashboard to toggle global alerts, manage CC lists, and audit send logs.

### 💼 Finance & Admin Suite
* **Audit Trails:** Detailed history tracking for every order status change.
* **Review Actions:** Dedicated Finance module for bulk exports, filtering, and final transaction review.

---

## ⚙️ Development & Setup

### Requirements
- **Python 3.10+**
- **ODBC Driver 18** (For optional SQL Server Sync)

### Quick Start
```bash
# 1. Setup Environment
python -m venv .venv
source .venv/bin/activate  # .\.venv\Scripts\Activate.ps1 on Windows

# 2. Install Dependencies
pip install -r Requirements.txt

# 3. Launch App
streamlit run Sales_Order_Inventory_App.py
```

Background Scheduler
To run the automated reminder and auto-cancel engine:

```Bash
python notification_scheduler.py
```
---
## 🔒 Security & Secrets Management
This repository is built with Security-First principles. Credentials and sensitive configuration are strictly separated from the logic:

- **Credential Masking:** SMTP and DB secrets are managed via `Send.txt` or `.streamlit/secrets.toml`.

- **Git Integrity:** All sensitive files are excluded via `.gitignore` to prevent accidental exposure of corporate assets.
---

## 📜 License & Intellectual Property
**Copyright (c) 2026 Benedic Cater / InnoGen Pharmaceuticals Inc. (Solvang)**

**All Rights Reserved.**
This repository is published for **portfolio review and technical demonstration purposes only.**

**Strict Restrictions:**
- **No Reproduction:** No part of this code may be copied, modified, or distributed.
- **Brand Protection:** Use of the "InnoGen" or "Solvang" name, branding, or logos is strictly prohibited.
- **Data Privacy:** Use of any proprietary data or business logic contained herein for commercial or personal projects is strictly prohibited.

_For professional inquiries or permission requests, please contact Benedic Cater._
