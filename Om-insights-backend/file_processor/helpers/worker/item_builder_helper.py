from datetime import datetime
from file_processor.model.sales_record_dto import SalesRecordDTO

class ItemBuilderHelper:
    @staticmethod
    def sales_builder(record, context, status="pending"):
        dto = SalesRecordDTO.parse_obj({
            **record,
            "business_id": context.business_id,
            "upload_timestamp": datetime.now().isoformat(),
            "business_region": context.business_region,
            "subscription_type": context.subscription_type,
            "status": status
        })
        return dto.to_dynamodb_item()
