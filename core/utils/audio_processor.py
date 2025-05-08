import subprocess
import os
import shutil
import logging
import uuid
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# Define supported input formats
SUPPORTED_FORMATS = ['.mp3', '.mp4', '.aac', '.wav', '.m4a', '.flac']


def ensure_tmp_dir():
    """
    Create tmp directory if it doesn't exist.
    
    Returns:
        Path: Path to the tmp directory
    """
    tmp_dir = settings.BASE_DIR / "tmp"
    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir, exist_ok=True)
        logger.info(f"Created temporary directory at {tmp_dir}")
    
    return tmp_dir


def check_ffmpeg_installed():
    """
    Check if ffmpeg is installed and available in the PATH.
    
    Returns:
        bool: True if ffmpeg is installed, False otherwise
    """
    try:
        subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("FFmpeg is not installed or not in PATH. Please install FFmpeg.")
        return False


def convert_to_mono_aac(
    input_file_path, 
    output_filename=None, 
    bitrate="64k", 
    sample_rate=16000,
    remove_original=False
):
    """
    Convert audio file to mono AAC format with specified bitrate.
    
    Args:
        input_file_path (str or Path): Path to input audio file
        output_filename (str, optional): Name for the output file (without extension). 
                                        If None, a UUID will be used.
        bitrate (str, optional): Target bitrate. Defaults to "64k".
        sample_rate (int, optional): Sample rate in Hz. Defaults to 16000.
        remove_original (bool, optional): Whether to remove original file after conversion. 
                                         Defaults to False.
    
    Returns:
        str: Path to the converted file or None if conversion failed
    """
    if not check_ffmpeg_installed():
        return None
    
    # Convert input path to Path object if it's a string
    input_path = Path(input_file_path) if isinstance(input_file_path, str) else input_file_path
    
    # Validate file extension
    if input_path.suffix.lower() not in SUPPORTED_FORMATS:
        logger.error(f"Unsupported file format: {input_path.suffix}. Supported formats: {SUPPORTED_FORMATS}")
        return None
    
    # Ensure input file exists
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return None
    
    # Create tmp directory if it doesn't exist
    tmp_dir = ensure_tmp_dir()
    
    # Generate output filename if not provided
    if not output_filename:
        output_filename = f"processed_{uuid.uuid4().hex}"
    
    # Make sure output filename doesn't have an extension
    output_filename = Path(output_filename).stem
    
    # Define output path
    output_path = tmp_dir / f"{output_filename}.aac"
    
    # If input file is not in tmp directory, copy it there first
    if tmp_dir != input_path.parent:
        tmp_input = tmp_dir / input_path.name
        shutil.copy2(input_path, tmp_input)
        input_path = tmp_input
        logger.debug(f"Copied input file to temp directory: {tmp_input}")
    
    try:
        # Build the FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output file if exists
            "-i", str(input_path),
            "-vn",  # Disable video if present
            "-ac", "1",  # Convert to mono (1 audio channel)
            "-c:a", "aac",  # Use AAC codec
            "-b:a", bitrate,  # Set bitrate
            "-ar", str(sample_rate),  # Set sample rate
            str(output_path)
        ]
        
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        # 根据 Django 调试模式决定输出重定向
        if settings.DEBUG:
            # 在调试模式下，将 FFmpeg 输出传递到主程序
            result = subprocess.run(
                cmd,
                stdout=None,  # None 表示继承父进程的 stdout
                stderr=None,  # None 表示继承父进程的 stderr
                text=True,
                check=True
            )
        else:
            # 在生产模式下，捕获输出
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        
        logger.info(f"Successfully converted {input_path} to mono AAC format at {output_path}")
        
        # Remove original file if requested and it was copied to tmp
        if remove_original and input_path.parent == tmp_dir and input_path != output_path:
            input_path.unlink()
            logger.debug(f"Removed original file: {input_path}")
        
        return str(output_path)
    
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr}")
        return None
    except Exception as e:
        logger.exception(f"Error during file conversion: {str(e)}")
        return None


def process_audio_file(file_path, bitrate="64k", sample_rate=16000):
    """
    Process audio file with standardized settings: mono channel, AAC codec, specified bitrate.
    
    Args:
        file_path (str or Path): Path to the input audio file
        bitrate (str, optional): Target bitrate. Defaults to "64k".
        sample_rate (int, optional): Sample rate in Hz. Defaults to 16000.
    
    Returns:
        str: Path to processed file or None if processing failed
    """
    logger.info(f"Processing audio file: {file_path}")
    return convert_to_mono_aac(file_path, bitrate=bitrate, sample_rate=sample_rate)

