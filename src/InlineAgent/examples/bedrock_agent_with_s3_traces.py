import os
import uuid
import argparse
import boto3

from InlineAgent.observability import ObservabilityConfig, observe
from InlineAgent.observability import create_tracer_provider
from InlineAgent import AgentAppConfig
from InlineAgent.observability.process import ProcessL2Trace

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run Bedrock Agent with S3 trace logging')
    parser.add_argument('--s3-bucket', type=str, required=True, help='S3 bucket name for storing trace logs')
    parser.add_argument('--region', type=str, default='us-northeast-1', help='AWS region for S3 bucket (default: us-northeast-1)')
    parser.add_argument('--profile', type=str, default='default', help='AWS profile to use')
    parser.add_argument('--question', type=str, default='Tell me about AWS Bedrock', help='Question to ask the agent')
    return parser.parse_args()

def setup_trace_saving(s3_bucket, region):
    """Configure trace saving to S3 with specified region"""
    # Set environment variables for S3 configuration
    os.environ["TRACE_S3_BUCKET"] = s3_bucket
    os.environ["SAVE_TRACES_TO_S3"] = "true"
    os.environ["AWS_REGION"] = region
    
    print(f"Trace logs will be saved to S3 bucket: {s3_bucket} in region: {region}")
    
    # Configure observability settings
    observe_config = ObservabilityConfig()
    observe_config.SAVE_TRACES_TO_S3 = True
    observe_config.TRACE_S3_BUCKET = s3_bucket
    
    # Create a wrapper function to force saving traces
    original_process_trace_event = ProcessL2Trace.process_trace_event
    
    def force_save_traces(trace_data, span_manager, save_traces, session_id, show_traces):
        # Always save traces regardless of save_traces parameter
        ProcessL2Trace.save_trace(trace_data=trace_data, session_id=session_id)
        return original_process_trace_event(trace_data, span_manager, save_traces, session_id, show_traces)
    
    # Replace the original method with our wrapper
    ProcessL2Trace.process_trace_event = force_save_traces
    
    return observe_config

@observe(show_traces=True, save_traces=True)  # Enable save_traces
def invoke_bedrock_agent(inputText: str, sessionId: str, **kwargs):
    """Invoke a Bedrock Agent with instrumentation"""

    # Create Bedrock client
    profile = kwargs.pop("profile", "default")

    bedrock_agent_runtime = boto3.Session(profile_name=profile).client(
        "bedrock-agent-runtime"
    )

    # Invoke the agent with the appropriate configuration
    response = bedrock_agent_runtime.invoke_agent(
        inputText=inputText, sessionId=sessionId, **kwargs
    )

    return response


if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()
    
    # Setup trace saving with S3 bucket and region
    observe_config = setup_trace_saving(args.s3_bucket, args.region)
    
    # Initialize observability
    agent_config = AgentAppConfig()
    create_tracer_provider(config=observe_config, timeout=300)

    user_id = "multiagent-test"
    question = args.question
    sessionId = f"session-{str(uuid.uuid4())}"

    # Tags for filtering
    tags = ["bedrock-agent", "example", "development"]
    stream_final_response = True
    enable_trace = True  # Required for observability

    print(f"Invoking agent with question: {question}")
    print(f"Session ID: {sessionId}")
    
    agent_answer = invoke_bedrock_agent(
        agentId=agent_config.AGENT_ID,
        agentAliasId=agent_config.AGENT_ALIAS_ID,
        inputText=question,
        sessionId=sessionId,
        enableTrace=enable_trace,
        streamingConfigurations={"streamFinalResponse": stream_final_response},
        user_id=user_id,
        tags=tags,
        profile=args.profile,
    )
    
    print("\nAgent invocation complete.")
    print(f"Trace logs have been saved to S3 bucket: {args.s3_bucket} in region: {args.region}")
