/** Bridge for C-team's existing React/MapLibre UI. No LLM-generated JavaScript is ever executed. */
export interface BBox { west:number; south:number; east:number; north:number }
export type LayerId='before'|'after'|'difference'|'quality';
export type MapAction =
  | {type:'map.focus_bbox';payload:{bbox:BBox}}
  | {type:'map.highlight_aoi';payload:{bbox:BBox}}
  | {type:'map.set_layer';payload:{layer_id:LayerId}}
  | {type:'fingerprint.open';payload:{evidence_id:string}}
  | {type:'evidence.open';payload:{evidence_id:string}}
  | {type:'story.open';payload:{story_id:string}};

export interface MapLibreSubset {
  fitBounds(bounds:[[number,number],[number,number]],options?:Record<string,unknown>):void;
}
export interface UIBridge {
  map:MapLibreSubset;
  setHighlightedAOI(bbox:BBox):void;
  setLayer(layer:LayerId):void;
  openFingerprint(evidenceId:string):void;
  openEvidence(evidenceId:string):void;
  openStory(storyId:string):void;
  hasEvidence(evidenceId:string):boolean;
  hasStory(storyId:string):boolean;
}
export interface ActionLog {at:number;action:MapAction;state:'executed'|'denied';reason?:string}
const layerAllowlist=new Set<LayerId>(['before','after','difference','quality']);
const validBox=(b:BBox):boolean =>
  !!b && [b.west,b.south,b.east,b.north].every(Number.isFinite) &&
  b.west>=-180 && b.east<=180 && b.south>=-90 && b.north<=90 &&
  b.west<b.east && b.south<b.north && b.east-b.west<=5 && b.north-b.south<=5;
const isSafeId=(s:unknown):s is string=>typeof s==='string' && /^[\w-]{4,100}$/.test(s);
/** Replay is rendering-only; it NEVER replays analysis API calls or destructive operations. */
export class VerifiedMapActionBus {
  private events: ActionLog[]=[];
  constructor(private ui:UIBridge) {}
  execute(a:MapAction):ActionLog {
    const denied=(reason:string):ActionLog=>{
      const e={at:Date.now(),action:a,state:'denied' as const,reason};this.events.push(e);return e;
    };
    try {
      switch(a.type){
        case 'map.focus_bbox':
          if(!validBox(a.payload?.bbox))return denied('invalid_aoi');
          this.ui.map.fitBounds([[a.payload.bbox.west,a.payload.bbox.south],[a.payload.bbox.east,a.payload.bbox.north]],{padding:70,maxZoom:13});break;
        case 'map.highlight_aoi':
          if(!validBox(a.payload?.bbox))return denied('invalid_aoi');
          this.ui.setHighlightedAOI(a.payload.bbox);break;
        case 'map.set_layer':
          if(!layerAllowlist.has(a.payload?.layer_id))return denied('layer_not_allowlisted');
          this.ui.setLayer(a.payload.layer_id);break;
        case 'fingerprint.open':
          if(!isSafeId(a.payload?.evidence_id)||!this.ui.hasEvidence(a.payload.evidence_id))return denied('unknown_evidence');
          this.ui.openFingerprint(a.payload.evidence_id);break;
        case 'evidence.open':
          if(!isSafeId(a.payload?.evidence_id)||!this.ui.hasEvidence(a.payload.evidence_id))return denied('unknown_evidence');
          this.ui.openEvidence(a.payload.evidence_id);break;
        case 'story.open':
          if(!isSafeId(a.payload?.story_id)||!this.ui.hasStory(a.payload.story_id))return denied('unknown_story');
          this.ui.openStory(a.payload.story_id);break;
        default: return denied('unsupported_action');
      }
    }catch{ return denied('UI_execution_error'); }
    const event={at:Date.now(),action:a,state:'executed' as const};
    this.events.push(event);this.events=this.events.slice(-200);return event;
  }
  log():ReadonlyArray<ActionLog>{return this.events.slice()}
  replaySafe():void {for (const e of this.events.slice()) if(e.state==='executed')this.execute(e.action)}
}
