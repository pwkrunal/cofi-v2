# Standard library imports
import asyncio
import base64
import concurrent.futures
import json as jsn
import logging.config
import math
import os
import random
import re
import shutil
import ssl
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Thread
from urllib import response
from urllib.parse import urlparse
import urllib.request as req

# Third-party imports
import docker
import mysql.connector
import pandas as pd
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv
from rapidfuzz import fuzz
from sanic import Sanic
from sanic.request import Request
from sanic.response import json, text
from sanic.response import json as sanic_json
from sanic_cors import CORS
from collections import defaultdict

# Local imports
import cofi_config as config
import stt_wrapper as api_wrapper
from license_sdk import LicenseClient

# Load environment variables
load_dotenv()
client_docker = docker.from_env()
logging.config.dictConfig(config.LOGGING_CONFIG)
logger = logging.getLogger('root')
logconsole = logging.getLogger('console')
executor = ThreadPoolExecutor()
app = Sanic(__name__)
app.config['REQUEST_MAX_SIZE'] = 500 * 1024 * 1024
app.config['CORS_AUTOMATIC_OPTIONS'] = True
app.config['REQUEST_TIMEOUT'] = 6000
app.config['RESPONSE_TIMEOUT'] = 6000
app.static('/audio', './audio')
app.static('/shared-files', '/home/ubuntu/Downloads/docker_volume/shared-files')
# Global variable to store webhook status info
WEBHOOK_STATUS = {}
SECRET_KEY_CLIENT = "HhkJiZPBvbs4PZzuaYIopStlheOP4xe82KalJR5PVQo="
cipher_client = Fernet(SECRET_KEY_CLIENT)
license_base_url = os.environ.get("license_base_url","https://license.contiinex.com/api")
license_db_url = os.environ.get("license_db_url","35.200.216.160")
client = LicenseClient(base_url=license_base_url)
license_instance_type = os.environ.get("license_instance_type","")

SPLIT_BASE_URL = os.environ.get('SPLIT_URL')
INSTANCE_TYPE = os.environ.get('INSTANCE_TYPE', '')
SPLIT_ARCH = os.environ.get('SPLIT_ARCH', False)
STT_FILE_DIR = os.environ.get('STORAGE_PATH')
LID_FILE_DIR = os.environ.get('DESTINATION_LID')
callMetadata = []
CORS(app)
translate_queue = []
REQUEST_IN_PROGRESS = False
REQUEST_IN_PROGRESS_AUDIT = False
REQUEST_IN_PROGRESS_AUDIT_2 = False
CURRENT_BATCH_ID = None
CURRENT_BATCH_STATUS = None
callMetadata = []
callsData = []
tradeAudioMappingData = []
callConversationData = []
tradeMetadataData = []
lotQuantityMappingData = []


request_queue = asyncio.Queue()
time.sleep(2)
db_config = {
    'user': os.environ.get('MYSQL_USER'),
    'password': os.environ.get('MYSQL_PASSWORD'),
    # 'host': '10.125.9.151',
    'host': os.environ.get('MYSQL_HOST'),
    #'host': '34.47.196.156',
    # 'database': 'testDb',
    'database': os.environ.get('MYSQL_DATABASE'),
}
dataBase1 = mysql.connector.connect(
  host =os.environ.get('MYSQL_HOST'),
  port=os.environ.get('MYSQL_PORT'),
  user = os.environ.get('MYSQL_USER'),
  password =os.environ.get('MYSQL_PASSWORD'),
  connection_timeout= 86400000
)

cursorObject1 = dataBase1.cursor(buffered=True)
try:
    cursorObject1.execute("CREATE DATABASE auditNexDb")
except Exception as e:
    print("Database exists")


dataBase2 = mysql.connector.connect(
  host =os.environ.get('MYSQL_HOST'),
  user =os.environ.get('MYSQL_USER'),
  password =os.environ.get('MYSQL_PASSWORD'),
  database = os.environ.get('MYSQL_DATABASE'),
  connection_timeout= 86400000
)
cursorObject = dataBase2.cursor(buffered=True)


def start_container_gpu(container_name, url):
    url = f"{url}/start_container"
    response = requests.post(url, json={"container_name": container_name})
    print("Start:", response.status_code, response.json())

def stop_container_gpu(container_name, url):
    url = f"{url}/stop_container"
    response = requests.post(url, json={"container_name": container_name})
    print("Stop:", response.status_code, response.json())


def start_container(container_name):
    url = f"{SPLIT_BASE_URL}/start_container"
    response = requests.post(url, json={"container_name": container_name})
    print("Start:", response.status_code, response.json())

def stop_container(container_name):
    url = f"{SPLIT_BASE_URL}/stop_container"
    response = requests.post(url, json={"container_name": container_name})
    print("Stop:", response.status_code, response.json())


def upload_file_stt_trigger(api_url, file_url):
    url = f"{api_url}/upload_file_stt"
    response = requests.post(url, json={"file_url": file_url, "ivr_enabled": os.environ.get("IS_IVR_ENABLED",1)})
    print("Upload:", response.status_code, response.json())

def distribute_files_for_stt(files, batch_date):
    """Distribute files to STT endpoints for processing"""
    upload_tasks = []
    stt_endpoints = os.environ.get('STT_ENDPOINTS', '')
    endpoints = [ep.strip() for ep in stt_endpoints.split(',') if ep.strip()]

    for idx, file in enumerate(files):
        # file_url = f"{SPLIT_BASE_URL}/audios/{batch_date}/{os.path.basename(file)}"
        file_url = f"{SPLIT_BASE_URL}/audios/{os.path.basename(file)}"

        if not endpoints:
            logger.info(f"No STT endpoints set, using default: {stt_endpoints}, URL: {file_url}")
            upload_tasks.append((stt_endpoints, file_url))
        else:
            for endpoint in endpoints:
                logger.info(f"STT endpoint {endpoint} found, URL: {file_url}")
                upload_tasks.append((endpoint, file_url))

    # Run uploads in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(upload_file_stt_trigger, endpoint, file_url)
                   for endpoint, file_url in upload_tasks]
        concurrent.futures.wait(futures)

    logger.info("Files uploaded to AUDIO_ENDPOINT(s) for STT processing.")

def process_smb_denoise(input_files=None):
    """
    Process SMB-DENOISE detection on audio files after they are copied and distributed
    """
    global REQUEST_IN_PROGRESS, INSTANCE_TYPE, SPLIT_ARCH
    global translate_queue
    REQUEST_IN_PROGRESS = True
    denoise_results = []
    # os.makedirs(output_dir, exist_ok=True)
    lid_api_urls = os.environ.get('DENOISE_API_URL', '')
    lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
    # files = [f for f in os.listdir(input_dir) if f.lower().endswith(".wav")]
    files = input_files
    

    rows = []  # buffer for csv rows
    processed_files = []
    def process_denoise_file(filename, denoise_api_url):

        logger.info(f"Processing DENOISE for file: {os.path.basename(file)} with API URL: {denoise_api_url}")
        try:
            dataBase3112 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject3112 = dataBase3112.cursor(dictionary=True,buffered=True)
            logger.info(f" Processing {filename}")
            payload = {
                "filename": filename,

            }
            # if template_dir:
            #     payload["template_folder"] = template_dir

            t0 = time.time()

            resp = requests.post(denoise_api_url, json=payload, timeout=None)
            elapsed = time.time() - t0


            result = resp.json()

            logger.info(f"DENOISE result: {result}")
            # Normalize result format
            if isinstance(result, dict) and "denoise_detected" in result:
                out = result
            elif isinstance(result, dict) and "result" in result:
                out = result["result"]
            else:
                out = result

            # Pull details
            denoise_detected = out.get("denoise_detected")
            denoise_end = out.get("denoise_end_sec")
            orig_sec = out.get("original_duration_sec")
            trimmed_sec = out.get("trimmed_duration_sec")
            output_audio = out.get("output_audio")

            logger.info(f"denoise_detected: {denoise_detected}, denoise_end: {denoise_end}, original_second: {orig_sec}, trimmed_second: {trimmed_sec}, output_audio: {output_audio}")

            # Save row for CSV
            rows.append([filename, denoise_detected, denoise_end, orig_sec, trimmed_sec, output_audio, round(elapsed, 2)])
            processed_files.append(filename)
            parsed = urlparse(denoise_api_url)
            logger.info(parsed.hostname + " " + filename)
            add_column = ("INSERT INTO auditNexDb.ivr (file, ip)" "VALUES(%s, %s)")
            add_result = (filename, parsed.hostname)
            cursorObject3112.execute(add_column, add_result)
            dataBase3112.commit()
            return {'ip': parsed.hostname, 'file': filename}
            # # Write every 50 files
            # if idx % 50 == 0:
            #     csv_out = os.path.join(output_dir, "ivr_results.csv")
            #     write_mode = "a" if os.path.exists(csv_out) else "w"
            #     with open(csv_out, write_mode, newline="") as f:
            #         writer = csv.writer(f)
            #         if write_mode == "w":
            #             writer.writerow(["filename", "ivr_detected", "ivr_end_sec", "original_duration_sec", "trimmed_duration_sec", "output_audio", "processing_time_sec"])
            #         writer.writerows(rows)
            #     rows = []  # clear buffer after writing
        except requests.RequestException as e:
            logger.error(f"Error triggering DENOISE API for file {file}: {e}")
            parsed = urlparse(denoise_api_url)
            logger.info(parsed.hostname + " " + filename)
            add_column = ("INSERT INTO auditNexDb.ivr (file, ip)" "VALUES(%s, %s)")
            add_result = (filename, parsed.hostname)
            cursorObject3112.execute(add_column, add_result)
            dataBase3112.commit()
            return {'ip': parsed.hostname, 'file': filename}

    logger.info("DENOISE API URLs: " + str(lid_api_url_list))
    logger.info(INSTANCE_TYPE)
    logger.info("Files to process for DENOISE: " + str(len(files)))
    # Prepare upload tasks for parallel execution
    upload_tasks = []
    # lid_api_urls = os.environ.get('LID_ENDPOINT', '')
    # lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
    upload_api_urls = os.environ.get('LID_ENDPOINT', '')
    upload_api_url_list = [url.strip() for url in upload_api_urls.split(',') if url.strip()]
    lid_files = [file for file in files if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
    processed_denoise_files = []
    for idx, file in enumerate(lid_files):
        file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
        lid_api_url = ''
        upload_api_url = ''
        if lid_api_url_list:
            getIndex = idx % len(lid_api_url_list)
            lid_api_url = lid_api_url_list[getIndex]
            upload_api_url = upload_api_url_list[getIndex]
        else:
            lid_api_url = os.environ.get('DENOISE_API_URL')
            upload_api_url = os.environ.get('LID_ENDPOINT')
        parsed = urlparse(lid_api_url)
        logger.info(parsed.hostname + " " + os.path.basename(file))
        processed_denoise_files.append({
            'ip': parsed.hostname,
            'file': os.path.basename(file),
            'lid_api_url': lid_api_url,
            'upload_api_url': upload_api_url
        })
        logger.info(f"Prepared upload task for file: {file_url} to LID API: {upload_api_url}")
        upload_tasks.append((upload_api_url, file_url))

    # Run uploads in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(upload_file_stt_trigger, endpoint, file_url) for endpoint, file_url in upload_tasks]
        concurrent.futures.wait(futures)

    logger.info("Files uploaded to AUDIO_ENDPOINT(s) for DENOISE processing.")

    time.sleep(2)
    lid_tasks = []
    # for fileObj in processed_denoise_files:
    #     lid_api_url = fileObj['lid_api_url']
    #     logger.info(f"Scheduling LID processing for file: {fileObj['file']} with API URL: {lid_api_url}")
    #     file = fileObj['file']
    #     lid_tasks.append((os.path.basename(file), lid_api_url))
    db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
            }

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT file, ip FROM ivr;")
    rows = cursor.fetchall()
    processed_denoise_files = []
    for row in rows:
        logger.info(f"SMB-DENOISE processed file: {row['file']} from IP: {row['ip']}")
        processed_denoise_files.append({
            'ip': row['ip'],  # from urlparse
            'file': row['file']       # from DB
        })
    for fileObj in processed_denoise_files:
            ip = fileObj['ip']
            lid_api_url  = ''
            for ivr_endpoint in lid_api_url_list:
                if ip == urlparse(ivr_endpoint).hostname:
                    lid_api_url = ivr_endpoint
                    break
            
            logger.info(f"Scheduling DENOISE processing for file: {fileObj['file']} with API URL: {lid_api_url}")
            file = fileObj['file']
            lid_tasks.append((os.path.basename(file), lid_api_url))
    logger.info(f"Total LID URLs to process: {len(lid_api_url_list)}")
    logger.info(f"Total LID tasks to process: {len(lid_tasks)}")
    # Process LID requests in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(lid_api_url_list) or 1) as executor:
        future_to_file = {executor.submit(process_denoise_file, file, lid_api_url): file for file, lid_api_url in lid_tasks}
        logger.info("Waiting for LID processing to complete...")
        for future in concurrent.futures.as_completed(future_to_file):
            dict_result = future.result()
            if dict_result:
                denoise_results.append(dict_result)





    logger.info(f"SMB-DENOISE processing completed. Processed {len(processed_files)} files. Copied files to lid_audios ----- Done")
    return denoise_results

def process_smb_ivr( input_files=None, processed_denoise_files=[]):
    """
    Process SMB-IVR detection on audio files after they are copied and distributed
    """
    global REQUEST_IN_PROGRESS, INSTANCE_TYPE, SPLIT_ARCH
    global translate_queue
    REQUEST_IN_PROGRESS = True
    ivr_results = []
    api_url = "http://localhost:4080/file_ivr_clean"
    # os.makedirs(output_dir, exist_ok=True)
    lid_api_urls = os.environ.get('IVR_API_URL', '')
    lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
    # files = [f for f in os.listdir(input_dir) if f.lower().endswith(".wav")]
    files = input_files
    # if not files:
    #     logger.info(f"No .wav files found in {input_dir}")
    #     return []

    rows = []  # buffer for csv rows
    processed_files = []
    def process_ivr_file(filename, ivr_api_url):

        logger.info(f"Processing IVR for file: {os.path.basename(file)} with API URL: {ivr_api_url}")
        try:
            dataBase3112 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject3112 = dataBase3112.cursor(dictionary=True,buffered=True)
            logger.info(f" Processing {filename}")
            payload = {
                "file_name": filename,

            }
            # if template_dir:
            #     payload["template_folder"] = template_dir

            t0 = time.time()

            resp = requests.post(ivr_api_url, json=payload, timeout=None)
            elapsed = time.time() - t0


            result = resp.json()


            # Normalize result format
            if isinstance(result, dict) and "ivr_detected" in result:
                out = result
            elif isinstance(result, dict) and "result" in result:
                out = result["result"]
            else:
                out = result

            # Pull details
            ivr_detected = out.get("ivr_detected")
            ivr_end = out.get("ivr_end_sec")
            orig_sec = out.get("original_duration_sec")
            trimmed_sec = out.get("trimmed_duration_sec")
            output_audio = out.get("output_path")

            logger.info(f"ivr_detected: {ivr_detected}, ivr_end: {ivr_end}, original_second: {orig_sec}, trimmed_second: {trimmed_sec}, output_audio: {output_audio}")

            # Save row for CSV
            rows.append([filename, ivr_detected, ivr_end, orig_sec, trimmed_sec, output_audio, round(elapsed, 2)])
            processed_files.append(filename)
            parsed = urlparse(ivr_api_url)
            logger.info(parsed.hostname + " " + filename)
            # add_column = ("INSERT INTO auditNexDb.ivr (file, ip)" "VALUES(%s, %s)")
            # add_result = (filename, parsed.hostname)
            # cursorObject3112.execute(add_column, add_result)
            # dataBase3112.commit()
            return {'ip': parsed.hostname, 'file': filename}
            # # Write every 50 files
            # if idx % 50 == 0:
            #     csv_out = os.path.join(output_dir, "ivr_results.csv")
            #     write_mode = "a" if os.path.exists(csv_out) else "w"
            #     with open(csv_out, write_mode, newline="") as f:
            #         writer = csv.writer(f)
            #         if write_mode == "w":
            #             writer.writerow(["filename", "ivr_detected", "ivr_end_sec", "original_duration_sec", "trimmed_duration_sec", "output_audio", "processing_time_sec"])
            #         writer.writerows(rows)
            #     rows = []  # clear buffer after writing
        except requests.RequestException as e:
            logger.error(f"Error triggering IVR API for file {file}: {e}")
            parsed = urlparse(ivr_api_url)
            logger.info(parsed.hostname + " " + filename)
            # add_column = ("INSERT INTO auditNexDb.ivr (file, ip)" "VALUES(%s, %s)")
            # add_result = (filename, parsed.hostname)
            # cursorObject3112.execute(add_column, add_result)
            # dataBase3112.commit()
            return {'ip': parsed.hostname, 'file': filename}

    logger.info("IVR API URLs: " + str(lid_api_url_list))
    logger.info(INSTANCE_TYPE)
    logger.info("Files to process for IVR: " + str(len(files)))
    # Prepare upload tasks for parallel execution
    
    
    time.sleep(2)
    lid_tasks = []
    # if len(processed_denoise_files) == 0:
    #     for fileObj in processed_ivr_files:
    #         ip = fileObj['ip']
    #         lid_api_url  = ''
    #         for ivr_endpoint in lid_api_url_list:
    #             if ip == urlparse(ivr_endpoint).hostname:
    #                 lid_api_url = ivr_endpoint
    #                 break
            
    #         logger.info(f"Scheduling IVR processing for file: {fileObj['file']} with API URL: {lid_api_url}")
    #         file = fileObj['file']
    #         lid_tasks.append((os.path.basename(file), lid_api_url))
    # else:
    #     for fileObj in processed_ivr_files:
    #         lid_api_url = fileObj['lid_api_url']
    #         logger.info(f"Scheduling IVR processing for file: {fileObj['file']} with API URL: {lid_api_url}")
    #         file = fileObj['file']
    #         lid_tasks.append((os.path.basename(file), lid_api_url))
    db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
            }

    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT file, ip FROM ivr;")
    rows = cursor.fetchall()
    processed_ivr_files = []
    for row in rows:
        logger.info(f"SMB-IVR processed file: {row['file']} from IP: {row['ip']}")
        processed_ivr_files.append({
            'ip': row['ip'],  # from urlparse
            'file': row['file']       # from DB
        })
    if len(processed_ivr_files) == 0:
        upload_tasks = []
        if len(processed_denoise_files) == 0:
            
            # lid_api_urls = os.environ.get('LID_ENDPOINT', '')
            # lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
            upload_api_urls = os.environ.get('LID_ENDPOINT', '')
            upload_api_url_list = [url.strip() for url in upload_api_urls.split(',') if url.strip()]
            lid_files = [file for file in files if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
            processed_ivr_files = []
            for idx, file in enumerate(lid_files):
                file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
                lid_api_url = ''
                upload_api_url = ''
                if lid_api_url_list:
                    getIndex = idx % len(lid_api_url_list)
                    lid_api_url = lid_api_url_list[getIndex]
                    upload_api_url = upload_api_url_list[getIndex]
                else:
                    lid_api_url = os.environ.get('IVR_API_URL')
                    upload_api_url = os.environ.get('LID_ENDPOINT')
                parsed = urlparse(lid_api_url)
                logger.info(parsed.hostname + " " + os.path.basename(file))
                processed_ivr_files.append({
                    'ip': parsed.hostname,
                    'file': os.path.basename(file),
                    'lid_api_url': lid_api_url,
                    'upload_api_url': upload_api_url
                })
                logger.info(f"Prepared upload task for file: {file_url} to IVR API: {upload_api_url}")
                upload_tasks.append((upload_api_url, file_url))

            # Run uploads in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(upload_file_stt_trigger, endpoint, file_url) for endpoint, file_url in upload_tasks]
                concurrent.futures.wait(futures)

            logger.info("Files uploaded to AUDIO_ENDPOINT(s) for IVR processing.")
    for fileObj in processed_ivr_files:
            ip = fileObj['ip']
            lid_api_url  = ''
            for ivr_endpoint in lid_api_url_list:
                if ip == urlparse(ivr_endpoint).hostname:
                    lid_api_url = ivr_endpoint
                    break
            
            logger.info(f"Scheduling IVR processing for file: {fileObj['file']} with API URL: {lid_api_url}")
            file = fileObj['file']
            lid_tasks.append((os.path.basename(file), lid_api_url))
    logger.info(f"Total IVR URLs to process: {len(lid_api_url_list)}")
    logger.info(f"Total IVR tasks to process: {len(lid_tasks)}")
    # Process LID requests in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(lid_api_url_list) or 1) as executor:
        future_to_file = {executor.submit(process_ivr_file, file, lid_api_url): file for file, lid_api_url in lid_tasks}
        logger.info("Waiting for IVR processing to complete...")
        for future in concurrent.futures.as_completed(future_to_file):
            dict_result = future.result()
            if dict_result:
                ivr_results.append(dict_result)





    logger.info(f"SMB-IVR processing completed. Processed {len(processed_files)} files. Copied files to lid_audios ----- Done")
    return ivr_results

def delete_file_stt(file_name):
    url = f"{SPLIT_BASE_URL}/delete_file_stt"
    response = requests.post(url, json={"file_name": file_name})
    print("Delete:", response.status_code, response.json())

def is_container_running(service_name):
    url = f"{SPLIT_BASE_URL}/is_service_running"
    try:
        response = requests.post(url, json={"service_name": service_name})
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx, 5xx)

        data = response.json()

        # Parsing the values
        is_running = data.get("is_running", False)
        print(f"Service '{service_name}' running: {is_running}")

        # Use parsed value in logic
        if is_running:
            print("Service is currently running.")
        else:
            print("Service is NOT running.")

        return is_running

    except requests.exceptions.RequestException as e:
        print(f"HTTP request failed: {e}")
        return False
    except ValueError:
        print("Failed to parse JSON response.")
        return False


@app.route('/', methods=['GET'])
async def f(request):
  return json({'success': "App is working"})


# Webhook API to receive status, process_name, and machine_ip
@app.route('/webhook/status', methods=['POST'])
async def webhook_status(request):
    global WEBHOOK_STATUS
    try:
        data = request.json
        status = data.get('status')
        process_name = data.get('process_name')
        machine_ip = data.get('machine_ip')
        if not all([status, process_name, machine_ip]):
            return sanic_json({'error': 'Missing required parameters'}, status=400)
        # Save to global variable
        WEBHOOK_STATUS[machine_ip] = {
            'status': status,
            'process_name': process_name,
            'timestamp': datetime.utcnow().isoformat()
        }
        # Check if all machines with the same process_name have status "Done"
        all_done = True
        for info in WEBHOOK_STATUS.values():
            if info['process_name'] == process_name and info['status'] != "Done":
                all_done = False
                break
        if all_done:
            db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
             }
            logger.info(f"All machines for process '{process_name}' have status 'Done'")
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)

            cursor.execute("select *  from auditNexDb.batchStatus where currentBatch = 1")
            batch_status = cursor.fetchall()
            if len(batch_status) > 0:
                print("batch_status ->", batch_status[0])
                CURRENT_BATCH_STATUS = batch_status[0]

                current_date = batch_status[0]['batchDate']
                CURRENT_BATCH_ID = batch_status[0]['id']
                process_rule_engine_step_1_fill_audio_not_found(current_date,batch_status[0]['id'])
        else:
            logger.info(f"Not all machines for process '{process_name}' are 'Done'")

        return sanic_json({'message': 'Status received', 'data': WEBHOOK_STATUS[machine_ip]})
    except Exception as e:
        return sanic_json({'error': str(e)}, status=500)

def process_trade_metadata_range(firstIndex, lastIndex, batch_id, current_date):
    logger.info(f"Processing trade metadata from index {firstIndex} to {lastIndex} for batch {batch_id} on {current_date}")
    connection = mysql.connector.connect(
        host =os.environ.get('MYSQL_HOST'),
        user =os.environ.get('MYSQL_USER'),
        password =os.environ.get('MYSQL_PASSWORD'),
        database = os.environ.get('MYSQL_DATABASE'),
    )
    cursor = connection.cursor(dictionary=True,buffered=True)
    allFileNames = []
    cursor.execute("SELECT * FROM `call` WHERE batchId=%s", (batch_id,))
    all_call_rows = cursor.fetchall()
    for call_r in all_call_rows:
        if (call_r["lang"] != "en") and (call_r["lang"] != "hi") and (call_r["lang"] != "hinglish"):
            allFileNames.append(call_r['audioName'])

    cursor.execute("SELECT * FROM tradeMetadata WHERE mappingStatus = 'Pending' AND batchId = %s AND id >= %s AND id <= %s", (batch_id, firstIndex, lastIndex))
    all_metadata_trade = cursor.fetchall()
    for trade in all_metadata_trade:



        print("**********\n")

        trade['clientCode'] = str(trade['clientCode']).strip()
        print(trade['clientCode'])
        # trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_1(trade)
        trade_meta_data = {}
        nearest_call_meta = {}
        conversation_row = None
        result = {}

        alNumber = trade['alNumber']
        audio_file_name = ''
        process_call_id = ''
        trade_using_client = False
        if alNumber is None or alNumber == "":
            alNumber = trade['regNumber']
            print("**************START WITHOUT AL *********************** "+str(trade['id']))
            trade['clientCode'] = str(trade['clientCode']).strip()
            print(trade['clientCode'])
            trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_1(trade,batch_id,False)
            print(len(nearest_call_meta))
            if len(nearest_call_meta) == 0:
                print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id,False)
                print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
            trade_using_client = True
            print("**************END WITHOUT AL*********************** "+str(trade['id']))
        else:
            print("**************START WITHOUT CLIENT CODE*********************** "+str(trade['id']))
            trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_2(trade,batch_id,False)

            print("**************END WITHOUT CLIENT CODE*********************** "+str(trade['id']))
            print(len(nearest_call_meta))
            if len(nearest_call_meta) == 0:
                print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id,False)
                print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
        # print(str(conversation_row))
        print(str(nearest_call_meta))


        dataInserted = False
        rows_to_insert = []
        index = 0
        for call_meta in nearest_call_meta:

            if call_meta['sRecordingFileName'] not in allFileNames:

                if dataInserted == False:
                    dataInserted = True
                row = (
                    trade['id'],
                    trade['orderId'],
                    trade['clientCode'],
                    trade['regNumber'],
                    trade['alNumber'],
                    trade['tradeDate'],
                    trade['orderPlacedTime'],
                    trade['instType'],
                    trade['expiryDate'],
                    trade['optionType'],
                    trade['symbol'],
                    trade['comScriptCode'],
                    trade['scripName'],
                    trade['strikePrice'],
                    trade['tradeQuantity'],
                    trade['tradePrice'],
                    trade['tradeValue'],
                    trade['lotQty'],
                    result['tag1'],
                    call_meta['sRecordingFileName'],
                    trade['batchId']
                )
                rows_to_insert.append(row)

            index = index + 1
        if rows_to_insert:
            insert_query = """
                INSERT INTO tradeAudioMapping (
                    tradeMetadataId,
                    orderId,
                    clientCode,
                    regNumber,
                    alNumber,
                    tradeDate,
                    orderPlacedTime,
                    instType,
                    expiryDate,
                    optionType,
                    symbol,
                    comScriptCode,
                    scripName,
                    strikePrice,
                    tradeQuantity,
                    tradePrice,
                    tradeValue,
                    lotQty,
                    voiceRecordingConfirmations,
                    audioFileName,
                    batchId
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_query, rows_to_insert)
            connection.commit()
        if (result and result['tag1'] == 'No call record found'):
            try:

                update_query = """
                    UPDATE tradeMetadata
                    SET voiceRecordingConfirmations = %s

                    WHERE id = %s;
                """

                values = ('No call record found',trade['id'])
                cursor.execute(update_query, values)  # Execute query with parameters
                connection.commit()  # Commit changes

                print("Update completed successfully.")

            except mysql.connector.Error as err:
                print(f"Error: {err}")
                connection.rollback()  # Rollback the transaction in case of an error
        elif dataInserted == False and len(nearest_call_meta) > 0:
            try:

                update_query = """
                    UPDATE tradeMetadata
                    SET voiceRecordingConfirmations = %s, audioCallRef = %s, audioFileName = %s

                    WHERE id = %s;
                """
                referenceLink = ''
                for call_result_n in all_call_rows:
                    if call_result_n['audioName'] == nearest_call_meta[0]['sRecordingFileName']:
                        referenceLink = int(str(call_result_n["id"]))
                        break


                values = ('Unsupported Language',referenceLink,nearest_call_meta[0]['sRecordingFileName'],trade['id'])
                cursor.execute(update_query, values)  # Execute query with parameters
                connection.commit()  # Commit changes

                print("Update completed successfully.")

            except mysql.connector.Error as err:
                print(f"Error: {err}")
                connection.rollback()  # Rollback the transaction in case of an error

        # update_query = """
        # UPDATE tradeMetadata
        # SET mappingStatus = %s

        # WHERE id = %s;
        # """

        # values = ('Complete',trade['id'])
        # cursor.execute(update_query, values)  # Execute query with parameters
        # connection.commit()  #




    cursor.close()
    connection.close()

@app.route('/triagging_process_step1', methods=['GET'])
async def triagging_process_step1(request):
    try:
        firstIndex = int(request.args.get('firstIndex'))
        lastIndex = int(request.args.get('lastIndex'))
        batch_id = int(request.args.get('batch_id'))
        current_date = request.args.get('current_date')
    except Exception:
        return sanic_json({'error': 'Missing or invalid parameters'}, status=400)
    # Start background thread for processing
    thread = Thread(target=process_trade_metadata_range, args=(firstIndex, lastIndex, batch_id, current_date))
    thread.start()
    return sanic_json({'status': 'received successfully'})

@app.route('/api/v1/recognize_speech_file', methods=['POST'])
async def recognize_speech_file(request: Request):
    try:
        logger.info("/api/v1/recognize_speech_file")
        current_app = request.app
        request_data = request.json
        print('request data',request_data)
        audit_response_data = await current_app.loop.run_in_executor(executor,
                                                            lambda: api_wrapper.recognize_speech_file(request_data, ""))




        print ('Audit response',audit_response_data)
        return json(audit_response_data)
    except  Exception as e:
        print(e)


@app.post("/stop_container")
async def stop_container(request):
    try:
        data = request.json
        service_name = data.get("container_name")

        if not service_name:
            return response.json(
                {"error": "Missing container_name in request"},
                status=400
            )

        container = get_container_by_name(service_name)

        if container:
            container.stop()
            return response.json(
                {"status": "success", "message": f"Container '{container.name}' stopped"}
            )
        else:
            return response.json(
                {"status": "error", "message": f"No container found for {service_name}"},
                status=404
            )

    except Exception as e:
        return response.json(
            {"status": "error", "message": str(e)},
            status=500
        )

@app.post("/start_container")
async def start_container(request):
    try:
        data = request.json
        service_name = data.get("container_name")

        if not service_name:
            return response.json(
                {"error": "Missing container_name in request"},
                status=400
            )

        container = get_container_by_name(service_name)

        if container:
            container.start()
            print(f"Started service: {service_name}")
            return response.json(
                {"status": "success", "message": f"Container '{container.name}' started"}
            )
        else:
            print(f"Service {service_name} not found or not in network")
            return response.json(
                {"status": "error", "message": f"No container found for {service_name}"},
                status=404
            )

    except Exception as e:
        return response.json(
            {"status": "error", "message": str(e)},
            status=500
        )

