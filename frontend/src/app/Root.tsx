import { useState } from 'react';
import { Outlet, useLocation } from 'react-router';
import { Navigation } from './components/Navigation';
import { Map } from './components/Map';
import { mockIncidents } from './data/incidents';

export function Root() {
  const location = useLocation();
  const isDashboard = location.pathname === '/';
  const [isLeftPanelMinimized, setIsLeftPanelMinimized] = useState(false);

  return (
    <div style={{
      position: 'relative',
      width: '100vw',
      height: '100vh',
      overflow: 'hidden',
      fontFamily: 'Inter, sans-serif',
      backgroundColor: '#1a1a2e',
    }}>
      {/* Background Map - visible on all pages, faded on non-dashboard */}
      {!isDashboard && (
        <Map 
          incidents={mockIncidents} 
          faded={true}
        />
      )}

      {/* Navigation */}
      <Navigation 
        onDashboardClick={() => {
          if (isDashboard) {
            setIsLeftPanelMinimized(!isLeftPanelMinimized);
          }
        }}
      />

      {/* Page Content */}
      <Outlet context={{ isLeftPanelMinimized, setIsLeftPanelMinimized }} />
    </div>
  );
}