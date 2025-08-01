from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph_swarm import create_swarm, create_handoff_tool, SwarmState
from langchain_core.tools import tool
from typing import Dict, Any
import asyncio

from agents.file_validation_agent import FileValidationAgent
from agents.conversion_agent import ConversionAgent
from agents.yaml_validation_agent import YAMLValidationAgent
from agents.evaluation_agent import EvaluationAgent
from agents.approval_agent import ApprovalAgent

class PipelineState(SwarmState):
    """Extended state for the pipeline with file processing data"""
    file_data: Dict = {}
    validation_result: Dict = {}
    yaml_content: str = ""
    yaml_validation: Dict = {}
    evaluation: Dict = {}
    approval: Dict = {}
    current_step: str = "start"
    errors: list = []

class SwarmPipeline:
    """Pipeline using LangGraph Swarm for multi-agent workflow"""
    
    def __init__(self, model: str = "openai:gpt-4o"):
        self.model = model
        self.checkpointer = InMemorySaver()
        
        # Initialize existing agents
        self.file_validation_agent = FileValidationAgent()
        self.conversion_agent = ConversionAgent()
        self.yaml_validation_agent = YAMLValidationAgent()
        self.evaluation_agent = EvaluationAgent()
        self.approval_agent = ApprovalAgent()
        
        self.app = self._create_swarm()
    
    def _create_tools(self):
        """Create tools that wrap your existing agents"""
        
        @tool
        async def validate_file_tool(file_data: Dict) -> Dict:
            """Validate the uploaded file using FileValidationAgent."""
            return await self.file_validation_agent.execute(file_data)
        
        @tool
        async def convert_to_yaml_tool(jenkins_content: str, validation_result: Dict) -> str:
            """Convert Jenkins to YAML using ConversionAgent."""
            return await self.conversion_agent.execute(jenkins_content, validation_result)
        
        @tool
        async def validate_yaml_tool(yaml_content: str) -> Dict:
            """Validate YAML using YAMLValidationAgent."""
            return await self.yaml_validation_agent.execute(yaml_content)
        
        @tool
        async def evaluate_conversion_tool(yaml_content: str, jenkins_content: str) -> Dict:
            """Evaluate conversion using EvaluationAgent."""
            return await self.evaluation_agent.execute(yaml_content, jenkins_content)
        
        @tool
        async def approve_pipeline_tool(yaml_content: str, evaluation_result: Dict) -> Dict:
            """Approve pipeline using ApprovalAgent."""
            return await self.approval_agent.execute(yaml_content, evaluation_result)
        
        return {
            'validate_file': validate_file_tool,
            'convert_to_yaml': convert_to_yaml_tool,
            'validate_yaml': validate_yaml_tool,
            'evaluate_conversion': evaluate_conversion_tool,
            'approve_pipeline': approve_pipeline_tool
        }
    
    def _create_swarm(self):
        """Create the multi-agent swarm workflow"""
        
        tools = self._create_tools()        
        file_validation_swarm_agent = create_react_agent(
            self.model,
            [
                tools['validate_file'],
                create_handoff_tool(
                    agent_name="conversion_agent",
                    description="Hand off to conversion agent after successful validation"
                )
            ],
            prompt="""You are a file validation specialist. Your job is to:
1. Use the validate_file_tool to validate uploaded Jenkins files
2. If validation passes, hand off to the conversion agent
3. If validation fails, provide clear error messages

Always use the validate_file_tool first to perform validation.""",
            name="file_validation_agent"
        )
        
        conversion_swarm_agent = create_react_agent(
            self.model,
            [
                tools['convert_to_yaml'],
                create_handoff_tool(
                    agent_name="yaml_validation_agent", 
                    description="Hand off to YAML validation agent after conversion"
                )
            ],
            prompt="""You are a Jenkins to YAML conversion specialist. Your job is to:
1. Use the convert_to_yaml_tool to convert Jenkins pipeline files to YAML
2. Hand off to YAML validation agent after successful conversion
3. Handle conversion errors appropriately

Always use the convert_to_yaml_tool to perform conversions.""",
            name="conversion_agent"
        )
        
        yaml_validation_swarm_agent = create_react_agent(
            self.model,
            [
                tools['validate_yaml'],
                create_handoff_tool(
                    agent_name="evaluation_agent",
                    description="Hand off to evaluation agent after YAML validation"
                )
            ],
            prompt="""You are a YAML validation specialist. Your job is to:
1. Use the validate_yaml_tool to validate generated YAML content
2. Hand off to evaluation agent after validation
3. Report validation results clearly

Always use the validate_yaml_tool to perform validation.""",
            name="yaml_validation_agent"
        )
        
        evaluation_swarm_agent = create_react_agent(
            self.model,
            [
                tools['evaluate_conversion'],
                create_handoff_tool(
                    agent_name="approval_agent",
                    description="Hand off to approval agent after evaluation"
                )
            ],
            prompt="""You are a conversion quality evaluator. Your job is to:
1. Use the evaluate_conversion_tool to evaluate conversion quality
2. Hand off to approval agent after evaluation
3. Provide detailed evaluation metrics

Always use the evaluate_conversion_tool to perform evaluation.""",
            name="evaluation_agent"
        )
        
        approval_swarm_agent = create_react_agent(
            self.model,
            [tools['approve_pipeline']],
            prompt="""You are the final approval authority. Your job is to:
1. Use the approve_pipeline_tool to make final approval decisions
2. Provide clear approval or rejection reasoning
3. Generate final results

Always use the approve_pipeline_tool to make approval decisions.""",
            name="approval_agent"
        )
        
        # Create the swarm workflow
        workflow = create_swarm(
            agents=[
                file_validation_swarm_agent,
                conversion_swarm_agent, 
                yaml_validation_swarm_agent,
                evaluation_swarm_agent,
                approval_swarm_agent
            ],
            default_active_agent="file_validation_agent",
            state_schema=PipelineState
        )
        
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def run_pipeline(self, file_data: Dict, thread_id: str = "default") -> Dict:
        """Run the complete pipeline using the swarm"""
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Prepare initial message with file data
        initial_message = {
            "role": "user", 
            "content": f"Please process this Jenkins file for YAML conversion: {file_data.get('filename', 'unknown')}"
        }
        
        # Initialize state with file data
        initial_state = {
            "messages": [initial_message],
            "file_data": file_data,
            "current_step": "file_validation"
        }
        
        try:
            # Run the swarm workflow
            result = await self.app.ainvoke(initial_state, config)
            
            # Extract results from the final state
            return {
                "success": True,
                "validation": result.get("validation_result", {}),
                "yaml_content": result.get("yaml_content", ""),
                "yaml_validation": result.get("yaml_validation", {}),
                "evaluation": result.get("evaluation", {}),
                "approval": result.get("approval", {}),
                "current_step": result.get("current_step", "completed"),
                "messages": result.get("messages", [])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "current_step": "error"
            }

# Usage example
async def main():
    """Example usage of the SwarmPipeline"""
    
    # Sample file data
    sample_file_data = {
        "filename": "Jenkinsfile",
        "content": """
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Building..'
            }
        }
        stage('Test') {
            steps {
                echo 'Testing..'
            }
        }
        stage('Deploy') {
            steps {
                echo 'Deploying....'
            }
        }
    }
}
""",
        "type": "jenkinsfile"
    }
    

    pipeline = SwarmPipeline()
    result = await pipeline.run_pipeline(sample_file_data, thread_id="example_run")
    
    print("Pipeline Result:")
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Final Step: {result['current_step']}")
        print(f"Approval Status: {result.get('approval', {}).get('approved', 'N/A')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(main())