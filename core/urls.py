from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('m/<uuid:pk>/', views.audio_media_detail, name='audio_media_detail'),
    path('summary/<uuid:pk>/', views.summary_snapshot_detail, name='summary_snapshot_detail'),
    path('', views.audio_media_list, name='audio_media_list'),
]
