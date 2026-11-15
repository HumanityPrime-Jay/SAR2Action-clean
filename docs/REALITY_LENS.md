# Reality Lens System (`RealityLensService`)

## Purpose
Separates what the satellite physically measured from competing hypotheses, known unknowns, and next required evidence—with `no_fake_confidence: true`.

## Four Lens Modes
1. **A · `OBSERVED`**: Physical radar backscatter and acquisition timestamps (e.g., `YL-CAND-03` `+7.55336 dB` VH change during `DURING_TYPHOON_WARNING`).
2. **B · `HYPOTHESES`**: Active competing physical/anthropogenic explanations for the observed signal.
3. **C · `UNKNOWN`**: Explicit gaps, unconfirmed crop damage, unresolved typhoon causality, and blocked cross-CRID comparisons.
4. **D · `NEXT_EVIDENCE`**: Actionable next observations (e.g., cloud-free Sentinel-2 optical pass, ground survey, or compatible NISAR CRID).

## API
- `GET /api/earth/events/{event_id}/lens/{lens}?field_id=...`
