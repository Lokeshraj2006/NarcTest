"""
Tests for the 13 compliance rules.

Covers the pass/fail/review path of each rule plus the orchestrator, with an
injected clock so date-sensitive rules are deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services.compliance_rules import (
    EXEMPT,
    FAIL,
    PASS,
    REVIEW,
    check_consumer_care,
    check_country_of_origin,
    check_expiry_date,
    check_font_size,
    check_generic_name,
    check_gstin_format,
    check_lmpc_registration,
    check_manufacturer_details,
    check_mfg_date,
    check_mrp,
    check_net_quantity,
    check_placement,
    check_readability,
    evaluate_all,
    summarize,
)

NOW = datetime(2026, 6, 15)


def _complete_label() -> dict:
    return {
        "product_name": "Masala Noodles",
        "manufacturer_name": "Nestle India Ltd.",
        "manufacturer_address": "Nestle House, Gurgaon 122002, Haryana",
        "country_of_origin": "India",
        "net_quantity": "70 g",
        "mrp": 14.0,
        "mfg_date": "12/05/2026",
        "expiry_date": "12/11/2026",
        "consumer_care_phone": "1800103194",
        "consumer_care_email": "care@nestle.in",
        "lmpc_number": "LMPC/HR/1234",
        # Checksum-valid GSTIN (the 'G' variant seen on some sample data has
        # a bad check digit — the correct one for this prefix is 'J').
        "gst_number": "06AAACN1160N1ZJ",
        "raw_text": "MRP Rs 14.00 inclusive of all taxes\nUSP Rs 0.20/g",
    }


# ── Rule 1 ───────────────────────────────────────────────────────────────
def test_manufacturer_pass():
    assert check_manufacturer_details(_complete_label())["status"] == PASS


def test_manufacturer_missing_both_fails():
    r = check_manufacturer_details({})
    assert r["status"] == FAIL
    assert "Neither" in r["failure_reason"]


def test_manufacturer_name_without_address_fails():
    r = check_manufacturer_details({"manufacturer_name": "Acme Foods"})
    assert r["status"] == FAIL
    assert "no address" in r["failure_reason"].lower()


def test_manufacturer_short_address_is_review():
    r = check_manufacturer_details(
        {"manufacturer_name": "Acme", "manufacturer_address": "Pune"}
    )
    assert r["status"] == REVIEW


def test_manufacturer_heading_read_but_address_unread_is_review():
    # Scan #18: OCR read "MARKETED BY:" but no address beside it.
    r = check_manufacturer_details(
        {"manufacturer_name": "HALDIRAMS", "raw_text": "MARKETED BY:\nFor EPR details scan the bercode"}
    )
    assert r["status"] == REVIEW
    assert "the address couldn't be read" in r["failure_reason"]


def test_manufacturer_heading_read_but_nothing_extracted_is_review():
    r = check_manufacturer_details({"raw_text": "Mfd. by:\n%RDA\nPer Servet"})
    assert r["status"] == REVIEW
    assert "name and address" in r["failure_reason"]


def test_manufacturer_missing_without_heading_still_fails():
    r = check_manufacturer_details({"manufacturer_name": "Acme Foods", "raw_text": "Net Wt 70 g"})
    assert r["status"] == FAIL


# ── Rule 2 ───────────────────────────────────────────────────────────────
def test_country_present_passes():
    assert check_country_of_origin({"country_of_origin": "India"})["status"] == PASS


def test_country_missing_domestic_is_exempt():
    assert check_country_of_origin({}, is_imported=False)["status"] == EXEMPT


def test_country_missing_unknown_origin_is_review():
    assert check_country_of_origin({})["status"] == REVIEW


# ── Rule 3 ───────────────────────────────────────────────────────────────
def test_generic_name_pass():
    assert check_generic_name({"product_name": "Toor Dal"})["status"] == PASS


def test_generic_name_missing_fails():
    assert check_generic_name({})["status"] == FAIL


def test_generic_name_not_identified_on_a_read_label_is_review():
    r = check_generic_name({"raw_text": "STORE IN A COOL & DRY PLACE\nMRP Rs 109"})
    assert r["status"] == REVIEW
    assert "another panel" in r["failure_reason"]


def test_generic_name_too_short_is_review():
    assert check_generic_name({"product_name": "AB"})["status"] == REVIEW


@pytest.mark.parametrize("name", ["Aloo Bhujia", "Bhujia Sev", "Maggi 2-Minute Masala Noodles"])
def test_real_product_names_pass(name):
    assert check_generic_name({"product_name": name})["status"] == PASS


# What OCR handed over as the product name on real Haldiram's scans.
@pytest.mark.parametrize(
    "text",
    [
        "MATERLAL IN ANAIR TIGHT CONTAINER.",
        "FIND MOR",
        "STORE IN A COOL & DRY PLACE, ONCE OPENED",
        "For Feedback or Queries, Write to-",
    ],
)
def test_label_boilerplate_as_name_is_review_not_pass(text):
    r = check_generic_name({"product_name": text})
    assert r["status"] == REVIEW
    assert "not a commodity name" in r["failure_reason"]


# ── Rule 4 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("qty", ["500 g", "1 kg", "200 ml", "1.5 L", "10 N"])
def test_net_quantity_valid_units_pass(qty):
    assert check_net_quantity({"net_quantity": qty})["status"] == PASS


def test_net_quantity_missing_fails():
    assert check_net_quantity({})["status"] == FAIL


def test_net_quantity_bad_unit_fails():
    r = check_net_quantity({"net_quantity": "500 blobs"})
    assert r["status"] == FAIL
    assert "not a permitted unit" in r["failure_reason"]


def test_net_quantity_unparseable_fails():
    assert check_net_quantity({"net_quantity": "family pack"})["status"] == FAIL


def test_net_quantity_zero_fails():
    assert check_net_quantity({"net_quantity": "0 g"})["status"] == FAIL


def test_net_quantity_heading_with_a_misread_letter_is_review():
    # Scan #19 read the heading as "NET QUAWTITY:".
    r = check_net_quantity({"raw_text": 'NET QUAWTITY:\nBATCH NO.:\n400 g (350g + 50g EXTRA")'})
    assert r["status"] == REVIEW


def test_net_quantity_heading_with_an_accent_and_a_cut_off_end_is_review():
    # Scan #21 read the heading as "NĚT QUANTIT".
    assert check_net_quantity({"raw_text": "NĚT QUANTIT\nMFG DATE"})["status"] == REVIEW


# ── Rule 5 ───────────────────────────────────────────────────────────────
def test_mrp_with_inclusive_wording_and_usp_passes():
    r = check_mrp({"mrp": 14.0, "net_quantity": "70 g",
                   "raw_text": "MRP Rs 14 inclusive of all taxes\nUSP Rs 0.20/g"})
    assert r["status"] == PASS
    assert "USP" in r["detected_value"]


@pytest.mark.parametrize(
    "raw_text",
    [
        "MRP: Rs.109.00 (Incl. of all taxes)\nUSP: Rs.0.27 per g",
        "MRP:3\n(ncl. of all taxes)\nRs.109,00\nRs.0.27 Per g",  # real OCR: leading "I" dropped
        "Rs 109 INCLUSIVE OF ALL TAXES\nUnit Sale Price: Rs 0.27/g",
    ],
)
def test_mrp_inclusive_wording_variants_pass(raw_text):
    fields = {"mrp": 109.0, "net_quantity": "400 g", "raw_text": raw_text}
    assert check_mrp(fields)["status"] == PASS


# ── Unit sale price (checked inside Rule 5, REVIEW only) ─────────────────
def test_missing_usp_is_review_not_fail():
    r = check_mrp({"mrp": 14.0, "net_quantity": "70 g", "raw_text": "MRP Rs 14 inclusive of all taxes"})
    assert r["status"] == REVIEW
    assert "unit sale price" in r["failure_reason"].lower()


def test_usp_heading_with_unread_value_is_review():
    r = check_mrp({"mrp": 109.0, "net_quantity": "400 g",
                   "raw_text": "MRP Rs.109.00 (incl. of all taxes)\nUSP (R Per gl:"})
    assert r["status"] == REVIEW
    assert "heading" in r["failure_reason"]


def test_usp_that_disagrees_with_mrp_per_quantity_is_review():
    # Real OCR of the Haldiram pack read its USP as Rs.0.31; 109 / 400 g = 0.27.
    r = check_mrp({"mrp": 109.0, "net_quantity": "400 g",
                   "raw_text": "MRP Rs.109.00 (incl. of all taxes)\nRs.0.31 Per g"})
    assert r["status"] == REVIEW
    assert "0.27" in r["failure_reason"]


@pytest.mark.parametrize(
    "mrp, qty, usp_text",
    [
        (45.0, "35 g", "USP R1.29/9"),          # Amul; "/g" read as "/9"
        (250.0, "200ml", "Unit Sale Price : Rs 1.25 Per ml"),  # Ob & Gob
        (220.0, "1 kg", "USP Rs 220/kg"),
        (99.0, "1 L", "USP Rs 0.10/ml"),        # per ml of a litre pack
    ],
)
def test_usp_matching_mrp_per_quantity_passes(mrp, qty, usp_text):
    r = check_mrp({"mrp": mrp, "net_quantity": qty,
                   "raw_text": f"MRP (incl. of all taxes)\n{usp_text}"})
    assert r["status"] == PASS, r["failure_reason"]


@pytest.mark.parametrize(
    "raw_text",
    [
        "MRP Rs 109 exclusive of all taxes",
        "nd, o. toxes)\nRs.109,00",  # real OCR too mangled to confirm the wording
    ],
)
def test_mrp_wording_not_established_is_review(raw_text):
    assert check_mrp({"mrp": 109.0, "raw_text": raw_text})["status"] == REVIEW


def test_mrp_without_inclusive_wording_is_review():
    r = check_mrp({"mrp": 14.0, "raw_text": "MRP Rs 14"})
    assert r["status"] == REVIEW
    assert "inclusive of all taxes" in r["failure_reason"]


def test_mrp_missing_fails():
    assert check_mrp({})["status"] == FAIL


def test_mrp_zero_fails():
    assert check_mrp({"mrp": 0})["status"] == FAIL


# ── Rule 6 ───────────────────────────────────────────────────────────────
def test_mfg_date_past_passes():
    assert check_mfg_date({"mfg_date": "12/05/2026"}, now=NOW)["status"] == PASS


def test_mfg_date_future_is_review_not_fail():
    # A future date is more often a misread digit (scan #34) than a pre-dated pack.
    r = check_mfg_date({"mfg_date": "12/12/2026"}, now=NOW)
    assert r["status"] == REVIEW
    assert "future" in r["failure_reason"]


def test_mfg_date_missing_fails():
    assert check_mfg_date({}, now=NOW)["status"] == FAIL


def test_mfg_date_unparseable_is_review():
    assert check_mfg_date({"mfg_date": "sometime"}, now=NOW)["status"] == REVIEW


# ── Rule 7 ───────────────────────────────────────────────────────────────
def test_expiry_future_passes():
    assert check_expiry_date({"expiry_date": "12/11/2026"}, now=NOW)["status"] == PASS


def test_expiry_past_fails_as_expired():
    r = check_expiry_date({"expiry_date": "01/01/2026"}, now=NOW)
    assert r["status"] == FAIL
    assert "expired" in r["failure_reason"].lower()


def test_expiry_missing_is_review_not_fail():
    # Not every commodity needs an expiry date.
    assert check_expiry_date({}, now=NOW)["status"] == REVIEW


def test_expiry_same_as_manufacture_date_is_review_not_expired():
    # Scan #35: both dates typed as 11/06/26 was reported "expired" and got a
    # GO notice. Identical dates mean one was misread or mistyped.
    r = check_expiry_date({"mfg_date": "11/06/26", "expiry_date": "11/06/26"}, now=datetime(2026, 9, 25))
    assert r["status"] == REVIEW
    assert "not after the manufacture date" in r["failure_reason"]


def test_expiry_before_manufacture_date_is_review():
    r = check_expiry_date({"mfg_date": "12/05/2026", "expiry_date": "01/01/2026"}, now=NOW)
    assert r["status"] == REVIEW


def test_expired_pack_with_sensible_dates_still_fails():
    r = check_expiry_date({"mfg_date": "01/01/2026", "expiry_date": "01/03/2026"}, now=NOW)
    assert r["status"] == FAIL
    assert "expired" in r["failure_reason"].lower()


def test_consumer_care_heading_without_readable_contact_is_review():
    r = check_consumer_care({"raw_text": "WWW.amul.com\nLIc. No\nWe apprec"})
    assert r["status"] == REVIEW


def test_a_spaced_toll_free_number_is_long_enough():
    assert check_consumer_care({"consumer_care_phone": "1800 258 3333"})["status"] == PASS


def test_month_name_date_without_a_separator_before_the_year():
    assert check_mfg_date({"mfg_date": "11/JUN25"}, now=NOW)["status"] == PASS


def test_consumer_care_missing_without_heading_still_fails():
    assert check_consumer_care({"raw_text": "Net Weight: 35 g"})["status"] == FAIL


def test_month_abbreviation_dates_are_understood():
    # Amul dark chocolate prints "Pkd.11/JUN/26" and "Exp.11/JUN/27".
    assert check_mfg_date({"mfg_date": "11/JUN/26"}, now=NOW)["status"] == PASS
    assert check_expiry_date({"expiry_date": "11/JUN/27"}, now=NOW)["status"] == PASS


def test_a_nutrition_footnote_is_not_a_product_name():
    # Scan #33 took "Approx Values ** % RDA Calculated" as the name.
    r = check_generic_name({"product_name": "hpprox Values ** % RDA Calculated"})
    assert r["status"] == REVIEW


# ── Dates or price printed on another surface ────────────────────────────
# Real wording from an Ob & Gob ice-cream tub: the dates are on the lid seal.
SEE_SEAL = "Net Qty.: 200ml / 155g\nBATCH NO., MFD., USE BY: SEE SEAL"


def test_mfg_date_on_the_seal_is_review_not_fail():
    r = check_mfg_date({"raw_text": SEE_SEAL}, now=NOW)
    assert r["status"] == REVIEW
    assert "seal" in r["failure_reason"]
    assert json.loads(r["details_json"])["printed_elsewhere"] == "seal"


def test_expiry_on_the_seal_says_where_to_look():
    r = check_expiry_date({"raw_text": SEE_SEAL}, now=NOW)
    assert r["status"] == REVIEW
    assert "seal" in r["failure_reason"]


def test_redirect_split_across_ocr_lines_still_counts():
    r = check_mfg_date({"raw_text": "BATCH NO., MFD., USE BY: SEE\nSEAL"}, now=NOW)
    assert r["status"] == REVIEW


def test_mrp_printed_on_the_bottom_is_review():
    r = check_mrp({"raw_text": "M.R.P.: SEE BOTTOM OF PACK"})
    assert r["status"] == REVIEW
    assert "bottom" in r["failure_reason"]


def test_a_date_redirect_does_not_excuse_a_missing_price():
    assert check_mrp({"raw_text": SEE_SEAL})["status"] == FAIL


def test_an_unrelated_see_back_does_not_excuse_a_missing_date():
    r = check_mfg_date({"raw_text": "Ingredients: see back of pack"}, now=NOW)
    assert r["status"] == FAIL


def test_a_date_read_from_the_seal_is_still_checked():
    r = check_mfg_date({"mfg_date": "12/12/2026", "raw_text": SEE_SEAL}, now=NOW)
    assert r["status"] == REVIEW
    assert "future" in r["failure_reason"], "the date itself is checked, not excused"


# ── Rule 8 ───────────────────────────────────────────────────────────────
def test_consumer_care_phone_passes():
    assert check_consumer_care({"consumer_care_phone": "18001031947"})["status"] == PASS


def test_consumer_care_email_only_passes():
    assert check_consumer_care({"consumer_care_email": "a@b.com"})["status"] == PASS


def test_consumer_care_missing_fails():
    assert check_consumer_care({})["status"] == FAIL


def test_consumer_care_short_phone_is_review():
    assert check_consumer_care({"consumer_care_phone": "123"})["status"] == REVIEW


# ── Rules 9-11 (CV-dependent) ────────────────────────────────────────────
def test_cv_rules_return_review_without_measurements():
    for fn, num in ((check_font_size, 9), (check_readability, 10), (check_placement, 11)):
        r = fn({})
        assert r["status"] == REVIEW, f"rule {num} should be REVIEW"
        assert r["rule_number"] == num
        assert "couldn't be measured from this photo" in r["failure_reason"]
        assert "not yet implemented" not in r["failure_reason"]


def test_font_size_uses_measurement_when_supplied():
    ok = check_font_size({}, {"min_height_mm": 1.5, "threshold_mm": 1.0})
    assert ok["status"] == PASS
    low = check_font_size({}, {"min_height_mm": 0.6, "threshold_mm": 1.0})
    assert low["status"] == REVIEW
    assert "measure it on the pack" in low["failure_reason"]


def test_font_size_never_fails_from_a_photo():
    # The barcode may be printed at 80-200% of standard size, so even a very
    # small reading is an estimate for a person to confirm, not a breach.
    for h in (0.1, 0.5, 0.84, 0.9):
        r = check_font_size({}, {"min_height_mm": h, "threshold_mm": 1.0})
        assert r["status"] == REVIEW, f"{h} mm should be REVIEW"


@pytest.mark.parametrize("calibration, words", [
    ({"usable": False, "reason": "No barcode bounding box supplied."},
     "no barcode was found to use as a ruler"),
    ({"usable": False, "reference": "code128", "barcode_width_px": 300.0},
     "has no standard width"),
    ({"usable": False, "mm_per_px": 0.9, "reference": "ean13", "barcode_width_px": 41.0},
     "scale looked wrong"),
    ({"usable": True, "mm_per_px": 0.1, "reference": "ean13", "barcode_width_px": 373.0},
     "no label text could be located"),
])
def test_unmeasured_font_size_says_why(calibration, words):
    r = check_font_size({}, None, calibration=calibration)
    assert r["status"] == REVIEW
    assert words in r["failure_reason"]


def test_evaluate_all_passes_the_barcode_calibration_to_rule_9():
    results = evaluate_all(
        _complete_label(), now=NOW,
        cv_measurements={"calibration": {"usable": False, "reason": "No barcode bounding box supplied."}},
    )
    font = next(r for r in results if r["rule_code"] == "FONT_SIZE")
    assert font["status"] == REVIEW
    assert "no barcode was found to use as a ruler" in font["failure_reason"]


def test_readability_uses_measurement_when_supplied():
    assert check_readability({}, {"contrast_ratio": 7.0})["status"] == PASS
    assert check_readability({}, {"contrast_ratio": 2.0})["status"] == FAIL


def test_readability_inconclusive_photo_reading_is_review():
    r = check_readability({}, {"contrast_ratio": 2.18, "threshold": 4.5, "inconclusive": True})
    assert r["status"] == REVIEW
    assert "not proof of a breach" in r["failure_reason"]


def test_placement_uses_measurement_when_supplied():
    assert check_placement({}, {"on_principal_panel": True})["status"] == PASS
    assert check_placement({}, {"on_principal_panel": False})["status"] == FAIL


# ── Rule 12 ──────────────────────────────────────────────────────────────
def test_lmpc_present_passes():
    assert check_lmpc_registration({"lmpc_number": "LMPC/HR/1234"})["status"] == PASS


def test_lmpc_missing_on_import_fails():
    r = check_lmpc_registration({}, is_imported=True)
    assert r["status"] == FAIL


def test_lmpc_missing_unknown_is_review():
    assert check_lmpc_registration({})["status"] == REVIEW


# ── Rule 13 ──────────────────────────────────────────────────────────────
def test_gstin_valid_passes():
    assert check_gstin_format("06AAACN1160N1ZJ")["status"] == PASS


def test_gstin_bad_checksum_fails():
    r = check_gstin_format("06AAACN1160N1ZG")  # correct check digit is 'J'
    assert r["status"] == FAIL
    assert "checksum" in r["failure_reason"].lower()


def test_gstin_missing_is_exempt():
    assert check_gstin_format(None)["status"] == EXEMPT


def test_gstin_shaped_but_wrong_structure_fails():
    assert check_gstin_format("06AAACN1160N1XJ")["status"] == FAIL  # 14th char must be 'Z'


def test_gstin_separators_are_ignored():
    assert check_gstin_format("06-AAACN1160N1ZJ")["status"] == PASS


def test_value_not_shaped_like_a_gstin_is_review():
    # Real scan: a pouch maker's packaging registration number in the GSTIN field.
    r = check_gstin_format("11-AACCM8173H-22")
    assert r["status"] == REVIEW
    assert "shape" in r["failure_reason"]
    assert '"live_registry_verified": false' in r["details_json"]
    assert check_gstin_format("NOTAGSTIN")["status"] == REVIEW


def test_gstin_never_claims_live_verification():
    r = check_gstin_format("06AAACN1160N1ZJ")
    assert '"live_registry_verified": false' in r["details_json"]


# ── Orchestrator ─────────────────────────────────────────────────────────
def test_evaluate_all_returns_thirteen_in_order():
    results = evaluate_all(_complete_label(), now=NOW)
    assert len(results) == 13
    assert [r["rule_number"] for r in results] == list(range(1, 14))


def test_evaluate_all_complete_label_has_no_failures():
    results = evaluate_all(_complete_label(), is_imported=False, now=NOW)
    fails = [r for r in results if r["status"] == FAIL]
    assert fails == [], f"unexpected failures: {[f['rule_code'] for f in fails]}"


# Real OCR from a fully labelled Bhujia Sev pack: the headings and the values
# came back as separate columns, so no value was paired with its heading.
_SPLIT_COLUMN_OCR = (
    "MRP\nUSP\nNET OUANTITY:\nATCH NO.:\nMG DATE:\n200 g\nLFG13-18\n4107/26\n8/02/27\nRe60 00"
)


def test_unread_values_under_printed_headings_are_review_not_fail():
    fields = {"raw_text": _SPLIT_COLUMN_OCR}
    results = [check_net_quantity(fields), check_mrp(fields), check_mfg_date(fields, now=NOW)]
    assert [r["status"] for r in results] == [REVIEW, REVIEW, REVIEW]
    assert all("couldn't be read" in r["failure_reason"] for r in results)


@pytest.mark.parametrize(
    "heading",
    ["NET QUANTITY:", "Net Wt.", "Net Contents", "M.R.P.", "MFG. DATE:", "MFG, DATE:", "Mfd dt", "Pkd on", "Date of Packing"],
)
def test_heading_variants_are_recognised(heading):
    fields = {"raw_text": f"INGREDIENTS: Potato\n{heading}"}
    statuses = {check_net_quantity(fields)["status"], check_mrp(fields)["status"],
                check_mfg_date(fields, now=NOW)["status"]}
    assert REVIEW in statuses


def test_declarations_absent_from_label_text_still_fail():
    fields = {"raw_text": "INGREDIENTS: Potato, Edible Oil\nSTORE IN A COOL & DRY PLACE"}
    assert check_net_quantity(fields)["status"] == FAIL
    assert check_mrp(fields)["status"] == FAIL
    assert check_mfg_date(fields, now=NOW)["status"] == FAIL


def test_split_column_pack_raises_no_declaration_failures():
    failed = {r["rule_code"] for r in evaluate_all({"raw_text": _SPLIT_COLUMN_OCR}, now=NOW)
              if r["status"] == FAIL}
    assert not failed & {"NET_QUANTITY", "MRP_DECLARATION", "MFG_DATE"}


def test_evaluate_all_empty_label_fails_the_mandatory_rules():
    results = evaluate_all({}, now=NOW)
    failed = {r["rule_code"] for r in results if r["status"] == FAIL}
    for code in (
        "MANUFACTURER_DETAILS",
        "GENERIC_NAME",
        "NET_QUANTITY",
        "MRP_DECLARATION",
        "MFG_DATE",
        "CONSUMER_CARE",
    ):
        assert code in failed, f"{code} should FAIL on an empty label"


def test_evaluate_all_cv_rules_are_review_by_default():
    results = evaluate_all(_complete_label(), now=NOW)
    cv = {r["rule_code"]: r["status"] for r in results
          if r["rule_code"] in ("FONT_SIZE", "READABILITY", "PLACEMENT")}
    assert set(cv.values()) == {REVIEW}


def test_evaluate_all_accepts_camelcase_gstin_key():
    results = evaluate_all({"gstNumber": "06AAACN1160N1ZG"}, now=NOW)
    gstin = next(r for r in results if r["rule_code"] == "GSTIN_FORMAT")
    assert gstin["status"] == FAIL


def test_summarize_counts_match_total():
    results = evaluate_all(_complete_label(), now=NOW)
    counts = summarize(results)
    assert sum(counts.values()) == 13


def test_every_result_carries_a_statutory_reference():
    for r in evaluate_all(_complete_label(), now=NOW):
        assert r["statutory_reference"], f"rule {r['rule_number']} has no citation"
