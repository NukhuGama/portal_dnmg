from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.urls import path, include
from .views import healthz
from core.views import MediaFileView, MediaUnavailableView

urlpatterns = [
    path('healthz/', healthz, name='healthz'),
    path('media-unavailable/', MediaUnavailableView.as_view(), name='media_unavailable'),
    # Endpoint to process language switching POST requests
    path('i18n/', include('django.conf.urls.i18n')),
]

# Multilingual routes with /en/, /tet/, /pt/ prefixes
urlpatterns += i18n_patterns(
    path('', include('core.urls')),
    path('auth/', include('users.urls')),
    path('weather/', include('weather.urls')),
    path('seismic/', include('seismic.urls')),
    path('cms/', include('cms.urls')),
    path('hr/', include('hr.urls')),
    prefix_default_language=True
)

if settings.DEBUG:
    # Uploaded files receive a friendly empty-state response when the database
    # record exists but the file itself has been removed from storage.
    urlpatterns += [path('media/<path:path>', MediaFileView.as_view(), name='media_file')]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
