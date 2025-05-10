from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "StreamSparkAI Admin"
admin.site.site_title = "StreamSparkAI Admin Portal"

urlpatterns = [
    path('', include('core.urls', namespace='core')),  # Adding core URLs to non-translated paths
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
