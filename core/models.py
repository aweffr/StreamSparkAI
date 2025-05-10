from django.conf import settings
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
import uuid
from uuid_extensions import uuid7  # Correct import for uuid7
import os
from pathlib import Path
import logging
from django.utils import timezone
from django.core.files.base import ContentFile
from .utils.llm_client import LLMClient, SummaryType, is_valid_model, SUPPORTED_MODELS

logger = logging.getLogger(__name__)

def get_uuid():
    """
    Generate a UUID for the model instance.
    """
    return uuid7()

def get_world_background():
    """
    读取世界背景信息文件
    
    Returns:
        str: 背景信息内容，如果文件不存在则返回空字符串
    """
    try:
        background_path = Path(__file__).parent / "utils" / "assets" / "world-background.txt"
        if background_path.exists():
            with open(background_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        else:
            logger.warning(f"世界背景信息文件不存在: {background_path}")
        return ""
    except Exception as e:
        logger.exception(f"读取世界背景信息文件时出错: {e}")
        return ""

def build_subtitle_prompt(title, description, formatted_transcription, max_length=6000):
    """
    构建用于生成副标题的提示词
    
    Args:
        title (str): 音频标题
        description (str): 音频描述
        formatted_transcription (str): 转录文本
        max_length (int): 传递给LLM的最大转录文本长度
        
    Returns:
        str: 格式化的提示词
    """
    return f"""请为以下音频转录文本生成一个简短副标题，要求：
1. 长度在10-120个字符之间
2. 简明扼要地概括内容核心
3. 有吸引力，能引起读者兴趣
4. 格式流畅，不使用标题格式（冒号、破折号等）
5. 只输出标题文本，不要有任何前缀、引号或解释

音频标题: {title}
{description if description else ''}

转录文本:
{formatted_transcription[:max_length]}"""

class AudioMedia(models.Model):
    """
    Model for storing and processing audio/video files.
    """
    STATUS_CHOICES = (
        ('not_started', _('Not Started')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
    )

    id = models.UUIDField(primary_key=True, default=get_uuid, editable=False)  # Using uuid7 function directly
    title = models.CharField(_('Title'), max_length=191)
    description = models.TextField(_('Description'), blank=True)
    
    # New fields
    source = models.CharField(_('Source'), max_length=191, blank=True, help_text=_("Where the audio came from"))
    subtitle = models.CharField(_('Subtitle'), max_length=191, blank=True, help_text=_("A short subtitle summarizing the content (30-150 chars)"))
    is_private = models.BooleanField(_('Private'), default=False, help_text=_("If enabled, only authenticated users can view this media"))
    
    # Original file upload
    original_file = models.FileField(
        _('Original File'),
        upload_to='media/original/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['mp3', 'mp4', 'aac', 'wav', 'm4a', 'flac'])]
    )
    upload_date = models.DateTimeField(_('Upload Date'), auto_now_add=True)
    
    # Processed AAC file
    processed_file = models.FileField(
        _('Processed AAC File'), 
        upload_to='media/processed/%Y/%m/%d/',
        blank=True, 
        null=True
    )
    processing_date = models.DateTimeField(_('Processing Date'), blank=True, null=True)
    processing_status = models.CharField(
        _('Processing Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started'
    )
    
    # Transcription fields
    transcription_status = models.CharField(
        _('Transcription Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='not_started'
    )
    transcription_start_date = models.DateTimeField(_('Transcription Start Date'), blank=True, null=True)
    transcription_end_date = models.DateTimeField(_('Transcription End Date'), blank=True, null=True)
    raw_transcription = models.JSONField(_('Raw Transcription'), blank=True, null=True)
    formatted_transcription = models.TextField(_('Formatted Transcription'), blank=True)
    
    # Summary fields - keeping these for backward compatibility
    summary = models.TextField(_('Summary'), blank=True)
    summary_type = models.CharField(_('Summary Type'), max_length=20, default='GENERAL')
    summary_date = models.DateTimeField(_('Summary Date'), blank=True, null=True)
    
    # Model selection field for the latest summary generation
    selected_model = models.CharField(_('Selected LLM Model'), max_length=50, blank=True)

    class Meta:
        verbose_name = _('Audio Media')
        verbose_name_plural = _('Audio Media')
        ordering = ['-upload_date']

    def __str__(self):
        return self.title
    
    def get_original_file_name(self):
        """Get the file name of the original file without path"""
        return os.path.basename(self.original_file.name) if self.original_file else None
    
    def get_processed_file_name(self):
        """Get the file name of the processed file without path"""
        return os.path.basename(self.processed_file.name) if self.processed_file else None
    
    def get_original_file_extension(self):
        """Get the extension of the original file"""
        if self.original_file:
            return Path(self.original_file.name).suffix.lower()
        return None
    
    def convert_to_aac(self):
        """
        Convert the original file to AAC format
        
        Returns:
            tuple: (success, error_message)
        """
        from .utils.audio_processor import process_audio_file
        
        if not self.original_file:
            return False, "No original file to process"
            
        # Update processing status
        self.processing_status = 'in_progress'
        self.save(update_fields=['processing_status'])
        
        try:
            # Convert the file to AAC format
            original_file_url = self.original_file.url
            original_file_path = settings.TMP_DIR / self.get_original_file_name()
            if not original_file_path.exists():
                # Download the original file to a temporary location
                from django.core.files.storage import default_storage
                with default_storage.open(self.original_file.name, 'rb') as f:
                    with open(original_file_path, 'wb') as temp_file:
                        temp_file.write(f.read())
            processed_file_path = process_audio_file(original_file_path)
            
            if not processed_file_path:
                self.processing_status = 'failed'
                self.save(update_fields=['processing_status'])
                return False, "Failed to convert to AAC format"
            
            # Save the processed file to the model
            with open(processed_file_path, 'rb') as f:
                file_name = os.path.basename(processed_file_path)
                self.processed_file.save(file_name, ContentFile(f.read()), save=False)
            
            # Update processing information
            self.processing_status = 'completed'
            self.processing_date = timezone.now()
            self.save()
            
            return True, None
                
        except Exception as e:
            logger.exception(f"Error converting {self.title} to AAC: {str(e)}")
            self.processing_status = 'failed'
            self.save(update_fields=['processing_status'])
            return False, str(e)
    
    def transcribe_audio(self):
        """
        Transcribe the processed audio file
        
        Returns:
            tuple: (success, error_message)
        """
        from django.conf import settings
        from .utils.transcribe_audio import transcribe_audio as transcribe_audio_util
        
        # Check if we have a processed file to transcribe
        if not self.processed_file:
            # If no processed file but original exists, suggest conversion
            if self.original_file:
                return False, "Needs to be converted to AAC format first"
            else:
                return False, "No audio file to transcribe"
                
        # Update transcription status
        self.transcription_status = 'in_progress'
        self.transcription_start_date = timezone.now()
        self.save(update_fields=['transcription_status', 'transcription_start_date'])
        
        try:
            # Get the URL to the processed file
            file_url = self.processed_file.url
            
            assert file_url.startswith(('http://', 'https://')), "File URL must start with http or https"
            
            logger.info(f"id: {self.id}, transcribing file: {file_url}")
            
            # Call the transcription utility
            transcription_result = transcribe_audio_util(file_url)
            
            # Update the model with the results
            self.raw_transcription = transcription_result.get('raw_json')
            self.formatted_transcription = transcription_result.get('formatted_text')
            self.transcription_status = 'completed'
            self.transcription_end_date = timezone.now()
            self.save()
            
            return True, None
            
        except Exception as e:
            logger.exception(f"Error transcribing {self.title}: {str(e)}")
            self.transcription_status = 'failed'
            self.save(update_fields=['transcription_status'])
            return False, str(e)
    
    def convert_and_transcribe(self):
        """
        Convert the file to AAC and then transcribe it
        
        Returns:
            tuple: (success, error_message)
        """
        # First convert to AAC
        success, error_message = self.convert_to_aac()
        if not success:
            return False, f"Conversion failed: {error_message}"
        
        # Then transcribe
        success, error_message = self.transcribe_audio()
        if not success:
            return False, f"Transcription failed: {error_message}"
        
        return True, None

    def generate_summary(self, summary_type_str='GENERAL', llm_provider=None, model=None):
        """
        使用LLM为转录文本生成总结
        
        Args:
            summary_type_str (str): 总结类型 ('GENERAL', 'KEY_POINTS', 等)
            llm_provider (str): LLM提供商 ('openai' 或 'alibaba')
            model (str): 模型名称，如果为None则使用默认模型
            
        Returns:
            tuple: (success, error_message)
        """
        # 检查是否有转录文本可用
        if not self.formatted_transcription:
            logger.warning(f"ID: {self.id}, 标题: {self.title} - 无可用转录文本, 无法生成总结")
            return False, "没有可用的转录文本来生成总结"
        
        # 如果未指定提供商，使用默认提供商
        if not llm_provider:
            llm_provider = getattr(settings, 'DEFAULT_LLM_PROVIDER', 'openai')
        
        logger.info(f"ID: {self.id}, 标题: {self.title} - 开始生成总结, 类型: {summary_type_str}, 提供商: {llm_provider}, 模型: {model or '默认'}")
        
        try:
            # 获取总结类型枚举
            summary_type = getattr(SummaryType, summary_type_str)
            
            # 构建上下文信息
            context_info = f"标题: {self.title}"
            if self.description:
                context_info += f"\n描述: {self.description}"
                
            # 添加世界背景信息
            world_background = get_world_background()
            if world_background:
                context_info += f"\n\n【背景知识参考 - 仅用于理解，不要与正文混淆】\n{world_background}\n\n【重要提示：上面的背景信息仅供你理解世界背景和事实，与待总结的正文无关，请不要在总结中引用或混淆这些背景信息。只总结传入的转录文本内容。】"
            
            # 获取LLM客户端
            client = LLMClient.get_client(provider=llm_provider)
            
            # 验证模型是否有效，如果指定了模型
            if model and not is_valid_model(llm_provider, model):
                logger.warning(f"指定的模型 {model} 对于提供商 {llm_provider} 无效，将使用默认模型")
                model = None
            
            # 调用LLM API生成总结，传递上下文信息和模型
            logger.info(f"ID: {self.id}, 标题: {self.title} - 调用LLM API, 提供商: {llm_provider}, 模型: {model or '默认'}")
            result = client.summarize(
                self.formatted_transcription, 
                summary_type, 
                context_info=context_info,
                model=model
            )
            
            if 'summary' in result and result['summary']:
                # 更新模型字段
                self.summary = result['summary']
                self.summary_type = summary_type_str
                self.summary_date = timezone.now()
                self.selected_model = result.get('model_used', '')
                self.save()
                
                # 创建总结快照
                snapshot = SummarySnapshot.objects.create(
                    audio_media=self,
                    summary_type=summary_type_str,
                    summary=result['summary'],
                    llm_provider=llm_provider,
                    llm_model=result.get('model_used', ''),
                    raw_response=result.get('raw_response')
                )
                
                logger.info(f"ID: {self.id}, 标题: {self.title} - 成功生成内容总结，使用模型: {result.get('model_used', '')}, 快照ID: {snapshot.id}")
                return True, None
            else:
                error_msg = "LLM未返回有效的总结内容"
                if 'raw_response' in result and result['raw_response']:
                    raw_response_str = str(result['raw_response'])
                    logger.error(f"ID: {self.id}, 标题: {self.title} - LLM响应无效, 原始响应: {raw_response_str[:500]}...")
                else:
                    logger.error(f"ID: {self.id}, 标题: {self.title} - LLM响应无效, 无原始响应")
                
                return False, error_msg
                
        except Exception as e:
            error_msg = f"为 {self.title} 生成总结时出错: {str(e)}"
            logger.exception(f"ID: {self.id}, 标题: {self.title} - 生成总结失败: {str(e)}")
            return False, error_msg

    def generate_subtitle(self, llm_provider=None, model=None):
        """
        使用LLM为转录文本生成简短副标题
        
        Args:
            llm_provider (str): LLM提供商 ('openai' 或 'alibaba')
            model (str): 模型名称，如果为None则使用默认模型
            
        Returns:
            tuple: (success, error_message)
        """
        # 检查是否有转录文本可用
        if not self.formatted_transcription:
            logger.warning(f"ID: {self.id}, 标题: {self.title} - 无可用转录文本, 无法生成副标题")
            return False, "没有可用的转录文本来生成副标题"
        
        # 如果未指定提供商，使用默认提供商
        if not llm_provider:
            llm_provider = getattr(settings, 'DEFAULT_LLM_PROVIDER', 'openai')
        
        logger.info(f"ID: {self.id}, 标题: {self.title} - 开始生成副标题, 提供商: {llm_provider}, 模型: {model or '默认'}")
        
        try:
            # 获取LLM客户端
            client = LLMClient.get_client(provider=llm_provider)
            
            # 验证模型是否有效，如果指定了模型
            if model and not is_valid_model(llm_provider, model):
                logger.warning(f"指定的模型 {model} 对于提供商 {llm_provider} 无效，将使用默认模型")
                model = None
            
            # 使用工具函数构建提示词
            prompt = build_subtitle_prompt(self.title, self.description, self.formatted_transcription)
            
            # 调用LLM API
            result = client.summarize(
                text=prompt,
                summary_type=SummaryType.GENERAL,
                model=model
            )
            
            if 'summary' in result and result['summary']:
                # 清理并限制副标题长度
                subtitle = result['summary'].strip()
                if len(subtitle) > 180:
                    subtitle = subtitle[:180] + '...'
                
                # 更新模型字段
                self.subtitle = subtitle
                self.save(update_fields=['subtitle', ])
                
                logger.info(f"ID: {self.id}, 标题: {self.title} - 成功生成副标题: '{subtitle}'")
                return True, None
            else:
                error_msg = "LLM未返回有效的副标题内容"
                logger.error(f"ID: {self.id}, 标题: {self.title} - {error_msg}")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"为 {self.title} 生成副标题时出错: {str(e)}"
            logger.exception(f"ID: {self.id}, 标题: {self.title} - 生成副标题失败: {str(e)}")
            return False, error_msg

    @property
    def raw_transcription_admin_display(self):
        """
        Display the raw transcription in the admin interface
        """
        if self.raw_transcription:
            str_display = str(self.raw_transcription)
            if len(str_display) > 1500:
                return str_display[:1500] + '......' + ' (truncated) total: ' + str(len(str_display)) + ' characters'
            else:
                return str_display
        return None

    def get_summary_type_display(self):
        """获取总结类型的显示名称"""
        try:
            summary_type = getattr(SummaryType, self.summary_type)
            return summary_type.get_display_name()
        except (AttributeError, ValueError):
            return self.summary_type


class SummarySnapshot(models.Model):
    """
    用于存储音频文件的总结快照，以便存档和比较不同的总结
    """
    id = models.UUIDField(primary_key=True, default=get_uuid, editable=False)  # Using uuid7 function directly
    audio_media = models.ForeignKey(AudioMedia, on_delete=models.CASCADE, related_name='summary_snapshots')
    
    summary_type = models.CharField(_('Summary Type'), max_length=20)
    summary = models.TextField(_('Summary Content'))
    
    # LLM 信息
    llm_provider = models.CharField(_('LLM Provider'), max_length=20)
    llm_model = models.CharField(_('LLM Model'), max_length=50)
    
    # 原始响应
    raw_response = models.JSONField(_('Raw LLM Response'), null=True, blank=True)
    
    # 时间戳
    created_at = models.DateTimeField(_('Created At'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Summary Snapshot')
        verbose_name_plural = _('Summary Snapshots')
        ordering = ['-created_at']        
    
    def __str__(self):
        return f"{self.summary_type} summary for {self.audio_media.title} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    def get_absolute_url(self):
        """返回查看该总结快照的URL"""
        return reverse('core:summary_snapshot_detail', args=[str(self.id)])

    def get_summary_type_display(self):
        """获取总结类型的显示名称"""
        try:
            summary_type = getattr(SummaryType, self.summary_type)
            return summary_type.get_display_name()
        except (AttributeError, ValueError):
            return self.summary_type