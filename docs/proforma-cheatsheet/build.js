const fs=require("fs");
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,WidthType,ShadingType,BorderStyle,ImageRun,AlignmentType,HeadingLevel,LevelFormat,PageBreak}=require("docx");

const TEAL="1A939B", LIGHT="EFF6F9", INK="0B0B0B", INK2="52514E", PALE="F7F7F5";
const FONT="Calibri";
const PAGE_W=12240, MARGIN=864, CONTENT=PAGE_W-2*MARGIN;

const noBorder={style:BorderStyle.NONE,size:0,color:"FFFFFF"};
const noBorders={top:noBorder,bottom:noBorder,left:noBorder,right:noBorder};
const gapBorder={style:BorderStyle.SINGLE,size:24,color:"FFFFFF"};
const gapBorders={top:gapBorder,bottom:gapBorder,left:gapBorder,right:gapBorder};

const run=(t,o={})=>new TextRun({text:t,font:FONT,size:o.size||20,bold:!!o.bold,color:o.color||INK,italics:!!o.italics});
const p=(children,o={})=>new Paragraph({children:Array.isArray(children)?children:[children],spacing:{before:o.before??0,after:o.after??60,line:o.line||264},alignment:o.align||AlignmentType.LEFT});
const text=(t,o={})=>p(run(t,o),o);
const bullet=(t,o={})=>new Paragraph({numbering:{reference:"bul",level:0},spacing:{before:0,after:o.after??30,line:248},children:[run(t,{size:o.size||19,color:o.color||INK})]});
const richBullet=(parts,o={})=>new Paragraph({numbering:{reference:"bul",level:0},spacing:{before:0,after:o.after??20,line:248},children:parts.map(([t,b])=>run(t,{size:o.size||19,bold:!!b,color:INK}))});
const divider=()=>new Paragraph({spacing:{before:30,after:40},border:{bottom:{style:BorderStyle.SINGLE,size:4,color:"B7DCDF",space:1}},children:[]});
const lead=(t)=>text(t,{size:20,bold:true,after:30,before:80});

function h1(t,sub){
  const out=[new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:140,after:sub?20:70},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:TEAL,space:4}},children:[run(t,{size:30,bold:true,color:TEAL})]})];
  if(sub) out.push(text(sub,{size:18,color:INK2,italics:true,after:100}));
  return out;
}
function h2(t){ return text(t,{size:23,bold:true,color:TEAL,before:60,after:40}); }

function img(file,widthIn){
  const data=fs.readFileSync(file); const w=data.readUInt32BE(16), h=data.readUInt32BE(20);
  const W=Math.round(widthIn*96), H=Math.round(W*h/w);
  return new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:30,after:30},children:[new ImageRun({type:"png",data,transformation:{width:W,height:H}})]});
}

// Tiles: {head, lines[] | bullets[], big}
function tiles(items,opts={}){
  const n=items.length; const cw=Math.floor(CONTENT/n); const widths=Array(n).fill(cw); widths[n-1]=CONTENT-cw*(n-1);
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:widths,borders:noBorders,
    rows:[new TableRow({children:items.map((it,i)=>new TableCell({
      width:{size:widths[i],type:WidthType.DXA},borders:gapBorders,
      shading:{type:ShadingType.CLEAR,fill:it.fill||LIGHT,color:"auto"},
      margins:{top:100,bottom:100,left:140,right:140},
      children:[
        ...(it.big?[p(run(it.big,{size:40,bold:true,color:TEAL}),{align:AlignmentType.CENTER,after:0})]:[]),
        p(run(it.head,{size:opts.headSize||21,bold:true,color:it.big?INK:TEAL}),{align:it.big?AlignmentType.CENTER:AlignmentType.LEFT,after:60}),
        ...(it.lines||[]).map(l=>l==="vs."?p(run("vs.",{size:16,color:TEAL,italics:true}),{after:10,line:220}):p(run(l,{size:opts.lineSize||19,color:INK2}),{align:it.big?AlignmentType.CENTER:AlignmentType.LEFT,after:30,line:240})),
        ...(it.bullets||[]).map(b=>Array.isArray(b)?richBullet(b,{size:opts.lineSize||19}):bullet(b,{size:opts.lineSize||19,after:20}))
      ]}))})]});
}

function kv(rows,keyW=2600){
  const vW=CONTENT-keyW;
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:[keyW,vW],borders:noBorders,
    rows:rows.map(([k,v])=>new TableRow({children:[
      new TableCell({width:{size:keyW,type:WidthType.DXA},borders:gapBorders,shading:{type:ShadingType.CLEAR,fill:LIGHT,color:"auto"},margins:{top:60,bottom:60,left:140,right:140},children:[p(run(k,{size:20,bold:true,color:TEAL}),{after:0})]}),
      new TableCell({width:{size:vW,type:WidthType.DXA},borders:gapBorders,shading:{type:ShadingType.CLEAR,fill:PALE,color:"auto"},margins:{top:60,bottom:60,left:140,right:140},children:Array.isArray(v)?v.map((l,i)=>p(run(l,{size:20,color:INK}),{after:i===v.length-1?0:20,line:240})):[p(run(v,{size:20,color:INK}),{after:0})]})
    ]}))});
}
const spacer=(n=80)=>new Paragraph({spacing:{before:0,after:n},children:[]});
const pageBreak=()=>new Paragraph({children:[new PageBreak()]});

