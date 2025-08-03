"""
EC2 instance information retrieval module.

This module provides functionality to display detailed information
about EC2 instances by their name tag across multiple AWS accounts.
"""

import logging
from typing import Dict, Any
from tabulate import tabulate

from ec2.find import find_instance_by_name
from load_config import get_aws_accounts

logger = logging.getLogger('aws-automation-tamer.ec2.info')


def format_instance_info(instance_data: Dict[str, Any], account_name: str, region: str) -> str:
    """
    Format EC2 instance information into a readable table.
    
    Args:
        instance_data: EC2 instance data from AWS API
        account_name: Name of the AWS account
        region: AWS region name
        
    Returns:
        Formatted table string
    """
    # Extract basic instance information
    instance_id = instance_data.get('InstanceId', 'N/A')
    instance_type = instance_data.get('InstanceType', 'N/A')
    state = instance_data.get('State', {}).get('Name', 'N/A')
    launch_time = instance_data.get('LaunchTime', 'N/A')
    if launch_time != 'N/A':
        launch_time = launch_time.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # Network information
    vpc_id = instance_data.get('VpcId', 'N/A')
    subnet_id = instance_data.get('SubnetId', 'N/A')
    availability_zone = instance_data.get('Placement', {}).get('AvailabilityZone', 'N/A')
    private_ip = instance_data.get('PrivateIpAddress', 'N/A')
    public_ip = instance_data.get('PublicIpAddress', 'N/A')
    
    # Security groups
    security_groups = []
    for sg in instance_data.get('SecurityGroups', []):
        security_groups.append(f"{sg['GroupName']} ({sg['GroupId']})")
    security_groups_str = ', '.join(security_groups) if security_groups else 'N/A'
    
    # Tags
    tags = {}
    for tag in instance_data.get('Tags', []):
        tags[tag['Key']] = tag['Value']
    
    # Key pair
    key_name = instance_data.get('KeyName', 'N/A')
    
    # Root device information
    root_device_name = instance_data.get('RootDeviceName', 'N/A')
    root_device_type = instance_data.get('RootDeviceType', 'N/A')
    
    # Block device mappings
    block_devices = []
    for bdm in instance_data.get('BlockDeviceMappings', []):
        device_name = bdm.get('DeviceName', 'N/A')
        if 'Ebs' in bdm:
            volume_id = bdm['Ebs'].get('VolumeId', 'N/A')
            volume_size = 'N/A'  # We'd need to query the volume for size
            block_devices.append(f"{device_name}: {volume_id}")
    block_devices_str = ', '.join(block_devices) if block_devices else 'N/A'
    
    # Monitoring
    monitoring = instance_data.get('Monitoring', {}).get('State', 'N/A')
    
    # Platform details
    platform = instance_data.get('Platform', 'Linux/Unix')
    architecture = instance_data.get('Architecture', 'N/A')
    
    # Build the table data
    table_data = [
        ['Account', account_name],
        ['Region', region],
        ['Availability Zone', availability_zone],
        ['Instance ID', instance_id],
        ['Instance Type', instance_type],
        ['State', state.upper()],
        ['Launch Time', launch_time],
        ['Platform', platform],
        ['Architecture', architecture],
        ['VPC ID', vpc_id],
        ['Subnet ID', subnet_id],
        ['Private IP', private_ip],
        ['Public IP', public_ip],
        ['Key Pair', key_name],
        ['Security Groups', security_groups_str],
        ['Root Device', f"{root_device_name} ({root_device_type})"],
        ['Block Devices', block_devices_str],
        ['Monitoring', monitoring],
    ]
    
    # Add important tags
    important_tags = ['Name', 'Environment', 'Project', 'Owner', 'CostCenter']
    for tag_key in important_tags:
        if tag_key in tags:
            table_data.append([f'Tag: {tag_key}', tags[tag_key]])
    
    # Add other tags if there are any not covered above
    other_tags = []
    for key, value in tags.items():
        if key not in important_tags:
            other_tags.append(f"{key}={value}")
    
    if other_tags:
        table_data.append(['Other Tags', ', '.join(other_tags)])
    
    # Create the table
    headers = ['Property', 'Value']
    table = tabulate(table_data, headers=headers, tablefmt='grid', maxcolwidths=[25, 50])
    
    return table


def get_instance_info(server_name: str, config: Dict[str, Any]) -> None:
    """
    Find and display detailed information about an EC2 instance.
    
    Args:
        server_name: The name tag value to search for
        config: Configuration dictionary containing AWS accounts
    """
    logger.info(f"Getting instance info for: {server_name}")
    
    print(f"🔍 Searching for EC2 instance: {server_name}")
    print("   Checking all configured accounts and regions...")
    
    try:
        result = find_instance_by_name(server_name, config)
        
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
            
            return
        
        account_name, region, instance_data = result
        
        print(f"\n✅ Found EC2 instance: {server_name}")
        print(f"   Located in account: {account_name}, region: {region}")
        print()
        
        # Display detailed information in table format
        table = format_instance_info(instance_data, account_name, region)
        print(table)
        
        logger.info(f"Successfully displayed info for instance {instance_data.get('InstanceId')} in {account_name}")
        
    except Exception as e:
        logger.error(f"Error getting instance info: {e}", exc_info=True)
        print(f"\n❌ Error getting instance information: {str(e)}")
        raise
