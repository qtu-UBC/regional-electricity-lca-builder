# Student lab — Northwest Ontario electricity LCA (medium voltage)

**Regional Electricity LCA Builder · Classroom-ready MV pilot · Updated 23 November 2026**

> **Scope:** This is a **client-proposed 2025 *generation* scenario**, not a verified Northwest Ontario *consumption* mix or an official grid emission factor. The Ontario-wide electricity network is retained as a proxy. The biofuel technology, electricity imports/exports, and connection voltage of an actual facility remain unverified.

**Recommended lab mode: instructor-prepared ZIPs.** Students use the **student app** for scenario exploration and provider-choice reasoning **consistent with the supplied ZIP**, then **openLCA** for inventory inspection and LCIA. Students do **not** start the instructor-review app, run IPC extraction, edit approval flags, or upload licensed MV exchange data to a public cloud. An optional advanced mode at the end explains how to export a custom package on an authorized workstation.

## Before class — what you will receive

| File / resource | Where it comes from | What to do |
|---|---|---|
| Student-facing Regional Electricity LCA Builder | Instructor-provided URL or local \`streamlit run app.py\` | Use Tabs 1–2 for reasoning and documentation |
| \`provider_library_APPROVED_LOCAL.json\` | Instructor, **only if licensing permits classroom access** | Use in Tab 2 if not already configured; metadata only |
| \`electricity_MV_CUSTOM_openLCA.zip\` | Instructor, generated after source review and baseline replication | **Import into openLCA**; four foreground processes |
| Licensed ecoinvent 3.12 **cut-off** openLCA database | Instructor / institutional access | The background database must match the class ZIP |
| Original \`market for electricity, medium voltage\` (Canada, Ontario) | Already in openLCA | Comparison baseline |
| Assignment template / results table | Instructor | Record decisions, LCIA, and caveats |

**Do not upload** the .zolca, instructor's \`mv_adapter_*LOCAL.json\`, or other ecoinvent inventory exchanges to Streamlit Cloud, GitHub, or public course spaces. The **scenario documentation ZIP** is *not* an openLCA import file.

### Learning outcomes

After the lab, you should be able to (1) construct and criticize a regional generation scenario; (2) justify compatible electricity provider choices; (3) inspect a four-process HV→MV supply chain in openLCA; (4) calculate two LCIA categories using the same functional unit; and (5) explain why a local generation scenario cannot automatically be treated as a facility's consumed electricity.

## 1. Scenario input — Northwest Ontario, 2025

| Source as supplied | Generation (GWh) | Share used in scenario |
|---|---:|---:|
| Hydro | 3,132.8 | 86.8293% |
| Wind | 289.7 | 8.0294% |
| Biofuel (technology unconfirmed) | 185.5 | 5.1414% |
| Natural gas | 0.0 | 0.0000% |
| **Total** | **3,608.0** | **100.0000%** |

These shares are calculated from GWh rather than the rounded reported percentages. In the app, the biofuel share is called **biomass** for technology classification; **wood chips and biogas are different assumptions** and should not be presented as verified fuel choices.

### Tab 1 · Build supply mix — 10–15 min

1. Choose **Start with a scenario → IESO Northwest — 2025 proposed generation mix**.
2. Verify year **2025**, boundary **generation**, and evidence status **user_supplied_unverified**.
3. Set **Electricity delivery level → medium** for this classroom exercise. Leave **Losses to delivered kWh (%) — simplified scaling = 0**; the MV model includes transformation and market self-consumption, so manually scaling losses again would double-count them.
4. Inspect the loaded hydro/wind/biomass fractions. Do **not** add an external GHG intensity; openLCA calculates impacts.
5. Confirm **Share sum = 1.0000** and **Errors = 0**. The advisories still matter.
6. Record which input claims have not been independently established: generation versus consumption, actual biofuel feedstock, interregional flows, and actual facility connection voltage.

**Checkpoint:** An arithmetic-valid scenario is *not* a verified regional supply.

## 2. Choose and defend generation providers — 15–20 min

### Tab 2 · Select providers

If the approved provider library is already loaded, you can skip the upload. Otherwise, upload the instructor-provided **\`provider_library_APPROVED_LOCAL.json\`** where authorized.

**Section A — Existing regional markets** is **optional**. If using it for documentation, choose **Market voltage = medium**, search \`Ontario\`, and select the original \`market for electricity, medium voltage\`. This does **not** change the custom export and is **not** a generation provider.

In **Section B — Generation providers**, choose one Ontario high-voltage provider for each active technology and enter a short rationale:

| Scenario share | Classroom starting choice | Example selection rationale |
|---|---|---|
| Hydro — 86.83% | \`electricity production, hydro, run-of-river\` | Ontario run-of-river hydro is an illustrative generation proxy; reservoir hydro is a technology sensitivity. |
| Wind — 8.03% | \`electricity production, wind, >3MW turbine, onshore\` | Ontario onshore wind above 3 MW is an illustrative turbine-size assumption; the actual fleet is not confirmed. |
| Biomass — 5.14% | \`heat and power co-generation, wood chips, 6667 kW, state-of-the-art 2014\` | Ontario wood-chip CHP is a hypothetical bioenergy proxy; actual fuel and heat/electricity co-product treatment are unverified. |

The instructor may provide **reservoir hydro**, **1–3 MW wind**, and **biogas CHP** as alternatives for sensitivity analysis. Do not use pumped-storage hydro as ordinary primary hydro generation without explicit justification. The **biomass** warning in Tab 2 is expected.

**Checkpoint:** The counter reads **“Selected 3 of 3 active providers.”** No process is chosen automatically; the three rationale fields must be filled.

**Crucial:** If you use an **instructor-prepared** custom ZIP, check that its embedded process names match the options you just selected. Changing a dropdown **does not alter** an already-downloaded ZIP. For another provider combination you must use the instructor-provided matching ZIP or, under an authorized local advanced workflow, export a new one. Otherwise your different provider choice is a *discussion option only*, not the basis of the calculated results.

## 3. Import the prepared Northwest MV package — 25 min

**Standard classroom route:** Your instructor supplies the already validated **\`electricity_MV_CUSTOM_openLCA.zip\`**. You do **not** need to download a baseline replication ZIP or upload an MV adapter.

1. Open the authorized ecoinvent 3.12 cut-off database in **openLCA** (prefer a disposable **test copy** during the lab).
2. Right-click the database → **Import… → Other… → JSON package (*.zip)**. In some openLCA views this is described as JSON-LD.
3. Select \`electricity_MV_CUSTOM_openLCA.zip\` **without unzipping it**.
4. Choose **Never update a data set that already exists**. Complete the import.
5. Find and inspect the four new foreground processes:

| Process | Main relationship to verify |
|---|---|
| \`LCA Clinic CUSTOM HV electricity | IESO Northwest…\` | 1 kWh HV output; hydro 0.86829, wind 0.08029, biomass 0.05141 kWh; each has the intended generation provider |
| \`v0.9 custom HV market | Canada, Ontario\` | 1 kWh HV from the custom generation mix; 0.01784 kWh HV input linked back to itself; original network exchanges retained |
| \`v0.9 custom HV-to-MV | Canada, Ontario\` | Input **1.0048249 kWh HV** from custom HV market; output 1 kWh MV |
| \`v0.9 custom MV market | IESO Northwest…\` | 1.00000 kWh MV from custom transformer; **0.00239264 kWh** MV self-input; SF₆ and MV transmission infrastructure retained |

The custom model **reroutes the original Ontario direct municipal-waste MV supply via the HV transformation pathway**. This all-HV generation connection is an explicit assumption, not an observation about actual power-plant connections.

**Checkpoint:** All electricity default providers link to the intended **custom** processes; there are no missing supplier links. Check the process connections before calculating LCIA. Do not multiply input shares by a further transmission-loss factor.

## 4. Calculate and compare LCIA — 25–30 min

1. In openLCA, create a product system from the **original Ontario** \`market for electricity, medium voltage\`.
2. Create another product system from **\`v0.9 custom MV market | IESO Northwest…\`**. Use the stored default providers and inspect any unresolved links.
3. Set both to **1 kWh of medium-voltage electricity**.
4. Calculate both using the **same ReCiPe 2016 v1.03, midpoint (H)** method and impact category definitions.
5. Compare climate change, water use and land use; keep all other assumptions constant.
6. Expand **Contribution analysis** for climate change and **Land use**. Distinguish parent-process totals from nested contributors; **do not add a parent and its child contributions**.

### Instructor pilot results — reference, not values to copy blindly

| Category (per 1 kWh MV) | Original Ontario MV | Example Northwest MV | Observation |
|---|---:|---:|---|
| Climate change (kg CO₂-eq) | 0.12681 | 0.01763 | ~86.1% lower in the illustrative scenario |
| Water use (m³) | 0.02685 | 0.00015 | Strongly affected by generation technology assumptions |
| Land use (m²·a crop-eq) | 0.00214 | 0.02904 | Larger in the illustrative scenario |

These are **rounded results from an instructor's openLCA pilot**, not required numerical targets or official emissions factors. If your values differ, first verify the **same database, functional unit, LCIA method, imported package and provider links**; then investigate genuine model differences. You must calculate your own results.

**Interpretation:** Electricity *generation shares* are not proportional to their shares of LCIA impacts. Infrastructure, direct SF₆ and other market emissions, and bioenergy supply chains also contribute. Land-use or water-use trade-offs may reflect particular technology proxies; investigate the contribution tree before attributing causality.

## 5. Submit the lab record — 15 min / after class

Submit a short report (approximately 2 pages) with your scenario table and provenance caveat, the three provider names and rationales, a screenshot of the custom MV market input links, a baseline-versus-Northwest LCIA table for at least **climate change plus one other category**, one contribution-analysis screenshot, and a discussion of what would need to be confirmed before applying the result to an actual SAF facility. Include the scenario documentation ZIP or methodology report from **Tab 3 → Scenario documentation** if requested by your instructor. This ZIP records assumptions and **cannot** be imported into openLCA.

### Discussion prompts

- Why does 86.83% hydro generation not imply 86.83% of climate-change impacts?
- How would switching to reservoir hydro or biogas CHP affect results, and what data would justify the choice?
- What distinguishes a **generation** scenario from a **facility electricity-consumption** inventory?
- Why can an electricity supply scenario improve GWP while worsening another category?
- Which results are supported by model validation, and which remain uncertain regional assumptions?

## Advanced extension: students build their own custom MV ZIP

Only if your instructor confirms the **license and local-computer requirements**, use a local instance of \`streamlit run app.py\` on an authorized machine with the instructor's approved provider metadata and validated MV adapter. Complete Tabs **1 → 2 → 3**, upload \`provider_library_APPROVED_LOCAL.json\` in Tab 2, select providers and explanations, then upload \`mv_adapter_REPLICATION_VALIDATED_LOCAL.json\` in Tab 3 to download **\`electricity_MV_CUSTOM_openLCA.zip\`**. You **do not** need to redo baseline replication. Import and calculate as above. Do not upload the MV adapter to a public Streamlit deployment without license authorization.

Instructor-only operations—local openLCA IPC extraction, provider approval, baseline cloning and recording original-versus-replicated LCIA evidence—are documented separately in [the instructor runbook](../docs/INSTRUCTOR_CLASSROOM_RUNBOOK.md). **Never invent review signatures, substitute an unrelated provider, or treat a completed import as independent scientific verification.**