const vs=(a,b)=>[a,"vs.",b];
const children=[
  p(run("Pro Forma Cheat Sheet",{size:40,bold:true,color:INK}),{after:0}),
  p([run("Walters Hospitality",{size:22,color:TEAL,bold:true}),run("   |   Part 1: Pre-LOI",{size:22,color:INK2,bold:true})],{after:60}),

  ...h1("1. Frame the venue"),
  tiles([
    {head:"Market",lines:vs("Current market","New market")},
    {head:"Performing or growth?",lines:vs("Established, strong performer","Upside we can unlock")},
    {head:"Vendor services",lines:vs("What they offer today","What we bring")},
    {head:"Employee structure",lines:["Overstaffed vs. understaffed","Owner hands-on vs. hands-off"]},
  ],{headSize:21,lineSize:18}),

  ...h1("2. Key terms"),
  img("ocmix.png",4.1),
  kv([
    ["Pro Forma Year 1 / 2 / 3","Year 1 starts the day we close."],
    ["OC events","\u201COriginal Contract\u201D events; booked prior to close by the sellers to occur post-close. We honor OC events as-is."],
    ["\u201CEvent\u201D vs. \u201CContract\u201D",["\u201CEvents\u201D in Year 1 occur in Year 1.","\u201CContracts\u201D in Year 1 are events booked in Year 1.","We only project Events pre-LOI."]],
  ]),

  ...h1("3. Market"),
  img("market.png",3.8),
  kv([
    ["1  Current market, in hub range","<90-minute drive from each hub (Catering / Floral / Bakery)."],
    ["2  Current market, outside hub range",["Part of the broader region, geographically and operationally.","Too far to utilize existing hubs."]],
    ["3  New market","A new region for Walters."],
  ],3300),

  ...h1("4. Top-Line Projections"),
  tiles([
    {head:"# of Events",lines:["Historical average?","LTM vs. NTM?"]},
    {head:"% Attachment",lines:["Share of events that attach to each vendor service; based on Walters regional averages"]},
    {head:"$ / Event",lines:["Spend per event on each vendor service; based on Walters averages"]},
  ],{headSize:21,lineSize:18}),
  h2("Vendor Services"),
  kv([
    ["Bar","Any market; on/off switch once we hold the liquor license."],
    ["Catering / Floral / Bakery","Existing markets; depends on hub distance."],
    ["Photography / DJ / Stationery","Any market; only need to hire and implement packages."],
  ],3300),
  divider(),
  lead("Attachment ramp-up"),
  text("Our typical assumption: ramp to the Walters average attachment by Year 3, adjusted for the venue.",{size:19,color:INK2,after:40}),
  img("ramp.png",5.3),

  ...h1("5. Expenses"),
  tiles([
    {head:"COGS",bullets:[
      [["Historically driven by their ",false],["existing vendor services",true],[" (if any); go-forward defers towards ",false],["our offerings and margins",true]],
      [["Keep their ",false],["go-forward OC costs",true],[" in mind (e.g. a required caterer's per-head cost on OC events)",false]]]},
    {head:"Payroll",bullets:[
      [["Current staff",true]],
      [["Current or new market",true]],
      [["Owner involvement",true],[": what they pay themselves; ",false],["replacement cost",true]]]},
    {head:"Operating expenses",bullets:[
      [["Venue specific",true],[" (utilities, maintenance)",false]],
      [["Walters operational changes",true],[" (marketing, insurance, finance expenses, professional services, etc.)",false]]]},
  ],{headSize:22,lineSize:18}),

  pageBreak(),
  p([run("Walters Hospitality",{size:22,color:TEAL,bold:true}),run("   |   Part 2: Post-LOI",{size:22,color:INK2,bold:true})],{after:60}),

  ...h1("6. Same process, more detail"),
  text("Everything in Part 1 again, with updated event counts, financials and what we learned in diligence. Then we get in the weeds:",{size:19,color:INK2,after:60}),
  tiles([
    {head:"Revenue",bullets:[
      [["Go-forward pricing",true],[" for the venue and each vendor service",false]],
      [["Go-live plans",true],[" for each vendor service",false]]]},
    {head:"Expenses",bullets:[
      [["Payroll",true],[": estimate costs by employee",false]],
      [["COGS and OpEx",true],[": more detail from what diligence collected",false]]]},
  ],{headSize:21,lineSize:18}),

  ...h1("7. New step: Leads / Tours / Contracts"),
  text("We start from the event counts and work backwards into estimated contracts, tours and leads using historical venue performance and Walters conversion rates, then work with Marketing and Sales to finalize what they feel is realistic.",{size:19,color:INK2,after:40}),
  img("funnel.png",6.0),

  ...h1("8. Monthly build"),
  text("We take the annual figures and use seasonality plus a slow ramp-up over the first ~6 months to spread the marketing funnel, events and financials across the months.",{size:19,color:INK2,after:40}),
  img("monthly.png",6.2),
];

const doc=new Document({
  styles:{default:{document:{run:{font:FONT,size:20,color:INK}}}},
  numbering:{config:[{reference:"bul",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:300,hanging:200}}}}]}]},
  sections:[{properties:{page:{size:{width:PAGE_W,height:15840},margin:{top:MARGIN,bottom:MARGIN,left:MARGIN,right:MARGIN}}},children}]
});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("Pro Forma Sheet.docx",b);console.log("written");});
