"""vuln_chain circuit — toy pattern check for IDOR+auth findings (scaffold, not CVE DB)."""
from __future__ import annotations


class VulnChainCircuit:
    name = "vuln_chain"

    @staticmethod
    def verify(public_inputs: dict, private_witness: dict) -> dict:
        findings = private_witness.get("findings", [])
        if len(findings) < 3:
            return {"critical": False, "reason": "need >=3 findings"}
        types = [str(f.get("type", "")).lower() for f in findings]
        has_idor = any("idor" in t for t in types)
        has_auth = any("auth" in t or "bypass" in t for t in types)
        if not (has_idor and has_auth):
            return {"critical": False, "reason": "chain pattern not matched"}
        # optional cvss band check when present
        for f in findings:
            cvss = f.get("cvss")
            if cvss is not None and not (4.0 <= float(cvss) <= 6.9):
                return {"critical": False, "reason": f"cvss out of med band: {cvss}"}
        return {"critical": True, "reason": "ok", "chain_type": "idor+auth"}

    @staticmethod
    def get_statement(public_inputs: dict, critical: bool) -> dict:
        return {
            "chain_id": public_inputs.get("chain_id"),
            "findings_hash": public_inputs.get("findings_hash"),
            "critical": critical,
        }
