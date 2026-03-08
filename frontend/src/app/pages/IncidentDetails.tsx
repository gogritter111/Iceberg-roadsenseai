import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router';
import { fetchIncidentById, submitFeedback } from '../data/incidents';
import { ResolutionFormModal } from '../components/ResolutionFormModal';
import { ArrowLeft } from 'lucide-react';

export function IncidentDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showResolutionForm, setShowResolutionForm] = useState(false);
  const [showSolvedConfirmation, setShowSolvedConfirmation] = useState(false);
  const [incident, setIncident] = useState<any>(null);

  useEffect(() => {
    if (id) fetchIncidentById(id).then(setIncident);
  }, [id]);

  if (!incident) {
    return (
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        textAlign: 'center',
        color: '#ffffff',
      }}>
        <h1>Incident not found</h1>
        <button onClick={() => navigate('/')}>Go back to Dashboard</button>
      </div>
    );
  }

  const handleVerify = () => {
    setIncident(prev => prev ? { ...prev, status: 'under_verification' as const } : null);
  };

  const handleIssueSolved = () => {
    setShowSolvedConfirmation(true);
  };

  const handleFalsePositive = () => {
    if (incident) {
      if (confirm(`Are you sure you want to mark incident ${incident.code} as a false positive? This will permanently remove it.`)) {
        navigate('/');
      }
    }
  };

  const handleResolutionSubmit = async (data: {
    resolvedBy: string;
    resolutionDate: string;
    resolutionNotes: string;
    actionTaken: string;
  }) => {
    if (incident) await submitFeedback({ incidentId: incident.id, ...data });
    setIncident((prev: any) => prev ? { ...prev, status: 'solved' as const } : null);
    setShowResolutionForm(false);
    setShowSolvedConfirmation(false);
    navigate('/');
  };

  const getStatusBadge = (status: string) => {
    if (status === 'under_verification') {
      return (
        <span style={{
          fontFamily: 'DM Mono, monospace',
          fontSize: '9px',
          padding: '3px 6px',
          background: 'rgba(59, 130, 246, 0.15)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '4px',
          color: '#60a5fa',
          letterSpacing: '0.02em',
        }}>
          VERIFYING
        </span>
      );
    }
    return null;
  };

  return (
    <>
      <div style={{
        position: 'absolute',
        top: '24px',
        left: '104px',
        right: '24px',
        bottom: '24px',
        background: 'rgba(18,18,24,0.92)',
        backdropFilter: 'blur(20px)',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.08)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 100,
      }}>
        {/* Header */}
        <div style={{
          padding: '24px 32px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: '16px',
        }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '6px',
              padding: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: '#ffffff',
            }}
          >
            <ArrowLeft size={18} />
          </button>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
              <h1 style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '24px',
                fontWeight: 700,
                color: '#ffffff',
                margin: 0,
              }}>
                Incident Details
              </h1>
              {getStatusBadge(incident.status)}
            </div>
            <p style={{
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.4)',
              margin: 0,
            }}>
              {incident.code}
            </p>
          </div>
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '32px',
        }}>
          <div style={{
            maxWidth: '900px',
            margin: '0 auto',
          }}>
            {/* Hero Card */}
            <div style={{
              background: 'rgba(0,0,0,0.3)',
              borderRadius: '12px',
              padding: '48px 32px',
              textAlign: 'center',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '32px',
            }}>
              <div style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '48px',
                fontWeight: 700,
                color: '#ffffff',
                letterSpacing: '-0.02em',
                marginBottom: '8px',
              }}>
                {incident.origin}
              </div>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.4)',
                letterSpacing: '0.05em',
              }}>
                BENGALURU, INDIA
              </div>
            </div>

            {/* Key Metrics Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
              marginBottom: '32px',
            }}>
              <div style={{
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid rgba(255,255,255,0.05)',
              }}>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '9px',
                  color: 'rgba(255,255,255,0.4)',
                  marginBottom: '8px',
                  letterSpacing: '0.05em',
                }}>
                  DAMAGE TYPE
                </div>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '24px',
                  fontWeight: 700,
                  color: '#ffffff',
                }}>
                  {incident.damageType}
                </div>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.5)',
                  marginTop: '4px',
                }}>
                  {incident.damageAbbrev}
                </div>
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: `1px solid ${incident.severityColor}33`,
              }}>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '9px',
                  color: 'rgba(255,255,255,0.4)',
                  marginBottom: '8px',
                  letterSpacing: '0.05em',
                }}>
                  SEVERITY
                </div>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '24px',
                  fontWeight: 700,
                  color: incident.severityColor,
                }}>
                  {incident.severity}
                </div>
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid rgba(255,255,255,0.05)',
              }}>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '9px',
                  color: 'rgba(255,255,255,0.4)',
                  marginBottom: '8px',
                  letterSpacing: '0.05em',
                }}>
                  SIGNALS DETECTED
                </div>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '24px',
                  fontWeight: 700,
                  color: '#ffffff',
                }}>
                  {incident.signalsDetected}
                </div>
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                padding: '24px',
                border: '1px solid rgba(255,255,255,0.05)',
              }}>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '9px',
                  color: 'rgba(255,255,255,0.4)',
                  marginBottom: '8px',
                  letterSpacing: '0.05em',
                }}>
                  CONFIDENCE
                </div>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '24px',
                  fontWeight: 700,
                  color: '#ffffff',
                }}>
                  {incident.confidence}%
                </div>
              </div>
            </div>

            {/* Location & Coordinates */}
            <div style={{
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '24px',
            }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '16px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Expected Location & Coordinates
              </div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '24px',
              }}>
                <div>
                  <div style={{
                    fontFamily: 'DM Mono, monospace',
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.5)',
                    marginBottom: '6px',
                  }}>
                    Location
                  </div>
                  <div style={{
                    fontFamily: 'Inter, sans-serif',
                    fontSize: '16px',
                    fontWeight: 600,
                    color: '#ffffff',
                  }}>
                    {incident.origin}, Bengaluru
                  </div>
                </div>
                <div>
                  <div style={{
                    fontFamily: 'DM Mono, monospace',
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.5)',
                    marginBottom: '6px',
                  }}>
                    Coordinates
                  </div>
                  <div style={{
                    fontFamily: 'DM Mono, monospace',
                    fontSize: '14px',
                    color: '#ffffff',
                  }}>
                    {incident.lat.toFixed(4)}°N, {incident.lng.toFixed(4)}°E
                  </div>
                </div>
              </div>
            </div>

            {/* Signal Sources */}
            <div style={{
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '24px',
            }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '16px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Signal Sources
              </div>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}>
                {incident.sources.map((source, idx) => (
                  <div key={idx} style={{
                    background: 'rgba(255,255,255,0.03)',
                    borderRadius: '6px',
                    padding: '12px 16px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}>
                    <div style={{
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '14px',
                      color: '#ffffff',
                      fontWeight: 500,
                    }}>
                      {source.name}
                    </div>
                    <div style={{
                      fontFamily: 'DM Mono, monospace',
                      fontSize: '12px',
                      color: 'rgba(255,255,255,0.6)',
                      background: 'rgba(255,255,255,0.08)',
                      padding: '4px 10px',
                      borderRadius: '4px',
                    }}>
                      {source.count} {source.count === 1 ? 'signal' : 'signals'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Analysis */}
            <div style={{
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '24px',
            }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '16px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                AI Source Analysis
              </div>
              <div style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                lineHeight: '1.7',
                color: 'rgba(255,255,255,0.8)',
              }}>
                {incident.explanation}
              </div>
            </div>

            {/* Next Steps */}
            <div style={{
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid rgba(255,255,255,0.05)',
              marginBottom: '32px',
            }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '16px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Recommended Next Steps
              </div>
              <ul style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '14px',
                lineHeight: '1.7',
                color: 'rgba(255,255,255,0.8)',
                paddingLeft: '24px',
                margin: 0,
              }}>
                {incident.severity === 'CRIT' && (
                  <>
                    <li>Deploy emergency road repair team immediately</li>
                    <li>Set up traffic diversion and warning signs</li>
                    <li>Notify local traffic authorities</li>
                    <li>Monitor citizen reports for additional incidents</li>
                  </>
                )}
                {incident.severity === 'HIGH' && (
                  <>
                    <li>Schedule repair team within 24 hours</li>
                    <li>Place warning markers at location</li>
                    <li>Update navigation apps with hazard warning</li>
                    <li>Continue monitoring signal activity</li>
                  </>
                )}
                {incident.severity === 'MED' && (
                  <>
                    <li>Add to weekly maintenance schedule</li>
                    <li>Conduct on-site assessment</li>
                    <li>Monitor for severity escalation</li>
                  </>
                )}
                {incident.severity === 'LOW' && (
                  <>
                    <li>Add to routine maintenance list</li>
                    <li>Monitor for pattern changes</li>
                    <li>Review in next planning cycle</li>
                  </>
                )}
              </ul>
            </div>

            {/* Action Buttons */}
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'center',
            }}>
              <button 
                onClick={handleVerify}
                disabled={incident.status === 'under_verification'}
                style={{
                  minWidth: '160px',
                  background: incident.status === 'under_verification' 
                    ? 'rgba(255,255,255,0.03)' 
                    : 'rgba(59, 130, 246, 0.15)',
                  border: incident.status === 'under_verification'
                    ? '1px solid rgba(255,255,255,0.05)'
                    : '1px solid rgba(59, 130, 246, 0.3)',
                  borderRadius: '8px',
                  padding: '12px 24px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: incident.status === 'under_verification' 
                    ? 'rgba(255,255,255,0.3)' 
                    : '#60a5fa',
                  cursor: incident.status === 'under_verification' ? 'not-allowed' : 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  if (incident.status !== 'under_verification') {
                    e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (incident.status !== 'under_verification') {
                    e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)';
                  }
                }}
              >
                {incident.status === 'under_verification' ? 'Verified' : 'Verify Incident'}
              </button>
              <button 
                onClick={handleIssueSolved}
                style={{
                  minWidth: '160px',
                  background: 'rgba(34, 197, 94, 0.15)',
                  border: '1px solid rgba(34, 197, 94, 0.3)',
                  borderRadius: '8px',
                  padding: '12px 24px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#22c55e',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(34, 197, 94, 0.25)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(34, 197, 94, 0.15)'}
              >
                Mark as Solved
              </button>
              <button 
                onClick={handleFalsePositive}
                style={{
                  minWidth: '160px',
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '8px',
                  padding: '12px 24px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#ef4444',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'}
              >
                Mark as False Positive
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Solved Confirmation Dialog */}
      {showSolvedConfirmation && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'rgba(0,0,0,0.6)',
          backdropFilter: 'blur(4px)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
        }}>
          <div style={{
            background: 'rgba(18,18,24,0.98)',
            backdropFilter: 'blur(20px)',
            borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.1)',
            padding: '24px',
            maxWidth: '400px',
            width: '100%',
          }}>
            <div style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '18px',
              fontWeight: 600,
              color: '#ffffff',
              marginBottom: '12px',
            }}>
              Mark as Solved?
            </div>
            <div style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: 'rgba(255,255,255,0.7)',
              marginBottom: '24px',
              lineHeight: '1.5',
            }}>
              You'll need to fill out a resolution form to document how this issue was addressed.
            </div>
            <div style={{
              display: 'flex',
              gap: '12px',
            }}>
              <button
                onClick={() => setShowSolvedConfirmation(false)}
                style={{
                  flex: 1,
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 500,
                  padding: '10px',
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  color: 'rgba(255,255,255,0.7)',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowSolvedConfirmation(false);
                  setShowResolutionForm(true);
                }}
                style={{
                  flex: 1,
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '14px',
                  fontWeight: 600,
                  padding: '10px',
                  background: 'rgba(34, 197, 94, 0.2)',
                  border: '1px solid rgba(34, 197, 94, 0.4)',
                  borderRadius: '6px',
                  color: '#22c55e',
                  cursor: 'pointer',
                }}
              >
                Continue
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Resolution Form Modal */}
      {showResolutionForm && (
        <ResolutionFormModal
          incident={incident}
          onClose={() => setShowResolutionForm(false)}
          onSubmit={handleResolutionSubmit}
        />
      )}
    </>
  );
}