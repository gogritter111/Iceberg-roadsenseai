import { useState, useMemo, useEffect } from 'react';
import { useNavigate, useOutletContext } from 'react-router';
import { Map } from '../components/Map';
import { FilterPopover, Filters } from '../components/FilterPopover';
import { ResolutionFormModal } from '../components/ResolutionFormModal';
import { Incident, fetchIncidents, submitFeedback } from '../data/incidents';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export function Dashboard() {
  const navigate = useNavigate();
  const { isLeftPanelMinimized } = useOutletContext<{ isLeftPanelMinimized: boolean }>();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [isDetailPanelVisible, setIsDetailPanelVisible] = useState(false);
  const [showResolutionForm, setShowResolutionForm] = useState(false);
  const [showSolvedConfirmation, setShowSolvedConfirmation] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    severity: [],
    damageTypes: [],
    confidenceMin: 0,
    timeRange: 'all',
    status: [],
  });

  // Load real incidents from API on mount
  useEffect(() => {
    fetchIncidents().then(setIncidents);
  }, []);

  // Trigger animation when incident is selected
  useEffect(() => {
    if (selectedIncident) {
      setTimeout(() => setIsDetailPanelVisible(true), 10);
    } else {
      setIsDetailPanelVisible(false);
    }
  }, [selectedIncident]);

  const filteredIncidents = useMemo(() => {
    return incidents.filter(incident => {
      // Status filter - default to active and under_verification if no status selected
      if (filters.status.length === 0) {
        if (incident.status === 'solved') return false;
      } else if (!filters.status.includes(incident.status)) {
        return false;
      }

      // Severity filter
      if (filters.severity.length > 0 && !filters.severity.includes(incident.severity)) {
        return false;
      }

      // Damage type filter
      if (filters.damageTypes.length > 0 && !filters.damageTypes.includes(incident.damageType)) {
        return false;
      }

      // Confidence filter
      if (incident.confidence < filters.confidenceMin) {
        return false;
      }

      // Time range filter
      if (filters.timeRange !== 'all') {
        const now = Date.now();
        const timeDiff = now - incident.timestamp;
        
        if (filters.timeRange === '1h' && timeDiff > 60 * 60 * 1000) return false;
        if (filters.timeRange === '24h' && timeDiff > 24 * 60 * 60 * 1000) return false;
        if (filters.timeRange === '7d' && timeDiff > 7 * 24 * 60 * 60 * 1000) return false;
      }

      return true;
    });
  }, [incidents, filters]);

  const handleIncidentSelect = (incident: Incident) => {
    setSelectedIncident(incident);
  };

  const handleCloseDetail = () => {
    setIsDetailPanelVisible(false);
    setTimeout(() => setSelectedIncident(null), 300);
  };

  const handleVerify = () => {
    if (selectedIncident) {
      setIncidents(prev => prev.map(inc => 
        inc.id === selectedIncident.id 
          ? { ...inc, status: 'under_verification' as const }
          : inc
      ));
      setSelectedIncident(prev => prev ? { ...prev, status: 'under_verification' as const } : null);
    }
  };

  const handleIssueSolved = () => {
    setShowSolvedConfirmation(true);
  };

  const handleFalsePositive = () => {
    if (selectedIncident) {
      if (confirm(`Are you sure you want to mark incident ${selectedIncident.code} as a false positive? This will permanently remove it.`)) {
        setIncidents(prev => prev.filter(inc => inc.id !== selectedIncident.id));
        handleCloseDetail();
      }
    }
  };

  const handleResolutionSubmit = async (data: {
    resolvedBy: string;
    resolutionDate: string;
    resolutionNotes: string;
    actionTaken: string;
  }) => {
    if (selectedIncident) {
      await submitFeedback({ incidentId: selectedIncident.id, ...data });
      setIncidents(prev => prev.map(inc => 
        inc.id === selectedIncident.id 
          ? { ...inc, status: 'solved' as const }
          : inc
      ));
      setShowResolutionForm(false);
      setShowSolvedConfirmation(false);
      handleCloseDetail();
    }
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
      {/* Fullscreen Map */}
      <Map 
        incidents={filteredIncidents}
        onIncidentClick={handleIncidentSelect}
      />

      {/* Floating Left Panel - Incident List */}
      <div style={{
        position: 'absolute',
        top: '24px',
        left: '104px',
        width: isLeftPanelMinimized ? '56px' : '280px',
        maxHeight: 'calc(100vh - 48px)',
        background: 'rgba(18,18,24,0.92)',
        backdropFilter: 'blur(20px)',
        borderRadius: '12px',
        border: '1px solid rgba(255,255,255,0.08)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 100,
        transition: 'width 0.3s ease',
      }}>
        {/* Filter Button */}
        <div style={{ 
          padding: '16px 18px', 
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          display: 'flex',
          gap: '8px',
          alignItems: 'center',
        }}>
          {!isLeftPanelMinimized && (
            <div style={{ flex: 1 }}>
              <FilterPopover filters={filters} onChange={setFilters} />
            </div>
          )}
        </div>

        {/* Incident List */}
        {!isLeftPanelMinimized && (
          <div style={{
            overflowY: 'auto',
            flex: 1,
          }}>
            {filteredIncidents.length === 0 ? (
              <div style={{
                padding: '32px 18px',
                textAlign: 'center',
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.4)',
              }}>
                No incidents match your filters
              </div>
            ) : (
              filteredIncidents.map((incident, index) => (
                <div key={incident.id}>
                  <div
                    onClick={() => setSelectedIncident(incident)}
                    style={{
                      padding: '16px 18px',
                      cursor: 'pointer',
                      position: 'relative',
                      background: selectedIncident?.id === incident.id 
                        ? 'rgba(255,255,255,0.06)' 
                        : 'transparent',
                      borderLeft: selectedIncident?.id === incident.id 
                        ? `2px solid ${incident.severityColor}` 
                        : '2px solid transparent',
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (selectedIncident?.id !== incident.id) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (selectedIncident?.id !== incident.id) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    {/* Top Row */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '8px',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          backgroundColor: incident.severityColor,
                        }} />
                        <span style={{
                          fontFamily: 'DM Mono, monospace',
                          fontSize: '11px',
                          color: 'rgba(255,255,255,0.5)',
                          letterSpacing: '0.02em',
                        }}>
                          {incident.code}
                        </span>
                        {getStatusBadge(incident.status)}
                      </div>
                      <span style={{
                        fontFamily: 'DM Mono, monospace',
                        fontSize: '11px',
                        color: 'rgba(255,255,255,0.5)',
                      }}>
                        {incident.confidence}
                      </span>
                    </div>

                    {/* Bottom Row - Route */}
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                    }}>
                      <span style={{
                        fontFamily: 'Inter, sans-serif',
                        fontSize: '15px',
                        fontWeight: 700,
                        color: '#ffffff',
                        letterSpacing: '-0.01em',
                      }}>
                        {incident.origin}
                      </span>
                      <span style={{
                        fontSize: '14px',
                        color: 'rgba(255,255,255,0.3)',
                      }}>
                        →
                      </span>
                      <span style={{
                        fontFamily: 'Inter, sans-serif',
                        fontSize: '15px',
                        fontWeight: 700,
                        color: '#ffffff',
                        letterSpacing: '-0.01em',
                      }}>
                        {incident.damageType}
                      </span>
                    </div>
                  </div>
                  {index < filteredIncidents.length - 1 && (
                    <div style={{
                      height: '1px',
                      background: 'rgba(255,255,255,0.06)',
                      marginLeft: '18px',
                      marginRight: '18px',
                    }} />
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Floating Right Panel - Detail View */}
      {selectedIncident && (
        <div style={{
          position: 'absolute',
          top: '24px',
          right: '24px',
          width: '340px',
          maxHeight: 'calc(100vh - 48px)',
          background: 'rgba(18,18,24,0.92)',
          backdropFilter: 'blur(20px)',
          borderRadius: '12px',
          border: '1px solid rgba(255,255,255,0.08)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 100,
          transform: isDetailPanelVisible ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.3s ease',
        }}>
          <div style={{
            overflowY: 'auto',
            flex: 1,
          }}>
            {/* Header */}
            <div style={{
              padding: '20px 24px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: '#ffffff',
                  letterSpacing: '0.02em',
                }}>
                  {selectedIncident.code}
                </span>
                {getStatusBadge(selectedIncident.status)}
              </div>
              <button
                onClick={handleCloseDetail}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'rgba(255,255,255,0.5)',
                  fontSize: '18px',
                  cursor: 'pointer',
                  padding: '4px',
                  lineHeight: 1,
                }}
              >
                ✕
              </button>
            </div>

            {/* Image Card - Location */}
            <div style={{
              margin: '20px 24px',
              background: 'rgba(0,0,0,0.3)',
              borderRadius: '8px',
              padding: '48px 24px',
              textAlign: 'center',
              border: '1px solid rgba(255,255,255,0.05)',
            }}>
              <div style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '32px',
                fontWeight: 700,
                color: '#ffffff',
                letterSpacing: '-0.02em',
              }}>
                {selectedIncident.origin}
              </div>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.4)',
                marginTop: '8px',
                letterSpacing: '0.05em',
              }}>
                BENGALURU
              </div>
            </div>

            {/* Large Code Labels */}
            <div style={{
              display: 'flex',
              gap: '12px',
              margin: '0 24px 24px',
            }}>
              <div style={{
                flex: 1,
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                padding: '20px 16px',
                textAlign: 'center',
                border: '1px solid rgba(255,255,255,0.05)',
              }}>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '28px',
                  fontWeight: 800,
                  color: '#ffffff',
                  letterSpacing: '0.02em',
                }}>
                  {selectedIncident.damageAbbrev}
                </div>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '9px',
                  color: 'rgba(255,255,255,0.4)',
                  marginTop: '4px',
                  letterSpacing: '0.05em',
                }}>
                  TYPE
                </div>
              </div>
              <div style={{
                flex: 1,
                background: 'rgba(0,0,0,0.3)',
                borderRadius: '8px',
                padding: '20px 16px',
                textAlign: 'center',
                border: '1px solid rgba(255,255,255,0.05)',
              }}>
                <div style={{
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '28px',
                  fontWeight: 800,
                  color: selectedIncident.severityColor,
                  letterSpacing: '0.02em',
                }}>
                  {selectedIncident.severity}
                </div>
                <div style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '9px',
                  color: 'rgba(255,255,255,0.4)',
                  marginTop: '4px',
                  letterSpacing: '0.05em',
                }}>
                  SEVERITY
                </div>
              </div>
            </div>

            {/* Stats Rows */}
            <div style={{
              margin: '0 24px 24px',
            }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '12px 0',
              }}>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.4)',
                  letterSpacing: '0.02em',
                }}>
                  Signals Detected
                </span>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: '#ffffff',
                  fontWeight: 500,
                }}>
                  {selectedIncident.signalsDetected}
                </span>
              </div>
              <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)' }} />
              
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '12px 0',
              }}>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.4)',
                  letterSpacing: '0.02em',
                }}>
                  Confidence
                </span>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: '#ffffff',
                  fontWeight: 500,
                }}>
                  {selectedIncident.confidence}%
                </span>
              </div>
              <div style={{ height: '1px', background: 'rgba(255,255,255,0.06)' }} />
              
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                padding: '12px 0',
              }}>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.4)',
                  letterSpacing: '0.02em',
                }}>
                  Last Updated
                </span>
                <span style={{
                  fontFamily: 'DM Mono, monospace',
                  fontSize: '11px',
                  color: '#ffffff',
                  fontWeight: 500,
                }}>
                  {selectedIncident.lastUpdated}
                </span>
              </div>
            </div>

            {/* Sources Info Section */}
            <div style={{
              margin: '0 24px 24px',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid rgba(255,255,255,0.05)',
            }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '9px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Signal Sources
              </div>
              <div style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '12px',
                color: 'rgba(255,255,255,0.7)',
              }}>
                {selectedIncident.sources.map((source, idx) => (
                  <div key={idx} style={{ marginBottom: '4px' }}>
                    {source.count} from {source.name}
                  </div>
                ))}
              </div>
            </div>

            {/* AI Explanation */}
            <div style={{
              margin: '0 24px 24px',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: '8px',
              padding: '16px',
              border: '1px solid rgba(255,255,255,0.05)',
            }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '9px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                AI Analysis
              </div>
              <div style={{
                fontFamily: 'Inter, sans-serif',
                fontSize: '13px',
                lineHeight: '1.6',
                color: 'rgba(255,255,255,0.7)',
              }}>
                {selectedIncident.explanation}
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{
              margin: '0 24px 24px',
              display: 'flex',
              gap: '8px',
            }}>
              <button 
                onClick={handleVerify}
                disabled={selectedIncident.status === 'under_verification'}
                style={{
                  flex: 1,
                  background: selectedIncident.status === 'under_verification' 
                    ? 'rgba(255,255,255,0.03)' 
                    : 'rgba(59, 130, 246, 0.15)',
                  border: selectedIncident.status === 'under_verification'
                    ? '1px solid rgba(255,255,255,0.05)'
                    : '1px solid rgba(59, 130, 246, 0.3)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: selectedIncident.status === 'under_verification' 
                    ? 'rgba(255,255,255,0.3)' 
                    : '#60a5fa',
                  cursor: selectedIncident.status === 'under_verification' ? 'not-allowed' : 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  if (selectedIncident.status !== 'under_verification') {
                    e.currentTarget.style.background = 'rgba(59, 130, 246, 0.25)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedIncident.status !== 'under_verification') {
                    e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)';
                  }
                }}
              >
                {selectedIncident.status === 'under_verification' ? 'Verified' : 'Verify'}
              </button>
              <button 
                onClick={handleIssueSolved}
                style={{
                  flex: 1,
                  background: 'rgba(34, 197, 94, 0.15)',
                  border: '1px solid rgba(34, 197, 94, 0.3)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#22c55e',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(34, 197, 94, 0.25)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(34, 197, 94, 0.15)'}
              >
                Issue Solved
              </button>
              <button 
                onClick={handleFalsePositive}
                style={{
                  flex: 1,
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#ef4444',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.25)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.15)'}
              >
                False Positive
              </button>
            </div>

            <div style={{
              margin: '0 24px 24px',
            }}>
              <button 
                onClick={() => navigate(`/incident/${selectedIncident.id}`)}
                style={{
                  width: '100%',
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '6px',
                  padding: '10px 12px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#ffffff',
                  cursor: 'pointer',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.12)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              >
                More Details
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Solved Confirmation Dialog */}
      {showSolvedConfirmation && selectedIncident && (
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
      {showResolutionForm && selectedIncident && (
        <ResolutionFormModal
          incident={selectedIncident}
          onClose={() => setShowResolutionForm(false)}
          onSubmit={handleResolutionSubmit}
        />
      )}
    </>
  );
}