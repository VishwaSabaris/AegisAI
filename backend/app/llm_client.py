import json
import time
import urllib.error
import urllib.request

from backend.app.agents.knowledge import KnowledgeAgent
from backend.app.models.evidence import InvestigationEvidence
from backend.app.models.incident import (
    Incident,
    IncidentAnalysis,
)


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "gemma3:4b-it-q4_K_M"

RAG_TOP_K = 3


SYSTEM_PROMPT = """
You are AegisAI, an AI DevOps incident investigation assistant.

Analyze infrastructure and application incidents using:

1. The incident information provided.
2. The investigation evidence provided.
3. The retrieved operational knowledge provided by the AegisAI
   knowledge base.

Return valid JSON only.

Do not use Markdown.
Do not use code fences.
Do not add explanations outside the JSON object.

Your response MUST follow the supplied JSON schema.

IMPORTANT DISTINCTION:

Investigation evidence represents observed infrastructure facts.

This includes:

- Pod status
- Pod readiness
- Restart counts
- Container state
- Application logs
- Kubernetes events
- Kubernetes Service existence
- Kubernetes Service ClusterIP
- Kubernetes Service ports
- Kubernetes Service endpoints

Retrieved knowledge represents operational guidance such as runbooks.
Retrieved knowledge is NOT proof that a particular infrastructure
condition exists.

Do not present information from the knowledge base as an observed fact
unless that fact is also supported by the investigation evidence.

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
2. Observed evidence must come only from the incident and investigation
   evidence.
3. Never invent logs, metrics, events, configuration, or infrastructure
   state.
4. Retrieved knowledge may be used to suggest checks or operational
   guidance, but must not be treated as observed infrastructure state.
5. If information is missing, identify what needs to be checked.
6. Infrastructure-changing actions should normally require approval.
7. Never claim that a remediation was executed.
8. You are proposing an action, not executing it.
9. Distinguish observed facts from hypotheses.
10. remediation.action must always be one of the supported
    machine-readable identifiers defined above.
11. Prefer remediation guidance supported by the retrieved runbook when
    it is relevant to the incident.
12. If a Kubernetes Service dependency is observed to be missing,
    explicitly consider that fact when determining the root cause.
"""


def _format_knowledge_context(
    results,
) -> str:
    """
    Convert retrieved RAG results into a compact prompt section.

    Similarity scores are included for observability, but the model
    must not treat the score itself as evidence.
    """

    if not results:
        return (
            "No relevant knowledge-base documents were retrieved."
        )

    sections: list[str] = []

    for index, result in enumerate(results, start=1):
        sections.append(
            f"""
KNOWLEDGE RESULT {index}

Source:
{result.source}

Title:
{result.title}

Similarity:
{result.similarity:.4f}

Content:
{result.content}
""".strip()
        )

    return "\n\n".join(sections)


