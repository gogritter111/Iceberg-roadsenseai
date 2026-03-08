import { createBrowserRouter } from 'react-router';
import { Dashboard } from './pages/Dashboard';
import { ListView } from './pages/ListView';
import { Settings } from './pages/Settings';
import { IncidentDetails } from './pages/IncidentDetails';
import { Root } from './Root';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Root,
    children: [
      { index: true, Component: Dashboard },
      { path: 'list', Component: ListView },
      { path: 'settings', Component: Settings },
      { path: 'incident/:id', Component: IncidentDetails },
    ],
  },
]);