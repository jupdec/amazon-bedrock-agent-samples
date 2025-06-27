package main
import (
    "context"
    "fmt"
    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/service/bedrockagentruntime"
)

func main() {
    ctx := context.Background()
    cfg, _ := config.LoadDefaultConfig(ctx)
    client := bedrockagentruntime.NewFromConfig(cfg)

    // Define your inline agent
    input := &bedrockagentruntime.InvokeInlineAgentInput{
        FoundationModel: aws.String("us.anthropic.claude-3-5-haiku-20241022-v1:0"),
        Instruction:     aws.String("You are a friendly assistant that is responsible for getting the current weather."),
        // Define ActionGroups and Tools here as per the SDK's struct definitions
        // ActionGroups: ...
        InputText:       aws.String("What is the weather of New York City, NY?"),
    }

    output, err := client.InvokeInlineAgent(ctx, input)
    if err != nil {
        panic(err)
    }

    fmt.Println("Agent response:", *output.OutputText)
}
