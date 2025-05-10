"""
URL configuration for StreamSparkAI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import set_language

admin.site.site_header = "StreamSparkAI Admin"
admin.site.site_title = "StreamSparkAI Admin Portal"

# Non-translated URLs
urlpatterns = [
    # Add language selection view
    path('i18n/setlang/', set_language, name='set_language'),
    # Add other non-i18n URLs here
    path('', include('core.urls', namespace='core')),  # Adding core URLs to non-translated paths
]

# Translated URLs
urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    # Add other URLs that need translation
    prefix_default_language=False,  # Don't add language code for default language
)

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
