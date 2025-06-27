package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "os"

    mcp "github.com/metoro-io/mcp-golang"
    "github.com/metoro-io/mcp-golang/transport/http"
)

// Example struct for cluster tool arguments
type ClusterArgs struct {
    // Add fields as required by your MCP tool
}

func main() {
    // Replace with your MCP HTTP server endpoint
    mcpServerURL := os.Getenv("MCP_SERVER_URL")
    if mcpServerURL == "" {
        mcpServerURL = "http://localhost:8080" // or your actual endpoint
    }

    // Create HTTP transport
    transport := http.NewHttpTransport(mcpServerURL)

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

    // Prepare arguments for the cluster tool (empty if not needed)
    args := ClusterArgs{}
    argsBytes, err := json.Marshal(args)
    if err != nil {
        log.Fatalf("Failed to marshal arguments: %v", err)
    }

    // Replace with your actual tool name, e.g., "list_clusters"
    toolName := "list_clusters"
    response, err := client.CallTool(context.Background(), toolName, argsBytes)
    if err != nil {
        log.Fatalf("Failed to call tool %s: %v", toolName, err)
    }

    // Print the response
    if response != nil && len(response.Content) > 0 && response.Content[0].TextContent != nil {
        fmt.Printf("Cluster Info: %s\n", response.Content[0].TextContent.Text)
    } else {
        fmt.Println("No cluster info received.")
    }
}

// Helper to safely dereference string pointers
func derefStr(s *string) string {
    if s == nil {
        return ""
    }
    return *s
}
