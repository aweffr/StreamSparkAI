from django import template
from django.conf import settings
from django.utils.translation import get_language

register = template.Library()

@register.inclusion_tag('core/language_selector.html')
def language_selector():
    """
    Renders a language selector dropdown.
    """
    current_lang = get_language()
    return {
        'languages': settings.LANGUAGES,
        'current_lang': current_lang,
    }
