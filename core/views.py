from django.shortcuts import render, get_object_or_404
from django.http import Http404, JsonResponse
import markdown
from .models import AudioMedia, SummarySnapshot
import math  # Add this import for math.ceil
import re
import jieba  # Add jieba for Chinese word segmentation
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger  # Add this import
import os
from django.utils import translation
from django.conf import settings
from django.views.decorators.cache import never_cache

def estimate_reading_time(text):
    """
    Estimate reading time based on word count.
    Handles both Chinese and non-Chinese text appropriately.
    
    Args:
        text (str): The text to estimate reading time for
        
    Returns:
        tuple: (reading_time_minutes, word_count)
    """
    if not text:
        return 0, 0
    
    # Check if text contains significant Chinese characters
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    chinese_char_count = len(chinese_pattern.findall(text))
    
    # If more than 10% of characters are Chinese, use Chinese segmentation
    if chinese_char_count > len(text) * 0.1:
        # Use jieba for Chinese word segmentation
        words = list(jieba.cut(text))
        word_count = len(words)
        # Chinese reading speed is typically slower in words per minute
        reading_speed = 200
    else:
        # For non-Chinese text, split by whitespace
        words = text.split()
        word_count = len(words)
        reading_speed = 240
    
    # Calculate reading time in minutes, round up to nearest minute
    reading_time = math.ceil(word_count / reading_speed)
    
    return reading_time, word_count

def audio_media_list(request):
    """显示所有已处理的音频媒体文件列表"""
    # 基础查询条件 - 已处理且已转录完成的文件
    base_query = AudioMedia.objects.filter(
        processing_status='completed',
        transcription_status='completed'
    )
    
    # 如果用户未登录，只显示公开媒体
    if not request.user.is_authenticated:
        all_media = base_query.filter(is_private=False).order_by('-upload_date')
    else:
        # 已登录用户可以查看所有媒体
        all_media = base_query.order_by('-upload_date')
    
    # Pagination - 10 items per page
    paginator = Paginator(all_media, 10)
    page = request.GET.get('page')
    
    try:
        paginated_media = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        paginated_media = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        paginated_media = paginator.page(paginator.num_pages)
    
    # Enhance media items with reading time info
    for media in paginated_media:
        reading_time, word_count = estimate_reading_time(media.summary)
        media.reading_time = reading_time
        media.word_count = word_count
    
    return render(request, 'core/audio_media_list.html', {
        'media_list': paginated_media,
    })

def audio_media_detail(request, pk):
    """显示单个音频媒体的详细信息，包括转录和最新总结"""
    media = get_object_or_404(AudioMedia, pk=pk)
    
    # 检查权限 - 如果是私有媒体且用户未登录，则禁止访问
    if media.is_private and not request.user.is_authenticated:
        raise Http404("Media not found")
    
    # 获取此媒体的所有总结快照，按创建时间降序排序
    snapshots = media.summary_snapshots.all().order_by('-created_at')
    
    # 将当前总结转换为markdown HTML
    summary_html = None
    if media.summary:
        summary_html = markdown.markdown(media.summary)
    
    return render(request, 'core/audio_media_detail.html', {
        'media': media,
        'summary_html': summary_html,
        'snapshots': snapshots,
    })

def summary_snapshot_detail(request, pk):
    """显示特定总结快照的详细信息"""
    snapshot = get_object_or_404(SummarySnapshot, pk=pk)
    
    # 将总结转换为markdown HTML
    summary_html = markdown.markdown(snapshot.summary)
    
    return render(request, 'core/summary_snapshot_detail.html', {
        'snapshot': snapshot,
        'summary_html': summary_html,
    })

@never_cache
def debug_translations(request):
    """
    Debug view to check translation settings.
    Only enable in development or temporarily in production.
    """
    if not settings.DEBUG and not request.user.is_superuser:
        return JsonResponse({"error": "Not available"}, status=403)
        
    # Get current language
    current_lang = translation.get_language()
    
    # Check if .mo files exist
    locale_path = settings.LOCALE_PATHS[0]
    mo_file_path = os.path.join(locale_path, current_lang, 'LC_MESSAGES', 'django.mo')
    mo_file_exists = os.path.exists(mo_file_path)
    
    # Environment variables related to locale
    locale_env = {k: v for k, v in os.environ.items() if 'lang' in k.lower() or 'loc' in k.lower()}
    
    return JsonResponse({
        "current_language": current_lang,
        "default_language": settings.LANGUAGE_CODE,
        "available_languages": dict(settings.LANGUAGES),
        "locale_paths": [str(p) for p in settings.LOCALE_PATHS],
        "mo_file_exists": mo_file_exists,
        "mo_file_path": mo_file_path,
        "use_i18n": settings.USE_I18N,
        "locale_middleware_enabled": "django.middleware.locale.LocaleMiddleware" in settings.MIDDLEWARE,
        "locale_env_variables": locale_env,
        "accept_language": request.META.get('HTTP_ACCEPT_LANGUAGE', 'Not provided'),
        "language_cookie": request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, 'Not set'),
        "language_session": request.session.get(translation.LANGUAGE_SESSION_KEY, 'Not set')
    })
