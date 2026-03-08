import { useState } from 'react';
import { Filter, X } from 'lucide-react';

export interface Filters {
  severity: string[];
  damageTypes: string[];
  confidenceMin: number;
  timeRange: string;
  status: string[];
}

interface FilterPopoverProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function FilterPopover({ filters, onChange }: FilterPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);

  const severityOptions = [
    { value: 'CRIT', label: 'Critical', color: '#ef4444' },
    { value: 'HIGH', label: 'High', color: '#f97316' },
    { value: 'MED', label: 'Medium', color: '#fbbf24' },
    { value: 'LOW', label: 'Low', color: '#fef3c7' },
  ];

  const damageTypeOptions = ['Pothole', 'Crack', 'Debris', 'Flooding'];
  
  const statusOptions = [
    { value: 'active', label: 'Active' },
    { value: 'under_verification', label: 'Under Verification' },
    { value: 'solved', label: 'Solved' },
  ];
  
  const timeRangeOptions = [
    { value: 'all', label: 'All Time' },
    { value: '1h', label: 'Last Hour' },
    { value: '24h', label: 'Last 24 Hours' },
    { value: '7d', label: 'Last 7 Days' },
  ];

  const toggleSeverity = (value: string) => {
    const newSeverity = filters.severity.includes(value)
      ? filters.severity.filter(s => s !== value)
      : [...filters.severity, value];
    onChange({ ...filters, severity: newSeverity });
  };

  const toggleDamageType = (value: string) => {
    const newTypes = filters.damageTypes.includes(value)
      ? filters.damageTypes.filter(t => t !== value)
      : [...filters.damageTypes, value];
    onChange({ ...filters, damageTypes: newTypes });
  };

  const toggleStatus = (value: string) => {
    const newStatus = filters.status.includes(value)
      ? filters.status.filter(s => s !== value)
      : [...filters.status, value];
    onChange({ ...filters, status: newStatus });
  };

  const activeFilterCount = 
    filters.severity.length + 
    filters.damageTypes.length + 
    (filters.confidenceMin > 0 ? 1 : 0) + 
    (filters.timeRange !== 'all' ? 1 : 0) +
    (filters.status?.length || 0);

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          background: isOpen ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.08)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: '8px',
          padding: '8px 14px',
          fontFamily: 'Inter, sans-serif',
          fontSize: '12px',
          fontWeight: 500,
          color: '#ffffff',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          width: '100%',
          justifyContent: 'center',
          transition: 'background 0.2s ease',
        }}
        onMouseEnter={(e) => {
          if (!isOpen) e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
        }}
        onMouseLeave={(e) => {
          if (!isOpen) e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
        }}
      >
        <Filter size={14} />
        Filter
        {activeFilterCount > 0 && (
          <span style={{
            background: '#ef4444',
            borderRadius: '10px',
            padding: '2px 6px',
            fontSize: '10px',
            fontWeight: 600,
          }}>
            {activeFilterCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            onClick={() => setIsOpen(false)}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 999,
            }}
          />
          <div style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            left: 0,
            right: 0,
            background: 'rgba(18,18,24,0.95)',
            backdropFilter: 'blur(20px)',
            borderRadius: '12px',
            border: '1px solid rgba(255,255,255,0.08)',
            padding: '16px',
            zIndex: 1000,
            maxHeight: '400px',
            overflowY: 'auto',
          }}>
            {/* Status Filter */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Status
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {statusOptions.map(option => (
                  <label
                    key={option.value}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      cursor: 'pointer',
                      padding: '6px',
                      borderRadius: '6px',
                      background: filters.status.includes(option.value) 
                        ? 'rgba(255,255,255,0.08)' 
                        : 'transparent',
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!filters.status.includes(option.value)) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!filters.status.includes(option.value)) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={filters.status.includes(option.value)}
                      onChange={() => toggleStatus(option.value)}
                    />
                    <span style={{
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '13px',
                      color: '#ffffff',
                    }}>
                      {option.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Severity Filter */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Severity
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {severityOptions.map(option => (
                  <label
                    key={option.value}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      cursor: 'pointer',
                      padding: '6px',
                      borderRadius: '6px',
                      background: filters.severity.includes(option.value) 
                        ? 'rgba(255,255,255,0.08)' 
                        : 'transparent',
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!filters.severity.includes(option.value)) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!filters.severity.includes(option.value)) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={filters.severity.includes(option.value)}
                      onChange={() => toggleSeverity(option.value)}
                      style={{ accentColor: option.color }}
                    />
                    <div style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: option.color,
                    }} />
                    <span style={{
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '13px',
                      color: '#ffffff',
                    }}>
                      {option.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Damage Type Filter */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Damage Type
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {damageTypeOptions.map(type => (
                  <label
                    key={type}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      cursor: 'pointer',
                      padding: '6px',
                      borderRadius: '6px',
                      background: filters.damageTypes.includes(type) 
                        ? 'rgba(255,255,255,0.08)' 
                        : 'transparent',
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!filters.damageTypes.includes(type)) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!filters.damageTypes.includes(type)) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={filters.damageTypes.includes(type)}
                      onChange={() => toggleDamageType(type)}
                    />
                    <span style={{
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '13px',
                      color: '#ffffff',
                    }}>
                      {type}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Confidence Filter */}
            <div style={{ marginBottom: '20px' }}>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Min Confidence: {filters.confidenceMin}%
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={filters.confidenceMin}
                onChange={(e) => onChange({ ...filters, confidenceMin: parseInt(e.target.value) })}
                style={{
                  width: '100%',
                  accentColor: '#ffffff',
                }}
              />
            </div>

            {/* Time Range Filter */}
            <div>
              <div style={{
                fontFamily: 'DM Mono, monospace',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.4)',
                marginBottom: '10px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
              }}>
                Time Range
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {timeRangeOptions.map(option => (
                  <label
                    key={option.value}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      cursor: 'pointer',
                      padding: '6px',
                      borderRadius: '6px',
                      background: filters.timeRange === option.value 
                        ? 'rgba(255,255,255,0.08)' 
                        : 'transparent',
                      transition: 'background 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (filters.timeRange !== option.value) {
                        e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (filters.timeRange !== option.value) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <input
                      type="radio"
                      name="timeRange"
                      checked={filters.timeRange === option.value}
                      onChange={() => onChange({ ...filters, timeRange: option.value })}
                    />
                    <span style={{
                      fontFamily: 'Inter, sans-serif',
                      fontSize: '13px',
                      color: '#ffffff',
                    }}>
                      {option.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            {/* Clear Filters */}
            {activeFilterCount > 0 && (
              <button
                onClick={() => onChange({
                  severity: [],
                  damageTypes: [],
                  confidenceMin: 0,
                  timeRange: 'all',
                  status: [],
                })}
                style={{
                  marginTop: '16px',
                  width: '100%',
                  background: 'rgba(239,68,68,0.1)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: '6px',
                  padding: '8px',
                  fontFamily: 'Inter, sans-serif',
                  fontSize: '12px',
                  fontWeight: 500,
                  color: '#ef4444',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                }}
              >
                <X size={14} />
                Clear All Filters
              </button>
            )}
          </div>
        </>
      )}
    </div>
  );
}