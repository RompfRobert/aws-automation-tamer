"""
EC2 instance finding module.

This module provides reusable functionality to find EC2 instances by their name tag
across multiple AWS accounts and regions.
"""

import logging
from typing import Dict, Any, Optional, Tuple

from libs.aws_session_manager import AssumeRoleSessionManager, AssumeRoleError
from load_config import get_aws_accounts, get_valid_regions
from botocore.exceptions import ClientError

logger = logging.getLogger('aws-automation-tamer.ec2.find')


def find_instance_by_name(server_name: str, config: Dict[str, Any]) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """
    Find an EC2 instance by name tag across all configured accounts.
    
    Args:
        server_name: The name tag value to search for
        config: Configuration dictionary containing AWS accounts
        
    Returns:
        Tuple of (account_name, region, instance_data) if found, None otherwise
        
    Raises:
        AssumeRoleError: If unable to assume role in any account
    """
    logger.info(f"Searching for instance with name tag: {server_name}")
    
    accounts = get_aws_accounts(config)
    valid_regions = get_valid_regions(config)
    session_manager = AssumeRoleSessionManager()
    
    logger.info(f"Searching across {len(accounts)} accounts in {len(valid_regions)} configured regions: {', '.join(valid_regions)}")
    
    # Search through all accounts
    for account_name, account_id in accounts.items():
        logger.debug(f"Searching in account: {account_name} ({account_id})")
        
        try:
            # Search in each configured region
            for region in valid_regions:
                logger.debug(f"Searching in account {account_name}, region: {region}")
                
                try:
                    # Create EC2 client for this specific region
                    regional_session = session_manager.assume_role(account_id, region)
                    ec2 = regional_session.client('ec2')
                    
                    # Search for instances with the specified name tag
                    response = ec2.describe_instances(
                        Filters=[
                            {
                                'Name': 'tag:Name',
                                'Values': [server_name]
                            },
                            {
                                'Name': 'instance-state-name',
                                'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']
                            }
                        ]
                    )
                    
                    # Check if any instances were found
                    for reservation in response['Reservations']:
                        for instance in reservation['Instances']:
                            # Double-check the actual region from the availability zone
                            actual_az = instance.get('Placement', {}).get('AvailabilityZone', '')
                            if actual_az:
                                # Extract region from AZ (e.g., 'eu-central-1a' -> 'eu-central-1')
                                actual_region = actual_az[:-1] if actual_az[-1].isalpha() else region
                                logger.info(f"Found instance {instance['InstanceId']} in account {account_name}, region {actual_region} (AZ: {actual_az})")
                                return account_name, actual_region, instance
                            else:
                                logger.info(f"Found instance {instance['InstanceId']} in account {account_name}, region {region}")
                                return account_name, region, instance
                            
                except ClientError as e:
                    # Log but continue - some regions might not be accessible
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    if error_code not in ['UnauthorizedOperation', 'OptInRequired']:
                        logger.warning(f"Error searching in region {region}: {error_code}")
                    continue
                    
        except AssumeRoleError as e:
            logger.error(f"Failed to assume role in account {account_name}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error in account {account_name}: {e}")
            continue
    
    logger.info(f"Instance '{server_name}' not found in any configured account")
    return None


def find_instance_with_session(server_name: str, config: Dict[str, Any]) -> Optional[Tuple[str, str, Dict[str, Any], Any]]:
    """
    Find an EC2 instance by name tag and return both instance data and the boto3 session.
    
    This is useful when you need to perform operations on the instance after finding it.
    
    Args:
        server_name: The name tag value to search for
        config: Configuration dictionary containing AWS accounts
        
    Returns:
        Tuple of (account_name, region, instance_data, ec2_client) if found, None otherwise
        
    Raises:
        AssumeRoleError: If unable to assume role in any account
    """
    logger.info(f"Searching for instance with session: {server_name}")
    
    accounts = get_aws_accounts(config)
    valid_regions = get_valid_regions(config)
    session_manager = AssumeRoleSessionManager()
    
    logger.info(f"Searching across {len(accounts)} accounts in {len(valid_regions)} configured regions: {', '.join(valid_regions)}")
    
    # Search through all accounts
    for account_name, account_id in accounts.items():
        logger.debug(f"Searching in account: {account_name} ({account_id})")
        
        try:
            # Search in each configured region
            for region in valid_regions:
                logger.debug(f"Searching in account {account_name}, region: {region}")
                
                try:
                    # Create EC2 client for this specific region
                    regional_session = session_manager.assume_role(account_id, region)
                    ec2 = regional_session.client('ec2')
                    
                    # Search for instances with the specified name tag
                    response = ec2.describe_instances(
                        Filters=[
                            {
                                'Name': 'tag:Name',
                                'Values': [server_name]
                            },
                            {
                                'Name': 'instance-state-name',
                                'Values': ['pending', 'running', 'shutting-down', 'stopping', 'stopped']
                            }
                        ]
                    )
                    
                    # Check if any instances were found
                    for reservation in response['Reservations']:
                        for instance in reservation['Instances']:
                            # Double-check the actual region from the availability zone
                            actual_az = instance.get('Placement', {}).get('AvailabilityZone', '')
                            if actual_az:
                                # Extract region from AZ (e.g., 'eu-central-1a' -> 'eu-central-1')
                                actual_region = actual_az[:-1] if actual_az[-1].isalpha() else region
                                logger.info(f"Found instance {instance['InstanceId']} in account {account_name}, region {actual_region} (AZ: {actual_az})")
                                return account_name, actual_region, instance, ec2
                            else:
                                logger.info(f"Found instance {instance['InstanceId']} in account {account_name}, region {region}")
                                return account_name, region, instance, ec2
                            
                except ClientError as e:
                    # Log but continue - some regions might not be accessible
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    if error_code not in ['UnauthorizedOperation', 'OptInRequired']:
                        logger.warning(f"Error searching in region {region}: {error_code}")
                    continue
                    
        except AssumeRoleError as e:
            logger.error(f"Failed to assume role in account {account_name}: {e}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error in account {account_name}: {e}")
            continue
    
    logger.info(f"Instance '{server_name}' not found in any configured account")
    return None
