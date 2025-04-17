import os
import json

class IndexTemplateManager:
    def get_template(index_name: str) -> dict:
        """Load the index template JSON from shared index_templates folder"""
        base_path = os.path.join(os.path.dirname(__file__), "index_templates")
        path = os.path.join(base_path, f"{index_name}.json")
        with open(path, "r") as f:
            return json.load(f)