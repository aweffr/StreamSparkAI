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
from django import forms
from django.contrib.admin.helpers import ActionForm

from .models import AudioMedia, SummarySnapshot
from .utils.audio_processor import process_audio_file
from .utils.transcribe_audio import transcribe_audio
from .utils.llm_client import SUPPORTED_MODELS

logger = logging.getLogger(__name__)


# 创建一个表单，用于在执行操作时选择LLM模型
class SummaryActionForm(ActionForm):
    llm_model = forms.ChoiceField(
        choices=[('', '-- 使用默认模型 --')],
        required=False,
        label=_("LLM Model")
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 动态加载模型选择字段
        all_models = []
        
        # 添加OpenAI模型
        openai_models = [(model, f"{model} (OpenAI)") for model in SUPPORTED_MODELS['openai']]
        all_models.extend(openai_models)
        
        # 添加阿里巴巴模型
        alibaba_models = [(model, f"{model} (Alibaba)") for model in SUPPORTED_MODELS['alibaba']]
        all_models.extend(alibaba_models)
        
        # 添加每个模型组
        self.fields['llm_model'].choices = [
            ('', '-- 使用默认模型 --'),
            (_('Available Models'), all_models),
        ]
    
    @staticmethod
    def get_provider_for_model(model_name):
        """根据模型名称确定提供商"""
        if not model_name:
            return getattr(settings, 'DEFAULT_LLM_PROVIDER', 'openai')
            
        if model_name in SUPPORTED_MODELS['openai']:
            return 'openai'
        elif model_name in SUPPORTED_MODELS['alibaba']:
            return 'alibaba'
        else:
            # 默认回退到配置中的默认提供商
            return getattr(settings, 'DEFAULT_LLM_PROVIDER', 'openai')


@admin.register(AudioMedia)
class AudioMediaAdmin(admin.ModelAdmin):
    list_display = ('title', 'upload_date', 'processing_status', 'transcription_status', 
                   'has_original_file', 'has_processed_file', 'has_summary')
    list_filter = ('processing_status', 'transcription_status', 'upload_date', 'summary_type')
    search_fields = ('title', 'description')
    readonly_fields = ('upload_date', 'processing_date', 'transcription_start_date', 
                      'transcription_end_date', 'processing_status', 'transcription_status', 
                      'raw_transcription_admin_display', 'formatted_transcription', 
                      'summary', 'summary_date', 'selected_model')
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
        (_('Summary Information'), {
            'fields': ('summary_type', 'summary', 'summary_date', 'selected_model')
        }),
    )
    actions = ['convert_to_aac', 'transcribe_audio', 'convert_and_transcribe', 
              'generate_general_summary', 'generate_detailed_summary', 'generate_key_points', 'generate_meeting_minutes']
    
    # 添加操作表单，用于在执行操作时指定LLM模型
    action_form = SummaryActionForm
    
    def has_original_file(self, obj):
        return bool(obj.original_file)
    has_original_file.boolean = True
    has_original_file.short_description = _('Original File')

    def has_processed_file(self, obj):
        return bool(obj.processed_file)
    has_processed_file.boolean = True
    has_processed_file.short_description = _('Processed File')

    def has_summary(self, obj):
        return bool(obj.summary)
    has_summary.boolean = True
    has_summary.short_description = _('Has Summary')

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

    def generate_general_summary(self, request, queryset):
        """Generate general summary for selected audio files"""
        self._generate_summary(request, queryset, 'GENERAL')
    generate_general_summary.short_description = _("Generate general summary")
    
    def generate_detailed_summary(self, request, queryset):
        """Generate detailed summary for selected audio files"""
        self._generate_summary(request, queryset, 'GENERAL_DETAIL')
    generate_detailed_summary.short_description = _("Generate detailed summary")
    
    def generate_key_points(self, request, queryset):
        """Extract key points from selected audio files"""
        self._generate_summary(request, queryset, 'KEY_POINTS')
    generate_key_points.short_description = _("Extract key points")
    
    def generate_meeting_minutes(self, request, queryset):
        """Generate meeting minutes for selected audio files"""
        self._generate_summary(request, queryset, 'MEETING_MINUTES')
    generate_meeting_minutes.short_description = _("Generate meeting minutes")
    
    def _generate_summary(self, request, queryset, summary_type):
        """Generic summary generation method"""
        success_count = 0
        error_count = 0
        
        # 从请求中获取LLM模型，根据模型自动确定提供商
        llm_model = request.POST.get('llm_model') or None
        llm_provider = SummaryActionForm.get_provider_for_model(llm_model)
        
        logger.info(f"批量生成{summary_type}类型总结, 提供商: {llm_provider}, 模型: {llm_model or '默认'}, 文件数: {queryset.count()}")
        
        for audio in queryset:
            if not audio.formatted_transcription:
                logger.warning(f"ID: {audio.id}, 标题: {audio.title} - 无可用转录文本, 跳过总结生成")
                self.message_user(request, 
                                f"{audio.title}: No transcription available", 
                                level=messages.WARNING)
                error_count += 1
                continue
                
            logger.info(f"ID: {audio.id}, 标题: {audio.title} - 开始生成总结")
            success, error = audio.generate_summary(
                summary_type_str=summary_type,
                llm_provider=llm_provider,
                model=llm_model
            )
            
            if success:
                success_count += 1
                self.message_user(request, 
                                f"{audio.title}: Summary generated successfully using model {audio.selected_model}", 
                                level=messages.SUCCESS)
            else:
                error_count += 1
                # Note: Error message handling simplified since error_message field no longer exists
                logger.error(f"ID: {audio.id}, 标题: {audio.title} - 总结生成失败: {error}")
                self.message_user(request, 
                                f"{audio.title}: {error}", 
                                level=messages.ERROR)
        
        if success_count > 0:
            self.message_user(request, 
                             f"Successfully generated summaries for {success_count} file(s)", 
                             level=messages.SUCCESS)
        
        if error_count > 0:
            self.message_user(request, 
                             f"Failed to generate summaries for {error_count} file(s)", 
                             level=messages.WARNING)


@admin.register(SummarySnapshot)
class SummarySnapshotAdmin(admin.ModelAdmin):
    """管理界面: 总结快照"""
    list_display = ('__str__', 'audio_media', 'summary_type', 'llm_provider', 'llm_model', 'created_at')
    list_filter = ('summary_type', 'llm_provider', 'llm_model', 'created_at')
    readonly_fields = ('id', 'audio_media', 'summary_type', 'llm_provider', 
                      'llm_model', 'summary', 'raw_response', 'created_at')
    search_fields = ('audio_media__title', 'summary')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('id', 'audio_media', 'created_at')
        }),
        (_('Summary Settings'), {
            'fields': ('summary_type', 'llm_provider', 'llm_model')
        }),
        (_('Summary Content'), {
            'fields': ('summary',)
        }),
        (_('Technical Details'), {
            'fields': ('raw_response',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """禁止手动添加总结快照，应该通过生成总结来创建"""
        return False