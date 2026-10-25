# Routes for the account, activity and export endpoints (app/records.py). API Gateway only forwards
# routes that are declared here; anything else gets a 404 with no CORS headers, which the browser
# reports as "Cannot reach the server". app/tests/test_gateway_routes.py fails if a route is missing.
resource "aws_apigatewayv2_route" "me_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /me"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "me_activity" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /me/activity"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "patient_export" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /patients/{patient_id}/export"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
