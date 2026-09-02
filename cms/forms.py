from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.widgets import AdminFileInput

from .models import (
    Category,
    JobOpening,
    JobOpeningAttachment,
    NewsArticle,
    OfficialBulletin,
)
from .sanitizers import sanitize_article_html, sanitize_job_html


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
            'excerpt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Short summary...'),
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': _('Write news article content here...'),
            }),
            'featured_image': AdminFileInput(attrs={'class': 'form-control'}),
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
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Monthly Climate Outlook - July 2026'),
            }),
            'bulletin_type': forms.Select(attrs={'class': 'form-select'}),
            'pdf_file': AdminFileInput(attrs={'class': 'form-control', 'accept': '.pdf'}),
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
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('e.g. Meteorologist / Senior Officer'),
            }),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Dili, Timor-Leste')}),
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': _('Full job description...'),
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Qualifications, skills, experience...'),
            }),
            'how_to_apply': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': _('Instructions on how to apply...'),
            }),
            'application_deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_description(self):
        description = sanitize_job_html(self.cleaned_data.get('description', ''))
        if not description:
            raise ValidationError(_('The job description cannot be empty.'))
        return description

    def clean_requirements(self):
        return sanitize_job_html(self.cleaned_data.get('requirements', ''))

    def clean_how_to_apply(self):
        return sanitize_job_html(self.cleaned_data.get('how_to_apply', ''))


class JobOpeningAttachmentForm(forms.ModelForm):
    allowed_extensions = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.rtf', '.txt', '.csv', '.zip',
    }

    class Meta:
        model = JobOpeningAttachment
        fields = ['file', 'title']
        widgets = {
            'file': AdminFileInput(attrs={
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
