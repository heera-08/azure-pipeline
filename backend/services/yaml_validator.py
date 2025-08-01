import yaml
import re
from typing import Dict, List

class YAMLValidatorService:
    def __init__(self):
        self.required_fields = ['trigger', 'pool', 'stages']
        self.valid_tasks = [
            'UsePythonVersion', 'NodeTool', 'DotNetCoreCLI', 'Maven', 'Gradle',
            'PowerShell', 'Bash', 'CmdLine', 'PublishTestResults', 
            'PublishBuildArtifacts', 'DownloadBuildArtifacts', 'Docker'
        ]

    def validate_yaml(self, yaml_content: str) -> Dict:
        """Validate Azure DevOps YAML content"""
        errors = []
        warnings = []
        fixed_yaml = yaml_content
        auto_fixed = False

        try:
            yaml_data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            errors.append(f"YAML syntax error: {str(e)}")
            return {
                "isValid": False,
                "errors": errors,
                "warnings": warnings,
                "autoFixed": False,
                "fixedYaml": yaml_content
            }

        # Validate required fields
        missing_fields = self._check_required_fields(yaml_data)
        if missing_fields:
            fixed_yaml, field_fixes = self._fix_missing_fields(fixed_yaml, missing_fields)
            if field_fixes:
                auto_fixed = True
                warnings.extend([f"Added missing field: {field}" for field in field_fixes])

        # Validate indentation
        indent_errors = self._validate_indentation(yaml_content.split('\n'))
        if indent_errors:
            errors.extend(indent_errors)
            fixed_yaml = self._fix_indentation(fixed_yaml)
            auto_fixed = True

        # Validate tasks
        task_warnings = self._validate_tasks(yaml_content)
        warnings.extend(task_warnings)

        # Check for common issues
        common_issues = self._check_common_issues(yaml_content)
        warnings.extend(common_issues)

        return {
            "isValid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "autoFixed": auto_fixed,
            "fixedYaml": fixed_yaml
        }

    def _check_required_fields(self, yaml_data: Dict) -> List[str]:
        """Check for required Azure DevOps YAML fields"""
        missing = []
        
        if not yaml_data.get('trigger'):
            missing.append('trigger')
            
        if not yaml_data.get('pool') and not yaml_data.get('vmImage'):
            missing.append('pool')
            
        if not yaml_data.get('stages') and not yaml_data.get('jobs') and not yaml_data.get('steps'):
            missing.append('stages/jobs/steps')
            
        return missing

    def _fix_missing_fields(self, yaml_content: str, missing_fields: List[str]) -> tuple:
        """Auto-fix missing required fields"""
        fixed_yaml = yaml_content
        fixes_applied = []
        
        if 'trigger' in missing_fields:
            fixed_yaml = f"trigger:\n- main\n\n{fixed_yaml}"
            fixes_applied.append('trigger')
            
        if 'pool' in missing_fields:
            fixed_yaml = f"pool:\n  vmImage: 'ubuntu-latest'\n\n{fixed_yaml}"
            fixes_applied.append('pool')
            
        return fixed_yaml, fixes_applied

    def _validate_indentation(self, lines: List[str]) -> List[str]:
        """Validate YAML indentation"""
        errors = []
        
        for i, line in enumerate(lines, 1):
            if line.strip() and not line.startswith('#'):
                leading_spaces = len(line) - len(line.lstrip())
                
                # Check for tabs
                if '\t' in line:
                    errors.append(f"Line {i}: Uses tabs instead of spaces")
                    
                # Check for odd indentation
                if leading_spaces % 2 != 0:
                    errors.append(f"Line {i}: Inconsistent indentation")
                    
        return errors

    def _fix_indentation(self, yaml_content: str) -> str:
        """Fix indentation issues"""
        # Replace tabs with spaces
        fixed = yaml_content.replace('\t', '  ')
        
        # Fix other indentation issues would be more complex
        # For now, just return tab-fixed version
        return fixed

    def _validate_tasks(self, yaml_content: str) -> List[str]:
        """Validate Azure DevOps tasks"""
        warnings = []
        
        # Find all task references
        task_pattern = r'task:\s*([^\s@\n]+)'
        matches = re.findall(task_pattern, yaml_content)
        
        for task in matches:
            if not any(valid_task in task for valid_task in self.valid_tasks):
                warnings.append(f"Unknown task: {task} - verify this is valid")
                
            # Check for missing version
            if '@' not in task:
                warnings.append(f"Task {task} missing version specification")
                
        return warnings

    def _check_common_issues(self, yaml_content: str) -> List[str]:
        """Check for common Azure DevOps YAML issues"""
        warnings = []
        
        # Check for Jenkins references
        if re.search(r'jenkins|jenkinsfile', yaml_content, re.IGNORECASE):
            warnings.append("YAML contains Jenkins references - manual review needed")
            
        # Check for empty sections
        if re.search(r'variables:\s*$', yaml_content, re.MULTILINE):
            warnings.append("Empty variables section detected")
            
        # Check for missing displayName
        if 'stages:' in yaml_content and 'displayName:' not in yaml_content:
            warnings.append("Consider adding displayName for better readability")
            
        return warnings