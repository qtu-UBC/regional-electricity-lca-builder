"""Regional Electricity LCA Builder — Streamlit student interface.

Run: streamlit run app.py
No internet or licensed ecoinvent processes are required to define scenario inputs.
"""
import io
import json
import hashlib
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from grid_core import (
    TECHNOLOGIES, parse_mix_csv, validate_scenario, dump_supply_mix_csv,
    scenario_documentation_report,
)
from openlca_jsonld import validate_catalog, package as make_openlca_package, package_preview
from mv_market import (
    adapter_review_status, mark_reviewed_for_testing, record_replication_validation,
    replication_evidence_errors, source_fingerprint, validate_mv_structure,
    validate_mv_adapter, mv_replication_package, make_mv_replication_processes,
    mv_package, mv_preview,
)
from provider_library import (
    library_errors, approved_candidates, approved_markets, catalog_for_selection,
    ranked_candidates, provider_class, region_preference,
)

# Built-in teaching examples: no licensed ecoinvent data or verified grid CI.
PRESET_DEMO = "Demo — Hypothetical electricity mix"
PRESET_NORTHWEST = "IESO Northwest — 2025 proposed generation mix"
PRESET_CUSTOM = "Create my own scenario"
PRESET_OPTIONS = (PRESET_DEMO, PRESET_NORTHWEST, PRESET_CUSTOM)
# Only these database configurations have a supported openLCA exporter.
# This list denotes app support, not databases installed on students' computers.
SUPPORTED_OPENLCA_DATABASES = ("ecoinvent 3.12, allocation cut-off",)
NORTHWEST_MIX_FILE = Path(__file__).resolve().parent / "data" / "IESO_Northwest_2025_Generation_Scenario.csv"
NORTHWEST_TUTORIAL_URL = (
    "https://github.com/qtu-UBC/regional-electricity-lca-builder/"
    "blob/main/tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md"
)


def preset_mix_rows(preset):
    """Create fresh editable rows from the selected starting scenario."""
    if preset == PRESET_NORTHWEST:
        return parse_mix_csv(NORTHWEST_MIX_FILE.read_text(encoding="utf-8-sig"))
    if preset == PRESET_DEMO:
        return [
            {"technology": "hydro", "share": 0.8,
             "source_url": "", "notes": "HYPOTHETICAL demonstration value"},
            {"technology": "nuclear", "share": 0.1,
             "source_url": "", "notes": "HYPOTHETICAL demonstration value"},
            {"technology": "natural_gas", "share": 0.1,
             "source_url": "", "notes": "HYPOTHETICAL demonstration value"},
        ]
    return [{"technology": "hydro", "share": 0.0,
             "source_url": "", "notes": "Replace with your own documented generation shares"}]


def on_voltage_change():
    """Avoid double-counting grid losses if an MV adapter will provide them."""
    if st.session_state.get("scenario_voltage") == "medium":
        st.session_state["scenario_losses_pct"] = 0.0


def load_selected_preset():
    """Reset the scenario's starting values when a preset is selected."""
    preset = st.session_state.get("scenario_preset", PRESET_DEMO)
    st.session_state.update({
        "scenario_region": (
            "IESO Northwest — 2025 client-proposed generation scenario"
            if preset == PRESET_NORTHWEST else
            "Demo — Hypothetical electricity mix" if preset == PRESET_DEMO else
            "Custom electricity scenario"
        ),
        "scenario_year": 2025,
        "scenario_boundary": "generation" if preset == PRESET_NORTHWEST else "hypothetical",
        "scenario_evidence": "user_supplied_unverified" if preset == PRESET_NORTHWEST else "illustrative",
        "scenario_voltage": "high",
        "scenario_losses_pct": 0.0,
        "scenario_source_url": "",
        "scenario_background": "ecoinvent 3.12, allocation cut-off",
        "starting_mix_rows": preset_mix_rows(preset),
        "preset_reload_id": st.session_state.get("preset_reload_id", 0) + 1,
    })


if "starting_mix_rows" not in st.session_state:
    st.session_state["scenario_preset"] = PRESET_DEMO
    load_selected_preset()


st.set_page_config(page_title="Regional Electricity LCA Builder", page_icon="⚡", layout="wide")
st.title("⚡ Regional Electricity LCA Builder")
st.caption("Create a documented regional electricity supply scenario for use in openLCA.")
st.info(
    "**Problem this tool solves:** LCI databases often lack an up-to-date electricity mix "
    "for a specific region. Combine documented generation shares with existing "
    "electricity providers in your licensed database, then export a custom unit "
    "process to openLCA for impact calculations.\n\n"
    "**Caution:** The tool does not supply ecoinvent data or independently "
    "verify regional grid statistics."
)

tab_build, tab_library, tab_openlca, tab_help = st.tabs([
    "1 · Build supply mix",
    "2 · Select providers",
    "3 · Export to openLCA",
    "Guide & cautions",
])

