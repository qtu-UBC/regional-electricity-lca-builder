"""Local-only Streamlit interface for instructor review of generator references.

Run from repository root: streamlit run instructor/review_app.py
Do NOT deploy this page publicly with licensed provider metadata.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from instructor.review_providers import approve_provider_library
from provider_library import provider_class

st.set_page_config(page_title="Instructor Provider Review", layout="wide")
st.title("Instructor setup · Electricity provider review")
st.warning(
    "LOCAL INSTRUCTOR WORKFLOW. Source files contain process metadata tied to a "
    "licensed ecoinvent database. Do not deploy this page publicly or distribute "
    "the reviewed JSON without checking your license."
)
st.markdown(
    "Approve **modeling options** (specific generation processes), not a measured "
    "regional electricity mix. Every selected provider requires an individual reason."
)
source_upload = st.file_uploader(
    "Upload extracted provider_library_REVIEW.json (any supported region)",
    type="json", key="source_library",
)
if source_upload is None:
    st.info(
        "First run python -m instructor.extract_provider_library against your "
        "restored openLCA .zolca, or upload an existing extracted catalog."
    )
    st.stop()

content = source_upload.getvalue()
source_hash = hashlib.sha256(content).hexdigest()
try:
    library = json.loads(content.decode("utf-8-sig"))
except (ValueError, UnicodeDecodeError) as exc:
    st.error(f"Cannot read source JSON: {exc}")
    st.stop()
if library.get("catalog_version") != 2 or not isinstance(library.get("entries"), list):
    st.error("This page requires a catalog_version 2 provider library with entries.")
    st.stop()
if library.get("extraction_truncated"):
    st.error("This extraction was truncated and cannot be approved.")
    st.stop()
if st.session_state.get("source_hash") != source_hash:
    st.session_state["source_hash"] = source_hash
    st.session_state["approved_provider_reasons"] = {}
    st.session_state["approved_market_ids"] = []
    st.session_state["prepared_json"] = None

decisions = st.session_state["approved_provider_reasons"]
st.caption(
    f"Source: {library.get('database_label', '(unknown)')} · "
    f"{len(library['entries']):,} candidate generators · "
    f"{len(library.get('markets', [])):,} existing electricity markets"
)
st.subheader("1 · Filter and review generator candidates")
a, b, c = st.columns(3)
regions = sorted({str(e.get("location", "")) for e in library["entries"]})
categories = sorted({str(e.get("technology", "")) for e in library["entries"]})
with a:
    initial = regions.index("Canada, Ontario") + 1 if "Canada, Ontario" in regions else 0
    region = st.selectbox("Geography", ["All geographies"] + regions, index=initial)
with b:
    technology = st.selectbox("Technology", ["All technologies"] + categories)
with c:
    query = st.text_input("Search process name", placeholder="hydro, wind, wood chips...")
rows = [
    e for e in library["entries"]
    if (region == "All geographies" or e.get("location") == region)
    and (technology == "All technologies" or e.get("technology") == technology)
    and query.casefold() in str(e.get("name", "")).casefold()
]
rows.sort(key=lambda x: (str(x.get("technology", "")), str(x.get("name", "")), str(x["id"])))
page_size = 40
pages = max(1, (len(rows) + page_size - 1) // page_size)
page = st.number_input("Results page", min_value=1, max_value=pages, value=1)
shown = rows[(page - 1) * page_size:page * page_size]
st.caption(
    f"{len(rows):,} matches; {len(shown)} on this page. "
    f"{len(decisions)} generator(s) already staged. "
    "Edit the checkboxes and review reasons, then click Apply page decisions "
    "BEFORE changing filters."
)
if shown:
    frame = pd.DataFrame([
        {
            "Approve": e["id"] in decisions,
            "Technology": e.get("technology", ""),
            "Location": e.get("location", ""),
            "Process": e.get("name", ""),
            "Role": provider_class(e),
            "Review reason": decisions.get(e["id"], ""),
            "UUID": e["id"],
        }
        for e in shown
    ])
    editor_key = "review_editor_" + hashlib.sha256(
        f"{source_hash}:{region}:{technology}:{query}:{page}".encode("utf-8")
    ).hexdigest()[:18]
    edited = st.data_editor(
        frame, key=editor_key, hide_index=True, use_container_width=True,
        disabled=["Technology", "Location", "Process", "Role", "UUID"],
        column_config={
            "Approve": st.column_config.CheckboxColumn("Approve for modeling", required=True),
            "Review reason": st.column_config.TextColumn(
                "Review reason (required)", width="large"
            ),
            "Process": st.column_config.TextColumn("Activity / reference product", width="large"),
        },
    )
    if st.button("Apply decisions for displayed page", type="primary"):
        pending, errors = {}, []
        for _, item in edited.iterrows():
            if bool(item["Approve"]):
                reason = str(item["Review reason"] or "").strip()
                if len(reason) < 12:
                    errors.append(f"{item['Process']}: review reason of 12+ characters required.")
                elif str(item["Role"]) not in ("generation", "cogeneration"):
                    errors.append(
                        f"{item['Process']}: unusual process role {item['Role']}; "
                        "this page only approves generation and cogeneration by default."
                    )
                else:
                    pending[str(item["UUID"])] = reason
        if errors:
            st.error("\n".join(errors))
        else:
            for e in shown:
                decisions.pop(e["id"], None)
            decisions.update(pending)
            st.session_state["prepared_json"] = None
            st.success(f"Saved choices. {len(decisions)} generators currently staged.")
else:
    st.info("No providers match this filter.")

with st.expander("Review currently selected generation processes"):
    if not decisions:
        st.caption("No generator selected yet.")
    else:
        selected_rows = [
            {"Technology": e["technology"], "Location": e.get("location", ""),
             "Process": e["name"], "Reason": decisions[e["id"]], "UUID": e["id"]}
            for e in library["entries"] if e["id"] in decisions
        ]
        st.dataframe(pd.DataFrame(selected_rows), hide_index=True, use_container_width=True)

st.subheader("2 · Optional baseline market references")
markets = library.get("markets", [])
market_options = [
    m for m in markets if region == "All geographies" or m.get("location") == region
]
market_options.sort(key=lambda m: (str(m.get("voltage", "")), str(m.get("name", ""))))
market_lookup = {m["id"]: m for m in market_options}
chosen = st.multiselect(
    "Choose existing electricity markets for reference (not generation providers)",
    options=list(market_lookup),
    default=[m for m in st.session_state["approved_market_ids"] if m in market_lookup],
    format_func=lambda uid: (
        f"{market_lookup[uid].get('name')} · {market_lookup[uid].get('location')} "
        f"· {market_lookup[uid].get('voltage', '?')} voltage"
    ),
    key="market_picker_" + hashlib.sha256(
        f"{source_hash}:{region}".encode("utf-8")
    ).hexdigest()[:12],
)
if st.button("Apply baseline market choices for this geography"):
    remain = [
        uid for uid in st.session_state["approved_market_ids"]
        if uid not in market_lookup
    ]
    st.session_state["approved_market_ids"] = remain + chosen
    st.session_state["prepared_json"] = None
    st.success(f"Saved {len(st.session_state['approved_market_ids'])} baseline market references.")

st.subheader("3 · Confirm review and prepare the approved library")
reviewer = st.text_input("Reviewer", placeholder="Instructor name")
scope = st.text_area(
    "Review scope, assumptions and limitations",
    placeholder=(
        "Verified dataset names, high-voltage electricity reference products, "
        "location, technology and compatibility with the intended class scenario. "
        "The proposed regional mix and biomass fuel remain unverified."
    ),
)
confirmed = st.checkbox(
    "I personally checked the selected source processes and their suitability as "
    "modeling options. This does not certify an actual regional generation mix."
)
if st.button("Validate and prepare approved JSON"):
    try:
        if not confirmed:
            raise ValueError("Please explicitly confirm the instructor review.")
        approved = approve_provider_library(
            library, decisions, st.session_state["approved_market_ids"],
            reviewer, scope,
        )
        st.session_state["prepared_json"] = json.dumps(
            approved, indent=2, ensure_ascii=False
        )
        st.success(
            f"Validated {approved['approved_provider_count']} generation options and "
            f"{approved['approved_market_count']} baseline markets. "
            "These are instructor-approved modeling candidates."
        )
    except (ValueError, KeyError, TypeError) as exc:
        st.session_state["prepared_json"] = None
        st.error(str(exc))
if st.session_state.get("prepared_json"):
    st.download_button(
        "Download provider_library_APPROVED_LOCAL.json",
        st.session_state["prepared_json"],
        file_name="provider_library_APPROVED_LOCAL.json",
        mime="application/json", type="primary",
    )
    st.caption(
        "Keep this file in local/ after downloading. Use it in Tab 2 of the student app "
        "only where licensing and authorized access permit."
    )
