import logging
from shutil import ExecError
import time
logger = logging.getLogger()
from sanic.response import json
import requests
import os
from datetime import datetime
import json
import mysql.connector
import math
import boto3
from pydub import AudioSegment
from io import BytesIO
from google.cloud import storage
import shutil
import docker
from mutagen import File
from license_sdk import LicenseClient
client_docker = docker.from_env()

license_base_url = os.environ.get("license_base_url","https://license.contiinex.com/api")
client = LicenseClient(base_url=license_base_url)

time.sleep(2)
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





    


def convert_seconds(seconds):
    hours = seconds // 3600  # Number of hours
    seconds %= 3600
    minutes = seconds // 60  # Number of minutes
    seconds %= 60  # Remaining seconds

    return f"{hours:02}:{minutes:02}:{seconds:02}"

def remove_all_contents(path):

    if os.path.exists(path) and os.path.isdir(path):

        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            

            if os.path.isdir(item_path):
                print(f"Removing directory: {item_path}")  # Optional: for logging
                shutil.rmtree(item_path)

            elif os.path.isfile(item_path):
                print(f"Removing file: {item_path}")  # Optional: for logging
                os.remove(item_path)
    else:
        print(f"The provided path {path} is invalid or does not exist.")

def get_audio_duration(url):

    response = requests.get(url)
    
    if response.status_code == 200:

        audio_data = BytesIO(response.content)
        

        audio = AudioSegment.from_file(audio_data)
        

        duration_seconds = len(audio) / 1000.0  # Convert milliseconds to seconds
        return duration_seconds
    else:
        print(f"Error: Unable to fetch audio from {url}")
        return None

def get_audio_duration_file(path):

    audio = AudioSegment.from_file(path)  # Replace with your file

        

    duration_seconds = len(audio) / 1000.0  # Convert milliseconds to seconds
    return duration_seconds
    
    
def audio_file_duration(request_data, callback_url):
    logger.info("api wrapper audio_file_duration with request data: " + str(request_data))
    logger.info(1)
    print(request_data['audioURL'])
    try:
        logger.info(get_audio_duration(request_data['audioURL']))
        duration = convert_seconds(int(get_audio_duration(request_data['audioURL'])))
        json_result = {'audioLength': duration}
        return json_result
    except Exception as e:
        print(e)
        logger.error(e)
        return False, "API: Interface Something went wrong"

def compare_machine_trade_results(list1, list2):


    keys_to_compare = ['script', 'trade_price', 'strike_price', 'quantity']


    matches = []
    for dict1 in list1:
        for dict2 in list2:
            for key in keys_to_compare:
                if dict1.get(key) == dict2.get(key):
                    matches.append((dict1, dict2, key, dict1[key]))
    
    return matches

def fill_na_none(data):


    filled_data = [(None if val == '' else val for val in tup) for tup in data]


    filled_data = [tuple(tup) for tup in filled_data]

    return filled_data

def get_trade_details_audio(audio_name, client_code):
    trade_sql_query = "SELECT `id`, `tradeDate`, `orderPlacedTime`, `symbol`, `strikePrice`, `tradeQuantity`, `tradePrice` FROM `tradeMetadataNew` where `clientCode` = %s and `audioFileName` = %s"


    cursor.execute(trade_sql_query, (client_code, audio_name,))
    rows = cursor.fetchall()

    return rows


def quantity_check(call_id):
    cursorObject.execute("SELECT lotQuantity, tradePrice FROM auditNexDb.callConversation where callId = '"+str(call_id) + "'")
    quantity_result = cursorObject.fetchall()
    quantity_discrepancy = False
    try:
        for row in quantity_result:
            if int(row[0]) >= 25000 or int(row[1]) < 5:
                quantity_discrepancy = True
                return quantity_discrepancy
                break
            else:
                continue
        return quantity_discrepancy
    except:
        return quantity_discrepancy

def trade_type_check(call_id):
    cursorObject.execute("SELECT optionType, lotQuantity, strikePrice, expiryDate, tradeDate, tradePrice, buySell FROM auditNexDb.callConversation where callId = '"+str(call_id) + "'")
    trade_result = cursorObject.fetchall()
    final_trade_type = ""
    if len(trade_result) == 0:
        final_trade_type += "NA"
    else:
        for row in trade_result:
            if (row[0] != "" and (row[0] != "None" or row[0].lower() != "na")) and (row[1] != "" and (row[1] != "None" or row[1].lower() != "na")) and (row[2] != "" and (row[2] != "None" or row[2].lower() != "na")) and (row[3] != "" and (row[3] != "None" or row[3].lower() != "na")):
                final_trade_type += "Options"
                break
            elif row[0] == "" and (row[1] != "" and (row[1] != "None" or row[1].lower() != "na")) and row[2] == "" and (row[3] != "" and (row[3] != "None" or row[3].lower() != "na")):
                final_trade_type += "Futures"
                break
            elif (row[4] != "" and (row[4] != "None" or row[4].lower() != "na")) or (row[5] != "" and (row[5] != "None" or row[5].lower() != "na")) or (row[6] != "" and (row[6] != "None" or row[6].lower() != "na")): 
                final_trade_type += "Equity/Cash"   
                break
            else:
                final_trade_type += "NA"
                break

    return final_trade_type


def get_trade_details_time(audio_name, client_code, start_date, start_time, end_date, end_time):




    trade_sql_query = "SELECT `id`, `tradeDate`, `orderPlacedTime`, `symbol`, `strikePrice`, `tradeQuantity`, `tradePrice` FROM `tradeMetadataNew` WHERE `clientCode` = %s and `tradeDate` = %s ORDER BY ABS(TIMESTAMPDIFF(SECOND, `orderPlacedTime`, STR_TO_DATE(%s, '%T'))) limit 1"


    print(start_time, type(start_time))

    cursor.execute(trade_sql_query, (client_code,start_date, start_time))
    rows = cursor.fetchall()








def get_machine_results(call_id):
    sql_query = "SELECT `scriptName`, `lotQuantity`, `strikePrice`, `tradePrice`, `buySell`, `optionType` FROM `callConversation` WHERE `callId` = %s"

    cursor.execute(sql_query, (call_id, ))

    rows = cursor.fetchall()

    return rows
    
def group_machine_results(machine_results):


    filled_data = [(None if val == '' else val for val in tup) for tup in machine_results]


    filled_data = [tuple(tup) for tup in filled_data]


    machine_results_li = []

    grouped_data = defaultdict(lambda: {'2nd_elements': 0, '3rd_elements': [], '4th_elements': []})


    for entry in filled_data:
        key = entry[0]  # Group by 1st element
        if entry[1] is not None:
            grouped_data[key]['2nd_elements'] += float(entry[1])
        if entry[2] is not None:
            grouped_data[key]['3rd_elements'].append(float(entry[2]))
        if entry[3] is not None:
            grouped_data[key]['4th_elements'].append(float(entry[3]))  # Collect 4th elements to calculate average


    for key, value in grouped_data.items():
        dict = {}
        dict["script"] = key

        if value['4th_elements']:
            avg_4th = mean(value['4th_elements'])
            dict["trade_price"] = int(avg_4th)
        else:
            dict["trade_price"] = None

        if value['3rd_elements']:
            avg_3rd = mean(value['3rd_elements'])
            dict["strike_price"] = int(avg_3rd)
        else:
            dict["strike_price"] = None

        sum_2nd = value['2nd_elements']
        dict["quantity"] = sum_2nd
        
        machine_results_li.append(dict)


    return machine_results_li

def group_trade_results(trade_results):
    
    grouped_result = []

    grouped_data = defaultdict(lambda: {'5th_elements': set(), '6th_elements': [], '7th_sum': 0})


    for entry in trade_results:

        key = (entry[3], entry[4])  # 4th element (group by this)
        grouped_data[key]['5th_elements'].add(entry[4])
        grouped_data[key]['6th_elements'].append(entry[5])  # 5th element to calculate average later
        grouped_data[key]['7th_sum'] += entry[6]  # 6th element to calculate the sum


    for key, value in grouped_data.items():
        dict={}
        dict["script"] = key[0]
        if key[1] != "":
            dict['strike_price'] = int(key[1])
        else:
            dict["strike_price"] = ""
        avg_6th = mean(value['6th_elements'])
        dict["quantity"] = avg_6th
        sum_7th = value['7th_sum']
        dict["trade_price"] = sum_7th 


        grouped_result.append(dict)

    return grouped_result

def get_callmeta(call_name):
    sql_query = "SELECT `sClientId`, `callStartDate`, `callStartTime`, `callEndDate`, `callEndTime` FROM `callMetaDataNew` where `sRecordingFileName`= %s"

    cursor.execute(sql_query, (call_name, ))
    rows = cursor.fetchall()
    for row in rows:

        return row

    
def append_log(message, file_path='logs.txt'):

    with open(file_path, 'a', encoding='utf-8') as file:

        file.write(message + '\n')

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):

        """Uploads a file to the Google Cloud Storage bucket."""
        current_directory = os.path.dirname(__file__)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(current_directory, "contiinex-comnex-90405f66ad02.json")


        storage_client = storage.Client()


        bucket = storage_client.bucket(bucket_name)


        blob = bucket.blob(destination_blob_name)


        blob.upload_from_filename(source_file_name)

        print(f"File {source_file_name} uploaded to {bucket_name}/{destination_blob_name}.")

        return True




def convert_to_mono(file_path, file_name, file_url):
    input_file = file_path+file_name
    new_file_name = file_name.replace(".wav", "_mono.wav")
    new_file_name = file_name.replace(".mp3", "_mono.wav")
    info = AudioSegment.from_file(input_file)
    output_file = file_path+new_file_name
    info = info.set_frame_rate(16000)
    info = info.set_channels(1)


    info.export(output_file, format="wav", bitrate="256k")
    
    print(f"file {new_file_name} is converted audio")
    audio_parts = file_url.split("/")
    bucket_name = audio_parts[3]
    dest_path = audio_parts[4]+"/"+audio_parts[5]+"/"+audio_parts[6]+"/"


    destination_blob_name = dest_path+new_file_name
    upload_status = upload_to_gcs(bucket_name, input_file, destination_blob_name)
    return upload_status, new_file_name

def move_blob(file_url, file_name):
    """Uploads a file to the Google Cloud Storage bucket."""
    current_directory = os.path.dirname(__file__)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(current_directory, "contiinex-comnex-90405f66ad02.json")


    storage_client = storage.Client()

    audio_parts = file_url.split("/")
    bucket_name = audio_parts[3]


    bucket = storage_client.bucket(bucket_name)

    source_path = audio_parts[4]+"/"+audio_parts[5]+"/"+audio_parts[6]+"/"
    dest_path = audio_parts[4]+"/"+audio_parts[5]+"/"+ "unsupported_format_audios/"


    destination_blob_name = dest_path+file_name
    source_blob_name = source_path+file_name


    new_blob = bucket.copy_blob(source_blob_name, bucket, destination_blob_name)

    source_blob_name.delete()



