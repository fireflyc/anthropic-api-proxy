import anthropic
import json
from anthropic import beta_tool

# Initialize client
client = anthropic.Anthropic(base_url="http://localhost:8080",
                             api_key="<APIKEY>")


# Define tools using the decorator
@beta_tool
def get_weather(location: str, unit: str = "fahrenheit") -> str:
    """Get the current weather in a given location.

    Args:
        location: The city and state, e.g. San Francisco, CA
        unit: Temperature unit, either 'celsius' or 'fahrenheit'
    """
    # In a full implementation, you'd call a weather API here
    return json.dumps({"temperature": "20°C", "condition": "Sunny"})


@beta_tool
def calculate_sum(a: int, b: int) -> str:
    """Add two numbers together.

    Args:
        a: First number
        b: Second number
    """
    return str(a + b)


def main():
    # Use the tool runner
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-6",
        max_tokens=1024,
        stream=True,
        tools=[get_weather, calculate_sum],
        messages=[
            {
                "role": "user",
                "content": "What's the weather like in Paris? Also, what's 15 + 27?",
            }
        ],
    )
    #for message in runner:
    #    print(message.content[0].text)

    for message_stream in runner:
        print("message:", message_stream.get_final_message().content[0])

    print(runner.until_done())

if __name__ == "__main__":
    main()
