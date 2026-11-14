import pathlib
import subprocess
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "LycolesUniversalInspector.lua"
SOURCE_TEXT = SOURCE_PATH.read_text(encoding="utf-8")
LUAU_BIN = ROOT / "build" / "luau-0.744" / "luau"


def extract_runtime_packaging_block() -> str:
    start_token = "local function jsonSafe(value, active, depth)"
    end_token = "-- Dynamic discovery records newly replicated instances"
    start = SOURCE_TEXT.find(start_token)
    end = SOURCE_TEXT.find(end_token)
    if start < 0 or end < 0 or end <= start:
        raise AssertionError("packaging runtime block not found")
    return SOURCE_TEXT[start:end]


def run_luau_harness(body: str) -> str:
    runtime_block = extract_runtime_packaging_block()
    harness = textwrap.dedent(
        f"""
        local WORKFLOW_HELPERS = {{}}
        local MAX_PART_BYTES = 105000

        local function _json_escape(value)
            local slash = string.char(92)
            value = value:gsub(slash, slash .. slash)
            value = value:gsub(string.char(34), slash .. string.char(34))
            value = value:gsub(string.char(10), slash .. "n")
            value = value:gsub(string.char(13), slash .. "r")
            value = value:gsub(string.char(9), slash .. "t")
            return '"' .. value .. '"'
        end

        local function _json_is_array(tbl)
            local count = 0
            local max = 0
            for key, _ in pairs(tbl) do
                if type(key) ~= "number" or key < 1 or key % 1 ~= 0 then
                    return false
                end
                if key > max then max = key end
                count = count + 1
            end
            return count > 0 and max == count
        end

        local function _json_encode_value(value, active)
            local kind = type(value)
            if kind == "nil" then return "null" end
            if kind == "boolean" then return value and "true" or "false" end
            if kind == "number" then return tostring(value) end
            if kind == "string" then return _json_escape(value) end
            if kind ~= "table" then return _json_escape(tostring(value)) end
            if active[value] then return '"[circular]"' end
            active[value] = true
            local out
            if _json_is_array(value) then
                local items = {{}}
                for i = 1, #value do
                    items[#items + 1] = _json_encode_value(value[i], active)
                end
                out = "[" .. table.concat(items, ",") .. "]"
            else
                local keys = {{}}
                for key, _ in pairs(value) do
                    keys[#keys + 1] = key
                end
                table.sort(keys, function(left, right)
                    return tostring(left) < tostring(right)
                end)
                local items = {{}}
                for _, key in ipairs(keys) do
                    local key_text = type(key) == "string" and key or tostring(key)
                    items[#items + 1] = _json_escape(key_text) .. ":" .. _json_encode_value(value[key], active)
                end
                out = "{{" .. table.concat(items, ",") .. "}}"
            end
            active[value] = nil
            return out
        end

        local function _json_encode(value)
            return _json_encode_value(value, {{}})
        end

        local guid_counter = 0
        local HttpService = {{
            GenerateGUID = function(_)
                guid_counter = guid_counter + 1
                return "guid-" .. tostring(guid_counter)
            end,
            JSONEncode = function(_, value)
                return _json_encode(value)
            end,
        }}

        {runtime_block}

        {body}
        """
    )

    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as tmp:
        tmp.write(harness)
        tmp_path = pathlib.Path(tmp.name)
    try:
        proc = subprocess.run(
            [str(LUAU_BIN), str(tmp_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise AssertionError(
                f"luau harness failed\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )
        return proc.stdout.strip()
    finally:
        tmp_path.unlink(missing_ok=True)


@unittest.skipUnless(LUAU_BIN.is_file(), "luau runtime binary unavailable")
class InspectorPackagingRuntimeTests(unittest.TestCase):
    def test_prepare_parts_externalizes_oversized_targeted_summary(self):
        out = run_luau_harness(
            """
            local hugeSamples = {}
            for i = 1, 320 do
                hugeSamples[i] = {kind = "camera", index = i, note = string.rep("X", 420)}
            end
            local report = {
                version = "30.6.67",
                placeId = 3623096087,
                gameId = 111,
                placeVersion = 1,
                inspectedAt = "2026-11-13T00:00:00Z",
                gameName = "PackagingRuntime",
                counts = {},
                groups = {},
                scanStats = {recorded = 2, complete = true},
                sessionId = "session-1",
                snapshotId = "snapshot-1",
                parentSnapshotId = nil,
                featureEvidence = {},
                featureReadiness = {},
                featureSnapshotDelta = {},
                automationDiagnostics = {},
                diagnostics = {complete = true},
                objects = {
                    {path = "Workspace.A", class = "Part", scanOrdinal = 1},
                    {path = "Workspace.B", class = "Part", scanOrdinal = 2},
                },
                interactionDiagnostics = {
                    recentInteractions = {},
                    targetedCaptureSessionSummary = {
                        schemaVersion = "31.0.targeted-evidence-session.1",
                        sessionId = "targeted-session-1",
                        samples = {
                            cameraSamples = hugeSamples,
                            timelineEvents = hugeSamples,
                        },
                        requestProgress = {
                            ["combat-camera-weapon-correlation"] = {
                                status = "collecting",
                                missingEvidence = {"camera-correlation"},
                                satisfiedEvidence = {},
                            }
                        },
                    },
                },
            }
            local parts, scanId, summary = prepareParts(report)
            local largest = 0
            for _, body in ipairs(parts) do
                if #body > largest then largest = #body end
                if #body > MAX_PART_BYTES then
                    error("part-limit-exceeded")
                end
            end
            if summary.targetedCaptureSessionSummaryExportMode ~= "separate-bounded-parts" then
                error("missing-summary-export-mode")
            end
            if type(summary.chunkedInteractionDiagnosticSummaryFields) ~= "table"
                or #summary.chunkedInteractionDiagnosticSummaryFields < 1 then
                error("missing-summary-chunk-descriptor")
            end
            if type(summary.targetedCaptureSessionSummaryChunkKey) ~= "string"
                or summary.targetedCaptureSessionSummaryChunkKey == "" then
                error("missing-summary-chunk-key")
            end
            if type(report.localPerformance) ~= "table"
                or type(report.localPerformance.packagingDiagnostics) ~= "table" then
                error("missing-packaging-diagnostics")
            end
            print(tostring(#parts), scanId, tostring(summary.targetedCaptureSessionSummaryEncodedLength), tostring(largest), report.localPerformance.packagingDiagnostics.status)
            """
        )
        parts = out.split()
        self.assertGreaterEqual(len(parts), 5)
        self.assertGreater(int(parts[0]), 2)
        self.assertTrue(parts[1].startswith("guid-"))
        self.assertGreater(int(parts[2]), 0)
        self.assertLessEqual(int(parts[3]), 105000)
        self.assertEqual(parts[4], "packaged")

    def test_prepare_parts_fragments_oversized_diagnostic_items_losslessly(self):
        out = run_luau_harness(
            """
            local hugeBlob = string.rep('\\"🔥', 32000)
            local hugeArray = {}
            for i = 1, 1800 do
                hugeArray[i] = {index = i, token = "α" .. tostring(i), note = string.rep("q", 48)}
            end
            local report = {
                version = "30.6.68",
                placeId = 3623096087,
                gameId = 333,
                placeVersion = 1,
                inspectedAt = "2026-11-14T00:00:00Z",
                gameName = "PackagingRuntimeOversizedDiagnostic",
                counts = {},
                groups = {},
                scanStats = {recorded = 2, complete = true},
                sessionId = "session-oversized-1",
                snapshotId = "snapshot-oversized-1",
                parentSnapshotId = nil,
                featureEvidence = {},
                featureReadiness = {},
                featureSnapshotDelta = {},
                automationDiagnostics = {},
                diagnostics = {complete = true},
                objects = {
                    {path = "Workspace.A", class = "Part", scanOrdinal = 1},
                    {path = "Workspace.B", class = "Part", scanOrdinal = 2},
                },
                interactionDiagnostics = {
                    recentInteractions = {},
                    clickTargetObservations = {
                        {
                            sampleType = "click-target",
                            path = "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Selected.Action.Button",
                            payload = hugeBlob,
                            nested = {
                                largeArray = hugeArray,
                                mirrored = {hugeBlob, hugeBlob},
                            },
                        },
                        {
                            sampleType = "click-target",
                            path = "LocalPlayer.PlayerGui.ScreenGui.Quests.Frame.Main.Prizes.Tabs.Playtime.Button",
                            payload = hugeBlob,
                            nested = {
                                largeArray = hugeArray,
                            },
                        },
                    },
                },
            }
            local partsA, scanA = prepareParts(report)
            local partsB, scanB = prepareParts(report)
            if scanA ~= scanB then error("scan-id-changed") end
            if #partsA ~= #partsB then error("fragmented-part-count-changed") end
            local largest = 0
            local markerHits = 0
            for _, body in ipairs(partsA) do
                if #body > largest then largest = #body end
                if #body > MAX_PART_BYTES then error("part-limit-exceeded") end
                if string.find(body, "30.6.interaction-diagnostics-item-fragment.1", 1, true) then
                    markerHits = markerHits + 1
                end
            end
            local metrics = report.localPerformance and report.localPerformance.packagingDiagnostics or nil
            if type(metrics) ~= "table" then error("missing-packaging-metrics") end
            if type(metrics.fragmentedRecordCount) ~= "number" or metrics.fragmentedRecordCount < 2 then
                error("missing-fragmented-record-count")
            end
            if type(metrics.fragmentedRecordTotalFragments) ~= "number"
                or metrics.fragmentedRecordTotalFragments < metrics.fragmentedRecordCount then
                error("invalid-fragment-total")
            end
            if type(metrics.recordFragmentations) ~= "table" or #metrics.recordFragmentations < 1 then
                error("missing-record-fragmentation-diagnostics")
            end
            if type(metrics.recordFragmentations[1].fieldPath) ~= "string" then
                error("missing-record-fragment-path")
            end
            if type(metrics.recordFragmentations[1].encodedBytes) ~= "number"
                or metrics.recordFragmentations[1].encodedBytes <= MAX_PART_BYTES then
                error("encoded-bytes-not-captured")
            end
            print(
                tostring(#partsA),
                scanA,
                tostring(largest),
                tostring(metrics.fragmentedRecordCount),
                tostring(metrics.fragmentedRecordTotalFragments),
                tostring(markerHits)
            )
            """
        )
        parts = out.split()
        self.assertGreaterEqual(len(parts), 6)
        self.assertGreater(int(parts[0]), 3)
        self.assertTrue(parts[1].startswith("guid-"))
        self.assertLessEqual(int(parts[2]), 105000)
        self.assertGreaterEqual(int(parts[3]), 2)
        self.assertGreaterEqual(int(parts[4]), int(parts[3]))
        self.assertGreaterEqual(int(parts[5]), 1)

    def test_prepare_parts_keeps_boundary_sized_diagnostic_item_unfragmented(self):
        out = run_luau_harness(
            """
            local nearLimit = string.rep("a", 22000)
            local report = {
                version = "30.6.68",
                placeId = 3623096087,
                gameId = 334,
                placeVersion = 1,
                inspectedAt = "2026-11-14T00:00:00Z",
                gameName = "PackagingRuntimeBoundaryDiagnostic",
                counts = {},
                groups = {},
                scanStats = {recorded = 2, complete = true},
                sessionId = "session-boundary-1",
                snapshotId = "snapshot-boundary-1",
                parentSnapshotId = nil,
                featureEvidence = {},
                featureReadiness = {},
                featureSnapshotDelta = {},
                automationDiagnostics = {},
                diagnostics = {complete = true},
                objects = {
                    {path = "Workspace.A", class = "Part", scanOrdinal = 1},
                    {path = "Workspace.B", class = "Part", scanOrdinal = 2},
                },
                interactionDiagnostics = {
                    recentInteractions = {},
                    clickTargetObservations = {
                        {
                            sampleType = "click-target",
                            path = "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Selected.Action.Button",
                            payload = nearLimit,
                        },
                    },
                },
            }
            local parts, scanId = prepareParts(report)
            local markerHits = 0
            local largest = 0
            for _, body in ipairs(parts) do
                if #body > largest then largest = #body end
                if #body > MAX_PART_BYTES then error("part-limit-exceeded") end
                if string.find(body, "30.6.interaction-diagnostics-item-fragment.1", 1, true) then
                    markerHits = markerHits + 1
                end
            end
            local metrics = report.localPerformance and report.localPerformance.packagingDiagnostics or nil
            if type(metrics) ~= "table" then error("missing-packaging-metrics") end
            print(tostring(#parts), scanId, tostring(largest), tostring(metrics.fragmentedRecordCount), tostring(markerHits))
            """
        )
        parts = out.split()
        self.assertGreaterEqual(len(parts), 5)
        self.assertGreaterEqual(int(parts[0]), 1)
        self.assertTrue(parts[1].startswith("guid-"))
        self.assertLessEqual(int(parts[2]), 105000)
        self.assertEqual(int(parts[3]), 0)
        self.assertEqual(int(parts[4]), 0)

    def test_prepare_parts_keeps_normal_summary_inline_and_deterministic(self):
        out = run_luau_harness(
            """
            local report = {
                version = "30.6.68",
                placeId = 3623096087,
                gameId = 222,
                placeVersion = 1,
                inspectedAt = "2026-11-13T00:00:00Z",
                gameName = "PackagingRuntimeSmall",
                counts = {},
                groups = {},
                scanStats = {recorded = 2, complete = true},
                sessionId = "session-2",
                snapshotId = "snapshot-2",
                parentSnapshotId = nil,
                featureEvidence = {},
                featureReadiness = {},
                featureSnapshotDelta = {},
                automationDiagnostics = {},
                diagnostics = {complete = true},
                objects = {
                    {path = "Workspace.A", class = "Part", scanOrdinal = 1},
                    {path = "Workspace.B", class = "Part", scanOrdinal = 2},
                },
                interactionDiagnostics = {
                    recentInteractions = {},
                    targetedCaptureSessionSummary = {
                        schemaVersion = "31.0.targeted-evidence-session.1",
                        sessionId = "targeted-session-2",
                        requestProgress = {
                            ["combat-camera-weapon-correlation"] = {status = "collecting"},
                        },
                    },
                },
            }
            local partsA, scanA, summaryA = prepareParts(report)
            local partsB, scanB, summaryB = prepareParts(report)
            if scanA ~= scanB then error("scan-id-changed") end
            if #partsA ~= #partsB then error("part-count-changed") end
            if partsA[1] ~= partsB[1] then error("part-order-not-deterministic") end
            if summaryA.targetedCaptureSessionSummaryExportMode ~= nil then
                error("unexpected-summary-externalization")
            end
            local largest = 0
            for _, body in ipairs(partsA) do
                if #body > largest then largest = #body end
                if #body > MAX_PART_BYTES then error("part-limit-exceeded") end
            end
            print(tostring(#partsA), scanA, tostring(largest))
            """
        )
        parts = out.split()
        self.assertGreaterEqual(len(parts), 3)
        self.assertGreaterEqual(int(parts[0]), 1)
        self.assertTrue(parts[1].startswith("guid-"))
        self.assertLessEqual(int(parts[2]), 105000)


if __name__ == "__main__":
    unittest.main()
