from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.db.models import Q
from django.db import transaction
from django.utils.html import escape
from core.media import media_url_available
import re

from .models import (
    Category, NewsArticle, NewsArticleInlineImage, NewsArticleInlineAttachment,
    OfficialBulletin, JobOpening,
)
from .forms import (
    CategoryForm, NewsArticleForm, OfficialBulletinForm, JobOpeningForm,
    JobOpeningAttachmentFormSet,
)
from .permissions import CMSManagementAccessMixin
from .sanitizers import sanitize_article_html


# Public Content Views
class PublicNewsListView(ListView):
    model = NewsArticle
    template_name = 'cms/public_news_list.html'
    context_object_name = 'articles'
    paginate_by = 9

    def get_queryset(self):
        queryset = NewsArticle.objects.filter(status=NewsArticle.Status.PUBLISHED).select_related('category', 'author')
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(excerpt__icontains=search_query) |
                Q(content__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['selected_category'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class PublicNewsDetailView(DetailView):
    model = NewsArticle
    template_name = 'cms/public_news_detail.html'
    context_object_name = 'article'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return NewsArticle.objects.filter(status=NewsArticle.Status.PUBLISHED).select_related(
            'category', 'author'
        ).prefetch_related('images', 'attachments')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Forms sanitize new content, and this second pass keeps legacy records
        # safe if they were created before the editor's validation existed.
        content = sanitize_article_html(self.object.content)

        def replace_missing_image(match):
            return match.group(0) if media_url_available(match.group('url')) else (
                '<p class="text-muted small">No files or data available.</p>'
            )

        def replace_missing_link(match):
            return match.group(0) if media_url_available(match.group('url')) else (
                '<span class="text-muted small">No files or data available.</span>'
            )

        context['article_content'] = re.sub(
            r"""<img\b[^>]*\bsrc=["'](?P<url>[^"']+)["'][^>]*>""",
            replace_missing_image,
            content,
            flags=re.IGNORECASE,
        )
        context['article_content'] = re.sub(
            r"""<a\b[^>]*\bhref=["'](?P<url>[^"']+)["'][^>]*>.*?</a>""",
            replace_missing_link,
            context['article_content'],
            flags=re.IGNORECASE | re.DOTALL,
        )
        return context


class PublicBulletinListView(ListView):
    model = OfficialBulletin
    template_name = 'cms/public_bulletin_list.html'
    context_object_name = 'bulletins'
    paginate_by = 12

    def get_queryset(self):
        queryset = OfficialBulletin.objects.all().select_related('uploaded_by')
        bulletin_type = self.request.GET.get('type')
        if bulletin_type:
            queryset = queryset.filter(bulletin_type=bulletin_type)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type_choices'] = OfficialBulletin.BulletinType.choices
        context['selected_type'] = self.request.GET.get('type', '')
        return context


class PublicBulletinDetailView(DetailView):
    model = OfficialBulletin
    template_name = 'cms/public_bulletin_detail.html'
    context_object_name = 'bulletin'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'


class NewsInlineContentMixin:
    """Persist images and documents inserted through the article-body editor."""

    document_extensions = {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.odt', '.ods', '.rtf', '.txt', '.csv', '.zip',
    }

    def form_valid(self, form):
        invalid_files = []
        for key in self.request.POST.getlist('inline_attachment_keys'):
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key):
                continue
            uploaded_file = self.request.FILES.get(f'inline_attachment_{key}')
            if uploaded_file and not any(uploaded_file.name.lower().endswith(extension) for extension in self.document_extensions):
                invalid_files.append(uploaded_file.name)
        if invalid_files:
            form.add_error('content', _(
                'Supporting files must be documents, text files, CSV files, or ZIP archives.'
            ))
            return self.form_invalid(form)
        with transaction.atomic():
            response = super().form_valid(form)
            self.save_inline_images()
            self.save_inline_attachments()
        return response

    def save_inline_images(self):
        """Replace editor upload placeholders with saved CMS media URLs and captions."""
        content = self.object.content
        for key in self.request.POST.getlist('inline_image_keys'):
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key):
                continue
            uploaded_file = self.request.FILES.get(f'inline_image_{key}')
            if not uploaded_file:
                continue
            caption = self.request.POST.get(f'inline_image_caption_{key}', '')[:255]
            inline_image = NewsArticleInlineImage.objects.create(
                article=self.object,
                image=uploaded_file,
                caption=caption,
            )
            replacement = (
                '<figure class="article-inline-image">'
                f'<img src="{escape(inline_image.image.url)}" alt="{escape(caption or self.object.title)}">'
                f'<figcaption>{escape(caption)}</figcaption>'
                '</figure>'
            )
            placeholder = re.compile(
                r'<figure\b[^>]*\bdata-upload-key="' + re.escape(key) + r'"[^>]*>.*?</figure>',
                re.IGNORECASE | re.DOTALL,
            )
            content = placeholder.sub(replacement, content)
        if content != self.object.content:
            self.object.content = content
            self.object.save(update_fields=['content', 'updated_at'])

    def save_inline_attachments(self):
        """Replace document placeholders with local download links inside the article."""
        content = self.object.content
        for key in self.request.POST.getlist('inline_attachment_keys'):
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', key):
                continue
            uploaded_file = self.request.FILES.get(f'inline_attachment_{key}')
            if not uploaded_file:
                continue
            title = self.request.POST.get(f'inline_attachment_title_{key}', '').strip()[:255]
            inline_attachment = NewsArticleInlineAttachment.objects.create(
                article=self.object,
                file=uploaded_file,
                title=title,
            )
            label = title or uploaded_file.name
            replacement = (
                '<figure class="article-inline-attachment">'
                f'<a href="{escape(inline_attachment.file.url)}" target="_blank" rel="noopener">{escape(label)}</a>'
                '<figcaption>Supporting document</figcaption>'
                '</figure>'
            )
            placeholder = re.compile(
                r'<figure\b[^>]*\bdata-attachment-upload-key="' + re.escape(key) + r'"[^>]*>.*?</figure>',
                re.IGNORECASE | re.DOTALL,
            )
            content = placeholder.sub(replacement, content)
        if content != self.object.content:
            self.object.content = content
            self.object.save(update_fields=['content', 'updated_at'])


