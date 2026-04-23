import streamlit as st

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")

home = st.Page("pages/Home.py", title="PawPal+", icon="🐾", default=True)
assistant = st.Page("pages/Pet_Care_Assistant.py", title="AI Assistant", icon="🤖")

pg = st.navigation([home, assistant], position="hidden")
pg.run()
