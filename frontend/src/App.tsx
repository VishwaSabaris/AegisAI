import { useEffect, useState } from "react";
import "./App.css";

type DashboardSummary = {
  total_incidents: number;
  active_incidents: number;
  recovered_incidents: number;
  failed_incidents: number;
  pending_approval: number;
  severity_distribution: Record<string, number>;
  lifecycle_distribution: Record<string, number>;
};

type DashboardSummaryResponse = {
  success: boolean;
  summary: DashboardSummary;
};

type TrendPoint = {
  date: string;
  count: number;
};

type IncidentTrendResponse = {
  success: boolean;
  trend: {
    days: number;
    trend: TrendPoint[];
  };
};

type Incident = {
  incident_id: string;
  service: string;
  namespace: string;
  environment: string;
  status: string;
  lifecycle_state: string;
  severity: string | null;
  root_cause: string | null;
  confidence: number | null;
  remediation_action: string | null;
  remediation_risk: string | null;
  requires_approval: boolean | null;
  approval_status: string | null;
  recovery_status: string | null;
  created_at: string;
  updated_at: string;
};

type IncidentListResponse = {
  success: boolean;
  incidents: Incident[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  filters: {
    service: string | null;
    namespace: string | null;
    lifecycle_state: string | null;
  };
};

type IncidentDetailsResponse = {
  success: boolean;
  incident: {
    incident_id: string;
    service: string;
    namespace: string;
    environment: string;
    status: string;
    recent_log: string;
  };
  lifecycle: {
    incident_id: string;
    service: string;
    namespace: string;
    state: string;
    previous_state: string | null;
    message: string;
  };
  workflow: {
    stage: string;
    incident: string;
    analysis: {
      severity: string;
      root_cause: string;
      confidence: number;
      evidence: string[];
      next_checks: string[];
      remediation: {
        action: string;
        risk: string;
        requires_approval: boolean;
      };
    };
    risk_decision: {
      action: string;
      risk: string;
      requires_approval: boolean;
      allowed: boolean;
      reason: string;
    } | null;
    approval_required: boolean;
    remediation_executed: boolean;
    recovery_status: string | null;
  };
  approval_status: string | null;
  recovery_status: string | null;
  created_at: string;
  updated_at: string;
};

type IncidentTimelineEntry = {
  id: number;
  incident_id: string;
  from_state: string | null;
  to_state: string;
  message: string;
  created_at: string;
};

type IncidentTimelineResponse = {
  success: boolean;
  incident_id: string;
  timeline: IncidentTimelineEntry[];
};

type ApprovalRequest = {
  approved: boolean;
  approved_by?: string | null;
  comment?: string | null;
};

const API_BASE_URL = "http://127.0.0.1:8000";

const LIFECYCLE_STATES = [
  "DETECTED",
  "INVESTIGATING",
  "ANALYZED",
  "AWAITING_APPROVAL",
  "APPROVED",
  "REJECTED",
  "EXECUTING",
  "VERIFYING",
  "RECOVERED",
  "FAILED",
];

function formatLabel(value: string | null): string {
  if (!value) {
    return "—";
  }

  return value
    .toLowerCase()
    .split("_")
    .map(
      (part) =>
        part.charAt(0).toUpperCase() + part.slice(1),
    )
    .join(" ");
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
  });
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatConfidence(value: number | null): string {
  if (value === null) {
    return "—";
  }

  return `${Math.round(value * 100)}%`;
}

