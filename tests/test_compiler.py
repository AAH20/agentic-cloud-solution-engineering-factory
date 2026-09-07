import copy
import json
import unittest
from pathlib import Path

from solution_factory.compiler import ContractError, compile_engagement
from solution_factory.qualification import QualificationError, qualify


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

    def test_partial_opportunity_requires_clarification(self):
        payload=json.loads((FIXTURE.parent/"azure-migration-opportunity.json").read_text())
        result=qualify(payload)
        self.assertEqual(result["decision"],"CLARIFY")
        self.assertEqual(result["qualification_score"],85.0)
        self.assertEqual(len(result["customer_questions"]),2)

    def test_complete_opportunity_is_pursued(self):
        payload=json.loads((FIXTURE.parent/"azure-migration-opportunity.json").read_text())
        for item in payload["criteria"].values(): item["state"]="confirmed"
        result=qualify(payload)
        self.assertEqual(result["decision"],"PURSUE")
        self.assertEqual(result["qualification_score"],100.0)

    def test_failed_hard_gate_declines_opportunity(self):
        payload=json.loads((FIXTURE.parent/"azure-migration-opportunity.json").read_text())
        payload["criteria"]["commercial_fit"]={"state":"failed","evidence":"Below minimum margin policy"}
        result=qualify(payload)
        self.assertEqual(result["decision"],"DECLINE")
        self.assertIn("commercial_fit",result["failed_hard_gates"])

    def test_unknown_criterion_is_rejected(self):
        payload=json.loads((FIXTURE.parent/"azure-migration-opportunity.json").read_text())
        payload["criteria"]["luck"]={"state":"confirmed"}
        with self.assertRaisesRegex(QualificationError,"unknown criteria"):
            qualify(payload)


if __name__ == "__main__":
    unittest.main()
