import os,uuid,tempfile
from datetime import datetime,timezone
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
from databricks.sdk import WorkspaceClient
from databricks import sql
from lakebase import init,upsert_review,reviews

st.set_page_config(page_title='Manufacturing Drawing Intelligence',page_icon=':material/precision_manufacturing:',layout='wide')

NAVY='#0B2545'; STEEL='#13315C'; ACCENT='#F28C28'; GREY='#5C6B7A'
COLORWAY=['#13315C','#F28C28','#3E8EDE','#2A9D8F','#E63946','#8D99AE','#6A4C93','#F4A261']

st.markdown('''<style>
header[data-testid="stHeader"]{background:transparent;height:0}
#MainMenu,footer{visibility:hidden}
.block-container{padding-top:1rem;padding-bottom:0;max-width:1500px}
.mfg-header{display:flex;justify-content:space-between;align-items:center;
  background:linear-gradient(90deg,#0B2545 0%,#13315C 60%,#1F4E79 100%);color:#fff;
  padding:18px 28px;border-radius:12px;border-bottom:4px solid #F28C28;margin-bottom:10px}
.mfg-brand{display:flex;align-items:center;gap:16px}
.mfg-logo{width:46px;height:46px;border-radius:10px;background:#F28C28;display:flex;align-items:center;justify-content:center}
.mfg-title{font-size:1.55rem;font-weight:700;letter-spacing:.3px;line-height:1.2}
.mfg-sub{font-size:.85rem;color:#C9D6E3;letter-spacing:.6px;text-transform:uppercase}
.mfg-meta{display:flex;gap:10px;align-items:center;font-size:.8rem}
.mfg-pill{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);padding:5px 12px;border-radius:20px}
.mfg-live{color:#7CFC9A;font-weight:700}
.st-key-navbar{background:#fff;border:1px solid #E1E6EC;border-radius:10px;padding:4px 10px;margin-bottom:8px}
.st-key-navbar div[role="radiogroup"]{gap:4px;flex-wrap:wrap}
.st-key-navbar div[role="radiogroup"] label{padding:8px 18px;border-radius:8px;margin:0;cursor:pointer;border-bottom:3px solid transparent}
.st-key-navbar div[role="radiogroup"] label > div:first-child{display:none}
.st-key-navbar div[role="radiogroup"] label p{font-weight:600;color:#13315C}
.st-key-navbar div[role="radiogroup"] label:hover{background:#F2F5F9}
.st-key-navbar div[role="radiogroup"] label:has(input:checked){background:#EEF3F9;border-bottom:3px solid #F28C28}
.st-key-filterbar{background:#F6F8FB;border:1px solid #E1E6EC;border-left:5px solid #13315C;border-radius:10px;padding:10px 16px 2px 16px;margin-bottom:14px}
.mfg-filter-title{font-size:.75rem;font-weight:700;color:#5C6B7A;text-transform:uppercase;letter-spacing:.8px}
div[data-testid="stMetric"]{background:#fff;border:1px solid #E1E6EC;border-top:4px solid #13315C;border-radius:10px;padding:12px 16px;box-shadow:0 1px 3px rgba(11,37,69,.06)}
div[data-testid="stMetricLabel"] p{font-weight:600;color:#5C6B7A;text-transform:uppercase;font-size:.75rem;letter-spacing:.6px}
.mfg-section{font-size:1.05rem;font-weight:700;color:#0B2545;border-left:4px solid #F28C28;padding-left:10px;margin:14px 0 6px 0}
.mfg-footer{margin-top:36px;background:#0B2545;color:#C9D6E3;border-top:4px solid #F28C28;border-radius:12px 12px 0 0;padding:22px 28px;font-size:.82rem}
.mfg-footer-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:24px}
.mfg-footer h4{color:#fff;font-size:.9rem;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:.8px}
.mfg-footer-bottom{border-top:1px solid rgba(255,255,255,.15);margin-top:16px;padding-top:10px;display:flex;justify-content:space-between;color:#8DA2B8}
</style>''',unsafe_allow_html=True)

