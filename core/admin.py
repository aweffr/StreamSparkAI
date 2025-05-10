import os
import logging
from datetime import datetime
from urllib.parse import urljoin
import concurrent.futures

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
            
    @staticmethod
    def get_default_model_for_provider(provider):
        """获取指定提供商的默认模型"""
        if provider.lower() == 'openai':
            return settings.DEFAULT_OPENAI_MODEL
        elif provider.lower() == 'alibaba':
            return settings.ALIBABA_LLM_MODEL
        return None


@admin.register(AudioMedia)
class AudioMediaAdmin(admin.ModelAdmin):
    # Class-level ThreadPoolExecutor for background tasks
    _executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="audio-process")
    
    list_display = ('title', 'upload_date', 'processing_status', 'transcription_status', 
                   'has_original_file', 'has_processed_file', 'has_summary', 'is_private')
    list_filter = ('processing_status', 'transcription_status', 'upload_date', 'summary_type', 'is_private')
    search_fields = ('title', 'description', 'source', 'subtitle')
    readonly_fields = ('upload_date', 'processing_date', 'transcription_start_date', 
                      'transcription_end_date', 'processing_status', 'transcription_status', 
                      'raw_transcription_admin_display', 'formatted_transcription', 
                      'summary', 'summary_date', 'selected_model', 'subtitle')
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'description', 'source', 'subtitle', 'is_private', 'upload_date')
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
              'generate_general_summary', 'generate_detailed_summary', 'generate_key_points', 
              'generate_meeting_minutes', 'generate_subtitle', 'process_audio_with_threadpool']
    
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
    
    def generate_subtitle(self, request, queryset):
        """Generate short subtitle for selected audio files"""
        success_count = 0
        error_count = 0
        
        # 从请求中获取LLM模型，根据模型自动确定提供商
        llm_model = request.POST.get('llm_model') or None
        llm_provider = SummaryActionForm.get_provider_for_model(llm_model)
        
        # 如果没有指定模型，则使用提供商的默认模型
        if not llm_model:
            llm_model = SummaryActionForm.get_default_model_for_provider(llm_provider)
            logger.info(f"未指定模型，使用{llm_provider}的默认模型: {llm_model}")
        
        logger.info(f"批量生成副标题, 提供商: {llm_provider}, 模型: {llm_model}, 文件数: {queryset.count()}")
        
        for audio in queryset:
            if not audio.formatted_transcription:
                logger.warning(f"ID: {audio.id}, 标题: {audio.title} - 无可用转录文本, 跳过副标题生成")
                self.message_user(request, 
                                f"{audio.title}: No transcription available", 
                                level=messages.WARNING)
                error_count += 1
                continue
                
            logger.info(f"ID: {audio.id}, 标题: {audio.title} - 开始生成副标题")
            success, error = audio.generate_subtitle(
                llm_provider=llm_provider,
                model=llm_model
            )
            
            if success:
                success_count += 1
                self.message_user(request, 
                                f"{audio.title}: Subtitle generated successfully: '{audio.subtitle}'", 
                                level=messages.SUCCESS)
            else:
                error_count += 1
                logger.error(f"ID: {audio.id}, 标题: {audio.title} - 副标题生成失败: {error}")
                self.message_user(request, 
                                f"{audio.title}: {error}", 
                                level=messages.ERROR)
        
        if success_count > 0:
            self.message_user(request, 
                             f"Successfully generated subtitles for {success_count} file(s)", 
                             level=messages.SUCCESS)
        
        if error_count > 0:
            self.message_user(request, 
                             f"Failed to generate subtitles for {error_count} file(s)", 
                             level=messages.WARNING)
                             
    generate_subtitle.short_description = _("Generate short subtitle")
    
    def process_audio_with_threadpool(self, request, queryset):
        """
        Process selected media files in a thread pool:
        1. Convert to AAC
        2. Transcribe
        3. Generate short title
        4. Generate detailed summary
        """
        # Get the selected model from the form
        llm_model = request.POST.get('llm_model') or None
        llm_provider = SummaryActionForm.get_provider_for_model(llm_model)
        
        # 如果没有指定模型，则使用提供商的默认模型
        if not llm_model:
            llm_model = SummaryActionForm.get_default_model_for_provider(llm_provider)
            logger.info(f"未指定模型，使用{llm_provider}的默认模型: {llm_model}")
            
        audio_count = queryset.count()
        
        def process_single_file(audio):
            """Process a single audio file with all steps"""
            logger.info(f"Starting background processing for ID: {audio.id}, 标题: {audio.title}")
            
            try:
                # Step 1: Convert to AAC
                success_convert, error_convert = audio.convert_to_aac()
                if not success_convert:
                    logger.error(f"ID: {audio.id}, 标题: {audio.title} - 转换AAC失败: {error_convert}")
                    return f"Failed to convert {audio.title} to AAC: {error_convert}"
                
                logger.info(f"ID: {audio.id}, 标题: {audio.title} - AAC转换成功")
                
                # Step 2: Transcribe audio
                success_transcribe, error_transcribe = audio.transcribe_audio()
                if not success_transcribe:
                    logger.error(f"ID: {audio.id}, 标题: {audio.title} - 转录失败: {error_transcribe}")
                    return f"Failed to transcribe {audio.title}: {error_transcribe}"
                    
                logger.info(f"ID: {audio.id}, 标题: {audio.title} - 转录成功")
                
                # Step 3: Generate subtitle
                if audio.formatted_transcription:
                    success_title, error_title = audio.generate_subtitle(
                        llm_provider=llm_provider,
                        model=llm_model
                    )
                    
                    if not success_title:
                        logger.error(f"ID: {audio.id}, 标题: {audio.title} - 副标题生成失败: {error_title}")
                    else:
                        logger.info(f"ID: {audio.id}, 标题: {audio.title} - 副标题生成成功: '{audio.subtitle}'")
                
                # Step 4: Generate detailed summary
                if audio.formatted_transcription:
                    success_summary, error_summary = audio.generate_summary(
                        summary_type_str='GENERAL_DETAIL',
                        llm_provider=llm_provider,
                        model=llm_model
                    )
                    
                    if not success_summary:
                        logger.error(f"ID: {audio.id}, 标题: {audio.title} - 详细总结生成失败: {error_summary}")
                    else:
                        logger.info(f"ID: {audio.id}, 标题: {audio.title} - 详细总结生成成功")
                
                logger.info(f"Background processing completed for ID: {audio.id}, 标题: {audio.title}")
                return f"Successfully processed {audio.title}"
            except Exception as e:
                logger.exception(f"ID: {audio.id}, 标题: {audio.title} - 处理过程中发生异常: {str(e)}")
                return f"Error processing {audio.title}: {str(e)}"
        
        def run_batch_processing():
            """Process all audio files in the batch"""
            logger.info(f"开始后台处理任务: {audio_count} 个文件, 模型: {llm_model or '默认'}, 提供商: {llm_provider}")
            try:
                # Copy the queryset IDs to avoid potential query issues
                audio_ids = list(queryset.values_list('id', flat=True))
                
                # Process each audio file
                futures = {}
                for audio_id in audio_ids:
                    try:
                        # Re-fetch each audio item to avoid potential stale data issues
                        audio = AudioMedia.objects.get(id=audio_id)
                        futures[self._executor.submit(process_single_file, audio)] = audio.title
                    except AudioMedia.DoesNotExist:
                        logger.error(f"无法找到ID为 {audio_id} 的音频记录")
                
                # Wait for all tasks to complete
                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    audio_title = futures[future]
                    try:
                        result = future.result()
                        completed += 1
                        logger.info(f"完成任务 ({completed}/{len(futures)}): {audio_title} - {result}")
                    except Exception as e:
                        logger.exception(f"处理任务失败: {audio_title} - {str(e)}")
                
                logger.info(f"所有后台任务处理完成: {completed}/{len(futures)} 个任务成功")
            except Exception as e:
                logger.exception(f"后台处理任务发生异常: {str(e)}")
        
        # Submit the batch processing to the executor
        self._executor.submit(run_batch_processing)
        
        # Return immediately with a message
        self.message_user(
            request,
            _("Background processing started for %(count)d file(s). You can safely leave this page.") % {'count': audio_count},
            level=messages.SUCCESS
        )
    
    process_audio_with_threadpool.short_description = _("Process in background (convert, transcribe, summarize)")
    
    def _generate_summary(self, request, queryset, summary_type):
        """Generic summary generation method"""
        success_count = 0
        error_count = 0
        
        # 从请求中获取LLM模型，根据模型自动确定提供商
        llm_model = request.POST.get('llm_model') or None
        llm_provider = SummaryActionForm.get_provider_for_model(llm_model)
        
        # 如果没有指定模型，则使用提供商的默认模型
        if not llm_model:
            llm_model = SummaryActionForm.get_default_model_for_provider(llm_provider)
            logger.info(f"未指定模型，使用{llm_provider}的默认模型: {llm_model}")
        
        logger.info(f"批量生成{summary_type}类型总结, 提供商: {llm_provider}, 模型: {llm_model}, 文件数: {queryset.count()}")
        
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