@app.post("/upload_file_stt")
async def upload_file_stt(request: Request):
    data = request.json
    file_url = data.get("file_url")
    ivr_enabled = data.get("ivr_enabled",1)
    """
    source_base_path = os.environ.get('SOURCE')
    parts = file_url.split("/")
    date_str = parts[-2]      # '28-07-2025'
    filename = parts[-1]      # 'file2.wav'
    destination_base_path =  os.environ.get('STORAGE_PATH')
    destination_lid_path =  os.environ.get('DESTINATION_LID')
    src_folder = os.path.join(source_base_path, date_str)
    print(date_str, filename)
    """
    if not file_url:
        return json({"message": "file_url is required", "status": False}, status=400)

    try:
        """
        src_item_path = os.path.join(src_folder, filename)
        dest_item_path = os.path.join(destination_base_path, filename)
        dest_lid_path = os.path.join(destination_lid_path, filename)

        if os.path.isfile(src_item_path):
            if os.path.exists(dest_item_path):
                logger.info(f"Skipped (already exists): {dest_item_path}")

            else:
                shutil.copy2(src_item_path, dest_item_path)
                logger.info(f"Copied: {dest_item_path}")


            if os.path.exists(dest_lid_path):
                logger.info(f"Skipped LID (already exists): {dest_lid_path}")

            else:
                shutil.copy2(src_item_path, dest_lid_path)
                logger.info(f"Copied LID : {dest_lid_path}")
        """
        file_name = file_url.split("/")[-1]
        file_path = os.path.join(STT_FILE_DIR, file_name)
        file_path_lid = os.path.join(LID_FILE_DIR, file_name)
        dir_name = os.path.dirname(file_path)
        dir_name_lid = os.path.dirname(file_path_lid)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        if dir_name_lid:
            os.makedirs(dir_name_lid, exist_ok=True)
        # # Check if file already exists in both locations
        # if os.path.exists(file_path) and os.path.exists(file_path_lid):
        #     return json({"message": "File already exists", "status": True})

        print(file_url)
        print(file_path)
        logger.info(f"file_path: {file_path} file_path_lid: {file_path_lid}")
        response = requests.get(file_url)
        response.raise_for_status()

        with open(file_path, "wb") as f:
             f.write(response.content)
        if ivr_enabled == str(0) or ivr_enabled == 0:
            with open(file_path_lid, "wb") as f:
                f.write(response.content)

        return json({"message": "File uploaded successfully", "status": True})
    except Exception as e:
        return json({"message": f"Failed to upload file: {str(e)}", "status": False}, status=500)

def decrypt_aes256(encrypted_token, checksum):
    """
    Decrypts an AES-256 encrypted token using the given checksum as the key.
    :param encrypted_token: The Base64 encoded encrypted token.
    :param checksum: The checksum to be used as the decryption key.
    :return: The decrypted token as a string, or None if decryption fails.
    """
    try:
        # Ensure the decryption key is 32 bytes (AES-256 requirement)
        key = checksum.ljust(32, '0').encode()  # Pad with '0' if needed

        # Decode the Base64-encoded encrypted token
        encrypted_data = base64.b64decode(encrypted_token)

        # Extract the IV (first 16 bytes)
        iv = encrypted_data[:16]
        actual_encrypted_data = encrypted_data[16:]

        # Set up the AES cipher for decryption
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Decrypt the data
        decrypted_data = decryptor.update(actual_encrypted_data) + decryptor.finalize()

        # Strip any padding (null bytes) and decode to UTF-8
        return decrypted_data.rstrip(b'\0').decode('utf-8', errors='replace')

    except UnicodeDecodeError as e:
        print(f"UnicodeDecodeError: {e}")
        print(f"Decrypted bytes (raw): {decrypted_data}")
        return None
    except Exception as e:
        print(f"Error decrypting token: {e}")
        return None

@app.post("/sync-data")
async def sync_data(request: Request):
    """
    Adds session data to the local Session table.
    """
    # Extract request data
    data = request.json
    license_id = data.get("licenseId")
    hours_completed = data.get("hoursCompleted")
    token = data.get("token")
    cpu = data.get("cpu", "")
    memory = data.get("memory", "")
    diskspace = data.get("diskspace", "")
    logger.info("******////*******")
    # Validate input
    if not license_id or hours_completed is None:
        return response.json({"error": "licenseId and hoursCompleted are required"}, status=400)
    logger.info(license_base_url)
    try:
        # Store session data locally
        print(1)
        client.store_data_locally(license_id, hours_completed, token,"",0,"","","",{'peak_cpu':cpu,'peak_memory':memory,'lowest_disk_space':diskspace})
        print(1)
        return json({"message": "Session data added successfully"})
    except Exception as e:
        return response.json({"error": f"Failed to add session data: {str(e)}"}, status=500)

@app.post("/check-license")
async def check_license(request: Request):
    """
    Checks if the provided token license is valid or not.
    """
    # data = request.json
    # token = data.get("token")
    # checksum = data.get("checksum")

    # if not token or not checksum:
    #     return response.json({"error": "token and checksum are required"}, status=400)

    # try:
    #     # Check license validity using the client SDK
    #     result = client.check_license_local(token, checksum)
    #     return response.json(result)
    # except Exception as e:
    #     return response.json({"error": f"Failed to check license: {str(e)}"}, status=500)
    data = request.json
    encrypted_token = data.get("token", "")
    checksum = data.get("checksum", "ABCD1234EF567890")

    logger.info(encrypted_token)
    logger.info(checksum)
    logger.info("Check license --------------------")
    try:
        # Decrypt the token

        decrypted_data = decrypt_aes256(encrypted_token, checksum)
        logger.info(decrypted_data)
        result = client.check_license_local(decrypted_data,encrypted_token)
        logger.info(result)
        # Return the decrypted data
        return json(result)
    except Exception as e:
        logger.info(str(e))
        # Handle decryption errors
        return response.json({"error": f"Failed to check license: {str(e)}"}, status=500)

@app.get("/auditnex-check-licenses")
async def check_licenses(request: Request):
    """
    Checks if the provided token license is valid or not.
    """

    logger.info("Check license --------------------")
    allLicenses = []
    try:
        # Decrypt the token
        allLicenses = client.fetch_all_local_licenses()
        index = 0
        for lic in allLicenses:
            decrypted_data = decrypt_aes256(lic['token'], "ABCD1234EF567890")
            logger.info(decrypted_data)
            result = client.check_license_local(decrypted_data,lic['token'])
            allLicenses[index]['isValid'] = result['isValid']
            allLicenses[index]['message'] = result['message']
            logger.info(result)
            index = index + 1
        # Return the decrypted data
        return json(allLicenses)
    except Exception as e:
        logger.info(str(e))
        # Handle decryption errors
        return response.json({"error": f"Failed to check license: {str(e)}"}, status=500)

@app.post("/auditnex-update-users")
async def auditnex_update_users(request: Request):
    data = request.json
    users = data.get('users')
    auditnex_process_id = data.get('auditnex_process_id')
    url = f"{license_base_url}/update_users"
    try:
        # Decrypt the token
        allLicenses = client.fetch_all_local_licenses()
        index = 0
        for lic in allLicenses:
            decrypted_data = decrypt_aes256(lic['token'], "ABCD1234EF567890")
            logger.info(decrypted_data)
            result = client.check_license_local(decrypted_data,lic['token'])
            allLicenses[index]['isValid'] = result['isValid']
            allLicenses[index]['message'] = result['message']
            logger.info(result)

            if allLicenses[index]['auditnex_process_id'] == auditnex_process_id:
                if allLicenses[index]['isValid'] == False:
                    return json({'isValid': False, 'auditnex_process_id': auditnex_process_id ,'message': 'License expired'})
                else:
                    payload = { 'users': users, 'auditnex_process_id': auditnex_process_id }
                    response2 = requests.post(url, json=payload)
                    logger.info(str(response2.json()))
                    return json(response2.json())
            index = index + 1
        # Return the decrypted data

    except Exception as e:
        logger.info(str(e))
        # Handle decryption errors
        return response.json({"error": f"Failed to check license: {str(e)}"}, status=500)




def update_instance_count(change, increment=True):
    """
    Update the no_of_instance count by incrementing or decrementing.
    :param change: Amount to increment or decrement.
    :param increment: Boolean, True to increment, False to decrement.
    :return: JSON response with updated instance count or error message.
    """
    try:
        connection = mysql.connector.connect(
                        host = license_db_url,
                        port=os.environ.get('MYSQL_PORT'),
                        user = os.environ.get('MYSQL_USER'),
                        password =os.environ.get('MYSQL_PASSWORD'),
                        database='licenseDb',
                        connection_timeout= 86400000
                        )
        if connection.is_connected():
            cursor = connection.cursor()

            # Fetch current instance count
            cursor.execute("SELECT no_of_instance FROM session_info WHERE id = 1")
            current_count = cursor.fetchone()[0]

            # Calculate new instance count
            new_count = current_count + change if increment else max(0, current_count - change)

            # Update the instance count in the database
            cursor.execute("UPDATE session_info SET no_of_instance = %s WHERE id = 1", (new_count,))
            connection.commit()
            return {"status": "success", "no_of_instance": new_count}

    except mysql.connector.Error as err:
        return {"status": "error", "message": f"Database error: {err}"}

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.post("/increment-instance")
async def increment_instance(request: Request):
    """
    Increment the no_of_instance by a given or default value (1).
    """
    change = int(request.json.get("value", 1))  # Default to 1 if no value is provided
    result = update_instance_count(change, increment=True)
    return json(result)

@app.post("/api/increment-instance")
async def increment_instance(request: Request):
    """
    Increment the no_of_instance by a given or default value (1).
    """
    change = int(request.json.get("value", 1))  # Default to 1 if no value is provided
    result = update_instance_count(change, increment=True)
    return json(result)

def decrypt_client_data(encrypted_data):
    decrypted_data = cipher_client.decrypt(encrypted_data.encode()).decode()
    client_name, client_code = decrypted_data.split("|")
    return {"clientName": client_name, "clientCode": client_code}

@app.get("/api/auditnex-client-info")
async def get_client_info(request: Request):
    details = decrypt_client_data(os.environ.get('client_access_key'))

    return json(details)

@app.post("/api/sync_new_process_callback")
async def sync_new_process_callback(request: Request):
    data = request.json
    # client_key = data.get('client_access_key')
    process_name = data.get('process_name')
    auditnex_process_id = data.get('auditnex_process_id')
    # instance_id = data.get('instance_id')
    url = f"{license_base_url}/sync_new_process_callback"
    payload = { 'client_access_key': os.environ.get('client_access_key'), 'process_name': process_name,'instance_id': os.environ.get('INSTANCE_ID'),'auditnex_process_id': auditnex_process_id }
    response2 = requests.post(url, json=payload)
    logger.info(str(response2.json()))
    return json(response2.json())


def get_no_instance():
    """
    Fetches the no_instance value from the session_info table where id = 1.
    :return: The no_instance value if found, None otherwise.
    """
    try:
        connection = mysql.connector.connect(
                        host = license_db_url,
                        port=os.environ.get('MYSQL_PORT'),
                        user = os.environ.get('MYSQL_USER'),
                        password =os.environ.get('MYSQL_PASSWORD'),
                        database='licenseDb',
                        connection_timeout= 86400000
                        )
        if connection.is_connected():
            cursor = connection.cursor()
            query = "SELECT no_of_instance FROM session_info WHERE id = %s"
            cursor.execute(query, (1,))
            result = cursor.fetchone()
            return result[0] if result else None

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def insert_session():
    global client
    """
    Inserts a new record into the session table with specified data.
    Fetches no_instance from session_info table where id = 1.

    :param no_user: Number of users.
    :param instance_id: ID of the instance.
    :param token: Token associated with the session.
    :return: True if insertion is successful, False otherwise.
    """
    # no_instance = get_no_instance()  # Fetch no_instance from session_info
    # if no_instance is None:
    #     logger.info("Failed to retrieve no_instance value from session_info.")
    #     return False

    try:
        # Connect to the database
        connection = mysql.connector.connect(
                        host = license_db_url,
                        port=os.environ.get('MYSQL_PORT'),
                        user = os.environ.get('MYSQL_USER'),
                        password =os.environ.get('MYSQL_PASSWORD'),
                        database='licenseDb',
                        connection_timeout= 86400000
                        )
        if connection.is_connected():
            allLicenses = client.get_local_license_key()
            for lic in allLicenses:
                logger.info('syncing for ...'+str(lic['token']))
                client.sync_token_update_periodically(lic['token'])
                cursor = connection.cursor()
                check_license_response = client.check_license(
                token=lic['token'],
                instance_id=os.environ.get('INSTANCE_ID')
                )
                message = ''
                if check_license_response and  'isValid' in check_license_response and check_license_response['isValid'] == False:
                    message = "License has been expired"
                # SQL query to insert a new session record
                query = """
                    INSERT INTO session (no_instance, no_user, hoursCompleted, instanceId, synced, token, message)
                    VALUES (%s, %s, 0, %s, 0, %s, %s)
                """
                # Execute the query with the fetched no_instance value and other provided values
                no_instance = get_no_instance()
                cursor.execute(query, (no_instance, 1, os.environ.get('INSTANCE_ID'), lic['token'],message))
                connection.commit()
                print("Data inserted successfully into the session table.")
            cursor.close()
            connection.close()
            return True

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/v1/recognize_speech_file_v3', methods=['POST'])
async def recognize_speech_file_v3(request: Request):
    try: 
        logger.info("/api/v1/recognize_speech_file_v3")
        logger.info('0')
        current_app = request.app
        request_data = request.json
        logger.info('request data'+str(request_data))
        
        logger.info('1')
        if 'files' in request_data:
            request_data['multiple'] = True
            logger.info('2')
            index = 0
            for f in request_data['files']:
                if index == 0:
                    request_data['index'] = index
                parsed = urlparse(f)
                request_data['files'][index] = {"audioUrl": f, "fileName": os.path.basename(parsed.path)}
                request_data['audio_uri'] = f
                request_data['file_name'] = os.path.basename(parsed.path)
                index = index + 1
            result = api_wrapper.insert_into_db_step_1_v5(request_data)
            return json({"status": "success", "message": "Audit in Progresss","expected_audit_time": "1 minute"})
        else:
            index = 0
            request_data['index'] = index
            result = api_wrapper.insert_into_db_step_1_v5(request_data)
            # await request_queue.put(request)
            if REQUEST_IN_PROGRESS == False:
                time.sleep(5)
                
                # audit_response_data = await current_app.loop.run_in_executor(executor,
                #                                             lambda: check_pending_req())
            return json({"status": "success", "message": "Audit in Progresss","expected_audit_time": "1 minute"})
            # audit_response_data = await current_app.loop.run_in_executor(executor,
            #                                                 lambda: api_wrapper.recognize_speech_file_v2(request_data, ""))
        # print ('Audit response',audit_response_data)
        # await request_queue.put(request)
        
        # return json({"status": "success", "message": "Audit in Progresss","expected_audit_time": "1 minute"})
        # print ('Audit response',audit_response_data)
        # return json(audit_response_data)
        
    except  Exception as e:
        logger.info(str(e))

@app.route('/api/v1/recognize_speech_file_v2', methods=['POST'])
async def recognize_speech_file_v2(request: Request):
    global REQUEST_IN_PROGRESS
    try:
        logger.info("/api/v1/recognize_speech_file_v2")
        current_app = request.app
        request_data = request.json
        logger.info('request data'+str(request_data))


        if 'files' in request_data:
            request_data['multiple'] = True

            index = 0
            for f in request_data['files']:
                request_data['index'] = index
                request_data['audio_uri'] = f['audioUrl']
                request_data['file_name'] = f['fileName']
                request_data['audioDuration'] = f['audioDuration']
                request_data['ip'] = request_data['ip']
                if index == 0:
                    result = api_wrapper.insert_into_db_step_1(request_data)




                index = index + 1
                if index == len(request_data['files']):
                    if REQUEST_IN_PROGRESS == False:
                        time.sleep(5)


                    return json({"status": "success", "message": "Audit in Progresss","expected_audit_time": "1 minute"})
        else:
            index = 0
            request_data['index'] = index
            result = api_wrapper.insert_into_db_step_1(request_data)

            if REQUEST_IN_PROGRESS == False:
                time.sleep(5)



            return json({"status": "success", "message": "Audit in Progresss","expected_audit_time": "1 minute"})









    except  Exception as e:
        logger.info(str(e))

async def process_reaudit(results):
    dataBase2 = mysql.connector.connect(
    host =os.environ.get('MYSQL_HOST'),
    user =os.environ.get('MYSQL_USER'),
    password =os.environ.get('MYSQL_PASSWORD'),
    database = os.environ.get('MYSQL_DATABASE'),
    connection_timeout= 86400000
    )
    cursorObject = dataBase2.cursor(buffered=True)

    for row1 in results:

        sql_query = "select * from `transcript` where callId = "+ str(row1[0])
        cursorObject.execute(sql_query)
        call_results = cursorObject.fetchall()
        transcript_for_nlp = ""
        for row in call_results:
            transcript_for_nlp = transcript_for_nlp + ' ' + 'start_time: '+ str(row[3]) + ' ' + row[5] +':' + ' ' + row[6] + ' ' + 'end_time: '+str(row[4]) + '\\n'

        nlp_request_data = {
            "call_id": row1[0],
            "audit_form_id": row1[2],
            "process_id": row1[1],
            "audio_language": row1[22],
            "file_name": row1[8],
            "trnascript_for_nlp": transcript_for_nlp
        }
        print("nlp request data -> ", nlp_request_data)
        api_wrapper.reaudit_file(nlp_request_data)
        await asyncio.sleep(10)


@app.route('/api/v1/reaudit', methods=['POST'])
async def reaudit(request: Request):
    try:
        logger.info("/api/v1/reaudit")
        request_data = request.json
        logger.info('request data -> '+str(request_data))

        if 'auditFormId' in request_data:
            audit_form_id = request_data["auditFormId"]
            dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject = dataBase2.cursor(buffered=True)

            sql_query = "select * from `call` where status = %s and auditFormId = %s"

            status = ('TranscriptDone',audit_form_id)

            cursorObject.execute(sql_query, status)
            results = cursorObject.fetchall()
            if len(results) == 0:
                return json({"status": "fail", "message": "audit form id is invalid. please pass valid audit form id"})
            else:
                reaudit_files_count = len(results)

                asyncio.create_task(process_reaudit(results))


                return json(
                    {
                        "success": 1,
                        "status": 200,
                        "title": "",
                        "message": "Call re-auditing started",
                        "data": {
                            "reAudited": reaudit_files_count,
                        }
                    }
                )























        else:
            return json({"status": "fail", "message": "please share valid audit form id"})
    except Exception as e:
        logger.info(str(e))

@app.route('/api/v1/audio_file_duration', methods=['POST'])
async def recognize_speech_file(request: Request):
    try:
        logger.info("/api/v1/audio_file_duration")
        current_app = request.app
        request_data = request.json
        print('request data',request_data)
        audit_response_data = await current_app.loop.run_in_executor(executor,
                                                            lambda: api_wrapper.audio_file_duration(request_data, ""))




        print ('Audit response',audit_response_data)
        return json(audit_response_data)
    except  Exception as e:
        print(e)


@app.route('/api/v1/stt', methods=['POST'])
async def trigger_stt(request: Request):
    try:
        logger.info("/api/v1/stt")
        current_app = request.app
        request_data = request.json
        print('request data',request_data)
        audit_response_data = await current_app.loop.run_in_executor(executor,
                                                            lambda: api_wrapper.recognize_speech_file_v2(request_data, ""))




        print ('Audit response',audit_response_data)
        return json(audit_response_data)
    except  Exception as e:
        print(e)

def safe_value(value):
    """Replace NaN values with None."""
    if pd.isna(value) or value == "":
        return None

    return value

def process_file(file_path, template_file, metadata_filename):
    try:

        file_name = os.path.splitext(os.path.basename(file_path))[0]


        config_defination = {}
        with open(template_file, 'r') as f:
            config_defination = jsn.load(f)

        columns_to_extract = config_defination.get(str(metadata_filename), [])

        primary_key = config_defination.get("primary_key", None)


        file_extension = os.path.splitext(file_path)[-1].lower()



        if file_extension == '.csv':
            logger.info("1")
            data = pd.read_csv(file_path, usecols=lambda x: x.strip() in [col.strip() for col in columns_to_extract])
            logger.info("2")
            data.columns = data.columns.str.rstrip()
            logger.info("3")
            data = data.applymap(lambda x: x.strip() if isinstance(x, str) else x)
            logger.info("4")
            data = data.replace("NULL", pd.NA).fillna("")
            logger.info("5")

            data = data[~data.apply(lambda row: row.astype(str).str.contains("----", na=False)).any(axis=1)]
            logger.info("6")

        elif file_extension in ['.xls', '.xlsx']:

            data = pd.read_excel(file_path, usecols=columns_to_extract)
        else:
            raise ValueError("Unsupported file format. Only .csv, .xls, and .xlsx files are supported.")


        if primary_key and primary_key not in columns_to_extract:
            raise ValueError(f"Primary key '{primary_key}' is not in the list of columns to extract.")


        if primary_key:
            grouped_data = data.groupby(primary_key).apply(lambda x: x.to_dict(orient="records")).to_dict()
        else:

            grouped_data = data.to_dict(orient="records")




        return grouped_data
    except  Exception as e:
        logger.info(str(e))

def convert_date_format(date_str):
    logger.info("kotak--"+str(date_str))
    try:

        dt = datetime.strptime(date_str, "%m/%d/%Y %I:%M:%S %p")


        formatted_date = dt.strftime("%d-%m-%Y %H:%M:%S")

        return formatted_date
    except ValueError:
        return "Invalid date format"

def ensure_seconds(date_str: str) -> str:
    try:
        # Try parsing without seconds (dd-mm-yyyy HH:MM)
        date_obj = datetime.strptime(date_str, "%d-%m-%Y %H:%M")
        # Format to include seconds
        logger.info("1")
        return date_obj.strftime("%d-%m-%Y %H:%M:%S")
    except ValueError:
        try:
            logger.info("2")
            # Try parsing with seconds (already correct format)
            date_obj = datetime.strptime(date_str, "%d-%m-%Y %H:%M:%S")
            # Return as is (or reformat to ensure consistency)
            return date_obj.strftime("%d-%m-%Y %H:%M:%S")
        except ValueError:
            try:
                # Try parsing without seconds (dd-mm-yyyy HH:MM)
                date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                # Format to include seconds
                logger.info("3")
                return date_obj.strftime("%d-%m-%Y %H:%M:%S")
            except ValueError:
            # Invalid format given
                try:
                    logger.info("4")
                # Try parsing with seconds (already correct format)
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d  %H:%M:%S")
                    # Return as is (or reformat to ensure consistency)
                    return date_obj.strftime("%d-%m-%Y %H:%M:%S")
                except ValueError:
                    logger.info("5")
                    raise ValueError(f"Invalid date format: {date_str}")

def normalize_to_int_string(value):
    if value is None or value == "":
        return ""
    try:
        # If it's a string, convert to float first (to handle "123.0")
        if isinstance(value, str):
            value = float(value)
        # Convert to int (truncates if float), then to string
        return str(int(value))
    except (ValueError, TypeError):
        raise ValueError(f"Cannot normalize value to integer string: {value}")

def insert_data_into_database(grouped_data, file_name, template_file, batch_size=1000):
    connection = None
    try:
        connection = mysql.connector.connect(
            host=os.environ.get('MYSQL_HOST'),
            user=os.environ.get('MYSQL_USER'),
            password=os.environ.get('MYSQL_PASSWORD'),
            database=os.environ.get('MYSQL_DATABASE'),
        )
        cursor = connection.cursor(buffered=True)
        with open(template_file, 'r') as f:
            config = jsn.load(f)

        column_mapping_call = config.get(str(file_name) + "_mapping", [])
        column_mapping_call_default = config.get("column_mapping_call_default", [])
        cursor.execute("select * from auditNexDb.batchStatus where currentBatch = 1")
        batch_status = cursor.fetchone()

        # Prepare batch data
        batch_data = []
        all_columns = None

        for record in grouped_data:
            call_columns = []
            call_values = []

            for json_key, db_column in column_mapping_call.items():
                json_key = json_key.strip()

                if json_key == 'orderid':
                    order_id_value = safe_value(record.get(json_key))
                    call_values.append(str(order_id_value))
                    call_columns.append(db_column)
                elif json_key == 'al_number':
                    # logger.info('al_number--'+str(record.get(json_key)))
                    al_number_value = safe_value(record.get(json_key))
                    call_values.append(normalize_to_int_string(al_number_value))
                    call_columns.append(db_column)
                elif json_key == 'reg_number':
                    # logger.info('reg_number--'+str(record.get(json_key)))
                    reg_number_value = safe_value(record.get(json_key))
                    call_values.append(normalize_to_int_string(reg_number_value))
                    call_columns.append(db_column)
                elif json_key == 'nIsAdd' and (record.get(json_key) == "" or isinstance(record.get(json_key), str)):
                    call_values.append(0)
                    call_columns.append(db_column)
                elif json_key == 'nCallStatus' and record.get(json_key) == "":
                    call_values.append(0)
                    call_columns.append(db_column)
                elif json_key == 'nCallType' and record.get(json_key) == "":
                    call_values.append(0)
                    call_columns.append(db_column)
                elif json_key == 'nCallCount' and record.get(json_key) == "":
                    call_values.append(0)
                    call_columns.append(db_column)
                elif json_key == 'dCallStartTime':
                    if 'nan' not in str(record.get(json_key)) and ('/' in str(record.get(json_key)) or '-' in str(record.get(json_key))):
                        dCallStartTime = str(record.get(json_key))

                        if '/' in str(record.get(json_key)):
                            logger.info('chaning')
                            dCallStartTime = convert_date_format(str(record.get(json_key)))

                        dCallStartTime = ensure_seconds(str(record.get(json_key)))
                        date_part, time_part = dCallStartTime.split(" ")
                        call_values.append(str(date_part))
                        call_columns.append('callStartDate')
                        call_values.append(str(time_part))
                        call_columns.append('callStartTime')
                        logger.info('kotak1--'+str(record.get(json_key)))

                        call_values.append(safe_value(record.get(json_key)))
                        call_columns.append(db_column)
                    else:
                        call_values.append("")
                        call_columns.append('callStartDate')
                        call_values.append("")
                        call_columns.append('callStartTime')
                        call_values.append(safe_value(record.get(json_key)))
                        call_columns.append(db_column)
                elif json_key == 'dCallEndTime' and record.get(json_key) is not 'None' and (record.get(json_key) is not None and str(record.get(json_key)) != "") and ('/' in str(record.get(json_key)) or '-' in str(record.get(json_key))):
                    dCallEndTime = str(record.get(json_key))
                    if '/' in str(record.get(json_key)):
                        dCallEndTime = convert_date_format(str(record.get(json_key)))

                    dCallEndTime = ensure_seconds(str(record.get(json_key)))
                    date_part, time_part = dCallEndTime.split(" ")
                    call_values.append(str(date_part))
                    call_columns.append('callEndDate')
                    call_values.append(str(time_part))
                    call_columns.append('callEndTime')
                    call_values.append(safe_value(record.get(json_key)))
                    call_columns.append(db_column)
                else:
                    if json_key == 'dCallEndTime':
                        call_values.append("")
                        call_columns.append('callEndDate')
                        call_values.append("")
                        call_columns.append('callEndTime')
                    call_values.append(safe_value(record.get(json_key)))
                    call_columns.append(db_column)

            # Add batchId
            call_values.append(str(batch_status[0]))
            call_columns.append('batchId')

            # Store column order from first record
            if all_columns is None:
                all_columns = call_columns.copy()

            # Add to batch
            batch_data.append(tuple(call_values))

            # Execute batch when batch_size is reached
            if len(batch_data) >= batch_size:
                _execute_batch_insert(cursor, file_name, all_columns, batch_data)
                connection.commit()
                batch_data = []
                logger.info(f"Inserted batch of {batch_size} records")

        # Insert remaining records
        if batch_data:
            _execute_batch_insert(cursor, file_name, all_columns, batch_data)
            connection.commit()
            logger.info(f"Inserted final batch of {len(batch_data)} records")

        print("Data successfully inserted into the database using batch insertion.")

    except Exception as error:
        logger.info(f"Error: {error}")
        if connection:
            connection.rollback()  # Rollback in case of an error
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")


def _execute_batch_insert(cursor, table_name, columns, batch_data):
    """Helper function to execute batch insert"""
    if not batch_data:
        return

    placeholders = ', '.join(['%s'] * len(columns))
    query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    cursor.executemany(query, batch_data)


def get_combined_text_from_call(call_table_callId):
    try:

        connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
        cursor = connection.cursor(buffered=True)


        query = """
            SELECT GROUP_CONCAT(t.text SEPARATOR ' ') AS combined_text
            FROM transcript t
            JOIN `call` c ON t.callId = c.id
            WHERE c.callI d = %s;
        """
        cursor.execute(query, (call_table_callId,))
        result = cursor.fetchone()

        if result and result[0]:
            return result[0]  # Return the combined text
        else:
            return "No text found for the given callId."

    except mysql.connector.Error as error:
        print(f"Error: {error}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL connection closed.")


def replace_empty_with_none(json_data):
    for record in json_data:
        for key, value in record.items():
            if value == "":
                record[key] = None
    return json_data


def process_data(json_data, mandatory_fields):

    invalid_records = []

    for record in json_data:

        for field in mandatory_fields:
            if field not in record or not record[field] or record[field] == None:
                invalid_records.append(record)
                break


        for key, value in record.items():
            if value == "":
                record[key] = None

    return json_data, invalid_records

