from mcp import StdioServerParameters

from InlineAgent.tools import MCPStdio
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent

# Step 1: Define MCP stdio parameters
server_params = StdioServerParameters(
    command="docker",
    args=["run", "-i", "--rm", "mcp/cluster"],
)

async def main():
    # Step 2: Create MCP Client
    cluster_mcp_client = await MCPStdio.create(server_params=server_params)
    
    try:
        # Step 3: Define an action group
        cluster_action_group = ActionGroup(
            name="ClusterGroup",
            description="Helps user get cluster details",
            mcp_clients=[cluster_mcp_client],
        )
        
        # Step 4: Invoke agent 
        await InlineAgent(
            # Step 4.1: Provide the model
            foundation_model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            # Step 4.2: Concise instruction
            instruction="""You are a friendly assistant that is responsible for giving cluster details""",
            # Step 4.3: Provide the agent name and action group
            agent_name="cluster_agent",
            action_groups=[cluster_action_group],
        ).invoke(input_text="list all clusters", enable_trace=True)
    
    finally:
        
        await cluster_mcp_client.cleanup()

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())