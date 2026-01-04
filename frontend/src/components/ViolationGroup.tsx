/**
 * ViolationGroup - Collapsible group of DFM violations by severity
 *
 * Displays a list of violations grouped by severity (error, warning, info).
 * Each violation can be clicked to highlight the corresponding face in 3D view.
 */

import { useState } from 'react';
import { DFMViolation } from './DFMPanel';

interface ViolationGroupProps {
  severity: 'error' | 'warning' | 'info';
  violations: DFMViolation[];
  onViolationClick: (violation: DFMViolation) => void;
  selectedViolationId: string | null;
}

export function ViolationGroup({
  severity,
  violations,
  onViolationClick,
  selectedViolationId
}: ViolationGroupProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const severityConfig = {
    error: {
      icon: '⚠',
      title: 'Critical Errors',
      color: '#ff3232'
    },
    warning: {
      icon: '⚡',
      title: 'Warnings',
      color: '#ffaa00'
    },
    info: {
      icon: 'ℹ',
      title: 'Information',
      color: '#3399ff'
    }
  };

  const config = severityConfig[severity];

  return (
    <div className={`violation-group violation-group-${severity}`}>
      <div
        className="group-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className={`severity-icon severity-${severity}`}>
          {config.icon}
        </span>
        <span className="group-title">{config.title}</span>
        <span className="group-count">{violations.length}</span>
        <span className={`expand-icon ${isExpanded ? 'expanded' : 'collapsed'}`}>
          ▼
        </span>
      </div>

      {isExpanded && (
        <div className="violations-list">
          {violations.map((violation, idx) => {
            const isSelected = violation.entity_id === selectedViolationId;

            return (
              <div
                key={`${violation.entity_id}-${idx}`}
                className={`violation-item severity-${violation.severity} ${isSelected ? 'selected' : ''}`}
                onClick={() => onViolationClick(violation)}
              >
                <div className="violation-message">{violation.message}</div>
                <div className="violation-details">
                  <span className="violation-value">
                    {violation.attribute}: {formatValue(violation.value, violation.attribute)}
                  </span>
                  <span className="violation-threshold">
                    (threshold: {formatValue(violation.threshold, violation.attribute)})
                  </span>
                </div>
                <div className="violation-entity">
                  {violation.entity_type} {violation.entity_id}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Format value based on attribute type
 */
function formatValue(value: number | boolean, attribute: string): string {
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }

  // Angle attributes (degrees)
  if (attribute.includes('angle')) {
    return `${value.toFixed(1)}°`;
  }

  // Normalized values (0-1)
  if (attribute.includes('variance') || attribute.includes('concentration')) {
    return value.toFixed(3);
  }

  // Distance/thickness values (mm)
  return `${value.toFixed(2)}mm`;
}
