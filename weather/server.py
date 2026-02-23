from fastmcp import FastMCP

mcp = FastMCP("Weather Server")

@mcp.tool()
def get_weather(city: str = "Toronto") -> str:
    """
    Get the current weather for a specific city.
    Use this tool when the user asks about weather conditions, temperature, or forecast.
    If no city is specified, it defaults to Toronto.
    """
    return f"The weather in {city} is Sunny, 25C"
