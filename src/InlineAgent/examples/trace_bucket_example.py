import asyncio
import uuid
import argparse

from InlineAgent.agent import InlineAgent
from InlineAgent.action_group import ActionGroup


def parse_arguments():
    parser = argparse.ArgumentParser(description='Run InlineAgent with custom S3 bucket for traces')
    parser.add_argument('--s3-bucket', type=str, required=True, help='S3 bucket name for storing trace logs')
    parser.add_argument('--profile', type=str, default='default', help='AWS profile to use')
    parser.add_argument('--question', type=str, default='What is the weather in New York?', help='Question to ask the agent')
    return parser.parse_args()


# Define a simple tool for demonstration
def get_current_weather(location: str, unit: str = "fahrenheit") -> str:
    """
    Get the current weather in a given location.

    Parameters:
        location: The city, e.g., San Francisco
        unit: The unit to use, e.g., fahrenheit or celsius. Defaults to "fahrenheit"
    """
    return f"Weather in {location} is 70 {unit}"


async def main():
    # Parse command line arguments
    args = parse_arguments()
    
    print(f"Using S3 bucket '{args.s3_bucket}' for storing traces")
    
    # Create a simple action group
    weather_action_group = ActionGroup(
        name="WeatherActionGroup",
        description="This is action group to get weather",
        tools=[get_current_weather],
    )
    
    # Create session ID
    session_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}")
    
    # Create InlineAgent
    agent = InlineAgent(
        foundation_model="us.anthropic.claude-3-5-haiku-20241022-v1:0",
        instruction="You are a friendly assistant that is responsible for getting the current weather.",
        action_groups=[weather_action_group],
        agent_name="WeatherAgent",
        profile=args.profile,
    )
    
    # Invoke the agent with trace_bucket_name parameter
    print(f"Asking: {args.question}")
    response = await agent.invoke(
        input_text=args.question,
        enable_trace=True,
        session_id=session_id,
        # Pass the bucket name at invocation time
        trace_bucket_name=args.s3_bucket
    )
    
    print("\nAgent response:")
    print(response)
    
    print(f"\nTraces have been saved to S3 bucket: {args.s3_bucket}")
    print(f"You can find the complete trace at: s3://{args.s3_bucket}/traces/{session_id}/complete_trace.json")


if __name__ == "__main__":
    asyncio.run(main())
