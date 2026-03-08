import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Incident } from '../data/incidents';

interface MapProps {
  incidents: Incident[];
  onIncidentClick?: (incident: Incident) => void;
  faded?: boolean;
}

export function Map({ incidents, onIncidentClick, faded = false }: MapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const markersRef = useRef<{ marker: L.Marker; incident: Incident; element: HTMLDivElement }[]>([]);
  const spotlightRef = useRef<HTMLDivElement>(null);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Initialize map only once
    if (!mapRef.current) {
      mapRef.current = L.map(mapContainerRef.current, {
        center: [12.9716, 77.5946],
        zoom: 12,
        zoomControl: false,
      });

      // Add tile layer
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(mapRef.current);
      
      // Set map pane z-index to be below UI elements
      const mapPane = mapRef.current.getPane('mapPane');
      if (mapPane) {
        mapPane.style.zIndex = '1';
      }
    }

    return () => {
      // Cleanup map on unmount
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapRef.current) return;

    // Clear existing markers
    markersRef.current.forEach(({ marker }) => marker.remove());
    markersRef.current = [];

    // Add markers for each incident
    incidents.forEach((incident) => {
      // Create custom HTML marker with pulsing animation
      const markerElement = document.createElement('div');
      markerElement.style.position = 'relative';
      markerElement.style.width = '32px';
      markerElement.style.height = '32px';
      markerElement.style.cursor = 'pointer';
      markerElement.style.zIndex = '500';

      // Create pulsing rings
      const pulse1 = document.createElement('div');
      pulse1.style.position = 'absolute';
      pulse1.style.top = '50%';
      pulse1.style.left = '50%';
      pulse1.style.width = '24px';
      pulse1.style.height = '24px';
      pulse1.style.borderRadius = '50%';
      pulse1.style.border = `2px solid ${incident.severityColor}`;
      pulse1.style.transform = 'translate(-50%, -50%)';
      pulse1.style.animation = 'pulse 3s ease-out infinite';
      pulse1.style.opacity = '0';

      const pulse2 = document.createElement('div');
      pulse2.style.position = 'absolute';
      pulse2.style.top = '50%';
      pulse2.style.left = '50%';
      pulse2.style.width = '24px';
      pulse2.style.height = '24px';
      pulse2.style.borderRadius = '50%';
      pulse2.style.border = `2px solid ${incident.severityColor}`;
      pulse2.style.transform = 'translate(-50%, -50%)';
      pulse2.style.animation = 'pulse 3s ease-out infinite 1.5s';
      pulse2.style.opacity = '0';

      // Create outer glow circle
      const outerGlow = document.createElement('div');
      outerGlow.style.position = 'absolute';
      outerGlow.style.top = '50%';
      outerGlow.style.left = '50%';
      outerGlow.style.width = '24px';
      outerGlow.style.height = '24px';
      outerGlow.style.borderRadius = '50%';
      outerGlow.style.backgroundColor = incident.severityColor;
      outerGlow.style.opacity = '0.2';
      outerGlow.style.transform = 'translate(-50%, -50%)';
      outerGlow.style.transition = 'opacity 0.3s ease';

      // Create main dot
      const dot = document.createElement('div');
      dot.style.position = 'absolute';
      dot.style.top = '50%';
      dot.style.left = '50%';
      dot.style.width = '12px';
      dot.style.height = '12px';
      dot.style.borderRadius = '50%';
      dot.style.backgroundColor = incident.severityColor;
      dot.style.transform = 'translate(-50%, -50%)';
      dot.style.boxShadow = `0 0 8px ${incident.severityColor}`;
      dot.style.transition = 'transform 0.3s ease';

      // Create center white dot
      const centerDot = document.createElement('div');
      centerDot.style.position = 'absolute';
      centerDot.style.top = '50%';
      centerDot.style.left = '50%';
      centerDot.style.width = '4px';
      centerDot.style.height = '4px';
      centerDot.style.borderRadius = '50%';
      centerDot.style.backgroundColor = 'white';
      centerDot.style.transform = 'translate(-50%, -50%)';

      markerElement.appendChild(pulse1);
      markerElement.appendChild(pulse2);
      markerElement.appendChild(outerGlow);
      markerElement.appendChild(dot);
      markerElement.appendChild(centerDot);

      // Hover effects
      markerElement.addEventListener('mouseenter', () => {
        outerGlow.style.opacity = '0.4';
        dot.style.transform = 'translate(-50%, -50%) scale(1.2)';
        // Trigger immediate pulse on hover
        pulse1.style.animation = 'pulse 1s ease-out';
        setTimeout(() => {
          pulse1.style.animation = 'pulse 3s ease-out infinite';
        }, 1000);
      });

      markerElement.addEventListener('mouseleave', () => {
        outerGlow.style.opacity = '0.2';
        dot.style.transform = 'translate(-50%, -50%) scale(1)';
      });

      // Create custom icon
      const icon = L.divIcon({
        html: markerElement,
        className: 'custom-marker',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      // Create custom popup with sources toggle
      let showingSources = false;
      
      const createPopupContent = () => {
        const container = document.createElement('div');
        container.style.fontFamily = 'Inter, sans-serif';
        container.style.padding = '8px';
        container.style.minWidth = '220px';

        // Code
        const code = document.createElement('div');
        code.style.fontFamily = 'DM Mono, monospace';
        code.style.fontSize = '11px';
        code.style.color = '#666';
        code.style.marginBottom = '6px';
        code.textContent = incident.code;
        container.appendChild(code);

        // Location and Damage Type
        const title = document.createElement('div');
        title.style.fontSize = '14px';
        title.style.fontWeight = '600';
        title.style.marginBottom = '6px';
        title.textContent = `${incident.origin} → ${incident.damageType}`;
        container.appendChild(title);

        // Severity
        const severity = document.createElement('div');
        severity.style.fontSize = '12px';
        severity.style.marginBottom = '6px';
        severity.innerHTML = `<span style="color: #999;">Severity:</span> <span style="color: ${incident.severityColor}; font-weight: 600;">${incident.severity}</span>`;
        container.appendChild(severity);

        // Summary
        const summary = document.createElement('div');
        summary.style.fontSize = '12px';
        summary.style.color = '#666';
        summary.style.marginBottom = '8px';
        summary.style.lineHeight = '1.4';
        summary.textContent = incident.summary;
        container.appendChild(summary);

        // Confidence
        const confidence = document.createElement('div');
        confidence.style.fontSize = '12px';
        confidence.style.color = '#666';
        confidence.style.marginBottom = '8px';
        confidence.textContent = `Confidence: ${incident.confidence}%`;
        container.appendChild(confidence);

        // Sources button
        const sourcesBtn = document.createElement('button');
        sourcesBtn.textContent = showingSources ? 'Hide Sources' : 'Show Sources';
        sourcesBtn.style.fontFamily = 'Inter, sans-serif';
        sourcesBtn.style.fontSize = '11px';
        sourcesBtn.style.padding = '4px 8px';
        sourcesBtn.style.background = 'rgba(255,255,255,0.1)';
        sourcesBtn.style.border = '1px solid rgba(255,255,255,0.2)';
        sourcesBtn.style.borderRadius = '4px';
        sourcesBtn.style.color = '#fff';
        sourcesBtn.style.cursor = 'pointer';
        sourcesBtn.style.marginBottom = '8px';
        
        const sourcesContainer = document.createElement('div');
        sourcesContainer.style.display = showingSources ? 'block' : 'none';
        sourcesContainer.style.fontSize = '11px';
        sourcesContainer.style.color = '#999';
        sourcesContainer.style.marginTop = '6px';
        sourcesContainer.style.paddingTop = '6px';
        sourcesContainer.style.borderTop = '1px solid rgba(255,255,255,0.1)';
        
        incident.sources.forEach(source => {
          const sourceItem = document.createElement('div');
          sourceItem.style.marginBottom = '3px';
          sourceItem.textContent = `${source.count} from ${source.name}`;
          sourcesContainer.appendChild(sourceItem);
        });

        sourcesBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          showingSources = !showingSources;
          sourcesBtn.textContent = showingSources ? 'Hide Sources' : 'Show Sources';
          sourcesContainer.style.display = showingSources ? 'block' : 'none';
        });

        container.appendChild(sourcesBtn);
        container.appendChild(sourcesContainer);

        // Action buttons container
        const actionsContainer = document.createElement('div');
        actionsContainer.style.display = 'flex';
        actionsContainer.style.gap = '6px';
        actionsContainer.style.marginTop = '8px';

        // Verify button
        const verifyBtn = document.createElement('button');
        verifyBtn.textContent = 'Verify';
        verifyBtn.style.flex = '1';
        verifyBtn.style.fontFamily = 'Inter, sans-serif';
        verifyBtn.style.fontSize = '11px';
        verifyBtn.style.padding = '6px 8px';
        verifyBtn.style.background = 'rgba(59, 130, 246, 0.2)';
        verifyBtn.style.border = '1px solid rgba(59, 130, 246, 0.4)';
        verifyBtn.style.borderRadius = '4px';
        verifyBtn.style.color = '#60a5fa';
        verifyBtn.style.cursor = 'pointer';
        verifyBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          onIncidentClick?.(incident);
        });

        // More button
        const moreBtn = document.createElement('button');
        moreBtn.textContent = 'More';
        moreBtn.style.flex = '1';
        moreBtn.style.fontFamily = 'Inter, sans-serif';
        moreBtn.style.fontSize = '11px';
        moreBtn.style.padding = '6px 8px';
        moreBtn.style.background = 'rgba(255,255,255,0.1)';
        moreBtn.style.border = '1px solid rgba(255,255,255,0.2)';
        moreBtn.style.borderRadius = '4px';
        moreBtn.style.color = '#fff';
        moreBtn.style.cursor = 'pointer';
        moreBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          onIncidentClick?.(incident);
        });

        actionsContainer.appendChild(verifyBtn);
        actionsContainer.appendChild(moreBtn);
        container.appendChild(actionsContainer);

        return container;
      };

      const marker = L.marker([incident.lat, incident.lng], { icon })
        .addTo(mapRef.current!);
      
      marker.bindPopup(() => createPopupContent(), {
        maxWidth: 250,
        className: 'custom-popup'
      });

      marker.on('click', () => {
        onIncidentClick?.(incident);
      });

      markersRef.current.push({ marker, incident, element: markerElement });
    });

    // Add keyframes for pulse animation
    if (!document.getElementById('pulse-animation')) {
      const style = document.createElement('style');
      style.id = 'pulse-animation';
      style.innerHTML = `
        @keyframes pulse {
          0% {
            transform: translate(-50%, -50%) scale(1);
            opacity: 0.8;
          }
          100% {
            transform: translate(-50%, -50%) scale(3);
            opacity: 0;
          }
        }
        .leaflet-popup-content-wrapper {
          background: rgba(18, 18, 24, 0.95) !important;
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 8px;
        }
        .leaflet-popup-tip {
          background: rgba(18, 18, 24, 0.95) !important;
        }
        .leaflet-popup-content {
          margin: 0 !important;
        }
      `;
      document.head.appendChild(style);
    }
  }, [incidents, onIncidentClick]);

  // Handle cursor movement for spotlight effect
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setCursorPos({ x, y });
  };

  return (
    <div 
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        opacity: faded ? 0.3 : 1,
        transition: 'opacity 0.3s ease',
        pointerEvents: faded ? 'none' : 'auto',
        zIndex: 1,
      }}
      onMouseMove={handleMouseMove}
    >
      <div 
        ref={mapContainerRef} 
        style={{ 
          width: '100%', 
          height: '100%',
        }} 
      />
      
      {/* Cursor spotlight effect */}
      {!faded && (
        <div
          ref={spotlightRef}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
            background: `radial-gradient(circle 250px at ${cursorPos.x}px ${cursorPos.y}px, rgba(255,255,255,0.12) 0%, transparent 70%)`,
            mixBlendMode: 'lighten',
            zIndex: 2,
          }}
        />
      )}
    </div>
  );
}