with tab_build:
    st.subheader("Start with an example or create your own")
    st.selectbox(
        "Start with a scenario",
        PRESET_OPTIONS,
        key="scenario_preset",
        on_change=load_selected_preset,
        help="Selecting a scenario loads its metadata and generation shares. You can edit any value afterward.",
    )
    if st.session_state["scenario_preset"] == PRESET_NORTHWEST:
        st.warning(
            "Client-proposed 2025 Northwest GENERATION mix (not independently verified). "
            "It does not establish the electricity mix consumed at a facility or a regional life-cycle CI. "
            "Imports, exports and interzonal transfers are not included."
        )
        st.markdown(f"[Open the worked student tutorial]({NORTHWEST_TUTORIAL_URL})")
    elif st.session_state["scenario_preset"] == PRESET_CUSTOM:
        st.info("Enter your own documented electricity shares. The new scenario starts at 0%; the shares must total 100% before export.")
    else:
        st.caption("The demonstration shares are hypothetical and are not measurements from any particular region.")

    st.subheader("Scenario metadata")
    c1,c2,c3 = st.columns(3)
    with c1:
        region = st.text_input("Region / scenario label", key="scenario_region")
        year = st.number_input("Reference year", 1990, 2100, step=1, key="scenario_year")
    with c2:
        boundary = st.selectbox("What do the shares represent?", ["hypothetical", "consumption", "generation"], key="scenario_boundary", help="Local generation is not necessarily the mix consumed by facilities.")
        evidence_status = st.selectbox("Evidence / review status", ["illustrative", "user_supplied_unverified", "verified"], key="scenario_evidence", help="Verified means an instructor checked the provenance, geographic scope, balance and year.")
    with c3:
        voltage = st.selectbox(
            "Electricity delivery level", ["high", "medium", "low"],
            key="scenario_voltage", on_change=on_voltage_change,
            help="MV export requires a locally reviewed region adapter; low voltage is not supported.",
        )
        losses_pct = st.number_input(
            "Losses to delivered kWh (%) — simplified scaling",
            min_value=0.0, max_value=34.9, step=0.5,
            key="scenario_losses_pct", disabled=(voltage == "medium"),
            help="MV export uses reviewed transformation and market losses instead of this generic adjustment.",
        )
    source_url = st.text_input("Primary public data source URL (required for documented scenarios)", key="scenario_source_url")
    ecoinvent_version = st.selectbox(
        "Background LCI database (supported for openLCA export)",
        options=SUPPORTED_OPENLCA_DATABASES,
        key="scenario_background",
        help=(
            "Only ecoinvent 3.12 cut-off is supported by the current JSON-LD exporter. "
            "The destination openLCA database must match the instructor's shared .zolca."
        ),
    )

    st.subheader("Generation / supply shares")
    reload_id = st.session_state["preset_reload_id"]
    uploaded = st.file_uploader(
        "Optional: upload a mix CSV (technology, share, source URL, notes)",
        type=["csv"], key=f"mixup_{reload_id}"
    )
    if uploaded is not None:
        raw = uploaded.getvalue().decode("utf-8-sig")
        try:
            mix = parse_mix_csv(raw)
            editor_key = f"mix_{reload_id}_" + hashlib.sha256(raw.encode()).hexdigest()[:8]
        except Exception as e:
            st.error(f"CSV error: {e}")
            mix = []
            editor_key = f"invalid_csv_{reload_id}"
    else:
        mix = st.session_state["starting_mix_rows"]
        editor_key = f"mix_preset_{reload_id}"
    if mix:
        # Legacy input CSVs may include CI columns; they are not used in the
        # student-facing custom unit-process workflow.
        df = pd.DataFrame(mix).reindex(
            columns=["technology", "share", "source_url", "notes"]
        )
        edited = st.data_editor(
            df, num_rows="dynamic", use_container_width=True, key=editor_key,
            column_config={
                "technology": st.column_config.SelectboxColumn(
                    "Technology", options=list(TECHNOLOGIES), required=True,
                ),
                "share": st.column_config.NumberColumn(
                    "Supply fraction (0–1)", min_value=0.0, max_value=1.0, format="%.4f",
                ),
                "source_url": st.column_config.TextColumn("Source URL"),
                "notes": st.column_config.TextColumn("Notes"),
            },
        )
        rows = edited.where(pd.notna(edited), None).to_dict(orient="records")
    else:
        rows = []

    payload = {"region":region,"year":int(year),"boundary":boundary,"evidence_status":evidence_status,
               "voltage":voltage,"loss_fraction":float(losses_pct)/100,"source_url":source_url,
               "ecoinvent_version":ecoinvent_version,"mix":rows}
    errors, warnings = validate_scenario(payload)
    st.markdown("#### Scenario validation")
    sum_col, error_col, advisory_col = st.columns(3)
    with sum_col:
        st.metric("Share sum", f"{sum(float(r.get('share') or 0) for r in rows):.4f}")
    with error_col:
        st.metric("Errors", len(errors))
    with advisory_col:
        st.metric("Advisories", len(warnings))
    st.caption(
        "**Legend:** 🟢 Green = arithmetic checks passed · "
        "🟡 Yellow = data provenance or scientific representativeness advisory · "
        "🔴 Red = invalid input (blocks export)."
    )
    if errors:
        st.error(f"{len(errors)} input error(s) must be corrected before export.")
        with st.expander(f"View {len(errors)} input error(s)", expanded=True):
            for error in errors:
                st.error(error)
    else:
        st.success(
            "Arithmetic checks passed. This does not independently verify "
            "the regional electricity mix."
        )
    if warnings:
        st.warning(
            f"{len(warnings)} advisory item(s): review the data sources and "
            "scientific representativeness before interpreting results."
        )
        with st.expander(f"View {len(warnings)} validation advisories"):
            for warning in warnings:
                st.warning(warning)
    st.session_state["scenario_payload"] = payload
    st.session_state["scenario_errors"] = errors
    st.session_state["scenario_warnings"] = warnings

