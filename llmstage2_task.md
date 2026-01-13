For llm stage2 we have to query auditform
use query from query_audit_form.py
here is sample records received from query,
[{"id":1,"auditFormId":1,"sectionId":1,"subSectionId":1,"questionId":1,"isCritical":0,"applicableTo":"None","criticalValue":null,"createdAt":"2025-01-06 15:36:02","updatedAt":"2025-02-24 11:12:38","name":"Was there a confirmation of the voice recording and customer acknowledgment obtained before initiating the trade?","description":"","answerType":"dropdown","attribute":"trade_name","prompt":"List all the individual stocks discussed during the entire conversation in JSON like ['name1','name2','name3',...]","intent":"List all the individual stocks discussed during the entire conversation in JSON like ['name1','name2','name3',...]","hindiIntent":"List all the individual stocks discussed during the entire conversation in JSON like ['name1','name2','name3',...]","requestType":"Llm","fieldValue":null},{"id":2,"auditFormId":1,"sectionId":1,"subSectionId":2,"questionId":2,"isCritical":0,"applicableTo":"None","criticalValue":null,"createdAt":"2025-01-06 15:36:02","updatedAt":"2025-02-24 11:12:38","name":"Who initiated the trade during the call the client, the dealer or was it mutually decided?","description":"","answerType":"dropdown","attribute":"trade_initialization","prompt":"If confirmed trade transaction executed during the call, who has initiated the first executed confirmed trade discussion during the call, the 'Dealer'or the 'Client' and answer in valid JSON like {'validation':'Dealer/Client'}. The answer of the following question must consider these criteras:  Dealer initiate trade scenarios:    1. trade discussion initiate with the dialouge by providing information on stocks, market conditions, growth prediction, market trends and strategies for example    2. trade discussion initiate by asking to place a buying/selling order of a specific stock   3. trade discussion initiate by mentioning that the dealer want to buy/sell any specific stock   4. trade discussion initiate by providing suggesion to buy/sell a specific stock at particular price and quantity   5. trade discussion initiate by suggesting the client for square off of a specific position   6. trade discussion initiate by asking the client whether he/she want to buy/sell a stock a any spefic price/quantity   7. trade discussion initiate by suggesting the client to let's make a buy/sell a particular specific with specific price/quantity   8. trade discussion initiate by asking to confirm the order.   9. trade discussion initiate by asking for permission to place order for the client to buy/sell a specific stock    Client initiate trade scenarios:   1. trade discussion initiate by giving instruction to the dealer to buy/sell a specific stock with specific price/quantity.   2. trade discussion initiate by instructing the dealer to do square off\n 3. trade discussion initiate by intructing to put a specific quantity for sell   4. trade discussion initiate by asking and seeking information on the current market price, market condition and or growth potential of any specific stock   5. trade discussion initiate by asking about the current market price, market condition and or growth potential of stock market.   6. trade discussion initiate by requesting to take further more quantity of a stock   7. trade discussion initiate by instructing to put more in a specific stock for trade   8. trade discussion initiate by instrucing to buy/sell a specific stock immediately","intent":"If confirmed trade transaction executed during the call, who has initiated the first executed confirmed trade discussion during the call, the 'Dealer'or the 'Client' and answer in valid JSON like {'validation':'Dealer/Client'}. The answer of the following question must consider these criteras:  Dealer initiate trade scenarios:    1. trade discussion initiate with the dialouge by providing information on stocks, market conditions, growth prediction, market trends and strategies for example    2. trade discussion initiate by asking to place a buying/selling order of a specific stock   3. trade discussion initiate by mentioning that the dealer want to buy/sell any specific stock   4. trade discussion initiate by providing suggesion to buy/sell a specific stock at particular price and quantity   5. trade discussion initiate by suggesting the client for square off of a specific position   6. trade discussion initiate by asking the client whether he/she want to buy/sell a stock a any spefic price/quantity   7. trade discussion initiate by suggesting the client to let's make a buy/sell a particular specific with specific price/quantity   8. trade discussion initiate by asking to confirm the order.   9. trade discussion initiate by asking for permission to place order for the client to buy/sell a specific stock    Client initiate trade scenarios:   1. trade discussion initiate by giving instruction to the dealer to buy/sell a specific stock with specific price/quantity.   2. trade discussion initiate by instructing the dealer to do square off\n 3. trade discussion initiate by intructing to put a specific quantity for sell   4. trade discussion initiate by asking and seeking information on the current market price, market condition and or growth potential of any specific stock   5. trade discussion initiate by asking about the current market price, market condition and or growth potential of stock market.   6. trade discussion initiate by requesting to take further more quantity of a stock   7. trade discussion initiate by instructing to put more in a specific stock for trade   8. trade discussion initiate by instrucing to buy/sell a specific stock immediately","hindiIntent":"If confirmed trade transaction executed during the call, who has initiated the first executed confirmed trade discussion during the call, the 'Dealer'or the 'Client' and answer in valid JSON like {'validation':'Dealer/Client'}. The answer of the following question must consider these criteras:  Dealer initiate trade scenarios:    1. trade discussion initiate with the dialouge by providing information on stocks, market conditions, growth prediction, market trends and strategies for example    2. trade discussion initiate by asking to place a buying/selling order of a specific stock   3. trade discussion initiate by mentioning that the dealer want to buy/sell any specific stock   4. trade discussion initiate by providing suggesion to buy/sell a specific stock at particular price and quantity   5. trade discussion initiate by suggesting the client for square off of a specific position   6. trade discussion initiate by asking the client whether he/she want to buy/sell a stock a any spefic price/quantity   7. trade discussion initiate by suggesting the client to let's make a buy/sell a particular specific with specific price/quantity   8. trade discussion initiate by asking to confirm the order.   9. trade discussion initiate by asking for permission to place order for the client to buy/sell a specific stock    Client initiate trade scenarios:   1. trade discussion initiate by giving instruction to the dealer to buy/sell a specific stock with specific price/quantity.   2. trade discussion initiate by instructing the dealer to do square off\n 3. trade discussion initiate by intructing to put a specific quantity for sell   4. trade discussion initiate by asking and seeking information on the current market price, market condition and or growth potential of any specific stock   5. trade discussion initiate by asking about the current market price, market condition and or growth potential of stock market.   6. trade discussion initiate by requesting to take further more quantity of a stock   7. trade discussion initiate by instructing to put more in a specific stock for trade   8. trade discussion initiate by instrucing to buy/sell a specific stock immediately","requestType":"Llm","fieldValue":null},{"id":3,"auditFormId":1,"sectionId":1,"subSectionId":2,"questionId":3,"isCritical":0,"applicableTo":"None","criticalValue":null,"createdAt":"2025-01-06 15:36:02","updatedAt":"2025-02-24 11:12:38","name":"Did the dealer induce or force the customer to trade during the call?","description":"","answerType":"dropdown","attribute":"clear_and_effective_communication","prompt":"Did the agent induce or force the customer to do trading during the conversation? Answer the following question in 'YES' or 'NO' in valid JSON like {'validation':'YES/NO'} and explaination outside the JSON","intent":"Did the agent induce or force the customer to do trading during the conversation? Answer the following question in 'YES' or 'NO' in valid JSON like {'validation':'YES/NO'} and explaination outside the JSON","hindiIntent":"Did the agent induce or force the customer to do trading during the conversation? Answer the following question in 'YES' or 'NO' in valid JSON like {'validation':'YES/NO'} and explaination outside the JSON","requestType":"Llm","fieldValue":null}]  -> store in audit_form variable

