from typing import Dict

class FileValidationAgent:
    def __init__(self):
        self.name = "FileValidationAgent"

    async def execute(self, file_data: Dict) -> Dict:
        """Execute Jenkinsfile/XML validation using local rules"""
        try:
            filename = file_data.get("name", "")
            content = file_data.get("content", "")
            errors = []
            warnings = []

            if filename.lower().find("jenkinsfile") != -1 or filename.endswith(".groovy"):
                if "pipeline" not in content:
                    errors.append('Missing "pipeline" block - declarative pipeline required')
                if "agent" not in content:
                    warnings.append('Missing "agent" declaration')
                if "stages" not in content:
                    errors.append('Missing "stages" block')
                if "stage(" not in content:
                    warnings.append("No stage definitions found")
                if "pipeline" in content and "steps" not in content:
                    warnings.append("No step definitions found in pipeline stages")
                if "checkout" not in content and "git" not in content:
                    warnings.append("No source code checkout detected")

            elif filename.endswith(".xml"):
                if "<project>" not in content and "<flow-definition>" not in content:
                    errors.append("Invalid Jenkins XML - missing project or flow-definition root element")
                if "<builders>" not in content and "<script>" not in content:
                    warnings.append("No build steps or script found in XML configuration")
                if "<scm>" not in content and "<definition>" not in content:
                    warnings.append("No source control management configuration found")

            if not content.strip():
                errors.append("File appears to be empty")

            if len(content) > 50000:
                warnings.append("File size is quite large - consider breaking into smaller components")

            return {
                "isValid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "agent": self.name,
            }

        except Exception as e:
            return {
                "isValid": False,
                "errors": [f"Validation failed: {str(e)}"],
                "warnings": [],
                "agent": self.name,
            }









