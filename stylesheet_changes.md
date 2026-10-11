# Changes to define2-1.xsl

`defineutils/definehtml/define2-1.xsl` is a modified copy of Lex Jansen's Define-XML v2.1 stylesheet (MIT
license, stylesheet date 2019-02-11; see `define2-1.xsl.LICENSE`). This file records every difference from that
original. **Log each new stylesheet edit here.**

## Background: the serializer, not the stylesheet

Until 2026-10, `definehtml.py` serialized the transform result with `etree.tostring()`. That writes XML and ignores
the stylesheet's `<xsl:output method="html">`, so empty elements were written self-closed (`<span id="x"/>`, `<a/>`,
`<ul/>`). A browser reads `<span .../>` as an unclosed start tag and nests everything after it inside that element.
This caused the "text shown as hyperlinks" problem that commit a0022b8 worked around in the stylesheet (section 1).
The Python code now serializes with `str(result)` / `bytes(result)`, which honor `xsl:output`. Section 2 reverts the
parts of the workaround that broke things.

## 1. Kept from commit a0022b8 (2026-02-03)

- **`displayHyperlink`** tests `string-length($href) > 0` rather than `$href`, and draws the external-link icon only
  when there is an href.
- **Empty anchors** are `<span id>` rather than `<a id>`: `datasets`, `IG.<OID>`, the variable anchors in the dataset
  tables, `decodelist`, `externaldictionary`, `compmethod` and `comment`. Fragment links work on any element, so
  this is harmless now that the output is serialized correctly. The "Create an anchor" comment before the `comment`
  anchor was removed with it.
- **Menu:** the "Supplemental Documents" submenu heading is a `<span>`; upstream it was an `<a>` with no href. The menu
  links use attribute value templates (`href="#IG.{@OID}"`) instead of `xsl:attribute`.
- **`ExternalCodeList/@ref`** is shown as text rather than passed to `displayHyperlink`, since it is an identifier,
  not a URL.

## 2. Reverted from commit a0022b8 (2026-10-10)

- **Menu section headings link to their sections again.** a0022b8's summary said these were `<a>` tags without an
  href. In fact only "Supplemental Documents" was, and the change turned five working links into plain text:

  | Heading | Target |
  |---|---|
  | Analysis Results Metadata | `#ARM_Table_Summary` |
  | CodeLists | `#decodelist` |
  | External Dictionaries | `#externaldictionary` |
  | Methods | `#compmethod` |
  | Comments | `#comment` |

- **The VLM toggle in the dataset tables** is again `<a id="…">VLM</a>`, so the stylesheet's `a{}` and `a:hover{}`
  rules style it as the clickable control it is.
- **`displayHyperlink`'s no-href branch** writes the trailing space again. That space is the only separator between
  the page numbers and named destinations of a document reference. Without it, an unresolved or href-less aCRF
  reference with pages `6 12 18` rendered as `[612 18]`.

## 3. Bug fixes (2026-10-10)

- **NCI codes and domain descriptions come from the right Alias.** The codelist caption, CodeListItem and
  EnumeratedItem templates tested for *any* Alias with `Context='nci:ExtCodeID'` but printed the *first* Alias.
  `getParentDescription` did the same for `Context='DomainDescription'`. All five now select
  `odm:Alias[@Context=…]/@Name`.
- **A Role on a value-level ItemRef no longer adds a column.** The VLM row wrote a Role cell when
  `count($ItemRef/@Role) > 0`, but the header has a Role column only under `$addRoleColumn`. The row now tests
  `$addRoleColumn='1'` alone.
- **Long page lists render.** `linkPages2Hyperlinks` and `linkNamedDestinations2Hyperlinks` recursed once per page or
  destination, and libxslt aborts at a template depth of 3000, so a PDFPageRef with about 995 or more pages failed
  the whole transform. Both now iterate with EXSLT `str:tokenize` (`xmlns:str="http://exslt.org/strings"`, added to
  `exclude-result-prefixes`). The output is byte-identical to the recursive templates on `tests/define.xml`, the
  ADaM and 360i sample define.xml files, and synthetic page-reference cases.
- **Where-clause values show for unresolved items.** `displayValue` used two complementary tests on `$DataType`. When
  a RangeCheck's `def:ItemOID` is unresolved, `$DataType` is an empty node-set, so both tests were false and the
  CheckValue was never printed. It is now an `xsl:choose`: numeric when `integer`/`float`, quoted otherwise.
- **The dataset caption shows the Define-XML v2.1 class.** It printed only the v2.0 `@def:Class` attribute, and now
  falls back to the v2.1 `def:Class/@Name` element.
- **The title's standard is the first IG standard.** `def:Standard[1][@Type='IG']` selected nothing when the first
  standard is not an IG. It is now `def:Standard[@Type='IG'][1]`, for both the name and the version.
- **VLM where-clause links point into the dataset being rendered.** `tableValueListsInTable` derived the dataset from
  every ItemGroupDef referencing the parent ItemDef, so with a shared ItemDef every dataset's VLM linked to the first
  one. The caller now passes its dataset OID in a new `ItemGroupOID` parameter. The variables `parentDef`,
  `parentOID` and `ParentVName` are no longer used and were removed; each one scanned every ItemDef for every VLM row.
- **ARM data references show only their own where clause.** When an AnalysisResult had two AnalysisDatasets for the
  same dataset, each entry rendered the where clauses of both. `displayWhereClause` is now given the current
  AnalysisDataset (`.`).
- **Print CSS:** added the missing comma between `.formalexpression-reference` and `.valuelist-reference`, so printing
  hides the Formal Expression and VLM markers as intended.

## 4. Performance (2026-10-10)

The stylesheet had no `xsl:key`, so every OID lookup (`$g_seqItemDefs[@OID=$oid]` and about 50 like it) scanned
every definition, and rendering time grew quadratically. Keys now index ItemDef (by OID and by Name), ItemGroupDef
(by OID and by Name), the dataset ItemRefs (by ItemOID), CodeList, ValueListDef, WhereClauseDef, MethodDef, CommentDef
and `def:leaf`.

- Each key's match pattern is anchored at `/odm:ODM/odm:Study[1]/odm:MetaDataVersion[1]`, the node set of the global
  sequences it replaces, so the lookups select exactly the same nodes.
- The related-dataset rows (SUPP--, SQAP--, parent) also switched from `../odm:ItemGroupDef[@Name = …]`, which read
  every child of MetaDataVersion, to the name key. Those templates only run for datasets of the first
  MetaDataVersion.
- The output is byte-identical before and after on all the comparison files.

Timings on synthetic copies of `tests/define.xml` scaled with extra suffixed definitions (lxml 6.0.1):

| File size | Before keys | After keys |
|---|---|---|
| 1.2 MB | 1.74 s | 0.08 s |
| 2.3 MB | 7.66 s | 0.18 s |
| 4.8 MB | 47.6 s (original stylesheet) | 0.43 s |

## 5. Header

A comment after the MIT license header identifies the file as a modified copy and points here.

## Outside the stylesheet

These are done in `definehtml.py`, not in the stylesheet:

- serialization through `xsl:output`;
- the scheme filter that turns any link other than relative, `http`, `https` or `file` into text;
- passing the stylesheet parameters (`nCodeListItemDisplay`, `displayMethodsTable`, `displayCommentsTable`,
  `displayPrefix`, `displayLengthDFormatSD`).
