import os
import streamlit as st
import requests
import pandas as pd

# Fall back to localhost only if running outside of Docker
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")

# NEW: Grab the API key and set up the global headers payload
API_KEY = os.getenv("API_KEY", "missing_key")
AUTH_HEADERS = {"X-API-Key": API_KEY}

st.set_page_config(
    page_title="Enterprise RAG Management Console",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Enterprise RAG Management Console")
st.caption("Production system interface controlling pluggable multi-format ingestion and hybrid retrieval")

# Establish communication verification layers with backend REST APIs
try:
    health_check = requests.get(f"{BACKEND_API_URL}/health", timeout=2)
    backend_live = health_check.status_code == 200
except requests.exceptions.RequestException:
    backend_live = False

if not backend_live:
    st.error(f"Critical Connection Failure: Cannot reach the backend API at {BACKEND_API_URL}. Verify Uvicorn is active.")
    st.stop()

# Organize dashboard spaces into explicit functional viewports
tab_chat, tab_admin = st.tabs(["Hybrid Chat Search", "Ingestion Command Center"])

# --- PANEL 1: HYBRID SEARCH CHAT PORTAL ---
with tab_chat:
    st.subheader("Grounded Documentation Search")
    st.info("Submitting prompts queries parallel full-text keywords and dense vector spaces via RRF scores.")
    
    # Maintain active user conversational threads inside state arrays
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # Re-render historic query streams across screen reflow lifecycles
    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Render historic citations cleanly if they exist in the payload
            if message.get("citations"):
                with st.expander("🔖 Verified Reference Citations"):
                    for source in message["citations"]:
                        st.markdown(f"* `{source}`")

    # Intercept new user inputs
    user_query = st.chat_input("Ask a technical scikit-learn documentation question...")
    
    if user_query:
        # Append query instantly to viewport layout logs
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            response_placeholder.markdown("Computing embeddings and evaluating database RRF ranks...")
            
            try:
                # Dispatch payload structures over the local loop network
                api_payload = {"question": user_query}
                backend_response = requests.post(
                    f"{BACKEND_API_URL}/api/v1/query",
                    headers=AUTH_HEADERS,
                    json=api_payload,
                    timeout=30
                )
                
                if backend_response.status_code == 200:
                    answer_data = backend_response.json()
                    final_answer = answer_data.get("answer", "No answer could be generated.")
                    citations = answer_data.get("citations", [])
                    
                    response_placeholder.markdown(final_answer)
                    
                    # Render new citations dynamically
                    if citations:
                        with st.expander("Verified Reference Citations"):
                            for source in citations:
                                st.markdown(f"* `{source}`")
                    
                    # Lock response frames into history ledger states
                    st.session_state["chat_history"].append({
                        "role": "assistant", 
                        "content": final_answer,
                        "citations": citations
                    })
                else:
                    error_detail = backend_response.json().get("detail", "Unknown server malfunction.")
                    response_placeholder.error(f"API Error ({backend_response.status_code}): {error_detail}")
            except Exception as e:
                response_placeholder.error(f"Network Transaction Dropped: {str(e)}")


# --- PANEL 2: INGESTION COMMAND CENTER ---
with tab_admin:
    st.subheader("Data Repository Pipeline Orchestration")
    
    # 1. Fetch live repository data distribution maps
    try:
        status_response = requests.get(f"{BACKEND_API_URL}/api/v1/status", headers=AUTH_HEADERS, timeout=3)
        if status_response.status_code == 200:
            metrics = status_response.json()
            
            col1, col2 = st.columns(2)
            col1.metric("Total Indexed Chunks", metrics.get("total_chunks_indexed", 0))
            col2.metric("Database Health", "Connected" if metrics.get("database_connected") else "Offline")
            
            # Format raw distribution dictionary mappings into structural dataframes
            fmt_data = metrics.get("formats_distribution", {})
            if fmt_data:
                st.write("### Extracted File Format Distribution")
                compiled_rows = []
                for extension, details in fmt_data.items():
                    compiled_rows.append({
                        "File Format Type": extension.upper(),
                        "Unique Documents Count": details.get("unique_documents", 0),
                        "Total Extracted Chunks": details.get("total_chunks", 0)
                    })
                st.table(pd.DataFrame(compiled_rows))
        else:
            st.warning("Could not pull live collection summary layout metrics from backend.")
    except Exception as err:
        st.error(f"Failed to query repository state data models: {err}")

    st.markdown("---")
    
    # 2. Ingestion Trigger Configuration Control Box
    st.write("### Trigger Fresh Pipeline Ingestion Run")
    
    admin_col1, admin_col2, admin_col3 = st.columns(3)
    input_type = admin_col1.selectbox("Connector Ingestion Mechanism Type", ["local", "web"])
    input_path = admin_col2.text_input(
        "Source Destination Target Path/URL", 
        value="data_sandbox/test_inputs" if input_type == "local" else ""
    )
    input_limit = admin_col3.number_value = admin_col3.text_input("Resource Extraction Limit (Optional)", value="5")
    
    if st.button("Initialize Production Ingestion Cycle"):
        try:
            # Reformat optional inputs into clean parameters
            parsed_limit = int(input_limit) if input_limit.strip().isdigit() else None
            
            ingest_payload = {
                "source_type": input_type,
                "target_path": input_path,
                "limit": parsed_limit,
                "batch_size": 50
            }
            
            trigger_response = requests.post(
                f"{BACKEND_API_URL}/api/v1/ingest",
                json=ingest_payload,
                headers=AUTH_HEADERS,
                timeout=5
            )
            
            if trigger_response.status_code == 202:
                st.success("Ingestion accepted. The pipeline is running in a non-blocking background thread worker pool.")
            else:
                st.error(f"Pipeline refused initialization: {trigger_response.text}")
        except Exception as trigger_err:
            st.error(f"Failed to transmit transaction trigger: {trigger_err}")

    st.markdown("---")
    
    # 3. Render Pipeline Telemetry Audit Logs
    st.write("### Live Pipeline Execution Logs Ledger")
    if st.button("Refresh Telemetry Audit Logs"):
        st.rerun()
        
    try:
        logs_response = requests.get(f"{BACKEND_API_URL}/api/v1/logs", headers=AUTH_HEADERS, timeout=3)
        if logs_response.status_code == 200:
            logs_array = logs_response.json()
            if logs_array:
                # Convert log list structures into scannable analysis dataframes
                df_logs = pd.DataFrame(logs_array)
                # Reorder columns for optimal dashboard scannability
                display_cols = ["run_id", "pipeline_name", "status", "extracted", "transformed", "indexed", "started_at"]
                df_logs = df_logs.astype(str)
                st.dataframe(df_logs[display_cols].head(500), use_container_width=True)
            else:
                st.info("No background pipeline logs written to database tables yet.")
        else:
            st.warning("Could not pull historical audit data logs.")
    except Exception as logs_err:
        st.error(f"Failed retrieving audit ledger history sequences: {logs_err}")