GEAR='''<svg width="28" height="28" viewBox="0 0 24 24" fill="#0B2545"><path d="M19.4 13a7.5 7.5 0 0 0 0-2l2.1-1.6-2-3.5-2.5 1a7.4 7.4 0 0 0-1.7-1L15 3.3h-4l-.4 2.6a7.4 7.4 0 0 0-1.7 1l-2.5-1-2 3.5L6.6 11a7.5 7.5 0 0 0 0 2l-2.1 1.6 2 3.5 2.5-1a7.4 7.4 0 0 0 1.7 1l.4 2.6h4l.4-2.6a7.4 7.4 0 0 0 1.7-1l2.5 1 2-3.5zM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7z" transform="translate(-1 0)"/></svg>'''

w=WorkspaceClient()
CATALOG=os.getenv('CATALOG','manufacturing_demo'); SCHEMA=os.getenv('SCHEMA','cad_intelligence')
BASE=f'{CATALOG}.{SCHEMA}'
VOLUME=os.getenv('VOLUME_PATH',f'/Volumes/{CATALOG}/{SCHEMA}/raw_drawings')

def query(q):
    with sql.connect(server_hostname=os.environ['DATABRICKS_HOST'].replace('https://',''),
      http_path=f"/sql/1.0/warehouses/{os.environ['WAREHOUSE_ID']}",
      credentials_provider=lambda:w.config.authenticate) as c:
        with c.cursor() as cur:
            cur.execute(q)
            return pd.DataFrame(cur.fetchall(),columns=[d[0] for d in cur.description])

def data(name): return query(f'SELECT * FROM {BASE}.{name}')

@st.cache_data(ttl=300,show_spinner='Loading governed manufacturing data...')
def load_all():
    usage=data('monthly_consumption'); fc=data('part_forecast'); plants=data('plants'); bom=data('extracted_bom')
    usage['month']=pd.to_datetime(usage['month']); fc['month']=pd.to_datetime(fc['month'])
    for c in ['consumed_qty','purchased_qty','stock_on_hand']: usage[c]=pd.to_numeric(usage[c]).fillna(0)
    for c in ['forecast_consumed_qty','projected_purchase_qty','projected_shortage_qty']: fc[c]=pd.to_numeric(fc[c]).fillna(0)
    plants['latitude']=pd.to_numeric(plants['latitude']); plants['longitude']=pd.to_numeric(plants['longitude'])
    bom['qty']=pd.to_numeric(bom['qty']).fillna(0)
    return usage,fc,plants,bom,datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

def style(fig,height=380,unified=True):
    fig.update_layout(template='plotly_white',colorway=COLORWAY,height=height,margin=dict(l=10,r=10,t=40,b=10),
        font=dict(family='Inter, Segoe UI, sans-serif',color='#0B2545'),hovermode='x unified' if unified else 'closest',
        legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,title=None),
        transition=dict(duration=500,easing='cubic-in-out'))
    return fig

def section(t): st.markdown(f'<div class="mfg-section">{t}</div>',unsafe_allow_html=True)

def fmt(n): return f'{n:,.0f}'

# ---------- Header ----------
try:
    usage,fc,plants,bom,refreshed=load_all(); data_ok=True; load_err=None
except Exception as exc:
    data_ok=False; load_err=exc; refreshed='unavailable'
    usage=fc=plants=bom=pd.DataFrame()

n_plants=len(plants) if data_ok else 0
st.markdown(f'''<div class="mfg-header">
  <div class="mfg-brand"><div class="mfg-logo">{GEAR}</div>
    <div><div class="mfg-title">Manufacturing Drawing Intelligence</div>
    <div class="mfg-sub">CAD extraction &middot; Parts demand &middot; Plant network operations</div></div></div>
  <div class="mfg-meta"><span class="mfg-pill"><span class="mfg-live">&#9679;</span> Live</span>
    <span class="mfg-pill">{n_plants} plants</span><span class="mfg-pill">Refreshed {refreshed}</span></div>
</div>''',unsafe_allow_html=True)

