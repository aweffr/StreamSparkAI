import time
from django.test import SimpleTestCase
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.files.base import ContentFile
import tempfile
import os
import uuid
from pathlib import Path
from .utils.transcribe_audio import transcribe_audio
from .utils.audio_processor import process_audio_file, SUPPORTED_FORMATS

class StorageTestCase(SimpleTestCase):
    """Test case to verify that django-storages configuration works correctly."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_file_paths = []
    
    def tearDown(self):
        """Clean up any test files created during tests."""
        for path in self.test_file_paths:
            if default_storage.exists(path):
                default_storage.delete(path)
    
    def test_basic_file_upload(self):
        """Test that a simple file upload works with the configured storage backend."""
        # Generate a unique filename to avoid conflicts
        filename = f'test-file-{uuid.uuid4()}.txt'
        test_file_path = f'test-uploads/{filename}'
        self.test_file_paths.append(test_file_path)
        
        # Create file content
        test_content = b"This is a test file for storage verification."
        
        # Upload the file using default storage
        saved_path = default_storage.save(test_file_path, ContentFile(test_content))
        
        # Verify the file was uploaded successfully
        self.assertTrue(default_storage.exists(saved_path), "Failed to find uploaded file")
        
        # Read the file content back
        with default_storage.open(saved_path) as f:
            retrieved_content = f.read()
        
        # Verify the content matches what we uploaded
        self.assertEqual(retrieved_content, test_content, "File content doesn't match original")
        
        # Get the URL for the file (important for cloud storage)
        file_url = default_storage.url(saved_path)
        self.assertIsNotNone(file_url)
        
        # Test file delete functionality
        default_storage.delete(saved_path)
        self.assertFalse(default_storage.exists(saved_path), "Failed to delete test file")
    
    def test_nested_directory_upload(self):
        """Test uploading to nested directories."""
        # Generate a unique path with nested directories
        test_file_path = f'test-uploads/nested/dirs/{uuid.uuid4()}/test.txt'
        self.test_file_paths.append(test_file_path)
        
        # Create and save file
        test_content = b"Test content for file in nested directory"
        saved_path = default_storage.save(test_file_path, ContentFile(test_content))
        
        # Verify the file exists in the nested structure
        self.assertTrue(default_storage.exists(saved_path))


class TestTranscribeAudio(SimpleTestCase):
    def setUp(self):
        self.audio_url = os.environ.get('TEST_AUDIO_URL')
        if not self.audio_url:
            raise ValueError("TEST_AUDIO_URL environment variable not set")

    def test_transcribe_audio_success(self):
        """Test successful transcription with valid audio URL"""
        # This test will make an actual API call
        
        result = transcribe_audio(self.audio_url)
        
        # Check if the result has expected structure
        self.assertIn('raw_json', result)
        self.assertIn('formatted_text', result)
        self.assertIsNotNone(result['raw_json'])
        self.assertIsNotNone(result['formatted_text'])
        self.assertNotIn("Error:", result['formatted_text'])
        
        # Verify the formatted text has speaker information
        self.assertIn("speaker", result['formatted_text'])
        
        print("Transcription formatted_text:", result['formatted_text'])
        with open(settings.LOG_DIR / f'transcription_result-{int(time.time())}.txt', 'w') as f:
            f.write(result['formatted_text'])


class TestAudioProcessor(SimpleTestCase):
    """Test case for audio processing functionality."""
    
    def setUp(self):
        # Check if we have a test audio file environment variable
        self.real_audio_path = os.environ.get('TEST_AUDIO_FILE')

    def test_process_audio_file_with_real_audio(self):
        """Test audio processing with a real audio file if available."""
        if not self.real_audio_path:
            self.skipTest("TEST_AUDIO_FILE environment variable not set")
        
        # Check that the file exists
        self.assertTrue(os.path.exists(self.real_audio_path), 
                       f"Test audio file {self.real_audio_path} doesn't exist")
        
        # Process the real audio file
        output_path = process_audio_file(self.real_audio_path)
        
        # Add validation similar to the previous test
        self.assertIsNotNone(output_path, "Audio processing failed with real audio file")
        
        if output_path:
            self.assertTrue(os.path.exists(output_path))
            self.assertTrue(output_path.endswith('.aac'))
            self.assertGreater(os.path.getsize(output_path), 0)