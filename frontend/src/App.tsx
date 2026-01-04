/**
 * Main Palmetto Application Component
 */

import { useState } from 'react';
import { Analytics } from '@vercel/analytics/react';
import './App.css';
import FileUpload from './components/FileUpload';
import Viewer3D from './components/Viewer3D';
import ResultsPanel from './components/ResultsPanel';
import AAGGraphViewer from './components/AAGGraphViewer';
import { ScriptingPanel } from './components/ScriptingPanel';
import { WelcomeModal } from './components/WelcomeModal';
import DFMPanel from './components/DFMPanel';
import { DFMViolation } from './components/DFMPanel';
import { RecognizedFeature } from './types/features';

function App() {
  const [modelId, setModelId] = useState<string | null>(null);
  const [modelFilename, setModelFilename] = useState<string>('');
  const [gltfUrl, setGltfUrl] = useState<string | null>(null);
  const [triFaceMapUrl, setTriFaceMapUrl] = useState<string | null>(null);
  const [topologyUrl, setTopologyUrl] = useState<string | null>(null);
  const [features, setFeatures] = useState<RecognizedFeature[]>([]);
  const [highlightedFaceIds, setHighlightedFaceIds] = useState<string[]>([]);
  const [highlightedVertexIds, setHighlightedVertexIds] = useState<string[]>([]);
  const [highlightedEdgeIds, setHighlightedEdgeIds] = useState<string[]>([]);
  const [selectedAagNodes, setSelectedAagNodes] = useState<string[]>([]);
  const [selectedFeatureIds, setSelectedFeatureIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [recognitionComplete, setRecognitionComplete] = useState(false);

  // Thickness analysis state
  const [showThicknessAnalysis, setShowThicknessAnalysis] = useState(false);
  const [sdfUrl, setSdfUrl] = useState<string | null>(null);
  const [slicePlaneAxis, setSlicePlaneAxis] = useState<'x' | 'y' | 'z'>('z');
  const [slicePlanePosition, setSlicePlanePosition] = useState(0.5);

  // Color range for thickness visualization (in mm)
  const [thicknessMin, setThicknessMin] = useState(0);
  const [thicknessMax, setThicknessMax] = useState(10);

  // Queried thickness value
  const [queriedThickness, setQueriedThickness] = useState<number | null>(null);
  const [queriedPosition, setQueriedPosition] = useState<[number, number, number] | null>(null);

  const handleUploadSuccess = async (uploadedModelId: string, filename: string) => {
    setModelId(uploadedModelId);
    setModelFilename(filename);
    setFeatures([]);
    setHighlightedFaceIds([]);
    setRecognitionComplete(false);

    // Run feature recognition with C++ engine
    await runRecognition(uploadedModelId);
  };

  const runRecognition = async (modelIdToAnalyze: string) => {
    try {
      setLoading(true);
      setRecognitionComplete(false);

      // Call the C++ Analysis Situs engine with all recognizer modules
      const response = await fetch(`/api/analyze/process`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_id: modelIdToAnalyze,
          modules: 'all',  // Run all Analysis Situs recognizers (holes, shafts, fillets, cavities)
          mesh_quality: 0.35,
          enable_thickness_heatmap: false,  // DISABLED - use fast SDF instead!
          heatmap_quality: 0.05,  // Dense FEA-style mesh
          enable_sdf: true,  // Generate volumetric Signed Distance Field (FAST!)
          sdf_resolution: 100,  // SDF grid resolution (100³ = ~0.5 seconds with new optimization!)
        }),
      });

      if (!response.ok) {
        throw new Error('Analysis failed');
      }

      const result = await response.json();
      console.log('Analysis result:', result);

      // Transform C++ engine features to frontend format
      const transformedFeatures = (result.features || []).map((feature: any) => ({
        feature_id: feature.id || feature.feature_id,
        feature_type: feature.subtype
          ? `${feature.type}_${feature.subtype}`
          : feature.type || feature.feature_type,
        confidence: feature.confidence || 1.0,
        face_ids: (feature.faces || feature.face_ids || []).map(String),
        properties: feature.params || feature.properties || {},
      }));

      setFeatures(transformedFeatures);

      // Load mesh, tri_face_map, and topology (use relative URLs for Vite proxy)
      const meshUrl = `/api/analyze/${modelIdToAnalyze}/artifacts/mesh.glb`;
      const sdfArtifactUrl = result.artifacts?.thickness_sdf
        ? `/api/analyze/${modelIdToAnalyze}/artifacts/thickness_sdf.json`
        : null;
      const mapUrl = `/api/analyze/${modelIdToAnalyze}/artifacts/tri_face_map.bin`;
      const topoUrl = `/api/analyze/${modelIdToAnalyze}/artifacts/topology.json`;

      setGltfUrl(meshUrl);
      setSdfUrl(sdfArtifactUrl);
      setTriFaceMapUrl(mapUrl);
      setTopologyUrl(topoUrl);

      // Auto-load SDF metadata to set thickness range
      if (sdfArtifactUrl) {
        try {
          const sdfResponse = await fetch(sdfArtifactUrl);
          const sdfData = await sdfResponse.json();
          if (sdfData.metadata?.thickness_range) {
            const [, max] = sdfData.metadata.thickness_range;
            setThicknessMin(0);  // Always use 0 for red
            setThicknessMax(max);  // Auto-set to detected max for blue
            console.log(`Auto-set thickness range: 0 - ${max.toFixed(2)}mm`);
          }
        } catch (error) {
          console.warn('Failed to load SDF metadata for auto-ranging:', error);
        }
      }

      // Signal that recognition is complete (triggers AAG graph fetch)
      setRecognitionComplete(true);

    } catch (error) {
      console.error('Recognition failed:', error);
      alert('Failed to run feature recognition');
    } finally {
      setLoading(false);
    }
  };

  const handleFeatureClick = (feature: RecognizedFeature, multiSelect = false) => {
    if (multiSelect) {
      // Toggle feature in multi-selection
      const isSelected = selectedFeatureIds.includes(feature.feature_id);
      const newSelectedIds = isSelected
        ? selectedFeatureIds.filter(id => id !== feature.feature_id)
        : [...selectedFeatureIds, feature.feature_id];

      setSelectedFeatureIds(newSelectedIds);

      // Update highlighted faces
      const selectedFeatures = features.filter(f => newSelectedIds.includes(f.feature_id));
      const allFaceIds = selectedFeatures.flatMap(f => f.face_ids);
      setHighlightedFaceIds(allFaceIds);

      // Update AAG nodes
      const nodeIds = allFaceIds.map(faceId => `face_${faceId}`);
      setSelectedAagNodes(nodeIds);
    } else {
      // Single selection (replace)
      setHighlightedFaceIds(feature.face_ids);

      // Highlight corresponding nodes in AAG graph
      const nodeIds = feature.face_ids.map(faceId => `face_${faceId}`);
      setSelectedAagNodes(nodeIds);

      // Track selected feature
      setSelectedFeatureIds([feature.feature_id]);
    }
  };

  const handleAagNodeClick = (nodeId: string, nodeData?: any, multiSelect = false) => {
    if (multiSelect) {
      // Toggle node in multi-selection
      const isSelected = selectedAagNodes.includes(nodeId);
      const newSelectedNodes = isSelected
        ? selectedAagNodes.filter(id => id !== nodeId)
        : [...selectedAagNodes, nodeId];

      setSelectedAagNodes(newSelectedNodes);

      // Update highlights based on node types
      const faceNodes = newSelectedNodes.filter(id => id.startsWith('face_'));
      const vertexNodes = newSelectedNodes.filter(id => id.startsWith('vertex_'));
      const edgeNodes = newSelectedNodes.filter(id => id.startsWith('edge_'));

      setHighlightedFaceIds(faceNodes.map(id => id.replace('face_', '')));
      setHighlightedVertexIds(vertexNodes);
      setHighlightedEdgeIds(edgeNodes);

      // Update selected features
      const faceIds = faceNodes.map(id => id.replace('face_', ''));
      const containingFeatures = features.filter(f =>
        f.face_ids.some(faceId => faceIds.includes(faceId))
      );
      setSelectedFeatureIds(containingFeatures.map(f => f.feature_id));
    } else {
      // Single selection (replace)
      setSelectedAagNodes([nodeId]);

      // Handle different node types
      if (nodeId.startsWith('face_')) {
        const faceId = nodeId.replace('face_', '');
        setHighlightedFaceIds([faceId]);
        setHighlightedVertexIds([]);
        setHighlightedEdgeIds([]);

        const containingFeature = features.find(f => f.face_ids.includes(faceId));
        setSelectedFeatureIds(containingFeature ? [containingFeature.feature_id] : []);

        if (nodeData && containingFeature) {
          nodeData.featureType = containingFeature.feature_type
            .split('_')
            .map((word: string) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
        }
      } else if (nodeId.startsWith('vertex_')) {
        setHighlightedVertexIds([nodeId]);
        setHighlightedFaceIds([]);
        setHighlightedEdgeIds([]);
        setSelectedFeatureIds([]);
      } else if (nodeId.startsWith('edge_')) {
        setHighlightedEdgeIds([nodeId]);
        setHighlightedFaceIds([]);
        setHighlightedVertexIds([]);
        setSelectedFeatureIds([]);
      } else if (nodeId.startsWith('shell_')) {
        setHighlightedFaceIds([]);
        setHighlightedVertexIds([]);
        setHighlightedEdgeIds([]);
        setSelectedFeatureIds([]);
      }
    }
  };

  const handleFaceClick = (faceId: string, multiSelect = false) => {
    if (multiSelect) {
      // Toggle face in multi-selection
      const isSelected = highlightedFaceIds.includes(faceId);
      const newFaceIds = isSelected
        ? highlightedFaceIds.filter(id => id !== faceId)
        : [...highlightedFaceIds, faceId];

      setHighlightedFaceIds(newFaceIds);

      // Update AAG nodes
      const nodeIds = newFaceIds.map(id => `face_${id}`);
      setSelectedAagNodes(nodeIds);

      // Update selected features
      const containingFeatures = features.filter(f =>
        f.face_ids.some(id => newFaceIds.includes(id))
      );
      setSelectedFeatureIds(containingFeatures.map(f => f.feature_id));
    } else {
      // Single selection (replace)
      setHighlightedFaceIds([faceId]);

      // Highlight corresponding node in AAG graph
      setSelectedAagNodes([`face_${faceId}`]);

      // Find and select feature containing this face
      const containingFeature = features.find(f => f.face_ids.includes(faceId));
      setSelectedFeatureIds(containingFeature ? [containingFeature.feature_id] : []);
    }
  };

  const handleHighlightGroup = (groupFeatures: RecognizedFeature[]) => {
    // Collect all face IDs from all features in the group
    const allFaceIds = groupFeatures.flatMap(f => f.face_ids);
    setHighlightedFaceIds(allFaceIds);

    // Highlight all corresponding nodes in AAG graph
    const nodeIds = allFaceIds.map(faceId => `face_${faceId}`);
    setSelectedAagNodes(nodeIds);

    // Select all features in the group
    setSelectedFeatureIds(groupFeatures.map(f => f.feature_id));
  };

  const handleClearHighlight = () => {
    setHighlightedFaceIds([]);
    setHighlightedVertexIds([]);
    setHighlightedEdgeIds([]);
    setSelectedAagNodes([]);
    setSelectedFeatureIds([]);
  };

  const handleQueryResult = (entityIds: string[], entityType: string) => {
    // Clear previous highlights
    setHighlightedFaceIds([]);
    setHighlightedVertexIds([]);
    setHighlightedEdgeIds([]);
    setSelectedFeatureIds([]);

    // Set AAG nodes
    setSelectedAagNodes(entityIds);

    // Highlight based on entity type
    if (entityType === 'face') {
      // Extract face IDs from entity IDs (e.g., "face_1" -> "1")
      const faceIds = entityIds.map(id => id.replace('face_', ''));
      setHighlightedFaceIds(faceIds);
    } else if (entityType === 'edge') {
      setHighlightedEdgeIds(entityIds);
    } else if (entityType === 'vertex') {
      setHighlightedVertexIds(entityIds);
    }
  };

  const handleDFMViolationClick = (violation: DFMViolation) => {
    // Extract face ID from entity_id (e.g., "face_42" -> "42")
    const faceId = violation.entity_id.replace('face_', '');

    // Highlight the face
    setHighlightedFaceIds([faceId]);

    // Update AAG nodes
    setSelectedAagNodes([violation.entity_id]);

    // Clear feature selection
    setSelectedFeatureIds([]);
  };

  return (
    <div className="app">
      <WelcomeModal onClose={() => {}} />

      <header className="app-header">
        <h1>Palmetto</h1>
      </header>

      <div className="app-container">
        <div className="sidebar">
          <FileUpload onUploadSuccess={handleUploadSuccess} />

          <div className="settings-panel">
            <h3>Visualization Settings</h3>

            {/* Queried thickness display (toggle moved to right panel) */}
            {sdfUrl && (
              <>
                {/* Queried thickness display */}
                {queriedThickness !== null && showThicknessAnalysis && (
                  <div className="setting-item" style={{
                    backgroundColor: 'rgba(100, 200, 255, 0.1)',
                    padding: '8px',
                    borderRadius: '4px',
                    border: '1px solid rgba(100, 200, 255, 0.3)'
                  }}>
                    <strong>Thickness at clicked point:</strong>
                    <div style={{ fontSize: '1.2em', marginTop: '4px', color: '#0066cc' }}>
                      {queriedThickness.toFixed(2)} mm
                    </div>
                    {queriedPosition && (
                      <div style={{ fontSize: '0.75em', color: '#666', marginTop: '4px' }}>
                        Position: ({queriedPosition[0].toFixed(1)}, {queriedPosition[1].toFixed(1)}, {queriedPosition[2].toFixed(1)})
                      </div>
                    )}
                  </div>
                )}

                {showThicknessAnalysis && (
                  <>
                    {/* Auto-calculated color range display */}
                    <div className="setting-item" style={{
                      backgroundColor: 'rgba(240, 240, 240, 0.5)',
                      padding: '8px',
                      borderRadius: '6px',
                      fontSize: '0.85em',
                      color: '#666'
                    }}>
                      <div style={{ fontWeight: 600, marginBottom: '4px' }}>Auto Color Range:</div>
                      <div>🔴 Red = 0.0mm (thin)</div>
                      <div>🔵 Blue = {thicknessMax.toFixed(2)}mm (max detected)</div>
                    </div>
                    <div style={{ fontSize: '0.75em', color: '#999', marginTop: '8px', textAlign: 'center' }}>
                      Use slice controls at bottom
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          {modelId && (
            <>
              <div className="model-info">
                <h3>Current Model</h3>
                <p className="filename">{modelFilename}</p>
                <p className="model-id">ID: {modelId.slice(0, 8)}...</p>
              </div>

              <ResultsPanel
                features={features}
                selectedFeatureIds={selectedFeatureIds}
                onFeatureClick={handleFeatureClick}
                onClearHighlight={handleClearHighlight}
                onHighlightGroup={handleHighlightGroup}
              />
            </>
          )}
        </div>

        <div className="main-content">
          <div className="viewer-container">
            {loading && (
              <div className="loading-overlay">
                <div className="spinner"></div>
                <p>Loading model...</p>
              </div>
            )}

            {gltfUrl && triFaceMapUrl && topologyUrl ? (
              <Viewer3D
                gltfUrl={gltfUrl}
                triFaceMapUrl={triFaceMapUrl}
                topologyUrl={topologyUrl}
                sdfUrl={sdfUrl ?? undefined}
                showThicknessAnalysis={showThicknessAnalysis}
                slicePlanePosition={slicePlanePosition}
                slicePlaneAxis={slicePlaneAxis}
                thicknessRange={[thicknessMin, thicknessMax]}
                highlightedFaceIds={highlightedFaceIds}
                highlightedVertexIds={highlightedVertexIds}
                highlightedEdgeIds={highlightedEdgeIds}
                onFaceClick={handleFaceClick}
                onThicknessQuery={(thickness, position) => {
                  setQueriedThickness(thickness);
                  setQueriedPosition(position);
                }}
              />
            ) : (
              <div className="viewer-placeholder">
                <div className="placeholder-content">
                  <h2>No Model Loaded</h2>
                  <p>Upload a CAD file to get started</p>
                  <div className="supported-formats">
                    <p>Supported formats:</p>
                    <ul>
                      <li>.step / .stp</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {/* Floating Slice Controls - Above Query Panel */}
            {showThicknessAnalysis && sdfUrl && (
              <div className="floating-slice-controls">
                <div className="floating-controls-content">
                  <div className="control-compact">
                    <label htmlFor="slice-axis-float">Axis:</label>
                    <select
                      id="slice-axis-float"
                      value={slicePlaneAxis}
                      onChange={(e) => setSlicePlaneAxis(e.target.value as 'x' | 'y' | 'z')}
                    >
                      <option value="x">X</option>
                      <option value="y">Y</option>
                      <option value="z">Z</option>
                    </select>
                  </div>

                  <div className="control-compact slider-compact">
                    <label htmlFor="slice-position-float">
                      {(slicePlanePosition * 100).toFixed(0)}%
                    </label>
                    <div className="slider-compact-container">
                      <span className="slider-label-sm">0</span>
                      <input
                        id="slice-position-float"
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={slicePlanePosition}
                        onChange={(e) => setSlicePlanePosition(parseFloat(e.target.value))}
                        className="slice-slider-compact"
                      />
                      <span className="slider-label-sm">100</span>
                    </div>
                  </div>

                  <div className="control-compact info-compact">
                    <span>🔴 0 → 🔵 {thicknessMax.toFixed(1)}mm</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="graph-panel">
            {/* Thickness Analysis Pill Toggle */}
            {sdfUrl && (
              <button
                className={`thickness-toggle-pill ${showThicknessAnalysis ? 'active' : ''}`}
                onClick={() => {
                  setShowThicknessAnalysis(!showThicknessAnalysis);
                  if (showThicknessAnalysis) {
                    setQueriedThickness(null);
                    setQueriedPosition(null);
                  }
                }}
                title={showThicknessAnalysis ? 'Hide Thickness Analysis' : 'Show Thickness Analysis'}
              >
                <span className="pill-icon">{showThicknessAnalysis ? '◉' : '○'}</span>
                <span className="pill-text">Thickness Analysis</span>
                <span className="pill-range">{showThicknessAnalysis ? `0-${thicknessMax.toFixed(1)}mm` : ''}</span>
              </button>
            )}

            <AAGGraphViewer
              modelId={modelId}
              recognitionComplete={recognitionComplete}
              selectedNodeIds={selectedAagNodes}
              onNodeClick={handleAagNodeClick}
            />

            <DFMPanel
              modelId={modelId}
              onViolationClick={handleDFMViolationClick}
              onClearHighlight={handleClearHighlight}
            />
          </div>
        </div>
      </div>

      {/* Natural Language Query Interface */}
      {modelId && (
        <ScriptingPanel
          modelId={modelId}
          onQueryResult={handleQueryResult}
        />
      )}

      {/* Vercel Analytics */}
      <Analytics />
    </div>
  );
}

export default App;
