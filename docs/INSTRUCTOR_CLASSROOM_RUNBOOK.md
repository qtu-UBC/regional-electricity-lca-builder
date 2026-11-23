# Instructor runbook — Northwest Ontario MV electricity lab

**Regional Electricity LCA Builder · Tested Ontario pilot · Updated 23 November 2026**

This is the operational checklist for preparing and teaching the classroom exercise. Share the [student lab guide](../tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md), not this instructor runbook or the licensed source adapter. For underlying modeling details and extension to other regions, see [MV technical reference](MEDIUM_VOLTAGE_v0.9.md).

> **Recommended design:** Complete extraction, provider review and baseline LCIA replication **once before class**. Students use a matching instructor-prepared custom ZIP in openLCA. They should not need to run the instructor review application, manage an IPC server, or approve ecoinvent data.

## 0. Choose the classroom mode

| Mode | Student work | Instructor work | Who handles the licensed MV adapter? |
|---|---|---|---|
| **A — Guided (recommended)** | Inspect shares and preselected providers; import prepared custom ZIP; calculate LCIA and analyze assumptions | Extract, approve, validate, export before class | Instructor only |
| B — Advanced local | Choose approved providers and export their **own** custom MV ZIP, then calculate | Prevalidate adapter; set up authorized local access | Licensed local student workstation |
| C — Introductory HV-only | Export one HV unit process | Provide approved provider metadata | Not required; **not MV delivered electricity** |

**Critical consistency rule:** A student selecting another generator in student Tab 2 will **not** change the instructor-prepared ZIP they import. If students compare alternatives, prepare a **different ZIP for each alternative** or allow authorized local student export. Otherwise treat alternative provider selection as a discussion exercise, not a distinct calculated LCA.

## 1. One-time prerequisites and extraction

From the repository root, with the same licensed ecoinvent 3.12 cut-off .zolca that the class uses:

~~~bash
git pull --ff-only origin main
mkdir -p local
python -m pip install -r requirements.txt -r requirements_instructor.txt
~~~

Restore the openLCA database, open it and enable **Tools → Developer Tools → IPC Server** (typically port 8080). Prefer a disposable **test copy** for imports. While IPC is running, extract **both** source inputs before changing apps:

~~~bash
python -m instructor.extract_provider_library \
  --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
  --reviewer "Course instructor" \
  --out local/provider_library_REVIEW.json

python -m instructor.extract_mv_adapter \
  --region "Canada, Ontario" \
  --database-label "ecoinvent 3.12 cut-off (class shared .zolca)" \
  --reviewer "Course instructor" \
  --out local/mv_adapter_REVIEW_LOCAL.json
~~~

The provider library contains process metadata. The MV adapter contains **licensed exchange coefficients**. Keep both in the ignored local/ folder unless sharing is explicitly authorized; **never push the adapter to public Git**. The database label and UUIDs must match exactly between the generator library and adapter.

If you have already generated a replication-validated adapter against the unchanged exact source database and exporter, **reuse it**; you do not need to re-extract or repeat this test for every class. Revalidation is required if the source network, database/version, identifiers or exporter methodology changes.

## 2. Instructor provider review — separate local application

Stop other Streamlit process if needed (**Ctrl+C**), then run:

~~~bash
streamlit run instructor/review_app.py
~~~

