import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from solution_factory.private_inference import OfferError, compile_offer, render_deployment, write_offer


ROOT = Path(__file__).resolve().parents[1]
INTAKE = json.loads((ROOT / "examples/private-inference-intake.json").read_text())
BENCHMARK = json.loads((ROOT / "examples/private-inference-benchmark.synthetic.json").read_text())


class PrivateInferenceTests(unittest.TestCase):
    def test_synthetic_offer_is_draft_without_deployment(self):
        offer = compile_offer(INTAKE, BENCHMARK)
        self.assertEqual(offer["status"], "not_ready")
        self.assertEqual(offer["quote"]["monthly_total_cost_usd"], "1730.00")
        self.assertEqual(offer["quote"]["monthly_price_usd"], "2471.43")
        with TemporaryDirectory() as directory:
            write_offer(offer, Path(directory))
            self.assertTrue((Path(directory) / "proposal.md").exists())
            self.assertFalse((Path(directory) / "deployment.yaml").exists())

    def test_operator_supplied_passing_measurement_creates_handoff(self):
        benchmark = {**BENCHMARK, "provenance": "operator_supplied_measurement"}
        offer = compile_offer(INTAKE, benchmark)
        self.assertEqual(offer["status"], "review_required")
        self.assertTrue(all(offer["acceptance_gates"].values()))
        manifest = render_deployment(offer)
        self.assertIn("Qwen/Qwen3-0.6B", manifest)
        self.assertIn("type: ClusterIP", manifest)

    def test_failed_measurement_blocks_deployment(self):
        benchmark = {**BENCHMARK, "provenance": "operator_supplied_measurement", "failed": 1, "succeeded": 29}
        offer = compile_offer(INTAKE, benchmark)
        self.assertEqual(offer["status"], "not_ready")
        with self.assertRaises(OfferError):
            render_deployment(offer)

    def test_mismatch_and_multigpu_rejected(self):
        with self.assertRaisesRegex(OfferError, "schema/model"):
            compile_offer(INTAKE, {**BENCHMARK, "model": "other"})
        bad = {**INTAKE, "costs": {**INTAKE["costs"], "gpu_count": 2}}
        with self.assertRaisesRegex(OfferError, "one GPU"):
            compile_offer(bad, BENCHMARK)


if __name__ == "__main__":
    unittest.main()
