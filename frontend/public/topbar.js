(function(){
  function qs(sel, ctx=document){ return ctx.querySelector(sel); }
  async function fetchJSON(url, opts={}){
    const resp = await fetch(url, { headers:{'Authorization':'Bearer '+token, ...(opts.headers||{})}, ...opts });
    if(!resp.ok) return null;
    return await resp.json();
  }
  function showToast(msg, type='info'){
    const cont = qs('#toastContainer');
    if(!cont) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    cont.appendChild(toast);
    setTimeout(()=>{
      toast.classList.add('hide');
      toast.addEventListener('animationend',()=>toast.remove(),{once:true});
    },3000);
  }
  window.showToast = showToast;
  const menuBtn = qs('#menuBtn');
  const sideMenu = qs('#sideMenu');
  if(menuBtn && sideMenu){
    menuBtn.addEventListener('click', () => sideMenu.classList.toggle('open'));
  }
  const userArea = qs('#userArea');
  const userPopup = qs('#userPopup');
  const popupClose = qs('#popupClose');
  if(userArea && userPopup && popupClose){
    userArea.addEventListener('click', () => userPopup.classList.remove('hidden'));
    popupClose.addEventListener('click', () => userPopup.classList.add('hidden'));
  }
  const editBtn = qs('#editBtn');
  const saveBtn = qs('#saveBtn');
  const inputs = ['nombre','grupo','curso','niu'].map(f=>qs(`#${f}Input`));
  async function loadPerfil(){
    const data = await fetchJSON(backend + '/me/perfil') || {};
    const p = data.perfil || {};
    qs('#userName').textContent = p.nombre || '';
    qs('#userNIU').textContent = p.niu || '';
    ['nombre','grupo','curso','niu'].forEach(f=>{ const el=qs(`#${f}Input`); if(el) el.value=p[f]||''; });
  }
  loadPerfil();
  function fieldMsg(f, applied){
    const names = {nombre:'Nombre', grupo:'Grupo', curso:'Curso', niu:'NIU'};
    return applied ? `${names[f]} modificado correctamente` : `Cambio de ${names[f]} solicitado correctamente`;
  }
  if(editBtn && saveBtn){
    editBtn.addEventListener('click', ()=>{
      inputs.forEach(i=>{ if(i) i.disabled=false; });
      editBtn.classList.add('hidden');
      saveBtn.classList.remove('hidden');
    });
    saveBtn.addEventListener('click', async ()=>{
      const body={
        nombre: qs('#nombreInput').value,
        grupo: qs('#grupoInput').value,
        curso: qs('#cursoInput').value,
        niu: qs('#niuInput').value
      };
      const resp = await fetch(backend + '/me/perfil', {
        method:'PATCH',
        headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},
        body: JSON.stringify(body)
      });
      const data = await resp.json();
      if(resp.ok){
        inputs.forEach(i=>{ if(i){ i.disabled=true; i.classList.remove('updated','pending'); }});
        editBtn.classList.remove('hidden');
        saveBtn.classList.add('hidden');
        const p = data.perfil || {};
        ['nombre','grupo','curso','niu'].forEach(f=>{ const el=qs(`#${f}Input`); if(el) el.value=p[f]||''; });
        qs('#userName').textContent = p.nombre || '';
        qs('#userNIU').textContent = p.niu || '';
        (data.aplicados||[]).forEach(f=>{ const el=qs(`#${f}Input`); if(el) el.classList.add('updated'); showToast(fieldMsg(f,true),'success'); });
        (data.pendientes_aprobacion||[]).forEach(f=>{ const el=qs(`#${f}Input`); if(el) el.classList.add('pending'); showToast(fieldMsg(f,false),'warning'); });
      }
    });
  }
})();
