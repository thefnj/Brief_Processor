import streamlit as st
import pdfplumber
import uuid
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
import re

# --- 1. CONFIG & AUTH ---
st.set_page_config(page_title="Modular Brief Engine", layout="wide")

# Connect to Google Sheets using Streamlit Secrets
def get_gspread_client():
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    # Ensure you have 'gcp_service_account' as a dict in your Streamlit Secrets
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# Connect to Gemini API
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. CORE FUNCTIONS ---

def extract_pdf_text(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
        return " ".join([page.extract_text() for page in pdf.pages if page.extract_text()])

def ai_genericize_brief(raw_text):
    prompt = f"""
    You are a creative strategist. Take the following brand brief and:
    1. Strip all specific brand names and locations.
    2. Genericize the concept (e.g., 'Nike' becomes 'Athletic Apparel Brand').
    3. Break the campaign into atomic components.

    Return ONLY a JSON object with this exact structure:
    {{
        "generic_title": "String",
        "original_sector": "String",
        "objective": "String",
        "insight": "String",
        "summary": "String",
        "components": [
            {{"type": "Social/Radio/etc", "desc": "Description", "cost_driver": "e.g. Talent"}}
        ]
    }}

    BRIEF TEXT:
    {raw_text}
    """
    response = model.generate_content(prompt)
    # Extract JSON using regex in case AI adds conversational text
    json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group(0)
    return json.loads(json_str)

# --- 3. UI LAYOUT ---
st.title("🚀 Modular Creative Engine")
st.markdown("Transform messy PDF briefs into clean, reusable data components.")

uploaded_file = st.file_uploader("Upload a PDF Brief", type="pdf")

if uploaded_file:
    if 'processed_data' not in st.session_state:
        with st.spinner("AI is genericizing your brief..."):
            text = extract_pdf_text(uploaded_file)
            st.session_state.processed_data = ai_genericize_brief(text)
            st.session_state.idea_id = f"IDEA-{uuid.uuid4().hex[:4].upper()}"

    data = st.session_state.processed_data
    
    # Display Results
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💡 Generic Concept")
        title = st.text_input("Title", value=data['generic_title'])
        sector = st.text_input("Sector", value=data['original_sector'])
        insight = st.text_area("Insight", value=data['insight'])
        obj = st.text_area("Objective", value=data['objective'])

    with col2:
        st.subheader("📦 Atomic Components")
        comp_df = pd.DataFrame(data['components'])
        st.table(comp_df)

    # --- 4. DATA SYNC ---
    if st.button("Push to Google Sheets DB", variant="primary"):
        try:
            gc = get_gspread_client()
            sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZGpiqI2QJwtLhAmHuehuz-nf4yN0Zyuih-Kp6Tj-5II/edit#gid=0")
            
            # 1. Sync to Ideas Tab
            ideas_sheet = sh.worksheet("Ideas")
            # Mapping to your specific 16 columns
            ideas_row = [st.session_state.idea_id, title, uploaded_file.name, sector, "", "", obj, insight, "", "", "", "", "", "", "", data['summary']]
            ideas_sheet.append_row(ideas_row)
            
            # 2. Sync to Components Tab
            comp_sheet = sh.worksheet("Components")
            for c in data['components']:
                comp_row = [f"COMP-{uuid.uuid4().hex[:2].upper()}", st.session_state.idea_id, c['type'], c['desc'], "Yes", c['cost_driver']]
                comp_sheet.append_row(comp_row)
            
            st.balloons()
            st.success(f"✅ Data synced! Idea ID: {st.session_state.idea_id}")
            
        except Exception as e:
            st.error(f"Error syncing to Sheets: {e}")
