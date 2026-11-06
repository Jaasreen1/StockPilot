const $=id=>document.getElementById(id);const money=cents=>(Number(cents)/100).toLocaleString('en-US',{style:'currency',currency:'USD'});let catalog=[];
async function request(path,options={}){const response=await fetch(path,{headers:{'Content-Type':'application/json'},...options});if(!response.ok){let detail='Request failed';try{const body=await response.json();detail=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail)}catch{}throw Error(detail)}return response.status===204?null:response.json()}
function toast(message,error=false){const node=$('toast');node.textContent=message;node.className=error?'error':'';node.style.display='block';clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>node.style.display='none',3500)}
function cell(text,cls){const el=document.createElement('td');el.textContent=String(text);if(cls)el.className=cls;return el}
function action(text,handler){const btn=document.createElement('button');btn.textContent=text;btn.className='small';btn.addEventListener('click',handler);return btn}
function renderProducts(rows){const body=$('products');body.replaceChildren();if(!rows.length){const tr=document.createElement('tr');const td=cell('No products found. Add your first product to get started.','empty');td.colSpan=7;tr.append(td);body.append(tr);return}for(const p of rows){const tr=document.createElement('tr');tr.append(cell(p.name,'product-name'),cell(p.sku,'sku'),cell(p.category),cell(money(p.price_cents)),cell(p.stock));const status=document.createElement('td');const pill=document.createElement('span');pill.className='pill'+(p.stock<=p.reorder_level?' low':'');pill.textContent=p.stock<=p.reorder_level?'Low stock':'In stock';status.append(pill);tr.append(status);const actions=document.createElement('td');actions.className='row-actions';actions.append(action('Stock',()=>openStock(p)),action('Edit',()=>openProduct(p)),action('Delete',()=>removeProduct(p)));tr.append(actions);body.append(tr)}}
function renderMovements(rows){const body=$('movements');body.replaceChildren();if(!rows.length){const tr=document.createElement('tr');const td=cell('No stock movements yet.','empty');td.colSpan=6;tr.append(td);body.append(tr);return}for(const m of rows){const tr=document.createElement('tr');for(const value of [m.product_name,m.kind,m.quantity,m.stock_before+' → '+m.stock_after,m.note||'—',m.created_at])tr.append(cell(value));body.append(tr)}}
async function refresh(){try{const search=$('search').value;const low=$('lowOnly').checked;const [products,metrics,movements,report]=await Promise.all([request('/api/products?search='+encodeURIComponent(search)+'&low_stock='+low),request('/api/metrics'),request('/api/movements'),request('/api/reports/overview')]);catalog=products;renderProducts(products);renderMovements(movements);renderReports(report);$('totalProducts').textContent=metrics.products.toLocaleString();$('totalUnits').textContent=metrics.units.toLocaleString();$('totalValue').textContent=money(metrics.inventory_value_cents);$('lowCount').textContent=metrics.low_stock.toLocaleString()}catch(err){toast(err.message,true)}}
function openProduct(p){const form=$('productForm');form.reset();form.elements.id.value=p?.id??'';$('productTitle').textContent=p?'Edit product':'Add product';$('initialStockLabel').hidden=!!p;if(p){for(const key of ['sku','name','category','reorder_level'])form.elements[key].value=p[key];form.elements.price.value=(p.price_cents/100).toFixed(2)}$('productDialog').showModal()}
function openStock(p){const form=$('stockForm');form.reset();form.elements.product_id.value=p.id;$('stockProduct').textContent=p.name+' · Current stock: '+p.stock;$('stockDialog').showModal()}
async function removeProduct(p){if(!confirm('Delete '+p.name+'? Products with movement history cannot be deleted.'))return;try{await request('/api/products/'+p.id,{method:'DELETE'});toast('Product deleted');refresh()}catch(err){toast(err.message,true)}}
$('productForm').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;const id=form.elements.id.value;const data={sku:form.elements.sku.value,name:form.elements.name.value,category:form.elements.category.value,price:form.elements.price.value,reorder_level:Number(form.elements.reorder_level.value)};if(!id)data.stock=Number(form.elements.stock.value);try{await request(id?'/api/products/'+id:'/api/products',{method:id?'PUT':'POST',body:JSON.stringify(data)});$('productDialog').close();toast(id?'Product updated':'Product created');refresh()}catch(err){toast(err.message,true)}});
$('stockForm').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget;try{await request('/api/products/'+form.elements.product_id.value+'/movements',{method:'POST',body:JSON.stringify({kind:form.elements.kind.value,quantity:Number(form.elements.quantity.value),note:form.elements.note.value})});$('stockDialog').close();toast('Stock updated');refresh()}catch(err){toast(err.message,true)}});
document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',() =>$(button.dataset.close).close()));$('newBtn').addEventListener('click',()=>openProduct());$('refreshBtn').addEventListener('click',refresh);$('lowOnly').addEventListener('change',refresh);let searchTimer;$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(refresh,250)});refresh();
function renderReports(report){
  const categories=$('categoryReport'),reorders=$('reorderReport');
  categories.replaceChildren();reorders.replaceChildren();
  if(!report.categories.length){categories.textContent='Add products to see category insights.';}
  const max=Math.max(1,...report.categories.map(c=>c.value_cents));
  for(const item of report.categories){
    const wrapper=document.createElement('div');wrapper.className='report-item';
    const top=document.createElement('div');top.className='report-line';
    const name=document.createElement('strong');name.textContent=item.category;
    const value=document.createElement('span');value.textContent=money(item.value_cents);
    top.append(name,value);
    const track=document.createElement('div');track.className='bar-track';
    const fill=document.createElement('div');fill.className='bar-fill';fill.style.width=(item.value_cents/max*100)+'%';
    track.append(fill);
    const foot=document.createElement('small');foot.textContent=item.products+' products · '+item.units+' units';
    wrapper.append(top,track,foot);categories.append(wrapper);
  }
  if(!report.low_stock.length){reorders.textContent='All products are above their reorder thresholds.';}
  for(const item of report.low_stock.slice(0,8)){
    const line=document.createElement('div');line.className='reorder-item';
    const detail=document.createElement('div');
    const name=document.createElement('strong');name.textContent=item.name;
    const sub=document.createElement('small');sub.textContent=item.sku+' · '+item.stock+' in stock / '+item.reorder_level+' threshold';
    detail.append(name,sub);
    const count=document.createElement('span');count.className='reorder-count';count.textContent=item.units_to_reorder+' needed';
    line.append(detail,count);reorders.append(line);
  }
}
$('exportProducts').addEventListener('click',()=>{window.location.href='/api/reports/products.csv'});
$('exportMovements').addEventListener('click',()=>{window.location.href='/api/reports/movements.csv'});
