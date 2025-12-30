/**
 * API client for Palmetto backend.
 */

import axios from 'axios';

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
