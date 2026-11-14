import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock maplibre-gl for jsdom unit tests
vi.mock('maplibre-gl', () => {
  return {
    Map: class {
        on() {}
        once() {}
        remove() {}
        isStyleLoaded() {
          return true;
        }
        getStyle() {
          return {};
        }
        getLayer() {
          return null;
        }
        getSource() {
          return null;
        }
        addSource() {}
        addLayer() {}
        removeLayer() {}
        removeSource() {}
        fitBounds() {}
    },
  };
});