def insert_into_db_step_1(request_data):
    try:
        header = {'Content-Type': "application/json"}
        url = os.environ.get('STT_URL')
        storage_path = os.environ.get('STORAGE_PATH')
        lid_audio_path = os.environ.get('DESTINATION_LID')
        nlp_endpoint = os.environ.get('NLP_API')
        sentiment_endpoint = os.environ.get('SENTIMENT_API')
        auditnex_endpoint = os.environ.get('AUDITNEX_API')
        audio_endpoint = os.environ.get('AUDIO_ENDPOINT')
        callback_url_new = os.environ.get('CALLBACK_URL')
        stt_api_url = os.environ.get('STT_API_URL')
        user_id = 0
        batch_id = None
        myresult = []
        call_id = 0
        process_id = 1
        audit_form_id = 1
        file_name = request_data['file_name']
        audio_url = request_data["audio_uri"]
        call_type = 'Call'
        language = ''
        language_id = 199
        metaData = {}
        ip = None
        audioDuration = 0.0

        if 'type' in request_data:
            call_type = request_data['type']
        if 'process_id' in request_data:
            process_id = request_data['process_id']
        if 'call_id' in request_data:
            metaData['call_id'] = request_data['call_id']
        if 'audio_uri' in request_data:
            metaData['audioUrl'] = request_data["audio_uri"]
        if 'reAudit' in request_data:
            metaData['reAudit'] = request_data['reAudit']
        if 'user_id' in request_data:
            user_id = request_data['user_id']
        if 'batchId' in request_data:
            batch_id = request_data['batchId']
        if 'audioDuration' in request_data:
            audioDuration = request_data['audioDuration']
        if 'ip' in request_data:
            ip = request_data['ip']
        if 'language' in request_data:
            metaData['language'] = request_data['language']
            language = request_data["language"]
            cursorObject.execute("SELECT * FROM auditNexDb.language where languageCode = '"+str(language) + "'")
            savedLanguageResult = cursorObject.fetchone()
            if savedLanguageResult:
                language_id = int(savedLanguageResult[0])
            metaData['languageId'] = language_id
            
        if "lid_processing_time" in request_data:
            metaData["durationLid"] = request_data["lid_processing_time"]

        if "language" not in request_data:    
            lid_request_data = {
                    "file_name": file_name,
                    "entity": "LID",
                    "response": ""
                }
            logger.info(stt_api_url)
            start_time_lid = datetime.now()
            lid_response = requests.post(stt_api_url, headers=header, json=lid_request_data)
            end_time_lid = datetime.now()
            duration_lid = (end_time_lid - start_time_lid).total_seconds()
            metaData['durationLid'] = duration_lid
            
            logger.info("LID response -> " + str(lid_response.json()))
            logger.info("LID trigger status - ended ")    
            if lid_response.status_code == 200:
                lid_json_response = lid_response.json()
                language = lid_json_response["data"]["derived_value"][0]["results"][0]
                metaData['language'] = language
                cursorObject.execute("SELECT * FROM auditNexDb.language where languageCode = '"+str(language) + "'")
                savedLanguageResult = cursorObject.fetchone()
                if savedLanguageResult:
                    language_id = int(savedLanguageResult[0])
                metaData['languageId'] = language_id
                audio_file_path = lid_audio_path+file_name
                if os.path.exists(audio_file_path):
                    try:
                        os.remove(audio_file_path)
                        print(f"File {audio_file_path} has been deleted successfully.")
                    except OSError as e:
                        print(f"Error: {e.strerror} - {e.filename}")
                else:
                    print(f"The file {audio_file_path} does not exist.")

        if 'reAudit' not in request_data:
            if 'multiple' in request_data and request_data['index'] == 0:
                for file_to_insert in request_data['files']:
                    if "audioUrl" in file_to_insert:
                        try:
                            if 'call_id' in file_to_insert:
                                metaData['call_id'] = file_to_insert['call_id']
                            metaData['audioUrl'] = file_to_insert["audioUrl"]

                            if "audioMode" in request_data:
                                metaData["audioMode"] = request_data["audioMode"]

                            filename = os.path.basename(file_to_insert["audioUrl"])
                            dir_name = os.path.dirname(storage_path+filename)
                        except Exception as e:
                            logger.info("error")
                            logger.info(str(e))
                    try:
                        # delete_query = "DELETE FROM auditNexDb.call WHERE audioName = '"+file_name+"';"
                        # cursorObject.execute(delete_query)
                        # dataBase2.commit()
                        logger.info("Insert call 1")
                        if user_id == 0:
                            logger.info("Insert call 1-1")
                            add_column = ("INSERT INTO auditNexDb.call (processId, auditFormId, categoryMappingId, audioUrl, audioName, status,type,metaData, languageId, lang,batchId,audioDuration,ip) VALUES (%s, %s,%s,%s, %s,%s, %s,%s, %s, %s,%s,%s)")
                            add_result = (process_id,int(audit_form_id),None,audio_url,file_name,'Pending',call_type,json.dumps(metaData),language_id,language,batch_id,audioDuration,ip)
                        else:
                            logger.info("Insert call 1-2")
                            add_column = ("INSERT INTO auditNexDb.call (processId, auditFormId, categoryMappingId, userId, audioUrl, audioName, status, type,metaData, languageId, lang,batchId,audioDuration,ip) VALUES (%s, %s,%s,%s, %s, %s, %s, %s, %s,%s, %s, %s, %s,%s)")
                            add_result = (process_id,int(audit_form_id),None,user_id,audio_url,file_name,'Pending', call_type,json.dumps(metaData),language_id,language,batch_id,audioDuration,ip)
                        logger.info(1)
                        cursorObject.execute(add_column, add_result)
                        logger.info(1)
                        dataBase2.commit()
                        logger.info("Insert call Done ")
                        print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and batchId = '"+str(batch_id) + "'" )
                        cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and batchId = '"+str(batch_id) + "'")
                        savedCallResult = cursorObject.fetchone()
                        logger.info(savedCallResult[0])
                        metaDataOld = json.loads(savedCallResult[25])
                        metaDataOld['call_id'] = savedCallResult[0]
                        update_query = """
                                            UPDATE auditNexDb.call
                                            SET status = %s,callId = %s, metaData = %s
                                            WHERE id = %s
                                            """
                        new_value = "Pending"
                        new_value2 = savedCallResult[0]
                        condition_value = savedCallResult[0]    
                        cursorObject.execute(update_query, (new_value,new_value2,json.dumps(metaDataOld),condition_value))
                        dataBase2.commit()
                        try:
                            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Pending"}, timeout=10)
                        except Exception as e:
                            print(e)
                            logger.error(e)
                    except Exception as e:
                        logger.error(str(e))
                        print(e)
                        return False, "API: Interface Something went wrong:"  + str(e)
            elif 'multiple' in request_data and request_data['index'] != 0:
                logger.info('Another file in multiple')
            else:
                try:
                    # delete_query = "DELETE FROM auditNexDb.call WHERE audioName = '"+file_name+"';"
                    # cursorObject.execute(delete_query)
                    # dataBase2.commit()
                    logger.info("Insert call 2")
                    add_column = ("INSERT INTO auditNexDb.call (processId, auditFormId, categoryMappingId, audioUrl, audioName, status, type,metaData) VALUES (%s, %s,%s, %s, %s, %s, %s, %s)")
                    add_result = (process_id,int(audit_form_id),1,audio_url,file_name,'Pending', call_type,json.dumps(metaData))
                    logger.info(1)
                    cursorObject.execute(add_column, add_result)
                    logger.info(1)
                    dataBase2.commit()
                    logger.info("Insert call Done ")
                    print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and batchId = '"+str(batch_id) + "'" )
                    cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and batchId = '"+str(batch_id) + "'")
                    savedCallResult = cursorObject.fetchone()
                    logger.info(savedCallResult[0])
                    metaDataOld = json.loads(savedCallResult[25])
                    metaDataOld['call_id'] = savedCallResult[0]
                    update_query = """
                                        UPDATE auditNexDb.call
                                        SET status = %s,callId = %s, metaData = %s
                                        WHERE id = %s
                                        """
                    new_value = "Pending"
                    new_value2 = savedCallResult[0]
                    condition_value = savedCallResult[0]    
                    cursorObject.execute(update_query, (new_value,new_value2,json.dumps(metaDataOld),condition_value))
                    dataBase2.commit()
                    try:
                        requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Pending"}, timeout=10)
                    except Exception as e:
                        print(e)
                        logger.error(e)
                except Exception as e:
                    logger.error(str(e))
                    print(e)
                    return False, "API: Interface Something went wrong:"  + str(e)
            print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and batchId = '"+str(batch_id) + "'" )
        else:
            cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and batchId = '"+str(batch_id) + "'")
            savedCallResult = cursorObject.fetchone()
            logger.info(savedCallResult[0])
            metaDataOld = json.loads(savedCallResult[25])
            metaDataOld['call_id'] = metaData['call_id']
            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s, metaData = %s
                                WHERE id = %s
                                """
            new_value = "Pending"
            condition_value = savedCallResult[0]    
            cursorObject.execute(update_query, (new_value,json.dumps(metaDataOld),condition_value))
            dataBase2.commit()
            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Pending"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)
        return True
    except Exception as e:
        logger.error(f"Exception in insert_into_db_step_1: {e}")
        print(f"Exception in insert_into_db_step_1: {e}")
        return False, f"API: Interface Something went wrong: {e}"


def recognize_speech_file_v3(request_data, callback_url,savedCallResult):
    logger.info("api wrapper recognize_speech_file_v3 with request data: " + str(request_data))
    
    process_id = 1
    audit_form_id = 1
    start_time = datetime.now()
    start_time_stt = datetime.now()
    end_time_stt = datetime.now()
    start_time_llm = datetime.now()
    end_time_llm = datetime.now()
    start_time_qa = datetime.now()
    end_time_qa = datetime.now()
    start_time_cs = datetime.now()
    end_time_cs = datetime.now()
    start_time_sentiment = datetime.now()
    end_time_sentiment = datetime.now()
    # savedCallResult = None
    header = {'Content-Type': "application/json"}
    url = os.environ.get('STT_URL')
    stt_api_url = os.environ.get('STT_API_URL')
    storage_path = os.environ.get('STORAGE_PATH')
    audio_chunks_path = os.environ.get('CHUNKS_PATH')
    nlp_endpoint = os.environ.get('NLP_API')
    sentiment_endpoint = os.environ.get('SENTIMENT_API')
    auditnex_endpoint = os.environ.get('AUDITNEX_API')
    audio_endpoint = os.environ.get('AUDIO_ENDPOINT')
    callback_url_new = os.environ.get('CALLBACK_URL')
    text_output_path = os.environ.get('TEXTOUTPUT')
    audioDuration = 0.0
    myresult = []
    call_id = 0

    process_type = 'sequential'

    log_file_path = '/docker_volume/logs/'+request_data['file_name'].replace('.mp3','.txt').replace('.wav','.txt')
    file_name = request_data['file_name']

    # if 'process_id' in request_data:
    #         logger.info("1")
    #         dataBase2 = mysql.connector.connect(
    #         host =os.environ.get('MYSQL_HOST'),
    #         user =os.environ.get('MYSQL_USER'),
    #         password =os.environ.get('MYSQL_PASSWORD'),
    #         database = os.environ.get('MYSQL_DATABASE'),
    #         connection_timeout= 86400000
    #         )
    #         cursorObject = dataBase2.cursor(buffered=True)
    #         logger.info("SELECT * FROM process where id = "+str(request_data['process_id']))
    #         cursorObject.execute("SELECT * FROM process where id = "+str(request_data['process_id']))
    #         logger.info("2")
    #         processResult = cursorObject.fetchone()
    #         logger.info("3")
    #         print("process result ->",processResult)
    #         process_id = int(processResult[0])
    #         logger.info("4")
    #         audit_form_id = int(processResult[4])
    #         process_type = processResult[8]
    #         logger.info("5")




   
    dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
    cursorObject = dataBase2.cursor(buffered=True)
    
             
    # print("SELECT * FROM auditNexDb.call where callId = '"+str(request_data["call_id"]) + "'")
    # cursorObject.execute("SELECT * FROM auditNexDb.call where callId = '"+str(request_data["call_id"]) + "' and status = 'TranscriptDone'")
    # logger.info("6") 
    # savedCallResult = cursorObject.fetchone()
    logger.info("7")
    # if not savedCallResult:
    #     return False, "API: Interface Something went wrong:"
    logger.info(savedCallResult[0])
    call_id = savedCallResult[0]
    logger.info("8")
         

    logger.info("storing call result" + str(savedCallResult[25]))
    logger.info("getting metadata")

    print("saved call result -> ", savedCallResult)    
    print("saved call result 25 -> ",type(savedCallResult[25]), savedCallResult[25])

    metaData = json.loads(savedCallResult[25])
    logger.info(metaData)
    lid_processing_time = metaData["durationLid"]
    all_chunks = []
    audio_url = audio_endpoint+"/"+request_data['file_name']
    if 'reAudit' in metaData:
        request_data['call_id'] = metaData['call_id']
        request_data['reAudit'] = metaData['reAudit']
        try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": request_data['call_id'], "status": "Pending"}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
    try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "InProgress"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    
        
    # dataBase2 = mysql.connector.connect(
    # host =os.environ.get('MYSQL_HOST'),
    # user =os.environ.get('MYSQL_USER'),
    # password =os.environ.get('MYSQL_PASSWORD'),
    # database = os.environ.get('MYSQL_DATABASE'),
    # connection_timeout= 86400000
    # )
    # cursorObject = dataBase2.cursor(buffered=True)
    
    if os.path.exists(log_file_path):

        # os.remove(log_file_path)
        print(f"File {log_file_path} has been deleted.")
    else:
        print(f"The file {log_file_path} does not exist.")
    log_message = "api wrapper recognize_speech_file_v2 with request data: " + str(request_data)
    append_log(log_message,log_file_path)
    
    stt_request_data = {
        'file_name': '',

        'no_of_speakers': 2,
        'audio_language': ""
    }
   
    if "no_of_speakers" in request_data:
        stt_request_data['no_of_speakers'] = request_data['no_of_speakers']



    
    if "audio_file_path" in request_data:
        stt_request_data['file_name'] = file_name

    if "language" not in request_data:
        lid_request_data = {
            "file_name": file_name,
            "entity": "LID",
            "response": ""
        }
        logger.info(stt_api_url)
        lid_response = requests.post(stt_api_url, headers=header, json=lid_request_data)

        logger.info("LID response -> " + str(lid_response))
        logger.info("LID trigger status - ended ")    
        if lid_response.status_code == 200:
            lid_json_response = lid_response.json()
            language = lid_json_response["data"]["derived_value"][0]["results"][0]
            if language == "hinglish":
                stt_request_data["audio_language"] = "hi"
            else:   
                stt_request_data["audio_language"] = language
    else:
        if request_data["language"] == "hinglish":
            stt_request_data["audio_language"] = "hi"
        else:
            stt_request_data["audio_language"] = request_data["language"]
    
    if (stt_request_data["audio_language"] != "en") and (stt_request_data["audio_language"] != "hi") and (stt_request_data["audio_language"] != "hinglish"):
        update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s
                        WHERE id = %s
                        """

        new_value = "Complete"
        condition_value = call_id
        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit()
        audio_file_path = storage_path+file_name
        if os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                print(f"File {audio_file_path} has been deleted successfully.")
            except OSError as e:
                print(f"Error: {e.strerror} - {e.filename}")
        else:
            print(f"The file {audio_file_path} does not exist.")

        logger.info("API: Language not supported")
        return False, "API: Language not supported"
    



    start_time_stt = datetime.now()        
    logger.info("STT trigger status - started" )
    logger.info("stt_request_data" + str(stt_request_data))
    logger.info("stt url called" + str(url))                            
    trnascript_for_nlp = ''

    cursorObject.execute("SELECT * FROM transcript tr WHERE tr.callId = "+ str(call_id) +"")

    all_tr_data = cursorObject.fetchall()
    
    
    for row in all_tr_data:
        
        s1, s2 = row[5].split(" ")
        all_chunks.append({'start_time': row[3], 'end_time': row[4], 'speaker': s2, 'transcript': row[6] })
        if "enable_speaker_detection" in request_data and request_data['enable_speaker_detection'] == True:
            trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+str(row[3]) + ' '+str(row[5]) + ':' + ' ' + str(row[6]) + ' ' + 'end_time: '+str(row[4]) + '\n'

        else:
            trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+str(row[3]) + ' '+str(row[5]) + ':' + ' ' + str(row[6]) + ' ' + 'end_time: '+str(row[4]) + '\n'
            # trnascript_for_nlp = trnascript_for_nlp + ' ' + row[6] + '.'

    connectionTrade = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
    cursorObjectTrade = connectionTrade.cursor(dictionary=True,buffered=True)     
    cursorObjectTrade.execute("SELECT * FROM auditNexDb.tradeMetadata where audioFileName = '"+str(request_data["file_name"])+"';")
    logger.info("6") 
    savedTradeResult = cursorObjectTrade.fetchone()
   
    
    cursorObjectTrade.close()
    connectionTrade.close()
    if True:
            
            if process_type == 'sttwithllm':
                sub_process_type = 'without_summary'
            else:
                sub_process_type = 'with_summary'

            cursorObject.execute("SELECT * FROM auditForm where id = "+str(audit_form_id))
            
            auditformresult = cursorObject.fetchone()

            
            cursorObject.execute("SELECT afsqm.*, s.*, q.* FROM auditFormSectionQuestionMapping afsqm INNER JOIN section s ON afsqm.sectionId = s.id INNER JOIN question q ON afsqm.questionId = q.id WHERE afsqm.auditFormId = "+ str(audit_form_id) +" AND s.id IN ( SELECT sectionId FROM auditFormSectionQuestionMapping WHERE auditFormId = "+ str(audit_form_id) +")")

            all_form_data = cursorObject.fetchall()
            

            audit_form = []
            audit_formIndex = -1
            section_list = []
            audio_language = ''
            for row in all_form_data:
                

                answerOptions = []
                cursorObject.execute('SELECT * from answerOption ao  WHERE questionId  = '+str(row[4]))
                all_option_data = cursorObject.fetchall()
                logger.info(row[0])

                for row2 in all_option_data:
                    answerOptions.append({'label':row2[3],'score': row2[4]})

                if row[2] not in section_list:

                        section_list.append(row[2])

                        section = {'section': row[7], 'subSection':[{'ssid':row[3],'questions': []}]}

                        if audio_language == "hi":
                            section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        else:
                            section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        audit_form.append(section)
                        audit_formIndex = audit_formIndex + 1
                else:

                    index = section_list.index(row[2])



                    subsFound = False
                    for section in audit_form:

                        for subs in section['subSection']:
                            if subs['ssid'] == row[3]:
                                subsFound = True

                                if audio_language == "hi":
                                    audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                                else:
                                    audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})

                    if subsFound == False:
                        audit_form[audit_formIndex]['subSection'].append({'ssid':row[3],'questions': []})
                        if audio_language == "hi":
                            audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        else:
                            audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                    
                        
            logger.info(audit_form)

            log_message = "stt response: " + str(trnascript_for_nlp)
            append_log(log_message,log_file_path)

            log_message = "audit form: " + str(audit_form)
            append_log(log_message,log_file_path)
            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Auditing"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)

            # update_query = """
            #                     UPDATE auditNexDb.call
            #                     SET status = %s,updatedAt = %s
            #                     WHERE id = %s
            #                     """

            # new_value = "Auditing"
            # condition_value = savedCallResult[0]
            # cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            # dataBase2.commit()    
            audit_score = 0
            sectionIndex = 0

            request_data_nlp = {
                                "text": trnascript_for_nlp,
                                "text_language": "hi",
                                "prompts": [
                                    {
                                        "entity": "trade_classify",
                                        "prompts": ["Classify the given conversation as '''trade''' or '''non-trade: Short calls''', based on the following conditions: non-trade - Short calls: Any one or more criteria should be consider The call ends with only one statement. The call ends due to not audible properly. The call conversation only about IVR options. The call end due to one speaker is busy or not picking up the call etc. There should not be any discussion about trade related information, stock details, market conditions, profit/loss, buy/sell, lot/quantity, trading suggestions during the conversation. OR trade: Any one scenario should present There should be discussion or mention about trading in terms of stock information, market conditions, profit/loss, buy/sell, lot/quantity and or order confirmation. Answer the following question in '''trade''' or '''non-trade''' in valid JSON like {'''validation''':trade/non-trade'''} and explanation outside the JSON."],
                                        "type": "multiple"
                                    }
                                ],
                                "additional_params": {}
                            }
            logger.info("LLM test1 kotak -LLM "+str(request_data_nlp))
            nlp_raw_response_1 = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
            nlp_response_1 = nlp_raw_response_1.json()
            logger.info("LLM test1 kotak -LLM trigger status - response "+str(nlp_response_1))
            nlp_response_1_result = None
            
            if 'data' in nlp_response_1:
                if 'derived_value' in nlp_response_1['data']:
                    
                    nlp_response_1_result = nlp_response_1['data']['derived_value'][0]['result']
                    if nlp_response_1_result == 'non-trade':
                        for section in audit_form:
                            if section['section'] != 'Call Category':
                                questionIndex = 0
                                for ssIndex, ss in enumerate(section['subSection']):
                                    for qIndex, question in enumerate(ss['questions']):
                                        if question["question"] != "Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?":
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                questionIndex = questionIndex + 1
                           

                            sectionIndex = sectionIndex + 1 
            if nlp_response_1_result != 'non-trade':
                for section in audit_form:
                    if section['section'] != 'Call Category':
                        questionIndex = 0
                        for ssIndex, ss in enumerate(section['subSection']):
                            for qIndex, question in enumerate(ss['questions']):



                                request_data_nlp = {
                                    "text": trnascript_for_nlp,
                                    "prompts": [
                                        {
                                            "entity": question['attribute'],
                                            "prompts": [question['intents']],
                                            "type": "multiple"
                                        }
                                    ],
                                    "additional_params": {}
                                }

                                request_data_stt_param = {
                                    "file_name": file_name,
                                    "file_url": audio_url,
                                    "entity": question['intents'],
                                    "response": all_chunks
                                }


                                logger.info("LLM trigger status - request")
                                logger.info(str(question))
                                if question['attribute'] == "speech_parameter":
                                    logger.info(str(request_data_stt_param))
                                else:
                                    logger.info(str(request_data_nlp))
                                log_message = "Sequence: " +str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex)
                                append_log(log_message,log_file_path)
                                log_message = "question: " + str(question)
                                append_log(log_message,log_file_path)
                                if question['attribute'] == "speech_parameter":
                                    log_message = "request data: " + str(request_data_stt_param)
                                    append_log(log_message,log_file_path)
                                else:
                                    log_message = "request data: " + str(request_data_nlp)
                                    append_log(log_message,log_file_path)
                                        
                                print("entity -> ",request_data_nlp["prompts"][0]["entity"])
                                print("intent -> ", request_data_nlp["prompts"][0]["prompts"][0])

                                if question["question"] == "Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?":
                                    
                                    # request_data_nlp = {
                                    #     "text": trnascript_for_nlp,
                                    #     "prompts": [
                                    #         {
                                    #             "entity": "trade_extraction",
                                    #             "prompts":  ["Extract all the unique stock names and stock indexes mentioned in the following conversation. The output must be a strictly formatted JSON array like ['name1', 'name2', 'name3', ...] in given language with no duplicates, explanations, additional text, or formatting. Include only stock names and indexes, ensuring accurate extraction.", "For the stock name 'Stock Name', extract all the details such as options type in call/put, lot or quantity, strike price, trade price, buy/sell indicator and expiry date from the conversation. If anything is not available for a specific stock, then mark as 'NA' Output for lot or quantity, strike price and market price should be numeric values, for example: 3, 1250, 259.65, 765 etc. Output for trade price should be the last confirmed market price of the stock at the time of trade. Output for expiry date should be english digit and in same format as present in the text. Provide the output strictly as a JSON array with objects formatted as follows: [{'options type':'call/put', 'lot/quantity':'value', 'strike price':'value', 'market price':'value', 'buy/sell':'Buy/Sell', 'expiry date':'date'},...]. Ensure no duplicates, include only relevant details, and avoid any additional text and explanations."],
                                    #             "type": "multiple"
                                    #         }
                                    #     ],
                                    #     "additional_params": {}
                                    # }
                                    
                                    # logger.info(str(request_data_nlp))
                                    # nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=300)
                                    # nlp_response = nlp_raw_response.json()
                                    # logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                    # print("first parameter response -> ", nlp_response)

                                    # log_message = "response data: " + str(nlp_response)
                                    # append_log(log_message,log_file_path)
                                    # if 'data' in nlp_response:
                                    #     result = nlp_response["data"]["derived_value"][0]["result"]
                                    #     if result != "NA":
                                    #         try:
                                    #             for item in result:

                                    #                 script_name = item["scriptName"]
                                    #                 option_type = item["optionType"]
                                    #                 lot = ""
                                    #                 quantity = item["lot/quantity"]
                                    #                 strike_price = item["strikePrice"]
                                    #                 trade_date = item["tradeDate"]
                                    #                 expiry_date = item["expiryDate"]
                                    #                 trade_price = item["tradePrice"]
                                    #                 buy_sell = item["buySell"]

                                    #                 dataBase2 = mysql.connector.connect(
                                    #                 host =os.environ.get('MYSQL_HOST'),
                                    #                 user =os.environ.get('MYSQL_USER'),
                                    #                 password =os.environ.get('MYSQL_PASSWORD'),
                                    #                 database = os.environ.get('MYSQL_DATABASE'),
                                    #                 connection_timeout= 86400000
                                    #                 )
                                    #                 cursorObject = dataBase2.cursor(buffered=True)

                                    #                 add_column = ("INSERT INTO callConversation (callId, scriptName, optionType, lotQuantity, strikePrice, tradeDate, expiryDate, tradePrice, buySell) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                                                        
                                    #                 add_result = (call_id,script_name, option_type, quantity, strike_price, trade_date, expiry_date, trade_price, buy_sell)

                                    #                 cursorObject.execute(add_column, add_result)
                                    #                 dataBase2.commit()

                                    #         except:
                                    #             continue

                                    continue






















                                                





                                            








                                                




















                                elif question["question"] == "Did the customer express frustration or use any abusive language during the call?":
                                    
                                    print("checking for emotion api")







                                    logger.info("LLM test1 "+str(request_data_nlp))
                                    start_time = datetime.now()
                                    nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                    end_time = datetime.now()
                                    processing_time = (end_time - start_time).total_seconds()
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                    nlp_response = nlp_raw_response.json()
                                    logger.info("LLM test1 trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))
                                    log_message = "response data: " + str(nlp_response)
                                    append_log(log_message,log_file_path)
                                    print(nlp_response)
                                    if 'data' in nlp_response:
                                        if 'derived_value' in nlp_response['data']:
                                            result = nlp_response['data']['derived_value'][0]['result']
                                            print("llm emotion output -> ", result)

                                            if len(result) > 0:

                                                if result.lower() == "yes":
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'
                                            
                                                elif result.lower() == "no":
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'

                                                elif result.lower() == "na":
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                
                                                else:
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'

                                                audit_score = audit_score + 0
                                            
                                            else:
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                audit_score = audit_score + 0
                                    if False and 'data' in nlp_response:
                                        if 'derived_value' in nlp_response['data']:
                                            result = nlp_response['data']['derived_value'][0]['results']
                                            print("stt emotion output ->", result)
                                            if result == "anger" or result == "disgust":
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "YES"

                                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                    if ans['label'] == result:
                                                        audit_score = audit_score + 0
                                        
                                            else:
                                                logger.info(str(request_data_nlp))
                                                nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                                nlp_response = nlp_raw_response.json()
                                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))
                                                log_message = "response data: " + str(nlp_response)
                                                append_log(log_message,log_file_path)
                                                print(nlp_response)
                                                if 'data' in nlp_response:
                                                    if 'derived_value' in nlp_response['data']:
                                                        result = nlp_response['data']['derived_value'][0]['result']
                                                        print("llm emotion output -> ", result)

                                                        if len(result) > 0:

                                                            if result.lower() == "yes":
                                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'
                                                        
                                                            elif result.lower() == "no":
                                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'

                                                            elif result.lower() == "na":
                                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                            
                                                            else:
                                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'

                                                            audit_score = audit_score + 0
                                                        
                                                        else:
                                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                            audit_score = audit_score + 0

                                    continue

                                elif question["question"] == "Is the price below 15 or quantity above 25000 highlighted and flagged?":
                                    # quantity_discrepancy_result = quantity_check(call_id)
                                    # if quantity_discrepancy_result:
                                    #     quantity_result = "YES"
                                    # else:
                                    #     quantity_result = "NO"

                                    # audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = quantity_result
                                    # for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    #     if ans['label'] == 'NA':
                                    #         audit_score = audit_score + int(str(ans['score']))
                                    continue

                                elif question["question"] == "Was the type of trade correctly identified and recorded as Options, Futures, or Equity/Cash? (Type of Trade)":
                                    # trade_type_result = trade_type_check(call_id)
                                    # audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = trade_type_result
                                    # for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    #     if ans['label'] == 'NA':
                                    #         audit_score = audit_score + int(str(ans['score']))
                                    continue

                                elif question["question"] == "Who initiated the trade during the call the client, the dealer or was it mutually decided?":
                                    logger.info("LLM test1 "+str(request_data_nlp))
                                    start_time = datetime.now()
                                    nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                    end_time = datetime.now()
                                    processing_time = (end_time - start_time).total_seconds()
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                    nlp_response = nlp_raw_response.json()
                                    logger.info("LLM test1 trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                    log_message = "response data: " + str(nlp_response)
                                    append_log(log_message,log_file_path)
                                    logger.info("LLM test1 "+str(nlp_response))
                                    if savedTradeResult and savedTradeResult['voiceRecordingConfirmations'] == 'No trade data found':
                                        logger.info('LLM test1 Question 2 No trade data found')
                                    
                                    elif 'data' in nlp_response:
                                        if 'derived_value' in nlp_response['data']:
                                            result = nlp_response['data']['derived_value'][0]['result']

                                            if len(result) > 0 and result.lower() == 'dealer':
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Dealer'
                                            elif len(result) > 0 and result.lower() == 'client':
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Client'
                                            elif len(result) > 0 and result.lower() == 'both':
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Both client & dealer'
                                            else:
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                        for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                            if ans['label'] == 'NA':
                                                audit_score = audit_score + int(str(ans['score']))
                                    continue

                                elif question["question"] == "Who Conducted the Research Client, Franchise or Kotak Research?":
                                    logger.info("LLM test1 NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                    # start_time = datetime.now()
                                    # nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                    # end_time = datetime.now()
                                    # processing_time = (end_time - start_time).total_seconds()
                                    # audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                    # nlp_response = nlp_raw_response.json()
                                    # logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                    # log_message = "response data: " + str(nlp_response)
                                    # append_log(log_message,log_file_path)
                                    # logger.info(str(nlp_response))
                                    # if 'data' in nlp_response:
                                    #     if 'derived_value' in nlp_response['data']:
                                    #         result = nlp_response['data']['derived_value'][0]['result']

                                    #         if len(result) > 0 and result.lower() == 'dealer':
                                    #             audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Kotak Research'
                                    #         elif len(result) > 0 and result.lower() == 'client':
                                    #             audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Client'
                                    #         else:
                                    #             audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    #     for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    #         if ans['label'] == 'NA':
                                    #             audit_score = audit_score + int(str(ans['score']))
                                    
                                elif question["question"] == "Did the client demonstrate a clear understanding of the derivatives and options segments and the risk involved in the type of transaction?":
                                    logger.info("NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                elif question["question"] == "Was the client informed and aware of any losses in their account during the call?":
                                    logger.info("NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                elif question["question"] == "Did the dealer exhibit rude behavior with the customer during the call?":
                                    logger.info("NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                elif question["question"] == "Did the dealer effectively communicate market conditions and provide clear guidance during the call, leading to customer satisfaction?":
                                    logger.info("NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                elif question["question"] == "Was the ledger balance confirmation marked as 'Yes' for trades where no recording was found or for partial trades?":
                                    logger.info("NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                elif question["question"] == "Did Kotak Research Lead to a Loss?":
                                    logger.info("NA question")
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    continue
                                elif request_data_nlp["prompts"][0]["prompts"][0] == "NA":
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "NA"
                                    for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                        if ans['label'] == 'NA':
                                            audit_score = audit_score + int(str(ans['score']))

                                    continue

                                elif question['attribute'] == "speech_parameter":
                                    print("speech api request -> ", request_data_stt_param)
                                    start_time = datetime.now()
                                    nlp_raw_response = requests.post(stt_api_url, headers=header, json = request_data_stt_param, timeout=150)
                                    end_time = datetime.now()
                                    processing_time = (end_time - start_time).total_seconds()
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                    nlp_response = nlp_raw_response.json()
                                    logger.info("LLM test1 LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                    log_message = "response data: " + str(nlp_response)
                                    append_log(log_message,log_file_path)
                                    print(nlp_response)
                                    if 'data' in nlp_response:
                                        if 'derived_value' in nlp_response['data']:
                                            result = nlp_response['data']['derived_value'][0]['results']
                                            print("stt api result ->", result)
                                            if len(result) == 0 or type(result) == list or result == "":
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "NA"
                                                audit_score = audit_score + 0
                                            else:
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = result

                                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                    if ans['label'] == result:
                                                        audit_score = audit_score + int(str(ans['score']))

                                    continue
                                elif question["question"] == "Did the dealer induce or force the customer to trade during the call?" and not savedTradeResult:
                                    logger.info("LLM test1 kotak- question 3 no trade found")
                                    continue
                                else:
                                    logger.info("LLM test1 "+str(request_data_nlp))
                                    start_time = datetime.now()
                                    nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                    end_time = datetime.now()
                                    processing_time = (end_time - start_time).total_seconds()
                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                    nlp_response = nlp_raw_response.json()
                                    logger.info("LLM test1 trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                    log_message = "response data: " + str(nlp_response)
                                    append_log(log_message,log_file_path)
                                    logger.info("LLM test1 "+str(nlp_response))
                                    if 'data' in nlp_response:
                                        if 'derived_value' in nlp_response['data']:
                                            result = nlp_response['data']['derived_value'][0]['result']

                                            if type(result) == list and len(result) == 0:
                                                result = 'NA'
                                            if len(result) > 0 and result.lower() != 'no' and result.lower() != "fatal":

                                                if type(result) == list:
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                    audit_score = audit_score + 0
                                                if result.lower() == "yes":
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'

                                                    for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                        if ans['label'] == 'YES':
                                                            audit_score = audit_score + int(str(ans['score']))
                                            
                                                elif result.lower() == "na":
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'

                                                    for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                        if ans['label'] == 'NA':
                                                            audit_score = audit_score + int(str(ans['score']))
                                            
                                            else:

                                                if result.lower() == "fatal":
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Fatal'
                                                else:    
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'
                                            if 'reference' in nlp_response['data']['derived_value'][0]:
                                                reference_text = ''
                                                for index, obj in enumerate(nlp_response['data']['derived_value'][0]['reference']):
                                                    if obj['text'] == 'Model timed out':
                                                        obj['text'] = 'NA'
                                                    reference_text = reference_text + obj['text'] + ' '
                                                    timing = { "startTime": obj['start_time'],
                                                                "endTime": obj['end_time'],
                                                                "referenceText": obj['text']
                                                            }
                                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['timings'].append(timing)

                                                if len(reference_text) > 0:
                                                    print('1')
                                                    request_data_call_sentiment = { 'text':  reference_text}
                                                
                                                
                                questionIndex = questionIndex + 1
                            

                    sectionIndex = sectionIndex + 1

            logger.info("Audit Form filled")

            

            for sindex, section in enumerate(audit_form):
                logger.info(sindex)
                print("sinex, section -> ", sindex, section)
                for ssIndex, ss in enumerate(section['subSection']):
                    logger.info(ssIndex)
                    for qindex, question in enumerate(ss['questions']):
                        logger.info(qindex)
                        score = 0
                        scored = 0
                        if question["question"] != "Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?" and question["question"] != "Is the price below 15 or quantity above 25000 highlighted and flagged?" and question["question"] != "Was the type of trade correctly identified and recorded as Options, Futures, or Equity/Cash? (Type of Trade)":
                            
                            if 'answer' not in question:
                                question['answer'] = ''
                            if 'sentiment' not in question:
                                question['sentiment'] = ''
                            logger.info(1)
                            for option in question['answerOptions']:
                                logger.info(str(option))
                                logger.info(str(question['answer']))

                                if option['label'].lower() == question['answer'].lower():
                                    scored = int(option['score'])


                                if (option['label'].lower() == 'yes') or (option['label'].lower() == 'good') or (option['label'].lower() == 'normal') or (option['label'].lower() == 'happiness'):
                                    score = int(option['score'])
                            logger.info(2)
                            logger.info(str(question))
                            logger.info(question['sid'])
                            logger.info(question['ssid'])
                            logger.info(question['qid'])
                            logger.info(3)









                            dataBase2 = mysql.connector.connect(
                            host =os.environ.get('MYSQL_HOST'),
                            user =os.environ.get('MYSQL_USER'),
                            password =os.environ.get('MYSQL_PASSWORD'),
                            database = os.environ.get('MYSQL_DATABASE'),
                            connection_timeout= 86400000
                            )

                            cursorObjectInsert = dataBase2.cursor(buffered=True)
                            add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment, isCritical, applicableTo) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                            add_result = (process_id,call_id,question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '', question["isCritical"], question["isApplicableTo"])



                            cursorObjectInsert.execute(add_column, add_result)
                            
                            dataBase2.commit()
                            cursorObjectInsert.close()

                            cursorObject = dataBase2.cursor(buffered=True)
                            logger.info("save done 1")
                            logger.info(str(call_id))
                            logger.info(str(question['sid']))
                            logger.info(str(question['qid']))
                            logger.info("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))

                            cursorObject.execute("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))
                        
                            savedQuestionResult = cursorObject.fetchone()


                            logger.info("saved done"+str(savedQuestionResult[0]))
                            for tindex, timing in enumerate(question['timings']):
                                add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")

                                add_result = (timing['startTime'],timing['endTime'],'',timing['referenceText'], savedQuestionResult[0])

                                cursorObject.execute(add_column, add_result)
                                
                                dataBase2.commit()
                                print("save done 2")
            print("---------")
            print("Update successful - auditFormFilled")
            print("---------")
            

            
            logger.info("LLM trigger status - started")



            dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject = dataBase2.cursor(buffered=True)

            

            end_time_llm = datetime.now()
            start_time_sentiment = datetime.now()
            request_data_call_sentiment = { 'text':  trnascript_for_nlp}
            logger.info("predict_sentiments")
            logger.info(sentiment_endpoint+"/predict_sentiments")
            logger.info(str(request_data_call_sentiment))

            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "AuditDone"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)
            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s,updatedAt = %s
                                WHERE id = %s
                                """

            new_value = "Complete"
            condition_value = call_id
            cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            dataBase2.commit() 
            if sub_process_type == "with_summary":
                
                end_time_cs = datetime.now()
                
                
                end_time_qa = datetime.now()

            else:
                pass        

    try:
        requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": call_id, "status": "AuditDone"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)
    
    # update_query = """
    #                     UPDATE auditNexDb.call
    #                     SET status = %s
    #                     WHERE id = %s
    #                     """

    # new_value = "Complete"
    # condition_value = call_id
    # cursorObject.execute(update_query, (new_value,condition_value))
    # dataBase2.commit() 
    
    end_time_llm = datetime.now()
    duration_llm = (end_time_llm - start_time_llm).total_seconds()

    llm_seconds = convert_seconds(int(float(duration_llm)))

    update_query = """
                UPDATE auditNexDb.logs 
                SET  timeLlm = %s
                WHERE filename = %s
    """
    update_values = ( llm_seconds, file_name)

    cursorObject.execute(update_query, update_values)
    dataBase2.commit()
    return

def recognize_speech_file_v4(request_data, callback_url,savedCallResult):
    logger.info("api wrapper recognize_speech_file_v4 with request data: " + str(request_data))
    
    process_id = 1
    audit_form_id = 1
    start_time = datetime.now()
    start_time_stt = datetime.now()
    end_time_stt = datetime.now()
    start_time_llm = datetime.now()
    end_time_llm = datetime.now()
    start_time_qa = datetime.now()
    end_time_qa = datetime.now()
    start_time_cs = datetime.now()
    end_time_cs = datetime.now()
    start_time_sentiment = datetime.now()
    end_time_sentiment = datetime.now()
    # savedCallResult = None
    header = {'Content-Type': "application/json"}
    url = os.environ.get('STT_URL')
    stt_api_url = os.environ.get('STT_API_URL')
    storage_path = os.environ.get('STORAGE_PATH')
    audio_chunks_path = os.environ.get('CHUNKS_PATH')
    nlp_endpoint = os.environ.get('NLP_API')
    sentiment_endpoint = os.environ.get('SENTIMENT_API')
    auditnex_endpoint = os.environ.get('AUDITNEX_API')
    audio_endpoint = os.environ.get('AUDIO_ENDPOINT')
    callback_url_new = os.environ.get('CALLBACK_URL')
    text_output_path = os.environ.get('TEXTOUTPUT')
    audioDuration = 0.0
    myresult = []
    call_id = 0

    process_type = 'sequential'

    log_file_path = '/docker_volume/logs/'+request_data['file_name'].replace('.mp3','.txt').replace('.wav','.txt')
    file_name = request_data['file_name']

    # if 'process_id' in request_data:
    #         logger.info("1")
    #         dataBase2 = mysql.connector.connect(
    #         host =os.environ.get('MYSQL_HOST'),
    #         user =os.environ.get('MYSQL_USER'),
    #         password =os.environ.get('MYSQL_PASSWORD'),
    #         database = os.environ.get('MYSQL_DATABASE'),
    #         connection_timeout= 86400000
    #         )
    #         cursorObject = dataBase2.cursor(buffered=True)
    #         logger.info("SELECT * FROM process where id = "+str(request_data['process_id']))
    #         cursorObject.execute("SELECT * FROM process where id = "+str(request_data['process_id']))
    #         logger.info("2")
    #         processResult = cursorObject.fetchone()
    #         logger.info("3")
    #         print("process result ->",processResult)
    #         process_id = int(processResult[0])
    #         logger.info("4")
    #         audit_form_id = int(processResult[4])
    #         process_type = processResult[8]
    #         logger.info("5")




   
    dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
    cursorObject = dataBase2.cursor(buffered=True)
    
             
    # print("SELECT * FROM auditNexDb.call where callId = '"+str(request_data["call_id"]) + "'")
    # cursorObject.execute("SELECT * FROM auditNexDb.call where callId = '"+str(request_data["call_id"]) + "' and status = 'AuditDone'")
    # logger.info("6") 
    # savedCallResult = cursorObject.fetchone()
    logger.info("7")
    # if not savedCallResult:
    #     return False, "API: Interface Something went wrong:"
    logger.info(savedCallResult[0])
    call_id = savedCallResult[0]
    logger.info("8")
    connectionTrade = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
        )
    cursorObjectTrade = connectionTrade.cursor(dictionary=True,buffered=True)     
    cursorObjectTrade.execute("SELECT * FROM auditNexDb.tradeAudioMapping where audioFileName = '"+str(request_data["file_name"]+"';"))
    logger.info("6") 
    savedTradeResult = cursorObjectTrade.fetchall()
    stockDetails = []
    for trade in savedTradeResult:
        stockDetails.append({"symbol": trade['symbol'], "strikePrice": trade['strikePrice'], "tradeQuantity": trade['tradeQuantity'], "tradePrice": trade['tradePrice'], "buySell": trade['buySell'], "scripName": trade['scripName']})
    
    logger.info(str(stockDetails))
    cursorObjectTrade.close()
    connectionTrade.close()
    logger.info("storing call result" + str(savedCallResult[25]))
    logger.info("getting metadata")

    print("saved call result -> ", savedCallResult)    
    print("saved call result 25 -> ",type(savedCallResult[25]), savedCallResult[25])

    metaData = json.loads(savedCallResult[25])
    logger.info(metaData)
    lid_processing_time = metaData["durationLid"]
    all_chunks = []
    audio_url = audio_endpoint+"/"+request_data['file_name']
    if 'reAudit' in metaData:
        request_data['call_id'] = metaData['call_id']
        request_data['reAudit'] = metaData['reAudit']
        try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": request_data['call_id'], "status": "Pending"}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
    try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "InProgress"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    
        
    # dataBase2 = mysql.connector.connect(
    # host =os.environ.get('MYSQL_HOST'),
    # user =os.environ.get('MYSQL_USER'),
    # password =os.environ.get('MYSQL_PASSWORD'),
    # database = os.environ.get('MYSQL_DATABASE'),
    # connection_timeout= 86400000
    # )
    # cursorObject = dataBase2.cursor(buffered=True)
    
    if os.path.exists(log_file_path):

        # os.remove(log_file_path)
        print(f"File {log_file_path} has been deleted.")
    else:
        print(f"The file {log_file_path} does not exist.")
    log_message = "api wrapper recognize_speech_file_v2 with request data: " + str(request_data)
    append_log(log_message,log_file_path)
    
    stt_request_data = {
        'file_name': '',

        'no_of_speakers': 2,
        'audio_language': ""
    }
   
    if "no_of_speakers" in request_data:
        stt_request_data['no_of_speakers'] = request_data['no_of_speakers']



    
    if "audio_file_path" in request_data:
        stt_request_data['file_name'] = file_name

    if "language" not in request_data:
        lid_request_data = {
            "file_name": file_name,
            "entity": "LID",
            "response": ""
        }
        logger.info(stt_api_url)
        lid_response = requests.post(stt_api_url, headers=header, json=lid_request_data)

        logger.info("LID response -> " + str(lid_response))
        logger.info("LID trigger status - ended ")    
        if lid_response.status_code == 200:
            lid_json_response = lid_response.json()
            language = lid_json_response["data"]["derived_value"][0]["results"][0]
            if language == "hinglish":
                stt_request_data["audio_language"] = "hi"
            else:   
                stt_request_data["audio_language"] = language
    else:
        if request_data["language"] == "hinglish":
            stt_request_data["audio_language"] = "hi"
        else:
            stt_request_data["audio_language"] = request_data["language"]
    
    if (stt_request_data["audio_language"] != "en") and (stt_request_data["audio_language"] != "hi") and (stt_request_data["audio_language"] != "hinglish"):
        update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s
                        WHERE id = %s
                        """

        new_value = "Complete"
        condition_value = call_id
        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit()
        audio_file_path = storage_path+file_name
        if os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                print(f"File {audio_file_path} has been deleted successfully.")
            except OSError as e:
                print(f"Error: {e.strerror} - {e.filename}")
        else:
            print(f"The file {audio_file_path} does not exist.")

        logger.info("API: Language not supported")
        return False, "API: Language not supported"
    



    start_time_stt = datetime.now()        
    logger.info("STT trigger status - started" )
    logger.info("stt_request_data" + str(stt_request_data))
    logger.info("stt url called" + str(url))                            
    trnascript_for_nlp = ''

    cursorObject.execute("SELECT * FROM transcript tr WHERE tr.callId = "+ str(call_id) +"")

    all_tr_data = cursorObject.fetchall()
    
    
    for row in all_tr_data:
        
        s1, s2 = row[5].split(" ")
        all_chunks.append({'start_time': row[3], 'end_time': row[4], 'speaker': s2, 'transcript': row[6] })
        if "enable_speaker_detection" in request_data and request_data['enable_speaker_detection'] == True:
            trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+str(row[3]) + ' '+str(row[5]) + ':' + ' ' + str(row[6]) + ' ' + 'end_time: '+str(row[4]) + '\n'

        else:
            trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+str(row[3]) + ' '+str(row[5]) + ':' + ' ' + str(row[6]) + ' ' + 'end_time: '+str(row[4]) + '\n'
            # trnascript_for_nlp = trnascript_for_nlp + ' ' + row[6] + '.'


    if True:
            
            if process_type == 'sttwithllm':
                sub_process_type = 'without_summary'
            else:
                sub_process_type = 'with_summary'

            cursorObject.execute("SELECT * FROM auditForm where id = "+str(audit_form_id))
            
            auditformresult = cursorObject.fetchone()

            
            cursorObject.execute("SELECT afsqm.*, s.*, q.* FROM auditFormSectionQuestionMapping afsqm INNER JOIN section s ON afsqm.sectionId = s.id INNER JOIN question q ON afsqm.questionId = q.id WHERE afsqm.auditFormId = "+ str(audit_form_id) +" AND s.id IN ( SELECT sectionId FROM auditFormSectionQuestionMapping WHERE auditFormId = "+ str(audit_form_id) +")")

            all_form_data = cursorObject.fetchall()
            

            audit_form = []
            audit_formIndex = -1
            section_list = []
            audio_language = ''
            for row in all_form_data:
                

                answerOptions = []
                cursorObject.execute('SELECT * from answerOption ao  WHERE questionId  = '+str(row[4]))
                all_option_data = cursorObject.fetchall()
                logger.info(row[0])

                for row2 in all_option_data:
                    answerOptions.append({'label':row2[3],'score': row2[4]})

                if row[2] not in section_list:

                        section_list.append(row[2])

                        section = {'section': row[7], 'subSection':[{'ssid':row[3],'questions': []}]}

                        if audio_language == "hi":
                            section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        else:
                            section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        audit_form.append(section)
                        audit_formIndex = audit_formIndex + 1
                else:

                    index = section_list.index(row[2])



                    subsFound = False
                    for section in audit_form:

                        for subs in section['subSection']:
                            if subs['ssid'] == row[3]:
                                subsFound = True

                                if audio_language == "hi":
                                    audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                                else:
                                    audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})

                    if subsFound == False:
                        audit_form[audit_formIndex]['subSection'].append({'ssid':row[3],'questions': []})
                        if audio_language == "hi":
                            audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        else:
                            audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                    
                        
            logger.info(audit_form)

            log_message = "stt response: " + str(trnascript_for_nlp)
            append_log(log_message,log_file_path)

            log_message = "audit form: " + str(audit_form)
            append_log(log_message,log_file_path)
            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Auditing"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)

            # update_query = """
            #                     UPDATE auditNexDb.call
            #                     SET status = %s,updatedAt = %s
            #                     WHERE id = %s
            #                     """

            # new_value = "Auditing"
            # condition_value = savedCallResult[0]
            # cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            # dataBase2.commit()    
            audit_score = 0
            sectionIndex = 0
            trade_type_result = ''
            for section in audit_form:
                if section['section'] != 'Call Category':
                    questionIndex = 0
                    for ssIndex, ss in enumerate(section['subSection']):
                        for qIndex, question in enumerate(ss['questions']):



                            request_data_nlp = {
                                "text": trnascript_for_nlp,
                                "prompts": [
                                    {
                                        "entity": question['attribute'],
                                        "prompts": [question['intents']],
                                        "type": "multiple"
                                    }
                                ],
                                "additional_params": {}
                            }

                            request_data_stt_param = {
                                "file_name": file_name,
                                "file_url": audio_url,
                                "entity": question['intents'],
                                "response": all_chunks
                            }


                            logger.info("LLM trigger status - request")
                            logger.info(str(question))
                            if question['attribute'] == "speech_parameter":
                                logger.info(str(request_data_stt_param))
                            else:
                                logger.info(str(request_data_nlp))
                            log_message = "Sequence: " +str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex)
                            append_log(log_message,log_file_path)
                            log_message = "question: " + str(question)
                            append_log(log_message,log_file_path)
                            if question['attribute'] == "speech_parameter":
                                log_message = "request data: " + str(request_data_stt_param)
                                append_log(log_message,log_file_path)
                            else:
                                log_message = "request data: " + str(request_data_nlp)
                                append_log(log_message,log_file_path)
                                      
                            print("entity -> ",request_data_nlp["prompts"][0]["entity"])
                            print("intent -> ", request_data_nlp["prompts"][0]["prompts"][0])
                            language_id = savedCallResult[6]
                            translate_endpoint = os.environ.get('NLP_TRANSLATE_API') or "http://translate:7060"
                            logger.info("***********************4567890*****************")
                            logger.info(f"LLM test trnascript_for_nlp: {trnascript_for_nlp}")
                            logger.info(f"LLM test language_id: {language_id}")
                            logger.info(f"LLM test question: {question['question']}")
                            if question["question"] == "Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?":
                                logger.info("1")
                                # if (language_id == 3) or (language_id == 140) or (language_id == '3') or (language_id == '140'):
                                #     logger.info("2")
                                #     transcript_query = "SELECT * from auditNexDb.transcript WHERE languageId = "+str(language_id)+" and callId = "+ str(call_id)
                                #     cursorObject.execute(transcript_query)
                                #     transcript_output = cursorObject.fetchall()
                                #     transcript_nlp = ""
                                #     for row in transcript_output:
                                #         transcript_nlp = transcript_nlp + ' ' + 'start_time: '+str(row[3]) + ' '+str(row[5]) + ':' + ' ' + str(row[6]) + ' ' + 'end_time: '+str(row[4]) + '\n'
                                #         # transcript_nlp += " start_time: "+str(item["startTime"]) + " "+ item["speaker"] + ": " + item["text"] + " end_time: "+ str(item["endTime"])+"\\n"
                                #     logger.info(str(transcript_nlp))
                                #     request_data_nlp = {
                                #         "text": transcript_nlp,
                                #         "service": "translation",
                                #         "language": str(language_id),
                                #         "languageId": str(language_id),
                                #         "callId":  str(call_id)
                                #     }
                                #     logger.info(translate_endpoint)
                                #     logger.info(request_data_nlp)
                                #     nlp_raw_response = requests.post(translate_endpoint+"/translate", headers=header, json=request_data_nlp, timeout=150)
                                #     nlp_response = nlp_raw_response.json()
                                #     logger.info(nlp_response)
                                #     logger.info("converted text")
                                #     trnascript_for_nlp = ""
                                #     for t in nlp_response:        
                                #         trnascript_for_nlp += " start_time: " + (str(t['startTime'])) + " " + t['speaker'] + ": " + t["text"] + " end_time: "+ (str(t['endTime'])) + "\\n"

                                #     logger.info(trnascript_for_nlp)
                                # request_data_nlp = {
                                #     "text": trnascript_for_nlp,
                                #     "stockDetails": stockDetails,
                                #     "prompts": [
                                #         {
                                #             "entity": "trade_extraction",
                                #             "prompts":  ["Extract all the unique stock names and stock indexes mentioned in the following conversation. The output must be a strictly formatted JSON array like ['name1', 'name2', 'name3', ...] in given language with no duplicates, explanations, additional text, or formatting. Include only stock names and indexes, ensuring accurate extraction.","Extract trade details for the stock name 'Stock Name' from the given conversation. Identify only valid, unique occurrences of option trades related to this stock. Extract the following fields for each: 'options type': 'call' or 'put', 'lot/quantity': numeric only (e.g., 1, 3, 50), 'strike price': numeric only, 'trade price': numeric only, 'buy/sell': 'Buy' or 'Sell'. If any detail is missing, mark it as 'NA'. Do not repeat the same entry. Return strictly a JSON array of objects in the following format (no extra text): [{'options type': 'call/put','lot/quantity': number,'strike price': number,'trade price': number,'buy/sell': 'Buy/Sell'}]."],
                                #             "type": "multiple"
                                #         }
                                #     ],
                                #     "additional_params": {}
                                # }
                                request_data_nlp = {
                                    "text": trnascript_for_nlp,
                                    "text_language": stt_request_data["audio_language"],
                                    "prompts": [""],
                                    "additional_params": {
                                        "trade_details": stockDetails
                                    }
                                }
                                # request_data_nlp = {
                                #     "text": trnascript_for_nlp,
                                #     "trade_details": stockDetails,
                                #     "text_language": stt_request_data["audio_language"],
                                #     "prompts": [
                                #         {
                                #             # "entity": "trade_try",
                                #             "entity": "trade_extraction",
                                #             "prompts":  ["List all the individual stocks were discussed with their corresponding stock name, options, lot/quantity, strike price, trade price, and buy/sell in a valid JSON format like: [{'stock name':'name', 'options':'call/put','lot/quantity': 'value', 'strike price','value', 'trade price': 'value', 'buy/sell': 'value'}]. Terms and Definitions of strock details: stock name: refers to the name of the security or stock being discussed. options: Call : Right to Buy – Grants the holder the right to purchase the underlying asset at a specified strike price before expiration. Call options are used when investors expect the asset’s price to rise. If the asset’s market price surpasses the strike price, the holder may buy at the lower strike price and potentially sell at a higher market value for profit. Put: Right to Sell – Grants the holder the right to sell the underlying asset at a specified strike price before expiration. Put options are advantageous when the asset’s price is expected to fall. If the price drops below the strike price, the holder can sell at the higher strike price, with the option to repurchase at a lower market price for profit. Lot/quantity: Represents the total number of option contracts or the quantity of options traded.It can be either only whole number or whole number along with 'lot' keyword. strike price: This predetermined price allows the option holder to buy (in a call option) or sell (in a put option) the underlying asset, as specified in the options contract. Strike price always assosiated with keyword 'call' or 'put'. Strike price is always expressed in whole number only. trade price: The last traded price of the discussed stock. The price is typically a whole number or a decimal number. buy/sell: Specifies if the stock was buy/bought ('Buy') or sell/sold ('Sell'). If any of the parameter is not available, then mark as 'NA'. Output for stock name should always be in English. Output for lot or quantity, strike price and trade price should be numeric values and present in english digits for example: 3, 1250, 259.65, 765 etc. Ensure no duplicates, include only relevant details, and avoid any additional text, explanations, or formatting."],
                                #             "type": "multiple"
                                #         }
                                #     ],
                                #     "additional_params": {}
                                # }
                                
                                # logger.info(str(request_data_nlp))
                                logger.info("LLM test first parameter request -> "+str(request_data_nlp) )
                                nlp_raw_response = requests.post(os.environ.get('NLP_API_Q1')+"/extract_information", headers=header, json=request_data_nlp, timeout=300)
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM test LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                logger.info("LLM test first parameter response -> "+str(nlp_response) )

                                log_message = "LLM test response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                dataBase2 = mysql.connector.connect(
                                                host =os.environ.get('MYSQL_HOST'),
                                                user =os.environ.get('MYSQL_USER'),
                                                password =os.environ.get('MYSQL_PASSWORD'),
                                                database = os.environ.get('MYSQL_DATABASE'),
                                                connection_timeout= 86400000
                                                )
                                if 'data' in nlp_response:
                                    result = nlp_response["data"]["derived_value"][0]["result"]
                                    if result != "NA":
                                        try:
                                            for item in result:

                                                script_name = item["scriptName"]
                                                option_type = item["optionType"]
                                                lot = ""
                                                quantity = 0
                                                if "lot/quantity" in item and item["lot/quantity"].lo != "NA":
                                                    quantity = item["lot/quantity"]
                                                strike_price = 0
                                                if "strikePrice" in item and item["strikePrice"] != "NA":
                                                    strike_price = item["strikePrice"]
                                                trade_date = item["tradeDate"]
                                                expiry_date = item["expiryDate"]
                                                trade_price = 0
                                                if "tradePrice" in item and item["tradePrice"] != "NA":
                                                    trade_price = item["tradePrice"]
                                                buy_sell = item["buySell"]
                                                if "currentMarket" in item:
                                                    current_market_price = item["currentMarket"]
                                                
                                                cursorObject = dataBase2.cursor(buffered=True)

                                                add_column = ("INSERT INTO callConversation (callId, scriptName, optionType, lotQuantity, strikePrice, tradeDate, expiryDate, tradePrice, buySell,currentMarketPrice, batchId) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s)")

                                                add_result = (call_id,script_name, option_type, quantity, strike_price, trade_date, expiry_date, trade_price, buy_sell,current_market_price, savedCallResult[30])

                                                cursorObject.execute(add_column, add_result)
                                                dataBase2.commit()
    
                                        except:
                                            continue

                                continue
                            
                            if question["question"] == "Was the type of trade correctly identified and recorded as Options, Futures, or Equity/Cash? (Type of Trade)":
                                trade_type_result = trade_type_check(call_id)
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = trade_type_result
                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    if ans['label'] == 'NA':
                                        audit_score = audit_score + int(str(ans['score']))
                                continue
                            
                            if question["question"] == "Is the price below 15 or quantity above 25000 highlighted and flagged?":
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'

                                # if trade_type_result == "Equity/Cash":
                                #     quantity_discrepancy_result = quantity_check(call_id)
                                #     if quantity_discrepancy_result:
                                #         quantity_result = "YES"
                                #     else:
                                #         quantity_result = "NO"
                                #     print("quantity_result ->", quantity_result)

                                # else:
                                #     quantity_result = "NA"
    
                                
                                
                                
                                # audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = quantity_result
                                # for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                #     if ans['label'] == 'NA':
                                #         audit_score = audit_score + int(str(ans['score']))
                                continue

                            

                                        
                            questionIndex = questionIndex + 1
                           

                sectionIndex = sectionIndex + 1

            logger.info("Audit Form filled")

            

            for sindex, section in enumerate(audit_form):
                logger.info(sindex)
                print("sinex, section -> ", sindex, section)
                for ssIndex, ss in enumerate(section['subSection']):
                    logger.info(ssIndex)
                    for qindex, question in enumerate(ss['questions']):
                        logger.info(qindex)
                        score = 0
                        scored = 0
                        if question["question"] == "Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?" or question["question"] == "Is the price below 15 or quantity above 25000 highlighted and flagged?" or question["question"] == "Was the type of trade correctly identified and recorded as Options, Futures, or Equity/Cash? (Type of Trade)":
                            if 'answer' not in question:
                                question['answer'] = ''
                            if 'sentiment' not in question:
                                question['sentiment'] = ''
                            logger.info(1)
                            for option in question['answerOptions']:
                                logger.info(str(option))
                                logger.info(str(question['answer']))

                                if option['label'].lower() == question['answer'].lower():
                                    scored = int(option['score'])


                                if (option['label'].lower() == 'yes') or (option['label'].lower() == 'good') or (option['label'].lower() == 'normal') or (option['label'].lower() == 'happiness'):
                                    score = int(option['score'])
                            logger.info(2)
                            logger.info(str(question))
                            logger.info(question['sid'])
                            logger.info(question['ssid'])
                            logger.info(question['qid'])
                            logger.info(3)









                            dataBase2 = mysql.connector.connect(
                            host =os.environ.get('MYSQL_HOST'),
                            user =os.environ.get('MYSQL_USER'),
                            password =os.environ.get('MYSQL_PASSWORD'),
                            database = os.environ.get('MYSQL_DATABASE'),
                            connection_timeout= 86400000
                            )

                            cursorObjectInsert = dataBase2.cursor(buffered=True)
                            add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment, isCritical, applicableTo) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                            add_result = (process_id,call_id,question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '', question["isCritical"], question["isApplicableTo"])



                            cursorObjectInsert.execute(add_column, add_result)
                            
                            dataBase2.commit()
                            cursorObjectInsert.close()

                            cursorObject = dataBase2.cursor(buffered=True)
                            logger.info("save done 1")
                            logger.info(str(call_id))
                            logger.info(str(question['sid']))
                            logger.info(str(question['qid']))
                            logger.info("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))

                            cursorObject.execute("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))
                        
                            savedQuestionResult = cursorObject.fetchone()


                            logger.info("saved done"+str(savedQuestionResult[0]))
                            for tindex, timing in enumerate(question['timings']):
                                add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")

                                add_result = (timing['startTime'],timing['endTime'],'',timing['referenceText'], savedQuestionResult[0])

                                cursorObject.execute(add_column, add_result)
                                
                                dataBase2.commit()
                                print("save done 2")
            print("---------")
            print("Update successful - auditFormFilled")
            print("---------")
            

            
            logger.info("LLM trigger status - started")



            dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject = dataBase2.cursor(buffered=True)

            

            end_time_llm = datetime.now()
            start_time_sentiment = datetime.now()
            request_data_call_sentiment = { 'text':  trnascript_for_nlp}
            logger.info("predict_sentiments")
            logger.info(sentiment_endpoint+"/predict_sentiments")
            logger.info(str(request_data_call_sentiment))

            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "AuditDone"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)
           
            if sub_process_type == "with_summary":
                
                end_time_cs = datetime.now()
                
                
                end_time_qa = datetime.now()

            else:
                pass        

    try:
        requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": call_id, "status": "AuditDone"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)
    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s,updatedAt = %s
                        WHERE id = %s
                        """

    new_value = "AuditDone"
    condition_value = call_id
    cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
    dataBase2.commit() 
    end_time_llm = datetime.now()
    duration_llm = (end_time_llm - start_time_llm).total_seconds()

    llm_seconds = convert_seconds(int(float(duration_llm)))

    update_query = """
                UPDATE auditNexDb.logs 
                SET  timeLlm = %s
                WHERE filename = %s
    """
    update_values = ( llm_seconds, file_name)

    cursorObject.execute(update_query, update_values)
    dataBase2.commit()
    return

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
    container = get_container_by_name(service_name)
    if container:
        container.stop()
        print(f"Stopped service: {service_name}")
    else:
        print(f"Service {service_name} not found or not in network")

def start_service(service_name):
    container = get_container_by_name(service_name)
    if container:
        container.start()
        print(f"Started service: {service_name}")
    else:
        print(f"Service {service_name} not found or not in network")

def get_audio_duration(file_path):
    audio = File(file_path)
    if audio is not None:
        duration_seconds = audio.info.length
        duration_minutes = duration_seconds / 60
        return duration_minutes
    else:
        raise Exception(f"Could not read the audio file: {file_path}")
    
def recognize_speech_file_v2(request_data, callback_url,savedCallResult):
    logger.info("api wrapper recognize_speech_file_v2 with request data: " + str(request_data))
    
    process_id = 1
    audit_form_id = 1
    start_time = datetime.now()
    start_time_stt = datetime.now()
    end_time_stt = datetime.now()
    start_time_llm = datetime.now()
    end_time_llm = datetime.now()
    start_time_qa = datetime.now()
    end_time_qa = datetime.now()
    start_time_cs = datetime.now()
    end_time_cs = datetime.now()
    start_time_sentiment = datetime.now()
    end_time_sentiment = datetime.now()
    # savedCallResult = None
    header = {'Content-Type': "application/json"}
    url = os.environ.get('STT_URL')
    stt_api_url = os.environ.get('STT_API_URL')
    storage_path = os.environ.get('STORAGE_PATH')
    audio_chunks_path = os.environ.get('CHUNKS_PATH')
    nlp_endpoint = os.environ.get('NLP_API')
    sentiment_endpoint = os.environ.get('SENTIMENT_API')
    auditnex_endpoint = os.environ.get('AUDITNEX_API')
    audio_endpoint = os.environ.get('AUDIO_ENDPOINT')
    callback_url_new = os.environ.get('CALLBACK_URL')
    text_output_path = os.environ.get('TEXTOUTPUT')
    diarization = os.environ.get('DIARIZATION')
    audioDuration = 0.0
    myresult = []
    call_id = 0
    file_path = storage_path+request_data['file_name']
    # duration_in_minutes = get_audio_duration(file_path)
    # logger.info('*************Duration Call**********')
    # logger.info(str(duration_in_minutes))
    process_type = 'sequential'
    # LICENSE_TOKEN = client.get_local_license_key_by_process_id(request_data['process_id'])
    LICENSE_TOKEN = 'AAA'
    INSTANCE_ID = os.environ.get('INSTANCE_ID')
    log_file_path = '/docker_volume/logs/'+request_data['file_name'].replace('.mp3','.txt').replace('.wav','.txt')
    audio_file_path = '/docker_volume/shared-files/'+request_data['file_name']
    file_name = request_data['file_name']
    # check_license_response = client.check_license(
    # token=LICENSE_TOKEN,
    # instance_id=INSTANCE_ID
    # )
    # if check_license_response and  'isValid' in check_license_response and check_license_response['isValid'] == False:
    #     sync_response = client.sync_data(
    #     LICENSE_TOKEN,
    #     INSTANCE_ID,0,0,0,0,
    #     0,
    #     "License has been expired"
    #     )
    #     return
    # if check_license_response and  'isValid' not in check_license_response:
    #     sync_response = client.sync_data(
    #     LICENSE_TOKEN,
    #     INSTANCE_ID,0,0,0,0,
    #     0,
    #     "License has been expired"
    #     )
    #     return

    # client.start_monitoring()
    # if 'process_id' in request_data:
    #         logger.info("1")
    #         dataBase2 = mysql.connector.connect(
    #         host =os.environ.get('MYSQL_HOST'),
    #         user =os.environ.get('MYSQL_USER'),
    #         password =os.environ.get('MYSQL_PASSWORD'),
    #         database = os.environ.get('MYSQL_DATABASE'),
    #         connection_timeout= 86400000
    #         )
    #         cursorObject = dataBase2.cursor(buffered=True)
    #         logger.info("SELECT * FROM process where id = "+str(request_data['process_id']))
    #         cursorObject.execute("SELECT * FROM process where id = "+str(request_data['process_id']))
    #         logger.info("2")
    #         processResult = cursorObject.fetchone()
    #         logger.info("3")
    #         print("process result ->",processResult)
    #         process_id = int(processResult[0])
    #         logger.info("4")
    #         audit_form_id = int(processResult[4])
    #         process_type = processResult[8]
    #         logger.info("5")


    dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
    cursorObject = dataBase2.cursor(buffered=True)

   
    
    
             
    # print("SELECT * FROM auditNexDb.call where callId = '"+str(request_data["call_id"]) + "'")
    # cursorObject.execute("SELECT * FROM auditNexDb.call where id = '"+str(request_data["call_id"]))
    # logger.info("6") 
    # savedCallResult = cursorObject.fetchone()
    logger.info("7")
    # if not savedCallResult:
    #     return False, "API: Interface Something went wrong:"
    logger.info(savedCallResult[0])
    call_id = savedCallResult[0]

    if not os.path.exists(audio_file_path):
        logger.info("audio file not present downloading from "+str(savedCallResult[7]))
        response = requests.get(savedCallResult[7])
        response.raise_for_status()
        

        with open(audio_file_path, "wb") as f:
            f.write(response.content) 
    logger.info("audio file checking")   
    if os.path.exists(audio_file_path):
        logger.info("audio file present")
        
    logger.info("8")
    # update_query = """
    #                     UPDATE auditNexDb.call
    #                     SET status = %s,callId = %s
    #                     WHERE id = %s
    #                     """

    # new_value = "Pending"
    # new_value2 = savedCallResult[0]   
    # condition_value = savedCallResult[0]    
    # cursorObject.execute(update_query, (new_value,new_value2,condition_value))
    # dataBase2.commit()       

    logger.info("storing call result" + str(savedCallResult[25]))
    logger.info("getting metadata")

    print("saved call result -> ", savedCallResult)    
    print("saved call result 25 -> ",type(savedCallResult[25]), savedCallResult[25])

    metaData = json.loads(savedCallResult[25])
    logger.info(metaData)
    lid_processing_time = 0
    language_id = 3
    if "durationLid" in metaData:
        lid_processing_time = metaData["durationLid"]
    if "durationLid" in metaData:
        language_id = metaData["languageId"]

    if 'languageId' in request_data:
        language_id = request_data['languageId']

    if 'reAudit' in metaData:
        request_data['call_id'] = metaData['call_id']
        request_data['reAudit'] = metaData['reAudit']
        try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": request_data['call_id'], "status": "Pending"}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
    try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "InProgress"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    # update_query = """
    #                     UPDATE auditNexDb.call
    #                     SET status = %s
    #                     WHERE id = %s
    #                     """

    # new_value = "InProgress"
    # condition_value = savedCallResult[0]
    # cursorObject.execute(update_query, (new_value,condition_value))
    # dataBase2.commit()
        
    # dataBase2 = mysql.connector.connect(
    # host =os.environ.get('MYSQL_HOST'),
    # user =os.environ.get('MYSQL_USER'),
    # password =os.environ.get('MYSQL_PASSWORD'),
    # database = os.environ.get('MYSQL_DATABASE'),
    # connection_timeout= 86400000
    # )
    # cursorObject = dataBase2.cursor(buffered=True)
    
    if os.path.exists(log_file_path):

        os.remove(log_file_path)
        print(f"File {log_file_path} has been deleted.")
    else:
        print(f"The file {log_file_path} does not exist.")
    log_message = "api wrapper recognize_speech_file_v2 with request data: " + str(request_data)
    append_log(log_message,log_file_path)
    
    stt_request_data = {
        'file_name': '',
        'use_time_based': False,
        'no_of_speakers': 2,
        'audio_language': "",
        'use_ivr': True,
        "post_processing": True,
    }
   
    if diarization:
        stt_request_data['no_of_speakers'] = 0
        stt_request_data['use_time_based'] = diarization


    
    if "audio_file_path" in request_data:
        stt_request_data['file_name'] = file_name

    if "language" not in request_data:
        lid_request_data = {
            "file_name": file_name,
            "entity": "LID",
            "response": ""
        }
        logger.info(stt_api_url)
        lid_response = requests.post(stt_api_url, headers=header, json=lid_request_data)

        logger.info("LID response -> " + str(lid_response))
        logger.info("LID trigger status - ended ")    
        if lid_response.status_code == 200:
            lid_json_response = lid_response.json()
            language = lid_json_response["data"]["derived_value"][0]["results"][0]
            if language == "hinglish":
                stt_request_data["audio_language"] = "hi"
            else:   
                stt_request_data["audio_language"] = language
    else:
        if request_data["language"] == "hinglish":
            stt_request_data["audio_language"] = "hi"
        else:
            stt_request_data["audio_language"] = request_data["language"]
    audio_file_path = storage_path+file_name
    duration_secs = request_data["audioDuration"]
    logger.info("****** audioduration "+str(duration_secs))
    if duration_secs <= 5:
        update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s,updatedAt = %s
                        WHERE id = %s
                        """

        new_value = "ShortCall"
        condition_value = call_id
        cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
        dataBase2.commit()
        audio_file_path = storage_path+file_name
        if os.path.exists(audio_file_path):
            try:
                # os.remove(audio_file_path)
                print(f"File {audio_file_path} has been deleted successfully.")
            except OSError as e:
                print(f"Error: {e.strerror} - {e.filename}")
        else:
            print(f"The file {audio_file_path} does not exist.")

        logger.info("API: Language not supported")
        return False, "API: Language not supported"
    if (stt_request_data["audio_language"] != "en") and (stt_request_data["audio_language"] != "hi") and (stt_request_data["audio_language"] != "hinglish"):
        update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s,updatedAt = %s
                        WHERE id = %s
                        """

        new_value = "UnsupportedLanguage"
        condition_value = call_id
        cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
        dataBase2.commit()
        audio_file_path = storage_path+file_name
        if os.path.exists(audio_file_path):
            try:
                # os.remove(audio_file_path)
                print(f"File {audio_file_path} has been deleted successfully.")
            except OSError as e:
                print(f"Error: {e.strerror} - {e.filename}")
        else:
            print(f"The file {audio_file_path} does not exist.")

        logger.info("API: Language not supported")
        return False, "API: Language not supported"
    



    start_time_stt = datetime.now()        
    logger.info("STT trigger status - started" )
    logger.info("stt_request_data" + str(stt_request_data))
    logger.info("stt url called" + str(url))                            
    trnascript_for_nlp = ''
    try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Transcription"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s
                        WHERE id = %s
                        """

    new_value = "Transcription"
    condition_value = savedCallResult[0]
    cursorObject.execute(update_query, (new_value,condition_value))
    dataBase2.commit()

    


         





    try:
        response = requests.post(url, headers=header, json=stt_request_data)
    except requests.exceptions.RequestException as e:
        try:
            logger.info("STT Exception1 - "+str(e))
            logger.info("Restarting STT and VAD services")
            stop_service('stt-inference')
            stop_service('smb-vad')
            time.sleep(30)
            start_service('stt-inference')
            start_service('smb-vad')
            time.sleep(180)
            response = requests.post(url, headers=header, json=stt_request_data)
        except requests.exceptions.RequestException as e:
            logger.info("STT Exception2 - "+str(e))
            logger.info("Restarting STT and VAD services")
            stop_service('stt-inference')
            stop_service('smb-vad')
            time.sleep(30)
            start_service('stt-inference')
            start_service('smb-vad')
            time.sleep(180)
            try:
                response = requests.post(url, headers=header, json=stt_request_data)
            except requests.exceptions.RequestException as e:
                logger.info("STT Exception3 - "+str(e))
                logger.info("Restarting STT and VAD services")
                update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s
                        WHERE id = %s
                        """

                new_value = "Pending"
                condition_value = savedCallResult[0]
                cursorObject.execute(update_query, (new_value,condition_value))
                dataBase2.commit()
                return
    print("stt status code -> ", response.status_code)
    print("stt response -> ", response)
    logger.info("STT trigger status - ended ")
    all_chunks = []
    
    if response.status_code == 200:
        stt_json_response = response.json()
        print("stt output -> ",stt_json_response)
        confidence = 0.0
        cnter = 0.0
        all_chunks = stt_json_response[1]
        vad_processing_time = stt_json_response[5]["VAD_time"]
        for t in stt_json_response[1]:
            logger.info(t['confidence'])
            if 'confidence' in t and t['confidence'] != 'nan':
                logger.info('inside')
                confidence = confidence + float(t['confidence'])
                cnter = cnter + 1
        logger.info(confidence)
        if cnter != 0.0:
            confidence = confidence / cnter
        
        logger.info('1')
        confidence = confidence * 100
        logger.info('2')
        confidence = round(confidence, 2)
        logger.info('3')
        if "enable_speaker_detection" in request_data and request_data['enable_speaker_detection'] == True:
            for t in stt_json_response[1]:
                if str(t['speaker']) == '0':
                        t['speaker'] = '1'
                elif str(t['speaker']) ==  '1':
                        t['speaker'] = '2'
                trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+t['start_time'] + ' Speaker '+t['speaker'] + ':' + ' ' + t['transcript'] + ' ' + 'end_time: '+t['end_time'] + '\n'

        else:
            for t in stt_json_response[1]:
                trnascript_for_nlp = trnascript_for_nlp + ' ' + t['transcript'] + '.'
        


        nlp_data = []
        









        final_response = { "status": "success", "transcript":  trnascript_for_nlp, "overall_confidence_level": confidence, "audio_file_duration": stt_json_response[0],"processing_time":stt_json_response[2]}
        logger.info(stt_json_response)








        if "file_name" in stt_request_data:
            final_response['file_name'] = stt_request_data['file_name']
        header = {'Content-Type': "application/json", 'Authorization': "c2Jpei1zbWFydC1zcGVlY2gtMjAyMQ=="}
        file_name = request_data['file_name']
        input_json = stt_json_response
        total_confidence = 0
        
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        trnascript_for_nlp = ''

        print("call_id", call_id, type(call_id))

        try:
            logger.info("LLM trigger status - started")

            

            for t in stt_json_response[1]:

                if str(t['speaker']) == '0':
                    t['speaker'] = '1'
                elif str(t['speaker']) == '1':
                    t['speaker'] = '2'

                trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+t['start_time'] + ' Speaker '+t['speaker'] + ':' + ' ' + t['transcript'] + ' ' + 'end_time: '+t['end_time'] + '\n'
            
            output_json = {
                "callId": int(call_id),
                "callTime": ''+formatted_datetime,
                "processingTime": convert_seconds(round(float(stt_json_response[2]))),
                "audioLength": convert_seconds(round(float(stt_json_response[0]))),
                "confidence": 100,
                "wordConfidence": 100,
                "text": trnascript_for_nlp,
                "chunk": []
            }

            print("output json -> ", output_json)

            try:
                txt_filename = request_data['file_name'].replace(".wav", ".txt")
                txt_filename = txt_filename.replace(".wav", ".txt")
                txt_file_path = text_output_path+txt_filename
                logger.info("stt text file path -> "+txt_file_path)
                with open(txt_file_path, "a", encoding='utf-8') as file:
                    for t in stt_json_response[1]:
                        txt_transcript = 'start_time: '+t['start_time'] + ' Speaker '+t['speaker'] + ':' + ' ' + t['transcript'] + ' ' + 'end_time: '+t['end_time'] + "\\n"
                        file.write(f'"{txt_transcript}"\n')        
                
            except:
                print("error converting to transcript output to text file")

            for chunk in input_json[1]:





                new_chunk = {
                    "progress": "inprogress",
                    "processingTime": 6,  # Static value as example, modify if needed
                    "confidence": 0.0,
                    "active": "false",
                    "text": '<b>Speaker '+chunk['speaker']+':</b>'+chunk['transcript'],
                    "startTime": float(chunk['start_time']),
                    "endTime": float(chunk['end_time']),
                    "audioLength": float(chunk['end_time']) - float(chunk['start_time'])  # Placeholder, modify if individual audio length per chunk is available
                }
                if 'confidence' in chunk and chunk['confidence'] != 'nan':
                    new_chunk['confidence'] = round(float(chunk['confidence']) * 100, 2)
                    if math.isnan(new_chunk['confidence']): 
                        new_chunk['confidence'] = 85.23
                    
                total_confidence += new_chunk['confidence'] 
                output_json['chunk'].append(new_chunk)
            

            print("new chunk loop completed")

            t_length = 1
            if len(input_json[1]) != 0:
                t_length = len(input_json[1])
            average_confidence = round(total_confidence / t_length, 2)
            audit_score = 0
            if math.isnan(average_confidence): 
                output_json['confidence'] = 85.23
                output_json['wordConfidence'] = 85.23
            else:
                output_json['confidence'] = average_confidence
                output_json['wordConfidence'] = average_confidence 
            logger.info("done confidence")
            
        
        except Exception as e:
                    logger.error(str(e))
                    print(e)
                    return False, "API: Interface Something went wrong:"  + str(e)
        
        
        try:
            logger.info("Insert call")
           
            
            audio_url = audio_endpoint+"/"+request_data['file_name']
            logger.info(audio_url)
            logger.info(process_id)
            logger.info(audit_form_id)
            logger.info(""+str(call_id))
            logger.info(""+str(final_response))
            

            update_query = """
            UPDATE auditNexDb.call
            SET audioDuration = %s, processingTime = %s, confidence = %s, wordConfidence = %s, status = %s, emotion = %s, rateOfSpeech = %s, engagement = %s, callOpening = %s, holdManagement = %s, tonalAnalysis = %s, updatedAt = %s
            WHERE id = %s
            """

            new_value1 = final_response['audio_file_duration']
            new_value2 = final_response['processing_time']
            new_value3 = output_json['confidence']
            new_value4 = output_json['wordConfidence']
            new_value5 = 'TranscriptDone'






            new_value11 = stt_json_response[3]["language"]

            print("audio language -> ", new_value11)
            audio_language = new_value11
            condition_value = call_id

            dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject = dataBase2.cursor(buffered=True)


            cursorObject.execute(update_query, (new_value1,new_value2,new_value3,new_value4,new_value5, None, None, None, None, None, None, datetime.now().replace(microsecond=0),condition_value))
            dataBase2.commit()

















            logger.info("Update call Done ")
            
        except Exception as e:
                    logger.error(str(e))
                    print(e)
                    return False, "API: Interface Something went wrong:"  + str(e)
        

        
    
        update_query = """
                            UPDATE auditNexDb.call
                            SET callId = %s
                            WHERE id = %s
                            """

        new_value = savedCallResult[0]
        condition_value = savedCallResult[0]

        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit()

        try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "TranscriptDone", "audioDuration": final_response['audio_file_duration']}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
        update_query = """
                            UPDATE auditNexDb.call
                            SET status = %s,updatedAt = %s
                            WHERE id = %s
                            """

        new_value = "TranscriptDone"
        condition_value = call_id
        cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
        dataBase2.commit()    
        # cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
    
        # savedCallResult = cursorObject.fetchone()
        audioDuration = str(final_response['audio_file_duration'])
        if True or 'reAudit' not in request_data:
            delete_query = "DELETE FROM auditNexDb.transcript WHERE callId = '"+str(call_id)+"';"
            cursorObject.execute(delete_query)
            dataBase2.commit()
        for t in all_chunks:
            add_column = ("INSERT INTO transcript (callId, languageId, startTime, endTime, speaker, text, rateOfSpeech, confidence)"
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")

            if t['confidence'] != 'nan':
                add_result = (call_id,int(language_id), float(t['start_time']),float(t['end_time']),'Speaker '+t['speaker'],t['transcript'],6,round(float(t['confidence']) * 100, 2))
            else:
                add_result = (call_id,int(language_id), float(t['start_time']),float(t['end_time']),'Speaker '+t['speaker'],t['transcript'],6,0.0)
            cursorObject.execute(add_column, add_result)
            dataBase2.commit()

        logger.info("Insert transcripts Done ")
        end_time_stt = datetime.now()
        start_time_llm = datetime.now()


        if process_type == 'sttwithllm' or process_type == 'sttwithllmsummary':
            
            if process_type == 'sttwithllm':
                sub_process_type = 'without_summary'
            else:
                sub_process_type = 'with_summary'

            cursorObject.execute("SELECT * FROM auditForm where id = "+str(audit_form_id))
            
            auditformresult = cursorObject.fetchone()

            
            cursorObject.execute("SELECT afsqm.*, s.*, q.* FROM auditFormSectionQuestionMapping afsqm INNER JOIN section s ON afsqm.sectionId = s.id INNER JOIN question q ON afsqm.questionId = q.id WHERE afsqm.auditFormId = "+ str(audit_form_id) +" AND s.id IN ( SELECT sectionId FROM auditFormSectionQuestionMapping WHERE auditFormId = "+ str(audit_form_id) +")")

            all_form_data = cursorObject.fetchall()
            

            audit_form = []
            audit_formIndex = -1
            section_list = []
            for row in all_form_data:
                

                answerOptions = []
                cursorObject.execute('SELECT * from answerOption ao  WHERE questionId  = '+str(row[4]))
                all_option_data = cursorObject.fetchall()
                logger.info(row[0])

                for row2 in all_option_data:
                    answerOptions.append({'label':row2[3],'score': row2[4]})

                if row[2] not in section_list:

                        section_list.append(row[2])

                        section = {'section': row[7], 'subSection':[{'ssid':row[3],'questions': []}]}

                        if audio_language == "hi":
                            section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        else:
                            section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        audit_form.append(section)
                        audit_formIndex = audit_formIndex + 1
                else:

                    index = section_list.index(row[2])



                    subsFound = False
                    for section in audit_form:

                        for subs in section['subSection']:
                            if subs['ssid'] == row[3]:
                                subsFound = True

                                if audio_language == "hi":
                                    audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                                else:
                                    audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})

                    if subsFound == False:
                        audit_form[audit_formIndex]['subSection'].append({'ssid':row[3],'questions': []})
                        if audio_language == "hi":
                            audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                        else:
                            audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': [], 'isCritical': row[5], 'isApplicableTo': row[6]})
                    
                        
            logger.info(audit_form)

            log_message = "stt response: " + str(trnascript_for_nlp)
            append_log(log_message,log_file_path)

            log_message = "audit form: " + str(audit_form)
            append_log(log_message,log_file_path)
            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Auditing"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)

            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s,updatedAt = %s
                                WHERE id = %s
                                """

            new_value = "Auditing"
            condition_value = savedCallResult[0]
            cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            dataBase2.commit()    
            audit_score = 0
            sectionIndex = 0
            for section in audit_form:
                if section['section'] != 'Call Category':
                    questionIndex = 0
                    for ssIndex, ss in enumerate(section['subSection']):
                        for qIndex, question in enumerate(ss['questions']):



                            request_data_nlp = {
                                "text": trnascript_for_nlp,
                                "prompts": [
                                    {
                                        "entity": question['attribute'],
                                        "prompts": [question['intents']],
                                        "type": "multiple"
                                    }
                                ],
                                "additional_params": {}
                            }

                            request_data_stt_param = {
                                "file_name": file_name,
                                "file_url": audio_url,
                                "entity": question['intents'],
                                "response": all_chunks
                            }


                            logger.info("LLM trigger status - request")
                            logger.info(str(question))
                            if question['attribute'] == "speech_parameter":
                                logger.info(str(request_data_stt_param))
                            else:
                                logger.info(str(request_data_nlp))
                            log_message = "Sequence: " +str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex)
                            append_log(log_message,log_file_path)
                            log_message = "question: " + str(question)
                            append_log(log_message,log_file_path)
                            if question['attribute'] == "speech_parameter":
                                log_message = "request data: " + str(request_data_stt_param)
                                append_log(log_message,log_file_path)
                            else:
                                log_message = "request data: " + str(request_data_nlp)
                                append_log(log_message,log_file_path)
                                      
                            print("entity -> ",request_data_nlp["prompts"][0]["entity"])
                            print("intent -> ", request_data_nlp["prompts"][0]["prompts"][0])

                            if question["question"] == "Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?":
                                if (language_id == 3) or (language_id == 140):
                                    transcript_query = "SELECT startTime, endTime, speaker, text from auditNexDb.transcript WHERE languageId = "+str(language_id)+" and callId = "+ str(call_id)
                                    cursor.execute(transcript_query)
                                    transcript_output = cursor.fetchall()
                                    transcript_nlp = ""
                                    for item in transcript_output:
                                        transcript_nlp += " start_time: "+str(item["startTime"]) + " "+ item["speaker"] + ": " + item["text"] + " end_time: "+ str(item["endTime"])+"\\n"
                                    logger.info(str(transcript_nlp))
                                    request_data_nlp = {
                                        "text": transcript_nlp,
                                        "service": "translation",
                                        "language": str(language_id),
                                        "languageId": str(language_id),
                                        "callId":  str(call_id)
                                    }
                                    logger.info(translate_endpoint)
                                    nlp_raw_response = requests.post(translate_endpoint+"/translate", headers=header, json=request_data_nlp, timeout=150)
                                    nlp_response = nlp_raw_response.json()

                                    trnascript_for_nlp = ""
                                    for t in nlp_response:        
                                        trnascript_for_nlp += " start_time: " + float(str(t['startTime'])) + " " + t['speaker'] + ": " + item["text"] + " end_time: "+ float(str(t['endTime'])) + "\\n"
                                
                                logger.info(str(request_data_nlp))
                                request_data_nlp = {
                                    "text": trnascript_for_nlp,
                                    "prompts": [
                                        {
                                            "entity": "trade_extraction",
                                            "prompts":  [
                                                    "Extract all the unique stock names and stock indexes mentioned in the following conversation. The output must be a strictly formatted JSON array like ['name1', 'name2', 'name3', ...] in given language with no duplicates, explanations, additional text, or formatting. Include only stock names and indexes, ensuring accurate extraction.", "For the stock name 'Stock Name', extract all the details such as options type in call/put, lot or quantity, strike price, trade price, buy/sell indicator and expiry date from the conversation. If anything is not available for a specific stock, then mark as 'NA' Output for lot or quantity, strike price and market price should be numeric values, for example: 3, 1250, 259.65, 765 etc. Output for trade price should be the last confirmed market price of the stock at the time of trade. Output for expiry date should be english digit and in same format as present in the text. Provide the output strictly as a JSON array with objects formatted as follows: [{'options type':'call/put', 'lot/quantity':'value', 'strike price':'value', 'market price':'value', 'buy/sell':'Buy/Sell', 'expiry date':'date'},...]. Ensure no duplicates, include only relevant details, and avoid any additional text and explanations."
                                                    ],
                                            "type": "multiple"
                                        }
                                    ],
                                    "additional_params": {}
                                }
                                nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=300)
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                print("first parameter response -> ", nlp_response)

                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                if 'data' in nlp_response:
                                    result = nlp_response["data"]["derived_value"][0]["result"]
                                    if result != "NA":
                                        try:
                                            for item in result:

                                                script_name = item["scriptName"]
                                                option_type = item["optionType"]
                                                lot = ""
                                                quantity = item["lot/quantity"]
                                                strike_price = item["strikePrice"]
                                                trade_date = item["tradeDate"]
                                                expiry_date = item["expiryDate"]
                                                trade_price = item["tradePrice"]
                                                buy_sell = item["buySell"]

                                                dataBase2 = mysql.connector.connect(
                                                host =os.environ.get('MYSQL_HOST'),
                                                user =os.environ.get('MYSQL_USER'),
                                                password =os.environ.get('MYSQL_PASSWORD'),
                                                database = os.environ.get('MYSQL_DATABASE'),
                                                connection_timeout= 86400000
                                                )
                                                cursorObject = dataBase2.cursor(buffered=True)

                                                add_column = ("INSERT INTO callConversation (callId, scriptName, optionType, lotQuantity, strikePrice, tradeDate, expiryDate, tradePrice, buySell, batchId) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                                                    
                                                add_result = (call_id,script_name, option_type, quantity, strike_price, trade_date, expiry_date, trade_price, buy_sell, savedCallResult[30])

                                                cursorObject.execute(add_column, add_result)
                                                dataBase2.commit()

                                        except:
                                            continue

                                continue






















                                            





                                        








                                            




















                            elif question["question"] == "Did the customer express frustration or use any abusive language during the call?":
                                
                                print("checking for emotion api")
                                request_data_stt_param["entity"] = "emotion_recognition"
                                start_time = datetime.now()
                                nlp_raw_response = requests.post(stt_api_url, headers=header, json = request_data_stt_param, timeout=150)
                                end_time = datetime.now()
                                processing_time = (end_time - start_time).total_seconds()
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))
                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                print(nlp_response)
                                if 'data' in nlp_response:
                                    if 'derived_value' in nlp_response['data']:
                                        result = nlp_response['data']['derived_value'][0]['results']
                                        print("stt emotion output ->", result)
                                        if result == "anger" or result == "disgust":
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "YES"

                                            for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                if ans['label'] == result:
                                                    audit_score = audit_score + 0
                                    
                                        else:
                                            logger.info(str(request_data_nlp))
                                            nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                            nlp_response = nlp_raw_response.json()
                                            logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))
                                            log_message = "response data: " + str(nlp_response)
                                            append_log(log_message,log_file_path)
                                            print(nlp_response)
                                            if 'data' in nlp_response:
                                                if 'derived_value' in nlp_response['data']:
                                                    result = nlp_response['data']['derived_value'][0]['result']
                                                    print("llm emotion output -> ", result)

                                                    if len(result) > 0:

                                                        if result.lower() == "yes":
                                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'
                                                    
                                                        elif result.lower() == "no":
                                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'

                                                        elif result.lower() == "na":
                                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                        
                                                        else:
                                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'

                                                        audit_score = audit_score + 0
                                                    
                                                    else:
                                                        audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                        audit_score = audit_score + 0

                                continue

                            elif question["question"] == "Is the price below 15 or quantity above 25000 highlighted and flagged?":
                                quantity_discrepancy_result = quantity_check(call_id)
                                if quantity_discrepancy_result:
                                    quantity_result = "YES"
                                else:
                                    quantity_result = "NO"

                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = quantity_result
                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    if ans['label'] == 'NA':
                                        audit_score = audit_score + int(str(ans['score']))
                                continue

                            elif question["question"] == "Was the type of trade correctly identified and recorded as Options, Futures, or Equity/Cash? (Type of Trade)":
                                trade_type_result = trade_type_check(call_id)
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = trade_type_result
                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    if ans['label'] == 'NA':
                                        audit_score = audit_score + int(str(ans['score']))
                                continue

                            elif question["question"] == "Who initiated the trade during the call the client, the dealer or was it mutually decided?":
                                logger.info(str(request_data_nlp))
                                start_time = datetime.now()
                                nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                end_time = datetime.now()
                                processing_time = (end_time - start_time).total_seconds()
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                logger.info(str(nlp_response))
                                if 'data' in nlp_response:
                                    if 'derived_value' in nlp_response['data']:
                                        result = nlp_response['data']['derived_value'][0]['result']

                                        if len(result) > 0 and result.lower() == 'dealer':
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Dealer'
                                        elif len(result) > 0 and result.lower() == 'client':
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Client'
                                        elif len(result) > 0 and result.lower() == 'both':
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Both client & dealer'
                                        else:
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                        if ans['label'] == 'NA':
                                            audit_score = audit_score + int(str(ans['score']))
                                continue

                            elif question["question"] == "Who Conducted the Research Client, Franchise or Kotak Research?":
                                logger.info(str(request_data_nlp))
                                start_time = datetime.now()
                                nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                end_time = datetime.now()
                                processing_time = (end_time - start_time).total_seconds()
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                logger.info(str(nlp_response))
                                if 'data' in nlp_response:
                                    if 'derived_value' in nlp_response['data']:
                                        result = nlp_response['data']['derived_value'][0]['result']

                                        if len(result) > 0 and result.lower() == 'dealer':
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Kotak Research'
                                        elif len(result) > 0 and result.lower() == 'client':
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Client'
                                        else:
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                    for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                        if ans['label'] == 'NA':
                                            audit_score = audit_score + int(str(ans['score']))
                                continue

                            elif request_data_nlp["prompts"][0]["prompts"][0] == "NA":
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "NA"
                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                    if ans['label'] == 'NA':
                                        audit_score = audit_score + int(str(ans['score']))

                                continue

                            elif question['attribute'] == "speech_parameter":
                                print("speech api request -> ", request_data_stt_param)
                                start_time = datetime.now()
                                nlp_raw_response = requests.post(stt_api_url, headers=header, json = request_data_stt_param, timeout=150)
                                end_time = datetime.now()
                                processing_time = (end_time - start_time).total_seconds()
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                print(nlp_response)
                                if 'data' in nlp_response:
                                    if 'derived_value' in nlp_response['data']:
                                        result = nlp_response['data']['derived_value'][0]['results']
                                        print("stt api result ->", result)
                                        if len(result) == 0 or type(result) == list or result == "":
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "NA"
                                            audit_score = audit_score + 0
                                        else:
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = result

                                            for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                if ans['label'] == result:
                                                    audit_score = audit_score + int(str(ans['score']))

                                continue
                                        
                            else:
                                logger.info(str(request_data_nlp))
                                start_time = datetime.now()
                                nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                end_time = datetime.now()
                                processing_time = (end_time - start_time).total_seconds()
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['processingTime'] = processing_time
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                logger.info(str(nlp_response))
                                if 'data' in nlp_response:
                                    if 'derived_value' in nlp_response['data']:
                                        result = nlp_response['data']['derived_value'][0]['result']

                                        if len(result) > 0 and result.lower() != 'no' and result.lower() != "fatal":

                                            if type(result) == list:
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'
                                                audit_score = audit_score + 0
                                            if result.lower() == "yes":
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'

                                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                    if ans['label'] == 'YES':
                                                        audit_score = audit_score + int(str(ans['score']))
                                        
                                            elif result.lower() == "na":
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NA'

                                                for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                    if ans['label'] == 'NA':
                                                        audit_score = audit_score + int(str(ans['score']))
                                        
                                        else:

                                            if result.lower() == "fatal":
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'Fatal'
                                            else:    
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'
                                        if 'reference' in nlp_response['data']['derived_value'][0]:
                                            reference_text = ''
                                            for index, obj in enumerate(nlp_response['data']['derived_value'][0]['reference']):
                                                if obj['text'] == 'Model timed out':
                                                    obj['text'] = 'NA'
                                                reference_text = reference_text + obj['text'] + ' '
                                                timing = { "startTime": obj['start_time'],
                                                            "endTime": obj['end_time'],
                                                            "referenceText": obj['text']
                                                        }
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['timings'].append(timing)

                                            if len(reference_text) > 0:
                                                print('1')
                                                request_data_call_sentiment = { 'text':  reference_text}


                                                

                                                

                                                    
















                                            
                            questionIndex = questionIndex + 1
















                sectionIndex = sectionIndex + 1

            logger.info("Audit Form filled")







            for sindex, section in enumerate(audit_form):
                logger.info(sindex)
                print("sinex, section -> ", sindex, section)
                for ssIndex, ss in enumerate(section['subSection']):
                    logger.info(ssIndex)
                    for qindex, question in enumerate(ss['questions']):
                        logger.info(qindex)
                        score = 0
                        scored = 0
                        if 'answer' not in question:
                            question['answer'] = ''
                        if 'sentiment' not in question:
                            question['sentiment'] = ''
                        logger.info(1)
                        for option in question['answerOptions']:
                            logger.info(str(option))
                            logger.info(str(question['answer']))

                            if option['label'].lower() == question['answer'].lower():
                                scored = int(option['score'])


                            if (option['label'].lower() == 'yes') or (option['label'].lower() == 'good') or (option['label'].lower() == 'normal') or (option['label'].lower() == 'happiness'):
                                score = int(option['score'])
                        logger.info(2)
                        logger.info(str(question))
                        logger.info(question['sid'])
                        logger.info(question['ssid'])
                        logger.info(question['qid'])
                        logger.info(3)









                        dataBase2 = mysql.connector.connect(
                        host =os.environ.get('MYSQL_HOST'),
                        user =os.environ.get('MYSQL_USER'),
                        password =os.environ.get('MYSQL_PASSWORD'),
                        database = os.environ.get('MYSQL_DATABASE'),
                        connection_timeout= 86400000
                        )

                        cursorObjectInsert = dataBase2.cursor(buffered=True)
                        add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment, isCritical, applicableTo, processingTime) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                        add_result = (process_id,call_id,question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '', question["isCritical"], question["isApplicableTo"], question["processingTime"])


                        cursorObjectInsert.execute(add_column, add_result)
                        
                        dataBase2.commit()
                        cursorObjectInsert.close()

                        cursorObject = dataBase2.cursor(buffered=True)
                        logger.info("save done 1")
                        logger.info(str(call_id))
                        logger.info(str(question['sid']))
                        logger.info(str(question['qid']))
                        logger.info("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))

                        cursorObject.execute("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))
                    
                        savedQuestionResult = cursorObject.fetchone()


                        logger.info("saved done"+str(savedQuestionResult[0]))
                        for tindex, timing in enumerate(question['timings']):
                            add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")

                            add_result = (timing['startTime'],timing['endTime'],'',timing['referenceText'], savedQuestionResult[0])

                            cursorObject.execute(add_column, add_result)
                            
                            dataBase2.commit()
                            print("save done 2")
            print("---------")
            print("Update successful - auditFormFilled")
            print("---------")


                
























                
                
                        

            
            logger.info("LLM trigger status - started")



            dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject = dataBase2.cursor(buffered=True)














            




























            end_time_llm = datetime.now()
            start_time_sentiment = datetime.now()
            request_data_call_sentiment = { 'text':  trnascript_for_nlp}
            logger.info("predict_sentiments")
            logger.info(sentiment_endpoint+"/predict_sentiments")
            logger.info(str(request_data_call_sentiment))

            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "AuditDone"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)
            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s,updatedAt = %s
                                WHERE id = %s
                                """

            new_value = "AuditDone"
            condition_value = call_id
            cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            dataBase2.commit() 





                

                




































            if sub_process_type == "with_summary":
                start_time_cs = datetime.now()




                












































                end_time_cs = datetime.now()




























                
                end_time_qa = datetime.now()

            else:
                pass
            
        logger.info(5)


        end_time = datetime.now()
        logger.info(5)
        duration = (end_time - start_time).total_seconds()
        logger.info(6)
        duration_stt = (end_time_stt - start_time_stt).total_seconds()
        duration_stt = duration_stt - int(float(vad_processing_time))
        logger.info(7)
        duration_llm = (end_time_llm - start_time_llm).total_seconds()
        logger.info(8)
        if process_type == 'sttwithllmsummary':
            duration_cs = (end_time_cs - start_time_cs).total_seconds()
            logger.info(9)
            duration_qa = (end_time_qa - start_time_qa).total_seconds()
            logger.info(10)
        else:
            duration_cs = 0
            logger.info(9)
            duration_qa = 0
            logger.info(10)
        duration_sentiment = (end_time_sentiment - start_time_sentiment).total_seconds()
        logger.info(11)
        hours, remainder = divmod(duration, 3600)
        logger.info(12)
        minutes, seconds = divmod(remainder, 60)
        logger.info(13)
        duration_formatted = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        logger.info(14)
        logger.info(start_time)
        logger.info(end_time)
        logger.info(convert_seconds(int(float(audioDuration))))
        logger.info(duration_formatted)
        logger.info(convert_seconds(int(float(duration_stt))))
        logger.info(convert_seconds(int(float(duration_llm))))
        logger.info(convert_seconds(int(float(duration_cs))))
        logger.info(convert_seconds(int(float(duration_qa))))
        logger.info(convert_seconds(int(float(duration_sentiment))))
        if True:
            insert_log_query = """
                INSERT INTO auditNexDb.logs (startTime, end_time, audioDuration, processingTime, filename, timeLid, timeVad, timeStt, timeLlm, timeCs, timeQa, timeSentiment)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            cursorObject.execute(insert_log_query, (start_time, end_time, convert_seconds(int(float(audioDuration))), duration_formatted, request_data['file_name'], convert_seconds(int(float(lid_processing_time))), convert_seconds(int(float(vad_processing_time))), convert_seconds(int(float(duration_stt))), convert_seconds(int(float(duration_llm))), convert_seconds(int(float(duration_cs))), convert_seconds(int(float(duration_qa))), convert_seconds(int(float(duration_sentiment)))))
            dataBase2.commit()
            logger.info(15)
        else:
            update_query = """
                UPDATE logs
                SET start_time = %s, end_time = %s, audio_duration = %s, processing_time = %s, time_stt = %s, time_llm = %s, time_cs = %s, time_qa = %s, time_sentiment = %s
                WHERE filename = %s
                """
            cursorObject.execute(update_query, (start_time, end_time, convert_seconds(int(float(stt_json_response[0]))), duration_formatted, convert_seconds(int(float(duration_stt))), convert_seconds(int(float(duration_llm))), convert_seconds(int(float(duration_cs))), convert_seconds(int(float(duration_qa))), convert_seconds(int(float(duration_sentiment))), request_data['file_name']))
            dataBase2.commit()
            logger.info("---------")
            logger.info("Update successful processes")    

        if process_type != 'sequential':

            logger.info(16)
            request_data_wb = {"callId": call_id, "status": "Complete"}
            logger.info(17)
            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json=request_data_wb, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)

            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s,updatedAt = %s
                                WHERE id = %s
                                """

            new_value = "Complete"
            condition_value = call_id
            cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
            dataBase2.commit() 
        logger.info(18)


        logger.info("Webhook triggered")
        
        "to delete the audio and chunks from respective locations"
        audio_file_path = storage_path+file_name
        if os.path.exists(audio_file_path):
            try:
                # os.remove(audio_file_path)
                print(f"File {audio_file_path} has been deleted successfully.")
            except OSError as e:
                print(f"Error: {e.strerror} - {e.filename}")
        else:
            print(f"The file {audio_file_path} does not exist.")


        # remove_all_contents('/docker_volume/chunks')
        # results = client.stop_monitoring()
        # logger.info(str(results))
        # sync_response = client.sync_data(
        # LICENSE_TOKEN,
        # INSTANCE_ID,0,0,0,0,
        # duration_in_minutes,'',
        # results
        # )
        return {'status': 'Data saved successfully'}
        


    
    elif response.status_code == 400:
        dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
        delete_query = "DELETE FROM auditNexDb.call WHERE callId = '"+str(call_id)+"';"
        cursorObject = dataBase2.cursor(buffered=True)
        cursorObject.execute(delete_query)
        dataBase2.commit()
        print(f"call id {call_id} deleted")
        logger.info("Data: Language unsupported")
        return False, "Data: Language unsupported"

    else:
        logger.info("API: Interface Something went wrong:")
        return False, "API: Interface Something went wrong:"

def reaudit_file(request_data):
    call_id = request_data["call_id"]
    audit_form_id = request_data["audit_form_id"]
    process_id = request_data["process_id"]
    audio_language = request_data["audio_language"]
    trnascript_for_nlp = request_data["trnascript_for_nlp"]
    nlp_endpoint = os.environ.get('NLP_API')
    auditnex_endpoint = os.environ.get('AUDITNEX_API')
    log_file_path = '/docker_volume/logs/'+request_data['file_name'].replace('.mp3','.txt').replace('.wav','.txt')
    header = {'Content-Type': "application/json"}
    
    logger.info("1")
    dataBase2 = mysql.connector.connect(
    host =os.environ.get('MYSQL_HOST'),
    user =os.environ.get('MYSQL_USER'),
    password =os.environ.get('MYSQL_PASSWORD'),
    database = os.environ.get('MYSQL_DATABASE'),
    connection_timeout= 86400000
    )
    
    cursorObject = dataBase2.cursor(buffered=True)
    cursorObject.execute("SELECT * FROM auditForm where id = "+str(audit_form_id))
    
    auditformresult = cursorObject.fetchone()

    
    cursorObject.execute("SELECT afsqm.*, s.*, q.* FROM auditFormSectionQuestionMapping afsqm INNER JOIN section s ON afsqm.sectionId = s.id INNER JOIN question q ON afsqm.questionId = q.id WHERE afsqm.auditFormId = "+ str(audit_form_id) +" AND s.id IN ( SELECT sectionId FROM auditFormSectionQuestionMapping WHERE auditFormId = "+ str(audit_form_id) +")")

    all_form_data = cursorObject.fetchall()
    

    audit_form = []
    audit_formIndex = -1
    section_list = []
    for row in all_form_data:
        

        answerOptions = []
        cursorObject.execute('SELECT * From answerOption ao  WHERE questionId  = '+str(row[4]))
        all_option_data = cursorObject.fetchall()
        logger.info(row[0])

        for row2 in all_option_data:
            answerOptions.append({'label':row2[3],'score': row2[4]})

        if row[2] not in section_list:

                section_list.append(row[2])

                section = {'section': row[7], 'subSection':[{'ssid':row[3],'questions': []}]}

                if audio_language == "hi":
                    section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': []})
                else:
                    section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': []})
                audit_form.append(section)
                audit_formIndex = audit_formIndex + 1
        else:

            index = section_list.index(row[2])


            subsFound = False
            for section in audit_form:
                for subs in section['subSection']:
                    if subs['ssid'] == row[3]:
                        subsFound = True
                        if audio_language == "hi":
                            audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': []})
                        else:
                            audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': []})

            if subsFound == False:
                audit_form[audit_formIndex]['subSection'].append({'ssid':row[3],'questions': []})
                if audio_language == "hi":
                    audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[20],'answerOptions': answerOptions,'timings': []})
                else:
                    audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[15],'answerType': row[17],'attribute': row[18],'intents': row[21],'answerOptions': answerOptions,'timings': []})
            
                
    logger.info(audit_form)
    log_message = "stt response: " + str(trnascript_for_nlp)
    append_log(log_message,log_file_path)

    log_message = "audit form: " + str(audit_form)
    append_log(log_message,log_file_path)
    try:
        requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": call_id, "status": "Auditing"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s,updatedAt = %s
                        WHERE id = %s
                        """

    new_value = "Auditing"
    condition_value = call_id
    cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
    dataBase2.commit()    
    audit_score = 0
    sectionIndex = 0
    for section in audit_form:
        if section['section'] != 'Call Category':
            questionIndex = 0
            for ssIndex, ss in enumerate(section['subSection']):
                for qIndex, question in enumerate(ss['questions']):



                    request_data_nlp = {
                        "text": trnascript_for_nlp,
                        "prompts": [
                            {
                                "entity": question['attribute'],
                                "prompts": [question['intents']],
                                "type": "multiple"
                            }
                        ],
                        "additional_params": {}
                    }

                    logger.info("LLM trigger status - request")
                    logger.info(str(question))
                    logger.info(str(request_data_nlp))
                    log_message = "Sequence: " +str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex)
                    append_log(log_message,log_file_path)
                    log_message = "question: " + str(question)
                    append_log(log_message,log_file_path)
                    log_message = "request data: " + str(request_data_nlp)
                    append_log(log_message,log_file_path)







                    
                    print("entity -> ",request_data_nlp["prompts"][0]["entity"])
                    print("intent -> ", request_data_nlp["prompts"][0]["prompts"][0])

                    if request_data_nlp["prompts"][0]["prompts"][0] == "NA":
                        audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "NA"
                        for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                            if ans['label'] == 'NA':
                                audit_score = audit_score + int(str(ans['score']))
                    
                    



                    
                    elif (request_data_nlp["prompts"][0]["prompts"][0] == "rateOfSpeech") or (request_data_nlp["prompts"][0]["prompts"][0] == "tonalAnalysis"):
                        print("speech parameter with intent detected")
                        cursorObject.execute("SELECT "+ str(request_data_nlp["prompts"][0]["prompts"][0]) +" FROM auditNexDb.call where callId = "+str(call_id)+ ";")

                        speechParameterResult = cursorObject.fetchone()
                        print("speech parameter intent result -> ", type(speechParameterResult[0]), speechParameterResult[0])
                        if not speechParameterResult:
                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = "NA"
                            for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                if ans['label'] == 'NA':
                                    audit_score = audit_score + int(str(ans['score']))
                        
                        elif (speechParameterResult[0].lower() == "good") or (speechParameterResult[0].lower() == "normal") or (speechParameterResult[0].lower() == "na"):
                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = speechParameterResult[0].upper()
                            for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                if ans['label'] == 'YES':
                                    audit_score = audit_score + int(str(ans['score']))
                        
                        elif (speechParameterResult[0].lower() == "fast") or (speechParameterResult[0].lower() == "slow") or (speechParameterResult[0].lower() == "monotonic/robotic"):
                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = speechParameterResult[0].upper()

                    else:
                        logger.info(str(request_data_nlp))
                        nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                        nlp_response = nlp_raw_response.json()
                        logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))

                        log_message = "response data: " + str(nlp_response)
                        append_log(log_message,log_file_path)
                        print(nlp_response)
                        if 'data' in nlp_response:
                            if 'derived_value' in nlp_response['data']:
                                result = nlp_response['data']['derived_value'][0]['result']

                                if len(result) > 0 and result.lower() != 'no':

                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'

                                    for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                        if ans['label'] == 'YES':
                                            audit_score = audit_score + int(str(ans['score']))
                                else:

                                    audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'
                                if 'reference' in nlp_response['data']['derived_value'][0]:
                                    reference_text = ''
                                    for index, obj in enumerate(nlp_response['data']['derived_value'][0]['reference']):
                                        if obj['text'] == 'Model timed out':
                                            obj['text'] = 'NA'
                                        reference_text = reference_text + obj['text'] + ' '
                                        timing = { "startTime": obj['start_time'],
                                                    "endTime": obj['end_time'],
                                                    "referenceText": obj['text']
                                                }
                                        audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['timings'].append(timing)

                                    if len(reference_text) > 0:
                                        print('1')
                                        request_data_call_sentiment = { 'text':  reference_text}


                                        

                                        

                                            
















                                    
                    questionIndex = questionIndex + 1
















        sectionIndex = sectionIndex + 1

    logger.info("Audit Form filled")





    for sindex, section in enumerate(audit_form):
        logger.info(sindex)
        print("sinex, section -> ", sindex, section)
        for ssIndex, ss in enumerate(section['subSection']):
            logger.info(ssIndex)
            for qindex, question in enumerate(ss['questions']):
                logger.info(qindex)
                score = 0
                scored = 0
                if 'answer' not in question:
                    question['answer'] = ''
                if 'sentiment' not in question:
                    question['sentiment'] = ''
                logger.info(1)
                for option in question['answerOptions']:
                    print(option['label'].lower(),question['answer'].lower())
                    if option['label'].lower() == question['answer'].lower():
                        scored = int(option['score'])
                    elif (question["answer"].lower() == "good") or (question["answer"].lower() == "normal"):
                        scored = int(option['score'])
                    if option['label'].lower() == 'yes':
                        score = int(option['score'])
                logger.info(2)
                logger.info(str(question))
                logger.info(question['sid'])
                logger.info(question['ssid'])
                logger.info(question['qid'])
                logger.info(3)









                dataBase2 = mysql.connector.connect(
                host =os.environ.get('MYSQL_HOST'),
                user =os.environ.get('MYSQL_USER'),
                password =os.environ.get('MYSQL_PASSWORD'),
                database = os.environ.get('MYSQL_DATABASE'),
                connection_timeout= 86400000
                )

                cursorObjectInsert = dataBase2.cursor(buffered=True)
                add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                add_result = (process_id,call_id,question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '')



                cursorObjectInsert.execute(add_column, add_result)
                
                dataBase2.commit()
                cursorObjectInsert.close()

                cursorObject = dataBase2.cursor(buffered=True)
                logger.info("save done 1")
                logger.info(str(call_id))
                logger.info(str(question['sid']))
                logger.info(str(question['qid']))
                logger.info("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))

                cursorObject.execute("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(call_id)+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))
            
                savedQuestionResult = cursorObject.fetchone()


                logger.info("saved done"+str(savedQuestionResult[0]))
                for tindex, timing in enumerate(question['timings']):
                    add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")

                    add_result = (timing['startTime'],timing['endTime'],'',timing['referenceText'], savedQuestionResult[0])

                    cursorObject.execute(add_column, add_result)
                    
                    dataBase2.commit()
                    print("save done 2")
    print("---------")
    print("Update successful - auditFormFilled")
    print("---------")
    logger.info("LLM trigger status - started")



    dataBase2 = mysql.connector.connect(
    host =os.environ.get('MYSQL_HOST'),
    user =os.environ.get('MYSQL_USER'),
    password =os.environ.get('MYSQL_PASSWORD'),
    database = os.environ.get('MYSQL_DATABASE'),
    connection_timeout= 86400000
    )
    cursorObject = dataBase2.cursor(buffered=True)














    




























    end_time_llm = datetime.now()
    start_time_sentiment = datetime.now()





    try:
        requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": call_id, "status": "AuditDone"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)
    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s,updatedAt = %s
                        WHERE id = %s
                        """

    new_value = "Complete"
    condition_value = call_id
    cursorObject.execute(update_query, (new_value,datetime.now().replace(microsecond=0),condition_value))
    dataBase2.commit() 





        

        





