# ---------- Nav bar ----------
PAGES=['Overview','Upload & review','Analytics','Demand forecast','Plant network','Ask Genie']
with st.container(key='navbar'):
    page=st.radio('Navigation',PAGES,horizontal=True,label_visibility='collapsed',key='nav')

# ---------- Global filters ----------
FILTER_KEYS=['f_plants','f_parts','f_range','f_fmonth']
def reset_filters():
    for k in FILTER_KEYS: st.session_state.pop(k,None)

if data_ok:
    plant_names=dict(zip(plants.plant_id,plants.plant_name))
    dmin,dmax=usage.month.min().date(),usage.month.max().date()
    months=sorted(fc.month.dt.strftime('%Y-%m').unique())
    with st.container(key='filterbar'):
        st.markdown('<div class="mfg-filter-title">Global filters &middot; applied to every view</div>',unsafe_allow_html=True)
        c1,c2,c3,c4,c5=st.columns([2.2,2.2,2,1.4,.8],vertical_alignment='bottom')
        sel_plants=c1.multiselect('Plants',sorted(plants.plant_id),format_func=lambda p:f'{p} - {plant_names.get(p,p)}',placeholder='All plants',key='f_plants')
        sel_parts=c2.multiselect('Parts',sorted(set(usage.part_id)|set(fc.part_id)),placeholder='All parts',key='f_parts')
        rng=c3.date_input('History window',(dmin,dmax),min_value=dmin,max_value=dmax,key='f_range')
        fmonth=c4.selectbox('Forecast month',['All']+months,key='f_fmonth')
        c5.button('Reset',on_click=reset_filters,width='stretch')
    rng=rng if isinstance(rng,(tuple,list)) else (rng,)
    start=pd.Timestamp(rng[0]); end=pd.Timestamp(rng[1] if len(rng)>1 else rng[0])

    def scope(df):
        out=df
        if sel_plants and 'plant_id' in out: out=out[out.plant_id.isin(sel_plants)]
        if sel_parts and 'part_id' in out: out=out[out.part_id.isin(sel_parts)]
        return out
    u=scope(usage); u=u[u.month.between(start,end)].copy(); u['m']=u.month.dt.strftime('%Y-%m')
    f_all=scope(fc).copy(); f_all['m']=f_all.month.dt.strftime('%Y-%m')
    f=f_all if fmonth=='All' else f_all[f_all.m==fmonth]
    p=plants[plants.plant_id.isin(sel_plants)] if sel_plants else plants
    b=bom[bom.part_id.isin(sel_parts)] if sel_parts else bom
elif page not in ('Upload & review','Ask Genie'):
    st.error(f'Analytics query failed: {load_err}')

