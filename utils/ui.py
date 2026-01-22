from __future__ import annotations
import streamlit as st

def metric_card(title: str, value: str | int, emoji: str = ""):
    st.metric(label=title, value=f"{emoji} {value}")


def light_card(title: str, body_md: str):
    st.container(border=True).markdown(f"**{title}**\n\n{body_md}")