import React, { useState } from 'react';

export interface IndicatorTooltipProps {
  indicatorId: string;
  label: string;
  shortHint: string;
  whatIsThis: string;
  howCalculated: string;
  howToRead: string;
  source: string;
  limitations: string[];
}

export const IndicatorTooltip: React.FC<IndicatorTooltipProps> = ({
  indicatorId,
  label,
  shortHint,
  whatIsThis,
  howCalculated,
  howToRead,
  source,
  limitations,
}) => {
  const [hovered, setHovered] = useState(false);
  const [expanded, setExpanded] = useState(false);

  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
      <span>{label}</span>
      <button
        type="button"
        aria-label={`解釋指標 ${label} (${indicatorId})`}
        aria-expanded={expanded}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
        onClick={() => setExpanded((prev) => !prev)}
        style={{
          border: '1px solid currentColor',
          borderRadius: '999px',
          width: '20px',
          height: '20px',
          fontSize: '12px',
          lineHeight: '18px',
          textAlign: 'center',
          background: 'transparent',
          color: 'inherit',
          cursor: 'pointer',
        }}
      >
        ⓘ
      </button>
      {hovered && !expanded && (
        <span
          role="tooltip"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 30,
            minWidth: '220px',
            padding: '8px',
            borderRadius: '6px',
            background: '#0f172a',
            color: '#f8fafc',
            fontSize: '12px',
            border: '1px solid #334155',
          }}
        >
          {shortHint}
        </span>
      )}
      {expanded && (
        <div
          role="dialog"
          aria-label={`${label} 詳細說明`}
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 40,
            minWidth: '280px',
            maxWidth: '360px',
            padding: '12px',
            borderRadius: '8px',
            background: '#0f172a',
            color: '#f8fafc',
            fontSize: '12px',
            border: '1px solid #475569',
          }}
        >
          <strong>{label}</strong>
          <p><b>這是什麼？</b> {whatIsThis}</p>
          <p><b>怎麼計算？</b> {howCalculated}</p>
          <p><b>數值怎麼看？</b> {howToRead}</p>
          <p><b>資料從哪裡來？</b> {source}</p>
          <p><b>有哪些限制？</b> {limitations.join('；')}</p>
        </div>
      )}
    </span>
  );
};
