import jwt
import datetime
import os
import requests
import json
import traceback
import time

# Variables for configuration
issuer_id = os.getenv('ISSUER_ID')  # Get issuer ID from environment variables
key_id = os.getenv('KEY_ID')  # Get key ID from environment variables
private_key = os.getenv('API_KEY')  # Get private key from environment variables
validation_key = os.getenv('VALIDATION_KEY')  # Get validation key from environment variables
email_domain = os.getenv('EMAIL_DOMAIN') # Get email domain from environment variables
app_id = os.getenv('APP_ID') # Enter your Apple App ID here

# Logging configuration
if 'FUNCTION_TARGET' in os.environ:
    # Configure logging for cloud function environment
    from google.cloud import logging_v2
    log_client = logging_v2.Client()
    log_level_int = int(os.getenv('LOG_LEVEL_INT', 20))  # Set log level, default to info
    log_client.get_default_handler()  # Initialize the default handler
    log_client.setup_logging(log_level=log_level_int)  # Set up logging with specified log level
    import logging
else:  # Local test runs
    # Configure logging for local development
    import logging
    logging.basicConfig(level=logging.DEBUG)  # Set logging level to DEBUG for local tests

def create_jwt(issuer_id, key_id, private_key):
    # Define the token header
    token_header = {
        'alg': 'ES256',  # Algorithm used for signing the token
        'kid': key_id,  # Key ID
        'typ': 'JWT'  # Token type
    }

    # Define the token payload with required and optional fields
    token_payload = {
        'iss': issuer_id,  # Issuer
        'iat': datetime.datetime.utcnow(),  # Issued at time
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=20),  # Expiration time (20 minutes)
        'aud': 'appstoreconnect-v1',  # Audience
    }

    # Encode the token
    token = jwt.encode(token_payload, private_key, algorithm='ES256', headers=token_header)
    return token  # Return the generated JWT

def get_app_store_uid(jwt_token, user_email):
    # Match email address to App Store Connect user
    logging.info('Searching App Store Connect users for email.')
    all_users_url = f'https://api.appstoreconnect.apple.com/v1/users?filter[username]={user_email}'  # API URL with filter
    headers = {
        'Authorization': f'Bearer {jwt_token}'  # Authorization header with JWT token
    }
    response = requests.get(all_users_url, headers=headers)  # Make the GET request
    if response.status_code == 200:
        # Request was successful
        data = response.json()  # Parse the response JSON
        if data['data']:
            # User found
            uid = data['data'][0]['id']  # Extract user ID
            logging.info('User uid found.')
            return uid  # Return the user ID
        else:
            # User not found
            logging.info('User not found.')
            return None  # Return None if user not found
    elif response.status_code == 500:
        # Server error, retry after waiting
        logging.error("Received 500 error, waiting 10 seconds before retrying.")
        time.sleep(10)  # Wait before retrying
        return get_app_store_uid(jwt_token, user_email)  # Retry the request

    else:
        # Other errors
        logging.info(f"Failed to fetch user: Status code {response.status_code}")
        logging.info(f"Response: {response.text}")
        raise RuntimeError("Failed to get App Store user.")  # Raise error for other status codes

def get_app_store_user_profile(jwt_token, uid):
    # Retrieve user profile using UID
    logging.info('Using UID to get user profile.')
    url = f'https://api.appstoreconnect.apple.com/v1/users/{uid}'  # API URL
    headers = {
        'Authorization': f'Bearer {jwt_token}'  # Authorization header with JWT token
    }
    response = requests.get(url, headers=headers)  # Make the GET request
    logging.info('Retrieved user profile:')
    logging.info(response.json())  # Log the user profile
    return response.json()  # Return the user profile JSON

