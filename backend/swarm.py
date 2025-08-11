import os
import json
import yaml
import re
from typing import Dict, List, Any, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt
from langgraph_swarm import create_handoff_tool, create_swarm, SwarmState
import google.generativeai as genai

# Configure APIs
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel('gemini-1.5-pro')
gpt4o_model = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))

# Enhanced SwarmState with tracking fields
class EnhancedSwarmState(SwarmState):
    jenkins_content: str = ""
    azure_yaml: str = ""
    conversion_attempts: int = 0
    max_retries: int = 4
    quality_score: float = 0.0
    feedback_history: List[str] = []
    validation_errors: List[str] = []
    pipeline_complete: bool = False
    needs_human_approval: bool = False

import re
from typing import Dict, Any, List

def validate_jenkins_schema(content: str) -> Dict[str, Any]:
    """Validate Jenkinsfile loosely against Jenkins Pipeline structure."""
    errors: List[str] = []
    warnings: List[str] = []

    if not content or len(content.strip()) < 5:
        return {
            "isValid": False,
            "errors": ["File is empty or too short to be a valid Jenkinsfile"],
            "warnings": []
        }

    # Strip single-line and multi-line comments
    content_no_comments = re.sub(r'//.*|/\*[\s\S]*?\*/', '', content)

    # Check for either declarative or scripted pipeline
    has_pipeline_block = bool(re.search(r'pipeline\s*\{', content_no_comments, re.IGNORECASE))
    has_node_block = bool(re.search(r'node\s*[\(\{]', content_no_comments, re.IGNORECASE))

    if not has_pipeline_block and not has_node_block:
        errors.append("Missing 'pipeline { ... }' (declarative) or 'node' (scripted) block.")
        return {
            "isValid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    # Declarative pipeline: relax requirements
    if has_pipeline_block:
        if not re.search(r'agent\s+[^\n\{]+|\bagent\s*\{', content_no_comments, re.IGNORECASE):
            warnings.append("No 'agent' declaration found. Some pipelines may still work without it.")

        if not re.search(r'stages?\s*\{', content_no_comments, re.IGNORECASE):
            warnings.append("No 'stages' block found. Consider adding one for clarity.")
        else:
            # Loosen stage detection to allow more patterns
            if not re.search(r'stage\s*\(.*\)\s*\{', content_no_comments, re.IGNORECASE):
                warnings.append("No named 'stage' blocks detected inside 'stages'.")

    # Best practice hints
    if has_pipeline_block:
        if not re.search(r'post\s*\{', content_no_comments, re.IGNORECASE):
            warnings.append("Consider adding a 'post' block for cleanup/notifications.")
        if not re.search(r'environment\s*\{', content_no_comments, re.IGNORECASE):
            warnings.append("Consider adding an 'environment' block for variables.")

    return {
        "isValid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def validate_azure_yaml_schema(yaml_content: str) -> Dict[str, Any]:
    """Validate Azure DevOps YAML against schema"""
    errors = []
    warnings = []
    auto_fixed = False
    fixed_yaml = yaml_content
    
    try:
        yaml_data = yaml.safe_load(yaml_content)
        
        if not yaml_data:
            return {
                "isValid": False, 
                "errors": ["Invalid or empty YAML content"], 
                "warnings": [], 
                "autoFixed": False,
                "fixedYaml": yaml_content
            }
        
        # Check required fields
        if 'trigger' not in yaml_data and 'pr' not in yaml_data:
            warnings.append("No trigger or PR trigger defined")
        
        if 'pool' not in yaml_data and 'jobs' not in yaml_data:
            errors.append("Missing 'pool' or 'jobs' definition")
        
        # Check for jobs or steps
        if 'jobs' not in yaml_data and 'steps' not in yaml_data:
            errors.append("Must have either 'jobs' or 'steps'")
        
        # Auto-fix common issues
        if 'trigger' not in yaml_data and 'pr' not in yaml_data:
            yaml_data['trigger'] = ['main']
            auto_fixed = True
            fixed_yaml = yaml.dump(yaml_data, default_flow_style=False)
        
    except yaml.YAMLError as e:
        errors.append(f"YAML parsing error: {str(e)}")
    
    return {
        "isValid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "autoFixed": auto_fixed,
        "fixedYaml": fixed_yaml
    }

@tool
def jenkins_validate_tool(content: str) -> Dict[str, Any]:
    """Validate Jenkins file content"""
    return validate_jenkins_schema(content)

@tool  
def gemini_convert_tool(jenkins_content: str, feedback: str = "") -> str:
    """Convert Jenkins pipeline to Azure DevOps YAML using Gemini llm with optional feedback"""
    feedback_prompt = f"\n\nAddress this feedback: {feedback}" if feedback else ""
    
    prompt = f"""Convert this Jenkins pipeline to Azure DevOps YAML format:

{jenkins_content}

Requirements:
1. Convert jenkins pipeline syntax to Azure DevOps YAML
2. Map Jenkins agents to Azure DevOps pool/vmImage
3. Convert stages to jobs or steps appropriately
4. Handle build steps, test steps, and deployment steps
5. Preserve environment variables and parameters
6. Add appropriate triggers{feedback_prompt}

Return only the YAML content, no explanation."""

    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error: Conversion failed - {str(e)}"

@tool
def yaml_validate_tool(yaml_content: str) -> Dict[str, Any]:
    """Validate Azure DevOps YAML"""
    return validate_azure_yaml_schema(yaml_content)

@tool
def gemini_evaluate_tool(yaml_content: str, jenkins_content: str) -> Dict[str, Any]:
    """Evaluate conversion quality using Gemini"""
    prompt = f"""Evaluate this Jenkins to Azure DevOps conversion quality:

Original Jenkins:
{jenkins_content[:1000]}...

Generated Azure DevOps YAML:
{yaml_content[:1000]}...

Score each aspect (1-10):
- Quality: How well does the YAML match Jenkins functionality?
- Completeness: Are all Jenkins features converted?
- Best Practices: Does it follow Azure DevOps best practices?

Return JSON:
{{
    "qualityScore": 8,
    "completeness": 7, 
    "bestPractices": 9,
    "overallScore": 8,
    "passed": true,
    "issues": "Description of issues or 'No issues identified'",
    "recommendations": "Recommendations or 'No recommendations'",
    "summary": "Brief summary"
}}"""

    try:
        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Ensure required fields
            result.setdefault("qualityScore", 5)
            result.setdefault("completeness", 5)
            result.setdefault("bestPractices", 5)
            result.setdefault("overallScore", 5)
            result.setdefault("passed", result.get("overallScore", 0) >= 6)
            result.setdefault("issues", "No issues identified")
            result.setdefault("recommendations", "No recommendations")
            result.setdefault("summary", "Conversion evaluation completed")
            return result
        else:
            raise ValueError("Could not parse JSON response")
            
    except Exception as e:
        return {
            "qualityScore": 5,
            "completeness": 5,
            "bestPractices": 5,
            "overallScore": 5,
            "passed": False,
            "issues": f"Evaluation error: {str(e)}",
            "recommendations": "Try again or check input format",
            "summary": "Evaluation could not be completed"
        }

@tool
def check_retry_limit(attempts: int, max_retries: int) -> Dict[str, Any]:
    """Check if retry limit has been reached"""
    return {
        "can_retry": attempts < max_retries,
        "attempts": attempts,
        "max_retries": max_retries,
        "remaining": max_retries - attempts
    }

@tool  
def human_approval_interrupt(jenkins_content: str, azure_yaml: str, quality_score: float, attempts: int) -> Dict[str, Any]:
    """Trigger human approval interrupt"""
    approval_data = {
        "jenkins_content": jenkins_content,
        "azure_yaml": azure_yaml,
        "quality_score": quality_score,
        "conversion_attempts": attempts,
        "message": "Please review the conversion and approve or provide feedback."
    }
    
    # This will pause execution and wait for UI input
    human_response = interrupt(approval_data)
    
    return {
        "approved": human_response.get("approved", False),
        "feedback": human_response.get("feedback", ""),
        "human_response": human_response
    }

# Create agents with proper retry and handoff logic
jenkins_validator_agent = create_react_agent(
    gpt4o_model,
    [jenkins_validate_tool, create_handoff_tool(agent_name="YAMLGenerator")],
    prompt="""You are a Jenkins validation expert. 
    
    Steps:
    1. Use jenkins_validate_tool to validate the Jenkins content
    2. Move to yaml_generator_agent using the hand off tool
    
    Be thorough in validation and clear about any issues found.""",
    name="JenkinsValidator",
)

yaml_generator_agent = create_react_agent(
    gpt4o_model,
    [gemini_convert_tool, check_retry_limit, create_handoff_tool(agent_name="YAMLValidator")],
    prompt="""You are a pipeline conversion expert. Convert Jenkins to Azure DevOps YAML using gemini_convert_tool.
    
    Steps:
    1. Check if there's feedback from previous attempts in the conversation
    2. Use  to convert (include feedback if available)
    3. Always hand off to YAMLValidator after conversion
    
    If this is a retry, incorporate any feedback to improve the conversion.""",
    name="YAMLGenerator",
)

yaml_validator_agent = create_react_agent(
    gpt4o_model,
    [
        yaml_validate_tool, 
        check_retry_limit,
        create_handoff_tool(agent_name="EvaluationAgent"),
        create_handoff_tool(agent_name="YAMLGenerator")
    ],
    prompt="""You are an Azure DevOps YAML validation expert.
    
    Steps:
    1. Use yaml_validate_tool to validate the YAML
    2. If valid, hand off to EvaluationAgent
    3. If invalid and retries available, hand off back to YAMLGenerator with specific feedback
    4. If invalid and no retries left, stop with error
    
    Use check_retry_limit to determine if more attempts are possible.""",
    name="YAMLValidator",
)

evaluation_agent = create_react_agent(
    gpt4o_model,
    [
        gemini_evaluate_tool,
        check_retry_limit,
        human_approval_interrupt,
        create_handoff_tool(agent_name="YAMLGenerator")
    ],
    prompt="""You are a conversion quality evaluation expert.
    
    Steps:
    1. Use gemini_evaluate_tool to evaluate conversion quality
    2. If overall score >= 7.0, use human_approval_interrupt for final approval
    3. If score < 7.0 and retries available, hand off to YAMLGenerator with improvement feedback
    4. If score < 7.0 and no retries left, still trigger human_approval_interrupt
    
    Always be thorough in evaluation and provide specific improvement suggestions.""",
    name="EvaluationAgent",
)

# Create the swarm workflow
checkpointer = InMemorySaver()
workflow = create_swarm(
    [jenkins_validator_agent, yaml_generator_agent, yaml_validator_agent, evaluation_agent],
    default_active_agent="JenkinsValidator",
    state_schema=EnhancedSwarmState
)

# Compile the swarm
swarm_app = workflow.compile(checkpointer=checkpointer)

# Main execution functions that use the swarm
def validate_jenkins_file(file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Jenkins validation through swarm"""
    config = {"configurable": {"thread_id": f"jenkins_val_{hash(file_data['content'])}"}}
    
    initial_state = {
        "messages": [HumanMessage(content=f"Validate this Jenkins file: {file_data['content']}")],
        "jenkins_content": file_data['content'],
        "conversion_attempts": 0,
        "max_retries": 4
    }
    
    
    try:
        result = swarm_app.invoke(initial_state, config=config)
        
        # Extract validation results from the swarm execution
        validation_result = validate_jenkins_schema(file_data['content'])
        
        return {
            **validation_result,
            "swarm_executed": True,
            "thread_id": config["configurable"]["thread_id"]
        }
    except Exception as e:
        return {
            "isValid": False,
            "errors": [f"Validation failed: {str(e)}"],
            "warnings": [],
            "swarm_executed": False
        }

def convert_to_yaml(jenkins_content: str, thread_id: str = None) -> Dict[str, Any]:
    """Execute full conversion pipeline through swarm with auto-retry"""
    if not thread_id:
        thread_id = f"convert_{hash(jenkins_content)}"
    
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "messages": [HumanMessage(content=f"Convert this Jenkins pipeline to Azure DevOps YAML: {jenkins_content}")],
        #"messages": [{"type": "human", "content": f"Convert this Jenkins pipeline to Azure DevOps YAML:{file_data['content']}"}],
        "jenkins_content": jenkins_content,
        "conversion_attempts": 0,
        "max_retries": 4,
        "feedback_history": []
    }
    
    try:
        result = swarm_app.invoke(initial_state, config=config)
        
        # Check if human approval is needed
        if '__interrupt__' in result:
            return {
                "status": "awaiting_approval",
                "interrupt_data": result['__interrupt__'][0].value,
                "thread_id": thread_id,
                "swarm_state": result
            }
        
        # If completed without interrupt, return the YAML
        return {
            "status": "completed",
            "yaml_content": result.get("azure_yaml", ""),
            "thread_id": thread_id,
            "swarm_state": result
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "thread_id": thread_id
        }

def validate_yaml_content(yaml_content: str) -> Dict[str, Any]:
    """Execute YAML validation through swarm"""
    try:
        result = validate_azure_yaml_schema(yaml_content)
        return {
            **result,
            "swarm_executed": True
        }
    except Exception as e:
        return {
            "isValid": False,
            "errors": [f"YAML validation failed: {str(e)}"],
            "warnings": [],
            "autoFixed": False,
            "fixedYaml": yaml_content,
            "swarm_executed": False
        }

def evaluate_conversion(yaml_content: str, jenkins_content: str) -> Dict[str, Any]:
    """Execute evaluation through swarm"""
    try:
        result = gemini_evaluate_tool.invoke({"yaml_content": yaml_content, "jenkins_content": jenkins_content})
        return {
            **result,
            "swarm_executed": True
        }
    except Exception as e:
        return {
            "qualityScore": 0,
            "completeness": 0,
            "bestPractices": 0,
            "overallScore": 0,
            "passed": False,
            "issues": f"Evaluation failed: {str(e)}",
            "recommendations": "Check input format and try again",
            "summary": "Evaluation could not be completed",
            "swarm_executed": False
        }

def resume_after_human_approval(thread_id: str, approved: bool, feedback: str = "") -> Dict[str, Any]:
    """Resume pipeline after human approval decision"""
    config = {"configurable": {"thread_id": thread_id}}
    
    human_decision = {
        "approved": approved,
        "feedback": feedback
    }
    
    try:
        result = swarm_app.invoke(Command(resume=human_decision), config=config)
        
        if approved:
            return {
                "status": "approved_and_completed",
                "azure_yaml": result.get("azure_yaml", ""),
                "final_result": result
            }
        else:
            # Check if another interrupt is needed (retry cycle)
            if '__interrupt__' in result:
                return {
                    "status": "retry_awaiting_approval",
                    "interrupt_data": result['__interrupt__'][0].value,
                    "thread_id": thread_id
                }
            else:
                return {
                    "status": "retry_completed", 
                    "azure_yaml": result.get("azure_yaml", ""),
                    "final_result": result
                }
                
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }