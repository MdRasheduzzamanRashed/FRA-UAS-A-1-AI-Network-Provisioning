"""Network intent: the structured form of a natural-language provisioning request.

The LLM never writes config files directly. It fills in a NetworkIntent (JSON),
which is checked here before any tool touches the network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

# Default test credentials from the template (configs/basic/ueransim/ue.yaml)
DEFAULT_KEY = "00000000000000000000000000000000"
DEFAULT_OPC = "00000000000000000000000000000000"


class IntentError(ValueError):
    """Raised when a request cannot be turned into a valid network."""


@dataclass
class UE:
    imsi: str                      # 15 digits, without the "imsi-" prefix
    apn: str = "internet"          # = DNN
    sst: int = 1
    sd: int = 1
    key: str = DEFAULT_KEY
    opc: str = DEFAULT_OPC


@dataclass
class NetworkIntent:
    name: str = "net1"
    mcc: str = "001"
    mnc: str = "01"
    tac: int = 1
    ue_subnet: str = "10.45.0.0/16"
    ues: list[UE] = field(default_factory=list)

    # ---------- construction ----------
    @classmethod
    def from_dict(cls, d: dict) -> "NetworkIntent":
        ues = [UE(**u) for u in d.get("ues", [])]
        fields = {k: v for k, v in d.items() if k != "ues"}
        intent = cls(**fields, ues=ues)
        intent.validate()
        return intent

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def slices(self) -> list[tuple[int, int]]:
        """All distinct (sst, sd) pairs requested by the UEs, in order."""
        seen: list[tuple[int, int]] = []
        for ue in self.ues:
            if (ue.sst, ue.sd) not in seen:
                seen.append((ue.sst, ue.sd))
        return seen or [(1, 1)]

    # ---------- validation ----------
    def validate(self) -> None:
        errors: list[str] = []
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", self.name):
            errors.append(f"name '{self.name}' must be lowercase letters, digits or '-'")
        if not re.fullmatch(r"\d{3}", str(self.mcc)):
            errors.append(f"MCC '{self.mcc}' must be exactly 3 digits")
        if not re.fullmatch(r"\d{2,3}", str(self.mnc)):
            errors.append(f"MNC '{self.mnc}' must be 2 or 3 digits")
        if not (0 < int(self.tac) < 2**24):
            errors.append(f"TAC {self.tac} out of range (1..16777215)")
        if not self.ues:
            errors.append("at least one UE is required")
        if len(self.ues) > 10:
            errors.append("at most 10 UEs are supported in this prototype")

        plmn = f"{self.mcc}{self.mnc}"
        imsis = set()
        for i, ue in enumerate(self.ues, 1):
            if not re.fullmatch(r"\d{15}", ue.imsi):
                errors.append(f"UE{i}: IMSI '{ue.imsi}' must be 15 digits")
            elif not ue.imsi.startswith(plmn):
                errors.append(f"UE{i}: IMSI {ue.imsi} does not start with the network PLMN {plmn} (MCC+MNC)")
            if ue.imsi in imsis:
                errors.append(f"UE{i}: duplicate IMSI {ue.imsi}")
            imsis.add(ue.imsi)
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,63}", ue.apn):
                errors.append(f"UE{i}: APN/DNN '{ue.apn}' is invalid")
            if not (0 < int(ue.sst) < 256):
                errors.append(f"UE{i}: SST {ue.sst} out of range (1..255)")
            for label, val in (("key", ue.key), ("opc", ue.opc)):
                if not re.fullmatch(r"[0-9a-fA-F]{32}", val):
                    errors.append(f"UE{i}: {label} must be 32 hex characters")
        if errors:
            raise IntentError("; ".join(errors))
