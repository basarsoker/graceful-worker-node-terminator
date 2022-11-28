from asyncio import events
import base64
import json
import boto3
from botocore.exceptions import ClientError
import re
import os
from botocore.signers import RequestSigner
from kubernetes import client, config
import urllib3
from check_pods import check_pods
from put_cron_job import put_cron_job

# body payload to cordon a node
cordon_node_payload = {
    "spec": {
        "unschedulable": True
    }
}

urllib3.disable_warnings()

def get_bearer_token(cluster_id, region):
    STS_TOKEN_EXPIRES_IN = 60
    session = boto3.session.Session()

    client = session.client('sts', region_name=region)
    service_id = client.meta.service_model.service_id

    signer = RequestSigner(
        service_id,
        region,
        'sts',
        'v4',
        session.get_credentials(),
        session.events
    )

    params = {
        'method': 'GET',
        'url': 'https://sts.{}.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15'.format(region),
        'body': {},
        'headers': {
            'x-k8s-aws-id': cluster_id
        },
        'context': {}
    }

    signed_url = signer.generate_presigned_url(
        params,
        region_name=region,
        expires_in=STS_TOKEN_EXPIRES_IN,
        operation_name=''
    )
    base64_url = base64.urlsafe_b64encode(signed_url.encode('utf-8')).decode('utf-8')
    # remove any base64 encoding padding:
    return 'k8s-aws-v1.' + re.sub(r'=*', '', base64_url)
    # If making a HTTP request you would create the authorization headers as follows:
    # headers = {'Authorization': 'Bearer ' + get_bearer_token('my_cluster', 'us-east-1')}


def cordon_node(client, instance_id):
    """
    cordon the worker node if it hadn't been cordoned before
    :param string instance_id: The ID of an instance that is planned to be shut down by the ASG
    :param object client: The Kubernetes python client talking to the cluster
    :return:
    """
    node_list = client.list_node(watch=False).items
    if len(node_list) > 0 :
      for i in node_list:
        if instance_id in i.spec.provider_id:
          if i.spec.unschedulable:
              print("{} worker node has ALREADY been cordoned".format(i.metadata.name))
          else:
            client.patch_node(i.metadata.name, cordon_node_payload)
            print("{} worker node has been cordoned".format(i.metadata.name))

          return i.metadata.name
    else:
      print("There isn't any node in the cluster")


def lambda_handler(event, context):
    """
    :param object event: The event that is sent by ASG
    :return:
    """
    # the name of the pod that is checked on the worker node
    # it doesn't have to be the full name, you may assign a substring of the name
    pod_name_substring = os.environ['POD_NAME']

    # extract the instance id
    sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
    instance_id = sns_message["EC2InstanceId"]
    asg_name    = sns_message["AutoScalingGroupName"]

    # check instance status, if it has already been terminated that means AWS had taken the instance due the spot price
    ec2_client = boto3.client('ec2')
    instance_status = ec2_client.describe_instance_status(
        InstanceIds=[
            instance_id
        ]
    )

    print("event")
    print(event)

    print("instance_id")
    print(instance_id)

    print("instance_status")
    print(instance_status)

    if len(instance_status["InstanceStatuses"]) < 1:
        print ({"{} had been taken by AWS due to the spot policy".format(instance_id)})
        return False

    #create k8s python client
    ApiToken = get_bearer_token(os.environ['CLUSTER_NAME'], os.environ['CLUSTER_REGION'])
    configuration = client.Configuration()
    configuration.host = os.environ['CLUSTER_ENDPOINT']
    configuration.verify_ssl = False
    configuration.debug = False
    configuration.api_key = {"authorization": "Bearer " + ApiToken}
    client.Configuration.set_default(configuration)
    core_v1_api_client = client.CoreV1Api()

    print("cordon the node")
    node_name = cordon_node(core_v1_api_client, instance_id)

    print("check for certains pods")
    pods = check_pods(pod_name_substring, instance_id)

    #delete and terminate the node if the pods are not running on the node
    asg_client = boto3.client('autoscaling')

    if pods == "":
        try:
            print("{} node is being deleted from the cluster".format(node_name))
            core_v1_api_client.delete_node(node_name)
            print("{} node is being terminated".format(node_name))
            asg_client.complete_lifecycle_action(
                AutoScalingGroupName  =  asg_name,
                LifecycleActionResult = 'CONTINUE',
                InstanceId            =  instance_id,
                # the LifecycleHookName vary in your case, please check the "autoscaling:EC2_INSTANCE_TERMINATING" signal sender lifecycle hook of your ASG
                LifecycleHookName     = 'Terminate-LC-Hook'
            )
            print("{} node has been deleted from the cluster and terminated".format(node_name))
        except ClientError as e:
            print("Exception when trying to delete and terminate the instance: {}".format(e))
    else:
        # set cron job that will terminate the instance once the pod stopped
        print("{} pod is still running on {} node. Thus the node will not be terminated for now. A cron job has been set and shall terminate the instance".format(pod_name_substring, node_name))
        put_cron_job(pod_name_substring, instance_id, asg_name, os.environ['CLUSTER_REGION'])
