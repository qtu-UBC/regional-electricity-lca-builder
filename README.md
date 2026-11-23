# Regional Electricity LCA Builder — v0.9 (MV pilot)

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
   python extract_provider_library.py \
     --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
     --reviewer "Course instructor" \
     --out provider_library_REVIEW.json
   ```

4. Review the candidate `entries` (generation providers) and `markets` (baseline markets). Verify technology, location, reference electricity flow, voltage and CHP/coproduction treatment. **All entries start unapproved.** Mark only defensible candidates `"approved": true`, then approve the library as a whole.
5. Subject to institutional and ecoinvent license terms, upload approved metadata as a **session JSON** in Tab 2 or configure the private `provider_library_json` Streamlit secret. Never upload your `.zolca` or licensed inventory exchanges to a public repository.
6. Pilot an exported JSON-LD ZIP against the restored class database, check provider UUID links and calculate a test product system before teaching with it.
7. For **medium voltage**, follow the [v0.9 MV instructor pilot guide](docs/MEDIUM_VOLTAGE_v0.9.md): extract a **local** source adapter, export baseline replication without a generator library, review its source links, compare original and replicated MV LCIA results, save the resulting local validation record, and only then configure custom generation providers.

The catalog's UUIDs are tied to the particular converted openLCA database. Different versions, system models or conversions may not use the same identifiers. The public Streamlit app never connects to the instructor's IPC server.

**Licensing:** An MV adapter contains process exchange amounts and may be licensed ecoinvent LCI. Keep the adapter and licensed database on the local instructor workstation by default, do not commit adapter JSON to this repository, and do not upload it to public Streamlit without verified redistribution permissions. The optional upload field is intended for licensed/local deployments. Synthetic tests and public code contain no source-database exchanges.

## Repository contents

| File | Role |
|---|---|
| `app.py` | Four-tab Streamlit UI and two distinct export types |
| `grid_core.py` | Scenario-share validation, CSV parsing, methodology reports and documentation exports; obsolete carbon-factor calculations have been removed |
| `provider_library.py` | Instructor approval guards, region ranking, generator classification and explicit provider selections |
| `extract_provider_library.py` | Read-only IPC discovery of reference-electricity suppliers from restored local `.zolca` |
| `openlca_jsonld.py` | Native openLCA JSON-LD HV foreground process ZIP |
| `extract_mv_adapter.py` | Local read-only extraction of three regional HV/MV processes, unapproved by default |
| `mv_market.py` | Guarded regional MV topology, baseline replication, adapted MV JSON-LD exporter |
| `docs/MEDIUM_VOLTAGE_v0.9.md` | MV instructor review, local extraction, license and LCIA validation workflow |
| `instructor_catalog.py`, `openlca_bridge.py` | Legacy instructor-only approaches, not needed in the main student workflow |
| `tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md` | Current worked student tutorial |
| `data/` | Illustrative mixes and templates; no licensed LCI |
| `tests/` | Python validation, exporter checks and Streamlit startup smoke test |

**Existing HV student materials (v0.8-compatible):** The [Word Northwest tutorial](tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.docx), [Markdown tutorial](tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md), and [Excel scenario workbook](Electricity_Scenario_Student_Template.xlsx) all follow the four-tab openLCA unit-process workflow. The workbook includes a formula-checked Northwest example, an editable supply mix, a provider-selection log, an import checklist and source notes. No GWP-screening exercises are included.

## Deployment and testing

Deploy `app.py` with `requirements.txt` on Streamlit Community Cloud. The cloud does not require `olca-ipc`, `olca-schema` or a licensed database. A matching openLCA 2 installation and licensed class `.zolca` are required to calculate impacts after import. The local MV adapter passes through stages **extracted → reviewed_for_testing → replication_validated**; the last is a recorded instructor comparison, not independent scientific verification.

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py grid_core.py openlca_jsonld.py provider_library.py extract_provider_library.py mv_market.py extract_mv_adapter.py
```

GitHub Actions runs these checks on pushes. They **do not replace** a live JSON-LD import/link/LCIA pilot against the actual licensed database.

## References

- [openLCA 2 schema and JSON-LD format](https://greendelta.github.io/olca-schema/)
- [openLCA manual: importing databases](https://greendelta.github.io/openLCA2-manual/databases/importing_and_combining_databases.html)
- [ecoinvent 3.12 in openLCA](https://www.openlca.org/ecoinvent-3-12-available-for-openlca/)
- [IESO power data directory](https://www.ieso.ca/en/Power-Data/Data-Directory)
