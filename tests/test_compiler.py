import copy
import json
import unittest
from pathlib import Path

from solution_factory.compiler import ContractError, compile_engagement


FIXTURE = Path(__file__).parents[1] / "examples" / "vmware-to-azure-ai-platform.json"


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())

    def test_selects_qualified_highest_scoring_option(self):
        result = compile_engagement(self.payload)
        self.assertEqual(result["selected_option"], "azure-modernized")
        self.assertEqual(result["status"], "qualified")

    def test_every_requirement_is_traceable(self):
        result = compile_engagement(self.payload)
        self.assertEqual(len(result["traceability"]), len(self.payload["requirements"]))
        self.assertTrue(result["hard_gates"]["every_requirement_traceable"])

    def test_rejects_missing_traceability(self):
        payload = copy.deepcopy(self.payload)
        del payload["traceability"]["NET-001"]
        with self.assertRaisesRegex(ContractError, "NET-001"):
            compile_engagement(payload)

    def test_rejects_when_no_option_covers_must_requirements(self):
        payload = copy.deepcopy(self.payload)
        for option in payload["options"]:
            option["supported_requirements"] = []
        with self.assertRaisesRegex(ContractError, "no architecture option"):
            compile_engagement(payload)

    def test_economics_are_deterministic(self):
        first = compile_engagement(self.payload)
        second = compile_engagement(self.payload)
        self.assertEqual(first["economics"], second["economics"])
        self.assertEqual(first["evidence_digest"], second["evidence_digest"])
        self.assertGreater(first["economics"]["year_one_roi_percent"], 0)

    def test_rejects_weights_that_do_not_total_one(self):
        payload = copy.deepcopy(self.payload)
        payload["weights"]["security"] = 0.9
        with self.assertRaisesRegex(ContractError, "weights"):
            compile_engagement(payload)


if __name__ == "__main__":
    unittest.main()