# ---------- Pages ----------
if page=='Overview' and data_ok:
    months_u=sorted(u.m.unique())
    def delta(col):
        if len(months_u)<2: return None
        cur=u[u.m==months_u[-1]][col].sum(); prev=u[u.m==months_u[-2]][col].sum()
        return f'{(cur-prev)/prev*100:+.1f}% vs prior month' if prev else None
    latest_stock=u[u.m==months_u[-1]].stock_on_hand.sum() if months_u else 0
    k=st.columns(5)
    k[0].metric('Consumed units',fmt(u.consumed_qty.sum()),delta("consumed_qty"))
    k[1].metric('Purchased units',fmt(u.purchased_qty.sum()),delta("purchased_qty"))
    k[2].metric('Stock on hand (latest)',fmt(latest_stock))
    k[3].metric('Projected shortage',fmt(f.projected_shortage_qty.sum()),delta_color='inverse',
        delta=f'{(f.projected_shortage_qty>0).sum()} part-plant risks' if len(f) else None)
    k[4].metric('BOM lines extracted',fmt(len(b)),f'{b.drawing_id.nunique()} drawings',delta_color='off')
    if u.empty: st.info('No consumption data for the selected filters.')
    else:
        left,right=st.columns([2.2,1])
        with left:
            section('Consumption vs purchasing trend')
            t=u.groupby('month',as_index=False)[['consumed_qty','purchased_qty']].sum()
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=t.month,y=t.consumed_qty,name='Consumed',mode='lines+markers',fill='tozeroy',line=dict(color=STEEL,width=3,shape='spline')))
            fig.add_trace(go.Scatter(x=t.month,y=t.purchased_qty,name='Purchased',mode='lines+markers',line=dict(color=ACCENT,width=3,dash='dot',shape='spline')))
            fig.update_xaxes(rangeslider_visible=True,rangeselector=dict(buttons=[dict(count=3,label='3M',step='month',stepmode='backward'),
                dict(count=6,label='6M',step='month',stepmode='backward'),dict(count=1,label='1Y',step='year',stepmode='backward'),dict(step='all',label='All')]))
            st.plotly_chart(style(fig,420),width='stretch')
        with right:
            section('Consumption share by plant')
            s=u.groupby('plant_id',as_index=False).consumed_qty.sum(); s['plant']=s.plant_id.map(plant_names)
            fig=px.pie(s,names='plant',values='consumed_qty',hole=.58)
            fig.update_traces(textposition='inside',textinfo='percent',pull=[.04]*len(s))
            st.plotly_chart(style(fig,420,False),width='stretch')
        section('Plant x month consumption heatmap')
        hm=u.pivot_table(index='plant_id',columns='m',values='consumed_qty',aggfunc='sum').fillna(0)
        hm.index=[f'{i} - {plant_names.get(i,i)}' for i in hm.index]
        fig=px.imshow(hm,aspect='auto',color_continuous_scale=['#EEF3F9','#3E8EDE','#0B2545'],labels=dict(x='Month',y='',color='Units'))
        st.plotly_chart(style(fig,320,False),width='stretch')

elif page=='Upload & review':
    section('Submit engineering drawing')
    uploaded=st.file_uploader('Upload engineering PDF',type=['pdf'])
    if uploaded and st.button('Upload and start extraction'):
        content=uploaded.getvalue()
        if len(content)>10_000_000 or not content.startswith(b'%PDF'):
            st.error('Only PDF files under 10 MB are accepted.')
        else:
            docid=str(uuid.uuid4()); path=f'{VOLUME}/incoming/{docid}.pdf'
            try:
                # UC volume files API via SDK; use binary IO rather than local filesystem.
                with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
                    f.write(content); f.flush()
                    with open(f.name,'rb') as src: w.files.upload(path,src,overwrite=False)
                init(); upsert_review(docid,uploaded.name,'SUBMITTED')
                run=w.jobs.run_now(job_id=int(os.environ['EXTRACTION_JOB_ID']))
                st.success(f'Uploaded {uploaded.name}. Job run: {run.run_id}. Review ID: {docid}')
            except Exception as exc: st.error(f'Upload/job failed: {exc}')
    section('Drawing review queue')
    try:
        init(); r=reviews()
        st.dataframe(pd.DataFrame(r,columns=['document_id','file_name','status','notes','updated_at']),width='stretch')
        with st.form('review'):
            doc=st.text_input('Review ID'); status=st.selectbox('Review status',['APPROVED','NEEDS_REVIEW','REJECTED'])
            notes=st.text_input('Notes')
            if st.form_submit_button('Save review') and doc:
                matching=[x for x in r if x[0]==doc]
                if matching: upsert_review(doc,matching[0][1],status,notes);st.success('Review saved')
                else: st.error('Unknown document ID')
    except Exception as exc: st.warning(f'Lakebase unavailable: {exc}')
