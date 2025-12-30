/**
 * FileUpload Component
 * Handles CAD file uploads (STEP, IGES, BREP)
 */

import { useState, useRef } from 'react';
import { uploadFile } from '../api/client';
import './FileUpload.css';

interface FileUploadProps {
  onUploadSuccess: (modelId: string, filename: string) => void;
}

export default function FileUpload({ onUploadSuccess }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file extension
    const validExtensions = ['.step', '.stp', '.iges', '.igs', '.brep'];
    const fileExt = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));

    if (!validExtensions.includes(fileExt)) {
      setError(`Invalid file type. Supported: ${validExtensions.join(', ')}`);
      return;
    }

    setError(null);
    setUploading(true);

    try {
      const response = await uploadFile(file);
      console.log('Upload successful:', response);

      // Clear file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Notify parent
      onUploadSuccess(response.model_id, response.filename);
    } catch (err: any) {
      console.error('Upload failed:', err);
      setError(err.response?.data?.detail || 'Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="file-upload">
      <h3>Upload CAD File</h3>

      <div
        className={`upload-area ${uploading ? 'uploading' : ''}`}
        onClick={handleClick}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".step,.stp,.iges,.igs,.brep"
          onChange={handleFileChange}
          disabled={uploading}
          style={{ display: 'none' }}
        />

        <div className="upload-content">
          {uploading ? (
            <>
              <div className="upload-spinner"></div>
              <p>Uploading and processing...</p>
            </>
          ) : (
            <>
              <svg
                className="upload-icon"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p className="upload-text">Click to upload or drag and drop</p>
              <p className="upload-hint">STEP, IGES, or BREP files</p>
            </>
          )}
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}
    </div>
  );
}
