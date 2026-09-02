from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.conf import settings
import uuid

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name=_('Category Name'))
    slug = models.SlugField(max_length=120, unique=True, blank=True, verbose_name=_('Slug'))
    description = models.TextField(blank=True, verbose_name=_('Description'))

    class Meta:
        ordering = ['name']
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class NewsArticle(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        PUBLISHED = 'PUBLISHED', _('Published')
        ARCHIVED = 'ARCHIVED', _('Archived')

    title = models.CharField(max_length=255, verbose_name=_('Title'))
    slug = models.SlugField(max_length=280, unique=True, blank=True, verbose_name=_('Slug'))
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
        verbose_name=_('Category')
    )
    excerpt = models.TextField(verbose_name=_('Excerpt / Summary'), help_text=_('Short overview displayed in cards and search results.'))
    content = models.TextField(verbose_name=_('Full Article Content'))
    featured_image = models.ImageField(
        upload_to='news/',
        null=True,
        blank=True,
        verbose_name=_('Featured Image')
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_('Publication Status')
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='news_articles',
        verbose_name=_('Author')
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Publication Date'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        verbose_name = _('News Article')
        verbose_name_plural = _('News Articles')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=['DRAFT', 'PUBLISHED', 'ARCHIVED']),
                name='cms_article_status_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-published_at', '-created_at'], name='cms_article_status_pub_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class NewsArticleImage(models.Model):
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Article')
    )
    image = models.ImageField(upload_to='news/images/', verbose_name=_('Image'))
    caption = models.CharField(max_length=255, blank=True, verbose_name=_('Caption / Label'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = _('News Article Image')
        verbose_name_plural = _('News Article Images')

    def __str__(self):
        return self.caption or self.image.name


class NewsArticleAttachment(models.Model):
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('Article')
    )
    file = models.FileField(upload_to='news/documents/', verbose_name=_('Supporting File'))
    title = models.CharField(max_length=255, blank=True, verbose_name=_('File Title'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = _('News Article Attachment')
        verbose_name_plural = _('News Article Attachments')

    def __str__(self):
        return self.title or self.file.name


class NewsArticleInlineImage(models.Model):
    """An image inserted at a specific point within an article's rich-text body."""
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name='inline_images',
        verbose_name=_('Article')
    )
    image = models.ImageField(upload_to='news/content/', verbose_name=_('Inline Image'))
    caption = models.CharField(max_length=255, blank=True, verbose_name=_('Image Caption'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = _('Inline Article Image')
        verbose_name_plural = _('Inline Article Images')

    def __str__(self):
        return self.caption or self.image.name


class NewsArticleInlineAttachment(models.Model):
    """A document inserted at a specific point within an article's rich-text body."""
    article = models.ForeignKey(
        NewsArticle,
        on_delete=models.CASCADE,
        related_name='inline_attachments',
        verbose_name=_('Article')
    )
    file = models.FileField(upload_to='news/content/documents/', verbose_name=_('Inline Supporting File'))
    title = models.CharField(max_length=255, blank=True, verbose_name=_('Document Title'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = _('Inline Article Attachment')
        verbose_name_plural = _('Inline Article Attachments')

    def __str__(self):
        return self.title or self.file.name


class OfficialBulletin(models.Model):
    class BulletinType(models.TextChoices):
        # DAILY_SYNOPTIC = 'DAILY_SYNOPTIC', _('Daily Synoptic Bulletin')
        # MONTHLY_CLIMATE = 'MONTHLY_CLIMATE', _('Monthly Climate Outlook')
        # MARINE = 'MARINE', _('Marine Bulletin')
        # SEISMIC = 'SEISMIC', _('Seismic Event Summary')
        # SPECIAL = 'SPECIAL', _('Special Hydrometeorological Report')

        DAILY_SYNOPTIC = 'DAILY_SYNOPTIC', _('Daily Synoptic Bulletin')
        WEEKLY_SYNOPTIC = 'WEEKLY_SYNOPTIC', _('Weekly Synoptic Bulletin')
        MONTHLY_CLIMATE = 'MONTHLY_CLIMATE', _('Monthly Climate Outlook')
        SEASONAL_CLIMATE = 'SEASONAL_CLIMATE', _('Seasonal Climate Outlook')
        ANNUAL_CLIMATE = 'ANNUAL_CLIMATE', _('Annual Climate Report')
        MARINE = 'MARINE', _('Marine Bulletin')
        SEISMIC = 'SEISMIC', _('Seismic Event Summary')
        SPECIAL = 'SPECIAL', _('Special Hydrometeorological Report')

    title = models.CharField(max_length=255, verbose_name=_('Bulletin Title'))
    slug = models.SlugField(max_length=280, unique=True, blank=True, verbose_name=_('Slug'))
    bulletin_type = models.CharField(
        max_length=30,
        choices=BulletinType.choices,
        default=BulletinType.DAILY_SYNOPTIC,
        verbose_name=_('Bulletin Type')
    )
    pdf_file = models.FileField(
        upload_to='bulletins/',
        verbose_name=_('PDF Document File')
    )
    summary = models.TextField(blank=True, verbose_name=_('Summary / Overview'))
    publication_date = models.DateField(verbose_name=_('Publication Date'))
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bulletins',
        verbose_name=_('Uploaded By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-publication_date', '-created_at']
        verbose_name = _('Official Bulletin')
        verbose_name_plural = _('Official Bulletins')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(bulletin_type__in=[
                    'DAILY_SYNOPTIC', 'WEEKLY_SYNOPTIC', 'MONTHLY_CLIMATE',
                    'SEASONAL_CLIMATE', 'ANNUAL_CLIMATE', 'MARINE', 'SEISMIC', 'SPECIAL',
                ]),
                name='cms_bulletin_type_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['bulletin_type', '-publication_date', '-created_at'], name='cms_bulletin_type_date_idx'),
        ]

    def __str__(self):
        return f"{self.get_bulletin_type_display()} - {self.title} ({self.publication_date})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or 'bulletin'
            candidate = base_slug
            number = 2
            while OfficialBulletin.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{number}"
                number += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class JobOpening(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        OPEN = 'OPEN', _('Open')
        CLOSED = 'CLOSED', _('Closed')

    class EmploymentType(models.TextChoices):
        FULL_TIME = 'FULL_TIME', _('Full Time')
        PART_TIME = 'PART_TIME', _('Part Time')
        CONTRACT = 'CONTRACT', _('Contract')
        INTERNSHIP = 'INTERNSHIP', _('Internship')
        VOLUNTEER = 'VOLUNTEER', _('Volunteer')

    title = models.CharField(max_length=255, verbose_name=_('Job Title'))
    slug = models.SlugField(max_length=280, unique=True, blank=True, verbose_name=_('Slug'))
    department = models.ForeignKey(
        'hr.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_openings',
        verbose_name=_('Department'),
    )
    location = models.CharField(max_length=150, default='Dili, Timor-Leste', verbose_name=_('Location'))
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
        verbose_name=_('Employment Type')
    )
    description = models.TextField(verbose_name=_('Job Description'))
    requirements = models.TextField(blank=True, verbose_name=_('Requirements'))
    how_to_apply = models.TextField(blank=True, verbose_name=_('How to Apply'))
    application_deadline = models.DateField(null=True, blank=True, verbose_name=_('Application Deadline'))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_('Status')
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='job_openings',
        verbose_name=_('Posted By')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Job Opening')
        verbose_name_plural = _('Job Openings')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(employment_type__in=[
                    'FULL_TIME', 'PART_TIME', 'CONTRACT', 'INTERNSHIP', 'VOLUNTEER',
                ]),
                name='cms_job_type_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=['DRAFT', 'OPEN', 'CLOSED']),
                name='cms_job_status_valid',
            ),
        ]
        indexes = [
            models.Index(fields=['status', '-created_at'], name='cms_job_status_created_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            self.slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class JobOpeningAttachment(models.Model):
    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('Job Opening')
    )
    file = models.FileField(upload_to='careers/documents/', verbose_name=_('Supporting File'))
    title = models.CharField(max_length=255, blank=True, verbose_name=_('File Title'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        verbose_name = _('Job Opening Attachment')
        verbose_name_plural = _('Job Opening Attachments')

    def __str__(self):
        return self.title or self.file.name
