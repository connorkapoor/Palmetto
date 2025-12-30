/**
 * ScriptingPanel - Natural language query interface for geometric queries.
 *
 * Allows users to query CAD model geometry using natural language:
 * - "show me all faces with area 20mm²"
 * - "find the largest face"
 * - "show planar faces"
 */

import React, { useState, useEffect } from 'react';
import {
  executeGeometricQuery,
  getQueryExamples,
  QueryResponse,
  QueryExample,
} from '../api/client';
import './ScriptingPanel.css';

interface ScriptingPanelProps {
  modelId: string;
  onQueryResult: (entityIds: string[], entityType: string) => void;
}

interface HistoryItem {
  query: string;
  timestamp: number;
  result?: QueryResponse;
}

const MAX_HISTORY = 50;

export const ScriptingPanel: React.FC<ScriptingPanelProps> = ({
  modelId,
  onQueryResult,
}) => {
  const [query, setQuery] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [examples, setExamples] = useState<QueryExample[]>([]);
  const [lastResult, setLastResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load history from localStorage on mount
  useEffect(() => {
    const storedHistory = localStorage.getItem('query-history');
    if (storedHistory) {
      try {
        setHistory(JSON.parse(storedHistory));
      } catch (e) {
        console.error('Failed to parse query history:', e);
      }
    }

    // Load example queries
    loadExamples();
  }, []);

  // Save history to localStorage
  useEffect(() => {
    if (history.length > 0) {
      localStorage.setItem('query-history', JSON.stringify(history));
    }
  }, [history]);

  const loadExamples = async () => {
    try {
      const data = await getQueryExamples();
      setExamples(data.examples);
    } catch (e) {
      console.error('Failed to load examples:', e);
    }
  };

  const handleExecute = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await executeGeometricQuery({
        model_id: modelId,
        query: query.trim(),
      });

      setLastResult(response);

      if (response.success) {
        // Add to history
        const newHistoryItem: HistoryItem = {
          query: query.trim(),
          timestamp: Date.now(),
          result: response,
        };

        setHistory((prev) => {
          const updated = [newHistoryItem, ...prev];
          return updated.slice(0, MAX_HISTORY);
        });

        // Notify parent with matching IDs
        onQueryResult(response.matching_ids, response.entity_type);

        // Warn if query had no filters (may not have been understood)
        if (response.structured_query.predicates.length === 0 &&
            !response.structured_query.sort_by &&
            response.total_matches > 5) {
          setError(
            `Query returned all ${response.entity_type}s (${response.total_matches} matches). ` +
            `The query may not have been understood. Try using keywords like "planar", "cylindrical", "circular", ` +
            `or set up Claude API key for better natural language support.`
          );
        } else {
          // Clear any previous errors if query was understood
          setError(null);
        }

        // Clear input
        setQuery('');
      } else {
        setError(response.error || 'Query execution failed');
      }
    } catch (e: any) {
      console.error('Query execution error:', e);
      setError(e.response?.data?.detail || e.message || 'Failed to execute query');
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleExecute();
    }
  };

  const handleHistoryClick = (item: HistoryItem) => {
    setQuery(item.query);
    if (item.result) {
      onQueryResult(item.result.matching_ids, item.result.entity_type);
      setLastResult(item.result);
    }
  };

  const handleTemplateClick = (example: QueryExample) => {
    setQuery(example.query);
  };

  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  // Group examples by category
  const examplesByCategory = examples.reduce((acc, ex) => {
    if (!acc[ex.category]) {
      acc[ex.category] = [];
    }
    acc[ex.category].push(ex);
    return acc;
  }, {} as Record<string, QueryExample[]>);

  return (
    <div className={`scripting-panel ${isExpanded ? 'expanded' : ''}`}>
      {/* Always visible input bar */}
      <div className="input-bar">
        <input
          type="text"
          className="query-input"
          placeholder="Query geometry: e.g., 'show all faces with area 20mm²'"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button
          className="execute-button"
          onClick={handleExecute}
          disabled={isLoading || !query.trim()}
        >
          {isLoading ? 'Executing...' : 'Execute'}
        </button>
        <button className="expand-button" onClick={toggleExpand}>
          {isExpanded ? '▼' : '▲'}
        </button>
      </div>

      {/* Results summary (always visible when there's a result) */}
      {lastResult && !isExpanded && (
        <div className="results-summary">
          {lastResult.success ? (
            <span className="success">
              Found {lastResult.total_matches} {lastResult.entity_type}
              {lastResult.total_matches !== 1 ? 's' : ''} ({lastResult.execution_time_ms.toFixed(0)}ms)
            </span>
          ) : (
            <span className="error">Query failed</span>
          )}
        </div>
      )}

      {/* Error display */}
      {error && !isExpanded && (
        <div className="error-banner">
          Error: {error}
        </div>
      )}

      {/* Expandable content */}
      {isExpanded && (
        <div className="panel-content">
          <div className="content-grid">
            {/* Left column: History */}
            <div className="history-section">
              <h3>Query History</h3>
              {history.length === 0 ? (
                <p className="empty-state">No queries yet. Try an example below!</p>
              ) : (
                <div className="history-list">
                  {history.map((item, idx) => (
                    <div
                      key={idx}
                      className="history-item"
                      onClick={() => handleHistoryClick(item)}
                    >
                      <div className="history-query">{item.query}</div>
                      <div className="history-meta">
                        {item.result ? (
                          <>
                            <span className={item.result.success ? 'success' : 'error'}>
                              {item.result.success
                                ? `${item.result.total_matches} matches`
                                : 'Failed'}
                            </span>
                            <span className="timestamp">
                              {new Date(item.timestamp).toLocaleTimeString()}
                            </span>
                          </>
                        ) : (
                          <span className="timestamp">
                            {new Date(item.timestamp).toLocaleTimeString()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Right column: Templates and Results */}
            <div className="right-column">
              {/* Templates */}
              <div className="templates-section">
                <h3>Example Queries</h3>
                {Object.entries(examplesByCategory).map(([category, categoryExamples]) => (
                  <div key={category} className="template-category">
                    <h4>{category}</h4>
                    <div className="template-list">
                      {categoryExamples.map((example, idx) => (
                        <button
                          key={idx}
                          className="template-button"
                          onClick={() => handleTemplateClick(example)}
                          title={example.description}
                        >
                          {example.query}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Results Details */}
              {lastResult && (
                <div className="results-section">
                  <h3>Last Query Results</h3>
                  {lastResult.success ? (
                    <div className="results-details">
                      <div className="result-row">
                        <span className="label">Query:</span>
                        <span className="value">{lastResult.query}</span>
                      </div>
                      <div className="result-row">
                        <span className="label">Entity Type:</span>
                        <span className="value">{lastResult.entity_type}</span>
                      </div>
                      <div className="result-row">
                        <span className="label">Total Matches:</span>
                        <span className="value">{lastResult.total_matches}</span>
                      </div>
                      <div className="result-row">
                        <span className="label">Execution Time:</span>
                        <span className="value">{lastResult.execution_time_ms.toFixed(2)}ms</span>
                      </div>
                      {lastResult.matching_ids.length > 0 && (
                        <div className="result-row">
                          <span className="label">Matching IDs:</span>
                          <span className="value small">
                            {lastResult.matching_ids.slice(0, 10).join(', ')}
                            {lastResult.matching_ids.length > 10 && '...'}
                          </span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="error-details">
                      <div className="result-row">
                        <span className="label">Query:</span>
                        <span className="value">{lastResult.query}</span>
                      </div>
                      <div className="result-row">
                        <span className="label">Error:</span>
                        <span className="value error">{lastResult.error}</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
