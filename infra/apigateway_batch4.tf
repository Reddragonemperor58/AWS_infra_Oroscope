# Routes for the DL photo upload and "Report a problem" endpoints. API Gateway forwards only
# declared routes; app/tests/test_gateway_routes.py fails if one is missing.
resource "aws_apigatewayv2_route" "dl_upload_url" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /diagnoses/{diagnosis_id}/dl-upload-url"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "problem_reports" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "POST /problem-reports"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
