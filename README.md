# gracefully-worker-terminator Lambda Function

This is a Lambda function to gracefully shutdown worker nodes in a K8s cluster.

It listens to an SNS topic, which is connected to the "autoscaling:EC2_INSTANCE_TERMINATING" signal sender lifecycle hook of an ASG.

These are the steps that this function takes whenever it receives a message from the connected SNS topic:

1 - Checks whether the node is alive, if it is not, that means AWS took the node as per the spot instance policy. In this case, terminates the execution

2 - Cordons the node

3 - Checks for the certain pods on the worker node. (Which pods will be checked can be defined inside the function)

4 - If one of those pods is running on the node, it puts a cron job inside the node, which controls the pods on the node, once pods die it gives a signal back to the ASG to proceed to terminate the node

5 - If none of those pods is running on the node, it gives a signal back to the ASG to proceed to terminate the node

## Architecture

![graceful-worker-node-shutdown drawio](https://user-images.githubusercontent.com/95694204/204337627-81693113-c7a0-43ed-b795-c25e485d1562.png)

1 - The auto-scaling dynamic policy decides to terminate the node, this activates its node termination signal lifecycle hook,

2 - The lifecycle hook send a message to an SNS topic and starts to wait within its timeout period,

3 - The SNS topic conveys the message to the Lambda function.


## Used libraries and documents

This is a part of this Medium page. For the comprehensive explanation you may check it.




It utilizes Python kubernetes-client to run kubernetes commands. For all available actions via this library:

https://github.com/kubernetes-client/python/blob/master/kubernetes/README.md


For the explanation of these actions:

https://k8s-python.readthedocs.io/en/stable/genindex.html



For a beginner guide:

https://www.velotio.com/engineering-blog/kubernetes-python-client



For an example usage of the client over EKS

https://github.com/pahud/eks-lambda-py/tree/master/functions/ListPods
https://github.com/pahud/eks-lambda-py/blob/master/functions/ListPods/fn/app.py
