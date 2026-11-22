# Medium-voltage customization — v0.9 instructor pilot

**Status:** JSON-LD builder and synthetic tests; NOT YET validated by importing
into the licensed class ecoinvent 3.12 cut-off .zolca and reproducing LCIA.
The workflow is region-agnostic for the **supported topology**, but it does
not assert that all ecoinvent regions have the same process structure.

## Why a regional adapter is required

The v0.8 HV builder connects reviewed high-voltage generators to a new
generation-mix process. A medium-voltage industrial customer also needs
voltage conversion, medium-voltage network infrastructure/emissions and
possibly direct MV generation. Hard-coding an Ontario loss factor would not
be general or scientifically appropriate.

v0.9 instead extracts these three source-region electricity processes locally:

1. market for electricity, high voltage
2. electricity voltage transformation from high to medium voltage
3. market for electricity, medium voltage

The converter retains the **original HV market non-electric exchanges and HV
self-consumption**, transformer coefficient, and **original MV market
non-electric inputs, emissions, and self-consumption**. In custom mode,
external HV electricity supply is replaced by the new HV generation mix;
direct MV electricity supply is rerouted through the HV transformation
pathway. This is the **all-HV scenario assumption**. The user must verify
whether it is appropriate for the site and generation mix.

**Boundary caution:** Retaining the source HV/MV network structure does NOT
make the client's local generation data a measured consumption mix. The
model does not resolve actual power flows, interzonal transfers, power
plant connection voltages or site-specific network characteristics.

## 1. Local prerequisites

- Restore the **same** licensed ecoinvent 3.12 cut-off .zolca used for the
  instructor-approved generator provider library.
- In openLCA 2, start **Tools → Developer Tools → IPC Server** (usually 8080).
- In your local repository, install cloud and instructor requirements:

      python -m pip install -r requirements.txt -r requirements_instructor.txt

- Confirm the exact regional process geography. In the Ontario example it
  is Canada, Ontario, not IESO Northwest. This represents an Ontario
  **network proxy**, not a Northwest-specific network dataset.

## 2. Extract the regional market adapter

Use the database label **exactly matching** your approved generator library:

      python extract_mv_adapter.py \
        --region "Canada, Ontario" \
        --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
        --reviewer "Course instructor" \
        --out mv_adapter_REVIEW_LOCAL.json

The extractor retrieves three processes, their exchange amounts,
flow/unit/property UUIDs, and default-provider UUIDs. It never downloads or
uploads data to a public Streamlit app.

**LICENSE NOTE:** Unlike the generation provider catalog, this adapter
contains **ecoinvent exchange coefficients, including elementary exchanges**.
Keep it on a licensed local workstation and **do not commit it to GitHub or
upload it to the public Streamlit instance by default**. Check your license
before any redistribution or hosted deployment. The gitignore protects
mv_adapter_*.json, but check staged files yourself.

If the region has multiple matching activities or uses another structure,
the extractor refuses to guess. Inspect the source market in openLCA.

## 3. Instructor review and approval

The generated adapter has approved=false. Confirm in openLCA:

- Correct geography, ecoinvent version, cut-off model and market UUIDs.
- All three reference outputs and compatible HV/MV flow-property/unit UUIDs.
- All important input provider links resolve against the restored .zolca.
- Transformation input comes from the selected HV market.
- HV and MV market self-inputs, if present, point to the corresponding
  source market.
- Direct MV generators and any unusual cross-voltage or import flows.
- Network infrastructure, SF6 inputs and elementary emissions.
- Full-precision amounts, including uncertainties if Monte Carlo is planned.
- Whether **all-HV generation** is defensible for the specific scenario.

Set approved=true only after review, retaining approved_by and reviewed_date.
Save to mv_adapter_APPROVED_LOCAL.json.

The v0.9 validator blocks adapters with unfamiliar cross-voltage input
patterns, missing input providers, mismatched product flows, duplicate
process identities, or non-zero user-defined simplified loss scaling.

## 4. Run Streamlit locally and export

      streamlit run app.py

1. **Tab 1:** Select a supply scenario. Set electricity delivery level to
   medium. The generic loss adjustment is disabled at zero.
