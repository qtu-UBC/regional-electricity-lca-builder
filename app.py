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
        voltage = st.selectbox("Electricity delivery level", ["high", "medium", "low"], key="scenario_voltage")
        losses_pct = st.number_input("Losses to delivered kWh (%) — simplified scaling", min_value=0.0, max_value=34.9, step=0.5, key="scenario_losses_pct")
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
            if st.session_state.get("scenario_payload", {}).get("voltage") != "high":
                st.warning("Only high-voltage custom electricity processes can be exported.")


with tab_openlca:
    st.subheader("Export a custom high-voltage electricity unit process")
    st.info(
        "Choose the electricity providers in Tab 2 first. This export contains a single "
        "foreground process referencing processes already inside your licensed .zolca. "
        "The cloud app does not contain ecoinvent inventories."
    )
    st.markdown(
        "**Prerequisites:** matching restored ecoinvent 3.12 cut-off .zolca in openLCA 2, "
        "an instructor-approved provider library, and HIGH-voltage electricity."
    )
    catalog = None
    library = st.session_state.get("provider_library_data")
    if library is not None:
        problems = library_errors(library)
        if problems:
            st.error("The provider library did not pass validation. Return to Tab 2.")
        else:
            chosen = st.session_state.get("selected_provider_ids", {})
            active = [r["technology"] for r in
                      st.session_state.get("scenario_payload", {}).get("mix", [])
                      if float(r.get("share") or 0) > 0]
            missing = [tech for tech in active if tech not in chosen]
            missing_reasons = [
                tech for tech in active
                if tech in chosen and not st.session_state.get("selection_justifications", {}).get(tech, "").strip()
            ]
            if missing:
                st.warning(
                    "Select one approved provider for each active technology in Tab 2: "
                    + ", ".join(missing)
                )
            elif missing_reasons:
                st.warning(
                    "Document why each provider is representative before exporting: "
                    + ", ".join(missing_reasons)
                )
            else:
                try:
                    catalog = catalog_for_selection(
                        library, chosen,
                        st.session_state.get("selection_justifications", {}),
                    )
                    st.success("Provider selections and justifications are ready for export.")
                except ValueError as exc:
                    st.error(str(exc))
    else:
        # Preserve compatibility with the original v0.2 instructor catalog workflow.
        try:
            secret_catalog = st.secrets.get("provider_catalog_json")
        except (FileNotFoundError, KeyError, AttributeError):
            secret_catalog = None
        if secret_catalog:
            try:
                catalog = json.loads(secret_catalog) if isinstance(secret_catalog, str) else dict(secret_catalog)
                st.info("Using the legacy v0.2 instructor catalog.")
            except (ValueError, TypeError) as exc:
                st.error(f"Legacy instructor catalog is invalid: {exc}")
        if catalog is None:
            catalog_up = st.file_uploader(
                "Optional: upload legacy v0.2 instructor catalog (JSON)",
                type=["json"], key="catalog_upload"
            )
            if catalog_up is not None:
                try:
                    catalog = json.loads(catalog_up.getvalue().decode("utf-8-sig"))
                except (ValueError, UnicodeDecodeError) as exc:
                    st.error(f"Catalog file could not be read: {exc}")
    sc = st.session_state.get("scenario_payload")
    if catalog is None:
        st.warning("No complete approved provider selection is available. Configure the library and choose providers in Tab 2, or use the legacy v0.2 catalog.")
    elif sc is not None:
        st.caption(f"Target database: {catalog.get('database_label', 'NOT SPECIFIED')} · Catalog reviewed by: {catalog.get('approved_by', 'UNKNOWN')}")
        cat_errors, cat_warnings = validate_catalog(catalog, sc)
        for error in cat_errors:
            st.error(error)
        for warning in cat_warnings:
            st.warning(warning)
        if not cat_errors:
            details = package_preview(sc, catalog)
            st.success("Ready to create an openLCA JSON-LD ZIP for the specified database (schema checks only).")
            st.write("**Output process:**", details['name'])
            st.dataframe(pd.DataFrame(details['inputs']), use_container_width=True, hide_index=True)
            st.download_button("Download openLCA JSON-LD ZIP", make_openlca_package(sc, catalog),
                               file_name="electricity_foreground_openLCA_IMPORT.zip", mime="application/zip", type="primary")
            st.markdown("""**In openLCA:** Select your matching target database → **Import → Linked Data (JSON-LD)** → choose the downloaded ZIP → **Never update datasets that already exist**. Then inspect the new process's exchanges and default providers, run **Check linking properties**, and connect it to your product system before calculation.""")
            st.warning("Import and provider resolution must be checked locally. This export has not been tested against your licensed openLCA database. A valid ZIP does not establish a regional electricity footprint or LCIA result.")
    else:
        st.warning("Create a scenario in Tab 1 first.")

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
3. **Export to openLCA (Tab 3):** Download the linked JSON-LD foreground unit process and the separate scenario documentation ZIP and methodology report.
4. **Calculate in openLCA:** Restore the same class `.zolca`, import the JSON-LD ZIP, verify provider links and calculate the complete product-system LCI/LCIA. Compare the custom supply scenario with your existing grid baseline.

### Key cautions

- A regional **generation** mix is not automatically the electricity mix **consumed** at a site; imports, exports, losses and interzonal transfers can matter.
- The tool neither retrieves official regional grid statistics nor redistributes licensed ecoinvent inventories.
- The openLCA exporter currently supports only **ecoinvent 3.12 cut-off high-voltage** electricity; medium- and low-voltage transformation and distribution are not reconstructed automatically.
- An instructor-approved provider catalog checks dataset references, not whether regional generation assumptions are representative.
- **An importable ZIP is not a verified LCA result.** Examine the imported exchanges, provider UUIDs and calculated LCIA results in your own licensed openLCA database.
""")
