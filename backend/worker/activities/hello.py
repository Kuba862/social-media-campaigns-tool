"""Hello-world activity: the only place in the worker allowed to touch the outside world."""

from temporalio import activity


@activity.defn
async def say_hello(name: str) -> str:
    activity.logger.info("saying hello to %s", name)
    return f"Hello, {name}!"
