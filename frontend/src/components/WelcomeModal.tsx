/**
 * Welcome Modal Component
 * Shows instructions on first app startup
 */

import { useEffect, useState } from 'react';
import './WelcomeModal.css';

const WELCOME_STORAGE_KEY = 'palmetto_welcome_shown';

interface WelcomeModalProps {
  onClose: () => void;
}

export function WelcomeModal({ onClose }: WelcomeModalProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if user has seen the welcome modal
    const hasSeenWelcome = localStorage.getItem(WELCOME_STORAGE_KEY);

    if (!hasSeenWelcome) {
      setIsVisible(true);
    }
  }, []);

  const handleClose = () => {
    localStorage.setItem(WELCOME_STORAGE_KEY, 'true');
    setIsVisible(false);
    onClose();
  };

  if (!isVisible) return null;

  return (
    <div className="welcome-overlay">
      <div className="welcome-modal">
        <div className="welcome-header">
          <h2>Welcome to Palmetto 🌴</h2>
          <p className="welcome-subtitle">Graph-Based CAD Feature Recognition</p>
        </div>

        <div className="welcome-content">
          <div className="welcome-section">
            <h3>Getting Started</h3>
            <ol className="welcome-steps">
              <li>
                <strong>Upload a CAD File</strong>
                <p>Click "Choose File" in the sidebar and select a STEP, IGES, or BREP file</p>
              </li>
              <li>
                <strong>View Features</strong>
                <p>Palmetto automatically detects holes, fillets, cavities, and shafts</p>
              </li>
              <li>
                <strong>Explore the Graph</strong>
                <p>The AAG (Attributed Adjacency Graph) shows topological relationships</p>
              </li>
              <li>
                <strong>Use Natural Language Queries</strong>
                <p>Type questions like "show faces with area &gt; 20mm²" in the bottom panel</p>
              </li>
            </ol>
          </div>

          <div className="welcome-section">
            <h3>Interaction Tips</h3>
            <ul className="welcome-tips">
              <li><strong>Click</strong> on features or faces to highlight them</li>
              <li><strong>Shift + Click</strong> to select multiple features</li>
              <li><strong>Mouse wheel</strong> to zoom in the 3D viewer</li>
              <li><strong>Right-click + drag</strong> to rotate the model</li>
            </ul>
          </div>

          <div className="welcome-section">
            <h3>Supported File Formats</h3>
            <div className="file-formats">
              <span className="file-badge">.STEP</span>
              <span className="file-badge">.STP</span>
              <span className="file-badge">.IGES</span>
              <span className="file-badge">.IGS</span>
              <span className="file-badge">.BREP</span>
            </div>
          </div>
        </div>

        <div className="welcome-footer">
          <button className="welcome-button" onClick={handleClose}>
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
}
