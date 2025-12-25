import streamlit as st
from google import generativeai as genai
import pandas as pd
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from dotenv import load_dotenv
import pypdf
import io
import base64
from mistralai import Mistral

# --- 1. CONFIGURATION & SETUP ---
load_dotenv()
st.set_page_config(page_title="NAMA Compliance Agent", layout="wide")


# API Configuration
api_key = st.secrets["gemini_auth_key"]
genai.configure(api_key=api_key)

# Mistral Configuration
MISTRAL_API_KEY = st.secrets["ocr_auth_key"]
mistral_client = Mistral(api_key=MISTRAL_API_KEY)

REQUIRED_DOCS = [
    "1- Fees application receipt copy.",
    "2- Nama water services vendor registeration certificates...",
    "3- Certificate of incorporation of the firm...",
    "4- Manufacturing Process flow chart...",
    "5-Valid copies certificates of (ISO 9001, ISO 45001 & ISO 14001).",
    "6- Factory Layout chart.",
    "7-Factory Organizational structure...",
    "8- Product Compliance Statement...",
    "9- Product Technical datasheets.",
    "10- Omanisation details...",
    "11- Product Independent Test certificates.",
    "12- Attestation of Sanitary Conformity...",
    "13- Provide products Chemicals Composition...",
    "14- Reference list of products used in Oman..."
]

# --- HELPER: Encode PDF to Base64 ---
def encode_pdf(file_bytes):
    """Encodes the raw PDF bytes to base64 for Mistral API."""
    return base64.b64encode(file_bytes).decode('utf-8')

# --- 2. INTELLIGENT EXTRACTION (Hybrid: Text First -> Mistral Native OCR) ---
def extract_text_smart(uploaded_file):
    """
    Attempts direct text read. If fails/empty, sends PDF directly to Mistral OCR.
    """
    text = ""
    file_bytes = uploaded_file.getvalue()
    
    # METHOD 1: Direct Text Extraction (Zero Latency check)
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        num_pages = len(pdf_reader.pages)
        limit = min(3, num_pages)
        
        for i in range(limit):
            page_text = pdf_reader.pages[i].extract_text()
            if page_text:
                text += page_text

        # If we found good text (not just empty space), return immediately
        if len(text.strip()) > 100: 
            return f"FILE_NAME: {uploaded_file.name}\n(Extracted via Text Layer)\n{text[:15000]}"
    except Exception as e:
        print(f"Direct extract failed for {uploaded_file.name}: {e}")

    # METHOD 2: Mistral Native OCR (Optimized)
    # 
    try:
        base64_pdf = encode_pdf(file_bytes)
        
        # Send the PDF directly. We request only specific pages to save time/cost.
        # Note: 'pages' parameter uses 0-based indexing.
        ocr_response = mistral_client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{base64_pdf}"
            },
            pages=[0, 1, 2],  # Only process first 3 pages
            include_image_base64=False # We don't need images back, just text
        )
        
        # Mistral returns structured markdown for each page
        ocr_text = ""
        for page in ocr_response.pages:
            ocr_text += page.markdown + "\n\n"
            
        return f"FILE_NAME: {uploaded_file.name}\n(Extracted via Mistral OCR)\n{ocr_text[:15000]}"
        
    except Exception as e:
        return f"Error reading {uploaded_file.name}: {str(e)}"

def batch_extract_all(files):
    """Uses ThreadPoolExecutor to process files simultaneously."""
    # We can increase workers again because Mistral Native OCR is much faster/stable
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(extract_text_smart, files))
    return results

