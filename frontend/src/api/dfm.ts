/**
 * DFM API Client
 *
 * Client for calling DFM (Design for Manufacturing) check endpoints.
 */

import { DFMCheckResponse } from '../components/DFMPanel';

/**
 * Check DFM compliance for a model
 *
 * @param modelId - The model ID to check
 * @param process - Manufacturing process (injection_molding, cnc_machining, etc.)
 * @param includeWarnings - Whether to include warnings (default: true)
 * @returns DFM check response with violations
 */
export async function checkDFM(
  modelId: string,
  process: string = 'injection_molding',
  includeWarnings: boolean = true
): Promise<DFMCheckResponse> {
  const params = new URLSearchParams({
    process,
    include_warnings: includeWarnings.toString()
  });

  const response = await fetch(`/api/dfm/${modelId}/check?${params}`);

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`DFM check failed: ${response.statusText} - ${errorText}`);
  }

  return response.json();
}

/**
 * Get available manufacturing processes
 *
 * @returns List of available manufacturing process names
 */
export function getAvailableProcesses(): string[] {
  return [
    'injection_molding',
    'cnc_machining',
    'additive_manufacturing',
    'sheet_metal',
    'investment_casting'
  ];
}

/**
 * Get human-readable process name
 *
 * @param process - Process identifier
 * @returns Human-readable process name
 */
export function getProcessDisplayName(process: string): string {
  const names: Record<string, string> = {
    'injection_molding': 'Injection Molding',
    'cnc_machining': 'CNC Machining',
    'additive_manufacturing': '3D Printing',
    'sheet_metal': 'Sheet Metal',
    'investment_casting': 'Investment Casting'
  };

  return names[process] || process;
}
