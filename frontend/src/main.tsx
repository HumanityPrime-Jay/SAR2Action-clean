import React from 'react';
import ReactDOM from 'react-dom/client';
import { setWorkerUrl } from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { App } from './App';
import { InvestigationStudio } from './studio/InvestigationStudio';
import './styles.css';

setWorkerUrl(maplibreWorkerUrl);

const studioPath = `${import.meta.env.BASE_URL}studio`;
const showStudio =
  new URLSearchParams(window.location.search).get('view') === 'studio' ||
  window.location.pathname.replace(/\/$/, '') === studioPath;

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    {showStudio ? <InvestigationStudio /> : <App />}
  </React.StrictMode>
);
