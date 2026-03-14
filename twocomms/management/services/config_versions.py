from __future__ import annotations

from copy import deepcopy

from management.models import ManagementStatsConfig


DEFAULT_COMPONENT_WEIGHTS = {
    "result": 0.40,
    "source_fairness": 0.10,
    "process": 0.20,
    "follow_up": 0.10,
    "data_quality": 0.10,
    "verified_communication": 0.10,
}

DEFAULT_FEATURE_FLAGS = {
    "mosaic_shadow_enabled": True,
    "telephony_shadow_enabled": False,
    "dtf_bridge_enabled": False,
    "admin_analytics_enabled": True,
}

DEFAULT_FORMULA_DEFAULTS = {
    "formula_version": "mosaic-v1",
    "defaults_version": "2026-03-13",
    "snapshot_schema_version": "v1",
    "payload_version": "v1",
    "rollout_state": "shadow",
}

DEFAULT_MOSAIC_CONFIG = {
    "weights": DEFAULT_COMPONENT_WEIGHTS,
    "evidence_gates": {
        "paid": 100,
        "admin_confirmed": 78,
        "crm_timestamped": 60,
        "self_reported": 45,
    },
    "trust_bounds": {"min": 0.85, "max": 1.05},
    "dampener": {
        "weak_axis_threshold": 0.45,
        "one_weak": 0.94,
        "two_weak": 0.88,
        "many_weak": 0.82,
    },
}

DEFAULT_PAYROLL_CONFIG = {
    "commission_rates": {
        "new": 0.025,
        "repeat": 0.05,
        "reactivation": 0.035,
        "rescue_spiff_min": 500,
        "rescue_spiff_max": 2000,
    },
    "soft_floor": {
        "target_new_clients": 1,
        "cap_amount": 120000,
    },
    "appeal_sla_hours": {
        "score": 48,
        "freeze": 24,
    },
}

DEFAULT_FORECAST_CONFIG = {
    "aging_multipliers": {
        "within_sla": 1.0,
        "double_sla": 0.85,
        "older": 0.65,
    },
    "payback_thresholds": {
        "safe": 1.25,
        "watch": 1.0,
    },
}

DEFAULT_TELEPHONY_CONFIG = {
    "health_thresholds": {
        "unmatched_ratio_warn": 0.15,
        "backlog_warn": 5,
        "missing_recording_warn": 0.20,
    },
    "meaningful_call_seconds": 30,
}

DEFAULT_UI_CONFIG = {
    "quiet_hours": {"start": 21, "end": 8},
    "max_followups_per_day": 25,
    "duplicate_queue_warn": 5,
    "manager_timezone": "Europe/Kiev",
}

DEFAULT_VALIDATION_STATE = {
    "state": "shadow_window_open",
    "dice_checkpoint_days": 14,
    "last_material_change_version": "mosaic-v1",
    "window_reset_required": False,
}


def merged_dict(base: dict, override: dict | None) -> dict:
    result = deepcopy(base)
    override = override or {}
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merged_dict(result[key], value)
        else:
            result[key] = value
    return result


def get_management_config(config: ManagementStatsConfig | None = None) -> dict:
    config = config or ManagementStatsConfig.objects.filter(pk=1).first()
    if not config:
        return {
            "feature_flags": deepcopy(DEFAULT_FEATURE_FLAGS),
            "formula_defaults": deepcopy(DEFAULT_FORMULA_DEFAULTS),
            "mosaic_config": deepcopy(DEFAULT_MOSAIC_CONFIG),
            "payroll_config": deepcopy(DEFAULT_PAYROLL_CONFIG),
            "forecast_config": deepcopy(DEFAULT_FORECAST_CONFIG),
            "telephony_config": deepcopy(DEFAULT_TELEPHONY_CONFIG),
            "ui_config": deepcopy(DEFAULT_UI_CONFIG),
            "validation_state": deepcopy(DEFAULT_VALIDATION_STATE),
            "legacy_kpd_formula_version": "kpd-v1",
            "shadow_mosaic_formula_version": DEFAULT_FORMULA_DEFAULTS["formula_version"],
        }

    return {
        "feature_flags": merged_dict(DEFAULT_FEATURE_FLAGS, config.feature_flags),
        "formula_defaults": merged_dict(DEFAULT_FORMULA_DEFAULTS, config.formula_defaults),
        "mosaic_config": merged_dict(DEFAULT_MOSAIC_CONFIG, config.mosaic_config),
        "payroll_config": merged_dict(DEFAULT_PAYROLL_CONFIG, config.payroll_config),
        "forecast_config": merged_dict(DEFAULT_FORECAST_CONFIG, config.forecast_config),
        "telephony_config": merged_dict(DEFAULT_TELEPHONY_CONFIG, config.telephony_config),
        "ui_config": merged_dict(DEFAULT_UI_CONFIG, config.ui_config),
        "validation_state": merged_dict(DEFAULT_VALIDATION_STATE, config.validation_state),
        "legacy_kpd_formula_version": config.legacy_kpd_formula_version or "kpd-v1",
        "shadow_mosaic_formula_version": config.shadow_mosaic_formula_version or DEFAULT_FORMULA_DEFAULTS["formula_version"],
    }