elif page=='Analytics' and data_ok:
    if u.empty: st.info('No consumption data for the selected filters.')
    else:
        left,right=st.columns(2)
        with left:
            section('Monthly consumption by plant (press play)')
            g=u.groupby(['m','plant_id'],as_index=False).consumed_qty.sum().sort_values('m')
            fig=px.bar(g,x='plant_id',y='consumed_qty',color='plant_id',animation_frame='m',
                range_y=[0,g.consumed_qty.max()*1.15],labels={'plant_id':'Plant','consumed_qty':'Units consumed','m':'Month'})
            fig.update_layout(showlegend=False)
            st.plotly_chart(style(fig,430,False),width='stretch')
        with right:
            section('Consumption mix: plant to part')
            tm=u.groupby(['plant_id','part_id'],as_index=False).consumed_qty.sum()
            tm=tm[tm.consumed_qty>0]
            fig=px.treemap(tm,path=[px.Constant('All plants'),'plant_id','part_id'],values='consumed_qty',
                color='consumed_qty',color_continuous_scale=['#EEF3F9','#3E8EDE','#0B2545'])
            fig.update_traces(root_color='#F6F8FB')
            st.plotly_chart(style(fig,430,False),width='stretch')
        left,right=st.columns([1.4,1])
        with left:
            section('Stock on hand by plant')
            so=u.groupby(['month','plant_id'],as_index=False).stock_on_hand.sum()
            fig=px.area(so,x='month',y='stock_on_hand',color='plant_id',labels={'stock_on_hand':'Units','month':'','plant_id':'Plant'})
            fig.update_xaxes(rangeslider_visible=True)
            st.plotly_chart(style(fig,400),width='stretch')
        with right:
            section('Top parts by consumption')
            tp=u.groupby('part_id',as_index=False)[['consumed_qty','purchased_qty']].sum().sort_values('consumed_qty').tail(12)
            fig=go.Figure([go.Bar(y=tp.part_id,x=tp.consumed_qty,orientation='h',name='Consumed',marker_color=STEEL),
                go.Bar(y=tp.part_id,x=tp.purchased_qty,orientation='h',name='Purchased',marker_color=ACCENT)])
            fig.update_layout(barmode='group')
            st.plotly_chart(style(fig,400,False),width='stretch')
    section('Extracted bill of materials')
    if b.empty: st.info('No BOM lines for the selected parts.')
    else:
        l,r=st.columns([1,2])
        mat=b.groupby('material',as_index=False).qty.sum().sort_values('qty',ascending=False)
        fig=px.bar(mat,x='material',y='qty',color='material',labels={'qty':'Quantity','material':''})
        fig.update_layout(showlegend=False)
        l.plotly_chart(style(fig,340,False),width='stretch')
        r.dataframe(b,width='stretch',height=340,hide_index=True,
            column_config={'qty':st.column_config.ProgressColumn('Qty',min_value=0,max_value=float(max(b.qty.max(),1)),format='%d')})

