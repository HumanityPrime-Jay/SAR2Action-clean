import React, { useCallback, useEffect, useState } from 'react';
import { useT } from '../../i18n';
import { useEarthContext } from '../EarthContext';
import { earthApi, type HypothesisArenaResponse, type RunHypothesisExperimentResponse } from '../api';
import { IndicatorTooltip } from './IndicatorTooltip';

export function ScientificHypothesisArena() {
  const t = useT();
  const { eventId, selectedFieldId, activeHypothesis, setActiveHypothesis, pushActionFeedback } = useEarthContext();
  const [arena, setArena] = useState<HypothesisArenaResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<RunHypothesisExperimentResponse | null>(null);

  const loadArena = useCallback(() => {
    earthApi.getArena(eventId, selectedFieldId).then(setArena).catch(() => {});
  }, [eventId, selectedFieldId]);

  useEffect(() => {
    loadArena();
  }, [loadArena]);

  const execute = async (hypothesisId: string, experimentType?: string, proposeOnly = false) => {
    setRunning(true);
    setActiveTool(experimentType || 'temporal_alignment_check');
    pushActionFeedback([`Executing ${experimentType || 'Hypothesis Experiment'} on ${selectedFieldId}`]);
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
      setActiveTool(null);
    }
  };

  return (
    <div className="eci-glass">
      <div className="eci-header">
        <div>
          <span className="eci-badge">SCIENTIFIC HYPOTHESIS ARENA</span>
          <h3 className="h3" style={{ margin: '5px 0 0', fontSize: 16, color: '#f8fafc' }}>
            {t('競爭假設與科學實驗競技場', 'Competing Hypothesis Arena')}
            <IndicatorTooltip indicatorKey="seasonal_ref" />
          </h3>
        </div>
        <button
          type="button"
          className="eci-btn secondary"
          disabled={running}
          onClick={() => execute(activeHypothesis, undefined, true)}
        >
          {t('建議下一個實驗', 'Propose Next Experiment')}
        </button>
      </div>

      {arena && (
        <p style={{ fontSize: 12.5, color: '#cbd5e1', marginTop: 0, marginBottom: 8 }}>
          {arena.research_question}
        </p>
      )}

      {/* Live Experiment Execution Stepper */}
      {(running || lastRun) && (
        <div className="eci-card active" style={{ marginBottom: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, marginBottom: 6 }}>
            <strong style={{ fontSize: 13 }}>
              {running ? `Tool Running: ${activeTool}` : lastRun?.experiment_type}
            </strong>
            <span className={`eci-badge ${lastRun?.executed ? 'ok' : 'warn'}`}>
              {running ? 'RUNNING_TOOL' : lastRun?.status}
            </span>
          </div>

          <div style={{ display: 'flex', gap: 4, fontSize: 10.5, color: '#94a3b8', marginBottom: 6, fontFamily: 'var(--f-mono, monospace)' }}>
            <span style={{ color: '#22d3ee' }}>1. START</span> →{' '}
            <span style={{ color: '#22d3ee' }}>2. TOOL ({activeTool || lastRun?.experiment_type})</span> →{' '}
            <span style={{ color: running ? '#94a3b8' : '#22d3ee' }}>3. EVIDENCE</span> →{' '}
            <span style={{ color: running ? '#94a3b8' : '#fb923c' }}>4. REVISION</span>
          </div>

          {lastRun && !running && (
            <>
              <p style={{ fontSize: 12, color: '#f1f5f9', margin: '4px 0' }}>{lastRun.summary}</p>
              <div style={{ fontSize: 11, color: '#67e8f9', fontFamily: 'var(--f-mono, monospace)' }}>
                Hypothesis Status: <b>{lastRun.hypothesis_status_after}</b> · Evaluation: <b>{lastRun.evaluation_outcome}</b>
                {lastRun.evidence_ids?.length > 0 && ` · Evidence: ${lastRun.evidence_ids.join(', ')}`}
              </div>
            </>
          )}
        </div>
      )}

      {(arena?.hypotheses || []).map((h) => {
        const supCount = h.supporting_evidence?.length || 1;
        const altCount = h.alternative_explanations?.length || 1;
        const missCount = h.missing_evidence?.length || 1;
        const total = Math.max(1, supCount + altCount + missCount);
        const toolName = h.available_experiments?.[0]?.tool || h.available_experiments?.[0]?.experiment_type || 'temporal_alignment_check';

        return (
          <div
            key={h.hypothesis_id}
            className={`eci-card${activeHypothesis === h.hypothesis_id ? ' active' : ''}`}
            onClick={() => setActiveHypothesis(h.hypothesis_id)}
            style={{ cursor: 'pointer' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
              <strong style={{ fontSize: 13 }}>{h.title || h.hypothesis_id}</strong>
              <span className="eci-badge warn">{h.status}</span>
            </div>

            <p style={{ fontSize: 12, color: '#e2e8f0', margin: '5px 0' }}>{h.description}</p>

            {/* Evidence Balance Visualization */}
            <div className="eci-balance-bar" title="Supporting vs Alternative vs Missing Evidence">
              <div style={{ width: `${(supCount / total) * 100}%`, background: '#22d3ee' }} />
              <div style={{ width: `${(altCount / total) * 100}%`, background: '#fb923c' }} />
              <div style={{ width: `${(missCount / total) * 100}%`, background: '#475569' }} />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: '#cbd5e1', marginTop: 4 }}>
              {h.supporting_evidence?.length > 0 && (
                <div>
                  <span style={{ color: '#22d3ee' }}>✓ Supporting:</span> {h.supporting_evidence.slice(0, 2).join(' · ')}
                </div>
              )}
              {h.alternative_explanations?.length > 0 && (
                <div>
                  <span style={{ color: '#fdba74' }}>⇄ Alternative:</span> {h.alternative_explanations.slice(0, 2).join(' · ')}
                </div>
              )}
              <div style={{ color: '#94a3b8' }}>
                Missing: {(h.missing_evidence || []).join(', ')}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
              <span className="mono" style={{ fontSize: 10.5, color: '#67e8f9' }}>
                Tool: {toolName}
              </span>
              <button
                type="button"
                className="eci-btn"
                disabled={running}
                onClick={(e) => {
                  e.stopPropagation();
                  execute(h.hypothesis_id, h.available_experiments?.[0]?.experiment_type, false);
                }}
              >
                {running ? t('執行中…', 'Running…') : t('執行科學實驗', 'Run Experiment')}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
