const fs=require("fs");
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,WidthType,ShadingType,BorderStyle,ImageRun,AlignmentType,HeadingLevel,LevelFormat,PageBreak,VerticalAlign}=require("docx");
const TEAL="1A939B", LIGHT="EFF6F9", INK="0B0B0B", INK2="52514E", PALE="F7F7F5", FILL="B45309";
const FONT="Calibri"; const PAGE_W=12240, MARGIN=864, CONTENT=PAGE_W-2*MARGIN;
const nb={style:BorderStyle.NONE,size:0,color:"FFFFFF"}; const noB={top:nb,bottom:nb,left:nb,right:nb};
const gb={style:BorderStyle.SINGLE,size:24,color:"FFFFFF"}; const gapB={top:gb,bottom:gb,left:gb,right:gb};
const run=(t,o={})=>new TextRun({text:t,font:FONT,size:o.size||19,bold:!!o.bold,color:o.color||INK,italics:!!o.italics});
const p=(ch,o={})=>new Paragraph({children:Array.isArray(ch)?ch:[ch],spacing:{before:o.before??0,after:o.after??50,line:o.line||252},alignment:o.align||AlignmentType.LEFT});
const text=(t,o={})=>p(run(t,o),o);
const fill=(t)=>run(`[${t}]`,{color:FILL,italics:true,size:18});   // placeholder marker
const bullet=(parts,o={})=>new Paragraph({numbering:{reference:"bul",level:0},spacing:{before:0,after:20,line:244},children:parts.map(x=>typeof x==="string"?run(x,{size:o.size||18}):x)});
const h1=(t,sub)=>{const out=[new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:130,after:sub?10:60},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:TEAL,space:4}},children:[run(t,{size:26,bold:true,color:TEAL})]})]; if(sub) out.push(text(sub,{size:17,color:INK2,italics:true,after:60})); return out;};
const img=(f,wIn)=>{const d=fs.readFileSync(f); const w=d.readUInt32BE(16),h=d.readUInt32BE(20); const W=Math.round(wIn*96); return new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:20,after:20},children:[new ImageRun({type:"png",data:d,transformation:{width:W,height:Math.round(W*h/w)}})]});};
function tiles(items,o={}){const n=items.length; const cw=Math.floor(CONTENT/n); const widths=Array(n).fill(cw); widths[n-1]=CONTENT-cw*(n-1);
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:widths,borders:noB,rows:[new TableRow({children:items.map((it,i)=>new TableCell({width:{size:widths[i],type:WidthType.DXA},borders:gapB,shading:{type:ShadingType.CLEAR,fill:it.fill||LIGHT,color:"auto"},margins:{top:90,bottom:90,left:130,right:130},
    children:[p(run(it.head,{size:o.headSize||19,bold:true,color:TEAL}),{after:40}),...(it.lines||[]).map(l=>p(Array.isArray(l)?l:run(l,{size:o.lineSize||18,color:INK2}),{after:24,line:236})),...(it.bullets||[]).map(b=>bullet(b,{size:o.lineSize||18}))]}))})]});}
function kv(rows,keyW=2600,o={}){const vW=CONTENT-keyW; return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:[keyW,vW],borders:noB,rows:rows.map(([k,v])=>new TableRow({children:[
  new TableCell({width:{size:keyW,type:WidthType.DXA},borders:gapB,shading:{type:ShadingType.CLEAR,fill:LIGHT,color:"auto"},margins:{top:50,bottom:50,left:130,right:130},children:[p(run(k,{size:18,bold:true,color:TEAL}),{after:0})]}),
  new TableCell({width:{size:vW,type:WidthType.DXA},borders:gapB,shading:{type:ShadingType.CLEAR,fill:PALE,color:"auto"},margins:{top:50,bottom:50,left:130,right:130},children:(Array.isArray(v)?v:[v]).map((l,i,a)=>p(Array.isArray(l)?l:run(l,{size:18}),{after:i===a.length-1?0:16,line:236}))})]}))});}