first we hit,
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

nlp_raw_response_1 = requests.post(nlp_endpoint+"/extract_information", headers=header, json=request_data_nlp, timeout=50)
            nlp_response_1 = nlp_raw_response_1.json()
            logger.info("LLM test1 kotak -LLM trigger status - response "+str(nlp_response_1))
            nlp_response_1_result = None
           
            if 'data' in nlp_response_1:
                if 'derived_value' in nlp_response_1['data']:
                   
                    nlp_response_1_result = nlp_response_1['data']['derived_value'][0]['result']
                    if nlp_response_1_result == 'non-trade':
                      Here we loop auditForm we extracted above and store ['answer'] = 'NA in each row


if nlp_response_1_result != 'non-trade':
trnascript_for_nlp take from text transcript table where callId = id from call table
loop this audit_form and get each question and answer type and prompt and intent and hindiIntent and requestType and fieldValue
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
Store
if 'data' in nlp_response:
                                        if 'derived_value' in nlp_response['data']:
                                            result = nlp_response['data']['derived_value'][0]['result']
                                            print("llm emotion output -> ", result)


                                            if len(result) > 0:


                                                if result.lower() == "yes":
                                                    audit_form[index]['answer'] = 'YES'
                                           
                                                elif result.lower() == "no":
                                                    aaudit_form[index]['answer'] = 'NO'


                                                elif result.lower() == "na":
                                                    aaudit_form[index]['answer'] = 'NA'
                                               
                                                else:
                                                    aaudit_form[index]['answer'] = 'NA'


                                                audit_score = audit_score + 0
                                           
                                            else:
                                                aaudit_form[index]['answer'] = 'NA'


Then loop audit_form  save result which includes answer from above into auditAnswer table,

add_column = ("INSERT INTO auditNexDb.auditAnswer (processId, callId, sectionId, subSectionId, questionId, answer, scored, score, sentiment, isCritical, applicableTo) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                            add_result = (process_id,call_id,question['sid'],question['ssid'],question['qid'],question['answer'],scored,score, '', question["isCritical"], question["isApplicableTo"])
