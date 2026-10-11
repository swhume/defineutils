"""Rendering tests for the bundled define2-1.xsl: the fixes made in the local copy of the stylesheet
(each fails against the stylesheet as it was) and a test of each major rendered section."""
import re
from pathlib import Path

import pytest
from lxml import etree

NS = {"odm": "http://www.cdisc.org/ns/odm/v1.3",
      "def": "http://www.cdisc.org/ns/def/v2.1",
      "arm": "http://www.cdisc.org/ns/arm/v1.0",
      "xlink": "http://www.w3.org/1999/xlink"}
ODM = NS["odm"]
DEF = NS["def"]
XLINK_HREF = f"{{{NS['xlink']}}}href"

SDTM_DEFINE = Path(__file__).parent / "define.xml"
# the CDISC ADaM Define-XML v2.1 sample, the only test file with Analysis Results Metadata
ADAM_DEFINE = Path(__file__).parent / "define-adam.xml"


def text(element) -> str:
    """the element's text with whitespace collapsed, as a browser displays it"""
    return " ".join(element.text_content().split())


def source(path: Path = SDTM_DEFINE):
    return etree.parse(str(path))


def dataset_table(page, oid: str):
    return page.xpath(f"//table[normalize-space(@summary)='ItemGroup IG.{oid}']")[0]


def physical_page_refs(tree):
    return tree.xpath("//def:PDFPageRef[@Type='PhysicalRef'][@PageRefs]", namespaces=NS)


# menu (F3)

def test_menu_section_headings_link_to_their_sections(render):
    page = render(SDTM_DEFINE, comments_table=True)

    for heading, target in [("CodeLists", "decodelist"), ("External Dictionaries", "externaldictionary"),
                            ("Methods", "compmethod"), ("Comments", "comment")]:
        assert page.xpath(f"//a[@class='tocItem'][normalize-space()='{heading}']/@href") == [f"#{target}"]
        assert page.get_element_by_id(target, None) is not None


def test_menu_arm_heading_links_to_the_summary(render):
    page = render(ADAM_DEFINE)

    assert page.xpath("//a[@class='tocItem'][normalize-space()='Analysis Results Metadata']/@href") == \
        ["#ARM_Table_Summary"]
    assert page.get_element_by_id("ARM_Table_Summary").tag == "h1"


def test_vlm_toggle_is_a_link_element(render):
    toggle = render(SDTM_DEFINE).xpath("//span[@class='valuelist-reference']")[0]

    assert [child.tag for child in toggle] == ["a"]
    assert text(toggle) == "VLM"


# document references (F6, F14)

@pytest.mark.parametrize("no_link", ["empty href", "unresolved leaf"])
def test_page_numbers_without_a_link_keep_their_separators(edited_define, render, no_link: str):
    def edit(tree):
        page_ref = physical_page_refs(tree)[0]
        page_ref.set("PageRefs", "6 12 18")
        if no_link == "empty href":
            leaf_id = page_ref.getparent().get("leafID")
            tree.xpath(f"//def:leaf[@ID='{leaf_id}']", namespaces=NS)[0].set(XLINK_HREF, "")
        else:
            page_ref.getparent().set("leafID", "LF.missing")

    page_text = text(render(edited_define(edit)))

    assert "[6 12 18 ]" in page_text
    assert "612" not in page_text


def test_page_references_link_each_page(edited_define, render):
    def edit(tree):
        refs = physical_page_refs(tree)
        refs[0].set("PageRefs", "6 12 18")
        del refs[1].attrib["PageRefs"]
        refs[1].set("FirstPage", "3")
        refs[1].set("LastPage", "9")

    page = render(edited_define(edit))
    hrefs = {a.get("href") for a in page.iter("a")}

    assert {"acrf.pdf#page=6", "acrf.pdf#page=12", "acrf.pdf#page=18", "acrf.pdf#page=3",
            "acrf.pdf#page=9"} <= hrefs
    assert "[3 - 9 ]" in text(page)


