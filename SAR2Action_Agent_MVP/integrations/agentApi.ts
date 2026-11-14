/** Typed request/response adapter. Allows C team to connect Agent UI without touching B's raster pipeline. */
import type {BBox,MapAction} from './mapActionBridge';
export type Pol='HH'|'HV'|'VV'|'VH';
export interface InvestigationRequest {
 scene_before:string;scene_after:string;polarization:Pol;bbox:BBox;
 query:string;locale:'zh-TW'|'en';audience:'general'|'technical';session_id:string;
 intent:'investigate'|'fingerprint'|'story'|'explain';
}
export interface AgentClaim {text:string;evidence_ids:string[];quantitative:boolean}
export interface InvestigationResponse {
 run_id:string;mode:'fixture'|'live';status:'completed'|'blocked'|'failed';
 observed_facts:AgentClaim[];possible_interpretations:string[];unknowns:string[];
 evidence_refs:string[];map_actions:MapAction[];warnings:string[];steps:Array<{tool:string;status:string}>;
 narrative:string;fingerprint?:{series:Array<{scene_id:string;median_db:number|null;n_valid:number}>;polarization:Pol};
 story?:EvidenceStory;
}
export interface EvidenceStory {
 story_id:string;status:'current'|'stale';mode:'fixture'|'live';source_signature:string;
 frames:Array<{key:string;title:string;caption:string;evidence_ids:string[];bbox:BBox;layer_id:string;time_label:string}>;
}
export async function callInvestigator(request:InvestigationRequest,signal?:AbortSignal):Promise<InvestigationResponse>{
 const res=await fetch('/api/agent/investigate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request),signal});
 if(!res.ok) throw Error(`Agent API failed (${res.status})`);
 return await res.json() as InvestigationResponse;
}
export async function fetchEvidence(id:string,signal?:AbortSignal):Promise<unknown>{
 if(!/^[\w-]{4,100}$/.test(id))throw Error('Invalid evidence ID');
 const res=await fetch('/api/evidence/'+encodeURIComponent(id),{signal});
 if(!res.ok)throw Error(`Evidence unavailable (${res.status})`);
 return await res.json();
}
export function assertEvidenceLinked(response:InvestigationResponse):void {
 const evidence=new Set(response.evidence_refs);
 for(const claim of response.observed_facts){
  if(claim.quantitative && (!claim.evidence_ids.length || claim.evidence_ids.some(id=>!evidence.has(id))))
   throw Error('Quantitative claim lacks a validated evidence ID');
 }
}
