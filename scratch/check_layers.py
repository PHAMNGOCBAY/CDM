import sqlite3, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
con = sqlite3.connect('data/TTHC.sqlite')
con.row_factory = sqlite3.Row
cur = con.cursor()

print('=== LAYERS symbols/description QTT ===')
cur.execute("""
    SELECT b.name AS bname, l.symbol, l.description, l.depth_top_m, l.depth_bot_m
    FROM layers l JOIN boreholes b ON l.borehole_id = b.id
    WHERE b.zone_id = 4 ORDER BY b.name, l.depth_top_m
""")
rows = cur.fetchall()
bh_cur = None
for r in rows:
    nm = r['bname']
    if nm != bh_cur:
        bh_cur = nm
        print(f'--- {bh_cur} ---')
    sym = r['symbol'] or ''
    desc = (r['description'] or '')[:50]
    print(f'  sym={sym:4s} | {r["depth_top_m"]:5.1f}-{r["depth_bot_m"]:5.1f}m | {desc}')

print()
print('=== ND-07 layers detail (id=59) ===')
cur.execute("""
    SELECT id, symbol, description, depth_top_m, depth_bot_m, thickness_m
    FROM layers WHERE borehole_id = 59 ORDER BY depth_top_m
""")
for r in cur.fetchall():
    sym = r['symbol'] or ''
    desc = r['description'] or ''
    print(f'  id={r["id"]} sym={sym:5s} | {r["depth_top_m"]:5.1f}-{r["depth_bot_m"]:5.1f}m | thick={r["thickness_m"]:.2f}m | {desc}')

print()
print('=== ND-05 layers detail (id=57) ===')
cur.execute("""
    SELECT id, symbol, description, depth_top_m, depth_bot_m, thickness_m
    FROM layers WHERE borehole_id = 57 ORDER BY depth_top_m
""")
for r in cur.fetchall():
    sym = r['symbol'] or ''
    desc = r['description'] or ''
    print(f'  id={r["id"]} sym={sym:5s} | {r["depth_top_m"]:5.1f}-{r["depth_bot_m"]:5.1f}m | thick={r["thickness_m"]:.2f}m | {desc}')

print()
print('=== UI MAPPING: Lớp QTT trên app_cdm.py ===')
print('  app_cdm.py dùng _CLAY_SYMBOLS["QTT"] = ["1","2"] → lớp bùn sét yếu')
print()
print('=== LAYERS symbol mapping (SQLite vs MD/UI) ===')
print('  Trong SQLite, lớp F (san lấp) lưu symbol=1, lớp CH lưu symbol=2,...')
print('  MD dùng symbol F,1,2,3,4 theo tên địa tầng thực')
print()
print('  ND-02: SQLite sym 1/2/3/4 ~ MD F/Lop1(CH)/Lop2(CL-CH)/Lop3(ML)')
print('  ND-04: MD lop1(CH)=0-29.5m nhưng SQLite sym=1 mà KHÔNG có lớp F → OK')

con.close()
