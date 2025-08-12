# Saving Traces to Amazon S3

This guide explains how to save traces from InlineAgent and Bedrock Agent invocations to an Amazon S3 bucket.

## Prerequisites

1. An AWS account with appropriate permissions to:
   - Create and access S3 buckets
   - Use Amazon Bedrock services
   - Create IAM roles and policies (if needed)

2. AWS CLI configured with credentials that have the necessary permissions
   - Run `aws configure` if you haven't set up your credentials

3. An S3 bucket or permissions to create one
   - You can create a bucket using the AWS Console or with the AWS CLI:
     ```
     aws s3 mb s3://your-trace-bucket-name --region us-northeast-1
     ```

## Specifying a Custom S3 Bucket

You can specify a custom S3 bucket for storing traces in two ways:

1. **At Invocation Time (Recommended)**: Pass the bucket name directly to the `invoke` method:
   ```python
   await agent.invoke(
       input_text="Your question here",
       trace_bucket_name="your-custom-bucket-name"
   )
   ```

2. **Using Environment Variables**: Set the following environment variables:
   ```
   TRACE_S3_BUCKET=your-custom-bucket-name
   SAVE_TRACES_TO_S3=true
   ```

## Examples

This repository includes examples demonstrating how to save traces to S3:

1. **Trace Bucket Example** - Shows how to specify a custom bucket at invocation time
   ```bash
   python amazon-bedrock-agent-samples/src/InlineAgent/examples/trace_bucket_example.py --s3-bucket your-trace-bucket-name --profile your-aws-profile --question "What is the weather in Seattle?"
   ```

2. **MCP Time Example** - Uses an InlineAgent with the MCP Time tool
   ```bash
   python amazon-bedrock-agent-samples/src/InlineAgent/examples/mcp/mcp_time/main.py --s3-bucket your-trace-bucket-name --region us-northeast-1
   ```

3. **Bedrock Agent Example** - Directly invokes a Bedrock Agent with trace saving
   ```bash
   python amazon-bedrock-agent-samples/src/InlineAgent/examples/bedrock_agent_with_s3_traces.py --s3-bucket your-trace-bucket-name --region us-northeast-1 --profile your-aws-profile --question "Your question here"
   ```

## How It Works

There are multiple approaches to save traces to S3:

### Method 1: Using the trace_bucket_name Parameter (Recommended)

The simplest approach is to pass the bucket name directly to the `invoke` method:

```python
await agent.invoke(
    input_text="Your question here",
    enable_trace=True,
    trace_bucket_name="your-custom-bucket-name"
)
```

This method is demonstrated in the `trace_bucket_example.py` example.

### Method 2: Using Environment Variables and ObservabilityConfig

This approach is used in the other examples:

1. **Environment Variables**: Set the following environment variables:
   - `TRACE_S3_BUCKET`: The name of your S3 bucket
   - `SAVE_TRACES_TO_S3`: Set to "true" to enable S3 saving
   - `AWS_REGION`: The AWS region for your S3 bucket (default: us-northeast-1)

2. **ObservabilityConfig**: Configure the ObservabilityConfig object:
   ```python
   observe_config = ObservabilityConfig()
   observe_config.SAVE_TRACES_TO_S3 = True
   observe_config.TRACE_S3_BUCKET = s3_bucket_name
   ```

3. **Force Saving Traces**: Override the ProcessL2Trace.process_trace_event method to ensure traces are saved:
   ```python
   original_process_trace_event = ProcessL2Trace.process_trace_event
   
   def force_save_traces(trace_data, span_manager, save_traces, session_id, show_traces):
       # Always save traces regardless of save_traces parameter
       ProcessL2Trace.save_trace(trace_data=trace_data, session_id=session_id)
       return original_process_trace_event(trace_data, span_manager, save_traces, session_id, show_traces)
   
   ProcessL2Trace.process_trace_event = force_save_traces
   ```

4. **Enable Tracing**: Set `save_traces=True` in the @observe decorator or enable_trace=True in agent invocations

## Trace File Structure in S3

Traces are saved to your S3 bucket with the following structure:

```
s3://your-trace-bucket-name/trace-logs/YYYY-MM-DD/session-id.json
```

Where:
- `YYYY-MM-DD` is the current date
- `session-id` is the session ID used for the agent invocation

## Troubleshooting

If you encounter issues with saving traces to S3:

1. **Check AWS Credentials**: Ensure your AWS credentials have the necessary permissions to write to the S3 bucket
2. **Verify Bucket Exists**: Make sure the specified S3 bucket exists in the correct region
3. **Check Logs**: Look for debug messages in the console output that indicate S3 operations
4. **Region Mismatch**: Ensure the region specified matches the region where your bucket is located

## Customizing Trace Saving

You can customize the trace saving behavior by modifying the `ProcessL2Trace.save_trace` method in your code. This allows you to:

- Change the S3 key structure
- Add additional metadata
- Implement custom error handling
- Format the trace data differently

For more information, refer to the InlineAgent observability documentation.
