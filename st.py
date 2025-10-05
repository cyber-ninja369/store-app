import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
from io import StringIO, BytesIO

# ======================
# Database Setup
# ======================
def init_db():
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item TEXT, category TEXT, 
                  quantity INTEGER, price REAL,
                  min_stock INTEGER DEFAULT 5)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sales
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  item_id INTEGER, quantity INTEGER,
                  sale_price REAL, sale_date TEXT,
                  FOREIGN KEY(item_id) REFERENCES inventory(id))''')
    
    try:
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", 
                 ('admin', make_hashes('admin123')))
    except:
        pass
    
    conn.commit()
    conn.close()

# ======================
# Authentication
# ======================
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

def create_user(username, password):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users VALUES (?,?)', 
                 (username, make_hashes(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    data = c.fetchone()
    conn.close()
    return data and check_hashes(password, data[1])

# ======================
# Inventory Functions
# ======================
def get_inventory():
    conn = sqlite3.connect('inventory.db')
    df = pd.read_sql('SELECT * FROM inventory', conn)
    conn.close()
    return df

def add_item(item, category, quantity, price, min_stock=5):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('INSERT INTO inventory (item, category, quantity, price, min_stock) VALUES (?,?,?,?,?)',
              (item, category, quantity, price, min_stock))
    conn.commit()
    conn.close()

def update_item(item_id, item, category, quantity, price, min_stock):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''UPDATE inventory SET item=?, category=?, quantity=?, price=?, min_stock=?
                 WHERE id=?''', (item, category, quantity, price, min_stock, item_id))
    conn.commit()
    conn.close()

def delete_item(item_id):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('DELETE FROM inventory WHERE id=?', (item_id,))
    conn.commit()
    conn.close()

# ======================
# Sales Functions
# ======================
def record_sale(item_id, quantity, sale_price):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('UPDATE inventory SET quantity = quantity - ? WHERE id = ?', (quantity, item_id))
    sale_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('INSERT INTO sales (item_id, quantity, sale_price, sale_date) VALUES (?,?,?,?)',
              (item_id, quantity, sale_price, sale_date))
    conn.commit()
    conn.close()

def get_sales():
    conn = sqlite3.connect('inventory.db')
    df = pd.read_sql('''SELECT s.id, i.item, s.quantity, s.sale_price, s.sale_date
                        FROM sales s JOIN inventory i ON s.item_id = i.id''', conn)
    conn.close()
    return df

# ======================
# Authentication Page
# ======================
def auth_page():
    st.title("🔐 Store Inventory Login")
    
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'show_signup' not in st.session_state:
        st.session_state.show_signup = False
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type='password')
            
            if st.form_submit_button("Login"):
                if login_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("signup_form"):
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type='password')
            confirm_password = st.text_input("Confirm Password", type='password')
            
            if st.form_submit_button("Create Account"):
                if new_password != confirm_password:
                    st.error("Passwords don't match!")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    if create_user(new_username, new_password):
                        st.success("Account created! Please login.")
                        st.session_state.show_signup = False
                    else:
                        st.error("Username already exists")