// numeric grid: header row + rows; first col label
function grid(header,rows,firstW=2700,o={}){const n=header.length; const cw=Math.floor((CONTENT-firstW)/(n-1)); const widths=[firstW,...Array(n-2).fill(cw),CONTENT-firstW-cw*(n-2)];
  const cell=(t,i,isHead,isBold,shade)=>new TableCell({width:{size:widths[i],type:WidthType.DXA},borders:gapB,shading:{type:ShadingType.CLEAR,fill:shade,color:"auto"},margins:{top:40,bottom:40,left:100,right:100},verticalAlign:VerticalAlign.CENTER,
    children:[p(typeof t==="string"?run(t,{size:17,bold:isHead||isBold,color:isHead?TEAL:(i===0?INK:INK)}):t,{after:0,align:i===0?AlignmentType.LEFT:AlignmentType.RIGHT,line:230})]});
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:widths,borders:noB,rows:[
    new TableRow({tableHeader:true,children:header.map((h,i)=>cell(h,i,true,false,LIGHT))}),
    ...rows.map(r=>new TableRow({children:r.cells.map((c,i)=>cell(c,i,false,!!r.bold,r.bold?LIGHT:PALE))}))]});}
const pageBreak=()=>new Paragraph({children:[new PageBreak()]});
const k=(v)=>v==null?"":(Math.abs(v)>=1000?`${(v/1000).toFixed(2)}M`:`${Math.round(v)}k`);
const money=(v)=>v==null?"":(v<0?`(${k(-v)})`:k(v));
const pct=(v)=>`${Math.round(v*100)}%`;

// ===== Deal data (Hadden Estate, from Hadden_Monthly_Forecast_vF.xlsx) =====
const D={
  venue:"Hadden Estate", closeDate:"Aug 13, 2026 (mid-month)", comp:"ATL", units:"$ in thousands",
  periods:["2024","2025","LTM Jul-26","Year 1","Year 2","Year 3"],
  events:[42,43,39,40,65,80], oc:[42,43,39,24,1,0], nw:[0,0,0,16,64,80],
  revPerEvent:[9.6,9.4,14.0,22.4,26.8,32.5],
  revenue:[466.5,437.7,560.8,906.4,1749.6,2602.1], gm:[380.0,395.2,511.8,890.7,1668.1,2429.8],
  payroll:[-195.1,-229.6,-275.4,-317.2,-397.9,-508.4], opex:[-281.1,-263.1,-260.1,-277.3,-381.2,-456.9],
  ebitdar:[-96.1,-97.5,-23.7,296.2,889.0,1464.5], rent:[null,null,null,-285,-285,-296.4], ebitda:[-96.1,-97.5,-23.7,11.2,604.0,1168.1],
  leads:[1500,1750,2000], tours:[300,350,400], contracts:[80,90,100], lt:[0.2,0.2,0.2], tc:[0.267,0.257,0.25],
  services:[ // name, today, attach Y1..Y3, $/event (new), WH ATL attach
    ["Bar (beverage)","None in-house",[0.5,0.75,1.0],0.75,null],
    ["Catering (food)","None in-house",[0,0.5,1.0],5.05,null],
    ["Lodging","~50% of events",[0.5,0.5,0.5],3.0,null],
    ["Floral","None",[0.072,0.239,0.478],3.26,0.478],
    ["Bakery","None",[0.048,0.161,0.322],1.13,0.322],
    ["DJ","None",[0.115,0.384,0.614],1.69,0.767],
    ["Stationery","None",[0.117,0.39,0.78],0.79,0.78],
    ["Photography","None",[0.051,0.171,0.343],1.11,0.343],
  ],
  staff:[["Danielle","Planner",85.0],["Yami","Coordinator",60.8],["Kathy","Sales",75.0],["Adi","Maintenance",75.0],["Josh","Maintenance (part-time, through Nov)",2.8]],
};

