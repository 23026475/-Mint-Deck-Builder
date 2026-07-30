import zipfile, re, sys, json, glob, os
from lxml import etree
ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
def slide_features(z, sldxml):
    r=etree.fromstring(z.read(sldxml))
    texts=[]; sizes=[]
    for t in r.iter('{%s}t'%ns['a']):
        if t.text and t.text.strip(): texts.append(t.text.strip())
    for rp in r.iter('{%s}rPr'%ns['a']):
        if rp.get('sz'): sizes.append(int(rp.get('sz')))
    n_pics=len(list(r.iter('{%s}pic'%ns['p'])))
    n_tbl=len(list(r.iter('{%s}tbl'%ns['a'])))
    n_chart=len([g for g in r.iter('{%s}graphicFrame'%ns['p']) if b'chart' in etree.tostring(g)])
    sps=list(r.iter('{%s}sp'%ns['p']))
    tboxes=[s for s in sps if s.find('.//a:t',ns) is not None]
    all_txt=' '.join(texts).lower()
    words=len(all_txt.split())
    bignums=sum(1 for t in texts if re.match(r'^[R$€£]?\s?[\d,.\s]+%?( ?/ ?\w+)?$',t) and len(t)<20)
    big_font=max(sizes) if sizes else 0
    # repeated similar boxes = card-ish
    xs={}
    for s in tboxes:
        off=s.find('.//a:off',ns)
        if off is not None:
            y=int(off.get('y'))//200000
            xs[y]=xs.get(y,0)+1
    max_row=max(xs.values()) if xs else 0
    return dict(txt=all_txt, words=words, n_pics=n_pics, n_tbl=n_tbl, n_chart=n_chart,
                n_tbox=len(tboxes), bignums=bignums, big_font=big_font, max_row=max_row, first=texts[0].lower() if texts else '')
def classify(f):
    t=f['txt']; first=f['first']
    def has(*ws): return any(w in t for w in ws)
    if f['n_chart']: return 'D02 Chart + takeaway'
    if has('agenda','contents','what we\'re doing'): return 'A03 Agenda'
    if has('thank you'): return 'G03 Thank you'
    if has('next steps') and f['words']<120: return 'G02 Next steps'
    if has('quote','“','”') and f['words']<60: return 'B06 Quote'
    if f['n_tbl'] and has('option','pricing','price','r ','investment') : return 'F02 Pricing options table'
    if f['n_tbl']: return 'D01 Data table'
    if has('meet the team','our team','team info'): return 'E01 Team'
    if f['n_pics']>=6 and f['words']<60: return 'E03 Logo wall'
    if has('case study','success story'): return 'E04 Case study'
    if has('award','winner','partner of the year','inner circle') and f['n_pics']>=3: return 'E05 Awards'
    if has('investment','/ month','/ year','pricing','excl. vat') and f['bignums']>=1: return 'F01 Pricing/stat card'
    if has('prerequisite','terms & conditions','fine print','exclusion'): return 'F03 Prerequisites/terms'
    if re.search(r'w1\b|w\d\d?\b',t) and has('week','phase','wave','month'): return 'C04 Gantt/phase plan'
    if has('roadmap','timeline') and f['bignums']>=3: return 'C02 Timeline/roadmap'
    if has(' vs ','versus','compare','comparison'): return 'B08 Comparison'
    if f['bignums']>=4 and f['big_font']>=3200: return 'D03 KPI dashboard'
    if has('summary','recap','takeaway') and f['words']<130: return 'G01 Summary+CTA'
    if f['words']<25 and f['n_tbox']<=2 and f['n_pics']<=2: return 'A04 Section divider' if f['big_font']>=3200 else 'B05 Full-bleed/statement'
    if f['words']<40 and f['big_font']>=4000: return 'B07 Big statement'
    if f['max_row']>=3 and f['n_tbox']>=6: return 'B02/B03 Card grid'
    if 1<=f['n_pics']<=3 and f['words']>30: return 'B04 Image + text'
    if f['n_tbox']>=4 and has('step','phase','discover','assess','deliver','→'): return 'C01 Process flow'
    if f['words']>=40: return 'B01 Title + bullets'
    return 'UNCLASSIFIED'
def deck(fp):
    z=zipfile.ZipFile(fp)
    slds=sorted([n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$',n)],
                key=lambda n:int(re.search(r'(\d+)',n).group(1)))
    out=[]
    for i,s in enumerate(slds,1):
        fe=slide_features(z,s)
        c='A01/A02 Cover' if i==1 else classify(fe)
        out.append(c)
    return out
if __name__=='__main__':
    agg={}
    for fp in sys.argv[1:]:
        try: r=deck(fp)
        except Exception as e: print(os.path.basename(fp),'ERROR',e); continue
        print(f"\n== {os.path.basename(fp)[:55]} ({len(r)} slides)")
        for i,c in enumerate(r,1): agg[c]=agg.get(c,0)+1
        from collections import Counter
        for k,v in Counter(r).most_common(): print(f"   {v:2d}x {k}")
    print("\n==== AGGREGATE ====")
    for k,v in sorted(agg.items(), key=lambda x:-x[1]): print(f"{v:3d}  {k}")
