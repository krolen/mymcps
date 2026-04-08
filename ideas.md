- Maybe add paging to searxng


additional configs for http servers:
# Create the main MCP server
# mcp = FastMCP(name="Data Server", instructions="""
#   This server provides useful tools to get additional information such as time, web search
# """)
# remote_proxy = create_proxy(
#     "http://localhost:7100/mcp",
#     name="Searxng web search"
# )
#
# @mcp.tool()
# def run_tool_a(input: str) -> str:
#     result = subprocess.run(
#         ["/envs/tool_a/bin/python", "tool_a_runner.py", input],
#         capture_output=True
#     )
#     return result.stdout.decode()
# # Mount the sub-servers
# mcp.mount(time_mcp, namespace = "timeserver")
# mcp.mount(remote_proxy, namespace = "Web_Search_MCP_server")
# mcp.mount(weather_mcp)
# mcp.mount(searxng_mcp)
