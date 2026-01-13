import mysql.connector
import json

def query_audit_form(audit_form_id):
    try:
        # Database configuration
        config = {
            'host': '74.225.140.57',
            'database': 'testDb',
            'user': 'root',
            'password': 'password', # User provided smtb123, letting user modify if needed
        }
        
        # Override password if smtb123 was the literal intended one
        config['password'] = 'smtb123'

        # Establish connection
        connection = mysql.connector.connect(**config)
        cursor = connection.cursor(dictionary=True)

        # The query provided by the user
        query = f"""
        SELECT afsqm.*, s.*, q.* 
        FROM auditFormSectionQuestionMapping afsqm 
        INNER JOIN section s ON afsqm.sectionId = s.id 
        INNER JOIN question q ON afsqm.questionId = q.id 
        WHERE afsqm.auditFormId = {audit_form_id} 
        AND s.id IN (
            SELECT sectionId 
            FROM auditFormSectionQuestionMapping 
            WHERE auditFormId = {audit_form_id}
        )
        """

        print(f"Executing query for audit_form_id: {audit_form_id}...")
        cursor.execute(query)
        
        # Fetch all results
        rows = cursor.fetchall()
        
        if not rows:
            print("[]")
        else:
            # Print the whole list as a single JSON array
            print(json.dumps(rows, indent=4, default=str))

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("\nMySQL connection closed.")

if __name__ == "__main__":
    # You can change this ID or pass it as an argument
    AUDIT_FORM_ID = 1 
    query_audit_form(AUDIT_FORM_ID)
