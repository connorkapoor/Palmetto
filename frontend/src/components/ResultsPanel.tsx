/**
 * ResultsPanel Component
 * Displays recognized features and allows clicking to highlight them
 */

import React from 'react';
import { RecognizedFeature } from '../types/features';
import './ResultsPanel.css';

interface ResultsPanelProps {
  features: RecognizedFeature[];
  selectedFeatureIds: string[];
  onFeatureClick: (feature: RecognizedFeature, multiSelect?: boolean) => void;
  onClearHighlight: () => void;
  onHighlightGroup?: (features: RecognizedFeature[]) => void;
}

export default function ResultsPanel({
  features,
  selectedFeatureIds,
  onFeatureClick,
  onClearHighlight,
  onHighlightGroup,
}: ResultsPanelProps) {
  const [isExpanded, setIsExpanded] = React.useState(true);

  if (features.length === 0) {
    return (
      <div className="results-panel">
        <div className="results-header">
          <h3>Features</h3>
        </div>
        <div className="no-results">
          <p>No features detected</p>
        </div>
      </div>
    );
  }

  const formatFeatureType = (type: string) => {
    return type
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const formatProperty = (key: string, value: any): string => {
    if (typeof value === 'number') {
      return value.toFixed(2);
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    return String(value);
  };

  // Group features by type
  const featuresByType = features.reduce((acc, feature) => {
    const type = formatFeatureType(feature.feature_type);
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(feature);
    return acc;
  }, {} as Record<string, RecognizedFeature[]>);

  return (
    <div className="results-panel">
      <div className="results-header">
        <h3>Features ({features.length})</h3>
        <button
          className="expand-btn"
          onClick={() => setIsExpanded(!isExpanded)}
          title={isExpanded ? 'Collapse' : 'Expand'}
        >
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {isExpanded && (
        <div className="features-list-compact">
          {Object.entries(featuresByType).map(([type, typeFeatures]) => (
            <div key={type} className="feature-group">
              <div className="feature-group-header">
                <div className="group-header-left">
                  <span className="feature-type-name">{type}</span>
                  <span className="feature-count-badge">{typeFeatures.length}</span>
                </div>
                {onHighlightGroup && (
                  <button
                    className="highlight-group-btn"
                    onClick={() => onHighlightGroup(typeFeatures)}
                    title={`Highlight all ${type} features`}
                  >
                    All
                  </button>
                )}
              </div>
              <div className="feature-items">
                {typeFeatures.map((feature) => {
                  const isSelected = selectedFeatureIds.includes(feature.feature_id);
                  const mainParam = feature.properties.radius_mm || feature.properties.diameter_mm || feature.properties.width_mm;
                  return (
                    <div
                      key={feature.feature_id}
                      className={`feature-item ${isSelected ? 'selected' : ''}`}
                      onClick={(e) => {
                        // Multi-select with Ctrl/Cmd key
                        const multiSelect = e.ctrlKey || e.metaKey;
                        onFeatureClick(feature, multiSelect);
                      }}
                    >
                      <span className="feature-name">
                        {type} {mainParam ? `(${mainParam.toFixed(1)}mm)` : ''}
                      </span>
                      <span className="feature-faces">{feature.face_ids.length}f</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          <button className="clear-all-btn" onClick={onClearHighlight}>
            Clear Selection
          </button>
        </div>
      )}
    </div>
  );
}
