# Current student interface (v0.7)

The student-facing Streamlit app is organized into **four tabs**:

1. **1 · Build supply mix** — define the regional mix and check arithmetic/provenance.
2. **2 · Select providers** — browse existing markets for the baseline and choose approved generator processes for the custom mix.
3. **3 · Export to openLCA** — download the foreground **JSON-LD ZIP** plus a separate **scenario documentation ZIP** and **methodology report**. Documentation downloads are available even when a provider library has not been configured, as long as the scenario passes arithmetic validation.
4. **Guide & cautions** — short methodology and import instructions.

**GWP screening is no longer part of the student interface.** Students do not enter technology carbon-intensity values; they calculate GWP and other LCIA categories in the licensed local openLCA product system. Older sample CSVs and JSON templates have been updated to omit CI fields. Version 0.8 removes the obsolete screening functions and their CI-specific tests; previous code remains recoverable from Git history.

The filename `SETUP_v0.4.md` remains unchanged to preserve existing links; follow the newer v0.7 instructions in this preface if older steps elsewhere in this document mention superseded tabs.

---

# v0.6 — Provider guidance and documented choices

This update is designed to prevent plausible-looking but inappropriate
electricity provider selection.

1. Students choose a documented grid scenario in **Tab 1**, then go to
   **Tab 2 → B. Generation providers**.
2. Only **instructor-approved** providers appear. The list places the target
   region first (e.g. **Canada, Ontario** for the Northwest example), then
   other Canadian regions, North America, and broader/other datasets.
   This is an aid to finding candidates, not evidence that the closest
   geography is the most representative technology.
3. **Dedicated electricity generation** and **CHP / cogeneration** processes
   are shown by default. Cogeneration datasets require checking the
   technology, biomass fuel and how electricity/heat co-production is modeled.
   **Industrial co-products, pumped storage and ambiguous processes** are
   hidden by default. To inspect them, deliberately enable **advanced
   providers** for that technology and justify why such a process is suitable.
4. The student **must write a short explanation** for every selected provider
   before the **Tab 3** JSON-LD export becomes available. The app records
   this explanation together with the chosen process role, geography and
   source in the imported custom unit process.
5. If no appropriate provider is approved, request instructor review
   rather than substitute an arbitrary dataset. The local 2025 IESO Northwest
   generation shares remain client-proposed and unverified.

The `provider_class` field in the newly extracted library is assigned
**heuristically** from the process name. Instructors must check it against
the actual reference flow and dataset documentation. Existing v0.5
libraries without the field continue to work using the same classifier
at selection time.

The app does **not** calculate an official regional grid CI. openLCA
calculates impacts after the exported foreground process is imported
and linked to the shared licensed ecoinvent 3.12 cut-off `.zolca`.

---

# v0.5 — Electricity markets and generators are separate

Version 0.5 discovers **providers of electricity product flows** directly from openLCA
rather than filtering the activity list solely by names. This includes qualifying
electricity-reference cogeneration activities, and distinguishes:
- **Existing markets:** `market for electricity...` and `market group for electricity...`.
  They can be searched as baseline references at high, medium, or low voltage.
  They are **not** inputs to the customized generation mix.
- **Generation processes:** high-voltage electricity-reference processes (including
  qualifying cogeneration). These are the **only** options for the custom
  high-voltage unit-process exporter.

The script requires the current `olca-ipc` API, using `client.get_providers(flow)`.
Re-run extraction: **old `provider_library_REVIEW.json` files do not contain
the new `markets` section**.

```bash
git pull origin main
python extract_provider_library.py \
  --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
  --reviewer "Course instructor" \
  --out provider_library_REVIEW.json
```

The extracted catalog remains unapproved. Review **both** `entries` (generation)
and `markets` (baseline references). Mark only appropriate individual records
`"approved": true`, and approve the library after confirming the database,
voltage, geography, and licensed-metadata sharing restrictions. If no eligible
biomass/cogeneration process is found, stop rather than substitute a mismatched
provider. An electricity **coproduct** without electricity as the quantitative
reference is not automatically eligible.

Student **Tab 2 · Select providers** now has section A (existing regional markets)
and section B (generation provider assignments). Only section B determines the
custom JSON-LD process exported in Tab 3. For a baseline market, select the
corresponding existing process directly in openLCA.

**Verification:** These changes have not been tested against the instructor's
local `.zolca` or through an actual JSON-LD import. Confirm both before use.

---

# v0.4 — Instructor setup and student workflow

The web application **does not compute life-cycle carbon intensity from ecoinvent**. Instead it builds one regional **high-voltage electricity foreground unit process** with links to electricity generation processes in the instructor's ecoinvent 3.12 **cut-off** `.zolca` database. Students import the exported JSON-LD ZIP into their restored copy of the same database and calculate impacts using openLCA.

## A. Extract provider metadata locally (instructor)

**Do not upload your `.zolca` database to GitHub or Streamlit.** Restore it in openLCA on your own computer. Keep the local database connection and any proprietary process information on that workstation.

1. Clone the repository and open its folder. Set up a Python environment:
   ```bash
   git clone https://github.com/qtu-UBC/regional-electricity-lca-builder.git
   cd regional-electricity-lca-builder
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements_instructor.txt
   ```
   On Windows, activate the environment using `.venv\Scripts\activate`.
