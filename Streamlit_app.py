import streamlit as st

#app_page = st.Page(page="app.py", title="📝 Document Verification")
#compliance_page = st.Page(page="pages/compliance.py", title="🚀 Report Generation")
st.image("nama-logo.png")

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