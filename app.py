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
st.caption(
    "A student-friendly tool for regional electricity LCA modeling, "
    "carbon intensity estimation, and sensitivity analysis."
)
st.info(
    "This tool supports electricity LCA scenario modeling for any "
    "geographic location. The default electricity mix is hypothetical "
    "and provided for demonstration purposes only. Users are responsible "
    "for verifying their input data. The tool does not automatically "
    "retrieve government electricity statistics or provide licensed "
    "background LCI datasets."
)

tab_build, tab_impact, tab_export, tab_openlca, tab_help = st.tabs(["1 · Build supply mix", "2 · GWP sensitivity", "3 · Scenario ZIP", "4 · openLCA import", "Guide & cautions"])

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
    left, right = st.columns(2)
    with left:
        st.metric("Share sum", f"{sum(float(r.get('share') or 0) for r in rows):.4f}")
        st.metric("Validation errors", len(errors))
    with right:
        candidate_ci = regional_lifecycle_ci(payload) if not errors else None
        st.metric("Computed life-cycle CI", f"{candidate_ci:,.1f} g CO₂e/kWh" if candidate_ci is not None else "Not available")
        st.caption("Computed only if ALL technology-specific life-cycle CI inputs are entered. These are not bundled, and the value is a screening estimate.")
    for e in errors:
        st.error(e)
    for w in warnings:
        st.warning(w)
    if not errors:
        st.success("Mix passes arithmetic checks. Scientific representativeness still requires instructor review.")
    st.session_state["scenario_payload"] = payload
    st.session_state["scenario_errors"] = errors
    st.session_state["scenario_warnings"] = warnings

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
        st.write("**For openLCA:** Visit Tab 4 to generate a native openLCA JSON-LD ZIP when an instructor-approved provider catalog is available. This scenario ZIP is for documentation and is not directly importable into openLCA.")
        st.warning("Output is not a certified or validated regional LCI. A successful export does not mean a supply mix has been verified.")


with tab_openlca:
    st.subheader("Export an openLCA 2-compatible foreground process")
    st.info("The instructor configures provider IDs ONCE for the exact destination ecoinvent database. Students never need to choose provider UUIDs. This package references existing local providers; it does not include licensed inventories.")
    st.markdown("**Prerequisites:** openLCA 2, a matching ecoinvent 3.12 cut-off database, and an instructor-approved provider catalog. Only HIGH-voltage electricity is supported in this release.")
    catalog = None
    try:
        secret_catalog = st.secrets.get("provider_catalog_json")
    except (FileNotFoundError, KeyError, AttributeError):
        secret_catalog = None
    if secret_catalog:
        try:
            catalog = json.loads(secret_catalog) if isinstance(secret_catalog, str) else dict(secret_catalog)
            st.success("Instructor catalog loaded from app deployment settings.")
        except (ValueError, TypeError) as ex:
            st.error(f"Instructor deployment catalog is invalid: {ex}")
    if catalog is None:
        catalog_up = st.file_uploader("Upload instructor-approved provider catalog (JSON)", type=["json"], key="catalog_upload")
        if catalog_up is not None:
            try:
                catalog = json.loads(catalog_up.getvalue().decode("utf-8-sig"))
            except (ValueError, UnicodeDecodeError) as ex:
                st.error(f"Catalog file could not be read: {ex}")
    sc = st.session_state.get("scenario_payload")
    if catalog is None:
        st.warning("No approved provider catalog available. The scenario calculator and GWP sensitivity work without it, but the openLCA ZIP cannot be generated. Ask the instructor to configure the catalog.")
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
5. For an openLCA import, use Tab 4. Your instructor first creates and approves a provider catalog for the SAME local ecoinvent database. Download the JSON-LD ZIP, import into openLCA, verify provider links and connect it to your project.

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
