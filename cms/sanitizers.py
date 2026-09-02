"""HTML sanitizers shared by CMS forms and public rendering."""

import re
from html import escape
from html.parser import HTMLParser


def _wrap_plain_text_paragraphs(html, block_tags):
    """Wrap plain editor text in paragraphs without altering structured HTML."""
    block_pattern = '|'.join(re.escape(tag) for tag in block_tags)
    if re.search(rf'<({block_pattern})\b', html):
        return html

    paragraphs = [segment.strip() for segment in html.split('\n\n') if segment.strip()]
    return ''.join(
        f'<p>{paragraph.replace(chr(10), "<br>")}</p>'
        for paragraph in paragraphs
    )


class ArticleHTMLSanitizer(HTMLParser):
    """Allow the presentation-focused HTML produced by the article editor."""

    allowed_tags = {
        'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li',
        'blockquote', 'h2', 'h3', 'figure', 'figcaption', 'img', 'a',
    }
    allowed_attributes = {
        'a': {'href', 'title'},
        'figure': {'class', 'data-upload-key', 'data-attachment-upload-key'},
        'img': {'src', 'alt'},
        'p': {'class'},
    }
    void_tags = {'br', 'img'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed_tags:
            return

        cleaned_attributes = []
        for name, value in attrs:
            if name not in self.allowed_attributes.get(tag, set()) or value is None:
                continue
            if name == 'href' and not re.match(
                r'^(https?://|mailto:|/(?!/))', value, re.IGNORECASE
            ):
                continue
            if name == 'src' and not value.startswith('/media/'):
                continue
            if name in {'data-upload-key', 'data-attachment-upload-key'} and not re.fullmatch(
                r'[A-Za-z0-9_-]{1,64}', value
            ):
                continue
            cleaned_attributes.append(f' {name}="{escape(value, quote=True)}"')

        self.parts.append(f'<{tag}{"".join(cleaned_attributes)}>')

    def handle_endtag(self, tag):
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(escape(data))

    def get_html(self):
        return ''.join(self.parts)


class JobHTMLSanitizer(ArticleHTMLSanitizer):
    """Allow only the formatting controls offered by the job-post editor."""

    allowed_tags = {
        'p', 'br', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li',
        'blockquote', 'h2', 'h3', 'a',
    }
    allowed_attributes = {'a': {'href', 'title'}}
    void_tags = {'br'}

    def handle_starttag(self, tag, attrs):
        # Browsers commonly create div elements when Enter is pressed in a
        # contenteditable surface. Normalize those elements into paragraphs.
        super().handle_starttag('p' if tag == 'div' else tag, attrs)

    def handle_endtag(self, tag):
        super().handle_endtag('p' if tag == 'div' else tag)


def _sanitize(value, sanitizer_class, block_tags):
    sanitizer = sanitizer_class()
    sanitizer.feed(value or '')
    sanitizer.close()
    html = sanitizer.get_html().strip()
    return _wrap_plain_text_paragraphs(html, block_tags)


def sanitize_article_html(value):
    """Normalize article HTML while removing unsupported and unsafe markup."""
    return _sanitize(
        value,
        ArticleHTMLSanitizer,
        ('p', 'h2', 'h3', 'ul', 'ol', 'blockquote', 'figure'),
    )


def sanitize_job_html(value):
    """Normalize job-post HTML while removing scripts and unsafe links."""
    return _sanitize(
        value,
        JobHTMLSanitizer,
        ('p', 'h2', 'h3', 'ul', 'ol', 'blockquote'),
    )
