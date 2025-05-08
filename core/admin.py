import os
import logging
from datetime import datetime
from urllib.parse import urljoin

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .models import AudioMedia
from .utils.audio_processor import process_audio_file
from .utils.transcribe_audio import transcribe_audio

logger = logging.getLogger(__name__)


@admin.register(AudioMedia)
class AudioMediaAdmin(admin.ModelAdmin):
    list_display = ('title', 'upload_date', 'processing_status', 'transcription_status', 'has_original_file', 'has_processed_file')
    list_filter = ('processing_status', 'transcription_status', 'upload_date')
    search_fields = ('title', 'description')
    readonly_fields = ('upload_date', 'processing_date', 'transcription_start_date', 'transcription_end_date',
                      'processing_status', 'transcription_status', 'raw_transcription_admin_display', 'formatted_transcription')
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'description', 'upload_date')
        }),
        (_('Files'), {
            'fields': ('original_file', 'processed_file')
        }),
        (_('Processing Information'), {
            'fields': ('processing_status', 'processing_date')
        }),
        (_('Transcription Information'), {
            'fields': ('transcription_status', 'transcription_start_date', 'transcription_end_date', 
                      'formatted_transcription', 'raw_transcription_admin_display')
        }),
    )
    actions = ['convert_to_aac', 'transcribe_audio', 'convert_and_transcribe']

    def has_original_file(self, obj):
        return bool(obj.original_file)
    has_original_file.boolean = True
    has_original_file.short_description = _('Original File')

    def has_processed_file(self, obj):
        return bool(obj.processed_file)
    has_processed_file.boolean = True
    has_processed_file.short_description = _('Processed File')

    def convert_to_aac(self, request, queryset):
        """
        Convert the selected media files to AAC format
        """
        success_count = 0
        error_count = 0
        
        for media in queryset:
            success, error_message = media.convert_to_aac()
            
            if success:
                success_count += 1
            else:
                self.message_user(request, 
                                f"Error processing {media.title}: {error_message}", 
                                level=messages.ERROR)
                error_count += 1
        
        if success_count > 0:
            self.message_user(request, 
                            f"Successfully converted {success_count} file(s) to AAC format", 
                            level=messages.SUCCESS)
        
        if error_count > 0:
            self.message_user(request, 
                            f"Failed to convert {error_count} file(s)", 
                            level=messages.WARNING)
    
    convert_to_aac.short_description = _("Convert selected files to AAC format")
    
    def transcribe_audio(self, request, queryset):
        """
        Transcribe the selected processed audio files
        """
        success_count = 0
        error_count = 0
        
        for media in queryset:
            success, error_message = media.transcribe_audio()
            
            if success:
                success_count += 1
            else:
                self.message_user(request, 
                                f"{media.title}: {error_message}", 
                                level=messages.ERROR if "No audio file" in error_message else messages.WARNING)
                error_count += 1
        
        if success_count > 0:
            self.message_user(request, 
                            f"Successfully transcribed {success_count} file(s)", 
                            level=messages.SUCCESS)
        
        if error_count > 0:
            self.message_user(request, 
                            f"Failed to transcribe {error_count} file(s)", 
                            level=messages.WARNING)
    
    transcribe_audio.short_description = _("Transcribe selected files")
    
    def convert_and_transcribe(self, request, queryset):
        """
        Convert selected media files to AAC and then transcribe them
        """
        success_count = 0
        error_count = 0
        
        for media in queryset:
            success, error_message = media.convert_and_transcribe()
            
            if success:
                success_count += 1
            else:
                self.message_user(request, 
                                f"Error processing {media.title}: {error_message}", 
                                level=messages.ERROR)
                error_count += 1
        
        if success_count > 0:
            self.message_user(request, 
                            f"Successfully converted and transcribed {success_count} file(s)", 
                            level=messages.SUCCESS)
        
        if error_count > 0:
            self.message_user(request, 
                            f"Failed to process {error_count} file(s)", 
                            level=messages.WARNING)
    
    convert_and_transcribe.short_description = _("Convert and transcribe selected files")