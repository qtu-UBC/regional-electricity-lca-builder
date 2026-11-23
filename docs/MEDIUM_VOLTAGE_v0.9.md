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

**Troubleshooting an activity-name/geography lookup failure:** Some imported
openLCA databases expose formatted activity titles through IPC, such as
`market for electricity, high voltage | electricity, high voltage | Cutoff, U - CA-ON`,
and may use a short geography code rather than `Canada, Ontario`. The extractor
accepts that formatted title and recognizes the Ontario `CA-ON` alias.
For other regions, specify the exact short code shown in your database:

    python extract_mv_adapter.py \
      --region "Canada, Alberta" \
      --region-code "CA-AB" \
      --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
      --reviewer "Course instructor" \
      --out mv_adapter_REVIEW_LOCAL.json

If the lookup still fails, inspect the **Candidate descriptors** printed in
the error, confirm the active .zolca and IPC port, and do not approve or guess
a supplier. This lookup correction does not establish successful MV network validation;
source review and openLCA LCIA replication remain necessary before custom export.

## 3. Three-stage review workflow (no blanket scientific approval)

The region adapter has three distinct, local stages:

| Stage | Meaning | Allowed action |
|---|---|---|
| extracted | Original three ecoinvent processes/exchanges retrieved; no scientific review yet | Inspect topology and export baseline replication ZIP |
| reviewed_for_testing | Instructor explicitly confirms source process identifiers, input links and exchange assumptions have been inspected | Enter openLCA comparison evidence; baseline replication still available |
| replication_validated | Instructor enters matching LCIA results for original and replicated 1 kWh MV markets, using the same LCIA method, and confirms local provider linking | **May** unlock custom MV export, when an approved generator catalog and scenario are also present |

**Important:** The third stage represents **instructor-entered evidence** of
matching LCIA results; Streamlit cannot independently verify the original
openLCA calculations. It does **not** validate the actual Northwest
generation mix, imported/exported power flows, or suitability of Ontario
network proxies for a particular SAF facility.

The new extractor writes review_status = extracted. An existing file
mv_adapter_REVIEW_LOCAL.json with legacy approved=false or approved=true
is also treated as extracted; the old flag no longer unlocks the custom
export.

Before recording **reviewed for testing**, check in openLCA:

- Dataset identity: exact Ontario HV market, HV-to-MV transformer, MV market,
  and source ecoinvent 3.12 cut-off .zolca.
- All three quantitative reference outputs, matching HV/MV product flows,
  units, locations and UUIDs.
- HV market self-input links to the HV market; transformer uses HV market;
  MV market uses transformer; MV self-input links to MV market.
- Direct MV generation, high-voltage import providers, network
  infrastructure, non-electric inputs and elementary emissions.
- Transformation/self-consumption values and any potential proxy limitations.

Record reviewer's name and notes in **Tab 3** and download the
mv_adapter_REVIEWED_LOCAL.json file. No manual editing of an approval flag
is required.

## 4. Local Streamlit sequence

    streamlit run app.py

1. **Tab 1:** Choose a scenario and select electricity delivery level
   **medium**. Generic simplified loss scaling is disabled at zero.
2. **Tab 3 (no provider catalog needed):** Upload the local extracted
   mv_adapter_REVIEW_LOCAL.json. Confirm source topology and download
   **MV baseline replication ZIP** immediately.
3. Import baseline replication into a **test copy** of the same licensed
   .zolca with **Never update existing datasets**. Inspect three
   processes' provider UUIDs, reference outputs and network exchanges.
4. Record **reviewed for testing** locally in Tab 3 with a reviewer,
   checklist attestation and explanatory notes. You can complete the review
   before or after the baseline ZIP import. Download the reviewed local JSON.
5. Calculate **original Ontario MV** and **replicated Ontario MV**
   product systems in openLCA, both at **1 kWh MV** with the identical
   LCIA method and characterization factors.
6. In Tab 3 enter actual results for **climate change / GWP plus at least
   one other distinct LCIA category**, their units, method/version,
   reviewer, and notes confirming provider-link checks. The app checks
   numeric agreement within a **recorded relative tolerance** (default
   0.1%; absolute floor 1e-12 unit).
7. Download the **replication-validated local adapter JSON**, which
   includes the original/reproduced values, reviewer/date, source graph
   fingerprint and replicated process UUID. Keep it local.
8. **Tab 2:** Configure the separate instructor-approved generation
   provider catalog and choose reviewed providers for active technologies.
9. **Tab 3:** Upload the validated adapter JSON and select your scenario;
   the customized MV ZIP is available only when both the recorded replication
   and approved generator choices pass the guards.

Changing source exchange coefficients, providers, reference products or
regional process UUIDs changes the fingerprint and invalidates the stored
replication record. A new original-versus-replica comparison is required.
Switching to another generation scenario does not invalidate an unchanged
network-adapter replication, but scientifically representative generation
and site-delivery assumptions still need separate review.

**License note:** The MV adapter contains ecoinvent exchange amounts and
can be license-restricted. Keep it, its source extracts, and the manually
recorded evidence on an authorized local machine. Do not commit them to a
public Git repository or upload them to public Streamlit Cloud by default.

## 5. Exactly what is copied and what is tested

**Baseline replication ZIP — 3 foreground processes, no provider catalog**

- Copy of HV market, original external suppliers plus internal HV self-loop
  redirected to the copy.
- Copy of HV-to-MV transformer, original input coefficient linked to copied
  HV market.
- Copy of MV market, original direct MV generators/infrastructure/emissions
  plus self-loop and transformed-MV links redirected to copied processes.

Baseline process UUIDs depend **only on the adapter source-data fingerprint**,
not on review status, generator choice or scenario. This means the same
baseline ZIP can be compared before and after documenting review.

**Custom MV ZIP — 4 foreground processes, gated**

- New HV generator mix built from selected, approved provider references.
- Adapted HV market retaining network infrastructure, emissions and HV
  self-consumption; replacing all original external HV electricity supply
  with custom generation.
- Adapted HV-to-MV transformation retaining the source coefficient.
- Adapted MV market retaining self-consumption and non-electric burdens,
  but reallocating direct MV generation to the HV transformation pathway.
  This is an explicit **all-HV** assumption, not an observed regional fact.

**Computational check:** Compare original vs replicated 1 kWh MV product
system with identical LCIA method for GWP and another category. Record
numerical differences and investigate any inconsistency. If the values
do not match, custom MV export remains locked. The app checks numeric
agreement using values entered by the instructor; it does not run
ecoinvent/openLCA LCIA itself.

**Remaining limitations:** The exporter copies exchange amounts, flows,
units and explicit providers, but not every parameter formula, uncertainty
distribution, exchange cost or source process annotation. Even an exact
deterministic LCIA replication does not establish Monte Carlo equivalence,
physical power flow tracing, site-specific network losses, or scientific
representativeness of local generation as electricity consumed.

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
