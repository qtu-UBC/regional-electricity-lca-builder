# Regional Electricity LCA Builder — v1.0 instructor workflow (MV pilot)

A student-friendly Streamlit tool for constructing a documented **regional electricity supply scenario** and exporting **custom high-voltage or region-adapted medium-voltage foreground processes** for openLCA 2. The exporter targets **ecoinvent 3.12 cut-off** and instructor-reviewed references from the same restored class `.zolca`. **MV export is a pilot requiring local source-database extraction and openLCA replication validation**.

## What problem does this solve?

An LCI database may lack a current, representative electricity supply mix for the region being studied. Students can supply their own documented technology shares and connect each share to a compatible generation process from a licensed background database. The builder exports a foreground electricity process; **openLCA, not Streamlit, calculates LCI and LCIA impacts**.

**Caution:** The tool does not supply ecoinvent inventory data, retrieve electricity statistics, verify a local generation mix against consumption, or certify results.

## Four-tab student workflow

1. **Build supply mix:** Choose the hypothetical example, the client-proposed IESO Northwest 2025 generation example, or a custom scenario. Edit technology shares and sources; review arithmetic validation and provenance advisories. No emission factors or GWP calculations are required.
2. **Select providers:** Use the instructor-reviewed library extracted from the *same* ecoinvent 3.12 cut-off `.zolca` students use. Existing electricity markets can be browsed for the **baseline**; choose actual generation processes for the **custom mix**. Geographies are ranked as search preferences, not automatic claims of suitability. Confirm CHP technology, unusual industrial co-products and storage assumptions. Write a short provider-selection rationale.
3. **Export to openLCA:** For HV, download one foreground high-voltage generation process. For MV, **first** upload an extracted local adapter and download the three-process baseline replication ZIP **without a generation-provider catalog or scientific approval**. Record instructor source review and two-category openLCA LCIA comparison. Only then can a four-process custom MV ZIP be unlocked with approved generation providers. The independent scenario documentation ZIP and methodology report remain available without a provider library when arithmetic checks pass; documentation ZIPs are **not importable**.
4. **Guide & cautions:** Review class workflow, limitations and the Northwest worked tutorial.

### openLCA import and calculation

In openLCA 2, restore the matching licensed class `.zolca`; choose **Import → Linked Data (JSON-LD)** and the exported process ZIP. Avoid overwriting pre-existing ecoinvent datasets. Inspect the new process's quantitative-reference electricity output, technology-specific input exchanges, and **default providers**. Verify provider links, create a test product system and run LCI/LCIA. Only then replace a compatible **high- or medium-voltage** supply input in the project product system and compare with the original baseline.

**MV v0.9:** Supports an instructor-reviewed three-process topology (regional HV market → HV-to-MV transformation → regional MV market) by copying original region-specific coefficients, network exchanges and self-consumption from a local, licensed source. All user-specified generation is modeled through the HV pathway; direct MV generation from the original market is replaced rather than retained. The three-process replication can be exported immediately from structurally valid extracted source data. Custom export is gated on instructor review, recorded numeric agreement for GWP and another impact category, matching source fingerprint, and approved generation providers. Replication evidence is instructor-entered, not independently computed by the cloud app. **Low-voltage supply, real power flows, actual regional import/export balances and general multi-voltage topologies remain unsupported.**

## Instructor preparation (local)

**[Instructor setup and catalog-review guide](docs/SETUP_v0.4.md)** (the filename is retained for backwards-compatible links; the content describes the latest workflow).

1. Restore the **same ecoinvent 3.12 cut-off `.zolca`** that is distributed to students and open it in openLCA.
2. Start **Tools → Developer Tools → IPC Server** (typically port 8080).
3. On your computer, install `requirements_instructor.txt` and run:

   ```bash
   mkdir -p local
   python -m instructor.extract_provider_library \
     --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
     --reviewer "Course instructor" \
     --out local/provider_library_REVIEW.json
   ```

4. Run the **local instructor review UI**: `streamlit run instructor/review_app.py`. Upload `local/provider_library_REVIEW.json`, filter by geography/technology, explicitly select candidate generators and record a reason for each. Optional baseline markets can be reviewed separately. Download `provider_library_APPROVED_LOCAL.json` to `local/`. **Nothing is auto-approved.**
5. Subject to institutional and ecoinvent license terms, upload the locally approved JSON as a **session JSON** in Tab 2 or configure the private `provider_library_json` Streamlit secret. Never upload your `.zolca` or licensed inventory exchanges to a public repository.
6. Pilot an exported JSON-LD ZIP against the restored class database, check provider UUID links and calculate a test product system before teaching with it.
7. For **medium voltage**, follow the [v0.9 MV instructor pilot guide](docs/MEDIUM_VOLTAGE_v0.9.md): extract a **local** source adapter, export baseline replication without a generator library, review its source links, compare original and replicated MV LCIA results, save the resulting local validation record, and only then configure custom generation providers.

