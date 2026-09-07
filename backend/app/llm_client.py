import json
import time
import urllib.error
import urllib.request

from backend.app.models.evidence import InvestigationEvidence
from backend.app.models.incident import (
    Incident,
    IncidentAnalysis,
)


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma3:4b-it-q4_K_M"


SYSTEM_PROMPT = """
You are AegisAI, an AI DevOps incident investigation assistant.

Analyze infrastructure and application incidents using ONLY the
incident information and investigation evidence provided.

Return valid JSON only.

Do not use Markdown.
Do not use code fences.
Do not add explanations outside the JSON object.

Your response MUST follow the supplied JSON schema.

IMPORTANT REMEDIATION RULE:

The remediation.action field MUST contain exactly ONE of these
machine-readable action identifiers:

1. "restart_deployment"
2. "rollback_deployment"
3. "scale_deployment"

NEVER put a sentence, explanation, recommendation, or natural-language
description inside remediation.action.

For example, this is VALID:

{
  "remediation": {
    "action": "restart_deployment",
    "risk": "medium",
    "requires_approval": true
  }
}

This is INVALID:

{
  "remediation": {
    "action": "Investigate database connectivity issues and update the configuration.",
    "risk": "medium",
    "requires_approval": true
  }
}

If you believe that none of the supported remediation actions is
appropriate, choose the safest supported action based only on the
available evidence and explain the limitation in next_checks.

Rules:

1. confidence must be between 0 and 1.
2. Evidence must come only from the incident and investigation evidence.
3. Never invent logs, metrics, events, configuration, or infrastructure state.
4. If information is missing, identify what needs to be checked.
5. Infrastructure-changing actions should normally require approval.
6. Never claim that a remediation was executed.
7. You are proposing an action, not executing it.
8. Distinguish observed facts from hypotheses.
9. remediation.action must always be one of the supported machine-readable
   identifiers defined above.
"""


def ask_gemma(
    incident: Incident,
    evidence: InvestigationEvidence,
) -> IncidentAnalysis:
    """
    Send an incident and structured investigation evidence to Gemma.

    Gemma is constrained by the JSON schema generated from the
    IncidentAnalysis Pydantic model.
    """

    incident_json = incident.model_dump_json(indent=2)
    evidence_json = evidence.model_dump_json(indent=2)

    user_prompt = f"""
Analyze the following DevOps incident.

INCIDENT:
{incident_json}

INVESTIGATION EVIDENCE:
{evidence_json}

Remember:

remediation.action MUST be exactly one of:

- restart_deployment
- rollback_deployment
- scale_deployment

Do not write a sentence in remediation.action.
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        "format": IncidentAnalysis.model_json_schema(),
        "stream": False,
        "options": {
            "temperature": 0.1,
        },
    }

    request_data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=request_data,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    start_time = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            response_data = response.read().decode("utf-8")

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to Ollama at {OLLAMA_URL}.\n"
            "Make sure the Ollama service is running.\n"
            f"Error: {error}"
        ) from error

    elapsed = time.perf_counter() - start_time

    try:
        ollama_response = json.loads(response_data)

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Ollama returned an invalid HTTP response."
        ) from error

    raw_content = (
        ollama_response
        .get("message", {})
        .get("content", "")
    )

    if not raw_content:
        raise RuntimeError(
            "Gemma returned an empty response."
        )

    try:
        analysis = IncidentAnalysis.model_validate_json(
            raw_content
        )

    except Exception as error:
        raise RuntimeError(
            "Gemma returned JSON that does not match the "
            "IncidentAnalysis schema.\n\n"
            f"Gemma response:\n{raw_content}"
        ) from error

    print(
        f"\nInference time: {elapsed:.2f} seconds"
    )

    return analysis


def main():
    incident = Incident(
        service="payment-service",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log=(
            "Database connection refused on port 5432"
        ),
    )

    evidence = InvestigationEvidence(
        pod_status=None,
        pod_logs=None,
        kubernetes_events=None,
    )

    print("=" * 60)
    print("AegisAI - Gemma + Structured Evidence")
    print("=" * 60)

    print("\nIncident:")
    print(
        incident.model_dump_json(
            indent=2
        )
    )

    print("\nEvidence:")
    print(
        evidence.model_dump_json(
            indent=2
        )
    )

    print(
        "\nNote: This direct client test uses empty evidence."
    )


if __name__ == "__main__":
    main()