2. In openLCA 2, **open the restored ecoinvent 3.12 cut-off database** that students will also restore, then start **Tools → Developer Tools → IPC Server** (normally port 8080).
3. From the project folder, run:
   ```bash
   python extract_provider_library.py \
     --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
     --reviewer "Course instructor" \
     --out provider_library_REVIEW.json
   ```
4. Inspect the resulting JSON. The script finds *candidate* high-voltage electricity-production processes by their activity names, obtains reference-output metadata over IPC, and collects process/flow/unit UUIDs and location names. It excludes market names, rejects non-high-voltage products and groups candidates with an identical reference-output flow, flow property and kWh unit. All candidate entries and the library itself are initially **unapproved**.
5. **Review each candidate manually**: ensure it is an electricity *generation* process (not a market, transformation or downstream supply), check its generation technology, reference product, geography and compatibility with the modeled scenario. Edit `technology` as necessary. Retain only useful providers, or set `approved: true` on individually accepted entries. The catalog can include several approved providers for each technology/geography. Check the `discovery` summary for excluded alternative reference flows; resolve any missing provider categories explicitly.
6. Once reviewed, set `approved: true` at the **library level**, identify the real reviewer in `approved_by`, and update `reviewed_date`. Retain `catalog_version: 2`. The public app rejects unapproved or incomplete libraries.
7. Check whether sharing even process names and UUIDs in a publicly hosted service complies with your ecoinvent agreement. Prefer **session upload** from your own trusted workstation while testing. Do not place the approved JSON in a public GitHub repository unless authorized. No licensed inventory exchanges or LCIA results are included.

**Important:** This is a discovery heuristic, not an automatic inventory audit. If the script returns few or no providers, inspect activity naming conventions or target-voltage reference-flow differences. The extractor does not parse the `.zolca` archive directly; it reads the restored database through openLCA IPC.

## B. Make the catalog available to the web app

Two options:

- **Private test:** Open the app, choose **2 · Select providers**, and upload the approved `provider_library_REVIEW.json` file. Only the active browser session uses that selection.
- **Instructor-managed deployment:** In Streamlit Community Cloud → app settings → Secrets, paste the *complete reviewed JSON* as a TOML multiline string:
  ```toml
  provider_library_json = '''
  { "catalog_version": 2, "...": "paste the complete reviewed catalog here" }
  '''
  ```
  The snippet above is illustrative, not a valid catalog. The deployed app must also be checked for institutional and ecoinvent licensing requirements before permitting access to that metadata.

The old `provider_catalog_json` secret is still supported as a **legacy v0.2 fallback**, but it provides only one predetermined provider for each technology rather than a searchable library.

## C. Student workflow

1. Open Streamlit, select a hypothetical, Northwest or custom scenario in **1 · Build supply mix**, and check its year, data boundary and electricity shares. The Northwest example is **client-proposed generation data**, not a verified consumption-based regional CI.
2. In **2 · Select providers**, choose one approved high-voltage electricity generation provider for each active technology. Filter by geography or search provider activity names. Different technologies may require different providers. No CI inputs are needed.
3. In **3 · Export to openLCA**, confirm that all active technologies have a provider and download the **openLCA JSON-LD ZIP**. Only use the matching background database. The ZIP includes a new foreground process and UUID links, not any ecoinvent inventories.
4. Open the same shared `.zolca` in openLCA 2. Import the JSON-LD ZIP, avoiding overwriting existing processes. Locate the generated custom HV electricity process. Inspect input flows and **default providers**, run linking checks and create a small test product system. Verify that openLCA can calculate a plausible inventory and LCIA result.
5. Use the custom high-voltage process in a project as a sensitivity scenario, retaining the original provincial grid as the baseline. Do **not** directly substitute a high-voltage supply process for medium- or low-voltage electricity without modeling transformation/distribution.
6. Export the methodology statement from the app's **5 · Scenario ZIP** tab and document the chosen providers, year, generation/consumption boundary, imports and uncertainties.

## D. Important limitations

- No actual `.zolca` or IPC connection was available during this development. **A live import, provider-link and LCIA pilot remains mandatory** before requiring students to use the exporter.
- Only high-voltage electricity is supported. The process does not model network infrastructure, medium-/low-voltage transformation or dynamic grid flows. Simple loss scaling does not replace these details.
- Provider metadata are matched against your specific database's UUIDs. Other ecoinvent versions, system models or conversions might not match.
- The provider library records discovery results but does not guarantee completeness or technology matching; instructors must approve every advertised option.
- A generation-based scenario such as IESO Northwest 2025 is not necessarily representative of site electricity consumption.
- No licensed LCI datasets, cumulative LCIA factors or inventory records are supplied with the application.

## E. Tests (local)

Run:

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py grid_core.py openlca_jsonld.py provider_library.py extract_provider_library.py
```

The offline tests cover selection rules and generated JSON-LD structure, but not the final openLCA import. A separate pilot using the actual shared class database is required.

Documentation: [openLCA IPC get descriptors](https://greendelta.github.io/openLCA-ApiDoc/data/get_descriptors.html), [openLCA IPC get by id](https://greendelta.github.io/openLCA-ApiDoc/data/get_by_id.html), [openLCA JSON-LD schema](https://greendelta.github.io/olca-schema/).
