from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from swarm_pipeline import SwarmPipeline
import uuid

load_dotenv()

app = FastAPI(title="Jenkins to Azure DevOps Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize swarm pipeline
swarm_pipeline = SwarmPipeline()

class FileContent(BaseModel):
    name: str
    content: str
    size: int

class ConversionRequest(BaseModel):
    file_content: str
    validation_result: dict

class YAMLValidationRequest(BaseModel):
    yaml_content: str

class EvaluationRequest(BaseModel):
    yaml_content: str
    jenkins_content: str

class FullPipelineRequest(BaseModel):
    file_data: FileContent
    thread_id: str = None

@app.post("/api/validate-jenkins")
async def validate_jenkins_file(file_data: FileContent):
    """Validate Jenkins file using enhanced Jenkins Linter API"""
    try:
        # Create a unique thread ID for this request
        thread_id = str(uuid.uuid4())
        
        # Convert FileContent to dict format expected by agents
        file_dict = {
            "filename": file_data.name,
            "content": file_data.content,
            "size": file_data.size,
            "type": "jenkinsfile"
        }
        
        # Run only the validation step using the swarm
        # This will run the file validation agent only
        result = await swarm_pipeline.run_pipeline(file_dict, thread_id=thread_id)
        
        if result["success"]:
            return result.get("validation", {})
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/convert-to-yaml")
async def convert_to_yaml(request: ConversionRequest):
    """Convert Jenkins file to Azure DevOps YAML"""
    try:
        # Create a unique thread ID for this request
        thread_id = str(uuid.uuid4())
        
        # Prepare file data with validation result
        file_dict = {
            "filename": "Jenkinsfile",
            "content": request.file_content,
            "type": "jenkinsfile",
            "validation_result": request.validation_result
        }
        
        # Run the pipeline up to conversion step
        result = await swarm_pipeline.run_pipeline(file_dict, thread_id=thread_id)
        
        if result["success"]:
            return {"yaml_content": result.get("yaml_content", "")}
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/validate-yaml") 
async def validate_yaml(request: YAMLValidationRequest):
    """Validate Azure DevOps YAML"""
    try:
        # Create a unique thread ID for this request
        thread_id = str(uuid.uuid4())
        
        # Create minimal file data for YAML validation
        file_dict = {
            "filename": "azure-pipeline.yml",
            "content": request.yaml_content,
            "type": "yaml"
        }
        
        # Run pipeline up to YAML validation
        result = await swarm_pipeline.run_pipeline(file_dict, thread_id=thread_id)
        
        if result["success"]:
            return result.get("yaml_validation", {})
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/evaluate-conversion")
async def evaluate_conversion(request: EvaluationRequest):
    """Evaluate conversion quality using LLM"""
    try:
        # Create a unique thread ID for this request
        thread_id = str(uuid.uuid4())
        
        # Prepare file data for evaluation
        file_dict = {
            "filename": "pipeline-evaluation",
            "content": request.jenkins_content,
            "yaml_content": request.yaml_content,
            "type": "evaluation"
        }
        
        # Run pipeline up to evaluation
        result = await swarm_pipeline.run_pipeline(file_dict, thread_id=thread_id)
        
        if result["success"]:
            return result.get("evaluation", {})
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/full-pipeline")
async def run_full_pipeline(request: FullPipelineRequest):
    """Run the complete Jenkins to YAML conversion pipeline"""
    try:
        # Use provided thread_id or generate new one
        thread_id = request.thread_id or str(uuid.uuid4())
        
        # Convert FileContent to dict format
        file_dict = {
            "filename": request.file_data.name,
            "content": request.file_data.content,
            "size": request.file_data.size,
            "type": "jenkinsfile"
        }
        
        # Run the complete pipeline
        result = await swarm_pipeline.run_pipeline(file_dict, thread_id=thread_id)
        
        if result["success"]:
            return {
                "thread_id": thread_id,
                "validation": result.get("validation", {}),
                "yaml_content": result.get("yaml_content", ""),
                "yaml_validation": result.get("yaml_validation", {}),
                "evaluation": result.get("evaluation", {}),
                "approval": result.get("approval", {}),
                "messages": result.get("messages", []),
                "final_step": result.get("current_step", "")
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/continue-pipeline")
async def continue_pipeline(thread_id: str, user_message: str):
    """Continue an existing pipeline conversation"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        
        # Add user message to continue the conversation
        new_message = {
            "role": "user",
            "content": user_message
        }
        
        # Continue the existing conversation
        result = await swarm_pipeline.app.ainvoke(
            {"messages": [new_message]}, 
            config
        )
        
        return {
            "thread_id": thread_id,
            "messages": result.get("messages", []),
            "current_step": result.get("current_step", "")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pipeline-status/{thread_id}")
async def get_pipeline_status(thread_id: str):
    """Get the current status of a pipeline"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        
        # Get current state
        state = await swarm_pipeline.app.aget_state(config)
        
        return {
            "thread_id": thread_id,
            "current_step": state.values.get("current_step", "unknown"),
            "messages": state.values.get("messages", []),
            "has_data": bool(state.values.get("file_data"))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "pipeline_type": "langgraph_swarm"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)