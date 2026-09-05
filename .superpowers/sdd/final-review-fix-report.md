# Whole-branch review fixes

## Fixes

- Value-haul candidates now receive batched seller profiles before delivery-cost gating. The seller profile's `country_code`, with the watch market as fallback, drives checkout extra, rough gating, payload `seller_country`, and persisted haul `country`.
- Size matching now prefers `size_title` and uses alphanumeric token boundaries. `M/L` remains valid for either target, while `XL` no longer matches `L` and title letters cannot override an explicit wrong size.
- `max_value_hauls_per_run` now caps value-haul score attempts instead of successful alerts.
- Pure `bundle_hunt` seed sellers still receive the configured 36-item closet fetch for haul evaluation, but their closet is excluded from premium per-item scoring unless that seller also entered the existing Path B/prior-row premium crawl set.
- Value-haul notification per-item prices are rounded to zero decimals.

## Test output

Command:

```text
cd scripts && uv run python -m unittest test_value_haul test_keep_rules test_bundle_pool test_profile_batch -v
```

Result:

```text
test_fingerprint_sorted_useful_only (test_value_haul.FingerprintTests.test_fingerprint_sorted_useful_only) ... ok
test_one_fails (test_value_haul.GateTests.test_one_fails) ... ok
test_three_candidates_pass (test_value_haul.GateTests.test_three_candidates_pass) ... ok
test_two_cheap_pass (test_value_haul.GateTests.test_two_cheap_pass) ... ok
test_two_expensive_fail (test_value_haul.GateTests.test_two_expensive_fail) ... ok
test_alert_rejects_high_scam (test_value_haul.PayloadAndAlertTests.test_alert_rejects_high_scam) ... ok
test_alert_requires_gate_after_rejects (test_value_haul.PayloadAndAlertTests.test_alert_requires_gate_after_rejects) ... ok
test_parse_object (test_value_haul.PayloadAndAlertTests.test_parse_object) ... ok
test_payload_totals (test_value_haul.PayloadAndAlertTests.test_payload_totals) ... ok
test_gym_title_accepted (test_value_haul.PrefilterTests.test_gym_title_accepted) ... ok
test_prefilter_caps_and_keeps_gym (test_value_haul.PrefilterTests.test_prefilter_caps_and_keeps_gym) ... ok
test_random_home_rejected (test_value_haul.PrefilterTests.test_random_home_rejected) ... ok
test_size_m_slash_l_matches (test_value_haul.PrefilterTests.test_size_m_slash_l_matches) ... ok
test_size_xl_does_not_match_l (test_value_haul.PrefilterTests.test_size_xl_does_not_match_l) ... ok
test_title_letters_do_not_override_size (test_value_haul.PrefilterTests.test_title_letters_do_not_override_size) ... ok
test_wrong_size_rejected (test_value_haul.PrefilterTests.test_wrong_size_rejected) ... ok
test_bundle_hunt_watch_never_keep (test_keep_rules.KeepRuleTests.test_bundle_hunt_watch_never_keep) ... ok
test_hunt_clothing_under_floor_is_not_keep (test_keep_rules.KeepRuleTests.test_hunt_clothing_under_floor_is_not_keep) ... ok
test_steal_clothing_under_floor_is_keep (test_keep_rules.KeepRuleTests.test_steal_clothing_under_floor_is_keep) ... ok
test_alerted_keys_preserve_insertion_order_and_trim_oldest (test_bundle_pool.BundlePoolTests.test_alerted_keys_preserve_insertion_order_and_trim_oldest) ... ok
test_current_row_wins_on_same_id (test_bundle_pool.BundlePoolTests.test_current_row_wins_on_same_id) ... ok
test_failed_closet_is_omitted_but_empty_closet_is_retained (test_bundle_pool.BundlePoolTests.test_failed_closet_is_omitted_but_empty_closet_is_retained) ... ok
test_fingerprint_stable (test_bundle_pool.BundlePoolTests.test_fingerprint_stable) ... ok
test_prior_extra_plus_new_keep_makes_bundle (test_bundle_pool.BundlePoolTests.test_prior_extra_plus_new_keep_makes_bundle) ... ok
test_attach_issues_one_comma_separated_seller_call (test_profile_batch.ProfileBatchTests.test_attach_issues_one_comma_separated_seller_call) ... ok

Ran 25 tests in 0.001s

OK
```
