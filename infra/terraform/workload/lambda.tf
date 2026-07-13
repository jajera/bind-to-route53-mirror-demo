data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.common_tags
}

data "aws_iam_policy_document" "lambda" {
  statement {
    actions   = ["route53:ListResourceRecordSets", "route53:ChangeResourceRecordSets"]
    resources = ["arn:aws:route53:::hostedzone/${aws_route53_zone.private.zone_id}"]
  }

  statement {
    actions = [
      "ec2:CreateNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DeleteNetworkInterface",
    ]
    resources = ["*"]
  }

  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:${var.aws_region}:*:*"]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${var.project_name}-lambda"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_security_group" "lambda" {
  name        = "${var.project_name}-lambda"
  description = "Sync Lambda"
  vpc_id      = aws_vpc.workload.id

  egress {
    description = "AXFR to BIND (on-prem account via VPN)"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = [local.bind_subnet_cidr]
  }

  egress {
    description = "Route 53 API via NAT gateway"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../../../dist/lambda"
  output_path = "${path.module}/../../../dist/lambda.zip"
}

resource "aws_lambda_function" "sync" {
  function_name    = "${var.project_name}-sync"
  role             = aws_iam_role.lambda.arn
  handler          = "zone_sync.handler.lambda_handler"
  runtime          = "python3.14"
  timeout          = 300
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256

  vpc_config {
    subnet_ids         = [aws_subnet.workload_lambda.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_event_rule" "sync" {
  name                = "${var.project_name}-sync"
  schedule_expression = "rate(${var.sync_interval_minutes} minutes)"
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_target" "sync" {
  rule      = aws_cloudwatch_event_rule.sync.name
  target_id = "sync-lambda"
  arn       = aws_lambda_function.sync.arn

  input = jsonencode({
    Domain    = var.domain_name
    MasterDns = data.terraform_remote_state.onprem.outputs.bind_private_ip
    ZoneId    = aws_route53_zone.private.zone_id
    IgnoreTTL = var.ignore_ttl
  })
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sync.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.sync.arn
}

resource "aws_cloudwatch_metric_alarm" "sync_errors" {
  alarm_name          = "${var.project_name}-sync-errors"
  alarm_description   = "BIND to Route53 sync Lambda reported one or more errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.sync.function_name
  }

  tags = local.common_tags
}
