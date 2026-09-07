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
const lead=(t)=>text(t,{size:20,bold:true,after:30,before:80});

function h1(t,sub){
  const out=[new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:240,after:sub?20:100},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:TEAL,space:4}},children:[run(t,{size:30,bold:true,color:TEAL})]})];
  if(sub) out.push(text(sub,{size:18,color:INK2,italics:true,after:100}));
  return out;
}
function h2(t){ return text(t,{size:23,bold:true,color:TEAL,before:140,after:40}); }

function img(file,widthIn){
  const data=fs.readFileSync(file); const w=data.readUInt32BE(16), h=data.readUInt32BE(20);
  const W=Math.round(widthIn*96), H=Math.round(W*h/w);
  return new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:60,after:60},children:[new ImageRun({type:"png",data,transformation:{width:W,height:H}})]});
}

// Tiles: {head, lines[] | bullets[], big}
function tiles(items,opts={}){
  const n=items.length; const cw=Math.floor(CONTENT/n); const widths=Array(n).fill(cw); widths[n-1]=CONTENT-cw*(n-1);
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:widths,borders:noBorders,
    rows:[new TableRow({children:items.map((it,i)=>new TableCell({
      width:{size:widths[i],type:WidthType.DXA},borders:gapBorders,
      shading:{type:ShadingType.CLEAR,fill:it.fill||LIGHT,color:"auto"},
      margins:{top:120,bottom:120,left:140,right:140},
      children:[
        ...(it.big?[p(run(it.big,{size:40,bold:true,color:TEAL}),{align:AlignmentType.CENTER,after:0})]:[]),
        p(run(it.head,{size:opts.headSize||21,bold:true,color:it.big?INK:TEAL}),{align:it.big?AlignmentType.CENTER:AlignmentType.LEFT,after:60}),
        ...(it.lines||[]).map(l=>p(run(l,{size:opts.lineSize||19,color:INK2}),{align:it.big?AlignmentType.CENTER:AlignmentType.LEFT,after:30,line:240})),
        ...(it.bullets||[]).map(b=>bullet(b,{size:opts.lineSize||19,after:20}))
      ]}))})]});
}

function kv(rows,keyW=2600){
  const vW=CONTENT-keyW;
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:[keyW,vW],borders:noBorders,
    rows:rows.map(([k,v])=>new TableRow({children:[
      new TableCell({width:{size:keyW,type:WidthType.DXA},borders:gapBorders,shading:{type:ShadingType.CLEAR,fill:LIGHT,color:"auto"},margins:{top:80,bottom:80,left:140,right:140},children:[p(run(k,{size:20,bold:true,color:TEAL}),{after:0})]}),
      new TableCell({width:{size:vW,type:WidthType.DXA},borders:gapBorders,shading:{type:ShadingType.CLEAR,fill:PALE,color:"auto"},margins:{top:80,bottom:80,left:140,right:140},children:Array.isArray(v)?v.map((l,i)=>p(run(l,{size:20,color:INK}),{after:i===v.length-1?0:20,line:240})):[p(run(v,{size:20,color:INK}),{after:0})]})
    ]}))});
}
const spacer=(n=80)=>new Paragraph({spacing:{before:0,after:n},children:[]});
const pageBreak=()=>new Paragraph({children:[new PageBreak()]});

const children=[
  p(run("Pro Forma Sheet",{size:52,bold:true,color:INK}),{after:0}),
  p(run("Walters Hospitality",{size:22,color:TEAL,bold:true}),{after:60}),
  p(run("Part 1: Pre-LOI",{size:26,bold:true,color:INK2}),{after:120}),

  ...h1("1. Frame the venue"),
  tiles([
    {head:"Market",lines:["Current market","New market"]},
    {head:"Performing or growth?",lines:["Already doing well","Growth opportunity"]},
    {head:"Vendor services",lines:["What they do today vs. what we implement, and how fast","Our marketing to fill events"]},
    {head:"Employee structure",lines:["Overstaffed or understaffed?","Owner involved or hands-off?"]},
  ],{headSize:21,lineSize:18}),

  ...h1("2. Key terms"),
  img("ocmix.png",6.4),
  kv([
    ["Year 1 / 2 / 3","Pro forma years. Year 1 starts the day we close."],
    ["OC events","Original Contract events; booked before close. Mostly Year 1, some Year 2, rarely Year 3. We want a healthy number; a year only holds so many."],
    ["New contracts","Events we assume will book after close; they can land in Year 1, 2 or 3."],
  ]),

  pageBreak(),

  ...h1("3. Market"),
  img("market.png",5.6),
  kv([
    ["1  Current market, in hub range",["Within 90 minutes of our hubs.","Vendor services modeled in Years 1 to 3 on our ramp."]],
    ["2  Current market, outside hub range",["In the broader region; likely grouped operationally with it.","Too far to use our hubs, so hub services start at $0.","Question: do we grow that direction and open hubs that can service it?"]],
    ["3  New market",["Venue must stand on its own.","Vendor services may be a couple of years out, once volume exists."]],
  ],3300),
  spacer(80),
  lead("The perfect new-market venue"),
  tiles([
    {head:"~100 events / year",lines:["Real volume from day one"]},
    {head:"All-inclusive package",lines:["Partnering with outside vendors, or some in-house"]},
    {head:"Owner not involved",lines:["Runs without them"]},
  ],{headSize:21,lineSize:18}),

  pageBreak(),

  ...h1("4. Top-Line Projections"),
  h2("Events"),
  bullet("Historical average per year"),
  bullet("Last 12 months"),
  bullet("Booked for the next 12 months"),
  h2("Revenue / Vendor Services"),
  bullet("Photography / DJ / Stationery: quick to implement"),
  bullet("Bar: on/off switch once we hold the liquor license"),
  bullet("Catering: attach slowly; test it"),
  bullet("Floral / Bakery: depends on hub distance"),
  lead("Attachment ramp-up"),
  text("Our typical assumption: ramp to the Walters average attachment by Year 3, tweaked for the venue.",{size:19,color:INK2,after:40}),
  img("ramp.png",6.0),
  lead("$ per vendor service"),
  bullet("Walters average $ per event for that service"),
  bullet("Small venue: tweak down; almost never tweak up"),
  bullet("Sanity-check against what brides at that venue actually spend"),
  lead("Don't \"Walterize\" too fast"),
  bullet("Test and attach slowly; catering is not 100% on day one"),

  ...h1("5. Expenses"),
  tiles([
    {head:"COGS",bullets:["Depends on their vendor services and other offerings","Keep theirs in mind (e.g. a required caterer's per-head cost on OC events)","Often they have little or no COGS; we implement on our ramp and margins"]},
    {head:"Payroll",bullets:["Who they employ today","Current or new market","How involved the owners are; what they pay themselves; replacement cost"]},
    {head:"Operating expenses",bullets:["Switch to our marketing; almost always higher","Their utilities and maintenance per event","Our insurance, finance expenses, professional services"]},
  ],{headSize:22,lineSize:18}),
];

const doc=new Document({
  styles:{default:{document:{run:{font:FONT,size:20,color:INK}}}},
  numbering:{config:[{reference:"bul",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:300,hanging:200}}}}]}]},
  sections:[{properties:{page:{size:{width:PAGE_W,height:15840},margin:{top:MARGIN,bottom:MARGIN,left:MARGIN,right:MARGIN}}},children}]
});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("Pro Forma Sheet.docx",b);console.log("written");});
