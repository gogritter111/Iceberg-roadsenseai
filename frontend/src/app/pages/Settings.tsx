import { useState } from 'react';

export function Settings() {
  const [name, setName] = useState('Admin User');
  const [region, setRegion] = useState('Bengaluru');

  return (
    <div style={{
      position: 'absolute',
      top: '24px',
      left: '104px',
      width: '600px',
      maxHeight: 'calc(100vh - 48px)',
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
      }}>
        <h1 style={{
          fontFamily: 'Inter, sans-serif',
          fontSize: '24px',
          fontWeight: 700,
          color: '#ffffff',
          margin: 0,
          marginBottom: '4px',
        }}>
          Settings
        </h1>
        <p style={{
          fontFamily: 'DM Mono, monospace',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.4)',
          margin: 0,
        }}>
          Configure your account and preferences
        </p>
      </div>

      {/* Content */}
      <div style={{
        padding: '32px',
        flex: 1,
        overflowY: 'auto',
      }}>
        {/* Name Field */}
        <div style={{ marginBottom: '28px' }}>
          <label style={{
            display: 'block',
            fontFamily: 'DM Mono, monospace',
            fontSize: '10px',
            color: 'rgba(255,255,255,0.4)',
            marginBottom: '10px',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}>
            Name
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{
              width: '100%',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              padding: '12px 16px',
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: '#ffffff',
              outline: 'none',
              transition: 'border-color 0.2s ease',
            }}
            onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'}
            onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'}
          />
        </div>

        {/* Region Field */}
        <div style={{ marginBottom: '28px' }}>
          <label style={{
            display: 'block',
            fontFamily: 'DM Mono, monospace',
            fontSize: '10px',
            color: 'rgba(255,255,255,0.4)',
            marginBottom: '10px',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}>
            Region
          </label>
          <input
            type="text"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="Enter your region (e.g., Bengaluru, Mumbai, Delhi)"
            style={{
              width: '100%',
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px',
              padding: '12px 16px',
              fontFamily: 'Inter, sans-serif',
              fontSize: '14px',
              color: '#ffffff',
              outline: 'none',
              transition: 'border-color 0.2s ease',
            }}
            onFocus={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'}
            onBlur={(e) => e.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'}
          />
        </div>

        {/* Info Card */}
        <div style={{
          background: 'rgba(0,0,0,0.2)',
          border: '1px solid rgba(255,255,255,0.05)',
          borderRadius: '8px',
          padding: '16px',
          marginBottom: '28px',
        }}>
          <div style={{
            fontFamily: 'DM Mono, monospace',
            fontSize: '9px',
            color: 'rgba(255,255,255,0.4)',
            marginBottom: '8px',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
          }}>
            Account Info
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: '8px',
          }}>
            <span style={{
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.5)',
            }}>
              Account Type
            </span>
            <span style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '12px',
              color: '#ffffff',
              fontWeight: 500,
            }}>
              Administrator
            </span>
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
          }}>
            <span style={{
              fontFamily: 'DM Mono, monospace',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.5)',
            }}>
              Active Since
            </span>
            <span style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: '12px',
              color: '#ffffff',
              fontWeight: 500,
            }}>
              Jan 2024
            </span>
          </div>
        </div>

        {/* Save Button */}
        <button
          style={{
            width: '100%',
            background: 'rgba(255,255,255,0.1)',
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: '8px',
            padding: '12px',
            fontFamily: 'Inter, sans-serif',
            fontSize: '14px',
            fontWeight: 600,
            color: '#ffffff',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.15)';
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.1)';
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)';
          }}
        >
          Save Changes
        </button>
      </div>
    </div>
  );
}