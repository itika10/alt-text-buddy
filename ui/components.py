import streamlit as st

def render_result(title: str, alt_text: str, tags: list[str], explain_why: str | None = None):
    st.subheader(title)
    st.write(f"**Alt text:** {alt_text}")
    st.write(f"**Tags:** {', '.join(tags) if tags else '—'}")
    if explain_why:
        with st.expander("Explain why"):
            st.write(explain_why)