def translate(request_data):

    try:
        header = {'Content-Type': "application/json"}
        translate_endpoint = os.environ.get('NLP_TRANSLATE_API') or "http://translate:7060"

        db_config = {
            "host": os.environ.get('MYSQL_HOST'),
            "user":os.environ.get('MYSQL_USER'),
            "password":os.environ.get('MYSQL_PASSWORD'),
            "database": os.environ.get('MYSQL_DATABASE'),
            "connection_timeout": 86400000
        }

        file_name = request_data["fileName"]
        language_id = request_data["languageId"]
        input_language_id = 3
        request_type = request_data["type"]
        file_name = (file_name, )
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        sql_query = "SELECT id, translationStatus, transliterationStatus, languageId FROM auditNexDb.call where `audioName` = %s"

        cursor.execute(sql_query, file_name)
        callId = cursor.fetchone()
        logger.info(str(callId["id"]))
        translationStatus = callId["translationStatus"]
        transliterationStatus = callId["transliterationStatus"]
        input_language_id = callId["languageId"]
        logger.info(str(callId["translationStatus"]))
        logger.info(str(callId["transliterationStatus"]))
        nlp_response = {}


        if request_type == 'translation' and translationStatus == 'In Progress':
            logger.info("Inside")
            update_query = """
                        UPDATE auditNexDb.call
                        SET translationStatus = %s
                        WHERE id = %s
                        """

            new_value = "In Progress"
            condition_value = str(callId["id"])
            cursorObject.execute(update_query, (new_value,condition_value))
            dataBase2.commit() 
            logger.info("Inside1")
            transcript_query = "SELECT startTime, endTime, speaker, text from auditNexDb.transcript WHERE languageId = "+str(input_language_id)+" and callId = "+ str(callId["id"])
            cursor.execute(transcript_query)
            transcript_output = cursor.fetchall()

            logger.info("Inside2")
            transcript_nlp = ""
            for item in transcript_output:
                transcript_nlp += " start_time: "+str(item["startTime"]) + " "+ item["speaker"] + ": " + item["text"] + " end_time: "+ str(item["endTime"])+"\\n"

            logger.info(str(transcript_nlp))
            request_data_nlp = {
                "text": transcript_nlp,
                "service": request_type,
                "language": language_id,
                "languageId": language_id,
                "callId":  str(callId["id"]),
            }
            logger.info(translate_endpoint)
            nlp_raw_response = requests.post(translate_endpoint+"/translate", headers=header, json=request_data_nlp, timeout=150)
            nlp_response = nlp_raw_response.json()

            logger.info(str(nlp_response))
            delete_query = "DELETE FROM auditNexDb.transcript WHERE callId = '"+str(callId["id"])+"' and languageId = '"+str(language_id)+"';"
            cursorObject.execute(delete_query)
            dataBase2.commit()
            for t in nlp_response:
                add_column = ("INSERT INTO transcript (callId, languageId, startTime, endTime, speaker, text, rateOfSpeech, confidence)"
                "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")

            
                add_result = (t['callId'],int(str(t['languageId'])), float(str(t['startTime'])),float(str(t['endTime'])),t['speaker'],t['text'],t['rateOfSpeech'],t['confidence'])
                cursorObject.execute(add_column, add_result)
                dataBase2.commit()
            update_query = """
                        UPDATE auditNexDb.call
                        SET translationStatus = %s
                        WHERE id = %s
                        """

            new_value = "Complete"
            condition_value = str(callId["id"])
            cursorObject.execute(update_query, (new_value,condition_value))
            dataBase2.commit() 




        if request_type == 'transliteration' and transliterationStatus == 'In Progress':
            update_query = """
                        UPDATE auditNexDb.call
                        SET transliterationStatus = %s
                        WHERE id = %s
                        """

            new_value = "In Progress"
            condition_value = str(callId["id"])
            cursorObject.execute(update_query, (new_value,condition_value))
            dataBase2.commit() 
            transcript_query = "SELECT startTime, endTime, speaker, text from auditNexDb.transcript WHERE languageId = "+str(input_language_id)+" and callId = "+ str(callId["id"])
            cursor.execute(transcript_query)
            transcript_output = cursor.fetchall()

            transcript_nlp = ""
            for item in transcript_output:
                transcript_nlp += " start_time: "+str(item["startTime"]) + " "+ item["speaker"] + ": " + item["text"] + " end_time: "+ str(item["endTime"])+"\\n"

            logger.info(str(transcript_nlp))
            request_data_nlp = {
                "text": transcript_nlp,
                "service": request_type,
                "language": language_id,
                "languageId": language_id,
                "callId":  str(callId["id"]),
            }
            
            nlp_raw_response = requests.post(translate_endpoint+"/translate", headers=header, json=request_data_nlp, timeout=150)
            nlp_response = nlp_raw_response.json()
            delete_query = "DELETE FROM auditNexDb.transcript WHERE callId = '"+str(callId["id"])+"' and languageId = '"+str(language_id)+"';"
            cursorObject.execute(delete_query)
            dataBase2.commit()
            for t in nlp_response:
                add_column = ("INSERT INTO transcript (callId, languageId, startTime, endTime, speaker, text, rateOfSpeech, confidence)"
                "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)")

            
                add_result = (t['callId'],int(t['languageId']), float(t['startTime']),float(t['endTime']),t['speaker'],t['text'],t['rateOfSpeech'],t['confidence'])
                cursorObject.execute(add_column, add_result)
                dataBase2.commit()
            update_query = """
                        UPDATE auditNexDb.call
                        SET transliterationStatus = %s
                        WHERE id = %s
                        """

            new_value = "Complete"
            condition_value = str(callId["id"])
            cursorObject.execute(update_query, (new_value,condition_value))
            dataBase2.commit() 


        cursor.close()
        conn.close()

        return nlp_response
    
    except Exception as e:
        print("error in translation", e)
        return {'status': 'Error', 'message': 'Error in '+str(request_type)}

