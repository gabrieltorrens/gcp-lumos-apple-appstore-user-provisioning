
# README

## Overview

I believe that standing permissions to release to the Apple App Store is a risk. You can use Lumos or other identity software to send a webhook to GCP when a user requests time based access to the App Store.
This Google Cloud Function handles incoming requests from a Lumos provisioning webhook. It processes the request to invite users to Apple App Store Connect or promote existing users to App Manager roles.
Use this function along with a deprovioning function and deprovisioning request that triggers when a user's access expires.

## Setup

### Prerequisites

- App Store Connect API credentials (issuer ID, key ID, private key)
- Generate a secret to be used to for validation.

### Environment Variables

Set the following environment variables in your Google Cloud Function configuration:

- `ISSUER_ID`: The issuer ID for App Store Connect API.
- `KEY_ID`: The key ID for App Store Connect API.
- `API_KEY`: The private key for App Store Connect API.
- `VALIDATION_KEY`: A custom key for validating incoming requests. This key should be stored in GCP and included in the Lumos request headers.
- `EMAIL_DOMAIN`: The email domain to be validated against.
- `APP_ID`: The App ID to be used in the user invitation.
- `LOG_LEVEL_INT`: (Optional) The logging level. Default is 20 (info).

## Usage

This function is designed to be triggered by HTTP requests from the Lumos provisioning webhook.

### Request Format

Lumos sends a JSON payload of access request data when the provisioning webhook is triggered. The format of this payload is below.

```json

{
  "application": {
    "app_id": "demo_app",
    "instance_id": "87t6g767y67atdsais",
    "user_friendly_label": "Demo App"
  },
  "permissions": [
    {
      "label": "Permission One Label",
      "value": "Permission One",
      "type": "PERMISSION",
      "source": "MANUAL"
    },
    {
      "label": "Permission Two Label",
      "value": "Permission Two",
      "type": "PERMISSION",
      "source": "MANUAL"
    }
  ],
  "target_user": {
    "email": "peterparker@lumos.com",
    "given_name": "Peter",
    "family_name": "Parker"
  },
  "access_length": 43189,
  "request_comment": "Give me access!",
  "request_task_url": "http://lumosidentity.com/tasks?requestId=12898293343"
}

```

### Headers

The request from Lumos must include a `Validation` custom header with a custom value matching the `VALIDATION_KEY` environment variable. This is necessary because the Lumos webhook requires the function to be public.

### Response

- If the request is successful, the function responds with an empty body and a 204 status code.
- See Lumos' documentation for the response they expect.

## Functions

### `create_jwt(issuer_id, key_id, private_key)`

Generates a JWT for authenticating requests to the App Store Connect API.

### `get_app_store_uid(jwt_token, user_email)`

Retrieves the App Store Connect user ID for a given email address.

### `get_app_store_user_profile(jwt_token, uid)`

Retrieves the profile information of a user given their App Store Connect user ID.

### `invite_user(jwt_token, user_email, user_first_name, user_last_name, user_permission)`

Invites a new user to App Store Connect.

### `promote_user_to_app_manager(jwt_token, uid)`

Promotes an existing user to the App Manager role in App Store Connect.

### `main(request)`

Main function to handle incoming requests, validate them, and perform the appropriate actions (invite or promote users).

## Logging

The function uses Google Cloud Logging when deployed to Google Cloud Functions. For local testing, it uses standard logging with a default level of DEBUG.
