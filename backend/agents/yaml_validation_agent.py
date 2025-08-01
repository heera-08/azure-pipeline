from services.yaml_validator import YAMLValidatorService
from typing import Dict

class YAMLValidationAgent:
    def __init__(self):
        self.name = "YAMLValidationAgent"
        self.yaml_validator = YAMLValidatorService()

    async def execute(self, yaml_content: str) -> Dict:
        """Execute YAML validation using Azure DevOps schema"""
        
        try:
            if not yaml_content or yaml_content.startswith('Error'):
                return {
                    "isValid": False,
                    "errors": ["No valid YAML content to validate"],
                    "warnings": [],
                    "autoFixed": False,
                    "fixedYaml": yaml_content,
                    "agent": self.name
                }
            
            # Use YAML Validator Service
            result = self.yaml_validator.validate_yaml(yaml_content)
            
            # Add agent information
            result["agent"] = self.name
            
            return result
            
        except Exception as e:
            return {
                "isValid": False,
                "errors": [f"YAML validation failed: {str(e)}"],
                "warnings": [],
                "autoFixed": False,
                "fixedYaml": yaml_content,
                "agent": self.name
            }