const children=[
  p([run("Investment Summary",{size:38,bold:true,color:INK}),run(`   ${D.venue}`,{size:38,bold:true,color:TEAL})],{after:0}),
  p([run("Walters Hospitality",{size:20,color:TEAL,bold:true}),run("   |   Pre-LOI Pro Forma   |   ",{size:20,color:INK2}),run(D.units,{size:20,color:INK2})],{after:80}),
  tiles([
    {head:"Target close",lines:[D.closeDate]},
    {head:"Location",lines:[[fill("city, state")]]},
    {head:"Deal terms",lines:[[fill("price / structure")]]},
    {head:"Comparable WH venue",lines:[D.comp]},
  ],{headSize:18,lineSize:18}),

  ...h1("1. The venue"),
  tiles([
    {head:"Market",lines:[[fill("zone 1 / 2 / 3; drive time to hubs")]]},
    {head:"Performing or growth?",lines:["Flat event count; revenue per event rising","Growth case rests on new bookings and vendor services"]},
    {head:"Vendor services today",lines:["Room rental and lodging only","No in-house food or beverage"]},
    {head:"Employee structure",lines:["5 staff: planner, coordinator, sales, 2 maintenance",[fill("owner involvement")]]},
  ],{headSize:18,lineSize:17}),

  ...h1("2. Events and headline P&L"),
  new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:[CONTENT/2,CONTENT/2],borders:noB,rows:[new TableRow({children:[
    new TableCell({width:{size:CONTENT/2,type:WidthType.DXA},borders:noB,children:[img("s_events.png",3.4)]}),
    new TableCell({width:{size:CONTENT/2,type:WidthType.DXA},borders:noB,children:[img("s_pnl.png",3.4)]}),
  ]})]}),
  grid(["",...D.periods],[
    {cells:["Events",...D.events.map(String)]},
    {cells:["   OC / new",...D.events.map((_,i)=>i<3?"actual":`${D.oc[i]} / ${D.nw[i]}`)]},
    {cells:["Revenue per event",...D.revPerEvent.map(v=>`${v.toFixed(1)}k`)]},
    {cells:["Revenue",...D.revenue.map(money)],bold:true},
    {cells:["Gross margin",...D.gm.map(money)]},
    {cells:["Payroll",...D.payroll.map(money)]},
    {cells:["Operating expenses",...D.opex.map(money)]},
    {cells:["EBITDAR",...D.ebitdar.map(money)],bold:true},
    {cells:["Rent (post-close)",...D.rent.map(v=>v==null?"–":money(v))]},
    {cells:["EBITDA",...D.ebitda.map(money)],bold:true},
  ],2500),
  text("Year 1 begins at close. OC = original contract events booked by the sellers before close.",{size:16,color:INK2,italics:true,before:30}),

  pageBreak(),
  p([run("Investment Summary",{size:20,bold:true,color:INK}),run(`   ${D.venue}`,{size:20,bold:true,color:TEAL}),run("   |   Assumptions",{size:20,color:INK2})],{after:40}),

  ...h1("3. Vendor services plan","Attachment = share of new-contract events that add the service; $ / event is the Walters average used"),
  grid(["Service","Today","Attach Y1","Attach Y2","Attach Y3","$ / event","WH ATL attach"],
    D.services.map(s=>({cells:[s[0],s[1],...s[2].map(pct),`${s[3].toFixed(2)}k`,s[4]==null?"–":pct(s[4])]})),2200),
  text("Bar is an on/off switch once licensed. Catering starts Year 2. Floral, bakery, DJ, stationery and photography ramp to the ATL average by Year 3.",{size:17,color:INK2,before:40}),

  ...h1("4. Expense assumptions"),
  tiles([
    {head:"Payroll",bullets:[["Current 5 staff carried at ",run("5% YoY",{size:18,bold:true})],["Add ancillary and F&B payroll as services go live"],[fill("owner pay vs. replacement cost")]]},
    {head:"COGS",bullets:[["Little COGS today"],["Food, alcohol and ancillary COGS at ",run("Walters margins",{size:18,bold:true})," as services attach"]]},
    {head:"Operating expenses",bullets:[["Marketing steps up to ",run("~67k",{size:18,bold:true})," from ~22k LTM"],["Insurance ~30k, property tax ~35k"],[run("Rent 285k",{size:18,bold:true})," post-close"]]},
  ],{headSize:18,lineSize:17}),

  ...h1("5. Marketing funnel","No venue lead or tour history; conversion rates are Walters averages"),
  grid(["","Year 1","Year 2","Year 3"],[
    {cells:["Leads",...D.leads.map(String)]},
    {cells:["L→T conversion",...D.lt.map(pct)]},
    {cells:["Tours",...D.tours.map(String)]},
    {cells:["T→C conversion",...D.tc.map(pct)]},
    {cells:["Contracts",...D.contracts.map(String)],bold:true},
  ],3000),

  ...h1("6. Risks and open items"),
  bullet(["Funnel rests entirely on Walters conversion rates; no venue history to check against"]),
  bullet(["Year 2 and 3 revenue depends on catering and bar going live on schedule"]),
  bullet(["Rent of 285k post-close is the gap between EBITDAR and EBITDA"]),
  bullet([fill("owner transition and replacement plan")]),
  bullet([fill("market zone and hub distance; which services can we actually serve")]),
  bullet([fill("diligence items outstanding")]),
];

const doc=new Document({styles:{default:{document:{run:{font:FONT,size:19,color:INK}}}},
  numbering:{config:[{reference:"bul",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:300,hanging:200}}}}]}]},
  sections:[{properties:{page:{size:{width:PAGE_W,height:15840},margin:{top:MARGIN,bottom:MARGIN,left:MARGIN,right:MARGIN}}},children}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("Investment Summary - Hadden Estate.docx",b);console.log("written");});
