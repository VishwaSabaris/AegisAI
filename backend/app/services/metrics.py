from prometheus_client import Counter, Gauge, Histogram


INCIDENTS_TOTAL = Counter(
    "aegisai_incidents_total",
    "Total number of incidents processed by AegisAI.",
    ["service", "severity"],
)

INCIDENTS_BY_STATE = Gauge(
    "aegisai_incidents_by_state",
    "Current number of persisted incidents by lifecycle state.",
    ["state"],
)

INVESTIGATION_DURATION_SECONDS = Histogram(
    "aegisai_investigation_duration_seconds",
    "Time spent investigating an incident.",
)

LLM_INFERENCE_DURATION_SECONDS = Histogram(
    "aegisai_llm_inference_duration_seconds",
    "Time spent waiting for local LLM inference.",
)

REMEDIATION_ATTEMPTS_TOTAL = Counter(
    "aegisai_remediation_attempts_total",
    "Total remediation attempts.",
    ["action"],
)

REMEDIATION_RESULTS_TOTAL = Counter(
    "aegisai_remediation_results_total",
    "Total remediation results.",
    ["action", "result"],
)

RECOVERY_RESULTS_TOTAL = Counter(
    "aegisai_recovery_results_total",
    "Total recovery verification results.",
    ["status"],
)
