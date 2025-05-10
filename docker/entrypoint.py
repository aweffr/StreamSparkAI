#!/usr/bin/env python3
import os
import sys
import time
import socket
import logging
from urllib.parse import urlparse
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docker-entrypoint")

def wait_for_db(database_url):
    """Wait for the database to be ready."""
    parsed_url = urlparse(database_url)
    
    # Only wait for MySQL/MariaDB connections
    if parsed_url.scheme in ("mysql", "mariadb"):
        host = parsed_url.hostname
        port = parsed_url.port or 3306
        
        logger.info(f"Waiting for database at {host}:{port}...")
        
        import socket
        
        start_time = time.time()
        while True:
            try:
                socket_obj = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socket_obj.settimeout(1)
                socket_obj.connect((host, port))
                socket_obj.close()
                logger.info(f"Database is ready at {host}:{port}")
                break
            except (socket.error, socket.timeout):
                if time.time() - start_time > 60:  # Wait up to 60 seconds
                    logger.error(f"Database connection timed out: {host}:{port}")
                    sys.exit(1)
                time.sleep(1)

def create_superuser_if_missing():
    """Create a superuser if one doesn't exist."""
    # Get superuser credentials from environment variables with defaults
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    
    if not password:
        logger.info("No DJANGO_SUPERUSER_PASSWORD provided, skipping superuser creation")
        return
        
    logger.info("Checking if any users exist in the system...")
    
    # Run a Django shell command to check if any user exists
    result = subprocess.run(
        ["python", "manage.py", "shell", "-c", 
         f"from django.contrib.auth import get_user_model; "
         f"User = get_user_model(); "
         f"exit(0 if User.objects.exists() else 1)"],
        capture_output=True
    )
    
    if result.returncode == 0:
        logger.info("Users already exist in the system, skipping superuser creation")
        return
        
    logger.info(f"No users found. Creating superuser '{username}'...")
    
    # Create superuser using management command
    process = subprocess.Popen([
        "python", "manage.py", "createsuperuser", 
        "--noinput",
        "--username", username,
        "--email", email
    ], env={**os.environ, "DJANGO_SUPERUSER_PASSWORD": password})
    
    if process.wait() != 0:
        logger.error("Failed to create superuser")
        return
        
    logger.info(f"Superuser '{username}' created successfully")

def main():
    """Main entry point for the container."""
    # Get database URL from environment
    database_url = os.environ.get("DATABASE_URL")
    
    if database_url and not database_url.startswith('sqlite'):
        wait_for_db(database_url)
    
    # Run django migrations
    logger.info("Running migrations...")
    subprocess.run(["python", "manage.py", "migrate"], check=True)
    
    # Create superuser if needed
    create_superuser_if_missing()
    
    # Collect static files
    logger.info("Collecting static files...")
    subprocess.run(["python", "manage.py", "collectstatic", "--no-input"], check=True)
    
    # Compile translation messages
    logger.info("Compiling messages...")
    subprocess.run(["python", "manage.py", "compilemessages"], check=True)

    logger.info("Starting Gunicorn server...")
    process = subprocess.Popen(["gunicorn", "conf.wsgi:application", "--bind", "0.0.0.0:8000"])
    # Wait for the process to finish, this keeps the container running
    process.wait()
    sys.exit(process.returncode)

if __name__ == "__main__":
    main()
