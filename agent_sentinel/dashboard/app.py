"""
Sentinel Dashboard — live view of every intercepted action, from both
adaptors, reading from the shared audit log.
"""

import pandas as pd
import streamlit as st

from agent_sentinel.core.audit_log import AuditLog

st.set_page_config(page_title="Sentinel Dashboard", layout="wide")
st.title("🛡️ Sentinel — Agent Action Audit Log")

log = AuditLog()
stats = log.stats()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Actions", stats["total"])
col2.metric("Allowed", stats["by_verdict"]["allow"])
col3.metric("Blocked", stats["by_verdict"]["block"])
col4.metric("Flagged", stats["by_verdict"]["flag"])

st.subheader("Recent Activity")

entries = log.recent(limit=200)
if entries:
    df = pd.DataFrame(
        [
            {
                "Time": e.created_at,
                "Agent": e.agent_id,
                "Tool": e.tool,
                "Source": e.source.value,
                "Verdict": e.verdict.value,
                "Layer": e.layer,
                "Reason": e.reason,
            }
            for e in entries
        ]
    )

    verdict_filter = st.multiselect(
        "Filter by verdict",
        options=["allow", "block", "flag"],
        default=["allow", "block", "flag"],
    )
    df = df[df["Verdict"].isin(verdict_filter)]

    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No actions logged yet. Run a demo script to generate activity.")

if st.button("🔄 Refresh"):
    st.rerun()
