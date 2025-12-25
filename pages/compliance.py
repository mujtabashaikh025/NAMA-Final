import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
from dotenv import load_dotenv
import os

load_dotenv() 

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Compliance Extractor", layout="wide")
# st.image("nama-logo.png") # Commented out to prevent error if image is missing locally

# REPLACE with your actual API Key (Use st.secrets in production)
api_key = "AIzaSyDpvIYZSQhsRNwqZ0ngXf78T9iv21YFaEk"

# --- 2. HELPER FUNCTIONS ---

def clean_json_string(json_str):
    """Cleans Markdown formatting from JSON string."""
    cleaned = re.sub(r"```json\s*", "", json_str)
    cleaned = re.sub(r"```", "", cleaned)
    return cleaned.strip()

def get_compliance_table(pdf_bytes, key):
    """Sends the PDF file DIRECTLY to Gemini."""
    try:
        genai.configure(api_key=key)
        config = genai.GenerationConfig(temperature=0.0)
        # Using 'gemini-1.5-flash' or 'gemini-1.5-pro' is recommended for PDF vision tasks
        model = genai.GenerativeModel('gemini-2.5-pro',generation_config=config) 
        
        system_prompt = """
        You are a Technical QA Engineer reviewing a scanned Vendor Specification Document.
        
        **YOUR TASK:**
        Look at the document image/PDF and extract a comprehensive Compliance Table.
        
        **INPUT DATA:**
        The document contains a list of "APPLICABLE STANDARDS" and specific sections. 
        
        **RULES:**
        1. Identify every Standard and Key Section.
        2. Determine Status:
           - "Comply", "Included" -> "Comply"
           - "Noncomply", "Excluded", "Not related" -> "Not Comply"
           - Handwritten tick/check mark -> "Comply"
        3. Remarks: Explain deviations if "Not Comply".

        **OUTPUT FORMAT (JSON ARRAY):**
        [
            {"Standard_Section": "BS EN 558-1", "Status": "Comply", "Remark": "Face-to-face dimensions"},
            {"Standard_Section": "ISO 1461", "Status": "Not Comply", "Remark": "Vendor excludes galvanization"}
        ]
        """

        pdf_data = {"mime_type": "application/pdf", "data": pdf_bytes}

        response = model.generate_content(
            contents=[system_prompt, pdf_data],
            generation_config={"response_mime_type": "application/json"}
        )
        
        return json.loads(clean_json_string(response.text))

    except Exception as e:
        st.error(f"AI Error: {str(e)}")
        return []

# --- 3. STREAMLIT UI ---
st.title("📑 Smart Compliance Report Generator")
st.markdown("Upload a Vendor Specification PDF to auto-extract the **Compliance Table**.")

uploaded_file = st.file_uploader("Upload Compliance Statement PDF", type=["pdf"])

if uploaded_file and st.button("Generate Compliance Table"):
    
    with st.spinner("👀 Analyzing PDF Image & Compliance..."):
        
        bytes_data = uploaded_file.getvalue()
        
        if bytes_data:
            table_data = get_compliance_table(bytes_data, api_key)
            
            if table_data:
                df = pd.DataFrame(table_data)

                # --- METRIC CALCULATION LOGIC ---
                total_items = len(df)
                
                # We filter for rows that contain "Comply" but NOT "Not Comply" (case insensitive)
                compliant_df = df[
                    df['Status'].astype(str).str.contains("Comply", case=False) & 
                    ~df['Status'].astype(str).str.contains("Not", case=False)
                ]
                
                num_comply = len(compliant_df)
                num_non_comply = total_items - num_comply
                
                # Calculate Percentage: (Comply / Total) * 100
                if total_items > 0:
                    compliance_pct = (num_comply / total_items) * 100
                else:
                    compliance_pct = 0.0

                # --- DISPLAY METRICS ---
                a, b = st.columns(2)
                a.metric("Compliance Percentage", f"{compliance_pct:.1f}%", border=True)
                b.metric("Number of Non-Compliance", f"{num_non_comply}", border=True)

                # --- VISUALS ---
                def color_status(val):
                    val_str = str(val).lower()
                    if 'comply' in val_str and 'not' not in val_str:
                        return 'background-color: #d4edda; color: #155724' # Green
                    return 'background-color: #f8d7da; color: #721c24'     # Red

                st.subheader("Compliance Report")
                st.dataframe(
                    df.style.map(color_status, subset=['Status']),
                    column_config={
                        "Standard_Section": "Standard / Section",
                        "Status": "Compliance Status",
                        "Remark": "AI Observations / Remarks"
                    },
                    use_container_width=True
                )
                
                # Download Button
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Report",
                    data=csv,
                    file_name="compliance_table.csv",
                    mime="text/csv",
                )
            else:
                st.warning("Could not extract a table. Please ensure the PDF is not password protected.")
