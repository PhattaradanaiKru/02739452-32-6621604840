const $ = s => document.querySelector(s);
const names = {estat:'e-Stat',undata:'UNdata',geonames:'GeoNames'};
const number = n => new Intl.NumberFormat('th-TH').format(n);
const shortNumber = n => new Intl.NumberFormat('th-TH',{maximumFractionDigits:2}).format(n);
const compact = n => n>=1000000?shortNumber(n/1000000)+' ล้าน':n>=1000?shortNumber(n/1000)+' พัน':number(n);
const prefecturesTH = {'Aichi':'ไอจิ','Akita':'อากิตะ','Aomori':'อาโอโมริ','Chiba':'ชิบะ','Ehime':'เอฮิเมะ','Fukui':'ฟุกุอิ','Fukuoka':'ฟุกุโอกะ','Fukushima':'ฟุกุชิมะ','Gifu':'กิฟุ','Gunma':'กุนมะ','Hiroshima':'ฮิโรชิมะ','Hokkaido':'ฮอกไกโด','Hyōgo':'เฮียวโงะ','Hyogo':'เฮียวโงะ','Ibaraki':'อิบารากิ','Ishikawa':'อิชิกาวะ','Iwate':'อิวาเตะ','Kagawa':'คางาวะ','Kagoshima':'คาโงชิมะ','Kanagawa':'คานางาวะ','Kochi':'โคจิ','Kumamoto':'คุมาโมโตะ','Kyoto':'เกียวโต','Mie':'มิเอะ','Miyagi':'มิยางิ','Miyazaki':'มิยาซากิ','Nagano':'นางาโนะ','Nagasaki':'นางาซากิ','Nara':'นาระ','Niigata':'นีงาตะ','Oita':'โออิตะ','Okayama':'โอกายามะ','Okinawa':'โอกินาวะ','Osaka':'โอซากะ','Saga':'ซางะ','Saitama':'ไซตามะ','Shiga':'ชิงะ','Shimane':'ชิมาเนะ','Shizuoka':'ชิซูโอกะ','Tochigi':'โทจิงิ','Tokushima':'โทคุชิมะ','Tokyo':'โตเกียว','Tottori':'ทตโตริ','Toyama':'โทยามะ','Wakayama':'วากายามะ','Yamagata':'ยามางาตะ','Yamaguchi':'ยามางูจิ','Yamanashi':'ยามานาชิ'};
const prefectureName = name => prefecturesTH[name] || name;
const statusesTH = {success:'สำเร็จ',degraded:'สำเร็จบางแหล่ง',quality_failed:'ไม่ผ่านคุณภาพ',failed:'ล้มเหลว',running:'กำลังทำงาน',pending:'รอดำเนินการ'};
const reasonsTH = {ambiguous_city:'ชื่อเมืองกำกวม จับคู่ได้มากกว่าหนึ่งเมือง',no_exact_city_match:'ไม่พบเมืองที่ตรงกัน',duplicate_city:'เมืองซ้ำ',missing_name_or_prefecture:'ไม่มีชื่อเมืองหรือจังหวัด',invalid_coordinates:'พิกัดไม่ถูกต้อง',outside_japan_bounds:'พิกัดอยู่นอกขอบเขตญี่ปุ่น',missing_or_invalid_population:'ไม่มีประชากรหรือค่าไม่ถูกต้อง',unexpected_population_year:'ปีข้อมูลไม่ตรงเกณฑ์',not_a_confirmed_city_municipality:'ยังยืนยันไม่ได้ว่าเป็นเทศบาลเมือง'};
const reasonLabel = s => reasonsTH[s] || 'ไม่ผ่านเกณฑ์การตรวจสอบ';
const sourceLabel = s => names[s] || (s==='merged'?'ข้อมูลรวม':'ไม่ทราบแหล่งข้อมูล');
const sourceMessage = s => s.includes('disabled for failure')?'ปิดแหล่งข้อมูลเพื่อทดสอบการกู้คืน':s.includes('Replayed recorded response')?'ใช้ข้อมูลที่บันทึกไว้เพื่อทดสอบเกณฑ์คุณภาพ':'ดึงข้อมูลไม่สำเร็จ โปรดดูรายละเอียดในบันทึกการทำงานของ Airflow';
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date = s => s ? new Date(s).toLocaleString('th-TH',{dateStyle:'medium',timeStyle:'short',timeZone:'Asia/Bangkok'}) : '—';
const badge = s => `<span class="status-badge ${esc(s)}">${esc(statusesTH[s] || 'ไม่ทราบสถานะ')}</span>`;
const pill = s => `<span class="source-pill ${esc(s)}">${esc(sourceLabel(s))}</span>`;
let rows=[], page=0, pageSize=15, currentController;
async function api(url,signal){const r=await fetch(url,{signal});const d=await r.json();if(!r.ok)throw new Error(d.error||'ไม่สามารถอ่านข้อมูลได้');return d;}
function error(e){$('#error').textContent=/[ก-๙]/.test(e.message)?e.message:'ไม่สามารถเชื่อมต่อระบบได้ โปรดตรวจสอบบริการเว็บและฐานข้อมูลแล้วลองอีกครั้ง';$('#error').hidden=false;}
function params(){const p=new URLSearchParams(new FormData($('#filters')));p.set('sort',$('#sort').value);return p;}
async function refreshCities(){
  if(currentController)currentController.abort();currentController=new AbortController();
  try{
    const p=params(),d=await api('/api/cities?'+p,currentController.signal);rows=d.cities;page=0;
    $('#export').href='/api/export.csv?'+p;
    $('#kpi-cities').textContent=number(d.metrics.cities);$('#kpi-population').textContent=compact(d.metrics.population);
    $('#kpi-prefectures').textContent=d.metrics.prefectures;$('#kpi-official').textContent=d.metrics.cities?Math.round(d.metrics.official/d.metrics.cities*100)+'%':'—';
    const selected=$('#prefecture').value;
    $('#prefecture').innerHTML='<option value="">ทุกจังหวัด</option>'+d.prefectures.map(x=>`<option value="${esc(x)}">${esc(prefectureName(x))}</option>`).join('');$('#prefecture').value=selected;
    $('#table-count').textContent=number(rows.length);renderTable();renderRanking();renderMap();$('#error').hidden=true;
  }catch(e){if(e.name!=='AbortError')error(e);}
}
function renderTable(){
  const subset=rows.slice(page*pageSize,(page+1)*pageSize);
  $('#city-table').innerHTML=subset.map((c,i)=>`<tr><td>${String(page*pageSize+i+1).padStart(2,'0')}</td><td><button class="city-name" data-city="${c.geoname_id}">${esc(c.name)}</button><span class="city-code">${esc(c.region_code||'GeoNames '+c.geoname_id)}</span></td><td>${esc(prefectureName(c.prefecture))}</td><td class="numeric">${number(c.population)}</td><td>${c.population_year||'ไม่ระบุปี'}</td><td>${c.sources.map(pill).join('')}</td><td class="coords">${c.latitude.toFixed(3)}° น. · ${c.longitude.toFixed(3)}° ตอ.${c.coordinate_reused?' · พิกัดเดิม':''}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">ไม่พบเมืองตามตัวกรอง ลองล้างตัวกรอง หรือเริ่มรวบรวมข้อมูลครั้งแรกใน Airflow</td></tr>';
  $('#pagination-info').textContent=rows.length?`แสดง ${page*pageSize+1}–${Math.min((page+1)*pageSize,rows.length)} จาก ${number(rows.length)} เมือง`:'ไม่มีเมืองในรายการ';
  $('#previous').disabled=page===0;$('#next').disabled=(page+1)*pageSize>=rows.length;
}
function renderRanking(){
  const top=[...rows].sort((a,b)=>b.population-a.population).slice(0,10),max=top[0]?.population||1;
  $('#ranking').innerHTML=top.map((c,i)=>`<div class="rank-row"><span class="rank-number">${String(i+1).padStart(2,'0')}</span><button class="rank-name" data-city="${c.geoname_id}">${esc(c.name)}</button><div class="bar-track"><div class="bar" style="width:${c.population/max*100}%"></div></div><span class="rank-value">${compact(c.population)}</span></div>`).join('')||'<p class="empty">ไม่มีเมืองในรายการที่เลือก</p>';
}
function renderMap(){
  // Equal-angle longitude/latitude plot. No basemap or guessed boundaries.
  const w=560,h=320,pad=28,lon0=122,lon1=148,lat0=23,lat1=46;
  const x=lon=>pad+(lon-lon0)/(lon1-lon0)*(w-2*pad),y=lat=>h-pad-(lat-lat0)/(lat1-lat0)*(h-2*pad);
  let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="map-title"><title id="map-title">เมืองญี่ปุ่นตามละติจูดและลองจิจูด</title><rect width="${w}" height="${h}" fill="#f7f9f2" rx="5"/>`;
  for(let lon=124;lon<=144;lon+=4)svg+=`<line x1="${x(lon)}" x2="${x(lon)}" y1="14" y2="${h-pad}" stroke="#e5ebdf" stroke-dasharray="3 5"/><text x="${x(lon)}" y="${h-8}" fill="#617563" font-size="8" text-anchor="middle">${lon}° ตอ.</text>`;
  for(let lat=24;lat<=44;lat+=4)svg+=`<line x1="${pad}" x2="${w-12}" y1="${y(lat)}" y2="${y(lat)}" stroke="#e5ebdf" stroke-dasharray="3 5"/><text x="6" y="${y(lat)+3}" fill="#617563" font-size="8">${lat}°</text>`;
  svg+=`<text x="${w-30}" y="35" fill="#617563" font-size="9" text-anchor="end">เหนือ ↑</text><text x="75" y="70" fill="#71866f" font-size="16">ประเทศญี่ปุ่น</text>`;
  for(const c of [...rows].sort((a,b)=>b.population-a.population)){
    const radius=1.6+Math.sqrt(c.population/4000000)*7;
    svg+=`<circle cx="${x(c.longitude)}" cy="${y(c.latitude)}" r="${radius}" fill="#337351" fill-opacity=".43" stroke="#f7f9f2" stroke-width=".5" data-city="${c.geoname_id}" tabindex="0" role="button" aria-label="${esc(c.name)} ประชากร ${number(c.population)} คน" style="cursor:pointer"><title>${esc(c.name)} · ${number(c.population)} คน · ${c.population_year||'ไม่ระบุปี'}</title></circle>`;
  }
  $('#map').innerHTML=svg+'</svg>';
}
async function detail(id){
  try{const d=await api('/api/cities/'+id),c=d.city;
    $('#city-detail').innerHTML=`<h2>${esc(c.name)}</h2><p>จังหวัด${esc(prefectureName(c.prefecture))} · รหัสเทศบาล ${esc(c.region_code||'ยังจับคู่ไม่ได้')}<br>ละติจูด ${c.latitude.toFixed(5)}° เหนือ / ลองจิจูด ${c.longitude.toFixed(5)}° ตะวันออก</p>`+d.observations.map(o=>`<div class="detail-record"><div>${pill(o.source)}<small>${o.year_key?'ค.ศ. '+o.year_key:'ไม่ระบุปี'}</small></div><strong>${number(o.population)} <small>คน</small></strong><div><a href="${esc(o.source_url)}" target="_blank" rel="noopener">เปิดแหล่งข้อมูล ↗</a><small>ดึงเมื่อ ${date(o.fetched_at)}</small></div></div>`).join('')+`<p>เลือกประชากรจาก ${esc(names[c.population_source])} พิกัดเป็นจุดอ้างอิงเทศบาลจาก GeoNames ดึงเมื่อ ${date(c.coordinate_fetched_at)}${c.coordinate_reused?' (ใช้พิกัดเดิมจากรอบที่สำเร็จก่อนหน้า)':''} ปีสำรวจและขอบเขตพื้นที่ที่ต่างกันอาจทำให้ตัวเลขไม่เท่ากัน</p>`;
    $('#city-dialog').showModal();
  }catch(e){error(e);}
}
async function refreshStatus(){
  try{const d=await api('/api/status'),latest=d.runs[0],published=d.published;
    $('#dataset-status').textContent=published?`${number(published.city_count)} เมือง · ${published.status==='degraded'?'เผยแพร่จากแหล่งที่ใช้งานได้':'เผยแพร่ข้อมูลแล้ว'}`:'รอการรวบรวมข้อมูลครั้งแรก';
    $('#dataset-status').closest('.dataset-meta').dataset.status=published?.status||'pending';
    $('#last-updated').textContent=published?'อัปเดตเมื่อ '+date(published.finished_at):'';
    $('#source-cards').innerHTML=['geonames','estat','undata'].map(s=>{const r=d.sources.find(x=>x.source===s);return `<article class="status-card"><h2>${names[s]}</h2>${badge(r?.status||'pending')}<strong>${number(r?.row_count||0)}</strong><small>รายการจากต้นทาง · ${date(r?.finished_at)}</small>${r?.message?`<p><small>${esc(sourceMessage(r.message))}</small></p>`:''}</article>`;}).join('');
    $('#run-table').innerHTML=d.runs.map(r=>`<tr><td>${esc(r.run_id)}</td><td>${badge(r.status)}</td><td>${number(r.city_count)}</td><td>${number(r.rejected_count)}</td><td>${date(r.started_at)}</td><td>${date(r.finished_at)}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">ยังไม่มีประวัติการทำงาน เริ่มงาน japan_city_pipeline ใน Airflow เพื่อรวบรวมข้อมูล</td></tr>';
    const q=latest?.quality;
    $('#quality-summary').dataset.status=q?.valid_cities!==undefined?(q.passed?'success':'quality_failed'):'pending';
    $('#quality-summary').textContent=q?.valid_cities!==undefined?`${q.passed?'ผ่านเกณฑ์คุณภาพ':'ไม่ผ่านเกณฑ์คุณภาพ'} · ${number(q.valid_cities)} เมืองที่ผ่านการตรวจ · ${number(q.official_population_cities)} เมืองมีประชากรปี 2020 · ${number(q.rejected_records)} รายการต้นทางหรือข้อมูลรวมไม่ผ่าน${q.reused_coordinate_cities?' · '+number(q.reused_coordinate_cities)+' เมืองใช้พิกัดเดิม':''}`:'ผลตรวจคุณภาพจะแสดงหลังรวบรวมข้อมูลครั้งแรก';
    $('#rejection-reasons').innerHTML=d.rejection_reasons.map(r=>`<span>${esc(sourceLabel(r.source))} · ${esc(reasonLabel(r.reason))} (${number(r.count)})</span>`).join('');
    $('#rejected-table').innerHTML=d.rejected.map(r=>`<tr><td>${pill(r.source)}</td><td>${esc(r.name)}</td><td>${esc(reasonLabel(r.reason))}</td></tr>`).join('')||'<tr><td colspan="3" class="empty">ไม่มีรายการที่ไม่ผ่านเกณฑ์</td></tr>';
  }catch(e){error(e);}
}
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.view').forEach(v=>v.hidden=v.id!==b.dataset.view);document.querySelectorAll('.nav').forEach(n=>{n.classList.toggle('active',n===b);if(n===b)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});if(b.dataset.view!=='overview')refreshStatus();}));
let timer;$('#filters').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(refreshCities,250);});$('#filters').addEventListener('submit',e=>e.preventDefault());$('#filters').addEventListener('reset',()=>setTimeout(refreshCities,0));$('#sort').addEventListener('change',refreshCities);
$('#previous').addEventListener('click',()=>{page--;renderTable();});$('#next').addEventListener('click',()=>{page++;renderTable();});
document.addEventListener('click',e=>{const c=e.target.closest('[data-city]');if(c)detail(c.dataset.city);});document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('circle[data-city]')){e.preventDefault();detail(e.target.dataset.city);}});
$('#close-dialog').addEventListener('click',()=>$('#city-dialog').close());$('#city-dialog').addEventListener('click',e=>{if(e.target===$('#city-dialog'))$('#city-dialog').close();});document.querySelectorAll('.refresh').forEach(b=>b.addEventListener('click',()=>{refreshStatus();refreshCities();}));
refreshCities();refreshStatus();setInterval(refreshStatus,30000);