function StatusBadge({
  value,
  tone = "default",
}: {
  value: string | null;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  return (
    <span className={`status-badge status-${tone}`}>
      {formatLabel(value)}
    </span>
  );
}

function IncidentList({
  incidents,
  page,
  total,
  totalPages,
  serviceFilter,
  namespaceFilter,
  lifecycleFilter,
  onServiceChange,
  onNamespaceChange,
  onLifecycleChange,
  onPageChange,
  onRefresh,
  onIncidentSelect,
}: {
  incidents: Incident[];
  page: number;
  total: number;
  totalPages: number;
  serviceFilter: string;
  namespaceFilter: string;
  lifecycleFilter: string;
  onServiceChange: (value: string) => void;
  onNamespaceChange: (value: string) => void;
  onLifecycleChange: (value: string) => void;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  onIncidentSelect: (incidentId: string) => void;
}) {
  return (
    <section className="panel incident-panel">
      <div className="panel-header">
        <div>
          <p className="panel-label">Operations</p>
          <h2>Incidents</h2>
        </div>

        <div className="incident-header-actions">
          <span className="panel-badge">
            {total} total
          </span>

          <button
            type="button"
            className="refresh-button"
            onClick={onRefresh}
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="incident-filters">
        <div className="filter-group">
          <label htmlFor="service-filter">
            Service
          </label>

          <select
            id="service-filter"
            value={serviceFilter}
            onChange={(event) =>
              onServiceChange(event.target.value)
            }
          >
            <option value="">All services</option>
            <option value="payment-service">
              payment-service
            </option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="namespace-filter">
            Namespace
          </label>

          <select
            id="namespace-filter"
            value={namespaceFilter}
            onChange={(event) =>
              onNamespaceChange(event.target.value)
            }
          >
            <option value="">All namespaces</option>
            <option value="aegis-demo">
              aegis-demo
            </option>
            <option value="default">default</option>
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="lifecycle-filter">
            Lifecycle
          </label>

          <select
            id="lifecycle-filter"
            value={lifecycleFilter}
            onChange={(event) =>
              onLifecycleChange(event.target.value)
            }
          >
            <option value="">
              All lifecycle states
            </option>

            {LIFECYCLE_STATES.map((state) => (
              <option key={state} value={state}>
                {formatLabel(state)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {incidents.length === 0 ? (
        <div className="empty-state">
          No incidents match the selected filters.
        </div>
      ) : (
        <>
          <div className="incident-table-wrapper">
            <table className="incident-table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Severity</th>
                  <th>Lifecycle</th>
                  <th>Remediation</th>
                  <th>Approval</th>
                  <th>Recovery</th>
                  <th>Created</th>
                </tr>
              </thead>

              <tbody>
                {incidents.map((incident) => (
                  <tr
                    key={incident.incident_id}
                    className="incident-row"
                    onClick={() =>
                      onIncidentSelect(
                        incident.incident_id,
                      )
                    }
                    tabIndex={0}
                    role="button"
                    onKeyDown={(event) => {
                      if (
                        event.key === "Enter" ||
                        event.key === " "
                      ) {
                        event.preventDefault();

                        onIncidentSelect(
                          incident.incident_id,
                        );
                      }
                    }}
                  >
                    <td>
                      <div className="service-cell">
                        <strong>
                          {incident.service}
                        </strong>

                        <span>
                          {incident.namespace} ·{" "}
                          {incident.environment}
                        </span>
                      </div>
                    </td>

                    <td>
                      <StatusBadge
                        value={incident.severity}
                        tone={
                          incident.severity ===
                          "critical"
                            ? "danger"
                            : incident.severity ===
                                "high"
                              ? "warning"
                              : "default"
                        }
                      />
                    </td>

                    <td>
                      <StatusBadge
                        value={
                          incident.lifecycle_state
                        }
                      />
                    </td>

                    <td>
                      <span className="table-secondary">
                        {formatLabel(
                          incident.remediation_action,
                        )}
                      </span>
                    </td>

                    <td>
                      <StatusBadge
                        value={
                          incident.approval_status
                        }
                        tone={
                          incident.approval_status ===
                          "APPROVED"
                            ? "success"
                            : incident.requires_approval
                              ? "warning"
                              : "default"
                        }
                      />
                    </td>

                    <td>
                      <StatusBadge
                        value={
                          incident.recovery_status
                        }
                        tone={
                          incident.recovery_status ===
                          "RECOVERED"
                            ? "success"
                            : incident.recovery_status ===
                                "NOT_RECOVERED"
                              ? "danger"
                              : "default"
                        }
                      />
                    </td>

                    <td>
                      <span
                        className="table-date"
                        title={formatDateTime(
                          incident.created_at,
                        )}
                      >
                        {formatDate(
                          incident.created_at,
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() =>
                onPageChange(page - 1)
              }
            >
              Previous
            </button>

            <span>
              Page {page} of {totalPages}
            </span>

            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() =>
                onPageChange(page + 1)
              }
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}

function ApprovalPanel({
  incidentId,
  approvalStatus,
  approvalRequired,
  onCompleted,
}: {
  incidentId: string;
  approvalStatus: string | null;
  approvalRequired: boolean;
  onCompleted: () => void;
}) {
  const [approver, setApprover] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] =
    useState(false);
  const [error, setError] =
    useState<string | null>(null);
  const [successMessage, setSuccessMessage] =
    useState<string | null>(null);

  const alreadyProcessed =
    approvalStatus === "APPROVED" ||
    approvalStatus === "REJECTED";

  async function submitApproval(
    approved: boolean,
  ) {
    try {
      setSubmitting(true);
      setError(null);
      setSuccessMessage(null);

      const payload: ApprovalRequest = {
        approved,
        approved_by: approver.trim() || null,
        comment: comment.trim() || null,
      };

      const response = await fetch(
        `${API_BASE_URL}/incidents/${incidentId}/approval`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      const responseData = await response.json();

      if (!response.ok) {
        throw new Error(
          responseData?.detail ??
            "Failed to submit approval decision.",
        );
      }

      setSuccessMessage(
        approved
          ? "Remediation approved successfully."
          : "Remediation rejected successfully.",
      );

      setApprover("");
      setComment("");

      onCompleted();
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Failed to submit approval decision.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (!approvalRequired && !alreadyProcessed) {
    return null;
  }

  return (
    <section className="panel detail-card approval-panel">
      <div className="detail-section-header">
        <div>
          <p className="panel-label">
            Human In The Loop
          </p>

          <h3>Remediation approval</h3>
        </div>

        <StatusBadge
          value={approvalStatus}
          tone={
            approvalStatus === "APPROVED"
              ? "success"
              : approvalStatus === "REJECTED"
                ? "danger"
                : "warning"
          }
        />
      </div>

      {alreadyProcessed ? (
        <div className="approval-processed">
          <strong>
            {approvalStatus === "APPROVED"
              ? "Remediation has been approved."
              : "Remediation has been rejected."}
          </strong>

          <p>
            This incident already has a final
            approval decision. No additional decision
            is required.
          </p>
        </div>
      ) : (
        <>
          <p className="detail-text approval-description">
            The proposed infrastructure change
            requires explicit human approval before
            execution.
          </p>

          <div className="approval-form">
            <div className="approval-field">
              <label htmlFor="approver-name">
                Approver name
              </label>

              <input
                id="approver-name"
                type="text"
                value={approver}
                onChange={(event) =>
                  setApprover(event.target.value)
                }
                placeholder="Enter approver name"
                disabled={submitting}
              />
            </div>

            <div className="approval-field">
              <label htmlFor="approval-comment">
                Comment
              </label>

              <textarea
                id="approval-comment"
                value={comment}
                onChange={(event) =>
                  setComment(event.target.value)
                }
                placeholder="Optional approval or rejection reason"
                rows={4}
                disabled={submitting}
              />
            </div>

            {error && (
              <div className="approval-error">
                {error}
              </div>
            )}

            {successMessage && (
              <div className="approval-success">
                {successMessage}
              </div>
            )}

            <div className="approval-actions">
              <button
                type="button"
                className="approval-button approval-reject"
                disabled={submitting}
                onClick={() =>
                  void submitApproval(false)
                }
              >
                {submitting
                  ? "Processing..."
                  : "Reject Remediation"}
              </button>

              <button
                type="button"
                className="approval-button approval-approve"
                disabled={submitting}
                onClick={() =>
                  void submitApproval(true)
                }
              >
                {submitting
                  ? "Processing..."
                  : "Approve Remediation"}
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}

function IncidentDetails({
  incidentId,
  onBack,
  onRefreshDashboard,
}: {
  incidentId: string;
  onBack: () => void;
  onRefreshDashboard: () => void;
}) {
  const [details, setDetails] =
    useState<IncidentDetailsResponse | null>(null);

  const [timeline, setTimeline] =
    useState<IncidentTimelineEntry[]>([]);

  const [loading, setLoading] = useState(true);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDetails() {
      try {
        const response = await fetch(
          `${API_BASE_URL}/incidents/${incidentId}`,
        );

        if (!response.ok) {
          throw new Error(
            "Failed to load incident details.",
          );
        }

        const data =
          (await response.json()) as IncidentDetailsResponse;

        const timelineResponse = await fetch(
          `${API_BASE_URL}/incidents/${incidentId}/timeline`,
        );

        if (!timelineResponse.ok) {
          throw new Error(
            "Failed to load incident timeline.",
          );
        }

        const timelineData =
          (await timelineResponse.json()) as IncidentTimelineResponse;

        if (cancelled) {
          return;
        }

        setDetails(data);
        setTimeline(timelineData.timeline);
        setError(null);
        setLoading(false);
      } catch (fetchError) {
        if (cancelled) {
          return;
        }

        setError(
          fetchError instanceof Error
            ? fetchError.message
            : "Failed to load incident details.",
        );

        setLoading(false);
      }
    }

    void loadDetails();

    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  async function refreshDetails() {
    try {
      const response = await fetch(
        `${API_BASE_URL}/incidents/${incidentId}`,
      );

      if (!response.ok) {
        throw new Error(
          "Failed to refresh incident details.",
        );
      }

      const data =
        (await response.json()) as IncidentDetailsResponse;

      const timelineResponse = await fetch(
        `${API_BASE_URL}/incidents/${incidentId}/timeline`,
      );

      if (!timelineResponse.ok) {
        throw new Error(
          "Failed to refresh incident timeline.",
        );
      }

      const timelineData =
        (await timelineResponse.json()) as IncidentTimelineResponse;

      setDetails(data);
      setTimeline(timelineData.timeline);
      setError(null);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error
          ? fetchError.message
          : "Failed to refresh incident details.",
      );
    }
  }

  async function handleApprovalCompleted() {
    await refreshDetails();
    onRefreshDashboard();
  }

  if (loading) {
    return (
      <section className="state-card">
        <p>Loading incident details...</p>
      </section>
    );
  }

  if (error || !details) {
    return (
      <section className="state-card error-card">
        <button
          type="button"
          className="back-button"
          onClick={onBack}
        >
          ← Back to incidents
        </button>

        <h2>Incident unavailable</h2>

        <p>
          {error ??
            "The requested incident could not be loaded."}
        </p>
      </section>
    );
  }

  const analysis = details.workflow.analysis;

  const riskDecision =
    details.workflow.risk_decision;

  return (
    <section className="incident-details">
      <button
        type="button"
        className="back-button"
        onClick={onBack}
      >
        ← Back to incidents
      </button>

      <div className="details-header panel">
        <div>
          <p className="panel-label">
            Incident Details
          </p>

          <h2>{details.incident.service}</h2>

          <p className="details-subtitle">
            {details.incident.namespace} ·{" "}
            {details.incident.environment}
          </p>

          <code className="incident-id">
            {details.incident.incident_id}
          </code>
        </div>

        <div className="details-header-status">
          <StatusBadge
            value={analysis.severity}
            tone={
              analysis.severity === "critical"
                ? "danger"
                : analysis.severity === "high"
                  ? "warning"
                  : "default"
            }
          />

          <StatusBadge
            value={details.lifecycle.state}
          />
        </div>
      </div>

      <div className="details-grid">
        <section className="panel detail-card">
          <p className="panel-label">
            Incident Status
          </p>

          <div className="detail-stat-grid">
            <div>
              <span className="detail-label">
                Current status
              </span>

              <strong>
                {details.incident.status}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Severity
              </span>

              <strong>
                {formatLabel(analysis.severity)}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Confidence
              </span>

              <strong>
                {formatConfidence(
                  analysis.confidence,
                )}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Workflow stage
              </span>

              <strong>
                {formatLabel(
                  details.workflow.stage,
                )}
              </strong>
            </div>
          </div>
        </section>

        <section className="panel detail-card">
          <p className="panel-label">Timeline</p>

          <div className="detail-stat-grid">
            <div>
              <span className="detail-label">
                Created
              </span>

              <strong>
                {formatDateTime(
                  details.created_at,
                )}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Updated
              </span>

              <strong>
                {formatDateTime(
                  details.updated_at,
                )}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Previous state
              </span>

              <strong>
                {formatLabel(
                  details.lifecycle
                    .previous_state,
                )}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Lifecycle message
              </span>

              <strong>
                {details.lifecycle.message}
              </strong>
            </div>
          </div>
        </section>
      </div>

      <section className="panel detail-card">
        <div className="detail-section-header">
          <div>
            <p className="panel-label">
              Lifecycle History
            </p>

            <h3>Incident Timeline</h3>
          </div>

          <span className="panel-badge">
            {timeline.length} transitions
          </span>
        </div>

        {timeline.length === 0 ? (
          <div className="timeline-empty">
            <p>
              No persisted lifecycle transitions are
              available for this incident.
            </p>
          </div>
        ) : (
          <div className="incident-timeline">
            {timeline.map((entry) => (
              <div
                className="timeline-entry"
                key={entry.id}
              >
                <div className="timeline-marker">
                  <span />
                </div>

                <div className="timeline-content">
                  <div className="timeline-header">
                    <div className="timeline-transition">
                      <span className="timeline-state">
                        {formatLabel(
                          entry.from_state ??
                            "Initial",
                        )}
                      </span>

                      <span className="timeline-arrow">
                        →
                      </span>

                      <span className="timeline-state timeline-state-current">
                        {formatLabel(
                          entry.to_state,
                        )}
                      </span>
                    </div>

                    <time>
                      {formatDateTime(
                        entry.created_at,
                      )}
                    </time>
                  </div>

                  <p className="timeline-message">
                    {entry.message}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="panel detail-card">
        <p className="panel-label">
          Root Cause Analysis
        </p>

        <h3>Root cause</h3>

        <p className="detail-text">
          {analysis.root_cause}
        </p>

        <div className="observed-log">
          <span className="detail-label">
            Recent log
          </span>

          <code>
            {details.incident.recent_log}
          </code>
        </div>
      </section>

      <section className="panel detail-card">
        <div className="detail-section-header">
          <div>
            <p className="panel-label">
              Investigation
            </p>

            <h3>Observed evidence</h3>
          </div>

          <span className="panel-badge">
            {analysis.evidence.length} observations
          </span>
        </div>

        <div className="evidence-list">
          {analysis.evidence.map(
            (item, index) => (
              <div
                className="evidence-item"
                key={`${index}-${item}`}
              >
                <span className="evidence-number">
                  {String(index + 1).padStart(
                    2,
                    "0",
                  )}
                </span>

                <span>{item}</span>
              </div>
            ),
          )}
        </div>
      </section>

      <section className="details-grid">
        <section className="panel detail-card">
          <div className="detail-section-header">
            <div>
              <p className="panel-label">
                Investigation
              </p>

              <h3>Next checks</h3>
            </div>

            <span className="panel-badge">
              {analysis.next_checks.length} checks
            </span>
          </div>

          <div className="check-list">
            {analysis.next_checks.map(
              (check, index) => (
                <div
                  className="check-item"
                  key={`${index}-${check}`}
                >
                  <span className="check-marker">
                    →
                  </span>

                  <span>{check}</span>
                </div>
              ),
            )}
          </div>
        </section>

        <section className="panel detail-card">
          <p className="panel-label">
            Remediation
          </p>

          <h3>Recommended action</h3>

          <div className="remediation-action">
            <strong>
              {formatLabel(
                analysis.remediation.action,
              )}
            </strong>

            <StatusBadge
              value={
                analysis.remediation.risk
              }
              tone={
                analysis.remediation.risk ===
                  "high" ||
                analysis.remediation.risk ===
                  "critical"
                  ? "danger"
                  : analysis.remediation.risk ===
                      "medium"
                    ? "warning"
                    : "default"
              }
            />
          </div>

          <div className="detail-stat-grid">
            <div>
              <span className="detail-label">
                Requires approval
              </span>

              <strong>
                {analysis.remediation
                  .requires_approval
                  ? "Yes"
                  : "No"}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Remediation executed
              </span>

              <strong>
                {details.workflow
                  .remediation_executed
                  ? "Yes"
                  : "No"}
              </strong>
            </div>
          </div>
        </section>
      </section>

      <section className="panel detail-card">
        <p className="panel-label">
          Risk Policy
        </p>

        <div className="risk-decision">
          <div className="risk-summary">
            <div>
              <span className="detail-label">
                Action
              </span>

              <strong>
                {formatLabel(
                  riskDecision?.action ??
                    analysis.remediation
                      .action,
                )}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Risk
              </span>

              <StatusBadge
                value={
                  riskDecision?.risk ??
                  analysis.remediation.risk
                }
                tone={
                  riskDecision?.risk === "high" ||
                  riskDecision?.risk ===
                    "critical"
                    ? "danger"
                    : "warning"
                }
              />
            </div>

            <div>
              <span className="detail-label">
                Policy approval
              </span>

              <strong>
                {riskDecision?.requires_approval
                  ? "Required"
                  : "Not required"}
              </strong>
            </div>

            <div>
              <span className="detail-label">
                Execution allowed
              </span>

              <strong>
                {riskDecision?.allowed
                  ? "Yes"
                  : "No"}
              </strong>
            </div>
          </div>

          {riskDecision?.reason && (
            <p className="detail-text risk-reason">
              {riskDecision.reason}
            </p>
          )}
        </div>
      </section>

      <ApprovalPanel
        incidentId={
          details.incident.incident_id
        }
        approvalStatus={
          details.approval_status
        }
        approvalRequired={
          details.workflow.approval_required
        }
        onCompleted={
          handleApprovalCompleted
        }
      />

      <div className="details-grid">
        <section className="panel detail-card">
          <p className="panel-label">
            Approval
          </p>

          <div className="status-detail">
            <span className="detail-label">
              Approval status
            </span>

            <StatusBadge
              value={
                details.approval_status
              }
              tone={
                details.approval_status ===
                "APPROVED"
                  ? "success"
                  : details.approval_status ===
                      "REJECTED"
                    ? "danger"
                    : "warning"
              }
            />
          </div>

          <div className="status-detail">
            <span className="detail-label">
              Approval required
            </span>

            <strong>
              {details.workflow
                .approval_required
                ? "Yes"
                : "No"}
            </strong>
          </div>
        </section>

        <section className="panel detail-card">
          <p className="panel-label">
            Recovery
          </p>

          <div className="status-detail">
            <span className="detail-label">
              Recovery status
            </span>

            <StatusBadge
              value={
                details.recovery_status ??
                details.workflow
                  .recovery_status
              }
              tone={
                details.recovery_status ===
                "RECOVERED"
                  ? "success"
                  : details.recovery_status ===
                      "NOT_RECOVERED"
                    ? "danger"
                    : "default"
              }
            />
          </div>
        </section>
      </div>

      <section className="panel detail-card">
        <p className="panel-label">
          Lifecycle
        </p>

        <div className="lifecycle-flow">
          <div className="lifecycle-step">
            <span>Previous</span>

            <strong>
              {formatLabel(
                details.lifecycle
                  .previous_state,
              )}
            </strong>
          </div>

          <span className="lifecycle-arrow">
            →
          </span>

          <div className="lifecycle-step active">
            <span>Current</span>

            <strong>
              {formatLabel(
                details.lifecycle.state,
              )}
            </strong>
          </div>
        </div>

        <p className="detail-text lifecycle-message">
          {details.lifecycle.message}
        </p>
      </section>
    </section>
  );
}

function App() {
  const [summary, setSummary] =
    useState<DashboardSummary | null>(null);

  const [trend, setTrend] =
    useState<TrendPoint[]>([]);

  const [incidents, setIncidents] =
    useState<Incident[]>([]);

  const [totalIncidents, setTotalIncidents] =
    useState(0);

  const [totalPages, setTotalPages] =
    useState(1);

  const [page, setPage] = useState(1);

  const [serviceFilter, setServiceFilter] =
    useState("");

  const [namespaceFilter, setNamespaceFilter] =
    useState("");

  const [lifecycleFilter, setLifecycleFilter] =
    useState("");

  const [selectedIncidentId, setSelectedIncidentId] =
    useState<string | null>(null);

  const [refreshKey, setRefreshKey] =
    useState(0);

  const [dashboardLoading, setDashboardLoading] =
    useState(true);

  const [incidentsLoading, setIncidentsLoading] =
    useState(true);

  const [dashboardError, setDashboardError] =
    useState<string | null>(null);

  const [incidentsError, setIncidentsError] =
    useState<string | null>(null);

  useEffect(() => {
    async function fetchDashboard() {
      try {
        setDashboardLoading(true);
        setDashboardError(null);

        const [
          summaryResponse,
          trendResponse,
        ] = await Promise.all([
          fetch(
            `${API_BASE_URL}/incidents/dashboard/summary`,
          ),
          fetch(
            `${API_BASE_URL}/incidents/dashboard/trend?days=7`,
          ),
        ]);

        if (!summaryResponse.ok) {
          throw new Error(
            "Failed to load dashboard summary.",
          );
        }

        if (!trendResponse.ok) {
          throw new Error(
            "Failed to load incident trend.",
          );
        }

        const summaryData =
          (await summaryResponse.json()) as DashboardSummaryResponse;

        const trendData =
          (await trendResponse.json()) as IncidentTrendResponse;

        setSummary(summaryData.summary);
        setTrend(trendData.trend.trend);
      } catch (error) {
        setDashboardError(
          error instanceof Error
            ? error.message
            : "Failed to load dashboard.",
        );
      } finally {
        setDashboardLoading(false);
      }
    }

    void fetchDashboard();
  }, [refreshKey]);

  useEffect(() => {
    async function fetchIncidents() {
      try {
        setIncidentsLoading(true);
        setIncidentsError(null);

        const params = new URLSearchParams({
          page: String(page),
          page_size: "10",
        });

        if (serviceFilter) {
          params.set(
            "service",
            serviceFilter,
          );
        }

        if (namespaceFilter) {
          params.set(
            "namespace",
            namespaceFilter,
          );
        }

        if (lifecycleFilter) {
          params.set(
            "lifecycle_state",
            lifecycleFilter,
          );
        }

        const response = await fetch(
          `${API_BASE_URL}/incidents?${params.toString()}`,
        );

        if (!response.ok) {
          throw new Error(
            "Failed to load incidents.",
          );
        }

        const data =
          (await response.json()) as IncidentListResponse;

        setIncidents(data.incidents);
        setTotalIncidents(data.total);

        setTotalPages(
          Math.max(data.total_pages, 1),
        );
      } catch (error) {
        setIncidentsError(
          error instanceof Error
            ? error.message
            : "Failed to load incidents.",
        );
      } finally {
        setIncidentsLoading(false);
      }
    }

    void fetchIncidents();
  }, [
    page,
    serviceFilter,
    namespaceFilter,
    lifecycleFilter,
    refreshKey,
  ]);

  function handleServiceChange(value: string) {
    setServiceFilter(value);
    setPage(1);
  }

  function handleNamespaceChange(value: string) {
    setNamespaceFilter(value);
    setPage(1);
  }

  function handleLifecycleChange(value: string) {
    setLifecycleFilter(value);
    setPage(1);
  }

  function handleRefresh() {
    setRefreshKey((current) => current + 1);
  }

  if (selectedIncidentId) {
    return (
      <main className="dashboard">
        <IncidentDetails
          incidentId={selectedIncidentId}
          onBack={() =>
            setSelectedIncidentId(null)
          }
          onRefreshDashboard={handleRefresh}
        />
      </main>
    );
  }

  if (dashboardLoading && !summary) {
    return (
      <main className="dashboard">
        <div className="state-card">
          <p>
            Loading AegisAI dashboard...
          </p>
        </div>
      </main>
    );
  }

  if (dashboardError && !summary) {
    return (
      <main className="dashboard">
        <div className="state-card error-card">
          <h2>Dashboard unavailable</h2>

          <p>{dashboardError}</p>

          <p>
            Make sure the AegisAI FastAPI backend
            is running on{" "}
            <code>127.0.0.1:8000</code>.
          </p>
        </div>
      </main>
    );
  }

  if (!summary) {
    return null;
  }

  const maxTrendCount = Math.max(
    ...trend.map((point) => point.count),
    1,
  );

  const severityTotal = Object.values(
    summary.severity_distribution,
  ).reduce(
    (total, count) => total + count,
    0,
  );

  const lifecycleTotal = Object.values(
    summary.lifecycle_distribution,
  ).reduce(
    (total, count) => total + count,
    0,
  );

  return (
    <main className="dashboard">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">
            AegisAI Control Plane
          </p>

          <h1>Incident Command Center</h1>

          <p className="subtitle">
            Local LLM-powered incident investigation,
            analysis, approval, and recovery
            monitoring.
          </p>
        </div>

        <div className="system-status">
          <span className="status-dot" />

          System operational
        </div>
      </header>

      <section className="metrics-grid">
        <div className="metric-card">
          <p className="metric-label">
            Total incidents
          </p>

          <p className="metric-value">
            {summary.total_incidents}
          </p>

          <p className="metric-description">
            All persisted incidents
          </p>
        </div>

        <div className="metric-card">
          <p className="metric-label">
            Active
          </p>

          <p className="metric-value">
            {summary.active_incidents}
          </p>

          <p className="metric-description">
            Incidents still in progress
          </p>
        </div>

        <div className="metric-card">
          <p className="metric-label">
            Recovered
          </p>

          <p className="metric-value">
            {summary.recovered_incidents}
          </p>

          <p className="metric-description">
            Successfully recovered
          </p>
        </div>

        <div className="metric-card">
          <p className="metric-label">
            Failed
          </p>

          <p className="metric-value">
            {summary.failed_incidents}
          </p>

          <p className="metric-description">
            Failed incident workflows
          </p>
        </div>

        <div className="metric-card">
          <p className="metric-label">
            Pending approval
          </p>

          <p className="metric-value">
            {summary.pending_approval}
          </p>

          <p className="metric-description">
            Waiting for human approval
          </p>
        </div>
      </section>

      <section className="dashboard-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <p className="panel-label">Trend</p>

              <h2>
                Incidents over the last 7 days
              </h2>
            </div>

            <span className="panel-badge">
              7 days
            </span>
          </div>

          <div className="trend-chart">
            {trend.map((point) => (
              <div
                className="trend-column"
                key={point.date}
              >
                <span className="trend-value">
                  {point.count}
                </span>

                <div className="trend-bar-container">
                  <div
                    className="trend-bar"
                    style={{
                      height: `${Math.max(
                        (point.count /
                          maxTrendCount) *
                          100,
                        point.count > 0
                          ? 4
                          : 1,
                      )}%`,
                    }}
                  />
                </div>

                <span className="trend-date">
                  {formatDate(point.date)}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <p className="panel-label">
                Severity
              </p>

              <h2>
                Incident distribution
              </h2>
            </div>

            <span className="panel-badge">
              {severityTotal} classified
            </span>
          </div>

          <div className="distribution-list">
            {Object.entries(
              summary.severity_distribution,
            ).map(([severity, count]) => (
              <div
                className="distribution-row"
                key={severity}
              >
                <div className="distribution-heading">
                  <span>
                    {formatLabel(severity)}
                  </span>

                  <strong>{count}</strong>
                </div>

                <div className="distribution-track">
                  <div
                    className="distribution-fill"
                    style={{
                      width: `${
                        severityTotal
                          ? (count /
                              severityTotal) *
                            100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel lifecycle-panel">
        <div className="panel-header">
          <div>
            <p className="panel-label">
              Workflow
            </p>

            <h2>
              Lifecycle distribution
            </h2>
          </div>

          <span className="panel-badge">
            {lifecycleTotal} tracked
          </span>
        </div>

        <div className="distribution-list">
          {Object.entries(
            summary.lifecycle_distribution,
          ).map(([state, count]) => (
            <div
              className="distribution-row"
              key={state}
            >
              <div className="distribution-heading">
                <span>
                  {formatLabel(state)}
                </span>

                <strong>{count}</strong>
              </div>

              <div className="distribution-track">
                <div
                  className="distribution-fill"
                  style={{
                    width: `${
                      lifecycleTotal
                        ? (count /
                            lifecycleTotal) *
                          100
                        : 0
                    }%`,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </section>

      {incidentsError ? (
        <section className="state-card error-card">
          <h2>
            Incident list unavailable
          </h2>

          <p>{incidentsError}</p>
        </section>
      ) : incidentsLoading ? (
        <section className="state-card">
          <p>Loading incidents...</p>
        </section>
      ) : (
        <IncidentList
          incidents={incidents}
          page={page}
          total={totalIncidents}
          totalPages={totalPages}
          serviceFilter={serviceFilter}
          namespaceFilter={namespaceFilter}
          lifecycleFilter={lifecycleFilter}
          onServiceChange={
            handleServiceChange
          }
          onNamespaceChange={
            handleNamespaceChange
          }
          onLifecycleChange={
            handleLifecycleChange
          }
          onPageChange={setPage}
          onRefresh={handleRefresh}
          onIncidentSelect={
            setSelectedIncidentId
          }
        />
      )}
    </main>
  );
}

export default App;
