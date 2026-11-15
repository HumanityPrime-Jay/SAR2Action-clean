import React, { useCallback, useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type HypothesisArenaResponse, type RunHypothesisExperimentResponse } from '../api';

export function ScientificHypothesisArena() {
  const t = useT();
  const { eventId, selectedFieldId, activeHypothesis, setActiveHypothesis } = useEarthContext();
  const [arena, setArena] = useState<HypothesisArenaResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<RunHypothesisExperimentResponse | null>(null);

  const loadArena = useCallback(() => {
    earthApi.getArena(eventId, selectedFieldId).then(setArena).catch(() => {});
  }, [eventId, selectedFieldId]);

  useEffect(() => {
    loadArena();
  }, [loadArena]);

  const execute = async (hypothesisId: string, experimentType?: string, proposeOnly = false) => {
    setRunning(true);
    try {
      const res = await earthApi.runExperiment({
        event_id: eventId,
        field_id: selectedFieldId,
        hypothesis_id: hypothesisId,
        experiment_type: experimentType,
        propose_only: proposeOnly,
      });
      setLastRun(res);
      loadArena();
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">SCIENTIFIC HYPOTHESIS ARENA</span>
          <h3 className="h3" style={{ margin: '6px 0 0', color: '#f8fafc' }}>
            {t('競爭假設與科學實驗競技場', 'Competing Hypothesis Arena')}
          </h3>
        </div>
        <button className="eci-btn secondary" disabled={running} onClick={() => execute(activeHypothesis, undefined, true)}>
          {t('AI 建議下一個實驗', 'Propose Next Experiment')}
        </button>
      </div>

      {arena && (
        <p style={{ fontSize: 12.5, color: '#cbd5e1', marginTop: 0 }}>
          {arena.research_question}
        </p>
      )}

      {lastRun && (
        <div className="eci-card active">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>{lastRun.experiment_type}</strong>
            <span className={`eci-badge ${lastRun.executed ? '' : 'warn'}`}>{lastRun.status}</span>
          </div>
          <p style={{ fontSize: 12.5, margin: '6px 0' }}>{lastRun.summary}</p>
          <div style={{ fontSize: 11.5, color: '#67e8f9', fontFamily: 'var(--f-mono, monospace)' }}>
            Hypothesis Status: {lastRun.hypothesis_status_after} · Evaluation: {lastRun.evaluation_outcome}
            {lastRun.evidence_ids.length > 0 && ` · Evidence: ${lastRun.evidence_ids.join(', ')}`}
          </div>
        </div>
      )}

      {(arena?.hypotheses || []).map((h) => (
        <div
          key={h.hypothesis_id}
          className={`eci-card${activeHypothesis === h.hypothesis_id ? ' active' : ''}`}
          onClick={() => setActiveHypothesis(h.hypothesis_id)}
          style={{ cursor: 'pointer' }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
            <strong>{h.hypothesis_id}</strong>
            <span className="eci-badge warn">{h.status}</span>
          </div>
          <p style={{ fontSize: 12.5, color: '#e2e8f0', margin: '6px 0' }}>{h.description}</p>
          <div style={{ fontSize: 11.5, color: '#94a3b8' }}>
            Missing: {h.missing_evidence.join(', ')}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
            <button
              className="eci-btn"
              disabled={running}
              onClick={(e) => {
                e.stopPropagation();
                execute(h.hypothesis_id, h.available_experiments[0]?.experiment_type, false);
              }}
            >
              {running ? t('執行中…', 'Running…') : t('執行科學實驗', 'Run Experiment')}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