# --- 3. BATCHED AI ANALYSIS (Gemini Flash) ---
def analyze_batch(batch_text_list):
    # Using Flash 2.0 for maximum speed on the analysis side
    model = genai.GenerativeModel('gemini-2.5-pro') 
    today_str = date.today().strftime("%Y-%m-%d")

    prompt = f"""
    Today is {today_str}. You are NAMA Document Analyzer.
    Extract data from pdfs and translate it if it is not in english.
    Classify each document using this list: {json.dumps(REQUIRED_DOCS)}
    
    Compliance Rule: ISO certificates must be valid for >180 days from {today_str}.
    
    Return ONLY a JSON object with this EXACT structure:
    {{
        "iso_analysis": [
            {{
                "standard": "ISO 9001",
                "expiry_date": "YYYY-MM-DD",
                "days_remaining": 0,
                "compliance_status": "Pass/Fail"
            }}
        ],
        "found_documents": [
            {{"filename": "name.pdf", "Category": "Category from list", "Status": "Valid"}}
        ],
        "wras_analysis": {{
                "found": true,
                "wras_id": "123456"
            }}
    }}
    """
    
    combined_content = "\n\n=== NEXT DOCUMENT ===\n".join(batch_text_list)
    
    try:
        response = model.generate_content(
            contents=[prompt, combined_content],
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        if isinstance(data, list): return data[0]
        return data
    except Exception:
        return {}

# --- 4. ONLINE WRAS CHECKER ---
def verify_wras_online(wras_id):
    if not wras_id or wras_id == "N/A":
        return {"status": "Skipped", "url": "#"}

    search_url = f"https://www.wrasapprovals.co.uk/approvals-directory/?search={wras_id}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=5)
        if response.status_code == 200 and "No results found" not in response.text:
            return {"status": "Active", "online_id": wras_id, "url": search_url}
        return {"status": "Not Found", "url": search_url}
    except:
        return {"status": "Error", "url": search_url}

# --- 5. UI & EXECUTION LOGIC ---
st.title("NAMA Compliance AI Audit")

uploaded_files = st.file_uploader("Upload Documents for Analysis...", type=["pdf"], accept_multiple_files=True)

if st.button("Run Audit", type="primary"):
    if uploaded_files:
        start_time = datetime.now()
        
        # 1. Fast Extraction
        with st.status("Reading Documents...", expanded=True) as status:
            st.write("Extracting text (Using Mistral Native OCR for scans)...")
            all_texts = batch_extract_all(uploaded_files)
            status.update(label="Text Extraction Complete!", state="complete", expanded=False)

        # 2. Parallel AI Analysis
        final_report = {
            "iso_analysis": [],
            "wras_analysis": {"found": False, "wras_id": None},
            "found_documents": [],
            "missing_documents": set(REQUIRED_DOCS),
            "wras_online_check": {"status": "N/A", "url": "#"}
        }

        batch_size = 8
        batches = [all_texts[i:i + batch_size] for i in range(0, len(all_texts), batch_size)]
        
        with st.spinner(f"Analyzing {len(batches)} batches with AI..."):
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_batch = {executor.submit(analyze_batch, batch): batch for batch in batches}
                
                for future in as_completed(future_to_batch):
                    batch_res = future.result()
                    if isinstance(batch_res, dict):
                        final_report["iso_analysis"].extend(batch_res.get("iso_analysis", []))
                        final_report["found_documents"].extend(batch_res.get("found_documents", []))
                        
                        wras = batch_res.get("wras_analysis", {})
                        if isinstance(wras, dict) and wras.get("found"):
                            final_report["wras_analysis"] = wras

        # Post-Processing
        for doc in final_report["found_documents"]:
            doc_type = doc.get("Category")
            if doc_type in final_report["missing_documents"]:
                final_report["missing_documents"].remove(doc_type)

        extracted_id = final_report["wras_analysis"].get("wras_id")
        if extracted_id:
            final_report["wras_online_check"] = verify_wras_online(extracted_id)

        st.session_state.analysis_result = final_report
        
        duration = (datetime.now() - start_time).total_seconds()
        st.success(f"Audit Complete in {duration:.2f} seconds!")

# --- 6. DISPLAY RESULTS ---
if "analysis_result" in st.session_state:
    res = st.session_state.analysis_result
    no_of_missing_docs = len(res["missing_documents"])
    doc_score = round(((14 - no_of_missing_docs) / 14) * 100, 2)
    
    wras_data = res.get("wras_online_check", {})
    wras_url = wras_data.get("url", "#")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💧 WRAS Status", wras_data.get("status", "N/A"), border=True)
        if wras_url != "#": st.link_button("🔍 Verify", wras_url)
    
    col2.metric("⛔ Missing Docs", f"{no_of_missing_docs}", border=True)
    col3.metric("🏆 Score", f"{doc_score}%", border=True)

    st.subheader("❌ Missing Documents")
    if res["missing_documents"]:
        for m in sorted(list(res["missing_documents"])):
            st.error(f"Missing: {m}")
    else:
        st.success("All required documents found!")
            
    st.subheader("✅ Documents Found")
    if res["found_documents"]:
        st.dataframe(pd.DataFrame(res["found_documents"]), use_container_width=True)


    st.subheader("🏭 ISO Validation")
    iso_data = res.get('iso_analysis', [])
    if iso_data:
        cols = st.columns(3)
        for idx, iso in enumerate(iso_data):
            with cols[idx % 3]:
                std_name = iso.get('standard', 'Unknown ISO')
                status = iso.get('compliance_status', 'Fail')
                days = iso.get('days_remaining', 0)
                
                status_color = "green" if "Pass" in status else "red"
                with st.container(border=True):
                    st.markdown(f"#### :{status_color}[{std_name}]")
                    if days < 180:
                        st.error(f"⚠️ {days} days left")
                    else:
                        st.success(f"✅ {days} days left")
                    st.caption(f"Expires: {iso.get('expiry_date')}")