Open the local URL shown in Terminal (often http://localhost:8501).

1. Upload local/provider_library_REVIEW.json. Filter **Geography → Canada, Ontario**.
2. Select reviewed generators in the table; write an individual review reason for each.
3. **Click Apply decisions for displayed page before changing filters.** The staged count should increase.
4. Consider a six-process shortlist: Ontario **run-of-river and reservoir hydro**, **1–3 MW and >3 MW onshore wind**, **wood-chip and biogas CHP**. Do not include pumped-storage as ordinary primary hydro, or electricity markets as generators.
5. Optionally select Ontario HV and MV existing baseline markets, then click **Apply baseline market choices for this geography**.
6. Enter reviewer name and scope/limitations, check the confirmation checkbox, then click **Validate and prepare approved JSON**.
7. Download **provider_library_APPROVED_LOCAL.json** to local/. For the pilot six-choice shortlist, Tab 2 should later show **6 approved providers**.

These are approved **modeling options**, not verified actual Northwest generation, facility consumption or biofuel technology. The reusable interface works for other supported geographies. No case-specific approval script is needed.

## 3. Baseline MV replication — only once per source adapter

Stop instructor Streamlit with **Ctrl+C**; start the student app **locally**:

~~~bash
streamlit run app.py
~~~

The **student app** is the four-tab Regional Electricity LCA Builder. Do not confuse it with the instructor-review page on the same localhost port.

### 3A. Get replication ZIP without visiting Tab 2

1. **Tab 1:** Select **IESO Northwest — 2025 proposed generation mix**, and **Electricity delivery level = medium**. Generic loss scaling must remain **0%**.
2. **Skip Tab 2.** In **Tab 3**, upload local/mv_adapter_REVIEW_LOCAL.json.
3. Under **Stage 1 · Baseline replication**, download **electricity_MV_BASELINE_REPLICATION_openLCA.zip**. Extracted status is sufficient: this is a technical test, not an approval.

### 3B. Import and check three processes in openLCA

Right-click the **test copy** of the correct database → **Import… → Other… → JSON package (*.zip)**. Select the ZIP **without unzipping it**, choose **Never update a data set that already exists**, and finish.

| Baseline replicated process | Core provider/exchange checks |
|---|---|
| HV market | External original electricity suppliers retained; **0.017837256 kWh** HV self-input points to **replicated HV market**; network infrastructure and N₂O/ozone exchanges retained |
| HV-to-MV transformer | **1.0048249 kWh** HV from replicated HV market produces **1 kWh MV** |
| MV market | **0.99861521 kWh MV** from replicated transformer; **0.0013847929 kWh MV** original waste electricity; **0.0023926442 kWh MV** self-input points to **replicated MV market**; SF6 and network exchanges retained |

These coefficients are **Ontario pilot observations, not universal defaults**.

Create product systems for the **original Ontario MV market** and **replicated Ontario MV market**. Calculate both with the same **1 kWh MV** reference amount, same provider-linking setup and **ReCiPe 2016 v1.03 midpoint (H)** method. Record climate change and at least one other impact category (e.g. water use); inspect unresolved links rather than trusting a successful import alone.

### 3C. Record validation evidence in Tab 3

In the still-running student app:

1. **Stage 2**: enter reviewer and source-review notes confirming dataset identities, input coefficients, four core links, non-electric exchanges and infrastructure. Check the confirmation and click **Record reviewed for testing**.
2. **Stage 3**: enter original and replicated **climate change** values and **one other named LCIA category**, **both original/replicated values**, both units, method/version, reviewer, comparison notes and tolerance (default 0.1%). Confirm linking and 1 kWh functional units.
3. Click **Check numerical agreement and record replication evidence**. If it says **could not convert string to float: ''**, a numeric result is blank (frequently the second-category result).
4. Download **mv_adapter_REPLICATION_VALIDATED_LOCAL.json** to local/. The record is instructor-entered LCIA evidence tied to the specific adapter fingerprint, not an independent cloud calculation.

**Reference original-vs-replicated pilot result:** 0.12681 kg CO2-eq/kWh for climate change and 0.02685 m3/kWh for water use, equal **at displayed precision**. For a formal 0.1% comparison, use fuller precision if available. This does **not** establish uncertainty equivalence, site-specific grid losses, or Northwest electricity consumption.

## 4. Export the customized Northwest scenario — student app

Keep the student app running:

1. **Tab 1:** Check Northwest preset, year 2025, generation boundary, **medium** voltage, shares totaling 1.0000, 0% generic loss scaling.
2. **Tab 2:** Upload local/provider_library_APPROVED_LOCAL.json. Section **A** (existing market) is optional; it does not change the export. In Section **B**, choose Ontario generators and enter a rationale for each: **run-of-river hydro (86.83%)**, **onshore wind >3 MW (8.03%)**, **wood-chip CHP (5.14%; conditional assumption)**.
3. Check **Selected 3 of 3 active providers**.
4. **Tab 3:** Upload local/mv_adapter_REPLICATION_VALIDATED_LOCAL.json. Check that Stage displays **Replication Validated** and Stage 4 previews four processes.
5. Click **Download customized MV JSON-LD ZIP** → electricity_MV_CUSTOM_openLCA.zip. Also save scenario documentation ZIP and methodology report; these **cannot** be imported into openLCA.

Import custom ZIP into the test database using the same **Other… → JSON package (*.zip) → Never update** settings.

| Custom foreground process | Key verification before LCIA |
|---|---|
| Custom HV mix | 0.86829 kWh Ontario hydro + 0.08029 wind + 0.05141 wood-chip CHP for 1 kWh HV output; generation providers explicitly assigned |
| Custom HV market | 1 kWh HV from custom mix; **0.017837256 kWh** HV self-input to itself; original HV infrastructure and N2O/ozone retained |
| Custom transformer | **1.0048249 kWh** HV from custom HV market → 1 kWh MV |
| Custom MV market | 1.00000 kWh MV from custom transformer; **0.0023926442 kWh MV** self-input to itself; original SF6/network retained |

The original direct MV municipal-waste contribution is **rerouted through HV**. That is an **all-HV generation-entry assumption**, not a fact about Northwest plant connections. Both HV and MV self-inputs are already present; **do not apply another loss multiplier**.

Calculate a product system from **custom MV market** (not the custom HV mix), **1 kWh MV**, with the **same ReCiPe midpoint** method as baseline.

**Illustrative pilot results (rounded):** 0.01763 versus 0.12681 kg CO2-eq/kWh (custom vs original); water use 0.00015 versus 0.02685 m3/kWh; land use 0.02904 versus 0.00214 m2·a crop-eq/kWh. These are **not official Northwest factors**. Inspect climate and land-use contribution trees and identify process-specific and infrastructure burdens before interpretation.

## 5. Classroom hand-off checklist (Mode A)

Prepare and provide the following **before** the lab:

- [ ] Matching licensed openLCA database/instructions under institutional access.
- [ ] **One clearly labelled four-process custom ZIP per intended scenario**, with matching process choices documented.
- [ ] The student lab guide and a one-page provider choice key.
- [ ] Original Ontario MV baseline reference and instructor-tested expected results.
- [ ] Approved provider **metadata only if license permits sharing**, or screenshots/process list if not.
- [ ] Optional instructor-created alternative custom ZIP for a wood-chip/biogas or hydro sensitivity.
- [ ] An answer key and advice for troubleshooting missing provider links.

**Do not distribute the exchange-bearing MV adapter to students or expose it via a public Streamlit deployment by default.** In Mode A, students do **not** upload the MV adapter or redo original-vs-replicated validation.

### Two-hour lab

| Minutes | Activity |
|---:|---|
| 0–10 | Motivation: provincial vs regional generation vs site consumption |
| 10–25 | Tab 1 shares/provenance |
| 25–45 | Tab 2 provider rationales; identify exact prebuilt ZIP variant |
| 45–70 | Import custom ZIP; check four links |
| 70–100 | Calculate Ontario vs Northwest MV LCIA |
| 100–120 | Examine contributions and trade-offs; discuss assumptions |

## 6. Troubleshooting

| Symptom | Action |
|---|---|
| Cannot find review JSON | Files are normally in local/; run extractor with openLCA IPC or reuse the original local file |
| Student Tab 2 says no library | Upload the **approved** metadata library (not the REVIEW JSON), if licensed |
| Counter says **2 of 3** | One technology dropdown or its required rationale is missing |
| MV custom ZIP locked | Need medium voltage, same database UUIDs, **replication-validated** adapter, approved library, all generation choices/rationales |
| Import wizard confusion | **Import… → Other… → JSON package (*.zip)**; never unzip; **Never update existing datasets** |
| Baseline LCIA differs | Check source database, product-flow UUIDs, provider/self-links, functional unit and LCIA method; do not record failed replication as validated |
| Student app closed | Stop instructor app with **Ctrl+C**; start **streamlit run app.py**; use Terminal's local URL, usually localhost:8501 |
| Downloads lost between restarts | Downloaded files persist; Streamlit session selections may not. Store generated JSON and ZIP in local/ |
| Student selected a different generator but calculated same LCIA | They imported the **same instructor-prebuilt ZIP**. Prepare a separate ZIP for each distinct modeled scenario |

## 7. Scientific and license cautions

- A 2025 Northwest **generation** mix is not necessarily electricity delivered to a SAF facility. Validate imports/exports, location/connection voltage, supply contracts and site demand before claiming actual consumption.
- The Ontario network, losses, direct emissions and all-HV assumption are **proxies**, not measured Northwest infrastructure.
- The reported biofuel input is **not linked to a verified technology**; heat/electricity coproduct treatment may affect wood-chip versus biogas results.
- Baseline comparison supports **deterministic** copying, not uncertainty/Monte Carlo equivalence.
- Neither this tool nor successful openLCA import validates carbon-credit eligibility, Scope 2 claims, or SAF regulatory compliance.
- Keep ecoinvent-derived exchange amounts, database and MV adapter on authorized local devices; check licensing before putting even metadata on a cloud service.

## 8. Navigation and files

~~~text
student app: streamlit run app.py       Tab 1 -> Tab 2 -> Tab 3
instructor app: streamlit run instructor/review_app.py
openLCA: same ecoinvent 3.12 cut-off restored database
repo/local/: ignored workspace for extracted/approved/validated JSON and ZIP
~~~

Related references: [MV technical guide](MEDIUM_VOLTAGE_v0.9.md), [setup/archive notes](SETUP_v0.4.md), [student lab](../tutorials/IESO_Northwest_2025_Streamlit_Student_Tutorial.md).
