import os
import requests
import re
from typing import Dict

class EvaluationAgent:
    def __init__(self):
        self.name = "EvaluationAgent"
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

    async def execute(self, yaml_content: str, jenkins_content: str) -> Dict:
        """Evaluate conversion quality using LLM"""
        
        try:
            if not yaml_content or yaml_content.startswith('Error'):
                return self._create_error_result("No valid YAML content to evaluate")
            
            prompt = self._build_evaluation_prompt(yaml_content, jenkins_content)
            
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
                return self._create_error_result(f"API request failed: {response.status_code}")
            
            data = response.json()
            
            if not data.get('candidates') or not data['candidates'][0].get('content'):
                return self._create_error_result("Invalid response from evaluation service")
            
            evaluation_text = data['candidates'][0]['content']['parts'][0]['text']
            
            # Parse the structured response
            result = self._parse_evaluation_response(evaluation_text)
            result["agent"] = self.name
            
            return result
            
        except Exception as e:
            return self._create_error_result(f"Evaluation failed: {str(e)}")

    def _build_evaluation_prompt(self, yaml_content: str, jenkins_content: str) -> str:
        """Build evaluation prompt for LLM"""
        return f"""Evaluate this Jenkins to Azure DevOps YAML conversion.

Original Jenkins Pipeline:
{jenkins_content}

Converted Azure DevOps YAML:
{yaml_content}

Provide evaluation in this exact format:
QUALITY_SCORE: X
COMPLETENESS: X
BEST_PRACTICES: X
ISSUES: List critical issues
RECOMMENDATIONS: List improvements
SUMMARY: Brief assessment

Use scores 1-10. Be concise and technical."""

    def _parse_evaluation_response(self, response: str) -> Dict:
        """Parse structured evaluation response"""
        try:
            quality_match = re.search(r'QUALITY_SCORE:\s*(\d+)', response)
            completeness_match = re.search(r'COMPLETENESS:\s*(\d+)', response)
            best_practices_match = re.search(r'BEST_PRACTICES:\s*(\d+)', response)
            
            issues_match = re.search(r'ISSUES:\s*(.*?)(?=RECOMMENDATIONS:|SUMMARY:|$)', response, re.DOTALL)
            recommendations_match = re.search(r'RECOMMENDATIONS:\s*(.*?)(?=SUMMARY:|$)', response, re.DOTALL)
            summary_match = re.search(r'SUMMARY:\s*(.*?)$', response, re.DOTALL)
            
            quality_score = int(quality_match.group(1)) if quality_match else 0
            completeness = int(completeness_match.group(1)) if completeness_match else 0
            best_practices = int(best_practices_match.group(1)) if best_practices_match else 0
            
            overall_score = round((quality_score + completeness + best_practices) / 3)
            
            return {
                "qualityScore": quality_score,
                "completeness": completeness,
                "bestPractices": best_practices,
                "overallScore": overall_score,
                "passed": overall_score >= 7,
                "issues": issues_match.group(1).strip() if issues_match else "No issues identified",
                "recommendations": recommendations_match.group(1).strip() if recommendations_match else "No recommendations",
                "summary": summary_match.group(1).strip() if summary_match else "No summary available",
                "rawEvaluation": response
            }
            
        except Exception:
            return self._create_error_result("Failed to parse evaluation response")

    def _create_error_result(self, error_message: str) -> Dict:
        """Create error result structure"""
        return {
            "qualityScore": 0,
            "completeness": 0,
            "bestPractices": 0,
            "overallScore": 0,
            "passed": False,
            "issues": error_message,
            "recommendations": "Fix the error and try again",
            "summary": "Evaluation could not be completed",
            "rawEvaluation": f"Error: {error_message}",
            "agent": self.name
        }