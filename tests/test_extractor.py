"""Tests for HTML → text extraction."""

from piqued.ingestion.extractor import count_words, extract_text


class TestExtractText:
    def test_empty_html(self):
        assert extract_text("") == ""
        assert extract_text("   ") == ""

    def test_simple_paragraph(self):
        result = extract_text("<p>Hello world.</p>")
        assert "Hello world." in result

    def test_headings_become_markdown(self):
        result = extract_text("<h2>My Section</h2>")
        assert "## My Section" in result

    def test_h3_becomes_triple_hash(self):
        result = extract_text("<h3>Subsection</h3>")
        assert "### Subsection" in result

    def test_inline_elements_preserve_spacing(self):
        html = (
            "<p>Tests whether <strong>utility tokens</strong> count as securities.</p>"
        )
        result = extract_text(html)
        assert "utility tokens" in result
        assert "whether utility" in result  # space preserved around <strong>

    def test_lists_become_bullets(self):
        html = "<ul><li>First</li><li>Second</li></ul>"
        result = extract_text(html)
        assert "- First" in result
        assert "- Second" in result

    def test_blockquote_prefixed(self):
        html = "<blockquote>A wise quote.</blockquote>"
        result = extract_text(html)
        assert "> A wise quote." in result

    def test_horizontal_rule_becomes_separator(self):
        html = "<p>Before</p><hr><p>After</p>"
        result = extract_text(html)
        assert "---" in result

    def test_scripts_stripped(self):
        html = "<p>Content</p><script>alert('xss')</script>"
        result = extract_text(html)
        assert "Content" in result
        assert "alert" not in result

    def test_multi_section_article(self):
        html = """
        <h2>Topic One</h2>
        <p>First section content.</p>
        <hr>
        <h2>Topic Two</h2>
        <p>Second section content.</p>
        """
        result = extract_text(html)
        assert "## Topic One" in result
        assert "## Topic Two" in result
        assert "First section" in result
        assert "Second section" in result

    def test_table_flattened(self):
        html = "<table><tr><th>Name</th><th>Value</th></tr><tr><td>A</td><td>1</td></tr></table>"
        result = extract_text(html)
        assert "Name" in result
        assert "A" in result

    def test_pre_block_preserved(self):
        html = "<pre>def foo():\n    return 42</pre>"
        result = extract_text(html)
        assert "def foo():" in result


class TestCountWords:
    def test_simple(self):
        assert count_words("hello world") == 2

    def test_empty(self):
        assert count_words("") == 0

    def test_multiline(self):
        assert count_words("one\ntwo\nthree") == 3
