from django.conf import settings
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
import uuid
import os
from pathlib import Path
import logging
from django.utils import timezone
from django.core.files.base import ContentFile
from .utils.llm_client import LLMClient, SummaryType

logger = logging.getLogger(__name__)

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('Title'), max_length=191)
    description = models.TextField(_('Description'), blank=True)
    
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
    
    # Summary fields
    summary = models.TextField(_('Summary'), blank=True)
    summary_type = models.CharField(_('Summary Type'), max_length=20, default='GENERAL')
    summary_date = models.DateTimeField(_('Summary Date'), blank=True, null=True)

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

    def generate_summary(self, summary_type_str='GENERAL', llm_provider='openai'):
        """
        使用LLM为转录文本生成总结
        
        Args:
            summary_type_str (str): 总结类型 ('GENERAL', 'KEY_POINTS', 等)
            llm_provider (str): LLM提供商 ('openai' 或 'alibaba')
            
        Returns:
            tuple: (success, error_message)
        """
        # 检查是否有转录文本可用
        if not self.formatted_transcription:
            return False, "没有可用的转录文本来生成总结"
        
        try:
            # 获取总结类型枚举
            summary_type = getattr(SummaryType, summary_type_str)
            
            # 构建上下文信息
            context_info = f"标题: {self.title}"
            if self.description:
                context_info += f"\n描述: {self.description}"
            
            # 获取LLM客户端
            client = LLMClient.get_client(provider=llm_provider)
            
            # 调用LLM API生成总结，传递上下文信息
            result = client.summarize(self.formatted_transcription, summary_type, context_info=context_info)
            
            if 'summary' in result and result['summary']:
                # 更新模型字段
                self.summary = result['summary']
                self.summary_type = summary_type_str
                self.summary_date = timezone.now()
                self.save()
                
                logger.info(f"成功为 {self.title} 生成了内容总结")
                return True, None
            else:
                return False, "LLM未返回有效的总结内容"
                
        except Exception as e:
            logger.exception(f"为 {self.title} 生成总结时出错: {str(e)}")
            return False, str(e)

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