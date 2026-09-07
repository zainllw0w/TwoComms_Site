"""Editable shooting-prize programme snapshot and fail-closed observation rules."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from management.models import BotInstruction


PROGRAMME_ID = "shooting_prize"
RESERVED_INTENT_TAG = "programme:shooting_prize"
PRIZE_STATUSES = frozenset({"recognized", "uncertain", "not_match"})
PRIZE_CUE_CODES = frozenset({
    "shooting_target", "shooting_range", "prize_certificate_layout", "programme_mark",
})
PRIZE_REASON_CODES = frozenset({
    "visible_programme_cues", "insufficient_detail", "foreign_certificate", "not_prize",
})


@dataclass(frozen=True)
class PrizeProgramme:
    programme_id: str
    version: str
    instruction: str
    cue_codes: tuple[str, ...]
    manager_required: bool = True
    confirmed_visual_sample: bool = False

    def prompt_snapshot(self) -> dict:
        return {
            "programme_id": self.programme_id,
            "version": self.version,
            "instruction": self.instruction,
            "cue_codes": list(self.cue_codes),
            "manager_required": True,
            "confirmed_visual_sample": False,
        }


@dataclass(frozen=True)
class PrizeCertificateObservation:
    programme_id: str
    programme_version: str
    status: str
    cue_codes: tuple[str, ...]
    reason_code: str
    manager_required: bool = True

    def public_value(self) -> dict:
        return {
            "programme_id": self.programme_id,
            "programme_version": self.programme_version,
            "status": self.status,
            "cue_codes": list(self.cue_codes),
            "reason_code": self.reason_code,
            "manager_required": True,
        }


def _instruction_tags(value: str) -> set[str]:
    return {
        item.strip().casefold()
        for item in str(value or "").replace(";", ",").split(",")
        if item.strip()
    }


def _version_for(instruction: BotInstruction) -> str:
    payload = {
        "title": str(instruction.title or ""),
        "body": str(instruction.body or ""),
        "intent_tags": str(instruction.intent_tags or ""),
        "priority": int(instruction.priority),
        "is_active": bool(instruction.is_active),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def active_shooting_prize_programme() -> PrizeProgramme | None:
    """Return exactly one enabled programme, never guessing from a title."""
    matches = [
        instruction
        for instruction in BotInstruction.objects.filter(is_active=True).order_by("priority", "id")
        if RESERVED_INTENT_TAG in _instruction_tags(instruction.intent_tags)
        and str(instruction.body or "").strip()
    ]
    if len(matches) != 1:
        return None
    instruction = matches[0]
    return PrizeProgramme(
        programme_id=PROGRAMME_ID,
        version=_version_for(instruction),
        instruction=str(instruction.body).strip(),
        cue_codes=tuple(sorted(PRIZE_CUE_CODES)),
    )


def conditional_programme_snapshot() -> dict | None:
    programme = active_shooting_prize_programme()
    return programme.prompt_snapshot() if programme else None


def validate_prize_observation(value, *, programme: PrizeProgramme | None):
    """Accept only one configured programme and a non-financial visual result."""
    if isinstance(value, PrizeCertificateObservation):
        value = value.public_value()
    if not isinstance(value, dict) or programme is None or set(value) != {
        "programme_id", "programme_version", "status", "cue_codes", "reason_code",
        "manager_required",
    }:
        return None
    if (
        value.get("programme_id") != programme.programme_id
        or value.get("programme_version") != programme.version
        or value.get("manager_required") is not True
    ):
        return None
    status = str(value.get("status") or "").strip().casefold()
    reason_code = str(value.get("reason_code") or "").strip().casefold()
    raw_cues = value.get("cue_codes")
    if (
        status not in PRIZE_STATUSES
        or reason_code not in PRIZE_REASON_CODES
        or not isinstance(raw_cues, list)
        or len(raw_cues) > len(PRIZE_CUE_CODES)
    ):
        return None
    cue_codes = tuple(str(code).strip().casefold() for code in raw_cues)
    if (
        len(cue_codes) != len(set(cue_codes))
        or not set(cue_codes).issubset(PRIZE_CUE_CODES)
        or not set(cue_codes).issubset(set(programme.cue_codes))
    ):
        return None
    if status == "not_match" and (cue_codes or reason_code not in {"foreign_certificate", "not_prize"}):
        return None
    if status in {"recognized", "uncertain"} and not cue_codes:
        return None
    # A programme without a separately verified visual sample cannot issue a
    # positive recognition. This producer never invents that later capability.
    if status == "recognized" and not programme.confirmed_visual_sample:
        status = "uncertain"
    return PrizeCertificateObservation(
        programme_id=programme.programme_id,
        programme_version=programme.version,
        status=status,
        cue_codes=cue_codes,
        reason_code=reason_code,
    )
