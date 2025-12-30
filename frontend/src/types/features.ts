/**
 * Feature type definitions matching backend enums.
 */

export enum FeatureType {
  HOLE_SIMPLE = 'hole_simple',
  HOLE_COUNTERSUNK = 'hole_countersunk',
  HOLE_COUNTERBORED = 'hole_counterbored',
  HOLE_THREADED = 'hole_threaded',
  SHAFT = 'shaft',
  BOSS = 'boss',
  CAVITY_BLIND = 'cavity_blind',
  CAVITY_THROUGH = 'cavity_through',
  POCKET = 'pocket',
  SLOT = 'slot',
  FILLET = 'fillet',
  CHAMFER = 'chamfer',
  ROUND = 'round',
}

export interface RecognizedFeature {
  feature_id: string;
  feature_type: FeatureType;
  confidence: number;
  face_ids: string[];
  properties: Record<string, any>;
  bounding_geometry?: any;
}

export interface FaceMap {
  [face_id: string]: number[];
}

export interface GLTFMetadata {
  face_map: FaceMap;
  feature_highlights: Record<string, string[]>;
  metadata: {
    vertex_count: number;
    triangle_count: number;
    face_count: number;
    exporter: string;
  };
}
