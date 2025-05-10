import logging
from django.utils import translation

logger = logging.getLogger('core')

class LanguageDebugMiddleware:
    """
    Middleware to log information about language detection and selection.
    Only enable this temporarily for debugging.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log before processing
        logger.info(f"Request path: {request.path}")
        logger.info(f"Accept-Language header: {request.headers.get('Accept-Language', 'None')}")
        logger.info(f"Current language before processing: {translation.get_language()}")

        # Check session and cookies
        lang_session = request.session.get(translation.LANGUAGE_SESSION_KEY, 'Not set')
        lang_cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, 'Not set')
        logger.info(f"Language in session: {lang_session}")
        logger.info(f"Language in cookie: {lang_cookie}")
        
        # Continue processing
        response = self.get_response(request)
        
        # Log after processing
        logger.info(f"Current language after processing: {translation.get_language()}")
        logger.info(f"Content-Language header: {response.get('Content-Language', 'Not set')}")
        
        return response
