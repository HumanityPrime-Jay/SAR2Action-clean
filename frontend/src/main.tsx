import React from 'react';
import ReactDOM from 'react-dom/client';
import { setWorkerUrl } from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { App } from './App';
import { InvestigationStudio } from './studio/InvestigationStudio';
import './styles.css';

setWorkerUrl(maplibreWorkerUrl);

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    {window.location.pathname === '/studio' ? <InvestigationStudio /> : <App />}
  </React.StrictMode>
);
