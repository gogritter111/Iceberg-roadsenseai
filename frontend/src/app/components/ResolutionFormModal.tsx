import { useState } from 'react';
import { Incident } from '../data/incidents';

interface ResolutionFormModalProps {
  incident: Incident;
  onClose: () => void;
  onSubmit: (data: {
    resolvedBy: string;
    resolutionDate: string;
    resolutionNotes: string;
    actionTaken: string;
  }) => void;
}

export function ResolutionFormModal({ incident, onClose, onSubmit }: ResolutionFormModalProps) {
  const [formData, setFormData] = useState({
    resolvedBy: '',
    resolutionDate: new Date().toISOString().split('T')[0],
    resolutionNotes: '',
    actionTaken: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      background: 'rgba(0,0,0,0.7)',
      backdropFilter: 'blur(8px)',
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
    }}>
      <div style={{
        width: '100%',
        maxWidth: '600px',
        maxHeight: '90vh',
        background: 'rgba(18,18,24,0.98)',
        backdropFilter: 'blur(20px)',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.1)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          padding: '24px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{
              fontFamily: 'DM Mono, monospace',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.5)',
              marginBottom: '4px',
            }}>
              {incident.code}
            </div>
            <div style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '20px',
              fontWeight: 700,
              color: '#ffffff',
            }}>
              Resolution Form
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'rgba(255,255,255,0.5)',
              fontSize: '24px',
              cursor: 'pointer',
              padding: '4px',
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>

        {/* Form Content */}
        <form onSubmit={handleSubmit} style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px',
        }}>
          {/* Incident Summary Card */}
          <div style={{
            background: 'rgba(0,0,0,0.3)',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '24px',
            border: '1px solid rgba(255,255,255,0.05)',
          }}>
            <div style={{
              fontFamily: 'DM Mono, monospace',
              fontSize: '9px',
              color: 'rgba(255,255,255,0.4)',
              marginBottom: '8px',
              letterSpacing: '0.05em',
            }}>
              INCIDENT DETAILS
            </div>
            <div style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '16px',
              fontWeight: 600,
              color: '#ffffff',
              marginBottom: '4px',
            }}>
              {incident.origin} → {incident.damageType}
            </div>
            <div style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.6)',
              lineHeight: '1.5',
            }}>
              {incident.summary}
            </div>
          </div>

          {/* Resolved By */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.6)',
              marginBottom: '8px',
              letterSpacing: '0.02em',
            }}>
              RESOLVED BY *
            </label>
            <input
              type="text"
              required
              value={formData.resolvedBy}
              onChange={(e) => setFormData({ ...formData, resolvedBy: e.target.value })}
              placeholder="Enter name or team"
              style={{
                width: '100%',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                padding: '12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                color: '#ffffff',
                outline: 'none',
              }}
              onFocus={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.3)'}
              onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>

          {/* Resolution Date */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.6)',
              marginBottom: '8px',
              letterSpacing: '0.02em',
            }}>
              RESOLUTION DATE *
            </label>
            <input
              type="date"
              required
              value={formData.resolutionDate}
              onChange={(e) => setFormData({ ...formData, resolutionDate: e.target.value })}
              style={{
                width: '100%',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                padding: '12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                color: '#ffffff',
                outline: 'none',
              }}
              onFocus={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.3)'}
              onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>

          {/* Action Taken */}
          <div style={{ marginBottom: '20px' }}>
            <label style={{
              display: 'block',
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.6)',
              marginBottom: '8px',
              letterSpacing: '0.02em',
            }}>
              ACTION TAKEN *
            </label>
            <select
              required
              value={formData.actionTaken}
              onChange={(e) => setFormData({ ...formData, actionTaken: e.target.value })}
              style={{
                width: '100%',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                padding: '12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                color: '#ffffff',
                outline: 'none',
              }}
              onFocus={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.3)'}
              onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            >
              <option value="" style={{ background: '#1a1a2e' }}>Select action...</option>
              <option value="repaired" style={{ background: '#1a1a2e' }}>Repaired</option>
              <option value="replaced" style={{ background: '#1a1a2e' }}>Replaced</option>
              <option value="cleared" style={{ background: '#1a1a2e' }}>Cleared</option>
            </select>
          </div>

          {/* Resolution Notes */}
          <div style={{ marginBottom: '24px' }}>
            <label style={{
              display: 'block',
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.6)',
              marginBottom: '8px',
              letterSpacing: '0.02em',
            }}>
              RESOLUTION NOTES *
            </label>
            <textarea
              required
              value={formData.resolutionNotes}
              onChange={(e) => setFormData({ ...formData, resolutionNotes: e.target.value })}
              placeholder="Describe how the issue was addressed..."
              rows={5}
              style={{
                width: '100%',
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                padding: '12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                color: '#ffffff',
                outline: 'none',
                resize: 'vertical',
              }}
              onFocus={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.3)'}
              onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
            />
          </div>

          {/* Action Buttons */}
          <div style={{
            display: 'flex',
            gap: '12px',
            paddingTop: '12px',
            borderTop: '1px solid rgba(255,255,255,0.06)',
          }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                flex: 1,
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 500,
                padding: '12px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '6px',
                color: 'rgba(255,255,255,0.7)',
                cursor: 'pointer',
                transition: 'background 0.2s ease',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
            >
              Cancel
            </button>
            <button
              type="submit"
              style={{
                flex: 1,
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                fontWeight: 600,
                padding: '12px',
                background: 'rgba(34, 197, 94, 0.2)',
                border: '1px solid rgba(34, 197, 94, 0.4)',
                borderRadius: '6px',
                color: '#22c55e',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(34, 197, 94, 0.3)';
                e.currentTarget.style.borderColor = 'rgba(34, 197, 94, 0.6)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(34, 197, 94, 0.2)';
                e.currentTarget.style.borderColor = 'rgba(34, 197, 94, 0.4)';
              }}
            >
              Mark as Solved
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}