@app.route('/api/v1/insert_transcript', methods=['POST'])
async def insert_transcript(request: Request):

    try:
        db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
        }

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        request_data = request.json
        print("request from script reached")

        for item in request_data:
            print("callId ->", item["callId"])
            add_column = ("INSERT INTO auditNexDb.transcript (callId, languageId, startTime, endTime, speaker, text, rateOfSpeech, confidence)"
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")
            add_result = (int(item["callId"]),int(item["languageId"]), float(item["startTime"]),float(item["endTime"]),item["speaker"],item["text"],"Good",float(90.0))
            cursor.execute(add_column, add_result)
            conn.commit()

        cursor.close()
        conn.close()
        return json({'status': True,'message': 'Data uploaded successfully'})

    except Exception as e:
        print(e)
        return json({'status': False,'message': 'something went wrong and data is not inserted'})

@app.route('/api/v1/upload_trademetadata', methods=['POST'])
async def upload_trademetadata(request: Request):
    try:
        logger.info("/api/v1/upload_trademetadata")
        current_app = request.app

        template_file = os.environ.get('API_DEFINATIONS_FILE')
        if request.files:
            uploaded_file = request.files.get('file')
            if uploaded_file:
                logger.info("Found trade metadata file")
                with open(os.environ.get('STORAGE_PATH')+uploaded_file.name, 'wb') as f:
                    f.write(uploaded_file.body)
                    f.close()
                    logger.info("upload done")
                    logger.info(str(os.environ.get('STORAGE_PATH')+uploaded_file.name))
                    grouped_data = process_file(os.environ.get('STORAGE_PATH')+uploaded_file.name, template_file,os.environ.get('TRADEMETAFILENAME'))
                    file_name = os.path.splitext(os.path.basename(uploaded_file.name))[0]
                    logger.info(str(file_name))
                    insert_data_into_database(grouped_data,os.environ.get('TRADEMETAFILENAME'),template_file)
                    logger.info("data inserted 1")
        logger.info(0)
        logger.info(str(request.content_type))
        if request.content_type == "application/json" and request.json:
            logger.info(1)
            request_data = request.json
            logger.info(2)
            logger.info(str(request_data))
            mandatory_fields = []
            if 'data' in request_data:
                processed_data = replace_empty_with_none(request_data['data'])
                logger.info(str(processed_data))
                processed_data, invalid_records = process_data(processed_data, mandatory_fields)
                insert_data_into_database(processed_data,os.environ.get('TRADEMETAFILENAME'),template_file)
                logger.info("json data inserted")
        logger.info(3)
        return json({'status': True,'message': 'Data uploaded successfully'})
    except  Exception as e:
        logger.info(str(e))

@app.route('/api/v1/upload_callmetadata', methods=['POST'])
async def upload_callmetadata(request: Request):
    try:
        logger.info("/api/v1/upload_callmetadata")
        current_app = request.app

        template_file = str(os.environ.get('API_DEFINATIONS_FILE'))
        logger.info(template_file)
        if request.files:
            uploaded_file = request.files.get('file')
            if uploaded_file:
                logger.info("Found call metadata file")
                with open(os.environ.get('STORAGE_PATH')+uploaded_file.name, 'wb') as f:
                    f.write(uploaded_file.body)
                    f.close()
                    logger.info("upload done")
                    logger.info(str(os.environ.get('STORAGE_PATH')+uploaded_file.name))
                    grouped_data = process_file(os.environ.get('STORAGE_PATH')+uploaded_file.name, template_file,os.environ.get('CALLMETAFILENAME'))
                    file_name = os.path.splitext(os.path.basename(uploaded_file.name))[0]
                    insert_data_into_database(grouped_data,os.environ.get('CALLMETAFILENAME'),template_file)
                    logger.info("data inserted")
        logger.info(str(request.content_type))
        if request.content_type == "application/json" and request.json:
            request_data = request.json
            logger.info('request data',request_data)
            mandatory_fields = ["clientCode"]
            if 'data' in request_data:
                processed_data = replace_empty_with_none(request_data['data'])
                processed_data, invalid_records = process_data(processed_data, mandatory_fields)
                insert_data_into_database(processed_data,os.environ.get('CALLMETAFILENAME'),template_file)
                logger.info("json data inserted")
        return json({'status': True,'message': 'Data uploaded successfully'})
    except  Exception as e:
        print(e)

async def worker():
    while True:
        try:
            request = await request_queue.get()

            print('worker ==> ')
            response = await process_request(request)
            print(f"Processed request: {request}")
            request_queue.task_done()
        except  Exception as e:
            print(e)

async def process_request(request: Request):
    try:
        await asyncio.sleep(2)
        return text(f"Processed request: {request}")
    except  Exception as e:
        print(e)









@app.route('/api/v1/translate', methods=['POST'])
async def translate_data(request: Request):
    global translate_queue

    try:
        logger.info("/api/v1/translate")
        current_app = request.app
        request_data = request.json



        request_type = request_data["type"]
        file_name = request_data["fileName"]
        dataBase312 = mysql.connector.connect(
        host =os.environ.get('MYSQL_HOST'),
        user =os.environ.get('MYSQL_USER'),
        password =os.environ.get('MYSQL_PASSWORD'),
        database = os.environ.get('MYSQL_DATABASE'),
        connection_timeout= 86400000
        )
        cursorObject312 = dataBase312.cursor(dictionary=True,buffered=True)
        cursorObject312.execute("select * from auditNexDb.batchStatus where currentBatch = 1")
        savedBatchResult = cursorObject312.fetchone()
        if savedBatchResult and ((savedBatchResult['sttStatus'] == 'Complete' and savedBatchResult['auditStatus'] == 'Complete' and savedBatchResult['remarks'] == 'Complete') or (savedBatchResult['sttStatus'] == 'Pending' and savedBatchResult['auditStatus'] == 'Pending' and savedBatchResult['remarks'] == 'Pending')):
            if request_type == 'translation':
                update_query = """
                                UPDATE auditNexDb.call
                                SET translationStatus = %s
                                WHERE audioName = %s
                                """

                new_value = "In Progress"
                condition_value = str(file_name)
                cursorObject312.execute(update_query, (new_value,condition_value))
                dataBase312.commit()

            if request_type == 'transliteration':
                update_query = """
                                UPDATE auditNexDb.call
                                SET transliterationStatus = %s
                                WHERE audioName = %s
                                """

                new_value = "In Progress"
                condition_value = str(file_name)
                cursorObject312.execute(update_query, (new_value,condition_value))
                dataBase312.commit()
            container_status = is_service_running('auditnex-translate-1')
            if container_status == False:
                start_service('auditnex-translate-1')
                time.sleep(120)
            result = api_wrapper.translate(request_data)
            return json(result)
        else:
            translate_queue.append(request_data)
            if request_type == 'translation':
                update_query = """
                                UPDATE auditNexDb.call
                                SET translationStatus = %s
                                WHERE audioName = %s
                                """

                new_value = "In Progress"
                condition_value = str(file_name)
                cursorObject312.execute(update_query, (new_value,condition_value))
                dataBase312.commit()

            if request_type == 'transliteration':
                update_query = """
                                UPDATE auditNexDb.call
                                SET transliterationStatus = %s
                                WHERE audioName = %s
                                """

                new_value = "In Progress"
                condition_value = str(file_name)
                cursorObject312.execute(update_query, (new_value,condition_value))
                dataBase312.commit()

        time.sleep(1)

        dataBase312.close()


    except  Exception as e:
        print(e)
def check_pending_req():
    global REQUEST_IN_PROGRESS, INSTANCE_TYPE
    global REQUEST_IN_PROGRESS_AUDIT
    global translate_queue
    global CURRENT_BATCH_ID
    machine_ip = os.environ.get('MACHINE_IP')
    logger.info("checking pending request")
    logger.info(CURRENT_BATCH_ID)
    logger.info("kotak- checking rest 0")
    logger.info("kotak "+str(CURRENT_BATCH_STATUS))
    logger.info(" "+str(REQUEST_IN_PROGRESS)+" "+str(REQUEST_IN_PROGRESS_AUDIT))
    if CURRENT_BATCH_STATUS and CURRENT_BATCH_STATUS['sttStatus'] != "InProgress":
        return
    if REQUEST_IN_PROGRESS and REQUEST_IN_PROGRESS == True:
        return
    if REQUEST_IN_PROGRESS_AUDIT and REQUEST_IN_PROGRESS_AUDIT == True:
        return
    if CURRENT_BATCH_ID is None:
        return

    try:
        REQUEST_IN_PROGRESS = True
        dataBase3 = mysql.connector.connect(
        host =os.environ.get('MYSQL_HOST'),
        user =os.environ.get('MYSQL_USER'),
        password =os.environ.get('MYSQL_PASSWORD'),
        database = os.environ.get('MYSQL_DATABASE'),
        connection_timeout= 86400000
        )
        cursorObject3 = dataBase3.cursor(buffered=True)
        savedCallResult = None
        cursorObject3.execute(
            "SELECT * FROM auditNexDb.call c WHERE status = 'Pending' AND batchId = %s AND ip = %s"
            "AND EXISTS (SELECT 1 FROM auditNexDb.tradeAudioMapping t WHERE c.audioName = t.audioFileName) ",
            (CURRENT_BATCH_ID, machine_ip,)
        )
        logger.info("kotak- checking rest 0-1")

        savedCallResult = cursorObject3.fetchone()
        if not savedCallResult :
            cursorObject3.execute(
                "SELECT * FROM auditNexDb.call c WHERE status = 'Pending' AND batchId = %s AND ip = %s ",
                (CURRENT_BATCH_ID, machine_ip,)
            )
            logger.info("kotak- checking rest 0-11")
            savedCallResult = cursorObject3.fetchone()
        if not savedCallResult :

            logger.info("kotak- checking rest 1")
            
            if INSTANCE_TYPE == 'PRIMARY':
                cursorObject3.execute(
                    "SELECT * FROM auditNexDb.call c WHERE status = 'Pending' AND batchId = %s ",
                    (CURRENT_BATCH_ID,)
                )
                logger.info("kotak- checking rest 0-11")
                savedCallResult = cursorObject3.fetchone()
                if not savedCallResult :
                    update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET sttStatus = %s, auditStatus = %s,sttEndTime = NOW(),auditStartTime = NOW()
                                    WHERE currentBatch = %s
                                """
                    update_values = ("Complete", "InProgress", str(1))
                    cursorObject3.execute(update_query, update_values)
                    dataBase3.commit()
                    CURRENT_BATCH_STATUS['sttStatus'] = "Complete"
                    CURRENT_BATCH_STATUS['auditStatus'] = "InProgress"

                    container_status = is_service_running('auditnex-translate-1')
                    REQUEST_IN_PROGRESS = False
                    if container_status == False:
                        start_service('auditnex-translate-1')
                        time.sleep(180)
            container_status = is_service_running('auditnex-llm-extraction-1')
            stop_service('auditnex-stt-inference-1')
            stop_service('auditnex-smb-vad-1')
            time.sleep(10)
            if container_status == True:
                stop_service("auditnex-llm-extraction-1")
                time.sleep(10)
            container_status = is_service_running('auditnex-llm-extraction-q1-1')
            if container_status == False:
                start_service("auditnex-llm-extraction-q1-1")
                time.sleep(300)

        if savedCallResult:
            update_query = """
                            UPDATE auditNexDb.call
                            SET status = %s
                            WHERE id = %s
                            """

            new_value = "InProgress"
            condition_value = savedCallResult[0]
            cursorObject3.execute(update_query, (new_value,condition_value))
            dataBase3.commit()
            logger.info("kotak- checking rest 5")

            print("checking pending request 2")




            was_stt_stop = False
            if INSTANCE_TYPE == 'PRIMARY':
                if len(translate_queue) > 0:
                    container_status = is_service_running('auditnex-stt-inference-1')
                    if container_status == True:
                        stop_service('auditnex-stt-inference-1')
                        stop_service('auditnex-smb-vad-1')
                    was_stt_stop = True
                    time.sleep(10)
                    container_status = is_service_running('auditnex-translate-1')
                    if container_status == False:
                        start_service('auditnex-translate-1')
                        time.sleep(180)

                for request_data in translate_queue:
                    logger.info("translate- "+str(request_data))
                    api_wrapper.translate(request_data)
                    logger.info(f"test translate Processing: {request_data}")

                    logger.info("Translate queue pending "+str(len(translate_queue)))

                if was_stt_stop:
                    translate_queue = []
                    container_status = is_service_running('auditnex-translate-1')
                    if container_status == True:
                        stop_service('auditnex-translate-1')
                    start_service("auditnex-stt-inference-1")
                    start_service("auditnex-smb-vad-1")
                    time.sleep(180)


            logger.info(savedCallResult[0])
            logger.info(savedCallResult[7])
            logger.info(savedCallResult[8])
            request_data = {'file_name': savedCallResult[8], 'audio_file_path': savedCallResult[7],'process_id': savedCallResult[1], 'call_id': savedCallResult[4], 'user_id': savedCallResult[5], 'languageId': savedCallResult[6], 'language': savedCallResult[22],'audioDuration':savedCallResult[9] }
            result = api_wrapper.recognize_speech_file_v2(request_data, "",savedCallResult)
            logger.info("Result: "+str(result))
            REQUEST_IN_PROGRESS = False
            logger.info('Done file '+str(request_data['file_name']))

    except Exception as e:
        logger.info(f"Error: {e}")
        dataBase3.rollback()
    finally:
        cursorObject3.close()
        dataBase3.close()






def check_transcript_done_req():
    global REQUEST_IN_PROGRESS, INSTANCE_TYPE
    global REQUEST_IN_PROGRESS_AUDIT
    global translate_queue
    global CURRENT_BATCH_ID
    global CURRENT_BATCH_STATUS

    if CURRENT_BATCH_STATUS and CURRENT_BATCH_STATUS['auditStatus'] != "InProgress":
        return
    if CURRENT_BATCH_STATUS and (CURRENT_BATCH_STATUS['sttStatus'] == 'Pending' or CURRENT_BATCH_STATUS['sttStatus'] == 'InProgress'):
        return
    if REQUEST_IN_PROGRESS and REQUEST_IN_PROGRESS == True:
        return
    if CURRENT_BATCH_ID is None:
        return

    try:
        REQUEST_IN_PROGRESS_AUDIT = True
        logger.info("checking audit pending request")
        logger.info(" "+str(REQUEST_IN_PROGRESS)+" "+str(REQUEST_IN_PROGRESS_AUDIT))
        dataBase3 = mysql.connector.connect(
        host =os.environ.get('MYSQL_HOST'),
        user =os.environ.get('MYSQL_USER'),
        password =os.environ.get('MYSQL_PASSWORD'),
        database = os.environ.get('MYSQL_DATABASE'),
        connection_timeout= 86400000
        )
        cursorObject3 = dataBase3.cursor(buffered=True)

        # Use parameterized query and SKIP LOCKED for MySQL 8 compatibility
        # cursorObject3.execute("SELECT * FROM auditNexDb.call c where status = 'TranscriptDone' and batchId = "+str(CURRENT_BATCH_ID) + " and EXISTS ( SELECT 1 FROM auditNexDb.tradeAudioMapping t WHERE c.audioName = t.audioFileName ) LIMIT 1 FOR UPDATE SKIP LOCKED")
        query = "SELECT * FROM auditNexDb.call WHERE status = %s AND batchId = %s LIMIT 1 FOR UPDATE SKIP LOCKED"
        cursorObject3.execute(query, ('TranscriptDone', CURRENT_BATCH_ID))
        savedCallResult = cursorObject3.fetchone()
        if not savedCallResult:
            logger.info("checking pending request 1")
            if INSTANCE_TYPE == 'PRIMARY':
                update_query = """
                            UPDATE auditNexDb.batchStatus
                            SET  auditStatus = %s, remarks = %s,auditEndTime = NOW()
                            WHERE currentBatch = %s
                        """
                update_values = ("Complete", "InProgress", str(1))

                cursorObject3.execute(update_query, update_values)
                dataBase3.commit()
                CURRENT_BATCH_STATUS['auditStatus'] = "Complete"
                CURRENT_BATCH_STATUS['remarks'] = "InProgress"
            REQUEST_IN_PROGRESS_AUDIT = False
            container_status = is_service_running('auditnex-llm-extraction-q1-1')
            if container_status == True:
                stop_service("auditnex-llm-extraction-q1-1")
                time.sleep(10)
            container_status = is_service_running('auditnex-llm-extraction-1')
            if container_status == False:
                start_service("auditnex-llm-extraction-1")
                time.sleep(300)
        else:
            update_query = """
                                    UPDATE auditNexDb.call
                                    SET status = %s,updatedAt = %s
                                    WHERE id = %s
                                    """

            new_value = "Auditing"
            condition_value = savedCallResult[0]
            cursorObject3.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            dataBase3.commit()
            container_status = is_service_running('auditnex-llm-extraction-1')
            if container_status == True:
                stop_service("auditnex-llm-extraction-1")
                time.sleep(10)
            container_status = is_service_running('auditnex-llm-extraction-q1-1')
            if container_status == False:
                start_service("auditnex-llm-extraction-q1-1")
                time.sleep(300)
            # if is_service_running('auditnex-stt-inference-1'):
            #     if INSTANCE_TYPE == 'PRIMARY':
            #         update_query = """
            #                     UPDATE auditNexDb.batchStatus
            #                     SET sttStatus = %s, auditStatus = %s
            #                     WHERE currentBatch = %s
            #                 """
            #         update_values = ("Complete", "InProgress", str(1))

            #         cursorObject3.execute(update_query, update_values)
            #         dataBase3.commit()
            #     CURRENT_BATCH_STATUS['sttStatus'] = "Complete"
            #     CURRENT_BATCH_STATUS['auditStatus'] = "InProgress"
            #     stop_service('auditnex-stt-inference-1')
            #     stop_service('auditnex-smb-vad-1')
            #     time.sleep(10)
            #     container_status = is_service_running('auditnex-llm-extraction-q1-1')
            #     if container_status == True:
            #         stop_service("auditnex-llm-extraction-q1-1")
            #         time.sleep(10)
            #     container_status = is_service_running('auditnex-llm-extraction-1')
            #     if container_status == False:
            #         start_service("auditnex-llm-extraction-1")
            #         time.sleep(300)
            # else:

            #     container_status = is_service_running('auditnex-llm-extraction-q1-1')
            #     if container_status == True:
            #         stop_service("auditnex-llm-extraction-q1-1")
            #         time.sleep(10)
            #     container_status = is_service_running('auditnex-llm-extraction-1')
            #     if container_status == False:
            #         start_service("auditnex-llm-extraction-1")
            #         time.sleep(300)
            logger.info("checking pending request 2")

            if len(translate_queue) > 0:
                container_status = is_service_running('auditnex-translate-1')
                if container_status == False:
                    start_service('auditnex-translate-1')
                    time.sleep(180)
                for request_data in translate_queue:
                    logger.info("translate- "+str(request_data))
                    api_wrapper.translate(request_data)
                    logger.info(f"test translate Processing: {request_data}")

                    logger.info("Translate queue pending "+str(len(translate_queue)))
                translate_queue = []
                # stop_service('auditnex-translate-1')
                # time.sleep(10)
            logger.info(savedCallResult[0])
            logger.info(savedCallResult[7])
            logger.info(savedCallResult[8])
            request_data = {'file_name': savedCallResult[8], 'audio_file_path': savedCallResult[7],'process_id': savedCallResult[1], 'call_id': savedCallResult[4], 'user_id': savedCallResult[5], 'languageId': savedCallResult[6], 'language': savedCallResult[22] }
            result = api_wrapper.recognize_speech_file_v4(request_data, "",savedCallResult)

            logger.info('Checking file pending for audit')



            REQUEST_IN_PROGRESS_AUDIT = False
    except Exception as e:
        logger.info(f"Error: {e}")
        dataBase3.rollback()
        REQUEST_IN_PROGRESS_AUDIT = False
    finally:
        cursorObject3.close()
        dataBase3.close()
        REQUEST_IN_PROGRESS_AUDIT = False



def check_transcript_done_req_question_1():
    global REQUEST_IN_PROGRESS, INSTANCE_TYPE
    global REQUEST_IN_PROGRESS_AUDIT
    global REQUEST_IN_PROGRESS_AUDIT_2
    global translate_queue
    global CURRENT_BATCH_ID
    global CURRENT_BATCH_STATUS
    logger.info("checking audit pending request for parameter 1")
    if CURRENT_BATCH_STATUS and CURRENT_BATCH_STATUS['remarks'] != 'InProgress':
        return
    if CURRENT_BATCH_STATUS and CURRENT_BATCH_STATUS['auditStatus'] == 'InProgress':
        return
    if CURRENT_BATCH_STATUS and (CURRENT_BATCH_STATUS['sttStatus'] == 'Pending' or CURRENT_BATCH_STATUS['sttStatus'] == 'InProgress'):
        return
    if REQUEST_IN_PROGRESS and REQUEST_IN_PROGRESS == True:
        logger.info('1')
        return
    if REQUEST_IN_PROGRESS_AUDIT and REQUEST_IN_PROGRESS_AUDIT == True:
        logger.info('1-1')
        return
    if REQUEST_IN_PROGRESS_AUDIT_2 and REQUEST_IN_PROGRESS_AUDIT_2 == True:
        logger.info('1-1-2')
        return
    if CURRENT_BATCH_ID is None:
        logger.info('1-2')
        return

    try:
        REQUEST_IN_PROGRESS_AUDIT_2 = True

        logger.info(" "+str(REQUEST_IN_PROGRESS)+" "+str(REQUEST_IN_PROGRESS_AUDIT))
        dataBase3 = mysql.connector.connect(
        host =os.environ.get('MYSQL_HOST'),
        user =os.environ.get('MYSQL_USER'),
        password =os.environ.get('MYSQL_PASSWORD'),
        database = os.environ.get('MYSQL_DATABASE'),
        connection_timeout= 86400000
        )
        cursorObject3 = dataBase3.cursor(buffered=True)



        logger.info("1-7")
        # cursorObject3.execute("SELECT * FROM auditNexDb.call c where status = 'AuditDone' and batchId = "+str(CURRENT_BATCH_ID) + " and EXISTS ( SELECT 1 FROM auditNexDb.tradeAudioMapping t WHERE c.audioName = t.audioFileName )")
        query = "SELECT * FROM auditNexDb.call WHERE status = %s AND batchId = %s LIMIT 1 FOR UPDATE SKIP LOCKED"
        cursorObject3.execute(query, ('AuditDone', CURRENT_BATCH_ID))

        savedCallResult = cursorObject3.fetchone()


        logger.info('1-8')

        if not savedCallResult:
            logger.info('1-9')


            logger.info("checking pending request 2")
            if INSTANCE_TYPE == 'PRIMARY':
                update_query = """
                            UPDATE auditNexDb.batchStatus
                            SET  auditStatus = %s, remarks = %s,auditEndTime = NOW()
                            WHERE currentBatch = %s
                        """
                update_values = ("Complete", "Complete", str(1))

                cursorObject3.execute(update_query, update_values)
                dataBase3.commit()
                CURRENT_BATCH_STATUS['auditStatus'] = "Complete"
                CURRENT_BATCH_STATUS['remarks'] = "Complete"
            REQUEST_IN_PROGRESS_AUDIT_2 = False



        else:
            logger.info('1-10')
            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s,updatedAt = %s
                                WHERE id = %s
                                """

            new_value = "Auditing"
            condition_value = savedCallResult[0]
            cursorObject3.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            dataBase3.commit()
            container_status = is_service_running('auditnex-llm-extraction-q1-1')
            if container_status == True:
                stop_service("auditnex-llm-extraction-q1-1")
                time.sleep(10)
            container_status = is_service_running('auditnex-llm-extraction-1')
            if container_status == False:
                start_service("auditnex-llm-extraction-1")
                time.sleep(300)
            # if is_service_running('auditnex-stt-inference-1'):
            #     if INSTANCE_TYPE == 'PRIMARY':
            #         update_query = """
            #                     UPDATE auditNexDb.batchStatus
            #                     SET auditStatus = %s, remarks = %s
            #                     WHERE currentBatch = %s
            #                 """
            #         update_values = ("Complete", "InProgress", str(1))
            #         cursorObject3.execute(update_query, update_values)
            #         dataBase3.commit()
            #     CURRENT_BATCH_STATUS['auditStatus'] = "Complete"
            #     CURRENT_BATCH_STATUS['remarks'] = "InProgress"

            #     stop_service('auditnex-stt-inference-1')
            #     stop_service('auditnex-smb-vad-1')
            #     time.sleep(10)
            #     container_status = is_service_running('auditnex-llm-extraction-1')
            #     if container_status == True:
            #         stop_service("auditnex-llm-extraction-1")
            #         time.sleep(10)
            #     container_status = is_service_running('auditnex-llm-extraction-q1-1')
            #     if container_status == False:
            #         start_service("auditnex-llm-extraction-q1-1")
            #         time.sleep(300)
            # else:
            #     container_status = is_service_running('auditnex-llm-extraction-1')
            #     if container_status == True:
            #         stop_service("auditnex-llm-extraction-1")
            #         time.sleep(10)
            #     container_status = is_service_running('auditnex-llm-extraction-q1-1')
            #     if container_status == False:
            #         start_service("auditnex-llm-extraction-q1-1")
            #         time.sleep(300)
            logger.info("checking pending request 2")

            if len(translate_queue) > 0:
                container_status = is_service_running('auditnex-translate-1')
                if container_status == False:
                    start_service('auditnex-translate-1')
                    time.sleep(180)
                for request_data in translate_queue:
                    logger.info("translate- "+str(request_data))
                    api_wrapper.translate(request_data)
                    logger.info(f"test translate Processing: {request_data}")

                    logger.info("Translate queue pending "+str(len(translate_queue)))
                translate_queue = []
                # stop_service('auditnex-translate-1')
                # time.sleep(10)
            translate_queue = []
            logger.info(savedCallResult[0])
            logger.info(savedCallResult[7])
            logger.info(savedCallResult[8])
            request_data = {'file_name': savedCallResult[8], 'audio_file_path': savedCallResult[7],'process_id': savedCallResult[1], 'call_id': savedCallResult[4], 'user_id': savedCallResult[5], 'languageId': savedCallResult[6], 'language': savedCallResult[22] }
            result = api_wrapper.recognize_speech_file_v3(request_data, "",savedCallResult)
            logger.info('Checking file pending for audit')


            REQUEST_IN_PROGRESS_AUDIT_2 = False
    except Exception as e:
        logger.info(f"Error: {e}")
        REQUEST_IN_PROGRESS_AUDIT_2 = False
        dataBase3.rollback()
    finally:
        cursorObject3.close()
        dataBase3.close()
        REQUEST_IN_PROGRESS_AUDIT_2 = False





def periodic_task():
    logger.info("test- checking service")
    global CURRENT_BATCH_STATUS,REQUEST_IN_PROGRESS
    list_all_containers()






    while True:
        if CURRENT_BATCH_STATUS is not None and CURRENT_BATCH_STATUS['sttStatus'] == 'InProgress' and REQUEST_IN_PROGRESS == False:
            check_pending_req()
            time.sleep(1)
        if CURRENT_BATCH_STATUS is not None and CURRENT_BATCH_STATUS['auditStatus'] == 'InProgress':
            check_transcript_done_req()
            time.sleep(1)
        if CURRENT_BATCH_STATUS is not None and CURRENT_BATCH_STATUS['remarks'] == 'InProgress':
            check_transcript_done_req_question_1()
            time.sleep(1)

def trigger_api_trademetadata(src_base_path, current_date):





    src_folder = os.path.join(src_base_path, current_date)
    meta_data_url = f"{os.environ.get('COFI_URL')}/api/v1/upload_trademetadata"
    file_name = f"trade_metadata_{current_date}.csv"

    file_path = src_base_path+current_date+"/"+file_name
    logger.info(file_path)

    if os.path.exists(file_path):

        with open(file_path, "rb") as file:

            files = {"file": file}


            response = requests.post(meta_data_url, files=files)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            if response.status_code == 200:
                print("Success", response.json())
            else:
                print("Error", response.status_code, response.text)
        return True
    else:
        return False


def trigger_api_metadata(src_base_path, current_date):





    src_folder = os.path.join(src_base_path, current_date)
    meta_data_url = f"{os.environ.get('COFI_URL')}/api/v1/upload_callmetadata"
    file_name = f"call_metadata_{current_date}.csv"

    file_path = src_base_path+current_date+"/"+file_name
    logger.info(file_path)

    if os.path.exists(file_path):

        with open(file_path, "rb") as file:

            files = {"file": file}


            response = requests.post(meta_data_url, files=files)
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
            if response.status_code == 200:
                print("Success", response.json())
            else:
                print("Error", response.status_code, response.text)
        return True
    else:
        return False

def copy_20_percent_files(src_base_path, dest_base_path, overwrite=False, current_date=None):
    try:
        copied_files = []
        src_folder = os.path.join(src_base_path, current_date)
        dest_folder = os.path.join(dest_base_path)
        logger.info("***************1-4**********")
        if not os.path.exists(src_folder):
            logger.info(f"Source folder '{src_folder}' does not exist. Exiting.")
            return [],current_date

        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        logger.info("***************1-5**********")

        # Get only files (ignore subdirectories)
        all_files = [f for f in os.listdir(src_folder) if os.path.isfile(os.path.join(src_folder, f))]
        logger.info("***************1-6********** "+str(len(all_files)))
        perc_to_copy = os.environ.get('COPY_PERCENTAGE')
        logger.info("***************1-7**********")
        final_perc = int(str(perc_to_copy))*0.01
        logger.info("***************1-8********** "+str(final_perc))
        # Calculate 20%
        files_to_copy_count = math.ceil(len(all_files) * final_perc)
        logger.info("***************1-9********** "+str(files_to_copy_count))
        # Select files to copy
        selected_files = all_files[:files_to_copy_count]
        logger.info("***************1-10********** "+str(len(selected_files)))
        logger.info(f"kotak - Total files found: {len(all_files)}")
        logger.info(f"kotak - Copying {len(selected_files)} files (20%) from {src_folder} to {dest_folder}")

        for item in selected_files:
            src_item_path = os.path.join(src_folder, item)
            dest_item_path = os.path.join(dest_folder, item)

            if os.path.isfile(src_item_path):
                if os.path.exists(dest_item_path) and not overwrite:
                    logger.info(f"Skipped (already exists): {dest_item_path}")
                    copied_files.append(dest_item_path)
                else:
                    shutil.copy2(src_item_path, dest_item_path)
                    logger.info(f"Copied: {dest_item_path}")
                    copied_files.append(dest_item_path)

        return copied_files,current_date
    except Exception as e:
        logger.info(str(e))

def copy_today_date_folder(src_base_path, dest_base_path, overwrite=False, current_date=None):





    src_folder = os.path.join(src_base_path, current_date)

    dest_folder = os.path.join(dest_base_path)

    if not os.path.exists(src_folder):
        logger.info(f"Source folder '{src_folder}' does not exist. Exiting.")
        return [],current_date

    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)

    copied_files = []
    for item in os.listdir(src_folder):
        src_item_path = os.path.join(src_folder, item)
        dest_item_path = os.path.join(dest_folder, item)

        if os.path.isfile(src_item_path):
            if os.path.exists(dest_item_path) and not overwrite:
                logger.info(f"Skipped (already exists): {dest_item_path}")
                copied_files.append(dest_item_path)
            else:
                shutil.copy2(src_item_path, dest_item_path)
                logger.info(f"Copied: {dest_item_path}")
                copied_files.append(dest_item_path)

    return copied_files,current_date

def sort_lid_result(data):

    language_priority = {"hi": 0, "hinglish": 1, "en": 2}  # "hi" comes first, then "en", followed by others


    sorted_data = sorted(
        data,
        key=lambda x: (language_priority.get(x["language"], 2), x["language"])
    )

    return sorted_data

