from file_processor.data_formatters.processor_factory import ProcessorFactory


def create_container(container_class):
    """Factory function to create and initialize the SalesWorkerContainer."""
    container = container_class()
    container.wire(modules=[
        'file_processor.data_formatters.processors.csv.csv_processor',
        'file_processor.data_formatters.processors.text.txt_processor',
        'file_processor.data_formatters.data_formatter'
    ])
    # ✅ Now you can register the processors using the container instance
    ProcessorFactory.register_processor("csv", lambda: container.csv_formatter())
    ProcessorFactory.register_processor("txt", lambda: container.txt_processor())

    container.init_resources()
    return container