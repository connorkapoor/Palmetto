/**
 * DFMPanel - Design for Manufacturing Checks Panel
 *
 * Displays DFM violations and warnings for selected manufacturing process.
 * Allows users to select a process and see violations grouped by severity.
 */

import { useState, useEffect } from 'react';
import './DFMPanel.css';
import { ViolationGroup } from './ViolationGroup';

export interface DFMViolation {
  entity_id: string;
  entity_type: string;
  rule: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  value: number;
  threshold: number;
  attribute: string;
}

export interface DFMCheckResponse {
  model_id: string;
  process: string;
  summary: {
    total: number;
    errors: number;
    warnings: number;
    info?: number;
  };
  violations: DFMViolation[];
}

interface DFMPanelProps {
  modelId: string | null;
  onViolationClick: (violation: DFMViolation) => void;
  onClearHighlight: () => void;
}

export default function DFMPanel({ modelId, onViolationClick, onClearHighlight }: DFMPanelProps) {
  const [process, setProcess] = useState<string>('injection_molding');
  const [violations, setViolations] = useState<DFMViolation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedViolationId, setSelectedViolationId] = useState<string | null>(null);
  const [isMinimized, setIsMinimized] = useState(false);

  // Fetch violations when process or modelId changes
  useEffect(() => {
    if (modelId) {
      fetchViolations();
    } else {
      setViolations([]);
      setError(null);
    }
  }, [modelId, process]);

  const fetchViolations = async () => {
    if (!modelId) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `/api/dfm/${modelId}/check?process=${process}&include_warnings=true`
      );

      if (!response.ok) {
        throw new Error(`DFM check failed: ${response.statusText}`);
      }

      const data: DFMCheckResponse = await response.json();
      setViolations(data.violations);
    } catch (err) {
      console.error('Failed to fetch DFM violations:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      setViolations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViolationClick = (violation: DFMViolation) => {
    setSelectedViolationId(violation.entity_id);
    onViolationClick(violation);
  };

  const handleClearHighlight = () => {
    setSelectedViolationId(null);
    onClearHighlight();
  };

  // Group violations by severity
  const violationsBySeverity = violations.reduce((acc, v) => {
    if (!acc[v.severity]) acc[v.severity] = [];
    acc[v.severity].push(v);
    return acc;
  }, {} as Record<string, DFMViolation[]>);

  return (
    <div className={`dfm-panel ${isMinimized ? 'minimized' : ''}`}>
      <div className="dfm-header">
        <h3>DFM Checks</h3>
        <div className="dfm-header-controls">
          {!isMinimized && (
            <select
              value={process}
              onChange={(e) => setProcess(e.target.value)}
              className="process-selector"
              disabled={!modelId || loading}
            >
              <option value="injection_molding">Injection Molding</option>
              <option value="cnc_machining">CNC Machining</option>
              <option value="additive_manufacturing">3D Printing</option>
              <option value="sheet_metal">Sheet Metal</option>
              <option value="investment_casting">Investment Casting</option>
            </select>
          )}
          <button
            className="minimize-btn"
            onClick={() => setIsMinimized(!isMinimized)}
            title={isMinimized ? 'Expand DFM Checks' : 'Minimize DFM Checks'}
          >
            {isMinimized ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {!modelId && (
            <div className="dfm-placeholder">
              <p>Upload a model to run DFM checks</p>
            </div>
          )}

          {modelId && loading && (
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Checking manufacturability...</p>
        </div>
      )}

      {modelId && error && (
        <div className="error-message">
          <span className="error-icon">⚠</span>
          <p>{error}</p>
        </div>
      )}

      {modelId && !loading && !error && violations.length === 0 && (
        <div className="no-violations">
          <span className="check-icon">✓</span>
          <p>No violations found!</p>
          <span className="subtitle">Part is manufacturable with {process.replace('_', ' ')}</span>
        </div>
      )}

      {modelId && !loading && !error && violations.length > 0 && (
        <div className="violations-container">
          <div className="violation-summary">
            {violationsBySeverity.error && (
              <span className="badge badge-error">
                {violationsBySeverity.error.length} Error{violationsBySeverity.error.length !== 1 ? 's' : ''}
              </span>
            )}
            {violationsBySeverity.warning && (
              <span className="badge badge-warning">
                {violationsBySeverity.warning.length} Warning{violationsBySeverity.warning.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          <button
            className="clear-highlight-btn"
            onClick={handleClearHighlight}
            disabled={!selectedViolationId}
          >
            Clear Selection
          </button>

          <div className="violations-list">
            {violationsBySeverity.error && (
              <ViolationGroup
                severity="error"
                violations={violationsBySeverity.error}
                onViolationClick={handleViolationClick}
                selectedViolationId={selectedViolationId}
              />
            )}

            {violationsBySeverity.warning && (
              <ViolationGroup
                severity="warning"
                violations={violationsBySeverity.warning}
                onViolationClick={handleViolationClick}
                selectedViolationId={selectedViolationId}
              />
            )}

            {violationsBySeverity.info && (
              <ViolationGroup
                severity="info"
                violations={violationsBySeverity.info}
                onViolationClick={handleViolationClick}
                selectedViolationId={selectedViolationId}
              />
            )}
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
}
