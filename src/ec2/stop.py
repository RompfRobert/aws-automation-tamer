"""
EC2 instance stopping module.

This module provides functionality to stop EC2 instances by their name tag
across multiple AWS accounts.
"""

import logging
from typing import Dict, Any
from botocore.exceptions import ClientError

from ec2.find import find_instance_with_session
from load_config import get_aws_accounts
from libs.get_confirmation import get_confirmation

logger = logging.getLogger('aws-automation-tamer.ec2.stop')


def stop_instance_by_name(server_name: str, config: Dict[str, Any], 
                         wait: bool = False, dry_run: bool = False, 
                         auto_confirm: bool = False) -> bool:
    """
    Stop an EC2 instance by finding it across all configured accounts.
    
    Args:
        server_name: The name tag value to search for
        config: Configuration dictionary containing AWS accounts
        wait: If True, wait for the instance to fully stop before returning
        dry_run: If True, perform a dry-run without stopping the instance
        auto_confirm: If True, skip confirmation prompts
        
    Returns:
        bool: True if the instance stop was successful or unnecessary, False otherwise
    """
    logger.info(f"Attempting to stop instance: {server_name}")
    
    print(f"🔍 Searching for EC2 instance: {server_name}")
    print("   Checking all configured accounts and regions...")
    
    try:
        result = find_instance_with_session(server_name, config)
        
        if result is None:
            print(f"\n❌ No EC2 instance found with name tag: {server_name}")
            print("   Checked all configured accounts and regions.")
            
            # Show which accounts were checked
            accounts = get_aws_accounts(config)
            if accounts:
                print(f"\n📋 Accounts checked:")
                for account_name, account_id in accounts.items():
                    print(f"   • {account_name} ({account_id})")
            else:
                print("\n⚠️  No AWS accounts configured. Run 'aat configure' to set up accounts.")
            
            return False
        
        account_name, region, instance_data, ec2_client = result
        instance_id = instance_data.get('InstanceId')
        
        if not instance_id:
            print(f"\n❌ Instance data is missing Instance ID")
            logger.error(f"Instance data is missing Instance ID for {server_name}")
            return False
            
        instance_state = instance_data.get('State', {}).get('Name', 'unknown')
        
        print(f"\n✅ Found EC2 instance: {server_name}")
        print(f"   Located in account: {account_name}, region: {region}")
        print(f"   Instance ID: {instance_id}")
        print(f"   Current state: {instance_state.upper()}")
        
        # Check current state
        if instance_state == 'stopped':
            print(f"\n✅ Instance {server_name} ({instance_id}) is already stopped.")
            logger.info(f"Instance {server_name} ({instance_id}) is already stopped.")
            return True
        elif instance_state == 'stopping':
            print(f"\n⏳ Instance {server_name} ({instance_id}) is already stopping.")
            if wait:
                print("   Waiting for instance to fully stop...")
                return _wait_for_instance_stopped(ec2_client, instance_id, server_name)
            logger.info(f"Instance {server_name} ({instance_id}) is already stopping.")
            return True
        elif instance_state not in ['running', 'pending']:
            print(f"\n⚠️  Instance {server_name} ({instance_id}) is in '{instance_state}' state and cannot be stopped.")
            logger.warning(f"Instance {server_name} ({instance_id}) is in '{instance_state}' state and cannot be stopped.")
            return False
        
        # Instance is running or pending, proceed with stop
        if dry_run:
            print(f"\n🔍 DRY RUN: Would stop instance {server_name} ({instance_id})")
            print("   No actual changes will be made.")
            logger.info(f"DRY RUN: Would stop instance {server_name} ({instance_id}).")
            return True
        
        # Ask for confirmation unless auto-confirm is enabled
        if not auto_confirm:
            print(f"\n⚠️  This will stop the EC2 instance:")
            print(f"   Instance: {server_name} ({instance_id})")
            print(f"   Account: {account_name}")
            print(f"   Region: {region}")
            
            if not get_confirmation("Are you sure you want to stop this instance?"):
                print("❌ Operation cancelled.")
                logger.info(f"Stop operation cancelled for instance {server_name} ({instance_id}).")
                return False
        
        # Stop the instance
        print(f"\n🛑 Stopping instance {server_name} ({instance_id})...")
        logger.info(f"Stopping instance {server_name} ({instance_id}) in account {account_name}, region {region}.")
        
        try:
            response = ec2_client.stop_instances(InstanceIds=[instance_id])
            logger.debug(f"Stop request sent for instance {server_name} ({instance_id}). Response: {response}")
            
            print(f"✅ Stop request sent successfully for instance {server_name} ({instance_id})")
            
            if wait:
                print("⏳ Waiting for instance to fully stop...")
                return _wait_for_instance_stopped(ec2_client, instance_id, server_name)
            else:
                print("   Use --wait option to wait for the instance to fully stop.")
                return True
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            print(f"\n❌ Failed to stop instance {server_name} ({instance_id})")
            print(f"   Error: {error_code} - {error_message}")
            logger.error(f"Failed to stop instance {server_name} ({instance_id}): {error_code} - {error_message}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error stopping instance {server_name} ({instance_id}): {str(e)}")
            logger.error(f"Unexpected error stopping instance {server_name} ({instance_id}): {e}", exc_info=True)
            return False
            
    except Exception as e:
        print(f"\n❌ Error finding or stopping instance: {str(e)}")
        logger.error(f"Error in stop_instance_by_name for {server_name}: {e}", exc_info=True)
        return False


