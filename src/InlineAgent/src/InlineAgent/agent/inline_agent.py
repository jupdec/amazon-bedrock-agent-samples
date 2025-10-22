from dataclasses import dataclass, field
from datetime import datetime, UTC

import json
import uuid
import copy
import os
import boto3
from decimal import Decimal
from decimal import Decimal
from typing import Callable, Dict, List, Literal, Optional, Tuple, Union
from pydantic import Field
from termcolor import colored
from rich.console import Console
from rich.markdown import Markdown


from InlineAgent.action_group import ActionGroups
from InlineAgent.action_group.action_group import ActionGroup
from InlineAgent.agent.collaborator_agent_instance import CollaboratorAgent
from InlineAgent.constants import (
    USER_INPUT_ACTION_GROUP_NAME,
    TraceColor,
)
from InlineAgent.agent.process_roc import ProcessROC
from InlineAgent.observability import Trace
from InlineAgent.knowledge_base import KnowledgeBasePlugin
from InlineAgent.tools.mcp import MCPServer
from InlineAgent.types import (
    InlineCollaboratorAgentConfig,
    InlineCollaboratorConfigurations,
)

import requests

@dataclass
class InlineAgent:
    foundation_model: str
    agent_name: str
    instruction: str
    action_groups: ActionGroups = field(default_factory=list)
    agent_collaboration: Literal["SUPERVISOR", "SUPERVISOR_ROUTER", "DISABLED"] = field(
        default="DISABLED"
    )
    collaborator_configuration: Optional[InlineCollaboratorAgentConfig] = None
    collaborators: Optional[List[Union["InlineAgent", CollaboratorAgent]]] = None
    customer_encryption_key_arn: Optional[str] = None
    guardrail_configuration: Dict = field(default_factory=dict)
    idle_session_ttl_in_seconds: Optional[int] = None
    knowledge_bases: List[KnowledgeBasePlugin] = field(default_factory=list)
    prompt_override_configuration: Dict = field(default_factory=dict)

    profile: str = field(default="default")
    user_input: bool = False
    tool_map: Dict[str, Callable] = None

    @property
    def session(self) -> boto3.Session:
        """Lazy loading of AWS session"""
        try:
            return boto3.Session(profile_name=self.profile)
        except:
            region = self._get_region_from_ec2_metadata()
            return boto3.Session(region_name=region)

    @property
    def account_id(self) -> str:
        sts_client = self.session.client("sts")
        identity = sts_client.get_caller_identity()
        return identity["Account"]

    @property
    def region(self) -> str:
        return self.session.region_name

    def _get_region_from_ec2_metadata(self) -> Optional[str]:
        """
        Retrieve the current region from EC2 Instance Metadata Service (IMDSv2).
        
        Returns:
            Optional[str]: AWS region name or None if unavailable
        """
        try:
            # Step 1: Get session token for IMDSv2
            token_response = requests.put(
                "http://169.254.169.254/latest/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                timeout=2
            )
            
            if token_response.status_code != 200:
                return None
            
            token = token_response.text
            
            # Step 2: Use token to get region
            region_response = requests.get(
                "http://169.254.169.254/latest/meta-data/placement/region",
                headers={"X-aws-ec2-metadata-token": token},
                timeout=2
            )
            
            if region_response.status_code == 200:
                return region_response.text
            
            return None
            
        except requests.RequestException as e:
            return None
        
    def __post_init__(self):

        if self.knowledge_bases:
            knowledge_bases_list = list()
            for knowledge_base in self.knowledge_bases:
                if not isinstance(knowledge_base, KnowledgeBasePlugin):
                    knowledge_bases_list.append(
                        KnowledgeBasePlugin.model_validate(knowledge_base).to_dict()
                    )
                else:
                    knowledge_bases_list.append(knowledge_base.to_dict())

            self.knowledge_bases = knowledge_bases_list

        if self.action_groups:
            if not isinstance(self.action_groups, ActionGroups):
                for action_group in self.action_groups:
                    ActionGroup.model_validate(action_group)
                self.action_groups = ActionGroups(action_groups=self.action_groups)

            self.tool_map = self.action_groups.tool_map

            self.action_groups = self.action_groups.actionGroups

        if self.user_input:
            if self.action_groups:
                self.action_groups.append(
                    {
                        "actionGroupName": USER_INPUT_ACTION_GROUP_NAME,
                        "parentActionGroupSignature": "AMAZON.UserInput",
                    }
                )
            else:
                self.action_groups = [
                    {
                        "actionGroupName": USER_INPUT_ACTION_GROUP_NAME,
                        "parentActionGroupSignature": "AMAZON.UserInput",
                    }
                ]

        match self.agent_collaboration:
            case "DISABLED" if self.collaborators is not None:
                raise ValueError(
                    "Collaborators should be None if agentCollaboration is DISABLED"
                )
            case "SUPERVISOR" | "SUPERVISOR_ROUTER" if self.collaborators is None:
                raise ValueError(
                    "Collaborators should not be None if agentCollaboration is SUPERVISOR or SUPERVISOR_ROUTER"
                )

        if self.collaborators:
            for collaborator in self.collaborators:
                if not isinstance(collaborator, CollaboratorAgent) and not isinstance(
                    collaborator, InlineAgent
                ):
                    raise ValueError(
                        "collaborators must be either instance of class `InlineAgent` or `CollaboratorAgent`"
                    )
        if self.collaborator_configuration is None:
            self.collaborator_configuration = InlineCollaboratorAgentConfig()
        else:
            if not isinstance(
                self.collaborator_configuration, InlineCollaboratorAgentConfig
            ):
                self.collaborator_configuration = (
                    InlineCollaboratorAgentConfig.model_validate(
                        self.collaborator_configuration
                    )
                )

        if not self.collaborator_configuration.instruction:
            self.collaborator_configuration.instruction = self.instruction

    def get_invoke_params(self) -> Dict:
        invokeParams = dict()
        match self.agent_collaboration:
            case "DISABLED":
                invokeParams = {
                    "actionGroups": self.action_groups,
                    "customerEncryptionKeyArn": self.customer_encryption_key_arn,
                    "foundationModel": self.foundation_model,
                    "guardrailConfiguration": self.guardrail_configuration,
                    "idleSessionTTLInSeconds": self.idle_session_ttl_in_seconds,
                    "instruction": self.instruction,
                    "knowledgeBases": self.knowledge_bases,
                    "promptOverrideConfiguration": self.prompt_override_configuration,
                }
            case "SUPERVISOR" | "SUPERVISOR_ROUTER":

                collaborator_configurations: List[InlineCollaboratorConfigurations] = []
                collaborators_param: List[Dict] = []
                for collaborator in self.collaborators:

                    if isinstance(collaborator, CollaboratorAgent):
                        collaborator_configurations.append(collaborator.to_dict())
                    elif isinstance(collaborator, InlineAgent):
                        collaborator_configurations.append(
                            {
                                "collaboratorInstruction": collaborator.collaborator_configuration.instruction,
                                "collaboratorName": collaborator.agent_name,
                                "relayConversationHistory": collaborator.collaborator_configuration.relayConversationHistory,
                            }
                        )

                        collaborators_param.append(collaborator.get_agent_params())
                invokeParams = {
                    "actionGroups": self.action_groups,
                    "agentCollaboration": self.agent_collaboration,
                    "collaboratorConfigurations": collaborator_configurations,
                    "collaborators": collaborators_param,
                    "customerEncryptionKeyArn": self.customer_encryption_key_arn,
                    "foundationModel": self.foundation_model,
                    "guardrailConfiguration": self.guardrail_configuration,
                    "idleSessionTTLInSeconds": self.idle_session_ttl_in_seconds,
                    "instruction": self.instruction,
                    "knowledgeBases": self.knowledge_bases,
                    "promptOverrideConfiguration": self.prompt_override_configuration,
                }

        return {k: v for k, v in invokeParams.items() if v}

    def get_agent_params(self):
        agentParams = {
            "actionGroups": self.action_groups,
            "agentCollaboration": self.agent_collaboration,
            "agentName": self.agent_name,
            "collaborators": self.collaborators,
            "customerEncryptionKeyArn": self.customer_encryption_key_arn,
            "foundationModel": self.foundation_model,
            "guardrailConfiguration": self.guardrail_configuration,
            "idleSessionTTLInSeconds": self.idle_session_ttl_in_seconds,
            "instruction": self.instruction,
            "knowledgeBases": self.knowledge_bases,
            "promptOverrideConfiguration": self.prompt_override_configuration,
        }
        return {k: v for k, v in agentParams.items() if v}

    async def invoke(
        self,
        input_text: str,
        enable_trace: bool = True,
        session_id: str = str(uuid.uuid4()),
        request_id: str = str(uuid.uuid4()),
        end_session: bool = False,
        session_state: Dict = None,
        add_citation: bool = False,
        process_response: bool = True,
        truncate_response: int = None,
        streaming_configurations: Dict = {"streamFinalResponse": False},
        bedrock_model_configurations: Dict = {
            "performanceConfig": {"latency": "standard"}
        },
        trace_bucket_name: Optional[str] = None,
        dynamodb_table_name: Optional[str] = "agent-sessions-table",
    ):
        if session_state is None:
            session_state = {}

        print(f"SessionId: {session_id}")

        agent_answer = ""
        
        bedrock_agent_runtime = self.session.client(
            "bedrock-agent-runtime"
        )

        inlineSessionState = copy.deepcopy(session_state)

        total_input_tokens = 0
        total_output_tokens = 0
        total_llm_calls = 0
        all_traces = []  # Collect all traces

        time_before_call = datetime.now(UTC)
        cite = None
        orch_step = 0
        sub_step = 0

        stream_final_response = streaming_configurations["streamFinalResponse"]
        print(self.get_invoke_params())
        while not agent_answer:
            if inlineSessionState:
                response = bedrock_agent_runtime.invoke_inline_agent(
                    sessionId=session_id,
                    inputText=input_text,
                    enableTrace=enable_trace,
                    endSession=end_session,
                    inlineSessionState=inlineSessionState,
                    streamingConfigurations=streaming_configurations,
                    bedrockModelConfigurations=bedrock_model_configurations,
                    **self.get_invoke_params(),
                )
            else:
                response = bedrock_agent_runtime.invoke_inline_agent(
                    sessionId=session_id,
                    inputText=input_text,
                    enableTrace=enable_trace,
                    endSession=end_session,
                    streamingConfigurations=streaming_configurations,
                    bedrockModelConfigurations=bedrock_model_configurations,
                    **self.get_invoke_params(),
                )

            if not process_response:
                return response

            inlineSessionState = copy.deepcopy(session_state)

            event_stream = response["completion"]

            try:
                for event in event_stream:
                    print(f"DEBUG: Processing event with keys: {list(event.keys())}")
                    print(json.dumps(event, indent=2, default=str))  # Uncomment to see all events
                    if "files" in event:
                        files_event = event["files"]

                        console = Console()
                        print("\n\n")
                        console.print(Markdown("**Files saved in output directory**"))

                        files_list = files_event["files"]
                        for idx, this_file in enumerate(files_list):
                            file_bytes = this_file["bytes"]

                            # save bytes to file, given the name of file and the bytes
                            directory_path = os.path.join(os.getcwd(), "output")
                            if not os.path.exists(directory_path):
                                try:
                                    os.makedirs(directory_path, exist_ok=True)
                                except OSError as e:
                                    print(f"Error creating directory output: {e}")
                                    raise

                            if not os.path.exists(
                                os.path.join(directory_path, str(session_id))
                            ):
                                try:
                                    os.makedirs(
                                        os.path.join(directory_path, str(session_id)),
                                        exist_ok=True,
                                    )
                                except OSError as e:
                                    print(f"Error creating directory output: {e}")
                                    raise

                            file_name = os.path.join(
                                directory_path, str(session_id), this_file["name"]
                            )
                            with open(file_name, "wb") as f:
                                f.write(file_bytes)

                    if "returnControl" in event:
                        inlineSessionState = await ProcessROC.process_roc(
                            inlineSessionState=inlineSessionState,
                            roc_event=event["returnControl"],
                            tool_map=self.tool_map,
                        )

                    # Collect traces
                    if "trace" in event:
                        print(f"DEBUG: Found trace event with keys: {list(event['trace'].keys())}")
                        all_traces.append(event["trace"])
                        
                        # Store EVERY trace event in DynamoDB and S3
                        try:
                            print(f"DEBUG: Storing trace event")
                            trace_id = str(uuid.uuid4())
                            timestamp = datetime.now(UTC).isoformat()
                            
                            # Determine trace type and extract token info if available
                            trace_type = "unknown"
                            input_tokens = 0
                            output_tokens = 0
                            llm_calls = 0
                            
                            if "trace" in event["trace"]:
                                # This is an LLM execution trace
                                trace_type = "llm_execution"
                                input_tokens, output_tokens, llm_calls = Trace.parse_trace(
                                    trace=event["trace"]["trace"],
                                    truncateResponse=truncate_response,
                                    agentName=self.agent_name,
                                )
                                total_input_tokens += int(input_tokens)
                                total_output_tokens += int(output_tokens)
                                total_llm_calls += int(llm_calls)
                            else:
                                # This is another type of trace (orchestration, preprocessing, etc.)
                                if "orchestrationTrace" in event["trace"]:
                                    trace_type = "orchestration"
                                elif "preProcessingTrace" in event["trace"]:
                                    trace_type = "preprocessing"
                                elif "postProcessingTrace" in event["trace"]:
                                    trace_type = "postprocessing"
                                elif "guardrailTrace" in event["trace"]:
                                    trace_type = "guardrail"
                            
                            # Create trace data for S3
                            trace_data = {
                                "sessionId": session_id,
                                "requestId": request_id,
                                "traceId": trace_id,
                                "inputText": input_text,
                                "agentName": self.agent_name,
                                "timestamp": timestamp,
                                "traceType": trace_type,
                                "tokenUsage": {"input": int(input_tokens), "output": int(output_tokens)} if input_tokens or output_tokens else None,
                                "trace": event["trace"]
                            }
                            

                            # Store only rationale traces in DynamoDB
                            print(f"DEBUG: DynamoDB table name: {dynamodb_table_name}")
                            print(f"DEBUG: Checking trace structure: {list(event['trace'].keys())}")
                            if dynamodb_table_name:
                                try:
                                    # Check if this trace has rationale
                                    # Handle both direct orchestrationTrace and nested trace.orchestrationTrace
                                    orchestration_trace = event["trace"].get("orchestrationTrace")
                                    if not orchestration_trace and "trace" in event["trace"]:
                                        orchestration_trace = event["trace"]["trace"].get("orchestrationTrace")
                                    
                                    if orchestration_trace and "rationale" in orchestration_trace:
                                        rationale_text = orchestration_trace["rationale"].get("text", "")
                                        print(f"🧠 RATIONALE FOUND: {rationale_text[:100]}...")
                                        
                                        # Only store if we have rationale text
                                        if rationale_text:
                                            print(f"💾 STORING RATIONALE TO DYNAMODB")
                                            dynamodb = self.session.resource('dynamodb')
                                            table = dynamodb.Table(dynamodb_table_name)
                                            print(f"DEBUG: DynamoDB table connection established")
                                            
                                            # Check if session/request item exists
                                            response = table.get_item(
                                                Key={
                                                    'sessionId': session_id,
                                                    'requestId': request_id
                                                }
                                            )
                                            
                                            if 'Item' in response:
                                                # Item exists, append to thinking field
                                                existing_thinking = response['Item'].get('thinking', '')
                                                
                                                if existing_thinking:
                                                    new_thinking = existing_thinking + "\n" + rationale_text
                                                else:
                                                    new_thinking = rationale_text
                                                
                                                # Update the item
                                                table.update_item(
                                                    Key={
                                                        'sessionId': session_id,
                                                        'requestId': request_id
                                                    },
                                                    UpdateExpression='SET thinking = :thinking, lastUpdated = :timestamp, #ttl = :ttl',
                                                    ExpressionAttributeNames={
                                                        '#ttl': 'ttl'
                                                    },
                                                    ExpressionAttributeValues={
                                                        ':thinking': new_thinking,
                                                        ':timestamp': timestamp,
                                                        ':ttl': int((datetime.now(UTC).timestamp() + 86400 * 30))
                                                    }
                                                )
                                                print(f"SUCCESS: Appended rationale to existing thinking field")
                                            
                                            else:
                                                # Item doesn't exist, create new with thinking field
                                                print(f"DEBUG: Creating new DynamoDB item")
                                                dynamodb_item = {
                                                    'sessionId': session_id,
                                                    'requestId': request_id,
                                                    'agentName': self.agent_name,
                                                    'inputText': input_text,
                                                    'timestamp': timestamp,
                                                    'lastUpdated': timestamp,
                                                    'ttl': int((datetime.now(UTC).timestamp() + 86400 * 30)),
                                                    'thinking': rationale_text
                                                }
                                                
                                                table.put_item(Item=dynamodb_item)
                                                print(f"SUCCESS: Created new item with thinking field")
                                            
                                            print(f"SUCCESS: Rationale stored: {rationale_text[:50]}...")
                                    
                                except Exception as dynamo_error:
                                    print(f"ERROR: Failed to store rationale to DynamoDB: {dynamo_error}")
                            
                        except Exception as e:
                            print(f"ERROR: Failed to store trace: {e}")
                            print(f"ERROR: Trace event keys: {list(event.get('trace', {}).keys()) if 'trace' in event else 'No trace in event'}")

                    # Get Final Answer
                    if "chunk" in event:
                        if add_citation:
                            if "attribution" in event["chunk"]:
                                agent_answer, cite = Trace.add_citation(
                                    citations=event["chunk"]["attribution"][
                                        "citations"
                                    ],
                                    cite=1 if not cite else cite,
                                )
                            else:
                                data = event["chunk"]["bytes"]
                                agent_answer += data.decode("utf8")
                                print(
                                    colored(
                                        data.decode("utf8"), TraceColor.final_output
                                    ),
                                    end="",
                                )
                        elif not add_citation:
                            data = event["chunk"]["bytes"]
                            if stream_final_response:
                                agent_answer += data.decode("utf8")
                                print(
                                    colored(
                                        data.decode("utf8"), TraceColor.final_output
                                    ),
                                    end="",
                                )
                            else:
                                agent_answer += data.decode("utf8")
                                print(
                                    colored(agent_answer, TraceColor.final_output),
                                    end="",
                                )

            except Exception as e:
                print(
                    colored("Caught exception while invoking Agent", TraceColor.error)
                )
                print(colored(f"input text: {input_text}", TraceColor.error))
                print(
                    colored(
                        f"request ID: {response['ResponseMetadata']['RequestId']}, retries: {response['ResponseMetadata']['RetryAttempts']}\n",
                        TraceColor.error,
                    )
                )
                print(colored(f"Error: {e}", TraceColor.error))
                raise Exception("Unexpected exception: ", e)

        duration = datetime.now(UTC) - time_before_call

        print(
            colored(
                f"\nAgent made a total of {total_llm_calls} LLM calls, "
                + f"using {total_input_tokens+total_output_tokens} tokens "
                + f"(in: {total_input_tokens}, out: {total_output_tokens})"
                + f", and took {duration.total_seconds():,.1f} total seconds",
                TraceColor.stats,
            )
        )

        # Store summary of all traces and ensure we don't store the old combined trace file
        if all_traces:
            try:
                # Create summary data
                summary_data = {
                    "sessionId": session_id,
                    "inputText": input_text,
                    "agentName": self.agent_name,
                    "timestamp": time_before_call.isoformat(),
                    "duration": duration.total_seconds(),
                    "tokenUsage": {"input": total_input_tokens, "output": total_output_tokens},
                    "totalLlmCalls": total_llm_calls,
                    "traceCount": len(all_traces)
                }
                
                # Store summary
                s3_client = self.session.client('s3')
                bucket_name = trace_bucket_name or 'eks_beaver_inline_agent_logs'
                summary_key = f"sessions/{session_id}/{request_id}/summary.json"
                s3_client.put_object(Bucket=bucket_name, Key=summary_key, Body=json.dumps(summary_data, default=str, indent=2))
                print(f"Trace summary stored to s3://{bucket_name}/{summary_key}")

            except Exception as e:
                print(f"Failed to store trace summary to S3: {e}")

        return agent_answer
