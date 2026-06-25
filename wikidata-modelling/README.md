# Wikidata modelling: Bulgarian Red Book conservation status

How to record each species' [Red Data Book of the Republic of Bulgaria](https://www.wikidata.org/wiki/Q12296472)
listing on Wikidata **without a new property**, using the existing generic
property [regional conservation status (P14254)](https://www.wikidata.org/wiki/Property:P14254).

## QuickStatements batch

Live import batch (1,072 statements): [QuickStatements batch #259821](https://quickstatements.toolforge.org/#/batch/259821)

Source file: [`quickstatements.tsv`](quickstatements.tsv) (generated from `tracking.csv`; 23 taxa without `wikidata_qid` omitted).

## Decision

No `BG Red Book taxon ID` property is proposed. Instead we attach the Bulgarian
Red Book category directly to each taxon item with **P14254**, disambiguated by
qualifier and sourced to the e-ecodb entry. This matches how P14254 is intended
to be used for national/regional Red Lists (Sweden, UAE, etc.), so it needs no
community approval and can be batch-loaded today.

## The statement model

For each taxon item (`wikidata_qid` in `tracking.csv`):

```
<taxon>  regional conservation status (P14254) = <IUCN category item>
         ├─ qualifier:  applies to jurisdiction (P1001)  = Bulgaria (Q219)
         ├─ qualifier:  statement supported by (P3680)   = Red Data Book of Bulgaria (Q12296472)
         └─ reference:  stated in (P248)        = Q12296472
                        reference URL (P854)     = <redbook_url>
                        retrieved (P813)         = <date>
```

- **Main value** = the IUCN-category item matching `redbook_status`.
- **P1001 qualifier** records the region the status applies to: Bulgaria (Q219).
- **P3680 qualifier** is what makes this unambiguous: a taxon may carry several
  P14254 statements (different countries/lists); the qualifier says *which* list.
- **Reference** points to the exact e-ecodb page (`redbook_url`) so the claim is
  verifiable and traceable back to the project's sources.

Global IUCN status stays separate: [P141](https://www.wikidata.org/wiki/Property:P141)
(+ [P627](https://www.wikidata.org/wiki/Property:P627)) for the worldwide
assessment. Do **not** put the BG category in P141 — P141 means "assigned by IUCN".

## Status mapping (`redbook_status` → P14254 value)

| Code | Wikidata item | Label |
|---|---|---|
| CR | [Q219127](https://www.wikidata.org/wiki/Q219127) | Critically Endangered |
| EN | [Q96377276](https://www.wikidata.org/wiki/Q96377276) | Endangered status |
| VU | [Q278113](https://www.wikidata.org/wiki/Q278113) | Vulnerable |
| RE | [Q10594853](https://www.wikidata.org/wiki/Q10594853) | Regionally Extinct |
| EX | [Q237350](https://www.wikidata.org/wiki/Q237350) | extinct species |

Notes:
- **EN**: use `Q96377276` (the item P141/P14254 canonically use). `Q11394`
  (endangered species) is auto-replaced to `Q96377276` on P141 anyway.
- **RE** (regionally extinct) is a regional-only IUCN category — appropriate here
  precisely because P14254 is *regional* (it is not in the global P141 one-of list).
- **EX**: the Bulgarian Red Book "Изчезнал" is treated as `extinct species`
  (Q237350). If a taxon survives elsewhere, `Regionally Extinct` (Q10594853) may
  be the more accurate regional value — decide per case for the 31 EX rows.

## Worked examples (from `tracking.csv`)

| Taxon | QID | redbook_url | Code | P14254 value |
|---|---|---|---|---|
| *Euphorbia aleppica* | [Q12230481](https://www.wikidata.org/wiki/Q12230481) | `vol1/Eupalepp.html` | EN | Q96377276 |
| *Aldrovanda vesiculosa* | [Q19668](https://www.wikidata.org/wiki/Q19668) | `vol1/Aldvesic.html` | CR | Q219127 |
| *Romanogobio kessleri* | [Q239875](https://www.wikidata.org/wiki/Q239875) | `vol2/Rokessle.html` | EN | Q96377276 |
| *Triturus alpestris* | [Q282715](https://www.wikidata.org/wiki/Q282715) | `vol2/Tralpest.html` | VU | Q278113 |
| *Hottonia palustris* | [Q157882](https://www.wikidata.org/wiki/Q157882) | `vol1/Hotpalus.html` | RE | Q10594853 |
| *Vipera aspis* | [Q572447](https://www.wikidata.org/wiki/Q572447) | `vol2/Viaspis.html` | EX | Q237350 |

## Files

| File | Purpose |
|---|---|
| [`quickstatements.tsv`](quickstatements.tsv) | Generated V1 commands (1,072 lines) — uploaded as [batch #259821](https://quickstatements.toolforge.org/#/batch/259821) |
| [`quickstatements.md`](quickstatements.md) | Batch-import syntax + generator snippet for `tracking.csv` |

Wikidata project page: [Wikidata:WikiProject Bulgaria/Red Book](https://www.wikidata.org/wiki/Wikidata:WikiProject_Bulgaria/Red_Book)

## Properties used

| Property | Role |
|---|---|
| [P14254](https://www.wikidata.org/wiki/Property:P14254) | regional conservation status (main value) |
| [P1001](https://www.wikidata.org/wiki/Property:P1001) | applies to jurisdiction (qualifier → Bulgaria Q219) |
| [P3680](https://www.wikidata.org/wiki/Property:P3680) | statement supported by (qualifier → Q12296472) |
| [P248](https://www.wikidata.org/wiki/Property:P248) | stated in (reference → Q12296472) |
| [P854](https://www.wikidata.org/wiki/Property:P854) | reference URL (→ e-ecodb page) |
| [P813](https://www.wikidata.org/wiki/Property:P813) | retrieved (reference date) |

## Prerequisites / open items

- Confirm [Q12296472](https://www.wikidata.org/wiki/Q12296472) is the right item
  for the *online* edition (e-ecodb). If a distinct item for the web edition is
  preferable, create/choose it and use it in P3680/P248.
- ~1,072 of 1,095 rows already have `wikidata_qid`; the ~23 unresolved taxa
  (see `notes` in `tracking.csv`) are skipped until matched.
- Decide the EX vs Regionally-Extinct call for the 31 `EX` rows.