# ======================
# Main Application
# ======================
def main_app():
    st.title("📊 Store Inventory Management System")
    
    inventory = get_inventory()
    menu = ["Inventory", "Sales", "Analytics"]
    choice = st.sidebar.selectbox("Menu", menu)
    
    if choice == "Inventory":
        st.header("Inventory Management")
        
        with st.expander("Add New Item"):
            with st.form("add_form", clear_on_submit=True):
                item = st.text_input("Item Name*")
                category = st.selectbox("Category*", 
                    ["protein", "perishables ()", "juice(per bottle)", "spices (in grams)", "Other"])
                quantity = st.number_input("Quantity", min_value=0)
                price = st.number_input("Price(in naira)*", min_value=0.0, step=0.01)
                min_stock = st.number_input("Min Stock*", min_value=1, value=5)
                
                if st.form_submit_button("Add Item"):
                    if item:
                        add_item(item, category, quantity, price, min_stock)
                        st.success("Item added!")
                        inventory = get_inventory()
                    else:
                        st.error("Item name required")
        
        if inventory is not None and not inventory.empty:
            low_stock = inventory[inventory['quantity'] < inventory['min_stock']]
            if not low_stock.empty:
                st.warning("⚠️ Low Stock Alert!")
                st.dataframe(low_stock[['item', 'quantity', 'min_stock']])
            
            st.subheader("Edit Inventory")
            edit_choice = st.selectbox("Select Item", inventory['item'])
            item_data = inventory[inventory['item'] == edit_choice].iloc[0]
            
            with st.form("edit_form"):
                new_item = st.text_input("Name", value=item_data['item'])
                
                categories = ["protein(kg)", "perishables(kg)", "juice(bottle)", "groceries (kg)", "Other"]
                current_category = item_data['category']
                default_index = categories.index(current_category) if current_category in categories else 4
                
                new_category = st.selectbox("Category", categories, index=default_index)
                new_quantity = st.number_input("Quantity", min_value=0, value=item_data['quantity'])
                new_price = st.number_input("Price", min_value=0.0, step=0.01, value=item_data['price'])
                new_min_stock = st.number_input("Min Stock", min_value=1, value=item_data['min_stock'])
                
                col1, col2 = st.columns(2)
                with col1:
                    update_btn = st.form_submit_button("Update Item")
                with col2:
                    delete_btn = st.form_submit_button("Delete Item")
                
                if update_btn:
                    update_item(item_data['id'], new_item, new_category, 
                              new_quantity, new_price, new_min_stock)
                    st.success("Item updated!")
                    st.rerun()
                    
                if delete_btn:
                    delete_item(item_data['id'])
                    st.success("Item deleted!")
                    st.rerun()
            
            st.dataframe(inventory.drop(columns=['id']))
            
            # Export Functionality
            st.subheader("Export Options")
            
            # TXT Export
            txt_buffer = StringIO()
            inventory.to_string(txt_buffer, index=False)
            txt_data = txt_buffer.getvalue()
            
            # Excel Export
            try:
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    inventory.to_excel(writer, index=False, sheet_name='Inventory')
                    writer.close()
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📝 Export as TXT",
                        data=txt_data,
                        file_name="inventory_report.txt",
                        mime="text/plain"
                    )
                with col2:
                    st.download_button(
                        label="💾 Export as Excel",
                        data=excel_buffer,
                        file_name="inventory_report.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except ImportError:
                st.warning("Excel export requires openpyxl. Install with: pip install openpyxl")
                st.download_button(
                    label="📝 Export as TXT",
                    data=txt_data,
                    file_name="inventory_report.txt",
                    mime="text/plain"
                )
        
        else:
            st.info("No items in inventory")
    
    elif choice == "Sales":
        st.header("Sales Tracking")
        inventory = get_inventory()
        
        if not inventory.empty:
            with st.form("sale_form"):
                item = st.selectbox("Item", inventory['item'])
                item_id = inventory[inventory['item'] == item].iloc[0]['id']
                max_qty = inventory[inventory['item'] == item].iloc[0]['quantity']
                quantity = st.number_input("Quantity", min_value=1, max_value=max_qty)
                sale_price = st.number_input("Sale Price", min_value=0.0, step=0.01,
                    value=float(inventory[inventory['item'] == item].iloc[0]['price']))
                
                if st.form_submit_button("Record Sale"):
                    record_sale(item_id, quantity, sale_price)
                    st.success("Sale recorded!")
            
            sales = get_sales()
            if not sales.empty:
                st.subheader("Sales History")
                st.dataframe(sales)
                
                sales['sale_date'] = pd.to_datetime(sales['sale_date'])
                daily_sales = sales.groupby(sales['sale_date'].dt.date)['sale_price'].sum()
                st.bar_chart(daily_sales)
            else:
                st.info("No sales recorded")
        else:
            st.warning("No items in inventory")
    
    elif choice == "Analytics":
        st.header("Inventory Analytics")
        inventory = get_inventory()
        
        if not inventory.empty:
            inventory['total_value'] = inventory['quantity'] * inventory['price']
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Stock by Category")
                st.bar_chart(inventory.groupby('category')['quantity'].sum())
            with col2:
                st.subheader("Value by Category")
                st.bar_chart(inventory.groupby('category')['total_value'].sum())
            
            st.subheader("Price Distribution")
            st.bar_chart(inventory['price'].value_counts())
        else:
            st.warning("No data to analyze")

# ======================
# App Initialization
# ======================
init_db()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    main_app()
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
else:
    auth_page()