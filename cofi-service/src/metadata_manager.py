"""Metadata file processing and database upload for callMetadata and tradeMetadata."""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
import json
import os

from .config import get_settings
from .database import get_database

logger = structlog.get_logger()


# Column mapping from CSV to database (from api_definations.json)
CALL_METADATA_MAPPING = {
    "nId": "nId",
    "sClientId": "sClientId",
    "sClientName": "sClientName",
    "sClientMobileNumber": "sClientMobileNumber",
    "nBranchId": "nBranchId",
    "sBranchName": "sBranchName",
    "sSessionId": "sSessionId",
    "dCallStartTime": "dCallStartTime",
    "dCallEndTime": "dCallEndTime",
    "nCallType": "nCallType",
    "nCallStatus": "nCallStatus",
    "sAgentId": "sAgentId",
    "sAgentName": "sAgentName",
    "sAgentMobileNumber": "sAgentMobileNumber",
    "sRecordingFileName": "sRecordingFileName",
    "sRecordingUrl": "sRecordingUrl",
    "nTagId": "nTagId",
    "sRemark": "sRemark",
    "dLastUpdateTime": "dLastUpdateTime",
    "nFeedBack": "nFeedBack",
    "nIsAdd": "nIsAdd",
    "sSIPChannel": "sSIPChannel"
}

# Trade metadata mapping from CSV columns to database columns
TRADE_METADATA_MAPPING = {
    "orderid": "orderId",
    "client_code": "clientCode",
    "client_name": "clientName",
    "reg_number": "regNumber",
    "al_name": "alName",
    "al_number": "alNumber",
    "al_relation": "alRelation",
    "trade_date": "tradeDate",
    "order_placed_time": "orderPlacedTime",
    "buy/sell": "buySell",
    "inst_type": "instType",
    "expiry_date": "expiryDate",
    "option_type": "optionType",
    "symbol": "symbol",
    "comscriptcode": "comScriptCode",
    "scripname": "scripName",
    "strike_price": "strikePrice",
    "trade_quantity": "tradeQuantity",
    "trade_price": "tradePrice",
    "trade_value": "tradeValue",
    "lot_qty": "lotQty",
    "dealercode_sbmaincode": "dealerCodeSbMainCode",
    "dealername_subrokername": "dealerNameSuBrokerName",
    "dealer_emailid": "dealerEmailId",
    "dealing_branch": "dealingBranch",
    "dealing_zone": "dealingZone",
    "dealing_state": "dealingState",
    "dealing_city": "dealingCity",
    "loginid": "loginId",
    "digit12": "digit12",
    "original_exchange_code": "originalExchangeCode"
}


