import os
import shutil
import subprocess
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def clean_up_efs(efs_path="/mnt/efs/"):
    """
    Deletes all contents inside the specified EFS path while keeping the directory itself.

    Parameters:
        efs_path (str): The EFS directory path to clean. Defaults to '/mnt/efs/'.

    Returns:
        dict: A dictionary containing the cleanup status, a message, and the final directory output.
    """
    try:
        logger.info("🚀 Cleanup of EFS started.")

        # Ensure the EFS directory exists before cleaning up
        if not os.path.exists(efs_path):
            os.makedirs(efs_path)
            logger.info(f"✅ Created missing EFS directory: {efs_path}")
        else:
            logger.info(f"✅ EFS directory exists: {efs_path}")

        # Delete everything inside the EFS directory while keeping the directory itself
        for item in os.listdir(efs_path):
            item_path = os.path.join(efs_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)  # Delete file or symbolic link
                    logger.info(f"🗑️ Deleted file: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)  # Delete directory and its contents
                    logger.info(f"🗑️ Deleted directory: {item_path}")
            except Exception as delete_error:
                logger.error(f"❌ Failed to delete {item_path}: {delete_error}")

        # Verify the cleanup and list the final contents of the directory
        remaining_contents = os.listdir(efs_path)
        logger.info(f"📂 Remaining contents of {efs_path} (should be empty): {remaining_contents}")

        output = subprocess.run(["ls", "-lah", efs_path], capture_output=True, text=True)
        logger.info(f"✅ Final output of {efs_path}: \n{output.stdout.strip()}")

        return {
            "status": "success",
            "message": "✅ Cleanup complete. EFS is now empty.",
            "output": output.stdout.strip()
        }

    except Exception as e:
        logger.error(f"❌ Error during cleanup: {str(e)}")
        return {"status": "error", "message": str(e)}


# Example usage
if __name__ == "__main__":
    result = clean_up_efs()
    print(result)