def get_lid_results(files,wait_time=1,batch_id=0,processed_ivr_files=[]):
    global REQUEST_IN_PROGRESS, INSTANCE_TYPE, SPLIT_ARCH
    global translate_queue
    REQUEST_IN_PROGRESS = True
    lid_results = []
    dataBase3111 = mysql.connector.connect(
    host =os.environ.get('MYSQL_HOST'),
    user =os.environ.get('MYSQL_USER'),
    password =os.environ.get('MYSQL_PASSWORD'),
    database = os.environ.get('MYSQL_DATABASE'),
    connection_timeout= 86400000
    )
    cursorObject3111 = dataBase3111.cursor(dictionary=True,buffered=True)


        # Get LID API URLs (comma-separated)
    lid_api_urls = os.environ.get('LID_API_URL', '')
    lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]

    def process_lid_file(file, lid_api_url,batch_id):
        lid_request_data = {
            "file_name": os.path.basename(file),
            "entity": "LID",
            "response": ""
        }
        print("LID Request data", lid_request_data)
        logger.info(f"Processing LID for file: {os.path.basename(file)} with API URL: {lid_api_url}")
        try:
            dataBase3112 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject3112 = dataBase3112.cursor(dictionary=True,buffered=True)
            cursorObject3112.execute("SELECT * FROM lidStatus WHERE audioName = %s", (lid_request_data['file_name'],))
            lid_row = cursorObject3112.fetchone()
            if not lid_row:
                start_time_lid = datetime.now()
                # Stop other services before LID
                # if SPLIT_ARCH == True:
                #     if is_service_running('auditnex-stt-inference-1'):
                #         stop_service('auditnex-stt-inference-1')
                #         time.sleep(10)
                #     if is_service_running('auditnex-smb-vad-1'):
                #         stop_service('auditnex-smb-vad-1')
                #         time.sleep(10)
                #     if is_service_running('auditnex-llm-extraction-1'):
                #         stop_service('auditnex-llm-extraction-1')
                #         time.sleep(10)
                #     container_status = is_service_running('auditnex-lid-inference-1')
                #     if container_status == False:
                #         start_service('auditnex-lid-inference-1')
                #         time.sleep(60)
                logger.info(f"Triggering LID API for file: {os.path.basename(file)}")
                lid_response = requests.post(lid_api_url, headers={"Content-Type": "application/json"}, json=lid_request_data)
                logger.info(f"LID Response for {os.path.basename(file)}: {str(lid_response)}")
                end_time_lid = datetime.now()
                duration_lid = (end_time_lid - start_time_lid).total_seconds()
                if lid_response.status_code == 200:

                    lid_json_response = lid_response.json()
                    logger.info(f"Response for lid {os.path.basename(file)} {str(lid_json_response)}" )
                    language = lid_json_response["data"]["derived_value"][0]["results"][0]
                    duration = lid_json_response["data"]["derived_value"][0]["audio_duration"]
                    # If language is a 3-letter code, make it 2-letter (e.g., "eng" -> "en")
                    if isinstance(language, str) and len(language) == 3:
                        language = language[:2]

                    parsed = urlparse(lid_api_url)

                    dict_result = {
                        "file": os.path.basename(file),
                        "language": language,
                        "lid_processing_time": duration_lid,
                        "audioDuration": duration,
                        'ip': parsed.hostname,
                    }
                    logger.info(f"Result for {os.path.basename(file)}: {dict_result}")
                    logger.info(f"LID response for {os.path.basename(file)}: {language}")
                    print(f"removing the lid completed file {file}")
                    # os.remove(file)
                    add_column = ("INSERT INTO auditNexDb.lidStatus (audioName,language,lidProcessingTime,batchId,audioDuration, ip,createdAt, updatedAt)" "VALUES(%s, %s, %s, %s, %s, %s, NOW(), NOW())")
                    add_result = (dict_result["file"], dict_result["language"], dict_result["lid_processing_time"], batch_id, duration,parsed.hostname)
                    cursorObject3112.execute(add_column, add_result)
                    dataBase3112.commit()
                    logger.info(f"LID result added to database for file: {dict_result['file']}")
                    return dict_result
            else:
                logger.info(f"LID already processed for file: {lid_row['audioName']}, skipping API call.")
                dict_result = {
                    "file": lid_row['audioName'],
                    "language": lid_row['language'],
                    "lid_processing_time": lid_row['lidProcessingTime'],
                    "audioDuration": lid_row['audioDuration'],
                    'ip': lid_row['ip'],
                }
                return dict_result
        except requests.RequestException as e:
            logger.error(f"Error triggering LID API for file {file}: {e}")
            return None
        finally:
            if cursorObject3112:
                cursorObject3112.close()
            if dataBase3112:
                dataBase3112.close()
        # try:
        #     start_time_lid = datetime.now()
        #     logger.info(f"Triggering LID API for file: {os.path.basename(file)}")
        #     lid_response = requests.post(lid_api_url, headers={"Content-Type": "application/json"}, json=lid_request_data)
        #     logger.info(f"LID Response for {os.path.basename(file)}: {str(lid_response)}")

        #     end_time_lid = datetime.now()
        #     duration_lid = (end_time_lid - start_time_lid).total_seconds()
        #     if lid_response.status_code == 200:

        #         lid_json_response = lid_response.json()
        #         logger.info(f"Response for lid {os.path.basename(file)} {str(lid_json_response)}" )
        #         language = lid_json_response["data"]["derived_value"][0]["results"][0]
        #         duration = lid_json_response["data"]["derived_value"][0]["audio_duration"]
        #         if isinstance(language, str) and len(language) == 3:
        #             language = language[:2]
        #         dict_result = {
        #             "file": os.path.basename(file),
        #             "language": language,
        #             "lid_processing_time": duration_lid,
        #             "audioDuration": duration
        #         }
        #         logger.info(f"LID response for {os.path.basename(file)}: {language}")
        #         return dict_result

        # except requests.RequestException as e:
        #     logger.error(f"Error triggering LID API for file {file}: {e}")
        #     return None





        # Upload files to AUDIO_ENDPOINT(s) if SPLIT_ARCH is True

    # logger.info("LID API URLs: " + str(lid_api_url_list))
    # logger.info(INSTANCE_TYPE)
    # logger.info("Files to process for LID: " + str(len(files)))
    # # Prepare upload tasks for parallel execution
    # upload_tasks = []
    # for idx, file in enumerate(files):
    #     if INSTANCE_TYPE == 'SPLIT':
    #         audio_endpoints = os.environ.get('LID_ENDPOINT', '')
    #         endpoints = [ep.strip() for ep in audio_endpoints.split(',') if ep.strip()]
    #         file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
    #         if not endpoints:
    #             logger.info(f"LID endpoint not found, using default: {os.environ.get('LID_ENDPOINT')} URL: {file_url}")
    #             upload_tasks.append((os.environ.get('LID_ENDPOINT'), file_url))
    #         else:
    #             for endpoint in endpoints:
    #                 logger.info(f"LID endpoint {endpoint} found, URL: {file_url}")
    #                 upload_tasks.append((endpoint, file_url))
    # # Run uploads in parallel
    # with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    #     futures = [executor.submit(upload_file_stt_trigger, endpoint, file_url) for endpoint, file_url in upload_tasks]
    #     concurrent.futures.wait(futures)

    # logger.info("Files uploaded to AUDIO_ENDPOINT(s) for LID processing.")

    # time.sleep(2)
    # Prepare files for LID processing
    lid_files = [file for file in files if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]

    # Assign files to LID API URLs in round-robin fashion
    lid_tasks = []
    # for idx, file in enumerate(lid_files):
    #     if lid_api_url_list:
    #         lid_api_url = lid_api_url_list[idx % len(lid_api_url_list)]
    #     else:
    #         lid_api_url = os.environ.get('LID_API_URL')
    #     lid_tasks.append((file, lid_api_url))

    for obj in processed_ivr_files:
        for api_url in lid_api_url_list:
            logger.info(f"Checking IP {obj['ip']} with API URL: {api_url}")
            if obj['ip'] in api_url:
                logger.info(f"Processing LID for file: {obj['file']} with API URL: {api_url}")
                lid_tasks.append((obj['file'], api_url))
                break  # stop after the first match
    # Process LID requests in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(lid_api_url_list) or 1) as executor:
        future_to_file = {executor.submit(process_lid_file, file, lid_api_url,batch_id): file for file, lid_api_url in lid_tasks}
        for future in concurrent.futures.as_completed(future_to_file):
            dict_result = future.result()
            if dict_result:
                lid_results.append(dict_result)
                logger.info(f"LID done files length: " + str(len(lid_results)))

        # Handle translate_queue logic (same as before)
    was_stt_stop = False
    if len(translate_queue) > 0:
        container_status = is_service_running('auditnex-lid-inference-1')
        if container_status == True:
            stop_service('auditnex-lid-inference-1')
        container_status = is_service_running('auditnex-stt-inference-1')
        if container_status == True:
            stop_service('auditnex-stt-inference-1')
            stop_service('auditnex-smb-vad-1')
        was_stt_stop = True
        time.sleep(10)
        container_status = is_service_running('auditnex-translate-1')
        if container_status == False:
            start_service('auditnex-translate-1')
            time.sleep(180)
    for request_data in translate_queue:
        logger.info("translate- "+str(request_data))
        api_wrapper.translate(request_data)
        logger.info(f"test lid translate Processing: {request_data}")
        logger.info("Translate lid queue pending "+str(len(translate_queue)))
    if was_stt_stop:
        translate_queue = []
        container_status = is_service_running('auditnex-translate-1')
        if container_status == True:
            stop_service('auditnex-translate-1')
            time.sleep(10)
        start_service("auditnex-stt-inference-1")
        start_service("auditnex-smb-vad-1")
        time.sleep(180)

    # time.sleep(wait_time)
    sorted_lid_results = sort_lid_result(lid_results)
    REQUEST_IN_PROGRESS = False
    cursorObject3111.close()
    dataBase3111.close()
    return sorted_lid_results


def trigger_api_stt(data, api_url, wait_time=1, current_date=None, batch_id=None):
    global REQUEST_IN_PROGRESS
    global CURRENT_BATCH_STATUS
    REQUEST_IN_PROGRESS = True
    if current_date == None:
        given_date_format = os.environ.get('DATE_FORMAT')
        current_date = datetime.now() - timedelta(days=1)
        current_date = current_date.strftime(given_date_format)


    for item in data:
        if (".wav" in item["file"]) or (".mp3" in item["file"]):
            payload = {
                "call_id": 0,
                "process_id": 1,
                "user_id": "1",
                "files": [
                    {
                        "audioUrl": os.environ.get('AUDIO_ENDPOINT') + "/" + str(current_date) + "/" + item["file"],
                        "fileName": item["file"],
                        "audioDuration": item["audioDuration"]
                    }
                ],
                "type": "Call",
                "batchId": batch_id,
                "languageId": "1",
                "language": item["language"],
                "audioDuration": item["audioDuration"],
                "lid_processing_time": item["lid_processing_time"],
                "ip": item["ip"]

            }

            payload['multiple'] = True

            index = 0
            for f in payload['files']:
                payload['index'] = index
                payload['audio_uri'] = f['audioUrl']
                payload['file_name'] = f['fileName']
                payload['audioDuration'] = f['audioDuration']

                result = api_wrapper.insert_into_db_step_1(payload)
                logger.info(f"Payload saved for file: {f['fileName']}")
            # try:
            #     response = requests.post(api_url, json=payload, headers={"Content-Type": "application/json"})
            #     logger.info(f"{response.status_code} - {response.text}")
            # except requests.RequestException as e:
            #     logger.error(f"Error triggering API for file {e}")

        else:
            continue


        # time.sleep(wait_time)


    # start_service('auditnex-translate-1')
    # time.sleep(10)

def trigger_api_in_batches(files, api_url, wait_time=1, today_date=None):
    if today_date == None:
        given_date_format = os.environ.get('DATE_FORMAT')

        today_date = datetime.now() - timedelta(days=1)
        today_date = today_date.strftime(given_date_format)
    for idx, file in enumerate(files):
        if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file)):
            payload = {
                "call_id": 0,
                "process_id": 1,
                "user_id": "1",
                "files": [
                    {
                        "audioUrl": os.environ.get('AUDIO_ENDPOINT') + "/" + str(today_date) + "/" + os.path.basename(file),
                        "fileName": os.path.basename(file)
                    }
                ],
                "type": "Call",
                "languageId": "1"
            }

            logger.info(f"Payload for file {idx + 1}: {payload}")

            try:
                response = requests.post(api_url, json=payload, headers={"Content-Type": "application/json"})
                logger.info(f"File {idx + 1}: {response.status_code} - {response.text}")
            except requests.RequestException as e:
                logger.error(f"Error triggering API for file {idx + 1}: {e}")

        else:
            continue


        time.sleep(wait_time)

def str_to_datetime(date_str, time_str):
    return datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")



def find_matching_trade(trade):
    connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
    cursor = connection.cursor(dictionary=True,buffered=True)
    lastResult = {}
    audioFileName = trade['audioFileName']
    alNumber = trade['alNumber']
    if alNumber is None or alNumber == "":
        print('Al number absent')
    else:
        alNumber = str(int(float(trade['alNumber'])))

    print('kotak- aLNumber '+str(alNumber))
    try:
        dt_obj = datetime.strptime(trade['tradeDate'], "%Y%m%d")
        dt_obj_2 = datetime.strptime(trade['orderPlacedTime'], "%H%M%S")
        trade_date = dt_obj.strftime("%d-%m-%Y")
        order_time = dt_obj_2.strftime("%H:%M:%S")


        order_datetime = str_to_datetime(trade_date, order_time)
        # print(str(trade['clientCode'])+'---'+str(trade_date)+'---')
        # print(str(trade_date) + " " + str(order_time)+ " " + str(order_time))

        cursor.execute("""
            SELECT * FROM callMetadata
            WHERE callStartDate = %s AND sClientId = %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
        """, (trade_date, trade['clientCode'],trade['audioFileName'], alNumber))
        call_metadata_rows = cursor.fetchall()

        if not call_metadata_rows or  (call_metadata_rows and len(call_metadata_rows) == 0):
            cursor.execute("""
                SELECT * FROM callMetadata
                WHERE callStartDate = %s AND sClientId = %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
            """, (trade_date, trade['clientCode'],trade['audioFileName'], trade['regNumber']))
            call_metadata_rows = cursor.fetchall()

        if call_metadata_rows and len(call_metadata_rows) > 0:
            print("******************************** Part 1 *****************************")



        for call_meta in call_metadata_rows:
            # print("Found call "+str(call_meta['sRecordingFileName']))
            if call_meta['callEndDate'] is None or call_meta['callEndTime'] is None:
                continue
            call_start = str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
            call_end = str_to_datetime(call_meta['callEndDate'], call_meta['callEndTime'])
            # print(str(order_datetime))
            print(str(order_datetime)+" "+str(call_start)+" "+ str(call_end))


            if call_start <= order_datetime <= call_end:


                audio_name = call_meta['sRecordingFileName']
                print(str(call_meta['id']) + " " + call_meta['sRecordingFileName'])

                cursor.execute("SELECT * FROM `call` WHERE audioName=%s", (audio_name,))
                call_row = cursor.fetchone()
                nearest_call_meta = call_meta
                if not call_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                if call_row:
                    call_id = call_row['id']


                    cursor.execute("SELECT * FROM callConversation WHERE callId=%s", (call_id,))
                    conversation_row = cursor.fetchall()
                    conversationLotQty = 0
                    conversationTradePrice = 0.0
                    conversationScriptName = ''
                    conversation_row_count = 0.0

                    if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                    for cr in conversation_row:
                        print(cr['lotQuantity'])
                        print(cr['tradePrice'])

                        if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                            try:
                                conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                            except Exception as e:
                                print(str(cr['lotQuantity']))


                        if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                            conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                        if cr['scriptName'] is not None and cr['scriptName'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):
                            conversationScriptName = conversationScriptName + " " +cr['scriptName']
                            conversation_row_count = conversation_row_count + 1
                        print("cscript - ",conversationScriptName)
                        print("clotQty - ",conversationLotQty)
                        if conversationTradePrice != 0.0:
                            conversationTradePrice = conversationTradePrice/ conversation_row_count
                        print("ctradePrice - ",conversationTradePrice)
                        if len(conversation_row) ==0:
                            print('conversion not found')
                            return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': '' }


                        if trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']:

                            if conversationTradePrice is None or conversationTradePrice == '' or conversationTradePrice == 0.0:
                                print('conversationTradePrice is not proper')
                                if trade['strikePrice'] is None or cr['strikePrice'] is None or int(float(trade['strikePrice']))!= cr['strikePrice']:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }

                            conversation_trade_price =conversationTradePrice
                            trade_price = float(trade['tradePrice'])
                            print("tradePrice - ",trade_price)
                            print((trade_price - 5 <= conversation_trade_price <= trade_price + 5))
                            if (trade_price - 5 <= conversation_trade_price <= trade_price + 5) or (trade['strikePrice'] is not None and cr['strikePrice'] is not None and int(float(trade['strikePrice'])) == cr['strikePrice']):

                                conversation_lot_quantity = conversationLotQty
                                trade_quantity = int(trade['tradeQuantity'])
                                print('price matched checking qty ',conversation_lot_quantity,trade_quantity)
                                if conversation_lot_quantity == 0:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                                if trade_quantity == conversation_lot_quantity:


                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '' }  # Matching row found
                                else:


                                    print("Checking for multiple Qty-"+str( trade['tradeDate']))
                                    print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                                    cursor.execute("""
                                        SELECT SUM(tradeQuantity) as totalQuantity
                                        FROM tradeMetadata
                                        WHERE clientCode = %s AND tradeDate = %s AND orderPlacedTime = %s
                                    """, (trade['clientCode'], trade['tradeDate'], trade['orderPlacedTime']))
                                    result2 = cursor.fetchone()

                                    if result2 and result2['totalQuantity'] is not None:
                                        total_quantity = result2['totalQuantity']
                                        print('Checking for multiple Qty- ',conversation_lot_quantity,total_quantity)
                                        if int(total_quantity) >= conversation_lot_quantity:

                                            return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' } # Matching row found
                                        else:
                                            print('Checking quantity from lotMapping table')
                                            cursor.execute("""
                                                SELECT *
                                                FROM lotQuantityMapping
                                                WHERE LOWER(scriptName) = LOWER(%s)
                                            """, (trade['symbol'].lower()))
                                            result3 = cursor.fetchone()
                                            finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                            print('Checking for multiple Qty from lottable- ',finalLotQty,total_quantity)
                                            if int(total_quantity) >= finalLotQty:

                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' }
                                            else:
                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                            else:
                                print("==>0-1",lastResult)
                                lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }}
                                # return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' } # Matching row found
                        else:
                                print("==>0-1",lastResult)
                                if ('result' in lastResult and 'pre trade found' not in lastResult['result']['tag1'].lower()) or 'result' not in lastResult:
                                    lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }}
                                # return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' } # Matching row found



        cursor.execute("""
            SELECT * FROM callMetadata
            WHERE callStartDate = %s AND sClientId = %s AND callEndTime < %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
            ORDER BY callEndTime DESC
            LIMIT 1
        """, (trade_date, trade['clientCode'], order_time, audioFileName, alNumber))
        nearest_call_meta = cursor.fetchone()

        if not nearest_call_meta:
            cursor.execute("""
            SELECT * FROM callMetadata
            WHERE callStartDate = %s AND sClientId = %s AND callEndTime < %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
            ORDER BY callEndTime DESC
            LIMIT 1
            """, (trade_date, trade['clientCode'], order_time, audioFileName, trade['regNumber']))
            nearest_call_meta = cursor.fetchone()

        while nearest_call_meta:  # Keep finding the nearest until we exhaust options
            audio_name = nearest_call_meta['sRecordingFileName']



            cursor.execute("SELECT * FROM `call` WHERE audioName='"+audio_name+"'")
            call_row = cursor.fetchone()
            if not call_row:
                return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
            if call_row:
                call_id = call_row['id']

                print("******************************** part 2 *****************************")
                print(str(nearest_call_meta['id']) + " " + nearest_call_meta['sRecordingFileName'])
                cursor.execute("SELECT * FROM callConversation WHERE callId=%s", (call_id,))
                conversation_row = cursor.fetchall()
                conversationLotQty = 0
                conversationTradePrice = 0.0
                conversationScriptName = ''
                conversation_row_count = 0
                if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                for cr in conversation_row:
                    print(cr['lotQuantity'])
                    print(cr['tradePrice'])

                    if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        try:
                                conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                        except Exception as e:
                            print(str(cr['lotQuantity']))
                    if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                    if cr['scriptName'] is not None and cr['scriptName'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):
                        conversationScriptName = conversationScriptName + " " +cr['scriptName']
                        conversation_row_count = conversation_row_count + 1
                    print("cscript - ",conversationScriptName)
                    print("clotQty - ",conversationLotQty)
                    if conversationTradePrice != 0.0:
                        conversationTradePrice = conversationTradePrice/ conversation_row_count
                    print("ctradePrice - ",conversationTradePrice)
                    if trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']:
                        if conversationTradePrice is None or conversationTradePrice == '' or conversationTradePrice == 0.0:
                                print('conversationTradePrice is not proper')
                                if trade['strikePrice'] is None or cr['strikePrice'] is None or int(float(trade['strikePrice']))!= cr['strikePrice']:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }

                        conversation_trade_price = conversationTradePrice
                        trade_price = float(trade['tradePrice'])
                        print("tradePrice - ",trade_price)
                        print((trade_price - 5 <= conversation_trade_price <= trade_price + 5))
                        if (trade_price - 5 <= conversation_trade_price <= trade_price + 5) or (trade['strikePrice'] is not None and cr['strikePrice'] is not None and int(float(trade['strikePrice'])) == cr['strikePrice']):

                                conversation_lot_quantity = conversationLotQty
                                trade_quantity = int(trade['tradeQuantity'])
                                if conversation_lot_quantity == 0:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                                if trade_quantity == conversation_lot_quantity:


                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '' }  # Matching row found
                                else:


                                    print("Checking for multiple Qty-"+str( trade['tradeDate']))
                                    print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                                    cursor.execute("""
                                        SELECT SUM(tradeQuantity) as totalQuantity
                                        FROM tradeMetadata
                                        WHERE clientCode = %s AND tradeDate = %s AND orderPlacedTime = %s
                                    """, (trade['clientCode'], trade['tradeDate'], trade['orderPlacedTime']))
                                    result2 = cursor.fetchone()

                                    if result2 and result2['totalQuantity'] is not None:
                                        total_quantity = result2['totalQuantity']
                                        print('Checking for multiple Qty- ',conversation_lot_quantity,total_quantity)
                                        if int(total_quantity) >= conversation_lot_quantity:

                                            return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' } # Matching row found
                                        else:
                                            print('Checking quantity from lotMapping table')
                                            cursor.execute("""
                                                SELECT *
                                                FROM lotQuantityMapping
                                                WHERE LOWER(scriptName) = LOWER(%s)
                                            """, (trade['symbol'].lower()))
                                            result3 = cursor.fetchone()
                                            finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                            print('Checking for multiple Qty from lottable- ',finalLotQty,total_quantity)
                                            if int(total_quantity) >= finalLotQty:

                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' }
                                            else:
                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                        else:
                            print("==>1-1",lastResult)

                            lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }}
                        #     return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' } # Matching row found
                    else:
                        print("==>1-2",lastResult)
                        # return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                        if ('result' in lastResult and 'pre trade found' not in lastResult['result']['tag1'].lower()) or 'result' not in lastResult:
                            lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }}



            cursor.execute("""
                SELECT * FROM callMetadata
                WHERE callStartDate = %s AND sClientId = %s AND callEndTime < %s AND id < %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
                ORDER BY callEndTime DESC
                LIMIT 1
            """, (trade_date, trade['clientCode'], nearest_call_meta['callEndTime'], nearest_call_meta['id'], audioFileName, alNumber))
            nearest_call_meta = cursor.fetchone()
            if not nearest_call_meta:
                cursor.execute("""
                SELECT * FROM callMetadata
                WHERE callStartDate = %s AND sClientId = %s AND callEndTime < %s AND id < %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
                ORDER BY callEndTime DESC
                LIMIT 1
                """, (trade_date, trade['clientCode'], nearest_call_meta['callEndTime'], nearest_call_meta['id'], audioFileName, trade['regNumber']))
                nearest_call_meta = cursor.fetchone()
        if lastResult and 'result' in lastResult:
            return lastResult['trade'], lastResult['nearest_call_meta'], lastResult['conversation_row'], lastResult['result']
        print("******************************** part 3 POST trade *****************************")
        cursor.execute("""
            SELECT *
            FROM callMetadata
            WHERE callStartDate = %s
            AND sClientId = %s
            AND callEndTime >= %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
            ORDER BY callEndTime ASC
            LIMIT 1
        """, (trade_date, trade['clientCode'], order_time, audioFileName, alNumber))

        nearest_call_meta = cursor.fetchone()
        if not nearest_call_meta:
            cursor.execute("""
            SELECT *
            FROM callMetadata
            WHERE callStartDate = %s
            AND sClientId = %s
            AND callEndTime >= %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
            ORDER BY callEndTime ASC
            LIMIT 1
            """, (trade_date, trade['clientCode'], order_time, audioFileName, trade['regNumber']))
            nearest_call_meta = cursor.fetchone()
        while nearest_call_meta:  # Keep finding the nearest until we exhaust options
            audio_name = nearest_call_meta['sRecordingFileName']



            cursor.execute("SELECT * FROM `call` WHERE audioName='"+audio_name+"'")
            call_row = cursor.fetchone()
            if not call_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' }
            if call_row:
                call_id = call_row['id']


                cursor.execute("SELECT * FROM callConversation WHERE callId=%s", (call_id,))
                conversation_row = cursor.fetchall()
                conversationLotQty = 0
                conversationTradePrice = 0.0
                conversationScriptName = ''
                conversation_row_count = 0
                if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                for cr in conversation_row:
                    print(cr['lotQuantity'])
                    print(cr['tradePrice'])
                    if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        try:
                                conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                        except Exception as e:
                            print(str(cr['lotQuantity']))
                    if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                    if cr['scriptName'] is not None and cr['scriptName'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):
                        conversationScriptName = conversationScriptName + " " +cr['scriptName']
                        conversation_row_count = conversation_row_count + 1
                    print("cscript - ",conversationScriptName)
                    print("clotQty - ",conversationLotQty)
                    if conversationTradePrice != 0.0:
                        conversationTradePrice = conversationTradePrice/ conversation_row_count
                    print("ctradePrice - ",conversationTradePrice)

                    if trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']:

                            if conversationTradePrice is None or conversationTradePrice == '' or conversationTradePrice == 0.0:
                                if trade['strikePrice'] is None or cr['strikePrice'] is None or int(float(trade['strikePrice']))!= cr['strikePrice']:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' }

                            conversation_trade_price =conversationTradePrice
                            trade_price = float(trade['tradePrice'])
                            if (trade_price - 5 <= conversation_trade_price <= trade_price + 5)or (trade['strikePrice'] is not None and cr['strikePrice'] is not None and int(float(trade['strikePrice'])) == cr['strikePrice']):

                                conversation_lot_quantity = conversationLotQty
                                trade_quantity = int(trade['tradeQuantity'])
                                if conversation_lot_quantity == 0:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }

                                if trade_quantity == conversation_lot_quantity:


                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '' }  # Matching row found
                                else:


                                    print("Checking for multiple Qty-"+str( trade['tradeDate']))
                                    print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                                    cursor.execute("""
                                        SELECT SUM(tradeQuantity) as totalQuantity
                                        FROM tradeMetadata
                                        WHERE clientCode = %s AND tradeDate = %s AND orderPlacedTime = %s
                                    """, (trade['clientCode'], trade['tradeDate'], trade['orderPlacedTime']))
                                    result2 = cursor.fetchone()

                                    if result2 and result2['totalQuantity'] is not None:
                                        total_quantity = result2['totalQuantity']

                                        if int(total_quantity) >= conversation_lot_quantity:

                                            return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' } # Matching row found
                                        else:

                                            cursor.execute("""
                                                SELECT *
                                                FROM lotQuantityMapping
                                                WHERE LOWER(scriptName) = LOWER(%s)
                                            """, (trade['symbol'].lower()))
                                            result3 = cursor.fetchone()
                                            finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                            if int(total_quantity) >= finalLotQty:

                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' }
                                            else:
                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                            else:
                                print("==>2",lastResult)
                                if 'result' not in lastResult:
                                    lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' }}
                            #     return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' } # Matching row found
                    # else:

                # return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' } # Matching row found



            cursor.execute("""
                SELECT *
                FROM callMetadata
                WHERE callStartDate = %s
                AND sClientId = %s
                AND callEndTime > %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
                ORDER BY callEndTime ASC
                LIMIT 1
            """, (trade_date, trade['clientCode'], nearest_call_meta['callEndTime'], audioFileName, alNumber))
            nearest_call_meta = cursor.fetchone()
            if not nearest_call_meta:
                cursor.execute("""
                SELECT *
                FROM callMetadata
                WHERE callStartDate = %s
                AND sClientId = %s
                AND callEndTime > %s AND sRecordingFileName = %s AND sClientMobileNumber = %s
                ORDER BY callEndTime ASC
                LIMIT 1
                """, (trade_date, trade['clientCode'], nearest_call_meta['callEndTime'], audioFileName, trade['regNumber']))
                nearest_call_meta = cursor.fetchone()

    except Exception as e:
        print(str(e))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


    if lastResult and 'result' in lastResult:
        return lastResult['trade'], lastResult['nearest_call_meta'], lastResult['conversation_row'], lastResult['result']
    else:
        return {},{},{},{'tag1': 'No call record found','tag2': '', 'tag3': '' }

