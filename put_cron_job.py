import boto3

encoding   = 'utf-8'
ssm_client = boto3.client("ssm")

def put_cron_job(pod_name, instance_id, asg_name, region):
    """
    put a cron job that checks for certain pods on the node, and not find terminates it
    :param  string pod_name     : the name of the pod that will be checked whether it exists on the node or not
    :param  string instance_id  : The ID of an instance that is planned to be terminated by the ASG
    :return boolean stdout      : the stdout of the running command
    """

    print("Setting up the cron job on the node {}".format(instance_id))

    # for more ssm documents https://eu-west-2.console.aws.amazon.com/systems-manager/documents?region=eu-west-2
    # ssm runs the commands as the root user
    ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={
          "commands": [
            """
            cat << EOF > check_pod_and_shutdown.sh
            #!/bin/bash
            runnings_pods=\$(docker ps --format \'{docker_format}\' -f name={pod_name})
            if [ -n \"\$runnings_pods\" ]; then
                echo "{pod_name} pods are still running" >> /tmp/cron.log
            else
                echo "the instance will be terminated" >> /tmp/cron.log
                aws autoscaling complete-lifecycle-action --region={region} \\
                --lifecycle-hook-name {lifecycle_hook_name} \\
                --auto-scaling-group-name {asg_name} \\
                --lifecycle-action-result CONTINUE \\
                --instance-id {instance_id}

            fi
            """.format(docker_format='{{.Names}}',pod_name = pod_name, asg_name = asg_name, lifecycle_hook_name = "Terminate-LC-Hook", instance_id = instance_id, region = region)],
            "workingDirectory": ["/tmp"]
        }
    )

    ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={
          "commands": [
            'chmod +x /tmp/check_pod_and_shutdown.sh']
        }
    )

    ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={
          "commands": [
            'crontab -l ; echo "*/2 * * * * /tmp/check_pod_and_shutdown.sh" | crontab - ']
        }
    )

    print("cron job created")

    return True