def invite_user(jwt_token, user_email, user_first_name, user_last_name, user_permission):
    # Invite a new user to App Store Connect
    logging.info('Inviting user to App Store Connect.')
    url = 'https://api.appstoreconnect.apple.com/v1/userInvitations'  # API URL
    headers = {
            'Authorization': f'Bearer {jwt_token}'  # Authorization header with JWT token
        }
    body = {
        "data": {
            "type": 'userInvitations',  # Request type
            "attributes": {
                "email": user_email,  # User email
                "firstName": user_first_name,  # User first name
                "lastName": user_last_name,  # User last name
                "roles": [user_permission, "CLOUD_MANAGED_APP_DISTRIBUTION"],  # User roles
                #"allAppsVisible": True # Optional: Make all apps visible
            },
            "relationships": {
                "visibleApps": {
                    "data": [
                        {
                        "id": app_id,  # App ID
                        "type": "apps"
                        }
                    ]
                }
            }
        }
    }
    # Make the POST request to invite the user
    response = requests.post(url, headers=headers, json=body)

    # Check if the request was successful
    if response.status_code == 201:
        logging.info("Invite successful!")
        logging.info(response.json())  # Print the JSON response
    else:
        logging.error(f"Failed to invite user: Status code {response.status_code}")
        logging.error("Response:", response.text)
        raise RuntimeError('User not invited.')  # Raise error if invite failed
    return response.json()  # Return the invite response JSON

def promote_user_to_app_manager(jwt_token, uid):
    # Promote an existing user to App Manager
    logging.info("Promoting user to App Manager")
    url = f'https://api.appstoreconnect.apple.com/v1/users/{uid}'  # API URL
    headers = {
        'Authorization': f'Bearer {jwt_token}'  # Authorization header with JWT token
    }
    body = {
        "data": {
            "type": 'users',  # Request type
            "id": uid,  # User ID
            "attributes": {
                "roles": ["APP_MANAGER","CLOUD_MANAGED_APP_DISTRIBUTION"],  # New roles
                "allAppsVisible": True  # Make all apps visible
            }
        }
    }
    response = requests.patch(url, headers=headers, json=body)  # Make the PATCH request

    if response.status_code == 200:
        logging.info("User promoted to App Manager!")
    else:
        logging.error(f"Failed to promote user: Status code {response.status_code}")
        logging.error("Response:", response.text)
        raise RuntimeError('User not promoted.')  # Raise error if promotion failed

def main(request):
    # Main function to handle the incoming request
    logging.info('Incoming request:')
    logging.info(request.data)  # Log the raw request data
    if 'Validation' not in request.headers:
        raise ValueError('Validation header is required')  # Check for validation header
    if request.headers['Validation'] != validation_key:
        raise ValueError('Validation header does not match')  # Validate the header
    request_json = request.get_json(silent=True)  # Parse request JSON
    user_email = request_json.get('target_user', {}).get('email')  # Get email from request
    user_first_name = request_json.get('target_user', {}).get('given_name')  # Get first name from request
    user_last_name = request_json.get('target_user', {}).get('family_name')  # Get last name from request
    
    user_permission = request_json['permissions'][0]['label']  # Get user permission from request
    if user_permission != "APP_MANAGER":
        raise RuntimeError('Not an allowed role.')  # Raise error for any other role

    # Check if the email domain is your domain
    if not user_email.endswith(email_domain):
        logging.error("Email domain is not correct. Rejecting.")
        return json.dumps({"response": "NO_PROVISIONING_ACTION"}), 200  # Return no action for incorrect email domains

    try:
        jwt_token = create_jwt(issuer_id, key_id, private_key)  # Create JWT token
        uid = get_app_store_uid(jwt_token, user_email)  # Get App Store user ID from email
        if not uid:
            invite_user(jwt_token, user_email, user_first_name, user_last_name, user_permission)  # Invite user if not found
            logging.info("User invited.")
        else:
            user_profile = get_app_store_user_profile(jwt_token, uid)  # Get user profile
            current_roles = user_profile['data']['attributes']['roles']  # Get current roles
            if "ACCOUNT_HOLDER" in current_roles or "ADMIN" in current_roles:
                logging.error("User is an admin or account holder. Exiting.")
                raise RuntimeError("User is an admin or account holder.")  # Exit if user is admin or account holder
            if "APP_MANAGER" not in current_roles:
                promote_user_to_app_manager(jwt_token, uid)  # Promote user if not already an App Manager
                logging.info("User promoted.")
        return '', 204  # Return success status
    except Exception as exc:
        logging.error(traceback.format_exc())  # Log the error traceback
        raise SystemExit() from exc  # Exit the function on error

if __name__ == '__main__':
    main(None, None)  # Run main function for local testing
