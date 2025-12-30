/**
 * AAGGraphViewer Component
 * Visualizes the Attributed Adjacency Graph using force-directed layout
 */

import { useEffect, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { getGraphData } from '../api/client';
import './AAGGraphViewer.css';

interface AAGGraphViewerProps {
  modelId: string | null;
  recognitionComplete: boolean;
  selectedNodeIds: string[];
  onNodeClick: (nodeId: string, nodeData?: any) => void;
}

interface GraphNode {
  id: string;
  name: string;
  group: string;
  color: string;
  val: number;
  attributes: Record<string, string>;
}

interface GraphLink {
  source: string;
  target: string;
  type: string;
  id: string;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: Record<string, number>;
}

export default function AAGGraphViewer({ modelId, recognitionComplete, selectedNodeIds, onNodeClick }: AAGGraphViewerProps) {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [isMinimized, setIsMinimized] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 600 });
  const [filters, setFilters] = useState({
    vertex: true,
    edge: true,
    face: true,
    shell: true
  });

  useEffect(() => {
    if (!modelId) {
      setGraphData(null);
      return;
    }

    // Only fetch graph after recognition is complete
    if (!recognitionComplete) {
      return;
    }

    const fetchGraph = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await getGraphData(modelId);
        setGraphData(data);
      } catch (err: any) {
        console.error('Failed to load graph:', err);
        setError(err.response?.data?.detail || 'Failed to load graph');
      } finally {
        setLoading(false);
      }
    };

    fetchGraph();
  }, [modelId, recognitionComplete]);

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        setDimensions({ width, height });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
    onNodeClick(node.id, node); // Notify parent component with node data
  };

  const handleBackgroundClick = () => {
    setSelectedNode(null);
  };

  if (!modelId) {
    return (
      <div className="aag-graph-viewer">
        <div className="graph-placeholder">
          <h3>AAG Graph</h3>
          <p>Upload a model to see the graph</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="aag-graph-viewer">
        <div className="graph-loading">
          <div className="spinner"></div>
          <p>Loading graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="aag-graph-viewer">
        <div className="graph-error">
          <h3>Error</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!graphData) {
    return (
      <div className="aag-graph-viewer">
        <div className="graph-placeholder">
          <p>No graph data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`aag-graph-viewer ${isMinimized ? 'minimized' : ''}`} ref={containerRef}>
      <div className="graph-header">
        <h3>AAG Graph</h3>
        <button
          className="minimize-btn"
          onClick={() => setIsMinimized(!isMinimized)}
          title={isMinimized ? 'Expand' : 'Minimize'}
        >
          {isMinimized ? '▲' : '▼'}
        </button>
      </div>

      {!isMinimized && (
        <>
          <div className="graph-stats">
            <span className="stat">
              <span className="stat-label">V:</span>{' '}
              {graphData.stats.vertex || 0}
            </span>
            <span className="stat">
              <span className="stat-label">E:</span>{' '}
              {graphData.stats.edge || 0}
            </span>
            <span className="stat">
              <span className="stat-label">F:</span>{' '}
              {graphData.stats.face || 0}
            </span>
            <span className="stat">
              <span className="stat-label">S:</span>{' '}
              {graphData.stats.shell || 0}
            </span>
          </div>

      <div className="graph-legend">
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#4a90e2' }}></span>
          <span>Vertex</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#50c878' }}></span>
          <span>Edge</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#f5a623' }}></span>
          <span>Face</span>
        </div>
        <div className="legend-item">
          <span className="legend-color" style={{ backgroundColor: '#bd10e0' }}></span>
          <span>Shell</span>
        </div>
      </div>

      <div className="graph-filters">
        <span className="filter-label">Show:</span>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.vertex}
            onChange={(e) => setFilters({ ...filters, vertex: e.target.checked })}
          />
          <span>V</span>
        </label>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.edge}
            onChange={(e) => setFilters({ ...filters, edge: e.target.checked })}
          />
          <span>E</span>
        </label>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.face}
            onChange={(e) => setFilters({ ...filters, face: e.target.checked })}
          />
          <span>F</span>
        </label>
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={filters.shell}
            onChange={(e) => setFilters({ ...filters, shell: e.target.checked })}
          />
          <span>S</span>
        </label>
      </div>

      <div className="graph-container">
        <ForceGraph2D
          graphData={(() => {
            // Filter nodes based on selected filters
            const filteredNodes = graphData.nodes.filter(node => {
              if (node.group === 'vertex') return filters.vertex;
              if (node.group === 'edge') return filters.edge;
              if (node.group === 'face') return filters.face;
              if (node.group === 'shell') return filters.shell;
              return true;
            });

            // Get IDs of visible nodes
            const visibleNodeIds = new Set(filteredNodes.map(n => n.id));

            // Filter links to only include those between visible nodes
            // Handle both string IDs and object references (after force-graph processes data)
            const filteredLinks = graphData.links.filter(link => {
              const sourceId = typeof link.source === 'object' ? (link.source as any).id : link.source;
              const targetId = typeof link.target === 'object' ? (link.target as any).id : link.target;
              return visibleNodeIds.has(sourceId) && visibleNodeIds.has(targetId);
            });

            return {
              nodes: filteredNodes,
              links: filteredLinks,
              stats: graphData.stats
            };
          })()}
          width={dimensions.width}
          height={dimensions.height - 120}
          nodeLabel="name"
          nodeColor="color"
          nodeVal="val"
          nodeCanvasObject={(node: any, ctx, globalScale) => {
            const label = node.name;
            const fontSize = 12 / globalScale;
            const isSelected = selectedNodeIds.includes(node.id);
            ctx.font = `${fontSize}px Sans-Serif`;

            // Draw selection highlight ring if selected
            if (isSelected) {
              ctx.strokeStyle = '#00ff00';
              ctx.lineWidth = 3 / globalScale;
              ctx.beginPath();
              ctx.arc(node.x, node.y, node.val + 2, 0, 2 * Math.PI);
              ctx.stroke();
            }

            // Draw node circle
            ctx.fillStyle = isSelected ? '#ffff00' : node.color;
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI);
            ctx.fill();

            // Draw border
            ctx.strokeStyle = isSelected ? '#00ff00' : '#333';
            ctx.lineWidth = isSelected ? 2 / globalScale : 0.5 / globalScale;
            ctx.stroke();

            // Draw label if zoomed in enough or if selected
            if (globalScale > 1.5 || isSelected) {
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = isSelected ? '#000' : '#333';
              ctx.font = `bold ${fontSize}px Sans-Serif`;
              ctx.fillText(label, node.x, node.y + node.val + 10);
            }
          }}
          linkColor={() => '#999'}
          linkWidth={1}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleSpeed={0.005}
          onNodeClick={handleNodeClick}
          onBackgroundClick={handleBackgroundClick}
          cooldownTicks={100}
          d3VelocityDecay={0.3}
        />
      </div>

      {selectedNode && (
        <div className="node-details">
          <div className="details-header">
            <h4>{selectedNode.name}</h4>
            <button onClick={() => setSelectedNode(null)}>×</button>
          </div>
          <div className="details-content">
            <div className="detail-row">
              <span className="detail-label">Type:</span>
              <span className="detail-value">{selectedNode.group}</span>
            </div>
            {Object.entries(selectedNode.attributes).map(([key, value]) => (
              <div key={key} className="detail-row">
                <span className="detail-label">{key}:</span>
                <span className="detail-value">{value}</span>
              </div>
            ))}
            {selectedNode.featureType && (
              <>
                <div className="detail-divider"></div>
                <div className="detail-row feature-info">
                  <span className="detail-label">Feature:</span>
                  <span className="detail-value feature-type">{selectedNode.featureType}</span>
                </div>
              </>
            )}
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}
