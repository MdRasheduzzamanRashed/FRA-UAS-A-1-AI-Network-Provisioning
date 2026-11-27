"""Offline tests: config generation, validation and tool safety. No Docker needed.

Run:  python -m pytest tests/ -q      (or: python -m unittest discover tests)
"""
import json
import os
import shutil
import unittest
from pathlib import Path

os.environ["PROVISION_DRY_RUN"] = "1"

import yaml  # noqa: E402


def load(p):
    with open(p) as f:
        return yaml.safe_load(f)


def save(d, p):
    with open(p, "w") as f:
        yaml.safe_dump(d, f)

from src.provisioning import configgen, tools  # noqa: E402
from src.provisioning.intent import IntentError, NetworkIntent  # noqa: E402

TWO_UES = json.loads((Path(__file__).parent / "intents" / "two_ues.json").read_text())


class ConfigGenTest(unittest.TestCase):
    def tearDown(self):
        for name in ("two-ues", "plmn-test", "slices", "broken"):
            shutil.rmtree(configgen.GEN_CONFIGS / name, ignore_errors=True)
            shutil.rmtree(configgen.GEN_COMPOSE / name, ignore_errors=True)

    def test_generate_and_validate(self):
        res = configgen.create_config(NetworkIntent.from_dict(TWO_UES))
        self.assertEqual(res["ues"], ["ue1", "ue2"])
        v = configgen.validate_config("two-ues")
        self.assertTrue(v["ok"], v["errors"])

    def test_compose_has_one_service_per_ue(self):
        configgen.create_config(NetworkIntent.from_dict(TWO_UES))
        compose = load(configgen.paths_for("two-ues")[1])
        self.assertIn("ue1", compose["services"])
        self.assertIn("ue2", compose["services"])
        self.assertNotIn("ue", compose["services"])

    def test_plmn_keeps_leading_zeros(self):
        configgen.create_config(NetworkIntent.from_dict(
            {"name": "plmn-test", "mcc": "999", "mnc": "070", "tac": 7,
             "ues": [{"imsi": "999070000000001"}]}))
        cfg = configgen.paths_for("plmn-test")[0]
        amf = load(cfg / "amf.yaml")["amf"]
        self.assertEqual(amf["tai"][0]["plmn_id"]["mnc"], "070")
        self.assertEqual(load(cfg / "gnb.yaml")["tac"], 7)
        self.assertTrue(configgen.validate_config("plmn-test")["ok"])

    def test_two_slices(self):
        configgen.create_config(NetworkIntent.from_dict(
            {"name": "slices", "ues": [{"imsi": "001010000000001", "sd": 1},
                                       {"imsi": "001010000000002", "sd": 2}]}))
        v = configgen.validate_config("slices")
        self.assertTrue(v["ok"], v["errors"])

    def test_validator_detects_tac_mismatch(self):
        configgen.create_config(NetworkIntent.from_dict({**TWO_UES, "name": "broken"}))
        gnb_path = configgen.paths_for("broken")[0] / "gnb.yaml"
        gnb = load(gnb_path)
        gnb["tac"] = 99                                   # inject a fault
        save(gnb, gnb_path)
        v = configgen.validate_config("broken")
        self.assertFalse(v["ok"])
        self.assertTrue(any("TAC" in e for e in v["errors"]))

    def test_validator_detects_plmn_mismatch_in_ue(self):
        configgen.create_config(NetworkIntent.from_dict({**TWO_UES, "name": "broken"}))
        ue_path = configgen.paths_for("broken")[0] / "ue2.yaml"
        ue = load(ue_path)
        ue["mcc"] = "262"
        save(ue, ue_path)
        self.assertFalse(configgen.validate_config("broken")["ok"])


class IntentTest(unittest.TestCase):
    def test_rejects_foreign_imsi(self):
        with self.assertRaises(IntentError):
            NetworkIntent.from_dict({"ues": [{"imsi": "262011234567890"}]})

    def test_rejects_short_imsi(self):
        with self.assertRaises(IntentError):
            NetworkIntent.from_dict({"ues": [{"imsi": "12345"}]})

    def test_rejects_too_many_ues(self):
        ues = [{"imsi": f"0010100000000{i:02d}"} for i in range(11)]
        with self.assertRaises(IntentError):
            NetworkIntent.from_dict({"ues": ues})


class ToolSafetyTest(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree(configgen.GEN_CONFIGS / "two-ues", ignore_errors=True)
        shutil.rmtree(configgen.GEN_COMPOSE / "two-ues", ignore_errors=True)

    def test_unknown_container_is_refused(self):
        tools.create_config(TWO_UES)
        with self.assertRaises(ValueError):
            tools.get_logs("; rm -rf /")

    def test_scripted_pipeline_dry_run(self):
        from src.provisioning.agent import run_scripted
        tools.COMMAND_LOG.clear()
        r = run_scripted(TWO_UES)
        # In dry-run there are no real UE logs, so only the steps up to start_ran can succeed.
        setup = [s for s in r["steps"] if s["tool"] not in ("get_ue_status", "test_connectivity")]
        self.assertTrue(all(s["ok"] for s in setup), setup)
        cmds = [" ".join(c) for c in tools.COMMAND_LOG]
        self.assertTrue(any("add_ue_with_slice 001010000000002" in c for c in cmds))
        self.assertTrue(any("up -d gnb ue1 ue2" in c for c in cmds))


if __name__ == "__main__":
    unittest.main()
