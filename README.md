# Regional Electricity LCA Builder — v0.7

A student-friendly Streamlit tool for constructing a documented **regional electricity supply scenario** and exporting a **custom high-voltage foreground unit process** for openLCA 2. The current exporter targets **ecoinvent 3.12 cut-off**, using an instructor-approved provider library extracted from the class's shared `.zolca`.

## What problem does this solve?

An LCI database may lack a current, representative electricity supply mix for the region being studied. Students can supply their own documented technology shares and connect each share to a compatible generation process from a licensed background database. The builder exports a foreground electricity process; **openLCA, not Streamlit, calculates LCI and LCIA impacts**.

**Caution:** The tool does not supply ecoinvent inventory data, retrieve electricity statistics, verify a local generation mix against consumption, or certify results.

## Four-tab student workflow

1. **Build supply mix:** Choose the hypothetical example, the client-proposed IESO Northwest 2025 generation example, or a custom scenario. Edit technology shares and sources; review arithmetic validation and provenance advisories. No emission factors or GWP calculations are required.
2. **Select providers:** Use the instructor-reviewed library extracted from the *same* ecoinvent 3.12 cut-off `.zolca` students use. Existing electricity markets can be browsed for the **baseline**; choose actual generation processes for the **custom mix**. Geographies are ranked as search preferences, not automatic claims of suitability. Confirm CHP technology, unusual industrial co-products and storage assumptions. Write a short provider-selection rationale.
3. **Export to openLCA:** Once an approved library and all required provider choices are present, download the linked **openLCA JSON-LD ZIP** containing one foreground high-voltage unit process. On the *same tab*, download a **scenario documentation ZIP** and a **methodology report**, even before an instructor library is available (as long as the scenario passes arithmetic checks). The documentation ZIP is **not importable** into openLCA.
4. **Guide & cautions:** Review class workflow, limitations and the Northwest worked tutorial.

### openLCA import and calculation

In openLCA 2, restore the matching licensed class `.zolca`; choose **Import → Linked Data (JSON-LD)** and the exported process ZIP. Avoid overwriting pre-existing ecoinvent datasets. Inspect the new process's quantitative-reference electricity output, technology-specific input exchanges, and **default providers**. Verify provider links, create a test product system and run LCI/LCIA. Only then replace a compatible **high-voltage** supply input in the project product system and compare with the original baseline.

The current exporter does **not** reconstruct medium/low-voltage transformation, grid infrastructure, interzonal transfers or imports. Generation mix and electricity consumed at a facility are not automatically the same. The simple loss-scaling option does not replace proper transmission/distribution modeling. An exported ZIP alone does not prove scientific representativeness or functioning provider links.

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

The catalog's UUIDs are tied to the particular converted openLCA database. Different versions, system models or conversions may not use the same identifiers. The public Streamlit app never connects to the instructor's IPC server.

## Repository contents

| File | Role |
|---|---|
| `app.py` | Four-tab Streamlit UI and two distinct export types |
| `grid_core.py` | Scenario validation and documentation; legacy carbon-factor helpers are retained internally but not shown in the student UI |
| `provider_library.py` | Instructor approval guards, region ranking, generator classification and explicit provider selections |
| `extract_provider_library.py` | Read-only IPC discovery of reference-electricity suppliers from restored local `.zolca` |
| `openlca_jsonld.py` | Native openLCA JSON-LD foreground process ZIP |
| `instructor_catalog.py`, `openlca_bridge.py` | Legacy instructor-only approaches, not needed in the main student workflow |
| `tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md` | Current worked student tutorial |
| `data/` | Illustrative mixes and templates; no licensed LCI |
| `tests/` | Python validation, exporter checks and Streamlit startup smoke test |

**Current student materials (v0.7):** The [Word Northwest tutorial](tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.docx), [Markdown tutorial](tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md), and [Excel scenario workbook](Electricity_Scenario_Student_Template.xlsx) all follow the four-tab openLCA unit-process workflow. The workbook includes a formula-checked Northwest example, an editable supply mix, a provider-selection log, an import checklist and source notes. No GWP-screening exercises are included.

## Deployment and testing

Deploy `app.py` with `requirements.txt` on Streamlit Community Cloud. The cloud does not require `olca-ipc`, `olca-schema` or a licensed database. A matching openLCA 2 installation and the licensed class `.zolca` are required to calculate the full impacts after import.

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py grid_core.py openlca_jsonld.py provider_library.py extract_provider_library.py
```

GitHub Actions runs these checks on pushes. They **do not replace** a live JSON-LD import/link/LCIA pilot against the actual licensed database.

## References

- [openLCA 2 schema and JSON-LD format](https://greendelta.github.io/olca-schema/)
- [openLCA manual: importing databases](https://greendelta.github.io/openLCA2-manual/databases/importing_and_combining_databases.html)
- [ecoinvent 3.12 in openLCA](https://www.openlca.org/ecoinvent-3-12-available-for-openlca/)
- [IESO power data directory](https://www.ieso.ca/en/Power-Data/Data-Directory)