with tab_library:
    st.subheader("Find electricity generation providers in your shared .zolca")
    st.caption(
        "Use an instructor-reviewed provider library extracted from the exact ecoinvent 3.12 "
        "cut-off .zolca distributed to the class. This library has names and UUIDs only; "
        "it contains no inventory exchanges or carbon intensity values."
    )
    provider_library = None
    try:
        library_secret = st.secrets.get("provider_library_json")
    except (FileNotFoundError, KeyError, AttributeError):
        library_secret = None
    if library_secret:
        try:
            provider_library = json.loads(library_secret) if isinstance(library_secret, str) else dict(library_secret)
            st.success("Instructor provider library loaded from deployment settings.")
        except (TypeError, ValueError) as exc:
            st.error(f"Provider library secret could not be decoded: {exc}")
    if provider_library is None:
        library_upload = st.file_uploader(
            "Upload an instructor-approved provider library (JSON)", type=["json"], key="library_upload"
        )
        if library_upload is not None:
            try:
                provider_library = json.loads(library_upload.getvalue().decode("utf-8-sig"))
            except (UnicodeDecodeError, ValueError) as exc:
                st.error(f"Invalid provider library JSON: {exc}")
    st.session_state["provider_library_data"] = provider_library
    st.session_state["selected_provider_ids"] = {}
    if provider_library is None:
        st.info(
            "The instructor has not configured a provider library yet. "
            "You can still define and document a supply-mix scenario. Exporting a "
            "linked openLCA process requires an instructor-reviewed provider library."
        )
    else:
        problems = library_errors(provider_library)
        for problem in problems:
            st.error(problem)
        if not problems:
            st.success(
                f"{len(approved_candidates(provider_library))} approved electricity providers available "
                f"for {provider_library['database_label']}."
            )
            st.warning(
                "Approved providers are compatible with the selected high-voltage product flow. "
                "A catalog approval does not verify the regional electricity mix or "
                "authorize redistribution of ecoinvent data."
            )
            st.markdown("#### A · Existing regional electricity markets (baseline reference)")
            st.caption(
                "These datasets are pre-mixed electricity markets. Use them as baseline "
                "references in openLCA, NOT as generation technologies in a custom grid."
            )
            available_markets = approved_markets(provider_library)
            if not available_markets:
                st.info(
                    "No approved electricity markets available yet. The instructor must run "
                    "the v0.5 extractor and review/approve market candidates."
                )
            else:
                market_voltage = st.selectbox(
                    "Market voltage", ["high", "medium", "low"], key="market_voltage"
                )
                market_search = st.text_input(
                    "Search regional electricity markets (activity / geography)",
                    key="market_search",
                ).strip().lower()
                filtered_markets = approved_markets(provider_library, voltage=market_voltage)
                if market_search:
                    filtered_markets = [
                        m for m in filtered_markets
                        if market_search in (m["name"] + " " + m.get("location", "")).lower()
                    ]
                st.selectbox(
                    "Existing market for baseline comparison",
                    options=[None] + [m["id"] for m in filtered_markets],
                    format_func=lambda uid: (
                        "Choose a market (optional)" if uid is None else next(
                            f"{m['name']} · {m.get('location', 'Not specified')}"
                            for m in filtered_markets if m["id"] == uid
                        )
                    ),
                    key="existing_market_baseline",
                )
                st.caption(
                    "Baseline selection is a reference only: v0.5 does not replace "
                    "or import this already-existing process. Choose the matching "
                    "market in your local openLCA product system."
                )
            st.divider()
            st.markdown("#### B · Generation providers for a custom electricity mix")
            st.caption(
                "Providers are listed by geographic relevance, then by process type. "
                "Geographic proximity is a search aid, not proof of representativeness. "
                "Cogeneration needs fuel/technology review; industrial co-products and "
                "storage processes are hidden unless you enable advanced options."
            )
            active_mix = [
                row for row in st.session_state.get("scenario_payload", {}).get("mix", [])
                if float(row.get("share") or 0) > 0
            ]
            selected = {}
            justifications = {}
            region_name = st.session_state.get("scenario_payload", {}).get("region", "")
            for row in active_mix:
                tech = row["technology"]
                st.markdown(f"**{tech.replace('_', ' ').title()} — {float(row['share']):.2%}**")
                tech_options = approved_candidates(provider_library, technology=tech)
                locations = sorted({e.get("location", "Not specified") for e in tech_options})
                left, right = st.columns(2)
                with left:
                    location_filter = st.selectbox(
                        f"{tech} — Geography",
                        ["All geographies"] + locations,
                        key=f"provider_geo_{tech}",
                    )
                with right:
                    text_filter = st.text_input(
                        f"{tech} — Search activity", key=f"provider_search_{tech}",
                    ).strip()
                show_advanced = st.checkbox(
                    f"{tech} — Include industrial co-products, storage and other unusual processes",
                    key=f"provider_advanced_{tech}",
                    value=False,
                )
                options = ranked_candidates(
                    provider_library, tech, region_name,
                    geography=location_filter, search=text_filter,
                    include_advanced=show_advanced,
                )
                if not options:
                    st.warning(
                        f"No approved {tech} providers match the filters. "
                        "Clear the search or request an instructor-reviewed provider."
                    )
                    continue
                indexed = {e["id"]: e for e in options}
                uuid_choice = st.selectbox(
                    f"Choose {tech} generation process",
                    options=[None] + list(indexed),
                    format_func=lambda pid, lookup=indexed: (
                        "Select a provider..." if pid is None else
                        f"{lookup[pid]['name']} · {lookup[pid].get('location', 'Not specified')} "
                        f"· {provider_class(lookup[pid]).replace('_', ' ').title()}"
                    ),
                    key=f"provider_{st.session_state['preset_reload_id']}_{tech}_{location_filter}_{text_filter}_{show_advanced}",
                )
                if uuid_choice is not None:
                    provider = indexed[uuid_choice]
                    role = provider_class(provider)
                    geography_tier = region_preference(provider.get("location", ""), region_name)[0]
                    if role == "cogeneration":
                        st.warning(
                            "Cogeneration: confirm the actual fuel and heat/electricity "
                            "allocation assumptions before selecting this provider."
                        )
                    elif role in ("industrial_coproduct", "storage", "review"):
                        st.warning(
                            "Advanced provider: this is not a standard dedicated generation "
                            "process. Verify the electricity-reference output, co-product "
                            "treatment and suitability with your instructor."
                        )
                    if geography_tier > 0 and region_name and "hypothetical" not in region_name.lower():
                        st.caption("Geographic proxy: explain why a non-local dataset is suitable.")
                    rationale = st.text_input(
                        f"Why did you select this {tech} provider? (required for export)",
                        key=f"provider_rationale_{st.session_state['preset_reload_id']}_{tech}_{uuid_choice}",
                        placeholder="E.g., Ontario location and matching run-of-river technology",
                    ).strip()
                    selected[tech] = uuid_choice
                    justifications[tech] = rationale
            st.session_state["selected_provider_ids"] = selected
            st.session_state["selection_justifications"] = justifications
            st.caption(
                f"Selected {len(selected)} of {len(active_mix)} active providers. "
                "Nothing is selected automatically. Each choice requires a short rationale."
            )
            selected_voltage = st.session_state.get("scenario_payload", {}).get("voltage")
            if selected_voltage == "medium":
                st.info(
                    "MV export is supported in v0.9 with an additional instructor-reviewed "
                    "regional HV market → transformer → MV market adapter in Tab 3. "
                    "The adapter must come from the same licensed .zolca."
                )
            elif selected_voltage == "low":
                st.warning("Low-voltage custom supply is not supported by this exporter.")


