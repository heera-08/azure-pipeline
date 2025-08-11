import azure.functions as func
import json
import logging
from swarm import validate_jenkins_file, convert_to_yaml, validate_yaml_content, evaluate_conversion

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the Azure Functions app
app = func.FunctionApp()

# CORS settings for Azure Web App
def add_cors_headers(response):
    """Add CORS headers to response"""
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

@app.route(route="validate-jenkins", methods=["POST", "OPTIONS"])
def validate_jenkins(req: func.HttpRequest) -> func.HttpResponse:
    """Validate Jenkins file - matches FileValidationAgent frontend call"""
    
    # Handle CORS preflight
    if req.method == "OPTIONS":
        response = func.HttpResponse("", status_code=200)
        return add_cors_headers(response)
    
    try:
        logger.info("Received Jenkins validation request")
        
        # Parse request body
        req_body = req.get_json()
        if not req_body:
            raise ValueError("Request body is empty")
        
        # Extract file data (matching frontend structure)
        file_data = {
            'name': req_body.get('name', ''),
            'content': req_body.get('content', ''),
            'size': req_body.get('size', 0)
        }
        
        if not file_data['content']:
            return add_cors_headers(func.HttpResponse(
                json.dumps({
                    "isValid": False,
                    "errors": ["File content is empty"],
                    "warnings": []
                }),
                status_code=400,
                mimetype="application/json"
            ))
        
        # Validate using swarm
        result = validate_jenkins_file(file_data)
        
        logger.info(f"Jenkins validation result: {result}")
        
        # Return response matching frontend expectations
        response = func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        return add_cors_headers(response)
        
    except Exception as e:
        logger.error(f"Jenkins validation error: {str(e)}")
        error_response = func.HttpResponse(
            json.dumps({
                "isValid": False,
                "errors": [f"Validation service error: {str(e)}"],
                "warnings": []
            }),
            status_code=500,
            mimetype="application/json"
        )
        return add_cors_headers(error_response)

@app.route(route="convert-to-yaml", methods=["POST", "OPTIONS"])
def convert_jenkins_to_yaml(req: func.HttpRequest) -> func.HttpResponse:
    """Convert Jenkins to Azure DevOps YAML - matches LLMConversionAgent frontend call"""
    
    # Handle CORS preflight
    if req.method == "OPTIONS":
        response = func.HttpResponse("", status_code=200)
        return add_cors_headers(response)
    
    try:
        logger.info("Received YAML conversion request")
        
        # Parse request body
        req_body = req.get_json()
        if not req_body:
            raise ValueError("Request body is empty")
        
        file_content = req_body.get('file_content', '')
        validation_result = req_body.get('validation_result', {})
        
        if not file_content:
            return add_cors_headers(func.HttpResponse(
                json.dumps({"yaml_content": "Error: No file content provided"}),
                status_code=400,
                mimetype="application/json"
            ))
        
        if not validation_result.get('isValid', False):
            return add_cors_headers(func.HttpResponse(
                json.dumps({"yaml_content": "Error: Jenkins file is not valid"}),
                status_code=400,
                mimetype="application/json"
            ))
        
        # Convert using swarm
        yaml_content = convert_to_yaml(file_content)
        
        logger.info("YAML conversion completed")
        
        # Return response matching frontend expectations
        response = func.HttpResponse(
            json.dumps({"yaml_content": yaml_content}),
            status_code=200,
            mimetype="application/json"
        )
        return add_cors_headers(response)
        
    except Exception as e:
        logger.info(f"Request body: {req_body}")
        logger.error(f"YAML conversion error: {str(e)}")
        
        error_response = func.HttpResponse(
            json.dumps({"yaml_content": f"Error: Conversion failed in azure - {str(e)}"}),
            status_code=500,
            mimetype="application/json"
        )
        return add_cors_headers(error_response)

