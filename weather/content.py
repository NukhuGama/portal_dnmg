"""Sanitisation for meteorologist-authored official forecast content."""

import re
from html import escape
from html.parser import HTMLParser


class ForecastHTMLSanitizer(HTMLParser):
    allowed_tags = {'p', 'br', 'strong', 'b', 'em', 'i', 'h2', 'h3', 'ul', 'ol', 'li', 'a', 'blockquote'}
    void_tags = {'br'}
    allowed_attributes = {'a': {'href', 'target', 'rel'}}
    bootstrap_icon_class_pattern = re.compile(r'^bi\s+bi-[a-z0-9-]+$')
    icon_heading_pattern = re.compile(
        r'(<i class="bi bi-[a-z0-9-]+"></i>)\s*<(h[23])>(.*?)</\2>',
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.discard_depth = 0
        self.span_format_stack = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.discard_depth += 1
            return
        if self.discard_depth:
            return
        if tag == 'span':
            style = next((value or '' for name, value in attrs if name.lower() == 'style'), '')
            formatting_tags = []
            if re.search(r'font-weight\s*:\s*(bold|bolder|[6-9]00)', style, re.IGNORECASE):
                formatting_tags.append('strong')
            if re.search(r'font-style\s*:\s*italic', style, re.IGNORECASE):
                formatting_tags.append('em')
            self.span_format_stack.append(formatting_tags)
            self.parts.extend(f'<{formatting_tag}>' for formatting_tag in formatting_tags)
            return
        # ContentEditable commonly creates divs when the author presses Enter.
        # Store them as semantic paragraphs for consistent public presentation.
        if tag == 'div':
            tag = 'p'
        if tag not in self.allowed_tags:
            return
        cleaned = []
        for name, value in attrs:
            if tag == 'i' and name == 'class' and value:
                # Bootstrap Icons need both classes to render. Restrict the
                # value to one icon so saved rich text cannot inject arbitrary
                # presentation classes.
                class_value = ' '.join(value.split())
                if self.bootstrap_icon_class_pattern.fullmatch(class_value):
                    cleaned.append(f' class="{escape(class_value, quote=True)}"')
                continue
            if tag == 'a' and name == 'rel':
                # A new-tab link always receives the safe rel value below.
                continue
            if name not in self.allowed_attributes.get(tag, set()) or value is None:
                continue
            if name == 'href' and not re.match(r'^(https?://|mailto:)', value, re.IGNORECASE):
                continue
            if name == 'target' and value != '_blank':
                continue
            cleaned.append(f' {name}="{escape(value, quote=True)}"')
        if tag == 'a' and any(name == 'target' and value == '_blank' for name, value in attrs):
            cleaned.append(' rel="noopener noreferrer"')
        self.parts.append(f'<{tag}{"".join(cleaned)}>')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.discard_depth = max(0, self.discard_depth - 1)
            return
        if self.discard_depth:
            return
        if tag == 'span':
            formatting_tags = self.span_format_stack.pop() if self.span_format_stack else []
            self.parts.extend(f'</{formatting_tag}>' for formatting_tag in reversed(formatting_tags))
            return
        if tag == 'div':
            tag = 'p'
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.discard_depth:
            self.parts.append(escape(data))

    def get_html(self):
        html = ''.join(self.parts).strip()
        # Authors often insert an icon and then make the following text a
        # heading. Keep them together as one heading row when that happens.
        return self.icon_heading_pattern.sub(
            lambda match: f'<{match.group(2)}>{match.group(1)} {match.group(3)}</{match.group(2)}>',
            html,
        )


def sanitize_forecast_html(value):
    """Keep a small, safe formatting subset while preserving plain-text drafts."""
    sanitizer = ForecastHTMLSanitizer()
    sanitizer.feed(value or '')
    sanitizer.close()
    html = sanitizer.get_html()
    if html and not re.search(r'<(p|h2|h3|ul|ol|blockquote)\b', html):
        paragraphs = [segment.strip() for segment in html.split('\n\n') if segment.strip()]
        html = ''.join(f'<p>{paragraph.replace(chr(10), "<br>")}</p>' for paragraph in paragraphs)
    return html
