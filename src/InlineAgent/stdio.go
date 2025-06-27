package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "os"

    mcp "github.com/metoro-io/mcp-golang"
    "github.com/metoro-io/mcp-golang/transport/stdio"
)

// WeatherArgs matches the expected tool signature
type WeatherArgs struct {
    Location string `json:"location"`
    State    string `json:"state"`
    Unit     string `json:"unit"`
}

func main() {
    // Use stdio transport (adjust if your MCP server uses HTTP/SSE)
    transport := stdio.NewStdioServerTransportWithIO(os.Stdout, os.Stdin)

    // Create MCP client
    client := mcp.NewClient(transport)

    // Initialize client
    _, err := client.Initialize(context.Background())
    if err != nil {
        log.Fatalf("Failed to initialize MCP client: %v", err)
    }

    // List available tools
    tools, err := client.ListTools(context.Background(), nil)
    if err != nil {
        log.Fatalf("Failed to list tools: %v", err)
    }
    fmt.Println("Available tools:")
    for _, tool := range tools.Tools {
        fmt.Printf("- %s: %s\n", tool.Name, derefStr(tool.Description))
    }

    // Prepare arguments for the weather tool
    args := WeatherArgs{
        Location: "New York City",
        State:    "NY",
        Unit:     "fahrenheit",
    }

    // Convert args to JSON
    argsBytes, err := json.Marshal(args)
    if err != nil {
        log.Fatalf("Failed to marshal arguments: %v", err)
    }

    // Call the weather tool (replace with your tool's actual name if different)
    toolName := "get_current_weather"
    response, err := client.CallTool(context.Background(), toolName, argsBytes)
    if err != nil {
        log.Fatalf("Failed to call tool %s: %v", toolName, err)
    }

    // Print the response
    if response != nil && len(response.Content) > 0 && response.Content[0].TextContent != nil {
        fmt.Printf("Weather: %s\n", response.Content[0].TextContent.Text)
    } else {
        fmt.Println("No weather response received.")
    }
}

// Helper to safely dereference string pointers
func derefStr(s *string) string {
    if s == nil {
        return ""
    }
    return *s
}
