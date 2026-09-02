from django import forms
from django.core.exceptions import ValidationError
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import re
from django.utils.translation import gettext_lazy as _
from .models import Category, NewsArticle, OfficialBulletin, JobOpening, JobOpeningAttachment


class ArticleHTMLSanitizer(HTMLParser):
    """Allow the small, presentation-focused HTML subset produced by the article editor."""
    allowed_tags = {'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 'blockquote', 'h2', 'h3', 'figure', 'figcaption', 'img', 'a'}
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
        cleaned = []
        for name, value in attrs:
            if name not in self.allowed_attributes.get(tag, set()) or value is None:
                continue
            if name == 'href' and not re.match(r'^(https?://|mailto:|/)', value, re.IGNORECASE):
                continue
            if name == 'src' and not value.startswith('/media/'):
                continue
            if name in {'data-upload-key', 'data-attachment-upload-key'} and not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
                continue
            cleaned.append(f' {name}="{escape(value, quote=True)}"')
        self.parts.append(f'<{tag}{"".join(cleaned)}>')

    def handle_endtag(self, tag):
        if tag in self.allowed_tags and tag not in self.void_tags:
            self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        self.parts.append(escape(data))

    def get_html(self):
        return ''.join(self.parts)


def sanitize_article_html(value):
    sanitizer = ArticleHTMLSanitizer()
    sanitizer.feed(value or '')
    sanitizer.close()
    html = sanitizer.get_html().strip()
    if not re.search(r'<(p|h2|h3|ul|ol|blockquote|figure)\b', html):
        paragraphs = [segment.strip() for segment in html.split('\n\n') if segment.strip()]
        html = ''.join(f'<p>{paragraph.replace(chr(10), "<br>")}</p>' for paragraph in paragraphs)
    return html

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Category Name')}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class NewsArticleForm(forms.ModelForm):
    class Meta:
        model = NewsArticle
        fields = ['title', 'category', 'excerpt', 'content', 'featured_image', 'status', 'published_at']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Article Title')}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Short summary...')}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': _('Write news article content here...')}),
            'featured_image': forms.FileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'published_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def clean_content(self):
        content = sanitize_article_html(self.cleaned_data.get('content', ''))
        if not content:
            raise ValidationError(_('The article body cannot be empty.'))
        return content


class OfficialBulletinForm(forms.ModelForm):
    class Meta:
        model = OfficialBulletin
        fields = ['title', 'bulletin_type', 'pdf_file', 'summary', 'publication_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Monthly Climate Outlook - July 2026')}),
            'bulletin_type': forms.Select(attrs={'class': 'form-select'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'publication_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class JobOpeningForm(forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = [
            'title', 'department', 'location', 'employment_type',
            'description', 'requirements', 'how_to_apply',
            'application_deadline', 'status',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('e.g. Meteorologist / Senior Officer')}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Dili, Timor-Leste')}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 8, 'placeholder': _('Full job description...')}),
            'requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': _('Qualifications, skills, experience...')}),
            'how_to_apply': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': _('Instructions on how to apply...')}),
            'application_deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class JobOpeningAttachmentForm(forms.ModelForm):
    allowed_extensions = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.rtf', '.txt', '.csv', '.zip',
    }

    class Meta:
        model = JobOpeningAttachment
        fields = ['file', 'title']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.xls,.xlsx,.odt,.ods,.rtf,.txt,.csv,.zip',
            }),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Document title')}),
        }

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if not uploaded_file:
            return uploaded_file
        extension = Path(uploaded_file.name).suffix.lower()
        if extension not in self.allowed_extensions:
            raise ValidationError(_(
                'Upload a document or archive file (PDF, Office document, text, CSV, or ZIP), not an image.'
            ))
        return uploaded_file


JobOpeningAttachmentFormSet = forms.inlineformset_factory(
    JobOpening, JobOpeningAttachment, form=JobOpeningAttachmentForm, extra=3, can_delete=True
)
