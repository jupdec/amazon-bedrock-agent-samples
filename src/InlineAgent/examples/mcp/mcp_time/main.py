from mcp import StdioServerParameters

from InlineAgent.tools import MCPStdio
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent
from InlineAgent.observability import ObservabilityConfig
from InlineAgent.observability.process import ProcessL2Trace

# Step 1: Define MCP stdio parameters
server_params = StdioServerParameters(
    command="docker",
    args=["run", "-i", "--rm", "mcp/time"],
)


async def main():
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
        ).invoke(
            input_text="Convert 12:30pm to Europe/London timezone? My timezone is America/New_York",
            enable_trace=True
        )

    finally:

        await time_mcp_client.cleanup()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
