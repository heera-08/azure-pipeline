from typing import Dict

class ApprovalAgent:
    def __init__(self):
        self.name = "ApprovalAgent"

    async def execute(self, yaml_content: str, evaluation_result: Dict) -> Dict:
        """Prepare YAML for human approval"""
        
        try:
            if not yaml_content or yaml_content.startswith('Error'):
                return {
                    "ready_for_approval": False,
                    "message": "No valid YAML content for approval",
                    "agent": self.name
                }
            
           
            evaluation_passed = evaluation_result.get('passed', False)
            overall_score = evaluation_result.get('overallScore', 0)
            
            return {
                "ready_for_approval": True,
                "yaml_content": yaml_content,
                "evaluation_passed": evaluation_passed,
                "overall_score": overall_score,
                "message": "YAML ready for human approval and download",
                "agent": self.name
            }
            
        except Exception as e:
            return {
                "ready_for_approval": False,
                "message": f"Approval preparation failed: {str(e)}",
                "agent": self.name
            }