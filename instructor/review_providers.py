"""Reusable instructor review of provider *metadata* (not a scientific approval).

No provider is approved automatically. Input should be an extraction from the
same licensed .zolca as the classroom openLCA database. Keep reviewed files
local unless distribution is permitted by your license.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from provider_library import library_errors, provider_class, PROVIDER_CLASSES


def approve_provider_library(
    source: Mapping[str, Any],
    provider_reasons: Mapping[str, str],
    market_ids: list[str],
    reviewer: str,
    review_notes: str,
    *,
    allow_advanced: bool = False,
    reviewed_date: str | None = None,
) -> dict:
    """Review a subset by UUID with explicit per-provider reasons and safeguards.

    The generator selections are *allowlisted*; unselected processes remain
    unapproved, regardless of any flags in the input JSON.
    """
    if not isinstance(source, dict) or source.get("catalog_version") != 2:
        raise ValueError("Input must be an extracted catalog_version=2 provider library.")
    if source.get("extraction_truncated"):
        raise ValueError("Cannot approve a truncated provider extraction.")
    if source.get("system_model") != "cut-off" or source.get("voltage") != "high":
        raise ValueError("Only cut-off high-voltage provider libraries are supported.")
    if not str(reviewer).strip():
        raise ValueError("Reviewer name is required.")
    if len(str(review_notes).strip()) < 12:
        raise ValueError("Document the intended review scope and scenario caveats.")
    if not isinstance(provider_reasons, Mapping):
        raise ValueError("Provider approvals must map UUIDs to individual review reasons.")
    if not isinstance(market_ids, list):
        raise ValueError("Market approvals must be a list of UUIDs.")
    if not provider_reasons:
        raise ValueError("Select at least one generator, with a written review reason.")
    entries = source.get("entries")
    markets = source.get("markets", [])
    if not isinstance(entries, list) or not isinstance(markets, list):
        raise ValueError("The provider library needs entries and markets arrays.")
    entries_by_id = {p["id"]: p for p in entries if isinstance(p, dict) and p.get("id")}
    markets_by_id = {m["id"]: m for m in markets if isinstance(m, dict) and m.get("id")}
    if len(entries_by_id) != len(entries) or len(markets_by_id) != len(markets):
        raise ValueError("Source library has missing/duplicate UUIDs; fix extraction before review.")
    unknown = set(provider_reasons) - set(entries_by_id)
    unknown_market = set(market_ids) - set(markets_by_id)
    if unknown or unknown_market:
        raise ValueError(
            f"Unknown generator UUIDs: {sorted(unknown)}; unknown market UUIDs: "
            f"{sorted(unknown_market)}"
        )
    if len(market_ids) != len(set(market_ids)):
        raise ValueError("Duplicate market approvals.")

    result = copy.deepcopy(source)
    for row in result["entries"]:
        uid = row["id"]
        row["approved"] = uid in provider_reasons
        row.pop("review_reason", None)
        if not row["approved"]:
            continue
        reason = str(provider_reasons[uid]).strip()
        if len(reason) < 12:
            raise ValueError(f"Provider {uid} needs a review reason (12+ characters).")
        name = str(row.get("name", "")).casefold()
        if "market for electricity" in name or name.startswith("market group for electricity"):
            raise ValueError(f"Provider {uid} is an electricity market, not generation.")
        classification = provider_class(row)
        if classification not in ("generation", "cogeneration"):
            if not allow_advanced or classification not in PROVIDER_CLASSES:
                raise ValueError(
                    f"Provider {uid} classified as {classification}; "
                    "remove it or explicitly enable advanced review."
                )
        row["review_reason"] = reason
    for row in result["markets"]:
        row["approved"] = row["id"] in market_ids

    result["approved"] = True
    result["approved_by"] = str(reviewer).strip()
    result["reviewed_date"] = reviewed_date or date.today().isoformat()
    result["review_notes"] = str(review_notes).strip()
    result["review_scope"] = "instructor-approved modeling options; not regional generation verification"
    result["approved_provider_count"] = len(provider_reasons)
    result["approved_market_count"] = len(market_ids)

    errors = library_errors(result)
    if errors:
        raise ValueError("Provider library validation failed: " + "; ".join(errors))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Original extracted provider_library_REVIEW.json")
    parser.add_argument("--selection-file", required=True,
                        help="JSON with providers:[{id,reason}], markets:[UUID], reviewer, review_notes")
    parser.add_argument("--out", default="local/provider_library_APPROVED_LOCAL.json")
    parser.add_argument("--allow-advanced", action="store_true",
                        help="Allow unusual coproduct/storage activities after additional explicit review")
    parser.add_argument("--confirm", action="store_true",
                        help="Explicitly acknowledge instructor review before producing approved output")
    args = parser.parse_args()
    if not args.confirm:
        parser.error("--confirm is mandatory; provider review must be an explicit instructor action")
    source = json.loads(Path(args.source).read_text(encoding="utf-8-sig"))
    decisions = json.loads(Path(args.selection_file).read_text(encoding="utf-8-sig"))
    selections = decisions.get("providers", [])
    if not isinstance(selections, list) or any(
        not isinstance(x, dict) or "id" not in x or "reason" not in x for x in selections
    ):
        parser.error("Selection file providers must be [{id: ..., reason: ...}, ...]")
    if len({x["id"] for x in selections}) != len(selections):
        parser.error("Duplicate provider UUID in selection file")
    approved = approve_provider_library(
        source, {x["id"]: x["reason"] for x in selections},
        decisions.get("markets", []),
        decisions.get("reviewer", ""), decisions.get("review_notes", ""),
        allow_advanced=args.allow_advanced,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(approved, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {output}: {approved['approved_provider_count']} reviewed generators, "
          f"{approved['approved_market_count']} baseline markets.")
    print("Provider approval does not establish regional supply/consumption representativeness.")


if __name__ == "__main__":
    main()