elif page=='Demand forecast' and data_ok:
    k=st.columns(3)
    k[0].metric('Forecast consumption',fmt(f.forecast_consumed_qty.sum()))
    k[1].metric('Projected purchases',fmt(f.projected_purchase_qty.sum()))
    k[2].metric('Projected shortage',fmt(f.projected_shortage_qty.sum()))
    section('Actuals and forecast')
    h=u.groupby('month',as_index=False).consumed_qty.sum()
    fa=f_all.groupby('month',as_index=False)[['forecast_consumed_qty','projected_purchase_qty','projected_shortage_qty']].sum()
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=h.month,y=h.consumed_qty,name='Actual consumption',mode='lines+markers',line=dict(color=STEEL,width=3,shape='spline')))
    if not h.empty and not fa.empty:
        bridge=pd.concat([h.tail(1).rename(columns={'consumed_qty':'forecast_consumed_qty'}),fa[['month','forecast_consumed_qty']]])
        fig.add_trace(go.Scatter(x=bridge.month,y=bridge.forecast_consumed_qty,name='Forecast consumption',mode='lines+markers',line=dict(color=ACCENT,width=3,dash='dash',shape='spline')))
    fig.add_trace(go.Bar(x=fa.month,y=fa.projected_purchase_qty,name='Projected purchases',marker_color='#3E8EDE',opacity=.55))
    fig.add_trace(go.Bar(x=fa.month,y=fa.projected_shortage_qty,name='Projected shortage',marker_color='#E63946',opacity=.8))
    if not fa.empty:
        fig.add_vrect(x0=fa.month.min()-pd.Timedelta(days=15),x1=fa.month.max()+pd.Timedelta(days=15),fillcolor=ACCENT,opacity=.07,line_width=0,
            annotation_text='Forecast horizon',annotation_position='top left')
    fig.update_xaxes(rangeslider_visible=True)
    st.plotly_chart(style(fig,460),width='stretch')
    left,right=st.columns(2)
    with left:
        section('Shortage risk by part')
        sp=f.groupby('part_id',as_index=False).projected_shortage_qty.sum().sort_values('projected_shortage_qty')
        fig=px.bar(sp,x='projected_shortage_qty',y='part_id',orientation='h',color='projected_shortage_qty',
            color_continuous_scale=['#FDECEA','#E63946','#8B0000'],labels={'projected_shortage_qty':'Units short','part_id':''})
        st.plotly_chart(style(fig,400,False),width='stretch')
    with right:
        section('Forecast by plant and month')
        pm=f_all.groupby(['m','plant_id'],as_index=False).forecast_consumed_qty.sum()
        fig=px.bar(pm,x='m',y='forecast_consumed_qty',color='plant_id',barmode='stack',labels={'m':'Month','forecast_consumed_qty':'Units','plant_id':'Plant'})
        st.plotly_chart(style(fig,400),width='stretch')
    with st.expander('Forecast detail'):
        st.dataframe(f.drop(columns=['m']),width='stretch',hide_index=True)

elif page=='Plant network' and data_ok:
    metric_label={'projected_shortage_qty':'Projected shortage','forecast_consumed_qty':'Forecast consumption',
        'projected_purchase_qty':'Projected purchases','consumed_qty':'Historical consumption'}
    mc1,mc2=st.columns([2,1])
    metric=mc1.radio('Column height',list(metric_label),format_func=metric_label.get,horizontal=True)
    pitch=mc2.slider('Map tilt',0,60,45)
    agg=f.groupby('plant_id',as_index=False)[['forecast_consumed_qty','projected_purchase_qty','projected_shortage_qty']].sum()
    hist=u.groupby('plant_id',as_index=False).consumed_qty.sum()
    geo=p.merge(agg,on='plant_id',how='left').merge(hist,on='plant_id',how='left').fillna(0)
    if geo.empty: st.info('No plants match the selected filters.')
    else:
        mx=max(float(geo[metric].max()),1.0)
        geo['elev']=geo[metric]/mx*180000
        geo['value']=geo[metric].astype(int)
        def color(row):
            if metric=='projected_shortage_qty':
                t=row[metric]/mx; return [int(230*t+42*(1-t)),int(57*t+157*(1-t)),int(70*t+143*(1-t)),220]
            return [19,49,92,220]
        geo['color']=geo.apply(color,axis=1)
        for c in ['forecast_consumed_qty','projected_purchase_qty','projected_shortage_qty','consumed_qty']: geo[c]=geo[c].astype(int)
        view=pdk.ViewState(latitude=float(geo.latitude.mean()),longitude=float(geo.longitude.mean()),zoom=4.6 if len(geo)>1 else 7,pitch=pitch,bearing=-10)
        layers=[
            pdk.Layer('ColumnLayer',data=geo,get_position='[longitude, latitude]',get_elevation='elev',elevation_scale=1,radius=16000,
                get_fill_color='color',pickable=True,auto_highlight=True,extruded=True),
            pdk.Layer('ScatterplotLayer',data=geo,get_position='[longitude, latitude]',get_radius=26000,get_fill_color=[242,140,40,90],
                get_line_color=[242,140,40,255],stroked=True,line_width_min_pixels=2,pickable=True),
            pdk.Layer('TextLayer',data=geo,get_position='[longitude, latitude]',get_text='plant_name',get_size=14,get_color=[11,37,69,255],
                get_pixel_offset=[0,22],get_alignment_baseline="'top'",font_weight=700)]
        tooltip={'html':'<b>{plant_name}</b> ({plant_id})<br/>Forecast consumption: {forecast_consumed_qty}<br/>'
            'Projected purchases: {projected_purchase_qty}<br/>Projected shortage: <b>{projected_shortage_qty}</b><br/>Historical consumption: {consumed_qty}',
            'style':{'backgroundColor':'#0B2545','color':'white','fontSize':'12px'}}
        left,right=st.columns([2.4,1])
        with left:
            section(f'European plant network - {metric_label[metric].lower()}'+('' if fmonth=='All' else f' ({fmonth})'))
            st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=view,tooltip=tooltip,map_provider='carto',map_style=pdk.map_styles.CARTO_LIGHT),
                width='stretch')
        with right:
            section('Plant ranking')
            rk=geo.sort_values(metric,ascending=True)
            fig=px.bar(rk,x=metric,y='plant_name',orientation='h',color=metric,
                color_continuous_scale=['#FDECEA','#E63946','#8B0000'] if metric=='projected_shortage_qty' else ['#EEF3F9','#3E8EDE','#0B2545'],
                labels={metric:metric_label[metric],'plant_name':''})
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style(fig,560,False),width='stretch')
        st.dataframe(geo.drop(columns=['elev','value','color']),width='stretch',hide_index=True)

