"""Authentication utilities for Om Insights."""
from shared_layer.logging.logger import Logger

logger = Logger()

class AuthContext:
    """
    Authentication context for Om Insights.
    Stores authentication information for the current request.
    """
    
    def __init__(self, user_id=None, roles=None, permissions=None, token=None):
        """
        Initialize authentication context.
        
        :param user_id: User ID
        :param roles: List of user roles
        :param permissions: List of user permissions
        :param token: Authentication token
        """
        self.user_id = user_id
        self.roles = roles or []
        self.permissions = permissions or []
        self.token = token
        
    def has_role(self, role):
        """
        Check if user has a specific role.
        
        :param role: Role to check
        :return: True if user has the role, False otherwise
        """
        return role in self.roles
        
    def has_permission(self, permission):
        """
        Check if user has a specific permission.
        
        :param permission: Permission to check
        :return: True if user has the permission, False otherwise
        """
        return permission in self.permissions


def get_auth_context(event):
    """
    Extract authentication context from Lambda event.
    
    :param event: AWS Lambda event dictionary
    :return: AuthContext object
    """
    try:
        # Extract authentication information from the event
        # This is a simplified implementation - adjust based on your auth mechanism
        headers = event.get('headers', {}) or {}
        auth_header = headers.get('Authorization', '')
        
        # If using JWT tokens with Cognito or similar service
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # In a real implementation, you would validate and decode the token here
            # For now, we'll create a simple auth context
            
            # Extract claims from the request context if available
            request_context = event.get('requestContext', {})
            authorizer = request_context.get('authorizer', {})
            
            user_id = authorizer.get('claims', {}).get('sub') or 'anonymous'
            roles = authorizer.get('claims', {}).get('cognito:groups', '').split(',') if authorizer.get('claims', {}).get('cognito:groups') else []
            
            return AuthContext(
                user_id=user_id,
                roles=roles,
                permissions=[],  # Derive permissions from roles if needed
                token=token
            )
        
        # Return default auth context if no valid auth header
        return AuthContext(user_id='anonymous')
        
    except Exception as e:
        logger.error(f"Error extracting auth context: {str(e)}", exc_info=True)
        # Return a default auth context in case of errors
        return AuthContext(user_id='anonymous')