def find_matching_trade_without_client_code(trade, cursor):
    # connection = mysql.connector.connect(
    #         host =os.environ.get('MYSQL_HOST'),
    #         user =os.environ.get('MYSQL_USER'),
    #         password =os.environ.get('MYSQL_PASSWORD'),
    #         database = os.environ.get('MYSQL_DATABASE'),
    #     )
    # cursor = connection.cursor(dictionary=True,buffered=True)
    lastResult = {}
    audioFileName = trade['audioFileName']
    alNumber = trade['alNumber']
    if alNumber is None or alNumber == "":
        if trade['regNumber'] is None or alNumber == "":
            alNumber = trade['regNumber']
        else:
            alNumber = str(int(float(trade['regNumber'])))
    else:
        alNumber = str(int(float(trade['alNumber'])))
    print('kotak- aLNumber '+str(alNumber))
    try:
        dt_obj = datetime.strptime(trade['tradeDate'], "%Y%m%d")
        dt_obj_2 = datetime.strptime(trade['orderPlacedTime'], "%H%M%S")
        trade_date = dt_obj.strftime("%d-%m-%Y")
        order_time = dt_obj_2.strftime("%H:%M:%S")


        order_datetime = str_to_datetime(trade_date, order_time)
        # print(str(trade['clientCode'])+'---'+str(trade_date)+'---')
        # print(str(trade_date) + " " + str(order_time)+ " " + str(order_time))

        cursor.execute("""
            SELECT * FROM callMetadata
            WHERE callStartDate = %s  AND sClientMobileNumber = %s
        """, (trade_date, alNumber))
        call_metadata_rows = cursor.fetchall()

        if not call_metadata_rows or  (call_metadata_rows and len(call_metadata_rows) == 0):
            cursor.execute("""
                SELECT * FROM callMetadata
                WHERE callStartDate = %s  AND sClientMobileNumber = %s
            """, (trade_date, trade['regNumber']))
            call_metadata_rows = cursor.fetchall()

        if call_metadata_rows and len(call_metadata_rows) > 0:
            print("******************************** Part 1 *****************************")



        for call_meta in call_metadata_rows:
            # print("Found call "+str(call_meta['sRecordingFileName']))
            if call_meta['callEndDate'] is None or call_meta['callEndTime'] is None:
                continue
            call_start = str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
            call_end = str_to_datetime(call_meta['callEndDate'], call_meta['callEndTime'])
            # print(str(order_datetime))
            print(str(order_datetime)+" "+str(call_start)+" "+ str(call_end))


            if call_start <= order_datetime <= call_end:


                audio_name = call_meta['sRecordingFileName']
                print(str(call_meta['id']) + " " + call_meta['sRecordingFileName'])

                cursor.execute("SELECT * FROM `call` WHERE audioName=%s", (audio_name,))
                call_row = cursor.fetchone()
                nearest_call_meta = call_meta
                if not call_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                if call_row:
                    call_id = call_row['id']


                    cursor.execute("SELECT * FROM callConversation WHERE callId=%s", (call_id,))
                    conversation_row = cursor.fetchall()
                    conversationLotQty = 0
                    conversationTradePrice = 0.0
                    conversationScriptName = ''
                    conversation_row_count = 0.0

                    if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                    for cr in conversation_row:
                        print(cr['lotQuantity'])
                        print(cr['tradePrice'])

                        if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                            try:
                                conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                            except Exception as e:
                                print(str(cr['lotQuantity']))


                        if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                            conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                        if cr['scriptName'] is not None and cr['scriptName'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):
                            conversationScriptName = conversationScriptName + " " +cr['scriptName']
                            conversation_row_count = conversation_row_count + 1
                        print("cscript - ",conversationScriptName)
                        print("clotQty - ",conversationLotQty)
                        if conversationTradePrice != 0.0:
                            conversationTradePrice = conversationTradePrice/ conversation_row_count
                        print("ctradePrice - ",conversationTradePrice)
                        if len(conversation_row) ==0:
                            print('conversion not found')
                            return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': '' }


                        if trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']:

                            if conversationTradePrice is None or conversationTradePrice == '' or conversationTradePrice == 0.0:
                                print('conversationTradePrice is not proper')
                                if trade['strikePrice'] is None or cr['strikePrice'] is None or int(float(trade['strikePrice']))!= cr['strikePrice']:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }

                            conversation_trade_price =conversationTradePrice
                            trade_price = float(trade['tradePrice'])
                            print("tradePrice - ",trade_price)
                            print((trade_price - 5 <= conversation_trade_price <= trade_price + 5))
                            if (trade_price - 5 <= conversation_trade_price <= trade_price + 5) or (trade['strikePrice'] is not None and cr['strikePrice'] is not None and int(float(trade['strikePrice'])) == cr['strikePrice']):

                                conversation_lot_quantity = conversationLotQty
                                trade_quantity = int(trade['tradeQuantity'])
                                print('price matched checking qty ',conversation_lot_quantity,trade_quantity)
                                if conversation_lot_quantity == 0:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                                if trade_quantity == conversation_lot_quantity:


                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '' }  # Matching row found
                                else:


                                    print("Checking for multiple Qty-"+str( trade['tradeDate']))
                                    print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                                    cursor.execute("""
                                        SELECT SUM(tradeQuantity) as totalQuantity
                                        FROM tradeMetadata
                                        WHERE clientCode = %s AND tradeDate = %s AND orderPlacedTime = %s
                                    """, (trade['clientCode'], trade['tradeDate'], trade['orderPlacedTime']))
                                    result2 = cursor.fetchone()

                                    if result2 and result2['totalQuantity'] is not None:
                                        total_quantity = result2['totalQuantity']
                                        print('Checking for multiple Qty- ',conversation_lot_quantity,total_quantity)
                                        if int(total_quantity) >= conversation_lot_quantity:

                                            return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' } # Matching row found
                                        else:
                                            print('Checking quantity from lotMapping table')
                                            cursor.execute("""
                                                SELECT *
                                                FROM lotQuantityMapping
                                                WHERE LOWER(scriptName) = LOWER(%s)
                                            """, (trade['symbol'].lower()))
                                            result3 = cursor.fetchone()
                                            finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                            print('Checking for multiple Qty from lottable- ',finalLotQty,total_quantity)
                                            if int(total_quantity) >= finalLotQty:

                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' }
                                            else:
                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                            else:
                                print("==>0-1",lastResult)
                                lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }}
                                # return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' } # Matching row found
                        else:
                                print("==>0-1",lastResult)
                                if ('result' in lastResult and 'pre trade found' not in lastResult['result']['tag1'].lower()) or 'result' not in lastResult:
                                    lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }}
                                # return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' } # Matching row found



        cursor.execute("""
            SELECT * FROM callMetadata
            WHERE callStartDate = %s  AND callEndTime < %s  AND sClientMobileNumber = %s
            ORDER BY callEndTime DESC
            LIMIT 1
        """, (trade_date, order_time, alNumber))
        nearest_call_meta = cursor.fetchone()

        if not nearest_call_meta:
            cursor.execute("""
            SELECT * FROM callMetadata
            WHERE callStartDate = %s  AND callEndTime < %s  AND sClientMobileNumber = %s
            ORDER BY callEndTime DESC
            LIMIT 1
            """, (trade_date, order_time, trade['regNumber']))
            nearest_call_meta = cursor.fetchone()

        while nearest_call_meta:  # Keep finding the nearest until we exhaust options
            audio_name = nearest_call_meta['sRecordingFileName']



            cursor.execute("SELECT * FROM `call` WHERE audioName='"+audio_name+"'")
            call_row = cursor.fetchone()
            if not call_row:
                return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
            if call_row:
                call_id = call_row['id']

                print("******************************** part 2 *****************************")
                print(str(nearest_call_meta['id']) + " " + nearest_call_meta['sRecordingFileName'])
                cursor.execute("SELECT * FROM callConversation WHERE callId=%s", (call_id,))
                conversation_row = cursor.fetchall()
                conversationLotQty = 0
                conversationTradePrice = 0.0
                conversationScriptName = ''
                conversation_row_count = 0
                if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                for cr in conversation_row:
                    print(cr['lotQuantity'])
                    print(cr['tradePrice'])

                    if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        try:
                                conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                        except Exception as e:
                            print(str(cr['lotQuantity']))
                    if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                    if cr['scriptName'] is not None and cr['scriptName'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):
                        conversationScriptName = conversationScriptName + " " +cr['scriptName']
                        conversation_row_count = conversation_row_count + 1
                    print("cscript - ",conversationScriptName)
                    print("clotQty - ",conversationLotQty)
                    if conversationTradePrice != 0.0:
                        conversationTradePrice = conversationTradePrice/ conversation_row_count
                    print("ctradePrice - ",conversationTradePrice)
                    if trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']:
                        if conversationTradePrice is None or conversationTradePrice == '' or conversationTradePrice == 0.0:
                                print('conversationTradePrice is not proper')
                                if trade['strikePrice'] is None or cr['strikePrice'] is None or int(float(trade['strikePrice']))!= cr['strikePrice']:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }

                        conversation_trade_price = conversationTradePrice
                        trade_price = float(trade['tradePrice'])
                        print("tradePrice - ",trade_price)
                        print((trade_price - 5 <= conversation_trade_price <= trade_price + 5))
                        if (trade_price - 5 <= conversation_trade_price <= trade_price + 5) or (trade['strikePrice'] is not None and cr['strikePrice'] is not None and int(float(trade['strikePrice'])) == cr['strikePrice']):

                                conversation_lot_quantity = conversationLotQty
                                trade_quantity = int(trade['tradeQuantity'])
                                if conversation_lot_quantity == 0:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                                if trade_quantity == conversation_lot_quantity:


                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '' }  # Matching row found
                                else:


                                    print("Checking for multiple Qty-"+str( trade['tradeDate']))
                                    print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                                    cursor.execute("""
                                        SELECT SUM(tradeQuantity) as totalQuantity
                                        FROM tradeMetadata
                                        WHERE clientCode = %s AND tradeDate = %s AND orderPlacedTime = %s
                                    """, (trade['clientCode'], trade['tradeDate'], trade['orderPlacedTime']))
                                    result2 = cursor.fetchone()

                                    if result2 and result2['totalQuantity'] is not None:
                                        total_quantity = result2['totalQuantity']
                                        print('Checking for multiple Qty- ',conversation_lot_quantity,total_quantity)
                                        if int(total_quantity) >= conversation_lot_quantity:

                                            return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' } # Matching row found
                                        else:
                                            print('Checking quantity from lotMapping table')
                                            cursor.execute("""
                                                SELECT *
                                                FROM lotQuantityMapping
                                                WHERE LOWER(scriptName) = LOWER(%s)
                                            """, (trade['symbol'].lower()))
                                            result3 = cursor.fetchone()
                                            finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                            print('Checking for multiple Qty from lottable- ',finalLotQty,total_quantity)
                                            if int(total_quantity) >= finalLotQty:

                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' }
                                            else:
                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                        else:
                            print("==>1-1",lastResult)

                            lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }}
                        #     return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' } # Matching row found
                    else:
                        print("==>1-2",lastResult)
                        # return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                        if ('result' in lastResult and 'pre trade found' not in lastResult['result']['tag1'].lower()) or 'result' not in lastResult:
                            lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }}



            cursor.execute("""
                SELECT * FROM callMetadata
                WHERE callStartDate = %s  AND callEndTime < %s AND id < %s  AND sClientMobileNumber = %s
                ORDER BY callEndTime DESC
                LIMIT 1
            """, (trade_date, nearest_call_meta['callEndTime'], nearest_call_meta['id'], alNumber))
            nearest_call_meta = cursor.fetchone()
            if not nearest_call_meta:
                cursor.execute("""
                SELECT * FROM callMetadata
                WHERE callStartDate = %s  AND callEndTime < %s AND id < %s  AND sClientMobileNumber = %s
                ORDER BY callEndTime DESC
                LIMIT 1
                """, (trade_date, nearest_call_meta['callEndTime'], nearest_call_meta['id'], trade['regNumber']))
                nearest_call_meta = cursor.fetchone()
        if lastResult and 'result' in lastResult:
            return lastResult['trade'], lastResult['nearest_call_meta'], lastResult['conversation_row'], lastResult['result']
        print("******************************** part 3 POST trade *****************************")
        cursor.execute("""
            SELECT *
            FROM callMetadata
            WHERE callStartDate = %s

            AND callEndTime >= %s  AND sClientMobileNumber = %s
            ORDER BY callEndTime ASC
            LIMIT 1
        """, (trade_date, order_time, alNumber))

        nearest_call_meta = cursor.fetchone()
        if not nearest_call_meta:
            cursor.execute("""
            SELECT *
            FROM callMetadata
            WHERE callStartDate = %s

            AND callEndTime >= %s  AND sClientMobileNumber = %s
            ORDER BY callEndTime ASC
            LIMIT 1
            """, (trade_date, order_time, trade['regNumber']))
            nearest_call_meta = cursor.fetchone()
        while nearest_call_meta:  # Keep finding the nearest until we exhaust options
            audio_name = nearest_call_meta['sRecordingFileName']



            cursor.execute("SELECT * FROM `call` WHERE audioName='"+audio_name+"'")
            call_row = cursor.fetchone()
            if not call_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' }
            if call_row:
                call_id = call_row['id']


                cursor.execute("SELECT * FROM callConversation WHERE callId=%s", (call_id,))
                conversation_row = cursor.fetchall()
                conversationLotQty = 0
                conversationTradePrice = 0.0
                conversationScriptName = ''
                conversation_row_count = 0
                if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                for cr in conversation_row:
                    print(cr['lotQuantity'])
                    print(cr['tradePrice'])
                    if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        try:
                                conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                        except Exception as e:
                            print(str(cr['lotQuantity']))
                    if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):

                        conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                    if cr['scriptName'] is not None and cr['scriptName'] != '' and (cr['scriptName'] == trade['symbol'] or cr['scriptName'] == trade['scripName']):
                        conversationScriptName = conversationScriptName + " " +cr['scriptName']
                        conversation_row_count = conversation_row_count + 1
                    print("cscript - ",conversationScriptName)
                    print("clotQty - ",conversationLotQty)
                    if conversationTradePrice != 0.0:
                        conversationTradePrice = conversationTradePrice/ conversation_row_count
                    print("ctradePrice - ",conversationTradePrice)

                    if trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']:

                            if conversationTradePrice is None or conversationTradePrice == '' or conversationTradePrice == 0.0:
                                if trade['strikePrice'] is None or cr['strikePrice'] is None or int(float(trade['strikePrice']))!= cr['strikePrice']:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' }

                            conversation_trade_price =conversationTradePrice
                            trade_price = float(trade['tradePrice'])
                            if (trade_price - 5 <= conversation_trade_price <= trade_price + 5)or (trade['strikePrice'] is not None and cr['strikePrice'] is not None and int(float(trade['strikePrice'])) == cr['strikePrice']):

                                conversation_lot_quantity = conversationLotQty
                                trade_quantity = int(trade['tradeQuantity'])
                                if conversation_lot_quantity == 0:
                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }

                                if trade_quantity == conversation_lot_quantity:


                                    return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '' }  # Matching row found
                                else:


                                    print("Checking for multiple Qty-"+str( trade['tradeDate']))
                                    print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                                    cursor.execute("""
                                        SELECT SUM(tradeQuantity) as totalQuantity
                                        FROM tradeMetadata
                                        WHERE clientCode = %s AND tradeDate = %s AND orderPlacedTime = %s
                                    """, (trade['clientCode'], trade['tradeDate'], trade['orderPlacedTime']))
                                    result2 = cursor.fetchone()

                                    if result2 and result2['totalQuantity'] is not None:
                                        total_quantity = result2['totalQuantity']

                                        if int(total_quantity) >= conversation_lot_quantity:

                                            return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' } # Matching row found
                                        else:

                                            cursor.execute("""
                                                SELECT *
                                                FROM lotQuantityMapping
                                                WHERE LOWER(scriptName) = LOWER(%s)
                                            """, (trade['symbol'].lower()))
                                            result3 = cursor.fetchone()
                                            finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                            if int(total_quantity) >= finalLotQty:

                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '', 'tag4': 'multiple' }
                                            else:
                                                return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                            else:
                                print("==>2",lastResult)
                                if 'result' not in lastResult:
                                    lastResult = {'trade':trade, 'nearest_call_meta': nearest_call_meta, 'conversation_row': conversation_row, 'result': {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' }}
                            #     return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' } # Matching row found
                    # else:

                # return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' } # Matching row found



            cursor.execute("""
                SELECT *
                FROM callMetadata
                WHERE callStartDate = %s

                AND callEndTime > %s  AND sClientMobileNumber = %s
                ORDER BY callEndTime ASC
                LIMIT 1
            """, (trade_date, nearest_call_meta['callEndTime'], alNumber))
            nearest_call_meta = cursor.fetchone()
            if not nearest_call_meta:
                cursor.execute("""
                SELECT *
                FROM callMetadata
                WHERE callStartDate = %s

                AND callEndTime > %s  AND sClientMobileNumber = %s
                ORDER BY callEndTime ASC
                LIMIT 1
                """, (trade_date, nearest_call_meta['callEndTime'], trade['regNumber']))
                nearest_call_meta = cursor.fetchone()

    except Exception as e:
        print(str(e))



    if lastResult and 'result' in lastResult:
        return lastResult['trade'], lastResult['nearest_call_meta'], lastResult['conversation_row'], lastResult['result']
    else:
        return {},{},{},{'tag1': 'No call record found','tag2': '', 'tag3': '' }

def find_matching_trade_in_step_2(trade,batch_id,onlyPostTrade=False):
    print('Inside find_matching_trade_in_step_2')
    lastResult = {}
    alNumber = trade['alNumber']
    # if alNumber is None or alNumber == "":
    #     alNumber = trade['regNumber']
    if alNumber is None or alNumber == "":
        print('Empty alNumber')
    else:
        alNumber = str(int(float(trade['alNumber'])))
    print('kotak- aLNumber '+str(alNumber))
    try:
        print(trade['id'])
        dt_obj = datetime.strptime(trade['tradeDate'], "%Y%m%d")
        dt_obj_2 = datetime.strptime(trade['orderPlacedTime'], "%H%M%S")
        trade_date = dt_obj.strftime("%d-%m-%Y")
        order_time = dt_obj_2.strftime("%H:%M:%S")
        print(str(trade_date) + " " + str(order_time))


        order_datetime = str_to_datetime(trade_date, order_time)
        print(str(trade['clientCode'])+'---'+str(trade_date)+'---')

        conversation_row = {}
        # PART 1: callStartDate, sClientMobileNumber, callStartTime/EndTime not null, batchId
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientMobileNumber'] == alNumber and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id
        ]
        if call_metadata_rows and len(call_metadata_rows) > 0:
            print("********************************-----*****************************")
        conversation_row = {}
        for call_meta in call_metadata_rows:
            print("Found call "+str(call_meta['sRecordingFileName']))
            call_start = str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
            call_end = str_to_datetime(call_meta['callEndDate'], call_meta['callEndTime'])
            print(str(order_datetime))
            print(str(order_datetime)+" "+str(call_start)+" "+ str(call_end))


            if call_start <= order_datetime <= call_end:
                print("Inside 1")

                # audio_name = call_meta['sRecordingFileName']
                # print(audio_name)

                # cursor.execute("SELECT * FROM `call` WHERE audioName=%s", (audio_name,))
                # call_row = cursor.fetchone()
                if onlyPostTrade == False:
                    return trade, [call_meta],conversation_row, {'tag1': 'Pre trade found','tag2': '', 'tag3': '' }


        print("*****PART 2****")
        # PART 2: callEndTime < order_time, order by callEndTime desc
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientMobileNumber'] == alNumber and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id and
            row['callEndTime'] < order_time
        ]
        call_metadata_rows.sort(key=lambda x: x['callEndTime'], reverse=True)
        if call_metadata_rows and len(call_metadata_rows) > 0:
            if onlyPostTrade == False:
                return trade, call_metadata_rows,conversation_row, {'tag1': 'Pre trade found','tag2': '', 'tag3': '' }


        print("****PART 3*****")
        # PART 3: callEndTime >= order_time, order by callEndTime asc
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientMobileNumber'] == alNumber and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id and
            row['callEndTime'] >= order_time
        ]
        call_metadata_rows.sort(key=lambda x: x['callEndTime'])
        if call_metadata_rows and len(call_metadata_rows) > 0:
            return trade, call_metadata_rows,conversation_row, {'tag1': 'Post trade found','tag2': '', 'tag3': '' }





    except Exception as e:
        print(str(e))

    return {},{},{},{'tag1': 'No call record found','tag2': '', 'tag3': '' }
def find_matching_trade_in_step_1(trade,batch_id, onlyPostTrade=False):
    print('Inside find_matching_trade_in_step_1')
    lastResult = {}
    alNumber = trade['alNumber']
    if alNumber is None or alNumber == "":
        if trade['regNumber'] is None or alNumber == "":
            alNumber = trade['regNumber']
        else:
            alNumber = str(int(float(trade['regNumber'])))
    else:
        alNumber = str(int(float(trade['alNumber'])))
    print('kotak- aLNumber '+str(alNumber))
    try:
        print(trade['id'])
        dt_obj = datetime.strptime(trade['tradeDate'], "%Y%m%d")
        dt_obj_2 = datetime.strptime(trade['orderPlacedTime'], "%H%M%S")
        trade_date = dt_obj.strftime("%d-%m-%Y")
        order_time = dt_obj_2.strftime("%H:%M:%S")
        print(str(trade_date) + " " + str(order_time))


        order_datetime = str_to_datetime(trade_date, order_time)
        print(str(trade['clientCode'])+'---'+str(trade_date)+'---')

        conversation_row = {}

        # PART 1: callStartDate, sClientMobileNumber, callStartTime/EndTime not null, batchId
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientMobileNumber'] == alNumber and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id
        ]
        if call_metadata_rows and len(call_metadata_rows) > 0:
            print("********************************-----*****************************")
        conversation_row = {}
        for call_meta in call_metadata_rows:
            print("Found call "+str(call_meta['sRecordingFileName']))
            call_start = str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
            call_end = str_to_datetime(call_meta['callEndDate'], call_meta['callEndTime'])
            print(str(order_datetime))
            print(str(order_datetime)+" "+str(call_start)+" "+ str(call_end))


            if call_start <= order_datetime <= call_end:
                print("Inside 1")

                # audio_name = call_meta['sRecordingFileName']
                # print(audio_name)

                # cursor.execute("SELECT * FROM `call` WHERE audioName=%s", (audio_name,))
                # call_row = cursor.fetchone()
                if onlyPostTrade == False:
                    return trade, [call_meta],conversation_row, {'tag1': 'Pre trade found','tag2': '', 'tag3': '' }


        print("****PART 2*****")

        # PART 2: callEndTime < order_time, order by callEndTime desc
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientMobileNumber'] == alNumber and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id and
            row['callEndTime'] < order_time
        ]
        call_metadata_rows.sort(key=lambda x: x['callEndTime'], reverse=True)
        if call_metadata_rows and len(call_metadata_rows) > 0:
            if onlyPostTrade == False:
                return trade, call_metadata_rows,conversation_row, {'tag1': 'Pre trade found','tag2': '', 'tag3': '' }



        print("****PART 3*****")
        # PART 3: callEndTime >= order_time, order by callEndTime asc
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientMobileNumber'] == alNumber and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id and
            row['callEndTime'] >= order_time
        ]
        call_metadata_rows.sort(key=lambda x: x['callEndTime'])
        if call_metadata_rows and len(call_metadata_rows) > 0:
            return trade, call_metadata_rows,conversation_row, {'tag1': 'Post trade found','tag2': '', 'tag3': '' }

    except Exception as e:
        print(str(e))

    return {},{},{},{'tag1': 'No call record found','tag2': '', 'tag3': '' }

def find_matching_trade_in_step_3(trade,batch_id,onlyPostTrade=False):
    print('Inside find_matching_trade_in_step_3')
    lastResult = {}
    alNumber = trade['alNumber']
    if alNumber is None or alNumber == "":
        if trade['regNumber'] is None or alNumber == "":
            alNumber = trade['regNumber']
        else:
            alNumber = str(int(float(trade['regNumber'])))
    else:
        alNumber = str(int(float(trade['alNumber'])))
    print('kotak- aLNumber '+str(alNumber))
    print(len(callMetadata))
    try:
        print(trade['id'])
        dt_obj = datetime.strptime(trade['tradeDate'], "%Y%m%d")
        dt_obj_2 = datetime.strptime(trade['orderPlacedTime'], "%H%M%S")
        trade_date = dt_obj.strftime("%d-%m-%Y")
        order_time = dt_obj_2.strftime("%H:%M:%S")
        print(str(trade_date) + " " + str(order_time))


        order_datetime = str_to_datetime(trade_date, order_time)
        print(str(trade['clientCode'])+'---'+str(trade_date)+'---')
        conversation_row = {}

        # PART 1: callStartDate, sClientId, callStartTime/EndTime not null, batchId
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientId'] is not None and
            row['sClientId'].lower() == trade['clientCode'].lower() and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id
        ]
        print(trade['clientCode'])
        matching_rows = [row for row in callMetadata if row['sClientId'] is not None and row['callStartDate'] == trade_date and row['sClientId'].lower() == trade['clientCode'].lower()]
        # print(matching_rows)
        # print(call_metadata_rows)
        if call_metadata_rows and len(call_metadata_rows) > 0:
            print("********************************-----*****************************")
        conversation_row = {}
        for call_meta in call_metadata_rows:
            print("Found call "+str(call_meta['sRecordingFileName']))
            call_start = str_to_datetime(call_meta['callStartDate'], call_meta['callStartTime'])
            call_end = str_to_datetime(call_meta['callEndDate'], call_meta['callEndTime'])
            print(str(order_datetime))
            print(str(order_datetime)+" "+str(call_start)+" "+ str(call_end))


            if call_start <= order_datetime <= call_end:
                # print("Inside 1")

                # audio_name = call_meta['sRecordingFileName']
                # print(audio_name)

                # cursor.execute("SELECT * FROM `call` WHERE audioName=%s", (audio_name,))
                # call_row = cursor.fetchone()
                if onlyPostTrade == False:
                    return trade, [call_meta],conversation_row, {'tag1': 'Pre trade found','tag2': '', 'tag3': '' }


        print("****PART 2*****")
        print(order_time,trade_date)
        # PART 2: callEndTime < order_time, order by callEndTime desc
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientId'] is not None and
            row['sClientId'].lower() == trade['clientCode'].lower() and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id and
            row['callEndTime'] < order_time
        ]

        call_metadata_rows.sort(key=lambda x: x['callEndTime'], reverse=True)
        if call_metadata_rows and len(call_metadata_rows) > 0:
            if onlyPostTrade == False:
                return trade, call_metadata_rows,conversation_row, {'tag1': 'Pre trade found','tag2': '', 'tag3': '' }


        print("****PART 3*****")
        # PART 3: callEndTime >= order_time, order by callEndTime asc
        call_metadata_rows = [row for row in callMetadata if
            row['callStartDate'] == trade_date and
            row['sClientId'] is not None and
            row['sClientId'].lower() == trade['clientCode'].lower() and
            row['callStartTime'] not in (None, '') and
            row['callEndTime'] not in (None, '') and
            row['batchId'] == batch_id and
            row['callEndTime'] >= order_time
        ]
        call_metadata_rows.sort(key=lambda x: x['callEndTime'])

        if call_metadata_rows and len(call_metadata_rows) > 0:
            return trade, call_metadata_rows,conversation_row, {'tag1': 'Post trade found','tag2': '', 'tag3': '' }

    except Exception as e:
        print(str(e))

    return {},{},{},{'tag1': 'No call record found','tag2': '', 'tag3': '' }


def get_container_by_name(service_name):
    try:
        containers = client_docker.containers.list(all=True)
        for container in containers:
            if service_name in container.name:  # Partial match for dynamic names
                return container
    except Exception as e:
        print(f"Error finding container {service_name}: {e}")
    return None

def stop_service(service_name):
    if INSTANCE_TYPE == 'SPLIT' and SPLIT_ARCH == True:
        stop_container(service_name)
        return
    container = get_container_by_name(service_name)
    if container:
        container.stop()
        print(f"Stopped service: {service_name}")
    else:
        print(f"Service {service_name} not found or not in network")

def start_docker_compose_service(service_name, compose_path=".."):
    try:
        logger.info("test- starting"+str(service_name))
        subprocess.run(["docker", "compose", "up", "-d", service_name], check=True)

        logger.info(f"test- Started service: {service_name}")
    except subprocess.CalledProcessError as e:
        logger.info(f"test- Error starting service {service_name}: {e}")
    except Exception as e:
        logger.info(f"test- Error starting  {service_name}: {e}")

def start_service(service_name):
    if INSTANCE_TYPE == 'SPLIT' and SPLIT_ARCH == True:
        start_container(service_name)
        return
    container = get_container_by_name(service_name)
    if container:
        container.start()
        print(f"Started service: {service_name}")
    else:
        print(f"Service {service_name} not found or not in network")

def list_all_containers():
    global client_docker
    containers = client_docker.containers.list(all=True)
    logger.info("test- listing all continers")

    for container in containers:
        logger.info(container.name)
        logger.info(f"test- ID: {container.id}, Name: {container.name}, Status: {container.status}")


def is_service_running(service_name):
    global client_docker
    """
    Checks if a Docker service (container) is running.

    :param service_name: Name of the Docker container
    :return: True if running, False otherwise
    """

    logger.info(f'test-{service_name}')
    if INSTANCE_TYPE == 'SPLIT' and SPLIT_ARCH == True:
       service_status = is_container_running(service_name)
       return service_status
    try:
        container = client_docker.containers.get(service_name)
        logger.info("test- status container "+str(container.status))
        return container.status == "running"
    except docker.errors.NotFound:
        logger.info("test- Not found")
        return False
    except Exception as e:
        logger.info(f"test- Error checking service {service_name}: {e}")
        return False

def evaluate_trade_result(trade):
    result = trade.get('result', {})
    ifScript = result.get('ifScript', False)
    ifPrice = result.get('ifPrice', False)
    ifQty = result.get('ifQty', False)

    if ifScript and ifPrice and ifQty:
        return 3, {'tag1': 'Pre trade found', 'tag2': 'Details matching', 'tag3': ''}
    elif ifScript and ifPrice and not ifQty:
        return 2, {'tag1': 'Pre trade found', 'tag2': 'Details not matching', 'tag3': 'Quantity'}
    elif ifScript and not ifPrice and ifQty:
        return 2, {'tag1': 'Pre trade found', 'tag2': 'Details not matching', 'tag3': 'Price'}
    elif not ifScript and ifPrice and ifQty:
        return 2, {'tag1': 'Pre trade found', 'tag2': 'Details not matching', 'tag3': 'Script'}
    elif ifScript and not ifPrice and not ifQty:
        return 2, {'tag1': 'Pre trade found', 'tag2': 'Details not matching', 'tag3': 'Price and Quantity'}
    elif not ifScript and ifPrice and not ifQty:
        return 1, {'tag1': 'No pre trade found', 'tag2': 'Details not matching', 'tag3': 'Script and Quantity'}
    elif not ifScript and not ifPrice and ifQty:
        return 1, {'tag1': 'No pre trade found', 'tag2': 'Details not matching', 'tag3': 'Script and Price'}
    else:
        return 0, {'tag1': 'No pre trade found', 'tag2': 'Details not matching', 'tag3': 'Script, Price and Quantity'}

def find_best_trade(trades, nearest_call_meta, conversation_row):
    best_rank = -1
    best_result = None

    for trade in trades:
        rank, tags = evaluate_trade_result(trade)
        if rank > best_rank:
            best_rank = rank
            best_result = (trade, nearest_call_meta, conversation_row, tags)
        if best_rank == 3:  # perfect match, no need to look further
            break
   
    return best_result

def get_price_diff_range(price):
    if price >= 7500:
        return 11, 15
    elif 5000 <= price < 7500:
        return 6, 10
    elif 2500 <= price < 5000:
        return 3, 6
    elif 1250 <= price < 2500:
        return 2, 4
    elif 650 <= price < 1250:
        return 0.90, 2
    elif 300 <= price < 650:
        return 0.45, 1
    else:  # below 300
        return 0.05, 0.45

def is_acronym(acronym, phrase):
    
    
    if len(phrase.split()) < 2:
        return False
    
    ignore_words = {"LTD", "LIMITED", "INC", "PVT", "CORPORATION", "LLC", "PLC"}
    
    acronym = acronym.replace("LIMITED", "").replace("CORPORATION", "").replace("LTD", "").replace("INC", "").replace("PVT", "").replace("LLC", "").replace("PLC", "").replace(' ','')
    words = [w for w in phrase.upper().split() if w not in ignore_words]
    initials = ''.join(word[0] for word in words)
    # if acronym.upper() == initials or acronym.upper() in initials or   initials in acronym.upper():
        
    #     print('******2',acronym.upper(),initials,acronym.upper() == initials)
        
        
    return acronym.upper() == initials

def match_company_names(name1, name2):
    # Try direct fuzzy match

    if name1 == 'NA' or name2 == 'NA':
        return True
    
    if name1 == '' or name2 == '':
        return False

    if name1 is None or name2 is None:
        return False
        
    similarity = fuzz.token_set_ratio(name1.replace('LIMITED','').replace('limited',''), name2.replace('LIMITED','').replace('limited',''))

    if name1.lower() == 'nifty' or name2.lower() == 'nifty':
        if name1.lower() == name2.lower():
            return True
        else:
            return False


    def normalize_name(name):
        return re.sub(r'[^A-Z]', '', name.upper())

    # Try acronym match in either direction
    # is_acro_1 = is_acronym(name1, name2)
    # is_acro_2 = is_acronym(name2, name1)
    
    print("match_company_names ==> ",similarity, name1, name2)
    if is_acronym(name1, name2) or is_acronym(name2, name1):
        return True
    if normalize_name(name1) == normalize_name(name2) or normalize_name(name1) in normalize_name(name2) or normalize_name(name2) in normalize_name(name1):
        return True

    if name1 == name2 or name1 in name2 or name2 in name1:
        return True
    # Fuzzy match
    similarity = fuzz.token_set_ratio(name1.replace('LIMITED','').replace('limited',''), name2.replace('LIMITED','').replace('limited',''))
    if similarity < 65:
        # Remove common suffixes from both names
        replacements = {
            "EQ": "",
            "LIMITED": "",
            "limited": "",
            "CORPORATION": "",
            "LTD": "",
            "INC": "",
            "PVT": "",
            "LLC": "",
            "PLC": "",
            "LLP": "",
        }
        
        for term, replacement in replacements.items():
            name1 = name1.replace(term, replacement).strip()
            name2 = name2.replace(term, replacement).strip()
        
        similarity = fuzz.token_set_ratio(name1, name2)
        print("final match",name1, name2,similarity)
        if similarity >= 65:
            return True
    return similarity >= 65

def group_by_script_name(data):
    """Group rows by scriptName, handling empty/None values"""
    grouped = defaultdict(list)
    
    for row in data:
        script_name = row.get('scriptName')
        # Handle None, empty string, or any falsy value
        key = script_name if script_name else 'EMPTY_SCRIPT'
        grouped[key].append(row)
    
    return dict(grouped)

# Additional utility functions
def get_script_summary(grouped_data):
    """Get summary statistics for each script"""
    summary = {}
    for script_name, rows in grouped_data.items():
        total_quantity = sum(row['lotQuantity'] for row in rows)
        total_trade_price = sum(row['tradePrice'] for row in rows)
        total_strike_price = sum(row['strikePrice'] for row in rows)
        row_count = len(rows)
        
        # Calculate average trade price, strike price, and quantity
        average_trade_price = total_trade_price / row_count if row_count > 0 else 0
        average_strike_price = total_strike_price / row_count if row_count > 0 else 0
        average_quantity = total_quantity / row_count if row_count > 0 else 0
        
        # Check if any row has currentMarketPrice as 'YES'
        has_current_market_price = any(row.get('currentMarketPrice') == 'YES' for row in rows)
        
        summary[script_name] = {
            'total_quantity': total_quantity,
            'average_quantity': average_quantity,
            'total_trade_price': total_trade_price,
            'average_trade_price': average_trade_price,
            'total_strike_price': total_strike_price,
            'average_strike_price': average_strike_price,
            'current_market_price': 'YES' if has_current_market_price else 'NO',
            'row_count': row_count
        }
    
    return summary

