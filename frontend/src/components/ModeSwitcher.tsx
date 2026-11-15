import React from 'react';

export type UserMode = 'FARMER' | 'AUTHORITY';

interface ModeSwitcherProps {
  mode: UserMode;
  onModeChange: (nextMode: UserMode) => void;
}

export const ModeSwitcher: React.FC<ModeSwitcherProps> = ({ mode, onModeChange }) => {
  return (
    <div
      role="group"
      aria-label="使用模式切換"
      style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}
    >
      <button
        type="button"
        aria-pressed={mode === 'FARMER'}
        onClick={() => onModeChange('FARMER')}
        style={{
          padding: '6px 12px',
          borderRadius: '6px',
          border: '1px solid currentColor',
          fontWeight: mode === 'FARMER' ? 700 : 400,
          cursor: 'pointer',
          background: mode === 'FARMER' ? 'rgba(52, 211, 153, 0.2)' : 'transparent',
          color: 'inherit',
        }}
      >
        🌾 農民模式
      </button>
      <button
        type="button"
        aria-pressed={mode === 'AUTHORITY'}
        onClick={() => onModeChange('AUTHORITY')}
        style={{
          padding: '6px 12px',
          borderRadius: '6px',
          border: '1px solid currentColor',
          fontWeight: mode === 'AUTHORITY' ? 700 : 400,
          cursor: 'pointer',
          background: mode === 'AUTHORITY' ? 'rgba(96, 165, 250, 0.2)' : 'transparent',
          color: 'inherit',
        }}
      >
        🛰️ 農政專業模式
      </button>
    </div>
  );
};