# Admin Management Views
class AdminNewsListView(CMSManagementAccessMixin, ListView):
    permission_code = 'news.view'
    model = NewsArticle
    template_name = 'cms/admin_news_list.html'
    context_object_name = 'articles'
    paginate_by = 15

    def get_queryset(self):
        queryset = NewsArticle.objects.select_related('category', 'author').all().order_by('-created_at')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(excerpt__icontains=q) |
                Q(content__icontains=q) |
                Q(author__username__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['status_choices'] = NewsArticle.Status.choices
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class NewsCreateView(CMSManagementAccessMixin, NewsInlineContentMixin, CreateView):
    permission_code = 'news.create'
    model = NewsArticle
    form_class = NewsArticleForm
    template_name = 'cms/news_form.html'
    success_url = reverse_lazy('cms:admin_news_list')

    def form_valid(self, form):
        if form.cleaned_data.get('status') == NewsArticle.Status.PUBLISHED and not self.request.user.has_portal_permission('news.publish'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(_("You do not have permission to publish news."))
        form.instance.author = self.request.user
        if form.cleaned_data.get('status') == NewsArticle.Status.PUBLISHED and not form.cleaned_data.get('published_at'):
            form.instance.published_at = now()
        messages.success(self.request, _(f"Article '{form.cleaned_data['title']}' created successfully."))
        return super().form_valid(form)


class NewsUpdateView(CMSManagementAccessMixin, NewsInlineContentMixin, UpdateView):
    permission_code = 'news.edit'
    model = NewsArticle
    form_class = NewsArticleForm
    template_name = 'cms/news_form.html'
    success_url = reverse_lazy('cms:admin_news_list')

    def form_valid(self, form):
        if form.cleaned_data.get('status') == NewsArticle.Status.PUBLISHED and not self.request.user.has_portal_permission('news.publish'):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(_("You do not have permission to publish news."))
        if form.cleaned_data.get('status') == NewsArticle.Status.PUBLISHED and not form.cleaned_data.get('published_at'):
            form.instance.published_at = now()
        messages.success(self.request, _(f"Article '{form.cleaned_data['title']}' updated successfully."))
        return super().form_valid(form)


class AdminBulletinListView(CMSManagementAccessMixin, ListView):
    permission_code = 'bulletins.view'
    model = OfficialBulletin
    template_name = 'cms/admin_bulletin_list.html'
    context_object_name = 'bulletins'
    paginate_by = 15

    def get_queryset(self):
        queryset = OfficialBulletin.objects.select_related('uploaded_by').all().order_by('-publication_date', '-created_at')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(summary__icontains=q) |
                Q(uploaded_by__username__icontains=q)
            )
        b_type = self.request.GET.get('type')
        if b_type:
            queryset = queryset.filter(bulletin_type=b_type)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type_choices'] = OfficialBulletin.BulletinType.choices
        context['selected_type'] = self.request.GET.get('type', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class BulletinCreateView(CMSManagementAccessMixin, CreateView):
    permission_code = 'bulletins.create'
    model = OfficialBulletin
    form_class = OfficialBulletinForm
    template_name = 'cms/bulletin_form.html'
    success_url = reverse_lazy('cms:admin_bulletin_list')

    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, _(f"Bulletin '{form.cleaned_data['title']}' uploaded successfully."))
        return super().form_valid(form)


class BulletinUpdateView(CMSManagementAccessMixin, UpdateView):
    permission_code = 'bulletins.edit'
    model = OfficialBulletin
    form_class = OfficialBulletinForm
    template_name = 'cms/bulletin_form.html'
    success_url = reverse_lazy('cms:admin_bulletin_list')

    def form_valid(self, form):
        messages.success(self.request, _(f"Bulletin '{form.cleaned_data['title']}' updated successfully."))
        return super().form_valid(form)


# ─── Career / Job Openings Views ────────────────────────────────────────────

class PublicCareerListView(ListView):
    """Public-facing job openings listing page."""
    model = JobOpening
    template_name = 'cms/public_career_list.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        queryset = JobOpening.objects.filter(
            status=JobOpening.Status.OPEN
        ).select_related('department')
        employment_type = self.request.GET.get('type')
        if employment_type:
            queryset = queryset.filter(employment_type=employment_type)
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(department__name__icontains=q) |
                Q(department__code__icontains=q) |
                Q(description__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employment_type_choices'] = JobOpening.EmploymentType.choices
        context['selected_type'] = self.request.GET.get('type', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class PublicCareerDetailView(DetailView):
    """Public-facing job opening detail page."""
    model = JobOpening
    template_name = 'cms/public_career_detail.html'
    context_object_name = 'job'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return JobOpening.objects.filter(
            status=JobOpening.Status.OPEN
        ).select_related('department').prefetch_related('attachments')


class CareerAttachmentFormsetMixin:
    """Persist repeatable supporting documents with a job opening."""

    def get_attachment_formset(self, instance):
        data = self.request.POST if self.request.method == 'POST' else None
        files = self.request.FILES if self.request.method == 'POST' else None
        return JobOpeningAttachmentFormSet(data, files, instance=instance, prefix='attachments')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = getattr(self, 'object', None) or JobOpening()
        context.setdefault('attachment_formset', self.get_attachment_formset(instance))
        return context

    def form_valid(self, form):
        attachment_formset = self.get_attachment_formset(form.instance)
        if not attachment_formset.is_valid():
            return self.render_to_response(self.get_context_data(
                form=form,
                attachment_formset=attachment_formset,
            ))
        with transaction.atomic():
            response = super().form_valid(form)
            attachment_formset.instance = self.object
            attachment_formset.save()
        return response


class AdminCareerListView(CMSManagementAccessMixin, ListView):
    permission_code = 'careers.view'
    """Admin view listing all job openings (all statuses)."""
    model = JobOpening
    template_name = 'cms/admin_career_list.html'
    context_object_name = 'jobs'
    paginate_by = 15

    def get_queryset(self):
        queryset = JobOpening.objects.select_related('posted_by', 'department').all().order_by('-created_at')
        q = self.request.GET.get('q')
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(department__name__icontains=q) |
                Q(department__code__icontains=q) |
                Q(description__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = JobOpening.Status.choices
        context['selected_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class CareerCreateView(CMSManagementAccessMixin, CareerAttachmentFormsetMixin, CreateView):
    permission_code = 'careers.create'
    """Admin view to create a new job opening."""
    model = JobOpening
    form_class = JobOpeningForm
    template_name = 'cms/career_form.html'
    success_url = reverse_lazy('cms:admin_career_list')

    def form_valid(self, form):
        form.instance.posted_by = self.request.user
        messages.success(self.request, _(f"Job opening '{form.cleaned_data['title']}' created successfully."))
        return super().form_valid(form)


class CareerUpdateView(CMSManagementAccessMixin, CareerAttachmentFormsetMixin, UpdateView):
    permission_code = 'careers.edit'
    """Admin view to edit an existing job opening."""
    model = JobOpening
    form_class = JobOpeningForm
    template_name = 'cms/career_form.html'
    success_url = reverse_lazy('cms:admin_career_list')

    def form_valid(self, form):
        messages.success(self.request, _(f"Job opening '{form.cleaned_data['title']}' updated successfully."))
        return super().form_valid(form)
