import streamlit as st

#app_page = st.Page(page="app.py", title="📝 Document Verification")
#compliance_page = st.Page(page="pages/compliance.py", title="🚀 Report Generation")
col1,col2 = st.columns(2)
with st.col1:
    st.image("images/nama-logo.png")
with st.col2:
    st.image("images/velyana-logo.png")

pages = {
    "Services": [
        st.Page("app.py", title="📝 Document Verification"),
        st.Page("pages/compliance.py", title="🚀 Report Generation"),
    ]
}

pg = st.navigation(pages)
pg.run()
# pg = st.navigation(
#     pages=[app_page, compliance_page]
# )

# pg.run()