2. **Tab 2:** Upload the instructor-approved generator provider catalog.
   Select one provider for each active generation technology; document the
   reason for each choice.
3. **Tab 3:** Upload the reviewed **local** regional MV adapter.
4. Review extracted transformation, self-consumption and direct-MV
   coefficients. Confirm their geography and the all-HV assumption.
5. Download **MV baseline replication ZIP** and **customized MV ZIP**.
   Both ZIPs need a database with matching source UUIDs.

Do not upload the exchange-bearing adapter to a public service without
explicitly checking ecoinvent licensing and deployment data controls.

### Export contents

**Replication export — 3 foreground processes**

- Copy of HV market, with original suppliers and self-loop redirected.
- Copy of HV-to-MV transformation, linked to the copied HV market.
- Copy of MV market, with original direct generation, network burdens,
  elementary exchanges and MV self-loop retained and locally redirected.

**Custom export — 4 foreground processes**

- New HV generator mix with instructor-reviewed providers.
- Adapted HV market: retains infrastructure/other exchanges/self-loop,
  replaces external HV electricity sources with the custom HV mix.
- Adapted transformation: retains the local HV input coefficient and
  supplies MV electricity from the custom HV market.
- Adapted MV market: removes direct MV generation, moves its amount to
  the transformed supply input, retains network/elementary exchanges and
  redirects its self-consumption to the custom MV market.

**Limitations:** The converter copies exchange amounts and explicit
providers, not all process metadata, exchange costs, parameter formulas,
uncertainty distributions, documentation, or database annotations.
An LCIA replication is required; Monte Carlo equivalence is not asserted.
The purpose is a reproducible foreground sensitivity scenario, not silently
replacing ecoinvent background data or certifying a Northwest grid mix.

## 5. Baseline replication validation — required gate

1. Import the replication ZIP to a **test copy** of the exact class .zolca:
   **Import → Linked Data (JSON-LD)**; **Never update existing datasets**.
2. Inspect each copied process's reference flow, non-electric exchanges,
   default providers and self-loop. Run openLCA linking checks.
3. Calculate a product system for 1 kWh of original regional MV market
   electricity and the replicated MV market with the **same LCIA method**.
4. Compare GWP and at least one other category. Record absolute and
   relative differences and investigate any unexplained mismatch.
5. **Do not interpret the custom MV result until replication passes.**
6. Then import the custom ZIP, verify no original-region grid electricity
   remains in the custom upstream path, and calculate the SAF sensitivity.

Static CI tests check topology and numeric transformations with
**synthetic example data**, not licensed ecoinvent data or live openLCA LCIA.

## 6. Ontario coefficients observed in the user's local .zolca

In the original Ontario transformation, 1.00482 kWh HV input per 1 kWh
MV output implies roughly 0.4797% transformation loss relative to HV input.

In the original Ontario MV market:

| Exchange | Amount per 1 kWh output |
|---|---:|
| MV from HV-to-MV transformer | 0.99862 kWh |
| Direct MV from municipal-waste electricity | 0.00138 kWh |
| MV market self-consumption | 0.00239 kWh |
| MV transmission network input | 1.86278e-8 km |
| Sulfur hexafluoride input | 1.29e-7 kg |
| Sulfur hexafluoride elementary output | 1.29e-7 kg |

These are **observations, not software defaults**. The adapter must extract
the source database coefficients and identifiers, including those of the
original HV market, whose exchanges have not been inspected in this chat.

For the simple recursive MV market:

    upstream HV kWh per 1 kWh MV =
        (non-self transformer MV input per market kWh) *
        (HV input per transformed MV kWh) /
        (1 - MV market self-input per market kWh)

This expression omits any further HV market self-consumption and extra
supply branches. Use the actual process graph for LCA calculation.

## 7. Other regions

Specify another **exact ecoinvent geography** with --region, and extract
the corresponding three processes. The validator refuses unsupported
structures; do not substitute a nearby geography silently.
For regions without suitable processes, document a justified proxy and
perform an additional scientific review. The architecture is general,
but **local replication validates each geography/database combination**.
