from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils.timezone import now
from tempfile import TemporaryDirectory
from users.models import User
from hr.models import Department
from .models import (
    Category, NewsArticle, NewsArticleAttachment, NewsArticleInlineImage, NewsArticleInlineAttachment, OfficialBulletin,
    JobOpening, JobOpeningAttachment,
)
from .forms import JobOpeningAttachmentForm, JobOpeningForm, NewsArticleForm

class CMSModelTestCase(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user(
            username="editor_user",
            password="password123",
            role=User.Role.EDITOR
        )
        self.category = Category.objects.create(name="Infrastructure")

    def test_category_slug_auto_generation(self):
        self.assertEqual(self.category.slug, "infrastructure")

    def test_news_article_creation(self):
        article = NewsArticle.objects.create(
            title="New Station Deployed in Ermera",
            category=self.category,
            excerpt="AWS installed in Ermera coffee belt.",
            content="Full details about Ermera station installation...",
            status=NewsArticle.Status.PUBLISHED,
            author=self.editor,
            published_at=now()
        )
        self.assertEqual(article.slug, "new-station-deployed-in-ermera")
        self.assertEqual(article.status, NewsArticle.Status.PUBLISHED)

    def test_official_bulletin_creation(self):
        bulletin = OfficialBulletin.objects.create(
            title="Monthly Climate Outlook July 2026",
            bulletin_type=OfficialBulletin.BulletinType.MONTHLY_CLIMATE,
            publication_date=now().date(),
            uploaded_by=self.editor
        )
        self.assertEqual(bulletin.bulletin_type, OfficialBulletin.BulletinType.MONTHLY_CLIMATE)
        self.assertEqual(bulletin.slug, "monthly-climate-outlook-july-2026")

    def test_official_bulletin_accepts_every_declared_type(self):
        bulletin = OfficialBulletin.objects.create(
            title="Weekly Synoptic Bulletin",
            bulletin_type=OfficialBulletin.BulletinType.WEEKLY_SYNOPTIC,
            publication_date=now().date(),
            uploaded_by=self.editor,
        )
        self.assertEqual(bulletin.bulletin_type, OfficialBulletin.BulletinType.WEEKLY_SYNOPTIC)

    def test_article_and_career_attachments(self):
        article = NewsArticle.objects.create(
            title="Supporting Material",
            excerpt="Summary",
            content="Content",
            author=self.editor,
        )
        attachment = NewsArticleAttachment.objects.create(
            article=article,
            title="Station data",
        )
        job = JobOpening.objects.create(
            title="Climate Officer",
            description="Role description.",
            posted_by=self.editor,
        )
        job_attachment = JobOpeningAttachment.objects.create(
            job_opening=job,
            title="Application form",
        )
        self.assertEqual(article.attachments.get(), attachment)
        self.assertEqual(job.attachments.get(), job_attachment)

    def test_career_attachment_form_rejects_images(self):
        form = JobOpeningAttachmentForm(
            data={'title': 'Not a document'},
            files={'file': SimpleUploadedFile('image.png', b'image data', content_type='image/png')},
        )
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_article_body_html_is_sanitized(self):
        form = NewsArticleForm(data={
            'title': 'Sanitized Article',
            'excerpt': 'Summary',
            'content': '<p>Safe text <strong>with emphasis</strong>.</p><script>alert(1)</script>',
            'status': NewsArticle.Status.DRAFT,
        })
        self.assertTrue(form.is_valid())
        self.assertNotIn('<script>', form.cleaned_data['content'])
        self.assertIn('<strong>with emphasis</strong>', form.cleaned_data['content'])

    def test_job_opening_creation(self):
        department = Department.objects.create(name="Forecasting", code="FORECAST")
        job = JobOpening.objects.create(
            title="Senior Meteorologist",
            department=department,
            description="Responsible for weather predictions.",
            status=JobOpening.Status.OPEN,
            posted_by=self.editor
        )
        self.assertTrue(job.slug.startswith("senior-meteorologist-"))
        self.assertEqual(job.status, JobOpening.Status.OPEN)
        self.assertEqual(job.department, department)

    def test_job_opening_rich_text_is_sanitized(self):
        form = JobOpeningForm(data={
            'title': 'Formatted Vacancy',
            'department': '',
            'location': 'Dili, Timor-Leste',
            'employment_type': JobOpening.EmploymentType.FULL_TIME,
            'description': (
                '<h2>Core duties</h2><div><strong>Monitor</strong> weather systems.</div>'
                '<script>alert(1)</script>'
            ),
            'requirements': '<ul><li>Relevant degree</li><li>Field experience</li></ul>',
            'how_to_apply': (
                '<p><a href="javascript:alert(1)">Unsafe</a> '
                '<a href="mailto:jobs@dnmg.gov.tl">Email DNMG</a></p>'
            ),
            'application_deadline': '',
            'status': JobOpening.Status.DRAFT,
        })

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('<h2>Core duties</h2>', form.cleaned_data['description'])
        self.assertIn('<p><strong>Monitor</strong> weather systems.</p>', form.cleaned_data['description'])
        self.assertIn('<strong>Monitor</strong>', form.cleaned_data['description'])
        self.assertIn('<ul><li>Relevant degree</li>', form.cleaned_data['requirements'])
        self.assertNotIn('<script>', form.cleaned_data['description'])
        self.assertNotIn('javascript:', form.cleaned_data['how_to_apply'])
        self.assertIn('href="mailto:jobs@dnmg.gov.tl"', form.cleaned_data['how_to_apply'])


class CMSViewsTestCase(TestCase):
    def setUp(self):
        self.media_directory = TemporaryDirectory()
        self.enterContext(override_settings(MEDIA_ROOT=self.media_directory.name))
        self.addCleanup(self.media_directory.cleanup)
        self.editor = User.objects.create_user(
            username="editor_staff",
            password="password123",
            role=User.Role.EDITOR
        )
        self.public_user = User.objects.create_user(
            username="public_visitor",
            password="password123",
            role=User.Role.PUBLIC
        )
        self.category = Category.objects.create(name="Climate")
        self.department = Department.objects.create(name="Geophysics", code="GEO")
        self.article = NewsArticle.objects.create(
            title="El Nino Preparedness Forum",
            category=self.category,
            excerpt="Forum held in Dili.",
            content="Content details...",
            status=NewsArticle.Status.PUBLISHED,
            author=self.editor,
            published_at=now()
        )
        self.job = JobOpening.objects.create(
            title="Geophysicist Specialist",
            department=self.department,
            description="Seismic monitoring duty.",
            status=JobOpening.Status.OPEN,
            posted_by=self.editor
        )
        self.bulletin = OfficialBulletin.objects.create(
            title="Marine Bulletin August 2026",
            bulletin_type=OfficialBulletin.BulletinType.MARINE,
            summary="Marine conditions and warnings.",
            publication_date=now().date(),
            uploaded_by=self.editor,
        )

    def test_public_news_list_view(self):
        response = self.client.get(reverse('cms:public_news_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El Nino Preparedness Forum")

    def test_public_news_detail_view(self):
        response = self.client.get(reverse('cms:public_news_detail', kwargs={'slug': self.article.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Content details...")

    def test_public_bulletin_list_and_detail_views(self):
        list_response = self.client.get(reverse('cms:public_bulletin_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Read More")
        self.assertContains(list_response, 'bulletin-card')
        self.assertContains(list_response, 'bulletin-card__meta')
        detail_response = self.client.get(reverse('cms:public_bulletin_detail', kwargs={'slug': self.bulletin.slug}))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Marine conditions and warnings.")
        self.assertContains(detail_response, 'public-bulletin-detail__metadata')

    def test_admin_news_list_editor_access(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('cms:admin_news_list'))
        self.assertEqual(response.status_code, 200)

    def test_news_editor_uses_one_inline_content_workflow(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('cms:news_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'inline_article_image_picker')
        self.assertContains(response, 'inline_article_attachment_picker')
        self.assertNotContains(response, 'images-TOTAL_FORMS')
        self.assertNotContains(response, 'attachments-TOTAL_FORMS')

    def test_news_editor_saves_inline_captioned_image_and_document(self):
        self.client.force_login(self.editor)
        image_data = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9e\x81\x83\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        response = self.client.post(reverse('cms:news_create'), {
            'title': 'Article With Inline Image',
            'category': '',
            'excerpt': 'Summary',
            'content': '<p>Opening paragraph.</p><figure data-upload-key="inline_test"><img src="data:image/png;base64,preview"><figcaption>Station at sunrise</figcaption></figure><p>More context.</p><figure data-attachment-upload-key="attachment_test"><figcaption>Attached file: Station report</figcaption></figure><p>Closing paragraph.</p>',
            'status': NewsArticle.Status.DRAFT,
            'published_at': '',
            'inline_image_keys': 'inline_test',
            'inline_image_caption_inline_test': 'Station at sunrise',
            'inline_image_inline_test': SimpleUploadedFile('sunrise.png', image_data, content_type='image/png'),
            'inline_attachment_keys': 'attachment_test',
            'inline_attachment_title_attachment_test': 'Station report',
            'inline_attachment_attachment_test': SimpleUploadedFile('station-report.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
        })
        self.assertRedirects(response, reverse('cms:admin_news_list'))
        article = NewsArticle.objects.get(title='Article With Inline Image')
        inline_image = NewsArticleInlineImage.objects.get(article=article)
        self.assertEqual(inline_image.caption, 'Station at sunrise')
        self.assertIn(inline_image.image.url, article.content)
        self.assertIn('<figcaption>Station at sunrise</figcaption>', article.content)
        inline_attachment = NewsArticleInlineAttachment.objects.get(article=article)
        self.assertEqual(inline_attachment.title, 'Station report')
        self.assertIn(inline_attachment.file.url, article.content)
        self.assertIn('Station report</a>', article.content)

    def test_news_editor_rejects_non_document_inline_attachment(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse('cms:news_create'), {
            'title': 'Invalid Inline Attachment',
            'category': '',
            'excerpt': 'Summary',
            'content': '<p>Article body.</p><figure data-attachment-upload-key="invalid_file"><figcaption>Attached file</figcaption></figure>',
            'status': NewsArticle.Status.DRAFT,
            'published_at': '',
            'inline_attachment_keys': 'invalid_file',
            'inline_attachment_title_invalid_file': 'Not a document',
            'inline_attachment_invalid_file': SimpleUploadedFile('image.png', b'image data', content_type='image/png'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Supporting files must be documents')
        self.assertFalse(NewsArticle.objects.filter(title='Invalid Inline Attachment').exists())

    def test_admin_news_list_public_user_blocked(self):
        self.client.force_login(self.public_user)
        response = self.client.get(reverse('cms:admin_news_list'))
        self.assertEqual(response.status_code, 403)

    def test_public_career_list_view(self):
        response = self.client.get(reverse('cms:public_career_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Geophysicist Specialist")

    def test_public_career_detail_view(self):
        response = self.client.get(reverse('cms:public_career_detail', kwargs={'slug': self.job.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seismic monitoring duty.")

    def test_public_career_detail_renders_safe_structured_content(self):
        self.job.description = (
            '<h2>Responsibilities</h2><ul><li>Monitor seismic activity</li></ul>'
            '<script>alert(1)</script>'
        )
        self.job.requirements = '<p><strong>Required:</strong> geophysics degree.</p>'
        self.job.save(update_fields=['description', 'requirements'])

        response = self.client.get(
            reverse('cms:public_career_detail', kwargs={'slug': self.job.slug})
        )

        self.assertContains(response, '<h2>Responsibilities</h2>')
        self.assertContains(response, '<ul><li>Monitor seismic activity</li></ul>')
        self.assertContains(response, '<strong>Required:</strong>')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_public_news_detail_sanitizes_legacy_article_content(self):
        self.article.content = (
            '<p>Important update.</p><script>alert(1)</script>'
            '<a href="//untrusted.example">Unsafe link</a>'
        )
        self.article.save(update_fields=['content', 'updated_at'])

        response = self.client.get(
            reverse('cms:public_news_detail', kwargs={'slug': self.article.slug})
        )

        self.assertContains(response, '<p>Important update.</p>')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'href="//untrusted.example"')

    def test_admin_career_list_editor_access(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('cms:admin_career_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Geophysicist Specialist")

    def test_career_editor_includes_document_upload_formset(self):
        self.client.force_login(self.editor)
        response = self.client.get(reverse('cms:career_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'attachments-TOTAL_FORMS')

    def test_career_editor_includes_rich_text_tools_for_each_content_section(self):
        self.client.force_login(self.editor)

        response = self.client.get(reverse('cms:career_create'))

        self.assertContains(response, 'id="job_description_editor"')
        self.assertContains(response, 'id="job_requirements_editor"')
        self.assertContains(response, 'id="job_application_editor"')
        self.assertContains(response, 'data-editor-command="bold"', count=3)
        self.assertContains(response, 'data-editor-command="italic"', count=3)
        self.assertContains(response, 'data-editor-command="insertUnorderedList"', count=3)
        self.assertContains(response, 'data-editor-command="insertOrderedList"', count=3)
        self.assertContains(response, 'data-editor-value="h2"', count=3)
