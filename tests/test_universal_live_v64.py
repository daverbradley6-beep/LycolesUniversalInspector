import tempfile, unittest, pathlib, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from universal_live_v64 import generate

class TestV64(unittest.TestCase):
    def test_generation(self):
        src=generate(85896571713843)
        self.assertIn('game.PlaceId~=85896571713843',src)
        self.assertIn('task.wait(3)',src)
        self.assertIn('MAX_ROWS=200',src)
        self.assertNotIn('__PLACE__',src)

    def test_no_remote_invocation(self):
        src=generate(123)
        for x in ('FireServer(', 'InvokeServer(', 'firetouchinterest(', 'getgc(', 'getconnections('):
            self.assertNotIn(x,src)

    def test_invalid_place(self):
        for x in (0,-1,True,'123'):
            with self.assertRaises(ValueError):generate(x)

    def test_invalid_limit(self):
        for x in (0,501,True):
            with self.assertRaises(ValueError):generate(123,x)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable,str(pathlib.Path(__file__).resolve().parents[1]/'tools'/'universal_live_v64.py'),
                            '--place-id','123','--output',d],check=True,capture_output=True)
            self.assertTrue((pathlib.Path(d)/'live-observer-v64.luau').exists())
            self.assertTrue((pathlib.Path(d)/'release-manifest-v64.json').exists())

if __name__=='__main__':unittest.main()
