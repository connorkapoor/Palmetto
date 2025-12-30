/**
 * NLInterface Component
 * Natural language input for feature recognition commands
 */

import { useState } from 'react';
import { parseNLCommand } from '../api/client';
import { RecognizedFeature } from '../types/features';
import './NLInterface.css';

interface NLInterfaceProps {
  modelId: string;
  onFeaturesRecognized: (features: RecognizedFeature[]) => void;
}

const EXAMPLE_COMMANDS = [
  'find all holes',
  'find holes larger than 10mm',
  'detect fillets',
  'find shafts',
  'show me all cavities',
];

export default function NLInterface({
  modelId,
  onFeaturesRecognized,
}: NLInterfaceProps) {
  const [command, setCommand] = useState('');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!command.trim() || !modelId) return;

    setError(null);
    setProcessing(true);
    setLastResult(null);

    try {
      const response = await parseNLCommand({
        model_id: modelId,
        command: command.trim(),
      });

      console.log('NL Recognition result:', response);

      setLastResult({
        intent: response.recognized_intent,
        featureCount: response.features.length,
        executionTime: response.execution_time,
      });

      onFeaturesRecognized(response.features);
      setCommand('');
    } catch (err: any) {
      console.error('NL recognition failed:', err);
      setError(err.response?.data?.detail || 'Failed to process command');
    } finally {
      setProcessing(false);
    }
  };

  const handleExampleClick = (example: string) => {
    setCommand(example);
  };

  return (
    <div className="nl-interface">
      <h3>Natural Language Query</h3>

      <form onSubmit={handleSubmit}>
        <div className="input-wrapper">
          <input
            type="text"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder="e.g., find all holes larger than 10mm"
            disabled={processing}
            className="nl-input"
          />
          <button
            type="submit"
            disabled={processing || !command.trim()}
            className="nl-submit"
          >
            {processing ? (
              <>
                <span className="btn-spinner"></span>
                Processing...
              </>
            ) : (
              'Recognize'
            )}
          </button>
        </div>
      </form>

      {error && <div className="nl-error">{error}</div>}

      {lastResult && (
        <div className="nl-result">
          <div className="result-row">
            <span className="result-label">Recognizer:</span>
            <span className="result-value">{lastResult.intent.recognizer}</span>
          </div>
          <div className="result-row">
            <span className="result-label">Found:</span>
            <span className="result-value">
              {lastResult.featureCount} feature{lastResult.featureCount !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="result-row">
            <span className="result-label">Time:</span>
            <span className="result-value">{lastResult.executionTime.toFixed(2)}s</span>
          </div>
        </div>
      )}

      <div className="examples">
        <p className="examples-label">Try these examples:</p>
        {EXAMPLE_COMMANDS.map((example) => (
          <button
            key={example}
            className="example-btn"
            onClick={() => handleExampleClick(example)}
            disabled={processing}
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
