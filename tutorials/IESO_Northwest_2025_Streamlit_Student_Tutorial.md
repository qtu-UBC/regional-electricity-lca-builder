# Student tutorial: IESO Northwest 2025 generation-mix scenario

**Regional Electricity LCA Builder v0.4 · LCA Clinic · 20 November 2026**

**Important:** This is a **client-proposed estimate of 2025 electricity generated within the Northwest region**. It has **not been independently verified**, and it is **not** an official IESO consumption-based carbon intensity. Local generation can differ from electricity delivered to a facility because of imports, exports, interzonal exchanges and losses.

## 1. Learning objectives

- Enter a documented alternative electricity generation mix into the Streamlit app.
- Recognize why a generation mix is not yet a life-cycle carbon intensity (CI).
- Conduct a GWP sensitivity analysis only when compatible life-cycle factors are available.
- Export assumptions for a reproducible student report; optionally export an openLCA foreground process if your instructor has validated the provider catalog.

## 2. Proposed 2025 data

| Source (as provided) | Output (GWh) | Stated share | Calculated exact share |
|---|---:|---:|---:|
| Hydroelectric | 3,132.8 | 86.8% | 86.8293% |
| Wind | 289.7 | 8.0% | 8.0294% |
| Biofuel | 185.5 | 5.1% | 5.1414% |
| Natural gas | 0.0 | 0.0% | 0.0000% |
| **Total** | **3,608.0** | **99.9% (rounded)** | **100.0000%** |

The displayed shares total 99.9% due to one-decimal rounding. The accompanying CSV computes each share as **generation output ÷ 3,608 GWh**. The app requires fractions (0–1), not percentages (0–100).

The app calls the **biofuel** technology `biomass`. This is an entry category, **not** a verified match to any particular ecoinvent bioelectricity technology. Fuel, combustion technology, and biogenic-carbon accounting must be checked before full LCA modeling.

## 3. Tab 1 — Build supply mix

1. Open your class Streamlit link and select **1 · Build supply mix**. Under **Start with a scenario**, select **IESO Northwest — 2025 proposed generation mix**. The generation shares and metadata load automatically.
2. Enter **Region / scenario label:** `IESO Northwest — 2025 client-proposed generation scenario`.
3. Set **Reference year:** `2025`.
4. For **What do the shares represent?**, select **generation**, *not consumption*.
5. For **Evidence / review status**, select **user_supplied_unverified** until an instructor checks the original source and method.
6. Set **Electricity delivery level** to **high** for the optional high-voltage openLCA demonstration only. Confirm the correct voltage for any actual project.
7. Leave **Losses to delivered kWh** at **0.0%** for this exercise; it means losses are *not modeled*, not that real losses are zero.
8. Leave **Primary public data source URL** blank if no public URL is available. Document the client-provided assumption in your report. Do not invent a URL.
9. Verify that the preloaded rows show `hydro`, `wind`, `biomass`, and `natural_gas`. You may optionally upload the provided CSV instead; do not upload it in addition to the preset, since it already contains the same shares.
10. Confirm **Share sum = 1.0000** and **Validation errors = 0**. Review the expected warnings about generation-versus-consumption and data provenance.

**Expected outcome:** **Computed life-cycle CI = Not available**. This is correct because the dataset supplies generation shares but *not* technology-specific life-cycle intensities. Do not interpret a missing CI as zero emissions.

## 4. Tab 4 — Optional GWP screening

To quantify a change in the **whole product LCA**, students need their baseline project GWP, electricity demand per functional unit, and compatible original and alternative **life-cycle** electricity carbon intensities.

**Method:**

`Updated product GWP (kg CO₂e/FU) = Baseline GWP + Electricity use (kWh/FU) × [Alternative LC CI − Original LC CI] (g CO₂e/kWh) ÷ 1000`

If instructors supply compatible technology-specific life-cycle factors, the alternative scenario CI can first be estimated as:

`Scenario LC CI = (0.86829268 × CI_hydro + 0.08029379 × CI_wind + 0.05141353 × CI_biomass) / (1 − loss_fraction)`.