def _build_observed_evidence(
    evidence: InvestigationEvidence,
) -> list[str]:
    """
    Convert validated investigation evidence into human-readable
    observed facts.

    This function is deterministic. It is intentionally independent
    of the LLM so that observed infrastructure facts cannot be
    discarded or invented by the model.
    """

    observed: list[str] = []

    if evidence.pod_status is not None:
        pod_status = evidence.pod_status

        observed.append(
            f"Pod {pod_status.pod} is in phase "
            f"{pod_status.phase}."
        )

        observed.append(
            f"Pod {pod_status.pod} ready status is "
            f"{pod_status.ready}."
        )

        observed.append(
            f"Pod {pod_status.pod} has restarted "
            f"{pod_status.restart_count} time(s)."
        )

        if pod_status.reason:
            observed.append(
                f"Pod {pod_status.pod} reports reason "
                f"{pod_status.reason}."
            )

        observed.append(
            f"Container status for pod {pod_status.pod}: "
            f"{pod_status.container_status}."
        )

    if evidence.pod_logs is not None:
        for log in evidence.pod_logs.logs:
            observed.append(
                f"Application log: {log}"
            )

    if evidence.kubernetes_events is not None:
        for event in evidence.kubernetes_events.events:
            observed.append(
                f"Kubernetes {event.type} event "
                f"{event.reason}: {event.message}"
            )

    if evidence.service_dependency is not None:
        dependency = evidence.service_dependency

        observed.append(
            f"Kubernetes Service {dependency.dependency} "
            f"exists: {dependency.exists}."
        )

        if dependency.cluster_ip:
            observed.append(
                f"Kubernetes Service "
                f"{dependency.dependency} ClusterIP: "
                f"{dependency.cluster_ip}."
            )

        if dependency.ports:
            observed.append(
                f"Kubernetes Service "
                f"{dependency.dependency} exposes ports: "
                f"{', '.join(dependency.ports)}."
            )

        if dependency.endpoints:
            observed.append(
                f"Kubernetes Service "
                f"{dependency.dependency} has endpoints: "
                f"{', '.join(dependency.endpoints)}."
            )
        else:
            observed.append(
                f"Kubernetes Service "
                f"{dependency.dependency} has no active endpoints."
            )

    return observed


def ask_gemma(
    incident: Incident,
    evidence: InvestigationEvidence,
) -> IncidentAnalysis:
    """
    Retrieve relevant operational knowledge and send the incident,
    investigation evidence, and RAG context to Gemma.

    Gemma produces a validated incident analysis but does not execute
    infrastructure-changing actions.

    Observed evidence in the final IncidentAnalysis is generated
    deterministically from the validated InvestigationEvidence rather
    than trusting the LLM to reproduce it.
    """

    knowledge_agent = KnowledgeAgent()

    knowledge_results = knowledge_agent.retrieve(
        query=(
            f"DevOps incident involving service "
            f"{incident.service}. "
            f"Current status: {incident.status}. "
            f"Recent log: {incident.recent_log}"
        ),
        limit=RAG_TOP_K,
    )

    knowledge_context = _format_knowledge_context(
        knowledge_results
    )

    incident_json = incident.model_dump_json(indent=2)
    evidence_json = evidence.model_dump_json(indent=2)

    user_prompt = f"""
Analyze the following DevOps incident.

INCIDENT:
{incident_json}

INVESTIGATION EVIDENCE:
{evidence_json}

RETRIEVED OPERATIONAL KNOWLEDGE:
{knowledge_context}

Use the retrieved operational knowledge as supporting guidance.

Important:

- Do not treat the knowledge-base content as direct evidence.
- Do not invent infrastructure facts from the runbook.
- Base the root cause primarily on the observed investigation evidence.
- Kubernetes Service existence and endpoint information are direct
  observed infrastructure evidence.
- If a required Kubernetes Service is observed to be missing, explicitly
  consider that missing Service as a likely root-cause factor.
- Use the runbook to identify relevant checks and remediation guidance.
- If the runbook recommends checking something that was not observed,
  put that check in next_checks.
- The evidence field should contain concise observed facts from the
  investigation evidence.

Remember:

remediation.action MUST be exactly one of:

- restart_deployment
- rollback_deployment
- scale_deployment

Do not write a sentence in remediation.action.

Never claim that the remediation has already been executed.
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

    observed_evidence = _build_observed_evidence(
        evidence
    )

    analysis = analysis.model_copy(
        update={
            "evidence": observed_evidence,
        }
    )

    print(
        f"\nRAG results retrieved: {len(knowledge_results)}"
    )

    for result in knowledge_results:
        print(
            f"  - {result.title} "
            f"(similarity={result.similarity:.4f})"
        )

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
    print("AegisAI - Gemma + RAG + Structured Evidence")
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

    print("\nRunning Gemma with RAG...")

    analysis = ask_gemma(
        incident=incident,
        evidence=evidence,
    )

    print("\nGemma Analysis:")
    print(
        analysis.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()
