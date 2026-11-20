# Regional Electricity LCA Builder — v0.4

**LCA Clinic teaching tool, updated 20 November 2026.** A student-facing Streamlit calculator plus a conditional **native openLCA 2 JSON-LD foreground-process ZIP** exporter. For preliminary attributional LCA and GWP sensitivity work, not a regulator-approved, certified, or measured regional grid model.


## New in v0.4: searchable providers from your shared .zolca

The recommended workflow now uses the **same ecoinvent 3.12 cut-off .zolca** restored by the instructor and students. The instructor extracts a library of electricity generator metadata and provider UUIDs once (using the local openLCA IPC server), reviews/approves individual entries, and lets students search approved generation processes in **Tab 2 · Select providers**. Students then export a custom high-voltage foreground electricity unit process in **Tab 3 · Export to openLCA**. openLCA performs the LCI/LCIA calculations; Streamlit does not have to calculate CI.

**[Read the complete v0.4 instructor setup and student instructions](docs/SETUP_v0.4.md).** This includes the `extract_provider_library.py` command, review and licensing precautions, Streamlit secrets and pilot import checklist. Do not publish a licensed database or unreviewed metadata. The older v0.2 manual provider catalog and GWP sensitivity functions remain available as optional/legacy workflows.

## Legacy v0.2 student workflow (browser → openLCA)

1. Use the hosted Streamlit application. Select year, region, voltage, and **boundary**. Replace the HYPOTHETICAL demonstration mix with a sourced supply mix. Use the GWP sensitivity tab when only direct carbon factors are known.
2. Review share and provenance warnings. For a real consumption-based regional market, account for imports, exports and interzonal transfers. A regional generation mix alone may not represent the site supply.
3. Download the **scenario ZIP** for a methodology record.
4. If the instructor has configured an approved provider catalog matching your local openLCA 2 **ecoinvent 3.12 cut-off** database, select HIGH voltage and download **openLCA JSON-LD ZIP** from Tab 4. Otherwise this option is unavailable; use the GWP sensitivity approach.
5. In openLCA desktop: open the matching target database; right-click **Import → Linked Data (JSON-LD)**, choose the ZIP, select **Never update a dataset that already exists**; import. The ZIP includes **one new foreground unit process**, not copied ecoinvent inventories.
6. Find the custom electricity process under Processes (search `LCA Clinic CUSTOM HV electricity`). Open Inputs/Outputs and verify that all electricity inputs have the correct **default provider**. Run database **Check linking properties** and investigate any missing provider. **Create a product system for the custom process as a test** (using default providers), calculate it, and confirm nonzero/credible LCI and LCIA results.
7. Only then substitute the custom supply process for the appropriate **high-voltage** electricity exchange in your project foreground, rebuild/relink the product system as necessary, calculate and compare with the original provincial-market baseline. Never substitute HV directly for an MV/LV input without properly modeling transformation/distribution.

**Important:** A successful file import does not prove that the provider links work. Live testing against the actual licensed database is still required. If provider UUIDs do not match, ask the instructor for the catalog generated specifically for your database; do not manually guess or switch UUIDs.

## Legacy v0.2 instructor setup (for manual provider mapping)

The class must have access to a properly licensed **openLCA Nexus ecoinvent 3.12 cut-off unit-process database** in openLCA 2. The *same database installation/version* must be used to generate the catalog and import students' scenario packages. Check institutional licensing and whether provider metadata may be uploaded to a cloud service; do not publish ecoinvent inventories or uncontrolled catalog exports.

1. Open the target database in openLCA, start **Tools → Developer Tools → IPC Server** (typically port 8080).
2. Install instructor-only dependencies on your workstation:

   ```bash
   pip install -r requirements_instructor.txt
   ```

3. Using your local licensed database, identify one suitable high-voltage provider per active technology and enter each actual **process UUID** in `data/INSTRUCTOR_PROVIDER_MAPPING_TEMPLATE.csv`. This is a one-time instructor review, not a student task. Confirm generation technology, geography, reference product, year and cut-off model. All reference outputs must be the **same product-flow UUID**, flow-property UUID and kWh unit UUID. Otherwise the exporter rejects the catalog. Prefer physically appropriate unit processes rather than downstream electricity markets, to prevent double counting.
4. Generate an instructor catalog from the running local server:

   ```bash
   python instructor_catalog.py \
     --mapping data/INSTRUCTOR_PROVIDER_MAPPING_TEMPLATE.csv \
     --database-label 'ecoinvent 3.12 cut-off UPR — my openLCA installation' \
     --reviewer 'Instructor' \
     --out provider_catalog_REVIEW.json
   ```

