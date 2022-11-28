import boto3
import time

encoding   = 'utf-8'
ssm_client = boto3.client("ssm")

def check_pods(pod_name, instance_id):
  """
  check some certain pods on the given worker node
  :param  string pod_name     : the name of the pod that will be checked whether it exists on the node or not
  :param  string instance_id  : the ID of an instance that is planned to be terminated by the ASG
  :return boolean stdout      : the stdout of the running command
  """

  print("Controlling pods with the name {} whether they are running on the node".format(pod_name))

  response = ssm_client.send_command(
      InstanceIds=[instance_id],
      DocumentName="AWS-RunShellScript",
      Parameters={
        "commands": ["docker ps --format '{docker_format}' -f name={pod_name}".format(docker_format='{{.Names}}', pod_name = pod_name)]
      }
  )

  # fetching command output
  time.sleep(3)
  output = ssm_client.get_command_invocation(CommandId=response["Command"]["CommandId"], InstanceId=instance_id)

  print("docker ps command output: {}".format(output["StandardOutputContent"]))

  return output["StandardOutputContent"]