The catalog's UUIDs are tied to the particular converted openLCA database. Different versions, system models or conversions may not use the same identifiers. The public Streamlit app never connects to the instructor's IPC server.

**Licensing:** An MV adapter contains process exchange amounts and may be licensed ecoinvent LCI. Keep the adapter and licensed database on the local instructor workstation by default, do not commit adapter JSON to this repository, and do not upload it to public Streamlit without verified redistribution permissions. The optional upload field is intended for licensed/local deployments. Synthetic tests and public code contain no source-database exchanges.

## Repository layout

The entry point remains `streamlit run app.py`. Core app modules stay at the
root so existing imports, test scripts and Streamlit Cloud deployment keep working.

| Path | Purpose |
|---|---|
| `app.py` | Student-facing four-tab Streamlit entry point |
| `grid_core.py`, `provider_library.py`, `openlca_jsonld.py`, `mv_market.py` | Active domain logic and openLCA exporters |
| `instructor/extract_provider_library.py` | Local IPC generator and market metadata extraction |
| `instructor/extract_mv_adapter.py` | Local IPC HV/MV source adapter extraction |
| `instructor/review_app.py` | **Reusable, local-only** instructor provider review UI |
| `instructor/review_providers.py` | Reusable approval validation and optional CLI |
| `tutorials/` | Classroom tutorials and scenario workbook |
| `docs/` | Instructor setup, review workflow and MV pilot documentation |
| `data/` | Public illustrative scenario and input templates |
| `tests/` | Synthetic test fixtures and regression checks |
| `archive/legacy/` | Historical standalone bridge and old catalog builder (not student workflow) |
| `local/` | **Ignored private workspace** for review JSON, validated adapters and exported ZIPs; create locally with `mkdir -p local` |

The root-level `extract_provider_library.py` and `extract_mv_adapter.py` are
compatibility launchers for earlier tutorials. New commands use
`python -m instructor.extract_provider_library` and
`python -m instructor.extract_mv_adapter`.

**For your existing workstation files:** move locally extracted
`provider_library_REVIEW.json`, `mv_adapter_REVIEW_LOCAL.json`,
`mv_adapter_REPLICATION_VALIDATED_LOCAL.json` and the approved provider
library to `local/` (without placing those data in Git). You do not need to
re-extract any datasets.

**Current student tutorial:** [Northwest exercise (Markdown)](tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md);
[Word edition](tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.docx);
[scenario workbook](tutorials/Electricity_Scenario_Student_Template.xlsx).
The tutorial and workbook are HV-oriented; the [MV pilot instructor guide](docs/MEDIUM_VOLTAGE_v0.9.md)
governs the added v0.9 MV replication procedure.

### Local instructor provider review

Run on your authorized local workstation:

```bash
mkdir -p local
python -m instructor.extract_provider_library \
  --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
  --reviewer "Course instructor" \
  --out local/provider_library_REVIEW.json
streamlit run instructor/review_app.py
```

Upload the review JSON to the **local instructor UI**, filter by region and
technology, mark only suitable generation processes, enter a specific written
review reason for each and acknowledge the review scope. Download the approved
JSON to `local/` and use it in student Tab 2. The interface works with any
supported ecoinvent geography from the extracted library; it is **not** a
Northwest-specific auto-approval script. You can also use
`python -m instructor.review_providers --help` for an explicit selection-file
CLI workflow. Do not publicly host the instructor UI or license-restricted
provider metadata by default.

## Deployment and testing

Deploy `app.py` with `requirements.txt` on Streamlit Community Cloud. The cloud does not require `olca-ipc`, `olca-schema` or a licensed database. A matching openLCA 2 installation and licensed class `.zolca` are required to calculate impacts after import. The local MV adapter passes through stages **extracted → reviewed_for_testing → replication_validated**; the last is a recorded instructor comparison, not independent scientific verification.

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py grid_core.py openlca_jsonld.py provider_library.py mv_market.py instructor/review_providers.py instructor/review_app.py instructor/extract_provider_library.py instructor/extract_mv_adapter.py
```

GitHub Actions runs these checks on pushes. They **do not replace** a live JSON-LD import/link/LCIA pilot against the actual licensed database.

## References

- [openLCA 2 schema and JSON-LD format](https://greendelta.github.io/olca-schema/)
- [openLCA manual: importing databases](https://greendelta.github.io/openLCA2-manual/databases/importing_and_combining_databases.html)
- [ecoinvent 3.12 in openLCA](https://www.openlca.org/ecoinvent-3-12-available-for-openlca/)
- [IESO power data directory](https://www.ieso.ca/en/Power-Data/Data-Directory)
