import { LayoutDashboard, List, Settings } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router';

interface NavigationProps {
  onDashboardClick?: () => void;
}

export function Navigation({ onDashboardClick }: NavigationProps) {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { icon: LayoutDashboard, path: '/', label: 'Dashboard' },
    { icon: List, path: '/list', label: 'List View' },
    { icon: Settings, path: '/settings', label: 'Settings' },
  ];

  return (
    <div style={{
      position: 'fixed',
      left: '24px',
      top: '50%',
      transform: 'translateY(-50%)',
      zIndex: 1000,
      background: 'rgba(18,18,24,0.92)',
      backdropFilter: 'blur(20px)',
      borderRadius: '16px',
      border: '1px solid rgba(255,255,255,0.08)',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {navItems.map((item) => {
        const Icon = item.icon;
        const isActive = location.pathname === item.path;
        
        return (
          <button
            key={item.path}
            onClick={() => {
              if (item.path === '/' && isActive && onDashboardClick) {
                onDashboardClick();
              } else {
                navigate(item.path);
              }
            }}
            title={item.label}
            style={{
              background: isActive ? 'rgba(255,255,255,0.12)' : 'transparent',
              border: 'none',
              borderRadius: '10px',
              width: '44px',
              height: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'background 0.2s ease',
              color: isActive ? '#ffffff' : 'rgba(255,255,255,0.5)',
            }}
            onMouseEnter={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.color = 'rgba(255,255,255,0.8)';
              }
            }}
            onMouseLeave={(e) => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'rgba(255,255,255,0.5)';
              }
            }}
          >
            <Icon size={20} />
          </button>
        );
      })}
    </div>
  );
}