with tab_openlca:
    st.subheader("Export custom high- or medium-voltage electricity")
    st.info(
        "HV export requires approved generation providers. For medium voltage, "
        "you can first reproduce an original ecoinvent market WITHOUT approving "
        "generation providers. Custom MV export is locked until you review the "
        "source and record successful openLCA LCIA replication."
    )
    st.caption(
        "All work must target the identical restored ecoinvent 3.12 cut-off .zolca; "
        "imported process links and environmental results require local openLCA checks."
    )
    catalog = None
    library = st.session_state.get("provider_library_data")
    if library is not None:
        problems = library_errors(library)
        if problems:
            st.error("Generation provider library needs instructor review in Tab 2.")
        else:
            chosen = st.session_state.get("selected_provider_ids", {})
            active = [
                r["technology"] for r in
                st.session_state.get("scenario_payload", {}).get("mix", [])
                if float(r.get("share") or 0) > 0
            ]
            missing = [tech for tech in active if tech not in chosen]
            missing_reasons = [
                tech for tech in active
                if tech in chosen and not st.session_state.get(
                    "selection_justifications", {}
                ).get(tech, "").strip()
            ]
            if missing:
                st.info(
                    "For custom HV/MV export, choose approved generation providers in Tab 2: "
                    + ", ".join(missing)
                    + ". Baseline MV replication does not need these selections."
                )
            elif missing_reasons:
                st.info(
                    "For custom export, document the provider rationale in Tab 2: "
                    + ", ".join(missing_reasons)
                )
            else:
                try:
                    catalog = catalog_for_selection(
                        library, chosen,
                        st.session_state.get("selection_justifications", {}),
                    )
                except ValueError as exc:
                    st.error(str(exc))
    else:
        try:
            secret_catalog = st.secrets.get("provider_catalog_json")
        except (FileNotFoundError, KeyError, AttributeError):
            secret_catalog = None
        if secret_catalog:
            try:
                catalog = (
                    json.loads(secret_catalog) if isinstance(secret_catalog, str)
                    else dict(secret_catalog)
                )
            except (ValueError, TypeError) as exc:
                st.error(f"Legacy instructor catalog is invalid: {exc}")
        if catalog is None and st.session_state.get("scenario_voltage") == "high":
            legacy_upload = st.file_uploader(
                "Optional: legacy v0.2 instructor generator catalog (JSON)",
                type=["json"], key="catalog_upload",
            )
            if legacy_upload is not None:
                try:
                    catalog = json.loads(
                        legacy_upload.getvalue().decode("utf-8-sig")
                    )
                except (ValueError, UnicodeDecodeError) as exc:
                    st.error(f"Legacy catalog could not be read: {exc}")

    sc = st.session_state.get("scenario_payload")
    if sc is None:
        st.warning("Create a scenario in Tab 1 first.")
    elif sc.get("voltage") == "high":
        st.markdown("#### High-voltage generation mix")
        if catalog is None:
            st.warning("Configure and select approved generation providers in Tab 2 first.")
        else:
            cat_errors, cat_warnings = validate_catalog(catalog, sc)
            for err in cat_errors:
                st.error(err)
            for warning in cat_warnings:
                st.warning(warning)
            if not cat_errors:
                details = package_preview(sc, catalog)
                st.success("HV package passed structural checks (not a verified LCA).")
                st.write("**Output process:**", details["name"])
                st.dataframe(
                    pd.DataFrame(details["inputs"]), hide_index=True,
                    use_container_width=True,
                )
                st.download_button(
                    "Download HV openLCA JSON-LD ZIP",
                    make_openlca_package(sc, catalog),
                    file_name="electricity_HV_openLCA_IMPORT.zip",
                    mime="application/zip", type="primary",
                )
    elif sc.get("voltage") == "medium":
        st.markdown("#### Medium-voltage workflow · v0.9")
        st.warning(
            "The MV adapter contains licensed ecoinvent exchange coefficients. "
            "Use the app LOCALLY unless your ecoinvent license explicitly permits "
            "transmitting those data to Streamlit Cloud. Do not commit adapter JSON."
        )
        try:
            mv_adapter_secret = st.secrets.get("mv_adapter_json")
        except (FileNotFoundError, KeyError, AttributeError):
            mv_adapter_secret = None
        source_adapter = None
        if mv_adapter_secret:
            try:
                source_adapter = (
                    json.loads(mv_adapter_secret)
                    if isinstance(mv_adapter_secret, str)
                    else dict(mv_adapter_secret)
                )
            except (ValueError, TypeError) as exc:
                st.error(f"MV adapter in settings is invalid: {exc}")
        if source_adapter is None:
            adapter_upload = st.file_uploader(
                "Local extracted or reviewed MV adapter (JSON)",
                type=["json"], key="mv_adapter_upload",
            )
            if adapter_upload is not None:
                try:
                    source_adapter = json.loads(
                        adapter_upload.getvalue().decode("utf-8-sig")
                    )
                except (UnicodeDecodeError, ValueError) as exc:
                    st.error(f"MV adapter JSON could not be read: {exc}")
        if source_adapter is None:
            st.info(
                "Upload mv_adapter_REVIEW_LOCAL.json from the IPC extractor. "
                "It can be EXTRACTED (unreviewed); no generator-provider catalog "
                "or approval is needed for the baseline replication ZIP."
            )
        else:
            adapter = source_adapter
            try:
                working = st.session_state.get("mv_working_adapter")
                if (
                    isinstance(working, dict)
                    and source_fingerprint(working) == source_fingerprint(source_adapter)
                ):
                    stages = ("extracted", "reviewed_for_testing", "replication_validated")
                    if (adapter_review_status(working) in stages
                            and adapter_review_status(source_adapter) in stages
                            and stages.index(adapter_review_status(working)) >
                                stages.index(adapter_review_status(source_adapter))):
                        adapter = working
            except (TypeError, ValueError, KeyError) as exc:
                st.error(f"Adapter fingerprint could not be computed: {exc}")
            mv_structure_errors, mv_structure_warnings = validate_mv_structure(adapter)
            st.markdown(
                "**Stage:** " + adapter_review_status(adapter).replace("_", " ").title()
            )
            for err in mv_structure_errors:
                st.error(err)
            if mv_structure_warnings:
                with st.expander(f"View {len(mv_structure_warnings)} structural caveats"):
                    for warning in mv_structure_warnings:
                        st.warning(warning)
            if not mv_structure_errors:
                replicate = make_mv_replication_processes(adapter)
                st.caption(
                    "Adapter geography: " + str(adapter["region"]) +
                    " · Source fingerprint: " + source_fingerprint(adapter)[:16]
                )
                st.markdown("##### Stage 1 · Baseline replication (no scientific approval required)")
                st.success(
                    "Source topology passed structural checks. A baseline replication "
                    "ZIP is available independently of any generation-provider catalog."
                )
                st.write("**Replicated MV process:**", replicate[-1]["name"])
                st.code(replicate[-1]["@id"], language="text")
                st.download_button(
                    "Download baseline MV replication ZIP",
                    mv_replication_package(adapter),
                    file_name="electricity_MV_BASELINE_REPLICATION_openLCA.zip",
                    mime="application/zip",
                )
                st.caption(
                    "Import into a test copy of the matching .zolca without overwriting "
                    "background datasets. Confirm all default providers, then calculate "
                    "the original and replicated MV market at 1 kWh with the SAME LCIA method."
                )

                if adapter_review_status(adapter) == "extracted":
                    st.markdown("##### Stage 2 · Record instructor source review")
                    st.caption(
                        "This records review for TESTING, not scientific approval. "
                        "The four source UUID links and non-electric exchanges should "
                        "be inspected in openLCA."
                    )
                    reviewer = st.text_input(
                        "Reviewer name", key="mv_reviewer", value="Course instructor",
                    )
                    review_notes = st.text_area(
                        "What did you check?",
                        key="mv_review_notes",
                        placeholder=(
                            "Checked HV self-link, transformer-to-HV, MV-to-transformer, "
                            "MV self-link, infrastructure and emissions."
                        ),
                    )
                    review_confirm = st.checkbox(
                        "I inspected the extracted source processes, exchange quantities "
                        "and default-provider links (review for testing only).",
                        key="mv_review_confirm",
                    )
                    if st.button("Record reviewed for testing", key="mv_review_button"):
                        try:
                            if not review_confirm:
                                raise ValueError("Please confirm the source review.")
                            adapter = mark_reviewed_for_testing(
                                adapter, reviewer, review_notes
                            )
                            st.session_state["mv_working_adapter"] = adapter
                            st.success("Recorded source review for testing.")
                        except ValueError as exc:
                            st.error(str(exc))

                stage = adapter_review_status(adapter)
                if stage in ("reviewed_for_testing", "replication_validated"):
                    st.download_button(
                        "Download locally reviewed MV adapter JSON",
                        json.dumps(adapter, indent=2, ensure_ascii=False),
                        file_name="mv_adapter_REVIEWED_LOCAL.json",
                        mime="application/json",
                    )

                if stage == "reviewed_for_testing":
                    st.markdown("##### Stage 3 · Record the openLCA replication comparison")
                    st.caption(
                        "Enter actual openLCA calculation results—not hypothetical values. "
                        "Use the identical LCIA method and 1 kWh MV functional unit. "
                        "A climate-change category and at least one OTHER category "
                        "must match within the recorded tolerance."
                    )
                    comparison_method = st.text_input(
                        "LCIA method and version (same for original and replica)",
                        key="mv_lcia_method",
                        placeholder="e.g., TRACI 2.1",
                    )
                    comparison_reviewer = st.text_input(
                        "Comparison reviewer", key="mv_comparison_reviewer",
                        value="Course instructor",
                    )
                    tolerance_percent = st.number_input(
                        "Relative tolerance (%)",
                        min_value=0.001, max_value=5.0, value=0.1,
                        format="%.3f", key="mv_tolerance_percent",
                    )
                    ca, cb = st.columns(2)
                    with ca:
                        st.markdown("**Impact category 1**")
                        climate_original = st.text_input(
                            "Original GWP / climate-change result",
                            key="mv_climate_original",
                        )
                        climate_replica = st.text_input(
                            "Replicated GWP / climate-change result",
                            key="mv_climate_replicated",
                        )
                        climate_unit = st.text_input(
                            "GWP result unit", key="mv_climate_unit",
                            value="kg CO2 eq",
                        )
                    with cb:
                        st.markdown("**Impact category 2**")
                        other_category = st.text_input(
                            "Other LCIA category name", key="mv_other_category",
                        )
                        other_original = st.text_input(
                            "Original result (other category)", key="mv_other_original",
                        )
                        other_replica = st.text_input(
                            "Replicated result (other category)", key="mv_other_replicated",
                        )
                        other_unit = st.text_input(
                            "Other category unit", key="mv_other_unit",
                        )
                    comparison_notes = st.text_area(
                        "OpenLCA linking checks and comparison notes",
                        key="mv_comparison_notes",
                    )
                    verified_links = st.checkbox(
                        "I checked all copied default providers and self-links in "
                        "openLCA, and used 1 kWh MV in both product-system calculations.",
                        key="mv_links_verified",
                    )
                    if st.button(
                        "Check numerical agreement and record replication evidence",
                        key="mv_record_evidence",
                    ):
                        try:
                            adapter = record_replication_validation(
                                adapter,
                                checked_by=comparison_reviewer,
                                method=comparison_method,
                                comparisons=[
                                    {
                                        "category": "Climate change / GWP",
                                        "original": float(climate_original),
                                        "replicated": float(climate_replica),
                                        "unit": climate_unit,
                                    },
                                    {
                                        "category": other_category,
                                        "original": float(other_original),
                                        "replicated": float(other_replica),
                                        "unit": other_unit,
                                    },
                                ],
                                notes=comparison_notes,
                                links_checked=verified_links,
                                tolerance_percent=tolerance_percent,
                            )
                            st.session_state["mv_working_adapter"] = adapter
                            st.success(
                                "Numerical agreement recorded with source-data fingerprint. "
                                "Results were entered by the instructor; Streamlit has NOT "
                                "independently calculated or verified LCIA."
                            )
                        except (ValueError, TypeError) as exc:
                            st.error("Cannot record replication evidence: " + str(exc))

                if adapter_review_status(adapter) == "replication_validated":
                    evidence_errors = replication_evidence_errors(adapter)
                    for err in evidence_errors:
                        st.error(err)
                    if not evidence_errors:
                        st.success(
                            "Instructor-entered LCIA replication evidence passes the "
                            "recorded tolerance and is bound to this exact adapter."
                        )
                        st.download_button(
                            "Download replication-validated adapter JSON (LOCAL)",
                            json.dumps(adapter, indent=2, ensure_ascii=False),
                            file_name="mv_adapter_REPLICATION_VALIDATED_LOCAL.json",
                            mime="application/json",
                        )

                st.markdown("##### Stage 4 · Customized MV electricity")
                if catalog is None:
                    st.info(
                        "Custom MV export also requires approved generation providers "
                        "selected in Tab 2. Baseline replication above remains available."
                    )
                custom_errors = []
                if catalog is not None:
                    custom_errors, custom_warnings = validate_mv_adapter(
                        adapter, catalog, sc
                    )
                    if custom_errors:
                        with st.expander(
                            f"Custom MV export locked · {len(custom_errors)} requirements",
                            expanded=True,
                        ):
                            for err in custom_errors:
                                st.warning(err)
                    elif custom_warnings:
                        with st.expander(
                            f"View {len(custom_warnings)} custom modeling advisories"
                        ):
                            for warning in custom_warnings:
                                st.warning(warning)
                if catalog is not None and not custom_errors:
                    summary = mv_preview(sc, catalog, adapter)
                    c1, c2, c3 = st.columns(3)
                    c1.metric(
                        "HV kWh per transformed MV kWh",
                        f"{summary['transformation_hv_per_mv_kwh']:.7f}",
                    )
                    c2.metric(
                        "MV self-input (kWh/kWh)",
                        f"{summary['mv_self_input_kwh_per_kwh']:.7f}",
                    )
                    c3.metric(
                        "Direct MV generation rerouted",
                        f"{summary['original_direct_mv_kwh_replaced']:.7f}",
                    )
                    st.dataframe(
                        pd.DataFrame(summary["processes"]),
                        use_container_width=True, hide_index=True,
                    )
                    st.download_button(
                        "Download customized MV JSON-LD ZIP",
                        mv_package(sc, catalog, adapter, replicate=False),
                        file_name="electricity_MV_CUSTOM_openLCA.zip",
                        mime="application/zip", type="primary",
                    )
                    st.warning(
                        "Instructor-recorded replication does NOT verify regional "
                        "representativeness. Custom mode routes ALL modeled generation "
                        "through HV, using the source region's network as a proxy."
                    )
            st.session_state["mv_adapter_data"] = adapter
    else:
        st.warning("Low-voltage export is not supported. Select HV or MV in Tab 1.")

    st.divider()
    st.subheader("Scenario documentation")
    st.caption(
        "Save the assumptions and source record whether or not the instructor "
        "provider library is configured. This documentation ZIP is NOT an "
        "openLCA-importable process; use the JSON-LD ZIP above for that."
    )
    sc_doc = st.session_state.get("scenario_payload")
    doc_errors = st.session_state.get("scenario_errors", [])
    doc_warnings = st.session_state.get("scenario_warnings", [])
    if sc_doc is None:
        st.info("Define a supply mix in Tab 1 to download documentation.")
    elif doc_errors:
        st.error("Fix the input validation errors in Tab 1 before exporting documentation.")
    else:
        active_catalog = catalog if catalog is not None else None
        provider_decisions = (
            {
                tech: {
                    "process_id": entry["id"],
                    "process_name": entry["name"],
                    "location": entry.get("location", "Not specified"),
                    "selection_reason": entry.get("selection_reason", ""),
                }
                for tech, entry in active_catalog["providers"].items()
            }
            if active_catalog is not None else {}
        )
        report = scenario_documentation_report(
            sc_doc, doc_errors, doc_warnings, provider_decisions
        )
        if sc_doc.get("voltage") == "medium":
            adapter_documented = st.session_state.get("mv_adapter_data")
            report += (
                "\n## Medium-voltage modeling (v0.9)\n\n"
                "- Regional HV market, HV-to-MV transformation, and MV market require "
                "an approved local adapter from the exact licensed background database.\n"
                "- No generic loss factor should be added on top of adapter losses.\n"
                "- Custom mode reroutes the original direct-MV generation through the HV pathway; "
                "the generation-to-consumption mapping remains an assumption.\n"
                "- Baseline LCIA replication and local provider linking are prerequisites "
                "for interpreting a customized MV result.\n"
                f"- Regional adapter geography: "
                f"{adapter_documented.get('region', 'not yet supplied') if isinstance(adapter_documented, dict) else 'not yet supplied'}\n"
            )
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(
            archive_buffer, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr(
                "scenario.json",
                json.dumps(sc_doc, indent=2, ensure_ascii=False),
            )
            archive.writestr("mix.csv", dump_supply_mix_csv(sc_doc["mix"]))
            archive.writestr("methodology_report.md", report)
            if provider_decisions:
                archive.writestr(
                    "selected_providers.json",
                    json.dumps(provider_decisions, indent=2, ensure_ascii=False),
                )
        docs_left, docs_right = st.columns(2)
        with docs_left:
            st.download_button(
                "Download scenario ZIP (documentation)",
                archive_buffer.getvalue(),
                file_name="electricity_scenario_documentation.zip",
                mime="application/zip",
            )
        with docs_right:
            st.download_button(
                "Download methodology report",
                report,
                file_name="methodology_report.md",
                mime="text/markdown",
            )
        st.caption(
            "The scenario archive contains source assumptions and, when the "
            "provider catalog is available, the selected provider metadata. "
            "Review distribution rights before sharing catalog-derived metadata."
        )

with tab_help:
    st.markdown(
        f"**Worked example:** [IESO Northwest 2025 student tutorial]({NORTHWEST_TUTORIAL_URL}). "
        "Its client-proposed generation shares are unverified."
    )
    st.markdown("""### Student workflow

1. **Build supply mix (Tab 1):** Choose a scenario, enter generation shares, sources, year and the generation/consumption boundary. Review share validation and scientific advisories.
2. **Select providers (Tab 2):** Search the instructor-approved ecoinvent 3.12 cut-off provider catalog. Choose suitable **generation** processes (not pre-mixed electricity markets) and document each selection.
3. **Export to openLCA (Tab 3):** For HV, download the generation-mix ZIP. For MV, upload a local extracted adapter, download and test the baseline replication without a generator catalog, record source review and two-category openLCA LCIA comparison, and only then unlock custom export. Download scenario documentation separately.
4. **Calculate in openLCA:** Restore the same class `.zolca`, import the JSON-LD ZIP, verify provider links and calculate the complete product-system LCI/LCIA. Compare the custom supply scenario with your existing grid baseline.

### Key cautions

- A regional **generation** mix is not automatically the electricity mix **consumed** at a site; imports, exports, losses and interzonal transfers can matter.
- The tool neither retrieves official regional grid statistics nor redistributes licensed ecoinvent inventories.
- MV export is a **v0.9 pilot**. Baseline replication needs an extracted region adapter; customized export requires reviewed source links, instructor-entered LCIA replication evidence and an approved generation catalog. An importable ZIP alone is not verification. Low voltage remains unsupported.
- MV customization preserves source-market network exchanges but routes all scenario generation through HV; direct MV generation, imports and proxies must be reviewed.
- Never publish or upload exchange-bearing MV adapters to a cloud app without confirming ecoinvent licensing permissions.
- An instructor-approved provider catalog checks dataset references, not whether regional generation assumptions are representative.
- **An importable ZIP is not a verified LCA result.** Examine the imported exchanges, provider UUIDs and calculated LCIA results in your own licensed openLCA database.
""")
