import os
import sqlite3
import pandas as pd
import streamlit as st

# Securely retrieve the API Key from Streamlit Secrets
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

# Configure Page Layout
st.set_page_config(page_title="OSU P-Card Audit Portal", page_icon="🔍", layout="wide")

DB_PATH = "pcards.db"

def run_query(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=params)

# Header
st.title("🔍 Oklahoma State University — P-Card Audit Portal")
st.markdown("---")

# Navigation Tabs
tab1, tab2 = st.tabs(["💬 Tab 1: Natural Language Query", "🚨 Tab 2: Prohibited Purchases Dashboard"])

# ==============================================================================
# TAB 1: NATURAL LANGUAGE AUDIT QUERY
# ==============================================================================
with tab1:
    st.header("Natural Language Audit Assistant")
    st.markdown("""
    Ask questions in plain English about the 2014 P-Card dataset:
    *Examples:*
    - *Show top cardholders by spending*
    - *Show vendor totals over $50,000*
    """)
    
    user_prompt = st.text_input("Enter your audit question:", placeholder="e.g., top 10 transactions by amount")
    
    if st.button("Run Query", key="nl_search"):
        if not user_prompt:
            st.warning("Please enter a question first.")
        else:
            prompt_lower = user_prompt.lower()
            if "top" in prompt_lower and "cardholder" in prompt_lower:
                sql_generated = "SELECT FullName, SUM(Amount) AS TotalSpent FROM pcards WHERE Year = 2014 GROUP BY FullName ORDER BY TotalSpent DESC LIMIT 10;"
            elif "vendor" in prompt_lower:
                sql_generated = "SELECT Vendor, COUNT(*) AS TxCount, SUM(Amount) AS TotalSpent FROM pcards WHERE Year = 2014 GROUP BY Vendor ORDER BY TotalSpent DESC LIMIT 10;"
            elif "5000" in prompt_lower or "over $5,000" in prompt_lower:
                sql_generated = "SELECT Amount, FullName, Vendor, Description, TransactionDate FROM pcards WHERE Year = 2014 AND Amount > 5000 ORDER BY Amount DESC;"
            else:
                sql_generated = f"SELECT FullName, Vendor, Amount, TransactionDate, Description, MCC FROM pcards WHERE Year = 2014 AND (LOWER(Description) LIKE '%{user_prompt}%' OR LOWER(Vendor) LIKE '%{user_prompt}%') LIMIT 50;"
            
            st.subheader("Generated SQL Query")
            st.code(sql_generated, language="sql")
            
            try:
                df_result = run_query(sql_generated)
                st.subheader(f"Results ({len(df_result)} records found)")
                st.dataframe(df_result, use_container_width=True)
            except Exception as e:
                st.error(f"Error executing query: {e}")

# ==============================================================================
# TAB 2: PROHIBITED PURCHASES DASHBOARD
# ==============================================================================
with tab2:
    st.header("Prohibited & Restricted Purchases Examiner")
    
    with st.expander("📖 Instructions for Auditors (Click to expand)", expanded=True):
        st.markdown("""
        **Policy Guidelines & Audit Steps:**
        1. **Select Year**: Filter the entire dataset by audit fiscal year (default: 2014).
        2. **Description Search**: Scans purchase descriptions for prohibited item keywords (e.g., alcohol, gas, gift cards).
        3. **Vendor Search**: Scans merchant names for unauthorized entities (e.g., post office, liquor store).
        4. **Follow-Up Action**: Export results or note transaction details (`FullName`, `Vendor`, `Amount`, `Date`) to request receipts.
        """)
    
    st.markdown("---")
    
    selected_year = st.selectbox("Select Audit Year:", [2014], index=0)
    
    st.subheader("Search Options")
    col_desc, col_vend = st.columns(2)
    
    with col_desc:
        desc_keyword = st.text_input("📝 Search Item Description Field:", placeholder="e.g., alcohol, gift card, deposit, flower")
    
    with col_vend:
        vendor_keyword = st.text_input("🏪 Search Merchant / Vendor Field:", placeholder="e.g., post office, shell, package store")
    
    if desc_keyword or vendor_keyword:
        conditions = ["Year = ?"]
        params = [selected_year]
        
        if desc_keyword:
            conditions.append("LOWER(Description) LIKE ?")
            params.append(f"%{desc_keyword.lower()}%")
            
        if vendor_keyword:
            conditions.append("LOWER(Vendor) LIKE ?")
            params.append(f"%{vendor_keyword.lower()}%")
            
        where_clause = " AND ".join(conditions)
        search_sql = f"SELECT FullName AS [Cardholder], Vendor, Amount, TransactionDate AS [Date], Description, MCC FROM pcards WHERE {where_clause} ORDER BY Amount DESC;"
        
        df_audit = run_query(search_sql, params)
        
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric("Flagged Transactions", f"{len(df_audit):,}")
        m2.metric("Total Flagged Amount", f"${df_audit['Amount'].sum():,.2f}" if not df_audit.empty else "$0.00")
        m3.metric("Highest Single Charge", f"${df_audit['Amount'].max():,.2f}" if not df_audit.empty else "$0.00")
        
        st.subheader("Flagged Transaction Details")
        st.dataframe(df_audit, use_container_width=True)


# System prompt inside your OpenAI API call function
system_prompt = """
You are an expert SQLite translator for a table named 'pcards'.
Return ONLY valid SQL queries. Do not include markdown formatting, backticks, or explanatory text.
Table Schema:
pcards(FullName, Vendor, Amount, TransactionDate, Description, MCC, Year, Month)
Rules:
1. Pay close attention to numbers in the prompt (e.g., if asked for 'top 5', use 'LIMIT 5').
2. If no limit is specified, default to 'LIMIT 10'.
"""