def insert_into_db_step_1_v5(request_data):
    header = {'Content-Type': "application/json"}
    url = os.environ.get('STT_URL')
    storage_path = os.environ.get('STORAGE_PATH')
    nlp_endpoint = os.environ.get('NLP_API')
    sentiment_endpoint = os.environ.get('SENTIMENT_API')
    auditnex_endpoint = os.environ.get('AUDITNEX_API')
    audio_endpoint = os.environ.get('AUDIO_ENDPOINT')
    callback_url_new = os.environ.get('CALLBACK_URL')
    user_id = 0
    myresult = []
    call_id = 0
    process_id = 1
    audit_form_id = 1
    file_name = request_data['file_name']
    call_type = 'Call'
    metaData = {}
    logger.info('insert_into_db_step_1'+str(request_data))
    if 'languageId' in request_data:
        logger.info('languageId '+str(request_data['languageId']))
        call_languageId = request_data['languageId']
        cursorObject.execute("SELECT * FROM auditNexDb.language where id = "+ call_languageId)
        languageResult = cursorObject.fetchone()
        metaData['language'] = languageResult[1]
    if 'type' in request_data:
        call_type = request_data['type']
    if 'process_id' in request_data:
        process_id = request_data['process_id']
    if 'language' in request_data:
        metaData['language'] = request_data['language']
    if 'call_id' in request_data:
        metaData['call_id'] = request_data['call_id']
    if 'audio_uri' in request_data:
        metaData['audioUrl'] = request_data["audio_uri"]
    if 'reAudit' in request_data:
        metaData['reAudit'] = request_data['reAudit']
    if 'user_id' in request_data:
        user_id = request_data['user_id']
    logger.info('metaData '+str(metaData))
    try:
        if 'reAudit' not in request_data:
            if 'multiple' in request_data and request_data['index'] == 0:
                for file_to_insert in request_data['files']:
                    logger.info('file_to_insert '+str(file_to_insert))
                    if "audioUrl" in file_to_insert:
                        try:
                            if 'call_id' in file_to_insert:
                                metaData['call_id'] = file_to_insert['call_id']
                            metaData['audioUrl'] = file_to_insert["audioUrl"]
                            response_1 = requests.get(file_to_insert["audioUrl"])
                            filename = os.path.basename(file_to_insert["audioUrl"])
                            # logger.info(storage_path+filename)
                            dir_name = os.path.dirname(storage_path+filename)
                            if not os.path.exists(dir_name):
                                os.makedirs(dir_name)
                            with open(storage_path+filename, 'wb') as file:
                                    file.write(response_1.content)
                                    file.close()
                                    logger.info('done writing')
                        except Exception as e:
                            logger.info("error")
                            logger.info(str(e))
                    try:
                            
                            delete_query = "DELETE FROM auditNexDb.call WHERE audioName = '"+file_to_insert['fileName']+"';"
                            
                            cursorObject.execute(delete_query)
                            dataBase2.commit()
                            logger.info("Insert call 1")
                            if user_id == 0:
                                logger.info("Insert call 1-1")
                                add_column = ("INSERT INTO auditNexDb.call (processId, auditFormId, categoryMappingId, audioUrl, audioName, status,type,metaData,languageId) VALUES (%s, %s,%s,%s, %s,%s, %s, %s, %s)")
                                
                                audio_url = audio_endpoint+"/"+file_to_insert['fileName']
                                
                                add_result = (process_id,int(audit_form_id),1,audio_url,file_to_insert['fileName'],'Pending',call_type,json.dumps(metaData),int(call_languageId))
                            else:
                                logger.info("Insert call 1-2")
                                add_column = ("INSERT INTO auditNexDb.call (processId, auditFormId, categoryMappingId, userId, audioUrl, audioName, status, type,metaData,languageId) VALUES (%s, %s,%s,%s, %s, %s, %s, %s, %s, %s)")
                                
                                audio_url = audio_endpoint+"/"+file_to_insert['fileName']
                                
                                add_result = (process_id,int(audit_form_id),1,user_id,audio_url,file_to_insert['fileName'],'Pending', call_type,json.dumps(metaData),call_languageId)
                                
                            logger.info(1)
                            cursorObject.execute(add_column, add_result)
                            logger.info(1)
                            dataBase2.commit()
                            logger.info("Insert call Done ")
                            print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_to_insert['fileName']) + "'")
                            cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_to_insert['fileName']) + "'")
                            
                            savedCallResult = cursorObject.fetchone()
                            logger.info(savedCallResult[0])
                            metaDataOld = json.loads(savedCallResult[25])
                            metaDataOld['call_id'] = savedCallResult[0]
                            update_query = """
                                                UPDATE auditNexDb.call
                                                SET status = %s,callId = %s, metaData = %s
                                                WHERE id = %s
                                                """

                            new_value = "Pending"
                            new_value2 = savedCallResult[0]
                            condition_value = savedCallResult[0]    
                            cursorObject.execute(update_query, (new_value,new_value2,json.dumps(metaDataOld),condition_value))
                            dataBase2.commit()

                            try:
                                    requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Pending"}, timeout=10)
                            except Exception as e:
                                print(e)
                                logger.error(e)
                    except Exception as e:
                                logger.error(str(e))
                                print(e)
                                return False, "API: Interface Something went wrong:"  + str(e)
            elif 'multiple' in request_data and request_data['index'] != 0:
                logger.info('Another file in multiple')
            else:
                try:
                            
                            delete_query = "DELETE FROM auditNexDb.call WHERE audioName = '"+request_data['file_name']+"';"
                            
                            cursorObject.execute(delete_query)
                            dataBase2.commit()
                            logger.info("Insert call 2")
                            add_column = ("INSERT INTO auditNexDb.call (processId, auditFormId, categoryMappingId, audioUrl, audioName, status, type,metaData,languageId) VALUES (%s, %s,%s, %s, %s, %s, %s, %s, %s)")
                            
                            audio_url = audio_endpoint+"/"+request_data['file_name']
                            
                            add_result = (process_id,int(audit_form_id),1,audio_url,file_name,'Pending', call_type,json.dumps(metaData),call_languageId)
                            logger.info(1)
                            cursorObject.execute(add_column, add_result)
                            logger.info(1)
                            dataBase2.commit()
                            logger.info("Insert call Done ")
                            print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
                            cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
                            
                            savedCallResult = cursorObject.fetchone()
                            logger.info(savedCallResult[0])
                            metaDataOld = json.loads(savedCallResult[25])
                            metaDataOld['call_id'] = savedCallResult[0]
                            update_query = """
                                                UPDATE auditNexDb.call
                                                SET status = %s,callId = %s, metaData = %s
                                                WHERE id = %s
                                                """

                            new_value = "Pending"
                            new_value2 = savedCallResult[0]
                            condition_value = savedCallResult[0]    
                            cursorObject.execute(update_query, (new_value,new_value2,json.dumps(metaDataOld),condition_value))
                            dataBase2.commit()

                            try:
                                    requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Pending"}, timeout=10)
                            except Exception as e:
                                print(e)
                                logger.error(e)
                except Exception as e:
                            logger.error(str(e))
                            print(e)
                            return False, "API: Interface Something went wrong:"  + str(e)
        else:
            print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
            cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
            
            savedCallResult = cursorObject.fetchone()
            logger.info(savedCallResult[0])
            metaDataOld = json.loads(savedCallResult[25])
            metaDataOld['call_id'] = metaData['call_id']
            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s, metaData = %s
                                WHERE id = %s
                                """

            new_value = "Pending"
            condition_value = savedCallResult[0]    
            cursorObject.execute(update_query, (new_value,json.dumps(metaDataOld),condition_value))
            dataBase2.commit()

            try:
                    requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Pending"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)
    except Exception as e:
        logger.error(str(e))
        print(e)
        return False, "API: Interface Something went wrong:"  + str(e)
    return True
            
def recognize_speech_file_v5(request_data, callback_url):
    logger.info("api wrapper recognize_speech_file_v5 with request data: " + str(request_data))
    
    process_id = 1
    audit_form_id = 1
    start_time = datetime.now()
    start_time_stt = datetime.now()
    end_time_stt = datetime.now()
    start_time_llm = datetime.now()
    end_time_llm = datetime.now()
    start_time_qa = datetime.now()
    end_time_qa = datetime.now()
    start_time_cs = datetime.now()
    end_time_cs = datetime.now()
    start_time_sentiment = datetime.now()
    end_time_sentiment = datetime.now()
    savedCallResult = None
    header = {'Content-Type': "application/json"}
    url = os.environ.get('STT_URL')
    storage_path = os.environ.get('STORAGE_PATH')
    nlp_endpoint = os.environ.get('NLP_API')
    sentiment_endpoint = os.environ.get('SENTIMENT_API')
    auditnex_endpoint = os.environ.get('AUDITNEX_API')
    audio_endpoint = os.environ.get('AUDIO_ENDPOINT')
    callback_url_new = os.environ.get('CALLBACK_URL')
    audioDuration = 0.0
    myresult = []
    call_id = 0

    process_type = 'sttwithllm'

    instance_url = 'https://inspiration-speed-3598.my.salesforce.com'
    access_token = '00DGA000009KgaK!ARsAQPOVRBj8uTmPIZyCIFQrzzGlkBBbOKGtw4ap8rQb5CtcbQmARXUJqEbN9Ed.OyG9N0xjOn6SbzDCIoPZcObzF1Ctu4gb'    
        
    new_lead_data = {
    'FirstName': 'John',
    'LastName': 'Doe',
    'Company': 'Example Company',
    'Phone': '123-456-7890',
    'Email': 'johndoe@example.com'
    }

    sfdc_url = f'{instance_url}/services/data/v61.0/sobjects/Lead/'

    sfdc_headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
    }

    log_file_path = '/docker_volume/logs/'+request_data['file_name'].replace('.mp3','.txt').replace('.wav','.txt')
    file_name = request_data['file_name']
    try:
        if 'process_id' in request_data:
            logger.info("1")
            dataBase2 = mysql.connector.connect(
            host =os.environ.get('MYSQL_HOST'),
            user =os.environ.get('MYSQL_USER'),
            password =os.environ.get('MYSQL_PASSWORD'),
            database = os.environ.get('MYSQL_DATABASE'),
            connection_timeout= 86400000
            )
            cursorObject = dataBase2.cursor(buffered=True)
            # logger.info("SELECT * FROM process where id = "+str(request_data['process_id']))
            cursorObject.execute("SELECT * FROM process where id = "+str(request_data['process_id']))
            # logger.info("2")
            processResult = cursorObject.fetchone()
            # logger.info("3")
            process_id = int(processResult[0])
            # logger.info("4")
            audit_form_id = int(processResult[6])
            process_type = processResult[9]
            # logger.info("5")
    except Exception as e:
            logger.error(str(e))
            print(e)
            return False, "API: Interface Something went wrong:"  + str(e)
    except Exception as e:
                logger.error(str(e))
                print(e)
                return False, "API: Interface Something went wrong:"  + str(e)
    
    
             
    print("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
    cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "' and status = 'Pending'")
    
    savedCallResult = cursorObject.fetchone()
    if not savedCallResult:
         return False, "API: Interface Something went wrong:"  + str(e)
    logger.info(savedCallResult[0])
    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s,callId = %s
                        WHERE id = %s
                        """

    new_value = "Pending"
    new_value2 = savedCallResult[0]   
    condition_value = savedCallResult[0]    
    cursorObject.execute(update_query, (new_value,new_value2,condition_value))
    dataBase2.commit()       

    logger.info("getting metadata")    
    metaData = json.loads(savedCallResult[25])
    logger.info(metaData)
    
    if 'reAudit' in metaData:
        request_data['call_id'] = metaData['call_id']
        request_data['reAudit'] = metaData['reAudit']
        try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": request_data['call_id'], "status": "Pending"}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
    try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "InProgress"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s
                        WHERE id = %s
                        """

    new_value = "InProgress"
    condition_value = savedCallResult[0]
    cursorObject.execute(update_query, (new_value,condition_value))
    dataBase2.commit()
        
    dataBase2 = mysql.connector.connect(
    host =os.environ.get('MYSQL_HOST'),
    user =os.environ.get('MYSQL_USER'),
    password =os.environ.get('MYSQL_PASSWORD'),
    database = os.environ.get('MYSQL_DATABASE'),
    connection_timeout= 86400000
    )
    cursorObject = dataBase2.cursor(buffered=True)
    
    if os.path.exists(log_file_path):
        # Delete the file
        os.remove(log_file_path)
        print(f"File {log_file_path} has been deleted.")
    else:
        print(f"The file {log_file_path} does not exist.")
    log_message = "api wrapper recognize_speech_file_v2 with request data: " + str(request_data)
    append_log(log_message,log_file_path)
    
    if 'call_id' in request_data and request_data['call_id'] != 0:
        call_id = request_data['call_id']
    else:
        call_id = savedCallResult[0]
    stt_request_data = {
        'file_name': '',
        'no_of_speakers': 2
    }
    if "no_of_speakers" in request_data:
        stt_request_data['no_of_speakers'] = request_data['no_of_speakers']
    if "language" in request_data:
        if request_data['language'] == 'en-AU':
            url = os.environ.get('STT_URL_AUS')
    
    if "file_name" in request_data:
        stt_request_data['file_name'] = request_data['file_name']
    # if "audio_uri" in request_data:
    #     try:
    #         response_1 = requests.get(request_data["audio_uri"])
    #         filename = os.path.basename(request_data["audio_uri"])
    #         print(storage_path+filename)
    #         dir_name = os.path.dirname(storage_path+filename)
    #         if not os.path.exists(dir_name):
    #             os.makedirs(dir_name)
    #         with open(storage_path+filename, 'wb') as file:
    #                 file.write(response_1.content)
    #                 file.close()
    #                 print('done writing')
    #                 stt_request_data['file_name'] = filename
            

        

    #     except Exception as e:
    #         print("error")
    #         logger.info(e)
    
    start_time_stt = datetime.now()        
    logger.info("STT trigger status - started" )
    print(url, stt_request_data)                                
    trnascript_for_nlp = ''
    try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Transcription"}, timeout=10)
    except Exception as e:
        print(e)
        logger.error(e)

    update_query = """
                        UPDATE auditNexDb.call
                        SET status = %s
                        WHERE id = %s
                        """

    new_value = "Transcription"
    condition_value = savedCallResult[0]
    cursorObject.execute(update_query, (new_value,condition_value))
    dataBase2.commit()
    language = 'en'
    
    if 'language' in metaData:
         language = metaData['language']
    
    stt_request_data['language'] = language
    stt_request_data['audio_language'] = language

    if language == 'hi':
        stt_request_data['file_name'] = metaData['audioUrl']
        process_type = 'stt'
    logger.info('stt_request_data'+str(stt_request_data))
    response = requests.post(url, headers=header, json=stt_request_data)
    logger.info("STT trigger status - ended ")
    all_chunks = []
    
    if response.status_code == 200:
        stt_json_response = response.json()
        logger.info('stt_json_response'+str(stt_json_response))
        confidence = 0.0
        cnter = 0.0
        all_chunks = stt_json_response[1]
        for t in stt_json_response[1]:
            t['confidence'] = 0.0
            if 'confidence' in t and t['confidence'] != 'nan' and t['confidence'] != 'NA':
                confidence = confidence + float(t['confidence'])
                cnter = cnter + 1
        confidence = confidence / cnter
        confidence = confidence * 100
        confidence = round(confidence, 2)
        if "enable_speaker_detection" in request_data and request_data['enable_speaker_detection'] == True:
            for t in stt_json_response[1]:
                if str(t['speaker']) == '0':
                        t['speaker'] = '1'
                elif str(t['speaker']) ==  '1':
                        t['speaker'] = '2'
                trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+t['start_time'] + ' Speaker '+t['speaker'] + ':' + ' ' + t['transcript'] + ' ' + 'end_time: '+t['end_time'] + '\n'
        else:
            for t in stt_json_response[1]:
                trnascript_for_nlp = trnascript_for_nlp + ' ' + t['transcript'] + '.'
        
        # NLP Email 

        nlp_data = []
        
        # license spring 

        # if "clientName" in request_data:
        #     cursorObject.execute("SELECT * FROM auditNexDb.clientConfig where clientName = '"+request_data['clientName'] + "'")
        #     savedClientResult = cursorObject.fetchone()
        #     lic_result = licspring.add_consumption(stt_json_response[0],savedClientResult[1],savedClientResult[2],savedClientResult[3])
        #     if lic_result == False:
        #         print('licence expired')

        final_response = { "status": "success", "transcript":  trnascript_for_nlp, "overall_confidence_level": confidence, "audio_file_duration": stt_json_response[0],"processing_time":stt_json_response[2]}
        logger.info(stt_json_response)
        if "call_id" in request_data and request_data['call_id'] != 0:
            final_response['call_id'] = call_id
        else:
            call_id = savedCallResult[0]
        if "file_name" in stt_request_data:
            final_response['file_name'] = stt_request_data['file_name']
        header = {'Content-Type': "application/json", 'Authorization': "c2Jpei1zbWFydC1zcGVlY2gtMjAyMQ=="}
        file_name = request_data['file_name']
        input_json = stt_json_response
        total_confidence = 0
        
        current_datetime = datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
        trnascript_for_nlp = ''
        # logger.info("1")
        try:
            logger.info("LLM trigger status - started")
            # if len(myresult) == 0:
            
            # logger.info("1")
            for t in stt_json_response[1]:
                # logger.info(str(t))
                if str(t['speaker']) == '0':
                    t['speaker'] = '1'
                elif str(t['speaker']) == '1':
                    t['speaker'] = '2'
                # t['transcript'] = t['transcript'].replace('Speaker 0','IC').replace('Speaker 1','Caller')                    
                trnascript_for_nlp = trnascript_for_nlp + ' ' + 'start_time: '+t['start_time'] + ' Speaker '+t['speaker'] + ':' + ' ' + t['transcript'] + ' ' + 'end_time: '+t['end_time'] + '\n'
            output_json = {
                "callId": int(call_id),
                "callTime": ''+formatted_datetime,
                "processingTime": convert_seconds(int(float(stt_json_response[2]))),
                "audioLength": convert_seconds(int(float(stt_json_response[0]))),
                "confidence": 100,
                "wordConfidence": 100,
                "text": trnascript_for_nlp,
                "chunk": []
            }

            #make sdfc call
            new_lead_data['Transcript__c'] = trnascript_for_nlp
            # response = requests.post(sfdc_url, headers=sfdc_headers, json=new_lead_data)


            # logger.info("2")
            for chunk in input_json[1]:
                # chunk['transcript'] = chunk['transcript'].replace('Speaker 0','IC').replace('Speaker 1','Caller')
                # if str(chunk['speaker']) == '0':
                #     chunk['speaker'] = '1'
                # elif str(chunk['speaker']) == '1':
                #     chunk['speaker'] = '2'
                new_chunk = {
                    "progress": "inprogress",
                    "processingTime": 6,  # Static value as example, modify if needed
                    "confidence": 0.0,
                    "active": "false",
                    "text": '<b>Speaker '+chunk['speaker']+':</b>'+chunk['transcript'],
                    "startTime": float(chunk['start_time']),
                    "endTime": float(chunk['end_time']),
                    "audioLength": float(chunk['end_time']) - float(chunk['start_time'])  # Placeholder, modify if individual audio length per chunk is available
                }
                chunk['confidence'] = 0.0
                if 'confidence' in chunk and chunk['confidence'] != 'nan' and chunk['confidence'] != 'NA':
                    new_chunk['confidence'] = round(float(chunk['confidence']) * 100, 2)
                    if math.isnan(new_chunk['confidence']): 
                        new_chunk['confidence'] = 85.23
                    
                total_confidence += new_chunk['confidence'] 
                output_json['chunk'].append(new_chunk)
            # logger.info("3")
            average_confidence = round(total_confidence / len(input_json[1]), 2)
            audit_score = 0
            if math.isnan(average_confidence): 
                output_json['confidence'] = 85.23
                output_json['wordConfidence'] = 85.23
            else:
                output_json['confidence'] = average_confidence
                output_json['wordConfidence'] = average_confidence 
            # logger.info("done confidence")
            
        
        except Exception as e:
                    logger.error(str(e))
                    print(e)
                    return False, "API: Interface Something went wrong:"  + str(e)
        
        
        try:
            logger.info("Insert call")
           
            
            audio_url = audio_endpoint+"/"+request_data['file_name']
            logger.info(audio_url)
            logger.info(process_id)
            logger.info(audit_form_id)
            logger.info(""+str(call_id))
            logger.info(""+str(final_response))
            

            update_query = """
            UPDATE auditNexDb.call
            SET audioDuration = %s, processingTime = %s, confidence = %s, wordConfidence = %s, status = %s
            WHERE id = %s
            """

            new_value1 = final_response['audio_file_duration']
            new_value2 = final_response['processing_time']
            new_value3 = output_json['confidence']
            new_value4 = output_json['wordConfidence']
            new_value5 = 'TranscriptDone'
            
            condition_value = savedCallResult[0]

            cursorObject.execute(update_query, (new_value1,new_value2,new_value3,new_value4,new_value5, condition_value))
            dataBase2.commit()
            logger.info("---------")
            logger.info("Update successful - Call")
            logger.info("---------")

            logger.info("Update call Done ")
            
        except Exception as e:
                    logger.error(str(e))
                    print(e)
                    return False, "API: Interface Something went wrong:"  + str(e)
        

        
    
        update_query = """
                            UPDATE auditNexDb.call
                            SET callId = %s
                            WHERE id = %s
                            """

        new_value = savedCallResult[0]
        condition_value = savedCallResult[0]

        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit()

        try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "TranscriptDone", "audioDuration": final_response['audio_file_duration']}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
        update_query = """
                            UPDATE auditNexDb.call
                            SET status = %s
                            WHERE id = %s
                            """

        new_value = "TranscriptDone"
        condition_value = savedCallResult[0]
        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit()    
        cursorObject.execute("SELECT * FROM auditNexDb.call where audioName = '"+str(file_name) + "'")
    
        savedCallResult = cursorObject.fetchone()
        audioDuration = str(final_response['audio_file_duration'])
        if True or 'reAudit' not in request_data:
            delete_query = "DELETE FROM auditNexDb.transcript WHERE callId = '"+str(savedCallResult[0])+"';"
            cursorObject.execute(delete_query)
            dataBase2.commit()
        for t in all_chunks:
            add_column = ("INSERT INTO transcript (callId, startTime, endTime, speaker, text, rateOfSpeech, confidence)"
            "VALUES(%s, %s, %s, %s, %s, %s, %s)")

            add_result = (savedCallResult[0],float(t['start_time']),float(t['end_time']),'Speaker '+t['speaker'],t['transcript'],6,round(float(t['confidence']) * 100, 2))

            cursorObject.execute(add_column, add_result)
            dataBase2.commit()

        logger.info("Insert transcripts Done ")
        end_time_stt = datetime.now()
        start_time_llm = datetime.now()
        logger.info(process_type)
        if process_type == 'sttwithllm':

            cursorObject.execute("SELECT * FROM auditForm where id = "+str(audit_form_id))
            
            auditformresult = cursorObject.fetchone()

            
            cursorObject.execute("SELECT afsqm.*, s.*, q.* FROM auditFormSectionQuestionMapping afsqm INNER JOIN section s ON afsqm.sectionId = s.id INNER JOIN question q ON afsqm.questionId = q.id WHERE afsqm.auditFormId = "+ str(audit_form_id) +" AND s.id IN ( SELECT sectionId FROM auditFormSectionQuestionMapping WHERE auditFormId = "+ str(audit_form_id) +")")
            # logger.info(2)
            all_form_data = cursorObject.fetchall()
            
            audit_form = []
            audit_formIndex = -1
            section_list = []
            for row in all_form_data:
                
                answerOptions = []
                cursorObject.execute('SELECT * From answerOption ao  WHERE questionId  = '+str(row[4]))
                all_option_data = cursorObject.fetchall()
                # logger.info(row[0])
                for row2 in all_option_data:
                    answerOptions.append({'label':row2[1],'score': row2[2]})
                # logger.info(101)
                if row[2] not in section_list:
                        # logger.info(102)
                        section_list.append(row[2])
                        # logger.info(1021)
                        section = {'section': row[7], 'subSection':[{'ssid':row[3],'questions': []}]}
                        # logger.info(104)
                        section['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[12],'answerType': row[13],'attribute': row[14],'intents': row[15],'answerOptions': answerOptions,'timings': []})
                        audit_form.append(section)
                        audit_formIndex = audit_formIndex + 1
                else:
                    # logger.info(103)
                    index = section_list.index(row[2])
                    # logger.info(105)
                    # logger.info(index)
                    subsFound = False
                    for section in audit_form:
                        for subs in section['subSection']:
                            if subs['ssid'] == row[3]:
                                subsFound = True
                                audit_form[index]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4],'question': row[12],'answerType': row[13],'attribute': row[14],'intents': row[15],'answerOptions': answerOptions,'timings': []})
                        
                                
                    if subsFound == False:
                        audit_form[audit_formIndex]['subSection'].append({'ssid':row[3],'questions': []})
                        audit_form[audit_formIndex]['subSection'][len(section['subSection'])-1]['questions'].append({'sid': row[2],'ssid': row[3],'qid': row[4], 'question': row[12],'answerType': row[13],'attribute': row[14],'intents': row[15],'answerOptions': answerOptions,'timings': []})
                    
                        
            logger.info(audit_form)
            log_message = "stt response: " + str(trnascript_for_nlp)
            append_log(log_message,log_file_path)

            log_message = "audit form: " + str(audit_form)
            append_log(log_message,log_file_path)
            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Auditing"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)

            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s
                                WHERE id = %s
                                """

            new_value = "Auditing"
            condition_value = savedCallResult[0]
            cursorObject.execute(update_query, (new_value,condition_value))
            dataBase2.commit()    
            audit_score = 0
            sectionIndex = 0
            for section in audit_form:
                if section['section'] != 'Call Category':
                    questionIndex = 0
                    for ssIndex, ss in enumerate(section['subSection']):
                        for qIndex, question in enumerate(ss['questions']):
                            # print(question)
                            # if question['intents'] == '':
                            #     continue
                            request_data_nlp = {
                                "text": trnascript_for_nlp,
                                "prompts": [
                                    {
                                        "entity": question['attribute'],
                                        "prompts": [question['intents']],
                                        "type": "multiple"
                                    }
                                ],
                                "additional_params": {}
                            }
                            # print(request_data_nlp)
                            logger.info("LLM trigger status - request")
                            logger.info(str(question))
                            logger.info(str(request_data_nlp))
                            log_message = "Sequence: " +str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex)
                            append_log(log_message,log_file_path)
                            log_message = "question: " + str(question)
                            append_log(log_message,log_file_path)
                            log_message = "request data: " + str(request_data_nlp)
                            append_log(log_message,log_file_path)
                            try:
                                nlp_raw_response = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
                                nlp_response = nlp_raw_response.json()
                                logger.info("LLM trigger status - response "+str(sectionIndex)+", "+str(ssIndex)+" , "+ str(qIndex))
                                # logger.info("Pedning "+str(len(audit_form) - (sectionIndex + 1))+" , "+ str(len(section['questions']) - (qIndex + 1)))
                                log_message = "response data: " + str(nlp_response)
                                append_log(log_message,log_file_path)
                                print(nlp_response)
                                if 'data' in nlp_response:
                                    if 'derived_value' in nlp_response['data']:
                                        result = nlp_response['data']['derived_value'][0]['result']
                                        # print(result)
                                        if len(result) > 0 and result.lower() != 'no':
                                            # logger.info(1)
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'YES'
                                            # logger.info(2)
                                            for ans in audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answerOptions']:
                                                if ans['label'] == 'YES':
                                                    audit_score = audit_score + int(str(ans['score']))
                                        else:
                                            # logger.info(3)
                                            audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['answer'] = 'NO'
                                        if 'reference' in nlp_response['data']['derived_value'][0]:
                                            reference_text = ''
                                            for index, obj in enumerate(nlp_response['data']['derived_value'][0]['reference']):
                                                if obj['text'] == 'Model timed out':
                                                     obj['text'] = 'NA'
                                                logger.info(reference_text)
                                                logger.info(str(obj['text']))
                                                reference_text = reference_text + obj['text'] + ' '
                                                timing = { "startTime": obj['start_time'],
                                                            "endTime": obj['end_time'],
                                                            "referenceText": obj['text']
                                                        }
                                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['timings'].append(timing)
                                            # logger.info(4)
                                            if len(reference_text) > 0:
                                                print('1')
                                                request_data_call_sentiment = { 'text':  reference_text}
                                                # try:
                                                #     sentiment_raw_response = requests.post(sentiment_endpoint+"/predict_sentiments", headers=header, json=request_data_call_sentiment, timeout=20)
                                                
                                                #     sentiment_response = sentiment_raw_response.json()
                                                
                                                #     # print(sentiment_response)
                                                    
                                                #     if 'data' in sentiment_response and 'derived_value' in sentiment_response['data']:

                                                #         update_query = """
                                                #         UPDATE transcriptsAndAuditResults
                                                #         SET overallSentiment = %s
                                                #         WHERE fileName = %s
                                                #         """
                                                #         transformed_data = {}
                                                #         for item in sentiment_response['data']['derived_value'][0]['result']:
                                                #             key = next(key for key in item.keys() if key != "confidence_score")
                                                #             value = item[key]
                                                #             transformed_data[key] = value
                                                #         audit_form[sectionIndex]['questions'][qIndex]['sentiment'] = transformed_data['polarity']
                                                # except Exception as e:
                                                #     audit_form[sectionIndex]['questions'][qIndex]['sentiment'] = ''
                                                #     print(e)
                                            
                                questionIndex = questionIndex + 1
                            except requests.exceptions.Timeout:
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['apiTimedout'] = 1
                                questionIndex = questionIndex + 1
                                logger.info("The request timed out. Please try again later.")
                                pass
                            except requests.Timeout:
                                questionIndex = questionIndex + 1
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['apiTimedout'] = 1
                                logger.info("The request timed out. Please try again later.")
                                pass
                            except requests.ConnectionError:
                                questionIndex = questionIndex + 1
                                audit_form[sectionIndex]['subSection'][ssIndex]['questions'][qIndex]['apiTimedout'] = 1
                                logger.info("The request timed out. Please try again later.")
                                pass

                sectionIndex = sectionIndex + 1

            logger.info("Audit Form filled")
            logger.info("DELETE FROM auditNexDb.auditAnswer WHERE callId = '"+str(savedCallResult[0])+"';")
            if True or 'reAudit' not in request_data:
                delete_query = "DELETE FROM auditNexDb.auditAnswer WHERE callId = '"+str(savedCallResult[0])+"';"
                cursorObject.execute(delete_query)
                dataBase2.commit()
            for sindex, section in enumerate(audit_form):
                logger.info(sindex)
                for ssIndex, ss in enumerate(section['subSection']):
                    logger.info(ssIndex)
                    for qindex, question in enumerate(ss['questions']):
                        logger.info(qindex)
                        score = 0
                        scored = 0
                        if 'answer' not in question:
                            question['answer'] = ''
                        if 'sentiment' not in question:
                            question['sentiment'] = ''
                        logger.info(1)
                        for option in question['answerOptions']:
                            print(option['label'].lower(),question['answer'].lower())
                            if option['label'].lower() == question['answer'].lower():
                                scored = int(option['score'])
                            if option['label'].lower() == 'yes':
                                score = int(option['score'])
                        logger.info(2)
                        logger.info(str(question))
                        logger.info(question['sid'])
                        logger.info(question['ssid'])
                        logger.info(question['qid'])
                        logger.info(3)
                        try:
                            if 'apiTimedout' in question:
                                logger.info('timeout')
                                cursorObjectInsert = dataBase2.cursor(buffered=True)
                                add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment,apiTimedout) VALUES(%s, %s, %s, %s, %s, %s, %s, %s,%s,%s)")
                                add_result = (process_id,savedCallResult[0],question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '',question['apiTimedout'])
                            else:
                                cursorObjectInsert = dataBase2.cursor(buffered=True)
                                add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                                add_result = (process_id,savedCallResult[0],question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '')

                        
                        except Exception as e:
                            logger.info(str(e))
                        cursorObjectInsert.execute(add_column, add_result)
                        
                        dataBase2.commit()
                        cursorObjectInsert.close()

                        cursorObject = dataBase2.cursor(buffered=True)
                        logger.info("save done 1")
                        logger.info(str(savedCallResult[0]))
                        logger.info(str(question['sid']))
                        logger.info(str(question['qid']))
                        logger.info("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(savedCallResult[0])+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))
                        try:
                            cursorObject.execute("SELECT * FROM auditNexDb.auditAnswer where callId = "+str(savedCallResult[0])+" and sectionId = " + str(question['sid']) + " and questionId = " + str(question['qid']))
                    
                            savedQuestionResult = cursorObject.fetchone()
                        except Exception as e:
                            logger.info(str(e))
                        logger.info("saved done"+str(savedQuestionResult[0]))
                        for tindex, timing in enumerate(question['timings']):
                            add_column = ("INSERT INTO auditNexDb.timing (startTime, endTime, speaker, `text`, auditAnswerId)" "VALUES(%s, %s, %s, %s, %s)")

                            add_result = (timing['startTime'],timing['endTime'],'',timing['referenceText'], savedQuestionResult[0])

                            cursorObject.execute(add_column, add_result)
                            
                            dataBase2.commit()
                            print("save done 2")
            print("---------")
            print("Update successful - auditFormFilled")
            print("---------")
            logger.info("LLM trigger status - started")
            end_time_llm = datetime.now()
            start_time_sentiment = datetime.now()
            request_data_call_sentiment = { 'text':  trnascript_for_nlp}
            logger.info("predict_sentiments")
            logger.info(sentiment_endpoint+"/predict_sentiments")
            logger.info(str(request_data_call_sentiment))

            try:
                requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "AuditDone"}, timeout=10)
            except Exception as e:
                print(e)
                logger.error(e)
            update_query = """
                                UPDATE auditNexDb.call
                                SET status = %s
                                WHERE id = %s
                                """

            new_value = "AuditDone"
            condition_value = savedCallResult[0]
            cursorObject.execute(update_query, (new_value,condition_value))
            dataBase2.commit() 
            # try:
            #     logger.info('predict_sentiments 2')
            #     sentiment_raw_response = requests.post(sentiment_endpoint+"/predict_sentiments", headers=header, json=request_data_call_sentiment, timeout=20)

            #     sentiment_response = sentiment_raw_response.json()
                
            #     # print(sentiment_response)
                
            #     if 'data' in sentiment_response and 'derived_value' in sentiment_response['data']:

            #         update_query = """
            #         UPDATE transcriptsAndAuditResults
            #         SET overallSentiment = %s
            #         WHERE fileName = %s
            #         """
            #         transformed_data = {}
            #         for item in sentiment_response['data']['derived_value'][0]['result']:
            #             key = next(key for key in item.keys() if key != "confidence_score")
            #             value = item[key]
            #             transformed_data[key] = value

            #         updated_transformed_value = {
            #             "polarity": {
            #                 "value": transformed_data['polarity'],
            #                 "remarks": ""
            #             }
            #         }
            #         add_column = ("INSERT INTO sentiment (category, result, remarks, callId)" "VALUES(%s, %s, %s, %s)")

            #         add_result = ('polarity',transformed_data['polarity'],'', savedCallResult[0])

            #         cursorObject.execute(add_column, add_result)
            #         dataBase2.commit()
            #         logger.info("---------")
            #         logger.info("Update successful - overallSentiment")
            #         logger.info("---------")
            # except requests.exceptions.Timeout:
            #     logger.info("The request timed out. Please try again later.")
            # except requests.Timeout:
            #     pass
            # except requests.ConnectionError:
            #     pass
            # logger.info(1)
            # end_time_sentiment = datetime.now()
        start_time_cs = datetime.now()
        logger.info("call_summary")
        logger.info(nlp_endpoint+"/call_summary")
        request_data_call_sentiment = { 'text':  trnascript_for_nlp}
        logger.info(str(request_data_call_sentiment))
        
        append_log("call summary request: " + str(request_data_call_sentiment),log_file_path)
        try:
            nlp_raw_response_cs = requests.post(nlp_endpoint+"/call_summary", headers=header, json=request_data_call_sentiment, timeout=20)
            nlp_response_cs = nlp_raw_response_cs.json()
            print(nlp_response_cs)
            append_log("call summary response: " + str(nlp_response_cs),log_file_path)
            if 'data' in nlp_response_cs and 'derived_value' in nlp_response_cs['data']:

                update_query = """
                UPDATE auditNexDb.call
                SET summary = %s, metaData = %s
                WHERE audioName = %s
                """

                new_value = nlp_response_cs['data']['derived_value'][0]['result']
                condition_value = file_name

                cursorObject.execute(update_query, (json.dumps(new_value), '' , condition_value))
                dataBase2.commit()
                logger.info("---------")
                logger.info("Update successful - summaryText")
                logger.info("---------")
        except Exception as e:
            print(e)

        try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json={"callId": savedCallResult[0], "status": "Summary"}, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)
        update_query = """
                            UPDATE auditNexDb.call
                            SET status = %s
                            WHERE id = %s
                            """

        new_value = "Summary"
        condition_value = savedCallResult[0]
        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit() 
        end_time_cs = datetime.now()
        # start_time_qa = datetime.now()
        # logger.info("qa_notes")
        # logger.info(nlp_endpoint+"/qa_notes")
        # logger.info(str(request_data_call_sentiment))
        # try:
        #     nlp_raw_response_cs = requests.post(nlp_endpoint+"/qa_notes", headers=header, json=request_data_call_sentiment, timeout=20)
        #     nlp_response_cs = nlp_raw_response_cs.json()
        #     logger.info(4)
        #     # print(nlp_response_cs)
        #     if 'data' in nlp_response_cs and 'derived_value' in nlp_response_cs['data']:
        #         qa_notes = "Positive Feedback:<br> "+nlp_response_cs['data']['derived_value'][0]['result']['positive_feedback']
        #         qa_notes = qa_notes + "<br><br>Areas for Improvement:<br> "+nlp_response_cs['data']['derived_value'][0]['result']['area_of_improvement']
        #         update_query = """
        #         UPDATE auditNexDb.call
        #         SET qaNotes = %s
        #         WHERE audioName = %s
        #         """

        #         new_value = qa_notes
        #         condition_value = file_name

        #         cursorObject.execute(update_query, (json.dumps(new_value), condition_value))
        #         dataBase2.commit()
        #         logger.info("---------")
        #         logger.info("Update successful - qaNotes")
        #         logger.info("---------")
        # except Exception as e:
        #     print(e)
        
        end_time_qa = datetime.now()

        
        logger.info(5)


        end_time = datetime.now()
        logger.info(5)
        duration = (end_time - start_time).total_seconds()
        logger.info(6)
        duration_stt = (end_time_stt - start_time_stt).total_seconds()
        logger.info(7)
        duration_llm = (end_time_llm - start_time_llm).total_seconds()
        logger.info(8)
        duration_cs = (end_time_cs - start_time_cs).total_seconds()
        logger.info(9)
        duration_qa = (end_time_qa - start_time_qa).total_seconds()
        logger.info(10)
        duration_sentiment = (end_time_sentiment - start_time_sentiment).total_seconds()
        logger.info(11)
        hours, remainder = divmod(duration, 3600)
        logger.info(12)
        minutes, seconds = divmod(remainder, 60)
        logger.info(13)
        duration_formatted = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        logger.info(14)
        logger.info(start_time)
        logger.info(end_time)
        logger.info(convert_seconds(int(float(audioDuration))))
        logger.info(duration_formatted)
        logger.info(convert_seconds(int(float(duration_stt))))
        logger.info(convert_seconds(int(float(duration_llm))))
        logger.info(convert_seconds(int(float(duration_cs))))
        logger.info(convert_seconds(int(float(duration_qa))))
        logger.info(convert_seconds(int(float(duration_sentiment))))
        if True:
            insert_log_query = """
                INSERT INTO auditNexDb.logs (startTime, end_time, audioDuration, processingTime, filename, timeStt, timeLlm, timeCs, timeQa, timeSentiment)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            cursorObject.execute(insert_log_query, (start_time, end_time, convert_seconds(int(float(audioDuration))), duration_formatted, request_data['file_name'], convert_seconds(int(float(duration_stt))), convert_seconds(int(float(duration_llm))), convert_seconds(int(float(duration_cs))), convert_seconds(int(float(duration_qa))), convert_seconds(int(float(duration_sentiment)))))
            dataBase2.commit()
            logger.info(15)
        else:
            update_query = """
                UPDATE logs
                SET start_time = %s, end_time = %s, audio_duration = %s, processing_time = %s, time_stt = %s, time_llm = %s, time_cs = %s, time_qa = %s, time_sentiment = %s
                WHERE filename = %s
                """
            cursorObject.execute(update_query, (start_time, end_time, convert_seconds(int(float(stt_json_response[0]))), duration_formatted, convert_seconds(int(float(duration_stt))), convert_seconds(int(float(duration_llm))), convert_seconds(int(float(duration_cs))), convert_seconds(int(float(duration_qa))), convert_seconds(int(float(duration_sentiment))), request_data['file_name']))
            dataBase2.commit()
            logger.info("---------")
            logger.info("Update successful processes")    
        logger.info(16)
        request_data_wb = {"callId": savedCallResult[0], "status": "Complete"}
        logger.info(17)
        try:
            requests.post(auditnex_endpoint+"/api/webhook/callStatus", headers=header, json=request_data_wb, timeout=10)
        except Exception as e:
            print(e)
            logger.error(e)

        update_query = """
                            UPDATE auditNexDb.call
                            SET status = %s
                            WHERE id = %s
                            """

        new_value = "Complete"
        condition_value = savedCallResult[0]
        cursorObject.execute(update_query, (new_value,condition_value))
        dataBase2.commit() 
        logger.info(18)
        # wp_response = wb_raw_response.json()
        # logger.info(19)
        logger.info("Webhook triggered")
        
        return {'status': 'Data saved successfully'}
        
        # response = requests.post(callback_url_new, headers=header, json=final_response)
        # return final_response    
    
    else:
        logger.info("API: Interface Something went wrong:")
        return False, "API: Interface Something went wrong:"