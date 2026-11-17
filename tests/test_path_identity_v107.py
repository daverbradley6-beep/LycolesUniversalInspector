import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

from path_identity_v107 import (
    PATH_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    build,
    migrate_v104_report,
    normalize_observation,
)

PLACE = 85896571713843


def identity(terminal_ordinal=1):
    return [
        {"name": "Workspace", "className": "Workspace", "ordinal": 1},
        {"name": "Stats", "className": "Folder", "ordinal": 1},
        {"name": "Coins", "className": "IntValue", "ordinal": terminal_ordinal},
    ]


def rich_row(terminal_ordinal=1):
    return {
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": identity(terminal_ordinal),
        "className": "IntValue",
    }


class PathIdentityV107Tests(unittest.TestCase):
    def test_full_identity_is_canonical(self):
        result = build([rich_row(2)], PLACE)
        self.assertEqual(result["schemaVersion"], REPORT_SCHEMA_VERSION)
        self.assertEqual(result["pathIdentityVersion"], PATH_SCHEMA_VERSION)
        self.assertEqual(result["objects"][0]["pathIdentity"], identity(2))
        self.assertEqual(result["objects"][0]["pathResolution"], "full_identity")

    def test_same_names_with_distinct_ordinals_are_preserved(self):
        result = build([rich_row(2), rich_row(1)], PLACE)
        self.assertEqual(result["acceptedCount"], 2)
        self.assertEqual(
            [item["pathIdentity"][-1]["ordinal"] for item in result["objects"]],
            [1, 2],
        )

    def test_exact_identity_duplicate_is_rejected(self):
        result = build([rich_row(), copy.deepcopy(rich_row())], PLACE)
        self.assertEqual(result["acceptedCount"], 1)
        self.assertEqual(result["rejections"], {"duplicate_identity": 1})

    def test_legacy_path_is_retained_without_fabricated_identity(self):
        result = build([{"path": "game.Workspace.Stats.Coins", "class": "IntValue"}], PLACE)
        item = result["objects"][0]
        self.assertIsNone(item["pathIdentity"])
        self.assertEqual(item["pathResolution"], "legacy_terminal_identity")

    def test_input_order_does_not_change_output(self):
        rows = [rich_row(2), rich_row(1)]
        self.assertEqual(build(rows, PLACE), build(list(reversed(rows)), PLACE))

    def test_legacy_path_is_rejected_when_rich_path_has_same_names(self):
        result = build([
            {"path": ["Workspace", "Stats", "Coins"], "className": "IntValue"},
            rich_row(),
        ], PLACE)
        self.assertEqual(result["acceptedCount"], 1)
        self.assertEqual(result["rejections"], {"ambiguous_legacy_path": 1})
        self.assertEqual(result["objects"][0]["pathResolution"], "full_identity")

    def test_v72_player_gui_path_gets_explicit_root_identity(self):
        row = {
            "path": ["HUD", "Coins"],
            "uniquePath": [
                {"name": "HUD", "className": "ScreenGui", "ordinal": 1},
                {"name": "Coins", "className": "TextLabel", "ordinal": 2},
            ],
            "className": "TextLabel",
        }
        source = {"schemaVersion": "72.import", "placeId": PLACE, "controls": [row]}
        result = build(source, PLACE)
        item = result["objects"][0]
        self.assertEqual(item["path"], ["PlayerGui", "HUD", "Coins"])
        self.assertEqual(
            item["pathIdentity"][0],
            {"name": "PlayerGui", "className": "PlayerGui", "ordinal": 1},
        )

    def test_v55_segments_are_accepted(self):
        row = {
            "segments": ["Workspace", *identity()[1:]],
            "className": "IntValue",
        }
        normalized = normalize_observation(row)
        self.assertEqual(normalized["path"], ["Workspace", "Stats", "Coins"])
        self.assertEqual(normalized["pathIdentity"], identity())

    def test_printable_unicode_identity_names_are_accepted(self):
        row = rich_row()
        row["path"][1] = "Stäts🚀"
        row["pathIdentity"][1]["name"] = "Stäts🚀"
        result = build([row], PLACE)
        self.assertEqual(result["acceptedCount"], 1)

    def test_unicode_added_after_older_python_databases_is_accepted(self):
        row = rich_row()
        row["path"][1] = "Stats\U0001fae8"
        row["pathIdentity"][1]["name"] = "Stats\U0001fae8"
        result = build([row], PLACE)
        self.assertEqual(result["acceptedCount"], 1)

    def test_control_characters_in_identity_names_are_rejected(self):
        row = rich_row()
        row["path"][1] = "Stats\nInjected"
        row["pathIdentity"][1]["name"] = "Stats\nInjected"
        result = build([row], PLACE)
        self.assertEqual(result["rejections"], {"invalid_path": 1})

    def test_format_characters_in_identity_names_are_rejected(self):
        row = rich_row()
        row["path"][1] = "Stats\u200bHidden"
        row["pathIdentity"][1]["name"] = "Stats\u200bHidden"
        result = build([row], PLACE)
        self.assertEqual(result["rejections"], {"invalid_path": 1})

    def test_noncharacters_in_identity_names_are_rejected(self):
        row = rich_row()
        row["path"][1] = "Stats\uffff"
        row["pathIdentity"][1]["name"] = "Stats\uffff"
        result = build([row], PLACE)
        self.assertEqual(result["rejections"], {"invalid_path": 1})

    def test_terminal_class_mismatch_is_rejected(self):
        row = rich_row()
        row["className"] = "NumberValue"
        result = build([row], PLACE)
        self.assertEqual(result["rejections"], {"identity_class_mismatch": 1})

    def test_identity_array_can_be_supplied_as_path(self):
        result = build([{"path": identity(), "className": "IntValue"}], PLACE)
        self.assertEqual(result["acceptedCount"], 1)
        self.assertEqual(result["objects"][0]["pathIdentity"], identity())

    def test_missing_supported_root_identity_is_rejected(self):
        row = rich_row()
        row["pathIdentity"][0] = {
            "name": "ServerStorage", "className": "ServerStorage", "ordinal": 1,
        }
        result = build([row], PLACE)
        self.assertEqual(result["rejections"], {"missing_root_identity": 1})

    def test_malformed_segment_fields_are_rejected(self):
        invalid_values = (True, 0, 100001, "1")
        for ordinal in invalid_values:
            with self.subTest(ordinal=ordinal):
                row = rich_row()
                row["pathIdentity"][1]["ordinal"] = ordinal
                result = build([row], PLACE)
                self.assertEqual(result["rejections"], {"invalid_path_identity": 1})

    def test_identity_names_must_match_path(self):
        row = rich_row()
        row["pathIdentity"][1]["name"] = "Other"
        result = build([row], PLACE)
        self.assertEqual(result["rejections"], {"path_identity_mismatch": 1})

    def test_migrate_v104_report_preserves_counts_and_contract(self):
        old = {
            "schemaVersion": "104.release",
            "placeId": PLACE,
            "inputCount": 2,
            "acceptedCount": 1,
            "rejectedCount": 1,
            "rejections": {"invalid_path": 1},
            "objects": [{
                "path": ["Workspace", "Stats", "Coins"],
                "className": "IntValue",
                "property": "Value",
                "canAutomate": False,
            }],
            "verifiedInGame": False,
            "gameplayFunctionsGenerated": 0,
            "readOnly": True,
        }
        migrated = migrate_v104_report(old)
        self.assertEqual(migrated["inputCount"], 2)
        self.assertEqual(migrated["rejections"], {"invalid_path": 1})
        self.assertIsNone(migrated["objects"][0]["pathIdentity"])
        self.assertEqual(migrated["migration"]["sourceSchemaVersion"], "104.release")

    def test_migrate_rejects_tampered_v104_contract(self):
        old = {
            "schemaVersion": "104.release",
            "placeId": PLACE,
            "inputCount": 1,
            "acceptedCount": 1,
            "rejectedCount": 0,
            "rejections": {},
            "objects": [{
                "path": ["Workspace", "Coins"],
                "className": "IntValue",
                "property": "Text",
                "canAutomate": False,
            }],
            "verifiedInGame": False,
            "gameplayFunctionsGenerated": 0,
            "readOnly": True,
        }
        with self.assertRaises(ValueError):
            migrate_v104_report(old)


if __name__ == "__main__":
    unittest.main()
