"""Shared contracts for the management statistics decision cockpit."""

STATS_PERFORMANCE_BUDGETS = {
    "max_sql_queries": 20,
    "max_materialized_message_rows": 2000,
    "max_serialized_payload_bytes": 350 * 1024,
    "local_benchmark_target_ms": 750,
}


def build_performance_contract(
    *,
    query_count,
    query_count_available,
    materialized_message_rows,
    serialized_payload_bytes,
):
    """Return measured request cost without hiding an exceeded budget."""
    measured = (
        query_count_available
        and query_count is not None
        and query_count > STATS_PERFORMANCE_BUDGETS["max_sql_queries"]
    )
    rows_exceeded = (
        materialized_message_rows
        > STATS_PERFORMANCE_BUDGETS["max_materialized_message_rows"]
    )
    payload_exceeded = (
        serialized_payload_bytes
        > STATS_PERFORMANCE_BUDGETS["max_serialized_payload_bytes"]
    )
    if measured or rows_exceeded or payload_exceeded:
        status = "needs_rollup"
    elif query_count_available:
        status = "within_budget"
    else:
        status = "unmeasured"
    return {
        "query_count": int(query_count) if query_count is not None else None,
        "query_count_available": bool(query_count_available),
        "materialized_message_rows": int(materialized_message_rows),
        "serialized_payload_bytes": int(serialized_payload_bytes),
        "budget_status": status,
        "budgets": dict(STATS_PERFORMANCE_BUDGETS),
    }