elif page=='Ask Genie':
    section('Ask Genie about parts, demand, or plants')
    space=os.getenv('GENIE_SPACE_ID','')
    if not space: st.warning('Configure GENIE_SPACE_ID app resource.')
    if data_ok and (sel_plants or sel_parts):
        st.caption('Global filters are added to your question as context.')
    question=st.text_input('Question',placeholder='e.g. Which plants have the highest projected shortage next month?')
    if st.button('Ask Genie',type='primary') and question and space:
        ctx=''
        if data_ok and sel_plants: ctx+=f" Only consider plants {', '.join(sel_plants)}."
        if data_ok and sel_parts: ctx+=f" Only consider parts {', '.join(sel_parts)}."
        try:
            with st.spinner('Genie is analysing governed data...'):
                reply=w.genie.start_conversation_and_wait(space_id=space,content=question+ctx)
            for att in (reply.attachments or []):
                if att.text and att.text.content: st.markdown(att.text.content)
                if att.query:
                    if att.query.description: st.markdown(att.query.description)
                    try:
                        res=w.genie.get_message_attachment_query_result(space_id=space,conversation_id=reply.conversation_id,
                            message_id=reply.message_id or reply.id,attachment_id=att.attachment_id)
                        sr=res.statement_response
                        cols=[c.name for c in sr.manifest.schema.columns]
                        st.dataframe(pd.DataFrame(sr.result.data_array or [],columns=cols),width='stretch',hide_index=True)
                    except Exception as exc: st.caption(f'Could not load query result: {exc}')
                    with st.expander('Generated SQL'): st.code(att.query.query or '',language='sql')
            with st.expander('Raw Genie response'): st.json(reply.as_dict())
            st.caption('Response is generated by Genie; inspect SQL and results before procurement decisions.')
        except Exception as exc:st.error(f'Genie error: {exc}')

# ---------- Footer ----------
st.markdown(f'''<div class="mfg-footer"><div class="mfg-footer-grid">
  <div><h4>Manufacturing Drawing Intelligence</h4>Engineering drawings, bills of materials and parts demand across the European plant network,
    in one governed workspace for operations, procurement and engineering teams.</div>
  <div><h4>Platform</h4>Unity Catalog governed Delta tables<br/>Lakebase review store<br/>Genie natural-language analytics</div>
  <div><h4>Operations</h4>{n_plants} plants monitored<br/>Data refreshed {refreshed}<br/>Catalog {BASE}</div>
</div><div class="mfg-footer-bottom"><span>&copy; {datetime.now().year} Manufacturing Operations &middot; Synthetic data for demonstration</span>
  <span>Powered by Databricks Apps</span></div></div>''',unsafe_allow_html=True)
