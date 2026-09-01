from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "data" / "output" / "it_skills_engine_validation_report.json"
RUNNER_PATH = PROJECT_ROOT / "run_it_skills_engine_validation.py"


class ItSkillsEngineE2ETests(unittest.TestCase):
    def test_it_skills_engine_package_validation_passes(self):
        if not REPORT_PATH.exists():
            completed = subprocess.run(
                [sys.executable, str(RUNNER_PATH)],
                cwd=PROJECT_ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + "\n" + completed.stderr,
            )

        report = json.loads(REPORT_PATH.read_text(encoding="utf8"))

        self.assertEqual(report["overall_package_status"], "PASS", report.get("defects"))
        self.assertEqual(report["slides_generated"], 8)
        self.assertEqual(report["duplicate_zip_entries"], 0)

        package = report["package_validation"]
        self.assertEqual(package["prompt_leaks"], [])
        self.assertTrue(package["image"]["found"])
        self.assertTrue(package["table"]["found"])
        self.assertEqual(package["table"]["missing_text"], [])
        self.assertTrue(package["chart"]["found"])
        self.assertEqual(package["chart"]["missing_text"], [])
        self.assertEqual(package["chart"]["missing_values"], [])

        # Visual chart rendering is intentionally not asserted from OOXML alone.
        # The report must explicitly require manual visual review for slide 5.
        self.assertEqual(report["visual_validation"]["status"], "REQUIRES_MANUAL_REVIEW")


if __name__ == "__main__":
    unittest.main()