**Purely hypothetical calculation check — NOT a Northwest estimate:** Suppose hydro = 20, wind = 15, and biomass = 200 g CO₂e/kWh (all invented for practice), with losses excluded. The computed scenario CI would be **28.85 g CO₂e/kWh**. If a made-up product baseline has 1,000 kg CO₂e/FU, 1,000 kWh/FU, and an original grid CI of 100 g CO₂e/kWh, the alternative product GWP would be **928.85 kg CO₂e/FU**, or **-7.11%**. Do not report these figures as case-study results.

If no compatible life-cycle factors are available, **do not calculate a numeric result from the generation shares alone**. The app's **Direct/operational CI only** option is an approximate screening correction, and is especially limited when the technology mix changes. It is not equivalent to a regional LCI.

## 5. Tab 5 — Save the scenario

1. Open **5 · Scenario ZIP**.
2. Click **Download scenario ZIP** to save the inputs, mix.csv, methodology report and (if run) sensitivity result.
3. Keep the original Ontario provincial ecoinvent result as the **baseline**. Label the new Northwest scenario as **client-proposed generation-based sensitivity**.
4. Include the share calculations, provenance, and warning statements in the report.

The Scenario ZIP is for **documentation** and cannot be directly imported into openLCA.

## 6. Tabs 2 and 3 — Select generation providers and export to openLCA

This path requires the instructor to extract and approve a searchable electricity-provider library from the **same restored ecoinvent 3.12 cut-off .zolca** students will use. The cloud app never includes licensed ecoinvent inventories.

1. Confirm your instructor has made a provider library available, either via deployment settings or a session-uploaded approved JSON. No per-student UUID lookup should be necessary.
2. Open **2 · Select providers**. Section A lists existing electricity markets for baseline reference; **do not** select an existing market as a generation technology. In section B, choose an **instructor-approved** high-voltage generation provider for hydro, wind and biomass. Options are ranked geographically, placing Ontario candidates first for this example. No provider is needed for 0% natural gas.
3. Verify the actual hydro technology (reservoir/run-of-river) and bioenergy fuel (biogas/wood). Cogeneration is offered with a warning about heat/electricity co-production. Industrial co-products, pumped storage and ambiguous processes are hidden unless the advanced option is intentionally enabled. Geography alone does not guarantee representativeness; **write a short selection rationale for each provider**. If no suitable provider is available, ask the instructor rather than choose a mismatched dataset.
4. Open **3 · Export to openLCA**. Confirm all active technologies have providers **and rationales** and no compatibility errors appear, then download the **openLCA JSON-LD ZIP**. The rationale is preserved in the process's input exchange metadata.
5. Import that ZIP into your locally restored copy of the **same class .zolca**. Avoid overwriting existing datasets. Inspect the new foreground process and its default providers, run linking checks, create a test product system and verify openLCA can calculate plausible LCI/LCIA results.
6. Only after instructor validation, use the custom high-voltage process in a compatible product system and compare with the original Ontario provincial-grid baseline.

**Critical limitations:** This is still only a client-proposed **generation-based** electricity scenario. It does not automatically incorporate grid imports, interzonal transfers, T&D infrastructure, or medium-/low-voltage conversion. Import success alone is not proof of a representative regional electricity LCA. The results are calculated inside openLCA, not by the Streamlit app.

## 7. What to submit

- Original Ontario provincial-grid GWP result, functional unit, and background dataset name.
- 2025 Northwest generation-mix table and source/provenance description.
- Streamlit scenario ZIP and methodology report.
- Updated GWP only if defensible *life-cycle* factors or a locally validated openLCA model are available.
- Short discussion: (a) generation vs consumption mix; (b) assumptions about biomass and imports; (c) effect on product GWP and its uncertainty.

## Instructor note

The supplied data are suitable for a **classroom sensitivity scenario**. Instructor preparation for v0.4 is described in [the repository setup guide](../docs/SETUP_v0.4.md). They are not sufficient, on their own, to assert that the electricity delivered to the site is 86.8% hydropower or to claim a particular regional carbon intensity. Seek the source/methodology from the client before presenting this as a measured Northwest electricity mix.
