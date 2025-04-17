# file_processor/data_formatters/processor_factory.py

from typing import Dict, Callable, Any


class ProcessorFactory:
    """Factory for returning ready-to-use processor instances."""

    _processors: Dict[str, Callable[[], Any]] = {}

    @classmethod
    def register_processor(cls, file_format: str, processor_fn: Callable[[], Any]) -> None:
        cls._processors[file_format.lower()] = processor_fn

    @classmethod
    def get_processor(cls, file_format: str):
        processor_fn = cls._processors.get(file_format.lower())
        if not processor_fn:
            raise ValueError(f"No processor registered for format: {file_format}")
        return processor_fn()  # 💡 Returns a ready-to-use processor instance

    @classmethod
    def supported_formats(cls) -> list:
        return list(cls._processors.keys())