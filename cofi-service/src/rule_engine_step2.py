import mysql.connector
from mysql.connector import Error
from datetime import datetime,timedelta
from rapidfuzz import fuzz
import re
import time
from collections import defaultdict
# MySQL connection configuration
print(14)
config = {
    'user': 'root',
    'password': 'smtb123',
    'host': '10.125.9.151',
    # 'host': '34.47.181.117',
    #'host': '34.47.196.156',
    # 'database': 'testDb',
    'database': 'auditNexDb'
}
callMetadata = []
callsData = []
tradeAudioMappingData = []
callConversationData = []
tradeMetadataData = []
lotQuantityMappingData = []
# Connect to MySQL
conn = mysql.connector.connect(**config)
cursorObject = conn.cursor(dictionary=True,buffered=True)

        
connection = mysql.connector.connect(**config)
cursor = connection.cursor(buffered=True)

print(12)
def str_to_datetime(date_str, time_str):
    return datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M:%S")

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
    connection = mysql.connector.connect(**config
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
                        print(f"ifQty: {ifQty}")
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
                        print(f"post tradeifQty: {ifQty}")
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
        
        print("Result - ",str(result),nearest_call_meta)
        print('After calling find_matching_trade_with_voice_confirmations - rule_engine_v2', result)
        


        if result and result['tag1'] != 'No call record found' and result['tag1'] != 'Non observatory call' and 'tag3' in result:

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

def execute_trademetarows_optimized(trade_metadata_rows, batch_id, batch_size=10000):
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
                # return
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
    print('Inside process_rule_engine - rule_engine_v2')
    connection = mysql.connector.connect(**config)
    cursor = connection.cursor(dictionary=True,buffered=True)
    
    print('krunal 0')
    cursor.execute("SELECT * FROM callMetadata WHERE batchId = %s", (batch_id,))
    callMetadata = cursor.fetchall()
    print('krunal 1')
    cursor.execute("SELECT * FROM `call` WHERE batchId = %s", (batch_id,))
    callsData = cursor.fetchall()
    print('krunal 2')
    cursor.execute("SELECT * FROM tradeMetadata WHERE voiceRecordingConfirmations = 'Non observatory call' and batchId = %s", (batch_id,))
    rows = cursor.fetchall()
    print('krunal 6')
    for tr1 in rows:
        tr1["orderId"] = normalize_order_id(tr1["orderId"])
        tradeMetadataData.append(tr1)
    allTradeMetadataIds = []
    allTradeMetadataIds = [row['id'] for row in tradeMetadataData]
    
    print("Length of allTradeMetadataIds: ",len(allTradeMetadataIds))
    time.sleep(10)
    cursor.execute("SELECT * FROM tradeAudioMapping WHERE  batchId = %s", (batch_id,))
    rows_tradeAudioMappingData = cursor.fetchall()
    print('krunal 3')
    
    for tr1 in rows_tradeAudioMappingData:
        tr1["orderId"] = normalize_order_id(tr1["orderId"])
        if tr1["tradeMetadataId"] in allTradeMetadataIds:
            tradeAudioMappingData.append(tr1)
            print("Updating tradeAudioMappingData id: ",tr1['id'])
            update_query = """
                UPDATE tradeAudioMapping 
                SET isScript = 0, isPrice = 0, isQuantity = 0
                WHERE id = %s
            """ % (tr1['id'])
            cursor.execute(update_query)    
            connection.commit()
    print('krunal 4')
    cursor.execute("SELECT * FROM callConversation WHERE batchId = %s", (batch_id,))
    callConversationData = cursor.fetchall()
    print('krunal 5')
    
    print('krunal 7')
    # Gather data from table lotQuantityMapping and store in lotQuantityMappingData variable using batchId
    cursor.execute("SELECT * FROM lotQuantityMapping")
    lotQuantityMappingData = cursor.fetchall()
    print('krunal 8')
    
    trade_metadata_rows = tradeAudioMappingData
    last_id = 1
    allTradeMetadataIds = []
    if tradeAudioMappingData and len(tradeAudioMappingData) > 0:
        last_id = tradeAudioMappingData[len(tradeAudioMappingData)-1]['id']
        
    print("length of tradeAudioMappingData: ",len(tradeAudioMappingData))
    time.sleep(10)
    execute_trademetarows_optimized(trade_metadata_rows,batch_id)
    print('krunal 9')
    # return
  
    # cursor.execute("SELECT * FROM tradeAudioMapping WHERE batchId = %s and id > %s", (batch_id, last_id))
    # trade_metadata_rows = cursor.fetchall()  
    # tradeAudioMappingData.extend(trade_metadata_rows)

    # execute_trademetarows_optimized(trade_metadata_rows,batch_id)

   
    
    # time.sleep(10)
    connection2 = mysql.connector.connect(**config)
    cursor2 = connection2.cursor(dictionary=True,buffered=True)
    cursor2.execute("SELECT * FROM tradeAudioMapping WHERE  batchId = %s", (batch_id,))
    tradeAudioMappingData = cursor2.fetchall()

    # # Get total count of records to process
    
    # cursor2.execute("SELECT COUNT(*) as count FROM tradeMetadata WHERE id = 491w6501 AND batchId = %s", (batch_id,))
    # result = cursor2.fetchone()
    # total_records = result['count']
    # print(f'Total records to process: {total_records}')
    cursor2.execute("SELECT * FROM tradeMetadata  WHERE voiceRecordingConfirmations = 'Non observatory call' and batchId = "+str(batch_id))

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
            
            # return
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


    return True