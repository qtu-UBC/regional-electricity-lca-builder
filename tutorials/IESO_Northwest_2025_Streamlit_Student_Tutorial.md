# Student tutorial: IESO Northwest 2025 generation-mix scenario

**Regional Electricity LCA Builder v0.7 · LCA Clinic · 20 November 2026**

**Important:** This example uses a **client-proposed estimate of 2025 generation in the IESO Northwest region**, not an independently verified IESO consumption-based electricity mix or official carbon intensity. The electricity generated within an area may not be the mix delivered to a facility because of imports, exports, interzonal transfers and losses.

## 1. Learning objectives

- Construct a documented alternative electricity supply mix with technology shares summing to 100%.
- Explain why a **generation mix** is not automatically a **consumption mix**.
- Select defensible electricity-generation providers from the instructor-reviewed ecoinvent 3.12 cut-off library.
- Export and inspect a custom high-voltage foreground electricity unit process in openLCA; calculate LCIA in **openLCA**, not Streamlit.
- Preserve scenario assumptions, provenance warnings and process-selection rationales for review.

## 2. Client-proposed generation data

| Source (as supplied) | 2025 output (GWh) | Reported share | Calculated share |
|---|---:|---:|---:|
| Hydroelectric | 3,132.8 | 86.8% | 86.8293% |
| Wind | 289.7 | 8.0% | 8.0294% |
| Biofuel | 185.5 | 5.1% | 5.1414% |
| Natural gas | 0.0 | 0.0% | 0.0000% |
| **Total** | **3,608.0** | **99.9% (rounded)** | **100.0000%** |

Reported shares total 99.9% due to rounding; the app uses each reported GWh value divided by **3,608.0 GWh**, entered as a fraction (0–1). The `biomass` scenario category represents the reported `biofuel` output, **not a verified fuel or technology match**. Students must check whether that 5.14% represents wood residues, biogas or other bioenergy before choosing a provider.

## 3. Tab 1 — Build supply mix

1. Under **Start with a scenario**, choose **IESO Northwest — 2025 proposed generation mix**. Its metadata and shares are loaded automatically. Do not upload the same CSV again unless deliberately replacing the preset.
2. Check **Reference year: 2025**, **What do the shares represent?: generation** and **Evidence / review status: user_supplied_unverified**.
3. Keep the electricity delivery level **high** for this introductory JSON-LD modeling exercise. Confirm the actual delivery voltage for any real project.
4. Leave **Losses to delivered kWh: 0%** in this example. This means losses are *not modeled*; it does not imply the physical grid has no losses.
5. If no public source URL is available for the proposed figures, leave the field blank. Record the client's data provenance in your report rather than invent a URL.
6. Check that the shares sum to **1.0000** and **Errors = 0**. Read the yellow advisories: the generation/consumption distinction and missing source verification remain important despite correct arithmetic.

**There are no carbon-intensity entry fields in this workflow.** The purpose is to build a foreground electricity process and let openLCA calculate the impacts.

## 4. Tab 2 — Select providers

This step requires an **instructor-approved provider library** extracted from the same locally restored ecoinvent 3.12 cut-off `.zolca` database that students use. The cloud app never contains the ecoinvent inventories.

1. In **A · Existing regional electricity markets**, find the appropriate Ontario electricity market for the *baseline*. An electricity market is already a mix; do not select it as a generation technology for the custom Northwest scenario.
2. In **B · Generation providers**, select an approved **Ontario hydro** process appropriate to the project (run-of-river or reservoir, as documented). **Pumped storage** is not a default primary generation choice.
3. Select an approved **Ontario onshore wind** process appropriate to the turbine assumptions.
4. For the **5.14% biomass** share, examine the Ontario `heat and power co-generation, biogas, gas engine` and `heat and power co-generation, wood chips, 6667 kW, state-of-the-art 2014` candidates. **Do not assume either one is correct** without knowing what the client's `biofuel` figure represents. CHP may also require reviewing allocation between electricity and heat.
5. Natural gas has a **0% share**, so no gas provider is needed.
6. Document a short **selection rationale** for each active provider, including technology, geography and any proxy assumptions. The dropdown ranks Ontario datasets first but does **not** prove they are representative. Unusual industrial co-product and storage processes appear only when the advanced filter is deliberately enabled.

If a defensible process is missing, ask the instructor to review the library rather than selecting an unrelated provider merely to complete the workflow.

## 5. Tab 3 — Export to openLCA and document the scenario

1. After selecting and explaining every active provider, download the **openLCA JSON-LD ZIP** from the first part of Tab 3. This archive contains **one foreground high-voltage electricity unit process** with references to existing processes in the shared database.
2. In the **Scenario documentation** section of the same tab, download the **scenario documentation ZIP** and **methodology report**. These record the supply shares, source status, advisories, and (when provider selections are available) selected provider references and rationales.
3. The **documentation ZIP is not importable into openLCA**. Only the JSON-LD foreground-process ZIP is intended for import.
4. Open your licensed ecoinvent 3.12 cut-off database in openLCA 2. Use **Import → Linked Data (JSON-LD)**; do not overwrite existing background data. Find the custom process, inspect its input exchanges and **default providers**, run the linking checks and calculate a small test product system.
5. Use the new supply process only for a compatible **high-voltage** product-system input. Compare with the baseline Ontario electricity market and describe assumptions about imports, losses, technology selection and uncertainty.
6. Do not interpret successful import or a calculated LCIA result as proof that the regional electricity mix is verified or eligible for regulatory claims.

## 6. What to submit

- The baseline Ontario electricity dataset and original product-system results, including the functional unit.
- The client-proposed 2025 generation table and clear provenance/verification status.
- Selected electricity generation providers, their geographies and selection rationales.
- The scenario documentation ZIP and methodology report.
- The imported openLCA foreground process, provider-link validation and calculated comparison with the baseline (once the instructor has validated the workflow).
- A short methodological discussion of generation versus consumption, biomass technology, transfers and uncertainty.

## Instructor note

This is a **classroom sensitivity scenario**, not an independently verified consumption-based Northwest electricity inventory. Before presenting numeric changes as regional impacts, validate the provider links in the class's shared `.zolca` and assess whether the proposed local generation shares approximate the electricity delivered to the study site. See the [instructor setup guide](../docs/SETUP_v0.4.md).
