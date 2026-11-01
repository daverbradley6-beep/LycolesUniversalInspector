# Lycoles v96 — Evidence-to-Action Bridge

v96 connects the passive discovery pipeline to the v95 authorized Roblox Studio compiler. It **does not infer or execute actions directly from recorded gameplay**: a developer must explicitly map each eligible evidence candidate to a supported action and approve it. This is designed for Roblox experiences the developer owns or is authorized to edit.

## Smoke test

```powershell
py -m unittest discover -s tests -p test_evidence_to_actions_v96.py -v
py tools/evidence_to_actions_v96.py --review examples/v96-review-example.json --mapping examples/v96-developer-mapping.json --output build/release-v96
py tools/secure_action_compiler_v95.py --output build/release-v96 --audit-only
```

## Real evidence

Use a v91 review JSON that contains at least one `review_candidate` and construct a developer mapping file using the same place ID, candidate ID, observed input, and expected outcome. Set `developerApproved: true` and `reviewedByDeveloper: true` only after validating the mapping against your own game implementation. Supply actual Roblox developer User IDs. The mapping supports the v95 action types: increment_stat, set_attribute, teleport_to_part.

The compiler produces server/client Luau files, the v95 manifest and an additional `provenance-v96.json` with a digest of the input review and a mapping of candidate IDs to action IDs. Install the Luau scripts in the correct Roblox Studio services in your own experience.

## Constraints

Evidence review status does not establish causality or gameplay execution. An observed E key associated with a stat increase does not prove an arbitrary game supports the equivalent server-side action. The bridge refuses missing approval, ineligible candidates, mismatched outcomes, unknown actions, invalid User IDs, or mismatched place IDs. Generated scripts require independent in-game testing before production use.
