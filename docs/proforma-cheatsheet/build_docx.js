const fs=require("fs");
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,WidthType,ShadingType,BorderStyle,ImageRun,AlignmentType,HeadingLevel,LevelFormat,PageBreak}=require("docx");

const BLUE="2A78D6", INK="0B0B0B", INK2="52514E", LIGHT="EEF2F8", ORANGE="EB6834", PALE="F7F7F5";
const FONT="Calibri";
const PAGE_W=12240, MARGIN=864, CONTENT=PAGE_W-2*MARGIN; // 10512 dxa

const noBorder={style:BorderStyle.NONE,size:0,color:"FFFFFF"};
const noBorders={top:noBorder,bottom:noBorder,left:noBorder,right:noBorder};
const gapBorder={style:BorderStyle.SINGLE,size:24,color:"FFFFFF"}; // white gap between tiles
const gapBorders={top:gapBorder,bottom:gapBorder,left:gapBorder,right:gapBorder};

const run=(t,o={})=>new TextRun({text:t,font:FONT,size:o.size||20,bold:o.bold||false,color:o.color||INK,italics:o.italics||false});
const p=(children,o={})=>new Paragraph({children:Array.isArray(children)?children:[children],spacing:{before:o.before??0,after:o.after??60,line:o.line||264},alignment:o.align||AlignmentType.LEFT});
const text=(t,o={})=>p(run(t,o),o);
const bullet=(t,o={})=>new Paragraph({numbering:{reference:"bul",level:0},spacing:{before:0,after:40,line:252},children:[run(t,{size:o.size||19,color:o.color||INK,bold:o.bold})]});
const richBullet=(parts,o={})=>new Paragraph({numbering:{reference:"bul",level:0},spacing:{before:0,after:40,line:252},children:parts.map(([t,b])=>run(t,{size:19,bold:!!b}))});

function h1(t,sub){
  const out=[new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:240,after:sub?20:100},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:BLUE,space:4}},children:[run(t,{size:30,bold:true,color:BLUE})]})];
  if(sub) out.push(text(sub,{size:18,color:INK2,italics:true,after:100}));
  return out;
}

function img(file,widthIn){
  const data=fs.readFileSync(file);
  // read PNG dims
  const w=data.readUInt32BE(16), h=data.readUInt32BE(20);
  const W=Math.round(widthIn*96), H=Math.round(W*h/w);
  return new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:60,after:60},children:[new ImageRun({type:"png",data,transformation:{width:W,height:H}})]});
}

// Tile row: array of {head, lines[], fill}
function tiles(items,opts={}){
  const n=items.length; const cw=Math.floor(CONTENT/n); const widths=Array(n).fill(cw); widths[n-1]=CONTENT-cw*(n-1);
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:widths,borders:noBorders,
    rows:[new TableRow({children:items.map((it,i)=>new TableCell({
      width:{size:widths[i],type:WidthType.DXA},borders:gapBorders,
      shading:{type:ShadingType.CLEAR,fill:it.fill||LIGHT,color:"auto"},
      margins:{top:120,bottom:120,left:140,right:140},
      children:[
        ...(it.big?[p(run(it.big,{size:it.bigSize||44,bold:true,color:it.headColor||BLUE}),{align:AlignmentType.CENTER,after:20})]:[]),
        p(run(it.head,{size:opts.headSize||21,bold:true,color:it.headColor||(it.big?INK:BLUE)}),{align:it.big?AlignmentType.CENTER:AlignmentType.LEFT,after:it.lines&&it.lines.length?60:0}),
        ...(it.lines||[]).map(l=>p(run(l,{size:opts.lineSize||19,color:INK2}),{align:it.big?AlignmentType.CENTER:AlignmentType.LEFT,after:30,line:240}))
      ]}))})]});
}

// Two-column key/value table
function kv(rows,keyW=2600){
  const vW=CONTENT-keyW;
  return new Table({width:{size:CONTENT,type:WidthType.DXA},columnWidths:[keyW,vW],borders:noBorders,
    rows:rows.map(([k,v],i)=>new TableRow({children:[
      new TableCell({width:{size:keyW,type:WidthType.DXA},borders:gapBorders,shading:{type:ShadingType.CLEAR,fill:LIGHT,color:"auto"},margins:{top:80,bottom:80,left:140,right:140},children:[p(run(k,{size:20,bold:true,color:BLUE}),{after:0})]}),
      new TableCell({width:{size:vW,type:WidthType.DXA},borders:gapBorders,shading:{type:ShadingType.CLEAR,fill:PALE,color:"auto"},margins:{top:80,bottom:80,left:140,right:140},children:[p(run(v,{size:20,color:INK}),{after:0})]})
    ]}))});
}

const spacer=(n=80)=>new Paragraph({spacing:{before:0,after:n},children:[]});

