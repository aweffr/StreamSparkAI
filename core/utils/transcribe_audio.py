import time
import json
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def transcribe_audio(audio_url):
    """
    Transcribe an audio file using Alibaba Cloud's Paraformer-v2 model with speaker diarization.
    
    Args:
        audio_url (str): URL to the audio file (must be publicly accessible)
    
    Returns:
        dict: A dictionary containing:
            - 'raw_json': The raw JSON response from the API
            - 'formatted_text': A formatted text with speaker labels
    """
    logger.info(f"Starting transcription for audio at: {audio_url}")
    
    # Get API key from Django settings
    api_key = getattr(settings, 'ALIBABA_DASHSCOPE_API_KEY', None)
    
    if not api_key:
        logger.error("API key for Alibaba DashScope not found in settings")
        raise ValueError("API key for Alibaba DashScope not found in settings")
    
    # Step 1: Submit the transcription task
    logger.info("Submitting transcription task to Alibaba DashScope API")
    task_id = submit_task(api_key, audio_url)
    
    if not task_id:
        logger.error("Failed to submit transcription task")
        return {
            'raw_json': None,
            'formatted_text': "Error: Failed to submit transcription task"
        }
    
    logger.info(f"Successfully submitted task with ID: {task_id}")
    
    # Step 2: Wait for the task to complete and get results
    logger.info(f"Waiting for task {task_id} to complete")
    result = wait_for_completion(api_key, task_id)
    
    if not result:
        logger.error(f"Failed to retrieve transcription results for task {task_id}")
        return {
            'raw_json': None,
            'formatted_text': "Error: Failed to retrieve transcription results"
        }
    
    logger.info(f"Successfully retrieved transcription results for task {task_id}")
    
    # Step 3: Process the results and format the text
    logger.info("Formatting transcription results")
    formatted_text = format_transcription_result(result)
    
    logger.info("Transcription process completed successfully")
    return {
        'raw_json': result,
        'formatted_text': formatted_text
    }

def submit_task(api_key, audio_url):
    """
    Submit a transcription task to the API.
    
    Args:
        api_key (str): Alibaba Cloud DashScope API key
        audio_url (str): URL to the audio file
    
    Returns:
        str: Task ID if successful, None otherwise
    """
    logger.debug(f"Preparing API request for audio at: {audio_url}")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    
    data = {
        "model": "paraformer-v2",
        "input": {"file_urls": [audio_url]},
        "parameters": {
            "channel_id": [0],
            "language_hints": ["zh", "en"],
            "diarization_enabled": True  # Enable speaker separation
        }
    }
    
    service_url = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
    
    try:
        logger.debug("Sending task submission request to Alibaba DashScope API")
        response = requests.post(
            service_url,
            headers=headers,
            data=json.dumps(data)
        )
        
        if response.status_code == 200:
            task_id = response.json().get("output", {}).get("task_id")
            logger.debug(f"Task submission successful, received task ID: {task_id}")
            return task_id
        else:
            logger.error(f"Task submission failed with status code: {response.status_code}, response: {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Exception during task submission: {e}")
        return None

def wait_for_completion(api_key, task_id, max_retries=120, retry_interval=5):
    """
    Poll for task completion and return results.
    
    Args:
        api_key (str): Alibaba Cloud DashScope API key
        task_id (str): ID of the transcription task
        max_retries (int): Maximum number of polling attempts
        retry_interval (int): Time between polling attempts in seconds
    
    Returns:
        dict: Task results if successful, None otherwise
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    
    retry_count = 0
    
    while retry_count < max_retries:
        service_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
        
        try:
            logger.debug(f"Polling task status (attempt {retry_count+1}/{max_retries})")
            response = requests.post(service_url, headers=headers)
            
            if response.status_code == 200:
                response_data = response.json()
                status = response_data.get('output', {}).get('task_status')
                
                if status == 'SUCCEEDED':
                    logger.info(f"Task {task_id} completed successfully")
                    # Get transcription results
                    results = response_data.get('output', {}).get('results', [])
                    if results and results[0].get('subtask_status') == 'SUCCEEDED':
                        # Get the transcription URL
                        transcription_url = results[0].get('transcription_url')
                        if transcription_url:
                            logger.debug(f"Fetching transcription content from URL: {transcription_url}")
                            # Fetch the transcription content
                            transcription_response = requests.get(transcription_url)
                            if transcription_response.status_code == 200:
                                logger.info("Successfully retrieved transcription content")
                                return transcription_response.json()
                            else:
                                logger.error(f"Failed to get transcription content: status code {transcription_response.status_code}, response: {transcription_response.text}")
                        else:
                            logger.error("No transcription URL found in the response")
                    else:
                        logger.error("Task reported success but subtask failed or no results were returned")
                    return None
                elif status in ['RUNNING', 'PENDING']:
                    # Task still processing, wait and retry
                    logger.debug(f"Task status: {status}, waiting {retry_interval} seconds before retry")
                    retry_count += 1
                    time.sleep(retry_interval)
                else:
                    # Task failed
                    logger.error(f"Task failed with status: {status}")
                    return None
            else:
                # API request failed
                logger.error(f"API request failed with status code: {response.status_code}, response: {response.text}")
                return None
        
        except Exception as e:
            logger.exception(f"Exception during task polling: {e}")
            return None
    
    # Max retries exceeded
    logger.error(f"Task polling timed out after {max_retries} attempts")
    return None

def format_transcription_result(result):
    """
    Format the transcription result with speaker labels (A, B, C, etc.)
    
    Args:
        result (dict): The raw transcription result from the API
    
    Returns:
        str: Formatted text with speaker labels (A, B, C, etc.)
    """
    if not result:
        logger.warning("No transcription result available to format")
        return "No transcription result available"
    
    transcripts = result.get('transcripts', [])
    if len(transcripts) == 0:
        logger.warning("No transcripts found in the result")
        return "No transcripts available"
    
    if "sentences" not in transcripts[0]:
        logger.warning("No sentences found in the transcript")
        return "No sentences available"
    
    # Extract sentences with speaker information
    sentences = transcripts[0].get('sentences', [])
    
    if len(sentences) == 0:
        logger.warning("No sentences found in the transcription result")
        return "No sentences available"
    
    logger.debug(f"Found {len(sentences)} valid sentences with speaker information")
    
    # Map speaker IDs to numbered labels (speaker 1, speaker 2, ...)
    speaker_map = {}
    current_speaker = None
    current_text = ""
    formatted_lines = []
    
    for sentence in sentences:
        speaker_id = sentence.get('speaker_id')
        text = sentence.get('text', '').strip()
        
        if not text:
            continue
        
        # Map speaker ID to a numbered label
        if speaker_id not in speaker_map:
            speaker_map[speaker_id] = f"speaker {len(speaker_map) + 1}"  # Convert to "speaker 1", "speaker 2", etc.
        
        speaker_label = speaker_map[speaker_id]
        
        # If this is the same speaker as the previous sentence, append to current text
        if speaker_id == current_speaker:
            current_text += f" {text}"
        else:
            # If we have accumulated text from a previous speaker, add it to the result
            if current_text:
                formatted_lines.append(f"{speaker_map[current_speaker]}: {current_text}")
            
            # Start accumulating text for the new speaker
            current_speaker = speaker_id
            current_text = text
    
    # Don't forget to add the last accumulated text
    if current_text:
        formatted_lines.append(f"{speaker_map[current_speaker]}: {current_text}")
    
    logger.debug(f"Formatted transcript with {len(formatted_lines)} lines from {len(speaker_map)} speakers")
    return "\n".join(formatted_lines)