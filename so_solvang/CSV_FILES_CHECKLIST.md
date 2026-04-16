# CSV Files Checklist for Deployment

## Required CSV Files

### 1. `sales_order_LIST_OF_ACCOUNTS.csv` ⚠️ **REQUIRED**
- **Purpose**: Contains client/account information needed for order submission
- **Status**: Must be uploaded before application can accept orders
- **Encoding**: UTF-8 or Latin-1
- **Location**: Same directory as `Sales_Order_Inventory_App.py`
- **Auto-created**: No - must be provided

### 2. `products.csv` ✅ Optional (Auto-created)
- **Purpose**: Product catalog with product information
- **Status**: Can be auto-created by syncing from SQL Server (Admin tab)
- **Columns**: ProductCode, ProductName, Price, Quantity, etc.
- **Location**: Same directory as `Sales_Order_Inventory_App.py`
- **Auto-created**: Yes - will be created when syncing from SQL Server or manually adding products

### 3. `orders.csv` ✅ Optional (Auto-created)
- **Purpose**: Stores all order submissions
- **Status**: Will be created automatically when first order is submitted
- **Location**: Same directory as `Sales_Order_Inventory_App.py`
- **Auto-created**: Yes - created on first order submission

### 4. `users.csv` ✅ Optional
- **Purpose**: Additional user accounts beyond hardcoded ones
- **Status**: Optional - default users are hardcoded in the application
- **Location**: Same directory as `Sales_Order_Inventory_App.py`
- **Auto-created**: Yes - can be created if you want to add users via CSV

## Other Files

### `Send.txt` ✅ Optional
- **Purpose**: Text file (if used by the application)
- **Status**: Optional
- **Location**: Same directory as `Sales_Order_Inventory_App.py`

## Upload Checklist

Before deploying, ensure you have:

- [ ] `Sales_Order_Inventory_App.py` - Main application
- [ ] `requirements.txt` - Dependencies
- [ ] `product_images/` folder - Product images
- [ ] `sales_order_LIST_OF_ACCOUNTS.csv` - **REQUIRED** - Accounts list
- [ ] `products.csv` - If you have existing product data (optional)
- [ ] `orders.csv` - If you have existing orders (optional)
- [ ] `users.csv` - If you have additional users (optional)
- [ ] `Send.txt` - If used (optional)

## Quick Upload Commands

```powershell
# Required files
scp "Sales_Order_Inventory_App.py" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp "requirements.txt" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp -r "product_images" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp "sales_order_LIST_OF_ACCOUNTS.csv" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/

# Optional files (if they exist)
scp "products.csv" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp "orders.csv" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp "users.csv" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
scp "Send.txt" rgbadmins@server:/home/rgbadmins/Streamlit_Apps/so_solvang/
```

## Notes

1. **`sales_order_LIST_OF_ACCOUNTS.csv` is critical** - Without it, users won't be able to submit orders as the account list is required.

2. **`products.csv`** can be created by:
   - Syncing from SQL Server via the Admin tab in the application
   - Manually creating the file with proper columns
   - Importing from an existing source

3. **`orders.csv`** will be automatically created when the first order is submitted through the application.

4. **File permissions**: Ensure all CSV files have read/write permissions:
   ```bash
   chmod 644 *.csv
   ```

5. **File encoding**: If you encounter encoding issues with `sales_order_LIST_OF_ACCOUNTS.csv`, ensure it's saved as UTF-8 or Latin-1.