class CallMetadataRepo:
    """Repository for callMetadata table operations."""
    
    def __init__(self, db):
        self.db = db
    
    def insert_many(self, records: List[Dict[str, Any]], batch_id: int) -> int:
        """Insert multiple callMetadata records."""
        if not records:
            return 0
        
        query = """
            INSERT INTO callMetadata (
                nId, sClientId, sClientName, sClientMobileNumber, nBranchId, sBranchName,
                sSessionId, dCallStartTime, dCallEndTime, nCallType, nCallStatus,
                sAgentId, sAgentName, sAgentMobileNumber, sRecordingFileName, sRecordingUrl,
                nTagId, sRemark, dLastUpdateTime, nFeedBack, nIsAdd, sSIPChannel, batchId
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params_list = []
        for record in records:
            params = (
                record.get('nId'),
                record.get('sClientId'),
                record.get('sClientName'),
                record.get('sClientMobileNumber'),
                record.get('nBranchId'),
                record.get('sBranchName'),
                record.get('sSessionId'),
                record.get('dCallStartTime'),
                record.get('dCallEndTime'),
                record.get('nCallType'),
                record.get('nCallStatus'),
                record.get('sAgentId'),
                record.get('sAgentName'),
                record.get('sAgentMobileNumber'),
                record.get('sRecordingFileName'),
                record.get('sRecordingUrl'),
                record.get('nTagId'),
                record.get('sRemark'),
                record.get('dLastUpdateTime'),
                record.get('nFeedBack'),
                record.get('nIsAdd'),
                record.get('sSIPChannel'),
                batch_id
            )
            params_list.append(params)
        
        return self.db.execute_many(query, params_list)
    
    def get_by_batch(self, batch_id: int) -> List[Dict]:
        """Get all callMetadata records for a batch."""
        query = "SELECT * FROM callMetadata WHERE batchId = %s"
        return self.db.execute_query(query, (batch_id,))
    
    def get_count_by_batch(self, batch_id: int) -> int:
        """Get count of callMetadata records for a batch."""
        query = "SELECT COUNT(*) as count FROM callMetadata WHERE batchId = %s"
        result = self.db.execute_one(query, (batch_id,))
        return result['count'] if result else 0


class TradeMetadataRepo:
    """Repository for tradeMetadata table operations."""
    
    def __init__(self, db):
        self.db = db
    
    def insert_many(self, records: List[Dict[str, Any]], batch_id: int, process_id: int) -> int:
        """Insert multiple tradeMetadata records."""
        if not records:
            return 0
        
        query = """
            INSERT INTO tradeMetadata (
                orderId, clientCode, clientName, regNumber, alName, alNumber, alRelation,
                tradeDate, orderPlacedTime, buySell, instType, expiryDate, optionType,
                symbol, comScriptCode, scripName, strikePrice, tradeQuantity, tradePrice,
                tradeValue, lotQty, dealerCodeSbMainCode, dealerNameSuBrokerName,
                dealerEmailId, dealingBranch, dealingZone, dealingState, dealingCity,
                loginId, digit12, originalExchangeCode, batchId, processId
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params_list = []
        for record in records:
            params = (
                record.get('orderId'),
                record.get('clientCode'),
                record.get('clientName'),
                record.get('regNumber'),
                record.get('alName'),
                record.get('alNumber'),
                record.get('alRelation'),
                record.get('tradeDate'),
                record.get('orderPlacedTime'),
                record.get('buySell'),
                record.get('instType'),
                record.get('expiryDate'),
                record.get('optionType'),
                record.get('symbol'),
                record.get('comScriptCode'),
                record.get('scripName'),
                record.get('strikePrice'),
                record.get('tradeQuantity'),
                record.get('tradePrice'),
                record.get('tradeValue'),
                record.get('lotQty'),
                record.get('dealerCodeSbMainCode'),
                record.get('dealerNameSuBrokerName'),
                record.get('dealerEmailId'),
                record.get('dealingBranch'),
                record.get('dealingZone'),
                record.get('dealingState'),
                record.get('dealingCity'),
                record.get('loginId'),
                record.get('digit12'),
                record.get('originalExchangeCode'),
                batch_id,
                process_id
            )
            params_list.append(params)
        
        return self.db.execute_many(query, params_list)
    
    def get_by_batch(self, batch_id: int) -> List[Dict]:
        """Get all tradeMetadata records for a batch."""
        query = "SELECT * FROM tradeMetadata WHERE batchId = %s"
        return self.db.execute_query(query, (batch_id,))
    
    def get_count_by_batch(self, batch_id: int) -> int:
        """Get count of tradeMetadata records for a batch."""
        query = "SELECT COUNT(*) as count FROM tradeMetadata WHERE batchId = %s"
        result = self.db.execute_one(query, (batch_id,))
        return result['count'] if result else 0


class MetadataManager:
    """Manages metadata file processing and database upload."""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = get_database()
        self.call_metadata_repo = CallMetadataRepo(self.db)
        self.trade_metadata_repo = TradeMetadataRepo(self.db)
    
    def get_batch_directory(self) -> Path:
        """Get the batch directory path."""
        return Path(self.settings.client_volume) / self.settings.batch_date
    
    def process_call_metadata_csv(self, batch_id: int) -> int:
        """
        Read callMetadata.csv from batch directory and insert into database.
        
        Args:
            batch_id: Current batch ID
            
        Returns:
            Number of records inserted
        """
        batch_dir = self.get_batch_directory()
        csv_path = batch_dir / "callMetadata.csv"
        
        if not csv_path.exists():
            logger.warning("callMetadata_csv_not_found", path=str(csv_path))
            return 0
        
        try:
            # Read CSV file using pandas
            df = pd.read_csv(csv_path)
            logger.info("callMetadata_csv_loaded", rows=len(df))
            
            # Parse call start/end times and add date/time columns
            records = []
            for _, row in df.iterrows():
                record = {}
                
                # Map CSV columns to database columns
                for csv_col, db_col in CALL_METADATA_MAPPING.items():
                    if csv_col in row:
                        value = row[csv_col]
                        # Handle NaN values
                        if pd.isna(value):
                            record[db_col] = None
                        else:
                            record[db_col] = str(value) if not isinstance(value, (int, float)) else value
                
                # Parse dCallStartTime to extract date and time parts
                if record.get('dCallStartTime'):
                    try:
                        start_time = str(record['dCallStartTime'])
                        # Try common formats
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
                            try:
                                dt = datetime.strptime(start_time, fmt)
                                record['callStartDate'] = dt.strftime("%Y-%m-%d")
                                record['callStartTime'] = dt.strftime("%H:%M:%S")
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
                
                # Parse dCallEndTime to extract date and time parts
                if record.get('dCallEndTime'):
                    try:
                        end_time = str(record['dCallEndTime'])
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
                            try:
                                dt = datetime.strptime(end_time, fmt)
                                record['callEndDate'] = dt.strftime("%Y-%m-%d")
                                record['callEndTime'] = dt.strftime("%H:%M:%S")
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
                
                records.append(record)
            
            # Insert records into database in batches
            batch_size = 10000
            total_inserted = 0
            
            for i in range(0, len(records), batch_size):
                batch_records = records[i:i + batch_size]
                inserted_count = self.call_metadata_repo.insert_many(batch_records, batch_id)
                total_inserted += inserted_count
                logger.info("callMetadata_batch_inserted", 
                           batch_num=i // batch_size + 1, 
                           count=inserted_count, 
                           total_so_far=total_inserted)
            
            logger.info("callMetadata_inserted", count=total_inserted, batch_id=batch_id)
            
            return total_inserted
            
        except Exception as e:
            logger.error("callMetadata_processing_failed", error=str(e))
            raise
    
    def process_trade_metadata_csv(self, batch_id: int) -> int:
        """
        Read tradeMetadata.csv from batch directory and insert into database.
        
        Args:
            batch_id: Current batch ID
            
        Returns:
            Number of records inserted
        """
        batch_dir = self.get_batch_directory()
        csv_path = batch_dir / "tradeMetadata.csv"
        
        if not csv_path.exists():
            logger.warning("tradeMetadata_csv_not_found", path=str(csv_path))
            return 0
        
        try:
            # Read CSV file using pandas
            df = pd.read_csv(csv_path)
            logger.info("tradeMetadata_csv_loaded", rows=len(df))
            
            records = []
            for _, row in df.iterrows():
                record = {}
                
                # Map CSV columns to database columns (case-insensitive matching)
                row_dict = {k.lower(): v for k, v in row.items()}
                
                for csv_col, db_col in TRADE_METADATA_MAPPING.items():
                    csv_col_lower = csv_col.lower()
                    if csv_col_lower in row_dict:
                        value = row_dict[csv_col_lower]
                        # Handle NaN values
                        if pd.isna(value):
                            record[db_col] = None
                        else:
                            # Handle numeric fields
                            if db_col in ['tradeQuantity', 'tradeValue', 'lotQty']:
                                try:
                                    record[db_col] = int(value) if value else None
                                except (ValueError, TypeError):
                                    record[db_col] = None
                            elif db_col == 'tradePrice':
                                try:
                                    record[db_col] = float(value) if value else None
                                except (ValueError, TypeError):
                                    record[db_col] = None
                            else:
                                record[db_col] = str(value) if value else None
                
                records.append(record)
            
            # Insert records into database in batches
            batch_size = 10000
            total_inserted = 0
            process_id = self.settings.process_id
            
            for i in range(0, len(records), batch_size):
                batch_records = records[i:i + batch_size]
                inserted_count = self.trade_metadata_repo.insert_many(batch_records, batch_id, process_id)
                total_inserted += inserted_count
                logger.info("tradeMetadata_batch_inserted", 
                           batch_num=i // batch_size + 1, 
                           count=inserted_count, 
                           total_so_far=total_inserted)
            
            logger.info("tradeMetadata_inserted", count=total_inserted, batch_id=batch_id)
            
            return total_inserted
            
        except Exception as e:
            logger.error("tradeMetadata_processing_failed", error=str(e))
            raise
    
    def is_call_metadata_processed(self, batch_id: int) -> bool:
        """Check if callMetadata has already been processed for this batch."""
        count = self.call_metadata_repo.get_count_by_batch(batch_id)
        return count > 0
    
    def is_trade_metadata_processed(self, batch_id: int) -> bool:
        """Check if tradeMetadata has already been processed for this batch."""
        count = self.trade_metadata_repo.get_count_by_batch(batch_id)
        return count > 0