def test_named_destinations_link_each_destination(edited_define, render):
    def edit(tree):
        named = tree.xpath("//def:PDFPageRef[@Type='NamedDestination']", namespaces=NS)[0]
        named.set("PageRefs", "Dem#20Vit AE CM")

    page = render(edited_define(edit))
    links = page.xpath("//a[contains(@href, '#Dem#20Vit')]")

    assert links
    for link in links:
        assert text(link) == "Dem Vit"
        assert "[Dem Vit AE CM ]" in text(link.getparent())
        assert [a.get("href").split("#", 1)[1] for a in link.getparent().iter("a")] == ["Dem#20Vit", "AE", "CM"]


def test_thousands_of_page_references_render(edited_define):
    # each page was one level of template recursion, and libxslt aborts at a depth of 3000
    from defineutils.definehtml import DefineHtml

    def edit(tree):
        physical_page_refs(tree)[0].set("PageRefs", " ".join(str(n) for n in range(1, 5001)))

    assert "#page=5000" in DefineHtml(edited_define(edit)).transform_to_html_string()


# codelists and datasets (F12, B4, B6)

def test_nci_codes_come_from_the_nci_alias(edited_define, render):
    tree = source()
    codelist = tree.xpath("//odm:CodeList[odm:Alias[@Context='nci:ExtCodeID']][odm:CodeListItem/odm:Alias]",
                          namespaces=NS)[0]
    enumerated = tree.xpath("//odm:CodeList[odm:EnumeratedItem/odm:Alias[@Context='nci:ExtCodeID']]",
                            namespaces=NS)[0]
    codelist_oid, enumerated_oid = codelist.get("OID"), enumerated.get("OID")
    codelist_code = codelist.xpath("odm:Alias[@Context='nci:ExtCodeID']/@Name", namespaces=NS)[0]
    item_code = codelist.xpath("odm:CodeListItem[odm:Alias][1]/odm:Alias/@Name", namespaces=NS)[0]
    enumerated_code = enumerated.xpath("odm:EnumeratedItem[odm:Alias][1]/odm:Alias/@Name", namespaces=NS)[0]

    def sponsor_alias_first(tree):
        nci = "odm:Alias[@Context='nci:ExtCodeID']"
        for alias in [tree.xpath(f"//odm:CodeList[@OID='{codelist_oid}']/{nci}", namespaces=NS)[0],
                      tree.xpath(f"//odm:CodeList[@OID='{codelist_oid}']/odm:CodeListItem[odm:Alias][1]/{nci}",
                                 namespaces=NS)[0],
                      tree.xpath(f"//odm:CodeList[@OID='{enumerated_oid}']/odm:EnumeratedItem[odm:Alias][1]/{nci}",
                                 namespaces=NS)[0]]:
            alias.addprevious(alias.makeelement(f"{{{ODM}}}Alias", Context="SponsorSynonym", Name="SPONSOR-X"))

    page = render(edited_define(sponsor_alias_first))

    caption = page.get_element_by_id(f"CL.{codelist_oid}").xpath("div[@class='codelist-caption']")[0]
    assert caption.xpath("span[@class='nci']/text()") == [codelist_code]
    item_cell = page.get_element_by_id(f"CL.{codelist_oid}").xpath(".//tr[2]/td[1]")[0]
    assert item_cell.xpath("span[@class='nci']/text()") == [item_code]
    enumerated_cell = page.get_element_by_id(f"CL.{enumerated_oid}").xpath(".//tr[2]/td[1]")[0]
    assert enumerated_cell.xpath("span[@class='nci']/text()") == [enumerated_code]
    assert "SPONSOR-X" not in text(page)


def test_domain_description_comes_from_its_alias(edited_define, render):
    def other_alias_first(tree):
        alias = tree.xpath("//odm:ItemGroupDef[@OID='IG.SUPPDM']/odm:Alias[@Context='DomainDescription']",
                           namespaces=NS)[0]
        alias.addprevious(alias.makeelement(f"{{{ODM}}}Alias", Context="SponsorNote", Name="NOT THE DOMAIN"))

    page = render(edited_define(other_alias_first))

    assert text(page.get_element_by_id("IG.SUPPDM").xpath("td[2]")[0]).endswith("(Demographics)")
    assert "NOT THE DOMAIN" not in text(page)


