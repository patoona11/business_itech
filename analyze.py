import pandas as pd
import json

file = '3. สนามกอล์ฟ-ปีงบ 69-เดือน-12-68.xlsm'
xl = pd.ExcelFile(file)
res = {}

for sheet in xl.sheet_names:
    try:
        df = xl.parse(sheet)
        res[sheet] = {
            'rows': len(df),
            'cols': len(df.columns),
            'headers': [str(c) for c in df.columns]
        }
    except Exception as e:
        res[sheet] = {'error': str(e)}

with open('summary.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