def find_matching_trade_with_voice_confirmations(trade, batch_id):
    global callMetadata, callsData, tradeAudioMappingData, callConversationData, tradeMetadataData, lotQuantityMappingData
    connection = mysql.connector.connect(**db_config
        )
    cursor = connection.cursor(dictionary=True,buffered=True)
    voiceResult = trade['voiceRecordingConfirmations']
    audioFileName = trade['audioFileName']
    print(voiceResult)
    lastResult = {}
    print('Inside find_matching_trade_with_voice_confirmations - rule_engine_v2')
    if trade['scripName'] == None:
        trade['scripName'] = ''
    if trade['symbol'] == None:
        trade['symbol'] = ''
    try:
        dt_obj = datetime.strptime(trade['tradeDate'], "%Y%m%d")
        dt_obj_2 = datetime.strptime(trade['orderPlacedTime'], "%H%M%S")
        trade_date = dt_obj.strftime("%d-%m-%Y")
        order_time = dt_obj_2.strftime("%H:%M:%S")
        if voiceResult == 'Pre trade found' or voiceResult == 'No pre trade found':
            conversation_row = []
            # Get single data from callMetadataData variable
            nearest_call_meta = next(
                (row for row in callMetadata if row['callStartDate'] == trade_date and row['sRecordingFileName'] == trade['audioFileName'] and row['batchId'] == batch_id),
                None
            )
            print(11)
            call_row = next(
                (row for row in callsData if row['audioName'] == trade['audioFileName'] and row['batchId'] == batch_id),
                None
            )
            if call_row:
                    print('Found call row')
                    call_id = call_row['id']

                    if call_row['status'] == 'UnsupportedLanguage':
                        return trade, {},{}, {'tag1': 'Unsupported Language','tag2': '', 'tag3': '' }
                    conversation_row = [
                        row for row in callConversationData
                        if row['callId'] == call_id
                    ]
                    conversationLotQty = 0
                    conversationTradePrice = 0.0
                    conversationScriptName = ''
                    conversation_row_count = 0.0
                    
                    
                    
                    if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        print('conversation not found')
                        return trade, nearest_call_meta,{}, {'tag1': 'Non observatory call','tag2': '', 'tag3': '' }
                    index = 0
                    checkAllScriptEmpty = False
                    allStockSame = False
                    checkIfSingle = False
                    indexScript = 0
                    allStockSame_scriptname = ''

                    grouped_with_empty = group_by_script_name(conversation_row)
                    summary = get_script_summary(grouped_with_empty)

                    for cr in conversation_row:
                        
                        if cr['scriptName'] == "":
                            indexScript = indexScript + 1
                            allStockSame = False
                        else:
                            if allStockSame_scriptname == '':
                                allStockSame_scriptname = cr['scriptName']
                            
                            if allStockSame_scriptname == cr['scriptName']:
                                allStockSame = True
                            else:
                                allStockSame = False

                    if indexScript == len(conversation_row):
                        checkAllScriptEmpty = True
                        checkIfSingle = True
                        allStockSame = True
                    for cr in conversation_row:
                        print(conversation_row)
                        print(cr['lotQuantity'])
                        print(cr['tradePrice'])
                        print('************')
                        print(cr['scriptName'],trade['scripName'],trade['symbol'])
                        print(call_id)
                        if checkAllScriptEmpty:
                            isCompanyMatching = find_matching_lot_quantity_mapping(trade,cr) or match_company_names(cr['scriptName'],trade['scripName']) or match_company_names(cr['scriptName'],trade['symbol'])
                            print("is company name matching1",isCompanyMatching)
                            if cr['lotQuantity'] is not None and cr['lotQuantity'] != '':
                                try:
                                    conversationLotQty =  int(float(cr['lotQuantity']))
                                except Exception as e:
                                    print(str(e))

                            if cr['tradePrice'] is not None and cr['tradePrice'] != '':
                                try:
                                    conversationTradePrice = float(cr['tradePrice'])
                                except Exception as e:
                                    print(str(e))
                            if checkIfSingle:
                                if cr['scriptName'] is not None and cr['scriptName'] != '' and (isCompanyMatching):
                                    conversationScriptName = conversationScriptName + "" +cr['scriptName']
                                        

                            if len(conversation_row) == 1:
                                allStockSame = True
                        
                        else:
                            isCompanyMatching = find_matching_lot_quantity_mapping(trade,cr) or match_company_names(cr['scriptName'],trade['scripName']) or match_company_names(cr['scriptName'],trade['symbol'])
                            # print(find_matching_lot_quantity_mapping(trade,cr))
                            # print(match_company_names(cr['scriptName'],trade['scripName']))
                            # print(match_company_names(cr['scriptName'],trade['symbol']))
                            # print("is company name matching2",isCompanyMatching)
                            if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and ( conversationScriptName != "" or isCompanyMatching or allStockSame):
                                
                                try:
                                    conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                                except Exception as e:
                                    print(str(cr['lotQuantity']))

                                
                            if cr['tradePrice'] is not None and cr['tradePrice'] != '' and ( conversationScriptName != "" or isCompanyMatching or allStockSame):
                                try:
                                    conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                                    conversation_row_count = conversation_row_count + 1
                                except Exception as e:
                                    print(str(cr['tradePrice']))
                               
                            if cr['scriptName'] is not None and cr['scriptName'] != '' and (isCompanyMatching):
                                conversationScriptName = conversationScriptName + "" +cr['scriptName']
                            
                            # else:
                            #     if cr['scriptName'] is not None:
                            #         similarity1 = fuzz.ratio(cr['scriptName'] , trade['scripName'])
                            #         similarity2 = fuzz.ratio(cr['scriptName'] , trade['symbol'])
                            #         if similarity1 > 70 or similarity2 > 70: 
                            #             conversationScriptName = conversationScriptName + "" +cr['scriptName']
                                
                            print("cscript - ",conversationScriptName)
                            print("clotQty - ",conversationLotQty)
                            print("conversationTradePrice - ",conversationTradePrice)
                            print("conversation_row_count - ",conversation_row_count)
                            if conversationTradePrice != 0.0:
                                conversationTradePrice = conversationTradePrice/ conversation_row_count
                            print("ctradePrice - ",conversationTradePrice)
                        
                        

                        ifScript= False
                        ifPrice = False
                        ifQty = False  
                        print(conversationScriptName,trade['symbol'])
                        if conversationScriptName != "" and (trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']):
                            ifScript = True
                        elif conversationScriptName != "" and (trade['scripName'] in conversationScriptName or conversationScriptName in trade['scripName']):
                            ifScript = True
                        else:
                            if conversationScriptName != "":
                                print('Checking company names')
                                if find_matching_lot_quantity_mapping(trade,cr) or match_company_names(trade['symbol'],conversationScriptName) or match_company_names(conversationScriptName,trade['symbol']):
                                    ifScript = True
                                if find_matching_lot_quantity_mapping(trade,cr) or match_company_names(trade['scripName'],conversationScriptName) or match_company_names(conversationScriptName,trade['scripName']):
                                    ifScript = True
                        
                        if ifScript == False:
                            ifScript = find_matching_lot_quantity_mapping(trade,cr)
                        
                        # else:
                        #     if conversationScriptName != "" :
                        #             similarity1 = fuzz.ratio(trade['symbol'] , conversationScriptName)
                        #             similarity2 = fuzz.ratio(conversationScriptName , ['symbol'])
                        #             if similarity1 > 70 or similarity2 > 70: 
                        #                 ifScript = True
                        if conversationTradePrice is not None and conversationTradePrice != '' and conversationTradePrice != 0.0:
                            print(trade['strikePrice'])
                            print(cr['strikePrice'])
                            conversation_trade_price =conversationTradePrice
                            trade_price = float(trade['tradePrice'])
                            print("tradePrice - ",trade_price)
                            lower_diff, upper_diff = get_price_diff_range(trade_price)
                            print((trade_price - lower_diff <= conversation_trade_price <= trade_price + upper_diff))
                            cond1 = (trade_price - lower_diff <= conversation_trade_price <= trade_price + upper_diff)
                            lower_diff2, upper_diff2 = get_price_diff_range(conversation_trade_price)
                            print((conversation_trade_price - lower_diff2 <= trade_price <= conversation_trade_price + upper_diff2))
                            cond2 = (conversation_trade_price - lower_diff2 <= trade_price <= conversation_trade_price + upper_diff2)
                            if cond1 or cond2:
                                ifPrice = True
                    
                        if ifPrice == False and (trade['strikePrice'] is not None and cr['strikePrice'] is not  None  and  trade['strikePrice'] != "" and  cr['strikePrice'] != "" and int(float(trade['strikePrice'])) != 0 and cr['strikePrice'] != 0 and int(float(trade['strikePrice'])) == cr['strikePrice']):
                            ifPrice = True
                        
                        print("checking ifPrice value part 1- ",ifPrice)
                        print("current market price part 1- ",cr['currentMarketPrice'])


                        if ifPrice == False:
                            for script_name, stats in summary.items():
                                if script_name == cr['scriptName'] or (script_name == 'EMPTY_SCRIPT' and cr['scriptName'] == ''):
                                    if stats['average_trade_price'] == trade['tradePrice'] or stats['average_strike_price'] == trade['strikePrice']:
                                        ifPrice = True
                        if ifPrice == False and cr['currentMarketPrice'] == 'YES':
                            ifPrice = True
                            
                        conversation_lot_quantity = conversationLotQty
                        trade_quantity = int(trade['tradeQuantity'])
                        print('price matched checking qty ',conversation_lot_quantity,trade_quantity)
                        if trade_quantity <= conversation_lot_quantity:
                            ifQty = True
                            
                        else:                      

                            print(f"SELECT SUM(tradeQuantity) as totalQuantity FROM tradeMetadata WHERE orderId = '{trade['orderId']}' AND audioFileName =  '{trade['audioFileName']}'")
                            
                            order_id = str(trade['orderId']).strip()
                            print(f"order_id: '{order_id}' (len={type(order_id)})")
                            
                            print(trade['orderId'])
                            # Take this value from tradeMetadataData variable then do this operation
                            total_quantity = sum(
                                int(row['tradeQuantity']) for row in tradeMetadataData
                                if str(row['orderId']) == str(trade['orderId']) and str(row['batchId']) == str(batch_id)
                                and row['tradeQuantity'] is not None and str(row['tradeQuantity']).strip() != ''
                            )
                            result2 = {'totalQuantity': total_quantity}
                            
                            if result2 and result2['totalQuantity'] is not None:
                                total_quantity = result2['totalQuantity']
                                print(total_quantity)
                                print('Checking for multiple Qty- ',conversation_lot_quantity)
                                if int(total_quantity) <= conversation_lot_quantity:
                                    ifQty = True
                                else:
                                    print('Checking quantity from lotMapping table 1',trade['symbol'])
                                    
                                    if trade['symbol'] == None:
                                        trade['symbol'] = 'NA'
                                    print(trade['symbol'].lower())
                                    # Get value using lotQuantityMappingData local variable
                                    print(len(lotQuantityMappingData))
                                    result3 = None
                                    # result3 = next(
                                    #     (row for row in lotQuantityMappingData 
                                    #      if (row.get('scriptName', '').lower() == trade['symbol'].lower() or 
                                    #          row.get('symbol', '').lower() == trade['symbol'].lower())),
                                    #     None
                                    # )
                                    for mapping in lotQuantityMappingData:
                                        # Check if symbol matches
                                        if mapping.get('symbol') == trade['symbol'] or mapping.get('symbol') == trade['symbol'].replace("EQ",""):
                                            # Check if scriptName matches any of the variation fields
                                            print('Found match',cr)
                                            script_name = (cr.get('scriptName') or '').lower()
                                            if (script_name == (mapping.get('scriptName') or '').lower() or
                                                script_name == (mapping.get('variation1') or '').lower() or
                                                script_name == (mapping.get('variation2') or '').lower() or
                                                script_name == (mapping.get('variation3') or '').lower()):
                                               result3 = mapping
                                            
                                    print(232332)
                                    if result3 is not None and result3['quantity'] is not None and result3['quantity'] != "":
                                        finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                        print('Checking for multiple Qty from lottable- ',finalLotQty,total_quantity)
                                        if int(total_quantity) <= finalLotQty:
                                            ifQty = True

                        if cr['currentMarketPrice'] == 'YES' and (ifScript == False and ifQty == False):
                            ifPrice = False
                        if len(conversation_row) == 1 and ifScript == False:
                            if ifQty == True and ifPrice == False:
                                ifQty = False
                        if ifQty == False:
                            for script_name, stats in summary.items():
                                if script_name == cr['scriptName'] or (script_name == 'EMPTY_SCRIPT' and cr['scriptName'] == ''):
                                    if stats['total_quantity'] == trade['tradeQuantity'] or stats['average_quantity'] == trade['tradeQuantity']:
                                        ifQty = True
                        conversation_row[index]['result'] = {'ifScript':ifScript, 'ifPrice': ifPrice,'ifQty': ifQty}
                        print(conversation_row[index]['result'])
                        index = index + 1

                    

            if call_row and nearest_call_meta and 'sRecordingFileName' in nearest_call_meta:   
                print(str(conversation_row))      
                final_result = find_best_trade(conversation_row, nearest_call_meta, conversation_row)
                if len(final_result) > 0:
                    ifScript = final_result[0]['result']['ifScript']  
                    ifPrice = final_result[0]['result']['ifPrice']  
                    ifQty = final_result[0]['result']['ifQty']  
                    if ifScript == True and ifPrice == True and ifQty == True:
                                
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details matching', 'tag3': '' }

                    elif ifScript == True and ifPrice == True and ifQty == False:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                    
                    elif ifScript == True and ifPrice == False and ifQty == True:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price' }
                    
                    elif ifScript == False and ifPrice == True and ifQty == True:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                    
                    elif ifScript == True and ifPrice == False and ifQty == False:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Pre trade found','tag2': 'Details not matching', 'tag3': 'Price and Quantity' }
                    
                    elif ifScript == False and ifPrice == True and ifQty == False:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script and Quantity' }
                    
                    elif ifScript == False and ifPrice == False and ifQty == True:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script and Price' }
                    
                    else:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Non observatory call','tag2': 'Details not matching', 'tag3': 'Script, Price and Quantity' }
                        trade_metadata_id = trade['tradeMetadataId']  # Replace with your actual ID

                        # Step 3: Execute the query
                        result_1231 = [row for row in tradeAudioMappingData if row['tradeMetadataId'] == trade_metadata_id]
                        # cursor.execute(query, (trade_metadata_id,))

                        # Step 4: Fetch and print the result
                        # result_1231 = cursor.fetchall()
                        idLastRow = False
                        all3 = False
                        if result_1231[len(result_1231)-1]['id'] == trade['id']:
                                idLastRow = True
                        if idLastRow == True:
                            for row_1231 in result_1231:
                                
                                if row_1231['isScript'] != 0 or row_1231['isPrice'] != 0 or row_1231['isQuantity'] != 0:
                                    all3 = True
                            
                            if all3 == False:    
                                trade_meta_data = {}
                                nearest_call_meta = {}
                                conversation_row = None
                                result = {}
                                        
                                alNumber = trade['alNumber']
                                audio_file_name = ''
                                process_call_id = ''
                                trade_using_client = False
                                if alNumber is None or alNumber == "":
                                    alNumber = trade['regNumber']
                                    print("**************START WITHOUT AL *********************** "+str(trade['id']))
                                    trade['clientCode'] = str(trade['clientCode']).strip()
                                    print(trade['clientCode'])
                                    trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_1(trade,batch_id,True)
                                    print(len(nearest_call_meta))
                                    if len(nearest_call_meta) == 0:
                                        print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                                        trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id,True)
                                        print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                                    trade_using_client = True
                                    print("**************END WITHOUT AL*********************** "+str(trade['id']))
                                else:
                                    print("**************START WITHOUT CLIENT CODE*********************** "+str(trade['id']))
                                    trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_2(trade,batch_id,True)
                                
                                    print("**************END WITHOUT CLIENT CODE*********************** "+str(trade['id']))
                                    print(len(nearest_call_meta))
                                    if len(nearest_call_meta) == 0:
                                        print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                                        trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id,True)
                                        print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                                print(nearest_call_meta)
                                if nearest_call_meta and len(nearest_call_meta) > 0:
                                    print('------ADDING NEW POST TRADE')
                                    for call_meta in nearest_call_meta:
                                        print('', trade['tradeMetadataId'])
                                        print("SELECT * FROM tradeAudioMapping WHERE tradeMetadataId = "+str(trade['tradeMetadataId']) + " and batchId = "+str(batch_id) + " and audioFileName='"+str(call_meta['sRecordingFileName'])+"'")
                                        trade_metadata_rows = [
                                            row for row in tradeAudioMappingData
                                            if row['tradeMetadataId'] == trade['tradeMetadataId']
                                            and row['batchId'] == batch_id
                                            and row['audioFileName'] == call_meta['sRecordingFileName']
                                        ]
                                        print('done fetching')
                                        if trade_metadata_rows and len(trade_metadata_rows) == 0:
                                            insert_query = """
                                                    INSERT INTO tradeAudioMapping (
                                                        tradeMetadataId,
                                                        orderId,
                                                        clientCode,
                                                        regNumber,
                                                        alNumber,
                                                        tradeDate,
                                                        orderPlacedTime,
                                                        instType,
                                                        expiryDate,
                                                        optionType,
                                                        symbol,
                                                        comScriptCode,
                                                        scripName,
                                                        strikePrice,
                                                        tradeQuantity,
                                                        tradePrice,
                                                        tradeValue,
                                                        lotQty,
                                                        voiceRecordingConfirmations,
                                                        audioFileName,
                                                        batchId
                                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                    """
                                            add_result = (trade['tradeMetadataId'],trade['orderId'],trade['clientCode'],trade['regNumber'],trade['alNumber'], trade['tradeDate'],trade['orderPlacedTime'],trade['instType'],trade['expiryDate'],trade['optionType'],trade['symbol'],trade['comScriptCode'],trade['scripName'],trade['strikePrice'],trade['tradeQuantity'],trade['tradePrice'],trade['tradeValue'],trade['lotQty'],result['tag1'],call_meta['sRecordingFileName'],trade['batchId'])
                                            cursor.execute(insert_query, add_result)
                                            connection.commit()
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'No pre trade found','tag2': 'Details not matching', 'tag3': 'Script, Price and Quantity' }
        if voiceResult == 'Post trade found':
            conversation_row = []
            print(len(callMetadata))
            nearest_call_meta = next(
                (row for row in callMetadata if row['callStartDate'] == trade_date and row['sRecordingFileName'] == trade['audioFileName'] and row['batchId'] == batch_id),
                None
            )
            print(11)
            call_row = next(
                (row for row in callsData if row['audioName'] == trade['audioFileName'] and row['batchId'] == batch_id),
                None
            )
            if call_row:
                    call_id = call_row['id']

                    if call_row['status'] == 'UnsupportedLanguage':
                        return trade, {},{}, {'tag1': 'Unsupported Language','tag2': '', 'tag3': '' }
                    conversation_row = [
                        row for row in callConversationData
                        if row['callId'] == call_id
                    ]
                    conversationLotQty = 0
                    conversationTradePrice = 0.0
                    conversationScriptName = ''
                    conversation_row_count = 0.0
                    
                    if (conversation_row and len(conversation_row) == 0) or not conversation_row:
                        return trade, nearest_call_meta,{}, {'tag1': 'Non observatory call','tag2': '', 'tag3': '' }
                    index = 0
                    checkAllScriptEmpty = False
                    allStockSame = False
                    checkIfSingle = False
                    indexScript = 0
                    allStockSame_scriptname = ''

                    grouped_with_empty = group_by_script_name(conversation_row)
                    summary = get_script_summary(grouped_with_empty)

                    for cr in conversation_row:
                        if cr['scriptName'] == "":
                            indexScript = indexScript + 1
                            allStockSame_scriptname = ''
                        else:
                            if allStockSame_scriptname == '':
                                allStockSame_scriptname = cr['scriptName']
                            
                            if allStockSame_scriptname == cr['scriptName']:
                                allStockSame = True
                            else:
                                allStockSame = False
                    

                    if indexScript == len(conversation_row):
                        checkAllScriptEmpty = True
                        checkIfSingle = True
                        allStockSame = True
                    for cr in conversation_row:
                        print(cr['lotQuantity'])
                        print(cr['tradePrice'])
                        print('************')
                        print(cr['scriptName'],trade['scripName'],trade['symbol'])
                        if checkAllScriptEmpty:
                            isCompanyMatching = find_matching_lot_quantity_mapping(trade,cr) or match_company_names(cr['scriptName'],trade['scripName']) or match_company_names(cr['scriptName'],trade['symbol'])
                            print("is company name matching3",isCompanyMatching)
                            if cr['lotQuantity'] is not None and cr['lotQuantity'] != '':
                                try:
                                    conversationLotQty =  int(float(cr['lotQuantity']))
                                except Exception as e:
                                    print(str(e))

                            if cr['tradePrice'] is not None and cr['tradePrice'] != '':
                                try:
                                    conversationTradePrice = float(cr['tradePrice'])
                                except Exception as e:
                                    print(str(cr['tradePrice']))
                            
                            if checkIfSingle:
                                if cr['scriptName'] is not None and cr['scriptName'] != '' and (isCompanyMatching):
                                    conversationScriptName = conversationScriptName + "" +cr['scriptName']
                                else:
                                    if cr['scriptName'] is not None:
                                        print('Checking company names',cr['scriptName'])
                                        print(trade['scripName'])
                                        print(trade['symbol'])
                                        if find_matching_lot_quantity_mapping(trade,cr) or match_company_names(cr['scriptName'],trade['scripName']) or match_company_names(cr['scriptName'],trade['symbol']):
                                            conversationScriptName = conversationScriptName + "" +cr['scriptName']
                            if len(conversation_row) == 1:
                                allStockSame = True
                                
                        else:
                            isCompanyMatching = find_matching_lot_quantity_mapping(trade,cr) or match_company_names(cr['scriptName'],trade['scripName']) or match_company_names(cr['scriptName'],trade['symbol'])
                            # print("is company name matching4",isCompanyMatching)
                            if cr['lotQuantity'] is not None and cr['lotQuantity'] != '' and ( conversationScriptName != "" or isCompanyMatching or allStockSame):
                                
                                try:
                                    conversationLotQty = conversationLotQty + int(float(cr['lotQuantity']))
                                except Exception as e:
                                    print(str(cr['lotQuantity']))

                                
                            if cr['tradePrice'] is not None and cr['tradePrice'] != '' and (conversationScriptName != "" or isCompanyMatching):
                                try:
                                    conversationTradePrice = conversationTradePrice + float(cr['tradePrice'])
                                    conversation_row_count = conversation_row_count + 1
                                except Exception as e:
                                    print(str(cr['tradePrice']))
                               
                            if cr['scriptName'] is not None and cr['scriptName'] != '' and (isCompanyMatching):
                                conversationScriptName = conversationScriptName + " " +cr['scriptName']
                            
                            print("cscript - ",conversationScriptName)
                            print("clotQty - ",conversationLotQty)
                            if conversationTradePrice != 0.0:
                                conversationTradePrice = conversationTradePrice/ conversation_row_count
                            print("ctradePrice - ",conversationTradePrice)
                        
                        

                        ifScript= False
                        ifPrice = False
                        ifQty = False  

                        if conversationScriptName != "" and (trade['symbol'] in conversationScriptName or conversationScriptName in trade['symbol']):
                            ifScript = True
                        elif conversationScriptName != "" and (trade['scripName'] in conversationScriptName or conversationScriptName in trade['scripName']):
                            ifScript = True
                        else:
                            if conversationScriptName != "":
                                print('Checking company names')
                                if find_matching_lot_quantity_mapping(trade,cr) or match_company_names(trade['symbol'],conversationScriptName) or match_company_names(conversationScriptName,trade['symbol']):
                                    ifScript = True
                                if find_matching_lot_quantity_mapping(trade,cr) or match_company_names(trade['scripName'],conversationScriptName) or match_company_names(conversationScriptName,trade['scripName']):
                                    ifScript = True
                        if ifScript == False:
                            ifScript = find_matching_lot_quantity_mapping(trade,cr)
                            

                        if conversationTradePrice is not None and conversationTradePrice != '' and conversationTradePrice != 0.0:
                            print(trade['strikePrice'])
                            print(cr['strikePrice'])
                            print("current market price", cr['currentMarketPrice'])
                            conversation_trade_price =conversationTradePrice
                            trade_price = float(trade['tradePrice'])
                            print("tradePrice - ",trade_price)
                            lower_diff, upper_diff = get_price_diff_range(trade_price)
                            print((trade_price - lower_diff <= conversation_trade_price <= trade_price + upper_diff))
                            cond1 = (trade_price - lower_diff <= conversation_trade_price <= trade_price + upper_diff)
                            lower_diff2, upper_diff2 = get_price_diff_range(conversation_trade_price)
                            print((conversation_trade_price - lower_diff2 <= trade_price <= conversation_trade_price + upper_diff2))
                            cond2 = (conversation_trade_price - lower_diff2 <= trade_price <= conversation_trade_price + upper_diff2)
                            if cond1 or cond2:
                                ifPrice = True

                        if ifPrice == False and (trade['strikePrice'] is not None and cr['strikePrice'] is not  None and trade['strikePrice'] != "" and  cr['strikePrice'] != "" and int(float(trade['strikePrice'])) == cr['strikePrice']):
                            ifPrice = True

                        print("checking ifPrice value - ",ifPrice)
                        print("current market price - ",cr['currentMarketPrice'])

                        if ifPrice == False:
                            for script_name, stats in summary.items():
                                if script_name == cr['scriptName'] or (script_name == 'EMPTY_SCRIPT' and cr['scriptName'] == ''):
                                    if stats['average_trade_price'] == trade['tradePrice'] or stats['average_strike_price'] == trade['strikePrice']:
                                        ifPrice = True

                        if ifPrice == False and cr['currentMarketPrice'] == 'YES':
                            ifPrice = True
                        
                            
                        conversation_lot_quantity = conversationLotQty
                        trade_quantity = int(trade['tradeQuantity'])
                        print('price matched checking qty ',conversation_lot_quantity,trade_quantity)
                        if trade_quantity <= conversation_lot_quantity:
                            ifQty = True
                            
                        else:
                            

                            print("Checking for multiple Qty-"+str( trade['tradeDate']))
                            print("Checking for multiple Qty-"+str( trade['orderPlacedTime']))
                            print(f"SELECT SUM(tradeQuantity) as totalQuantity FROM tradeMetadata WHERE orderId = '{trade['orderId']}' AND audioFileName =  '{trade['audioFileName']}'")
                            
                            order_id = str(trade['orderId']).strip()

                            total_quantity = sum(
                                int(row['tradeQuantity']) for row in tradeMetadataData
                                if str(row['orderId']) == str(trade['orderId']) and str(row['batchId']) == str(batch_id)
                                and row['tradeQuantity'] is not None and str(row['tradeQuantity']).strip() != ''
                            )
                            result2 = {'totalQuantity': total_quantity}
                            if result2 and result2['totalQuantity'] is not None:
                                total_quantity = result2['totalQuantity']
                                print(total_quantity)
                                print('Checking for multiple Qty- ',conversation_lot_quantity)
                                if int(total_quantity) <= conversation_lot_quantity:
                                    ifQty = True
                                else:
                                    print('Checking quantity from lotMapping table 1',trade['symbol'])
                                    if trade['symbol'] == None:
                                        trade['symbol'] = 'NA'
                                    print(trade['symbol'].lower())
                                    # Get value using lotQuantityMappingData local variable
                                    result3 = None
                                    # result3 = next(
                                    #     (row for row in lotQuantityMappingData 
                                    #      if (row.get('scriptName', '').lower() == trade['symbol'].lower() or 
                                    #          row.get('symbol', '').lower() == trade['symbol'].lower())),
                                    #     None
                                    # )
                                    for mapping in lotQuantityMappingData:
                                        # Check if symbol matches
                                        if mapping.get('symbol') == trade['symbol'] or mapping.get('symbol') == trade['symbol'].replace("EQ",""):
                                            # Check if scriptName matches any of the variation fields
                                            print('Found match2',cr)
                                            script_name = (cr.get('scriptName') or '').lower()
                                            if (script_name == (mapping.get('scriptName') or '').lower() or
                                                script_name == (mapping.get('variation1') or '').lower() or
                                                script_name == (mapping.get('variation2') or '').lower() or
                                                script_name == (mapping.get('variation3') or '').lower()):
                                               result3 = mapping
                                    print(232332)
                                    if result3 is not None and result3['quantity'] is not None and result3['quantity'] != "":
                                        finalLotQty = conversation_lot_quantity * int(result3['quantity'])
                                        print('Checking for multiple Qty from lottable- ',finalLotQty,total_quantity)
                                        if int(total_quantity) <= finalLotQty:
                                            ifQty = True

                        if cr['currentMarketPrice'] == 'YES' and (ifScript == False and ifQty == False):
                            ifPrice = False
                        if len(conversation_row) == 1 and ifScript == False:
                            if ifQty == True and ifPrice == False:
                                ifQty = False
                        if ifQty == False:
                            for script_name, stats in summary.items():
                                if script_name == cr['scriptName'] or (script_name == 'EMPTY_SCRIPT' and cr['scriptName'] == ''):
                                    if stats['total_quantity'] == trade['tradeQuantity'] or stats['average_quantity'] == trade['tradeQuantity']:
                                        ifQty = True
                        conversation_row[index]['result'] = {'ifScript':ifScript, 'ifPrice': ifPrice,'ifQty': ifQty}
                        print(conversation_row[index]['result'])
                        
                        index = index + 1

            print('1ksdjfkldsfkdsjfkdjf**********jfdfhdkjsh')
            print(nearest_call_meta)
            if call_row and nearest_call_meta and 'sRecordingFileName' in nearest_call_meta:         
                final_result = find_best_trade(conversation_row, nearest_call_meta, conversation_row)
                print('2ksdjfkldsfkdsjfkdjf**********jfdfhdkjsh')
                if len(final_result) > 0:
                    ifScript = final_result[0]['result']['ifScript']  
                    ifPrice = final_result[0]['result']['ifPrice']  
                    ifQty = final_result[0]['result']['ifQty']  
                    if ifScript == True and ifPrice == True and ifQty == True:
                                
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details matching', 'tag3': '' }

                    elif ifScript == True and ifPrice == True and ifQty == False:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Quantity' }
                    
                    elif ifScript == True and ifPrice == False and ifQty == True:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price' }
                    
                    elif ifScript == False and ifPrice == True and ifQty == True:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Script' }
                    
                    elif ifScript == True and ifPrice == False and ifQty == False:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'Post trade found','tag2': 'Details not matching', 'tag3': 'Price and Quantity' }
                    
                    elif ifScript == False and ifPrice == True and ifQty == False:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'No Post trade found','tag2': 'Details not matching', 'tag3': 'Script and Quantity' }
                    
                    elif ifScript == False and ifPrice == False and ifQty == True:
                        return trade, nearest_call_meta,conversation_row, {'tag1': 'No Post trade found','tag2': 'Details not matching', 'tag3': 'Script and Price' }
                    
                    else:
                        return trade, nearest_call_meta,{}, {'tag1': 'Non observatory call','tag2': 'Details not matching', 'tag3': 'Script, Price and Quantity' }
                        
        

        return trade, {},{}, {'tag1': 'No call record found','tag2': '', 'tag3': '' }
    except Exception as e:
        print(str(e))

def evaluate_trade_result_part2(row):
    is_script = row['isScript'] == 1
    is_price = row['isPrice'] == 1
    is_quantity = row['isQuantity'] == 1

    score = sum([is_script, is_price, is_quantity])

    if score == 3:
        return score, {
            'tag1': 'Pre trade found',
            'tag2': 'Details matching',
            'tag3': ''
        }
    elif score == 2:
        missing = []
        if not is_script: missing.append("Script")
        if not is_price: missing.append("Price")
        if not is_quantity: missing.append("Quantity")
        return score, {
            'tag1': 'Pre trade found',
            'tag2': 'Details not matching',
            'tag3': ', '.join(missing)
        }
    elif score == 1:
        missing = []
        if not is_script: missing.append("Script")
        if not is_price: missing.append("Price")
        if not is_quantity: missing.append("Quantity")
        if is_script:
            return score, {
            'tag1': 'Pre trade found',
            'tag2': 'Details not matching',
            'tag3': ', '.join(missing)
            }
        return score, {
            'tag1': 'No pre trade found',
            'tag2': 'Details not matching',
            'tag3': ', '.join(missing)
        }
    else:
        return score, {
            'tag1': 'Non observatory call',
            'tag2': '',
            'tag3': ''
        }
    
def evaluate_trade_result_part3(row):
    print('===> Inside evaluate_trade_result_part3')
    is_script = row['isScript'] == 1
    is_price = row['isPrice'] == 1
    is_quantity = row['isQuantity'] == 1

    score = sum([is_script, is_price, is_quantity])
    print(score)
    if score == 3:
        return score, {
            'tag1': 'Post trade found',
            'tag2': 'Details matching',
            'tag3': ''
        }
    elif score == 2:
        missing = []
        if not is_script: missing.append("Script")
        if not is_price: missing.append("Price")
        if not is_quantity: missing.append("Quantity")
        return score, {
            'tag1': 'Post trade found',
            'tag2': 'Details not matching',
            'tag3': ', '.join(missing)
        }
    elif score == 1:
        missing = []
        if not is_script: missing.append("Script")
        if not is_price: missing.append("Price")
        if not is_quantity: missing.append("Quantity")
        if is_script:
            return score, {
            'tag1': 'Post trade found',
            'tag2': 'Details not matching',
            'tag3': ', '.join(missing)
            }
        
        return score, {
            'tag1': 'No Post trade found',
            'tag2': 'Details not matching',
            'tag3': ', '.join(missing)
        }
    else:
        return score, {
            'tag1': 'Non observatory call',
            'tag2': '',
            'tag3': ''
        }


def find_best_trade_part2(rows):
    best_row = None
    best_score = -1
    best_tags = {}

    for row in rows:
        if 'pre trade' in row['voiceRecordingConfirmations'].lower():
            score, tags = evaluate_trade_result_part2(row)
        else:
            score, tags = evaluate_trade_result_part3(row)
        if score > best_score:
            best_score = score
            best_row = row
            best_tags = tags

    return best_row, best_tags

def find_matching_lot_quantity_mapping(trade, conversation_row):
    print('===> Inside find_matching_lot_quantity_mapping')
    """
    Find matching rows in lotQuantityMappingData based on trade symbol and script name.
    
    Args:
        trade (dict): Trade dictionary containing 'symbol' key
        conversation_row (dict): Conversation row containing 'scriptName' and variation fields
        
    Returns:
        dict or None: The matching row from lotQuantityMappingData if found, else None
    """
    if not trade or 'symbol' not in trade or not conversation_row or conversation_row['scriptName'] is None or trade['symbol'] is None or conversation_row['scriptName'] == '':
        return False
    print(trade['symbol'],conversation_row['scriptName'])    
    # Assuming lotQuantityMappingData is a global variable or passed as parameter
    for mapping in lotQuantityMappingData:
        # Check if symbol matches
        if mapping.get('symbol') == trade['symbol'] or mapping.get('symbol') == trade['symbol'].replace("EQ",""):
            # Check if scriptName matches any of the variation fields
            print('Found match')
            script_name = conversation_row.get('scriptName', '').lower() 

            if (script_name == (mapping.get('scriptName') or '').lower() or
                script_name == (mapping.get('variation1') or '').lower() or
                script_name == (mapping.get('variation2') or '').lower() or
                script_name == (mapping.get('variation3') or '').lower()):
                return True
            print(1)
            print(match_company_names(script_name,(mapping.get('scriptName') or '').lower()))
            print(match_company_names(script_name,(mapping.get('variation1') or '').lower()))
            print(match_company_names(script_name,(mapping.get('variation2') or '').lower()))
            print(match_company_names(script_name,(mapping.get('variation3') or '').lower()))
            
            if match_company_names(script_name,(mapping.get('scriptName') or '').lower()) or match_company_names(script_name,(mapping.get('variation1') or '').lower()) or match_company_names(script_name,(mapping.get('variation2') or '').lower()) or match_company_names(script_name,(mapping.get('variation3') or '').lower()):
                return True
            print(2)
            if match_company_names((mapping.get('scriptName') or '').lower(),script_name) or match_company_names((mapping.get('variation1') or '').lower(),script_name) or match_company_names((mapping.get('variation1') or '').lower(),script_name) or match_company_names((mapping.get('variation1') or '').lower(),script_name):
                return True
            print(3)
    return False

