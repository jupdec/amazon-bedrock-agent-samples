import asyncio
import uuid
import logging
from mcp import Stu
from httpx import HTTPStatusError

from InlineAgent.tools import MCPStreamableHttp
from InlineAgent.action_group import ActionGroup
from InlineAgent.agent import InlineAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    cluster_mcp_client = None
    try:
        # Step 2: Create MCP Client with required parameters
        logger.info("Initializing MCP client...")
        cluster_mcp_client = await MCPStreamableHttp(
            url="http://localhost:3005/mcp",
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                
            },
            sse_read_timeout=3600,  # Increase timeout to 1 hour
            timeout=30  # Increase initial connection timeout to 30 seconds
        )
        logger.info("MCP client initialized successfully")
        
        cluster_action_group = ActionGroup(
            name="ClusterGroup",
            description="Helps user get cluster details",
            mcp_clients=[cluster_mcp_client],
        )
        
        # Create agent instance
        agent = InlineAgent(
            foundation_model="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            instruction="""You are a friendly assistant that is responsible for answering user queries""",
            agent_name="cluster_agent",
            action_groups=[cluster_action_group],
        )
        
        # Interactive chat loop
        session_id = str(uuid.uuid4())  # Generate a session ID
        session_state = {}
        
        print("Welcome to Cluster Assistant! Type 'exit' to quit.")
        print(f"Session ID: {session_id}")
        
        while True:
            # Get user input
            user_input = input("\nYou: ")
            
            # Check for exit command
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("Goodbye!")
                break
            
            try:
                # Invoke agent with user input
                response = await agent.invoke(
                    input_text=user_input,
                    enable_trace=True,
                    session_id=session_id,
                    session_state=session_state,
                    end_session=False
                )
                
                # Store the response for the next interaction
                if isinstance(response, dict) and 'sessionState' in response:
                    session_state = response['sessionState']
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                print("An error occurred while processing your request. Please try again.")

    except HTTPStatusError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
        print(f"Failed to connect to MCP server: {http_err}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print("An unexpected error occurred. Please check the logs for details.")
    finally:
        if cluster_mcp_client:
            try:
                await cluster_mcp_client.cleanup()
                logger.info("MCP client cleaned up successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
