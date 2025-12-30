/**
 * API client for Palmetto backend.
 */

import axios from 'axios';
import { RecognizedFeature, RecognizerInfo } from '../types/features';

// Use relative URLs to leverage Vite proxy during development
// In production, set VITE_API_URL environment variable
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Upload

export interface UploadResponse {
  model_id: string;
  filename: string;
  file_format: string;
  topology_stats: Record<string, number>;
  message: string;
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<UploadResponse>('/api/analyze/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}

export async function listModels() {
  const response = await api.get('/api/upload/models');
  return response.data;
}

export async function deleteModel(modelId: string) {
  const response = await api.delete(`/api/upload/models/${modelId}`);
  return response.data;
}

// Recognition

export interface RecognitionRequest {
  model_id: string;
  recognizer: string;
  parameters: Record<string, any>;
}

export interface RecognitionResponse {
  model_id: string;
  recognizer: string;
  features: RecognizedFeature[];
  execution_time: number;
  feature_count: number;
}

export async function recognizeFeatures(
  request: RecognitionRequest
): Promise<RecognitionResponse> {
  const response = await api.post<RecognitionResponse>(
    '/api/recognition/recognize',
    request
  );
  return response.data;
}

export async function listRecognizers(): Promise<{ recognizers: RecognizerInfo[] }> {
  const response = await api.get('/api/recognition/recognizers');
  return response.data;
}

// Natural Language

export interface NLRequest {
  model_id: string;
  command: string;
}

export interface NLResponse {
  model_id: string;
  command: string;
  recognized_intent: {
    recognizer: string;
    parameters: Record<string, any>;
    confidence: number;
  };
  recognizer: string;
  features: RecognizedFeature[];
  execution_time: number;
}

export async function parseNLCommand(request: NLRequest): Promise<NLResponse> {
  const response = await api.post<NLResponse>('/api/nl/parse', request);
  return response.data;
}

// Export

export interface ExportRequest {
  model_id: string;
  include_features: boolean;
  feature_ids: string[];
  linear_deflection?: number;
  angular_deflection?: number;
}

export async function exportToGLTF(request: ExportRequest): Promise<Blob> {
  const response = await api.post('/api/export/gltf', request, {
    responseType: 'blob',
  });
  return response.data;
}

// Graph

export interface GraphNode {
  id: string;
  name: string;
  group: string;
  color: string;
  val: number;
  attributes: Record<string, string>;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
  id: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: Record<string, number>;
}

export async function getGraphData(modelId: string): Promise<GraphData> {
  const response = await api.get<GraphData>(`/api/graph/${modelId}`);
  return response.data;
}

// Query

export interface QueryRequest {
  model_id: string;
  query: string;
}

export interface QueryPredicate {
  attribute: string;
  operator: string;
  value: any;
  tolerance?: number;
}

export interface StructuredQuery {
  entity_type: string;
  predicates: QueryPredicate[];
  sort_by?: string;
  order?: string;
  limit?: number;
}

export interface QueryResponse {
  model_id: string;
  query: string;
  structured_query: StructuredQuery;
  matching_ids: string[];
  total_matches: number;
  entity_type: string;
  execution_time_ms: number;
  entities?: any[];
  success: boolean;
  error?: string;
}

export async function executeGeometricQuery(
  request: QueryRequest
): Promise<QueryResponse> {
  const response = await api.post<QueryResponse>('/api/query/execute', request);
  return response.data;
}

export interface QueryExample {
  query: string;
  description: string;
  category: string;
}

export async function getQueryExamples(): Promise<{ examples: QueryExample[]; total_count: number }> {
  const response = await api.get('/api/query/examples');
  return response.data;
}

export default api;