def test_dataset_caption_shows_the_define_21_class(render):
    caption = dataset_table(render(SDTM_DEFINE), "IG.TS").xpath("caption")[0]

    assert ") - TRIAL DESIGN" in text(caption)


def test_title_uses_the_first_ig_standard_after_other_standards(edited_define, render):
    def ct_standards_first(tree):
        standards = tree.xpath("//def:Standards", namespaces=NS)[0]
        for standard in standards.xpath("def:Standard[@Type='CT']", namespaces=NS):
            standards.insert(0, standard)

    title = render(edited_define(ct_standards_first)).find(".//title").text

    assert title.endswith(": SDTMIG 3.1.2, ...")


def test_print_css_hides_the_formal_expression_and_vlm_markers(render):
    css = render(SDTM_DEFINE).xpath("//style")[0].text

    assert re.search(r"\.external-link-gif,\s*\.formalexpression-reference,\s*\.valuelist-reference\s*\{"
                     r"\s*display: none", css)


# value level metadata (F13, F15, B5)

def test_vlm_role_does_not_add_a_column(edited_define, render):
    def role_on_one_vlm_item(tree):
        tree.xpath("//def:ValueListDef[@OID='VL.LB.LBORRES']/odm:ItemRef", namespaces=NS)[0].set("Role", "Result Qualifier")

    table = dataset_table(render(edited_define(role_on_one_vlm_item)), "IG.LB")
    columns = len(table.xpath("tr[@class='header']/th"))

    assert not table.xpath("tr[@class='header']/th[normalize-space()='Role']")
    assert {len(row.xpath("td")) for row in table.xpath("tr[td]")} == {columns}


def test_unresolved_where_clause_item_keeps_its_check_value(edited_define, render):
    tree = source()
    where_oid = tree.xpath("//def:ValueListDef[@OID='VL.LB.LBORRES']/odm:ItemRef[1]/def:WhereClauseRef/@WhereClauseOID",
                           namespaces=NS)[0]
    check = tree.xpath(f"//def:WhereClauseDef[@OID='{where_oid}']/odm:RangeCheck[@Comparator='EQ']",
                       namespaces=NS)[0]
    item_oid, value = check.get(f"{{{DEF}}}ItemOID"), check.findtext("odm:CheckValue", namespaces=NS)

    def unresolve(tree):
        for range_check in tree.xpath(f"//def:WhereClauseDef[@OID='{where_oid}']/odm:RangeCheck", namespaces=NS):
            if range_check.get(f"{{{DEF}}}ItemOID") == item_oid:
                range_check.set(f"{{{DEF}}}ItemOID", "IT.LB.MISSING")

    page = render(edited_define(unresolve))

    assert f'[unresolved: IT.LB.MISSING] = "{value}"' in text(dataset_table(page, "IG.LB"))


def test_shared_vlm_where_clauses_link_into_the_dataset_being_rendered(edited_define, render):
    def share_lb_result_with_xx(tree):
        last = tree.xpath("//odm:ItemGroupDef[@OID='IG.XX']/odm:ItemRef", namespaces=NS)[-1]
        order = int(last.get("OrderNumber"))
        for offset, item_oid in enumerate(["IT.LB.LBTESTCD", "IT.LB.LBSPEC", "IT.LB.LBORRES"], 1):
            item_ref = last.makeelement(f"{{{ODM}}}ItemRef", ItemOID=item_oid, Mandatory="No",
                                        OrderNumber=str(order + offset))
            last.addnext(item_ref)
            last = item_ref

    page = render(edited_define(share_lb_result_with_xx))

    for dataset in ["IG.LB", "IG.XX"]:
        rows = page.xpath(f"//tr[contains(concat(' ', @class, ' '), ' {dataset}.IT.LB.LBORRES ')]")
        links = {a.get("href") for row in rows for a in row.iter("a") if "LBTESTCD" in (a.get("href") or "")}
        assert rows
        assert links == {f"#{dataset}.IT.LB.LBTESTCD"}


