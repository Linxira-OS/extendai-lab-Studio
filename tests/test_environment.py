import unittest
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from abris.environment.detector import EnvironmentDetector


class EnvironmentDetectorTest(unittest.TestCase):
    def test_environment_detector_returns_snapshot(self) -> None:
        detector = EnvironmentDetector(tools=[], python_modules=["json"], r_packages=[])
        snapshot = detector.detect()

        self.assertTrue(snapshot.python_version)
        self.assertGreaterEqual(snapshot.cpu_count, 1)
        self.assertIn("json", snapshot.available_python_modules)


if __name__ == "__main__":
    unittest.main()