5. Open `provider_catalog_REVIEW.json`, inspect every provider and metadata, and **explicitly change `"approved": false` to `true` only after review**. The resulting catalog includes process names, identifiers and common reference-flow identifiers, **not inventories or carbon factors**. Check sharing rights before hosting it.
6. Configure the hosted Streamlit app with the approved JSON as secret key `provider_catalog_json` (escaped JSON string), **or** allow authorized users to upload the catalog in Tab 4. Do not check any approved catalog into a public GitHub repository. The server must not connect to the licensed local database.
7. Pilot by creating a **hypothetical** scenario, generating the ZIP, importing it into a **backup/test copy** of the exact database, running `Check linking properties` and computing a product-system LCIA. Review voltage and system-boundary treatment before classroom use.

If multiple databases or ecoinvent releases are in use, create a separate catalog for each; UUIDs may differ across versions and openLCA conversions. Only ecoinvent **3.12 cut-off**, high-voltage, same-flow links are supported by this starter.

## Deploy on Streamlit Community Cloud

Only `app.py`, `grid_core.py`, `openlca_jsonld.py`, `requirements.txt`, and the teaching data/docs are needed on the cloud server. Use `app.py` as the entrypoint. The cloud dependencies are `streamlit` and `pandas`; **openLCA and the ecoinvent database are never installed in the cloud**. The instructor script `instructor_catalog.py` and `requirements_instructor.txt` run separately on an authorized workstation.

- Students can use the web calculator and export documentation without ecoinvent or openLCA.
- To **calculate** a full LCA from the imported foreground process, students need openLCA 2 and access to the matching licensed background database, or an institutional computing environment.
- Uploaded data are processed during the app session. Review client confidentiality and hosting policies before inputting sensitive facility information.

## Contents

- `app.py`: Streamlit interface with preset mix selection, searchable provider selector, and openLCA export.
- `grid_core.py`: validated supply shares and GWP screening.
- `openlca_jsonld.py`: native openLCA 2 ZIP process exporter (`olca-schema.json`, `processes/<UUID>.json`), with guarded use of external provider refs.
- `instructor_catalog.py`: optional legacy v0.2 one-time manual catalog generator.\n- `extract_provider_library.py`: recommended v0.4 local IPC discovery script for all electricity generation candidates.\n- `provider_library.py`: validates approved searchable provider metadata and maps student selections into exporter references.
- `openlca_bridge.py`: optional **legacy v0.1** alternative direct IPC writer (not needed for student ZIP workflow).
- `Electricity_Scenario_Student_Template.xlsx`: classroom assumptions and sensitivity companion.
- `data/`: example **hypothetical** mix, example scenario, and a blank instructor mapping template. **No real IESO Northwest CI or ecoinvent inventories are bundled.**
- `tests/`: core calculations plus JSON-LD structure and guardrails.

## Boundaries and warnings

- No current, official, consumption-based IESO Northwest CI is bundled or assumed.
- The supplied mix may be **generation based**, **consumption based**, or purely **hypothetical**; label accordingly. The exporter does not verify regional electricity transfers or generation statistics.
- High-voltage **only** for native openLCA exporter. MV/LV transformation, transmission infrastructure, grid services, imports, hourly modeling, consequential effects, and system-specific losses are **not** reconstructed automatically.
- A `loss_fraction` greater than zero only scales upstream electricity kWh, not grid construction, voltage conversion or electricity use at other voltages. Default to zero unless explicitly justified.
- No upstream inventory or LCIA is calculated on the cloud. Student-provided lifecycle emission factors can be used for **screening**, but are not embedded in the imported process.
- No provider catalog is published because actual IDs must be obtained from a local licensed database. The provider catalog does **not** make a data mix independently scientifically valid.
- No actual openLCA 2 server or licensed ecoinvent DB was available for end-to-end import/link calculation testing in this build environment. The package matches the published openLCA 2 ZIP schema and passed structural and logic tests, but **classroom deployment requires the instructor's live database pilot**.

## Sources and format documentation

- Native openLCA 2 ZIP schema: https://greendelta.github.io/olca-schema/
- JSON-LD database import guidance: https://greendelta.github.io/openLCA2-manual/databases/importing_and_combining_databases.html
- GreenDelta `olca-schema.zipio.ZipWriter` package version format: https://github.com/GreenDelta/olca-schema/blob/master/py/olca_schema/zipio.py
- 3.12 implementation and UUID caveats: https://www.openlca.org/ecoinvent-3-12-available-for-openlca/
- IESO source data: https://www.ieso.ca/en/Power-Data/Data-Directory

## Testing

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py grid_core.py openlca_jsonld.py instructor_catalog.py
```

Tests cover share arithmetic, sensitivity results, native ZIP structure, flow/provider linking references, loss scaling, deterministic IDs, rejection of missing/unapproved/wrong-voltage catalogs and instructor catalog creation. **Passing tests is not a substitute for an actual openLCA import and LCIA calculation.**