# analysis results metadata (B7 and the section)

def test_arm_summary_lists_every_display_and_result(render):
    tree = source(ADAM_DEFINE)
    page = render(ADAM_DEFINE)

    displays = tree.xpath("//arm:ResultDisplay/@OID", namespaces=NS)
    results = tree.xpath("//arm:AnalysisResult/@OID", namespaces=NS)
    assert page.xpath("//div[@class='arm-summary-resultdisplay']/a/@href") == [f"#ARD.{oid}" for oid in displays]
    assert page.xpath("//p[@class='arm-summary-result']/a/@href") == [f"#AR.{oid}" for oid in results]
    assert page.xpath("//a[starts-with(@id, 'ARD.')]/@id") == [f"ARD.{oid}" for oid in displays]
    assert page.xpath("//span[@class='arm-resulttitle']/@id") == [f"AR.{oid}" for oid in results]


def test_arm_details(render):
    tree = source(ADAM_DEFINE)
    page = render(ADAM_DEFINE)

    for result in tree.xpath("//arm:AnalysisResult", namespaces=NS):
        rows = page.get_element_by_id(f"AR.{result.get('OID')}").xpath(
            "ancestor::tr[1]/following-sibling::tr[not(@class='arm-analysisresult')]")
        cells = {text(row.xpath("td[1]")[0]): row.xpath("td[2]")[0] for row in rows[:6]}
        assert text(cells["Analysis Reason"]) == result.get("AnalysisReason")
        assert text(cells["Analysis Purpose"]) == result.get("AnalysisPurpose")
        references = cells["Data References (incl. Selection Criteria)"].xpath("div[@class='arm-data-reference']")
        datasets = result.xpath("arm:AnalysisDatasets/arm:AnalysisDataset/@ItemGroupOID", namespaces=NS)
        assert [text(reference).split(" [")[0] for reference in references] == [oid[3:] for oid in datasets]

    assert len(page.xpath("//pre[@class='arm-code']")) == len(tree.xpath("//arm:Code", namespaces=NS))
    assert page.xpath("//div[@class='arm-code-ref']//a/@href") == ["../programs/at14-5-02-sas.txt"]


def test_arm_data_references_show_only_their_own_where_clause(edited_define, render):
    def second_adqsadas_dataset(tree):
        dataset = tree.xpath("//arm:AnalysisResult[@OID='AR.Table_14-3.01.R.1']/arm:AnalysisDatasets/arm:AnalysisDataset",
                             namespaces=NS)[0]
        second = etree.fromstring(etree.tostring(dataset))
        second.find("def:WhereClauseRef", NS).set("WhereClauseOID", "WC.ADQSADAS.AVAL.ACITM01-ACITM14")
        dataset.addnext(second)

    page = render(edited_define(second_adqsadas_dataset, source=ADAM_DEFINE))
    references = page.get_element_by_id("AR.AR.Table_14-3.01.R.1").xpath(
        "ancestor::tr[1]/following-sibling::tr[td[1][normalize-space()='Data References (incl. Selection Criteria)']][1]"
        "//div[@class='arm-data-reference']")

    assert len(references) == 2
    assert "ACTOT" in text(references[0]) and "ACITM01" not in text(references[0])
    assert "ACITM01" in text(references[1]) and "ACTOT" not in text(references[1])


# the other sections

def test_standards_table(render):
    tree = source()
    table = render(SDTM_DEFINE).get_element_by_id("Standards_Table")

    assert table.xpath("tr[@id]/@id") == [f"STD.{oid}" for oid in tree.xpath("//def:Standard/@OID", namespaces=NS)]


def test_datasets_table_and_a_table_per_dataset(render):
    tree = source()
    page = render(SDTM_DEFINE)

    for dataset in tree.xpath("//odm:ItemGroupDef", namespaces=NS):
        oid = dataset.get("OID")
        assert page.get_element_by_id(oid).xpath("td[1]/a/@href") == [f"#IG.{oid}"]
        assert page.get_element_by_id(f"IG.{oid}") is not None
        variables = dataset_table(page, oid).xpath("tr[td][not(contains(@class, 'vlm'))][not(td/@colspan)]")
        assert len(variables) == len(dataset.xpath("odm:ItemRef", namespaces=NS))


