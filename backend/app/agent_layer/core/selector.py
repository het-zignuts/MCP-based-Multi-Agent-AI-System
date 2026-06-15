from app.agent_layer.core import agent_registry


class AgentSelector:

    @staticmethod
    def select_agent(message: str) -> str:
    # replace manual selection with llm call.
        text = message.lower()

        if any(word in text for word in [
            "code",
            "python",
            "bug",
            "function",
            "class",
            "api",
        ]):
            return "code"

        if any(word in text for word in [
            "research",
            "search",
            "find",
            "latest",
            "news",
        ]):
            return "research"

        if any(word in text for word in [
            "csv",
            "excel",
            "dataset",
            "analysis",
        ]):
            return "data"

        if any(word in text for word in [
            "pdf",
            "docx",
            "document",
        ]):
            return "document"

        if any(word in text for word in [
            "image",
            "picture",
            "photo",
        ]):
            return "image"

        return "general"