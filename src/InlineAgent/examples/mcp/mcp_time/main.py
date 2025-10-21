import argparse
import uuid
import sys
import os
from mcp import StdioServerParameters

# Add the local source directory to use our updated rationale storage code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from InlineAgent.tools import MCPStdio
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent
from InlineAgent.observability import ObservabilityConfig
from InlineAgent.observability.process import ProcessL2Trace

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run InlineAgent with MCP Time tool, S3 trace storage, and DynamoDB session storage')
    parser.add_argument('--s3-bucket', type=str, required=True, help='S3 bucket name for storing trace logs')
    parser.add_argument('--dynamodb-table', type=str, default='agent-sessions-table', help='DynamoDB table name for storing session data (default: agent-sessions-table)')
    parser.add_argument('--profile', type=str, default='default', help='AWS profile to use')
    parser.add_argument('--question', type=str, default='Convert 12:30pm to Europe/London timezone? My timezone is America/New_York', 
                        help='Question to ask the agent')
    return parser.parse_args()

# Step 1: Define MCP stdio parameters
server_params = StdioServerParameters(
    command="docker",
    args=["run", "-i", "--rm", "mcp/time"],
)


async def main():
    # Parse command line arguments
    args = parse_arguments()
    
    print(f"Using S3 bucket '{args.s3_bucket}' for storing traces")
    print(f"Using DynamoDB table '{args.dynamodb_table}' for storing session data")
    
    # Generate unique session and request IDs
    session_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}")
    print(f"Request ID: {request_id}")
    
    # Configure observability
    observe_config = ObservabilityConfig()
    observe_config.PRODUCE_BEDROCK_OTEL_TRACES = True
    
    # Force saving traces
    original_process_trace_event = ProcessL2Trace.process_trace_event
    
    def force_save_traces(trace_data, span_manager, save_traces, session_id, show_traces):
        # Always save traces and show traces regardless of parameters
        return original_process_trace_event(trace_data, span_manager, True, session_id, True)
    
    ProcessL2Trace.process_trace_event = force_save_traces
    
    # Step 2: Create MCP Client
    time_mcp_client = await MCPStdio.create(server_params=server_params)

    try:
        # Step 3: Define an action group
        time_action_group = ActionGroup(
            name="TimeActionGroup",
            description="Helps user get current time and convert time.",
            mcp_clients=[time_mcp_client],
        )

        # Step 4: Invoke agent
        await InlineAgent(
            # Step 4.1: Provide the model
            foundation_model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            # Step 4.2: Concise instruction
            instruction="""You are a friendly assistant that is responsible for resolving user queries. """,
            # Step 4.3: Provide the agent name and action group
            agent_name="time_agent",
            action_groups=[time_action_group],
            profile=args.profile,
        ).invoke(
            input_text=args.question,
            enable_trace=True,
            session_id=session_id,
            request_id=request_id,
            trace_bucket_name=args.s3_bucket,
            dynamodb_table_name=args.dynamodb_table
        )
        
        print(f"\nTraces have been saved to S3 bucket: {args.s3_bucket}")
        print(f"Session data has been saved to DynamoDB table: {args.dynamodb_table}")
        print(f"You can find individual trace files at: s3://{args.s3_bucket}/sessions/{session_id}/{request_id}/traces/")
        print(f"You can find the summary file at: s3://{args.s3_bucket}/sessions/{session_id}/{request_id}/summary.json")

    finally:

        await time_mcp_client.cleanup()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
