#!/usr/bin/env python3
"""Create a self-contained interactive viewer for account_table_lineage.json."""

import json
from pathlib import Path

from html_graph_descriptions import describe_graph


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "output/account_table_lineage.json"
OUTPUT = ROOT / "output/account_table_lineage.html"

HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ACCOUNT Lineage | Ultracs to CDP</title>
<style>
:root{color-scheme:light;--ink:#142f36;--muted:#5e7378;--line:#d7e2df;--paper:#eef4f1;--panel:#fff;--green:#16784f;--teal:#167c83;--blue:#3f6f91;--amber:#bd7a2a;--coral:#b85648;--violet:#76619a;--shadow:0 10px 30px #183b3820}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{font-family:"Aptos","Segoe UI",sans-serif;color:var(--ink);background:var(--paper);display:grid;grid-template-rows:auto auto minmax(0,1fr);overflow:hidden}
header{display:flex;align-items:center;gap:14px;padding:13px 18px;background:#fff;border-bottom:1px solid var(--line);flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:11px;margin-right:8px}
.mark{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;background:var(--green);color:#fff;font-size:12px;font-weight:800}
h1{font-size:18px;line-height:1.1;margin:0;font-weight:720}
.subtitle{display:block;margin-top:4px;color:var(--muted);font-size:11px;font-weight:500}
.search{height:37px;width:min(370px,32vw);padding:0 12px;border:1px solid #b9cbc6;border-radius:8px;background:#fbfdfc;font:inherit;font-size:13px;outline:none}
.search:focus{border-color:var(--teal);box-shadow:0 0 0 3px #167c831c}
.toolbar{display:flex;align-items:center;gap:7px}
button{font:inherit;font-size:12px;font-weight:650;color:var(--ink);border:1px solid #b9cbc6;background:white;padding:8px 10px;border-radius:7px;cursor:pointer}
button:hover{background:#edf6f2;border-color:#7da99a}
button:focus-visible{outline:3px solid #167c8344;outline-offset:1px}
#stats{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}
.confidence-note{font-size:9px;color:var(--muted);white-space:nowrap}
.confidence-filter{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0;padding:4px 7px;border:1px solid var(--line);border-radius:5px}.confidence-filter legend{padding:0 4px;color:#50656a;font-size:9px;font-weight:750}.confidence-filter label{display:flex;align-items:center;gap:3px;color:#50656a;font-size:9px;white-space:nowrap}.confidence-filter input{accent-color:var(--green);margin:0}
.gap-strip{display:flex;gap:8px;align-items:center;padding:8px 18px;background:#fffaf0;border-bottom:1px solid #eadbbd;overflow:auto;white-space:nowrap}
.gap-title{font-size:11px;font-weight:800;color:#815a20;text-transform:uppercase}
.gap-chip{border:1px solid #e1c78f;background:#fff;border-radius:20px;padding:5px 9px;color:#694d21;font-size:11px;cursor:pointer}
.gap-chip:hover{background:#fff3d9}
main{display:grid;grid-template-columns:minmax(0,1fr) 355px;gap:12px;padding:12px;min-height:0}
.graph-panel,.inspector{min-height:0;background:var(--panel);border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow)}
.graph-panel{position:relative;overflow:hidden;background-color:#f9fcfa;background-image:radial-gradient(#adc3bd 0.7px,transparent 0.7px);background-size:20px 20px}
#graph{width:100%;height:100%;display:block;touch-action:none;cursor:grab}
#graph.dragging{cursor:grabbing}
.graph-hint{position:absolute;left:14px;bottom:12px;padding:7px 10px;background:#ffffffdd;border:1px solid var(--line);border-radius:7px;color:var(--muted);font-size:10px;pointer-events:none}
.inspector{display:flex;flex-direction:column;overflow:hidden}
.panel-head{padding:15px 15px 12px;border-bottom:1px solid var(--line)}
.panel-head h2{font-size:13px;margin:0;font-weight:760}
.panel-head p{font-size:11px;line-height:1.45;color:var(--muted);margin:6px 0 0}
#details{padding:13px 15px;overflow:auto;min-height:0}
.empty{padding:12px;background:#f2f7f5;border-radius:8px;color:#46615f;font-size:12px;line-height:1.55}
.selected-type{font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;color:var(--green)}
.selected-name{font-size:16px;line-height:1.3;font-weight:750;margin:5px 0 3px;overflow-wrap:anywhere}
.node-id{font-family:Consolas,"Courier New",monospace;font-size:10px;line-height:1.45;color:var(--muted);overflow-wrap:anywhere;margin:0 0 12px}
.section-title{margin:14px 0 7px;font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:800;color:#516a6b}
.kv{display:grid;grid-template-columns:92px minmax(0,1fr);gap:6px 9px;font-size:11px;line-height:1.45;padding:7px 0;border-top:1px solid #edf2f0}
.key{color:var(--muted);overflow-wrap:anywhere}.value{overflow-wrap:anywhere;white-space:pre-wrap}
.relation{display:grid;grid-template-columns:1fr;gap:3px;margin:6px 0;padding:8px 9px;border:1px solid #e1e9e6;border-radius:7px;background:#fcfefd}
.relation-type{font-size:10px;font-weight:800;color:var(--teal)}
.relation-peer{font-size:11px;overflow-wrap:anywhere}
.relation-direction{color:#94a4a1;padding:0 4px}
.column{margin:7px 0;padding:9px;border:1px solid #dce9e3;border-left:3px solid var(--green);border-radius:6px;background:#f8fcf9}
.column strong{display:block;font-size:11px;margin-bottom:5px}
.column-meta{font-size:10px;line-height:1.5;color:#4b6463}
.confidence{display:inline-block;padding:2px 6px;border-radius:10px;background:#e9f3e9;color:#346344;font-size:9px;font-weight:800}
.confidence.inferred,.confidence.candidate_composite_key{background:#fff1d8;color:#855a19}
.description-origin{display:inline-block;margin:5px 0;padding:2px 6px;border-radius:9px;background:#e6f1ee;color:#315f55;font-size:9px;font-weight:750}
.description-text{font-size:11px;line-height:1.5;color:#41595a;white-space:pre-wrap;overflow-wrap:anywhere}
.gap-card{margin:8px 0;padding:10px;border:1px solid #eadbbd;border-left:3px solid var(--amber);border-radius:7px;background:#fffaf0}
.gap-card h3{margin:0 0 5px;font-size:11px;color:#674b20}
.gap-card p{margin:0;color:#5d5547;font-size:10px;line-height:1.5}
.legend{position:absolute;top:12px;left:12px;display:flex;gap:7px;flex-wrap:wrap;max-width:70%;pointer-events:none}
.legend-item{display:flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid #dce6e2;border-radius:12px;background:#fffffff0;font-size:9px;color:#4b6264}
.dot{width:8px;height:8px;border-radius:50%}
.filters{display:flex;align-items:center;gap:7px;flex-wrap:wrap;max-width:min(650px,45vw)}
.filter{display:flex;align-items:center;gap:4px;color:#50656a;font-size:10px;white-space:nowrap}
.filter input{accent-color:var(--green);margin:0}
@media(max-width:920px){main{grid-template-columns:minmax(0,1fr) 300px}.filters{display:none}.search{width:min(300px,36vw)}}
@media(max-width:680px){body{grid-template-rows:auto auto minmax(0,1fr)}header{gap:8px;padding:10px}.brand{width:100%}.search{width:100%;order:3}.toolbar{order:4}#stats{margin-left:auto}.gap-strip{padding:7px 10px}main{grid-template-columns:1fr;grid-template-rows:minmax(0,1fr) 38vh;padding:8px;gap:8px}.inspector{min-height:0}.legend{max-width:90%}.graph-hint{font-size:9px}}
</style>
</head>
<body>
<header>
  <div class="brand"><div class="mark">A</div><h1>ACCOUNT lineage<span class="subtitle">Ultracs DWACC → HVR → accounts-v1</span></h1></div>
  <input id="search" class="search" type="search" placeholder="Search nodes, keys, columns, evidence…" aria-label="Search account lineage">
  <div id="filters" class="filters" aria-label="Filter node types"></div>
  <fieldset id="confidenceFilter" class="confidence-filter" aria-label="Filter relationships by confidence">
    <legend>Relationship confidence</legend>
    <label><input type="checkbox" data-confidence value="explicit" checked>Explicit / confirmed · 95%</label>
    <label><input type="checkbox" data-confidence value="calculated" checked>Calculated · 90%</label>
    <label><input type="checkbox" data-confidence value="declared_source" checked>Declared source · 85%</label>
    <label><input type="checkbox" data-confidence value="inferred" checked>Inferred / candidate · 60%</label>
    <label><input type="checkbox" data-confidence value="unconfirmed" checked>Unconfirmed · 50%</label>
    <label><input type="checkbox" data-confidence value="not_rated" checked>Not rated</label>
  </fieldset>
  <div class="toolbar">
    <button id="fit" title="Fit all nodes in the graph">Fit</button>
    <button id="zoomIn" title="Zoom in">+</button>
    <button id="zoomOut" title="Zoom out">−</button>
    <button id="reset" title="Restore node positions and view">Reset</button>
  </div>
  <span class="confidence-note">Evidence confidence % is heuristic, not probability</span>
  <span id="stats"></span>
</header>
<div id="gapStrip" class="gap-strip"><span class="gap-title">Open gaps</span></div>
<main>
  <section class="graph-panel" aria-label="Interactive account lineage graph">
    <canvas id="graph"></canvas>
    <div id="legend" class="legend"></div>
    <div class="graph-hint">Recorded edge direction shown · drag nodes · drag empty canvas to pan · scroll to zoom · click a node for details</div>
  </section>
  <aside class="inspector">
    <div class="panel-head"><h2 id="panelTitle">Graph Inspector</h2><p id="panelSubtitle">Select a node to inspect its properties and connected relationships. The gap register is below.</p></div>
    <div id="details"></div>
  </aside>
</main>
<script id="account-data" type="application/json">__GRAPH_DATA__</script>
<script>
const graph=JSON.parse(document.getElementById('account-data').textContent);
const nodes=graph.nodes,edges=graph.edges;
function confidencePercent(value){return ({explicit:95,confirmed:95,confirmed_calculated:90,declared_source:85,inferred:60,unconfirmed:50})[String(value||'').toLowerCase()]??null}
function confidenceLabel(value){const score=confidencePercent(value);return score===null?String(value||'unspecified')+' (not rated)':String(value||'unspecified')+' ('+score+'%)'}
function confidenceBucket(value){const label=String(value||'').toLowerCase();if(['explicit','confirmed'].includes(label))return 'explicit';if(label==='confirmed_calculated')return 'calculated';if(label==='declared_source')return 'declared_source';if(['inferred','candidate_composite_key'].includes(label))return 'inferred';if(label==='unconfirmed')return 'unconfirmed';return 'not_rated'}
let activeConfidenceBuckets=new Set(['explicit','calculated','declared_source','inferred','unconfirmed','not_rated']);
function confidenceAllowed(value){return activeConfidenceBuckets.has(confidenceBucket(value))}
function updateConfidenceBuckets(){activeConfidenceBuckets=new Set([...document.querySelectorAll('#confidenceFilter [data-confidence]:checked')].map(input=>input.value))}
const palette={
  MV_FILE:'#367a8a',PROGRAM:'#315f79',EXTRACT_FILE:'#bb7a2e',
  HVR_CHANNEL:'#6d5b91',HVR_LOCATION:'#647d9a',S3_PATH:'#16877f',
  CDP_PRODUCT:'#34734c',AIRFLOW_DAG:'#437d56',AIRFLOW_TASK:'#579266',
  DBT_SOURCE:'#b18430',DBT_MODEL:'#bf7250',SNOWFLAKE_RELATION:'#328265',
  SCHEMACHANGE_MIGRATION:'#9a687f',SNOWFLAKE_TABLE:'#328265'
};
const edgePalette={
  READS_FROM:'#4c8091',WRITES_TO:'#bb7a2e',CALLS:'#75858a',CARRIED_BY:'#765f91',
  CAPTURES_FROM:'#527b98',INTEGRATES_TO:'#607e9c',COPIES_TO:'#16877f',LANDS_IN:'#34734c',
  CONTAINS:'#477c55',CONTAINS_TASK:'#64916e',PRECEDES:'#77847f',COPIES_FROM:'#18847d',
  LOADS_FROM:'#4e8d85',LOADS_TO:'#34734c',EXECUTES_DBT:'#aa7346',DEPENDS_ON:'#b27459',
  RESOLVES_TO:'#b18430',MATERIALIZES_AS:'#328265',MIGRATES:'#9a687f'
};
const canvas=document.getElementById('graph'),ctx=canvas.getContext('2d');
const filters=document.getElementById('filters'),search=document.getElementById('search'),stats=document.getElementById('stats');
const details=document.getElementById('details'),panelTitle=document.getElementById('panelTitle'),panelSubtitle=document.getElementById('panelSubtitle');
const types=[...new Set(nodes.map(node=>node.type))].sort();
const typeGroups={
  MV_FILE:0,PROGRAM:1,EXTRACT_FILE:2,HVR_CHANNEL:3,HVR_LOCATION:4,S3_PATH:5,
  CDP_PRODUCT:6,AIRFLOW_DAG:6,AIRFLOW_TASK:7,DBT_SOURCE:8,DBT_MODEL:9,
  SCHEMACHANGE_MIGRATION:9,SNOWFLAKE_TABLE:10,SNOWFLAKE_RELATION:10
};
const laneNames=['Source file','BASIC program','Extract','HVR channel','HVR location','S3 path','Product / DAG','Airflow task','dbt source','dbt model / migration','Snowflake relation'];
const groupLists=new Map();
for(const node of nodes){const group=typeGroups[node.type]??6;if(!groupLists.has(group))groupLists.set(group,[]);groupLists.get(group).push(node)}
for(const list of groupLists.values())list.sort((a,b)=>displayName(a).localeCompare(displayName(b)));
const positions=new Map();let worldWidth=2440,worldHeight=1100;
for(const [group,list] of groupLists){
  list.forEach((node,index)=>{
    let lane=group;
    if(node.type==='HVR_CHANNEL'){
      if(node.id.includes('ult_sf_acc'))lane=3;
      else if(node.id.includes('ult_s3_acc'))lane=3;
    }
    if(node.id==='hvr:location:fs_hvr_conv')lane=4;
    if(node.type==='S3_PATH'&&node.id.includes('HVR:ultracs:dwacc'))lane=5;
    positions.set(node.id,{x:105+lane*155,y:90+index*105});
    worldHeight=Math.max(worldHeight,120+index*105);
  });
}
const initialPositions=new Map([...positions].map(([id,p])=>[id,{x:p.x,y:p.y}]));
const enabled=new Set(types),nodeMap=new Map(nodes.map(node=>[node.id,node]));
let width=1,height=1,dpr=1,scale=1,offsetX=0,offsetY=0,drag=null,selected=null,hovered=null,searchMatches=new Set();

function displayName(node){
  const p=node.properties||{};
  if(p.name)return String(p.name);
  if(p.task_id)return String(p.task_id);
  if(p.path)return String(p.path);
  return node.id.split(':').slice(-1)[0];
}
function resize(){
  const rect=canvas.getBoundingClientRect();dpr=window.devicePixelRatio||1;width=rect.width;height=rect.height;
  canvas.width=Math.max(1,Math.round(width*dpr));canvas.height=Math.max(1,Math.round(height*dpr));
  ctx.setTransform(dpr,0,0,dpr,0,0);fit(false);draw();
}
function bounds(){
  const pts=[...positions.values()];
  return{x0:Math.min(...pts.map(p=>p.x))-90,y0:Math.min(...pts.map(p=>p.y))-75,x1:Math.max(...pts.map(p=>p.x))+200,y1:Math.max(...pts.map(p=>p.y))+75};
}
function fit(render=true){
  const b=bounds(),pad=62,bw=b.x1-b.x0,bh=b.y1-b.y0;
  scale=Math.max(.07,Math.min(1.15,(width-pad*2)/bw,(height-pad*2)/bh));
  offsetX=(width-bw*scale)/2-b.x0*scale;offsetY=(height-bh*scale)/2-b.y0*scale;
  if(render)draw();
}
function fitVisible(){
  const visible=nodes.filter(node=>visibleIds().has(node.id));if(!visible.length)return;
  const points=visible.map(node=>positions.get(node.id));
  const b={x0:Math.min(...points.map(p=>p.x))-48,y0:Math.min(...points.map(p=>p.y))-48,x1:Math.max(...points.map(p=>p.x))+175,y1:Math.max(...points.map(p=>p.y))+48};
  const bw=b.x1-b.x0,bh=b.y1-b.y0,pad=42;
  scale=Math.max(.07,Math.min(1.25,(width-pad*2)/bw,(height-pad*2)/bh));
  offsetX=(width-bw*scale)/2-b.x0*scale;offsetY=(height-bh*scale)/2-b.y0*scale;
}
function zoomAt(factor,x=width/2,y=height/2){
  const wx=(x-offsetX)/scale,wy=(y-offsetY)/scale;scale=Math.max(.2,Math.min(2.5,scale*factor));
  offsetX=x-wx*scale;offsetY=y-wy*scale;draw();
}
function visibleIds(){
  let allowed=new Set(nodes.filter(node=>enabled.has(node.type)).map(node=>node.id));
  const query=search.value.trim().toLowerCase();
  if(query){
    const hits=new Set(nodes.filter(node=>(node.id+' '+JSON.stringify(node.properties)).toLowerCase().includes(query)).map(node=>node.id));
    searchMatches=hits;const nearby=new Set(hits);
    for(const edge of edges){if(hits.has(edge.source))nearby.add(edge.target);if(hits.has(edge.target))nearby.add(edge.source)}
    allowed=new Set([...allowed].filter(id=>nearby.has(id)));
  }else searchMatches.clear();
  return allowed;
}
function shorten(value,max=29){value=String(value);return value.length>max?value.slice(0,max-1)+'…':value}
function draw(){
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);ctx.fillStyle='#f9fcfa';ctx.fillRect(0,0,width,height);
  const allowed=visibleIds();
  ctx.save();ctx.translate(offsetX,offsetY);ctx.scale(scale,scale);
  for(let lane=0;lane<laneNames.length;lane++){
    const x=105+lane*155;
    if(scale>.42){ctx.fillStyle='#849994';ctx.font=`700 ${10/scale}px Aptos, Segoe UI, sans-serif`;ctx.fillText(laneNames[lane].toUpperCase(),x,30)}
    ctx.strokeStyle='#e2ebe7';ctx.lineWidth=1/scale;ctx.beginPath();ctx.moveTo(x-14,42);ctx.lineTo(x-14,worldHeight);ctx.stroke();
  }
  let visibleEdgeCount=0;
  for(const edge of edges){
    if(!confidenceAllowed(edge.properties?.confidence))continue;
    if(!allowed.has(edge.source)||!allowed.has(edge.target))continue;
    visibleEdgeCount++;
    const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)continue;
    const selectedEdge=selected&&(edge.source===selected||edge.target===selected);
    const alpha=selected&&!selectedEdge?.12:.63;ctx.globalAlpha=alpha;ctx.strokeStyle=edgePalette[edge.type]||'#869894';ctx.fillStyle=edgePalette[edge.type]||'#869894';
    const dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy)||1,ux=dx/len,uy=dy/len;
    const sx=a.x+ux*26,sy=a.y+uy*26,ex=b.x-ux*29,ey=b.y-uy*29;
    ctx.lineWidth=(selectedEdge?2:1.25)/scale;ctx.beginPath();ctx.moveTo(sx,sy);ctx.lineTo(ex,ey);ctx.stroke();
    const angle=Math.atan2(ey-sy,ex-sx),arrow=7/scale;ctx.beginPath();ctx.moveTo(ex,ey);ctx.lineTo(ex-arrow*Math.cos(angle-.45),ey-arrow*Math.sin(angle-.45));ctx.lineTo(ex-arrow*Math.cos(angle+.45),ey-arrow*Math.sin(angle+.45));ctx.closePath();ctx.fill();
    if(selectedEdge||scale>.7){
      const mx=(sx+ex)/2,my=(sy+ey)/2;ctx.font=`700 ${9/scale}px Aptos, Segoe UI, sans-serif`;
      const label=edge.type;const tw=ctx.measureText(label).width;ctx.fillStyle='#ffffffed';ctx.fillRect(mx-tw/2-4/scale,my-7/scale,tw+8/scale,14/scale);
      ctx.fillStyle=edgePalette[edge.type]||'#667';ctx.textAlign='center';ctx.fillText(label,mx,my+3/scale);ctx.textAlign='left';
    }
  }
  ctx.globalAlpha=1;
  for(const node of nodes){
    if(!allowed.has(node.id))continue;const p=positions.get(node.id);if(!p)continue;
    const r=9/scale,isSelected=node.id===selected,isHit=searchMatches.has(node.id),isHovered=node.id===hovered;
    ctx.beginPath();ctx.arc(p.x,p.y,r,0,Math.PI*2);ctx.fillStyle=palette[node.type]||'#60777a';ctx.fill();
    if(isSelected||isHit||isHovered){ctx.lineWidth=(isSelected?3:2)/scale;ctx.strokeStyle=isSelected?'#102f32':isHit?'#d08a2c':'#ffffff';ctx.stroke()}
    if(scale>.48||isSelected||isHovered){
      ctx.textAlign='center';ctx.font=`700 ${10/scale}px Aptos, Segoe UI, sans-serif`;ctx.fillStyle='#fff';ctx.fillText(shorten(node.type.replaceAll('_',' '),22),p.x,p.y+3/scale);
      ctx.textAlign='left';ctx.font=`650 ${11/scale}px Aptos, Segoe UI, sans-serif`;ctx.fillStyle='#18383b';ctx.fillText(shorten(displayName(node),26),p.x+r+7/scale,p.y+4/scale);
    }
  }
  ctx.restore();stats.textContent=`${allowed.size} / ${nodes.length} nodes · ${visibleEdgeCount} / ${edges.length} relationships`;
}
function point(event){const r=canvas.getBoundingClientRect();return{x:(event.clientX-r.left-offsetX)/scale,y:(event.clientY-r.top-offsetY)/scale}}
function nodeAt(p){let found=null,best=25/scale;for(const node of nodes){if(!enabled.has(node.type))continue;const q=positions.get(node.id);const d=Math.hypot(q.x-p.x,q.y-p.y);if(d<best){best=d;found=node}}return found}
function addSectionTitle(parent,title){const h=document.createElement('div');h.className='section-title';h.textContent=title;parent.append(h)}
function addText(parent,className,text){const el=document.createElement('div');el.className=className;el.textContent=text;parent.append(el);return el}
function renderGaps(){
  const strip=document.getElementById('gapStrip');
  for(const gap of graph.gap_register||[]){const button=document.createElement('button');button.className='gap-chip';button.textContent=gap.id+' · '+gap.title;button.title=gap.impact;button.addEventListener('click',()=>showGap(gap));strip.append(button)}
}
function showGap(gap){
  selected=null;panelTitle.textContent=gap.id+' · '+gap.title;panelSubtitle.textContent='Open lineage question';details.replaceChildren();
  addText(details,'selected-type',gap.status.replaceAll('_',' '));addText(details,'node-id',gap.id);
  addSectionTitle(details,'What is known');addText(details,'empty',gap.details);
  addSectionTitle(details,'Why it matters');addText(details,'empty',gap.impact);
  addSectionTitle(details,'Evidence');addText(details,'empty',gap.evidence);draw();
}
function renderNode(node){
  selected=node.id;panelTitle.textContent='Node Inspector';panelSubtitle.textContent='Recorded properties and directly connected graph relationships.';details.replaceChildren();
  addText(details,'selected-type',node.type.replaceAll('_',' '));addText(details,'selected-name',displayName(node));addText(details,'node-id',node.id);
  addText(details,'confidence',`Evidence confidence: ${confidenceLabel(node.properties?.confidence)}`);
  addSectionTitle(details,'Description');addText(details,'description-text',node.properties?.html_description||'Description unavailable.');addText(details,'description-origin',node.properties?.html_description_origin||'Generated');
  const adjacent=edges.filter(edge=>(edge.source===node.id||edge.target===node.id)&&confidenceAllowed(edge.properties?.confidence));
  addSectionTitle(details,`Relationships · ${adjacent.length}`);
  if(!adjacent.length)addText(details,'empty','No relationships in this graph.');
  for(const edge of adjacent){
    const forward=edge.source===node.id,peer=nodeMap.get(forward?edge.target:edge.source),card=document.createElement('div');card.className='relation';
    addText(card,'relation-type',edge.type+(forward?' · outgoing':' · incoming'));
    addText(card,'relation-peer',(forward?'→ ':'← ')+(peer?displayName(peer):forward?edge.target:edge.source));
    addText(card,'confidence',confidenceLabel(edge.properties?.confidence));
    addText(card,'description-text',edge.properties?.html_description||'Description unavailable.');
    addText(card,'description-origin',edge.properties?.html_description_origin||'Generated');
    details.append(card);
  }
  const props={...node.properties};const columns=props.related_columns;delete props.related_columns;delete props.source_paths;delete props.html_description;delete props.html_description_origin;delete props.description;
  addSectionTitle(details,'Properties');
  for(const [key,value] of Object.entries(props)){
    const row=document.createElement('div');row.className='kv';addText(row,'key',key==='confidence'?'evidence confidence':key);addText(row,'value',key==='confidence'?confidenceLabel(value):typeof value==='string'?value:JSON.stringify(value));details.append(row);
  }
  if(Array.isArray(columns)){
    addSectionTitle(details,`Related columns · ${columns.length}`);
    for(const column of columns){
      const card=document.createElement('div');card.className='column';
      const title=document.createElement('strong');title.textContent=column.business_field;card.append(title);
      const meta=document.createElement('div');meta.className='column-meta';
      const description=column.description||`${column.business_field} is mapped from ${column.source_locator||'the recorded source field'} through DWACC and HVR to the listed dbt column.`;
      const descriptionOrigin=column.description?'Repository sourced':'Generated';
      const dbtTargets=(column.dbt_targets||[]).map(target=>`${target.stage}: ${target.model}.${target.column} (${target.data_type||'type not declared'})`).join('\n');
      meta.textContent=`Description (${descriptionOrigin}): ${description}\nSource: ${column.source_locator||'not separately identified'}\nDWACC header: ${column.extract_column||column.extract_columns?.join(' + ')||'not separately recorded'}\nHVR parameter: ${column.hvr_param_column||column.hvr_param_columns?.join(' + ')}${column.hvr_param_position?` (position ${column.hvr_param_position})`:''}\nPrimary dbt target: ${column.dbt_column||column.dbt_columns?.join(' + ')}\nAll dbt targets:\n${dbtTargets||'not found'}\nEvidence confidence: ${confidenceLabel(column.confidence)}`;card.append(meta);details.append(card);
    }
  }
  draw();
}
function renderInitial(){
  selected=null;panelTitle.textContent='Graph Inspector';panelSubtitle.textContent='Select a node to inspect its properties and connected relationships.';details.replaceChildren();
  addText(details,'empty','Recorded arrows follow schema direction. Some source-to-consumer walks require traversing READS_FROM or DEPENDS_ON in reverse.');
  addSectionTitle(details,'Open Sections');
  for(const gap of graph.gap_register||[]){
    const card=document.createElement('div');card.className='gap-card';const title=document.createElement('h3');title.textContent=gap.id+' · '+gap.title;card.append(title);const body=document.createElement('p');body.textContent=gap.impact;card.append(body);card.addEventListener('click',()=>showGap(gap));details.append(card);
  }
  draw();
}
for(const type of types){
  const label=document.createElement('label');label.className='filter';const input=document.createElement('input');input.type='checkbox';input.checked=true;input.addEventListener('change',()=>{if(input.checked)enabled.add(type);else enabled.delete(type);fitVisible();draw()});label.append(input,document.createTextNode(type.replaceAll('_',' ')));filters.append(label);
}
for(const type of types){const item=document.createElement('span');item.className='legend-item';const dot=document.createElement('i');dot.className='dot';dot.style.background=palette[type]||'#60777a';item.append(dot,document.createTextNode(type.replaceAll('_',' ')));document.getElementById('legend').append(item)}
canvas.addEventListener('pointerdown',event=>{canvas.setPointerCapture(event.pointerId);const node=nodeAt(point(event));if(node){const p=positions.get(node.id);drag={mode:'node',id:node.id,x:event.clientX,y:event.clientY,nx:p.x,ny:p.y,moved:false};renderNode(node)}else drag={mode:'pan',x:event.clientX,y:event.clientY,ox:offsetX,oy:offsetY,moved:false};canvas.classList.add('dragging')});
canvas.addEventListener('pointermove',event=>{
  if(!drag){const node=nodeAt(point(event));hovered=node?.id||null;draw();return}
  const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>2)drag.moved=true;
  if(drag.mode==='node')positions.set(drag.id,{x:drag.nx+dx/scale,y:drag.ny+dy/scale});else{offsetX=drag.ox+dx;offsetY=drag.oy+dy}draw();
});
canvas.addEventListener('pointerup',event=>{if(drag?.mode==='node'&&!drag.moved)renderNode(nodeMap.get(drag.id));drag=null;canvas.classList.remove('dragging');if(canvas.hasPointerCapture(event.pointerId))canvas.releasePointerCapture(event.pointerId)});
canvas.addEventListener('pointercancel',()=>{drag=null;canvas.classList.remove('dragging')});
canvas.addEventListener('wheel',event=>{event.preventDefault();const r=canvas.getBoundingClientRect();zoomAt(event.deltaY<0?1.1:.91,event.clientX-r.left,event.clientY-r.top)},{passive:false});
search.addEventListener('input',()=>{fitVisible();draw()});
document.getElementById('confidenceFilter').addEventListener('change',()=>{updateConfidenceBuckets();if(selected)renderNode(nodeMap.get(selected));else draw()});
document.getElementById('fit').addEventListener('click',()=>fit());
document.getElementById('zoomIn').addEventListener('click',()=>zoomAt(1.18));
document.getElementById('zoomOut').addEventListener('click',()=>zoomAt(.84));
document.getElementById('reset').addEventListener('click',()=>{for(const [id,p] of initialPositions)positions.set(id,{x:p.x,y:p.y});search.value='';document.querySelectorAll('#confidenceFilter [data-confidence]').forEach(input=>input.checked=true);updateConfidenceBuckets();for(const type of types)enabled.add(type);for(const input of filters.querySelectorAll('input'))input.checked=true;renderInitial();fit()});
window.addEventListener('resize',resize);
renderGaps();renderInitial();resize();
</script>
</body>
</html>
'''


def main() -> None:
    graph = describe_graph(json.loads(INPUT.read_text(encoding="utf-8")))
    embedded = json.dumps(graph, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    OUTPUT.write_text(HTML.replace("__GRAPH_DATA__", embedded), encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges)")


if __name__ == "__main__":
    main()