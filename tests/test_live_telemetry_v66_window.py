import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from live_telemetry_v66 import generate

class TestV66Window(unittest.TestCase):
    def test_drag_support(self):
        s=generate(85896571713843)
        self.assertIn('UserInputService.InputChanged:Connect',s)
        self.assertIn('title.InputBegan:Connect',s)
        self.assertIn('panel.Position=UDim2.new',s)
    def test_minimize_restore(self):
        s=generate(85896571713843)
        self.assertIn('minimize.MouseButton1Click:Connect(toggleMinimize)',s)
        self.assertIn('minimize.Text=minimized and "+" or "-"',s)
        self.assertIn('control.Visible=not minimized',s)
        self.assertIn('content={filter,export,status,scroll}',s)
    def test_sampling_not_suspended(self):
        s=generate(85896571713843)
        self.assertIn('while gui.Parent do',s)
        self.assertIn('pcall(sample)',s)
        self.assertNotIn('if not minimized then sample()',s)
if __name__=="__main__": unittest.main()
