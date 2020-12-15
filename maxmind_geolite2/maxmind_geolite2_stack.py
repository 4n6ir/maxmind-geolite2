from aws_cdk import (
    aws_events as _events,
    aws_events_targets as _targets,
    aws_iam as _iam,
    aws_lambda as _lambda,
    aws_logs as _logs,
    aws_s3 as _s3,
    aws_s3_deployment as _deployment,
    aws_ssm as _ssm,
    core
)

#
# https://dev.maxmind.com/geoip/geoip2/geolite2/
#
maxmind_api_key_secure_ssm_parameter = '/maxmind/geolite2'


class MaxmindGeolite2Stack(core.Stack):

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = _s3.Bucket(
            self, 'download',
            encryption=_s3.BucketEncryption.S3_MANAGED,
            block_public_access=_s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=core.RemovalPolicy.DESTROY
        )

        _deployment.BucketDeployment(
            self, 'DeployFunctionFile',
            sources=[_deployment.Source.asset('code')],
            destination_bucket=bucket,
            prune=False
        )

        geoip2_layer = _lambda.LayerVersion(
            self, 'geoip2_layer',
            code=_lambda.Code.asset('layer'),
            license='Creative Commons Attribution-ShareAlike 4.0 International License',
            description='This product includes GeoLite2 data created by MaxMind, available from https://www.maxmind.com.'
        )

        search_role = _iam.Role(self, 'search_role', assumed_by=_iam.ServicePrincipal('lambda.amazonaws.com'))
        search_role.add_managed_policy(_iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole'))

        search_lambda = _lambda.Function(
            self, 'search_lambda',
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset('search'),
            handler='search.handler',
            role=search_role,
            timeout=core.Duration.seconds(30),
            layers=[geoip2_layer]
        )

        search_logs = _logs.LogGroup(
            self, 'search_logs',
            log_group_name='/aws/lambda/'+search_lambda.function_name,
            retention=_logs.RetentionDays.ONE_DAY,
            removal_policy=core.RemovalPolicy.DESTROY
        )
        
        download_role = _iam.Role(self, 'download_role', assumed_by=_iam.ServicePrincipal('lambda.amazonaws.com'))
        download_role.add_managed_policy(_iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole'))
        download_role.add_to_policy(_iam.PolicyStatement(actions=['lambda:UpdateFunctionCode','s3:GetObject','s3:PutObject','ssm:GetParameter'],resources=['*']))

        download_lambda = _lambda.Function(
            self, 'download_lambda',
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.asset('download'),
            handler='download.handler',
            role=download_role,
            timeout=core.Duration.seconds(300),
            environment=dict(
                S3_BUCKET=bucket.bucket_name,
                SSM_PARAMETER=maxmind_api_key_secure_ssm_parameter,
                LAMBDA_FUNCTION=search_lambda.function_name
            ),
            layers=[geoip2_layer],
            memory_size=256
        )

        download_logs = _logs.LogGroup(
            self, 'download_logs',
            log_group_name='/aws/lambda/'+download_lambda.function_name,
            retention=_logs.RetentionDays.ONE_DAY,
            removal_policy=core.RemovalPolicy.DESTROY
        )

        rule = _events.Rule(
            self, 'download_rule',
            schedule=_events.Schedule.cron(
                minute='0',
                hour='0',
                month='*',
                week_day='WED',
                year='*'
            )
        )
        rule.add_target(_targets.LambdaFunction(download_lambda))
