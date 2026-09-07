import json
import time
import urllib.error
import urllib.request

from backend.app.models.incident import (
    Incident,
    IncidentAnalysis,
)


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma3:4b-it-q4_K_M"


SYSTEM_PROMPT = """
You are AegisAI, an AI DevOps incident investigation assistant.

Analyze infrastructure and application incidents using ONLY the
evidence provided by the user.

Return valid JSON only.

Do not use Markdown.
Do not use code fences.
Do not add explanations outside the JSON object.

Your response MUST follow this structure:

{
  "severity": "low|medium|high|critical",
  "root_cause": "string",
  "confidence": 0.0,
  "evidence": [
    "string"
  ],
  "next_checks": [
    "string"
  ],
  "remediation": {
    "action": "string",
    "risk": "low|medium|high|critical",
    "requires_approval": true
  }
}

Rules:

1. confidence must be between 0 and 1.
2. Evidence must come only from the incident information provided.
3. Never invent logs, metrics, events, configuration, or infrastructure state.
4. If information is missing, identify what needs to be checked.
5. Infrastructure-changing actions should normally require approval.
6. Never claim that a remediation was executed.
7. You are proposing an action, not executing it.
"""


def ask_gemma(incident: Incident) -> IncidentAnalysis:
    """
    Send a validated Incident to Gemma and return a validated
    IncidentAnalysis.
    """

    incident_json = incident.model_dump_json(indent=2)

    user_prompt = f"""
Analyze the following DevOps incident:

{incident_json}
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
        "format": "json",
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
        with urllib.request.urlopen(request, timeout=120) as response:
            response_data = response.read().decode("utf-8")

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to Ollama at {OLLAMA_URL}.\n"
            f"Make sure the Ollama service is running.\n"
            f"Error: {error}"
        ) from error

    elapsed = time.perf_counter() - start_time

    try:
        ollama_response = json.loads(response_data)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Ollama returned an invalid HTTP response."
        ) from error

    raw_content = ollama_response.get("message", {}).get("content", "")

    if not raw_content:
        raise RuntimeError("Gemma returned an empty response.")

    try:
        analysis = IncidentAnalysis.model_validate_json(raw_content)
    except Exception as error:
        raise RuntimeError(
            "Gemma returned JSON that does not match the "
            "IncidentAnalysis schema.\n\n"
            f"Gemma response:\n{raw_content}"
        ) from error

    print(f"\nInference time: {elapsed:.2f} seconds")

    return analysis


def main():
    incident = Incident(
        service="payment-service",
        environment="Kubernetes",
        status="CrashLoopBackOff",
        recent_log="Database connection refused on port 5432",
    )

    print("=" * 60)
    print("AegisAI - Gemma + Pydantic")
    print("=" * 60)

    print("\nIncident:")
    print(incident.model_dump_json(indent=2))

    print("\nSending incident to local Gemma...")

    analysis = ask_gemma(incident)

    print("\nValidated Incident Analysis:")
    print("-" * 60)
    print(analysis.model_dump_json(indent=2))
    print("-" * 60)

    print("\nValidated Python objects:")
    print(f"Severity: {analysis.severity}")
    print(f"Confidence: {analysis.confidence}")
    print(f"Root cause: {analysis.root_cause}")
    print(f"Evidence count: {len(analysis.evidence)}")
    print(f"Next checks: {len(analysis.next_checks)}")
    print(f"Remediation risk: {analysis.remediation.risk}")
    print(
        f"Requires approval: "
        f"{analysis.remediation.requires_approval}"
    )


if __name__ == "__main__":
    main()
