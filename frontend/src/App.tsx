/**
 * Main Palmetto Application Component
 */

import { useState } from 'react';
import './App.css';
import FileUpload from './components/FileUpload';
import Viewer3D from './components/Viewer3D';
import ResultsPanel from './components/ResultsPanel';
// import NLInterface from './components/NLInterface';  // Disabled - uses Python recognizers
import AAGGraphViewer from './components/AAGGraphViewer';
import { ScriptingPanel } from './components/ScriptingPanel';
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
      const mapUrl = `/api/analyze/${modelIdToAnalyze}/artifacts/tri_face_map.bin`;
      const topoUrl = `/api/analyze/${modelIdToAnalyze}/artifacts/topology.json`;

      setGltfUrl(meshUrl);
      setTriFaceMapUrl(mapUrl);
      setTopologyUrl(topoUrl);

      // Signal that recognition is complete (triggers AAG graph fetch)
      setRecognitionComplete(true);

    } catch (error) {
      console.error('Recognition failed:', error);
      alert('Failed to run feature recognition');
    } finally {
      setLoading(false);
    }
  };

  const handleFeaturesRecognized = (recognizedFeatures: RecognizedFeature[]) => {
    setFeatures(recognizedFeatures);
    setHighlightedFaceIds([]);
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

  return (
    <div className="app">
      <header className="app-header">
        <h1>Palmetto</h1>
      </header>

      <div className="app-container">
        <div className="sidebar">
          <FileUpload onUploadSuccess={handleUploadSuccess} />

          {modelId && (
            <>
              <div className="model-info">
                <h3>Current Model</h3>
                <p className="filename">{modelFilename}</p>
                <p className="model-id">ID: {modelId.slice(0, 8)}...</p>
              </div>

              {/* NL Interface temporarily disabled - uses Python recognizers */}
              {/* <NLInterface
                modelId={modelId}
                onFeaturesRecognized={handleFeaturesRecognized}
              /> */}

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
                highlightedFaceIds={highlightedFaceIds}
                highlightedVertexIds={highlightedVertexIds}
                highlightedEdgeIds={highlightedEdgeIds}
                onFaceClick={handleFaceClick}
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
                      <li>.iges / .igs</li>
                      <li>.brep</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="graph-panel">
            <AAGGraphViewer
              modelId={modelId}
              recognitionComplete={recognitionComplete}
              selectedNodeIds={selectedAagNodes}
              onNodeClick={handleAagNodeClick}
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
    </div>
  );
}

export default App;
