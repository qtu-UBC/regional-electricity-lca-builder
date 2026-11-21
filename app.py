"""Regional Electricity LCA Builder — Streamlit student interface.

Run: streamlit run app.py
No internet or licensed ecoinvent processes are required to use the scenario/sensitivity modules.
"""
import io
import json
import hashlib
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from grid_core import (TECHNOLOGIES, parse_mix_csv, validate_scenario, regional_lifecycle_ci,
                       project_sensitivity, direct_factor_correction, dump_mix_csv, scenario_report)
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
            {"technology": "hydro", "share": 0.8, "ci_lifecycle_g_per_kwh": None,
             "source_url": "", "notes": "HYPOTHETICAL demonstration value"},
            {"technology": "nuclear", "share": 0.1, "ci_lifecycle_g_per_kwh": None,
             "source_url": "", "notes": "HYPOTHETICAL demonstration value"},
            {"technology": "natural_gas", "share": 0.1, "ci_lifecycle_g_per_kwh": None,
             "source_url": "", "notes": "HYPOTHETICAL demonstration value"},
        ]
    return [{"technology": "hydro", "share": 0.0, "ci_lifecycle_g_per_kwh": None,
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

tab_build, tab_library, tab_openlca, tab_impact, tab_export, tab_help = st.tabs(["1 · Build supply mix", "2 · Select providers", "3 · Export to openLCA", "4 · GWP screening (optional)", "5 · Scenario ZIP", "Guide & cautions"])

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
        losses_pct = st.number_input("Losses to delivered kWh (%) — screening scaling", min_value=0.0, max_value=34.9, step=0.5, key="scenario_losses_pct")
    source_url = st.text_input("Primary public data source URL (required for documented scenarios)", key="scenario_source_url")
    ecoinvent_version = st.text_input("Background LCI identifier (optional for GWP screening)", key="scenario_background")

    st.subheader("Generation / supply shares")
    reload_id = st.session_state["preset_reload_id"]
    uploaded = st.file_uploader(
        "Optional: upload a mix CSV (technology, share, optional CI, source URL)",
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
        df = pd.DataFrame(mix)
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=editor_key,
            column_config={
                "technology": st.column_config.SelectboxColumn("Technology", options=list(TECHNOLOGIES), required=True),
                "share": st.column_config.NumberColumn("Supply fraction (0–1)", min_value=0.0, max_value=1.0, format="%.4f"),
                "ci_lifecycle_g_per_kwh": st.column_config.NumberColumn("Life-cycle CI (g CO₂e/kWh) · optional", min_value=0.0, format="%.2f"),
                "source_url": st.column_config.TextColumn("Source URL"),
                "notes": st.column_config.TextColumn("Notes"),
            })
        rows = edited.where(pd.notna(edited), None).to_dict(orient="records")
    else:
        rows = []

    payload = {"region":region,"year":int(year),"boundary":boundary,"evidence_status":evidence_status,
               "voltage":voltage,"loss_fraction":float(losses_pct)/100,"source_url":source_url,
               "ecoinvent_version":ecoinvent_version,"mix":rows}
    errors, warnings = validate_scenario(payload)
    st.markdown("#### Scenario validation")
    sum_col, error_col, advisory_col, ci_col = st.columns(4)
    with sum_col:
        st.metric("Share sum", f"{sum(float(r.get('share') or 0) for r in rows):.4f}")
    with error_col:
        st.metric("Errors", len(errors))
    with advisory_col:
        st.metric("Advisories", len(warnings))
    candidate_ci = regional_lifecycle_ci(payload) if not errors else None
    with ci_col:
        st.metric(
            "Life-cycle CI",
            f"{candidate_ci:,.1f} g CO₂e/kWh" if candidate_ci is not None else "Not available",
        )
    st.caption(
        "Life-cycle CI is available only when all active technologies have "
        "compatible life-cycle intensity inputs; the app does not bundle them."
    )
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
            "The scenario and GWP screening tabs remain usable, but a searchable openLCA "
            "provider selection requires the local catalog-extraction step."
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


with tab_impact:
    st.subheader("GWP sensitivity analysis for the whole student LCA")
    st.write("Change only the electricity contribution; all other product-system burdens are held constant. Use the original project's *life-cycle* electricity CI, not a government direct emission factor.")
    a,b,c = st.columns(3)
    with a:
        total = st.number_input("Original total GWP (kg CO₂e / functional unit)", value=1000.0, min_value=0.0, step=10.0)
        kwh = st.number_input("Electricity use (kWh / functional unit)", value=1000.0, min_value=0.0, step=50.0)
    with b:
        original_lc = st.number_input("Original grid *life-cycle* CI (g CO₂e/kWh)", value=100.0, min_value=0.0)
        option = st.radio("Alternative source information", ["Life-cycle CI", "Direct/operational CI only"], horizontal=False)
    with c:
        if option == "Life-cycle CI":
            alt_lc = st.number_input("Alternative *life-cycle* CI (g CO₂e/kWh)", value=20.0, min_value=0.0)
            alt_direct = None
        else:
            original_direct = st.number_input("Original grid *direct* CI (g CO₂e/kWh; SAME boundary/year)", value=50.0, min_value=0.0)
            alt_direct = st.number_input("Alternative grid *direct* CI (g CO₂e/kWh)", value=10.0, min_value=0.0)
            alt_lc = None
    if option == "Direct/operational CI only":
        st.warning("Screening approximation only: assumes unchanged non-direct life-cycle electricity impacts. It may be unsuitable for hydro-dominated scenarios with different technology mixes.")
    try:
        effective_alt = alt_lc if alt_lc is not None else direct_factor_correction(original_lc, original_direct, alt_direct)
        outcome = project_sensitivity(total, kwh, original_lc, effective_alt)
        p,q,r = st.columns(3)
        p.metric("Original total GWP", f"{outcome['original_total_kg_co2e']:,.2f} kg")
        q.metric("Adjusted total GWP", f"{outcome['updated_total_kg_co2e']:,.2f} kg")
        r.metric("Relative change", f"{outcome['percent_change']:+.1f}%" if outcome['percent_change'] is not None else "N/A")
        chart = pd.DataFrame({"GWP (kg CO₂e)":[outcome['original_total_kg_co2e'],outcome['updated_total_kg_co2e']]}, index=["Original","Alternative"])
        st.bar_chart(chart)
        st.caption(f"Alternative electricity factor used: {effective_alt:,.2f} g CO₂e/kWh (" + ("user-supplied lifecycle" if alt_lc is not None else "direct-factor screening correction") + "). Inputs displayed on opening are HYPOTHETICAL EXAMPLES.")
        st.session_state['gwp_result'] = dict(outcome, scenario_type=option, original_grid_lifecycle_g=original_lc,
                                             alternative_grid_lifecycle_g=effective_alt, electricity_kwh=kwh)
    except ValueError as ex:
        st.error(str(ex))
        st.session_state['gwp_result'] = None

with tab_export:
    st.subheader("Reproducible scenario package")
    p = st.session_state.get('scenario_payload')
    e = st.session_state.get('scenario_errors', [])
    w = st.session_state.get('scenario_warnings', [])
    if not p:
        st.info("Enter a valid scenario in Tab 1 first.")
    elif e:
        st.error("Fix arithmetic validation errors in Tab 1 before exporting.")
    else:
        ci = regional_lifecycle_ci(p)
        report = scenario_report(p, e, w, ci)
        template = 'technology,process_uuid,notes\n' + ''.join(f'{row["technology"]},,Select a local openLCA provider process UUID; reference output must be electricity in kWh\n' for row in p['mix'] if float(row['share'])>0)
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("scenario.json", json.dumps(p, indent=2, ensure_ascii=False))
            z.writestr("mix.csv", dump_mix_csv(p['mix']))
            z.writestr("methodology_report.md", report)
            z.writestr("provider_mapping_TEMPLATE.csv", template)
            if st.session_state.get('gwp_result'):
                z.writestr("sensitivity_result.json", json.dumps(st.session_state['gwp_result'], indent=2))
        st.download_button("Download scenario ZIP", b.getvalue(), file_name="electricity_scenario.zip", mime="application/zip", type="primary")
        st.download_button("Download methodology statement", report, file_name="methodology_report.md", mime="text/markdown")
        st.write("**For openLCA:** Select providers in Tab 2, then use Tab 3 to generate a native JSON-LD ZIP. The scenario ZIP here is for documentation, not directly importable into openLCA.")
        st.warning("Output is not a certified or validated regional LCI. A successful export does not mean a supply mix has been verified.")


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

with tab_help:
    st.markdown(
        f"**Worked example:** [IESO Northwest 2025 student tutorial]({NORTHWEST_TUTORIAL_URL}). "
        "The client-proposed shares are generation-based and unverified."
    )
    st.markdown("""### Student workflow
1. Select the grid boundary, year and voltage; upload verifiable supply mix shares (or edit the demonstration).
2. Check that the shares describe electricity **consumed** by the facility; if only local generation is available, clearly state the limitation.
3. Use the GWP tab if only a carbon intensity factor is available; **direct and lifecycle intensities are not interchangeable**.
4. Export the scenario ZIP and attach its methodology report to the assignment.
5. For openLCA, use **Tab 2** to search and choose approved electricity providers and **Tab 3** to export JSON-LD. The instructor first extracts and approves a provider library from the SAME restored .zolca. After import, verify all links and calculate a test product system.

### Important exclusions
- This app does not fetch live electricity data, publish an official Northwest CI, or access licensed ecoinvent content.
- An openLCA JSON-LD ZIP contains only a new foreground process and references existing providers. It cannot work in a different database with different provider UUIDs.
- A hypothetical low-carbon electricity mix is not a measured regional grid.
- Simple upstream kWh scaling for losses is not a substitute for transmission/distribution infrastructure.
- Electricity generation data, imports and exports must be reconciled before calling a regional mix consumption-based.
- The tool is intended for preliminary attributional screening; it does not establish marginal or consequential grid emissions.

### Primary public references
- [IESO Data Directory](https://www.ieso.ca/en/Power-Data/Data-Directory)
- [ECCC Fuel LCA Model methodology](https://www.canada.ca/en/environment-climate-change/services/managing-pollution/fuel-life-cycle-assessment-model/methodology.html)
- [openLCA IPC documentation](https://greendelta.github.io/openLCA-ApiDoc/intro.html)
""")
