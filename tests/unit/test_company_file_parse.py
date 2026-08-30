"""Company file parsing (docx/pdf → property entries) and .env persistence."""

import zipfile
from pathlib import Path

from rental_agent.config.env_file import update_env_file
from rental_agent.contracts import enums as e
from rental_agent.contracts.providers import LlmTaskResult
from rental_agent.enrichment.company.portfolio import (
    entries_deterministic,
    entries_via_llm,
    extract_entries,
    name_fingerprint,
    parse_company_document,
)

_DOC_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <w:body>
  <w:p><w:r><w:t>Company Portfolio 2026</w:t></w:r></w:p>
  <w:p><w:hyperlink r:id="rId1"><w:r><w:t>The Greenpoint</w:t></w:r></w:hyperlink></w:p>
  <w:p><w:r><w:t>Hudson Terrace Apartments - https://example.com/hudson</w:t></w:r></w:p>
 </w:body>
</w:document>
"""

_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1"
  Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
  Target="https://streeteasy.com/building/the-greenpoint" TargetMode="External"/>
</Relationships>
"""


def _write_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", _DOC_XML)
        archive.writestr("word/_rels/document.xml.rels", _RELS_XML)


def test_docx_parse_captures_text_and_links(tmp_path: Path) -> None:
    docx = tmp_path / "portfolio.docx"
    _write_docx(docx)
    doc = parse_company_document(docx)
    assert "Company Portfolio 2026" in doc.text
    urls = {url for _, url, _ in doc.links}
    assert "https://streeteasy.com/building/the-greenpoint" in urls  # hyperlink rel
    assert "https://example.com/hudson" in urls  # plain-text URL


def test_deterministic_entries_pair_names_with_links(tmp_path: Path) -> None:
    docx = tmp_path / "portfolio.docx"
    _write_docx(docx)
    entries = entries_deterministic(parse_company_document(docx))
    by_name = {entry.name: entry.url for entry in entries}
    assert by_name["The Greenpoint"] == "https://streeteasy.com/building/the-greenpoint"
    assert by_name["Hudson Terrace Apartments"] == "https://example.com/hudson"


def test_name_fingerprint_normalizes() -> None:
    assert name_fingerprint("  The   Greenpoint ") == name_fingerprint("the greenpoint")


def test_address_shaped_names_are_detected_and_expanded() -> None:
    from rental_agent.enrichment.company.service import (
        _expand_street_suffixes,
        _looks_like_address,
    )

    assert _looks_like_address("160 water st")
    assert _looks_like_address("22-22 Jackson ave")
    assert not _looks_like_address("The Greenpoint")
    assert not _looks_like_address("Pearl House")
    assert _expand_street_suffixes("160 water st") == "160 water street"
    assert _expand_street_suffixes("4540 center blvd") == "4540 center boulevard"
    # '1st'/'21st' style ordinals must never be rewritten.
    assert _expand_street_suffixes("21 west 1st ave") == "21 west 1st avenue"


class _ScriptedLlm:
    def __init__(self, output: dict | None) -> None:
        self._output = output

    def execute(self, request):  # noqa: ANN001, ANN201 - protocol shape
        if self._output is None:
            return LlmTaskResult(status=e.ModelExecutionStatus.FAILED, error_code="BOOM")
        return LlmTaskResult(status=e.ModelExecutionStatus.SUCCEEDED, output=self._output)


def test_llm_entries_drop_urls_not_in_document(tmp_path: Path) -> None:
    docx = tmp_path / "portfolio.docx"
    _write_docx(docx)
    doc = parse_company_document(docx)
    llm = _ScriptedLlm(
        {
            "entries": [
                {
                    "name": "The Greenpoint",
                    "url": "https://streeteasy.com/building/the-greenpoint",
                    "address": None,
                },
                {"name": "Invented Tower", "url": "https://evil.example.com/injected"},
            ]
        }
    )
    entries = entries_via_llm(llm, doc)
    assert entries is not None
    by_name = {entry.name: entry.url for entry in entries}
    assert by_name["The Greenpoint"] == "https://streeteasy.com/building/the-greenpoint"
    # The model may not introduce URLs that are absent from the document.
    assert by_name["Invented Tower"] is None


def test_extract_entries_falls_back_when_llm_fails(tmp_path: Path) -> None:
    docx = tmp_path / "portfolio.docx"
    _write_docx(docx)
    doc = parse_company_document(docx)
    entries, method = extract_entries(doc, _ScriptedLlm(None))
    assert method == "deterministic"
    assert {entry.name for entry in entries} == {"The Greenpoint", "Hudson Terrace Apartments"}


def test_update_env_file_upserts_and_removes(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\nRENTAL_DB_PORT=5433\nRENTAL_PROVIDER_LLM_BASE_URL=old\n")
    update_env_file(
        env,
        {
            "RENTAL_PROVIDER_LLM_BASE_URL": None,
            "RENTAL_PROVIDER_OPENAI_API_KEY": "sk-test-123",
        },
    )
    content = env.read_text()
    assert "# comment" in content  # untouched lines survive
    assert "RENTAL_DB_PORT=5433" in content
    assert "LLM_BASE_URL" not in content  # None removes
    assert "RENTAL_PROVIDER_OPENAI_API_KEY=sk-test-123" in content