def execute_trademetarows(trade_metadata_rows,batch_id):
    connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
    cursor = connection.cursor(dictionary=True,buffered=True)
    for trade in trade_metadata_rows:
        print('trade Id ',trade['id'])
        trade_meta_data = {}
        nearest_call_meta = {}
        conversation_row = None
        result = {}
        alNumber = trade['alNumber']
        audio_file_name = ''
        process_call_id = 1
        trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_with_voice_confirmations(trade,batch_id)
        print(str(result))
        print('After calling find_matching_trade_with_voice_confirmations - rule_engine_v2', result)



        if result and result['tag1'] != 'No call record found' and 'tag3' in result:

            if result['tag3'] == "":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isScript = %s,isPrice = %s,isQuantity = %s
                    WHERE id = %s
                """
                update_values = (1,1,1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()
            elif result['tag3'] == "Script":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isPrice = %s,isQuantity = %s
                    WHERE id = %s
                """
                update_values = (1,1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()
            elif result['tag3'] == "Price":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isQuantity = %s, isScript = %s
                    WHERE id = %s
                """
                update_values = (1,1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()
            elif result['tag3'] == "Quantity":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isScript = %s, isPrice = %s
                    WHERE id = %s
                """
                update_values = (1,1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()
            elif result['tag3'] == "Script and Price":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isQuantity = %s
                    WHERE id = %s
                """
                update_values = (1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()
            elif result['tag3'] == "Script and Quantity":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isPrice = %s
                    WHERE id = %s
                """
                update_values = (1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()

            elif result['tag3'] == "Price and Quantity":
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping
                    SET isScript = %s
                    WHERE id = %s
                """
                update_values = (1,trade['id'])


                cursor.execute(update_query, update_values)
                connection.commit()
            elif result['tag3'] == "Script, Price and Quantity":
                print('###')

    cursor.close()
    connection.close()


def execute_trademetarows_optimized(trade_metadata_rows, batch_id, batch_size=10000,connection=None,cursor=None):
    """
    Optimized version of execute_trademetarows with batch processing and batch updates
    """
    total_records = len(trade_metadata_rows)
    processed_records = 0
    total_batches = (total_records + batch_size - 1) // batch_size
    start_time = datetime.now()
    
    print(f'Starting optimized processing of {total_records} trade metadata rows in batches of {batch_size}')
    
    # Batch collections for different update types
    batch_updates = {
        "": [],  # All fields (isScript=1, isPrice=1, isQuantity=1)
        "Script": [],  # isPrice=1, isQuantity=1
        "Price": [],  # isScript=1, isQuantity=1
        "Quantity": [],  # isScript=1, isPrice=1
        "Script and Price": [],  # isQuantity=1
        "Script and Quantity": [],  # isPrice=1
        "Price and Quantity": []  # isScript=1
    }
    
    for batch_start in range(0, total_records, batch_size):
        batch_end = min(batch_start + batch_size, total_records)
        batch_num = batch_start // batch_size + 1
        batch_start_time = datetime.now()
        
        print(f'Processing batch {batch_num}/{total_batches}: records {batch_start + 1} to {batch_end}')
        time.sleep(10)
        try:
            # Clear batch collections
            for key in batch_updates:
                batch_updates[key] = []
            
            # Process current batch
            current_batch = trade_metadata_rows[batch_start:batch_end]
            index = 0
            for trade in current_batch:
                index = index + 1
                print("**************************************************************************************************")
                print(index)
                print("**************************************************************************************************")
                trade_meta_data, nearest_call_meta, conversation_row, result = find_matching_trade_with_voice_confirmations(trade, batch_id)
                print("\n\n")
                print("Result - ",str(result),nearest_call_meta)
                if result and result['tag1'] != 'No call record found' and result['tag1'] != 'Non observatory call' and result['tag1'] != 'Unsupported Language' and 'tag3' in result:
                    tag3 = result['tag3']
                    if tag3 in batch_updates:
                        batch_updates[tag3].append(trade['id'])
                    elif tag3 == "Script, Price and Quantity":
                        # No update needed for this case
                        pass
                elif result and result['tag1'] == 'Unsupported Language':
                    print(f"Skipping trade {trade['id']} due to unsupported language")
                    continue

            print('Going to update tradeAudioMapping table...   ',batch_num)
            # time.sleep(120)
            # Execute batch updates
            updates_executed = 0
            
            # All fields update (isScript=1, isPrice=1, isQuantity=1)
            if batch_updates[""]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isScript = 1, isPrice = 1, isQuantity = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates[""]))
                cursor.execute(update_query, batch_updates[""])
                updates_executed += len(batch_updates[""])
            
            # Script missing (update isPrice=1, isQuantity=1)
            if batch_updates["Script"]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isPrice = 1, isQuantity = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates["Script"]))
                cursor.execute(update_query, batch_updates["Script"])
                updates_executed += len(batch_updates["Script"])
            
            # Price missing (update isScript=1, isQuantity=1)
            if batch_updates["Price"]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isScript = 1, isQuantity = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates["Price"]))
                cursor.execute(update_query, batch_updates["Price"])
                updates_executed += len(batch_updates["Price"])
            
            # Quantity missing (update isScript=1, isPrice=1)
            if batch_updates["Quantity"]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isScript = 1, isPrice = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates["Quantity"]))
                cursor.execute(update_query, batch_updates["Quantity"])
                updates_executed += len(batch_updates["Quantity"])
            
            # Script and Price missing (update isQuantity=1)
            if batch_updates["Script and Price"]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isQuantity = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates["Script and Price"]))
                cursor.execute(update_query, batch_updates["Script and Price"])
                updates_executed += len(batch_updates["Script and Price"])
            
            # Script and Quantity missing (update isPrice=1)
            if batch_updates["Script and Quantity"]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isPrice = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates["Script and Quantity"]))
                cursor.execute(update_query, batch_updates["Script and Quantity"])
                updates_executed += len(batch_updates["Script and Quantity"])
            
            # Price and Quantity missing (update isScript=1)
            if batch_updates["Price and Quantity"]:
                update_query = """
                    UPDATE auditNexDb.tradeAudioMapping 
                    SET isScript = 1
                    WHERE id IN (%s)
                """ % ','.join(['%s'] * len(batch_updates["Price and Quantity"]))
                cursor.execute(update_query, batch_updates["Price and Quantity"])
                updates_executed += len(batch_updates["Price and Quantity"])
            
            # Single commit for all updates in this batch
            connection.commit()
            
            processed_records += len(current_batch)
            batch_end_time = datetime.now()
            batch_duration = (batch_end_time - batch_start_time).total_seconds()
            
            # Calculate ETA
            if processed_records > 0:
                avg_time_per_record = (batch_end_time - start_time).total_seconds() / processed_records
                remaining_records = total_records - processed_records
                estimated_remaining_time = avg_time_per_record * remaining_records
                eta = datetime.now() + timedelta(seconds=estimated_remaining_time)
                
                print(f"Batch {batch_num}/{total_batches} completed in {batch_duration:.1f}s. "
                      f"Updated {updates_executed} records. "
                      f"Progress: {processed_records}/{total_records} ({processed_records/total_records*100:.1f}%). "
                      f"ETA: {eta.strftime('%H:%M:%S')}")
            else:
                print(f"Batch {batch_num}/{total_batches} completed in {batch_duration:.1f}s. "
                      f"Updated {updates_executed} records. "
                      f"Progress: {processed_records}/{total_records} ({processed_records/total_records*100:.1f}%)")
                      
        except Exception as e:
            print(f"Error processing batch {batch_num}: {str(e)}")
            connection.rollback()
            # continue
    
    total_duration = (datetime.now() - start_time).total_seconds()
    print(f"Optimized processing completed in {total_duration:.1f} seconds")

def normalize_order_id(value):
    try:
        # if it’s numeric (float, int, or numeric string), normalize
        return str(int(float(value)))
    except (ValueError, TypeError):
        # if not numeric (e.g. "oeruewi762"), keep as string
        return str(value)
    
def process_rule_engine(current_date,batch_id):
    global callMetadata, callsData, tradeAudioMappingData, callConversationData, tradeMetadataData,lotQuantityMappingData
    connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
    cursor = connection.cursor(dictionary=True,buffered=True)

    cursor.execute("SELECT * FROM callMetadata WHERE batchId = %s", (batch_id,))
    callMetadata = cursor.fetchall()

    cursor.execute("SELECT * FROM auditNexDb.call WHERE batchId = %s", (batch_id,))
    callsData = cursor.fetchall()

    cursor.execute("SELECT * FROM tradeAudioMapping WHERE batchId = %s", (batch_id,))
    rows_tradeAudioMappingData = cursor.fetchall()
    print('krunal 3')
    for tr1 in rows_tradeAudioMappingData:
        tr1["orderId"] = normalize_order_id(tr1["orderId"])
        tradeAudioMappingData.append(tr1)

    cursor.execute("SELECT * FROM callConversation WHERE batchId = %s", (batch_id,))
    callConversationData = cursor.fetchall()

    cursor.execute("SELECT * FROM tradeMetadata WHERE batchId = %s", (batch_id,))
    rows = cursor.fetchall()
    
    for tr1 in rows:
        tr1["orderId"] = normalize_order_id(tr1["orderId"])
        tradeMetadataData.append(tr1)

    # Gather data from table lotQuantityMapping and store in lotQuantityMappingData variable using batchId
    cursor.execute("SELECT * FROM lotQuantityMapping")
    lotQuantityMappingData = cursor.fetchall()

    trade_metadata_rows = tradeAudioMappingData
    last_id = 1
    if tradeAudioMappingData and len(tradeAudioMappingData) > 0:
        last_id = tradeAudioMappingData[len(tradeAudioMappingData)-1]['id']

    print('Last ID fetched from tradeAudioMapping: %s', last_id)
    execute_trademetarows_optimized(trade_metadata_rows,batch_id,10000,connection,cursor)
    print("----------------------------------------------------------------------------------------------------")

    # print('fetching after ',last_id)
    # cursor.execute("SELECT * FROM tradeAudioMapping WHERE batchId = %s and id > %s", (batch_id, last_id))
    # trade_metadata_rows = cursor.fetchall()
    # tradeAudioMappingData.extend(trade_metadata_rows)

    # execute_trademetarows(trade_metadata_rows,batch_id)


    connection2 = mysql.connector.connect(**db_config)
    cursor2 = connection2.cursor(dictionary=True,buffered=True)
    cursor2.execute("SELECT * FROM tradeAudioMapping WHERE batchId = %s", (batch_id,))
    tradeAudioMappingData = cursor2.fetchall()

    # Get total count of records to process
    
    cursor2.execute("SELECT COUNT(*) as count FROM tradeMetadata WHERE (voiceRecordingConfirmations is NULL or voiceRecordingConfirmations = '') AND batchId = %s", (batch_id,))
    result = cursor2.fetchone()
    total_records = result['count']
    print(f'Total records to process: {total_records}')
    cursor2.execute("SELECT * FROM tradeMetadata  WHERE  (voiceRecordingConfirmations is NULL or voiceRecordingConfirmations = '') AND batchId = "+str(batch_id))

    # cursor.execute("SELECT * FROM tradeMetadata  WHERE id=418168 and batchId = "+str(batch_id))
    print('done fetching')
    trade_metadata_rows_original = cursor2.fetchall()
    # Build lookup dictionaries for better performance
    doneIndex = 0
    cursor2.close()
    connection2.close()
    for trade in trade_metadata_rows_original:
        trade_metadata_id = trade['id']
        doneIndex += 1
        print("Processing trade", doneIndex)
        rows = [row for row in tradeAudioMappingData if row['tradeMetadataId'] == trade_metadata_id]

        if not rows:
            print("No records found for tradeMetadataId =", trade_metadata_id)
        else:
            
            best_trade, tags = find_best_trade_part2(rows)
            print("Best trade ID:", best_trade['id'])
            print("Matching Tags:", tags)
            
            # Check for specific tag1 values and UnsupportedLanguage status
            call_result_n = None
            if tags['tag1'] in ['No pre trade found', 'No post trade found', 'Non observatory call']:
                if rows and 'audioFileName' in rows[0]:
                    # Check if audioFileName exists in callsData
                    unsupported_call = next(
                        (call for call in callsData if call.get('audioName') == rows[0]['audioFileName'] and call.get('status') == 'UnsupportedLanguage'),
                        None
                    )
                    if unsupported_call:
                        tags['tag1'] = 'Unsupported Language'
                        tags['tag2'] = ''
                        tags['tag3'] = ''
                        call_result_n = unsupported_call
                        best_trade = rows[0]
                        print("Found UnsupportedLanguage call, updated tag1 to 'Unsupported Language'")
            
            # If call_result_n was not set by UnsupportedLanguage logic, use the original logic
            if not call_result_n:
                # cursor.execute("SELECT * FROM tradeMetadata WHERE audioFileName='"+str(best_trade['audioFileName'])+"' and batchId = "+str(batch_id))
                # trade_metadata_dup_row = cursor.fetchone()
                # Select a single record from callsData variable (first match)
                call_result_n = next(
                    (row for row in callsData if row['audioName'] == best_trade['audioFileName'] and row['batchId'] == batch_id),
                    None
                )
            # print(len(callsData))
            print("kkfdsfk1")
            if not call_result_n:
                print('Call not found')
            # call_result_n = cursor.fetchone()
            
            if call_result_n:
                print("Updating for id:", trade['id'])
                referenceLink = int(str(call_result_n["id"]))
                update_query = """
                    UPDATE tradeMetadata
                    SET voiceRecordingConfirmations = %s, 
                        matchingStatus = %s, 
                        dataMissing = %s, 
                        audioFileName = %s,
                        processId = %s,
                        audioCallRef = %s
                    WHERE id = %s;
                """
                print(best_trade)
                values = (tags['tag1'], tags['tag2'], tags['tag3'], best_trade['audioFileName'],1,referenceLink,trade['id'])
                cursor.execute(update_query, values)  # Execute query with parameters
                connection.commit()  # Commit changes


                update_query = """
                    UPDATE tradeMetadata
                    SET voiceRecordingConfirmations = %s, 
                        matchingStatus = %s, 
                        dataMissing = %s, 
                        audioFileName = %s,
                        processId = %s,
                        audioCallRef = %s
                    WHERE clientCode = %s AND orderId = %s ;
                """

                values = (tags['tag1'], tags['tag2'], tags['tag3'], best_trade['audioFileName'],1,referenceLink,trade['clientCode'], trade['orderId'])
                cursor.execute(update_query, values)  # Execute query with parameters
                connection.commit()
                result = tags
            if call_result_n:
                print("kotak updating audit ans 1")
                process_call_id = call_result_n['processId']
                # select_query = """
                #     SELECT id FROM auditNexDb.auditAnswer
                #     WHERE callId = %s AND sectionId = 1 AND questionId = 1
                # """
                # cursor.execute(select_query, (call_result_n['id'],))
                # auditAnswer_row = cursor.fetchone()
                delete_query = "DELETE FROM auditNexDb.auditAnswer WHERE  sectionId = 1 AND questionId = 1 AND callId = " + str(call_result_n['id'])
                cursor.execute(delete_query)
                connection.commit()
                if False and call_result_n and auditAnswer_row:
                    print("kotak updating audit ans 2")
                    print("kotak"+str(call_result_n['id']))
                    print("kotak"+str(auditAnswer_row['id']))
                    print("kotak"+str(result['tag1']))
                    update_query = """
                        UPDATE auditNexDb.auditAnswer 
                        SET answer = %s
                        WHERE id = %s
                    """
                    update_values = (result['tag1'], auditAnswer_row['id'])


                    cursor.execute(update_query, update_values)
                    connection.commit()
                    print(result['tag1'],call_result_n['id'],auditAnswer_row['id'])
                        
                    delete_query = "DELETE FROM auditNexDb.timing WHERE auditAnswerId = " + str(auditAnswer_row['id'])
                    cursor.execute(delete_query)
                    connection.commit()
                    add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")
                    referenceT = result['tag2']
                    if result['tag3']:
                        referenceT =  referenceT + ';' + result['tag3']
                    add_result = (0,0,'',referenceT, auditAnswer_row['id'])

                    cursor.execute(add_column, add_result)
                    connection.commit()
                # if call_result_n and not auditAnswer_row:
                if call_result_n:
                    print("kotak updating audit ans 2")
                    add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")
                    add_result = (call_result_n['processId'],call_result_n['id'],1,1,1,result['tag1'],0,0)
                        


                    cursor.execute(add_column, add_result)
                    inserted_id = cursor.lastrowid  
                    connection.commit()
                    # delete_query = "DELETE FROM auditNexDb.timing WHERE auditAnswerId = " + str(inserted_id)
                    # cursor.execute(delete_query)
                    # connection.commit()
                    add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")
                    referenceT = result['tag2']
                    if result['tag3']:
                        referenceT =  referenceT + ';' + result['tag3']
                    add_result = (0,0,'',referenceT, inserted_id)

                    cursor.execute(add_column, add_result)
                    connection.commit()

    logger.info("kotak-end2")
        # delete_query = "DELETE FROM auditNexDb.lidStatus"
        # cursor.execute(delete_query)
        # connection.commit()
    logger.info("kotak-end3")
    update_query = '''UPDATE auditNexDb.batchStatus set batchStatus = %s, batchStatus = %s,batchEndTime = NOW()
                        WHERE batchDate = %s'''
    update_values = ("Complete","Complete", current_date)
    cursor.execute(update_query,update_values)
    connection.commit()
    CURRENT_BATCH_STATUS['batchStatus'] = "Complete"
    CURRENT_BATCH_STATUS['triagingStatus'] = "Complete"
    callMetadata = []
    callsData = []
    tradeAudioMappingData = []
    callConversationData = []
    tradeMetadataData = []
    lotQuantityMappingData = []

def process_rule_engine_step_1_fill_audio_not_found(current_date,batch_id):
    global REQUEST_IN_PROGRESS, CURRENT_BATCH_STATUS
    connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
    cursor = connection.cursor(dictionary=True,buffered=True)
    cursor.execute("SELECT * FROM auditNexDb.call WHERE  batchId = "+str(batch_id))
    call_result_rows = cursor.fetchall()
    logger.info('krunal rule engine step 1 '+str(batch_id))
    for callr in call_result_rows:
        logger.info('krunal rule engine step 2 '+str(callr['audioName']))
        cursor.execute("SELECT * FROM tradeAudioMapping WHERE  audioFileName = '"+str(callr['audioName'])+"'")
        trade_metadata_result_row = cursor.fetchone()
        logger.info('krunal rule engine step 3 '+str(callr['audioName']))
        if not trade_metadata_result_row:
            logger.info('krunal rule engine step 4 ')
        if not trade_metadata_result_row:
            logger.info('krunal rule engine step 5 ')
            print("krunal",callr['id'])
            select_query = """
                SELECT id FROM auditNexDb.auditAnswer
                WHERE callId = %s AND sectionId = 1 AND questionId = 1
            """
            cursor.execute(select_query, (callr['id'],))
            auditAnswer_row = cursor.fetchone()
            if callr and auditAnswer_row :
                update_query = """
                    UPDATE auditNexDb.auditAnswer
                    SET answer = %s
                    WHERE id = %s
                """
                update_values = ("No trade data found", auditAnswer_row['id'])


                cursor.execute(update_query, update_values)
                connection.commit()

            if callr and not auditAnswer_row :
                logger.info('krunal rule engine step 6 ')
                add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")
                add_result = (callr['processId'],callr['id'],1,1,1,"No trade data found",0,0)



                cursor.execute(add_column, add_result)

                connection.commit()

            select_query = """
                SELECT id FROM auditNexDb.auditAnswer
                WHERE callId = %s AND sectionId = 2 AND questionId = 2
            """
            cursor.execute(select_query, (callr['id'],))
            auditAnswer_row = cursor.fetchone()
            if callr and auditAnswer_row:
                update_query = """
                    UPDATE auditNexDb.auditAnswer
                    SET answer = %s
                    WHERE id = %s
                """
                update_values = ("No trade data found", auditAnswer_row['id'])


                cursor.execute(update_query, update_values)
                connection.commit()

            if callr and not auditAnswer_row:
                logger.info('krunal rule engine step 7 ')
                add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")
                add_result = (callr['processId'],callr['id'],1,2,2,"No trade data found",0,0)



                cursor.execute(add_column, add_result)

                connection.commit()

            select_query = """
                SELECT id FROM auditNexDb.auditAnswer
                WHERE callId = %s AND sectionId = 2 AND questionId = 3
            """
            cursor.execute(select_query, (callr['id'],))
            auditAnswer_row = cursor.fetchone()
            if callr and auditAnswer_row :
                update_query = """
                    UPDATE auditNexDb.auditAnswer
                    SET answer = %s
                    WHERE id = %s
                """
                update_values = ("No trade data found", auditAnswer_row['id'])


                cursor.execute(update_query, update_values)
                connection.commit()

            if callr and not auditAnswer_row :
                logger.info('krunal rule engine step 8 ')
                add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score) VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")
                add_result = (callr['processId'],callr['id'],1,2,3,"No trade data found",0,0)



                cursor.execute(add_column, add_result)

                connection.commit()
    cursor.close()
    connection.close()
    dataBase3 = mysql.connector.connect(
    host =os.environ.get('MYSQL_HOST'),
    user =os.environ.get('MYSQL_USER'),
    password =os.environ.get('MYSQL_PASSWORD'),
    database = os.environ.get('MYSQL_DATABASE'),
    connection_timeout= 86400000
    )
    cursorObject3 = dataBase3.cursor(buffered=True)

    update_query = """
                        UPDATE auditNexDb.batchStatus
                        SET dbInsertionStatus = %s, sttStatus = %s
                        WHERE batchDate = %s
                    """
    update_values = ("Complete", "InProgress", current_date)

    cursorObject3.execute(update_query, update_values)
    dataBase3.commit()
    CURRENT_BATCH_STATUS['dbInsertionStatus'] = "Complete"
    CURRENT_BATCH_STATUS['sttStatus'] = "InProgress"
    container_status = is_service_running('auditnex-translate-1')
    if container_status == True:
        stop_service('auditnex-translate-1')
        time.sleep(10)
    if is_service_running('auditnex-llm-extraction-1'):
        stop_service('auditnex-llm-extraction-1')

        time.sleep(10)
        container_status = is_service_running('auditnex-stt-inference-1')
        if container_status == False:
            start_service("auditnex-stt-inference-1")
            time.sleep(180)

        container_status = is_service_running('auditnex-smb-vad-1')
        if container_status == False:
            start_service("auditnex-smb-vad-1")
            time.sleep(180)
    container_status = is_service_running('auditnex-llm-extraction-q1-1')
    if container_status == True:
        stop_service("auditnex-llm-extraction-q1-1")
        time.sleep(10)
    else:
        container_status = is_service_running('auditnex-stt-inference-1')
        if container_status == False:
            start_service("auditnex-stt-inference-1")
            time.sleep(180)

        container_status = is_service_running('auditnex-smb-vad-1')
        if container_status == False:
            start_service("auditnex-smb-vad-1")
            time.sleep(180)

    REQUEST_IN_PROGRESS = False

def process_rule_engine_step_1(current_date,batch_id):
    global callMetadata
    connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )

    tradeIdsAdded = []
    cursor = connection.cursor(dictionary=True,buffered=True)
    allFileNames = []
    cursor.execute("SELECT * FROM callMetadata WHERE batchId = %s", (batch_id,))
    callMetadata = cursor.fetchall()
    for row in callMetadata:
        if not row.get('callEndDate'):
            row['callEndDate'] = row['callStartDate']
            print(row['id'], row['callEndDate'])
        if not row.get('callEndTime'):
            try:

                start_dt = datetime.strptime(row['callStartTime'], "%H:%M:%S")
                end_dt = (start_dt + timedelta(minutes=2)).time()
                row['callEndTime'] = end_dt.strftime("%H:%M:%S")
                print(row['id'], row['callStartDate'], row['callStartTime'], row['callEndDate'],   row['callEndTime'] )
            except Exception:
                row['callEndTime'] = row['callStartTime']
    cursor.execute("SELECT * FROM `call` WHERE batchId=%s", (batch_id,))
    all_call_rows = cursor.fetchall()
    for call_r in all_call_rows:
        if (call_r["lang"] != "en") and (call_r["lang"] != "hi") and (call_r["lang"] != "hinglish"):
            allFileNames.append(call_r['audioName'])


    # machine_count = 5
    # machine_api_url = ['http://10.125.9.115:5065', 'http://10.125.9.19:5065', 'http://10.125.9.69:5065', 'http://10.125.9.53:5065']
    # machine_ip_list = ['10.125.9.115', '10.125.9.19', '10.125.9.69', '10.125.9.53']

    # cursor.execute("SELECT * FROM tradeMetadata WHERE mappingStatus = 'Pending' AND batchId = %s", (batch_id,))
    # all_trades = cursor.fetchall()
    # total_trades = len(all_trades)
    # machine_count = 5

    # # Calculate startIndex and endIndex for each machine
    # indices_s = []
    # indices_e = []
    # chunk_size = total_trades // machine_count
    # remainder = total_trades % machine_count

    # start = 0
    # # Use actual row IDs for indices instead of just positions
    # cursor.execute("SELECT MIN(id) AS first_id, MAX(id) AS last_id FROM tradeMetadata WHERE batchId = %s", (batch_id,))
    # id_range = cursor.fetchone()
    # first_id = id_range['first_id']
    # last_id = id_range['last_id']

    # # Calculate chunk size based on ID range
    # total_ids = last_id - first_id + 1
    # chunk_size = total_ids // machine_count
    # remainder = total_ids % machine_count

    # start_id = first_id
    # for i in range(machine_count):
    #     end_id = start_id + chunk_size - 1
    #     if i < remainder:
    #         end_id += 1
    #     indices_s.append(start_id)
    #     indices_e.append(end_id)
    #     start_id = end_id + 1
    # # Example: indices = [(0, 19), (20, 39), ...] for 100 trades and 5 machines
    # print("Machine indices:", indices_s, indices_e)
    # for i,m_url in enumerate(machine_api_url):
    #     api_url = f"{m_url}/triagging_process_step1"
    #     payload = {
    #         "firstIndex": indices_s[i+1],
    #         "lastIndex": indices_e[i+1],
    #         "batch_id": batch_id,
    #         "current_date": current_date
    #     }
    #     logger.info(f"Triggering triagging_process_step1 for machine {api_url} with payload: {payload}")
    #     try:
    #         # response = requests.get(api_url, params=payload)
    #         logger.info(f"Triggered triagging_process_step1 for machine {i}: {response.status_code}")
    #     except Exception as e:
    #         logger.error(f"Error triggering triagging_process_step1 for machine {i}: {e}")




    cursor.execute("SELECT * FROM tradeMetadata WHERE batchId = %s", (batch_id,))
    # cursor.execute("SELECT * FROM tradeMetadata WHERE mappingStatus = 'Pending' AND batchId = %s AND id >= %s AND id <= %s", (batch_id, indices_s[0], indices_e[0]))
    all_metadata_trade = cursor.fetchall()
    for trade in all_metadata_trade:






        print("**********\n")

        trade['clientCode'] = str(trade['clientCode']).strip()
        print(trade['clientCode'])
        # trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_1(trade)
        trade_meta_data = {}
        nearest_call_meta = {}
        conversation_row = None
        result = {}

        alNumber = trade['alNumber']
        audio_file_name = ''
        process_call_id = ''
        trade_using_client = False
        if alNumber is not None and alNumber != "" and trade['regNumber'] is not None and trade['regNumber'] != "":
            print("**************START WITHOUT CLIENT CODE AND REG NUMBER*********************** "+str(trade['id']))
            trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_2(trade,batch_id)
           
            print("**************END WITHOUT CLIENT CODE AND REG NUMBER*********************** "+str(trade['id']))
            print("process_rule_engine_step_1 1",len(nearest_call_meta))
            print("process_rule_engine_step_1 2",nearest_call_meta)
            print("process_rule_engine_step_1 2-1",result)
            trade['alNumber'] = None
            print("**************START WITHOUT AL *********************** "+str(trade['id']))
            trade['clientCode'] = str(trade['clientCode']).strip()
            print(trade['clientCode'])
            trade_meta_data,nearest_call_meta_2,conversation_row,result2 = find_matching_trade_in_step_1(trade,batch_id)
            print("process_rule_engine_step_1 3",nearest_call_meta_2)
            print("process_rule_engine_step_1 4",len(nearest_call_meta_2))
            if len(nearest_call_meta_2) > 0:
                result = result2
                existing_ids = {item['id'] for item in nearest_call_meta}
                for item in nearest_call_meta_2:
                    if item['id'] not in existing_ids:
                        nearest_call_meta.append(item)
                        existing_ids.add(item['id']) 
            print("process_rule_engine_step_1 5",nearest_call_meta)
            if len(nearest_call_meta) == 0 and len(nearest_call_meta_2) == 0:
                print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id)
                print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
            trade_using_client = True
            print("**************END WITHOUT AL*********************** "+str(trade['id']))

        elif alNumber is None or alNumber == "":
            alNumber = trade['regNumber']
            print("**************START WITHOUT AL *********************** "+str(trade['id']))
            trade['clientCode'] = str(trade['clientCode']).strip()
            print(trade['clientCode'])
            trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_1(trade,batch_id,False)
            print(len(nearest_call_meta))
            if len(nearest_call_meta) == 0:
                print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id,False)
                print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
            trade_using_client = True
            print("**************END WITHOUT AL*********************** "+str(trade['id']))
        else:
            print("**************START WITHOUT CLIENT CODE*********************** "+str(trade['id']))
            trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_2(trade,batch_id,False)

            print("**************END WITHOUT CLIENT CODE*********************** "+str(trade['id']))
            print(len(nearest_call_meta))
            if len(nearest_call_meta) == 0:
                print("**************START WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
                trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_3(trade,batch_id,False)
                print("**************END WITHOUT CLIENT CODE PART 2*********************** "+str(trade['id']))
        # print(str(conversation_row))
        # print(str(nearest_call_meta))
        if (result and result['tag1'] == 'No call record found'):
            print("**************No call record found *********************** "+str(trade['id']))
            trade['clientCode'] = str(trade['clientCode']).strip()
            trade['alNumber'] = None
            print(trade['alNumber'])
            trade_meta_data,nearest_call_meta,conversation_row,result = find_matching_trade_in_step_1(trade,batch_id)
            print(len(nearest_call_meta))

        dataInserted = False
        rows_to_insert = []
        index = 0
        for call_meta in nearest_call_meta:

            if call_meta['sRecordingFileName'] not in allFileNames:

                if dataInserted == False:
                    dataInserted = True
                row = (
                    trade['id'],
                    trade['orderId'],
                    trade['clientCode'],
                    trade['regNumber'],
                    trade['alNumber'],
                    trade['tradeDate'],
                    trade['orderPlacedTime'],
                    trade['instType'],
                    trade['expiryDate'],
                    trade['optionType'],
                    trade['symbol'],
                    trade['comScriptCode'],
                    trade['scripName'],
                    trade['strikePrice'],
                    trade['tradeQuantity'],
                    trade['tradePrice'],
                    trade['tradeValue'],
                    trade['lotQty'],
                    result['tag1'],
                    call_meta['sRecordingFileName'],
                    trade['batchId']
                )
                rows_to_insert.append(row)

            index = index + 1
        if rows_to_insert:
            insert_query = """
                INSERT INTO tradeAudioMapping (
                    tradeMetadataId,
                    orderId,
                    clientCode,
                    regNumber,
                    alNumber,
                    tradeDate,
                    orderPlacedTime,
                    instType,
                    expiryDate,
                    optionType,
                    symbol,
                    comScriptCode,
                    scripName,
                    strikePrice,
                    tradeQuantity,
                    tradePrice,
                    tradeValue,
                    lotQty,
                    voiceRecordingConfirmations,
                    audioFileName,
                    batchId
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_query, rows_to_insert)
            connection.commit()

        if (result and result['tag1'] == 'No call record found'):
            try:

                update_query = """
                    UPDATE tradeMetadata
                    SET voiceRecordingConfirmations = %s

                    WHERE id = %s;
                """

                values = ('No call record found',trade['id'])
                cursor.execute(update_query, values)  # Execute query with parameters
                connection.commit()  # Commit changes

                print("Update completed successfully.")

            except mysql.connector.Error as err:
                print(f"Error: {err}")
                connection.rollback()  # Rollback the transaction in case of an error
        elif dataInserted == False and len(nearest_call_meta) > 0:
            try:

                update_query = """
                    UPDATE tradeMetadata
                    SET voiceRecordingConfirmations = %s

                    WHERE id = %s;
                """

                values = ('Unsupported Language',trade['id'])
                cursor.execute(update_query, values)  # Execute query with parameters
                connection.commit()  # Commit changes

                print("Update completed successfully.")

            except mysql.connector.Error as err:
                print(f"Error: {err}")
                connection.rollback()  # Rollback the transaction in case of an error

        # update_query = """
        # UPDATE tradeMetadata
        # SET mappingStatus = %s

        # WHERE id = %s;
        # """

        # values = ('Complete',trade['id'])
        # cursor.execute(update_query, values)  # Execute query with parameters
        # connection.commit()  # Commit changes
        # print("Update completed successfully.")

    # while True:
    #     cursor.execute(
    #         "SELECT * FROM tradeMetadata WHERE mappingStatus = 'Pending' AND batchId = %s",
    #         (batch_id,)
    #         )
    #     trade_new = cursor.fetchone()
    #     if not trade_new:
    #         logger.info("No more trades to process in step 1")
    #         process_rule_engine_step_1_fill_audio_not_found(current_date,batch_id)
    #         break

    cursor.close()
    connection.close()



def trigger_rule_engine():
    global CURRENT_BATCH_STATUS
    while True:














        logger.info(f" trigger_rule_engine Task executed at {datetime.utcnow()} (UTC)")
        connection = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
        cursor = connection.cursor(buffered=True)

        cursor.execute("select * from auditNexDb.batchStatus where currentBatch = 1")
        batch_status = cursor.fetchone()











        if batch_status and batch_status[7] == 'Complete' and batch_status[11] == 'Complete' and batch_status[10] == 'Pending' and  batch_status[10] == 'Pending':
            batch_id = batch_status[0]



            update_query = """
                UPDATE auditNexDb.batchStatus
                SET  triagingStatus = %s,triaggingStartTime = NOW()
                WHERE currentBatch = %s
            """
            update_values = ( "InProgress", str(1))

            cursor.execute(update_query, update_values)
            connection.commit()
            CURRENT_BATCH_STATUS['triagingStatus'] = "InProgress"

            cursor.execute("SELECT callmetadataStatus, trademetadataStatus, batchDate FROM auditNexDb.batchStatus where currentBatch = 1")
            meta_files_status = cursor.fetchone()
            current_date = meta_files_status[2]
            call_meta_file_status = False
            trade_meta_file_status = False

            if meta_files_status[0] != 1:
                logger.info("fetching metadata")
                source_base_path = os.environ.get('SOURCE')
                call_meta_file_status = trigger_api_metadata(source_base_path, current_date)
            if  meta_files_status[1] != 1:
                logger.info("fetching metadata")
                source_base_path = os.environ.get('SOURCE')
                trade_meta_file_status = trigger_api_trademetadata(source_base_path, current_date)

            if call_meta_file_status == True and trade_meta_file_status == True:
                process_rule_engine(current_date,batch_id)
            else:
                process_rule_engine(current_date,batch_id)


        time.sleep(120)


def get_current_batch_status():
    global CURRENT_BATCH_ID
    global CURRENT_BATCH_STATUS
    while True:
        given_date_format = os.environ.get('DATE_FORMAT')
        db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
            }

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("select *  from auditNexDb.batchStatus where currentBatch = 1")
        batch_status = cursor.fetchall()
        if len(batch_status) > 0:
            print("batch_status ->", batch_status[0])
            CURRENT_BATCH_STATUS = batch_status[0]

            current_date = batch_status[0]['batchDate']
            CURRENT_BATCH_ID = batch_status[0]['id']
        cursor.close()
        conn.close()
        time.sleep(60)

