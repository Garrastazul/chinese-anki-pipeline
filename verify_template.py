import zipfile, sqlite3, json, io, tempfile, os

apkg = r'output/test_chinese-grammar-a1.apkg'

with zipfile.ZipFile(apkg) as z:
    with z.open('collection.anki2') as f:
        raw = f.read()

with tempfile.NamedTemporaryFile(suffix='.anki21', delete=False) as tmp:
    tmp.write(raw)
    tmp.flush()
    tmpname = tmp.name

try:
    conn = sqlite3.connect(tmpname)
    cur = conn.execute("SELECT models FROM col")
    models = json.loads(cur.fetchone()[0])

    for mid, model in models.items():
        if model.get('name') == 'Reorder':
            print(f"Model ID: {mid}")
            print(f"Fields ({len(model['flds'])}): {[f['name'] for f in model['flds']]}")
            for tmpl in model['tmpls']:
                if tmpl.get('name') == 'Card 4':
                    qfmt = tmpl['qfmt']
                    print(f"\n--- qfmt (first 300 chars) ---")
                    print(qfmt[:300])
                    print("...")
                    
                    print("\n--- Checks ---")
                    if "split(' · ')" in qfmt or "split(\' · \')" in qfmt:
                        print("GOOD: split with middle dot")
                    else:
                        idx = qfmt.find('.split(')
                        if idx >= 0:
                            print(f"ISSUE: split char = {repr(qfmt[idx:idx+50])}")
                        else:
                            print("ISSUE: split() not found!")
                    
                    if '+ audio +' in qfmt:
                        print("GOOD: audio in innerHTML")
                    else:
                        print("ISSUE: audio NOT in innerHTML")
                    
                    print("pycmd found:" + (" YES (ISSUE)" if 'pycmd' in qfmt else " NO (GOOD)"))
                    print("setTimeout found:" + (" YES (ISSUE)" if 'setTimeout' in qfmt else " NO (GOOD)"))
                    print("function init found:" + (" YES (ISSUE)" if 'function init' in qfmt else " NO (GOOD)"))
                    print("trim() found:" + (" YES (ISSUE)" if '.trim()' in qfmt else " NO (GOOD)"))
                    
                    afmt = tmpl['afmt']
                    print(f"\n--- afmt ---")
                    print(afmt[:200])
    conn.close()
finally:
    os.unlink(tmpname)
