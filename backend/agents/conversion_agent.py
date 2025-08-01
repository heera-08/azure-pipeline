import os
import requests
from typing import Dict

class ConversionAgent:
    def __init__(self):
        self.name = "ConversionAgent"
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    async def execute(self, jenkins_content: str, validation_result: Dict) -> str:
        """Convert Jenkins pipeline to Azure DevOps YAML"""
        
        if not validation_result.get('isValid', False):
            return "Error: Cannot convert invalid Jenkins file. Please fix validation errors first."
        
        try:
            prompt = self._build_conversion_prompt(jenkins_content)
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if not response.ok:
                return f"Error: API request failed with status {response.status_code}"
            
            data = response.json()
            
            if not data.get('candidates') or not data['candidates'][0].get('content'):
                return "Error: Invalid response from conversion service"
            
            converted_yaml = data['candidates'][0]['content']['parts'][0]['text']
            
            # Clean up the response (remove markdown formatting if present)
            converted_yaml = self._clean_yaml_response(converted_yaml)
            
            return converted_yaml
            
        except Exception as e:
            return f"Error: Conversion failed - {str(e)}"

    def _build_conversion_prompt(self, jenkins_content: str) -> str:
        """Build the conversion prompt for the LLM"""
        return f"""Convert this Jenkins pipeline to Azure DevOps YAML format.

Rules:
1. Return ONLY valid Azure DevOps YAML
2. No explanations or markdown formatting
3. Include trigger, pool, and stages sections
4. Convert Jenkins stages to Azure DevOps stages
5. Map Jenkins steps to appropriate Azure DevOps tasks
6. Preserve environment variables and parameters

Jenkins Pipeline:
{jenkins_content}

Azure DevOps YAML:"""

    def _clean_yaml_response(self, response: str) -> str:
        """Clean up the LLM response to extract pure YAML"""
        # Remove markdown code blocks if present
        response = response.strip()
        
        if response.startswith('```yaml'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]
            
        if response.endswith('```'):
            response = response[:-3]
            
        return response.strip()