const children=[
  p(run("Pre-LOI Proforma",{size:52,bold:true,color:INK}),{after:0}),
  p(run("Cheat sheet · how we underwrite a venue before LOI",{size:24,color:INK2}),{after:40}),
  p(run("Walters Hospitality",{size:18,color:BLUE,bold:true}),{after:120}),

  ...h1("1. Frame the venue","Four questions that set the tone for every proforma"),
  tiles([
    {head:"Performing or growth?",lines:["Already doing well","— or —","Growth opportunity"]},
    {head:"Vendor services",lines:["What they do today vs. what we implement, and how fast","Plus our marketing to fill events"]},
    {head:"Employee structure",lines:["Overstaffed or understaffed?","Owner heavily involved or hands-off?"]},
    {head:"Market",lines:["Current market","— or —","New market"]},
  ],{headSize:21,lineSize:18}),

  ...h1("2. Key terms"),
  img("timeline.png",6.9),
  kv([
    ["Year 1 / 2 / 3","Proforma years. Year 1 starts the day we close — the moment we own it."],
    ["OC events","Original Contract events: already on the books before close. We want a healthy number — you can only book so many events into a year."],
    ["New contract","Anything we book after close, whether it lands in Year 1, 2 or 3."],
  ]),

  new Paragraph({children:[new PageBreak()]}),

  ...h1("3. Current vs. new market","Current market = within 90 minutes of our hubs"),
  img("market.png",5.8),
  kv([
    ["Dallas hubs","The Olana (bakery + floral) · one of our three catering hubs, whichever is closest"],
    ["Rule","Model each vendor service against its own hub. 30 min from catering but 1–2 hrs from bakery → catering yes, bakery $0."],
    ["New market","Think further out. The venue must do well on its own; vendor services may not come for a couple of years, once volume exists."],
  ],2700),
  spacer(80),
  text("The perfect new-market venue",{size:20,bold:true,after:40}),
  tiles([
    {head:"~100 events / year",lines:["Real volume from day one"]},
    {head:"All-inclusive package",lines:["Partnering with outside vendors — or some in-house"]},
    {head:"Owner not involved",lines:["Runs without them"]},
  ],{headSize:21,lineSize:18}),

  ...h1("4. Events — the three numbers","First thing we look at when projecting forward"),
  tiles([
    {big:"1",head:"Historical average",lines:["Events per year over their history"]},
    {big:"2",head:"Last 12 months",lines:["Events actually held"]},
    {big:"3",head:"Next 12 months",lines:["Events currently booked"]},
  ],{headSize:22,lineSize:18}),

  new Paragraph({children:[new PageBreak()]}),

  ...h1("5. Revenue / Vendor Services","What they offer today · when we can implement · how fast we attach"),
  kv([
    ["Photography · DJ · Stationery","Quick to implement — set pricing and start selling."],
    ["Bar","On/off switch. Off until we hold the liquor license, then on. Do they pour in-house today?"],
    ["Catering","Attach slowly — test, don't flip at close. Do they require a caterer today, even if not in-house?"],
    ["Floral · Bakery","Hub-dependent. Too far from The Olana → $0."],
  ],2900),
  img("ramp.png",5.2),
  kv([
    ["Attachment ramp-up","Ramp up to the Walters average attachment for each service by Year 3. Tweak for what they do today and what we truly believe we can do."],
    ["$ per vendor service","Use the Walters average $ per event for that service. Small venue → tweak down. Almost never tweak up. Sanity-check the implied $ per event against what the owner says brides actually spend."],
    ["Don't \"Walterize\" too fast","Flipping every package to standard at close can lose the brides that venue attracts. Test and attach slowly — never assume catering is 100% on day one."],
  ],2900),

  ...h1("6. Expenses","A mix of what they do today and what we can and should do post-close"),
  tiles([
    {head:"COGS",lines:["Venue-rental-only → little COGS today","Add COGS for each vendor service we attach","Required caterer? Carry their per-head cost on every OC event; set what we charge going forward"]},
    {head:"Payroll",lines:["Don't assume big cuts — they're likely staffed about where we'd be","Overstaffed or understaffed?","Owner: how involved today? What do they pay themselves? If they walk, who replaces them and at what cost?"]},
    {head:"Operating expenses",lines:["Multiple lines","Start from what they spend today","Adjust to how we'd run it post-close"]},
  ],{headSize:22,lineSize:18}),
];

const doc=new Document({
  styles:{default:{document:{run:{font:FONT,size:20,color:INK}}}},
  numbering:{config:[{reference:"bul",levels:[{level:0,format:LevelFormat.BULLET,text:"•",alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:360,hanging:240}}}}]}]},
  sections:[{properties:{page:{size:{width:PAGE_W,height:15840},margin:{top:MARGIN,bottom:MARGIN,left:MARGIN,right:MARGIN}}},children}]
});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync("Pre-LOI Proforma Cheat Sheet.docx",b);console.log("written");});
