import os
import sqlite3
import pandas as pd
import streamlit as st
import google.generativeai as genai

# Retrieve Google AI Studio API Key from Streamlit Secrets or Environment Variables
api_key = st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Initialize Gemini Model
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.1-pro")
else:
    model = None

# Configure Page Layout
st.set_page_config(page_title="OSU P-Card Audit Portal", page_icon="🔍", layout="wide")

DB_PATH = "pcards.db"

def run_query(query, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=params)

SYSTEM_PROMPT = """
You are an expert SQLite translator for a table named 'pcards'.
Return ONLY valid SQL queries without markdown formatting, backticks, or explanatory text.

Table Schema:
pcards(FullName, Vendor, Amount, TransactionDate, Description, MCC, Year, Month)

Rules:
1. Parse numbers in the prompt carefully (e.g., 'top 5' or 'top five' must use 'LIMIT 5').
2. If no limit or count is requested in the prompt, default to 'LIMIT 10'.
3. Always ensure the generated SQL is valid SQLite.
"""

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
    - *Show top 5 cardholders by spending*
    - *Show vendor totals over $50,000*
    """)
    
    user_prompt = st.text_input("Enter your audit question:", placeholder="e.g., Show top 5 cardholders by spending")
    
    if st.button("Run Query", key="nl_search"):
        if not user_prompt:
            st.warning("Please enter a question first.")
        elif not model:
            st.error("Google AI Studio API Key is missing. Please check your Streamlit secrets.")
        else:
            try:
                # 1. Combine system prompt and user question for Gemini
                full_prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {user_prompt}"
                response = model.generate_content(full_prompt)
                
                # 2. Extract and sanitize SQL string
                sql_generated = response.text.strip()
                sql_generated = sql_generated.replace("```sql", "").replace("```", "").strip()
                
                st.subheader("Generated SQL Query")
                st.code(sql_generated, language="sql")
                
                # 3. Execute query and display results
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