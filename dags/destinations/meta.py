"""
Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""Meta Custom Audiences destination implementation."""

import hashlib
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.customaudience import CustomAudience
from pydantic import Field
from typing import Any, Dict, List, Mapping, Optional, Sequence
from utils import ProtocolSchema, RunResult, ValidationResult, TadauMixin

# Default batch size (adjust as needed)
_BATCH_SIZE = 1000

_USER_IDENTIFIER_FIELDS = [
    "email",
    "phone",
    "first_name",
    "last_name",
    "city",
    "state",
    "country_code",
    "zip_code",
]

class Destination(TadauMixin):
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._api = FacebookAdsApi.init(
            access_token=config['access_token'],
            app_secret=config['app_secret'],
            app_id=config['app_id'],
        )
        self._audience = CustomAudience(config['audience_id'])

    def send_data(
        self, input_data: List[Mapping[str, Any]], dry_run: bool
    ) -> Optional[RunResult]:
        """Builds payload and sends data to Meta API."""
        if len(input_data) == 0:
            print("No rows of user data to send, exiting out of destination.")
            return RunResult(dry_run=dry_run, successful_hits=0, failed_hits=0)

        user_data = []
        failures = []

        print(f"Processing {len(input_data)} user records")
        for index, row in enumerate(input_data):
            try:
                user = self._process_user_data(row)
                user_data.append(user)
            except ValueError as ve:
                err_msg = f"Could not process data at row '{index}': {str(ve)}"
                print(err_msg)
                failures.append(err_msg)

        print(f"There were '{len(failures)}' user rows that couldn't be processed.")

        if dry_run:
            print("Running as a dry run, so skipping upload steps.")
            return RunResult(
                dry_run=True,
                successful_hits=len(user_data),
                failed_hits=len(failures),
                error_messages=failures
            )

        try:
            response = self._audience.add_users(schema=CustomAudience.Schema.email_hash, data=user_data)
            print(f"Successfully added {response['num_received']} users to the audience.")
            return RunResult(
                dry_run=False,
                successful_hits=response['num_received'],
                failed_hits=len(failures),
                error_messages=failures
            )
        except Exception as e:
            error_msg = f"Failed to add users to audience: {str(e)}"
            print(error_msg)
            failures.append(error_msg)
            return RunResult(
                dry_run=False,
                successful_hits=0,
                failed_hits=len(input_data),
                error_messages=failures
            )

    def _process_user_data(self, user_data: Mapping[str, Any]) -> str:
        """Process and hash user data."""
        if 'email' in user_data:
            return hashlib.sha256(user_data['email'].lower().encode('utf-8')).hexdigest()
        raise ValueError("Email is required for Meta Custom Audiences")

    @staticmethod
    def schema() -> Optional[ProtocolSchema]:
        """Returns the required metadata for this destination config."""
        return ProtocolSchema(
            "META_CUSTOM_AUDIENCE",
            [
                ("access_token", str, Field(description="Meta API Access Token")),
                ("app_secret", str, Field(description="Meta App Secret")),
                ("app_id", str, Field(description="Meta App ID")),
                ("audience_id", str, Field(description="Custom Audience ID")),
            ]
        )

    def batch_size(self) -> int:
        """Returns the required batch_size for the underlying destination API."""
        return _BATCH_SIZE

    def validate(self) -> ValidationResult:
        """Validates the provided config."""
        required_fields = ["access_token", "app_secret", "app_id", "audience_id"]
        missing_fields = [field for field in required_fields if field not in self._config]
        
        if missing_fields:
            return ValidationResult(
                is_valid=False,
                error_message=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # You might want to add more validation here, such as checking the format of the fields
        # or making a test API call to ensure the credentials are valid
        
        return ValidationResult(is_valid=True)