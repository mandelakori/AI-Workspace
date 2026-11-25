"use strict";

const el=id=>document.getElementById(id);
const session=document.querySelector('meta[name="operator-session"]').content;
let data, project="", thread="", draft=null, attachment=null, selectedJob="";
let screenImage=null, screenPng="", observation=null, busy=false, refreshInProgress=false;
const pretty=value=>JSON.stringify(value,null,2);

async function api(path,body) {
  const response=await fetch(path,body===undefined?{}:{
    method:"POST",headers:{"Content-Type":"application/json","X-AIWork-Session":session},body:JSON.stringify(body)
  });
  const result=await response.json();
  if(!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}
async function act(action) {
  el("notice").textContent="";
  try {await action();}
  catch(error) {el("notice").textContent=error.message;}
}
function node(tag,text="",name="") {
  const element=document.createElement(tag);
  element.textContent=text;
  if(name) element.className=name;
  return element;
}
function button(text,action) {
  const result=node("button",text,"secondary");
  result.type="button";
  result.onclick=()=>act(action);
  return result;
}
function options(select,rows,selected) {
  select.replaceChildren(...rows.map(([value,label])=>new Option(label,value)));
  if(rows.some(row=>row[0]===selected)) select.value=selected;
}
function summary(parent,title,value,key,expanded) {
  const part=node("details");
  part.dataset.key=key;
  part.open=expanded.has(key);
  part.append(node("summary",title),node("pre",typeof value==="string"?value:pretty(value)));
  parent.append(part);
}
function hideReview() {draft=null;el("review").hidden=true;el("composer").hidden=false;}

async function newThread() {
  thread=(await api("/api/thread",{project})).thread;
  selectedJob="";
  hideReview();
  await refresh();
  el("prompt").focus();
}
async function selectProject(id) {
  project=id;
  thread=data.threads.find(row=>row.project===id)?.id||"";
  selectedJob="";
  attachment=null;
  el("attachment").hidden=true;
  hideReview();
  if(!thread) await newThread();
  else await refresh();
}

async function refresh() {
  if(refreshInProgress) return;
  refreshInProgress=true;
  try {
    const [state,queue]=await Promise.all([api("/api/desktop"),api("/api/jobs")]);
    data=state;
    if(!project) project=data.threads[0]?.project||data.projects[0]?.id||"";
    if(!thread) thread=data.threads.find(row=>row.project===project)?.id||"";
    const current=data.threads.find(row=>row.id===thread);
    const folder=data.projects.find(row=>row.id===project)?.path||"";
    options(el("projects"),data.projects.map(p=>[p.id,p.path.split(/[\\/]/).pop()]),project);
    if(!el("models").options.length) {
      const local=data.models.find(p=>p.location==="local");
      options(el("models"),[...data.models.map(p=>[p.id,p.name+" · "+(p.location==="local"?"Laptop":"A100")]),
                            ["","Automatic"]],local?.id||"");
    }
    if(el("native-mode").options.length===1 && data.native.length>1)
      options(el("native-mode"),data.native.map(name=>[name,name==="binary"?"PE / ELF metadata":name]),"binary");
    el("runtime").textContent=data.runtime.detail;
    el("project-path").textContent=folder;
    el("title").textContent=current?.title||"New conversation";
    el("threads").replaceChildren(...data.threads.filter(row=>row.project===project).map(row=>{
      const item=button(row.title,async()=>{thread=row.id;selectedJob="";hideReview();await refresh();});
      item.setAttribute("aria-current",String(row.id===thread));
      return item;
    }));
    const jobs=new Map(queue.jobs.map(job=>[job.id,job]));
    const messages=data.messages.filter(row=>row.thread===thread).reverse();
    const timeline=el("conversation");
    const seen=new Set([...timeline.querySelectorAll("details[open]")].map(value=>value.dataset.key));
    const detailJob=selectedJob || messages.at(-1)?.job;
    const report=detailJob?await api("/api/jobs/"+detailJob):null;
    timeline.replaceChildren(...messages.map(message=>{
      const card=node("article","","message");
      const job=jobs.get(message.job);
      const status=node("p",job?.status||"Recorded","status");
      status.dataset.state=job?.status||"";
      card.append(node("p",message.prompt,"prompt"),status);
      if(job?.detail) card.append(node("p",job.detail));
      if(message.job===detailJob && report) renderReport(card,report,seen);
      else card.append(button("Open result",async()=>{selectedJob=message.job;await refresh();}));
      return card;
    }));
    if(report && !messages.some(message=>message.job===detailJob) && !el("history").hidden)
      renderReport(timeline,report,seen);
    el("job-list").replaceChildren(...queue.jobs.map(job=>button(
      `${job.status} · ${job.created} · ${job.id.slice(0,8)}`,
      async()=>{selectedJob=job.id;await refresh();}
    )));
    const next=[...queue.jobs].reverse().find(job=>job.dispatchable);
    if(next && !queue.dispatching) {
      try {await api("/api/run",{job:next.id});}
      catch(error) {el("notice").textContent=error.message;}
    }
    screenButtons();
  } finally { refreshInProgress=false; }
}

function renderReport(parent,report,expanded) {
  for(const attempt of report.attempts) {
    const key=report.job+attempt.attempt;
    if(attempt.analysis?.binary) summary(parent,"Native analysis",attempt.analysis,key+"native",expanded);
    if(attempt.answer) parent.append(node("p",attempt.answer,"prompt"));
    if(attempt.activity.length || Object.keys(attempt.metrics).length)
      summary(parent,"Tool activity and resource usage",{tools:attempt.activity,usage:attempt.metrics,
        execution:attempt.execution,admission:attempt.admission},key+"activity",expanded);
    if(attempt.patch) {
      summary(parent,"Source diff",attempt.patch,key+"diff",expanded);
      if(!attempt.patch.includes("[Preview truncated. See the on-disk artifact.]"))
      parent.append(button("Save patch",()=>{
        const url=URL.createObjectURL(new Blob([attempt.patch],{type:"text/plain"}));
        const link=document.createElement("a");link.href=url;link.download=report.job+".patch";link.click();
        setTimeout(()=>URL.revokeObjectURL(url),1000);
      }));
    }
    if(attempt.verification.length)
      summary(parent,"Independent verification results",attempt.verification,key+"verification",expanded);
  }
}

el("projects").onchange=()=>act(()=>selectProject(el("projects").value));
el("pick").onclick=()=>act(async()=>{
  const picked=await api("/api/pick",{});
  if(picked.project) {
    data=await api("/api/desktop");
    await selectProject(picked.project);
  }
});
el("new").onclick=()=>act(newThread);
el("history-tab").onclick=()=>{el("history").hidden=!el("history").hidden;};
el("screen-tab").onclick=()=>{el("screen").hidden=!el("screen").hidden;};
el("native").onclick=()=>act(async()=>{
  if(!thread) await newThread();
  const result=await api("/api/native",{thread,specialist:el("native-mode").value});
  if(result.job) {selectedJob=result.job;await refresh();}
});

const shellQuote=value=>"'"+value.replaceAll("'","'\"'\"'")+"'";
el("composer").onsubmit=event=>{
  event.preventDefault();
  act(async()=>{
    if(!thread) await newThread();
    const result=await api("/api/draft",{thread,model:el("models").value,prompt:el("prompt").value,
                                        ...(attachment?{screen:attachment}:{})});
    const review=await api("/api/review",result.draft);
    draft=result.draft;
    el("read-scope").value=draft.inputs.join("\n");
    el("write-scope").value=draft.write_roots.join("\n");
    el("check").value=draft.commands[0].argv.map(shellQuote).join(" ");
    el("route").textContent=`Compute — ${review.eligible.map(route=>route.profile.id).join(", ")}. `
      + (review.eligible.some(route=>route.profile.location==="a100")?"Approved project inputs may be sent to the existing A100. ":"")
      + `Writable paths — ${draft.write_roots.join(", ")}.`+(attachment?" Includes the reviewed local screen observation.":"");
    el("read-note").textContent="Readable paths — "+draft.inputs.join(", ")+".";
    el("verification-note").textContent="Verification — "+data.checks[result.recipe]+
      (result.recipe==="syntax"?" (syntax verification only).":".");
    el("review").hidden=false;
    el("composer").hidden=true;
    el("approve").focus();
  });
};
el("cancel").onclick=()=>{hideReview();el("prompt").focus();};
el("models").onchange=hideReview;
el("approve").onclick=()=>act(async()=>{
  el("approve").disabled=true;
  try {
    const lines=id=>el(id).value.split(/\r?\n/).map(value=>value.trim()).filter(Boolean);
    const current={...draft,inputs:lines("read-scope"),write_roots:lines("write-scope"),command:el("check").value};
    const review=await api("/api/review",current);
    selectedJob=(await api("/api/queue",{...current,review:review.review})).job;
    el("prompt").value="";
    attachment=null;
    el("attachment").hidden=true;
    hideReview();
    await refresh();
  } finally {el("approve").disabled=false;}
});

function screenButtons() {
  el("capture").disabled=busy;
  el("png").disabled=busy;
  el("interpret").disabled=busy || !screenPng || !data?.local_perception;
  el("attach").disabled=busy || !observation;
}
async function preview(base64) {
  const image=new Image();
  image.src="data:image/png;base64,"+base64;
  await image.decode();
  if(image.width>4096||image.height>4096||image.width*image.height>4096*2160)
    throw new Error("Image dimensions exceed the screenshot limit.");
  screenPng=base64;
  screenImage=image;
  observation=null;
  el("elements").replaceChildren();
  draw();
}
function draw(active) {
  const canvas=el("preview");
  canvas.hidden=false;canvas.width=screenImage.width;canvas.height=screenImage.height;
  const ctx=canvas.getContext("2d");
  ctx.drawImage(screenImage,0,0);
  ctx.lineWidth=3;ctx.font="18px sans-serif";
  for(const element of observation?.elements||[]) {
    const [x,y,r,b]=element.bbox.map((value,i)=>value*(i%2?canvas.height:canvas.width));
    ctx.strokeStyle=element.id===active?"#ffea30":element.kind==="text"?"#21b8e8":"#ee58e9";
    ctx.strokeRect(x,y,r-x,b-y);ctx.fillStyle="#122a34";ctx.fillRect(x,y,30,22);
    ctx.fillStyle=ctx.strokeStyle;ctx.fillText(element.id,x+3,y+17);
  }
}
async function screenAction(action) {
  busy=true;screenButtons();
  try {await action();}
  finally {busy=false;screenButtons();}
}
el("capture").onclick=()=>act(()=>screenAction(async()=>preview((await api("/api/capture",{})).png)));
el("png").onchange=()=>act(()=>screenAction(async()=>{
  const file=el("png").files[0];if(!file) return;
  if(file.type!=="image/png" || file.size>4*1024*1024) throw new Error("Choose a PNG of up to 4 MiB.");
  const image=await new Promise((resolve,reject)=>{
    const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(",")[1]);reader.onerror=reject;
    reader.readAsDataURL(file);
  });
  await preview(image);
}));
el("interpret").onclick=()=>act(()=>screenAction(async()=>{
  el("notice").textContent="Interpreting locally…";
  observation=await api("/api/perception",{png:screenPng,location:"local"});
  el("notice").textContent="";
  draw();
  el("elements").replaceChildren(...observation.elements.map(item=>button(
    `${item.id} · ${item.description || item.kind}`,()=>draw(item.id))));
}));
el("attach").onclick=()=>act(async()=>{
  const laptop=data.models.find(p=>p.location==="local");
  if(!laptop) throw new Error("No laptop model is configured.");
  el("models").value=laptop.id;
  hideReview();
  attachment=observation;
  el("attachment").hidden=false;
  el("screen").hidden=true;
  el("prompt").focus();
});
el("detach").onclick=()=>{attachment=null;el("attachment").hidden=true;};
act(refresh);
setInterval(()=>refresh().catch(()=>{}),3500);
