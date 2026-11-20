# Student tutorial: IESO Northwest 2025 generation-mix scenario

**Regional Electricity LCA Builder v0.2 · LCA Clinic · 17 November 2026**

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

1. Open your class Streamlit link and select **1 · Build supply mix**.
2. Enter **Region / scenario label:** `IESO Northwest — 2025 client-proposed generation scenario`.
3. Set **Reference year:** `2025`.
4. For **What do the shares represent?**, select **generation**, *not consumption*.
5. For **Evidence / review status**, select **user_supplied_unverified** until an instructor checks the original source and method.
6. Set **Electricity delivery level** to **high** for the optional high-voltage openLCA demonstration only. Confirm the correct voltage for any actual project.
7. Leave **Losses to delivered kWh** at **0.0%** for this exercise; it means losses are *not modeled*, not that real losses are zero.
8. Leave **Primary public data source URL** blank if no public URL is available. Document the client-provided assumption in your report. Do not invent a URL.
9. Click **Optional: upload a mix CSV** and select `IESO_Northwest_2025_Generation_Scenario.csv`. The rows should show `hydro`, `wind`, `biomass`, `natural_gas`.
10. Confirm **Share sum = 1.0000** and **Validation errors = 0**. Review the expected warnings about generation-versus-consumption and data provenance.

**Expected outcome:** **Computed life-cycle CI = Not available**. This is correct because the dataset supplies generation shares but *not* technology-specific life-cycle intensities. Do not interpret a missing CI as zero emissions.

## 4. Tab 2 — GWP sensitivity

To quantify a change in the **whole product LCA**, students need their baseline project GWP, electricity demand per functional unit, and compatible original and alternative **life-cycle** electricity carbon intensities.

**Method:**

`Updated product GWP (kg CO₂e/FU) = Baseline GWP + Electricity use (kWh/FU) × [Alternative LC CI − Original LC CI] (g CO₂e/kWh) ÷ 1000`

If instructors supply compatible technology-specific life-cycle factors, the alternative scenario CI can first be estimated as:

`Scenario LC CI = (0.86829268 × CI_hydro + 0.08029379 × CI_wind + 0.05141353 × CI_biomass) / (1 − loss_fraction)`.

**Purely hypothetical calculation check — NOT a Northwest estimate:** Suppose hydro = 20, wind = 15, and biomass = 200 g CO₂e/kWh (all invented for practice), with losses excluded. The computed scenario CI would be **28.85 g CO₂e/kWh**. If a made-up product baseline has 1,000 kg CO₂e/FU, 1,000 kWh/FU, and an original grid CI of 100 g CO₂e/kWh, the alternative product GWP would be **928.85 kg CO₂e/FU**, or **-7.11%**. Do not report these figures as case-study results.

If no compatible life-cycle factors are available, **do not calculate a numeric result from the generation shares alone**. The app's **Direct/operational CI only** option is an approximate screening correction, and is especially limited when the technology mix changes. It is not equivalent to a regional LCI.

## 5. Tab 3 — Save the scenario

1. Open **3 · Scenario ZIP**.
2. Click **Download scenario ZIP** to save the inputs, mix.csv, methodology report and (if run) sensitivity result.
3. Keep the original Ontario provincial ecoinvent result as the **baseline**. Label the new Northwest scenario as **client-proposed generation-based sensitivity**.
4. Include the share calculations, provenance, and warning statements in the report.

The Scenario ZIP is for **documentation** and cannot be directly imported into openLCA.

## 6. Tab 4 — Optional openLCA modeling (instructor enabled)

This path needs an **instructor-approved provider catalog for the same local ecoinvent 3.12 cut-off database** and a checked openLCA 2 installation. The cloud app does **not** supply licensed ecoinvent inventories.

1. Ask your instructor to validate technology mappings for active categories: **hydro, wind, biomass**. The zero-share natural-gas row needs no provider for this scenario.
2. Confirm the scenario uses **high voltage**. The v0.2 exporter does not support medium or low voltage.
3. If the catalog is available, open **4 · openLCA import** and download **openLCA JSON-LD ZIP**.
4. Import the ZIP into the **matching** licensed openLCA database; avoid overwriting existing datasets.
5. Inspect the imported foreground process, check each default provider, run linking checks, create a test product system and verify the LCA result.
6. Only after instructor validation, use the custom market as an alternative electricity input in a compatible high-voltage product system and compare against the original Ontario baseline.

**Critical limitations:** The package does not represent unmodeled imports or interzonal exchanges, independently establish a regional CI, automatically add grid infrastructure, or implement medium/low-voltage transformation. Successful ZIP generation does not establish a valid regional LCA.

## 7. What to submit

- Original Ontario provincial-grid GWP result, functional unit, and background dataset name.
- 2025 Northwest generation-mix table and source/provenance description.
- Streamlit scenario ZIP and methodology report.
- Updated GWP only if defensible *life-cycle* factors or a locally validated openLCA model are available.
- Short discussion: (a) generation vs consumption mix; (b) assumptions about biomass and imports; (c) effect on product GWP and its uncertainty.

## Instructor note

The supplied data are suitable for a **classroom sensitivity scenario**. They are not sufficient, on their own, to assert that the electricity delivered to the site is 86.8% hydropower or to claim a particular regional carbon intensity. Seek the source/methodology from the client before presenting this as a measured Northwest electricity mix.
