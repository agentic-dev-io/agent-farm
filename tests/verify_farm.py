import subprocess
import time

def test_server_startup():
    print("Starting server process...")
    # Using uv run to ensure dependencies are present
    process = subprocess.Popen(
        ["uv", "run", "src/agent_farm/main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd="d:/farmer_agent"
    )
    
    # Wait for startup (downloads can take time)
    print("Waiting for startup (15s)...")
    time.sleep(15)
    
    # Check if it's still running
    if process.poll() is not None:
        print("Server exited prematurely!")
        print("STDERR:", process.stderr.read())
        return

    print("Server seems to be running. Sending basic JSON-RPC request...")
    
    # Simple JSON-RPC initialize request (just to see if we get a response or if it crashes)
    # Note: real MCP handshake is more complex, but this proves stdin/stdout is hooked up.
    rpc_request = '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}\n'
    
    try:
        stdout, stderr = process.communicate(input=rpc_request, timeout=5)
        print("STDOUT:", stdout)
        print("STDERR:", stderr)
    except subprocess.TimeoutExpired:
        print("Timeout waiting for response. Server might be running but not responding or blocked.")
        process.kill()
        out, err = process.communicate()
        print("STDERR (after kill):", err)

if __name__ == "__main__":
    test_server_startup()