@app.route(route="validate-yaml", methods=["POST", "OPTIONS"])
def validate_yaml(req: func.HttpRequest) -> func.HttpResponse:
    """Validate Azure DevOps YAML - matches YAMLValidationAgent frontend call"""
    
    # Handle CORS preflight
    if req.method == "OPTIONS":
        response = func.HttpResponse("", status_code=200)
        return add_cors_headers(response)
    
    try:
        logger.info("Received YAML validation request")
        
        # Parse request body
        req_body = req.get_json()
        if not req_body:
            raise ValueError("Request body is empty")
        
        yaml_content = req_body.get('yaml_content', '')
        
        if not yaml_content or yaml_content.startswith('Error'):
            return add_cors_headers(func.HttpResponse(
                json.dumps({
                    "isValid": False,
                    "errors": ["Invalid or empty YAML content"],
                    "warnings": [],
                    "autoFixed": False,
                    "fixedYaml": yaml_content
                }),
                status_code=400,
                mimetype="application/json"
            ))
        
        # Validate using swarm
        result = validate_yaml_content(yaml_content)
        
        logger.info(f"YAML validation result: {result}")
        
        # Return response matching frontend expectations
        response = func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        return add_cors_headers(response)
        
    except Exception as e:
        logger.error(f"YAML validation error: {str(e)}")
        error_response = func.HttpResponse(
            json.dumps({
                "isValid": False,
                "errors": [f"YAML validation service error: {str(e)}"],
                "warnings": [],
                "autoFixed": False,
                "fixedYaml": yaml_content if 'yaml_content' in locals() else ""
            }),
            status_code=500,
            mimetype="application/json"
        )
        return add_cors_headers(error_response)

@app.route(route="evaluate-conversion", methods=["POST", "OPTIONS"])
def evaluate_yaml_conversion(req: func.HttpRequest) -> func.HttpResponse:
    """Evaluate conversion quality - matches LLMEvaluationAgent frontend call"""
    
    # Handle CORS preflight
    if req.method == "OPTIONS":
        response = func.HttpResponse("", status_code=200)
        return add_cors_headers(response)
    
    try:
        logger.info("Received conversion evaluation request")
        
        # Parse request body
        req_body = req.get_json()
        if not req_body:
            raise ValueError("Request body is empty")
        
        yaml_content = req_body.get('yaml_content', '')
        jenkins_content = req_body.get('jenkins_content', '')
        
        if not yaml_content or yaml_content.startswith('Error'):
            return add_cors_headers(func.HttpResponse(
                json.dumps({
                    "qualityScore": 0,
                    "completeness": 0,
                    "bestPractices": 0,
                    "overallScore": 0,
                    "passed": False,
                    "issues": "Invalid YAML content provided",
                    "recommendations": "Ensure YAML generation completed successfully",
                    "summary": "Cannot evaluate invalid YAML content"
                }),
                status_code=400,
                mimetype="application/json"
            ))
        
        if not jenkins_content:
            return add_cors_headers(func.HttpResponse(
                json.dumps({
                    "qualityScore": 0,
                    "completeness": 0,
                    "bestPractices": 0,
                    "overallScore": 0,
                    "passed": False,
                    "issues": "Original Jenkins content missing",
                    "recommendations": "Provide original Jenkins file for comparison",
                    "summary": "Cannot evaluate without original Jenkins content"
                }),
                status_code=400,
                mimetype="application/json"
            ))
        
        # Evaluate using swarm
        result = evaluate_conversion(yaml_content, jenkins_content)
        
        logger.info(f"Evaluation result: {result}")
        
        # Return response matching frontend expectations
        response = func.HttpResponse(
            json.dumps(result),
            status_code=200,
            mimetype="application/json"
        )
        return add_cors_headers(response)
        
    except Exception as e:
        logger.error(f"Evaluation error: {str(e)}")
        error_response = func.HttpResponse(
            json.dumps({
                "qualityScore": 0,
                "completeness": 0,
                "bestPractices": 0,
                "overallScore": 0,
                "passed": False,
                "issues": f"Evaluation service error: {str(e)}",
                "recommendations": "Check API configuration and try again",
                "summary": "Evaluation could not be completed"
            }),
            status_code=500,
            mimetype="application/json"
        )
        return add_cors_headers(error_response)

# Health check endpoint
@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint"""
    response = func.HttpResponse(
        json.dumps({"status": "healthy", "service": "jenkins-azure-converter"}),
        status_code=200,
        mimetype="application/json"
    )
    return add_cors_headers(response)