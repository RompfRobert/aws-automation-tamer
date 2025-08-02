"""
AWS Session Manager - Refactored role assumption functionality.

This module provides an improved, production-ready implementation for assuming
AWS IAM roles across accounts with proper error handling, validation, and
configurability.

Features:
- Configurable role names, session duration, and external IDs
- Dynamic session naming for better audit trails
- Regional STS endpoints for better performance
- Input validation and comprehensive error handling
- Optional session caching for performance
- Backwards compatibility with original function
"""

import boto3
import uuid
import re
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from botocore.exceptions import ClientError, NoCredentialsError

# Set up logging
logger = logging.getLogger('aws-automation-tamer.session-manager')


class AssumeRoleError(Exception):
    """
    Custom exception for role assumption errors.
    
    Provides better error context and handling than generic exceptions.
    """
    
    def __init__(self, message: str, account_id: Optional[str] = None, 
                 role_name: Optional[str] = None, region: Optional[str] = None,
                 original_error: Optional[Exception] = None):
        self.account_id = account_id
        self.role_name = role_name
        self.region = region
        self.original_error = original_error
        
        # Build comprehensive error message
        context_parts = []
        if account_id:
            context_parts.append(f"account={account_id}")
        if role_name:
            context_parts.append(f"role={role_name}")
        if region:
            context_parts.append(f"region={region}")
        
        if context_parts:
            context = " (" + ", ".join(context_parts) + ")"
            full_message = f"{message}{context}"
        else:
            full_message = message
            
        if original_error:
            full_message += f" - Original error: {str(original_error)}"
            
        super().__init__(full_message)


