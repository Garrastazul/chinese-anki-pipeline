import zipfile, sqlite3, json, tempfile, os

apkg = r'output/test_chinese-grammar-a1.apkg'

with zipfile.ZipFile(apkg) as z:
    with z.open('collection.anki2') as f:
        raw = f.read()

with tempfile.NamedTemporaryFile(suffix='.anki2', delete=False) as tmp:
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
                    afmt = tmpl['afmt']

                    print("\n--- qfmt checks ---")
                    print("data-audio div present:", "data-audio" in qfmt)
                    print("'var hanzi' present:", "var hanzi" in qfmt)
                    print("'var pinyinHtml' present:", "var pinyinHtml" in qfmt)
                    print("audio = '{{AudioField}}' present:", "audio = '{{AudioField}}'" in qfmt or "audio = '{{AudioField}}'" in qfmt)
                    print("pinyinHtml = '{{{PinyinHtml}}}' present:", "pinyinHtml = '{{{PinyinHtml}}}'" in qfmt)

                    print("\n--- afmt ---")
                    print(afmt)
    conn.close()
finally:
    os.unlink(tmpname)