def _wait_for_instance_stopped(ec2_client, instance_id: str, server_name: str) -> bool:
    """
    Wait for an EC2 instance to reach the 'stopped' state.
    
    Args:
        ec2_client: boto3 EC2 client
        instance_id: EC2 instance ID
        server_name: Server name for logging
        
    Returns:
        bool: True if instance stopped successfully, False if timeout or error
    """
    try:
        waiter = ec2_client.get_waiter('instance_stopped')
        waiter.wait(
            InstanceIds=[instance_id],
            WaiterConfig={
                'Delay': 15,  # Check every 15 seconds
                'MaxAttempts': 40  # Wait up to 10 minutes (40 * 15 seconds)
            }
        )
        print(f"✅ Instance {server_name} ({instance_id}) has fully stopped.")
        logger.info(f"Instance {server_name} ({instance_id}) has fully stopped.")
        return True
        
    except Exception as e:
        print(f"❌ Timeout or error waiting for instance {server_name} ({instance_id}) to stop: {str(e)}")
        logger.error(f"Error waiting for instance {server_name} ({instance_id}) to stop: {e}")
        return False


# Legacy function for backwards compatibility
def stop_instance(ec2_client, instance_details: Dict[str, Any], server_name: str, 
                 wait: bool = False, dry_run: bool = False, confirm: bool = True) -> bool:
    """
    Legacy function - stop an EC2 instance given its details.
    
    This function is kept for backwards compatibility. New code should use stop_instance_by_name.
    """
    logger.warning("Using legacy stop_instance function. Consider migrating to stop_instance_by_name.")
    
    instance_id = instance_details.get('InstanceId')
    if not instance_id:
        logger.error("InstanceId not found in instance details.")
        return False

    instance_state = instance_details.get('State', {}).get('Name', '')
    try:
        if instance_state == 'running':
            if dry_run:
                logger.info(f"DRY RUN: Would stop instance {server_name} ({instance_id}).")
                return True
            else:
                # Ask for confirmation if required
                if confirm and not get_confirmation(f"Stop instance {server_name} ({instance_id})?"):
                    logger.info(f"Operation cancelled for instance {server_name} ({instance_id}).")
                    return False
                
                logger.info(f"Stopping instance {server_name} ({instance_id}).")
                response = ec2_client.stop_instances(InstanceIds=[instance_id])
                logger.debug(f"Stop request sent for instance {server_name} ({instance_id}). Response: {response}")
                
                if wait:
                    logger.info(f"Waiting for instance {server_name} ({instance_id}) to reach 'stopped' state...")
                    waiter = ec2_client.get_waiter('instance_stopped')
                    waiter.wait(InstanceIds=[instance_id])
                    logger.info(f"Instance {server_name} ({instance_id}) has fully stopped.")
                return True
        elif instance_state == 'stopped':
            logger.info(f"Instance {server_name} ({instance_id}) is already stopped.")
            return True
        else:
            logger.info(f"Instance {server_name} ({instance_id}) is in '{instance_state}' state and cannot be stopped.")
            return False
    except Exception as e:
        logger.error(f"Error stopping instance {server_name} ({instance_id}): {e}", exc_info=True)
        return False