class AssumeRoleSessionManager:
    """
    Manages AWS role assumption with best practices.
    
    This class provides a clean, configurable interface for assuming IAM roles
    across AWS accounts while following security and operational best practices.
    """
    
    # AWS account ID pattern (12 digits)
    ACCOUNT_ID_PATTERN = re.compile(r'^\d{12}$')
    
    # Valid AWS regions (subset of commonly used ones)
    VALID_REGIONS = {
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1',
        'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'ap-northeast-2',
        'ca-central-1', 'sa-east-1', 'ap-south-1'
    }
    
    def __init__(self, 
                 default_role_name: str = "aws-automation-tamer-admin",
                 session_duration: int = 3600,
                 session_name_prefix: str = "AwsAutomationTamer",
                 external_id: Optional[str] = None,
                 enable_caching: bool = False):
        """
        Initialize the session manager.
        
        Args:
            default_role_name: Default IAM role name to assume
            session_duration: Session duration in seconds (900-43200)
            session_name_prefix: Prefix for generated session names
            external_id: External ID for additional security (optional)
            enable_caching: Whether to cache sessions for performance
        """
        self.default_role_name = default_role_name
        self.session_duration = session_duration
        self.session_name_prefix = session_name_prefix
        self.external_id = external_id
        self.enable_caching = enable_caching
        
        # Session cache
        self._session_cache: Dict[str, boto3.Session] = {}
        
        # Validate configuration
        self._validate_configuration()
        
        logger.debug(f"AssumeRoleSessionManager initialized with role={default_role_name}, "
                    f"duration={session_duration}s, caching={enable_caching}")
    
    def _validate_configuration(self) -> None:
        """Validate the configuration parameters."""
        if not self.default_role_name or len(self.default_role_name) > 64:
            raise ValueError(f"Invalid default_role_name: {self.default_role_name}")
        
        if not (900 <= self.session_duration <= 43200):  # AWS limits
            raise ValueError(f"session_duration must be between 900 and 43200 seconds, got {self.session_duration}")
        
        if not self.session_name_prefix or len(self.session_name_prefix) > 32:
            raise ValueError(f"Invalid session_name_prefix: {self.session_name_prefix}")
    
    def _validate_inputs(self, account_id: str, region_name: str, role_name: Optional[str] = None) -> None:
        """
        Validate input parameters.
        
        Args:
            account_id: AWS account ID to validate
            region_name: AWS region name to validate
            role_name: Optional role name to validate
            
        Raises:
            ValueError: If any input is invalid
        """
        # Validate account ID
        if not account_id or not isinstance(account_id, str):
            raise ValueError(f"account_id must be a non-empty string, got: {account_id}")
        
        if not self.ACCOUNT_ID_PATTERN.match(account_id):
            raise ValueError(f"account_id must be a 12-digit string, got: {account_id}")
        
        # Validate region
        if not region_name or not isinstance(region_name, str):
            raise ValueError(f"region_name must be a non-empty string, got: {region_name}")
        
        # For regions, we'll be flexible but log if it's not in our known list
        if region_name not in self.VALID_REGIONS:
            logger.warning(f"Using potentially invalid region: {region_name}")
        
        # Validate role name if provided
        if role_name is not None:
            if not role_name or len(role_name) > 64:
                raise ValueError(f"role_name must be non-empty and max 64 chars, got: {role_name}")
    
    def _generate_session_name(self) -> str:
        """
        Generate a unique session name for better audit trails.
        
        Returns:
            A unique session name with timestamp and UUID
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]  # Short UUID
        return f"{self.session_name_prefix}-{timestamp}-{unique_id}"
    
    def _get_sts_endpoint_url(self, region_name: str) -> str:
        """
        Get the regional STS endpoint URL.
        
        Args:
            region_name: AWS region name
            
        Returns:
            Regional STS endpoint URL
        """
        return f"https://sts.{region_name}.amazonaws.com"
    
    def _build_role_arn(self, account_id: str, role_name: str) -> str:
        """
        Build the IAM role ARN.
        
        Args:
            account_id: AWS account ID
            role_name: IAM role name
            
        Returns:
            Complete role ARN
        """
        return f"arn:aws:iam::{account_id}:role/{role_name}"
    
    def _get_cache_key(self, account_id: str, region_name: str, role_name: str) -> str:
        """
        Generate cache key for session caching.
        
        Args:
            account_id: AWS account ID
            region_name: AWS region
            role_name: IAM role name
            
        Returns:
            Cache key string
        """
        return f"{account_id}:{region_name}:{role_name}"
    
    def assume_role(self, 
                   account_id: str, 
                   region_name: str,
                   role_name: Optional[str] = None) -> boto3.Session:
        """
        Assume an IAM role and return a boto3 session.
        
        Args:
            account_id: Target AWS account ID (12-digit string)
            region_name: AWS region name
            role_name: IAM role name (uses default if not provided)
            
        Returns:
            boto3.Session configured with assumed role credentials
            
        Raises:
            AssumeRoleError: If role assumption fails
            ValueError: If input parameters are invalid
        """
        # Use default role name if not provided
        effective_role_name = role_name or self.default_role_name
        
        # Validate inputs
        try:
            self._validate_inputs(account_id, region_name, effective_role_name)
        except ValueError as e:
            raise AssumeRoleError(f"Invalid input parameters: {e}", 
                                account_id=account_id, 
                                role_name=effective_role_name,
                                region=region_name)
        
        # Check cache if enabled
        if self.enable_caching:
            cache_key = self._get_cache_key(account_id, region_name, effective_role_name)
            if cache_key in self._session_cache:
                logger.debug(f"Returning cached session for {cache_key}")
                return self._session_cache[cache_key]
        
        logger.info(f"Assuming role {effective_role_name} in account {account_id} for region {region_name}")
        
        try:
            # Create STS client with regional endpoint
            sts_endpoint = self._get_sts_endpoint_url(region_name)
            sts_client = boto3.client('sts', 
                                    region_name=region_name,
                                    endpoint_url=sts_endpoint)
            
            # Build assume role parameters
            role_arn = self._build_role_arn(account_id, effective_role_name)
            session_name = self._generate_session_name()
            
            assume_role_params = {
                'RoleArn': role_arn,
                'RoleSessionName': session_name,
                'DurationSeconds': self.session_duration
            }
            
            # Add external ID if configured
            if self.external_id:
                assume_role_params['ExternalId'] = self.external_id
            
            logger.debug(f"Calling assume_role with params: {assume_role_params}")
            
            # Assume the role
            response = sts_client.assume_role(**assume_role_params)
            credentials = response['Credentials']
            
            # Create session with assumed role credentials
            session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken']
            )
            
            # Cache session if enabled
            if self.enable_caching:
                cache_key = self._get_cache_key(account_id, region_name, effective_role_name)
                self._session_cache[cache_key] = session
                logger.debug(f"Cached session for {cache_key}")
            
            logger.info(f"Successfully assumed role {effective_role_name} in account {account_id}")
            return session
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"Failed to assume role {effective_role_name} in account {account_id}: "
                        f"{error_code} - {error_message}")
            
            raise AssumeRoleError(
                f"AWS API error during role assumption: {error_code} - {error_message}",
                account_id=account_id,
                role_name=effective_role_name,
                region=region_name,
                original_error=e
            )
            
        except NoCredentialsError as e:
            logger.error("No AWS credentials available for role assumption")
            raise AssumeRoleError(
                "No AWS credentials available. Please configure your AWS credentials.",
                account_id=account_id,
                role_name=effective_role_name,
                region=region_name,
                original_error=e
            )
            
        except Exception as e:
            logger.error(f"Unexpected error during role assumption: {e}")
            raise AssumeRoleError(
                f"Unexpected error during role assumption: {e}",
                account_id=account_id,
                role_name=effective_role_name,
                region=region_name,
                original_error=e
            )
    
    def clear_cache(self) -> None:
        """Clear the session cache."""
        self._session_cache.clear()
        logger.debug("Session cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get information about the current cache state.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'enabled': self.enable_caching,
            'size': len(self._session_cache),
            'keys': list(self._session_cache.keys()) if self.enable_caching else []
        }


# Backwards compatibility function
def assume_role_and_create_session(account_id: str, region_name: str) -> boto3.Session:
    """
    Backwards compatible function for the original implementation.
    
    This function maintains compatibility with existing code while using
    the improved implementation under the hood.
    
    Args:
        account_id: AWS account ID
        region_name: AWS region name
        
    Returns:
        boto3.Session with assumed role credentials
    """
    logger.warning("Using legacy assume_role_and_create_session function. "
                  "Consider migrating to AssumeRoleSessionManager for better features.")
    
    # Use the new implementation with default settings for backwards compatibility
    manager = AssumeRoleSessionManager()
    return manager.assume_role(account_id, region_name)


# Legacy alias for backwards compatibility
create_assumed_role_session = assume_role_and_create_session
