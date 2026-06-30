import boto3

from app.config import settings


class CognitoClient:
    def __init__(self) -> None:
        self.client = boto3.client("cognito-idp", region_name=settings.cognito_region)
        self.client_id = settings.cognito_client_id
        self.user_pool_id = settings.cognito_user_pool_id

    def sign_up(self, email: str, password: str, name: str) -> str:
        """Crea el usuario en Cognito. Devuelve el `sub` (cognito_sub)."""
        response = self.client.sign_up(
            ClientId=self.client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": name},
            ],
        )
        return response["UserSub"]

    def confirm_sign_up(self, email: str, code: str) -> None:
        self.client.confirm_sign_up(
            ClientId=self.client_id,
            Username=email,
            ConfirmationCode=code,
        )

    def resend_confirmation_code(self, email: str) -> None:
        self.client.resend_confirmation_code(ClientId=self.client_id, Username=email)

    def initiate_auth(self, email: str, password: str) -> dict:
        return self.client.initiate_auth(
            ClientId=self.client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": password},
        )

    def respond_to_mfa_challenge(self, session: str, email: str, code: str) -> dict:
        return self.client.respond_to_auth_challenge(
            ClientId=self.client_id,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=session,
            ChallengeResponses={"USERNAME": email, "SOFTWARE_TOKEN_MFA_CODE": code},
        )

    def refresh_tokens(self, refresh_token: str) -> dict:
        return self.client.initiate_auth(
            ClientId=self.client_id,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": refresh_token},
        )

    def global_sign_out(self, access_token: str) -> None:
        self.client.global_sign_out(AccessToken=access_token)

    def change_password(self, access_token: str, old_password: str, new_password: str) -> None:
        self.client.change_password(
            AccessToken=access_token,
            PreviousPassword=old_password,
            ProposedPassword=new_password,
        )

    def admin_delete_user(self, email: str) -> None:
        try:
            self.client.admin_delete_user(UserPoolId=self.user_pool_id, Username=email)
        except self.client.exceptions.UserNotFoundException:
            pass


def get_cognito() -> CognitoClient:
    return CognitoClient()
