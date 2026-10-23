# Routes for the record-keeping endpoints (app/records.py). GET /patients already exists in
# apigateway.tf and now served by the same Lambda with search and paging.
resource "aws_apigatewayv2_route" "patient_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /patients/{patient_id}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "patient_update" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "PATCH /patients/{patient_id}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "patient_diagnoses" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /patients/{patient_id}/diagnoses"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_route" "diagnosis_get" {
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = "GET /diagnoses/{diagnosis_id}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}