def test_value_level_metadata_rows(render):
    tree = source()
    page = render(SDTM_DEFINE)
    checked = 0

    for dataset in tree.xpath("//odm:ItemGroupDef[not(starts-with(@Name, 'SUPP'))]", namespaces=NS):
        for item_oid in dataset.xpath("odm:ItemRef/@ItemOID", namespaces=NS):
            value_list = tree.xpath(f"//odm:ItemDef[@OID='{item_oid}']/def:ValueListRef/@ValueListOID", namespaces=NS)
            if not value_list:
                continue
            expected = len(tree.xpath(f"//def:ValueListDef[@OID='{value_list[0]}']/odm:ItemRef", namespaces=NS))
            rows = page.xpath(f"//tr[contains(concat(' ', @class, ' '), ' {dataset.get('OID')}.{item_oid} ')]")
            assert len(rows) == expected
            checked += 1
    assert checked >= 6


def test_codelists(render):
    tree = source()
    page = render(SDTM_DEFINE)

    for codelist in tree.xpath("//odm:CodeList[odm:CodeListItem or odm:EnumeratedItem]", namespaces=NS):
        table = page.get_element_by_id(f"CL.{codelist.get('OID')}").xpath("table")[0]
        assert len(table.xpath("tr[td]")) == len(codelist.xpath("odm:CodeListItem|odm:EnumeratedItem", namespaces=NS))


def test_external_dictionaries(render):
    row = render(SDTM_DEFINE).get_element_by_id("CL.CL.ISO.COUNTRY")

    assert [text(cell) for cell in row.xpath("td")[1:]] == ["ISO-3166 (Country Codes)", "2013-11-15"]
    assert row.xpath(".//a/@href") == ["https://www.iso.org/iso-3166-country-codes.html"]


def test_methods_table(render):
    tree = source()
    page = render(SDTM_DEFINE)

    assert page.xpath("//tr[starts-with(@id, 'MT.')]/@id") == \
        [f"MT.{oid}" for oid in tree.xpath("//odm:MethodDef/@OID", namespaces=NS)]
    assert len(page.xpath("//div[@class='formalexpression']")) == \
        len(tree.xpath("//odm:MethodDef/odm:FormalExpression", namespaces=NS))


def test_supplemental_documents_menu(render):
    tree = source()
    submenu = render(SDTM_DEFINE).xpath("//li[span[@class='tocItem'][.='Supplemental Documents']]/ul")[0]

    expected = [tree.xpath(f"//def:leaf[@ID='{leaf_id}']/@xlink:href", namespaces=NS)[0]
                for leaf_id in tree.xpath("//def:SupplementalDoc/def:DocumentRef/@leafID", namespaces=NS)]
    assert submenu.xpath("li/a/@href") == expected


def test_annotated_crf(edited_define, render):
    def annotated_crf(tree):
        supplemental = tree.xpath("//def:SupplementalDoc", namespaces=NS)[0]
        annotated = supplemental.makeelement(f"{{{DEF}}}AnnotatedCRF")
        annotated.append(annotated.makeelement(f"{{{DEF}}}DocumentRef", leafID="LF.acrf"))
        supplemental.addprevious(annotated)

    tree = source()
    page = render(edited_define(annotated_crf))

    menu_entries = page.xpath("//ul[@class='hmenu']/li/a[@href='acrf.pdf']")
    assert [text(entry) for entry in menu_entries] == ["Annotated CRF"]
    pages = {f"acrf.pdf#page={number}"
             for page_refs in tree.xpath("//def:DocumentRef[@leafID='LF.acrf']/def:PDFPageRef/@PageRefs", namespaces=NS)
             for number in page_refs.split()}
    assert {a.get("href") for a in page.iter("a") if (a.get("href") or "").startswith("acrf.pdf#")} == pages
