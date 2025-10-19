from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022", 
    api_key="sk-91muMTPMVB6nol36k9jTzZGttnHpRqANPayqpFFa5ZomzjFI",
    base_url="https://yinli.one",
    temperature=0
    )
