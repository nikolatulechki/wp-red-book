# Batch import — QuickStatements

Add the Bulgarian Red Book status to each taxon item via
[QuickStatements](https://quickstatements.toolforge.org/) V1 (tab-separated).

**Uploaded batch:** [batch #259821](https://quickstatements.toolforge.org/#/batch/259821) (from [`quickstatements.tsv`](quickstatements.tsv)).

## One statement = one line

```
<QID>	P14254	<STATUS_QID>	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"<redbook_url>"	S813	+<YYYY>-<MM>-<DD>T00:00:00Z/11
```

- `P1001` qualifier → Bulgaria (Q219) — the jurisdiction the status applies to
- `P3680` qualifier → Red Data Book of Bulgaria (Q12296472)
- `S248` / `S854` / `S813` are the reference: stated in / reference URL / retrieved
- `/11` on the date = day precision

## Example lines (the six worked taxa)

```
Q12230481	P14254	Q96377276	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"http://e-ecodb.bas.bg/rdb/bg/vol1/Eupalepp.html"	S813	+2026-06-25T00:00:00Z/11
Q19668	P14254	Q219127	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"http://e-ecodb.bas.bg/rdb/bg/vol1/Aldvesic.html"	S813	+2026-06-25T00:00:00Z/11
Q239875	P14254	Q96377276	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"http://e-ecodb.bas.bg/rdb/bg/vol2/Rokessle.html"	S813	+2026-06-25T00:00:00Z/11
Q282715	P14254	Q278113	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"http://e-ecodb.bas.bg/rdb/bg/vol2/Tralpest.html"	S813	+2026-06-25T00:00:00Z/11
Q157882	P14254	Q10594853	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"http://e-ecodb.bas.bg/rdb/bg/vol1/Hotpalus.html"	S813	+2026-06-25T00:00:00Z/11
Q572447	P14254	Q237350	P1001	Q219	P3680	Q12296472	S248	Q12296472	S854	"http://e-ecodb.bas.bg/rdb/bg/vol2/Viaspis.html"	S813	+2026-06-25T00:00:00Z/11
```

## Generate from `tracking.csv`

```python
import csv
from datetime import date

STATUS = {
    "CR": "Q219127",     # Critically Endangered
    "EN": "Q96377276",   # Endangered status
    "VU": "Q278113",     # Vulnerable
    "RE": "Q10594853",   # Regionally Extinct
    "EX": "Q237350",     # extinct species
}
RED_BOOK = "Q12296472"   # Red Data Book of the Republic of Bulgaria
BULGARIA = "Q219"        # applies to jurisdiction
today = date.today().isoformat()

with open("tracking.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        qid = row["wikidata_qid"].strip()
        status = STATUS.get(row["redbook_status"].strip())
        url = row["redbook_url"].strip()
        if not (qid.startswith("Q") and status and url):
            continue  # skip unresolved taxa / unknown codes
        print(
            f'{qid}\tP14254\t{status}'
            f'\tP1001\t{BULGARIA}'
            f'\tP3680\t{RED_BOOK}'
            f'\tS248\t{RED_BOOK}'
            f'\tS854\t"{url}"'
            f'\tS813\t+{today}T00:00:00Z/11'
        )
```

Pipe the output into QuickStatements (Import → V1 commands). Review a small
batch first; QuickStatements de-duplicates identical statements but will add a
second P14254 value if the status item differs.

## Alternative: pywikibot

The project already uses a bot account. If you prefer programmatic edits over
QuickStatements, the same model maps to `ItemPage.addClaim` + `addQualifier`
(P3680) + `addSource` (P248/P854/P813); see the `wikidata-pybot` skill.
