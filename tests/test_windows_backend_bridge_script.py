import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "windows_setup_lycoles_backend_bridge.ps1"


class WindowsBackendBridgeScriptTests(unittest.TestCase):
    def test_script_exists_and_targets_openhands_container(self):
        self.assertTrue(SCRIPT.is_file())
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('[string]$ContainerName = "openhands-app"', content)
        self.assertIn('[int]$BackendPort = 8787', content)

    def test_script_uses_non_destructive_sidecar_proxy_pattern(self):
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('docker rm -f $ProxyContainerName', content)
        self.assertIn('Invoke-Docker run -d', content)
        self.assertIn('--name $ProxyContainerName', content)
        self.assertIn('alpine/socat', content)
        self.assertIn('TCP:$ContainerName:$BackendPort', content)

    def test_script_supports_optional_shared_token_and_health_validation(self):
        content = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('LYCOLES_BACKEND_SHARED_TOKEN', content)
        self.assertIn('X-Lycoles-Backend-Token', content)
        self.assertIn('Invoke-RestMethod -Uri $healthUrl', content)


if __name__ == "__main__":
    unittest.main()
