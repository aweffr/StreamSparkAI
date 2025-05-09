import time
from django.test import SimpleTestCase
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.files.base import ContentFile
import tempfile
import os
import uuid
from pathlib import Path
import json
import logging
from .utils.transcribe_audio import transcribe_audio
from .utils.audio_processor import process_audio_file, SUPPORTED_FORMATS
from .utils.llm_client import LLMClient, SummaryType, trim_multiple_line_indent

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


class TestLLMClient(SimpleTestCase):
    """Test the LLMClient for both OpenAI and Alibaba providers."""
    
    def setUp(self):
        """Set up the test environment."""
        # Test text for summarization
        self.test_text = trim_multiple_line_indent("""
        speaker 1: 欢迎大家参加今天的会议。我们今天主要讨论两个议题：一个是新产品的发布时间表，另一个是营销策略。
        speaker 2: 关于新产品发布，研发团队已经完成了主要功能开发，目前正在进行最后的测试。我们预计可以在下个月底前完成所有测试。
        speaker 1: 那么，我们可以定在什么时候正式发布？
        speaker 2: 考虑到测试完成后还需要准备发布材料，我建议定在两个月后的15号。
        speaker 3: 我同意这个时间，这样营销团队也有足够的时间准备宣传活动。我们计划在社交媒体上进行为期两周的预热。
        speaker 1: 好的，那么发布日期就定在两个月后的15号。现在我们来讨论一下营销策略。
        speaker 3: 我们已经起草了一个营销方案，主要包括网络广告、社交媒体推广和线下活动三个部分。
        speaker 1: 预算是多少？
        speaker 3: 总预算约50万元，其中网络广告20万，社交媒体推广15万，线下活动15万。
        speaker 1: 这个预算看起来合理。我们需要重点关注哪些渠道？
        speaker 3: 根据我们的用户画像分析，重点应该放在抖音和小红书上，这两个平台是我们目标用户最活跃的地方。
        speaker 1: 好的，那就按这个方案执行。还有其他问题吗？
        speaker 2: 没有了。
        speaker 3: 我这边也没有了。
        speaker 1: 那么今天的会议就到这里。谢谢大家参加。
        """)
    
    def test_openai_health_check(self):
        """Test the health_check method with OpenAI client."""
        # Create an OpenAI client and test health check
        client = LLMClient.get_client(provider="openai")
        success, response = client.health_check()
        
        # Assertions
        self.assertTrue(success, f"Health check failed: {response}")
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        
        print(f"OpenAI health check response: {response[:100]}...")
    
    def test_alibaba_health_check(self):
        """Test the health_check method with Alibaba client."""
        # Create an Alibaba client and test health check
        client = LLMClient.get_client(provider="alibaba")
        success, response = client.health_check()
        
        # Assertions
        self.assertTrue(success, f"Health check failed: {response}")
        self.assertIsNotNone(response)
        self.assertIsInstance(response, str)
        self.assertTrue(len(response) > 0)
        
        print(f"Alibaba health check response: {response[:100]}...")
    
    def test_openai_summarize(self):
        """Test the summarize method with OpenAI client."""
        # Create an OpenAI client and test summarize
        client = LLMClient.get_client(provider="openai")
        result = client.summarize(self.test_text, summary_type=SummaryType.GENERAL)
        
        # Assertions
        self.assertIn('summary', result)
        self.assertIn('raw_response', result)
        self.assertIsNotNone(result['summary'])
        self.assertIsNotNone(result['raw_response'])
        self.assertIsInstance(result['summary'], str)
        self.assertTrue(len(result['summary']) > 0)
        
        print(f"OpenAI summary: {result['summary'][:100]}...")
    
    def test_alibaba_summarize(self):
        """Test the summarize method with Alibaba client."""
        # Create an Alibaba client and test summarize
        client = LLMClient.get_client(provider="alibaba")
        result = client.summarize(self.test_text, summary_type=SummaryType.KEY_POINTS)
        
        # Assertions
        self.assertIn('summary', result)
        self.assertIn('raw_response', result)
        self.assertIsNotNone(result['summary'])
        self.assertIsNotNone(result['raw_response'])
        self.assertIsInstance(result['summary'], str)
        self.assertTrue(len(result['summary']) > 0)
        
        print(f"Alibaba key points summary: {result['summary'][:100]}...")