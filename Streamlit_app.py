import streamlit as st
from PIL import Image

img1 = Image.open("images/nama-logo.png")
s1 = (250, 200) 
img1_resized = img1.resize(s1)

col1, col2 = st.columns(2)

with col1:
    st.image(img1_resized)

with col2:
    st.image("images/velyana-new.png")
    
pg = st.navigation(pages)
pg.run()
