from django.shortcuts import render, get_object_or_404
from django.http import Http404
import markdown
from .models import AudioMedia, SummarySnapshot

def audio_media_list(request):
    """显示所有已处理的音频媒体文件列表"""
    # 基础查询条件 - 已处理且已转录完成的文件
    base_query = AudioMedia.objects.filter(
        processing_status='completed',
        transcription_status='completed'
    )
    
    # 如果用户未登录，只显示公开媒体
    if not request.user.is_authenticated:
        media_list = base_query.filter(is_private=False).order_by('-upload_date')
    else:
        # 已登录用户可以查看所有媒体
        media_list = base_query.order_by('-upload_date')
    
    return render(request, 'core/audio_media_list.html', {
        'media_list': media_list,
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
