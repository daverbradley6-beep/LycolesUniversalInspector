Lycoles v93 Release Audit

v93 checks artifact hashes, place IDs, JSON structure, review-only contracts, and generated Luau for unsupported execution APIs. The v92 Unicode output has also been corrected to preserve UTF-8 characters.

Generate:

    py tools/diagnostic_builder_v92.py --place-id 85896571713843 --event-log results-v87-test2.txt --event-log results-v87-test3.txt --output build/release-v92

Audit:

    py tools/release_auditor_v93.py --directory build/release-v92 --version 92 --place-id 85896571713843 --report build/release-v92/audit-v93.json

Tests:

    py -m unittest discover -s tests -p test_release_auditor_v93.py -v
    py -m unittest discover -s tests -p test_diagnostic_builder_v92.py -v

A passing static audit does not establish in-game functionality or causality.