def get_dest_paths_from_src(src_base_path, dest_base_path,current_date):
    """
    Get all file names from src_folder and build corresponding
    destination paths in dest_folder.
    
    Args:
        src_folder (str): Source directory containing files.
        dest_folder (str): Destination directory.
    
    Returns:
        list[str]: List of destination file paths.
    """

    src_folder = os.path.join(src_base_path, current_date)
    dest_folder = os.path.join(dest_base_path)
    
    if not os.path.isdir(src_folder):
        raise FileNotFoundError(f"Source folder not found: {src_folder}")

    # Get only file names (skip directories)
    file_names = [
        f for f in os.listdir(src_folder)
        if os.path.isfile(os.path.join(src_folder, f))
    ]

    # Join each filename with the destination folder
    dest_paths = [os.path.join(dest_folder, f) for f in file_names]
    return dest_paths

def session_task():
    global CURRENT_BATCH_ID
    global CURRENT_BATCH_STATUS
    #source_base_path = os.environ.get('SOURCE')
    # current_date = '21-09-2025'
    # trade_meta_file_status = trigger_api_trademetadata(source_base_path, current_date)
    # logger.info("*****************Done trademetadata insertion")
    # db_config = {
    #     "host": os.environ.get('MYSQL_HOST'),
    #     "user":os.environ.get('MYSQL_USER'),
    #     "password":os.environ.get('MYSQL_PASSWORD'),
    #     "database": os.environ.get('MYSQL_DATABASE'),
    #     "connection_timeout": 86400000
    #     }

    # conn = mysql.connector.connect(**db_config)
    # cursor = conn.cursor(dictionary=True)
    # update_query = """
    #     UPDATE auditNexDb.batchStatus
    #     SET  step1StartTime = NOW()
    #     WHERE currentBatch = %s
    # """
    # update_values = (  str(1),)

    # cursor.execute(update_query, update_values)
    # conn.commit()
    # process_rule_engine_step_1(current_date,6)
    # process_rule_engine_step_1_fill_audio_not_found(current_date,6)
    # update_query = """
    #     UPDATE auditNexDb.batchStatus
    #     SET  step1EndTime = NOW()
    #     WHERE currentBatch = %s
    # """
    # update_values = (  str(1),)

    # cursor.execute(update_query, update_values)
    # conn.commit()
    # update_query = """
    # UPDATE auditNexDb.batchStatus
    # SET sttStatus = %s,sttStartTime = NOW()
    # WHERE batchDate = %s
    # """
    # update_values = ("InProgress", current_date)

    # cursor.execute(update_query, update_values)
    # conn.commit()
    # CURRENT_BATCH_STATUS['sttStatus'] = "InProgress"
    # return
    while True:
        logger.info(f"session_task Task executed at {datetime.utcnow()} (UTC)")
        given_date_format = os.environ.get('DATE_FORMAT')
        db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
            }

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("select *  from auditNexDb.batchStatus where currentBatch = 1")
        batch_status = cursor.fetchall()
        if len(batch_status) > 0:
            print("batch_status ->", batch_status[0])
            CURRENT_BATCH_STATUS = batch_status[0]

            current_date = batch_status[0]['batchDate']
            CURRENT_BATCH_ID = batch_status[0]['id']
        else:
            logger.info("No current batch found. Waiting for next execution.")
            return
        if batch_status[0]['batchStatus'] == "Pending" and batch_status[0]['dbInsertionStatus'] == "Pending":

            logger.info(f"Task executed at {datetime.utcnow()} (UTC)")
            source_base_path = os.environ.get('SOURCE')
            destination_base_path =  os.environ.get('DESTINATION')
            overwrite_existing = False
            api_url = f"{os.environ.get('COFI_URL')}/api/v1/recognize_speech_file_v2"
            logger.info(api_url)
            src_folder = os.path.join(source_base_path, current_date)
            #step1
            logger.info("***************1-1**********")
            logger.info("checkin folder "+str(os.path.exists(src_folder)))
            cursor.execute("SELECT callmetadataStatus, trademetadataStatus, batchDate FROM auditNexDb.batchStatus where currentBatch = 1")
            meta_files_status = cursor.fetchone()
            copied_files = []
            if os.path.exists(src_folder):

                update_query = """
                                UPDATE auditNexDb.batchStatus
                                SET  dbInsertionStatus = %s,dbInsertionStartTime = NOW(),batchStartTime = NOW()
                                WHERE batchDate = %s
                                """
                update_values = ("InProgress", current_date)

                cursor.execute(update_query, update_values)
                conn.commit()
                CURRENT_BATCH_STATUS['dbInsertionStatus'] = "InProgress"
                logger.info("***************1-2**********")
                logger.info("Starting copy files to destination folder")
                # copied_files,current_date = copy_20_percent_files(source_base_path, destination_base_path, overwrite_existing, current_date)
                copied_files = get_dest_paths_from_src(source_base_path, destination_base_path,current_date)
                logger.info("***************1-3**********")
                logger.info("Copy files to destination folder completed")
                logger.info(str(copied_files))
                update_query = """
                                UPDATE auditNexDb.batchStatus
                                SET  dbInsertionStatus = %s,dbInsertionEndTime = NOW()
                                WHERE batchDate = %s
                                """
                update_values = ("Complete", current_date)

                cursor.execute(update_query, update_values)
                conn.commit()
                CURRENT_BATCH_STATUS['dbInsertionStatus'] = "Complete"
                #step2 - Copy files to LID folder
                destination_lid_path =  os.environ.get('DESTINATION_LID')
                #copied_files_lid,current_date = copy_20_percent_files(source_base_path, destination_lid_path, overwrite_existing, current_date)
                copied_files_lid = copied_files
                logger.info(len(copied_files_lid))
                #step3 - Process metadata
                if copied_files_lid:
                    db_config = {
                    "host": os.environ.get('MYSQL_HOST'),
                    "user":os.environ.get('MYSQL_USER'),
                    "password":os.environ.get('MYSQL_PASSWORD'),
                    "database": os.environ.get('MYSQL_DATABASE'),
                    "connection_timeout": 86400000
                    }

                    conn = mysql.connector.connect(**db_config)
                    cursor = conn.cursor(dictionary=True)
                    



                    if meta_files_status['callmetadataStatus'] != 1:
                         call_meta_file_status = trigger_api_metadata(source_base_path, current_date)
                         if call_meta_file_status:
                             update_query = """
                                 UPDATE auditNexDb.batchStatus
                                 SET callmetadataStatus = %s
                                 WHERE batchDate = %s
                             """
                             update_values = (str(1), current_date)
                             cursor.execute(update_query, update_values)
                             conn.commit()
                             CURRENT_BATCH_STATUS['callmetadataStatus'] = 1
                    if meta_files_status['trademetadataStatus']  != 1:
                         trade_meta_file_status = trigger_api_trademetadata(source_base_path, current_date)
                         if trade_meta_file_status:
                             update_query = """
                                 UPDATE auditNexDb.batchStatus
                                 SET trademetadataStatus = %s
                                 WHERE batchDate = %s
                             """
                             update_values = (str(1), current_date)
                             cursor.execute(update_query, update_values)
                             conn.commit()
                    #         CURRENT_BATCH_STATUS['trademetadataStatus'] = 1


                #step - Denoise
                processed_denoise_files = []
                logger.info("Starting Denoise processing...")
                audio_endpoints = os.environ.get('LID_ENDPOINT', '')
                endpoints = [ep.strip() for ep in audio_endpoints.split(',') if ep.strip()]
                IS_DENOISE_ENABLED = os.environ.get("IS_DENOISE_ENABLED", "0")
                shared_folder = os.environ.get('DESTINATION')  # shared-files directory
                ivr_output_folder = os.path.join(shared_folder, "ivr_results")
                template_dir = os.environ.get('IVR_TEMPLATE_DIR', '/docker_volume/ivr')
                
                # delete_query = "DELETE FROM auditNexDb.ivr"
                # cursor.execute(delete_query)
                # conn.commit()
                # Process SMB-IVR on copied files
                
                upload_tasks = []
                if IS_DENOISE_ENABLED != str(1):
                    
                    lid_api_urls = os.environ.get('LID_ENDPOINT', '')
                    lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
                    lid_files = [file for file in copied_files_lid if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
                    
                    for idx, file in enumerate(lid_files):
                        file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
                    
                        if lid_api_url_list:
                            lid_api_url = lid_api_url_list[idx % len(lid_api_url_list)]
                        else:
                            lid_api_url = os.environ.get('LID_ENDPOINT')
                        parsed = urlparse(lid_api_url)
                        logger.info(parsed.hostname + " " + os.path.basename(file))
                        processed_denoise_files.append({
                            'ip': parsed.hostname,
                            'file': os.path.basename(file)
                        })
                        filename = os.path.basename(file)
                        add_column = ("INSERT INTO auditNexDb.ivr (file, ip)" "VALUES(%s, %s)")
                        add_result = (filename, parsed.hostname)
                        cursor.execute(add_column, add_result)
                        conn.commit()
                        logger.info(f"Prepared upload task for file: {file_url} to LID API: {lid_api_url}")
                        upload_tasks.append((lid_api_url, file_url))

                    # Run uploads in parallel
                    # with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    #     futures = [executor.submit(upload_file_stt_trigger, endpoint, file_url) for endpoint, file_url in upload_tasks]
                    #     concurrent.futures.wait(futures)

                    logger.info("SMB-DENOISE processing is disabled via IS_IVR_ENABLED flag.")
                    

                if batch_status[0]['denoiseStatus'] == "Pending":
                    if IS_DENOISE_ENABLED != str(1):
                        
                        update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  denoiseStatus = %s,denoiseEndTime = NOW()
                                    WHERE batchDate = %s
                                    """
                        update_values = ("Complete", current_date,)
                        # Build array
                        cursor.execute(update_query, update_values)
                        conn.commit()
                        time.sleep(60)
                    else:
                        logger.info("Denoise processing is enabled via IS_DENOISE_ENABLED flag.")
                        update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  denoiseStartTime = NOW()
                                    WHERE batchDate = %s
                                    """
                        update_values = (current_date,)

                        cursor.execute(update_query, update_values)
                        conn.commit()

                        for endpoint in endpoints:
                            logger.info(f"Starting container auditnex-smb-denoise-1 on endpoint: {endpoint}")
                            start_container_gpu("auditnex-smb-denoise-1",endpoint)

                        time.sleep(60)

                        processed_denoise_files = process_smb_denoise( copied_files_lid)
                        
                        
                        update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  denoiseStatus = %s,denoiseEndTime = NOW()
                                    WHERE batchDate = %s
                                    """
                        update_values = ("Complete", current_date,)
                        # Build array
                        cursor.execute(update_query, update_values)
                        conn.commit()
                        cursor.execute("SELECT file, ip FROM ivr;")
                        rows = cursor.fetchall()
                        for row in rows:
                            logger.info(f"SMB-DENOISE processed file: {row['file']} from IP: {row['ip']}")
                            processed_denoise_files.append({
                                'ip': row['ip'],  # from urlparse
                                'file': row['file']       # from DB
                            })


                        lid_api_urls = os.environ.get('LID_ENDPOINT', '')
                        lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
                        lid_files = [file for file in copied_files_lid if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
                        
                        for idx, file in enumerate(lid_files):
                            file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
                        
                            if lid_api_url_list:
                                lid_api_url = lid_api_url_list[idx % len(lid_api_url_list)]
                            else:
                                lid_api_url = os.environ.get('DENOISE_API_URL')
                            parsed = urlparse(lid_api_url)
                            logger.info(parsed.hostname + " " + os.path.basename(file))
                            processed_denoise_files.append({
                                'ip': parsed.hostname,
                                'file': os.path.basename(file)
                            })

                        logger.info(f"SMB-DENOISE processing completed for {len(processed_denoise_files)} files")    
                        audio_endpoints = os.environ.get('LID_ENDPOINT', '')
                        endpoints = [ep.strip() for ep in audio_endpoints.split(',') if ep.strip()]
                        for endpoint in endpoints:
                            logger.info(f"Stopping container auditnex-smb-denoise-1 on endpoint: {endpoint}")
                            stop_container_gpu("auditnex-smb-denoise-1",endpoint)
                        time.sleep(60)
                        for endpoint in endpoints:
                            logger.info(f"Starting container auditnex-smb-ivr-1 on endpoint: {endpoint}")
                            start_container_gpu("auditnex-smb-ivr-1",endpoint)

                        time.sleep(60)
                #step4 - Process SMB-IVR
                #step4: SMB-IVR Processing FIRST
                processed_ivr_files = []
                if batch_status[0]['ivrStatus'] == "Pending":
                    if copied_files_lid:
                        logger.info("Starting SMB-IVR processing...")
                        shared_folder = os.environ.get('DESTINATION')  # shared-files directory
                        ivr_output_folder = os.path.join(shared_folder, "ivr_results")
                        template_dir = os.environ.get('IVR_TEMPLATE_DIR', '/docker_volume/ivr')
                        
                        # delete_query = "DELETE FROM auditNexDb.ivr"
                        # cursor.execute(delete_query)
                        # conn.commit()
                        # Process SMB-IVR on copied files
                        
                        upload_tasks = []
                        logger.info("1")
                        IS_IVR_ENABLED = os.environ.get("IS_IVR_ENABLED", "0")
                        if IS_IVR_ENABLED != str(1):
                            if IS_DENOISE_ENABLED != str(1):
                                lid_api_urls = os.environ.get('LID_ENDPOINT', '')
                                lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
                                lid_files = [file for file in copied_files_lid if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
                                
                                for idx, file in enumerate(lid_files):
                                    file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
                                
                                    if lid_api_url_list:
                                        lid_api_url = lid_api_url_list[idx % len(lid_api_url_list)]
                                    else:
                                        lid_api_url = os.environ.get('LID_ENDPOINT')
                                    parsed = urlparse(lid_api_url)
                                    logger.info(parsed.hostname + " " + os.path.basename(file))
                                    processed_ivr_files.append({
                                        'ip': parsed.hostname,
                                        'file': os.path.basename(file)
                                    })
                                    logger.info(f"Prepared upload task for file: {file_url} to LID API: {lid_api_url}")
                                    logger.info("2")
                                    upload_tasks.append((lid_api_url, file_url))
                                    logger.info("3")

                                # Run uploads in parallel
                                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                                    futures = [executor.submit(upload_file_stt_trigger, endpoint, file_url) for endpoint, file_url in upload_tasks]
                                    concurrent.futures.wait(futures)

                                logger.info("SMB-IVR processing is disabled via IS_IVR_ENABLED flag.")
                            else:
                                processed_ivr_files = processed_denoise_files
                                update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  denoiseStatus = %s,denoiseEndTime = NOW()
                                    WHERE batchDate = %s
                                    """
                                update_values = ("Complete", current_date,)
                                # Build array
                                cursor.execute(update_query, update_values)
                                conn.commit()

                            update_query = """
                                        UPDATE auditNexDb.batchStatus
                                        SET  ivrStatus = %s,ivrEndTime = NOW()
                                        WHERE batchDate = %s
                                        """
                            update_values = ("Complete", current_date,)
                            # Build array
                            cursor.execute(update_query, update_values)
                            conn.commit()
                            for endpoint in endpoints:
                                logger.info(f"Starting container auditnex-lid-inference-1 on endpoint: {endpoint}")
                                start_container_gpu("auditnex-lid-inference-1",endpoint)

                            time.sleep(60)
                        else:

                            update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  ivrStartTime = NOW()
                                    WHERE batchDate = %s
                                    """
                            update_values = (current_date,)

                            cursor.execute(update_query, update_values)
                            conn.commit()

                            for endpoint in endpoints:
                                logger.info(f"Starting container auditnex-smb-ivr-1 on endpoint: {endpoint}")
                                start_container_gpu("auditnex-smb-ivr-1",endpoint)

                            time.sleep(60)

                            processed_ivr_files = process_smb_ivr(copied_files_lid,processed_denoise_files)
                            
                            
                            update_query = """
                                        UPDATE auditNexDb.batchStatus
                                        SET  ivrStatus = %s,ivrEndTime = NOW()
                                        WHERE batchDate = %s
                                        """
                            update_values = ("Complete", current_date,)
                            # Build array
                            cursor.execute(update_query, update_values)
                            conn.commit()
                            cursor.execute("SELECT file, ip FROM ivr;")
                            rows = cursor.fetchall()
                            for row in rows:
                                logger.info(f"SMB-IVR processed file: {row['file']} from IP: {row['ip']}")
                                processed_ivr_files.append({
                                    'ip': row['ip'],  # from urlparse
                                    'file': row['file']       # from DB
                                })


                            lid_api_urls = os.environ.get('LID_ENDPOINT', '')
                            lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
                            lid_files = [file for file in copied_files_lid if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
                            
                            for idx, file in enumerate(lid_files):
                                file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
                            
                                if lid_api_url_list:
                                    lid_api_url = lid_api_url_list[idx % len(lid_api_url_list)]
                                else:
                                    lid_api_url = os.environ.get('IVR_API_URL')
                                parsed = urlparse(lid_api_url)
                                logger.info(parsed.hostname + " " + os.path.basename(file))
                                processed_ivr_files.append({
                                    'ip': parsed.hostname,
                                    'file': os.path.basename(file)
                                })

                            logger.info(f"SMB-IVR processing completed for {len(processed_ivr_files)} files")    
                            audio_endpoints = os.environ.get('LID_ENDPOINT', '')
                            endpoints = [ep.strip() for ep in audio_endpoints.split(',') if ep.strip()]
                            for endpoint in endpoints:
                                logger.info(f"Stopping container auditnex-ivr-inference-1 on endpoint: {endpoint}")
                                stop_container_gpu("auditnex-smb-ivr-1",endpoint)
                            time.sleep(60)
                            for endpoint in endpoints:
                                logger.info(f"Starting container auditnex-lid-inference-1 on endpoint: {endpoint}")
                                start_container_gpu("auditnex-lid-inference-1",endpoint)

                            time.sleep(60)

                    

                #step5: LID Processing SECOND (using files created by SMB-IVR docker)
                processed_ivr_files = []
                cursor.execute("SELECT file, ip FROM ivr;")
                rows = cursor.fetchall()
                already_processed_files = []
                for row in rows:
                    logger.info(f"SMB-IVR processed file: {row['file']} from IP: {row['ip']}")
                    if row['file'] not in already_processed_files:
                        already_processed_files.append(row['file'])
                        processed_ivr_files.append({
                            'ip': row['ip'],  # from urlparse
                            'file': row['file']       # from DB
                        })
                # lid_api_urls = os.environ.get('DENOISE_API_URL', '')
                # lid_api_url_list = [url.strip() for url in lid_api_urls.split(',') if url.strip()]
                # upload_api_urls = os.environ.get('LID_ENDPOINT', '')
                # upload_api_url_list = [url.strip() for url in upload_api_urls.split(',') if url.strip()]
                # lid_files = [file for file in copied_files_lid if (".wav" in os.path.basename(file)) or (".mp3" in os.path.basename(file))]
               
                # for idx, file in enumerate(lid_files):
                #     file_url = os.environ.get('SPLIT_BASE_URL') + "/audios/" + str(CURRENT_BATCH_STATUS['batchDate']) + "/" + os.path.basename(file)
                #     lid_api_url = ''
                #     upload_api_url = ''
                #     if lid_api_url_list:
                #         getIndex = idx % len(lid_api_url_list)
                #         lid_api_url = lid_api_url_list[getIndex]
                #         upload_api_url = upload_api_url_list[getIndex]
                #     else:
                #         lid_api_url = os.environ.get('DENOISE_API_URL')
                #         upload_api_url = os.environ.get('LID_ENDPOINT')
                #     parsed = urlparse(lid_api_url)
                #     logger.info(parsed.hostname + " " + os.path.basename(file))
                #     processed_ivr_files.append({
                #         'ip': parsed.hostname,
                #         'file': os.path.basename(file),
                #         'lid_api_url': lid_api_url,
                #         'upload_api_url': upload_api_url
                #     })
                    
                    
                time.sleep(10)
                logger.info(f"Total processed IVR files: {len(processed_ivr_files)}")
                lid_batch_check = os.environ.get("LID_BATCH")
                print("lid batch process -> ", lid_batch_check)
                if lid_batch_check == str(1):
                    audio_endpoints = os.environ.get('LID_ENDPOINT', '')
                    endpoints = [ep.strip() for ep in audio_endpoints.split(',') if ep.strip()]
                    
                    for endpoint in endpoints:
                        logger.info(f"Starting container auditnex-lid-inference-1 on endpoint: {endpoint}")
                        start_container_gpu("auditnex-lid-inference-1",endpoint)

                    time.sleep(60)
                    # LID will process files from the LID folder created by SMB-IVR docker
                    lid_folder = os.environ.get('DESTINATION_LID')
                    if os.path.exists(lid_folder):
                        lid_files = [f for f in os.listdir(lid_folder) if f.lower().endswith(('.wav', '.mp3'))]
                        logger.info(f"Found {len(lid_files)} files in LID folder for processing")

                        if copied_files_lid:
                            update_query = """
                                UPDATE auditNexDb.batchStatus
                                SET  lidStartTime = NOW()
                                WHERE batchDate = %s
                                """
                            update_values = (current_date,)

                            cursor.execute(update_query, update_values)
                            conn.commit()
                            lid_results_list = get_lid_results(copied_files_lid, 1, batch_status[0]['id'],processed_ivr_files)
                            update_query = """
                                UPDATE auditNexDb.batchStatus
                                SET  lidEndTime = NOW()
                                WHERE batchDate = %s
                                """
                            update_values = (current_date,)

                            cursor.execute(update_query, update_values)
                            conn.commit()

                            cursor.execute("SELECT audioName,language,audioDuration,ip,lidProcessingTime FROM lidStatus WHERE batchId = %s;", (batch_status[0]['id'],))
                            rows = cursor.fetchall()
                            lid_results_list = []
                            for row in rows:
                                logger.info(f"SMB-LID db processed file: {row['audioName']} from IP: {row['ip']}")
                                lid_results_list.append({
                                    "file": row['audioName'],
                                    "language": row['language'],
                                    "lid_processing_time":  row['lidProcessingTime'],
                                    "audioDuration": row['audioDuration'],
                                    'ip': row['ip'],
                                })

                            if len(lid_results_list) == 0:
                                logger.info("LID not generated for any file. Exiting.")
                            else:
                                update_query = """
                                UPDATE auditNexDb.batchStatus
                                SET lidStatus = %s, dbInsertionStatus = %s
                                WHERE batchDate = %s
                                """
                                update_values = ("Complete", "Complete", current_date)

                                cursor.execute(update_query, update_values)
                                conn.commit()
                                CURRENT_BATCH_STATUS['lidStatus'] = "Complete"
                                CURRENT_BATCH_STATUS['dbInsertionStatus'] = "Complete"

                                #step7: STT Processing THIRD

                                trigger_api_stt(lid_results_list, api_url,1,current_date,batch_status[0]['id'])
                                update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  step1StartTime = NOW()
                                    WHERE currentBatch = %s
                                """
                                update_values = (  str(1),)

                                cursor.execute(update_query, update_values)
                                conn.commit()
                                process_rule_engine_step_1(current_date,batch_status[0]['id'])
                                process_rule_engine_step_1_fill_audio_not_found(current_date,batch_status[0]['id'])
                                update_query = """
                                    UPDATE auditNexDb.batchStatus
                                    SET  step1EndTime = NOW()
                                    WHERE currentBatch = %s
                                """
                                update_values = (  str(1),)

                                cursor.execute(update_query, update_values)
                                conn.commit()
                                update_query = """
                                UPDATE auditNexDb.batchStatus
                                SET sttStatus = %s,sttStartTime = NOW()
                                WHERE batchDate = %s
                                """
                                update_values = ("InProgress", current_date)

                                cursor.execute(update_query, update_values)
                                conn.commit()
                                CURRENT_BATCH_STATUS['sttStatus'] = "InProgress"
                        else:
                            logger.info("No LID files found in LID folder. SMB-IVR may not have completed yet.")
                            continue
                    else:
                        logger.info("LID folder does not exist. SMB-IVR may not have completed yet.")
                        continue

                elif lid_batch_check == str(0):
                    if copied_files:

                        trigger_api_in_batches(copied_files_lid, api_url,1,current_date)
                    else:
                        logger.info("No files were copied. Exiting.")

                else:
                    logger.info("LID config not set")
            else:
                logger.info(f"Source folder '{src_folder}' does not exist. Exiting.")

        elif batch_status[0]['batchStatus'] == "Complete":
            update_query = """
                UPDATE auditNexDb.batchStatus
                SET currentBatch = %s
                WHERE batchDate = %s
            """
            update_values = (str(0), current_date)
            cursor.execute(update_query, update_values)
            conn.commit()
            CURRENT_BATCH_STATUS['currentBatch'] = 0
            previous_date_query  = '''select batchDate from auditNexDb.batchStatus where batchStatus = "Complete" order by id desc limit 1'''
            cursor.execute(previous_date_query)
            previous_date = cursor.fetchone()
            date_obj = datetime.strptime(previous_date['batchDate'], given_date_format)  # Parse the date
            next_date = date_obj + timedelta(days=1)
            formatted_date = next_date.strftime("%d-%m-%Y")
            add_column = ("INSERT INTO auditNexDb.batchStatus (batchDate, currentBatch) VALUES(%s, %s) ")
            add_result = (str(formatted_date), str(1))
            cursor.execute(add_column, add_result)
            cursor.execute("select * from auditNexDb.batchStatus where currentBatch = 1")
            batch_status = cursor.fetchall()
            print("batch_status ->", batch_status[0])
            CURRENT_BATCH_STATUS = batch_status[0]

            current_date = batch_status[0]['batchDate']
            CURRENT_BATCH_ID = batch_status[0]['id']
            conn.commit()
            if is_service_running('auditnex-llm-extraction-1'):
                stop_service('auditnex-llm-extraction-1')

                time.sleep(10)
                container_status = is_service_running('auditnex-stt-inference-1')
                if container_status == False:
                    start_service("auditnex-stt-inference-1")
                    time.sleep(180)

                container_status = is_service_running('auditnex-smb-vad-1')
                if container_status == False:
                    start_service("auditnex-smb-vad-1")
                    time.sleep(180)
            else:
                container_status = is_service_running('auditnex-stt-inference-1')
                if container_status == False:
                    start_service("auditnex-stt-inference-1")
                    time.sleep(180)

                container_status = is_service_running('auditnex-smb-vad-1')
                if container_status == False:
                    start_service("auditnex-smb-vad-1")
                    time.sleep(180)


        time.sleep(500)


def license_periodic_task():
    while True:
        check_pending_req(REQUEST_IN_PROGRESS)  # Call your async function

        logger.info(license_instance_type)
        if license_instance_type != '':
            logger.info("Checking local data")
            client.sync_local_sessions_to_main()
        time.sleep(10)

def license_session_task():
    while True:

        insert_session()

        time.sleep(60)

@app.listener('before_server_start')
async def setup_periodic_tasks(app, loop):
    if INSTANCE_TYPE != 'SPLIT':
        task_thread = Thread(target=periodic_task, daemon=True)
        task_thread.start()
    if INSTANCE_TYPE == 'SPLIT':
        task_thread2 = Thread(target=session_task, daemon=True)
        task_thread2.start()
        task_thread3 = Thread(target=trigger_rule_engine, daemon=True)
        task_thread3.start()

    task_thread4 = Thread(target=get_current_batch_status, daemon=True)
    task_thread4.start()

    # task_thread5 = Thread(target=license_periodic_task, daemon=True)
    # task_thread5.start()
    # task_thread6 = Thread(target=license_session_task, daemon=True)
    # task_thread6.start()


if __name__ == "__main__":



    app.run(host='0.0.0.0', port=int(config.SERVICE_PORT))

